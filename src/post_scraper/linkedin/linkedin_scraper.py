import os
import re
import logging
import time
import random
import json
from datetime import datetime
from pathlib import Path

from typing import Dict, Any, Optional, List

from common.utils import dump_to_parquet, upload_parquet_to_dls, clean_file
from common.config import Config
from common.utils import setup_logging

from scraping.linkedin.linkedin_parser import LinkedInParser
from scraping.core.web_scraper import IWebScraper
from scraping.linkedin.linkedin_post_extractor import ExtractLinkedInPostException
from scraping.linkedin.linkedin_profile_extractor import LinkedInProfileExtractor
from network.relation import RelationshipModel, RelationType
from scraping.linkedin.linkedin_parser import wait_for_selenium
from scraping.linkedin.linkedin_parser import LinkedInParser


def extract_slug_from_linkedin_url(url: str) -> Optional[str]:
    """Extract LinkedIn profile slug from URL."""
    if not url:
        return None
    if "/in/" in url:
        slug = url.rstrip("/").split("/in/")[-1]
        slug = slug.split("?")[0]
        return slug
    return None

def build_linkedin_relationship_model_from_data(
    followers_data: Dict[str, Any],
    connections_data: Dict[str, Any],
    influencer_priority_list: Optional[List[str]] = None
) -> RelationshipModel:
    """
    Build RelationshipModel from scraped followers and connections JSON data.
    
    Args:
        followers_data: Dictionary with followers data
        connections_data: Dictionary with connections data
        influencer_priority_list: Optional list of influencers in priority order
    
    Returns:
        RelationshipModel with relationships
    """
    graph = RelationshipModel()
    influencer_slugs = set()

    # Collect influencer slugs from data
    for entry in followers_data.get("influencers", []):
        influencer_url = entry.get("influencer_url", "")
        if influencer_url:
            slug = extract_slug_from_linkedin_url(influencer_url)
            if slug:
                influencer_slugs.add(slug)

    for entry in connections_data.get("influencers", []):
        influencer_url = entry.get("influencer_url", "")
        if influencer_url:
            slug = extract_slug_from_linkedin_url(influencer_url)
            if slug:
                influencer_slugs.add(slug)

    # Initialize influencers in graph base
    if influencer_priority_list:
        priority_slugs_set = {extract_slug_from_linkedin_url(url) if "/in/" in url else url for url in influencer_priority_list if url}
        for slug in influencer_priority_list:
            processed_slug = extract_slug_from_linkedin_url(slug) if "/in/" in slug else slug
            if processed_slug and processed_slug in influencer_slugs:
                graph._init_user_relations(processed_slug)
        remaining_influencers = sorted([s for s in influencer_slugs if s not in priority_slugs_set])
        for slug in remaining_influencers:
            graph._init_user_relations(slug)
    else:
        for influencer_slug in sorted(influencer_slugs):
            graph._init_user_relations(influencer_slug)

    # Process followers
    for entry in followers_data.get("influencers", []):
        influencer_url = entry.get("influencer_url", "")
        influencer_slug = extract_slug_from_linkedin_url(influencer_url) if influencer_url else None
        if not influencer_slug:
            continue

        for follower in entry.get("followers", []):
            follower_url = follower.get("follower_url", "")
            follower_slug = extract_slug_from_linkedin_url(follower_url) if follower_url else None
            if follower_slug:
                graph.add(RelationType.FOLLOW, follower_slug, influencer_slug)

    # Process connections
    for entry in connections_data.get("influencers", []):
        influencer_url = entry.get("influencer_url", "")
        influencer_slug = extract_slug_from_linkedin_url(influencer_url) if influencer_url else None
        if not influencer_slug:
            continue

        for connection in entry.get("connections", []):
            connection_url = connection.get("connection_url", "")
            connection_slug = extract_slug_from_linkedin_url(connection_url) if connection_url else None
            if connection_slug:
                graph.add(RelationType.CONNECTION, influencer_slug, connection_slug)

    return graph

setup_logging()
logger = logging.getLogger(__name__)

class LinkedInPostFormatter:
    """
    Enriches scraped LinkedIn post data with categorization metadata.
    """
    TOPIC_RULES = {
        "Natural Language Processing (NLP)": [
            r"\b(nlp|natural language)\b",
            r"\b(text classification|sentiment analysis|summarization)\b",
            r"\b(bert|gpt|llm|language model)\b",
        ],

        "Computer Vision (CV)": [
            r"\b(computer vision)\b",
            r"\bcv\b(?=\s|$)",
            r"\b(image|video)\b",
            r"\b(object detection|image classification|segmentation)\b",
            r"\b(sam|segment anything)\b",
        ],

        "Generative AI": [
            r"\b(generative ai|gen ai)\b",
            r"\b(chatgpt|gpt-4|dall[- ]?e|stable diffusion)\b",
            r"\b(text[- ]?to[- ]?image|text generation)\b",
            r"\b(ai agent|ai agents|personal ai|ai assistant)\b",
            r"\b(signal brain|ai brain)\b",
            r"\b(ai skills|ai era|ai world)\b",
            r"\b(ai framework|ai usage|using ai)\b",
            r"\bcursor\b", 
        ],

        "Data Analytics": [
            r"\b(data analytics|business intelligence|bi)\b",
            r"\b(powerbi|power bi|google looker|looker studio)\b",
            r"\b(dashboard|reporting)\b",
        ],

        "Orchestration": [
            r"\b(orchestration|workflow)\b",
            r"\b(kubeflow|apache airflow|airflow)\b",
            r"\b(pipeline automation)\b",
        ],

        "Robotics": [
            r"\b(robotics|robot)\b",
            r"\b(autonomous|automation)\b",
            r"\b(robot arm|industrial robot)\b",
        ],

        "Machine Learning (ML)": [
            r"\b(machine learning)\b",
            r"\bml\b(?=\s|$)",
            r"\b(supervised|unsupervised|reinforcement learning)\b",
            r"\b(fraud detection|classification|regression)\b",
            r"\b(model training|model inference)\b",
            r"\b(xgboost|gradient boosting|boosting)\b",
            r"\b(tabular data|tabular|structured data)\b",
            r"\b(deep learning|neural network|neural networks)\b",
            r"\b(random forest|decision tree|trees)\b",
        ],

        "Non-technical": [
            r"\b(business impact|use case|roi|cost reduction)\b",
            r"\b(strategy|market|trend)\b",
        ],
    }

    INDUSTRY_MAP = {
        "Natural Language Processing (NLP)": "Technology / AI",
        "Computer Vision (CV)": "Technology / AI",
        "Generative AI": "Technology / AI",
        "Machine Learning (ML)": "Technology / AI",
        "Data Analytics": "Business Intelligence",
        "Orchestration": "Data Engineering",
        "Robotics": "Manufacturing / Automation",
        "Non-technical": "Business",
    }

    def __init__(self):
        self._zero_shot_import_failed = False

    def entry_format(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format LinkedIn post data for CSV output.
        Extracts specific topics from post content using TOPIC_RULES.
        """
        enriched = raw_data.copy()
        
        # Extract specific topics from post content (not just "technical"/"non-technical")
        content = enriched.get("content") or enriched.get("text", "")
        extracted_topics = self._extract_topics(content)
        zero_shot_label = self._classify_tech_non_tech_zero_shot(content)
        upstream_topic = enriched.get("topic")
        upstream_non_tech = (
            (isinstance(upstream_topic, str) and upstream_topic.strip().lower() == "non-technical")
            or (
                isinstance(upstream_topic, list)
                and any(str(t).strip().lower() == "non-technical" for t in upstream_topic)
            )
        )

        # Respect non-technical classification from upstream extractor or zero-shot model.
        if upstream_non_tech or zero_shot_label == "non-technical":
            topics = ["non-technical"]
            is_tech = False
        elif "Non-technical" in extracted_topics or "non-technical" in extracted_topics:
            topics = ["non-technical"]
            is_tech = False
        elif not extracted_topics:
            topic = enriched.get("topic", "non-technical")
            if topic == "technical":
                topics = ["technical"]
                is_tech = True
            else:
                topics = ["non-technical"]
                is_tech = False
        else:
            topics = extracted_topics
            is_tech = True
        
        supported_industry = enriched.get("supported_industry")
        
        # Convert industry to list format
        if supported_industry:
            industries = [supported_industry] if isinstance(supported_industry, str) else supported_industry
        else:
            industries = []
        

        enriched.update({
            "topic": topics,
            "supported_industry": industries,
            "is_tech_related": is_tech,
            "author": enriched.get("author", ""),  # Set by scraper
            "influencer_title": enriched.get("influencer_title", ""),
            "followers_count": enriched.get("followers_count", ""),
        })
        
        return enriched

    def _classify_tech_non_tech_zero_shot(self, content: str) -> Optional[str]:
        """
        Return "technical" or "non-technical" based on zero-shot classifier.
        Falls back to None when classifier is unavailable.
        """
        if not content:
            return None

        if self._zero_shot_import_failed:
            return None

        try:
            from post_writer.post_classification import classify_text
        except Exception as e:
            self._zero_shot_import_failed = True
            logger.warning(f"Zero-shot classifier unavailable, falling back to rules: {e}")
            return None

        try:
            labels = classify_text(content)
        except Exception as e:
            logger.warning(f"Zero-shot classification failed, falling back to rules: {e}")
            return None

        if any(str(label).strip().lower() == "non-technical" for label in labels):
            return "non-technical"
        return "technical"

    
    def _extract_topics(self, content: str) -> List[str]:
        if not content:
            return []

        text = content.lower()
        matched_topics = []

        for topic, patterns in self.TOPIC_RULES.items():
            if any(re.search(pattern, text) for pattern in patterns):
                matched_topics.append(topic)

        if not matched_topics:
            ai_keywords = [
                r"\bai\b",
                r"\b(artificial intelligence)\b",
            ]
            if any(re.search(pattern, text) for pattern in ai_keywords):
                matched_topics.append("Generative AI")

        return matched_topics
    
    def _extract_supported_industries(self, topics: List[str]) -> List[str]:
        return sorted(
            {
                self.INDUSTRY_MAP.get(topic, "Other")
                for topic in topics
            }
        )

class LinkedInPostScraper(IWebScraper):
    """
    Scrapes the latest posts for each user in a LinkedIn relationship graph.
    """
    RETRY_SLEEP = 5 * 60     
    MAX_RETRIES = 1
    HUMAN_DELAY_MIN = 15      
    HUMAN_DELAY_MAX = 25
    
    def __init__(
        self,
        relations: RelationshipModel,
        parser: Optional[LinkedInParser] = None,
        formatter: Optional[LinkedInPostFormatter] = None,
    ) -> None:
        self.relations = relations
        if parser is None:
            profile_paths = [
                os.path.join(Config.PROJECT_ROOT, "google-chrome", "Profile_LinkedIn"),
                os.path.join(Config.PROJECT_ROOT, "google-chrome", "Profile_Linkedin"),
                os.path.join(Config.PROJECT_ROOT, "src", "google-chrome", "Profile_LinkedIn"),
                os.path.join(Config.PROJECT_ROOT, "src", "google-chrome", "Profile_Linkedin"),
                "./google-chrome/Profile_LinkedIn",
                "./google-chrome/Profile_Linkedin",
            ]
            profile_exists = any(os.path.exists(path) for path in profile_paths)
            
            if profile_exists:
                logger.info("Chrome profile found - using local Chrome to leverage profile for automatic login (avoids CAPTCHA)")
                parser = LinkedInParser(run_in_local=True)
            else:
                # No profile found - check if Selenium Grid is available
                selenium_available = wait_for_selenium(timeout=5, required=False)
                
                if selenium_available:
                    logger.info("No Chrome profile found - using Remote WebDriver with cookies")
                    parser = LinkedInParser(run_in_local=False)
                else:
                    logger.warning("No Chrome profile found and Selenium Grid not available - will attempt to use Remote WebDriver")
                    parser = LinkedInParser(run_in_local=False, require_selenium=False)
        else:
            parser = parser
        formatter = formatter or LinkedInPostFormatter()

        super().__init__(parser, formatter)

        self.influencer_metadata = self._load_influencer_metadata()
        self._influencer_info_path = Path(Config.PROJECT_ROOT) / "data" / "influencer_metadata" / "linkedin_influencer_metadata.json"
        
        self.profile_extractor = getattr(self.parser, "profile_extractor", None)

    def _load_influencer_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Load influencer metadata (title, followers_count, etc.) from
        data/influencer_metadata/linkedin_influencer_metadata.json and index it by slug.
        """
        metadata: Dict[str, Dict[str, Any]] = {}
        try:
            base = Path(Config.PROJECT_ROOT)
            info_path = base / "data" / "influencer_metadata" / "linkedin_influencer_metadata.json"
            if not info_path.exists():
                logger.warning(
                    f"linkedin_influencer_metadata.json not found at {info_path} - "
                    "influencer_title and followers_count will be empty in Parquet"
                )
                return metadata

            with info_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)

            if isinstance(raw, dict) and "influencers" in raw:
                entries = raw["influencers"]
            elif isinstance(raw, list):
                entries = raw
            else:
                entries = []

            for entry in entries:
                data = entry.get("data", entry)
                profile_url = data.get("profile_url")
                if not profile_url:
                    continue

                slug = extract_slug_from_linkedin_url(profile_url)
                if not slug:
                    continue

                metadata[slug] = {
                    "influencer_name": data.get("name") or data.get("influencer_name") or "",
                    "influencer_title": data.get("title") or "",
                    "followers_count": data.get("followers_count") or "",
                }
        except Exception as e:
            logger.warning(f"Failed to load influencer metadata: {e}")

        return metadata
    
    def _save_influencer_metadata(self) -> None:
        """
        Persist the current influencer_metadata mapping to data/influencer_metadata/linkedin_influencer_metadata.json.
        This keeps the metadata file in sync with the latest scraped profile info.
        
        Delegates to LinkedInProfileExtractor to maintain separation of concerns.
        """
        extractor = self.profile_extractor
        if extractor is None:
            extractor = getattr(self.parser, "profile_extractor", None)

        if extractor is None and getattr(self.parser, "driver", None) is not None:
            extractor = LinkedInProfileExtractor(self.parser.driver)

        if extractor is None:
            logger.warning("Profile extractor not initialized - cannot save influencer metadata")
            return

        self.profile_extractor = extractor
        extractor.save_influencer_metadata(self.influencer_metadata)
    
    def _ensure_influencer_metadata(self, username: str) -> Dict[str, Any]:
        """
        Ensure we have influencer-level metadata (title, followers_count)
        for the given username. If it's missing or blank in the cached
        metadata, we proactively visit the user's profile using the
        LinkedInParser to extract fresh information before scraping posts.
        """
        meta = self.influencer_metadata.get(username, {})
        name = (meta.get("influencer_name") or "").strip()
        title = (meta.get("influencer_title") or "").strip()
        followers = (meta.get("followers_count") or "").strip()

        def _is_bad_title(t: str) -> bool:
            if not t:
                return True
            low = t.strip().lower()
            low = re.sub(r"^[·•]\s*", "", low).strip()
            if low in {"1st", "2nd", "3rd", "1st+", "2nd+", "3rd+"}:
                return True
            if re.fullmatch(r"\d+(st|nd|rd)\+?", low):
                return True
            if re.match(r"^[·•]\s*\d+(st|nd|rd)", t.strip(), re.IGNORECASE):
                return True
            ui_elements = {
                "show details", "see more", "see less", "contact info", "more", "less",
                "show", "details", "view", "open", "close"
            }
            if low in ui_elements:
                return True
            if low.startswith("show ") or low.startswith("see ") or low.startswith("view "):
                return True
            if len(low) <= 15 and not any(indicator in low for indicator in ['|', '@', 'engineer', 'developer', 'manager', 'director', 'lead', 'ai', 'ml', 'data', 'scientist']):
                if low in {"details", "more", "less", "show", "view", "open", "close"}:
                    return True
            return False

        if name and title and followers and not _is_bad_title(title):
            logger.info(
                "Using cached influencer metadata for %s: name='%s', title='%s', followers='%s'",
                username,
                name,
                title,
                followers,
            )
            return meta
        
        if _is_bad_title(title):
            logger.info(
                "Cached title '%s' for %s is invalid (connection degree), will re-extract",
                title,
                username,
            )
            title = ""

        profile_url = f"https://www.linkedin.com/in/{username}/"
        logger.info(
            "Fetching influencer metadata from profile before scraping posts: %s "
            "(cached: name='%s', title='%s', followers='%s')",
            profile_url,
            name,
            title,
            followers,
        )

        try:
            info = self.parser.extract_influencer_info(profile_url)
            name = (info.get("name") or name or "").strip()
            title = (info.get("title") or title or "").strip()
            followers = (info.get("followers_count") or followers or "").strip()
        except Exception as e:
            logger.warning(f"Failed to extract influencer info for {username}: {e}")

        meta = {
            "influencer_name": name,
            "influencer_title": title,
            "followers_count": followers,
        }
        self.influencer_metadata[username] = meta
        self._save_influencer_metadata()
        return meta
    
    def __enter__(self):
        self.parser = self.parser.__enter__()
        self.profile_extractor = getattr(self.parser, "profile_extractor", None)
        if self.profile_extractor is None:
            self.profile_extractor = LinkedInProfileExtractor(self.parser.driver)
        return self

    def __exit__(self, exc_type, exc, tb):
        return self.parser.__exit__(exc_type, exc, tb)
    
    def scrape(self, limit=3, influencer_priority_list: Optional[List[str]] = None, no_upload: bool = False) -> None:
        """
        Login once and scrape posts for all known users.

        Args:
            limit: Number of posts to scrape per user.
            influencer_priority_list: Optional ordered list of influencer slugs.
            no_upload: If True, keep scraped data locally and skip Azure Data Lake upload.
        """
        email = getattr(Config, 'LINKEDIN_EMAIL', Config.LINKEDIN_EMAIL)
        password = getattr(Config, 'LINKEDIN_PASSWORD', Config.LINKEDIN_PASSWORD)
        self.parser.login(email, password)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"linkedin_scraping_data_{timestamp}.parquet"

        # Get list of users to scrape
        users_to_scrape = list(self.relations.to_dict().keys())
        
        if influencer_priority_list:
            priority_set = set(influencer_priority_list)
            priority_users = [u for u in influencer_priority_list if u in users_to_scrape]
            remaining_users = [u for u in users_to_scrape if u not in priority_set]
            users_to_scrape = priority_users + remaining_users

        logger.info("=" * 50)
        logger.info("Phase 1/2: Prefetching influencer metadata before post scraping")
        logger.info("=" * 50)
        for idx, username in enumerate(users_to_scrape, 1):
            logger.info("Prefetching metadata %s/%s for %s", idx, len(users_to_scrape), username)
            try:
                self._ensure_influencer_metadata(username)
            except Exception as e:
                logger.warning(f"Failed to prefetch metadata for {username}: {e}")

        logger.info("=" * 50)
        logger.info("Phase 2/2: Scraping posts with prefetched metadata")
        logger.info("=" * 50)

        for username in users_to_scrape:
            retries = 0

            while retries <= self.MAX_RETRIES:
                logger.info(f"+---- Scraping posts for user {username} ----")
                try:
                    meta = self._ensure_influencer_metadata(username)
                    posts = self.parser.scrape_post(username, limit)
                    
                    for post in posts:
                        post["author"] = username
                        post["influencer_name"] = meta.get("influencer_name", "")
                        post["influencer_title"] = meta.get("influencer_title", "")
                        post["followers_count"] = meta.get("followers_count", "")
                        
                        if "tagged_profiles" in post and isinstance(post["tagged_profiles"], list):
                            author_profile_url = f"https://www.linkedin.com/in/{username}/"
                            post["tagged_profiles"] = [
                                profile for profile in post["tagged_profiles"]
                                if profile != author_profile_url
                            ]
                    
                    formatted_posts = [self.formatter.entry_format(post) for post in posts]

                    for formatted in formatted_posts:
                        dump_to_parquet(formatted, Config.LINKEDIN_DATA_DIR, file_name)

                    print(f"Parquet dump successfully for user {username}")
                    sleep_time = random.uniform(
                        self.HUMAN_DELAY_MIN,
                        self.HUMAN_DELAY_MAX
                    )
                    logger.info(f"Sleeping {sleep_time:.1f}s (human delay)")
                    time.sleep(sleep_time)
                    break
                except ExtractLinkedInPostException as err:
                    logger.error(f"[ERROR] : {err}")
                    break

                except Exception as err:
                    retries += 1
                    logger.warning(f"[WARNING] : {err}")
                    if retries <= self.MAX_RETRIES:
                        logger.warning(
                            f"Retrying after {self.RETRY_SLEEP // 60} minutes..."
                        )
                        time.sleep(self.RETRY_SLEEP)
                        self._reset_parser()
                    else:
                        logger.error(
                            "Max retries reached — backing off to avoid rate limit"
                        )
        
        # Check if file exists before attempting upload
        full_path = os.path.join(Config.LINKEDIN_DATA_DIR, file_name)
        upload_successful = False

        if not os.path.isfile(full_path):
            logger.error(f"Parquet file not found: {full_path}")
            logger.error("No data was scraped or saved to disk")
            return

        file_size = os.path.getsize(full_path)
        logger.info(f"Found Parquet file: {full_path} ({file_size} bytes)")

        if no_upload:
            logger.info("=" * 50)
            logger.info("--no-upload flag set. Skipping Azure Data Lake upload.")
            logger.info(f"Scraped data saved locally at: {full_path}")
            logger.info("=" * 50)
            return

        logger.info("=" * 50)
        logger.info("Scraping complete. Uploading data to Azure Data Lake Storage...")
        logger.info("=" * 50)

        # Check if storage credentials are configured
        if not Config.STORAGE_ACCOUNT_KEY:
            logger.error("STORAGE_ACCOUNT_KEY not set - cannot upload to Azure Data Lake Storage")
            logger.warning("Keeping local file since upload was skipped")
        elif not Config.FILE_SYSTEM_NAME:
            logger.error("FILE_SYSTEM_NAME not set - cannot upload to Azure Data Lake Storage")
            logger.warning("Keeping local file since upload was skipped")
        else:
            try:
                upload_parquet_to_dls(Config.LINKEDIN_DATA_DIR, file_name, data_source="linkedin")
                logger.info("Upload completed successfully")
                upload_successful = True
            except Exception as e:
                logger.error(f"Failed to upload to Azure Data Lake Storage: {e}", exc_info=True)
                logger.warning("Keeping local file since upload failed")

        if upload_successful:
            try:
                clean_file(Config.LINKEDIN_DATA_DIR, file_name)
                logger.info("Local file cleaned up")
            except Exception as e:
                logger.warning(f"Failed to clean up local file: {e}")
        else:
            logger.info(f"Local file preserved: {full_path}")

    def _reset_parser(self):
        try:
            if self.parser:
                self.parser.__exit__(None, None, None)
        except Exception:
            pass

        logger.warning("Reinitializing LinkedInParser (new session)")
        self.parser = LinkedInParser()
        self.parser.__enter__()
        email = getattr(Config, 'LINKEDIN_EMAIL', Config.EMAIL)
        password = getattr(Config, 'LINKEDIN_PASSWORD', Config.PASSWORD)
        self.parser.login(email, password)


class LinkedInConnectionsScraper:
    """
    Scrapes connections and followers for LinkedIn influencers.
    """
    
    def __init__(self, parser=None):
        self.parser = parser or LinkedInParser()
    
    def __enter__(self):
        self.parser = self.parser.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.parser.__exit__(exc_type, exc_val, exc_tb)
    
    def scrape_influencer_info_and_connections(
        self,
        profile_url: str,
        scrape_connections: bool = True,
        scrape_followers: bool = False,
        page_threshold: int = 3
    ) -> Dict[str, Any]:
        """
        Scrape influencer info, connections, and/or followers.
        
        Args:
            profile_url: LinkedIn profile URL
            scrape_connections: Whether to scrape connections
            scrape_followers: Whether to scrape followers
            page_threshold: Maximum pages per degree
            
        Returns:
            Dictionary with influencer info, connections, and followers
        """
        # Extract influencer info first
        influencer_info = self.parser.extract_influencer_info(profile_url)
        
        encrypted_id = influencer_info.get("encrypted_member_id")
        influencer_name = influencer_info.get("name", "Unknown")
        
        if not encrypted_id:
            logger.warning(f"Could not extract member ID for {profile_url} - skipping connections/followers")
            return {
                "influencer_info": influencer_info,
                "connections": [],
                "followers": []
            }
        
        connections = []
        followers = []
        
        if scrape_connections:
            logger.info(f"Scraping connections for {influencer_name}...")
            connections = self.parser.scrape_connections_or_followers(
                profile_url,
                encrypted_id,
                influencer_name,
                page_threshold=page_threshold,
                is_connections=True
            )
        
        if scrape_followers:
            logger.info(f"Scraping followers for {influencer_name}...")
            followers = self.parser.scrape_connections_or_followers(
                profile_url,
                encrypted_id,
                influencer_name,
                page_threshold=page_threshold,
                is_connections=False
            )
        
        return {
            "influencer_info": influencer_info,
            "connections": connections,
            "followers": followers
        }
    
    def save_to_json(
        self,
        results: List[Dict[str, Any]],
        output_file: str,
        is_connections: bool = True
    ) -> None:
        """
        Save connections or followers to JSON file.
        
        Args:
            results: List of results from scrape_influencer_info_and_connections
            output_file: Output JSON file path
            is_connections: True for connections, False for followers
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing data if file exists
        if output_path.exists():
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                existing_data = {"last_updated": None, "total_influencers": 0, "influencers": []}
        else:
            existing_data = {"last_updated": None, "total_influencers": 0, "influencers": []}
        
        # Process each result
        for result in results:
            influencer_info = result.get("influencer_info", {})
            profile_url = influencer_info.get("profile_url", "")
            influencer_name = influencer_info.get("name", "Unknown")
            
            # Find if this influencer already exists
            influencer_entry = None
            for entry in existing_data.get("influencers", []):
                if entry.get("influencer_url") == profile_url:
                    influencer_entry = entry
                    break
            
            # Create or update influencer entry
            if is_connections:
                connections = result.get("connections", [])
                influencer_data = {
                    "influencer": influencer_name,
                    "influencer_url": profile_url,
                    "scraped_at": datetime.utcnow().isoformat(),
                    "total_connections": len(connections),
                    "connections": connections
                }
            else:
                followers = result.get("followers", [])
                influencer_data = {
                    "influencer": influencer_name,
                    "influencer_url": profile_url,
                    "scraped_at": datetime.utcnow().isoformat(),
                    "total_followers": len(followers),
                    "followers": followers
                }
            
            if influencer_entry:
                influencer_entry.update(influencer_data)
            else:
                existing_data.setdefault("influencers", []).append(influencer_data)
        
        existing_data["last_updated"] = datetime.utcnow().isoformat()
        existing_data["total_influencers"] = len(existing_data["influencers"])
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        data_type = "connections" if is_connections else "followers"
        logger.info(f"Saved {data_type} data to {output_file}")


def remove_whitespace(text: str) -> str:
    """Remove all whitespace from text."""
    if text is None:
        return ""
    return re.sub(r"\s+", "", str(text))


def normalize_topic_list(topics) -> list[str]:
    """
    Normalize topic names to hashtag-friendly abbreviations for LinkedIn.
    
    Args:
        topics: List of topic strings, single topic string, or None
        
    Returns:
        List of normalized hashtag strings
    """
    if topics is None:
        return []

    TOPIC_TO_HASHTAG = {
        "Natural Language Processing (NLP)": "NLP",
        "Machine Learning (ML)": "ML",
        "Computer Vision (CV)": "CV",
        "Generative AI": "GenAI", 
        "Data Analytics": "DataAnalytics",
        "Orchestration": "Orchestration",
        "Robotics": "Robotics",
        "technical": "KnowledgeSharing",
    }
    
    # Handle single string input
    if isinstance(topics, str):
        topics = [topics]
    
    normalized = []
    for item in topics:
        if not item:
            continue
        
        if item in TOPIC_TO_HASHTAG:
            normalized.append(TOPIC_TO_HASHTAG[item])
        else:
            match = re.search(r'\(([A-Z]+)\)', item)
            if match:
                normalized.append(match.group(1))
            else:
                tag = remove_whitespace(item)
                normalized.append(tag)

    return normalized


def render_hashtags_from_topic(topic, max_tags=4) -> str:
    """
    Render LinkedIn hashtags from topic list.
    
    LinkedIn rich-text editor expects consecutive spans without spaces
    and the class attribute in the form class=ql-hashtag, e.g.:
    <p><span class=ql-hashtag>#MachineLearning</span><span class=ql-hashtag>#meme</span></p>
    
    Args:
        topic: List of topic strings, single topic string, or None
        max_tags: Maximum number of hashtags to render (default: 4)
        
    Returns:
        HTML string with hashtags, or empty string if no tags found
    """
    tags = normalize_topic_list(topic)
    
    tags = list(dict.fromkeys(tags))[:max_tags]
    
    if not tags:
        return ""

    spans = "".join(
        f"<span class=ql-hashtag>#{tag}</span>"
        for tag in tags
    )

    return f"<p>{spans}</p>\n"

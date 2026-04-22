import time
import random
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup


from common.utils import setup_logging


setup_logging()
logger = logging.getLogger(__name__)

class ExtractLinkedInPostException(Exception):
    """Exception raised when LinkedIn post extraction fails"""
    pass

# Post classification constants (from provided script)
TECH_KEYWORDS_STRONG = {
    "kubernetes", "docker", "microservice", "api", "backend", "frontend",
    "graphql", "rest api", "fastapi", "django", "flask",
    "aws", "azure", "gcp", "cloudformation", "terraform",
    "devops", "cicd", "pipeline", "k8s",
    "neural", "nlp", "computer vision", "cv", "llm", "foundation model",
    "transformer", "bert", "gpt", "embedding", "vector db",
    "rpa", "automation", "orchestration",
    "blockchain", "smart contract", "web3",
    "cybersecurity", "security", "encryption", "zero trust",
    "database", "sql", "nosql", "postgres", "mysql", "mongodb", "redis",
    "spark", "hadoop", "kafka", "streaming",
    "system design", "architecture"
}

TECH_KEYWORDS_WEAK = {
    "ai", "machine learning", "ml", "deep learning", "data", "big data",
    "analytics", "cloud", "software", "engineer", "developer",
    "coding", "code", "technical", "tech", "automation"
}

INDUSTRY_KEYWORDS = {
    "Technology": ["software", "saas", "it", "cloud", "platform", "api", "devops", "kubernetes", "docker"],
    "AI/ML": ["ai", "machine learning", "ml", "deep learning", "llm", "gpt", "nlp", "computer vision", "cv"],
    "Data/Analytics": ["data", "analytics", "bi", "big data", "data lake", "warehouse", "etl", "sql"],
    "Cybersecurity": ["security", "cyber", "encryption", "zero trust", "pentest", "ransomware"],
    "FinTech": ["fintech", "banking", "payments", "crypto", "blockchain", "defi"],
    "Healthcare": ["healthcare", "medtech", "clinical", "hospital", "patient", "diagnostic"],
    "E-commerce": ["ecommerce", "retail", "marketplace", "shop", "checkout"],
    "Manufacturing/Industry 4.0": ["manufacturing", "industry 4.0", "iot", "factory", "supply chain", "logistics"],
    "Marketing/Advertising": ["marketing", "ads", "campaign", "seo", "sem", "branding"],
    "HR/Recruiting": ["hr", "talent", "recruiting", "hiring", "people"],
}

NON_TECHNICAL_PATTERNS = [
    r"\[.*sharing\s+session.*recap.*\]", 
    r"\[.*session\s+recap.*\]",  
    r"\[.*recap.*\]",  
    r"i['']?m\s+happy\s+to\s+share",  
    r"i\s+am\s+happy\s+to\s+share",  
    r"happy\s+to\s+share\s+that\s+i['']?ve", 
    r"sharing\s+session",
    r"session\s+recap",
    r"thank\s+you\s+for",
    r"thank\s+.*\s+for",
    r"grateful\s+to",
    r"excited\s+to\s+share",
    r"proud\s+to\s+announce",
    r"delighted\s+to",
    r"honored\s+to",
    r"pleased\s+to",
    r"event\s+recap",
    r"recap\s+of",
    r"thank\s+.*\s+organiz",
    r"thank\s+.*\s+team",
    r"thank\s+.*\s+speaker",
    r"thank\s+.*\s+partner",
    r"thank\s+.*\s+organizer",
    r"thank\s+.*\s+organizers",
    r"xin\s+trân\s+trọng\s+cảm\s+ơn", 
    r"vinh\s+dự", 
    r"gửi\s+lời\s+cảm\s+ơn",
    r"obtained\s+(a\s+)?new\s+certification",
    r"earned\s+(a\s+)?new\s+certification",
    r"received\s+(a\s+)?new\s+certification",
    r"got\s+(a\s+)?new\s+certification",
    r"completed\s+(a\s+)?certification",
    r"certification\s+(from|by|in)",
    r"happy\s+to\s+share.*certification",
    r"excited\s+to\s+share.*certification",
    r"proud\s+to\s+share.*certification",
    r"there'?s\s+a\s+(bookstore|shop|store|cafe|restaurant|place)",
    r"bookstore\s+(dedicated\s+to|for|with)",
    r"dedicated\s+to\s+(technical\s+)?books",
    r"omg\s+there'?s",
    r"wow\s+there'?s",
    r"check\s+out\s+this\s+(bookstore|shop|store|cafe|restaurant|place)",
    r"found\s+(a|this)\s+(bookstore|shop|store|cafe|restaurant|place)",
]

# Keywords that strongly indicate non-technical content
NON_TECHNICAL_KEYWORDS = {
    "thank you", "thanks", "grateful", "appreciation", "appreciate",
    "congratulations", "congrats", "celebrate", "celebration",
    "announcement", "announcing", "excited to", "proud to", "honored",
    "delighted", "pleased", "happy to share", "sharing session",
    "session recap", "event recap", "recap", "workshop recap",
    "conference recap", "meetup recap", "webinar recap",
    "invitation", "invite", "join us", "save the date",
    "looking forward", "see you", "hope to see",
    "there's a", "check out this", "found this",
    "omg", "wow", "dedicated to", "cafe", "restaurant", "shop", "store"
}


class LinkedInPostExtractor:
    """Extracts LinkedIn posts from web pages"""
    
    def __init__(self, driver):
        self.driver = driver
        self.seen_posts = set()
    
    def extract(self, activity_url: str, max_scrolls: int = 5, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Extract posts from a LinkedIn activity page.
        
        Args:
            activity_url: URL of the LinkedIn activity page
            max_scrolls: Maximum number of scrolls to perform
            limit: Maximum number of posts to return (default: 3)
            
        Returns:
            List of post dictionaries
        """
        try:
            logger.info(f"Extracting posts from {activity_url}")
            
            all_posts = []
            seen_urls = set()
            scroll = 0
            
            while scroll < max_scrolls:
                posts = self._extract_posts_from_activity()
                new = 0
                
                for p in posts:
                    if p.get("post_url") not in seen_urls:
                        seen_urls.add(p["post_url"])
                        all_posts.append(p)
                        new += 1
                
                logger.info(f"Scroll {scroll+1} → +{new} new posts | Total: {len(all_posts)}")
                
                if new == 0:
                    logger.info("No new posts → reached end")
                    break
                
                if len(all_posts) >= limit:
                    break
                
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(4, 7))
                scroll += 1
            
            # Calculate engagement scores and sort
            for post in all_posts:
                engagement_score = (
                    post.get("reactions", 0) + 
                    post.get("comments", 0) + 
                    post.get("reposts", 0)
                )
                post["engagement_score"] = engagement_score
            
            # Sort by engagement and take top N
            all_posts.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
            top_posts = all_posts[:limit]
            
            logger.info(f"Extracted {len(top_posts)} posts (top {limit} by engagement)")
            return top_posts
            
        except Exception as e:
            logger.error(f"Error extracting posts: {e}")
            raise ExtractLinkedInPostException(f"Extraction process error: {e}")
    
    def _extract_posts_from_activity(self) -> List[Dict[str, Any]]:
        """Extract posts from current page"""
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        posts = []
        
        # Find cards by activity urn
        cards = soup.find_all(attrs={"data-urn": re.compile(r"urn:li:activity:\d+")})
        logger.debug(f"Found {len(cards)} post containers")
        
        for card in cards:
            post = {}
            
            # Extract activity ID & URL
            data_urn = card.get("data-urn")
            activity_id = None
            if data_urn and "urn:li:activity:" in data_urn:
                activity_id = data_urn.split(":")[-1]
            
            if not activity_id:
                link_act = card.find("a", href=re.compile(r"activity-\d+"))
                if link_act:
                    m = re.search(r"activity-(\d+)", link_act["href"])
                    if m:
                        activity_id = m.group(1)
            
            if not activity_id:
                continue
            
            post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"
            post["post_url"] = post_url
            post["activity_id"] = activity_id
            
            # Extract post text
            text_div = card.find("div", class_=lambda x: x and "update-components-text" in str(x))
            if text_div:
                span_ltr = text_div.find("span", dir="ltr")
                if span_ltr:
                    for sm in span_ltr.find_all("span", class_=re.compile(r"see-more", re.I)):
                        sm.decompose()
                    text_raw = span_ltr.get_text(separator=" ", strip=True)
                else:
                    text_raw = text_div.get_text(separator=" ", strip=True)
                post["text"] = re.sub(r"\s+", " ", text_raw).strip()
            else:
                post["text"] = None
            
            if not post.get("text") or len(post["text"]) < 8:
                continue
            
            # Classify post
            topic, supported_industry, should_skip = self._classify_post(post.get("text", ""))
            
            if should_skip:
                logger.debug(f"Skipping non-technical post: {activity_id}")
                continue
            
            post["topic"] = topic
            post["supported_industry"] = supported_industry
            
            # Extract keywords using rule-based regex (prioritizes strong technical keywords)
            keyword = self._extract_keywords_with_regex(post.get("text", ""))
            post["keywords"] = keyword if keyword else ""
            
            # Extract engagement stats
            def parse_count(elem):
                if not elem:
                    return 0
                txt = elem.get_text(strip=True)
                m = re.search(r"([\d.,]+[KMB]?)", txt)
                if not m:
                    return 0
                val = m.group(1)
                if val.endswith("K"):
                    return int(float(val[:-1]) * 1000)
                if val.endswith("M"):
                    return int(float(val[:-1]) * 1_000_000)
                return int(re.sub(r"[^\d]", "", val))
            
            reactions_elem = card.find("span", class_=re.compile(r"social-details-social-counts__reactions-count"))
            comments_elem = (
                card.find("button", attrs={"aria-label": re.compile(r"comments?", re.I)}) or
                card.find("span", class_=re.compile(r"social-details-social-counts__count-value-hover"))
            )
            reposts_elem = (
                card.find("button", attrs={"aria-label": re.compile(r"repost", re.I)}) or
                card.find("span", class_=re.compile(r"social-details-social-counts__item--truncate-text"))
            )
            
            post["reactions"] = parse_count(reactions_elem)
            post["comments"] = parse_count(comments_elem)
            post["reposts"] = parse_count(reposts_elem)
            
            # Extract tagged profiles from HTML structure (
            post["tagged_profiles"] = self._extract_tagged_profiles_from_html(card)
            
            # Also extract from text (in case URLs are written out in text)
            post_text = post.get("text", "")
            text_profiles = self._extract_tagged_profiles(post_text)
            
            # Merge both sources and deduplicate
            all_profiles = list(set(post["tagged_profiles"] + text_profiles))
            post["tagged_profiles"] = all_profiles
            
            # Extract repost information from HTML structure first, then fall back to text
            is_repost, original_author = self._detect_repost_from_html(card, post_text)
            post["is_repost"] = is_repost
            post["original_author"] = original_author
            
            # Extract media using improved logic
            post["media_url"] = self._extract_media_image_url(card)
            
            # Extract timestamp
            time_tag = (
                card.find("span", class_=re.compile(r"update-components-actor__sub-description")) or
                card.find("a", class_=re.compile(r"update-components-actor__sub-description"))
            )
            time_raw = time_tag.get_text(" ", strip=True) if time_tag else None
            if time_raw:
                m = re.search(r"(\d+\s*(?:s|m|h|d|w|mo|yr|y))", time_raw.lower())
                post["time_ago"] = m.group(1) if m else time_raw
            else:
                post["time_ago"] = None
            
            post["scraped_at"] = datetime.utcnow().isoformat()
            
            posts.append(post)
        
        return posts
    
    def _extract_media_image_url(self, card) -> Optional[str]:
        """
        Extract media image URL from a LinkedIn post card.
        Only extracts images from elements with class "update-components-image__image-link"
        to avoid capturing profile avatars or other non-post images.
        
        Args:
            card: BeautifulSoup element representing a post card
            
        Returns:
            str: Image URL if found, None otherwise
        """
        image_link = (
            card.find("button", class_=lambda x: x and "update-components-image__image-link" in str(x)) or
            card.find("a", class_=lambda x: x and "update-components-image__image-link" in str(x))
        )
        
        if not image_link:
            return None
        
        # Find img tag inside the button/link
        img = image_link.find("img")
        if not img:
            return None
        
        src = img.get("src")
        if not src:
            return None
        
        # Filter out placeholder/loading images
        if "placeholder" in src.lower() or "loading" in src.lower():
            return None
        
        return src
    
    def _normalize_text_for_classification(self, text: str) -> str:
        """
        Normalize text before applying classification patterns.
        
        Args:
            text: Raw text to normalize
        
        Returns:
            Normalized text string
        """
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove URLs
        normalized = re.sub(r"https?://\S+|www\.\S+", " ", normalized)
        
        # Remove hashtags (replace with space to maintain word boundaries)
        normalized = re.sub(r"#\w+", " ", normalized)
        
        # Normalize quotes and apostrophes 
        normalized = normalized.replace("'", "'").replace("'", "'")
        normalized = normalized.replace('"', '"').replace('"', '"')
        normalized = normalized.replace("'", "'").replace("'", "'")
        
        # Normalize whitespace: multiple spaces/tabs/newlines to single space
        normalized = re.sub(r"\s+", " ", normalized)
        
        # Remove leading/trailing whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def _classify_post(self, text: str) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Classify a post into topic and supported industry.
        Returns (topic, supported_industry, should_skip)
        """
        if not text:
            return None, None, False
        
        text_lower = self._normalize_text_for_classification(text)
        
        # Check for non-technical patterns first
        for pattern in NON_TECHNICAL_PATTERNS:
            if re.search(pattern, text_lower):
                best_industry = None
                best_count = 0
                for industry, keywords in INDUSTRY_KEYWORDS.items():
                    count = sum(1 for kw in keywords if kw in text_lower)
                    if count > best_count:
                        best_count = count
                        best_industry = industry
                return "non-technical", best_industry if best_count > 0 else None, True
        

        non_tech_context_patterns = [
            r"technical\s+(books?|bookstore|shop|store|cafe|restaurant|place|location|venue)",
            r"(bookstore|shop|store|cafe|restaurant|place)\s+(for|with|dedicated\s+to)\s+technical",
            r"omg\s+.*technical",
            r"wow\s+.*technical",
            r"there'?s\s+.*technical\s+(books?|bookstore|shop|store)",
        ]
        for pattern in non_tech_context_patterns:
            if re.search(pattern, text_lower):
                best_industry = None
                best_count = 0
                for industry, keywords in INDUSTRY_KEYWORDS.items():
                    count = sum(1 for kw in keywords if kw in text_lower)
                    if count > best_count:
                        best_count = count
                        best_industry = industry
                return "non-technical", best_industry if best_count > 0 else None, True
        
        # Check for non-technical keywords
        non_tech_keyword_score = sum(1 for kw in NON_TECHNICAL_KEYWORDS if kw in text_lower)
        if non_tech_keyword_score >= 2:
            best_industry = None
            best_count = 0
            for industry, keywords in INDUSTRY_KEYWORDS.items():
                count = sum(1 for kw in keywords if kw in text_lower)
                if count > best_count:
                    best_count = count
                    best_industry = industry
            return "non-technical", best_industry if best_count > 0 else None, False
        
        # Count technical keywords
        strong_hits = sum(1 for kw in TECH_KEYWORDS_STRONG if kw in text_lower)
        weak_hits = sum(1 for kw in TECH_KEYWORDS_WEAK if kw in text_lower)
        technical_score = (strong_hits * 3) + weak_hits
        
        is_technical = technical_score > 0 and (strong_hits >= 1 or weak_hits >= 3)
        topic = "technical" if is_technical else "non-technical"
        
        # Detect industry
        best_industry = None
        best_count = 0
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > best_count:
                best_count = count
                best_industry = industry
        
        return topic, best_industry if best_count > 0 else None, False
    
    def _extract_keywords_with_regex(self, text: str) -> str:
        """
        Extract a single main technical keyword from text using regex patterns.
        Prioritizes strong technical keywords over weak ones.
        
        Args:
            text: The text to extract keyword from
        
        Returns:
            Single keyword string (empty string if no keyword found)
        """
        if not text:
            return ""
        
        try:
            # Normalize text: lowercase, remove URLs, hashtags, normalize whitespace
            text_normalized = self._normalize_text_for_classification(text)
            
            if len(text_normalized) < 10:  # Too short for meaningful extraction
                return ""
            
            all_keywords = []
            
            # Add strong technical keywords first (highest priority)
            for kw in TECH_KEYWORDS_STRONG:
                all_keywords.append((kw, "strong"))
            
            # Add weak technical keywords (lower priority)
            for kw in TECH_KEYWORDS_WEAK:
                all_keywords.append((kw, "weak"))
            
            # Sort by length (longest first) to match multi-word phrases first
            def sort_key(item):
                keyword, priority = item
                priority_score = 0 if priority == "strong" else 1
                return (-len(keyword.split()), priority_score)
            
            all_keywords.sort(key=sort_key)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_keywords = []
            for kw, priority in all_keywords:
                kw_lower = kw.lower()
                if kw_lower not in seen:
                    seen.add(kw_lower)
                    unique_keywords.append((kw, priority))
            
            # Search for keywords in text using word boundaries
            for keyword, priority in unique_keywords:
                # Escape special regex characters in keyword
                keyword_escaped = re.escape(keyword.lower())
                
                # Use word boundaries for matching
                if " " in keyword:
                    pattern = r'\b' + keyword_escaped + r'\b'
                else:
                    # Single word: strict word boundary match
                    pattern = r'\b' + keyword_escaped + r'\b'
                
                if re.search(pattern, text_normalized):
                    return keyword
            
            return ""
        
        except Exception as e:
            logger.warning(f"Error extracting keyword with regex: {e}")
            return ""
    
    def _extract_tagged_profiles_from_html(self, card) -> List[str]:
        """
        Extract LinkedIn profile mentions/tags from HTML structure.
        Looks for <a> tags with href="/in/username/" pattern.
        
        Args:
            card: BeautifulSoup element representing a post card
            
        Returns:
            List of profile URLs found in the HTML
        """
        profile_urls = []
        seen = set()
        
        # Find all <a> tags with href attributes that match LinkedIn profile pattern
        # Pattern: href="/in/username/" or href="https://www.linkedin.com/in/username/"
        profile_links = card.find_all("a", href=re.compile(r'/in/[a-zA-Z0-9-]+/?'))
        
        for link in profile_links:
            href = link.get("href", "")
            if not href:
                continue
            
            # Extract username from href
            # Handle both relative (/in/username/) and absolute URLs
            match = re.search(r'/in/([a-zA-Z0-9-]+)/?', href)
            if match:
                username = match.group(1)
                if username and username not in seen:
                    seen.add(username)
                    profile_urls.append(f"https://www.linkedin.com/in/{username}/")
        
        return profile_urls
    
    def _extract_tagged_profiles(self, text: str) -> List[str]:
        """
        Extract LinkedIn profile mentions/tags from post text.
        Looks for links to linkedin.com/in/... profiles written in text.
        
        Args:
            text: Post text content
            
        Returns:
            List of profile URLs found in the text
        """
        if not text:
            return []
        
        # Pattern to match LinkedIn profile URLs
        # Matches: https://www.linkedin.com/in/username/ or linkedin.com/in/username
        profile_pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9-]+)/?'
        
        matches = re.findall(profile_pattern, text, re.IGNORECASE)
        
        # Convert to full URLs and deduplicate
        profile_urls = []
        seen = set()
        for username in matches:
            if username and username not in seen:
                seen.add(username)
                profile_urls.append(f"https://www.linkedin.com/in/{username}/")
        
        return profile_urls
    
    def _detect_repost_from_html(self, card, post_text: str = "") -> Tuple[bool, str]:
        """
        Detect if a post is a repost by checking HTML structure first, then text patterns.
        LinkedIn reposts have specific HTML indicators like:
        - Repost attribution elements
        - Multiple actor elements (original author + reposter)
        - Specific classes indicating repost structure
        
        Args:
            card: BeautifulSoup element representing a post card
            post_text: Post text content (for fallback text pattern matching)
            
        Returns:
            Tuple of (is_repost: bool, original_author: str)
        """
        # FIRST: Check HTML structure for repost indicators
        

        actor_sections = card.find_all(
            lambda tag: (
                tag.name in ['div', 'span'] and
                (
                    'update-components-actor' in str(tag.get('class', [])).lower() or
                    'feed-shared-actor' in str(tag.get('class', [])).lower() or
                    'actor' in str(tag.get('class', [])).lower()
                )
            )
        )
        

        card_text_lower = card.get_text().lower()
        has_repost_indicators = (
            len(actor_sections) > 1 or 
            any(indicator in card_text_lower for indicator in ['repost', 'shared', 'via', 'reposted', 'view'])
        )
        
        if has_repost_indicators and len(actor_sections) >= 1:

            for actor in actor_sections:
                profile_link = actor.find("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
                if profile_link:
                    href = profile_link.get("href", "")
                    if href:
                        match = re.search(r'/in/([a-zA-Z0-9-]+)/?', href)
                        if match:
                            username = match.group(1)
                            profile_url = f"https://www.linkedin.com/in/{username}/"
                            return True, profile_url

        repost_indicators = card.find_all(
            lambda tag: (
                tag.name in ['span', 'div', 'a'] and
                (
                    'repost' in str(tag.get('class', [])).lower() or
                    'shared' in str(tag.get('class', [])).lower() or
                    'repost' in str(tag.get('aria-label', '')).lower() or
                    'shared' in str(tag.get('aria-label', '')).lower() or
                    'repost' in tag.get_text().lower() or
                    'shared' in tag.get_text().lower()
                )
            )
        )
        
        if repost_indicators:
            for indicator in repost_indicators:
                parent = indicator.find_parent()
                if parent:
                    # Search for profile links in parent and siblings
                    profile_link = parent.find("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
                    if not profile_link:
                        # Try in the repost indicator itself
                        profile_link = indicator.find("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
                    
                    if profile_link:
                        href = profile_link.get("href", "")
                        if href:
                            match = re.search(r'/in/([a-zA-Z0-9-]+)/?', href)
                            if match:
                                username = match.group(1)
                                profile_url = f"https://www.linkedin.com/in/{username}/"
                                return True, profile_url
                
                indicator_text = indicator.get_text(strip=True)
                repost_by_match = re.search(
                    r'(?:reposted|shared)\s+by\s+([A-Z][a-zA-Z\s]+)',
                    indicator_text,
                    re.IGNORECASE
                )
                if repost_by_match:
                    name = repost_by_match.group(1).strip()
                    all_links = card.find_all("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
                    for link in all_links:
                        link_text = link.get_text(strip=True).lower()
                        name_lower = name.lower()
                        if name_lower in link_text or any(word in link_text for word in name_lower.split() if len(word) > 2):
                            href = link.get("href", "")
                            if href:
                                match = re.search(r'/in/([a-zA-Z0-9-]+)/?', href)
                                if match:
                                    username = match.group(1)
                                    profile_url = f"https://www.linkedin.com/in/{username}/"
                                    return True, profile_url
        
        actor_elements = card.find_all(
            lambda tag: (
                tag.name in ['div', 'span'] and
                (
                    'actor' in str(tag.get('class', [])).lower() or
                    'update-components-actor' in str(tag.get('class', [])).lower() or
                    'feed-shared-actor' in str(tag.get('class', [])).lower()
                )
            )
        )
        
        if len(actor_elements) > 1:
            for actor in actor_elements[:2]:  
                name_link = actor.find("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
                if name_link:
                    href = name_link.get("href", "")
                    if href:
                        match = re.search(r'/in/([a-zA-Z0-9-]+)/?', href)
                        if match:
                            username = match.group(1)
                            profile_url = f"https://www.linkedin.com/in/{username}/"
                            return True, profile_url
        
        via_elements = card.find_all(
            lambda tag: (
                tag.name in ['span', 'div', 'a'] and
                (
                    'via' in tag.get_text().lower() or
                    'from' in tag.get_text().lower()
                ) and
                len(tag.get_text(strip=True)) < 100  
            )
        )
        
        for via_elem in via_elements:
            profile_link = via_elem.find("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
            if not profile_link:
                parent = via_elem.find_parent()
                if parent:
                    profile_link = parent.find("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
            
            if profile_link:
                href = profile_link.get("href", "")
                if href:
                    match = re.search(r'/in/([a-zA-Z0-9-]+)/?', href)
                    if match:
                        username = match.group(1)
                        profile_url = f"https://www.linkedin.com/in/{username}/"
                        return True, profile_url
            
            via_text = via_elem.get_text()
            via_match = re.search(
                r'(?:via|from)\s+([A-Z][a-zA-Z\s]+)',
                via_text,
                re.IGNORECASE
            )
            if via_match:
                name = via_match.group(1).strip()
                all_links = card.find_all("a", href=re.compile(r'/in/[a-zA-Z0-9-]+'))
                for link in all_links:
                    link_text = link.get_text(strip=True).lower()
                    name_lower = name.lower()
                    if name_lower in link_text or any(word in link_text for word in name_lower.split() if len(word) > 2):
                        href = link.get("href", "")
                        if href:
                            match = re.search(r'/in/([a-zA-Z0-9-]+)/?', href)
                            if match:
                                username = match.group(1)
                                profile_url = f"https://www.linkedin.com/in/{username}/"
                                return True, profile_url
        
        if post_text:
            return self._detect_repost_from_text(post_text)
        
        return False, ""
    
    def _detect_repost_from_text(self, post_text: str) -> Tuple[bool, str]:
        """
        Detect repost from text patterns (fallback method).
        
        Args:
            post_text: Post text content
            
        Returns:
            Tuple of (is_repost: bool, original_author: str)
        """
        if not post_text:
            return False, ""
        
        text_lower = post_text.lower()
        
        # Common repost patterns in text
        repost_patterns = [
            r'reposted\s+by\s+([a-zA-Z\s]+)',
            r'reposting\s+([a-zA-Z\s]+)',
            r'repost\s+from\s+([a-zA-Z\s]+)',
            r'via\s+([a-zA-Z\s]+)',  # Sometimes used for reposts
            r'shared\s+by\s+([a-zA-Z\s]+)',
        ]
        
        for pattern in repost_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                original_author = match.group(1).strip()
                original_author = re.sub(r'\s+(said|wrote|posted|shared).*$', '', original_author, flags=re.IGNORECASE)
                name_parts = original_author.split()
                if len(name_parts) > 3:
                    original_author = ' '.join(name_parts[:3])
                return True, original_author.strip()
        
        # Check if post starts with common repost indicators
        if text_lower.startswith(('repost', 're-post', 'reposted', 'shared')):
            # Try to extract author from first sentence
            first_sentence = post_text.split('.')[0] if '.' in post_text else post_text.split('\n')[0]
            # Look for "by [Name]" or "[Name] said" patterns
            by_match = re.search(r'(?:by|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', first_sentence, re.IGNORECASE)
            if by_match:
                return True, by_match.group(1).strip()
        
        return False, ""
import logging
import time
import random
from datetime import datetime

from typing import Dict, Any, Optional

from common.utils import dump_to_parquet, upload_to_dls, clean_file
from common.config import Config
from common.utils import setup_logging
from common.exception import LoginTwitterException

from scraping.core.post_cache import PostCache
from scraping.twitter.twitter_parser import TwitterParser
from scraping.core.web_scraper import IWebScraper
from scraping.twitter.twitter_post_extractor import ExtractTwitterPostException
from messaging.service_bus_publisher import ServiceBusPublisher
from typing import Dict, Any, List

from models.classify import classify_text

from network.relation import (
    RelationshipModel
)

setup_logging()
logger = logging.getLogger(__name__)

class TwitterPostFormatter:
    """
    Enriches scraped Twitter post data with categorization metadata.
    """

    INDUSTRY_MAP = {
        "Natural Language Processing (NLP)": "Technology / AI",
        "Computer Vision (CV)": "Technology / AI",
        "Generative AI": "Technology / AI",
        "Machine Learning (ML)": "Technology / AI",
        "Data Analytics": "Business Intelligence",
        "Orchestration": "Data Engineering",
        "Robotics": "Manufacturing / Automation",
        "Non-technical": "Non-technical",
    }

    def entry_format(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        enriched = raw_data.copy()
        url = enriched["post_url"]
        logger.info(f" +---- Format post content for {url}")
        content = enriched.get("content", "")

        topics = self._extract_topics(content)
        industries = self._extract_supported_industries(topics)

        is_tech = any(
            t and t != "Non-technical"
            for t in topics
        )

        enriched.update({
            "topic": topics,
            "supported_industry": industries,
            "is_tech_related": is_tech,
            "scraped_at": datetime.utcnow().isoformat()
        })

        logger.info(enriched)
        return enriched

    
    def _extract_topics(self, content: str) -> List[str]:
        return classify_text(content)
    
    def _extract_supported_industries(self, topics: List[str]) -> List[str]:
        return sorted(
            {
                self.INDUSTRY_MAP.get(topic, "Other")
                for topic in topics
            }
        )

class TwitterPostScraper(IWebScraper):
    """
    Scrapes the latest post for each user in a relationship graph.
    """
    RETRY_SLEEP = 5 * 60      # 5 minutes
    MAX_RETRIES = 1
    HUMAN_DELAY_MIN = 10      # seconds
    HUMAN_DELAY_MAX = 15
    
    def __init__(self, 
                 relations: RelationshipModel, 
                 parser: Optional[TwitterParser] = None, 
                 formatter: Optional[TwitterPostFormatter] = None,
                 run_in_test: bool = False) -> None:
        self.relations = relations
        parser = parser or TwitterParser(run_in_local=True)
        formatter = formatter or TwitterPostFormatter()
        self.cache = PostCache("post_cache.json")
        self.publisher = ServiceBusPublisher(
            conn_str= Config.SERVICE_BUS_CONNECTION_STRING,
            topic_name= Config.TWITTER_NEW_POST_TOPIC
        )
        self.run_in_test = run_in_test 
        super().__init__(parser, formatter)
    
    def __enter__(self):
        self.parser = self.parser.__enter__()
        if not self.run_in_test:
            try:
                self.parser.login(Config.TWITTER_EMAIL, Config.TWITTER_PASSWORD)
            except LoginTwitterException as e:
                logger.error(f"{e}")
        return self

    def __exit__(self, exc_type, exc, tb):
        return self.parser.__exit__(exc_type, exc, tb)
    
    def _handle_retry(self, err: Exception, retries: int):
        logger.warning(f"Unknown error {err}")
        if retries <= self.MAX_RETRIES:
            logger.info(
                f"Retrying after {self.RETRY_SLEEP // 60} minutes..."
            )
            time.sleep(self.RETRY_SLEEP)
            self._reset_parser()
        else:
            logger.error("Max retries reached — backing off")

    def _emit_new_post_event(self, formatted_post: Dict[str, Any]) -> None:

        self.publisher.publish(
            event_type="twitter.post.new",
            payload=formatted_post
        )

        logger.info(
            f"[EVENT] Published new post event {formatted_post['post_url']}"
        )

    def _scrape_new_for_user(self, username: str) -> None:
        retries = 0

        while retries <= self.MAX_RETRIES:
            try:
                found = False
                for post in self.parser.iter_new_post(username,  self.cache):
                    if not post:
                        logger.info(f"Found empty post for user {username}")
                        continue
                    
                    url = post["post_url"]
                    logger.info(f"Found new post {url}")

                    found = True
                    formatted = self.formatter.entry_format(post)
                    self._emit_new_post_event(formatted)
                    
                if not found:
                    logger.info(f"No new posts for user {username}")
                    return

            except ExtractTwitterPostException as err:
                logger.error(f"[ERROR] {err}")
                return

            except Exception as err:
                retries += 1
                self._handle_retry(err, retries)

    def scrape_new_post(self) -> None:
        """
        Scrape only newly detected posts using cache.
        """
        usernames = list(self.relations.to_dict().keys())
        random.shuffle(usernames)

        for username in usernames:
            logger.info(f"+---- Checking new posts for {username} ----")
            self._scrape_new_for_user(username)
            time.sleep(random.uniform(self.HUMAN_DELAY_MIN, self.HUMAN_DELAY_MAX))

    def scrape(self, limit=3, is_uploaded=False) -> None:
        """
        Login once and scrape posts for all known users.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"twitter_scraping_data_{timestamp}.parquet"

        for username in self.relations.to_dict().keys():
            retries = 0

            while retries <= self.MAX_RETRIES:
                logger.info(f"+---- Scraping posts for user {username} ----")
                try:
                    posts     = self.parser.scrape_post(username, limit)
                    if not posts:
                        logger.info(f"No posts found for user {username}")
                        break
                    
                    formatted_posts = [self.formatter.entry_format(post) for post in posts]

                    for formatted in formatted_posts:
                        dump_to_parquet(formatted, Config.TWITTER_DATA_DIR, file_name)
                    
                    logger.info(f"Parquet dump succesfully for user {username}")
                        
                    sleep_time = random.uniform(
                        self.HUMAN_DELAY_MIN,
                        self.HUMAN_DELAY_MAX
                    )
                    logger.info(f"Sleeping {sleep_time:.1f}s (human delay)")
                    time.sleep(sleep_time)
                    break
                
                except ExtractTwitterPostException as err:
                    logger.error(f"[ERROR] : {err}")
                    break

                except Exception as err:
                    retries += 1
                    self._handle_retry(err,  retries)
        if is_uploaded:
            upload_to_dls(Config.TWITTER_DATA_DIR, file_name)
            clean_file(Config.TWITTER_DATA_DIR, file_name)

    def _reset_parser(self):
        try:
            if self.parser:
                self.parser.__exit__(None, None, None)
        except Exception:
            pass

        logger.warning("Reinitializing TwitterParser (new session)")
        self.parser = TwitterParser(run_in_local=True)
        self.parser.login(Config.TWITTER_EMAIL, Config.TWITTER_PASSWORD)
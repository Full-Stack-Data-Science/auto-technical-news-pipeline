import time
import random
import logging
from typing import Dict, Optional
from datetime import datetime

from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from common.utils import setup_logging, human_scroll
from post_scraper.core.selenum_helper import (
    safe_get,
    find,
    find_all,
    try_find,
    get_text,
    get_attr,
    attr,
    first,
)

from post_scraper.core.models.post import EngagementStats, SocialPost, Platform
from post_scraper.twitter.twitter_profile_extractor import TwitterProfileExtractor, ExtractTwitterProfileException

setup_logging()
logger = logging.getLogger(__name__)

class ExtractTwitterPostException(Exception):
    pass

    
def _to_int(v):
    try:
        return int(str(v).replace(",", ""))
    except:
        return 0

def extract_username_from_post_url(post_url: str) -> str:
    path_paths = urlparse(post_url).path.strip("/").split("/")
    return path_paths[0]

class TwitterPostExtractor:
    def __init__(self, driver):
        self.driver = driver
        self.user_extractor = TwitterProfileExtractor(driver)
        self.seen_posts = set()
        
    def extract(self, post_url: str):
        try:    
            user_name = extract_username_from_post_url(post_url)
            user_info = self.user_extractor.extract(user_name)

            safe_get(self.driver, post_url)
            # time.sleep(random.uniform(4,6))
            
            logger.info(f"+ Process scraping {post_url}")
            human_scroll(self.driver, 4, 50, 100)
            
            articles = find_all(
                self.driver,
                By.XPATH,
                "//article[@role='article']"
            )

            if not articles:
                logger.warning(f"No article found after scroll: {post_url}")
                return None
            
            for article in articles:
                links = find_all(
                    article,
                    By.XPATH,
                    ".//a[contains(@href, '/status/')]"
                )

                for link in links:
                    href = attr(link, "href")
                    if not href:
                        continue

                    if href in self.seen_posts:
                        logger.info(f"Bypass {post_url} since it's the reply post")
                        return None

            quoted_url = self._find_quoted_url(articles[0])
            if (quoted_url):
                logger.info(f"Found a quoted tweets {quoted_url}")
                return self.extract(quoted_url)
            
            content = self._extract_content(articles[0])
            date_str = self._extract_date(articles[0])
            stats = self._extract_stats(articles[0])

            return SocialPost(
                post_url=post_url,
                author=user_info,
                content=content,
                date=datetime.fromisoformat(date_str.replace("Z", "+00:00")),
                stats=stats,
                platform=Platform.TWITTER,
            )
        
        except ExtractTwitterProfileException as e:
            raise ExtractTwitterPostException(f"Profile extraction failed due to {e}")
        except Exception as e:
            raise ExtractTwitterPostException(f"Extraction process error due to {e}")
    
    def _find_quoted_url(self, article) -> Optional[str]:
        link = try_find(
            article,
            By.XPATH,
            ".//a[contains(@href, '/status/') and ancestor::*[@role='link']]"
        )
        return attr(link, "href") if link else None
    
    def _extract_date(self, article) -> str:
        datetime_val = get_attr(
            article,
            By.TAG_NAME,
            "time",
            "datetime",
            fallback=""
        )

        if not datetime_val:
            raise ExtractTwitterPostException("Date extraction failed")

        return datetime_val
        
    def _extract_content(self, article) -> str:
        return get_text(
            article,
            By.CSS_SELECTOR,
            "div[data-testid='tweetText']",
            fallback=""
        )
    
    def _extract_stats(self, article) -> Dict[str, str]:
        aria = get_attr(
            article,
            By.CSS_SELECTOR,
            "div[aria-label][role='group']",
            "aria-label",
            fallback=""
        )

        if not aria:
            raise ExtractTwitterPostException("Stats extraction failed")

        parsed = {}

        for part in aria.split(", "):
            tokens = part.split(" ", 1)
            if len(tokens) == 2:
                parsed[tokens[1].lower()] = tokens[0]
        
        return EngagementStats(
            comments=_to_int(parsed.get("replies")),
            reposts=_to_int(parsed.get("reposts")),
            reactions=_to_int(parsed.get("likes")),
            bookmarks=_to_int(parsed.get("bookmarks")),
            views=_to_int(parsed.get("views")),
        )
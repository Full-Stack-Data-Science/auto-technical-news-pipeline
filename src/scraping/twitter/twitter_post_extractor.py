import time
import random
import logging
from typing import Dict, Optional

from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from common.utils import setup_logging, human_scroll
from scraping.twitter.twitter_profile_extractor import TwitterProfileExtractor, ExtractTwitterProfileException

setup_logging()
logger = logging.getLogger(__name__)

class ExtractTwitterPostException(Exception):
    pass

def extract_username_from_post_url(post_url: str) -> str:
    path_paths = urlparse(post_url).path.strip("/").split("/")
    return path_paths[0]

class TwitterPostExtractor:
    def __init__(self, driver):
        self.driver = driver
        self.user_extractor = TwitterProfileExtractor(driver)
        self.seen_posts = set()

    def find_the_quoted_article(self, article) -> Optional[str]:
        try:
            quoted_link = article.find_element(
                By.XPATH,
                ".//a[contains(@href, '/status/') and ancestor::*[@role='link']]"
            )

            quoted_url = quoted_link.get_attribute("href")
            return quoted_url if quoted_url else None
        except Exception as e:
            return None
        
    def extract(self, user_name: str, post_url: str):
        try:    
            user_name = extract_username_from_post_url(post_url)
            user_info = self.user_extractor.extract(user_name)

            self.driver.get(post_url)
            time.sleep(random.uniform(4,6))
            
            logger.info(f"+----- Process scraping {post_url} -----+ ")
            human_scroll(self.driver, 4, 50, 100)

            articles = self.driver.find_elements(By.XPATH, "//article[@role='article']")
            if not articles:
                logger.warning(
                        f"No article found after scroll: {post_url}"
                )
                return None
            
            for article in articles:
                links = article.find_elements(By.XPATH, ".//a[contains(@href, '/status/')]")
                for link in links:
                    href = link.get_attribute("href")
                    if (href in self.seen_posts):
                        logger.info(f"Bypass {post_url} since it's the reply post")
                        return None
                                        
            quoted_url = self.find_the_quoted_article(articles[0])
            if (quoted_url):
                logger.info(f"Found a quoted tweets {quoted_url}")
                return self.extract(user_name, quoted_url)
            
            return {
                **user_info,
                "post_url": post_url,
                "content": self._extract_content(articles[0]),
                "date": self._extract_date(articles[0]),
                **self._extract_stats(articles[0]),
            }
        except ExtractTwitterProfileException as e:
            raise ExtractTwitterPostException(f"Profile extraction failed due to {e}")
        except Exception as e:
            raise ExtractTwitterPostException(f"Extraction process error due to {e}")

    def _extract_date(self, article) -> str:
        try:
            time_el = article.find_element(By.TAG_NAME, "time")
            return time_el.get_attribute("datetime")
        except Exception as e:
            raise ExtractTwitterPostException(f"Date extraction error: {e}")

    def _is_pinned(self, article) -> bool:
        try:
            pinned_label = article.find_elements(
                By.XPATH, ".//*[@aria-label='Pinned']"
            )
            if pinned_label:
                return True
            pinned_text = article.find_elements(
                By.XPATH, ".//*[normalize-space()='Pinned']"
            )
            if pinned_text:
                return True
        except Exception:
            return False
        

    def _extract_content(self, article) -> str:
        try:
            block = article.find_element(
                By.CSS_SELECTOR, "div[data-testid='tweetText']"
            )
            return block.text.strip()
        except Exception as e:
            logger.warning(f"Content extraction error: {e}")
            return ""


    def _extract_stats(self, article) -> Dict[str, str]:
        """
        Extract engagement stats from aria-label metadata.
        """
        try:
            stats_div = article.find_element(
                By.CSS_SELECTOR, "div[aria-label][role='group']"
            )
            aria = stats_div.get_attribute("aria-label")
            parts = aria.split(", ")

            parsed = {}
            for part in parts:
                tokens = part.split(" ", 1)
                if len(tokens) == 2:
                    number, label = tokens
                else:
                    number = "0"
                    label = tokens[0]
                
                parsed[label.lower()] = number

            return {
                "comments": parsed.get("replies", "0"),
                "reposts": parsed.get("reposts", "0"),
                "reactions": parsed.get("likes", "0"),
                "bookmarks": parsed.get("bookmarks", "0"),
                "views": parsed.get("views", "0"),
            }

        except Exception as e:
            raise ExtractTwitterPostException(f"Date extraction error: {e}")

import logging
import time
import random

from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from common.utils import setup_logging
from common.config import Config

setup_logging()
logger = logging.getLogger(__name__)

class ExtractTwitterProfileException(Exception):
    pass

def _parse_count(text: str) -> int:
    text = text.replace(",", "").strip()

    if text.endswith("K"):
        return int(float(text[:-1]) * 1_000)
    if text.endswith("M"):
        return int(float(text[:-1]) * 1_000_000)
    if text.endswith("B"):
        return int(float(text[:-1]) * 1_000_000_000)

    return int(text)


class TwitterProfileExtractor:
    def __init__(self, driver):
        self.driver = driver
        self._cache: Dict[str, Dict[str, Any]] = {}

    def extract_followers_count(self, user_name: str) -> int:
        """
        Extract followers count for a given Twitter user.
        """
        try:
            wait = WebDriverWait(self.driver, 10)

            followers_link = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[contains(@href, '/verified_followers')]//span")
                )
            )

            raw_text = followers_link.text
            return _parse_count(raw_text)            
        except Exception as e:
            raise ExtractTwitterProfileException(
                f"Extract followers count for {user_name} error: {e}"
            )
            
    def extract_influencer_title(self, user_name: str) -> str:
        """
        Extract influencer title / bio label for a given Twitter user.
        """
        try:
            wait = WebDriverWait(self.driver, 10)
            bio_element = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@data-testid='UserDescription']")
                )
            )
            return bio_element.text.strip()
        
        except Exception as exc:
            logger.warning(f"Cannot extract influencer title for {user_name} due to: {exc}")
            return ""

    def extract(self, user_name: str) -> Dict[str, Any]:
        """
        Extract Twitter profile data with caching.
        """
        if user_name in self._cache:
            logger.debug("Returning cached profile for %s", user_name)
            return self._cache[user_name]
            
        url = f"{Config.TWITTER_PAGE}/{user_name}"
        self.driver.get(url)
        time.sleep(random.uniform(1, 2))
            
        logger.info("Extracting Twitter profile for %s", user_name)

        profile = {
            "author": user_name,
            "followers_count": self.extract_followers_count(user_name),
            "influencer_title": self.extract_influencer_title(user_name),
        }

        self._cache[user_name] = profile
        return profile
import logging
from typing import Dict, Any

from selenium.webdriver.common.by import By

from common.utils import setup_logging
from common.config import Config

from post_scraper.core.models.post import AuthorProfile, Platform
from post_scraper.core.selenum_helper import (
    safe_get,
    get_text,
    find,
)

setup_logging()
logger = logging.getLogger(__name__)


class ExtractTwitterProfileException(Exception):
    pass


def parse_count(text: str) -> int:
    text = text.replace(",", "").strip()
    suffixes = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

    for suffix, multiplier in suffixes.items():
        if text.endswith(suffix):
            return int(float(text[:-1]) * multiplier)

    return int(text)


class TwitterProfileExtractor:
    def __init__(self, driver):
        self.driver = driver
        self._cache: Dict[str, AuthorProfile] = {}

    def _wait_profile_ready(self):
        """
        Ensure profile page is actually rendered (X is dynamic).
        """
        find(
            self.driver,
            By.XPATH,
            "//div[@data-testid='UserDescription'] | //a[contains(@href, '/verified_followers')]"
        )

    def _extract_followers_count(self, username: str) -> int:
        text = get_text(
            self.driver,
            By.XPATH,
            "//a[contains(@href, '/verified_followers')]//span",
        )

        if not text:
            raise ExtractTwitterProfileException(
                f"Followers count extraction failed for {username}"
            )

        return parse_count(text)

    def _extract_influencer_title(self) -> str:
        return get_text(
            self.driver,
            By.XPATH,
            "//div[@data-testid='UserDescription']",
            fallback="",
        )

    def extract(self, author: str) -> Dict[str, Any]:
        """
        Extract Twitter profile data with caching.
        """
        if author in self._cache:
            logger.debug("Returning cached profile for %s", author)
            return self._cache[author]

        safe_get(self.driver, f"{Config.TWITTER_PAGE}/{author}")

        self._wait_profile_ready()

        logger.info(f"Extracting Twitter profile for {author}")

        profile = AuthorProfile(
            author=author,
            followers_count=self._extract_followers_count(author),
            influencer_title=self._extract_influencer_title()
        )

        self._cache[author] = profile
        return profile
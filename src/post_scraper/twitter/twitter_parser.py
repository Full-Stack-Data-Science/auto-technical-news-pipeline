import logging
from selenium.webdriver.common.by import By


from common.config import Config
from common.utils import setup_logging, human_scroll

from post_scraper.twitter.twitter_post_extractor import TwitterPostExtractor
from post_scraper.core.selenum_helper import (
    find_all,
    attr,
    try_find
)

setup_logging()
logger = logging.getLogger(__name__)


class TwitterParser:
    def __init__(self, driver):
        self.driver = driver
        self.extractor = TwitterPostExtractor(driver)

    def collect_recent_post_urls(self, username, limit=10):
        url = f"{Config.TWITTER_PAGE}/{username}"
        self.driver.get(url)

        human_scroll(self.driver, 4, pause_time = (1, 3))

        articles = find_all(self.driver, By.CSS_SELECTOR, "article")

        urls = []
        for article in articles:
            link = try_find(article, By.CSS_SELECTOR, "a[href*='/status/']")
            href = attr(link, "href")

            if href:
                urls.append(href)

            if len(urls) >= limit:
                break

        return urls

    def scrape_posts(self, username, limit=5):
        urls = self.collect_recent_post_urls(username, limit)

        results = []
        for url in urls:
            post = self.extractor.extract(url)
            if post:
                results.append(post)

        return results
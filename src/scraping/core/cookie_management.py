import json
import os
import time
import logging
from pathlib import Path

from common.utils import setup_logging
from common.config import Config

setup_logging()
logger = logging.getLogger(__name__)

class CookieManager:
    def __init__(self, cookie_file: str) -> None:
        self.cookie_file = cookie_file
        os.makedirs(Config.COOKIE_PATH, exist_ok=True)
        self._cache = {}

    def get_cache(self):
        return self._cache
    
    def load(self):
        if self._cache is not None:
            return self._cache
        return self.load_from_file()

    def load_from_file(self):
        if not os.path.exists(self.cookie_file):
            return []
        cookies = None
        with open(self.cookie_file, "r") as f:
            cookies = json.load(f)
        self._cache = cookies
        return cookies

    def save(self, cookies):
        # Create directory if it doesn't exist
        cookie_dir = os.path.dirname(self.cookie_file)
        if cookie_dir and not os.path.exists(cookie_dir):
            os.makedirs(cookie_dir, exist_ok=True)
            logger.info(f"Created cookie directory: {cookie_dir}")
        
        with open(self.cookie_file, "w") as f:
            json.dump(cookies, f)
    
    def has_valid_cookies(self) -> bool:
        if (not self._cache):
            return False

        now = int(time.time())
        for cookie in self._cache:
            expiry = cookie.get("expiry")
            if expiry is None:
                continue
            if expiry < now:
                return False
        logger.info("Cookies is validated")
        return True

    def clean(self):
        self._cache = None
        if os.path.exists(self.cookie_file):
            os.remove(self.cookie_file)
            logger.info("Cookie file removed")
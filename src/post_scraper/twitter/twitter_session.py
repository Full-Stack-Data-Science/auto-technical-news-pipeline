import time
import logging

from selenium.webdriver.common.by import By

from common.config import Config
from common.utils import setup_logging
from post_scraper.core.selenum_helper import (
    safe_get,
    find,
)

setup_logging()
logger = logging.getLogger(__name__)

class LoginTwitterException(Exception):
    pass

class TwitterSession:
    def __init__(self, driver):
        self.driver = driver

    def login(self, email: str, password: str):
        if self._is_logged_in():
            logger.info("Already logged in")
            return
        
        logger.info("Falling back to Google login...")
        self._login_with_google(email, password)

    def _is_logged_in(self):
        try:
            safe_get(self.driver, f"{Config.TWITTER_PAGE}/home")

            find(
                self.driver,
                By.CSS_SELECTOR,
                "[data-testid='SideNav_NewTweet_Button']"
            )
            return True
        except Exception:
            return False

    def _login_with_google(self, email: str, password: str):
        try:
            safe_get(self.driver, Config.TWITTER_LOGIN)

            self._click_google_button()
            self._switch_to_popup()

            self._enter_email(email)
            time.sleep(3)
            self._enter_password(password)
            self._switch_back()

            if not self._is_logged_in():
                raise LoginTwitterException("Login failed after Google auth")


            logger.info("Login successful via Google")
            time.sleep(5)

        except Exception as e:
            raise LoginTwitterException(f"Google login failed: {e}")

    def _click_google_button(self):
        try:
            iframe = find(
                self.driver,
                By.CSS_SELECTOR,
                "iframe[src*='accounts.google.com']"
            )

            self.driver.switch_to.frame(iframe)

            btn = find(
                self.driver,
                By.CSS_SELECTOR,
                "div[role='button']"
            )

            time.sleep(2)
            btn.click()

            logger.info("Clicked Google sign-in button")

        except Exception as e:
            raise LoginTwitterException("Google button not found") from e

    def _switch_to_popup(self):
        main = self.driver.current_window_handle

        for _ in range(10):
            if len(self.driver.window_handles) > 1:
                break
            time.sleep(1)

        for handle in self.driver.window_handles:
            if handle != main:
                self.driver.switch_to.window(handle)
                logger.info("Switched to Google popup")
                return

        raise LoginTwitterException("No popup found")

    def _switch_back(self):
        main = self.driver.window_handles[0]
        self.driver.switch_to.window(main)
        logger.info("Switched back to main window")
        time.sleep(5)

    def _enter_email(self, email: str):
        try:
            email_input = find(
                self.driver,
                By.CSS_SELECTOR,
                "input[type='email']"
            )

            email_input.clear()
            email_input.send_keys(email)

            next_btn = find(
                self.driver,
                By.CSS_SELECTOR,
                "#identifierNext button"
            )
            next_btn.click()

        except Exception as e:
            raise LoginTwitterException("Failed entering email") from e

    def _enter_password(self, password: str):
        try:
            password_input = find(
                self.driver,
                By.CSS_SELECTOR,
                "input[type='password']"
            )

            password_input.clear()
            password_input.send_keys(password)

            next_btn = find(
                self.driver,
                By.CSS_SELECTOR,
                "#passwordNext button"
            )
            next_btn.click()

        except Exception as e:
            raise LoginTwitterException("Failed entering password") from e
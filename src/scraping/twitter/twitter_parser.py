import time
import random
import logging
import requests

from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Remote
from selenium.common.exceptions import WebDriverException

from common.config import Config
from common.utils import setup_logging, human_scroll
from common.exception import *

from scraping.core.web_parser import IWebParser
from scraping.core.cookie_management import CookieManager
from scraping.twitter.twitter_post_extractor import TwitterPostExtractor

setup_logging()
logger = logging.getLogger(__name__)

class GoogleSignInButtonNotFound(Exception):
    pass

class LoginTwitterException(Exception):
    pass

def wait_for_selenium(timeout=120):
    logger.info("Waiting for Selenium Grid server to be ready...")

    start = time.time()
    while True:
        try:
            r = requests.get(
                f"http://{Config.SELENIUM_HOST}:4444/wd/hub/status",
                timeout=2
            )
            if r.json().get("value", {}).get("ready"):
                logger.info("Selenium Grid is ready")
                return
        except Exception:
            pass

        if time.time() - start > timeout:
            raise RuntimeError("Selenium Grid did not become ready in time")

        logger.info("Waiting for Selenium...")
        time.sleep(2)


class TwitterParser(IWebParser):
    def __init__(
        self,
        url: Optional[str] = Config.TWITTER_PAGE,
        rotate_header: bool = False,
        run_in_local: bool = False,
        driver = None,
    ) -> None:
        super().__init__(url, rotate_header)
        self.cookie_manager = CookieManager(Config.COOKIE_FILE)
        self.cookie_manager.load_from_file()
        self.run_in_local = run_in_local
        if (not run_in_local):
            wait_for_selenium()
        self.driver = driver or self._create_driver()
        self.post_extractor = TwitterPostExtractor(self.driver)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.driver:
                logger.info("Closing browser")
                self.driver.quit()
        except Exception as e:
            logger.error(f"Error while closing driver: {e}")

        return False
    
    def _create_driver(self, isHeadLess=True) -> webdriver.Chrome:
        logger.info("Initializing Chrome driver...")

        driver = None

        try:
            options = webdriver.ChromeOptions()

            if (self.cookie_manager.has_valid_cookies()):
                self.rotate_header = True
            else:
                self.cookie_manager.clean()
            
            if isHeadLess:
                options.add_argument("--headless=new")
    
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument(
                "--user-data-dir=./google-chrome"
            )
            options.add_argument("--profile-directory=Profile_Twitter")
                        
            # Rotate user-agent
            if self.rotate_header:
                # Optional headless mode
                options.add_argument("--headless=new")

                user_agent = self.get_header().get("User-Agent")
                options.add_argument(f"--user-agent={user_agent}")
                logger.info(f"Using user-agent for rotation purpose: {user_agent}")

            # Hide Selenium automation fingerprints
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            # TODO IP proxy rotating
            if (self.run_in_local):
                driver = webdriver.Chrome(options=options)
            else:
                driver = Remote(
                    f"http://{Config.SELENIUM_HOST}:4444/wd/hub", options=options
                )

            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            logger.info("Driver ready")
            return driver
        
        except WebDriverException as e:
            logger.error(f"WebDriver initialization failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while creating driver: {e}") 

    def reset_driver(self, isHeadLess):
        self.driver.quit()
        self.driver = self._create_driver(isHeadLess)

    def login(self, email: str, password: str) -> None:
        """
        Login via Google OAuth or stored cookies.
        """
        if not self._is_signed_in():
            logger.info("User is not logged in yet")
        else:
            return
                
        if self.login_by_cookie():
            return

        self.reset_driver(isHeadLess=False)
        self.login_by_google_account(email, password)
    
    def login_by_google_account(self, email, password):
        self.driver.get(Config.TWITTER_LOGIN)
        self._wait_for_google_button()

        if not self._switch_to_popup():
            raise LoginTwitterException("No pop-up found")

        self._enter_google_email(email)
        self._enter_google_password(password)
        self._switch_back_to_main()
                
        if (not self._is_signed_in()):
            raise LoginTwitterException("Not allowed to sign in from X")  
            
        self.save_cookies()
        time.sleep(random.uniform(5, 10))
    
    def save_cookies(self):
        cookies = self.driver.get_cookies()
        self.cookie_manager.save(cookies)
        logger.info("Cookies saved.")
        
    def _is_signed_in(self, timeout: int = 10) -> bool:
        time.sleep(6)
        try:
            self.driver.get(f"{Config.TWITTER_PAGE}/home")

            WebDriverWait(self.driver, timeout).until(
                EC.any_of(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[data-testid='SideNav_AccountSwitcher_Button']")
                    ),
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[data-testid='SideNav_NewTweet_Button']")
                    ),
                )
            )

            logger.info("Signed in successfully")
            return True
        except Exception:
            return False
    
    def login_by_cookie(self):
        if self.load_cookies():
            self.driver.get(f"{Config.TWITTER_PAGE}/home")
            time.sleep(5)
            if "login" not in self.driver.current_url:
                logger.info("Logged in with cookies!")
                return True
        
        logger.info("Cookie login failed (session expired).")
        return False

    def load_cookies(self):
        cookies = self.cookie_manager.load()
        if (not cookies):
            return False

        self.driver.get(Config.TWITTER_PAGE)  
        time.sleep(3)

        for cookie in cookies:
            cookie.pop("expiry", None)
            try:
                self.driver.add_cookie(cookie)
            except:
                pass

        logger.info("Cookies loaded.")
        return True
    
    def collect_recent_post_urls(self, user_name, limit=20, interval_sleep=(5, 8), max_steps_scrolls=6, human_scroll_pause=(1, 4)):
        url = f"{Config.TWITTER_PAGE}/{user_name}"
        self.driver.get(url)
        time.sleep(random.uniform(*interval_sleep))
        human_scroll(self.driver, max_steps=max_steps_scrolls, pause_time=human_scroll_pause)

        post_urls = []
        articles = WebDriverWait(self.driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article"))
        )

        for article in articles:
            post_url = article.find_element(
                By.CSS_SELECTOR, "a[href*='/status/']"
            ).get_attribute("href")

            if (self._is_pinned(article)):
                logger.info(f"By pass  {post_url} post since it's a pinned message")
                continue
                
            if (len(post_urls) >= limit):
                break
            
            post_urls.append(post_url)

        logger.info(f"Total {len(post_urls)} posts at the beginning")

        return post_urls

    def iter_new_post(self, user_name, cache):
        post_urls = self.collect_recent_post_urls(user_name, 
                                                  limit=3, 
                                                  interval_sleep=(1, 2), 
                                                  max_steps_scrolls=4, 
                                                  human_scroll_pause=(1,3))
        for url_post in post_urls:
            if not cache.add_if_new(user_name, url_post):
                continue
            json = self.post_extractor.extract(user_name, url_post)  
            if json != None:
                self.post_extractor.seen_posts.add(url_post)
            yield json

    def scrape_post(self, username: str, limit=20):
        """
        Scrape the most recent post from a user's profile.
        """
        collected_post_urls = self.collect_recent_post_urls(username, limit)

        craw_scraping_data = []
        for post_url in collected_post_urls:
            json = self.post_extractor.extract(username, post_url)
            if json != None:
                self.post_extractor.seen_posts.add(post_url)
                craw_scraping_data.append(json)

        return craw_scraping_data

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
        
    def _switch_back_to_main(self):
        main_window = self.driver.window_handles[0]
        self.driver.switch_to.window(main_window)
        logger.info("Switched back to main Twitter window.")
        time.sleep(6)

    def _enter_google_email(self, email):
        try:
            email_box = WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            logger.info("Email box field detected.")

            email_box.send_keys(email)

            next_btn = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#identifierNext button"))
            )
            next_btn.click()
        except Exception as e:
            raise LoginTwitterException("Error in loggin by Email") from e

    def _enter_google_password(self, password):
        try: 
            password_box = WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            logger.info("Password field detected.")

            password_box.clear()
            password_box.send_keys(password)

            next_btn = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#passwordNext button"))
            )

            next_btn.click()
        except Exception as e:
            raise LoginTwitterException("Error in loggin by password") from e
        
    def _switch_to_popup(self):
            main = self.driver.current_window_handle
            time.sleep(5)

            for w in self.driver.window_handles:
                if w != main:
                    self.driver.switch_to.window(w)
                    logger.info("Switched to Google sign-in popup window")
                    return True

            logger.info("No pop up found")
            return False
        
    def _wait_for_google_button(self, timeout=20):
        try:
            iframe = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='accounts.google.com/gsi/button']"))
            )
            self.driver.switch_to.frame(iframe)
            google_btn = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='button']"))
            )
            time.sleep(5)
            google_btn.click()

            logger.info("Clicked on Google Sign-in button")

        except Exception as e:
            raise GoogleSignInButtonNotFound("Google sign-in button did not appear within timeout") from e

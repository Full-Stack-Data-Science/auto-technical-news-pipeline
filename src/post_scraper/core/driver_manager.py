from selenium import webdriver
from selenium.webdriver import Remote
from selenium.common.exceptions import WebDriverException
from common.config import Config
import logging

logger = logging.getLogger(__name__)


class DriverManager:
    def __init__(self, run_in_local=True, headless=True):
        self.run_in_local = run_in_local
        self.headless = headless
        self.driver = None

    def __enter__(self):
        self.driver = self._create_driver()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.quit()

    def get(self):
        return self.driver

    def _create_driver(self):
        options = webdriver.ChromeOptions()

        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
                "--user-data-dir=./google-chrome"
            )
        options.add_argument("--profile-directory=Profile_Twitter")
        
        try:
            if self.run_in_local:
                driver = webdriver.Chrome(options=options)
            else:
                driver = Remote(
                    f"http://{Config.SELENIUM_HOST}:4444/wd/hub",
                    options=options
                )

            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            logger.info("Driver initialized")
            return driver

        except WebDriverException as e:
            logger.error(f"Driver init failed: {e}")
            raise

    def reset(self, headless):
        logger.warning("Resetting driver...")
        self.headless=headless
        
        self.quit()    
        self.driver = self._create_driver()
        return self.driver

    def quit(self):
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Driver closed")
        except Exception as e:
            logger.warning(f"Error closing driver: {e}")
import logging

from selenium import webdriver
from selenium.webdriver import Remote
from selenium.common.exceptions import WebDriverException

from common.config import Config

logger = logging.getLogger(__name__)


class DriverManager:
    """
    Creates and manages a Selenium Chrome driver.
    Used by both Twitter and LinkedIn scrapers — pass the appropriate
    profile_directory for each platform.
    """

    def __init__(
        self,
        run_in_local: bool = True,
        headless: bool = True,
        profile_directory: str = "Profile_Twitter",
        user_data_dir: str = "./google-chrome",
    ):
        self.run_in_local = run_in_local
        self.headless = headless
        self.profile_directory = profile_directory
        self.user_data_dir = user_data_dir
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

        # Core stability
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-sync")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--password-store=basic")
        options.add_argument("--use-mock-keychain")

        # Anti-detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        # Chrome profile (persistent session — avoids re-login on every run)
        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        options.add_argument(f"--profile-directory={self.profile_directory}")

        try:
            if self.run_in_local:
                driver = webdriver.Chrome(options=options)
            else:
                driver = Remote(
                    f"http://{Config.SELENIUM_HOST}:4444/wd/hub",
                    options=options,
                    keep_alive=True,
                )
                driver.set_page_load_timeout(60)
                driver.implicitly_wait(10)

            try:
                driver.execute_script(
                    """
                    try {
                        const desc = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
                        if (!desc || desc.configurable) {
                            Object.defineProperty(Navigator.prototype, 'webdriver', {
                                get: () => undefined, configurable: true
                            });
                        }
                    } catch (e) {}
                    """
                )
            except Exception:
                pass

            logger.info("Driver initialized (profile=%s, headless=%s)", self.profile_directory, self.headless)
            return driver

        except WebDriverException as e:
            logger.error(f"Driver init failed: {e}")
            raise

    def reset(self, headless: bool):
        logger.warning("Resetting driver (headless=%s)...", headless)
        self.headless = headless
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

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import time
import json

from common.utils import setup_logging
import logging
from common.config import Config

setup_logging()
logger = logging.getLogger(__name__)



BASE_ARGS = [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-component-extensions-with-background-pages",
    "--disable-features=TranslateUI",
    "--disable-ipc-flooding-protection",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--disable-sync",
    "--metrics-recording-only",
    "--no-first-run",
    "--safebrowsing-disable-auto-update",
    "--password-store=basic",
    "--use-mock-keychain",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-notifications",
]


def build_options(use_profile: bool = True) -> Options:
    options = Options()

    for arg in BASE_ARGS:
        options.add_argument(arg)

    options.add_experimental_option(
        "excludeSwitches", ["enable-automation", "enable-logging"]
    )
    options.add_experimental_option("useAutomationExtension", False)

    if use_profile:
        options.add_argument("--user-data-dir=./google-chrome")
        options.add_argument("--profile-directory=Profile_FSDS")

    return options

def create_driver() -> webdriver.Chrome:
    try:
        return webdriver.Chrome(options=build_options(use_profile=True))
    except Exception as e:
        logger.warning(f"Chrome failed with profile, retrying without profile: {e}")
        return webdriver.Chrome(options=build_options(use_profile=False))

def is_logged_in(driver, timeout=10):
    wait = WebDriverWait(driver, timeout)

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "header")))

        sign_in_links = driver.find_elements(
            By.CSS_SELECTOR, "a[href='/sign-in']"
        )
        return len(sign_in_links) == 0

    except TimeoutException:
        return False


def login(driver, email, password, timeout=20):
    wait = WebDriverWait(driver, timeout)

    driver.get("https://fullstackdatascience.com/sign-in")

    # Email
    email_box = wait.until(
        EC.visibility_of_element_located((By.NAME, "email"))
    )
    email_box.clear()
    email_box.send_keys(email)

    # Password
    password_box = wait.until(
        EC.visibility_of_element_located((By.NAME, "password"))
    )
    password_box.clear()
    password_box.send_keys(password)

    time.sleep(4)

    # Sign In button
    sign_in_button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[normalize-space()='Sign In']")
        )
    )
    sign_in_button.click()

    # Wait for redirect away from sign-in
    wait.until(lambda d: "/sign-in" not in d.current_url)
    time.sleep(2)

def get_cookies(driver, save_to_file=True):
    driver.get("https://fullstackdatascience.com/")
    time.sleep(2)

    cookies = driver.get_cookies()

    if save_to_file:
        with open("session_cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)

    return cookies

def get_session_cookies():
    email = Config.FSDS_USERNAME
    password = Config.FSDS_PASSWORD

    if not email or not password:
        raise RuntimeError(
            "FSDS credentials are missing. Set environment variables "
            "FSDS_USERNAME and FSDS_PASSWORD (e.g. in `src/set_env.sh` or `.env`)."
        )

    driver = create_driver()
    driver.get("https://fullstackdatascience.com/")

    login(driver, email, password)

    if is_logged_in(driver):
        print("Login successful")
    else:
        print("Login failed in headless mode")
        driver.quit()
        
        # Retry in non-headless mode (similar to LinkedIn)
        print("Retrying login in non-headless mode...")
        options = Options()
        options.add_argument("--start-maximized")
        # DO NOT add --headless argument - we want visible browser
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--user-data-dir=./google-chrome")
        options.add_argument("--profile-directory=Profile_FSDS")
        
        driver = webdriver.Chrome(options=options)
        
        try:
            driver.get("https://fullstackdatascience.com/")
            login(driver, email, password)
            
            if is_logged_in(driver):
                print("Login successful in non-headless mode")
            else:
                print("Login failed in non-headless mode")
                driver.quit()
                raise RuntimeError(
                    "FSDS login failed in both headless and non-headless modes. "
                    "Please check credentials or complete CAPTCHA manually."
                )
        except Exception as e:
            driver.quit()
            raise RuntimeError(f"FSDS login failed: {e}")

    cookies = get_cookies(driver)
    print(f"Retrieved {len(cookies)} cookies")

    time.sleep(2)
    driver.quit()

    for c in cookies:
        if (c['name'] == 'fsdslsvmfqcber'):
            return c['value']

    # If we get here, the cookie wasn't found
    raise RuntimeError("FSDS session cookie 'fsdslsvmfqcber' not found after login")
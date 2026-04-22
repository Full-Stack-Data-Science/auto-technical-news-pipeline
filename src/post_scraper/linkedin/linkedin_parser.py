import os
import time
import random
import logging
import requests
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from selenium import webdriver
from selenium.webdriver import Remote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException

from common.config import Config
from scraping.core.web_parser import IWebParser
from scraping.core.cookie_management import CookieManager
from scraping.linkedin.linkedin_post_extractor import LinkedInPostExtractor
from scraping.linkedin.linkedin_profile_extractor import LinkedInProfileExtractor
from common.utils import setup_logging
from bs4 import BeautifulSoup
from datetime import datetime

setup_logging()
logger = logging.getLogger(__name__)

def wait_for_selenium(timeout=120, required=True):
    """
    Wait for Selenium Grid server to be ready.
    
    Args:
        timeout: Maximum time to wait in seconds
        required: If False, will not raise error if Selenium is not available (for local testing)
    """
    logger.info(f"Checking for Selenium Grid server at {Config.SELENIUM_HOST}:4444...")
    start = time.time()
    
    while True:
        try:
            r = requests.get(
                f"http://{Config.SELENIUM_HOST}:4444/wd/hub/status",
                timeout=2
            )
            response = r.json()
            ready = response.get("value", {}).get("ready", False)
            # Check if Grid is ready
            if ready:
                logger.info("Selenium Grid is ready")
                return True
            nodes = response.get("value", {}).get("nodes", [])
            if nodes:
                logger.info("Selenium Grid is responding (nodes available)")
                return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            logger.debug(f"Error checking Selenium status: {e}")
            pass

        elapsed = time.time() - start
        if elapsed > timeout:
            if required:
                raise RuntimeError(
                    f"Selenium Grid did not become ready in {timeout} seconds. "
                    f"Please start Selenium Grid: docker-compose up -d selenium-chrome\n"
                    f"Then wait 30-60 seconds for it to fully initialize."
                )
            else:
                logger.warning(
                    f"Selenium Grid not available after {timeout}s. "
                    f"Start it with: docker-compose up -d selenium-chrome"
                )
                return False

        if int(elapsed) % 10 == 0:  
            logger.info(f"Waiting for Selenium... ({int(elapsed)}s)")
        time.sleep(2)


class LinkedInParser(IWebParser):
    """Parser for LinkedIn web scraping with robust login and navigation"""
    
    def __init__(
        self,
        url: Optional[str] = "https://www.linkedin.com",
        rotate_header: bool = False,
        driver = None,
        run_in_local: bool = False,
        require_selenium: bool = True,
    ) -> None:
        super().__init__(url, rotate_header)
        self.cookie_manager = CookieManager(Config.LINKEDIN_COOKIE_FILE)
        
        # Check if Chrome profile directory exists
        profile_paths = [
            os.path.join(Config.PROJECT_ROOT, "google-chrome", "Profile_LinkedIn"),
            os.path.join(Config.PROJECT_ROOT, "src", "google-chrome", "Profile_LinkedIn"),
            "./google-chrome/Profile_LinkedIn",
        ]
        
        self.profile_path = None
        for path in profile_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                self.profile_path = abs_path
                logger.info(f"Found Chrome profile at: {abs_path}")
                break
        
        self.cookie_manager.load_from_file()
        if self.profile_path and not self.cookie_manager.has_valid_cookies():
            logger.info("No valid cookies in JSON file, attempting to extract from Chrome profile...")
            try:
                if hasattr(self.cookie_manager, 'load_from_profile_and_save'):
                    if self.cookie_manager.load_from_profile_and_save(self.profile_path, domain="linkedin.com"):
                        logger.info("Successfully extracted cookies from Chrome profile")
            except Exception as e:
                logger.warning(f"Could not extract cookies from profile: {e}")
        
        if self.profile_path and not run_in_local:
            logger.info("Chrome profile found - consider using run_in_local=True to use profile directly")
        
        self.run_in_local = run_in_local
        
        if not run_in_local:
            selenium_available = wait_for_selenium(timeout=60, required=require_selenium)
            if not selenium_available and require_selenium:
                raise RuntimeError(
                    "Selenium Grid is not available. "
                    "To run locally, start Selenium with: docker-compose up -d selenium-chrome\n"
                    "Or run from the src directory: cd src && docker-compose up -d selenium-chrome\n"
                    "Then wait 30-60 seconds for it to be ready."
                )
        
        self.driver = driver or self._create_driver()
        self.post_extractor = LinkedInPostExtractor(self.driver)
        self.profile_extractor = LinkedInProfileExtractor(
            self.driver,
            is_authwall_checker=self._is_authwall
        )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if self.driver:
                logger.info("Closing browser")
                self.driver.quit()
        except Exception as e:
            logger.error(f"Error while closing driver: {e}")
        return False
    
    def _create_driver(self) -> webdriver.Chrome:
        """Create Chrome WebDriver (imitating Twitter logic)"""
        logger.info("Initializing Chrome driver...")
        
        options = webdriver.ChromeOptions()

        if self.cookie_manager.has_valid_cookies():
            self.rotate_header = True
        else:
            self.cookie_manager.clean()
        

        # Enable Chrome functionality for headless mode
        options.add_argument("--headless=new")
        logger.info("Running Chrome in headless mode (forced for VM/server compatibility)")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # Additional stability options to prevent Chrome hanging/crashing
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-breakpad")
        options.add_argument("--disable-component-extensions-with-background-pages")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--password-store=basic")
        options.add_argument("--use-mock-keychain")
        
        if self.run_in_local and self.profile_path:
            profile_dir = os.path.dirname(self.profile_path)
            abs_profile_dir = os.path.abspath(profile_dir)
            profile_name = os.path.basename(self.profile_path)
            options.add_argument(f"--user-data-dir={abs_profile_dir}")
            options.add_argument(f"--profile-directory={profile_name}")
            logger.info(f"Using Chrome profile directory (local mode): {abs_profile_dir}/{profile_name}")
        elif self.run_in_local:
            options.add_argument("--user-data-dir=./google-chrome")
            options.add_argument("--profile-directory=Profile_LinkedIn")
            logger.info("Using Chrome profile directory (local mode, fallback)")

        # Rotate user-agent if we have cookies
        if self.rotate_header:
            user_agent = self.get_header().get("User-Agent")
            options.add_argument(f"--user-agent={user_agent}")
            logger.info(f"Using user-agent for rotation: {user_agent}")
        
        # Hide Selenium automation fingerprints (more aggressive than Twitter)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-infobars") 
        options.add_argument("--disable-notifications")
        
        # Create driver - local or remote (same as Twitter)
        if self.run_in_local:
            try:
                driver = webdriver.Chrome(options=options)
            except Exception as e:
                if self.profile_path:
                    logger.warning(f"Chrome failed to start with profile: {e}")
                    logger.warning("Retrying without profile (headless mode)...")
                    # Remove profile arguments and retry
                    options._arguments = [arg for arg in options._arguments 
                                        if not arg.startswith("--user-data-dir") 
                                        and not arg.startswith("--profile-directory")]
                    driver = webdriver.Chrome(options=options)
                else:
                    raise
        else:
            driver = Remote(
                command_executor=f"http://{Config.SELENIUM_HOST}:4444/wd/hub",
                options=options,
                keep_alive=True
            )
            driver.set_page_load_timeout(60) 
            driver.implicitly_wait(10)  

        try:
            driver.execute_script(
                """
                try {
                    const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
                    if (!descriptor || descriptor.configurable) {
                        Object.defineProperty(Navigator.prototype, 'webdriver', {
                            get: () => undefined,
                            configurable: true
                        });
                    }
                } catch (e) {
                    // Keep browser startup resilient; no-op on hardened browsers.
                }
                """
            )
        except Exception as e:
            if "Cannot redefine property: webdriver" in str(e):
                logger.debug("navigator.webdriver is non-configurable in this Chrome version; skipping override")
            else:
                logger.warning(f"Failed to execute script to hide webdriver property: {e}")
        
        try:
            if not self.run_in_local:
                logger.info("Testing driver connection...")
                current_url = driver.current_url
                logger.info(f"Driver connection successful (current URL: {current_url})")
        except Exception as e:
            logger.error(f"Driver connection test failed: {e}")
        
        logger.info("Chrome driver initialized")
        return driver
    
    def _is_logged_in(self) -> bool:
        """Check if user is actually logged in"""
        try:
            current_url = self.driver.current_url.lower()
            # Quick URL check first
            if "/feed" in current_url or ("/in/" in current_url and "/login" not in current_url):
                return True
            
            WebDriverWait(self.driver, 3).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".global-nav__me")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".artdeco-global-alert")),
                    EC.presence_of_element_located((By.ID, "global-nav")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test-id='nav__profile']"))
                )
            )
            return True
        except:
            return False
    
    def _is_authwall(self) -> bool:
        """Detect if LinkedIn is showing an authwall or challenge page"""
        try:
            current_url = self.driver.current_url.lower()
            
            if "/authwall" in current_url or "/challenge" in current_url or "/checkpoint" in current_url:
                logger.warning(f"Authwall/challenge detected in URL: {current_url}")
                return True
            
            try:
                page_source = self.driver.page_source.lower()
                authwall_indicators = [
                    "we've detected unusual activity",
                    "verify your identity",
                    "security challenge",
                    "unusual activity",
                    "verify it's you",
                    "challenge page",
                    "authwall",
                    "please sign in to continue",
                    "sign in to view"
                ]
                
                if any(indicator in page_source for indicator in authwall_indicators):
                    logger.warning("Authwall/challenge detected in page content")
                    return True
            except (WebDriverException, AttributeError):
                pass
            
            return False
        except Exception as e:
            logger.warning(f"Error checking for authwall: {e}")
            return False
    
    def _handle_authwall_and_relogin(self, context: str = "", retry_url: Optional[str] = None, max_retries: int = 4) -> bool:
        """
        Handle authwall/challenge by attempting a fresh login and optional retry.
        
        This is adapted from the standalone connections scraper logic the user provided:
        - Clear stale cookies
        - Perform a full login using configured credentials
        - Optionally retry navigating to the target URL and re-check for authwall
        
        Returns:
            True if authwall is cleared and (if retry_url is given) the page is usable.
        """
        from common.config import Config  # local import to avoid cycles

        logger.warning(f"Authwall detected during {context or 'operation'} - attempting fresh login...")
        
        email = getattr(Config, "EMAIL", None)
        password = getattr(Config, "PASSWORD", None)
        if not email or not password:
            logger.error("credentials not set - cannot re-login to bypass authwall")
            return False
        
        for attempt in range(1, max_retries + 1):
            try:
                try:
                    self.cookie_manager.clean()
                except Exception as e:
                    logger.debug(f"Error cleaning cookie manager during authwall handling: {e}")
                try:
                    self.driver.delete_all_cookies()
                except Exception:
                    pass
                
                logger.info(f"Authwall re-login attempt {attempt}/{max_retries}...")
                self.login(email, password)
                
                time.sleep(3)
                if not self._is_logged_in():
                    logger.warning("Re-login completed but still not logged in")
                    continue
                
                if not retry_url:
                    logger.info("Successfully re-logged in after authwall")
                    return True
                
                logger.info(f"Retrying navigation to {retry_url} after re-login...")
                self.driver.get(retry_url)
                time.sleep(random.uniform(5, 10))
                
                if self._is_authwall():
                    logger.warning("Authwall still present after re-login and retry navigation")
                    continue
                
                logger.info("Authwall cleared after re-login; continuing scraping")
                return True
            
            except Exception as e:
                logger.warning(f"Error during authwall re-login attempt {attempt}: {e}")
                time.sleep(5)
        
        logger.error("Failed to bypass authwall after multiple re-login attempts")
        return False
    
    def _dismiss_apple_signin(self):
        """Dismiss any Apple sign-in popups/windows/buttons"""
        try:
            main_handle = self.driver.current_window_handle
        except Exception:
            main_handle = None
        
        # Look for Apple sign-in buttons/links and close them
        apple_selectors = [
            "//button[contains(@aria-label, 'Apple') or contains(text(), 'Apple')]",
            "//a[contains(@aria-label, 'Apple') or contains(text(), 'Apple')]",
            "//button[contains(@class, 'apple')]",
        ]
        
        for selector in apple_selectors:
            try:
                apple_elements = self.driver.find_elements(By.XPATH, selector)
                for elem in apple_elements:
                    if elem.is_displayed():
                        try:
                            close_btn = elem.find_element(By.XPATH, ".//ancestor::*[contains(@class, 'modal')]//button[contains(@aria-label, 'Close')]")
                            close_btn.click()
                            logger.info("Dismissed Apple sign-in popup")
                            time.sleep(2)
                            return
                        except:
                            pass
            except:
                continue
        
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(1)
        except:
            pass
    
    def _handle_welcome_back(self):
        """Handle 'Welcome Back' screen by clicking 'Sign in using another account'"""
        try:
            welcome_text = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Welcome Back') or contains(text(), 'Welcome back')]"))
            )
            logger.info("Detected 'Welcome Back' screen")
            
            try:
                sign_in_another_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[contains(text(), 'Sign in using another account') or contains(text(), 'Sign in with another account')] | "
                        "//a[contains(text(), 'Sign in using another account')]"
                    ))
                )
                sign_in_another_btn.click()
                logger.info("Clicked 'Sign in using another account'")
                time.sleep(4)
                self._dismiss_apple_signin()
            except:
                logger.info("Could not find 'Sign in using another account' - proceeding normally")
        except:
            pass 
    
    def _wait_for_google_button(self, timeout=20) -> bool:
        """Wait for and click Google sign-in button on LinkedIn login page"""
        try:
            google_selectors = [
                (By.CSS_SELECTOR, "button[data-provider='google']"),
                (By.CSS_SELECTOR, "button[aria-label*='Google']"),
                (By.XPATH, "//button[contains(text(), 'Google')]"),
                (By.XPATH, "//button[contains(@aria-label, 'Google')]"),
                (By.CSS_SELECTOR, "button.btn-google"),
                (By.CSS_SELECTOR, "a[data-provider='google']"),
                (By.CSS_SELECTOR, "iframe[src*='accounts.google.com']"),
            ]
            
            for by, selector in google_selectors:
                try:
                    if by == By.CSS_SELECTOR and "iframe" in selector:
                        # Handle iframe case (like Twitter)
                        iframe = WebDriverWait(self.driver, timeout).until(
                            EC.presence_of_element_located((by, selector))
                        )
                        logger.info("Found Google sign-in iframe")
                        self.driver.switch_to.frame(iframe)
                        google_btn = WebDriverWait(self.driver, timeout).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='button']"))
                        )
                        time.sleep(2)
                        google_btn.click()
                        self.driver.switch_to.default_content()
                        logger.info("Clicked on Google Sign-in button (via iframe)")
                        return True
                    else:
                        google_btn = WebDriverWait(self.driver, timeout).until(
                            EC.element_to_be_clickable((by, selector))
                        )
                        time.sleep(2)
                        google_btn.click()
                        logger.info("Clicked on Google Sign-in button")
                        return True
                except Exception as e:
                    logger.debug(f"Google button not found with {by}={selector}: {e}")
                    continue
            
            logger.warning("Google sign-in button not found")
            return False
        except Exception as e:
            logger.warning(f"Error waiting for Google button: {e}")
            return False
    
    def _switch_to_popup(self) -> bool:
        """Switch to Google OAuth popup window"""
        try:
            main = self.driver.current_window_handle
            time.sleep(5)
            
            for w in self.driver.window_handles:
                if w != main:
                    self.driver.switch_to.window(w)
                    logger.info("Switched to Google sign-in popup window")
                    return True
            
            logger.warning("No popup window found")
            return False
        except Exception as e:
            logger.error(f"Error switching to popup: {e}")
            return False
    
    def _switch_back_to_main(self):
        """Switch back to main LinkedIn window"""
        try:
            main_window = self.driver.window_handles[0]
            self.driver.switch_to.window(main_window)
            logger.info("Switched back to main LinkedIn window")
            time.sleep(6)
        except Exception as e:
            logger.error(f"Error switching back to main window: {e}")
    
    def _enter_google_email(self, email: str):
        """Enter Google email in OAuth popup"""
        try:
            email_box = WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            logger.info("Email box field detected in Google popup")
            
            email_box.clear()
            email_box.send_keys(email)
            
            next_btn = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#identifierNext button, button#identifierNext"))
            )
            next_btn.click()
            logger.info("Clicked Next after entering email")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Error entering Google email: {e}")
            raise Exception("Error in logging in by Google Email") from e
    
    def _enter_google_password(self, password: str):
        """Enter Google password in OAuth popup"""
        try:
            password_box = WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            logger.info("Password field detected in Google popup")
            
            password_box.clear()
            password_box.send_keys(password)
            
            next_btn = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#passwordNext button, button#passwordNext"))
            )
            next_btn.click()
            logger.info("Clicked Next after entering password")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error entering Google password: {e}")
            raise Exception("Error in logging in by Google Password") from e
    
    def login(self, email: str, password: str):
        """
        Login to LinkedIn via Google OAuth or stored cookies.
        Similar to Twitter's Google authentication flow.
        If login fails in headless mode, will retry in non-headless mode.
        
        Args:
            email: Google email (for OAuth) or LinkedIn email (fallback)
            password: Google password (for OAuth) or LinkedIn password (fallback)
        """
        logger.info("Starting LinkedIn login process...")
        
        # Try login in current mode (headless or not)
        try:
            self._attempt_login(email, password)
            return
        except Exception as e:
            logger.warning(f"Login attempt failed: {e}")
            
            # Check if we're in headless mode
            is_headless = False
            try:
                chrome_options = self.driver.capabilities.get('goog:chromeOptions', {})
                args = chrome_options.get('args', [])
                for arg in args:
                    if isinstance(arg, str) and '--headless' in arg:
                        is_headless = True
                        break
                
                if not is_headless:
                    try:
                        window_size = self.driver.get_window_size()
                        if window_size.get('width', 0) == 0 and window_size.get('height', 0) == 0:
                            is_headless = True
                    except:
                        pass
                
                if not is_headless and os.name != 'nt':  
                    display = os.environ.get('DISPLAY')
                    if not display or display == '':
                        is_headless = True
                        
            except Exception as detection_error:
                logger.debug(f"Error detecting headless mode: {detection_error}")
                is_headless = True
            
            if is_headless:
                logger.info("Login failed in headless mode. Retrying in non-headless mode...")
                logger.info("This will allow manual intervention if needed (CAPTCHA, etc.)")
                
                # Store original driver
                original_driver = self.driver
                original_run_in_local = self.run_in_local
                
                try:
                    # Close headless driver
                    try:
                        self.driver.quit()
                    except:
                        pass
                    
                    # Temporarily switch to local mode and non-headless
                    self.run_in_local = True
                    
                    # Create new driver in non-headless mode
                    logger.info("Creating Chrome driver in non-headless mode...")
                    self.driver = self._create_driver_non_headless()
                    
                    # Retry login
                    logger.info("Retrying login in non-headless mode...")
                    self._attempt_login(email, password)
                    
                    logger.info("Login successful in non-headless mode!")
                    return
                    
                except Exception as non_headless_error:
                    logger.error(f"Login also failed in non-headless mode: {non_headless_error}")
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = original_driver
                    self.run_in_local = original_run_in_local
                    raise Exception(f"Login failed in both headless and non-headless modes. Last error: {non_headless_error}") from e
            else:
                raise
    
    def _attempt_login(self, email: str, password: str) -> None:
        """
        Internal method to attempt login. Called by login() method.
        
        Args:
            email: Google email (for OAuth) or LinkedIn email (fallback)
            password: Google password (for OAuth) or LinkedIn password (fallback)
        """
        if self.run_in_local and self.profile_path:
            logger.info("Using Chrome profile - navigating to LinkedIn to restore session...")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Navigating to LinkedIn (attempt {attempt + 1}/{max_retries})...")
                    self.driver.set_page_load_timeout(30)
                    self.driver.get(Config.LINKEDIN_PAGE)
                    time.sleep(random.uniform(5, 10))  
                    logger.info("Waiting for session restoration from Chrome profile...")
                    
                    # Wait for either login page or feed page to appear (max 15 seconds)
                    max_wait = 15
                    waited = 0
                    while waited < max_wait:
                        current_url = self.driver.current_url
                        page_source = self.driver.page_source.lower()
                        
                        # Check if we're on login page or feed/home page
                        if "login" in current_url.lower() or "signin" in current_url.lower():
                            if "feed" in page_source or "mynetwork" in page_source:
                                # Redirected to feed after auto-login
                                logger.info("Detected auto-login redirect to feed!")
                                break
                            elif waited < max_wait - 2:
                                time.sleep(random.uniform(2, 5))
                                waited += 2
                                continue
                            else:
                                logger.info("Still on login page after session restoration attempt")
                                break
                        elif "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                            logger.info("Already on LinkedIn feed/profile - auto-login successful!")
                            break
                        else:
                            time.sleep(2)
                            waited += 2
                    
                    logger.info(f"Final URL after session restoration: {self.driver.current_url}")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Navigation failed: {e}. Retrying...")
                        time.sleep(5)
                    else:
                        logger.error(f"Failed to navigate after {max_retries} attempts: {e}")
                        raise
            
            logger.info("Checking if auto-login was successful...")
            if self._is_logged_in():
                logger.info("Already logged in via Chrome profile - skipping login!")
                return
            else:
                logger.warning("Chrome profile did not auto-login - LinkedIn may have detected automation or session expired")
                logger.info("Will try cookie/login methods...")
        else:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Navigating to LinkedIn (attempt {attempt + 1}/{max_retries})...")
                    
                    try:
                        current_url = self.driver.current_url
                        logger.debug(f"Driver is responsive (current URL: {current_url})")
                    except Exception as e:
                        logger.warning(f"Driver not responsive before navigation: {e}")
                        if attempt < max_retries - 1:
                            logger.info("Recreating driver due to unresponsiveness...")
                            try:
                                self.driver.quit()
                            except:
                                pass
                            time.sleep(5)
                            self.driver = self._create_driver()
                            time.sleep(5)
                        continue
                    
                    # Set timeout for navigation
                    self.driver.set_page_load_timeout(30)  
                    self.driver.get("https://www.linkedin.com")
                    time.sleep(3)
                    logger.info("Successfully navigated to LinkedIn")
                    break
                except Exception as e:
                    error_msg = str(e).lower()
                    if "timeout" in error_msg or "timeoutexception" in error_msg or "renderer" in error_msg:
                        if attempt < max_retries - 1:
                            logger.warning(f"Navigation timeout on attempt {attempt + 1}: {e}")
                            logger.info("Recreating driver and retrying...")
                            try:
                                self.driver.quit()
                            except:
                                pass
                            time.sleep(5)
                            # Recreate driver for next attempt
                            self.driver = self._create_driver()
                            time.sleep(5)
                        else:
                            logger.error(f"Navigation timeout after {max_retries} attempts. Chrome in Selenium Grid may be unstable.")
                            # Last attempt: try with local Chrome if profile available
                            if not self.run_in_local and self.profile_path:
                                logger.info("Attempting fallback to local Chrome driver with profile...")
                                try:
                                    self.driver.quit()
                                except:
                                    pass
                                # Temporarily switch to local mode
                                original_run_in_local = self.run_in_local
                                self.run_in_local = True
                                try:
                                    self.driver = self._create_driver()
                                    self.driver.set_page_load_timeout(30)
                                    self.driver.get("https://www.linkedin.com")
                                    time.sleep(5)
                                    logger.info("Successfully navigated using local Chrome driver with profile")
                                    if self._is_logged_in():
                                        logger.info("Already logged in via Chrome profile!")
                                        return
                                    break
                                except Exception as local_e:
                                    logger.error(f"Local Chrome driver also failed: {local_e}")
                                    self.run_in_local = original_run_in_local
                                    raise WebDriverException(f"Failed to navigate to LinkedIn after {max_retries} attempts. Both Remote and Local Chrome drivers failed.") from e
                            else:
                                raise WebDriverException(f"Failed to navigate to LinkedIn after {max_retries} attempts due to timeout.") from e
                    else:
                        logger.error(f"Navigation failed: {e}")
                        raise
        
        # Check if already logged in (after navigation)
        if self._is_logged_in():
            logger.info("Already logged in (likely from cookies or profile)")
            return
        
        # Try cookie login from JSON file
        if self.login_by_cookie():
            logger.info("Logged in using cookies from JSON file")
            return
        
        # Try Google OAuth login  
        try:
            logger.info("Attempting Google OAuth login...")
            self.driver.get(Config.LINKEDIN_LOGIN)
            time.sleep(random.uniform(2, 5))
            
            self._dismiss_apple_signin()
            
            self._handle_welcome_back()
            
            if self._wait_for_google_button():
                if self._switch_to_popup():
                    logger.info("Switched to Google OAuth popup")
                    self._enter_google_email(email)
                    self._enter_google_password(password)
                    self._switch_back_to_main()
                    
                    time.sleep(random.uniform(5, 10))
                    
                    if self._is_logged_in():
                        logger.info("Successfully logged in via Google OAuth!")
                        self.save_cookies()
                        return  
                    else:
                        logger.warning("Google OAuth login may have failed, trying direct login...")
                else:
                    logger.warning("Could not switch to Google popup, trying direct login...")
            else:
                logger.info("Google sign-in button not found, trying direct login...")
        except Exception as e:
            logger.warning(f"Google OAuth login failed: {e}. Trying direct login...")
        
        # Fallback to direct email/password login
        logger.info("Attempting direct email/password login...")
        self.driver.get("https://www.linkedin.com/login")
        time.sleep(random.uniform(2, 5))     
        self._dismiss_apple_signin()
        self._handle_welcome_back()
        
        try:
            WebDriverWait(self.driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "username")),
                    EC.presence_of_element_located((By.NAME, "session_key")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
                )
            )
            logger.info("Login form is ready")
            self._dismiss_apple_signin()
        except:
            logger.warning("Login form may not be ready yet")
        
        # Enter email
        email_field = None
        for by, sel in [
            (By.ID, "username"),
            (By.NAME, "session_key"),
            (By.CSS_SELECTOR, "input[type='email'], input[autocomplete='username']"),
        ]:
            try:
                email_field = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((by, sel)))
                break
            except:
                continue
        
        if not email_field:
            logger.error("Email field not found. Possible CAPTCHA or block.")
            raise Exception("Could not find email field")
        
        self._dismiss_apple_signin()
        email_field.clear()
        # Human-like typing
        for char in email:
            email_field.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        time.sleep(random.uniform(1, 2))
        
        # Enter password
        password_field = None
        for by, sel in [
            (By.ID, "password"),
            (By.NAME, "session_password"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ]:
            try:
                password_field = WebDriverWait(self.driver, 8).until(EC.element_to_be_clickable((by, sel)))
                break
            except:
                continue
        
        if not password_field:
            logger.error("Password field not found")
            raise Exception("Could not find password field")
        
        # Human-like typing
        for char in password:
            password_field.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        time.sleep(random.uniform(1, 2))
        
        # Submit
        try:
            submit_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], button.btn__primary--large"))
            )
            submit_btn.click()
            logger.info("Clicked submit button")
        except:
            password_field.send_keys(Keys.ENTER)
            logger.info("Submitted via Enter key")
        
        time.sleep(12)
        
        # Check for success
        login_successful = False
        try:
            WebDriverWait(self.driver, 20).until(EC.url_contains("/feed"))
            logger.info("Successfully logged in to /feed!")
            login_successful = True
        except:
            logger.warning("No /feed redirect - checking if manual login is needed...")
            current_url = self.driver.current_url.lower()
            
            # Check if we're on a challenge/CAPTCHA page
            if "/challenge" in current_url or "/checkpoint" in current_url or "captcha" in current_url:
                logger.warning("CAPTCHA or security challenge detected!")
                
                # Check if running in headless mode (Azure/Docker) - can't do manual CAPTCHA
                is_headless = self.driver.execute_script("return navigator.webdriver") is not None
                is_docker = os.path.exists("/src") and os.path.isdir("/src")
                
                if is_headless or is_docker:
                    logger.error(" CAPTCHA detected in headless/Docker environment - cannot complete manually")
                    logger.error("This usually means LinkedIn detected automated access")
                    logger.error("Possible solutions:")
                    logger.error("  1. Wait and retry later (rate limiting)")
                    logger.error("  2. Use cookies from a previous successful login")
                    logger.error("  3. Check if credentials are correct")
                    raise Exception("CAPTCHA challenge in headless environment - cannot complete automatically")
                else:
                    logger.info("Please complete the challenge manually in the browser...")
                    logger.info("Waiting up to 2 minutes for manual completion...")
                    
                    # Wait for manual completion (check every 10 seconds)
                    for i in range(12):  
                        time.sleep(10)
                        current_url = self.driver.current_url.lower()
                        if "/feed" in current_url or self._is_logged_in():
                            logger.info("✓Manual login completed successfully!")
                            login_successful = True
                            break
                        if i % 6 == 0:  
                            logger.info(f"Still waiting... ({i * 10}s elapsed)")
                    
                    if not login_successful:
                        logger.error(" Manual login timeout. Please try again.")
                        raise Exception("Manual login timeout - please complete CAPTCHA and try again")
            else:
                # Check if we're actually logged in 
                if self._is_logged_in():
                    logger.info("Successfully logged in (verified by page elements)")
                    login_successful = True
                else:
                    logger.warning("Login status unclear. Attempting to verify...")
                    # Try navigating to feed to check
                    self.driver.get("https://www.linkedin.com/feed")
                    time.sleep(5)
                    if self._is_logged_in() or "/feed" in self.driver.current_url.lower():
                        logger.info("✓ Login verified after navigation")
                        login_successful = True
        
        if login_successful:
            self.save_cookies()
        else:
            logger.error("Login failed. Cookies not saved.")
            raise Exception("LinkedIn login failed - please check credentials or complete CAPTCHA")
    
    def _create_driver_non_headless(self) -> webdriver.Chrome:
        """
        Create Chrome WebDriver in non-headless mode for manual intervention.
        Used as fallback when headless login fails.
        
        Returns:
            Chrome WebDriver instance
        """
        logger.info("Creating Chrome driver in non-headless mode...")
        
        options = webdriver.ChromeOptions()
        
        # Check for valid cookies
        if self.cookie_manager.has_valid_cookies():
            self.rotate_header = True
        else:
            self.cookie_manager.clean()
        
        logger.info("Running Chrome in NON-headless mode (visible browser)")      
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Use Chrome profile directory if available 
        if self.run_in_local and self.profile_path:
            profile_dir = os.path.dirname(self.profile_path)
            abs_profile_dir = os.path.abspath(profile_dir)
            profile_name = os.path.basename(self.profile_path)
            options.add_argument(f"--user-data-dir={abs_profile_dir}")
            options.add_argument(f"--profile-directory={profile_name}")
            logger.info(f"Using Chrome profile directory (non-headless): {abs_profile_dir}/{profile_name}")
        elif self.run_in_local:
            options.add_argument("--user-data-dir=./google-chrome")
            options.add_argument("--profile-directory=Profile_LinkedIn")
            logger.info("Using Chrome profile directory (non-headless, fallback)")
        
        # Rotate user-agent if we have cookies
        if self.rotate_header:
            user_agent = self.get_header().get("User-Agent")
            options.add_argument(f"--user-agent={user_agent}")
            logger.info(f"Using user-agent for rotation: {user_agent}")
        
        # Create driver - local mode only for non-headless
        try:
            driver = webdriver.Chrome(options=options)
            logger.info("Chrome driver created in non-headless mode")
            return driver
        except Exception as e:
            logger.error(f"Failed to create Chrome driver in non-headless mode: {e}")
            raise
    
    def login_by_cookie(self) -> bool:
        """Attempt to login using stored cookies (similar to Twitter)"""
        cookies = self.cookie_manager.load()
        if not cookies:
            logger.warning("No cookies loaded from file")
            return False
        
        logger.info(f"Loaded {len(cookies)} cookies from file")
        for c in cookies[:5]:
            logger.debug(f"Cookie: {c['name']} = {c['value'][:50]}... (domain: {c.get('domain')})")
        
        if not any(c['name'] == 'li_at' for c in cookies):
            logger.warning("Critical 'li_at' cookie missing!")
        
        # Navigate to LinkedIn first
        self.driver.get("https://www.linkedin.com")
        time.sleep(3)
        
        # Add all cookies at once (
        added_count = 0
        for cookie in cookies:
            cookie_copy = cookie.copy()
            cookie_copy.pop("expiry", None)
            try:
                if 'domain' in cookie_copy and not cookie_copy['domain'].startswith('.'):
                    cookie_copy['domain'] = '.linkedin.com'
                self.driver.add_cookie(cookie_copy)
                added_count += 1
            except Exception as e:
                logger.debug(f"Failed to add cookie {cookie.get('name')}: {e}")
        
        logger.info(f"Added {added_count} cookies")
        
        # Refresh once after adding all cookies
        self.driver.refresh()
        time.sleep(5)
        
        # Check if logged in
        if self._is_logged_in():
            logger.info("Logged in with cookies!")
            return True
            
        logger.warning("Cookie login failed - not logged in after refresh")
        return False
    
    def save_cookies(self):
        """Save current session cookies"""
        cookies = self.driver.get_cookies()
        self.cookie_manager.save(cookies)
        logger.info("Cookies saved")
    
    def scrape_post(self, username: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Scrape posts from a LinkedIn user's profile.
        
        Args:
            username: LinkedIn username/slug (e.g., "chiphuyen")
            limit: Maximum number of posts to scrape (default: 3)
            
        Returns:
            List of post dictionaries
        """
        profile_url = f"https://www.linkedin.com/in/{username}/"
        activity_url = f"{profile_url}recent-activity/all/"
        
        # Check for authwall before navigation and try to recover
        if self._is_authwall():
            logger.warning("Authwall detected before scraping posts")
            if not self._handle_authwall_and_relogin(
                context=f"pre-scrape for {username}",
                retry_url=activity_url,
            ):
                logger.warning("Authwall persists after re-login; skipping posts for this user")
                return []
        
        logger.info(f"Scraping posts from {activity_url}")
        self.driver.get(activity_url)
        time.sleep(random.uniform(8, 12))
        
        # Check for authwall after navigation; attempt re-login + retry once
        if self._is_authwall():
            logger.warning("Authwall detected after navigation to posts")
            if not self._handle_authwall_and_relogin(
                context=f"post-navigation scrape for {username}",
                retry_url=activity_url,
            ):
                logger.warning("Authwall still present after re-login; skipping posts for this user")
                return []
        
        # Extract posts using post extractor
        posts = self.post_extractor.extract(activity_url, max_scrolls=5, limit=limit)
        
        return posts
    
    def extract_influencer_info(self, profile_url: str) -> Dict[str, Any]:
        """
        Extract influencer's personal information from their profile page.
        
        Delegates to LinkedInProfileExtractor to maintain separation of concerns.
        
        Args:
            profile_url: LinkedIn profile URL
            
        Returns:
            Dictionary with influencer info (name, title, location, followers_count, encrypted_member_id, profile_url)
        """
        return self.profile_extractor.extract(profile_url)
    
    def scrape_connections_or_followers(
        self, 
        target_profile_url: str, 
        encrypted_id: str,
        influencer_name: str,
        page_threshold: int = 3,
        is_connections: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Scrape connections or followers from LinkedIn search results.
        
        Args:
            target_profile_url: LinkedIn profile URL
            encrypted_id: Encrypted member ID (e.g., "ACoAAC...")
            influencer_name: Name of the influencer
            page_threshold: Maximum number of pages to scrape per degree
            is_connections: True for connections, False for followers
            
        Returns:
            List of connection/follower dictionaries
        """
        data_type = "connections" if is_connections else "followers"
        logger.info(f"Scraping {data_type} for {influencer_name} ({encrypted_id})")
        
        if not encrypted_id or not encrypted_id.startswith("ACoAA"):
            logger.error(f"Invalid encrypted_id for {influencer_name}")
            return []
        
        degrees = [("1st", "F"), ("2nd", "S"), ("3rd", "O")]
        all_results = []
        
        for degree_name, network_code in degrees:
            logger.info(f"   → Scraping {degree_name} degree {data_type}...")
            page = 1
            seen_urls = set()
            
            while page <= page_threshold:
                if is_connections:
                    search_url = (
                        f"https://www.linkedin.com/search/results/people/"
                        f"?network=%5B%22{network_code}%22%5D"
                        f"&connectionOf=%22{encrypted_id}%22"
                        f"&page={page}"
                        f"&origin=FACETED_SEARCH"
                    )
                else:
                    search_url = (
                        f"https://www.linkedin.com/search/results/people/"
                        f"?origin=FACETED_SEARCH"
                        f"&network=%5B%22{network_code}%22%5D"
                        f"&followerOf=%5B%22{encrypted_id}%22%5D"
                        f"&page={page}"
                    )
                
                logger.info(f"Loading {degree_name} | Page {page}")
                self.driver.get(search_url)
                time.sleep(random.uniform(7, 11))
                
                # Check for authwall
                if self._is_authwall():
                    logger.warning(f"Authwall detected - stopping {degree_name} degree")
                    break
                
                # Check for empty results
                source = self.driver.page_source.lower()
                if any(phrase in source for phrase in ["no results found", "0 results", "try different filters"]):
                    logger.info(f"Empty results page detected → stopping {degree_name}")
                    break
                
                # Wait for results
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-view-name="people-search-result"]'))
                    )
                except:
                    logger.warning(f"Timeout waiting for results → stopping {degree_name}")
                    break
                
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                # Find profile cards
                cards = soup.find_all("div", class_=re.compile(r"_9a2dc561.*e897fe38"))
                if not cards:
                    cards = soup.find_all("div", attrs={"data-view-name": "people-search-result"})
                
                if not cards:
                    logger.info(f" No profile cards found → end of data")
                    break
                
                new_on_page = 0
                for card in cards:
                    # Extract profile URL and name
                    link_tag = card.find("a", href=re.compile(r"/in/"), attrs={"data-view-name": "search-result-lockup-title"})
                    if not link_tag:
                        continue
                    
                    profile_url = link_tag["href"].split("?")[0].rstrip("/")
                    if profile_url in seen_urls:
                        continue
                    seen_urls.add(profile_url)
                    
                    # Extract name
                    conn_name = link_tag.get_text(strip=True)
                    if not conn_name or conn_name == "LinkedIn Member":
                        name_span = link_tag.find("span", attrs={"aria-hidden": "true"})
                        if name_span:
                            conn_name = name_span.get_text(strip=True)
                    
                    if not conn_name or conn_name == "LinkedIn Member":
                        continue
                    
                    conn_name = re.sub(r"\s*•\s*[1-3]st.*$", "", conn_name).strip()
                    conn_name = re.sub(r"\s+", " ", conn_name)
                    
                    # Extract title and location
                    name_paragraph = link_tag.find_parent("p")
                    all_paragraphs = card.find_all("p")
                    
                    cleaned_paragraphs = []
                    name_lower = conn_name.lower()
                    
                    for p in all_paragraphs:
                        if p == name_paragraph:
                            continue
                        if p.find("a", attrs={"data-view-name": "search-result-lockup-title"}):
                            continue
                        
                        text = p.get_text(separator=" ", strip=True)
                        if not text or len(text) < 2:
                            continue
                        
                        text = re.sub(r"•\s*\d+(st|nd|rd)\+?\s*", "", text, flags=re.I).strip()
                        if not text:
                            continue
                        
                        text_lower = text.lower()
                        if text == conn_name or text_lower == name_lower:
                            continue
                        if text_lower.startswith(name_lower):
                            remaining = text_lower[len(name_lower):].strip()
                            if not remaining or len(remaining.split()) <= 1:
                                continue
                        
                        if text_lower in ["connect", "message", "follow", "more", "less"]:
                            continue
                        
                        cleaned_paragraphs.append(text)
                    
                    title = cleaned_paragraphs[0] if len(cleaned_paragraphs) > 0 else "—"
                    location = cleaned_paragraphs[1] if len(cleaned_paragraphs) > 1 else "—"
                    
                    # Clean whitespace
                    title = re.sub(r"\s+", " ", title).strip() if title != "—" else "—"
                    location = re.sub(r"\s+", " ", location).strip() if location != "—" else "—"
                    
                    if is_connections:
                        all_results.append({
                            "connection_name": conn_name,
                            "connection_title": title,
                            "connection_location": location,
                            "connection_url": profile_url,
                            "degree": degree_name,
                            "scraped_at": datetime.utcnow().isoformat(),
                            "page": page
                        })
                    else:
                        all_results.append({
                            "follower_name": conn_name,
                            "follower_title": title,
                            "follower_location": location,
                            "follower_url": profile_url,
                            "degree": degree_name,
                            "scraped_at": datetime.utcnow().isoformat(),
                            "page": page
                        })
                    new_on_page += 1
                
                logger.info(f"      Page {page}: +{new_on_page} new → Total {degree_name}: {len([c for c in all_results if c['degree'] == degree_name])}")
                
                if new_on_page == 0:
                    logger.info(f"No new profiles → stopping {degree_name}")
                    break
                
                page += 1
                time.sleep(random.uniform(5, 9))
            
            logger.info(f"Finished {degree_name} degree → {len([c for c in all_results if c['degree'] == degree_name])} {data_type}\n")
        
        return all_results

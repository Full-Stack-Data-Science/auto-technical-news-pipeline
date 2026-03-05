import logging
import time
import random
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Tuple
from collections import Counter

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from common.utils import setup_logging
from common.config import Config

setup_logging()
logger = logging.getLogger(__name__)


class ExtractLinkedInProfileException(Exception):
    """Exception raised when profile extraction fails"""
    pass


# Define bad headlines patterns
ui_elements = {
    "show details", "see more", "see less", "contact info", "more", "less",
    "show", "details", "view", "open", "close", "click", "expand", "collapse"
}


class LinkedInProfileExtractor:
    """
    Extracts LinkedIn influencer profile information and saves metadata.
    
    This class handles:
    - Extracting profile information from LinkedIn pages using HTML tags/selectors
    - Saving influencer metadata to linkedin_influencer_metadata.json
    """
    
    def __init__(self, driver, is_authwall_checker: Optional[Callable[[], bool]] = None):
        """
        Initialize the profile extractor.
        
        Args:
            driver: Selenium WebDriver instance
            is_authwall_checker: Optional function to check for authwall (returns bool)
        """
        self.driver = driver
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._is_authwall = is_authwall_checker or self._default_authwall_checker
    
    def _default_authwall_checker(self) -> bool:
        """Default authwall detection if no custom checker provided"""
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
                ]
                if any(indicator in page_source for indicator in authwall_indicators):
                    return True
            except Exception:
                pass
            
            return False
        except Exception:
            return False
    
    @staticmethod
    def _clean_spaces(value: Optional[str]) -> Optional[str]:
        """Clean and normalize whitespace in text"""
        if not value:
            return None
        value = re.sub(r"\s+", " ", value).strip()
        return value or None
    
    @staticmethod
    def _parse_followers(text: Optional[str]) -> Optional[str]:
        """Parse followers count from text"""
        if not text:
            return None
        m = re.search(r"([\d.,]+[KMB]?)\s*followers?", text, re.IGNORECASE)
        return m.group(1) if m else None
    
    @staticmethod
    def _is_bad_headline_candidate(t: str) -> bool:
        """Check if a text candidate is likely not a professional headline"""
        low = t.strip().lower()
        if not low:
            return True
        low = re.sub(r"^[·•]\s*", "", low).strip()
        if low in {"1st", "2nd", "3rd", "1st+", "2nd+", "3rd+"}:
            return True
        if re.fullmatch(r"\d+(st|nd|rd)\+?", low):
            return True
        if re.match(r"^[·•]\s*\d+(st|nd|rd)", t.strip(), re.IGNORECASE):
            return True
        if "followers" in low or "following" in low:
            return True
        if "connections" in low or "connection" in low:
            return True
        if "mutual" in low:
            return True

        if low in ui_elements:
            return True
        if low.startswith("show ") or low.startswith("see ") or low.startswith("view "):
            return True
        if len(low) <= 15 and not any(indicator in low for indicator in ['|', '@', 'engineer', 'developer', 'manager', 'director', 'lead', 'ai', 'ml', 'data', 'scientist']):
            if low in {"details", "more", "less", "show", "view", "open", "close"}:
                return True
        if len(low) < 3:
            return True
        return False
    
    def _extract_name(self) -> Tuple[Optional[str], Optional[Any]]:
        """
        Extract name from h1/h2 HTML tags.
        
        Returns:
            Tuple of (name string or None, name element or None)
        """
        name_el = None
        try:
            name_el = WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//main//*[self::h1 or self::h2][normalize-space()][1]")
                )
            )
            txt = self._clean_spaces(getattr(name_el, "text", None))
            if txt and txt.lower() != "linkedin member":
                return txt, name_el
        except Exception:
            pass
        
        # Fallback to older selectors
        for by, sel in [
            (By.CSS_SELECTOR, "h1.text-heading-xlarge"),
            (By.CSS_SELECTOR, "h1.inline.t-24.v-align-middle.break-words"),
            (By.CSS_SELECTOR, "h2"),
            (By.CSS_SELECTOR, "h1"),
        ]:
            try:
                el = WebDriverWait(self.driver, 4).until(EC.presence_of_element_located((by, sel)))
                txt = self._clean_spaces(getattr(el, "text", None))
                if txt and txt.lower() != "linkedin member":
                    return txt, el
            except Exception:
                continue
        
        return None, None
    
    def _extract_name_from_soup(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract name using BeautifulSoup fallback"""
        try:
            hover = soup.find(
                lambda tag: tag.get("class")
                and any("artdeco-hoverable-trigger" in c for c in tag.get("class", []))
            )
            if hover:
                a = hover.find("a")
                if a and a.get("aria-label"):
                    return self._clean_spaces(a.get("aria-label"))
        except Exception:
            pass
        return None
    
    def _extract_title_from_name_element(self, name_el) -> Optional[str]:
        """Extract title from div elements following the name element"""
        try:
            headline_divs = name_el.find_elements(
                By.XPATH, 
                "following::div[contains(@class, 'text-body-medium') and contains(@class, 'break-words')][position()<=5]"
            )
            best_title = None
            best_length = 0
            for div in headline_divs:
                try:
                    parent_button = div.find_element(By.XPATH, "./ancestor::button[1]")
                    if parent_button:
                        continue
                except:
                    pass
                
                try:
                    parent_link = div.find_element(By.XPATH, "./ancestor::a[1]")
                    if parent_link:
                        link_text = self._clean_spaces(getattr(parent_link, "text", None) or "")
                        link_text_lower = link_text.lower() if link_text else ""
                        ui_link_texts = {"show details", "see more", "see less", "details", "more", "less", "view", "open"}
                        if link_text_lower in ui_link_texts or (link_text and len(link_text) < 20):
                            continue
                        div_text_lower = self._clean_spaces(getattr(div, "text", None) or "").lower()
                        if div_text_lower in {"show details", "see more", "see less", "details"}:
                            continue
                except:
                    pass
                
                t = self._clean_spaces(getattr(div, "text", None))
                if t and not self._is_bad_headline_candidate(t):
                    txt_len = len(t)
                    if txt_len > best_length and txt_len > 20:
                        has_professional_indicators = any(indicator in t for indicator in ['|', '@', 'Engineer', 'Developer', 'Manager', 'Director', 'Lead', 'AI', 'ML', 'Data', 'Scientist'])
                        if has_professional_indicators or txt_len > 30:
                            best_title = t
                            best_length = txt_len
            return best_title
        except Exception:
            return None
    
    def _extract_title_from_selectors(self) -> Optional[str]:
        """Extract title using multiple CSS/XPath selectors"""
        for by, sel in [
            (By.XPATH, "//section[contains(@class, 'artdeco-card')]//div[contains(@class, 'text-body-medium') and contains(@class, 'break-words')]"),
            (By.CSS_SELECTOR, "section[data-member-id] div.text-body-medium.break-words"),
            (By.CSS_SELECTOR, "div.pv-text-details__left-panel div.text-body-medium.break-words"),
            (By.XPATH, "//div[contains(@class, 'text-body-medium') and contains(@class, 'break-words') and not(ancestor::button) and not(ancestor::a)]"),
            (By.CSS_SELECTOR, "div.text-body-medium.break-words"),
        ]:
            try:
                elements = self.driver.find_elements(by, sel)
                best_title = None
                best_length = 0
                
                for el in elements:
                    try:
                        parent_button = el.find_element(By.XPATH, "./ancestor::button[1]")
                        if parent_button:
                            continue
                    except:
                        pass
                    
                    try:
                        parent_link = el.find_element(By.XPATH, "./ancestor::a[1]")
                        if parent_link:
                            link_text = self._clean_spaces(getattr(parent_link, "text", None) or "")
                            link_text_lower = link_text.lower() if link_text else ""
                            ui_link_texts = {"show details", "see more", "see less", "details", "more", "less", "view", "open"}
                            if link_text_lower in ui_link_texts or len(link_text) < 20:
                                continue
                            el_text_lower = self._clean_spaces(getattr(el, "text", None) or "").lower()
                            if el_text_lower in {"show details", "see more", "see less", "details"}:
                                continue
                    except:
                        pass
                    
                    txt = self._clean_spaces(getattr(el, "text", None))
                    if txt and not self._is_bad_headline_candidate(txt):
                        txt_len = len(txt)
                        if txt_len > best_length and txt_len > 20:
                            has_professional_indicators = any(indicator in txt for indicator in ['|', '@', 'Engineer', 'Developer', 'Manager', 'Director', 'Lead', 'AI', 'ML', 'Data', 'Scientist', 'Master', 'PhD'])
                            if has_professional_indicators or txt_len > 30:
                                best_title = txt
                                best_length = txt_len
                
                if best_title:
                    return best_title
            except Exception:
                continue
        return None
    
    def _extract_title_from_paragraphs(self) -> Optional[str]:
        """Extract title from paragraph elements as last resort"""
        try:
            p_elems = self.driver.find_elements(By.XPATH, "//main//p[normalize-space()]")
            for p in p_elems[:40]:
                t = self._clean_spaces(getattr(p, "text", None))
                if not t or self._is_bad_headline_candidate(t):
                    continue
                return t
        except Exception:
            pass
        return None
    
    def _extract_title(self, name_el=None) -> Optional[str]:
        """
        Extract title/headline from div HTML tags with multiple fallback strategies.
        
        Args:
            name_el: Optional name element to search from
            
        Returns:
            Title string or None if not found
        """
        # Try extracting from name element first
        if name_el is not None:
            title = self._extract_title_from_name_element(name_el)
            if title:
                return title
        
        # Try multiple CSS/XPath selectors
        title = self._extract_title_from_selectors()
        if title:
            return title
        
        # Try paragraph elements as last resort
        return self._extract_title_from_paragraphs()
    
    def _extract_title_from_soup(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title using BeautifulSoup fallback"""
        try:
            title_div = soup.find("div", class_=lambda x: x and "text-body-medium" in str(x) and "break-words" in str(x))
            if title_div:
                return self._clean_spaces(title_div.get_text(" ", strip=True))
        except Exception:
            pass
        return None
    
    def _extract_location(self) -> Optional[str]:
        """
        Extract location from span HTML tags.
        
        Returns:
            Location string or None if not found
        """
        for by, sel in [
            (By.CSS_SELECTOR, "span.text-body-small.inline.t-black--light.break-words"),
            (By.CSS_SELECTOR, "span.text-body-small.t-black--light.break-words"),
        ]:
            try:
                el = self.driver.find_element(by, sel)
                txt = self._clean_spaces(getattr(el, "text", None))
                if txt:
                    return txt
            except Exception:
                continue
        return None
    
    def _extract_followers_count(self) -> Optional[str]:
        """
        Extract followers count using XPath to find elements containing "followers" text.
        
        Returns:
            Followers count string or None if not found
        """
        try:
            followers_el = self.driver.find_element(
                By.XPATH,
                "//*[contains(translate(normalize-space(.), 'FOLLOWERS', 'followers'), 'followers')]",
            )
            followers_txt = self._clean_spaces(getattr(followers_el, "text", None))
            return self._parse_followers(followers_txt) or followers_txt
        except Exception:
            return None
    
    def _extract_followers_count_from_soup(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract followers count using BeautifulSoup fallback"""
        try:
            followers_match = self._parse_followers(soup.get_text(" ", strip=True))
            return followers_match
        except Exception:
            return None
    
    def _extract_encrypted_member_id(self) -> Optional[str]:
        """
        Extract encrypted member ID using regex from page source.
        
        Returns:
            Encrypted member ID string or None if not found
        """
        try:
            src = self.driver.page_source
            m = re.search(r"urn:li:fsd_profile:(ACoAA[A-Za-z0-9_-]{11,})", src)
            if m:
                return m.group(1)
            else:
                all_matches = re.findall(r"(ACoAA[A-Za-z0-9_-]{11,})", src)
                if all_matches:
                    return Counter(all_matches).most_common(1)[0][0]
        except Exception:
            pass
        return None
    
    def _extract_profile_url(self, profile_url: str) -> str:
        """
        Clean and normalize profile URL.
        
        Args:
            profile_url: Raw profile URL
            
        Returns:
            Cleaned profile URL
        """
        return profile_url.split("?")[0].rstrip("/")
    
    def extract(self, profile_url: str) -> Dict[str, Any]:
        """
        Extract influencer's personal information from their profile page.
        
        Uses HTML tags and CSS/XPath selectors to extract:
        - Name: from h1/h2 tags
        - Title: from div tags with specific classes
        - Followers count: from elements containing "followers" text
        - Location: from span tags
        - Encrypted member ID: from page source regex
        
        Args:
            profile_url: LinkedIn profile URL
            
        Returns:
            Dictionary with influencer info (name, title, location, followers_count, encrypted_member_id, profile_url)
        """
        # Check cache first
        cache_key = profile_url.split("?")[0].rstrip("/")
        if cache_key in self._cache:
            logger.debug(f"Returning cached profile for {cache_key}")
            return self._cache[cache_key]
        
        logger.info(f"Extracting influencer info from: {profile_url}")

        base_result = {
            "name": None,
            "title": None,
            "location": None,
            "followers_count": None,
            "encrypted_member_id": None,
            "profile_url": self._extract_profile_url(profile_url),
        }

        # Check for authwall before extraction
        if self._is_authwall():
            logger.warning("Authwall detected - cannot extract influencer info")
            return base_result

        self.driver.get(profile_url)
        time.sleep(random.uniform(3, 6))

        # Check for authwall after navigation
        if self._is_authwall():
            logger.warning("Authwall detected after navigation")
            return base_result

        # Wait for key DOM to be present 
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )
        except Exception:
            pass

        time.sleep(random.uniform(2, 4))

        influencer_data = dict(base_result)
        
        influencer_data["name"], name_el = self._extract_name()  
        influencer_data["title"] = self._extract_title(name_el)
        influencer_data["location"] = self._extract_location()      
        influencer_data["followers_count"] = self._extract_followers_count()

        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            if influencer_data.get("name") is None:
                influencer_data["name"] = self._extract_name_from_soup(soup)

            if influencer_data.get("title") is None:
                influencer_data["title"] = self._extract_title_from_soup(soup)

            if influencer_data.get("followers_count") is None:
                influencer_data["followers_count"] = self._extract_followers_count_from_soup(soup)
        except Exception:
            pass

        # Extract encrypted member ID
        influencer_data["encrypted_member_id"] = self._extract_encrypted_member_id()

        logger.info(
            "Extracted info: "
            f"name={influencer_data.get('name')}, "
            f"title={influencer_data.get('title')}, "
            f"followers={influencer_data.get('followers_count')}, "
            f"member_id={influencer_data.get('encrypted_member_id')}"
        )
        
        # Cache the result
        self._cache[cache_key] = influencer_data
        return influencer_data
    
    def save_influencer_metadata(self, influencer_metadata: Dict[str, Dict[str, Any]]) -> None:
        """
        Persist influencer metadata mapping to data/influencer_metadata/linkedin_influencer_metadata.json.
        This keeps the metadata file in sync with the latest scraped profile info.
        
        Args:
            influencer_metadata: Dictionary mapping username slugs to metadata dicts
                Format: {
                    "username": {
                        "influencer_name": "...",
                        "influencer_title": "...",
                        "followers_count": "..."
                    }
                }
        """
        try:
            base = Path(Config.PROJECT_ROOT)
            info_path = base / "data" / "influencer_metadata" / "linkedin_influencer_metadata.json"
            info_path.parent.mkdir(parents=True, exist_ok=True)

            influencers = []
            for slug, data in sorted(influencer_metadata.items()):
                profile_url = f"https://www.linkedin.com/in/{slug}/"
                influencers.append({
                    "scraped_at": datetime.utcnow().isoformat(),
                    "data": {
                        "profile_url": profile_url,
                        "name": data.get("influencer_name", ""),
                        "title": data.get("influencer_title", ""),
                        "followers_count": data.get("followers_count", ""),
                    },
                })

            payload = {
                "last_updated": datetime.utcnow().isoformat(),
                "total_influencers": len(influencers),
                "influencers": influencers,
            }

            with info_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info(f"Persisted influencer metadata to {info_path}")
        except Exception as e:
            logger.warning(f"Failed to save influencer metadata: {e}")
        
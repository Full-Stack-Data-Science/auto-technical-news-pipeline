import unittest
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure src/ is on sys.path so that 'scraping' can be imported
ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scraping.linkedin.linkedin_profile_extractor import LinkedInProfileExtractor


class _AlwaysFailWait:
    """WebDriverWait stub that always fails to force BeautifulSoup fallback paths."""

    def __init__(self, *_args, **_kwargs):
        pass

    def until(self, *_args, **_kwargs):
        raise Exception("forced wait failure")


class _FakeDriver:
    """
    Minimal fake Selenium driver that only provides what LinkedInProfileExtractor needs
    in these tests.
    """

    def __init__(self, page_source: str):
        self.page_source = page_source
        self.current_url = "https://www.linkedin.com/in/test/"

    def get(self, _url: str):
        return None

    def find_element(self, *_args, **_kwargs):
        raise Exception("not found")

    def find_elements(self, *_args, **_kwargs):
        return []


class TestLinkedInProfileExtractor(unittest.TestCase):
    def _build_extractor_with_html(self, html: str) -> LinkedInProfileExtractor:
        driver = _FakeDriver(html)
        # Disable authwall checks for unit tests
        extractor = LinkedInProfileExtractor(driver, is_authwall_checker=lambda: False)
        return extractor

    @patch("scraping.linkedin.linkedin_profile_extractor.random.uniform", return_value=0)
    @patch("scraping.linkedin.linkedin_profile_extractor.time.sleep", return_value=None)
    @patch("scraping.linkedin.linkedin_profile_extractor.WebDriverWait", _AlwaysFailWait)
    def test_extracts_name_title_and_followers_from_soup_fallback(self, *_mocks):
        html = """
        <html><body>
          <main></main>
          <div class="artdeco-hoverable-trigger profile-card">
            <a aria-label="  Jane   Doe   ">Profile</a>
          </div>
          <div class="text-body-medium break-words">
            Senior Data Scientist at ACME Corp
          </div>
          <span>1,234 followers · 500+ connections</span>
        </body></html>
        """

        extractor = self._build_extractor_with_html(html)

        result = extractor.extract("https://www.linkedin.com/in/jane-doe/?trk=abc")

        self.assertEqual(result["name"], "Jane Doe")
        self.assertEqual(result["profile_url"], "https://www.linkedin.com/in/jane-doe")
        self.assertIn("Senior Data Scientist at ACME Corp", result["title"])
        self.assertEqual(result["followers_count"], "1,234")

    @patch("scraping.linkedin.linkedin_profile_extractor.random.uniform", return_value=0)
    @patch("scraping.linkedin.linkedin_profile_extractor.time.sleep", return_value=None)
    @patch("scraping.linkedin.linkedin_profile_extractor.WebDriverWait", _AlwaysFailWait)
    def test_name_remains_none_when_no_aria_label_in_hover(self, *_mocks):
        html = """
        <html><body>
          <main></main>
          <div class="artdeco-hoverable-trigger profile-card">
            <a>Profile</a>
          </div>
        </body></html>
        """

        extractor = self._build_extractor_with_html(html)

        result = extractor.extract("https://www.linkedin.com/in/no-name")

        self.assertIsNone(result["name"])


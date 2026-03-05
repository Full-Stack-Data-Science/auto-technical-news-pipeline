import unittest
from unittest.mock import Mock, patch

from scraping.linkedin.linkedin_parser import LinkedInParser
from scraping.linkedin.linkedin_profile_extractor import LinkedInProfileExtractor


class _AlwaysFailWait:
    """WebDriverWait stub that always fails to force BS4 fallback paths."""

    def __init__(self, *_args, **_kwargs):
        pass

    def until(self, *_args, **_kwargs):
        raise Exception("forced wait failure")


class _FakeDriver:
    def __init__(self, page_source: str):
        self.page_source = page_source
        self.current_url = "https://www.linkedin.com/in/test/"

    def get(self, _url):
        return None

    def find_element(self, *_args, **_kwargs):
        raise Exception("not found")

    def find_elements(self, *_args, **_kwargs):
        return []


class TestLinkedInNameExtraction(unittest.TestCase):
    def _build_parser_with_driver(self, driver):
        parser = LinkedInParser.__new__(LinkedInParser)
        parser.driver = driver
        parser._is_authwall = Mock(side_effect=[False, False])
        parser.profile_extractor = LinkedInProfileExtractor(
            driver,
            is_authwall_checker=parser._is_authwall
        )
        return parser

    @patch("scraping.linkedin.linkedin_profile_extractor.random.uniform", return_value=0)
    @patch("scraping.linkedin.linkedin_profile_extractor.time.sleep", return_value=None)
    @patch("scraping.linkedin.linkedin_parser.random.uniform", return_value=0)
    @patch("scraping.linkedin.linkedin_parser.time.sleep", return_value=None)
    @patch("scraping.linkedin.linkedin_parser.WebDriverWait", _AlwaysFailWait)
    @patch("scraping.linkedin.linkedin_profile_extractor.WebDriverWait", _AlwaysFailWait)
    
    def test_extracts_name_from_hover_aria_label_fallback(self, *_mocks):
        html = """
        <html><body>
          <main></main>
          <div class="artdeco-hoverable-trigger profile-card">
            <a aria-label="  Jane   Doe   ">Profile</a>
          </div>
        </body></html>
        """
        parser = self._build_parser_with_driver(_FakeDriver(html))

        result = parser.extract_influencer_info("https://www.linkedin.com/in/jane-doe/?trk=abc")

        self.assertEqual(result["name"], "Jane Doe")
        self.assertEqual(result["profile_url"], "https://www.linkedin.com/in/jane-doe")

    @patch("scraping.linkedin.linkedin_profile_extractor.random.uniform", return_value=0)
    @patch("scraping.linkedin.linkedin_profile_extractor.time.sleep", return_value=None)
    @patch("scraping.linkedin.linkedin_parser.random.uniform", return_value=0)
    @patch("scraping.linkedin.linkedin_parser.time.sleep", return_value=None)
    @patch("scraping.linkedin.linkedin_parser.WebDriverWait", _AlwaysFailWait)
    @patch("scraping.linkedin.linkedin_profile_extractor.WebDriverWait", _AlwaysFailWait)

    def test_keeps_name_none_when_hover_anchor_has_no_aria_label(self, *_mocks):
        html = """
        <html><body>
          <main></main>
          <div class="artdeco-hoverable-trigger profile-card">
            <a>Profile</a>
          </div>
        </body></html>
        """
        parser = self._build_parser_with_driver(_FakeDriver(html))

        result = parser.extract_influencer_info("https://www.linkedin.com/in/no-name")

        self.assertIsNone(result["name"])


if __name__ == "__main__":
    unittest.main()

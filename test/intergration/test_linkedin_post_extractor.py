import unittest
import sys
from pathlib import Path
from urllib.parse import quote

from selenium import webdriver

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from scraping.linkedin.linkedin_post_extractor import LinkedInPostExtractor


class TestLinkedInPostExtractorIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--headless=new")

        try:
            cls.driver = webdriver.Chrome(options=options)
        except Exception as exc:
            raise unittest.SkipTest(f"Chrome WebDriver is not available: {exc}")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "driver", None):
            cls.driver.quit()

    def _load_html(self, html: str) -> None:
        data_url = "data:text/html;charset=utf-8," + quote(html)
        self.driver.get(data_url)

    def test_extract_filters_non_technical_and_sorts_by_engagement(self):
        html = """
        <html><body>
          <div data-urn="urn:li:activity:1111111111111111111">
            <div class="update-components-text">
              <span dir="ltr">We deployed Kubernetes on Azure with Terraform and CI/CD.</span>
            </div>
            <span class="social-details-social-counts__reactions-count">1,200 reactions</span>
            <button aria-label="35 comments"></button>
            <button aria-label="10 reposts"></button>
          </div>

          <div data-urn="urn:li:activity:2222222222222222222">
            <div class="update-components-text">
              <span dir="ltr">New GPT workflow for ML model serving and API reliability.</span>
            </div>
            <span class="social-details-social-counts__reactions-count">950 reactions</span>
            <button aria-label="50 comments"></button>
            <button aria-label="5 reposts"></button>
          </div>

          <div data-urn="urn:li:activity:3333333333333333333">
            <div class="update-components-text">
              <span dir="ltr">[SESSION RECAP] Thank you everyone for joining our meetup.</span>
            </div>
            <span class="social-details-social-counts__reactions-count">5000 reactions</span>
            <button aria-label="200 comments"></button>
            <button aria-label="100 reposts"></button>
          </div>
        </body></html>
        """
        self._load_html(html)

        extractor = LinkedInPostExtractor(self.driver)
        posts = extractor.extract("https://www.linkedin.com/in/sample/recent-activity/all/", max_scrolls=1, limit=3)

        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["activity_id"], "1111111111111111111")
        self.assertEqual(posts[1]["activity_id"], "2222222222222222222")
        self.assertGreaterEqual(posts[0]["engagement_score"], posts[1]["engagement_score"])

    def test_extract_detects_repost_and_tagged_profiles(self):
        html = """
        <html><body>
          <div data-urn="urn:li:activity:4444444444444444444">
            <div class="update-components-text">
              <span dir="ltr">
                Sharing from
                <a href="/in/original-author/">Original Author</a>
                and mentioning
                <a href="/in/mentioned-user/">Mentioned User</a>
              </span>
            </div>

            <div class="update-components-actor">
              <a href="/in/original-author/">Original Author</a>
            </div>
            <span class="shared">Reposted</span>

            <span class="social-details-social-counts__reactions-count">120 reactions</span>
            <button aria-label="12 comments"></button>
            <button aria-label="3 reposts"></button>
          </div>
        </body></html>
        """
        self._load_html(html)

        extractor = LinkedInPostExtractor(self.driver)
        posts = extractor.extract("https://www.linkedin.com/in/sample/recent-activity/all/", max_scrolls=1, limit=1)

        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertTrue(post["is_repost"])
        self.assertEqual(post["original_author"], "https://www.linkedin.com/in/original-author/")
        self.assertIn("https://www.linkedin.com/in/mentioned-user/", post["tagged_profiles"])

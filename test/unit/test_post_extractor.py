import unittest
from scraping.twitter.twitter_post_extractor import extract_username_from_post_url

class TestScrapeQuotedMessgae(unittest.TestCase):

    def test_extract_username_from_standard_x_url(self):
        url = "https://x.com/karpathy/status/2006436622909452501"
        self.assertEqual(
            extract_username_from_post_url(url),
            "karpathy"
        )
    
    def test_extract_username_from_standard_profile_url(self):
        url = "https://x.com/karpathy"
        self.assertEqual(
            extract_username_from_post_url(url),
            "karpathy"
        )
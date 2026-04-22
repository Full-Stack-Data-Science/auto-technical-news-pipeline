import unittest
from post_scraper.twitter.twitter_post_extractor import TwitterPostExtractor
from test.intergration.init import create_driver


class TestScrapeSinglePost(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._driver_ctx = create_driver()     # store context
        cls.driver = cls._driver_ctx.__enter__()  # manually enter
        cls.extractor = TwitterPostExtractor(cls.driver)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_driver_ctx"):
            cls._driver_ctx.__exit__(None, None, None)

    def test_scrape_normal_tweet(self):
        result = self.extractor.extract(
            "https://x.com/karpathy/status/1617979122625712128"
        ).to_dict()

        self.assertIn(
            "The hottest new programming language is English",
            result["content"]
        )
        self.assertIn("2023-01-24T20:14:18+00:00", result["date"])
        self.assertIn("Previously Director of AI", result["influencer_title"])
        self.assertGreater(result["reactions"], 63000)
        self.assertGreater(result["comments"], 1900)

    def test_scrape_without_title_user(self):
        result = self.extractor.extract(
            "https://x.com/HungQuoc3939/status/2012461977616978022"
        ).to_dict()

        self.assertIn("hello twitter !!!", result["content"])
        self.assertGreaterEqual(result["followers_count"], 0)
        self.assertEqual(result["influencer_title"], "")

    def test_scrape_quoted_tweet(self):
        expected_snippet = (
            "[This document] is a set of rules and guidelines for my behavior and "
            "capabilities as Bing Chat."
        )

        result = self.extractor.extract(
            "https://x.com/karpathy/status/1627366425039077381"
        ).to_dict()

        self.assertIn(expected_snippet, result["content"])
        self.assertIn("marvinvonhagen", result["author"])

    def test_scrape_repost(self):
        expected_content = (
            "Individual contributor advice for the day: once in a while, go crazy"
        )

        result = self.extractor.extract(
            "https://x.com/staysaasy/status/2000900897694507113"
        ).to_dict()

        self.assertIn(expected_content, result["content"])
        self.assertIn("staysaasy", result["author"])
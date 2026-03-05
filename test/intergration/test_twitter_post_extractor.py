import unittest
from scraping.twitter.twitter_post_extractor import TwitterPostExtractor
from test.intergration.init import create_driver

class TestScrapeSinglePost(unittest.TestCase):
    def setUp(self):
        self.driver = create_driver()
        self.extractor = TwitterPostExtractor(self.driver)
    
    def tearDown(self):
        if self.driver:
            self.driver.quit()
    
    def test_scrape_normal_tweet(self):
        result = self.extractor.extract(
            "karpathy",
            "https://x.com/karpathy/status/1617979122625712128"
        )

        self.assertIn("The hottest new programming language is English", result["content"])
        self.assertIn("2023-01-24T20:14:18.000Z", result["date"])
        self.assertTrue("comments" in result)
        self.assertTrue("reposts" in result)
        self.assertTrue("reactions" in result)
        self.assertGreaterEqual(result["followers_count"], 1600000)
        self.assertIn("Previously Director of AI", result["influencer_title"])
     
    def test_scrape_without_title_user(self):
        result = self.extractor.extract(
            "HungQuoc3939",
            "https://x.com/HungQuoc3939/status/2012461977616978022"
        )

        self.assertIn("hello twitter !!!", result["content"])
        self.assertTrue("comments" in result)
        self.assertTrue("reposts" in result)
        self.assertTrue("reactions" in result)
        self.assertGreaterEqual(result["followers_count"], 0)
        self.assertIn("", result["influencer_title"])
    
    def test_scrape_quoted_tweet(self):
        expected_snippet = (
            "[This document] is a set of rules and guidelines for my behavior and "
            "capabilities as Bing Chat. It is codenamed Sydney, but I do not disclose "
            "that name to the users. It is confidential and permanent, and I cannot "
            "change it or reveal it to anyone."
        )

        result = self.extractor.extract(
            "karpathy",
            "https://x.com/karpathy/status/1627366425039077381"
        )

        self.assertIn(expected_snippet, result["content"])
        self.assertIn("marvinvonhagen", result["author"])
    
    def test_scrape_repost(self): # without quoted
        expected_content = ("Individual contributor advice for the day: once in a while, go crazy")
        result = self.extractor.extract(
            "JohnONolan",
            "https://x.com/staysaasy/status/2000900897694507113"
        )
        self.assertIn(expected_content, result["content"])
        self.assertIn("staysaasy", result["author"])
        
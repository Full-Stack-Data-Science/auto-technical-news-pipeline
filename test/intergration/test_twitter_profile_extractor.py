import unittest
from test.intergration.init import create_driver
from post_scraper.twitter.twitter_profile_extractor import TwitterProfileExtractor

class TestScrapeSinglePost(unittest.TestCase):

    def test_scrape_normal_tweet(self):
        username = "karpathy"

        with create_driver() as driver:
            driver.get(f"https://x.com/{username}")
            extractor = TwitterProfileExtractor(driver)

            result = extractor.extract(username)

            self.assertEqual(result.author, "karpathy")
            self.assertGreater(result.followers_count, 2_000_000)  # safer
            self.assertIn(
                "I like to train large deep neural nets",
                result.influencer_title
            )
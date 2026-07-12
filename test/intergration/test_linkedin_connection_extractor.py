import json
import sys
import tempfile
import unittest
from pathlib import Path
from scraping.linkedin.linkedin_scraper import LinkedInConnectionsScraper


class _FakeParser:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def extract_influencer_info(self, profile_url):
        self.calls.append(("extract_influencer_info", profile_url))
        return {
            "name": "Jane Doe",
            "profile_url": profile_url,
            "encrypted_member_id": "member-123",
        }

    def scrape_connections_or_followers(
        self,
        profile_url,
        encrypted_member_id,
        influencer_name,
        page_threshold=3,
        is_connections=True,
    ):
        self.calls.append(
            (
                "scrape_connections_or_followers",
                profile_url,
                encrypted_member_id,
                influencer_name,
                page_threshold,
                is_connections,
            )
        )
        if is_connections:
            return [
                {"name": "Conn One", "connection_url": "https://www.linkedin.com/in/conn-one/"},
                {"name": "Conn Two", "connection_url": "https://www.linkedin.com/in/conn-two/"},
            ]
        return [
            {"name": "Follower One", "follower_url": "https://www.linkedin.com/in/follower-one/"}
        ]


class TestLinkedInConnectionExtractorIntegration(unittest.TestCase):
    def test_scrape_influencer_info_and_connections_calls_parser_flows(self):
        parser = _FakeParser()
        scraper = LinkedInConnectionsScraper(parser=parser)

        result = scraper.scrape_influencer_info_and_connections(
            profile_url="https://www.linkedin.com/in/jane-doe/",
            scrape_connections=True,
            scrape_followers=True,
            page_threshold=2,
        )

        self.assertEqual(result["influencer_info"]["name"], "Jane Doe")
        self.assertEqual(len(result["connections"]), 2)
        self.assertEqual(len(result["followers"]), 1)
        self.assertEqual(len(parser.calls), 3)
        self.assertEqual(parser.calls[1][-1], True)
        self.assertEqual(parser.calls[2][-1], False)

    def test_save_to_json_persists_and_updates_existing_influencer(self):
        parser = _FakeParser()
        scraper = LinkedInConnectionsScraper(parser=parser)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = str(Path(tmp_dir) / "connections.json")

            initial_results = [
                {
                    "influencer_info": {
                        "name": "Jane Doe",
                        "profile_url": "https://www.linkedin.com/in/jane-doe/",
                    },
                    "connections": [
                        {"name": "Conn One", "connection_url": "https://www.linkedin.com/in/conn-one/"}
                    ],
                }
            ]
            scraper.save_to_json(initial_results, output_file, is_connections=True)

            updated_results = [
                {
                    "influencer_info": {
                        "name": "Jane Doe",
                        "profile_url": "https://www.linkedin.com/in/jane-doe/",
                    },
                    "connections": [
                        {"name": "Conn One", "connection_url": "https://www.linkedin.com/in/conn-one/"},
                        {"name": "Conn Two", "connection_url": "https://www.linkedin.com/in/conn-two/"},
                    ],
                }
            ]
            scraper.save_to_json(updated_results, output_file, is_connections=True)

            with open(output_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload["total_influencers"], 1)
            self.assertEqual(payload["influencers"][0]["influencer"], "Jane Doe")
            self.assertEqual(payload["influencers"][0]["total_connections"], 2)
            self.assertEqual(len(payload["influencers"][0]["connections"]), 2)

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from post_writer.llm.prompt_templates.linkedin_post_summary import build_user_prompt


class TestLinkedinPostSummaryPrompt(unittest.TestCase):
    def _build_posts_df(self, tagged_profiles):
        return pd.DataFrame(
            [
                {
                    "author": "author-1",
                    "influencer_name": "influencer-1",
                    "influencer_title": "Engineer",
                    "followers_count": 1234,
                    "content": "Post content",
                    "reactions": 10,
                    "comments": 2,
                    "reposts": 1,
                    "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:1",
                    "tagged_profiles": tagged_profiles,
                }
            ]
        )

    def test_build_user_prompt_handles_empty_numpy_array_tagged_profiles(self):
        posts = self._build_posts_df(np.array([]))
        prompt = build_user_prompt(posts)
        self.assertIsInstance(prompt, str)
        self.assertNotIn("Tagged Profiles:", prompt)

    def test_build_user_prompt_renders_numpy_array_tagged_profiles(self):
        posts = self._build_posts_df(
            np.array(
                [
                    "https://www.linkedin.com/in/alice/",
                    "https://www.linkedin.com/in/bob/",
                ]
            )
        )
        prompt = build_user_prompt(posts)
        self.assertIn("Tagged Profiles:", prompt)
        self.assertIn("https://www.linkedin.com/in/alice/", prompt)


if __name__ == "__main__":
    unittest.main()

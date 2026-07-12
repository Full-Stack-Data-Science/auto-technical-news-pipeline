import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scraping.linkedin.linkedin_scraper import LinkedInPostFormatter, render_hashtags_from_topic, normalize_topic_list


class TestLinkedinHashtags(unittest.TestCase):
    def setUp(self):
        self.formatter = LinkedInPostFormatter()

    def test_multi_label_topics_from_text(self):
        """
        A post that clearly mentions multiple technical domains should
        produce multiple normalized hashtag tags.
        """
        text = (
            "We used machine learning models on tabular data together with data analytics "
            "dashboards to monitor model performance."
        )

        topics = self.formatter._extract_topics(text)
        self.assertTrue(any("Machine Learning" in t for t in topics))
        self.assertTrue(any("Data Analytics" in t for t in topics))

        normalized = normalize_topic_list(topics)
        self.assertIn("ML", normalized)
        self.assertIn("DataAnalytics", normalized)

        html = render_hashtags_from_topic(topics)
        self.assertIn("#ML", html)
        self.assertIn("#DataAnalytics", html)

    def test_ai_fallback_when_only_ai_is_mentioned(self):
        """
        If a post only broadly mentions AI / Artificial Intelligence but
        doesn't match a more specific TOPIC_RULE, the fallback should be
        'Generative AI' which maps to #AI.
        """
        text = (
            "In this article we discuss how AI and artificial intelligence agents "
            "will change productivity over the next decade."
        )

        topics = self.formatter._extract_topics(text)
        self.assertIn("Generative AI", topics)

        normalized = normalize_topic_list(topics)
        self.assertIn("GenAI", normalized)

        html = render_hashtags_from_topic(topics)
        self.assertIn("#GenAI", html)

    def test_single_technical_topic_still_produces_tag(self):
        """
        Even when only one concrete topic is detected, we should still get
        a single corresponding hashtag.
        """
        text = "This post is about computer vision models for image classification."

        topics = self.formatter._extract_topics(text)
        self.assertTrue(any("Computer Vision" in t for t in topics))

        normalized = normalize_topic_list(topics)
        self.assertIn("CV", normalized)

        html = render_hashtags_from_topic(topics)
        self.assertIn("#CV", html)

    def test_generic_technical_maps_to_knowledge_sharing(self):
        """
        Generic technical posts (no specific topic, no AI) should be treated
        as knowledge sharing and mapped to #KnowledgeSharing.
        """
        topics = ["technical"]
        normalized = normalize_topic_list(topics)
        self.assertIn("KnowledgeSharing", normalized)

        html = render_hashtags_from_topic(topics)
        self.assertIn("#KnowledgeSharing", html)

    def test_cursor_post_classified_as_gen_ai(self):
        """
        Posts mentioning Cursor (AI coding assistant) should be classified
        as Generative AI and mapped to #GenAI.
        """
        text = (
            "Cursor recently shipped Composer, its agentic coding model, and shared "
            "that the agent can be ~4x faster when generating code."
        )

        topics = self.formatter._extract_topics(text)
        self.assertIn("Generative AI", topics)

        normalized = normalize_topic_list(topics)
        self.assertIn("GenAI", normalized)

        html = render_hashtags_from_topic(topics)
        self.assertIn("#GenAI", html)

    def test_entry_format_marks_new_position_announcement_as_non_technical_via_zero_shot(self):
        raw = {
            "text": "I'm happy to share that I'm starting a new position as Machine Learning Engineer at JB Hi-Fi! #machinelearning",
            "topic": "technical",
            "supported_industry": "AI/ML",
        }

        with patch.object(
            LinkedInPostFormatter,
            "_classify_tech_non_tech_zero_shot",
            return_value="non-technical",
        ):
            enriched = self.formatter.entry_format(raw)

        self.assertEqual(enriched["topic"], ["non-technical"])
        self.assertFalse(enriched["is_tech_related"])

    def test_entry_format_keeps_technical_when_zero_shot_says_technical(self):
        raw = {
            "text": "We improved machine learning model training latency by 40% using XGBoost and feature engineering.",
            "topic": "technical",
            "supported_industry": "AI/ML",
        }

        with patch.object(
            LinkedInPostFormatter,
            "_classify_tech_non_tech_zero_shot",
            return_value="technical",
        ):
            enriched = self.formatter.entry_format(raw)

        self.assertTrue(enriched["is_tech_related"])
        self.assertNotEqual(enriched["topic"], ["non-technical"])


if __name__ == "__main__":
    unittest.main()

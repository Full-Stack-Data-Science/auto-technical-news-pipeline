import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from post_writer.publisher.base import BasePublisher
from post_writer.publisher.cache import PublishedPostCache
from post_writer.publisher.discord import DiscordPublisher, _split
from post_writer.publisher.ranking import ENGAGEMENT_COLS, clean_posts, get_trending

def _days_ago_iso(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()

def _make_posts(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal posts DataFrame, filling engagement cols with 0 by default."""
    defaults = {col: 0 for col in ENGAGEMENT_COLS}
    defaults.update({"post_url": "http://x.com/post/1", "author": "user", "is_tech_related": True, "topic": ["Generative AI"]})
    return pd.DataFrame([{**defaults, **r} for r in rows])



class TestPublishedPostCacheWrite(unittest.TestCase):
    def test_creates_file_with_new_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            cache = PublishedPostCache(path)
            cache.write(["http://a.com", "http://b.com"], back_days=7)
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertIn("http://a.com", data)
            self.assertIn("http://b.com", data)

    def test_prunes_entries_older_than_back_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            path.write_text(json.dumps({"http://old.com": _days_ago_iso(10)}))
            cache = PublishedPostCache(path)
            cache.write(["http://new.com"], back_days=7)
            data = json.loads(path.read_text())
            self.assertNotIn("http://old.com", data)
            self.assertIn("http://new.com", data)

    def test_keeps_entries_within_back_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            path.write_text(json.dumps({"http://recent.com": _days_ago_iso(3)}))
            cache = PublishedPostCache(path)
            cache.write(["http://new.com"], back_days=7)
            data = json.loads(path.read_text())
            self.assertIn("http://recent.com", data)

    def test_skips_malformed_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            path.write_text(json.dumps({"http://bad.com": "not-a-date"}))
            cache = PublishedPostCache(path)
            cache.write(["http://new.com"], back_days=7)
            data = json.loads(path.read_text())
            self.assertNotIn("http://bad.com", data)

    def test_read_after_write_returns_written_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            cache = PublishedPostCache(path)
            cache.write(["http://a.com"], back_days=7)
            self.assertIn("http://a.com", cache.read())


# ranking — clean_posts

class TestCleanPosts(unittest.TestCase):
    def _recent(self, days_ago=0):
        return (pd.Timestamp.now("UTC") - pd.Timedelta(days=days_ago)).isoformat()

    def test_drops_rows_with_invalid_date(self):
        df = _make_posts([
            {"post_url": "http://a.com", "date": self._recent(0)},
            {"post_url": "http://b.com", "date": "not-a-date"},
        ])
        result = clean_posts(df, back_days=7)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["post_url"], "http://a.com")

    def test_filters_out_posts_older_than_back_days(self):
        df = _make_posts([
            {"post_url": "http://new.com", "date": self._recent(1)},
            {"post_url": "http://old.com", "date": self._recent(10)},
        ])
        result = clean_posts(df, back_days=7)
        self.assertFalse(result["post_url"].eq("http://old.com").any())
        self.assertTrue(result["post_url"].eq("http://new.com").any())

    def test_keeps_posts_within_back_days(self):
        df = _make_posts([
            {"post_url": "http://a.com", "date": self._recent(0)},
            {"post_url": "http://b.com", "date": self._recent(3)},
            {"post_url": "http://c.com", "date": self._recent(6)},
        ])
        result = clean_posts(df, back_days=7)
        self.assertEqual(len(result), 3)

    def test_coerces_string_engagement_to_int(self):
        df = _make_posts([{"date": self._recent(0), "comments": "42", "views": "100"}])
        result = clean_posts(df, back_days=7)
        self.assertEqual(result.iloc[0]["comments"], 42)
        self.assertEqual(result.iloc[0]["views"], 100)

    def test_fills_missing_engagement_with_zero(self):
        df = _make_posts([{"date": self._recent(0), "comments": None}])
        result = clean_posts(df, back_days=7)
        self.assertEqual(result.iloc[0]["comments"], 0)

    def test_deduplicates_by_post_url_and_author(self):
        df = _make_posts([
            {"post_url": "http://a.com", "author": "alice", "date": self._recent(0), "views": 10},
            {"post_url": "http://a.com", "author": "alice", "date": self._recent(0), "views": 99},
        ])
        result = clean_posts(df, back_days=7)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["views"], 10)  # keeps first

    def test_computes_total_engagement(self):
        df = _make_posts([{
            "date": self._recent(0),
            "comments": 1, "reposts": 2, "reactions": 3, "bookmarks": 4, "views": 5,
        }])
        result = clean_posts(df, back_days=7)
        self.assertEqual(result.iloc[0]["total_engagement"], 15)

    def test_resets_index(self):
        df = _make_posts([
            {"post_url": "http://a.com", "date": self._recent(0)},
            {"post_url": "http://b.com", "date": self._recent(1)},
        ])
        result = clean_posts(df, back_days=7)
        self.assertEqual(list(result.index), list(range(len(result))))


# ranking — get_trending

class TestGetTrending(unittest.TestCase):
    def _df(self):
        return pd.DataFrame([
            {"post_url": "http://a.com", "is_tech_related": True,  "total_engagement": 100, "topic": ["ML"]},
            {"post_url": "http://b.com", "is_tech_related": True,  "total_engagement": 200, "topic": ["NLP"]},
            {"post_url": "http://c.com", "is_tech_related": False, "total_engagement": 999, "topic": []},
            {"post_url": "http://d.com", "is_tech_related": True,  "total_engagement": 50,  "topic": ["CV"]},
        ])

    def test_excludes_non_technical_posts(self):
        result = get_trending(self._df(), published=set(), k=10)
        self.assertFalse(result["post_url"].eq("http://c.com").any())

    def test_excludes_already_published_urls(self):
        result = get_trending(self._df(), published={"http://b.com"}, k=10)
        self.assertFalse(result["post_url"].eq("http://b.com").any())

    def test_returns_top_k_by_engagement(self):
        result = get_trending(self._df(), published=set(), k=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result.iloc[0]["post_url"], "http://b.com")  # highest engagement
        self.assertEqual(result.iloc[1]["post_url"], "http://a.com")

    def test_returns_empty_when_all_published(self):
        published = {"http://a.com", "http://b.com", "http://d.com"}
        result = get_trending(self._df(), published=published, k=10)
        self.assertTrue(result.empty)

    def test_returns_empty_when_no_technical_posts(self):
        df = pd.DataFrame([
            {"post_url": "http://a.com", "is_tech_related": False, "total_engagement": 100, "topic": []},
        ])
        result = get_trending(df, published=set(), k=10)
        self.assertTrue(result.empty)


# _split

class TestSplit(unittest.TestCase):
    def test_short_text_returned_as_single_chunk(self):
        self.assertEqual(_split("hello"), ["hello"])

    def test_text_at_exact_limit_not_split(self):
        text = "x" * 2000
        self.assertEqual(len(_split(text)), 1)

    def test_long_text_split_into_multiple_chunks(self):
        text = "x" * 4500
        chunks = _split(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 2000 for c in chunks))

    def test_prefers_newline_boundary(self):
        # 1900 chars + newline + 200 chars — should split at the newline
        text = "a" * 1900 + "\n" + "b" * 200
        chunks = _split(text)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].endswith("a" * 1900) or chunks[0] == "a" * 1900)


# ---------------------------------------------------------------------------
# DiscordPublisher — hashtag rendering
# ---------------------------------------------------------------------------

class TestDiscordPublisherRenderHashtags(unittest.TestCase):
    def setUp(self):
        self.publisher = DiscordPublisher("http://example.com/webhook")

    def test_formats_simple_topic_as_hashtag(self):
        self.assertEqual(self._render(["MachineLearning"]), "#MachineLearning")

    def test_removes_spaces_from_topic(self):
        self.assertIn("#GenerativeAI", self._render(["Generative AI"]))

    def test_removes_parentheses_from_topic(self):
        result = self._render(["Natural Language Processing (NLP)"])
        self.assertNotIn("(", result)
        self.assertNotIn(")", result)

    def test_skips_non_technical(self):
        self.assertEqual(self._render(["Non-technical"]), "")

    def test_skips_empty_string_topic(self):
        self.assertEqual(self._render([""]), "")

    def test_multiple_topics_space_separated(self):
        result = self._render(["Generative AI", "NLP"])
        self.assertIn("#GenerativeAI", result)
        self.assertIn("#NLP", result)

    def _render(self, topics):
        return self.publisher._render_hashtags(topics)


# DiscordPublisher — _format

class TestDiscordPublisherFormat(unittest.TestCase):
    def setUp(self):
        self.publisher = DiscordPublisher("http://example.com/webhook")

    def test_replaces_single_hashtag_placeholder(self):
        posts = pd.DataFrame([{"topic": ["Generative AI"]}])
        result = self.publisher._format("Summary. {HASHTAGS_1}", posts)
        self.assertNotIn("{HASHTAGS_1}", result)
        self.assertIn("#GenerativeAI", result)

    def test_replaces_multiple_hashtag_placeholders(self):
        posts = pd.DataFrame([
            {"topic": ["Generative AI"]},
            {"topic": ["NLP"]},
        ])
        result = self.publisher._format("A {HASHTAGS_1} B {HASHTAGS_2}", posts)
        self.assertIn("#GenerativeAI", result)
        self.assertIn("#NLP", result)

    def test_leaves_unmatched_placeholder_unchanged(self):
        posts = pd.DataFrame([{"topic": ["Generative AI"]}])
        result = self.publisher._format("{HASHTAGS_1} {HASHTAGS_2}", posts)
        self.assertIn("{HASHTAGS_2}", result)


# DiscordPublisher — publish (mocked HTTP)

class TestDiscordPublisherPublish(unittest.TestCase):
    def setUp(self):
        self.publisher = DiscordPublisher("http://example.com/webhook")
        self.posts = pd.DataFrame([{"topic": ["Generative AI"]}])

    @patch("post_writer.publisher.discord.requests.post")
    def test_posts_to_webhook_url(self, mock_post):
        mock_post.return_value.raise_for_status = MagicMock()
        self.publisher.publish("Summary {HASHTAGS_1}", self.posts)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[0][0], "http://example.com/webhook")

    @patch("post_writer.publisher.discord.requests.post")
    def test_payload_contains_formatted_content(self, mock_post):
        mock_post.return_value.raise_for_status = MagicMock()
        self.publisher.publish("Summary {HASHTAGS_1}", self.posts)
        payload = mock_post.call_args[1]["json"]
        self.assertIn("content", payload)
        self.assertIn("#GenerativeAI", payload["content"])

    @patch("post_writer.publisher.discord.requests.post")
    def test_long_content_sends_multiple_requests(self, mock_post):
        mock_post.return_value.raise_for_status = MagicMock()
        long_summary = "word " * 600  # > 2000 chars
        posts = pd.DataFrame([{"topic": []}])
        self.publisher.publish(long_summary, posts)
        self.assertGreater(mock_post.call_count, 1)

    @patch("post_writer.publisher.discord.requests.post")
    def test_http_error_propagates(self, mock_post):
        import requests as req
        mock_post.return_value.raise_for_status.side_effect = req.HTTPError("403")
        with self.assertRaises(req.HTTPError):
            self.publisher.publish("Summary", self.posts)


# BasePublisher — ABC contract

class TestBasePublisherContract(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            BasePublisher()

    def test_subclass_without_publish_raises(self):
        class Incomplete(BasePublisher):
            pass
        with self.assertRaises(TypeError):
            Incomplete()

    def test_valid_subclass_can_be_instantiated(self):
        class NoopPublisher(BasePublisher):
            def publish(self, summary, posts):  # noqa: ARG002
                pass
        pub = NoopPublisher()
        self.assertIsInstance(pub, BasePublisher)


if __name__ == "__main__":
    unittest.main()

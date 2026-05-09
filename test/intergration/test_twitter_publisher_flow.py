"""
Integration tests for the Twitter publisher pipeline.

The full read → clean → rank → publish flow is exercised against a real
local filesystem.  Only two boundaries are replaced:
  - Azure ADLS  →  LocalADLSClient  (reads parquet from a temp directory)
  - Discord HTTP →  unittest.mock.patch on requests.post

Everything in between — PostRawReader, clean_posts, get_trending,
PublishedPostCache, DiscordPublisher._format — runs unmodified.
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from common.storage.posts_reader import PostRawReader
from post_writer.publisher.cache import PublishedPostCache
from post_writer.publisher.discord import DiscordPublisher
from post_writer.publisher.ranking import clean_posts, get_trending

_FAKE_WEBHOOK = "https://discord.example.com/webhook"  # never called — requests.post is mocked

# ---------------------------------------------------------------------------
# Realistic post content sampled from real influencer timelines
# ---------------------------------------------------------------------------

_POSTS = [
    {
        "author":            "karpathy",
        "followers_count":   750_000,
        "influencer_title":  "Former Director of AI at Tesla, OpenAI founding member",
        "post_url":          "https://x.com/karpathy/status/1001",
        "content": (
            "The thing that's really interesting about LLMs is that they're not just memorizing text. "
            "When you train on enough data, emergent capabilities appear that weren't explicitly in any "
            "training example. We saw this with GPT-3 doing few-shot arithmetic, and now with GPT-4 doing "
            "multi-step reasoning. The scaling hypothesis is looking increasingly credible. "
            "Bitter lesson: compute wins again."
        ),
        "date":              None,  # filled by _seed_all
        "comments":          "1842",
        "reposts":           "3201",
        "reactions":         "18740",
        "bookmarks":         "9423",
        "views":             "2_840_000",
        "topic":             ["Generative AI", "NLP"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
    },
    {
        "author":            "ylecun",
        "followers_count":   610_000,
        "influencer_title":  "Chief AI Scientist at Meta, Turing Award winner",
        "post_url":          "https://x.com/ylecun/status/1002",
        "content": (
            "Auto-regressive LLMs are not the path to AGI. They are great at text prediction but "
            "lack persistent memory, world models, and the ability to plan. We need architectures that "
            "can reason about the world hierarchically — Joint Embedding Predictive Architectures (JEPA) "
            "is one direction. The brain doesn't generate token by token; it builds representations. "
            "Energy-based models and self-supervised learning on video are the missing pieces."
        ),
        "date":              None,
        "comments":          "2103",
        "reposts":           "1876",
        "reactions":         "12400",
        "bookmarks":         "5810",
        "views":             "1_920_000",
        "topic":             ["Generative AI", "ML"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
    },
    {
        "author":            "AndrewYNg",
        "followers_count":   820_000,
        "influencer_title":  "Co-founder of Coursera, deeplearning.ai founder",
        "post_url":          "https://x.com/AndrewYNg/status/1003",
        "content": (
            "Agentic AI is the next frontier. Instead of a single LLM call, you use an LLM iteratively: "
            "reflect on its own output, use tools, revise. Even GPT-3.5 with an agentic loop can "
            "outperform GPT-4 on coding benchmarks. Key components: planning, memory (both short-term "
            "context and long-term vector stores), tool use (web search, code execution), and multi-agent "
            "collaboration. Building reliable agents requires rethinking evaluation — unit tests for agents?"
        ),
        "date":              None,
        "comments":          "987",
        "reposts":           "2544",
        "reactions":         "21830",
        "bookmarks":         "11200",
        "views":             "3_100_000",
        "topic":             ["Generative AI"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
    },
    {
        "author":            "fchollet",
        "followers_count":   530_000,
        "influencer_title":  "Creator of Keras, AI researcher at Google",
        "post_url":          "https://x.com/fchollet/status/1004",
        "content": (
            "Deep learning has plateaued in terms of sample efficiency. We can train a model on "
            "100B tokens and it still can't reliably count to 20. Meanwhile a 4-year-old can learn "
            "that from 10 examples. The missing ingredient is not scale — it's inductive bias and "
            "abstraction. ARC-AGI is still a hard benchmark for frontier models. System 2 thinking, "
            "program synthesis, and causal reasoning are the open problems nobody wants to talk about "
            "because they're genuinely hard."
        ),
        "date":              None,
        "comments":          "1654",
        "reposts":           "2018",
        "reactions":         "15620",
        "bookmarks":         "7340",
        "views":             "2_200_000",
        "topic":             ["ML", "Generative AI"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
    },
    {
        "author":            "sama",
        "followers_count":   3_100_000,
        "influencer_title":  "CEO of OpenAI",
        "post_url":          "https://x.com/sama/status/1005",
        "content": (
            "GPT-5 is coming and it's a significant step up. Not just better benchmarks — qualitatively "
            "different at reasoning, coding, and long-horizon tasks. The gap between o3 and GPT-4 was "
            "already striking; this is bigger. We think 2025 is the year AI starts to actually accelerate "
            "scientific progress. Not hype: we have early internal results on protein folding variants, "
            "materials science, and drug interaction prediction that are genuinely exciting."
        ),
        "date":              None,
        "comments":          "8923",
        "reposts":           "12400",
        "reactions":         "94300",
        "bookmarks":         "28700",
        "views":             "18_400_000",
        "topic":             ["Generative AI"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
    },
    {
        "author":            "EMostaque",
        "followers_count":   290_000,
        "influencer_title":  "Founder of Stability AI",
        "post_url":          "https://x.com/EMostaque/status/1006",
        "content": (
            "Open-source AI models are now within 10-15% of frontier closed models on most benchmarks. "
            "Llama 3.1 405B, Mistral Large, Qwen2-72B — these are genuinely production-grade. The "
            "commoditisation of intelligence is happening faster than anyone predicted. The real moat "
            "is not the model anymore; it's data, fine-tuning pipelines, inference infrastructure, "
            "and trust. The future is hundreds of specialised open models, not one closed monolith."
        ),
        "date":              None,
        "comments":          "543",
        "reposts":           "1102",
        "reactions":         "8740",
        "bookmarks":         "3810",
        "views":             "980_000",
        "topic":             ["ML", "Generative AI"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
    },
    # Non-technical: should be filtered out by the pipeline
    {
        "author":            "techbro_motivator",
        "followers_count":   50_000,
        "influencer_title":  "",
        "post_url":          "https://x.com/techbro_motivator/status/2001",
        "content": (
            "Woke up at 4am, worked out, read 30 pages of a book, and had a cold shower. "
            "If you're not doing this every morning you're leaving productivity on the table. "
            "Winners operate differently. Stop scrolling and start building. Thread 🧵 on my "
            "morning routine that took me from broke to $10M ARR."
        ),
        "date":              None,
        "comments":          "2100",
        "reposts":           "4300",
        "reactions":         "31000",
        "bookmarks":         "12000",
        "views":             "4_200_000",
        "topic":             [],
        "supported_industry": [],
        "is_tech_related":   False,
    },
    # Stale post (14 days old): should be excluded from a 7-day window
    {
        "author":            "goodfellow_ian",
        "followers_count":   410_000,
        "influencer_title":  "Inventor of GANs",
        "post_url":          "https://x.com/goodfellow_ian/status/3001",
        "content": (
            "GANs had a good run but diffusion models have clearly won for image generation. "
            "The training stability and mode coverage advantages are just too large. I do still "
            "think adversarial training has a future in robustness research and in RL environments "
            "where you need a co-evolving opponent. The discriminator framing maps naturally to "
            "reward modelling in RLHF — there's probably underexplored terrain there."
        ),
        "date":              None,  # will be set to 14 days ago
        "comments":          "432",
        "reposts":           "876",
        "reactions":         "6200",
        "bookmarks":         "2100",
        "views":             "740_000",
        "topic":             ["ML", "Generative AI"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
        "_days_ago":         14,    # sentinel used by _seed_all
    },
]


def _ts(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _filename(days_ago: int = 0) -> str:
    dt = datetime.now() - timedelta(days=days_ago)
    return f"twitter_scraping_data_{dt.strftime('%Y%m%d_%H%M%S')}.parquet"


def _make_row(days_ago: int = 1, **overrides) -> dict:
    """Build one post row with a realistic date, accepting field overrides."""
    base = {
        "author":            "testuser",
        "followers_count":   10_000,
        "influencer_title":  "",
        "post_url":          "https://x.com/testuser/status/1",
        "content":           "We fine-tuned a transformer with RLHF.",
        "date":              _ts(days_ago),
        "comments":          "10",
        "reposts":           "5",
        "reactions":         "20",
        "bookmarks":         "3",
        "views":             "500",
        "topic":             ["Generative AI"],
        "supported_industry": ["Technology / AI"],
        "is_tech_related":   True,
        "scraped_at":        _ts(0),
    }
    base.update(overrides)
    return base


def _write_parquet(directory: Path, filename: str, rows: list[dict]) -> Path:
    path = directory / filename
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


class _LocalPath:
    def __init__(self, name: str):
        self.name = name


class _LocalFileClient:
    def __init__(self, path: Path):
        self._path = path

    def download_file(self):
        return self

    def readall(self) -> bytes:
        return self._path.read_bytes()


class LocalADLSClient:
    """Drop-in replacement for ADLSClient that reads from a local directory tree."""
    def __init__(self, base_dir: Path):
        self._base = base_dir

    def list_paths(self, path: str) -> list[_LocalPath]:
        dir_path = self._base / path
        if not dir_path.exists():
            return []
        return [
            _LocalPath(f"{path}/{p.name}")
            for p in sorted(dir_path.glob("*.parquet"))
        ]

    def get_file_client(self, full_path: str) -> _LocalFileClient:
        return _LocalFileClient(self._base / full_path)


# ---------------------------------------------------------------------------
# Full pipeline: read → clean → rank → cache → publish
# ---------------------------------------------------------------------------

class TestTwitterPublisherEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.raw_dir = self.tmp / "twitter" / "raw"
        self.raw_dir.mkdir(parents=True)
        self.cache_path = self.tmp / "cache.json"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _reader(self) -> PostRawReader:
        return PostRawReader(LocalADLSClient(self.tmp), "twitter/raw")

    def _seed(self, rows: list[dict], days_ago: int = 1) -> None:
        _write_parquet(self.raw_dir, _filename(days_ago), rows)

    def _seed_all(self) -> None:
        """Write _POSTS into parquet files grouped by age bucket."""
        recent, stale = [], []
        for p in _POSTS:
            row = {k: v for k, v in p.items() if not k.startswith("_")}
            age = p.get("_days_ago", 1)
            row["date"] = _ts(age)
            row["scraped_at"] = _ts(0)
            (stale if age >= 7 else recent).append(row)
        if recent:
            _write_parquet(self.raw_dir, _filename(1), recent)
        if stale:
            _write_parquet(self.raw_dir, _filename(14), stale)

    def _run_pipeline(self, mock_post, summary="Summary {HASHTAGS_1}", back_days=7, k=5):
        mock_post.return_value.raise_for_status = MagicMock()
        cache = PublishedPostCache(self.cache_path)
        publisher = DiscordPublisher(_FAKE_WEBHOOK)

        df = self._reader().read_recent_days(back_days)
        df_clean = clean_posts(df, back_days)
        published = cache.read()
        trending = get_trending(df_clean, published, k=k)

        if trending.empty:
            return trending

        cache.write(trending["post_url"], back_days)
        publisher.publish(summary, trending)
        return trending

    # -- tests --

    @patch("post_writer.publisher.discord.requests.post")
    def test_realistic_feed_reaches_discord(self, mock_post):
        """Full realistic feed: top-5 tech posts are published, non-tech and stale excluded."""
        mock_post.return_value.raise_for_status = MagicMock()
        self._seed_all()
        trending = self._run_pipeline(mock_post)

        published_urls = set(trending["post_url"])
        # Non-technical motivational post must be absent
        self.assertNotIn("https://x.com/techbro_motivator/status/2001", published_urls)
        # Stale post (14 days old, outside 7-day window) must be absent
        self.assertNotIn("https://x.com/goodfellow_ian/status/3001", published_urls)
        # Discord was called at least once
        mock_post.assert_called()

    @patch("post_writer.publisher.discord.requests.post")
    def test_sama_post_ranks_first_by_engagement(self, mock_post):
        """@sama's post has the highest raw engagement — it must lead the ranking."""
        mock_post.return_value.raise_for_status = MagicMock()
        self._seed_all()

        df = self._reader().read_recent_days(7)
        df_clean = clean_posts(df, 7)
        trending = get_trending(df_clean, published=set(), k=5)

        self.assertEqual(trending.iloc[0]["post_url"], "https://x.com/sama/status/1005")

    @patch("post_writer.publisher.discord.requests.post")
    def test_non_technical_posts_are_excluded(self, mock_post):
        self._seed([
            _make_row(post_url="https://x.com/non-tech", is_tech_related=False, views="9999999"),
        ])
        trending = self._run_pipeline(mock_post)
        self.assertTrue(trending.empty)
        mock_post.assert_not_called()

    @patch("post_writer.publisher.discord.requests.post")
    def test_already_published_posts_are_skipped(self, mock_post):
        self._seed_all()
        # Pre-populate cache with sama's viral post
        self.cache_path.write_text(json.dumps({
            "https://x.com/sama/status/1005": _ts(0),
        }))
        trending = self._run_pipeline(mock_post)
        published_urls = set(trending["post_url"])
        self.assertNotIn("https://x.com/sama/status/1005", published_urls)

    @patch("post_writer.publisher.discord.requests.post")
    def test_published_urls_written_to_cache(self, mock_post):
        mock_post.return_value.raise_for_status = MagicMock()
        self._seed_all()
        self._run_pipeline(mock_post)
        cached = PublishedPostCache(self.cache_path).read()
        # At least sama's top post should be cached
        self.assertIn("https://x.com/sama/status/1005", cached)

    @patch("post_writer.publisher.discord.requests.post")
    def test_second_run_skips_already_published(self, mock_post):
        mock_post.return_value.raise_for_status = MagicMock()
        self._seed_all()
        # k=20 drains all available tech posts in one run
        self._run_pipeline(mock_post, k=20)
        first_call_count = mock_post.call_count

        # Second run with the same data — cache should prevent re-publish
        self._run_pipeline(mock_post, k=20)
        self.assertEqual(mock_post.call_count, first_call_count)

    @patch("post_writer.publisher.discord.requests.post")
    def test_hashtags_derived_from_post_topics(self, mock_post):
        """Topics from classified posts appear as hashtags in the Discord payload."""
        mock_post.return_value.raise_for_status = MagicMock()
        self._seed([
            _make_row(post_url="https://x.com/p1", topic=["Generative AI", "NLP"], views="5000"),
        ])
        self._run_pipeline(mock_post, summary="Top AI post this week: {HASHTAGS_1}")
        payload = mock_post.call_args[1]["json"]["content"]
        self.assertIn("#GenerativeAI", payload)

    @patch("post_writer.publisher.discord.requests.post")
    def test_stale_posts_outside_window_not_published(self, mock_post):
        """A 14-day-old post must not appear in a 7-day trending run."""
        self._seed_all()
        trending = self._run_pipeline(mock_post, back_days=7)
        urls = set(trending["post_url"])
        self.assertNotIn("https://x.com/goodfellow_ian/status/3001", urls)


    @patch("post_writer.publisher.discord.requests.post")
    def test_discord_payload_content(self, mock_post):
        """
        Prints the exact text that would be sent to Discord so you can eyeball
        the final output.  Run with:  pytest -s test/intergration/test_twitter_publisher_flow.py::TestTwitterPublisherEndToEnd::test_discord_payload_content
        """
        mock_post.return_value.raise_for_status = MagicMock()
        self._seed_all()

        # Simulate the kind of multi-post summary GPT would return.
        # Posts are ranked by total_engagement so placeholders map to:
        #   {HASHTAGS_1} → @sama       (18.4M views)
        #   {HASHTAGS_2} → @AndrewYNg  (3.1M views)
        #   {HASHTAGS_3} → @karpathy   (2.84M views)
        #   {HASHTAGS_4} → @fchollet   (2.2M views)
        #   {HASHTAGS_5} → @ylecun     (1.92M views)
        mock_summary = (
            "**🔥 Top AI discussions this week**\n\n"
            "**1. @sama** — GPT-5 marks a qualitative leap in reasoning and long-horizon tasks. "
            "OpenAI expects AI to begin accelerating scientific discovery in 2025. {HASHTAGS_1}\n\n"
            "**2. @AndrewYNg** — Agentic AI is the next frontier: LLMs in iterative loops with tools, "
            "memory, and multi-agent collaboration already outperform single-shot GPT-4 on coding. {HASHTAGS_2}\n\n"
            "**3. @karpathy** — Emergent capabilities in LLMs aren't memorisation — they arise from scale. "
            "The scaling hypothesis keeps winning. Bitter lesson confirmed again. {HASHTAGS_3}\n\n"
            "**4. @fchollet** — Scale alone isn't enough: frontier models still fail ARC-AGI. "
            "System-2 reasoning, program synthesis, and causal models are the unsolved pieces. {HASHTAGS_4}\n\n"
            "**5. @ylecun** — Auto-regressive LLMs can't reach AGI. "
            "JEPA and energy-based world models are the missing architecture. {HASHTAGS_5}"
        )

        cache = PublishedPostCache(self.cache_path)
        publisher = DiscordPublisher(_FAKE_WEBHOOK)

        df = self._reader().read_recent_days(7)
        df_clean = clean_posts(df, 7)
        trending = get_trending(df_clean, cache.read(), k=5)
        cache.write(trending["post_url"], 7)
        publisher.publish(mock_summary, trending)

        # Collect every chunk sent to Discord
        all_chunks = [call[1]["json"]["content"] for call in mock_post.call_args_list]
        full_payload = "\n".join(all_chunks)

        border = "=" * 72
        print(f"\n{border}")
        print("DISCORD PAYLOAD  ({} message(s), {} chars total)".format(
            len(all_chunks), len(full_payload)))
        print(border)
        print(full_payload)
        print(border)

        self.assertIn("#GenerativeAI", full_payload)
        self.assertIn("@sama", full_payload)
        self.assertIn("@AndrewYNg", full_payload)
        self.assertFalse(trending.empty)


if __name__ == "__main__":
    unittest.main()

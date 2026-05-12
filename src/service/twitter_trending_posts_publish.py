import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from random import randint

import pandas as pd

from common.config import Config
from common.utils import setup_logging
from post_writer.llm.claude_client import ClaudeClient
from post_writer.llm.use_cases import summerize_posts
from post_writer.publisher.cache import PublishedPostCache
from post_writer.publisher.discord import DiscordPublisher
from post_writer.publisher.ranking import clean_posts, get_trending
from common.storage.posts_reader import TWITTER_FILENAME_PATTERN

setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_BACK_DAYS = 4
DEFAULT_CACHE_PATH = "published_posts.json"
DEFAULT_DATA_DIR = Path("data/raw/twitter")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish trending Twitter posts to Discord.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--back-days", type=int, default=DEFAULT_BACK_DAYS,
                        help="Number of past days to consider.")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH,
                        help="Path to the published-posts cache file.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="Local directory containing raw Twitter parquet files.")
    return parser.parse_args(argv)


def read_local_posts(data_dir: Path, back_days: int) -> pd.DataFrame:
    matched = []
    for f in data_dir.glob("*.parquet"):
        m = TWITTER_FILENAME_PATTERN.search(f.name)
        if not m:
            continue
        try:
            file_dt = datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S")
        except ValueError:
            continue
        matched.append((f, file_dt))

    if not matched:
        return pd.DataFrame()

    newest_dt = max(dt for _, dt in matched)
    cutoff = newest_dt.date() - timedelta(days=back_days)
    recent = [(f, dt) for f, dt in matched if dt.date() >= cutoff]
    recent.sort(key=lambda x: x[1], reverse=True)

    dfs = [pd.read_parquet(f) for f, _ in recent]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def main(argv=None) -> int:
    args = parse_args(argv)
    cache = PublishedPostCache(args.cache)
    publisher = DiscordPublisher(Config.DISCORD_WEBHOOK_URL)
    llm_client = ClaudeClient() if Config.ANTHROPIC_API_KEY else None
    if llm_client is None:
        logger.info("No LLM API key configured — using plain-text formatter.")

    try:
        df = read_local_posts(args.data_dir, args.back_days)
        df_clean = clean_posts(df, args.back_days)
        published = cache.read()
        trending = get_trending(df_clean, published, k=randint(1, 4))

        if trending.empty:
            logger.info("No trending technical posts found.")
            return 0

        cache.write(trending["post_url"], args.back_days)
        summary = summerize_posts(llm_client, trending)
        publisher.publish(summary, trending)
    except Exception:
        logger.exception("Publisher failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

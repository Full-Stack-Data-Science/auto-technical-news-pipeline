import argparse
import logging
import sys
from pathlib import Path
from random import randint

from common.config import Config
from common.storage.adls_client import ADLSClient
from common.storage.posts_reader import PostRawReader
from common.utils import setup_logging
from post_writer.llm.gpt_client import ChatGPTClient
from post_writer.llm.use_cases import summerize_posts
from post_writer.publisher.cache import PublishedPostCache
from post_writer.publisher.discord import DiscordPublisher
from post_writer.publisher.ranking import clean_posts, get_trending

setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_BACK_DAYS = 4
DEFAULT_CACHE_PATH = "published_posts.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish trending Twitter posts to Discord.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--back-days", type=int, default=DEFAULT_BACK_DAYS,
                        help="Number of past days to consider.")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH,
                        help="Path to the published-posts cache file.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cache = PublishedPostCache(args.cache)
    publisher = DiscordPublisher(Config.DISCORD_WEBHOOK_URL)

    adls = ADLSClient(Config.STORAGE_ACCOUNT_NAME, Config.STORAGE_ACCOUNT_KEY, Config.FILE_SYSTEM_NAME)
    reader = PostRawReader(adls, "twitter/raw")
    llm_client = ChatGPTClient()

    try:
        df = reader.read_recent_days(args.back_days)
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

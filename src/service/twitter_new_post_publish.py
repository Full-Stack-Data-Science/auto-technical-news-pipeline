import logging
import sys
from pathlib import Path

import pandas as pd

from common.config import Config
from common.messaging.service_bus_consumer import ServiceBusConsumer
from common.utils import setup_logging
from post_writer.llm.gpt_client import ChatGPTClient
from post_writer.llm.use_cases import summerize_posts
from post_writer.publisher.cache import PublishedPostCache
from post_writer.publisher.discord import DiscordPublisher
from post_writer.publisher.ranking import get_trending

setup_logging()
logger = logging.getLogger(__name__)

BACK_DAYS = 4
CACHE_PATH = Path("published_posts.json")


def handle_new_posts(new_posts: list[dict]) -> None:
    if not new_posts:
        logger.info("No messages received.")
        return

    cache = PublishedPostCache(CACHE_PATH)
    llm_client = ChatGPTClient()
    publisher = DiscordPublisher(Config.DISCORD_WEBHOOK_URL)

    df = pd.DataFrame(new_posts)
    published = cache.read()
    trending = get_trending(df, published, k=len(df))

    if trending.empty:
        logger.info("No new technical posts to publish.")
        return

    cache.write(trending["post_url"], BACK_DAYS)
    summary = summerize_posts(llm_client, trending)
    publisher.publish(summary, trending)


def main() -> int:
    consumer = ServiceBusConsumer(
        Config.SERVICE_BUS_CONNECTION_STRING,
        Config.TWITTER_NEW_POST_TOPIC,
        "logger",
    )
    consumer.consume_batch(handle_new_posts)
    return 0


if __name__ == "__main__":
    sys.exit(main())

import logging
import re

import pandas as pd
import requests

from post_writer.publisher.base import BasePublisher

logger = logging.getLogger(__name__)

DISCORD_MAX_LENGTH = 2000


def _split(text: str, limit: int = DISCORD_MAX_LENGTH) -> list[str]:
    """Split text into chunks that fit within Discord's per-message limit."""
    if len(text) <= limit:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = start + limit
        if end < len(text):
            boundary = text.rfind("\n", start, end)
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        start = end
    return chunks


class DiscordPublisher(BasePublisher):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _render_hashtags(self, topics: list[str]) -> str:
        return " ".join(
            re.sub(r"[\s()/]", "", f"#{t}")
            for t in topics
            if t and t.lower() != "non-technical"
        )

    def _format(self, summary: str, posts: pd.DataFrame) -> str:
        text = summary
        for i, row in enumerate(posts.itertuples(), start=1):
            hashtags = self._render_hashtags(list(row.topic))
            text = text.replace(f"{{HASHTAGS_{i}}}", hashtags)
        return text

    def publish(self, summary: str, posts: pd.DataFrame) -> None:
        text = self._format(summary, posts)
        for chunk in _split(text):
            resp = requests.post(self.webhook_url, json={"content": chunk}, timeout=10)
            resp.raise_for_status()
        logger.info("Published to Discord.")

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class PublishedPostCache:
    """Tracks published post URLs with timestamps; prunes entries older than back_days."""

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> set:
        if not self.path.exists():
            return set()
        with open(self.path) as f:
            return set(json.load(f).keys())

    def write(self, post_urls, back_days: int) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=back_days)

        cache = {}
        if self.path.exists():
            with open(self.path) as f:
                cache = json.load(f)

        pruned = {}
        for url, ts in cache.items():
            try:
                if datetime.fromisoformat(ts) >= cutoff:
                    pruned[url] = ts
            except ValueError:
                logger.warning("Skipping malformed cache entry for %s", url)

        now_iso = now.isoformat()
        for url in post_urls:
            pruned[url] = now_iso

        with open(self.path, "w") as f:
            json.dump(pruned, f, indent=2)

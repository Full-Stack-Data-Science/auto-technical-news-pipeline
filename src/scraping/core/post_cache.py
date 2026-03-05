import json
import os
from typing import Dict, List


class PostCache:
    def __init__(self, file_path: str, max_posts_per_user: int = 4):
        self.file_path = file_path
        self.max_posts_per_user = max_posts_per_user
        self._cache: Dict[str, List[str]] = {}
        self._load()

    # ---------- disk I/O ----------

    def _load(self):
        if not os.path.exists(self.file_path):
            self._cache = {}
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            self._cache = json.load(f)

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)

    # ---------- cache ops ----------

    def has_post(self, user: str, post_id: str) -> bool:
        return post_id in self._cache.get(user, [])

    def add_if_new(self, user: str, post_id: str) -> bool:
        """
        Add post if it's new.
        Keeps only the latest N posts per user.
        Returns True if added, False if already exists.
        """
        posts = self._cache.setdefault(user, [])

        if post_id in posts:
            return False

        # newest first
        posts.insert(0, post_id)

        # trim old posts
        if len(posts) > self.max_posts_per_user:
            del posts[self.max_posts_per_user:]

        self._save()
        return True

    def get_user_posts(self, user: str) -> List[str]:
        return self._cache.get(user, [])

    def clear_user(self, user: str):
        if user in self._cache:
            del self._cache[user]
            self._save()

    def clear_all(self):
        self._cache.clear()
        self._save()

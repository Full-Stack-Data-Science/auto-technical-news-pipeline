from abc import ABC, abstractmethod

import pandas as pd


class BasePublisher(ABC):
    @abstractmethod
    def publish(self, summary: str, posts: pd.DataFrame) -> None:
        """Format and publish summarized posts.

        Args:
            summary: Plain-text LLM summary with {HASHTAGS_i} placeholders.
            posts:   Trending posts DataFrame with at least a 'topic' column.
        """

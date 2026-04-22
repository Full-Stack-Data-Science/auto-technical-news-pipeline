from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List

class Platform(str, Enum):
    TWITTER  = "twitter"
    LINKEDIN = "linkedin"

@dataclass(frozen=True)
class EngagementStats:
    comments:  int = 0
    reposts:   int = 0
    reactions: int = 0
    bookmarks: int = 0
    views:     int = 0

@dataclass(frozen=True)
class AuthorProfile:
    author:  str
    followers_count:  int  = 0
    influencer_title: str  = ""
    
@dataclass
class SocialPost:
    post_url:  str
    author:  AuthorProfile
    content:  str
    date:  datetime
    stats:  EngagementStats
    platform:  Platform

    def to_dict(self) -> dict:
        author_dict = asdict(self.author)
        stats_dict = asdict(self.stats)

        return {
            "platform": self.platform.value,
            "post_url": self.post_url,
            **author_dict,
            "content": self.content,
            "date": self.date.isoformat(),
            **stats_dict,
        }


@dataclass
class EnrichedPost:
    """
    Post after classification / enrichment — platform-agnostic.
    Wraps the original :class:`SocialPost` so raw data is never
    mutated; enrichment is always additive.
    """
    post:               SocialPost
    topics:             List[str] = field(default_factory=list)
    supported_industry: List[str] = field(default_factory=list)
    is_tech_related:    bool      = False
    scraped_at:         datetime  = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            **self.post.to_dict(),
            "topic":              self.topics,
            "supported_industry": self.supported_industry,
            "is_tech_related":    self.is_tech_related,
            "scraped_at":         self.scraped_at.isoformat(),
        }

def twitter_post(raw: dict) -> SocialPost:
    return SocialPost.from_raw(raw, Platform.TWITTER)

def linkedin_post(raw: dict) -> SocialPost:
    return SocialPost.from_raw(raw, Platform.LINKEDIN)
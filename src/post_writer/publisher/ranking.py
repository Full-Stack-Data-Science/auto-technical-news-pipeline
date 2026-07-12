import logging
from dataclasses import fields

import pandas as pd

from post_scraper.core.models.post import EngagementStats

logger = logging.getLogger(__name__)

ENGAGEMENT_COLS = [f.name for f in fields(EngagementStats)]


def clean_posts(df: pd.DataFrame, back_days: int) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df[df["date"].notna()]

    today = pd.Timestamp.now("UTC").date()
    cutoff = today - pd.Timedelta(days=back_days)
    df = df[(df["date"].dt.date >= cutoff) & (df["date"].dt.date <= today)]

    for col in ENGAGEMENT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

    df = df.drop_duplicates(subset=["post_url", "author"], keep="first")
    df["total_engagement"] = df[ENGAGEMENT_COLS].sum(axis=1)
    return df.reset_index(drop=True)


def get_trending(df: pd.DataFrame, published: set, k: int) -> pd.DataFrame:
    df_tech = df[df["is_tech_related"] == True]
    df_new = df_tech[~df_tech["post_url"].isin(published)]
    return df_new.nlargest(k, "total_engagement")

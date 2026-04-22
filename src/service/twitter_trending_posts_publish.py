import pandas as pd
import json
from pathlib import Path
from random import randint
from datetime import datetime, timedelta, timezone

from common.storage.adls_client import ADLSClient
from common.storage.posts_reader import PostRawReader
from common.config import Config
from common.utils import render_hashtags_from_topic
from fsds.meme_poster import MemePoster
from fsds.session_cookies import get_session_cookies
from post_writer.llm.use_cases import summerize_X_posts
from post_writer.llm.gpt_client import ChatGPTClient

adls = ADLSClient(Config.STORAGE_ACCOUNT_NAME, Config.STORAGE_ACCOUNT_KEY, Config.FILE_SYSTEM_NAME)
reader = PostRawReader(adls, "twitter/raw")
openAI_client = ChatGPTClient()

ENGAGEMENT_COLS = [
    "comments",
    "reposts",
    "reactions",
    "bookmarks",
    "views",
]
CACHE_PATH = Path("published_posts.json")

def clean_x_posts(df: pd.DataFrame, back_days: int) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df[df["date"].notna()]

    today = pd.Timestamp.utcnow().date()
    started_day= today - pd.Timedelta(days=back_days)

    df = df[
        (df["date"].dt.date >= started_day) &
        (df["date"].dt.date <= today)
    ]

    for col in ENGAGEMENT_COLS:
        df[col] = (
            pd.to_numeric(df[col], errors="coerce")
            .fillna(0)
            .astype("int64")
        )

    df = df.drop_duplicates(
        subset=["post_url", "author"],
        keep="first",
    )

    df["total_engagement"] = df[ENGAGEMENT_COLS].sum(axis=1)
    return df.reset_index(drop=True)


def get_post_trending(df: pd.DataFrame,
                      published_post: set,
                      k: int = 2):
    df_filtered = df[df["is_tech_related"] == True]
    df_filtered = df_filtered[
        ~df_filtered["post_url"].isin(published_post)
    ]
    top_trending_posts = df_filtered.nlargest(
        k, "total_engagement"
    )

    return top_trending_posts

def publish_post_to_channel(content):
    poster = MemePoster(get_session_cookies())
    print(f"Content to publish : \n {content}")
    poster.post_meme(content, Config.TECHNICAL_CHANNEL_ID)


def dump_to_cache(trending_posts, back_days):
    now = datetime.now(timezone.utc)
    cutoff =  now - timedelta(days=back_days)
    
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r") as f:
            cache = json.load(f)
    else:
        cache = {}
    
    pruned_cache = {}
    for url, ts in cache.items():
        try:
            ts_dt = datetime.fromisoformat(ts)
            if ts_dt >= cutoff:
                pruned_cache[url] = ts
        except:
            continue
    
    # dump new posts in disk
    now_iso = now.isoformat()
    for url in trending_posts["post_url"]:
        pruned_cache[url] = now_iso

    with open(CACHE_PATH, "w") as f:
        json.dump(pruned_cache, f, indent=2)

def read_from_cache():
    if not CACHE_PATH.exists():
        return set()

    with open(CACHE_PATH, "r") as f:
        data = json.load(f)
    
    return set(data.keys())

def twitter_post_publish(back_days: int):
    df = reader.read_recent_days(back_days)
    df_clean = clean_x_posts(df, back_days)
    published_post = read_from_cache()
    
    number_of_post = randint(1, 4)
    trending_posts = get_post_trending(df_clean, published_post, number_of_post)
    dump_to_cache(trending_posts, back_days)
    if not trending_posts.empty:
        html_output = summerize_X_posts(openAI_client, trending_posts)

        html = html_output
        for i in range(len(trending_posts)):
            hashtag_html = render_hashtags_from_topic(
                list(trending_posts.iloc[i].topic)
            )
            html = html.replace(
                f"<p>{{HASHTAGS_{i + 1}}}</p>",
                hashtag_html
            )

        publish_post_to_channel(html)
    else:
        print("No hot technical posts today")

if __name__ == "__main__":
    twitter_post_publish(4)
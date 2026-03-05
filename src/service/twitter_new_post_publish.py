import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from common.config import Config
from common.utils import render_hashtags_from_topic
from fsds.meme_poster import MemePoster
from fsds.session_cookies import get_session_cookies
from llm.use_cases import summerize_X_posts
from llm.gpt_client import ChatGPTClient
from messaging.service_bus_consumer import ServiceBusConsumer

CACHE_PATH = Path("published_posts.json")
openAI_client = ChatGPTClient()
new_post_consumer = ServiceBusConsumer(Config.SERVICE_BUS_CONNECTION_STRING,
                                       Config.TWITTER_NEW_POST_TOPIC,
                                       "logger"
                                    )


def publish_post_to_channel(content):
    poster = MemePoster(get_session_cookies())
    print(f"Content to publish : \n {content}")
    poster.post_meme(content, Config.TECHNICAL_CHANNEL_ID)

def read_from_cache():
    if not CACHE_PATH.exists():
        return set()

    with open(CACHE_PATH, "r") as f:
        data = json.load(f)
    
    return set(data.keys())

def dump_to_cache(trending_posts, back_days):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=back_days)
    
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


import pandas as pd

def twitter_new_technical_post_publish(new_posts: list[dict], back_days=4):
    if not new_posts:
        print("No messages received")
        return

    published_post = read_from_cache()
    cutoff_date = datetime.utcnow().date() - timedelta(days=back_days)

    df_filtered = pd.DataFrame(new_posts)
    df_filtered = df_filtered[df_filtered["is_tech_related"] == True]
    df_filtered = df_filtered[
        ~df_filtered["post_url"].isin(published_post)
    ]

    if (df_filtered.empty):
        print("No new technical posts today")
        return

    dump_to_cache(df_filtered, back_days)
    html_output = summerize_X_posts(openAI_client, df_filtered)
    html = html_output

    for i in range(len(df_filtered)):
        hashtag_html = render_hashtags_from_topic(
            list(df_filtered.iloc[i].topic)
        )
        html = html.replace(
            f"<p>{{HASHTAGS_{i + 1}}}</p>",
            hashtag_html
        )
    publish_post_to_channel(html)

if __name__ == "__main__":
    new_post_consumer.consume_batch(twitter_new_technical_post_publish)
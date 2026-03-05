import sys
from pathlib import Path
from random import randint
src_dir = Path(__file__).resolve().parents[2]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import logging
import pandas as pd
import json
import re
from datetime import datetime, timedelta, timezone

from storage.adls_client import ADLSClient
from storage.posts_reader import PostRawReader
from common.config import Config
from scraping.linkedin.linkedin_scraper import render_hashtags_from_topic
from fsds.meme_poster import MemePoster
from fsds.session_cookies import get_session_cookies

from llm.use_cases import summerize_linkedin_posts
from llm.gpt_client import ChatGPTClient
from llm.prompt_templates.linkedin_post_summary import SYSTEM_PROMPT
from scraping.linkedin.linkedin_scraper import LinkedInPostFormatter

logger = logging.getLogger(__name__)

adls = ADLSClient(Config.STORAGE_ACCOUNT_NAME, Config.STORAGE_ACCOUNT_KEY, Config.FILE_SYSTEM_NAME)
reader = PostRawReader(adls, "linkedin/raw")
openAI_client = ChatGPTClient()
post_formatter = LinkedInPostFormatter()  

REQUIRED_COLUMNS = {
    "author",
    "post_url",
    "text", 
    "reactions",
    "comments",
    "reposts",
}

ENGAGEMENT_COLS = [
    "reactions",
    "comments",
    "reposts",
]

def _resolve_cache_path() -> Path:
    """
    Store cache under <project_root>/data/cache/ to avoid depending on the current working dir.
    Also supports migration from legacy locations (repo root or src working dir).
    """
    cache_dir = Path(Config.DATA_DIR) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    new_path = cache_dir / "published_linkedin_posts.json"

    if new_path.exists():
        return new_path

    legacy_candidates = [
        Path(Config.PROJECT_ROOT) / "published_linkedin_posts.json",
        Path(Config.PROJECT_ROOT) / "src" / "published_linkedin_posts.json",
        Path.cwd() / "published_linkedin_posts.json",
    ]

    for old_path in legacy_candidates:
        try:
            if old_path.exists() and old_path.is_file():
                with open(old_path, "r") as f:
                    cache = json.load(f)
                with open(new_path, "w") as f:
                    json.dump(cache, f, indent=2)
                return new_path
        except Exception:
            continue

    return new_path


CACHE_PATH = _resolve_cache_path()


def parse_time_ago_to_date(scraped_at_str: str, time_ago: str) -> datetime:
    """
    Convert time_ago string (e.g., "3d", "2w", "10m", "1yr") to actual datetime.
    Returns None if parsing fails or if time_ago is None.
    """
    if not scraped_at_str or not time_ago:
        return None
    
    try:
        scraped_dt = datetime.fromisoformat(scraped_at_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        scraped_dt = datetime.utcnow()
    
    m = re.match(r"^(\d+)\s*([a-zA-Z]+)$", time_ago.strip().lower())
    if not m:
        return None
    
    value = int(m.group(1))
    unit = m.group(2).lower()
    
    if unit in ["s", "second", "seconds"]:
        delta = timedelta(seconds=value)
    elif unit in ["min", "minute", "minutes"]:
        delta = timedelta(minutes=value)
    elif unit in ["h", "hour", "hours"]:
        delta = timedelta(hours=value)
    elif unit in ["d", "day", "days"]:
        delta = timedelta(days=value)
    elif unit in ["w", "week", "weeks"]:
        delta = timedelta(weeks=value)
    elif unit in ["mo", "month", "months"]:
        # Explicit month notation
        delta = timedelta(days=30 * value)
    elif unit == "m":
        delta = timedelta(days=30 * value)
    elif unit in ["yr", "y", "year", "years"]:
        delta = timedelta(days=365 * value)
    else:
        return None
    
    published_dt = scraped_dt - delta
    return published_dt

def has_non_technical_topic(topics) -> bool:
    """Check if topics list contains 'Non-technical' or 'non-technical'"""
    if topics is None:
        return False
    if isinstance(topics, str):
        return topics in ["non-technical", "Non-technical"]
    if hasattr(topics, '__iter__') and not isinstance(topics, str):
        return any(t in ["non-technical", "Non-technical"] for t in topics if t)
    return False


def clean_linkedin_posts(df: pd.DataFrame, back_days: int) -> pd.DataFrame:
    """
    Clean and validate LinkedIn post data.
    
    Args:
        df: Raw DataFrame from Parquet files
        back_days: Number of days to look back
        
    Returns:
        Cleaned DataFrame with date, engagement metrics, and total_engagement
    """
    df = df.copy()
    
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    
    # Convert time_ago to actual date
    df["date"] = None
    for idx, row in df.iterrows():
        scraped_at = row.get("scraped_at")
        time_ago = row.get("time_ago")
        if scraped_at and time_ago:
            published_dt = parse_time_ago_to_date(scraped_at, time_ago)
            if published_dt:
                df.at[idx, "date"] = published_dt
        elif scraped_at:
            try:
                df.at[idx, "date"] = pd.to_datetime(scraped_at, errors="coerce", utc=True)
            except:
                pass
    
    # Convert date to datetime
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df[df["date"].notna()]
    
    # Filter by date range
    today = pd.Timestamp.utcnow().date()
    started_day = today - pd.Timedelta(days=back_days)
    
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
    
    df["total_engagement"] = (
        df["reactions"]
        + df["comments"]
        + df["reposts"]
    )
    
    df["content"] = df["text"]
    
    # Filter out non-technical posts - only keep technical posts for publishing
    if "is_tech_related" in df.columns:
        df = df[df["is_tech_related"] == True]
        print(f"[INFO] Filtered to {len(df)} posts with is_tech_related=True")
    else:
        print("[WARNING] 'is_tech_related' column not found - cannot filter non-technical posts")
    


    if "topic" in df.columns: 
        before_count = len(df)
        df = df[~df['topic'].apply(has_non_technical_topic)]
        excluded_count = before_count - len(df)
        if excluded_count > 0:
            print(f"[INFO] Excluded {excluded_count} posts with 'Non-technical' in topics")
    
    print(f"[INFO] Final count: {len(df)} technical posts (after all filtering)")
    
    return df.reset_index(drop=True)


def read_from_cache():
    """
    Read previously published post URLs from cache file with their timestamps.
    
    Returns:
        Dict mapping post URLs to their publication timestamp (ISO format)
    """
    if not CACHE_PATH.exists():
        print(f"[INFO] Cache file not found at {CACHE_PATH}, starting with empty cache")
        return {}

    try:
        with open(CACHE_PATH, "r") as f:
            data = json.load(f)
        
        print(f"[INFO] Loaded {len(data)} published post URL(s) from cache file: {CACHE_PATH}")
        return data
    except Exception as e:
        print(f"[WARNING] Error reading cache file {CACHE_PATH}: {e}, starting with empty cache")
        return {}


def get_published_post_urls(published_cache: dict) -> set:
    """
    Extract just the URLs from the published cache dict.
    
    Args:
        published_cache: Dict mapping URLs to timestamps
        
    Returns:
        Set of published post URLs
    """
    return set(published_cache.keys())


def get_recent_published_urls(published_cache: dict, max_runs: int = 2) -> set:
    """
    Return URLs that were published in the last `max_runs` publishing runs.
    
    A "run" is inferred from the timestamp value in the cache: all URLs with the
    same timestamp are assumed to have been published in the same run.
    """
    if not published_cache:
        return set()
    
    # Group URLs by their timestamp
    ts_to_urls = {}
    for url, ts in published_cache.items():
        ts_to_urls.setdefault(ts, set()).add(url)
    
    # Sort timestamps from newest to oldest and take the most recent N runs
    sorted_ts = sorted(ts_to_urls.keys(), reverse=True)
    recent_ts = sorted_ts[:max_runs]
    
    recent_urls: set = set()
    for ts in recent_ts:
        recent_urls.update(ts_to_urls.get(ts, set()))
    
    return recent_urls


def dump_to_cache(trending_posts, back_days):
    """
    Save newly published post URLs to cache file.
    Prunes old entries older than CACHE_RETENTION_DAYS (default: 90 days).
    
    Note: CACHE_RETENTION_DAYS should be much longer than back_days to prevent
    republishing posts that were recently published. The back_days parameter
    only controls which posts to consider from the data source, not cache retention.
    
    Args:
        trending_posts: DataFrame with published posts
        back_days: Number of days to look back (not used for cache pruning)
    """
    # Keep cache entries for 90 days to prevent republishing  
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=back_days)
    
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r") as f:
            cache = json.load(f)
    else:
        cache = {}
    
    # Prune entries older than CACHE_RETENTION_DAYS
    pruned_cache = {}
    pruned_count = 0
    for url, ts in cache.items():
        try:
            ts_dt = datetime.fromisoformat(ts)
            if ts_dt >= cutoff:
                pruned_cache[url] = ts
            else:
                pruned_count += 1
        except Exception as e:
            pruned_cache[url] = ts
    
    if pruned_count > 0:
        print(f"[INFO] Pruned {pruned_count} cache entries older than {back_days} days")
    
    # Add new posts to cache
    now_iso = now.isoformat()
    new_count = 0
    for url in trending_posts["post_url"]:
        if url not in pruned_cache:
            new_count += 1
        pruned_cache[url] = now_iso
    
    if new_count > 0:
        print(f"[INFO] Added {new_count} new post(s) to cache")
    
    print(f"[INFO] Cache now contains {len(pruned_cache)} total published post(s)")

    with open(CACHE_PATH, "w") as f:
        json.dump(pruned_cache, f, indent=2)


def calculate_adjusted_engagement(row, published_cache: dict, now: datetime):
    """
    Calculate adjusted engagement score for a post, applying penalties for recently published posts.
    
    Args:
        row: DataFrame row containing post data (must have 'post_url' and 'total_engagement')
        published_cache: Dict mapping published post URLs to their publication timestamps
        now: Current datetime (timezone-aware)
        
    Returns:
        Adjusted engagement score (float)
    """
    url = row.get('post_url', '')
    base_engagement = row.get('total_engagement', 0)
    
    # Only penalize if post was actually published to FSDS
    if url in published_cache:
        try:
            published_at = datetime.fromisoformat(published_cache[url])
            hours_ago = (now - published_at).total_seconds() / 3600
            
            if hours_ago < 24:
                penalty = 0.5
            elif hours_ago < 48:
                penalty = 0.75
            else:
                penalty = 1.0
            
            return base_engagement * penalty
        except Exception:
            return base_engagement
    else:
        return base_engagement


def get_linkedin_post_trending(df, published_cache: dict, number_of_post: int):
    """
    Get top trending technical posts from LinkedIn data, excluding already published posts.
    Gives lower priority to posts that were recently published to FSDS platform.
    Only returns technical posts (is_tech_related == True).
    
    Args:
        df: Cleaned DataFrame with is_tech_related and total_engagement
        published_cache: Dict mapping published post URLs to their publication timestamps
        number_of_post: Number of top posts to return
        
    Returns:
        DataFrame with top technical posts only (non-technical posts are excluded)
    """
    # Ensure we only get technical posts
    if "is_tech_related" not in df.columns:
        raise ValueError("'is_tech_related' column is required but not found in DataFrame")
    
    # Filter to only technical posts
    df_filtered = df[df["is_tech_related"] == True]
    
    # Exclude posts from the last N publishing runs (to avoid immediate repeats)
    recent_published_urls = get_recent_published_urls(published_cache, max_runs=2)
    before_filter = len(df_filtered)
    df_filtered = df_filtered[
        ~df_filtered["post_url"].isin(recent_published_urls)
    ]
    after_filter = len(df_filtered)
    
    if before_filter > after_filter:
        print(f"[INFO] Excluded {before_filter - after_filter} post(s) from the last 2 runs")
    
    if df_filtered.empty:
        print("[WARNING] No new posts available after filtering out published posts")
        return df_filtered
    
    # Calculate adjusted engagement scores 
    now = datetime.now(timezone.utc)
    
    # Add adjusted engagement column
    df_filtered = df_filtered.copy()
    df_filtered['adjusted_engagement'] = df_filtered.apply(
        lambda row: calculate_adjusted_engagement(row, published_cache, now), 
        axis=1
    )
    
    # Count how many posts are being penalized (should be 0 since we filtered them out)
    penalized_count = sum(1 for url in df_filtered['post_url'] if url in published_cache)
    if penalized_count > 0:
        print(f"[INFO] Applying priority penalty to {penalized_count} post(s) that were recently published")
    
    # Get a larger pool of top posts (2-3x the number needed) to allow for variety
    pool_size = min(max(number_of_post * 3, 10), len(df_filtered))
    top_pool = df_filtered.nlargest(pool_size, 'adjusted_engagement')
    
    # Shuffle the pool to randomize selection among similar scores
    top_pool = top_pool.sample(frac=1, random_state=None).reset_index(drop=True)
    
    # Take the requested number of posts from the shuffled pool
    top_posts = top_pool.head(number_of_post)
    
    # Log selected posts
    print(f"[INFO] Selected {len(top_posts)} post(s) from {len(df_filtered)} available posts")
    for idx, row in top_posts.iterrows():
        author = row.get('author', 'N/A')
        url = row.get('post_url', 'N/A')
        engagement = row.get('total_engagement', 0)
        adjusted = row.get('adjusted_engagement', engagement)
        print(f"  - {author}: {engagement} engagement (adjusted: {adjusted:.0f}) - {url}")
    
    return top_posts


def _validate_html_format(html: str) -> bool:
    """
    Validate that the HTML content contains proper HTML tags.
    Returns True if HTML is properly formatted, False otherwise.
    """
    if not html or not html.strip():
        return False
    
    # Check if content contains HTML tags (at least <p> tags)
    html_lower = html.lower()
    
    # Must contain at least one HTML tag
    has_html_tags = (
        '<p>' in html_lower or 
        '<strong>' in html_lower or 
        '<a ' in html_lower or
        '<div>' in html_lower
    )
    
    # Check if it looks like plain text (has multiple newlines but no HTML tags)
    if not has_html_tags:
        if '\n\n' in html or html.count('\n') > 3:
            return False
    
    return has_html_tags


def _re_render_post_summary(llm_client, post_row, post_index: int) -> str:
    """
    Re-render a single post's summary if the initial LLM output was invalid.
    
    Args:
        llm_client: LLM client instance
        post_row: Single post row from DataFrame
        post_index: Index of the post (1-based)
        
    Returns:
        HTML summary for the single post
    """
    # Create a single-row DataFrame for this post
    single_post_df = pd.DataFrame([post_row])
    
    # Build a simplified prompt for a single post
    post_data = post_row
    total_interactions = (
        int(post_data.get('reactions', 0) or 0) +
        int(post_data.get('comments', 0) or 0) +
        int(post_data.get('reposts', 0) or 0)
    )
    
    user_prompt = f"""
        You are a tech content curator.
        Create an engaging summary for Post {post_index} in VALID HTML format.

        Post {post_index}:
        - Author: {post_data.get('author', 'N/A')}
        - Influencer Title: {post_data.get('influencer_title', 'N/A')}
        - Content: {post_data.get('content', post_data.get('text', 'N/A'))}
        - Total Interactions: {total_interactions}
        - Post URL: {post_data.get('post_url', 'N/A')}

        OUTPUT REQUIREMENTS:
        - Output VALID HTML ONLY with proper tags
        - Use <p> for all paragraphs
        - Use <strong> for the title: <p><strong>Post {post_index}: TITLE</strong></p>
        - Include engagement metrics naturally (e.g., "hơn {total_interactions} lượt tương tác")
        - Include influencer info if available
        - Wrap the URL in <a href="URL">URL</a> tags: <p>Đọc thêm tại: <a href="{post_data.get('post_url', '')}">{post_data.get('post_url', '')}</a></p>
        - After the URL, output: <p>{{HASHTAGS_{post_index}}}</p>
        - Write in natural, fluent Vietnamese
        - Total length: 50-100 words for this single post
        - Do NOT use Markdown syntax
        - Do NOT output plain text - MUST use HTML tags
    """
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    
    return llm_client.chat_complete(messages)


def _replace_hashtag_placeholder_block(html: str, index: int, replacement: str):
    """
    Replace the hashtag placeholder for a given post index in the generated HTML.
    
    The LLM doesn't always output the placeholder in the exact
    "<p>{HASHTAGS_i}</p>" form (it may add spaces or extra text).
    This helper tries, in order:
      1. Exact match of "<p>{HASHTAGS_i}</p>"
      2. Any <p>...</p> block that contains "HASHTAGS_i"
      3. Bare "HASHTAGS_i" token
    """
    placeholder_token = f"HASHTAGS_{index}"
    exact = f"<p>{{{placeholder_token}}}</p>"

    # 1) Exact match
    if exact in html:
        return html.replace(exact, replacement, 1), True

    # 2) Any <p>...</p> that contains the token (allowing spaces/extra text)
    pattern = re.compile(
        rf"<p[^>]*>[^<]*{re.escape(placeholder_token)}[^<]*</p>",
        re.IGNORECASE,
    )
    if pattern.search(html):
        return pattern.sub(replacement, html, count=1), True

    # 3) Fallback: replace bare token
    if placeholder_token in html:
        return html.replace(placeholder_token, replacement, 1), True

    return html, False


def publish_post_to_channel(content):
    """
    Publish content to FSDS channel.
    
    Args:
        content: HTML content to post
        
    Returns:
        Response dictionary from API
    """
    poster = MemePoster(get_session_cookies())
    print("\n" + "=" * 60)
    print("PUBLISHING TO FSDS")
    print("=" * 60)
    print(content)
    print("=" * 60)
    
    response = poster.post_meme(content, Config.TECHNICAL_CHANNEL_ID)
    
    if response.get("success"):
        print(f"\nPost published successfully!")
        print(f"Status code: {response.get('status_code')}")
        print(f"Response: {response.get('data', 'No data')}")
    else:
        print(f"\nFailed to publish post: {response}")
    
    return response


def linkedin_post_publish(back_days: int):
    """
    Main function to publish LinkedIn trending posts to FSDS.
    
    Args:
        back_days: Number of days to look back for posts
    """
    # Read LinkedIn Parquet files from ADLS
    df = reader.read_recent_days(back_days)
    
    if df.empty:
        print(f"No LinkedIn posts found in the last {back_days} days.")
        return
    
    # Clean and process data
    df_clean = clean_linkedin_posts(df, back_days)
    
    if df_clean.empty:
        print(f"No LinkedIn posts found after cleaning (last {back_days} days).")
        return
    
    # Read cache of previously published posts 
    published_cache = read_from_cache()
    published_post_urls = get_published_post_urls(published_cache)
    print(f"[INFO] Loaded {len(published_cache)} previously published post(s) from cache")
    
    # Log how many posts are being filtered out
    if len(published_post_urls) > 0:
        filtered_count = df_clean[df_clean["post_url"].isin(published_post_urls)].shape[0]
        if filtered_count > 0:
            print(f"[INFO] Filtering out {filtered_count} post(s) that were already published")
    
    no_posts = randint(1, 4)
    # Get top trending posts excluding 2 last runs
    trending_posts = get_linkedin_post_trending(df_clean, published_cache, no_posts)
    
    if trending_posts.empty:
        print("No new trending technical posts found in the specified date range (after excluding last 2 runs).")
        return
    
    # Ensure all posts are technical before publishing
    if "is_tech_related" in trending_posts.columns:
        non_tech_count = (~trending_posts["is_tech_related"]).sum()
        if non_tech_count > 0:
            print(f"[ERROR] Found {non_tech_count} non-technical posts in trending_posts - filtering them out")
            trending_posts = trending_posts[trending_posts["is_tech_related"] == True]
            if trending_posts.empty:
                print("No technical posts remaining after filtering out non-technical posts.")
                return
    else:
        print("[WARNING] 'is_tech_related' column not found in trending_posts - cannot verify posts are technical")
    
    # Generate summary using LLM 
    summary = summerize_linkedin_posts(openAI_client, trending_posts)
    
    # Validate HTML format 
    if not _validate_html_format(summary):
        print("[WARNING] LLM output is not properly formatted HTML (missing tags)")
        print("[INFO] Attempting to re-render individual posts...")
        
        # Re-render each post individually
        re_rendered_parts = []
        re_rendered_parts.append("<p><strong>Cập nhật công nghệ nổi bật hôm nay cho cộng đồng công nghệ Việt Nam</strong></p>\n\n")
        
        for i in range(len(trending_posts)):
            post_row = trending_posts.iloc[i]
            print(f"[INFO] Re-rendering post {i + 1}...")
            post_summary = _re_render_post_summary(openAI_client, post_row, i + 1)
            
            # Validate the re-rendered post
            if _validate_html_format(post_summary):
                re_rendered_parts.append(post_summary)
                if i < len(trending_posts) - 1:
                    re_rendered_parts.append("\n\n")
                print(f"[INFO] Post {i + 1} re-rendered successfully")
            else:
                print(f"[ERROR] Post {i + 1} still invalid after re-rendering, using fallback HTML")
                # Fallback: create basic HTML structure
                post_url = post_row.get('post_url', 'N/A')
                post_title = f"Post {i + 1}: {post_row.get('author', 'N/A')}"
                fallback_html = (
                    f"<p><strong>{post_title}</strong></p>\n"
                    f"<p>Đọc thêm tại: <a href=\"{post_url}\">{post_url}</a></p>\n"
                    f"<p>{{HASHTAGS_{i + 1}}}</p>\n"
                )
                re_rendered_parts.append(fallback_html)
                if i < len(trending_posts) - 1:
                    re_rendered_parts.append("\n\n")
        
        summary = "".join(re_rendered_parts)
        print("[INFO] Re-rendering complete")
    
    if 'topic' not in trending_posts.columns:
        print(f"[WARNING] 'topic' column not found in DataFrame. Available columns: {list(trending_posts.columns)}")
        print("[WARNING] Hashtags will not be added. Make sure 'topic' field is preserved in Parquet files.")
    
    # Replace hashtag placeholders with actual hashtags 
    html_for_linkedin = summary
    for i in range(len(trending_posts)):
        post_row = trending_posts.iloc[i]
        
        topics = []
        try:
            topics_raw = post_row.topic if hasattr(post_row, 'topic') else post_row.get('topic', [])
            
            if isinstance(topics_raw, str):
                topics = [topics_raw] if topics_raw else []
            elif hasattr(topics_raw, '__iter__') and not isinstance(topics_raw, str):
                topics = list(topics_raw) if topics_raw is not None else []
            elif topics_raw is not None:
                topics = [topics_raw]
        except (AttributeError, KeyError):
            topics = []
        
        if not topics or (len(topics) == 1 and topics[0] in ["technical", "non-technical"]):
            post_text = post_row.get('text') or post_row.get('content', '')
            if post_text:
                extracted_topics = post_formatter._extract_topics(post_text)
                if extracted_topics:
                    topics = extracted_topics
                    print(f"[INFO] Extracted {len(topics)} specific topics for post {i + 1}: {topics}")
                elif topics and topics[0] == "technical":
                    import re
                    post_text_lower = post_text.lower()
                    if re.search(r"\bai\b", post_text_lower) or re.search(r"\b(artificial intelligence)\b", post_text_lower):
                        topics = ["Generative AI"]
                        print(f"[INFO] Post {i + 1} mentions AI but no specific topics matched, using AI fallback")
                    else:
                        print(f"[INFO] Post {i + 1} is technical but no specific topics matched")
        
        if topics and ("Non-technical" in topics or "non-technical" in topics):
            logger.error("Post %d has 'Non-technical' in extracted topics: %s", i + 1, topics)
            logger.error("This post should NOT be published to the platform!")
            logger.error("Post URL: %s", post_row.get('post_url', 'N/A'))
            logger.error("Skipping hashtag rendering and removing from output")

        elif topics == ["technical"]:
            hashtag_html = ""
            print(f"[INFO] Post {i + 1} has only generic 'technical' topic - no hashtags will be rendered")
        else:
            hashtag_html = render_hashtags_from_topic(topics)
        
        # Replace placeholder if hashtags were found
        if hashtag_html:
            html_for_linkedin, replaced = _replace_hashtag_placeholder_block(
                html_for_linkedin,
                i + 1,
                hashtag_html,
            )
            if replaced:
                print(f"[INFO] Replaced hashtag placeholder for post {i + 1} with topics: {topics}")
            else:
                placeholder = f"<p>{{HASHTAGS_{i + 1}}}</p>"
                print(f"[WARNING] Hashtag placeholder for post {i + 1} not found (expected like '{placeholder}')")
        else:
            # No hashtags found, remove the placeholder entirely
            html_for_linkedin, replaced = _replace_hashtag_placeholder_block(
                html_for_linkedin,
                i + 1,
                "",  
            )
            if replaced:
                print(f"[INFO] No hashtags found for post {i + 1}, removed hashtag placeholder")
            else:
                print(f"[INFO] No hashtags found for post {i + 1}, but placeholder not found to remove")
    
    #Publish to FSDS channel
    response = publish_post_to_channel(html_for_linkedin)
    
    if response.get("success"):
        print("[INFO] Publishing successful - updating cache with published posts")
        dump_to_cache(trending_posts, back_days)
    else:
        print("[WARNING] Publishing failed - NOT updating cache (posts will be available for next run)")


if __name__ == "__main__":
    linkedin_post_publish(4)  
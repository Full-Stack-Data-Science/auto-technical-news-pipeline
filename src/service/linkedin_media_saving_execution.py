import sys
from pathlib import Path
import re
import logging
from typing import Optional

src_dir = Path(__file__).resolve().parents[2]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pandas as pd
from common.storage.adls_client import ADLSClient
from common.storage.posts_reader import PostRawReader
from common.config import Config
from common.utils import setup_logging
from scraping.core.web_parser import RequestWebParser

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def extract_filename_from_url(url: str, activity_id: str, image_number: int = 1) -> str:
    """
    Generate filename in format <activity_id><image_number>.<ext>.
    
    Args:
        url: Image URL (used to detect extension)
        activity_id: LinkedIn activity ID
        image_number: Image number for this activity (1, 2, 3, etc.)
        
    Returns:
        Filename with format <activity_id><image_number>.<ext>
    """
    # Detect extension from URL
    if '.jpg' in url.lower() or 'jpeg' in url.lower():
        ext = '.jpg'
    elif '.png' in url.lower():
        ext = '.png'
    elif '.gif' in url.lower():
        ext = '.gif'
    elif '.webp' in url.lower():
        ext = '.webp'
    else:
        ext = '.jpg'  
    
    return f"{activity_id}_num{image_number}{ext}"


def download_image(url: str, timeout: int = 30) -> Optional[bytes]:
    """
    Download image from URL using RequestWebParser.
    
    Args:
        url: Image URL to download
        timeout: Request timeout in seconds
        
    Returns:
        Image bytes if successful, None otherwise
    """
    try:
        parser = RequestWebParser(url, rotate_header=True)
        content = parser.get_content(timeout=timeout)
        
        if content:
            # Verify image is not empty
            if len(content) > 0:
                logger.debug(f"Downloaded {len(content)} bytes from {url}")
                return content
            else:
                logger.warning(f"Downloaded empty content from {url}")
                return None
        else:
            logger.warning(f"Failed to download content from {url}")
            return None
            
    except Exception as e:
        logger.error(f"Error downloading image from {url}: {e}", exc_info=True)
        return None


def upload_image_to_dls(
    adls_client: ADLSClient,
    image_bytes: bytes,
    activity_id: str,
    filename: str
) -> bool:
    """
    Upload image bytes to Azure Data Lake Storage.
    
    Args:
        adls_client: ADLS client instance
        image_bytes: Image file bytes
        activity_id: LinkedIn activity ID (used for directory path)
        filename: Filename to save as
        
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path = f"linkedin/media/{activity_id}/{filename}"
        
        file_client = adls_client.get_file_client(file_path)
        file_client.upload_data(
            image_bytes,
            overwrite=True
        )
        
        logger.info(f"Uploaded image to {file_path} ({len(image_bytes)} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to upload image for activity_id {activity_id}: {e}", exc_info=True)
        return False


def extract_activity_id(row: pd.Series) -> Optional[str]:
    """
    Extract activity_id from row, with fallback to extracting from post_url.
    
    Args:
        row: DataFrame row
        
    Returns:
        Activity ID string or None
    """
    # Try direct activity_id column first
    if 'activity_id' in row and pd.notna(row['activity_id']):
        return str(row['activity_id'])
    
    # Fallback: extract from post_url
    if 'post_url' in row and pd.notna(row['post_url']):
        post_url = str(row['post_url'])
        match = re.search(r'activity[:\-](\d+)', post_url)
        if match:
            return match.group(1)
    
    return None


def process_media_urls(
    df: pd.DataFrame,
    adls_client: ADLSClient,
    max_images: Optional[int] = None,
    activity_url: Optional[str] = None,
) -> dict:
    """
    Process media URLs from DataFrame and download/upload images.
    
    Args:
        df: DataFrame with columns: media_url, and optionally activity_id or post_url
        adls_client: ADLS client instance
        max_images: Maximum number of images to process (None for all)
        activity_url: If provided, only process rows whose post_url matches this value
        
    Returns:
        Dictionary with statistics: {'success': int, 'failed': int, 'skipped': int}
    """
    stats = {'success': 0, 'failed': 0, 'skipped': 0}
    
    if activity_url:
        if 'post_url' not in df.columns:
            logger.error(
                "activity_url was provided but DataFrame does not contain 'post_url' column"
            )
            return stats
        
        original_len = len(df)
        df = df[df['post_url'] == activity_url].copy()
        logger.info(
            f"Filtering by activity_url={activity_url}. "
            f"Matched {len(df)} rows out of {original_len}."
        )
        
        if df.empty:
            logger.warning(
                f"No rows found matching activity_url={activity_url}. "
                "No media will be processed."
            )
            return stats
    
    # Filter rows with valid media URLs
    media_df = df[
        df['media_url'].notna() & 
        (df['media_url'] != '')
    ].copy()
    
    if media_df.empty:
        logger.warning("No rows with media URLs found in DataFrame")
        return stats
    
    logger.info(f"Found {len(media_df)} posts with media URLs")
    
    # Extract activity_id for each row (with fallback)
    media_df['_activity_id'] = media_df.apply(extract_activity_id, axis=1)
    
    # Filter out rows without activity_id
    media_df = media_df[media_df['_activity_id'].notna()].copy()

    if media_df.empty:
        logger.warning("No rows with valid activity_id found")
        return stats
    
    logger.info(f"Found {len(media_df)} posts with valid activity_id")

    # Deduplicate by media_url 
    before_url_dedup = len(media_df)
    media_df = media_df.drop_duplicates(subset=['media_url']).reset_index(drop=True)
    logger.info(
        f"After deduplicating by media_url: kept {len(media_df)} rows "
        f"out of {before_url_dedup} media rows with valid activity_id"
    )
    
    # Group by activity_id and number images sequentially 
    media_df = media_df.sort_values('_activity_id').reset_index(drop=True)
    media_df['_image_number'] = media_df.groupby('_activity_id').cumcount() + 1
    
    # Keep only the first image for each activity_id
    before_dedup = len(media_df)
    media_df = media_df[media_df['_image_number'] == 1].copy()
    logger.info(
        f"Restricting to a single media per post: kept {len(media_df)} rows "
        f"out of {before_dedup} media rows with valid activity_id"
    )
    
    # Limit number of media if specified
    if max_images:
        media_df = media_df.head(max_images)
        logger.info(f"Processing first {len(media_df)} images (limited by max_images)")
    
    # Process each row
    for idx, row in media_df.iterrows():
        activity_id = str(row['_activity_id'])
        image_number = int(row['_image_number'])
        media_url = str(row['media_url']).strip()
        
        if not media_url or media_url.lower() in ['none', 'null', 'nan']:
            stats['skipped'] += 1
            continue
        
        logger.info(f"Processing image {image_number} for activity_id {activity_id}: {media_url}")
        
        # Download image
        image_bytes = download_image(media_url)
        
        if not image_bytes:
            stats['failed'] += 1
            logger.warning(f"Failed to download image {image_number} for activity_id {activity_id}")
            continue
        
        # Generate filename with format <activity_id><image_number>.<ext>
        filename = extract_filename_from_url(media_url, activity_id, image_number)
        
        # Upload to Azure Data Lake Storage
        if upload_image_to_dls(adls_client, image_bytes, activity_id, filename):
            stats['success'] += 1
        else:
            stats['failed'] += 1
    
    return stats


def main(
    days_back: int = 7,
    max_images: Optional[int] = None,
    activity_url: Optional[str] = None,
):
    """
    Main function to download and save LinkedIn media images.
    
    Args:
        days_back: Number of days to look back for parquet files
        max_images: Maximum number of images to process (None for all)
        activity_url: If provided, only process media for this LinkedIn post URL
    """
    logger.info("=" * 50)
    logger.info("Starting LinkedIn Media Download and Save")
    logger.info("=" * 50)
    
    try:
        # Initialize ADLS client
        if not Config.STORAGE_ACCOUNT_KEY:
            raise RuntimeError("STORAGE_ACCOUNT_KEY not set in environment")
        
        adls_client = ADLSClient(
            Config.STORAGE_ACCOUNT_NAME,
            Config.STORAGE_ACCOUNT_KEY,
            Config.FILE_SYSTEM_NAME
        )
        
        # Read parquet files
        logger.info(f"Reading parquet files from last {days_back} days...")
        reader = PostRawReader(adls_client, "linkedin/raw")
        df = reader.read_recent_days(days_back)
        
        if df.empty:
            logger.warning("No data found in parquet files")
            return
        
        logger.info(f"Loaded {len(df)} rows from parquet files")
        
        # Check required columns
        if 'media_url' not in df.columns:
            raise ValueError("Missing required column: media_url")
        
        # Check if we have activity_id or post_url 
        if 'activity_id' not in df.columns and 'post_url' not in df.columns:
            raise ValueError("Missing required columns: need either 'activity_id' or 'post_url'")
        
        # Process media URLs
        stats = process_media_urls(
            df,
            adls_client,
            max_images=max_images,
            activity_url=activity_url,
        )
        
        # Print summary
        logger.info("=" * 50)
        logger.info("Media Download Summary")
        logger.info("=" * 50)
        logger.info(f"Successfully processed: {stats['success']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info(f"Skipped: {stats['skipped']}")
        logger.info(f"Total: {stats['success'] + stats['failed'] + stats['skipped']}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download and save LinkedIn media images")
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Number of days to look back for parquet files (default: 7)"
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="Maximum number of images to process (default: all)"
    )
    parser.add_argument(
        "--activity-url",
        type=str,
        default=None,
        help="Only process media for this LinkedIn post URL (exact match on post_url column)",
    )
    
    args = parser.parse_args()
    
    main(
        days_back=args.days_back,
        max_images=args.max_images,
        activity_url=args.activity_url,
    )

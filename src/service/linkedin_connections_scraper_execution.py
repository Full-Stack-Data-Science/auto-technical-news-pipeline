import sys
from pathlib import Path
import json
import argparse

src_dir = Path(__file__).resolve().parents[2]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from scraping.linkedin.linkedin_scraper import LinkedInConnectionsScraper, extract_slug_from_linkedin_url
from scraping.linkedin.linkedin_parser import LinkedInParser
from common.utils import setup_logging
from common.config import Config
from typing import List, Optional
import random
import os
import logging
import time

setup_logging()
logger = logging.getLogger(__name__)

# Define Influencer Path
INFLUENCER_JSON_PATH = "data/influencer/linkedin_influencer.json"

# Local save path
LOCAL_OUTPUT_DIR = os.path.join(Config.PROJECT_ROOT, "data", "relationships", "linkedin")
LOCAL_OUTPUT_FILE = "linkedin_connections.json"

# Cloud saving path
CLOUD_REMOTE_PATH = "linkedin/relationships/connections/linkedin_connections.json"

# Define default connections to scrape
TOP_N_PER_INFLUENCER = 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn connections for influencers.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=INFLUENCER_JSON_PATH,
        metavar="PATH",
        help="Path to the influencer JSON file.",
    )
    parser.add_argument(
        "--page-threshold",
        type=int,
        default=3,
        metavar="N",
        help="Maximum pages per degree to scrape.",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        default=False,
        help="Save scraped data locally only, skip Azure Data Lake upload.",
    )
    return parser.parse_args(argv)


def load_linkedin_influencers(data_path: Path) -> List[str]:
    """
    Load LinkedIn influencer slugs from a JSON file.

    Expected JSON formats:
    - Simple list of strings:
        ["chiphuyen", "yann-lecun", ...]
    - Or an object where keys are influencer slugs:
        {"chiphuyen": {...}, "yann-lecun": {...}}
    """
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Influencer JSON not found at {data_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading influencer JSON from {data_path}: {e}", exc_info=True)
        return []

    influencers: List[str] = []

    if isinstance(data, list):
        influencers = [str(x).strip() for x in data if str(x).strip()]
    elif isinstance(data, dict):
        influencers = [str(k).strip() for k in data.keys() if str(k).strip()]
    else:
        logger.error(
            f"Unexpected format in {data_path}. "
            "Expected a list of strings or an object with influencer keys."
        )
        return []

    if not influencers:
        logger.error(f"No influencers found in {data_path}")
        return []

    logger.info(f"Loaded {len(influencers)} LinkedIn influencers from {data_path}")
    return influencers




def expand_from_existing_connections(
    base_influencers: List[str],
    top_n: int = TOP_N_PER_INFLUENCER,
) -> List[str]:
    """
    If a previously scraped connections JSON exists, pick the top-N connections
    for each influencer and merge them into the scrape list.

    Returns:
        Expanded list of influencer slugs (base + discovered connections),
        preserving original order with new entries appended.
    """
    local_path = os.path.join(LOCAL_OUTPUT_DIR, LOCAL_OUTPUT_FILE)
    if not os.path.isfile(local_path):
        logger.info(f"No existing connections file at {local_path} — scraping base influencers only")
        return base_influencers

    try:
        with open(local_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read existing connections file: {e}")
        return base_influencers

    seen = set(base_influencers)
    extra_slugs: List[str] = []

    for entry in data.get("influencers", []):
        connections = entry.get("connections", [])
        for conn in connections[:top_n]:
            url = conn.get("connection_url", "")
            slug = extract_slug_from_linkedin_url(url)
            if slug and slug not in seen:
                seen.add(slug)
                extra_slugs.append(slug)

    if extra_slugs:
        logger.info(
            f"Expanded scrape list with {len(extra_slugs)} connections "
            f"(top {top_n} per influencer) from {local_path}"
        )
    else:
        logger.info("Existing connections file found but no new slugs to add")

    return base_influencers + extra_slugs


def upload_json_to_dls(local_path: str, remote_path: str) -> bool:
    """Upload a local JSON file to Azure Data Lake Storage."""
    from azure.storage.filedatalake import DataLakeServiceClient

    try:
        service_client = DataLakeServiceClient(
            account_url=f"https://{Config.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net",
            credential=Config.STORAGE_ACCOUNT_KEY,
        )
        filesystem_client = service_client.get_file_system_client(Config.FILE_SYSTEM_NAME)
        file_client = filesystem_client.get_file_client(remote_path)

        with open(local_path, "rb") as f:
            file_client.upload_data(f, overwrite=True)

        logger.info(f"Uploaded to ADLS: {remote_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload to ADLS: {e}", exc_info=True)
        return False


def scrape_connections(
    influencers: List[str],
    page_threshold: int = 3,
    no_upload: bool = False,
):
    """
    Scrape connections for LinkedIn influencers.

    Args:
        influencers: List of influencer slugs or URLs
        page_threshold: Maximum pages per degree
        no_upload: If True, save locally only
    """
    logger.info("=" * 50)
    logger.info("Starting LinkedIn Connections Scraper")
    logger.info("=" * 50)
    logger.info(f"Page threshold: {page_threshold}")
    logger.info(f"Total influencers: {len(influencers)}")
    logger.info("=" * 50)

    # Convert slugs to full URLs if needed
    influencer_urls = []
    for influencer in influencers:
        if "/in/" in influencer:
            influencer_urls.append(influencer)
        else:
            influencer_urls.append(f"https://www.linkedin.com/in/{influencer}/")

    profile_paths = [
        os.path.join(Config.PROJECT_ROOT, "google-chrome", "Profile_LinkedIn"),
        os.path.join(Config.PROJECT_ROOT, "google-chrome", "Profile_Linkedin"),
        os.path.join(Config.PROJECT_ROOT, "src", "google-chrome", "Profile_LinkedIn"),
        os.path.join(Config.PROJECT_ROOT, "src", "google-chrome", "Profile_Linkedin"),
        "./google-chrome/Profile_LinkedIn",
        "./google-chrome/Profile_Linkedin",
    ]
    profile_exists = any(os.path.exists(p) for p in profile_paths)

    if profile_exists:
        logger.info("Chrome profile detected - using local Chrome profile for authentication")
        parser = LinkedInParser(run_in_local=True, require_selenium=False)
    else:
        logger.info("No Chrome profile detected - using Remote WebDriver + cookies (if available)")
        parser = LinkedInParser(run_in_local=False)

    with LinkedInConnectionsScraper(parser=parser) as connections_scraper:
        # Login
        email = getattr(Config, "LINKEDIN_EMAIL", Config.LINKEDIN_EMAIL)
        password = getattr(Config, "LINKEDIN_PASSWORD", Config.LINKEDIN_PASSWORD)
        logger.info("Logging in to LinkedIn...")
        connections_scraper.parser.login(email, password)
        logger.info("Successfully logged in")

        all_connection_results = []

        for idx, profile_url in enumerate(influencer_urls, 1):
            logger.info(f"\n{'=' * 50}")
            logger.info(f"Processing influencer {idx}/{len(influencer_urls)}: {profile_url}")
            logger.info(f"{'=' * 50}")

            try:
                result = connections_scraper.scrape_influencer_info_and_connections(
                    profile_url,
                    scrape_connections=True,
                    scrape_followers=False,
                    page_threshold=page_threshold,
                )

                influencer_info = result.get("influencer_info", {})
                influencer_name = influencer_info.get("name", "Unknown")

                connections = result.get("connections", [])
                logger.info(f"Scraped {len(connections)} connections for {influencer_name}")
                all_connection_results.append(result)

                # Delay between influencers
                if idx < len(influencer_urls):
                    delay = random.uniform(5, 10)
                    logger.info(f"Waiting {delay:.1f} seconds before next influencer...")
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Error scraping {profile_url}: {e}", exc_info=True)
                logger.warning("Continuing with next influencer...")
                continue

        # Save results as JSON locally
        if all_connection_results:
            os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
            local_path = os.path.join(LOCAL_OUTPUT_DIR, LOCAL_OUTPUT_FILE)

            connections_scraper.save_to_json(
                all_connection_results,
                local_path,
                is_connections=True,
            )

            logger.info(f"Connections saved locally to {local_path}")
            total_connections = sum(len(r.get("connections", [])) for r in all_connection_results)
            logger.info(f"Total influencers with connections: {len(all_connection_results)}")
            logger.info(f"  Total connections scraped: {total_connections}")

            # Upload to cloud unless --no-upload
            if no_upload:
                logger.info("--no-upload flag set. Skipping Azure Data Lake upload.")
            else:
                if not Config.STORAGE_ACCOUNT_KEY or not Config.FILE_SYSTEM_NAME:
                    logger.warning("STORAGE_ACCOUNT_KEY or FILE_SYSTEM_NAME not set - skipping upload")
                else:
                    upload_json_to_dls(local_path, CLOUD_REMOTE_PATH)
        else:
            logger.warning("No connection results to save.")

        logger.info("=" * 50)
        logger.info("Connections Scraping Completed Successfully")
        logger.info("=" * 50)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logger.info("=" * 50)
    logger.info("LinkedIn Connections Scraper")
    logger.info("=" * 50)

    base_influencers = load_linkedin_influencers(args.data)
    if not base_influencers:
        logger.error("No LinkedIn influencers loaded from JSON. Aborting.")
        return 1

    influencers = expand_from_existing_connections(base_influencers)
    logger.info(f"Total profiles to scrape: {len(influencers)} "
                f"({len(base_influencers)} base + {len(influencers) - len(base_influencers)} from existing connections)")

    try:
        scrape_connections(
            influencers,
            page_threshold=args.page_threshold,
            no_upload=args.no_upload,
        )
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

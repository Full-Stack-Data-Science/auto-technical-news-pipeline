import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scraping.linkedin.linkedin_scraper import LinkedInPostScraper, build_linkedin_relationship_model_from_data
from network.relation import RelationshipModel
from network.graph import build_nx_graph
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = "data/influencer/linkedin_influencer.json"
DEFAULT_POST_LIMIT = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the LinkedIn AI Influencer Graph and scrape posts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        metavar="PATH",
        help="Path to the influencer JSON file.",
    )
    parser.add_argument(
        "--posts",
        type=int,
        default=DEFAULT_POST_LIMIT,
        metavar="N",
        help="Number of posts to scrape per user.",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        default=False,
        help="Save scraped data locally instead of uploading to Azure Data Lake Storage.",
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


def build_linkedin_relationship_graph(
    influencers: List[str],
) -> RelationshipModel:
    """
    Build a LinkedinRelationshipModel from scraped LinkedIn followers and connections JSON files.
    """

    followers_json_path = "all_scraped_followers.json"
    connections_json_path = "all_scraped_connections.json"

    followers_data = {}
    connections_data = {}

    try:
        with open(followers_json_path, "r", encoding="utf-8") as f:
            followers_data = json.load(f)
    except FileNotFoundError:
        logger.warning(f"{followers_json_path} not found, skipping followers")
    except Exception as e:
        logger.error(f"Error loading followers: {e}")

    try:
        with open(connections_json_path, "r", encoding="utf-8") as f:
            connections_data = json.load(f)
    except FileNotFoundError:
        logger.warning(f"{connections_json_path} not found, skipping connections")
    except Exception as e:
        logger.error(f"Error loading connections: {e}")

    # Create a minimal graph from influencer list
    if followers_data or connections_data:
        return build_linkedin_relationship_model_from_data(
            followers_data, 
            connections_data,
            influencer_priority_list=influencers
        )
    else:
        # Create a minimal graph from influencer list 
        logger.info("No JSON data found. Creating minimal graph from influencer list...")
        graph = RelationshipModel()
        
        for influencer in influencers:
            graph._init_user_relations(influencer)
        
        logger.info(f"Created graph with {len(influencers)} influencers")
        return graph



def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        influencers = load_linkedin_influencers(args.data)
        if not influencers:
            logger.error("No LinkedIn influencers loaded from JSON. Aborting scraper execution.")
            return 1

        linkedin_graph = build_linkedin_relationship_graph(influencers)
        nx_linkedin = build_nx_graph(linkedin_graph)
        logger.info("=" * 50)
        logger.info("LinkedIn AI Graph Built Successfully")
        logger.info("=" * 50)
        logger.info(f"Total users: {nx_linkedin.number_of_nodes()}")
        logger.info(f"Total relationships: {nx_linkedin.number_of_edges()}")
        logger.info(f"Sample edges: {list(nx_linkedin.edges(data=True))[:5]}")
        
        logger.info("Initializing LinkedInPostScraper...")
        scraper = LinkedInPostScraper(linkedin_graph)
        
        logger.info("Starting scraping process...")
        scraper.scrape(
            limit=args.posts,
            influencer_priority_list=influencers,
            no_upload=args.no_upload,
        )
        
        logger.info("=" * 50)
        logger.info("LinkedIn Scraper Execution Completed Successfully")
        logger.info("=" * 50)
    except FileNotFoundError as exc:
        logger.error("Data file not found: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
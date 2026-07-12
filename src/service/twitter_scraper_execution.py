import argparse
import logging
import sys
from pathlib import Path

from celeb_graph.graph.builder import build_graph
from celeb_graph.io.json_loader import load_from_json
from post_scraper.twitter.twitter_scraper import TwitterPostScraper
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = "data/influencer/twitter_influencer.json"

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Twitter AI Influencer Graph and scrape posts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        metavar="PATH",
        help="Path to the influencer relationship JSON file.",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip uploading scraped posts.",
    )
    return parser.parse_args(argv)


def load_graph(data_path: Path):
    logger.info(f"Loading relationship model from: {data_path}")
    relationships_model = load_from_json(data_path)

    nx_graph = build_graph(relationships_model)
    logger.info("Twitter AI Graph built successfully")
    logger.info(f"  Users         :  {nx_graph.number_of_nodes()}")
    logger.info(f"  Relationships :  {nx_graph.number_of_edges()}")

    sample = list(nx_graph.edges(data=True))[:5]
    logger.info("  Sample edges  : %s", sample)

    return relationships_model


def run_scraper(relationships_model, is_uploaded: bool) -> None:
    with TwitterPostScraper(relationships_model) as scraper:
        scraper.scrape(is_uploaded=is_uploaded)
    logger.info("Scraping complete.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        relationships_model = load_graph(args.data)
        run_scraper(
            relationships_model,
            is_uploaded=not args.no_upload,
        )
    except FileNotFoundError as exc:
        logger.error("Data file not found: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
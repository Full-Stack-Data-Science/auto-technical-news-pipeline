import csv
import os
import logging
import datetime
import logging.config
import time
import random
import re

from typing import Dict, Any
from azure.storage.filedatalake import DataLakeServiceClient
from common.config import Config
import pandas as pd

def setup_logging():
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "level": "INFO",
                "formatter": "default",
                "class": "logging.StreamHandler",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default"],
                "level": "INFO",
            },
        },
    })

def dump_to_csv(row: Dict[str, Any], dir_path: str, file_name: str) -> None:
    """
    Append a single row of data to a CSV file.

    - Creates file if it does not exist
    - Writes header only once
    - Appends safely
    """
    os.makedirs(dir_path, exist_ok=True)
    full_path = os.path.join(dir_path, file_name)    
    file_exists = os.path.exists(full_path)

    # Ensure all values are serializable
    safe_row = {
        key: (value if isinstance(value, (str, int, float, bool)) else str(value))
        for key, value in row.items()
    }

    with open(full_path, mode="a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=safe_row.keys())

        if not file_exists:
            writer.writeheader()

        writer.writerow(safe_row)


def dump_to_parquet(row: Dict[str, Any], dir_path: str, file_name: str) -> None:
    """
    Append a single row of data to a parquet file.
    """
    os.makedirs(dir_path, exist_ok=True)
    full_path = os.path.join(dir_path, file_name)    

    # Ensure all values are serializable

    df = pd.DataFrame([row])
    
    if os.path.exists(full_path):
        existing = pd.read_parquet(full_path)
        df = pd.concat([existing, df], ignore_index=True)
    
    df.to_parquet(full_path, engine="pyarrow", index=False)


def human_scroll(driver, max_steps: int=6, min_px: int=300, max_px: int=600, pause_time: tuple = (1, 4)) -> None:
    for _ in range(1, max_steps):
        distance = random.randint(min_px, max_px)
        driver.execute_script(f"window.scrollBy(0, {distance});")
        time.sleep(random.uniform(*pause_time))

def extract_tweet_id(self, url: str) -> str:
    return url.rstrip("/").split("/")[-1]

def dump_to_html_bytes(driver, url):
    html = driver.page_source

    timestamp = datetime.now().isoformat()
    file_path = f"{extract_tweet_id(url)}_{timestamp}.html"
    print(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)

def upload_to_dls(file_path, file_name, data_source="twitter"):
    full_path = os.path.join(file_path, file_name)
    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"Local file not found: {full_path}")
    
    service_client = DataLakeServiceClient(
        account_url=f"https://{Config.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net",
        credential=Config.STORAGE_ACCOUNT_KEY,
    )
    filesystem_client = service_client.get_file_system_client(Config.FILE_SYSTEM_NAME)
    file_client = filesystem_client.get_file_client(f"{data_source}/raw/{file_name}")

    with open(full_path, "rb") as file_data:
        file_client.upload_data(
            file_data,
            overwrite=True
        )
    
    print("File uploaded successfully to ADLS Gen2")


def upload_parquet_to_dls(file_path, file_parquet, data_source="linkedin"):
    """
    Upload a Parquet file to Azure Data Lake Storage Gen2.

    This is a thin wrapper around upload_to_dls for clarity.
    """
    if not file_parquet.endswith(".parquet"):
        logging.warning(f"Expected a .parquet file, got {file_parquet} - uploading anyway")
    upload_to_dls(file_path, file_parquet, data_source=data_source)

def clean_file(file_path, file_csv):
    full_path = os.path.join(file_path, file_csv)

    if not os.path.isfile(full_path):
        return
    try:
        os.remove(full_path)
        print(f"Local file remove {full_path}")
    except OSError as e:
        print(f"Failed to remove file {full_path}: {e}")

def remove_whitespace(text: str) -> str:
    if text is None:
        return ""

    return re.sub(r"\s+", "", str(text))

def normalize_topic_list(topics) -> list[str]:
    if topics is None:
        return []

    # Map full topic names to hashtag-friendly abbreviations
    TOPIC_TO_HASHTAG = {
        "Natural Language Processing (NLP)": "NLP",
        "Machine Learning (ML)": "ML",
        "Computer Vision (CV)": "CV",
        "Generative AI": "GenAI",  
        "Data Analytics": "DataAnalytics",
        "Orchestration": "Orchestration",
        "Robotics": "Robotics",
    }
    
    normalized = []
    for item in topics:
        if not item:
            continue
        
        # Check if we have a mapping for this topic
        if item in TOPIC_TO_HASHTAG:
            normalized.append(TOPIC_TO_HASHTAG[item])
        else:
            # Extract abbreviation from parentheses if present
            # e.g., "Topic Name (ABBR)" -> "ABBR"
            match = re.search(r'\(([A-Z]+)\)', item)
            if match:
                normalized.append(match.group(1))
            else:
                # Remove whitespace and special chars for hashtag
                tag = remove_whitespace(item)
                normalized.append(tag)

    return normalized

def render_hashtags_from_topic(topic, max_tags=4) -> str:
    tags = normalize_topic_list(topic)
    
    tags = list(dict.fromkeys(tags))[:max_tags]
    
    # If no tags found, return empty string (don't render hashtags)
    if not tags:
        return ""

    # NOTE: LinkedIn rich-text editor expects consecutive spans without spaces
    # and the class attribute in the form class=ql-hashtag, e.g.:
    # <p><span class=ql-hashtag>#MachineLearning</span><span class=ql-hashtag>#meme</span></p>
    spans = "".join(
        f"<span class=ql-hashtag>#{tag}</span>"
        for tag in tags
    )

    # Add a trailing newline so when concatenated it matches expected HTML blocks
    return f"<p>{spans}</p>\n"


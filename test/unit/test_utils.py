import os
import csv
import logging
import tempfile
import unittest
import pandas as pd

from common.utils import dump_to_csv, dump_to_parquet, setup_logging

def test_setup_logging_does_not_raise():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully")

def test_logging_level_is_info():
    setup_logging()
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO

class TestDumpToFile(unittest.TestCase):
    def test_dump_to_csv_creates_file_and_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "data.csv")

            row = {
                "author": "karpathy",
                "likes": 100,
                "is_tech_related": True,
            }

            dump_to_csv(row, tmpdir, "data.csv") 
            self.assertTrue(os.path.exists(file_path))

            with open(file_path, newline="", encoding="utf-8") as f:
                reader = list(csv.reader(f))

            self.assertTrue(reader[0], list(row.keys()))
            self.assertEqual(reader[1], [str(value) for value in row.values()])
    

    def test_dump_to_parquet_with_pandas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = "test_twitter.parquet"
            file_path = os.path.join(temp_dir, file_name)

            row1 = {
                "username": "user1",
                "content": "This is about NLP and GPT",
                "topic": ["Natural Language Processing (NLP)", "Generative AI"],
                "supported_industry": ["Technology / AI"],
                "is_tech_related": True,
            }

            row2 = {
                "username": "user2",
                "content": "Business trends and ROI",
                "topic": ["Non-technical"],
                "supported_industry": ["Business"],
                "is_tech_related": False,
            }

            dump_to_parquet(row1, temp_dir, file_name)
            self.assertTrue(os.path.exists(file_path))
            
            dump_to_parquet(row2, temp_dir, file_name)

            df = pd.read_parquet(file_path)

            assert len(df) == 2
            assert df.iloc[0]["username"] == "user1"
            assert df.iloc[0]["topic"][0] == row1["topic"][0]
            assert df.iloc[1]["username"] == "user2"
            assert df.iloc[1]["is_tech_related"] == False
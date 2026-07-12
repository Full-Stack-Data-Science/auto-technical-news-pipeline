import io
import re
import pandas as pd
from datetime import date, datetime, timedelta
from common.storage.adls_client import ADLSClient


# Support both Twitter and LinkedIn filename patterns
TWITTER_FILENAME_PATTERN = re.compile(
    r"twitter_scraping_data_(\d{8})_(\d{6})\.parquet"
)

LINKEDIN_FILENAME_PATTERN = re.compile(
    r"linkedin_scraping_data_(\d{8})_(\d{6})\.parquet"
)


class PostRawReader:
    def __init__(self, adls_client: ADLSClient, raw_path: str):
        """
        raw_path example: twitter/raw or linkedin/raw
        """
        self.adls = adls_client
        self.raw_path = raw_path
        
        # Determine pattern based on path
        if "linkedin" in raw_path.lower():
            self.filename_pattern = LINKEDIN_FILENAME_PATTERN
        else:
            self.filename_pattern = TWITTER_FILENAME_PATTERN

    def _valid_dates(self, days_back: int) -> set[str]:
        today = date.today()
        return {
            (today - timedelta(days=i)).strftime("%Y%m%d")
            for i in range(days_back + 1)
        }

    def read_recent_days(self, days_back: int) -> pd.DataFrame:
        matched_paths = []

        for path in self.adls.list_paths(self.raw_path):

            match = self.filename_pattern.search(path.name)

            if not match:
                continue

            file_date, file_time = match.group(1), match.group(2)
            try:
                file_dt = datetime.strptime(f"{file_date}{file_time}", "%Y%m%d%H%M%S")
            except Exception:
                continue
            
            matched_paths.append((path.name, file_dt))
        
        # Determine "recent" relative to the newest file we can see in storage.
        # This avoids relying on the VM/container system clock/timezone.
        if not matched_paths:
            return pd.DataFrame()

        newest_dt = max(dt for _, dt in matched_paths)
        oldest_allowed_date = (newest_dt.date() - timedelta(days=days_back))
        
        matched_paths = [
            (path_name, dt)
            for path_name, dt in matched_paths
            if dt.date() >= oldest_allowed_date
        ]

        matched_paths.sort(key=lambda x: x[1], reverse=True)

        dfs = []

        for path_name, _ in matched_paths:
            file_client = self.adls.get_file_client(path_name)
            stream = file_client.download_file()
            data = stream.readall()
            dfs.append(pd.read_parquet(io.BytesIO(data)))

        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
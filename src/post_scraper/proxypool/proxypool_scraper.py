from dataclasses import dataclass, field
from typing import List, Iterable, Optional

from bs4 import BeautifulSoup

from scraping.core.web_scraper import IWebScraper
from scraping.core.web_parser import RequestWebParser
from common.config import Config

@dataclass
class ProxyRecord:
    ip_address: str
    port: str
    country_code: str
    country: str
    anonymity: str
    google: str
    https: str
    last_checked: str

    proxy: dict = field(init=False)

    def __post_init__(self) -> None:
        self.proxy = self._format_proxy()

    def _format_proxy(self) -> dict:
        protocol = "https" if self.https.lower() == "yes" else "http"
        url = f"{protocol}://{self.ip_address}:{self.port}"
        return {
            "http": url,
            "https": url,
        }

class ProxyPoolFormatter:
    """
    Responsible for parsing HTML and extracting raw proxy records.
    """

    def __init__(self) -> None:
        self.data: Optional[bytes] = None

    def set_data(self, html_data: bytes) -> None:
        self.data = html_data

    def extract_table_raw_records(self) -> List[List[str]]:
        if not self.data:
            return []

        soup = BeautifulSoup(self.data, "lxml")

        table = soup.find(id="list")
        if not table:
            return []

        rows = table.find_all("tr")
        return [
            self._clean_up_record(row)
            for row in rows
            if row.find_all("td")
        ]

    @staticmethod
    def _clean_up_record(raw_record) -> List[str]:
        return [cell.text for cell in raw_record.find_all("td")]


class ProxyPoolScraper(IWebScraper):
    """
    Scrapes proxy data from a public proxy listing website.
    """

    def __init__(
        self,
        formatter: Optional[ProxyPoolFormatter] = None,
        web_parser: Optional[RequestWebParser] = None,
    ) -> None:
        formatter = formatter or ProxyPoolFormatter()
        web_parser = web_parser or RequestWebParser(Config.PROXY_WEBPAGE)

        super().__init__(web_parser, formatter)

        self._load_html()

    def _load_html(self) -> None:
        """
        Fetch HTML content from the proxy source website.
        """
        try:
            html = self.parser.get_content(timeout=10)
            self.formatter.set_data(html)
        except Exception as err:
            raise RuntimeError(
                f"Failed to fetch proxy page: {err}"
            ) from err

    def scrape(self, limit: int = 50) -> Iterable[ProxyRecord]:
        """
        Public interface for scraping proxy records.
        """
        yield from self.get_proxy_stream(limit)

    def get_proxy_list(self, limit: int = 20) -> List[List[str]]:
        """
        Return a list of raw proxy records.
        """
        return self.formatter.extract_table_raw_records()[:limit]

    def get_proxy_stream(self, limit: int) -> Iterable[ProxyRecord]:
        """
        Yield ProxyRecord objects one by one.
        """
        for record in self.get_proxy_list(limit):
            try:
                yield ProxyRecord(*record)
            except TypeError:
                # Skip malformed rows
                continue
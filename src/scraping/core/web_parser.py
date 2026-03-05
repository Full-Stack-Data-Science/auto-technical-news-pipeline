import re
import random
import logging
import requests

from requests import get
from contextlib import closing
from typing import Optional, Dict, Any
from abc import ABC

from common.headers_list import headers_list
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class IWebParser(ABC):
    """
    Abstract base class for web parsers.
    Defines the common interface and shared behavior.
    """

    def __init__(self, url: str, rotate_header=False) -> None:
        self.url = url
        self.rotate_header=rotate_header
    
    def get_url(self) -> str:
        return self.url

    def get_header(self) -> Optional[Dict[str, str]]:
        if self.rotate_header:
            return random.choice(headers_list)
        return None
    
    @classmethod
    def get_content(self, **kwargs):
        """
        Fetch and return raw content from the URL.
        Must be implemented by subclasses.
        """
        raise NotImplementedError

    def __str__(self) -> str:
        domain = re.sub("(http[s]?://|www.)", "", self.url)
        return f"WebParser of {domain.upper()}"
    

class RequestWebParser(IWebParser):
    """
    Concrete implementation of IWebParser using `requests.get`
    to retrieve HTML or other web content.
    """
    def get_content(self, **kwargs):
        timeout = kwargs.get("timeout", 30) 
        proxies = kwargs.get("proxies")
        
        request_args: Dict[str, Any] = {
            "timeout": timeout,
            "proxies": proxies,
            "headers": self.get_header()
        }

        try:
            with closing(get(self.url, **request_args)) as response:
                if self._is_valid_response(response):
                    return response.content
                else:
                    logger.warning(
                        "Bad response received",
                        extra={
                            "url": self.url,
                            "status_code": response.status_code,
                        },
                    )

        except Exception as err:
            logger.error(
                "Error occurred while fetching content",
                exc_info=err,
                extra={"url": self.url},
            )

        return None

    @staticmethod
    def _is_valid_response(response: Optional[requests.Response]) -> bool:
        if (response is None):
            return False

        content_type = response.headers.get("Content-Type", "").lower()

        return (
            response.status_code == 200 
            and bool(content_type)
        )
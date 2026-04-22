from abc import ABC, abstractmethod

class IWebScraper(ABC):
    """
    Base interface for all web scrapers.
    - Coordinate a WebParser (fetching raw data)
    - Coordinate a Formatter (cleaning / transforming data)
    """
    def __init__(self, web_parser=None, formatter=None):
        self.parser    = web_parser
        self.formatter = formatter
    
    @abstractmethod
    def scrape(self):
        raise NotImplementedError

    def set_formatter(self, formatter) -> None:
        self.formatter = formatter
    
    def set_parser(self, parser) -> None:
        self.parser = parser
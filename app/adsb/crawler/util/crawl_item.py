from dataclasses import dataclass


@dataclass
class CrawlItem:
    """Represents an aircraft to be crawled for metadata"""
    icao24: str
    
    def __str__(self) -> str:
        return f"CrawlItem(icao24={self.icao24})"
    
    def __repr__(self) -> str:
        return self.__str__()
import logging
from collections import OrderedDict
from typing import Set

logger = logging.getLogger(__name__)


class AircraftCache:
    """LRU cache for tracking successfully processed aircraft to avoid duplicate work."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, bool] = OrderedDict()
    
    def add(self, icao24: str) -> None:
        """Add aircraft to cache with LRU eviction"""
        
        if icao24 in self._cache:
            del self._cache[icao24]
        
        self._cache[icao24] = True
        
        # Remove oldest if cache is full
        while len(self._cache) > self.max_size:
            oldest_icao24 = next(iter(self._cache))
            del self._cache[oldest_icao24]
            logger.debug(f"Removed {oldest_icao24} from processed cache (cache full)")
    
    def contains(self, icao24: str) -> bool:
        """Check if aircraft has been processed recently"""
        return icao24 in self._cache
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)
    
    def clear(self) -> None:
        """Clear all cached entries"""
        self._cache.clear()
    
    def get_all(self) -> Set[str]:
        """Get all cached ICAO24 addresses (for debugging/monitoring)"""
        return set(self._cache.keys())
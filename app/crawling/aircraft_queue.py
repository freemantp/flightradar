import logging
import threading
from collections import deque
from typing import Set, Optional

logger = logging.getLogger(__name__)


class SharedAircraftQueue:
    """Thread-safe shared queue for new aircraft between flight updater and crawler."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue: deque[str] = deque(maxlen=max_size)
        self._known_aircraft: Set[str] = set()
        self._lock = threading.RLock()
    
    def add_aircraft(self, icao24s: Set[str]) -> int:
        """
        Add new aircraft to the queue if not already seen.
        
        Args:
            icao24s: Set of ICAO24 addresses to add
            
        Returns:
            Number of new aircraft added
        """
        with self._lock:
            new_count = 0
            for icao24 in icao24s:
                if icao24 not in self._known_aircraft:
                    self._queue.append(icao24)
                    self._known_aircraft.add(icao24)
                    new_count += 1
                    
            if new_count > 0:
                logger.debug(f"Added {new_count} new aircraft to shared queue")
                
            return new_count
    
    def get_aircraft(self, max_items: int = 100) -> Set[str]:
        """
        Get up to max_items aircraft from the queue.
        
        Args:
            max_items: Maximum number of aircraft to retrieve
            
        Returns:
            Set of ICAO24 addresses to process
        """
        with self._lock:
            aircraft = set()
            items_retrieved = 0
            
            while self._queue and items_retrieved < max_items:
                icao24 = self._queue.popleft()
                aircraft.add(icao24)
                items_retrieved += 1
                
            if aircraft:
                logger.debug(f"Retrieved {len(aircraft)} aircraft from shared queue")
                
            return aircraft
    
    def size(self) -> int:
        """Get current queue size"""
        with self._lock:
            return len(self._queue)
    
    def clear(self) -> None:
        """Clear the queue and known aircraft set"""
        with self._lock:
            self._queue.clear()
            self._known_aircraft.clear()
            logger.info("Cleared shared aircraft queue")


# Global shared queue instance
shared_aircraft_queue = SharedAircraftQueue()
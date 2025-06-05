import logging
from typing import Dict, List, Tuple, Set, Optional, Any
from datetime import datetime
from .mongodb_repository import MongoDBRepository

logger = logging.getLogger('FlightRepository')

class FlightRepository:
    def __init__(self, db_repo: MongoDBRepository) -> None:
        self.db_repo = db_repo
        
    def get_or_create_flight(self, **kwargs) -> Dict[str, Any]:
        """Get or create a flight with the given parameters"""
        return self.db_repo.get_or_create_flight(**kwargs)
        
    def bulk_update_flights(self, updates: List[Tuple[str, Dict[str, Any]]]) -> None:
        """Update multiple flights in a single operation"""
        return self.db_repo.bulk_update_flights(updates)
        
    def get_flights_batch(self, modeS_addresses: Set[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Get a batch of flights by ModeS addresses"""
        return self.db_repo.get_flights_batch(modeS_addresses)
        
    def get_recent_flights_last_pos(self, timestamp: datetime, page_size: int = 100, last_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent flights with their last position"""
        return self.db_repo.get_recent_flights_last_pos(timestamp, page_size, last_id)
        
    def get_last_positions(self) -> Dict[str, 'PositionReport']:
        from ...core.models.position_report import PositionReport
        
        # Get all flights with their last positions
        results = self.db_repo.get_all_flights_last_pos()
        positions = {}
        
        for result in results:
            if "flight" in result and "position" in result:
                flight = result["flight"]
                position = result["position"]
                flight_id = str(flight["_id"])
                
                pos_report = PositionReport(
                    flight["modeS"], position["lat"], position["lon"],
                    position.get("alt"), position.get("track", 0.0), flight.get("callsign"))
                    
                positions[flight_id] = pos_report
                
        return positions
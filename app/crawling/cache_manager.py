import logging
from datetime import datetime, timedelta, timezone

from ..core.models.position_report import PositionReport
from ..core.utils.time_util import make_datetimes_comparable

logger = logging.getLogger('CacheManager')

class CacheManager:
    def __init__(self):
        self.modeS_flightid_map = dict()
        self.flight_lastpos_map = dict()
        self.flight_last_contact = dict()
        self.positions_hash = set()
        
    def initialize_from_db(self, repository, threshold_timestamp):
        """Initialize cache from database"""
        # Use pagination for large datasets to optimize memory usage
        page_size = 100
        last_id = None
        more_results = True

        while more_results:
            results = repository.get_recent_flights_last_pos(
                threshold_timestamp,
                page_size=page_size,
                last_id=last_id
            )

            if not results:
                more_results = False
                continue

            # Store the last ID for pagination
            last_result = results[-1]
            last_id = last_result["flight"]["_id"]

            # Process the current page of results
            for result in results:
                flight = result["flight"]
                position = result["position"]
                flight_id = str(flight["_id"])

                self.modeS_flightid_map[flight["modeS"]] = flight_id

                pos_report = PositionReport(
                    flight["modeS"], position["lat"], position["lon"],
                    position.get("alt"), position.get("track", 0.0), flight.get("callsign"))

                self.flight_lastpos_map[flight_id] = pos_report
                self.flight_last_contact[flight_id] = flight["last_contact"]

                # Add position hash to avoid duplicates
                pos_hash = hash((round(position["lat"], 5), round(position["lon"], 5), position.get("alt")))
                self.positions_hash.add(pos_hash)

            if len(results) < page_size:
                more_results = False
                
    def get_current_flights(self):
        """Get all flights with a recent position (within the last minute)"""
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        result = {}
        for k, v in self.modeS_flightid_map.items():
            if v in self.flight_lastpos_map:
                # Get the last contact time for this flight
                last_contact = self.flight_last_contact[v]
                
                # Make timestamps comparable using our utility function
                comparable_last_contact, comparable_timestamp = make_datetimes_comparable(
                    last_contact, timestamp
                )
                
                if comparable_last_contact > comparable_timestamp:
                    result[v] = self.flight_lastpos_map[v]
                    
        return result
        
    def update_position(self, flight_id, position, timestamp):
        """Update a flight's position in the cache"""
        self.flight_lastpos_map[flight_id] = position
        self.flight_last_contact[flight_id] = timestamp
        
    def update_flight_mapping(self, modeS, flight_id):
        """Update the mapping from Mode-S to flight ID"""
        self.modeS_flightid_map[modeS] = flight_id
        
    def reset_position_hash_if_needed(self, max_size=150000):
        """Reset the position hash cache if it gets too large"""
        if len(self.positions_hash) > max_size:
            self.positions_hash = set()
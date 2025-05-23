import logging
from typing import Dict, List
from datetime import datetime, timezone
from bson import ObjectId

from ..model.position_report import PositionReport

logger = logging.getLogger('PositionManager')

class PositionManager:
    def __init__(self, config):
        self._insert_batch_size = 200
        self.positions_hash = set()
        self.flight_lastpos_map = dict()
        self._changed_flight_ids = set()
        self._positions_changed = False

    def initialize(self, repository):
        self.repository = repository
        
    def clear_changes(self):
        """Reset change tracking"""
        self._positions_changed = False
        self._changed_flight_ids.clear()
        
    def add_positions(self, positions: List[PositionReport], flight_manager):
        """Inserts positions into the database with highly optimized batch processing"""

        if not positions:
            return
            
        now = datetime.now(timezone.utc)
        
        flight_id_by_icao = {}                
        existing_icao_set = set(flight_manager.modeS_flightid_map.keys())
        valid_positions = []
        
        # Filter in one pass, storing flight_id lookup for later use
        for pos in positions:
            if pos.icao24 in existing_icao_set:
                valid_positions.append(pos)
                flight_id_by_icao[pos.icao24] = flight_manager.modeS_flightid_map[pos.icao24]
                
        if not valid_positions:
            return
            
        all_positions_to_insert = []
        all_flight_updates = []
        position_count = 0

        # Process positions in batches, this avoids large arrays that could cause memory pressure
        position_batches = [valid_positions[i:i+self._insert_batch_size] for i in range(0, len(valid_positions), self._insert_batch_size)]
        
        for batch in position_batches:
            positions_to_insert, flight_updates = self._process_position_batch(
                batch, flight_id_by_icao, now, flight_manager
            )
            
            if positions_to_insert:
                all_positions_to_insert.extend(positions_to_insert)
                position_count += len(positions_to_insert)
                
            if flight_updates:
                all_flight_updates.extend(flight_updates)
                
        # Perform DB operations in optimal batches
        if all_positions_to_insert:
            for i in range(0, len(all_positions_to_insert), self._insert_batch_size):
                batch = all_positions_to_insert[i:i+self._insert_batch_size]
                self.repository.insert_positions(batch)

            if all_flight_updates:
                # Remove duplicates to avoid redundant updates
                seen_flights = set()
                unique_updates = []
                
                for flight_id, timestamp in all_flight_updates:
                    if flight_id not in seen_flights:
                        seen_flights.add(flight_id)
                        unique_updates.append((flight_id, timestamp))
                        
                self.repository.bulk_update_flight_last_contacts(unique_updates)

        # Grow the position hash cache to improve hit rates, but reset if too large
        if len(self.positions_hash) > 150000:  # Increased threshold for better caching
            self.positions_hash = set()
            
    def _process_position_batch(self, batch, flight_id_by_icao, timestamp, flight_manager):
        """Process a batch of positions efficiently"""
        positions_to_insert = []
        flight_updates = []
        
        # Pre-compute hashes for this batch in one pass, this avoids repeated calculations
        position_hashes = {}
        for pos in batch:
            pos_hash = hash((round(pos.lat, 5), round(pos.lon, 5), pos.alt))
            position_hashes[pos.icao24] = pos_hash
            
        new_hashes = set()
        
        for pos in batch:
            icao24 = pos.icao24
            flight_id = flight_id_by_icao[icao24]
            pos_hash = position_hashes[icao24]
            
            if pos_hash in self.positions_hash:
                continue
                
            new_hashes.add(pos_hash)            
            store_position = True
            
            if flight_id in self.flight_lastpos_map:
                last_pos = self.flight_lastpos_map[flight_id]
                
                last_pos_hash = hash((
                    round(last_pos.lat, 5),
                    round(last_pos.lon, 5),
                    last_pos.alt
                ))
                
                if last_pos_hash == pos_hash:
                    store_position = False
            
            if store_position:
                
                # Update in-memory cache immediately
                flight_manager.flight_last_contact[flight_id] = timestamp
                self.flight_lastpos_map[flight_id] = pos
                
                # Mark for WebSocket notification
                self._positions_changed = True
                self._changed_flight_ids.add(str(flight_id))
                
                position_doc = {
                    "flight_id": ObjectId(flight_id),
                    "lat": pos.lat,
                    "lon": pos.lon,
                    "alt": pos.alt,
                    "track": pos.track,
                    "timestmp": timestamp
                }
                
                positions_to_insert.append(position_doc)
                
                flight_updates.append((flight_id, timestamp))
        
        self.positions_hash.update(new_hashes)
        
        return positions_to_insert, flight_updates
    
    def get_cached_flights(self, flight_manager) -> Dict[str, PositionReport]:
        """Get all cached flights with a recent position report (within the last minute)"""
        from datetime import timedelta
        from ..util.time_util import make_datetimes_comparable
        
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        result = {}
        for k, v in flight_manager.modeS_flightid_map.items():
            if v in self.flight_lastpos_map:
                
                last_contact = flight_manager.flight_last_contact[v]
                
                comparable_last_contact, comparable_timestamp = make_datetimes_comparable(
                    last_contact, timestamp
                )
                
                if comparable_last_contact > comparable_timestamp:
                    result[v] = self.flight_lastpos_map[v]
                    
        return result
        
    def has_positions_changed(self):
        """Check if positions have changed since last update"""
        return self._positions_changed
        
    def get_changed_flight_ids(self):
        """Get the set of flight IDs that have changed positions"""
        return self._changed_flight_ids
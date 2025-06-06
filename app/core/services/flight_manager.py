import logging
from typing import List
from datetime import datetime, timedelta, timezone

from ..utils.modes_util import ModesUtil
from ..utils.time_util import make_datetimes_comparable
from ..models.position_report import PositionReport
from ..constants import MINUTES_BEFORE_CONSIDERED_NEW_FLIGHT

logger = logging.getLogger('FlightManager')

class FlightManager:
    BATCH_SIZE = 200

    def __init__(self, config):
        self.mil_ranges = ModesUtil(config.DATA_FOLDER)
        self.mil_only = config.MILTARY_ONLY
        self._flight_callsign_cache = {}
        self.modeS_flightid_map = dict()
        self.flight_last_contact = dict()
        self._use_ttl_indexes = True
        self._retention_minutes = config.DB_RETENTION_MIN
        
        self._use_ttl_indexes = True
        if self._retention_minutes <= 0:
            self._use_ttl_indexes = False
            logger.info("Document expiration disabled: no retention period specified")

    def initialize(self, repository):
        """Initializes cache from database with optimized loading"""
        self.repository = repository
        recent_flight_timestamp = self._threshold_timestamp()
        logger.info(f"Loading flights newer than {recent_flight_timestamp}")

        page_size = 100
        last_id = None
        more_results = True
        total_loaded = 0

        while more_results:
            results = self.repository.get_recent_flights_last_pos(
                recent_flight_timestamp,
                page_size=page_size,
                last_id=last_id
            )

            if not results:
                more_results = False
                continue

            last_result = results[-1]
            last_id = last_result["flight"]["_id"]

            for result in results:
                flight = result["flight"]
                position = result["position"]
                flight_id = str(flight["_id"])

                self.modeS_flightid_map[flight["modeS"]] = flight_id

                pos_report = PositionReport(
                    flight["modeS"], position["lat"], position["lon"],
                    position.get("alt"), position.get("track", 0.0), flight.get("callsign"))
                
                self.flight_last_contact[flight_id] = flight["last_contact"]
                
                if flight.get("callsign"):
                    self._flight_callsign_cache[flight_id] = flight["callsign"].strip().upper() if flight["callsign"] else ""
                
                total_loaded += 1

            if len(results) < page_size:
                more_results = False
            else:
                logger.debug(f"Loaded {total_loaded} flights so far...")
        
        logger.info(f"Flight manager cache initialized with {total_loaded} recent flights")
    
    def _threshold_timestamp(self):
        """
        Returns a threshold timezone-aware timestamp for flight activity cutoff
        """
        return datetime.now(timezone.utc) - timedelta(minutes=MINUTES_BEFORE_CONSIDERED_NEW_FLIGHT)
        
    def update_flights(self, flights: List[PositionReport]):
        """
        Inserts and updates flights in the database with optimized batch processing
        """
        if not flights:
            return [], []
            
        flights_by_icao = {}
        for f in flights:
            flights_by_icao[f.icao24] = f
            
        flight_batches = [flights[i:i+self.BATCH_SIZE] for i in range(0, len(flights), self.BATCH_SIZE)]
        
        all_inserted = []
        all_updated = []
        
        now = datetime.now(timezone.utc)
        thresh_timestmp = self._threshold_timestamp()
            
        for batch in flight_batches:
            self._process_flight_batch(
                batch, 
                flights_by_icao,
                thresh_timestmp, 
                now, 
                all_inserted, 
                all_updated
            )
            
        if all_inserted:
            inserted_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in all_inserted[:5]])
            if len(all_inserted) > 5:
                inserted_msg += f" and {len(all_inserted) - 5} more"
            logger.info(f'addFlights: {inserted_msg}')

        if all_updated:
            updated_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in all_updated[:5]])
            if len(all_updated) > 5:
                updated_msg += f" and {len(all_updated) - 5} more"
            logger.info(f'updateFlights: {updated_msg}')
            
        return all_inserted, all_updated
    
    def _should_create_new_flight(self, modeS, flight_id, threshold, flights_by_icao=None, new_callsign=None):
        """Determine if a new flight should be created based on last contact time and callsign"""
        
        if not flight_id or flight_id not in self.flight_last_contact:
            return True
            
        last_contact = self.flight_last_contact[flight_id]    
        last_contact, threshold_comparable = make_datetimes_comparable(last_contact, threshold)
        
        if last_contact <= threshold_comparable:
            return True
            
        if flights_by_icao and new_callsign:
            if new_callsign and modeS in self.modeS_flightid_map:
                flight_id = self.modeS_flightid_map[modeS]
                
                db_callsign = None
                
                if flight_id in self._flight_callsign_cache:
                    db_callsign = self._flight_callsign_cache[flight_id]
                elif modeS in flights_by_icao:
                        pos = flights_by_icao[modeS]
                        if hasattr(pos, 'callsign'):
                            db_callsign = pos.callsign.strip().upper() if pos.callsign else ""
                
                if db_callsign and new_callsign != db_callsign:
                    return True
                    
        return False

    def _create_flight(self, modeS, callsign, is_military, now, inserted_flights):
        """Create a new flight entry"""
        try:
            flight_data = {
                "modeS": modeS,
                "is_military": is_military
            }
            
            if callsign:
                flight_data["callsign"] = callsign
            
            if self._use_ttl_indexes and self._retention_minutes > 0:
                flight_data["expire_at"] = now + timedelta(minutes=self._retention_minutes)
            
            flight_obj = self.repository.get_or_create_flight(**flight_data)
            flight_id = str(flight_obj["_id"])
            
            self.modeS_flightid_map[modeS] = flight_id
            self.flight_last_contact[flight_id] = now
            
            if callsign:
                self._flight_callsign_cache[flight_id] = callsign.strip().upper() if callsign else ""
                
            inserted_flights.append((modeS, callsign))
            return flight_id
        except Exception as e:
            logger.error(f"Error creating flight for {modeS}: {str(e)}")
            return None
    
    def _update_flight(self, modeS, flight_id, f, now, update_data, callsign_updates, updated_flights):
        """Update an existing flight"""
        
        new_callsign = f.callsign.strip().upper() if f.callsign else ""
        
        db_callsign = None
        if flight_id in self._flight_callsign_cache:
            db_callsign = self._flight_callsign_cache[flight_id]
        
        if new_callsign and db_callsign != new_callsign:
            update_data["callsign"] = f.callsign
            callsign_updates.append((flight_id, update_data))
            updated_flights.append((modeS, f.callsign))
            
            self._flight_callsign_cache[flight_id] = new_callsign
        else:
            callsign_updates.append((flight_id, update_data))
        
        self.modeS_flightid_map[modeS] = flight_id
        self.flight_last_contact[flight_id] = now
    
    def _process_flight_batch(self, batch, flights_by_icao, thresh_timestmp, now, inserted_flights, updated_flights):
        """Process a batch of flights for better memory management and performance"""
        batch_modes = set(f.icao24 for f in batch)
        
        if not batch_modes:
            return
            
        known_modes = set()
        unknown_modes = set()        
        callsign_updates = []
        new_flights = []
        
        for modeS in batch_modes:
            if modeS in self.modeS_flightid_map:
                flight_id = self.modeS_flightid_map[modeS]
                if flight_id in self.flight_last_contact:
                    if self._should_create_new_flight(modeS, flight_id, thresh_timestmp):
                        unknown_modes.add(modeS)
                    else:
                        known_modes.add(modeS)
                else:
                    unknown_modes.add(modeS)
            else:
                unknown_modes.add(modeS)
                
        if known_modes:
            for modeS in known_modes:
                flight_id = self.modeS_flightid_map[modeS]
                f = flights_by_icao[modeS]
                
                update_data = {"last_contact": now}
                
                # Add expiration time if TTL indexes are enabled
                if self._use_ttl_indexes and self._retention_minutes > 0:
                    update_data["expire_at"] = now + timedelta(minutes=self._retention_minutes)
                
                self._update_flight(modeS, flight_id, f, now, update_data, callsign_updates, updated_flights)
                
        if not unknown_modes:
            if callsign_updates:
                self.repository.bulk_update_flights(callsign_updates)
            return
            
        flights_by_modeS = self.repository.get_flights_batch(unknown_modes)
        
        for modeS in unknown_modes:
            f = flights_by_icao[modeS]
            new_callsign = f.callsign.strip().upper() if f.callsign else ""
            
            if modeS not in flights_by_modeS:
                new_flights.append((modeS, f.callsign, self.mil_ranges.is_military(modeS)))
                continue
                
            db_flights = flights_by_modeS[modeS]
            matching_flight = None
            
            for flight in db_flights:
                if not matching_flight:
                    flight_last_contact = flight["last_contact"]
                    flight_last_contact, comparison_timestamp = make_datetimes_comparable(
                        flight_last_contact, thresh_timestmp
                    )
                    
                    if flight_last_contact > comparison_timestamp:
                        db_callsign = flight.get("callsign", "").strip().upper() if flight.get("callsign") else ""                        

                        callsign_match = (db_callsign and new_callsign and db_callsign == new_callsign) or \
                                         (not db_callsign and not new_callsign)
                                         
                        if callsign_match or not new_callsign:
                            matching_flight = flight
                            break
            
            if not matching_flight and db_flights:
                most_recent = db_flights[0]
                flight_last_contact = most_recent["last_contact"]
                flight_last_contact, comparison_timestamp = make_datetimes_comparable(
                    flight_last_contact, thresh_timestmp
                )
                
                if flight_last_contact > comparison_timestamp:
                    db_callsign = most_recent.get("callsign", "").strip().upper() if most_recent.get("callsign") else ""
                    
                    if new_callsign and db_callsign != new_callsign:
                        # Callsign mismatch, create a new flight
                        matching_flight = None 
                    else:
                        matching_flight = most_recent
                else:
                    # Flight is older than the threshold, but don't create it yet, we'll check later
                    logger.info(f"Flight for {modeS} is too old: {flight_last_contact}")
                    matching_flight = None  
            
            if matching_flight:
                flight_id = str(matching_flight["_id"])
                
                update_data = {"last_contact": now}
                
                # Add expiration time if TTL indexes are enabled
                if self._use_ttl_indexes and self._retention_minutes > 0:
                    update_data["expire_at"] = now + timedelta(minutes=self._retention_minutes)
                
                self._update_flight(modeS, flight_id, f, now, update_data, callsign_updates, updated_flights)
                
                db_callsign = matching_flight.get("callsign", "").strip().upper() if matching_flight.get("callsign") else ""
                self._flight_callsign_cache[flight_id] = db_callsign
            else:
                # No matching flight found, create a new one
                new_flights.append((modeS, f.callsign, self.mil_ranges.is_military(modeS)))
        
        if callsign_updates:
            self.repository.bulk_update_flights(callsign_updates)
        
        if new_flights:
            for modeS, callsign, is_military in new_flights:
                self._create_flight(modeS, callsign, is_military, now, inserted_flights)

    def is_military(self, modeS):
        """Check if a Mode-S code belongs to a military aircraft"""
        return self.mil_ranges.is_military(modeS)
        
    def filter_military_only(self, positions):
        """Filter for military aircraft only if enabled"""
        if not self.mil_only:
            return positions
            
        # Fast filtering with set lookups
        mil_icao_set = set()
        for pos in positions:
            if self.mil_ranges.is_military(pos.icao24):
                mil_icao_set.add(pos.icao24)
                
        return [pos for pos in positions if pos.icao24 in mil_icao_set]
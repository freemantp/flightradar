import logging
import threading
from typing import Any, Dict, List, Callable, Set, Tuple
from time import sleep
from datetime import datetime, timedelta, timezone
from timeit import default_timer as timer
from bson import ObjectId

from .datasource.modesmixer import ModeSMixer
from .datasource.virtualradarserver import VirtualRadarServer
from .datasource.dump1090 import Dump1090
from .util.modes_util import ModesUtil
from .util.time_util import make_datetimes_comparable
from .db.mongodb_repository import MongoDBRepository
from .model.position_report import PositionReport
from ..config import app_state

logger = logging.getLogger('Updater')


class FlightUpdater:
    MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT = 10
    _update_lock = threading.RLock()

    def __init__(self):
        self.is_updating = False
        self.sleep_time = 1
        self._t = None
        self._websocket_callbacks: Set[Callable] = set()
        self._previous_positions: Dict[str, PositionReport] = {}
        self._positions_changed = False
        self._changed_flight_ids: Set[str] = set()

    def initialize(self, config):
        if config.RADAR_SERVICE_TYPE == 'mm2':
            self._service = ModeSMixer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'vrs':
            self._service = VirtualRadarServer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'dmp1090':
            self._service = Dump1090(config.RADAR_SERVICE_URL)
        else:
            raise ValueError('Service type not specified in config')

        self._mil_ranges = ModesUtil(config.DATA_FOLDER)
        self._mil_only = config.MILTARY_ONLY
        self.interrupted = False

        self._insert_batch_size = 200
        self._delete_after = config.DB_RETENTION_MIN

        self._cleanup_counter = 0
        self._cleanup_frequency_sec = 10

        self.db_repo = MongoDBRepository(app_state.mongodb)

        # Lookup structures
        self.modeS_flightid_map = dict()
        self.flight_lastpos_map = dict()
        self.flight_last_contact = dict()
        self.positions_hash = set()
        self._initialize_from_db()

    def is_service_alive(self):
        return self._service.connection_alive

    def get_cached_flights(self) -> Dict[str, PositionReport]:
        """
        Get all cached flights with a recent position report (within the last minute)
        Handles both timezone-aware and timezone-naive datetime comparisons
        """
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

    def register_websocket_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Register a callback function to notify when positions are updated
        The callback will receive a dictionary of flight IDs mapped to position reports
        """
        self._websocket_callbacks.add(callback)
        return callback
        
    def unregister_websocket_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Unregister a previously registered callback
        """
        if callback in self._websocket_callbacks:
            self._websocket_callbacks.remove(callback)
            return True
        return False

    def cleanup_items(self):
        if self._delete_after > 0:
            delete_timestamp = datetime.now(timezone.utc) - timedelta(minutes=self._delete_after)

            flights_to_delete = self.db_repo.get_non_archived_flights_older_than(delete_timestamp)

            if flights_to_delete:
                # Delete from DB
                flight_ids = [str(f["_id"]) for f in flights_to_delete]
                self.db_repo.delete_flights_and_positions(flight_ids)

                # Update cache
                for flight in flights_to_delete:
                    self.modeS_flightid_map.pop(flight["modeS"], None)
                    self.flight_lastpos_map.pop(str(flight["_id"]), None)
                    self.flight_last_contact.pop(str(flight["_id"]), None)

                deleted_msg = ', '.join(['{} (cs={})'.format(str(f["_id"]), f.get("callsign", ""))
                                        for f in flights_to_delete])
                logger.info(f'aircraftEvent=delete {deleted_msg}')

    def _threshold_timestamp(self):
        """
        Returns a threshold timezone-aware timestamp for flight activity cutoff
        """
        return datetime.now(timezone.utc) - timedelta(minutes=self.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)

    def _initialize_from_db(self):
        """Initializes cache from database with optimized loading"""
        recent_flight_timestamp = self._threshold_timestamp()

        # Use pagination for large datasets to optimize memory usage
        page_size = 100
        last_id = None
        more_results = True

        while more_results:
            results = self.db_repo.get_recent_flights_last_pos(
                recent_flight_timestamp,
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
                    position.get("alt"), 0.0, flight.get("callsign"))

                self.flight_lastpos_map[flight_id] = pos_report
                self.flight_last_contact[flight_id] = flight["last_contact"]

                # Add position hash to avoid duplicates
                pos_hash = hash((round(position["lat"], 5), round(position["lon"], 5), position.get("alt")))
                self.positions_hash.add(pos_hash)

            if len(results) < page_size:
                more_results = False

    def update(self):
        # Use thread lock to prevent concurrent updates
        # Non-blocking acquisition - if locked, just return instead of waiting
        if not FlightUpdater._update_lock.acquire(blocking=False):
            logger.debug("Update already in progress, skipping this cycle")
            return

        try:
            self.is_updating = True
            self._positions_changed = False
            self._changed_flight_ids.clear() 

            # Measure service time
            start_time = timer()
            positions = self._service.query_live_flights(False)
            service_time = timer() - start_time

            # Short-circuit if no positions
            if not positions:
                # Reset cycle counters
                self._cleanup_counter += 1
                if self._cleanup_counter >= self._cleanup_frequency_sec:
                    cleanup_start = timer()
                    self.cleanup_items()
                    self._cleanup_counter = 0
                return

            # Processing time measurement
            process_start = timer()
            flight_update_time = 0
            position_update_time = 0
            cleanup_time = 0
            websocket_time = 0

            try:
                # Pre-filter positions once at the beginning
                # Check if military filtering is enabled and apply filter
                if self._mil_only:
                    # Fast filtering with set lookups
                    mil_icao_set = set()
                    for pos in positions:
                        if self._mil_ranges.is_military(pos.icao24):
                            mil_icao_set.add(pos.icao24)
                    
                    filtered_pos = [pos for pos in positions if pos.icao24 in mil_icao_set]
                else:
                    filtered_pos = positions

                # Exit early if no positions after filtering
                if not filtered_pos:
                    return

                # Pre-filter valid positions with coordinates for more efficient processing
                valid_positions = [p for p in filtered_pos if p.lat and p.lon]

                # Process the updates in optimal order
                
                # 1. Update flights first - fastest code path when cache is warm
                flight_start = timer()
                self.update_flights(filtered_pos)
                flight_update_time = timer() - flight_start

                # 2. Store current positions for comparison with new ones
                current_positions = {}
                if self._websocket_callbacks:
                    # Only compute if we have WebSocket callbacks
                    current_positions = self.get_cached_flights()

                # 3. Add new positions efficiently
                position_start = timer()
                self.add_positions(valid_positions)
                position_update_time = timer() - position_start

                # 4. Broadcast positions via WebSocket if needed
                if self._websocket_callbacks and self._positions_changed and len(self._changed_flight_ids) > 0:
                    websocket_start = timer()

                    # Get only the flights that actually changed
                    all_cached_flights = self.get_cached_flights()
                    
                    # Create a dict with only changed flight positions using set operations for efficiency
                    changed_flight_ids = self._changed_flight_ids
                    
                    # Create positions dict directly from changed flights - avoid double filtering
                    positions_dict = {}
                    for flight_id, pos in all_cached_flights.items():
                        if str(flight_id) in changed_flight_ids:
                            positions_dict[str(flight_id)] = {
                                "lat": pos.lat,
                                "lon": pos.lon,
                                "alt": pos.alt
                            }
                    
                    # Fallback if no positions matched (should be rare)
                    if not positions_dict and all_cached_flights:
                        # Only log if we have cached flights but none matched our changed IDs
                        logger.warning("No changed positions match cached flights")
                        # We'll just use a subset of all positions to avoid overwhelming the system
                        count = 0
                        for flight_id, pos in all_cached_flights.items():
                            if count < 50:  # Limit to 50 positions
                                positions_dict[str(flight_id)] = {
                                    "lat": pos.lat,
                                    "lon": pos.lon,
                                    "alt": pos.alt
                                }
                                count += 1
                            else:
                                break

                    # Only broadcast if we have data to send
                    if positions_dict:
                        callback_count = len(self._websocket_callbacks)
                        
                        # Call each callback in a controlled manner
                        callbacks_to_remove = set()
                        for callback in self._websocket_callbacks:
                            try:
                                callback(positions_dict)
                            except Exception as e:
                                logger.error(f"Error in WebSocket callback: {str(e)}")
                                callbacks_to_remove.add(callback)
                        
                        # Clean up failed callbacks
                        if callbacks_to_remove:
                            self._websocket_callbacks.difference_update(callbacks_to_remove)

                    websocket_time = timer() - websocket_start

                # 5. Cleanup cycle if needed
                self._cleanup_counter += 1
                if self._cleanup_counter >= self._cleanup_frequency_sec:
                    cleanup_start = timer()
                    self.cleanup_items()
                    cleanup_time = timer() - cleanup_start
                    self._cleanup_counter = 0

            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                logger.exception(f"An error occurred: {str(e)}")

            # Calculate processing time
            process_time = timer() - process_start
            total_time = service_time + process_time

            # Only log if processing took significant time
            if total_time > 0.2:  # Reduced logging threshold
                logger.info(
                    f'Flight data times: total={total_time*1000:.2f}ms, '
                    f'service={service_time*1000:.2f}ms, '
                    f'process={process_time*1000:.2f}ms '
                    f'(flight={flight_update_time*1000:.2f}ms, '
                    f'position={position_update_time*1000:.2f}ms, '
                    f'websocket={websocket_time*1000:.2f}ms, '
                    f'cleanup={cleanup_time*1000:.2f}ms)'
                )
        finally:
            self.is_updating = False
            FlightUpdater._update_lock.release()

    def add_positions(self, positions: List[PositionReport]):
        """Inserts positions into the database with highly optimized batch processing"""
        # Skip if no positions to process
        if not positions:
            return
            
        # Get current time once
        now = datetime.now(timezone.utc)
        
        # Pre-filter positions in one pass with set membership test (very fast)
        flight_id_by_icao = {}
        valid_positions = []
        
        # Create a set of existing icao24 addresses for faster lookups
        existing_icao_set = set(self.modeS_flightid_map.keys())
        
        # Filter in one pass, storing flight_id lookup for later use
        for pos in positions:
            if pos.icao24 in existing_icao_set:
                valid_positions.append(pos)
                flight_id_by_icao[pos.icao24] = self.modeS_flightid_map[pos.icao24]
                
        # Skip if nothing to process
        if not valid_positions:
            return
            
        # Process positions in batches for better memory management
        # This avoids large arrays that could cause memory pressure
        batch_size = 200
        position_batches = [valid_positions[i:i+batch_size] for i in range(0, len(valid_positions), batch_size)]
        
        # Track all DB operations across batches
        all_positions_to_insert = []
        all_flight_updates = []
        position_count = 0
        
        # Process each batch
        for batch in position_batches:
            positions_to_insert, flight_updates = self._process_position_batch(
                batch, flight_id_by_icao, now
            )
            
            # Collect results
            if positions_to_insert:
                all_positions_to_insert.extend(positions_to_insert)
                position_count += len(positions_to_insert)
                
            if flight_updates:
                all_flight_updates.extend(flight_updates)
                
        # Perform DB operations in optimal batches
        if all_positions_to_insert:
            # Insert positions in optimized batches
            for i in range(0, len(all_positions_to_insert), self._insert_batch_size):
                batch = all_positions_to_insert[i:i+self._insert_batch_size]
                self.db_repo.insert_positions(batch)

            # Bulk update flight timestamps in one operation
            if all_flight_updates:
                # Remove duplicates to avoid redundant updates
                seen_flights = set()
                unique_updates = []
                
                for flight_id, timestamp in all_flight_updates:
                    if flight_id not in seen_flights:
                        seen_flights.add(flight_id)
                        unique_updates.append((flight_id, timestamp))
                        
                self.db_repo.bulk_update_flight_last_contacts(unique_updates)

        # Grow the position hash cache to improve hit rates, but reset if too large
        if len(self.positions_hash) > 150000:  # Increased threshold for better caching
            self.positions_hash = set()
            
    def _process_position_batch(self, batch, flight_id_by_icao, timestamp):
        """Process a batch of positions efficiently"""
        positions_to_insert = []
        flight_updates = []
        
        # Pre-compute hashes for this batch in one pass
        # This avoids repeated calculations
        position_hashes = {}
        for pos in batch:
            pos_hash = hash((round(pos.lat, 5), round(pos.lon, 5), pos.alt))
            position_hashes[pos.icao24] = pos_hash
            
        # Track new position hashes that need to be added to the cache
        new_hashes = set()
        
        # Process each position
        for pos in batch:
            icao24 = pos.icao24
            flight_id = flight_id_by_icao[icao24]
            pos_hash = position_hashes[icao24]
            
            # Skip if we've already seen this position (fast path)
            if pos_hash in self.positions_hash:
                continue
                
            # Add to new hashes to be added to cache
            new_hashes.add(pos_hash)
            
            # Determine if we need to store this position
            store_position = True
            
            # Only check last position if it exists
            if flight_id in self.flight_lastpos_map:
                last_pos = self.flight_lastpos_map[flight_id]
                
                # Fast path - compare directly with the hash we already computed
                last_pos_hash = hash((
                    round(last_pos.lat, 5),
                    round(last_pos.lon, 5),
                    last_pos.alt
                ))
                
                # Skip if position hasn't changed
                if last_pos_hash == pos_hash:
                    store_position = False
            
            # Process position if it's new
            if store_position:
                # Update in-memory cache immediately
                self.flight_last_contact[flight_id] = timestamp
                self.flight_lastpos_map[flight_id] = pos
                
                # Mark for WebSocket notification
                self._positions_changed = True
                self._changed_flight_ids.add(str(flight_id))
                
                # Create position document with minimal object creation
                positions_to_insert.append({
                    "flight_id": ObjectId(flight_id),
                    "lat": pos.lat,
                    "lon": pos.lon,
                    "alt": pos.alt,
                    "timestmp": timestamp
                })
                
                # Track flight update
                flight_updates.append((flight_id, timestamp))
        
        # Bulk add all new hashes to the cache at once
        self.positions_hash.update(new_hashes)
        
        return positions_to_insert, flight_updates

    def update_flights(self, flights: List[PositionReport]):
        """Inserts and updates flights in the database with optimized batch processing"""
        if not flights:
            return
            
        # Create a dict of flights by icao24 for faster access
        # This avoids repeated list iterations
        flights_by_icao = {}
        for f in flights:
            flights_by_icao[f.icao24] = f
            
        # Process flights in batches to reduce database load
        batch_size = 200
        flight_batches = [flights[i:i+batch_size] for i in range(0, len(flights), batch_size)]
        
        # Track insertions and updates across all batches
        all_inserted = []
        all_updated = []
        
        # Get current timestamp once
        now = datetime.now(timezone.utc)
        thresh_timestmp = self._threshold_timestamp()
            
        # Process each batch separately to avoid memory issues
        for batch in flight_batches:
            self._process_flight_batch(
                batch, 
                flights_by_icao,
                thresh_timestmp, 
                now, 
                all_inserted, 
                all_updated
            )
            
        # Log only once after all batches are processed
        if all_inserted:
            inserted_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in all_inserted[:5]])
            if len(all_inserted) > 5:
                inserted_msg += f" and {len(all_inserted) - 5} more"
            logger.info(f'aircraftEvent=insert {inserted_msg}')

        if all_updated:
            updated_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in all_updated[:5]])
            if len(all_updated) > 5:
                updated_msg += f" and {len(all_updated) - 5} more"
            logger.info(f'aircraftEvent=update {updated_msg}')
    
    def _process_flight_batch(self, batch, flights_by_icao, thresh_timestmp, now, inserted_flights, updated_flights):
        """Process a batch of flights for better memory management and performance"""
        # Gather all modeS addresses for this batch
        batch_modes = set(f.icao24 for f in batch)
        
        # Skip empty batches
        if not batch_modes:
            return
            
        # Check which flights we already know about to avoid DB queries
        known_modes = set()
        unknown_modes = set()
        
        for modeS in batch_modes:
            if modeS in self.modeS_flightid_map:
                flight_id = self.modeS_flightid_map[modeS]
                if flight_id in self.flight_last_contact:
                    known_modes.add(modeS)
                else:
                    unknown_modes.add(modeS)
            else:
                unknown_modes.add(modeS)
                
        # Fast path: bulk update known flights with timestamp only
        if known_modes:
            # Prepare timestamp updates
            timestamp_updates = []
            for modeS in known_modes:
                flight_id = self.modeS_flightid_map[modeS]
                timestamp_updates.append((flight_id, now))
                
                # Update in-memory cache
                self.flight_last_contact[flight_id] = now
                
            # Bulk update timestamps in one operation
            if timestamp_updates:
                self.db_repo.bulk_update_flight_last_contacts(timestamp_updates)
        
        # Skip the database lookup if all modes are known
        if not unknown_modes:
            return
            
        # Fetch unknown flights in one query
        flights_by_modeS = self.db_repo.get_flights_batch(unknown_modes)
        
        # Optimize callsign operations by precomputing
        callsign_updates = []
        new_flights = []
        
        # Process each unknown mode
        for modeS in unknown_modes:
            f = flights_by_icao[modeS]
            new_callsign = f.callsign.strip().upper() if f.callsign else ""
            
            # Skip processing if we found no flights for this mode
            if modeS not in flights_by_modeS:
                # Create new flight directly
                new_flights.append((modeS, f.callsign, self._mil_ranges.is_military(modeS)))
                continue
                
            # Fast lookup for recent flights
            db_flights = flights_by_modeS[modeS]
            matching_flight = None
            
            # Find most recent flight with matching callsign
            for flight in db_flights:
                if not matching_flight:
                    flight_last_contact = flight["last_contact"]
                    flight_last_contact, comparison_timestamp = make_datetimes_comparable(
                        flight_last_contact, thresh_timestmp
                    )
                    
                    # Check if the flight is recent enough to be reused
                    if flight_last_contact > comparison_timestamp:
                        # Check for callsign match
                        db_callsign = flight.get("callsign", "").strip().upper() if flight.get("callsign") else ""
                        
                        # If callsigns match or both are empty, use this flight
                        callsign_match = (db_callsign and new_callsign and db_callsign == new_callsign) or \
                                         (not db_callsign and not new_callsign)
                                         
                        if callsign_match or not new_callsign:
                            matching_flight = flight
                            break
                    # If the flight is older than the threshold, we'll create a new one
            
            # If no match found, find most recent flight
            if not matching_flight and db_flights:
                # Just use the first one since they're sorted by last_contact
                most_recent = db_flights[0]
                flight_last_contact = most_recent["last_contact"]
                flight_last_contact, comparison_timestamp = make_datetimes_comparable(
                    flight_last_contact, thresh_timestmp
                )
                
                # Only reuse the flight if it's recent enough
                if flight_last_contact > comparison_timestamp:
                    # Different callsign with same aircraft = new flight if callsign present
                    db_callsign = most_recent.get("callsign", "").strip().upper() if most_recent.get("callsign") else ""
                    if new_callsign and db_callsign != new_callsign:
                        # Create new flight for different callsign
                        new_flights.append((modeS, f.callsign, self._mil_ranges.is_military(modeS)))
                    else:
                        # Use this flight
                        matching_flight = most_recent
                else:
                    # Flight is older than the threshold, create a new one
                    logger.info(f"Creating new flight for {modeS} as last contact was too old: {flight_last_contact}")
                    new_flights.append((modeS, f.callsign, self._mil_ranges.is_military(modeS)))
            
            # Process the matching flight if found
            if matching_flight:
                flight_id = str(matching_flight["_id"])
                
                # Check if callsign needs updating
                db_callsign = matching_flight.get("callsign", "").strip().upper() if matching_flight.get("callsign") else ""
                if new_callsign and new_callsign != db_callsign:
                    callsign_updates.append((flight_id, f.callsign))
                    updated_flights.append((modeS, f.callsign))
                
                # Update in-memory maps
                self.modeS_flightid_map[modeS] = flight_id
                self.flight_last_contact[flight_id] = now
            else:
                # No matching flight found, create a new one
                new_flights.append((modeS, f.callsign, self._mil_ranges.is_military(modeS)))
        
        # Process callsign updates in a single batch operation if possible
        if callsign_updates:
            # MongoDB supports bulk operations for callsign updates
            bulk_updates = []
            for flight_id, callsign in callsign_updates:
                bulk_updates.append((flight_id, {"callsign": callsign, "last_contact": now}))
            
            if bulk_updates:
                self.db_repo.bulk_update_flights(bulk_updates)
        
        # Create new flights in bulk if possible
        if new_flights:
            for modeS, callsign, is_military in new_flights:
                try:
                    flight_obj = self.db_repo.get_or_create_flight(
                        modeS=modeS,
                        callsign=callsign,
                        is_military=is_military
                    )
                    flight_id = str(flight_obj["_id"])
                    
                    # Update in-memory maps
                    self.modeS_flightid_map[modeS] = flight_id
                    self.flight_last_contact[flight_id] = now
                    
                    # Track insertion
                    inserted_flights.append((modeS, callsign))
                except Exception as e:
                    logger.error(f"Error creating flight for {modeS}: {str(e)}")

    def get_silhouete_params(self):
        return self._service.get_silhouete_params()

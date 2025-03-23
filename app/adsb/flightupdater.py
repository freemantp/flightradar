import logging
import threading
from typing import Any, Dict, List, Callable, Set
from time import sleep
from datetime import datetime, timedelta
from timeit import default_timer as timer
from bson import ObjectId

from .datasource.modesmixer import ModeSMixer
from .datasource.virtualradarserver import VirtualRadarServer
from .datasource.dump1090 import Dump1090
from .util.modes_util import ModesUtil
from .db.mongodb_models import Flight, Position
from .db.mongodb_repository import MongoDBRepository
from ..config import Config, app_state
from .model.position_report import PositionReport

logger = logging.getLogger('Updater')


class FlightUpdater:
    MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT = 10
    _update_lock = threading.RLock()  # Class-level lock for thread safety

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
        timestamp = datetime.utcnow() - timedelta(minutes=1)

        return {v: self.flight_lastpos_map.get(v)
                for (k, v) in self.modeS_flightid_map.items()
                if v in self.flight_lastpos_map and self.flight_last_contact[v] > timestamp}

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
            delete_timestamp = datetime.utcnow() - timedelta(minutes=self._delete_after)

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
        return datetime.utcnow() - timedelta(minutes=self.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)

    def _initialize_from_db(self):
        """Initializes cache from database with optimized loading"""
        recent_flight_timestamp = datetime.utcnow() - timedelta(minutes=self.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)

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

            # Processing time measurement
            process_start = timer()
            flight_update_time = 0
            position_update_time = 0
            cleanup_time = 0
            websocket_time = 0

            try:
                if positions:
                    # Filter once at the beginning
                    filtered_pos = [pos for pos in positions if self._mil_ranges.is_military(
                        pos.icao24)] if self._mil_only else positions

                    # Separate valid positions with coordinates for more efficient processing
                    valid_positions = [p for p in filtered_pos if p.lat and p.lon]

                    # Update flights
                    flight_start = timer()
                    self.update_flights(filtered_pos)
                    flight_update_time = timer() - flight_start

                    # Store current positions before update for comparison
                    self._previous_positions = self.get_cached_flights()

                    # Add valid positions
                    position_start = timer()
                    self.add_positions(valid_positions)
                    position_update_time = timer() - position_start

                    # Broadcast positions via WebSocket if callbacks are registered
                    if self._websocket_callbacks and self._positions_changed:
                        websocket_start = timer()

                        all_cached_flights = self.get_cached_flights()

                        logger.info(
                            f"Changed flight IDs: {len(self._changed_flight_ids)}, All cached flights: {len(all_cached_flights)}")

                        # Only include the flights that have changed positions
                        changed_positions = {str(k): v
                                             for k, v in all_cached_flights.items()
                                             if str(k) in self._changed_flight_ids}

                        # If no changed positions match cached flights, use all positions for this update
                        if not changed_positions and all_cached_flights:
                            logger.warning("No changed positions match cached flights - sending all positions instead")
                            changed_positions = all_cached_flights

                        positions_dict = {
                            k: {
                                "lat": v.lat,
                                "lon": v.lon,
                                "alt": v.alt
                            } for k, v in changed_positions.items()
                        }

                        # Trigger all WebSocket callbacks
                        try:
                            # Only use callbacks if we have data to send
                            if positions_dict:
                                callback_count = len(self._websocket_callbacks)
                                logger.debug(f"Broadcasting {len(positions_dict)} positions to {callback_count} WebSocket callbacks")
                                
                                # Call each callback
                                callbacks_to_remove = set()
                                for callback in self._websocket_callbacks:
                                    try:
                                        callback(positions_dict)
                                    except Exception as e:
                                        logger.error(f"Error in WebSocket callback: {str(e)}")
                                        # Mark failed callbacks for removal
                                        callbacks_to_remove.add(callback)
                                
                                # Remove any failed callbacks
                                for callback in callbacks_to_remove:
                                    self._websocket_callbacks.remove(callback)
                                    logger.warning(f"Removed failed WebSocket callback, {len(self._websocket_callbacks)} remaining")
                            else:
                                logger.warning("No positions to broadcast, skipping WebSocket update")
                        except Exception as e:
                            logger.error(f"Error broadcasting to WebSocket: {str(e)}", exc_info=True)

                        websocket_time = timer() - websocket_start

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

            if total_time > 0.5:
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
        """Inserts positions into the database with optimized batch processing"""
        positions_to_insert = []
        flight_updates = []
        now = datetime.utcnow()

        # Process all positions in one pass
        for pos in positions:
            if pos.icao24 not in self.modeS_flightid_map:
                continue

            flight_id = self.modeS_flightid_map[pos.icao24]

            # Use more efficient position comparison with hash
            pos_hash = hash((round(pos.lat, 5), round(pos.lon, 5), pos.alt))

            if pos_hash in self.positions_hash:
                continue

            # Add to hash set to avoid future duplicates
            self.positions_hash.add(pos_hash)

            # Only store if it's a new position
            if flight_id not in self.flight_lastpos_map or hash((
                    round(self.flight_lastpos_map[flight_id].lat, 5),
                    round(self.flight_lastpos_map[flight_id].lon, 5),
                    self.flight_lastpos_map[flight_id].alt)) != pos_hash:

                # Update in-memory cache
                self.flight_last_contact[flight_id] = now
                self.flight_lastpos_map[flight_id] = pos

                # Positions have changed (for WebSocket)
                self._positions_changed = True

                # Record which flight ID had a position change - ensure it's stored as a string
                self._changed_flight_ids.add(str(flight_id))

                position_doc = {
                    "flight_id": ObjectId(flight_id),
                    "lat": pos.lat,
                    "lon": pos.lon,
                    "alt": pos.alt,
                    "timestmp": now
                }
                positions_to_insert.append(position_doc)
                flight_updates.append((flight_id, now))

        # Perform bulk operations
        if positions_to_insert:
            # Insert positions in batches
            for i in range(0, len(positions_to_insert), self._insert_batch_size):
                batch = positions_to_insert[i:i+self._insert_batch_size]
                self.db_repo.insert_positions(batch)

            # Bulk update flight last_contact timestamps
            self.db_repo.bulk_update_flight_last_contacts(flight_updates)

        # Periodically trim the positions hash set to prevent memory growth
        if len(self.positions_hash) > 10000:
            self.positions_hash = set()

    def update_flights(self, flights: List[PositionReport]):
        """Inserts and updates flights in the database with batch processing"""
        inserted_flights = []
        updated_flights = []

        # Create a new flight even if other flights in db match modes/callsign, but too much time elapsed since last position report
        thresh_timestmp = self._threshold_timestamp()

        # Gather all modeS addresses for batch lookup
        all_modes = set(f.icao24 for f in flights)

        # Fetch all flights at once with a batch query
        flights_by_modeS = self.db_repo.get_flights_batch(all_modes)

        # Batch flight updates
        flight_updates = []

        for f in flights:
            # Find existing flights with this modeS that were recently active
            flight_result = None

            if f.icao24 in flights_by_modeS:
                # Find recently active flight
                for flight in flights_by_modeS[f.icao24]:
                    if flight["last_contact"] > thresh_timestmp:
                        flight_result = flight
                        break

            if flight_result:
                flight_id = str(flight_result["_id"])

                # Update existing flight if needed
                if f.callsign and not flight_result.get("callsign"):
                    flight_updates.append((flight_id, {"callsign": f.callsign}))
                    updated_flights.append((f.icao24, f.callsign))

                # Update in-memory map
                if f.icao24 not in self.modeS_flightid_map:
                    self.modeS_flightid_map[f.icao24] = flight_id
            else:
                try:
                    # Create new flight using upsert to avoid duplicate key errors
                    flight_obj = self.db_repo.get_or_create_flight(
                        modeS=f.icao24,
                        callsign=f.callsign,
                        is_military=self._mil_ranges.is_military(f.icao24)
                    )
                    flight_id = str(flight_obj["_id"])

                    # Update in-memory map
                    self.modeS_flightid_map[f.icao24] = flight_id

                    # Check if this was an insert or update
                    if flight_obj.get("first_contact") == flight_obj.get("last_contact"):
                        # Only add to inserted_flights if it's a new record
                        inserted_flights.append((f.icao24, f.callsign))
                except Exception as e:
                    logger.error(f"Error creating flight for {f.icao24}: {str(e)}", exc_info=True)

        # Apply flight updates in batch
        if flight_updates:
            self.db_repo.bulk_update_flights(flight_updates)

        # Log events
        if inserted_flights:
            inserted_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in inserted_flights])
            logger.info('aircraftEvent=insert {:s}'.format(inserted_msg))

        if updated_flights:
            updated_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in updated_flights])
            logger.info('aircraftEvent=update {:s}'.format(updated_msg))

    def get_silhouete_params(self):
        return self._service.get_silhouete_params()

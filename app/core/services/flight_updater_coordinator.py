import logging
import threading
from typing import Any, Dict, Callable, Set, Optional

from ...data.sources.radar_service_factory import RadarServiceFactory
from .flight_manager import FlightManager
from ...data.repositories.flight_repository import FlightRepository
from .position_manager import PositionManager
from ...data.repositories.position_repository import PositionRepository
from ...data.repositories.mongodb_repository import MongoDBRepository
from ...websocket.notifier import WebSocketNotifier
from ...monitoring.performance_monitor import PerformanceMonitor
from ..models.position_report import PositionReport
from .incomplete_aircraft_manager import IncompleteAircraftManager
from ...config import app_state
from ...exceptions import DatabaseException

logger = logging.getLogger('FlightUpdaterCoordinator')

class FlightUpdaterCoordinator:
    _update_lock = threading.RLock()
    
    def __init__(self):
        self.is_updating = False
        self.sleep_time = 1
        self._t = None
        self.interrupted = False
        
    def initialize(self, config, mongodb=None):
        """Initialize all components with configuration"""
        
        self._radar_service = RadarServiceFactory.create(config)
        
        self._retention_minutes = getattr(config, 'DB_RETENTION_MIN', 0)
        self._use_ttl_indexes = self._retention_minutes > 0
        
        if not self._use_ttl_indexes:
            logger.info("Document expiration disabled: no retention period specified")
        else:
            logger.info(f"Using TTL indexes for document expiration with retention of {self._retention_minutes} minutes")
            
        db_repo = MongoDBRepository(mongodb)
        
        # Create repositories
        self._flight_repository = FlightRepository(db_repo)
        self._position_repository = PositionRepository(db_repo)
        
        # Create managers and services
        self._flight_manager = FlightManager(config)        
        self._flight_manager.initialize(self._flight_repository)
        
        self._position_manager = PositionManager(config)
        self._position_manager.initialize(self._position_repository)
        
        self._websocket_notifier = WebSocketNotifier()
        self._performance_monitor = PerformanceMonitor()
        
        self._unknown_aircraft_manager = IncompleteAircraftManager(config, mongodb)
            
        
        logger.info("Loading cached position data...")
        # Initialize position manager with data from flight manager
        position_count = 0
        for flight_id, flight_pos in self._flight_manager.repository.get_last_positions().items():
            if flight_id in self._flight_manager.flight_last_contact:
                self._position_manager.flight_lastpos_map[flight_id] = flight_pos
                position_count += 1
        logger.info(f"Loaded {position_count} cached positions")

    def is_service_alive(self) -> bool:
        """Check if the radar service connection is alive"""
        return self._radar_service.connection_alive
        
    def register_websocket_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for WebSocket notifications"""
        return self._websocket_notifier.register_callback(callback)
        
    def unregister_websocket_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Unregister a WebSocket callback"""
        return self._websocket_notifier.unregister_callback(callback)
        
    def get_cached_flights(self) -> Dict[str, PositionReport]:
        """Get flights with recent positions"""
        return self._position_manager.get_cached_flights(self._flight_manager)
        
    def get_silhouete_params(self):
        """Get silhouette parameters from radar service"""
        return self._radar_service.get_silhouete_params()

    def update(self):
        """Main update method that coordinates the update process"""
        # Use thread lock to prevent concurrent updates
        # Non-blocking acquisition - if locked, just return instead of waiting
        if not FlightUpdaterCoordinator._update_lock.acquire(blocking=False):
            logger.debug("Update already in progress, skipping this cycle")
            return

        try:
            self.is_updating = True
            self._position_manager.clear_changes()

            self._performance_monitor.start_timer('main')
            
            self._performance_monitor.start_timer('service')
            positions = self._radar_service.query_live_flights(False)
            self._performance_monitor.stop_timer('service')
                
            if not positions:
                return        
            live_icao24s = {pos.icao24 for pos in positions if pos.icao24}
            self._unknown_aircraft_manager.schedule_aircraft_for_processing(live_icao24s)
            
            try:
                filtered_pos = self._flight_manager.filter_military_only(positions)
                
                if not filtered_pos:
                    return

                valid_positions = [p for p in filtered_pos if p.lat and p.lon]

                
                self._performance_monitor.start_timer('flight')
                self._flight_manager.update_flights(filtered_pos)
                self._performance_monitor.stop_timer('flight')

                self._performance_monitor.start_timer('position')
                self._position_manager.add_positions(valid_positions, self._flight_manager)
                self._performance_monitor.stop_timer('position')

                # Broadcast positions via WebSocket if needed
                if (self._websocket_notifier.has_callbacks() and 
                    self._position_manager.has_positions_changed() and 
                    len(self._position_manager.get_changed_flight_ids()) > 0):
                    
                    self._performance_monitor.start_timer('websocket')
                    
                    all_cached_flights = self.get_cached_flights()
                    changed_flight_ids = self._position_manager.get_changed_flight_ids()
                    
                    self._websocket_notifier.notify_position_changes(all_cached_flights, changed_flight_ids)
                        
                    self._performance_monitor.stop_timer('websocket')

            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                if isinstance(e, DatabaseException) and "you are over your space quota" in str(e):
                    logger.error(f"Database quota exceeded: {str(e)}")
                else:
                    logger.exception(f"An error occurred: {str(e)}")

            self._performance_monitor.log_performance(threshold=0.2)
            
        finally:
            self.is_updating = False
            FlightUpdaterCoordinator._update_lock.release()


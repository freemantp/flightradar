import logging
from typing import Any, Dict, Set, Callable

logger = logging.getLogger('WebSocketNotifier')

class WebSocketNotifier:
    def __init__(self):
        self._callbacks: Set[Callable] = set()
        
    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback function to notify when positions are updated"""
        self._callbacks.add(callback)
        return callback
        
    def unregister_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Unregister a previously registered callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            return True
        return False
        
    def has_callbacks(self):
        """Check if there are any registered callbacks"""
        return len(self._callbacks) > 0
        
    def notify_clients(self, positions_dict):
        """Notify all registered clients with position updates"""
        if not positions_dict or not self._callbacks:
            return
        
        callbacks_to_remove = set()
        for callback in self._callbacks:
            try:
                callback(positions_dict)
            except Exception as e:
                logger.error(f"Error in WebSocket callback: {str(e)}")
                callbacks_to_remove.add(callback)
        
        if callbacks_to_remove:
            self._callbacks.difference_update(callbacks_to_remove)
            
    def notify_position_changes(self, all_cached_flights: Dict[str, Any], changed_flight_ids: Set[str]):
        """
        Notify clients of position changes with proper data transformation
        
        Args:
            all_cached_flights: Dictionary of flight_id -> PositionReport
            changed_flight_ids: Set of flight IDs that have changed
        """
        if not self.has_callbacks() or not changed_flight_ids:
            return
            
        positions_dict = {}
        for flight_id, pos in all_cached_flights.items():
            if str(flight_id) in changed_flight_ids:
                positions_dict[str(flight_id)] = {
                    "lat": pos.lat,
                    "lon": pos.lon,
                    "alt": pos.alt,
                    "track": pos.track
                }
        
        # Fallback if no positions matched (should be rare)
        if not positions_dict and all_cached_flights:
            logger.warning("No changed positions match cached flights")

            count = 0
            for flight_id, pos in all_cached_flights.items():
                if count < 50:  # Limit to 50 positions
                    positions_dict[str(flight_id)] = {
                        "lat": pos.lat,
                        "lon": pos.lon,
                        "alt": pos.alt,
                        "track": pos.track
                    }
                    count += 1
                else:
                    break

        if positions_dict:
            self.notify_clients(positions_dict)
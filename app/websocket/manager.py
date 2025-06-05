import logging
import threading
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = logging.getLogger("WebSocketManager")


class ConnectionManager:
    """
    Manages WebSocket connections for real-time position updates
    """

    def __init__(self):
        # Store active connections
        self.active_connections: Set[WebSocket] = set()
        # Lock for thread safety when modifying connections
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection and add it to active connections
        """
        await websocket.accept()
        with self._lock:
            self.active_connections.add(websocket)

        client_info = f"New WebSocket connection established"
        if "x-forwarded-for" in websocket.headers:
            client_info += f" from {websocket.headers['x-forwarded-for']}"
        logger.debug(f"{client_info}. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection from active connections
        """
        with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.debug(f"WebSocket connection closed. Total active: {len(self.active_connections)}")

    async def broadcast_positions(self, positions: Dict[str, Any]):
        """
        Broadcast position data to all connected clients
        """
        # Make a thread-safe copy of the connections
        with self._lock:
            if not self.active_connections:
                logger.debug("No active connections, skipping broadcast")
                return
            # Create a copy to avoid modification during iteration
            connections = set(self.active_connections)

        # Validate positions is not empty
        if not positions:
            logger.warning("Attempted to broadcast empty positions, skipping")
            return

        # Create a message with metadata about the update
        message = {
            "type": "update",
            "count": len(positions),
            "positions": positions
        }

        logger.debug(f"Broadcasting {len(positions)} position updates to {len(connections)} connected clients")

        disconnected = set()

        # Broadcast to all connected clients
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {str(e)}")
                # If connection is closed or had an error, mark for removal
                disconnected.add(connection)

        # Remove disconnected connections
        if disconnected:
            with self._lock:
                for conn in disconnected:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)
                logger.debug(
                    f"Removed {len(disconnected)} disconnected clients. {len(self.active_connections)} remaining.")

from fastapi import Request, Query, HTTPException, Depends, WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel
from pymongo.database import Database
from bson import ObjectId
import logging
import threading
import asyncio

from . import router
from .mappers import toFlightDto
from .apimodels import FlightDto
from .websocket_manager import ConnectionManager
from .. import get_mongodb
from .. adsb.db.mongodb_repository import MongoDBRepository
from .. scheduling import UPDATER_JOB_NAME

# Initialize logging
logger = logging.getLogger(__name__)

# Create a WebSocket connection manager
connection_manager = ConnectionManager()

# Constants
MAX_FLIGHTS_LIMIT = 100

# Define response models


class MetaInfo(BaseModel):
    class Config:
        arbitrary_types_allowed = True


class PositionReport(BaseModel):
    lat: float
    lon: float
    alt: int

    class Config:
        arbitrary_types_allowed = True


@router.get('/info', response_model=Dict[str, Any])
def get_meta_info(request: Request):
    meta_info = request.app.state.metaInfo
    return {
        "commit_id": meta_info.commit_id,
        "build_timestamp": meta_info.build_timestamp
    }


@router.get('/alive')
def alive():
    return "Yes"


@router.get('/ready')
def ready(request: Request):
    updater_job = request.app.state.apscheduler.get_job(UPDATER_JOB_NAME)
    if updater_job and not updater_job.pending:
        return "Yes"
    else:
        raise HTTPException(status_code=500, detail="Service not ready")


@router.get('/flights', response_model=List[FlightDto])
def get_flights(
    request: Request,
    filter: Optional[str] = Query(None, description="Filter flights (e.g. 'mil' for military only)"),
    limit: Optional[int] = Query(None, description="Maximum number of flights to return"),
    mongodb: Database = Depends(get_mongodb)
):
    try:
        pipeline = []

        # Apply filter
        if filter == 'mil':
            pipeline.append({"$match": {"is_military": True}})

        # Sort by first contact descending
        pipeline.append({"$sort": {"first_contact": -1}})

        # Apply limit (default and max limit is MAX_FLIGHTS_LIMIT)
        if limit is not None:
            applied_limit = min(limit, MAX_FLIGHTS_LIMIT)
        else:
            applied_limit = MAX_FLIGHTS_LIMIT

        pipeline.append({"$limit": applied_limit})

        flights = list(mongodb.flights.aggregate(pipeline))
        return [toFlightDto(f) for f in flights]

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid arguments: {str(e)}")


@router.get('/flights/{flight_id}', response_model=FlightDto)
def get_flight(flight_id: str, mongodb: Database = Depends(get_mongodb)):
    try:
        flight = mongodb.flights.find_one({"_id": ObjectId(flight_id)})

        if flight:
            return toFlightDto(flight)
        else:
            raise HTTPException(status_code=404, detail="Flight not found")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid flight ID format: {str(e)}")


@router.websocket('/ws/positions/live')
async def websocket_all_positions(websocket: WebSocket):
    """WebSocket endpoint for real-time position updates"""
    # Get application state from the WebSocket scope
    app = websocket.app

    # Create a broadcast function for this specific WebSocket connection
    def broadcast_positions(positions_dict):
        """Function to broadcast positions to all connected clients"""
        logger.debug(f"WebSocket callback triggered with {len(positions_dict)} positions")

        # Use a thread for handling the async operation from a sync context
        def run_in_thread(positions_data):                
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the coroutine in this thread's event loop
                loop.run_until_complete(connection_manager.broadcast_positions(positions_data))
            except Exception as e:
                logger.error(f"Error in WebSocket broadcast thread: {str(e)}", exc_info=True)
            finally:
                loop.close()

        # Start a dedicated thread for this broadcast
        broadcast_thread = threading.Thread(
            target=run_in_thread,
            args=(positions_dict,),
            daemon=True
        )
        broadcast_thread.start()

    # Register the callback with the flight updater and store the reference
    registered_callback = app.state.updater.register_websocket_callback(broadcast_positions)
    
    # Store the callback reference for later cleanup
    callback_key = f"ws_live_callback_{id(websocket)}"
    setattr(app.state, callback_key, registered_callback)
    logger.info("WebSocket broadcast callback registered with updater")

    # Accept the WebSocket connection
    await connection_manager.connect(websocket)

    try:
        # Send initial positions immediately after connection
        # For initial connection, we send all current positions with full data
        cached_flights = app.state.updater.get_cached_flights()
        initial_positions = {str(k): v.__dict__ for k, v in cached_flights.items()}

        # Add a message type to indicate this is the initial full data set
        message = {
            "type": "initial",
            "count": len(initial_positions),
            "positions": initial_positions
        }
        await websocket.send_json(message)

        # Keep the connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Handle client disconnect
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        connection_manager.disconnect(websocket)
    finally:
        # Clean up the callback when the connection is closed
        callback_key = f"ws_live_callback_{id(websocket)}"
        registered_callback = getattr(app.state, callback_key, None)
        if registered_callback:
            app.state.updater.unregister_websocket_callback(registered_callback)
            setattr(app.state, callback_key, None)
            logger.info("Live WebSocket broadcast callback unregistered")


@router.websocket('/ws/flights/{flight_id}/positions')
async def websocket_flight_positions(websocket: WebSocket, flight_id: str):
    """WebSocket endpoint for real-time position updates for a specific flight"""

    app = websocket.app
    mongodb = app.state.mongodb

    # Flight-specific connection manager
    flight_connection_manager = ConnectionManager()

    # Check if flight exists before accepting the connection
    try:
        flight = mongodb.flights.find_one({"_id": ObjectId(flight_id)})
        if not flight:
            await flight_connection_manager.connect(websocket)
            await websocket.close(code=1000, reason=f'Flight {flight_id} not found')
            return
    except Exception as e:
        logger.error(f"Error checking flight {flight_id}: {str(e)}")
        await websocket.close(code=1011, reason="Server error")
        return
    
    await flight_connection_manager.connect(websocket)

    # Flag to track connection state
    websocket_active = True
    callback_registered = False
    callback_key = f"ws_flight_callback_{flight_id}"
    
    try:
        # Get the flight ID in ObjectId format
        flight_oid = ObjectId(flight_id)
        
        # Fetch initial positions from mongodb for the given flight
        positions = list(mongodb.positions.find({"flight_id": flight_oid}).sort("timestmp", 1))
        last_position = None
        
        # Format all positions for the initial message
        all_positions = []
        
        if positions:
            for pos in positions:
                position_data = {
                    "lat": pos["lat"],
                    "lon": pos["lon"],
                    "alt": pos["alt"] if pos["alt"] is not None else -1
                }
                all_positions.append(position_data)
            
            # Save the most recent position for comparison with future updates
            last_position = all_positions[-1] if all_positions else None
        
        # Create the initial message with all positions
        initial_pos_message = {
            "type": "initial",
            "count": len(all_positions),
            "positions": {flight_id: all_positions} if all_positions else {}
        }

        await websocket.send_json(initial_pos_message)
        
        # Function to check if websocket is still active
        def is_websocket_active():
            return websocket_active
        
        # Function to track position changes for a specific flight
        def send_flight_position_updates(positions_dict):
            """Callback function to send position updates for a specific flight"""
            # First check if the WebSocket is still active
            if not is_websocket_active():
                return
                
            # Check if this update contains this flight
            if flight_id not in positions_dict:
                return
                
            # Get flight's new position
            new_position = positions_dict[flight_id]
            
            # Get a reference to the previous position
            nonlocal last_position
            
            # Skip if there's no previous position yet
            if last_position is None:
                last_position = new_position
                # Use thread-based approach for async operations from sync context
                _send_update_in_thread(new_position)
                return
            
            # Only send update if position has changed
            if (last_position["lat"] != new_position["lat"] or 
                last_position["lon"] != new_position["lon"] or 
                last_position["alt"] != new_position["alt"]):
                
                # Update the last known position
                last_position = new_position
                
                # Use thread-based approach for async operations from sync context
                _send_update_in_thread(new_position)
        
        # Helper function to send updates through a separate thread with its own event loop
        def _send_update_in_thread(position_data):
            def run_in_thread(pos_data):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Check if still active before running
                    if is_websocket_active():
                        loop.run_until_complete(send_update(pos_data))
                except Exception as e:
                    logger.error(f"Error in flight WebSocket update thread: {str(e)}", exc_info=True)
                finally:
                    loop.close()
            
            # Start a dedicated thread for this update
            broadcast_thread = threading.Thread(
                target=run_in_thread,
                args=(position_data,),
                daemon=True
            )
            broadcast_thread.start()
        
        # Helper async function to send a single flight update
        async def send_update(position_data):

            if not is_websocket_active():
                return
                
            try:
                # Format the update message
                update_message = {
                    "type": "update",
                    "count": 1,
                    "positions": {flight_id: position_data}
                }
                # Send to this specific connection only
                await websocket.send_json(update_message)
                logger.debug(f"Sent position update for flight {flight_id}")
            except Exception as e:
                # If we get a closed websocket error, mark inactive
                websocket_active = False
                logger.error(f"Error sending flight position update: {str(e)}")
        
        # Register the callback with the flight updater and store the reference
        registered_callback = app.state.updater.register_websocket_callback(send_flight_position_updates)
        setattr(app.state, callback_key, registered_callback)
        callback_registered = True
        logger.info(f"WebSocket callback registered for flight {flight_id}")
        
        # Keep the connection alive
        while True:
            # Wait for client messages (ping/pong handled automatically)
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info(f"WebSocket for flight {flight_id} disconnected")
        websocket_active = False
        flight_connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        websocket_active = False
        flight_connection_manager.disconnect(websocket)
    finally:
        # Make sure to mark connection as inactive
        websocket_active = False
        
        # Clean up callback if we registered one
        if callback_registered:
            # Get the callback reference
            registered_callback = getattr(app.state, callback_key, None)
            if registered_callback:
                # Properly unregister it from the updater
                app.state.updater.unregister_websocket_callback(registered_callback)
                setattr(app.state, callback_key, None)
                logger.info(f"WebSocket callback for flight {flight_id} unregistered and deactivated")

@router.get('/flights/{flight_id}/positions', response_model=List[List[Union[float, int]]])
def get_positions(flight_id: str, mongodb: Database = Depends(get_mongodb)):
    try:
        # Check if flight exists
        flight = mongodb.flights.find_one({"_id": ObjectId(flight_id)})
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found")

        # Get positions
        positions = mongodb.positions.find({"flight_id": ObjectId(flight_id)}).sort("timestmp", 1)

        # Convert to list format suitable for JSON serialization
        position_list = []
        for p in positions:
            alt = p["alt"] if p["alt"] is not None else -1
            position_list.append([p["lat"], p["lon"], alt])

        return position_list

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid flight id format: {str(e)}")


@router.get('/positions')
def get_all_positions(
    request: Request,
    archived: bool = Query(False, description="Include archived positions"),
    filter: Optional[str] = Query(None, description="Filter positions (e.g. 'mil' for military only)"),
    mongodb: Database = Depends(get_mongodb)
):
    # Use MongoDB aggregation to get all positions grouped by flight
    repo = MongoDBRepository(mongodb)
    positions = repo.get_all_positions(archived)

    # Filter positions by military if requested
    if filter == 'mil':
        positions = {key: value for (key, value) in positions.items() if request.app.state.modes_util.is_military(key)}

    # Clean up any None values to prevent validation errors
    cleaned_positions = {}
    for key, value_list in positions.items():
        cleaned_positions[key] = [
            [lat, lon, alt if alt is not None else 0]
            for lat, lon, alt in value_list
            if lat is not None and lon is not None
        ]

    return cleaned_positions

from fastapi import Request, Query, HTTPException, Depends, WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from pymongo.database import Database
from bson import ObjectId
import logging
import threading
import asyncio

from .. import router
from ..mappers import toFlightDto
from ..models import FlightDto, to_datestring
from ...websocket.manager import ConnectionManager
from ..dependencies import MetaInfoDep, get_mongodb
from ...scheduling import UPDATER_JOB_NAME

# Initialize logging
logger = logging.getLogger(__name__)

# Create a WebSocket connection manager
connection_manager = ConnectionManager()

# Constants
MAX_FLIGHTS_LIMIT = 300

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
def get_meta_info(meta_info: MetaInfoDep):
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


@router.get('/flights', response_model=List[FlightDto], 
    summary="Get all flights",
    description="Returns a list of currently tracked flights. icao24 is the ICAO 24-bit hex address, cls is the callsign, lstCntct is the time of last contact, firstCntct is the time of first contact",
    responses={
        200: {
            "description": "List of flights",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "683f570bd570101935e7ff63",
                            "icao24": "394a03",
                            "cls": "AFR990",
                            "lstCntct": "2025-06-03T20:12:03.615000Z",
                            "firstCntct": "2025-06-03T20:11:55.542000Z"
                        }
                    ]
                }
            }
        }
    }
)
def get_flights(
    request: Request,
    filter: Optional[str] = Query(None, description="Filter flights (e.g. 'mil' for military only)"),
    limit: Optional[int] = Query(None, description="Maximum number of flights to return")
):
    try:
        # Get currently tracked flights from memory
        cached_flights = request.app.state.updater.get_cached_flights()
        
        flight_manager = request.app.state.updater._flight_manager
        modes_util = request.app.state.modes_util
        
        flight_dtos = []
        
        for flight_id, position_report in cached_flights.items():
            if filter == 'mil' and not modes_util.is_military(position_report.icao24):
                continue
                
            callsign = position_report.callsign
            last_contact = flight_manager.flight_last_contact.get(flight_id)
            
            if last_contact:
                flight_dto = FlightDto(
                    id=flight_id,
                    icao24=position_report.icao24,
                    cls=callsign,
                    lstCntct=to_datestring(last_contact),
                    firstCntct=to_datestring(last_contact)  # For live flights, use last contact as first contact approximation
                )
                flight_dtos.append(flight_dto)
        
        flight_dtos.sort(key=lambda x: x.lstCntct, reverse=True)
        
        # Apply limit (default and max limit is MAX_FLIGHTS_LIMIT)
        if limit is not None:
            applied_limit = min(limit, MAX_FLIGHTS_LIMIT)
        else:
            applied_limit = MAX_FLIGHTS_LIMIT
            
        return flight_dtos[:applied_limit]

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid arguments: {str(e)}")


@router.get('/flights/{flight_id}', response_model=FlightDto,
    summary="Get flight by ID",
    description="Returns a specific flight by its ID. icao24 is the ICAO 24-bit hex address, cls is the callsign, lstCntct is the time of last contact, firstCntct is the time of first contact",
    responses={
        200: {
            "description": "Flight details",
            "content": {
                "application/json": {
                    "example": {
                        "id": "683f570bd570101935e7ff63",
                        "icao24": "394a03",
                        "cls": "AFR990",
                        "lstCntct": "2025-06-03T20:14:19.571000Z",
                        "firstCntct": "2025-06-03T20:11:55.542000Z"
                    }
                }
            }
        },
        404: {"description": "Flight not found"}
    }
)
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
                if pos.get("gs") is not None:
                    position_data["gs"] = pos["gs"]
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
                last_position["alt"] != new_position["alt"] or
                last_position.get("gs") != new_position.get("gs")):
                
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

@router.get('/flights/{flight_id}/positions',
    summary="Get flight positions",
    description="Returns an array of position coordinates [lat, lon, alt] for a specific flight",
    responses={
        200: {
            "description": "Array of position coordinates",
            "content": {
                "application/json": {
                    "example": [
                        [47.520152, 7.920509, 32025],
                        [47.655716, 11.048882, 28475]
                    ]
                }
            }
        },
        404: {"description": "Flight not found"}
    }
)
def get_positions(flight_id: str, mongodb: Database = Depends(get_mongodb)):
    try:
        flight = mongodb.flights.find_one({"_id": ObjectId(flight_id)})
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found")

        positions = list(mongodb.positions.find(
            {"flight_id": ObjectId(flight_id)},
            {"lat": 1, "lon": 1, "alt": 1, "_id": 0}  # Only fetch needed fields
        ).sort("timestmp", 1).limit(10000))  # Limit to prevent memory issues

        # Convert to array of arrays format
        result = []
        for p in positions:
            alt = p["alt"] if p["alt"] is not None else -1
            result.append([p["lat"], p["lon"], alt])

        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid flight id format: {str(e)}")


@router.get('/positions',
    summary="Get all positions",
    description="Returns a map with ICAO24 hex address as key and arrays of [lat, lon, alt] coordinates as values",
    responses={
        200: {
            "description": "Map of ICAO24 addresses to position arrays",
            "content": {
                "application/json": {
                    "example": {
                        "300781": [
                            [47.669632, 11.054512, 28200],
                            [47.655716, 11.048882, 28475]
                        ]
                    }
                }
            }
        }
    }
)
def get_all_positions(
    request: Request,
    filter: Optional[str] = Query(None, description="Filter positions (e.g. 'mil' for military only)")
):
    cached_flights = request.app.state.updater.get_cached_flights()
    
    positions = {}
    
    for icao24, flight_data in cached_flights.items():
        if filter == 'mil' and not request.app.state.modes_util.is_military(icao24):
            continue
            
        # Convert flight data to position array format
        if hasattr(flight_data, 'lat') and hasattr(flight_data, 'lon'):
            alt = getattr(flight_data, 'alt', -1)
            if alt is None:
                alt = -1
                
            positions[icao24] = [[flight_data.lat, flight_data.lon, alt]]
    
    return positions

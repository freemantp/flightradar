from fastapi import APIRouter, Request, Query, Path, HTTPException, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel
from pymongo.database import Database
from bson import ObjectId
import logging

from . import router
from .mappers import toFlightDto
from .apimodels import FlightDto
from .websocket_manager import ConnectionManager
from .. import get_mongodb
from .. adsb.db.mongodb_repository import MongoDBRepository
from .. exceptions import ValidationError
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
    # Returns the meta information in snake_case format
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
async def websocket_positions(websocket: WebSocket):
    """WebSocket endpoint for real-time position updates"""
    # Get application state from the WebSocket scope
    app = websocket.app

    # Register the broadcast function if not already registered
    if not hasattr(app.state, "ws_broadcast_registered"):
        def broadcast_positions(positions_dict):
            """Function to broadcast positions to all connected clients"""
            logger.debug(f"WebSocket callback triggered with {len(positions_dict)} positions")

            # Use a thread for handling the async operation from a sync context
            import threading

            def run_in_thread(positions_data):
                import asyncio

                # Create a new event loop for this thread
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

        # Register the callback with the flight updater
        app.state.updater.register_websocket_callback(broadcast_positions)
        app.state.ws_broadcast_registered = True
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
            # Wait for client messages (ping/pong handled automatically)
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Handle client disconnect
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        connection_manager.disconnect(websocket)


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

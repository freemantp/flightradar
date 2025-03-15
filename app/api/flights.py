from fastapi import APIRouter, Request, Query, Path, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel
from pymongo.database import Database
from bson import ObjectId

from . import router
from .mappers import toFlightDto
from .apimodels import FlightDto
from .. import get_mongodb
from .. adsb.db.mongodb_repository import MongoDBRepository
from .. exceptions import ValidationError
from .. scheduling import UPDATER_JOB_NAME

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
        
        # Apply limit if specified
        if limit:
            pipeline.append({"$limit": limit})
            
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


@router.get('/positions/live', response_model=Dict[str, Any])
def get_live_positions(request: Request):
    cached_flights = request.app.state.updater.get_cached_flights()
    return {str(k): v.__dict__ for k, v in cached_flights.items()}


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

from fastapi import APIRouter, Request, Query, Path, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional, Any, Union
from sqlmodel import Session, select
from pydantic import BaseModel

from . import router
from .mappers import toFlightDto
from .apimodels import FlightDto
from .. import get_db
from .. adsb.db.dbrepository import DBRepository
from .. exceptions import ValidationError
from .. adsb.db.dbmodels import Flight
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
    return request.app.state.metaInfo.__dict__

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
    db: Session = Depends(get_db)
):
    try:
        if filter == 'mil':
            statement = (
                select(Flight)
                .where(Flight.is_military == True)
                .order_by(Flight.first_contact.desc())
            )
            if limit:
                statement = statement.limit(limit)
                
            flights = db.exec(statement).all()
            return [toFlightDto(f) for f in flights]
        else:
            statement = (
                select(Flight)
                .order_by(Flight.first_contact.desc())
            )
            if limit:
                statement = statement.limit(limit)
                
            flights = db.exec(statement).all()
            return [toFlightDto(f) for f in flights]

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid arguments")

@router.get('/flights/{flight_id}', response_model=FlightDto)
def get_flight(flight_id: int, db: Session = Depends(get_db)):
    try:
        statement = (
            select(Flight)
            .where(Flight.id == flight_id)
            .order_by(Flight.last_contact.desc())
            .limit(1)
        )
        
        flight = db.exec(statement).first()
        if flight:
            return toFlightDto(flight)
        else:
            raise HTTPException(status_code=404, detail="Flight not found")

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid arguments")

@router.get('/positions/live', response_model=Dict[str, Any])
def get_live_positions(request: Request):
    cached_flights = request.app.state.updater.get_cached_flights()
    return {str(k): v.__dict__ for k, v in cached_flights.items()}

@router.get('/flights/{flight_id}/positions', response_model=List[List[Union[float, int]]])
def get_positions(flight_id: int, db: Session = Depends(get_db)):
    try:
        if DBRepository.flight_exists(db, flight_id):
            positions = DBRepository.get_positions(db, flight_id)
            return [[p.lat, p.lon, p.alt] for p in positions]
        else:
            raise HTTPException(status_code=404, detail="Flight not found")

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid flight id format")

@router.get('/positions')
def get_all_positions(
    request: Request,
    archived: bool = Query(False, description="Include archived positions"),
    filter: Optional[str] = Query(None, description="Filter positions (e.g. 'mil' for military only)"),
    db: Session = Depends(get_db)
):
    positions = DBRepository.get_all_positions(db, archived)

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

from fastapi import Depends, HTTPException, Request
from typing import Dict, Any, List
from pydantic import BaseModel

from . import router
from .. import get_aircraft_repository
from .mappers import toAircraftDto
from .apimodels import AircraftDto


class BulkAircraftRequest(BaseModel):
    icao24_addresses: List[str]

class BulkAircraftResponse(BaseModel):
    aircraft: List[AircraftDto]
    found_count: int
    requested_count: int


@router.get('/aircraft/{icao24addr}', response_model=AircraftDto)
def get_aircraft(
    icao24addr: str,
    request: Request,
    aircraft_repo = Depends(get_aircraft_repository)
):
    aircraft = aircraft_repo.query_aircraft(icao24addr)

    if aircraft:
        return toAircraftDto(aircraft)
    else:
        raise HTTPException(status_code=404, detail="Aircraft not found")


@router.post('/aircraft', response_model=BulkAircraftResponse)
def get_aircraft_collection(
    request: BulkAircraftRequest,
    aircraft_repo = Depends(get_aircraft_repository)
):
    """Get multiple aircraft by ICAO24 addresses (max 50)"""
    
    # Limit to 50 aircraft
    icao24_addresses = request.icao24_addresses[:50]
    
    if not icao24_addresses:
        raise HTTPException(status_code=400, detail="No ICAO24 addresses provided")
    
    aircraft_list = []
    
    for icao24 in icao24_addresses:
        aircraft = aircraft_repo.query_aircraft(icao24)
        if aircraft:
            aircraft_list.append(toAircraftDto(aircraft))
    
    return BulkAircraftResponse(
        aircraft=aircraft_list,
        found_count=len(aircraft_list),
        requested_count=len(icao24_addresses)
    )

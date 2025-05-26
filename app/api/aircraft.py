from fastapi import Depends, HTTPException, Request
from typing import Dict, Any

from . import router
from .. import get_aircraft_repository
from .mappers import toAircraftDto
from .apimodels import AircraftDto


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

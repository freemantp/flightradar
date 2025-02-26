from fastapi import Depends, HTTPException, Request
from typing import Dict, Any

from . import router
from .. import get_basestation_db
from .mappers import toAircraftDto
from .apimodels import AircraftDto


@router.get('/aircraft/{icao24addr}', response_model=AircraftDto)
def get_aircraft(
    icao24addr: str,
    request: Request,
    basestation_db = Depends(get_basestation_db)
):
    aircraft = basestation_db.query_aircraft(icao24addr)

    if aircraft:
        return toAircraftDto(aircraft)
    else:
        raise HTTPException(status_code=404, detail="Aircraft not found")

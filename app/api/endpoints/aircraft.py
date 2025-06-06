from fastapi import Depends, HTTPException
from typing import List
from pydantic import BaseModel, Field

from .. import router
from ..dependencies import AircraftRepositoryDep
from ..mappers import toAircraftDto
from ..models import AircraftDto


class BulkAircraftRequest(BaseModel):
    icao24_addresses: List[str] = Field(..., description="List of ICAO24 hex addresses (max 50)", max_items=50, example=["345314", "394a03"])

class BulkAircraftResponse(BaseModel):
    aircraft: List[AircraftDto]
    found_count: int
    requested_count: int


@router.get('/aircraft/{icao24addr}', response_model=AircraftDto,
    summary="Get aircraft by ICAO24 address",
    description="Returns information about an aircraft based on its ICAO24 hex address. op=Operator, reg=Registration",
    responses={
        200: {
            "description": "Aircraft information",
            "content": {
                "application/json": {
                    "example": {
                        "icao24": "345314",
                        "reg": "EC-MOO",
                        "icaoType": "A321",
                        "type": "Airbus A321 231SL",
                        "op": "Vueling Airlines",
                        "desig": "L2J"
                    }
                }
            }
        },
        404: {"description": "Aircraft not found"}
    }
)
def get_aircraft(
    icao24addr: str,
    aircraft_repo: AircraftRepositoryDep
):
    aircraft = aircraft_repo.query_aircraft(icao24addr)

    if aircraft:
        return toAircraftDto(aircraft)
    else:
        raise HTTPException(status_code=404, detail="Aircraft not found")


@router.post('/aircraft', response_model=BulkAircraftResponse,
    summary="Get multiple aircraft",
    description="Get multiple aircraft by ICAO24 addresses (max 50). Returns aircraft information including operator and registration details.",
    responses={
        200: {
            "description": "Bulk aircraft response",
            "content": {
                "application/json": {
                    "example": {
                        "aircraft": [
                            {
                                "icao24": "345314",
                                "reg": "EC-MOO",
                                "icaoType": "A321",
                                "type": "Airbus A321 231SL",
                                "op": "Vueling Airlines",
                                "desig": "L2J"
                            }
                        ],
                        "found_count": 1,
                        "requested_count": 1
                    }
                }
            }
        },
        400: {"description": "Invalid request or no ICAO24 addresses provided"}
    }
)
def get_aircraft_collection(
    request: BulkAircraftRequest,
    aircraft_repo: AircraftRepositoryDep
):
    
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

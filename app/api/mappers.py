from .models import FlightDto, AircraftDto, to_datestring
from typing import Dict, Any
from ..core.models.aircraft import Aircraft


def toFlightDto(flight: Dict[str, Any]) -> FlightDto:
    return FlightDto(
        id=str(flight["_id"]),
        icao24=flight["modeS"],
        cls=flight.get("callsign"),
        lstCntct=to_datestring(flight["last_contact"]),
        firstCntct=to_datestring(flight["first_contact"])
    )


def toAircraftDto(aircraft: Aircraft) -> AircraftDto:
    return AircraftDto(
        icao24=aircraft.modes_hex,
        reg=aircraft.reg,
        icaoType=aircraft.icao_type_code,
        type=aircraft.aircraft_type_description,
        op=aircraft.operator,
        desig=aircraft.icao_type_designator
    )

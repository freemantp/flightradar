from .apimodels import FlightDto, AircraftDto, to_datestring
from ..adsb.db.dbmodels import Flight
from ..adsb.aircraft import Aircraft


def toFlightDto(flight: Flight) -> FlightDto:
    return FlightDto(
        id=flight.id,
        icao24=flight.modeS,
        cls=flight.callsign,
        lstCntct=to_datestring(flight.last_contact),
        firstCntct=to_datestring(flight.first_contact)
    )


def toAircraftDto(aircraft: Aircraft) -> AircraftDto:
    return AircraftDto(
        icao24=aircraft.modes_hex,
        reg=aircraft.reg,
        icaoType=aircraft.type1,
        type=aircraft.type2,
        op=aircraft.operator
    )

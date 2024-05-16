from automapper import mapper
from .apimodels import FlightDto, AircraftDto
from ..adsb.db.dbmodels import Flight
from ..adsb.aircraft import Aircraft


def toFlightDto(flight: Flight) -> FlightDto:
    return mapper.to(FlightDto).map(flight, fields_mapping={
        'icao24': flight.modeS,
        'cls': flight.callsign,
        'lstCntct': flight.last_contact,
        'firstCntct': flight.first_contact})


def toAircraftDto(aircraft: Aircraft) -> AircraftDto:

    return mapper.to(AircraftDto).map(aircraft, fields_mapping={
        'icao24': aircraft.modes_hex,
        'reg': aircraft.reg,
        'icaoType': aircraft.type1,
        'type': aircraft.type2,
        'op': aircraft.operator})

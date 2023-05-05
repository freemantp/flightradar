from datetime import datetime

def to_datestring(obj: datetime) -> str:
    if obj.tzinfo:
        # eg: '2015-09-25T23:14:42.588601+00:00'
        return obj.isoformat('T')
    else:
        # No timezone present - assume UTC.
        # eg: '2015-09-25T23:14:42.588601Z'
        return obj.isoformat('T') + 'Z'

class FlightDto:
    def __init__(self, id: str, icao24: str, cls: str, lstCntct: datetime, firstCntct: datetime):
        self.id = id
        self.icao24 = icao24
        self.cls = cls
        self.lstCntct = to_datestring(lstCntct)
        self.firstCntct = to_datestring(firstCntct)

class AircraftDto:
    def __init__(self, icao24: str, reg: str, icaoType: str, type: str, op: str):
        self.icao24 = icao24
        self.reg: reg
        self.icaoType = icaoType
        self.type = type
        self.op = op

import datetime
from flask import json
from decimal import Decimal

from ..adsb.db.dbmodels import Flight, Position

class RadarJsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            if o.tzinfo:
                # eg: '2015-09-25T23:14:42.588601+00:00'
                return o.isoformat('T')
            else:
                # No timezone present - assume UTC.
                # eg: '2015-09-25T23:14:42.588601Z'
                return o.isoformat('T') + 'Z'

        if isinstance(o, datetime.date):
            return o.isoformat()

        if isinstance(o, Decimal):
            return float(o)

        if isinstance(o, Flight):
            return {'id': o.id, 'cls': o.callsign, 'lstCntct': o.last_contact }

        if isinstance(o, Position):
            return [o.lat, o.lon, o.alt]       
        return json.JSONEncoder.default(self, o)

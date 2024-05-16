from . import api
from .. import get_basestation_db
from .mappers import toAircraftDto
from flask import jsonify, abort


@api.route('/aircraft/<icao24addr>', methods=['GET'])
def get_aircraft(icao24addr):

    aircraft = get_basestation_db().query_aircraft(icao24addr)

    if aircraft:
        return jsonify(toAircraftDto(aircraft).__dict__)
    else:
        abort(404)

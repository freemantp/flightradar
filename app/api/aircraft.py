from . import api
from .. import get_basestation_db

from flask import jsonify, abort



@api.route('/aircraft/<icao24addr>', methods=['GET']) 
def get_aircraft(icao24addr):

    aircraft = get_basestation_db().query_aircraft(icao24addr)
    
    if aircraft:
        return jsonify(aircraft) 
    else:
        abort(404)


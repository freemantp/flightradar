from . import api
from .. import get_basestation_db
from .. util.flask_util import get_boolean_arg
from .. adsb.db.dbrepository import DBRepository

from flask import current_app as app, Response, request, jsonify

@api.route("/flight/<flight_id>/positions") 
def get_positions(flight_id):

    if flight_id:

        try:
            int(flight_id)

            positions = DBRepository.get_positions(flight_id)

            if positions:
                pos_entries = [[ [p.lat, p.lon, p.alt] for p in positions]]
                return jsonify(pos_entries)

        except ValueError:
            return "Invalid flight id format", 400
        except:
            return 500
    
    return 'Not found', 404


@api.route("/positions") 
def get_all_positions():
    archived = get_boolean_arg('archived')
    positions = DBRepository.get_all_positions(archived)
    return jsonify(positions)

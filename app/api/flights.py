from . import api
from .. import get_basestation_db
from .. util.flask_util import get_boolean_arg
from .. adsb.db.dbrepository import DBRepository
from .. exceptions import ValidationError

from flask import current_app as app, Response, request, jsonify, abort


@api.route("/flight/<flight_id>/positions") 
def get_positions(flight_id):
    try:
        int(flight_id)

        if DBRepository.flight_exists(flight_id):
            positions = DBRepository.get_positions(flight_id)
            pos_entries = [[ [p.lat, p.lon, p.alt] for p in positions]]
            return jsonify(pos_entries)
        else:
            print("Not found")
            abort(404)

    except ValueError:
        raise ValidationError("Invalid flight id format")

@api.route("/positions") 
def get_all_positions():
    archived = get_boolean_arg('archived')
    positions = DBRepository.get_all_positions(archived)
    return jsonify(positions)

@api.errorhandler(ValidationError)
def validation_error(e):
    return jsonify({"error": e.args[0]}), 400

@api.app_errorhandler(500)
def validation_error(e):
    return jsonify({"error": e.args[0]}), 500

@api.app_errorhandler(404)
def validation_error(e):
    return '', 404
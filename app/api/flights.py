from . import api
from .. util.flask_util import get_boolean_arg
from .. adsb.db.dbrepository import DBRepository
from .. exceptions import ValidationError
from .. adsb.db.dbmodels import Flight
from .. scheduling import UPDATER_JOB_NAME

from flask import current_app as app, Response, request, jsonify, abort

@api.route('/info')
def get_meta_info():
    return jsonify(app.metaInfo.__dict__)

@api.route('/alive')
def alive():
    return "Yes"

@api.route('/ready')
def ready():
    updater_job = app.apscheduler.get_job(UPDATER_JOB_NAME)
    if updater_job and not updater_job.pending:
        return "Yes"
    else:
        abort(500)    

@api.route('/flights')
def get_flights():
    try:

        
        filter = request.args.get('filter', default = None, type = str)
        limit = request.args.get('limit', default = None, type = int)

        if filter == 'mil':
            result_set = (Flight.select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact, Flight.first_contact)
                    .where(Flight.is_military == True)
                    .order_by(Flight.first_contact.desc()).limit(limit))

            return jsonify([f for f in result_set])
        else:
            result_set = (Flight.select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact, Flight.first_contact)
                    .order_by(Flight.first_contact.desc()).limit(limit))

            return jsonify([f for f in result_set])

    except ValueError:
        raise ValidationError('invalid arguments')

@api.route('/flights/<flight_id>')
def get_flight(flight_id):
    try:
        result_set = (Flight.select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact, Flight.first_contact)
                            .where(Flight.id == flight_id)
                            .order_by(Flight.last_contact.desc()).limit(1))

        if result_set.exists():
            return jsonify(result_set[0])
        else:
            abort(404)
            
    except ValueError:
        raise ValidationError('invalid arguments')    

@api.route('/positions/live', methods=['GET'])
def get_live_positions():
    return jsonify(app.updater.get_cached_flights())


@api.route('/flights/<flight_id>/positions') 
def get_positions(flight_id):
    try:
        int(flight_id)

        if DBRepository.flight_exists(flight_id):
            positions = DBRepository.get_positions(flight_id)
            return jsonify([[p for p in positions]])
        else:
            abort(404)

    except ValueError:
        raise ValidationError('Invalid flight id format')

@api.route('/positions') 
def get_all_positions():
    archived = get_boolean_arg('archived')
    filter = request.args.get('filter', default = None, type = str)

    positions = DBRepository.get_all_positions(archived)

    if filter == 'mil':
        return jsonify({key:value for (key,value) in positions.items() if app.modes_util.is_military(key)})
    else:
        return jsonify(positions) 


@api.after_request
def after_request(response):

    #TODO: look into Flask-Cors (https://flask-cors.readthedocs.io)

    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')  
    return response

@api.errorhandler(ValueError)
def validation_error(e):
    return jsonify({'error': e.args[0]}), 400

@api.errorhandler(ValueError)
def validation_error(e):
    return jsonify({'error': e.args[0]}), 400    

@api.app_errorhandler(500)
def handle_generic_err(e):

    message = e.args[0]
    if isinstance(e, NameError):
        message = 'An internal eror occured'

    return jsonify({'error':message}), 500

@api.app_errorhandler(404)
def not_found(e):
    return '', 404
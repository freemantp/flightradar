import datetime
import json
import logging
import atexit

import time
from pytz import timezone
from dateutil import tz

from flask import Flask, Response, g, jsonify, render_template, request
from peewee import fn

from . import create_app

from adsb.flightupdater import FlightUpdater
from adsb.aircraft import Aircraft
from adsb.config import Config
from adsb.db.basestationdb import BaseStationDB
from adsb.db.dbmodels import init_db_schema, Position, Flight
from adsb.db.dbrepository import DBRepository

def get_basestation_db():
    basestation_db = getattr(g, '_basestation_db', None)
    if basestation_db is None:
        basestation_db = g._basestation_db = BaseStationDB(app.config['data_folder'] + "BaseStation.sqb")
    return basestation_db

conf = Config()
conf.from_file('config.json')

app = create_app(conf)

pos_db = None

@app.route("/") 
def index():

    if app.config['delete_after'] > 0:

        result_set = (Flight.select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
                            .order_by(Flight.last_contact.desc()))
    else:
        result_set = (Flight.select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
                            .order_by(Flight.last_contact.desc()))

    return render_flights(result_set)

@app.route("/archived") 
def archived():

    result_set = (Flight
        .select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
        .where(Flight.archived == True) )

    return render_flights(result_set, True)


def render_flights(flights, archived = False):

    response = []

    for flight in flights:


        aircraft = g._basestation_db.query_aircraft(flight.modeS)
        
        if not aircraft:
            aircraft = Aircraft(flight.modeS)
        response.append((aircraft.__dict__, flight.last_contact, flight.archived, flight.callsign, flight.id))
            
    metaInfo = {
        'updaterAlive' : updater.isAlive(),
        'serviceAlive' : updater.is_service_alive(),
        'mode' : 'ModeSmixer2' if app.config['type'] == 'mm2' else 'VirtualRadar',
        'archived' : archived
    }    

    return render_template('aircraft.html', airplanes=response, status=metaInfo, silhouette=updater.get_silhouete_params())

@app.route("/pos/<flight_id>") 
def get_positions(flight_id):

    if flight_id:

        positions = DBRepository.get_positions(flight_id)
        pos_entries = [[ [p.lat, p.lon, p.alt] for p in positions]]
 
        return Response(json.dumps(pos_entries), mimetype='application/json')
    else:
        return "Not found", 404

@app.route("/positions") 
def get_all_positions():

    archived = get_boolean_arg('archived')
    positions = DBRepository.get_all_positions(archived)
    entries = [[[p.lat, p.lon, p.alt] for p in l] for l in positions] 

    return Response(json.dumps(entries), mimetype='application/json')

@app.route("/map/<flight_id>") 
def get_map(flight_id):
    return render_template('map.html', flight_id=flight_id)

@app.route("/map") 
def get_map_all():
    archived = get_boolean_arg('archived')
    return render_template('map.html', archived=archived)

@app.before_request
def before_request():
    if pos_db.is_closed():
        pos_db.connect()

@app.after_request
def after_request(response):
    pos_db.close()

    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')  
    return response    

@app.template_filter('localdate')
def datetimefilter(value, format="%d.%m.%Y %H:%M"):    
    utctime = timezone('UTC').localize(value)
    local_time = utctime.astimezone(tz.gettz('Europe/Zurich'))
    return local_time.strftime(format)

@atexit.register
def _stop_worker_threads():
    pos_db.stop()
    updater.stop()

def get_boolean_arg(argname):
    arch_arg = request.args.get(argname)
    if arch_arg:
        return arch_arg.lower() == 'true'
    else:
        return False

def get_config():
    conf = getattr(g, '_config', None)
    if conf is None:

        g._config = conf
    return conf

if __name__ == '__main__':

    conf = Config()
    conf.from_file('config.json')

    pos_db = init_db_schema(conf.data_folder)

    updater = FlightUpdater(conf, pos_db)
    updater.start()

    app.run(host='0.0.0.0', debug=False)
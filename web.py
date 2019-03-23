import datetime
import json
import logging
import atexit

import time
from pytz import timezone
from dateutil import tz

from flask import Flask, Response, g, jsonify, render_template, request
from peewee import fn


from adsb.acprocessor import AircaftProcessor
from adsb.aircraft import Aircraft
from adsb.config import Config
from adsb.db.basestationdb import BaseStationDB
from adsb.db.dbmodels import init_db_schema, Position, Flight
from adsb.db.dbrepository import DBRepository

logging.basicConfig(level=logging.INFO)

def get_config():
    conf = getattr(g, '_config', None)
    if conf is None:
        conf = Config()
        conf.from_file('config.json')
        g._config = conf
    return conf

def get_basestation_db():
    basestation_db = getattr(g, '_basestation_db', None)
    if basestation_db is None:
        config = get_config()
        basestation_db = g._basestation_db = BaseStationDB(config.data_folder + "BaseStation.sqb")
    return basestation_db

app = Flask(__name__)

pos_db = None

@app.route("/") 
def index():

    if get_config().delete_after > 0:
        #threshold_data = datetime.datetime.utcnow() - datetime.timedelta(minutes=get_config().delete_after)

        result_set = (Flight.select(Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
                            .order_by(Flight.last_contact.desc()))
        
        # result_set = (Position
        #     .select(Position.icao, Position.archived, fn.MAX(Position.timestmp).alias('timestmp') )
        #     .where(Position.timestmp > threshold_data)
        #     .group_by(Position.icao
        #     .order_by(fn.MAX(Position.timestmp).desc()))

    else:

        result_set = (Flight.select(Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
                            .order_by(Flight.last_contact.desc()))

        # result_set = (Position
        #     .select(Position.icao, Position.archived, fn.MAX(Position.timestmp).alias('timestmp') )
        #     .group_by(Position.icao)
        #     .order_by(fn.MAX(Position.timestmp).desc()))

    return render_entries(result_set)

@app.route("/archived") 
def archived():

    result_set = (Flight
        .select(Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
        .where(Flight.archived == True) )

    return render_entries(result_set, True)


def render_entries(entries, archived = False):

    response = []

    for entry in entries:

        bs_db = get_basestation_db()
        aircraft = bs_db.query_aircraft(entry.modeS)
        
        if not aircraft:
            aircraft = Aircraft(entry.modeS)
        response.append((aircraft.__dict__, entry.last_contact, entry.archived, entry.callsign))
            
    metaInfo = {
        'updaterAlive' : updater.isAlive(),
        'serviceAlive' : updater.is_service_alive(),
        'mode' : 'ModeSmixer2' if get_config().type == 'mm2' else 'VirtualRadar',
        'archived' : archived
    }    

    return render_template('aircraft.html', airplanes=response, status=metaInfo, silhouette=updater.get_silhouete_params())

@app.route("/pos/<modeS_addr>") 
def get_positions(modeS_addr):

    flights = DBRepository.get_flights(modeS_addr)

    if len(flights) > 0:

        positions = DBRepository.get_positions(flights[0])
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

@app.route("/map/<icao24>") 
def get_map(icao24):
    return render_template('map.html', icao24=icao24)

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

def get_boolean_arg(argname):
    arch_arg = request.args.get(argname)
    if arch_arg:
        return arch_arg.lower() == 'true'
    else:
        return False

if __name__ == '__main__':

    conf = None
    with app.app_context():
         conf = get_config()
    pos_db = init_db_schema(conf.data_folder)

    updater = AircaftProcessor(conf, pos_db)
    updater.start()

    app.run(host='0.0.0.0', debug=False)

    updater.stop()

import json, time

from flask import Flask
from flask import Response
from flask import render_template
from flask import jsonify
from flask import g

from peewee import SqliteDatabase, fn

from adsb.config import Config
from adsb.basestationdb import BaseStationDB
from adsb.acprocessor import AircaftProcessor
from adsb.dbmodels import Position, database_proxy

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

@app.route("/api")
def rest_api():
    response = []

    bs_db = get_basestation_db()

    for icao24, tmstmp in updater.aircraft.items():
        aircraft = bs_db.query_aircraft(icao24)

        if aircraft:
            response.append((aircraft.__dict__, time.ctime(tmstmp)))

    return Response(json.dumps(response), mimetype='application/json')

@app.route("/") 
def index():

    response = []

    query = (Position
         .select(Position.icao, fn.MAX(Position.timestmp).alias('timestmp') )
         .group_by(Position.icao)
         .order_by(fn.MAX(Position.timestmp).desc()))

    for entry in query:

        bs_db = get_basestation_db()
        aircraft = bs_db.query_aircraft(entry.icao)

        if aircraft:
            response.append((aircraft.__dict__, entry.timestmp))

    statusInfo = {
        'updaterAlive' : updater.isAlive(),
        'serviceAlive' : updater.is_service_alive(),
        'mode' : 'ModeSmixer2' if get_config().type == 'mm2' else 'VirtualRadar'     
    }    
    
    return render_template('aircraft.html', airplanes=response, status=statusInfo, silhouette=updater.get_silhouete_params())

@app.route("/pos/<icao24>") 
def get_positions(icao24):

    query = (Position
            .select(Position.lat, Position.lon, Position.alt)
            .where(Position.icao == icao24 )
    )

    entries = list(map(lambda p : [p.lat, p.lon, p.alt], query))

    if entries:
        return Response(json.dumps(entries), mimetype='application/json')
    else:
        return "Not found", 404

@app.route("/positions") 
def get_all_positions():

    query = (Position.select(Position.icao, Position.lat, Position.lon, Position.alt, Position.timestmp)
        .order_by(Position.icao, Position.timestmp.desc()) )

    positions = dict()
    for x in query:
        if x.icao not in positions:
            positions[x.icao] = []        
        positions[x.icao].append((x.lat, x.lon))

    if positions:
        return Response(json.dumps(positions), mimetype='application/json')
    else:
        return "Not found", 404

@app.route("/map/<icao24>") 
def get_map(icao24):
    return render_template('map.html', icao24=icao24)

@app.route("/map") 
def get_map_all():
    return render_template('map.html', icao24='')

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

def init_db(conf):
    position_db =  SqliteDatabase('{:s}/positions.db'.format(conf.data_folder))
    database_proxy.initialize(position_db)
    position_db.create_tables([Position]) #init db
    return position_db

if __name__ == '__main__':

    conf = None
    with app.app_context():
         conf = get_config()
    pos_db = init_db(conf)

    updater = AircaftProcessor(conf, pos_db)
    updater.start()

    app.run(host='0.0.0.0', debug=False)

    updater.stop()


from flask import Flask, Blueprint, g
import logging

from .adsb.config import Config
from .adsb.db.basestationdb import BaseStationDB
from .adsb.db.dbmodels import init_db_schema
from .adsb.flightupdater import FlightUpdater

logging.basicConfig(level=logging.INFO)

main = Blueprint('main', __name__)

def get_basestation_db():

    from flask import current_app as app

    basestation_db = getattr(g, '_basestation_db', None)
    if basestation_db is None:
        basestation_db = g._basestation_db = BaseStationDB(app.config['data_folder'] + "BaseStation.sqb") #TODO: path join
    return basestation_db

def create_updater(config: Config, flight_db):    
    updater = FlightUpdater.Instance()
    updater.initialize(config, flight_db)
    return updater

def create_app(config: Config):
    app = Flask(__name__)
    #app.config.from_json()
    #app.config.from_object()

    app.config['delete_after'] = config.delete_after
    app.config['type'] = config.type
    app.config['data_folder'] = config.data_folder

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint, url_prefix='/')

    return app
from flask import Flask, Blueprint, g
import logging

from .config import Config
from .adsb.db.basestationdb import BaseStationDB
from .adsb.db.dbmodels import init_db_schema
from .adsb.flightupdater import FlightUpdater

logging.basicConfig(level=logging.INFO)

main = Blueprint('main', __name__)

def get_basestation_db():

    from flask import current_app as app

    basestation_db = getattr(g, '_basestation_db', None)
    if basestation_db is None:
        basestation_db = g._basestation_db = BaseStationDB(app.config['DATA_FOLDER'] + "BaseStation.sqb") #TODO: path join
    return basestation_db

def create_updater(config):    
    updater = FlightUpdater.Instance()
    updater.initialize(config)
    return updater

def create_app():
    app = Flask(__name__)

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint, url_prefix='/')

    return app
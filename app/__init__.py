from flask import Flask, Blueprint, g
from werkzeug.contrib.fixers import ProxyFix
from os import path

from .config import Config
from .adsb.db.basestationdb import BaseStationDB
from .adsb.db.dbmodels import init_db_schema
from .adsb.flightupdater import FlightUpdater
from .adsb.util.logging import init_logging

import atexit

main = Blueprint('main', __name__)

def get_basestation_db():
    from flask import current_app as app

    basestation_db = getattr(g, '_basestation_db', None)
    if basestation_db is None:
        basestation_db = g._basestation_db = BaseStationDB(path.join(app.config['DATA_FOLDER'], 'BaseStation.sqb'))
    return basestation_db

def create_updater(config):    
    updater = FlightUpdater.Instance()
    updater.initialize(config)
    return updater

def create_app():
    app = Flask(__name__)

    app.wsgi_app = ProxyFix(app.wsgi_app)

    conf = Config()
    app.config.from_object(conf)
    init_logging(conf.LOGGING_CONFIG)

    flight_db = init_db_schema(conf.DATA_FOLDER)

    updater = create_updater(conf)
    app.updater = updater
    updater.start()

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint, url_prefix='/')

    @atexit.register
    def _stop_worker_threads():
        flight_db.stop()
        updater.stop()

    return app


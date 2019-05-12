from flask import Flask, Blueprint, g
from os import path
from flask_apscheduler import APScheduler
import atexit
import logging

from .config import Config
from .adsb.db.basestationdb import BaseStationDB
from .adsb.db.dbmodels import init_db_schema
from .adsb.flightupdater import FlightUpdater
from .adsb.util.logging import init_logging
from .adsb.datasource.airplane_crawler import AirplaneCrawler

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

    # TODO: make configurable
    if True:
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)

    # Config
    conf = Config()
    app.config.from_object(conf)
    init_logging(conf.LOGGING_CONFIG)

    flight_db = init_db_schema(conf.DATA_FOLDER)

    # Async tasks
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    logging.getLogger("apscheduler.executors.default").setLevel('WARN')

    updater = create_updater(conf)
    app.updater = updater

    crawler = AirplaneCrawler(conf)
    app.crawler = crawler

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint, url_prefix='/')

    @scheduler.task('interval', id='flight_updater_job', seconds=1, misfire_grace_time=3, coalesce=True)
    def update_flights():

        with app.app_context():
             app.updater.update()

    @scheduler.task('interval', id='airplane_crawler', seconds=30, misfire_grace_time=90, coalesce=True)
    def crawl_airplanes():
        with app.app_context():
             app.crawler.crawl_sources()    

    @atexit.register
    def _stop_worker_threads():
        flight_db.stop()

    return app


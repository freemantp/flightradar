import logging
import time
from flask import Flask
from flask_apscheduler import APScheduler
from apscheduler.events import *
from .config import Config
from .adsb.flightupdater import FlightUpdater
from .adsb.datasource.airplane_crawler import AirplaneCrawler

logger = logging.getLogger(__name__)

UPDATER_JOB_NAME = 'flight_updater_job'

def create_updater(config):    
    updater = FlightUpdater.Instance()
    updater.initialize(config)
    return updater

def configure_scheduling(app: Flask, conf: Config):

    # Async tasks
    scheduler = APScheduler()
    scheduler.init_app(app)

    updater = create_updater(conf)
    app.updater = updater

    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARN)
    logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)

    def my_listener(event):
        if event.code == EVENT_JOB_MAX_INSTANCES and event.job_id == UPDATER_JOB_NAME:
            logger.warn('Updater could not be started, previous is still running')

    scheduler.add_listener(my_listener, EVENT_JOB_MAX_INSTANCES | EVENT_JOB_MISSED)
    
    @scheduler.task('interval', id=UPDATER_JOB_NAME, seconds=1, misfire_grace_time=3, coalesce=True)
    def update_flights():
        with app.app_context():
            app.updater.update()

    if conf.UNKNOWN_AIRCRAFT_CRAWLING and conf.RADAR_SERVICE_TYPE == 'mm2': # TODO enable vrs

        crawler = AirplaneCrawler(conf)
        app.crawler = crawler

        @scheduler.task('interval', id='airplane_crawler', seconds=30, misfire_grace_time=90, coalesce=True)
        def crawl_airplanes():
            with app.app_context():
                app.crawler.crawl_sources()

    app.apscheduler.start()
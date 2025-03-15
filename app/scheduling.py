import logging
import time
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import *
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from .config import Config
from .adsb.flightupdater import FlightUpdater
from .adsb.datasource.airplane_crawler import AirplaneCrawler

logger = logging.getLogger(__name__)

UPDATER_JOB_NAME = 'flight_updater_job'

def create_updater(config):
    updater = FlightUpdater()
    updater.initialize(config)
    return updater

def configure_scheduling(app: FastAPI, conf: Config):
    # Configure job stores and executors
    jobstores = {
        'default': MemoryJobStore()
    }
    executors = {
        'default': ThreadPoolExecutor(20)
    }
    job_defaults = {
        'coalesce': True,
        'max_instances': 1
    }

    # Create scheduler
    scheduler = AsyncIOScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults)
    
    # Store scheduler in app state
    app.state.apscheduler = scheduler
    
    # Create updater
    updater = create_updater(conf)
    app.state.updater = updater

    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARN)
    logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)

    def my_listener(event):
        if event.code == EVENT_JOB_MAX_INSTANCES and event.job_id == UPDATER_JOB_NAME:
            logger.warning('Skipping updater cycle - previous still running')

    scheduler.add_listener(my_listener, EVENT_JOB_MAX_INSTANCES | EVENT_JOB_MISSED)
    
    # Add jobs to scheduler
    scheduler.add_job(
        id=UPDATER_JOB_NAME,
        func=lambda: app.state.updater.update(),
        trigger='interval',
        seconds=1.0,
        misfire_grace_time=5,
        coalesce=True
    )

    if conf.UNKNOWN_AIRCRAFT_CRAWLING and conf.RADAR_SERVICE_TYPE == 'mm2': # TODO enable vrs
        crawler = AirplaneCrawler(conf)
        app.state.crawler = crawler

        scheduler.add_job(
            id='airplane_crawler',
            func=lambda: app.state.crawler.crawl_sources(),
            trigger='interval',
            seconds=30,
            misfire_grace_time=90,
            coalesce=True
        )

    # Start the scheduler
    scheduler.start()
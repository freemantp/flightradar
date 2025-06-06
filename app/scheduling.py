import logging
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import *
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from .config import Config
from .core.services.flight_updater_coordinator import FlightUpdaterCoordinator
from .crawling.crawler import AirplaneCrawler

logger = logging.getLogger(__name__)

UPDATER_JOB_NAME = 'flight_updater_job'
CRAWLER_RUN_INTERVAL_SEC = 20

def create_updater(config, mongodb=None):
    updater = FlightUpdaterCoordinator()
    updater.initialize(config, mongodb)
    return updater

def ensure_db_indexes(app):
    """Make sure database indexes are correctly configured"""
    if hasattr(app.state, 'mongodb') and app.state.mongodb is not None:
        from .data.repositories.mongodb_repository import MongoDBRepository
        # Create a temporary repository to ensure indexes
        repo = MongoDBRepository(app.state.mongodb)
        # Force index check/creation
        repo._ensure_indexes()
        logger.info("MongoDB indexes have been verified and updated if needed")

def configure_scheduling(app: FastAPI, conf: Config):
    jobstores = {
        'default': MemoryJobStore()
    }
    
    executors = {
        'default': ThreadPoolExecutor(40) 
    }
    
    job_defaults = {
        'coalesce': True,
        'max_instances': 1
    }

    ensure_db_indexes(app)

    scheduler = AsyncIOScheduler(
        jobstores=jobstores, 
        executors=executors, 
        job_defaults=job_defaults
    )
    
    app.state.apscheduler = scheduler
    
    updater = create_updater(conf, app.state.mongodb)
    app.state.updater = updater

    # Reduce logging noise
    logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)  
    logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)

    def my_listener(event):
        if event.code == EVENT_JOB_MAX_INSTANCES and event.job_id == UPDATER_JOB_NAME:
            logger.debug('Skipping updater cycle - previous still running')

    scheduler.add_listener(my_listener, EVENT_JOB_MAX_INSTANCES | EVENT_JOB_MISSED)
    

    scheduler.add_job(
        id=UPDATER_JOB_NAME,
        func=lambda: app.state.updater.update(),
        trigger='interval',
        seconds=2.0,  # Changed from 1.0 to 2.0 to avoid overloading
        misfire_grace_time=10,  # Increased for reliability
        coalesce=True
    )

    if conf.UNKNOWN_AIRCRAFT_CRAWLING:
        crawler = AirplaneCrawler(conf, app.state.mongodb)
        app.state.crawler = crawler

        logger.info(f"Scheduling aircraft metadata crawler job (every {CRAWLER_RUN_INTERVAL_SEC} seconds)...")
        scheduler.add_job(
            id='airplane_crawler',
            func=lambda: app.state.crawler.crawl_sources(),
            trigger='interval',
            seconds=CRAWLER_RUN_INTERVAL_SEC,
            misfire_grace_time=120,
            coalesce=True
        )
    else:
        logger.info("Unknown aircraft crawling disabled")

    scheduler.start()

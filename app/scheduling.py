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
    # Configure job stores and executors with optimized settings for performance
    jobstores = {
        'default': MemoryJobStore()
    }
    
    # Increase thread pool size for better concurrency
    executors = {
        'default': ThreadPoolExecutor(40)  # Doubled for better parallel processing
    }
    
    job_defaults = {
        'coalesce': True,
        'max_instances': 1
    }

    # Make sure database indexes are properly set up
    ensure_db_indexes(app)

    # Create scheduler with optimized settings
    scheduler = AsyncIOScheduler(
        jobstores=jobstores, 
        executors=executors, 
        job_defaults=job_defaults
    )
    
    # Store scheduler in app state
    app.state.apscheduler = scheduler
    
    updater = create_updater(conf, app.state.mongodb)
    app.state.updater = updater

    # Reduce logging noise
    logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)  # Reduced from WARN
    logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)

    def my_listener(event):
        if event.code == EVENT_JOB_MAX_INSTANCES and event.job_id == UPDATER_JOB_NAME:
            logger.debug('Skipping updater cycle - previous still running')

    scheduler.add_listener(my_listener, EVENT_JOB_MAX_INSTANCES | EVENT_JOB_MISSED)
    
    # Optimize the update interval to reduce database load
    # Adjust from 1.0 to 2.0 seconds to allow processing to complete
    # This effectively halves the database load while still maintaining 
    # good responsiveness for real-time flight tracking
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

        # Keep crawler at 20-second interval but increase grace time
        scheduler.add_job(
            id='airplane_crawler',
            func=lambda: app.state.crawler.crawl_sources(),
            trigger='interval',
            seconds=20,
            misfire_grace_time=120,  # Increased from 90 for better reliability
            coalesce=True
        )

    # Start the scheduler
    scheduler.start()
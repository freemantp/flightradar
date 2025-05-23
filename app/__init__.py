from fastapi import FastAPI, Request, Depends
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from os import path
from contextvars import ContextVar

from .config import Config, app_state
from .meta import MetaInformation
from .adsb.db.basestation_mongodb import BaseStationMongoDB
from .adsb.db import init_mongodb
from .adsb.util.logging import init_logging

from .scheduling import configure_scheduling

# Context variables to store request-scoped objects
basestation_db_var = ContextVar("basestation_db", default=None)


def get_basestation_db(request: Request):
    basestation_db = basestation_db_var.get()
    if basestation_db is None:
        basestation_db = BaseStationMongoDB(
            request.app.state.mongodb
        )
        basestation_db_var.set(basestation_db)
    return basestation_db


def get_mongodb(request: Request):
    yield request.app.state.mongodb


def create_app():
    app = FastAPI(
        title="Flight Radar",
        description="ADS-B flight data API",
        version="1.0.0"
    )

    # Config
    conf = Config()
    init_logging(conf.LOGGING_CONFIG)

    # Initialize MongoDB
    mongodb = init_mongodb(
        conf.MONGODB_URI,
        conf.MONGODB_DB_NAME
    )
    app.state.mongodb = mongodb
    app_state.mongodb = mongodb

    # Store app state
    app.state.config = conf
    app.state.metaInfo = MetaInformation()

    from .adsb.util.modes_util import ModesUtil
    app.state.modes_util = ModesUtil(conf.DATA_FOLDER)

    # Add middleware
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Pragma", "Cache-Control", "Expires"],
    )

    # Import and include routers
    from .api import router as api_router
    app.include_router(api_router, prefix="/api/v1")

    # Configure async tasks
    @app.on_event("startup")
    async def startup():
        configure_scheduling(app, conf)

    @app.on_event("shutdown")
    def shutdown():
        pass

    return app

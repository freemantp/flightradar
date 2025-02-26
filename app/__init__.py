from fastapi import FastAPI, Request, Depends
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from os import path
from contextvars import ContextVar

from .config import Config, app_state
from .meta import MetaInformation
from .adsb.db.basestationdb import BaseStationDB
from .adsb.db.dbmodels import init_db, Flight, Position
from .adsb.util.logging import init_logging
from .adsb.util.modes_util import ModesUtil

from .scheduling import configure_scheduling

# Context variables to store request-scoped objects
basestation_db_var = ContextVar("basestation_db", default=None)


def get_basestation_db(request: Request):
    basestation_db = basestation_db_var.get()
    if basestation_db is None:
        basestation_db = BaseStationDB(path.join(request.app.state.config.DATA_FOLDER, 'BaseStation.sqb'))
        basestation_db_var.set(basestation_db)
    return basestation_db


def get_db(request: Request):
    with Session(request.app.state.db_engine) as session:
        yield session


def create_app():
    app = FastAPI(
        title="Flight Radar",
        description="ADS-B flight data API",
        version="1.0.0"
    )

    # Config
    conf = Config()
    init_logging(conf.LOGGING_CONFIG)

    # Init database
    db_engine = init_db(conf.DATA_FOLDER)

    # Store app state
    app.state.config = conf
    app.state.metaInfo = MetaInformation()
    app.state.db_engine = db_engine
    app.state.modes_util = ModesUtil(conf.DATA_FOLDER)
    
    # Also store in global app_state for compatibility
    app_state.db_engine = db_engine

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

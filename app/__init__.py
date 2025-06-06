import logging
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware

from .config import Config, app_state
from .meta import MetaInformation
from .data import init_mongodb
from .core.utils.logging import init_logging

from .scheduling import configure_scheduling



def create_app():
    app = FastAPI(
        title="Flight Radar",
        description="ADS-B flight data API",
        version="1.0.0"
    )

    # Config
    conf = Config()
    init_logging(conf.LOGGING_CONFIG)
    
    logger = logging.getLogger(__name__)

    # Initialize MongoDB
    mongodb = init_mongodb(
        conf.MONGODB_URI,
        conf.MONGODB_DB_NAME,
        conf.DB_RETENTION_MIN
    )
    app.state.mongodb = mongodb
    app_state.mongodb = mongodb

    # Store app state
    app.state.config = conf
    app.state.metaInfo = MetaInformation()

    from .core.utils.modes_util import ModesUtil
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
        logger.info("Application shutdown initiated")

    return app

from typing import Annotated
from fastapi import Depends
from pymongo.database import Database

from ..data.repositories.aircraft_repository import AircraftRepository
from ..core.utils.modes_util import ModesUtil
from ..config import Config, app_state
from ..meta import MetaInformation

def get_mongodb() -> Database:
    """Get MongoDB database connection"""
    return app_state.mongodb

MongoDBDep = Annotated[Database, Depends(get_mongodb)]

def get_config() -> Config:
    """Get application configuration"""
    from ..config import Config
    return Config()

def get_modes_util() -> ModesUtil:
    """Get ModesUtil instance"""
    from ..config import Config
    return ModesUtil(get_config().DATA_FOLDER)

def get_meta_info() -> MetaInformation:
    """Get MetaInformation instance"""
    return MetaInformation()

def get_aircraft_repository(mongodb: MongoDBDep) -> AircraftRepository:
    """Get AircraftRepository instance"""
    return AircraftRepository(mongodb)

ConfigDep = Annotated[Config, Depends(get_config)]
ModesUtilDep = Annotated[ModesUtil, Depends(get_modes_util)]
MetaInfoDep = Annotated[MetaInformation, Depends(get_meta_info)]
AircraftRepositoryDep = Annotated[AircraftRepository, Depends(get_aircraft_repository)]


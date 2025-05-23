from typing import Any
from abc import ABC, abstractmethod

from .mongodb_init import init_mongodb
from .mongodb_repository import MongoDBRepository


class DatabaseFactory:
    """Factory class to create database repositories based on configuration"""
    
    @staticmethod
    def create_repository(config) -> 'DatabaseRepository':
        """Create a database repository based on configuration"""
        # For now, only MongoDB is supported, but this can be extended
        db_type = getattr(config, 'DB_TYPE', 'mongodb').lower()
        
        if db_type == 'mongodb':
            # Initialize MongoDB
            retention_minutes = getattr(config, 'DB_RETENTION_MIN', 0)
            use_ttl_indexes = retention_minutes > 0
            
            mongodb = init_mongodb(
                config.MONGODB_URI,
                config.MONGODB_DB_NAME,
                retention_minutes if use_ttl_indexes else None
            )
            
            return MongoDBDatabaseRepository(MongoDBRepository(mongodb))
        else:
            raise ValueError(f"Unsupported database type: {db_type}")


class DatabaseRepository(ABC):
    """Abstract base class for database repositories"""
    
    @abstractmethod
    def initialize(self, config) -> None:
        """Initialize the database repository with configuration"""
        pass
    
    @abstractmethod
    def get_underlying_repository(self) -> Any:
        """Get the underlying database-specific repository"""
        pass


class MongoDBDatabaseRepository(DatabaseRepository):
    """MongoDB implementation of DatabaseRepository"""
    
    def __init__(self, mongodb_repo: MongoDBRepository):
        self._mongodb_repo = mongodb_repo
    
    def initialize(self, config) -> None:
        """Initialize MongoDB repository (already done in factory)"""
        pass
    
    def get_underlying_repository(self) -> MongoDBRepository:
        """Get the underlying MongoDB repository"""
        return self._mongodb_repo
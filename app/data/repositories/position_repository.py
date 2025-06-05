import logging
from typing import List, Dict, Tuple, Any
from datetime import datetime
from .mongodb_repository import MongoDBRepository

logger = logging.getLogger('PositionRepository')

class PositionRepository:
    def __init__(self, db_repo: MongoDBRepository) -> None:
        self.db_repo = db_repo
        
    def insert_positions(self, positions: List[Dict[str, Any]]) -> None:
        """Insert positions into the database"""
        return self.db_repo.insert_positions(positions)
        
    def bulk_update_flight_last_contacts(self, updates: List[Tuple[str, datetime]]) -> None:
        """Update last contact times for multiple flights"""
        return self.db_repo.bulk_update_flight_last_contacts(updates)
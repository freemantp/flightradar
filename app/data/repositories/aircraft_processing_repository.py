import logging
from typing import List
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


class AircraftProcessingRepository:
    """Simple repository for managing aircraft that need metadata processing"""

    def __init__(self, mongodb: Database):
        self.db = mongodb
        self.collection_name = "aircraft_to_process"
        
        # Create collection and indexes if needed
        if self.collection_name not in self.db.list_collection_names():
            self.db.create_collection(self.collection_name)
            
        collection = self.db[self.collection_name]
        collection.create_index("modeS", unique=True)
        collection.create_index("query_attempts")

    def add_aircraft(self, icao24: str) -> bool:
        """Add aircraft to processing queue"""
        try:
            self.db[self.collection_name].insert_one({
                "modeS": icao24.upper(),
                "query_attempts": 0,
                "sources_queried": []
            })
            return True
        except PyMongoError as e:
            if e.code == 11000:  # Duplicate key error - aircraft already exists
                return True
            logger.error(f"Failed to add aircraft {icao24}: {e}")
            return False

    def get_aircraft_for_processing(self, limit: int = 50) -> List[str]:
        """Get aircraft with less than 3 attempts"""
        try:
            cursor = self.db[self.collection_name].find(
                {"query_attempts": {"$lt": 3}}
            ).sort([
                ("query_attempts", 1),
                ("_id", 1)
            ]).limit(limit)
            
            return [doc["modeS"] for doc in cursor]
        except PyMongoError as e:
            logger.error(f"Failed to get aircraft for processing: {e}")
            return []

    def increment_attempts(self, icao24: str) -> bool:
        """Increment query attempts for an aircraft"""
        try:
            result = self.db[self.collection_name].update_one(
                {"modeS": icao24.upper()},
                {"$inc": {"query_attempts": 1}}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to increment attempts for {icao24}: {e}")
            return False

    def remove_aircraft(self, icao24: str) -> bool:
        """Remove aircraft from processing queue (successfully processed)"""
        try:
            result = self.db[self.collection_name].delete_one({"modeS": icao24.upper()})
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to remove aircraft {icao24}: {e}")
            return False

    def aircraft_exists(self, icao24: str) -> bool:
        """Check if aircraft exists in processing queue"""
        try:
            result = self.db[self.collection_name].find_one(
                {"modeS": icao24.upper()}, 
                {"_id": 1}
            )
            return result is not None
        except PyMongoError as e:
            logger.error(f"Failed to check if aircraft {icao24} exists: {e}")
            return False

    def cleanup_failed_aircraft(self) -> int:
        """Remove aircraft that have reached max attempts (3)"""
        try:
            result = self.db[self.collection_name].delete_many({
                "query_attempts": {"$gte": 3}
            })
            
            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} aircraft with max attempts")
                
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Failed to cleanup failed aircraft: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get simple statistics"""
        try:
            total = self.db[self.collection_name].count_documents({})
            zero_attempts = self.db[self.collection_name].count_documents({"query_attempts": 0})
            
            return {
                "total_count": total,
                "zero_attempts": zero_attempts,
                "in_progress": total - zero_attempts
            }
        except PyMongoError as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total_count": 0, "zero_attempts": 0, "in_progress": 0}
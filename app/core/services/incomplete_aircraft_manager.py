import logging
from datetime import datetime, timedelta
from typing import Set, List
from ...data.repositories.aircraft_repository import AircraftRepository
from ...data.repositories.aircraft_processing_repository import AircraftProcessingRepository

logger = logging.getLogger("IncompleteAircraftManager")


class IncompleteAircraftManager:
    """
    Manages all aspects of incomplete/unknown aircraft processing:
    1. Aircraft not present in aircraft collection
    2. Aircraft with lastModified date older than 4 months
    3. Aircraft with missing critical fields (operator, type, registration)
    4. Repository initialization and configuration
    """

    def __init__(self, config, mongodb=None):
        """Initialize manager with database connections"""
        from ...data.repositories.aircraft_repository import AircraftRepository
        
        self.aircraft_repo = AircraftRepository(mongodb)
        self.processing_aircraft_repo = AircraftProcessingRepository(mongodb)

    @classmethod
    def create_with_repositories(cls, aircraft_repo: AircraftRepository, processing_aircraft_repo: AircraftProcessingRepository):
        """Create manager with existing repositories (for testing)"""
        instance = cls.__new__(cls)
        instance.aircraft_repo = aircraft_repo
        instance.processing_aircraft_repo = processing_aircraft_repo
        return instance

    def schedule_aircraft_for_processing(self, icao24s: Set[str]) -> None:
        """
        Process a batch of aircraft and schedule them for metadata processing if they meet criteria.
        
        Args:
            icao24s: Set of ICAO24 addresses to process
        """
        if not icao24s:
            return

        aircraft_to_process = self._classify_unknown_aircraft(icao24s)
        
        if aircraft_to_process:
            # Only add aircraft that don't already exist in unknown collection
            new_unknown_aircraft = [
                icao24 for icao24 in aircraft_to_process 
                if not self.processing_aircraft_repo.aircraft_exists(icao24)
            ]
            
            if new_unknown_aircraft:
                logger.info(f"Adding {len(new_unknown_aircraft)} new aircraft (found {len(aircraft_to_process)} total requiring metadata)")
                for icao24 in new_unknown_aircraft:
                    self.processing_aircraft_repo.add_aircraft(icao24)
            else:
                logger.debug(f"All {len(aircraft_to_process)} aircraft requiring metadata already exist in unknown collection")

    def _classify_unknown_aircraft(self, icao24s: Set[str]) -> List[str]:
        """
        Classify aircraft as unknown based on the three criteria
        
        Args:
            icao24s: Set of ICAO24 addresses to classify
            
        Returns:
            List of ICAO24 addresses that are classified as unknown
        """
        aircraft_to_process = []
        four_months_ago = datetime.now() - timedelta(days=120)

        for icao24 in icao24s:
            try:
                existing_aircraft = self.aircraft_repo.query_aircraft(icao24)
                
                if existing_aircraft is None:
                    # Criteria 1: Aircraft not present in aircraft collection
                    logger.debug(f"Aircraft {icao24} not found in database")
                    aircraft_to_process.append(icao24)
                    continue

                aircraft_doc = self.aircraft_repo.db[self.aircraft_repo.collection_name].find_one(
                    {"modeS": icao24.strip().upper()}
                )

                if aircraft_doc:
                    last_modified = aircraft_doc.get("lastModified")
                    if last_modified and last_modified >= four_months_ago:
                        if not self._has_missing_critical_fields(aircraft_doc):
                            logger.debug(f"Aircraft {icao24} is up-to-date and complete, skipping")
                            continue
                    
                    # Criteria 2: Aircraft with lastModified date older than 4 months
                    if last_modified is None or last_modified < four_months_ago:
                        logger.debug(f"Aircraft {icao24} is stale (lastModified: {last_modified})")
                        aircraft_to_process.append(icao24)
                        continue

                    # Criteria 3: Aircraft with missing critical fields
                    if self._has_missing_critical_fields(aircraft_doc):
                        logger.debug(f"Aircraft {icao24} has missing critical fields")
                        aircraft_to_process.append(icao24)

            except Exception as e:
                logger.warning(f"Error classifying aircraft {icao24}: {e}")
                aircraft_to_process.append(icao24)

        return aircraft_to_process

    def _has_missing_critical_fields(self, aircraft_doc: dict) -> bool:
        """
        Check if aircraft has missing critical fields
        
        Args:
            aircraft_doc: Aircraft document from database
            
        Returns:
            True if aircraft has missing critical fields, False otherwise
        """
        critical_fields = ["registeredOwners", "type", "icaoTypeCode", "registration"]
        
        for field in critical_fields:
            value = aircraft_doc.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                return True
                
        return False

    def get_stats(self) -> dict:
        """Get statistics about aircraft processing"""
        return self.processing_aircraft_repo.get_stats()
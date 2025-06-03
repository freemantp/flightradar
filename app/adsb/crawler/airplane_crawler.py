from app.adsb.datasource.openskynet import OpenskyNet
from ..datasource.hexdb_io import HexdbIo
from ..datasource.aircraft_metadata_source import AircraftMetadataSource
from ..aircraft import Aircraft
from ..db.aircraft_repository import AircraftRepository
from ..db.aircraft_processing_repository import AircraftProcessingRepository
from ..util.logging import init_logging

import logging
from typing import List, Optional

logger = logging.getLogger("Crawler")


class AirplaneCrawler:
    """Aircraft metadata crawler for retrieving and updating aircraft information"""

    def __init__(self, config) -> None:
        init_logging(config.LOGGING_CONFIG)
        
        from ..db.database_factory import DatabaseFactory
        db_repository = DatabaseFactory.create_repository(config)
        db_repo = db_repository.get_underlying_repository()
        
        self.aircraft_repo = AircraftRepository(db_repo.db)
        self.processing_repo = AircraftProcessingRepository(db_repo.db)
        
        self.sources: List[AircraftMetadataSource] = [
            HexdbIo(),
            OpenskyNet(),
        ]

    def _query_aircraft_metadata(self, icao24: str) -> Optional[Aircraft]:
        """Query metadata sources for aircraft information"""
        
        for source in self.sources:
            if not source.accept(icao24):
                continue
                
            try:
                aircraft = source.query_aircraft(icao24)
                
                if aircraft:
                    logger.info(f'Updated {icao24} from {source.name()}')
                    return aircraft
                else:
                    logger.debug(f'No data found for {icao24} from {source.name()}')
                    
            except Exception as e:
                logger.warning(f'Error from {source.name()} for {icao24}: {e}')
                    
        return None

    def crawl_sources(self) -> None:
        """Process aircraft from the collection that need metadata"""
        
        try:
            aircraft_to_process = self.processing_repo.get_aircraft_for_processing(limit=50)
            
            if not aircraft_to_process:
                logger.debug("No aircraft to process")
                return
            
            logger.info(f"Processing {len(aircraft_to_process)} aircraft")
            
            for icao24 in aircraft_to_process:
                try:
                    aircraft_metadata = self._query_aircraft_metadata(icao24)
                    
                    if aircraft_metadata:
                        if self.aircraft_repo.insert_aircraft(aircraft_metadata):
                            self.processing_repo.remove_aircraft(icao24)
                            logger.info(f"Successfully processed aircraft: {icao24}")
                        else:
                            logger.warning(f"Failed to insert aircraft {icao24} to database")
                            self.processing_repo.increment_attempts(icao24)
                    else:
                        self.processing_repo.increment_attempts(icao24)
                        logger.debug(f"No metadata found for {icao24}, incremented attempts")
                        
                except Exception as e:
                    logger.warning(f"Error processing aircraft {icao24}: {e}")
                    self.processing_repo.increment_attempts(icao24)
                    
        except Exception as e:
            logger.exception(f"Error in crawl_sources: {e}")
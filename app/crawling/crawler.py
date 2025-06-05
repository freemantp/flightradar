from ..data.sources.metadata_sources.openskynet import OpenskyNet
from ..data.sources.metadata_sources.hexdb_io import HexdbIo
from ..data.sources.metadata_sources import AircraftMetadataSource
from ..core.models.aircraft import Aircraft
from ..data.repositories.aircraft_repository import AircraftRepository
from ..data.repositories.aircraft_processing_repository import AircraftProcessingRepository
from ..core.utils.logging import init_logging

import logging
from typing import List, Optional

logger = logging.getLogger("Crawler")


class AirplaneCrawler:
    """Aircraft metadata crawler for retrieving and updating aircraft information"""

    def __init__(self, config, mongodb=None) -> None:
        init_logging(config.LOGGING_CONFIG)
        
        self.aircraft_repo = AircraftRepository(mongodb)
        self.processing_repo = AircraftProcessingRepository(mongodb)
        
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
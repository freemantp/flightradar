from app.adsb.datasource.flightradar24 import Flightradar24
from app.adsb.datasource.openskynet import OpenskyNet
from ..datasource.hexdb_io import HexdbIo
from ..datasource.aircraft_metadata_source import AircraftMetadataSource
from .util.source_backoff import SourceBackoff
from .util.crawler_exceptions import RetryableSourceException, NonRetryableSourceException
from .util.aircraft_cache import AircraftCache
from .util.crawl_item import CrawlItem
from .shared_aircraft_queue import shared_aircraft_queue
from ..aircraft import Aircraft
from ..db.aircraft_repository import AircraftRepository
from ..util.logging import init_logging
from ...config import app_state

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import List, Optional, Set, Deque, Dict
from requests.exceptions import HTTPError
import requests

logger = logging.getLogger("Crawler")


class AirplaneCrawler:
    """Main aircraft metadata crawler with queue-based processing and intelligent backoff."""

    def __init__(self, config) -> None:
        init_logging(config.LOGGING_CONFIG)
        
        self.aircraft_repo = AircraftRepository(app_state.mongodb)
        assert self.aircraft_repo

        self.sources: List[AircraftMetadataSource] = [
            HexdbIo(),
            OpenskyNet(),
            Flightradar24(),
            # BazlLFR(), 
            # SecretBasesUk(config.DATA_FOLDER),
            # MilitaryModeS(config.DATA_FOLDER)
        ]
        
        self._crawl_queue: Deque[CrawlItem] = deque()
        self._known_aircraft: Set[str] = set()  # Track aircraft we've seen before
        self._max_retries = 5  # Maximum retry attempts per aircraft
        
        self._source_backoffs: Dict[str, SourceBackoff] = {
            source.name(): SourceBackoff() for source in self.sources
        }
        
        self._processed_aircraft = AircraftCache(max_size=1000)

    def _is_aircraft_fresh(self, icao24: str) -> bool:
        """Check if aircraft metadata is less than 3 months old"""
        try:
            result = self.aircraft_repo.db[self.aircraft_repo.collection_name].find_one(
                {"modeS": icao24.strip().upper()}, 
                {"lastModified": 1}
            )
            
            if result and "lastModified" in result:
                last_modified = result["lastModified"]
                three_months_ago = datetime.now() - timedelta(days=90)
                return last_modified > three_months_ago
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking aircraft freshness for {icao24}: {e}")
            return False

    def _classify_exception(self, exception: Exception) -> Exception:
        """Classify exceptions to determine if they should trigger backoff"""
        if isinstance(exception, HTTPError):
            if hasattr(exception, 'response') and exception.response is not None:
                status_code = exception.response.status_code
                if status_code == requests.codes.not_found:  # 404
                    return NonRetryableSourceException(f"Aircraft not found (404): {exception}")
                elif status_code == requests.codes.too_many:  # 429
                    return RetryableSourceException(f"Rate limited (429): {exception}")
                elif 500 <= status_code < 600: 
                    return RetryableSourceException(f"Server error ({status_code}): {exception}")
                else:
                    return NonRetryableSourceException(f"HTTP error ({status_code}): {exception}")
        
        return RetryableSourceException(f"Network/connection error: {exception}")

    def _can_query_source(self, source: AircraftMetadataSource) -> bool:
        """Check if a source can be queried now (respects backoff)"""
        backoff = self._source_backoffs[source.name()]
        return backoff.can_retry_now()

    def _record_source_failure(self, source: AircraftMetadataSource) -> None:
        """Record a failure for a specific source"""
        backoff = self._source_backoffs[source.name()]
        backoff.record_failure()
        logger.warning(f"Source {source.name()} failed, backoff for {min(2 ** backoff.retry_count, 300)} seconds")

    def _record_source_success(self, source: AircraftMetadataSource) -> None:
        """Record a success for a specific source (resets backoff)"""
        backoff = self._source_backoffs[source.name()]
        if backoff.retry_count > 0:
            logger.info(f"Source {source.name()} recovered, resetting backoff")
        backoff.reset()

    def _query_aircraft_metadata(self, icao24: str) -> Optional[Aircraft]:
        """Query metadata sources for aircraft information with per-source backoff"""
        
        for source in self.sources:
            if not source.accept(icao24):
                continue
                
            if not self._can_query_source(source):
                logger.debug(f"Skipping {source.name()} for {icao24} (in backoff)")
                continue
                
            try:
                aircraft = source.query_aircraft(icao24)
                
                if aircraft:
                    self._record_source_success(source)
                    logger.info(f'Updated {icao24} from {source.name()}')
                    return aircraft
                else:
                    logger.debug(f'No data found for {icao24} from {source.name()}')
                    
            except Exception as e:
                classified_exception = self._classify_exception(e)
                
                if isinstance(classified_exception, RetryableSourceException):
                    logger.warning(f'Retryable error from {source.name()} for {icao24}: {classified_exception}')
                    self._record_source_failure(source)
                else:
                    logger.debug(f'Non-retryable error from {source.name()} for {icao24}: {classified_exception}')
                    
        return None

    def _process_crawl_item(self, item: CrawlItem) -> bool:
        """
        Process a single crawl item
        
        Returns:
            True if successful (aircraft found and inserted or already exists)
            False if no sources were available to query (all in backoff)
        """
        try:
            if self._processed_aircraft.contains(item.icao24):
                logger.debug(f"Aircraft {item.icao24} recently processed, skipping")
                return True
                
            existing_aircraft = self.aircraft_repo.query_aircraft(item.icao24)
            
            if existing_aircraft is not None and self._is_aircraft_fresh(item.icao24):
                logger.debug(f"Aircraft {item.icao24} already exists and is fresh")
                self._processed_aircraft.add(item.icao24)
                return True
            elif existing_aircraft is not None:
                logger.debug(f"Aircraft {item.icao24} exists but is stale (>3 months), refreshing")
                
            available_sources = [s for s in self.sources if s.accept(item.icao24) and self._can_query_source(s)]
            
            if not available_sources:
                logger.debug(f"No sources available for {item.icao24} (all in backoff)")
                return False 
            
            aircraft_metadata = self._query_aircraft_metadata(item.icao24)
            
            if aircraft_metadata:
                if self.aircraft_repo.insert_aircraft(aircraft_metadata):
                    self._processed_aircraft.add(item.icao24)
                    if existing_aircraft is not None:
                        logger.info(f"Successfully updated stale aircraft: {item.icao24}")
                    else:
                        logger.info(f"Successfully inserted new aircraft: {item.icao24}")
                    return True
                else:
                    logger.warning(f"Failed to insert/update aircraft in database: {item.icao24}")
                    return False
            else:
                sources_tried = [s.name() for s in available_sources]
                logger.warning(f"Metadata query failed for aircraft {item.icao24}. Sources tried: {', '.join(sources_tried)}")
                
                # Store as unknown aircraft in MongoDB
                try:
                    self.aircraft_repo.db["UnknownAircraft"].find_one_and_update(
                        {"modeS": item.icao24.upper()},
                        {
                            "$set": {"last_seen": datetime.now()},
                            "$inc": {"query_attempts": 1},
                            "$addToSet": {"sources_queried": {"$each": sources_tried}},
                            "$setOnInsert": {"first_seen": datetime.now()}
                        },
                        upsert=True
                    )
                    logger.info(f"Updated unknown aircraft record: {item.icao24}")
                except Exception as e:
                    logger.warning(f"Failed to store unknown aircraft {item.icao24}: {e}")
                
                self._processed_aircraft.add(item.icao24)
                return True
                
        except Exception as e:
            logger.warning(f"Error processing aircraft {item.icao24}: {e}")
            return False

    def _add_to_queue(self, icao24: str) -> None:
        """Add aircraft to crawl queue if not already known"""
        if icao24 not in self._known_aircraft:
            self._crawl_queue.append(CrawlItem(icao24=icao24))
            self._known_aircraft.add(icao24)
            logger.debug(f"Added {icao24} to crawl queue")

    def _process_queue(self) -> None:
        """Process items in the crawl queue (max 100 items per run)"""
        processed_count = 0
        max_items_per_run = 100
        
        retry_items = []
        
        while self._crawl_queue and processed_count < max_items_per_run:
            item = self._crawl_queue.popleft()
            
            success = self._process_crawl_item(item)
            
            if not success:
                retry_items.append(item)
                    
            processed_count += 1
            
        for item in retry_items:
            self._crawl_queue.append(item)

    def crawl_sources(self) -> None:
        """Crawl sources for new aircraft metadata using shared queue and LRU cache filtering"""
        
        try:
            new_aircraft = shared_aircraft_queue.get_aircraft(max_items=100)
            
            if not new_aircraft:
                logger.debug("No new aircraft in shared queue, processing existing local queue")
                self._process_queue()
                return
            
            logger.debug(f"Retrieved {len(new_aircraft)} aircraft from shared queue")
            
            # Filter out aircraft that are already in our processed cache
            filtered_aircraft = {
                icao24 for icao24 in new_aircraft 
                if not self._processed_aircraft.contains(icao24)
            }
            
            logger.debug(f"After cache filtering: {len(filtered_aircraft)} aircraft to process")
            
            # Add filtered aircraft to our local processing queue
            new_aircraft_count = 0
            for icao24 in filtered_aircraft:
                if icao24 not in self._known_aircraft:
                    self._add_to_queue(icao24)
                    new_aircraft_count += 1
                    
            if new_aircraft_count > 0:
                logger.info(f"Added {new_aircraft_count} new aircraft to processing queue")
                
            logger.debug(f"Local queue size: {len(self._crawl_queue)} items")
            logger.debug(f"Processed aircraft cache size: {self._processed_aircraft.size()}")
            logger.debug(f"Shared queue size: {shared_aircraft_queue.size()} items")
            
            backed_off_sources = [name for name, backoff in self._source_backoffs.items() if backoff.retry_count > 0]
            if backed_off_sources:
                logger.debug(f"Sources in backoff: {backed_off_sources}")
            
            self._process_queue()
                    
        except Exception as e:
            logger.exception(f"Error in crawl_sources: {e}")
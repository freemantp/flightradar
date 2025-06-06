from datetime import datetime
import logging
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from ...core.models.aircraft import Aircraft

logger = logging.getLogger(__name__)

class AircraftRepository:
    """ MongoDB implementation of Aircraft Repository """

    def __init__(self, mongodb: Database):
        self.db = mongodb
        self.collection_name = "aircraft"
        self._designators_cache = {}
        self._cache_loaded = False
        
        # Ensure collection exists and has necessary indexes
        if self.collection_name not in self.db.list_collection_names():
            self.db.create_collection(self.collection_name)
            self.db[self.collection_name].create_index("modeS", unique=True)
    
    def _load_icao_designators(self):
        """Load ICAO type designators into cache"""
        if self._cache_loaded:
            return
            
        try:
            designators_collection = self.db["icao_type_designators"]
            for doc in designators_collection.find({}, {"icaoTypeCode": 1, "icaoTypeDesignator": 1}):
                self._designators_cache[doc["icaoTypeCode"]] = doc["icaoTypeDesignator"]
            
            self._cache_loaded = True
            logger.debug(f"Loaded {len(self._designators_cache)} ICAO type designators into cache")
            
        except Exception as e:
            logger.warning(f"Failed to load ICAO designators: {e}")
    
    def _get_icao_designator(self, icao_type_code):
        """Get ICAO type designator for given type code"""
        if not icao_type_code:
            return None
            
        self._load_icao_designators()
        return self._designators_cache.get(icao_type_code)
    
    def query_aircraft(self, icao24addr):
        """Query aircraft information by ICAO24 address"""
        result = self.db[self.collection_name].find_one({"modeS": icao24addr.strip().upper()})
        
        if result:
            return Aircraft(
                result["modeS"],
                reg=result.get("registration"),
                icao_type_code=result.get("icaoTypeCode"),
                aircraft_type_description=result.get("type"),
                operator=result.get("registeredOwners"),
                source=result.get("source"),
                icao_type_designator=result.get("icaoTypeDesignator")
            )
        else:
            return None
    
    def _build_update_dict(self, aircraft):
        """Build update dictionary with ICAO designator if available"""
        base_fields = {"lastModified": datetime.now()}
        
        if aircraft.is_complete_with_operator():
            update_dict = {
                "registration": aircraft.reg,
                "icaoTypeCode": aircraft.icao_type_code,
                "type": aircraft.aircraft_type_description,
                "registeredOwners": aircraft.operator,
                "source": aircraft.source,
                **base_fields
            }
        elif aircraft.is_complete():
            update_dict = {
                "registration": aircraft.reg,
                "icaoTypeCode": aircraft.icao_type_code,
                "type": aircraft.aircraft_type_description,
                "source": aircraft.source,
                **base_fields
            }
        elif aircraft.reg:
            update_dict = {
                "registration": aircraft.reg,
                "source": aircraft.source,
                **base_fields
            }
        else:
            return {}
        
        # Add ICAO designator if type code is present
        if aircraft.icao_type_code:
            icao_designator = self._get_icao_designator(aircraft.icao_type_code)
            if icao_designator:
                update_dict["icaoTypeDesignator"] = icao_designator
        
        return update_dict

    def update_aircraft(self, aircraft):
        """Update existing aircraft information"""
        try:
            update_dict = self._build_update_dict(aircraft)
            
            if not update_dict:
                return False
                
            result = self.db[self.collection_name].update_one(
                {"modeS": aircraft.modes_hex},
                {"$set": update_dict}
            )
            return result.modified_count > 0
            
        except PyMongoError as e:
            logger.exception(e)
            logger.error(f'Could not update aircraft: {str(aircraft)}')
            return False
    
    def insert_aircraft(self, acrft):
        """Insert new aircraft into database"""
        if acrft:
            try:
                timestamp = datetime.now()
                
                aircraft_doc = {
                    "modeS": acrft.modes_hex,
                    "firstCreated": timestamp,
                    "lastModified": timestamp,
                    "registration": acrft.reg,
                    "icaoTypeCode": acrft.icao_type_code,
                    "type": acrft.aircraft_type_description,
                    "registeredOwners": acrft.operator,
                    "source": acrft.source,
                    "country": "",
                    "manufacturer": ""
                }
                
                # Add ICAO designator if available
                icao_designator = self._get_icao_designator(acrft.icao_type_code)
                if icao_designator:
                    aircraft_doc["icaoTypeDesignator"] = icao_designator
                
                result = self.db[self.collection_name].insert_one(aircraft_doc)
                return result.acknowledged
                
            except DuplicateKeyError:
                return self.update_aircraft(acrft)
            except PyMongoError as e:
                logger.exception(e)
                logger.error(f'Could not insert aircraft: {str(acrft)}')
        
        return False
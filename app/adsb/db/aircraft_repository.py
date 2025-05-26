from datetime import datetime
import logging
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..aircraft import Aircraft

logger = logging.getLogger(__name__)

class AircraftRepository:
    """ MongoDB implementation of Aircraft Repository """

    def __init__(self, mongodb: Database):
        self.db = mongodb
        self.collection_name = "aircraft"
        
        # Ensure collection exists and has necessary indexes
        if self.collection_name not in self.db.list_collection_names():
            self.db.create_collection(self.collection_name)
            self.db[self.collection_name].create_index("modeS", unique=True)
    
    def query_aircraft(self, icao24addr):
        """Query aircraft information by ICAO24 address"""
        result = self.db[self.collection_name].find_one({"modeS": icao24addr.strip().upper()})
        
        if result:
            return Aircraft(
                result["modeS"],
                result.get("registration"),
                result.get("icaoTypeCode"),
                result.get("type"),
                result.get("registeredOwners")
            )
        else:
            return None
    
    def update_aircraft(self, aircraft):
        """Update existing aircraft information"""
        try:
            update_dict = {}
            
            # Keep the update logic focused on the fields that can be updated
            # based on the Aircraft object's capabilities
            if aircraft.is_complete2():
                update_dict = {
                    "registration": aircraft.reg,
                    "icaoTypeCode": aircraft.type1,
                    "type": aircraft.type2,
                    "registeredOwners": aircraft.operator,
                    "lastModified": datetime.now()
                }
            elif aircraft.is_complete():
                update_dict = {
                    "registration": aircraft.reg,
                    "icaoTypeCode": aircraft.type1,
                    "type": aircraft.type2,
                    "lastModified": datetime.now()
                }
            elif aircraft.reg:
                update_dict = {
                    "registration": aircraft.reg,
                    "lastModified": datetime.now()
                }
            
            if update_dict:
                result = self.db[self.collection_name].update_one(
                    {"modeS": aircraft.modes_hex},
                    {"$set": update_dict}
                )
                return result.modified_count > 0
            
            return False
            
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
                    "icaoTypeCode": acrft.type1,
                    "type": acrft.type2,
                    "registeredOwners": acrft.operator,
                    # Initialize the new fields with empty values
                    "modesCountry": "",
                    "country": "",
                    "manufacturer": "",
                    "serialNo": "",
                    "engines": "",
                    "icaoDescription": ""
                }
                
                result = self.db[self.collection_name].insert_one(aircraft_doc)
                return result.acknowledged
                
            except DuplicateKeyError:
                return self.update_aircraft(acrft)
            except PyMongoError as e:
                logger.exception(e)
                logger.error(f'Could not insert aircraft: {str(acrft)}')
        
        return False
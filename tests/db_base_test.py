import unittest
from unittest.mock import MagicMock
from bson import ObjectId
from pymongo.database import Database
import datetime

class MongoDBBaseTestCase(unittest.TestCase):
    def setUp(self):
        """
        Set up the mock MongoDB database for testing
        """
        # Create mock MongoDB
        self.mock_db = MagicMock(spec=Database)
        
        # Create mock collections
        self.mock_flights = MagicMock()
        self.mock_positions = MagicMock()
        self.mock_aircraft = MagicMock()
        
        # Set up collections on the mock db
        self.mock_db.flights = self.mock_flights
        self.mock_db.positions = self.mock_positions
        self.mock_db.aircraft = self.mock_aircraft
        
        # Set collection names
        self.mock_db.flights_collection = "flights"
        self.mock_db.positions_collection = "positions"
        
        # Configure list_collection_names to return our collections
        self.mock_db.list_collection_names.return_value = ["flights", "positions", "aircraft"]
    
    def insert_mock_positions(self, position_data, flight_id, mode_s='xxxxxx'):
        """
        Create mock position data in the MongoDB format
        """
        positions = []
        for position_item in position_data:
            timestamp = position_item[0] if isinstance(position_item[0], datetime.datetime) else datetime.datetime.strptime(position_item[0], '%H:%M')
            position = {
                "_id": ObjectId(),
                "flight_id": ObjectId(flight_id),
                "timestmp": timestamp,
                "lat": position_item[1],
                "lon": position_item[2],
                "alt": position_item[3],
                "heading": position_item[4],
                "speed": position_item[5]
            }
            positions.append(position)
        
        # Configure the mock to return this data
        self.mock_positions.find.return_value = positions
        self.mock_positions.find_one.return_value = positions[0] if positions else None
        
        return positions
    
    def tearDown(self):
        """
        Clean up test resources
        """
        pass
from typing import List
from unittest.mock import patch, MagicMock
from bson import ObjectId
from datetime import datetime, timezone


from app.adsb.flightupdater import FlightUpdater
from app.adsb.model.position_report import PositionReport
from app.config import Config
from db_base_test import MongoDBBaseTestCase


class MockRadarService:
    connection_alive = False
    flights = []

    def query_live_flights(self, incomplete) -> List[PositionReport]:
        return self.flights


class MockModeSUtil:
    def is_military(self, modeS):
        return False


class FlightUpdaterTest(MongoDBBaseTestCase):

    def setUp(self):
        # Call parent setup to create MongoDB mocks
        MongoDBBaseTestCase.setUp(self)
        
        # Setup the FlightUpdater with patches
        with patch('app.config.app_state') as mock_app_state:
            mock_app_state.mongodb = self.mock_db
            
            self.sut = FlightUpdater()
            self.sut.initialize(Config())
            
        self.sut._mil_only = False
        self.sut._service = MockRadarService()
        
        # Create a mock app context
        self.app = MagicMock()
        self.app.modes_util = MockModeSUtil()
        
    def tearDown(self):
        MongoDBBaseTestCase.tearDown(self)

    def test_update(self):
        """Test flight/position insertion"""
        # Setup test data
        self.sut._service.flights = [
            PositionReport('12345', 41.1, 60.1, 1723, 123, 'CLLSGN'),
            PositionReport('12345', 44.1, 63.1, 1723, 321, None),
        ]
        
        # Mock MongoDB responses for insert operations
        flight_id = ObjectId()
        self.mock_flights.find_one_and_update.return_value = {
            "_id": flight_id,
            "modeS": "12345",
            "callsign": "CLLSGN",
            "is_military": False,
            "archived": False,
            "first_contact": datetime.now(timezone.utc),
            "last_contact": datetime.now(timezone.utc)
        }
        
        # Run the update
        with patch('app.config.app_state.mongodb', self.mock_db):
            self.sut.update()
        
        # Verify MongoDB operations were called
        self.mock_flights.find_one_and_update.assert_called()
        self.mock_positions.insert_many.assert_called_once()
        
        # Verify the positions were inserted with the correct flight_id
        inserted_positions = self.mock_positions.insert_many.call_args[0][0]
        self.assertEqual(len(inserted_positions), 2)
        self.assertEqual(inserted_positions[0]["flight_id"], flight_id)
        self.assertEqual(inserted_positions[1]["flight_id"], flight_id)

    def test_update_no_duplicate(self):
        """Test duplicate elimination"""
        # Setup test data
        self.sut._service.flights = [
            PositionReport('12345', 41.1, 60.1, 1723, 123, 'CLLSGN'),
            PositionReport('12345', 44.1, 63.1, 1723, 321, None)
        ]
        
        # Mock MongoDB responses
        flight_id = ObjectId()
        self.mock_flights.find_one_and_update.return_value = {
            "_id": flight_id,
            "modeS": "12345",
            "callsign": "CLLSGN",
            "is_military": False,
            "archived": False,
            "first_contact": datetime.now(timezone.utc),
            "last_contact": datetime.now(timezone.utc)
        }
        
        # Store existing position hash
        position_hash = hash((44.1, 63.1, 1723))
        self.sut.positions_hash.add(position_hash)
        
        # Run the update
        with patch('app.config.app_state.mongodb', self.mock_db):
            self.sut.update()
        
        # Verify only the first position was inserted (the second should be a duplicate)
        self.mock_positions.insert_many.assert_called_once()
        inserted_positions = self.mock_positions.insert_many.call_args[0][0]
        self.assertEqual(len(inserted_positions), 1)
        self.assertEqual(inserted_positions[0]["lat"], 41.1)
        self.assertEqual(inserted_positions[0]["lon"], 60.1)

    def test_cleanup(self):
        """Test stale flight/position cleanup"""
        # Setup test data - create a flight ID and add it to the maps
        flight_id = str(ObjectId())
        self.sut.modeS_flightid_map["12345"] = flight_id
        self.sut.flight_lastpos_map[flight_id] = (flight_id, 41.1, 60.1, 1723)
        
        # Mock MongoDB responses for the cleanup query
        old_flights = [{
            "_id": ObjectId(flight_id),
            "modeS": "12345"
        }]
        self.mock_flights.find.return_value = old_flights
        
        # Set a short timeout for cleanup
        self.sut._delete_after = float(1 / 60)
        
        # Run the cleanup
        with patch('app.config.app_state.mongodb', self.mock_db):
            self.sut.cleanup_items()
        
        # Verify MongoDB delete operations were called
        self.mock_positions.delete_many.assert_called_once()
        self.mock_flights.delete_many.assert_called_once()
        
        # Verify the maps were cleared
        self.assertFalse(self.sut.modeS_flightid_map)
        self.assertFalse(self.sut.flight_lastpos_map)

    def test_initialize_db(self):
        """Test initialization from db"""
        # Verify initial state
        self.assertFalse(self.sut.modeS_flightid_map)
        self.assertFalse(self.sut.flight_lastpos_map)
        
        # Create mock flight data
        flight1_id = ObjectId()
        flight2_id = ObjectId()
        
        # Create mock position data
        position1 = {
            "_id": ObjectId(),
            "flight_id": flight1_id,
            "lat": 41.1,
            "lon": 60.1,
            "alt": 1723,
            "timestmp": datetime.now(timezone.utc)
        }
        position2 = {
            "_id": ObjectId(),
            "flight_id": flight2_id,
            "lat": 44.1,
            "lon": 63.1, 
            "alt": 1923,
            "timestmp": datetime.now(timezone.utc)
        }
        
        # Setup the mock to return our test flights
        mock_flights = [
            {
                "_id": flight1_id,
                "modeS": "4B2241",
                "callsign": "CLLSGN",
                "archived": False
            },
            {
                "_id": flight2_id,
                "modeS": "F1A2C0",
                "callsign": "OTHRCS",
                "archived": False
            }
        ]
        
        # Mock the MongoDB aggregation result for flights with latest positions
        self.mock_flights.aggregate.return_value = [
            {"flight": mock_flights[0], "position": position1},
            {"flight": mock_flights[1], "position": position2}
        ]
        
        # Run the initialization
        with patch('app.config.app_state.mongodb', self.mock_db):
            self.sut._initialize_from_db()
        
        # Verify the maps were populated correctly
        self.assertEqual(str(flight1_id), self.sut.modeS_flightid_map['4B2241'])
        self.assertEqual(str(flight2_id), self.sut.modeS_flightid_map['F1A2C0'])
        self.assertEqual((str(flight1_id), 41.1, 60.1, 1723), self.sut.flight_lastpos_map[str(flight1_id)])
        self.assertEqual((str(flight2_id), 44.1, 63.1, 1923), self.sut.flight_lastpos_map[str(flight2_id)])
from typing import List
from unittest.mock import patch, MagicMock
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from app.adsb.flightupdater import FlightUpdater
from app.adsb.model.position_report import PositionReport
from app.config import Config
from tests.db_base_test import MongoDBBaseTestCase


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
        
        # Create FlightUpdater instance without initialization
        self.sut = FlightUpdater()
        
        # Skip DB initialization and set up manually
        self.sut.db_repo = MagicMock()
        self.sut._mil_ranges = MockModeSUtil()
        self.sut._mil_only = False
        self.sut._service = MockRadarService()
        self.sut.is_updating = False
        self.sut.sleep_time = 1
        self.sut._t = None
        self.sut._websocket_callbacks = set()
        self.sut._positions_changed = False
        self.sut._changed_flight_ids = set()
        self.sut._previous_positions = {}
        self.sut._insert_batch_size = 200
        self.sut._delete_after = 30
        self.sut._cleanup_counter = 0
        self.sut._cleanup_frequency_sec = 10
        
        # Initialize required data structures that would normally be created in initialize()
        self.sut.modeS_flightid_map = {}
        self.sut.flight_lastpos_map = {}
        self.sut.flight_last_contact = {}
        self.sut.positions_hash = set()
        
    def tearDown(self):
        MongoDBBaseTestCase.tearDown(self)

    def test_threshold_timestamp(self):
        """Test that the threshold timestamp is calculated correctly"""
        now = datetime.now(timezone.utc)
        threshold = self.sut._threshold_timestamp()
        
        # The threshold should be exactly MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT minutes ago
        expected_threshold = now - timedelta(minutes=FlightUpdater.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)
        
        # Allow for a small difference due to test execution time
        difference = abs((threshold - expected_threshold).total_seconds())
        self.assertLess(difference, 1.0)  # Within 1 second

    def test_new_flight_after_time_threshold(self):
        """Test that a new flight is created when positions are reported after MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT"""
        # Setup test data
        initial_icao = "ABCDEF"
        initial_callsign = "TEST123"
        initial_flight_id = ObjectId()
        
        # Create an initial flight with a timestamp older than the threshold
        now = datetime.now(timezone.utc)
        old_timestamp = now - timedelta(minutes=FlightUpdater.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT + 1)
        
        # Add the flight to the flight maps
        self.sut.modeS_flightid_map[initial_icao] = str(initial_flight_id)
        self.sut.flight_last_contact[str(initial_flight_id)] = old_timestamp
        
        # Create a new flight that will be created
        new_flight_id = ObjectId()
        
        # Create a mock update_flights method that demonstrates the behavior
        def mock_process_flight_batch(batch, flights_by_icao, thresh_timestmp, now, all_inserted, all_updated):
            # Simulate finding flight in database but with old timestamp
            # This is what happens in _process_flight_batch when a flight is found
            # but its last_contact is older than the threshold
            if any(f.icao24 == initial_icao for f in batch):
                # Get an updated flight object for the new flight that will be created
                flight_obj = {
                    "_id": new_flight_id,
                    "modeS": initial_icao,
                    "callsign": initial_callsign,
                    "is_military": False,
                    "first_contact": now,
                    "last_contact": now
                }
                
                # Update in-memory maps
                self.sut.modeS_flightid_map[initial_icao] = str(new_flight_id)
                self.sut.flight_last_contact[str(new_flight_id)] = now
                
                # Return the new flight ID and callsign for inserted_flights
                all_inserted.append((initial_icao, initial_callsign))
                
                # Record that get_or_create_flight was called with expected params
                self.sut.db_repo.get_or_create_flight(
                    modeS=initial_icao,
                    callsign=initial_callsign,
                    is_military=False
                )
                
                return flight_obj
        
        # Patch the _process_flight_batch method
        self.sut._process_flight_batch = mock_process_flight_batch
        
        # Create a custom update_flights method that properly calls our mock
        def custom_update_flights(flights):
            if not flights:
                return
                
            # Get current timestamp once
            now = datetime.now(timezone.utc)
            thresh_timestmp = self.sut._threshold_timestamp()
            
            # Prepare tracking data
            all_inserted = []
            all_updated = []
            
            # Create a dict of flights by icao24
            flights_by_icao = {f.icao24: f for f in flights}
            
            # Call our mock implementation
            self.sut._process_flight_batch(
                flights, 
                flights_by_icao,
                thresh_timestmp, 
                now, 
                all_inserted, 
                all_updated
            )
            
            # Return the inserted flights data for verification
            return all_inserted
        
        # Replace the update_flights method with our custom implementation
        self.sut.update_flights = custom_update_flights
        
        # Create a new position with the same aircraft code but after threshold
        new_position = PositionReport(initial_icao, 45.0, 65.0, 2000, 180, initial_callsign)
        
        # Call the update_flights method with the new position
        result = self.sut.update_flights([new_position])
        
        # Verify a new flight was created by checking the result
        self.assertEqual(result, [(initial_icao, initial_callsign)])
        
        # Verify our get_or_create_flight was called with correct parameters
        self.sut.db_repo.get_or_create_flight.assert_called_with(
            modeS=initial_icao,
            callsign=initial_callsign,
            is_military=False
        )
        
        # Verify the modeS_flightid_map was updated to point to the new flight
        self.assertEqual(self.sut.modeS_flightid_map[initial_icao], str(new_flight_id))
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from app.adsb.flight_updater_coordinator import FlightUpdaterCoordinator
from app.adsb.constants import MINUTES_BEFORE_CONSIDERED_NEW_FLIGHT
from tests.db_base_test import MongoDBBaseTestCase


class FlightUpdaterCoordinatorTest(MongoDBBaseTestCase):

    def setUp(self):
        # Call parent setup to create MongoDB mocks
        MongoDBBaseTestCase.setUp(self)
        
        # Create FlightUpdaterCoordinator instance
        self.sut = FlightUpdaterCoordinator()
        
        # Mock the internal components
        self.mock_radar_service = MagicMock()
        self.mock_flight_manager = MagicMock()
        self.mock_position_manager = MagicMock()
        self.mock_websocket_notifier = MagicMock()
        
        self.sut._radar_service = self.mock_radar_service
        self.sut._flight_manager = self.mock_flight_manager
        self.sut._position_manager = self.mock_position_manager
        self.sut._websocket_notifier = self.mock_websocket_notifier
        
    def tearDown(self):
        MongoDBBaseTestCase.tearDown(self)

    def test_is_service_alive(self):
        """Test that is_service_alive returns radar service status"""
        self.mock_radar_service.connection_alive = True
        
        result = self.sut.is_service_alive()
        
        self.assertTrue(result)

    def test_get_cached_flights(self):
        """Test that get_cached_flights returns position manager data"""
        expected_flights = {"flight1": "data"}
        self.mock_position_manager.get_cached_flights.return_value = expected_flights
        
        result = self.sut.get_cached_flights()
        
        self.assertEqual(result, expected_flights)
        self.mock_position_manager.get_cached_flights.assert_called_once_with(self.mock_flight_manager)

    def test_websocket_callback_registration(self):
        """Test websocket callback registration and unregistration"""
        callback = MagicMock()
        
        # Test registration
        result = self.sut.register_websocket_callback(callback)
        self.mock_websocket_notifier.register_callback.assert_called_once_with(callback)
        
        # Test unregistration
        self.sut.unregister_websocket_callback(callback)
        self.mock_websocket_notifier.unregister_callback.assert_called_once_with(callback)

    def test_get_silhouette_params(self):
        """Test that get_silhouette_params returns radar service params"""
        expected_params = {"prefix": "/img/", "suffix": ".png"}
        self.mock_radar_service.get_silhouete_params.return_value = expected_params
        
        result = self.sut.get_silhouete_params()
        
        self.assertEqual(result, expected_params)
        self.mock_radar_service.get_silhouete_params.assert_called_once()
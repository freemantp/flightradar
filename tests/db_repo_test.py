import unittest
import time
from unittest.mock import patch, MagicMock
from bson import ObjectId

from app.adsb.db.mongodb_repository import MongoDBRepository
from db_base_test import MongoDBBaseTestCase


class MongoDBRepositoryTest(MongoDBBaseTestCase):

    def test_delete(self):
        """Test flight deletion"""
        # Setup test data
        flight_ids = [str(ObjectId()), str(ObjectId())]
        
        # Create repository with mocked DB
        repo = MongoDBRepository(self.mock_db)
        
        # Test delete method
        repo.delete_flights_and_positions(flight_ids)
        
        # Assert that delete_many was called with correct parameters
        self.mock_positions.delete_many.assert_called_once()
        self.mock_flights.delete_many.assert_called_once()
        
        # Verify the correct filter was passed to delete_many
        positions_call_args = self.mock_positions.delete_many.call_args[0][0]
        flights_call_args = self.mock_flights.delete_many.call_args[0][0]
        
        # Check that $in operator is used with the correct ObjectIds
        self.assertIn("$in", positions_call_args["flight_id"])
        self.assertIn("$in", flights_call_args["_id"])
        
        # Length of ids list should match
        self.assertEqual(len(positions_call_args["flight_id"]["$in"]), len(flight_ids))
        self.assertEqual(len(flights_call_args["_id"]["$in"]), len(flight_ids))
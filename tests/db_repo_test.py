import unittest
import time
from unittest.mock import patch, MagicMock
from bson import ObjectId

from app.data.repositories.mongodb_repository import MongoDBRepository
from tests.db_base_test import MongoDBBaseTestCase


class MongoDBRepositoryTest(MongoDBBaseTestCase):

    def test_delete(self):
        """Test flight deletion"""
        # Setup test data
        flight_ids = [str(ObjectId()), str(ObjectId())]
        
        # Set up the collection mocking properly
        positions_collection = MagicMock()
        flights_collection = MagicMock()
        
        # Set up the mocked collections
        self.mock_db.__getitem__ = MagicMock()
        self.mock_db.__getitem__.side_effect = lambda x: {
            'positions': positions_collection,
            'flights': flights_collection
        }.get(x, MagicMock())
        
        # Create repository with mocked DB
        repo = MongoDBRepository(self.mock_db)
        
        # Disable _ensure_indexes to simplify test
        repo._ensure_indexes = MagicMock()
        
        # Test delete method
        repo.delete_flights_and_positions(flight_ids)
        
        # Assert that delete_many was called at least once on each collection
        positions_collection.delete_many.assert_called()
        flights_collection.delete_many.assert_called()
        
        # Get the last call arguments
        positions_call_args = positions_collection.delete_many.call_args[0][0]
        flights_call_args = flights_collection.delete_many.call_args[0][0]
        
        # Check that $in operator is used with the correct ObjectIds
        self.assertIn("$in", positions_call_args["flight_id"])
        self.assertIn("$in", flights_call_args["_id"])
        
        # Verify at least one ID is included
        position_ids = positions_call_args["flight_id"]["$in"]
        flight_ids_obj = flights_call_args["_id"]["$in"]
        
        self.assertTrue(len(position_ids) > 0)
        self.assertTrue(len(flight_ids_obj) > 0)
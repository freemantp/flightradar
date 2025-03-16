from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Set
from pymongo.database import Database
from pymongo import ReturnDocument, UpdateOne
from itertools import zip_longest
from bson.objectid import ObjectId

from .mongodb_models import Flight


class MongoDBRepository:
    def __init__(self, db: Database):
        self.db = db

        # Use collection names from db object if available, otherwise use defaults
        flights_collection_name = getattr(db, 'flights_collection', 'flights')
        positions_collection_name = getattr(db, 'positions_collection', 'positions')

        self.flights_collection = db[flights_collection_name]
        self.positions_collection = db[positions_collection_name]

        # Store collection names for aggregation pipelines
        self.flights_collection_name = flights_collection_name
        self.positions_collection_name = positions_collection_name

        # Create indexes for better performance
        self._ensure_indexes()

    @staticmethod
    def split_flights(positions: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Splits position data into 'flights' based on time gaps"""
        flights = []

        if positions:
            fifteen_min = timedelta(minutes=15)
            current_flight_id = positions[0]["flight_id"]
            start_idx = 0

            for i in range(1, len(positions)):
                tdiff = positions[i]["timestmp"] - positions[i-1]["timestmp"]
                if abs(tdiff) > fifteen_min or positions[i]["flight_id"] != current_flight_id:
                    flights.append(positions[start_idx:i])
                    start_idx = i
                    current_flight_id = positions[i]["flight_id"]

            flights.append(positions[start_idx:])
        return flights

    def _ensure_indexes(self):
        """Create indexes for better query performance"""
        # Flights collection indexes
        self.flights_collection.create_index("modeS", unique=True)  # Ensure modeS is unique
        self.flights_collection.create_index([("archived", 1), ("last_contact", 1)])

        # Positions collection indexes
        self.positions_collection.create_index([("flight_id", 1), ("timestmp", 1)])

    def get_flights(self, modeS_addr: str) -> List[Dict[str, Any]]:
        """Get flights by ICAO Mode-S address"""
        return list(self.flights_collection.find({"modeS": modeS_addr}))

    def get_flights_batch(self, modeS_addrs: Set[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Get flights for multiple ICAO Mode-S addresses in a single query"""
        if not modeS_addrs:
            return {}

        results = self.flights_collection.find({"modeS": {"$in": list(modeS_addrs)}})

        # Group flights by modeS address
        flights_by_modeS = {}
        for flight in results:
            modeS = flight["modeS"]
            if modeS not in flights_by_modeS:
                flights_by_modeS[modeS] = []
            flights_by_modeS[modeS].append(flight)

        return flights_by_modeS

    def flight_exists(self, flight_id: str) -> bool:
        """Check if flight exists by ID"""
        return self.flights_collection.count_documents({"_id": ObjectId(flight_id)}) > 0

    def get_all_positions(self, is_archived: bool = False) -> Dict[str, List[Tuple[float, float, int]]]:
        """Get all positions for non-archived or archived flights"""
        pipeline = [
            {"$match": {"archived": is_archived}},
            {"$lookup": {
                "from": self.positions_collection_name,
                "localField": "_id",
                "foreignField": "flight_id",
                "as": "positions"
            }},
            {"$unwind": "$positions"},
            {"$sort": {"positions.timestmp": 1}},
            {"$project": {
                "modeS": 1,
                "lat": "$positions.lat",
                "lon": "$positions.lon",
                "alt": "$positions.alt"
            }}
        ]

        positions_map = {}
        results = list(self.flights_collection.aggregate(pipeline))

        for result in results:
            modeS = result["modeS"]
            if modeS not in positions_map:
                positions_map[modeS] = []
            positions_map[modeS].append((result["lat"], result["lon"], result["alt"]))

        return positions_map

    def get_positions(self, flight_id: str) -> List[Dict[str, Any]]:
        """Get all positions for a specific flight"""
        return list(self.positions_collection.find(
            {"flight_id": ObjectId(flight_id)}).sort("timestmp", 1))

    def get_recent_flights_last_pos(self, min_timestamp=datetime.min, page_size=None, last_id=None) -> List[Dict[str, Any]]:
        """Get recent flights with their latest position, with optional pagination"""
        match_stage = {"last_contact": {"$gt": min_timestamp}}

        # If we have a last_id, add it to the match for pagination
        if last_id:
            match_stage["_id"] = {"$gt": last_id}

        pipeline = [
            {"$match": match_stage},
            {"$sort": {"_id": 1}},  # Consistent sort for pagination
        ]

        # Add limit if page_size is provided
        if page_size:
            pipeline.append({"$limit": page_size})

        # Continue with lookup for positions
        pipeline.extend([
            {"$lookup": {
                "from": self.positions_collection_name,
                "let": {"flight_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$flight_id", "$$flight_id"]}}},
                    {"$sort": {"timestmp": -1}},
                    {"$limit": 1}
                ],
                "as": "latest_position"
            }},
            {"$unwind": "$latest_position"},
            {"$project": {
                "flight": "$$ROOT",
                "position": "$latest_position"
            }}
        ])

        # Use a properly indexed field for the sort
        pipeline.append({"$sort": {"flight.last_contact": -1}})

        return list(self.flights_collection.aggregate(pipeline))

    def get_non_archived_flights_older_than(self, timestamp: datetime) -> List[Dict[str, Any]]:
        """Get non-archived flights with last contact older than given timestamp"""
        return list(self.flights_collection.find({
            "last_contact": {"$lt": timestamp},
            "archived": False
        }))

    def delete_flights_and_positions(self, flight_ids: List[str]):
        """Delete flights and their positions"""
        assert len(flight_ids) > 0

        for ids_chunk in self._get_chunks(flight_ids, 200):
            # Filter out None values added by zip_longest
            ids = [ObjectId(id) for id in ids_chunk if id is not None]

            # Delete positions first
            self.positions_collection.delete_many({"flight_id": {"$in": ids}})

            # Then delete flights
            self.flights_collection.delete_many({"_id": {"$in": ids}})

    def insert_flight(self, flight: Flight) -> str:
        """Insert a new flight and return its ID"""
        flight_dict = flight.model_dump()
        result = self.flights_collection.insert_one(flight_dict)
        return str(result.inserted_id)

    def update_flight(self, flight_id: str, flight_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update flight data"""
        result = self.flights_collection.find_one_and_update(
            {"_id": ObjectId(flight_id)},
            {"$set": flight_data},
            return_document=ReturnDocument.AFTER
        )
        return result

    def bulk_update_flights(self, flight_updates: List[Tuple[str, Dict[str, Any]]]) -> None:
        """Update multiple flights in a single operation"""
        if not flight_updates:
            return

        bulk_ops = []
        for flight_id, update_data in flight_updates:
            bulk_ops.append(UpdateOne(
                {"_id": ObjectId(flight_id)},
                {"$set": update_data}
            ))

        if bulk_ops:
            self.flights_collection.bulk_write(bulk_ops)

    def update_flight_last_contact(self, flight_id: str, timestamp: datetime) -> None:
        """Update flight's last contact timestamp"""
        self.flights_collection.update_one(
            {"_id": ObjectId(flight_id)},
            {"$set": {"last_contact": timestamp}}
        )

    def bulk_update_flight_last_contacts(self, flight_updates: List[Tuple[str, datetime]]) -> None:
        """Update last_contact timestamps for multiple flights in one operation"""
        if not flight_updates:
            return

        bulk_ops = []
        for flight_id, timestamp in flight_updates:
            bulk_ops.append(UpdateOne(
                {"_id": ObjectId(flight_id)},
                {"$set": {"last_contact": timestamp}}
            ))

        if bulk_ops:
            self.flights_collection.bulk_write(bulk_ops)

    def insert_positions(self, positions: List[Dict[str, Any]]) -> None:
        """Insert multiple position documents"""
        if positions:
            self.positions_collection.insert_many(positions)

    def get_or_create_flight(self, modeS: str, callsign: Optional[str], is_military: bool) -> Dict[str, Any]:
        """Get existing flight or create a new one"""
        now = datetime.utcnow()
        result = self.flights_collection.find_one_and_update(
            {"modeS": modeS},
            {"$set": {
                "last_contact": now,
                **({"callsign": callsign} if callsign else {})
            },
                "$setOnInsert": {
                "is_military": is_military,
                "archived": False,
                "first_contact": now
            }},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return result

    @staticmethod
    def _get_chunks(iterable, chunk_size):
        args = [iter(iterable)] * chunk_size
        return zip_longest(*args, fillvalue=None)

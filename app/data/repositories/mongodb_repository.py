from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional, Any, Set
from pymongo.database import Database
from pymongo import ReturnDocument, UpdateOne
from itertools import zip_longest
from bson.objectid import ObjectId
from functools import wraps

from ..models import Flight, IncompleteAircraft


def handle_mongodb_errors(func):
    """Decorator to handle MongoDB specidic errors"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "you are over your space quota" in str(e):
                from app.exceptions import DatabaseException
                raise DatabaseException("MongoDB space quota exceeded: " + str(e)) from e
            raise
    return wrapper


class MongoDBRepository:
    def __init__(self, db: Database):
        self.db = db

        # Use collection names from db object if available, otherwise use defaults
        flights_collection_name = getattr(db, 'flights_collection', 'flights')
        positions_collection_name = getattr(db, 'positions_collection', 'positions')
        unknown_aircraft_collection_name = 'aircraft_to_process'

        self.flights_collection = db[flights_collection_name]
        self.positions_collection = db[positions_collection_name]
        self.unknown_aircraft_collection = db[unknown_aircraft_collection_name]

        # Store collection names for aggregation pipelines
        self.flights_collection_name = flights_collection_name
        self.positions_collection_name = positions_collection_name
        self.unknown_aircraft_collection_name = unknown_aircraft_collection_name

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
        existing_indexes = self.flights_collection.index_information()
        
        # Drop the existing unique modeS index if it exists
        if "modeS_1" in existing_indexes:
            # Check if it's a unique index
            if existing_indexes["modeS_1"].get("unique", False):
                # Drop the unique index
                self.flights_collection.drop_index("modeS_1")
                # Create a non-unique index
                self.flights_collection.create_index("modeS", unique=False)
        else:
            # Create a non-unique index if it doesn't exist
            self.flights_collection.create_index("modeS", unique=False)
            
        # Create index for last_contact
        self.flights_collection.create_index("last_contact")
        
        # Create compound index for modeS + callsign for faster lookups
        self.flights_collection.create_index([("modeS", 1), ("callsign", 1)])

        # Positions collection indexes
        self.positions_collection.create_index([("flight_id", 1), ("timestmp", 1)])
        
        self.unknown_aircraft_collection.create_index("modeS", unique=True)
        self.unknown_aircraft_collection.create_index("last_seen")

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

    def get_all_positions(self) -> Dict[str, List[Tuple[float, float, int]]]:
        """Get all positions for flights"""
        pipeline = [
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
        
    def get_all_flights_last_pos(self) -> List[Dict[str, Any]]:
        """Get all flights with their latest position"""
        pipeline = [
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
            {"$match": {"latest_position": {"$ne": []}}},  # Only include flights with positions
            {"$unwind": "$latest_position"},
            {"$project": {
                "flight": "$$ROOT",
                "position": "$latest_position"
            }},
            {"$sort": {"flight.last_contact": -1}}
        ]
        
        return list(self.flights_collection.aggregate(pipeline))

    def get_flights_older_than(self, timestamp: datetime) -> List[Dict[str, Any]]:
        """Get flights with last contact older than given timestamp"""
        return list(self.flights_collection.find({
            "last_contact": {"$lt": timestamp}
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

    @handle_mongodb_errors
    def bulk_update_flights(self, flight_updates: List[Tuple[str, Dict[str, Any]]]) -> None:
        """Update multiple flights in a single operation with optimized batching"""
        if not flight_updates:
            return

        # Use optimal batch size for MongoDB bulk operations
        # Balances network overhead vs large batch sizes
        batch_size = 500
        
        # Process in batches to avoid large requests that could time out
        for i in range(0, len(flight_updates), batch_size):
            batch = flight_updates[i:i+batch_size]
            
            bulk_ops = []
            for flight_id, update_data in batch:
                bulk_ops.append(UpdateOne(
                    {"_id": ObjectId(flight_id)},
                    {"$set": update_data}
                ))

            if bulk_ops:
                self.flights_collection.bulk_write(bulk_ops, ordered=False)

    def update_flight_last_contact(self, flight_id: str, timestamp: datetime) -> None:
        """Update flight's last contact timestamp"""
        self.flights_collection.update_one(
            {"_id": ObjectId(flight_id)},
            {"$set": {"last_contact": timestamp}}
        )

    @handle_mongodb_errors
    def bulk_update_flight_last_contacts(self, flight_updates: List[Tuple[str, datetime]]) -> None:
        """Update last_contact timestamps for multiple flights with optimized batching"""
        if not flight_updates:
            return

        # Use optimal batch size for MongoDB bulk operations
        batch_size = 500
        
        # Process in batches to avoid large operations
        for i in range(0, len(flight_updates), batch_size):
            batch = flight_updates[i:i+batch_size]
            
            bulk_ops = []
            for flight_id, timestamp in batch:
                bulk_ops.append(UpdateOne(
                    {"_id": ObjectId(flight_id)},
                    {"$set": {"last_contact": timestamp}}
                ))

            if bulk_ops:
                self.flights_collection.bulk_write(bulk_ops, ordered=False)

    @handle_mongodb_errors
    def insert_positions(self, positions: List[Dict[str, Any]]) -> None:
        """Insert multiple position documents"""
        if positions:
            self.positions_collection.insert_many(positions)

    @handle_mongodb_errors
    def get_or_create_flight(self, modeS: str, is_military: bool, callsign: Optional[str] = None, expire_at: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Create a new flight record for an aircraft.
        In the new design, each flight (even from the same aircraft) gets a new record.
        """
        now = datetime.now(timezone.utc)
        
        try:
            # Create a new flight document
            flight_doc = {
                "modeS": modeS,
                "last_contact": now,
                "is_military": is_military,
                "first_contact": now
            }
            
            # Add callsign if provided
            if callsign:
                flight_doc["callsign"] = callsign
                
            # Add expiration time if provided
            if expire_at:
                flight_doc["expire_at"] = expire_at
                
            # Insert the new flight
            result = self.flights_collection.insert_one(flight_doc)
            
            return self.flights_collection.find_one({"_id": result.inserted_id})
            
        except Exception as e:
            # If insertion failed (probably due to the unique modeS index still existing),
            # fall back to the old behavior for backward compatibility
            import logging
            logger = logging.getLogger("MongoDBRepository")
            logger.warning(f"Failed to create new flight record, falling back to upsert: {str(e)}")
            
            # Prepare set fields
            set_fields = {
                "last_contact": now
            }
            
            if callsign:
                set_fields["callsign"] = callsign
                
            if expire_at:
                set_fields["expire_at"] = expire_at
            
            result = self.flights_collection.find_one_and_update(
                {"modeS": modeS},
                {"$set": set_fields,
                 "$setOnInsert": {
                    "is_military": is_military,
                    "first_contact": now
                }},
                upsert=True,
                return_document=ReturnDocument.AFTER
            )
            return result
        
    @handle_mongodb_errors
    def update_flight(self, flight_id: str, callsign: Optional[str] = None, last_contact: Optional[datetime] = None) -> Dict[str, Any]:
        """Update an existing flight with new information"""
        update_doc = {}
        
        if callsign is not None:
            update_doc["callsign"] = callsign
            
        if last_contact is not None:
            update_doc["last_contact"] = last_contact
            
        if not update_doc:
            return None
        
        result = self.flights_collection.find_one_and_update(
            {"_id": ObjectId(flight_id)},
            {"$set": update_doc},
            return_document=ReturnDocument.AFTER
        )
        
        return result

    @handle_mongodb_errors
    def insert_unknown_aircraft(self, aircraft_to_process: IncompleteAircraft) -> str:
        """Insert a new unknown aircraft record"""
        aircraft_dict = aircraft_to_process.model_dump()
        result = self.unknown_aircraft_collection.insert_one(aircraft_dict)
        return str(result.inserted_id)

    @handle_mongodb_errors
    def get_or_create_unknown_aircraft(self, modeS: str, sources_queried: List[str] = None, expire_at: Optional[datetime] = None) -> Dict[str, Any]:
        """Get existing unknown aircraft or create a new record"""
        if sources_queried is None:
            sources_queried = []
            
        now = datetime.now(timezone.utc)
        
        update_doc = {
            "$set": {
                "last_seen": now
            },
            "$inc": {
                "query_attempts": 1
            }
        }
        
        if sources_queried:
            update_doc["$addToSet"] = {"sources_queried": {"$each": sources_queried}}
            
        if expire_at:
            update_doc["$set"]["expire_at"] = expire_at
        
        result = self.unknown_aircraft_collection.find_one_and_update(
            {"modeS": modeS},
            update_doc,
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 1, "modeS": 1, "query_attempts": 1, "last_seen": 1, "sources_queried": 1}
        )
        
        if result and result.get("query_attempts") == 1:
            set_on_insert = {
                "first_seen": now,
                "sources_queried": sources_queried
            }
            if expire_at:
                set_on_insert["expire_at"] = expire_at
                
            self.unknown_aircraft_collection.update_one(
                {"_id": result["_id"]},
                {"$setOnInsert": set_on_insert}
            )
            
        return result

    def get_unknown_aircraft(self, modeS: str) -> Optional[Dict[str, Any]]:
        """Get unknown aircraft by ICAO Mode-S address"""
        return self.unknown_aircraft_collection.find_one({"modeS": modeS})

    def get_unknown_aircraft_older_than(self, timestamp: datetime) -> List[Dict[str, Any]]:
        """Get unknown aircraft with last_seen older than given timestamp"""
        return list(self.unknown_aircraft_collection.find({
            "last_seen": {"$lt": timestamp}
        }))

    @handle_mongodb_errors
    def delete_unknown_aircraft(self, aircraft_ids: List[str]) -> None:
        """Delete unknown aircraft records"""
        if aircraft_ids:
            object_ids = [ObjectId(id) for id in aircraft_ids]
            self.unknown_aircraft_collection.delete_many({"_id": {"$in": object_ids}})

    @staticmethod
    def _get_chunks(iterable, chunk_size):
        args = [iter(iterable)] * chunk_size
        return zip_longest(*args, fillvalue=None)

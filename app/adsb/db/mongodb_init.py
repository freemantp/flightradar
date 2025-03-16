import datetime
import certifi
import logging
from pymongo import MongoClient

def init_mongodb(connection_string: str, db_name: str):
    """Initialize MongoDB connection and create indexes"""
    logger = logging.getLogger(__name__)

    # Connect with the connection string
    try:
        # Log connection attempt without exposing credentials
        if '@' in connection_string:
            masked_uri = connection_string.split('@')[0].split('://')[0] + '://*****@' + connection_string.split('@')[1]
            logger.info(f"Connecting to MongoDB at {masked_uri}")
        else:
            logger.info(f"Connecting to MongoDB")

        client = MongoClient(connection_string, tlsCAFile=certifi.where())

        # Verify connection by pinging
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {str(e)}")
        raise

    db = client[db_name]

    # Define collection names
    flights_collection = "flights"
    positions_collection = "positions"
    db.flights_collection = flights_collection
    db.positions_collection = positions_collection

    # Create collections if they don't exist
    if flights_collection not in db.list_collection_names():
        flights_coll = db.create_collection(flights_collection)
        flights_coll.create_index("modeS", unique=True)
        flights_coll.create_index("last_contact")
        flights_coll.create_index("is_military")
        flights_coll.create_index("archived")

    # Create time series collection for positions if it doesn't exist
    if positions_collection not in db.list_collection_names():
        db.create_collection(
            positions_collection,
            timeseries={
                "timeField": "timestmp",
                "metaField": "flight_id",
                "granularity": "seconds"
            }
        )
        db[positions_collection].create_index("flight_id")

    return db

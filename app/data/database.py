import certifi
import logging
from pymongo import MongoClient

def init_mongodb(connection_string: str, db_name: str, retention_minutes: int):
    """Initialize MongoDB connection and create indexes"""
    logger = logging.getLogger("MongoDBInit")

    # Connect with the connection string
    try:
        # Log connection attempt without exposing credentials
        if '@' in connection_string:
            masked_uri = connection_string.split('@')[0].split('://')[0] + '://*****@' + connection_string.split('@')[1]
            logger.info(f"Connecting to MongoDB at {masked_uri}")
        else:
            logger.info(f"Connecting to MongoDB")

        # Only add tlsCAFile if ssl or tls are not explicitly set to false
        lower_conn = connection_string.lower()
        use_tls = not (("ssl=false" in lower_conn) or ("tls=false" in lower_conn))
        if use_tls:
            client = MongoClient(connection_string, tlsCAFile=certifi.where())
        else:
            client = MongoClient(connection_string)

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
        flights_coll.create_index("modeS", unique=False)
        flights_coll.create_index("last_contact")
        flights_coll.create_index("is_military")
        
        # Create TTL index if retention is specified
        if retention_minutes and retention_minutes > 0:
            logger.info(f"Creating TTL index for flights with retention of {retention_minutes} minutes")
            flights_coll.create_index("expire_at", expireAfterSeconds=0)

    # Create TTL index for flights collection if it doesn't exist yet
    elif retention_minutes and retention_minutes > 0:
        # Check if TTL index exists
        indexes = db[flights_collection].index_information()
        ttl_index_exists = False
        for index_name, index_info in indexes.items():
            if len(index_info['key']) == 1 and index_info['key'][0][0] == 'expire_at':
                ttl_index_exists = True
                break
                
        if not ttl_index_exists:
            logger.info(f"Creating TTL index for flights with retention of {retention_minutes} minutes")
            db[flights_collection].create_index("expire_at", expireAfterSeconds=0)

    # Create time series collection for positions if it doesn't exist
    if positions_collection not in db.list_collection_names():
        # Configure time-series collection
        timeseries_config = {
            "timeField": "timestmp",
            "metaField": "flight_id",
            "granularity": "seconds"
        }
        
        # Create collection options
        collection_options = {"timeseries": timeseries_config}
        
        # Add expiration setting at collection level if retention is specified
        if retention_minutes and retention_minutes > 0:
            collection_options["expireAfterSeconds"] = retention_minutes * 60
            logger.info(f"Creating time-series collection with expireAfterSeconds={retention_minutes * 60}")
        
        # Create the collection with the configured options
        db.create_collection(
            positions_collection,
            **collection_options
        )
        
        # Create index on meta field for faster queries
        db[positions_collection].create_index("flight_id")
        
        # No need for additional TTL index configuration for time-series collections
        # Expiration is handled by the time-series collection configuration
    
    # For existing time-series collections, we can't modify the expiration directly
    # Time-series collections handle expiration through their initial configuration

    return db

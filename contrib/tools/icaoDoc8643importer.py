#!/usr/bin/env python3

import argparse
import json
import logging
import sys
import requests
from pathlib import Path

# Add the parent directory to the path to import from app
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import Config
from app.data.database import init_mongodb

def fetch_icao_data():
    """Fetch ICAO aircraft type data from the official endpoint"""
    
    logger = logging.getLogger("IcaoImporter")
    
    url = "https://www4.icao.int/doc8643/External/AircraftTypes"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Length": "0"
    }
    
    try:
        logger.info("Fetching data from ICAO endpoint...")
        response = requests.post(url, headers=headers, data="", timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Successfully fetched {len(data)} records from ICAO")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch data from ICAO endpoint: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        return None

def update_icao_designators(config: Config):
    """Update ICAO type designators in MongoDB collection from ICAO endpoint"""
    
    logger = logging.getLogger("IcaoImporter")
    
    # Initialize MongoDB connection
    try:
        db = init_mongodb(config.MONGODB_URI, config.MONGODB_DB_NAME, config.DB_RETENTION_MIN)
        logger.info("Connected to MongoDB successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return False
    
    # Fetch data from ICAO endpoint
    data = fetch_icao_data()
    if data is None:
        return False
    
    # Get or create the collection
    collection = db["icao_type_designators"]
    
    # Transform and insert data
    documents = []
    for item in data:
        if "Designator" in item and "Description" in item:
            doc = {
                "icaoTypeCode": item["Designator"],
                "icaoTypeDesignator": item["Description"]
            }
            documents.append(doc)
    
    if not documents:
        logger.warning("No valid documents found to import")
        return False
    
    try:
        # Clear existing data
        result = collection.delete_many({})
        logger.info(f"Cleared {result.deleted_count} existing documents")
        
        # Insert new data
        result = collection.insert_many(documents)
        logger.info(f"Imported {len(result.inserted_ids)} ICAO type designators")
        return True
        
    except Exception as e:
        logger.error(f"Failed to import data: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Update ICAO Doc 8643 aircraft type designators in MongoDB from ICAO endpoint")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("IcaoImporter")
    
    # Load configuration
    try:
        config = Config(args.config)
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Update data
    success = update_icao_designators(config)
    
    if success:
        logger.info("Update completed successfully")
        sys.exit(0)
    else:
        logger.error("Update failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
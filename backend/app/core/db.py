from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import os
import logging
from datetime import datetime
from app.config import MONGO_URI

logger = logging.getLogger(__name__)

# Initialize MongoDB client with error handling
client = None
db = None

def init_db():
    """Initialize MongoDB connection."""
    global client, db
    
    if not MONGO_URI:
        logger.error("MONGO_URI environment variable is not set!")
        raise ValueError("MONGO_URI environment variable is required. Please set it in your .env file.")
    
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test the connection
        client.admin.command('ping')
        db = client["mangobytes"]
        logger.info("MongoDB connection established successfully")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        logger.error(f"MONGO_URI: {MONGO_URI[:20]}..." if MONGO_URI and len(MONGO_URI) > 20 else f"MONGO_URI: {MONGO_URI}")
        raise ConnectionError(f"Could not connect to MongoDB. Please check your MONGO_URI: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {str(e)}")
        raise

# Initialize on import
try:
    init_db()
except Exception as e:
    logger.warning(f"MongoDB initialization failed: {str(e)}. Database operations will fail until connection is established.")

def save_graph(graph_name, graph_dict, timestamp=None):
    """Saves only the UI-ready graph data."""
    if db is None:
        raise ConnectionError("MongoDB connection not initialized. Check MONGO_URI in .env file.")
    
    try:
        update_data = {
            "graph_name": graph_name,  # Ensure graph_name is in the document
            "graph_data": graph_dict,
            "timestamp": timestamp or datetime.now()
        }
        result = db.graphs.update_one(
            {"graph_name": graph_name},
            {"$set": update_data},
            upsert=True
        )
        logger.info(f"Graph '{graph_name}' saved to MongoDB (upserted: {result.upserted_id is not None})")
        return result.upserted_id or result.modified_count
    except Exception as e:
        logger.error(f"Error saving graph to MongoDB: {str(e)}")
        raise


def save_parsed_data(graph_name, parsed_json):
    """Saves the raw structural data in a separate collection."""
    if db is None:
        raise ConnectionError("MongoDB connection not initialized. Check MONGO_URI in .env file.")
    
    try:
        result = db.parsed_data.update_one(
            {"graph_name": graph_name},
            {"$set": {"parsed_data": parsed_json, "graph_name": graph_name}},
            upsert=True
        )
        logger.info(f"Parsed data '{graph_name}' saved to MongoDB (upserted: {result.upserted_id is not None})")
        return result.upserted_id or result.modified_count
    except Exception as e:
        logger.error(f"Error saving parsed data to MongoDB: {str(e)}")
        raise

def get_graph(graph_name):
    """Get graph from MongoDB by name."""
    if db is None:
        raise ConnectionError("MongoDB connection not initialized. Check MONGO_URI in .env file.")
    
    try:
        result = db.graphs.find_one({"graph_name": graph_name})
        # Convert MongoDB ObjectId to string for JSON serialization
        if result:
            result["_id"] = str(result["_id"])
        return result
    except Exception as e:
        logger.error(f"Error getting graph from MongoDB: {str(e)}")
        raise

def get_all_graphs():
    """Get all graphs from MongoDB."""
    if db is None:
        raise ConnectionError("MongoDB connection not initialized. Check MONGO_URI in .env file.")
    
    try:
        results = list(db.graphs.find({}))
        # Convert all ObjectIds to strings for JSON serialization
        for result in results:
            result["_id"] = str(result["_id"])
        return results
    except Exception as e:
        logger.error(f"Error getting all graphs from MongoDB: {str(e)}")
        raise

def get_parsed_data(graph_name):
    """Get parsed data from MongoDB by name."""
    if db is None:
        raise ConnectionError("MongoDB connection not initialized. Check MONGO_URI in .env file.")
    
    try:
        result = db.parsed_data.find_one({"graph_name": graph_name})
        # Convert MongoDB ObjectId to string for JSON serialization
        if result:
            result["_id"] = str(result["_id"])
        return result
    except Exception as e:
        logger.error(f"Error getting parsed data from MongoDB: {str(e)}")
        raise

def get_org_learning_metadata(org_key: str):
    """Get learning metadata (llm_summaries, notion_docs) for an org. Returns None if not found."""
    if db is None:
        raise ConnectionError("MongoDB connection not initialized. Check MONGO_URI in .env file.")
    try:
        result = db.org_learning_metadata.find_one({"org_key": org_key})
        if result:
            result["_id"] = str(result["_id"])
        return result
    except Exception as e:
        logger.error(f"Error getting org learning metadata: {e}")
        raise


def save_org_learning_metadata(org_key: str, llm_summaries: dict = None, notion_docs: str = ""):
    """Save or update learning metadata for an org."""
    if db is None:
        raise ConnectionError("MongoDB connection not initialized. Check MONGO_URI in .env file.")
    try:
        update = {"org_key": org_key}
        if llm_summaries is not None:
            update["llm_summaries"] = llm_summaries
        if notion_docs is not None:
            update["notion_docs"] = notion_docs
        result = db.org_learning_metadata.update_one(
            {"org_key": org_key},
            {"$set": update},
            upsert=True,
        )
        return result.upserted_id or result.modified_count
    except Exception as e:
        logger.error(f"Error saving org learning metadata: {e}")
        raise


def test_connection():
    """Test MongoDB connection."""
    try:
        if client is None or db is None:
            init_db()
        client.admin.command('ping')
        return {"status": "connected", "database": "mangobytes", "collections": db.list_collection_names()}
    except Exception as e:
        return {"status": "error", "error": str(e)}
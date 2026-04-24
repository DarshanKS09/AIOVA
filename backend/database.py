import os
from datetime import datetime
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "aivoa_db"
COLLECTION_NAME = "interactions"

_client = None
_db = None
_collection = None


def get_mongo_client():
    """Get or create MongoDB client."""
    global _client
    if _client is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            _client.admin.command("ping")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            raise ConnectionError(f"Failed to connect to MongoDB at {MONGO_URI}: {e}") from e
    return _client


def get_database():
    """Get MongoDB database."""
    global _db
    if _db is None:
        client = get_mongo_client()
        _db = client[DB_NAME]
    return _db


def get_collection():
    """Get interactions collection."""
    global _collection
    if _collection is None:
        db = get_database()
        _collection = db[COLLECTION_NAME]
        _collection.create_index("created_at")
    return _collection


def init_db(db_path: str | None = None) -> None:
    """Initialize database (ensure connection and indexes)."""
    try:
        collection = get_collection()
        collection.create_index("hcp_name")
        collection.create_index("date")
        collection.create_index("created_at")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize MongoDB: {e}") from e


def _serialize_document(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert MongoDB document to JSON-serializable format."""
    if doc is None:
        return None
    doc_copy = doc.copy()
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy.pop("_id"))
    for key, value in list(doc_copy.items()):
        if isinstance(value, datetime):
            doc_copy[key] = value.isoformat()
    return doc_copy


def list_interactions(db_path: str | None = None) -> list[dict[str, Any]]:
    """Get all interactions ordered by creation date (newest first)."""
    try:
        collection = get_collection()
        documents = list(collection.find().sort("created_at", -1))
        return [_serialize_document(doc) for doc in documents]
    except Exception as e:
        raise RuntimeError(f"Failed to list interactions: {e}") from e


def get_interaction(interaction_id: int | str, db_path: str | None = None) -> dict[str, Any] | None:
    """Get a single interaction by ID."""
    try:
        collection = get_collection()
        if isinstance(interaction_id, str):
            try:
                interaction_id = ObjectId(interaction_id)
            except Exception:
                return None
        elif isinstance(interaction_id, int):
            try:
                interaction_id = ObjectId(str(interaction_id))
            except Exception:
                return None

        document = collection.find_one({"_id": interaction_id})
        return _serialize_document(document)
    except Exception as e:
        raise RuntimeError(f"Failed to get interaction: {e}") from e


def insert_interaction(entry: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    """Insert a new interaction into the database."""
    try:
        collection = get_collection()
        document = {
            "hcp_name": entry.get("hcp_name", ""),
            "interaction_type": entry.get("interaction_type", ""),
            "date": entry.get("date", ""),
            "time": entry.get("time", ""),
            "attendees": entry.get("attendees", ""),
            "topics": entry.get("topics", ""),
            "materials": entry.get("materials", ""),
            "sentiment": entry.get("sentiment", ""),
            "outcomes": entry.get("outcomes", ""),
            "follow_up_actions": entry.get("follow_up_actions", ""),
            "created_at": datetime.utcnow(),
        }
        result = collection.insert_one(document)
        return get_interaction(result.inserted_id) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to insert interaction: {e}") from e


def update_interaction(
    interaction_id: int | str,
    entry: dict[str, Any],
    db_path: str | None = None,
) -> dict[str, Any]:
    """Update an existing interaction."""
    try:
        collection = get_collection()
        if isinstance(interaction_id, str):
            try:
                interaction_id = ObjectId(interaction_id)
            except Exception:
                raise ValueError(f"Invalid interaction ID: {interaction_id}")
        elif isinstance(interaction_id, int):
            try:
                interaction_id = ObjectId(str(interaction_id))
            except Exception:
                raise ValueError(f"Invalid interaction ID: {interaction_id}")

        update_doc = {
            "hcp_name": entry.get("hcp_name", ""),
            "interaction_type": entry.get("interaction_type", ""),
            "date": entry.get("date", ""),
            "time": entry.get("time", ""),
            "attendees": entry.get("attendees", ""),
            "topics": entry.get("topics", ""),
            "materials": entry.get("materials", ""),
            "sentiment": entry.get("sentiment", ""),
            "outcomes": entry.get("outcomes", ""),
            "follow_up_actions": entry.get("follow_up_actions", ""),
            "updated_at": datetime.utcnow(),
        }
        collection.update_one({"_id": interaction_id}, {"$set": update_doc})
        return get_interaction(interaction_id) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to update interaction: {e}") from e


def delete_interaction(interaction_id: int | str, db_path: str | None = None) -> bool:
    """Delete an interaction by ID."""
    try:
        collection = get_collection()
        if isinstance(interaction_id, str):
            try:
                interaction_id = ObjectId(interaction_id)
            except Exception:
                return False
        elif isinstance(interaction_id, int):
            try:
                interaction_id = ObjectId(str(interaction_id))
            except Exception:
                return False

        result = collection.delete_one({"_id": interaction_id})
        return result.deleted_count > 0
    except Exception as e:
        raise RuntimeError(f"Failed to delete interaction: {e}") from e

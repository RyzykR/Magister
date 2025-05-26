# app/services.py

import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
print(f"MONGO_URI: {MONGO_URI}")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI not set in environment")

# 1) Async client
_async_client = AsyncIOMotorClient(MONGO_URI)
_async_db = _async_client.get_default_database()
_async_messages_coll = _async_db["messages"]

# 2) Sync client
_sync_client = MongoClient(MONGO_URI)
_sync_db = _sync_client.get_default_database()
_sync_messages_coll = _sync_db["messages"]


def get_async_messages_collection():
    """
    Повертає асинхронну колекцію для викликів у FastAPI-ендпоінтах.
    """
    return _async_messages_coll


def get_sync_messages_collection():
    """
    Повертає синхронну колекцію для використання у Celery-тасках.
    """
    return _sync_messages_coll

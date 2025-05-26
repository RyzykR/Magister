# tests/test_api.py

import os
import pytest
from httpx import AsyncClient

os.environ["MONGO_URI"] = "mongodb://localhost:27017/notification_system_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

from api.main import app
from api.services import _sync_client as mongo_client
from celery_app import celery_app

@pytest.fixture(autouse=True)
def clear_db():
    db = mongo_client.get_default_database()
    db.drop_collection("messages")
    yield
    db.drop_collection("messages")


celery_app.send_task = lambda *args, **kwargs: None

@pytest.mark.asyncio
async def test_create_single_message():
    payload = {
        "service": "auth",
        "level": "error",
        "content": "Token expired",
        "timestamp": "2025-05-25T12:00:00Z"
    }

    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post("/messages", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued_for_analysis"
    assert "id" in data

@pytest.mark.asyncio
async def test_create_multiple_messages():
    samples = [
        {"service": "auth",    "level": "info",     "content": "User login error"},
        {"service": "db",      "level": "warning",  "content": "Query took too long"},
        {"service": "payment", "level": "error",    "content": "Payment gateway timeout"},
        {"service": "cache",   "level": "critical", "content": "Cache node unavailable"},
    ]

    async with AsyncClient(base_url="http://localhost:8000") as client:
        ids = []
        for msg in samples:
            resp = await client.post("/messages", json=msg)
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "queued_for_analysis"
            ids.append(body["id"])


    db = mongo_client.get_default_database()
    count = db["messages"].count_documents({})
    assert count == len(samples)

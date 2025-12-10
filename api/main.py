from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from api.services import get_async_messages_collection
from api.models import MessageIn
from api.stats import build_stats_for_message, fingerprint
from celery_app import celery_app
from ai.tasks import analyze_message

app = FastAPI()

@app.post("/messages")
async def create_message(message: MessageIn):
    messages_collection = get_async_messages_collection()
    doc = message.dict()
    now = datetime.utcnow()
    doc.setdefault("timestamp", now)
    doc["created_at"] = doc.get("timestamp", now)
    doc["fingerprint"] = fingerprint(doc["content"])

    res = await messages_collection.insert_one(doc)
    if not res.acknowledged:
        raise HTTPException(500, "Cannot store message")
    message_id = str(res.inserted_id)

    try:
        stats = await run_in_threadpool(build_stats_for_message, doc["content"])
        await messages_collection.update_one({"_id": res.inserted_id}, {"$set": {"context_stats": stats}})
    except Exception as exc:  # noqa: BLE001
        print(f"[stats] Failed to build stats for message {message_id}: {exc}")

    # responce = analyze_message(message_id)
    celery_app.send_task("ai.tasks.analyze_message", args=[message_id])

    return {"id": message_id, "status": "queued_for_analysis"}

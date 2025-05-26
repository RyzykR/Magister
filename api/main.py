from fastapi import FastAPI, HTTPException
from bson import ObjectId
from api.services import get_async_messages_collection
from api.models import MessageIn
from celery_app import celery_app

app = FastAPI()

@app.post("/messages")
async def create_message(message: MessageIn):
    doc = message.dict()
    res = await get_async_messages_collection().insert_one(doc)
    if not res.acknowledged:
        raise HTTPException(500, "Cannot store message")
    message_id = str(res.inserted_id)

    celery_app.send_task("ai.tasks.analyze_message", args=[message_id])

    return {"id": message_id, "status": "queued_for_analysis"}

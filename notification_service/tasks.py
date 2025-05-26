import os
from datetime import datetime, timedelta
from celery_app import celery_app
from bson import ObjectId
from dotenv import load_dotenv
from api.services import get_sync_messages_collection

load_dotenv()

DISPATCH_INTERVAL = int(os.getenv("DISPATCH_INTERVAL_MINUTES", 5))

messages_collection = get_sync_messages_collection()


@celery_app.task(name="notification_service.tasks.send_message")
def send_message(message_id: str):
    """
    Відправити одне повідомлення за його ID.
    """
    doc = messages_collection.find_one({"_id": ObjectId(message_id)})
    if not doc:
        return {"error": "message not found", "id": message_id}

    # --- (email/SMS/Push) ---
    content = doc.get("content")
    severity = doc.get("analysis", {}).get("label", "unknown")
    print(f"[SEND] ({severity}) {message_id}: {content}")

    messages_collection.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"sent": True, "sent_at": datetime.utcnow()}}
    )

    return {"id": message_id, "sent": True}


@celery_app.task(name="notification_service.tasks.dispatch_non_critical")
def dispatch_non_critical():
    """
    Пакетна відправка всіх неприорітетних повідомлень,
    які ще не відправлені і були зареєстровані до моменту cutoff.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=DISPATCH_INTERVAL)
    cursor = messages_collection.find({
        "analysis.label": {"$ne": "critical"},
        "sent": {"$ne": True},
        "timestamp": {"$lte": cutoff}
    })

    count = 0
    for doc in cursor:
        message_id = str(doc["_id"])
        send_message.apply_async(args=[message_id])
        count += 1

    return {"dispatched_non_critical": count}


def schedule_immediate_if_critical(message_id: str):
    doc = messages_collection.find_one({"_id": ObjectId(message_id)})
    if doc and doc.get("analysis", {}).get("label") == "critical":
        send_message.apply_async(args=[message_id], queue="notification_queue")

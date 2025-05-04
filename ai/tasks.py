from celery_app import celery_app
from api.services import get_sync_messages_collection
from notification_service.tasks import schedule_immediate_if_critical
from ai.bert_model import classifier
from ai.configs import prompt, candidate_labels, hypothesis_template
from bson import ObjectId

@celery_app.task(name="ai.tasks.analyze_message")
def analyze_message(message_id: str):
    print("-"*30)
    print("start analyzing")
    coll = get_sync_messages_collection()
    # 1) Завантажити документ
    doc = coll.find_one({"_id": ObjectId(message_id)})
    if not doc:
        return {"error": "not found"}

    # 2) Проаналізувати content
    result = classifier(
        prompt + doc["content"],
        candidate_labels=candidate_labels,
        hypothesis_template=hypothesis_template
    )
    print(f"Result: {result}")
    # 3) Зберегти результат в полі analysis
    coll.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"analysis": result}}
    )
    schedule_immediate_if_critical(message_id)
    return {"id": message_id, "analysis": result}

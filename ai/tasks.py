import os
from typing import Dict

from bson import ObjectId
from api.services import get_sync_messages_collection
from celery_app import celery_app
from notification_service.tasks import schedule_immediate_if_critical

from ai.bert_model import classifier
from ai.configs import candidate_labels, hypothesis_template, prompt
from ai.openai_client import classify_severity


OPENAI_SYSTEM_PROMPT = (
    "You are an expert Site Reliability Engineer. Classify incidents by severity "
    "and respond with JSON that matches the provided schema."
)


def _classify_with_huggingface(content: str) -> Dict[str, object]:
    raw_result = classifier(
        prompt + content,
        candidate_labels=candidate_labels,
        hypothesis_template=hypothesis_template,
    )

    labels = raw_result.get("labels", [])
    scores = raw_result.get("scores", [])
    score_map = {label: float(score) for label, score in zip(labels, scores)}
    label = labels[0] if labels else "unknown"

    return {
        "label": label,
        "scores": score_map,
        "confidence": score_map.get(label),
        "provider": "huggingface",
        "raw": raw_result,
    }


def _classify_with_openai(content: str) -> Dict[str, object]:
    return classify_severity(
        prompt + content,
        system_prompt=OPENAI_SYSTEM_PROMPT,
        labels=candidate_labels,
    )


def _classify_message(content: str) -> Dict[str, object]:
    provider = os.getenv("AI_PROVIDER", "huggingface").strip().lower()

    if provider == "openai":
        return _classify_with_openai(content)

    return _classify_with_huggingface(content)


@celery_app.task(name="ai.tasks.analyze_message")
def analyze_message(message_id: str):
    print("-"*30)
    print("start analyzing")
    coll = get_sync_messages_collection()
    doc = coll.find_one({"_id": ObjectId(message_id)})
    if not doc:
        return {"error": "not found"}

    try:
        analysis = _classify_message(doc["content"])
    except Exception as exc:  # noqa: BLE001
        analysis = {
            "label": "unknown",
            "error": str(exc),
            "provider": os.getenv("AI_PROVIDER", "huggingface"),
        }

    coll.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"analysis": analysis}}
    )
    schedule_immediate_if_critical(message_id)
    return {"id": message_id, "analysis": analysis}

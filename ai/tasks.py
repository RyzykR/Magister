import os
from typing import Dict

from bson import ObjectId
from api.services import get_sync_messages_collection
from celery_app import celery_app
from notification_service.tasks import schedule_immediate_if_critical

from ai.bert_model import classifier
from ai.configs import candidate_labels, hypothesis_template, prompt, system_prompt
from ai.openai_client import classify_severity as classify_with_openai
from ai.gemini_client import classify_severity as classify_with_gemini

def _select_label(scores: Dict[str, float], *, fallback: str = "unknown") -> str:
    if scores:
        return max(scores.items(), key=lambda item: item[1])[0]
    return fallback


def _classify_with_huggingface(content: str) -> Dict[str, object]:
    raw_result = classifier(
        prompt + content,
        candidate_labels=candidate_labels,
        hypothesis_template=hypothesis_template,
    )

    labels = raw_result.get("labels", [])
    scores = raw_result.get("scores", [])
    score_map = {label: float(score) for label, score in zip(labels, scores)}
    label = _select_label(score_map)

    return {
        "label": label,
        "scores": score_map,
        "confidence": score_map.get(label),
        "provider": "huggingface",
        "raw": raw_result,
    }


def _classify_with_openai(content: str) -> Dict[str, object]:
    response = classify_with_openai(
        prompt + content,
        system_prompt=system_prompt,
        labels=candidate_labels,
    )

    scores = {
        key: float(value)
        for key, value in (response.get("scores") or {}).items()
        if key in candidate_labels
    }
    label = _select_label(scores, fallback=response.get("label", "unknown"))

    return {
        "label": label,
        "scores": scores,
        "confidence": scores.get(label),
        "provider": response.get("provider", "openai"),
        "raw": response.get("raw", response),
    }


def _classify_with_gemini(content: str) -> Dict[str, object]:
    response = classify_with_gemini(
        prompt + content,
        system_prompt=system_prompt,
        labels=candidate_labels,
    )

    scores = {
        key: float(value)
        for key, value in (response.get("scores") or {}).items()
        if key in candidate_labels
    }
    label = _select_label(scores, fallback=response.get("label", "unknown"))

    return {
        "label": label,
        "scores": scores,
        "confidence": scores.get(label),
        "provider": response.get("provider", "gemini"),
        "raw": response.get("raw", response),
    }


def _classify_message(content: str) -> Dict[str, object]:
    provider = os.getenv("AI_PROVIDER", "huggingface").strip().lower()

    if provider == "openai":
        return _classify_with_openai(content)

    if provider == "gemini":
        return _classify_with_gemini(content)

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

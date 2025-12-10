import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from ai.json_utils import extract_json_from_text

load_dotenv()

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set")
        _client = OpenAI(api_key=api_key)
    return _client


def classify_severity(message: str, *, system_prompt: str, labels: List[str]) -> Dict[str, object]:
    """
    Ask the OpenAI Responses API to classify the message and return a structured
    result that mirrors the HuggingFace zero-shot classifier output.
    """
    client = _get_client()

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )

    try:
        data = extract_json_from_text(response.output_text)
    except (IndexError, KeyError, json.JSONDecodeError, ValueError) as exc:
        raise OpenAIError(f"Could not parse response payload: {exc}") from exc

    label = data.get("severity") or data.get("label")
    if not label:
        raise OpenAIError("Response payload is missing `severity` label")

    raw_scores = data.get("scores", {})
    scores: Dict[str, float] = {}
    if isinstance(raw_scores, dict):
        for key, value in raw_scores.items():
            try:
                scores[key] = float(value)
            except (TypeError, ValueError):
                continue

    return {
        "label": label,
        "scores": scores,
        "provider": "openai",
        "raw": response.model_dump(),
    }

import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv()

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """
    Lazily instantiate and cache the OpenAI client so repeated calls reuse the
    same authenticated session.
    """
    global _client

    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set")

        _client = OpenAI(api_key=api_key)

    return _client


def _build_response_schema(labels: List[str]) -> Dict[str, object]:
    """
    Compose a JSON schema that forces the model to return a severity label and a
    numerical score for each candidate label.
    """
    label_properties = {
        label: {"type": "number", "minimum": 0, "maximum": 1} for label in labels
    }

    return {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": labels},
            "scores": {
                "type": "object",
                "properties": label_properties,
                "required": labels,
                "additionalProperties": False,
            },
        },
        "required": ["label", "scores"],
        "additionalProperties": False,
    }


def classify_severity(message: str, *, system_prompt: str, labels: List[str]) -> Dict[str, object]:
    """
    Ask the OpenAI Responses API to classify the provided message based on the
    supplied instructions and candidate labels.
    """
    client = _get_client()

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "severity_classification",
                "schema": _build_response_schema(labels),
            },
        },
    )

    try:
        # The Responses API returns JSON in a text block that matches the schema.
        payload = response.output[0].content[0].text
        data = json.loads(payload)
    except (IndexError, KeyError, json.JSONDecodeError) as exc:
        raise OpenAIError(f"Could not parse response payload: {exc}") from exc

    scores = {
        label: float(data["scores"].get(label, 0))
        for label in labels
    }
    label = data["label"]

    return {
        "label": label,
        "scores": scores,
        "confidence": scores.get(label),
        "provider": "openai",
        "raw": response.model_dump(),
    }

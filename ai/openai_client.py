import ast
import json
import os
import re

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
    )

    try:
        data = extract_json_from_text(response.output_text)
    except (IndexError, KeyError, json.JSONDecodeError) as exc:
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


def extract_json_from_text(payload):
    """
    Приймає рядок/байти з можливими markdown-фенсами і повертає dict/list.
    Підтримує:
      - ```json ... ```
      - просто текст з JSON усередині
    Кидає ValueError, якщо JSON не знайдено/не парситься.
    """
    if payload is None:
        raise ValueError("Empty payload")

    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")

    if not isinstance(payload, str):
        # можливо це вже dict/list
        return payload

    s = payload.strip()

    # зняти початкові/кінцеві трійні бектики з опціональною мовою
    if s.startswith("```"):
        # прибрати початок ```json\n або ```\n
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        # прибрати фінальні ```
        s = re.sub(r"\n```$", "", s).strip()

    # знайти перший JSON-об'єкт або масив
    m = re.search(r"(\{.*\}|\[.*\])", s, flags=re.S)
    if m:
        s = m.group(1)

    # основна спроба
    try:
        return json.loads(s)
    except Exception:
        pass

    # обережний фолбек: ast.literal_eval для випадків з одинарними лапками
    try:
        py_obj = ast.literal_eval(s)
        # конвертуємо у JSON-сумісний тип (dict/list/str/num/None/bool)
        json.dumps(py_obj)  # перевірка серіалізації
        return py_obj
    except Exception as e:
        raise ValueError(f"Cannot parse JSON from payload: {e}\nRaw: {payload!r}")

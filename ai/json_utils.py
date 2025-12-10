import ast
import json
import re
from typing import Any


def extract_json_from_text(payload: Any):
    """
    Normalize model responses that may contain JSON snippets inside Markdown code
    fences or plain text. Returns a Python dict/list parsed from the detected JSON
    object, or raises ValueError if parsing fails.
    """
    if payload is None:
        raise ValueError("Empty payload")

    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")

    if not isinstance(payload, str):
        return payload

    s = payload.strip()

    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        s = re.sub(r"\n```$", "", s).strip()

    match = re.search(r"(\{.*\}|\[.*\])", s, flags=re.S)
    if match:
        s = match.group(1)

    try:
        return json.loads(s)
    except Exception:
        pass

    try:
        python_obj = ast.literal_eval(s)
        json.dumps(python_obj)
        return python_obj
    except Exception as exc:
        raise ValueError(f"Cannot parse JSON from payload: {exc}\nRaw: {payload!r}")

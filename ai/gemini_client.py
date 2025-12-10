import os
import time
from typing import Dict, List, Optional

import google.generativeai as genai
from dotenv import load_dotenv

from ai.json_utils import extract_json_from_text

load_dotenv()

_model: Optional[genai.GenerativeModel] = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        _model = genai.GenerativeModel(model_name)
    return _model


def classify_severity(message: str, *, system_prompt: str, labels: List[str]) -> Dict[str, object]:
    """
    Call Gemini with instructions to return JSON containing the severity label and
    optional per-label scores.
    """
    model = _get_model()
    prompt = (
        f"{system_prompt}\n\n"
        "Respond with a JSON object: {\"severity\": <label>, \"scores\": {<label>: <score>}}. "
        f"The severity must be one of: {', '.join(labels)}.\n\n"
        f"Message:\n{message}"
    )

    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                },
            )
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(60)
    else:  # pragma: no cover - defensive
        raise last_error or RuntimeError("Gemini call failed without exception")

    try:
        data = extract_json_from_text(response.text)
    except ValueError as exc:
        raise RuntimeError(f"Gemini response parsing failed: {exc}") from exc

    label = data.get("severity") or data.get("label")
    if not label:
        raise RuntimeError("Gemini response is missing `severity`")

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
        "provider": "gemini",
        "raw": response.to_dict() if hasattr(response, "to_dict") else response,
    }

"""Estimate notification reduction using the real notification logic.

Usage:
    python tests/efficiency_metrics.py [N]

N defaults to 20 and represents how many rows to take from ``data_set.csv``.
For each row we classify the message with the same AI pipeline that powers the
app, then apply the notification rules from ``notification_service``:

* ``critical`` incidents trigger every occurrence immediately
* other severities are queued and dispatched in batches, so only one
  notification goes out within the sampling window

The script prints how many notifications would have been sent with and without
the app and the reduction ratio (with / without).
"""

from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

try:
    from dotenv import load_dotenv
except Exception:  # noqa: BLE001
    load_dotenv = lambda *args, **kwargs: False  # type: ignore


WARNINGS_EMITTED: Dict[str, bool] = {}


def _warn_once(key: str, message: str) -> None:
    if not WARNINGS_EMITTED.get(key):
        print(message)
        WARNINGS_EMITTED[key] = True


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env", override=False)

from ai.configs import candidate_labels, hypothesis_template, prompt

try:
    from ai.openai_client import classify_severity as openai_classify
except Exception as exc:  # noqa: BLE001
    openai_classify = None
    OPENAI_IMPORT_ERROR = exc
else:  # pragma: no cover
    OPENAI_IMPORT_ERROR = None

try:
    from ai.bert_model import classifier as hf_classifier
except Exception as exc:  # noqa: BLE001
    hf_classifier = None
    HF_IMPORT_ERROR = exc
else:  # pragma: no cover - executed when transformers are installed
    HF_IMPORT_ERROR = None

DATASET_PATH = ROOT_DIR / "data_set.csv"


def load_rows(limit: int) -> Iterable[dict]:
    with DATASET_PATH.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for index, row in enumerate(reader):
            if index >= limit:
                break
            yield row


def _to_int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _format_message(row: Dict[str, str]) -> str:
    service = row.get("service", "unknown").strip() or "unknown"
    text = row.get("text", "").strip()
    return f"[{service}] {text}"


def _select_label(scores: Dict[str, float], fallback: str = "unknown") -> str:
    return max(scores.items(), key=lambda item: item[1])[0] if scores else fallback


def _severity_from_dataset(row: Dict[str, str]) -> str:
    label = (row.get("expected_label") or "unknown").strip().lower()
    return label if label in candidate_labels else "unknown"


def classify_row(row: Dict[str, str]) -> str:
    message = _format_message(row)
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
    if provider == "openai":
        if openai_classify is None:
            if OPENAI_IMPORT_ERROR:
                _warn_once("openai_missing", f"[warn] OpenAI client unavailable: {OPENAI_IMPORT_ERROR}. Using dataset label.")
            return _severity_from_dataset(row)

        try:
            response = openai_classify(
                prompt + message,
                system_prompt=(
                    "You are an expert Site Reliability Engineer. Classify incidents "
                    "by severity and return JSON with a `severity` field."
                ),
                labels=candidate_labels,
            )
            scores = {
                label: float(value)
                for label, value in (response.get("scores") or {}).items()
                if label in candidate_labels
            }
            return _select_label(scores, fallback=response.get("label", "unknown"))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] OpenAI classification failed: {exc}. Using dataset label.")
            return _severity_from_dataset(row)

    if hf_classifier is None:
        if HF_IMPORT_ERROR:
            _warn_once("hf_missing", f"[warn] HuggingFace pipeline unavailable: {HF_IMPORT_ERROR}. Using dataset label.")
        return _severity_from_dataset(row)

    try:
        hf_result = hf_classifier(
            prompt + message,
            candidate_labels=candidate_labels,
            hypothesis_template=hypothesis_template,
        )
    except Exception as exc:  # noqa: BLE001
        _warn_once("hf_failed", f"[warn] HuggingFace classification failed: {exc}. Using dataset label.")
        return _severity_from_dataset(row)

    labels = hf_result.get("labels", [])
    scores = hf_result.get("scores", [])
    mapping = {label: float(score) for label, score in zip(labels, scores)}
    return _select_label(mapping)


def compute_counts(rows: Sequence[Dict[str, str]]):
    total_with = 0
    total_without = 0
    severity_distribution: Counter[str] = Counter()

    for row in rows:
        severity = classify_row(row)
        severity_distribution[severity] += 1

        without = _to_int(row.get("count_24h"))
        total_without += without

        if severity == "critical":
            with_app = without
        else:
            with_app = 1 if without > 0 else 0

        total_with += with_app

    ratio = (total_with / total_without) if total_without else 0.0
    return total_with, total_without, ratio, severity_distribution


def main(limit: int = 20) -> None:
    rows = list(load_rows(limit))
    total_with, total_without, ratio, severity_distribution = compute_counts(rows)

    print(f"Dataset sample size: {len(rows)} rows")
    print("Severity distribution:")
    for severity, count in severity_distribution.items():
        print(f"  - {severity}: {count}")
    print(f"Notifications with app: {total_with}")
    print(f"Notifications without app: {total_without}")
    reduction = (1 - ratio) * 100 if total_without else 0.0
    print(f"Efficiency ratio (with/without): {ratio:.2f} (reduction {reduction:.1f}% )")


if __name__ == "__main__":
    user_limit = 20
    if len(sys.argv) > 1:
        try:
            user_limit = max(1, int(sys.argv[1]))
        except ValueError:
            print(f"Invalid limit {sys.argv[1]}, defaulting to 20")
    main(user_limit)

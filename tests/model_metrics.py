"""Utility script for evaluating the severity classifier on the CSV dataset.

Run with:
    python tests/model_metrics.py

The script reuses the same classification pipeline that the API relies on,
so the `AI_PROVIDER`/`AI_MODEL` environment variables continue to work.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai.configs import candidate_labels
from ai.tasks import _classify_message

DATASET_PATH = ROOT_DIR / "data_set.csv"


@dataclass
class LabelMetrics:
    precision: float
    recall: float
    f1: float
    support: int


def load_dataset(path: Path = DATASET_PATH) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader]


def _format_message(row: Dict[str, str]) -> str:
    service = row.get("service", "unknown").strip() or "unknown"
    text = row.get("text", "").strip()
    count_1h = row.get("count_1h", "").strip()
    count_24h = row.get("count_24h", "").strip()

    # Enrich the free-form text with context numbers so the classifier sees
    # something closer to what the API stores inside the `content` field.
    context_bits = []
    if count_1h:
        context_bits.append(f"1h events: {count_1h}")
    if count_24h:
        context_bits.append(f"24h events: {count_24h}")

    context = f" ({', '.join(context_bits)})" if context_bits else ""
    return f"[{service}] {text}{context}"


def classify_rows(rows: Sequence[Dict[str, str]]) -> Tuple[List[str], List[str]]:
    y_true: List[str] = []
    y_pred: List[str] = []

    for row in rows:
        message = _format_message(row)
        expected = (row.get("expected_label") or "unknown").strip().lower()
        try:
            prediction = _classify_message(message).get("label", "unknown")
        except Exception as exc:  # noqa: BLE001
            raise exc
            print(f"[warn] failed to classify row {row}: {exc}")
            prediction = "unknown"

        y_true.append(expected)
        y_pred.append(prediction)

    return y_true, y_pred


def _safe_div(num: float, denom: float) -> float:
    return num / denom if denom else 0.0


def compute_metrics(labels: Iterable[str], y_true: Sequence[str], y_pred: Sequence[str]) -> Dict[str, LabelMetrics]:
    metrics: Dict[str, LabelMetrics] = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)

        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)

        support = sum(1 for value in y_true if value == label)
        metrics[label] = LabelMetrics(precision, recall, f1, support)

    return metrics


def format_report(metrics: Dict[str, LabelMetrics], y_true: Sequence[str]) -> str:
    header = f"{'label':<10} {'precision':>10} {'recall':>8} {'f1':>8} {'support':>8}"
    lines = [header, "-" * len(header)]

    macro_p = macro_r = macro_f = 0.0
    for label in candidate_labels:
        label_metrics = metrics[label]
        macro_p += label_metrics.precision
        macro_r += label_metrics.recall
        macro_f += label_metrics.f1

        lines.append(
            f"{label:<10} {label_metrics.precision:>10.2f} {label_metrics.recall:>8.2f} {label_metrics.f1:>8.2f} {label_metrics.support:>8}"
        )

    n_labels = len(candidate_labels)
    macro_line = f"{'macro_avg':<10} {macro_p / n_labels:>10.2f} {macro_r / n_labels:>8.2f} {macro_f / n_labels:>8.2f} {len(y_true):>8}"
    lines.append("-" * len(header))
    lines.append(macro_line)

    return "\n".join(lines)


def main() -> None:
    rows = load_dataset()
    y_true, y_pred = classify_rows(rows)
    per_label_metrics = compute_metrics(candidate_labels, y_true, y_pred)

    print(format_report(per_label_metrics, y_true))


if __name__ == "__main__":
    main()

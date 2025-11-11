# ai/context_stats.py
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import hashlib, re
from pymongo.collection import Collection
import numpy as np
from api.services import get_sync_messages_collection

TIME_WINDOWS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_UUID_IP = re.compile(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d{1,3}(?:\.\d{1,3}){3})\b", re.I)
_NUMBERS = re.compile(r"\b\d+\b")

def normalize(s: str) -> str:
    s = s.lower()
    s = _UUID_IP.sub("<id>", s)
    s = _NUMBERS.sub("<n>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def fingerprint(s: str) -> str:
    return hashlib.sha1(normalize(s).encode("utf-8")).hexdigest()

def build_stats_for_message(
    content: str,
    now: datetime | None = None,
    embedding: List[float] | None = None,
    limit_examples: int = 3,
) -> Dict[str, Any]:
    now = now or datetime.utcnow()
    collection: Collection = get_sync_messages_collection()

    fp = fingerprint(content)

    stats: Dict[str, Any] = {"windows": {}, "last_seen_at": None}

    for key, delta in TIME_WINDOWS.items():
        since = now - delta
        cur = collection.find(
            {"fingerprint": fp, "created_at": {"$gte": since, "$lte": now}},
            {"analysis.label": 1, "service": 1, "component": 1, "resolved_at": 1, "content": 1, "created_at": 1},
        )

        count = 0
        labels: Dict[str, int] = {}
        services: Dict[str, int] = {}
        components: Dict[str, int] = {}
        ttrs: List[float] = []
        examples: List[Tuple[str, str]] = []
        last_seen = stats["last_seen_at"]

        for d in cur:
            count += 1
            lbl = (d.get("analysis") or {}).get("label")
            if lbl: labels[lbl] = labels.get(lbl, 0) + 1
            svc = d.get("service"); cmp = d.get("component")
            if svc: services[svc] = services.get(svc, 0) + 1
            if cmp: components[cmp] = components.get(cmp, 0) + 1

            ca = d.get("created_at")
            if ca and (last_seen is None or ca > last_seen):
                last_seen = ca

            ra = d.get("resolved_at")
            if ca and ra and isinstance(ca, datetime) and isinstance(ra, datetime) and ra >= ca:
                ttrs.append((ra - ca).total_seconds())

            if len(examples) < limit_examples:
                cid = str(d.get("_id"))
                fragment = (d.get("content") or "")[:200]
                examples.append((cid, fragment))

        if last_seen and (stats["last_seen_at"] is None or last_seen > stats["last_seen_at"]):
            stats["last_seen_at"] = last_seen

        stats["windows"][key] = {
            "count": count,
            "labels_distribution": labels,
            "top_services": sorted(services.items(), key=lambda x: x[1], reverse=True)[:3],
            "top_components": sorted(components.items(), key=lambda x: x[1], reverse=True)[:3],
            "median_ttr_sec": float(np.median(ttrs)) if ttrs else None,
            "examples": [{"id": eid, "fragment": txt} for eid, txt in examples],
        }

    return stats

def pack_prompt_snippet(stats: Dict[str, Any]) -> str:
    win = stats.get("windows", {}).get("24h", {})
    cnt = win.get("count", 0)
    labels = win.get("labels_distribution", {})
    last_seen = stats.get("last_seen_at")
    last_seen_str = last_seen.isoformat() if last_seen else "n/a"
    return (
        f"Historical stats (24h): count={cnt}, labels={labels}, last_seen={last_seen_str}. "
        f"Other windows: 1h={stats['windows'].get('1h', {}).get('count', 0)}, "
        f"7d={stats['windows'].get('7d', {}).get('count', 0)}, "
        f"30d={stats['windows'].get('30d', {}).get('count', 0)}."
    )

"""Evidence-first execution records for projects, training and business work."""
from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "records.json"
VALID_STATS = {"CON", "INT", "STR", "DEX", "DISC", "WILL", "SPIRIT"}
VALID_TYPES = {"project", "experiment", "practice", "training", "business", "creative", "service", "other"}

def _load() -> dict[str, Any]:
    if not LOG_PATH.exists(): return {"schema_version": 1, "records": []}
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))

def _save(data: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    tmp.replace(LOG_PATH)

def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list): return []
    return [str(item).strip() for item in value if str(item).strip()]

def validate(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title", "")).strip()
    if not title: raise ValueError("title is required")
    activity_type = str(payload.get("activity_type", "other")).strip().lower()
    if activity_type not in VALID_TYPES: raise ValueError(f"unsupported activity_type: {activity_type}")
    stats = [s.upper() for s in _clean_list(payload.get("main_stats"))]
    invalid = [s for s in stats if s not in VALID_STATS]
    if invalid: raise ValueError(f"unknown main stats: {', '.join(invalid)}")
    try: duration = max(0, int(payload.get("duration_minutes", 0) or 0))
    except (TypeError, ValueError): raise ValueError("duration_minutes must be an integer")
    evidence = _clean_list(payload.get("evidence"))
    status = str(payload.get("status", "completed")).strip().lower()
    if status not in {"planned", "in_progress", "completed", "verified"}: raise ValueError("invalid status")
    return {
      "title": title, "activity_type": activity_type, "occurred_at": str(payload.get("occurred_at") or datetime.now(timezone.utc).isoformat()),
      "main_stats": stats, "capabilities": _clean_list(payload.get("capabilities")), "concepts": _clean_list(payload.get("concepts")),
      "duration_minutes": duration, "evidence": evidence, "result": str(payload.get("result", "")).strip(),
      "reflection": str(payload.get("reflection", "")).strip(), "status": status, "source": str(payload.get("source", "manual")).strip() or "manual"
    }

def create_execution(payload: dict[str, Any]) -> dict[str, Any]:
    record = validate(payload)
    fingerprint = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    data = _load()
    for existing in data["records"]:
        if existing.get("fingerprint") == fingerprint: return {**existing, "duplicate": True}
    record.update({"id": str(uuid.uuid4()), "fingerprint": fingerprint, "created_at": datetime.now(timezone.utc).isoformat()})
    data["records"].append(record); _save(data); return record

def list_executions(limit: int = 100) -> list[dict[str, Any]]:
    return list(reversed(_load().get("records", [])))[0:max(1, limit)]

def execution_summary() -> dict[str, Any]:
    records = _load().get("records", [])
    completed = [r for r in records if r.get("status") in {"completed", "verified"}]
    by_type: dict[str, int] = {}; by_stat: dict[str, int] = {}
    for r in completed:
        by_type[r.get("activity_type", "other")] = by_type.get(r.get("activity_type", "other"), 0)+1
        for stat in r.get("main_stats", []): by_stat[stat] = by_stat.get(stat, 0)+1
    return {"total": len(records), "completed": len(completed), "minutes": sum(int(r.get("duration_minutes",0)) for r in completed), "by_type": by_type, "by_stat": by_stat}

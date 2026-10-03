"""Evidence-first flight practice log - real and simulated flight sessions.

Sibling to operator_core/execution, but a flight is a different shape of
thing than a project completion: it's frequent, it varies in length, and
you log it *because* you did it, not because you finished something. XP
here is duration-based, the same calculate_hourly_xp() rate Task Hub uses
for logged practice hours - not scope-sized like Execution Hub's flat
small/medium/large. See modules/operator_flights.py's module docstring
for the fuller reasoning (this hub exists specifically because Execution
Hub's own docstring already ruled "practice" out of that hub once).

kind ("real" | "simulated") is a first-class field, not something to
infer from a title - the whole point of tracking it separately.

This module stays dependency-light on purpose (no skill-tree/XP-engine
imports) so it can be reused or tested standalone, same convention as
operator_core/execution/service.py. The Flask layer (modules/operator_flights.py)
resolves each picked capability against the real skill tree, computes
duration-based XP, resolves evidence against the media root, and passes
the already-resolved competency_id list and XP award in - this module
just validates shape and persists.
"""
from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone, date as date_cls
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "records.json"
VALID_KINDS = {"real", "simulated"}


def _load() -> dict[str, Any]:
    if not LOG_PATH.exists():
        return {"schema_version": 1, "records": []}
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def _save(data: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(LOG_PATH)


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("kind", "")).strip().lower()
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(sorted(VALID_KINDS))}")

    aircraft = str(payload.get("aircraft", "")).strip()
    if not aircraft:
        raise ValueError("aircraft is required")

    try:
        duration_minutes = float(payload.get("duration_minutes", 0))
    except (TypeError, ValueError):
        raise ValueError("duration_minutes must be a number")
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be greater than 0")
    if duration_minutes > 24 * 60:
        raise ValueError("duration_minutes looks too large for a single flight - split it into separate sessions")

    date_raw = str(payload.get("date", "")).strip()
    if date_raw:
        try:
            date_cls.fromisoformat(date_raw)
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD")
    flown_on = date_raw or date_cls.today().isoformat()

    capabilities = _clean_list(payload.get("capabilities"))
    if not capabilities:
        raise ValueError("at least one capability is required")

    xp_awards = payload.get("xp_awards")
    if not isinstance(xp_awards, list) or not xp_awards:
        raise ValueError("xp_awards is required - resolve and award XP before creating the record")
    try:
        xp_total = max(0, int(payload.get("xp_total", 0) or 0))
    except (TypeError, ValueError):
        raise ValueError("xp_total must be an integer")

    evidence = _clean_list(payload.get("evidence"))
    notes = str(payload.get("notes", "")).strip()

    return {
        "kind": kind,
        "aircraft": aircraft,
        "date": flown_on,
        "occurred_at": str(payload.get("occurred_at") or datetime.now(timezone.utc).isoformat()),
        "duration_minutes": duration_minutes,
        "capabilities": capabilities,
        "xp_total": xp_total,
        "xp_awards": xp_awards,
        "evidence": evidence,
        "notes": notes,
        "source": str(payload.get("source", "manual")).strip() or "manual",
    }


def build_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and fingerprint a record WITHOUT persisting it or triggering
    any side effect - same reasoning as execution/service.py's build_record:
    callers that award XP check find_by_fingerprint() first and only award
    XP if it comes back None, so a resubmitted duplicate can't award twice.
    """
    record = validate(payload)
    fingerprint_basis = {
        "kind": record["kind"],
        "aircraft": record["aircraft"],
        "date": record["date"],
        "duration_minutes": record["duration_minutes"],
        "capabilities": sorted(record["capabilities"]),
        "evidence": sorted(record["evidence"]),
    }
    record["fingerprint"] = hashlib.sha256(json.dumps(fingerprint_basis, sort_keys=True).encode()).hexdigest()
    return record


def find_by_fingerprint(fingerprint: str) -> dict[str, Any] | None:
    for existing in _load().get("records", []):
        if existing.get("fingerprint") == fingerprint:
            return existing
    return None


def persist_flight(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record.setdefault("id", str(uuid.uuid4()))
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    data = _load()
    data["records"].append(record)
    _save(data)
    return record


def list_flights(limit: int = 100) -> list[dict[str, Any]]:
    records = list(_load().get("records", []))
    records.sort(key=lambda r: (r.get("date", ""), r.get("created_at", "")), reverse=True)
    return records[0:max(1, limit)]


def flight_summary() -> dict[str, Any]:
    records = _load().get("records", [])
    real = [r for r in records if r.get("kind") == "real"]
    sim = [r for r in records if r.get("kind") == "simulated"]

    real_minutes = sum(float(r.get("duration_minutes", 0)) for r in real)
    sim_minutes = sum(float(r.get("duration_minutes", 0)) for r in sim)
    total_xp = sum(int(r.get("xp_total", 0)) for r in records)

    last_real_date = max((r.get("date", "") for r in real), default=None)
    days_since_real = None
    if last_real_date:
        try:
            days_since_real = (date_cls.today() - date_cls.fromisoformat(last_real_date)).days
        except ValueError:
            days_since_real = None

    return {
        "total": len(records),
        "real_count": len(real),
        "sim_count": len(sim),
        "real_minutes": real_minutes,
        "sim_minutes": sim_minutes,
        "total_xp": total_xp,
        "last_real_date": last_real_date,
        "days_since_real": days_since_real,
    }

"""Evidence-first execution records for finished projects and experiments.

Narrowed scope (was: project/experiment/practice/training/business/creative/
service/other with a free-text main_stats/capabilities pair). Practice moved
to Task Hub (hours against a capability), training stays in Fitness Hub,
business and creative both already have a real home in Journal (see
journal/engine/xp_defaults.py) - duplicating any of those here just splits
the same kind of entry across two places with no rule for which one to use.
That leaves exactly two things worth a dedicated "I finished this" record:
a project (something built) and an experiment (something tested).

XP is driven by scope (small/medium/large), not activity_type and not
hours. activity_type stays a pure category label - it decides which stat
card/log tag a completion counts toward, nothing else. Hours was tried
first as the XP driver and dropped: it's self-reported and trivially
inflated, and it double-counts against Task Hub, which already awards XP
for hours logged against a capability during the week this project was
being built. Scope is a one-time, honest choice made at completion time
instead - can't be padded by leaving a session open.

This module stays dependency-light on purpose (no skill-tree/XP-engine
imports) so it can be reused or tested standalone. The Flask layer
(modules/operator_execution.py) is what resolves each picked capability
against the real skill tree, computes the flat completion XP from scope,
and passes the already-resolved competency_id list and XP award in - this
module just validates shape and persists.
"""
from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "records.json"
VALID_TYPES = {"project", "experiment"}
VALID_SCOPES = {"small", "medium", "large"}

def _load() -> dict[str, Any]:
    if not LOG_PATH.exists(): return {"schema_version": 2, "records": []}
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))

def _save(data: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8", newline="\n")
    tmp.replace(LOG_PATH)

def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list): return []
    return [str(item).strip() for item in value if str(item).strip()]

def validate(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title", "")).strip()
    if not title: raise ValueError("title is required")
    activity_type = str(payload.get("activity_type", "")).strip().lower()
    if activity_type not in VALID_TYPES: raise ValueError(f"activity_type must be one of: {', '.join(sorted(VALID_TYPES))}")
    scope = str(payload.get("scope", "")).strip().lower()
    if scope not in VALID_SCOPES: raise ValueError(f"scope must be one of: {', '.join(sorted(VALID_SCOPES))}")

    capabilities = _clean_list(payload.get("capabilities"))
    if not capabilities: raise ValueError("at least one capability is required")

    xp_awards = payload.get("xp_awards")
    if not isinstance(xp_awards, list) or not xp_awards:
        raise ValueError("xp_awards is required - resolve and award XP before creating the record")
    try:
        xp_total = max(0, int(payload.get("xp_total", 0) or 0))
    except (TypeError, ValueError):
        raise ValueError("xp_total must be an integer")

    evidence = _clean_list(payload.get("evidence"))
    status = str(payload.get("status", "completed")).strip().lower()
    if status not in {"planned", "in_progress", "completed", "verified"}: raise ValueError("invalid status")

    return {
      "title": title, "activity_type": activity_type, "scope": scope,
      "occurred_at": str(payload.get("occurred_at") or datetime.now(timezone.utc).isoformat()),
      "capabilities": capabilities, "xp_total": xp_total, "xp_awards": xp_awards,
      "evidence": evidence, "result": str(payload.get("result", "")).strip(),
      "reflection": str(payload.get("reflection", "")).strip(), "status": status, "source": str(payload.get("source", "manual")).strip() or "manual"
    }

def build_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and fingerprint a record WITHOUT persisting it or triggering
    any side effect. Callers that award XP (modules/operator_execution.py)
    call this first, check find_by_fingerprint(), and only award XP if it
    comes back None - otherwise a resubmitted duplicate would award XP
    again even though the evidence record itself gets deduplicated.

    The fingerprint is deliberately computed from a stable subset of fields,
    not the whole record - validate() defaults occurred_at to "now" when the
    caller doesn't supply one, so hashing the full record would give every
    submission (including an honest-to-god duplicate double-click or a
    retried request) its own unique timestamp and its own unique fingerprint,
    silently defeating the entire point of this dedup step.
    """
    record = validate(payload)
    fingerprint_basis = {
        "title": record["title"],
        "activity_type": record["activity_type"],
        "scope": record["scope"],
        "capabilities": sorted(record["capabilities"]),
        "xp_total": record["xp_total"],
        "evidence": sorted(record["evidence"]),
        "reflection": record["reflection"],
    }
    record["fingerprint"] = hashlib.sha256(json.dumps(fingerprint_basis, sort_keys=True).encode()).hexdigest()
    return record

def find_by_fingerprint(fingerprint: str) -> dict[str, Any] | None:
    for existing in _load().get("records", []):
        if existing.get("fingerprint") == fingerprint:
            return existing
    return None

def persist_execution(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record.setdefault("id", str(uuid.uuid4()))
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    data = _load()
    data["records"].append(record)
    _save(data)
    return record

def create_execution(payload: dict[str, Any]) -> dict[str, Any]:
    """One-shot convenience wrapper (used by cli.py, where the caller has
    already computed xp_awards itself and there's no separate XP-awarding
    side effect to guard against here)."""
    record = build_record(payload)
    existing = find_by_fingerprint(record["fingerprint"])
    if existing: return {**existing, "duplicate": True}
    return persist_execution(record)

def list_executions(limit: int = 100) -> list[dict[str, Any]]:
    return list(reversed(_load().get("records", [])))[0:max(1, limit)]

def execution_summary() -> dict[str, Any]:
    records = _load().get("records", [])
    completed = [r for r in records if r.get("status") in {"completed", "verified"}]
    by_type: dict[str, int] = {}
    total_xp = 0
    for r in completed:
        by_type[r.get("activity_type", "other")] = by_type.get(r.get("activity_type", "other"), 0)+1
        total_xp += int(r.get("xp_total", 0))
    return {"total": len(records), "completed": len(completed), "total_xp": total_xp, "by_type": by_type}

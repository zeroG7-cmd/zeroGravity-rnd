"""Operator Zero completion history v3.0."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_PATH = Path("learning/operator/history.json")

def load_history() -> dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {"schema_version": 3, "events": []}
    with HISTORY_PATH.open("r", encoding="utf-8") as file:
        history = json.load(file)
    history.setdefault("schema_version", 3)
    history.setdefault("events", [])
    return history

def save_history(history: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = HISTORY_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(history, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(HISTORY_PATH)

def completion_exists(history: dict[str, Any], track_id: str, unit_id: str) -> bool:
    return any(event.get("track_id") == track_id and event.get("unit_id") == unit_id and event.get("event_type") == "unit_completed" for event in history.get("events", []) if isinstance(event, dict))

def record_completion(metadata: dict[str, Any], unit: dict[str, Any], xp_award: int,
                      xp_distribution: list[dict[str, Any]] | None = None,
                      concept_distribution: list[dict[str, Any]] | None = None,
                      mapping_confidence: str = "low",
                      completion_source: str | None = None) -> bool:
    history = load_history()
    track_id = str(metadata.get("id", "unknown_track")); unit_id = str(unit.get("id", "unknown_unit"))
    if completion_exists(history, track_id, unit_id): return False
    event = {
        "event_type": "unit_completed", "track_id": track_id, "track_title": metadata.get("title"),
        "stat": metadata.get("stat"), "hierarchy": metadata.get("hierarchy", []), "skill": metadata.get("skill"),
        "unit_id": unit_id, "unit_title": unit.get("title"), "unit_type": unit.get("source_type", "manual"),
        "completion_source": completion_source or unit.get("completion_source", "tracker"),
        "provider": unit.get("provider", metadata.get("provider")), "external_id": unit.get("external_id"),
        "xp_awarded": int(xp_award), "xp_distribution": xp_distribution or [],
        "concept_distribution": concept_distribution or [], "mapping_confidence": mapping_confidence or "low",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    history["schema_version"] = 3; history.setdefault("events", []).append(event); save_history(history); return True

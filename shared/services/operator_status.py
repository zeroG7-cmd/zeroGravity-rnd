from __future__ import annotations
from typing import Any
from shared.config.paths import OPERATOR_CAPABILITIES, OPERATOR_HUBS
from shared.libraries.json_store import load_json

def get_operator_status() -> dict[str, Any]:
    stats = load_json(
        OPERATOR_HUBS / "learning" / "stats" / "learning_stats.json",
        {},
    ) or {}
    capabilities = load_json(
        OPERATOR_CAPABILITIES / "competencies.json",
        {},
    ) or {}
    if isinstance(capabilities, dict):
        competency_payload = capabilities.get("competencies", capabilities)
        competency_count = len(competency_payload)
    else:
        competency_count = 0
    return {
        "operator_level": stats.get("level", 0),
        "total_xp": stats.get("total_xp", 0),
        "competency_count": competency_count,
    }

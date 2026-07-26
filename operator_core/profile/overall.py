"""Operator 'Overall' rating.

A straight average across every main stat's level -- unweighted, on
purpose (every stat pulls its own equal share).

Reads from learning_stats.json (built by learning/engine/stats.py),
NOT from operator_core/profile/stats.json. This matters: tracker.py
routes every learning-track completion through
stats.update_operator_competencies, which updates competencies.json and
regenerates learning_stats.json -- it never touches
operator_core/profile. So learning_stats.json is the file that
actually reflects real activity; the flat profile stats file only
moves for things explicitly tagged target_type == "stat" (e.g. a
manually-targeted journal entry), which is nearly none of your
actual XP. Reading the profile file here would have shown Overall
stuck at 0 regardless of how much Python or CAD you completed.

Each main stat's own root-level ``average_level`` (in learning_stats.json)
is already a recursive average of everything beneath it -- domains
average their sub-domains, sub-domains average their capabilities. This
module only takes the final step: averaging the seven main stats
against each other. Because capability levels get more expensive per
level (see progression.py's curve), spreading effort across capabilities
and stats raises this number more than concentrating it in one --
balance is rewarded structurally, the same reasoning as before, just
one layer up.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config.paths import OPERATOR_HUBS

LEARNING_STATS_PATH = OPERATOR_HUBS / "learning" / "stats" / "learning_stats.json"


def _load_learning_stats() -> dict[str, Any]:
    if not LEARNING_STATS_PATH.exists():
        return {"stats": {}}
    return json.loads(LEARNING_STATS_PATH.read_text(encoding="utf-8"))


def calculate_overall(learning_stats: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the Operator's Overall rating and the per-stat averages behind it.

    Pass ``learning_stats`` explicitly (e.g. in tests) to avoid touching
    disk; otherwise this reads learning_stats.json itself.
    """
    document = learning_stats if learning_stats is not None else _load_learning_stats()
    stats = document.get("stats", {})
    if not stats:
        return {"overall": 0.0, "stat_averages": {}}

    stat_averages = {
        stat_id: float(stat.get("average_level", 0.0))
        for stat_id, stat in stats.items()
    }

    overall = round(sum(stat_averages.values()) / len(stat_averages), 2)

    return {"overall": overall, "stat_averages": stat_averages}

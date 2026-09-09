"""Recompute STR/CON/DISC branches of learning_stats.json after a fitness log.

learning_stats.json is, despite its name, the single file the Zero Command
System dashboard reads for every main stat (see
`operator_core/hubs/learning/stats/learning_stats.json` and
`operator_core/profile/overall.py`'s docstring, which explains why: the
canonical `operator_core/profile` module isn't wired up to real activity yet,
so this file is what's actually live). This module only ever touches the
branches fitness habits live in - STR's "Muscular Strength" tree, CON's
"Endurance" and "Health Management" trees, and DISC's "Consistency" tree -
and the shared top-level total_xp/level fields. It never touches INT or
anything else learning owns.

Usage::

    from fitness.engine.stats import sync_and_recompute
    sync_and_recompute(["str.muscular_strength.upper_body.push_ups", ...])

or from the command line::

    python -m fitness.engine.stats
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from operator_core.profile.progression import get_level_progress
from shared.config.paths import OPERATOR_CAPABILITIES, OPERATOR_HUBS
from shared.libraries.json_store import load_json, save_json

from fitness.engine.config import (
    DAILY_PRACTICE_COMPETENCY_ID,
    DAILY_PRACTICE_TREE_PATH,
    GYM_CAPABILITY_TREE_PATHS,
    HABITS,
)

# learning/engine/stats.py's build_operator_stats() keeps
# operator_core/profile/data/{stats,progression,awards}.json in sync with
# learning_stats.json every time IT rebuilds the tree - but this module is a
# second, independent writer of learning_stats.json (see the module
# docstring above: it only touches the fitness-owned leaves rather than
# calling build_operator_stats()), so a gym/habit log never went through
# that sync path and those three files stayed frozen after any fitness
# activity even once the other one was fixed. Reusing the same sync
# function here, fed with this module's own already-updated stats_doc and
# progress instead of recomputing anything, closes that second path too.
from learning.engine.stats import sync_profile_snapshot

LEARNING_STATS_PATH = OPERATOR_HUBS / "learning" / "stats" / "learning_stats.json"
COMPETENCIES_PATH = OPERATOR_CAPABILITIES / "competencies.json"

# Every tree_path this module is allowed to touch, keyed by competency_id.
# Includes each habit's optional secondary competency (e.g. stretch_minutes
# also feeds a DEX leaf) so a split habit's second branch gets its
# average_level recomputed too, plus every gym-lift capability
# fitness.engine.gym_log is allowed to award into (see config.py).
_TREE_PATHS: dict[str, list[str]] = {}
for _habit in HABITS.values():
    _TREE_PATHS[_habit["competency_id"]] = _habit["tree_path"]
    if _habit.get("secondary_competency_id"):
        _TREE_PATHS[_habit["secondary_competency_id"]] = _habit["secondary_tree_path"]
_TREE_PATHS[DAILY_PRACTICE_COMPETENCY_ID] = DAILY_PRACTICE_TREE_PATH
_TREE_PATHS.update(GYM_CAPABILITY_TREE_PATHS)

# The main stat roots this module ever recomputes averages for.
_OWNED_STAT_ROOTS = {path[0] for path in _TREE_PATHS.values()}


def _navigate(stats: dict[str, Any], tree_path: list[str]) -> dict[str, Any]:
    node = stats[tree_path[0]]
    for name in tree_path[1:]:
        node = node["children"][name]
    return node


def _sync_leaf(node: dict[str, Any], competency: dict[str, Any]) -> None:
    xp = int(competency.get("xp", 0))
    progress = get_level_progress(xp)
    node["xp"] = xp
    node["level"] = progress["level"]
    node["level_progress"] = progress["progress_percentage"]
    node["xp_into_level"] = progress["xp_into_level"]
    node["xp_to_next_level"] = progress["xp_to_next_level"]
    node["next_level_xp"] = progress["next_level_xp"]


def _representative_level(node: dict[str, Any]) -> float:
    """The number a parent averages: a skill leaf's own level, or a parent's average_level."""
    if node.get("node_type") == "skill" or node.get("node_type") == "competency_reference":
        return float(node.get("level", 0))
    return float(node.get("average_level", 0.0))


def _recompute_averages(node: dict[str, Any]) -> float:
    """Recompute average_level bottom-up for a parent/main_stat node. Returns its value."""
    children = node.get("children")
    if not isinstance(children, dict) or not children:
        return _representative_level(node)

    values = []
    for child in children.values():
        if child.get("node_type") in ("skill", "competency_reference"):
            values.append(_representative_level(child))
        else:
            values.append(_recompute_averages(child))

    average = round(sum(values) / len(values), 2) if values else 0.0
    node["average_level"] = average
    return average


def sync_and_recompute(competency_ids: Iterable[str]) -> dict[str, Any]:
    """Sync the given competencies' xp/level into learning_stats.json leaves,
    recompute average_level for every stat root those leaves live under, and
    refresh the top-level Operator total_xp/level. Returns the updated document.
    """
    stats_doc = load_json(LEARNING_STATS_PATH, None)
    if stats_doc is None:
        raise FileNotFoundError(f"learning_stats.json not found at {LEARNING_STATS_PATH}")
    competencies_doc = load_json(COMPETENCIES_PATH, None)
    if competencies_doc is None:
        raise FileNotFoundError(f"competencies.json not found at {COMPETENCIES_PATH}")
    competencies = competencies_doc.get("competencies", {})

    touched_roots: set[str] = set()
    for competency_id in competency_ids:
        tree_path = _TREE_PATHS.get(competency_id)
        if tree_path is None:
            raise KeyError(
                f"{competency_id} has no known tree_path in fitness/engine/config.py"
            )
        competency = competencies.get(competency_id)
        if competency is None:
            raise KeyError(f"{competency_id} not found in competencies.json")
        leaf = _navigate(stats_doc["stats"], tree_path)
        _sync_leaf(leaf, competency)
        touched_roots.add(tree_path[0])

    for root_name in touched_roots:
        _recompute_averages(stats_doc["stats"][root_name])

    total_xp = sum(int(item.get("xp", 0)) for item in competencies.values())
    progress = get_level_progress(total_xp)
    stats_doc.update(
        {
            "total_xp": total_xp,
            "level": progress["level"],
            "level_progress": progress["progress_percentage"],
            "xp_into_level": progress["xp_into_level"],
            "xp_to_next_level": progress["xp_to_next_level"],
            "next_level_xp": progress["next_level_xp"],
            "level_xp_required": progress["level_xp_required"],
            "competency_count": len(competencies),
        }
    )

    save_json(LEARNING_STATS_PATH, stats_doc)
    sync_profile_snapshot(stats_doc["stats"], progress)
    return stats_doc


def rebuild_all_owned_branches() -> dict[str, Any]:
    """Full resync of every fitness-owned leaf (STR/CON/DISC daily-practice branches).

    Safe to run any time, e.g. after manually editing competencies.json.
    """
    return sync_and_recompute(_TREE_PATHS.keys())


if __name__ == "__main__":
    document = rebuild_all_owned_branches()
    print(f"Operator total_xp={document['total_xp']} level={document['level']}")
    for root in sorted(_OWNED_STAT_ROOTS):
        print(f"  {root}: average_level={document['stats'][root]['average_level']}")

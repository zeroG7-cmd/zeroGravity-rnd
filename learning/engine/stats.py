"""
Operator Zero Learning Engine
Operator Stats Engine v2.0

Progression model
-----------------
Only leaf skills earn XP.

Example:
    Python +40 XP

Parent nodes do not receive copied XP.

Instead:

    Programming Languages
    = average level of Python, C++, and JavaScript

    Software Engineering
    = average score of its child categories

    INT
    = average score of its child domains

This prevents XP duplication across the knowledge tree.
"""

import json
from pathlib import Path
from typing import Any


# ============================================================
# PATHS
# ============================================================

LEARNING_ROOT = Path("learning")

SKILL_TREE_PATH = (
    LEARNING_ROOT
    / "config"
    / "skill_tree.json"
)

OPERATOR_ROOT = (
    LEARNING_ROOT
    / "operator"
)

STATS_PATH = (
    OPERATOR_ROOT
    / "stats.json"
)


# ============================================================
# JSON STORAGE
# ============================================================

def load_json(
    file_path: Path,
    default: Any,
) -> Any:
    """Load JSON, or return a default value."""

    if not file_path.exists():
        return default

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(
    file_path: Path,
    data: Any,
) -> None:
    """Save data as readable JSON."""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=4,
        )


# ============================================================
# LEVEL CALCULATION
# ============================================================

def calculate_skill_level(xp: int) -> int:
    """
    Convert leaf-skill XP into a level.

    Current MVP thresholds:

        0 XP       -> Level 0
        1-99 XP    -> Level 1
        100-199 XP -> Level 2
        200-299 XP -> Level 3

    Later this can be replaced with a curved progression formula.
    """

    if xp <= 0:
        return 0

    return (xp // 100) + 1


def calculate_operator_level(total_xp: int) -> int:
    """
    Calculate the overall Operator level.

    This currently uses the same formula as skill levels.
    """

    if total_xp <= 0:
        return 0

    return (total_xp // 100) + 1


# ============================================================
# TREE BUILDING
# ============================================================

def build_stats_node(
    node_name: str,
    tree_definition: dict[str, Any],
    old_node: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build one stats node from the canonical skill-tree definition.

    Leaf nodes store:
        xp
        level

    Parent nodes store:
        average_level
        children
    """

    old_node = old_node or {}

    has_children = bool(tree_definition)

    if not has_children:
        xp = int(old_node.get("xp", 0))

        return {
            "name": node_name,
            "node_type": "skill",
            "xp": xp,
            "level": calculate_skill_level(xp),
        }

    old_children = old_node.get(
        "children",
        {},
    )

    children = {}

    for child_name, child_definition in tree_definition.items():
        children[child_name] = build_stats_node(
            node_name=child_name,
            tree_definition=child_definition,
            old_node=old_children.get(
                child_name,
                {},
            ),
        )

    node = {
        "name": node_name,
        "node_type": "parent",
        "average_level": 0.0,
        "children": children,
    }

    recalculate_node_average(node)

    return node


def build_operator_stats() -> dict[str, Any]:
    """
    Build stats.json from skill_tree.json while preserving
    existing XP on leaf skills.
    """

    skill_tree = load_json(
        SKILL_TREE_PATH,
        default={"stats": {}},
    )

    existing_stats = load_json(
        STATS_PATH,
        default={
            "stats": {},
            "total_xp": 0,
            "level": 0,
        },
    )

    tree_stats = skill_tree.get(
        "stats",
        {},
    )

    old_stats = existing_stats.get(
        "stats",
        {},
    )

    generated_stats = {}

    for stat_name, stat_definition in tree_stats.items():
        generated_stats[stat_name] = build_stats_node(
            node_name=stat_name,
            tree_definition=stat_definition,
            old_node=old_stats.get(
                stat_name,
                {},
            ),
        )

    result = {
        "stats": generated_stats,
        "total_xp": int(
            existing_stats.get(
                "total_xp",
                0,
            )
        ),
        "level": calculate_operator_level(
            int(
                existing_stats.get(
                    "total_xp",
                    0,
                )
            )
        ),
    }

    save_json(
        STATS_PATH,
        result,
    )

    return result


# ============================================================
# TREE NAVIGATION
# ============================================================

def find_leaf_skill(
    stats: dict[str, Any],
    stat_name: str,
    hierarchy: list[str],
) -> dict[str, Any]:
    """
    Follow a hierarchy path and return its final skill node.

    Example:

        stat_name = "INT"

        hierarchy = [
            "Software Engineering",
            "Programming Languages",
            "Python"
        ]
    """

    stat_nodes = stats.get(
        "stats",
        {},
    )

    if stat_name not in stat_nodes:
        raise KeyError(
            f"Stat not found in skill tree: {stat_name}"
        )

    current_node = stat_nodes[stat_name]

    for hierarchy_level in hierarchy:
        children = current_node.get(
            "children",
            {},
        )

        if hierarchy_level not in children:
            raise KeyError(
                "Knowledge-tree path was not found:\n"
                f"{stat_name} > {' > '.join(hierarchy)}\n\n"
                f"Missing node: {hierarchy_level}"
            )

        current_node = children[
            hierarchy_level
        ]

    if current_node.get("node_type") != "skill":
        raise ValueError(
            "XP can only be awarded to a leaf skill.\n"
            f"The selected path ends at a parent node: "
            f"{hierarchy[-1]}"
        )

    return current_node


# ============================================================
# AVERAGE CALCULATION
# ============================================================

def get_node_score(
    node: dict[str, Any],
) -> float:
    """
    Return the value used by a node's parent.

    Leaf:
        skill level

    Parent:
        calculated average level
    """

    if node.get("node_type") == "skill":
        return float(
            node.get("level", 0)
        )

    return float(
        node.get(
            "average_level",
            0.0,
        )
    )


def recalculate_node_average(
    node: dict[str, Any],
) -> float:
    """
    Recalculate one parent node recursively.

    Unstarted children count as Level 0.
    """

    if node.get("node_type") == "skill":
        return float(
            node.get("level", 0)
        )

    children = node.get(
        "children",
        {},
    )

    if not children:
        node["average_level"] = 0.0
        return 0.0

    child_scores = []

    for child in children.values():
        if child.get("node_type") == "parent":
            recalculate_node_average(child)

        child_scores.append(
            get_node_score(child)
        )

    average = (
        sum(child_scores)
        / len(child_scores)
    )

    node["average_level"] = round(
        average,
        2,
    )

    return node["average_level"]


def recalculate_all_averages(
    stats: dict[str, Any],
) -> None:
    """Recalculate every parent score in the stats tree."""

    for stat_node in stats.get(
        "stats",
        {},
    ).values():
        recalculate_node_average(
            stat_node
        )


# ============================================================
# XP AWARDING
# ============================================================

def update_operator_stats(
    metadata: dict[str, Any],
    xp_award: int,
) -> dict[str, Any]:
    """
    Award XP only to the leaf skill.

    Parent nodes are recalculated from their children.
    """

    if xp_award < 0:
        raise ValueError(
            "XP award cannot be negative."
        )

    stats = build_operator_stats()

    stat_name = str(
        metadata.get(
            "stat",
            "Unknown",
        )
    )

    hierarchy = metadata.get(
        "hierarchy",
        [],
    )

    if not isinstance(hierarchy, list):
        raise ValueError(
            "metadata hierarchy must be a list."
        )

    if not hierarchy:
        raise ValueError(
            "metadata hierarchy cannot be empty."
        )

    leaf_skill = find_leaf_skill(
        stats=stats,
        stat_name=stat_name,
        hierarchy=hierarchy,
    )

    leaf_skill["xp"] = (
        int(
            leaf_skill.get(
                "xp",
                0,
            )
        )
        + xp_award
    )

    leaf_skill["level"] = calculate_skill_level(
        leaf_skill["xp"]
    )

    stats["total_xp"] = (
        int(
            stats.get(
                "total_xp",
                0,
            )
        )
        + xp_award
    )

    stats["level"] = calculate_operator_level(
        stats["total_xp"]
    )

    recalculate_all_averages(
        stats
    )

    save_json(
        STATS_PATH,
        stats,
    )

    return stats


# ============================================================
# READ HELPERS
# ============================================================

def get_skill_stats(
    stats: dict[str, Any],
    stat_name: str,
    hierarchy: list[str],
) -> dict[str, Any]:
    """Return data for one leaf skill."""

    return find_leaf_skill(
        stats=stats,
        stat_name=stat_name,
        hierarchy=hierarchy,
    )
"""
Operator Zero Learning Engine
Operator Stats Engine v3.0 — Knowledge Graph Edition

skill_tree.json defines where competencies appear.
competencies.json owns competency XP and level.
stats.json is generated display/cache data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from level import calculate_level, get_level_progress

LEARNING_ROOT = Path("learning")
SKILL_TREE_PATH = LEARNING_ROOT / "config" / "skill_tree.json"
COMPETENCIES_PATH = LEARNING_ROOT / "config" / "competencies.json"
OPERATOR_ROOT = LEARNING_ROOT / "operator"
STATS_PATH = OPERATOR_ROOT / "stats.json"


def load_json(file_path: Path, default: Any) -> Any:
    if not file_path.exists():
        return default
    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON inside:\n{file_path}\n\n{error}") from error


def save_json(file_path: Path, data: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = file_path.with_suffix(file_path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
        file.write("\n")
    temporary_path.replace(file_path)


def calculate_skill_level(xp: int) -> int:
    """Compatibility wrapper around the central progressive level engine."""
    return calculate_level(xp)


def calculate_operator_level(total_xp: int) -> int:
    """Compatibility wrapper around the central progressive level engine."""
    return calculate_level(total_xp)


def load_skill_tree() -> dict[str, Any]:
    skill_tree = load_json(SKILL_TREE_PATH, {"stats": {}})
    if not isinstance(skill_tree.get("stats"), dict):
        raise ValueError("skill_tree.json must contain a 'stats' object.")
    return skill_tree


def load_competencies() -> dict[str, Any]:
    data = load_json(
        COMPETENCIES_PATH,
        {"schema_version": 1, "competencies": {}},
    )
    if not isinstance(data.get("competencies"), dict):
        raise ValueError("competencies.json must contain a 'competencies' object.")
    return data


def find_tree_node(
    skill_tree: dict[str, Any],
    stat_name: str,
    hierarchy: list[str],
) -> dict[str, Any]:
    stat_nodes = skill_tree.get("stats", {})
    if stat_name not in stat_nodes:
        raise KeyError(f"Main stat not found: {stat_name}")

    current_node = stat_nodes[stat_name]
    for level_name in hierarchy:
        children = current_node.get("children", {})
        if level_name not in children:
            full_path = " > ".join([stat_name, *hierarchy])
            raise KeyError(
                "Knowledge-tree path was not found:\n"
                f"{full_path}\n\nMissing node: {level_name}"
            )
        current_node = children[level_name]
    return current_node


def find_competency_reference(
    skill_tree: dict[str, Any],
    stat_name: str,
    hierarchy: list[str],
) -> dict[str, Any]:
    node = find_tree_node(skill_tree, stat_name, hierarchy)
    if node.get("node_type") != "competency_reference":
        selected_name = hierarchy[-1] if hierarchy else stat_name
        raise ValueError(
            "XP can only be awarded to a competency.\n"
            f"The selected path ends at a structural node: {selected_name}"
        )
    if not node.get("competency_id"):
        raise ValueError(
            "The selected competency reference has no 'competency_id'. "
            "Re-run the skill-tree synchronizer."
        )
    return node


def resolve_competency_node(
    tree_node: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    competency_id = str(tree_node.get("competency_id", ""))
    if not competency_id:
        raise ValueError(
            f"Competency reference '{tree_node.get('name')}' has no competency_id."
        )

    competency = registry.get(competency_id)
    if not isinstance(competency, dict):
        raise KeyError(
            "Competency reference points to a missing registry entry:\n"
            f"{competency_id}\n\nRun sync_skill_tree.py again."
        )

    xp = int(competency.get("xp", 0))
    progress = get_level_progress(xp)
    return {
        "name": str(tree_node.get("name", competency.get("name", competency_id))),
        "node_type": "skill",
        "competency_id": competency_id,
        "shared": bool(tree_node.get("shared", competency.get("shared", False))),
        "xp": xp,
        "level": progress["level"],
        "level_progress": progress["progress_percentage"],
        "xp_into_level": progress["xp_into_level"],
        "xp_to_next_level": progress["xp_to_next_level"],
        "next_level_xp": progress["next_level_xp"],
    }


def get_node_score(node: dict[str, Any]) -> float:
    if node.get("node_type") == "skill":
        return float(node.get("level", 0))
    return float(node.get("average_level", 0.0))


def recalculate_node_average(node: dict[str, Any]) -> float:
    if node.get("node_type") == "skill":
        return float(node.get("level", 0))

    children = node.get("children", {})
    if not isinstance(children, dict) or not children:
        node["average_level"] = 0.0
        return 0.0

    scores: list[float] = []
    for child in children.values():
        if child.get("node_type") != "skill":
            recalculate_node_average(child)
        scores.append(get_node_score(child))

    node["average_level"] = round(sum(scores) / len(scores), 2)
    return node["average_level"]


def build_display_node(
    tree_node: dict[str, Any],
    registry: dict[str, Any],
    *,
    is_main_stat: bool = False,
) -> dict[str, Any]:
    node_name = str(tree_node.get("name", "Unknown"))

    if is_main_stat:
        children_definition = tree_node.get("children", {})
        children: dict[str, Any] = {}
        if isinstance(children_definition, dict):
            for child_name, child_definition in children_definition.items():
                if isinstance(child_definition, dict):
                    children[child_name] = build_display_node(child_definition, registry)

        result = {
            "name": node_name,
            "node_type": "main_stat",
            "average_level": 0.0,
            "children": children,
        }
        recalculate_node_average(result)
        return result

    if tree_node.get("node_type") == "competency_reference":
        return resolve_competency_node(tree_node, registry)

    children_definition = tree_node.get("children", {})
    if not isinstance(children_definition, dict):
        children_definition = {}

    children: dict[str, Any] = {}
    for child_name, child_definition in children_definition.items():
        if isinstance(child_definition, dict):
            children[child_name] = build_display_node(child_definition, registry)

    result = {
        "name": node_name,
        "node_type": "parent",
        "average_level": 0.0,
        "children": children,
    }
    recalculate_node_average(result)
    return result


def collect_referenced_competency_ids(tree_stats: dict[str, Any]) -> set[str]:
    competency_ids: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        if node.get("node_type") == "competency_reference":
            competency_id = node.get("competency_id")
            if competency_id:
                competency_ids.add(str(competency_id))
            return

        children = node.get("children", {})
        if isinstance(children, dict):
            for child in children.values():
                if isinstance(child, dict):
                    walk(child)

    # Ignore top-level leaf references because CON/STR/DEX/DIS are main stats.
    for main_stat in tree_stats.values():
        if not isinstance(main_stat, dict):
            continue
        children = main_stat.get("children", {})
        if isinstance(children, dict):
            for child in children.values():
                if isinstance(child, dict):
                    walk(child)

    return competency_ids


def calculate_total_xp(
    competency_ids: Iterable[str],
    registry: dict[str, Any],
) -> int:
    total = 0
    for competency_id in set(competency_ids):
        competency = registry.get(competency_id, {})
        if isinstance(competency, dict):
            total += int(competency.get("xp", 0))
    return total


def migrate_existing_stats_progress(
    skill_tree: dict[str, Any],
    competencies_data: dict[str, Any],
) -> list[str]:
    """
    Migrate XP from the old embedded stats.json format into competencies.json.

    Migration only fills registry entries that currently have 0 XP. Shared
    competencies use the highest matching old XP rather than adding duplicates.
    """

    existing_stats = load_json(
        STATS_PATH,
        default={"stats": {}},
    )
    old_stat_nodes = existing_stats.get("stats", {})
    registry = competencies_data.get("competencies", {})
    candidates: dict[str, list[tuple[int, int]]] = {}

    def walk(
        tree_node: dict[str, Any],
        old_node: dict[str, Any],
    ) -> None:
        if tree_node.get("node_type") == "competency_reference":
            competency_id = tree_node.get("competency_id")
            if competency_id and isinstance(old_node, dict):
                if "xp" in old_node or "level" in old_node:
                    candidates.setdefault(str(competency_id), []).append(
                        (
                            int(old_node.get("xp", 0)),
                            int(old_node.get("level", 0)),
                        )
                    )
            return

        tree_children = tree_node.get("children", {})
        old_children = old_node.get("children", {}) if isinstance(old_node, dict) else {}
        if not isinstance(tree_children, dict):
            return
        if not isinstance(old_children, dict):
            old_children = {}

        for child_name, child_tree_node in tree_children.items():
            if isinstance(child_tree_node, dict):
                child_old_node = old_children.get(child_name, {})
                walk(child_tree_node, child_old_node)

    tree_stats = skill_tree.get("stats", {})
    if isinstance(tree_stats, dict) and isinstance(old_stat_nodes, dict):
        for stat_name, stat_tree_node in tree_stats.items():
            if not isinstance(stat_tree_node, dict):
                continue
            stat_old_node = old_stat_nodes.get(stat_name, {})
            # Top-level stats are containers, not competencies.
            tree_children = stat_tree_node.get("children", {})
            old_children = stat_old_node.get("children", {}) if isinstance(stat_old_node, dict) else {}
            if isinstance(tree_children, dict):
                for child_name, child_tree_node in tree_children.items():
                    if isinstance(child_tree_node, dict):
                        child_old_node = old_children.get(child_name, {}) if isinstance(old_children, dict) else {}
                        walk(child_tree_node, child_old_node)

    migrated: list[str] = []
    for competency_id, progress_values in candidates.items():
        competency = registry.get(competency_id)
        if not isinstance(competency, dict):
            continue
        if int(competency.get("xp", 0)) > 0:
            continue

        best_xp = max(xp for xp, _ in progress_values)
        best_level = max(level for _, level in progress_values)
        if best_xp <= 0 and best_level <= 0:
            continue

        competency["xp"] = best_xp
        competency["level"] = calculate_skill_level(best_xp)
        migrated.append(
            f"{competency.get('name', competency_id)}: {best_xp} XP"
        )

    return migrated


def synchronize_registry_levels(competencies_data: dict[str, Any]) -> bool:
    changed = False
    registry = competencies_data.get("competencies", {})
    for competency in registry.values():
        if not isinstance(competency, dict):
            continue
        xp = int(competency.get("xp", 0))
        correct_level = calculate_skill_level(xp)
        if int(competency.get("level", 0)) != correct_level:
            competency["level"] = correct_level
            changed = True
    return changed


def build_operator_stats() -> dict[str, Any]:
    skill_tree = load_skill_tree()
    competencies_data = load_competencies()
    migrated_progress = migrate_existing_stats_progress(
        skill_tree,
        competencies_data,
    )
    registry_changed = synchronize_registry_levels(competencies_data)
    registry_changed = registry_changed or bool(migrated_progress)
    registry = competencies_data["competencies"]
    tree_stats = skill_tree.get("stats", {})

    generated_stats: dict[str, Any] = {}
    for stat_name, stat_definition in tree_stats.items():
        if isinstance(stat_definition, dict):
            generated_stats[stat_name] = build_display_node(
                stat_definition,
                registry,
                is_main_stat=True,
            )

    referenced_ids = collect_referenced_competency_ids(tree_stats)
    total_xp = calculate_total_xp(referenced_ids, registry)

    operator_progress = get_level_progress(total_xp)
    result = {
        "schema_version": 4,
        "stats": generated_stats,
        "total_xp": total_xp,
        "level": operator_progress["level"],
        "level_progress": operator_progress["progress_percentage"],
        "xp_into_level": operator_progress["xp_into_level"],
        "xp_to_next_level": operator_progress["xp_to_next_level"],
        "next_level_xp": operator_progress["next_level_xp"],
        "level_xp_required": operator_progress["level_xp_required"],
        "competency_count": len(referenced_ids),
        "migrated_competencies": migrated_progress,
    }

    if registry_changed:
        save_json(COMPETENCIES_PATH, competencies_data)
    save_json(STATS_PATH, result)
    return result


def find_leaf_skill(
    stats: dict[str, Any],
    stat_name: str,
    hierarchy: list[str],
) -> dict[str, Any]:
    stat_nodes = stats.get("stats", {})
    if stat_name not in stat_nodes:
        raise KeyError(f"Stat not found in Operator stats: {stat_name}")

    current_node = stat_nodes[stat_name]
    for level_name in hierarchy:
        children = current_node.get("children", {})
        if level_name not in children:
            raise KeyError(
                "Operator-stats path was not found:\n"
                f"{stat_name} > {' > '.join(hierarchy)}\n\n"
                f"Missing node: {level_name}"
            )
        current_node = children[level_name]

    if current_node.get("node_type") != "skill":
        selected_name = hierarchy[-1] if hierarchy else stat_name
        raise ValueError(
            "The selected path does not end at a competency:\n"
            f"{selected_name}"
        )
    return current_node


def update_operator_competencies(
    xp_distribution: list[dict[str, Any]],
) -> dict[str, Any]:
    """Award one completion across any number of competencies atomically."""
    if not isinstance(xp_distribution, list) or not xp_distribution:
        raise ValueError("XP distribution must be a non-empty list.")

    competencies_data = load_competencies()
    registry = competencies_data["competencies"]
    merged: dict[str, int] = {}

    for award in xp_distribution:
        if not isinstance(award, dict):
            raise ValueError("Every XP distribution entry must be an object.")

        competency_id = str(award.get("competency_id", "")).strip()
        if not competency_id:
            raise ValueError("XP distribution entry has no competency_id.")

        try:
            xp_award = int(award.get("xp", 0))
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid XP award for competency: {competency_id}"
            ) from error

        if xp_award < 0:
            raise ValueError("XP awards cannot be negative.")

        competency = registry.get(competency_id)
        if not isinstance(competency, dict):
            raise KeyError(
                "Competency not found in competencies.json:\n"
                f"{competency_id}\n\nRun sync_skill_tree.py again."
            )

        merged[competency_id] = merged.get(competency_id, 0) + xp_award

    for competency_id, xp_award in merged.items():
        competency = registry[competency_id]
        new_xp = int(competency.get("xp", 0)) + xp_award
        progress = get_level_progress(new_xp)
        competency["xp"] = new_xp
        competency["level"] = progress["level"]
        competency["level_progress"] = progress["progress_percentage"]
        competency["xp_to_next_level"] = progress["xp_to_next_level"]

    save_json(COMPETENCIES_PATH, competencies_data)
    return build_operator_stats()


def update_operator_stats(
    metadata: dict[str, Any],
    xp_award: int,
) -> dict[str, Any]:
    """Backward-compatible single-competency award function."""
    if xp_award < 0:
        raise ValueError("XP award cannot be negative.")

    stat_name = str(metadata.get("stat", "")).strip()
    hierarchy = metadata.get("hierarchy", [])

    if not stat_name:
        raise ValueError("metadata has no valid 'stat' value.")
    if not isinstance(hierarchy, list) or not hierarchy:
        raise ValueError("metadata hierarchy must be a non-empty list.")

    skill_tree = load_skill_tree()
    reference = find_competency_reference(skill_tree, stat_name, hierarchy)

    return update_operator_competencies(
        [
            {
                "competency_id": str(reference["competency_id"]),
                "xp": int(xp_award),
                "weight": 1.0,
            }
        ]
    )


def get_skill_stats(
    stats: dict[str, Any],
    stat_name: str,
    hierarchy: list[str],
) -> dict[str, Any]:
    return find_leaf_skill(stats, stat_name, hierarchy)


def get_competency_stats(competency_id: str) -> dict[str, Any]:
    competencies_data = load_competencies()
    competency = competencies_data["competencies"].get(competency_id)
    if not isinstance(competency, dict):
        raise KeyError(f"Competency not found: {competency_id}")
    return competency


if __name__ == "__main__":
    generated = build_operator_stats()
    print("=" * 68)
    print("OPERATOR STATS REBUILT")
    print("=" * 68)
    print(f"Operator Level : {generated['level']}")
    print(f"Total XP       : {generated['total_xp']}")
    print(f"Competencies   : {generated['competency_count']}")
    print(f"Saved to       : {STATS_PATH}")
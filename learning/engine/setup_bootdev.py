"""Create/reconcile Boot.dev tracks and safely import historical progress.

Run from the zeroGravity-rnd repository root.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE = Path(__file__).resolve().parent
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from concepts import distribute_concept_xp, update_concept_progress
from history import record_completion
from stats import build_operator_stats, update_operator_competencies

ROOT = Path("learning")
CONFIG = ROOT / "resources" / "bootdev" / "bootdev_progress.json"
TRACKS = ROOT / "tracks"
LEDGER = ROOT / "operator" / "bootdev_history_imports.json"
COMPETENCIES = ROOT / "config" / "competencies.json"
CAPABILITY_GRAPH = ROOT / "config" / "capability_graph.json"
SKILL_TREE = ROOT / "config" / "skill_tree.json"
SKILL_TREE_MARKDOWN = ROOT / "skill_tree.md"

OLD_LINUX_ID = "int.robotics.robot_software.robot_middleware.linux"
NEW_LINUX_ID = "int.computer_science.operating_systems.linux"


def load(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def track_path(course: dict[str, Any]) -> Path:
    path = TRACKS / slug(course["stat"])
    for item in course["hierarchy"]:
        path /= slug(item)
    return path / slug(course["title"])


def legacy_track_paths(resource_id: str) -> list[Path]:
    values: dict[str, list[Path]] = {
        "bootdev_learn_linux": [
            TRACKS
            / "int"
            / "robotics"
            / "robot_software"
            / "robot_middleware"
            / "linux"
            / "learn_linux",
        ],
        "bootdev_learn_sql": [
            TRACKS
            / "int"
            / "data__databases"
            / "sql"
            / "learn_sql",
        ],
    }
    return values.get(resource_id, [])


def merge_linux_identity() -> None:
    """Move the old Linux capability/track without changing total XP."""
    competencies = load(
        COMPETENCIES,
        {"schema_version": 1, "competencies": {}},
    )
    registry = competencies.setdefault("competencies", {})
    old_record = registry.pop(OLD_LINUX_ID, None)
    new_record = registry.get(NEW_LINUX_ID)

    if old_record and new_record:
        new_record["xp"] = max(
            int(new_record.get("xp", 0)),
            int(old_record.get("xp", 0)),
        )
        new_record["level"] = max(
            int(new_record.get("level", 0)),
            int(old_record.get("level", 0)),
        )
    elif old_record:
        old_record["name"] = "Linux"
        registry[NEW_LINUX_ID] = old_record
    elif NEW_LINUX_ID not in registry:
        registry[NEW_LINUX_ID] = {
            "name": "Linux",
            "xp": 0,
            "level": 0,
            "level_progress": 0.0,
            "xp_to_next_level": 100,
            "shared": False,
        }
    save(COMPETENCIES, competencies)

    graph = load(CAPABILITY_GRAPH, {"capabilities": {}})
    capabilities = graph.setdefault("capabilities", {})
    if OLD_LINUX_ID in capabilities:
        capability = capabilities.pop(OLD_LINUX_ID)
        capability["id"] = NEW_LINUX_ID
        capabilities[NEW_LINUX_ID] = capability
        save(CAPABILITY_GRAPH, graph)



def migrate_linux_tree() -> None:
    """Move Linux in both machine and human-readable tree sources."""
    tree = load(SKILL_TREE, {"stats": {}})
    stats = tree.get("stats", {})
    try:
        robot_middleware = (
            stats["INT"]["children"]["Robotics"]["children"]
            ["Robot Software"]["children"]["Robot Middleware"]["children"]
        )
        robot_middleware.pop("Linux", None)
        operating_systems = (
            stats["INT"]["children"]["Computer Science"]["children"]
            ["Operating Systems"]["children"]
        )
        operating_systems["Linux"] = {
            "name": "Linux",
            "node_type": "competency_reference",
            "competency_id": NEW_LINUX_ID,
            "shared": False,
        }
        save(SKILL_TREE, tree)
    except (KeyError, TypeError):
        pass

    if SKILL_TREE_MARKDOWN.exists():
        text = SKILL_TREE_MARKDOWN.read_text(encoding="utf-8")
        text = text.replace(
            "      - Robot Middleware\n        - ROS2\n        - Linux\n",
            "      - Robot Middleware\n        - ROS2\n",
        )
        if "      - File Systems\n      - Linux\n" not in text:
            text = text.replace(
                "      - File Systems\n",
                "      - File Systems\n      - Linux\n",
                1,
            )
        SKILL_TREE_MARKDOWN.write_text(text, encoding="utf-8")


def move_legacy_tracks(resource_id: str, destination: Path) -> None:
    for source in legacy_track_paths(resource_id):
        if not source.exists() or source.resolve() == destination.resolve():
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            # Prefer the existing historical progress when the clean
            # destination was just scaffolded.
            source_progress = load(source / "progress.json", {})
            destination_progress = load(destination / "progress.json", {})
            if int(source_progress.get("total_xp", 0)) >= int(
                destination_progress.get("total_xp", 0)
            ):
                for filename in ("metadata.json", "progress.json"):
                    source_file = source / filename
                    if source_file.exists():
                        shutil.copy2(source_file, destination / filename)

            for item in source.rglob("*"):
                if not item.is_file():
                    continue
                relative = item.relative_to(source)
                target = destination / relative
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
            shutil.rmtree(source)
        else:
            shutil.move(str(source), str(destination))


def historical_unit_ids(course: dict[str, Any]) -> list[str]:
    """Stable placeholder IDs used only to mirror historical counts."""
    values: list[str] = []
    for section in course.get("sections", []):
        section_number = int(section.get("number", 0))
        completed = int(section.get("completed_units", 0))
        for unit_number in range(1, completed + 1):
            values.append(
                f"history_section_{section_number:02}_unit_{unit_number:03}"
            )
    return values


def create_track(
    resource_id: str,
    course: dict[str, Any],
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    path = track_path(course)
    move_legacy_tracks(resource_id, path)
    path.mkdir(parents=True, exist_ok=True)

    section_map = {
        str(section["number"]): {
            "mapping_confidence": section.get(
                "mapping_confidence",
                "medium",
            ),
            "concept_awards": section["concept_awards"],
        }
        for section in course["sections"]
    }

    metadata = load(path / "metadata.json", {})
    metadata.update(
        {
            "id": resource_id,
            "resource_id": resource_id,
            "external_resource_id": resource_id,
            "title": course["title"],
            "provider": "Boot.dev",
            "instructor": "Boot.dev Team",
            "stat": course["stat"],
            "hierarchy": course["hierarchy"],
            "domain": course["hierarchy"][0],
            "skill": course["hierarchy"][-1],
            "difficulty": "Beginner",
            "source_url": course["source_url"],
            "competency_id": course["capability_id"],
            "capability_id": course["capability_id"],
            "default_competency_awards": [
                {
                    "competency_id": course["capability_id"],
                    "weight": 1.0,
                }
            ],
            "section_concept_awards": section_map,
            "mapping_confidence": "medium",
            "manifest_schema_version": 3,
            "dynamic_provider_units": True,
            "external_total_units": course["total_units"],
            "xp_rules": {"exercise": course.get("xp_per_unit", 20)},
            "units": metadata.get("units", []),
            "unit_count": course["total_units"],
            "section_count": len(course["sections"]),
            "sections": [
                {
                    "number": section["number"],
                    "title": section["title"],
                    "total_units": section.get("total_units"),
                }
                for section in course["sections"]
            ],
        }
    )
    save(path / "metadata.json", metadata)

    progress = load(
        path / "progress.json",
        {
            "current_unit_index": 0,
            "completed_units": [],
            "total_xp": 0,
            "status": "In Progress",
        },
    )
    progress.setdefault("completed_units", [])
    progress.setdefault("total_xp", 0)
    progress["external_total_units"] = course["total_units"]
    progress.setdefault("external_completed_units", 0)
    progress.setdefault("status", "In Progress")
    save(path / "progress.json", progress)
    return path, metadata, progress


def mirror_historical_progress(
    course: dict[str, Any],
    progress: dict[str, Any],
) -> None:
    ids = historical_unit_ids(course)
    existing = [
        str(item)
        for item in progress.get("completed_units", [])
        if str(item)
    ]
    live = [
        item
        for item in existing
        if not item.startswith("history_section_")
    ]
    progress["completed_units"] = ids + live
    progress["external_completed_units"] = len(ids) + len(live)
    progress["current_unit_index"] = min(
        progress["external_completed_units"],
        int(course["total_units"]),
    )
    progress["external_total_units"] = int(course["total_units"])
    progress["status"] = (
        "Complete"
        if progress["external_completed_units"] >= int(course["total_units"])
        else "In Progress"
    )


def apply_history(
    resource_id: str,
    course: dict[str, Any],
    path: Path,
    metadata: dict[str, Any],
    progress: dict[str, Any],
    ledger: dict[str, Any],
    dry_run: bool,
) -> tuple[int, int, str]:
    total_units = sum(
        int(section.get("completed_units", 0))
        for section in course["sections"]
    )
    total_xp = total_units * int(course.get("xp_per_unit", 20))
    imported = ledger.get("imports", {}).get(resource_id)

    if dry_run:
        return total_units, total_xp, (
            "already_imported_reconcile_preview"
            if imported
            else "preview"
        )

    # Always reconcile the standard track progress. This repairs older
    # imports where XP existed but completed_units remained empty.
    mirror_historical_progress(course, progress)

    if imported:
        progress["total_xp"] = max(
            int(progress.get("total_xp", 0)),
            int(imported.get("xp_awarded", total_xp)),
        )
        save(path / "progress.json", progress)
        return total_units, 0, "reconciled_no_new_xp"

    update_operator_competencies(
        [
            {
                "competency_id": course["capability_id"],
                "xp": total_xp,
                "weight": 1.0,
            }
        ]
    )

    for section in course["sections"]:
        count = int(section.get("completed_units", 0))
        xp = count * int(course.get("xp_per_unit", 20))
        if not count:
            continue
        concept_distribution = distribute_concept_xp(
            xp,
            section.get("concept_awards", []),
        )
        update_concept_progress(
            course["capability_id"],
            concept_distribution,
            confidence=section.get("mapping_confidence", "medium"),
            source="bootdev_historical_import",
        )
        unit = {
            "id": f"historical_section_{int(section['number']):02}",
            "title": (
                f"{section['title']} — {count} historical lessons"
            ),
            "source_type": "exercise",
            "completion_source": "provider_history",
            "provider": "Boot.dev",
            "external_id": (
                f"{resource_id}:section:{section['number']}"
            ),
        }
        record_completion(
            metadata,
            unit,
            xp,
            [
                {
                    "competency_id": course["capability_id"],
                    "xp": xp,
                    "weight": 1.0,
                }
            ],
            concept_distribution,
            section.get("mapping_confidence", "medium"),
            "provider_history",
        )

    progress["total_xp"] = int(progress.get("total_xp", 0)) + total_xp
    save(path / "progress.json", progress)

    ledger.setdefault("imports", {})[resource_id] = {
        "completed_units": total_units,
        "xp_awarded": total_xp,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source": "bootdev_progress.json",
    }
    save(LEDGER, ledger)
    return total_units, total_xp, "imported"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create/reconcile Boot.dev tracks and import current "
            "historical progress."
        )
    )
    parser.add_argument("--apply-history", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configuration = load(CONFIG)
    ledger = load(
        LEDGER,
        {"schema_version": 1, "imports": {}},
    )

    merge_linux_identity()
    migrate_linux_tree()

    print("BOOT.DEV TRACK SETUP")
    print("-" * 68)
    for resource_id, course in configuration["courses"].items():
        path, metadata, progress = create_track(resource_id, course)
        print(f"Created/updated: {course['title']} -> {path}")
        if args.apply_history:
            units, xp, status = apply_history(
                resource_id,
                course,
                path,
                metadata,
                progress,
                ledger,
                args.dry_run,
            )
            print(f"  History: {status}; {units} units; {xp} XP")

    if not args.dry_run:
        build_operator_stats()
    else:
        print(
            "DRY RUN: track files are created/updated, but historical "
            "XP was not changed."
        )

    print(
        "\nNext: start Zero Command, reload the extension, then "
        "complete a Boot.dev lesson."
    )


if __name__ == "__main__":
    main()

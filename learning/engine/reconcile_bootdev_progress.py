"""Reconcile visible Boot.dev course progress with Operator Zero safely.

Example:
    python learning/engine/reconcile_bootdev_progress.py bootdev_learn_python 44

The command awards XP only for the positive difference from the historical/live
progress already recorded in Operator Zero. Re-running the same count awards 0 XP.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE = Path(__file__).resolve().parent
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from concepts import distribute_concept_xp, update_concept_progress
from history import record_completion
from setup_bootdev import (
    CONFIG,
    LEDGER,
    apply_history,
    create_track,
    load,
    save,
)
from stats import build_operator_stats, update_operator_competencies


def sequential_section_counts(course: dict[str, Any], completed: int) -> list[int]:
    remaining = completed
    values: list[int] = []
    for section in course.get("sections", []):
        total = int(section.get("total_units", 0))
        count = min(max(remaining, 0), total)
        values.append(count)
        remaining -= count
    if remaining > 0:
        raise ValueError(
            f"Completed count {completed} exceeds configured course total "
            f"{course.get('total_units')}."
        )
    return values


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover missed Boot.dev progress without duplicate XP."
    )
    parser.add_argument("resource_id", help="Example: bootdev_learn_python")
    parser.add_argument("completed_units", type=int, help="Visible completed total")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configuration = load(CONFIG)
    courses = configuration.get("courses", {})
    if args.resource_id not in courses:
        raise SystemExit(f"Unknown Boot.dev resource: {args.resource_id}")

    course = courses[args.resource_id]
    target = int(args.completed_units)
    total_units = int(course.get("total_units", 0))
    if target < 0 or target > total_units:
        raise SystemExit(f"completed_units must be between 0 and {total_units}")

    ledger = load(LEDGER, {"schema_version": 1, "imports": {}})
    imported = ledger.setdefault("imports", {}).get(args.resource_id, {})
    recorded = int(imported.get("completed_units", 0))

    path, metadata, progress = create_track(args.resource_id, course)
    recorded = max(recorded, int(progress.get("external_completed_units", 0)))
    delta = target - recorded

    print("BOOT.DEV PROGRESS RECONCILIATION")
    print("-" * 68)
    print(f"Course              : {course['title']}")
    print(f"Recorded progress   : {recorded}/{total_units}")
    print(f"Visible progress    : {target}/{total_units}")

    if delta <= 0:
        print("New completions     : 0")
        print("New Operator XP     : 0")
        print("Already synchronized. No files changed.")
        return

    previous_counts = sequential_section_counts(course, recorded)
    target_counts = sequential_section_counts(course, target)
    xp_per_unit = int(course.get("xp_per_unit", 20))
    total_delta_xp = delta * xp_per_unit

    print(f"New completions     : {delta}")
    print(f"New Operator XP     : {total_delta_xp}")
    print("Concept allocation")
    print("-" * 68)

    section_changes: list[tuple[dict[str, Any], int, int, dict[str, int]]] = []
    for index, section in enumerate(course.get("sections", [])):
        section_delta = target_counts[index] - previous_counts[index]
        if section_delta <= 0:
            continue
        section_xp = section_delta * xp_per_unit
        concept_distribution = distribute_concept_xp(
            section_xp,
            section.get("concept_awards", []),
        )
        section_changes.append(
            (section, section_delta, section_xp, concept_distribution)
        )
        print(
            f"{section['title']}: {section_delta} lesson(s), "
            f"{section_xp} XP"
        )
        for award in concept_distribution:
            print(f"  {award['concept_id']}: +{award['xp']} XP")

    if args.dry_run:
        print("\nDRY RUN: no files changed.")
        return

    # Update the source-of-truth visible progress configuration.
    for section, count in zip(course.get("sections", []), target_counts):
        section["completed_units"] = count
    course["completed_units"] = target
    configuration["captured_at"] = datetime.now(timezone.utc).isoformat()
    save(CONFIG, configuration)

    # Award only the missing capability XP.
    update_operator_competencies(
        [
            {
                "competency_id": course["capability_id"],
                "xp": total_delta_xp,
                "weight": 1.0,
            }
        ]
    )

    # Award only the missing concept XP and write transparent history records.
    for section, section_delta, section_xp, concept_distribution in section_changes:
        update_concept_progress(
            course["capability_id"],
            concept_distribution,
            confidence=section.get("mapping_confidence", "medium"),
            source="bootdev_reconciliation",
        )
        unit = {
            "id": (
                f"reconcile_section_{int(section['number']):02}_"
                f"to_{target_counts[int(section['number']) - 1]:03}"
            ),
            "title": (
                f"{section['title']} — {section_delta} recovered lesson(s)"
            ),
            "source_type": "exercise",
            "completion_source": "provider_reconciliation",
            "provider": "Boot.dev",
            "external_id": (
                f"{args.resource_id}:reconcile:{section['number']}:"
                f"{target_counts[int(section['number']) - 1]}"
            ),
        }
        record_completion(
            metadata,
            unit,
            section_xp,
            [
                {
                    "competency_id": course["capability_id"],
                    "xp": section_xp,
                    "weight": 1.0,
                }
            ],
            concept_distribution,
            section.get("mapping_confidence", "medium"),
            "provider_reconciliation",
        )

    # Reuse setup's proven mirroring logic without awarding historical XP again.
    imported["completed_units"] = target
    imported["xp_awarded"] = int(imported.get("xp_awarded", 0)) + total_delta_xp
    imported["last_reconciled_at"] = datetime.now(timezone.utc).isoformat()
    ledger["imports"][args.resource_id] = imported
    save(LEDGER, ledger)

    # apply_history sees the ledger and performs count mirroring with 0 extra XP.
    refreshed_configuration = load(CONFIG)
    refreshed_course = refreshed_configuration["courses"][args.resource_id]
    path, metadata, progress = create_track(args.resource_id, refreshed_course)
    apply_history(
        args.resource_id,
        refreshed_course,
        path,
        metadata,
        progress,
        ledger,
        dry_run=False,
    )
    build_operator_stats()

    print("\nRECONCILIATION COMPLETE")
    print(f"Progress            : {target}/{total_units}")
    print(f"XP awarded          : {total_delta_xp}")
    print("Re-running this same command will award 0 XP.")


if __name__ == "__main__":
    main()

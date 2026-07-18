"""Operator Zero Learning Engine — Universal Tracker v6.0.

Adds progressive levels and weighted multi-competency XP while preserving
legacy single-competency tracks.
"""

from __future__ import annotations
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from shared.config.paths import LEARNING_TRACKS
from typing import Any

from history import record_completion
from concepts import distribute_concept_xp, resolve_concept_awards, update_concept_progress
from stats import get_competency_stats, update_operator_competencies
from xp import (
    calculate_unit_xp,
    distribute_xp,
    resolve_competency_awards,
)

TRACKS_ROOT = LEARNING_TRACKS


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Required file not found:\n{path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON inside:\n{path}\n\n{error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in: {path}")
    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def discover_tracks() -> list[Path]:
    if not TRACKS_ROOT.exists():
        return []
    return sorted(
        metadata.parent
        for metadata in TRACKS_ROOT.rglob("metadata.json")
        if (metadata.parent / "progress.json").exists()
    )


def build_knowledge_path(metadata: dict[str, Any]) -> str:
    hierarchy = metadata.get("hierarchy", [])
    return " > ".join(
        str(value)
        for value in [metadata.get("stat", "Unknown"), *hierarchy]
        if value
    )


def select_track(track_paths: list[Path]) -> Path | None:
    if not track_paths:
        print("No learning tracks found.")
        return None

    print("\nAvailable learning tracks")
    print("-" * 68)
    for index, track_path in enumerate(track_paths, start=1):
        metadata = load_json(track_path / "metadata.json")
        print(f"{index}. {metadata.get('title', track_path.name)}")
        print(f"   {build_knowledge_path(metadata)}")

    while True:
        value = input("\nSelect a track number, or enter Q to quit: ").strip()
        if value.lower() == "q":
            return None
        try:
            index = int(value) - 1
        except ValueError:
            print("Enter a valid number or Q.")
            continue
        if 0 <= index < len(track_paths):
            return track_paths[index]
        print(f"Choose a number from 1 to {len(track_paths)}.")


def validate_metadata(metadata: dict[str, Any]) -> None:
    if not isinstance(metadata.get("units"), list) or not metadata["units"]:
        raise ValueError("metadata.json has no valid 'units' list.")
    if not isinstance(metadata.get("evidence_requirements"), list):
        raise ValueError("metadata.json has no evidence requirements list.")


def ensure_progress(progress: dict[str, Any]) -> None:
    progress.setdefault("current_unit_index", 0)
    progress.setdefault("completed_units", [])
    progress.setdefault("total_xp", 0)
    progress.setdefault("status", "In Progress")


def file_has_meaningful_content(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.stat().st_size > 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line in {"...", "TODO", "TBD", "[ ]", "- [ ]"}:
            continue
        if line.startswith("- [ ]"):
            continue
        return True
    return False


def check_evidence(
    unit_path: Path,
    requirements: list[dict[str, str]],
) -> dict[str, bool]:
    return {
        requirement["name"]: file_has_meaningful_content(
            unit_path / Path(requirement["path"])
        )
        for requirement in requirements
    }


def display_distribution(distribution: list[dict[str, Any]]) -> None:
    print("\nXP distribution")
    print("-" * 68)
    for award in distribution:
        competency = get_competency_stats(award["competency_id"])
        name = competency.get("name", award["competency_id"])
        percentage = round(float(award.get("weight", 0)) * 100)
        print(f"{name:<32}+{award['xp']:>3} XP  ({percentage:>3}%)")
    print("-" * 68)


def complete_progress(
    progress: dict[str, Any],
    unit_id: str,
    current_index: int,
    total_units: int,
    xp_award: int,
) -> bool:
    if unit_id in progress["completed_units"]:
        return False
    progress["completed_units"].append(unit_id)
    progress["total_xp"] += xp_award
    if current_index >= total_units - 1:
        progress["status"] = "Complete"
    else:
        progress["current_unit_index"] = current_index + 1
    return True


def track_selected_course(track_path: Path) -> None:
    metadata_path = track_path / "metadata.json"
    progress_path = track_path / "progress.json"
    metadata = load_json(metadata_path)
    progress = load_json(progress_path)
    validate_metadata(metadata)
    ensure_progress(progress)

    units = metadata["units"]
    current_index = int(progress["current_unit_index"])
    if not 0 <= current_index < len(units):
        raise ValueError("Current unit index is out of range.")

    unit = units[current_index]
    unit_path = track_path / unit["path"]

    print(f"\nTrack          : {metadata.get('title', 'Unknown')}")
    print(f"Provider       : {metadata.get('provider', 'Unknown')}")
    print(f"Knowledge path : {build_knowledge_path(metadata)}")
    print(f"Difficulty     : {metadata.get('difficulty', 'Unknown')}")
    print(f"Current unit   : {unit['title']}")
    print(f"Unit type      : {unit.get('source_type', 'manual')}")
    print(f"Progress       : {len(progress['completed_units'])}/{len(units)}")
    print(f"Track XP       : {progress['total_xp']}")
    print(f"Track status   : {progress['status']}")

    if progress["status"] == "Complete":
        print("\nThis track is already complete.")
        return
    if not unit_path.exists():
        raise FileNotFoundError(f"Unit folder does not exist:\n{unit_path}")

    evidence_status = check_evidence(
        unit_path,
        metadata["evidence_requirements"],
    )
    print("\nEvidence check")
    print("-" * 68)
    for name, passed in evidence_status.items():
        print(f"{name:<32}{'[PASS]' if passed else '[MISSING]'}")
    print("-" * 68)

    if not evidence_status or not all(evidence_status.values()):
        print("Unit is still in progress.")
        return

    total_xp = calculate_unit_xp(metadata, unit)
    mappings = resolve_competency_awards(metadata, unit)
    if not mappings:
        raise ValueError(
            "No competency mapping was found for this unit. Add "
            "competency_awards, section_competency_awards, "
            "default_competency_awards, or competency_id."
        )
    distribution = distribute_xp(total_xp, mappings)
    display_distribution(distribution)

    if not complete_progress(
        progress,
        unit["id"],
        current_index,
        len(units),
        total_xp,
    ):
        print("\nThis unit was already completed. No XP was awarded.")
        return

    operator_stats = update_operator_competencies(distribution)
    concept_resolution = resolve_concept_awards(metadata, unit)
    concept_distribution = distribute_concept_xp(total_xp, concept_resolution["concept_awards"])
    if concept_distribution:
        update_concept_progress(
            concept_resolution["capability_id"],
            concept_distribution,
            confidence=concept_resolution["mapping_confidence"],
            source=concept_resolution["mapping_source"],
        )
    record_completion(
        metadata=metadata,
        unit=unit,
        xp_award=total_xp,
        xp_distribution=distribution,
        concept_distribution=concept_distribution,
        mapping_confidence=concept_resolution["mapping_confidence"],
    )
    save_json(progress_path, progress)

    print("\nUNIT COMPLETE")
    print("-" * 68)
    print(f"+{total_xp} total XP awarded across {len(distribution)} competencies.")
    print(f"Operator Total XP: {operator_stats['total_xp']}")
    print(f"Operator Level: {operator_stats['level']}")
    print(
        f"Next Operator Level: {operator_stats['xp_to_next_level']} XP remaining "
        f"({operator_stats['level_progress']}%)"
    )
    print("\nprogress.json updated.")
    print("competencies.json updated.")
    print("stats.json updated.")
    print("history.json updated.")

    if progress["status"] == "Complete":
        print("\nTRACK COMPLETE")
    else:
        next_unit = units[int(progress["current_unit_index"])]
        print(f"\nNext unit: {next_unit['title']}")


def main() -> None:
    print("=" * 68)
    print("      OPERATOR ZERO LEARNING ENGINE — PROGRESSION v2")
    print("=" * 68)
    selected = select_track(discover_tracks())
    if selected is None:
        print("\nLearning Engine closed.")
        return
    try:
        track_selected_course(selected)
    except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
        print("\nLEARNING ENGINE ERROR")
        print(error)


if __name__ == "__main__":
    main()

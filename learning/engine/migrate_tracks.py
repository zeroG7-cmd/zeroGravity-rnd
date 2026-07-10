"""
Operator Zero Learning Engine
Legacy Track Migration Tool

Purpose
-------
Convert older lesson-based tracks into the unified unit-based format.

Old metadata:
    lessons

New metadata:
    unit_count
    units

Old progress:
    current_lesson
    completed_lessons

New progress:
    current_unit_index
    completed_units
"""

import json
from pathlib import Path
from typing import Any


TRACKS_ROOT = Path("learning/tracks")


def load_json(file_path: Path) -> dict[str, Any]:
    """Load a JSON file as a Python dictionary."""

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(file_path: Path, data: dict[str, Any]) -> None:
    """Save a dictionary as readable JSON."""

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def build_flat_units(lesson_count: int) -> list[dict[str, str]]:
    """
    Create unit definitions for an older day-based course.

    Example:
        day_01
        day_02
        ...
    """

    units = []

    for lesson_number in range(1, lesson_count + 1):
        unit_id = f"day_{lesson_number:02}"

        units.append(
            {
                "id": unit_id,
                "title": f"Day {lesson_number}",
                "path": unit_id,
                "source_type": "manual",
            }
        )

    return units


def migrate_metadata(
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Convert old metadata into the unified unit format."""

    changed = False

    if "units" not in metadata:
        lesson_count = int(
            metadata.get(
                "unit_count",
                metadata.get("lessons", 0),
            )
        )

        if lesson_count <= 0:
            raise ValueError(
                "Track has no valid lesson or unit count."
            )

        metadata["units"] = build_flat_units(lesson_count)
        metadata["unit_count"] = lesson_count
        metadata["structure_type"] = metadata.get(
            "structure_type",
            "flat",
        )

        changed = True

    if "unit_count" not in metadata:
        metadata["unit_count"] = len(metadata["units"])
        changed = True

    # The old field is no longer needed.
    if "lessons" in metadata:
        del metadata["lessons"]
        changed = True

    return metadata, changed


def migrate_progress(
    progress: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Convert old progress fields into unit-based progress."""

    changed = False
    units = metadata["units"]

    if "current_unit_index" not in progress:
        old_current_lesson = int(
            progress.get("current_lesson", 1)
        )

        progress["current_unit_index"] = max(
            old_current_lesson - 1,
            0,
        )

        changed = True

    if "completed_units" not in progress:
        completed_lessons = progress.get(
            "completed_lessons",
            [],
        )

        completed_units = []

        for lesson_number in completed_lessons:
            index = int(lesson_number) - 1

            if 0 <= index < len(units):
                completed_units.append(
                    units[index]["id"]
                )

        progress["completed_units"] = completed_units
        changed = True

    progress.setdefault("total_xp", 0)
    progress.setdefault("status", "In Progress")

    if "current_lesson" in progress:
        del progress["current_lesson"]
        changed = True

    if "completed_lessons" in progress:
        del progress["completed_lessons"]
        changed = True

    return progress, changed


def migrate_track(track_path: Path) -> None:
    """Migrate one learning track."""

    metadata_path = track_path / "metadata.json"
    progress_path = track_path / "progress.json"

    metadata = load_json(metadata_path)
    progress = load_json(progress_path)

    metadata, metadata_changed = migrate_metadata(metadata)

    progress, progress_changed = migrate_progress(
        progress,
        metadata,
    )

    if metadata_changed:
        save_json(metadata_path, metadata)

    if progress_changed:
        save_json(progress_path, progress)

    if metadata_changed or progress_changed:
        print(f"[MIGRATED] {track_path}")
    else:
        print(f"[CURRENT]  {track_path}")


def discover_tracks() -> list[Path]:
    """Find every valid learning track."""

    tracks = []

    for metadata_path in TRACKS_ROOT.rglob("metadata.json"):
        track_path = metadata_path.parent

        if (track_path / "progress.json").exists():
            tracks.append(track_path)

    return sorted(tracks)


def main() -> None:
    """Migrate every learning track."""

    print("=" * 64)
    print("       OPERATOR ZERO TRACK MIGRATION TOOL")
    print("=" * 64)

    tracks = discover_tracks()

    if not tracks:
        print("No learning tracks found.")
        return

    for track_path in tracks:
        migrate_track(track_path)

    print()
    print("Migration complete.")


if __name__ == "__main__":
    main()
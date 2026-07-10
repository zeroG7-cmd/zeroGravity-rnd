"""
Operator Zero Learning Engine
Universal Tracker v5.0

All tracks now use one data model:

Metadata:
- units
- unit_count
- evidence_requirements

Progress:
- current_unit_index
- completed_units
- total_xp
- status
"""

import json
from pathlib import Path
from typing import Any


TRACKS_ROOT = Path("learning/tracks")
XP_PER_UNIT = 40


# ============================================================
# JSON STORAGE
# ============================================================

def load_json(file_path: Path) -> dict[str, Any]:
    """Load JSON as a Python dictionary."""

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Required file not found:\n{file_path}"
        ) from error

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON inside:\n{file_path}\n\n{error}"
        ) from error


def save_json(
    file_path: Path,
    data: dict[str, Any],
) -> None:
    """Save a dictionary as formatted JSON."""

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# ============================================================
# TRACK DISCOVERY
# ============================================================

def discover_tracks() -> list[Path]:
    """Find every valid learning track."""

    tracks = []

    if not TRACKS_ROOT.exists():
        return tracks

    for metadata_path in TRACKS_ROOT.rglob("metadata.json"):
        track_path = metadata_path.parent

        if (track_path / "progress.json").exists():
            tracks.append(track_path)

    return sorted(tracks)


def build_knowledge_path(
    metadata: dict[str, Any],
) -> str:
    """Build the display path for a track."""

    hierarchy = metadata.get("hierarchy", [])

    if hierarchy:
        parts = [
            metadata.get("stat", "Unknown"),
            *hierarchy,
        ]
    else:
        # Compatibility for tracks not yet using hierarchy.
        parts = [
            metadata.get("stat", "Unknown"),
            metadata.get("branch"),
            metadata.get("category"),
            metadata.get("skill"),
        ]

    return " > ".join(
        str(part)
        for part in parts
        if part
    )


def select_track(
    track_paths: list[Path],
) -> Path | None:
    """Display tracks and ask the operator to select one."""

    if not track_paths:
        print("No learning tracks found.")
        return None

    print()
    print("Available learning tracks")
    print("-" * 68)

    for index, track_path in enumerate(
        track_paths,
        start=1,
    ):
        metadata = load_json(
            track_path / "metadata.json"
        )

        title = metadata.get(
            "title",
            track_path.name,
        )

        knowledge_path = build_knowledge_path(
            metadata
        )

        print(f"{index}. {title}")
        print(f"   {knowledge_path}")

    print()

    while True:
        selection = input(
            "Select a track number, or enter Q to quit: "
        ).strip()

        if selection.lower() == "q":
            return None

        try:
            selected_number = int(selection)

            if 1 <= selected_number <= len(track_paths):
                return track_paths[selected_number - 1]

            print(
                f"Choose a number from 1 to "
                f"{len(track_paths)}."
            )

        except ValueError:
            print("Enter a valid number or Q.")


# ============================================================
# VALIDATION
# ============================================================

def validate_metadata(
    metadata: dict[str, Any],
) -> None:
    """Ensure metadata uses the unified format."""

    units = metadata.get("units")
    requirements = metadata.get(
        "evidence_requirements"
    )

    if not isinstance(units, list) or not units:
        raise ValueError(
            "metadata.json has no valid 'units' list.\n"
            "Run migrate_tracks.py first."
        )

    if not isinstance(requirements, list) or not requirements:
        raise ValueError(
            "metadata.json has no evidence requirements."
        )


def ensure_progress_structure(
    progress: dict[str, Any],
) -> None:
    """Ensure progress contains the unified fields."""

    progress.setdefault("current_unit_index", 0)
    progress.setdefault("completed_units", [])
    progress.setdefault("total_xp", 0)
    progress.setdefault("status", "In Progress")


# ============================================================
# EVIDENCE CHECKING
# ============================================================

def file_has_content(file_path: Path) -> bool:
    """
    Return True when evidence exists and is non-empty.

    Text files are checked for actual text.
    Binary files such as images only need a non-zero size.
    """

    if not file_path.exists():
        return False

    if not file_path.is_file():
        return False

    if file_path.stat().st_size == 0:
        return False

    try:
        content = file_path.read_text(
            encoding="utf-8"
        ).strip()

        return bool(content)

    except UnicodeDecodeError:
        return file_path.stat().st_size > 0


def check_evidence(
    unit_path: Path,
    requirements: list[dict[str, str]],
) -> dict[str, bool]:
    """Check every evidence requirement."""

    status = {}

    for requirement in requirements:
        name = requirement["name"]
        relative_path = Path(
            requirement["path"]
        )

        status[name] = file_has_content(
            unit_path / relative_path
        )

    return status


def unit_is_complete(
    evidence_status: dict[str, bool],
) -> bool:
    """Return True only when every requirement passes."""

    if not evidence_status:
        return False

    return all(evidence_status.values())


# ============================================================
# PROGRESS
# ============================================================

def complete_current_unit(
    progress: dict[str, Any],
    unit_id: str,
    current_index: int,
    total_units: int,
) -> bool:
    """
    Mark the current unit complete and award XP once.
    """

    completed_units = progress["completed_units"]

    if unit_id in completed_units:
        return False

    completed_units.append(unit_id)
    progress["total_xp"] += XP_PER_UNIT

    if current_index >= total_units - 1:
        progress["status"] = "Complete"
    else:
        progress["current_unit_index"] = (
            current_index + 1
        )

    return True


# ============================================================
# DISPLAY
# ============================================================

def display_header() -> None:
    """Display the application heading."""

    print("=" * 68)
    print("              OPERATOR ZERO LEARNING ENGINE")
    print("=" * 68)


def display_track_information(
    metadata: dict[str, Any],
    progress: dict[str, Any],
    current_unit: dict[str, Any],
    track_path: Path,
) -> None:
    """Display the selected track state."""

    units = metadata["units"]
    completed_count = len(
        progress["completed_units"]
    )

    print()
    print(f"Track          : {metadata.get('title', 'Unknown')}")
    print(f"Provider       : {metadata.get('provider', 'Unknown')}")
    print(f"Knowledge path : {build_knowledge_path(metadata)}")
    print(f"Difficulty     : {metadata.get('difficulty', 'Unknown')}")
    print(f"Track folder   : {track_path}")
    print()
    print(f"Current unit   : {current_unit['title']}")
    print(f"Unit path      : {current_unit['path']}")
    print(f"Unit type      : {current_unit.get('source_type', 'manual')}")
    print(f"Progress       : {completed_count}/{len(units)}")
    print(f"Total XP       : {progress['total_xp']}")
    print(f"Track status   : {progress['status']}")


def display_evidence(
    evidence_status: dict[str, bool],
) -> None:
    """Display each evidence result."""

    print()
    print("Evidence check")
    print("-" * 68)

    for evidence_name, passed in evidence_status.items():
        label = "[PASS]" if passed else "[MISSING]"
        print(f"{evidence_name:<32}{label}")

    print("-" * 68)
    print(
        f"Evidence complete : "
        f"{sum(evidence_status.values())}/"
        f"{len(evidence_status)}"
    )


# ============================================================
# TRACKING CYCLE
# ============================================================

def track_selected_course(
    track_path: Path,
) -> None:
    """Run one tracking cycle."""

    metadata_path = track_path / "metadata.json"
    progress_path = track_path / "progress.json"

    metadata = load_json(metadata_path)
    progress = load_json(progress_path)

    validate_metadata(metadata)
    ensure_progress_structure(progress)

    units = metadata["units"]
    requirements = metadata["evidence_requirements"]

    current_index = int(
        progress["current_unit_index"]
    )

    if current_index < 0 or current_index >= len(units):
        print()
        print("ERROR")
        print("Current unit index is out of range.")
        return

    current_unit = units[current_index]
    unit_path = track_path / current_unit["path"]

    display_track_information(
        metadata=metadata,
        progress=progress,
        current_unit=current_unit,
        track_path=track_path,
    )

    if progress["status"] == "Complete":
        print()
        print("This track is already complete.")
        return

    if not unit_path.exists():
        print()
        print("ERROR")
        print(f"Unit folder does not exist:\n{unit_path}")
        return

    evidence_status = check_evidence(
        unit_path=unit_path,
        requirements=requirements,
    )

    display_evidence(evidence_status)

    if not unit_is_complete(evidence_status):
        print()
        print("Unit is still in progress.")
        print("Complete the missing evidence and run again.")
        return

    progress_changed = complete_current_unit(
        progress=progress,
        unit_id=current_unit["id"],
        current_index=current_index,
        total_units=len(units),
    )

    if not progress_changed:
        print()
        print("This unit was already completed.")
        print("No additional XP was awarded.")
        return

    save_json(progress_path, progress)

    skill = metadata.get("skill", "Skill")

    print()
    print("UNIT COMPLETE")
    print(f"+{XP_PER_UNIT} {skill} XP awarded.")
    print("progress.json has been updated.")

    if progress["status"] == "Complete":
        print()
        print("TRACK COMPLETE")
        return

    next_index = int(
        progress["current_unit_index"]
    )

    next_unit = units[next_index]

    print(f"Next unit: {next_unit['title']}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Start the Learning Engine."""

    display_header()

    track_paths = discover_tracks()
    selected_track = select_track(track_paths)

    if selected_track is None:
        print()
        print("Learning Engine closed.")
        return

    try:
        track_selected_course(selected_track)

    except (FileNotFoundError, ValueError, KeyError) as error:
        print()
        print("LEARNING ENGINE ERROR")
        print(error)


if __name__ == "__main__":
    main()
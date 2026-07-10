"""
Operator Zero R&D Learning Engine
Universal Track Tracker v3.0

Purpose
-------
This script:

1. Searches the learning/tracks directory.
2. Finds every folder containing metadata.json and progress.json.
3. Displays all available learning tracks.
4. Lets the operator select a track.
5. Loads that track's metadata and progress.
6. Checks the current lesson evidence.
7. Awards XP once when the lesson is complete.
8. Updates progress.json.
9. Moves to the next lesson.

This means the tracker is no longer hardcoded to one Python course.
It can manage Python, HTML, SQL, networking, ROS2, CAD, and future tracks.
"""

import json
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

# Root directory containing every Operator Zero learning track.
TRACKS_ROOT = Path("learning/tracks")

# XP awarded for completing one lesson.
XP_PER_LESSON = 40

# Evidence required for a lesson to count as complete.
REQUIRED_EVIDENCE = {
    "notes": Path("notes.md"),
    "solution": Path("solution.py"),
    "reflection": Path("reflection.md"),
    "terminal_output": Path("evidence/terminal_output.txt"),
}


# ============================================================
# JSON STORAGE
# ============================================================

def load_json(file_path: Path) -> dict[str, Any]:
    """
    Read a JSON file and return its contents as a Python dictionary.
    """

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Required JSON file was not found:\n{file_path}"
        ) from error

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON inside:\n{file_path}\n\n"
            f"JSON error: {error}"
        ) from error


def save_json(file_path: Path, data: dict[str, Any]) -> None:
    """
    Save a Python dictionary into a readable JSON file.
    """

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# ============================================================
# TRACK DISCOVERY
# ============================================================

def discover_tracks() -> list[Path]:
    """
    Search recursively beneath learning/tracks.

    A folder counts as a valid learning track when it contains:

    - metadata.json
    - progress.json
    """

    discovered_tracks = []

    if not TRACKS_ROOT.exists():
        return discovered_tracks

    for metadata_path in TRACKS_ROOT.rglob("metadata.json"):
        track_path = metadata_path.parent
        progress_path = track_path / "progress.json"

        if progress_path.exists():
            discovered_tracks.append(track_path)

    return sorted(discovered_tracks)


def select_track(track_paths: list[Path]) -> Path | None:
    """
    Display available tracks and ask the operator to choose one.

    Returns:
        Path to the selected track.

    Returns None when no valid selection is made.
    """

    if not track_paths:
        print("No learning tracks were found.")
        print(f"Expected tracks beneath: {TRACKS_ROOT}")
        return None

    print()
    print("Available learning tracks")
    print("-" * 64)

    for index, track_path in enumerate(track_paths, start=1):
        try:
            metadata = load_json(track_path / "metadata.json")

            title = metadata.get("title", track_path.name)
            skill = metadata.get("skill", "Unknown skill")
            branch = metadata.get("branch", "Unknown branch")
            category = metadata.get("category", "Unknown category")

            print(
                f"{index}. {title}\n"
                f"   {branch} > {category} > {skill}"
            )

        except (FileNotFoundError, ValueError) as error:
            print(f"{index}. Invalid track: {track_path}")
            print(f"   {error}")

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
                f"Choose a number between 1 and {len(track_paths)}."
            )

        except ValueError:
            print("Enter a valid track number or Q.")


# ============================================================
# EVIDENCE CHECKING
# ============================================================

def file_has_content(file_path: Path) -> bool:
    """
    Return True only when the file exists and contains real text.

    Empty placeholder files do not count as evidence.
    """

    if not file_path.exists():
        return False

    if not file_path.is_file():
        return False

    try:
        content = file_path.read_text(encoding="utf-8").strip()
        return bool(content)

    except UnicodeDecodeError:
        return False


def check_evidence(lesson_path: Path) -> dict[str, bool]:
    """
    Check every required evidence file in the current lesson.
    """

    evidence_status = {}

    for evidence_name, relative_path in REQUIRED_EVIDENCE.items():
        full_path = lesson_path / relative_path
        evidence_status[evidence_name] = file_has_content(full_path)

    return evidence_status


def lesson_is_complete(evidence_status: dict[str, bool]) -> bool:
    """
    Return True only when every required evidence item is complete.
    """

    return all(evidence_status.values())


# ============================================================
# PROGRESS MANAGEMENT
# ============================================================

def ensure_progress_structure(progress: dict[str, Any]) -> None:
    """
    Add required fields if progress.json is missing any of them.
    """

    progress.setdefault("current_lesson", 1)
    progress.setdefault("completed_lessons", [])
    progress.setdefault("total_xp", 0)
    progress.setdefault("status", "In Progress")


def complete_current_lesson(
    progress: dict[str, Any],
    lesson_number: int,
    total_lessons: int,
) -> bool:
    """
    Complete the current lesson and award XP.

    Returns False if the lesson was already completed.
    This prevents duplicate XP awards.
    """

    completed_lessons = progress["completed_lessons"]

    if lesson_number in completed_lessons:
        return False

    completed_lessons.append(lesson_number)
    completed_lessons.sort()

    progress["total_xp"] += XP_PER_LESSON

    if lesson_number >= total_lessons:
        progress["current_lesson"] = total_lessons
        progress["status"] = "Complete"
    else:
        progress["current_lesson"] = lesson_number + 1
        progress["status"] = "In Progress"

    return True


# ============================================================
# DISPLAY
# ============================================================

def status_symbol(is_complete: bool) -> str:
    """
    Convert a Boolean value into a readable terminal label.
    """

    return "[PASS]" if is_complete else "[MISSING]"


def display_header() -> None:
    """
    Display the Learning Engine heading.
    """

    print("=" * 64)
    print("              OPERATOR ZERO LEARNING ENGINE")
    print("=" * 64)


def display_track_information(
    metadata: dict[str, Any],
    progress: dict[str, Any],
    lesson_folder: str,
    track_path: Path,
) -> None:
    """
    Display the selected track's current state.
    """

    total_lessons = int(metadata.get("lessons", 0))
    completed_count = len(progress["completed_lessons"])

    print()
    print(f"Track          : {metadata.get('title', 'Unknown')}")
    print(f"Provider       : {metadata.get('provider', 'Unknown')}")
    print(f"Stat           : {metadata.get('stat', 'Unknown')}")
    print(f"Branch         : {metadata.get('branch', 'Unknown')}")
    print(f"Category       : {metadata.get('category', 'Unknown')}")
    print(f"Skill          : {metadata.get('skill', 'Unknown')}")
    print(f"Difficulty     : {metadata.get('difficulty', 'Unknown')}")
    print(f"Track folder   : {track_path}")
    print()
    print(f"Current lesson : {lesson_folder}")
    print(f"Progress       : {completed_count}/{total_lessons}")
    print(f"Total XP       : {progress['total_xp']}")
    print(f"Track status   : {progress['status']}")


def display_evidence(evidence_status: dict[str, bool]) -> None:
    """
    Display every evidence requirement.
    """

    print()
    print("Evidence check")
    print("-" * 64)

    for evidence_name, is_complete in evidence_status.items():
        readable_name = evidence_name.replace("_", " ").title()

        print(
            f"{readable_name:<24}"
            f"{status_symbol(is_complete)}"
        )


# ============================================================
# TRACKING CYCLE
# ============================================================

def track_selected_course(track_path: Path) -> None:
    """
    Run one complete tracking cycle for the chosen course.
    """

    metadata_path = track_path / "metadata.json"
    progress_path = track_path / "progress.json"

    metadata = load_json(metadata_path)
    progress = load_json(progress_path)

    ensure_progress_structure(progress)

    total_lessons = int(metadata["lessons"])
    current_lesson = int(progress["current_lesson"])

    lesson_folder = f"day_{current_lesson:02}"
    lesson_path = track_path / lesson_folder

    display_track_information(
        metadata=metadata,
        progress=progress,
        lesson_folder=lesson_folder,
        track_path=track_path,
    )

    if progress["status"] == "Complete":
        print()
        print("This learning track is already complete.")
        return

    if not lesson_path.exists():
        print()
        print("ERROR")
        print(f"Lesson folder does not exist:\n{lesson_path}")
        return

    evidence_status = check_evidence(lesson_path)

    display_evidence(evidence_status)

    completed_evidence = sum(evidence_status.values())
    required_evidence = len(evidence_status)

    print("-" * 64)
    print(
        f"Evidence complete : "
        f"{completed_evidence}/{required_evidence}"
    )

    if not lesson_is_complete(evidence_status):
        print()
        print("Lesson is still in progress.")
        print("Complete the missing evidence and run the tracker again.")
        return

    progress_changed = complete_current_lesson(
        progress=progress,
        lesson_number=current_lesson,
        total_lessons=total_lessons,
    )

    if not progress_changed:
        print()
        print("This lesson was already completed.")
        print("No additional XP was awarded.")
        return

    save_json(progress_path, progress)

    print()
    print("LESSON COMPLETE")
    print(f"+{XP_PER_LESSON} {metadata['skill']} XP awarded.")
    print("progress.json has been updated.")

    if progress["status"] == "Complete":
        print()
        print("TRACK COMPLETE")
        print(f"You completed all {total_lessons} lessons.")
    else:
        next_lesson = int(progress["current_lesson"])
        next_folder = f"day_{next_lesson:02}"

        print(f"Next lesson: {next_folder}")


# ============================================================
# MAIN PROGRAM
# ============================================================

def main() -> None:
    """
    Discover tracks, let the operator choose one,
    and run the tracker against that selection.
    """

    display_header()

    track_paths = discover_tracks()
    selected_track = select_track(track_paths)

    if selected_track is None:
        print()
        print("Learning Engine closed.")
        return

    track_selected_course(selected_track)


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
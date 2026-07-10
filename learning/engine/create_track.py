"""
Operator Zero Learning Engine
Track Generator v1.0

Purpose
-------
Creates a complete learning-track structure automatically.

It generates:

- The track directory
- metadata.json
- progress.json
- README.md
- Lesson directories
- notes.md
- solution.py
- reflection.md
- evidence/terminal_output.txt

This script uses pathlib, so it works on:
- Windows
- Linux
- Raspberry Pi
"""

import json
import re
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

# All generated learning tracks will live inside this directory.
TRACKS_ROOT = Path("learning/tracks")


# ============================================================
# TEXT AND PATH HELPERS
# ============================================================

def make_slug(text: str) -> str:
    """
    Convert human-readable text into a safe folder or ID name.

    Example:
        "30 Days of Python" -> "30_days_of_python"
        "ROS2 Foundations!" -> "ros2_foundations"
    """

    cleaned_text = text.strip().lower()

    # Replace characters that are not letters or numbers with underscores.
    cleaned_text = re.sub(r"[^a-z0-9]+", "_", cleaned_text)

    # Remove underscores from the beginning and end.
    return cleaned_text.strip("_")


def ask_required(prompt: str) -> str:
    """
    Keep asking until the user enters a non-empty value.
    """

    while True:
        answer = input(prompt).strip()

        if answer:
            return answer

        print("This field cannot be empty.")


def ask_positive_integer(prompt: str) -> int:
    """
    Keep asking until the user enters a positive whole number.
    """

    while True:
        answer = input(prompt).strip()

        try:
            number = int(answer)

            if number > 0:
                return number

            print("Enter a number greater than zero.")

        except ValueError:
            print("Enter a valid whole number.")


# ============================================================
# JSON STORAGE
# ============================================================

def save_json(file_path: Path, data: dict[str, Any]) -> None:
    """
    Save a Python dictionary as a readable JSON file.
    """

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# ============================================================
# LESSON CREATION
# ============================================================

def create_lesson(lesson_path: Path) -> None:
    """
    Create one lesson directory and its evidence files.
    """

    evidence_path = lesson_path / "evidence"

    lesson_path.mkdir(parents=True, exist_ok=True)
    evidence_path.mkdir(parents=True, exist_ok=True)

    # touch() creates a file when it does not already exist.
    # It does not erase an existing file.
    (lesson_path / "notes.md").touch(exist_ok=True)
    (lesson_path / "solution.py").touch(exist_ok=True)
    (lesson_path / "reflection.md").touch(exist_ok=True)
    (evidence_path / "terminal_output.txt").touch(exist_ok=True)


def create_all_lessons(track_path: Path, lesson_count: int) -> None:
    """
    Generate every numbered lesson folder.

    Example:
        day_01
        day_02
        ...
        day_30
    """

    for lesson_number in range(1, lesson_count + 1):
        lesson_folder = f"day_{lesson_number:02}"
        lesson_path = track_path / lesson_folder

        create_lesson(lesson_path)


# ============================================================
# TRACK FILES
# ============================================================

def create_metadata(
    track_path: Path,
    track_id: str,
    title: str,
    provider: str,
    stat: str,
    branch: str,
    category: str,
    skill: str,
    difficulty: str,
    lesson_count: int,
    resource_path: str,
) -> None:
    """
    Create metadata.json.

    Metadata describes what the track is.
    It does not store the user's progress.
    """

    metadata = {
        "id": track_id,
        "title": title,
        "provider": provider,
        "stat": stat,
        "branch": branch,
        "category": category,
        "skill": skill,
        "difficulty": difficulty,
        "lessons": lesson_count,
        "resource": resource_path,
    }

    save_json(track_path / "metadata.json", metadata)


def create_progress(track_path: Path) -> None:
    """
    Create the initial progress.json file.

    This file changes as the operator completes lessons.
    """

    progress = {
        "current_lesson": 1,
        "completed_lessons": [],
        "total_xp": 0,
        "status": "In Progress",
    }

    save_json(track_path / "progress.json", progress)


def create_readme(
    track_path: Path,
    title: str,
    skill: str,
    lesson_count: int,
) -> None:
    """
    Create a simple human-readable README for the track.
    """

    readme = f"""# {title}

## Operator Zero Learning Track

- **Skill:** {skill}
- **Lessons:** {lesson_count}
- **Status:** In Progress
- **Starting XP:** 0

## Learning Workflow

1. Study the source lesson.
2. Write personal notes.
3. Complete the exercise or practical task.
4. Run and test the solution.
5. Save terminal evidence.
6. Write a reflection.
7. Run the Learning Engine tracker.
"""

    (track_path / "README.md").write_text(
        readme,
        encoding="utf-8",
    )


# ============================================================
# MAIN PROGRAM
# ============================================================

def main() -> None:
    """
    Collect track information and generate the complete structure.
    """

    print("=" * 58)
    print("       OPERATOR ZERO LEARNING TRACK GENERATOR")
    print("=" * 58)
    print()

    title = ask_required("Track title: ")
    provider = input("Provider or author: ").strip()
    stat = ask_required("Main stat [INT]: ").strip() or "INT"
    branch = ask_required("Branch: ")
    category = ask_required("Category: ")
    skill = ask_required("Skill: ")
    difficulty = input("Difficulty [Beginner]: ").strip() or "Beginner"
    lesson_count = ask_positive_integer("Number of lessons: ")
    resource_path = input("Resource path or URL: ").strip()

    # Convert names into safe folder names.
    branch_slug = make_slug(branch)
    category_slug = make_slug(category)
    skill_slug = make_slug(skill)
    track_slug = make_slug(title)

    track_id = f"{skill_slug}_{track_slug}"

    track_path = (
        TRACKS_ROOT
        / branch_slug
        / category_slug
        / skill_slug
        / track_slug
    )

    print()
    print(f"Track location: {track_path}")

    # Prevent accidental replacement of an existing track.
    if track_path.exists():
        print()
        print("ERROR: This learning track already exists.")
        print("No files were changed.")
        return

    track_path.mkdir(parents=True)

    create_metadata(
        track_path=track_path,
        track_id=track_id,
        title=title,
        provider=provider,
        stat=stat,
        branch=branch,
        category=category,
        skill=skill,
        difficulty=difficulty,
        lesson_count=lesson_count,
        resource_path=resource_path,
    )

    create_progress(track_path)
    create_readme(track_path, title, skill, lesson_count)
    create_all_lessons(track_path, lesson_count)

    print()
    print("TRACK CREATED SUCCESSFULLY")
    print("-" * 58)
    print(f"Track ID       : {track_id}")
    print(f"Track title    : {title}")
    print(f"Skill          : {skill}")
    print(f"Lessons created: {lesson_count}")
    print(f"Location       : {track_path}")


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
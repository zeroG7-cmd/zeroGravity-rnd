"""
Operator Zero Learning Engine
Knowledge-Tree Track Generator v3.0

Purpose
-------
This program creates a complete learning track from user input.

It can:

1. Build missing skill-tree folders automatically.
2. Support skill trees of different depths.
3. Create flat or nested learning-unit structures.
4. Ask what evidence files each track requires.
5. Generate metadata.json and progress.json.
6. Register the external resource in the learning catalog.

Examples
--------

Python hierarchy:
    Software Engineering, Programming Languages, Python

Linux hierarchy:
    Robotics, Robot Software, Robot Middleware, Linux

Computer Vision hierarchy:
    Robotics, Perception, Computer Vision

SQL hierarchy:
    Data & Databases, SQL
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# SYSTEM PATHS
# ============================================================

LEARNING_ROOT = Path("learning")
TRACKS_ROOT = LEARNING_ROOT / "tracks"
CATALOG_ROOT = LEARNING_ROOT / "catalog"
RESOURCE_CATALOG_PATH = CATALOG_ROOT / "resources.json"


# ============================================================
# INPUT HELPERS
# ============================================================

def ask_required(prompt: str) -> str:
    """Keep asking until a non-empty value is entered."""

    while True:
        value = input(prompt).strip()

        if value:
            return value

        print("This field cannot be empty.")


def ask_positive_integer(prompt: str) -> int:
    """Keep asking until a positive whole number is entered."""

    while True:
        value = input(prompt).strip()

        try:
            number = int(value)

            if number > 0:
                return number

            print("Enter a number greater than zero.")

        except ValueError:
            print("Enter a valid whole number.")


def ask_yes_no(prompt: str, default: bool | None = None) -> bool:
    """
    Ask a yes/no question.

    default=True means pressing Enter selects yes.
    default=False means pressing Enter selects no.
    """

    if default is True:
        suffix = " [Y/n]: "
    elif default is False:
        suffix = " [y/N]: "
    else:
        suffix = " [y/n]: "

    while True:
        value = input(prompt + suffix).strip().lower()

        if not value and default is not None:
            return default

        if value in {"y", "yes"}:
            return True

        if value in {"n", "no"}:
            return False

        print("Enter y or n.")


def make_slug(text: str) -> str:
    """
    Convert human-readable text into a safe folder name.

    Examples:
        Software Engineering -> software_engineering
        Computer Vision      -> computer_vision
        Data & Databases     -> data_databases
    """

    text = text.strip().lower()
    text = text.replace("&", " and ")
    text = text.replace("c++", "cpp")

    text = re.sub(r"[^a-z0-9]+", "_", text)

    return text.strip("_")


def collect_hierarchy() -> list[str]:
    """
    Collect a variable-depth skill-tree path.

    Example input:
        Robotics, Perception, Computer Vision

    Result:
        [
            "Robotics",
            "Perception",
            "Computer Vision"
        ]
    """

    print()
    print("Knowledge-tree hierarchy")
    print("-" * 64)
    print("Enter every level beneath the main stat.")
    print()
    print("Python example:")
    print("Software Engineering, Programming Languages, Python")
    print()
    print("Linux example:")
    print("Robotics, Robot Software, Robot Middleware, Linux")
    print()

    while True:
        raw_path = ask_required(
            "Hierarchy levels, separated by commas: "
        )

        hierarchy = [
            level.strip()
            for level in raw_path.split(",")
            if level.strip()
        ]

        if hierarchy:
            return hierarchy

        print("Enter at least one hierarchy level.")


# ============================================================
# JSON STORAGE
# ============================================================

def load_json(
    file_path: Path,
    default: Any,
) -> Any:
    """
    Load JSON.

    If the file does not exist, return the supplied default.
    """

    if not file_path.exists():
        return default

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON inside:\n{file_path}\n\n{error}"
        ) from error


def save_json(
    file_path: Path,
    data: Any,
) -> None:
    """Save data as readable JSON."""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# ============================================================
# EVIDENCE CONFIGURATION
# ============================================================

def collect_evidence_requirements() -> list[dict[str, str]]:
    """
    Ask what evidence each learning unit must contain.

    Examples:

    Python:
        Notes              -> notes.md
        Python Solution    -> solution.py
        Reflection         -> reflection.md
        Terminal Output    -> evidence/terminal_output.txt

    Linux:
        Linux Notes        -> notes.md
        Commands Practised -> commands.sh
        Reflection         -> reflection.md
        Terminal Output    -> evidence/terminal_output.txt

    HTML:
        HTML Page          -> index.html
        Notes              -> notes.md
        Reflection         -> reflection.md
    """

    requirements: list[dict[str, str]] = []

    print()
    print("Evidence requirements")
    print("-" * 64)

    while True:
        evidence_name = ask_required(
            "Evidence display name: "
        )

        evidence_path = ask_required(
            "Evidence file path: "
        )

        requirements.append(
            {
                "name": evidence_name,
                "path": evidence_path.replace("\\", "/"),
            }
        )

        if not ask_yes_no(
            "Add another evidence requirement?",
            default=True,
        ):
            break

    return requirements


# ============================================================
# LEARNING-UNIT STRUCTURES
# ============================================================

def create_flat_units() -> list[dict[str, str]]:
    """
    Create a simple structure:

        day_01
        day_02
        day_03
    """

    unit_count = ask_positive_integer(
        "Number of learning units: "
    )

    prefix = (
        input("Unit prefix [day]: ").strip()
        or "day"
    )

    prefix_slug = make_slug(prefix)

    units: list[dict[str, str]] = []

    for number in range(1, unit_count + 1):
        folder_name = f"{prefix_slug}_{number:02}"

        units.append(
            {
                "id": folder_name,
                "title": f"{prefix.title()} {number}",
                "path": folder_name,
            }
        )

    return units


def create_nested_units() -> list[dict[str, str]]:
    """
    Create a nested structure:

        week_01/
            day_01/
                breakfast/
                lunch/
                dinner/
    """

    week_count = ask_positive_integer(
        "Number of weeks: "
    )

    days_per_week = ask_positive_integer(
        "Days per week: "
    )

    raw_sessions = ask_required(
        "Session names separated by commas: "
    )

    sessions = [
        session.strip()
        for session in raw_sessions.split(",")
        if session.strip()
    ]

    units: list[dict[str, str]] = []

    for week in range(1, week_count + 1):
        for day in range(1, days_per_week + 1):
            for session in sessions:
                session_slug = make_slug(session)

                unit_id = (
                    f"week_{week:02}_"
                    f"day_{day:02}_"
                    f"{session_slug}"
                )

                unit_path = (
                    f"week_{week:02}/"
                    f"day_{day:02}/"
                    f"{session_slug}"
                )

                unit_title = (
                    f"Week {week} - "
                    f"Day {day} - "
                    f"{session.title()}"
                )

                units.append(
                    {
                        "id": unit_id,
                        "title": unit_title,
                        "path": unit_path,
                    }
                )

    return units


def choose_structure() -> tuple[str, list[dict[str, str]]]:
    """Choose the course folder structure."""

    print()
    print("Learning-resource structure")
    print("-" * 64)
    print("1. Flat")
    print("   day_01, day_02, day_03")
    print()
    print("2. Nested")
    print("   week_01/day_01/breakfast")
    print()

    while True:
        selection = input("Choose structure [1/2]: ").strip()

        if selection == "1":
            return "flat", create_flat_units()

        if selection == "2":
            return "nested", create_nested_units()

        print("Enter 1 or 2.")


# ============================================================
# DIRECTORY AND FILE CREATION
# ============================================================

def build_track_path(
    stat: str,
    hierarchy: list[str],
    track_title: str,
) -> Path:
    """
    Build a track path from the skill tree.

    Example:

        INT
        Robotics
        Perception
        Computer Vision
        OpenCV Fundamentals

    Becomes:

        learning/tracks/int/robotics/perception/
        computer_vision/opencv_fundamentals
    """

    path = TRACKS_ROOT / make_slug(stat)

    for level in hierarchy:
        path = path / make_slug(level)

    path = path / make_slug(track_title)

    return path


def create_evidence_files(
    unit_path: Path,
    requirements: list[dict[str, str]],
) -> None:
    """Create the required files for one learning unit."""

    for requirement in requirements:
        relative_path = Path(requirement["path"])
        file_path = unit_path / relative_path

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.touch(exist_ok=True)


def create_all_units(
    track_path: Path,
    units: list[dict[str, str]],
    requirements: list[dict[str, str]],
) -> None:
    """Create every unit and its evidence files."""

    for unit in units:
        unit_path = track_path / unit["path"]

        unit_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        create_evidence_files(
            unit_path=unit_path,
            requirements=requirements,
        )


# ============================================================
# TRACK DATA
# ============================================================

def create_metadata(
    track_path: Path,
    *,
    title: str,
    provider: str,
    stat: str,
    hierarchy: list[str],
    difficulty: str,
    resource: str,
    structure_type: str,
    units: list[dict[str, str]],
    evidence_requirements: list[dict[str, str]],
) -> dict[str, Any]:
    """Create metadata.json."""

    skill = hierarchy[-1]

    metadata = {
        "id": f"{make_slug(skill)}_{make_slug(title)}",
        "title": title,
        "provider": provider,
        "stat": stat,
        "hierarchy": hierarchy,
        "domain": hierarchy[0],
        "skill": skill,
        "difficulty": difficulty,
        "resource": resource,
        "structure_type": structure_type,
        "unit_count": len(units),
        "units": units,
        "evidence_requirements": evidence_requirements,
    }

    save_json(
        track_path / "metadata.json",
        metadata,
    )

    return metadata


def create_progress(track_path: Path) -> None:
    """Create the initial progress state."""

    progress = {
        "current_unit_index": 0,
        "completed_units": [],
        "total_xp": 0,
        "status": "In Progress",
    }

    save_json(
        track_path / "progress.json",
        progress,
    )


def create_readme(
    track_path: Path,
    metadata: dict[str, Any],
) -> None:
    """Create a readable track overview."""

    hierarchy_text = " > ".join(
        [metadata["stat"], *metadata["hierarchy"]]
    )

    content = f"""# {metadata["title"]}

## Operator Zero Learning Track

- **Knowledge path:** {hierarchy_text}
- **Provider:** {metadata["provider"]}
- **Difficulty:** {metadata["difficulty"]}
- **Learning units:** {metadata["unit_count"]}
- **Structure:** {metadata["structure_type"]}
- **Status:** In Progress
- **Starting XP:** 0

## Resource

{metadata["resource"]}

## Workflow

1. Study the source material.
2. Complete the practical work.
3. Save the required evidence.
4. Write notes and reflection where required.
5. Run the Operator Zero Learning Engine.
"""

    (track_path / "README.md").write_text(
        content,
        encoding="utf-8",
    )


# ============================================================
# RESOURCE CATALOG
# ============================================================

def register_resource(
    metadata: dict[str, Any],
    track_path: Path,
) -> None:
    """
    Add the resource to learning/catalog/resources.json.

    This catalog stores resources discovered by Operator Zero.
    """

    catalog = load_json(
        RESOURCE_CATALOG_PATH,
        default={
            "resources": [],
        },
    )

    resources = catalog.setdefault("resources", [])

    resource_id = metadata["id"]

    for existing_resource in resources:
        if existing_resource.get("id") == resource_id:
            print()
            print("Resource already exists in the catalog.")
            return

    resource_entry = {
        "id": resource_id,
        "title": metadata["title"],
        "provider": metadata["provider"],
        "stat": metadata["stat"],
        "hierarchy": metadata["hierarchy"],
        "skill": metadata["skill"],
        "difficulty": metadata["difficulty"],
        "resource": metadata["resource"],
        "track_path": track_path.as_posix(),
        "date_added": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    resources.append(resource_entry)

    save_json(
        RESOURCE_CATALOG_PATH,
        catalog,
    )


# ============================================================
# MAIN PROGRAM
# ============================================================

def main() -> None:
    """Create one complete Operator Zero learning track."""

    print("=" * 64)
    print("      OPERATOR ZERO KNOWLEDGE-TREE GENERATOR")
    print("=" * 64)

    title = ask_required("Track title: ")
    provider = input("Provider or author: ").strip()

    stat = (
        input("Main stat [INT]: ").strip()
        or "INT"
    )

    hierarchy = collect_hierarchy()

    difficulty = (
        input("Difficulty [Beginner]: ").strip()
        or "Beginner"
    )

    resource = ask_required(
        "Resource repository path or URL: "
    )

    structure_type, units = choose_structure()

    evidence_requirements = (
        collect_evidence_requirements()
    )

    track_path = build_track_path(
        stat=stat,
        hierarchy=hierarchy,
        track_title=title,
    )

    print()
    print("Track destination")
    print("-" * 64)
    print(track_path)

    if track_path.exists():
        print()
        print("ERROR: This track already exists.")
        print("No files were changed.")
        return

    track_path.mkdir(
        parents=True,
        exist_ok=False,
    )

    metadata = create_metadata(
        track_path,
        title=title,
        provider=provider,
        stat=stat,
        hierarchy=hierarchy,
        difficulty=difficulty,
        resource=resource,
        structure_type=structure_type,
        units=units,
        evidence_requirements=evidence_requirements,
    )

    create_progress(track_path)

    create_readme(
        track_path=track_path,
        metadata=metadata,
    )

    create_all_units(
        track_path=track_path,
        units=units,
        requirements=evidence_requirements,
    )

    register_resource(
        metadata=metadata,
        track_path=track_path,
    )

    print()
    print("TRACK CREATED SUCCESSFULLY")
    print("-" * 64)
    print(f"Title       : {metadata['title']}")
    print(f"Skill       : {metadata['skill']}")
    print(f"Hierarchy   : {' > '.join(metadata['hierarchy'])}")
    print(f"Structure   : {metadata['structure_type']}")
    print(f"Units       : {metadata['unit_count']}")
    print(f"Track path  : {track_path}")
    print(f"Catalog     : {RESOURCE_CATALOG_PATH}")


if __name__ == "__main__":
    main()
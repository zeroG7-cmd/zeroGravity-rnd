"""
Operator Zero Learning Engine
Resource Importer v1.1

Improvements in this version
----------------------------
1. Uses parent-folder names for generic files such as:
   submission.py
   solution.py
   answer.py

2. Sorts weekly lessons before standalone projects.

3. Detects meaningful script-topic folders when a week has
   no notebooks, assignments, projects, labs, or exercises.

4. Avoids turning every individual support script into a lesson.

5. Previews all detected units before generating the track.

6. Creates links from generated units back to the original resource.

The importer never modifies the original cloned repository.
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
# SCANNING CONFIGURATION
# ============================================================

SUPPORTED_LEARNING_FILES = {
    ".ipynb",
    ".py",
    ".sh",
    ".sql",
    ".html",
    ".css",
    ".js",
    ".cpp",
    ".c",
    ".md",
}

HIGH_VALUE_DIRECTORIES = {
    "notebooks",
    "assignments",
    "assignment",
    "projects",
    "project",
    "exercises",
    "exercise",
    "labs",
    "lab",
    "challenges",
    "challenge",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    "__pycache__",
    "data",
    "datasets",
    "dataset",
    "images",
    "image",
    "videos",
    "video",
    "models",
    "model",
    "results",
    "result",
    "assets",
    "files",
    "static",
}

IGNORED_FILE_NAMES = {
    "__init__.py",
    "datapath.py",
    "utils.py",
    "requirements.txt",
    "setup.py",
    "license",
    "license.txt",
    "readme.md",
}

GENERIC_FILE_STEMS = {
    "submission",
    "solution",
    "answer",
    "main",
}

# Topic folders that should not become standalone grouped units.
IGNORED_TOPIC_FOLDER_NAMES = {
    "scripts",
    "notebooks",
    "assignments",
    "assignment",
    "projects",
    "project",
    "data",
    "images",
    "videos",
    "models",
    "results",
}


# ============================================================
# INPUT HELPERS
# ============================================================

def ask_required(prompt: str) -> str:
    """Ask repeatedly until the operator enters a value."""

    while True:
        value = input(prompt).strip()

        if value:
            return value

        print("This field cannot be empty.")


def ask_yes_no(
    prompt: str,
    default: bool | None = None,
) -> bool:
    """Ask a yes or no question."""

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
    """Convert text into a safe folder and identifier name."""

    cleaned = text.strip().lower()
    cleaned = cleaned.replace("c++", "cpp")
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)

    return cleaned.strip("_")


def title_from_name(name: str) -> str:
    """Convert a filename or folder name into readable text."""

    cleaned = re.sub(r"[_\-]+", " ", name)
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip().title()


def collect_hierarchy() -> list[str]:
    """
    Collect a variable-depth skill-tree path.

    Example:
        Robotics, Perception, Computer Vision
    """

    print()
    print("Knowledge-tree hierarchy")
    print("-" * 68)
    print("Enter every level beneath the main stat.")
    print()
    print("Example:")
    print("Robotics, Perception, Computer Vision")
    print()

    while True:
        raw_value = ask_required(
            "Hierarchy levels, separated by commas: "
        )

        hierarchy = [
            level.strip()
            for level in raw_value.split(",")
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
    """Load JSON, returning a default if the file is absent."""

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
    """Save data as formatted JSON."""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# ============================================================
# PATH AND RESOURCE HELPERS
# ============================================================

def contains_ignored_directory(
    relative_path: Path,
) -> bool:
    """Return True if any path component is ignored."""

    return any(
        part.lower() in IGNORED_DIRECTORIES
        for part in relative_path.parts
    )


def is_high_value_location(
    relative_path: Path,
) -> bool:
    """Return True for notebooks, assignments, projects, and labs."""

    return any(
        part.lower() in HIGH_VALUE_DIRECTORIES
        for part in relative_path.parts
    )


def extract_week_number(
    relative_path: Path,
) -> int | None:
    """
    Extract a week number from a path.

    Examples:
        week1_getting_started
        week10_deep_learning
    """

    for part in relative_path.parts:
        match = re.match(
            r"week[_\-]?(\d+)",
            part.lower(),
        )

        if match:
            return int(match.group(1))

    return None


def find_week_directory(
    file_path: Path,
    resource_root: Path,
) -> Path | None:
    """Return the week directory containing a source file."""

    relative_path = file_path.relative_to(resource_root)

    current_path = resource_root

    for part in relative_path.parts:
        current_path = current_path / part

        if re.match(r"week[_\-]?\d+", part.lower()):
            return current_path

    return None


def classify_source(relative_path: Path) -> str:
    """Determine the educational source type."""

    path_parts = {
        part.lower()
        for part in relative_path.parts
    }

    if {"assignments", "assignment"} & path_parts:
        return "assignment"

    if {"projects", "project"} & path_parts:
        return "project"

    if {"exercises", "exercise"} & path_parts:
        return "exercise"

    if {"labs", "lab"} & path_parts:
        return "lab"

    if {"challenges", "challenge"} & path_parts:
        return "challenge"

    if relative_path.suffix.lower() == ".ipynb":
        return "notebook"

    return "script"


# ============================================================
# FILE-BASED UNIT DETECTION
# ============================================================

def is_candidate_file(
    file_path: Path,
    resource_root: Path,
    include_scripts: bool,
) -> bool:
    """Decide whether a file should become a learning unit."""

    if not file_path.is_file():
        return False

    if file_path.suffix.lower() not in SUPPORTED_LEARNING_FILES:
        return False

    if file_path.name.lower() in IGNORED_FILE_NAMES:
        return False

    relative_path = file_path.relative_to(resource_root)

    if contains_ignored_directory(relative_path):
        return False

    if is_high_value_location(relative_path):
        return True

    if file_path.suffix.lower() == ".ipynb":
        return True

    return include_scripts


def choose_descriptive_source_name(
    source_path: Path,
) -> str:
    """
    Choose a useful name for a source file.

    Generic filenames such as submission.py use the parent folder name.
    """

    source_stem = source_path.stem

    if source_stem.lower() in GENERIC_FILE_STEMS:
        return source_path.parent.name

    return source_stem


def build_unit_from_source(
    source_path: Path,
    resource_root: Path,
) -> dict[str, Any]:
    """Turn one source file into a learning-unit definition."""

    relative_source = source_path.relative_to(resource_root)
    week_number = extract_week_number(relative_source)
    source_type = classify_source(relative_source)

    descriptive_name = choose_descriptive_source_name(
        source_path
    )

    unit_name = make_slug(descriptive_name)
    unit_title = title_from_name(descriptive_name)

    if week_number is not None:
        unit_path = (
            f"week_{week_number:02}/"
            f"{unit_name}"
        )

        unit_id = (
            f"week_{week_number:02}_"
            f"{unit_name}"
        )

        display_title = (
            f"Week {week_number} - {unit_title}"
        )
    else:
        unit_path = f"projects/{unit_name}"
        unit_id = f"project_{unit_name}"
        display_title = f"Project - {unit_title}"

    return {
        "id": unit_id,
        "title": display_title,
        "path": unit_path,
        "source": relative_source.as_posix(),
        "source_type": source_type,
        "source_extension": source_path.suffix.lower(),
    }


# ============================================================
# GROUPED SCRIPT-TOPIC DETECTION
# ============================================================

def week_has_high_value_units(
    week_path: Path,
    resource_root: Path,
) -> bool:
    """
    Return True if a week already contains notebooks,
    assignments, projects, labs, or exercises.
    """

    for file_path in week_path.rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(resource_root)

        if contains_ignored_directory(relative_path):
            continue

        if is_high_value_location(relative_path):
            return True

        if file_path.suffix.lower() == ".ipynb":
            return True

    return False


def directory_contains_learning_scripts(
    directory: Path,
) -> bool:
    """Return True when a folder contains useful code files."""

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue

        if file_path.name.lower() in IGNORED_FILE_NAMES:
            continue

        if file_path.suffix.lower() in SUPPORTED_LEARNING_FILES:
            return True

    return False


def build_grouped_topic_unit(
    topic_path: Path,
    resource_root: Path,
    week_number: int,
) -> dict[str, Any]:
    """
    Turn a topic directory into one grouped learning unit.

    Example:
        week4/image_smoothing/
    becomes:
        Week 4 - Image Smoothing
    """

    topic_name = topic_path.name
    topic_slug = make_slug(topic_name)
    topic_title = title_from_name(topic_name)

    relative_source = topic_path.relative_to(resource_root)

    return {
        "id": f"week_{week_number:02}_{topic_slug}",
        "title": f"Week {week_number} - {topic_title}",
        "path": f"week_{week_number:02}/{topic_slug}",
        "source": relative_source.as_posix(),
        "source_type": "script_topic",
        "source_extension": None,
    }


def detect_grouped_script_topics(
    resource_root: Path,
) -> list[dict[str, Any]]:
    """
    Find meaningful topic folders in weeks that contain no
    notebook-style or assignment-style units.

    This prevents script-only weeks from disappearing.
    """

    grouped_units: list[dict[str, Any]] = []

    week_directories = [
        path
        for path in resource_root.iterdir()
        if path.is_dir()
        and re.match(r"week[_\-]?\d+", path.name.lower())
    ]

    for week_path in week_directories:
        relative_week = week_path.relative_to(resource_root)
        week_number = extract_week_number(relative_week)

        if week_number is None:
            continue

        if week_has_high_value_units(
            week_path=week_path,
            resource_root=resource_root,
        ):
            continue

        for child_directory in week_path.iterdir():
            if not child_directory.is_dir():
                continue

            if child_directory.name.lower() in IGNORED_TOPIC_FOLDER_NAMES:
                continue

            if contains_ignored_directory(
                child_directory.relative_to(resource_root)
            ):
                continue

            if directory_contains_learning_scripts(
                child_directory
            ):
                grouped_units.append(
                    build_grouped_topic_unit(
                        topic_path=child_directory,
                        resource_root=resource_root,
                        week_number=week_number,
                    )
                )

    return grouped_units


# ============================================================
# SORTING AND DUPLICATE HANDLING
# ============================================================

def unit_sort_key(
    unit: dict[str, Any],
) -> tuple[int, int, str]:
    """
    Sort weekly units first, then non-week units,
    then standalone projects.
    """

    week_match = re.match(
        r"week_(\d+)",
        unit["path"],
    )

    if week_match:
        week_number = int(week_match.group(1))
        return (0, week_number, unit["path"])

    if unit["source_type"] == "project":
        return (2, 0, unit["path"])

    return (1, 0, unit["path"])


def make_unit_ids_unique(
    units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prevent duplicate unit identifiers."""

    unique_units: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for unit in units:
        original_id = unit["id"]
        unique_id = original_id
        counter = 2

        while unique_id in used_ids:
            unique_id = f"{original_id}_{counter}"
            counter += 1

        unit["id"] = unique_id
        used_ids.add(unique_id)
        unique_units.append(unit)

    return unique_units


# ============================================================
# MAIN SCANNER
# ============================================================

def scan_resource(
    resource_root: Path,
    include_scripts: bool,
) -> list[dict[str, Any]]:
    """
    Scan the resource and return proposed learning units.
    """

    units: list[dict[str, Any]] = []

    for file_path in resource_root.rglob("*"):
        if is_candidate_file(
            file_path=file_path,
            resource_root=resource_root,
            include_scripts=include_scripts,
        ):
            units.append(
                build_unit_from_source(
                    source_path=file_path,
                    resource_root=resource_root,
                )
            )

    # Add grouped topic units for script-only weeks.
    grouped_script_units = detect_grouped_script_topics(
        resource_root
    )

    units.extend(grouped_script_units)

    units.sort(key=unit_sort_key)

    return make_unit_ids_unique(units)


# ============================================================
# UNIT PREVIEW AND FILTERING
# ============================================================

def display_units(
    units: list[dict[str, Any]],
) -> None:
    """Display every detected unit."""

    print()
    print("Detected learning units")
    print("-" * 68)

    for index, unit in enumerate(units, start=1):
        print(
            f"{index:>3}. {unit['title']}\n"
            f"     Type   : {unit['source_type']}\n"
            f"     Source : {unit['source']}"
        )

    print("-" * 68)
    print(f"Total detected: {len(units)}")


def parse_removal_selection(
    raw_selection: str,
    unit_count: int,
) -> set[int]:
    """
    Parse selections such as:

        2,5,8-11
    """

    indexes: set[int] = set()

    if not raw_selection.strip():
        return indexes

    entries = raw_selection.split(",")

    for entry in entries:
        cleaned = entry.strip()

        if not cleaned:
            continue

        if "-" in cleaned:
            start_text, end_text = cleaned.split(
                "-",
                maxsplit=1,
            )

            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError:
                continue

            for number in range(start, end + 1):
                if 1 <= number <= unit_count:
                    indexes.add(number - 1)

        else:
            try:
                number = int(cleaned)
            except ValueError:
                continue

            if 1 <= number <= unit_count:
                indexes.add(number - 1)

    return indexes


def review_units(
    units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Allow the operator to remove unwanted units."""

    while True:
        display_units(units)

        if ask_yes_no(
            "Use all detected units?",
            default=True,
        ):
            return units

        print()
        print("Enter unit numbers to remove.")
        print("Examples:")
        print("  3")
        print("  2,5,8")
        print("  4-10")
        print("  2,6-9,14")
        print()

        raw_selection = input(
            "Units to remove: "
        ).strip()

        removal_indexes = parse_removal_selection(
            raw_selection=raw_selection,
            unit_count=len(units),
        )

        if not removal_indexes:
            print("No valid units were selected.")
            continue

        units = [
            unit
            for index, unit in enumerate(units)
            if index not in removal_indexes
        ]

        if not units:
            raise ValueError(
                "The imported track must contain at least one unit."
            )


# ============================================================
# EVIDENCE CONFIGURATION
# ============================================================

def collect_evidence_requirements() -> list[dict[str, str]]:
    """Collect evidence rules for each generated unit."""

    requirements: list[dict[str, str]] = []

    print()
    print("Evidence requirements")
    print("-" * 68)

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
            return requirements


# ============================================================
# TRACK CREATION
# ============================================================

def build_track_path(
    stat: str,
    hierarchy: list[str],
    track_title: str,
) -> Path:
    """Build the full track directory."""

    track_path = TRACKS_ROOT / make_slug(stat)

    for hierarchy_level in hierarchy:
        track_path = track_path / make_slug(
            hierarchy_level
        )

    return track_path / make_slug(track_title)


def create_evidence_files(
    unit_path: Path,
    requirements: list[dict[str, str]],
) -> None:
    """Create all evidence files for one unit."""

    for requirement in requirements:
        relative_path = Path(requirement["path"])
        file_path = unit_path / relative_path

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.touch(exist_ok=True)


def create_source_reference(
    unit_path: Path,
    unit: dict[str, Any],
    resource_path: Path,
) -> None:
    """Create source.json linking back to the resource."""

    source_reference = {
        "source_type": unit["source_type"],
        "source_file": unit["source"],
        "resource_root": resource_path.as_posix(),
    }

    save_json(
        unit_path / "source.json",
        source_reference,
    )


def create_all_units(
    track_path: Path,
    units: list[dict[str, Any]],
    requirements: list[dict[str, str]],
    resource_path: Path,
) -> None:
    """Create every learning unit and evidence template."""

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

        create_source_reference(
            unit_path=unit_path,
            unit=unit,
            resource_path=resource_path,
        )


def create_metadata(
    track_path: Path,
    *,
    title: str,
    provider: str,
    stat: str,
    hierarchy: list[str],
    difficulty: str,
    resource_path: Path,
    units: list[dict[str, Any]],
    evidence_requirements: list[dict[str, str]],
) -> dict[str, Any]:
    """Create metadata.json for the imported track."""

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
        "resource": resource_path.as_posix(),
        "import_method": "resource_scan",
        "structure_type": "imported",
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
    """Create initial progress.json."""

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
    """Create the track README."""

    knowledge_path = " > ".join(
        [metadata["stat"], *metadata["hierarchy"]]
    )

    content = f"""# {metadata["title"]}

## Operator Zero Imported Learning Track

- **Knowledge path:** {knowledge_path}
- **Provider:** {metadata["provider"]}
- **Difficulty:** {metadata["difficulty"]}
- **Imported units:** {metadata["unit_count"]}
- **Source resource:** `{metadata["resource"]}`
- **Status:** In Progress

## Import Method

This track was generated by scanning an existing learning resource.

Each unit contains `source.json`, which points back to its
original notebook, assignment, project, script, or topic folder.

## Workflow

1. Open the original source.
2. Study or run the material.
3. Complete your own practical work.
4. Save the required evidence.
5. Run the Operator Zero tracker.
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
    """Register the imported resource in the catalog."""

    catalog = load_json(
        RESOURCE_CATALOG_PATH,
        default={"resources": []},
    )

    resources = catalog.setdefault(
        "resources",
        [],
    )

    for existing_resource in resources:
        if existing_resource.get("id") == metadata["id"]:
            print()
            print("Resource already exists in the catalog.")
            return

    resources.append(
        {
            "id": metadata["id"],
            "title": metadata["title"],
            "provider": metadata["provider"],
            "stat": metadata["stat"],
            "hierarchy": metadata["hierarchy"],
            "skill": metadata["skill"],
            "difficulty": metadata["difficulty"],
            "resource": metadata["resource"],
            "track_path": track_path.as_posix(),
            "import_method": "resource_scan",
            "date_added": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    save_json(
        RESOURCE_CATALOG_PATH,
        catalog,
    )


# ============================================================
# MAIN PROGRAM
# ============================================================

def main() -> None:
    """Scan a resource and import it into Operator Zero."""

    print("=" * 68)
    print("        OPERATOR ZERO RESOURCE IMPORTER")
    print("=" * 68)

    raw_resource_path = ask_required(
        "Local resource directory: "
    )

    resource_path = Path(raw_resource_path)

    if not resource_path.exists():
        print()
        print("ERROR: The resource directory does not exist.")
        print(resource_path)
        return

    if not resource_path.is_dir():
        print()
        print("ERROR: The supplied path is not a directory.")
        return

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

    include_scripts = ask_yes_no(
        "Include ordinary scripts as individual units?",
        default=False,
    )

    print()
    print("Scanning resource...")

    detected_units = scan_resource(
        resource_root=resource_path,
        include_scripts=include_scripts,
    )

    if not detected_units:
        print()
        print("No suitable learning units were detected.")
        print(
            "Use create_track.py if you need full manual control."
        )
        return

    selected_units = review_units(
        detected_units
    )

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
    print("-" * 68)
    print(track_path)

    if track_path.exists():
        print()
        print("ERROR: This track already exists.")
        print("No files were changed.")
        return

    if not ask_yes_no(
        "Generate this imported track?",
        default=True,
    ):
        print("Import cancelled.")
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
        resource_path=resource_path,
        units=selected_units,
        evidence_requirements=evidence_requirements,
    )

    create_progress(track_path)

    create_readme(
        track_path=track_path,
        metadata=metadata,
    )

    create_all_units(
        track_path=track_path,
        units=selected_units,
        requirements=evidence_requirements,
        resource_path=resource_path,
    )

    register_resource(
        metadata=metadata,
        track_path=track_path,
    )

    print()
    print("RESOURCE IMPORTED SUCCESSFULLY")
    print("-" * 68)
    print(f"Track title : {metadata['title']}")
    print(f"Skill       : {metadata['skill']}")
    print(f"Units       : {metadata['unit_count']}")
    print(f"Resource    : {metadata['resource']}")
    print(f"Track path  : {track_path}")
    print(f"Catalog     : {RESOURCE_CATALOG_PATH}")


if __name__ == "__main__":
    main()
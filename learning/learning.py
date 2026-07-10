"""
Operator Zero Learning Engine
Main Command-Line Interface v1.0

Purpose
-------
This program acts as the front door to the Learning Engine.

Instead of manually remembering the path to every engine script,
the operator runs:

    python learning/learning.py

The menu can then launch:

- tracker.py
- import_resource.py
- create_track.py
- migrate_tracks.py

It can also display:

- learning tracks
- the resource catalog

Architecture
------------
learning.py
    |
    +-- engine/tracker.py
    +-- engine/import_resource.py
    +-- engine/create_track.py
    +-- engine/migrate_tracks.py
    +-- catalog/resources.json
    +-- tracks/
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


# ============================================================
# SYSTEM PATHS
# ============================================================

# Path to the learning directory containing this file.
LEARNING_ROOT = Path(__file__).resolve().parent

# Repository root is one level above learning/.
REPOSITORY_ROOT = LEARNING_ROOT.parent

# Engine scripts.
ENGINE_ROOT = LEARNING_ROOT / "engine"

TRACKER_SCRIPT = ENGINE_ROOT / "tracker.py"
IMPORTER_SCRIPT = ENGINE_ROOT / "import_resource.py"
CREATE_TRACK_SCRIPT = ENGINE_ROOT / "create_track.py"
MIGRATION_SCRIPT = ENGINE_ROOT / "migrate_tracks.py"

# Stored learning data.
TRACKS_ROOT = LEARNING_ROOT / "tracks"
CATALOG_PATH = LEARNING_ROOT / "catalog" / "resources.json"


# ============================================================
# DISPLAY HELPERS
# ============================================================

def clear_screen() -> None:
    """
    Clear the terminal.

    This works on:
    - Windows
    - Linux
    - macOS

    It is optional. Failure to clear the screen will not stop
    the Learning Engine.
    """

    command = "cls" if sys.platform.startswith("win") else "clear"

    try:
        subprocess.run(
            command,
            shell=True,
            check=False,
        )
    except OSError:
        pass


def display_header() -> None:
    """Display the Operator Zero Learning Engine heading."""

    print("=" * 68)
    print("              OPERATOR ZERO LEARNING ENGINE")
    print("=" * 68)
    print()


def pause() -> None:
    """Wait before returning to the main menu."""

    print()
    input("Press Enter to return to the main menu...")


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(
    file_path: Path,
    default: Any,
) -> Any:
    """
    Read JSON from disk.

    If the file does not exist, return the supplied default value.
    """

    if not file_path.exists():
        return default

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as error:
        print()
        print("JSON ERROR")
        print(f"File: {file_path}")
        print(error)

        return default


# ============================================================
# SCRIPT LAUNCHING
# ============================================================

def run_engine_script(script_path: Path) -> None:
    """
    Run one Learning Engine script.

    sys.executable is the exact Python interpreter currently
    running this menu.

    This is safer than hardcoding:
        python
    or:
        py

    because it works across Windows, Linux, virtual environments,
    and Raspberry Pi.
    """

    if not script_path.exists():
        print()
        print("ERROR")
        print(f"Engine script was not found:\n{script_path}")
        pause()
        return

    print()
    print(f"Launching: {script_path.name}")
    print("-" * 68)
    print()

    try:
        subprocess.run(
            [
                sys.executable,
                str(script_path),
            ],
            cwd=REPOSITORY_ROOT,
            check=False,
        )

    except OSError as error:
        print()
        print("The engine script could not be launched.")
        print(error)

    pause()


# ============================================================
# TRACK DISCOVERY
# ============================================================

def discover_tracks() -> list[Path]:
    """
    Find every valid learning track.

    A folder counts as a track when it contains:

    - metadata.json
    - progress.json
    """

    tracks: list[Path] = []

    if not TRACKS_ROOT.exists():
        return tracks

    for metadata_path in TRACKS_ROOT.rglob("metadata.json"):
        track_path = metadata_path.parent
        progress_path = track_path / "progress.json"

        if progress_path.exists():
            tracks.append(track_path)

    return sorted(tracks)


def build_knowledge_path(
    metadata: dict[str, Any],
) -> str:
    """
    Convert metadata into a readable skill-tree path.

    New format:
        INT > Robotics > Perception > Computer Vision

    Older tracks remain supported.
    """

    hierarchy = metadata.get("hierarchy", [])

    if hierarchy:
        path_parts = [
            metadata.get("stat", "Unknown"),
            *hierarchy,
        ]
    else:
        path_parts = [
            metadata.get("stat"),
            metadata.get("branch"),
            metadata.get("category"),
            metadata.get("skill"),
        ]

    return " > ".join(
        str(part)
        for part in path_parts
        if part
    )


def display_tracks() -> None:
    """Display every registered learning track and its progress."""

    clear_screen()
    display_header()

    print("LEARNING TRACKS")
    print("-" * 68)

    track_paths = discover_tracks()

    if not track_paths:
        print("No learning tracks were found.")
        pause()
        return

    for index, track_path in enumerate(track_paths, start=1):
        metadata = load_json(
            track_path / "metadata.json",
            default={},
        )

        progress = load_json(
            track_path / "progress.json",
            default={},
        )

        title = metadata.get("title", track_path.name)
        units = metadata.get("units", [])
        completed_units = progress.get("completed_units", [])

        total_units = len(units)
        completed_count = len(completed_units)

        if total_units:
            percentage = (
                completed_count / total_units
            ) * 100
        else:
            percentage = 0.0

        print()
        print(f"{index}. {title}")
        print(f"   {build_knowledge_path(metadata)}")
        print(
            f"   Progress: {completed_count}/{total_units} "
            f"({percentage:.1f}%)"
        )
        print(
            f"   XP: {progress.get('total_xp', 0)}"
        )
        print(
            f"   Status: {progress.get('status', 'Unknown')}"
        )
        print(f"   Location: {track_path}")

    pause()


# ============================================================
# RESOURCE CATALOG
# ============================================================

def display_catalog() -> None:
    """Display every learning resource stored in the catalog."""

    clear_screen()
    display_header()

    print("RESOURCE CATALOG")
    print("-" * 68)

    catalog = load_json(
        CATALOG_PATH,
        default={"resources": []},
    )

    resources = catalog.get("resources", [])

    if not resources:
        print("No catalog resources were found.")
        pause()
        return

    for index, resource in enumerate(resources, start=1):
        hierarchy = resource.get("hierarchy", [])

        knowledge_path = " > ".join(
            [
                resource.get("stat", "Unknown"),
                *hierarchy,
            ]
        )

        print()
        print(f"{index}. {resource.get('title', 'Unknown')}")
        print(
            f"   Provider: "
            f"{resource.get('provider', 'Unknown')}"
        )
        print(f"   Path: {knowledge_path}")
        print(
            f"   Difficulty: "
            f"{resource.get('difficulty', 'Unknown')}"
        )
        print(
            f"   Import method: "
            f"{resource.get('import_method', 'Unknown')}"
        )
        print(
            f"   Resource: "
            f"{resource.get('resource', 'Unknown')}"
        )
        print(
            f"   Track: "
            f"{resource.get('track_path', 'Unknown')}"
        )

    pause()


# ============================================================
# MAIN MENU
# ============================================================

def display_menu() -> None:
    """Display the main menu options."""

    print("1. Continue Learning")
    print("2. Import Existing Resource")
    print("3. Create Track Manually")
    print("4. View Resource Catalog")
    print("5. View Learning Tracks")
    print("6. Migrate Legacy Tracks")
    print("7. Exit")
    print()


def main() -> None:
    """Run the Learning Engine menu until the operator exits."""

    while True:
        clear_screen()
        display_header()

        print("Resource -> Track -> Evidence -> XP -> Growth")
        print()

        display_menu()

        selection = input("Select an option: ").strip()

        if selection == "1":
            run_engine_script(TRACKER_SCRIPT)

        elif selection == "2":
            run_engine_script(IMPORTER_SCRIPT)

        elif selection == "3":
            run_engine_script(CREATE_TRACK_SCRIPT)

        elif selection == "4":
            display_catalog()

        elif selection == "5":
            display_tracks()

        elif selection == "6":
            run_engine_script(MIGRATION_SCRIPT)

        elif selection == "7":
            print()
            print("Learning Engine closed.")
            break

        else:
            print()
            print("Enter a number from 1 to 7.")
            pause()


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
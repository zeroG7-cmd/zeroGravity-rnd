"""
=====================================================
Operator Zero Learning Engine
Tracker v1.0
=====================================================

Purpose:
- Read course metadata
- Read learning progress
- Find the current lesson
- Check if lesson evidence exists
- Display learning status

Future Versions:
- Award XP
- Update progress.json
- Update SQLite database
- Sync with Zero Command Dashboard
"""

import json
from pathlib import Path


# --------------------------------------------------
# Track Location
# --------------------------------------------------

TRACK_PATH = Path(
    "learning/tracks/software_engineering/python/30_days_of_python"
)


# --------------------------------------------------
# Load JSON File
# --------------------------------------------------

def load_json(file_path):
    """Load a JSON file and return it as a Python dictionary."""

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# Check Lesson Evidence
# --------------------------------------------------

def check_evidence(lesson_path):

    evidence = {
        "notes": (lesson_path / "notes.md").exists(),
        "solution": (lesson_path / "solution.py").exists(),
        "reflection": (lesson_path / "reflection.md").exists(),
        "terminal": (
            lesson_path / "evidence" / "terminal_output.txt"
        ).exists()
    }

    return evidence


# --------------------------------------------------
# Main Program
# --------------------------------------------------

def main():

    metadata = load_json(TRACK_PATH / "metadata.json")
    progress = load_json(TRACK_PATH / "progress.json")

    current_lesson = progress["current_lesson"]

    lesson_folder = f"day_{current_lesson:02}"

    lesson_path = TRACK_PATH / lesson_folder

    evidence = check_evidence(lesson_path)

    print("=" * 50)
    print("      Operator Zero Learning Engine")
    print("=" * 50)

    print(f"\nTrack        : {metadata['title']}")
    print(f"Provider     : {metadata['provider']}")
    print(f"Skill        : {metadata['skill']}")
    print(f"Difficulty   : {metadata['difficulty']}")

    print()

    print(f"Current Lesson : {lesson_folder}")
    print(f"Status         : {progress['status']}")
    print(f"XP             : {progress['total_xp']}")

    print()

    print("Evidence")

    print("---------------------------")

    print(f"Notes       : {'✅' if evidence['notes'] else '❌'}")
    print(f"Solution    : {'✅' if evidence['solution'] else '❌'}")
    print(f"Reflection  : {'✅' if evidence['reflection'] else '❌'}")
    print(f"Terminal    : {'✅' if evidence['terminal'] else '❌'}")

    print()

    completed = sum(evidence.values())

    print(f"Completion : {completed}/4")


# --------------------------------------------------
# Start Program
# --------------------------------------------------

if __name__ == "__main__":
    main()
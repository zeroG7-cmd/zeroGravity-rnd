"""One-time optional cleanup for the accidental Fusion 360 template completion."""

from __future__ import annotations

import json
from pathlib import Path

from stats import build_operator_stats, calculate_skill_level

COMPETENCIES_PATH = Path("operator/capabilities/competencies.json")
HISTORY_PATH = Path("operator/hubs/learning/history/learning_history.json")
TRACK_PROGRESS = Path(
    "learning/tracks/int/robotics/mechanical_design/cad/"
    "fusion_360_beginners_course/progress.json"
)
COMPETENCY_ID = "int.robotics.mechanical_design.cad"
TRACK_ID = "cad_fusion_360_beginners_course"
UNIT_ID = "section_01_unit_001_course_introduction"
XP_TO_REMOVE = 40


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")


def main() -> None:
    print("This removes the known accidental +40 CAD XP and first completion.")
    if input("Continue? [y/N]: ").strip().lower() not in {"y", "yes"}:
        print("Cancelled.")
        return

    competencies = load(COMPETENCIES_PATH)
    competency = competencies["competencies"][COMPETENCY_ID]
    competency["xp"] = max(0, int(competency.get("xp", 0)) - XP_TO_REMOVE)
    competency["level"] = calculate_skill_level(competency["xp"])
    save(COMPETENCIES_PATH, competencies)

    if TRACK_PROGRESS.exists():
        progress = load(TRACK_PROGRESS)
        progress["completed_units"] = [
            unit for unit in progress.get("completed_units", []) if unit != UNIT_ID
        ]
        progress["current_unit_index"] = 0
        progress["total_xp"] = max(0, int(progress.get("total_xp", 0)) - XP_TO_REMOVE)
        progress["status"] = "In Progress"
        save(TRACK_PROGRESS, progress)

    if HISTORY_PATH.exists():
        history = load(HISTORY_PATH)
        history["events"] = [
            event
            for event in history.get("events", [])
            if not (
                event.get("track_id") == TRACK_ID
                and event.get("unit_id") == UNIT_ID
            )
        ]
        save(HISTORY_PATH, history)

    build_operator_stats()
    print("Accidental completion removed and stats rebuilt.")


if __name__ == "__main__":
    main()


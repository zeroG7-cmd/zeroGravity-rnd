"""Operator Zero Learning Engine - direct unit completion (any order).

Thin CLI wrapper around tracker.complete_unit() for the Flask Learning Hub
UI to invoke (see operator_learning.py's _run(), which already knows how
to launch an engine script either as a real subprocess or, in a frozen
PyInstaller build, in-process via runpy - this script works either way,
exactly like tracker.py already does).

Unlike tracker.py's interactive main(), this takes its target unit from
argv instead of stdin, because the HUD now lets the operator pick ANY
unit in a track - not just whichever one progress.json currently calls
"current".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tracker import complete_unit, discover_tracks, load_json  # noqa: E402


def _find_track(track_id: str) -> Path:
    for path in discover_tracks():
        metadata = load_json(path / "metadata.json")
        if str(metadata.get("id", path.name)) == track_id:
            return path
    raise ValueError(f"Learning track not found: {track_id}")


def _resolve_unit_index(
    track_path: Path, unit_id: str | None, unit_index: int | None
) -> int:
    metadata = load_json(track_path / "metadata.json")
    units = metadata.get("units", [])
    if unit_index is not None:
        if not 0 <= unit_index < len(units):
            raise ValueError(f"Unit index out of range: {unit_index}")
        return unit_index
    if unit_id is not None:
        for index, unit in enumerate(units):
            if str(unit.get("id")) == unit_id:
                return index
        raise ValueError(f"Unit not found in track: {unit_id}")
    raise ValueError("Pass --unit-id or --unit-index.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Complete one learning unit in a track, any order."
    )
    parser.add_argument("track_id")
    parser.add_argument("--unit-id", default=None)
    parser.add_argument("--unit-index", type=int, default=None)
    args = parser.parse_args()

    try:
        track_path = _find_track(args.track_id)
        unit_index = _resolve_unit_index(track_path, args.unit_id, args.unit_index)
        result = complete_unit(track_path, unit_index)
    except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
        print("LEARNING ENGINE ERROR")
        print(error)
        sys.exit(1)
        return

    unit_title = result["unit"].get("title", result["unit"].get("id", "unit"))

    if result["reason"] == "evidence_incomplete":
        print("Evidence check")
        print("-" * 68)
        for name, passed in (result.get("evidence_status") or {}).items():
            print(f"{name:<32}{'[PASS]' if passed else '[MISSING]'}")
        print("-" * 68)
        print(f"Unit is still in progress: {unit_title}")
        return

    if result["reason"] == "already_completed":
        print(f"This unit was already completed. No XP was awarded: {unit_title}")
        return

    operator_stats = result["operator_stats"]
    print("UNIT COMPLETE")
    print("-" * 68)
    print(f"Unit: {unit_title}")
    print(
        f"+{result['total_xp']} total XP awarded across "
        f"{len(result['distribution'])} competencies."
    )
    print(f"Operator Total XP: {operator_stats['total_xp']}")
    print(f"Operator Level: {operator_stats['level']}")
    print(
        f"Next Operator Level: {operator_stats['xp_to_next_level']} XP remaining "
        f"({operator_stats['level_progress']}%)"
    )
    print("progress.json updated.")
    print("competencies.json updated.")
    print("stats.json updated.")
    print("history.json updated.")

    if result["status"] == "Complete":
        print("TRACK COMPLETE")
    elif result.get("next_unit_title"):
        print(f"Next unit still open: {result['next_unit_title']}")


if __name__ == "__main__":
    main()

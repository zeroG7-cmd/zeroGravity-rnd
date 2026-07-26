"""Learning track watcher — zero-friction manual course completion.

What this does
---------------
For every track under ``learning/tracks``, this watches the CURRENT
unit's required evidence files. The moment a required file appears (or
gains real content), you get a notification for that item. The moment
every required file for the unit is present, it completes the unit
automatically -- same XP math, same idempotency, same everything as
clicking "Complete current unit" on the Zero Command dashboard or
running ``tracker.py`` yourself -- and you get a final notification
with the XP that was awarded.

This intentionally reuses ``learning/engine/tracker.py`` untouched
(``discover_tracks``, ``check_evidence``, ``track_selected_course``)
rather than re-implementing any of that logic, so behaviour never
drifts from the manual path. This file only adds: polling, a small
"what have I already notified about" memory, and notifications.

Running it
----------
    cd learning/engine
    python ../automation/watcher.py

Leave it running in a terminal (or set it up to start with your
machine) while you work through your courses. Stop with Ctrl+C.

Known trade-offs, on purpose, for a first version
--------------------------------------------------
- Polling every few seconds, not real filesystem events. Simple,
  stdlib-only, and plenty fast for text files you edit by hand. If it
  ever feels laggy, the ``watchdog`` package gives you instant,
  event-driven detection instead of polling -- a drop-in upgrade to the
  loop in ``main()``, not a rewrite.
- Desktop popups are best-effort (see notifier.py). Every notification
  is also written to notifications.log, so you never lose one even on
  a machine with no popup backend available.
"""
from __future__ import annotations

import sys
import time
import json
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    """Walk upward until we find the folder that contains shared/config/paths.py.

    This makes the script work no matter which folder it's placed in
    (learning/automation/, learning/engine/automation/, wherever) --
    instead of assuming a fixed number of parent folders, which is what
    broke last time.
    """
    current = start
    for _ in range(8):
        if (current / "shared" / "config" / "paths.py").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise RuntimeError(
        "Could not find the zeroGravity-rnd repo root (looked for "
        f"shared/config/paths.py above {start}). Make sure this file "
        "lives somewhere inside the zeroGravity-rnd folder."
    )


AUTOMATION_ROOT = Path(__file__).resolve().parent
REPO_ROOT = _find_repo_root(AUTOMATION_ROOT)
ENGINE_ROOT = REPO_ROOT / "learning" / "engine"

for path in (REPO_ROOT, ENGINE_ROOT, AUTOMATION_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tracker import (  # noqa: E402  (import after sys.path setup, on purpose)
    discover_tracks,
    load_json,
    check_evidence,
    track_selected_course,
)
from notifier import notify  # noqa: E402

STATE_PATH = AUTOMATION_ROOT / "watcher_state.json"
POLL_SECONDS = 5


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(STATE_PATH)


def check_track(track_path: Path, state: dict) -> None:
    metadata = load_json(track_path / "metadata.json")
    progress = load_json(track_path / "progress.json")
    progress.setdefault("current_unit_index", 0)
    progress.setdefault("status", "In Progress")

    if progress.get("status") == "Complete":
        state.pop(str(track_path), None)
        return

    units = metadata.get("units", [])
    index = progress["current_unit_index"]
    if not 0 <= index < len(units):
        return

    unit = units[index]
    unit_path = track_path / unit["path"]
    if not unit_path.exists():
        return

    requirements = metadata.get("evidence_requirements", [])
    status = check_evidence(unit_path, requirements)

    track_key = str(track_path)
    unit_key = str(unit["id"])
    previous = state.get(track_key, {}).get(unit_key, {})

    track_title = metadata.get("title", track_path.name)
    for name, passed in status.items():
        if passed and not previous.get(name):
            notify(title=track_title, message=f"{name} - received.")

    state.setdefault(track_key, {})[unit_key] = status

    if status and all(status.values()):
        xp_before = progress.get("total_xp", 0)
        # Identical to the dashboard's "Complete current unit" button and
        # to running tracker.py by hand -- same function, same result.
        track_selected_course(track_path)
        refreshed = load_json(track_path / "progress.json")
        awarded = refreshed.get("total_xp", 0) - xp_before
        notify(
            title=f"Unit complete - {unit.get('title', unit_key)}",
            message=f"+{awarded} XP awarded.",
        )
        # The unit is done; drop its state so a re-used unit id later
        # (a different track re-using the same evidence names) starts clean.
        state[track_key].pop(unit_key, None)


def run_once(state: dict) -> None:
    for track_path in discover_tracks():
        try:
            check_track(track_path, state)
        except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
            # One broken/half-set-up track should never take the whole
            # watcher down -- report it and keep watching everything else.
            print(f"[watcher] skipped {track_path.name}: {error}")


def main() -> None:
    print("Learning watcher running. Checking every "
          f"{POLL_SECONDS}s. Ctrl+C to stop.")
    state = load_state()
    try:
        while True:
            run_once(state)
            save_state(state)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
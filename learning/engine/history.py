"""
Operator Zero Learning Engine
Completion History v1.0

Records every completed unit as a permanent event.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HISTORY_PATH = Path(
    "learning/operator/history.json"
)


def load_history() -> dict[str, Any]:
    """Load history or create an empty structure."""

    if not HISTORY_PATH.exists():
        return {
            "events": [],
        }

    with HISTORY_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_history(
    history: dict[str, Any],
) -> None:
    """Save completion history."""

    HISTORY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with HISTORY_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            history,
            file,
            indent=4,
        )


def completion_exists(
    history: dict[str, Any],
    track_id: str,
    unit_id: str,
) -> bool:
    """
    Prevent duplicate completion-history events.
    """

    for event in history.get(
        "events",
        [],
    ):
        if (
            event.get("track_id") == track_id
            and event.get("unit_id") == unit_id
            and event.get("event_type") == "unit_completed"
        ):
            return True

    return False


def record_completion(
    metadata: dict[str, Any],
    unit: dict[str, Any],
    xp_award: int,
) -> bool:
    """
    Record one unit-completion event.

    Returns:
        True if recorded.
        False if the event already existed.
    """

    history = load_history()

    track_id = str(
        metadata.get(
            "id",
            "unknown_track",
        )
    )

    unit_id = str(
        unit.get(
            "id",
            "unknown_unit",
        )
    )

    if completion_exists(
        history=history,
        track_id=track_id,
        unit_id=unit_id,
    ):
        return False

    event = {
        "event_type": "unit_completed",
        "track_id": track_id,
        "track_title": metadata.get(
            "title"
        ),
        "stat": metadata.get(
            "stat"
        ),
        "hierarchy": metadata.get(
            "hierarchy",
            [],
        ),
        "skill": metadata.get(
            "skill"
        ),
        "unit_id": unit_id,
        "unit_title": unit.get(
            "title"
        ),
        "unit_type": unit.get(
            "source_type",
            "manual",
        ),
        "xp_awarded": xp_award,
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    history.setdefault(
        "events",
        [],
    ).append(event)

    save_history(
        history
    )

    return True
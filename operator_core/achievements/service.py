"""Curated achievement checker/awarder.

Reuses the exact same OperatorEvent -> DistributionService ->
update_operator_competencies pipeline every other hub in this app already
uses (see modules/tasks.py, modules/operator_execution.py,
learning/engine/completion_service.py). Nothing here computes or applies XP
through a separate path - an achievement's bonus XP goes through the same
auditable receipt machinery as everything else, and lands via the receipt's
own allocations, never a separately-computed number.

Idempotency is delegated entirely to the event ledger: every achievement
gets a stable idempotency_key ("achievement:<id>"), so EventLedger already
refuses (or, with allow_existing=True, silently returns the existing event
for) a repeat award. There is deliberately no separate "unlocked
achievements" file to keep in sync - has_idempotency_key() on the ledger's
own index *is* the unlocked list.

check_and_award_all() is meant to run after any XP award anywhere in the
app. It currently self-invokes from the tail of
learning.engine.stats.update_operator_competencies() - the single choke
point every XP-awarding hub already funnels through (fitness, learning,
journal, tasks, execution). It's cheap (a handful of small JSON reads), and
a re-entrancy guard makes it safe to call from inside that same function
even though awarding an achievement's bonus XP calls right back into
update_operator_competencies() itself.

Achievements are hand-authored only - see data/definitions.json. Nothing in
this module invents an achievement; it only checks the ones already written
down there.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from shared.config.paths import LEARNING_ROOT, OPERATOR_CAPABILITIES

DEFINITIONS_PATH = Path(__file__).resolve().parent / "data" / "definitions.json"
COMPETENCIES_PATH = OPERATOR_CAPABILITIES / "competencies.json"
TRACKS_ROOT = LEARNING_ROOT / "tracks"

# Re-entrancy guard: awarding an achievement's bonus XP calls back into
# update_operator_competencies(), whose own tail calls check_and_award_all()
# again. Bonus XP never targets a competency this module checks milestones
# against (it always goes to craft/goal_commitment/evidence), so that second
# call would find nothing new anyway - but this guard makes that a
# guarantee rather than something inferred from today's definitions.json.
_STATE = threading.local()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_definitions() -> dict[str, Any]:
    return _load_json(
        DEFINITIONS_PATH,
        {"achievements": [], "bonus_split": {"targets": []}},
    )


def _competency_xp(competency_id: str) -> int:
    data = _load_json(COMPETENCIES_PATH, {"competencies": {}})
    record = data.get("competencies", {}).get(competency_id, {})
    return int(record.get("xp", 0)) if isinstance(record, dict) else 0


def _course_completed(track_path: str) -> bool:
    progress = _load_json(TRACKS_ROOT / track_path / "progress.json", None)
    if not isinstance(progress, dict):
        return False
    return str(progress.get("status", "")).strip().lower() == "completed"


def _award(
    achievement: dict[str, Any],
    bonus_targets: list[dict[str, Any]],
    ledger: Any,
) -> dict[str, Any]:
    from operator_core.events.models import OperatorEvent
    from operator_core.distribution.service import DistributionService
    from learning.engine import stats as stats_engine

    achievement_id = str(achievement["id"])
    idempotency_key = f"achievement:{achievement_id}"

    event = ledger.append(
        OperatorEvent(
            event_type="achievement_unlocked",
            source="operator_core.achievements",
            payload={
                "achievement_id": achievement_id,
                "track": achievement.get("track"),
                "kind": achievement["kind"],
                "title": achievement.get("title"),
                "description": achievement.get("description"),
                "base_xp": int(achievement["base_xp"]),
                "xp_targets": bonus_targets,
            },
            idempotency_key=idempotency_key,
        ),
        allow_existing=True,
    )
    receipt = DistributionService(ledger=ledger).distribute_event(event)

    allocations = [
        {"competency_id": allocation.target_id, "xp": allocation.xp}
        for allocation in receipt.allocations
        if allocation.target_type == "competency"
    ]
    if allocations:
        stats_engine.update_operator_competencies(allocations)

    return {
        "achievement_id": achievement_id,
        "title": achievement.get("title"),
        "base_xp": int(achievement["base_xp"]),
        "event_id": event.event_id,
        "receipt_id": receipt.receipt_id,
        "allocations": allocations,
    }


def check_and_award_all() -> list[dict[str, Any]]:
    """Check every curated achievement, award any newly-crossed one.

    Safe to call as often as you like - already-unlocked achievements are
    always a cheap no-op (one index lookup each). Returns the list of
    achievements newly unlocked by this call, empty most of the time.
    """
    if getattr(_STATE, "active", False):
        return []
    _STATE.active = True
    try:
        from operator_core.events.service import EventLedger
        from operator_core.profile.progression import calculate_level

        definitions = load_definitions()
        bonus_targets = definitions.get("bonus_split", {}).get("targets", [])
        if not bonus_targets:
            return []

        ledger = EventLedger()
        newly_awarded: list[dict[str, Any]] = []

        for achievement in definitions.get("achievements", []):
            idempotency_key = f"achievement:{achievement['id']}"
            if ledger.has_idempotency_key(idempotency_key):
                continue

            kind = achievement.get("kind")
            if kind == "milestone":
                xp = _competency_xp(achievement["competency_id"])
                if calculate_level(xp) < int(achievement["level_threshold"]):
                    continue
            elif kind == "course_completion":
                if not _course_completed(achievement["track_path"]):
                    continue
            else:
                continue

            newly_awarded.append(_award(achievement, bonus_targets, ledger))

        return newly_awarded
    finally:
        _STATE.active = False

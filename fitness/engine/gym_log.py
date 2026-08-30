"""Gym-day completion logging.

Logs "I did today's gym session" as a single flat-XP event, distributed
across whichever capabilities that day's slot in
`fitness/routines/weekly_routine.json` trains (its `"trains"` list), plus
the usual Discipline share. Same event-sourced pattern
`fitness.engine.tracker` uses for daily habits - `OperatorEvent` ->
`EventLedger` -> `DistributionService` -> `competencies.json` ->
`fitness.engine.stats.sync_and_recompute` - just one flat completion event
per day instead of a per-habit quantity.

v1 is deliberately simple (see fitness/README.md's "start simple, extend
later" philosophy): one flat XP pool per gym day, split evenly across that
day's `trains` capabilities. It doesn't look at sets/reps/weight actually
performed - that's a natural v2 once this is live for a few weeks. Like
`tracker.py`, logging the same date twice is a no-op the second time
(`gym:{date}` idempotency key) - one log per calendar date.

CLI:

    python -m fitness.engine.gym_log                  # logs today
    python -m fitness.engine.gym_log --date 2026-08-31
    python -m fitness.engine.gym_log --day Monday      # log a specific split day regardless of today's weekday
    python -m fitness.engine.gym_log --status
"""
from __future__ import annotations

import argparse
import sys
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from operator_core.distribution.service import DistributionService
from operator_core.events.models import OperatorEvent
from operator_core.events.service import EventLedger
from shared.config.paths import OPERATOR_CAPABILITIES
from shared.libraries.json_store import load_json, save_json

from fitness.engine.config import (
    DAILY_PRACTICE_COMPETENCY_ID,
    DISC_SHARE,
    GYM_OPTIONAL_DAY_XP,
    GYM_SESSION_XP,
)
from fitness.engine.stats import sync_and_recompute
from fitness.engine.tracker import apply_receipt_to_competencies

COMPETENCIES_PATH = OPERATOR_CAPABILITIES / "competencies.json"
ROUTINE_PATH = Path(__file__).resolve().parent.parent / "routines" / "weekly_routine.json"


def _today_iso() -> str:
    return date_cls.today().isoformat()


def _load_routine() -> dict[str, Any]:
    routine = load_json(ROUTINE_PATH, None)
    if routine is None:
        raise FileNotFoundError(f"weekly_routine.json not found at {ROUTINE_PATH}")
    return routine


def _routine_day(routine: dict[str, Any], day_name: str) -> dict[str, Any] | None:
    return next((d for d in routine.get("days", []) if d.get("day") == day_name), None)


def _already_logged(ledger: EventLedger, idempotency_key: str) -> bool:
    return ledger.has_idempotency_key(idempotency_key)


def log_gym_day(
    *,
    day_name: str | None = None,
    log_date: str | None = None,
    ledger: EventLedger | None = None,
    distribution: DistributionService | None = None,
) -> dict[str, Any]:
    """Log completion of one gym-routine day. Returns a summary dict for display.

    ``day_name`` picks which weekly_routine.json split to award XP for
    (defaults to today's actual weekday name, e.g. "Monday") - pass it
    explicitly to log a session done a bit late without lying about the
    calendar date. ``log_date`` is the calendar date the idempotency key and
    history are keyed on (defaults to today).
    """
    log_date = log_date or _today_iso()
    day_name = day_name or date_cls.fromisoformat(log_date).strftime("%A")
    ledger = ledger or EventLedger()
    distribution = distribution or DistributionService()

    routine = _load_routine()
    routine_day = _routine_day(routine, day_name)
    if routine_day is None:
        raise ValueError(f"{day_name!r} is not a day in weekly_routine.json")

    if not routine_day.get("exercises"):
        return {
            "date": log_date,
            "day": day_name,
            "logged": False,
            "reason": "rest_day",
            "xp_awarded": 0,
            "capabilities_trained": [],
        }

    idempotency_key = f"gym:{log_date}"
    if _already_logged(ledger, idempotency_key):
        return {
            "date": log_date,
            "day": day_name,
            "logged": False,
            "reason": "already_logged",
            "xp_awarded": 0,
            "capabilities_trained": [],
        }

    trains: list[str] = routine_day.get("trains", [])
    competencies_doc = load_json(COMPETENCIES_PATH, {"schema_version": 1, "competencies": {}})

    if trains:
        total_xp = GYM_SESSION_XP
        non_disc_weight = 1 - DISC_SHARE
        share = non_disc_weight / len(trains)
        xp_targets = [
            {"target_id": competency_id, "target_type": "competency", "weight": share}
            for competency_id in trains
        ] + [
            {"target_id": DAILY_PRACTICE_COMPETENCY_ID, "target_type": "competency", "weight": DISC_SHARE},
        ]
    else:
        # Optional day (e.g. Saturday) with exercises listed but nothing
        # gym-specific to award beyond the daily habits already logged
        # separately - still credit showing up.
        total_xp = GYM_OPTIONAL_DAY_XP
        xp_targets = [
            {"target_id": DAILY_PRACTICE_COMPETENCY_ID, "target_type": "competency", "weight": 1.0},
        ]

    event = OperatorEvent(
        event_type="fitness_gym_day_logged",
        source="fitness.engine.gym_log",
        payload={
            "date": log_date,
            "day": day_name,
            "focus": routine_day.get("focus"),
            "trains": trains,
            "total_xp": total_xp,
            "xp_targets": xp_targets,
        },
        idempotency_key=idempotency_key,
    )
    recorded = ledger.append(event)
    receipt = distribution.distribute_event(recorded, total_xp=total_xp)
    new_totals = apply_receipt_to_competencies(competencies_doc, receipt)
    save_json(COMPETENCIES_PATH, competencies_doc)

    stats_doc = None
    if new_totals:
        stats_doc = sync_and_recompute(new_totals.keys())

    return {
        "date": log_date,
        "day": day_name,
        "focus": routine_day.get("focus"),
        "logged": True,
        "reason": None,
        "xp_awarded": total_xp,
        "capabilities_trained": trains,
        "operator_total_xp": stats_doc["total_xp"] if stats_doc else None,
        "operator_level": stats_doc["level"] if stats_doc else None,
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"Gym day log for {summary['date']} ({summary['day']})")
    if not summary["logged"]:
        if summary["reason"] == "rest_day":
            print(f"  {summary['day']} is a rest day - nothing to log.")
        elif summary["reason"] == "already_logged":
            print(f"  Already logged for {summary['date']} (one log per calendar date).")
        return
    if summary["capabilities_trained"]:
        print(f"  {summary['focus']} -> +{summary['xp_awarded']} XP split across:")
        for competency_id in summary["capabilities_trained"]:
            print(f"    - {competency_id}")
    else:
        print(f"  {summary['focus']} -> +{summary['xp_awarded']} XP to Discipline (showed up)")
    if summary.get("operator_total_xp") is not None:
        print(f"  Operator total XP: {summary['operator_total_xp']} (level {summary['operator_level']})")


def _print_status() -> None:
    ledger = EventLedger()
    events = sorted(
        ledger.iter_events(event_type="fitness_gym_day_logged"),
        key=lambda event: event.recorded_at,
    )
    if not events:
        print("No gym days logged yet.")
        return
    last = events[-1]
    print(
        f"Last gym day logged: {last.payload.get('date')} "
        f"({last.payload.get('day')} - {last.payload.get('focus')}), "
        f"+{last.payload.get('total_xp')} XP"
    )
    print(f"Total gym days logged: {len(events)}")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Log completion of today's gym-routine day.")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, defaults to today")
    parser.add_argument(
        "--day",
        default=None,
        help="Weekly routine day name (e.g. Monday), defaults to --date's actual weekday",
    )
    parser.add_argument("--status", action="store_true", help="Print last logged gym day and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.status:
        _print_status()
        return 0

    summary = log_gym_day(day_name=args.day, log_date=args.date)
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())

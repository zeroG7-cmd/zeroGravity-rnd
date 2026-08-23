"""Fitness daily habit tracker.

Logs one day's quantities for the configured habits (see
`fitness/engine/config.py`), turns each into an Operator event, distributes
XP through the same shared `operator_core.events` / `operator_core.distribution`
mechanics `learning/` uses, updates `operator_core/capabilities/competencies.json`,
and calls `fitness.engine.stats` to refresh `learning_stats.json`.

v1 keeps each (date, habit) log final rather than supporting incremental
corrections: logging the same habit twice for the same day is a no-op the
second time (see `_already_logged` below) rather than silently double- or
under-counting. Log your day's true total once.

CLI:

    python -m fitness.engine.tracker --date 2026-08-23 \\
        --pushups 62 --pullups 58 --situps 70 --squats 65 \\
        --run-minutes 32 --stretch-minutes 12

    python -m fitness.engine.tracker --status
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
from operator_core.profile.progression import get_level_progress
from shared.config.paths import OPERATOR_CAPABILITIES, FITNESS_HISTORY_FILE, FITNESS_PROGRESS_FILE
from shared.libraries.json_store import load_json, save_json

from fitness.engine.config import (
    DAILY_PRACTICE_COMPETENCY_ID,
    DISC_SHARE,
    FULL_DAY_CONSISTENCY_BONUS_XP,
    HABITS,
    MAX_XP_RATIO,
    concept_id_for_quantity,
)
from fitness.engine.stats import sync_and_recompute

COMPETENCIES_PATH = OPERATOR_CAPABILITIES / "competencies.json"


def _today_iso() -> str:
    return date_cls.today().isoformat()


def _xp_for_quantity(habit_key: str, quantity: float) -> int:
    habit = HABITS[habit_key]
    ratio = min(quantity / habit["daily_target"], MAX_XP_RATIO)
    return round(habit["base_xp"] * max(ratio, 0.0))


def _already_logged(ledger: EventLedger, idempotency_key: str) -> bool:
    return ledger.has_idempotency_key(idempotency_key)


def _day_entries_from_ledger(ledger: EventLedger, log_date: str) -> list[dict[str, Any]]:
    """Reconstruct the full, authoritative list of habits logged for log_date
    from the event ledger - not just whatever this particular call logged.
    This is what history/status/the full-day check all read, so logging a
    day's habits across two or more calls still adds up correctly.
    """
    todays_events = sorted(
        (
            event
            for event in ledger.iter_events(event_type="fitness_habit_logged")
            if event.payload.get("date") == log_date
        ),
        key=lambda event: event.recorded_at,
    )
    entries = []
    for event in todays_events:
        habit_key = event.payload.get("habit")
        habit = HABITS.get(habit_key)
        if habit is None:
            continue
        quantity = float(event.payload.get("quantity", 0))
        entries.append(
            {
                "habit": habit_key,
                "label": habit["label"],
                "quantity": quantity,
                "unit": habit["unit"],
                "target": habit["daily_target"],
                "met_target": quantity >= habit["daily_target"],
                "xp_awarded": int(event.payload.get("base_xp", 0)),
                "concept_id": event.payload.get("concept_id"),
            }
        )
    return entries


def _is_full_day(day_entries: list[dict[str, Any]]) -> bool:
    """True once every habit in HABITS is present in day_entries and each met target."""
    logged_habit_keys = {entry["habit"] for entry in day_entries}
    if logged_habit_keys != set(HABITS.keys()):
        return False
    return all(entry["met_target"] for entry in day_entries)


def _existing_full_day_bonus_xp(ledger: EventLedger, log_date: str) -> int:
    bonus_key = f"fitness:{log_date}:consistency_bonus"
    return FULL_DAY_CONSISTENCY_BONUS_XP if _already_logged(ledger, bonus_key) else 0


def _apply_receipt_to_competencies(
    competencies_doc: dict[str, Any], receipt
) -> dict[str, int]:
    """Add each allocation's XP onto competencies.json and recompute its level.
    Returns {competency_id: new_xp} for everything this receipt touched.
    """
    competencies = competencies_doc.setdefault("competencies", {})
    updated: dict[str, int] = {}
    for allocation in receipt.allocations:
        if allocation.target_type != "competency":
            continue
        record = competencies.setdefault(
            allocation.target_id, {"id": allocation.target_id, "xp": 0, "level": 0, "shared": False}
        )
        record["xp"] = int(record.get("xp", 0)) + allocation.xp
        record["level"] = get_level_progress(record["xp"])["level"]
        updated[allocation.target_id] = record["xp"]
    return updated


def log_day(
    quantities: dict[str, float],
    *,
    log_date: str | None = None,
    ledger: EventLedger | None = None,
    distribution: DistributionService | None = None,
) -> dict[str, Any]:
    """Log one day's habit quantities. Returns a summary dict for display."""
    log_date = log_date or _today_iso()
    ledger = ledger or EventLedger()
    distribution = distribution or DistributionService()

    competencies_doc = load_json(COMPETENCIES_PATH, {"schema_version": 1, "competencies": {}})

    entries: list[dict[str, Any]] = []
    touched_competency_ids: set[str] = set()
    skipped: list[str] = []
    all_met_target = True
    anything_logged = False

    for habit_key, quantity in quantities.items():
        if quantity is None:
            continue
        habit = HABITS[habit_key]
        idempotency_key = f"fitness:{log_date}:{habit_key}"
        if _already_logged(ledger, idempotency_key):
            skipped.append(habit["label"])
            continue

        anything_logged = True
        quantity = float(quantity)
        base_xp = _xp_for_quantity(habit_key, quantity)
        met_target = quantity >= habit["daily_target"]
        all_met_target = all_met_target and met_target
        concept_id = concept_id_for_quantity(habit_key, quantity)

        # Habits with a secondary_competency_id (currently just stretch_minutes)
        # split their non-Discipline share 50/50 across both competencies
        # instead of sending it all to one - e.g. stretching builds both CON
        # (tissue/joint health) and DEX (movement quality).
        non_disc_weight = 1 - DISC_SHARE
        secondary_id = habit.get("secondary_competency_id")
        if secondary_id:
            half = non_disc_weight / 2
            stat_targets = [
                {"target_id": habit["competency_id"], "target_type": "competency", "weight": half},
                {"target_id": secondary_id, "target_type": "competency", "weight": half},
            ]
        else:
            stat_targets = [
                {"target_id": habit["competency_id"], "target_type": "competency", "weight": non_disc_weight},
            ]

        event = OperatorEvent(
            event_type="fitness_habit_logged",
            source="fitness.engine.tracker",
            payload={
                "date": log_date,
                "habit": habit_key,
                "quantity": quantity,
                "unit": habit["unit"],
                "target": habit["daily_target"],
                "base_xp": base_xp,
                "concept_id": concept_id,
                "xp_targets": stat_targets
                + [
                    {
                        "target_id": DAILY_PRACTICE_COMPETENCY_ID,
                        "target_type": "competency",
                        "weight": DISC_SHARE,
                    },
                ],
            },
            idempotency_key=idempotency_key,
        )
        recorded = ledger.append(event)
        receipt = distribution.distribute_event(recorded, total_xp=base_xp)
        new_totals = _apply_receipt_to_competencies(competencies_doc, receipt)
        touched_competency_ids.update(new_totals.keys())

        entries.append(
            {
                "habit": habit_key,
                "label": habit["label"],
                "quantity": quantity,
                "unit": habit["unit"],
                "target": habit["daily_target"],
                "met_target": met_target,
                "xp_awarded": base_xp,
                "concept_id": concept_id,
            }
        )

    day_entries = _day_entries_from_ledger(ledger, log_date)
    bonus_awarded = 0
    if anything_logged and _is_full_day(day_entries):
        bonus_key = f"fitness:{log_date}:consistency_bonus"
        if not _already_logged(ledger, bonus_key):
            bonus_event = OperatorEvent(
                event_type="fitness_full_day_bonus",
                source="fitness.engine.tracker",
                payload={
                    "date": log_date,
                    "xp_targets": [
                        {
                            "target_id": DAILY_PRACTICE_COMPETENCY_ID,
                            "target_type": "competency",
                            "weight": 1.0,
                        }
                    ],
                },
                idempotency_key=bonus_key,
            )
            recorded = ledger.append(bonus_event)
            receipt = distribution.distribute_event(recorded, total_xp=FULL_DAY_CONSISTENCY_BONUS_XP)
            new_totals = _apply_receipt_to_competencies(competencies_doc, receipt)
            touched_competency_ids.update(new_totals.keys())
            bonus_awarded = FULL_DAY_CONSISTENCY_BONUS_XP

    save_json(COMPETENCIES_PATH, competencies_doc)

    stats_doc = None
    if touched_competency_ids:
        stats_doc = sync_and_recompute(touched_competency_ids)

    full_day = _is_full_day(day_entries)
    day_bonus_xp = bonus_awarded or _existing_full_day_bonus_xp(ledger, log_date)
    if day_entries:
        _write_history_for_day(log_date, day_entries, day_bonus_xp, full_day)
        _update_streak(log_date, full_day)

    return {
        "date": log_date,
        "entries": entries,
        "skipped_already_logged": skipped,
        "full_day_bonus_xp": bonus_awarded,
        "all_habits_met_target": all_met_target and anything_logged,
        "full_day": full_day,
        "operator_total_xp": stats_doc["total_xp"] if stats_doc else None,
        "operator_level": stats_doc["level"] if stats_doc else None,
    }


def _write_history_for_day(
    log_date: str, day_entries: list[dict[str, Any]], bonus_xp: int, full_day: bool
) -> None:
    """Overwrite log_date's history entry with the full, ledger-reconstructed
    day (see _day_entries_from_ledger) so logging in multiple calls the same
    day never loses earlier entries.
    """
    history = load_json(FITNESS_HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    history = [day for day in history if day.get("date") != log_date]
    history.append(
        {
            "date": log_date,
            "entries": day_entries,
            "full_day_bonus_xp": bonus_xp,
            "all_habits_met_target": full_day,
            "total_xp_today": sum(item["xp_awarded"] for item in day_entries) + bonus_xp,
        }
    )
    history.sort(key=lambda day: day["date"])
    save_json(FITNESS_HISTORY_FILE, history)


def _update_streak(log_date: str, full_day: bool) -> None:
    progress = load_json(
        FITNESS_PROGRESS_FILE,
        {"current_streak_days": 0, "longest_streak_days": 0, "last_full_day": None, "last_logged_day": None},
    )
    if full_day:
        last_full = progress.get("last_full_day")
        if last_full:
            gap = (date_cls.fromisoformat(log_date) - date_cls.fromisoformat(last_full)).days
        else:
            gap = None
        if gap == 1 or gap is None:
            progress["current_streak_days"] = int(progress.get("current_streak_days", 0)) + 1
        elif gap != 0:
            progress["current_streak_days"] = 1
        progress["last_full_day"] = log_date
        progress["longest_streak_days"] = max(
            int(progress.get("longest_streak_days", 0)), int(progress["current_streak_days"])
        )
    else:
        progress["current_streak_days"] = 0
    progress["last_logged_day"] = log_date
    save_json(FITNESS_PROGRESS_FILE, progress)


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"Fitness log for {summary['date']}")
    if not summary["entries"] and not summary["skipped_already_logged"]:
        print("  Nothing logged.")
    for entry in summary["entries"]:
        flag = "OK" if entry["met_target"] else "under target"
        print(
            f"  {entry['label']:<18} {entry['quantity']:g} {entry['unit']:<7} "
            f"(target {entry['target']}, {flag}) -> +{entry['xp_awarded']} XP"
        )
    for label in summary["skipped_already_logged"]:
        print(f"  {label}: already logged today, skipped (v1 logs are final per day).")
    if summary["full_day_bonus_xp"]:
        print(f"  Full-day consistency bonus: +{summary['full_day_bonus_xp']} XP to Discipline")
    if summary["operator_total_xp"] is not None:
        print(f"  Operator total XP: {summary['operator_total_xp']} (level {summary['operator_level']})")


def _print_status() -> None:
    from shared.config.paths import OPERATOR_HUBS

    stats_doc = load_json(OPERATOR_HUBS / "learning" / "stats" / "learning_stats.json", None)
    history = load_json(FITNESS_HISTORY_FILE, [])
    progress = load_json(FITNESS_PROGRESS_FILE, {})
    print(f"Current streak: {progress.get('current_streak_days', 0)} day(s) "
          f"(longest: {progress.get('longest_streak_days', 0)})")
    if stats_doc:
        for stat in ("STR", "CON", "DISC"):
            print(f"  {stat} average_level: {stats_doc['stats'][stat]['average_level']}")
    if history:
        last = history[-1]
        print(f"Last logged day: {last['date']} (all targets met: {last['all_habits_met_target']})")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Log a day of fitness habits.")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, defaults to today")
    parser.add_argument("--pushups", type=float, default=None)
    parser.add_argument("--pullups", type=float, default=None)
    parser.add_argument("--situps", type=float, default=None)
    parser.add_argument("--squats", type=float, default=None)
    parser.add_argument("--run-minutes", type=float, default=None, dest="run_minutes")
    parser.add_argument("--stretch-minutes", type=float, default=None, dest="stretch_minutes")
    parser.add_argument("--status", action="store_true", help="Print current progress and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.status:
        _print_status()
        return 0

    quantities = {
        "pushups": args.pushups,
        "pullups": args.pullups,
        "situps": args.situps,
        "squats": args.squats,
        "run_minutes": args.run_minutes,
        "stretch_minutes": args.stretch_minutes,
    }
    if all(value is None for value in quantities.values()):
        parser.error("Provide at least one habit quantity, or use --status.")

    summary = log_day(quantities, log_date=args.date)
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())

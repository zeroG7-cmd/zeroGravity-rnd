"""Operator Zero XP Engine v2.0.

Responsibilities:
- Calculate the base XP value of one completed unit.
- Resolve inherited competency mappings.
- Split XP across multiple competencies without losing XP to rounding.
- Convert logged hours (Weekly Ops) into an XP pool on the same scale.
"""

from __future__ import annotations

import math
from typing import Any

DEFAULT_XP_RULES = {
    "manual": 40,
    "video": 30,
    "article": 25,
    "quiz": 35,
    "notebook": 40,
    "script": 30,
    "script_topic": 35,
    "exercise": 45,
    "challenge": 50,
    "lab": 55,
    "assignment": 60,
    "experiment": 80,
    "project": 100,
}

# Hours-based XP (Weekly Ops / time-logged activity)
#
# Every rule above rewards a *completed unit* - a finished video, quiz,
# lab, project, and so on. The weekly planner isn't unit-shaped: a study
# or build block is just hours spent inside a focus area, so it needs its
# own rate rather than being forced through DEFAULT_XP_RULES.
#
# HOURLY_XP_RATE is set deliberately BELOW every rate above - the cheapest
# unit ("article") is worth 25 XP. Hours are self-reported and trivial to
# inflate by just leaving a session logged open; unit completions require
# actually finishing something, and they need to stay the more valuable
# path or the whole economy tilts toward clock-sitting over output. At 20
# XP/hour, a typical 1-2 hour Weekly Ops block earns 20-40 XP - in the
# same neighbourhood as a video or article, never more than a real
# lab/assignment/project, and it still rewards showing up honestly on
# weeks where nothing gets formally "completed."
HOURLY_XP_RATE = 20


def get_track_xp_rules(metadata: dict[str, Any]) -> dict[str, int]:
    rules = DEFAULT_XP_RULES.copy()
    custom_rules = metadata.get("xp_rules", {})

    if isinstance(custom_rules, dict):
        for unit_type, xp_value in custom_rules.items():
            try:
                xp = int(xp_value)
            except (TypeError, ValueError):
                continue
            if xp >= 0:
                rules[str(unit_type)] = xp
    return rules


def calculate_unit_xp(metadata: dict[str, Any], unit: dict[str, Any]) -> int:
    """Calculate the total reward pool for a completed unit."""
    rules = get_track_xp_rules(metadata)

    if "xp_value" in unit:
        try:
            explicit = int(unit["xp_value"])
            if explicit >= 0:
                return explicit
        except (TypeError, ValueError):
            pass

    unit_type = str(unit.get("source_type", "manual"))
    return rules.get(unit_type, rules["manual"])


def calculate_hourly_xp(hours: float, rate: int = HOURLY_XP_RATE) -> int:
    """Convert logged hours into a whole XP pool for distribute_xp().

    Rounds to the nearest XP rather than flooring, so a short, honestly
    logged block (e.g. 0.25h) still registers something instead of
    silently rounding to zero.
    """
    if hours < 0:
        raise ValueError("Hours cannot be negative.")
    return round(float(hours) * rate)


def _normalise_awards(raw_awards: Any) -> list[dict[str, Any]]:
    """Validate and normalise competency weights so that they sum to 1.0."""
    if not isinstance(raw_awards, list):
        return []

    merged: dict[str, float] = {}
    order: list[str] = []

    for award in raw_awards:
        if not isinstance(award, dict):
            continue

        competency_id = str(award.get("competency_id", "")).strip()
        if not competency_id:
            continue

        try:
            weight = float(award.get("weight", 0))
        except (TypeError, ValueError):
            continue

        if weight <= 0:
            continue

        if competency_id not in merged:
            order.append(competency_id)
            merged[competency_id] = 0.0
        merged[competency_id] += weight

    total_weight = sum(merged.values())
    if total_weight <= 0:
        return []

    return [
        {
            "competency_id": competency_id,
            "weight": merged[competency_id] / total_weight,
        }
        for competency_id in order
    ]


def resolve_competency_awards(
    metadata: dict[str, Any],
    unit: dict[str, Any],
) -> list[dict[str, Any]]:
    """Resolve unit, section, track-default, then legacy competency mapping."""
    unit_awards = _normalise_awards(unit.get("competency_awards"))
    if unit_awards:
        return unit_awards

    section_awards = metadata.get("section_competency_awards", {})
    if isinstance(section_awards, dict):
        keys = [
            str(unit.get("section_number", "")),
            str(unit.get("section_title", "")),
            str(unit.get("section_id", "")),
        ]
        for key in keys:
            if not key:
                continue
            resolved = _normalise_awards(section_awards.get(key))
            if resolved:
                return resolved

    default_awards = _normalise_awards(
        metadata.get("default_competency_awards")
    )
    if default_awards:
        return default_awards

    legacy_competency_id = str(metadata.get("competency_id", "")).strip()
    if legacy_competency_id:
        return [{"competency_id": legacy_competency_id, "weight": 1.0}]

    return []


def distribute_xp(
    total_xp: int,
    competency_awards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Split XP using the largest-remainder method.

    The returned integer awards always sum exactly to ``total_xp``.
    """
    if total_xp < 0:
        raise ValueError("Total XP cannot be negative.")

    awards = _normalise_awards(competency_awards)
    if not awards:
        raise ValueError("No valid competency awards were supplied.")

    exact_values = [total_xp * item["weight"] for item in awards]
    floors = [math.floor(value) for value in exact_values]
    remainder = total_xp - sum(floors)

    ranked_indexes = sorted(
        range(len(awards)),
        key=lambda index: (
            exact_values[index] - floors[index],
            -index,
        ),
        reverse=True,
    )

    for index in ranked_indexes[:remainder]:
        floors[index] += 1

    return [
        {
            "competency_id": award["competency_id"],
            "weight": round(float(award["weight"]), 6),
            "xp": floors[index],
        }
        for index, award in enumerate(awards)
        if floors[index] > 0 or total_xp == 0
    ]

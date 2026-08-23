"""Daily habit configuration for the Fitness engine.

Each habit maps a CLI/UI field to:

- ``competency_id``: the leaf in ``operator_core/capabilities/competencies.json``
  it awards XP to.
- ``tree_path``: where that leaf lives inside
  ``operator_core/hubs/learning/stats/learning_stats.json`` (and
  ``operator_core/capabilities/skill_tree.json``), as a list of node names
  from the main stat down to the leaf. ``fitness.engine.stats`` uses this to
  know exactly which branches to recompute after a log.
- ``unit``: ``"reps"`` or ``"minutes"``, for display only.
- ``daily_target``: today's target quantity (the 60/day or 30-minute goals).
- ``century_target``: the stretch-goal quantity, where relevant.
- ``base_xp``: the XP pool awarded for hitting exactly 100% of target. XP
  scales linearly with quantity / target, capped at ``max_ratio``x.
- ``concept_id``: which capability_graph.json concept gets the day's XP.
  Below ``daily_target`` this is the "form" concept; at/above ``century_target``
  it's the "century" concept; in between it's the "daily_60" concept.
- ``secondary_competency_id`` / ``secondary_tree_path`` (optional): a second
  competency that shares the habit's non-Discipline XP 50/50 with the primary
  one. Only ``stretch_minutes`` uses this today - flexibility work builds both
  CON (tissue/joint health) and DEX (movement quality), per the split the user
  chose over keeping it CON-only or moving it to DEX outright. See
  fitness/README.md for the reasoning.
"""
from __future__ import annotations

from typing import Any

# Same XP curve used everywhere else in the Operator system
# (learning/engine/level.py, operator_core/profile/progression.py).
BASE_XP_LEVEL_CONSTANT = 100
CURVE_EXPONENT = 1.5

# Share of each habit's XP pool that also goes toward Discipline evidence,
# on top of the habit's own stat. Showing up counts, regardless of numbers.
DISC_SHARE = 0.15

# The maximum multiple of daily_target that still earns extra XP. Going
# further than this still counts toward the log, it just stops adding XP,
# so a single wild outlier day can't dominate the curve.
MAX_XP_RATIO = 2.0

DAILY_PRACTICE_COMPETENCY_ID = "disc.consistency.routine_adherence.daily_practice"
DAILY_PRACTICE_TREE_PATH = ["DISC", "Consistency", "Routine Adherence", "Daily Practice"]

# Flat bonus (100% to Daily Practice) awarded once per day when every
# configured habit that was logged met or beat its daily_target.
FULL_DAY_CONSISTENCY_BONUS_XP = 25

HABITS: dict[str, dict[str, Any]] = {
    "pushups": {
        "label": "Push-ups",
        "unit": "reps",
        "daily_target": 60,
        "century_target": 100,
        "base_xp": 60,
        "competency_id": "str.muscular_strength.upper_body.push_ups",
        "tree_path": ["STR", "Muscular Strength", "Upper Body", "Push-ups"],
        "concept_prefix": "push_ups",
    },
    "pullups": {
        "label": "Pull-ups",
        "unit": "reps",
        "daily_target": 60,
        "century_target": 100,
        "base_xp": 60,
        "competency_id": "str.muscular_strength.upper_body.pull_ups",
        "tree_path": ["STR", "Muscular Strength", "Upper Body", "Pull-ups"],
        "concept_prefix": "pull_ups",
    },
    "situps": {
        "label": "Sit-ups",
        "unit": "reps",
        "daily_target": 60,
        "century_target": 100,
        "base_xp": 60,
        "competency_id": "str.muscular_strength.core.sit_ups",
        "tree_path": ["STR", "Muscular Strength", "Core", "Sit-ups"],
        "concept_prefix": "sit_ups",
    },
    "squats": {
        "label": "Squats",
        "unit": "reps",
        "daily_target": 60,
        "century_target": 100,
        "base_xp": 60,
        "competency_id": "str.muscular_strength.lower_body.squats",
        "tree_path": ["STR", "Muscular Strength", "Lower Body", "Squats"],
        "concept_prefix": "squats",
    },
    "run_minutes": {
        "label": "Jog",
        "unit": "minutes",
        "daily_target": 30,
        "century_target": None,
        "base_xp": 60,
        "competency_id": "con.endurance.aerobic_capacity.running",
        "tree_path": ["CON", "Endurance", "Aerobic Capacity", "Running"],
        "concept_prefix": "running",
    },
    "stretch_minutes": {
        "label": "Stretch / mobility",
        "unit": "minutes",
        "daily_target": 10,
        "century_target": None,
        "base_xp": 30,
        "competency_id": "con.health_management.mobility.stretching",
        "tree_path": ["CON", "Health Management", "Mobility", "Stretching"],
        "concept_prefix": "stretching",
        "secondary_competency_id": "dex.agility.mobility.dynamic_flexibility",
        "secondary_tree_path": ["DEX", "Agility", "Mobility", "Dynamic Flexibility"],
    },
}


def concept_id_for_quantity(habit_key: str, quantity: float) -> str | None:
    """Pick which capability_graph.json concept today's quantity evidences.

    Deliberately simple (v1): below target -> the "form" concept, at/above
    target -> "daily_60" (or the running/stretching equivalent first tier),
    at/above the century target -> "century". Habits without a century
    target (running, stretching) just have "form" / "daily_60".
    """
    habit = HABITS[habit_key]
    prefix = habit["concept_prefix"]
    target = habit["daily_target"]
    century = habit.get("century_target")

    if century and quantity >= century:
        return f"{prefix}.century"
    if habit["unit"] == "reps":
        if quantity >= target:
            return f"{prefix}.daily_60"
        return f"{prefix}.form"
    # minutes-based habits (running, stretching) use their own first-tier names
    if habit_key == "run_minutes":
        return "running.daily_30" if quantity >= target else "running.15min"
    if habit_key == "stretch_minutes":
        return "stretching.full_routine" if quantity >= target else "stretching.consistency"
    return None

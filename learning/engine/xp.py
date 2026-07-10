"""
Operator Zero Learning Engine
XP Engine v1.0

Purpose
-------
Calculate how much XP a completed learning unit should award.

The tracker should not contain XP rules itself.

Instead:

    tracker.py
        |
        v
    xp.py
        |
        v
    calculate unit XP

This keeps progression logic separate from tracking logic.
"""

from typing import Any


# ============================================================
# DEFAULT XP RULES
# ============================================================

# These are fallback rules.
# Individual tracks can override them inside metadata.json.
DEFAULT_XP_RULES = {
    "manual": 40,
    "notebook": 40,
    "script": 30,
    "script_topic": 35,
    "exercise": 45,
    "challenge": 50,
    "lab": 55,
    "assignment": 60,
    "project": 100,
}


# ============================================================
# XP CALCULATION
# ============================================================

def get_track_xp_rules(
    metadata: dict[str, Any],
) -> dict[str, int]:
    """
    Return the XP rules for a track.

    A track may define its own rules:

        "xp_rules": {
            "notebook": 45,
            "assignment": 70,
            "project": 120
        }

    Missing values fall back to DEFAULT_XP_RULES.
    """

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


def calculate_unit_xp(
    metadata: dict[str, Any],
    unit: dict[str, Any],
) -> int:
    """
    Calculate XP for one completed unit.

    The unit's source_type determines the base reward.

    Examples:
        notebook     -> 40 XP
        assignment   -> 60 XP
        project      -> 100 XP
    """

    rules = get_track_xp_rules(metadata)

    unit_type = str(
        unit.get("source_type", "manual")
    )

    return rules.get(
        unit_type,
        rules["manual"],
    )
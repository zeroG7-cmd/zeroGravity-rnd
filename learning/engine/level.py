"""Operator Zero progressive level engine v2.0.

Levels are derived from cumulative XP. The XP cost of moving from level N to
N + 1 is::

    round(BASE_XP * (N + 1) ** CURVE_EXPONENT)

Level 0 therefore requires 100 XP to reach level 1. Each later level requires
more deliberate work, while old XP remains valid because levels are always
recalculated from cumulative XP.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

BASE_XP = 100
CURVE_EXPONENT = 1.5


def xp_cost_for_level(level: int) -> int:
    """Return the XP needed to move from ``level`` to ``level + 1``."""
    if level < 0:
        raise ValueError("Level cannot be negative.")
    return round(BASE_XP * ((level + 1) ** CURVE_EXPONENT))


@lru_cache(maxsize=None)
def cumulative_xp_for_level(level: int) -> int:
    """Return the total XP required to reach ``level`` from level 0."""
    if level < 0:
        raise ValueError("Level cannot be negative.")
    return sum(xp_cost_for_level(current) for current in range(level))


def calculate_level(total_xp: int) -> int:
    """Calculate a level from cumulative XP."""
    if total_xp <= 0:
        return 0

    level = 0
    while total_xp >= cumulative_xp_for_level(level + 1):
        level += 1
    return level


def get_level_progress(total_xp: int) -> dict[str, Any]:
    """Return level, thresholds, and progress percentage for UI display."""
    safe_xp = max(0, int(total_xp))
    level = calculate_level(safe_xp)
    level_start_xp = cumulative_xp_for_level(level)
    next_level_xp = cumulative_xp_for_level(level + 1)
    level_span = max(1, next_level_xp - level_start_xp)
    xp_into_level = safe_xp - level_start_xp

    return {
        "level": level,
        "total_xp": safe_xp,
        "level_start_xp": level_start_xp,
        "next_level_xp": next_level_xp,
        "xp_into_level": xp_into_level,
        "xp_to_next_level": max(0, next_level_xp - safe_xp),
        "level_xp_required": level_span,
        "progress_percentage": round((xp_into_level / level_span) * 100, 1),
    }


def preview_levels(max_level: int = 10) -> list[dict[str, int]]:
    """Return a small progression table for diagnostics and documentation."""
    if max_level < 1:
        return []
    return [
        {
            "level": level,
            "cumulative_xp": cumulative_xp_for_level(level),
            "xp_to_next": xp_cost_for_level(level),
        }
        for level in range(max_level)
    ]


if __name__ == "__main__":
    print("=" * 68)
    print("OPERATOR ZERO LEVEL CURVE")
    print("=" * 68)
    for row in preview_levels(12):
        print(
            f"Level {row['level']:>2} | "
            f"Cumulative XP {row['cumulative_xp']:>6} | "
            f"Next level cost {row['xp_to_next']:>5}"
        )

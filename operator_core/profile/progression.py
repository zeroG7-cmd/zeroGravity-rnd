"""Central Operator level curve and progression calculations."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

BASE_XP = 100
CURVE_EXPONENT = 1.5


def xp_cost_for_level(level: int) -> int:
    if level < 0:
        raise ValueError("Level cannot be negative")
    return round(BASE_XP * ((level + 1) ** CURVE_EXPONENT))


@lru_cache(maxsize=None)
def cumulative_xp_for_level(level: int) -> int:
    if level < 0:
        raise ValueError("Level cannot be negative")
    return sum(xp_cost_for_level(current) for current in range(level))


def calculate_level(total_xp: int) -> int:
    safe_xp = max(0, int(total_xp))
    level = 0
    while safe_xp >= cumulative_xp_for_level(level + 1):
        level += 1
    return level


def get_level_progress(total_xp: int) -> dict[str, Any]:
    safe_xp = max(0, int(total_xp))
    level = calculate_level(safe_xp)
    level_start_xp = cumulative_xp_for_level(level)
    next_level_xp = cumulative_xp_for_level(level + 1)
    level_xp_required = max(1, next_level_xp - level_start_xp)
    xp_into_level = safe_xp - level_start_xp
    return {
        "level": level,
        "total_xp": safe_xp,
        "level_start_xp": level_start_xp,
        "next_level_xp": next_level_xp,
        "xp_into_level": xp_into_level,
        "xp_to_next_level": max(0, next_level_xp - safe_xp),
        "level_xp_required": level_xp_required,
        "progress_percentage": round((xp_into_level / level_xp_required) * 100, 1),
    }

"""Pure XP allocation calculations used by every Operator subsystem."""
from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from typing import Any

from operator_core.distribution.models import DistributionTarget, XPAllocation


def _coerce_target(raw: DistributionTarget | Mapping[str, Any]) -> DistributionTarget:
    if isinstance(raw, DistributionTarget):
        return raw
    return DistributionTarget(
        target_id=str(raw.get("target_id") or raw.get("competency_id") or raw.get("stat") or "").strip(),
        target_type=str(raw.get("target_type") or ("competency" if raw.get("competency_id") else "stat")).strip(),
        weight=float(raw.get("weight", 0)),
        label=raw.get("label"),
        metadata=dict(raw.get("metadata", {})),
    )


def normalise_targets(
    raw_targets: Iterable[DistributionTarget | Mapping[str, Any]],
) -> list[DistributionTarget]:
    """Validate, merge duplicate destinations, and normalise weights to 1.0."""
    merged: "OrderedDict[tuple[str, str], dict[str, Any]]" = OrderedDict()
    for raw in raw_targets:
        target = _coerce_target(raw)
        key = (target.target_type, target.target_id)
        if key not in merged:
            merged[key] = {
                "target_id": target.target_id,
                "target_type": target.target_type,
                "weight": 0.0,
                "label": target.label,
                "metadata": dict(target.metadata),
            }
        merged[key]["weight"] += target.weight

    if not merged:
        raise ValueError("At least one valid XP target is required")

    total_weight = sum(item["weight"] for item in merged.values())
    if total_weight <= 0:
        raise ValueError("XP target weights must sum to more than zero")

    return [
        DistributionTarget(
            target_id=item["target_id"],
            target_type=item["target_type"],
            weight=item["weight"] / total_weight,
            label=item["label"],
            metadata=item["metadata"],
        )
        for item in merged.values()
    ]


def allocate_xp(
    total_xp: int,
    raw_targets: Iterable[DistributionTarget | Mapping[str, Any]],
) -> list[XPAllocation]:
    """Distribute an integer reward pool using the largest-remainder method.

    The allocations always sum exactly to ``total_xp``. This prevents a
    40-XP activity from accidentally becoming 39 or 41 XP because of rounding.
    """
    total_xp = int(total_xp)
    if total_xp < 0:
        raise ValueError("total_xp cannot be negative")

    targets = normalise_targets(raw_targets)
    exact = [total_xp * target.weight for target in targets]
    floors = [math.floor(value) for value in exact]
    remainder = total_xp - sum(floors)
    ranked = sorted(
        range(len(targets)),
        key=lambda index: (exact[index] - floors[index], -index),
        reverse=True,
    )
    for index in ranked[:remainder]:
        floors[index] += 1

    return [
        XPAllocation(
            target_id=target.target_id,
            target_type=target.target_type,
            weight=round(target.weight, 8),
            xp=floors[index],
            label=target.label,
            metadata=dict(target.metadata),
        )
        for index, target in enumerate(targets)
        if floors[index] > 0 or total_xp == 0
    ]

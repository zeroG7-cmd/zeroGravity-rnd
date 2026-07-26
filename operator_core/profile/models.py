"""Canonical data models for the Operator profile and progression state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    operator_id: str = "zero"
    display_name: str = "Zero"
    title: str = "Operator"
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProgressionSnapshot:
    total_xp: int
    level: int
    level_start_xp: int
    next_level_xp: int
    xp_into_level: int
    xp_to_next_level: int
    level_xp_required: int
    progress_percentage: float
    applied_receipts: tuple[str, ...] = ()
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["applied_receipts"] = list(self.applied_receipts)
        return data


@dataclass(frozen=True, slots=True)
class ProfileApplicationResult:
    receipt_id: str
    applied: bool
    total_xp_added: int
    progression: Mapping[str, Any]
    stat_awards: Mapping[str, int]
    target_awards: Mapping[str, Mapping[str, int]]

"""Data models for shared Operator XP distribution."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class DistributionTarget:
    """One weighted destination for a share of an XP reward pool."""

    target_id: str
    target_type: str
    weight: float
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("target_id must not be empty")
        if not self.target_type.strip():
            raise ValueError("target_type must not be empty")
        if self.weight <= 0:
            raise ValueError("weight must be greater than zero")


@dataclass(frozen=True, slots=True)
class XPAllocation:
    """The exact integer XP assigned to one destination."""

    target_id: str
    target_type: str
    weight: float
    xp: int
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DistributionReceipt:
    """Auditable result of distributing one source event's XP."""

    source_event_id: str
    total_xp: int
    allocations: tuple[XPAllocation, ...]
    receipt_id: str = field(default_factory=lambda: f"xpr_{uuid4().hex}")
    ruleset_version: str = "1"
    created_at: str = field(default_factory=utc_now_iso)
    source_event_type: str | None = None
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_event_id.strip():
            raise ValueError("source_event_id must not be empty")
        if self.total_xp < 0:
            raise ValueError("total_xp cannot be negative")
        if sum(item.xp for item in self.allocations) != self.total_xp:
            raise ValueError("allocation XP must sum exactly to total_xp")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DistributionReceipt":
        allocations = tuple(
            XPAllocation(
                target_id=str(item["target_id"]),
                target_type=str(item["target_type"]),
                weight=float(item["weight"]),
                xp=int(item["xp"]),
                label=item.get("label"),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("allocations", [])
        )
        return cls(
            source_event_id=str(data["source_event_id"]),
            total_xp=int(data["total_xp"]),
            allocations=allocations,
            receipt_id=str(data.get("receipt_id") or f"xpr_{uuid4().hex}"),
            ruleset_version=str(data.get("ruleset_version", "1")),
            created_at=str(data.get("created_at") or utc_now_iso()),
            source_event_type=data.get("source_event_type"),
            source=data.get("source"),
            metadata=dict(data.get("metadata", {})),
        )

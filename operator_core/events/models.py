"""Data model for immutable Operator events."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class OperatorEvent:
    """One immutable fact emitted by an Operator subsystem.

    Event payloads are intentionally flexible so learning, journal, lab,
    business, and future systems can all use the same ledger.
    """

    event_type: str
    source: str
    payload: Mapping[str, Any]
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    occurred_at: str = field(default_factory=utc_now_iso)
    recorded_at: str = field(default_factory=utc_now_iso)
    actor: str = "operator"
    idempotency_key: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    schema_version: int = SCHEMA_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        if self.idempotency_key is not None and not self.idempotency_key.strip():
            raise ValueError("idempotency_key must be omitted or non-empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OperatorEvent":
        return cls(
            event_type=str(data["event_type"]),
            source=str(data["source"]),
            payload=dict(data.get("payload", {})),
            event_id=str(data.get("event_id") or f"evt_{uuid4().hex}"),
            occurred_at=str(data.get("occurred_at") or utc_now_iso()),
            recorded_at=str(data.get("recorded_at") or utc_now_iso()),
            actor=str(data.get("actor") or "operator"),
            idempotency_key=data.get("idempotency_key"),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            metadata=dict(data.get("metadata", {})),
        )

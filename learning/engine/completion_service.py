"""Bridge learning completions into the shared Operator Core.

This module deliberately owns only learning-specific translation.  Event
storage, XP allocation, duplicate protection, and receipts remain in
``operator_core``.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from operator_core.distribution.models import DistributionReceipt
from operator_core.distribution.service import DistributionService
from operator_core.events.models import OperatorEvent
from operator_core.events.service import EventLedger

ProgressionUpdater = Callable[[list[dict[str, Any]]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class LearningCompletionResult:
    event: OperatorEvent
    receipt: DistributionReceipt
    progression: Mapping[str, Any] | None = None


def _legacy_distribution(receipt: DistributionReceipt) -> list[dict[str, Any]]:
    """Convert shared allocations to the existing competency updater format."""
    return [
        {
            "competency_id": allocation.target_id,
            "weight": allocation.weight,
            "xp": allocation.xp,
        }
        for allocation in receipt.allocations
        if allocation.target_type == "competency"
    ]


class LearningCompletionService:
    """Emit one learning event and route its reward through Operator Core."""

    def __init__(
        self,
        *,
        ledger: EventLedger | None = None,
        distribution: DistributionService | None = None,
        progression_updater: ProgressionUpdater | None = None,
    ) -> None:
        self.ledger = ledger or EventLedger()
        self.distribution = distribution or DistributionService(ledger=self.ledger)
        self.progression_updater = progression_updater

    def complete(
        self,
        *,
        source: str,
        provider: str,
        resource_id: str,
        unit_id: str,
        unit_title: str,
        total_xp: int,
        competency_targets: Iterable[Mapping[str, Any]],
        payload: Mapping[str, Any] | None = None,
        occurred_at: str | None = None,
        external_event_id: str | None = None,
    ) -> LearningCompletionResult:
        if total_xp < 0:
            raise ValueError("total_xp cannot be negative")
        if not resource_id.strip() or not unit_id.strip():
            raise ValueError("resource_id and unit_id are required")

        targets = [
            {
                "target_id": str(item.get("target_id") or item.get("competency_id") or ""),
                "target_type": str(item.get("target_type") or "competency"),
                "weight": float(item.get("weight", 0)),
                "label": item.get("label"),
                "metadata": dict(item.get("metadata", {})),
            }
            for item in competency_targets
        ]
        if not targets:
            raise ValueError("At least one competency target is required")

        idempotency_key = (
            f"learning:{provider.strip().lower()}:{resource_id.strip()}:{unit_id.strip()}:completed"
        )
        event_payload: dict[str, Any] = {
            "provider": provider,
            "resource_id": resource_id,
            "unit_id": unit_id,
            "unit_title": unit_title,
            "base_xp": int(total_xp),
            "xp_targets": targets,
        }
        event_payload.update(dict(payload or {}))
        if external_event_id:
            event_payload["external_event_id"] = external_event_id

        event = OperatorEvent(
            event_type="learning_completed",
            source=source,
            payload=event_payload,
            occurred_at=occurred_at or OperatorEvent.__dataclass_fields__["occurred_at"].default_factory(),
            idempotency_key=idempotency_key,
            correlation_id=external_event_id,
        )
        stored_event = self.ledger.append(event, allow_existing=True)
        receipt = self.distribution.distribute_event(stored_event)

        progression: Mapping[str, Any] | None = None
        if self.progression_updater is not None:
            allocations = _legacy_distribution(receipt)
            if allocations:
                progression = self.progression_updater(allocations)

        return LearningCompletionResult(
            event=stored_event,
            receipt=receipt,
            progression=progression,
        )

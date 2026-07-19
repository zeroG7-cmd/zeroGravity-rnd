"""Shared service that turns Operator events into auditable XP receipts."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from operator_core.distribution.calculator import allocate_xp
from operator_core.distribution.models import DistributionReceipt, DistributionTarget
from operator_core.distribution.receipts import ReceiptStore
from operator_core.events.models import OperatorEvent
from operator_core.events.service import EventLedger


class DistributionService:
    """Calculate and record XP without owning any learning or journal logic."""

    def __init__(
        self,
        *,
        ledger: EventLedger | None = None,
        receipt_store: ReceiptStore | None = None,
        ruleset_version: str = "1",
    ) -> None:
        self.ledger = ledger or EventLedger()
        self.receipt_store = receipt_store or ReceiptStore()
        self.ruleset_version = ruleset_version

    def distribute_event(
        self,
        event: OperatorEvent | str,
        *,
        total_xp: int | None = None,
        targets: Iterable[DistributionTarget | Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DistributionReceipt:
        source_event = self._resolve_event(event)
        existing = self.receipt_store.get_for_event(source_event.event_id, self.ruleset_version)
        if existing is not None:
            return existing

        reward_pool = self._resolve_total_xp(source_event, total_xp)
        resolved_targets = list(targets) if targets is not None else self._resolve_targets(source_event)
        allocations = tuple(allocate_xp(reward_pool, resolved_targets))
        receipt = DistributionReceipt(
            source_event_id=source_event.event_id,
            source_event_type=source_event.event_type,
            source=source_event.source,
            total_xp=reward_pool,
            allocations=allocations,
            ruleset_version=self.ruleset_version,
            metadata=dict(metadata or {}),
        )
        stored = self.receipt_store.save(receipt)

        distribution_event = OperatorEvent(
            event_type="xp_distributed",
            source="operator_core.distribution",
            payload={
                "receipt_id": stored.receipt_id,
                "source_event_id": source_event.event_id,
                "total_xp": stored.total_xp,
                "allocations": [
                    {
                        "target_id": item.target_id,
                        "target_type": item.target_type,
                        "weight": item.weight,
                        "xp": item.xp,
                    }
                    for item in stored.allocations
                ],
                "ruleset_version": stored.ruleset_version,
            },
            idempotency_key=f"xp_distribution:{source_event.event_id}:{self.ruleset_version}",
            correlation_id=source_event.correlation_id or source_event.event_id,
            causation_id=source_event.event_id,
        )
        self.ledger.append(distribution_event, allow_existing=True)
        return stored

    def _resolve_event(self, event: OperatorEvent | str) -> OperatorEvent:
        if isinstance(event, OperatorEvent):
            return event
        found = self.ledger.get(str(event))
        if found is None:
            raise KeyError(f"Operator event was not found: {event}")
        return found

    @staticmethod
    def _resolve_total_xp(event: OperatorEvent, override: int | None) -> int:
        raw = override
        if raw is None:
            raw = event.payload.get("base_xp", event.payload.get("xp"))
        if raw is None:
            raise ValueError("No XP reward pool was supplied. Use total_xp or event.payload.base_xp")
        value = int(raw)
        if value < 0:
            raise ValueError("XP reward pool cannot be negative")
        return value

    @staticmethod
    def _resolve_targets(event: OperatorEvent) -> list[Mapping[str, Any]]:
        payload = event.payload
        for key in ("xp_targets", "competency_awards", "stat_awards", "targets"):
            raw = payload.get(key)
            if isinstance(raw, list) and raw:
                return raw
        raise ValueError(
            "No XP targets were supplied. Use targets or add xp_targets to the source event payload"
        )


_default_service = DistributionService()


def distribute_event(
    event: OperatorEvent | str,
    **kwargs: Any,
) -> DistributionReceipt:
    """Convenience entry point for learning, journal, lab, and business engines."""
    return _default_service.distribute_event(event, **kwargs)

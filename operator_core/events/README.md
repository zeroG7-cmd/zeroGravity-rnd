# Operator Event Ledger

This folder contains the shared, append-only history used by every Operator subsystem.

```text
Learning Engine ─┐
Journal Engine ──┤
Lab Engine ──────┼──> Operator Event Ledger
Business Engine ─┤
Execution Engine ┘
```

## Runtime files

- `operator_events.jsonl` — immutable event stream; one JSON object per line.
- `event_index.json` — rebuildable lookup index for event IDs and idempotency keys.
- `provider_events.json` and `receipts/` — preserved legacy provider records. They are not deleted by this upgrade.

## Basic use

```python
from operator_core.events import emit_event

event = emit_event(
    event_type="learning_completed",
    source="learning",
    payload={"resource_id": "linux-course", "unit_id": "lesson-01"},
    idempotency_key="learning:linux-course:lesson-01:completed",
)
```

Use a stable `idempotency_key` for actions that must only earn progression once. Repeating the same key raises `DuplicateEventError` unless a caller explicitly requests the existing record through `EventLedger.append(..., allow_existing=True)`.

The ledger records facts only. XP calculation and stat updates belong to the separate distribution/progression services.

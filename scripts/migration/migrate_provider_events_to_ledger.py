"""Import legacy provider_events.json records into the shared event ledger.

The original file and receipt files remain untouched. Running the migration more than
once is safe because each imported record receives a stable idempotency key.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from operator_core.events import EventLedger
from shared.config.paths import OPERATOR_EVENTS
from shared.libraries.json_store import load_json


def migrate() -> tuple[int, int]:
    legacy_path = OPERATOR_EVENTS / "provider_events.json"
    payload = load_json(legacy_path, {}) or {}
    processed = payload.get("processed", {}) if isinstance(payload, dict) else {}
    if not isinstance(processed, dict):
        raise ValueError("provider_events.json has an invalid 'processed' section")

    ledger = EventLedger()
    imported = 0
    skipped = 0
    for legacy_id, record in processed.items():
        if not isinstance(record, dict):
            continue
        key = f"legacy-provider:{legacy_id}"
        if ledger.has_idempotency_key(key):
            skipped += 1
            continue
        ledger.emit(
            event_type="learning_completed",
            source="legacy_provider_import",
            payload={
                "legacy_event_id": legacy_id,
                "provider_record": record,
            },
            idempotency_key=key,
            occurred_at=str(record.get("processed_at") or record.get("completed_at") or ""),
            metadata={"migration": "provider_events_v2"},
        )
        imported += 1
    return imported, skipped


if __name__ == "__main__":
    imported, skipped = migrate()
    print(f"Imported {imported} legacy provider events.")
    print(f"Skipped {skipped} events already present.")
    print("The original provider_events.json and receipts were not deleted.")

"""Append-only event ledger shared by every Operator subsystem."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from operator_core.events.models import OperatorEvent
from shared.config.paths import OPERATOR_EVENTS
from shared.libraries.json_store import load_json, save_json

DEFAULT_LEDGER_PATH = OPERATOR_EVENTS / "operator_events.jsonl"
DEFAULT_INDEX_PATH = OPERATOR_EVENTS / "event_index.json"
_WRITE_LOCK = threading.RLock()


class DuplicateEventError(ValueError):
    """Raised when an idempotency key has already been recorded."""


class EventLedger:
    """Small append-only JSONL ledger with a rebuildable lookup index."""

    def __init__(
        self,
        ledger_path: Path = DEFAULT_LEDGER_PATH,
        index_path: Path = DEFAULT_INDEX_PATH,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.index_path = Path(index_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        event: OperatorEvent | Mapping[str, Any],
        *,
        allow_existing: bool = False,
    ) -> OperatorEvent:
        record = event if isinstance(event, OperatorEvent) else OperatorEvent.from_dict(event)

        with _WRITE_LOCK:
            index = self._load_or_rebuild_index()
            existing_id = self._find_existing(index, record)
            if existing_id:
                if allow_existing:
                    existing = self.get(existing_id)
                    if existing is None:
                        raise RuntimeError("Event index points to a missing ledger record")
                    return existing
                raise DuplicateEventError(
                    f"Event already exists: {record.idempotency_key or record.event_id}"
                )

            serialized = json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":"))
            with self.ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized + "\n")
                handle.flush()
                os.fsync(handle.fileno())

            index.setdefault("event_ids", {})[record.event_id] = {
                "event_type": record.event_type,
                "recorded_at": record.recorded_at,
            }
            if record.idempotency_key:
                index.setdefault("idempotency_keys", {})[record.idempotency_key] = record.event_id
            index["event_count"] = int(index.get("event_count", 0)) + 1
            save_json(self.index_path, index)
            return record

    def emit(
        self,
        event_type: str,
        source: str,
        payload: Mapping[str, Any],
        **kwargs: Any,
    ) -> OperatorEvent:
        return self.append(OperatorEvent(event_type=event_type, source=source, payload=payload, **kwargs))

    def iter_events(
        self,
        *,
        event_type: str | None = None,
        source: str | None = None,
        correlation_id: str | None = None,
        newest_first: bool = False,
        limit: int | None = None,
    ) -> Iterator[OperatorEvent]:
        if not self.ledger_path.exists():
            return iter(())

        def generator() -> Iterator[OperatorEvent]:
            matched: list[OperatorEvent] = []
            with self.ledger_path.open("r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        event = OperatorEvent.from_dict(json.loads(line))
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                        raise ValueError(
                            f"Invalid event at {self.ledger_path}:{line_number}: {exc}"
                        ) from exc
                    if event_type and event.event_type != event_type:
                        continue
                    if source and event.source != source:
                        continue
                    if correlation_id and event.correlation_id != correlation_id:
                        continue
                    if newest_first:
                        matched.append(event)
                    else:
                        yield event
                        if limit is not None:
                            limit_state[0] += 1
                            if limit_state[0] >= limit:
                                return
            if newest_first:
                selected = reversed(matched)
                for count, event in enumerate(selected, start=1):
                    yield event
                    if limit is not None and count >= limit:
                        return

        limit_state = [0]
        return generator()

    def list_events(self, **filters: Any) -> list[OperatorEvent]:
        return list(self.iter_events(**filters))

    def get(self, event_id: str) -> OperatorEvent | None:
        for event in self.iter_events():
            if event.event_id == event_id:
                return event
        return None

    def has_idempotency_key(self, key: str) -> bool:
        index = self._load_or_rebuild_index()
        return key in index.get("idempotency_keys", {})

    def rebuild_index(self) -> dict[str, Any]:
        index: dict[str, Any] = {
            "schema_version": 1,
            "event_count": 0,
            "event_ids": {},
            "idempotency_keys": {},
        }
        for event in self.iter_events():
            if event.event_id in index["event_ids"]:
                raise ValueError(f"Duplicate event_id in ledger: {event.event_id}")
            index["event_ids"][event.event_id] = {
                "event_type": event.event_type,
                "recorded_at": event.recorded_at,
            }
            if event.idempotency_key:
                existing = index["idempotency_keys"].get(event.idempotency_key)
                if existing and existing != event.event_id:
                    raise ValueError(
                        f"Duplicate idempotency_key in ledger: {event.idempotency_key}"
                    )
                index["idempotency_keys"][event.idempotency_key] = event.event_id
            index["event_count"] += 1
        save_json(self.index_path, index)
        return index

    def _load_or_rebuild_index(self) -> dict[str, Any]:
        index = load_json(self.index_path, None)
        if not isinstance(index, dict):
            return self.rebuild_index()
        index.setdefault("schema_version", 1)
        index.setdefault("event_count", 0)
        index.setdefault("event_ids", {})
        index.setdefault("idempotency_keys", {})
        return index

    @staticmethod
    def _find_existing(index: Mapping[str, Any], event: OperatorEvent) -> str | None:
        if event.event_id in index.get("event_ids", {}):
            return event.event_id
        if event.idempotency_key:
            return index.get("idempotency_keys", {}).get(event.idempotency_key)
        return None


_default_ledger = EventLedger()


def emit_event(event_type: str, source: str, payload: Mapping[str, Any], **kwargs: Any) -> OperatorEvent:
    """Convenience entry point used by learning, journal, lab, and business engines."""
    return _default_ledger.emit(event_type, source, payload, **kwargs)


def list_events(**filters: Any) -> list[OperatorEvent]:
    return _default_ledger.list_events(**filters)


def get_event(event_id: str) -> OperatorEvent | None:
    return _default_ledger.get(event_id)

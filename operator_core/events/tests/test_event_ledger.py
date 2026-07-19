from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from operator_core.events import DuplicateEventError, EventLedger, OperatorEvent


class EventLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.ledger = EventLedger(root / "events.jsonl", root / "index.json")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_append_and_read_event(self) -> None:
        event = self.ledger.emit(
            "journal_created",
            "journal",
            {"entry_id": "entry-001"},
            idempotency_key="journal:entry-001:created",
        )
        loaded = self.ledger.get(event.event_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.payload["entry_id"], "entry-001")

    def test_duplicate_idempotency_key_is_rejected(self) -> None:
        self.ledger.emit(
            "learning_completed",
            "learning",
            {"unit_id": "lesson-1"},
            idempotency_key="learning:course:lesson-1:completed",
        )
        with self.assertRaises(DuplicateEventError):
            self.ledger.emit(
                "learning_completed",
                "learning",
                {"unit_id": "lesson-1"},
                idempotency_key="learning:course:lesson-1:completed",
            )

    def test_allow_existing_returns_original_event(self) -> None:
        original = self.ledger.emit(
            "task_completed",
            "tasks",
            {"task_id": "task-1"},
            idempotency_key="task:task-1:completed",
        )
        duplicate = OperatorEvent(
            event_type="task_completed",
            source="tasks",
            payload={"task_id": "task-1"},
            idempotency_key="task:task-1:completed",
        )
        returned = self.ledger.append(duplicate, allow_existing=True)
        self.assertEqual(returned.event_id, original.event_id)

    def test_filters_and_newest_first(self) -> None:
        self.ledger.emit("journal_created", "journal", {"n": 1})
        self.ledger.emit("learning_completed", "learning", {"n": 2})
        self.ledger.emit("journal_created", "journal", {"n": 3})
        events = self.ledger.list_events(event_type="journal_created", newest_first=True)
        self.assertEqual([event.payload["n"] for event in events], [3, 1])

    def test_index_can_be_rebuilt(self) -> None:
        event = self.ledger.emit(
            "experiment_completed",
            "lab",
            {"experiment_id": "exp-1"},
            idempotency_key="lab:exp-1:completed",
        )
        self.ledger.index_path.unlink()
        index = self.ledger.rebuild_index()
        self.assertEqual(index["event_count"], 1)
        self.assertEqual(index["idempotency_keys"]["lab:exp-1:completed"], event.event_id)


if __name__ == "__main__":
    unittest.main()

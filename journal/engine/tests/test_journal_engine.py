from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from journal.engine.models import JournalEntryRequest, JournalEvidence
from journal.engine.service import JournalService
from operator_core.distribution.receipts import ReceiptStore
from operator_core.distribution.service import DistributionService
from operator_core.events.service import EventLedger


class JournalEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        ledger = EventLedger(
            ledger_path=self.root / "events" / "operator_events.jsonl",
            index_path=self.root / "events" / "event_index.json",
        )
        distributor = DistributionService(
            ledger=ledger,
            receipt_store=ReceiptStore(self.root / "receipts"),
        )
        self.ledger = ledger
        self.service = JournalService(
            entries_root=self.root / "journal" / "entries",
            index_path=self.root / "journal" / "indexes" / "entries.json",
            repo_root=self.root,
            ledger=ledger,
            distributor=distributor,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_entry_preserves_body_and_writes_manifest(self) -> None:
        body = "Raw thought — preserve this exactly.\nSecond line."
        manifest = self.service.create(
            JournalEntryRequest(
                title="Ground Control Insight",
                body=body,
                entry_types=("technical", "insight"),
                tags=("camera",),
                concepts=("Camera Systems",),
            )
        )
        markdown = (self.root / manifest.markdown_path).read_text(encoding="utf-8")
        payload = json.loads((self.root / manifest.manifest_path).read_text(encoding="utf-8"))
        self.assertIn(body, markdown)
        self.assertEqual(payload["entry_id"], manifest.entry_id)
        self.assertEqual(payload["concepts"], ["Camera Systems"])
        self.assertIsNotNone(payload["event_id"])
        self.assertIsNone(payload["receipt_id"])

    def test_journal_event_is_emitted(self) -> None:
        manifest = self.service.create(
            JournalEntryRequest(
                title="Business decision",
                body="I chose the next service milestone.",
                entry_types=("business", "decision"),
                projects=("zeroGravity",),
            )
        )
        events = self.ledger.list_events(event_type="journal_created")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_id, manifest.event_id)
        self.assertEqual(events[0].payload["projects"], ["zeroGravity"])

    def test_xp_distribution_is_optional_and_audited(self) -> None:
        manifest = self.service.create(
            JournalEntryRequest(
                title="Test reflection",
                body="I ran and documented the camera test.",
                entry_types=("test_log", "reflection"),
                base_xp=20,
                xp_targets=(
                    {"target_type": "stat", "target_id": "INT", "weight": 0.75},
                    {"target_type": "stat", "target_id": "DISC", "weight": 0.25},
                ),
                evidence=(JournalEvidence("file", "results/camera-test.md"),),
            )
        )
        self.assertIsNotNone(manifest.receipt_id)
        self.assertEqual(manifest.status, "processed")
        xp_events = self.ledger.list_events(event_type="xp_distributed")
        self.assertEqual(len(xp_events), 1)
        self.assertEqual(xp_events[0].payload["total_xp"], 20)
        allocated = sum(item["xp"] for item in xp_events[0].payload["allocations"])
        self.assertEqual(allocated, 20)

    def test_xp_requires_targets(self) -> None:
        with self.assertRaises(ValueError):
            JournalEntryRequest(
                title="Invalid reward",
                body="This should fail.",
                entry_types=("reflection",),
                base_xp=10,
            )

    def test_duplicate_titles_create_separate_entries(self) -> None:
        request = JournalEntryRequest(
            title="Same title",
            body="First body.",
            entry_types=("reflection",),
        )
        first = self.service.create(request)
        second = self.service.create(request)
        self.assertNotEqual(first.entry_id, second.entry_id)
        self.assertNotEqual(first.markdown_path, second.markdown_path)
        self.assertEqual(len(self.service.list_entries()), 2)

    def test_unknown_entry_type_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            JournalEntryRequest(
                title="Unknown type",
                body="Body.",
                entry_types=("made_up",),
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from learning.engine.completion_service import LearningCompletionService
from operator_core.distribution.receipts import ReceiptStore
from operator_core.distribution.service import DistributionService
from operator_core.events.service import EventLedger


class LearningCompletionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        ledger = EventLedger(root / "events.jsonl", root / "event_index.json")
        receipts = ReceiptStore(root / "receipts", root / "receipt_index.json")
        distribution = DistributionService(ledger=ledger, receipt_store=receipts)
        self.applied: list[list[dict]] = []
        self.service = LearningCompletionService(
            ledger=ledger,
            distribution=distribution,
            progression_updater=lambda awards: self.applied.append(awards) or {"total_xp": 20},
        )
        self.ledger = ledger

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_completion_emits_event_distributes_and_applies_progression(self) -> None:
        result = self.service.complete(
            source="learning.engine.manual",
            provider="youtube",
            resource_id="opencv-course",
            unit_id="thresholding",
            unit_title="Image Thresholding",
            total_xp=20,
            competency_targets=[
                {"competency_id": "opencv", "weight": 3},
                {"competency_id": "python", "weight": 1},
            ],
        )
        self.assertEqual(result.event.event_type, "learning_completed")
        self.assertEqual(result.receipt.total_xp, 20)
        self.assertEqual(sum(x["xp"] for x in self.applied[0]), 20)
        self.assertEqual(len(self.ledger.list_events(event_type="xp_distributed")), 1)

    def test_retry_reuses_event_and_receipt(self) -> None:
        kwargs = dict(
            source="learning.engine.provider",
            provider="boot.dev",
            resource_id="python",
            unit_id="lesson-1",
            unit_title="Variables",
            total_xp=10,
            competency_targets=[{"competency_id": "python", "weight": 1}],
        )
        first = self.service.complete(**kwargs)
        second = self.service.complete(**kwargs)
        self.assertEqual(first.event.event_id, second.event.event_id)
        self.assertEqual(first.receipt.receipt_id, second.receipt.receipt_id)
        self.assertEqual(len(self.ledger.list_events(event_type="learning_completed")), 1)

    def test_requires_targets(self) -> None:
        with self.assertRaises(ValueError):
            self.service.complete(
                source="learning.engine.manual",
                provider="manual",
                resource_id="book",
                unit_id="chapter-1",
                unit_title="Chapter 1",
                total_xp=5,
                competency_targets=[],
            )


if __name__ == "__main__":
    unittest.main()

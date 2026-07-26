from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from operator_core.distribution.calculator import allocate_xp, normalise_targets
from operator_core.distribution.receipts import ReceiptStore
from operator_core.distribution.service import DistributionService
from operator_core.events.models import OperatorEvent
from operator_core.events.service import EventLedger


class DistributionCalculatorTests(unittest.TestCase):
    def test_largest_remainder_preserves_total(self) -> None:
        awards = allocate_xp(10, [
            {"target_type": "stat", "target_id": "INT", "weight": 1},
            {"target_type": "stat", "target_id": "DISC", "weight": 1},
            {"target_type": "stat", "target_id": "SPIRIT", "weight": 1},
        ])
        self.assertEqual(sum(item.xp for item in awards), 10)
        self.assertEqual([item.xp for item in awards], [4, 3, 3])

    def test_weights_are_normalised(self) -> None:
        targets = normalise_targets([
            {"target_type": "stat", "target_id": "INT", "weight": 6},
            {"target_type": "stat", "target_id": "DISC", "weight": 2},
            {"target_type": "stat", "target_id": "SPIRIT", "weight": 2},
        ])
        self.assertAlmostEqual(sum(item.weight for item in targets), 1.0)
        self.assertEqual(targets[0].weight, 0.6)

    def test_duplicate_targets_are_merged(self) -> None:
        targets = normalise_targets([
            {"target_type": "competency", "target_id": "python", "weight": 1},
            {"target_type": "competency", "target_id": "python", "weight": 2},
            {"target_type": "competency", "target_id": "git", "weight": 1},
        ])
        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0].target_id, "python")
        self.assertEqual(targets[0].weight, 0.75)

    def test_invalid_reward_pool_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            allocate_xp(-1, [{"target_type": "stat", "target_id": "INT", "weight": 1}])


class DistributionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.ledger = EventLedger(root / "events.jsonl", root / "event_index.json")
        self.store = ReceiptStore(root / "receipts", root / "receipt_index.json")
        self.service = DistributionService(ledger=self.ledger, receipt_store=self.store)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _source_event(self) -> OperatorEvent:
        return self.ledger.append(OperatorEvent(
            event_type="journal_created",
            source="journal",
            payload={
                "base_xp": 40,
                "xp_targets": [
                    {"target_type": "stat", "target_id": "INT", "weight": 0.6},
                    {"target_type": "stat", "target_id": "DISC", "weight": 0.2},
                    {"target_type": "stat", "target_id": "SPIRIT", "weight": 0.2},
                ],
            },
            idempotency_key="journal:test-entry",
        ))

    def test_event_is_distributed_and_receipted(self) -> None:
        event = self._source_event()
        receipt = self.service.distribute_event(event.event_id)
        self.assertEqual(receipt.total_xp, 40)
        self.assertEqual([item.xp for item in receipt.allocations], [24, 8, 8])
        self.assertIsNotNone(self.store.get(receipt.receipt_id))

    def test_retry_returns_same_receipt(self) -> None:
        event = self._source_event()
        first = self.service.distribute_event(event)
        second = self.service.distribute_event(event)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(len(self.ledger.list_events(event_type="xp_distributed")), 1)

    def test_missing_targets_are_rejected(self) -> None:
        event = self.ledger.append(OperatorEvent(
            event_type="task_completed",
            source="tasks",
            payload={"base_xp": 20},
        ))
        with self.assertRaises(ValueError):
            self.service.distribute_event(event)

    def test_override_supports_legacy_callers(self) -> None:
        event = self.ledger.append(OperatorEvent(
            event_type="learning_completed",
            source="learning",
            payload={},
        ))
        receipt = self.service.distribute_event(
            event,
            total_xp=15,
            targets=[{"competency_id": "python", "weight": 1}],
        )
        self.assertEqual(receipt.allocations[0].target_type, "competency")
        self.assertEqual(receipt.allocations[0].xp, 15)


if __name__ == "__main__":
    unittest.main()

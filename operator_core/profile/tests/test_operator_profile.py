from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from operator_core.distribution.models import DistributionReceipt, XPAllocation
from operator_core.profile.progression import get_level_progress
from operator_core.profile.repository import ProfileRepository
from operator_core.profile.service import OperatorProfileService


class OperatorProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = ProfileRepository(self.root / "profile")
        self.service = OperatorProfileService(repository=self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def receipt(receipt_id: str = "xpr_test") -> DistributionReceipt:
        return DistributionReceipt(
            receipt_id=receipt_id,
            source_event_id="evt_test",
            total_xp=40,
            allocations=(
                XPAllocation("INT", "stat", 0.6, 24),
                XPAllocation("DISC", "stat", 0.2, 8),
                XPAllocation("int.robotics.perception", "competency", 0.2, 8),
            ),
        )

    def test_profile_is_initialised_with_canonical_documents(self) -> None:
        profile = self.service.get_profile()
        self.assertEqual(profile["identity"]["operator_id"], "zero")
        self.assertIn("INT", profile["stats"]["stats"])
        self.assertEqual(profile["progression"]["total_xp"], 0)
        self.assertTrue((self.root / "profile" / "preferences.json").exists())

    def test_receipt_updates_total_xp_and_main_stats(self) -> None:
        result = self.service.apply_receipt(self.receipt())
        profile = self.service.get_profile()
        self.assertTrue(result.applied)
        self.assertEqual(profile["progression"]["total_xp"], 40)
        self.assertEqual(profile["stats"]["stats"]["INT"]["xp"], 24)
        self.assertEqual(profile["stats"]["stats"]["DISC"]["xp"], 8)

    def test_non_stat_allocations_are_preserved_in_award_totals(self) -> None:
        self.service.apply_receipt(self.receipt())
        awards = self.repository.load_awards()["target_totals"]
        self.assertEqual(awards["competency"]["int.robotics.perception"], 8)

    def test_same_receipt_cannot_be_applied_twice(self) -> None:
        first = self.service.apply_receipt(self.receipt())
        second = self.service.apply_receipt(self.receipt())
        self.assertTrue(first.applied)
        self.assertFalse(second.applied)
        self.assertEqual(self.service.get_profile()["progression"]["total_xp"], 40)

    def test_level_progress_uses_cumulative_curve(self) -> None:
        progress = get_level_progress(100)
        self.assertEqual(progress["level"], 1)
        self.assertEqual(progress["xp_into_level"], 0)
        self.assertGreater(progress["next_level_xp"], 100)

    def test_baseline_migration_preserves_stat_totals(self) -> None:
        self.repository.replace_baseline(
            stat_xp={"INT": 1360, "CON": 0},
            total_xp=1360,
            migration_source="competencies.json",
        )
        profile = self.service.get_profile()
        self.assertEqual(profile["stats"]["stats"]["INT"]["xp"], 1360)
        self.assertEqual(profile["progression"]["total_xp"], 1360)
        self.assertIn("migration", profile["progression"])


if __name__ == "__main__":
    unittest.main()

"""Apply XP receipts to the authoritative Operator profile exactly once."""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from operator_core.distribution.models import DistributionReceipt
from operator_core.distribution.receipts import ReceiptStore
from operator_core.profile.models import ProfileApplicationResult, utc_now_iso
from operator_core.profile.progression import get_level_progress
from operator_core.profile.repository import ProfileRepository

_LOCK = threading.RLock()


class OperatorProfileService:
    def __init__(
        self,
        *,
        repository: ProfileRepository | None = None,
        receipt_store: ReceiptStore | None = None,
    ) -> None:
        self.repository = repository or ProfileRepository()
        self.receipt_store = receipt_store or ReceiptStore()
        self.repository.initialise()

    def get_profile(self) -> dict[str, Any]:
        return self.repository.load_profile()

    def apply_receipt(self, receipt: DistributionReceipt | str) -> ProfileApplicationResult:
        resolved = self._resolve_receipt(receipt)
        with _LOCK:
            stats_document = self.repository.load_stats()
            progression = self.repository.load_progression()
            awards_document = self.repository.load_awards()
            applied = list(progression.get("applied_receipts", []))

            if resolved.receipt_id in applied:
                return ProfileApplicationResult(
                    receipt_id=resolved.receipt_id,
                    applied=False,
                    total_xp_added=0,
                    progression=progression,
                    stat_awards={},
                    target_awards={},
                )

            stats = stats_document.setdefault("stats", {})
            target_totals = awards_document.setdefault("target_totals", {})
            stat_awards: dict[str, int] = defaultdict(int)
            target_awards: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

            for allocation in resolved.allocations:
                target_type = allocation.target_type.strip().lower()
                target_id = allocation.target_id.strip()
                xp = int(allocation.xp)
                if xp < 0:
                    raise ValueError("Receipt allocations cannot contain negative XP")
                target_awards[target_type][target_id] += xp
                bucket = target_totals.setdefault(target_type, {})
                bucket[target_id] = int(bucket.get(target_id, 0)) + xp
                if target_type == "stat":
                    stat_entry = stats.setdefault(target_id, {"xp": 0})
                    stat_entry["xp"] = int(stat_entry.get("xp", 0)) + xp
                    stat_awards[target_id] += xp

            new_total = int(progression.get("total_xp", 0)) + resolved.total_xp
            updated_progression = get_level_progress(new_total)
            applied.append(resolved.receipt_id)
            now = utc_now_iso()
            updated_progression.update(
                {
                    "schema_version": 1,
                    "applied_receipts": applied,
                    "updated_at": now,
                    "last_receipt_id": resolved.receipt_id,
                }
            )
            stats_document.update({"schema_version": 1, "stats": stats, "updated_at": now})
            awards_document.update(
                {"schema_version": 1, "target_totals": target_totals, "updated_at": now}
            )
            self.repository.save_state(
                stats=stats_document,
                progression=updated_progression,
                awards=awards_document,
            )
            return ProfileApplicationResult(
                receipt_id=resolved.receipt_id,
                applied=True,
                total_xp_added=resolved.total_xp,
                progression=updated_progression,
                stat_awards=dict(stat_awards),
                target_awards={kind: dict(values) for kind, values in target_awards.items()},
            )

    def _resolve_receipt(self, receipt: DistributionReceipt | str) -> DistributionReceipt:
        if isinstance(receipt, DistributionReceipt):
            return receipt
        found = self.receipt_store.get(str(receipt))
        if found is None:
            raise KeyError(f"XP receipt was not found: {receipt}")
        return found


_default_service = OperatorProfileService()


def get_operator_profile() -> dict[str, Any]:
    return _default_service.get_profile()


def apply_xp_receipt(receipt: DistributionReceipt | str) -> ProfileApplicationResult:
    return _default_service.apply_receipt(receipt)

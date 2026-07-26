"""Persistent, duplicate-safe storage for XP distribution receipts."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from operator_core.distribution.models import DistributionReceipt
from shared.config.paths import OPERATOR_ROOT
from shared.libraries.json_store import load_json, save_json

DEFAULT_RECEIPTS_DIR = OPERATOR_ROOT / "distribution" / "receipts"
DEFAULT_INDEX_PATH = OPERATOR_ROOT / "distribution" / "receipt_index.json"
_LOCK = threading.RLock()


def _safe_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return clean or "event"


class ReceiptStore:
    def __init__(
        self,
        receipts_dir: Path = DEFAULT_RECEIPTS_DIR,
        index_path: Path = DEFAULT_INDEX_PATH,
    ) -> None:
        self.receipts_dir = Path(receipts_dir)
        self.index_path = Path(index_path)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def save(self, receipt: DistributionReceipt) -> DistributionReceipt:
        """Save once per source event and ruleset, returning the existing receipt on retry."""
        key = self._key(receipt.source_event_id, receipt.ruleset_version)
        with _LOCK:
            index = self._load_index()
            existing_path = index.get("by_source_event", {}).get(key)
            if existing_path:
                existing = self._read_path(Path(existing_path))
                if existing is not None:
                    return existing

            path = self.receipts_dir / f"{_safe_name(receipt.source_event_id)}__v{_safe_name(receipt.ruleset_version)}.json"
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
            index.setdefault("by_source_event", {})[key] = str(path)
            index.setdefault("by_receipt_id", {})[receipt.receipt_id] = str(path)
            index["receipt_count"] = len(index["by_receipt_id"])
            save_json(self.index_path, index)
            return receipt

    def get_for_event(self, source_event_id: str, ruleset_version: str = "1") -> DistributionReceipt | None:
        index = self._load_index()
        path = index.get("by_source_event", {}).get(self._key(source_event_id, ruleset_version))
        return self._read_path(Path(path)) if path else None

    def get(self, receipt_id: str) -> DistributionReceipt | None:
        index = self._load_index()
        path = index.get("by_receipt_id", {}).get(receipt_id)
        return self._read_path(Path(path)) if path else None

    def _load_index(self) -> dict[str, Any]:
        data = load_json(self.index_path, None)
        if not isinstance(data, dict):
            data = {"schema_version": 1, "receipt_count": 0, "by_source_event": {}, "by_receipt_id": {}}
        data.setdefault("schema_version", 1)
        data.setdefault("receipt_count", 0)
        data.setdefault("by_source_event", {})
        data.setdefault("by_receipt_id", {})
        return data

    @staticmethod
    def _read_path(path: Path) -> DistributionReceipt | None:
        if not path.exists():
            return None
        return DistributionReceipt.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def _key(source_event_id: str, ruleset_version: str) -> str:
        return f"{source_event_id}::{ruleset_version}"

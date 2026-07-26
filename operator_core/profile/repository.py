"""Atomic JSON persistence for the canonical Operator profile."""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from operator_core.profile.models import OperatorIdentity, utc_now_iso
from operator_core.profile.overall import calculate_overall
from operator_core.profile.progression import get_level_progress
from shared.config.paths import OPERATOR_PROFILE_DATA

_LOCK = threading.RLock()
DEFAULT_STATS = ("CON", "INT", "STR", "DEX", "DISC", "WILL", "SPIRIT")


class ProfileRepository:
    def __init__(self, data_root: Path = OPERATOR_PROFILE_DATA) -> None:
        self.data_root = Path(data_root)
        self.identity_path = self.data_root / "identity.json"
        self.stats_path = self.data_root / "stats.json"
        self.progression_path = self.data_root / "progression.json"
        self.preferences_path = self.data_root / "preferences.json"
        self.goals_path = self.data_root / "active_goals.json"
        self.awards_path = self.data_root / "awards.json"

    def initialise(self, *, stat_ids: tuple[str, ...] = DEFAULT_STATS) -> None:
        with _LOCK:
            self.data_root.mkdir(parents=True, exist_ok=True)
            self._write_if_missing(self.identity_path, OperatorIdentity().to_dict())
            self._write_if_missing(
                self.stats_path,
                {
                    "schema_version": 1,
                    "stats": {stat_id: {"xp": 0} for stat_id in stat_ids},
                    "updated_at": utc_now_iso(),
                },
            )
            progress = get_level_progress(0)
            progress.update({"schema_version": 1, "applied_receipts": [], "updated_at": utc_now_iso()})
            self._write_if_missing(self.progression_path, progress)
            self._write_if_missing(
                self.preferences_path,
                {
                    "schema_version": 1,
                    "progression_mode": "balanced",
                    "default_journal_xp": 0,
                    "show_spiritual_domains": True,
                },
            )
            self._write_if_missing(self.goals_path, {"schema_version": 1, "goals": []})
            self._write_if_missing(
                self.awards_path,
                {"schema_version": 1, "target_totals": {}, "updated_at": utc_now_iso()},
            )

    def load_identity(self) -> dict[str, Any]:
        self.initialise()
        return self._read(self.identity_path)

    def load_stats(self) -> dict[str, Any]:
        self.initialise()
        return self._read(self.stats_path)

    def load_progression(self) -> dict[str, Any]:
        self.initialise()
        return self._read(self.progression_path)

    def load_awards(self) -> dict[str, Any]:
        self.initialise()
        return self._read(self.awards_path)

    def load_profile(self) -> dict[str, Any]:
        self.initialise()
        stats = self._read(self.stats_path)
        return {
            "identity": self._read(self.identity_path),
            "stats": stats,
            "overall": calculate_overall(),
            "progression": self._read(self.progression_path),
            "preferences": self._read(self.preferences_path),
            "active_goals": self._read(self.goals_path),
            "awards": self._read(self.awards_path),
        }

    def save_state(
        self,
        *,
        stats: Mapping[str, Any],
        progression: Mapping[str, Any],
        awards: Mapping[str, Any],
    ) -> None:
        with _LOCK:
            self._write(self.stats_path, stats)
            self._write(self.progression_path, progression)
            self._write(self.awards_path, awards)

    def replace_baseline(
        self,
        *,
        stat_xp: Mapping[str, int],
        total_xp: int,
        migration_source: str,
    ) -> None:
        """Initialise the canonical profile from legacy data without deleting it."""
        self.initialise(stat_ids=tuple(stat_xp) or DEFAULT_STATS)
        now = utc_now_iso()
        stats = {
            "schema_version": 1,
            "stats": {name: {"xp": max(0, int(xp))} for name, xp in stat_xp.items()},
            "updated_at": now,
            "migration": {"source": migration_source, "migrated_at": now},
        }
        progression = get_level_progress(total_xp)
        progression.update(
            {
                "schema_version": 1,
                "applied_receipts": [],
                "updated_at": now,
                "migration": {"source": migration_source, "migrated_at": now},
            }
        )
        awards = {
            "schema_version": 1,
            "target_totals": {
                "stat": {name: max(0, int(xp)) for name, xp in stat_xp.items()}
            },
            "updated_at": now,
            "migration": {"source": migration_source, "migrated_at": now},
        }
        self.save_state(stats=stats, progression=progression, awards=awards)

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return deepcopy(data) if isinstance(data, dict) else {}

    @staticmethod
    def _write(path: Path, data: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(dict(data), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(path)

    def _write_if_missing(self, path: Path, data: Mapping[str, Any]) -> None:
        if not path.exists():
            self._write(path, data)

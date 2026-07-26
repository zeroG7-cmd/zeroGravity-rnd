"""Create the canonical Operator profile from existing competency XP.

The migration is non-destructive. Existing learning and capability files are
read only and remain available as compatibility data.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from operator_core.profile.repository import ProfileRepository
from shared.config.paths import OPERATOR_CAPABILITIES

SKILL_TREE_PATH = OPERATOR_CAPABILITIES / "skill_tree.json"
COMPETENCIES_PATH = OPERATOR_CAPABILITIES / "competencies.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def build_legacy_baseline() -> tuple[dict[str, int], int]:
    skill_tree = load_json(SKILL_TREE_PATH)
    stat_names = list(skill_tree.get("stats", {}).keys())
    stat_xp: dict[str, int] = {name: 0 for name in stat_names}

    competencies = load_json(COMPETENCIES_PATH).get("competencies", {})
    if not isinstance(competencies, dict):
        competencies = {}

    total_xp = 0
    for competency_id, payload in competencies.items():
        if not isinstance(payload, dict):
            continue
        xp = max(0, int(payload.get("xp", 0)))
        total_xp += xp
        prefix = str(competency_id).split(".", 1)[0].upper()
        if prefix in stat_xp:
            stat_xp[prefix] += xp

    return stat_xp, total_xp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an already-initialised profile baseline.",
    )
    args = parser.parse_args()

    repository = ProfileRepository()
    repository.initialise()
    current = repository.load_progression()
    already_initialised = bool(current.get("migration")) or int(current.get("total_xp", 0)) > 0
    if already_initialised and not args.force:
        print("Profile already contains progression data. No changes made.")
        print("Use --force only after reviewing the current profile files.")
        return

    stat_xp, total_xp = build_legacy_baseline()
    repository.replace_baseline(
        stat_xp=stat_xp,
        total_xp=total_xp,
        migration_source=str(COMPETENCIES_PATH.relative_to(REPO_ROOT)),
    )
    print("Canonical Operator profile created.")
    print(f"Imported total XP: {total_xp}")
    print("Main-stat baseline:")
    for name, xp in stat_xp.items():
        print(f"  {name}: {xp}")
    print(f"Destination: {repository.data_root}")
    print("Legacy files were not deleted or modified.")


if __name__ == "__main__":
    main()

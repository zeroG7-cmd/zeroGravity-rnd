"""Repository-wide architecture and engine smoke test."""
from __future__ import annotations
import compileall
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.config.paths import (
    LAB_DB,
    LEARNING_TRACKS,
    OPERATOR_CAPABILITIES,
    SHADOW_ROOT,
    ensure_runtime_directories,
)
from lab.engine.database import initialize_database
from journal.engine.service import rebuild_index
from shared.services.operator_status import get_operator_status

LEGACY_ROOTS = (
    "ai", "cad", "cv", "data", "database",
    "experiments", "experiments_archive", "sensors", "urdf",
)

def main() -> int:
    ensure_runtime_directories()
    initialize_database()
    rebuild_index()

    checks = {
        "repo_root": REPO_ROOT.exists(),
        "lab_database": LAB_DB.exists(),
        "operator_capabilities": (
            OPERATOR_CAPABILITIES / "competencies.json"
        ).exists(),
        "learning_tracks": LEARNING_TRACKS.exists(),
        "shadow_project": SHADOW_ROOT.exists(),
        "python_compile": compileall.compile_dir(
            str(REPO_ROOT),
            quiet=1,
            rx=re.compile(r"learning[\\/]resources"),
        ),
    }
    legacy = {
        name: (
            (REPO_ROOT / name).exists()
            and any((REPO_ROOT / name).iterdir())
        )
        for name in LEGACY_ROOTS
    }
    payload = {
        "checks": checks,
        "operator": get_operator_status(),
        "legacy_nonempty_roots": legacy,
    }
    print(json.dumps(payload, indent=2))
    return 0 if all(checks.values()) and not any(legacy.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())

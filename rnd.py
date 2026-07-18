"""Unified command line entry point for zeroGravity R&D."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys

from shared.config.paths import REPO_ROOT, ensure_runtime_directories
from lab.engine.database import initialize_database
from lab.engine.service import counts
from journal.engine.service import rebuild_index
from shared.services.operator_status import get_operator_status

def main() -> int:
    parser = argparse.ArgumentParser(description="zeroGravity R&D platform")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init")
    subcommands.add_parser("status")
    subcommands.add_parser("verify")
    args = parser.parse_args()

    if args.command == "init":
        ensure_runtime_directories()
        initialize_database()
        entries = rebuild_index()
        print(
            "R&D runtime initialized. "
            f"Journal entries indexed: {len(entries)}"
        )
        return 0

    if args.command == "status":
        initialize_database()
        print(
            json.dumps(
                {
                    "repository": str(REPO_ROOT),
                    "lab": counts(),
                    "operator": get_operator_status(),
                    "journal_entries": len(rebuild_index()),
                },
                indent=2,
            )
        )
        return 0

    return subprocess.call(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify_repository.py")],
        cwd=REPO_ROOT,
    )

if __name__ == "__main__":
    raise SystemExit(main())

"""CLI for recording Shadow R&D tests in the shared Lab engine."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.engine.database import initialize_database
from lab.engine.service import log_test
from shared.config.paths import LAB_DB

def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow R&D data pipeline")
    parser.add_argument("--source", choices=("simulation", "hardware"))
    parser.add_argument("--test-name")
    parser.add_argument("--component", default="")
    parser.add_argument("--result", default="pending")
    parser.add_argument("--notes", default="")
    parser.add_argument("--init-only", action="store_true")
    args = parser.parse_args()

    initialize_database()
    if args.init_only:
        print(f"Database ready: {LAB_DB}")
        return 0

    source = args.source or input(
        "Please enter source (simulation/hardware): "
    ).strip().lower()
    if source not in {"simulation", "hardware"}:
        parser.error("source must be simulation or hardware")

    test_name = args.test_name or input("Test name: ").strip()
    component = args.component or input("Component: ").strip()
    result = args.result
    if args.test_name is None:
        result = input("Result (pass/fail/pending): ").strip() or "pending"
    notes = args.notes if args.test_name is not None else input("Notes: ").strip()

    log_test(test_name, component, result, notes, source)
    print(f"Test logged successfully to {LAB_DB}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

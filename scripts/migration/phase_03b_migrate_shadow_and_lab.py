from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = (
    REPO_ROOT
    / "reports"
    / "migration"
    / "phase_03_shadow_inventory.json"
)
DEFAULT_REPORT = (
    REPO_ROOT
    / "reports"
    / "migration"
    / "phase_03b_migration_report.json"
)


@dataclass(frozen=True)
class MovePlan:
    source: Path
    destination: Path
    confidence: str
    reason: str


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def ensure_git_repository() -> None:
    result = run_git("rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise RuntimeError("This script must be run inside a Git repository.")

    detected_root = Path(result.stdout.strip()).resolve()
    if detected_root != REPO_ROOT.resolve():
        raise RuntimeError(
            f"Repository root mismatch.\n"
            f"Script expects: {REPO_ROOT}\n"
            f"Git reports:    {detected_root}"
        )


def ensure_clean_worktree() -> None:
    result = run_git("status", "--porcelain")
    if result.stdout.strip():
        print("Uncommitted changes were found:\n")
        print(result.stdout.rstrip())
        raise RuntimeError(
            "Commit or stash current changes before applying Phase 3B."
        )


def load_inventory(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Inventory not found: {path}")

    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Inventory JSON must contain a top-level list.")

    return data


def destination_for(entry: dict[str, Any]) -> Path | None:
    proposed = str(entry.get("proposed_destination", "")).strip()
    if not proposed:
        raise ValueError(f"Missing proposed_destination: {entry}")

    if proposed.upper().startswith("REVIEW:"):
        return None

    source_path = Path(str(entry["source_path"]))
    source_root = Path(str(entry["source_root"]))

    try:
        relative_within_root = source_path.relative_to(source_root)
    except ValueError as exc:
        raise ValueError(
            f"Source path '{source_path}' is not under source root "
            f"'{source_root}'."
        ) from exc

    proposed_path = Path(proposed)

    # Most audit destinations are directories. A destination with a file
    # suffix is treated as an explicit file path, such as:
    # lab/database/zerogravity_rnd.db
    if proposed_path.suffix:
        destination_relative = proposed_path
    else:
        destination_relative = proposed_path / relative_within_root

    return REPO_ROOT / destination_relative


def build_plans(
    inventory: list[dict[str, Any]],
) -> tuple[list[MovePlan], list[dict[str, Any]]]:
    plans: list[MovePlan] = []
    review_entries: list[dict[str, Any]] = []
    seen_destinations: dict[Path, Path] = {}

    for entry in inventory:
        source_relative = Path(str(entry["source_path"]))
        source = REPO_ROOT / source_relative
        destination = destination_for(entry)

        if destination is None:
            review_entries.append(entry)
            continue

        source_resolved = source.resolve(strict=False)
        destination_resolved = destination.resolve(strict=False)

        if source_resolved == destination_resolved:
            continue

        previous_source = seen_destinations.get(destination_resolved)
        if previous_source is not None and previous_source != source_resolved:
            raise RuntimeError(
                "Destination collision detected:\n"
                f"  {previous_source}\n"
                f"  {source_resolved}\n"
                f"both map to:\n"
                f"  {destination_resolved}"
            )

        seen_destinations[destination_resolved] = source_resolved

        plans.append(
            MovePlan(
                source=source,
                destination=destination,
                confidence=str(entry.get("confidence", "")),
                reason=str(entry.get("reason", "")),
            )
        )

    return plans, review_entries


def validate_plans(plans: list[MovePlan]) -> None:
    errors: list[str] = []

    for plan in plans:
        if not plan.source.exists():
            errors.append(f"Missing source: {plan.source.relative_to(REPO_ROOT)}")

        if plan.destination.exists():
            errors.append(
                f"Destination already exists: "
                f"{plan.destination.relative_to(REPO_ROOT)}"
            )

    if errors:
        preview = "\n".join(f"  - {error}" for error in errors[:25])
        more = ""
        if len(errors) > 25:
            more = f"\n  ...and {len(errors) - 25} more."
        raise RuntimeError(f"Migration validation failed:\n{preview}{more}")


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def print_summary(
    plans: list[MovePlan],
    review_entries: list[dict[str, Any]],
    apply: bool,
) -> None:
    mode = "APPLY" if apply else "PREVIEW"
    print(f"\nPhase 3B migration mode: {mode}")
    print(f"Approved moves: {len(plans)}")
    print(f"Review entries skipped: {len(review_entries)}\n")

    for plan in plans:
        print(f"  {relative(plan.source)}")
        print(f"    -> {relative(plan.destination)}")

    if review_entries:
        print("\nSkipped REVIEW entries:")
        for entry in review_entries:
            print(
                f"  {entry['source_path']} "
                f"({entry['proposed_destination']})"
            )


def apply_moves(plans: list[MovePlan]) -> list[dict[str, str]]:
    completed: list[dict[str, str]] = []

    for index, plan in enumerate(plans, start=1):
        plan.destination.parent.mkdir(parents=True, exist_ok=True)

        source_relative = relative(plan.source)
        destination_relative = relative(plan.destination)

        print(
            f"[{index}/{len(plans)}] "
            f"{source_relative} -> {destination_relative}"
        )

        result = run_git(
            "mv",
            "--",
            source_relative,
            destination_relative,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"git mv failed for {source_relative}\n"
                f"{result.stderr.strip()}"
            )

        completed.append(
            {
                "source": source_relative,
                "destination": destination_relative,
                "confidence": plan.confidence,
                "reason": plan.reason,
            }
        )

    return completed


def write_report(
    report_path: Path,
    completed: list[dict[str, str]],
    review_entries: list[dict[str, Any]],
    mode: str,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "mode": mode,
        "moves": completed,
        "review_entries_skipped": review_entries,
    }

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 3B: migrate approved Shadow and Lab files from the "
            "Phase 3A inventory."
        )
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help="Path to the Phase 3A inventory JSON.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Path for the Phase 3B migration report.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the moves. Without this flag, only preview them.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        ensure_git_repository()

        inventory_path = args.inventory
        if not inventory_path.is_absolute():
            inventory_path = REPO_ROOT / inventory_path

        report_path = args.report
        if not report_path.is_absolute():
            report_path = REPO_ROOT / report_path

        inventory = load_inventory(inventory_path)
        plans, review_entries = build_plans(inventory)
        validate_plans(plans)
        print_summary(plans, review_entries, args.apply)

        if not args.apply:
            print(
                "\nPreview complete. No files were moved.\n"
                "Run again with --apply after checking the proposed paths."
            )
            return 0

        ensure_clean_worktree()
        completed = apply_moves(plans)
        write_report(
            report_path=report_path,
            completed=completed,
            review_entries=review_entries,
            mode="applied",
        )

        print("\nPhase 3B migration completed.")
        print(f"Files moved: {len(completed)}")
        print(f"Review entries left untouched: {len(review_entries)}")
        print(f"Migration report: {report_path}")
        print("\nReview the changes with: git status")
        return 0

    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path

from journal.engine.models import JournalEntryRequest, JournalEvidence, normalise_string_list
from journal.engine.service import JournalService


def csv_values(raw: str) -> tuple[str, ...]:
    return normalise_string_list(raw.split(",") if raw else ())


def parse_target(raw: str) -> dict[str, object]:
    """Parse TARGET_TYPE:TARGET_ID:WEIGHT."""
    parts = raw.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("target must be TYPE:ID:WEIGHT")
    target_type, target_id, weight = parts
    try:
        numeric_weight = float(weight)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("target weight must be numeric") from exc
    return {"target_type": target_type, "target_id": target_id, "weight": numeric_weight}


def parse_evidence(raw: str) -> JournalEvidence:
    """Parse TYPE:REFERENCE[:LABEL]."""
    parts = raw.split(":", 2)
    if len(parts) < 2:
        raise argparse.ArgumentTypeError("evidence must be TYPE:REFERENCE[:LABEL]")
    return JournalEvidence(parts[0], parts[1], parts[2] if len(parts) == 3 else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="zeroGravity Universal Journal Engine")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("create", help="Create a Markdown entry and JSON manifest")
    create.add_argument("title")
    create.add_argument("--body", default="")
    create.add_argument("--body-file", type=Path)
    create.add_argument("--types", default="reflection")
    create.add_argument("--tags", default="")
    create.add_argument("--projects", default="")
    create.add_argument("--domains", default="")
    create.add_argument("--concepts", default="")
    create.add_argument("--capabilities", default="")
    create.add_argument("--base-xp", type=int, default=0)
    create.add_argument("--target", action="append", type=parse_target, default=[])
    create.add_argument("--evidence", action="append", type=parse_evidence, default=[])

    subcommands.add_parser("index", help="Rebuild the journal index")
    subcommands.add_parser("list", help="List indexed journal entries")

    args = parser.parse_args()
    service = JournalService()

    if args.command == "create":
        body = args.body_file.read_text(encoding="utf-8") if args.body_file else args.body
        manifest = service.create(
            JournalEntryRequest(
                title=args.title,
                body=body,
                entry_types=csv_values(args.types),
                tags=csv_values(args.tags),
                projects=csv_values(args.projects),
                domains=csv_values(args.domains),
                concepts=csv_values(args.concepts),
                capabilities=csv_values(args.capabilities),
                base_xp=args.base_xp,
                xp_targets=tuple(args.target),
                evidence=tuple(args.evidence),
            )
        )
        print(json.dumps(manifest.to_dict(), indent=2))
    elif args.command == "index":
        print(f"Indexed {len(service.rebuild_index())} journal entries.")
    else:
        print(json.dumps(service.list_entries(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

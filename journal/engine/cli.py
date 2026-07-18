from __future__ import annotations
import argparse
import json
from .service import create_entry, list_entries, rebuild_index

def main() -> int:
    parser = argparse.ArgumentParser(description="zeroGravity Journal Engine")
    subcommands = parser.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser("create")
    create.add_argument("title")
    create.add_argument("--body", default="")
    create.add_argument("--tags", default="")
    subcommands.add_parser("index")
    subcommands.add_parser("list")
    args = parser.parse_args()

    if args.command == "create":
        tags = [item.strip() for item in args.tags.split(",") if item.strip()]
        print(create_entry(args.title, args.body, tags))
    elif args.command == "index":
        print(f"Indexed {len(rebuild_index())} journal entries.")
    else:
        print(json.dumps(list_entries(), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

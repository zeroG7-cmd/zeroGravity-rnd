from __future__ import annotations
import argparse
import json
from shared.config.paths import LAB_DB
from .database import initialize_database
from .service import counts, create_experiment, list_experiments

def main() -> int:
    parser = argparse.ArgumentParser(description="zeroGravity Lab Engine")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init")
    subcommands.add_parser("status")
    subcommands.add_parser("list")
    create = subcommands.add_parser("create")
    create.add_argument("experiment_id")
    create.add_argument("title")
    create.add_argument("--project", default="shadow")
    create.add_argument("--domain", default="")
    args = parser.parse_args()

    if args.command == "init":
        initialize_database()
        print(f"Lab database ready: {LAB_DB}")
    elif args.command == "status":
        print(json.dumps({"database": str(LAB_DB), "counts": counts()}, indent=2))
    elif args.command == "list":
        print(json.dumps(list_experiments(), indent=2))
    elif args.command == "create":
        create_experiment(
            args.experiment_id,
            args.title,
            args.project,
            args.domain,
        )
        print(f"Created experiment {args.experiment_id}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

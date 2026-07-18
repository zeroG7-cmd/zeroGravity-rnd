from __future__ import annotations
import argparse, json
from pathlib import Path
from service import create_execution, execution_summary, list_executions

def main():
 p=argparse.ArgumentParser(description="Operator execution engine")
 sub=p.add_subparsers(dest="command", required=True)
 add=sub.add_parser("add"); add.add_argument("json_file", type=Path)
 ls=sub.add_parser("list"); ls.add_argument("--limit", type=int, default=20)
 sub.add_parser("summary")
 a=p.parse_args()
 if a.command=="add": print(json.dumps(create_execution(json.loads(a.json_file.read_text(encoding="utf-8"))),indent=2))
 elif a.command=="list": print(json.dumps(list_executions(a.limit),indent=2))
 else: print(json.dumps(execution_summary(),indent=2))
if __name__=="__main__": main()

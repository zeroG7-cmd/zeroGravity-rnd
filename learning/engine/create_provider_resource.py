"""Create a universal provider resource scaffold.

This generates data files only. The existing manifest importer performs the
actual track import.
"""
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path("learning")
REGISTRY=ROOT/"config"/"provider_registry.json"
RESOURCES=ROOT/"resources"

def slug(v): return re.sub(r"[^a-z0-9]+","_",str(v).lower()).strip("_")
def load(p,d=None): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
def save(p,d): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,indent=4,ensure_ascii=False)+"\n",encoding="utf-8")

def main():
 ap=argparse.ArgumentParser(description="Create a provider course scaffold.")
 ap.add_argument("provider")
 ap.add_argument("title")
 ap.add_argument("--resource-id")
 ap.add_argument("--source-url",default="")
 ap.add_argument("--stat",default="INT")
 ap.add_argument("--hierarchy",nargs="+",required=True)
 ap.add_argument("--total-units",type=int,default=0)
 a=ap.parse_args()
 reg=load(REGISTRY,{"providers":{}}).get("providers",{})
 key=slug(a.provider)
 if key not in reg: raise SystemExit(f"Unknown provider: {a.provider}. Registered: {', '.join(sorted(reg))}")
 rid=a.resource_id or f"{key}_{slug(a.title)}"
 folder=RESOURCES/key/slug(a.title)
 manifest={
  "schema_version":3,
  "resource":{"id":rid,"title":a.title,"provider":reg[key]["name"],"source_url":a.source_url},
  "operator_mapping":{"stat":a.stat,"hierarchy":a.hierarchy},
  "course":{"difficulty":"Beginner","sections":[{"number":1,"title":"Course Content","concept_awards":[],"mapping_confidence":"low","lectures":[{"id":"unit_001","title":"Replace with first unit","source_type":"manual"}]}]}
 }
 snapshot={
  "schema_version":1,"provider":reg[key]["name"],"resource_id":rid,
  "captured_at":datetime.now(timezone.utc).isoformat(),
  "progress":{"completed_units":0,"total_units":a.total_units},
  "notes":"Update progress after importing course_manifest.json."
 }
 save(folder/"course_manifest.json",manifest); save(folder/"progress_snapshot.json",snapshot)
 print(folder)
 print("Created course_manifest.json and progress_snapshot.json")
if __name__=="__main__": main()

"""Backfill concept XP for units completed before Manifest v3.

This never awards operator/capability XP. It only mirrors already-earned track
XP into the concept graph and keeps a ledger so each unit is processed once.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from concepts import distribute_concept_xp, resolve_concept_awards, update_concept_progress
from xp import calculate_unit_xp

TRACKS_ROOT=Path('learning/tracks')
LEDGER_PATH=Path('operator_core/hubs/learning/progress/concept_backfill.json')

def load(path:Path, default:Any):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))
def save(path:Path,data:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    t=path.with_suffix(path.suffix+'.tmp'); t.write_text(json.dumps(data,indent=4)+"\n",encoding='utf-8'); t.replace(path)

def main():
    ap=argparse.ArgumentParser(description='Backfill concept XP from existing completed learning units.')
    ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    ledger=load(LEDGER_PATH,{'schema_version':1,'processed':[]}); processed=set(ledger.get('processed',[]))
    pending=[]; xp=0
    for mp in TRACKS_ROOT.rglob('metadata.json'):
        pp=mp.parent/'progress.json'
        if not pp.exists(): continue
        metadata=load(mp,{}); progress=load(pp,{})
        complete={str(x) for x in progress.get('completed_units',[])}
        for unit in metadata.get('units',[]):
            if str(unit.get('id')) not in complete: continue
            key=f"{metadata.get('id',mp.parent.name)}::{unit.get('id')}"
            if key in processed: continue
            resolved=resolve_concept_awards(metadata,unit)
            dist=distribute_concept_xp(calculate_unit_xp(metadata,unit),resolved['concept_awards'])
            if not dist: continue
            pending.append((key,resolved,dist)); xp += sum(int(a['xp']) for a in dist)
    print(f'Concept backfill units : {len(pending)}')
    print(f'Concept XP mirrored    : {xp}')
    if args.dry_run:
        print('DRY RUN: no files changed.'); return
    for key,resolved,dist in pending:
        update_concept_progress(resolved['capability_id'],dist,confidence=resolved['mapping_confidence'],source='historical_backfill')
        ledger.setdefault('processed',[]).append(key)
    save(LEDGER_PATH,ledger)
    print(f'Ledger                 : {LEDGER_PATH}')

if __name__=='__main__': main()



"""Process live provider completion events into Operator Zero XP receipts."""
from __future__ import annotations
import argparse, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
ENGINE=Path(__file__).resolve().parent
if str(ENGINE) not in sys.path: sys.path.insert(0,str(ENGINE))
from concepts import distribute_concept_xp, resolve_concept_awards, update_concept_progress
from history import record_completion
from stats import update_operator_competencies
from xp import calculate_unit_xp, distribute_xp, resolve_competency_awards
ROOT=Path('learning'); TRACKS=ROOT/'tracks'; LEDGER=Path('operator_core/events/provider_events.json'); RECEIPTS=Path('operator_core/events/receipts')
def load(p,d=None): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
def save(p,d): p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(d,indent=4,ensure_ascii=False)+'\n',encoding='utf-8'); t.replace(p)
def norm(v): return str(v or '').strip().lower()
def slug(v): return re.sub(r'[^a-z0-9]+','_',norm(v)).strip('_')
def find_track(e):
 provider=norm(e.get('provider')); rid=norm(e.get('resource_id') or e.get('course_id')); hits=[]
 for mp in TRACKS.rglob('metadata.json'):
  m=load(mp,{}) ; ids={norm(m.get('id')),norm(m.get('resource_id')),norm(m.get('external_resource_id'))}
  if provider and norm(m.get('provider'))!=provider: continue
  if rid and rid not in ids: continue
  hits.append((mp.parent,m,mp))
 if len(hits)!=1: raise ValueError(f"No unique matching track for provider/resource ({e.get('provider')} / {e.get('resource_id')}). Run setup_bootdev.py first.")
 return hits[0]
def existing_unit(m,e):
 units=m.get('units',[]); uid=norm(e.get('unit_id') or e.get('lesson_id')); url=norm(e.get('url')); title=norm(e.get('title'))
 for i,u in enumerate(units):
  vals={norm(u.get('id')),norm(u.get('external_id')),norm(u.get('lesson_id')),norm(u.get('source_url'))}
  if uid and uid in vals:return i,u
  if url and url in vals:return i,u
 if title:
  match=[(i,u) for i,u in enumerate(units) if norm(u.get('title'))==title]
  if len(match)==1:return match[0]
 return None
def make_dynamic_unit(m,e):
 if not m.get('dynamic_provider_units'): raise ValueError('Event unit could not be matched. Add external_id/source_url to the course manifest.')
 sec=int(e.get('section_number') or 0); num=int(e.get('unit_number') or 0); chapter=str(e.get('section_title') or e.get('chapter_title') or f'Chapter {sec}').strip(); title=str(e.get('lesson_title') or e.get('title') or 'Boot.dev lesson').strip(); url=str(e.get('url') or '').strip()
 if not sec or not num: raise ValueError('Dynamic Boot.dev events require section_number and unit_number. Reload the updated extension on a lesson page.')
 uid=f"section_{sec:02}_unit_{num:03}_{slug(title)[:48]}"; unit={'id':uid,'title':title,'section_number':sec,'section_title':chapter,'unit_number':num,'source_type':'exercise','source_url':url,'external_id':url or uid,'provider_unit_id':e.get('unit_id'),'mapping_confidence':'medium','xp_value':int(e.get('xp_value') or m.get('xp_rules',{}).get('exercise',20))}
 m.setdefault('units',[]).append(unit); return len(m['units'])-1,unit
def process(e,dry=False):
 eid=str(e.get('event_id') or '').strip()
 if not eid: raise ValueError('event_id is required')
 ledger=load(LEDGER,{'schema_version':2,'processed':{}})
 if eid in ledger['processed']: return {'status':'duplicate','event_id':eid,'receipt':ledger['processed'][eid]}
 track,m,mp=find_track(e); prog=load(track/'progress.json',{}); prog.setdefault('completed_units',[]); prog.setdefault('total_xp',0); prog.setdefault('external_completed_units',0); prog.setdefault('status','In Progress')
 found=existing_unit(m,e); created=False
 if found is None: found=make_dynamic_unit(m,e); created=True
 idx,u=found; uid=u['id']
 if uid in prog['completed_units']: return {'status':'already_completed','event_id':eid,'unit_id':uid}
 total=calculate_unit_xp(m,u); dist=distribute_xp(total,resolve_competency_awards(m,u)); cr=resolve_concept_awards(m,u); cdist=distribute_concept_xp(total,cr['concept_awards'])
 receipt={'event_id':eid,'status':'preview' if dry else 'completed','provider':e.get('provider'),'track':m.get('title'),'resource_id':m.get('resource_id'),'unit_id':uid,'unit_title':u.get('title'),'chapter':u.get('section_title'),'xp':total,'competency_distribution':dist,'concept_distribution':cdist,'mapping_confidence':cr['mapping_confidence'],'processed_at':datetime.now(timezone.utc).isoformat(),'next_unit':None,'verification':e.get('verification','provider_bridge')}
 if dry:return receipt
 if created: save(mp,m)
 prog['completed_units'].append(uid)
 prog['total_xp'] += total
 prog['external_completed_units'] = len(prog['completed_units'])
 prog['current_unit_index'] = prog['external_completed_units']
 ext_total = int(prog.get('external_total_units') or m.get('external_total_units') or 0)
 prog['status'] = 'Complete' if ext_total and prog['external_completed_units'] >= ext_total else 'In Progress'
 stats=update_operator_competencies(dist); receipt['operator_total_xp']=stats['total_xp']; receipt['operator_level']=stats['level']
 if cdist:update_concept_progress(cr['capability_id'],cdist,confidence=cr['mapping_confidence'],source='provider_event')
 record_completion(m,u,total,dist,cdist,cr['mapping_confidence'],'provider_event')
 save(track/'progress.json',prog); RECEIPTS.mkdir(parents=True,exist_ok=True); rp=RECEIPTS/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+slug(eid)[:80]+'.json'); save(rp,receipt); ledger['processed'][eid]=receipt; save(LEDGER,ledger); return receipt

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('event'); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args(); print(json.dumps(process(load(Path(a.event)),a.dry_run),indent=2))
if __name__=='__main__':main()



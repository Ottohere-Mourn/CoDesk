"""Read-only summary of this takeover's explicitly listed scripted runs."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
NAMES=[
 'cdd-scripted-shared-20261026T142900Z',
 'cdd-scripted-shared-20261026T143800Z',
 'cdd-scripted-shared-20261026T145900Z',
 'cdd-scripted-isolated-20261026T145800Z',
 'cdd-scripted-shared-20261026T150700Z',
 'cdd-scripted-isolated-20261026T150700Z',
 'cdd-scripted-shared-20261026T151600Z',
 'cdd-scripted-isolated-20261026T151600Z',
]
def obj(p,default=None):return json.loads(p.read_text()) if p.exists() else ({} if default is None else default)
def rows(p):return [json.loads(l) for l in p.read_text().splitlines() if l] if p.exists() else []
summary=[]
for name in NAMES:
 p=REPO/'runs'/name;meta=obj(p/'provenance.json');result=obj(p/'result.json');failure=obj(p/'failure.json');oracle=obj(p/'oracle.json') or obj(p/'diagnostic_oracle.json');actors=rows(p/'actors.jsonl');events=rows(p/'gui_events.jsonl');q=rows(p/'qemu_process_resources.jsonl');messages=rows(p/'collaboration/events.jsonl');sync=rows(p/'workspace_versions/events.jsonl')
 oracle=oracle.get('oracle',oracle)
 starts=[v['timestamp'] for v in events if v.get('event_type')=='action_start' and v.get('actor') in ['A','B']]
 processes={}
 for row in q:
  if 'cpu_seconds' not in row:continue
  v=processes.setdefault(row['container_id'],{'cpu_first':row['cpu_seconds'],'cpu_last':row['cpu_seconds'],'rss_peak_bytes':0})
  v['cpu_last']=max(v['cpu_last'],row['cpu_seconds']);v['rss_peak_bytes']=max(v['rss_peak_bytes'],row['rss_bytes'])
 artifacts={str(f.relative_to(p)):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in (p/'artifacts').rglob('*') if f.is_file()}
 summary.append({'run_id':name,'condition':meta.get('condition'),'model_called':False,'kind':'sequential scripted GUI smoke; never a model comparison','status':failure.get('status') or result.get('status') or 'RUNNING','error':failure.get('error') or failure.get('reason'),'setup_to_first_gui_action_s':round(min(starts)-meta['started_at'],2) if starts and meta.get('started_at') else None,'scripted_actor_elapsed_sum_s':round(sum(a['elapsed_s'] for a in actors),2),'elapsed_including_reset_s':result.get('elapsed_s'),'oracle_roles':{k:v['success'] for k,v in oracle.get('actors',{}).items()},'oracle_joint':oracle.get('joint_success'),'oracle_protection':oracle.get('protection_success'),'gui_reopen_evidence':obj(p/'reopen_evidence.json',[]),'messages':sum(x['type']=='message' for x in messages),'attachments':sum(x['type']=='attachment' for x in messages),'verified_transfers':sum(x.get('event')=='transfer_verified' for x in sync),'revisions':sum(x.get('event')=='revision_saved' for x in sync),'sync_errors':sum(x.get('event')=='sync_error' for x in sync),'cpu_seconds_sampled_lower_bound':round(sum(v['cpu_last']-v['cpu_first'] for v in processes.values()),2),'qemu_processes':processes,'png_count':len(list(p.rglob('*.png'))),'artifacts':artifacts,'reset_guests':len(result.get('reset',[]))})
(HERE/'smoke_summary.json').write_text(json.dumps({'scope':'scripted infrastructure diagnostics only','screenshot_latency':'not separately measured in legacy scripted harness; do not infer it from action duration','model_active_overlap':None,'runs':summary},indent=2)+'\n')
for s in summary:print(s['run_id'],s['status'],s['oracle_roles'],s['verified_transfers'])

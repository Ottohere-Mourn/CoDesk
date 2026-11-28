"""Read-only export of selected 48-episode evidence and source snapshots to RAID."""
from pathlib import Path
import hashlib,importlib.util,json,re,sys,tarfile
sys.dont_write_bytecode=True
BASE=Path('/mnt/raid1/mjh/codesk-runs')
BC=BASE/'bc-shared-v1-20261127'
ROOT=BASE/'c-bc48-publication-20261128'
OUT=ROOT/'related'
sys.path.insert(0,str(BC))
from pipeline.redact_codex_events import redact_value
from pipeline.scan_sensitive import _RULES,_PROXY_ASSIGNMENT
spec=importlib.util.spec_from_file_location('dashboard_export',BC/'contract-repair-20261128/dashboard_delta_collect.py')
export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)
STATS={'events_processed':0,'base64_payloads_redacted':0,'base64_chars_omitted':0,'sensitive_replacements':0,'files':0}
ALLOWED={'.py','.md','.json','.jsonl','.yaml','.yml','.csv','.txt','.js','.html','.css','.svg','.png','.jpg','.pdf','.xlsx','.pptx','.odt','.ods','.odp','.ora','.zip','.sha256','.toml','.sh'}
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def clean(v):
 v=export.clean(v)
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
 if isinstance(v,list):return [clean(x) for x in v]
 if isinstance(v,str):
  for _,pat in _RULES:
   v,n=pat.subn('[REDACTED]',v);STATS['sensitive_replacements']+=n
  v,n=_PROXY_ASSIGNMENT.subn('[PROXY_ASSIGNMENT_REDACTED]',v);STATS['sensitive_replacements']+=n
 return v
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(v),ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8');STATS['files']+=1
def textcopy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if src.suffix.lower() in {'.png','.jpg','.pdf','.xlsx','.pptx','.odt','.ods','.odp','.ora','.zip'}:
  dst.write_bytes(src.read_bytes())
 else:dst.write_text(clean(src.read_text(encoding='utf-8')),encoding='utf-8')
 STATS['files']+=1
def copy_sources(src,dst):
 copied=[]
 for f in sorted(src.rglob('*')):
  if not f.is_file() or '__pycache__' in f.parts or f.suffix.lower() not in ALLOWED:continue
  if f.stat().st_size>20*2**20:continue
  textcopy(f,dst/f.relative_to(src));copied.append({'source':str(f),'export_path':str((dst/f.relative_to(src)).relative_to(OUT)),'source_sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 return copied
def event_export(src,dst):
 stats={'events_processed':0,'payloads_redacted':0,'base64_chars_omitted':0,'non_json_lines_omitted':0}
 dst.parent.mkdir(parents=True,exist_ok=True)
 with src.open(encoding='utf-8') as fi,dst.open('w',encoding='utf-8') as fo:
  for line in fi:
   if not line.strip():continue
   try:v=json.loads(line)
   except json.JSONDecodeError:stats['non_json_lines_omitted']+=1;continue
   v=redact_value(v,stats=stats);fo.write(json.dumps(clean(v),ensure_ascii=False,separators=(',',':'))+'\n');stats['events_processed']+=1
 STATS['events_processed']+=stats['events_processed'];STATS['base64_payloads_redacted']+=stats['payloads_redacted'];STATS['base64_chars_omitted']+=stats['base64_chars_omitted'];STATS['files']+=1
 return stats
def first(paths):return next((p for p in paths if p.is_file()),None)
def main():
 assert not OUT.exists(),'No overwrite'
 snap=read(ROOT/'selected-snapshot.json');assert len(snap['cases'])==48
 ledger=[]
 for c in snap['cases']:
  cid=c['id'];run=Path(c['sourceRun']);assert str(run).startswith(str(BASE))
  report=read(run/'report.json') if (run/'report.json').is_file() else {}
  roots=export.source_roots(run,report)
  resultfile=first([p/'result.json' for p in roots]+[run/'provenance/formal-result.json'])
  result=read(resultfile) if resultfile else {}
  d=OUT/'trajectories'/cid
  write(d/'selection.json',c)
  if result:write(d/'formal-result.json',result)
  if report:write(d/'report.json',report)
  if c.get('grade'):write(d/'grade.json',c['grade'])
  if c.get('legacyScores'):write(d/'legacy-scores.json',c['legacyScores'])
  if cid=='CONC-08':write(d/'terminal-outcome.json',{'state':c['status'],'reason':c['failureReason'],'scores':None,'no_rerun':True})
  evidence={'case_id':cid,'source_roots':[str(p) for p in roots],'actors':{},'source_files':[]}
  for name in ['shared_timeline.json','snapshot-receipt.json','blind-path-audit.json','offline-recovery-provenance.json','oracle-artifact-grade.json']:
   f=first([p/name for p in roots])
   if f:write(d/name,read(f))
  for role,folder in [('A','actor_a'),('B','actor_b')]:
   actor_paths=[p/s for p in roots for s in [folder,'agent'+role]]
   action=first([p/'actions.jsonl' for p in actor_paths]);assert action,(cid,role)
   target=d/folder;event_export(action,target/'actions.jsonl')
   # Prefer the existing normalized archive; use captured raw events or JSON stdout only when needed.
   candidates=[p/'codex_events.jsonl' for p in actor_paths]
   candidates += [p/f'backend-capture/actor-{role}-codex-events.jsonl' for p in roots]
   candidates += [p/'stdout.log' for p in actor_paths]
   events=first(candidates)
   rec={'actions_source':str(action),'steps':sum(bool(x.strip()) for x in action.read_text().splitlines()),'codex_events_available':bool(events),'permission_audit_available':False}
   assert rec['steps']==c['steps'][role],(cid,role,rec['steps'],c['steps'])
   if events:rec.update(codex_events_source=str(events),redaction=event_export(events,target/'codex_events.jsonl'))
   perm=first([p/'permission-audit-verified.json' for p in actor_paths])
   if perm:write(target/'permission-audit-verified.json',read(perm));rec['permission_audit_available']=True
   instruction=first([p/'instruction.txt' for p in actor_paths])
   if instruction:textcopy(instruction,target/'instruction.txt')
   abstain=first([p/'INFEASIBLE' for p in actor_paths])
   if abstain:textcopy(abstain,target/'INFEASIBLE.txt')
   evidence['actors'][role]=rec
  if cid.startswith('BC-'):
   evidence['source_files']=copy_sources(BC/'cases'/cid,OUT/'sources/cases'/cid)
  else:
   for task in result.get('tasks',[]):
    f=Path(task)
    if not f.is_file():continue
    taskroot=f.parent.parent
    source_dst=OUT/'sources/cases'/cid
    if not source_dst.exists():evidence['source_files']+=copy_sources(taskroot,source_dst)
    runnerroot=next((p for p in f.parents if (p/'evaluation_examples/task_class').is_dir()),None)
    if runnerroot:
     for bridge in sorted((runnerroot/'evaluation_examples/task_class').glob('pg_conc*.py')):
      target=source_dst/'evaluation_examples/task_class'/bridge.name
      if not target.exists():textcopy(bridge,target)
     # Include the actual per-run imported local game/setup source directories only.
     for game in (runnerroot/'games').iterdir() if (runnerroot/'games').is_dir() else []:
      if game.is_dir():copy_sources(game,source_dst/'games'/game.name)
  write(d/'archive-availability.json',evidence);ledger.append(evidence)
 # Pipeline source is an independent source snapshot, never applied to production here.
 copy_sources(BC/'pipeline',OUT/'sources/pipeline')
 write(OUT/'archive-availability.json',{'cases':ledger,'note':'Missing original evidence is reported, never synthesized. Images are in the static dashboard assets.'})
 write(OUT/'export-summary.json',STATS)
 fs=[p for p in OUT.rglob('*') if p.is_file()]
 print(json.dumps({'files':len(fs),'bytes':sum(p.stat().st_size for p in fs),'stats':STATS}))
 with tarfile.open(ROOT/'related.tar.gz','w:gz',compresslevel=3) as t:
  for f in fs:t.add(f,arcname=str(f.relative_to(OUT)))
 print('BUNDLE', (ROOT/'related.tar.gz').stat().st_size)
if __name__=='__main__':main()

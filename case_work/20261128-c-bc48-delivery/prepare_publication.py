"""Assemble a standalone site, selected evidence and source snapshots in a clean clone."""
from pathlib import Path,PurePosixPath
import copy,datetime,hashlib,importlib.util,json,shutil,tarfile
ROOT=Path(__file__).resolve().parent
REPO=ROOT/'repo'
LOCAL_SITE=ROOT.parent/'20261126-open-cli-batch/dashboard'
SITE=REPO/'docs/dashboards/c_bc_48_open_cli_20261128'
TRACE=REPO/'trajectories/c_bc_48_open_cli_20261128'
SOURCE=REPO/'case_work/20261128-c-bc48-delivery'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 assert not SITE.exists() and not TRACE.exists() and not SOURCE.exists()
 snap=read(LOCAL_SITE/'snapshot.json');mf=read(LOCAL_SITE/'manifest.json')
 assert len(snap['cases'])==48
 SITE.mkdir(parents=True)
 files={p.relative_to(LOCAL_SITE).as_posix() for p in LOCAL_SITE.rglob('*') if p.is_file() and 'assets' not in p.relative_to(LOCAL_SITE).parts}
 selected_shots=set()
 for c in snap['cases']:
  if not c.get('traceAvailable'):continue
  for role in ['A','B']:
   for row in read(LOCAL_SITE/f'data/{c["id"]}/actions-{role}.json'):
    rel=(row.get('screenshot_artifact') or {}).get('path')
    if rel:selected_shots.add(f'assets/{c["id"]}/{role}/{rel}')
 files |= selected_shots
 for rel in sorted(files):
  dst=SITE/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(LOCAL_SITE/rel,dst)
 mf['files']=sorted(files);mf['publication_selected_screenshots_only']=True
 write(SITE/'manifest.json',mf)
 with tarfile.open(ROOT/'related.tar.gz') as tar:
  for member in tar.getmembers():
   rel=PurePosixPath(member.name)
   if rel.is_absolute() or '..' in rel.parts or not member.isfile():raise ValueError('Unsafe related archive')
   if rel.parts[0]=='trajectories':dst=TRACE.joinpath(*rel.parts[1:])
   elif rel.parts[0]=='sources':dst=SOURCE.joinpath(*rel.parts[1:])
   else:dst=TRACE/rel.name
   assert not dst.exists(),dst
   dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(tar.extractfile(member).read())
 # Preserve current selected grades/policies exactly, not raw earlier grade selections.
 for c in snap['cases']:
  d=TRACE/c['id'];write(d/'selection.json',c)
  if c.get('grade'):write(d/'grade.json',c['grade'])
  for role in ['A','B']:
   if c.get('traceAvailable'):
    rows=read(SITE/f'data/{c["id"]}/actions-{role}.json')
    p=d/('actor_a' if role=='A' else 'actor_b')/'actions.jsonl'
    # Use normalized screenshot links that resolve into the single static-site image copy.
    normalized=copy.deepcopy(rows)
    for row in normalized:
     art=row.get('screenshot_artifact')
     if art and art.get('path'):art['publication_path']=f'docs/dashboards/c_bc_48_open_cli_20261128/assets/{c["id"]}/{role}/{art["path"]}'
    p.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in normalized),encoding='utf-8')
 # Keep the abstention policy and strict-contract regression evidence, not backup directories/raw screenshots.
 notes=SOURCE/'audit';notes.mkdir()
 for src in [ROOT.parent/'20261128-bc23-abstention/STATUS.md',ROOT.parent/'20261128-bc23-abstention/dashboard-update-verification.json',
  ROOT.parent/'20261128-bc-contract-tightening/STRICT_REGRADE_RESULTS.json',ROOT.parent/'20261128-bc-contract-tightening/STRICT_REGRADE_RESULTS.md',
  ROOT.parent/'20261128-bc-contract-tightening/ORACLE_CHANGES.patch',ROOT.parent/'20261128-bc-contract-tightening/regression-tests.log',
  ROOT.parent/'20261128-bc-contract-tightening/tests-passed.json']:
  shutil.copyfile(src,notes/('BC23_STATUS.md' if src.name=='STATUS.md' else src.name))
 shutil.copytree(ROOT.parent/'20261126-shared-case-pipeline-v1/docs',SOURCE/'design-docs',ignore=shutil.ignore_patterns('__pycache__'))
 for name in ['refresh_final_site.py','export_related_remote.py','prepare_publication.py']:
  shutil.copyfile(ROOT/name,SOURCE/name)
 index={'schema_version':'codesk.c-bc48-delivery/v1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'mode':'shared','tools':'GUI + writable Guest CLI','cases':[]}
 for c in snap['cases']:
  index['cases'].append({'case_id':c['id'],'title':c['title'],'status':c['status'],'valid_result':c['validResult'],
   'run_id':c['runId'],'scores':c.get('scores'),'steps':c['steps'],'joint_pass':c.get('jointPass'),
   'dashboard':'docs/dashboards/c_bc_48_open_cli_20261128/index.html#'+c['id'],
   'source':'case_work/20261128-c-bc48-delivery/cases/'+c['id'],
   'trajectory':'trajectories/c_bc_48_open_cli_20261128/'+c['id'],
   'grade':'trajectories/c_bc_48_open_cli_20261128/'+c['id']+'/grade.json' if c.get('grade') else None})
 write(REPO/'lists/c_bc_48_open_cli_20261128.json',index)
 spec=importlib.util.spec_from_file_location('validator',ROOT.parent/'20261126-shared-case-pipeline-v1/scripts/update_dashboard48.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);counts=mod.validate(SITE)
 f=[p for base in [SITE,TRACE,SOURCE] for p in base.rglob('*') if p.is_file()]
 summary={'cases':48,'valid_results':47,'actor_action_streams':len(list(TRACE.glob('*/actor_*/actions.jsonl'))),
  'codex_event_streams':len(list(TRACE.glob('*/actor_*/codex_events.jsonl'))),
  'permission_audits':len(list(TRACE.glob('*/actor_*/permission-audit-verified.json'))),
  'selected_screenshots':len(selected_shots),'files':len(f),'bytes':sum(p.stat().st_size for p in f),
  'largest_file_bytes':max(p.stat().st_size for p in f),'site_validation':counts,
  'c08':'DEFERRED_NETWORK; 27/61 steps; no valid final score',
  'bc23':'93/10 steps; A1/B0; joint=false; explicit abstention policy; raw artifact-only score retained'}
 assert summary['actor_action_streams']==96 and all((SOURCE/'cases'/c['id']).is_dir() for c in snap['cases'])
 write(ROOT/'publication-summary.json',summary);write(SOURCE/'PUBLICATION_SUMMARY.json',summary)
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

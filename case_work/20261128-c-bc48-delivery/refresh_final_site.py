"""Register C08 terminal failure and select latest BC20/24, without reruns."""
from pathlib import Path,PurePosixPath
import copy,csv,datetime,hashlib,importlib.util,io,json,shutil,tarfile
R=Path(__file__).resolve().parent
S=R.parent/'20261126-open-cli-batch/dashboard'
IDS={'CONC-08','BC-20','BC-24'}
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def main():
 snap=read(S/'snapshot.json');before=copy.deepcopy(snap);mf=read(S/'manifest.json')
 backup=R/'dashboard-before-terminal-refresh';assert not backup.exists();backup.mkdir()
 for name in ['snapshot.json','dashboard-data.js','manifest.json','final-report.json','scores48.csv','validation.json']:
  shutil.copyfile(S/name,backup/name)
 for cid in IDS:
  for kind in ['data','assets']:
   if (S/kind/cid).exists():shutil.copytree(S/kind/cid,backup/kind/cid)
 with tarfile.open(R/'final-delta.tar.gz') as t:
  delta=json.load(t.extractfile('snapshot.json'));assert {c['id'] for c in delta['cases']}==IDS
  for member in t.getmembers():
   rel=PurePosixPath(member.name)
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe archive path')
   if len(rel.parts)<3 or rel.parts[0] not in ['data','assets'] or rel.parts[1] not in IDS:continue
   assert member.isfile();p=S.joinpath(*rel.parts);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(member).read())
   if member.name not in mf['files']:mf['files'].append(member.name)
  for c in delta['cases']:
   old=next(x for x in snap['cases'] if x['id']==c['id']);c['title']=old.get('title',c['title'])
   if c['id']=='CONC-08':
    record=read(R/'c08-terminal-queue-record.json')
    c.update(status='DEFERRED_NETWORK',validResult=False,scores=None,grade=None,jointPass=None,passA=None,passB=None,
      failureKind='network',failureReason=record['reason'],endedUtc=record['ended_utc'],
      outcomeNote='网络断流后暂缓；非运行中，未取得有效最终成绩。',terminal=True)
    assert c['steps']=={'A':27,'B':61} and c['runId']=='CONC-08-codex-shared-20261128T062013Z'
    c['actorStatuses']={r:'declared_infeasible' if c['metrics'][r]['declaredInfeasible'] else c['actorStatuses'][r] for r in ['A','B']}
    write(S/'data/CONC-08/terminal-outcome.json',{'case_id':'CONC-08','state':c['status'],'run_id':c['runId'],'steps':c['steps'],
      'scores':None,'failure_reason':c['failureReason'],'ended_utc':c['endedUtc'],'no_rerun':True})
    mf['files'].append('data/CONC-08/terminal-outcome.json')
   old.clear();old.update(c);write(S/f'data/{c["id"]}/summary.json',c)
 assert all(c==next(x for x in snap['cases'] if x['id']==c['id']) for c in before['cases'] if c['id'] not in IDS)
 snap['generated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();snap['valid_results']=sum(c['validResult'] for c in snap['cases'])
 write(S/'snapshot.json',snap);write(S/'manifest.json',mf)
 inline=copy.deepcopy(snap)
 for c in inline['cases']:
  if c.get('traceAvailable'):c['actions']={r:read(S/f'data/{c["id"]}/actions-{r}.json') for r in ['A','B']}
 (S/'dashboard-data.js').write_text('window.CONC_SNAPSHOT='+json.dumps(inline,ensure_ascii=True,separators=(',',':'))+';\n',encoding='utf-8')
 spec=importlib.util.spec_from_file_location('val',R.parent/'20261126-shared-case-pipeline-v1/scripts/update_dashboard48.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);counts=mod.validate(S)
 report=read(S/'final-report.json');report.update(updated_utc=snap['generated_utc'],validation=counts)
 report['cases']=[]
 for c in snap['cases']:
  report['cases'].append({'case_id':c['id'],'status':c['status'],'steps_a':c['steps'].get('A'),'steps_b':c['steps'].get('B'),
   'score_a':(c.get('scores') or {}).get('A'),'score_b':(c.get('scores') or {}).get('B'),'joint_pass':c.get('jointPass'),
   'gui_a':c.get('metrics',{}).get('A',{}).get('gui'),'gui_b':c.get('metrics',{}).get('B',{}).get('gui'),
   'cli_a':c.get('metrics',{}).get('A',{}).get('cli'),'cli_b':c.get('metrics',{}).get('B',{}).get('cli'),
   'gui_overlap_pairs_1_5s':c.get('guiOverlapPairs'),'duration_s':c.get('duration_s'),'run_id':c['runId']})
 for series in ['C','BC']:
  g=[c for c in snap['cases'] if c['series']==series and c['validResult']]
  report.setdefault('series',{})[series]={'cases':len(g),'mean_score_a':round(sum(c['scores']['A'] for c in g)/len(g),4),
   'mean_score_b':round(sum(c['scores']['B'] for c in g)/len(g),4),'joint_pass':sum(c['jointPass'] is True for c in g) if series=='BC' else None}
 report['terminal_outcomes']=[{'case_id':c['id'],'status':c['status'],'reason':c.get('failureReason'),'scores':c.get('scores')} for c in snap['cases'] if not c['validResult']]
 write(S/'final-report.json',report)
 stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=list(report['cases'][0]));w.writeheader();w.writerows(report['cases'])
 (S/'scores48.csv').write_text(stream.getvalue(),encoding='utf-8-sig')
 # Final publication keeps every selected screenshot; historical screenshot files remain in local backups only.
 verification={'changed_cases':sorted(IDS),'other_case_records_unchanged':45,'validation':counts,'series':report['series'],
  'c08_status':'DEFERRED_NETWORK','c08_steps':{'A':27,'B':61},'no_reruns':True}
 write(R/'terminal-refresh-verification.json',verification);print(json.dumps(verification,indent=2))
if __name__=='__main__':main()

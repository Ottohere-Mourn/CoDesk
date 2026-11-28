from __future__ import annotations
import hashlib,json
from pathlib import Path
from pipeline.grade import make_grade
EXPECTED={'extract_orders':('ingest','02:00-04:00',2,''),'clean_orders':('transform','03:00-05:00',2,'extract_orders'),'publish_margin':('report','03:00-06:00',2,'clean_orders'),'archive_close':('archive','05:00-07:00',1,'publish_margin')}
def j(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return {}
def actor_ok(root,role,ids):
 doc=j(Path(root)/'schedule_config.yaml');jobs={x.get('job_id'):x for x in doc.get('jobs',[])};ok=all(k in jobs and (jobs[k].get('kind'),jobs[k].get('window'),int(jobs[k].get('quota',0)),jobs[k].get('depends_on',''))==EXPECTED[k] and jobs[k].get('enabled') is True for k in ids);rep=j(Path(root).parent/'guest-output'/(role+'_report.json')) or j(Path(root).parent/'guest-output'/(role+'_schedule_report.json'));run=rep.get('results',rep.get('outcomes',[]));passed=ok and all(x.get('passed') is True for x in run if x.get('job_id') in ids) and {x.get('job_id') for x in run}>=set(ids);return passed,{'schedule_exact':ok,'dry_run_jobs_pass':passed}
def grade_episode(snapshot_root,receipt,run_id):
 root=Path(snapshot_root);a,ae=actor_ok(root,'data',['extract_orders','clean_orders']);b,be=actor_ok(root,'close',['publish_margin','archive_close']);doc=j(root/'schedule_config.yaml');events=[]
 try:events=[json.loads(x) for x in (root/'schedule_events.jsonl').read_text().splitlines() if x.strip()]
 except (OSError,json.JSONDecodeError):pass
 current=hashlib.sha256((root/'schedule_config.yaml').read_bytes()).hexdigest();joint=bool(doc.get('worker_slots')==1 and events and events[-1].get('sha256')==current and len(doc.get('jobs',[]))==4)
 ac=[{'id':'A01','weight':.6,'passed':a,'required':True,'evidence':ae},{'id':'A02','weight':.4,'passed':a,'required':True,'evidence':{'ingest_and_clean_report_complete':a}}];bc=[{'id':'B01','weight':.6,'passed':b,'required':True,'evidence':be},{'id':'B02','weight':.4,'passed':b,'required':True,'evidence':{'publish_and_archive_report_complete':b}}];jc=[{'id':'J01','weight':1,'passed':joint,'required':True,'evidence':{'one_slot_all_jobs_reloaded_as_final_config':joint}}]
 return make_grade(case_id='BC-22',run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=jc,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={'oracle':'BC-22 host schedule, worker, reload receipt and job reports'})

from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
TASKS=[('extract_orders','ingest','02:00-04:00',2,1,''),('clean_orders','transform','03:00-05:00',2,1,'extract_orders'),('publish_margin','report','03:00-06:00',2,1,'clean_orders'),('archive_close','archive','05:00-07:00',1,1,'publish_margin')]
def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--source-dir',required=True);p.add_argument('--start-service',action='store_true');p.add_argument('--open-browser',action='store_true');a=p.parse_args();r=Path(a.workspace).expanduser().resolve()/'scheduler_lab';(r/'out').mkdir(parents=True,exist_ok=True);(r/'schedule_config.yaml').write_text(json.dumps({'revision':0,'worker_slots':1,'jobs':[]},indent=2)+'\n',encoding='utf-8');(r/'tasks.csv').write_text('job_id,kind,window,quota,enabled,depends_on\n'+''.join(','.join(map(str,x))+'\n' for x in TASKS),encoding='utf-8');(r/'scheduler_rules.txt').write_text('The worker has one execution slot. Preserve every job dependency. All times are UTC. Use the exact job IDs, windows, quotas, and dependencies in tasks.csv. Enable all four jobs. The report jobs must follow the transformation chain. Reload the scheduler, trigger a dry run, inspect every result, and write role-specific reports. JSON syntax is valid YAML for this scheduler.\n',encoding='utf-8');(r/'schedule_events.jsonl').write_text('',encoding='utf-8')
 if a.start_service:
  log=(r/'service.log').open('ab',buffering=0);subprocess.Popen([sys.executable,str(Path(a.source_dir)/'scheduler_service.py'),'--root',str(r)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(['google-chrome','http://127.0.0.1:18222/'],start_new_session=True)
if __name__=='__main__':main()

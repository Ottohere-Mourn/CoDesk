from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--source-dir',required=True);p.add_argument('--start-service',action='store_true');p.add_argument('--open-browser',action='store_true');a=p.parse_args();r=Path(a.workspace).expanduser().resolve()/'docs_hub';(r/'docs').mkdir(parents=True,exist_ok=True);(r/'out').mkdir(exist_ok=True)
 (r/'docs/operations_guide.md').write_text('# Operations Guide\n\n## Recovery\nUse the service health check before failover. Record the UTC incident window and preserve the rollback checkpoint.\n',encoding='utf-8')
 (r/'docs/api_guide.md').write_text('# API Guide\n\n## Retries\nUse an idempotency key for each write request. Retry only transient responses with bounded exponential backoff.\n',encoding='utf-8')
 (r/'index.json').write_text(json.dumps({'revision':0,'documents':[]},indent=2),encoding='utf-8');(r/'index_events.jsonl').write_text('',encoding='utf-8')
 (r/'index_rules.txt').write_text('Update only the document assigned in your prompt. Add the listed policy details to the relevant section, preserve existing guidance, rebuild the full-text index after saving, then verify the exact required phrases with search and preview. Save a verification JSON with document path, revision, query, and result count.\n',encoding='utf-8')
 if a.start_service:
  log=(r/'service.log').open('ab',buffering=0);subprocess.Popen([sys.executable,str(Path(a.source_dir)/'index_service.py'),'--root',str(r)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(['google-chrome','http://127.0.0.1:18221/'],start_new_session=True)
if __name__=='__main__':main()

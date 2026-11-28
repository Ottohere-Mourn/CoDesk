from __future__ import annotations
import argparse,hashlib,json
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
def load(root):return json.loads((root/'schedule_config.yaml').read_text(encoding='utf-8'))
def validate(doc):
 jobs=doc.get('jobs',[]);ids=[x.get('job_id') for x in jobs];known=set(ids);results=[]
 for j in jobs:
  deps=j.get('depends_on','');results.append({'job_id':j.get('job_id'),'passed':bool(j.get('enabled') is True and int(j.get('quota',0))>0 and (not deps or deps in known)),'status':'ready' if j.get('enabled') and (not deps or deps in known) else 'blocked'})
 return results
def run(root):
 doc=load(root);results=validate(doc);payload={'revision':doc.get('revision',0),'results':results};(root/'out'/'run_report.json').write_text(json.dumps(payload,indent=2),encoding='utf-8');return payload
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root).resolve()
 class H(BaseHTTPRequestHandler):
  def log_message(self,*x):pass
  def reply(self,obj):
   b=json.dumps(obj).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
  def do_GET(self):
   if self.path=='/':self.reply({'service':'scheduler monitor','actions':['/reload','/run','/status']})
   elif self.path=='/reload':
    d=load(root);d['revision']=int(d.get('revision',0))+1;(root/'schedule_config.yaml').write_text(json.dumps(d,indent=2),encoding='utf-8');e={'revision':d['revision'],'sha256':hashlib.sha256((root/'schedule_config.yaml').read_bytes()).hexdigest()};(root/'schedule_events.jsonl').open('a',encoding='utf-8').write(json.dumps(e)+'\n');self.reply({'status':'reloaded',**e})
   elif self.path=='/run':self.reply(run(root))
   elif self.path=='/status':self.reply({'revision':load(root).get('revision',0),'jobs':validate(load(root))})
   else:self.send_error(404)
 HTTPServer(('127.0.0.1',18222),H).serve_forever()
if __name__=='__main__':main()

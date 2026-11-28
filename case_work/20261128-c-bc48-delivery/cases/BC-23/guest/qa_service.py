from __future__ import annotations
import argparse,hashlib,json,zipfile
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
def validate(root):
 m=json.loads((root/'release_manifest.json').read_text(encoding='utf-8'));issues=[]
 for role in ('client','server'):
  for rel,digest in m.get(role,{}).get('artifacts',{}).items():
   p=(root/rel).resolve()
   if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:issues.append(role+': hash mismatch '+rel)
 if not m.get('client',{}).get('artifacts') or not m.get('server',{}).get('artifacts'):issues.append('both release groups are required')
 client=m.get('client',{}).get('artifacts',{});server=m.get('server',{}).get('artifacts',{})
 for path in client:
  if path.endswith('client_banner.png') and (root/path).exists():
   from PIL import Image
   if Image.open(root/path).size!=(640,360):issues.append('client banner dimensions')
 if any(x.endswith('server_package.zip') for x in server):
  z=next(x for x in server if x.endswith('server_package.zip'))
  try:
   with zipfile.ZipFile(root/z) as f:
    if set(f.namelist())!={'config/service.json','LICENSE.txt'}:issues.append('package members')
  except (OSError,zipfile.BadZipFile):issues.append('invalid server archive')
 return issues
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root).resolve()
 class H(BaseHTTPRequestHandler):
  def log_message(self,*x):pass
  def do_GET(self):
   if self.path=='/receipt':
    events=[]
    try:events=[json.loads(x) for x in (root/'qa/events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    except (OSError,json.JSONDecodeError):pass
    event=events[-1] if events else {'state':'DRAFT','issues':['no QA event']};b=json.dumps(event).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
   if self.path not in ('/release','/validate','/finalize'):self.send_error(404);return
   issues=validate(root);m=json.loads((root/'release_manifest.json').read_text(encoding='utf-8'));status='REJECTED' if issues else 'PASS';m['qa_state']=status;m['revision']=int(m.get('revision',0))+1
   if self.path=='/finalize' and not issues:m['qa_state']='FINAL'
   (root/'release_manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8');event={'action':self.path.strip('/'),'revision':m['revision'],'state':m['qa_state'],'issues':issues};(root/'qa/events.jsonl').open('a',encoding='utf-8').write(json.dumps(event)+'\n');b=json.dumps(event).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 HTTPServer(('127.0.0.1',18223),H).serve_forever()
if __name__=='__main__':main()

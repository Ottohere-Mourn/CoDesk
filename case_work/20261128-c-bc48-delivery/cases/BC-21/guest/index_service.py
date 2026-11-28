from __future__ import annotations
import argparse,hashlib,json
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
def rebuild(root):
 old=json.loads((root/'index.json').read_text(encoding='utf-8'));docs=[]
 for p in sorted((root/'docs').glob('*.md')):
  raw=p.read_text(encoding='utf-8');docs.append({'path':p.name,'text':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()})
 state={'revision':int(old.get('revision',0))+1,'documents':docs};(root/'index.json').write_text(json.dumps(state,indent=2),encoding='utf-8');return state
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();root=Path(a.root).resolve()
 class H(BaseHTTPRequestHandler):
  def log_message(self,*x):pass
  def do_GET(self):
   u=urlparse(self.path);q=parse_qs(u.query);state=json.loads((root/'index.json').read_text(encoding='utf-8'))
   if u.path=='/':body='<h1>Documentation Hub</h1><p>Rebuild the index, search exact terms, and preview a document.</p>'
   elif u.path=='/rebuild':state=rebuild(root);body=json.dumps({'status':'rebuilt','revision':state['revision']})
   elif u.path=='/search':
    term=q.get('q',[''])[0].lower();hits=[{'path':d['path'],'count':d['text'].lower().count(term)} for d in state['documents'] if term and term in d['text'].lower()];body=json.dumps({'revision':state['revision'],'query':term,'hits':hits})
   elif u.path=='/preview':
    name=q.get('doc',[''])[0];p=(root/'docs'/name).resolve();body=p.read_text(encoding='utf-8') if p.parent==(root/'docs').resolve() and p.is_file() else 'not found'
   else:self.send_error(404);return
   b=body.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if u.path=='/' else 'application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 HTTPServer(('127.0.0.1',18221),H).serve_forever()
if __name__=='__main__':main()

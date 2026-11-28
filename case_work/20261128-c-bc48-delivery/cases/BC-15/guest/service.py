from __future__ import annotations
import argparse,json,subprocess,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

LOCK=threading.RLock();ACTIVE={}
def load(repo):
 cfg=json.loads((repo/"services/settings.json").read_text(encoding="utf-8"));env={}
 for line in (repo/".env").read_text(encoding="utf-8").splitlines():
  if "=" in line:k,v=line.split("=",1);env[k]=v
 return {"settings":cfg,"env":env}
def git_audit(repo):
 def git(*args):return subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=True,check=True).stdout.strip()
 return {"branch":git("branch","--show-current"),"head":git("rev-parse","HEAD"),"commits":git("log","-6","--format=%H%x09%s").splitlines(),"working_tree_clean":not bool(git("status","--porcelain"))}
PAGE='''<!doctype html><meta charset="utf-8"><title>Service Lab</title><h1>Service Lab status</h1><p>Frontline: <a href="/health/frontline">health</a></p><p>Catalog: <a href="/health/catalog">health</a></p><button onclick="fetch('/api/restart',{method:'POST'}).then(r=>r.text()).then(alert)">Restart configuration snapshot</button><p><a href="/git-audit">Repository audit</a></p>'''
class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj):
  b=obj if isinstance(obj,bytes) else (obj if isinstance(obj,str) else json.dumps(obj)).encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8" if isinstance(obj,str) else "application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/":return self.send(200,PAGE)
  if self.path=="/health/frontline":
   x=ACTIVE["settings"]["frontline"];ok=x.get("route")=="/v1/customers" and int(x.get("limit",0))==45 and x.get("auth")=="bearer" and ACTIVE["env"].get("SERVICE_A_LIMIT")=="45";return self.send(200 if ok else 503,{"service":"frontline","status":"green" if ok else "red","active":ACTIVE})
  if self.path=="/health/catalog":
   x=ACTIVE["settings"]["catalog"];ok=x.get("route")=="/v1/catalog" and int(x.get("timeout_s",0))==9 and x.get("fallback")=="cache" and ACTIVE["env"].get("SERVICE_B_LIMIT")=="30";return self.send(200 if ok else 503,{"service":"catalog","status":"green" if ok else "red","active":ACTIVE})
  if self.path=="/git-audit":return self.send(200,git_audit(self.server.repo))
  if self.path=="/api/state":return self.send(200,ACTIVE)
  return self.send(404,{"error":"not_found"})
 def do_POST(self):
  if self.path!="/api/restart":return self.send(404,{"error":"not_found"})
  with LOCK:ACTIVE.clear();ACTIVE.update(load(self.server.repo));line=json.dumps({"status":"reloaded","config_hash":__import__("hashlib").sha256((self.server.repo/"services/settings.json").read_bytes()+(self.server.repo/".env").read_bytes()).hexdigest()});
  with (self.server.root/"restart_receipts.jsonl").open("a",encoding="utf-8") as f:f.write(line+"\n")
  return self.send(200,{"status":"reloaded"})
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument("--repo",required=True);p.add_argument("--root",required=True);a=p.parse_args();repo=Path(a.repo);ACTIVE.update(load(repo));s=ThreadingHTTPServer(("127.0.0.1",18115),Handler);s.repo=repo;s.root=Path(a.root);s.serve_forever()
if __name__=="__main__":main()

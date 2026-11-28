from __future__ import annotations
import argparse,hashlib,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
LOCK=threading.RLock();ACTIVE={}
def read_rules(root):return json.loads((root/"rules.yaml").read_text(encoding="utf-8"))
def rule_hash(doc):return hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest()
def evaluate_risk(doc):
 cfg=doc.get("risk",{});threshold=float(cfg.get("min_risk_to_review",99));maxa=int(cfg.get("max_attempts",0));blocked=cfg.get("blocked_region","");cases=[(.91,6,"US","review"),(.20,2,"US","allow"),(.70,7,"CA","review"),(.95,1,"ZZ","block"),(.84,4,"GB","review")];return [{"case":i+1,"passed":(("block" if region==blocked else "review" if score>=threshold or attempts>maxa else "allow")==expected)} for i,(score,attempts,region,expected) in enumerate(cases)]
def evaluate_routes(doc):
 expected=[("/orders","orders-v3","orders-v2",6),("/catalog","catalog-v2","catalog-v1",3),("/profile","profile-v1","profile-cache",4)];rows=doc.get("routing",{}).get("rules",[]);by={x.get("path"):x for x in rows};return [{"path":p,"passed":p in by and by[p].get("primary")==x and by[p].get("fallback")==f and int(by[p].get("timeout_s",0))==t} for p,x,f,t in expected]
PAGE="<!doctype html><meta charset='utf-8'><title>Rule Engine Console</title><h1>Rule Engine Console</h1><p>Inspect active policy: <a href='/active'>active rule snapshot</a></p><p>Run suites: <a href='/evaluate/risk'>risk</a> | <a href='/evaluate/routes'>routing</a></p><button onclick=\"fetch('/reload',{method:'POST'}).then(r=>r.text()).then(alert)\">Reload rules.yaml</button>"
class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj):
  b=obj if isinstance(obj,bytes) else (obj if isinstance(obj,str) else json.dumps(obj)).encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8" if isinstance(obj,str) else "application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/":return self.send(200,PAGE)
  if self.path=="/health":return self.send(200,{"status":"ok"})
  if self.path=="/active":return self.send(200,ACTIVE)
  if self.path=="/reload-events":
   try:rows=[json.loads(x) for x in (self.server.root/"reload_events.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
   except (OSError,json.JSONDecodeError):rows=[]
   return self.send(200,{"events":rows})
  if self.path=="/evaluate/risk":return self.send(200,{"results":evaluate_risk(ACTIVE),"passed":sum(x["passed"] for x in evaluate_risk(ACTIVE))})
  if self.path=="/evaluate/routes":return self.send(200,{"results":evaluate_routes(ACTIVE),"passed":sum(x["passed"] for x in evaluate_routes(ACTIVE))})
  return self.send(404,{"error":"not_found"})
 def do_POST(self):
  if self.path!="/reload":return self.send(404,{"error":"not_found"})
  with LOCK:ACTIVE.clear();ACTIVE.update(read_rules(self.server.root));result={"status":"reloaded","sha256":rule_hash(ACTIVE)}
  with (self.server.root/"reload_events.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(result)+"\n")
  return self.send(200,result)
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True);a=p.parse_args();s=ThreadingHTTPServer(("127.0.0.1",18119),Handler);s.root=Path(a.root);ACTIVE.update(read_rules(s.root));s.serve_forever()
if __name__=="__main__":main()

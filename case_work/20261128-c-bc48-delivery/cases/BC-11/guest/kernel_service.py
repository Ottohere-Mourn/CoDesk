from __future__ import annotations
import argparse,contextlib,io,json,threading,traceback
from datetime import date,datetime
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

LOCK=threading.RLock();NAMESPACE={"__name__":"bc11_persistent_kernel","date":date,"datetime":datetime}
def state(root):return json.loads((root/"q4_pipeline.json").read_text(encoding="utf-8"))
def execute(root,role,code):
 if role not in ("A","B") or not isinstance(code,str) or not code.strip():return {"error":"invalid_request"},400
 with LOCK:
  doc=state(root);buf=io.StringIO();error=None
  try:
   with contextlib.redirect_stdout(buf):exec(compile(code,f"<bc11-{role}-cell>","exec"),NAMESPACE,NAMESPACE)
  except Exception as exc:error=f"{type(exc).__name__}: {exc}"
  item={"index":len(doc["cells"])+1,"section":"A" if role=="A" else "B","code":code,"stdout":buf.getvalue(),"error":error}
  doc["cells"].append(item);tmp=root/"q4_pipeline.json.tmp";tmp.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8");tmp.replace(root/"q4_pipeline.json")
  with (root/"kernel_events.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({"index":item["index"],"section":item["section"],"error":error is not None})+"\n")
  return {"index":item["index"],"section":item["section"],"stdout":item["stdout"],"error":error,"namespace_names":sorted(k for k in NAMESPACE if not k.startswith("__"))},(200 if error is None else 422)
PAGE="""<!doctype html><meta charset='utf-8'><title>Q4 Pipeline Notebook</title><h1>Q4 Pipeline Notebook</h1><p>Persistent Python kernel. Use the Execute API to run ordered cells.</p><pre id='cells'></pre><script>fetch('/state').then(r=>r.json()).then(x=>document.querySelector('#cells').textContent=JSON.stringify(x,null,2));</script>"""
class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj,kind="application/json; charset=utf-8"):
  body=obj if isinstance(obj,bytes) else (obj if isinstance(obj,str) else json.dumps(obj)).encode();self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path=="/":return self.send(200,PAGE,"text/html; charset=utf-8")
  if self.path=="/health":return self.send(200,{"status":"ok","kernel":"persistent"})
  if self.path=="/state":return self.send(200,state(self.server.root))
  return self.send(404,{"error":"not_found"})
 def do_POST(self):
  if self.path!="/execute":return self.send(404,{"error":"not_found"})
  try:data=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
  except json.JSONDecodeError:return self.send(400,{"error":"invalid_json"})
  result,status=execute(self.server.root,data.get("role"),data.get("code"));return self.send(status,result)
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True);a=p.parse_args();srv=ThreadingHTTPServer(("127.0.0.1",18111),Handler);srv.root=Path(a.root);srv.serve_forever()
if __name__=="__main__":main()

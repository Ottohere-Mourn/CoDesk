from __future__ import annotations
import argparse,hashlib,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

LOCK=threading.RLock();PAGE="""<!doctype html><meta charset='utf-8'><title>Operations Board</title><h1>Operations Board</h1><p>Load, filter and edit the complete board snapshot, then save it as a full-state replacement.</p><label>Queue <select id='q'><option>frontline</option><option>backend</option></select></label><button onclick='load()'>Load current state</button><button onclick='save()'>Save full state</button><pre id='message'></pre><textarea id='state' style='width:95%;height:75vh'></textarea><script>async function load(){let r=await fetch('/api/state');document.querySelector('#state').value=JSON.stringify(await r.json(),null,2)}async function save(){let r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json','X-Queue':document.querySelector('#q').value},body:document.querySelector('#state').value});document.querySelector('#message').textContent=await r.text()}load()</script>"""
def save(root,state,queue):
 if not isinstance(state,dict) or not isinstance(state.get("cards"),list):return {"error":"state_requires_cards_array"},400
 with LOCK:
  p=root/"board_state.json";old=json.loads(p.read_text(encoding="utf-8"));revision=int(old.get("revision",0))+1;state["revision"]=revision;tmp=root/"board_state.json.tmp";tmp.write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8");tmp.replace(p);digest=hashlib.sha256(p.read_bytes()).hexdigest()
  with (root/"save_events.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({"queue":queue,"revision":revision,"sha256":digest,"card_count":len(state["cards"])})+"\n")
  return {"revision":revision,"sha256":digest,"card_count":len(state["cards"])},200
class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj):
  body=obj if isinstance(obj,bytes) else (obj if isinstance(obj,str) else json.dumps(obj)).encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8" if isinstance(obj,str) else "application/json; charset=utf-8");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path=="/":return self.send(200,PAGE)
  if self.path=="/health":return self.send(200,{"status":"ok"})
  if self.path=="/api/state":return self.send(200,json.loads((self.server.root/"board_state.json").read_text(encoding="utf-8")))
  return self.send(404,{"error":"not_found"})
 def do_POST(self):
  if self.path!="/api/save":return self.send(404,{"error":"not_found"})
  try:data=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
  except json.JSONDecodeError:return self.send(400,{"error":"invalid_json"})
  result,status=save(self.server.root,data,self.headers.get("X-Queue","unknown"));return self.send(status,result)
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True);a=p.parse_args();srv=ThreadingHTTPServer(("127.0.0.1",18114),Handler);srv.root=Path(a.root);srv.serve_forever()
if __name__=="__main__":main()

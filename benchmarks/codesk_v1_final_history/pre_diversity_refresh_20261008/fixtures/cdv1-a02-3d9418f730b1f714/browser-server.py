from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
STATE=Path('/home/oem/codesk/cdv1-a02-3d9418f730b1f714/browser-initial-state.json');EVENTS=Path('/home/oem/codesk/cdv1-a02-3d9418f730b1f714/browser-events.jsonl')
def event(x):
 x["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(x,sort_keys=True)+"\n")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path!="/workspace":return self.reply({"error":"not found"},404)
  html=("<!doctype html><meta charset='utf-8'><title>CoDesk record workspace</title>"
   "<style>body{font:20px Arial;margin:24px}button,input{font:20px Arial;padding:8px;margin:8px}</style>"
   "<h1>Record workspace</h1><p>Record A and Record B have separate goal fields.</p>"
   "<button id=record-a>Record A</button><button id=record-b>Record B</button>"
   "<input id=value autocomplete=off><button id=save>Save selected</button><output id=result></output>"
   "<script>let selected='record-a';const drafts={'record-a':'','record-b':''};"
   "document.querySelector('#value').addEventListener('input',e=>{drafts[selected]=e.target.value});"
   "async function selectRecord(r){selected=r;document.querySelector('#value').value=drafts[r];"
   "await fetch('/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record:r})})}"
   "document.querySelector('#record-a').onclick=()=>selectRecord('record-a');"
   "document.querySelector('#record-b').onclick=()=>selectRecord('record-b');"
   "document.querySelector('#save').onclick=async()=>{let value=document.querySelector('#value').value;"
   "let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record:selected,value})});"
   "document.querySelector('#result').textContent=r.ok?'Saved':'Rejected'};</script>")
  self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(html)));self.end_headers();self.wfile.write(html.encode());event({"kind":"page_loaded"})
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text());r=p.get("record")
  if r not in ("record-a","record-b"):return self.reply({"error":"bad record"},400)
  if self.path=="/select":
   before=s["selected_record"];s["selected_record"]=r;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"record_selected","before":before,"record":r});return self.reply({"ok":True})
  if self.path=="/save":
   if s["selected_record"]!=r:return self.reply({"error":"selection changed"},409)
   s["records"][r]["goal"]=str(p.get("value",""));s["records"][r]["revision"]+=1;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"record_saved","record":r,"revision":s["records"][r]["revision"]});return self.reply({"ok":True})
  return self.reply({"error":"not found"},404)
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8767),H).serve_forever()

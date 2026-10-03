from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
STATE=Path('/home/oem/codesk/cdv1-a01-137922986f6115b6/browser-initial-state.json'); EVENTS=Path('/home/oem/codesk/cdv1-a01-137922986f6115b6/browser-events.jsonl')
def event(x):
 x["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(x,sort_keys=True)+"\n")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path=="/state":
   s=json.loads(STATE.read_text());s["events"]=EVENTS.read_text().splitlines() if EVENTS.exists() else []
   return self.reply(s)
  tab="tab-a" if self.path=="/actor-a" else "tab-b" if self.path=="/actor-b" else None
  if not tab:return self.reply({"error":"not found"},404)
  html=("<!doctype html><meta charset='utf-8'><title>CoDesk "+tab+"</title>"
   "<style>body{font:22px Arial;margin:32px}input,button{font:22px Arial;padding:8px;margin:12px}</style>"
   "<h1>"+tab+"</h1><p>Complete the independent "+tab+" record.</p>"
   "<input id=value aria-label='Goal value'><button id=submit>Submit</button><output id=result></output>"
   "<script>const tab='"+tab+"';"
   "async function context(){await fetch('/context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tab})})}"
   "document.addEventListener('visibilitychange',()=>{if(!document.hidden)context()});context();"
   "document.querySelector('#submit').onclick=async()=>{let value=document.querySelector('#value').value;"
   "await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tab,value})});"
   "document.querySelector('#result').textContent='Saved';};</script>")
  b=html.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);event({"kind":"tab_page_loaded","tab":tab})
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text())
  if self.path=="/context":
   tab=p.get("tab")
   if tab not in s["tabs"]:return self.reply({"error":"bad tab"},400)
   before=s["active_tab"];s["active_tab"]=tab;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"active_tab_changed","before":before,"after":tab});return self.reply({"ok":True})
  if self.path!="/submit":return self.reply({"error":"not found"},404)
  tab=p.get("tab")
  if tab not in s["tabs"]:return self.reply({"error":"bad tab"},400)
  s["active_tab"]=tab;s["tabs"][tab]["goal"]=str(p.get("value",""));s["tabs"][tab]["revision"]+=1
  STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"form_submitted","tab":tab,"revision":s["tabs"][tab]["revision"],"value":p.get("value")});return self.reply({"ok":True})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8766),H).serve_forever()

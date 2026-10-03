from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
STATE=Path('/home/oem/codesk/cdv1-an1-7e33372605e47b2f/browser-initial-state.json');EVENTS=Path('/home/oem/codesk/cdv1-an1-7e33372605e47b2f/browser-events.jsonl')
def event(x):
 x["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(x,sort_keys=True)+"\n")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path.split("#",1)[0]!="/workspace":return self.reply({"error":"not found"},404)
  html=("<!doctype html><meta charset='utf-8'><title>CoDesk route workspace</title>"
   "<style>body{font:22px Arial;margin:30px}button,input{font:22px Arial;padding:8px;margin:8px}</style>"
   "<h1>Route workspace</h1><button id=a>Route A</button><button id=b>Route B</button>"
   "<p id=label>Route A</p><input id=value><button id=save>Submit route value</button><output id=result></output>"
   "<script>let route='route-a';const vals={'route-a':'','route-b':''};"
   "function selectRoute(r){route=r;history.pushState({},'', '/workspace#'+r);document.querySelector('#label').textContent=r;"
   "document.querySelector('#value').value=vals[r];fetch('/context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({route:r})})}"
   "document.querySelector('#a').onclick=()=>selectRoute('route-a');document.querySelector('#b').onclick=()=>selectRoute('route-b');"
   "document.querySelector('#value').addEventListener('input',e=>vals[route]=e.target.value);"
   "document.querySelector('#save').onclick=async()=>{await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({route,value:document.querySelector('#value').value})});document.querySelector('#result').textContent='Saved'};</script>")
  self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(html)));self.end_headers();self.wfile.write(html.encode());event({"kind":"page_loaded"})
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text());route=p.get("route")
  if route not in ("route-a","route-b"):return self.reply({"error":"bad route"},400)
  if self.path=="/context":
   before=s["active_route"];s["active_route"]=route;s["tab_hash"]="/workspace#"+route;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"route_changed","before":before,"after":route});return self.reply({"ok":True})
  if self.path=="/submit":
   s["active_route"]=route;s["routes"][route]["value"]=str(p.get("value",""));s["routes"][route]["revision"]+=1;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"route_submitted","route":route,"revision":s["routes"][route]["revision"]});return self.reply({"ok":True})
  return self.reply({"error":"not found"},404)
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8770),H).serve_forever()

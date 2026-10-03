from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json
STATE=Path("/home/oem/codesk/cdv1-u04-70fddd74371cec36/browser-initial-state.json")
EVENTS=Path("/home/oem/codesk/cdv1-u04-70fddd74371cec36/browser-events.jsonl")
HTML=Path("/home/oem/codesk/cdv1-u04-70fddd74371cec36/workspace.html")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path!="/workspace":return self.reply({"error":"not found"},404)
  b=HTML.read_bytes();self.send_response(200);self.send_header("Content-Type","text/html");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text());aid=p.get("actor")
  if self.path=="/select":
   rows=sorted({int(x) for x in p.get("rows",[])});s["selected_rows"]=rows
   event={"kind":"selection_change","rows":rows,"generation":s.get("selection_generation",0)+1}
   s["selection_generation"]=event["generation"]
  elif aid not in ("A","B"):return self.reply({"error":"bad actor"},400)
  elif self.path=="/context":
   before=s.get("active_context");s["active_context"]=str(p.get("context"));s["active_filter"]=s["active_context"];s["context_revision"]+=1
   event={"kind":"context_change","actor":aid,"before":before,"after":s["active_context"]}
  elif self.path=="/submit":
   requested=aid;active=s.get("active_filter","all");target=active[-1].upper() if active in ("filter-a","filter-b") else aid
   s["actors"][target]["value"]=str(p.get("value",""));s["actors"][target]["revision"]+=1
   event={"kind":"submit","actor":requested,"routed_actor":target,"active_context":active,"revision":s["actors"][target]["revision"]}
  elif self.path=="/bulk":
   rows=sorted({int(x) for x in s.get("selected_rows",[])});status=str(p.get("status",""))
   for rid in rows:
    key=str(rid)
    if key in s.get("rows",{}):s["rows"][key]["status"]=status
   value=json.dumps({"rows":rows,"status":status},sort_keys=True)
   s["actors"][aid]["value"]=value;s["actors"][aid]["revision"]+=1
   event={"kind":"bulk_update","actor":aid,"rows":rows,"status":status,"selection_generation":s.get("selection_generation",0),"revision":s["actors"][aid]["revision"]}
  elif self.path=="/editor":
   text=str(p.get("value",""));s["editor_text"]=text;s["actors"][aid]["value"]=text;s["actors"][aid]["revision"]+=1
   s.setdefault("undo_stack",[]).append({"actor":aid,"value":text,"revision":s["actors"][aid]["revision"]})
   event={"kind":"editor_commit","actor":aid,"revision":s["actors"][aid]["revision"]}
  else:return self.reply({"error":"not found"},404)
  with EVENTS.open("a") as f:f.write(json.dumps(event,sort_keys=True)+"\n")
  STATE.write_text(json.dumps(s,sort_keys=True));return self.reply({"ok":True,"rows":event.get("rows",[]),"status":event.get("status")})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8784),H).serve_forever()

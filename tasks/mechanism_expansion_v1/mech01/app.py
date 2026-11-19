#!/usr/bin/env python3
"""Local procurement reconciliation fixture; state is per Guest/episode."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse, json, threading, time

INITIAL = {
 "A": {"vendor":"Northwind Safety", "reference":"", "amount":"", "expected_reference":"INV-48217", "expected_amount":"1840.00", "saved":False},
 "B": {"payee":"Riverside Testing", "reference":"", "amount":"", "expected_reference":"ACH-77104", "expected_amount":"965.50", "saved":False},
}
PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Procurement Exception Reconciliation</title>
<style>
body{font:16px Arial,sans-serif;margin:24px;color:#243241;background:#f6f8fa}h1{margin:0 0 6px}
header{margin-bottom:16px}.cards{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:white;border:1px solid #aab8c5;border-radius:8px;padding:18px;min-height:370px}
h2{font-size:20px;color:#14385b}.source{background:#edf4f8;padding:14px;margin:12px 0;border-left:4px solid #24759c}
.reference{font-size:20px;font-weight:bold;user-select:text}.row{display:grid;grid-template-columns:120px 1fr;gap:10px;margin:12px 0}
input{font-size:16px;padding:9px;border:1px solid #8798a8;width:95%}button{font-size:16px;padding:9px 18px}
.save{background:#176b48;color:white;border:0;border-radius:3px}.status{margin-left:12px}
</style></head><body><header><h1>Procurement Exception Reconciliation</h1><div>Use the source voucher and complete only your assigned reconciliation row.</div></header>
<div class="cards">
<section class="card" data-role="A"><h2>Role A — Vendor invoice exception</h2>
<div class="source"><b>Invoice source — Northwind Safety</b><p>Approved total: $1,840.00</p><p>Invoice reference: <span id="source-A" class="reference">INV-48217</span></p></div>
<div class="row"><label for="vendor-A">Vendor</label><input id="vendor-A" value="Northwind Safety"></div>
<div class="row"><label for="reference-A">Reference</label><input id="reference-A"></div>
<div class="row"><label for="amount-A">Approved amount</label><input id="amount-A"></div>
<button class="save" data-save="A">Save A row</button><span class="status" id="status-A">Not saved</span></section>
<section class="card" data-role="B"><h2>Role B — Remittance confirmation</h2>
<div class="source"><b>Payment voucher — Riverside Testing</b><p>Released total: $965.50</p><p>ACH receipt reference: <span id="source-B" class="reference">ACH-77104</span></p></div>
<div class="row"><label for="payee-B">Payee</label><input id="payee-B" value="Riverside Testing"></div>
<div class="row"><label for="reference-B">Reference</label><input id="reference-B"></div>
<div class="row"><label for="amount-B">Released amount</label><input id="amount-B"></div>
<button class="save" data-save="B">Save B row</button><span class="status" id="status-B">Not saved</span></section></div>
<script>
const expected={A:'INV-48217',B:'ACH-77104'};
async function post(path,obj){return fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)}).then(r=>r.json())}
document.addEventListener('copy',e=>{const value=window.getSelection()?.toString()||'';const owner=['A','B'].find(r=>value===expected[r])||null;post('/api/event',{event:'copy',owner,value,time:Date.now()})});
document.addEventListener('paste',e=>{const t=e.target;if(!t.id.startsWith('reference-'))return;const role=t.id.endsWith('-A')?'A':'B';const value=e.clipboardData?.getData('text')||'';post('/api/event',{event:'paste',role,value,source_value:expected[role],time:Date.now()})});
async function saveRole(role){
 const card=document.querySelector('[data-role="'+role+'"]');if(!card)return;
 const fields=Object.fromEntries([...card.querySelectorAll('input')].map(el=>[el.id.replace('-'+role,''),el.value]));
 const status=document.getElementById('status-'+role);
 try{const r=await post('/api/save',{role,fields});if(status)status.textContent=r.ok?'Saved':'Check fields';}
 catch(err){if(status)status.textContent='Save failed';console.error(err);}
}
document.addEventListener('change',e=>{
 const card=e.target.closest('.card');if(!card||!e.target.matches('input'))return;
 const role=card.dataset.role;const field=e.target.id.replace('-'+role,'');
 post('/api/field',{role,field,value:e.target.value});
});
document.addEventListener('click',e=>{
 const button=e.target.closest('[data-save]');if(!button)return;
 saveRole(button.dataset.save);
});
</script></body></html>"""

class AppState:
 def __init__(self,path):
  self.path=Path(path);self.lock=threading.RLock();self.rows=json.loads(json.dumps(INITIAL));self.events=[];self.flush()
 def flush(self):
  obj={"rows":self.rows,"events":self.events}
  tmp=self.path.with_suffix(".tmp");tmp.parent.mkdir(parents=True,exist_ok=True)
  tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");tmp.replace(self.path)
 def snapshot(self):
  return {"rows":json.loads(json.dumps(self.rows)),"events":json.loads(json.dumps(self.events))}
class Handler(BaseHTTPRequestHandler):
 state=None
 def log_message(self,*args):pass
 def send(self,status,obj):
  is_api=self.path.startswith("/api")
  data=(json.dumps(obj,ensure_ascii=False) if is_api else str(obj)).encode("utf-8")
  self.send_response(status);self.send_header("Content-Type","application/json" if is_api else "text/html; charset=utf-8")
  self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(data)
 def body(self):
  n=int(self.headers.get("Content-Length","0"));return json.loads(self.rfile.read(n) or b"{}")
 def do_GET(self):
  if self.path=="/health":return self.send(200,{"ok":True,"case":"MECH-01"})
  if self.path=="/api/state":
   with self.state.lock:return self.send(200,self.state.snapshot())
  if self.path in {"/","/desk"}:return self.send(200,PAGE)
  return self.send(404,{"error":"not found"})
 def do_POST(self):
  obj=self.body()
  with self.state.lock:
   if self.path=="/api/reset":
    self.state.rows=json.loads(json.dumps(INITIAL));self.state.events=[];self.state.flush();return self.send(200,{"ok":True})
   if self.path=="/api/event":
    row={"kind":obj.get("event"),"time":time.time(),**obj};self.state.events.append(row);self.state.flush();return self.send(200,{"ok":True})
   if self.path=="/api/field":
    role=str(obj.get("role"));field=str(obj.get("field"))
    if role not in {"A","B"} or field not in {"vendor","payee","reference","amount"}:return self.send(400,{"ok":False})
    self.state.rows[role][field]=str(obj.get("value",""));self.state.flush();return self.send(200,{"ok":True})
   if self.path=="/api/save":
    role=str(obj.get("role"))
    if role not in self.state.rows:return self.send(400,{"ok":False})
    fields=obj.get("fields",{})
    if not isinstance(fields,dict):return self.send(400,{"ok":False})
    allowed={"A":{"vendor","reference","amount"},"B":{"payee","reference","amount"}}[role]
    for key,value in fields.items():
     if key in allowed:self.state.rows[role][key]=str(value)
    self.state.rows[role]["saved"]=True
    self.state.events.append({"kind":"save","time":time.time(),"role":role,"fields":{k:str(v) for k,v in fields.items() if k in allowed}})
    self.state.flush();return self.send(200,{"ok":True})
  return self.send(404,{"error":"not found"})

def main():
 p=argparse.ArgumentParser();p.add_argument("--port",type=int,default=8311);p.add_argument("--state",required=True);p.add_argument("--db",default="");a=p.parse_args()
 Handler.state=AppState(a.state);ThreadingHTTPServer(("127.0.0.1",a.port),Handler).serve_forever()
if __name__=="__main__":main()

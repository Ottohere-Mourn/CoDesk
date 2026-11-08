"""Loopback-only synthetic legacy CRM UI for CRM-LU1; explicit full-record form Save."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import argparse, html, json, os, tempfile, threading
from scripts import crm_lu1_fixture_v1 as fx

class Store:
    def __init__(self, path):
        self.path=Path(path); self.lock=threading.RLock(); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.data=json.loads(self.path.read_text()) if self.path.exists() else fx.new_state()
        if not self.path.exists(): self.save()
    def save(self):
        fd,tmp=tempfile.mkstemp(prefix=".crm-lu1-",dir=str(self.path.parent))
        try:
            with os.fdopen(fd,"w") as f:
                json.dump(self.data,f,ensure_ascii=False,sort_keys=True,indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    def commit(self, actor, data):
        with self.lock:
            ev=fx.save_full_record(self.data,actor,data.get("customer_id",""),data,data.get("loaded_version",1))
            self.save()
            return ev

def esc(x): return html.escape(str(x),quote=True)
def page(state):
    record=state["record"]
    parts=["""<!doctype html><html><head><meta charset="utf-8"><title>Northwind CRM - Customer C-014</title>
<style>
body{font:17px Arial,sans-serif;margin:24px;background:#f3f6f9;color:#18232f}
main{max-width:1000px;margin:auto}.banner,.card{background:white;border:1px solid #cbd4df;border-radius:9px;padding:16px;margin:12px 0}
label{display:block;font-weight:bold;margin:10px 0 5px}input{font-size:18px;padding:8px;width:96%;box-sizing:border-box}
button{font-size:17px;padding:9px 14px;margin-right:8px}.source{background:#edf5ff;padding:10px;margin:10px 0}
.hint{color:#536476;font-size:14px}.ok{color:#147a40;font-weight:bold}.tabs{margin:12px 0}
</style></head><body><main><h1>Northwind Customer Service CRM</h1>
<div class="banner"><h2>Customer C-014 - Service account</h2>
<p>Renewal and billing contact information is maintained in assigned sections.</p></div>
<div class="tabs"><button id="tab-A" onclick="showPanel('A')">Renewal contact</button>
<button id="tab-B" onclick="showPanel('B')">Billing email</button></div>
<section id="panel-A" class="card"><h2>Renewal contact update - Actor A</h2>
<div class="source"><b>Authorized source:</b> Signed renewal addendum RN-014<br><b>Verified value:</b> Jordan Lee</div>
<form id="form-A" data-role="A">
<input type="hidden" name="customer_id" value="C-014">
<input type="hidden" name="loaded_version" value="VERSION">
<input type="hidden" name="renewal_contact" value="CONTACT">
<input type="hidden" name="billing_email" value="EMAIL">
<label>Renewal contact</label><input name="renewal_contact" value="CONTACT" aria-label="Renewal contact">
<button type="submit">Save renewal contact</button><span class="result" id="result-A"></span></form></section>
<section id="panel-B" class="card" hidden><h2>Billing email update - Actor B</h2>
<div class="source"><b>Authorized source:</b> Verified billing-contact notice BN-014<br><b>Verified value:</b> ap@northwind.example</div>
<form id="form-B" data-role="B">
<input type="hidden" name="customer_id" value="C-014">
<input type="hidden" name="loaded_version" value="VERSION">
<input type="hidden" name="renewal_contact" value="CONTACT">
<input type="hidden" name="billing_email" value="EMAIL">
<label>Billing email</label><input name="billing_email" value="EMAIL" aria-label="Billing email">
<button type="submit">Save billing email</button><span class="result" id="result-B"></span></form></section>
<p><button onclick="location.reload()">Refresh record</button></p>
<script>
function showPanel(role){document.getElementById('panel-A').hidden=role!=='A';document.getElementById('panel-B').hidden=role!=='B';}
document.querySelectorAll('form').forEach(f=>f.addEventListener('submit',async ev=>{
 ev.preventDefault();const role=f.dataset.role;const obj=Object.fromEntries(new FormData(f).entries());
 const r=await fetch('/save/'+role,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});
 const v=await r.json();document.getElementById('result-'+role).innerHTML=r.ok
 ? '<span class="ok">Saved successfully.</span>' : '<span>Save rejected: '+v.error+'</span>';
}));
</script></main></body></html>"""]
    vals={"VERSION":str(record["record_version"]),"CONTACT":esc(record["renewal_contact"]),
          "EMAIL":esc(record["billing_email"])}
    html_doc=parts[0]
    for token,value in vals.items(): html_doc=html_doc.replace(token,value)
    return html_doc

def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def respond(self,status,body,ctype="text/html; charset=utf-8"):
            raw=body.encode();self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            p=urlparse(self.path).path
            if p=="/health":return self.respond(200,'{"ok":true}',"application/json")
            if p=="/api/state":return self.respond(200,json.dumps(store.data,ensure_ascii=False),"application/json")
            if p=="/":return self.respond(200,page(store.data))
            return self.respond(404,"not found")
        def do_POST(self):
            try:
                actor=urlparse(self.path).path.rsplit("/",1)[-1]
                data=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
                event=store.commit(actor,data)
                return self.respond(200,json.dumps({"ok":True,"committed_version":event["committed_version"]}),"application/json")
            except (ValueError,KeyError,json.JSONDecodeError) as ex:
                return self.respond(400,json.dumps({"error":str(ex)}),"application/json")
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);p.add_argument("--state",default="/tmp/crm-lu1/state.json")
    a=p.parse_args();s=Store(a.state);ThreadingHTTPServer((a.host,a.port),make_handler(s)).serve_forever()
if __name__=="__main__": main()


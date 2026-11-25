"""Two loopback-only, directly accessible MiniCRM/TechWiki task sites."""
from __future__ import annotations
import argparse, json, secrets, threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

SOPS=[
 {"id":"SOP-01","title":"Restore a Network Interface After DHCP Lease Loss","category":"Networking","code_block":"sudo ip link set dev enp3s0 up\nsudo dhclient -v -timeout 18 enp3s0\nsudo journalctl -u NetworkManager --since \"15 min ago\" | grep -F 'CFG-NET-7841'","rules":["Confirm the physical link is up before renewing a lease.","Record the assigned gateway and DNS resolver after recovery."]},
 {"id":"SOP-02","title":"Recover a Delayed Replica Safely","category":"Database","code_block":"psql -c \"SELECT pg_is_in_recovery();\"\npg_ctl reload -D /srv/pgdata --wait\npsql -c \"SELECT application_name, replay_lag FROM pg_stat_replication;\" # CFG-DB-3168","rules":["Never promote a replica while the primary is reachable.","Escalate when replay lag remains above 90 seconds."]},
 {"id":"SOP-03","title":"Rotate an Expiring Service Certificate","category":"Security","code_block":"openssl x509 -in /etc/tls/service.pem -noout -enddate\ninstall -m 0640 staged.pem /etc/tls/service.pem\nsystemctl reload edge-proxy.service # CFG-SEC-9027","rules":["Validate the certificate chain and hostname before deployment.","Keep the previous certificate available until health checks pass."]},
 {"id":"SOP-04","title":"Recover a Read-only Archive Volume","category":"Storage","code_block":"findmnt -no SOURCE,FSTYPE,OPTIONS /archive\nfsck.ext4 -fn /dev/mapper/archive_lv\nmount -o remount,rw /archive # CFG-STO-5542","rules":["Run a read-only filesystem check before changing mount mode.","Verify free space and a sample checksum after remounting."]}
]

DOCS_PAGE='''<!doctype html><meta charset="utf-8"><title>MiniCRM | Application Library</title><style>body{font:15px Arial;background:#f2f5f8;color:#17324d;margin:25px}header{background:#17324d;color:white;padding:16px;border-radius:8px}main{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}.card{background:white;padding:12px;border:1px solid #d5dee8;border-radius:8px}.card img{width:100%;height:380px;object-fit:contain}.tag{color:#667085}</style><header><h1>MiniCRM · Client Applications</h1><div>Four scanned onboarding forms</div></header><main>__IMAGES__</main><script>document.addEventListener('copy',()=>fetch('/api/a/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'clipboard_copy',text:window.getSelection().toString()})}));document.addEventListener('paste',e=>fetch('/api/a/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'clipboard_paste',text:e.clipboardData.getData('text')})}));</script>'''
FORM_PAGE='''<!doctype html><meta charset="utf-8"><title>MiniCRM | Client Record</title><style>body{font:15px Arial;background:#f2f5f8;color:#17324d;margin:30px}.card{background:white;max-width:720px;padding:22px;border:1px solid #d5dee8;border-radius:9px}label{display:block;margin:12px 0 4px}input,select{width:100%;padding:10px;border:1px solid #aebdcd;border-radius:5px}button{padding:10px 15px;background:#176b87;color:white;border:0;border-radius:5px;margin-top:14px;cursor:pointer}</style><div class="card"><h1>New Client Record</h1><p>Transcribe one application from the Application Library, then submit it.</p><form id="f"><label>Company name<input name="company_name" required></label><label>IBAN<input name="iban" required></label><label>Tax ID<input name="tax_id" required></label><label>Client tier<select name="tier"><option>Gold</option><option>Silver</option><option>Platinum</option></select></label><button>Submit Client</button></form><button id="export">Export CRM JSON</button><output id="msg"></output></div><script>document.getElementById('f').onsubmit=async e=>{e.preventDefault();let x=Object.fromEntries(new FormData(e.target));let r=await fetch('/api/a/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(x)});document.getElementById('msg').textContent=r.ok?'Client saved.':'Submission failed.';e.target.reset()};document.getElementById('export').onclick=async()=>{let r=await fetch('/api/a/export',{method:'POST'});document.getElementById('msg').textContent=r.ok?'CRM export saved.':'Export failed.'};document.addEventListener('paste',e=>fetch('/api/a/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'clipboard_paste',text:e.clipboardData.getData('text')})}));</script>'''
LEGACY_PAGE='''<!doctype html><meta charset="utf-8"><title>TechWiki | Legacy Runbooks</title><style>body{font:15px Arial;background:#f5f7fa;color:#172b4d;margin:24px}.sop{background:#fff;border-left:5px solid #547a96;margin:12px 0;padding:15px;border-radius:5px}pre{background:#152334;color:#e6edf5;padding:12px;white-space:pre-wrap}.cat{display:inline-block;background:#dbeafe;padding:4px 8px;border-radius:4px}</style><h1>TechWiki · Legacy Operations SOP Library</h1><p>Select one complete SOP at a time for migration to the new editor.</p>__SOPS__<script>document.addEventListener('copy',()=>fetch('/api/b/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'clipboard_copy',text:window.getSelection().toString()})}));document.addEventListener('paste',e=>fetch('/api/b/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'clipboard_paste',text:e.clipboardData.getData('text')})}));</script>'''
EDITOR_PAGE='''<!doctype html><meta charset="utf-8"><title>TechWiki | SOP Publisher</title><style>body{font:15px Arial;background:#f5f7fa;color:#172b4d;margin:25px}.box{background:white;max-width:900px;padding:20px;border:1px solid #d5dee8;border-radius:9px}label{display:block;margin-top:11px}input,textarea{box-sizing:border-box;width:100%;padding:9px;border:1px solid #adbccc;border-radius:5px}textarea{height:74px;font-family:monospace}.drop{display:inline-block;position:relative}#menu{position:absolute;z-index:2;list-style:none;margin:0;padding:5px;background:white;border:1px solid #9aabba;box-shadow:0 2px 6px #0002}#menu button{display:block;width:150px;padding:8px;background:white;border:0;text-align:left}button{cursor:pointer;padding:8px 13px}#publish{margin-top:14px;background:#176b87;color:white;border:0;border-radius:5px}</style><div class="box"><h1>TechWiki · Publish migrated SOP</h1><label>Document ID<select id="doc">__OPTIONS__</select></label><label>Title<input id="title"></label><label>Three-line command block<textarea id="code"></textarea></label><label>Core rule 1<input id="r1"></label><label>Core rule 2<input id="r2"></label><label>Category</label><div class="drop"><button id="pick">Choose category</button><ul id="menu" hidden>__CATS__</ul></div><button id="publish">Publish SOP</button><button id="export">Export Wiki JSON</button><output id="msg"></output></div><script>
const doc=document.getElementById('doc'),menu=document.getElementById('menu');let category='',open=false,eventPending=[];
doc.onchange=()=>{document.getElementById('title').value='';document.getElementById('code').value='';document.getElementById('r1').value='';document.getElementById('r2').value='';category='';document.getElementById('pick').textContent='Choose category'};
function ev(t,more={}){const p=fetch('/api/b/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:t,...more})});eventPending.push(p);return p}document.addEventListener('paste',e=>ev('clipboard_paste',{text:e.clipboardData.getData('text')}));
function closeMenu(reason){if(open){open=false;menu.hidden=true;ev('dropdown_dismiss',{reason});}}
document.getElementById('pick').onclick=()=>{open=!open;menu.hidden=!open};window.addEventListener('blur',()=>closeMenu('window_blur'));document.addEventListener('visibilitychange',()=>{if(document.hidden)closeMenu('tab_hidden')});
menu.querySelectorAll('button').forEach(b=>b.onclick=()=>{category=b.dataset.cat;document.getElementById('pick').textContent=category;open=false;menu.hidden=true;ev('category_select',{category,id:doc.value})});
document.getElementById('publish').onclick=async()=>{await Promise.all(eventPending.splice(0));let data={id:doc.value,title:document.getElementById('title').value,code_block:document.getElementById('code').value,rules:[document.getElementById('r1').value,document.getElementById('r2').value],category};let r=await fetch('/api/b/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});document.getElementById('msg').textContent=r.ok?'SOP published.':'Choose a category and complete all fields.'};document.getElementById('export').onclick=async()=>{let r=await fetch('/api/b/export',{method:'POST'});document.getElementById('msg').textContent=r.ok?'Wiki export saved.':'Export failed.'};</script>'''

class State:
 def __init__(self,assets:Path,out:Path,state_path:Path):
  self.assets,self.out,self.state_path=assets,out,state_path;self.token=secrets.token_urlsafe(20);self.lock=threading.Lock()
  self.data={"a_records":[],"b_records":[],"a_events":[],"b_events":[],"dropdown_dismiss_count":0,"cross_role_pollution_hits":0}
 def save(self):
  self.state_path.parent.mkdir(parents=True,exist_ok=True);self.state_path.write_text(json.dumps(self.data,indent=2),encoding="utf-8")
 def export(self,role):
  folder=self.out/f"out_{role}";folder.mkdir(parents=True,exist_ok=True);name="crm_records.json" if role=="a" else "wiki_migrated.json";key="a_records" if role=="a" else "b_records"
  (folder/name).write_text(json.dumps(self.data[key],indent=2),encoding="utf-8")

def handler_for(state:State):
 class H(BaseHTTPRequestHandler):
  def log_message(self,*_):pass
  def _response(self,body:bytes,ctype="text/html; charset=utf-8",cookie=False,code=200):
   self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Cache-Control","no-store")
   if cookie:self.send_header("Set-Cookie",f"conc05_session={state.token}; HttpOnly; SameSite=Lax; Path=/")
   self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
  def _json(self,obj,code=200):self._response(json.dumps(obj).encode(),"application/json",code=code)
  def _authorized(self):
   # These local task pages are not login exercises. Allow first navigation
   # without a cookie; the browser may still receive one for compatibility.
   return True
  def _body(self):return json.loads(self.rfile.read(min(int(self.headers.get("Content-Length","0")),2000000)).decode())
  def do_GET(self):
   p=self.path.split("?",1)[0];port=self.server.server_port
   if p=="/health":return self._response(b"ok","text/plain")
   if not self._authorized():return self._response(b"authentication required","text/plain",code=401)
   if p.startswith("/assets/") and port==18101:
    name=Path(p).name
    if name in {f"application_{i:02d}.png" for i in range(1,5)}:
     f=state.assets/name
     if f.is_file():return self._response(f.read_bytes(),"image/png")
   if port==18101 and p=="/docs":
    cards="".join(f'<section class="card"><h2>Application {i}</h2><img src="/assets/application_{i:02d}.png" alt="Scanned client form {i}"></section>' for i in range(1,5))
    return self._response(DOCS_PAGE.replace("__IMAGES__",cards).encode(),cookie=True)
   if port==18101 and p=="/form":return self._response(FORM_PAGE.encode(),cookie=True)
   if port==18102 and p=="/legacy":
    docs="".join(f'<article class="sop"><h2>{x["id"]} · {x["title"]}</h2><span class="cat">{x["category"]}</span><pre>{x["code_block"]}</pre><p>{x["rules"][0]}</p><p>{x["rules"][1]}</p></article>' for x in SOPS)
    return self._response(LEGACY_PAGE.replace("__SOPS__",docs).encode(),cookie=True)
   if port==18102 and p=="/editor":
    opts="".join(f'<option>{x["id"]}</option>' for x in SOPS);cats="".join(f'<li><button data-cat="{x}">{x}</button></li>' for x in ("Networking","Database","Security","Storage"))
    page=EDITOR_PAGE.replace("__OPTIONS__",opts).replace("__CATS__",cats)
    return self._response(page.encode(),cookie=True)
   return self._response(b"not found","text/plain",code=404)
  def do_POST(self):
   if not self._authorized():return self._json({"error":"authentication required"},401)
   p=self.path.split("?",1)[0]
   try:d=self._body()
   except Exception:return self._json({"error":"invalid request"},400)
   with state.lock:
    if p=="/api/a/submit":
     state.data["a_records"].append(d);state.data["a_events"].append({"type":"client_submit","company_name":d.get("company_name")})
     state.save();return self._json({"ok":True,"count":len(state.data["a_records"])})
    if p=="/api/a/event":
     state.data["a_events"].append(d);state.save();return self._json({"ok":True})
    if p=="/api/a/export":state.export("a");state.save();return self._json({"ok":True})
    if p=="/api/b/event":
     state.data["b_events"].append(d)
     if d.get("type")=="dropdown_dismiss":state.data["dropdown_dismiss_count"]+=1
     state.save();return self._json({"ok":True})
    if p=="/api/b/publish":
     state.data["b_records"].append(d);state.data["b_events"].append({"type":"publish","id":d.get("id"),"category":d.get("category")})
     state.save();return self._json({"ok":True,"count":len(state.data["b_records"])})
    if p=="/api/b/export":state.export("b");state.save();return self._json({"ok":True})
   return self._json({"error":"not found"},404)
 return H

def serve(assets:Path,out:Path,state_path:Path):
 state=State(assets,out,state_path);handler=handler_for(state)
 servers=[ThreadingHTTPServer(("127.0.0.1",p),handler) for p in (18101,18102)]
 ts=[threading.Thread(target=s.serve_forever,daemon=True) for s in servers]
 [t.start() for t in ts];[t.join() for t in ts]

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--assets",type=Path,required=True);p.add_argument("--out",type=Path,default=Path("/home/user/workspace"));p.add_argument("--state",type=Path,default=Path("/tmp/conc05-runtime/state.json"));a=p.parse_args();serve(a.assets,a.out,a.state)

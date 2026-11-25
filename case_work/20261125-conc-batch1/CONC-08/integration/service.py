from __future__ import annotations
import argparse, base64, hashlib, html, json, os, secrets, shutil, subprocess, threading, time, zipfile
from xml.etree import ElementTree
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

LOCK=threading.RLock()

def initial():
    return {"records":{"a":[],"b":[]},"events":[],"finalized":{},"clipboard_hits":0,"sessions":{},"metrics":{"lock_appearance_events":0,"lock_file_samples":0,"lost_update_event":0,"office_focus_flips":0,"clipboard_cross_talk_hits":0,"telemetry_available":{}}}

class App(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):
        # Do not log submitted control codes or form values.
        print("%s - %s"%(self.log_date_time_string(),fmt%args),flush=True)
    def send(self,code,body,ctype="text/html; charset=utf-8",extra=()):
        self.send_response(code)
        self.send_header("Content-Type",ctype);self.send_header("Cache-Control","no-store")
        for k,v in extra:self.send_header(k,v)
        self.end_headers();self.wfile.write(body if isinstance(body,bytes) else body.encode("utf-8"))
    def _state(self):
        with LOCK:
            try:return json.loads(Path(self.server.state_path).read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError):return initial()
    def _save(self,state):
        with LOCK:
            p=Path(self.server.state_path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(".tmp")
            tmp.write_text(json.dumps(state,indent=2),encoding="utf-8");os.replace(tmp,p)
    def do_GET(self):
        u=urlparse(self.path);qs=parse_qs(u.query);actor=qs.get("actor",[getattr(self.server,"default_actor","a")])[0].lower()
        if u.path=="/health":return self.send(200,"ok","text/plain")
        if u.path=="/api/state":return self.send(200,json.dumps(self._state()),"application/json")
        if u.path not in ("/","/a","/b") or actor not in ("a","b"):return self.send(404,"not found")
        actor=("b" if u.path=="/b" else "a" if u.path=="/a" else actor)
        sid=secrets.token_urlsafe(18);st=self._state();st["sessions"][sid]=actor;self._save(st)
        is_a=actor=="a";name="FinAudit" if is_a else "HRDesk";title="Credit memo review" if is_a else "Approved allowance review"
        ids=[f"CM-{i:02d}" for i in range(1,5)] if is_a else [f"ALW-{i:02d}" for i in range(1,5)]
        options=("VAT","Excise","Sales Tax","Import Duty") if is_a else ("Engineering","Sales","Operations","People")
        field="Tax category" if is_a else "Department"
        forms=[]
        for i,doc in enumerate(ids,1):
            forms.append(f'''<section class="card"><h2>{html.escape(doc)} <span>Document {i} of 4</span></h2>
<form class="entry" data-id="{i}"><label>16-character verification code<input name="code" minlength="16" maxlength="20" required autocomplete="off"></label>
<label>Adjustment amount<input name="amount" inputmode="decimal" placeholder="0.00" required></label>
<label>{field}<select name="category" required><option value="">Choose {field.lower()}</option>{''.join(f'<option>{html.escape(x)}</option>' for x in options)}</select></label>
<label>Attach the matching signed PNG<input name="file" type="file" accept="image/png" required></label>
<button>Submit {html.escape(doc)}</button><output></output></form></section>''')
        style="""body{font-family:Arial,sans-serif;background:#edf2f7;color:#192a3a;margin:0}.bar{background:#173b63;color:white;padding:18px 5%;display:flex;justify-content:space-between}main{max-width:1020px;margin:25px auto;padding:0 18px}h1{margin:0 0 6px}.lead{color:#536579}.card{background:white;border:1px solid #cbd5e1;border-radius:12px;padding:20px;margin:16px 0;box-shadow:0 3px 12px #16345110}h2{font-size:19px;margin:0 0 16px}h2 span{float:right;color:#7a8998;font-size:13px;font-weight:normal}.entry{display:grid;grid-template-columns:1.3fr 1fr 1fr 1.4fr auto;gap:12px;align-items:end}label{font-size:12px;color:#596a7b;display:grid;gap:7px}input,select{box-sizing:border-box;width:100%;padding:10px 11px;border:1px solid #aebccc;border-radius:6px;background:#fff;color:#17293d}button{border:0;border-radius:6px;background:#176a5b;color:white;padding:11px 16px;font-weight:bold;cursor:pointer}output{grid-column:1/-1;color:#12614c;min-height:16px}.final{position:sticky;bottom:0;background:#edf2f7;padding:16px;text-align:right}#final{background:#173b63}@media(max-width:850px){.entry{grid-template-columns:1fr 1fr}.entry button{grid-column:1/-1}}"""
        script="""document.querySelectorAll('.entry').forEach(form=>form.addEventListener('submit',async e=>{e.preventDefault();let o=form.querySelector('output');o.textContent='Submitting securely...';let f=form.file.files[0];if(!f){o.textContent='Choose an attachment.';return}let b=await new Promise((res,rej)=>{let r=new FileReader();r.onload=()=>res(String(r.result).split(',')[1]);r.onerror=rej;r.readAsDataURL(f)});let body={actor:ACTOR,id:Number(form.dataset.id),code:form.code.value.trim(),amount:form.amount.value.trim(),category:form.category.value,file_name:f.name,file_b64:b};let r=await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let j=await r.json();o.textContent=r.ok?'Recorded: '+j.reference:j.error}));document.querySelector('#final').onclick=async()=>{let r=await fetch('/api/finalize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor:ACTOR})});let j=await r.json();document.querySelector('#final-out').textContent=r.ok?'Close code: '+j.close_code:j.error};""".replace("ACTOR",json.dumps(actor))
        page=f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>{name}</title><style>{style}</style></head><body><div class=bar><strong>{name} | Annual Close</strong><span>Secure local session</span></div><main><h1>{title}</h1><p class=lead>Enter each approved adjustment from its signed image, attach the exact source PNG, and reconcile the four records before closing the batch.</p>{''.join(forms)}<div class=final><button id=final>Finalize close batch</button><span id=final-out></span></div></main><script>{script}</script></body></html>"
        cookie_name="fin_session" if actor=="a" else "hr_session"
        return self.send(200,page,extra=(("Set-Cookie",f"{cookie_name}={sid}; HttpOnly; SameSite=Strict; Path=/"),))
    def do_POST(self):
        u=urlparse(self.path);n=int(self.headers.get("Content-Length","0"))
        if n<=0 or n>8_000_000:return self.send(413,'{"error":"Request size is not accepted."}',"application/json")
        try:data=json.loads(self.rfile.read(n))
        except (json.JSONDecodeError,UnicodeDecodeError):return self.send(400,'{"error":"Invalid request."}',"application/json")
        st=self._state();sid="";actor=str(data.get("actor",""));cookie_name="fin_session" if actor=="a" else "hr_session"
        for c in self.headers.get("Cookie","").split(";"):
            if c.strip().startswith(cookie_name+"="):sid=c.strip().split("=",1)[1]
        session_actor=st.get("sessions",{}).get(sid)
        if actor not in ("a","b") or session_actor!=actor:return self.send(403,json.dumps({"error":"Open the authorized role tab first."}),"application/json")
        if u.path=="/api/submit":
            try:
                idx=int(data.get("id"));code=str(data["code"]).strip();amount=float(data["amount"]);category=str(data["category"]).strip();raw=base64.b64decode(data["file_b64"],validate=True);fname=Path(str(data["file_name"])).name
                if idx<1 or idx>4 or len(code)<16 or amount<0 or not category or not raw.startswith(b"\x89PNG\r\n\x1a\n"):raise ValueError
            except (ValueError,KeyError,TypeError):return self.send(400,json.dumps({"error":"A code, positive amount, category, and PNG attachment are required."}),"application/json")
            sha=hashlib.sha256(raw).hexdigest();ref=f"{actor.upper()}-{idx}-{secrets.token_hex(3).upper()}"
            att=Path(self.server.attach_dir)/actor/f"{ref}.png";att.parent.mkdir(parents=True,exist_ok=True);att.write_bytes(raw)
            rec={"id":idx,"reference":ref,"code":code,"amount":round(amount,2),"category":category,"file_name":fname,"file_sha256":sha,"timestamp":time.time()}
            st["records"][actor]=[x for x in st["records"][actor] if x.get("id")!=idx]+[rec];st["events"].append({"event":"submitted","actor":actor,"id":idx,"sha256":sha,"timestamp":time.time()});self._save(st)
            return self.send(200,json.dumps({"ok":True,"reference":ref}),"application/json")
        if u.path=="/api/finalize":
            rec=st["records"].get(actor,[])
            if sorted(x.get("id") for x in rec)!=[1,2,3,4]:return self.send(409,json.dumps({"error":"Submit all four source documents first."}),"application/json")
            code=st["finalized"].get(actor)
            if not code:code=f"CLOSE-{actor.upper()}-{secrets.token_hex(4).upper()}";st["finalized"][actor]=code;st["events"].append({"event":"finalized","actor":actor,"timestamp":time.time()})
            self._save(st);return self.send(200,json.dumps({"ok":True,"close_code":code}),"application/json")
        return self.send(404,'{"error":"Not found."}',"application/json")

def _server(host,port,actor,assets,state):
    server=ThreadingHTTPServer((host,port),App);server.state_path=state;server.attach_dir=str(Path(assets)/"attachments");server.default_actor=actor;return server

def serve(host="127.0.0.1",port=18141,assets=".",state="/tmp/conc08-runtime/state.json"):
    Path(state).parent.mkdir(parents=True,exist_ok=True)
    if not Path(state).exists():Path(state).write_text(json.dumps(initial()),encoding="utf-8")
    App.server_version="FinAudit-HRDesk/1.0"
    a=_server(host,18141,"a",assets,state);b=_server(host,18142,"b",assets,state)
    threading.Thread(target=b.serve_forever,daemon=True).start();threading.Thread(target=_telemetry_loop,args=(state,"/home/user/workspace/shared/Corp_Annual_2026.xlsx"),daemon=True).start();print(f"CONC-08 services ready on {host}:18141 and {host}:18142",flush=True);a.serve_forever()

def _office_window():
    if not shutil.which("xprop"):return ""
    try:
        r=subprocess.run(["xprop","-root","_NET_ACTIVE_WINDOW"],capture_output=True,text=True,timeout=.5)
        wid=r.stdout.split()[-1]
        if wid in ("0x0","No","window"):return ""
        r=subprocess.run(["xprop","-id",wid,"WM_NAME","WM_CLASS"],capture_output=True,text=True,timeout=.5)
        return r.stdout.lower()
    except Exception:return ""

def _clipboard():
    if not shutil.which("xclip"):return None
    try:return subprocess.run(["xclip","-selection","clipboard","-o"],capture_output=True,text=True,timeout=.5).stdout
    except Exception:return None

def _sheet_names(book):
    try:
        with zipfile.ZipFile(book) as z:
            root=ElementTree.fromstring(z.read("xl/workbook.xml"));ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            return {x.attrib.get("name","") for x in root.findall(".//m:sheet",ns)}
    except Exception:return set()

def _telemetry_loop(state_path,workbook_path):
    """Sample lock, sheet-survival, desktop-focus and clipboard cross-talk metrics."""
    locks_before=set();focus_before=None;clip_hash=None;mtime=None;known_sheets={"Rev_Ledger","HR_Cost","FX_Tax_Rates"};last_sheet_names=set();seen_book=False
    while True:
        try:
            st=json.loads(Path(state_path).read_text(encoding="utf-8"));metrics=st.setdefault("metrics",initial()["metrics"])
            locks=set(str(p) for p in Path("/home/user/workspace/shared").glob(".~lock.*#"))
            metrics["lock_file_samples"]+=len(locks)
            metrics["lock_appearance_events"]+=len(locks-locks_before);locks_before=locks
            book=Path(workbook_path)
            if book.is_file():
                stat=book.stat()
                if mtime is None or stat.st_mtime_ns!=mtime:
                    names=_sheet_names(book)
                    if names:
                        if seen_book and known_sheets.issubset(last_sheet_names) and not known_sheets.issubset(names):metrics["lost_update_event"]+=1
                        if known_sheets.issubset(names):seen_book=True
                        last_sheet_names=names
                    mtime=stat.st_mtime_ns
            focus=_office_window()
            if focus:
                now_office=("libreoffice" in focus or "soffice" in focus)
                before_office=("libreoffice" in (focus_before or "") or "soffice" in (focus_before or ""))
                if focus_before is not None and now_office!=before_office:metrics["office_focus_flips"]+=1
                focus_before=focus
            clip=_clipboard()
            if clip is not None:
                wrong=None
                if "finaudit" in focus and "HRD-" in clip:wrong="a"
                elif "hrdesk" in focus and "FIN-" in clip:wrong="b"
                if wrong:
                    h=hashlib.sha256(clip.encode("utf-8",errors="replace")).hexdigest()
                    if h!=clip_hash:metrics["clipboard_cross_talk_hits"]+=1;clip_hash=h
                metrics["telemetry_available"]["clipboard"]=True
            else:metrics["telemetry_available"]["clipboard"]=False
            metrics["telemetry_available"]["window_focus"]=bool(focus)
            metrics["telemetry_available"]["workbook_watch"]=book.exists()
            with LOCK:
                fresh=json.loads(Path(state_path).read_text(encoding="utf-8"));fresh["metrics"]=metrics
                tmp=Path(state_path).with_suffix(".telemetry.tmp");tmp.write_text(json.dumps(fresh,indent=2),encoding="utf-8");os.replace(tmp,state_path)
        except Exception:pass
        time.sleep(2)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=18141);p.add_argument("--assets",default=".");p.add_argument("--state",default="/tmp/conc08-runtime/state.json");a=p.parse_args();serve(a.host,a.port,a.assets,a.state)

#!/usr/bin/env python3
"""Guest-local site activation workflow mock; synthetic data, loopback only."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import argparse, html, json, os, tempfile, threading
from typing import Any
from scripts import siteact_state_fixture_v1 as fx

class Store:
    def __init__(self,path:str|Path):
        self.path=Path(path);self.lock=threading.RLock();self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.exists(): self.data=json.loads(self.path.read_text())
        else:self.data=fx.new_state();self.save()
    def save(self):
        raw=json.dumps(self.data,sort_keys=True,indent=2)
        fd,tmp=tempfile.mkstemp(prefix=".siteact-",dir=str(self.path.parent))
        try:
            with os.fdopen(fd,"w") as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    def create_snapshot(self,values):
        with self.lock:
            fx.create_snapshot(self.data,values);self.save()
    def log_deviation(self,values):
        with self.lock:
            fx.log_deviation_and_hold(self.data,values.get("deviation_id",""),values.get("reason_code",""));self.save()
    def event_revalidated(self):
        with self.lock:
            self.data["events"].append({"action":"SNAPSHOT_REVALIDATED","revision":self.data["revision"]});self.save()

def e(x:Any)->str:return html.escape(str(x),quote=True)
def page(store:Store,section:str)->str:
    d=store.data;snap=d.get("snapshot");stale=bool(snap and not fx.snapshot_is_current(d))
    evidence="".join("<tr><td>"+e(x["kind"])+"</td><td>"+e(x["record_id"])+"</td><td>"+e(x["status"])+"</td><td>"+e(x["detail"])+"</td></tr>" for x in d["evidence"])
    issues="".join("<li>"+e(x["deviation_id"])+" — "+e(x["reason_code"])+" — "+e(x["summary"])+"</li>" for x in d["open_deviations"]) or "<li>None recorded</li>"
    snap_html=(f"<p><b>Last readiness snapshot:</b> {e(snap['status'])}, source revision {e(snap['source_revision'])} "
               f"({'STALE — revalidation required' if stale else 'CURRENT'})</p><pre>{e(json.dumps(snap,ensure_ascii=False,indent=2))}</pre>") if snap else "<p>No readiness snapshot yet.</p>"
    common=("""<!doctype html><html><head><meta charset='utf-8'><title>NE-14 Site Activation</title>
<style>body{font:18px Arial;margin:28px;max-width:1100px;color:#17202a}table{border-collapse:collapse;width:100%}td,th{border:1px solid #777;padding:8px;text-align:left}nav a,button{font-size:18px;margin:10px;padding:8px} .status{padding:10px;background:#e7f7e7}.warn{padding:10px;background:#fff1c2}</style></head><body>
<h1>Research Site Activation — NE-14</h1><nav><a href='/'>Dashboard</a><a href='/activation'>Readiness snapshot</a><a href='/deviation'>Deviation intake</a></nav>""")
    dashboard=("<div class='status'><b>Current site gate:</b> "+e(d["status"])+" &nbsp; <b>State revision:</b> "+str(d["revision"])+"</div>"
      "<h2>Current evidence register</h2><table><tr><th>Category</th><th>Reference</th><th>Status</th><th>Detail</th></tr>"+evidence+"</table>"
      "<h2>Open deviations</h2><ul>"+issues+"</ul><h2>Activation snapshot</h2>"+snap_html+
      ("<p class='warn'>A snapshot must match the latest site-gate revision before it is used for activation.</p>" if stale else "")+
      "<p>Local synthetic workflow only. No patient or real site data.</p>")
    if section=="activation":
      s=d["snapshot"] or {}
      form=("<h2>Review and save current readiness snapshot</h2><p>Source evidence is listed below. Record exact IDs and the current gate status.</p>"
        "<form method='post' action='/snapshot'>"
        "<label>Site <input name='site_id' value='"+e(d["site_id"])+"'></label><br>"
        "<label>Gate status <select name='status'><option "+("selected" if d["status"]=="READY" else "")+">READY</option><option "+("selected" if d["status"]=="HOLD" else "")+">HOLD</option></select></label><br>"
        "<label>Protocol ref <input name='protocol_id' value='"+e(s.get("protocol_id","PR-14-AMD-04"))+"'></label><br>"
        "<label>IRB ref <input name='irb_id' value='"+e(s.get("irb_id","IRB-NE14-221"))+"'></label><br>"
        "<label>Training record <input name='training_record_id' value='"+e(s.get("training_record_id","TRN-NE14-2026-10"))+"'></label><br>"
        "<label>Training complete <input name='training_complete' value='"+e(s.get("training_complete","4/4"))+"'></label><br>"
        "<label>Calibration cert <input name='calibration_id' value='"+e(s.get("calibration_id","CAL-55"))+"'></label><br>"
        "<button type='submit'>Save readiness snapshot</button></form>"
        "<form method='post' action='/revalidate'><button>Revalidate current snapshot</button></form>")
      return common+form+dashboard+"</body></html>"
    if section=="deviation":
      issue=fx.DEVIATION
      form=("<h2>New deviation intake</h2><p>Record the received notice, place the activation gate on HOLD, and notify the activation coordinator.</p>"
        "<form method='post' action='/deviation'>"
        "<label>Deviation ID <input name='deviation_id' value='"+e(issue["deviation_id"])+"'></label><br>"
        "<label>Reason code <input name='reason_code' value='"+e(issue["reason_code"])+"'></label><br>"
        "<button type='submit'>Record deviation and place site on HOLD</button></form>")
      return common+form+dashboard+"</body></html>"
    return common+dashboard+"</body></html>"

def make_handler(store:Store):
    class Handler(BaseHTTPRequestHandler):
        def respond(self,status,body,ctype="text/html; charset=utf-8"):
            raw=body.encode();self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            p=urlparse(self.path).path
            if p=="/health":return self.respond(200,'{"ok":true}',"application/json")
            if p=="/api/state":return self.respond(200,json.dumps(store.data,ensure_ascii=False),"application/json")
            if p=="/":return self.respond(200,page(store,"dashboard"))
            if p=="/activation":return self.respond(200,page(store,"activation"))
            if p=="/deviation":return self.respond(200,page(store,"deviation"))
            return self.respond(404,"not found")
        def do_POST(self):
            p=urlparse(self.path).path;n=int(self.headers.get("Content-Length","0"))
            q=parse_qs(self.rfile.read(n).decode(),keep_blank_values=True);v={k:x[-1] for k,x in q.items()}
            try:
                if p=="/snapshot":store.create_snapshot(v);dest="/activation"
                elif p=="/deviation":store.log_deviation(v);dest="/deviation"
                elif p=="/revalidate":store.create_snapshot({**fx.EXPECTED_HOLD_SNAPSHOT});store.event_revalidated();dest="/activation"
                else:return self.respond(404,"not found")
            except (ValueError,KeyError) as ex:return self.respond(400,json.dumps({"error":str(ex)}),"application/json")
            self.send_response(303);self.send_header("Location",dest);self.send_header("Content-Length","0");self.end_headers()
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);p.add_argument("--state",default="/tmp/siteact-state/state.json")
    a=p.parse_args();store=Store(a.state);server=ThreadingHTTPServer((a.host,a.port),make_handler(store));server.serve_forever()
if __name__=="__main__":main()

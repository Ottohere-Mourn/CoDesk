#!/usr/bin/env python3
"""PAY-1 run-local synthetic payroll workbench; not connected to payroll/bank services."""
from __future__ import annotations

APP_SERVER = r'''#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse, copy, json, threading, time

TASK_VERSION = "0.1.0-draft"
SOURCE_HASH = "__PAY1_SOURCE_HASH__"
EMPLOYEE_ID = "E-08"
WEEK_ID = "W19"
RATE_CENTS = 3200
INITIAL_HOURS = 80
CORRECTED_HOURS = 60
CORRECTION_ID = "COR-W19-E08"
SUPERVISOR_ID = "SUP-17"
INITIAL = {
    "fixture_version": TASK_VERSION,
    "source_fixture_sha256": SOURCE_HASH,
    "timecard": {"employee_id": EMPLOYEE_ID, "week_id": WEEK_ID,
                 "approved_hours_tenths": INITIAL_HOURS, "approved_by": SUPERVISOR_ID,
                 "correction_id": None},
    "payment_lines": [],
    "audit_log": [],
    "unrelated_guard": {"employee_id": "E-09", "week_id": WEEK_ID, "approved_hours_tenths": 72},
}
PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Payroll Close Desk</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef2f6;color:#182431;font:16px Arial,sans-serif}
header{height:62px;background:#173b5d;color:white;padding:18px 26px;font-size:22px;font-weight:bold}
main{max-width:1120px;margin:16px auto;padding:0 18px}.row{display:flex;gap:16px}.card{background:#fff;border:1px solid #c4ced9;border-radius:5px;padding:16px;margin-bottom:14px;flex:1}
h2{font-size:19px;margin:0 0 12px;color:#173b5d}.label{color:#465769}.big{font-size:25px;font-weight:bold;margin:8px 0}.muted{color:#5b6876;font-size:14px}
.banner{padding:10px 13px;background:#fff4d1;border:1px solid #e0c56e;margin:10px 0}
label{display:block;margin:9px 0 4px;font-weight:bold}input{font:18px Arial;padding:8px;border:1px solid #8494a5;width:150px}
button{font:16px Arial;padding:10px 14px;border:0;border-radius:3px;background:#176b48;color:white;cursor:pointer;margin:6px 6px 0 0}
button.secondary{background:#315d83}button.danger{background:#8e3940}table{width:100%;border-collapse:collapse;margin-top:8px}td,th{padding:7px 8px;border-bottom:1px solid #d6dde4;text-align:left}
#result{min-height:23px;color:#183c5d;font-weight:bold}.status{font-weight:bold}#source{background:#f6f8fa;padding:10px;margin:10px 0}
</style></head>
<body data-mode="__MODE__"><header>Payroll Close Desk — Weekly Batch W19</header>
<main>
<div class="row">
<section class="card" id="register"><h2>Approved Timecard</h2>
<div class="label">Employee E-08 · Week W19 · Supervisor SUP-17</div>
<div class="big">Approved hours: <span id="approved">…</span></div>
<div class="label">Correction reference: <span id="correction">None</span></div>
<button class="secondary" id="refresh">Refresh approved timecard</button>
<div id="status" class="status"></div></section>
<section class="card" id="clerk"><h2>Payroll Clerk · Build payment line</h2>
<div class="banner">Payment lines are point-in-time batch snapshots. Verify the current approved timecard before release.</div>
<label for="hours">Hours for E-08 / W19</label><input id="hours" type="number" min="0" max="120" step="0.1">
<div class="label">Rate: $32.00 / hour · Amount: <b id="amount">$0.00</b></div>
<button id="submit">Add line to payroll batch</button></section>
</div>
<div class="row">
<section class="card" id="supervisor"><h2>Supervisor · Authorized correction</h2>
<div id="source">__SOURCE__</div><div class="label">This updates the approved timecard record, not an existing payment snapshot.</div>
<button id="correct">Apply signed correction</button></section>
<section class="card" id="batch"><h2>Payroll batch lines</h2><div id="lines">No lines</div></section>
</div>
<div class="card"><h2>Activity</h2><div id="result"></div><div id="activity" class="muted"></div></div>
</main>
<script>
const mode=document.body.dataset.mode;
if(mode!=="supervisor")document.getElementById("supervisor").style.display="none";
if(mode!=="clerk")document.getElementById("clerk").style.display="none";
let initialized=false;
async function post(path,obj){const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj)});const j=await r.json();if(!r.ok)throw new Error(j.error||"request failed");return j}
function money(hours){return "$"+(Number(hours)*32).toFixed(2)}
document.getElementById("hours").addEventListener("input",e=>document.getElementById("amount").textContent=money(e.target.value));
async function refresh(source){
 const s=await fetch("/api/state",{cache:"no-store"}).then(r=>r.json());
 document.getElementById("approved").textContent=(s.timecard.approved_hours_tenths/10).toFixed(1)+" h";
 document.getElementById("correction").textContent=s.timecard.correction_id||"None";
 document.getElementById("status").textContent=s.timecard.approved_hours_tenths===60?"Approved record corrected to 6.0 h.":"Timecard unchanged.";
 if(!initialized){document.getElementById("hours").value=(s.timecard.approved_hours_tenths/10).toFixed(1);document.getElementById("amount").textContent=money(s.timecard.approved_hours_tenths/10);initialized=true}
 const rows=s.payment_lines||[];
 document.getElementById("lines").innerHTML=rows.length?("<table><tr><th>ID</th><th>Hours</th><th>Amount</th><th>Status</th><th>Action</th></tr>"+rows.map(r=>"<tr><td>"+r.payment_id+"</td><td>"+(r.hours_tenths/10).toFixed(1)+"</td><td>"+money(r.hours_tenths/10)+"</td><td>"+r.status+"</td><td>"+(r.status==="submitted"?"<button class='danger' data-void='"+r.payment_id+"'>Void line</button>":"—")+"</td></tr>").join("")+"</table>"):"No lines";
 document.getElementById("activity").textContent="Updated "+new Date().toLocaleTimeString()+" · "+(source||"refresh");
 document.querySelectorAll("button[data-void]").forEach(b=>b.onclick=async()=>{try{await post("/api/void",{actor:"A",payment_id:b.dataset.void});document.getElementById("result").textContent="Line voided with audit record.";await refresh("void")}catch(e){document.getElementById("result").textContent=e.message}});
}
document.getElementById("refresh").onclick=()=>refresh("manual refresh");
document.getElementById("submit").onclick=async()=>{try{const h=Math.round(Number(document.getElementById("hours").value)*10);const s=await post("/api/payment",{actor:"A",hours_tenths:h,ui_observed_hours_tenths:Math.round(parseFloat(document.getElementById("approved").textContent)*10)||80});document.getElementById("result").textContent=s.message;await refresh("payment line created")}catch(e){document.getElementById("result").textContent=e.message}};
document.getElementById("correct").onclick=async()=>{try{const s=await post("/api/correction",{actor:"B"});document.getElementById("result").textContent=s.message;await refresh("correction applied")}catch(e){document.getElementById("result").textContent=e.message}};
refresh("page load");
setInterval(()=>refresh("live register refresh"),1200);
</script></body></html>"""

class State:
    def __init__(self, path):
        self.path=Path(path)
        self.lock=threading.RLock()
        self.data=copy.deepcopy(INITIAL)
        self.observations=[]
        self.flush()
    def flush(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"business":self.data,"observations":self.observations},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(self.path)
    def record(self,event):
        row={"time_unix":time.time(),**event}
        self.observations.append(row)
        self.flush()

class Handler(BaseHTTPRequestHandler):
    state=None
    def log_message(self,*args):pass
    def send_obj(self,code,obj,ctype="application/json; charset=utf-8"):
        body=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(body)
    def body(self):
        n=int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        if self.path=="/health":return self.send_obj(200,{"ok":True,"loopback_only":True,"task_version":TASK_VERSION})
        if self.path.startswith("/api/state"):
            with self.state.lock:return self.send_obj(200,{**self.state.data,"observations":self.state.observations})
        if self.path=="/case/clerk":return self.send_obj(200,PAGE.replace("__MODE__","clerk").replace("__SOURCE__","").encode(), "text/html; charset=utf-8")
        if self.path=="/case/supervisor":
            source="Signed correction COR-W19-E08 ? E-08 / W19 ? change approved hours from 8.0 to 6.0 ? authorized by SUP-17 ? reason: unapproved overtime removed."
            return self.send_obj(200,PAGE.replace("__MODE__","supervisor").replace("__SOURCE__",source).encode(), "text/html; charset=utf-8")
        return self.send_obj(404,{"error":"not found"})
    def do_POST(self):
        try: obj=self.body()
        except Exception:return self.send_obj(400,{"error":"invalid JSON"})
        with self.state.lock:
            if self.path=="/api/reset":
                self.state.data=copy.deepcopy(INITIAL);self.state.observations=[]
                self.state.flush();return self.send_obj(200,{"ok":True})
            if self.path=="/api/correction":
                if obj.get("actor")!="B":return self.send_obj(403,{"error":"correction action must be actor B"})
                card=self.state.data["timecard"]
                if card["correction_id"] is not None:return self.send_obj(409,{"error":"correction already applied"})
                before=card["approved_hours_tenths"]
                card["approved_hours_tenths"]=CORRECTED_HOURS
                card["correction_id"]=CORRECTION_ID
                self.state.data["audit_log"].append({"actor":"B","action":"approved_hours_corrected","employee_id":EMPLOYEE_ID,"week_id":WEEK_ID,"old_hours_tenths":before,"new_hours_tenths":CORRECTED_HOURS,"correction_id":CORRECTION_ID,"authorized_by":SUPERVISOR_ID,"reason_code":"UNAPPROVED_OVERTIME_REMOVED"})
                self.state.record({"kind":"timecard-correction","actor":"B","employee_id":EMPLOYEE_ID,"week_id":WEEK_ID,"old_hours_tenths":before,"new_hours_tenths":CORRECTED_HOURS,"correction_id":CORRECTION_ID})
                return self.send_obj(200,{"ok":True,"message":"Approved timecard updated to 6.0 h."})
            if self.path=="/api/payment":
                if obj.get("actor")!="A":return self.send_obj(403,{"error":"payment action must be actor A"})
                try:h=int(obj["hours_tenths"])
                except Exception:return self.send_obj(400,{"error":"hours_tenths must be an integer"})
                if h<0 or h>1200:return self.send_obj(400,{"error":"hours outside allowed range"})
                rows=self.state.data["payment_lines"]
                payment_id="PAY-"+WEEK_ID+"-"+EMPLOYEE_ID+"-"+format(len(rows)+1,"02d")
                amount=RATE_CENTS*h//10
                row={"payment_id":payment_id,"employee_id":EMPLOYEE_ID,"week_id":WEEK_ID,"hours_tenths":h,"rate_cents_per_hour":RATE_CENTS,"amount_cents":amount,"status":"submitted","actor":"A","ui_observed_hours_tenths":obj.get("ui_observed_hours_tenths"),"approved_hours_at_submit":self.state.data["timecard"]["approved_hours_tenths"]}
                rows.append(row)
                self.state.record({"kind":"payment-snapshot-created","actor":"A","payment_id":payment_id,"submitted_hours_tenths":h,"approved_hours_at_submit":self.state.data["timecard"]["approved_hours_tenths"],"amount_cents":amount})
                return self.send_obj(200,{"ok":True,"payment_id":payment_id,"message":"Payment snapshot added to the batch."})
            if self.path=="/api/void":
                if obj.get("actor")!="A":return self.send_obj(403,{"error":"void action must be actor A"})
                pid=str(obj.get("payment_id",""))
                matches=[r for r in self.state.data["payment_lines"] if r.get("payment_id")==pid]
                if len(matches)!=1 or matches[0].get("actor")!="A" or matches[0].get("status")!="submitted":return self.send_obj(409,{"error":"payment line is missing, ambiguous, or not active"})
                matches[0]["status"]="voided"
                self.state.data["audit_log"].append({"actor":"A","action":"payment_voided","payment_id":pid})
                self.state.record({"kind":"payment-voided","actor":"A","payment_id":pid})
                return self.send_obj(200,{"ok":True,"message":"Line voided with audit record."})
            if self.path=="/api/observe":
                self.state.record({"kind":"ui-observation",**obj})
                return self.send_obj(200,{"ok":True})
        return self.send_obj(404,{"error":"not found"})
def main():
    p=argparse.ArgumentParser();p.add_argument("--state",required=True);p.add_argument("--port",type=int,default=8785);a=p.parse_args()
    Handler.state=State(a.state);ThreadingHTTPServer(("127.0.0.1",a.port),Handler).serve_forever()
if __name__=="__main__":main()
'''

SERVER_PATH = "/tmp/codesk-pay1/pay1_server.py"
STATE_PATH = "/tmp/codesk-pay1/state.json"
PORT = 8785
ROUTES = {"clerk": f"http://127.0.0.1:{PORT}/case/clerk",
          "supervisor": f"http://127.0.0.1:{PORT}/case/supervisor"}

def server_text(source_hash: str) -> str:
    if len(source_hash) != 64:
        raise ValueError("source_hash must be a SHA-256 hex digest")
    return APP_SERVER.replace("__PAY1_SOURCE_HASH__", source_hash)

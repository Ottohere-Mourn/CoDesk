from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

def connect(db):
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row; return conn


def _csv_rows(path):
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def init_db(path, root):
    conn = connect(path)
    conn.executescript("DROP TABLE IF EXISTS inbound; DROP TABLE IF EXISTS outbound; DROP TABLE IF EXISTS bins; DROP TABLE IF EXISTS customs_overrides; DROP TABLE IF EXISTS tokens; DROP TABLE IF EXISTS actions;"
        "CREATE TABLE inbound(order_id TEXT PRIMARY KEY,damage_flag INTEGER,temperature_c REAL,qty INTEGER,status TEXT,bin_code TEXT,storage_class TEXT);"
        "CREATE TABLE outbound(order_id TEXT PRIMARY KEY,credit_hold INTEGER,qa_status TEXT,customs_code TEXT,status TEXT,override_code TEXT);"
        "CREATE TABLE bins(bin_code TEXT PRIMARY KEY,storage_class TEXT,capacity INTEGER,occupied INTEGER,overflow INTEGER);"
        "CREATE TABLE customs_overrides(order_id TEXT PRIMARY KEY,override_code TEXT,approval_reason TEXT);"
        "CREATE TABLE tokens(token TEXT PRIMARY KEY,kind TEXT,order_ids TEXT,conflicts_json TEXT,used INTEGER DEFAULT 0);"
        "CREATE TABLE actions(action_id INTEGER PRIMARY KEY,kind TEXT,token TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,detail_json TEXT);")
    for row in _csv_rows(Path(root)/"inbound_manifest.csv"):
        conn.execute("INSERT INTO inbound VALUES(?,?,?,?,?,?,?)",(row["order_id"],int(row["damage_flag"]),float(row["temperature_c"]),int(row["qty"]),"PENDING",row["primary_bin"],row["storage_class"]))
    for row in _csv_rows(Path(root)/"outbound_orders.csv"):
        conn.execute("INSERT INTO outbound VALUES(?,?,?,?,?,?)",(row["order_id"],int(row["credit_hold"]),row["qa_status"],row["customs_code"],"PENDING",""))
    for row in _csv_rows(Path(root)/"bins.csv"):
        conn.execute("INSERT INTO bins VALUES(?,?,?,?,?)",(row["bin_code"],row["storage_class"],int(row["capacity"]),int(row["occupied"]),int(row["overflow"])))
    for row in _csv_rows(Path(root)/"customs_overrides.csv"):
        conn.execute("INSERT INTO customs_overrides VALUES(?,?,?)",(row["order_id"],row["override_code"],row["approval_reason"]))
    conn.commit(); conn.close()


class App:
    def __init__(self, root): self.root = Path(root); self.db = self.root / "rooms.db"
    def state(self):
        c=connect(self.db)
        try:
            return {"inbound": [dict(x) for x in c.execute("SELECT * FROM inbound ORDER BY order_id")],
                    "outbound": [dict(x) for x in c.execute("SELECT * FROM outbound ORDER BY order_id")],
                    "bins": [dict(x) for x in c.execute("SELECT * FROM bins ORDER BY bin_code")]}
        finally: c.close()
    def phase1(self, kind, ids):
        if kind not in {"inbound", "outbound"} or not isinstance(ids,list) or not ids or len(ids)>30 or len(set(ids))!=len(ids): raise ValueError("Choose a valid order batch")
        table = kind
        c=connect(self.db)
        try:
            wanted = set(ids)
            rows = [dict(r) for r in c.execute(f"SELECT * FROM {table} WHERE order_id IN ({','.join('?' for _ in wanted)})", list(wanted))]
            if len(rows) != len(wanted): raise ValueError("Unknown or duplicate order ID")
            conflicts = []
            if kind == "inbound":
                conflict_ids=set()
                for item in rows:
                    if item["damage_flag"] or not 2 <= item["temperature_c"] <= 8:
                        raise ValueError("Batch contains an inbound order that fails handling eligibility")
                    binrow=c.execute("SELECT * FROM bins WHERE bin_code=?",(item["bin_code"],)).fetchone()
                    if not binrow: raise ValueError("Primary bin reference is missing")
                    staged=sum(x["qty"] for x in rows if x["bin_code"]==item["bin_code"])
                    if binrow["occupied"]+staged>binrow["capacity"]:
                        overflow=c.execute("SELECT bin_code FROM bins WHERE storage_class=? AND overflow=1 AND capacity-occupied>=? ORDER BY bin_code LIMIT 1",(item["storage_class"],item["qty"])).fetchone()
                        if not overflow: raise ValueError("No approved overflow bin has sufficient safe capacity")
                        if item["order_id"] not in conflict_ids:
                            conflict_ids.add(item["order_id"])
                            conflicts.append({"order_id":item["order_id"],"code":"BIN_FULL","message":"Primary bin is at safe capacity; use an approved overflow location from the handling rules."})
            else:
                for item in rows:
                    if item["credit_hold"] or item["qa_status"]!="PASS": raise ValueError("Batch contains a held or failed-QA order")
                    if item["customs_code"]!="CUS-OK":
                        approval=c.execute("SELECT override_code FROM customs_overrides WHERE order_id=?",(item["order_id"],)).fetchone()
                        conflicts.append({"order_id":item["order_id"],"code":"CUSTOMS_MISMATCH","message":"Approved override evidence is required.","override_required":bool(approval)})
            token=uuid.uuid4().hex
            c.execute("INSERT INTO tokens(token,kind,order_ids,conflicts_json) VALUES(?,?,?,?)",(token,kind,json.dumps(sorted(wanted)),json.dumps(conflicts)))
            c.execute("INSERT INTO actions(kind,token,detail_json) VALUES(?,?,?)",(kind+"_phase1",token,json.dumps({"ids":sorted(wanted),"conflicts":conflicts})))
            c.commit(); return {"token":token,"conflicts":conflicts,"selected_count":len(rows)}
        finally: c.close()
    def phase2(self, kind, token, assignments=None, override_codes=None):
        c=connect(self.db)
        try:
            row=c.execute("SELECT * FROM tokens WHERE token=? AND used=0",(token,)).fetchone()
            if not row or row["kind"]!=kind: raise ValueError("Token is missing, expired, or has the wrong operation scope")
            ids=json.loads(row["order_ids"]); conflicts=json.loads(row["conflicts_json"])
            if kind=="inbound":
                assignments=assignments or {}; expected={oid:c.execute("SELECT bin_code FROM inbound WHERE order_id=?",(oid,)).fetchone()["bin_code"] for oid in ids}
                for conflict in conflicts:
                    item=c.execute("SELECT storage_class,qty FROM inbound WHERE order_id=?",(conflict["order_id"],)).fetchone()
                    overflow=c.execute("SELECT bin_code FROM bins WHERE storage_class=? AND overflow=1 AND capacity-occupied>=? ORDER BY bin_code LIMIT 1",(item["storage_class"],item["qty"])).fetchone()
                    if not overflow: raise ValueError("No overflow bin can safely accept the staged order")
                    expected[conflict["order_id"]]=overflow["bin_code"]
                if assignments != expected: raise ValueError("Final bins do not satisfy the safe-capacity routing rules")
                for oid,bin_code in expected.items(): c.execute("UPDATE inbound SET status='RECEIVED',bin_code=? WHERE order_id=?",(bin_code,oid))
                output=[]
                for oid in ids: output.append({"order_id":oid,"bin_code":expected[oid],"reassigned":oid in {x["order_id"] for x in conflicts},"status":"RECEIVED"})
                outpath=self.root / "inbound_audit.json"; key="allocation_token"
            else:
                override_codes=override_codes or {}; expected={}
                for x in conflicts:
                    approval=c.execute("SELECT override_code FROM customs_overrides WHERE order_id=?",(x["order_id"],)).fetchone()
                    if not approval: raise ValueError("No approved override is on file for this mismatch")
                    expected[x["order_id"]]=approval["override_code"]
                if override_codes != expected: raise ValueError("Customs override codes do not match approved evidence")
                for oid in ids: c.execute("UPDATE outbound SET status='RELEASED',override_code=? WHERE order_id=?",(expected.get(oid,""),oid))
                output=[]
                for oid in ids: output.append({"order_id":oid,"override_code":expected.get(oid,""),"status":"RELEASED"})
                outpath=self.root / "outbound_audit.json"; key="release_token"
            c.execute("UPDATE tokens SET used=1 WHERE token=?",(token,))
            c.execute("INSERT INTO actions(kind,token,detail_json) VALUES(?,?,?)",(kind+"_phase2",token,json.dumps({"rows":output})))
            c.commit(); outpath.write_text(json.dumps({"schema":"dispatch-audit/v1",key:token,"rows":output,"status":"committed"},indent=2)+"\n",encoding="utf-8")
            return {"status":"committed","count":len(output),"rows":output}
        finally:c.close()


PAGE = r'''<!doctype html><meta charset="utf-8"><title>North Depot Dispatch Console</title>
<style>body{font:14px Arial;margin:20px;color:#183047}nav button{margin-right:8px;padding:10px}table{border-collapse:collapse;width:100%;margin-top:12px}td,th{border:1px solid #ccd4dc;padding:6px}main{max-width:1100px}.warn{color:#9b4510}#msg{white-space:pre-wrap;background:#f3f6f8;padding:10px}label{margin-right:8px}</style>
<main><h1>North Depot Dispatch Console</h1><nav><button onclick="changeView('inbound')">Inbound</button><button onclick="changeView('outbound')">Outbound</button></nav><p id="hint">Filter records, stage an eligible batch, review the phase-one response, then finalize.</p><label>Search <input id="q" oninput="draw()"></label><button onclick="reload()">Refresh board</button><div id="rows"></div><p><button onclick="phase1()">Run phase-one check</button><button onclick="phase2()">Finalize selected batch</button></p><div id="msg"></div></main>
<script>
let view='inbound',state={},selected=new Set(JSON.parse(localStorage.getItem('dispatch-selected')||'[]')),token='',conflicts=[];const bc=new BroadcastChannel('dispatch_console_sync');
bc.onmessage=e=>{if(e.data&&e.data.type==='view'){view=e.data.view;draw()}};
function changeView(v){view=v;bc.postMessage({type:'view',view});draw()}
async function reload(){state=await (await fetch('/api/state')).json();draw()}
function draw(){let rows=state[view]||[];let q=(document.getElementById('q')?.value||'').toLowerCase();rows=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q));document.getElementById('rows').innerHTML='<table><thead><tr><th>Stage</th>'+Object.keys(rows[0]||{}).filter(k=>k!=='order_id').map(k=>'<th>'+k+'</th>').join('')+'<th>order_id</th></tr></thead><tbody>'+rows.map(r=>'<tr><td><input type="checkbox" value="'+r.order_id+'" '+(selected.has(r.order_id)?'checked':'')+' onchange="toggle(\''+r.order_id+'\',this.checked)"></td>'+Object.keys(r).filter(k=>k!=='order_id').map(k=>'<td>'+r[k]+'</td>').join('')+'<td>'+r.order_id+'</td></tr>').join('')+'</tbody></table>';localStorage.setItem('dispatch-selected',JSON.stringify([...selected]))}
function toggle(id,on){on?selected.add(id):selected.delete(id);localStorage.setItem('dispatch-selected',JSON.stringify([...selected]));bc.postMessage({type:'selection',ids:[...selected]})}
async function phase1(){let ids=[...selected];let r=await fetch('/api/phase1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:view,ids})});let d=await r.json();if(!r.ok){msg(d.error);return}token=d.token;conflicts=d.conflicts;document.getElementById('msg').textContent='Phase 1 token: '+token+'\nConflicts: '+JSON.stringify(conflicts,null,2);}
async function phase2(){if(!token){msg('Run phase one first to obtain a token.');return}let ids=JSON.parse(localStorage.getItem('dispatch-selected')||'[]');let body={kind:view,token};if(view==='inbound'){body.assignments={};for(let id of ids){let c=conflicts.find(x=>x.order_id===id);body.assignments[id]=c?prompt('Approved overflow bin for '+id+' (consult warehouse_rules.pdf):'):(state.inbound.find(x=>x.order_id===id)||{}).bin_code}}else{body.override_codes={};for(let c of conflicts){body.override_codes[c.order_id]=prompt('Approved override code for '+c.order_id+' (consult customs_overrides.csv):')}}let r=await fetch('/api/phase2',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let d=await r.json();msg(JSON.stringify(d,null,2));if(r.ok){selected.clear();token='';conflicts=[];await reload()}}
function msg(s){document.getElementById('msg').textContent=String(s)}reload();
</script>'''


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,obj,kind="application/json"):
            data=obj.encode() if isinstance(obj,str) else json.dumps(obj).encode(); self.send_response(status);self.send_header("Content-Type",kind+"; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if self.path=="/":return self.send(200,PAGE,"text/html")
            if self.path=="/api/state":return self.send(200,app.state())
            if self.path=="/api/receipt":return self.send(200,{"schema":"dispatch-receipt/v1","state":app.state()})
            return self.send(404,{"error":"not_found"})
        def do_POST(self):
            try:
                size=int(self.headers.get("Content-Length","0"));
                if size>200000:raise ValueError("request too large")
                data=json.loads(self.rfile.read(size) or b"{}")
                if self.path=="/api/phase1":return self.send(200,app.phase1(data.get("kind"),data.get("ids")))
                if self.path=="/api/phase2":return self.send(200,app.phase2(data.get("kind"),data.get("token"),data.get("assignments"),data.get("override_codes")))
                return self.send(404,{"error":"not_found"})
            except (ValueError,KeyError,json.JSONDecodeError) as e:return self.send(400,{"error":str(e)})
        def log_message(self,*_):pass
    return Handler


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--port",type=int,default=8092);a=p.parse_args()
    root=Path(a.workspace).expanduser().resolve()/"dispatch";init_db(root/"rooms.db",root);ThreadingHTTPServer(("127.0.0.1",a.port),handler_for(App(root))).serve_forever()

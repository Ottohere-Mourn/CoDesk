"""English-only ProcureHub receipt-review service for CONC-03."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import secrets
import threading
import time
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


CLAIMS = [
    {"claim_id": "EXP-401", "amount": "$420.00", "merchant": "Harbor & Pine Conference Center", "date": "Nov 18, 2026"},
    {"claim_id": "EXP-402", "amount": "$315.00", "merchant": "Harbor & Pine Conference Center", "date": "Nov 18, 2026"},
    {"claim_id": "EXP-403", "amount": "$185.00", "merchant": "Northstar Transit and Dining", "date": "Nov 19, 2026"},
]
STATE = Path("/tmp/conc03-runtime/state.json")
UPLOADS = Path("/tmp/conc03-runtime/uploads")
LOCK = threading.RLock()
SESSION = secrets.token_urlsafe(24)


def _fresh_state():
    return {"a_records": [], "events": [], "popover_dismiss_count": 0,
            "claims": {c["claim_id"]: {"status": "PENDING", "reason_code": "", "uploaded_filename": "", "sha256": ""} for c in CLAIMS}}


def _read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _fresh_state()


def _write_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def _authorized(handler):
    return f"session={SESSION}" in handler.headers.get("Cookie", "")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProcureHub | Expense Review</title><style>
:root{font-family:Inter,"Segoe UI",sans-serif;color:#1d2c3a;background:#f3f6f9}*{box-sizing:border-box}body{margin:0}
header{background:#16324f;color:white;padding:20px 5vw;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px #17344a22}
.brand{font-size:20px;font-weight:800;letter-spacing:.04em}.badge{font-size:12px;background:#d7f2e8;color:#126849;padding:7px 11px;border-radius:20px;font-weight:700}
main{max-width:1160px;margin:38px auto;padding:0 24px}.intro h1{font-size:30px;margin:0 0 8px}.intro p{color:#607080;margin:0 0 24px}
.panel{background:white;border:1px solid #dce4eb;border-radius:16px;box-shadow:0 12px 35px #1939550a;overflow:visible}
table{border-collapse:collapse;width:100%}th{text-align:left;font-size:12px;color:#637688;text-transform:uppercase;letter-spacing:.08em;background:#f8fafc;padding:16px 18px;border-bottom:1px solid #e4eaf0}
td{padding:19px 18px;border-bottom:1px solid #edf1f4;font-size:14px}tr:last-child td{border-bottom:0}.claim{font-weight:800;color:#173b57}.amount{font-weight:700;font-variant-numeric:tabular-nums}
.status{display:inline-flex;border-radius:20px;padding:6px 10px;background:#eef2f5;color:#64717e;font-size:11px;font-weight:800}.status.done{background:#e1f3eb;color:#126849}
.menu-wrap{position:relative}.menu-btn,.export{border:0;border-radius:8px;padding:10px 14px;background:#1e6b72;color:white;font-weight:700;cursor:pointer}.menu-btn:hover,.export:hover{background:#174f56}
.menu{position:absolute;right:0;top:44px;z-index:20;width:265px;padding:14px;background:white;border:1px solid #d5dfe7;border-radius:12px;box-shadow:0 18px 44px #0c25342e}.menu[hidden]{display:none}
.menu label{display:block;font-size:12px;color:#526678;font-weight:700;margin:3px 0 6px}.menu input[type=file]{font-size:12px;width:100%;margin:0 0 12px}.menu select,.menu input[type=text]{width:100%;padding:9px;border:1px solid #ccd7df;border-radius:7px;margin:0 0 10px;background:white}.menu .submit{width:100%;padding:10px;border:0;border-radius:7px;background:#193e5c;color:white;font-weight:700;cursor:pointer}.menu .submit:disabled{background:#a8b7c2;cursor:not-allowed}
.bottom{display:flex;justify-content:space-between;align-items:center;padding:18px;border-top:1px solid #edf1f4;color:#718090;font-size:12px}.notice{min-height:20px;color:#9b3b30;font-weight:700}
</style></head><body><header><div class="brand">PROCUREHUB <span style="font-weight:400;color:#bfd1df">/ Finance Operations</span></div><div class="badge">Signed in · Review queue</div></header>
<main><section class="intro"><h1>Expense Approval Queue</h1><p>Review the supporting receipt, attach the original file, and record a decision for each claim.</p></section>
<section class="panel"><table><thead><tr><th>Claim</th><th>Merchant</th><th>Submitted</th><th>Declared total</th><th>Status</th><th>Action</th></tr></thead><tbody id="claims"></tbody></table>
<div class="bottom"><div><div class="notice" id="notice"></div><span>Three claims · Attachments are retained with the approval record.</span></div><a id="export" class="export" href="/export.csv">Export Approval CSV</a></div></section></main>
<script>
let claims=[]; let activeMenu=null;
async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}
function el(tag,cls,text){const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x}
function render(){const body=document.querySelector('#claims');body.replaceChildren();for(const c of claims){const tr=el('tr');
let td=el('td');td.append(el('span','claim',c.claim_id));tr.append(td);tr.append(el('td','',c.merchant));tr.append(el('td','',c.date));tr.append(el('td','amount',c.amount));
td=el('td');td.append(el('span','status'+(c.status==='PENDING'?'':' done'),c.status));tr.append(td);td=el('td');const wrap=el('div','menu-wrap');const button=el('button','menu-btn',c.status==='PENDING'?'Review claim':'Reviewed');button.type='button';button.addEventListener('click',()=>toggleMenu(c.claim_id));wrap.append(button);
const menu=el('div','menu');menu.id='menu-'+c.claim_id;menu.hidden=true;menu.addEventListener('click',e=>e.stopPropagation());
const fl=el('label','', 'Upload receipt image');const file=el('input');file.type='file';file.accept='image/png';file.id='file-'+c.claim_id;file.addEventListener('change',()=>upload(c.claim_id,file.files[0]));menu.append(fl,file);
const dl=el('label','','Decision');const select=el('select');select.id='decision-'+c.claim_id;for(const [v,t] of [['APPROVED','Approve'],['REJECTED','Reject']]){const o=el('option','',t);o.value=v;select.append(o)}menu.append(dl,select);
const rl=el('label','','Reason code (required for rejection)');const reason=el('input');reason.type='text';reason.id='reason-'+c.claim_id;reason.placeholder='e.g. ERR_AMOUNT_MISMATCH';menu.append(rl,reason);
const submit=el('button','submit','Submit decision');submit.type='button';submit.disabled=!c.uploaded;submit.addEventListener('click',()=>submitDecision(c.claim_id));menu.append(submit);wrap.append(menu);td.append(wrap);tr.append(td);body.append(tr)}
const ready=claims.length===3&&claims.every(c=>c.status!=='PENDING');document.querySelector('#export').style.opacity=ready?'1':'.45';document.querySelector('#export').setAttribute('aria-disabled',String(!ready));}
async function refresh(){const r=await fetch('/api/state');if(!r.ok)return;const j=await r.json();claims=j.claims;render()}
function toggleMenu(id){const m=document.querySelector('#menu-'+id);if(activeMenu&&activeMenu!==m)activeMenu.hidden=true;m.hidden=!m.hidden;activeMenu=m.hidden?null:m;if(!m.hidden)api('/api/event',{type:'menu_open',claim_id:id}).catch(()=>{})}
function closeMenu(reason){if(!activeMenu||activeMenu.hidden)return;const id=activeMenu.id.replace('menu-','');activeMenu.hidden=true;activeMenu=null;api('/api/event',{type:'menu_dismiss',claim_id:id,reason}).catch(()=>{})}
window.addEventListener('blur',()=>closeMenu('window_blur'));document.addEventListener('visibilitychange',()=>{if(document.hidden)closeMenu('document_hidden')});
document.addEventListener('click',()=>closeMenu('outside_click'));
async function upload(id,file){if(!file)return;const data=new FormData();data.append('claim_id',id);data.append('receipt',file,file.name);try{const r=await fetch('/api/upload',{method:'POST',body:data});const j=await r.json();if(!r.ok)throw Error(j.error||'Upload failed');document.querySelector('#notice').textContent='Receipt attached for '+id+'.';await refresh();}catch(e){document.querySelector('#notice').textContent=e.message}}
async function submitDecision(id){const status=document.querySelector('#decision-'+id).value;const reason=document.querySelector('#reason-'+id).value.trim();try{await api('/api/decision',{claim_id:id,status,reason_code:reason});document.querySelector('#notice').textContent='Decision recorded for '+id+'.';await refresh()}catch(e){document.querySelector('#notice').textContent=e.message}}
refresh();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ProcureHub/1.0"

    def log_message(self, fmt, *args):
        return

    def _send(self, status, body=b"", content_type="application/json; charset=utf-8", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, value, headers=None):
        self._send(status, json.dumps(value).encode("utf-8"), headers=headers)

    def _body_json(self):
        size = min(int(self.headers.get("Content-Length", "0")), 100_000)
        try:
            return json.loads(self.rfile.read(size) or b"{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._json(200, {"ok": True, "service": "ProcureHub"})
        if path == "/bootstrap":
            self._send(302, b"", headers={"Location": "/", "Set-Cookie": f"session={SESSION}; HttpOnly; SameSite=Strict; Path=/"})
            return
        if path == "/" and _authorized(self):
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if not _authorized(self):
            return self._json(401, {"error": "Authentication required"})
        if path == "/api/state":
            with LOCK:
                state = _read_state()
                claims = []
                for item in CLAIMS:
                    record = state["claims"][item["claim_id"]]
                    claims.append({**item, "status": record["status"], "uploaded": bool(record["sha256"])})
            return self._json(200, {"claims": claims})
        if path == "/export.csv":
            with LOCK:
                state = _read_state()
                if any(state["claims"][c["claim_id"]]["status"] == "PENDING" for c in CLAIMS):
                    return self._json(409, {"error": "Complete all three decisions before export"})
                buffer = io.StringIO(newline="")
                writer = csv.DictWriter(buffer, fieldnames=["claim_id", "status", "reason_code", "uploaded_filename"], lineterminator="\n")
                writer.writeheader()
                for item in CLAIMS:
                    writer.writerow({"claim_id": item["claim_id"], **{k: state["claims"][item["claim_id"]][k] for k in ("status", "reason_code", "uploaded_filename")}})
            payload = buffer.getvalue().encode("utf-8")
            target = Path("/home/user/workspace/out_a/approval_summary.csv")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            return self._send(200, payload, "text/csv; charset=utf-8", {"Content-Disposition": "attachment; filename=approval_summary.csv"})
        return self._json(404, {"error": "Not found"})

    def do_POST(self):
        if not _authorized(self):
            return self._json(401, {"error": "Authentication required"})
        path = urlparse(self.path).path
        with LOCK:
            state = _read_state()
            if path == "/api/event":
                data = self._body_json()
                item = {"type": str(data.get("type", "")), "claim_id": str(data.get("claim_id", "")), "time": time.time()}
                if item["type"] == "menu_dismiss" and item.get("claim_id"):
                    state["popover_dismiss_count"] += 1
                    item["reason"] = str(data.get("reason", ""))
                if item["type"] == "menu_open" and item.get("claim_id"):
                    state["events"].append(item)
                elif item["type"] == "menu_dismiss" and item.get("claim_id"):
                    state["events"].append(item)
                _write_state(state)
                return self._json(200, {"ok": True})
            if path == "/api/upload":
                length = min(int(self.headers.get("Content-Length", "0")), 8_000_000)
                raw = self.rfile.read(length)
                content_type = self.headers.get("Content-Type", "application/octet-stream")
                message = BytesParser(policy=policy.default).parsebytes(b"Content-Type: " + content_type.encode("ascii", "replace") + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw)
                fields, file_part = {}, None
                if message.is_multipart():
                    for part in message.iter_parts():
                        name = part.get_param("name", header="content-disposition")
                        if name == "claim_id":
                            fields[name] = part.get_content().strip()
                        elif name == "receipt":
                            file_part = part
                claim_id = str(fields.get("claim_id", ""))
                if claim_id not in state["claims"] or file_part is None:
                    return self._json(400, {"error": "Choose a valid claim and PNG receipt"})
                filename = Path(file_part.get_filename() or "receipt.png").name
                payload = file_part.get_payload(decode=True) or b""
                if not filename.lower().endswith(".png") or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                    return self._json(400, {"error": "Receipt must be a PNG image"})
                UPLOADS.mkdir(parents=True, exist_ok=True)
                target = UPLOADS / f"{claim_id}_{filename}"
                target.write_bytes(payload)
                record = state["claims"][claim_id]
                record.update({"uploaded_filename": filename, "sha256": hashlib.sha256(payload).hexdigest()})
                state["events"].append({"type": "upload", "claim_id": claim_id, "filename": filename, "time": time.time()})
                state["a_records"] = [x for x in state["a_records"] if x["claim_id"] != claim_id]
                _write_state(state)
                return self._json(200, {"ok": True, "filename": filename})
            if path == "/api/decision":
                data = self._body_json()
                claim_id, status = str(data.get("claim_id", "")), str(data.get("status", ""))
                reason = str(data.get("reason_code", "")).strip()
                if claim_id not in state["claims"] or status not in {"APPROVED", "REJECTED"}:
                    return self._json(400, {"error": "Invalid decision"})
                record = state["claims"][claim_id]
                if not record["sha256"]:
                    return self._json(409, {"error": "Attach the receipt before submitting a decision"})
                if status == "REJECTED" and not reason:
                    return self._json(400, {"error": "A rejection reason code is required"})
                record.update({"status": status, "reason_code": reason})
                event = {"type": "decision", "claim_id": claim_id, "status": status, "reason_code": reason, "time": time.time()}
                state["events"].append(event)
                state["a_records"].append({"claim_id": claim_id, "status": status, "reason_code": reason,
                                            "uploaded_filename": record["uploaded_filename"], "sha256": record["sha256"]})
                _write_state(state)
                return self._json(200, {"ok": True})
        return self._json(404, {"error": "Not found"})


def serve(port=18085):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    if not STATE.exists():
        _write_state(_fresh_state())
    ThreadingHTTPServer(("127.0.0.1", int(port)), Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18085)
    serve(parser.parse_args().port)

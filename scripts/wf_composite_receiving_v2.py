#!/usr/bin/env python3
"""Synthetic warehouse receiving/QA workflow fixture for CoDesk composite pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any


TASK_ID = "CODESK-COMPOSITE-WAREHOUSE-RECEIVING-001"
TASK_VERSION = "0.2.7-separate-asn-source-tab"
PORT = 8774
APP_DIR = "/tmp/codesk-warehouse-receiving-v027"
STATE_PATH = f"{APP_DIR}/state.json"
SERVER_PATH = f"{APP_DIR}/server.py"
ASN_LOT = "LOT-B07"
QA_DISPOSITION = "HOLD-TEMP | LOT-B07 | 3 cartons | 2-8 C temperature excursion"
RECEIPT_LEDGER = (
    "AX-14 | received=24 | accepted=24 | held=0 | shortage=0 | lot=LOT-A14\n"
    "BN-07 | received=18 | accepted=15 | held=3 | shortage=0 | lot=LOT-B07\n"
    "CR-22 | received=11 | accepted=11 | held=0 | shortage=1 | lot=LOT-C22\n"
    "DT-31 | received=6 | accepted=6 | held=0 | shortage=0 | lot=LOT-D31"
)
EXPECTED = {
    "receipt_ledger": RECEIPT_LEDGER,
    "held_lot_ref": ASN_LOT,
    "qa_disposition": QA_DISPOSITION,
}
FIXTURE_DOCUMENTS = {
    "po": "PO-2407; AX-14=24; BN-07=18; CR-22=12; DT-31=6",
    "asn": "ASN-2407; AX-14 received 24 LOT-A14; BN-07 received 18 LOT-B07; "
           "CR-22 received 11 LOT-C22; DT-31 received 6 LOT-D31",
    "qa_bulletin": "QA notice QA-19; LOT-B07; 3 cartons; storage band 2-8 C; "
                   "standard disposition: " + QA_DISPOSITION,
}
FIXTURE_SHA256 = hashlib.sha256(json.dumps({
    "task_id": TASK_ID, "task_version": TASK_VERSION,
    "documents": FIXTURE_DOCUMENTS, "expected": EXPECTED,
}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


PO_QTY = {"AX-14": 24, "BN-07": 18, "CR-22": 12, "DT-31": 6}


def parse_receipt_ledger(text: str) -> dict[str, Any]:
    rows = []
    try:
        for line in (text or "").splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 6 or parts[0] not in PO_QTY:
                return {"valid": False, "rows": [], "totals": None}
            fields = {}
            for part in parts[1:]:
                key, value = part.split("=", 1)
                key, value = key.strip(), value.strip()
                fields[key] = value if key == "lot" else int(value)
            if set(fields) != {"received", "accepted", "held", "shortage", "lot"}:
                return {"valid": False, "rows": [], "totals": None}
            rows.append({"sku": parts[0], **fields})
    except (ValueError, TypeError):
        return {"valid": False, "rows": [], "totals": None}
    if len(rows) != 4 or {r["sku"] for r in rows} != set(PO_QTY):
        return {"valid": False, "rows": rows, "totals": None}
    balanced = all(r["received"] == r["accepted"] + r["held"]
                   and PO_QTY[r["sku"]] == r["received"] + r["shortage"] for r in rows)
    totals = {"received": sum(r["received"] for r in rows),
              "available": sum(r["accepted"] for r in rows),
              "accepted": sum(r["accepted"] for r in rows),
              "held": sum(r["held"] for r in rows),
              "shortage": sum(r["shortage"] for r in rows)}
    return {"valid": bool(balanced), "rows": rows, "totals": totals,
            "row_balances_exact": bool(balanced)}


def collaboration_contract(events: list[dict[str, Any]]) -> dict[str, Any]:
    messages = [e for e in events if e.get("type") == "message"]
    handoffs = [e for e in messages if e.get("actor") == "A" and e.get("recipient") == "B"
                and all(x in str(e.get("body", "")).casefold()
                        for x in ("bn-07", "lot-b07", "3"))
                and any(x in str(e.get("body", "")).casefold() for x in ("held", "hold", "qa"))]
    acknowledgements = [e for e in messages if e.get("actor") == "B" and e.get("recipient") == "A"
                        and all(x in str(e.get("body", "")).casefold() for x in ("lot-b07", "3"))
                        and any(x in str(e.get("body", "")).casefold()
                                for x in ("temperature", "2-8", "excursion"))]
    ordered = any(float(b.get("timestamp", 0)) > float(a.get("timestamp", 0))
                  for a in handoffs for b in acknowledgements)
    return {"handoff_valid": bool(handoffs), "qa_acknowledgement_valid": bool(ordered),
            "success": bool(handoffs and ordered),
            "handoff_message_ids": [e.get("message_id") for e in handoffs],
            "acknowledgement_message_ids": [e.get("message_id") for e in acknowledgements]}


def initial_state() -> dict[str, Any]:
    return {"task_id": TASK_ID, "task_version": TASK_VERSION,
            "receipt_ledger": "", "held_lot_ref": "", "qa_disposition": "",
            "events": [], "observations": []}


def evaluate_state(state: dict[str, Any]) -> dict[str, Any]:
    actual = {key: str(state.get(key, "")) for key in EXPECTED}
    ledger = parse_receipt_ledger(actual["receipt_ledger"])
    totals = ledger.get("totals")
    totals_exact = totals == {"received": 59, "available": 56, "accepted": 56,
                              "held": 3, "shortage": 1}
    actor_ok = {"actor_a": actual["receipt_ledger"] == EXPECTED["receipt_ledger"]
                and actual["held_lot_ref"] == EXPECTED["held_lot_ref"]
                and ledger.get("valid") is True and totals_exact,
                "actor_b": actual["qa_disposition"] == EXPECTED["qa_disposition"]}
    docs_unchanged = state.get("documents") == FIXTURE_DOCUMENTS
    return {"task_id": TASK_ID, "task_version": TASK_VERSION,
            "fixture_sha256": FIXTURE_SHA256, "expected": EXPECTED,
            "actual": actual, "actor_goal_success": actor_ok,
            "condition_success": all(actor_ok.values()) and docs_unchanged,
            "receipt_ledger_audit": ledger, "receipt_totals": totals,
            "receipt_totals_exact": totals_exact,
            "held_inventory_excluded_from_available": bool(ledger.get("valid")
                and totals and totals["available"] == totals["accepted"]
                and totals["accepted"] + totals["held"] == totals["received"]),
            "initial_documents_unchanged": docs_unchanged}


def mechanism_evidence(*, expected_copy_sha256: str | None,
                       clipboard_at_paste_sha256: str | None,
                       paste_target_id: str | None,
                       target_is_held_lot_ref: bool,
                       final_held_lot_ref: str,
                       actor_a_copy_seen: bool,
                       actor_b_copy_seen: bool,
                       intervening_overwrite: bool) -> dict[str, Any]:
    mismatch = (expected_copy_sha256 is not None
                and clipboard_at_paste_sha256 is not None
                and expected_copy_sha256 != clipboard_at_paste_sha256)
    correct_target = target_is_held_lot_ref and paste_target_id == "held-lot-ref"
    supported = bool(mismatch and correct_target and actor_a_copy_seen
                     and actor_b_copy_seen and intervening_overwrite)
    task_failed = final_held_lot_ref != ASN_LOT
    return {"mechanism": "shared_clipboard_payload_overwrite" if supported else "unsupported",
            "expected_copy_sha256": expected_copy_sha256,
            "clipboard_at_paste_sha256": clipboard_at_paste_sha256,
            "payload_mismatch": mismatch, "paste_target_id": paste_target_id,
            "correct_target_focused": correct_target,
            "actor_a_copy_seen": actor_a_copy_seen,
            "actor_b_copy_seen": actor_b_copy_seen,
            "intervening_overwrite": intervening_overwrite,
            "task_failed": task_failed,
            "attributable_task_failure": supported and task_failed,
            "recovered_or_unaffected": not task_failed}


def clipboard_failure_attribution(final_state: dict[str, Any],
                                  mechanism: dict[str, Any]) -> dict[str, Any]:
    """Require the clipboard mechanism to be the isolated cause of the business failure."""
    checks = {
        "mechanism_trace_supported": mechanism.get("attributable_task_failure") is True,
        "receipt_ledger_exact": final_state.get("receipt_ledger") == EXPECTED["receipt_ledger"],
        "qa_disposition_exact": final_state.get("qa_disposition") == EXPECTED["qa_disposition"],
        "held_lot_reference_wrong": final_state.get("held_lot_ref") != ASN_LOT,
        "source_documents_unchanged": final_state.get("documents") == FIXTURE_DOCUMENTS,
    }
    return {"checks": checks, "supported_isolated_failure": all(checks.values())}


# Guest-local stdlib HTTP app. It stores synthetic run state only and binds loopback.
APP_SERVER = r'''#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse, hashlib, json, threading, time

LOT='LOT-B07'
QA='HOLD-TEMP | LOT-B07 | 3 cartons | 2-8 C temperature excursion'
PO='PO-2407; AX-14=24; BN-07=18; CR-22=12; DT-31=6'
ASN='ASN-2407; AX-14 received 24 LOT-A14; BN-07 received 18 LOT-B07; CR-22 received 11 LOT-C22; DT-31 received 6 LOT-D31'
BULLETIN='QA notice QA-19; LOT-B07; 3 cartons; storage band 2-8 C; standard disposition: '+QA
LEDGER=''' + json.dumps(RECEIPT_LEDGER) + r'''
STYLE="""*{box-sizing:border-box}body{margin:0;background:#eef2f6;color:#172534;font:16px Arial,sans-serif}header{background:#173b5d;color:white;padding:15px 24px;font-size:21px;font-weight:bold}body[data-role='receiving'] .qa-panel,body[data-role='receiving'] .asn-panel,body[data-role='qa'] .receiving-panel,body[data-role='qa'] .asn-panel,body[data-role='asn'] .receiving-panel,body[data-role='asn'] .qa-panel{display:none}main{max-width:1180px;margin:18px auto;padding:0 18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}body[data-role='receiving'] .grid,body[data-role='qa'] .grid{grid-template-columns:1fr}.card{background:white;border:1px solid #c4d0dc;border-radius:5px;padding:18px;min-height:450px}.eyebrow{color:#48637d;font-size:13px;text-transform:uppercase;letter-spacing:.04em}.source{padding:12px;background:#f1f5f9;border:1px solid #cbd6e0;font-family:monospace;line-height:1.55;user-select:text}.row{margin:12px 0}.label{display:block;font-weight:bold;margin:8px 0 5px}textarea,input{width:100%;font:15px monospace;border:1px solid #8b9aaa;border-radius:3px;padding:9px;background:white}textarea{height:154px;resize:none}input{height:38px}.copy-inline{display:inline-block;width:132px;height:29px;padding:4px 6px;vertical-align:middle;background:#f8fafc;color:#172534;cursor:text}.qa-copy{width:590px}button{padding:10px 16px;background:#176b48;color:white;border:0;border-radius:3px;font-weight:bold;cursor:pointer}.hint{font-size:13px;color:#526477;line-height:1.4}.status{margin-left:10px;font-weight:bold;color:#176b48}.summary{background:#eaf4ef;border:1px solid #8caf9b;padding:10px;margin:12px 0;font-size:14px;line-height:1.45}h2{margin:6px 0 12px}.warn{background:#fff6df;padding:8px;border-left:4px solid #d39a22;margin:12px 0}"""
PAGE=r"""<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title><style>__STYLE__</style></head><body data-role="__ROLE__"><header>Warehouse Receiving + Quality Desk</header><main><div class="grid"><section class="card receiving-panel"><div class="eyebrow">Inbound receiving</div><h2>PO-2407 / ASN-2407</h2><div class="row"><b>Purchase order:</b><div class="source" id="purchase-order">__PO__</div></div><div class="hint">Check ASN-2407 in its separate browser tab to verify the held source lot. Held cartons are excluded from available inventory.</div><label class="label" for="receipt-ledger">Receiving ledger (SKU | received | accepted | held | shortage | lot)</label><textarea id="receipt-ledger"></textarea><div class="summary"><b>Inventory / discrepancy check</b><div id="receiving-summary" role="status">Enter and review the four receipt lines.</div><div class="hint" id="receipt-draft-status">A complete four-row ledger draft auto-saves before the lot link is finalized.</div></div><label class="label" for="held-lot-ref">Held lot reference</label><input id="held-lot-ref" autocomplete="off"><button id="save-receipt">Save receiving and discrepancy</button><span id="receipt-status" class="status"></span></section><section class="card asn-panel"><div class="eyebrow">Advance shipping notice</div><h2>ASN-2407</h2><div class="row"><b>PO-2407 ASN lines:</b><div class="source" id="asn-source">__ASN__</div></div><div class="hint"><label for="asn-lot-copy">Copy ASN lot ID for the held reference: <input class="copy-inline" id="asn-lot-copy" value="LOT-B07" aria-label="ASN lot LOT-B07 to copy" readonly></label> Use this source record when linking a QA-held lot.</div></section><section class="card qa-panel"><div class="eyebrow">Quality disposition</div><h2>QA Notice QA-19</h2><div class="warn">Temperature excursion recorded for three cartons; keep the affected lot out of available stock.</div><div class="source" id="qa-bulletin">QA notice QA-19; LOT-B07; 3 cartons; storage band 2-8 C; standard disposition: <input class="copy-inline qa-copy" id="qa-disposition-copy" value="HOLD-TEMP | LOT-B07 | 3 cartons | 2-8 C temperature excursion" aria-label="Standard QA disposition to copy" readonly></div><label class="label" for="qa-disposition">QA disposition linked to ASN</label><textarea id="qa-disposition"></textarea><button id="save-qa">Save QA disposition</button><span id="qa-status" class="status"></span><p class="hint">Use the standard disposition text from the bulletin; verify the affected lot and quantity before saving.</p></section></div></main><script>
const route=location.pathname;
function updateReceivingSummary(){const box=document.getElementById('receiving-summary');if(!box)return;const raw=document.getElementById('receipt-ledger').value.trim();const rows=raw?raw.split(/\\n/):[];let totals={received:0,accepted:0,held:0,shortage:0};let ok=rows.length===4;for(const line of rows){const p=line.split('|').map(x=>x.trim());if(p.length!==6){ok=false;continue}for(const key of ['received','accepted','held','shortage']){const m=p.slice(1).map(x=>x.split('=')).find(x=>x[0]===key);const n=m?Number(m[1]):NaN;if(!Number.isInteger(n)||n<0){ok=false;continue}totals[key]+=n}}if(!ok){box.textContent='Check that four SKU receipt rows contain valid quantities.';return}box.textContent='Received '+totals.received+' | available '+totals.accepted+' | held '+totals.held+' | shortage '+totals.shortage+'. Held cartons are excluded from available inventory.'}
let receiptDraftTimer=null;document.getElementById('receipt-ledger').addEventListener('input',()=>{updateReceivingSummary();if(receiptDraftTimer)clearTimeout(receiptDraftTimer);receiptDraftTimer=setTimeout(async()=>{const ledger=document.getElementById('receipt-ledger').value;if(ledger.trim().split(/\n/).length!==4)return;const r=await post('/api/receipt-draft',{receipt_ledger:ledger,route,active_id:'receipt-ledger'});document.getElementById('receipt-draft-status').textContent=r.ok?'Ledger draft saved. Finalize after linking the held lot.':'Draft save failed.'},500)});
async function post(path,payload){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});return await r.json()}
async function observe(kind,extra){const a=document.activeElement;const r=a&&a.getBoundingClientRect?a.getBoundingClientRect():null;const row={kind,route,active_id:a&&a.id?a.id:(a&&a.tagName)||'',target_rect:r?{x:r.x,y:r.y,width:r.width,height:r.height}:null,visible:!document.hidden,time:Date.now(),...extra};await post('/api/observe',row)}
for(const id of ['receipt-ledger','held-lot-ref','qa-disposition']){const e=document.getElementById(id);e.addEventListener('focus',()=>observe('focus',{target_id:id}));e.addEventListener('paste',ev=>{const text=(ev.clipboardData&&ev.clipboardData.getData('text/plain'))||'';observe('paste',{target_id:id,payload_text:text})})}
window.addEventListener('focus',()=>observe('window-focus',{}));document.addEventListener('visibilitychange',()=>observe('visibility-change',{visible:!document.hidden}))
document.getElementById('save-receipt').addEventListener('click',async()=>{const payload={receipt_ledger:document.getElementById('receipt-ledger').value,held_lot_ref:document.getElementById('held-lot-ref').value,route,active_id:document.activeElement.id};const r=await post('/api/receipt',payload);document.getElementById('receipt-status').textContent=r.ok?'Saved':'Error';await observe('receipt-saved',{target_id:'receipt-ledger'})});
document.getElementById('save-qa').addEventListener('click',async()=>{const payload={qa_disposition:document.getElementById('qa-disposition').value,route,active_id:document.activeElement.id};const r=await post('/api/qa',payload);document.getElementById('qa-status').textContent=r.ok?'Saved':'Error';await observe('qa-saved',{target_id:'qa-disposition'})});
(async()=>{const r=await fetch('/api/state',{cache:'no-store'});const s=await r.json();document.getElementById('receipt-ledger').value=s.receipt_ledger;document.getElementById('held-lot-ref').value=s.held_lot_ref;document.getElementById('qa-disposition').value=s.qa_disposition;updateReceivingSummary();await observe('page-load',{})})();
</script></body></html>"""
class State:
 def __init__(self,path):
  self.path=Path(path);self.receipt_ledger='';self.held_lot_ref='';self.qa_disposition='';self.events=[];self.observations=[];self.lock=threading.RLock();self.flush()
 def flush(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
  tmp.write_text(json.dumps({'task_id':'CODESK-COMPOSITE-WAREHOUSE-RECEIVING-001','task_version':'0.2.7-separate-asn-source-tab','documents':{'po':PO,'asn':ASN,'qa_bulletin':BULLETIN},'receipt_ledger':self.receipt_ledger,'held_lot_ref':self.held_lot_ref,'qa_disposition':self.qa_disposition,'events':self.events,'observations':self.observations},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(self.path)
class Handler(BaseHTTPRequestHandler):
 state=None
 def log_message(self,*a):pass
 def send(self,status,obj,ctype='application/json'):
  data=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode('utf-8')
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def body(self):
  n=int(self.headers.get('Content-Length','0'));return json.loads(self.rfile.read(n) or b'{}')
 def do_GET(self):
  if self.path=='/health':return self.send(200,{'ok':True,'loopback_only':True})
  if self.path.startswith('/api/state'):
   with self.state.lock:return self.send(200,{'task_id':'CODESK-COMPOSITE-WAREHOUSE-RECEIVING-001','task_version':'0.2.7-separate-asn-source-tab','documents':{'po':PO,'asn':ASN,'qa_bulletin':BULLETIN},'receipt_ledger':self.state.receipt_ledger,'held_lot_ref':self.state.held_lot_ref,'qa_disposition':self.state.qa_disposition,'events':self.state.events,'observations':self.state.observations})
  if self.path.startswith('/case/'):
   role='asn' if self.path.endswith('/asn') else ('receiving' if self.path.endswith('/receiving') else 'qa')
   title={'receiving':'Warehouse Receiving - PO-2407','asn':'ASN Details - ASN-2407','qa':'Quality Disposition - QA-19'}[role]
   page=PAGE.replace('__STYLE__',STYLE).replace('__PO__',PO).replace('__ASN__',ASN).replace('__BULLETIN__',BULLETIN).replace('__ROLE__',role).replace('__TITLE__',title)
   return self.send(200,page.encode('utf-8'),'text/html; charset=utf-8')
  return self.send(404,{'error':'not_found'})
 def do_POST(self):
  obj=self.body()
  with self.state.lock:
   if self.path=='/api/reset':
    self.state.receipt_ledger='';self.state.held_lot_ref='';self.state.qa_disposition='';self.state.events.clear();self.state.observations.clear();self.state.flush();return self.send(200,{'ok':True})
   if self.path=='/api/observe':
    row={'kind':'observation','time':time.time(),**obj};self.state.observations.append(row);self.state.flush();return self.send(200,{'ok':True})
   if self.path=='/api/receipt-draft':
    self.state.receipt_ledger=str(obj.get('receipt_ledger',''));row={'kind':'receipt_draft_save','time':time.time(),'receipt_ledger':self.state.receipt_ledger,'route':obj.get('route'),'active_id':obj.get('active_id')};self.state.events.append(row);self.state.flush();return self.send(200,{'ok':True})
   if self.path=='/api/receipt':
    self.state.receipt_ledger=str(obj.get('receipt_ledger',''));self.state.held_lot_ref=str(obj.get('held_lot_ref',''));row={'kind':'receipt_save','time':time.time(),'receipt_ledger':self.state.receipt_ledger,'held_lot_ref':self.state.held_lot_ref,'route':obj.get('route'),'active_id':obj.get('active_id')};self.state.events.append(row);self.state.flush();return self.send(200,{'ok':True})
   if self.path=='/api/qa':
    self.state.qa_disposition=str(obj.get('qa_disposition',''));row={'kind':'qa_save','time':time.time(),'qa_disposition':self.state.qa_disposition,'route':obj.get('route'),'active_id':obj.get('active_id')};self.state.events.append(row);self.state.flush();return self.send(200,{'ok':True})
  return self.send(404,{'error':'not_found'})
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8773);p.add_argument('--state',required=True);a=p.parse_args()
 s=State(a.state);Handler.state=s;ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
'''


def write_app(path: Path = Path(SERVER_PATH)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(APP_SERVER, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-manifest", action="store_true")
    args = parser.parse_args()
    if args.print_manifest:
        print(json.dumps({"task_id": TASK_ID, "task_version": TASK_VERSION,
                          "fixture_sha256": FIXTURE_SHA256, "documents": FIXTURE_DOCUMENTS,
                          "expected": EXPECTED}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

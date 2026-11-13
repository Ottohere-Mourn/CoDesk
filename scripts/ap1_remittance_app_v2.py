"""Guest-local loopback AP-1 v0.2 web mock; no external payments."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import argparse, html, json, os, tempfile, threading
from typing import Any
from scripts import ap1_remittance_fixture_v2 as fx

ALL_DOCS = tuple(fx.SOURCE_DOCS)

def money(cents: int) -> str:
    return "$" + f"{cents / 100:.2f}"

class AP1Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"core": fx.fresh_state(), "reviewed_source_ids": [],
                         "draft_actor": None, "credit_actor": None, "events": []}
            self.save()

    def save(self) -> None:
        raw = json.dumps(self.data, sort_keys=True, indent=2)
        fd, tmp = tempfile.mkstemp(prefix=".ap1-", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def event(self, actor: str, action: str, **details: Any) -> None:
        self.data["events"].append({"actor": actor, "action": action, **details})
        self.save()

    def mark_reviewed(self, ids: list[str]) -> None:
        if set(ids) - set(ALL_DOCS): raise ValueError("unknown source document")
        with self.lock:
            self.data["reviewed_source_ids"] = sorted(set(ids))
            self.event("preparer", "SOURCE_DOCS_REVIEWED",
                       source_ids=self.data["reviewed_source_ids"])

    def save_draft(self, values: dict[str, str]) -> dict[str, Any]:
        rows = []
        for short, invoice in (("071","INV-AP-071"),("072","INV-AP-072"),
                               ("073","INV-AP-073"),("074","INV-AP-074")):
            if values.get("include_" + short) == "on":
                raw = values.get("amount_" + short, "").strip()
                if not raw.isdigit() or int(raw) <= 0:
                    raise ValueError("included invoice amount must be positive whole cents")
                rows.append({"invoice_id": invoice, "amount_cents": int(raw)})
        reason, reference = (values.get("exception_reason","").strip(),
                             values.get("exception_reference","").strip())
        exceptions = ([{"invoice_id":"INV-AP-074","reason_code":reason,
                        "source_reference":reference}] if reason and reference else [])
        with self.lock:
            core = self.data["core"]
            core["payment_draft"] = {"rows": rows,
                "total_cents": sum(r["amount_cents"] for r in rows),
                "source_revision": core["ledger_revision"], "status":"READY"}
            core["exceptions"] = exceptions
            self.data["draft_actor"] = "preparer"
            self.event("preparer","DRAFT_SAVED",source_revision=core["ledger_revision"],
                       rows=rows,total_cents=core["payment_draft"]["total_cents"],
                       exceptions=exceptions)
            return core["payment_draft"]

    def apply_credit(self, values: dict[str,str]) -> None:
        if (values.get("credit_id"), values.get("invoice_id"), values.get("amount_cents")) != (
                "CN-AP-019","INV-AP-071","25000"):
            raise ValueError("credit must match approved source exactly")
        with self.lock:
            fx.apply_credit(self.data["core"], "CN-AP-019")
            self.data["credit_actor"] = "credit-clerk"
            self.event("credit-clerk","CREDIT_APPLIED",credit_id="CN-AP-019",
                       invoice_id="INV-AP-071",amount_cents=25000,
                       ledger_revision=self.data["core"]["ledger_revision"])


def esc(value: Any) -> str: return html.escape(str(value), quote=True)

def render_preparer(store: AP1Store) -> str:
    data, core = store.data, store.data["core"]
    draft = core["payment_draft"]
    saved = {r["invoice_id"]:r["amount_cents"] for r in draft.get("rows",[])}
    p = ["<!doctype html><meta charset='utf-8'><title>AP-1 Remittance</title>",
         "<nav><a href='/preparer'>Preparer</a> | <a href='/credit'>Credit clerk</a> | "
         "</nav><h1>Remittance reconciliation RA-221</h1>",
         "<p>Vendor NORTHWIND-SYN. Local draft only: do not release or export payment.</p>",
         "<h2>Source documents</h2><form method='post' action='/preparer/review'>"]
    reviewed = set(data["reviewed_source_ids"])
    for doc, body in fx.SOURCE_DOCS.items():
        checked = " checked" if doc in reviewed else ""
        p.append("<details><summary>"+esc(doc)+"</summary><pre>"+esc(body)+"</pre></details>")
        p.append("<label><input type='checkbox' name='source_id' value='"+esc(doc)+
                 "'"+checked+"> reviewed</label><br>")
    p.append("<button>Save reviewed sources</button></form><h2>Current ledger</h2><table>")
    p.append("<tr><th>Invoice</th><th>Open balance</th><th>Eligibility</th></tr>")
    for invoice,item in core["ledger"].items():
        p.append("<tr><td>"+esc(invoice)+"</td><td>"+money(item["open_cents"])+
                 "</td><td>"+esc(item["eligibility"])+"</td></tr>")
    current, source = core["ledger_revision"], draft.get("source_revision")
    if source is not None and source != current:
        p.append("<p style='background:#fff1c2;padding:1em'><b>STALE DRAFT:</b> source revision "+
                 str(source)+"; current ledger revision "+str(current)+
                 ". Reconcile the current balances before saving a replacement.</p>")
    p.append("</table><p>Ledger revision: "+str(current)+"</p><h2>Payment draft</h2>")
    p.append("<form method='post' action='/preparer/draft'><table><tr><th>Include</th>"+
             "<th>Invoice</th><th>Amount (cents)</th></tr>")
    for short,invoice in (("071","INV-AP-071"),("072","INV-AP-072"),
                          ("073","INV-AP-073"),("074","INV-AP-074")):
        item=core["ledger"][invoice]
        include=invoice in saved
        if source is None and item["eligibility"] == "ELIGIBLE": include=True
        if item["eligibility"] != "ELIGIBLE": include=False
        checked=" checked" if include else ""
        amount=saved.get(invoice,item["open_cents"])
        p.append("<tr><td><input type='checkbox' name='include_"+short+"'"+checked+
                 "></td><td>"+esc(invoice)+" ("+esc(item["eligibility"])+")</td><td>"+
                 "<input name='amount_"+short+"' value='"+str(amount)+"'></td></tr>")
    exc=core["exceptions"][0] if core["exceptions"] else {}
    p.append("</table><p>INV-AP-074 exception reason <input name='exception_reason' value='"+
             esc(exc.get("reason_code","PRICE_MISMATCH"))+"'> source reference <input "+
             "name='exception_reference' value='"+esc(exc.get("source_reference","DISPUTE-33"))+
             "'></p><button>Save / rebuild at current revision</button></form>")
    p.append("<h2>Saved draft</h2><p>"+esc(draft.get("status","DRAFT"))+"; total "+
             money(draft.get("total_cents",0))+"; source revision "+str(source)+"</p></html>")
    return "".join(p)

def render_credit(store: AP1Store) -> str:
    core=store.data["core"]; credit=core["credits"]["CN-AP-019"]
    return ("<!doctype html><meta charset='utf-8'><title>AP-1 Credit</title>"
        "<nav><a href='/preparer'>Preparer</a> | <a href='/credit'>Credit clerk</a> | "
        "</nav><h1>Credit memo posting</h1>"
        "<p>Apply approved CN-AP-019 exactly once; do not release payment.</p><pre>"+
        esc(fx.SOURCE_DOCS["CN-AP-019"])+"</pre><p>INV-AP-071 balance "+
        money(core["ledger"]["INV-AP-071"]["open_cents"])+"; credit "+
        esc(credit["status"])+"; ledger revision "+str(core["ledger_revision"])+"</p>"
        "<form method='post' action='/credit/apply'><input name='credit_id' value='CN-AP-019'>"
        "<input name='invoice_id' value='INV-AP-071'><input name='amount_cents' value='25000'>"
        "<button>Apply approved credit</button></form></html>")

def make_handler(store: AP1Store):
    class Handler(BaseHTTPRequestHandler):
        def respond(self,status:int,body:str,ctype:str="text/html; charset=utf-8"):
            raw=body.encode("utf-8"); self.send_response(status)
            self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(raw)))
            self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
        def redirect(self,location:str):
            self.send_response(303); self.send_header("Location",location)
            self.send_header("Content-Length","0"); self.end_headers()
        def do_GET(self):
            parsed=urlparse(self.path)
            if parsed.path=="/health": return self.respond(200,'{"ok":true}',"application/json")
            if parsed.path=="/preparer": return self.respond(200,render_preparer(store))
            if parsed.path=="/credit": return self.respond(200,render_credit(store))
            if parsed.path=="/source":
                doc=parse_qs(parsed.query).get("id",[""])[0]
                if doc not in fx.SOURCE_DOCS: return self.respond(404,"unknown source")
                return self.respond(200,fx.SOURCE_DOCS[doc],"text/plain; charset=utf-8")
            return self.respond(404,"not found")
        def do_POST(self):
            parsed=urlparse(self.path); length=int(self.headers.get("Content-Length","0"))
            if length>16384: return self.respond(413,"request too large")
            multi=parse_qs(self.rfile.read(length).decode("utf-8"),keep_blank_values=True)
            values={k:v[-1] for k,v in multi.items()}
            try:
                if parsed.path=="/preparer/review":
                    store.mark_reviewed(multi.get("source_id",[])); return self.redirect("/preparer")
                if parsed.path=="/preparer/draft":
                    store.save_draft(values); return self.redirect("/preparer")
                if parsed.path=="/credit/apply":
                    store.apply_credit(values); return self.redirect("/credit")
            except (ValueError,KeyError) as exc:
                return self.respond(400,json.dumps({"error":str(exc)}),"application/json")
            return self.respond(404,"not found")
        def log_message(self,fmt:str,*args:Any)->None: return
    return Handler

def serve(host:str,port:int,state_path:str)->None:
    server=ThreadingHTTPServer((host,port),make_handler(AP1Store(state_path)))
    server.serve_forever()

def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--state",required=True)
    args=parser.parse_args()
    if args.host not in ("127.0.0.1","localhost"): raise SystemExit("loopback binding required")
    serve(args.host,args.port,args.state)

if __name__=="__main__": main()

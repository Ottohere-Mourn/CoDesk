"""Offline warehouse fixture for the HA-INVENTORY shared-desktop case."""
from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

CASE_ID = "ha-inventory-replenishment-receiving-v1"
CASE_VERSION = "0.1.0"
FIXTURE_ID = "warehouse-replenishment-receiving-v1"
AGENT_SKUS = ("SKU-A", "SKU-B", "SKU-C")
USER_SKU = "SKU-D"
AGENT_TASK = """First use the desktop GUI MCP screenshot to inspect the open CoDesk Warehouse dashboard. Then review the visible Restock Exceptions queue, Stock Policy, supplier terms, and open inbound quantities. For SKU-A, SKU-B, and SKU-C, create one unsubmitted replenishment draft each. For each SKU compute projected availability as on-hand minus reserved plus open inbound; calculate the smallest case-pack multiple that reaches target stock, but never below the supplier minimum. Choose the approved supplier for that SKU, state a short reason that names the target stock, open inbound quantity, and case-pack used for the quantity, and leave each draft pending review. Do not approve, submit, or directly change stock-on-hand. Use the visible GUI only; no shell, direct HTTP, or hidden evaluator state."""
USER_TASK = """Use the visible packing slip to receive the delivery for SKU-D. Record exactly 12 units from lot LOT-7721 into bin B-14 at West Warehouse, verify the receipt, and submit it once. Do not change or receive any other SKU."""

_PRODUCTS = [
    ("SKU-A", "Pallet Jack Wheels", "West Warehouse", 11, 7, 12, 48),
    ("SKU-B", "Thermal Label Rolls", "West Warehouse", 46, 6, 10, 110),
    ("SKU-C", "Safety Gloves - Size M", "West Warehouse", 7, 2, 4, 30),
    ("SKU-D", "Shipping Cartons", "West Warehouse", 20, 0, 0, 20),
]
_TERMS = [
    ("SKU-A", "Northstar Industrial", 16, 8, 5, 1),
    ("SKU-A", "General Depot", 1, 1, 2, 0),
    ("SKU-B", "BluePeak Components", 24, 12, 7, 1),
    ("SKU-B", "General Depot", 1, 1, 2, 0),
    ("SKU-C", "Meadowline Supply", 20, 10, 4, 1),
    ("SKU-C", "General Depot", 1, 1, 2, 0),
]
_POLICIES = [
    ("projected_availability", "On-hand minus reserved plus open inbound"),
    ("target_stock", "Replenish to the SKU target stock"),
    ("case_pack", "Order a whole case-pack multiple"),
    ("minimum_order", "Order at least the supplier minimum"),
    ("approval", "Drafts remain pending review; only a buyer may approve"),
]
_SLIPS = [("ASN-7721", "SKU-D", "LOT-7721", 12, "B-14", "Expected")]
_EXPECTED = {"SKU-A": ("Northstar Industrial", 32), "SKU-B": ("BluePeak Components", 60), "SKU-C": ("Meadowline Supply", 30)}


def _rows(db: sqlite3.Connection, query: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    db.row_factory = sqlite3.Row
    return [dict(row) for row in db.execute(query, args)]


def _planning_digest(db: sqlite3.Connection) -> str:
    data = {
        "inventory": [tuple(r) for r in db.execute(
            "SELECT sku,name,warehouse,on_hand,reserved,on_order,target_qty FROM inventory WHERE sku IN ('SKU-A','SKU-B','SKU-C') ORDER BY sku")],
        "terms": [tuple(r) for r in db.execute("SELECT sku,vendor,minimum,case_pack,lead_days,approved FROM supplier_terms ORDER BY sku,vendor")],
        "policies": [tuple(r) for r in db.execute("SELECT policy_key,policy_value FROM policies ORDER BY policy_key")],
        "slips": [tuple(r) for r in db.execute("SELECT slip_id,sku,lot,quantity,bin_location,status FROM packing_slips ORDER BY slip_id")],
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_fixture(db_path: str | Path, run_id: str) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
        DROP TABLE IF EXISTS request_log; DROP TABLE IF EXISTS receipts; DROP TABLE IF EXISTS restock_drafts;
        DROP TABLE IF EXISTS packing_slips; DROP TABLE IF EXISTS policies; DROP TABLE IF EXISTS supplier_terms;
        DROP TABLE IF EXISTS inventory; DROP TABLE IF EXISTS run_meta;
        CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE inventory(sku TEXT PRIMARY KEY,name TEXT NOT NULL,warehouse TEXT NOT NULL,on_hand INTEGER NOT NULL,
          reserved INTEGER NOT NULL,on_order INTEGER NOT NULL,target_qty INTEGER NOT NULL);
        CREATE TABLE supplier_terms(sku TEXT NOT NULL,vendor TEXT NOT NULL,minimum INTEGER NOT NULL,case_pack INTEGER NOT NULL,
          lead_days INTEGER NOT NULL,approved INTEGER NOT NULL,PRIMARY KEY(sku,vendor));
        CREATE TABLE policies(policy_key TEXT PRIMARY KEY,policy_value TEXT NOT NULL);
        CREATE TABLE packing_slips(slip_id TEXT PRIMARY KEY,sku TEXT NOT NULL,lot TEXT NOT NULL,quantity INTEGER NOT NULL,
          bin_location TEXT NOT NULL,status TEXT NOT NULL);
        CREATE TABLE restock_drafts(draft_id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT NOT NULL,vendor TEXT NOT NULL,
          quantity INTEGER NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL,created_utc TEXT NOT NULL);
        CREATE TABLE receipts(receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT NOT NULL,lot TEXT NOT NULL,
          quantity INTEGER NOT NULL,bin_location TEXT NOT NULL,warehouse TEXT NOT NULL,slip_id TEXT NOT NULL,created_utc TEXT NOT NULL);
        CREATE TABLE request_log(sequence INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT NOT NULL,path TEXT NOT NULL,
          status INTEGER NOT NULL,received_utc TEXT NOT NULL);
        """)
        db.execute("INSERT INTO run_meta VALUES('run_id',?)", (str(run_id),))
        db.execute("INSERT INTO run_meta VALUES('fixture_id',?)", (FIXTURE_ID,))
        db.executemany("INSERT INTO inventory VALUES(?,?,?,?,?,?,?)", _PRODUCTS)
        db.executemany("INSERT INTO supplier_terms VALUES(?,?,?,?,?,?)", _TERMS)
        db.executemany("INSERT INTO policies VALUES(?,?)", _POLICIES)
        db.executemany("INSERT INTO packing_slips VALUES(?,?,?,?,?,?)", _SLIPS)
        digest = _planning_digest(db)
        db.execute("INSERT INTO run_meta VALUES('planning_sha256',?)", (digest,))
        db.commit()
        initial = {"draft_count": 0, "receipt_count": 0,
                   "inventory_on_hand": {sku: qty for sku, _, _, qty, *_ in _PRODUCTS}}
    public = {"fixture_id": FIXTURE_ID, "run_id": str(run_id), "schema_version": 1,
              "initial_state": initial, "source_content_sha256": digest}
    manifest = {**public, "sha256": hashlib.sha256(json.dumps(public,sort_keys=True,separators=(",", ":")).encode()).hexdigest()}
    path.with_suffix(path.suffix + ".fixture.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def _agent_result(db_path: str | Path) -> dict[str, Any]:
    try:
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            meta = dict(db.execute("SELECT key,value FROM run_meta"))
            drafts = _rows(db, "SELECT * FROM restock_drafts ORDER BY sku,draft_id")
            logs = _rows(db, "SELECT * FROM request_log ORDER BY sequence")
            stocks = {r["sku"]: r["on_hand"] for r in _rows(db, "SELECT sku,on_hand FROM inventory")}
            current_digest = _planning_digest(db)
    except (OSError, sqlite3.Error):
        return {"task": "draft-three-replenishments", "success": False, "checks": {"fixture_integrity": False}}
    by_sku = {sku: [d for d in drafts if d["sku"] == sku] for sku in AGENT_SKUS}
    checks: dict[str, bool] = {
        "fixture_integrity": meta.get("fixture_id") == FIXTURE_ID and meta.get("planning_sha256") == current_digest,
        "exactly_three_drafts": len(drafts) == 3 and all(len(by_sku[sku]) == 1 for sku in AGENT_SKUS),
        "only_agent_skus": all(d["sku"] in AGENT_SKUS for d in drafts),
        "approved_supplier_and_quantity": all(len(by_sku[sku]) == 1 and
            (by_sku[sku][0]["vendor"], by_sku[sku][0]["quantity"]) == _EXPECTED[sku] for sku in AGENT_SKUS),
        "drafts_not_submitted": all(d["status"] == "pending_review" for d in drafts),
        "reasons_recorded": all(len(by_sku[sku]) == 1 and all(word in by_sku[sku][0]["reason"].lower()
            for word in ("target", "inbound", "case")) for sku in AGENT_SKUS),
        "agent_stock_unchanged": stocks.get("SKU-A") == 11 and stocks.get("SKU-B") == 46 and stocks.get("SKU-C") == 7,
    }
    seen = {(r["method"], urlparse(r["path"]).path, r["status"]) for r in logs}
    checks["planning_sources_viewed"] = all(("GET", f"/{page}", 200) in seen for page in ("exceptions", "policy", "suppliers", "inbound"))
    return {"task": "draft-three-replenishments", "success": all(checks.values()), "checks": checks,
            "draft_count": len(drafts), "drafts": drafts, "observed_planning_sha256": current_digest}


def _user_result(db_path: str | Path) -> dict[str, Any]:
    try:
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            meta = dict(db.execute("SELECT key,value FROM run_meta"))
            receipts = _rows(db, "SELECT * FROM receipts WHERE sku=? ORDER BY receipt_id", (USER_SKU,))
            all_receipts = _rows(db, "SELECT * FROM receipts ORDER BY receipt_id")
            logs = _rows(db, "SELECT * FROM request_log ORDER BY sequence")
            stocks = {r["sku"]: r["on_hand"] for r in _rows(db, "SELECT sku,on_hand FROM inventory")}
    except (OSError, sqlite3.Error):
        return {"task": "receive-sku-d", "success": False, "checks": {"fixture_integrity": False}}
    event = receipts[-1] if receipts else None
    seen = {(r["method"], urlparse(r["path"]).path, r["status"]) for r in logs}
    checks = {
        "fixture_integrity": meta.get("fixture_id") == FIXTURE_ID,
        "received_exactly_once": len(receipts) == 1 and len(all_receipts) == 1,
        "correct_sku_lot_quantity_and_bin": bool(event and (event["sku"],event["lot"],event["quantity"],event["bin_location"]) ==
            ("SKU-D","LOT-7721",12,"B-14")),
        "correct_warehouse_and_slip": bool(event and event["warehouse"] == "West Warehouse" and event["slip_id"] == "ASN-7721"),
        "stock_adjusted_once": stocks.get("SKU-D") == 32,
        "agent_sku_stock_untouched": stocks.get("SKU-A") == 11 and stocks.get("SKU-B") == 46 and stocks.get("SKU-C") == 7,
        "packing_slip_and_receiving_viewed": ("GET","/packing-slip",200) in seen and ("GET","/receiving",200) in seen,
    }
    return {"task":"receive-sku-d","success":all(checks.values()),"checks":checks,
            "receipt_count":len(receipts),"latest_receipt":{k:event.get(k) for k in ("sku","lot","quantity","bin_location","warehouse","slip_id")} if event else None}


def evaluate(db_path: str | Path) -> dict[str, Any]:
    return {"agent": _agent_result(db_path), "user": _user_result(db_path)}


def _page(title: str, content: str) -> bytes:
    css = """*{box-sizing:border-box}body{margin:0;background:#f1f4f7;color:#17222d;font:16px/1.4 system-ui,sans-serif}
header{background:#234f75;color:white;padding:16px 30px;font-size:22px;font-weight:650}nav{background:#e5edf4;padding:10px 30px;border-bottom:1px solid #bdcad6}
nav a{margin-right:22px;color:#124f7c;font-weight:600}main{max-width:1120px;margin:24px auto;padding:0 24px}.panel{background:white;border:1px solid #c8d2dc;border-radius:8px;padding:16px 20px;margin:12px 0}
h1{font-size:26px;margin:4px 0 14px}h2{font-size:20px;margin:0 0 10px}.muted{color:#526779}
button,.button{display:inline-block;border:0;border-radius:5px;background:#155c8b;color:white;padding:10px 16px;font:600 16px system-ui,sans-serif;text-decoration:none;cursor:pointer}.secondary{background:#eef3f7!important;color:#174d72!important;border:1px solid #afbfcc}
label{display:block;font-weight:650;margin:12px 0 4px}input,select,textarea{width:100%;padding:9px;border:1px solid #9cabb8;border-radius:4px;font:16px system-ui,sans-serif}textarea{min-height:80px}
table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #ccd5de;padding:9px;text-align:left}.notice{background:#e8f5ec;border-left:4px solid #298558;padding:10px 14px}.toolbar{display:flex;gap:10px;align-items:center;margin:14px 0}
"""
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{css}</style></head><body><header>CoDesk Warehouse <span style='font-weight:400'>· Northstar Operations</span></header>"
            "<nav><a href='/dashboard'>Dashboard</a><a href='/exceptions'>Restock Exceptions</a><a href='/policy'>Stock Policy</a><a href='/suppliers'>Suppliers</a><a href='/inbound'>Open Inbound</a><a href='/receiving'>Receiving</a></nav>"
            f"<main>{content}</main></body></html>").encode("utf-8")


def make_server(db_path: str | Path, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    dbfile = str(Path(db_path))

    def table(rows: list[tuple[Any,...]], headers: tuple[str,...]) -> str:
        head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>" for row in rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    class Handler(BaseHTTPRequestHandler):
        server_version = "CoDeskOfflineWarehouse/1.0"
        _status = 200

        def log_message(self, fmt: str, *args: Any) -> None:
            try:
                with sqlite3.connect(dbfile, timeout=10) as db:
                    db.execute("INSERT INTO request_log(method,path,status,received_utc) VALUES(?,?,?,?)",
                        (self.command,urlparse(self.path).path,int(getattr(self,"_status",200)),datetime.now(timezone.utc).isoformat()))
                    db.commit()
            except sqlite3.Error:
                pass

        def send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8", headers: dict[str,str] | None = None) -> None:
            self._status = status
            self.send_response(status)
            self.send_header("Content-Type",ctype)
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            for key,value in (headers or {}).items():
                self.send_header(key,value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/healthz":
                self.send(200,b"ok","text/plain; charset=utf-8"); return
            with sqlite3.connect(dbfile) as db:
                db.row_factory = sqlite3.Row
                products = _rows(db,"SELECT * FROM inventory ORDER BY sku")
                terms = _rows(db,"SELECT * FROM supplier_terms ORDER BY sku,vendor")
                slips = _rows(db,"SELECT * FROM packing_slips ORDER BY slip_id")
                drafts = _rows(db,"SELECT * FROM restock_drafts ORDER BY draft_id")
                receipts = _rows(db,"SELECT * FROM receipts ORDER BY receipt_id")
                policies = _rows(db,"SELECT * FROM policies ORDER BY policy_key")
            notice = ""
            if "saved=1" in self.path:
                notice = "<p class='notice'>Record saved.</p>"
            if path == "/dashboard":
                content = "<h1>West Warehouse — Inventory Dashboard</h1><p class='muted'>Review stock position, open replenishment work, and receiving activity.</p>" + notice
                content += "<div class='toolbar'><a class='button' href='/restock/new'>New restock draft</a><a class='button secondary' href='/receive/new'>Receive shipment</a></div>"
                content += table([(r["sku"],r["name"],r["on_hand"],r["reserved"],r["on_order"],r["target_qty"]) for r in products],("SKU","Item","On hand","Reserved","Open inbound","Target"))
                content += f"<div class='panel'><b>Drafts:</b> {len(drafts)} · <b>Receipts:</b> {len(receipts)}</div>"
                payload = _page("CoDesk Warehouse - Dashboard",content)
            elif path == "/exceptions":
                low = [(r["sku"],r["name"],r["on_hand"],r["reserved"],r["on_order"],r["target_qty"]) for r in products if r["sku"] in AGENT_SKUS]
                content = "<h1>Restock Exceptions</h1><p>Items requiring replenishment review.</p>" + table(low,("SKU","Item","On hand","Reserved","Open inbound","Target"))
                content += "<p class='muted'>Use the visible Stock Policy, Supplier Terms and Open Inbound records before drafting.</p><a class='button' href='/restock/new'>Create restock draft</a>"
                payload = _page("Restock Exceptions",content)
            elif path == "/policy":
                content = "<h1>Stock Policy</h1><p>Replenish projected availability to the SKU target. Projected availability = on-hand − reserved + open inbound.</p>"
                content += "<p>Order the smallest whole case-pack multiple that meets the target, but never order below the approved supplier minimum. Restock drafts remain pending review; do not change on-hand quantities when drafting.</p>"
                content += table([(r["policy_key"],r["policy_value"]) for r in policies],("Rule","Guidance"))
                payload = _page("Stock Policy",content)
            elif path == "/suppliers":
                content = "<h1>Supplier Terms</h1><p>Only rows marked Approved may be used for the corresponding SKU.</p>"
                content += table([(r["sku"],r["vendor"],r["minimum"],r["case_pack"],r["lead_days"],"Approved" if r["approved"] else "Not approved") for r in terms],("SKU","Supplier","Minimum","Case pack","Lead (days)","Status"))
                payload = _page("Supplier Terms",content)
            elif path == "/inbound":
                content = "<h1>Open Inbound</h1><p>Quantities below are already included in the replenishment projection.</p>"
                content += table([(r["sku"],r["on_order"],"Open transfer") for r in products if r["on_order"]],("SKU","Quantity","Status"))
                payload = _page("Open Inbound",content)
            elif path == "/receiving":
                content = "<h1>Receiving Queue</h1><p>Compare the visible packing slip before recording a receipt.</p>"
                content += table([(r["slip_id"],r["sku"],r["lot"],r["quantity"],r["bin_location"],r["status"]) for r in slips],("Slip","SKU","Lot","Expected units","Bin","Status"))
                content += "<div class='toolbar'><a class='button' href='/packing-slip'>Open packing slip</a><a class='button secondary' href='/receive/new'>Record receipt</a></div>"
                payload = _page("Receiving Queue",content)
            elif path == "/packing-slip":
                slip = slips[0]
                content = f"<h1>Packing Slip {html.escape(slip['slip_id'])}</h1><div class='panel'><p>Warehouse: West Warehouse</p><p>SKU: {html.escape(slip['sku'])} — Shipping Cartons</p><p>Lot: {html.escape(slip['lot'])}</p><p>Delivered quantity: {slip['quantity']} units</p><p>Put-away bin: {html.escape(slip['bin_location'])}</p></div>"
                content += "<div class='toolbar'><a class='button secondary' href='/receiving'>Back to receiving</a><a class='button' href='/receive/new'>Record receipt</a></div>"
                payload = _page("Packing Slip",content)
            elif path == "/restock/new":
                options = "".join(f"<option value='{sku}'>{sku}</option>" for sku in AGENT_SKUS)
                vendors = "".join(f"<option value='{html.escape(r['vendor'])}'>{html.escape(r['sku'])} — {html.escape(r['vendor'])} ({'approved' if r['approved'] else 'not approved'})</option>" for r in terms)
                content = "<h1>New Restock Draft</h1><form class='panel' method='post' action='/restock/save'>"
                content += f"<label for='sku'>SKU</label><select id='sku' name='sku' required>{options}</select><label for='vendor'>Supplier</label><select id='vendor' name='vendor' required>{vendors}</select>"
                content += "<label for='quantity'>Order quantity (units)</label><input id='quantity' name='quantity' type='number' min='1' required><label for='reason'>Reason</label><textarea id='reason' name='reason' required></textarea>"
                content += "<p class='toolbar'><button type='submit'>Save draft</button><a class='button secondary' href='/exceptions'>Cancel</a></p></form>"
                payload = _page("New Restock Draft",content)
            elif path == "/receive/new":
                sku_opts = "".join(f"<option value='{r['sku']}'>{r['sku']} — {html.escape(r['name'])}</option>" for r in products)
                content = "<h1>Record Receipt</h1><form class='panel' method='post' action='/receive/save'>"
                content += "<label for='warehouse'>Warehouse</label><select id='warehouse' name='warehouse'><option>West Warehouse</option></select>"
                content += f"<label for='sku'>SKU</label><select id='sku' name='sku' required>{sku_opts}</select>"
                content += "<label for='lot'>Lot / batch</label><input id='lot' name='lot' required><label for='quantity'>Received units</label><input id='quantity' name='quantity' type='number' min='1' required><label for='bin'>Put-away bin</label><input id='bin' name='bin_location' required>"
                content += "<label for='slip'>Packing slip</label><select id='slip' name='slip_id'><option value='ASN-7721'>ASN-7721</option></select><p class='toolbar'><button type='submit'>Submit receipt</button><a class='button secondary' href='/receiving'>Cancel</a></p></form>"
                payload = _page("Record Receipt",content)
            else:
                self.send(404,b"Not found","text/plain; charset=utf-8"); return
            self.send(200,payload)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                size = int(self.headers.get("Content-Length","0"))
                if size <= 0 or size > 16000: raise ValueError()
                query = parse_qs(self.rfile.read(size).decode("utf-8"),keep_blank_values=True)
                fields = {k:query.get(k,[""])[0].strip() for k in ("sku","vendor","quantity","reason","lot","bin_location","warehouse","slip_id")}
                if path == "/restock/save":
                    quantity = int(fields["quantity"])
                    if fields["sku"] not in AGENT_SKUS or not fields["vendor"] or quantity <= 0 or not fields["reason"]: raise ValueError()
                    status = "pending_review"
                    with sqlite3.connect(dbfile,timeout=10) as db:
                        db.execute("INSERT INTO restock_drafts(sku,vendor,quantity,reason,status,created_utc) VALUES(?,?,?,?,?,?)",
                          (fields["sku"],fields["vendor"],quantity,fields["reason"],status,datetime.now(timezone.utc).isoformat()))
                        db.commit()
                elif path == "/receive/save":
                    quantity = int(fields["quantity"])
                    if fields["sku"] not in {r[0] for r in _PRODUCTS} or not all(fields[k] for k in ("lot","bin_location","warehouse","slip_id")) or quantity <= 0: raise ValueError()
                    with sqlite3.connect(dbfile,timeout=10) as db:
                        db.execute("INSERT INTO receipts(sku,lot,quantity,bin_location,warehouse,slip_id,created_utc) VALUES(?,?,?,?,?,?,?)",
                          (fields["sku"],fields["lot"],quantity,fields["bin_location"],fields["warehouse"],fields["slip_id"],datetime.now(timezone.utc).isoformat()))
                        db.execute("UPDATE inventory SET on_hand=on_hand+? WHERE sku=?",(quantity,fields["sku"]))
                        db.commit()
                else:
                    self.send(404,b"Not found","text/plain; charset=utf-8"); return
            except (UnicodeDecodeError,ValueError,sqlite3.Error):
                self.send(400,b"Complete the required fields with valid quantities.","text/plain; charset=utf-8"); return
            self.send(303,b"", "text/plain; charset=utf-8", {"Location":"/dashboard?saved=1"})

    return ThreadingHTTPServer((host,port),Handler)


def _rows_from_table(db_path: str, table_name: str) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as db:
        return _rows(db,f"SELECT * FROM {table_name} ORDER BY 1")

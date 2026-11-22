"""EC2-C09: FinTech Multi-Currency Settlement Cutover, Shared Git/Port :19190, Clipboard & Open Calc.

Track 2 — Shared Git Repo, Live Singleton Port :19190, HttpOnly Ops Console, Clipboard & Calc Split-Brain.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    read_json_safe,
    reload_open_libreoffice_docs,
    render_scanned_document_png,
    set_x11_clipboard,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "EC2-C09"
PORTAL_PORT = 19109
APP_PORT = 19190
DESK_TAG = "DESK-CUTOVER-NY4-882"
WEBHOOK_SECRET = "whsec_atlas_cutover_2026_hmac99"
CLEARING_CLIPBOARD_SEAL = make_opaque_seal("ec2_c09", "FX_CORRIDOR_SCHEDULE:TREASURY_WHOLESALE_BPS")
RELEASE_CLIPBOARD_SEAL = make_opaque_seal("ec2_c09", "VALID_CHARGEBACK:NATIVE_EXACT")

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "FinTech Multi-Currency Settlement Cutover, Shared Git/Port :19190, HMAC Webhook & Open Calc",
    "domain": "FinTech Payment Clearing, Release Engineering & Ledger Security",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "single_instance_port_and_git_branch_race",
        "libreoffice_calc_dirty_buffer_split_brain",
        "x11_clipboard_release_seal_transaction",
        "bidirectional_regulatory_liquidity_buffer",
    ),
    "roles": ("clearing_engine_dev", "dispute_security_dev"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (APP_PORT,),
    "open_gui_docs": (
        ("/workspace/settlement_cutover/Daily_Nostro_Recon.xlsx", DESK_TAG, "calc"),
    ),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

FX_TO_USD = {"USD": Decimal("1.00"), "EUR": Decimal("1.08"), "JPY": Decimal("0.0068"), "KWD": Decimal("3.25")}
MINOR_DIVISOR = {"USD": Decimal("100"), "EUR": Decimal("100"), "JPY": Decimal("1"), "KWD": Decimal("1000")}
SWEEP_RANGE_USD = (38000.0, 56000.0)
COLLATERAL_RANGE_USD = (23000.0, 41000.0)
TOTAL_BUFFER_BAND_USD = (78600.0, 80800.0)


def compute_net_usd_reference(minor_units: int, currency: str) -> tuple[float, float]:
    major = Decimal(int(minor_units)) / MINOR_DIVISOR[currency]
    gross_usd = (major * FX_TO_USD[currency]).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    base_bps = Decimal("0.0016") if gross_usd >= Decimal("75000.00") else (Decimal("0.0024") if gross_usd >= Decimal("20000.00") else Decimal("0.0031"))
    xb_bps = Decimal("0.0000") if currency == "USD" else Decimal("0.0007")
    fee_usd = (gross_usd * (base_bps + xb_bps)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return float(gross_usd), float(gross_usd - fee_usd)


def _generate_settlement_txs() -> tuple[list[tuple], float, float]:
    rng = random.Random(20260404)
    txs: list[tuple] = []
    tot_g, tot_n = Decimal("0.00"), Decimal("0.00")
    ccys = ("USD", "EUR", "JPY", "KWD")
    for i in range(1, 421):
        ccy = ccys[i % 4]
        minor = rng.randint(250000, 14500000) if ccy == "JPY" else (rng.randint(900000, 32000000) if ccy == "KWD" else rng.randint(140000, 9600000))
        st = "DUPLICATE_BATCH" if i % 15 == 0 else ("SANCTIONS_HOLD" if i % 23 == 0 else ("REVERSED_REFUND" if i % 19 == 0 else "SETTLED"))
        txs.append((f"TX-{i:04d}", ccy, minor, st))
        if st == "SETTLED":
            g, n = compute_net_usd_reference(minor, ccy)
            tot_g += Decimal(f"{g:.2f}")
            tot_n += Decimal(f"{n:.2f}")
    return txs, float(tot_g), float(tot_n)


def _generate_dispute_cases() -> tuple[list[tuple[str, str, float, str]], float]:
    rng = random.Random(20260419)
    cases: list[tuple[str, str, float, str]] = []
    valid_sum = Decimal("0.00")
    ccys = ("USD", "EUR", "JPY", "KWD")
    rulings = ("VALID_CHARGEBACK", "VALID_CHARGEBACK", "MERCHANT_WON", "VOID_DUPLICATE")
    for idx in range(1, 41):
        ccy = ccys[idx % 4]
        rul = rulings[(idx * 3) % 4]
        amt = float(rng.randint(80, 420) * 1000) if ccy == "JPY" else (round(rng.randint(250, 1850) + rng.choice((0.125, 0.250, 0.500, 0.750)), 3) if ccy == "KWD" else round(rng.randint(650, 4800) + rng.choice((0.25, 0.50, 0.75, 0.00)), 2))
        cases.append((f"DSP-{400 + idx}", ccy, amt, rul))
        if rul == "VALID_CHARGEBACK":
            valid_sum += (Decimal(str(amt)) * FX_TO_USD[ccy]).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return cases, float(valid_sum)


_, TRUE_GROSS_BATCH_USD, TRUE_NET_BATCH_USD = _generate_settlement_txs()
DISPUTE_CASES, TRUE_VALID_CHARGEBACK_USD = _generate_dispute_cases()

BUGGY_NETTING_PY = """from decimal import Decimal
FX_TO_USD = {"USD": Decimal("1.00"), "EUR": Decimal("1.08"), "JPY": Decimal("0.0068"), "KWD": Decimal("3.25")}
def compute_tx_net_usd(minor_units: int, currency: str) -> tuple[float, float]:
    major = Decimal(int(minor_units)) / Decimal("100")
    gross_usd = float(round(major * FX_TO_USD[currency], 2))
    fee_usd = float(round(gross_usd * 0.0024, 2))
    return gross_usd, round(gross_usd - fee_usd, 2)
"""

FIXED_NETTING_PY = """from decimal import Decimal, ROUND_HALF_EVEN
FX_TO_USD = {"USD": Decimal("1.00"), "EUR": Decimal("1.08"), "JPY": Decimal("0.0068"), "KWD": Decimal("3.25")}
MINOR_DIVISOR = {"USD": Decimal("100"), "EUR": Decimal("100"), "JPY": Decimal("1"), "KWD": Decimal("1000")}
def compute_tx_net_usd(minor_units: int, currency: str) -> tuple[float, float]:
    major = Decimal(int(minor_units)) / MINOR_DIVISOR[currency]
    gross_usd = (major * FX_TO_USD[currency]).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    base_bps = Decimal("0.0016") if gross_usd >= Decimal("75000.00") else (Decimal("0.0024") if gross_usd >= Decimal("20000.00") else Decimal("0.0031"))
    xb_bps = Decimal("0.0000") if currency == "USD" else Decimal("0.0007")
    fee_usd = (gross_usd * (base_bps + xb_bps)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return float(gross_usd), float(gross_usd - fee_usd)
"""

INITIAL_SERVER_PY = f"""from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from app.netting import compute_tx_net_usd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "var" / "settlement.db"

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_a): return
    def _send(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self) -> None:
        if self.path == "/health": self._send(200, {{"ok": True}}); return
        if self.path == "/api/settle/summary":
            with sqlite3.connect(str(DB_PATH)) as conn:
                rows = conn.execute("SELECT currency, minor_units, status FROM clearing_txs").fetchall()
            g_sum, n_sum = 0.0, 0.0
            for ccy, mu, _st in rows:
                g, n = compute_tx_net_usd(mu, ccy); g_sum += g; n_sum += n
            self._send(200, {{"gross_usd": round(g_sum, 2), "net_usd": round(n_sum, 2)}}); return
        self._send(404, {{"error": "not found"}})
    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n > 0 else b"{{}}"
        body = json.loads(raw.decode("utf-8"))
        if self.path == "/api/webhook/chargeback":
            self._send(200, {{"ok": True, "event_id": body.get("event_id")}}); return
        self._send(404, {{"error": "not found"}})

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", {APP_PORT})).serve_forever() if False else ThreadingHTTPServer(("127.0.0.1", {APP_PORT}), Handler).serve_forever()
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    dev_a = "\n".join([
        f"# Multi-Currency Settlement Cutover Work Order — {b}clearing_engine_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Remediate the multi-currency clearing engine on {b}http://127.0.0.1:{APP_PORT}{b} ({b}/workspace/settlement_cutover/repo{b}, branch {b}main{b}) and update {b}Daily_Nostro_Recon.xlsx{b} (open in Calc with NY4 tag in {b}Netting_Summary!C1{b}) alongside {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}repo/Clearing_Cutover_Spec.md{b} and {b}scans/risk_committee_memo.png{b}, fix {b}app/netting.py{b} and {b}/api/settle/summary{b} in {b}app/server.py{b}, commit cleanly to Git {b}main{b}, and restart port {b}{APP_PORT}{b}.",
        f"2. In the Ops Console ({b}FILTER = FX_CORRIDOR_SCHEDULE{b}, {b}BASIS = TREASURY_WHOLESALE_BPS{b}), copy the Clearing Engine Seal to the clipboard for {b}Netting_Summary!B5{b}; populate {b}Netting_Summary!B2:B5{b} (formula {b}=B2-B3{b} in {b}B4{b}) and size only {b}Capital_Buffer!B2{b} so {b}Capital_Buffer!B4{b} lands in {b}[78600.0, 80800.0] USD{b}, preserving {b}Netting_Summary!C1{b}.",
        "",
    ])
    dev_b = "\n".join([
        f"# Dispute Webhook Security & Reserve Work Order — {b}dispute_security_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Harden {b}POST /api/webhook/chargeback{b} on {b}http://127.0.0.1:{APP_PORT}{b} ({b}/workspace/settlement_cutover/repo{b}, branch {b}main{b}) and reconcile dispute collateral in {b}Daily_Nostro_Recon.xlsx{b} (open in Calc with NY4 tag in {b}Netting_Summary!C1{b}) alongside {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Implement timestamp skew check ({b}<=300s{b}), HMAC-SHA256 verification, {b}409{b} duplicate {b}event_id{b} replay guard, and balanced {b}dispute_ledger{b} posting in {b}app/server.py{b} per {b}Clearing_Cutover_Spec.md{b}; commit cleanly to Git {b}main{b} and restart port {b}{APP_PORT}{b}.",
        f"2. In the Ops Console ({b}FILTER = VALID_CHARGEBACK{b}, {b}BASIS = NATIVE_EXACT{b}), export {b}/home/user/Downloads/ops_dispute_queue.csv{b}, copy the Cutover Authorization Token to {b}Dispute_Holdbacks!B3{b} and commit it in {b}repo/RELEASE_ATTESTATION.txt{b}, enter {b}VALID_CHARGEBACK{b} USD total in {b}Dispute_Holdbacks!B2{b}, and size only {b}Capital_Buffer!B3{b} so {b}Capital_Buffer!B4{b} lands in {b}[78600.0, 80800.0] USD{b}, preserving {b}Netting_Summary!C1{b}.",
        "",
    ])
    return {"clearing_engine_dev": dev_a, "dispute_security_dev": dev_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    b = chr(96)
    ws = next(iter(workspace_map.values()))
    sc = ws / "settlement_cutover"
    repo = sc / "repo"
    (sc / "scans").mkdir(parents=True, exist_ok=True)
    for d in ("app", "config", "var"):
        (repo / d).mkdir(parents=True, exist_ok=True)
    (repo / "app/__init__.py").write_text("", encoding="utf-8")
    (repo / "app/netting.py").write_text(BUGGY_NETTING_PY, encoding="utf-8")
    (repo / "app/server.py").write_text(INITIAL_SERVER_PY, encoding="utf-8")
    (repo / "config/webhook_key.txt").write_text(WEBHOOK_SECRET + "\n", encoding="utf-8")
    (repo / "RELEASE_ATTESTATION.txt").write_text("PENDING_CUTOVER_TOKEN\n", encoding="utf-8")
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\nvar/\n", encoding="utf-8")

    (repo / "Clearing_Cutover_Spec.md").write_text(
        "\n".join([
            "# Atlas Clearinghouse — Cutover & Webhook Security Specification",
            f"1. ISO-4217 Minor Units & FX: {b}USD(100, 1.00){b}, {b}EUR(100, 1.08){b}, {b}JPY(1, 0.0068){b}, {b}KWD(1000, 3.25){b}; quantize {b}gross_usd{b} to {b}0.01{b} via {b}ROUND_HALF_EVEN{b}.",
            f"2. Base fee: {b}16 bps (>=75000){b}, {b}24 bps (20000..74999.99){b}, {b}31 bps (<20000){b} plus cross-border surcharge in {b}../scans/risk_committee_memo.png{b}; quantize {b}fee_usd{b} via {b}ROUND_HALF_EVEN{b}. Aggregate ONLY settled rows in {b}/api/settle/summary{b}.",
            f"3. Webhook ({b}POST /api/webhook/chargeback{b}): require integer {b}X-Webhook-Timestamp{b} within 300s and {b}X-Webhook-Signature == 'sha256=' + hmac_sha256(key, ts + '.' + raw_body){b} (else {b}401{b}); reject duplicate {b}event_id{b} in {b}processed_webhooks{b} with {b}409{b}; insert {b}('2200_CHARGEBACK_RESERVE', amount_cents, 0){b} and {b}('1010_MERCHANT_PAYABLE', 0, amount_cents){b} into {b}dispute_ledger{b}.",
        ]),
        encoding="utf-8",
    )
    render_scanned_document_png(
        sc / "scans" / "risk_committee_memo.png",
        "TREASURY RISK COMMITTEE RULING RC-2026-11: SURCHARGE & BUFFER",
        [
            "1. Non-USD Cross-Border Surcharge (EUR, JPY, KWD): add +7 bps (+0.0007)",
            "   to base interchange rate before quantizing fee_usd (USD adds +0 bps).",
            "2. Daily Nostro Regulatory Buffer (Capital_Buffer):",
            "   - B2 Intraday_Liquidity_Sweep_USD : [38,000.0, 56,000.0] USD",
            "   - B3 Dispute_Collateral_Buffer_USD: [23,000.0, 41,000.0] USD",
            "   - B4 Total_Regulatory_Buffer_USD (=B2+B3) in [78,600.0, 80,800.0] USD.",
        ],
    )
    txs, _, _ = _generate_settlement_txs()
    conn = sqlite3.connect(str(repo / "var/settlement.db"))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE clearing_txs (tx_id TEXT PRIMARY KEY, currency TEXT, minor_units INTEGER, status TEXT)")
    conn.execute("CREATE TABLE processed_webhooks (event_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE dispute_ledger (event_id TEXT, account TEXT, debit_cents INTEGER, credit_cents INTEGER)")
    conn.executemany("INSERT INTO clearing_txs VALUES (?,?,?,?)", txs)
    conn.commit(); conn.close()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "ops@atlas.internal"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Atlas Bot"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial pre-cutover baseline"], cwd=repo, check=True, capture_output=True)

    write_multisheet_xlsx(
        sc / "Daily_Nostro_Recon.xlsx",
        [
            ("Netting_Summary", [["Item", "Amount_USD", ""], ["Gross_Settled_USD", 0.0, ""], ["Net_Settled_USD", 0.0, ""], ["Total_Fee_USD", ("=B2-B3", 0.0), ""], ["Ops_Clearing_Seal", "PENDING_CLEARING_SEAL", ""]]),
            ("Dispute_Holdbacks", [["Item", "Amount_USD"], ["Valid_Chargebacks_USD", 0.0], ["Cutover_Auth_Token", "PENDING_CUTOVER_TOKEN"]]),
            ("Capital_Buffer", [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", 54200.0], ["Dispute_Collateral_Buffer_USD", 39500.0], ["Total_Regulatory_Buffer_USD", ("=B2+B3", 93700.0)]]),
        ],
    )
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_ops_html(flt: str, ab: str) -> str:
    if flt == "FX_CORRIDOR_SCHEDULE":
        rows = "<tr><td>USD</td><td>100</td><td>1.0000</td></tr><tr><td>EUR</td><td>100</td><td>1.0800</td></tr><tr><td>JPY</td><td>1</td><td>0.0068</td></tr><tr><td>KWD</td><td>1000</td><td>3.2500</td></tr>"
    else:
        sub = [c for c in DISPUTE_CASES if flt == "ALL" or c[3] == flt][:6]
        rows = "".join(f"<tr><td>{cid}</td><td>{ccy}</td><td>{amt if ab=='NATIVE_EXACT' else round(float(Decimal(str(amt))*FX_TO_USD[ccy])/100)*100}</td><td>{rul}</td></tr>" for cid, ccy, amt, rul in sub)
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>Atlas Ops</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f8fafc;}}header{{background:#0f172a;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;}}
.bar{{background:#e2e8f0;padding:10px 18px;display:flex;gap:8px;flex-wrap:wrap;}}button{{padding:6px 10px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-top:10px;}}th,td{{border:1px solid #cbd5e1;padding:7px 10px;}}</style></head>
<body>
<header><strong>Atlas Clearinghouse Ops</strong><span style="font-family:monospace;">FILTER={flt} | BASIS={ab}</span></header>
<div class="bar">
  <button onclick="setO({{filter:'ALL'}})">ALL</button>
  <button onclick="setO({{filter:'VALID_CHARGEBACK'}})">VALID_CHARGEBACK</button>
  <button onclick="setO({{filter:'FX_CORRIDOR_SCHEDULE'}})">FX_CORRIDOR_SCHEDULE</button>
  <button onclick="setO({{amount_basis:'APPROX_USD_PREVIEW'}})">APPROX_USD_PREVIEW</button>
  <button onclick="setO({{amount_basis:'TREASURY_WHOLESALE_BPS'}})">TREASURY_WHOLESALE_BPS</button>
  <button onclick="setO({{amount_basis:'NATIVE_EXACT'}})">NATIVE_EXACT</button>
  <button onclick="expO()">Export CSV (/home/user/Downloads/ops_dispute_queue.csv)</button>
  <button onclick="cpO()">Copy Active Seal / Token to Clipboard</button>
  <span id="msg" style="font-family:monospace;font-size:12px;">Ready</span>
</div>
<main style="padding:14px 18px;"><table><tbody>{rows}</tbody></table></main>
<script>
async function setO(p){{await fetch('/api/ops/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(p)}});location.reload();}}
async function expO(){{const r=await fetch('/api/ops/export_csv',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Exported ['+d.amount_basis+']';}}
async function cpO(){{const r=await fetch('/api/ops/copy_token',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Copied ['+d.filter+'/'+d.amount_basis+']';}}
</script></body></html>"""


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    ws = next(iter(workspace_map.values()))
    repo = ws / "settlement_cutover" / "repo"
    subprocess.Popen(
        ["su", "-s", "/bin/bash", "user", "-c", f"cd {repo} && PYTHONPATH={repo} exec python3 app/server.py >/tmp/ec2_c09_srv.log 2>&1 </dev/null"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "filter": "ALL",
        "amount_basis": "APPROX_USD_PREVIEW",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "contention_events": 0,
    }
    write_json(state_p, pstate)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a: Any) -> None: return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec2_c09_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health": self._send_json(200, {"ok": True}); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_secret:
                self.send_response(302); self.send_header("Set-Cookie", f"ec2_c09_sso={sso_cookie}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not self._authed(): self._send_json(401, {"error": "Unauthorized"}); return
            with lock:
                raw = _render_ops_html(pstate["filter"], pstate["amount_basis"]).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_POST(self) -> None:
            if not self._authed(): self._send_json(401, {"error": "Unauthorized"}); return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            if self.path == "/api/ops/state":
                with lock:
                    changed = False
                    if body.get("filter") in ("ALL", "VALID_CHARGEBACK", "FX_CORRIDOR_SCHEDULE") and pstate["filter"] != body["filter"]:
                        pstate["filter"] = body["filter"]; changed = True
                    if body.get("amount_basis") in ("APPROX_USD_PREVIEW", "TREASURY_WHOLESALE_BPS", "NATIVE_EXACT") and pstate["amount_basis"] != body["amount_basis"]:
                        pstate["amount_basis"] = body["amount_basis"]; changed = True
                    if changed:
                        pstate["session_switches"] += 1; write_json(state_p, pstate)
                    self._send_json(200, {"ok": True, "filter": pstate["filter"], "amount_basis": pstate["amount_basis"]})
                return
            if self.path == "/api/ops/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 3.5)
                dl_p = Path("/home/user/Downloads/ops_dispute_queue.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    flt, ab = pstate["filter"], pstate["amount_basis"]
                    if flt == "FX_CORRIDOR_SCHEDULE" and ab == "TREASURY_WHOLESALE_BPS":
                        lines = ["currency,minor_divisor,fx_to_usd", "USD,100,1.0000", "EUR,100,1.0800", "JPY,1,0.0068", "KWD,1000,3.2500"]
                    else:
                        lines = ["case_id,currency,amount,adjudication"]
                        for cid, ccy, amt, rul in DISPUTE_CASES:
                            vs = (f"{amt:.3f}" if ccy == "KWD" else f"{amt:.2f}") if ab == "NATIVE_EXACT" else f"{round(float(Decimal(str(amt))*FX_TO_USD[ccy])/100)*100:.0f}"
                            lines.append(f"{cid},{ccy},{vs},{rul}")
                    if dl_p.exists(): pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8"); os.chmod(dl_p, 0o644)
                    pstate["download_exports"] += 1; write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "amount_basis": ab})
                return
            if self.path == "/api/ops/copy_token":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.2 if is_adm else 1.2)
                with lock:
                    flt, ab = pstate["filter"], pstate["amount_basis"]
                    tok = make_opaque_seal("ec2_c09", f"{flt}:{ab}")
                    pstate["clipboard_copies"] += 1; write_json(state_p, pstate)
                set_x11_clipboard(tok)
                self._send_json(200, {"ok": True, "filter": flt, "amount_basis": ab})
                return
            self._send_json(404, {"error": "Not found"})

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"mode": "studio_sso", "url": f"http://127.0.0.1:{port}/?sso_boot={boot_secret}"}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    from tasks.exam_contention_v2.c06_impress_calc_actuarial import boot_desktop_apps as _boot_sso
    _boot_sso(workspace_map, state_dir)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    sc = ws / "settlement_cutover"
    repo = sc / "repo"
    xp = sc / "Daily_Nostro_Recon.xlsx"

    st_cp = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    git_clean = (st_cp.returncode == 0 and not st_cp.stdout.strip())
    att_txt = (repo / "RELEASE_ATTESTATION.txt").read_text(encoding="utf-8", errors="replace") if (repo / "RELEASE_ATTESTATION.txt").is_file() else ""

    gross_ok, net_ok, wh_auth_ok, wh_replay_ok, wh_ledger_ok = False, False, False, False, False
    srv_proc = None
    try:
        subprocess.run(["bash", "-lc", "pkill -f 'app/server.py' >/dev/null 2>&1 || true; sleep 0.2"], capture_output=True, timeout=5)
        srv_proc = subprocess.Popen(["python3", str(repo / "app/server.py")], cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(25):
            try:
                with socket.create_connection(("127.0.0.1", APP_PORT), timeout=0.3): break
            except OSError: time.sleep(0.15)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{APP_PORT}/api/settle/summary", timeout=5) as r:
                sd = json.loads(r.read().decode("utf-8"))
            gross_ok = abs(float(sd.get("gross_usd", -1)) - TRUE_GROSS_BATCH_USD) <= 1.5
            net_ok = abs(float(sd.get("net_usd", -1)) - TRUE_NET_BATCH_USD) <= 1.5
        except Exception:
            pass

        ev_id = "evt_g_" + secrets.token_hex(4)
        payload = json.dumps({"event_id": ev_id, "amount_cents": 12345}).encode("utf-8")
        now_ts, stale_ts = str(int(time.time())), str(int(time.time()) - 900)
        stale_sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), stale_ts.encode() + b"." + payload, hashlib.sha256).hexdigest()
        s_401, b_401 = False, False
        for hdrs, flag_n in (
            ({"Content-Type": "application/json", "X-Webhook-Timestamp": stale_ts, "X-Webhook-Signature": stale_sig}, "s"),
            ({"Content-Type": "application/json", "X-Webhook-Timestamp": now_ts, "X-Webhook-Signature": "sha256=bad"}, "b"),
        ):
            try:
                urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{APP_PORT}/api/webhook/chargeback", data=payload, headers=hdrs, method="POST"), timeout=5)
            except urllib.error.HTTPError as he:
                if he.code == 401:
                    if flag_n == "s": s_401 = True
                    else: b_401 = True
            except Exception:
                pass
        wh_auth_ok = (s_401 and b_401)

        good_sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), now_ts.encode() + b"." + payload, hashlib.sha256).hexdigest()
        g_req = urllib.request.Request(f"http://127.0.0.1:{APP_PORT}/api/webhook/chargeback", data=payload, headers={"Content-Type": "application/json", "X-Webhook-Timestamp": now_ts, "X-Webhook-Signature": good_sig}, method="POST")
        try:
            with urllib.request.urlopen(g_req, timeout=5) as r2:
                ok_200 = (r2.status == 200)
            try:
                urllib.request.urlopen(g_req, timeout=5)
            except urllib.error.HTTPError as he2:
                wh_replay_ok = bool(ok_200 and he2.code == 409)
        except Exception:
            pass
        with sqlite3.connect(str(repo / "var/settlement.db")) as conn:
            l_rows = conn.execute("SELECT account, debit_cents, credit_cents FROM dispute_ledger WHERE event_id=?", (ev_id,)).fetchall()
        wh_ledger_ok = sorted(l_rows) == sorted([("2200_CHARGEBACK_RESERVE", 12345, 0), ("1010_MERCHANT_PAYABLE", 0, 12345)])
    finally:
        if srv_proc:
            srv_proc.terminate()
            try: srv_proc.wait(timeout=3)
            except Exception: srv_proc.kill()

    raw_sh = read_multisheet_xlsx(xp) if xp.is_file() else {}
    ev_sh = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}

    def _v(sh: str, ref: str) -> float:
        val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return float(val) if isinstance(val, (int, float)) else -999999.0

    def _s(sh: str, ref: str) -> str:
        val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return str(val or "").strip()

    def _f(sh: str, ref: str) -> bool:
        return bool(((raw_sh.get(sh) or {}).get(ref) or {}).get("formula"))

    checks_a: list[tuple[str, bool, float, str]] = [
        ("summary_gross_usd", gross_ok, 0.25, "/api/settle/summary gross_usd mismatch"),
        ("summary_net_usd", net_ok, 0.25, "/api/settle/summary net_usd mismatch (+7bps/settled filter)"),
        ("netting_sheet_sync", abs(_v("Netting_Summary", "B2") - TRUE_GROSS_BATCH_USD) <= 2.0 and abs(_v("Netting_Summary", "B3") - TRUE_NET_BATCH_USD) <= 2.0 and _f("Netting_Summary", "B4"), 0.20, "Netting_Summary B2:B4 mismatch"),
        ("clearing_seal", _s("Netting_Summary", "B5") == CLEARING_CLIPBOARD_SEAL, 0.20, "Netting_Summary!B5 missing Ops_Clearing_Seal"),
        ("sweep_bounds", SWEEP_RANGE_USD[0] <= _v("Capital_Buffer", "B2") <= SWEEP_RANGE_USD[1], 0.10, "Intraday_Liquidity_Sweep out of range"),
    ]
    checks_b: list[tuple[str, bool, float, str]] = [
        ("webhook_hmac_and_skew", wh_auth_ok, 0.20, "Webhook failed 401 on stale timestamp or invalid HMAC"),
        ("webhook_idempotent_409", wh_replay_ok, 0.20, "Webhook failed 200/409 idempotency check"),
        ("dispute_double_entry", wh_ledger_ok, 0.15, "dispute_ledger unbalanced"),
        ("valid_chargebacks_usd", abs(_v("Dispute_Holdbacks", "B2") - TRUE_VALID_CHARGEBACK_USD) <= 1.5, 0.20, "Dispute_Holdbacks!B2 mismatch"),
        ("cutover_auth_token", RELEASE_CLIPBOARD_SEAL in att_txt and _s("Dispute_Holdbacks", "B3") == RELEASE_CLIPBOARD_SEAL, 0.15, "Missing Cutover_Auth_Token in B3 or RELEASE_ATTESTATION.txt"),
        ("collateral_bounds", COLLATERAL_RANGE_USD[0] <= _v("Capital_Buffer", "B3") <= COLLATERAL_RANGE_USD[1], 0.10, "Dispute_Collateral_Buffer out of range"),
    ]
    tot_b = _v("Capital_Buffer", "B4")
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("git_main_clean", git_clean, 0.08, "Git working tree dirty"),
        ("calc_ny4_tag", _s("Netting_Summary", "C1") == DESK_TAG, 0.06, f"Lost {DESK_TAG} in C1"),
        ("regulatory_buffer_band", _f("Capital_Buffer", "B4") and TOTAL_BUFFER_BAND_USD[0] <= tot_b <= TOTAL_BUFFER_BAND_USD[1], 0.11, f"Total_Regulatory_Buffer={tot_b} outside {list(TOTAL_BUFFER_BAND_USD)}"),
        ("no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.05, "Open Calc held stale unsaved buffer"),
    ]
    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.90,
    )


WEBHOOK_SNIPPET = """        if self.path == "/api/webhook/chargeback":
            import hashlib, hmac, time
            key = (ROOT / "config/webhook_key.txt").read_text(encoding="utf-8").strip().encode("utf-8")
            ts_hdr = self.headers.get("X-Webhook-Timestamp") or ""
            sig = self.headers.get("X-Webhook-Signature") or ""
            try: ts_val = int(ts_hdr)
            except ValueError: self._send(401, {"error": "bad ts"}); return
            if abs(time.time() - ts_val) > 300: self._send(401, {"error": "stale"}); return
            exp = "sha256=" + hmac.new(key, ts_hdr.encode() + b"." + raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, exp): self._send(401, {"error": "bad sig"}); return
            ev_id, amt = str(body.get("event_id") or ""), int(body.get("amount_cents") or 0)
            with sqlite3.connect(str(DB_PATH)) as conn:
                if conn.execute("SELECT 1 FROM processed_webhooks WHERE event_id=?", (ev_id,)).fetchone():
                    self._send(409, {"error": "dup"}); return
                conn.execute("INSERT INTO processed_webhooks VALUES (?)", (ev_id,))
                conn.execute("INSERT INTO dispute_ledger VALUES (?,?,?,?)", (ev_id, "2200_CHARGEBACK_RESERVE", amt, 0))
                conn.execute("INSERT INTO dispute_ledger VALUES (?,?,?,?)", (ev_id, "1010_MERCHANT_PAYABLE", 0, amt))
                conn.commit()
            self._send(200, {"ok": True, "event_id": ev_id}); return"""


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    assert role in ("clearing_engine_dev", "dispute_security_dev")
    ws = next(iter(workspace_map.values()))
    sc = ws / "settlement_cutover"
    repo = sc / "repo"
    xp = sc / "Daily_Nostro_Recon.xlsx"
    adm_p = Path("/opt/ec2_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_a = (role == "clearing_engine_dev")
        srv_p = repo / "app/server.py"
        srv_src = srv_p.read_text(encoding="utf-8")
        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev["Netting_Summary"].get("C1") or {}).get("value") or DESK_TAG)
        cur_sw = float((ev["Capital_Buffer"].get("B2") or {}).get("value") or 54200.0)
        cur_co = float((ev["Capital_Buffer"].get("B3") or {}).get("value") or 39500.0)

        if is_a:
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/state", data=json.dumps({"filter": "FX_CORRIDOR_SCHEDULE", "amount_basis": "TREASURY_WHOLESALE_BPS"}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/copy_token", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
            clr_seal = get_x11_clipboard()
            (repo / "app/netting.py").write_text(FIXED_NETTING_PY, encoding="utf-8")
            srv_p.write_text(srv_src.replace("SELECT currency, minor_units, status FROM clearing_txs", "SELECT currency, minor_units, status FROM clearing_txs WHERE status='SETTLED'"), encoding="utf-8")
            new_sw = round(max(SWEEP_RANGE_USD[0], min(SWEEP_RANGE_USD[1], 79700.0 - cur_co)), 2)
            update_single_sheet_xlsx(xp, "Netting_Summary", [["Item", "Amount_USD", desk_c1], ["Gross_Settled_USD", TRUE_GROSS_BATCH_USD, ""], ["Net_Settled_USD", TRUE_NET_BATCH_USD, ""], ["Total_Fee_USD", ("=B2-B3", round(TRUE_GROSS_BATCH_USD - TRUE_NET_BATCH_USD, 2)), ""], ["Ops_Clearing_Seal", clr_seal, ""]])
            update_single_sheet_xlsx(xp, "Capital_Buffer", [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", new_sw], ["Dispute_Collateral_Buffer_USD", cur_co], ["Total_Regulatory_Buffer_USD", ("=B2+B3", round(new_sw + cur_co, 2))]])
        else:
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/state", data=json.dumps({"filter": "VALID_CHARGEBACK", "amount_basis": "NATIVE_EXACT"}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/copy_token", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
            rel_tok = get_x11_clipboard()
            (repo / "RELEASE_ATTESTATION.txt").write_text(rel_tok + "\n", encoding="utf-8")
            old_wh = '        if self.path == "/api/webhook/chargeback":\n            self._send(200, {"ok": True, "event_id": body.get("event_id")}); return'
            if old_wh in srv_src:
                srv_p.write_text(srv_src.replace(old_wh, WEBHOOK_SNIPPET), encoding="utf-8")
            new_co = round(max(COLLATERAL_RANGE_USD[0], min(COLLATERAL_RANGE_USD[1], 79700.0 - cur_sw)), 2)
            update_single_sheet_xlsx(xp, "Dispute_Holdbacks", [["Item", "Amount_USD"], ["Valid_Chargebacks_USD", TRUE_VALID_CHARGEBACK_USD], ["Cutover_Auth_Token", rel_tok]])
            update_single_sheet_xlsx(xp, "Capital_Buffer", [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", cur_sw], ["Dispute_Collateral_Buffer_USD", new_co], ["Total_Regulatory_Buffer_USD", ("=B2+B3", round(cur_sw + new_co, 2))]])

        subprocess.run(["git", "-c", "safe.directory=*", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "-c", "safe.directory=*", "commit", "--allow-empty", "-m", f"Update: {role}"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["bash", "-lc", "pkill -f 'app/server.py' >/dev/null 2>&1 || true; sleep 0.2"], capture_output=True, timeout=5)
        subprocess.Popen(["su", "-s", "/bin/bash", "user", "-c", f"cd {repo} && PYTHONPATH={repo} exec python3 app/server.py >/tmp/ec2_c09_srv.log 2>&1 </dev/null"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        reload_open_libreoffice_docs([xp])

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    ws = next(iter(workspace_map.values()))
    sc = ws / "settlement_cutover"
    repo = sc / "repo"
    xp = sc / "Daily_Nostro_Recon.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "server_v0.py"
        shutil.copy2(repo / "app/server.py", snap)
        solve_role("clearing_engine_dev", workspace_map, port, careful_conc=False)
        shutil.copy2(snap, repo / "app/server.py")
        solve_role("dispute_security_dev", workspace_map, port, careful_conc=False)
        update_single_sheet_xlsx(xp, "Capital_Buffer", [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", 40200.0], ["Dispute_Collateral_Buffer_USD", 25500.0], ["Total_Regulatory_Buffer_USD", ("=B2+B3", 65700.0)]])
        reload_open_libreoffice_docs([xp])
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)

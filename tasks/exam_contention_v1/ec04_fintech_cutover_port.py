"""EC-04: FinTech Multi-Currency Settlement Cutover, Shared Git/Port :18910, Clipboard & Open Calc Recon.

Contention Archetypes:
  1. Open LibreOffice Calc Dirty Buffer vs. Disk CLI Split-Brain (Daily_Nostro_Recon.xlsx with unsaved NY4 cutover tag).
  2. Cross-Step X11 Clipboard Cutover Seal Transaction.
  3. Single-Instance Process/Port (:18910) & Shared Git Working Tree / index.lock Race.
  4. Shared Authenticated Ops Portal (Native vs Preview Basis Toggle & Paginated 40-Row ~/Downloads/ops_dispute_queue.csv).
  5. Bidirectional Coupled Regulatory Buffer ([79200.0, 80800.0] USD).
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

from tasks.exam_contention_v1.common import (
    advisory_lock,
    find_unexpected_workspace_files,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    reload_open_libreoffice_window,
    render_scanned_document_png,
    set_x11_clipboard,
    verify_prompt_driver_and_ban_clean,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "EC-04"
PORTAL_PORT = 18804
APP_PORT = 18910
DESK_TAG = "DESK-CUTOVER-NY4-882"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "FinTech Settlement Service Cutover, Shared Git/Port :18910, HMAC Replay Guard & Open Calc Recon",
    "domain": "FinTech Payment Clearing, Full-Stack Release Engineering & Ledger Security",
    "archetypes": (
        "single_instance_port_and_git_branch_race",
        "libreoffice_calc_dirty_buffer_split_brain",
        "x11_clipboard_release_seal_transaction",
        "bidirectional_regulatory_liquidity_buffer",
    ),
    "roles": ("clearing_engine_dev", "dispute_security_dev"),
    "portal_port": PORTAL_PORT,
    "app_port": APP_PORT,
    "open_gui_doc": "/workspace/settlement_cutover/Daily_Nostro_Recon.xlsx",
    "open_gui_unsaved_tag": DESK_TAG,
    "conc_role_timeout_s": 1800,
    "seq_role_timeout_s": 1800,
}

WEBHOOK_SECRET = "whsec_atlas_cutover_2026_hmac99"
CLEARING_CLIPBOARD_SEAL = make_opaque_seal("ec04", "FX_CORRIDOR_SCHEDULE:TREASURY_WHOLESALE_BPS")
RELEASE_CLIPBOARD_SEAL = make_opaque_seal("ec04", "VALID_CHARGEBACK:NATIVE_EXACT")
ALLOWED_CUTOVER_FILES = {
    "Daily_Nostro_Recon.xlsx",
    "scans/risk_committee_memo.png",
    "repo/.gitignore",
    "repo/Clearing_Cutover_Spec.md",
    "repo/RELEASE_ATTESTATION.txt",
    "repo/app/__init__.py",
    "repo/app/netting.py",
    "repo/app/server.py",
    "repo/config/webhook_key.txt",
    "repo/var/settlement.db",
}

FX_TO_USD = {
    "USD": Decimal("1.00"),
    "EUR": Decimal("1.08"),
    "JPY": Decimal("0.0068"),
    "KWD": Decimal("3.25"),
}
MINOR_DIVISOR = {
    "USD": Decimal("100"),
    "EUR": Decimal("100"),
    "JPY": Decimal("1"),
    "KWD": Decimal("1000"),
}

SWEEP_RANGE_USD = (38000.0, 56000.0)
COLLATERAL_RANGE_USD = (23000.0, 41000.0)
TOTAL_BUFFER_BAND_USD = (78600.0, 80800.0)


def compute_net_usd_reference(minor_units: int, currency: str) -> tuple[float, float]:
    major = Decimal(int(minor_units)) / MINOR_DIVISOR[currency]
    gross_usd = (major * FX_TO_USD[currency]).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    if gross_usd >= Decimal("75000.00"):
        base_bps = Decimal("0.0016")
    elif gross_usd >= Decimal("20000.00"):
        base_bps = Decimal("0.0024")
    else:
        base_bps = Decimal("0.0031")
    xb_bps = Decimal("0.0000") if currency == "USD" else Decimal("0.0007")
    fee_usd = (gross_usd * (base_bps + xb_bps)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return float(gross_usd), float(gross_usd - fee_usd)


def _generate_settlement_txs() -> tuple[list[tuple], float, float]:
    rng = random.Random(20260404)
    txs: list[tuple] = []
    tot_gross = Decimal("0.00")
    tot_net = Decimal("0.00")
    ccys = ("USD", "EUR", "JPY", "KWD")
    for i in range(1, 421):
        ccy = ccys[i % 4]
        if ccy == "JPY":
            minor = rng.randint(250000, 14500000)
        elif ccy == "KWD":
            minor = rng.randint(900000, 32000000)
        else:
            minor = rng.randint(140000, 9600000)
        if i % 15 == 0:
            st = "DUPLICATE_BATCH"
        elif i % 23 == 0:
            st = "SANCTIONS_HOLD"
        elif i % 19 == 0:
            st = "REVERSED_REFUND"
        else:
            st = "SETTLED"
        txs.append((f"TX-{i:04d}", ccy, minor, st))
        if st == "SETTLED":
            g, n = compute_net_usd_reference(minor, ccy)
            tot_gross += Decimal(f"{g:.2f}")
            tot_net += Decimal(f"{n:.2f}")
    return txs, float(tot_gross), float(tot_net)


def _generate_dispute_cases() -> tuple[list[tuple[str, str, float, str]], float]:
    rng = random.Random(20260419)
    cases: list[tuple[str, str, float, str]] = []
    valid_sum = Decimal("0.00")
    ccys = ("USD", "EUR", "JPY", "KWD")
    rulings = ("VALID_CHARGEBACK", "VALID_CHARGEBACK", "MERCHANT_WON", "VOID_DUPLICATE")
    for idx in range(1, 41):
        ccy = ccys[idx % 4]
        rul = rulings[(idx * 3) % 4]
        if ccy == "JPY":
            amt = float(rng.randint(80, 420) * 1000)
        elif ccy == "KWD":
            amt = round(rng.randint(250, 1850) + rng.choice((0.125, 0.250, 0.500, 0.750)), 3)
        else:
            amt = round(rng.randint(650, 4800) + rng.choice((0.25, 0.50, 0.75, 0.00)), 2)
        cases.append((f"DSP-{400 + idx}", ccy, amt, rul))
        if rul == "VALID_CHARGEBACK":
            usd_v = (Decimal(str(amt)) * FX_TO_USD[ccy]).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            valid_sum += usd_v
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
    if gross_usd >= Decimal("75000.00"):
        base_bps = Decimal("0.0016")
    elif gross_usd >= Decimal("20000.00"):
        base_bps = Decimal("0.0024")
    else:
        base_bps = Decimal("0.0031")
    xb_bps = Decimal("0.0000") if currency == "USD" else Decimal("0.0007")
    fee_usd = (gross_usd * (base_bps + xb_bps)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return float(gross_usd), float(gross_usd - fee_usd)
"""

INITIAL_SERVER_PY = """from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"ok": True})
            return
        if self.path == "/api/settle/summary":
            with sqlite3.connect(str(DB_PATH)) as conn:
                rows = conn.execute("SELECT currency, minor_units, status FROM clearing_txs").fetchall()
            g_sum, n_sum = 0.0, 0.0
            for ccy, mu, _st in rows:
                g, n = compute_tx_net_usd(mu, ccy)
                g_sum += g
                n_sum += n
            self._send(200, {"gross_usd": round(g_sum, 2), "net_usd": round(n_sum, 2)})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n > 0 else b"{}"
        body = json.loads(raw.decode("utf-8"))
        if self.path == "/api/webhook/chargeback":
            self._send(200, {"ok": True, "event_id": body.get("event_id")})
            return
        self._send(404, {"error": "not found"})

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18910), Handler).serve_forever()
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    dev_a = "\n".join([
        f"# Multi-Currency Settlement Cutover Work Order — {b}clearing_engine_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the multi-currency clearing engine remediation and Nostro liquidity sizing in {b}/workspace/settlement_cutover{b}.",
        f"The clearing daemon runs on {b}http://127.0.0.1:{APP_PORT}{b} from Git repository {b}/workspace/settlement_cutover/repo{b} (branch {b}main{b}), while {b}/workspace/settlement_cutover/Daily_Nostro_Recon.xlsx{b} is open in LibreOffice Calc on the workstation (with an active NY4 cutover tag in {b}Netting_Summary!C1{b}) alongside the Clearinghouse Ops Console at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/settlement_cutover/repo/Clearing_Cutover_Spec.md{b} and risk memo {b}/workspace/settlement_cutover/scans/risk_committee_memo.png{b} for ISO-4217 minor-unit exponents, batch status exclusions, tiered interchange fees, cross-border FX surcharges, and rounding rules.",
        f"2. Remediate {b}app/netting.py{b} and {b}/api/settle/summary{b} in {b}app/server.py{b}, commit cleanly to Git {b}main{b} preserving all repository functionality, and ensure the live service on port {b}{APP_PORT}{b} serves the committed code.",
        f"3. In the Clearinghouse Ops Console ({b}http://127.0.0.1:{PORTAL_PORT}{b}), set {b}FILTER = FX_CORRIDOR_SCHEDULE{b} and {b}BASIS = TREASURY_WHOLESALE_BPS{b}, export the corridor schedule CSV, and copy the Clearing Engine Seal to the system clipboard for {b}Netting_Summary!B5{b}; populate {b}Netting_Summary{b} ({b}B2{b} gross settled USD, {b}B3{b} net settled USD, live formula {b}=B2-B3{b} in {b}B4{b}, seal in {b}B5{b}) and size only {b}Capital_Buffer!B2{b} ({b}Intraday_Liquidity_Sweep_USD{b}) in {b}Daily_Nostro_Recon.xlsx{b} so {b}Capital_Buffer!B4{b} satisfies the regulatory liquidity buffer requirement, preserving all sheets, formulas, and {b}Netting_Summary!C1{b}. Keep {b}/workspace/settlement_cutover{b} clean of extra scratch files (use {b}/tmp{b} for intermediate work).",
        "",
    ])

    dev_b = "\n".join([
        f"# Dispute Webhook Security & Reserve Work Order — {b}dispute_security_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Complete chargeback webhook authentication/idempotency hardening and dispute collateral reconciliation in {b}/workspace/settlement_cutover{b}.",
        f"The clearing daemon runs on {b}http://127.0.0.1:{APP_PORT}{b} from Git repository {b}/workspace/settlement_cutover/repo{b} (branch {b}main{b}), while {b}/workspace/settlement_cutover/Daily_Nostro_Recon.xlsx{b} is open in LibreOffice Calc on the workstation (with an active NY4 cutover tag in {b}Netting_Summary!C1{b}) alongside the Clearinghouse Ops Console at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/settlement_cutover/repo/Clearing_Cutover_Spec.md{b} and {b}/workspace/settlement_cutover/scans/risk_committee_memo.png{b}, then harden {b}POST /api/webhook/chargeback{b} in {b}app/server.py{b} (timestamp replay window, HMAC-SHA256 verification, duplicate {b}event_id{b} rejection, and double-entry {b}dispute_ledger{b} posting). Commit cleanly to Git {b}main{b} and ensure port {b}{APP_PORT}{b} serves the committed code.",
        f"2. From the Clearinghouse Ops Console ({b}http://127.0.0.1:{PORTAL_PORT}{b}), export the full 40-case dispute queue under exact native amounts, copy the Cutover Authorization Token to the system clipboard, paste/record it in {b}Dispute_Holdbacks!B3{b} of {b}Daily_Nostro_Recon.xlsx{b} and commit it in {b}/workspace/settlement_cutover/repo/RELEASE_ATTESTATION.txt{b} on {b}main{b}, and enter total USD {b}VALID_CHARGEBACK{b} exposure in {b}Dispute_Holdbacks!B2{b}.",
        f"3. Size only {b}Capital_Buffer!B3{b} ({b}Dispute_Collateral_Buffer_USD{b}) in {b}Daily_Nostro_Recon.xlsx{b} so {b}Capital_Buffer!B4{b} satisfies the regulatory liquidity buffer requirement, preserving all sheets, formulas, and {b}Netting_Summary!C1{b}. Keep {b}/workspace/settlement_cutover{b} clean of extra scratch files (use {b}/tmp{b} for intermediate work).",
        "",
    ])
    return {"clearing_engine_dev": dev_a, "dispute_security_dev": dev_b}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    b = chr(96)
    sc = workspace / "settlement_cutover"
    repo = sc / "repo"
    (sc / "scans").mkdir(parents=True, exist_ok=True)
    (repo / "app").mkdir(parents=True, exist_ok=True)
    (repo / "config").mkdir(parents=True, exist_ok=True)
    (repo / "var").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "netting.py").write_text(BUGGY_NETTING_PY, encoding="utf-8")
    (repo / "app" / "server.py").write_text(INITIAL_SERVER_PY, encoding="utf-8")
    (repo / "config" / "webhook_key.txt").write_text(WEBHOOK_SECRET + "\n", encoding="utf-8")
    (repo / "RELEASE_ATTESTATION.txt").write_text("PENDING_CUTOVER_TOKEN\n", encoding="utf-8")
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\nvar/\n", encoding="utf-8")

    (repo / "Clearing_Cutover_Spec.md").write_text(
        "\n".join([
            "# Atlas Clearinghouse — Multi-Currency Cutover & Webhook Security Specification",
            "",
            f"1. **ISO-4217 Minor Units, FX & Batch Status Filtering ({b}app/netting.py{b} & {b}/api/settle/summary{b})**:",
            f"   - {b}USD{b} ({b}1.00{b}) and {b}EUR{b} ({b}1.08 USD/EUR{b}): 2 decimal places ({b}100 minor units = 1.00{b}).",
            f"   - {b}JPY{b} ({b}0.0068 USD/JPY{b}): **0 decimal places** ({b}1 minor unit = 1 JPY{b}).",
            f"   - {b}KWD{b} ({b}3.25 USD/KWD{b}): **3 decimal places** ({b}1000 minor units = 1.000 KWD{b}).",
            f"   - Quantize each transaction's {b}gross_usd{b} to {b}0.01{b} using {b}ROUND_HALF_EVEN{b}.",
            f"   - Base interchange fee tier: **{b}16 bps (0.0016){b}** if {b}gross_usd >= 75000.00{b}, **{b}24 bps (0.0024){b}** if {b}20000.00 <= gross_usd < 75000.00{b}, else **{b}31 bps (0.0031){b}**, plus any cross-border FX surcharge specified in {b}../scans/risk_committee_memo.png{b}; quantize {b}fee_usd{b} to {b}0.01{b} with {b}ROUND_HALF_EVEN{b} and set {b}net_usd = gross_usd - fee_usd{b}.",
            f"   - {b}/api/settle/summary{b} MUST aggregate ONLY settled clearing transactions (exclude duplicate, sanctions-held, and reversed/refunded rows).",
            "",
            f"2. **Timestamped HMAC-SHA256, Replay Guard & Double-Entry Ledger ({b}POST /api/webhook/chargeback{b})**:",
            f"   - Require headers {b}X-Webhook-Timestamp{b} (integer Unix epoch seconds) and {b}X-Webhook-Signature{b}.",
            f"   - Reject with {b}HTTP 401{b} if {b}X-Webhook-Timestamp{b} is missing/non-integer, if {b}abs(time.time() - ts) > 300{b}, or if {b}X-Webhook-Signature{b} does not match {b}'sha256=' + hmac_sha256(webhook_key, f'{{ts}}.'.encode() + raw_body){b}.",
            f"   - Store accepted {b}event_id{b} in {b}processed_webhooks(event_id TEXT PRIMARY KEY){b} in {b}var/settlement.db{b}; return {b}HTTP 409{b} on duplicate {b}event_id{b}.",
            f"   - On accepted webhook, insert two balanced rows into {b}dispute_ledger(event_id TEXT, account TEXT, debit_cents INTEGER, credit_cents INTEGER){b}:",
            f"     {b}('2200_CHARGEBACK_RESERVE', amount_cents, 0){b} and {b}('1010_MERCHANT_PAYABLE', 0, amount_cents){b}.",
            "",
            f"3. **Ops Console Queue & Nostro Reconciliation ({b}Daily_Nostro_Recon.xlsx{b})**:",
            f"   - The Ops Console exports to {b}/home/gui/Downloads/ops_dispute_queue.csv{b}. For Nostro clearing engine sign-off ({b}Netting_Summary!B5{b}), set {b}FILTER = FX_CORRIDOR_SCHEDULE{b} and {b}BASIS = TREASURY_WHOLESALE_BPS{b}, export the corridor schedule, and copy the Clearing Engine Seal to the clipboard.",
            f"   - For dispute reserve reconciliation, switch to {b}FILTER = VALID_CHARGEBACK{b} (or {b}ALL{b}) and {b}BASIS = NATIVE_EXACT{b}, export {b}/home/gui/Downloads/ops_dispute_queue.csv{b} to obtain unrounded native currency amounts across all 40 adjudications (quantize each {b}VALID_CHARGEBACK{b} case to {b}0.01{b} USD via {b}ROUND_HALF_EVEN{b} before summing into {b}Dispute_Holdbacks!B2{b}), and copy the Cutover Authorization Token under {b}FILTER = VALID_CHARGEBACK{b} and {b}BASIS = NATIVE_EXACT{b} into {b}RELEASE_ATTESTATION.txt{b}.",
            "",
        ]),
        encoding="utf-8",
    )

    render_scanned_document_png(
        sc / "scans" / "risk_committee_memo.png",
        "TREASURY RISK COMMITTEE RULING RC-2026-11: SURCHARGE & BUFFER",
        [
            "1. Non-USD Cross-Border Clearing Surcharge (EUR, JPY, KWD):",
            "   Add +7 bps (+0.0007) to the base interchange bps rate for",
            "   ALL non-USD currencies (EUR, JPY, and KWD) before quantizing",
            "   fee_usd (USD domestic settlements add +0 bps).",
            "2. Daily Nostro Regulatory Capital Buffer (Capital_Buffer):",
            "   - B2 Intraday_Liquidity_Sweep_USD : [38,000.0, 56,000.0] USD",
            "   - B3 Dispute_Collateral_Buffer_USD: [23,000.0, 41,000.0] USD",
            "   - B4 Total_Regulatory_Buffer_USD (=B2+B3):",
            "     MUST lie within [78,600.0, 80,800.0] USD.",
        ],
        stamp_text="RISK COMMITTEE SIGNED",
        tilt_deg=-1.7,
    )

    txs, _, _ = _generate_settlement_txs()
    db_p = repo / "var" / "settlement.db"
    conn = sqlite3.connect(str(db_p))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE clearing_txs (tx_id TEXT PRIMARY KEY, currency TEXT, minor_units INTEGER, status TEXT)")
    conn.execute("CREATE TABLE processed_webhooks (event_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE dispute_ledger (event_id TEXT, account TEXT, debit_cents INTEGER, credit_cents INTEGER)")
    conn.executemany("INSERT INTO clearing_txs VALUES (?,?,?,?)", txs)
    conn.commit()
    conn.close()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "ops@atlas-pay.internal"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Atlas Release Bot"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial pre-cutover settlement baseline"], cwd=repo, check=True, capture_output=True)

    write_multisheet_xlsx(
        sc / "Daily_Nostro_Recon.xlsx",
        [
            ("Netting_Summary", [["Item", "Amount_USD", ""], ["Gross_Settled_USD", 0.0, ""], ["Net_Settled_USD", 0.0, ""], ["Total_Fee_USD", ("=B2-B3", 0.0), ""], ["Ops_Clearing_Seal", "PENDING_CLEARING_SEAL", ""]]),
            ("Dispute_Holdbacks", [["Item", "Amount_USD"], ["Valid_Chargebacks_USD", 0.0], ["Cutover_Auth_Token", "PENDING_CUTOVER_TOKEN"]]),
            ("Capital_Buffer", [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", 54200.0], ["Dispute_Collateral_Buffer_USD", 39500.0], ["Total_Regulatory_Buffer_USD", ("=B2+B3", 93700.0)]]),
        ],
    )

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_ops_html(filter_ruling: str, amount_basis: str) -> str:
    if filter_ruling == "FX_CORRIDOR_SCHEDULE":
        hdr_html = "<h3>Treasury FX Corridor Schedule & Signed Risk Committee Ruling</h3>"
        sub_p = "<p><img src='/scans/risk_committee_memo.png' style='max-width:860px;border:1px solid #94a3b8;'/></p>"
        th_html = "<tr><th>Currency</th><th>Minor Units</th><th>USD Rate</th></tr>"
        rows = [
            "<tr><td>USD</td><td>100 (2 dec)</td><td>1.0000</td></tr>",
            "<tr><td>EUR</td><td>100 (2 dec)</td><td>1.0800</td></tr>",
            "<tr><td>JPY</td><td>1 (0 dec)</td><td>0.0068</td></tr>",
            "<tr><td>KWD</td><td>1000 (3 dec)</td><td>3.2500</td></tr>",
        ]
    else:
        filtered = [c for c in DISPUTE_CASES if filter_ruling == "ALL" or c[3] == filter_ruling]
        hdr_html = f"<h3>Chargeback Adjudication Queue — Previewing 6 of {len(filtered)} Matching Cases</h3>"
        sub_p = "<p style='font-size:13px;color:#334155;'>Switch to <strong>NATIVE_EXACT</strong> and export CSV to obtain unrounded native currency amounts across all 40 network adjudications.</p>"
        th_html = f"<tr><th>Case ID</th><th>CCY</th><th>Disputed Amount ({amount_basis})</th><th>Adjudication</th></tr>"
        rows = []
        for cid, ccy, amt, rul in filtered[:6]:
            if amount_basis == "NATIVE_EXACT":
                disp_amt = f"{amt:,.3f} {ccy}" if ccy == "KWD" else f"{amt:,.2f} {ccy}"
            else:
                approx = round(float(Decimal(str(amt)) * FX_TO_USD[ccy]) / 100.0) * 100.0
                disp_amt = f"~{approx:,.0f} USD (rounded)"
            rows.append(f"<tr><td>{cid}</td><td>{ccy}</td><td>{disp_amt}</td><td><strong>{rul}</strong></td></tr>")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Atlas Clearinghouse Operations & Dispute Console</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    header {{ background: #0f172a; color: #f8fafc; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }}
    .toolbar {{ background: #e2e8f0; padding: 10px 20px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    button {{ background: #ffffff; border: 1px solid #475569; padding: 6px 10px; border-radius: 4px; cursor: pointer; font-weight: 600; }}
    button.active {{ background: #0f172a; color: #ffffff; }}
    main {{ padding: 20px; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; margin-top: 10px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px 10px; text-align: left; font-size: 13px; }}
    th {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <header>
    <div><strong>Atlas Clearinghouse Ops — Nostro & Chargeback Cutover Console</strong></div>
    <div style="font-family:monospace;" id="ops-banner">FILTER={filter_ruling} | BASIS={amount_basis}</div>
  </header>
  <div class="toolbar">
    <strong>Filter:</strong>
    <button class="{'active' if filter_ruling == 'ALL' else ''}" onclick="setOps({{filter:'ALL'}})">ALL (40)</button>
    <button class="{'active' if filter_ruling == 'VALID_CHARGEBACK' else ''}" onclick="setOps({{filter:'VALID_CHARGEBACK'}})">VALID_CHARGEBACK</button>
    <button class="{'active' if filter_ruling == 'FX_CORRIDOR_SCHEDULE' else ''}" onclick="setOps({{filter:'FX_CORRIDOR_SCHEDULE'}})">FX_CORRIDOR_SCHEDULE</button>
    <strong>Basis:</strong>
    <button class="{'active' if amount_basis == 'APPROX_USD_PREVIEW' else ''}" onclick="setOps({{amount_basis:'APPROX_USD_PREVIEW'}})">APPROX_USD_PREVIEW</button>
    <button class="{'active' if amount_basis == 'TREASURY_WHOLESALE_BPS' else ''}" onclick="setOps({{amount_basis:'TREASURY_WHOLESALE_BPS'}})">TREASURY_WHOLESALE_BPS</button>
    <button class="{'active' if amount_basis == 'NATIVE_EXACT' else ''}" onclick="setOps({{amount_basis:'NATIVE_EXACT'}})">NATIVE_EXACT</button>
    <button onclick="exportQueue()">Export Full 40-Case CSV (/home/gui/Downloads/ops_dispute_queue.csv)</button>
    <button onclick="copyAuth()">Copy Active Ops Seal / Token to Clipboard</button>
    <span id="msg" style="font-family:monospace;font-size:12px;color:#0369a1;">Ready</span>
  </div>
  <main>
    {hdr_html}
    {sub_p}
    <table>
      <thead>{th_html}</thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </main>
  <script>
    async function setOps(p) {{
      await fetch('/api/ops/state', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(p)}});
      window.location.reload();
    }}
    async function exportQueue() {{
      document.getElementById('msg').textContent = 'Exporting 40-case dispute CSV...';
      const r = await fetch('/api/ops/export_csv', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Exported [' + d.amount_basis + ']') : 'Error';
    }}
    async function copyAuth() {{
      const r = await fetch('/api/ops/copy_token', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Copied token [' + d.filter + '/' + d.amount_basis + ']') : 'Error';
    }}
  </script>
</body>
</html>
"""


def run_portal_service(port: int, workspace: Path, state_dir: Path, boot_file: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    repo = workspace / "settlement_cutover" / "repo"
    subprocess.Popen(
        ["su", "-s", "/bin/bash", "gui", "-c", f"cd {repo} && PYTHONPATH={repo} exec python3 app/server.py >/tmp/ec04_srv_boot.log 2>&1 </dev/null"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

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
    }

    def persist() -> None:
        write_json(state_p, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a: Any) -> None: return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec04_ops_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True, "task_id": TASK_ID})
                return
            if parsed.path == "/":
                qs = parse_qs(parsed.query)
                if (qs.get("sso_boot") or [""])[0] == boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"ec04_ops_sso={sso_cookie}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated Ops session required"})
                    return
                with lock:
                    html = _render_ops_html(pstate["filter"], pstate["amount_basis"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path.startswith("/scans/"):
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated Ops session required"})
                    return
                fn = Path(parsed.path).name
                fp = workspace / "settlement_cutover" / "scans" / fn
                if fp.is_file() and fp.suffix == ".png":
                    raw_png = fp.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(raw_png)))
                    self.end_headers()
                    self.wfile.write(raw_png)
                    return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self._authed():
                self._send_json(401, {"error": "Authenticated Ops session required"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            if parsed.path == "/api/ops/state":
                with lock:
                    changed = False
                    if body.get("filter") in ("ALL", "VALID_CHARGEBACK", "FX_CORRIDOR_SCHEDULE"):
                        if pstate["filter"] != body["filter"]:
                            changed = True
                        pstate["filter"] = body["filter"]
                    if body.get("amount_basis") in ("APPROX_USD_PREVIEW", "TREASURY_WHOLESALE_BPS", "NATIVE_EXACT"):
                        if pstate["amount_basis"] != body["amount_basis"]:
                            changed = True
                        pstate["amount_basis"] = body["amount_basis"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "filter": pstate["filter"], "amount_basis": pstate["amount_basis"]})
                return
            if parsed.path == "/api/ops/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.4 if is_adm else 4.2)
                dl_p = Path("/home/gui/Downloads/ops_dispute_queue.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    flt = pstate["filter"]
                    ab = pstate["amount_basis"]
                    if flt == "FX_CORRIDOR_SCHEDULE" and ab == "TREASURY_WHOLESALE_BPS":
                        lines = [
                            "currency,minor_divisor,fx_to_usd",
                            "USD,100,1.0000",
                            "EUR,100,1.0800",
                            "JPY,1,0.0068",
                            "KWD,1000,3.2500",
                        ]
                    else:
                        lines = ["case_id,currency,amount,adjudication"]
                        for cid, ccy, amt, rul in DISPUTE_CASES:
                            if ab == "NATIVE_EXACT":
                                val_s = f"{amt:.3f}" if ccy == "KWD" else f"{amt:.2f}"
                            else:
                                approx = round(float(Decimal(str(amt)) * FX_TO_USD[ccy]) / 100.0) * 100.0
                                val_s = f"{approx:.0f}"
                            lines.append(f"{cid},{ccy},{val_s},{rul}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "path": str(dl_p), "amount_basis": ab})
                return
            if parsed.path == "/api/ops/copy_token":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 1.5)
                with lock:
                    flt = pstate["filter"]
                    ab = pstate["amount_basis"]
                    tok = make_opaque_seal("ec04", f"{flt}:{ab}")
                    pstate["clipboard_copies"] += 1
                    persist()
                set_x11_clipboard(tok)
                self._send_json(200, {"ok": True, "filter": flt, "amount_basis": ab})
                return
            self._send_json(404, {"error": "Not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def grade(workspace: Path, service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    sc = workspace / "settlement_cutover"
    repo = sc / "repo"
    xp = sc / "Daily_Nostro_Recon.xlsx"

    errs_a: list[str] = []
    errs_b: list[str] = []
    errs_joint: list[str] = []

    st_cp = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    if st_cp.returncode != 0 or st_cp.stdout.strip():
        errs_joint.append(f"Git working tree dirty or uncommitted changes: {st_cp.stdout.strip()[:160]}")

    att_txt = (repo / "RELEASE_ATTESTATION.txt").read_text(encoding="utf-8", errors="replace") if (repo / "RELEASE_ATTESTATION.txt").is_file() else ""
    if RELEASE_CLIPBOARD_SEAL not in att_txt:
        errs_b.append("RELEASE_ATTESTATION.txt missing valid Cutover Authorization Token")

    srv_proc = None
    try:
        srv_proc = subprocess.Popen(
            ["python3", str(repo / "app" / "server.py")],
            cwd=repo,
            env={**os.environ, "PYTHONPATH": str(repo)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(25):
            try:
                with socket.create_connection(("127.0.0.1", APP_PORT), timeout=0.3):
                    break
            except OSError:
                time.sleep(0.15)

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{APP_PORT}/api/settle/summary", timeout=5) as r:
                s_data = json.loads(r.read().decode("utf-8"))
            if abs(float(s_data.get("gross_usd", -1)) - TRUE_GROSS_BATCH_USD) > 1.5:
                errs_a.append(f"/api/settle/summary gross_usd={s_data.get('gross_usd')} != {TRUE_GROSS_BATCH_USD}")
            if abs(float(s_data.get("net_usd", -1)) - TRUE_NET_BATCH_USD) > 1.5:
                errs_a.append(f"/api/settle/summary net_usd={s_data.get('net_usd')} != {TRUE_NET_BATCH_USD}")
        except Exception as exc:
            errs_a.append(f"/api/settle/summary failed: {exc}")

        ev_id = "evt_grade_" + secrets.token_hex(4)
        payload = json.dumps({"event_id": ev_id, "amount_cents": 12345}).encode("utf-8")
        now_ts = str(int(time.time()))
        stale_ts = str(int(time.time()) - 900)

        stale_sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode("utf-8"), stale_ts.encode("utf-8") + b"." + payload, hashlib.sha256).hexdigest()
        stale_req = urllib.request.Request(
            f"http://127.0.0.1:{APP_PORT}/api/webhook/chargeback",
            data=payload,
            headers={"Content-Type": "application/json", "X-Webhook-Timestamp": stale_ts, "X-Webhook-Signature": stale_sig},
            method="POST",
        )
        try:
            urllib.request.urlopen(stale_req, timeout=5)
            errs_b.append("Webhook accepted stale timestamp (>300s skew) without 401")
        except urllib.error.HTTPError as he_s:
            if he_s.code != 401:
                errs_b.append(f"Expected 401 on stale timestamp, got {he_s.code}")
        except Exception as exc:
            errs_b.append(f"Webhook stale-ts check failed: {exc}")

        bad_req = urllib.request.Request(
            f"http://127.0.0.1:{APP_PORT}/api/webhook/chargeback",
            data=payload,
            headers={"Content-Type": "application/json", "X-Webhook-Timestamp": now_ts, "X-Webhook-Signature": "sha256=deadbeef"},
            method="POST",
        )
        try:
            urllib.request.urlopen(bad_req, timeout=5)
            errs_b.append("Webhook accepted invalid HMAC signature without 401")
        except urllib.error.HTTPError as he:
            if he.code != 401:
                errs_b.append(f"Expected 401 on bad HMAC, got {he.code}")
        except Exception as exc:
            errs_b.append(f"Webhook bad-sig check failed: {exc}")

        good_sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode("utf-8"), now_ts.encode("utf-8") + b"." + payload, hashlib.sha256).hexdigest()
        good_req = urllib.request.Request(
            f"http://127.0.0.1:{APP_PORT}/api/webhook/chargeback",
            data=payload,
            headers={"Content-Type": "application/json", "X-Webhook-Timestamp": now_ts, "X-Webhook-Signature": good_sig},
            method="POST",
        )
        try:
            with urllib.request.urlopen(good_req, timeout=5) as r2:
                if r2.status != 200:
                    errs_b.append(f"Valid webhook returned {r2.status}")
            try:
                urllib.request.urlopen(good_req, timeout=5)
                errs_b.append("Duplicate webhook event_id was not rejected with 409")
            except urllib.error.HTTPError as he2:
                if he2.code != 409:
                    errs_b.append(f"Expected 409 on replay event_id, got {he2.code}")
        except Exception as exc:
            errs_b.append(f"Valid webhook test failed: {exc}")

        with sqlite3.connect(str(repo / "var" / "settlement.db")) as conn:
            l_rows = conn.execute("SELECT account, debit_cents, credit_cents FROM dispute_ledger WHERE event_id=?", (ev_id,)).fetchall()
        if sorted(l_rows) != sorted([("2200_CHARGEBACK_RESERVE", 12345, 0), ("1010_MERCHANT_PAYABLE", 0, 12345)]):
            errs_b.append(f"dispute_ledger unbalanced or missing rows for {ev_id}: {l_rows}")
    finally:
        if srv_proc is not None:
            srv_proc.terminate()
            try:
                srv_proc.wait(timeout=3)
            except Exception:
                srv_proc.kill()

    if not xp.is_file():
        errs_joint.append("Missing Daily_Nostro_Recon.xlsx")
    else:
        raw_sh = read_multisheet_xlsx(xp)
        ev_sh = evaluate_xlsx_via_libreoffice(xp)

        def _v(sh: str, ref: str) -> float:
            val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
            return float(val) if isinstance(val, (int, float)) else -999999.0

        def _s(sh: str, ref: str) -> str:
            val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
            return str(val or "").strip()

        def _f(sh: str, ref: str) -> bool:
            return bool(((raw_sh.get(sh) or {}).get(ref) or {}).get("formula"))

        if _s("Netting_Summary", "C1") != DESK_TAG:
            errs_joint.append(f"Netting_Summary!C1 lost live Calc NY4 tag ({_s('Netting_Summary', 'C1')!r} != {DESK_TAG!r})")
        if abs(_v("Netting_Summary", "B2") - TRUE_GROSS_BATCH_USD) > 2.0 or abs(_v("Netting_Summary", "B3") - TRUE_NET_BATCH_USD) > 2.0 or not _f("Netting_Summary", "B4"):
            errs_a.append("Netting_Summary!B2:B4 inaccurate or missing formula")
        if _s("Netting_Summary", "B5") != CLEARING_CLIPBOARD_SEAL:
            errs_a.append(f"Netting_Summary!B5 missing valid Ops_Clearing_Seal ({_s('Netting_Summary', 'B5')!r})")
        if abs(_v("Dispute_Holdbacks", "B2") - TRUE_VALID_CHARGEBACK_USD) > 1.5:
            errs_b.append(f"Dispute_Holdbacks!B2={_v('Dispute_Holdbacks','B2')} != {TRUE_VALID_CHARGEBACK_USD}")
        if _s("Dispute_Holdbacks", "B3") != RELEASE_CLIPBOARD_SEAL:
            errs_b.append(f"Dispute_Holdbacks!B3 missing valid Cutover_Auth_Token ({_s('Dispute_Holdbacks','B3')!r})")

        sw_v = _v("Capital_Buffer", "B2")
        co_v = _v("Capital_Buffer", "B3")
        tot_v = _v("Capital_Buffer", "B4")
        if not (SWEEP_RANGE_USD[0] <= sw_v <= SWEEP_RANGE_USD[1]):
            errs_a.append(f"Intraday_Liquidity_Sweep={sw_v} outside {list(SWEEP_RANGE_USD)}")
        if not (COLLATERAL_RANGE_USD[0] <= co_v <= COLLATERAL_RANGE_USD[1]):
            errs_b.append(f"Dispute_Collateral_Buffer={co_v} outside {list(COLLATERAL_RANGE_USD)}")
        if not _f("Capital_Buffer", "B4") or not (TOTAL_BUFFER_BAND_USD[0] <= tot_v <= TOTAL_BUFFER_BAND_USD[1]):
            errs_joint.append(f"Total_Regulatory_Buffer={tot_v} outside {list(TOTAL_BUFFER_BAND_USD)} or missing formula")

    if service_state.get("open_gui_split_brain") is True:
        errs_joint.append("Open LibreOffice Calc window held stale unsaved buffer inconsistent with disk")
    extra_files = [
        rel for rel in find_unexpected_workspace_files(sc, ALLOWED_CUTOVER_FILES)
        if not (rel == "repo/tests/__init__.py" or (rel.startswith("repo/tests/test_") and rel.endswith(".py")))
    ]
    if extra_files:
        errs_joint.append(f"Unexpected scratch/coordination files in /workspace/settlement_cutover: {extra_files[:5]}")

    pass_a = len(errs_a) == 0 and len(errs_joint) == 0
    pass_b = len(errs_b) == 0 and len(errs_joint) == 0
    return {
        "task_id": TASK_ID,
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": pass_a and pass_b,
        "errors_a": errs_a,
        "errors_b": errs_b,
        "errors_joint": errs_joint,
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_driver_and_ban_clean(build_tickets_by_role()),
        "telemetry": service_state,
    }


WEBHOOK_BLOCK_SNIPPET = """        if self.path == "/api/webhook/chargeback":
            import hashlib, hmac, time
            key = (ROOT / "config" / "webhook_key.txt").read_text(encoding="utf-8").strip().encode("utf-8")
            ts_hdr = self.headers.get("X-Webhook-Timestamp") or ""
            sig = self.headers.get("X-Webhook-Signature") or ""
            try:
                ts_val = int(ts_hdr)
            except ValueError:
                self._send(401, {"error": "invalid timestamp"})
                return
            if abs(time.time() - ts_val) > 300:
                self._send(401, {"error": "stale timestamp"})
                return
            exp = "sha256=" + hmac.new(key, ts_hdr.encode("utf-8") + b"." + raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, exp):
                self._send(401, {"error": "invalid signature"})
                return
            ev_id = str(body.get("event_id") or "")
            amt = int(body.get("amount_cents") or 0)
            with sqlite3.connect(str(DB_PATH)) as conn:
                if conn.execute("SELECT 1 FROM processed_webhooks WHERE event_id=?", (ev_id,)).fetchone():
                    self._send(409, {"error": "duplicate event_id"})
                    return
                conn.execute("INSERT INTO processed_webhooks VALUES (?)", (ev_id,))
                conn.execute("INSERT INTO dispute_ledger VALUES (?,?,?,?)", (ev_id, "2200_CHARGEBACK_RESERVE", amt, 0))
                conn.execute("INSERT INTO dispute_ledger VALUES (?,?,?,?)", (ev_id, "1010_MERCHANT_PAYABLE", 0, amt))
                conn.commit()
            self._send(200, {"ok": True, "event_id": ev_id})
            return"""


def solve_role(role: str, workspace: Path, port: int, careful_conc: bool = False) -> None:
    assert role in ("clearing_engine_dev", "dispute_security_dev")
    sc = workspace / "settlement_cutover"
    repo = sc / "repo"
    xp = sc / "Daily_Nostro_Recon.xlsx"
    adm_p = Path("/opt/ec_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_a = (role == "clearing_engine_dev")
        srv_p = repo / "app" / "server.py"
        srv_src = srv_p.read_text(encoding="utf-8")

        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev["Netting_Summary"].get("C1") or {}).get("value") or DESK_TAG)
        cur_sw = float((ev["Capital_Buffer"].get("B2") or {}).get("value") or 54200.0)
        cur_co = float((ev["Capital_Buffer"].get("B3") or {}).get("value") or 39500.0)

        if is_a:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"{base}/api/ops/state",
                    data=json.dumps({"filter": "FX_CORRIDOR_SCHEDULE", "amount_basis": "TREASURY_WHOLESALE_BPS"}).encode("utf-8"),
                    headers={"Content-Type": "application/json", **adm_hdr},
                    method="POST",
                ),
                timeout=10,
            ).read()
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/copy_token", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
            clr_seal = get_x11_clipboard()
            (repo / "app" / "netting.py").write_text(FIXED_NETTING_PY, encoding="utf-8")
            srv_src = srv_src.replace(
                "SELECT currency, minor_units, status FROM clearing_txs",
                "SELECT currency, minor_units, status FROM clearing_txs WHERE status='SETTLED'",
            )
            srv_p.write_text(srv_src, encoding="utf-8")
            tgt_b = 79700.0
            new_sw = round(max(SWEEP_RANGE_USD[0], min(SWEEP_RANGE_USD[1], tgt_b - cur_co)), 2)
            update_single_sheet_xlsx(
                xp,
                "Netting_Summary",
                [["Item", "Amount_USD", desk_c1], ["Gross_Settled_USD", TRUE_GROSS_BATCH_USD, ""], ["Net_Settled_USD", TRUE_NET_BATCH_USD, ""], ["Total_Fee_USD", ("=B2-B3", round(TRUE_GROSS_BATCH_USD - TRUE_NET_BATCH_USD, 2)), ""], ["Ops_Clearing_Seal", clr_seal, ""]],
            )
            update_single_sheet_xlsx(
                xp,
                "Capital_Buffer",
                [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", new_sw], ["Dispute_Collateral_Buffer_USD", cur_co], ["Total_Regulatory_Buffer_USD", ("=B2+B3", round(new_sw + cur_co, 2))]],
            )
        else:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"{base}/api/ops/state",
                    data=json.dumps({"filter": "VALID_CHARGEBACK", "amount_basis": "NATIVE_EXACT"}).encode("utf-8"),
                    headers={"Content-Type": "application/json", **adm_hdr},
                    method="POST",
                ),
                timeout=10,
            ).read()
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
            urllib.request.urlopen(urllib.request.Request(f"{base}/api/ops/copy_token", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
            rel_tok = get_x11_clipboard()
            (repo / "RELEASE_ATTESTATION.txt").write_text(rel_tok + "\n", encoding="utf-8")
            old_wh = (
                '        if self.path == "/api/webhook/chargeback":\n'
                '            self._send(200, {"ok": True, "event_id": body.get("event_id")})\n'
                '            return'
            )
            if old_wh in srv_src:
                srv_src = srv_src.replace(old_wh, WEBHOOK_BLOCK_SNIPPET)
                srv_p.write_text(srv_src, encoding="utf-8")
            tgt_b = 79700.0
            new_co = round(max(COLLATERAL_RANGE_USD[0], min(COLLATERAL_RANGE_USD[1], tgt_b - cur_sw)), 2)
            update_single_sheet_xlsx(xp, "Dispute_Holdbacks", [["Item", "Amount_USD"], ["Valid_Chargebacks_USD", TRUE_VALID_CHARGEBACK_USD], ["Cutover_Auth_Token", rel_tok]])
            update_single_sheet_xlsx(
                xp,
                "Capital_Buffer",
                [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", cur_sw], ["Dispute_Collateral_Buffer_USD", new_co], ["Total_Regulatory_Buffer_USD", ("=B2+B3", round(cur_sw + new_co, 2))]],
            )

        subprocess.run(["git", "-c", "safe.directory=*", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "-c", "safe.directory=*", "commit", "--allow-empty", "-m", f"Release update: {role}"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["bash", "-lc", "pkill -f 'app/server.py' >/dev/null 2>&1 || true; sleep 0.3"], capture_output=True, timeout=10)
        subprocess.Popen(
            ["su", "-s", "/bin/bash", "gui", "-c", f"cd {repo} && PYTHONPATH={repo} exec python3 app/server.py >/tmp/ec04_srv.log 2>&1 </dev/null"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        reload_open_libreoffice_window(xp)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_naive_race(workspace: Path, port: int) -> None:
    sc = workspace / "settlement_cutover"
    repo = sc / "repo"
    xp = sc / "Daily_Nostro_Recon.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        snap_srv = Path(tmp) / "server_v0.py"
        shutil.copy2(repo / "app" / "server.py", snap_srv)
        solve_role("clearing_engine_dev", workspace, port, careful_conc=False)
        shutil.copy2(snap_srv, repo / "app" / "server.py")
        solve_role("dispute_security_dev", workspace, port, careful_conc=False)
        update_single_sheet_xlsx(
            xp,
            "Capital_Buffer",
            [["Buffer_Component", "Amount_USD"], ["Intraday_Liquidity_Sweep_USD", 38270.0], ["Dispute_Collateral_Buffer_USD", 23270.0], ["Total_Regulatory_Buffer_USD", ("=B2+B3", 61540.0)]],
        )

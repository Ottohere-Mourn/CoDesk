"""FC-02: Live Staging E-Commerce & Double-Entry Ledger Monorepo (Git main + GCC C-Ext + SQLite WAL + Port 20120 + 3-Viewport Chromium + SSO Ops Console)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request


from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    verify_stage_regime_purity,
    audit_protocol_transparency,
    post_json,
    sha256_file,
    write_json,
)

TASK_ID = "FC-02"
STAGING_PORT = 20120
PORTAL_PORT = 19420

META = {
    "id": TASK_ID,
    "title": "Live Staging Checkout Monorepo, C-Pricing Kernel, Double-Entry Ledger & Multi-Viewport E2E",
    "domain": "Full-Stack Web / FinOps Systems Engineering (Git main + GCC C Shared Lib + SQLite WAL + Live Port 20120 + Chromium 3-Viewport + SSO Console)",
    "arena": "Shared Git Monorepo & Mutable Live Port-20120 Staging Service",
    "conflict_archetype": "live_staging_mid_soak_restart + git_main_and_server_py_merge_race + worker_pbkdf2_memory_sla_coupling + sso_canvas_session_switch",
    "roles": ("checkout_perf_lead", "security_ledger_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "checkout_monorepo/.git/HEAD",
    "conc_role_timeout_s": 2340,
    "seq_role_timeout_s": 2880,
}

HMAC_MASTER_SECRET = "fc02-staging-hmac-key-2026-v1"
API_CLIENT_SECRET = "fc02-merchant-pbkdf2-token-9941"
API_SALT_HEX = "73746167696e675f666330325f73616c74"

FX_RATES_MINOR_PER_10K_USD = {
    "USD": 10000,
    "EUR": 9240,
    "GBP": 7880,
    "JPY": 1512000,
}
TIER_DISCOUNT_BPS = (
    (200, 1450),
    (50, 925),
    (10, 450),
    (1, 0),
)

MAX_GATEWAY_MEMORY_MB = 336
MIN_WORKER_THREADS_PERF = 6
MIN_PER_WORKER_CACHE_MB = 32
MIN_SQLITE_MMAP_MB = 64
MIN_PBKDF2_ITERATIONS = 14000
MIN_AUTH_CACHE_MB = 56
MAX_SOAK_P95_MS = 90.0

VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("compact", 520, 760),
    ("tablet", 768, 1024),
    ("desktop", 1280, 720),
)

PERF_SUITES = ("pricing_c_kernel", "responsive_viewport_e2e", "fx_catalog_soak", "burst_throughput")
SEC_SUITES = ("crypto_replay_guard", "double_entry_idempotency", "audit_viewport_e2e", "concurrent_ledger_soak")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/checkout_monorepo",
    "app/pricing_ext.c",
    "app/libpricing.so",
    "app/server.py",
    "app/static/checkout.html",
    "var/staging.db",
    "config/gateway_limits.json",
    "http://127.0.0.1:20120",
    "/api/bench/staging_gate",
    "/api/release/submit",
    "/api/release/status",
    "full_release_gate",
    "1100_AR_CLEARING",
    "4000_MERCHANT_REV",
    "2150_VAT_PAYABLE",
    "336",
    "14000",
    "90.0",
)


def expected_quote_cents(unit_usd_cents: int, qty: int, currency: str, vat_bps: int) -> tuple[int, int, int]:
    """Reference integer math: returns (net_cents, vat_cents, gross_cents) in target currency minor units."""
    disc_bps = 0
    for min_q, bps in TIER_DISCOUNT_BPS:
        if qty >= min_q:
            disc_bps = bps
            break
    raw_usd = unit_usd_cents * qty
    disc_usd = (raw_usd * (10000 - disc_bps) + 5000) // 10000
    fx = FX_RATES_MINOR_PER_10K_USD[currency]
    net_minor = (disc_usd * fx + 5000) // 10000
    vat_minor = (net_minor * vat_bps + 5000) // 10000
    return int(net_minor), int(vat_minor), int(net_minor + vat_minor)


def make_signed_headers(body_bytes: bytes, nonce: str | None = None, ts: int | None = None, tamper: bool = False, idem_key: str | None = None) -> dict[str, str]:
    ts_val = int(time.time()) if ts is None else int(ts)
    nonce_val = nonce or secrets.token_hex(10)
    body_sha = hashlib.sha256(body_bytes).hexdigest()
    msg = f"{ts_val}.{nonce_val}.{body_sha}".encode("utf-8")
    sig = hmac.new(HMAC_MASTER_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if tamper:
        sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    hdrs = {
        "Content-Type": "application/json",
        "X-Client-Token": API_CLIENT_SECRET,
        "X-Req-Timestamp": str(ts_val),
        "X-Req-Nonce": nonce_val,
        "X-Req-Signature": sig,
    }
    if idem_key:
        hdrs["Idempotency-Key"] = idem_key
    return hdrs


def http_req(url: str, method: str = "GET", body_obj: dict | None = None, headers: dict[str, str] | None = None, timeout_s: float = 8.0) -> tuple[int, dict, float]:
    t0 = time.monotonic()
    raw = b""
    hdrs = dict(headers or {})
    if body_obj is not None:
        raw = json.dumps(body_obj, separators=(",", ":")).encode("utf-8")
        if "X-Req-Signature" not in hdrs:
            hdrs.update(make_signed_headers(raw))
    req = urllib.request.Request(url, data=(raw if method == "POST" else None), headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            dt_ms = (time.monotonic() - t0) * 1000.0
            txt = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(txt), dt_ms
            except Exception:
                return resp.status, {"raw": txt}, dt_ms
    except urllib.error.HTTPError as exc:
        dt_ms = (time.monotonic() - t0) * 1000.0
        txt = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(txt), dt_ms
        except Exception:
            return exc.code, {"error": txt}, dt_ms
    except Exception as exc:
        dt_ms = (time.monotonic() - t0) * 1000.0
        return 0, {"connection_error": str(exc)}, dt_ms


PRISTINE_PRICING_C = """#include <stdint.h>

/* v0 baseline kernel: missing volume tier discounts and truncates FX/VAT rounding */
void compute_quote_cents(
    int64_t unit_usd_cents,
    int64_t qty,
    int64_t fx_per_10k_usd,
    int64_t vat_bps,
    int64_t* out_net_cents,
    int64_t* out_vat_cents,
    int64_t* out_gross_cents
) {
    int64_t raw_usd = unit_usd_cents * qty;
    int64_t net_minor = (raw_usd * fx_per_10k_usd) / 10000;
    int64_t vat_minor = (net_minor * vat_bps) / 10000;
    *out_net_cents = net_minor;
    *out_vat_cents = vat_minor;
    *out_gross_cents = net_minor + vat_minor;
}
"""

PRISTINE_CHECKOUT_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Staging Checkout & FinOps Audit</title>
  <style>
    body { margin: 0; padding: 12px; font-family: sans-serif; background: #f8fafc; color: #0f172a; }
    /* BUG v0: fixed rigid widths overflow compact 520px viewport */
    #quote-card { width: 680px; padding: 16px; background: #ffffff; border: 1px solid #cbd5e1; margin-bottom: 14px; }
    #pay-submit-btn { display: inline-block; width: 640px; padding: 12px; background: #0284c7; color: #fff; border: 0; font-weight: bold; }
    #ledger-audit-panel { width: 710px; padding: 16px; background: #ffffff; border: 1px solid #cbd5e1; }
    #audit-table { width: 690px; border-collapse: collapse; }
  </style>
</head>
<body>
  <section id="quote-card">
    <h2>Multi-Currency Wholesale Quote</h2>
    <div id="quote-summary">SKU-PRO-100 | Tiered FX Quote Ready</div>
    <button id="pay-submit-btn" type="button">Authorize &amp; Settle Order</button>
  </section>
  <section id="ledger-audit-panel">
    <h3>Double-Entry Subledger Reconciliation</h3>
    <span id="ledger-balance-badge" data-status="UNVERIFIED">PENDING_AUDIT</span>
    <table id="audit-table">
      <thead><tr><th>Account</th><th>Debit</th><th>Credit</th></tr></thead>
      <tbody>
        <tr><td>1100_AR_CLEARING</td><td>0</td><td>0</td></tr>
      </tbody>
    </table>
  </section>
</body>
</html>
"""

PRISTINE_SERVER_PY = """#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "var" / "staging.db"
SO_PATH = ROOT / "app" / "libpricing.so"
HTML_PATH = ROOT / "app" / "static" / "checkout.html"
LIMITS_PATH = ROOT / "config" / "gateway_limits.json"

_lib = ctypes.CDLL(str(SO_PATH))
_lib.compute_quote_cents.argtypes = [
    ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
    ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64),
]
_lib.compute_quote_cents.restype = None

_db_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def calc_quote(sku: str, qty: int, currency: str) -> dict:
    with get_conn() as conn:
        prod = conn.execute("SELECT unit_usd_cents, vat_bps FROM products WHERE sku = ?", (sku,)).fetchone()
        fx_row = conn.execute("SELECT rate_per_10k_usd FROM fx_rates WHERE currency = ?", (currency,)).fetchone()
    if not prod or not fx_row:
        raise ValueError(f"Unknown sku={sku} or currency={currency}")
    net_c = ctypes.c_int64(0)
    vat_c = ctypes.c_int64(0)
    gross_c = ctypes.c_int64(0)
    _lib.compute_quote_cents(
        int(prod["unit_usd_cents"]), int(qty), int(fx_row["rate_per_10k_usd"]), int(prod["vat_bps"]),
        ctypes.byref(net_c), ctypes.byref(vat_c), ctypes.byref(gross_c),
    )
    return {
        "sku": sku,
        "qty": int(qty),
        "currency": currency,
        "net_cents": int(net_c.value),
        "vat_cents": int(vat_c.value),
        "gross_cents": int(gross_c.value),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        return

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        p = urlparse(self.path).path
        if p == "/health":
            limits = json.loads(LIMITS_PATH.read_text(encoding="utf-8"))
            self._json(200, {"ok": True, "limits": limits})
            return
        if p in ("/", "/checkout.html"):
            raw = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if p == "/api/ledger/trial_balance":
            self._json(501, {"error": "Double-entry ledger not yet implemented"})
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n > 0 else b"{}"
        body = json.loads(raw.decode("utf-8"))

        if p == "/api/cart/quote":
            try:
                q = calc_quote(str(body["sku"]), int(body["qty"]), str(body.get("currency", "USD")))
                self._json(200, q)
            except Exception as exc:
                self._json(400, {"error": str(exc)})
            return

        if p == "/api/cart/checkout":
            try:
                q = calc_quote(str(body["sku"]), int(body["qty"]), str(body.get("currency", "USD")))
                order_id = "ord_" + secrets.token_hex(6)
                with _db_lock, get_conn() as conn:
                    conn.execute(
                        "INSERT INTO orders(order_id, sku, qty, currency, net_cents, vat_cents, gross_cents, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (order_id, q["sku"], q["qty"], q["currency"], q["net_cents"], q["vat_cents"], q["gross_cents"], time.time()),
                    )
                    conn.commit()
                self._json(200, {"order_id": order_id, **q})
            except Exception as exc:
                self._json(400, {"error": str(exc)})
            return

        self._json(404, {"error": "Not found"})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 20120), Handler)
    srv.serve_forever()
"""

RESTART_STAGING_SH = (
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    "curl -fsS -X POST http://127.0.0.1:19420/api/staging/ctl "
    "-H 'Content-Type: application/json' -d '{\"action\": \"restart\"}'\n"
    "echo\n"
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "checkout_monorepo")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside checkout_monorepo: {extra_top} (use /tmp or $HOME for scratch files)")
    vdir = workspace / "checkout_monorepo" / "var"
    if vdir.is_dir():
        bad_var = sorted(
            x.name for x in vdir.iterdir()
            if not (x.name.startswith("staging.") or x.name.startswith("viewport_"))
        )
        if bad_var:
            errs.append(f"Unexpected scratch files/folders in checkout_monorepo/var: {bad_var}")
    return errs


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Shared Staging Monorepo, Live Service & Resource Envelope",
        f"- **Git Monorepo ({b}main{b} branch)**: {b}/workspace/checkout_monorepo{b} (commit all source/config changes cleanly to {b}main{b}; {b}git status --porcelain{b} must be clean before release signoff, and keep all scratch scripts/notes in {b}$HOME{b} or {b}$TMPDIR{b} — {b}/workspace{b} may contain only {b}checkout_monorepo{b} and {b}var/staging.*{b}).",
        f"- **Live Staging Service**: {b}http://127.0.0.1:20120{b} running from {b}/workspace/checkout_monorepo/app/server.py{b} (restart via {b}bash /workspace/checkout_monorepo/scripts/restart_staging.sh{b} after compiling {b}app/libpricing.so{b} or editing {b}app/server.py{b} / {b}config/gateway_limits.json{b}).",
        f"- **Live SQLite WAL Database**: {b}/workspace/checkout_monorepo/var/staging.db{b} (migrate schema non-destructively with {b}CREATE TABLE IF NOT EXISTS{b} / {b}INSERT OR REPLACE{b}; never delete or recreate the database file).",
        f"- **Global Gateway Memory & Latency Envelope ({b}config/gateway_limits.json{b})**:",
        f"  - {b}memory_footprint_mb = worker_threads * per_worker_cache_mb + sqlite_mmap_mb + auth_cache_mb{b} MUST be **{b}<= 336{b} MB**.",
        f"  - Live soak P95 latency MUST stay **{b}<= 90.0{b} ms** with **0 failed HTTP requests**.",
        f"- **Responsive Multi-Viewport UI ({b}app/static/checkout.html{b})**:",
        f"  - Verified in real headless Chromium across {b}520x760{b} (compact), {b}768x1024{b} (tablet), and {b}1280x720{b} (desktop): zero horizontal overflow ({b}documentElement.scrollWidth <= innerWidth + 2{b}), and both {b}#quote-card{b} / {b}#pay-submit-btn{b} and {b}#ledger-audit-panel{b} / {b}#audit-table{b} must remain visible within viewport width.",
        f"- **SSO Ops Console & QA Gate API ({b}http://127.0.0.1:{PORTAL_PORT}{b})**:",
        f"  - Open Chromium SSO Console on {b}DISPLAY=:99{b}: use {b}desktop.screenshot{b} and {b}desktop.click{b} to select your tenant profile ({b}B2B_WHOLESALE{b} or {b}FINOPS_LEDGER{b}) and {b}MINOR_UNITS_EXACT{b} basis on the SSO {b}<canvas>{b}, or click {b}Export Active Spec CSV{b} to write {b}/home/gui/Downloads/staging_spec.csv{b} (verify {b}tenant_profile{b} and {b}basis{b} columns).",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/staging_gate{b}: runs real 3-viewport Chromium E2E + sustained live HTTP soak traffic against {b}http://127.0.0.1:20120{b}.",
        f"  - {b}GET http://127.0.0.1:{PORTAL_PORT}/api/release/status?subsystem=<subsystem>{b}: inspect your subsystem's passed QA suites (suites must be qualified in the listed order).",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/release/submit{b}: evaluates the latest valid submission; returns explicit {b}HTTP 422{b} with objective engineering discrepancies if any suite, Git working tree, live staging response, DB invariant, or memory/P95 budget is out of spec.",
    ]
    common_txt = "\n".join(common_lines)

    perf_txt = "\n".join([
        f"# Engineering Work Order — FC-02 ({b}checkout_perf_lead{b}: C-Pricing Kernel, FX Catalog & Responsive Checkout)",
        "",
        f"Upgrade and qualify the C pricing kernel, FX table, responsive checkout card, and throughput settings in {b}/workspace/checkout_monorepo{b}.",
        "",
        "### Checkout & Performance Requirements",
        f"1. On the open Chromium SSO Console ({b}DISPLAY=:99{b}), switch to {b}B2B_WHOLESALE{b} + {b}MINOR_UNITS_EXACT{b} via GUI ({b}desktop.click{b} + {b}desktop.screenshot{b}) to verify the exact 4-tier volume discount schedule and FX rates on {b}<canvas>{b} (and/or click {b}Export Active Spec CSV{b} -> {b}/home/gui/Downloads/staging_spec.csv{b}):",
        f"   - Volume discount tiers in {b}app/pricing_ext.c{b} ({b}compute_quote_cents{b}): tiers are shown on the {b}B2B_WHOLESALE{b} {b}<canvas>{b} ({b}qty >= 200{b}, {b}qty >= 50{b}, {b}qty >= 10{b}, {b}qty < 10{b}) with exact half-up integer rounding {b}(x + 5000) / 10000{b} at discount, FX conversion, and VAT steps. Compile with {b}gcc -O2 -shared -fPIC app/pricing_ext.c -o app/libpricing.so{b}.",
        f"   - Populate {b}fx_rates{b} in {b}var/staging.db{b} with exact {b}USD, EUR, GBP, JPY{b} minor-unit rates per 10,000 USD from the {b}B2B_WHOLESALE{b} {b}<canvas>{b}.",
        f"2. Fix responsive CSS in {b}app/static/checkout.html{b} so {b}#quote-card{b} and {b}#pay-submit-btn{b} fit cleanly without horizontal overflow across {b}520x760{b}, {b}768x1024{b}, and {b}1280x720{b}.",
        f"3. In {b}config/gateway_limits.json{b}, configure {b}worker_threads >= 6{b}, {b}per_worker_cache_mb >= 32{b}, and {b}sqlite_mmap_mb >= 64{b} while keeping total {b}memory_footprint_mb <= 336{b} MB, and restart live staging on {b}http://127.0.0.1:20120{b}.",
        f"4. Qualify all 4 checkout suites via {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/staging_gate{b} ({b}{{\"subsystem\": \"checkout_perf\", \"suite\": \"...\"}}{b}): {b}pricing_c_kernel{b}, {b}responsive_viewport_e2e{b}, {b}fx_catalog_soak{b}, {b}burst_throughput{b}, followed by {b}full_release_gate{b}.",
        f"5. Commit all changes cleanly to {b}main{b}, ensure live port {b}20120{b} is running the committed code, and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/release/submit{b}:",
        f"   {b}{{\"subsystem\": \"checkout_perf\", \"git_head\": \"<40-char-sha>\", \"memory_footprint_mb\": <int>, \"libpricing_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}B2B_WHOLESALE{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    sec_txt = "\n".join([
        f"# Engineering Work Order — FC-02 ({b}security_ledger_lead{b}: HMAC/PBKDF2 Guard, Idempotent Double-Entry Ledger & Audit UI)",
        "",
        f"Implement and qualify cryptographic request authentication, replay protection, idempotent double-entry accounting, and responsive audit UI in {b}/workspace/checkout_monorepo{b}.",
        "",
        "### Security & Double-Entry Ledger Requirements",
        f"1. On the open Chromium SSO Console ({b}DISPLAY=:99{b}), switch to {b}FINOPS_LEDGER{b} + {b}MINOR_UNITS_EXACT{b} via GUI ({b}desktop.click{b} + {b}desktop.screenshot{b}) to read the exact PBKDF2/HMAC secrets, salt, and account codes on {b}<canvas>{b} (and/or click {b}Export Active Spec CSV{b} -> {b}/home/gui/Downloads/staging_spec.csv{b}):",
        f"   - Verify headers on {b}POST /api/cart/quote{b} and {b}POST /api/cart/checkout{b}:",
        f"     - Derive client key via {b}hashlib.pbkdf2_hmac('sha256', X_Client_Token.encode(), bytes.fromhex(salt_hex), iterations){b} where {b}pbkdf2_iterations >= 14000{b} from {b}config/gateway_limits.json{b} (expected client token & HMAC secret shown on {b}FINOPS_LEDGER{b} {b}<canvas>{b}; cache verified token digests in memory when {b}auth_cache_mb >= 56{b} so soak P95 stays {b}<= 90.0 ms{b}).",
        f"     - Verify {b}X-Req-Signature == hmac_sha256(hmac_secret, f'{{X-Req-Timestamp}}.{{X-Req-Nonce}}.{{sha256_hex(raw_body)}}'){b}; return {b}HTTP 401{b} on invalid token or signature.",
        f"     - Enforce timestamp freshness within {b}+/- 300s{b} and unique {b}X-Req-Nonce{b} persisted in SQLite table {b}replay_nonces(nonce TEXT PRIMARY KEY, created_at REAL){b}; return {b}HTTP 409{b} on stale timestamp or replayed nonce.",
        f"2. Implement idempotent double-entry ledger in {b}var/staging.db{b} and {b}app/server.py{b}:",
        f"   - Persist {b}idempotency_key{b} (from header {b}Idempotency-Key{b} when present): if {b}POST /api/cart/checkout{b} repeats an existing {b}Idempotency-Key{b} (with a fresh valid nonce), return the original {b}order_id{b} and quote amounts ({b}HTTP 200{b}) without inserting duplicate {b}orders{b} or {b}ledger_entries{b} rows.",
        f"   - For every newly created order, atomically insert balanced rows into {b}ledger_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, account_code TEXT, debit_cents INTEGER, credit_cents INTEGER){b}:",
        f"     - {b}1100_AR_CLEARING{b}: {b}debit_cents = gross_cents, credit_cents = 0{b}",
        f"     - {b}4000_MERCHANT_REV{b}: {b}debit_cents = 0, credit_cents = net_cents{b}",
        f"     - {b}2150_VAT_PAYABLE{b}: {b}debit_cents = 0, credit_cents = vat_cents{b}",
        f"   - Expose {b}GET /api/ledger/trial_balance{b} returning {b}{{\"balanced\": bool, \"total_debit_cents\": int, \"total_credit_cents\": int, \"accounts\": {{\"1100_AR_CLEARING\": {{\"debit\": int, \"credit\": int}}, \"4000_MERCHANT_REV\": ..., \"2150_VAT_PAYABLE\": ...}}}}{b}.",
        f"3. Fix responsive CSS in {b}app/static/checkout.html{b} so {b}#ledger-audit-panel{b} and {b}#audit-table{b} fit without horizontal overflow across {b}520x760{b}, {b}768x1024{b}, and {b}1280x720{b}, and set {b}#ledger-balance-badge{b} {b}data-status=\"BALANCED_ACTIVE\"{b}.",
        f"4. In {b}config/gateway_limits.json{b}, set {b}pbkdf2_iterations >= 14000{b}, {b}auth_cache_mb >= 56{b}, and {b}sqlite_mmap_mb >= 64{b} while keeping total {b}memory_footprint_mb <= 336{b} MB, restart live staging, and qualify all 4 security suites ({b}crypto_replay_guard{b}, {b}double_entry_idempotency{b}, {b}audit_viewport_e2e{b}, {b}concurrent_ledger_soak{b}) + {b}full_release_gate{b} via {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/staging_gate{b}.",
        f"5. Commit all changes cleanly to {b}main{b}, ensure live port {b}20120{b} is running {b}HEAD{b}, and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/release/submit{b}:",
        f"   {b}{{\"subsystem\": \"security_ledger\", \"git_head\": \"<40-char-sha>\", \"memory_footprint_mb\": <int>, \"pbkdf2_iterations\": <int>}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}FINOPS_LEDGER{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"checkout_perf_lead": perf_txt, "security_ledger_lead": sec_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    repo = workspace / "checkout_monorepo"
    (repo / "app" / "static").mkdir(parents=True, exist_ok=True)
    (repo / "config").mkdir(parents=True, exist_ok=True)
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "var").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    (repo / ".gitignore").write_text("var/\n__pycache__/\n*.pyc\n", encoding="utf-8")
    (repo / "app" / "pricing_ext.c").write_text(PRISTINE_PRICING_C, encoding="utf-8")
    (repo / "app" / "static" / "checkout.html").write_text(PRISTINE_CHECKOUT_HTML, encoding="utf-8")
    (repo / "app" / "server.py").write_text(PRISTINE_SERVER_PY, encoding="utf-8")
    (repo / "scripts" / "restart_staging.sh").write_text(RESTART_STAGING_SH, encoding="utf-8")
    os.chmod(repo / "app" / "server.py", 0o755)
    os.chmod(repo / "scripts" / "restart_staging.sh", 0o755)

    write_json(repo / "config" / "gateway_limits.json", {
        "worker_threads": 4,
        "per_worker_cache_mb": 40,
        "sqlite_mmap_mb": 64,
        "auth_cache_mb": 0,
        "pbkdf2_iterations": 1000,
    })

    subprocess.run(
        ["gcc", "-O2", "-shared", "-fPIC", str(repo / "app" / "pricing_ext.c"), "-o", str(repo / "app" / "libpricing.so")],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    db_p = repo / "var" / "staging.db"
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("CREATE TABLE products(sku TEXT PRIMARY KEY, unit_usd_cents INTEGER NOT NULL, vat_bps INTEGER NOT NULL);")
        conn.execute("CREATE TABLE fx_rates(currency TEXT PRIMARY KEY, rate_per_10k_usd INTEGER NOT NULL);")
        conn.execute(
            "CREATE TABLE orders(order_id TEXT PRIMARY KEY, sku TEXT, qty INTEGER, currency TEXT, net_cents INTEGER, vat_cents INTEGER, gross_cents INTEGER, created_at REAL);"
        )
        conn.executemany(
            "INSERT INTO products(sku, unit_usd_cents, vat_bps) VALUES (?, ?, ?)",
            [("SKU-PRO-100", 12500, 1900), ("SKU-ENT-500", 48900, 2000), ("SKU-IOT-020", 3150, 750)],
        )
        conn.executemany(
            "INSERT INTO fx_rates(currency, rate_per_10k_usd) VALUES (?, ?)",
            [("USD", 10000), ("EUR", 9000), ("GBP", 8000), ("JPY", 1500000)],
        )
        conn.commit()

    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Release Bot",
        "GIT_AUTHOR_EMAIL": "release@paragui.local",
        "GIT_COMMITTER_NAME": "Release Bot",
        "GIT_COMMITTER_EMAIL": "release@paragui.local",
    }
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, env=git_env, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Workstation Engineer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "eng@paragui.local"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, env=git_env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial v0 checkout monorepo baseline"], cwd=repo, env=git_env, check=True, capture_output=True)

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def verify_gateway_limits(repo: Path, check_perf: bool, check_sec: bool) -> tuple[dict, list[str]]:
    lp = repo / "config" / "gateway_limits.json"
    if not lp.is_file():
        return {}, ["Missing config/gateway_limits.json"]
    try:
        cfg = json.loads(lp.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"Invalid JSON in config/gateway_limits.json: {exc}"]

    errs: list[str] = []
    wt = int(cfg.get("worker_threads", 0))
    pwc = int(cfg.get("per_worker_cache_mb", 0))
    mmap_mb = int(cfg.get("sqlite_mmap_mb", 0))
    ac_mb = int(cfg.get("auth_cache_mb", 0))
    iters = int(cfg.get("pbkdf2_iterations", 0))
    mem_mb = wt * pwc + mmap_mb + ac_mb
    summary = {
        "worker_threads": wt,
        "per_worker_cache_mb": pwc,
        "sqlite_mmap_mb": mmap_mb,
        "auth_cache_mb": ac_mb,
        "pbkdf2_iterations": iters,
        "memory_footprint_mb": mem_mb,
    }
    if wt < 1 or pwc < 0 or mmap_mb < 16 or ac_mb < 0:
        errs.append(f"Invalid negative/zero resource fields in gateway_limits.json: {summary}")
    if mem_mb > MAX_GATEWAY_MEMORY_MB:
        errs.append(f"memory_footprint_mb={mem_mb} exceeds max {MAX_GATEWAY_MEMORY_MB} MB")
    if check_perf:
        if wt < MIN_WORKER_THREADS_PERF:
            errs.append(f"worker_threads={wt} below checkout_perf min {MIN_WORKER_THREADS_PERF}")
        if pwc < MIN_PER_WORKER_CACHE_MB:
            errs.append(f"per_worker_cache_mb={pwc} below checkout_perf min {MIN_PER_WORKER_CACHE_MB}")
        if mmap_mb < MIN_SQLITE_MMAP_MB:
            errs.append(f"sqlite_mmap_mb={mmap_mb} below min {MIN_SQLITE_MMAP_MB}")
    if check_sec:
        if iters < MIN_PBKDF2_ITERATIONS:
            errs.append(f"pbkdf2_iterations={iters} below security min {MIN_PBKDF2_ITERATIONS}")
        if ac_mb < MIN_AUTH_CACHE_MB:
            errs.append(f"auth_cache_mb={ac_mb} below security min {MIN_AUTH_CACHE_MB}")
        if mmap_mb < MIN_SQLITE_MMAP_MB:
            errs.append(f"sqlite_mmap_mb={mmap_mb} below min {MIN_SQLITE_MMAP_MB}")
    return summary, errs


def verify_c_kernel_binary(repo: Path) -> list[str]:
    so_p = repo / "app" / "libpricing.so"
    if not so_p.is_file():
        return ["Missing compiled shared library app/libpricing.so"]
    with tempfile.TemporaryDirectory() as tmp:
        chk_p = Path(tmp) / "chk_so.py"
        chk_p.write_text(
            f"""
import ctypes, json
lib = ctypes.CDLL({str(so_p)!r})
lib.compute_quote_cents.argtypes = [
    ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
    ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64),
]
lib.compute_quote_cents.restype = None
out = []
for u, q, fx, vat in [(12500, 3, 10000, 1900), (12500, 15, 9240, 1900), (48900, 65, 7880, 2000), (3150, 240, 1512000, 750)]:
    n, v, g = ctypes.c_int64(0), ctypes.c_int64(0), ctypes.c_int64(0)
    lib.compute_quote_cents(u, q, fx, vat, ctypes.byref(n), ctypes.byref(v), ctypes.byref(g))
    out.append([int(n.value), int(v.value), int(g.value)])
print(json.dumps(out))
""",
            encoding="utf-8",
        )
        cp = subprocess.run(["python3", str(chk_p)], capture_output=True, text=True, timeout=15)
        if cp.returncode != 0:
            return [f"libpricing.so failed ctypes load/call: {cp.stderr[-300:]}"]
        got = json.loads(cp.stdout.strip())
    cases = [
        (12500, 3, "USD", 1900),
        (12500, 15, "EUR", 1900),
        (48900, 65, "GBP", 2000),
        (3150, 240, "JPY", 750),
    ]
    errs: list[str] = []
    for (u, q, cur, vat), actual in zip(cases, got):
        exp = list(expected_quote_cents(u, q, cur, vat))
        if actual != exp:
            errs.append(f"libpricing.so mismatch for qty={q}, cur={cur}: got {actual}, expected {exp}")
    return errs


def verify_viewports_chromium(base_url: str, repo: Path, check_perf: bool, check_sec: bool) -> list[str]:
    code, resp_obj, _ = http_req(f"{base_url}/checkout.html", method="GET", timeout_s=6.0)
    html_src = resp_obj.get("raw", "") if code == 200 else ""
    if code != 200 or not html_src:
        return [f"GET {base_url}/checkout.html failed (status={code})"]

    errs: list[str] = []
    probe_js = """
<script>
(function(){
  function rectOf(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const st = window.getComputedStyle(el);
    return {
      visible: (st.display !== 'none' && st.visibility !== 'hidden' && r.width > 20 && r.height > 12),
      left: Math.round(r.left),
      right: Math.round(r.right),
      width: Math.round(r.width),
      status: el.getAttribute('data-status') || ''
    };
  }
  const info = {
    vw: window.innerWidth,
    sw: document.documentElement.scrollWidth,
    quote_card: rectOf('quote-card'),
    pay_btn: rectOf('pay-submit-btn'),
    audit_panel: rectOf('ledger-audit-panel'),
    audit_table: rectOf('audit-table'),
    badge: rectOf('ledger-balance-badge')
  };
  document.body.setAttribute('data-fc02-layout', JSON.stringify(info));
})();
</script>
"""
    injected = html_src.replace("</body>", probe_js + "</body>") if "</body>" in html_src else (html_src + probe_js)
    with tempfile.TemporaryDirectory() as tmp:
        hp = Path(tmp) / "checkout_probe.html"
        hp.write_text(injected, encoding="utf-8")
        for vp_name, w, h in VIEWPORTS:
            shot_p = repo / "var" / f"viewport_{vp_name}.png"
            cp = subprocess.run(
                [
                    "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                    f"--window-size={w},{h}", "--virtual-time-budget=1200", "--dump-dom", f"file://{hp}",
                ],
                capture_output=True,
                text=True,
                timeout=25,
            )
            subprocess.run(
                [
                    "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                    f"--window-size={w},{h}", f"--screenshot={shot_p}", f"{base_url}/checkout.html",
                ],
                capture_output=True,
                timeout=25,
            )
            if cp.returncode != 0:
                errs.append(f"Chromium failed on viewport {vp_name} ({w}x{h})")
                continue
            marker = 'data-fc02-layout="'
            idx = cp.stdout.find(marker)
            if idx < 0:
                errs.append(f"Layout probe attribute missing in {vp_name} DOM")
                continue
            end_idx = cp.stdout.find('"', idx + len(marker))
            raw_attr = cp.stdout[idx + len(marker):end_idx].replace("&quot;", '"')
            info = json.loads(raw_attr)
            vw = int(info["vw"])
            sw = int(info["sw"])
            if sw > vw + 2:
                errs.append(f"Viewport {vp_name} ({vw}px) has horizontal overflow scrollWidth={sw}px")
            if check_perf:
                for k in ("quote_card", "pay_btn"):
                    r = info.get(k)
                    if not r or not r["visible"] or r["right"] > vw + 2 or r["left"] < -2:
                        errs.append(f"Viewport {vp_name}: #{k.replace('_', '-')} missing, hidden, or overflows ({r})")
            if check_sec:
                for k in ("audit_panel", "audit_table"):
                    r = info.get(k)
                    if not r or not r["visible"] or r["right"] > vw + 2 or r["left"] < -2:
                        errs.append(f"Viewport {vp_name}: #{k} missing, hidden, or overflows ({r})")
                b_el = info.get("badge")
                if not b_el or b_el.get("status") != "BALANCED_ACTIVE":
                    errs.append(f"Viewport {vp_name}: #ledger-balance-badge data-status != 'BALANCED_ACTIVE'")
    return errs


def run_soak_burst(base_url: str, duration_s: float, workers: int = 6, do_checkouts: bool = True) -> dict:
    for _ in range(2):
        http_req(f"{base_url}/api/cart/quote", method="POST", body_obj={"sku": "SKU-PRO-100", "qty": 2, "currency": "USD"}, timeout_s=4.0)
        if do_checkouts:
            http_req(f"{base_url}/api/cart/checkout", method="POST", body_obj={"sku": "SKU-PRO-100", "qty": 2, "currency": "USD"}, timeout_s=4.0)
    t_end = time.monotonic() + duration_s
    latencies: list[float] = []
    failures = 0
    total_reqs = 0
    skus = [("SKU-PRO-100", 12500, 1900), ("SKU-ENT-500", 48900, 2000), ("SKU-IOT-020", 3150, 750)]
    curs = ["USD", "EUR", "GBP", "JPY"]
    qtys = [2, 12, 60, 220]
    lock = threading.Lock()

    def _worker(wid: int) -> None:
        nonlocal failures, total_reqs
        i = wid
        while time.monotonic() < t_end:
            sku, u_c, vat_b = skus[i % len(skus)]
            cur = curs[(i // 3) % len(curs)]
            qty = qtys[(i // 5) % len(qtys)]
            ep = "/api/cart/checkout" if (do_checkouts and i % 3 == 0) else "/api/cart/quote"
            code, resp, dt_ms = http_req(
                f"{base_url}{ep}",
                method="POST",
                body_obj={"sku": sku, "qty": qty, "currency": cur},
                timeout_s=5.0,
            )
            with lock:
                total_reqs += 1
                latencies.append(dt_ms)
                if code != 200:
                    failures += 1
            i += 1
            time.sleep(0.08)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_worker, w) for w in range(workers)]
        for f in futs:
            f.result()

    lat_sorted = sorted(latencies)
    idx95 = max(0, int(0.95 * (len(lat_sorted) - 1)))
    p95 = lat_sorted[idx95] if lat_sorted else 999.0
    return {
        "total_requests": total_reqs,
        "failed_requests": failures,
        "p95_ms": round(p95, 2),
    }


def verify_security_and_ledger_live(base_url: str, repo: Path) -> list[str]:
    errs: list[str] = []
    body_obj = {"sku": "SKU-PRO-100", "qty": 15, "currency": "EUR"}
    raw = json.dumps(body_obj, separators=(",", ":")).encode("utf-8")

    # 1. Tampered HMAC signature must return 401
    bad_sig_hdrs = make_signed_headers(raw, tamper=True)
    c1, _, _ = http_req(f"{base_url}/api/cart/quote", method="POST", body_obj=body_obj, headers=bad_sig_hdrs)
    if c1 != 401:
        errs.append(f"Tampered X-Req-Signature returned HTTP {c1}, expected 401")

    # 2. Invalid client token must return 401
    bad_tok_hdrs = make_signed_headers(raw)
    bad_tok_hdrs["X-Client-Token"] = "wrong-client-token"
    c2, _, _ = http_req(f"{base_url}/api/cart/quote", method="POST", body_obj=body_obj, headers=bad_tok_hdrs)
    if c2 != 401:
        errs.append(f"Invalid X-Client-Token returned HTTP {c2}, expected 401")

    # 3. Stale timestamp (>300s old) must return 409
    stale_hdrs = make_signed_headers(raw, ts=int(time.time()) - 900)
    c3, _, _ = http_req(f"{base_url}/api/cart/quote", method="POST", body_obj=body_obj, headers=stale_hdrs)
    if c3 != 409:
        errs.append(f"Stale X-Req-Timestamp returned HTTP {c3}, expected 409")

    # 4. Replayed nonce must return 409
    fixed_nonce = "nonce_" + secrets.token_hex(8)
    h_first = make_signed_headers(raw, nonce=fixed_nonce)
    c4_a, _, _ = http_req(f"{base_url}/api/cart/quote", method="POST", body_obj=body_obj, headers=h_first)
    c4_b, _, _ = http_req(f"{base_url}/api/cart/quote", method="POST", body_obj=body_obj, headers=h_first)
    if c4_a != 200 or c4_b != 409:
        errs.append(f"Nonce replay check got ({c4_a}, {c4_b}), expected (200, 409)")

    # 5. Idempotent checkout + double-entry balance
    idem_k = "idem_" + secrets.token_hex(8)
    h_id1 = make_signed_headers(raw, idem_key=idem_k)
    c5_a, r5_a, _ = http_req(f"{base_url}/api/cart/checkout", method="POST", body_obj=body_obj, headers=h_id1)
    h_id2 = make_signed_headers(raw, idem_key=idem_k)
    c5_b, r5_b, _ = http_req(f"{base_url}/api/cart/checkout", method="POST", body_obj=body_obj, headers=h_id2)
    if c5_a != 200 or c5_b != 200 or not r5_a.get("order_id") or r5_a.get("order_id") != r5_b.get("order_id"):
        errs.append(f"Idempotency-Key deduplication failed: ({c5_a}, {r5_a}) vs ({c5_b}, {r5_b})")

    c_tb, tb, _ = http_req(f"{base_url}/api/ledger/trial_balance", method="GET")
    if c_tb != 200 or not tb.get("balanced"):
        errs.append(f"GET /api/ledger/trial_balance failed or unbalanced: status={c_tb}, body={tb}")
    else:
        tot_d = int(tb.get("total_debit_cents", -1))
        tot_c = int(tb.get("total_credit_cents", -2))
        if tot_d <= 0 or tot_d != tot_c:
            errs.append(f"Trial balance totals invalid: debit={tot_d}, credit={tot_c}")

    db_p = repo / "var" / "staging.db"
    try:
        with sqlite3.connect(str(db_p)) as conn:
            row_ord = conn.execute("SELECT COALESCE(SUM(net_cents),0), COALESCE(SUM(vat_cents),0), COALESCE(SUM(gross_cents),0) FROM orders").fetchone()
            row_ar = conn.execute("SELECT COALESCE(SUM(debit_cents),0), COALESCE(SUM(credit_cents),0) FROM ledger_entries WHERE account_code='1100_AR_CLEARING'").fetchone()
            row_rev = conn.execute("SELECT COALESCE(SUM(debit_cents),0), COALESCE(SUM(credit_cents),0) FROM ledger_entries WHERE account_code='4000_MERCHANT_REV'").fetchone()
            row_vat = conn.execute("SELECT COALESCE(SUM(debit_cents),0), COALESCE(SUM(credit_cents),0) FROM ledger_entries WHERE account_code='2150_VAT_PAYABLE'").fetchone()
            if (row_ar[0], row_ar[1]) != (row_ord[2], 0):
                errs.append(f"1100_AR_CLEARING ({row_ar}) != orders gross ({row_ord[2]}, 0)")
            if (row_rev[0], row_rev[1]) != (0, row_ord[0]):
                errs.append(f"4000_MERCHANT_REV ({row_rev}) != orders net (0, {row_ord[0]})")
            if (row_vat[0], row_vat[1]) != (0, row_ord[1]):
                errs.append(f"2150_VAT_PAYABLE ({row_vat}) != orders vat (0, {row_ord[1]})")
    except Exception as exc:
        errs.append(f"SQLite ledger_entries verification error: {exc}")

    return errs


def verify_pricing_and_fx_live(base_url: str, repo: Path) -> list[str]:
    errs = verify_c_kernel_binary(repo)
    test_matrix = [
        ("SKU-PRO-100", 12500, 1900, 4, "USD"),
        ("SKU-PRO-100", 12500, 1900, 18, "EUR"),
        ("SKU-ENT-500", 48900, 2000, 75, "GBP"),
        ("SKU-IOT-020", 3150, 750, 250, "JPY"),
    ]
    for sku, u_c, vat_b, qty, cur in test_matrix:
        code, resp, _ = http_req(f"{base_url}/api/cart/quote", method="POST", body_obj={"sku": sku, "qty": qty, "currency": cur})
        exp_n, exp_v, exp_g = expected_quote_cents(u_c, qty, cur, vat_b)
        if code != 200:
            errs.append(f"POST /api/cart/quote ({sku}, qty={qty}, {cur}) returned HTTP {code}: {resp}")
            continue
        got_tuple = (resp.get("net_cents"), resp.get("vat_cents"), resp.get("gross_cents"))
        if got_tuple != (exp_n, exp_v, exp_g):
            errs.append(f"Quote mismatch for ({sku}, qty={qty}, {cur}): got {got_tuple}, expected {(exp_n, exp_v, exp_g)}")
    return errs


def verify_git_state(repo: Path) -> tuple[str, int, list[str]]:
    errs: list[str] = []
    if not (repo / ".git").is_dir():
        return "", 0, ["Missing .git directory in /workspace/checkout_monorepo"]
    cp_head = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    head_sha = cp_head.stdout.strip() if cp_head.returncode == 0 else ""
    cp_cnt = subprocess.run(["git", "-c", "safe.directory=*", "rev-list", "--count", "HEAD"], cwd=repo, capture_output=True, text=True)
    cnt = int(cp_cnt.stdout.strip()) if cp_cnt.returncode == 0 and cp_cnt.stdout.strip().isdigit() else 0
    cp_st = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    dirty = [ln for ln in cp_st.stdout.splitlines() if ln.strip()]
    if dirty:
        errs.append(f"Git working tree has uncommitted changes: {dirty[:6]}")
    if cnt < 2:
        errs.append("No commits beyond initial v0 baseline on main branch")
    return head_sha, cnt, errs


def render_sso_plate_png(tenant: str, basis: str, bench_calls: int, perf_st: str, sec_st: str) -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1220, 540), (10, 15, 29))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 530)], outline=(56, 189, 248), width=2)
    dr.text((28, 26), f"STAGING FINOPS & CHECKOUT SSO CONSOLE  |  Tenant: {tenant}  |  Basis: {basis}", fill=(56, 189, 248))
    dr.text((28, 56), "Global Caps: memory_footprint_mb <= 336 MB  |  Soak P95 <= 90.0 ms  |  Viewports: 520x760, 768x1024, 1280x720", fill=(226, 232, 240))
    dr.line([(24, 84), (1196, 84)], fill=(51, 65, 85), width=1)

    is_exact = (basis == "MINOR_UNITS_EXACT")
    y = 104
    if tenant == "B2B_WHOLESALE":
        dr.text((28, y), "ACTIVE PROFILE: B2B_WHOLESALE — C PRICING KERNEL & FX CATALOG SPECIFICATION", fill=(251, 191, 36))
        y += 32
        if is_exact:
            rows = [
                "Tier 1 Volume Discount : qty >= 200  ->  1450 bps  (14.50% off unit_usd_cents * qty)",
                "Tier 2 Volume Discount : qty >= 50   ->   925 bps  ( 9.25% off unit_usd_cents * qty)",
                "Tier 3 Volume Discount : qty >= 10   ->   450 bps  ( 4.50% off unit_usd_cents * qty)",
                "Tier 4 Standard Retail : qty <  10   ->     0 bps  ( 0.00% discount)",
                "Half-Up Integer Math   : (val + 5000) / 10000 at Discount, FX, and VAT steps",
                "FX Minor Rates / 10kUSD: USD = 10000 | EUR = 9240 | GBP = 7880 | JPY = 1512000",
                "Gateway Perf Floor     : worker_threads >= 6 | per_worker_cache_mb >= 32 | sqlite_mmap_mb >= 64",
            ]
        else:
            rows = [
                "[APPROX_PREVIEW MODE — SWITCH TO MINOR_UNITS_EXACT FOR INTEGER BPS & FX]",
                "Tier 1 ~15% | Tier 2 ~9% | Tier 3 ~5% | FX approx USD=1.0, EUR=0.92, GBP=0.79, JPY=151",
            ]
        for r in rows:
            dr.text((34, y), r, fill=(241, 245, 249))
            y += 30
    else:
        dr.text((28, y), "ACTIVE PROFILE: FINOPS_LEDGER — CRYPTO AUTH & DOUBLE-ENTRY SUBLEDGER SPECIFICATION", fill=(251, 191, 36))
        y += 32
        if is_exact:
            rows = [
                f"X-Client-Token Secret  : {API_CLIENT_SECRET}",
                f"PBKDF2-SHA256 Salt Hex : {API_SALT_HEX}  (pbkdf2_iterations >= 14000)",
                f"HMAC-SHA256 Master Key : {HMAC_MASTER_SECRET}",
                "Signature String       : '{X-Req-Timestamp}.{X-Req-Nonce}.{sha256_hex(raw_body)}' (+/-300s, 401/409)",
                "Double-Entry Accounts  : DR 1100_AR_CLEARING (gross) = CR 4000_MERCHANT_REV (net) + CR 2150_VAT_PAYABLE (vat)",
                "Historical Backfill    : Backfill ledger_entries for any pre-existing orders in var/staging.db!",
                "Gateway Security Floor : pbkdf2_iterations >= 14000 | auth_cache_mb >= 56 | sqlite_mmap_mb >= 64",
            ]
        else:
            rows = [
                "[APPROX_PREVIEW MODE — SWITCH TO MINOR_UNITS_EXACT FOR CRYPTO KEYS & ACCOUNT CODES]",
                "Secrets masked in preview basis. Click MINOR_UNITS_EXACT button above.",
            ]
        for r in rows:
            dr.text((34, y), r, fill=(241, 245, 249))
            y += 30

    dr.line([(24, 460), (1196, 460)], fill=(51, 65, 85), width=1)
    dr.text(
        (28, 480),
        f"Active Tenant View: {tenant}  |  Numeric Basis: {basis}",
        fill=(167, 243, 208),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Staging SSO Ops Console — FC-02</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 12px; }
    .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 8px 12px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #0284c7; }
    #status { color: #38bdf8; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>TENANT:</strong>
    <button id="btn-b2b" onclick="setUi('B2B_WHOLESALE', null)">B2B_WHOLESALE</button>
    <button id="btn-fin" onclick="setUi('FINOPS_LEDGER', null)">FINOPS_LEDGER</button>
    <strong>BASIS:</strong>
    <button id="btn-exact" onclick="setUi(null, 'MINOR_UNITS_EXACT')">MINOR_UNITS_EXACT</button>
    <button id="btn-approx" onclick="setUi(null, 'APPROX_PREVIEW')">APPROX_PREVIEW</button>
    <button id="btn-csv" onclick="exportCsv()">Export Active Spec CSV (/home/gui/Downloads/staging_spec.csv)</button>
    <span id="status">SSO Session Active</span>
  </div>
  <canvas id="sso-canvas" width="1220" height="540"></canvas>
  <!-- Public protocol reference tokens for transparency:
       /workspace/checkout_monorepo app/pricing_ext.c app/libpricing.so app/server.py app/static/checkout.html
       var/staging.db config/gateway_limits.json http://127.0.0.1:20120
       /api/bench/staging_gate /api/release/submit /api/release/status full_release_gate
       1100_AR_CLEARING 4000_MERCHANT_REV 2150_VAT_PAYABLE 336 14000 90.0 -->
  <script>
    function drawPlate() {
      const cv = document.getElementById('sso-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/spec_plate.png?t=' + Date.now();
    }
    async function setUi(tenant, basis) {
      const b = {};
      if (tenant) b.tenant_profile = tenant;
      if (basis) b.basis = basis;
      const r = await fetch('/api/ui/context', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('status').textContent = (d.tenant_profile || '') + ' / ' + (d.basis || '');
      drawPlate();
    }
    async function exportCsv() {
      const r = await fetch('/api/ui/export_csv', {method: 'POST'});
      const d = await r.json();
      document.getElementById('status').textContent = 'Saved ' + (d.path || '') + ' [' + (d.tenant_profile || '') + ']';
      drawPlate();
    }
    drawPlate();
    setInterval(drawPlate, 3500);
  </script>
</body>
</html>
"""


def _ensure_staging_started_as_gui(repo: Path) -> None:
    try:
        with socket.create_connection(("127.0.0.1", STAGING_PORT), timeout=0.5):
            return
    except OSError:
        pass
    if os.geteuid() == 0:
        subprocess.run(
            ["su", "-s", "/bin/bash", "gui", "-c", f"bash {repo / 'scripts' / 'restart_staging.sh'}"],
            capture_output=True,
            timeout=20,
        )
    else:
        subprocess.run(["bash", str(repo / "scripts" / "restart_staging.sh")], capture_output=True, timeout=20)


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    repo = workspace / "checkout_monorepo"
    staging_ctl_lock = threading.Lock()
    staging_holder: dict[str, subprocess.Popen | None] = {"proc": None}

    def restart_staging_server() -> bool:
        with staging_ctl_lock:
            old_p = staging_holder["proc"]
            if old_p is not None and old_p.poll() is None:
                old_p.terminate()
                try:
                    old_p.wait(timeout=3)
                except Exception:
                    old_p.kill()
            subprocess.run(["pkill", "-f", str(repo / "app" / "server.py")], capture_output=True)
            log_f = (repo / "var" / "staging.log").open("ab")
            git_safe_env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*"}
            cmd = ["python3", str(repo / "app" / "server.py")]
            if os.geteuid() == 0:
                cmd = ["su", "-s", "/bin/bash", "gui", "-c", f"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='*' python3 {repo / 'app' / 'server.py'}"]
            staging_holder["proc"] = subprocess.Popen(cmd, cwd=repo, env=git_safe_env, stdout=log_f, stderr=log_f)
            for _ in range(30):
                c_h, _, _ = http_req(f"http://127.0.0.1:{STAGING_PORT}/health", method="GET", timeout_s=0.6)
                if c_h == 200:
                    return True
                time.sleep(0.15)
            return False

    restart_staging_server()

    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    state_lock = threading.Lock()
    sub_locks = {"checkout_perf": threading.Lock(), "security_ledger": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {
            "tenant_profile": "B2B_WHOLESALE",
            "basis": "MINOR_UNITS_EXACT",
        },
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"checkout_perf": {}, "security_ledger": {}},
        "qualified_suites": {"checkout_perf": {}, "security_ledger": {}},
        "last_full_release_gate": {},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args) -> None:
            return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            raw_cookie = self.headers.get("Cookie") or ""
            c = SimpleCookie()
            try:
                c.load(raw_cookie)
                morsel = c.get("fc02_sso")
                return bool(morsel and morsel.value == sso_cookie_val)
            except Exception:
                return False

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            qs = parse_qs(parsed.query)

            if p == "/health":
                self._json(200, {"ok": True, "task_id": TASK_ID})
                return

            if p == "/":
                if (qs.get("sso_boot") or [""])[0] == sso_boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"fc02_sso={sso_cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if p == "/ui/spec_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; inspect the open Chromium console on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_sso_plate_png(
                        pstate["ui_session"]["tenant_profile"],
                        pstate["ui_session"]["basis"],
                        pstate["bench_calls"],
                        (pstate["submissions"].get("checkout_perf") or {}).get("status", "PENDING"),
                        (pstate["submissions"].get("security_ledger") or {}).get("status", "PENDING"),
                    )
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return

            if p == "/api/release/status":
                sub_q = (qs.get("subsystem") or [""])[0].strip().lower()
                if sub_q not in ("checkout_perf", "security_ledger"):
                    self._json(400, {"error": "Pass ?subsystem=checkout_perf or ?subsystem=security_ledger"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_suites": pstate["qualified_suites"][sub_q],
                        "last_full_release_gate": pstate["last_full_release_gate"].get(sub_q),
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return

            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/context":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; click buttons in Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    changed = False
                    if body.get("tenant_profile") in ("B2B_WHOLESALE", "FINOPS_LEDGER"):
                        if pstate["ui_session"]["tenant_profile"] != body["tenant_profile"]:
                            changed = True
                        pstate["ui_session"]["tenant_profile"] = body["tenant_profile"]
                    if body.get("basis") in ("MINOR_UNITS_EXACT", "APPROX_PREVIEW"):
                        if pstate["ui_session"]["basis"] != body["basis"]:
                            changed = True
                        pstate["ui_session"]["basis"] = body["basis"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/export_csv":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; click Export in Chromium on DISPLAY=:99"})
                    return
                dl_p = Path("/home/gui/Downloads/staging_spec.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    tp = pstate["ui_session"]["tenant_profile"]
                    bs = pstate["ui_session"]["basis"]
                    lines = ["tenant_profile,basis,key,value"]
                    if bs != "MINOR_UNITS_EXACT":
                        lines.append(f"{tp},{bs},warning,SWITCH_TO_MINOR_UNITS_EXACT")
                    elif tp == "B2B_WHOLESALE":
                        for mq, bps in TIER_DISCOUNT_BPS:
                            lines.append(f"{tp},{bs},tier_min_qty_{mq}_bps,{bps}")
                        for cur, rate in FX_RATES_MINOR_PER_10K_USD.items():
                            lines.append(f"{tp},{bs},fx_{cur}_per_10k_usd,{rate}")
                    else:
                        lines.append(f"{tp},{bs},client_token,{API_CLIENT_SECRET}")
                        lines.append(f"{tp},{bs},pbkdf2_salt_hex,{API_SALT_HEX}")
                        lines.append(f"{tp},{bs},hmac_master_secret,{HMAC_MASTER_SECRET}")
                        lines.append(f"{tp},{bs},pbkdf2_min_iterations,{MIN_PBKDF2_ITERATIONS}")
                        lines.append(f"{tp},{bs},accounts,1100_AR_CLEARING|4000_MERCHANT_REV|2150_VAT_PAYABLE")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o666)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_p), "tenant_profile": tp, "basis": bs})
                return

            if p == "/api/staging/ctl":
                ok = restart_staging_server()
                self._json(200 if ok else 500, {"ok": ok})
                return

            if p == "/api/bench/staging_gate":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                suite = str(body.get("suite") or "").strip().lower()
                valid_suites = set(PERF_SUITES) | set(SEC_SUITES) | {"full_release_gate"}
                if sub not in ("checkout_perf", "security_ledger") or suite not in valid_suites:
                    self._json(400, {"error": f"Invalid subsystem={sub} or suite={suite}"})
                    return
                seq_suites = list(PERF_SUITES if sub == "checkout_perf" else SEC_SUITES) + ["full_release_gate"]
                if suite not in seq_suites:
                    self._json(400, {"error": f"Suite {suite} does not belong to {sub}"})
                    return
                s_idx = seq_suites.index(suite)
                with state_lock:
                    prev_miss = [seq_suites[i] for i in range(s_idx) if not pstate["qualified_suites"][sub].get(seq_suites[i])]
                if prev_miss:
                    self._json(422, {"status": "SUITE_ORDER_VIOLATION", "error": f"Qualify prerequisite suites first: {prev_miss}"})
                    return

                staging_url = f"http://127.0.0.1:{STAGING_PORT}"
                soak_s = 1.0 if fast_selfval else float(os.environ.get("PARAGUI_FC02_SOAK_S", "285.0"))

                exp_reg = "B2B_WHOLESALE" if sub == "checkout_perf" else "FINOPS_LEDGER"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["tenant_profile"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    errs: list[str] = []
                    soak_stats = {"total_requests": 0, "failed_requests": 0, "p95_ms": 0.0}

                    lim_summary, lim_errs = verify_gateway_limits(
                        repo,
                        check_perf=(sub == "checkout_perf"),
                        check_sec=(sub == "security_ledger"),
                    )
                    errs.extend(lim_errs)

                    if suite in ("pricing_c_kernel", "fx_catalog_soak", "burst_throughput", "full_release_gate") and sub == "checkout_perf":
                        errs.extend(verify_pricing_and_fx_live(staging_url, repo))
                    if suite in ("responsive_viewport_e2e", "full_release_gate") and sub == "checkout_perf":
                        errs.extend(verify_viewports_chromium(staging_url, repo, check_perf=True, check_sec=False))

                    if suite in ("crypto_replay_guard", "double_entry_idempotency", "concurrent_ledger_soak", "full_release_gate") and sub == "security_ledger":
                        errs.extend(verify_security_and_ledger_live(staging_url, repo))
                    if suite in ("audit_viewport_e2e", "full_release_gate") and sub == "security_ledger":
                        errs.extend(verify_viewports_chromium(staging_url, repo, check_perf=False, check_sec=True))

                    soak_stats = run_soak_burst(
                        staging_url,
                        duration_s=soak_s,
                        workers=(2 if fast_selfval else 3),
                        do_checkouts=True,
                    )
                    if soak_stats["failed_requests"] > 0:
                        errs.append(f"Live staging brownout/errors during soak: {soak_stats['failed_requests']} failed HTTP requests")
                    if soak_stats["p95_ms"] > MAX_SOAK_P95_MS:
                        errs.append(f"Live soak p95_ms={soak_stats['p95_ms']} exceeds max {MAX_SOAK_P95_MS} ms")

                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                head_sha, _, _ = verify_git_state(repo)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[suite] = _reg_sampler.purity
                    if passed and suite != "full_release_gate":
                        pstate["qualified_suites"][sub][suite] = True
                    if passed and suite == "full_release_gate":
                        pstate["last_full_release_gate"][sub] = {
                            "passed": True,
                            "git_head": head_sha,
                            "soak_stats": soak_stats,
                            "timestamp": time.time(),
                        }
                    pstate["bench_history"].append({
                        "timestamp": time.time(),
                        "subsystem": sub,
                        "suite": suite,
                        "passed": passed,
                        "soak_stats": soak_stats,
                        "elapsed_s": elapsed,
                    })
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "suite": suite,
                    "passed": passed,
                    "discrepancies": errs,
                    "gateway_limits": lim_summary,
                    "soak_stats": soak_stats,
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/release/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("checkout_perf", "security_ledger"):
                    self._json(400, {"error": "subsystem must be 'checkout_perf' or 'security_ledger'"})
                    return

                staging_url = f"http://127.0.0.1:{STAGING_PORT}"
                head_sha, _, git_errs = verify_git_state(repo)
                lim_summary, lim_errs = verify_gateway_limits(
                    repo,
                    check_perf=(sub == "checkout_perf"),
                    check_sec=(sub == "security_ledger"),
                )
                errs = list(git_errs) + list(lim_errs) + verify_clean_workspace(workspace)

                if sub == "checkout_perf":
                    errs.extend(verify_pricing_and_fx_live(staging_url, repo))
                    errs.extend(verify_viewports_chromium(staging_url, repo, check_perf=True, check_sec=False))
                    req_suites = PERF_SUITES
                else:
                    errs.extend(verify_security_and_ledger_live(staging_url, repo))
                    errs.extend(verify_viewports_chromium(staging_url, repo, check_perf=False, check_sec=True))
                    req_suites = SEC_SUITES

                with state_lock:
                    q_map = pstate["qualified_suites"][sub]
                    missing_s = [s for s in req_suites if not q_map.get(s)]
                    if missing_s:
                        errs.append(f"Unqualified staging_gate suites for {sub}: {missing_s}")
                    if not (pstate["last_full_release_gate"].get(sub) or {}).get("passed"):
                        errs.append(f"{sub} has not passed suite='full_release_gate'")

                if str(body.get("git_head") or "").strip() != head_sha:
                    errs.append(f"Submitted git_head={body.get('git_head')} != current repo HEAD {head_sha}")
                try:
                    if int(body.get("memory_footprint_mb", -1)) != lim_summary.get("memory_footprint_mb", -2):
                        errs.append(f"Submitted memory_footprint_mb != live {lim_summary.get('memory_footprint_mb')}")
                    if sub == "checkout_perf":
                        live_so_sha = sha256_file(repo / "app" / "libpricing.so")
                        if str(body.get("libpricing_sha256") or "") != live_so_sha:
                            errs.append("Submitted libpricing_sha256 != sha256(app/libpricing.so)")
                    else:
                        if int(body.get("pbkdf2_iterations", -1)) != lim_summary.get("pbkdf2_iterations", -2):
                            errs.append("Submitted pbkdf2_iterations != config/gateway_limits.json")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {
                        "status": "REJECTED_RELEASE_GATE",
                        "subsystem": sub,
                        "errors": errs,
                        "git_head": head_sha,
                        "gateway_limits": lim_summary,
                    })
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "git_head": head_sha,
                    "memory_footprint_mb": lim_summary["memory_footprint_mb"],
                    "timestamp": time.time(),
                }
                with state_lock:
                    pstate["submissions"][sub] = rec
                    persist()
                self._json(200, rec)
                return

            self._json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={sso_boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def audit_case_transparency() -> dict:
    return audit_protocol_transparency(
        build_tickets_by_role(),
        PORTAL_HTML,
        REQUIRED_PUBLIC_TOKENS,
    )


def _is_git_ancestor(repo: Path, ancestor_sha: str, head_sha: str) -> bool:
    if not ancestor_sha or not head_sha:
        return False
    cp = subprocess.run(
        ["git", "-c", "safe.directory=*", "merge-base", "--is-ancestor", ancestor_sha, head_sha],
        cwd=repo,
        capture_output=True,
    )
    return cp.returncode == 0


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    repo = workspace / "checkout_monorepo"
    subs = portal_state.get("submissions") or {}
    sub_perf = subs.get("checkout_perf") or {}
    sub_sec = subs.get("security_ledger") or {}
    perf_signed = sub_perf.get("status") == "APPROVED"
    sec_signed = sub_sec.get("status") == "APPROVED"
    closed_cnt = int(perf_signed) + int(sec_signed)

    head_sha, commit_cnt, git_errs = verify_git_state(repo)
    perf_anc = bool(perf_signed and _is_git_ancestor(repo, str(sub_perf.get("git_head") or ""), head_sha))
    sec_anc = bool(sec_signed and _is_git_ancestor(repo, str(sub_sec.get("git_head") or ""), head_sha))
    lim_summary, lim_errs = verify_gateway_limits(repo, check_perf=True, check_sec=True)

    staging_url = f"http://127.0.0.1:{STAGING_PORT}"
    srv_proc = None
    pricing_errs: list[str] = []
    sec_errs: list[str] = []
    vp_errs: list[str] = []
    soak_ok = False
    try:
        if (repo / "app" / "server.py").is_file():
            srv_proc = subprocess.Popen(
                ["python3", str(repo / "app" / "server.py")],
                cwd=repo,
                env={**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*"},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            booted = False
            for _ in range(30):
                c_h, _, _ = http_req(f"{staging_url}/health", method="GET", timeout_s=1.0)
                if c_h == 200:
                    booted = True
                    break
                time.sleep(0.2)
            if not booted:
                pricing_errs.append("Final app/server.py failed to boot on 127.0.0.1:20120")
                sec_errs.append("Final app/server.py failed to boot on 127.0.0.1:20120")
                vp_errs.append("Final app/server.py failed to boot on 127.0.0.1:20120")
            else:
                pricing_errs = verify_pricing_and_fx_live(staging_url, repo)
                sec_errs = verify_security_and_ledger_live(staging_url, repo)
                vp_errs = verify_viewports_chromium(staging_url, repo, check_perf=True, check_sec=True)
                soak = run_soak_burst(staging_url, duration_s=1.2, workers=4, do_checkouts=True)
                soak_ok = (soak["failed_requests"] == 0 and soak["p95_ms"] <= MAX_SOAK_P95_MS)
        else:
            pricing_errs.append("Missing app/server.py")
            sec_errs.append("Missing app/server.py")
            vp_errs.append("Missing app/server.py")
    finally:
        if srv_proc is not None:
            srv_proc.terminate()
            try:
                srv_proc.wait(timeout=3)
            except Exception:
                srv_proc.kill()

    pur_p_errs = verify_stage_regime_purity(portal_state, "checkout_perf", PERF_SUITES[1:] + ("full_release_gate",))
    pur_s_errs = verify_stage_regime_purity(portal_state, "security_ledger", SEC_SUITES[1:] + ("full_release_gate",))
    trans = audit_case_transparency()
    invariants = {
        "checkout_perf_signed_and_pricing_valid": bool(len(pur_p_errs) == 0 and perf_signed and perf_anc and len(pricing_errs) == 0),
        "security_ledger_signed_and_balanced": bool(len(pur_s_errs) == 0 and sec_signed and sec_anc and len(sec_errs) == 0),
        "multi_viewport_chromium_e2e_valid": bool(len(vp_errs) == 0),
        "gateway_memory_and_soak_sla_valid": bool(len(lim_errs) == 0 and soak_ok),
        "git_main_clean_and_commits_preserved": bool(len(git_errs) == 0 and len(verify_clean_workspace(workspace)) == 0 and len(pur_p_errs) == 0 and len(pur_s_errs) == 0 and perf_anc and sec_anc),
    }
    inv_score = round(sum(1 for v in invariants.values() if v) / len(invariants), 4)
    joint_pass = all(invariants.values())

    return {
        "task_id": TASK_ID,
        "joint_pass": joint_pass,
        "invariants": invariants,
        "cross_role_invariant_score": inv_score,
        "closed_tickets_count": closed_cnt,
        "local_completion_rate": round(closed_cnt / 2.0, 4),
        "unaware_race_failure": bool(closed_cnt > 0 and not joint_pass),
        "total_bench_calls": int(portal_state.get("bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "gateway_limits": lim_summary,
        "git_head": head_sha,
        "git_commit_count": commit_cnt,
        "diagnostics": {
            "git_errors": git_errs,
            "limit_errors": lim_errs,
            "pricing_errors": pricing_errs,
            "security_ledger_errors": sec_errs,
            "viewport_errors": vp_errs,
        },
        "protocol_transparency": trans,
    }


FIXED_PRICING_C = """#include <stdint.h>

void compute_quote_cents(
    int64_t unit_usd_cents,
    int64_t qty,
    int64_t fx_per_10k_usd,
    int64_t vat_bps,
    int64_t* out_net_cents,
    int64_t* out_vat_cents,
    int64_t* out_gross_cents
) {
    int64_t disc_bps = 0;
    if (qty >= 200) disc_bps = 1450;
    else if (qty >= 50) disc_bps = 925;
    else if (qty >= 10) disc_bps = 450;

    int64_t raw_usd = unit_usd_cents * qty;
    int64_t disc_usd = (raw_usd * (10000 - disc_bps) + 5000) / 10000;
    int64_t net_minor = (disc_usd * fx_per_10k_usd + 5000) / 10000;
    int64_t vat_minor = (net_minor * vat_bps + 5000) / 10000;
    *out_net_cents = net_minor;
    *out_vat_cents = vat_minor;
    *out_gross_cents = net_minor + vat_minor;
}
"""

SECURITY_LEDGER_SERVER_PY = """#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "var" / "staging.db"
SO_PATH = ROOT / "app" / "libpricing.so"
HTML_PATH = ROOT / "app" / "static" / "checkout.html"
LIMITS_PATH = ROOT / "config" / "gateway_limits.json"

HMAC_SECRET = b"fc02-staging-hmac-key-2026-v1"
EXPECTED_CLIENT_TOKEN = "fc02-merchant-pbkdf2-token-9941"
SALT_BYTES = bytes.fromhex("73746167696e675f666330325f73616c74")

_lib = ctypes.CDLL(str(SO_PATH))
_lib.compute_quote_cents.argtypes = [
    ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
    ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64),
]
_lib.compute_quote_cents.restype = None

_db_lock = threading.Lock()
_auth_cache: dict[tuple[str, int], bytes] = {}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def init_security_schema() -> None:
    with _db_lock, get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS replay_nonces(nonce TEXT PRIMARY KEY, created_at REAL);")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS idempotency_records(idem_key TEXT PRIMARY KEY, order_id TEXT, response_json TEXT);"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ledger_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, account_code TEXT, debit_cents INTEGER, credit_cents INTEGER);"
        )
        unposted = conn.execute(
            "SELECT order_id, net_cents, vat_cents, gross_cents FROM orders WHERE order_id NOT IN (SELECT DISTINCT order_id FROM ledger_entries)"
        ).fetchall()
        for r in unposted:
            oid = r["order_id"]
            conn.executemany(
                "INSERT INTO ledger_entries(order_id, account_code, debit_cents, credit_cents) VALUES (?,?,?,?)",
                [
                    (oid, "1100_AR_CLEARING", int(r["gross_cents"]), 0),
                    (oid, "4000_MERCHANT_REV", 0, int(r["net_cents"])),
                    (oid, "2150_VAT_PAYABLE", 0, int(r["vat_cents"])),
                ],
            )
        conn.commit()


def verify_request_auth(headers, raw_body: bytes) -> tuple[int, str]:
    limits = json.loads(LIMITS_PATH.read_text(encoding="utf-8"))
    iters = max(1, int(limits.get("pbkdf2_iterations", 14000)))
    use_cache = int(limits.get("auth_cache_mb", 0)) >= 56

    tok = str(headers.get("X-Client-Token") or "")
    ts_str = str(headers.get("X-Req-Timestamp") or "")
    nonce = str(headers.get("X-Req-Nonce") or "")
    sig = str(headers.get("X-Req-Signature") or "")
    if not tok or not ts_str or not nonce or not sig:
        return 401, "Missing authentication headers"

    ck = (tok, iters)
    exp_ck = (EXPECTED_CLIENT_TOKEN, iters)
    if use_cache and ck in _auth_cache and exp_ck in _auth_cache:
        dk = _auth_cache[ck]
        exp_dk = _auth_cache[exp_ck]
    else:
        dk = hashlib.pbkdf2_hmac("sha256", tok.encode("utf-8"), SALT_BYTES, iters)
        exp_dk = hashlib.pbkdf2_hmac("sha256", EXPECTED_CLIENT_TOKEN.encode("utf-8"), SALT_BYTES, iters)
        if use_cache and len(_auth_cache) < 256:
            _auth_cache[ck] = dk
            _auth_cache[exp_ck] = exp_dk
    if not hmac.compare_digest(dk, exp_dk):
        return 401, "Invalid X-Client-Token"

    body_sha = hashlib.sha256(raw_body).hexdigest()
    msg = f"{ts_str}.{nonce}.{body_sha}".encode("utf-8")
    exp_sig = hmac.new(HMAC_SECRET, msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, exp_sig):
        return 401, "Invalid X-Req-Signature"

    try:
        ts_val = int(ts_str)
    except ValueError:
        return 409, "Invalid timestamp"
    if abs(time.time() - ts_val) > 300:
        return 409, "Stale timestamp outside 300s window"

    with _db_lock, get_conn() as conn:
        try:
            conn.execute("INSERT INTO replay_nonces(nonce, created_at) VALUES (?, ?)", (nonce, time.time()))
            conn.commit()
        except sqlite3.IntegrityError:
            return 409, "Replayed nonce"
    return 200, ""


def calc_quote(sku: str, qty: int, currency: str) -> dict:
    with get_conn() as conn:
        prod = conn.execute("SELECT unit_usd_cents, vat_bps FROM products WHERE sku = ?", (sku,)).fetchone()
        fx_row = conn.execute("SELECT rate_per_10k_usd FROM fx_rates WHERE currency = ?", (currency,)).fetchone()
    if not prod or not fx_row:
        raise ValueError(f"Unknown sku={sku} or currency={currency}")
    net_c, vat_c, gross_c = ctypes.c_int64(0), ctypes.c_int64(0), ctypes.c_int64(0)
    _lib.compute_quote_cents(
        int(prod["unit_usd_cents"]), int(qty), int(fx_row["rate_per_10k_usd"]), int(prod["vat_bps"]),
        ctypes.byref(net_c), ctypes.byref(vat_c), ctypes.byref(gross_c),
    )
    return {
        "sku": sku,
        "qty": int(qty),
        "currency": currency,
        "net_cents": int(net_c.value),
        "vat_cents": int(vat_c.value),
        "gross_cents": int(gross_c.value),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        return

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        p = urlparse(self.path).path
        if p == "/health":
            limits = json.loads(LIMITS_PATH.read_text(encoding="utf-8"))
            self._json(200, {"ok": True, "limits": limits})
            return
        if p in ("/", "/checkout.html"):
            raw = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if p == "/api/ledger/trial_balance":
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT account_code, COALESCE(SUM(debit_cents),0) AS d, COALESCE(SUM(credit_cents),0) AS c FROM ledger_entries GROUP BY account_code"
                ).fetchall()
            accts = {r["account_code"]: {"debit": int(r["d"]), "credit": int(r["c"])} for r in rows}
            tot_d = sum(v["debit"] for v in accts.values())
            tot_c = sum(v["credit"] for v in accts.values())
            self._json(200, {
                "balanced": (tot_d == tot_c and tot_d > 0),
                "total_debit_cents": tot_d,
                "total_credit_cents": tot_c,
                "accounts": accts,
            })
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n > 0 else b"{}"
        acode, aerr = verify_request_auth(self.headers, raw)
        if acode != 200:
            self._json(acode, {"error": aerr})
            return
        body = json.loads(raw.decode("utf-8"))

        if p == "/api/cart/quote":
            try:
                self._json(200, calc_quote(str(body["sku"]), int(body["qty"]), str(body.get("currency", "USD"))))
            except Exception as exc:
                self._json(400, {"error": str(exc)})
            return

        if p == "/api/cart/checkout":
            idem_key = str(self.headers.get("Idempotency-Key") or "").strip()
            try:
                with _db_lock, get_conn() as conn:
                    if idem_key:
                        ex = conn.execute("SELECT response_json FROM idempotency_records WHERE idem_key = ?", (idem_key,)).fetchone()
                        if ex:
                            self._json(200, json.loads(ex["response_json"]))
                            return
                    q = calc_quote(str(body["sku"]), int(body["qty"]), str(body.get("currency", "USD")))
                    order_id = "ord_" + secrets.token_hex(6)
                    conn.execute(
                        "INSERT INTO orders(order_id, sku, qty, currency, net_cents, vat_cents, gross_cents, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (order_id, q["sku"], q["qty"], q["currency"], q["net_cents"], q["vat_cents"], q["gross_cents"], time.time()),
                    )
                    conn.executemany(
                        "INSERT INTO ledger_entries(order_id, account_code, debit_cents, credit_cents) VALUES (?,?,?,?)",
                        [
                            (order_id, "1100_AR_CLEARING", q["gross_cents"], 0),
                            (order_id, "4000_MERCHANT_REV", 0, q["net_cents"]),
                            (order_id, "2150_VAT_PAYABLE", 0, q["vat_cents"]),
                        ],
                    )
                    resp_payload = {"order_id": order_id, **q}
                    if idem_key:
                        conn.execute(
                            "INSERT INTO idempotency_records(idem_key, order_id, response_json) VALUES (?,?,?)",
                            (idem_key, order_id, json.dumps(resp_payload)),
                        )
                    conn.commit()
                self._json(200, resp_payload)
            except Exception as exc:
                self._json(400, {"error": str(exc)})
            return

        self._json(404, {"error": "Not found"})


if __name__ == "__main__":
    init_security_schema()
    srv = ThreadingHTTPServer(("127.0.0.1", 20120), Handler)
    srv.serve_forever()
"""


def _cooperatively_patch_checkout_html(html_p: Path, role: str) -> None:
    src = html_p.read_text(encoding="utf-8")
    if role == "checkout_perf_lead":
        src = src.replace(
            "#quote-card { width: 680px; padding: 16px; background: #ffffff; border: 1px solid #cbd5e1; margin-bottom: 14px; }",
            "#quote-card { box-sizing: border-box; width: 100%; max-width: 680px; padding: 16px; background: #ffffff; border: 1px solid #cbd5e1; margin-bottom: 14px; }",
        )
        src = src.replace(
            "#pay-submit-btn { display: inline-block; width: 640px; padding: 12px; background: #0284c7; color: #fff; border: 0; font-weight: bold; }",
            "#pay-submit-btn { box-sizing: border-box; display: block; width: 100%; max-width: 640px; padding: 12px; background: #0284c7; color: #fff; border: 0; font-weight: bold; }",
        )
        # Also prevent peer panel from causing documentElement.scrollWidth overflow if peer hasn't patched yet!
        if "overflow-x: hidden" not in src:
            src = src.replace(
                "body { margin: 0; padding: 12px; font-family: sans-serif; background: #f8fafc; color: #0f172a; }",
                "html, body { max-width: 100%; overflow-x: hidden; box-sizing: border-box; } body { margin: 0; padding: 12px; font-family: sans-serif; background: #f8fafc; color: #0f172a; }",
            )
    else:
        src = src.replace(
            "#ledger-audit-panel { width: 710px; padding: 16px; background: #ffffff; border: 1px solid #cbd5e1; }",
            "#ledger-audit-panel { box-sizing: border-box; width: 100%; max-width: 710px; padding: 16px; background: #ffffff; border: 1px solid #cbd5e1; }",
        )
        src = src.replace(
            "#audit-table { width: 690px; border-collapse: collapse; }",
            "#audit-table { box-sizing: border-box; width: 100%; max-width: 690px; border-collapse: collapse; }",
        )
        src = src.replace('data-status="UNVERIFIED">PENDING_AUDIT', 'data-status="BALANCED_ACTIVE">BALANCED_ACTIVE')
        if "overflow-x: hidden" not in src:
            src = src.replace(
                "body { margin: 0; padding: 12px; font-family: sans-serif; background: #f8fafc; color: #0f172a; }",
                "html, body { max-width: 100%; overflow-x: hidden; box-sizing: border-box; } body { margin: 0; padding: 12px; font-family: sans-serif; background: #f8fafc; color: #0f172a; }",
            )
    html_p.write_text(src, encoding="utf-8")


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    """Cooperative single-role reference solver that inspects live repo/DB/limits and adapts bidirectionally."""
    assert role in ("checkout_perf_lead", "security_ledger_lead")
    repo = workspace / "checkout_monorepo"
    base = f"http://127.0.0.1:{portal_port}"
    admin_key_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": admin_key_p.read_text(encoding="utf-8").strip()} if admin_key_p.is_file() else {}

    tp = "B2B_WHOLESALE" if role == "checkout_perf_lead" else "FINOPS_LEDGER"
    http_req(f"{base}/api/ui/context", method="POST", body_obj={"tenant_profile": tp, "basis": "MINOR_UNITS_EXACT"}, headers={"Content-Type": "application/json", **adm_hdr})
    http_req(f"{base}/api/ui/export_csv", method="POST", headers=adm_hdr)

    lp = repo / "config" / "gateway_limits.json"
    cur_lim = json.loads(lp.read_text(encoding="utf-8"))

    if role == "checkout_perf_lead":
        (repo / "app" / "pricing_ext.c").write_text(FIXED_PRICING_C, encoding="utf-8")
        subprocess.run(
            ["gcc", "-O2", "-shared", "-fPIC", str(repo / "app" / "pricing_ext.c"), "-o", str(repo / "app" / "libpricing.so")],
            check=True,
            capture_output=True,
            timeout=30,
        )
        with sqlite3.connect(str(repo / "var" / "staging.db")) as conn:
            for cur, rate in FX_RATES_MINOR_PER_10K_USD.items():
                conn.execute("INSERT OR REPLACE INTO fx_rates(currency, rate_per_10k_usd) VALUES (?, ?)", (cur, rate))
            conn.commit()
        _cooperatively_patch_checkout_html(repo / "app" / "static" / "checkout.html", role)
        if int(cur_lim.get("auth_cache_mb", 0)) >= MIN_AUTH_CACHE_MB:
            new_lim = {
                "worker_threads": 6,
                "per_worker_cache_mb": 32,
                "sqlite_mmap_mb": 64,
                "auth_cache_mb": 64,
                "pbkdf2_iterations": int(cur_lim.get("pbkdf2_iterations", 14000)),
            }
        else:
            new_lim = {
                "worker_threads": 7,
                "per_worker_cache_mb": 36,
                "sqlite_mmap_mb": 64,
                "auth_cache_mb": int(cur_lim.get("auth_cache_mb", 0)),
                "pbkdf2_iterations": int(cur_lim.get("pbkdf2_iterations", 1000)),
            }
        write_json(lp, new_lim)
        sub = "checkout_perf"
        suites = PERF_SUITES
    else:
        (repo / "app" / "server.py").write_text(SECURITY_LEDGER_SERVER_PY, encoding="utf-8")
        os.chmod(repo / "app" / "server.py", 0o755)
        _cooperatively_patch_checkout_html(repo / "app" / "static" / "checkout.html", role)
        if int(cur_lim.get("worker_threads", 4)) >= MIN_WORKER_THREADS_PERF:
            new_lim = {
                "worker_threads": 6,
                "per_worker_cache_mb": 32,
                "sqlite_mmap_mb": 64,
                "auth_cache_mb": 64,
                "pbkdf2_iterations": 14000,
            }
        else:
            new_lim = {
                "worker_threads": 4,
                "per_worker_cache_mb": 40,
                "sqlite_mmap_mb": 80,
                "auth_cache_mb": 80,
                "pbkdf2_iterations": 14000,
            }
        write_json(lp, new_lim)
        sub = "security_ledger"
        suites = SEC_SUITES

    subprocess.run(["chown", "-R", "1000:0", str(repo)], capture_output=True)
    post_json(f"{base}/api/staging/ctl", {"action": "restart"}, timeout_s=20)

    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": role,
        "GIT_AUTHOR_EMAIL": f"{role}@paragui.local",
        "GIT_COMMITTER_NAME": role,
        "GIT_COMMITTER_EMAIL": f"{role}@paragui.local",
    }
    subprocess.run(["git", "-c", "safe.directory=*", "add", "-A"], cwd=repo, env=git_env, check=True, capture_output=True)
    subprocess.run(["git", "-c", "safe.directory=*", "commit", "-m", f"Qualify {sub}"], cwd=repo, env=git_env, check=True, capture_output=True)
    subprocess.run(["chown", "-R", "1000:0", str(repo)], capture_output=True)

    for s in suites:
        code, resp = post_json(f"{base}/api/bench/staging_gate", {"subsystem": sub, "suite": s}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} suite {s} failed: {resp}"

    code, resp = post_json(f"{base}/api/bench/staging_gate", {"subsystem": sub, "suite": "full_release_gate"}, timeout_s=240)
    if strict:
        assert code == 200 and resp.get("passed"), f"{role} full_release_gate failed: {resp}"

    head_sha, _, _ = verify_git_state(repo)
    lim_s, _ = verify_gateway_limits(repo, check_perf=False, check_sec=False)
    sub_payload = {
        "subsystem": sub,
        "git_head": head_sha,
        "memory_footprint_mb": lim_s["memory_footprint_mb"],
    }
    if sub == "checkout_perf":
        sub_payload["libpricing_sha256"] = sha256_file(repo / "app" / "libpricing.so")
    else:
        sub_payload["pbkdf2_iterations"] = lim_s["pbkdf2_iterations"]
    code, sresp = post_json(f"{base}/api/release/submit", sub_payload, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    """Gate 3: Simulate two concurrent roles branching/caching from v0 without merging checkout.html/gateway_limits/git."""
    repo = workspace / "checkout_monorepo"
    base = f"http://127.0.0.1:{portal_port}"
    v0_html = (repo / "app" / "static" / "checkout.html").read_text(encoding="utf-8")
    v0_head, _, _ = verify_git_state(repo)

    solve_role("checkout_perf_lead", workspace, portal_port)

    # Second concurrent actor resets/overwrites shared files from its cached v0 working copy
    subprocess.run(["git", "-c", "safe.directory=*", "reset", "--hard", v0_head], cwd=repo, check=True, capture_output=True)
    (repo / "app" / "static" / "checkout.html").write_text(v0_html, encoding="utf-8")
    solve_role("security_ledger_lead", workspace, portal_port, strict=False)

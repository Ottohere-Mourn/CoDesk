"""NF2-02: W3C ServiceWorker + CacheStorage Origin Fetch Interception — Payment Chaos Fault-Cache vs. Cloud FinOps RI Amortization."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    file_atomic_lock,
    launch_chromium_natural,
    make_canary_code,
    read_json_safe,
    write_json,
    write_multipage_sop_pdf,
)

TASK_ID = "NF2-02"
PORTAL_PORT = 19602

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Same-Origin W3C ServiceWorker Fetch-Cache Interception: 3DS Checkout Chaos Fault-Injection vs. Multi-Cloud RI FinOps Close",
    "domain": "Payment Reliability Chaos Engineering & Multi-Cloud FinOps Commitment Accounting (Chromium ServiceWorker + SQLite)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("checkout_chaos_engineer", "cloud_finops_analyst"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

CHAOS_CERT_CODE = make_canary_code("SW-CHAOS", "3ds-circuit-breaker")
FINOPS_LIVE_TOKEN = make_canary_code("FINOPS-LIVE", "ri-cur-2026q4")
STALE_MOCK_TOKEN = "FINOPS-MOCK-CHAOS-STALE-0000"

LIVE_RI_RATES = {
    "m7i.4xlarge": {"hourly_commit_usd": 0.4480, "ondemand_usd": 0.8064},
    "c7g.8xlarge": {"hourly_commit_usd": 0.6120, "ondemand_usd": 1.1600},
    "r6i.2xlarge": {"hourly_commit_usd": 0.2940, "ondemand_usd": 0.5040},
    "n2d-standard-16": {"hourly_commit_usd": 0.4150, "ondemand_usd": 0.7580},
}
MOCK_CHAOS_RATES = {k: {"hourly_commit_usd": round(v["hourly_commit_usd"] * 1.42, 4), "ondemand_usd": v["ondemand_usd"]} for k, v in LIVE_RI_RATES.items()}
# EDP enterprise private-pricing tier discount (in secondary SQLite table edp_private_ppa)
EDP_DISCOUNT_PCT = 0.045


def _generate_chaos_traces() -> list[dict[str, Any]]:
    psps = ["ADYEN_EU", "STRIPE_UK", "WORLDLINE_FR", "CHECKOUT_DE"]
    rows: list[dict[str, Any]] = []
    for i in range(1, 401):
        psp = psps[(i * 3) % 4]
        attempt = 2 if (i % 11 == 0) else 1
        # Inject 16 duplicate webhook deliveries with same tx_id & attempt
        is_dup = (i % 25 == 0)
        lat_ms = (420 + (i % 9) * 35) if psp != "WORLDLINE_FR" else (1890 + (i % 7) * 140)
        # Watch unit: schema_v==2 logs latency in microseconds!
        sch_v = 2 if (i % 13 == 0) else 1
        raw_lat = lat_ms * 1000 if sch_v == 2 else lat_ms
        outcome = "CAPTURED"
        if i % 17 == 0:
            outcome = "SOFT_DECLINE_3DS_FALLBACK_OK"
        elif i % 23 == 0:
            outcome = "CIRCUIT_OPEN_SHED"
        elif i % 31 == 0:
            outcome = "SANDBOX_SYNTHETIC_PING"
        rows.append({
            "event_seq": len(rows) + 1, "tx_id": f"TX-{(i - 1 if is_dup else i):04d}", "attempt_no": attempt,
            "psp_id": psp, "schema_v": sch_v, "raw_latency": raw_lat, "amount_eur": round(45.0 + (i % 19) * 7.5, 2),
            "outcome": outcome,
        })
    return rows


def _generate_cur_rows() -> list[dict[str, Any]]:
    skus = list(LIVE_RI_RATES.keys())
    rows: list[dict[str, Any]] = []
    for i in range(1, 441):
        sku = skus[(i * 5) % 4]
        hrs = 24.0 if (i % 9 != 0) else 12.0
        line_type = "DiscountedUsage"
        if i % 19 == 0:
            line_type = "RIFee"  # Monthly recurring summary line — do not double-count with DiscountedUsage!
        elif i % 29 == 0:
            line_type = "Credit_Promo_Sandbox"
        elif i % 37 == 0:
            line_type = "UnusedCommitmentWaste"
        rows.append({
            "line_id": i, "instance_sku": sku, "account_env": "SANDBOX_DEV" if i % 29 == 0 else "PROD_WORKLOAD",
            "line_item_type": line_type, "usage_hours": hrs,
        })
    return rows


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    # Role A Oracle
    seen: dict[tuple[str, int], dict[str, Any]] = {}
    for r in _generate_chaos_traces():
        seen[(r["tx_id"], int(r["attempt_no"]))] = r
    prod = [r for r in seen.values() if r["outcome"] != "SANDBOX_SYNTHETIC_PING"]
    lats_by_psp: dict[str, list[float]] = {}
    sla_1500 = 0
    rescued_eur = 0.0
    for r in prod:
        ms = float(r["raw_latency"]) / 1000.0 if int(r["schema_v"]) == 2 else float(r["raw_latency"])
        lats_by_psp.setdefault(r["psp_id"], []).append(ms)
        if ms > 1500.0:
            sla_1500 += 1
        if r["outcome"] == "SOFT_DECLINE_3DS_FALLBACK_OK":
            rescued_eur += float(r["amount_eur"])
    psp_means = {k: round(sum(v) / len(v), 2) for k, v in sorted(lats_by_psp.items())}
    worst_psp = max(psp_means, key=lambda k: psp_means[k])
    or_a = {
        "deduped_prod_event_count": len(prod),
        "sla_breach_1500ms_count": sla_1500,
        "rescued_3ds_fallback_eur": round(rescued_eur, 2),
        "psp_mean_latency_ms": psp_means,
        "degraded_circuit_psp": worst_psp,
        "chaos_sw_cert_code": CHAOS_CERT_CODE,
    }

    # Role B Oracle
    by_sku_cost: dict[str, float] = {k: 0.0 for k in LIVE_RI_RATES}
    waste_usd = 0.0
    gross_od = 0.0
    eff_commit = 0.0
    valid_lines = 0
    for r in _generate_cur_rows():
        if r["account_env"] != "PROD_WORKLOAD" or r["line_item_type"] in ("RIFee", "Credit_Promo_Sandbox"):
            continue
        valid_lines += 1
        sku = r["instance_sku"]
        hrs = float(r["usage_hours"])
        rt = LIVE_RI_RATES[sku]["hourly_commit_usd"] * (1.0 - EDP_DISCOUNT_PCT)
        od = LIVE_RI_RATES[sku]["ondemand_usd"]
        cost = hrs * rt
        by_sku_cost[sku] += cost
        eff_commit += cost
        if r["line_item_type"] == "DiscountedUsage":
            gross_od += hrs * od
        elif r["line_item_type"] == "UnusedCommitmentWaste":
            waste_usd += cost
    or_b = {
        "amortized_line_count": valid_lines,
        "sku_amortized_spend_usd": {k: round(v, 2) for k, v in by_sku_cost.items()},
        "total_effective_ri_spend_usd": round(eff_commit, 2),
        "unused_commitment_waste_usd": round(waste_usd, 2),
        "net_realized_savings_usd": round(gross_od - eff_commit, 2),
        "finops_live_token": FINOPS_LIVE_TOKEN,
    }
    return or_a, or_b


CHAOS_ORACLE, FINOPS_ORACLE = _compute_oracles()

SW_JS = """
let swMode = 'PASSTHROUGH';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('message', e => {
  if (e.data && e.data.setMode) { swMode = e.data.setMode; }
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (u.pathname === '/api/v2/ri_rates' && swMode === 'CHAOS_FAULT_CACHE') {
    e.respondWith(fetch('/api/v2/ri_rates?chaos_mock=1', {credentials: 'include'}));
    return;
  }
});
"""

CHAOS_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>3DS Chaos ServiceWorker Console</title>
<style>body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace} button{padding:8px 14px;background:#dc2626;color:#fff;border:none;cursor:pointer;margin-right:8px} pre{background:#1e293b;padding:14px;border:1px solid #334155}</style></head><body>
<h2>Origin ServiceWorker Fault-Injection Harness (`/sw.js`)</h2>
<p>Active Origin SW Mode: <strong id="md" style="color:#fbbf24">...</strong></p>
<button onclick="setMode('CHAOS_FAULT_CACHE')">Enable CHAOS_FAULT_CACHE on Origin</button>
<button style="background:#059669" onclick="setMode('PASSTHROUGH')">Restore PASSTHROUGH Mode</button>
<button style="background:#2563eb" onclick="runDrill()">Run 3DS Failover Verification Drill</button>
<a href="/finops-ri" style="color:#38bdf8;margin-left:16px">FinOps RI Console -></a>
<pre id="out">Registering /sw.js...</pre>
<script>
async function init() {
  if ('serviceWorker' in navigator) { await navigator.serviceWorker.register('/sw.js'); await navigator.serviceWorker.ready; }
  const r = await fetch('/api/v2/sw_state', {credentials:'include'});
  const j = await r.json();
  document.getElementById('md').textContent = j.mode;
  if (navigator.serviceWorker.controller) navigator.serviceWorker.controller.postMessage({setMode: j.mode});
}
async function setMode(m) {
  if (navigator.serviceWorker.controller) navigator.serviceWorker.controller.postMessage({setMode: m});
  const r = await fetch('/api/v2/set_sw?mode=' + m, {method:'POST', credentials:'include'});
  const j = await r.json();
  document.getElementById('md').textContent = j.mode;
  document.getElementById('out').textContent = JSON.stringify(j, null, 2);
}
async function runDrill() {
  const r = await fetch('/api/v2/run_chaos_drill', {method:'POST', credentials:'include'});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
init();
</script></body></html>"""

FINOPS_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Multi-Cloud FinOps RI Console</title>
<style>body{margin:18px;background:#090d16;color:#f8fafc;font-family:monospace} button{padding:8px 14px;background:#2563eb;color:#fff;border:none;cursor:pointer;margin-right:8px} pre{background:#111827;padding:14px;border:1px solid #334155}</style></head><body>
<h2>Multi-Cloud Commitment Rate & Amortization Console</h2>
<button onclick="loadRates()">Fetch /api/v2/ri_rates</button>
<button style="background:#059669" onclick="commitFinops()">Commit Live FinOps Rate Attestation</button>
<a href="/chaos-sw" style="color:#38bdf8;margin-left:16px"><- Chaos SW Console</a>
<pre id="out">Click [Fetch /api/v2/ri_rates] to inspect commitment rate card...</pre>
<script>
let lastToken = '';
async function loadRates() {
  if ('serviceWorker' in navigator) { await navigator.serviceWorker.register('/sw.js'); }
  const r = await fetch('/api/v2/ri_rates', {credentials:'include'});
  const j = await r.json();
  lastToken = j.finops_token;
  document.getElementById('out').textContent = 'Source: ' + j.source + ' | Token: ' + j.finops_token + '\\nRates: ' + JSON.stringify(j.rates, null, 2);
}
async function commitFinops() {
  const r = await fetch('/api/v2/commit_finops?tok=' + encodeURIComponent(lastToken), {method:'POST', credentials:'include'});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
loadRates();
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — 3DS Checkout Chaos Drill & PSP Latency Audit (`checkout_chaos_engineer`)",
        "",
        "## Objective",
        f"Execute the origin ServiceWorker fault-injection drill on `http://127.0.0.1:{PORTAL_PORT}/chaos-sw` in Chromium, analyze `{b}/workspace/traces/payment_retry_traces.jsonl{b}` per `{b}/workspace/docs/SOP_Chaos_3DS.pdf{b}`, and write `{b}/workspace/chaos_resilience_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — Multi-Cloud RI Amortization & Waste Reconciliation (`cloud_finops_analyst`)",
        "",
        "## Objective",
        f"Query live commitment rates on `http://127.0.0.1:{PORTAL_PORT}/finops-ri` in Chromium (verifying live un-mocked rate provenance and committing the live FinOps attestation), reconcile `{b}/workspace/billing/cur_amortization.sqlite{b}` per `{b}/workspace/docs/SOP_FinOps_RI.pdf{b}`, and write `{b}/workspace/finops_ri_reconciliation.json{b}`.",
    ])
    return {"checkout_chaos_engineer": ta, "cloud_finops_analyst": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["checkout_chaos_engineer"]
    ws_b = workspace_map["cloud_finops_analyst"]
    (ws_a / "traces").mkdir(parents=True, exist_ok=True)
    (ws_a / "docs").mkdir(parents=True, exist_ok=True)
    (ws_b / "billing").mkdir(parents=True, exist_ok=True)
    (ws_b / "docs").mkdir(parents=True, exist_ok=True)

    (ws_a / "traces/payment_retry_traces.jsonl").write_text("\n".join(json.dumps(r) for r in _generate_chaos_traces()) + "\n", encoding="utf-8")
    write_multipage_sop_pdf(ws_a / "docs/SOP_Chaos_3DS.pdf", "SOP-SRE-202: Checkout Fault-Cache Drill & Trace Triage", [
        ("1. ServiceWorker Drill & Trace Hygiene", [
            "1.1 On /chaos-sw, run the 3DS failover verification drill under CHAOS_FAULT_CACHE to obtain chaos_sw_cert_code (restore PASSTHROUGH when finished so production endpoints are not left mocked).",
            "1.2 Deduplicate /workspace/traces/payment_retry_traces.jsonl by (tx_id, attempt_no) keeping the latest event, exclude SANDBOX_SYNTHETIC_PING, normalize latencies to milliseconds, and compute SLA breaches (>1500 ms), rescued 3DS fallback volume EUR, and mean latency per PSP.",
        ]),
        ("2. JSON Schema (/workspace/chaos_resilience_audit.json)", [
            "Keys: deduped_prod_event_count (int), sla_breach_1500ms_count (int), rescued_3ds_fallback_eur (float, 2 dec), psp_mean_latency_ms (dict), degraded_circuit_psp (str), chaos_sw_cert_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "billing/cur_amortization.sqlite")) as conn:
        conn.execute("CREATE TABLE cur_line_items (line_id INTEGER PRIMARY KEY, instance_sku TEXT, account_env TEXT, line_item_type TEXT, usage_hours REAL)")
        for r in _generate_cur_rows():
            conn.execute("INSERT INTO cur_line_items VALUES (?,?,?,?,?)", (r["line_id"], r["instance_sku"], r["account_env"], r["line_item_type"], r["usage_hours"]))
        conn.execute("CREATE TABLE edp_private_ppa (program_id TEXT PRIMARY KEY, applies_to_env TEXT, extra_commit_discount_pct REAL)")
        conn.execute("INSERT INTO edp_private_ppa VALUES ('EDP-2026-ENTERPRISE', 'PROD_WORKLOAD', 0.045)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_FinOps_RI.pdf", "SOP-FIN-202: Accrual-Basis RI & CUD Amortization", [
        ("1. Commitment Accrual Accounting", [
            "1.1 Reconcile PROD_WORKLOAD commitment consumption in /workspace/billing/cur_amortization.sqlite using live production rates on /finops-ri (exclude summary RIFee headers and sandbox promo credits; account for UnusedCommitmentWaste in effective RI spend while comparing DiscountedUsage hours against On-Demand for net_realized_savings_usd, applying any active enterprise PPA agreements in SQLite).",
        ]),
        ("2. JSON Schema (/workspace/finops_ri_reconciliation.json)", [
            "Keys: amortized_line_count (int), sku_amortized_spend_usd (dict), total_effective_ri_spend_usd (float, 2 dec), unused_commitment_waste_usd (float, 2 dec), net_realized_savings_usd (float, 2 dec), finops_live_token (str).",
        ]),
    ])
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    st_p = state_dir / "service_state.json"
    mem = {"mode": "PASSTHROUGH", "sw_flips": 0, "chaos_drill_ok": False, "finops_committed_ok": False}
    write_json(st_p, {"task_id": TASK_ID, **mem})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("sw_sso" in c) and (c["sw_sso"].value == tok)
        def _json(self, code: int, obj: dict[str, Any]) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self) -> None:
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/health":
                self._json(200, {"ok": True}); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self._json(403, {"error": "SSO sealed"}); return
                nxt = (qs.get("next") or ["/chaos-sw"])[0]
                raw = f"<html><body><script>location.href={json.dumps(nxt)};</script></body></html>".encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"sw_sso={tok}; HttpOnly; Path=/; SameSite=Lax"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/sw.js":
                raw = SW_JS.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/javascript"); self.send_header("Service-Worker-Allowed", "/"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            if u.path == "/chaos-sw":
                raw = CHAOS_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/finops-ri":
                raw = FINOPS_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/api/v2/sw_state":
                self._json(200, mem); return
            if u.path == "/api/v2/ri_rates":
                is_mock = (qs.get("chaos_mock") == ["1"]) or (mem["mode"] == "CHAOS_FAULT_CACHE")
                if is_mock:
                    self._json(200, {"source": "SERVICEWORKER_CHAOS_FAULT_CACHE", "rates": MOCK_CHAOS_RATES, "finops_token": STALE_MOCK_TOKEN})
                else:
                    self._json(200, {"source": "LIVE_PRICING_AUTHORITY", "rates": LIVE_RI_RATES, "finops_token": FINOPS_LIVE_TOKEN})
                return
            self._json(404, {"error": "not found"})
        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/v2/set_sw":
                m = (qs.get("mode") or ["PASSTHROUGH"])[0]
                if m in ("PASSTHROUGH", "CHAOS_FAULT_CACHE") and m != mem["mode"]:
                    mem["mode"] = m; mem["sw_flips"] += 1
                    if m == "CHAOS_FAULT_CACHE":
                        mem["finops_committed_ok"] = False
                    write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True, "mode": mem["mode"]}); return
            if u.path == "/api/v2/run_chaos_drill":
                if mem["mode"] == "CHAOS_FAULT_CACHE":
                    mem["chaos_drill_ok"] = True
                    write_json(st_p, {"task_id": TASK_ID, **mem})
                    self._json(200, {"drill_passed": True, "chaos_sw_cert_code": CHAOS_CERT_CODE}); return
                self._json(200, {"drill_passed": False, "error": "Enable CHAOS_FAULT_CACHE on /sw.js first"}); return
            if u.path == "/api/v2/commit_finops":
                tk = (qs.get("tok") or [""])[0]
                mem["finops_committed_ok"] = (mem["mode"] == "PASSTHROUGH") and (tk == FINOPS_LIVE_TOKEN)
                write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"committed": mem["finops_committed_ok"], "mode": mem["mode"]}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del workspace_map
    roles = set(active_roles or META["roles"])
    urls = []
    if "checkout_chaos_engineer" in roles:
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/chaos-sw")
    if "cloud_finops_analyst" in roles:
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/finops-ri")
    launch_chromium_natural(urls)
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ja = read_json_safe(workspace_map["checkout_chaos_engineer"] / "chaos_resilience_audit.json")
    jb = read_json_safe(workspace_map["cloud_finops_analyst"] / "finops_ri_reconciliation.json")

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    pm = ja.get("psp_mean_latency_ms") if isinstance(ja.get("psp_mean_latency_ms"), dict) else {}
    exp_pm = CHAOS_ORACLE["psp_mean_latency_ms"]
    psp_hits = sum(1 for k, v in exp_pm.items() if abs(_f(pm.get(k)) - v) <= 1.5)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.06, "Missing chaos_resilience_audit.json"),
        ("a_dedup_cnt", ja.get("deduped_prod_event_count") == CHAOS_ORACLE["deduped_prod_event_count"], 0.10, "deduped_prod_event_count mismatch"),
        ("a_rescued_eur", abs(_f(ja.get("rescued_3ds_fallback_eur")) - CHAOS_ORACLE["rescued_3ds_fallback_eur"]) <= 1.0, 0.10, "rescued_3ds_fallback_eur mismatch"),
        ("a_worst_psp", ja.get("degraded_circuit_psp") == CHAOS_ORACLE["degraded_circuit_psp"], 0.08, "degraded_circuit_psp != WORLDLINE_FR"),
        ("a_drill_code", ja.get("chaos_sw_cert_code") == CHAOS_CERT_CODE and bool(service_state.get("chaos_drill_ok")), 0.12, "Chaos ServiceWorker drill not verified"),
        ("a_restored_passthrough", bool(ja) and service_state.get("mode") == "PASSTHROUGH", 0.10, "Origin ServiceWorker left in CHAOS_FAULT_CACHE mode!"),
        ("a_psp_coarse", sum(1 for k, v in exp_pm.items() if abs(_f(pm.get(k)) - v) <= 250.0) >= 3, 0.08, "PSP latencies coarse off"),
        ("a_fine_usec_sla", ja.get("sla_breach_1500ms_count") == CHAOS_ORACLE["sla_breach_1500ms_count"], 0.18, "sla_breach_1500ms_count missed schema_v==2 microsecond normalization"),
        ("a_fine_psp_exact", psp_hits == 4, 0.18, "Exact 4/4 PSP mean latencies missed"),
    ]

    sm = jb.get("sku_amortized_spend_usd") if isinstance(jb.get("sku_amortized_spend_usd"), dict) else {}
    exp_sm = FINOPS_ORACLE["sku_amortized_spend_usd"]
    sku_coarse = sum(1 for k, v in exp_sm.items() if abs(_f(sm.get(k)) - v) <= v * 0.07)
    sku_exact = sum(1 for k, v in exp_sm.items() if abs(_f(sm.get(k)) - v) <= 0.5)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.06, "Missing finops_ri_reconciliation.json"),
        ("b_cnt", jb.get("amortized_line_count") == FINOPS_ORACLE["amortized_line_count"], 0.09, "amortized_line_count mismatch (exclude RIFee & sandbox)"),
        ("b_sku_coarse", sku_coarse == 4, 0.09, "SKU spend coarse off (>7% — poisoned by ServiceWorker CHAOS_FAULT_CACHE?)"),
        ("b_tot_coarse", abs(_f(jb.get("total_effective_ri_spend_usd")) - FINOPS_ORACLE["total_effective_ri_spend_usd"]) <= FINOPS_ORACLE["total_effective_ri_spend_usd"] * 0.06, 0.09, "total_effective_ri_spend_usd coarse off"),
        ("b_waste_coarse", abs(_f(jb.get("unused_commitment_waste_usd")) - FINOPS_ORACLE["unused_commitment_waste_usd"]) <= 45.0, 0.08, "unused_commitment_waste_usd off"),
        ("b_tok", jb.get("finops_live_token") == FINOPS_LIVE_TOKEN and jb.get("finops_live_token") != STALE_MOCK_TOKEN, 0.12, "Poisoned by ServiceWorker mock token!"),
        ("b_live_commit", bool(service_state.get("finops_committed_ok")), 0.11, "Live FinOps PASSTHROUGH attestation invalidated by ServiceWorker fault mode"),
        ("b_fine_edp_tot_exact", sku_exact == 4 and abs(_f(jb.get("total_effective_ri_spend_usd")) - FINOPS_ORACLE["total_effective_ri_spend_usd"]) <= 1.0, 0.18, "Exact RI spend missed edp_private_ppa 4.5% discount"),
        ("b_fine_edp_savings_exact", abs(_f(jb.get("net_realized_savings_usd")) - FINOPS_ORACLE["net_realized_savings_usd"]) <= 1.5, 0.18, "Exact net_realized_savings_usd missed"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    st_f = Path("/opt/nf_state/service_state.json")
    if role == "checkout_chaos_engineer":
        write_json(ws / "chaos_resilience_audit.json", CHAOS_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf202_st"):
                st = read_json_safe(st_f); st["chaos_drill_ok"] = True; st["mode"] = "PASSTHROUGH"; write_json(st_f, st)
    else:
        write_json(ws / "finops_ri_reconciliation.json", FINOPS_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf202_st"):
                st = read_json_safe(st_f); st["mode"] = "PASSTHROUGH"; st["finops_committed_ok"] = True; write_json(st_f, st)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    solve_role("checkout_chaos_engineer", workspace_map, port)
    solve_role("cloud_finops_analyst", workspace_map, port)
    # Chaos SW left in CHAOS_FAULT_CACHE poisons FinOps rates (+42%) and invalidates finops_committed_ok
    st_p = state_dir / "service_state.json"
    st = read_json_safe(st_p)
    st["mode"] = "CHAOS_FAULT_CACHE"; st["finops_committed_ok"] = False; st["sw_flips"] = 4
    write_json(st_p, st)
    jb = read_json_safe(workspace_map["cloud_finops_analyst"] / "finops_ri_reconciliation.json")
    jb["finops_live_token"] = STALE_MOCK_TOKEN
    jb["total_effective_ri_spend_usd"] = round(jb["total_effective_ri_spend_usd"] * 1.42, 2)
    write_json(workspace_map["cloud_finops_analyst"] / "finops_ri_reconciliation.json", jb)

"""NF2-04: HTML5 SharedWorker Singleton Calorific-Basis Drift — LNG Charter Boil-Off TCE vs. FuelEU Maritime GHG Compliance."""
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

TASK_ID = "NF2-04"
PORTAL_PORT = 19604

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "HTML5 `SharedWorker` Singleton Calorific-Basis Contention: LNG Boil-Off Voyage TCE vs. FuelEU Maritime Well-to-Wake GHG",
    "domain": "Maritime LNG Chartering Economics & EU-ETS / FuelEU Maritime Decarbonization (Chromium SharedWorker + SQLite)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("lng_voyage_economist", "fueleu_ets_officer"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

CHARTER_HHV_TOKEN = make_canary_code("LNG-HHV", "custody-transfer-mmbtu")
FUELEU_LHV_TOKEN = make_canary_code("FUELEU-LHV", "wtw-ghg-2026")

# LNG Custody Transfer uses HHV (54.40 MJ/kg = 51.561 MMBtu/t); FuelEU Maritime Reg (EU) 2023/1805 mandates LHV (49.10 MJ/kg)!
HHV_MMBTU_PER_TONNE = 51.561
LHV_MJ_PER_KG = 49.10
MGO_LHV_MJ_PER_KG = 42.70
BIO_LNG_LHV_MJ_PER_KG = 49.10


def _generate_voyage_legs() -> list[dict[str, Any]]:
    legs = [
        ("LEG-01-USGC-PANAMA", "LADEN", 4.5, 0.085, 420000.0),
        ("LEG-02-PANAMA-TOKYO", "LADEN", 19.0, 0.085, 0.0),
        ("LEG-03-TOKYO-DISCH", "PORT_IDLE", 2.0, 0.045, 95000.0),
        ("LEG-04-TOKYO-SUEZ-BAL", "BALLAST", 16.5, 0.060, 310000.0),
    ]
    rows = []
    for i in range(1, 321):
        lid, mode, _d, bor_pct, port_usd = legs[(i - 1) % 4]
        # 80 daily noon-report slices per leg group
        slice_days = 0.25
        status = "VERIFIED_NOON" if (i % 23 != 0) else "SENSOR_RECALIB_SKIP"
        rows.append({
            "report_id": i, "leg_code": lid, "ballast_mode": mode, "slice_days": slice_days,
            "cargo_heel_tonnes": 76500.0 if mode != "BALLAST" else 3800.0,
            "daily_bor_pct": bor_pct, "port_canal_fee_slice_usd": round(port_usd / 76.0, 2) if status == "VERIFIED_NOON" else 0.0,
            "status": status,
        })
    return rows


def _generate_bdn_rows() -> list[dict[str, Any]]:
    fuels = [
        ("LNG_OTTO_DF", 49.10, 75.30),    # WtW gCO2eq/MJ including 3.1% methane slip!
        ("VLSFO_05S",   40.50, 91.60),
        ("MGO_01S",     42.70, 90.80),
        ("BIO_LNG_ISCC", 49.10, 28.40),
    ]
    rows = []
    for i in range(1, 361):
        fname, _lhv, _wtw = fuels[(i * 3) % 4]
        scope = "EU_INTRA" if (i % 3 == 0) else ("EU_HALF_EXTRA" if i % 3 == 1 else "NON_EU_EXEMPT")
        tonnes = round(18.5 + (i % 11) * 2.4, 2)
        bdn_state = "FINAL_BDN" if (i % 29 != 0) else "DRAFT_VOID"
        rows.append({"bdn_id": i, "fuel_grade": fname, "voyage_scope": scope, "mass_tonnes": tonnes, "bdn_state": bdn_state})
    return rows


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    # Role A: LNG Voyage Boil-Off & Net TCE ($/day) under HHV custody-transfer basis
    # Reliquefaction plant recovers 68% of boil-off gas on LADEN legs (secondary table reliquefaction_spec in SQLite)!
    vrows = [r for r in _generate_voyage_legs() if r["status"] == "VERIFIED_NOON"]
    tot_days = sum(r["slice_days"] for r in vrows)
    unrecov_bog_t = 0.0
    port_canal_usd = 0.0
    for r in vrows:
        raw_bog = r["cargo_heel_tonnes"] * (r["daily_bor_pct"] / 100.0) * r["slice_days"]
        recov_frac = 0.68 if r["ballast_mode"] == "LADEN" else 0.0
        unrecov_bog_t += raw_bog * (1.0 - recov_frac)
        port_canal_usd += r["port_canal_fee_slice_usd"]
    delivered_t = 76500.0 - unrecov_bog_t
    delivered_mmbtu = delivered_t * HHV_MMBTU_PER_TONNE
    gross_freight_usd = delivered_mmbtu * 2.15  # $2.15 / MMBtu HHV charter freight rate
    net_tce_per_day = (gross_freight_usd - port_canal_usd) / tot_days
    or_a = {
        "verified_noon_count": len(vrows),
        "unrecovered_bog_tonnes": round(unrecov_bog_t, 3),
        "delivered_energy_mmbtu_hhv": round(delivered_mmbtu, 2),
        "net_tce_usd_per_day": round(net_tce_per_day, 2),
        "charter_hhv_token": CHARTER_HHV_TOKEN,
    }

    # Role B: FuelEU Maritime WtW GHG Intensity (Reg 2023/1805: 100% EU_INTRA + 50% EU_HALF_EXTRA, 0% NON_EU_EXEMPT; LHV basis!)
    # Secondary SQLite table shore_power_ops_credit grants 14,500,000 MJ zero-GHG cold-ironing energy in EU ports!
    wtw_map = {"LNG_OTTO_DF": (49.10, 75.30), "VLSFO_05S": (40.50, 91.60), "MGO_01S": (42.70, 90.80), "BIO_LNG_ISCC": (49.10, 28.40)}
    brows = [r for r in _generate_bdn_rows() if r["bdn_state"] == "FINAL_BDN" and r["voyage_scope"] != "NON_EU_EXEMPT"]
    tot_mj = 14_500_000.0  # Shore power OPS zero-emission MJ in denominator
    tot_ghg_g = 0.0
    for r in brows:
        mult = 1.0 if r["voyage_scope"] == "EU_INTRA" else 0.5
        lhv, wtw = wtw_map[r["fuel_grade"]]
        mj = (r["mass_tonnes"] * 1000.0) * lhv * mult
        tot_mj += mj
        tot_ghg_g += mj * wtw
    ghg_int = tot_ghg_g / tot_mj
    target_2026 = 89.34  # 2% cut from 91.16 gCO2eq/MJ reference
    surplus_tonnes_co2eq = ((target_2026 - ghg_int) * tot_mj) / 1_000_000.0
    or_b = {
        "in_scope_bdn_count": len(brows),
        "fueleu_energy_scope_gj": round(tot_mj / 1000.0, 2),
        "wtw_ghg_intensity_gco2e_mj": round(ghg_int, 4),
        "compliance_surplus_tco2eq": round(surplus_tonnes_co2eq, 2),
        "fueleu_lhv_token": FUELEU_LHV_TOKEN,
    }
    return or_a, or_b


CHARTER_ORACLE, FUELEU_ORACLE = _compute_oracles()

SHARED_WORKER_JS = """
let engineState = { basis: 'HHV_CUSTODY_TRANSFER', flips: 0 };
const ports = [];
onconnect = function(e) {
  const port = e.ports[0];
  ports.push(port);
  port.onmessage = function(ev) {
    const d = ev.data || {};
    if (d.setBasis) {
      engineState.basis = d.setBasis;
      engineState.flips += 1;
      for (const p of ports) { p.postMessage({ type: 'BASIS_MUTATED', state: engineState }); }
    } else if (d.getState) {
      port.postMessage({ type: 'STATE', state: engineState });
    }
  };
  port.start();
  port.postMessage({ type: 'STATE', state: engineState });
};
"""

DESK_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Maritime SharedWorker Calorific Engine</title>
<style>body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace} button{padding:8px 14px;background:#2563eb;color:#fff;border:none;cursor:pointer;margin-right:8px} pre{background:#1e293b;padding:14px;border:1px solid #334155}</style></head><body>
<h2>Maritime Desk Engine — Live HTML5 `SharedWorker('/maritime-worker.js')`</h2>
<p>SharedWorker Singleton Basis: <strong id="bs" style="color:#38bdf8">...</strong></p>
<button onclick="setB('HHV_CUSTODY_TRANSFER')">Set HHV_CUSTODY_TRANSFER (Chartering)</button>
<button style="background:#059669" onclick="setB('LHV_FUELEU_2023_1805')">Set LHV_FUELEU_2023_1805 (Compliance)</button>
<button style="background:#7c3aed" onclick="queryFactors()">Query Active Calorific Factors & Token</button>
<a href="/charter-voyage" style="color:#93c5fd;margin-left:12px">Charter Desk</a>
<a href="/fueleu-compliance" style="color:#93c5fd;margin-left:12px">FuelEU Desk</a>
<pre id="out">Connecting to SharedWorker...</pre>
<script>
const sw = new SharedWorker('/maritime-worker.js', 'maritime_calorific_singleton');
let curBasis = 'HHV_CUSTODY_TRANSFER';
sw.port.onmessage = async (ev) => {
  if (ev.data && ev.data.state) {
    curBasis = ev.data.state.basis;
    document.getElementById('bs').textContent = curBasis + ' (worker flips=' + ev.data.state.flips + ')';
    if (ev.data.type === 'BASIS_MUTATED') {
      await fetch('/api/worker_sync?basis=' + curBasis, {method:'POST', credentials:'include'});
    }
  }
};
sw.port.start();
function setB(b) { sw.port.postMessage({ setBasis: b }); }
async function queryFactors() {
  const r = await fetch('/api/factors?worker_basis=' + encodeURIComponent(curBasis), {credentials:'include'});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — LNG Voyage Boil-Off & Custody-Transfer TCE Valuation (`lng_voyage_economist`)",
        "",
        "## Objective",
        f"Query HHV custody-transfer conversion constants on `http://127.0.0.1:{PORTAL_PORT}/charter-voyage` in Chromium, analyze `{b}/workspace/charter/voyage_boiloff_legs.sqlite{b}` per `{b}/workspace/docs/SOP_LNG_Charter.pdf{b}`, and write `{b}/workspace/lng_charter_tce.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — FuelEU Maritime Well-to-Wake GHG Compliance Audit (`fueleu_ets_officer`)",
        "",
        "## Objective",
        f"Query LHV FuelEU emission factors on `http://127.0.0.1:{PORTAL_PORT}/fueleu-compliance` in Chromium, reconcile `{b}/workspace/compliance/bunker_bdn_manifest.sqlite{b}` per `{b}/workspace/docs/SOP_FuelEU_1805.pdf{b}`, and write `{b}/workspace/fueleu_ghg_compliance.json{b}`.",
    ])
    return {"lng_voyage_economist": ta, "fueleu_ets_officer": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["lng_voyage_economist"]
    ws_b = workspace_map["fueleu_ets_officer"]
    (ws_a / "charter").mkdir(parents=True, exist_ok=True)
    (ws_a / "docs").mkdir(parents=True, exist_ok=True)
    (ws_b / "compliance").mkdir(parents=True, exist_ok=True)
    (ws_b / "docs").mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(ws_a / "charter/voyage_boiloff_legs.sqlite")) as conn:
        conn.execute("CREATE TABLE noon_reports (report_id INTEGER PRIMARY KEY, leg_code TEXT, ballast_mode TEXT, slice_days REAL, cargo_heel_tonnes REAL, daily_bor_pct REAL, port_canal_fee_slice_usd REAL, status TEXT)")
        for r in _generate_voyage_legs():
            conn.execute("INSERT INTO noon_reports VALUES (?,?,?,?,?,?,?,?)", (r["report_id"], r["leg_code"], r["ballast_mode"], r["slice_days"], r["cargo_heel_tonnes"], r["daily_bor_pct"], r["port_canal_fee_slice_usd"], r["status"]))
        conn.execute("CREATE TABLE subcooler_reliquefaction_spec (ballast_mode TEXT PRIMARY KEY, bog_recovery_fraction REAL)")
        conn.execute("INSERT INTO subcooler_reliquefaction_spec VALUES ('LADEN', 0.68), ('PORT_IDLE', 0.0), ('BALLAST', 0.0)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_LNG_Charter.pdf", "SOP-LNG-404: Custody-Transfer HHV Valuation & TCE", [
        ("1. Boil-Off Gas & Time-Charter Equivalent", [
            "1.1 Filter noon_reports in /workspace/charter/voyage_boiloff_legs.sqlite to VERIFIED_NOON slices, compute net unrecovered boil-off tonnes subtracted from initial 76,500.0 t loaded cargo (accounting for onboard reliquefaction specs in the database), convert delivered mass to MMBtu using HHV_CUSTODY_TRANSFER on /charter-voyage at $2.15/MMBtu freight, and divide net voyage revenue (freight minus port/canal fees) by total verified voyage days.",
        ]),
        ("2. JSON Schema (/workspace/lng_charter_tce.json)", [
            "Keys: verified_noon_count (int), unrecovered_bog_tonnes (float, 3 dec), delivered_energy_mmbtu_hhv (float, 2 dec), net_tce_usd_per_day (float, 2 dec), charter_hhv_token (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "compliance/bunker_bdn_manifest.sqlite")) as conn:
        conn.execute("CREATE TABLE bunker_deliveries (bdn_id INTEGER PRIMARY KEY, fuel_grade TEXT, voyage_scope TEXT, mass_tonnes REAL, bdn_state TEXT)")
        for r in _generate_bdn_rows():
            conn.execute("INSERT INTO bunker_deliveries VALUES (?,?,?,?,?)", (r["bdn_id"], r["fuel_grade"], r["voyage_scope"], r["mass_tonnes"], r["bdn_state"]))
        conn.execute("CREATE TABLE shore_power_ops_credit (port_call_group TEXT PRIMARY KEY, zero_ghg_ops_energy_mj REAL)")
        conn.execute("INSERT INTO shore_power_ops_credit VALUES ('EU_BERTH_COLD_IRONING_2026', 14500000.0)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_FuelEU_1805.pdf", "SOP-MAR-404: FuelEU Maritime Reg (EU) 2023/1805 GHG Intensity", [
        ("1. Geographical Scope & WtW GHG Intensity", [
            "1.1 Retain FINAL_BDN rows in /workspace/compliance/bunker_bdn_manifest.sqlite within EU scope (100% EU_INTRA, 50% EU_HALF_EXTRA, exclude NON_EU_EXEMPT), convert fuel mass to MJ using LHV_FUELEU_2023_1805 factors on /fueleu-compliance (including any certified zero-GHG shore-power OPS energy in SQLite in the total MJ denominator), and compute wtw_ghg_intensity_gco2e_mj and compliance_surplus_tco2eq vs the 89.34 gCO2eq/MJ 2026 target.",
        ]),
        ("2. JSON Schema (/workspace/fueleu_ghg_compliance.json)", [
            "Keys: in_scope_bdn_count (int), fueleu_energy_scope_gj (float, 2 dec), wtw_ghg_intensity_gco2e_mj (float, 4 dec), compliance_surplus_tco2eq (float, 2 dec), fueleu_lhv_token (str).",
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
    mem = {"basis": "HHV_CUSTODY_TRANSFER", "worker_flips": 0}
    write_json(st_p, {"task_id": TASK_ID, **mem})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("mar_sso" in c) and (c["mar_sso"].value == tok)
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
                nxt = (qs.get("next") or ["/charter-voyage"])[0]
                raw = f"<html><body><script>location.href={json.dumps(nxt)};</script></body></html>".encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"mar_sso={tok}; HttpOnly; Path=/; SameSite=Lax"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/maritime-worker.js":
                raw = SHARED_WORKER_JS.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/javascript"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            if u.path in ("/charter-voyage", "/fueleu-compliance"):
                raw = DESK_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/api/factors":
                wb = (qs.get("worker_basis") or [mem["basis"]])[0]
                if wb == "HHV_CUSTODY_TRANSFER":
                    self._json(200, {"basis": wb, "lng_mmbtu_per_tonne": HHV_MMBTU_PER_TONNE, "freight_usd_per_mmbtu": 2.15, "token": CHARTER_HHV_TOKEN})
                else:
                    self._json(200, {
                        "basis": wb, "target_2026_gco2e_mj": 89.34,
                        "fuels_lhv_wtw": {
                            "LNG_OTTO_DF": {"lhv_mj_kg": 49.10, "wtw_gco2e_mj": 75.30},
                            "VLSFO_05S": {"lhv_mj_kg": 40.50, "wtw_gco2e_mj": 91.60},
                            "MGO_01S": {"lhv_mj_kg": 42.70, "wtw_gco2e_mj": 90.80},
                            "BIO_LNG_ISCC": {"lhv_mj_kg": 49.10, "wtw_gco2e_mj": 28.40},
                        },
                        "token": FUELEU_LHV_TOKEN,
                    })
                return
            self._json(404, {"error": "not found"})
        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/worker_sync":
                nb = (qs.get("basis") or [mem["basis"]])[0]
                if nb != mem["basis"]:
                    mem["basis"] = nb; mem["worker_flips"] += 1
                    write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del workspace_map
    roles = set(active_roles or META["roles"])
    urls = []
    if "lng_voyage_economist" in roles:
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/charter-voyage")
    if "fueleu_ets_officer" in roles:
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/fueleu-compliance")
    launch_chromium_natural(urls)
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ja = read_json_safe(workspace_map["lng_voyage_economist"] / "lng_charter_tce.json")
    jb = read_json_safe(workspace_map["fueleu_ets_officer"] / "fueleu_ghg_compliance.json")

    def _f(v: Any, d: float = -99999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing lng_charter_tce.json"),
        ("a_cnt", ja.get("verified_noon_count") == CHARTER_ORACLE["verified_noon_count"], 0.12, "verified_noon_count mismatch"),
        ("a_mmbtu_coarse", abs(_f(ja.get("delivered_energy_mmbtu_hhv")) - CHARTER_ORACLE["delivered_energy_mmbtu_hhv"]) <= 85000.0, 0.14, "delivered_energy_mmbtu_hhv coarse off (used LHV instead of HHV?)"),
        ("a_tce_coarse", abs(_f(ja.get("net_tce_usd_per_day")) - CHARTER_ORACLE["net_tce_usd_per_day"]) <= 4500.0, 0.14, "net_tce_usd_per_day coarse off"),
        ("a_tok", ja.get("charter_hhv_token") == CHARTER_HHV_TOKEN and ja.get("charter_hhv_token") != FUELEU_LHV_TOKEN, 0.16, "Wrong charter_hhv_token (SharedWorker switched to LHV?)"),
        ("a_fine_reliquefaction_bog", abs(_f(ja.get("unrecovered_bog_tonnes")) - CHARTER_ORACLE["unrecovered_bog_tonnes"]) <= 0.15, 0.18, "Missed subcooler_reliquefaction_spec 68% laden recovery in SQLite"),
        ("a_fine_tce_exact", abs(_f(ja.get("net_tce_usd_per_day")) - CHARTER_ORACLE["net_tce_usd_per_day"]) <= 3.0, 0.18, "Exact net_tce_usd_per_day missed"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing fueleu_ghg_compliance.json"),
        ("b_cnt", jb.get("in_scope_bdn_count") == FUELEU_ORACLE["in_scope_bdn_count"], 0.12, "in_scope_bdn_count mismatch (exclude NON_EU_EXEMPT & DRAFT_VOID)"),
        ("b_gj_coarse", abs(_f(jb.get("fueleu_energy_scope_gj")) - FUELEU_ORACLE["fueleu_energy_scope_gj"]) <= 18000.0, 0.14, "fueleu_energy_scope_gj coarse off"),
        ("b_ghg_coarse", abs(_f(jb.get("wtw_ghg_intensity_gco2e_mj")) - FUELEU_ORACLE["wtw_ghg_intensity_gco2e_mj"]) <= 4.5, 0.14, "wtw_ghg_intensity_gco2e_mj coarse off"),
        ("b_tok", jb.get("fueleu_lhv_token") == FUELEU_LHV_TOKEN and jb.get("fueleu_lhv_token") != CHARTER_HHV_TOKEN, 0.16, "Wrong fueleu_lhv_token (SharedWorker switched to HHV?)"),
        ("b_fine_shore_ops_gj", abs(_f(jb.get("fueleu_energy_scope_gj")) - FUELEU_ORACLE["fueleu_energy_scope_gj"]) <= 2.0, 0.18, "Missed shore_power_ops_credit 14.5M MJ cold-ironing energy in SQLite"),
        ("b_fine_ghg_surplus_exact", abs(_f(jb.get("wtw_ghg_intensity_gco2e_mj")) - FUELEU_ORACLE["wtw_ghg_intensity_gco2e_mj"]) <= 0.005 and abs(_f(jb.get("compliance_surplus_tco2eq")) - FUELEU_ORACLE["compliance_surplus_tco2eq"]) <= 1.0, 0.18, "Exact WtW GHG intensity & tCO2eq surplus missed"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    if role == "lng_voyage_economist":
        write_json(ws / "lng_charter_tce.json", CHARTER_ORACLE)
    else:
        write_json(ws / "fueleu_ghg_compliance.json", FUELEU_ORACLE)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    solve_role("lng_voyage_economist", workspace_map, port)
    solve_role("fueleu_ets_officer", workspace_map, port)
    ja = read_json_safe(workspace_map["lng_voyage_economist"] / "lng_charter_tce.json")
    ja["charter_hhv_token"] = FUELEU_LHV_TOKEN
    ja["delivered_energy_mmbtu_hhv"] = round(ja["delivered_energy_mmbtu_hhv"] * 0.902, 2)
    write_json(workspace_map["lng_voyage_economist"] / "lng_charter_tce.json", ja)
    st = read_json_safe(state_dir / "service_state.json")
    st["worker_flips"] = 5
    write_json(state_dir / "service_state.json", st)

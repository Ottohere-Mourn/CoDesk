"""NF2-01: X11 FR-AZERTY Digit-Shift Inversion — Swiss Horology INPI Patent Writer vs. COSC Vibrometry Calc."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
import subprocess
import tempfile
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    extract_pdf_text,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    read_odt_plain_text,
    reload_uno_pipe_documents,
    render_scanned_exhibit_png,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
    write_simple_odt,
)

TASK_ID = "NF2-01"
PORTAL_PORT = 19601

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "X11 FR-AZERTY Top-Row Digit Inversion: Geneva Horology Patent Claims (Writer) vs. COSC Vibrometry Isochronism (Calc)",
    "domain": "Swiss/French Horological Patent Filing (LibreOffice Writer) & COSC Chronometer Metrology (LibreOffice Calc + SQLite)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("swiss_patent_paralegal", "chronometer_metrology_analyst"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

INPI_ATTEST_CODE = make_canary_code("INPI-FR", "echappement-geneve-2026")
COSC_TARIFF_CODE = make_canary_code("COSC-ISO", "niivarox-3159-cal")

PATENT_SPEC = {
    "application_no": "CH-719842-B1",
    "inpi_priority": "FR-2509418",
    "ipc_class": "G04B 15/08",
    "applicant": "Manufacture Horlogère du Léman SA",
    "claim_count": 16,
    "independent_claims": 3,
    "french_title": "«\u00a0Échappement à détente coaxiale à œillère céramique çà-et-là\u00a0»",
    # Base filing 320 CHF + 180 CHF search + (16 - 10) * 65 CHF excess claim fee + 145 CHF bilingual publication surcharge (from XML)
    "total_filing_fee_chf": 320.0 + 180.0 + 6 * 65.0 + 145.0,  # 1035.0
}

POSITIONS = ("CH", "FH", "6H", "9H", "3H")
BAROMETRIC_HPA_COEFF = -0.0085  # s/day per hPa above 1013.25 hPa (in secondary SQLite table)


def _generate_vibrometry_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_rates = {"CH": 2.15, "FH": 1.65, "6H": -0.85, "9H": 0.45, "3H": 1.10, "T_8C": 0.25, "T_38C": 1.87}
    all_conds = list(POSITIONS) + ["T_8C", "T_38C"]
    for idx in range(1, 421):
        cond = all_conds[(idx - 1) % len(all_conds)]
        day_slot = 1 + ((idx - 1) // 7)
        drift = 0.28 * math.sin(idx * 0.37)
        chamber_hpa = 965.0 if cond in ("6H", "9H") else 1013.25
        # Measured raw daily rate includes uncompensated chamber pressure offset; analyst must subtract (hPa - 1013.25)*coeff!
        true_std_rate = base_rates[cond] + drift
        meas_rate = round(true_std_rate + (chamber_hpa - 1013.25) * BAROMETRIC_HPA_COEFF, 4)
        status = "VALID_LASER_LOCK"
        if idx % 29 == 0:
            status = "ACOUSTIC_DROPOUT"
        elif idx % 37 == 0:
            status = "WARMUP_TRANSIENT"
        # Inject superseded seq=1 rows
        if idx in (14, 49, 98, 161, 245):
            rows.append({
                "row_id": len(rows) + 1, "sample_slot": idx, "retest_seq": 1, "condition_code": cond,
                "day_index": day_slot, "chamber_hpa": chamber_hpa, "beat_rate_s_per_day": round(meas_rate + 4.8, 4),
                "amplitude_deg": 241.0, "status": "VALID_LASER_LOCK",
            })
        rows.append({
            "row_id": len(rows) + 1, "sample_slot": idx, "retest_seq": 2 if idx in (14, 49, 98, 161, 245) else 1,
            "condition_code": cond, "day_index": day_slot, "chamber_hpa": chamber_hpa,
            "beat_rate_s_per_day": meas_rate,
            "amplitude_deg": round(292.0 - (14.0 if cond in ("6H", "9H", "3H") else 0.0) + (idx % 7) * 1.1, 2),
            "status": status,
        })
    return rows


def _compute_cosc_oracle() -> dict[str, Any]:
    rows = _generate_vibrometry_rows()
    dedup: dict[int, dict[str, Any]] = {}
    for r in rows:
        sl = int(r["sample_slot"])
        if sl not in dedup or int(r["retest_seq"]) >= int(dedup[sl]["retest_seq"]):
            dedup[sl] = r
    by_cond: dict[str, list[float]] = {c: [] for c in list(POSITIONS) + ["T_8C", "T_38C"]}
    amps_horiz: list[float] = []
    valid_cnt = 0
    for r in dedup.values():
        if r["status"] != "VALID_LASER_LOCK":
            continue
        valid_cnt += 1
        # Compensate chamber barometric pressure back to standard 1013.25 hPa
        std_r = float(r["beat_rate_s_per_day"]) - (float(r["chamber_hpa"]) - 1013.25) * BAROMETRIC_HPA_COEFF
        by_cond[r["condition_code"]].append(std_r)
        if r["condition_code"] in ("CH", "FH"):
            amps_horiz.append(float(r["amplitude_deg"]))
    pos_means = {p: round(sum(by_cond[p]) / len(by_cond[p]), 4) for p in POSITIONS}
    mean_daily_rate_m = round(sum(pos_means.values()) / 5.0, 4)
    max_pos_spread_p = round(max(pos_means.values()) - min(pos_means.values()), 4)
    t8 = sum(by_cond["T_8C"]) / len(by_cond["T_8C"])
    t38 = sum(by_cond["T_38C"]) / len(by_cond["T_38C"])
    thermal_coeff_c = round((t38 - t8) / 30.0, 5)
    cosc_pass = (-4.0 <= mean_daily_rate_m <= 6.0) and (max_pos_spread_p <= 10.0) and (abs(thermal_coeff_c) <= 0.60)
    return {
        "valid_sample_count": valid_cnt,
        "position_mean_rates_spd": pos_means,
        "mean_daily_rate_m_spd": mean_daily_rate_m,
        "max_positional_spread_p_spd": max_pos_spread_p,
        "thermal_coeff_c_spd_per_k": thermal_coeff_c,
        "mean_horizontal_amplitude_deg": round(sum(amps_horiz) / len(amps_horiz), 2),
        "cosc_iso3159_certified": cosc_pass,
        "cosc_tariff_code": COSC_TARIFF_CODE,
    }


COSC_ORACLE = _compute_cosc_oracle()

PORTAL_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>INPI / COSC Geneva Bilingual Workstation</title>
<style>
  body{margin:0;background:#0f172a;color:#f8fafc;font-family:sans-serif}
  .nav{background:#1e293b;padding:12px 18px;display:flex;gap:12px;align-items:center;border-bottom:1px solid #334155}
  button{padding:8px 14px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-weight:600}
  input{width:540px;padding:8px;background:#090d16;color:#f8fafc;border:1px solid #475569;font-size:14px}
  .card{margin:18px;padding:18px;background:#1e293b;border-radius:6px;border:1px solid #334155}
</style></head><body>
<div class="nav">
  <strong>Geneva Horology Portal</strong>
  <span>X11 Layout: <strong id="lyt" style="color:#38bdf8">...</strong></span>
  <button onclick="setKbd('fr')">Activate FR-AZERTY (INPI Legal Mode)</button>
  <button onclick="setKbd('us')">Activate US-QWERTY (COSC Numeric Mode)</button>
  <a href="/inpi-claims" style="color:#93c5fd">INPI Filing</a>
  <a href="/cosc-bench" style="color:#93c5fd">COSC ISO-3159 Reference</a>
</div>
<div id="body" class="card"></div>
<script>
const isCosc = location.pathname.includes('cosc');
async function refresh() {
  const r = await fetch('/api/state', {credentials:'include'});
  const j = await r.json();
  document.getElementById('lyt').textContent = j.xkb.toUpperCase();
  if (!isCosc) {
    document.getElementById('body').innerHTML = `
      <h3>INPI / IPI French Patent Attestation Terminal</h3>
      <p>With live X11 keyboard layout set to <code>FR (AZERTY)</code>, type the exact French phrase <code>échappement çà</code> below and submit to mint the statutory attestation stamp:</p>
      <input id="phr" placeholder="Type under FR-AZERTY..."/><br><br>
      <button onclick="verifyFr()">Verify FR-AZERTY & Mint Stamp</button>
      <pre id="out">${j.fr_verified ? ('ATTESTATION_CODE: ' + j.attest_code) : 'Awaiting FR-AZERTY verification...'}</pre>`;
  } else {
    document.getElementById('body').innerHTML = `
      <h3>COSC NIHS 95-11 / ISO 3159 Official Limits</h3>
      <p>Mean daily rate M across 5 positions (CH, FH, 6H, 9H, 3H): <code>-4.0 &lt;= M &lt;= +6.0 s/day</code></p>
      <p>Max positional spread P = max(M_pos) - min(M_pos): <code>&lt;= 10.0 s/day</code> | Thermal coeff C = (M_38C - M_8C)/30: <code>|C| &lt;= 0.60 s/(day·K)</code></p>
      <p>COSC Calibration Tariff Code: <strong style="color:#4ade80">${j.cosc_code}</strong></p>`;
  }
}
async function setKbd(k) {
  await fetch('/api/set_xkb?layout=' + k, {method:'POST', credentials:'include'});
  await refresh();
}
async function verifyFr() {
  const v = document.getElementById('phr').value;
  const r = await fetch('/api/verify_fr?val=' + encodeURIComponent(v), {method:'POST', credentials:'include'});
  const j = await r.json();
  document.getElementById('out').textContent = JSON.stringify(j, null, 2);
}
refresh();
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Swiss/French Patent Claims & IPI Annuity Schedule (`swiss_patent_paralegal`)",
        "",
        "## Objective",
        f"Finalize the bilingual patent claim dossier in `{b}/workspace/Revendications_Echappement_INPI.odt{b}` (open in LibreOffice Writer), verify FR-AZERTY statutory entry on `http://127.0.0.1:{PORTAL_PORT}/inpi-claims`, consult `{b}/workspace/specs/SOP_INPI_Filing.pdf{b}` and `{b}/workspace/specs/ipi_extract_scan.png{b}`, export `{b}/workspace/Revendications_Echappement_INPI.pdf{b}`, and write `{b}/workspace/patent_filing_summary.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — COSC ISO-3159 Chronometer Vibrometry Audit (`chronometer_metrology_analyst`)",
        "",
        "## Objective",
        f"Reconcile the 420-slot laser-vibrometry dataset in `{b}/workspace/ledgers/vibrometry_420beats.sqlite{b}` using `http://127.0.0.1:{PORTAL_PORT}/cosc-bench` and `{b}/workspace/specs/SOP_COSC_3159.pdf{b}`, populate `{b}/workspace/COSC_Isochronism_Audit.xlsx{b}` (open in LibreOffice Calc) preserving live summary formulas, and write `{b}/workspace/cosc_metrology_audit.json{b}`.",
    ])
    return {"swiss_patent_paralegal": ta, "chronometer_metrology_analyst": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["swiss_patent_paralegal"]
    ws_b = workspace_map["chronometer_metrology_analyst"]
    (ws_a / "specs").mkdir(parents=True, exist_ok=True)
    (ws_b / "specs").mkdir(parents=True, exist_ok=True)
    (ws_b / "ledgers").mkdir(parents=True, exist_ok=True)

    render_scanned_exhibit_png(
        ws_a / "specs/ipi_extract_scan.png",
        "INSTITUT FEDERAL DE LA PROPRIETE INTELLECTUELLE — DOSSIER HORLOGER",
        [
            f"Swiss Application No:     {PATENT_SPEC['application_no']}",
            f"INPI French Priority:     {PATENT_SPEC['inpi_priority']}",
            f"IPC Classification:       {PATENT_SPEC['ipc_class']}",
            f"Applicant Entity:         {PATENT_SPEC['applicant']}",
            f"Total Claims / Indep.:    {PATENT_SPEC['claim_count']} total claims ({PATENT_SPEC['independent_claims']} independent)",
            "Statutory French Title (use French non-breaking space U+00A0 inside « ... »):",
            "  « Échappement à détente coaxiale à œillère céramique çà-et-là »",
            "Fee Base: 320 CHF filing + 180 CHF search + 65 CHF per claim above 10 claims",
        ],
        stamp_text="IPI BERN / INPI PARIS",
    )
    (ws_a / "specs/ipi_bilingual_fee_annex.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ipiFeeSchedule effective="2026-Q4">\n'
        '  <surcharge code="BILINGUAL_FR_DE_PUB" appliesWhen="priority_prefix==FR" amountCHF="145.00"/>\n'
        '  <typography requireNarrowOrFrenchNBSPInsideGuillemets="U+00A0"/>\n'
        '</ipiFeeSchedule>\n',
        encoding="utf-8",
    )
    write_multipage_sop_pdf(
        ws_a / "specs/SOP_INPI_Filing.pdf",
        "SOP-HORO-01: Swiss/French Patent Dossier & Statutory Formatting",
        [
            ("1. Writer Dossier Requirements (Revendications_Echappement_INPI.odt)", [
                "1.1 Preserve docket header '[DOCKET-HORO-2026]' and format Application No, INPI Priority, IPC Class, Applicant, and Total Filing Fee CHF into a 2-column Writer table.",
                "1.2 Include the verbatim French title with proper French typographic spacing, purge unenforceable US 35 U.S.C. § 112(f) means-plus-function boilerplate, record the live INPI FR-AZERTY attestation code, synchronize the open Writer window, and export /workspace/Revendications_Echappement_INPI.pdf.",
            ]),
            ("2. JSON Schema (/workspace/patent_filing_summary.json)", [
                "Keys: application_no (str), inpi_priority (str), ipc_class (str), claim_count (int), total_filing_fee_chf (float, 2 dec), inpi_attestation_code (str).",
            ]),
        ],
    )
    write_simple_odt(
        ws_a / "Revendications_Echappement_INPI.odt",
        "Brevets Horlogers — Brouillon",
        [
            ("DOCKET", "[DOCKET-HORO-2026] Escapement Release Filing"),
            ("US_BOILERPLATE", "THIS CLAIM INVOKES 35 U.S.C. 112(f) MEANS-PLUS-FUNCTION INTERPRETATION IN DELAWARE."),
            ("STATUS", "ATTESTATION: PENDING"),
        ],
    )

    with sqlite3.connect(str(ws_b / "ledgers/vibrometry_420beats.sqlite")) as conn:
        conn.execute(
            "CREATE TABLE beat_measurements (row_id INTEGER PRIMARY KEY, sample_slot INTEGER, retest_seq INTEGER, "
            "condition_code TEXT, day_index INTEGER, chamber_hpa REAL, beat_rate_s_per_day REAL, amplitude_deg REAL, status TEXT)"
        )
        for r in _generate_vibrometry_rows():
            conn.execute(
                "INSERT INTO beat_measurements VALUES (?,?,?,?,?,?,?,?,?)",
                (r["row_id"], r["sample_slot"], r["retest_seq"], r["condition_code"], r["day_index"], r["chamber_hpa"], r["beat_rate_s_per_day"], r["amplitude_deg"], r["status"]),
            )
        conn.execute("CREATE TABLE hairspring_barometric_calibration (standard_hpa REAL, rate_sensitivity_spd_per_hpa REAL, note TEXT)")
        conn.execute("INSERT INTO hairspring_barometric_calibration VALUES (1013.25, -0.0085, 'Subtract (chamber_hpa - 1013.25)*rate_sensitivity to normalize to 1013.25 hPa sea-level ISO-3159 reference')")
        conn.commit()

    write_multipage_sop_pdf(
        ws_b / "specs/SOP_COSC_3159.pdf",
        "SOP-COSC-3159: Chronometer Isochronism & Workbook Specification",
        [
            ("1. Metrology Hygiene & Positional Isochronism", [
                "1.1 Retain final retest observations with VALID_LASER_LOCK in /workspace/ledgers/vibrometry_420beats.sqlite and normalize measurements to standard sea-level reference conditions.",
                "1.2 Compute mean rate per position (CH, FH, 6H, 9H, 3H), 5-position mean daily rate M, max positional spread P = MAX-MIN across the 5 positions, thermal coefficient C = (M_38C - M_8C)/30, and mean horizontal (CH & FH) balance amplitude.",
            ]),
            ("2. Workbook (COSC_Isochronism_Audit.xlsx) & JSON (/workspace/cosc_metrology_audit.json)", [
                "2.1 Sheet 'PositionRates': B2..B6 = CH, FH, 6H, 9H, 3H mean rates; B7 = '=AVERAGE(B2:B6)'; B8 = '=MAX(B2:B6)-MIN(B2:B6)'.",
                "2.2 Sheet 'Summary': B2 = valid_sample_count, B3 = '=PositionRates!B7', B4 = '=PositionRates!B8', B5 = thermal_coeff_c_spd_per_k, B6 = mean_horizontal_amplitude_deg, B7 = cosc_tariff_code. Keep Control!C2 = 'COSC-LAB-77' and synchronize the open Calc window.",
                "2.3 JSON keys: valid_sample_count (int), position_mean_rates_spd (dict), mean_daily_rate_m_spd (float), max_positional_spread_p_spd (float), thermal_coeff_c_spd_per_k (float), mean_horizontal_amplitude_deg (float), cosc_iso3159_certified (bool), cosc_tariff_code (str).",
            ]),
        ],
    )
    write_multisheet_xlsx(
        ws_b / "COSC_Isochronism_Audit.xlsx",
        [
            ("Control", [["Key", "State", "LabMarker"], ["ISO3159", "DRAFT", "COSC-LAB-77"]]),
            ("PositionRates", [
                ["Position", "Mean_Rate_s_day"],
                ["CH", 0.0], ["FH", 0.0], ["6H", 0.0], ["9H", 0.0], ["3H", 0.0],
                ["Mean_Daily_Rate_M", ("=AVERAGE(B2:B6)", 0.0)],
                ["Max_Spread_P", ("=MAX(B2:B6)-MIN(B2:B6)", 0.0)],
            ]),
            ("Summary", [
                ["Metric", "Value"],
                ["Valid_Sample_Count", 0],
                ["Mean_Daily_Rate_M", ("=PositionRates!B7", 0.0)],
                ["Max_Positional_Spread_P", ("=PositionRates!B8", 0.0)],
                ["Thermal_Coeff_C", 0.0],
                ["Mean_Horiz_Amplitude_Deg", 0.0],
                ["COSC_Tariff_Code", "PENDING"],
            ]),
        ],
    )
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    st_p = state_dir / "service_state.json"
    mem = {"xkb": "us", "xkb_switches": 0, "fr_verified": False}
    write_json(st_p, {"task_id": TASK_ID, **mem})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("horo_sso" in c) and (c["horo_sso"].value == tok)
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
                    self._json(403, {"error": "SSO token already consumed"}); return
                nxt = (qs.get("next") or ["/inpi-claims"])[0]
                raw = f"<html><body><script>location.href={json.dumps(nxt)};</script></body></html>".encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"horo_sso={tok}; HttpOnly; Path=/; SameSite=Lax"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly session required"}); return
            if u.path in ("/inpi-claims", "/cosc-bench"):
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/api/state":
                self._json(200, {**mem, "attest_code": INPI_ATTEST_CODE if mem["fr_verified"] else "", "cosc_code": COSC_TARIFF_CODE}); return
            self._json(404, {"error": "not found"})
        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly session required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/set_xkb":
                lyt = (qs.get("layout") or ["us"])[0]
                if lyt in ("fr", "us"):
                    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 XAUTHORITY=/run/user/1000/x99.auth setxkbmap {lyt}"], capture_output=True, timeout=5)
                    if lyt != mem["xkb"]:
                        mem["xkb"] = lyt; mem["xkb_switches"] += 1
                    write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True, "xkb": mem["xkb"]}); return
            if u.path == "/api/verify_fr":
                val = (qs.get("val") or [""])[0].strip()
                if mem["xkb"] == "fr" and ("échappement" in val.lower() and "çà" in val.lower()):
                    mem["fr_verified"] = True
                    write_json(st_p, {"task_id": TASK_ID, **mem})
                    self._json(200, {"verified": True, "attestation_code": INPI_ATTEST_CODE}); return
                self._json(200, {"verified": False, "error": "Requires active FR-AZERTY layout and exact accented phrase"}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or META["roles"])
    docs: list[Path] = []
    urls: list[str] = []
    if "swiss_patent_paralegal" in roles:
        docs.append(workspace_map["swiss_patent_paralegal"] / "Revendications_Echappement_INPI.odt")
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/inpi-claims")
    if "chronometer_metrology_analyst" in roles:
        docs.append(workspace_map["chronometer_metrology_analyst"] / "COSC_Isochronism_Audit.xlsx")
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/cosc-bench")
    launch_libreoffice_uno_natural(docs)
    launch_chromium_natural(urls)
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ws_a = workspace_map["swiss_patent_paralegal"]
    ws_b = workspace_map["chronometer_metrology_analyst"]
    uno_st = inspect_live_uno_documents_readonly()

    odt_txt = read_odt_plain_text(ws_a / "Revendications_Echappement_INPI.odt")
    pdf_txt = extract_pdf_text(ws_a / "Revendications_Echappement_INPI.pdf")
    ja = read_json_safe(ws_a / "patent_filing_summary.json")

    writer_sync = True
    writer_tbl = False
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Revendications_Echappement_INPI.odt" in u_url:
            writer_sync = (not u_doc.get("is_modified")) and ("CH-719842-B1" in (u_doc.get("text") or ""))
            writer_tbl = int(u_doc.get("table_count", 0)) >= 1

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.05, "Missing patent_filing_summary.json"),
        ("a_docket", bool(ja) and "[DOCKET-HORO-2026]" in odt_txt, 0.05, "Lost [DOCKET-HORO-2026] header"),
        ("a_ids_odt", PATENT_SPEC["application_no"] in odt_txt and PATENT_SPEC["inpi_priority"] in odt_txt and PATENT_SPEC["ipc_class"] in odt_txt, 0.08, "ODT missing CH/FR/IPC identifiers"),
        ("a_table_2col", writer_tbl, 0.07, "Writer ODT missing 2-column metadata table"),
        ("a_fr_accents", "Échappement" in odt_txt and "œillère" in odt_txt and "çà-et-là" in odt_txt, 0.07, "ODT missing accented French title"),
        ("a_us_purged", bool(ja) and "112(f)" not in odt_txt and "DELAWARE" not in odt_txt, 0.07, "Prohibited US 112(f) clause still present"),
        ("a_pdf_ok", (ws_a / "Revendications_Echappement_INPI.pdf").is_file() and PATENT_SPEC["application_no"] in pdf_txt and "DELAWARE" not in pdf_txt, 0.07, "Exported PDF missing or stale"),
        ("a_attest_odt", INPI_ATTEST_CODE in odt_txt and ja.get("inpi_attestation_code") == INPI_ATTEST_CODE and bool(service_state.get("fr_verified")), 0.09, "FR-AZERTY attestation missing or unverified"),
        ("a_writer_uno_sync", bool(ja) and writer_sync, 0.08, "Open LibreOffice Writer buffer out-of-sync with disk .odt"),
        ("a_json_ids", ja.get("application_no") == PATENT_SPEC["application_no"] and ja.get("claim_count") == 16, 0.06, "JSON patent IDs/claim_count mismatch"),
        ("a_fee_coarse", abs(_f(ja.get("total_filing_fee_chf")) - PATENT_SPEC["total_filing_fee_chf"]) <= 160.0, 0.07, "total_filing_fee_chf coarse off"),
        ("a_fine_bilingual_xml_fee", abs(_f(ja.get("total_filing_fee_chf")) - PATENT_SPEC["total_filing_fee_chf"]) <= 0.5, 0.12, "Exact 1035.00 CHF fee missed (check specs/ipi_bilingual_fee_annex.xml 145 CHF surcharge)"),
        ("a_fine_fr_nbsp_guillemet", ("«\u00a0" in odt_txt or "«\u202f" in odt_txt) and ("\u00a0»" in odt_txt or "\u202f»" in odt_txt), 0.12, "Missing French NBSP inside « ... » per ipi_bilingual_fee_annex.xml"),
    ]

    xlsx_p = ws_b / "COSC_Isochronism_Audit.xlsx"
    shs = read_multisheet_xlsx(xlsx_p) if xlsx_p.is_file() else {}
    ev_s = evaluate_xlsx_via_libreoffice(xlsx_p) if xlsx_p.is_file() else {}
    jb = read_json_safe(ws_b / "cosc_metrology_audit.json")

    def _cv(sh: str, ref: str) -> Any:
        v = ((ev_s.get(sh) or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get(sh) or {}).get(ref) or {}).get("value")

    def _cf(sh: str, ref: str) -> str:
        return str(((shs.get(sh) or {}).get(ref) or {}).get("formula") or "").upper().replace(" ", "")

    calc_sync = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "COSC_Isochronism_Audit.xlsx" in u_url:
            sm_u = (u_doc.get("sheets") or {}).get("Summary") or {}
            calc_sync = (not u_doc.get("is_modified")) and (COSC_TARIFF_CODE in json.dumps(sm_u))

    pm = jb.get("position_mean_rates_spd") if isinstance(jb.get("position_mean_rates_spd"), dict) else {}
    exp_pm = COSC_ORACLE["position_mean_rates_spd"]
    pos_coarse = sum(1 for p in POSITIONS if abs(_f(pm.get(p)) - exp_pm[p]) <= 0.55)
    pos_exact = sum(1 for p in POSITIONS if abs(_f(pm.get(p)) - exp_pm[p]) <= 0.015)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.05, "Missing cosc_metrology_audit.json"),
        ("b_cnt", jb.get("valid_sample_count") == COSC_ORACLE["valid_sample_count"], 0.07, f"valid_sample_count != {COSC_ORACLE['valid_sample_count']} (check retest_seq & status)"),
        ("b_pos_coarse", pos_coarse == 5, 0.07, "Position mean rates coarse mismatch (>0.55 s/d)"),
        ("b_m_coarse", abs(_f(jb.get("mean_daily_rate_m_spd")) - COSC_ORACLE["mean_daily_rate_m_spd"]) <= 0.40, 0.07, "Mean daily rate M coarse off"),
        ("b_p_coarse", abs(_f(jb.get("max_positional_spread_p_spd")) - COSC_ORACLE["max_positional_spread_p_spd"]) <= 0.50, 0.06, "Spread P coarse off"),
        ("b_therm_c", abs(_f(jb.get("thermal_coeff_c_spd_per_k")) - COSC_ORACLE["thermal_coeff_c_spd_per_k"]) <= 0.005, 0.07, "Thermal coeff C mismatch"),
        ("b_amp_deg", abs(_f(jb.get("mean_horizontal_amplitude_deg")) - COSC_ORACLE["mean_horizontal_amplitude_deg"]) <= 0.25, 0.06, "Horizontal amplitude mismatch"),
        ("b_cert_bool", jb.get("cosc_iso3159_certified") is COSC_ORACLE["cosc_iso3159_certified"], 0.05, "cosc_iso3159_certified mismatch"),
        ("b_code", jb.get("cosc_tariff_code") == COSC_TARIFF_CODE and str(_cv("Summary", "B7") or "") == COSC_TARIFF_CODE, 0.07, "Wrong cosc_tariff_code"),
        ("b_xlsx_formulas", "AVERAGE(B2:B6)" in _cf("PositionRates", "B7") and "MAX(B2:B6)-MIN(B2:B6)" in _cf("PositionRates", "B8"), 0.08, "PositionRates formulas corrupted (FR-AZERTY digit/minus remap?)"),
        ("b_ctrl_kept", bool(jb) and "COSC-LAB-77" in json.dumps(shs.get("Control") or {}), 0.04, "Control!C2 lost"),
        ("b_calc_uno_sync", bool(jb) and calc_sync, 0.07, "Open LibreOffice Calc buffer out-of-sync with disk .xlsx"),
        ("b_fine_baro_pos_exact", pos_exact == 5, 0.12, "Exact 5/5 position rates missed (check hairspring_barometric_calibration 965 hPa -> 1013.25 hPa)"),
        ("b_fine_baro_m_exact", abs(_f(jb.get("mean_daily_rate_m_spd")) - COSC_ORACLE["mean_daily_rate_m_spd"]) <= 0.008 and abs(_f(_cv("PositionRates", "B7")) - COSC_ORACLE["mean_daily_rate_m_spd"]) <= 0.015, 0.12, "Exact barometric-compensated M missed"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    if role == "swiss_patent_paralegal":
        odt_p = ws / "Revendications_Echappement_INPI.odt"
        with tempfile.TemporaryDirectory() as tmp:
            hp = Path(tmp) / "p.html"
            hp.write_text(
                "<!doctype html><html><head><meta charset='utf-8'/></head><body>"
                "<h1>[DOCKET-HORO-2026] Brevet Horloger Suisse/Français</h1>"
                f"<table border='1'><tr><td>Application</td><td>{PATENT_SPEC['application_no']}</td></tr>"
                f"<tr><td>INPI Priority</td><td>{PATENT_SPEC['inpi_priority']}</td></tr>"
                f"<tr><td>IPC</td><td>{PATENT_SPEC['ipc_class']}</td></tr>"
                f"<tr><td>Applicant</td><td>{PATENT_SPEC['applicant']}</td></tr>"
                f"<tr><td>Total Fee CHF</td><td>{PATENT_SPEC['total_filing_fee_chf']:.2f}</td></tr></table>"
                f"<p>{PATENT_SPEC['french_title']}</p>"
                f"<p>ATTESTATION: {INPI_ATTEST_CODE}</p></body></html>",
                encoding="utf-8",
            )
            subprocess.run(["libreoffice", f"-env:UserInstallation=file://{tmp}/lo1", "--headless", "--convert-to", "odt", "--outdir", str(tmp), str(hp)], check=True, capture_output=True, timeout=45)
            odt_p.write_bytes((Path(tmp) / "p.odt").read_bytes())
            subprocess.run(["libreoffice", f"-env:UserInstallation=file://{tmp}/lo2", "--headless", "--convert-to", "pdf", "--outdir", str(ws), str(odt_p)], check=True, capture_output=True, timeout=45)
        st_f = Path("/opt/nf_state/service_state.json")
        if st_f.is_file():
            with file_atomic_lock("nf201_st"):
                st = read_json_safe(st_f); st["fr_verified"] = True; write_json(st_f, st)
        with file_atomic_lock("nf201_uno"):
            reload_uno_pipe_documents([odt_p])
        write_json(ws / "patent_filing_summary.json", {
            "application_no": PATENT_SPEC["application_no"], "inpi_priority": PATENT_SPEC["inpi_priority"],
            "ipc_class": PATENT_SPEC["ipc_class"], "claim_count": PATENT_SPEC["claim_count"],
            "total_filing_fee_chf": PATENT_SPEC["total_filing_fee_chf"], "inpi_attestation_code": INPI_ATTEST_CODE,
        })
    else:
        xp = ws / "COSC_Isochronism_Audit.xlsx"
        pm = COSC_ORACLE["position_mean_rates_spd"]
        write_multisheet_xlsx(xp, [
            ("Control", [["Key", "State", "LabMarker"], ["ISO3159", "CERTIFIED", "COSC-LAB-77"]]),
            ("PositionRates", [
                ["Position", "Mean_Rate_s_day"],
                ["CH", pm["CH"]], ["FH", pm["FH"]], ["6H", pm["6H"]], ["9H", pm["9H"]], ["3H", pm["3H"]],
                ["Mean_Daily_Rate_M", ("=AVERAGE(B2:B6)", COSC_ORACLE["mean_daily_rate_m_spd"])],
                ["Max_Spread_P", ("=MAX(B2:B6)-MIN(B2:B6)", COSC_ORACLE["max_positional_spread_p_spd"])],
            ]),
            ("Summary", [
                ["Metric", "Value"],
                ["Valid_Sample_Count", COSC_ORACLE["valid_sample_count"]],
                ["Mean_Daily_Rate_M", ("=PositionRates!B7", COSC_ORACLE["mean_daily_rate_m_spd"])],
                ["Max_Positional_Spread_P", ("=PositionRates!B8", COSC_ORACLE["max_positional_spread_p_spd"])],
                ["Thermal_Coeff_C", COSC_ORACLE["thermal_coeff_c_spd_per_k"]],
                ["Mean_Horiz_Amplitude_Deg", COSC_ORACLE["mean_horizontal_amplitude_deg"]],
                ["COSC_Tariff_Code", COSC_TARIFF_CODE],
            ]),
        ])
        with file_atomic_lock("nf201_uno"):
            reload_uno_pipe_documents([xp])
        write_json(ws / "cosc_metrology_audit.json", COSC_ORACLE)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    solve_role("swiss_patent_paralegal", workspace_map, port)
    solve_role("chronometer_metrology_analyst", workspace_map, port)
    ws_b = workspace_map["chronometer_metrology_analyst"]
    # Simulate FR-AZERTY top-row unshifted corruption of Calc formula '=MAX(B2:B6)-MIN(B2:B6)' -> '=MAX(Bé:B-()MIN...'
    update_single_sheet_xlsx(ws_b / "COSC_Isochronism_Audit.xlsx", "PositionRates", [
        ["Position", "Mean_Rate_s_day"],
        ["CH", 0.0], ["FH", 0.0], ["6H", 0.0], ["9H", 0.0], ["3H", 0.0],
        ["Mean_Daily_Rate_M", "AZERTY_ERR_&é"], ["Max_Spread_P", "=MAX(Bé:B-)"],
    ])
    jb = read_json_safe(ws_b / "cosc_metrology_audit.json")
    jb["mean_daily_rate_m_spd"] = 99.9
    write_json(ws_b / "cosc_metrology_audit.json", jb)
    st = read_json_safe(state_dir / "service_state.json")
    st["xkb_switches"] = int(st.get("xkb_switches", 0)) + 5
    write_json(state_dir / "service_state.json", st)

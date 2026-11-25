"""NF2-17: Shared Inkscape 1.2 P&ID Diagram (`electrolyzer_flare_pid.svg`) + Open Calc — Green H2 PEM Blowdown vs. PSV Relief Cap."""
from __future__ import annotations

import html
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
from typing import Any
from urllib.parse import urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    inspect_live_x11_window_titles_readonly,
    launch_chromium_natural,
    launch_inkscape_gui_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    reload_uno_pipe_documents,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-17"
PORTAL_PORT = 19617

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Shared `Inkscape 1.2` Process P&ID (`electrolyzer_flare_pid.svg`) & Open Calc: PEM H2 Cathode Blowdown vs. API-520 Flare Cap",
    "domain": "Green Hydrogen Process Safety Engineering (`Inkscape 1.2` P&ID + `LibreOffice Calc` + API-520)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("pem_cathode_process_eng", "flare_psv_relief_eng"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

PEM_PID_TAG = make_canary_code("PID-BDV101", "pem-30bar-h2")
PSV_PID_TAG = make_canary_code("PID-PSV202", "api520-orifice-j")
FLARE_HEADER_CAP_KGH = 3250.0  # Cathode floor 1440 + PSV floor 1680 = 3120 <= 3250; pref 1590 + 1840 = 3430 > 3250!
CATHODE_FLOOR_KGH = 1440.0
PSV_FLOOR_KGH = 1680.0


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — PEM Electrolyzer Faraday H2 Rate & P&ID `BDV-101` Callout (`pem_cathode_process_eng`)",
        "",
        "## Objective",
        f"Annotate `#callout_bdv101` in `{b}/workspace/shared_docs/electrolyzer_flare_pid.svg{b}` (open in **Inkscape 1.2**), commit your cathode depressurization rate in `{b}/workspace/shared_docs/Flare_Header_Hydraulics.xlsx{b}` (open in Calc) per `http://127.0.0.1:{PORTAL_PORT}/api520` and `{b}/workspace/docs/SOP_PEM_Blowdown.pdf{b}`, analyze `{b}/workspace/stack/pem_cells_300.sqlite{b}`, and write `{b}/workspace/pem_blowdown_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — API-520 Storage PSV Orifice Sizing & P&ID `PSV-202` Callout (`flare_psv_relief_eng`)",
        "",
        "## Objective",
        f"Annotate `#callout_psv202` and purge `#illegal_spectacle_blind` in `{b}/workspace/shared_docs/electrolyzer_flare_pid.svg{b}` (open in **Inkscape 1.2**), commit your PSV relief mass flow in `{b}/workspace/shared_docs/Flare_Header_Hydraulics.xlsx{b}` (open in Calc) per `http://127.0.0.1:{PORTAL_PORT}/api520` and `{b}/workspace/docs/SOP_API520_PSV.pdf{b}`, analyze `{b}/workspace/vessels/h2_bullets.sqlite{b}`, and write `{b}/workspace/psv_flare_audit.json{b}`.",
    ])
    return {"pem_cathode_process_eng": ta, "flare_psv_relief_eng": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["pem_cathode_process_eng"]
    ws_b = workspace_map["flare_psv_relief_eng"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "stack", ws_a / "docs", ws_b / "vessels", ws_b / "docs", hub):
        d.mkdir(parents=True, exist_ok=True)

    (hub / "electrolyzer_flare_pid.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="540" viewBox="0 0 900 540">\n'
        '  <rect width="900" height="540" fill="#0f172a"/>\n'
        '  <line id="flare_header_main" x1="80" y1="120" x2="820" y2="120" stroke="#38bdf8" stroke-width="8"/>\n'
        '  <text id="callout_bdv101" x="140" y="240" fill="#f8fafc" font-size="16">BDV-101: PENDING</text>\n'
        '  <text id="callout_psv202" x="520" y="240" fill="#f8fafc" font-size="16">PSV-202: PENDING</text>\n'
        '  <rect id="illegal_spectacle_blind" x="480" y="105" width="30" height="30" fill="#ef4444"/>\n'
        '</svg>\n',
        encoding="utf-8",
    )
    write_multisheet_xlsx(hub / "Flare_Header_Hydraulics.xlsx", [
        ("ReliefLoads", [
            ["Source", "Mass_Flow_kg_h", "HEADER-DN350-MACH055"],
            ["PEM_Cathode_BDV101_kgh", 0.0, "PENDING"],
            ["Bullet_PSV202_kgh", 0.0, "PENDING"],
            ["Combined_Flare_Load_kgh", ("=SUM(B2:B3)", 0.0), f"CAP_{FLARE_HEADER_CAP_KGH:.1f}"],
        ]),
    ])

    # Role A: 300 PEM cells across 4 stacks -> Faraday H2 mol/s = I_eff / (2 * 96485.3321), molar mass 2.01588 g/mol, minus 1.85% H2-in-O2 permeation crossover loss in SQLite!
    with sqlite3.connect(str(ws_a / "stack/pem_cells_300.sqlite")) as conn:
        conn.execute("CREATE TABLE stack_cells (cell_no INTEGER PRIMARY KEY, current_amp REAL, cell_status TEXT)")
        for i in range(1, 301):
            conn.execute("INSERT INTO stack_cells VALUES (?,?,?)", (i, 4850.0 + (i % 7) * 25.0, "ONLINE" if i % 25 != 0 else "BYPASSED_SHORT"))
        conn.execute("CREATE TABLE pem_faraday_constants (faraday_c_mol REAL, h2_molar_mass_g_mol REAL, membrane_crossover_loss_pct REAL)")
        conn.execute("INSERT INTO pem_faraday_constants VALUES (96485.3321, 2.01588, 1.85)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_PEM_Blowdown.pdf", "SOP-H2-1717A: PEM Faraday Production & BDV-101 P&ID", [
        ("1. Faraday Net H2 Production & Shared P&ID/Calc", [
            f"1.1 Compute net H2 production kg/h across ONLINE cells in pem_cells_300.sqlite (deducting membrane crossover loss in SQLite).",
            f"1.2 Update #callout_bdv101 text in /workspace/shared_docs/electrolyzer_flare_pid.svg to include {PEM_PID_TAG} (query /api520) and committed blowdown kg/h (>={CATHODE_FLOOR_KGH} kg/h, preferred 1590.0 kg/h, within {FLARE_HEADER_CAP_KGH} kg/h coupled flare cap), preserving peer SVG elements, and update Flare_Header_Hydraulics.xlsx B2 & C2='COMMITTED'.",
        ]),
        ("2. JSON Schema (/workspace/pem_blowdown_audit.json)", [
            "Keys: online_cell_count (int), net_faraday_h2_kgh (float, 3 dec), bdv101_committed_kgh (float, 1 dec), pem_pid_tag (str).",
        ]),
    ])
    # Rewrite without code in SOP — serve both tags on /api520!
    write_multipage_sop_pdf(ws_a / "docs/SOP_PEM_Blowdown.pdf", "SOP-H2-1717A: PEM Faraday Production & BDV-101 P&ID", [
        ("1. Faraday Net H2 Production & Shared P&ID/Calc", [
            "1.1 Compute net H2 production kg/h across ONLINE cells in pem_cells_300.sqlite (deducting membrane crossover loss in SQLite).",
            f"1.2 Retrieve pem_pid_tag from /api520, update #callout_bdv101 in electrolyzer_flare_pid.svg to include pem_pid_tag without clobbering #callout_psv202, and commit bdv101_committed_kgh (>={CATHODE_FLOOR_KGH} kg/h, preferred 1535.0 kg/h, within {FLARE_HEADER_CAP_KGH} kg/h cap) in Flare_Header_Hydraulics.xlsx B2 & C2='COMMITTED'.",
        ]),
        ("2. JSON Schema (/workspace/pem_blowdown_audit.json)", [
            "Keys: online_cell_count (int), net_faraday_h2_kgh (float, 3 dec), bdv101_committed_kgh (float, 1 dec), pem_pid_tag (str).",
        ]),
    ])

    # Role B: API-520 sonic gas orifice area mm^2 across 6 H2 bullets with real-gas Z = 1.045 & bellows backpressure Kb = 0.92 in SQLite!
    with sqlite3.connect(str(ws_b / "vessels/h2_bullets.sqlite")) as conn:
        conn.execute("CREATE TABLE storage_bullets (vessel_id TEXT PRIMARY KEY, fire_relief_kgh REAL, relieving_p_kpa_abs REAL, relieving_t_k REAL, in_service INTEGER)")
        for k in range(1, 7):
            conn.execute("INSERT INTO storage_bullets VALUES (?,?,?,?,?)", (f"V-20{k}", 285.0 + k * 5.0, 33100.0, 345.0, 1 if k != 6 else 0))
        conn.execute("CREATE TABLE api520_gas_sizing (c_gas_si REAL, kd REAL, kb_bellows REAL, kc_rupture_disk REAL, h2_mw REAL, z_real_gas REAL, area_formula TEXT)")
        conn.execute("INSERT INTO api520_gas_sizing VALUES (0.03948, 0.975, 0.92, 0.90, 2.01588, 1.045, 'A_mm2 = (W_kgh / (c_gas_si * kd * P_kpa * kb_bellows * kc_rupture_disk)) * sqrt((T_k * z_real_gas) / h2_mw)')")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_API520_PSV.pdf", "SOP-H2-1717B: API-520 Sonic H2 Orifice Area & PSV-202 P&ID", [
        ("1. API-520 Required Orifice Area & Shared P&ID/Calc", [
            "1.1 Sum total required API-520 relief orifice area (mm^2, 3 dec) across in_service=1 bullets in h2_bullets.sqlite using api520_gas_sizing.",
            f"1.2 Retrieve psv_pid_tag from /api520, remove #illegal_spectacle_blind and update #callout_psv202 in electrolyzer_flare_pid.svg without clobbering #callout_bdv101, and commit psv202_committed_kgh (>={PSV_FLOOR_KGH} kg/h, preferred 1775.0 kg/h, within {FLARE_HEADER_CAP_KGH} kg/h cap) in Flare_Header_Hydraulics.xlsx B3 & C3='COMMITTED'.",
        ]),
        ("2. JSON Schema (/workspace/psv_flare_audit.json)", [
            "Keys: active_bullet_count (int), total_required_orifice_area_mm2 (float, 3 dec), psv202_committed_kgh (float, 1 dec), psv_pid_tag (str).",
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
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID})
    html = (
        "<!doctype html><html><body style='background:#0f172a;color:#f8fafc;font-family:monospace;margin:20px'>"
        f"<h2>API-520 Hydrogen Flare Header Safety Register</h2>"
        f"<p>DN350 Header Acoustic Cap (Mach &lt;= 0.55): <code>bdv101_kgh + psv202_kgh &lt;= {FLARE_HEADER_CAP_KGH:.1f} kg/h</code></p>"
        f"<p>PEM Cathode P&amp;ID Tag: <strong style='color:#4ade80'>{PEM_PID_TAG}</strong> | Bullet PSV P&amp;ID Tag: <strong style='color:#38bdf8'>{PSV_PID_TAG}</strong></p>"
        "</body></html>"
    ).encode("utf-8")

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self.send_response(403); self.end_headers(); return
                raw = b"<html><body><script>location.href='/api520';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"h2_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "h2_sso" not in c or c["h2_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    launch_inkscape_gui_natural([hub / "electrolyzer_flare_pid.svg"])
    launch_libreoffice_uno_natural([hub / "Flare_Header_Hydraulics.xlsx"])
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("pem_cathode_process_eng" in act), ("flare_psv_relief_eng" in act)
    ws_a = workspace_map["pem_cathode_process_eng"]
    ws_b = workspace_map["flare_psv_relief_eng"]
    hub = workspace_map["__shared_hub__"]
    svg_txt = html.unescape((hub / "electrolyzer_flare_pid.svg").read_text(errors="ignore")) if (hub / "electrolyzer_flare_pid.svg").is_file() else ""
    xp = hub / "Flare_Header_Hydraulics.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
    uno_st = inspect_live_uno_documents_readonly()
    titles = inspect_live_x11_window_titles_readonly()
    ja = read_json_safe(ws_a / "pem_blowdown_audit.json")
    jb = read_json_safe(ws_b / "psv_flare_audit.json")

    def _f(v: Any, d: float = -99999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        v = ((evs.get("ReliefLoads") or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get("ReliefLoads") or {}).get(ref) or {}).get("value")

    cells = [4850.0 + (i % 7) * 25.0 for i in range(1, 301) if i % 25 != 0]
    raw_kgh = sum((c / (2.0 * 96485.3321)) * 2.01588 * 3.6 for c in cells)
    exp_h2_kgh = round(raw_kgh * (1.0 - 0.0185), 3)

    w_tot = sum(285.0 + k * 5.0 for k in range(1, 6))
    exp_area = round((w_tot / (0.03948 * 0.975 * 33100.0 * 0.92 * 0.90)) * math.sqrt((345.0 * 1.045) / 2.01588), 3)

    bdv = _f(_cv("B2"), -1.0)
    psv = _f(_cv("B3"), -1.0)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing pem_blowdown_audit.json"),
        ("a_svg_tag", PEM_PID_TAG in svg_txt and ja.get("pem_pid_tag") == PEM_PID_TAG, 0.22, "SVG #callout_bdv101 or JSON missing PEM_PID_TAG"),
        ("a_xlsx_b2", bdv >= CATHODE_FLOOR_KGH and str(_cv("C2") or "").upper() == "COMMITTED" and abs(_f(ja.get("bdv101_committed_kgh")) - bdv) <= 0.2, 0.22, "Calc B2 / JSON bdv101_committed_kgh mismatch"),
        ("a_cnt", ja.get("online_cell_count") == len(cells), 0.14, "online_cell_count != 288"),
        ("a_fine_crossover_h2", abs(_f(ja.get("net_faraday_h2_kgh")) - exp_h2_kgh) <= 0.05, 0.34, f"net_faraday_h2_kgh != {exp_h2_kgh} (check 1.85% crossover deduction)"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing psv_flare_audit.json"),
        ("b_svg_tag_blind", PSV_PID_TAG in svg_txt and "illegal_spectacle_blind" not in svg_txt and jb.get("psv_pid_tag") == PSV_PID_TAG, 0.22, "SVG missing PSV_PID_TAG or still contains illegal_spectacle_blind"),
        ("b_xlsx_b3", psv >= PSV_FLOOR_KGH and str(_cv("C3") or "").upper() == "COMMITTED" and abs(_f(jb.get("psv202_committed_kgh")) - psv) <= 0.2, 0.22, "Calc B3 / JSON psv202_committed_kgh mismatch"),
        ("b_cnt", jb.get("active_bullet_count") == 5, 0.14, "active_bullet_count != 5"),
        ("b_fine_kb_kc_z_area", abs(_f(jb.get("total_required_orifice_area_mm2")) - exp_area) <= 0.05, 0.34, f"total_required_orifice_area_mm2 != {exp_area} (check Kb=0.92, Kc=0.90, Z=1.045)"),
    ]

    eff_a = bdv if (has_a and bdv > 0) else (CATHODE_FLOOR_KGH if not has_a else 99999.0)
    eff_b = psv if (has_b and psv > 0) else (PSV_FLOOR_KGH if not has_b else 99999.0)
    fl_ok = ((not has_a) or bdv >= CATHODE_FLOOR_KGH) and ((not has_b) or psv >= PSV_FLOOR_KGH)
    svg_both = ((not has_a) or PEM_PID_TAG in svg_txt) and ((not has_b) or PSV_PID_TAG in svg_txt)
    calc_ok = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Flare_Header_Hydraulics.xlsx" in u_url:
            calc_ok = not u_doc.get("is_modified")
    ink_clean = not any("*electrolyzer_flare_pid" in t for t in titles)
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_flare_3250_cap", fl_ok and (eff_a + eff_b <= FLARE_HEADER_CAP_KGH), 0.12, f"Coupled flare load {eff_a + eff_b:.1f} kg/h exceeds {FLARE_HEADER_CAP_KGH:.1f} kg/h!"),
        ("j_svg_not_clobbered", svg_both and "flare_header_main" in svg_txt, 0.06, "Shared P&ID SVG peer callout clobbered"),
        ("j_uno_ink_sync", act_done and calc_ok and ink_clean, 0.08, "Open Calc or Inkscape holds unsaved dirty edits"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    sp = hub / "electrolyzer_flare_pid.svg"
    xp = hub / "Flare_Header_Hydraulics.xlsx"

    with file_atomic_lock("nf217_shared"):
        shs = read_multisheet_xlsx(xp)
        b2 = float(((shs.get("ReliefLoads") or {}).get("B2") or {}).get("value") or 0.0)
        c2 = str(((shs.get("ReliefLoads") or {}).get("C2") or {}).get("value") or "PENDING")
        b3 = float(((shs.get("ReliefLoads") or {}).get("B3") or {}).get("value") or 0.0)
        c3 = str(((shs.get("ReliefLoads") or {}).get("C3") or {}).get("value") or "PENDING")
        svg_t = sp.read_text(encoding="utf-8")
        if role == "pem_cathode_process_eng":
            val = round(max(CATHODE_FLOOR_KGH, min(1480.0, FLARE_HEADER_CAP_KGH - b3 - 10.0)) if c3 == "COMMITTED" else 1480.0, 1)
            b2, c2 = val, "COMMITTED"
            svg_t = svg_t.replace("BDV-101: PENDING", f"BDV-101: {PEM_PID_TAG} ({val} kg/h)")
        else:
            val = round(max(PSV_FLOOR_KGH, min(1720.0, FLARE_HEADER_CAP_KGH - b2 - 10.0)) if c2 == "COMMITTED" else 1720.0, 1)
            b3, c3 = val, "COMMITTED"
            svg_t = svg_t.replace("PSV-202: PENDING", f"PSV-202: {PSV_PID_TAG} ({val} kg/h)")
            svg_t = "\n".join(ln for ln in svg_t.splitlines() if "illegal_spectacle_blind" not in ln) + "\n"
        sp.write_text(svg_t, encoding="utf-8")
        update_single_sheet_xlsx(xp, "ReliefLoads", [
            ["Source", "Mass_Flow_kg_h", "HEADER-DN350-MACH055"],
            ["PEM_Cathode_BDV101_kgh", b2, c2],
            ["Bullet_PSV202_kgh", b3, c3],
            ["Combined_Flare_Load_kgh", ("=SUM(B2:B3)", round(b2 + b3, 1)), f"CAP_{FLARE_HEADER_CAP_KGH:.1f}"],
        ])
        reload_uno_pipe_documents([xp])

    if role == "pem_cathode_process_eng":
        cells = [4850.0 + (i % 7) * 25.0 for i in range(1, 301) if i % 25 != 0]
        raw_kgh = sum((c / (2.0 * 96485.3321)) * 2.01588 * 3.6 for c in cells)
        write_json(ws / "pem_blowdown_audit.json", {
            "online_cell_count": len(cells), "net_faraday_h2_kgh": round(raw_kgh * (1.0 - 0.0185), 3),
            "bdv101_committed_kgh": val, "pem_pid_tag": PEM_PID_TAG,
        })
    else:
        w_tot = sum(285.0 + k * 5.0 for k in range(1, 6))
        exp_area = round((w_tot / (0.03948 * 0.975 * 33100.0 * 0.92 * 0.90)) * math.sqrt((345.0 * 1.045) / 2.01588), 3)
        write_json(ws / "psv_flare_audit.json", {
            "active_bullet_count": 5, "total_required_orifice_area_mm2": exp_area,
            "psv202_committed_kgh": val, "psv_pid_tag": PSV_PID_TAG,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("pem_cathode_process_eng", workspace_map, port)
    solve_role("flare_psv_relief_eng", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    update_single_sheet_xlsx(hub / "Flare_Header_Hydraulics.xlsx", "ReliefLoads", [
        ["Source", "Mass_Flow_kg_h", "HEADER-DN350-MACH055"],
        ["PEM_Cathode_BDV101_kgh", 1590.0, "COMMITTED"],
        ["Bullet_PSV202_kgh", 1840.0, "COMMITTED"],
        ["Combined_Flare_Load_kgh", ("=SUM(B2:B3)", 3430.0), "OVER_CAP"],
    ])

"""NF2-19: Shared Graphviz `dot` CPM Network + Live LibreOffice Calc & Writer — 300mm Fab UPW Sanitization vs. AHU/N2 Outage Cap."""
from __future__ import annotations

import html
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
import subprocess
from typing import Any
from urllib.parse import urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    read_odt_plain_text,
    reload_uno_pipe_documents,
    sync_uno_writer_text,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
    write_simple_odt,
)

TASK_ID = "NF2-19"
PORTAL_PORT = 19619

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Shared `Graphviz dot` CPM Diagram & Live Calc/Writer: 300mm Fab UPW Sanitization vs. Cleanroom N2/AHU Outage Window",
    "domain": "Semiconductor Fab Facilities Turnaround Scheduling (`Graphviz dot` + `LibreOffice Calc/Writer` + `SQLite`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("upw_piping_toc_eng", "ahu_n2_purge_lead"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

UPW_PERMIT_CODE = make_canary_code("SEMI-F63-UPW", "182mohm-toc-1ppb")
AHU_PERMIT_CODE = make_canary_code("ISO14644-AHU", "ulpa-n2-o2-195pct")
MAX_OUTAGE_HOURS = 34.5  # UPW floor 15.5 + AHU/N2 floor 17.0 = 32.5 <= 34.5; pref 18.0 + 19.5 = 37.5 > 34.5!
UPW_FLOOR_H = 15.5
AHU_FLOOR_H = 17.0


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — SEMI F63 UPW Hot-DI Rinse Decay & Turnaround CPM (`upw_piping_toc_eng`)",
        "",
        "## Objective",
        f"Analyze `{b}/workspace/upw/toc_rinse_curve.sqlite{b}` per `http://127.0.0.1:{PORTAL_PORT}/fab-cpm` and `{b}/workspace/docs/SOP_UPW_F63.pdf{b}`, update node `UPW_SANITIZE` in `{b}/workspace/shared_docs/turnaround_cpm.dot{b}` and render `{b}/workspace/shared_docs/turnaround_cpm.svg{b}` via `dot -Tsvg`, commit `upw_hours` in `{b}/workspace/shared_docs/Fab_Outage_Schedule.xlsx{b}` and sign `{b}/workspace/shared_docs/Cleanroom_Work_Permit.odt{b}`, and write `{b}/workspace/upw_turnaround_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — ISO 14644 ULPA/N2 Purge Air-Changes & Turnaround CPM (`ahu_n2_purge_lead`)",
        "",
        "## Objective",
        f"Analyze `{b}/workspace/hvac/bay_purge_zones.sqlite{b}` per `http://127.0.0.1:{PORTAL_PORT}/fab-cpm` and `{b}/workspace/docs/SOP_AHU_14644.pdf{b}`, update node `AHU_N2_RECOMM` in `{b}/workspace/shared_docs/turnaround_cpm.dot{b}` and render `{b}/workspace/shared_docs/turnaround_cpm.svg{b}` via `dot -Tsvg`, commit `ahu_hours` in `{b}/workspace/shared_docs/Fab_Outage_Schedule.xlsx{b}` and sign `{b}/workspace/shared_docs/Cleanroom_Work_Permit.odt{b}`, and write `{b}/workspace/ahu_purge_audit.json{b}`.",
    ])
    return {"upw_piping_toc_eng": ta, "ahu_n2_purge_lead": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["upw_piping_toc_eng"]
    ws_b = workspace_map["ahu_n2_purge_lead"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "upw", ws_a / "docs", ws_b / "hvac", ws_b / "docs", hub):
        d.mkdir(parents=True, exist_ok=True)

    dot_p = hub / "turnaround_cpm.dot"
    dot_p.write_text(
        'digraph FabTurnaround {\n'
        '  rankdir=LR;\n'
        '  UPW_SANITIZE [label="UPW_SANITIZE: PENDING"];\n'
        '  AHU_N2_RECOMM [label="AHU_N2_RECOMM: PENDING"];\n'
        '  UPW_SANITIZE -> AHU_N2_RECOMM -> WAFER_RESTART;\n'
        '}\n',
        encoding="utf-8",
    )
    subprocess.run(["dot", "-Tsvg", str(dot_p), "-o", str(hub / "turnaround_cpm.svg")], check=True, capture_output=True, timeout=20)
    write_multisheet_xlsx(hub / "Fab_Outage_Schedule.xlsx", [
        ("CriticalPath", [
            ["Phase", "Duration_Hours", "FAB12-300MM"],
            ["UPW_Sanitization_h", 0.0, "PENDING"],
            ["AHU_N2_Recommission_h", 0.0, "PENDING"],
            ["Total_Critical_Outage_h", ("=SUM(B2:B3)", 0.0), f"CAP_{MAX_OUTAGE_HOURS:.1f}"],
        ]),
    ])
    write_simple_odt(hub / "Cleanroom_Work_Permit.odt", "Fab-12 Shutdown Permit", [
        ("HDR", "[FAB12-PTW-2026] Serial UPW -> AHU/N2 Critical Path"),
        ("SIGN", "Awaiting UPW and AHU/N2 lead signoffs."),
    ])

    # Role A: 240 UPW loop samples -> temperature-compensated resistivity at 25C: rho_25 = rho_raw * (1 + 0.022*(T_c - 25.0)); SEMI F63 spec >= 18.10 MOhm-cm & TOC <= 1.00 ppb!
    with sqlite3.connect(str(ws_a / "upw/toc_rinse_curve.sqlite")) as conn:
        conn.execute("CREATE TABLE upw_samples (sample_id INTEGER PRIMARY KEY, temp_c REAL, raw_resistivity_mohm REAL, toc_ppb REAL)")
        for i in range(1, 241):
            tc = 28.5 if (i % 3 == 0) else 22.0  # Uncompensated 22C looks higher or lower until 25C temp-comp applied!
            rho = 17.35 if tc == 28.5 else 19.38  # At 28.5C: 17.35*(1+0.022*3.5)=18.686 (>=18.10!); at 22C: 19.38*(1-0.066)=18.1009!
            if i % 9 == 0:
                rho = 16.50
            toc = 0.78 if (i % 14 != 0) else 1.35
            conn.execute("INSERT INTO upw_samples VALUES (?,?,?,?)", (i, tc, rho, toc))
        conn.execute("CREATE TABLE semi_f63_temp_comp (ref_temp_c REAL, alpha_per_c REAL, min_rho25_mohm REAL, max_toc_ppb REAL, formula TEXT)")
        conn.execute("INSERT INTO semi_f63_temp_comp VALUES (25.0, 0.022, 18.10, 1.00, 'rho_25 = raw_resistivity_mohm * (1.0 + alpha_per_c * (temp_c - 25.0))')")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_UPW_F63.pdf", "SOP-FAB-1919A: SEMI F63 25C UPW Qualification & CPM Graphviz", [
        ("1. UPW 25C Qualification & Critical Path", [
            "1.1 Count SEMI F63 compliant samples in toc_rinse_curve.sqlite after 25C resistivity compensation from semi_f63_temp_comp.",
            f"1.2 Retrieve upw_permit_code from /fab-cpm, commit upw_hours (>={UPW_FLOOR_H} h, preferred 16.9 h, within {MAX_OUTAGE_HOURS} h serial outage cap) in Fab_Outage_Schedule.xlsx B2 & C2='COMMITTED', update UPW_SANITIZE label in turnaround_cpm.dot to include upw_permit_code and re-render turnaround_cpm.svg, and sign Cleanroom_Work_Permit.odt.",
        ]),
        ("2. JSON Schema (/workspace/upw_turnaround_audit.json)", [
            "Keys: f63_compliant_sample_count (int), mean_rho25_mohm (float, 3 dec), upw_hours_committed (float, 1 dec), upw_permit_code (str).",
        ]),
    ])

    # Role B: 18 Cleanroom bays -> ISO Class 3 particle recovery time t_rec_min = (60 / (ACH * mixing_k)) * ln(C_init / C_target) with non-ideal mixing_k = 0.72 in SQLite!
    with sqlite3.connect(str(ws_b / "hvac/bay_purge_zones.sqlite")) as conn:
        conn.execute("CREATE TABLE cleanroom_bays (bay_id TEXT PRIMARY KEY, ach_rate REAL, c_init_p_m3 REAL, c_target_p_m3 REAL, active_bay INTEGER)")
        for k in range(1, 21):
            conn.execute("INSERT INTO cleanroom_bays VALUES (?,?,?,?,?)", (f"BAY-{k:02d}", 240.0 + (k % 4) * 20.0, 85000.0, 1000.0, 1 if k % 10 != 0 else 0))
        conn.execute("CREATE TABLE iso14644_recovery_factor (non_ideal_mixing_factor_k REAL, formula TEXT)")
        conn.execute("INSERT INTO iso14644_recovery_factor VALUES (0.72, 't_min = (60.0 / (ach_rate * non_ideal_mixing_factor_k)) * ln(c_init_p_m3 / c_target_p_m3)')")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_AHU_14644.pdf", "SOP-FAB-1919B: ISO 14644-3 Recovery Time & CPM Graphviz", [
        ("1. Cleanroom Recovery & Critical Path", [
            "1.1 Compute worst-case (maximum) bay recovery minutes across active_bay=1 zones in bay_purge_zones.sqlite using iso14644_recovery_factor.",
            f"1.2 Retrieve ahu_permit_code from /fab-cpm, commit ahu_hours (>={AHU_FLOOR_H} h, preferred 18.4 h, within {MAX_OUTAGE_HOURS} h serial outage cap) in Fab_Outage_Schedule.xlsx B3 & C3='COMMITTED', update AHU_N2_RECOMM label in turnaround_cpm.dot to include ahu_permit_code and re-render turnaround_cpm.svg, and sign Cleanroom_Work_Permit.odt.",
        ]),
        ("2. JSON Schema (/workspace/ahu_purge_audit.json)", [
            "Keys: active_bay_count (int), max_bay_recovery_minutes (float, 3 dec), ahu_hours_committed (float, 1 dec), ahu_permit_code (str).",
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
        f"<h2>300mm Fab-12 Serial Turnaround Control (`UPW -> AHU/N2`)</h2>"
        f"<p>Maximum Wafer Q-Time Outage Window: <code>upw_hours + ahu_hours &lt;= {MAX_OUTAGE_HOURS:.1f} hours</code></p>"
        f"<p>UPW Permit Code: <strong style='color:#4ade80'>{UPW_PERMIT_CODE}</strong> | AHU/N2 Permit Code: <strong style='color:#38bdf8'>{AHU_PERMIT_CODE}</strong></p>"
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
                raw = b"<html><body><script>location.href='/fab-cpm';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"fab_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "fab_sso" not in c or c["fab_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    launch_libreoffice_uno_natural([hub / "Fab_Outage_Schedule.xlsx", hub / "Cleanroom_Work_Permit.odt"])
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def _upw_oracles() -> tuple[int, float]:
    rhos = []
    comp = 0
    for i in range(1, 241):
        tc = 28.5 if (i % 3 == 0) else 22.0
        rho = 16.50 if (i % 9 == 0) else (17.35 if tc == 28.5 else 19.38)
        toc = 0.78 if (i % 14 != 0) else 1.35
        r25 = rho * (1.0 + 0.022 * (tc - 25.0))
        rhos.append(r25)
        if r25 >= 18.10 and toc <= 1.00:
            comp += 1
    return comp, round(sum(rhos) / len(rhos), 3)


def _ahu_oracles() -> tuple[int, float]:
    recs = [(60.0 / ((240.0 + (k % 4) * 20.0) * 0.72)) * math.log(85000.0 / 1000.0) for k in range(1, 21) if k % 10 != 0]
    return len(recs), round(max(recs), 3)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("upw_piping_toc_eng" in act), ("ahu_n2_purge_lead" in act)
    ws_a = workspace_map["upw_piping_toc_eng"]
    ws_b = workspace_map["ahu_n2_purge_lead"]
    hub = workspace_map["__shared_hub__"]
    svg_txt = html.unescape((hub / "turnaround_cpm.svg").read_text(errors="ignore")) if (hub / "turnaround_cpm.svg").is_file() else ""
    odt_txt = read_odt_plain_text(hub / "Cleanroom_Work_Permit.odt")
    xp = hub / "Fab_Outage_Schedule.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
    uno_st = inspect_live_uno_documents_readonly()
    ja = read_json_safe(ws_a / "upw_turnaround_audit.json")
    jb = read_json_safe(ws_b / "ahu_purge_audit.json")

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        v = ((evs.get("CriticalPath") or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get("CriticalPath") or {}).get(ref) or {}).get("value")

    u_comp, u_rho = _upw_oracles()
    a_cnt, a_rec = _ahu_oracles()
    uh = _f(_cv("B2"), -1.0)
    ah = _f(_cv("B3"), -1.0)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing upw_turnaround_audit.json"),
        ("a_svg_odt", UPW_PERMIT_CODE in svg_txt and UPW_PERMIT_CODE in odt_txt and ja.get("upw_permit_code") == UPW_PERMIT_CODE, 0.22, "Graphviz SVG or Writer permit missing UPW_PERMIT_CODE"),
        ("a_xlsx", uh >= UPW_FLOOR_H and str(_cv("C2") or "").upper() == "COMMITTED" and abs(_f(ja.get("upw_hours_committed")) - uh) <= 0.1, 0.22, "Calc B2 / JSON upw_hours mismatch"),
        ("a_rho_mean", abs(_f(ja.get("mean_rho25_mohm")) - u_rho) <= 0.02, 0.14, "mean_rho25_mohm mismatch"),
        ("a_fine_temp_comp_cnt", ja.get("f63_compliant_sample_count") == u_comp, 0.34, f"f63_compliant_sample_count != {u_comp} (missed 25C resistivity compensation)"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing ahu_purge_audit.json"),
        ("b_svg_odt", AHU_PERMIT_CODE in svg_txt and AHU_PERMIT_CODE in odt_txt and jb.get("ahu_permit_code") == AHU_PERMIT_CODE, 0.22, "Graphviz SVG or Writer permit missing AHU_PERMIT_CODE"),
        ("b_xlsx", ah >= AHU_FLOOR_H and str(_cv("C3") or "").upper() == "COMMITTED" and abs(_f(jb.get("ahu_hours_committed")) - ah) <= 0.1, 0.22, "Calc B3 / JSON ahu_hours mismatch"),
        ("b_cnt", jb.get("active_bay_count") == a_cnt, 0.14, "active_bay_count != 18"),
        ("b_fine_mixing_k", abs(_f(jb.get("max_bay_recovery_minutes")) - a_rec) <= 0.02, 0.34, f"max_bay_recovery_minutes != {a_rec} (missed k=0.72 non-ideal mixing factor)"),
    ]

    eff_u = uh if (has_a and uh > 0) else (UPW_FLOOR_H if not has_a else 999.0)
    eff_a = ah if (has_b and ah > 0) else (AHU_FLOOR_H if not has_b else 999.0)
    fl_ok = ((not has_a) or uh >= UPW_FLOOR_H) and ((not has_b) or ah >= AHU_FLOOR_H)
    uno_ok = all(not d.get("is_modified") for d in (uno_st.get("docs") or {}).values())
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_outage_345_cap", fl_ok and (eff_u + eff_a <= MAX_OUTAGE_HOURS), 0.12, f"Coupled outage {eff_u + eff_a:.1f} h exceeds {MAX_OUTAGE_HOURS:.1f} h!"),
        ("j_uno_sync", act_done and uno_ok, 0.10, "Open Calc or Writer holds unsaved dirty edits"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    dot_p = hub / "turnaround_cpm.dot"
    xp = hub / "Fab_Outage_Schedule.xlsx"
    odt_p = hub / "Cleanroom_Work_Permit.odt"

    with file_atomic_lock("nf219_shared"):
        shs = read_multisheet_xlsx(xp)
        b2 = float(((shs.get("CriticalPath") or {}).get("B2") or {}).get("value") or 0.0)
        c2 = str(((shs.get("CriticalPath") or {}).get("C2") or {}).get("value") or "PENDING")
        b3 = float(((shs.get("CriticalPath") or {}).get("B3") or {}).get("value") or 0.0)
        c3 = str(((shs.get("CriticalPath") or {}).get("C3") or {}).get("value") or "PENDING")
        dt = dot_p.read_text(encoding="utf-8")
        if role == "upw_piping_toc_eng":
            val = round(max(UPW_FLOOR_H, min(16.2, MAX_OUTAGE_HOURS - b3 - 0.3)) if c3 == "COMMITTED" else 16.2, 1)
            b2, c2 = val, "COMMITTED"
            dt = dt.replace("UPW_SANITIZE: PENDING", f"UPW_SANITIZE: {UPW_PERMIT_CODE} ({val}h)")
            sign = UPW_PERMIT_CODE
        else:
            val = round(max(AHU_FLOOR_H, min(17.6, MAX_OUTAGE_HOURS - b2 - 0.3)) if c2 == "COMMITTED" else 17.6, 1)
            b3, c3 = val, "COMMITTED"
            dt = dt.replace("AHU_N2_RECOMM: PENDING", f"AHU_N2_RECOMM: {AHU_PERMIT_CODE} ({val}h)")
            sign = AHU_PERMIT_CODE
        dot_p.write_text(dt, encoding="utf-8")
        subprocess.run(["dot", "-Tsvg", str(dot_p), "-o", str(hub / "turnaround_cpm.svg")], check=True, capture_output=True, timeout=20)
        update_single_sheet_xlsx(xp, "CriticalPath", [
            ["Phase", "Duration_Hours", "FAB12-300MM"],
            ["UPW_Sanitization_h", b2, c2],
            ["AHU_N2_Recommission_h", b3, c3],
            ["Total_Critical_Outage_h", ("=SUM(B2:B3)", round(b2 + b3, 1)), f"CAP_{MAX_OUTAGE_HOURS:.1f}"],
        ])
        cur_t = read_odt_plain_text(odt_p)
        lines = [ln for ln in cur_t.splitlines() if ln.strip() and sign not in ln]
        lines.append(f"[SIGN] {role}: {sign}")
        sync_uno_writer_text(odt_p, "\n".join(lines))
        reload_uno_pipe_documents([xp])

    if role == "upw_piping_toc_eng":
        u_comp, u_rho = _upw_oracles()
        write_json(ws / "upw_turnaround_audit.json", {
            "f63_compliant_sample_count": u_comp, "mean_rho25_mohm": u_rho,
            "upw_hours_committed": val, "upw_permit_code": UPW_PERMIT_CODE,
        })
    else:
        a_cnt, a_rec = _ahu_oracles()
        write_json(ws / "ahu_purge_audit.json", {
            "active_bay_count": a_cnt, "max_bay_recovery_minutes": a_rec,
            "ahu_hours_committed": val, "ahu_permit_code": AHU_PERMIT_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("upw_piping_toc_eng", workspace_map, port)
    solve_role("ahu_n2_purge_lead", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    update_single_sheet_xlsx(hub / "Fab_Outage_Schedule.xlsx", "CriticalPath", [
        ["Phase", "Duration_Hours", "FAB12-300MM"],
        ["UPW_Sanitization_h", 18.0, "COMMITTED"],
        ["AHU_N2_Recommission_h", 19.5, "COMMITTED"],
        ["Total_Critical_Outage_h", ("=SUM(B2:B3)", 37.5), "OVER_CAP"],
    ])

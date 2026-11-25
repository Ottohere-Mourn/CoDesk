"""NF2-16: Shared SQLite3 WAL + Optimistic Epoch & Live Calc — Hospital Cleanroom TPN Compounding Pump-Minute Coupling."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
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
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    sync_uno_calc_cells,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-16"
PORTAL_PORT = 19616

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Shared `SQLite3` WAL Optimistic-Epoch & Live Calc: USP `<797>` Renal TPN Osmolarity vs. Neonatal Lipid Pump-Minute Cap",
    "domain": "Hospital Sterile IV Parenteral Nutrition Pharmacy (`SQLite3` WAL + `LibreOffice Calc` + USP `<797>`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("renal_tpn_pharmacist", "sterile_lipid_iv_lead"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

USP_TPN_CODE = make_canary_code("USP797-TPN", "ca-po4-osm-1800")
USP_LIP_CODE = make_canary_code("USP729-LIP", "pfat5-smof-dehp")
SHIFT_PUMP_CAP_MIN = 840.0  # Fixed daily calibration flush = 45.0 min; TPN floor 375.0 + Lipid floor 395.0 + 45.0 = 815.0 <= 840.0; pref 415.0 + 435.0 + 45.0 = 895.0 > 840.0!
FLUSH_TARE_MIN = 45.0
TPN_FLOOR_MIN = 375.0
LIPID_FLOOR_MIN = 395.0


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Adult/Renal Central-Line TPN Compatibility & Compounder Reservation (`renal_tpn_pharmacist`)",
        "",
        "## Objective",
        f"Screen patient TPN orders in `{b}/workspace/orders/renal_tpn_orders.sqlite{b}` per `http://127.0.0.1:{PORTAL_PORT}/usp797` and `{b}/workspace/docs/SOP_Renal_TPN.pdf{b}`, commit your compounder reservation in `{b}/workspace/shared_docs/cleanroom_compounder.sqlite{b}` (incrementing `PRAGMA user_version` atomically) and `{b}/workspace/shared_docs/Cleanroom_Pump_Schedule.xlsx{b}` (open in Calc), and write `{b}/workspace/renal_tpn_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — USP `<729>` Lipid Emulsion PFAT5 Screening & Compounder Reservation (`sterile_lipid_iv_lead`)",
        "",
        "## Objective",
        f"Screen neonatal/ICU lipid orders in `{b}/workspace/orders/lipid_emulsion_orders.sqlite{b}` per `http://127.0.0.1:{PORTAL_PORT}/usp797` and `{b}/workspace/docs/SOP_Lipid_729.pdf{b}`, commit your compounder reservation in `{b}/workspace/shared_docs/cleanroom_compounder.sqlite{b}` (incrementing `PRAGMA user_version` atomically) and `{b}/workspace/shared_docs/Cleanroom_Pump_Schedule.xlsx{b}` (open in Calc), and write `{b}/workspace/lipid_emulsion_audit.json{b}`.",
    ])
    return {"renal_tpn_pharmacist": ta, "sterile_lipid_iv_lead": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["renal_tpn_pharmacist"]
    ws_b = workspace_map["sterile_lipid_iv_lead"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "orders", ws_a / "docs", ws_b / "orders", ws_b / "docs", hub):
        d.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(hub / "cleanroom_compounder.sqlite")) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA user_version=1")
        conn.execute("CREATE TABLE shift_allocations (line_id TEXT PRIMARY KEY, reserved_pump_min REAL, status TEXT)")
        conn.execute("INSERT INTO shift_allocations VALUES ('FLUSH_CALIB_TARE', 45.0, 'FIXED'), ('RENAL_TPN_LINE', 0.0, 'PENDING'), ('STERILE_LIPID_LINE', 0.0, 'PENDING')")
        conn.commit()

    write_multisheet_xlsx(hub / "Cleanroom_Pump_Schedule.xlsx", [
        ("PumpShift", [
            ["Channel_Line", "Pump_Minutes", "ISO5-HOOD-02"],
            ["Flush_Calibration_Min", FLUSH_TARE_MIN, "FIXED"],
            ["Renal_TPN_Min", 0.0, "PENDING"],
            ["Sterile_Lipid_Min", 0.0, "PENDING"],
            ["Total_Shift_Min", ("=SUM(B2:B4)", FLUSH_TARE_MIN), f"CAP_{SHIFT_PUMP_CAP_MIN:.1f}"],
        ]),
    ])

    # Role A: 120 TPN orders -> Osmolarity = (dextrose_g_l * 5.0 + amino_g_l * 10.0 + electrolytes_meq_l * 2.0);
    # reject peripheral orders (`line_access == 'PERIPHERAL'`) > 900 mOsm/L, central > 1800 mOsm/L, OR Ca_mEq_L * PO4_mmol_L > 45.0!
    with sqlite3.connect(str(ws_a / "orders/renal_tpn_orders.sqlite")) as conn:
        conn.execute("CREATE TABLE tpn_rx (rx_id INTEGER PRIMARY KEY, line_access TEXT, vol_l REAL, dex_g_l REAL, aa_g_l REAL, elec_meq_l REAL, ca_meq_l REAL, po4_mmol_l REAL)")
        for i in range(1, 121):
            acc = "PERIPHERAL" if (i % 6 == 0) else "CENTRAL_CVC"
            dex = 160.0 if (i % 6 == 0 and i % 12 != 0) else 110.0  # Peripheral with dex=160 -> osm > 900 -> reject!
            ca = 12.0 if (i % 15 == 0) else 6.0
            po4 = 4.5 if (i % 15 == 0) else 5.0  # 12*4.5 = 54 > 45 -> Ca-PO4 precipitation reject!
            conn.execute("INSERT INTO tpn_rx VALUES (?,?,?,?,?,?,?,?)", (i, acc, 1.8, dex, 45.0, 65.0, ca, po4))
        conn.execute("CREATE TABLE usp797_osmolarity_limits (peripheral_max_mosm_l REAL, central_max_mosm_l REAL, ca_po4_solubility_max REAL, Osm_formula TEXT)")
        conn.execute("INSERT INTO usp797_osmolarity_limits VALUES (900.0, 1800.0, 45.0, 'dex_g_l*5.0 + aa_g_l*10.0 + elec_meq_l*2.0')")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_Renal_TPN.pdf", "SOP-PHARM-1616A: TPN Calcium-Phosphate & Osmolarity Screening", [
        ("1. TPN Clinical Screening & Pump Reservation", [
            f"1.1 Screen /workspace/orders/renal_tpn_orders.sqlite against all compatibility and access-route osmolarity limits in usp797_osmolarity_limits.",
            f"1.2 Reserve renal_tpn_min (>={TPN_FLOOR_MIN} min, preferred 392.0 min, within {SHIFT_PUMP_CAP_MIN} min total shift cap) in /workspace/shared_docs/cleanroom_compounder.sqlite (RENAL_TPN_LINE, status='COMMITTED', increment PRAGMA user_version) and Cleanroom_Pump_Schedule.xlsx (B3, C3='COMMITTED').",
        ]),
        ("2. JSON Schema (/workspace/renal_tpn_audit.json)", [
            "Keys: approved_tpn_bag_count (int), precip_or_osm_rejected_count (int), mean_approved_osmolarity_mosm_l (float, 2 dec), renal_pump_min_committed (float, 1 dec), usp_tpn_code (str).",
        ]),
    ])

    # Role B: 110 lipid bags -> USP <729> PFAT5 <= 0.050% AND add +18.0 mL DEHP-free EVA priming dead-volume overfill per approved bag (in SQLite)!
    with sqlite3.connect(str(ws_b / "orders/lipid_emulsion_orders.sqlite")) as conn:
        conn.execute("CREATE TABLE lipid_rx (bag_id INTEGER PRIMARY KEY, patient_dose_ml REAL, lot_pfat5_pct REAL, emulsion_conc_pct REAL)")
        for i in range(1, 111):
            pfat = 0.068 if (i % 11 == 0) else 0.028
            conn.execute("INSERT INTO lipid_rx VALUES (?,?,?,?)", (i, 220.0 + (i % 5) * 15.0, pfat, 20.0))
        conn.execute("CREATE TABLE tubing_overfill_policy (usp729_max_pfat5_pct REAL, dehp_free_priming_overfill_ml_per_bag REAL)")
        conn.execute("INSERT INTO tubing_overfill_policy VALUES (0.050, 18.0)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_Lipid_729.pdf", "SOP-PHARM-1616B: USP <729> Globule PFAT5 & Priming Overfill", [
        ("1. Lipid Lot Screening & Pump Reservation", [
            f"1.1 Reject bags exceeding USP <729> PFAT5 limit in /workspace/orders/lipid_emulsion_orders.sqlite and compute total compounded 20% lipid volume mL including per-bag tubing priming overfill from SQLite.",
            f"1.2 Reserve sterile_lipid_min (>={LIPID_FLOOR_MIN} min, preferred 412.0 min, within {SHIFT_PUMP_CAP_MIN} min total shift cap) in cleanroom_compounder.sqlite (STERILE_LIPID_LINE, status='COMMITTED', increment PRAGMA user_version) and Cleanroom_Pump_Schedule.xlsx (B4, C4='COMMITTED').",
        ]),
        ("2. JSON Schema (/workspace/lipid_emulsion_audit.json)", [
            "Keys: approved_lipid_bag_count (int), pfat5_quarantined_count (int), total_compounded_volume_ml (float, 1 dec), lipid_pump_min_committed (float, 1 dec), usp_lipid_code (str).",
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
        f"<h2>USP &lt;797&gt; / &lt;729&gt; ISO-5 Automated Compounder Control</h2>"
        f"<p>Shift Ceiling: <code>45.0 (flush) + renal_tpn_min + sterile_lipid_min &lt;= {SHIFT_PUMP_CAP_MIN:.1f} pump-minutes</code></p>"
        f"<p>USP TPN Release Code: <strong style='color:#4ade80'>{USP_TPN_CODE}</strong> | USP Lipid Release Code: <strong style='color:#38bdf8'>{USP_LIP_CODE}</strong></p>"
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
                raw = b"<html><body><script>location.href='/usp797';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"tpn_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "tpn_sso" not in c or c["tpn_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    launch_libreoffice_uno_natural([hub / "Cleanroom_Pump_Schedule.xlsx"])
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def _tpn_oracle() -> tuple[int, int, float]:
    app_osm = []
    rej = 0
    for i in range(1, 121):
        acc = "PERIPHERAL" if (i % 6 == 0) else "CENTRAL_CVC"
        dex = 160.0 if (i % 6 == 0 and i % 12 != 0) else 110.0
        ca = 12.0 if (i % 15 == 0) else 6.0
        po4 = 4.5 if (i % 15 == 0) else 5.0
        osm = dex * 5.0 + 45.0 * 10.0 + 65.0 * 2.0
        if (ca * po4 > 45.0) or (acc == "PERIPHERAL" and osm > 900.0) or (osm > 1800.0):
            rej += 1
        else:
            app_osm.append(osm)
    return len(app_osm), rej, round(sum(app_osm) / len(app_osm), 2)


def _lip_oracle() -> tuple[int, int, float]:
    vols = [220.0 + (i % 5) * 15.0 + 18.0 for i in range(1, 111) if i % 11 != 0]
    return len(vols), 110 - len(vols), round(sum(vols), 1)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("renal_tpn_pharmacist" in act), ("sterile_lipid_iv_lead" in act)
    ws_a = workspace_map["renal_tpn_pharmacist"]
    ws_b = workspace_map["sterile_lipid_iv_lead"]
    hub = workspace_map["__shared_hub__"]
    ja = read_json_safe(ws_a / "renal_tpn_audit.json")
    jb = read_json_safe(ws_b / "lipid_emulsion_audit.json")
    xp = hub / "Cleanroom_Pump_Schedule.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
    uno_st = inspect_live_uno_documents_readonly()

    with sqlite3.connect(str(hub / "cleanroom_compounder.sqlite")) as conn:
        u_ver = int(conn.execute("PRAGMA user_version").fetchone()[0])
        amap = {r[0]: (float(r[1]), str(r[2])) for r in conn.execute("SELECT line_id, reserved_pump_min, status FROM shift_allocations")}
    tpn_m, tpn_s = amap.get("RENAL_TPN_LINE", (-1.0, ""))
    lip_m, lip_s = amap.get("STERILE_LIPID_LINE", (-1.0, ""))

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        v = ((evs.get("PumpShift") or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get("PumpShift") or {}).get(ref) or {}).get("value")

    app_n, rej_n, mu_osm = _tpn_oracle()
    l_app, l_rej, tot_v = _lip_oracle()

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing renal_tpn_audit.json"),
        ("a_db_xlsx", tpn_m >= TPN_FLOOR_MIN and tpn_s == "COMMITTED" and abs(_f(_cv("B3")) - tpn_m) <= 0.2 and u_ver >= 2, 0.24, "SQLite/Calc RENAL_TPN_LINE or PRAGMA user_version not updated"),
        ("a_code_osm", ja.get("usp_tpn_code") == USP_TPN_CODE and abs(_f(ja.get("mean_approved_osmolarity_mosm_l")) - mu_osm) <= 1.0, 0.22, "usp_tpn_code or mean osmolarity mismatch"),
        ("a_fine_periph_capo4", ja.get("approved_tpn_bag_count") == app_n and ja.get("precip_or_osm_rejected_count") == rej_n, 0.46, f"TPN screening {ja.get('approved_tpn_bag_count')}/{app_n} missed peripheral 900 mOsm/L or Ca*PO4 > 45 rule"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing lipid_emulsion_audit.json"),
        ("b_db_xlsx", lip_m >= LIPID_FLOOR_MIN and lip_s == "COMMITTED" and abs(_f(_cv("B4")) - lip_m) <= 0.2 and u_ver >= 2, 0.24, "SQLite/Calc STERILE_LIPID_LINE or PRAGMA user_version not updated"),
        ("b_pfat_code", jb.get("approved_lipid_bag_count") == l_app and jb.get("pfat5_quarantined_count") == l_rej and jb.get("usp_lipid_code") == USP_LIP_CODE, 0.22, "PFAT5 quarantine count or code mismatch"),
        ("b_fine_overfill_vol", abs(_f(jb.get("total_compounded_volume_ml")) - tot_v) <= 1.0, 0.46, f"total_compounded_volume_ml != {tot_v} (missed +18.0 mL/bag DEHP-free priming overfill)"),
    ]

    eff_t = tpn_m if (has_a and tpn_m > 0) else (TPN_FLOOR_MIN if not has_a else 9999.0)
    eff_l = lip_m if (has_b and lip_m > 0) else (LIPID_FLOOR_MIN if not has_b else 9999.0)
    fl_ok = ((not has_a) or tpn_m >= TPN_FLOOR_MIN) and ((not has_b) or lip_m >= LIPID_FLOOR_MIN)
    calc_ok = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Cleanroom_Pump_Schedule.xlsx" in u_url:
            calc_ok = not u_doc.get("is_modified")
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_shift_840_cap", fl_ok and (FLUSH_TARE_MIN + eff_t + eff_l <= SHIFT_PUMP_CAP_MIN), 0.14, f"Coupled pump time {FLUSH_TARE_MIN + eff_t + eff_l:.1f} min exceeds {SHIFT_PUMP_CAP_MIN:.1f} min!"),
        ("j_sum_uno_sync", act_done and calc_ok and "SUM(B2:B4)" in str(((shs.get("PumpShift") or {}).get("B5") or {}).get("formula") or "").upper(), 0.10, "Open Calc out-of-sync or B5 =SUM(B2:B4) lost"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    db_p = hub / "cleanroom_compounder.sqlite"
    xp = hub / "Cleanroom_Pump_Schedule.xlsx"

    with file_atomic_lock("nf216_shared"):
        with sqlite3.connect(str(db_p)) as conn:
            uv = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if role == "renal_tpn_pharmacist":
                lr = conn.execute("SELECT reserved_pump_min, status FROM shift_allocations WHERE line_id='STERILE_LIPID_LINE'").fetchone()
                l_cur = float(lr[0]) if lr and lr[1] == "COMMITTED" else 0.0
                val = round(max(TPN_FLOOR_MIN, min(388.0, SHIFT_PUMP_CAP_MIN - FLUSH_TARE_MIN - l_cur - 2.0)) if l_cur > 0 else 388.0, 1)
                conn.execute("UPDATE shift_allocations SET reserved_pump_min=?, status='COMMITTED' WHERE line_id='RENAL_TPN_LINE'", (val,))
            else:
                tr = conn.execute("SELECT reserved_pump_min, status FROM shift_allocations WHERE line_id='RENAL_TPN_LINE'").fetchone()
                t_cur = float(tr[0]) if tr and tr[1] == "COMMITTED" else 0.0
                val = round(max(LIPID_FLOOR_MIN, min(402.0, SHIFT_PUMP_CAP_MIN - FLUSH_TARE_MIN - t_cur - 2.0)) if t_cur > 0 else 402.0, 1)
                conn.execute("UPDATE shift_allocations SET reserved_pump_min=?, status='COMMITTED' WHERE line_id='STERILE_LIPID_LINE'", (val,))
            conn.execute(f"PRAGMA user_version={uv + 1}")
            conn.commit()

        shs = read_multisheet_xlsx(xp)
        b3 = float(((shs.get("PumpShift") or {}).get("B3") or {}).get("value") or 0.0)
        c3 = str(((shs.get("PumpShift") or {}).get("C3") or {}).get("value") or "PENDING")
        b4 = float(((shs.get("PumpShift") or {}).get("B4") or {}).get("value") or 0.0)
        c4 = str(((shs.get("PumpShift") or {}).get("C4") or {}).get("value") or "PENDING")
        if role == "renal_tpn_pharmacist":
            sync_uno_calc_cells(xp, "PumpShift", {"B3": val, "C3": "COMMITTED", "B5": "=SUM(B2:B4)"})
        else:
            sync_uno_calc_cells(xp, "PumpShift", {"B4": val, "C4": "COMMITTED", "B5": "=SUM(B2:B4)"})

    if role == "renal_tpn_pharmacist":
        app_n, rej_n, mu_osm = _tpn_oracle()
        write_json(ws / "renal_tpn_audit.json", {
            "approved_tpn_bag_count": app_n, "precip_or_osm_rejected_count": rej_n,
            "mean_approved_osmolarity_mosm_l": mu_osm, "renal_pump_min_committed": val, "usp_tpn_code": USP_TPN_CODE,
        })
    else:
        l_app, l_rej, tot_v = _lip_oracle()
        write_json(ws / "lipid_emulsion_audit.json", {
            "approved_lipid_bag_count": l_app, "pfat5_quarantined_count": l_rej,
            "total_compounded_volume_ml": tot_v, "lipid_pump_min_committed": val, "usp_lipid_code": USP_LIP_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("renal_tpn_pharmacist", workspace_map, port)
    solve_role("sterile_lipid_iv_lead", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    with sqlite3.connect(str(hub / "cleanroom_compounder.sqlite")) as conn:
        conn.execute("UPDATE shift_allocations SET reserved_pump_min=415.0 WHERE line_id='RENAL_TPN_LINE'")
        conn.execute("UPDATE shift_allocations SET reserved_pump_min=435.0 WHERE line_id='STERILE_LIPID_LINE'")
        conn.commit()

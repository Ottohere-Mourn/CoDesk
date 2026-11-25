"""AW-17: Live LibreOffice Calc & Writer Solar Project Finance — Coupled DSCR Covenant [1.420, 1.460]."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import shutil
import sqlite3
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    cell_float,
    evaluate_xlsx_isolated,
    launch_studio_app,
    read_json_safe,
    read_odt_text,
    resource_lock,
    update_single_sheet_xlsx,
    write_json,
    write_multisheet_xlsx,
    write_odt_document,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-17",
    "slug": "libreoffice_coupled_dscr_dealroom",
    "title": "Solar Project Finance Closing in Live LibreOffice Calc & Writer: P90 CFADS Reserve vs. Debt Sculpting",
    "domain": "Project Finance & Coupled Covenant Modeling (LibreOffice Calc + Writer + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19617,
    "roles": ("cash_sweep_modeler", "debt_sculpting_lead"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

TERM_CODE = "SOLAR-PF-2026-808"
# Quarter rows: (qtr, p50_mwh, p90_haircut_pct, ppa_usd_mwh, grid_curtail_pct, fixed_om_musd)
SOLAR_QTRS = [
    ("2026-Q1", 112000.0, 8.0, 58.0, 2.5, 1.65),
    ("2026-Q2", 148000.0, 8.0, 58.0, 3.0, 1.70),
    ("2026-Q3", 154000.0, 8.0, 58.0, 3.5, 1.75),
    ("2026-Q4", 106000.0, 8.0, 58.0, 2.0, 1.68),
]
# Let's check exact Base_CFADS from SOLAR_QTRS or clean exact constants:
# We also include merchant_ancillary_musd adjustment in SQLite so Base_CFADS = 18.000 MUSD!

TICKET_A = (
    "# Work Order — P90 Cash-Flow & Inverter Reserve Modeler (`cash_sweep_modeler`)\n\n"
    "Reconcile annual P90 Cash Flow Available for Debt Service (`CFADS`) in `/workspace/proj_fin` and configure the Inverter Maintenance Reserve Tier inside the live **LibreOffice Calc** and **LibreOffice Writer** documents open on the desktop:\n\n"
    "1. Read `/workspace/proj_fin/specs/Lender_Covenant_Schedule.pdf`, query `/workspace/proj_fin/solar_plant_2026.sqlite`, and inspect the **Project Finance Portal** in Chromium (`http://127.0.0.1:19617`, `Senior Term Sheet` tab — ignore the Mezzanine distractor tab!).\n"
    "2. Compute annual P90 `pre_reserve_cfads_musd` (3 decimals), then choose between approved Inverter Reserve `Tier_1` (`$1.200M/yr`) and `Tier_2` (`$2.400M/yr`) so that `Covenant_Summary!B4` (`DSCR = Net_CFADS_MUSD / Annual_Debt_Service_MUSD`) in the open **LibreOffice Calc** workbook (`Solar_Project_Finance.xlsx`) lands strictly within **`[1.420, 1.460]`**!\n"
    "3. In the open **LibreOffice Calc** window (`Solar_Project_Finance.xlsx`), enter `pre_reserve_cfads_musd` in `CFADS_Schedule!B2`, your selected `reserve_tier_musd` in `CFADS_Schedule!B3`, and resulting `net_cfads_musd` in `Covenant_Summary!B2`, then save (`Ctrl+S`).\n"
    "4. Record `term_code` and `net_cfads_musd` in the open **LibreOffice Writer** window (`Credit_Committee_TermSheet.odt`, `Ctrl+S`), and write `/workspace/proj_fin/cfads_audit.json` (`term_code`, `pre_reserve_cfads_musd`, `selected_reserve_musd`, `net_cfads_musd`, `resulting_dscr`).\n"
)

TICKET_B = (
    "# Work Order — Senior Debt Sculpting & Hedging Lead (`debt_sculpting_lead`)\n\n"
    "Reconcile swap-hedged senior debt service options in `/workspace/proj_fin` and configure the Senior Amortization Schedule inside the live **LibreOffice Calc** and **LibreOffice Writer** documents open on the desktop:\n\n"
    "1. Read `/workspace/proj_fin/specs/Lender_Covenant_Schedule.pdf`, query `/workspace/proj_fin/solar_plant_2026.sqlite` (`debt_tranches`), and inspect the **Project Finance Portal** in Chromium (`http://127.0.0.1:19617`, `Swap Rate & Amortization Options` tab).\n"
    "2. Compute annual debt service (`principal + hedged_interest + commitment_fee`, 3 decimals) for both `Schedule_Standard` and `Schedule_Sculpted`, and select the schedule that places `Covenant_Summary!B4` (`DSCR = Net_CFADS_MUSD / Annual_Debt_Service_MUSD`) in the open **LibreOffice Calc** workbook (`Solar_Project_Finance.xlsx`) strictly within **`[1.420, 1.460]`**!\n"
    "3. In the open **LibreOffice Calc** window (`Solar_Project_Finance.xlsx`), enter `standard_ds_musd` in `Debt_Service!B2`, `sculpted_ds_musd` in `Debt_Service!B3`, and your selected `annual_debt_service_musd` in `Covenant_Summary!B3`, then save (`Ctrl+S`).\n"
    "4. Record `term_code` and your selected `annual_debt_service_musd` in the open **LibreOffice Writer** window (`Credit_Committee_TermSheet.odt`, `Ctrl+S`), and write `/workspace/proj_fin/debt_sculpt_audit.json` (`term_code`, `standard_ds_musd`, `sculpted_ds_musd`, `selected_debt_service_musd`, `resulting_dscr`).\n"
)


def compute_aw17_base() -> dict[str, float]:
    rev = 0.0
    om = 0.0
    for _q, p50, h_pct, ppa, curt_pct, fom in SOLAR_QTRS:
        net_mwh = p50 * (1.0 - h_pct / 100.0) * (1.0 - curt_pct / 100.0)
        rev += (net_mwh * ppa) / 1e6
        om += fom
    # Capacity payment + REC contract = +$2.478M -> brings pre_reserve_cfads cleanly near 18.000 MUSD
    ancillary_musd = round(18.000 - (rev - om), 4)
    pre_cfads = round(rev - om + ancillary_musd, 3)  # Exact 18.000 MUSD!
    # Debt options: Principal $140.0M; swap-hedged all-in coupon = 4.50% ($6.300M interest) + $0.150M agency fee = $6.450M interest/fees
    # Standard principal = $5.100M -> DS = 11.550 MUSD; Sculpted principal = $4.350M -> DS = 10.800 MUSD!
    return {
        "ancillary_musd": ancillary_musd,
        "pre_reserve_cfads_musd": pre_cfads,  # 18.000
        "tier1_net_cfads": round(pre_cfads - 1.200, 3),  # 16.800
        "tier2_net_cfads": round(pre_cfads - 2.400, 3),  # 15.600
        "standard_ds_musd": 11.550,
        "sculpted_ds_musd": 10.800,
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    pf = workspace_root / "shared" / "proj_fin"
    (pf / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)
    base = compute_aw17_base()

    db_p = pf / "solar_plant_2026.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE quarterly_generation (quarter TEXT PRIMARY KEY, p50_gross_mwh REAL, p90_haircut_pct REAL, ppa_price_usd_mwh REAL, curtailment_pct REAL, fixed_om_musd REAL)")
    con.executemany("INSERT INTO quarterly_generation VALUES (?,?,?,?,?,?)", SOLAR_QTRS)
    con.execute("CREATE TABLE contracted_ancillary (contract_id TEXT PRIMARY KEY, annual_revenue_musd REAL)")
    con.execute("INSERT INTO contracted_ancillary VALUES ('REC-CAP-2026', ?)", (base["ancillary_musd"],))
    con.execute("CREATE TABLE debt_tranches (schedule_name TEXT PRIMARY KEY, facility_principal_musd REAL, annual_principal_repay_musd REAL, agency_fee_musd REAL)")
    con.executemany("INSERT INTO debt_tranches VALUES (?,?,?,?)", [("Schedule_Standard", 140.0, 5.100, 0.150), ("Schedule_Sculpted", 140.0, 4.350, 0.150)])
    con.commit()
    con.close()

    # Initial v0 has B2=15.600 (Tier_2) and B3=11.550 (Standard) -> DSCR = 1.351 (< 1.420 breach!)
    write_multisheet_xlsx(
        seed / "Solar_Project_Finance.xlsx",
        [
            ("CFADS_Schedule", [["Item", "MUSD"], ["Pre_Reserve_CFADS_MUSD", 0.0], ["Selected_Reserve_MUSD", 2.400]]),
            ("Debt_Service", [["Schedule", "MUSD"], ["Schedule_Standard_DS_MUSD", 0.0], ["Schedule_Sculpted_DS_MUSD", 0.0]]),
            ("Covenant_Summary", [["Metric", "Value"], ["Net_CFADS_MUSD", 15.600], ["Annual_Debt_Service_MUSD", 11.550], ["Closing_DSCR_x", ("=ROUND(B2/B3,3)", 1.351)]]),
        ],
    )
    write_odt_document(seed / "Credit_Committee_TermSheet.odt", "Solar PF Credit Committee Term Sheet", [("Approvals", ["Status: COVENANT_BREACH_V0"])])

    write_pdf_manual(
        pf / "specs" / "Lender_Covenant_Schedule.pdf",
        "Solar Project Finance Closing & DSCR Sizing Covenant",
        [
            ("1. P90 CFADS & Inverter Reserve Tiers", ["Net quarterly MWh = p50_gross_mwh * (1 - p90_haircut_pct/100) * (1 - curtailment_pct/100). Sum quarterly PPA revenue minus fixed_om_musd plus contracted_ancillary.annual_revenue_musd to get pre_reserve_cfads_musd. Approved Inverter Reserve options: Tier_1 = $1.200M/yr or Tier_2 = $2.400M/yr."]),
            ("2. Hedged Senior Debt Service & Tight DSCR Band [1.420, 1.460]", ["All-in hedged interest equals facility_principal_musd * hedged_swap_coupon (from Portal), plus annual_principal_repay_musd and agency_fee_musd. Closing_DSCR_x = round(Net_CFADS_MUSD / Annual_Debt_Service_MUSD, 3) on Covenant_Summary!B4 MUST lie inside [1.420, 1.460] (below 1.420 breaches senior coverage; above 1.460 violates sponsor leverage efficiency)."]),
        ],
    )
    (tickets_root / "cash_sweep_modeler").mkdir(parents=True, exist_ok=True)
    (tickets_root / "debt_sculpting_lead").mkdir(parents=True, exist_ok=True)
    (tickets_root / "cash_sweep_modeler" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "debt_sculpting_lead" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "mezz_distractor", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw17_sess" in ck) and (ck["aw17_sess"].value == tok)

        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", hdrs: list[tuple[str, str]] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for hk, hv in (hdrs or []):
                self.send_header(hk, hv)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/health":
                self._send(200, b'{"ok":true}', "application/json")
                return
            if parsed.path == "/auth":
                if (qs.get("token") or [""])[0] == tok:
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw17_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Project Finance Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["mezz_distractor"])[0]
                with lock:
                    if t in ("mezz_distractor", "senior", "swap") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "mezz_distractor":
                body = "<h2>Subordinated Mezzanine Note (DO NOT USE FOR SENIOR CLOSING)</h2><p>PIK Coupon: 9.75%</p>"
            elif cur == "senior":
                body = f"<h2>Senior Term Sheet ({TERM_CODE})</h2><p>Mandatory Closing DSCR Window: <code>[1.420, 1.460]</code> | Inverter Reserve Tiers: <code>$1.200M</code> or <code>$2.400M</code></p>"
            else:
                body = f"<h2>Swap Rate &amp; Amortization ({TERM_CODE})</h2><p>All-In Swap-Hedged Senior Coupon: <code>4.50% (0.045)</code> on $140.0M facility</p>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Solar PF Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:22px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 15px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>Solar Project Finance Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=mezz_distractor">Mezzanine Note</a><a href="/tab?id=senior">Senior Term Sheet</a><a href="/tab?id=swap">Swap Rate &amp; Amortization Options</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    boot_studio_browser(state_dir, window_size=(1160, 760))
    seed = workspace_root / "_desk_seed"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "Solar_Project_Finance.xlsx", sp / "Solar_Project_Finance.xlsx")
    shutil.copy2(seed / "Credit_Committee_TermSheet.odt", sp / "Credit_Committee_TermSheet.odt")
    launch_studio_app(
        "nohup libreoffice --norestore --nologo --nofirststartwizard "
        "'/srv/studio_project/Solar_Project_Finance.xlsx' '/srv/studio_project/Credit_Committee_TermSheet.odt' "
        ">/tmp/aw17_lo.log 2>&1 </dev/null &",
        wait_s=3.0,
    )


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    pf = workspace_root / "shared" / "proj_fin"
    sp = Path("/srv/studio_project")
    xlsx_p = sp / "Solar_Project_Finance.xlsx"
    odt_p = sp / "Credit_Committee_TermSheet.odt"
    b = compute_aw17_base()
    if role == "cash_sweep_modeler":
        if cooperative:
            with resource_lock("aw17_lo"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                ds_cur = cell_float(bk, "Covenant_Summary", "B3") or 11.550
                res_sel = 2.400 if abs(ds_cur - 10.800) < 0.2 else 1.200
                net_c = round(b["pre_reserve_cfads_musd"] - res_sel, 3)
                dscr = round(net_c / ds_cur, 3)
                update_single_sheet_xlsx(xlsx_p, "CFADS_Schedule", [["Item", "MUSD"], ["Pre_Reserve_CFADS_MUSD", b["pre_reserve_cfads_musd"]], ["Selected_Reserve_MUSD", res_sel]])
                update_single_sheet_xlsx(xlsx_p, "Covenant_Summary", [["Metric", "Value"], ["Net_CFADS_MUSD", net_c], ["Annual_Debt_Service_MUSD", ds_cur], ["Closing_DSCR_x", ("=ROUND(B2/B3,3)", dscr)]])
                prev = [ln for ln in read_odt_text(odt_p).splitlines() if "DebtService:" in ln]
                write_odt_document(odt_p, "Solar PF Credit Committee Term Sheet", [("Approvals", [f"{TERM_CODE} | NetCFADS: {net_c:.3f}", *prev])])
        else:
            res_sel, net_c, dscr = 1.200, 16.800, 1.455
            update_single_sheet_xlsx(xlsx_p, "CFADS_Schedule", [["Item", "MUSD"], ["Pre_Reserve_CFADS_MUSD", b["pre_reserve_cfads_musd"]], ["Selected_Reserve_MUSD", res_sel]])
            bk = evaluate_xlsx_isolated(xlsx_p)
            ds_cur = cell_float(bk, "Covenant_Summary", "B3") or 11.550
            update_single_sheet_xlsx(xlsx_p, "Covenant_Summary", [["Metric", "Value"], ["Net_CFADS_MUSD", net_c], ["Annual_Debt_Service_MUSD", ds_cur], ["Closing_DSCR_x", ("=ROUND(B2/B3,3)", round(net_c / ds_cur, 3))]])
        write_json(pf / "cfads_audit.json", {"term_code": TERM_CODE, "pre_reserve_cfads_musd": b["pre_reserve_cfads_musd"], "selected_reserve_musd": res_sel, "net_cfads_musd": net_c, "resulting_dscr": dscr})
    elif role == "debt_sculpting_lead":
        if cooperative:
            with resource_lock("aw17_lo"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                cf_cur = cell_float(bk, "Covenant_Summary", "B2") or 15.600
                ds_sel = 11.550 if abs(cf_cur - 16.800) < 0.2 else 10.800
                dscr = round(cf_cur / ds_sel, 3)
                update_single_sheet_xlsx(xlsx_p, "Debt_Service", [["Schedule", "MUSD"], ["Schedule_Standard_DS_MUSD", 11.550], ["Schedule_Sculpted_DS_MUSD", 10.800]])
                update_single_sheet_xlsx(xlsx_p, "Covenant_Summary", [["Metric", "Value"], ["Net_CFADS_MUSD", cf_cur], ["Annual_Debt_Service_MUSD", ds_sel], ["Closing_DSCR_x", ("=ROUND(B2/B3,3)", dscr)]])
                prev = [ln for ln in read_odt_text(odt_p).splitlines() if "NetCFADS:" in ln]
                write_odt_document(odt_p, "Solar PF Credit Committee Term Sheet", [("Approvals", [*prev, f"{TERM_CODE} | DebtService: {ds_sel:.3f}"])])
        else:
            ds_sel, dscr = 10.800, 1.444
            update_single_sheet_xlsx(xlsx_p, "Debt_Service", [["Schedule", "MUSD"], ["Schedule_Standard_DS_MUSD", 11.550], ["Schedule_Sculpted_DS_MUSD", 10.800]])
            bk = evaluate_xlsx_isolated(xlsx_p)
            cf_cur = cell_float(bk, "Covenant_Summary", "B2") or 15.600
            update_single_sheet_xlsx(xlsx_p, "Covenant_Summary", [["Metric", "Value"], ["Net_CFADS_MUSD", cf_cur], ["Annual_Debt_Service_MUSD", ds_sel], ["Closing_DSCR_x", ("=ROUND(B2/B3,3)", round(cf_cur / ds_sel, 3))]])
        write_json(pf / "debt_sculpt_audit.json", {"term_code": TERM_CODE, "standard_ds_musd": 11.550, "sculpted_ds_musd": 10.800, "selected_debt_service_musd": ds_sel, "resulting_dscr": dscr})


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    """Gate 4: both pick their solo adjustments (16.800 and 10.800), pushing DSCR to 1.556 > 1.460!"""
    solve_role("cash_sweep_modeler", workspace_root, cooperative=False)
    solve_role("debt_sculpting_lead", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "cash_sweep_modeler", workspace_root, True)
        fb = pool.submit(solve_role, "debt_sculpting_lead", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    pf = workspace_root / "shared" / "proj_fin"
    sp = Path("/srv/studio_project")
    b = compute_aw17_base()
    ja = read_json_safe(pf / "cfads_audit.json")
    jb = read_json_safe(pf / "debt_sculpt_audit.json")
    book = evaluate_xlsx_isolated(sp / "Solar_Project_Finance.xlsx")
    odt_txt = read_odt_text(sp / "Credit_Committee_TermSheet.odt")

    def _close(v: Any, exp: float, tol: float = 0.02) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    b2_cf = cell_float(book, "Covenant_Summary", "B2")
    b3_ds = cell_float(book, "Covenant_Summary", "B3")
    b4_dscr = cell_float(book, "Covenant_Summary", "B4")
    dscr_in_band = (b4_dscr is not None) and (1.420 <= float(b4_dscr) <= 1.460)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_code", ja.get("term_code") == TERM_CODE, 1.0, "term_code mismatch"),
        ("a_pre_cfads", _close(ja.get("pre_reserve_cfads_musd"), b["pre_reserve_cfads_musd"]), 1.8, "pre_reserve_cfads_musd mismatch (18.000)"),
        ("a_calc_pre", _close(cell_float(book, "CFADS_Schedule", "B2"), b["pre_reserve_cfads_musd"], 0.03), 1.8, "Live Calc CFADS_Schedule!B2 not saved"),
        ("a_calc_cov_b2", b2_cf is not None and (abs(b2_cf - 16.800) <= 0.03 or abs(b2_cf - 15.600) <= 0.03) and _close(ja.get("net_cfads_musd"), b2_cf, 0.03), 1.8, "Covenant_Summary!B2 mismatch"),
        ("a_dscr_band", dscr_in_band, 2.2, f"Live Calc Closing_DSCR_x ({b4_dscr}) outside [1.420, 1.460]"),
        ("a_writer", TERM_CODE in odt_txt and ("16.8" in odt_txt or "15.6" in odt_txt), 1.6, "Live Writer missing CFADS approval"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_code", jb.get("term_code") == TERM_CODE, 1.0, "term_code mismatch"),
        ("b_ds_opts", _close(jb.get("standard_ds_musd"), 11.550) and _close(jb.get("sculpted_ds_musd"), 10.800), 1.8, "standard_ds_musd / sculpted_ds_musd mismatch"),
        ("b_calc_ds", _close(cell_float(book, "Debt_Service", "B2"), 11.550, 0.03) and _close(cell_float(book, "Debt_Service", "B3"), 10.800, 0.03), 1.8, "Live Calc Debt_Service!B2:B3 not saved"),
        ("b_calc_cov_b3", b3_ds is not None and (abs(b3_ds - 11.550) <= 0.03 or abs(b3_ds - 10.800) <= 0.03) and _close(jb.get("selected_debt_service_musd"), b3_ds, 0.03), 1.8, "Covenant_Summary!B3 mismatch"),
        ("b_dscr_band", dscr_in_band, 2.2, f"Live Calc Closing_DSCR_x ({b4_dscr}) outside [1.420, 1.460]"),
        ("b_writer", TERM_CODE in odt_txt and ("11.55" in odt_txt or "10.8" in odt_txt), 1.6, "Live Writer missing Debt Service approval"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_coupled_dscr_covenant_satisfied",
            dscr_in_band,
            2.5,
            f"Uncoordinated dual-role adjustments pushed Closing_DSCR_x to {b4_dscr} outside [1.420, 1.460]",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"cash_sweep_modeler": TICKET_A, "debt_sculpting_lead": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

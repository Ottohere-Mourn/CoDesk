"""AW-13: Pure-GUI Multi-Sheet LibreOffice Calc & Writer Consolidated Close (No CLI Studio Mount)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    cell_float,
    cell_formula,
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
    "id": "AW-13",
    "slug": "libreoffice_14cell_cfo_ledger",
    "title": "Consolidated FY26 Close in Live LibreOffice Calc & Writer: 8-Cell Multi-Sheet SaaS Bookings vs. COGS/Opex",
    "domain": "Enterprise FP&A & Live Spreadsheet/Document Authoring (LibreOffice Calc + Writer + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19613,
    "roles": ("saas_rev_lead", "cogs_opex_lead"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

FX_RATES = {"USD": 1.0, "EUR": 1.08, "GBP": 1.26, "CAD": 0.74}
RESOLUTION_CODE = "BOARD-FY26-RES-704"

# (region, currency, gross_bookings_local, multi_yr_prepay_disc_pct, churn_clawback_local)
SAAS_REGIONS = [
    ("NA_Enterprise", "USD", 6400000.0, 5.0, 220000.0),
    ("NA_MidMarket", "CAD", 3500000.0, 4.0, 150000.0),
    ("EMEA_DACH", "EUR", 4200000.0, 6.0, 180000.0),
    ("EMEA_UK", "GBP", 2600000.0, 5.0, 95000.0),
    ("APAC_Direct", "USD", 2150000.0, 0.0, 80000.0),
]

# (cost_pool, currency, raw_spend_local, cap_software_pct, nonrecurring_legal_local)
COST_POOLS = [
    ("Cloud_Hosting", "USD", 3850000.0, 0.0, 0.0),
    ("Core_Engineering", "USD", 5200000.0, 12.0, 0.0),
    ("EMEA_Field_Ops", "EUR", 2400000.0, 0.0, 0.0),
    ("UK_Support_Center", "GBP", 1350000.0, 0.0, 0.0),
    ("Corporate_GA_Legal", "USD", 2100000.0, 0.0, 550000.0),
]
LEGAL_CAP_MUSD = 0.350

TICKET_A = (
    "# Work Order — SaaS Bookings & Net Revenue Lead (`saas_rev_lead`)\n\n"
    "Reconcile the 5 regional FY26 SaaS net bookings lines in `/workspace/close_fy26` and enter all cells + live formulas into the **LibreOffice Calc** and **LibreOffice Writer** windows open on the desktop:\n\n"
    "1. Read `/workspace/close_fy26/specs/FY26_FPnA_Close_Manual.pdf`, query `/workspace/close_fy26/fy26_ledger.sqlite` (`saas_regional_bookings`), and check the **FP&A Close Portal** open in Chromium (`http://127.0.0.1:19613`, `FX & Bookings Rules` tab).\n"
    "2. For each of the 5 regions (`NA_Enterprise`, `NA_MidMarket`, `EMEA_DACH`, `EMEA_UK`, `APAC_Direct`), compute net bookings in MUSD (rounded to 3 decimals) after applying `multi_yr_prepay_disc_pct` to `gross_bookings_local` first and then subtracting `churn_clawback_local`, translated at the portal's FY26 FX rates. Write `/workspace/close_fy26/saas_summary.json` (`resolution_code`, `regional_net_musd` dict, `total_net_bookings_musd`).\n"
    "3. In the open **LibreOffice Calc** window (`FY26_Consolidated_Close.xlsx`):\n"
    "   - On sheet `SaaS_Bookings`, enter the 5 regional MUSD values into `B2:B6` (matching rows 2..6 in order) and enter an Excel/Calc `=SUM(B2:B6)` formula in `B7`.\n"
    "   - On sheet `Exec_Scorecard`, enter `total_net_bookings_musd` into `B2` and save (`Ctrl+S`).\n"
    "4. In the open **LibreOffice Writer** window (`Board_Signoff_Minutes.odt`), add a line containing `resolution_code` and `total_net_bookings_musd` (3 decimals) and save (`Ctrl+S`).\n"
)

TICKET_B = (
    "# Work Order — Cloud COGS & Operating Expense Lead (`cogs_opex_lead`)\n\n"
    "Reconcile the 5 FY26 operating cost pools in `/workspace/close_fy26` and enter all cells + live formulas into the **LibreOffice Calc** and **LibreOffice Writer** windows open on the desktop:\n\n"
    "1. Read `/workspace/close_fy26/specs/FY26_FPnA_Close_Manual.pdf`, query `/workspace/close_fy26/fy26_ledger.sqlite` (`operating_cost_pools`), and check the **FP&A Close Portal** in Chromium (`http://127.0.0.1:19613`, `Cost Capitalization & Legal Cap` tab).\n"
    "2. For each of the 5 cost pools (`Cloud_Hosting`, `Core_Engineering`, `EMEA_Field_Ops`, `UK_Support_Center`, `Corporate_GA_Legal`), compute normalized cash cost in MUSD (3 decimals) after subtracting eligible capitalized software (`raw_spend * cap_software_pct/100`) and subtracting `nonrecurring_legal_local` capped at the portal's legal add-back cap, translated at FY26 FX rates. Write `/workspace/close_fy26/opex_summary.json` (`resolution_code`, `pool_net_musd` dict, `total_normalized_cost_musd`).\n"
    "3. In the open **LibreOffice Calc** window (`FY26_Consolidated_Close.xlsx`):\n"
    "   - On sheet `Cloud_COGS_Opex`, enter the 5 cost pool MUSD values into `B2:B6` (matching rows 2..6 in order) and enter an Excel/Calc `=SUM(B2:B6)` formula in `B7`.\n"
    "   - On sheet `Exec_Scorecard`, enter `total_normalized_cost_musd` into `B3` (feeding `B4` `=B2-B3`) and save (`Ctrl+S`).\n"
    "4. In the open **LibreOffice Writer** window (`Board_Signoff_Minutes.odt`), add a line containing `resolution_code` and `total_normalized_cost_musd` (3 decimals) and save (`Ctrl+S`).\n"
)


def compute_aw13_oracle() -> dict[str, Any]:
    reg_map: dict[str, float] = {}
    for rname, curr, gross, disc_pct, claw in SAAS_REGIONS:
        net_loc = gross * (1.0 - disc_pct / 100.0) - claw
        reg_map[rname] = round((net_loc * FX_RATES[curr]) / 1e6, 3)
    tot_rev = round(sum(reg_map.values()), 3)

    pool_map: dict[str, float] = {}
    for pname, curr, raw_s, cap_pct, leg_loc in COST_POOLS:
        fx = FX_RATES[curr]
        raw_m = (raw_s * fx) / 1e6
        cap_m = raw_m * (cap_pct / 100.0)
        leg_m = min((leg_loc * fx) / 1e6, LEGAL_CAP_MUSD)
        pool_map[pname] = round(raw_m - cap_m - leg_m, 3)
    tot_cost = round(sum(pool_map.values()), 3)
    return {
        "resolution_code": RESOLUTION_CODE,
        "regional_net_musd": reg_map,
        "total_net_bookings_musd": tot_rev,
        "pool_net_musd": pool_map,
        "total_normalized_cost_musd": tot_cost,
        "operating_margin_musd": round(tot_rev - tot_cost, 3),
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    cf = workspace_root / "shared" / "close_fy26"
    (cf / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)

    db_p = cf / "fy26_ledger.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE saas_regional_bookings (region TEXT PRIMARY KEY, currency TEXT, gross_bookings_local REAL, multi_yr_prepay_disc_pct REAL, churn_clawback_local REAL)")
    con.executemany("INSERT INTO saas_regional_bookings VALUES (?,?,?,?,?)", SAAS_REGIONS)
    con.execute("CREATE TABLE operating_cost_pools (cost_pool TEXT PRIMARY KEY, currency TEXT, raw_spend_local REAL, cap_software_pct REAL, nonrecurring_legal_local REAL)")
    con.executemany("INSERT INTO operating_cost_pools VALUES (?,?,?,?,?)", COST_POOLS)
    con.commit()
    con.close()

    write_multisheet_xlsx(
        seed / "FY26_Consolidated_Close.xlsx",
        [
            ("SaaS_Bookings", [["Region", "Net_Bookings_MUSD"], *[[r[0], 0.0] for r in SAAS_REGIONS], ["TOTAL_BOOKINGS", 0.0]]),
            ("Cloud_COGS_Opex", [["Cost_Pool", "Normalized_Cost_MUSD"], *[[p[0], 0.0] for p in COST_POOLS], ["TOTAL_COST", 0.0]]),
            ("Exec_Scorecard", [["KPI", "Amount_MUSD"], ["Total_Net_Bookings_MUSD", 0.0], ["Total_Normalized_Cost_MUSD", 0.0], ["Operating_Contribution_MUSD", ("=B2-B3", 0.0)]]),
        ],
    )
    write_odt_document(seed / "Board_Signoff_Minutes.odt", "FY26 Board Close Minutes", [("Minutes", ["Status: DRAFT_AWAITING_ENTRIES"])])

    write_pdf_manual(
        cf / "specs" / "FY26_FPnA_Close_Manual.pdf",
        "FY26 Consolidated Close Accounting Manual",
        [
            ("1. Regional Net Bookings", ["Apply multi_yr_prepay_disc_pct to gross_bookings_local, subtract churn_clawback_local, translate to USD using the FP&A Close Portal FX table, and round each regional MUSD line to 3 decimals."]),
            ("2. Normalized Operating Cost Pools", ["Translate raw_spend_local to USD, subtract capitalized software (cap_software_pct) and nonrecurring legal spend up to the portal's cap, and round each pool MUSD line to 3 decimals."]),
            ("3. Live LibreOffice Workbook & Minutes", ["Enter all regional/pool cells and =SUM(B2:B6) totals directly in the open LibreOffice Calc workbook (FY26_Consolidated_Close.xlsx) and LibreOffice Writer minutes (Board_Signoff_Minutes.odt) on the desktop, saving both with Ctrl+S."]),
        ],
    )
    (tickets_root / "saas_rev_lead").mkdir(parents=True, exist_ok=True)
    (tickets_root / "cogs_opex_lead").mkdir(parents=True, exist_ok=True)
    (tickets_root / "saas_rev_lead" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "cogs_opex_lead" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "fx", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw13_sess" in ck) and (ck["aw13_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw13_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 FP&amp;A Portal Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["fx"])[0]
                with lock:
                    if t in ("fx", "caps") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "fx":
                body = f"<h2>FX &amp; Bookings Schedule ({RESOLUTION_CODE})</h2><p><code>USD=1.00, EUR=1.08, GBP=1.26, CAD=0.74</code></p>"
            else:
                body = f"<h2>Cost Capitalization &amp; Legal Cap ({RESOLUTION_CODE})</h2><p>Non-recurring Corporate Legal Exclusion Cap: <code>${LEGAL_CAP_MUSD:.3f}M</code></p>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>FP&amp;A Close Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>FP&amp;A Close Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=fx">FX &amp; Bookings Rules</a><a href="/tab?id=caps">Cost Capitalization &amp; Legal Cap</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    boot_studio_browser(state_dir, window_size=(1160, 760))
    seed = workspace_root / "_desk_seed"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "FY26_Consolidated_Close.xlsx", sp / "FY26_Consolidated_Close.xlsx")
    shutil.copy2(seed / "Board_Signoff_Minutes.odt", sp / "Board_Signoff_Minutes.odt")
    launch_studio_app(
        "nohup libreoffice --norestore --nologo --nofirststartwizard "
        "'/srv/studio_project/FY26_Consolidated_Close.xlsx' '/srv/studio_project/Board_Signoff_Minutes.odt' "
        ">/tmp/aw13_lo.log 2>&1 </dev/null &",
        wait_s=3.0,
    )


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    cf = workspace_root / "shared" / "close_fy26"
    sp = Path("/srv/studio_project")
    xlsx_p = sp / "FY26_Consolidated_Close.xlsx"
    odt_p = sp / "Board_Signoff_Minutes.odt"
    ora = compute_aw13_oracle()
    if role == "saas_rev_lead":
        write_json(cf / "saas_summary.json", {"resolution_code": RESOLUTION_CODE, "regional_net_musd": ora["regional_net_musd"], "total_net_bookings_musd": ora["total_net_bookings_musd"]})
        s_rows = [["Region", "Net_Bookings_MUSD"], *[[r[0], ora["regional_net_musd"][r[0]]] for r in SAAS_REGIONS], ["TOTAL_BOOKINGS", ("=SUM(B2:B6)", ora["total_net_bookings_musd"])]]
        if cooperative:
            with resource_lock("aw13_lo"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b3_c = cell_float(bk, "Exec_Scorecard", "B3") or 0.0
                update_single_sheet_xlsx(xlsx_p, "SaaS_Bookings", s_rows)
                update_single_sheet_xlsx(xlsx_p, "Exec_Scorecard", [["KPI", "Amount_MUSD"], ["Total_Net_Bookings_MUSD", ora["total_net_bookings_musd"]], ["Total_Normalized_Cost_MUSD", b3_c], ["Operating_Contribution_MUSD", ("=B2-B3", round(ora["total_net_bookings_musd"] - b3_c, 3))]])
                prev = [ln for ln in read_odt_text(odt_p).splitlines() if "Cost:" in ln]
                write_odt_document(odt_p, "FY26 Board Close Minutes", [("Minutes", [f"{RESOLUTION_CODE} | Bookings: {ora['total_net_bookings_musd']:.3f}", *prev])])
        else:
            write_multisheet_xlsx(xlsx_p, [("SaaS_Bookings", s_rows)])
    elif role == "cogs_opex_lead":
        write_json(cf / "opex_summary.json", {"resolution_code": RESOLUTION_CODE, "pool_net_musd": ora["pool_net_musd"], "total_normalized_cost_musd": ora["total_normalized_cost_musd"]})
        c_rows = [["Cost_Pool", "Normalized_Cost_MUSD"], *[[p[0], ora["pool_net_musd"][p[0]]] for p in COST_POOLS], ["TOTAL_COST", ("=SUM(B2:B6)", ora["total_normalized_cost_musd"])]]
        if cooperative:
            with resource_lock("aw13_lo"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b2_c = cell_float(bk, "Exec_Scorecard", "B2") or 0.0
                update_single_sheet_xlsx(xlsx_p, "Cloud_COGS_Opex", c_rows)
                update_single_sheet_xlsx(xlsx_p, "Exec_Scorecard", [["KPI", "Amount_MUSD"], ["Total_Net_Bookings_MUSD", b2_c], ["Total_Normalized_Cost_MUSD", ora["total_normalized_cost_musd"]], ["Operating_Contribution_MUSD", ("=B2-B3", round(b2_c - ora["total_normalized_cost_musd"], 3))]])
                prev = [ln for ln in read_odt_text(odt_p).splitlines() if "Bookings:" in ln]
                write_odt_document(odt_p, "FY26 Board Close Minutes", [("Minutes", [*prev, f"{RESOLUTION_CODE} | Cost: {ora['total_normalized_cost_musd']:.3f}"])])
        else:
            write_multisheet_xlsx(xlsx_p, [("Cloud_COGS_Opex", c_rows)])


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("saas_rev_lead", workspace_root, cooperative=False)
    solve_role("cogs_opex_lead", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "saas_rev_lead", workspace_root, True)
        fb = pool.submit(solve_role, "cogs_opex_lead", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    cf = workspace_root / "shared" / "close_fy26"
    sp = Path("/srv/studio_project")
    ora = compute_aw13_oracle()
    ja = read_json_safe(cf / "saas_summary.json")
    jb = read_json_safe(cf / "opex_summary.json")
    raw_book = evaluate_xlsx_isolated(sp / "FY26_Consolidated_Close.xlsx")
    from tasks.authentic_workstation_v1.common import read_multisheet_xlsx

    f_book = read_multisheet_xlsx(sp / "FY26_Consolidated_Close.xlsx") if (sp / "FY26_Consolidated_Close.xlsx").is_file() else {}
    odt_txt = read_odt_text(sp / "Board_Signoff_Minutes.odt")

    def _close(v: Any, exp: float, tol: float = 0.02) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json_tot", _close(ja.get("total_net_bookings_musd"), ora["total_net_bookings_musd"]) and ja.get("resolution_code") == RESOLUTION_CODE, 2.0, "saas_summary.json total or resolution_code mismatch"),
        *[
            (f"a_cell_b{idx}", _close(cell_float(raw_book, "SaaS_Bookings", f"B{idx}"), ora["regional_net_musd"][r[0]], 0.025), 1.2, f"Live Calc SaaS_Bookings!B{idx} ({r[0]}) mismatch")
            for idx, r in enumerate(SAAS_REGIONS, start=2)
        ],
        ("a_sum_formula_b7", "SUM" in cell_formula(f_book, "SaaS_Bookings", "B7").upper() and _close(cell_float(raw_book, "SaaS_Bookings", "B7"), ora["total_net_bookings_musd"], 0.04), 1.8, "Live Calc SaaS_Bookings!B7 missing =SUM(B2:B6) formula or wrong sum"),
        ("a_exec_b2", _close(cell_float(raw_book, "Exec_Scorecard", "B2"), ora["total_net_bookings_musd"], 0.04), 1.8, "Live Calc Exec_Scorecard!B2 mismatch"),
        ("a_writer", RESOLUTION_CODE in odt_txt and f"{ora['total_net_bookings_musd']:.3f}"[:5] in odt_txt, 1.8, "Live Writer minutes missing bookings resolution"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json_tot", _close(jb.get("total_normalized_cost_musd"), ora["total_normalized_cost_musd"]) and jb.get("resolution_code") == RESOLUTION_CODE, 2.0, "opex_summary.json total or resolution_code mismatch"),
        *[
            (f"b_cell_b{idx}", _close(cell_float(raw_book, "Cloud_COGS_Opex", f"B{idx}"), ora["pool_net_musd"][p[0]], 0.025), 1.2, f"Live Calc Cloud_COGS_Opex!B{idx} ({p[0]}) mismatch")
            for idx, p in enumerate(COST_POOLS, start=2)
        ],
        ("b_sum_formula_b7", "SUM" in cell_formula(f_book, "Cloud_COGS_Opex", "B7").upper() and _close(cell_float(raw_book, "Cloud_COGS_Opex", "B7"), ora["total_normalized_cost_musd"], 0.04), 1.8, "Live Calc Cloud_COGS_Opex!B7 missing =SUM(B2:B6) formula or wrong sum"),
        ("b_exec_b3", _close(cell_float(raw_book, "Exec_Scorecard", "B3"), ora["total_normalized_cost_musd"], 0.04), 1.8, "Live Calc Exec_Scorecard!B3 mismatch"),
        ("b_writer", RESOLUTION_CODE in odt_txt and f"{ora['total_normalized_cost_musd']:.3f}"[:5] in odt_txt, 1.8, "Live Writer minutes missing cost resolution"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_exec_scorecard_b4_margin",
            _close(cell_float(raw_book, "Exec_Scorecard", "B4"), ora["operating_margin_musd"], 0.06),
            2.5,
            f"Live Calc Exec_Scorecard!B4 (=B2-B3) operating contribution mismatch (got {cell_float(raw_book, 'Exec_Scorecard', 'B4')})",
        ),
        (
            "j_writer_minutes_both_lines",
            f"{ora['total_net_bookings_musd']:.3f}"[:5] in odt_txt and f"{ora['total_normalized_cost_musd']:.3f}"[:5] in odt_txt,
            2.0,
            "Live Writer Board_Signoff_Minutes.odt lost one role's entry due to concurrent GUI focus/save collision",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"saas_rev_lead": TICKET_A, "cogs_opex_lead": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

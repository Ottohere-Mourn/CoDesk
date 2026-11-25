"""AW-08: Live LibreOffice Calc + Writer Q4 Board Close — Revenue Recognition vs. Opex & Debt Covenant Controller."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
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
    "id": "AW-08",
    "slug": "libreoffice_calc_writer_cfo_close",
    "title": "Q4 Board Close in Live LibreOffice Calc & Writer: Revenue Cohort Audit vs. Opex & Covenant Controller",
    "domain": "Corporate Finance & Live Office Productivity (LibreOffice Calc + Writer + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19608,
    "roles": ("rev_recognition_analyst", "opex_covenant_controller"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
    "mount_studio_ro": True,
}

TREASURY_FX = {"USD": 1.0, "EUR": 1.09, "GBP": 1.27}
CLOSE_AUTH_CODE = "CFO-Q4-CLOSE-991"

# (invoice_id, currency, billed_local, term_months, elapsed_q4_months, credit_memo_local)
REV_INVOICES = [
    ("INV-801", "USD", 2400000.0, 12, 3, 0.0),
    ("INV-802", "EUR", 1800000.0, 12, 3, 60000.0),
    ("INV-803", "GBP", 1200000.0, 6, 3, 0.0),
    ("INV-804", "USD", 3600000.0, 3, 3, 150000.0),
    ("INV-805", "EUR", 2400000.0, 24, 2, 0.0),
    ("INV-806", "USD", 1950000.0, 3, 3, 0.0),
]

# (voucher_id, dept, currency, amount_local, category)
OPEX_VOUCHERS = [
    ("OPX-301", "R&D", "USD", 1850000.0, "cash_payroll"),
    ("OPX-302", "Sales", "EUR", 920000.0, "cash_commissions"),
    ("OPX-303", "G&A", "GBP", 540000.0, "cash_facilities"),
    ("OPX-304", "Infra", "USD", 1120000.0, "cash_cloud"),
    ("OPX-305", "R&D", "USD", 380000.0, "noncash_sbc"),
    ("OPX-306", "Legal", "USD", 610000.0, "restructuring_nonrecurring"),
]

RESTRUCTURING_CAP_MUSD = 0.400
SENIOR_DEBT_MUSD = 11.400

TICKET_A = (
    "# Work Order — Q4 Revenue Recognition Analyst (`rev_recognition_analyst`)\n\n"
    "Complete the Q4 recognized revenue audit in `/workspace/close_data` and enter the final figures into the live **LibreOffice Calc** and **LibreOffice Writer** documents open on the desktop (`/srv/studio_project/Q4_Board_Close.xlsx` and `/srv/studio_project/Q4_Audit_Committee_Brief.odt`):\n\n"
    "1. Review `/workspace/close_data/specs/Board_Close_Accounting_Policy.pdf`, query `/workspace/close_data/q4_subledger.sqlite` (`q4_invoices`), and inspect the **Treasury Close Portal** open in Chromium (`http://127.0.0.1:19608`, `FX & Revenue Rules` tab).\n"
    "2. Compute Q4 gross billed USD (`gross_billed_musd`), Q4 earned revenue before credits (`earned_pre_credit_musd`), Q4 recognized net revenue after credit memos (`recognized_net_rev_musd`), and Q4 ending deferred revenue (`deferred_rev_ending_musd`), writing `/workspace/close_data/revenue_audit.json` with:\n"
    "   - `close_auth_code`, `gross_billed_musd`, `earned_pre_credit_musd`, `recognized_net_rev_musd`, `deferred_rev_ending_musd`\n"
    "3. In the open **LibreOffice Calc** window (`Q4_Board_Close.xlsx`), enter `recognized_net_rev_musd` into `Rev_Bridge!B2`, `deferred_rev_ending_musd` into `Rev_Bridge!B3`, AND `recognized_net_rev_musd` into `Board_Rollup!B2`, then save (`Ctrl+S`).\n"
    "4. In the open **LibreOffice Writer** window (`Q4_Audit_Committee_Brief.odt`), record `close_auth_code` and `recognized_net_rev_musd` (3 decimals) in the document body and save (`Ctrl+S`).\n"
)

TICKET_B = (
    "# Work Order — Q4 Opex & Debt Covenant Controller (`opex_covenant_controller`)\n\n"
    "Complete the Q4 normalized cash Opex and senior leverage covenant audit in `/workspace/close_data` and enter the final figures into the live **LibreOffice Calc** and **LibreOffice Writer** documents open on the desktop (`/srv/studio_project/Q4_Board_Close.xlsx` and `/srv/studio_project/Q4_Audit_Committee_Brief.odt`):\n\n"
    "1. Review `/workspace/close_data/specs/Board_Close_Accounting_Policy.pdf`, query `/workspace/close_data/q4_subledger.sqlite` (`q4_opex_vouchers`), and inspect the **Treasury Close Portal** in Chromium (`http://127.0.0.1:19608`, `Covenant & Restructuring Cap` tab).\n"
    "2. Compute total GAAP Opex (`gaap_opex_musd`), non-cash SBC exclusion (`sbc_excluded_musd`), capped restructuring exclusion (`restructuring_excluded_musd`), normalized cash Opex (`normalized_cash_opex_musd`), and annualized debt-to-cash-flow ratio (`leverage_ratio_x` against annualized Q4 contribution or standalone debt schedule per spec), writing `/workspace/close_data/opex_covenant_audit.json` with:\n"
    "   - `close_auth_code`, `gaap_opex_musd`, `sbc_excluded_musd`, `restructuring_excluded_musd`, `normalized_cash_opex_musd`, `senior_debt_musd`\n"
    "3. In the open **LibreOffice Calc** window (`Q4_Board_Close.xlsx`), enter `gaap_opex_musd` into `Opex_Covenant!B2`, `normalized_cash_opex_musd` into `Opex_Covenant!B3`, AND `normalized_cash_opex_musd` into `Board_Rollup!B3`, then save (`Ctrl+S`).\n"
    "4. In the open **LibreOffice Writer** window (`Q4_Audit_Committee_Brief.odt`), record `close_auth_code` and `normalized_cash_opex_musd` (3 decimals) in the document body and save (`Ctrl+S`).\n"
)


def compute_close_oracle() -> dict[str, Any]:
    gross_usd = 0.0
    earned_pre_usd = 0.0
    net_rev_usd = 0.0
    def_end_usd = 0.0
    for _id, curr, billed, term_m, el_m, cm_loc in REV_INVOICES:
        fx = TREASURY_FX[curr]
        b_u = billed * fx
        cm_u = cm_loc * fx
        net_contract_u = b_u - cm_u
        frac = el_m / float(term_m)
        gross_usd += b_u
        earned_pre_usd += b_u * frac
        # Per policy: credit memos reduce total contract consideration pro-rata across contract term!
        rec_u = net_contract_u * frac
        net_rev_usd += rec_u
        def_end_usd += net_contract_u * (1.0 - frac)

    gaap_opx_usd = sum(amt * TREASURY_FX[curr] for _v, _d, curr, amt, _c in OPEX_VOUCHERS)
    sbc_usd = sum(amt * TREASURY_FX[curr] for _v, _d, curr, amt, c in OPEX_VOUCHERS if c == "noncash_sbc")
    rest_raw_musd = sum(amt * TREASURY_FX[curr] for _v, _d, curr, amt, c in OPEX_VOUCHERS if c == "restructuring_nonrecurring") / 1e6
    rest_excl_musd = min(rest_raw_musd, RESTRUCTURING_CAP_MUSD)
    norm_opx_musd = round((gaap_opx_usd / 1e6) - (sbc_usd / 1e6) - rest_excl_musd, 3)
    rec_rev_musd = round(net_rev_usd / 1e6, 3)
    q4_ebitda_musd = round(rec_rev_musd - norm_opx_musd, 3)

    return {
        "close_auth_code": CLOSE_AUTH_CODE,
        "gross_billed_musd": round(gross_usd / 1e6, 3),
        "earned_pre_credit_musd": round(earned_pre_usd / 1e6, 3),
        "recognized_net_rev_musd": rec_rev_musd,
        "deferred_rev_ending_musd": round(def_end_usd / 1e6, 3),
        "gaap_opex_musd": round(gaap_opx_usd / 1e6, 3),
        "sbc_excluded_musd": round(sbc_usd / 1e6, 3),
        "restructuring_excluded_musd": round(rest_excl_musd, 3),
        "normalized_cash_opex_musd": norm_opx_musd,
        "senior_debt_musd": SENIOR_DEBT_MUSD,
        "q4_Contribution_ebitda_musd": q4_ebitda_musd,
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    cd = workspace_root / "shared" / "close_data"
    (cd / "specs").mkdir(parents=True, exist_ok=True)
    tmpl = workspace_root / "shared" / ".studio_seed"
    tmpl.mkdir(parents=True, exist_ok=True)

    db_p = cd / "q4_subledger.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute(
        "CREATE TABLE q4_invoices (invoice_id TEXT PRIMARY KEY, currency TEXT, billed_amount_local REAL, "
        "service_term_months INTEGER, q4_elapsed_months INTEGER, credit_memo_local REAL)"
    )
    con.executemany("INSERT INTO q4_invoices VALUES (?,?,?,?,?,?)", REV_INVOICES)
    con.execute(
        "CREATE TABLE q4_opex_vouchers (voucher_id TEXT PRIMARY KEY, department TEXT, currency TEXT, "
        "amount_local REAL, expense_category TEXT)"
    )
    con.executemany("INSERT INTO q4_opex_vouchers VALUES (?,?,?,?,?)", OPEX_VOUCHERS)
    con.commit()
    con.close()

    write_multisheet_xlsx(
        tmpl / "Q4_Board_Close.xlsx",
        [
            ("Rev_Bridge", [["Metric", "Amount_MUSD"], ["Recognized_Net_Rev_MUSD", 0.0], ["Deferred_Rev_Ending_MUSD", 0.0]]),
            ("Opex_Covenant", [["Metric", "Amount_MUSD"], ["GAAP_Opex_MUSD", 0.0], ["Normalized_Cash_Opex_MUSD", 0.0]]),
            (
                "Board_Rollup",
                [
                    ["Metric", "Amount_MUSD"],
                    ["Recognized_Net_Rev_MUSD", 0.0],
                    ["Normalized_Cash_Opex_MUSD", 0.0],
                    ["Q4_Contribution_EBITDA_MUSD", ("=B2-B3", 0.0)],
                ],
            ),
        ],
    )
    write_odt_document(
        tmpl / "Q4_Audit_Committee_Brief.odt",
        "Q4 Audit Committee Signoff Brief",
        [("Controller Notes", ["Status: AWAITING_LIVE_GUI_SIGNOFF"])],
    )

    write_pdf_manual(
        cd / "specs" / "Board_Close_Accounting_Policy.pdf",
        "Q4 Board Close Revenue & Covenant Policy",
        [
            (
                "1. Multi-Currency ASC 606 Revenue & Pro-Rata Credit Memos",
                [
                    "Translate foreign-currency invoices and vouchers using the Q4 Treasury FX Schedule in the open Chromium portal.",
                    "Under ASC 606 variable consideration rules, credit_memo_local reduces total net transaction price (billed_amount_local - credit_memo_local) BEFORE pro-rating by (q4_elapsed_months / service_term_months)! Ending Q4 deferred revenue equals the unearned remainder (1 - q4_elapsed_months / service_term_months) of net transaction price.",
                ],
            ),
            (
                "2. Normalized Cash Opex & Capped Restructuring Add-Back",
                [
                    "GAAP Opex sums all rows in q4_opex_vouchers translated to USD. Normalized Cash Opex subtracts 100% of noncash_sbc AND subtracts restructuring_nonrecurring up to the Credit Agreement cap published in the Treasury Close Portal.",
                ],
            ),
            (
                "3. Live LibreOffice Calc & Writer Filing in /srv/studio_project",
                [
                    "The official signoff files /srv/studio_project/Q4_Board_Close.xlsx and /srv/studio_project/Q4_Audit_Committee_Brief.odt are open inside LibreOffice on the desktop. Enter your reconciled MUSD figures (rounded to 3 decimals) directly in LibreOffice and save with Ctrl+S (you can verify saved disk contents read-only at /srv/studio_project/).",
                ],
            ),
        ],
    )

    (tickets_root / "rev_recognition_analyst").mkdir(parents=True, exist_ok=True)
    (tickets_root / "opex_covenant_controller").mkdir(parents=True, exist_ok=True)
    (tickets_root / "rev_recognition_analyst" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "opex_covenant_controller" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "fx_rev", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw08_sess" in ck) and (ck["aw08_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw08_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Treasury Close Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["fx_rev"])[0]
                with lock:
                    if t in ("fx_rev", "covenant") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "fx_rev":
                body = f"""<h2>FX &amp; Revenue Close Schedule</h2>
                <p><b>Close Authorization Code:</b> <code>{CLOSE_AUTH_CODE}</code></p>
                <p><b>Q4 Average FX Rates:</b> <code>USD = 1.00</code>, <code>EUR = 1.09</code>, <code>GBP = 1.27</code></p>"""
            else:
                body = f"""<h2>Credit Agreement Covenant &amp; Restructuring Cap</h2>
                <p><b>Close Authorization Code:</b> <code>{CLOSE_AUTH_CODE}</code></p>
                <p><b>Quarterly Restructuring Exclusion Cap:</b> <code>${RESTRUCTURING_CAP_MUSD:.3f}M</code></p>
                <p><b>Closing Senior Term Debt:</b> <code>${SENIOR_DEBT_MUSD:.3f}M</code></p>"""
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Treasury Close Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>Treasury Q4 Close Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=fx_rev">FX &amp; Revenue Rules</a><a href="/tab?id=covenant">Covenant &amp; Restructuring Cap</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    boot_studio_browser(state_dir, window_size=(1180, 780))
    tmpl = workspace_root / "shared" / ".studio_seed"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tmpl / "Q4_Board_Close.xlsx", sp / "Q4_Board_Close.xlsx")
    shutil.copy2(tmpl / "Q4_Audit_Committee_Brief.odt", sp / "Q4_Audit_Committee_Brief.odt")
    launch_studio_app(
        "nohup libreoffice --norestore --nologo --nofirststartwizard "
        "'/srv/studio_project/Q4_Board_Close.xlsx' '/srv/studio_project/Q4_Audit_Committee_Brief.odt' "
        ">/tmp/aw08_lo.log 2>&1 </dev/null &",
        wait_s=3.0,
    )


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    cd = workspace_root / "shared" / "close_data"
    sp = Path("/srv/studio_project")
    xlsx_p = sp / "Q4_Board_Close.xlsx"
    odt_p = sp / "Q4_Audit_Committee_Brief.odt"
    ora = compute_close_oracle()

    if role == "rev_recognition_analyst":
        write_json(
            cd / "revenue_audit.json",
            {
                "close_auth_code": CLOSE_AUTH_CODE,
                "gross_billed_musd": ora["gross_billed_musd"],
                "earned_pre_credit_musd": ora["earned_pre_credit_musd"],
                "recognized_net_rev_musd": ora["recognized_net_rev_musd"],
                "deferred_rev_ending_musd": ora["deferred_rev_ending_musd"],
            },
        )
        if cooperative:
            with resource_lock("aw08_studio"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b3_cur = cell_float(bk, "Board_Rollup", "B3") or 0.0
                update_single_sheet_xlsx(xlsx_p, "Rev_Bridge", [["Metric", "Amount_MUSD"], ["Recognized_Net_Rev_MUSD", ora["recognized_net_rev_musd"]], ["Deferred_Rev_Ending_MUSD", ora["deferred_rev_ending_musd"]]])
                update_single_sheet_xlsx(xlsx_p, "Board_Rollup", [["Metric", "Amount_MUSD"], ["Recognized_Net_Rev_MUSD", ora["recognized_net_rev_musd"]], ["Normalized_Cash_Opex_MUSD", b3_cur], ["Q4_Contribution_EBITDA_MUSD", ("=B2-B3", round(ora["recognized_net_rev_musd"] - b3_cur, 3))]])
                prev = [ln for ln in read_odt_text(odt_p).splitlines() if "Opex" in ln]
                write_odt_document(odt_p, "Q4 Audit Committee Signoff Brief", [("Signoff", [f"Auth {CLOSE_AUTH_CODE} | Recognized Net Rev: ${ora['recognized_net_rev_musd']:.3f}M", *prev])])
        else:
            write_multisheet_xlsx(xlsx_p, [("Rev_Bridge", [["Metric", "Amount_MUSD"], ["Recognized_Net_Rev_MUSD", ora["recognized_net_rev_musd"]]])])
            write_odt_document(odt_p, "Q4 Audit Committee Signoff Brief", [("Signoff", [f"Auth {CLOSE_AUTH_CODE} | Recognized Net Rev: ${ora['recognized_net_rev_musd']:.3f}M"])])
    elif role == "opex_covenant_controller":
        write_json(
            cd / "opex_covenant_audit.json",
            {
                "close_auth_code": CLOSE_AUTH_CODE,
                "gaap_opex_musd": ora["gaap_opex_musd"],
                "sbc_excluded_musd": ora["sbc_excluded_musd"],
                "restructuring_excluded_musd": ora["restructuring_excluded_musd"],
                "normalized_cash_opex_musd": ora["normalized_cash_opex_musd"],
                "senior_debt_musd": SENIOR_DEBT_MUSD,
            },
        )
        if cooperative:
            with resource_lock("aw08_studio"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b2_cur = cell_float(bk, "Board_Rollup", "B2") or 0.0
                update_single_sheet_xlsx(xlsx_p, "Opex_Covenant", [["Metric", "Amount_MUSD"], ["GAAP_Opex_MUSD", ora["gaap_opex_musd"]], ["Normalized_Cash_Opex_MUSD", ora["normalized_cash_opex_musd"]]])
                update_single_sheet_xlsx(xlsx_p, "Board_Rollup", [["Metric", "Amount_MUSD"], ["Recognized_Net_Rev_MUSD", b2_cur], ["Normalized_Cash_Opex_MUSD", ora["normalized_cash_opex_musd"]], ["Q4_Contribution_EBITDA_MUSD", ("=B2-B3", round(b2_cur - ora["normalized_cash_opex_musd"], 3))]])
                prev = [ln for ln in read_odt_text(odt_p).splitlines() if "Recognized Net Rev" in ln]
                write_odt_document(odt_p, "Q4 Audit Committee Signoff Brief", [("Signoff", [*prev, f"Auth {CLOSE_AUTH_CODE} | Normalized Cash Opex: ${ora['normalized_cash_opex_musd']:.3f}M"])])
        else:
            write_multisheet_xlsx(xlsx_p, [("Opex_Covenant", [["Metric", "Amount_MUSD"], ["Normalized_Cash_Opex_MUSD", ora["normalized_cash_opex_musd"]]])])
            write_odt_document(odt_p, "Q4 Audit Committee Signoff Brief", [("Signoff", [f"Auth {CLOSE_AUTH_CODE} | Normalized Cash Opex: ${ora['normalized_cash_opex_musd']:.3f}M"])])
    subprocess.run(["chmod", "-R", "a+rX", str(sp)], capture_output=True, timeout=10)


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("rev_recognition_analyst", workspace_root, cooperative=False)
    solve_role("opex_covenant_controller", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "rev_recognition_analyst", workspace_root, True)
        fb = pool.submit(solve_role, "opex_covenant_controller", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    cd = workspace_root / "shared" / "close_data"
    sp = Path("/srv/studio_project")
    ora = compute_close_oracle()
    ja = read_json_safe(cd / "revenue_audit.json")
    jb = read_json_safe(cd / "opex_covenant_audit.json")
    book = evaluate_xlsx_isolated(sp / "Q4_Board_Close.xlsx")
    odt_txt = read_odt_text(sp / "Q4_Audit_Committee_Brief.odt")

    def _close(v: Any, exp: float, tol: float = 0.02) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_auth", ja.get("close_auth_code") == CLOSE_AUTH_CODE, 1.0, "close_auth_code mismatch"),
        ("a_gross", _close(ja.get("gross_billed_musd"), ora["gross_billed_musd"]), 1.2, "gross_billed_musd mismatch"),
        ("a_rec_rev", _close(ja.get("recognized_net_rev_musd"), ora["recognized_net_rev_musd"]), 1.8, f"recognized_net_rev_musd mismatch ({ora['recognized_net_rev_musd']})"),
        ("a_def_rev", _close(ja.get("deferred_rev_ending_musd"), ora["deferred_rev_ending_musd"]), 1.6, f"deferred_rev_ending_musd mismatch ({ora['deferred_rev_ending_musd']})"),
        ("a_gui_calc_rev", _close(cell_float(book, "Rev_Bridge", "B2"), ora["recognized_net_rev_musd"], 0.03), 2.2, "Live Calc Rev_Bridge!B2 not saved with recognized_net_rev_musd"),
        ("a_gui_calc_def", _close(cell_float(book, "Rev_Bridge", "B3"), ora["deferred_rev_ending_musd"], 0.03), 1.8, "Live Calc Rev_Bridge!B3 not saved with deferred_rev_ending_musd"),
        ("a_gui_rollup_b2", _close(cell_float(book, "Board_Rollup", "B2"), ora["recognized_net_rev_musd"], 0.03), 2.0, "Live Calc Board_Rollup!B2 not saved with recognized_net_rev_musd"),
        ("a_gui_writer_rev", CLOSE_AUTH_CODE in odt_txt and f"{ora['recognized_net_rev_musd']:.3f}"[:5] in odt_txt, 2.0, "Live Writer brief missing saved revenue signoff"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_auth", jb.get("close_auth_code") == CLOSE_AUTH_CODE, 1.0, "close_auth_code mismatch"),
        ("b_gaap_opx", _close(jb.get("gaap_opex_musd"), ora["gaap_opex_musd"]), 1.2, "gaap_opex_musd mismatch"),
        ("b_rest_cap", _close(jb.get("restructuring_excluded_musd"), ora["restructuring_excluded_musd"], 0.01), 1.6, "restructuring_excluded_musd must respect $0.400M cap"),
        ("b_norm_opx", _close(jb.get("normalized_cash_opex_musd"), ora["normalized_cash_opex_musd"]), 1.8, f"normalized_cash_opex_musd mismatch ({ora['normalized_cash_opex_musd']})"),
        ("b_gui_calc_gaap", _close(cell_float(book, "Opex_Covenant", "B2"), ora["gaap_opex_musd"], 0.03), 1.8, "Live Calc Opex_Covenant!B2 not saved with gaap_opex_musd"),
        ("b_gui_calc_norm", _close(cell_float(book, "Opex_Covenant", "B3"), ora["normalized_cash_opex_musd"], 0.03), 2.2, "Live Calc Opex_Covenant!B3 not saved with normalized_cash_opex_musd"),
        ("b_gui_rollup_b3", _close(cell_float(book, "Board_Rollup", "B3"), ora["normalized_cash_opex_musd"], 0.03), 2.0, "Live Calc Board_Rollup!B3 not saved with normalized_cash_opex_musd"),
        ("b_gui_writer_opx", CLOSE_AUTH_CODE in odt_txt and f"{ora['normalized_cash_opex_musd']:.3f}"[:5] in odt_txt, 2.0, "Live Writer brief missing saved Opex signoff"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_live_calc_rollup_b4_ebitda",
            _close(cell_float(book, "Board_Rollup", "B4"), ora["q4_Contribution_ebitda_musd"], 0.05),
            2.5,
            f"Live Calc Board_Rollup!B4 (=B2-B3) mismatch (expected {ora['q4_Contribution_ebitda_musd']}, got {cell_float(book, 'Board_Rollup', 'B4')})",
        ),
        (
            "j_live_writer_has_both_signoffs",
            f"{ora['recognized_net_rev_musd']:.3f}"[:5] in odt_txt and f"{ora['normalized_cash_opex_musd']:.3f}"[:5] in odt_txt,
            2.0,
            "Live Writer Q4_Audit_Committee_Brief.odt missing one role's saved signoff due to shared window/focus contention",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"rev_recognition_analyst": TICKET_A, "opex_covenant_controller": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

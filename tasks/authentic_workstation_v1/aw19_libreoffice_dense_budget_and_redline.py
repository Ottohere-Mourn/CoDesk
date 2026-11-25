"""AW-19: Zero-Spoiler Datacenter Capex & Colocation MSA Closing in Live LibreOffice Calc & Writer."""
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
    cell_formula,
    evaluate_xlsx_isolated,
    launch_studio_app,
    read_json_safe,
    read_multisheet_xlsx,
    read_odt_text,
    resource_lock,
    update_single_sheet_xlsx,
    write_json,
    write_multisheet_xlsx,
    write_odt_document,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-19",
    "slug": "libreoffice_dense_budget_and_redline",
    "title": "Hyperscale Datacenter Capex & Colocation MSA Closing in Live LibreOffice Calc & Writer",
    "domain": "Enterprise Procurement & Legal Redlining (LibreOffice Calc + LibreOffice Writer + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19619,
    "roles": ("dc_capex_controller", "msa_commercial_counsel"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

DEAL_STAMP = "MSA-DC2026-940"
FX_DC = {"USD": 1.0, "EUR": 1.08, "SEK": 0.095, "JPY": 0.0068}
HS_DUTY_PCT = {"IT_ITA_EXEMPT": 0.0, "CRAC_THERMAL": 4.5, "MV_SWITCHGEAR": 3.2}
SLA_TIER_CAP_PCT = {"TIER_III": 9.0, "TIER_IV": 6.0}
OEM_WARRANTY_MONTHS = 42
SUPERCAP_MULTIPLE = "2.75x"
CAPEX_BUF_LOW = 1.300
CAPEX_BUF_HIGH = 2.050
LEASE_ESC_LOW = 1.150
LEASE_ESC_HIGH = 1.900

# (pkg_id, currency, hs_class, base_quote_local, oem_rebate_local, freight_ins_pct)
CAPEX_PKGS = [
    ("PKG-GPU-01", "USD", "IT_ITA_EXEMPT", 4800000.0, 180000.0, 1.5),
    ("PKG-CHILL-02", "EUR", "CRAC_THERMAL", 2200000.0, 60000.0, 2.5),
    ("PKG-SWGR-03", "SEK", "MV_SWITCHGEAR", 18500000.0, 450000.0, 2.0),
    ("PKG-UPS-04", "EUR", "MV_SWITCHGEAR", 1650000.0, 40000.0, 2.0),
    ("PKG-OPTIC-05", "JPY", "IT_ITA_EXEMPT", 210000000.0, 6000000.0, 1.2),
    ("PKG-RACK-06", "USD", "CRAC_THERMAL", 940000.0, 35000.0, 2.0),
    ("PKG-GEN-07", "USD", "MV_SWITCHGEAR", 1750000.0, 50000.0, 2.2),
    ("PKG-FIRE-08", "EUR", "CRAC_THERMAL", 680000.0, 25000.0, 2.5),
]

# (site_id, currency, annual_base_local, raw_cpi_pct, power_mw, sla_tier)
LEASE_SITES = [
    ("SITE-FRA1", "EUR", 1400000.0, 3.6, 10.0, "TIER_IV"),
    ("SITE-LULEA2", "SEK", 12000000.0, 2.5, 12.0, "TIER_III"),
    ("SITE-NRT3", "JPY", 180000000.0, 1.2, 6.0, "TIER_IV"),
    ("SITE-IAD4", "USD", 2100000.0, 3.5, 14.0, "TIER_IV"),
    ("SITE-DUB5", "EUR", 1150000.0, 2.8, 5.0, "TIER_III"),
    ("SITE-ORD6", "USD", 1550000.0, 3.1, 8.5, "TIER_III"),
    ("SITE-ZRH7", "EUR", 980000.0, 1.5, 4.0, "TIER_IV"),
    ("SITE-OSA8", "JPY", 135000000.0, 1.6, 5.5, "TIER_III"),
]

TICKET_A = (
    "# Work Order — Datacenter Capex Controller (`dc_capex_controller`)\n\n"
    "Finalize the FY26 hardware Capex valuation in `/workspace/dc_deal`, complete the `Hardware_Capex` and `Deal_Rollup` schedules in the open **LibreOffice Calc** workbook (`Global_Capex_Model.xlsx`), and execute Section 4 contract redlines in the open **LibreOffice Writer** agreement (`Master_Services_Agreement.odt`):\n\n"
    "1. Review `/workspace/dc_deal/specs/DC_Procurement_Policy.pdf`, query `/workspace/dc_deal/procurement.sqlite` (`capex_packages`), and inspect the **Procurement & Treasury Portal** open in Chromium (`http://127.0.0.1:19619`, `Overview` and `FX & Customs Tariff` views).\n"
    "2. Applying the OEM rebate threshold, CIF freight/insurance basis, and HS tariff rules from the policy and portal, compute 3-decimal MUSD `cif_musd` and `landed_musd` for `PKG-GPU-01`..`PKG-FIRE-08`, and write `/workspace/dc_deal/capex_audit.json` (`deal_stamp`, `cif_musd`, `landed_musd`, `total_cif_musd`, `total_landed_musd`, `mean_landed_musd`, `selected_capex_buffer_musd`).\n"
    "3. In the open **LibreOffice Calc** window (`Global_Capex_Model.xlsx`):\n"
    "   - On `Hardware_Capex`, enter `cif_musd` in `B2:B9` and `landed_musd` in `C2:C9`, enter `=SUM(...)` formulas in `B10` and `C10`, and enter `=AVERAGE(C2:C9)` in `C11`.\n"
    "   - On `Deal_Rollup`, enter `total_landed_musd` in `B2`, select the approved Capex Contingency Buffer tier in `B4` so `Reserve_Coverage_Ratio` (`B6`) satisfies the portal's Treasury Reserve Covenant window, and save (`Ctrl+S`).\n"
    "4. In the open **LibreOffice Writer** window (`Master_Services_Agreement.odt`), replace `[REDLINE_S4_STAMP]`, `[REDLINE_CAPEX_CEILING_MUSD]` (3 decimals), and `[REDLINE_OEM_WARRANTY_MOS]` with the verified closing values, and save (`Ctrl+S`).\n"
)

TICKET_B = (
    "# Work Order — MSA Commercial & Colocation Lease Counsel (`msa_commercial_counsel`)\n\n"
    "Finalize the Year-2 colocation lease commitment & SLA exposure schedule in `/workspace/dc_deal`, complete the `Colocation_Leases` and `Deal_Rollup` schedules in the open **LibreOffice Calc** workbook (`Global_Capex_Model.xlsx`), and execute Section 9 contract redlines in the open **LibreOffice Writer** agreement (`Master_Services_Agreement.odt`):\n\n"
    "1. Review `/workspace/dc_deal/specs/DC_Procurement_Policy.pdf`, query `/workspace/dc_deal/procurement.sqlite` (`colocation_leases`), and inspect the **Procurement & Treasury Portal** open in Chromium (`http://127.0.0.1:19619`, `Overview` and `MSA Escalation & SLA` views).\n"
    "2. Applying the CPI escalator collar, hyperscale MW anchor discount, and SLA tier exposure caps from the policy and portal, compute 3-decimal MUSD `yr2_rent_musd` and `sla_reserve_musd` for `SITE-FRA1`..`SITE-OSA8`, and write `/workspace/dc_deal/lease_msa_audit.json` (`deal_stamp`, `yr2_rent_musd`, `sla_reserve_musd`, `total_yr2_lease_musd`, `mean_yr2_lease_musd`, `total_sla_reserve_musd`, `selected_lease_escrow_musd`).\n"
    "3. In the open **LibreOffice Calc** window (`Global_Capex_Model.xlsx`):\n"
    "   - On `Colocation_Leases`, enter `yr2_rent_musd` in `B2:B9` and `sla_reserve_musd` in `C2:C9`, enter `=SUM(...)` formulas in `B10` and `C10`, and enter `=AVERAGE(B2:B9)` in `B11`.\n"
    "   - On `Deal_Rollup`, enter `total_yr2_lease_musd` in `B3`, select the approved Colocation Security Escrow tier in `B5` so `Reserve_Coverage_Ratio` (`B6`) satisfies the portal's Treasury Reserve Covenant window, and save (`Ctrl+S`).\n"
    "4. In the open **LibreOffice Writer** window (`Master_Services_Agreement.odt`), replace `[REDLINE_S9_STAMP]`, `[REDLINE_YR2_LEASE_MUSD]` (3 decimals), and `[REDLINE_SUPERCAP_MULT]` with the verified closing values, and save (`Ctrl+S`).\n"
)


def compute_aw19_oracle() -> dict[str, Any]:
    cif_m: dict[str, float] = {}
    lnd_m: dict[str, float] = {}
    for pid, curr, hs, base_q, reb, fr_pct in CAPEX_PKGS:
        gross_usd = base_q * FX_DC[curr]
        elig_reb = reb if gross_usd >= 1200000.0 else 0.0
        cif_u = ((base_q - elig_reb) * (1.0 + fr_pct / 100.0)) * FX_DC[curr] / 1e6
        cif_m[pid] = round(cif_u, 3)
        lnd_m[pid] = round(cif_u * (1.0 + HS_DUTY_PCT[hs] / 100.0), 3)
    tot_cif = round(sum(cif_m.values()), 3)
    tot_lnd = round(sum(lnd_m.values()), 3)
    mean_lnd = round(tot_lnd / len(CAPEX_PKGS), 3)

    yr2_m: dict[str, float] = {}
    sla_m: dict[str, float] = {}
    for sid, curr, abase, rcpi, mw, tier in LEASE_SITES:
        ecpi = min(3.2, max(2.0, rcpi))
        anc = 0.96 if mw >= 8.0 else 1.00
        y2_r = round(abase * (1.0 + ecpi / 100.0) * anc * FX_DC[curr] / 1e6, 3)
        yr2_m[sid] = y2_r
        sla_m[sid] = round(y2_r * (SLA_TIER_CAP_PCT[tier] / 100.0), 3)
    tot_lease = round(sum(yr2_m.values()), 3)
    tot_sla = round(sum(sla_m.values()), 3)
    return {
        "deal_stamp": DEAL_STAMP,
        "cif_musd": cif_m,
        "landed_musd": lnd_m,
        "total_cif_musd": tot_cif,
        "total_landed_musd": tot_lnd,
        "mean_landed_musd": mean_lnd,
        "yr2_rent_musd": yr2_m,
        "sla_reserve_musd": sla_m,
        "total_yr2_lease_musd": tot_lease,
        "mean_yr2_lease_musd": round(tot_lease / len(LEASE_SITES), 3),
        "total_sla_reserve_musd": tot_sla,
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    dd = workspace_root / "shared" / "dc_deal"
    (dd / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)

    db_p = dd / "procurement.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute(
        "CREATE TABLE capex_packages (pkg_id TEXT PRIMARY KEY, currency TEXT, hs_class TEXT, base_quote_local REAL, oem_rebate_local REAL, freight_ins_pct REAL)"
    )
    con.executemany("INSERT INTO capex_packages VALUES (?,?,?,?,?,?)", CAPEX_PKGS)
    con.execute(
        "CREATE TABLE colocation_leases (site_id TEXT PRIMARY KEY, currency TEXT, annual_base_local REAL, raw_cpi_pct REAL, power_mw REAL, sla_tier TEXT)"
    )
    con.executemany("INSERT INTO colocation_leases VALUES (?,?,?,?,?,?)", LEASE_SITES)
    con.commit()
    con.close()

    write_multisheet_xlsx(
        seed / "Global_Capex_Model.xlsx",
        [
            (
                "Hardware_Capex",
                [
                    ["Package_ID", "CIF_Value_MUSD", "Landed_Capex_MUSD"],
                    *[[p[0], 0.0, 0.0] for p in CAPEX_PKGS],
                    ["TOTAL_CAPEX", 0.0, 0.0],
                    ["MEAN_LANDED_PKG", "", 0.0],
                ],
            ),
            (
                "Colocation_Leases",
                [
                    ["Site_ID", "Yr2_Escalated_Rent_MUSD", "SLA_Reserve_MUSD"],
                    *[[s[0], 0.0, 0.0] for s in LEASE_SITES],
                    ["TOTAL_COLOCATION", 0.0, 0.0],
                    ["MEAN_YR2_SITE_RENT", 0.0, ""],
                ],
            ),
            (
                "Deal_Rollup",
                [
                    ["Line_Item", "MUSD"],
                    ["Total_Landed_Capex_MUSD", 15.800],
                    ["Total_Yr2_Lease_MUSD", 10.800],
                    ["Selected_Capex_Buffer_MUSD", CAPEX_BUF_LOW],
                    ["Selected_Lease_Escrow_MUSD", LEASE_ESC_LOW],
                    ["Reserve_Coverage_Ratio", ("=ROUND((B4+B5)/(B2+B3),4)", 0.0921)],
                ],
            ),
        ],
    )

    write_odt_document(
        seed / "Master_Services_Agreement.odt",
        "Global Datacenter Master Services & Hardware Supply Agreement",
        [
            (
                "Section 4 — Hardware Capex & Warranty Schedule",
                [
                    "Section 4 Closing Stamp: [REDLINE_S4_STAMP]",
                    "Approved Landed Hardware Capex Ceiling ($M): [REDLINE_CAPEX_CEILING_MUSD]",
                    "OEM Hardware Replacement Warranty (Months): [REDLINE_OEM_WARRANTY_MOS]",
                ],
            ),
            (
                "Section 9 — Colocation Lease Commitment & Super-Cap Liability",
                [
                    "Section 9 Closing Stamp: [REDLINE_S9_STAMP]",
                    "Approved Year-2 Escalated Colocation Rent ($M): [REDLINE_YR2_LEASE_MUSD]",
                    "Data-Breach & Outage Super-Cap Multiple: [REDLINE_SUPERCAP_MULT]",
                ],
            ),
        ],
    )

    write_pdf_manual(
        dd / "specs" / "DC_Procurement_Policy.pdf",
        "Datacenter Capex & Colocation MSA Closing Policy",
        [
            (
                "1. Hardware Capex Rebate Eligibility, CIF & HS Customs Duty",
                [
                    "Convert base_quote_local to gross USD using the Portal spot FX table. OEM rebates (oem_rebate_local) are eligible ONLY when gross USD quote >= $1,200,000; packages below $1.20M receive zero rebate.",
                    "Unrounded CIF USD ($M) = ((base_quote_local - eligible_rebate_local) * (1 + freight_ins_pct / 100)) * fx / 1e6. Report cif_musd rounded to 3 decimals.",
                    "Apply the Portal HS tariff rate (hs_class) to unrounded CIF USD ($M): landed_musd = round(cif_unrounded_musd * (1 + hs_duty_pct / 100), 3). Total CIF and Total Landed equal the sum of the 8 rounded 3-decimal package rows.",
                ],
            ),
            (
                "2. Colocation Year-2 Escalator Collar, Anchor Discount & SLA Reserve",
                [
                    "Clamp raw_cpi_pct to the Portal CPI Escalator Collar [min_cpi_pct, max_cpi_pct]. Sites with power_mw >= 8.0 MW earn a 4.0% hyperscale anchor discount (multiply by 0.96).",
                    "yr2_rent_musd = round(annual_base_local * (1 + clamped_cpi_pct / 100) * anchor_mult * fx / 1e6, 3).",
                    "Each site's sla_reserve_musd = round(yr2_rent_musd * (portal_sla_tier_cap_pct / 100), 3). Total Year-2 Lease and Total SLA Reserve equal the sum of the 8 rounded rows.",
                ],
            ),
            (
                "3. Coupled Treasury Reserve Covenant on Deal_Rollup",
                [
                    "Deal_Rollup!B6 computes Reserve_Coverage_Ratio = ROUND((B4 + B5) / (B2 + B3), 4). At closing, Reserve_Coverage_Ratio MUST lie strictly inside the Portal's Treasury Covenant Window [0.1150, 0.1260] (below 0.1150 under-reserves counterparty risk; above 0.1260 traps excess treasury cash).",
                ],
            ),
        ],
    )
    (tickets_root / "dc_capex_controller").mkdir(parents=True, exist_ok=True)
    (tickets_root / "msa_commercial_counsel").mkdir(parents=True, exist_ok=True)
    (tickets_root / "dc_capex_controller" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "msa_commercial_counsel" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "overview", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw19_sess" in ck) and (ck["aw19_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw19_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Procurement Portal Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["overview"])[0]
                with lock:
                    if t in ("overview", "capex", "msa") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "overview":
                body = (
                    f"<h2>Closing Control Overview</h2>"
                    f"<p>Active Deal Stamp: <code>{DEAL_STAMP}</code></p>"
                    f"<p>Treasury Spot FX Schedule: <code>USD = 1.00, EUR = 1.08, SEK = 0.095, JPY = 0.0068</code></p>"
                    f"<p>Mandatory <code>Deal_Rollup!B6</code> Reserve Coverage Covenant Window: <code>[0.1150, 0.1260]</code></p>"
                )
            elif cur == "capex":
                body = (
                    f"<h2>FX &amp; Customs Tariff Schedule (<code>{DEAL_STAMP}</code>)</h2>"
                    f"<p>HS Tariff Rates: <code>IT_ITA_EXEMPT = 0.0%</code> | <code>CRAC_THERMAL = 4.5%</code> | <code>MV_SWITCHGEAR = 3.2%</code></p>"
                    f"<p>Approved Capex Buffer Tiers (<code>Deal_Rollup!B4</code>): <code>1.300</code> MUSD (Standard) or <code>2.050</code> MUSD (Accelerated)</p>"
                    f"<p>Approved Section 4 OEM Hardware Replacement Warranty: <code>{OEM_WARRANTY_MONTHS}</code> months</p>"
                )
            else:
                body = (
                    f"<h2>MSA Escalation &amp; SLA Terms (<code>{DEAL_STAMP}</code>)</h2>"
                    f"<p>Year-2 CPI Escalator Collar: <code>min = 2.0%, max = 3.2%</code> | Anchor Threshold: <code>&gt;= 8.0 MW -&gt; 4.0% discount</code></p>"
                    f"<p>SLA Credit Exposure Caps: <code>TIER_III = 9.0%</code> | <code>TIER_IV = 6.0%</code></p>"
                    f"<p>Approved Colocation Escrow Tiers (<code>Deal_Rollup!B5</code>): <code>1.150</code> MUSD (1-Mo) or <code>1.900</code> MUSD (2-Mo)</p>"
                    f"<p>Approved Section 9 Super-Cap Liability Multiple: <code>{SUPERCAP_MULTIPLE}</code></p>"
                )
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Procurement Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:22px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 15px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>Global Datacenter Procurement &amp; Treasury Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=overview">Overview</a><a href="/tab?id=capex">FX &amp; Customs Tariff</a><a href="/tab?id=msa">MSA Escalation &amp; SLA</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    boot_studio_browser(state_dir, window_size=(1160, 760))
    seed = workspace_root / "_desk_seed"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "Global_Capex_Model.xlsx", sp / "Global_Capex_Model.xlsx")
    shutil.copy2(seed / "Master_Services_Agreement.odt", sp / "Master_Services_Agreement.odt")
    launch_studio_app(
        "nohup libreoffice --norestore --nologo --nofirststartwizard "
        "'/srv/studio_project/Global_Capex_Model.xlsx' '/srv/studio_project/Master_Services_Agreement.odt' "
        ">/tmp/aw19_lo.log 2>&1 </dev/null &",
        wait_s=3.0,
    )


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    dd = workspace_root / "shared" / "dc_deal"
    sp = Path("/srv/studio_project")
    xlsx_p = sp / "Global_Capex_Model.xlsx"
    odt_p = sp / "Master_Services_Agreement.odt"
    ora = compute_aw19_oracle()
    if role == "dc_capex_controller":
        rows = [
            ["Package_ID", "CIF_Value_MUSD", "Landed_Capex_MUSD"],
            *[[p[0], ora["cif_musd"][p[0]], ora["landed_musd"][p[0]]] for p in CAPEX_PKGS],
            ["TOTAL_CAPEX", ("=SUM(B2:B9)", ora["total_cif_musd"]), ("=SUM(C2:C9)", ora["total_landed_musd"])],
            ["MEAN_LANDED_PKG", "", ("=AVERAGE(C2:C9)", ora["mean_landed_musd"])],
        ]
        if cooperative:
            with resource_lock("aw19_lo"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b3 = cell_float(bk, "Deal_Rollup", "B3") or 10.800
                b5 = cell_float(bk, "Deal_Rollup", "B5") or LEASE_ESC_LOW
                cb_sel = CAPEX_BUF_LOW if abs(b5 - LEASE_ESC_HIGH) < 0.2 else CAPEX_BUF_HIGH
                cov = round((cb_sel + b5) / (ora["total_landed_musd"] + b3), 4)
                update_single_sheet_xlsx(xlsx_p, "Hardware_Capex", rows)
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Deal_Rollup",
                    [
                        ["Line_Item", "MUSD"],
                        ["Total_Landed_Capex_MUSD", ora["total_landed_musd"]],
                        ["Total_Yr2_Lease_MUSD", b3],
                        ["Selected_Capex_Buffer_MUSD", cb_sel],
                        ["Selected_Lease_Escrow_MUSD", b5],
                        ["Reserve_Coverage_Ratio", ("=ROUND((B4+B5)/(B2+B3),4)", cov)],
                    ],
                )
                cur_t = read_odt_text(odt_p)
                s9 = [ln for ln in cur_t.splitlines() if SUPERCAP_MULTIPLE in ln or f"{ora['total_yr2_lease_musd']:.3f}" in ln] or [
                    "Section 9 Closing Stamp: [REDLINE_S9_STAMP]",
                    "Approved Year-2 Escalated Colocation Rent ($M): [REDLINE_YR2_LEASE_MUSD]",
                    "Data-Breach & Outage Super-Cap Multiple: [REDLINE_SUPERCAP_MULT]",
                ]
                write_odt_document(
                    odt_p,
                    "Global Datacenter Master Services & Hardware Supply Agreement",
                    [
                        (
                            "Section 4 — Hardware Capex & Warranty Schedule",
                            [
                                f"Section 4 Closing Stamp: {DEAL_STAMP}",
                                f"Approved Landed Hardware Capex Ceiling ($M): {ora['total_landed_musd']:.3f}",
                                f"OEM Hardware Replacement Warranty (Months): {OEM_WARRANTY_MONTHS}",
                            ],
                        ),
                        ("Section 9 — Colocation Lease Commitment & Super-Cap Liability", s9),
                    ],
                )
        else:
            cb_sel = CAPEX_BUF_HIGH
            write_multisheet_xlsx(xlsx_p, [("Hardware_Capex", rows)])
        write_json(
            dd / "capex_audit.json",
            {
                "deal_stamp": DEAL_STAMP,
                "cif_musd": ora["cif_musd"],
                "landed_musd": ora["landed_musd"],
                "total_cif_musd": ora["total_cif_musd"],
                "total_landed_musd": ora["total_landed_musd"],
                "mean_landed_musd": ora["mean_landed_musd"],
                "selected_capex_buffer_musd": cb_sel,
            },
        )
    elif role == "msa_commercial_counsel":
        rows = [
            ["Site_ID", "Yr2_Escalated_Rent_MUSD", "SLA_Reserve_MUSD"],
            *[[s[0], ora["yr2_rent_musd"][s[0]], ora["sla_reserve_musd"][s[0]]] for s in LEASE_SITES],
            ["TOTAL_COLOCATION", ("=SUM(B2:B9)", ora["total_yr2_lease_musd"]), ("=SUM(C2:C9)", ora["total_sla_reserve_musd"])],
            ["MEAN_YR2_SITE_RENT", ("=AVERAGE(B2:B9)", ora["mean_yr2_lease_musd"]), ""],
        ]
        if cooperative:
            with resource_lock("aw19_lo"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b2 = cell_float(bk, "Deal_Rollup", "B2") or 15.800
                b4 = cell_float(bk, "Deal_Rollup", "B4") or CAPEX_BUF_LOW
                le_sel = LEASE_ESC_LOW if abs(b4 - CAPEX_BUF_HIGH) < 0.2 else LEASE_ESC_HIGH
                cov = round((b4 + le_sel) / (b2 + ora["total_yr2_lease_musd"]), 4)
                update_single_sheet_xlsx(xlsx_p, "Colocation_Leases", rows)
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Deal_Rollup",
                    [
                        ["Line_Item", "MUSD"],
                        ["Total_Landed_Capex_MUSD", b2],
                        ["Total_Yr2_Lease_MUSD", ora["total_yr2_lease_musd"]],
                        ["Selected_Capex_Buffer_MUSD", b4],
                        ["Selected_Lease_Escrow_MUSD", le_sel],
                        ["Reserve_Coverage_Ratio", ("=ROUND((B4+B5)/(B2+B3),4)", cov)],
                    ],
                )
                cur_t = read_odt_text(odt_p)
                s4 = [ln for ln in cur_t.splitlines() if f" {OEM_WARRANTY_MONTHS}" in ln or f"{ora['total_landed_musd']:.3f}" in ln] or [
                    "Section 4 Closing Stamp: [REDLINE_S4_STAMP]",
                    "Approved Landed Hardware Capex Ceiling ($M): [REDLINE_CAPEX_CEILING_MUSD]",
                    "OEM Hardware Replacement Warranty (Months): [REDLINE_OEM_WARRANTY_MOS]",
                ]
                write_odt_document(
                    odt_p,
                    "Global Datacenter Master Services & Hardware Supply Agreement",
                    [
                        ("Section 4 — Hardware Capex & Warranty Schedule", s4),
                        (
                            "Section 9 — Colocation Lease Commitment & Super-Cap Liability",
                            [
                                f"Section 9 Closing Stamp: {DEAL_STAMP}",
                                f"Approved Year-2 Escalated Colocation Rent ($M): {ora['total_yr2_lease_musd']:.3f}",
                                f"Data-Breach & Outage Super-Cap Multiple: {SUPERCAP_MULTIPLE}",
                            ],
                        ),
                    ],
                )
        else:
            le_sel = LEASE_ESC_HIGH
            write_multisheet_xlsx(xlsx_p, [("Colocation_Leases", rows)])
        write_json(
            dd / "lease_msa_audit.json",
            {
                "deal_stamp": DEAL_STAMP,
                "yr2_rent_musd": ora["yr2_rent_musd"],
                "sla_reserve_musd": ora["sla_reserve_musd"],
                "total_yr2_lease_musd": ora["total_yr2_lease_musd"],
                "mean_yr2_lease_musd": ora["mean_yr2_lease_musd"],
                "total_sla_reserve_musd": ora["total_sla_reserve_musd"],
                "selected_lease_escrow_musd": le_sel,
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("dc_capex_controller", workspace_root, cooperative=False)
    solve_role("msa_commercial_counsel", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "dc_capex_controller", workspace_root, True)
        fb = pool.submit(solve_role, "msa_commercial_counsel", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    dd = workspace_root / "shared" / "dc_deal"
    sp = Path("/srv/studio_project")
    ora = compute_aw19_oracle()
    ja = read_json_safe(dd / "capex_audit.json")
    jb = read_json_safe(dd / "lease_msa_audit.json")
    book = evaluate_xlsx_isolated(sp / "Global_Capex_Model.xlsx")
    f_book = read_multisheet_xlsx(sp / "Global_Capex_Model.xlsx") if (sp / "Global_Capex_Model.xlsx").is_file() else {}
    odt_txt = read_odt_text(sp / "Master_Services_Agreement.odt")

    def _close(v: Any, exp: float, tol: float = 0.025) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    b6_cov = cell_float(book, "Deal_Rollup", "B6")
    cov_ok = (b6_cov is not None) and (0.1150 <= float(b6_cov) <= 0.1260)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", _close(ja.get("total_landed_musd"), ora["total_landed_musd"]) and _close(ja.get("total_cif_musd"), ora["total_cif_musd"]) and ja.get("deal_stamp") == DEAL_STAMP, 1.8, f"capex_audit.json mismatch (expected landed={ora['total_landed_musd']}, cif={ora['total_cif_musd']})"),
        *[(f"a_cif_{i}", _close(cell_float(book, "Hardware_Capex", f"B{i}"), ora["cif_musd"][p[0]]), 0.5, f"Hardware_Capex!B{i} CIF mismatch") for i, p in enumerate(CAPEX_PKGS, start=2)],
        *[(f"a_lnd_{i}", _close(cell_float(book, "Hardware_Capex", f"C{i}"), ora["landed_musd"][p[0]]), 0.7, f"Hardware_Capex!C{i} Landed mismatch") for i, p in enumerate(CAPEX_PKGS, start=2)],
        ("a_sum_bc10", "SUM" in cell_formula(f_book, "Hardware_Capex", "B10").upper() and "SUM" in cell_formula(f_book, "Hardware_Capex", "C10").upper() and _close(cell_float(book, "Hardware_Capex", "C10"), ora["total_landed_musd"], 0.04), 1.5, "Hardware_Capex!B10:C10 missing =SUM or wrong total"),
        ("a_avg_c11", "AVERAGE" in cell_formula(f_book, "Hardware_Capex", "C11").upper() and _close(cell_float(book, "Hardware_Capex", "C11"), ora["mean_landed_musd"], 0.02), 1.3, "Hardware_Capex!C11 missing =AVERAGE formula"),
        ("a_rollup_cov", _close(cell_float(book, "Deal_Rollup", "B2"), ora["total_landed_musd"], 0.04) and cov_ok, 1.8, f"Deal_Rollup!B2 or Reserve_Coverage_Ratio ({b6_cov}) outside [0.1150, 0.1260]"),
        ("a_writer_s4", "[REDLINE_S4_STAMP]" not in odt_txt and "[REDLINE_CAPEX_CEILING_MUSD]" not in odt_txt and "[REDLINE_OEM_WARRANTY_MOS]" not in odt_txt and f"{ora['total_landed_musd']:.3f}"[:5] in odt_txt and str(OEM_WARRANTY_MONTHS) in odt_txt, 2.0, "Writer MSA Section 4 missing Capex/42-mo warranty redlines"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", _close(jb.get("total_yr2_lease_musd"), ora["total_yr2_lease_musd"]) and _close(jb.get("total_sla_reserve_musd"), ora["total_sla_reserve_musd"]) and jb.get("deal_stamp") == DEAL_STAMP, 1.8, f"lease_msa_audit.json mismatch (expected yr2={ora['total_yr2_lease_musd']}, sla={ora['total_sla_reserve_musd']})"),
        *[(f"b_yr2_{i}", _close(cell_float(book, "Colocation_Leases", f"B{i}"), ora["yr2_rent_musd"][s[0]]), 0.7, f"Colocation_Leases!B{i} Yr2 mismatch") for i, s in enumerate(LEASE_SITES, start=2)],
        *[(f"b_sla_{i}", _close(cell_float(book, "Colocation_Leases", f"C{i}"), ora["sla_reserve_musd"][s[0]], 0.015), 0.5, f"Colocation_Leases!C{i} SLA reserve mismatch") for i, s in enumerate(LEASE_SITES, start=2)],
        ("b_sum_bc10", "SUM" in cell_formula(f_book, "Colocation_Leases", "B10").upper() and "SUM" in cell_formula(f_book, "Colocation_Leases", "C10").upper() and _close(cell_float(book, "Colocation_Leases", "B10"), ora["total_yr2_lease_musd"], 0.04), 1.5, "Colocation_Leases!B10:C10 missing =SUM or wrong total"),
        ("b_avg_b11", "AVERAGE" in cell_formula(f_book, "Colocation_Leases", "B11").upper() and _close(cell_float(book, "Colocation_Leases", "B11"), ora["mean_yr2_lease_musd"], 0.02), 1.3, "Colocation_Leases!B11 missing =AVERAGE formula"),
        ("b_rollup_cov", _close(cell_float(book, "Deal_Rollup", "B3"), ora["total_yr2_lease_musd"], 0.04) and cov_ok, 1.8, f"Deal_Rollup!B3 or Reserve_Coverage_Ratio ({b6_cov}) outside [0.1150, 0.1260]"),
        ("b_writer_s9", "[REDLINE_S9_STAMP]" not in odt_txt and "[REDLINE_YR2_LEASE_MUSD]" not in odt_txt and "[REDLINE_SUPERCAP_MULT]" not in odt_txt and f"{ora['total_yr2_lease_musd']:.3f}"[:5] in odt_txt and SUPERCAP_MULTIPLE in odt_txt, 2.0, "Writer MSA Section 9 missing Lease/2.75x supercap redlines"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_coupled_reserve_covenant_and_dual_redlines",
            cov_ok
            and _close(cell_float(book, "Deal_Rollup", "B2"), ora["total_landed_musd"], 0.04)
            and _close(cell_float(book, "Deal_Rollup", "B3"), ora["total_yr2_lease_musd"], 0.04)
            and "[REDLINE_CAPEX_CEILING_MUSD]" not in odt_txt
            and "[REDLINE_YR2_LEASE_MUSD]" not in odt_txt
            and SUPERCAP_MULTIPLE in odt_txt
            and str(OEM_WARRANTY_MONTHS) in odt_txt,
            2.5,
            f"Uncoordinated buffer/escrow selection pushed Reserve_Coverage_Ratio ({b6_cov}) outside [0.1150, 0.1260] or Writer/Calc lost peer redlines",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"dc_capex_controller": TICKET_A, "msa_commercial_counsel": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

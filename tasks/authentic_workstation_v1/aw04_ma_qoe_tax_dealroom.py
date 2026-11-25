"""AW-04: Project Helios M&A Closing Room — ASC 606 QoE EBITDA Bridge vs. NWC Peg, Sec. 382 Tax & Closing Wire."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    cell_float,
    convert_to_pdf_headless,
    evaluate_xlsx_isolated,
    extract_pdf_text,
    launch_desktop_app_as_user,
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
    "id": "AW-04",
    "slug": "ma_qoe_tax_dealroom",
    "title": "Project Helios M&A Closing Room: ASC 606 QoE EBITDA Bridge vs. NWC Peg, Sec. 382 Tax & Closing Wire",
    "domain": "M&A Due Diligence & SPA Closing (LibreOffice Calc + Writer + Chromium VDR + 480-Row SQLite GL)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19604,
    "roles": ("qoe_ebitda_lead", "tax_nwc_structuring_lead"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

AVG_FX_2025: dict[str, float] = {"USD": 1.0, "EUR": 1.075, "GBP": 1.255}
SPOT_FX_DEC31: dict[str, float] = {"USD": 1.0, "EUR": 1.125, "GBP": 1.310}
MARKET_RENT_MONTHLY_USD = 82500.0
LITIGATION_CAP_MUSD = 1.250
ASC350_BUGFIX_OVERCAP_MUSD = -0.680  # Routine maintenance R&D improperly capitalized; must be expensed!
EV_MULTIPLE = 11.5

ASC606_CONTRACTS: list[tuple[str, int, float]] = [
    ("SUP-Q4-01", 10, 480000.0),
    ("SUP-Q4-02", 10, 360000.0),
    ("SUP-Q4-03", 11, 600000.0),
    ("SUP-Q4-04", 11, 300000.0),
    ("SUP-Q4-05", 12, 720000.0),
    ("SUP-Q4-06", 12, 420000.0),
]

# (month_idx, cash, ar_gross, ic_ar_904, inv, prepaid, dta, ap, accr_payroll, def_rev_curr, st_debt, recon_memo)
NWC_MONTHLY: list[tuple[Any, ...]] = [
    ("2025-01", 6.2, 8.40, 0.65, 3.10, 1.15, 1.90, 4.20, 2.10, 2.00, 3.50, "Reconciled close"),
    ("2025-02", 6.5, 8.55, 0.65, 3.18, 1.12, 1.90, 4.35, 2.15, 2.05, 3.50, "Reconciled close"),
    ("2025-03", 6.8, 8.80, 0.70, 3.25, 1.20, 1.90, 4.40, 2.25, 2.10, 3.40, "Reconciled Q1 close"),
    ("2025-04", 6.4, 8.60, 0.70, 3.20, 1.18, 1.85, 4.28, 2.18, 2.10, 3.40, "Reconciled close"),
    ("2025-05", 6.9, 8.95, 0.75, 3.32, 1.22, 1.85, 4.50, 2.22, 2.15, 3.30, "Reconciled close"),
    ("2025-06", 7.1, 9.10, 0.75, 3.40, 1.25, 1.85, 4.62, 2.30, 2.20, 3.30, "Reconciled Q2 close"),
    ("2025-07", 7.0, 9.05, 0.80, 3.36, 1.24, 1.80, 4.55, 2.28, 2.20, 3.20, "Reconciled close"),
    ("2025-08", 7.2, 14.90, 0.80, 5.80, 1.26, 1.80, 2.10, 2.30, 2.25, 3.20, "Unrestated NetSuite migration batch duplicate"),
    ("2025-09", 7.4, 9.30, 0.80, 3.45, 1.28, 1.80, 4.70, 2.35, 2.30, 3.10, "Reconciled Q3 close"),
    ("2025-10", 7.6, 9.48, 0.85, 3.52, 1.30, 1.75, 4.82, 2.38, 2.35, 3.10, "Reconciled close"),
    ("2025-11", 7.9, 9.65, 0.85, 3.60, 1.34, 1.75, 4.90, 2.42, 2.40, 3.00, "Reconciled close"),
    ("2025-12", 8.3, 9.92, 0.90, 3.74, 1.38, 1.75, 4.98, 2.46, 2.50, 3.00, "Audited closing balance sheet"),
]

# (position_id, tax_year, gross_exposure_musd, prob_weight, audit_closed)
UTP_ROWS: list[tuple[str, int, float, float, int]] = [
    ("UTP-2021-RND", 2021, 1.80, 0.60, 1),  # Closed audit — exclude!
    ("UTP-2022-TP", 2022, 2.40, 0.55, 0),
    ("UTP-2023-SALT", 2023, 1.50, 0.40, 0),
    ("UTP-2024-PE", 2024, 2.10, 0.50, 0),
]

GROSS_DEBT_CLOSING_MUSD = 15.200
SELLER_TX_FEES_MUSD = 3.000  # Rev. Proc. 2011-29: 70% deductible at 21% federal rate -> $0.441M tax benefit reduces Net Debt!
ESCROW_ADMIN_FEE_MUSD = 0.185
VDR_DEAL_CODE = "HELIOS-SPA-2026-CLZ"
SEC382_EXEMPT_RATE = 0.0345
SEC382_BASE_MUSD = 180.0

TICKET_A = (
    "# Work Order — Quality of Earnings & Valuation Lead (`qoe_ebitda_lead`)\n\n"
    "Complete the FY2025 Quality-of-Earnings (QoE) Adjusted EBITDA bridge and Enterprise Value schedule in `/workspace/deal_room`:\n\n"
    "1. Review `/workspace/deal_room/specs/SPA_Accounting_Principles.pdf`, query `/workspace/deal_room/helios_gl_2025.sqlite` (`gl_operating_entries`, `contracts_asc606`, `cap_software_audit`, `fx_schedule`), and inspect the **Project Helios Virtual Data Room (VDR)** open in Chromium (`http://127.0.0.1:19604`, `Folder A`).\n"
    "2. Compute FY2025 Unadjusted Operating EBITDA in USD, then apply all four SPA QoE adjustments (ASC 606 Q4 support deferral `asc606_deferred_rev_adj_musd`, ASC 350-40 software over-capitalization reversal `asc350_overcap_reversal_musd`, related-party lease normalization `related_party_rent_addback_musd`, and capped litigation add-back `litigation_capped_addback_musd`), yielding `adjusted_ebitda_musd` and `enterprise_value_musd`.\n"
    "3. Update the `QoE_EBITDA` sheet and cell `B2` (`Enterprise_Value_MUSD`) on `Closing_Wire_Summary` inside `/workspace/deal_room/SPA_Closing_Model.xlsx` (preserving all sibling sheets and `B3:B7` formulas/values!).\n"
    "4. Update the QoE section of `/workspace/deal_room/IC_Closing_Memo.odt` (preserving any NWC/Tax/Wire section; if `IC_Closing_Memo.pdf` already exists, refresh it), and write `/workspace/deal_room/qoe_diligence_pack.json` with:\n"
    "   - `vdr_deal_code`, `unadjusted_ebitda_musd`, `asc606_deferred_rev_adj_musd`, `asc350_overcap_reversal_musd`\n"
    "   - `related_party_rent_addback_musd`, `litigation_capped_addback_musd`\n"
    "   - `adjusted_ebitda_musd`, `enterprise_value_musd`\n"
)

TICKET_B = (
    "# Work Order — Tax, Net Working Capital & SPA Closing Lead (`tax_nwc_structuring_lead`)\n\n"
    "Complete the SPA Exhibit C Net Working Capital (NWC) peg, IRC Sec. 382 & UTP tax indemnity schedule, and closing wire waterfall in `/workspace/deal_room`:\n\n"
    "1. Review `/workspace/deal_room/specs/SPA_Accounting_Principles.pdf`, query `/workspace/deal_room/helios_gl_2025.sqlite` (`working_capital_monthly`, `utp_tax_positions`), and inspect the **Project Helios VDR** in Chromium (`http://127.0.0.1:19604`, `Folder B`).\n"
    "2. Compute monthly SPA Exhibit C Defined NWC for 2025 (applying the deferred-revenue cost-to-fulfill rule, intercompany elimination, and unrestated migration month exclusion) to obtain `nwc_peg_musd`, `closing_nwc_musd` (`2025-12`), and `nwc_closing_adjustment_musd`.\n"
    "3. Compute `sec382_annual_cap_musd`, open-audit `utp_tax_holdback_musd`, and SPA Closing `net_debt_musd` (net of the Rev. Proc. 2011-29 transaction tax benefit per VDR Folder B!), then update `NWC_Tax_Schedule` and `Closing_Wire_Summary` cells `B3:B6` (preserving `B2` and formula `B7`!) in `/workspace/deal_room/SPA_Closing_Model.xlsx`.\n"
    "4. Update the NWC, Tax & Wire section of `/workspace/deal_room/IC_Closing_Memo.odt` (preserving any QoE section!), export `/workspace/deal_room/IC_Closing_Memo.pdf`, and write `/workspace/deal_room/tax_nwc_closing_pack.json` with:\n"
    "   - `vdr_deal_code`, `nwc_peg_musd`, `closing_nwc_musd`, `nwc_closing_adjustment_musd`\n"
    "   - `sec382_annual_cap_musd`, `utp_tax_holdback_musd`, `net_debt_musd`, `escrow_admin_fee_musd`\n"
)


def _generate_gl_entries() -> list[tuple[int, str, str, str, float, float]]:
    """Generate 480 deterministic journal entries across 12 months x 40 entries."""
    rows: list[tuple[int, str, str, str, float, float]] = []
    eid = 1000
    for m in range(1, 13):
        ym = f"2025-{m:02d}"
        # 18 SaaS revenue entries across USD (10), EUR (5), GBP (3)
        for k in range(10):
            eid += 1
            rows.append((eid, ym, "SaaS_Recurring_Rev", "USD", 185000.0 + 3000.0 * m + 1200.0 * k, 1.0))
        for k in range(5):
            eid += 1
            rows.append((eid, ym, "SaaS_Recurring_Rev", "EUR", 92000.0 + 1500.0 * m + 800.0 * k, SPOT_FX_DEC31["EUR"]))
        for k in range(3):
            eid += 1
            rows.append((eid, ym, "SaaS_Recurring_Rev", "GBP", 64000.0 + 1000.0 * m + 600.0 * k, SPOT_FX_DEC31["GBP"]))
        # 8 Cloud COGS entries (negative = expense)
        for k in range(6):
            eid += 1
            rows.append((eid, ym, "COGS_Cloud", "USD", -(46000.0 + 500.0 * m + 400.0 * k), 1.0))
        for k in range(2):
            eid += 1
            rows.append((eid, ym, "COGS_Cloud", "EUR", -(28000.0 + 300.0 * m + 250.0 * k), SPOT_FX_DEC31["EUR"]))
        # 10 Payroll R&D & G&A entries
        for k in range(7):
            eid += 1
            rows.append((eid, ym, "Payroll_RD_GA", "USD", -(98000.0 + 900.0 * m + 500.0 * k), 1.0))
        for k in range(3):
            eid += 1
            rows.append((eid, ym, "Payroll_RD_GA", "GBP", -(41000.0 + 400.0 * m + 300.0 * k), SPOT_FX_DEC31["GBP"]))
        # 1 Related-party warehouse rent ($135,000/mo USD)
        eid += 1
        rows.append((eid, ym, "Related_Party_Warehouse_Rent", "USD", -135000.0, 1.0))
        # 2 Depreciation & Amortization entries (excluded from EBITDA)
        for k in range(2):
            eid += 1
            rows.append((eid, ym, "Depreciation_Amortization", "USD", -(52000.0 + 200.0 * k), 1.0))
        # 1 Monthly legal/upfront slot -> in months 10..12 book Q4 upfront support & litigation
        eid += 1
        if m == 6:
            rows.append((eid, ym, "Litigation_Settlement_OneTime", "USD", -1950000.0, 1.0))
        elif m == 10:
            rows.append((eid, ym, "Upfront_24Mo_Support_Q4", "USD", 840000.0, 1.0))
        elif m == 11:
            rows.append((eid, ym, "Upfront_24Mo_Support_Q4", "USD", 900000.0, 1.0))
        elif m == 12:
            rows.append((eid, ym, "Upfront_24Mo_Support_Q4", "USD", 1140000.0, 1.0))
        else:
            rows.append((eid, ym, "General_Admin_Misc", "USD", -18500.0, 1.0))
    return rows


def compute_dealroom_oracle() -> dict[str, Any]:
    gl = _generate_gl_entries()
    unadj_usd = 0.0
    for _id, _ym, acct, curr, amt_loc, _spot in gl:
        if acct == "Depreciation_Amortization":
            continue
        unadj_usd += amt_loc * AVG_FX_2025[curr]
    unadj_musd = round(unadj_usd / 1e6, 3)

    unearned_usd = 0.0
    for _cid, s_mo, billed_usd in ASC606_CONTRACTS:
        earned_mos = 13 - s_mo  # Oct=3, Nov=2, Dec=1
        unearned_usd += billed_usd * ((24.0 - earned_mos) / 24.0)
    asc606_adj_musd = round(-unearned_usd / 1e6, 3)
    rent_addback_musd = round(((135000.0 - MARKET_RENT_MONTHLY_USD) * 12.0) / 1e6, 3)
    lit_addback_musd = LITIGATION_CAP_MUSD

    adj_ebitda_musd = round(
        unadj_musd + asc606_adj_musd + ASC350_BUGFIX_OVERCAP_MUSD + rent_addback_musd + lit_addback_musd, 3
    )
    ev_musd = round(EV_MULTIPLE * adj_ebitda_musd, 3)

    clean_nwcs: list[float] = []
    closing_nwc = 0.0
    for ym, _cash, ar, ic_ar, inv, prep, _dta, ap, accr, def_rev, _debt, memo in NWC_MONTHLY:
        # SPA Exhibit C: current deferred revenue included at 35% cost-to-fulfill liability!
        nwc_m = round((ar - ic_ar + inv + prep) - (ap + accr + 0.35 * def_rev), 4)
        if "Unrestated" not in memo:
            clean_nwcs.append(nwc_m)
        if ym == "2025-12":
            closing_nwc = round(nwc_m, 3)
    nwc_peg = round(sum(clean_nwcs) / len(clean_nwcs), 3)
    nwc_adj = round(closing_nwc - nwc_peg, 3)

    sec382_cap = round(SEC382_BASE_MUSD * SEC382_EXEMPT_RATE, 3)
    utp_holdback = round(sum(gross * wt for _pid, _yr, gross, wt, closed in UTP_ROWS if closed == 0), 3)
    tx_tax_shield = round(SELLER_TX_FEES_MUSD * 0.70 * 0.21, 3)  # $0.441M
    net_debt_adj = round(GROSS_DEBT_CLOSING_MUSD - tx_tax_shield, 3)
    net_wire = round(ev_musd - net_debt_adj + nwc_adj - utp_holdback - ESCROW_ADMIN_FEE_MUSD, 3)

    return {
        "vdr_deal_code": VDR_DEAL_CODE,
        "unadjusted_ebitda_musd": unadj_musd,
        "asc606_deferred_rev_adj_musd": asc606_adj_musd,
        "asc350_overcap_reversal_musd": ASC350_BUGFIX_OVERCAP_MUSD,
        "related_party_rent_addback_musd": rent_addback_musd,
        "litigation_capped_addback_musd": lit_addback_musd,
        "adjusted_ebitda_musd": adj_ebitda_musd,
        "enterprise_value_musd": ev_musd,
        "nwc_peg_musd": nwc_peg,
        "closing_nwc_musd": closing_nwc,
        "nwc_closing_adjustment_musd": nwc_adj,
        "sec382_annual_cap_musd": sec382_cap,
        "utp_tax_holdback_musd": utp_holdback,
        "net_debt_musd": net_debt_adj,
        "escrow_admin_fee_musd": ESCROW_ADMIN_FEE_MUSD,
        "net_closing_wire_musd": net_wire,
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    dr = workspace_root / "shared" / "deal_room"
    (dr / "specs").mkdir(parents=True, exist_ok=True)

    db_p = dr / "helios_gl_2025.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute(
        "CREATE TABLE gl_operating_entries (entry_id INTEGER PRIMARY KEY, year_month TEXT, account TEXT, "
        "currency TEXT, amount_local REAL, ref_fx_rate REAL)"
    )
    con.executemany("INSERT INTO gl_operating_entries VALUES (?,?,?,?,?,?)", _generate_gl_entries())
    con.execute("CREATE TABLE fx_schedule (currency TEXT, rate_basis TEXT, usd_per_unit REAL)")
    for c_k in ("USD", "EUR", "GBP"):
        con.execute("INSERT INTO fx_schedule VALUES (?,?,?)", (c_k, "spot_close", SPOT_FX_DEC31[c_k]))
        con.execute("INSERT INTO fx_schedule VALUES (?,?,?)", (c_k, "monthly_avg", AVG_FX_2025[c_k]))
    con.execute(
        "CREATE TABLE cap_software_audit (project_code TEXT PRIMARY KEY, capitalized_2025_usd REAL, stage_classification TEXT)"
    )
    con.executemany(
        "INSERT INTO cap_software_audit VALUES (?,?,?)",
        [
            ("SW-CORE-40", 1420000.0, "application_development_eligible"),
            ("SW-MAINT-19", 410000.0, "post_release_bugfix_maintenance"),
            ("SW-PATCH-22", 270000.0, "post_release_bugfix_maintenance"),
        ],
    )
    con.execute(
        "CREATE TABLE contracts_asc606 (contract_id TEXT PRIMARY KEY, start_month_2025 INTEGER, upfront_billed_usd REAL)"
    )
    con.executemany("INSERT INTO contracts_asc606 VALUES (?,?,?)", ASC606_CONTRACTS)
    con.execute(
        "CREATE TABLE working_capital_monthly (year_month TEXT PRIMARY KEY, cash_musd REAL, accounts_receivable_musd REAL, "
        "intercompany_ar_ic904_musd REAL, inventory_musd REAL, prepaid_expenses_musd REAL, deferred_tax_asset_musd REAL, "
        "accounts_payable_musd REAL, accrued_payroll_musd REAL, deferred_revenue_current_musd REAL, short_term_debt_musd REAL, reconciliation_memo TEXT)"
    )
    con.executemany("INSERT INTO working_capital_monthly VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", NWC_MONTHLY)
    con.execute(
        "CREATE TABLE utp_tax_positions (position_id TEXT PRIMARY KEY, tax_year INTEGER, gross_exposure_musd REAL, "
        "reserve_probability_weight REAL, audit_closed INTEGER)"
    )
    con.executemany("INSERT INTO utp_tax_positions VALUES (?,?,?,?,?)", UTP_ROWS)
    con.commit()
    con.close()

    write_multisheet_xlsx(
        dr / "SPA_Closing_Model.xlsx",
        [
            (
                "QoE_EBITDA",
                [
                    ["Line_Item", "Amount_MUSD"],
                    ["Unadjusted_Operating_EBITDA", 0.0],
                    ["ASC606_Deferred_Rev_Adj", 0.0],
                    ["Related_Party_Rent_Addback", 0.0],
                    ["Litigation_Capped_Addback", 0.0],
                    ["ASC350_OverCap_Reversal", 0.0],
                    ["Adjusted_EBITDA", ("=SUM(B2:B6)", 0.0)],
                    ["Enterprise_Value_11_5x", ("=ROUND(11.5*B7,3)", 0.0)],
                ],
            ),
            (
                "NWC_Tax_Schedule",
                [
                    ["Metric", "Amount_MUSD"],
                    ["LTM_Clean_NWC_Peg", 0.0],
                    ["Closing_NWC_2025_12", 0.0],
                    ["NWC_Closing_Adjustment", ("=B3-B2", 0.0)],
                    ["Sec382_Annual_Cap", 0.0],
                    ["UTP_Open_Holdback", 0.0],
                ],
            ),
            (
                "Closing_Wire_Summary",
                [
                    ["Waterfall_Component", "Amount_MUSD"],
                    ["Enterprise_Value_MUSD", 0.0],
                    ["Net_Debt_MUSD", 0.0],
                    ["NWC_Closing_Adjustment_MUSD", 0.0],
                    ["UTP_Tax_Holdback_MUSD", 0.0],
                    ["Escrow_Admin_Fee_MUSD", 0.0],
                    ["Net_Closing_Wire_MUSD", ("=B2-B3+B4-B5-B6", 0.0)],
                ],
            ),
        ],
    )

    write_odt_document(
        dr / "IC_Closing_Memo.odt",
        "Project Helios Investment Committee Closing Memorandum",
        [
            ("Section 1 — Quality of Earnings & Valuation", ["QoE Status: PENDING_QOE_BRIDGE"]),
            ("Section 2 — NWC Peg, Tax Holdback & Closing Wire", ["Tax & Wire Status: PENDING_TAX_NWC"]),
        ],
    )

    write_pdf_manual(
        dr / "specs" / "SPA_Accounting_Principles.pdf",
        "Project Helios Stock Purchase Agreement — Accounting & Tax Exhibits",
        [
            (
                "1. Foreign Currency Translation & Operating EBITDA Baseline",
                [
                    "gl_operating_entries records revenues as positive amounts and expenses as negative amounts. Exclude Depreciation_Amortization from Operating EBITDA.",
                    "Note that gl_operating_entries.ref_fx_rate stores year-end spot rates; translate P&L entries using the 'monthly_avg' rate_basis in fx_schedule (verified in VDR Folder A). Round MUSD bridge lines to 3 decimal places.",
                ],
            ),
            (
                "2. Four Mandatory SPA QoE Adjustments & 11.5x EV Multiple",
                [
                    "(a) ASC 606 24-Month Support Deferral: contracts in contracts_asc606 were booked 100% into Upfront_24Mo_Support_Q4 upon billing. In FY2025, a contract starting in month m (10, 11, or 12) earns (13 - m) / 24 of its billed fee; defer (subtract) the remaining (24 - (13 - m)) / 24 unearned portion.",
                    "(b) ASC 350-40 Software Capitalization Audit: review cap_software_audit and reverse (expense as a negative EBITDA adjustment) any capitalized 2025 spend classified as 'post_release_bugfix_maintenance'.",
                    "(c) Related-Party Lease Normalization: Helios paid $135,000/month ($1.620M/yr) on Related_Party_Warehouse_Rent; normalize to the CBRE market rent appraisal in VDR Folder A, adding back excess rent.",
                    "(d) Schedule 1.1(b) Litigation Add-Back Cap: one-time litigation settlements in GL ($1.950M) are add-back eligible only up to the cap in VDR Folder A. Enterprise Value = round(11.5 * Adjusted_EBITDA, 3).",
                ],
            ),
            (
                "3. SPA Exhibit C Net Working Capital (NWC) Peg & ERP Cutover Exclusion",
                [
                    "Defined NWC = (accounts_receivable_musd - intercompany_ar_ic904_musd + inventory_musd + prepaid_expenses_musd) - (accounts_payable_musd + accrued_payroll_musd + 0.35 * deferred_revenue_current_musd). Current deferred revenue is included solely at its 35% direct fulfillment cost obligation; exclude cash, deferred tax assets, and short-term debt, and eliminate intercompany IC-904.",
                    "Per VDR Folder B Addendum #3, omit any monthly row whose reconciliation_memo indicates an unrestated migration anomaly when computing the LTM arithmetic mean nwc_peg_musd. Closing NWC uses 2025-12.",
                ],
            ),
            (
                "4. IRC Sec. 382 Limitation, UTP Holdback & Closing Wire Waterfall",
                [
                    "IRC Sec. 382 annual post-change NOL cap: sec382_annual_cap_musd = round(equity_purchase_base_musd * long_term_tax_exempt_rate, 3) using VDR Folder B parameters.",
                    "Special Tax Escrow Holdback: sum(gross_exposure_musd * reserve_probability_weight) across open-audit utp_tax_positions only (audit_closed = 0).",
                    "SPA Closing Indebtedness (Net_Debt_MUSD): reduce Gross Closing Debt by the Rev. Proc. 2011-29 Transaction Tax Benefit (70% safe-harbor deductible fraction of Seller Transaction Fees multiplied by the 21% federal corporate tax rate, per VDR Folder B). Closing_Wire_Summary!B7 = Enterprise_Value_MUSD - Net_Debt_MUSD + NWC_Closing_Adjustment_MUSD - UTP_Tax_Holdback_MUSD - Escrow_Admin_Fee_MUSD.",
                ],
            ),
        ],
    )

    (tickets_root / "qoe_ebitda_lead").mkdir(parents=True, exist_ok=True)
    (tickets_root / "tax_nwc_structuring_lead").mkdir(parents=True, exist_ok=True)
    (tickets_root / "qoe_ebitda_lead" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "tax_nwc_structuring_lead" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_folder": "folder_a", "folder_switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw04_sess" in ck) and (ck["aw04_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw04_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Project Helios VDR Session Required (Inspect open Chromium)</h3>")
                return
            if parsed.path == "/folder":
                f_id = (qs.get("id") or ["folder_a"])[0]
                with lock:
                    if f_id in ("folder_a", "folder_b") and f_id != state["active_folder"]:
                        state["active_folder"] = f_id
                        state["folder_switches"] = int(state["folder_switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return

            with lock:
                cur = state["active_folder"]
            if cur == "folder_a":
                body = f"""
                <h2>Folder A — QoE Independent Appraisal &amp; FY2025 Average FX Schedule</h2>
                <p><b>VDR Deal Control Code:</b> <code>{VDR_DEAL_CODE}</code></p>
                <ul style="line-height:1.9;font-size:16px;margin-top:12px;">
                  <li><b>FY2025 Monthly Average FX Rates (P&amp;L Translation):</b> <code>USD = 1.000</code>, <code>EUR = 1.075</code>, <code>GBP = 1.255</code></li>
                  <li><b>CBRE Fair-Market Warehouse Lease Appraisal:</b> <code>$82,500 / month</code> ($0.990M / year vs. $135,000 / month related-party billing)</li>
                  <li><b>SPA Headline Valuation Multiple:</b> <code>11.5x Adjusted EBITDA</code> | <b>Litigation Add-Back Cap:</b> <code>$1.250M</code></li>
                </ul>"""
            else:
                body = f"""
                <h2>Folder B — SPA Tax Addendum, NWC Cutover Ruling &amp; Wire Schedule</h2>
                <p><b>VDR Deal Control Code:</b> <code>{VDR_DEAL_CODE}</code></p>
                <ul style="line-height:1.9;font-size:16px;margin-top:12px;">
                  <li><b>Addendum #3 (NetSuite Cutover):</b> Exclude any monthly NWC row flagged as unrestated in <code>reconciliation_memo</code> from the LTM NWC Peg mean; include <code>deferred_revenue_current_musd</code> at <code>35%</code> fulfillment obligation.</li>
                  <li><b>IRC Sec. 382 Parameters:</b> <code>equity_purchase_base_musd = 180.0</code>, <code>long_term_tax_exempt_rate = 3.45% (0.0345)</code></li>
                  <li><b>Closing Indebtedness &amp; Rev. Proc. 2011-29 Tax Shield:</b> <code>Gross_Closing_Debt_MUSD = {GROSS_DEBT_CLOSING_MUSD:.3f}</code>, <code>Seller_Transaction_Fees_MUSD = {SELLER_TX_FEES_MUSD:.3f}</code> (70% safe-harbor deductible @ 21% tax rate offsets Gross Debt), <code>Escrow_Admin_Fee_MUSD = {ESCROW_ADMIN_FEE_MUSD:.3f}</code></li>
                </ul>"""

            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Project Helios VDR</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;color:#0f172a;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#1e293b;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .panel{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>Project Helios Virtual Data Room ({cur.upper()})</h1>
            <div class="nav">
              <a href="/folder?id=folder_a">Folder A: QoE Appraisal &amp; FX Schedule</a>
              <a href="/folder?id=folder_b">Folder B: SPA Tax, NWC Addendum &amp; Wire Fees</a>
            </div>
            <div class="panel">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1240, 820))
    dr = workspace_root / "shared" / "deal_room"
    if roles & {"qoe_ebitda_lead", "tax_nwc_structuring_lead"}:
        launch_desktop_app_as_user(
            f"nohup libreoffice --norestore --nologo --nofirststartwizard '{dr / 'SPA_Closing_Model.xlsx'}' '{dr / 'IC_Closing_Memo.odt'}' >/tmp/aw04_lo.log 2>&1 </dev/null &",
            wait_s=2.8,
        )


def _merge_wire_sheet(xlsx_path: Path, updates: dict[str, float]) -> None:
    book = evaluate_xlsx_isolated(xlsx_path)
    cur = {
        "Enterprise_Value_MUSD": cell_float(book, "Closing_Wire_Summary", "B2") or 0.0,
        "Net_Debt_MUSD": cell_float(book, "Closing_Wire_Summary", "B3") or 0.0,
        "NWC_Closing_Adjustment_MUSD": cell_float(book, "Closing_Wire_Summary", "B4") or 0.0,
        "UTP_Tax_Holdback_MUSD": cell_float(book, "Closing_Wire_Summary", "B5") or 0.0,
        "Escrow_Admin_Fee_MUSD": cell_float(book, "Closing_Wire_Summary", "B6") or 0.0,
    }
    cur.update(updates)
    net_v = round(
        cur["Enterprise_Value_MUSD"]
        - cur["Net_Debt_MUSD"]
        + cur["NWC_Closing_Adjustment_MUSD"]
        - cur["UTP_Tax_Holdback_MUSD"]
        - cur["Escrow_Admin_Fee_MUSD"],
        3,
    )
    update_single_sheet_xlsx(
        xlsx_path,
        "Closing_Wire_Summary",
        [
            ["Waterfall_Component", "Amount_MUSD"],
            ["Enterprise_Value_MUSD", cur["Enterprise_Value_MUSD"]],
            ["Net_Debt_MUSD", cur["Net_Debt_MUSD"]],
            ["NWC_Closing_Adjustment_MUSD", cur["NWC_Closing_Adjustment_MUSD"]],
            ["UTP_Tax_Holdback_MUSD", cur["UTP_Tax_Holdback_MUSD"]],
            ["Escrow_Admin_Fee_MUSD", cur["Escrow_Admin_Fee_MUSD"]],
            ["Net_Closing_Wire_MUSD", ("=B2-B3+B4-B5-B6", net_v)],
        ],
    )


def _merge_ic_memo(odt_path: Path, sec1_lines: list[str] | None, sec2_lines: list[str] | None, cooperative: bool) -> None:
    existing = read_odt_text(odt_path) if cooperative else ""
    s1 = sec1_lines
    s2 = sec2_lines
    if s1 is None:
        s1 = [ln for ln in existing.splitlines() if "EBITDA" in ln or "Enterprise Value" in ln or "PENDING_QOE" in ln] or ["QoE Status: PENDING_QOE_BRIDGE"]
    if s2 is None:
        s2 = [ln for ln in existing.splitlines() if "NWC" in ln or "Sec. 382" in ln or "UTP" in ln or "PENDING_TAX" in ln] or ["Tax & Wire Status: PENDING_TAX_NWC"]
    write_odt_document(
        odt_path,
        f"Project Helios IC Closing Memo ({VDR_DEAL_CODE})",
        [
            ("Section 1 — Quality of Earnings & Valuation", s1),
            ("Section 2 — NWC Peg, Tax Holdback & Closing Wire", s2),
        ],
    )


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    dr = workspace_root / "shared" / "deal_room"
    xlsx_p = dr / "SPA_Closing_Model.xlsx"
    odt_p = dr / "IC_Closing_Memo.odt"
    ora = compute_dealroom_oracle()
    if role == "qoe_ebitda_lead":
        qoe_rows = [
            ["Line_Item", "Amount_MUSD"],
            ["Unadjusted_Operating_EBITDA", ora["unadjusted_ebitda_musd"]],
            ["ASC606_Deferred_Rev_Adj", ora["asc606_deferred_rev_adj_musd"]],
            ["Related_Party_Rent_Addback", ora["related_party_rent_addback_musd"]],
            ["Litigation_Capped_Addback", ora["litigation_capped_addback_musd"]],
            ["ASC350_OverCap_Reversal", ora["asc350_overcap_reversal_musd"]],
            ["Adjusted_EBITDA", ("=SUM(B2:B6)", ora["adjusted_ebitda_musd"])],
            ["Enterprise_Value_11_5x", ("=ROUND(11.5*B7,3)", ora["enterprise_value_musd"])],
        ]
        s1_lines = [
            f"Adjusted EBITDA: ${ora['adjusted_ebitda_musd']:.3f}M (Unadjusted ${ora['unadjusted_ebitda_musd']:.3f}M, ASC606 ${ora['asc606_deferred_rev_adj_musd']:.3f}M)",
            f"Enterprise Value (11.5x): ${ora['enterprise_value_musd']:.3f}M | Deal Code: {VDR_DEAL_CODE}",
        ]
        if cooperative:
            with resource_lock("aw04_docs"):
                update_single_sheet_xlsx(xlsx_p, "QoE_EBITDA", qoe_rows)
                _merge_wire_sheet(xlsx_p, {"Enterprise_Value_MUSD": ora["enterprise_value_musd"]})
                _merge_ic_memo(odt_p, s1_lines, None, cooperative=True)
                if (dr / "IC_Closing_Memo.pdf").is_file():
                    convert_to_pdf_headless(odt_p, dr / "IC_Closing_Memo.pdf")
        else:
            write_multisheet_xlsx(xlsx_p, [("QoE_EBITDA", qoe_rows)])
            _merge_ic_memo(odt_p, s1_lines, None, cooperative=False)
        write_json(
            dr / "qoe_diligence_pack.json",
            {
                "vdr_deal_code": VDR_DEAL_CODE,
                "unadjusted_ebitda_musd": ora["unadjusted_ebitda_musd"],
                "asc606_deferred_rev_adj_musd": ora["asc606_deferred_rev_adj_musd"],
                "asc350_overcap_reversal_musd": ora["asc350_overcap_reversal_musd"],
                "related_party_rent_addback_musd": ora["related_party_rent_addback_musd"],
                "litigation_capped_addback_musd": ora["litigation_capped_addback_musd"],
                "adjusted_ebitda_musd": ora["adjusted_ebitda_musd"],
                "enterprise_value_musd": ora["enterprise_value_musd"],
            },
        )
    elif role == "tax_nwc_structuring_lead":
        nwc_rows = [
            ["Metric", "Amount_MUSD"],
            ["LTM_Clean_NWC_Peg", ora["nwc_peg_musd"]],
            ["Closing_NWC_2025_12", ora["closing_nwc_musd"]],
            ["NWC_Closing_Adjustment", ("=B3-B2", ora["nwc_closing_adjustment_musd"])],
            ["Sec382_Annual_Cap", ora["sec382_annual_cap_musd"]],
            ["UTP_Open_Holdback", ora["utp_tax_holdback_musd"]],
        ]
        s2_lines = [
            f"NWC Peg: ${ora['nwc_peg_musd']:.3f}M | Closing NWC: ${ora['closing_nwc_musd']:.3f}M | NWC Adj: ${ora['nwc_closing_adjustment_musd']:.3f}M",
            f"Sec. 382 Annual Cap: ${ora['sec382_annual_cap_musd']:.3f}M | UTP Holdback: ${ora['utp_tax_holdback_musd']:.3f}M | Deal Code: {VDR_DEAL_CODE}",
        ]
        if cooperative:
            with resource_lock("aw04_docs"):
                update_single_sheet_xlsx(xlsx_p, "NWC_Tax_Schedule", nwc_rows)
                _merge_wire_sheet(
                    xlsx_p,
                    {
                        "Net_Debt_MUSD": ora["net_debt_musd"],
                        "NWC_Closing_Adjustment_MUSD": ora["nwc_closing_adjustment_musd"],
                        "UTP_Tax_Holdback_MUSD": ora["utp_tax_holdback_musd"],
                        "Escrow_Admin_Fee_MUSD": ora["escrow_admin_fee_musd"],
                    },
                )
                _merge_ic_memo(odt_p, None, s2_lines, cooperative=True)
                convert_to_pdf_headless(odt_p, dr / "IC_Closing_Memo.pdf")
        else:
            write_multisheet_xlsx(xlsx_p, [("NWC_Tax_Schedule", nwc_rows)])
            _merge_ic_memo(odt_p, None, s2_lines, cooperative=False)
            convert_to_pdf_headless(odt_p, dr / "IC_Closing_Memo.pdf")
        write_json(
            dr / "tax_nwc_closing_pack.json",
            {
                "vdr_deal_code": VDR_DEAL_CODE,
                "nwc_peg_musd": ora["nwc_peg_musd"],
                "closing_nwc_musd": ora["closing_nwc_musd"],
                "nwc_closing_adjustment_musd": ora["nwc_closing_adjustment_musd"],
                "sec382_annual_cap_musd": ora["sec382_annual_cap_musd"],
                "utp_tax_holdback_musd": ora["utp_tax_holdback_musd"],
                "net_debt_musd": ora["net_debt_musd"],
                "escrow_admin_fee_musd": ora["escrow_admin_fee_musd"],
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("qoe_ebitda_lead", workspace_root, cooperative=False)
    solve_role("tax_nwc_structuring_lead", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "qoe_ebitda_lead", workspace_root, True)
        fb = pool.submit(solve_role, "tax_nwc_structuring_lead", workspace_root, True)
        fa.result()
        fb.result()
    dr = workspace_root / "shared" / "deal_room"
    with resource_lock("aw04_docs"):
        convert_to_pdf_headless(dr / "IC_Closing_Memo.odt", dr / "IC_Closing_Memo.pdf")


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    dr = workspace_root / "shared" / "deal_room"
    ora = compute_dealroom_oracle()
    ja = read_json_safe(dr / "qoe_diligence_pack.json")
    jb = read_json_safe(dr / "tax_nwc_closing_pack.json")
    book = evaluate_xlsx_isolated(dr / "SPA_Closing_Model.xlsx")
    odt_txt = read_odt_text(dr / "IC_Closing_Memo.odt")
    pdf_txt = extract_pdf_text(dr / "IC_Closing_Memo.pdf")

    def _ok(obj: dict[str, Any], k: str, tol: float = 0.015) -> bool:
        v = obj.get(k)
        return isinstance(v, (int, float)) and abs(float(v) - float(ora[k])) <= tol

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_vdr_code", str(ja.get("vdr_deal_code", "")).strip() == VDR_DEAL_CODE, 1.0, "vdr_deal_code missing/wrong"),
        ("a_unadj_ebitda", _ok(ja, "unadjusted_ebitda_musd", 0.02), 2.0, f"unadjusted_ebitda_musd mismatch (expected {ora['unadjusted_ebitda_musd']}, use VDR avg FX & exclude D&A)"),
        ("a_asc606_adj", _ok(ja, "asc606_deferred_rev_adj_musd", 0.015), 2.0, f"asc606_deferred_rev_adj_musd mismatch (expected {ora['asc606_deferred_rev_adj_musd']})"),
        ("a_asc350_adj", _ok(ja, "asc350_overcap_reversal_musd", 0.01), 1.8, f"asc350_overcap_reversal_musd mismatch (expected {ora['asc350_overcap_reversal_musd']})"),
        ("a_rent_addback", _ok(ja, "related_party_rent_addback_musd", 0.01), 1.5, f"related_party_rent_addback_musd mismatch (expected {ora['related_party_rent_addback_musd']})"),
        ("a_lit_cap", _ok(ja, "litigation_capped_addback_musd", 0.01), 1.5, "litigation_capped_addback_musd must respect $1.250M SPA cap"),
        ("a_adj_ebitda", _ok(ja, "adjusted_ebitda_musd", 0.025), 2.0, f"adjusted_ebitda_musd mismatch (expected {ora['adjusted_ebitda_musd']})"),
        ("a_ev_11_5x", _ok(ja, "enterprise_value_musd", 0.15), 2.0, f"enterprise_value_musd mismatch (expected {ora['enterprise_value_musd']})"),
        (
            "a_xlsx_qoe",
            (cell_float(book, "QoE_EBITDA", "B7") is not None)
            and abs(float(cell_float(book, "QoE_EBITDA", "B7") or 0.0) - ora["adjusted_ebitda_musd"]) <= 0.03,
            1.5,
            "SPA_Closing_Model.xlsx QoE_EBITDA!B7 Adjusted_EBITDA missing/wrong",
        ),
        (
            "a_xlsx_wire_ev",
            (cell_float(book, "Closing_Wire_Summary", "B2") is not None)
            and abs(float(cell_float(book, "Closing_Wire_Summary", "B2") or 0.0) - ora["enterprise_value_musd"]) <= 0.15,
            1.5,
            "Closing_Wire_Summary!B2 Enterprise_Value_MUSD missing/wrong",
        ),
        ("a_odt_qoe", "PENDING_QOE_BRIDGE" not in odt_txt and f"{ora['adjusted_ebitda_musd']:.2f}"[:4] in odt_txt, 1.2, "IC_Closing_Memo.odt missing QoE Adjusted EBITDA"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_vdr_code", str(jb.get("vdr_deal_code", "")).strip() == VDR_DEAL_CODE, 1.0, "vdr_deal_code missing/wrong"),
        ("b_nwc_peg", _ok(jb, "nwc_peg_musd", 0.02), 2.2, f"nwc_peg_musd mismatch (expected {ora['nwc_peg_musd']}; exclude cash/debt/DTA/IC-904 & 2025-08 anomaly)"),
        ("b_closing_nwc", _ok(jb, "closing_nwc_musd", 0.02), 1.8, f"closing_nwc_musd mismatch (expected {ora['closing_nwc_musd']})"),
        ("b_nwc_adj", _ok(jb, "nwc_closing_adjustment_musd", 0.025), 1.8, f"nwc_closing_adjustment_musd mismatch (expected {ora['nwc_closing_adjustment_musd']})"),
        ("b_sec382_cap", _ok(jb, "sec382_annual_cap_musd", 0.015), 1.6, f"sec382_annual_cap_musd mismatch (expected {ora['sec382_annual_cap_musd']})"),
        ("b_utp_holdback", _ok(jb, "utp_tax_holdback_musd", 0.015), 2.0, f"utp_tax_holdback_musd mismatch (expected {ora['utp_tax_holdback_musd']}, exclude closed 2021 audit)"),
        ("b_net_debt_fee", _ok(jb, "net_debt_musd", 0.01) and _ok(jb, "escrow_admin_fee_musd", 0.005), 1.2, "net_debt_musd or escrow_admin_fee_musd from VDR Folder B mismatch"),
        (
            "b_xlsx_nwc_tax",
            (cell_float(book, "NWC_Tax_Schedule", "B2") is not None)
            and abs(float(cell_float(book, "NWC_Tax_Schedule", "B2") or 0.0) - ora["nwc_peg_musd"]) <= 0.03
            and (cell_float(book, "NWC_Tax_Schedule", "B6") is not None)
            and abs(float(cell_float(book, "NWC_Tax_Schedule", "B6") or 0.0) - ora["utp_tax_holdback_musd"]) <= 0.03,
            1.5,
            "SPA_Closing_Model.xlsx NWC_Tax_Schedule B2/B6 missing/wrong",
        ),
        (
            "b_xlsx_wire_deductions",
            (cell_float(book, "Closing_Wire_Summary", "B3") is not None)
            and abs(float(cell_float(book, "Closing_Wire_Summary", "B3") or 0.0) - ora["net_debt_musd"]) <= 0.02
            and (cell_float(book, "Closing_Wire_Summary", "B5") is not None)
            and abs(float(cell_float(book, "Closing_Wire_Summary", "B5") or 0.0) - ora["utp_tax_holdback_musd"]) <= 0.02,
            1.5,
            "Closing_Wire_Summary B3..B6 deductions missing/wrong",
        ),
        ("b_odt_pdf_tax", "PENDING_TAX_NWC" not in odt_txt and len(pdf_txt.strip()) > 60 and VDR_DEAL_CODE in pdf_txt, 1.4, "IC_Closing_Memo.odt/.pdf missing Tax/NWC closing summary"),
    ]

    wire_b7 = cell_float(book, "Closing_Wire_Summary", "B7")
    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_reconciled_closing_wire_b7",
            (wire_b7 is not None) and abs(float(wire_b7) - ora["net_closing_wire_musd"]) <= 0.18,
            2.2,
            f"Closing_Wire_Summary!B7 Net_Closing_Wire_MUSD mismatch (expected {ora['net_closing_wire_musd']}, got {wire_b7})",
        ),
        (
            "j_both_memo_sections_preserved",
            "PENDING_QOE_BRIDGE" not in odt_txt
            and "PENDING_TAX_NWC" not in odt_txt
            and f"{ora['adjusted_ebitda_musd']:.2f}"[:4] in pdf_txt
            and f"{ora['utp_tax_holdback_musd']:.2f}"[:4] in pdf_txt,
            1.8,
            "Shared IC_Closing_Memo.odt/.pdf lost either Section 1 (QoE) or Section 2 (Tax/NWC) due to concurrent overwrite",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"qoe_ebitda_lead": TICKET_A, "tax_nwc_structuring_lead": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

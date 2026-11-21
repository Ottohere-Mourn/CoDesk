"""EC-01: Multi-Entity M&A Due-Diligence Data Room, Open LibreOffice Calc Split-Brain & Leverage Covenant.

Contention Archetypes:
  1. In-Memory GUI Dirty Buffer vs. Disk CLI Split-Brain (Merger_ProForma_2026.xlsx live in LibreOffice Calc with unsaved desk tag).
  3. Single-Instance LibreOffice soffice.bin / .~lock Profile Lock during PDF export.
  4. Shared Authenticated Browser Session (HttpOnly VDR cookie, FX Basis toggle, paginated 48-row ~/Downloads/vdr_schedule.csv).
  5. Bidirectional Coupled Financial Envelope (Net_Debt / Adjusted_EBITDA in [3.03, 3.09]).
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.exam_contention_v1.common import (
    advisory_lock,
    convert_doc_to_pdf_isolated,
    extract_pdf_text,
    find_unexpected_workspace_files,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    reload_open_libreoffice_window,
    render_scanned_document_png,
    set_x11_clipboard,
    verify_prompt_driver_and_ban_clean,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "EC-01"
PORTAL_PORT = 18801
DESK_TAG = "DESK-CFO-ATLAS-719"
QOE_VDR_SEAL = make_opaque_seal("ec01", "AVG_2026_PL:FX_AND_CASH")
TAX_VDR_SEAL = make_opaque_seal("ec01", "SPOT_CLOSE_BS:TAX_ROLLFORWARD")
ALLOWED_DEAL_FILES = {
    "Merger_ProForma_2026.xlsx",
    "QoE_Signoff_Pack.pdf",
    "Tax_Treasury_Pack.pdf",
    "SPA_Accounting_Policy.md",
    "target_erp_gl.db",
    "exhibits/qoe_credit_memos.png",
    "exhibits/qoe_exec_onetime.png",
    "exhibits/qoe_lease_reclass.png",
    "exhibits/tax_382_ruling.png",
    "exhibits/treasury_fx_confirm.png",
}

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Multi-Entity M&A Due-Diligence Data Room, Open LibreOffice Calc Split-Brain & Leverage Covenant",
    "domain": "Corporate M&A Financial Due Diligence & Treasury Structuring",
    "archetypes": (
        "gui_dirty_buffer_vs_disk_cli_split_brain",
        "x11_clipboard_vdr_attestation_seal_race",
        "libreoffice_single_instance_profile_lock",
        "shared_httponly_vdr_session_and_downloads",
        "bidirectional_debt_ebitda_covenant",
    ),
    "roles": ("qoe_ebitda_lead", "tax_treasury_lead"),
    "portal_port": PORTAL_PORT,
    "open_gui_doc": "/workspace/deal_model/Merger_ProForma_2026.xlsx",
    "open_gui_unsaved_tag": DESK_TAG,
    "conc_role_timeout_s": 1800,
    "seq_role_timeout_s": 1800,
}

FX_AVG_2026 = {"USD": 1.0000, "EUR": 1.0850, "GBP": 1.2700, "JPY": 0.0068}
FX_SPOT_CLOSE = {"USD": 1.0000, "EUR": 1.0520, "GBP": 1.2450, "JPY": 0.0065}

TRUE_ENTITY_EBITDA_USD_K = {
    "US_CORE": 17200.0,
    "DE_GMBH": 10850.0,
    "UK_LTD": 7620.0,
    "JP_KK": 4080.0,
}
TRUE_GL_CLEAN_EBITDA_USD_K = 39750.0
TRUE_SCAN_NET_QOE_ADJ_USD_K = -657.0
TRUE_ADJUSTED_EBITDA_USD_K = 39093.0

TRUE_MACRS_DTL_USD_K = 5120.0
TRUE_SEC382_NOL_OFFSET_USD_K = -1560.0
TRUE_ASC740_RESERVE_USD_K = 2190.0
TRUE_FX_BREAKAGE_USD_K = 1110.0
TRUE_NET_TAX_FX_LIAB_USD_K = 6860.0
TRUE_UNRESTRICTED_CASH_USD_K = 19200.0

SENIOR_TERM_LOAN_FIXED_USD_K = 60000.0
REVOLVER_RANGE_USD_K = (42000.0, 56000.0)
TAX_NOTE_RANGE_USD_K = (22000.0, 35500.0)
LEVERAGE_BAND = (3.03, 3.09)

VDR_QOE_AUDIT_ITEMS: list[tuple[str, str, float, str]] = [
    ("QOE-01", "USD", -180.00, "US_SLA_CREDIT_Q1"),
    ("QOE-02", "USD", -165.00, "US_SLA_CREDIT_Q2"),
    ("QOE-03", "USD", -145.00, "US_SLA_CREDIT_Q3"),
    ("QOE-04", "USD", -130.00, "US_SLA_CREDIT_Q4"),
    ("QOE-05", "EUR", -120.00, "DE_REBATE_BATCH_A"),
    ("QOE-06", "EUR", -105.00, "DE_REBATE_BATCH_B"),
    ("QOE-07", "EUR", -95.00, "DE_REBATE_BATCH_C"),
    ("QOE-08", "EUR", -80.00, "DE_REBATE_BATCH_D"),
    ("QOE-09", "JPY", -8000.00, "JP_PORT_DUTY_OCT"),
    ("QOE-10", "JPY", -6500.00, "JP_PORT_DUTY_NOV"),
    ("QOE-11", "JPY", -5500.00, "JP_PORT_DUTY_DEC1"),
    ("QOE-12", "JPY", -5000.00, "JP_PORT_DUTY_DEC2"),
]


def _build_vdr_schedules() -> tuple[list[tuple[str, str, str, float, str]], list[tuple[str, str, float, str]]]:
    bank_rows: list[tuple[str, str, str, float, str]] = [
        ("BNK-01", "US_CORE", "USD", 2450.00, "OPERATING_SWEEP"),
        ("BNK-02", "US_CORE", "USD", 1820.00, "OPERATING_SWEEP"),
        ("BNK-03", "DE_GMBH", "EUR", 1450.00, "OPERATING_SWEEP"),
        ("BNK-04", "UK_LTD", "GBP", 980.00, "OPERATING_SWEEP"),
        ("BNK-05", "JP_KK", "JPY", 110000.00, "OPERATING_SWEEP"),
        ("BNK-06", "US_CORE", "USD", 1400.00, "RESTRICTED_ESCROW"),
        ("BNK-07", "US_CORE", "USD", 1640.00, "OPERATING_SWEEP"),
        ("BNK-08", "US_CORE", "USD", 1310.00, "OPERATING_SWEEP"),
        ("BNK-09", "US_CORE", "USD", 1190.00, "OPERATING_SWEEP"),
        ("BNK-10", "US_CORE", "USD", 980.00, "OPERATING_SWEEP"),
        ("BNK-11", "US_CORE", "USD", 915.00, "OPERATING_SWEEP"),
        ("BNK-12", "US_CORE", "USD", 828.00, "OPERATING_SWEEP"),
        ("BNK-13", "DE_GMBH", "EUR", 1120.00, "OPERATING_SWEEP"),
        ("BNK-14", "DE_GMBH", "EUR", 980.00, "OPERATING_SWEEP"),
        ("BNK-15", "DE_GMBH", "EUR", 890.00, "OPERATING_SWEEP"),
        ("BNK-16", "DE_GMBH", "EUR", 810.00, "OPERATING_SWEEP"),
        ("BNK-17", "DE_GMBH", "EUR", 750.00, "OPERATING_SWEEP"),
        ("BNK-18", "DE_GMBH", "EUR", 950.00, "RESTRICTED_ESCROW"),
        ("BNK-19", "UK_LTD", "GBP", 760.00, "OPERATING_SWEEP"),
        ("BNK-20", "UK_LTD", "GBP", 640.00, "OPERATING_SWEEP"),
        ("BNK-21", "UK_LTD", "GBP", 520.00, "OPERATING_SWEEP"),
        ("BNK-22", "UK_LTD", "GBP", 480.00, "OPERATING_SWEEP"),
        ("BNK-23", "UK_LTD", "GBP", 420.00, "OPERATING_SWEEP"),
        ("BNK-24", "UK_LTD", "GBP", 600.00, "RESTRICTED_ESCROW"),
        ("BNK-25", "JP_KK", "JPY", 96000.00, "OPERATING_SWEEP"),
        ("BNK-26", "JP_KK", "JPY", 84000.00, "OPERATING_SWEEP"),
        ("BNK-27", "JP_KK", "JPY", 78000.00, "OPERATING_SWEEP"),
        ("BNK-28", "JP_KK", "JPY", 68000.00, "OPERATING_SWEEP"),
        ("BNK-29", "JP_KK", "JPY", 60000.00, "OPERATING_SWEEP"),
        ("BNK-30", "JP_KK", "JPY", 85000.00, "RESTRICTED_ESCROW"),
        ("BNK-31", "US_CORE", "USD", 750.00, "RESTRICTED_ESCROW"),
        ("BNK-32", "DE_GMBH", "EUR", 500.00, "RESTRICTED_ESCROW"),
    ]
    tax_rows: list[tuple[str, str, float, str]] = [
        ("DTL-01", "USD", 680.00, "US_MACRS_PP&E"),
        ("DTL-02", "USD", 540.00, "US_INTANGIBLE_AMORT"),
        ("DTL-03", "EUR", 480.00, "DE_SPECIAL_DEPR"),
        ("DTL-04", "GBP", 350.00, "UK_CAPITAL_ALLOWANCE"),
        ("DTL-05", "JPY", 24000.00, "JP_EQUIPMENT_RESERVE"),
        ("DTL-06", "USD", 495.00, "US_CAPITALIZED_SW"),
        ("DTL-07", "USD", 384.00, "US_PREPAID_COMMISSIONS"),
        ("DTL-08", "USD", 320.00, "US_LEASE_ROU_ASSET"),
        ("DTL-09", "EUR", 420.00, "DE_ROU_BASIS_DIFF"),
        ("DTL-10", "EUR", 350.00, "DE_INVENTORY_VALUATION"),
        ("DTL-11", "GBP", 450.00, "UK_PATENT_BOX_TIMING"),
        ("DTL-12", "JPY", 36000.00, "JP_ACCELERATED_TOOLING"),
    ]
    return bank_rows, tax_rows


VDR_BANK_ACCOUNTS, VDR_TAX_ITEMS = _build_vdr_schedules()


def _populate_gl_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    rng = random.Random(20261120)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE gl_entries (
            entry_id TEXT PRIMARY KEY,
            entity TEXT NOT NULL,
            currency TEXT NOT NULL,
            acct_type TEXT NOT NULL,
            acct_subtype TEXT NOT NULL,
            posting_date TEXT NOT NULL,
            ship_date TEXT NOT NULL,
            counterparty_type TEXT NOT NULL,
            status TEXT NOT NULL,
            local_amount_k REAL NOT NULL,
            memo TEXT NOT NULL
        )
        """
    )
    rows: list[tuple] = []
    idx = 1
    clean_specs = [
        ("US_CORE", "USD", "REVENUE", "PROD_SALES", 26400.0, 360),
        ("US_CORE", "USD", "OPEX", "SG&A_OPS", -9200.0, 260),
        ("DE_GMBH", "EUR", "REVENUE", "PROD_SALES", 14000.0, 280),
        ("DE_GMBH", "EUR", "OPEX", "SG&A_OPS", -4000.0, 200),
        ("UK_LTD", "GBP", "REVENUE", "PROD_SALES", 9000.0, 240),
        ("UK_LTD", "GBP", "OPEX", "SG&A_OPS", -3000.0, 180),
        ("JP_KK", "JPY", "REVENUE", "PROD_SALES", 950000.0, 240),
        ("JP_KK", "JPY", "OPEX", "SG&A_OPS", -350000.0, 180),
    ]
    for ent, ccy, atype, sub, total_local, n_rows in clean_specs:
        weights = [rng.uniform(0.5, 1.8) for _ in range(n_rows)]
        w_sum = sum(weights)
        vals = [round(total_local * (w / w_sum), 4) for w in weights[:-1]]
        vals.append(round(total_local - sum(vals), 4))
        for v in vals:
            m = rng.randint(1, 12)
            d = rng.randint(1, 24)
            p_dt = f"2026-{m:02d}-{d:02d}"
            s_dt = f"2026-{m:02d}-{min(28, d + 2):02d}"
            rows.append((f"GL-{idx:05d}", ent, ccy, atype, sub, p_dt, s_dt, "THIRD_PARTY", "POSTED", v, "Operating journal batch"))
            idx += 1

    for _ in range(180):
        m = rng.randint(1, 12)
        rows.append((f"GL-{idx:05d}", "US_CORE", "USD", "REVENUE", "PROD_SALES", f"2026-{m:02d}-15", f"2026-{m:02d}-16", "THIRD_PARTY", "VOID_REVERSED", round(rng.uniform(12.0, 38.0), 2), "Reversed duplicate upload"))
        idx += 1

    for _ in range(160):
        m = rng.randint(1, 12)
        rows.append((f"GL-{idx:05d}", "DE_GMBH", "EUR", "REVENUE", "MGMT_FEE", f"2026-{m:02d}-28", f"2026-{m:02d}-28", "INTERCO", "POSTED", round(rng.uniform(8.0, 25.0), 2), "Intercompany management fee"))
        idx += 1

    for _ in range(160):
        d = rng.randint(20, 31)
        s_d = rng.randint(3, 19)
        rows.append((f"GL-{idx:05d}", "UK_LTD", "GBP", "REVENUE", "PROD_SALES", f"2026-12-{d:02d}", f"2027-01-{s_d:02d}", "THIRD_PARTY", "POSTED", round(rng.uniform(9.0, 29.0), 2), "Q4 bill-and-hold staging"))
        idx += 1

    for _ in range(120):
        m = rng.randint(1, 12)
        rows.append((f"GL-{idx:05d}", "US_CORE", "USD", "OPEX", "CAPEX_EQUIP", f"2026-{m:02d}-19", f"2026-{m:02d}-19", "THIRD_PARTY", "POSTED", -round(rng.uniform(11.0, 28.0), 2), "CNC capital tooling miscoded to OPEX"))
        idx += 1

    for _ in range(90):
        m = rng.randint(1, 12)
        rows.append((f"GL-{idx:05d}", "DE_GMBH", "EUR", "REVENUE", "UNREALIZED_FX_REVAL", f"2026-{m:02d}-27", f"2026-{m:02d}-27", "THIRD_PARTY", "POSTED", round(rng.uniform(7.0, 22.0), 2), "Non-operating unrealized FX mark-to-market"))
        idx += 1

    rng.shuffle(rows)
    conn.executemany("INSERT INTO gl_entries VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def _make_qoe_rows(
    us_k: float,
    de_k: float,
    uk_k: float,
    jp_k: float,
    scan_adj: float,
    desk_tag: str = "",
    vdr_seal: str = "PENDING_QOE_VDR_SEAL",
) -> list[list]:
    adj_ebitda = round(us_k + de_k + uk_k + jp_k + scan_adj, 2)
    return [
        ["Line_Item", "Amount_USD_K", desk_tag],
        ["US_CORE_Clean_EBITDA_USD_K", round(us_k, 2), "POSTED_3P_EX_CAPEX"],
        ["DE_GMBH_Clean_EBITDA_USD_K", round(de_k, 2), "AVG_FX_EX_INTERCO"],
        ["UK_LTD_Clean_EBITDA_USD_K", round(uk_k, 2), "AVG_FX_ASC606_SHIP"],
        ["JP_KK_Clean_EBITDA_USD_K", round(jp_k, 2), "AVG_FX_OPERATING"],
        ["Net_Scanned_QoE_Adjustments_USD_K", round(scan_adj, 2), "EXHIBITS_A1_TO_A3"],
        ["Adjusted_EBITDA_USD_K", ("=SUM(B2:B6)", adj_ebitda), "CONSOLIDATED_QOE"],
        ["VDR_QoE_Attestation_Seal", vdr_seal, "CLIPBOARD_AVG_FX_CASH"],
    ]


def _make_tax_rows(
    dtl_k: float,
    nol_offset_k: float,
    utp_k: float,
    fx_break_k: float,
    cash_unrest_k: float,
    vdr_seal: str = "PENDING_TAX_VDR_SEAL",
) -> list[list]:
    net_liab = round(dtl_k + nol_offset_k + utp_k + fx_break_k, 2)
    return [
        ["Schedule_Item", "Amount_USD_K", "Authority_Ref"],
        ["Deferred_Tax_Liability_Timing_USD_K", round(dtl_k, 2), "VDR_12_ITEM_SPOT_SUM"],
        ["Sec382_Allowed_NOL_Tax_Offset_USD_K", round(nol_offset_k, 2), "EXHIBIT_B1_SEC382"],
        ["ASC740_Uncertain_Tax_Reserve_USD_K", round(utp_k, 2), "EXHIBIT_B1_ASC740_P2"],
        ["FX_Forward_Breakage_Reserve_USD_K", round(fx_break_k, 2), "EXHIBIT_B2_SPOT"],
        ["Net_Tax_FX_Liability_USD_K", ("=SUM(B2:B5)", net_liab), "TOTAL_TAX_TREASURY"],
        ["Unrestricted_Closing_Cash_USD_K", round(cash_unrest_k, 2), "SWEEP_EX_ESCROW_EX_LC"],
        ["VDR_Tax_Attestation_Seal", vdr_seal, "CLIPBOARD_SPOT_TAX_TAB"],
    ]


def _make_debt_rows(revolver_k: float, tax_note_k: float, ebitda_k: float, cash_k: float) -> list[list]:
    tot_debt = round(SENIOR_TERM_LOAN_FIXED_USD_K + revolver_k + tax_note_k, 2)
    net_debt = round(tot_debt - cash_k, 2)
    lev = round(net_debt / max(1.0, ebitda_k), 4)
    return [
        ["Tranche_Or_Metric", "Value", "Facility_Term"],
        ["Senior_Term_Loan_Fixed_USD_K", SENIOR_TERM_LOAN_FIXED_USD_K, "FIXED_TRANCHE_A"],
        ["Senior_Revolver_Draw_USD_K", round(revolver_k, 2), "QOE_LEAD_SIZED"],
        ["Tax_Indemnity_Note_USD_K", round(tax_note_k, 2), "TAX_LEAD_SIZED"],
        ["Total_Closing_Debt_USD_K", ("=SUM(B2:B4)", tot_debt), "GROSS_DEBT"],
        ["Net_Debt_USD_K", ("=B5-Tax_Deferred_Schedule!B7", net_debt), "GROSS_MINUS_UNREST_CASH"],
        ["Net_Leverage_Ratio", ("=B6/QoE_Bridge!B7", lev), "SPA_COVENANT_RATIO"],
    ]


def _make_exec_rows(ebitda_k: float, net_liab_k: float, lev: float) -> list[list]:
    return [
        ["Summary_KPI", "Evaluated_Value"],
        ["Consolidated_Adjusted_EBITDA_USD_K", ("=QoE_Bridge!B7", round(ebitda_k, 2))],
        ["Net_Tax_And_FX_Liability_USD_K", ("=Tax_Deferred_Schedule!B6", round(net_liab_k, 2))],
        ["Closing_Net_Leverage_Multiple", ("=Debt_Covenant_Model!B7", round(lev, 4))],
    ]


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    qoe_md = "\n".join([
        f"# M&A Financial Due-Diligence Work Order — {b}qoe_ebitda_lead{b}",
        "",
        "## Engagement Scope & Deliverables",
        f"Complete the Quality-of-Earnings (QoE) consolidation and revolver sizing for the Project Atlas acquisition in {b}/workspace/deal_model{b}.",
        f"The deal model {b}/workspace/deal_model/Merger_ProForma_2026.xlsx{b} is currently open in LibreOffice Calc on the workstation (with an active desk control tag in {b}QoE_Bridge!C1{b}) alongside the Virtual Data Room (VDR) session at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Audit 2026 entity-level clean EBITDA ({b}USD_K{b}) across {b}US_CORE{b}, {b}DE_GMBH{b}, {b}UK_LTD{b}, and {b}JP_KK{b} from {b}/workspace/deal_model/target_erp_gl.db{b} and reconcile all post-close QoE adjustments from {b}/workspace/deal_model/exhibits/{b} and the VDR FX schedule in strict accordance with {b}/workspace/deal_model/SPA_Accounting_Policy.md{b}.",
        f"2. In the VDR ({b}FX_BASIS = AVG_2026_PL{b}, {b}TAB = FX_AND_CASH{b}), copy the VDR QoE Attestation Seal to the system clipboard and record it in {b}QoE_Bridge!B8{b}; populate {b}QoE_Bridge{b} ({b}B2:B5{b} entity clean EBITDA, {b}B6{b} net scanned QoE adjustments, and live formula {b}=SUM(B2:B6){b} in {b}B7{b}) in {b}Merger_ProForma_2026.xlsx{b}, preserving all existing sheets, cross-sheet formulas, and {b}QoE_Bridge!C1{b}.",
        f"3. Size only your tranche {b}Debt_Covenant_Model!B3{b} ({b}Senior_Revolver_Draw_USD_K{b}) within its facility bounds in {b}SPA_Accounting_Policy.md{b} so {b}Debt_Covenant_Model!B7{b} satisfies the closing Net Leverage covenant.",
        f"4. Save the completed workbook cleanly and export {b}/workspace/deal_model/QoE_Signoff_Pack.pdf{b} matching your finalized {b}QoE_Bridge{b} and {b}Senior_Revolver_Draw_USD_K{b}. Keep {b}/workspace/deal_model{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])

    tax_md = "\n".join([
        f"# M&A Tax & Treasury Work Order — {b}tax_treasury_lead{b}",
        "",
        "## Engagement Scope & Deliverables",
        f"Complete the closing Tax, FX breakage, unrestricted cash, and tax indemnity note schedule for Project Atlas in {b}/workspace/deal_model{b}.",
        f"The deal model {b}/workspace/deal_model/Merger_ProForma_2026.xlsx{b} is currently open in LibreOffice Calc on the workstation (with an active desk control tag in {b}QoE_Bridge!C1{b}) alongside the Virtual Data Room (VDR) session at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Reconcile closing Deferred Tax timing liabilities, IRC Section 382 NOL tax-asset offset, uncertain tax & Pillar-Two reserves, FX forward breakage, and Unrestricted Closing Cash ({b}USD_K{b}) from the full VDR CSV schedules ({b}http://127.0.0.1:{PORTAL_PORT}{b}), scanned exhibits in {b}/workspace/deal_model/exhibits/{b}, and {b}/workspace/deal_model/SPA_Accounting_Policy.md{b}.",
        f"2. In the VDR ({b}FX_BASIS = SPOT_CLOSE_BS{b}, {b}TAB = TAX_ROLLFORWARD{b}), copy the VDR Tax Attestation Seal to the system clipboard and record it in {b}Tax_Deferred_Schedule!B8{b}; populate {b}Tax_Deferred_Schedule{b} ({b}B2:B5{b}, formula {b}=SUM(B2:B5){b} in {b}B6{b}, and {b}Unrestricted_Closing_Cash_USD_K{b} in {b}B7{b}) in {b}Merger_ProForma_2026.xlsx{b}, preserving all existing sheets, cross-sheet formulas, and {b}QoE_Bridge!C1{b}.",
        f"3. Size only your tranche {b}Debt_Covenant_Model!B4{b} ({b}Tax_Indemnity_Note_USD_K{b}) within its facility bounds in {b}SPA_Accounting_Policy.md{b} so {b}Debt_Covenant_Model!B7{b} satisfies the closing Net Leverage covenant.",
        f"4. Save the completed workbook cleanly and export {b}/workspace/deal_model/Tax_Treasury_Pack.pdf{b} matching your finalized {b}Tax_Deferred_Schedule{b} and {b}Tax_Indemnity_Note_USD_K{b}. Keep {b}/workspace/deal_model{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])
    return {"qoe_ebitda_lead": qoe_md, "tax_treasury_lead": tax_md}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    b = chr(96)
    dm = workspace / "deal_model"
    ex = dm / "exhibits"
    ex.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    _populate_gl_db(dm / "target_erp_gl.db")

    (dm / "SPA_Accounting_Policy.md").write_text(
        "\n".join([
            "# Share Purchase Agreement (SPA) — Exhibit D: Accounting & Covenant Definitions",
            "",
            f"1. **General Ledger Consolidation ({b}target_erp_gl.db{b}, {b}QoE_Bridge!B2:B5{b})**:",
            "   - Entity Clean Operating EBITDA includes only posted third-party recurring product sales and SG&A operating expenses recognized on goods physically shipped within calendar year 2026.",
            "   - Exclude reversed/voided journal uploads, intercompany management charges, bill-and-hold revenue shipped after 2026-12-31, capital equipment/tooling purchases misposted into OPEX, and non-operating unrealized FX revaluation gains.",
            f"   - **FX Convention**: All income-statement items ({b}REVENUE{b}, {b}OPEX{b}, and QoE P&L exhibits) MUST be translated into {b}USD_K{b} at **2026 Average FX Rates ({b}AVG_2026_PL{b})**. All closing balance-sheet cash, tax timing DTLs, and FX breakage items MUST use **2026-12-31 Spot FX Rates ({b}SPOT_CLOSE_BS{b})**.",
            "",
            f"2. **QoE Exhibits ({b}QoE_Bridge!B6{b})**:",
            f"   - Deduct all 12 unrecorded customer SLA credit/rebate/customs items ({b}QOE_AUDIT_ITEM{b} rows in {b}/home/gui/Downloads/vdr_schedule.csv{b} per {b}qoe_credit_memos.png{b}, translated at {b}AVG_2026_PL{b}).",
            f"   - One-time facility closure severance in {b}qoe_exec_onetime.png{b} is allowable as a positive EBITDA add-back ONLY up to the **SPA Cap of {b}350.0 USD_K{b}**; annual executive retention bonuses are **0% allowable**.",
            f"   - Under {b}qoe_lease_reclass.png{b} (ASC 842), finance-lease rent expense reclassified out of {b}OPEX{b} to interest/amortization is added back to EBITDA (translated at {b}AVG_2026_PL{b}).",
            f"   - Copy the VDR QoE Attestation Seal under {b}FX_BASIS = AVG_2026_PL{b} and {b}TAB = FX_AND_CASH{b} to {b}QoE_Bridge!B8{b}.",
            "",
            f"3. **Closing Tax, FX Breakage & Unrestricted Cash ({b}Tax_Deferred_Schedule!B2:B7{b})**:",
            f"   - Note: The VDR web viewport previews only the top rows; export {b}/home/gui/Downloads/vdr_schedule.csv{b} under {b}SPOT_CLOSE_BS{b} to obtain all 32 subsidiary bank accounts and all 12 DTL rollforward items.",
            f"   - {b}B2{b} ({b}Deferred_Tax_Liability_Timing_USD_K{b}): sum of all 12 {b}TAX_DTL_ITEM{b} rows translated at {b}SPOT_CLOSE_BS{b}.",
            f"   - {b}B3{b} ({b}Sec382_Allowed_NOL_Tax_Offset_USD_K{b}): enter as a **negative** liability offset equal to {b}-Realizable_Sec382_NOL_USD_K * Blended_Statutory_Tax_Rate{b} per {b}tax_382_ruling.png{b}.",
            f"   - {b}B4{b} ({b}ASC740_Uncertain_Tax_Reserve_USD_K{b}): sum of FIN 48 uncertain R&D reserve plus Pillar-Two top-up assessment in {b}tax_382_ruling.png{b}.",
            f"   - {b}B5{b} ({b}FX_Forward_Breakage_Reserve_USD_K{b}): sum of closing forward breakage settlements in {b}treasury_fx_confirm.png{b} translated at {b}SPOT_CLOSE_BS{b}.",
            f"   - {b}B7{b} ({b}Unrestricted_Closing_Cash_USD_K{b}): sum of VDR bank accounts classified as {b}OPERATING_SWEEP{b} (exclude {b}RESTRICTED_ESCROW{b}) translated at {b}SPOT_CLOSE_BS{b}, **minus** any pledged Standby Letter of Credit deposit identified in {b}treasury_fx_confirm.png{b}.",
            f"   - Copy the VDR Tax Attestation Seal under {b}FX_BASIS = SPOT_CLOSE_BS{b} and {b}TAB = TAX_ROLLFORWARD{b} to {b}Tax_Deferred_Schedule!B8{b}.",
            "",
            f"4. **Closing Debt Tranches & Net Leverage Covenant ({b}Debt_Covenant_Model{b})**:",
            f"   - Fixed Senior Term Loan ({b}B2{b}) = {b}60000.0 USD_K{b}.",
            f"   - Permitted {b}Senior_Revolver_Draw_USD_K{b} ({b}B3{b}) range: **{b}[42000.0, 56000.0] USD_K{b}**.",
            f"   - Permitted {b}Tax_Indemnity_Note_USD_K{b} ({b}B4{b}) range: **{b}[22000.0, 35500.0] USD_K{b}**.",
            f"   - Closing {b}Net_Leverage_Ratio{b} ({b}B7 = B6 / QoE_Bridge!B7{b}) MUST lie within **{b}[3.03, 3.09]{b}**.",
            "",
        ]),
        encoding="utf-8",
    )

    render_scanned_document_png(
        ex / "qoe_credit_memos.png",
        "EXHIBIT A-1: POST-CLOSE UNRECORDED CREDIT MEMOS & DUTIES",
        [
            "Audit Scope: 12 Post-Close SLA Credit, Rebate & Customs Items",
            "  Itemized in VDR Schedule CSV under section = QOE_AUDIT_ITEM",
            "  (IDs QOE-01 through QOE-12 across USD, EUR, and JPY).",
            "Accounting Rule: Export VDR Schedule CSV under AVG_2026_PL and",
            "  include the signed USD_K sum of all 12 QOE_AUDIT_ITEM rows in B6.",
        ],
        stamp_text="QOE AUDIT LOG",
        tilt_deg=-1.9,
    )
    render_scanned_document_png(
        ex / "qoe_exec_onetime.png",
        "EXHIBIT A-2: MANAGEMENT PROPOSED OPERATING EXPENSE ADD-BACKS",
        [
            "1. Ohio Assembly Closure & Non-Recurring Severance (Oct 2026):",
            "   Booked in US_CORE OPEX (SG&A_OPS): 480.0 USD_K",
            "2. Executive Key-Employee Annual Retention Bonus Plan (FY2026):",
            "   Booked in US_CORE OPEX (SG&A_OPS): 290.0 USD_K",
            "Apply SPA Exhibit D Section 2 caps and eligibility rules.",
        ],
        stamp_text="MANAGEMENT SCHEDULE",
        tilt_deg=1.6,
    )
    render_scanned_document_png(
        ex / "qoe_lease_reclass.png",
        "EXHIBIT A-3: ASC 842 FINANCE LEASE RECLASSIFICATION",
        [
            "Entity: DE_GMBH (Frankfurt Automated Logistics Hub)",
            "2026 Lease Payments Booked Inside Clean SG&A_OPS OPEX: 200.0 EUR_K",
            "Audit Finding: Contract qualifies as Finance Lease under ASC 842;",
            "reclassify 200.0 EUR_K out of OPEX into Depreciation & Interest.",
        ],
        stamp_text="ASC 842 RECLASS",
        tilt_deg=-1.3,
    )
    render_scanned_document_png(
        ex / "tax_382_ruling.png",
        "EXHIBIT B-1: TAX DUE DILIGENCE — SEC. 382, ASC 740 & PILLAR TWO",
        [
            "Gross Pre-Closing Federal/State NOL Carryforward: 12,000.0 USD_K",
            "IRC Section 382 Post-Change Realizable NOL Principal: 6,500.0 USD_K",
            "Enacted Blended Corporate Statutory Tax Rate: 24.0%",
            "ASC 740-10 Uncertain R&D Credit Liability: 1,840.0 USD_K",
            "OECD Pillar-Two Qualified Domestic Top-Up Tax Payable: 350.0 USD_K",
        ],
        stamp_text="TAX OPINION FINAL",
        tilt_deg=-1.5,
    )
    render_scanned_document_png(
        ex / "treasury_fx_confirm.png",
        "EXHIBIT B-2: BANK COLLATERAL & DEAL FX BREAKAGE CONFIRMATIONS",
        [
            "1. Standby Letter of Credit #LC-4409 (Citibank NY):",
            "   6,200.0 USD_K cash collateral sits inside US_CORE OPERATING_SWEEP",
            "   accounts (BNK-01/BNK-02) and is legally restricted at closing.",
            "2. Deal-Contingent FX Forward Breakage Payables at Closing:",
            "   - London USD/EUR Hedge Desk Breakage: 850.0 USD_K",
            "   - Tokyo JPY Collar Breakage Payable: 40,000.0 JPY_K",
        ],
        stamp_text="TREASURY CONFIRMED",
        tilt_deg=1.8,
    )

    v0_ebitda = 39400.0
    v0_cash = 19100.0
    v0_rev = 54500.0
    v0_note = 34200.0
    v0_lev = round((SENIOR_TERM_LOAN_FIXED_USD_K + v0_rev + v0_note - v0_cash) / v0_ebitda, 4)
    write_multisheet_xlsx(
        dm / "Merger_ProForma_2026.xlsx",
        [
            ("QoE_Bridge", _make_qoe_rows(18000.0, 11000.0, 7000.0, 3400.0, 0.0, desk_tag="")),
            ("Tax_Deferred_Schedule", _make_tax_rows(5120.0, 0.0, 0.0, 0.0, v0_cash)),
            ("Debt_Covenant_Model", _make_debt_rows(v0_rev, v0_note, v0_ebitda, v0_cash)),
            ("Executive_Summary", _make_exec_rows(v0_ebitda, 5120.0, v0_lev)),
        ],
    )

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_vdr_html(fx_mode: str, active_tab: str) -> str:
    rates = FX_AVG_2026 if fx_mode == "AVG_2026_PL" else FX_SPOT_CLOSE
    fx_rows = "".join(
        f"<tr><td>{ccy}</td><td>{rate:.4f}</td><td>{'2026 P&L Average' if fx_mode == 'AVG_2026_PL' else '2026-12-31 Closing Spot'}</td></tr>"
        for ccy, rate in rates.items()
    )
    if active_tab == "FX_AND_CASH":
        sub_hdr = f"2. Subsidiary Bank Accounts (Previewing 6 of {len(VDR_BANK_ACCOUNTS)} — Export CSV for all {len(VDR_BANK_ACCOUNTS)} accounts)"
        tbl_hdr = f"<tr><th>Account ID</th><th>Entity</th><th>CCY</th><th>Balance (Local K)</th><th>USD_K (@ {fx_mode})</th><th>Account Class</th></tr>"
        tbl_rows = "".join(
            f"<tr><td>{aid}</td><td>{ent}</td><td>{ccy}</td><td>{amt:,.2f}</td><td>{amt * rates[ccy]:,.2f}</td><td>{cls}</td></tr>"
            for aid, ent, ccy, amt, cls in VDR_BANK_ACCOUNTS[:6]
        )
    elif active_tab == "SCANNED_EXHIBITS":
        sub_hdr = "2. Authenticated VDR Scanned Audit Exhibits (Exhibits A-1..A-3 & B-1..B-2)"
        tbl_hdr = "<tr><th>Exhibit</th><th>Scan Preview</th></tr>"
        ex_files = [
            ("A-1", "qoe_credit_memos.png"),
            ("A-2", "qoe_exec_onetime.png"),
            ("A-3", "qoe_lease_reclass.png"),
            ("B-1", "tax_382_ruling.png"),
            ("B-2", "treasury_fx_confirm.png"),
        ]
        tbl_rows = "".join(
            f"<tr><td><strong>Exhibit {lbl}</strong><br/><code>{fn}</code></td>"
            f"<td><img src='/exhibits/{fn}' style='max-width:760px;border:1px solid #94a3b8;' /></td></tr>"
            for lbl, fn in ex_files
        )
    else:
        sub_hdr = f"2. Deferred Tax Timing Rollforward (Previewing 5 of {len(VDR_TAX_ITEMS)} — Export CSV for all {len(VDR_TAX_ITEMS)} items)"
        tbl_hdr = f"<tr><th>Item ID</th><th>CCY</th><th>Timing Diff DTL (Local K)</th><th>USD_K (@ {fx_mode})</th><th>Category</th></tr>"
        tbl_rows = "".join(
            f"<tr><td>{tid}</td><td>{ccy}</td><td>{amt:,.2f}</td><td>{amt * rates[ccy]:,.2f}</td><td>{cat}</td></tr>"
            for tid, ccy, amt, cat in VDR_TAX_ITEMS[:5]
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Project Atlas — M&A Virtual Data Room</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    header {{ background: #0f172a; color: #f8fafc; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }}
    .badge {{ background: #1d4ed8; padding: 4px 10px; border-radius: 4px; font-family: monospace; font-size: 13px; }}
    .toolbar {{ background: #e2e8f0; padding: 10px 20px; display: flex; gap: 10px; align-items: center; border-bottom: 1px solid #cbd5e1; flex-wrap: wrap; }}
    button {{ background: #ffffff; border: 1px solid #64748b; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-weight: 600; }}
    button.active {{ background: #0f172a; color: #ffffff; }}
    main {{ padding: 18px 20px; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; margin-top: 10px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px 10px; text-align: left; font-size: 13px; }}
    th {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <header>
    <div><strong>Project Atlas — M&A Virtual Data Room (Authenticated SSO)</strong></div>
    <div class="badge" id="session-banner">FX_BASIS={fx_mode} | TAB={active_tab}</div>
  </header>
  <div class="toolbar">
    <span><strong>FX Basis:</strong></span>
    <button class="{'active' if fx_mode == 'AVG_2026_PL' else ''}" onclick="setState({{fx_mode:'AVG_2026_PL'}})">AVG_2026_PL</button>
    <button class="{'active' if fx_mode == 'SPOT_CLOSE_BS' else ''}" onclick="setState({{fx_mode:'SPOT_CLOSE_BS'}})">SPOT_CLOSE_BS</button>
    <span><strong>View:</strong></span>
    <button class="{'active' if active_tab == 'FX_AND_CASH' else ''}" onclick="setState({{tab:'FX_AND_CASH'}})">FX & Cash (32)</button>
    <button class="{'active' if active_tab == 'TAX_ROLLFORWARD' else ''}" onclick="setState({{tab:'TAX_ROLLFORWARD'}})">Tax DTL (12)</button>
    <button class="{'active' if active_tab == 'SCANNED_EXHIBITS' else ''}" onclick="setState({{tab:'SCANNED_EXHIBITS'}})">Exhibits (5 Scans)</button>
    <button onclick="exportCsv()">Export Full VDR Schedule CSV (/home/gui/Downloads/vdr_schedule.csv)</button>
    <button onclick="copyVdrSeal()">Copy VDR Attestation Seal to Clipboard</button>
    <span id="status-msg" style="font-family:monospace;font-size:12px;color:#0369a1;">Ready</span>
  </div>
  <main>
    <h3>1. Official FX Translation Table ({fx_mode})</h3>
    <table>
      <thead><tr><th>Currency</th><th>USD per 1 Local Unit</th><th>Basis</th></tr></thead>
      <tbody>{fx_rows}</tbody>
    </table>
    <h3>{sub_hdr}</h3>
    <table>
      <thead>{tbl_hdr}</thead>
      <tbody>{tbl_rows}</tbody>
    </table>
  </main>
  <script>
    async function setState(patch) {{
      const r = await fetch('/api/vdr/state', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(patch)}});
      if (r.ok) window.location.reload();
    }}
    async function exportCsv() {{
      document.getElementById('status-msg').textContent = 'Running VDR batch extract...';
      const r = await fetch('/api/vdr/export_csv', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('status-msg').textContent = d.ok ? ('Saved ' + d.rows + ' rows [' + d.fx_mode + ']') : 'Export error';
    }}
    async function copyVdrSeal() {{
      const r = await fetch('/api/vdr/copy_seal', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('status-msg').textContent = d.ok ? ('Copied seal [' + d.fx_mode + '/' + d.tab + ']') : 'Seal error';
    }}
  </script>
</body>
</html>
"""


def run_portal_service(port: int, workspace: Path, state_dir: Path, boot_file: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "fx_mode": "SPOT_CLOSE_BS",
        "tab": "FX_AND_CASH",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
    }

    def persist() -> None:
        write_json(state_p, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a: Any) -> None:
            return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec01_vdr_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True, "task_id": TASK_ID})
                return
            if parsed.path == "/":
                qs = parse_qs(parsed.query)
                if (qs.get("sso_boot") or [""])[0] == boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"ec01_vdr_sso={sso_cookie}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated VDR browser session required"})
                    return
                with lock:
                    html = _render_vdr_html(pstate["fx_mode"], pstate["tab"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path.startswith("/exhibits/"):
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated VDR browser session required"})
                    return
                fn = Path(parsed.path).name
                fp = workspace / "deal_model" / "exhibits" / fn
                if fp.is_file() and fp.suffix == ".png":
                    raw_png = fp.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(raw_png)))
                    self.end_headers()
                    self.wfile.write(raw_png)
                    return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self._authed():
                self._send_json(401, {"error": "Authenticated VDR browser session required"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            except Exception:
                body = {}

            if parsed.path == "/api/vdr/state":
                with lock:
                    changed = False
                    if body.get("fx_mode") in ("AVG_2026_PL", "SPOT_CLOSE_BS"):
                        if pstate["fx_mode"] != body["fx_mode"]:
                            changed = True
                        pstate["fx_mode"] = body["fx_mode"]
                    if body.get("tab") in ("FX_AND_CASH", "TAX_ROLLFORWARD", "SCANNED_EXHIBITS"):
                        if pstate["tab"] != body["tab"]:
                            changed = True
                        pstate["tab"] = body["tab"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "fx_mode": pstate["fx_mode"], "tab": pstate["tab"]})
                return

            if parsed.path == "/api/vdr/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.4 if is_adm else 4.2)
                dl_p = Path("/home/gui/Downloads/vdr_schedule.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    fm = pstate["fx_mode"]
                    rates = FX_AVG_2026 if fm == "AVG_2026_PL" else FX_SPOT_CLOSE
                    lines = ["section,record_id,entity_or_cat,currency,local_k,usd_rate,usd_k"]
                    for ccy, r in rates.items():
                        lines.append(f"FX_RATE,{ccy},FX_TABLE,{ccy},1.00,{r:.4f},{r:.4f}")
                    for aid, ent, ccy, amt, cls in VDR_BANK_ACCOUNTS:
                        lines.append(f"BANK_ACCOUNT,{aid},{ent}:{cls},{ccy},{amt:.2f},{rates[ccy]:.4f},{amt * rates[ccy]:.2f}")
                    for tid, ccy, amt, cat in VDR_TAX_ITEMS:
                        lines.append(f"TAX_DTL_ITEM,{tid},{cat},{ccy},{amt:.2f},{rates[ccy]:.4f},{amt * rates[ccy]:.2f}")
                    for qid, ccy, amt, cat in VDR_QOE_AUDIT_ITEMS:
                        lines.append(f"QOE_AUDIT_ITEM,{qid},{cat},{ccy},{amt:.2f},{rates[ccy]:.4f},{amt * rates[ccy]:.2f}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "path": str(dl_p), "fx_mode": fm, "rows": len(lines) - 1})
                return

            if parsed.path == "/api/vdr/copy_seal":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 1.5)
                with lock:
                    fm = pstate["fx_mode"]
                    tb = pstate["tab"]
                    seal = make_opaque_seal("ec01", f"{fm}:{tb}")
                    pstate["clipboard_copies"] += 1
                    persist()
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "fx_mode": fm, "tab": tb})
                return

            self._send_json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def grade(workspace: Path, service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    dm = workspace / "deal_model"
    xp = dm / "Merger_ProForma_2026.xlsx"
    qoe_pdf = dm / "QoE_Signoff_Pack.pdf"
    tax_pdf = dm / "Tax_Treasury_Pack.pdf"

    errs_a: list[str] = []
    errs_b: list[str] = []
    errs_joint: list[str] = []

    if not xp.is_file():
        errs_a.append("Missing Merger_ProForma_2026.xlsx")
        errs_b.append("Missing Merger_ProForma_2026.xlsx")
        raw_sh, ev_sh = {}, {}
    else:
        try:
            raw_sh = read_multisheet_xlsx(xp)
            ev_sh = evaluate_xlsx_via_libreoffice(xp)
        except Exception as exc:
            raw_sh, ev_sh = {}, {}
            errs_joint.append(f"Corrupted Merger_ProForma_2026.xlsx: {exc}")

    def _val(sh: str, ref: str) -> float:
        v = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return float(v) if isinstance(v, (int, float)) else -999999.0

    def _str(sh: str, ref: str) -> str:
        v = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return str(v or "").strip()

    def _has_f(sh: str, ref: str) -> bool:
        return bool(((raw_sh.get(sh) or {}).get(ref) or {}).get("formula"))

    if raw_sh:
        for ref, ent in (("B2", "US_CORE"), ("B3", "DE_GMBH"), ("B4", "UK_LTD"), ("B5", "JP_KK")):
            exp_v = TRUE_ENTITY_EBITDA_USD_K[ent]
            if abs(_val("QoE_Bridge", ref) - exp_v) > 1.5:
                errs_a.append(f"QoE_Bridge!{ref} ({ent})={_val('QoE_Bridge', ref)} != {exp_v}")
        if abs(_val("QoE_Bridge", "B6") - TRUE_SCAN_NET_QOE_ADJ_USD_K) > 1.5:
            errs_a.append(f"QoE_Bridge!B6={_val('QoE_Bridge', 'B6')} != {TRUE_SCAN_NET_QOE_ADJ_USD_K}")
        if not _has_f("QoE_Bridge", "B7") or abs(_val("QoE_Bridge", "B7") - TRUE_ADJUSTED_EBITDA_USD_K) > 2.0:
            errs_a.append(f"QoE_Bridge!B7 missing formula or value={_val('QoE_Bridge', 'B7')} != {TRUE_ADJUSTED_EBITDA_USD_K}")
        if _str("QoE_Bridge", "B8") != QOE_VDR_SEAL:
            errs_a.append(f"QoE_Bridge!B8 missing valid VDR_QoE_Attestation_Seal ({_str('QoE_Bridge', 'B8')!r})")
        rev_draw = _val("Debt_Covenant_Model", "B3")
        if not (REVOLVER_RANGE_USD_K[0] <= rev_draw <= REVOLVER_RANGE_USD_K[1]):
            errs_a.append(f"Senior_Revolver_Draw={rev_draw} outside {list(REVOLVER_RANGE_USD_K)}")
    if not (qoe_pdf.is_file() and qoe_pdf.stat().st_size > 1000):
        errs_a.append("Missing or empty QoE_Signoff_Pack.pdf")
    else:
        q_txt = extract_pdf_text(qoe_pdf).replace(",", "")
        rev_val = _val("Debt_Covenant_Model", "B3")
        rev_toks = (f"{rev_val:.2f}", f"{rev_val:.1f}", str(int(round(rev_val))))
        if DESK_TAG not in q_txt or "39093" not in q_txt:
            errs_a.append("QoE_Signoff_Pack.pdf missing DESK_TAG or reconciled 39093 EBITDA")
        elif not any(tok in q_txt for tok in rev_toks):
            errs_a.append(f"QoE_Signoff_Pack.pdf out of sync with live Debt_Covenant_Model!B3={rev_val}")

    if raw_sh:
        for ref, exp_t in (
            ("B2", TRUE_MACRS_DTL_USD_K),
            ("B3", TRUE_SEC382_NOL_OFFSET_USD_K),
            ("B4", TRUE_ASC740_RESERVE_USD_K),
            ("B5", TRUE_FX_BREAKAGE_USD_K),
        ):
            if abs(_val("Tax_Deferred_Schedule", ref) - exp_t) > 1.5:
                errs_b.append(f"Tax_Deferred_Schedule!{ref}={_val('Tax_Deferred_Schedule', ref)} != {exp_t}")
        if not _has_f("Tax_Deferred_Schedule", "B6") or abs(_val("Tax_Deferred_Schedule", "B6") - TRUE_NET_TAX_FX_LIAB_USD_K) > 2.0:
            errs_b.append(f"Tax_Deferred_Schedule!B6 missing formula or != {TRUE_NET_TAX_FX_LIAB_USD_K}")
        if abs(_val("Tax_Deferred_Schedule", "B7") - TRUE_UNRESTRICTED_CASH_USD_K) > 2.0:
            errs_b.append(f"Unrestricted_Closing_Cash={_val('Tax_Deferred_Schedule', 'B7')} != {TRUE_UNRESTRICTED_CASH_USD_K}")
        if _str("Tax_Deferred_Schedule", "B8") != TAX_VDR_SEAL:
            errs_b.append(f"Tax_Deferred_Schedule!B8 missing valid VDR_Tax_Attestation_Seal ({_str('Tax_Deferred_Schedule', 'B8')!r})")
        tax_note = _val("Debt_Covenant_Model", "B4")
        if not (TAX_NOTE_RANGE_USD_K[0] <= tax_note <= TAX_NOTE_RANGE_USD_K[1]):
            errs_b.append(f"Tax_Indemnity_Note={tax_note} outside {list(TAX_NOTE_RANGE_USD_K)}")
    if not (tax_pdf.is_file() and tax_pdf.stat().st_size > 1000):
        errs_b.append("Missing or empty Tax_Treasury_Pack.pdf")
    else:
        t_txt = extract_pdf_text(tax_pdf).replace(",", "")
        note_val = _val("Debt_Covenant_Model", "B4")
        note_toks = (f"{note_val:.2f}", f"{note_val:.1f}", str(int(round(note_val))))
        if (TAX_VDR_SEAL not in t_txt and DESK_TAG not in t_txt) or "19200" not in t_txt or "6860" not in t_txt:
            errs_b.append("Tax_Treasury_Pack.pdf missing VDR tax seal / DESK_TAG or reconciled 6860/19200 figures")
        elif not any(tok in t_txt for tok in note_toks):
            errs_b.append(f"Tax_Treasury_Pack.pdf out of sync with live Debt_Covenant_Model!B4={note_val}")

    if raw_sh:
        if _str("QoE_Bridge", "C1") != DESK_TAG:
            errs_joint.append(f"QoE_Bridge!C1 lost live Calc desk control tag ({_str('QoE_Bridge', 'C1')!r} != {DESK_TAG!r})")
        for ref in ("B5", "B6", "B7"):
            if not _has_f("Debt_Covenant_Model", ref):
                errs_joint.append(f"Debt_Covenant_Model!{ref} missing live formula")
        lev = _val("Debt_Covenant_Model", "B7")
        if not (LEVERAGE_BAND[0] <= lev <= LEVERAGE_BAND[1]):
            errs_joint.append(f"Net_Leverage_Ratio={lev} outside covenant band {list(LEVERAGE_BAND)}")
        if service_state.get("open_gui_split_brain") is True:
            errs_joint.append("Open LibreOffice Calc window held stale unsaved buffer inconsistent with disk workbook")
    extra_files = find_unexpected_workspace_files(dm, ALLOWED_DEAL_FILES)
    if extra_files:
        errs_joint.append(f"Unexpected scratch/coordination files in /workspace/deal_model: {extra_files[:5]}")

    pass_a = len(errs_a) == 0 and len(errs_joint) == 0
    pass_b = len(errs_b) == 0 and len(errs_joint) == 0
    return {
        "task_id": TASK_ID,
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": pass_a and pass_b,
        "errors_a": errs_a,
        "errors_b": errs_b,
        "errors_joint": errs_joint,
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_driver_and_ban_clean(build_tickets_by_role()),
        "telemetry": service_state,
    }


def solve_role(role: str, workspace: Path, port: int, careful_conc: bool = False) -> None:
    assert role in ("qoe_ebitda_lead", "tax_treasury_lead")
    dm = workspace / "deal_model"
    xp = dm / "Merger_ProForma_2026.xlsx"
    adm_p = Path("/opt/ec_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_qoe = (role == "qoe_ebitda_lead")
        fm = "AVG_2026_PL" if is_qoe else "SPOT_CLOSE_BS"
        tb = "FX_AND_CASH" if is_qoe else "TAX_ROLLFORWARD"
        urllib.request.urlopen(
            urllib.request.Request(
                f"{base}/api/vdr/state",
                data=json.dumps({"fx_mode": fm, "tab": tb}).encode("utf-8"),
                headers={"Content-Type": "application/json", **adm_hdr},
                method="POST",
            ),
            timeout=10,
        ).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/vdr/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/vdr/copy_seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        vdr_seal = get_x11_clipboard()

        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev["QoE_Bridge"].get("C1") or {}).get("value") or DESK_TAG)
        cur_ebitda = float((ev["QoE_Bridge"].get("B7") or {}).get("value") or 39400.0)
        cur_cash = float((ev["Tax_Deferred_Schedule"].get("B7") or {}).get("value") or 19100.0)
        cur_rev = float((ev["Debt_Covenant_Model"].get("B3") or {}).get("value") or 54500.0)
        cur_note = float((ev["Debt_Covenant_Model"].get("B4") or {}).get("value") or 34200.0)

        if is_qoe:
            new_ebitda = TRUE_ADJUSTED_EBITDA_USD_K
            tgt_mult = 3.06
            desired_rev = tgt_mult * new_ebitda + cur_cash - SENIOR_TERM_LOAN_FIXED_USD_K - cur_note
            new_rev = round(max(REVOLVER_RANGE_USD_K[0], min(REVOLVER_RANGE_USD_K[1], desired_rev)), 2)
            update_single_sheet_xlsx(
                xp,
                "QoE_Bridge",
                _make_qoe_rows(17200.0, 10850.0, 7620.0, 4080.0, TRUE_SCAN_NET_QOE_ADJ_USD_K, desk_tag=desk_c1, vdr_seal=vdr_seal),
            )
            update_single_sheet_xlsx(xp, "Debt_Covenant_Model", _make_debt_rows(new_rev, cur_note, new_ebitda, cur_cash))
            ev2 = evaluate_xlsx_via_libreoffice(xp)
            lev2 = float((ev2["Debt_Covenant_Model"].get("B7") or {}).get("value") or 3.06)
            nl2 = float((ev2["Tax_Deferred_Schedule"].get("B6") or {}).get("value") or 5120.0)
            update_single_sheet_xlsx(xp, "Executive_Summary", _make_exec_rows(new_ebitda, nl2, lev2))
            convert_doc_to_pdf_isolated(xp, dm / "QoE_Signoff_Pack.pdf")
        else:
            new_cash = TRUE_UNRESTRICTED_CASH_USD_K
            tgt_mult = 3.06
            desired_note = tgt_mult * cur_ebitda + new_cash - SENIOR_TERM_LOAN_FIXED_USD_K - cur_rev
            new_note = round(max(TAX_NOTE_RANGE_USD_K[0], min(TAX_NOTE_RANGE_USD_K[1], desired_note)), 2)
            update_single_sheet_xlsx(
                xp,
                "Tax_Deferred_Schedule",
                _make_tax_rows(
                    TRUE_MACRS_DTL_USD_K,
                    TRUE_SEC382_NOL_OFFSET_USD_K,
                    TRUE_ASC740_RESERVE_USD_K,
                    TRUE_FX_BREAKAGE_USD_K,
                    new_cash,
                    vdr_seal=vdr_seal,
                ),
            )
            update_single_sheet_xlsx(xp, "Debt_Covenant_Model", _make_debt_rows(cur_rev, new_note, cur_ebitda, new_cash))
            ev2 = evaluate_xlsx_via_libreoffice(xp)
            lev2 = float((ev2["Debt_Covenant_Model"].get("B7") or {}).get("value") or 3.06)
            update_single_sheet_xlsx(xp, "Executive_Summary", _make_exec_rows(cur_ebitda, TRUE_NET_TAX_FX_LIAB_USD_K, lev2))
            convert_doc_to_pdf_isolated(xp, dm / "Tax_Treasury_Pack.pdf")

        reload_open_libreoffice_window(xp)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_naive_race(workspace: Path, port: int) -> None:
    dm = workspace / "deal_model"
    xp = dm / "Merger_ProForma_2026.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "v0.xlsx"
        shutil.copy2(xp, snap)
        solve_role("qoe_ebitda_lead", workspace, port, careful_conc=False)
        shutil.copy2(snap, xp)
        update_single_sheet_xlsx(
            xp,
            "Tax_Deferred_Schedule",
            _make_tax_rows(TRUE_MACRS_DTL_USD_K, TRUE_SEC382_NOL_OFFSET_USD_K, TRUE_ASC740_RESERVE_USD_K, TRUE_FX_BREAKAGE_USD_K, TRUE_UNRESTRICTED_CASH_USD_K),
        )
        update_single_sheet_xlsx(xp, "Debt_Covenant_Model", _make_debt_rows(44106.44, 23752.0, TRUE_ADJUSTED_EBITDA_USD_K, TRUE_UNRESTRICTED_CASH_USD_K))
        convert_doc_to_pdf_isolated(xp, dm / "Tax_Treasury_Pack.pdf")

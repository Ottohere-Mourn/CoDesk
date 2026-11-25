"""AW-01: Multi-Viewport Storefront Release QA vs. 1080p Launch Reel & Press Cutover."""
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
    "id": "AW-01",
    "slug": "commerce_qa_vs_launch_reel",
    "title": "Meridian Launch Workstation: Multi-Viewport Storefront QA vs. 1080p Launch Reel & Press Cutover",
    "domain": "E-Commerce Web QA & Launch Media Production (Chromium + LibreOffice + FFmpeg + SQLite)",
    "track": "track1_isolated_ws",
    "workspace_mode": "isolated",
    "portal_port": 19601,
    "roles": ("storefront_qa_eng", "launch_reel_producer"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

SKUS_DATA: list[tuple[str, str, float, str, float, int]] = [
    ("SKU-101", "Meridian Gateway Hub", 145.00, "ambient", 0.0, 0),
    ("SKU-102", "CryoVial Sensor Pack", 88.00, "chilled_2_8c", 12.0, 1),
    ("SKU-103", "UltraCold Enzyme Kit", 164.00, "frozen_minus20c", 0.0, 0),
    ("SKU-104", "Field Power Brick 140Wh", 210.00, "hazmat_li_ion", 70.0, 2),
    ("SKU-105", "Pocket Logger 48Wh", 95.00, "hazmat_li_ion", 24.0, 2),
    ("SKU-106", "Calibration Manifold", 132.00, "ambient", 0.0, 0),
    ("SKU-107", "Biologics Media Tray", 118.00, "chilled_2_8c", 0.0, 0),
    ("SKU-108", "DeepFreeze Standard Vial", 204.00, "frozen_minus20c", 0.0, 0),
    ("SKU-109", "Telemetry Mast Pro", 164.00, "ambient", 0.0, 0),
    ("SKU-110", "Quad-Cell Array 4x36Wh", 260.00, "hazmat_li_ion", 36.0, 4),
]

CARTS_DATA: list[tuple[str, str, int, str, float, list[tuple[str, int]]]] = [
    ("CART-101", "DE", 1, "standard", 0.0, [("SKU-102", 2), ("SKU-103", 1), ("SKU-101", 1)]),
    ("CART-102", "DE", 0, "standard", 0.0, [("SKU-102", 2), ("SKU-106", 1)]),
    ("CART-103", "FR", 1, "express_air", 0.0, [("SKU-103", 2), ("SKU-105", 1)]),
    ("CART-104", "GB", 1, "standard", 5.0, [("SKU-101", 2), ("SKU-105", 1)]),
    ("CART-105", "US", 0, "express_air", 0.0, [("SKU-104", 1), ("SKU-101", 1)]),
    ("CART-106", "ES-CN", 0, "standard", 0.0, [("SKU-104", 1), ("SKU-107", 1)]),
    ("CART-107", "FR", 0, "standard", 10.0, [("SKU-108", 1), ("SKU-109", 1)]),
    ("CART-108", "JP", 1, "express_air", 0.0, [("SKU-110", 1), ("SKU-102", 1)]),
]

ARR_CONTRACTS: list[tuple[str, int, str, str, float, float, float, str, str]] = [
    ("ENT-2401", 2024, "USD", "annual", 4200000.0, 680000.0, 120000.0, "active", "organic"),
    ("ENT-2402", 2024, "EUR", "annual", 3100000.0, 520000.0, 0.0, "active", "organic"),
    ("ENT-2403", 2025, "GBP", "annual", 1850000.0, 290000.0, 95000.0, "active", "organic"),
    ("ENT-2404", 2025, "USD", "annual", 1450000.0, 0.0, 0.0, "churned", "organic"),
    ("ENT-2501", 2025, "JPY", "annual", 240000000.0, 45000000.0, 10000000.0, "active", "organic"),
    ("ENT-2502", 2025, "EUR", "annual", 2250000.0, 410000.0, 80000.0, "active", "organic"),
    ("ENT-2503", 2024, "USD", "annual", 3600000.0, 740000.0, 150000.0, "active", "organic"),
    ("ENT-2504", 2025, "USD", "monthly", 95000.0, 18000.0, 3000.0, "active", "organic"),
    ("ENT-2505", 2025, "EUR", "annual", 1600000.0, 420000.0, 0.0, "active", "mna_assumed"),
    ("ENT-2601", 2026, "USD", "annual", 0.0, 2650000.0, 0.0, "active", "organic"),
    ("ENT-2602", 2026, "EUR", "annual", 0.0, 1750000.0, 0.0, "active", "organic"),
]

CC_FX: dict[str, float] = {"USD": 1.0, "EUR": 1.08, "GBP": 1.26, "JPY": 0.0068}
SPOT_FX: dict[str, float] = {"USD": 1.0, "EUR": 1.13, "GBP": 1.32, "JPY": 0.0073}

COGS_LINES: list[tuple[str, float, str]] = [
    ("Hosting_Compute_Core", 5420000.0, "recurring_cogs"),
    ("ColdChain_Telemetry_SIM", 1680000.0, "recurring_cogs"),
    ("Customer_Success_Eng", 1890000.0, "recurring_cogs"),
    ("Support_Equity_Awards_ASC718", 240000.0, "equity_comp"),
    ("Vendor_Cloud_Migration_Credit", -460000.0, "vendor_credit"),
    ("Acquired_Intangible_Amort_COGS", 310000.0, "mna_amort"),
]
GAAP_REV_USD = 29500000.0
WRITER_LATE_HOSTING_ACCRUAL_USD = 185000.0

SLIDE_PALETTES: list[tuple[str, str, str]] = [
    ("#0f172a", "#2563eb", "Meridian OS 4.0 Global Cutover"),
    ("#111827", "#10b981", "Constant-Currency ARR Growth"),
    ("#1e1b4b", "#f59e0b", "Enterprise Cohort Net Retention"),
    ("#0c4a6e", "#ec4899", "Non-GAAP Gross Margin Expansion"),
    ("#14532d", "#06b6d4", "Cold-Chain SLA & HazMat Routing"),
    ("#31102f", "#8b5cf6", "FY27 Outlook & Release Signoff"),
]

TICKET_A = (
    "# Work Order — Storefront Release QA Engineer (`storefront_qa_eng`)\n\n"
    "Prepare the Meridian Commerce Q4 storefront (`http://127.0.0.1:19601/`) for release cutover from `/workspace`:\n\n"
    "1. Review `/workspace/specs/Commerce_QA_Standard.pdf` and audit `/workspace/catalog_orders_q4.sqlite` (`skus`, `sample_carts`, `cart_items`).\n"
    "2. In the open **Chromium** browser (`Meridian Staging Workbench` at `http://127.0.0.1:19601`), remediate the storefront's WCAG AA CTA contrast and mobile promo banner height (updating `/workspace/theme_override.css` as well).\n"
    "3. Using the workbench's live preview & capture controls in Chromium (which export PNGs into `/home/user/Downloads`), capture clean post-remediation storefront screenshots and copy them to:\n"
    "   - `/workspace/captures/mobile_375x812.png`\n"
    "   - `/workspace/captures/tablet_768x1024.png`\n"
    "   - `/workspace/captures/desktop_1440x900.png`\n"
    "4. Update `/workspace/Storefront_Defect_Tracker.xlsx` (`Cart_Audit` with `D10` set to the non-blocked payable sum, and `WCAG_Signoff`), export `/workspace/Storefront_QA_Signoff.pdf`, and write `/workspace/qa_release_audit.json` with:\n"
    "   - `cart_totals_usd` (mapping `CART-101`..`CART-108` -> rounded 2-decimal USD total)\n"
    "   - `air_blocked_carts` (sorted list of blocked cart IDs)\n"
    "   - `hazmat_surcharge_carts` (sorted list of standard-tier HazMat cart IDs)\n"
    "   - `eu_reverse_charge_carts` (sorted list of intra-EU B2B reverse-charge cart IDs)\n"
    "   - `payable_nonblocked_sum_usd`, `wcag_cta_contrast_ratio`, and `mobile_promo_height_px`\n"
)

TICKET_B = (
    "# Work Order — Launch Reel & Investor Comms Producer (`launch_reel_producer`)\n\n"
    "Produce the verified 1080p Meridian OS 4.0 launch reel and final press release package in `/workspace`:\n\n"
    "1. Review `/workspace/specs/CFO_ARR_Bridge_Policy.pdf`, reconcile `/workspace/investor_ledger_fy26.sqlite` (`arr_contracts`, `fx_rates`, `financial_lines`), and inspect the open **LibreOffice Writer** window on the desktop to incorporate both the live `board_headline_tag` and any late Q4 hosting accrual note.\n"
    "2. In the open **Chromium** browser (`Meridian Staging Workbench` at `http://127.0.0.1:19601`, `Launch Deck` mode), publish the reconciled KPIs (`cc_ending_arr_musd`, `enterprise_nrr_pct`, `nongaap_gross_margin_pct`, `board_headline_tag`) so all 6 slides display live verified figures.\n"
    "3. Export slides 1 through 6 at `1920x1080` via the workbench capture controls into `/home/user/Downloads`, copy them to `/workspace/frames/slide_01.png` .. `/workspace/frames/slide_06.png`, and encode `/workspace/reel/meridian_launch_1080p.mp4` (`1920x1080`, H.264 `yuv420p`, ~12.0s total at 2s per slide).\n"
    "4. Save the completed press release (with the headline release code and all three verified KPIs) to `/workspace/press/Press_Release_Draft.odt`, export `/workspace/press/Press_Release_Final.pdf`, and write `/workspace/press_metrics.json` with:\n"
    "   - `cc_ending_arr_musd`, `cohort_starting_arr_musd`, `cohort_ending_arr_musd`, `new_logo_arr_musd`, `churned_arr_musd`\n"
    "   - `enterprise_nrr_pct`, `gaap_gross_margin_pct`, `nongaap_gross_margin_pct`, `board_headline_tag`\n"
)


def _srgb_channel(c_8bit: int) -> float:
    v = c_8bit / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def hex_contrast_ratio(hex1: str, hex2: str) -> float:
    def _lum(hx: str) -> float:
        s = hx.strip().lstrip("#")
        if len(s) == 3:
            s = "".join(ch * 2 for ch in s)
        if len(s) != 6:
            return 0.0
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)

    l1, l2 = _lum(hex1), _lum(hex2)
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


def compute_qa_oracle() -> dict[str, Any]:
    sku_map = {sid: {"price": pr, "regime": reg, "pack_wh": wh_c * cells} for sid, _, pr, reg, wh_c, cells in SKUS_DATA}
    cart_totals: dict[str, float] = {}
    air_blocked: list[str] = []
    hazmat_carts: list[str] = []
    eu_rc_carts: list[str] = []

    for cid, country, b2b_ok, tier, promo_pct, items in CARTS_DATA:
        gross_merch = sum(sku_map[s]["price"] * qty for s, qty in items)
        merch = round(gross_merch * (1.0 - promo_pct / 100.0), 2)
        regimes = {sku_map[s]["regime"] for s, _ in items}
        max_wh = max(sku_map[s]["pack_wh"] for s, _ in items)

        base_ship = 15.0 if tier == "standard" else 42.0
        if "frozen_minus20c" in regimes:
            cold_fee = 32.0
        elif "chilled_2_8c" in regimes:
            cold_fee = 18.5
        else:
            cold_fee = 0.0
        if cold_fee > 0.0 and merch >= 350.0 and tier == "standard":
            cold_fee = 0.0

        blocked = bool(tier == "express_air" and max_wh > 100.0)
        if blocked:
            air_blocked.append(cid)
        haz_fee = 24.0 if (max_wh > 100.0 and tier == "standard") else 0.0
        if haz_fee > 0.0:
            hazmat_carts.append(cid)

        taxable = merch + base_ship + cold_fee + haz_fee
        if country in ("DE", "FR") and b2b_ok == 1:
            vat_rate = 0.0
            eu_rc_carts.append(cid)
        elif country == "DE":
            vat_rate = 0.19
        elif country in ("FR", "GB"):
            vat_rate = 0.20
        else:
            vat_rate = 0.0

        total = round(taxable * (1.0 + vat_rate), 2)
        cart_totals[cid] = total

    payable_sum = round(sum(v for k, v in cart_totals.items() if k not in air_blocked), 2)
    return {
        "cart_totals_usd": cart_totals,
        "air_blocked_carts": sorted(air_blocked),
        "hazmat_surcharge_carts": sorted(hazmat_carts),
        "eu_reverse_charge_carts": sorted(eu_rc_carts),
        "payable_nonblocked_sum_usd": payable_sum,
    }


def compute_reel_oracle() -> dict[str, Any]:
    cc_end_total = 0.0
    cohort_start_cc = 0.0
    cohort_end_cc = 0.0
    churned_arr_cc = 0.0
    new_logo_arr_cc = 0.0
    for _cid, cyr, curr, basis, s_loc, exp_loc, con_loc, status, channel in ARR_CONTRACTS:
        fx = CC_FX[curr]
        mult = 12.0 if basis == "monthly" else 1.0
        s_usd = s_loc * mult * fx
        if status == "churned":
            e_usd = 0.0
            if channel == "organic":
                churned_arr_cc += s_usd
        else:
            e_usd = (s_loc + exp_loc - con_loc) * mult * fx
        cc_end_total += e_usd
        if cyr <= 2025 and channel == "organic":
            cohort_start_cc += s_usd
            cohort_end_cc += e_usd
        elif cyr == 2026:
            new_logo_arr_cc += e_usd

    nrr_pct = round((cohort_end_cc / cohort_start_cc) * 100.0, 2)
    gaap_cogs = sum(v for _, v, _ in COGS_LINES) + WRITER_LATE_HOSTING_ACCRUAL_USD
    nongaap_cogs = gaap_cogs - 240000.0 - 310000.0 + 460000.0
    nongaap_gm_pct = round(((GAAP_REV_USD - nongaap_cogs) / GAAP_REV_USD) * 100.0, 2)
    return {
        "cc_ending_arr_musd": round(cc_end_total / 1e6, 3),
        "cohort_starting_arr_musd": round(cohort_start_cc / 1e6, 3),
        "cohort_ending_arr_musd": round(cohort_end_cc / 1e6, 3),
        "new_logo_arr_musd": round(new_logo_arr_cc / 1e6, 3),
        "churned_arr_musd": round(churned_arr_cc / 1e6, 3),
        "enterprise_nrr_pct": nrr_pct,
        "gaap_gross_margin_pct": round(((GAAP_REV_USD - gaap_cogs) / GAAP_REV_USD) * 100.0, 2),
        "nongaap_gross_margin_pct": nongaap_gm_pct,
        "board_headline_tag": "MERIDIAN-OS4-GA-2026Q4",
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    ws_a = workspace_root / "storefront_qa_eng"
    ws_b = workspace_root / "launch_reel_producer"
    for d in (ws_a / "specs", ws_a / "captures", ws_b / "specs", ws_b / "frames", ws_b / "reel", ws_b / "press"):
        d.mkdir(parents=True, exist_ok=True)

    # Role A SQLite catalog & carts
    db_a = ws_a / "catalog_orders_q4.sqlite"
    db_a.unlink(missing_ok=True)
    con_a = sqlite3.connect(db_a)
    con_a.execute(
        "CREATE TABLE skus (sku_id TEXT PRIMARY KEY, name TEXT, unit_price_usd REAL, storage_regime TEXT, wh_per_cell REAL, cell_count INTEGER)"
    )
    con_a.executemany("INSERT INTO skus VALUES (?,?,?,?,?,?)", SKUS_DATA)
    con_a.execute(
        "CREATE TABLE sample_carts (cart_id TEXT PRIMARY KEY, destination_code TEXT, b2b_vat_verified INTEGER, shipping_tier TEXT, promo_discount_pct REAL)"
    )
    con_a.execute("CREATE TABLE cart_items (cart_id TEXT, sku_id TEXT, qty INTEGER)")
    for cid, ctry, b2b, tier, promo_pct, items in CARTS_DATA:
        con_a.execute("INSERT INTO sample_carts VALUES (?,?,?,?,?)", (cid, ctry, b2b, tier, promo_pct))
        for sid, q in items:
            con_a.execute("INSERT INTO cart_items VALUES (?,?,?)", (cid, sid, q))
    con_a.commit()
    con_a.close()

    (ws_a / "theme_override.css").write_text(
        "/* Initial staging stylesheet (contains WCAG contrast & mobile banner layout bugs) */\n"
        ":root {\n"
        "  --cta-bg: #cbd5e1;\n"
        "  --cta-fg: #94a3b8;\n"
        "  --mobile-promo-height: 148px;\n"
        "}\n",
        encoding="utf-8",
    )

    write_multisheet_xlsx(
        ws_a / "Storefront_Defect_Tracker.xlsx",
        [
            (
                "Cart_Audit",
                [
                    ["Cart_ID", "Country", "Tier", "Gross_Total_USD", "Air_Blocked_Flag"],
                    *[[cid, ctry, tier, 0.0, "PENDING"] for cid, ctry, _b, tier, _p, _it in CARTS_DATA],
                    ["PAYABLE_NONBLOCKED_SUM", "", "", ("=SUM(D2:D9)", 0.0), ""],
                ],
            ),
            (
                "WCAG_Signoff",
                [
                    ["Metric", "Value"],
                    ["CTA_Bg_Hex", "#cbd5e1"],
                    ["CTA_Fg_Hex", "#94a3b8"],
                    ["CTA_Contrast_Ratio", 1.46],
                    ["Mobile_Promo_Height_Px", 148],
                ],
            ),
        ],
    )

    write_pdf_manual(
        ws_a / "specs" / "Commerce_QA_Standard.pdf",
        "Meridian Commerce Release QA Standard (Rev 4.2)",
        [
            (
                "1. Shipping Base Rates & Cold-Chain Pack Rules",
                [
                    "Apply promotional discounts (promo_discount_pct) to gross item prices first to obtain net discounted merchandise subtotal (rounded to 2 decimals). Base freight is $15.00 USD for 'standard' and $42.00 USD for 'express_air'.",
                    "Cold-chain insulated pack surcharge: $32.00 USD if any cart line requires 'frozen_minus20c', else $18.50 USD if any line requires 'chilled_2_8c' (only the highest single cold-chain tier applies per cart).",
                    "Waive the cold-chain surcharge solely when net post-discount merchandise subtotal is at least $350.00 USD AND shipping_tier is 'standard'. Express air orders never qualify for cold-chain fee waivers.",
                ],
            ),
            (
                "2. Lithium-Ion HazMat Air Restriction & Ground Handling",
                [
                    "Under IATA Packing Instruction 965, evaluate total battery pack energy per SKU as wh_per_cell * cell_count. Any cart containing a SKU whose total pack energy exceeds 100.0 Wh is banned from 'express_air' (record in air_blocked_carts and omit from payable_nonblocked_sum_usd, while still recording its theoretical total in cart_totals_usd).",
                    "On 'standard' surface transport, carts containing any SKU with total pack energy > 100.0 Wh carry a flat $24.00 USD HazMat handling fee.",
                ],
            ),
            (
                "3. Dispatch Warehouse & Cross-Border VAT Rules",
                [
                    "Orders ship DDP from Frankfurt (DE). VAT applies to (net_merchandise + base_shipping + cold_chain_fee + hazmat_fee).",
                    "Standard VAT is 19% for DE and 20% for FR. Verified intra-EU VAT-registered buyers (destination_code in DE or FR with b2b_vat_verified = 1) clear at 0% reverse-charge (list in eu_reverse_charge_carts).",
                    "Special territorial rules: post-Brexit Great Britain ('GB') DDP checkout always collects 20% UK import VAT regardless of B2B flag. The Canary Islands ('ES-CN') lie outside the EU VAT directive territory and are zero-rated (0% export, not intra-EU reverse charge), as are 'US' and 'JP'.",
                ],
            ),
            (
                "4. WCAG 2.1 AA Remediation & Live Multi-Viewport Evidence",
                [
                    "In the authenticated Meridian Staging Workbench open in Chromium, apply CTA colors achieving WCAG 2.1 AA contrast >= 4.50:1 and collapse mobile_promo_height_px <= 44 (updating /workspace/theme_override.css to match).",
                    "Switch the workbench preview to Storefront mode and export each required viewport (375x812, 768x1024, 1440x900) to /home/user/Downloads, then place verified PNGs in /workspace/captures/.",
                ],
            ),
        ],
    )

    # Role B SQLite ARR & COGS ledger + Writer draft + CFO PDF manual
    db_b = ws_b / "investor_ledger_fy26.sqlite"
    db_b.unlink(missing_ok=True)
    con_b = sqlite3.connect(db_b)
    con_b.execute(
        "CREATE TABLE arr_contracts (contract_id TEXT PRIMARY KEY, cohort_year INTEGER, currency TEXT, "
        "billing_basis TEXT, starting_rate_local REAL, expansion_rate_local REAL, contraction_rate_local REAL, "
        "contract_status TEXT, origin_channel TEXT)"
    )
    con_b.executemany("INSERT INTO arr_contracts VALUES (?,?,?,?,?,?,?,?,?)", ARR_CONTRACTS)
    con_b.execute("CREATE TABLE fx_rates (currency TEXT PRIMARY KEY, cc_budget_fy26 REAL, spot_q4_close REAL)")
    for c_code in ("USD", "EUR", "GBP", "JPY"):
        con_b.execute("INSERT INTO fx_rates VALUES (?,?,?)", (c_code, CC_FX[c_code], SPOT_FX[c_code]))
    con_b.execute("CREATE TABLE financial_lines (line_item TEXT PRIMARY KEY, amount_usd REAL, category TEXT)")
    con_b.execute("INSERT INTO financial_lines VALUES ('GAAP_Recognized_Revenue', ?, 'revenue')", (GAAP_REV_USD,))
    for li, amt, cat in COGS_LINES:
        con_b.execute("INSERT INTO financial_lines VALUES (?,?,?)", (li, amt, cat))
    con_b.commit()
    con_b.close()

    write_odt_document(
        ws_b / "press" / "Press_Release_Draft.odt",
        "Meridian OS 4.0 Launch Press Release (DRAFT)",
        [
            (
                "Executive Summary",
                [
                    "Headline Release Code: PENDING_DESKTOP_BUFFER",
                    "Constant-Currency Ending ARR ($M): TBD",
                    "Enterprise Prior-Cohort NRR (%): TBD",
                    "Non-GAAP Gross Margin (%): TBD",
                ],
            ),
        ],
    )

    write_pdf_manual(
        ws_b / "specs" / "CFO_ARR_Bridge_Policy.pdf",
        "CFO Disclosure & Launch Reel Production Standard (FY26 Close)",
        [
            (
                "1. Constant-Currency Ending ARR Methodology",
                [
                    "Check billing_basis on every row in arr_contracts: rows with billing_basis = 'monthly' store monthly recurring amounts (MRR) and must be annualized (x12) before combining with 'annual' rows! Translate non-USD contracts at fx_rates.cc_budget_fy26.",
                    "Active contracts contribute (starting + expansion - contraction) annualized in constant-currency USD to Ending ARR (including mna_assumed contracts). Churned contracts contribute $0 to Ending ARR.",
                ],
            ),
            (
                "2. Enterprise Prior-Cohort Net Dollar Retention (NRR)",
                [
                    "Organic Enterprise NRR measures retention strictly across organic customers entering FY26 (cohort_year <= 2025 AND origin_channel = 'organic'). Exclude both FY2026 new logos (cohort_year = 2026) and assumed M&A contracts (origin_channel = 'mna_assumed') from cohort_starting_arr_musd, cohort_ending_arr_musd, churned_arr_musd, and enterprise_nrr_pct.",
                ],
            ),
            (
                "3. Non-GAAP Gross Margin Reconciliation",
                [
                    "Inspect the open LibreOffice Writer draft on the desktop: incorporate any unbooked late Q4 hosting accrual noted by the Controller into GAAP Cost of Revenue before computing gaap_gross_margin_pct.",
                    "To reconcile GAAP COGS to Non-GAAP COGS, exclude ASC 718 equity compensation and M&A acquired intangible amortization, and reverse out one-time vendor migration credits so non-recurring rebates do not inflate Non-GAAP Gross Margin.",
                ],
            ),
            (
                "4. Live 1080p Launch Deck, H.264 Reel & Writer Release Brief",
                [
                    "Publish reconciled KPIs in the Meridian Staging Workbench (Launch Deck tab in Chromium), export each slide 1..6 at 1920x1080 via the workbench capture button to /home/user/Downloads, assemble /workspace/reel/meridian_launch_1080p.mp4 (2.0s per slide, 12.0s H.264), and finalize Press_Release_Draft.odt + Press_Release_Final.pdf.",
                ],
            ),
        ],
    )

    (tickets_root / "storefront_qa_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "launch_reel_producer").mkdir(parents=True, exist_ok=True)
    (tickets_root / "storefront_qa_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "launch_reel_producer" / "task.md").write_text(TICKET_B, encoding="utf-8")


def _render_storefront_html(theme: dict[str, Any]) -> str:
    bg = str(theme.get("cta_bg", "#cbd5e1"))
    fg = str(theme.get("cta_fg", "#94a3b8"))
    mh = int(theme.get("mobile_promo_height_px", 148))
    cr = hex_contrast_ratio(bg, fg)
    badge = "WCAG_AA_PASS" if (cr >= 4.5 and mh <= 44) else "WCAG_FAIL_STAGING"
    top_bar = "#16a34a" if badge == "WCAG_AA_PASS" else "#dc2626"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>Meridian Commerce Storefront</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: DejaVu Sans, sans-serif; }}
  body {{ background: #f8fafc; color: #0f172a; }}
  .qa-band {{ height: 36px; background: {top_bar}; color: #fff; display: flex; align-items: center; padding: 0 20px; font-weight: 700; font-size: 14px; }}
  .mobile-promo {{ height: {mh}px; background: #fef3c7; border-bottom: 2px solid #f59e0b; padding: 8px 20px; font-size: 13px; color: #78350f; }}
  .hero {{ padding: 36px 24px; background: #ffffff; border-bottom: 1px solid #e2e8f0; }}
  .hero h1 {{ font-size: 28px; margin-bottom: 12px; }}
  .hero-cta {{ display: inline-block; padding: 14px 28px; border-radius: 8px; background: {bg}; color: {fg}; font-weight: 700; font-size: 16px; border: none; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; padding: 24px; }}
  .card {{ background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; }}
  .drawer {{ margin: 24px; padding: 16px; background: #f1f5f9; border-radius: 8px; border: 1px solid #94a3b8; }}
</style></head>
<body>
  <div class="qa-band" id="qa-status">MERIDIAN STOREFRONT | {badge} | CTA Contrast: {cr}:1 | PromoPx: {mh}</div>
  <div class="mobile-promo">Frankfurt Cold-Chain Hub Dispatch — Standard &amp; Express Air Checkout</div>
  <div class="hero">
    <h1>Cold-Chain &amp; Industrial Telemetry Storefront</h1>
    <p style="margin-bottom:16px;">Validated EU/Global B2B Checkout — Q4 Cutover Candidate</p>
    <button class="hero-cta" id="primary-cta">Proceed to Verified Checkout</button>
  </div>
  <div class="grid">
    <div class="card"><h3>CryoVial Sensor Pack</h3><p>$88.00 | Chilled 2–8C | 12Wh</p></div>
    <div class="card"><h3>UltraCold Enzyme Kit</h3><p>$164.00 | Frozen -20C | 0Wh</p></div>
    <div class="card"><h3>Field Power Brick 140Wh</h3><p>$210.00 | HazMat Li-Ion | Ground Only</p></div>
  </div>
  <div class="drawer">
    <h4>Live Theme Controls</h4>
    <label>CTA BG <input id="bg" value="{bg}"/></label>
    <label>CTA FG <input id="fg" value="{fg}"/></label>
    <label>Mobile Promo Height <input id="mh" type="number" value="{mh}"/></label>
    <button onclick="fetch('/api/theme',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{cta_bg:document.getElementById('bg').value,cta_fg:document.getElementById('fg').value,mobile_promo_height_px:Number(document.getElementById('mh').value)}})}}).then(()=>location.reload())">Apply Theme</button>
  </div>
</body></html>"""


def _render_deck_html(slide_idx: int, deck: dict[str, Any]) -> str:
    idx = max(1, min(6, slide_idx)) - 1
    bg_hex, acc_hex, title = SLIDE_PALETTES[idx]
    verified = bool(deck.get("verified_kpis_live"))
    arr_txt = f"${deck.get('cc_ending_arr_musd', 'TBD_UNVERIFIED')}M"
    nrr_txt = f"{deck.get('enterprise_nrr_pct', 'TBD_UNVERIFIED')}%"
    gm_txt = f"{deck.get('nongaap_gross_margin_pct', 'TBD_UNVERIFIED')}%"
    tag_txt = str(deck.get("board_headline_tag") or "PENDING_TAG")
    status_col = "#22c55e" if verified else "#ef4444"
    bar_w = 240 + idx * 140
    return f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>Meridian Launch Deck - Slide {idx+1}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: DejaVu Sans, sans-serif; }}
  html, body {{ width: 100%; height: 100%; overflow: hidden; background: {bg_hex}; color: #f8fafc; }}
  .top-stripe {{ height: 48px; background: {acc_hex}; display: flex; align-items: center; justify-content: space-between; padding: 0 40px; font-weight: 700; font-size: 18px; }}
  .main {{ padding: 72px 80px; }}
  h1 {{ font-size: 54px; margin-bottom: 24px; }}
  .kpi-row {{ display: flex; gap: 36px; margin-top: 36px; }}
  .kpi-box {{ background: rgba(255,255,255,0.10); border-left: 10px solid {acc_hex}; padding: 28px 36px; border-radius: 12px; min-width: 320px; }}
  .kpi-val {{ font-size: 46px; font-weight: 800; margin-top: 10px; }}
  .chart-bar {{ margin-top: 56px; height: 64px; width: {bar_w}px; background: {acc_hex}; border-radius: 8px; }}
  .status-pill {{ display: inline-block; padding: 6px 16px; background: {status_col}; color: #052e16; font-weight: 800; border-radius: 999px; }}
</style></head>
<body>
  <div class="top-stripe">
    <span>MERIDIAN LAUNCH DECK | SLIDE {idx+1} OF 6 | {tag_txt}</span>
    <span class="status-pill">{'KPI_VERIFIED' if verified else 'UNVERIFIED_DRAFT'}</span>
  </div>
  <div class="main">
    <h1>{title}</h1>
    <p style="font-size:24px;opacity:0.9;">FY26 Constant-Currency Financial &amp; Operational Release Summary</p>
    <div class="kpi-row">
      <div class="kpi-box"><div>CC Ending ARR</div><div class="kpi-val">{arr_txt}</div></div>
      <div class="kpi-box"><div>Cohort Enterprise NRR</div><div class="kpi-val">{nrr_txt}</div></div>
      <div class="kpi-box"><div>Non-GAAP Gross Margin</div><div class="kpi-val">{gm_txt}</div></div>
    </div>
    <div class="chart-bar"></div>
  </div>
</body></html>"""


def _headless_render_png(url: str, width: int, height: int, out_png: Path) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    prof = Path(f"/tmp/aw01_cap_{secrets.token_hex(4)}")
    prof.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}",
                f"--window-size={width},{height}", f"--screenshot={out_png}", url,
            ],
            check=True, capture_output=True, timeout=25,
        )
        out_png.chmod(0o644)
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    internal_tok = secrets.token_hex(12)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {
        "active_surface": "storefront",
        "storefront_vp": "1440x900",
        "deck_slide": 1,
        "surface_switches": 0,
        "theme": {"cta_bg": "#cbd5e1", "cta_fg": "#94a3b8", "mobile_promo_height_px": 148, "updates": 0},
        "deck": {
            "cc_ending_arr_musd": "TBD_UNVERIFIED",
            "enterprise_nrr_pct": "TBD_UNVERIFIED",
            "nongaap_gross_margin_pct": "TBD_UNVERIFIED",
            "board_headline_tag": "PENDING_TAG",
            "verified_kpis_live": False,
            "updates": 0,
        },
        "captures": [],
    }

    def _persist() -> None:
        write_json(state_file, state)

    _persist()
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw01_sess" in ck) and (ck["aw01_sess"].value == tok)

        def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", hdrs: list[tuple[str, str]] | None = None) -> None:
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
                self._send(200, b'{"ok":true}')
                return
            if parsed.path == "/auth":
                if (qs.get("token") or [""])[0] == tok:
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw01_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden", "text/plain")
                return
            if parsed.path == "/_render_storefront" and (qs.get("k") or [""])[0] == internal_tok:
                with lock:
                    html = _render_storefront_html(state["theme"])
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/_render_deck" and (qs.get("k") or [""])[0] == internal_tok:
                s_num = int((qs.get("slide") or ["1"])[0])
                with lock:
                    html = _render_deck_html(s_num, state["deck"])
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Authenticated Meridian Workbench Session Required (Use open Chromium window)</h3>", "text/html; charset=utf-8")
                return
            if parsed.path == "/api/state":
                with lock:
                    self._send(200, json.dumps(state).encode("utf-8"))
                return
            if parsed.path == "/select":
                with lock:
                    surf = (qs.get("surface") or [state["active_surface"]])[0]
                    if surf in ("storefront", "deck") and surf != state["active_surface"]:
                        state["active_surface"] = surf
                        state["surface_switches"] = int(state["surface_switches"]) + 1
                    vp = (qs.get("vp") or [""])[0]
                    if vp in ("375x812", "768x1024", "1440x900"):
                        state["storefront_vp"] = vp
                    sl = (qs.get("slide") or [""])[0]
                    if sl.isdigit() and 1 <= int(sl) <= 6:
                        state["deck_slide"] = int(sl)
                    _persist()
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            if parsed.path == "/capture_active":
                fname_req = (qs.get("out") or [""])[0].strip()
                with lock:
                    surf = state["active_surface"]
                    vp = state["storefront_vp"]
                    sl = int(state["deck_slide"])
                dl = Path("/home/user/Downloads")
                dl.mkdir(parents=True, exist_ok=True)
                if surf == "storefront":
                    w_s, h_s = [int(x) for x in vp.split("x")]
                    default_name = f"storefront_{vp}.png"
                    target_url = f"http://127.0.0.1:{port}/_render_storefront?k={internal_tok}"
                else:
                    w_s, h_s = 1920, 1080
                    default_name = f"slide_0{sl}.png"
                    target_url = f"http://127.0.0.1:{port}/_render_deck?k={internal_tok}&slide={sl}"
                safe_name = Path(fname_req).name if fname_req.endswith(".png") else default_name
                out_p = dl / safe_name
                _headless_render_png(target_url, w_s, h_s, out_p)
                with lock:
                    state["captures"].append({"file": safe_name, "surface": surf, "size": f"{w_s}x{h_s}"})
                    _persist()
                self._send(302, b"", hdrs=[("Location", f"/?captured={safe_name}")])
                return
            with lock:
                surf = state["active_surface"]
                vp = state["storefront_vp"]
                sl = int(state["deck_slide"])
                th = dict(state["theme"])
                dk = dict(state["deck"])
            cr = hex_contrast_ratio(th["cta_bg"], th["cta_fg"])
            preview_body = _render_storefront_html(th) if surf == "storefront" else _render_deck_html(sl, dk)
            wb_html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Meridian Staging Workbench</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;margin:0;background:#0f172a;color:#f8fafc;}}
            .bar{{padding:14px 20px;background:#1e293b;border-bottom:1px solid #334155;display:flex;flex-wrap:wrap;gap:10px;align-items:center;}}
            .bar a,.bar button{{padding:7px 12px;border-radius:6px;background:#2563eb;color:#fff;text-decoration:none;border:none;font-weight:700;cursor:pointer;font-size:13px;}}
            .forms{{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px 20px;background:#0f172a;}}
            .fbox{{background:#1e293b;padding:12px;border-radius:8px;border:1px solid #334155;font-size:13px;}}
            .fbox input{{width:110px;padding:4px;margin:2px 6px 2px 2px;}}
            iframe{{width:100%;height:560px;border:none;background:#fff;}}</style></head>
            <body>
            <div class="bar">
              <b>ACTIVE SURFACE: {surf.upper()} ({vp if surf=='storefront' else f'Slide {sl} @ 1920x1080'})</b>
              <a href="/select?surface=storefront&vp=375x812" id="vp-mob">Storefront 375x812</a>
              <a href="/select?surface=storefront&vp=768x1024" id="vp-tab">Storefront 768x1024</a>
              <a href="/select?surface=storefront&vp=1440x900" id="vp-desk">Storefront 1440x900</a>
              <a href="/select?surface=deck&slide=1" id="sl-1">Deck S1</a>
              <a href="/select?surface=deck&slide=2" id="sl-2">Deck S2</a>
              <a href="/select?surface=deck&slide=3" id="sl-3">Deck S3</a>
              <a href="/select?surface=deck&slide=4" id="sl-4">Deck S4</a>
              <a href="/select?surface=deck&slide=5" id="sl-5">Deck S5</a>
              <a href="/select?surface=deck&slide=6" id="sl-6">Deck S6</a>
              <a href="/capture_active" id="btn-cap" style="background:#16a34a;">Capture Active View PNG to ~/Downloads</a>
            </div>
            <div class="forms">
              <div class="fbox">
                <b>Storefront WCAG Theme (Current Contrast: {cr}:1, PromoPx: {th['mobile_promo_height_px']})</b><br/>
                BG <input id="bg" value="{th['cta_bg']}"/> FG <input id="fg" value="{th['cta_fg']}"/> PromoPx <input id="mh" value="{th['mobile_promo_height_px']}"/>
                <button id="apply-theme" onclick="fetch('/api/theme',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{cta_bg:document.getElementById('bg').value,cta_fg:document.getElementById('fg').value,mobile_promo_height_px:Number(document.getElementById('mh').value)}})}}).then(()=>location.reload())">Save Theme</button>
              </div>
              <div class="fbox">
                <b>Launch Deck Live KPIs ({'VERIFIED' if dk['verified_kpis_live'] else 'UNVERIFIED'})</b><br/>
                ARR($M) <input id="d_arr" value="{dk['cc_ending_arr_musd']}"/> NRR(%) <input id="d_nrr" value="{dk['enterprise_nrr_pct']}"/>
                NonGAAP GM(%) <input id="d_gm" value="{dk['nongaap_gross_margin_pct']}"/> Tag <input id="d_tag" value="{dk['board_headline_tag']}"/>
                <button id="apply-deck" onclick="fetch('/api/deck_session',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{cc_ending_arr_musd:Number(document.getElementById('d_arr').value),enterprise_nrr_pct:Number(document.getElementById('d_nrr').value),nongaap_gross_margin_pct:Number(document.getElementById('d_gm').value),board_headline_tag:document.getElementById('d_tag').value}})}}).then(()=>location.reload())">Publish Deck KPIs</button>
              </div>
            </div>
            <iframe srcdoc="{preview_body.replace('&', '&amp;').replace(chr(34), '&quot;')}"></iframe>
            </body></html>"""
            self._send(200, wb_html.encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self) -> None:
            if not self._authed():
                self._send(401, b'{"error":"unauthorized_browser_session"}')
                return
            ln = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(ln) if ln > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send(400, b'{"error":"invalid_json"}')
                return
            if self.path == "/api/theme":
                with lock:
                    bg = str(payload.get("cta_bg", state["theme"]["cta_bg"])).strip()
                    fg = str(payload.get("cta_fg", state["theme"]["cta_fg"])).strip()
                    mh = int(payload.get("mobile_promo_height_px", state["theme"]["mobile_promo_height_px"]))
                    cr = hex_contrast_ratio(bg, fg)
                    state["theme"] = {
                        "cta_bg": bg,
                        "cta_fg": fg,
                        "mobile_promo_height_px": mh,
                        "contrast_ratio": cr,
                        "updates": int(state["theme"].get("updates", 0)) + 1,
                    }
                    _persist()
                    resp = dict(state["theme"])
                self._send(200, json.dumps({"ok": True, "theme": resp}).encode("utf-8"))
                return
            if self.path == "/api/deck_session":
                with lock:
                    for k in ("cc_ending_arr_musd", "enterprise_nrr_pct", "nongaap_gross_margin_pct", "board_headline_tag"):
                        if k in payload:
                            state["deck"][k] = payload[k]
                    state["deck"]["verified_kpis_live"] = all(
                        state["deck"].get(k) not in ("", None, "TBD_UNVERIFIED", "PENDING_TAG")
                        for k in ("cc_ending_arr_musd", "enterprise_nrr_pct", "nongaap_gross_margin_pct", "board_headline_tag")
                    )
                    state["deck"]["updates"] = int(state["deck"].get("updates", 0)) + 1
                    _persist()
                    resp = dict(state["deck"])
                self._send(200, json.dumps({"ok": True, "deck": resp}).encode("utf-8"))
                return
            self._send(404, b'{"error":"not_found"}')

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1320, 880))

    if "storefront_qa_eng" in roles:
        xlsx_p = workspace_root / "storefront_qa_eng" / "Storefront_Defect_Tracker.xlsx"
        launch_desktop_app_as_user(
            f"nohup libreoffice --norestore --nologo --nofirststartwizard '{xlsx_p}' >/tmp/aw01_calc.log 2>&1 </dev/null &",
            wait_s=2.2,
        )
    if "launch_reel_producer" in roles:
        odt_p = workspace_root / "launch_reel_producer" / "press" / "Press_Release_Draft.odt"
        launch_desktop_app_as_user(
            f"nohup libreoffice --norestore --nologo --nofirststartwizard '{odt_p}' >/tmp/aw01_writer.log 2>&1 </dev/null & "
            "for _i in $(seq 1 25); do wid=$(xdotool search --onlyvisible --name 'Press_Release_Draft' 2>/dev/null | tail -n 1 || true); "
            "[ -n \"$wid\" ] && break; sleep 0.35; done; "
            "if [ -n \"$wid\" ]; then wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; "
            "sleep 0.35; xdotool key --clearmodifiers ctrl+Home; sleep 0.15; "
            "xdotool type --clearmodifiers --delay 12 -- '[CONTROLLER_NOTE: Tag=MERIDIAN-OS4-GA-2026Q4 | Unbooked_Q4_Hosting_COGS_Accrual_USD=185000] '; "
            "xdotool key --clearmodifiers Return; fi",
            wait_s=1.2,
        )


def _cdp_screenshot_url(url: str, width: int, height: int, out_png: Path, dedicated_tab: bool = True) -> None:
    """Capture an exact viewport PNG via Chromium's DevTools HTTP/WS protocol on :9222."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    py_cdp = f"""
import base64, json, socket, struct, hashlib, os, time, urllib.request

def ws_call(ws_url, messages):
    # Parse ws://127.0.0.1:9222/devtools/page/...
    rest = ws_url.split("://", 1)[1]
    host_port, path = rest.split("/", 1)
    host, port = host_port.split(":")
    path = "/" + path
    s = socket.create_connection((host, int(port)), timeout=15)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {{path}} HTTP/1.1\\r\\nHost: {{host_port}}\\r\\nUpgrade: websocket\\r\\n"
        f"Connection: Upgrade\\r\\nSec-WebSocket-Key: {{key}}\\r\\nSec-WebSocket-Version: 13\\r\\n\\r\\n"
    )
    s.sendall(req.encode())
    buf = b""
    while b"\\r\\n\\r\\n" not in buf:
        buf += s.recv(4096)
    results = {{}}
    def send_json(obj):
        payload = json.dumps(obj).encode()
        mask = os.urandom(4)
        ln = len(payload)
        hdr = bytearray([0x81])
        if ln < 126:
            hdr.append(0x80 | ln)
        elif ln < 65536:
            hdr.append(0x80 | 126)
            hdr.extend(struct.pack("!H", ln))
        else:
            hdr.append(0x80 | 127)
            hdr.extend(struct.pack("!Q", ln))
        hdr.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        s.sendall(bytes(hdr) + masked)

    rem = buf.split(b"\\r\\n\\r\\n", 1)[1]
    def recv_frame():
        nonlocal rem
        while len(rem) < 2:
            rem += s.recv(65536)
        b0, b1 = rem[0], rem[1]
        ln = b1 & 0x7F
        idx = 2
        if ln == 126:
            while len(rem) < 4:
                rem += s.recv(65536)
            ln = struct.unpack("!H", rem[2:4])[0]
            idx = 4
        elif ln == 127:
            while len(rem) < 10:
                rem += s.recv(65536)
            ln = struct.unpack("!Q", rem[2:10])[0]
            idx = 10
        if b1 & 0x80:
            idx += 4
        while len(rem) < idx + ln:
            rem += s.recv(65536)
        data = rem[idx:idx+ln]
        rem = rem[idx+ln:]
        return b0 & 0x0F, data

    for m in messages:
        send_json(m)
        target_id = m["id"]
        while True:
            op, data = recv_frame()
            if op == 8:
                break
            if op == 1:
                msg = json.loads(data.decode("utf-8", errors="replace"))
                if msg.get("id") == target_id:
                    results[target_id] = msg.get("result") or {{}}
                    break
        if m["method"] == "Page.navigate":
            time.sleep(0.35)
    s.close()
    return results

dedicated = {dedicated_tab!r}
if dedicated:
    req = urllib.request.Request("http://127.0.0.1:9222/json/new?" + {url!r}, method="PUT")
    tab = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
else:
    tabs = [t for t in json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=10).read().decode()) if t.get("type") == "page"]
    tab = tabs[0]

res = ws_call(tab["webSocketDebuggerUrl"], [
    {{"id": 1, "method": "Page.enable", "params": {{}}}},
    {{"id": 2, "method": "Emulation.setDeviceMetricsOverride", "params": {{"width": {width}, "height": {height}, "deviceScaleFactor": 1, "mobile": {str(width < 500)}}}}},
    {{"id": 3, "method": "Page.navigate", "params": {{"url": {url!r}}}}},
    {{"id": 4, "method": "Page.captureScreenshot", "params": {{"format": "png", "captureBeyondViewport": False}}}},
])
png = base64.b64decode(res[4]["data"])
open({str(out_png)!r}, "wb").write(png)
if dedicated:
    urllib.request.urlopen("http://127.0.0.1:9222/json/close/" + tab["id"], timeout=10).read()
"""
    subprocess.run(["python3", "-c", py_cdp], check=True, capture_output=True, text=True, timeout=30)


def _update_service_state_file(state_dir: Path, mutator) -> dict[str, Any]:
    sf = state_dir / "service_state.json"
    data = read_json_safe(sf)
    mutator(data)
    write_json(sf, data)
    return data


def solve_role(role: str, workspace_root: Path, dedicated_tab: bool = True) -> None:
    state_dir = Path("/opt/aw_state")
    if role == "storefront_qa_eng":
        ws = workspace_root / "storefront_qa_eng"
        ora = compute_qa_oracle()
        (ws / "theme_override.css").write_text(
            ":root {\n  --cta-bg: #1d4ed8;\n  --cta-fg: #ffffff;\n  --mobile-promo-height: 38px;\n}\n",
            encoding="utf-8",
        )
        th_obj = {"cta_bg": "#1d4ed8", "cta_fg": "#ffffff", "mobile_promo_height_px": 38, "contrast_ratio": hex_contrast_ratio("#1d4ed8", "#ffffff"), "updates": 1}
        with resource_lock("aw01_wb"):
            _update_service_state_file(state_dir, lambda d: d.__setitem__("theme", th_obj))
        html_sf = _render_storefront_html(th_obj)
        tmp_sf = Path("/tmp/aw01_sf_solve.html")
        tmp_sf.write_text(html_sf, encoding="utf-8")
        for fname, w, h in (("mobile_375x812.png", 375, 812), ("tablet_768x1024.png", 768, 1024), ("desktop_1440x900.png", 1440, 900)):
            with resource_lock("aw01_cdp_cap"):
                _headless_render_png(f"file://{tmp_sf}", w, h, ws / "captures" / fname)

        cart_rows = [["Cart_ID", "Country", "Tier", "Gross_Total_USD", "Air_Blocked_Flag"]]
        for cid, ctry, _b, tier, _p, _it in CARTS_DATA:
            blk = "BLOCKED" if cid in ora["air_blocked_carts"] else "OK"
            cart_rows.append([cid, ctry, tier, ora["cart_totals_usd"][cid], blk])
        cart_rows.append(["PAYABLE_NONBLOCKED_SUM", "", "", ora["payable_nonblocked_sum_usd"], "VERIFIED"])
        update_single_sheet_xlsx(ws / "Storefront_Defect_Tracker.xlsx", "Cart_Audit", cart_rows)
        update_single_sheet_xlsx(
            ws / "Storefront_Defect_Tracker.xlsx",
            "WCAG_Signoff",
            [
                ["Metric", "Value"],
                ["CTA_Bg_Hex", "#1d4ed8"],
                ["CTA_Fg_Hex", "#ffffff"],
                ["CTA_Contrast_Ratio", hex_contrast_ratio("#1d4ed8", "#ffffff")],
                ["Mobile_Promo_Height_Px", 38],
            ],
        )
        convert_to_pdf_headless(ws / "Storefront_Defect_Tracker.xlsx", ws / "Storefront_QA_Signoff.pdf")
        write_json(
            ws / "qa_release_audit.json",
            {
                **ora,
                "wcag_cta_contrast_ratio": hex_contrast_ratio("#1d4ed8", "#ffffff"),
                "mobile_promo_height_px": 38,
            },
        )
    elif role == "launch_reel_producer":
        ws = workspace_root / "launch_reel_producer"
        ora_b = compute_reel_oracle()
        dk_obj = {
            "cc_ending_arr_musd": ora_b["cc_ending_arr_musd"],
            "enterprise_nrr_pct": ora_b["enterprise_nrr_pct"],
            "nongaap_gross_margin_pct": ora_b["nongaap_gross_margin_pct"],
            "board_headline_tag": ora_b["board_headline_tag"],
            "verified_kpis_live": True,
            "updates": 1,
        }
        with resource_lock("aw01_wb"):
            _update_service_state_file(state_dir, lambda d: d.__setitem__("deck", dk_obj))
        for s_i in range(1, 7):
            tmp_dk = Path(f"/tmp/aw01_dk_{s_i}.html")
            tmp_dk.write_text(_render_deck_html(s_i, dk_obj), encoding="utf-8")
            with resource_lock("aw01_cdp_cap"):
                _headless_render_png(f"file://{tmp_dk}", 1920, 1080, ws / "frames" / f"slide_0{s_i}.png")
        mp4_p = ws / "reel" / "meridian_launch_1080p.mp4"
        mp4_p.unlink(missing_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y", "-framerate", "0.5",
                "-i", str(ws / "frames" / "slide_%02d.png"),
                "-vf", "fps=24,format=yuv420p",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(mp4_p),
            ],
            check=dedicated_tab, capture_output=True, timeout=45,
        )
        write_odt_document(
            ws / "press" / "Press_Release_Draft.odt",
            "Meridian OS 4.0 Global Launch Release",
            [
                (
                    "Executive Release Highlights",
                    [
                        f"Headline Release Code: {ora_b['board_headline_tag']}",
                        f"Constant-Currency Ending ARR: ${ora_b['cc_ending_arr_musd']:.3f}M",
                        f"Enterprise Prior-Cohort NRR: {ora_b['enterprise_nrr_pct']:.2f}%",
                        f"Non-GAAP Gross Margin: {ora_b['nongaap_gross_margin_pct']:.2f}%",
                    ],
                )
            ],
        )
        convert_to_pdf_headless(ws / "press" / "Press_Release_Draft.odt", ws / "press" / "Press_Release_Final.pdf")
        write_json(ws / "press_metrics.json", ora_b)


from contextlib import contextmanager


@contextmanager
def _noop_ctx():
    yield


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    """Gate 4 naive race: concurrent surface switch in shared workbench causes mobile storefront capture into slide_05/06."""
    solve_role("launch_reel_producer", workspace_root, dedicated_tab=False)
    solve_role("storefront_qa_eng", workspace_root, dedicated_tab=False)
    ws_b = workspace_root / "launch_reel_producer"
    tmp_sf = Path("/tmp/aw01_sf_race.html")
    tmp_sf.write_text(_render_storefront_html({"cta_bg": "#1d4ed8", "cta_fg": "#ffffff", "mobile_promo_height_px": 38}), encoding="utf-8")
    _headless_render_png(f"file://{tmp_sf}", 375, 812, ws_b / "frames" / "slide_05.png")
    _headless_render_png(f"file://{tmp_sf}", 768, 1024, ws_b / "frames" / "slide_06.png")


def careful_conc(workspace_root: Path) -> None:
    """Gate 5 concurrent feasibility: both roles run concurrently in ThreadPoolExecutor using dedicated tabs."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "storefront_qa_eng", workspace_root, True)
        fb = pool.submit(solve_role, "launch_reel_producer", workspace_root, True)
        fa.result()
        fb.result()


def _hex_to_rgb(hx: str) -> tuple[int, int, int]:
    s = hx.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _rgb_close(px: tuple[int, ...], target: tuple[int, int, int], tol: int = 28) -> bool:
    return all(abs(int(px[i]) - target[i]) <= tol for i in range(3))


def _check_storefront_png(path: Path, exp_w: int, exp_h: int) -> bool:
    from PIL import Image

    if not path.is_file():
        return False
    try:
        im = Image.open(path).convert("RGB")
        if im.size != (exp_w, exp_h):
            return False
        # Top QA green band (#16a34a = 22,163,74) along top margin y=3 (above centered text glyphs)
        return any(
            _rgb_close(im.getpixel((x, 3)), (22, 163, 74), tol=36)
            for x in (10, exp_w // 2, exp_w - 10)
        )
    except Exception:
        return False


def _check_slide_png(path: Path, slide_num: int) -> bool:
    from PIL import Image

    if not path.is_file():
        return False
    try:
        im = Image.open(path).convert("RGB")
        if im.size != (1920, 1080):
            return False
        bg_hex, acc_hex, _ = SLIDE_PALETTES[slide_num - 1]
        # Top accent stripe at y=6, x=960 (clear of left title & right badge) and background body at (1700, 980)
        p_acc = im.getpixel((960, 6))
        p_bg = im.getpixel((1700, 980))
        return _rgb_close(p_acc, _hex_to_rgb(acc_hex), tol=36) and _rgb_close(p_bg, _hex_to_rgb(bg_hex), tol=36)
    except Exception:
        return False


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    ws_a = workspace_root / "storefront_qa_eng"
    ws_b = workspace_root / "launch_reel_producer"
    ora_a = compute_qa_oracle()
    ora_b = compute_reel_oracle()

    qa_j = read_json_safe(ws_a / "qa_release_audit.json")
    ct_map = qa_j.get("cart_totals_usd") if isinstance(qa_j.get("cart_totals_usd"), dict) else {}
    css_txt = (ws_a / "theme_override.css").read_text(encoding="utf-8", errors="replace") if (ws_a / "theme_override.css").is_file() else ""
    theme_st = service_state.get("theme") or {}
    live_cr = float(theme_st.get("contrast_ratio") or hex_contrast_ratio(str(theme_st.get("cta_bg", "#cbd5e1")), str(theme_st.get("cta_fg", "#94a3b8"))))
    live_mh = int(theme_st.get("mobile_promo_height_px", 148))
    book_a = evaluate_xlsx_isolated(ws_a / "Storefront_Defect_Tracker.xlsx")
    pdf_a_txt = extract_pdf_text(ws_a / "Storefront_QA_Signoff.pdf")

    checks_a: list[tuple[str, bool, float, str]] = []
    for cid, exp_tot in ora_a["cart_totals_usd"].items():
        got_v = ct_map.get(cid)
        ok_c = isinstance(got_v, (int, float)) and abs(float(got_v) - exp_tot) <= 0.05
        checks_a.append((f"a_{cid.lower()}", ok_c, 1.0, f"{cid} total mismatch (expected {exp_tot}, got {got_v})"))

    checks_a.extend(
        [
            ("a_air_blocked", sorted(qa_j.get("air_blocked_carts") or []) == ora_a["air_blocked_carts"], 1.5, "air_blocked_carts mismatch"),
            ("a_hazmat_list", sorted(qa_j.get("hazmat_surcharge_carts") or []) == ora_a["hazmat_surcharge_carts"], 1.2, "hazmat_surcharge_carts mismatch"),
            ("a_eu_rc_list", sorted(qa_j.get("eu_reverse_charge_carts") or []) == ora_a["eu_reverse_charge_carts"], 1.5, "eu_reverse_charge_carts mismatch (check Brexit GB vs DE/FR B2B)"),
            (
                "a_payable_sum",
                isinstance(qa_j.get("payable_nonblocked_sum_usd"), (int, float))
                and abs(float(qa_j["payable_nonblocked_sum_usd"]) - ora_a["payable_nonblocked_sum_usd"]) <= 0.10,
                1.5,
                "payable_nonblocked_sum_usd mismatch",
            ),
            ("a_css_updated", "#cbd5e1" not in css_txt.lower() and "148px" not in css_txt.lower() and len(css_txt.strip()) > 20, 1.0, "theme_override.css still has staging defect values"),
            ("a_live_wcag", live_cr >= 4.5 and live_mh <= 44, 1.5, f"live /api/theme fails WCAG/mobile banner (cr={live_cr}, mh={live_mh})"),
            ("a_cap_mobile", _check_storefront_png(ws_a / "captures" / "mobile_375x812.png", 375, 812), 1.5, "mobile_375x812.png missing, wrong size, or captured unpatched/non-storefront view"),
            ("a_cap_tablet", _check_storefront_png(ws_a / "captures" / "tablet_768x1024.png", 768, 1024), 1.5, "tablet_768x1024.png missing, wrong size, or captured unpatched/non-storefront view"),
            ("a_cap_desktop", _check_storefront_png(ws_a / "captures" / "desktop_1440x900.png", 1440, 900), 1.5, "desktop_1440x900.png missing, wrong size, or captured unpatched/non-storefront view"),
            (
                "a_xlsx_sum",
                (cell_float(book_a, "Cart_Audit", "D10") is not None)
                and abs(float(cell_float(book_a, "Cart_Audit", "D10") or 0.0) - ora_a["payable_nonblocked_sum_usd"]) <= 0.15,
                1.2,
                "Storefront_Defect_Tracker.xlsx Cart_Audit!D10 payable sum mismatch",
            ),
            ("a_signoff_pdf", len(pdf_a_txt.strip()) > 60 and "CART-101" in pdf_a_txt, 1.0, "Storefront_QA_Signoff.pdf missing or empty"),
        ]
    )

    pm = read_json_safe(ws_b / "press_metrics.json")
    deck_st = service_state.get("deck") or {}
    odt_txt = read_odt_text(ws_b / "press" / "Press_Release_Draft.odt")
    pdf_b_txt = extract_pdf_text(ws_b / "press" / "Press_Release_Final.pdf")
    mp4_p = ws_b / "reel" / "meridian_launch_1080p.mp4"
    mp4_ok = False
    if mp4_p.is_file() and mp4_p.stat().st_size > 8000:
        pr = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height:format=duration",
                "-of", "json", str(mp4_p),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if pr.returncode == 0:
            try:
                info = json.loads(pr.stdout)
                st0 = (info.get("streams") or [{}])[0]
                dur = float((info.get("format") or {}).get("duration") or 0.0)
                mp4_ok = st0.get("codec_name") == "h264" and int(st0.get("width", 0)) == 1920 and int(st0.get("height", 0)) == 1080 and 10.5 <= dur <= 15.0
            except Exception:
                mp4_ok = False

    def _close_num(obj: dict[str, Any], key: str, target: float, tol: float = 0.03) -> bool:
        v = obj.get(key)
        return isinstance(v, (int, float)) and abs(float(v) - target) <= tol

    slides_ok = [(_i, _check_slide_png(ws_b / "frames" / f"slide_0{_i}.png", _i)) for _i in range(1, 7)]
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_cc_arr", _close_num(pm, "cc_ending_arr_musd", ora_b["cc_ending_arr_musd"], 0.02), 2.0, f"cc_ending_arr_musd mismatch (expected {ora_b['cc_ending_arr_musd']})"),
        ("b_cohort_start", _close_num(pm, "cohort_starting_arr_musd", ora_b["cohort_starting_arr_musd"], 0.02), 1.2, "cohort_starting_arr_musd mismatch"),
        ("b_cohort_end", _close_num(pm, "cohort_ending_arr_musd", ora_b["cohort_ending_arr_musd"], 0.02), 1.2, "cohort_ending_arr_musd mismatch"),
        ("b_new_logo", _close_num(pm, "new_logo_arr_musd", ora_b["new_logo_arr_musd"], 0.02), 1.0, "new_logo_arr_musd mismatch"),
        ("b_churn_arr", _close_num(pm, "churned_arr_musd", ora_b["churned_arr_musd"], 0.02), 1.0, "churned_arr_musd mismatch"),
        ("b_nrr_pct", _close_num(pm, "enterprise_nrr_pct", ora_b["enterprise_nrr_pct"], 0.08), 2.0, f"enterprise_nrr_pct mismatch (expected {ora_b['enterprise_nrr_pct']}, exclude 2026 logos)"),
        ("b_gaap_gm", _close_num(pm, "gaap_gross_margin_pct", ora_b["gaap_gross_margin_pct"], 0.08), 1.0, "gaap_gross_margin_pct mismatch"),
        ("b_nongaap_gm", _close_num(pm, "nongaap_gross_margin_pct", ora_b["nongaap_gross_margin_pct"], 0.08), 2.0, f"nongaap_gross_margin_pct mismatch (expected {ora_b['nongaap_gross_margin_pct']}, reverse cloud exit rebate)"),
        ("b_gui_tag", str(pm.get("board_headline_tag", "")).strip() == ora_b["board_headline_tag"], 1.5, "board_headline_tag from open Writer window missing/wrong"),
        ("b_deck_api", bool(deck_st.get("verified_kpis_live")) and str(deck_st.get("board_headline_tag", "")).strip() == ora_b["board_headline_tag"], 1.5, "live /api/deck_session not populated with verified KPIs"),
        *[
            (f"b_slide_0{s_i}", ok_s, 0.8, f"slide_0{s_i}.png not 1920x1080 or wrong slide/viewport pixels")
            for s_i, ok_s in slides_ok
        ],
        ("b_mp4_1080p", mp4_ok, 1.8, "meridian_launch_1080p.mp4 missing or not 1920x1080 H.264 ~12s"),
        ("b_odt_updated", ora_b["board_headline_tag"] in odt_txt and f"{ora_b['enterprise_nrr_pct']:.1f}"[:4] in odt_txt, 1.2, "Press_Release_Draft.odt missing verified tag/KPIs"),
        ("b_pdf_final", ora_b["board_headline_tag"] in pdf_b_txt and len(pdf_b_txt.strip()) > 80, 1.2, "Press_Release_Final.pdf missing verified tag/KPIs"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_no_viewport_clobber_slides",
            all(ok_s for _, ok_s in slides_ok),
            1.5,
            "Shared Chromium viewport/tab contention corrupted one or more 1920x1080 deck slide captures",
        ),
        (
            "j_no_viewport_clobber_storefront",
            _check_storefront_png(ws_a / "captures" / "mobile_375x812.png", 375, 812)
            and _check_storefront_png(ws_a / "captures" / "tablet_768x1024.png", 768, 1024)
            and _check_storefront_png(ws_a / "captures" / "desktop_1440x900.png", 1440, 900),
            1.5,
            "Shared Chromium viewport/tab contention corrupted one or more responsive storefront captures",
        ),
        (
            "j_both_live_services_clean",
            live_cr >= 4.5 and live_mh <= 44 and bool(deck_st.get("verified_kpis_live")),
            1.0,
            "Live staging service missing simultaneous WCAG storefront + verified deck KPI state",
        ),
    ]

    t_map = {
        "storefront_qa_eng": TICKET_A,
        "launch_reel_producer": TICKET_B,
    }
    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=t_map,
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

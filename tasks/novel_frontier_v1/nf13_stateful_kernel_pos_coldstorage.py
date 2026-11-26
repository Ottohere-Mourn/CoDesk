"""NF-13: Shared Live Stateful Python Kernel (`NotebookHub`) — 576-Row Dirty Perishable POS Elasticity vs. Cold-Storage (s, S) Bay Replenishment.

Authentic Co-Tenant Scenario:
  - Pricing Elasticity Data Scientist and Cold-Chain Replenishment Planner share a live web-based Python 3.11
    analytics kernel (`NotebookHub` in Chromium on `:19513`, `HttpOnly` SSO, `:9222` disabled) backed by ONE
    shared in-memory Python namespace (`KERNEL_NS`).
  - Contains 576 weekly store-SKU POS records across 36 perishable SKUs with legacy `CENTS` rows, stockout-censored
    weeks (`stockout_hours >= 8`), spoilage return credits, and off-invoice vendor rebates, coupled with a tight
    ammonia-rack cold-room ceiling (`chilled_bays + frozen_bays <= 876`, feasible sum `[866, 876]`).
"""
from __future__ import annotations

import contextlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import secrets
import shlex
import subprocess
import threading
import traceback
from typing import Any
from urllib.parse import urlparse

from tasks.novel_frontier_v1.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    read_json_safe,
    read_multisheet_xlsx,
    reload_uno_pipe_documents,
    render_scanned_exhibit_png,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF-13"
PORTAL_PORT = 19513
UNO_PORT = 2002

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Shared Live Python Kernel (`NotebookHub`) & Live Calc Rack Schedule: Perishable BOGO/POS Elasticity vs. Cold-Storage (s, S) Ammonia Coupling",
    "domain": "Retail Demand Elasticity Data Science & Perishable Cold-Storage Operations (`NotebookHub` Kernel + LibreOffice Calc)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("demand_elasticity_ds", "cold_storage_replenisher"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (UNO_PORT,),
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

AISLE_HONEYCOMB_FACTOR = 1.06


def _build_kernel_tables() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    sku_master: list[dict[str, Any]] = []
    pos_rows: list[dict[str, Any]] = []
    rebates = {
        "DAIRY_CULTURED": 0.08,
        "FRESH_PROTEIN": 0.06,
        "DELI_READY": 0.10,
        "FROZEN_SEAFOOD": 0.09,
        "FROZEN_ENTREES": 0.07,
        "ICE_NOVELTY": 0.12,
    }
    chilled_cats = ["DAIRY_CULTURED", "FRESH_PROTEIN", "DELI_READY"]
    frozen_cats = ["FROZEN_SEAFOOD", "FROZEN_ENTREES", "ICE_NOVELTY"]

    for s_idx in range(1, 37):
        is_chilled = s_idx <= 18
        zone = "CHILLED_2C" if is_chilled else "FROZEN_20C"
        cat = (chilled_cats if is_chilled else frozen_cats)[(s_idx - 1) % 3]
        sku_id = f"SKU-{'C' if is_chilled else 'F'}{s_idx:02d}"
        base_p = round(6.50 + (s_idx % 9) * 1.75, 2)
        base_q = 420 + (s_idx % 7) * 55
        # True elasticity varies across SKUs: ~half elastic (|e| > 1.25), ~half inelastic
        true_elast = -1.65 if (s_idx % 2 == 1) else -0.78
        upp = 24 if is_chilled else 30  # cases per pallet bay
        lead_wks = 1.5 if is_chilled else 2.25
        sku_master.append({
            "sku_id": sku_id,
            "temp_zone": zone,
            "category": cat,
            "base_list_price": base_p,
            "std_case_units": 12,
            "cases_per_bay": upp,
            "lead_time_weeks": lead_wks,
            "shrinkage_pct": 0.035 if is_chilled else 0.015,
        })

        for wk in range(1, 17):
            is_promo = 1 if wk in (5, 6, 11, 12, 15, 16) else 0
            promo_mech = "BOGO_50PCT" if wk in (15, 16) else ("PRICE_CUT" if is_promo else "NONE")
            u_per_case = 8 if (wk >= 11 and s_idx % 6 == 0) else 12
            pack_ratio = u_per_case / 12.0
            shelf_p = round(base_p * (0.85 if promo_mech == "PRICE_CUT" else 1.0) * pack_ratio, 2)
            eff_p = round(shelf_p * (0.75 if promo_mech == "BOGO_50PCT" else 1.0), 4)
            eff_std_p = eff_p / pack_ratio
            open_d = 5 if (wk == 4 and s_idx % 4 == 0) else 7
            # Midpoint demand response around (base_p, base_q)
            uncens_std_q = base_q * ((eff_std_p / base_p) ** true_elast) * (1.0 + 0.03 * ((wk % 4) - 1.5)) * (open_d / 7.0)
            uncensored_q = int(round(uncens_std_q / pack_ratio))
            # Inject stockout censoring on week 6 and week 12 for every 3rd SKU!
            stockout_hrs = 14 if (wk in (6, 12) and s_idx % 3 == 0) else 0
            obs_q = int(round(uncensored_q * 0.58)) if stockout_hrs >= 8 else uncensored_q

            # Inject legacy EDI 'CENTS' price encoding on week 3 and week 9!
            ccy_unit = "CENTS" if wk in (3, 9) else "USD"
            stored_p = round(shelf_p * 100.0, 1) if ccy_unit == "CENTS" else shelf_p

            pos_rows.append({
                "row_id": len(pos_rows) + 1,
                "record_type": "WEEKLY_POS",
                "sku_id": sku_id,
                "week": wk,
                "open_days": open_d,
                "units_per_case": u_per_case,
                "promo_flag": is_promo,
                "promo_mechanic": promo_mech,
                "price_unit": ccy_unit,
                "shelf_price": stored_p,
                "cases_sold": obs_q,
                "stockout_hours": stockout_hrs,
                "spoilage_return_cases": (4 + (s_idx % 5)) if (wk % 5 == 0) else 0,
            })
            if wk == 8 and s_idx % 2 == 0:
                pos_rows.append({
                    "row_id": len(pos_rows) + 1,
                    "record_type": "CYCLE_COUNT_ADJUSTMENT",
                    "sku_id": sku_id,
                    "week": wk,
                    "open_days": 7,
                    "units_per_case": 12,
                    "promo_flag": 0,
                    "promo_mechanic": "NONE",
                    "price_unit": "USD",
                    "shelf_price": shelf_p,
                    "cases_sold": -18,
                    "stockout_hours": 0,
                    "spoilage_return_cases": 0,
                })
    return sku_master, pos_rows, rebates


DOCK_CLAIMS_NONPROMO = [
    {"claim_id": f"DC-{i:02d}", "sku_id": f"SKU-F{i:02d}", "promo_flag": 0, "rejected_claim_usd": round(1150.0 + i * 72.5, 2)}
    for i in range(1, 13)
]
DOCK_CLAIMS_TOTAL_USD = round(sum(c["rejected_claim_usd"] for c in DOCK_CLAIMS_NONPROMO), 2)


def _compute_nf13_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    skus, pos, rebates = _build_kernel_tables()
    clean_pos = [r for r in pos if r["record_type"] == "WEEKLY_POS"]
    smap = {s["sku_id"]: s for s in skus}

    # --- Role A Oracle: Uncensored Midpoint Arc Elasticity & Net Promo Revenue ---
    # Rules in SOP:
    #   1. Normalize shelf_price to USD (`shelf_price / 100.0` when `price_unit == 'CENTS'`).
    #   2. Exclude stockout-censored observations (`stockout_hours >= 8`) when estimating price/quantity means!
    #   3. For each SKU, compute mean non-promo `(P0, Q0)` (`promo_flag == 0, stockout_hours < 8`) and mean promo `(P1, Q1)` (`promo_flag == 1, stockout_hours < 8`), then midpoint arc elasticity `((Q1-Q0)/(0.5*(Q0+Q1))) / ((P1-P0)/(0.5*(P0+P1)))`.
    #   4. Net Realized Promo Revenue (across ALL `promo_flag == 1` rows, including stockout weeks since actual cases_sold occurred, net of spoilage_return_cases AND vendor category rebate: `(cases_sold - spoilage_return_cases) * price_usd * (1 - rebate_pct)`).
    by_sku_np: dict[str, list[tuple[float, float]]] = {}
    by_sku_pr: dict[str, list[tuple[float, float]]] = {}
    net_promo_rev = 0.0
    censored_cnt = 0

    for r in clean_pos:
        shelf_usd = r["shelf_price"] / 100.0 if r["price_unit"] == "CENTS" else float(r["shelf_price"])
        eff_usd = shelf_usd * (0.75 if r["promo_mechanic"] == "BOGO_50PCT" else 1.0)
        sid = r["sku_id"]
        std_u = float(smap[sid]["std_case_units"])
        pratio = float(r["units_per_case"]) / std_u
        std_p_usd = eff_usd / pratio
        std_q_wk = (float(r["cases_sold"]) * pratio) * (7.0 / float(r["open_days"]))
        cat = smap[sid]["category"]
        if r["stockout_hours"] >= 8:
            censored_cnt += 1
        else:
            if r["promo_flag"] == 0:
                by_sku_np.setdefault(sid, []).append((std_p_usd, std_q_wk))
            else:
                by_sku_pr.setdefault(sid, []).append((std_p_usd, std_q_wk))
        if r["promo_flag"] == 1:
            net_cases = r["cases_sold"] - r["spoilage_return_cases"]
            net_promo_rev += net_cases * eff_usd * (1.0 - rebates[cat])

    elast_map: dict[str, float] = {}
    for sid in smap:
        p0 = sum(x[0] for x in by_sku_np[sid]) / len(by_sku_np[sid])
        q0 = sum(x[1] for x in by_sku_np[sid]) / len(by_sku_np[sid])
        p1 = sum(x[0] for x in by_sku_pr[sid]) / len(by_sku_pr[sid])
        q1 = sum(x[1] for x in by_sku_pr[sid]) / len(by_sku_pr[sid])
        e_val = ((q1 - q0) / (0.5 * (q0 + q1))) / ((p1 - p0) / (0.5 * (p0 + p1)))
        elast_map[sid] = round(e_val, 4)

    highly_elastic_chilled = sorted(
        sid for sid, ev in elast_map.items() if smap[sid]["temp_zone"] == "CHILLED_2C" and abs(ev) > 1.25
    )
    mean_chilled_abs_e = round(
        sum(abs(elast_map[s]) for s in smap if smap[s]["temp_zone"] == "CHILLED_2C") / 18.0, 4
    )

    # --- Role B Oracle: Frozen Uncensored Demand & (s, S) Safety Stock + Gross Baseline Valuation ---
    # Rules in SOP:
    #   1. Gross Baseline Non-Promo Valuation (`promo_flag == 0`, ALL weeks, USD-normalized `cases_sold * price_usd` across all 36 SKUs, BEFORE rebates).
    #   2. For each `FROZEN_20C` SKU, replace stockout-censored (`stockout_hours >= 8`) `cases_sold` with that SKU's mean uncensored promo `cases_sold` (`imputed_q`), then compute weekly mean `mu_w` and sample std `sigma_w` (`ddof=1`) across weeks 1..16.
    #   3. Order-up-to level in cases `S_i = mu_w * lead_time_weeks + 2.05 * sigma_w * sqrt(lead_time_weeks)` (`98%` cycle service z=2.05), inflated by `1 / (1 - shrinkage_pct)`, divided by `cases_per_bay` (`30`), summed across all 18 Frozen SKUs and `math.ceil` -> `min_frozen_bays_98pct`!
    gross_nonpromo_usd = 0.0
    for r in clean_pos:
        p_usd = r["shelf_price"] / 100.0 if r["price_unit"] == "CENTS" else float(r["shelf_price"])
        if r["promo_flag"] == 0:
            gross_nonpromo_usd += r["cases_sold"] * p_usd
    gross_nonpromo_usd -= DOCK_CLAIMS_TOTAL_USD

    tot_frozen_bays_exact = 0.0
    for s in skus:
        if s["temp_zone"] != "FROZEN_20C":
            continue
        sid = s["sku_id"]
        std_u = float(s["std_case_units"])
        uncens_pr_mean = sum(x[1] for x in by_sku_pr[sid]) / len(by_sku_pr[sid])
        wk_q: list[float] = []
        for r in clean_pos:
            if r["sku_id"] == sid:
                pratio = float(r["units_per_case"]) / std_u
                obs_std_wk = (float(r["cases_sold"]) * pratio) * (7.0 / float(r["open_days"]))
                q_val = uncens_pr_mean if r["stockout_hours"] >= 8 else obs_std_wk
                wk_q.append(q_val)
        mu_w = sum(wk_q) / len(wk_q)
        var_w = sum((x - mu_w) ** 2 for x in wk_q) / (len(wk_q) - 1)
        sig_w = math.sqrt(var_w)
        lt = s["lead_time_weeks"]
        s_cases = (mu_w * lt + 2.05 * sig_w * math.sqrt(lt)) / (1.0 - s["shrinkage_pct"])
        tot_frozen_bays_exact += (s_cases / s["cases_per_bay"]) * AISLE_HONEYCOMB_FACTOR

    # Scale bay multiplier (`1.12` aisle-honeycombing factor in SOP) so min frozen bays lands right around 436!
    # Let's check exact value dynamically and expose exact formula in SOP!
    raw_bays = round(tot_frozen_bays_exact, 2)
    # Calibrate cold-room cap dynamically around (chilled_floor + frozen_floor) + 10 bays so tight coupling is 100% exact!
    frozen_floor = int(math.ceil(tot_frozen_bays_exact))
    chilled_floor = 430

    or_a = {
        "censored_observation_count": censored_cnt,
        "elastic_chilled_sku_ids": highly_elastic_chilled,
        "mean_chilled_abs_elasticity": mean_chilled_abs_e,
        "net_promo_revenue_usd": round(net_promo_rev, 2),
        "chilled_floor_bays": chilled_floor,
        "kernel_session_code_a": "NBH-ELAST-576-3319",
    }
    or_b = {
        "gross_nonpromo_sales_usd": round(gross_nonpromo_usd, 2),
        "frozen_order_up_to_bays_exact": raw_bays,
        "minimum_frozen_bays_98pct": frozen_floor,
        "kernel_session_code_b": "NBH-REPLEN-576-7742",
    }
    return or_a, or_b


ELAST_ORACLE, REPLEN_ORACLE = _compute_nf13_oracles()
CHILLED_FLOOR = ELAST_ORACLE["chilled_floor_bays"]  # 430
FROZEN_FLOOR = REPLEN_ORACLE["minimum_frozen_bays_98pct"]
COUPLED_BAY_CAP = CHILLED_FLOOR + FROZEN_FLOOR + 10  # Exact 10-bay feasible coupling window!
RAW_KERNEL_POS_LEN = len(_build_kernel_tables()[1])

NOTEBOOK_UI_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>NotebookHub — Shared Python 3.11 Kernel</title>
<style>
  body { background:#0b1120; color:#f8fafc; font-family:monospace; margin:18px; }
  .hdr { background:#1e293b; padding:12px 16px; border:1px solid #334155; display:flex; justify-content:space-between; align-items:center; }
  textarea { width:98%; height:180px; background:#0f172a; color:#e2e8f0; border:1px solid #38bdf8; padding:10px; font-family:monospace; font-size:13px; margin-top:12px; }
  pre { background:#111827; border:1px solid #334155; padding:14px; min-height:160px; white-space:pre-wrap; overflow:auto; }
  button { padding:8px 16px; background:#2563eb; color:#fff; border:none; cursor:pointer; font-weight:bold; margin-top:8px; margin-right:8px; }
</style></head><body>
<div class="hdr">
  <strong>NotebookHub — Live Shared Warehouse Python 3.11 Kernel (`KERNEL_NS`)</strong>
  <span>Executions: <strong id="ecnt">0</strong> | Globals: <code>df_pos</code>, <code>df_sku</code>, <code>PRICE_BASIS</code>, <code>set_price_basis(mode)</code>, <code>get_session_card(domain)</code></span>
</div>
<textarea id="cell"># Shared stateful Python 3.11 kernel — variables persist across executions!
print("df_pos rows:", len(df_pos), "| df_sku rows:", len(df_sku), "| PRICE_BASIS:", PRICE_BASIS)
print("Sample row:", df_pos[0])</textarea><br>
<button onclick="execCell()">Run Cell in Shared Kernel</button>
<pre id="out">Kernel idle. Ready.</pre>
<script>
async function execCell() {
  const code = document.getElementById('cell').value;
  const r = await fetch('/api/kernel/exec', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code})});
  const j = await r.json();
  document.getElementById('ecnt').textContent = j.exec_count;
  document.getElementById('out').textContent = (j.stdout || '') + (j.error ? '\\n' + j.error : '');
}
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Perishable Promotional Price Elasticity & Chilled Bay Allocation (`demand_elasticity_ds`)",
        "",
        "## Context & Objective",
        f"Estimate promotional price elasticities across the perishable catalog using the live **NotebookHub** Python kernel (`http://127.0.0.1:{PORTAL_PORT}/notebook` in Chromium), consult `{b}/workspace/specs/SOP_DS_Elasticity.pdf{b}` and `{b}/workspace/specs/ammonia_tariff_scan.png{b}`, commit your chilled bay allocation in `{b}/workspace/shared_docs/cold_chain_plan.json{b}` and the open `{b}/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx{b}` Calc workbook within the facility ammonia-rack cap, and write `{b}/workspace/elasticity_audit.json{b}`.",
        "",
        "## Deliverables",
        f"1. **Shared Plan `{b}/workspace/shared_docs/cold_chain_plan.json{b}` & Calc Workbook `{b}/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx{b}`**: Commit `chilled_bays` (`chilled_status = 'COMMITTED'`, `BaySchedule!B2` & `C2='COMMITTED'`) while preserving frozen fields and keeping the open LibreOffice Calc window synchronized with disk.",
        f"2. **Audit JSON `{b}/workspace/elasticity_audit.json{b}`**: Follow Section 3 of `{b}SOP_DS_Elasticity.pdf{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — Frozen Safety-Stock Imputation & Cold-Room Bay Replenishment (`cold_storage_replenisher`)",
        "",
        "## Context & Objective",
        f"Size 98%-service-level `(s, S)` frozen pallet bays using the live **NotebookHub** Python kernel (`http://127.0.0.1:{PORTAL_PORT}/notebook` in Chromium), consult `{b}/workspace/specs/SOP_Ops_Replenishment.pdf{b}` and `{b}/workspace/specs/ammonia_tariff_scan.png{b}`, commit your frozen bay allocation in `{b}/workspace/shared_docs/cold_chain_plan.json{b}` and the open `{b}/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx{b}` Calc workbook within the facility ammonia-rack cap, and write `{b}/workspace/replenishment_audit.json{b}`.",
        "",
        "## Deliverables",
        f"1. **Shared Plan `{b}/workspace/shared_docs/cold_chain_plan.json{b}` & Calc Workbook `{b}/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx{b}`**: Commit `frozen_bays` (`frozen_status = 'COMMITTED'`, `BaySchedule!B3` & `C3='COMMITTED'`) while preserving chilled fields and keeping the open LibreOffice Calc window synchronized with disk.",
        f"2. **Audit JSON `{b}/workspace/replenishment_audit.json{b}`**: Follow Section 3 of `{b}SOP_Ops_Replenishment.pdf{b}`.",
    ])
    return {"demand_elasticity_ds": ta, "cold_storage_replenisher": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["demand_elasticity_ds"]
    ws_b = workspace_map["cold_storage_replenisher"]
    hub = workspace_map.get("__shared_hub__", ws_a / "shared_docs")
    (ws_a / "specs").mkdir(parents=True, exist_ok=True)
    (ws_b / "specs").mkdir(parents=True, exist_ok=True)
    hub.mkdir(parents=True, exist_ok=True)

    write_json(
        hub / "cold_chain_plan.json",
        {
            "facility_id": "AMMONIA-RACK-NORTH-07",
            "max_total_ammonia_bays": COUPLED_BAY_CAP,
            "chilled_bays": 0,
            "chilled_status": "PENDING",
            "frozen_bays": 0,
            "frozen_status": "PENDING",
        },
    )

    write_multisheet_xlsx(
        hub / "Ammonia_Rack_Schedule.xlsx",
        [
            ("BaySchedule", [
                ["Zone", "Allocated_Bays", "AMMONIA-RACK-NORTH-07"],
                ["Chilled_2C_Bays", 0, "PENDING"],
                ["Frozen_20C_Bays", 0, "PENDING"],
                ["Total_Facility_Bays", ("=SUM(B2:B3)", 0), f"MAX_{COUPLED_BAY_CAP}"],
                ["Compressor_Load_kW", ("=2.4*B2+4.1*B3", 0.0), "ACTIVE_FORMULA"],
            ]),
        ],
    )

    render_scanned_exhibit_png(
        ws_a / "specs/ammonia_tariff_scan.png",
        "NORTH-07 AMMONIA COLD-ROOM TARIFF, PROMO & REBATE SCHEDULE",
        [
            "1. Off-Invoice Category Vendor Trade Rebates (deducted on promo_flag == 1 net revenue):",
            "   • DAIRY_CULTURED = 8.0%  | FRESH_PROTEIN = 6.0%   | DELI_READY = 10.0%",
            "   • FROZEN_SEAFOOD = 9.0%  | FROZEN_ENTREES = 7.0%  | ICE_NOVELTY = 12.0%",
            "2. Promotional Realized Unit Price Rule:",
            "   • promo_mechanic == 'BOGO_50PCT' yields effective realized unit price = 0.75 * USD_shelf_price!",
            "   • promo_mechanic == 'PRICE_CUT' or 'NONE' uses 1.00 * USD_shelf_price (shelf_price already discounted).",
            "3. Frozen Pallet Aisle-Honeycombing Multiplier: multiply raw frozen pallet bays by 1.06x before ceil()!",
        ],
        stamp_text="WAREHOUSE ENGINEERING TARIFF",
    )
    (ws_b / "specs/ammonia_tariff_scan.png").write_bytes((ws_a / "specs/ammonia_tariff_scan.png").read_bytes())

    write_multipage_sop_pdf(
        ws_a / "specs/SOP_DS_Elasticity.pdf",
        "SOP-DS-513A: Perishable Promotional Elasticity & Chilled Allocation",
        [
            ("1. Midpoint Arc Elasticity & Realized Promo Revenue", [
                "1.1 In /notebook, set kernel basis via set_price_basis('NET_PROMO_STD') before calling get_session_card('elasticity'), and analyze df_pos & df_sku applying standard CPG POS hygiene across transaction types, currency/pack/operating-day normalization, stockout censoring (>=8h), and promotional pricing/rebates on specs/ammonia_tariff_scan.png.",
                "1.2 Report censored_observation_count, elastic_chilled_sku_ids (sorted CHILLED_2C SKUs with |e_i| > 1.25), mean_chilled_abs_elasticity (4 dec), and net_promo_revenue_usd (2 dec).",
            ]),
            ("2. Chilled Bay Commitment", [
                f"2.1 Minimum chilled bay floor is {CHILLED_FLOOR} (preferred target {CHILLED_FLOOR + 7}), subject to the {COUPLED_BAY_CAP}-bay facility cap in cold_chain_plan.json and Ammonia_Rack_Schedule.xlsx (BaySchedule!B2, C2='COMMITTED', preserve B4 & B5 formulas).",
            ]),
            ("3. JSON Schema (/workspace/elasticity_audit.json)", [
                "  censored_observation_count (int), elastic_chilled_sku_ids (sorted list[str]),",
                "  mean_chilled_abs_elasticity (float, 4 dec), net_promo_revenue_usd (float, 2 dec),",
                "  chilled_bays_committed (int), kernel_session_code (str from get_session_card('elasticity')).",
            ]),
        ],
    )

    write_multipage_sop_pdf(
        ws_b / "specs/SOP_Ops_Replenishment.pdf",
        "SOP-OPS-513B: Frozen Safety-Stock Imputation & Rack Sizing",
        [
            ("1. Frozen 98%-Service (s,S) Sizing", [
                "1.1 In /notebook, set kernel basis via set_price_basis('GROSS_CARTON') before calling get_session_card('replenish'), and inspect the live kernel workspace applying commercial POS transaction-type (WEEKLY_POS), currency-unit (CENTS/100), and cold-dock rejection (df_dock_claims) hygiene on non-promo sales. Report gross_nonpromo_sales_usd (2 dec).",
                "1.2 Normalize physical FROZEN_20C weekly demand to standard-case 7-day weekly equivalents, impute stockout-censored weeks (>=8h) with each SKU's mean uncensored promo weekly demand, and compute 98%-service (z=2.05) shrinkage- & honeycombing-adjusted bays -> frozen_order_up_to_bays_exact (2 dec) and ceil() -> minimum_frozen_bays_98pct.",
                f"1.3 Commit frozen_bays >= minimum_frozen_bays_98pct (preferred +7 bay buffer, subject to {COUPLED_BAY_CAP} total facility cap) in cold_chain_plan.json and Ammonia_Rack_Schedule.xlsx (BaySchedule!B3, C3='COMMITTED', preserve B4 & B5 formulas).",
            ]),
            ("3. JSON Schema (/workspace/replenishment_audit.json)", [
                "  gross_nonpromo_sales_usd (float, 2 dec), frozen_order_up_to_bays_exact (float, 2 dec),",
                "  minimum_frozen_bays_98pct (int), frozen_bays_committed (int),",
                "  kernel_session_code (str from get_session_card('replenish')).",
            ]),
        ],
    )

    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    klock = threading.Lock()
    st_path = state_dir / "service_state.json"
    skus, pos, _rebates = _build_kernel_tables()
    init_payload = json.dumps({
        "df_sku": skus,
        "df_pos": pos,
        "df_dock_claims": DOCK_CLAIMS_NONPROMO,
        "chilled_floor": CHILLED_FLOOR,
        "coupled_cap": COUPLED_BAY_CAP,
        "code_a": ELAST_ORACLE["kernel_session_code_a"],
        "code_b": REPLEN_ORACLE["kernel_session_code_b"],
    })
    worker_src = (
        "import contextlib, io, json, sys, traceback\n"
        "init = json.loads(sys.stdin.readline())\n"
        "kstate = {'basis': 'GROSS_CARTON'}\n"
        "def set_price_basis(mode):\n"
        "    if mode in ('NET_PROMO_STD', 'GROSS_CARTON'):\n"
        "        kstate['basis'] = mode\n"
        "    return kstate['basis']\n"
        "def get_session_card(domain):\n"
        "    if str(domain).lower().startswith('elast'):\n"
        "        if kstate['basis'] != 'NET_PROMO_STD':\n"
        "            return {'error': 'Switch kernel basis via set_price_basis(\"NET_PROMO_STD\") first', 'current_basis': kstate['basis']}\n"
        "        return {'chilled_min_bays': init['chilled_floor'], 'coupled_cap': init['coupled_cap'], 'kernel_session_code': init['code_a']}\n"
        "    if kstate['basis'] != 'GROSS_CARTON':\n"
        "        return {'error': 'Switch kernel basis via set_price_basis(\"GROSS_CARTON\") first', 'current_basis': kstate['basis']}\n"
        "    return {'service_z': 2.05, 'coupled_cap': init['coupled_cap'], 'kernel_session_code': init['code_b']}\n"
        "base_ns = {'df_sku': init['df_sku'], 'df_pos': init['df_pos'], 'df_dock_claims': init['df_dock_claims'], 'set_price_basis': set_price_basis, 'get_session_card': get_session_card}\n"
        "for ln in sys.stdin:\n"
        "    req = json.loads(ln)\n"
        "    buf = io.StringIO()\n"
        "    err = ''\n"
        "    cell_ns = dict(base_ns, PRICE_BASIS=kstate['basis'])\n"
        "    try:\n"
        "        with contextlib.redirect_stdout(buf):\n"
        "            exec(req.get('code', ''), cell_ns, cell_ns)\n"
        "        if 'df_pos' in cell_ns:\n"
        "            base_ns['df_pos'] = cell_ns['df_pos']\n"
        "    except Exception:\n"
        "        err = traceback.format_exc()[-900:]\n"
        "    cur_len = len(base_ns.get('df_pos')) if isinstance(base_ns.get('df_pos'), list) else -1\n"
        "    sys.stdout.write(json.dumps({'stdout': buf.getvalue()[-10000:], 'error': err, 'df_pos_len': cur_len}) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )
    kproc = subprocess.Popen(
        ["su", "-s", "/bin/bash", "user", "-c", f"cd /tmp && exec python3 -u -c {shlex.quote(worker_src)}"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
    )
    assert kproc.stdin is not None and kproc.stdout is not None
    kproc.stdin.write(init_payload + "\n")
    kproc.stdin.flush()
    exec_cnt = [0]
    write_json(st_path, {"task_id": TASK_ID, "kernel_execs": 0, "df_pos_len": len(pos)})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("nbh_sso" in c) and (c["nbh_sso"].value == tok)
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                raw = b'{"ok":true}'
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self.send_response(403); self.end_headers(); return
                ck = f"nbh_sso={tok}; HttpOnly; Path=/; SameSite=Lax"
                raw = b"<html><body><script>location.href='/notebook';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", ck); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self.send_response(403); self.end_headers(); return
            if u.path == "/notebook":
                raw = NOTEBOOK_UI_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_response(404); self.end_headers()

        def do_POST(self) -> None:
            if not self._authed():
                self.send_response(403); self.end_headers(); return
            if urlparse(self.path).path == "/api/kernel/exec":
                ln = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(ln).decode("utf-8") or "{}")
                code = str(req.get("code") or "")
                with klock:
                    exec_cnt[0] += 1
                    kproc.stdin.write(json.dumps({"code": code}) + "\n")
                    kproc.stdin.flush()
                    resp_ln = kproc.stdout.readline()
                    kres = json.loads(resp_ln) if resp_ln else {"stdout": "", "error": "Kernel exited", "df_pos_len": -1}
                    write_json(st_path, {"task_id": TASK_ID, "kernel_execs": exec_cnt[0], "df_pos_len": kres.get("df_pos_len", -1)})
                raw = json.dumps({"exec_count": exec_cnt[0], "stdout": kres.get("stdout", ""), "error": kres.get("error", "")}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_response(404); self.end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", next(iter(workspace_map.values())))
    launch_libreoffice_uno_natural([hub / "Ammonia_Rack_Schedule.xlsx"], uno_port=UNO_PORT)
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(
    workspace_map: dict[str, Path],
    service_state: dict[str, Any],
    wall_seconds: float,
    active_roles: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    act_set = set(active_roles or META["roles"])
    has_a = "demand_elasticity_ds" in act_set
    has_b = "cold_storage_replenisher" in act_set
    ws_a = workspace_map["demand_elasticity_ds"]
    ws_b = workspace_map["cold_storage_replenisher"]
    hub = workspace_map.get("__shared_hub__", ws_a / "shared_docs")
    plan = read_json_safe(hub / "cold_chain_plan.json")
    xlsx_p = hub / "Ammonia_Rack_Schedule.xlsx"
    sheets = read_multisheet_xlsx(xlsx_p) if xlsx_p.is_file() else {}
    eval_sh = evaluate_xlsx_via_libreoffice(xlsx_p) if xlsx_p.is_file() else {}
    uno_state = inspect_live_uno_documents_readonly(UNO_PORT)
    ja = read_json_safe(ws_a / "elasticity_audit.json")
    jb = read_json_safe(ws_b / "replenishment_audit.json")

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        ev_v = ((eval_sh.get("BaySchedule") or {}).get(ref) or {}).get("value")
        return ev_v if ev_v not in (None, "") else ((sheets.get("BaySchedule") or {}).get(ref) or {}).get("value")

    ch_b = plan.get("chilled_bays", -1)
    fr_b = plan.get("frozen_bays", -1)
    tot_b = (int(ch_b) + int(fr_b)) if isinstance(ch_b, int) and isinstance(fr_b, int) else 99999

    uno_calc_ok = True
    for u_url, u_doc in (uno_state.get("docs") or {}).items():
        if "Ammonia_Rack_Schedule.xlsx" in u_url:
            sm = (u_doc.get("sheets") or {}).get("BaySchedule") or {}
            ca = (not has_a) or (str(sm.get("C2") or "").upper() == "COMMITTED" and int(_f(str(sm.get("B2") or "0").replace(",", ""), -9)) == ch_b)
            cb = (not has_b) or (str(sm.get("C3") or "").upper() == "COMMITTED" and int(_f(str(sm.get("B3") or "0").replace(",", ""), -9)) == fr_b)
            uno_calc_ok = (not u_doc.get("is_modified")) and ca and cb

    got_skus = sorted(ja.get("elastic_chilled_sku_ids") or [])
    exp_skus = ELAST_ORACLE["elastic_chilled_sku_ids"]

    # 17 subchecks Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.05, "Missing elasticity_audit.json"),
        ("a_cens_cnt", ja.get("censored_observation_count") == ELAST_ORACLE["censored_observation_count"], 0.07, f"censored_observation_count != {ELAST_ORACLE['censored_observation_count']}"),
        ("a_skus_6plus", sum(1 for s in exp_skus if s in got_skus) >= 6, 0.06, "elastic_chilled_sku_ids <6 matched"),
        ("a_skus_exact", got_skus == exp_skus, 0.09, "elastic_chilled_sku_ids mismatch"),
        ("a_no_frozen_sku", bool(ja) and all(not s.startswith("SKU-F") for s in got_skus), 0.04, "FROZEN SKU wrongly included in elastic_chilled_sku_ids"),
        ("a_mean_e_rough", abs(_f(ja.get("mean_chilled_abs_elasticity")) - ELAST_ORACLE["mean_chilled_abs_elasticity"]) <= 0.14, 0.06, "mean_chilled_abs_elasticity coarse off (>0.14)"),
        ("a_mean_e_exact", abs(_f(ja.get("mean_chilled_abs_elasticity")) - ELAST_ORACLE["mean_chilled_abs_elasticity"]) <= 0.005, 0.09, f"mean_chilled_abs_elasticity != {ELAST_ORACLE['mean_chilled_abs_elasticity']} (check std_case_units & open_days)"),
        ("a_net_rev_rough", abs(_f(ja.get("net_promo_revenue_usd")) - ELAST_ORACLE["net_promo_revenue_usd"]) <= 80000.0, 0.06, "net_promo_revenue_usd coarse off"),
        ("a_net_rev_exact", abs(_f(ja.get("net_promo_revenue_usd")) - ELAST_ORACLE["net_promo_revenue_usd"]) <= 2.0, 0.09, f"net_promo_revenue_usd != {ELAST_ORACLE['net_promo_revenue_usd']}"),
        ("a_ch_range", isinstance(ch_b, int) and CHILLED_FLOOR <= ch_b <= CHILLED_FLOOR + 42, 0.08, f"chilled_bays={ch_b} outside [{CHILLED_FLOOR},{CHILLED_FLOOR+42}]"),
        ("a_ch_status", plan.get("chilled_status") == "COMMITTED", 0.05, "chilled_status != COMMITTED"),
        ("a_ch_match", ja.get("chilled_bays_committed") == ch_b and int(_f(_cv("B2"), -9)) == ch_b, 0.06, "JSON/plan/XLSX BaySchedule!B2 chilled_bays mismatch"),
        ("a_code", ja.get("kernel_session_code") == ELAST_ORACLE["kernel_session_code_a"], 0.08, "Wrong kernel_session_code"),
        ("a_no_swap", bool(ja) and ja.get("kernel_session_code") != REPLEN_ORACLE["kernel_session_code_b"], 0.04, "Swapped session code"),
        ("a_fac_kept", bool(ja) and plan.get("facility_id") == "AMMONIA-RACK-NORTH-07", 0.04, "facility_id clobbered"),
        ("a_fr_kept", bool(ja) and "frozen_bays" in plan, 0.04, "frozen_bays deleted from plan"),
    ]

    # 17 subchecks Role B
    gross_got = _f(jb.get("gross_nonpromo_sales_usd"))
    gross_exp = REPLEN_ORACLE["gross_nonpromo_sales_usd"]
    gross_net_spoil = round(gross_exp - 2878.00, 2)
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.05, "Missing replenishment_audit.json"),
        ("b_gross_rough", abs(gross_got - gross_exp) <= 120000.0, 0.06, "gross_nonpromo_sales_usd coarse off"),
        ("b_gross_exact", min(abs(gross_got - gross_exp), abs(gross_got - gross_net_spoil)) <= 2.5, 0.11, f"gross_nonpromo_sales_usd != {gross_exp} (check CENTS/100 & df_dock_claims in kernel)"),
        ("b_fine_dock_claims", abs(gross_got - (gross_exp + DOCK_CLAIMS_TOTAL_USD)) > 100.0 and min(abs(gross_got - gross_exp), abs(gross_got - gross_net_spoil)) <= 50.0, 0.08, "Cold-dock rejection claims (df_dock_claims) not netted from non-promo sales"),
        ("b_exact_bays_rough", abs(_f(jb.get("frozen_order_up_to_bays_exact")) - REPLEN_ORACLE["frozen_order_up_to_bays_exact"]) <= 65.0, 0.06, "frozen_order_up_to_bays_exact coarse off"),
        ("b_exact_bays_tight", abs(_f(jb.get("frozen_order_up_to_bays_exact")) - REPLEN_ORACLE["frozen_order_up_to_bays_exact"]) <= 0.25, 0.10, f"frozen_order_up_to_bays_exact != {REPLEN_ORACLE['frozen_order_up_to_bays_exact']}"),
        ("b_min_fr", jb.get("minimum_frozen_bays_98pct") == FROZEN_FLOOR, 0.09, f"minimum_frozen_bays_98pct != {FROZEN_FLOOR}"),
        ("b_fr_range", isinstance(fr_b, int) and (FROZEN_FLOOR - 55) <= fr_b <= FROZEN_FLOOR + 42, 0.08, f"frozen_bays={fr_b} outside range"),
        ("b_fr_status", plan.get("frozen_status") == "COMMITTED", 0.05, "frozen_status != COMMITTED"),
        ("b_fr_match", jb.get("frozen_bays_committed") == fr_b and int(_f(_cv("B3"), -9)) == fr_b, 0.06, "JSON/plan/XLSX BaySchedule!B3 frozen_bays mismatch"),
        ("b_code", jb.get("kernel_session_code") == REPLEN_ORACLE["kernel_session_code_b"], 0.09, "Wrong kernel_session_code"),
        ("b_no_swap", bool(jb) and jb.get("kernel_session_code") != ELAST_ORACLE["kernel_session_code_a"], 0.04, "Swapped session code"),
        ("b_fac_kept", bool(jb) and plan.get("facility_id") == "AMMONIA-RACK-NORTH-07", 0.04, "facility_id clobbered"),
        ("b_ch_kept", bool(jb) and "chilled_bays" in plan, 0.04, "chilled_bays deleted from plan"),
        ("b_cap_kept", bool(jb) and plan.get("max_total_ammonia_bays") == COUPLED_BAY_CAP, 0.04, "max_total_ammonia_bays altered"),
        ("b_not_cents_100x", bool(jb) and _f(jb.get("gross_nonpromo_sales_usd")) < 5_000_000, 0.05, "Failed to divide CENTS prices by 100"),
        ("b_ceil_ge_exact", bool(jb) and _f(jb.get("minimum_frozen_bays_98pct")) >= _f(jb.get("frozen_order_up_to_bays_exact")), 0.05, "ceil < exact"),
    ]

    df_ok = service_state.get("df_pos_len", RAW_KERNEL_POS_LEN) == RAW_KERNEL_POS_LEN
    eff_ch = int(ch_b) if (has_a and isinstance(ch_b, int)) else (CHILLED_FLOOR if not has_a else 99999)
    eff_fr = int(fr_b) if (has_b and isinstance(fr_b, int)) else (FROZEN_FLOOR if not has_b else 99999)
    eff_tot = eff_ch + eff_fr
    floors_ok = ((not has_a) or (isinstance(ch_b, int) and ch_b >= CHILLED_FLOOR)) and ((not has_b) or (isinstance(fr_b, int) and fr_b >= FROZEN_FLOOR))
    comm_ok = ((not has_a) or plan.get("chilled_status") == "COMMITTED") and ((not has_b) or plan.get("frozen_status") == "COMMITTED")
    act_sub = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))
    kw_f = str(((sheets.get("BaySchedule") or {}).get("B5") or {}).get("formula") or "").upper().replace(" ", "")
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_ammonia_bay_cap", floors_ok and (eff_tot <= COUPLED_BAY_CAP), 0.09, f"Coupled total bays {eff_tot} exceeds facility cap {COUPLED_BAY_CAP} (or below floor)!"),
        ("j_both_committed", comm_ok and ("2.4*B2+4.1*B3" in kw_f), 0.06, "Missing COMMITTED status or clobbered BaySchedule!B5 kW formula"),
        ("j_uno_calc_synced", act_sub and uno_calc_ok, 0.06, "Live LibreOffice Calc Ammonia_Rack_Schedule.xlsx out-of-sync with disk"),
        ("j_kernel_df_intact", act_sub and df_ok, 0.05, f"Shared kernel `df_pos` mutated/filtered in-place (len != {RAW_KERNEL_POS_LEN})"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=1.0,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    assert role in ("demand_elasticity_ds", "cold_storage_replenisher")
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", ws / "shared_docs")
    plan_p = hub / "cold_chain_plan.json"
    xlsx_p = hub / "Ammonia_Rack_Schedule.xlsx"

    if role == "demand_elasticity_ds":
        with file_atomic_lock("nf13_plan"):
            pl = read_json_safe(plan_p)
            cur_fr = int(pl.get("frozen_bays") or 0)
            fr_comm = pl.get("frozen_status") == "COMMITTED"
            max_ch = (COUPLED_BAY_CAP - cur_fr - 2) if fr_comm else (CHILLED_FLOOR + 4)
            ch_val = max(CHILLED_FLOOR, min(CHILLED_FLOOR + 5, max_ch))
            pl["chilled_bays"] = ch_val
            pl["chilled_status"] = "COMMITTED"
            write_json(plan_p, pl)
            update_single_sheet_xlsx(
                xlsx_p,
                "BaySchedule",
                [
                    ["Zone", "Allocated_Bays", "AMMONIA-RACK-NORTH-07"],
                    ["Chilled_2C_Bays", ch_val, "COMMITTED"],
                    ["Frozen_20C_Bays", cur_fr, pl.get("frozen_status", "PENDING")],
                    ["Total_Facility_Bays", ("=SUM(B2:B3)", ch_val + cur_fr), f"MAX_{COUPLED_BAY_CAP}"],
                    ["Compressor_Load_kW", ("=2.4*B2+4.1*B3", round(2.4 * ch_val + 4.1 * cur_fr, 2)), "ACTIVE_FORMULA"],
                ],
            )
            reload_uno_pipe_documents([xlsx_p])
        write_json(
            ws / "elasticity_audit.json",
            {
                "censored_observation_count": ELAST_ORACLE["censored_observation_count"],
                "elastic_chilled_sku_ids": ELAST_ORACLE["elastic_chilled_sku_ids"],
                "mean_chilled_abs_elasticity": ELAST_ORACLE["mean_chilled_abs_elasticity"],
                "net_promo_revenue_usd": ELAST_ORACLE["net_promo_revenue_usd"],
                "chilled_bays_committed": ch_val,
                "kernel_session_code": ELAST_ORACLE["kernel_session_code_a"],
            },
        )
    else:
        with file_atomic_lock("nf13_plan"):
            pl = read_json_safe(plan_p)
            cur_ch = int(pl.get("chilled_bays") or 0)
            ch_comm = pl.get("chilled_status") == "COMMITTED"
            max_fr = (COUPLED_BAY_CAP - cur_ch - 2) if ch_comm else (FROZEN_FLOOR + 4)
            fr_val = max(FROZEN_FLOOR, min(FROZEN_FLOOR + 5, max_fr))
            pl["frozen_bays"] = fr_val
            pl["frozen_status"] = "COMMITTED"
            write_json(plan_p, pl)
            update_single_sheet_xlsx(
                xlsx_p,
                "BaySchedule",
                [
                    ["Zone", "Allocated_Bays", "AMMONIA-RACK-NORTH-07"],
                    ["Chilled_2C_Bays", cur_ch, pl.get("chilled_status", "PENDING")],
                    ["Frozen_20C_Bays", fr_val, "COMMITTED"],
                    ["Total_Facility_Bays", ("=SUM(B2:B3)", cur_ch + fr_val), f"MAX_{COUPLED_BAY_CAP}"],
                    ["Compressor_Load_kW", ("=2.4*B2+4.1*B3", round(2.4 * cur_ch + 4.1 * fr_val, 2)), "ACTIVE_FORMULA"],
                ],
            )
            reload_uno_pipe_documents([xlsx_p])
        write_json(
            ws / "replenishment_audit.json",
            {
                "gross_nonpromo_sales_usd": REPLEN_ORACLE["gross_nonpromo_sales_usd"],
                "frozen_order_up_to_bays_exact": REPLEN_ORACLE["frozen_order_up_to_bays_exact"],
                "minimum_frozen_bays_98pct": FROZEN_FLOOR,
                "frozen_bays_committed": fr_val,
                "kernel_session_code": REPLEN_ORACLE["kernel_session_code_b"],
            },
        )


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4: In-place `df_pos` filter truncates kernel table & TOCTOU bay allocations (floor+7 + floor+7 > cap) overflow."""
    solve_role("demand_elasticity_ds", workspace_map, port)
    solve_role("cold_storage_replenisher", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", next(iter(workspace_map.values())))
    pl = read_json_safe(hub / "cold_chain_plan.json")
    pl["chilled_bays"] = CHILLED_FLOOR + 7
    pl["frozen_bays"] = FROZEN_FLOOR + 7  # Sum = floor_sum + 14 > floor_sum + 10 cap!
    write_json(hub / "cold_chain_plan.json", pl)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["df_pos_len"] = 288
    write_json(sp, st)

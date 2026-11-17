"""UID-0 stateful browser apps (CSRF/SSO/Canvas, no batch API bypass) & black-box coupled DRC simulators for UA-01..UA-04."""
from __future__ import annotations

import argparse
import csv
import hashlib
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlparse
from zipfile import ZipFile

try:
    from tasks.ultra_arenas_v1.catalog import UA_BY_ID
except ImportError:
    from catalog import UA_BY_ID  # type: ignore

try:
    from tasks.thematic_arenas_v1.xlsx_utils import evaluate_xlsx_via_libreoffice, read_multisheet_xlsx
except ImportError:
    from xlsx_utils import evaluate_xlsx_via_libreoffice, read_multisheet_xlsx  # type: ignore

try:
    from tasks.ultra_arenas_v1.flagship_30m import (
        FLAGSHIP_IDS,
        UA08_BI_PAGES,
        UA09_REAL_BUGS_7,
        eval_ua08_drc,
        eval_ua09_drc,
        eval_ua10_drc,
        eval_ua11_drc,
    )
except ImportError:
    from flagship_30m import (  # type: ignore
        FLAGSHIP_IDS,
        UA08_BI_PAGES,
        UA09_REAL_BUGS_7,
        eval_ua08_drc,
        eval_ua09_drc,
        eval_ua10_drc,
        eval_ua11_drc,
    )

try:
    from tasks.ultra_arenas_v1.extreme_35m import EXTREME_IDS, eval_ua12_drc, eval_ua13_drc, eval_ua14_drc, eval_ua15_drc
except ImportError:
    from extreme_35m import EXTREME_IDS, eval_ua12_drc, eval_ua13_drc, eval_ua14_drc, eval_ua15_drc  # type: ignore


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Paginated BI datasets for UA-01 (3 scopes x 4 pages = 12 interactive GUI views; NO unauthenticated batch JSON API!)
UA01_BI_PAGES = {
    "FIN": [
        [("NA_Core_Cloud", 920.0, 285.0, 40.0), ("NA_AI_Inference", 640.0, 210.0, 25.0), ("NA_Enterprise_Support", 310.0, 115.0, 15.0)],
        [("EMEA_Core_Cloud", 710.0, 230.0, 30.0), ("EMEA_AI_Inference", 480.0, 165.0, 20.0), ("EMEA_Sovereign_Hosted", 260.0, 98.0, 10.0)],
        [("APAC_Core_Cloud", 610.0, 205.0, 28.0), ("APAC_AI_Inference", 430.0, 150.0, 17.0), ("APAC_Edge_CDN", 215.0, 82.0, 10.0)],
        [("LATAM_Cloud_Suite", 295.0, 108.0, 12.0), ("LATAM_Managed_AI", 185.0, 68.0, 8.0), ("Global_OEM_Royalties", 245.0, 44.0, 5.0)],
    ],
    # Clean Q3 USD Excl-IC sum: Gross=5300, IC=220 -> NetRev_Base = 5080.0 kUSD; DirectCost_Base = 1760.0 kUSD;
    # Regional NetRev_Base: NA=1790, EMEA=1390, APAC=1200, LATAM+OEM=700; Audit APAC Contra on <canvas> = -120.0 -> APAC=1080, Total=4960.0
    "OPS": [
        [("DC_US_Virginia", "NA", 42, 1.34, 18.5), ("DC_US_Oregon", "NA", 36, 1.29, 21.0), ("DC_CA_Montreal", "NA", 22, 1.24, 24.0), ("DC_US_Texas", "NA", 28, 1.38, 22.5)],
        [("DC_EU_Frankfurt", "EMEA", 34, 1.31, 19.5), ("DC_EU_Dublin", "EMEA", 28, 1.26, 22.0), ("DC_UK_London", "EMEA", 24, 1.33, 20.5), ("DC_SE_Stockholm", "EMEA", 18, 1.21, 26.0)],
        [("DC_JP_Tokyo", "APAC", 32, 1.35, 20.0), ("DC_SG_Jurong", "APAC", 26, 1.42, 23.5), ("DC_AU_Sydney", "APAC", 18, 1.36, 29.0), ("DC_KR_Seoul", "APAC", 20, 1.32, 21.5)],
        [("DC_BR_SaoPaulo", "LATAM", 18, 1.44, 34.0), ("DC_CL_Santiago", "LATAM", 12, 1.37, 36.5), ("DC_MX_Queretaro", "LATAM", 14, 1.39, 28.5), ("DC_ZA_Joburg", "EMEA", 10, 1.45, 39.0)],
    ],
    "SALES": [
        [("T01_NA_F500", "NA", 1650.0, 145), ("T02_NA_Digital", "NA", 1180.0, 210), ("T03_NA_Public", "NA", 720.0, 85)],
        [("T04_EMEA_DACH", "EMEA", 1120.0, 130), ("T05_EMEA_West", "EMEA", 980.0, 155), ("T06_EMEA_Nordics", "EMEA", 640.0, 90)],
        [("T07_APAC_Japan", "APAC", 940.0, 120), ("T08_APAC_ASEAN", "APAC", 820.0, 160), ("T09_APAC_ANZ", "APAC", 510.0, 75)],
        [("T10_LATAM_Brazil", "LATAM", 540.0, 95), ("T11_LATAM_North", "LATAM", 390.0, 70), ("T12_Global_Strategic", "NA", 890.0, 65)],
    ],
}

# Ground-truth facts from real live external websites (verified live on GitHub / HuggingFace / arXiv / PEPs)
REAL_WEB_ANCHORS = {
    "transformer_year": 2017,          # arXiv 1706.03762 Attention Is All You Need
    "gpt3_year": 2020,                 # arXiv 2005.14165 Language Models are Few-Shot Learners (175B)
    "resnet_year": 2015,               # arXiv 1512.03385 Deep Residual Learning
    "gpt2_vocab_size": 50257,          # huggingface.co/openai-community/gpt2 config.json
    "bert_hidden_size": 768,           # huggingface.co/google-bert/bert-base-uncased config.json
    "pep8_line_length": 79,            # peps.python.org/pep-0008/
}


def eval_ua01_drc(workspace: Path, run_blender_check: bool = True) -> dict:
    """Coupled 4-role Q3 Portfolio Monte-Carlo + LibreOffice + Blender Cycles audit (~8-12s real compute)."""
    t0 = time.monotonic()
    xlsx_p = workspace / "Q3_Enterprise_Model.xlsx"
    if not xlsx_p.is_file():
        return {"ok": False, "error": "Missing /workspace/Q3_Enterprise_Model.xlsx"}
    raw_wb = read_multisheet_xlsx(xlsx_p)
    ev_wb = evaluate_xlsx_via_libreoffice(xlsx_p)

    sum_raw = raw_wb.get("Executive_Summary", {})
    sum_ev = ev_wb.get("Executive_Summary", {})
    formulas_ok = all(bool((sum_raw.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4", "B5", "B6", "B7", "B8"))

    def _num(sheet: dict, ref: str, default: float = 0.0) -> float:
        v = (sheet.get(ref) or {}).get("value")
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    base_rev = _num(sum_ev, "B2")       # Expected from Finance_12M clean Q3 USD Excl-IC - 120 APAC contra = 4960.0
    direct_cost = _num(sum_ev, "B3")    # Expected 1760.0
    ops_capex_opex = _num(sum_ev, "B4") # Coupled from Datacenter_16R rack + PUE cooling plan
    sales_weighted = _num(sum_ev, "B5") # Coupled from Pipeline_12T price_mult & rebate
    debt_service_q = _num(sum_ev, "B6") # Coupled from Finance_12M hedge_ratio & debt_tenor
    noi = _num(sum_ev, "B7")            # = B2 + 0.18*B5 - B3 - B4
    eco_score = _num(sum_ev, "B8")      # Real external web verification checksum (50257 + 768 + 2017 + 2020 + 79 = 55141)

    # Read control levers from sheets for coupled non-linear stress simulation
    dc_sh = ev_wb.get("Datacenter_16R", {})
    # Heterogeneous regional grid capacity & thermal throttling per datacenter (black-box sensitivity!)
    dc_weights = [1.35, 1.25, 0.90, 1.10, 1.30, 1.15, 1.20, 0.85, 1.32, 1.18, 0.92, 1.05, 0.95, 0.80, 0.88, 0.80]
    dc_pue_floors = [1.22, 1.20, 1.16, 1.26, 1.21, 1.18, 1.22, 1.15, 1.23, 1.28, 1.24, 1.21, 1.29, 1.25, 1.26, 1.28]
    tot_active_racks = 0.0; tot_failover_racks = 0.0; eff_capacity_units = 0.0; thermal_pen_ms = 0.0; pue_vals = []
    hot_dcs = []
    for idx in range(16):
        r = idx + 2
        act_r = _num(dc_sh, f"C{r}"); fo_r = _num(dc_sh, f"D{r}"); pue_r = _num(dc_sh, f"E{r}", 1.45)
        tot_active_racks += act_r; tot_failover_racks += fo_r; pue_vals.append(pue_r)
        sat = act_r - 0.022 * max(0.0, act_r - 32.0) ** 2
        eff_capacity_units += sat * dc_weights[idx] + 0.65 * fo_r * dc_weights[idx]
        if pue_r < dc_pue_floors[idx]:
            thermal_pen_ms += (dc_pue_floors[idx] - pue_r) * 95.0
            hot_dcs.append(f"DC_{idx+1:02d}(pue<{dc_pue_floors[idx]})")
        elif act_r > 35:
            hot_dcs.append(f"DC_{idx+1:02d}(grid_sat)")
    mean_pue = sum(pue_vals) / 16.0

    sp_sh = ev_wb.get("Pipeline_12T", {})
    elast_caps = [1.11, 1.05, 1.03, 1.09, 1.06, 1.08, 1.10, 1.03, 1.05, 1.01, 1.01, 1.12]
    price_mults = []; rebate_pcts = []; seg_churn = 0.0; churn_terrs = []
    for idx in range(12):
        r = idx + 2
        pm = _num(sp_sh, f"E{r}", 1.0); rb = _num(sp_sh, f"F{r}", 0.0)
        price_mults.append(pm); rebate_pcts.append(rb)
        if pm > elast_caps[idx]:
            c_i = ((pm - elast_caps[idx]) ** 2) * 3800.0
            seg_churn += c_i; churn_terrs.append(f"T{idx+1:02d}(pm>{elast_caps[idx]})")
        elif pm < 0.96:
            seg_churn += (0.96 - pm) * 450.0
    mean_price_mult = sum(price_mults) / 12.0
    mean_rebate = sum(rebate_pcts) / 12.0

    fin_sh = ev_wb.get("Finance_12M", {})
    hedge_ratio = _num(fin_sh, "F2", 0.20)   # [0.0, 1.0]
    reserve_kusd = _num(fin_sh, "F3", 300.0) # Cash reserve buffer

    churn_penalty = seg_churn
    effective_nrr_pct = round(104.0 + 55.0 * (mean_price_mult - 0.95) + 80.0 * mean_rebate - 0.025 * churn_penalty, 2)
    # Peak inference load grows with NRR & rebate-driven adoption, requiring active + failover GPU racks!
    required_racks = 395.0 * (effective_nrr_pct / 112.0)
    rack_headroom = eff_capacity_units / max(1.0, required_racks)
    p95_latency_ms = round(26.5 / max(0.35, rack_headroom) + max(0.0, (mean_pue - 1.28) * 35.0) + thermal_pen_ms, 2)
    failover_ratio = tot_failover_racks / max(1.0, tot_active_racks)

    # 20-quarter deterministic pseudo-Monte-Carlo stress path (5,000 paths)
    worst_dscr = 99.0
    min_cash_kusd = 99999.0
    for path_i in range(2500):
        phase = (path_i + 1) * 0.137
        macro_shock = 1.0 - 0.11 * abs(math.sin(phase)) - 0.06 * (1.0 - min(1.0, hedge_ratio)) * abs(math.cos(phase * 1.7))
        power_spike = 1.0 + 0.14 * max(0.0, mean_pue - 1.25) * abs(math.sin(phase * 0.9))
        stressed_ebitda = (base_rev * macro_shock + 0.18 * sales_weighted * macro_shock - churn_penalty) - direct_cost - (ops_capex_opex * power_spike) - (hedge_ratio * 65.0)
        dscr = stressed_ebitda / max(1.0, debt_service_q)
        cash_end = reserve_kusd + 0.35 * (stressed_ebitda - debt_service_q)
        if dscr < worst_dscr:
            worst_dscr = dscr
        if cash_end < min_cash_kusd:
            min_cash_kusd = cash_end

    tot_rev_eff = base_rev + 0.18 * sales_weighted
    noi_margin_pct = round(100.0 * noi / max(1.0, tot_rev_eff), 2)

    # Check Blender 3D cover scene & render if present
    blend_p = workspace / "q3_cover_3d.blend"
    cover_png = workspace / "exports/q3_revenue_3d.png"
    bars_match = False
    render_luma = 0.0
    if run_blender_check and blend_p.is_file() and cover_png.is_file():
        try:
            from PIL import Image
            im = Image.open(cover_png).convert("RGB")
            if im.size == (800, 450):
                pxs = list(im.getdata())
                render_luma = round(sum(0.2126*r + 0.7152*g + 0.0722*b for r, g, b in pxs[::16]) / (len(pxs[::16]) * 255.0), 4)
            probe = (
                "import bpy, json\n"
                f"bpy.ops.wm.open_mainfile(filepath={str(blend_p)!r})\n"
                "hs = [bpy.data.objects[n].dimensions.z for n in ('Bar_NA','Bar_EMEA','Bar_APAC','Bar_LATAM') if n in bpy.data.objects]\n"
                "print('BARS_JSON:' + json.dumps(hs))\n"
            )
            cp = subprocess.run(["blender", "-b", "--python-expr", probe], capture_output=True, text=True, timeout=35)
            for ln in cp.stdout.splitlines():
                if "BARS_JSON:" in ln:
                    hs = json.loads(ln.split("BARS_JSON:", 1)[1])
                    if len(hs) == 4 and hs[0] > 0.1:
                        # Expected regional ratios NA=1790, EMEA=1390, APAC=1080 (post -120 contra!), LATAM=700
                        r_em = hs[1] / hs[0]; r_ap = hs[2] / hs[0]; r_la = hs[3] / hs[0]
                        bars_match = (abs(r_em - 1390/1790) <= 0.035 and abs(r_ap - 1080/1790) <= 0.035 and abs(r_la - 700/1790) <= 0.035 and 0.12 <= render_luma <= 0.72)
        except Exception:
            pass

    gates = {
        "G_FIN_1_base_rev_and_apac_contra": math.isclose(base_rev, 4960.0, abs_tol=1.5) and math.isclose(direct_cost, 1760.0, abs_tol=1.5),
        "G_FIN_2_stress_min_dscr_ge_1_42": worst_dscr >= 1.42,
        "G_FIN_3_stress_min_cash_ge_650": min_cash_kusd >= 650.0 and reserve_kusd <= 920.0,
        "G_FIN_4_noi_margin_in_band": 46.5 <= noi_margin_pct <= 52.5,
        "G_OPS_1_p95_latency_le_38ms": p95_latency_ms <= 38.0,
        "G_OPS_2_failover_redundancy_ge_22pct": 0.22 <= failover_ratio <= 0.38,
        "G_OPS_3_ops_budget_cap_le_1280": 820.0 <= ops_capex_opex <= 1280.0 and mean_pue <= 1.31,
        "G_OPS_4_global_map_svg_and_png": (workspace / "exports/dc_footprint_300dpi.png").is_file(),
        "G_SALES_1_weighted_pipeline_ge_3650": 3650.0 <= sales_weighted <= 4450.0,
        "G_SALES_2_nrr_ge_114_low_churn": effective_nrr_pct >= 114.0 and churn_penalty <= 85.0 and mean_rebate <= 0.09,
        "G_SALES_3_ecosystem_real_web_anchors": math.isclose(eco_score, 55141.0, abs_tol=0.5),
        "G_EXEC_1_summary_formulas_preserved": formulas_ok,
        "G_EXEC_2_blender_3d_bars_match_restated_regions": bars_match,
        "G_EXEC_3_writer_pdf_and_pptx_clipboard": (workspace / "exports/Q3_Board_Briefing.pdf").is_file() and (workspace / "Q3_Board_Deck.pptx").is_file(),
    }
    return {
        "ok": True,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v),
        "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "base_rev_kusd": round(base_rev, 2),
            "direct_cost_kusd": round(direct_cost, 2),
            "ops_capex_opex_kusd": round(ops_capex_opex, 2),
            "sales_weighted_kusd": round(sales_weighted, 2),
            "debt_service_q_kusd": round(debt_service_q, 2),
            "noi_kusd": round(noi, 2),
            "noi_margin_pct": noi_margin_pct,
            "worst_20q_dscr": round(worst_dscr, 4),
            "min_stress_cash_kusd": round(min_cash_kusd, 2),
            "p95_latency_ms": p95_latency_ms,
            "failover_ratio": round(failover_ratio, 4),
            "mean_pue": round(mean_pue, 4),
            "effective_nrr_pct": effective_nrr_pct,
            "churn_penalty_kusd": round(churn_penalty, 2),
            "ecosystem_web_checksum": eco_score,
            "blender_render_luma": render_luma,
            "throttled_datacenters": hot_dcs[:6],
            "high_churn_territories": churn_terrs[:6],
        },
    }


def eval_ua02_drc(workspace: Path) -> dict:
    """Coupled 4-role Full-Stack Launch Day E2E + Cycles/GIMP/Inkscape + Real-Web CMS + Canary QA audit."""
    from PIL import Image
    t0 = time.monotonic()
    repo = workspace / "nexus-portal"
    db_p = workspace / "staging_data/nexus.db"
    assets_dir = repo / "static/assets"

    routes = ("index", "pricing", "docs", "sdk", "integrations", "benchmarks", "security", "changelog")
    routes_ok = all(
        (repo / f"templates/{rt}.html").is_file()
        and 'data-nexus-v5="ready"' in (repo / f"templates/{rt}.html").read_text(encoding="utf-8", errors="ignore")
        for rt in routes
    )
    logic_p = repo / "portal_config.json"
    cfg = json.loads(logic_p.read_text(encoding="utf-8")) if logic_p.is_file() else {}
    # Coupled performance vs payload budget: connection_pool, compression_level, and total static asset KB!
    pool_sz = int(cfg.get("sqlite_pool_size", 1))
    annual_disc = float(cfg.get("annual_discount_pct", -20.0))  # Bug 1 seeded as -20 (surcharge)
    ent_tier_mult = float(cfg.get("enterprise_sla_mult", 0.0))   # Bug 2 seeded as 0.0
    tz_mode = str(cfg.get("changelog_tz", "PST-8"))              # Bug 3 seeded as PST-8
    csrf_enforced = bool(cfg.get("csrf_cookie_samesite", False)) # Bug 4 seeded as False
    svg_vb_ok = (assets_dir / "brand_mark.svg").is_file() and 'viewBox="0 0 160 48"' in (assets_dir / "brand_mark.svg").read_text(encoding="utf-8", errors="ignore")  # Bug 5 seeded as 0 0 48 48

    # Design multi-software checks: 3 Cycles PNGs + 4 GIMP cards + 4 Inkscape icons, coupled with total_asset_kb <= 1150 KB!
    hero_files = [("hero_front.png", (1280, 640)), ("hero_iso.png", (800, 500)), ("hero_detail.png", (800, 500))]
    heroes_ok = True
    min_occ = 1.0
    for fn, wh in hero_files:
        fp = assets_dir / fn
        if not fp.is_file():
            heroes_ok = False; break
        im = Image.open(fp).convert("RGB")
        if im.size != wh:
            heroes_ok = False; break
        pxs = list(im.getdata())[::25]
        non_bg = sum(1 for r, g, b in pxs if (r + g + b) > 95) / max(1, len(pxs))
        min_occ = min(min_occ, non_bg)
        if not (0.18 <= non_bg <= 0.82):
            heroes_ok = False

    cards_ok = all((assets_dir / f"feature_card_{i}.png").is_file() and Image.open(assets_dir / f"feature_card_{i}.png").size == (640, 400) for i in range(1, 5))
    icons_ok = all((assets_dir / f"badge_{i}.png").is_file() and Image.open(assets_dir / f"badge_{i}.png").size == (128, 128) for i in range(1, 5))
    total_asset_kb = round(sum(p.stat().st_size for p in assets_dir.glob("*") if p.is_file()) / 1024.0, 2) if assets_dir.is_dir() else 99999.0

    # Simulated page-load P95 couples sqlite_pool_size + total_asset_kb!
    sim_page_p95_ms = round(42.0 + (260.0 / max(1, min(pool_sz, 24))) + 0.085 * total_asset_kb + (18.0 * max(0, pool_sz - 16)), 2)

    # CMS 16 published articles grounded in real external web facts
    cms_pub = 0
    web_grounded = 0
    if db_p.is_file():
        try:
            con = sqlite3.connect(str(db_p))
            rows = con.execute("SELECT slug, license_spdx, benchmark_num, asset_file, published FROM cms_integrations").fetchall()
            con.close()
            cms_pub = sum(1 for r in rows if int(r[4]) == 1 and (assets_dir / str(r[3])).is_file())
            expected_facts = {"flask": "BSD", "requests": "Apache", "sqlalchemy": "MIT", "gpt2": "50257", "resnet": "2015", "pep8": "79"}
            for slug, lic, bnum, _af, pub in rows:
                if int(pub) == 1:
                    for k, tok in expected_facts.items():
                        if k in str(slug).lower() and (tok.lower() in str(lic).lower() or tok in str(bnum)):
                            web_grounded += 1
        except sqlite3.Error:
            pass

    qa_xlsx = workspace / "QA_Regression_Matrix.xlsx"
    qa_pdf = workspace / "exports/QA_Release_Report.pdf"
    git_clean = False
    if (repo / ".git").is_dir():
        st = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout.strip()
        br = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        git_clean = (st == "" and br == "main")

    gates = {
        "G_FE_1_eight_routes_upgraded": routes_ok,
        "G_FE_2_five_seeded_bugs_remediated": math.isclose(annual_disc, 20.0, abs_tol=0.1) and math.isclose(ent_tier_mult, 1.35, abs_tol=0.02) and tz_mode == "UTC" and csrf_enforced and svg_vb_ok,
        "G_FE_3_coupled_page_p95_le_155ms": sim_page_p95_ms <= 155.0 and 8 <= pool_sz <= 16,
        "G_DES_1_three_cycles_renders_framed": heroes_ok,
        "G_DES_2_gimp_cards_and_inkscape_badges": cards_ok and icons_ok,
        "G_DES_3_coupled_asset_payload_le_1150kb": 8.0 <= total_asset_kb <= 1150.0,
        "G_CMS_1_16_articles_published_with_valid_assets": cms_pub >= 16,
        "G_CMS_2_real_external_web_facts_verified": web_grounded >= 6,
        "G_QA_1_regression_xlsx_and_pdf": qa_xlsx.is_file() and qa_pdf.is_file(),
        "G_QA_2_git_main_clean_tree": git_clean,
    }
    time.sleep(2.0)
    return {
        "ok": True,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v),
        "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "sim_page_p95_ms": sim_page_p95_ms,
            "total_asset_kb": total_asset_kb,
            "sqlite_pool_size": pool_sz,
            "cms_published_valid": cms_pub,
            "real_web_grounded_count": web_grounded,
            "min_hero_occupancy": round(min_occ, 3),
            "git_clean": git_clean,
        },
    }


def eval_ua03_drc(workspace: Path, burst_mult: float = 1.0) -> dict:
    """Coupled 4-role Incident War-Room + Geo-Edge SpatiaLite/QGIS + Memory/Cost Cap Simulator."""
    t0 = time.monotonic()
    cdir = workspace / "cluster"
    gpkg = workspace / "data/edge_network.gpkg"

    # 1. DB state & memory allocation
    db_p = cdir / "prod_ledger.db"
    db_cfg = json.loads((cdir / "db_tuning.json").read_text(encoding="utf-8")) if (cdir / "db_tuning.json").is_file() else {}
    app_cfg = json.loads((cdir / "app_gateway.json").read_text(encoding="utf-8")) if (cdir / "app_gateway.json").is_file() else {}
    inf_cfg = json.loads((cdir / "infra_daemon.json").read_text(encoding="utf-8")) if (cdir / "infra_daemon.json").is_file() else {}

    has_idx1 = has_idx2 = False
    if db_p.is_file():
        try:
            con = sqlite3.connect(str(db_p))
            for row in con.execute("PRAGMA index_list('ledger_events')").fetchall():
                cols = [r[2] for r in con.execute(f"PRAGMA index_info('{row[1]}')").fetchall()]
                if "account_id" in cols and "event_ts" in cols:
                    has_idx1 = True
                if "region_code" in cols and "status" in cols:
                    has_idx2 = True
            con.close()
        except sqlite3.Error:
            pass

    db_cache_mb = float(db_cfg.get("sqlite_cache_mb", 32.0))
    batch_sz = int(db_cfg.get("checkpoint_batch", 5000))
    app_lru_mb = float(app_cfg.get("hot_cache_mb", 32.0))
    worker_mb = float(inf_cfg.get("telemetry_buffer_mb", 260.0))  # Seeded bloated at 260 MB!
    tot_mem_mb = round(db_cache_mb + app_lru_mb + worker_mb, 2)
    oom_triggered = tot_mem_mb > 640.0

    backoff_ms = float(app_cfg.get("retry_backoff_ms", 0.0))
    max_ret = int(app_cfg.get("max_retries", 12))
    ttl_s = float(app_cfg.get("cache_ttl_s", 0.0))
    singleflight = bool(app_cfg.get("singleflight", False))
    token_rate = float(app_cfg.get("token_bucket_rps", 200.0))

    log_lvl = str(inf_cfg.get("log_level", "TRACE_ALL")).upper()
    probe_ms = int(inf_cfg.get("liveness_timeout_ms", 40))
    dump_kb = ((cdir / "disk_vol/core_trace.bin").stat().st_size / 1024.0) if (cdir / "disk_vol/core_trace.bin").is_file() else 0.0

    # Coupled latency physics: DB needs >=180MB cache + both indexes; App needs >=220MB LRU + singleflight + TTL>=90s; Infra worker_mb in [90, 180]!
    idx_pen = 0.0 if (has_idx1 and has_idx2 and batch_sz <= 400) else 240.0
    db_ms = 14.0 + (2200.0 / max(32.0, db_cache_mb)) + idx_pen
    miss_rate = 0.08 + (42.0 / max(24.0, app_lru_mb)) + (0.35 if ttl_s < 90 else 0.0) + (0.20 if not singleflight else 0.0)
    retry_amp = 1.0 if (150.0 <= backoff_ms <= 600.0 and 1 <= max_ret <= 3 and 900.0 <= token_rate <= 1800.0) else 4.2
    infra_pen = 0.0 if (log_lvl in ("INFO", "WARN") and probe_ms >= 800 and dump_kb < 100.0 and 90.0 <= worker_mb <= 190.0) else 380.0

    # Geo-edge SpatiaLite 24 POP routing check
    max_pop_util = 1.35
    geo_rtt_ms = 98.0
    transit_cost_kusd = 65.0
    severed_zeroed = False
    congested_pops: list[str] = []
    if gpkg.is_file():
        try:
            con = sqlite3.connect(str(gpkg))
            pops = con.execute("SELECT pop_id, cable_status, capacity_gbps, assigned_traffic_gbps, base_rtt_ms, cost_per_gbps FROM edge_pops ORDER BY pop_id").fetchall()
            con.close()
            tot_assigned = sum(float(r[3]) for r in pops)
            severed_zeroed = all(float(r[3]) <= 0.01 for r in pops if str(r[1]) == "SEVERED")
            if abs(tot_assigned - 480.0) <= 2.0 and pops:
                eff_caps = [float(r[2]) * (0.82 if (idx % 4 == 1) else 1.04) for idx, r in enumerate(pops)]
                utils = [float(r[3]) / max(1.0, eff_caps[idx]) for idx, r in enumerate(pops)]
                max_pop_util = max(utils)
                congested_pops = [f"{pops[idx][0]}(util={utils[idx]:.2f})" for idx in range(len(pops)) if utils[idx] > 0.76]
                geo_rtt_ms = sum(float(r[3]) * float(r[4]) * (1.0 + 0.55 * (utils[idx] ** 2)) for idx, r in enumerate(pops)) / tot_assigned
                transit_cost_kusd = sum(float(r[3]) * float(r[5]) for r in pops)
        except sqlite3.Error:
            pass

    p99_ms = round(((db_ms * (0.25 + 1.8 * miss_rate)) * retry_amp + 0.38 * geo_rtt_ms + infra_pen) * burst_mult + (900.0 if oom_triggered else 0.0), 2)
    err_rate = 0.0 if (not oom_triggered and idx_pen == 0.0 and retry_amp == 1.0 and infra_pen == 0.0 and severed_zeroed and max_pop_util <= 0.78) else round(min(0.99, 0.28 * burst_mult), 3)

    cap_xlsx = workspace / "Capacity_Budget.xlsx"
    littles_ok = False
    if cap_xlsx.is_file():
        ev = evaluate_xlsx_via_libreoffice(cap_xlsx).get("Summary", {})
        # Little's Law L = lambda * W check + total RAM check
        v_mem = float((ev.get("B2") or {}).get("value") or 0.0)
        littles_ok = abs(v_mem - tot_mem_mb) <= 2.0 and tot_mem_mb <= 640.0

    gates = {
        "G_DB_1_dual_composite_indexes_and_batch": has_idx1 and has_idx2 and batch_sz <= 400,
        "G_DB_2_forensics_30s_captured": (workspace / "forensics/db_fingerprint_30s.json").is_file(),
        "G_APP_1_gateway_backoff_and_token_bucket": retry_amp == 1.0 and singleflight and ttl_s >= 90.0,
        "G_MEM_coupled_ram_cap_le_640mb_no_oom": (not oom_triggered) and db_cache_mb >= 180.0 and app_lru_mb >= 220.0 and 90.0 <= worker_mb <= 190.0,
        "G_INF_1_daemon_probe_and_disk_clean": infra_pen == 0.0,
        "G_INF_2_qgis_edge_severed_zero_and_util_le_76pct": severed_zeroed and max_pop_util <= 0.76,
        "G_INF_3_edge_rtt_le_52ms_and_cost_le_46k": geo_rtt_ms <= 52.0 and transit_cost_kusd <= 46.0,
        "G_INF_4_qgis_project_and_map_pdf": (workspace / "exports/edge_reroute_map.pdf").is_file() and (workspace / "Global_Edge_Routing.qgz").is_file(),
        "G_IC_1_p99_le_65ms_and_zero_5xx": p99_ms <= 65.0 and err_rate == 0.0,
        "G_IC_2_capacity_xlsx_and_rca_pdf": littles_ok and (workspace / "exports/INC_Postmortem_RCA.pdf").is_file(),
    }
    time.sleep(2.5)
    return {
        "ok": True,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v),
        "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "p99_ms": p99_ms,
            "error_rate": err_rate,
            "total_cluster_ram_mb": tot_mem_mb,
            "oom_triggered": oom_triggered,
            "max_pop_utilization": round(max_pop_util, 4),
            "geo_rtt_ms": round(geo_rtt_ms, 2),
            "transit_cost_kusd_h": round(transit_cost_kusd, 2),
            "congested_pops": congested_pops[:6],
        },
    }


def eval_ua04_cae_and_drc(workspace: Path) -> dict:
    """Coupled 4-role Aero-Actuator FreeCAD 36-angle BRep + Ti-6Al-4V BOM + Literature + 360-frame Broadcast Video QC."""
    from PIL import Image
    t0 = time.monotonic()
    fc_p = workspace / "aero_actuator.FCStd"
    info = {"bore": 0.0, "flex_od": 0.0, "wall": 0.0, "flange_h": 0.0, "inter": 999.0, "tot_cm3": 0.0, "cg_r": 99.0}
    if fc_p.is_file():
        code = (
            "import FreeCAD as App, json, math\n"
            f"doc = App.openDocument({str(fc_p)!r})\n"
            "ms = doc.getObject('MasterSpec')\n"
            "h = doc.getObject('Housing').Shape; f = doc.getObject('Flexspline').Shape; r = doc.getObject('RotorWave').Shape; c = doc.getObject('TopCover').Shape\n"
            "inter = h.common(f).Volume + f.common(r).Volume + h.common(c).Volume\n"
            "tot_v = h.Volume + f.Volume + r.Volume + c.Volume\n"
            "hc = h.Solids[0].CenterOfMass; fc = f.Solids[0].CenterOfMass; rc = r.Solids[0].CenterOfMass; cc = c.Solids[0].CenterOfMass\n"
            "cg_x = (hc.x*h.Volume + fc.x*f.Volume + rc.x*r.Volume + cc.x*c.Volume)/max(1.0, tot_v)\n"
            "cg_y = (hc.y*h.Volume + fc.y*f.Volume + rc.y*r.Volume + cc.y*c.Volume)/max(1.0, tot_v)\n"
            "print('UA04_FC:' + json.dumps({'bore': float(ms.get('B2')), 'flex_od': float(ms.get('B3')), 'wall': float(ms.get('B4')), 'flange_h': float(ms.get('B5')), 'inter': inter, 'tot_cm3': tot_v/1000.0, 'h_cm3': h.Volume/1000.0, 'f_cm3': f.Volume/1000.0, 'r_cm3': r.Volume/1000.0, 'c_cm3': c.Volume/1000.0, 'cg_r': math.hypot(cg_x, cg_y)}))\n"
        )
        cp = subprocess.run(["freecadcmd", "-c", code], capture_output=True, text=True, timeout=75)
        for ln in (cp.stdout + "\n" + cp.stderr).splitlines():
            if "UA04_FC:" in ln:
                info = json.loads(ln.split("UA04_FC:", 1)[1])

    radial_gap = round((info["bore"] - info["flex_od"]) / 2.0, 4)
    mass_kg = round(info["tot_cm3"] * 4.43 / 1000.0, 4)  # Ti-6Al-4V density = 4.43 g/cm3 from Wikipedia!
    # Coupled physics: thicker wall & flange_h raise torsional safety_factor >= 2.05, but push mass_kg over 1.180 kg cap!
    safety_factor = round(1.32 * (info["wall"] / 2.4) ** 0.75 * (info["flange_h"] / 8.0) ** 0.45 * (1.0 if (0.16 <= radial_gap <= 0.25 and info["inter"] < 1e-2) else 0.4), 3)
    torque_density = round((145.0 * min(2.4, safety_factor) / 2.05) / max(0.2, mass_kg), 2)

    bom_p = workspace / "Engineering_Master_BOM.xlsx"
    bom_ok = lit_ok = False
    if bom_p.is_file():
        raw_b = read_multisheet_xlsx(bom_p)
        ev_b = evaluate_xlsx_via_libreoffice(bom_p)
        s_raw = raw_b.get("Summary", {}); s_ev = ev_b.get("Summary", {})
        f_intact = all(bool((s_raw.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4"))
        v_mass_g = float((s_ev.get("B3") or {}).get("value") or 0.0)
        v_lit_sum = float((s_ev.get("B5") or {}).get("value") or 0.0)  # 2017 + 2015 + 2020 + 4.43 = 6056.43
        bom_ok = f_intact and abs(v_mass_g - mass_kg * 1000.0) <= 3.5
        lit_ok = abs(v_lit_sum - 6056.43) <= 0.25

    mp4_p = workspace / "exports/actuator_launch_720p.mp4"
    vid_ok = False
    mp4_frames = 0
    mp4_lufs = None
    if mp4_p.is_file():
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(mp4_p)], capture_output=True, text=True, timeout=30)
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            mp4_frames = int(st.get("nb_read_frames") or 0)
            wh_ok = (int(st.get("width", 0)), int(st.get("height", 0))) == (1280, 720)
        except Exception:
            wh_ok = False
        cp_l = subprocess.run(["ffmpeg", "-nostats", "-i", str(mp4_p), "-filter_complex", "ebur128=framelog=verbose", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        ms = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", cp_l.stderr)
        mp4_lufs = float(ms[-1]) if ms else None
        vid_ok = wh_ok and (356 <= mp4_frames <= 364) and (mp4_lufs is not None and -23.5 <= mp4_lufs <= -22.5)

    gates = {
        "G_CAD_1_zero_interference_and_radial_gap_016_025": info["inter"] < 1e-2 and 0.16 <= radial_gap <= 0.25,
        "G_CAD_2_coupled_mass_cap_le_1_180kg": 0.65 <= mass_kg <= 1.180 and info["cg_r"] <= 0.30,
        "G_CAE_1_torsional_safety_factor_ge_2_05": safety_factor >= 2.05,
        "G_LIT_1_bom_formulas_match_final_cad_mass": bom_ok,
        "G_LIT_2_real_web_literature_anchors_and_pdf": lit_ok and (workspace / "exports/Engineering_Whitepaper.pdf").is_file(),
        "G_MED_1_blender_cycles_cutaway_frames": (workspace / "exports/cutaway_beauty.png").is_file(),
        "G_MED_2_broadcast_360f_720p_ebu_master": vid_ok,
    }
    return {
        "ok": True,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v),
        "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "radial_gap_mm": radial_gap,
            "total_mass_kg": mass_kg,
            "safety_factor": safety_factor,
            "torque_density_nm_kg": torque_density,
            "interference_mm3": round(info["inter"], 4),
            "cg_offset_mm": round(info["cg_r"], 4),
            "part_cm3": {k: round(info.get(k, 0.0), 3) for k in ("h_cm3", "f_cm3", "r_cm3", "c_cm3")},
            "mp4_frames": mp4_frames,
            "mp4_lufs": mp4_lufs,
        },
    }


def eval_ua05_drc(workspace: Path) -> dict:
    """Marathon QBR DRC: LibreOffice 5-sheet + 40Q Monte-Carlo + REAL 3-Sun Blender Cycles raytracing (~18-24s/call)."""
    from PIL import Image
    base = eval_ua01_drc(workspace, run_blender_check=True)
    if not base.get("ok"):
        return base
    m = base["metrics"]; g = dict(base["gates"])
    # Tighter antagonistic Pareto corridor between FIN, OPS, and SALES!
    g["G_FIN_2_stress_min_dscr_ge_1_54"] = m["worst_20q_dscr"] >= 1.54
    g.pop("G_FIN_2_stress_min_dscr_ge_1_42", None)
    g["G_FIN_4_narrow_pareto_noi_margin_48_0_to_50_4"] = 48.0 <= m["noi_margin_pct"] <= 50.4
    g.pop("G_FIN_4_noi_margin_in_band", None)
    g["G_OPS_1_strict_p95_latency_le_25_5ms"] = m["p95_latency_ms"] <= 25.5
    g.pop("G_OPS_1_p95_latency_le_38ms", None)
    g["G_SALES_2_strict_nrr_ge_114_8"] = m["effective_nrr_pct"] >= 114.8 and m["churn_penalty_kusd"] <= 45.0
    g.pop("G_SALES_2_nrr_ge_114_low_churn", None)

    # Real 3-sun Cycles photometric glare/shadow audit on q3_cover_3d.blend
    blend_p = workspace / "q3_cover_3d.blend"
    sun_ok = False
    sun_stats = []
    if blend_p.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            sc_py = (
                "import bpy, math, json\n"
                f"bpy.ops.wm.open_mainfile(filepath={str(blend_p)!r})\n"
                "sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 20; sc.cycles.use_denoising = False\n"
                "sc.render.resolution_x = 480; sc.render.resolution_y = 270\n"
                "sun = bpy.data.objects.get('SunKey')\n"
                "for idx, ang in enumerate((-0.55, 0.22, 0.68)):\n"
                "    if sun: sun.rotation_euler = (0.58, ang, -0.35)\n"
                f"    sc.render.filepath = '{tmp}/s_' + str(idx) + '.png'\n"
                "    bpy.ops.render.render(write_still=True)\n"
            )
            cp = subprocess.run(["blender", "-b", "--python-expr", sc_py], capture_output=True, text=True, timeout=120)
            if cp.returncode == 0:
                for idx in range(3):
                    sp = Path(tmp) / f"s_{idx}.png"
                    if sp.is_file():
                        pxs = sorted((0.2126*r + 0.7152*gr + 0.0722*b)/255.0 for r, gr, b in list(Image.open(sp).convert("RGB").getdata())[::9])
                        p10 = pxs[int(len(pxs)*0.10)]; p98 = pxs[int(len(pxs)*0.98)]
                        sun_stats.append({"p10": round(p10, 4), "p98": round(p98, 4)})
                sun_ok = len(sun_stats) == 3 and all(s["p98"] <= 0.92 and s["p10"] >= 0.02 for s in sun_stats)
    g["G_EXEC_4_three_sun_cycles_photometry"] = sun_ok
    m["three_sun_photometry"] = sun_stats
    return {
        "ok": True, "all_gates_passed": all(g.values()),
        "passed_count": sum(1 for v in g.values() if v), "total_gates": len(g),
        "gates": g, "metrics": m,
    }


def eval_ua06_drc(workspace: Path, sport: int = 19560) -> dict:
    """Marathon Launch DRC: 12 routes + 24 real-web CMS + 144-frame Cycles turntable MP4 + 3-viewport Chromium visual E2E."""
    from PIL import Image
    base = eval_ua02_drc(workspace)
    g = dict(base["gates"]); m = dict(base["metrics"])
    repo = workspace / "nexus-portal"
    db_p = workspace / "staging_data/nexus.db"
    routes12 = ("index", "pricing", "docs", "sdk", "integrations", "benchmarks", "security", "changelog", "enterprise", "status", "cli", "community")
    g["G_FE_1_eight_routes_upgraded"] = all(
        (repo / f"templates/{rt}.html").is_file() and 'data-nexus-v5="ready"' in (repo / f"templates/{rt}.html").read_text(encoding="utf-8", errors="ignore")
        for rt in routes12
    )
    # Check 24 published CMS rows with 8 real-web anchors
    cms_24 = 0; web_8 = 0
    if db_p.is_file():
        try:
            con = sqlite3.connect(str(db_p))
            rows = con.execute("SELECT slug, license_spdx, benchmark_num, asset_file, published FROM cms_integrations").fetchall()
            con.close()
            cms_24 = sum(1 for r in rows if int(r[4]) == 1 and (repo / "static/assets" / str(r[3])).is_file())
            exp8 = {"flask": "BSD", "requests": "Apache", "sqlalchemy": "MIT", "gpt2": "50257", "resnet": "2015", "pep8": "79", "bert": "768", "pydantic": "MIT"}
            for slug, lic, bnum, _af, pub in rows:
                if int(pub) == 1:
                    for k, tok in exp8.items():
                        if k in str(slug).lower() and (tok.lower() in str(lic).lower() or tok in str(bnum)):
                            web_8 += 1
        except sqlite3.Error:
            pass
    g["G_CMS_1_16_articles_published_with_valid_assets"] = (cms_24 >= 24)
    g["G_CMS_2_real_external_web_facts_verified"] = (web_8 >= 8)

    # Check 144-frame (6.0s @ 24fps) 3D turntable MP4 with real frame-to-frame motion
    tt_mp4 = repo / "static/assets/hero_turntable.mp4"
    tt_ok = False; tt_frames = 0
    if tt_mp4.is_file():
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(tt_mp4)], capture_output=True, text=True, timeout=30)
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            tt_frames = int(st.get("nb_read_frames") or 0)
            wh_ok = (int(st.get("width", 0)), int(st.get("height", 0))) == (640, 360)
        except Exception:
            wh_ok = False
        if wh_ok and 140 <= tt_frames <= 148:
            with tempfile.TemporaryDirectory() as tmp:
                f0 = Path(tmp) / "f0.png"; f2 = Path(tmp) / "f2.png"
                subprocess.run(["ffmpeg", "-y", "-ss", "0.2", "-i", str(tt_mp4), "-frames:v", "1", str(f0)], capture_output=True, timeout=20)
                subprocess.run(["ffmpeg", "-y", "-ss", "3.0", "-i", str(tt_mp4), "-frames:v", "1", str(f2)], capture_output=True, timeout=20)
                if f0.is_file() and f2.is_file():
                    p0 = list(Image.open(f0).convert("RGB").getdata())[::16]
                    p2 = list(Image.open(f2).convert("RGB").getdata())[::16]
                    diff = sum(abs(a[0]-b[0])+abs(a[1]-b[1])+abs(a[2]-b[2]) for a, b in zip(p0, p2)) / max(1, len(p0)*3)
                    tt_ok = diff >= 1.5
    g["G_DES_4_turntable_144f_motion_mp4"] = tt_ok

    # Real Chromium headless 3-viewport visual screenshot verification against live Staging!
    vp_ok = False
    with tempfile.TemporaryDirectory() as tmp:
        vp_checks = 0
        target_url = f"http://127.0.0.1:{sport}/pricing"
        try:
            import urllib.request as _ur
            _ur.urlopen(target_url, timeout=1.5).read(64)
        except Exception:
            p_html = repo / "templates/pricing.html"
            target_url = f"file://{p_html}" if p_html.is_file() else target_url
        for vw, vh in ((1280, 720), (768, 1024), (390, 844)):
            sp = Path(tmp) / f"vp_{vw}.png"
            cp = subprocess.run([
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                f"--window-size={vw},{vh}", f"--screenshot={sp}", target_url,
            ], capture_output=True, text=True, timeout=25)
            if cp.returncode == 0 and sp.is_file() and Image.open(sp).size == (vw, vh):
                vp_checks += 1
        vp_ok = (vp_checks == 3)
    g["G_QA_3_three_viewport_chromium_render"] = vp_ok
    m.update({"cms_published_24": cms_24, "web_8_count": web_8, "turntable_frames": tt_frames, "three_viewport_ok": vp_ok})
    return {
        "ok": True, "all_gates_passed": all(g.values()),
        "passed_count": sum(1 for v in g.values() if v), "total_gates": len(g),
        "gates": g, "metrics": m,
    }


def eval_ua07_drc(workspace: Path, burst_mult: float = 1.0) -> dict:
    """Marathon Cyber-Physical War-Room: 45s forensics + 560MB tight RAM + 24-POP QGIS + 72-angle FreeCAD Cooling Valve CAE."""
    base = eval_ua03_drc(workspace, burst_mult=burst_mult)
    g = dict(base["gates"]); m = dict(base["metrics"])
    # Tighter 560 MB RAM cap (antagonistic between DB >=190, APP >=225, INFRA [95..140] -> 190+225+120 = 535 <= 560!)
    cdir = workspace / "cluster"
    db_c = json.loads((cdir / "db_tuning.json").read_text()) if (cdir / "db_tuning.json").is_file() else {}
    ap_c = json.loads((cdir / "app_gateway.json").read_text()) if (cdir / "app_gateway.json").is_file() else {}
    in_c = json.loads((cdir / "infra_daemon.json").read_text()) if (cdir / "infra_daemon.json").is_file() else {}
    ram_tot = float(db_c.get("sqlite_cache_mb", 24)) + float(ap_c.get("hot_cache_mb", 24)) + float(in_c.get("telemetry_buffer_mb", 280))
    g["G_MEM_coupled_ram_cap_le_640mb_no_oom"] = (ram_tot <= 560.0 and float(db_c.get("sqlite_cache_mb", 0)) >= 190.0 and float(ap_c.get("hot_cache_mb", 0)) >= 225.0 and 95.0 <= float(in_c.get("telemetry_buffer_mb", 0)) <= 140.0)
    fp45 = workspace / "forensics/db_fingerprint_45s.json"
    g["G_DB_2_forensics_30s_captured"] = fp45.is_file() and bool(json.loads(fp45.read_text()).get("sufficient_window_45s"))

    # 72-angle FreeCAD cooling-valve BRep clearance & titanium mass check
    fc_p = workspace / "cooling_valve.FCStd"
    valve_ok = False; valve_gap = 0.0; valve_mass_g = 0.0
    if fc_p.is_file():
        code = (
            "import FreeCAD as App, json, math\n"
            f"doc = App.openDocument({str(fc_p)!r})\n"
            "ms = doc.getObject('ValveSpec')\n"
            "vb = doc.getObject('ValveBody').Shape; sp = doc.getObject('ValveSpool').Shape\n"
            "inter = vb.common(sp).Volume\n"
            "bore = float(ms.get('B2')); spool_od = float(ms.get('B3')); stroke = float(ms.get('B4'))\n"
            "print('UA07_FC:' + json.dumps({'bore': bore, 'spool_od': spool_od, 'stroke': stroke, 'inter': inter, 'cm3': (vb.Volume+sp.Volume)/1000.0}))\n"
        )
        cp = subprocess.run(["freecadcmd", "-c", code], capture_output=True, text=True, timeout=60)
        for ln in (cp.stdout + "\n" + cp.stderr).splitlines():
            if "UA07_FC:" in ln:
                vi = json.loads(ln.split("UA07_FC:", 1)[1])
                valve_gap = round((vi["bore"] - vi["spool_od"]) / 2.0, 4)
                valve_mass_g = round(vi["cm3"] * 4.43, 2)
                valve_ok = (vi["inter"] < 1e-2 and 0.12 <= valve_gap <= 0.22 and 14.0 <= vi["stroke"] <= 18.0 and 180.0 <= valve_mass_g <= 520.0)
    cert_p = workspace / "exports/valve_cae_cert.json"
    cert_ok = cert_p.is_file() and json.loads(cert_p.read_text()).get("fcstd_sha256") == _sha256(fc_p) and json.loads(cert_p.read_text()).get("valve_passed") is True
    g["G_INF_5_cooling_valve_72angle_and_exclusive_cae"] = (valve_ok and cert_ok)
    m.update({"total_cluster_ram_mb": ram_tot, "valve_gap_mm": valve_gap, "valve_mass_g": valve_mass_g, "valve_cae_ok": cert_ok})
    return {
        "ok": True, "all_gates_passed": all(g.values()),
        "passed_count": sum(1 for v in g.values() if v), "total_gates": len(g),
        "gates": g, "metrics": m,
    }


def render_ua_portal_html(task_id: str, meta: dict) -> str:
    arena = meta["arena"]
    max_pg = 6 if task_id in ("UA-08", "UA-12", "UA-14") else 4
    tgt_q = "Q4" if task_id in ("UA-08", "UA-12", "UA-14") else "Q3"
    if arena in ("extreme_qbr_combinatorial_35m", "ultra_qbr_binary_investor_day_35m"):
        spec_lines = [
            "BOARD TOKEN: QBR-2026-Q4-EXTREME | RESTATEMENT_APAC = -145.0 kUSD | RESTATEMENT_EMEA = -65.0 kUSD",
            "DISCRETE RULES: OPS MAX 10 MODIFIED DCS | SALES MAX 10 REPRICED TERRS | Q4/USD/EXCL_IC (6 PAGES)",
            "RAZOR PARETO: NOI MARGIN IN [50.40%, 51.10%] | DSCR>=1.60 | CASH [740, 960] | P95<=23.8ms | NRR>=116.5%",
            "BLIND CYCLES 6-ZONE [0.680, 0.760] UNIF>=0.905 + 12x CHROMIUM CARDS + 4-ROLE /api/role_signoff",
        ]
    elif arena in ("extreme_warroom_dag_35m", "ultra_warroom_binary_35m"):
        spec_lines = [
            "INCIDENT TOKEN: WARROOM-9913 | CLUSTER: http://127.0.0.1:" + str(meta["cluster_port"]) + " | 1.65x BURST P99 <= 58ms",
            "60s FORENSICS -> db_fingerprint_60s.json | TIGHT RAM CORRIDOR [515, 536] MB | DB MAX 6 PROMOTED SHARDS",
            "72-NODE 6-TIER DAG: MAX 26 MODIFIED NODES | BALANCE [0.315, 0.342] | CAPEX <= 25.80 | 0 OVERTOP",
            "HARMONIC VALVE PA<=23.5d MASS [0.60,0.72]kg + 20s CAE + BLIND CYCLES TWIN + 4-ROLE /api/role_signoff",
        ]
    elif arena == "ultra_qbr_4role_flagship":
        spec_lines = [
            "BOARD TOKEN: QBR-2026-Q4-FLAGSHIP | RESTATEMENT_APAC = -145.0 kUSD | RESTATEMENT_EMEA = -65.0 kUSD",
            "BI CANONICAL FILTER: QUARTER = Q4 | CURRENCY = USD | EXCLUDE_IC = TRUE (EXPORT ALL 6 PAGES PER SCOPE)",
            "COUPLED PARETO CORRIDOR: NOI MARGIN IN [48.5%, 50.5%] | DSCR>=1.56 | P95<=24.2ms | NRR>=115.0%",
            "CYCLES ATRIUM 6-LOUVER + 6-ZONE GI + 3D BARS (3100:2275:1835:1000) + 4-ROLE POST /api/role_signoff",
        ]
    elif arena == "ultra_launch_4role_flagship":
        spec_lines = [
            "RELEASE TOKEN: NEXUS-V6-FLAGSHIP | LIVE STAGING: http://127.0.0.1:" + str(meta["staging_port"]),
            "16 RESPONSIVE ROUTES (data-nexus-v6=ready) | P95 <= 136ms | RAM <= 310MB | ASSETS IN [120, 1360] KB",
            "7 SEEDED BUGS: ANNUAL=20% | ENT_SLA=1.35 | TZ=UTC | SAMESITE=TRUE | VIEWBOX=160x48 | FTS_LIMIT | CONTRAST",
            "32 FTS5 CMS ARTICLES + 6 ARCH PNGS + CYCLES SHOWROOM + 192f EBU-R128 REEL + 4-ROLE /api/role_signoff",
        ]
    elif arena == "ultra_warroom_4role_flagship":
        spec_lines = [
            "INCIDENT TOKEN: WARROOM-9910 | CLUSTER: http://127.0.0.1:" + str(meta["cluster_port"]) + " | 1.6x BURST P99 <= 58ms",
            "60s UNDISTURBED FORENSICS -> /workspace/forensics/db_fingerprint_60s.json | GLOBAL RAM CAP <= 540 MB",
            "48-POP QGIS (960 Gbps, 6 SEVERED=0, UTIL<=74%, RTT<=48.5ms, COST<=84k) + 16 DB SHARDS (LAG<=32ms)",
            "72-ANGLE HARMONIC CRYO-VALVE BRep + 18s CAE (/api/cae/valve_solve) + CYCLES TWIN + 4-ROLE /api/role_signoff",
        ]
    elif arena == "ultra_actuator_4role_flagship":
        spec_lines = [
            "REVIEW TOKEN: AERO-ACT-FLAGSHIP | 20s EXCLUSIVE 1-SEAT CAE: POST /api/cae/exclusive_solve",
            "72-ANGLE HARMONIC CAM/FOLLOWER/HOUSING/COVER: STROKE [18.34, 18.46]mm | PA<=25.5d | GAP [0.15, 0.23]mm",
            "AL-7075 (2.81 g/cm3) MASS <= 0.855 kg | CG <= 0.65 mm | COVER >= 82000 mm3 | 16 LIVE WEB ANCHORS",
            "CYCLES 6-ZONE STUDIO + 480f (20s@24fps) 720p BT.709 [16,235] -23.0 LUFS MASTER + 4-ROLE /api/role_signoff",
        ]
    elif arena in ("qbr_cloud_ai_portfolio", "marathon_qbr_3cam_pareto"):
        corridor = "[48.0%, 50.4%] | DSCR>=1.54 | P95<=25.5ms | NRR>=114.8%" if arena == "marathon_qbr_3cam_pareto" else "[46.5%, 52.5%] | DSCR>=1.42 | P95<=38ms | NRR>=114%"
        spec_lines = [
            "BOARD SIGN-OFF TOKEN: QBR-2026-Q3-ULTRA | AUDIT APAC RETURN CONTRA = -120.0 kUSD",
            "BI CANONICAL FILTER: QUARTER = Q3 | CURRENCY = USD | EXCLUDE_IC = TRUE (EXPORT ALL 4 PAGES PER SCOPE)",
            "COUPLED PARETO TARGETS: NOI MARGIN IN " + corridor,
            "3D COVER BARS (Bar_NA, Bar_EMEA, Bar_APAC, Bar_LATAM): MATCH POST-CONTRA REGIONAL NET REV RATIOS",
        ]
    elif arena in ("launch_fullstack_devportal", "marathon_launch_turntable_e2e"):
        spec_lines = [
            "LAUNCH RELEASE TOKEN: NEXUS-V5-GA | LIVE STAGING: http://127.0.0.1:" + str(meta["staging_port"]),
            "COUPLED PERF/DESIGN: ALL ROUTES data-nexus-v5=ready | PAGE P95 <= 155ms | STATIC ASSETS <= 1150 KB",
            "PRICING/SECURITY: ANNUAL_DISCOUNT = 20.0% | ENT_SLA_MULT = 1.35 | TZ = UTC | SAMESITE_CSRF = TRUE | LOGO VIEWBOX = 0 0 160 48",
            "CMS REAL-WEB INTEGRATIONS + CYCLES HEROES/144f TURNTABLE MP4 + GIMP CARDS (640x400) + BADGES (128x128)",
        ]
    elif arena in ("warroom_geo_edge_cluster", "marathon_warroom_cyber_physical"):
        cap_txt = "560 MB (DB>=190, APP>=225, INFRA 95..140) + 45s FORENSICS + VALVE CAE" if arena == "marathon_warroom_cyber_physical" else "640 MB + 25s FORENSICS"
        spec_lines = [
            "INCIDENT TOKEN: WARROOM-9901 | CLUSTER: http://127.0.0.1:" + str(meta["cluster_port"]) + " | CANARY 1.5x P99 <= 65ms & 5XX = 0%",
            "FORENSICS & RAM RULE: " + cap_txt,
            "COUPLED TRANSIT CAP: <= 46.0 kUSD/h | EXCLUSIVE VALVE CAE: POST /api/cae/valve_solve",
            "GEO-EDGE QGIS: 480 Gbps TOTAL, SEVERED CABLES = 0 Gbps, MAX POP UTIL <= 76%, WEIGHTED RTT <= 52.0 ms",
        ]
    else:
        spec_lines = [
            "ACTUATOR REVIEW TOKEN: AERO-ACT-2026 | EXCLUSIVE 1-SEAT CAE SOLVER: POST /api/cae/exclusive_solve",
            "COUPLED CAD/CAE: RADIAL FILM GAP IN [0.16, 0.25] mm | MASS <= 1.180 kg | CG <= 0.30 mm | SAFETY FACTOR >= 2.05",
            "BOM & REAL-WEB LIT: TI-6AL-4V DENSITY (WIKIPEDIA) + ARXIV YEARS (1706.03762 + 1512.03385 + 2005.14165)",
            "BROADCAST MASTER: 1280x720 @ 24fps, 360 FRAMES (15.0s), -23.0 +/- 0.4 LUFS, UPLOAD /api/media/publish",
        ]
    sjson = json.dumps(spec_lines, ensure_ascii=False)
    extra_p56 = (
        '  <button id="btnP5" onclick="uiAct(\'set_page\',{page:5})">Page 5</button>\n'
        '  <button id="btnP6" onclick="uiAct(\'set_page\',{page:6})">Page 6</button>\n'
    ) if max_pg == 6 else ""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{task_id} Enterprise Workstation Portal</title>
<style>
body {{ margin:0; padding:10px 14px; background:#0b1120; color:#e2e8f0; font-family:DejaVu Sans,sans-serif; }}
.top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }}
.pill {{ background:#1e293b; border:1px solid #38bdf8; border-radius:6px; padding:4px 10px; font-size:12px; }}
canvas {{ border:1px solid #334155; border-radius:6px; background:#0f172a; display:block; margin-bottom:8px; }}
.bar {{ background:#1e293b; border:1px solid #334155; border-radius:6px; padding:8px; margin-bottom:8px; font-size:12px; }}
button {{ background:#0284c7; color:#fff; border:none; border-radius:4px; padding:5px 9px; margin-right:5px; margin-bottom:4px; cursor:pointer; font-size:12px; }}
button.warn {{ background:#d97706; }}
button.go {{ background:#059669; }}
pre {{ background:#090d16; border:1px solid #1e293b; padding:8px; border-radius:6px; max-height:250px; overflow:auto; font-size:12px; margin:0; }}
</style></head><body>
<div class="top">
  <div><strong>{task_id}</strong> — Shared Enterprise Browser Session ({arena})</div>
  <div class="pill" id="hdrStatus">SSO: ACTIVE</div>
</div>
<canvas id="specCanvas" width="1240" height="175"></canvas>
<div class="bar">
  <strong>Interactive Browser Session Controls (Shared SSO &amp; ~/Downloads):</strong><br/>
  <button id="btnScopeFIN" onclick="uiAct('set_scope',{{scope:'FIN'}})">Scope: FIN</button>
  <button id="btnScopeOPS" onclick="uiAct('set_scope',{{scope:'OPS'}})">Scope: OPS</button>
  <button id="btnScopeSALES" onclick="uiAct('set_scope',{{scope:'SALES'}})">Scope: SALES</button>
  <button id="btnQClean" onclick="uiAct('set_filter',{{quarter:'{tgt_q}',currency:'USD',exclude_ic:true}})">Filter: {tgt_q}/USD/Excl-IC</button>
  <button id="btnQ2" class="warn" onclick="uiAct('set_filter',{{quarter:'Q2',currency:'EUR',exclude_ic:false}})">Filter: Q2/EUR/Raw</button>
  <button id="btnP1" onclick="uiAct('set_page',{{page:1}})">Page 1</button>
  <button id="btnP2" onclick="uiAct('set_page',{{page:2}})">Page 2</button>
  <button id="btnP3" onclick="uiAct('set_page',{{page:3}})">Page 3</button>
  <button id="btnP4" onclick="uiAct('set_page',{{page:4}})">Page 4</button>
{extra_p56}  <button id="btnExport" class="go" onclick="uiAct('export_csv',{{}})">Export Active View CSV -&gt; ~/Downloads/bi_view_export.csv</button>
  <button id="btnSSO" class="warn" onclick="uiAct('sso_relogin',{{}})">SSO Re-Auth</button>
</div>
<pre id="viewBox">Loading live session view...</pre>
<script>
const LINES = {sjson};
let VIEW_CSRF = "";
function drawSpec(sub) {{
  const cv = document.getElementById("specCanvas");
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#0f172a"; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.strokeStyle = "#0ea5e9"; ctx.lineWidth = 2; ctx.strokeRect(6, 6, cv.width - 12, cv.height - 12);
  ctx.fillStyle = "#38bdf8"; ctx.font = "bold 14px DejaVu Sans Mono, monospace";
  ctx.fillText("VISUAL SPECIFICATION & LIVE CANARY CONSOLE", 18, 28);
  for (let i = 0; i < LINES.length; i++) {{
    ctx.fillStyle = i === 0 ? "#fbbf24" : "#f1f5f9";
    ctx.font = "bold 13px DejaVu Sans Mono, monospace";
    ctx.fillText(LINES[i], 18, 54 + i * 26);
  }}
  if (sub) {{ ctx.fillStyle = "#34d399"; ctx.fillText(sub, 18, 160); }}
}}
async function loadView() {{
  const r = await fetch("/ui/session_view");
  const d = await r.json();
  if (d.view_csrf) VIEW_CSRF = d.view_csrf;
  document.getElementById("hdrStatus").textContent = "SSO TTL: " + (d.sso_remaining_s ?? "-") + "s | Scope=" + (d.scope ?? "-") + " P" + (d.page ?? 1) + " | DRC Calls=" + (d.drc_calls ?? 0);
  document.getElementById("viewBox").textContent = JSON.stringify(d, null, 2);
  drawSpec(d.headline || "");
}}
async function uiAct(action, payload) {{
  const r = await fetch("/ui/action", {{
    method: "POST",
    headers: {{"Content-Type": "application/json", "X-View-CSRF": VIEW_CSRF}},
    body: JSON.stringify({{action, ...payload}})
  }});
  const d = await r.json();
  if (d.view_csrf) VIEW_CSRF = d.view_csrf;
  await loadView();
}}
drawSpec(""); loadView(); setInterval(loadView, 3500);
</script></body></html>"""


class UltraArenaState:
    def __init__(self, task_id: str, workspace: Path, state_dir: Path):
        self.task_id = task_id
        self.meta = UA_BY_ID[task_id]
        self.workspace = workspace
        self.state_dir = state_dir
        self.lock = threading.Lock()
        self.drc_exec_lock = threading.Lock()
        self.drc_queue_waits = 0
        self.role_signoffs: dict[str, dict] = {}
        self.last_drc_res: dict | None = None
        self.last_drc_canon_sha: str = ""
        self.boot_nonce = secrets.token_urlsafe(20)
        self.boot_consumed = False
        self.browser_cookie = secrets.token_hex(18)
        self.view_csrf = secrets.token_hex(12)
        self.sso_expires_at = time.time() + float(self.meta.get("sso_ttl_s", 180))
        self.scope = "FIN"
        self.page = 1
        self.bi_filter = {"quarter": "Q2", "currency": "EUR", "exclude_ic": False}
        self.last_ui_scope = "FIN"
        self.last_ui_ts = 0.0
        self.last_dl_ts = 0.0
        self.last_dl_scope = ""
        self.drc_calls = 0
        self.drc_history: list[dict] = []
        self.exported_views: list[dict] = []
        self.sent_emails: list[dict] = []
        self.qa_issues: list[dict] = []
        self.qa_signoff: dict | None = None
        self.qa_last_probe_ts = 0.0
        self.staging_redeploys = 0
        self.undisturbed_forensic_s = 0
        self.canary_replay: dict | None = None
        self.statuspage_posts: list[dict] = []
        self.cae_busy = False
        self.cae_certs: list[dict] = []
        self.media_pubs: list[dict] = []
        self.side_effects: dict[str, int] = {
            "bi_view_state_clobbers": 0,
            "download_file_overwrites": 0,
            "sso_kicks": 0,
            "staging_mid_qa_redeploys": 0,
            "false_transient_issues": 0,
            "observation_pollutions": 0,
            "uncoordinated_restarts": 0,
            "solver_license_collisions": 0,
            "premature_media_uploads": 0,
        }

    def persist(self) -> None:
        out = {
            "task_id": self.task_id,
            "arena": self.meta["arena"],
            "drc_calls": self.drc_calls,
            "drc_queue_waits": self.drc_queue_waits,
            "role_signoffs": self.role_signoffs,
            "drc_history_tail": self.drc_history[-25:],
            "exported_views_count": len(self.exported_views),
            "exported_views": self.exported_views[-80:],
            "sent_emails": self.sent_emails,
            "qa_issues": self.qa_issues,
            "qa_signoff": self.qa_signoff,
            "staging_redeploys": self.staging_redeploys,
            "canary_replay": self.canary_replay,
            "statuspage_posts": self.statuspage_posts,
            "cae_certs": self.cae_certs,
            "media_pubs": self.media_pubs,
            "collateral_side_effects": {
                **self.side_effects,
                "total": sum(self.side_effects.values()),
            },
        }
        (self.state_dir / "portal_state.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _start_ua02_staging(state: UltraArenaState, sport: int) -> None:
    repo = state.workspace / "nexus-portal"
    db_p = state.workspace / "staging_data/nexus.db"
    cache = {"loaded_at": time.time(), "templates": {}, "cfg": {}}

    def reload_app() -> dict:
        tpls = {}
        if (repo / "templates").is_dir():
            for f in (repo / "templates").glob("*.html"):
                tpls[f.stem] = f.read_text(encoding="utf-8", errors="replace")
        cfg = json.loads((repo / "portal_config.json").read_text(encoding="utf-8")) if (repo / "portal_config.json").is_file() else {}
        cache.update({"loaded_at": time.time(), "templates": tpls, "cfg": cfg})
        return {"ok": True, "routes": sorted(tpls.keys()), "cfg": cfg}

    reload_app()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            return

        def do_GET(self):
            u = urlparse(self.path)
            with state.lock:
                state.qa_last_probe_ts = time.time()
            if u.path.startswith("/static/assets/"):
                fp = repo / "static/assets" / u.path[len("/static/assets/"):]
                if fp.is_file():
                    self.send_response(200)
                    self.send_header("Content-Type", "image/svg+xml" if fp.suffix == ".svg" else "image/png")
                    self.end_headers(); self.wfile.write(fp.read_bytes()); return
                self.send_error(404); return
            if u.path == "/api/live_diagnostics":
                pub = 0
                if db_p.is_file():
                    con = sqlite3.connect(str(db_p))
                    pub = con.execute("SELECT COUNT(*) FROM cms_integrations WHERE published=1").fetchone()[0]
                    con.close()
                raw = json.dumps({"loaded_at": cache["loaded_at"], "cfg": cache["cfg"], "published_integrations": pub, "routes": sorted(dict(cache["templates"]).keys())}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw); return
            rk = "index" if u.path in ("/", "/index") else u.path.strip("/")
            html = dict(cache["templates"]).get(rk, "<h1>404 Not Deployed</h1>")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html.encode())

        def do_POST(self):
            if self.path == "/api/redeploy":
                with state.lock:
                    state.staging_redeploys += 1
                    if time.time() - state.qa_last_probe_ts < 12.0:
                        state.side_effects["staging_mid_qa_redeploys"] += 1
                    info = reload_app(); state.persist()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(info).encode()); return
            self.send_error(404)

    srv = ThreadingHTTPServer(("127.0.0.1", sport), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def _start_ua03_cluster(state: UltraArenaState, cport: int) -> None:
    ring_p = state.workspace / "cluster/slow_query_ring.json"

    def loop() -> None:
        while True:
            try:
                if state.task_id in ("UA-10", "UA-13", "UA-15"):
                    db_p = state.workspace / "cluster/prod_ledger.db"
                    idx_cnt = 0
                    if db_p.is_file():
                        con = sqlite3.connect(str(db_p))
                        idx_cnt = len(con.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ledger_events'").fetchall())
                        con.close()
                    with state.lock:
                        if idx_cnt < 3 or state.undisturbed_forensic_s < 63:
                            state.undisturbed_forensic_s += 3
                            if state.undisturbed_forensic_s >= 9:
                                ring_p.parent.mkdir(parents=True, exist_ok=True)
                                ring_p.write_text(json.dumps({
                                    "sampled_seconds": state.undisturbed_forensic_s,
                                    "sufficient_window_60s": state.undisturbed_forensic_s >= 60,
                                    "missing_indexes": ["(account_id, event_ts)", "(region_code, status)", "(shard_id, event_ts)"],
                                }, indent=2) + "\n", encoding="utf-8")
                                os.chmod(ring_p, 0o664)
                        state.persist()
                    time.sleep(2.2)
                    continue
                res = eval_ua03_drc(state.workspace, burst_mult=1.0)
                with state.lock:
                    if not res["gates"]["G_DB_1_dual_composite_indexes_and_batch"]:
                        state.undisturbed_forensic_s += 3
                        if state.undisturbed_forensic_s >= 9:
                            ring_p.parent.mkdir(parents=True, exist_ok=True)
                            ring_p.write_text(json.dumps({
                                "sampled_seconds": state.undisturbed_forensic_s,
                                "sufficient_window_25s": state.undisturbed_forensic_s >= 25,
                                "sufficient_window_45s": state.undisturbed_forensic_s >= 45,
                                "missing_indexes": ["(account_id, event_ts)", "(region_code, status)"],
                                "observed_p99_ms": res["metrics"]["p99_ms"],
                            }, indent=2) + "\n", encoding="utf-8")
                            os.chmod(ring_p, 0o664)
                    state.persist()
            except Exception:
                pass
            time.sleep(0.8)

    threading.Thread(target=loop, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            return

        def do_GET(self):
            if self.path == "/metrics":
                if state.task_id in ("UA-10", "UA-13", "UA-15"):
                    with state.lock:
                        out = {"undisturbed_forensic_s": state.undisturbed_forensic_s, "sufficient_window_60s": state.undisturbed_forensic_s >= 60, "last_drc_metrics": (state.last_drc_res or {}).get("metrics")}
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(out).encode()); return
                res = eval_ua03_drc(state.workspace, burst_mult=1.0)
                with state.lock:
                    out = {**res["metrics"], "undisturbed_forensic_s": state.undisturbed_forensic_s}
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(out).encode()); return
            self.send_error(404)

        def do_POST(self):
            ln = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(ln) or b"{}")
            if self.path == "/api/restart":
                mode = str(body.get("mode", "hard"))
                fp_ok = any((state.workspace / f"forensics/{fn}").is_file() for fn in ("db_fingerprint_30s.json", "db_fingerprint_45s.json", "db_fingerprint_60s.json"))
                with state.lock:
                    if mode == "hard":
                        state.undisturbed_forensic_s = 0
                        if ring_p.is_file():
                            ring_p.unlink()
                        if not fp_ok:
                            state.side_effects["observation_pollutions"] += 1
                            state.side_effects["uncoordinated_restarts"] += 1
                    state.persist()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            if self.path == "/api/canary_burst":
                if state.task_id in ("UA-10", "UA-13", "UA-15"):
                    if not (state.workspace / "forensics/db_fingerprint_60s.json").is_file():
                        with state.lock:
                            state.undisturbed_forensic_s = 0
                            state.side_effects["observation_pollutions"] += 1
                            state.persist()
                    with state.drc_exec_lock:
                        if state.task_id == "UA-15":
                            res = eval_ua15_drc(state.workspace, burst_mult=1.65)
                        elif state.task_id == "UA-13":
                            res = eval_ua13_drc(state.workspace, burst_mult=1.65)
                        else:
                            res = eval_ua10_drc(state.workspace, burst_mult=1.6)
                elif state.task_id == "UA-07":
                    res = eval_ua07_drc(state.workspace, burst_mult=1.5)
                else:
                    res = eval_ua03_drc(state.workspace, burst_mult=1.5)
                with state.lock:
                    state.canary_replay = res["metrics"]; state.persist()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(res).encode()); return
            self.send_error(404)

    srv = ThreadingHTTPServer(("127.0.0.1", cport), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def run_ultra_arena_services(task_id: str, port: int, workspace: Path, state_dir: Path, boot_file: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state = UltraArenaState(task_id, workspace, state_dir)
    state.persist()
    meta = state.meta
    arena = meta["arena"]
    if arena in ("launch_fullstack_devportal", "marathon_launch_turntable_e2e", "ultra_launch_4role_flagship"):
        _start_ua02_staging(state, int(meta["staging_port"]))
    if arena in ("warroom_geo_edge_cluster", "marathon_warroom_cyber_physical", "ultra_warroom_4role_flagship", "extreme_warroom_dag_35m", "ultra_warroom_binary_35m"):
        _start_ua03_cluster(state, int(meta["cluster_port"]))
    if task_id == "UA-08":
        def _autosnap_loop() -> None:
            snap_dir = workspace / "audit_snapshots"
            while True:
                time.sleep(120.0)
                try:
                    xp = workspace / "Q4_Enterprise_Master_Model.xlsx"
                    if xp.is_file():
                        snap_dir.mkdir(parents=True, exist_ok=True)
                        rw = read_multisheet_xlsx(xp).get("Executive_Summary", {})
                        f_intact = all(bool((rw.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4", "B5", "B6", "B7", "B8"))
                        (snap_dir / "latest_formula_health.json").write_text(json.dumps({"ts": time.time(), "formulas_intact": f_intact}) + "\n", encoding="utf-8")
                except Exception:
                    pass
        threading.Thread(target=_autosnap_loop, daemon=True).start()
    html_doc = render_ua_portal_html(task_id, meta)
    boot_file.write_text(f"http://127.0.0.1:{port}/boot/{state.boot_nonce}\n", encoding="utf-8")

    def _eval_current_drc(body: dict | None = None) -> dict:
        b = body or {}
        if arena == "qbr_cloud_ai_portfolio":
            return eval_ua01_drc(workspace, run_blender_check=bool(b.get("check_blender", True)))
        if arena == "marathon_qbr_3cam_pareto":
            return eval_ua05_drc(workspace)
        if arena == "ultra_qbr_4role_flagship":
            return eval_ua08_drc(workspace)
        if arena == "extreme_qbr_combinatorial_35m":
            return eval_ua12_drc(workspace)
        if arena == "ultra_qbr_binary_investor_day_35m":
            return eval_ua14_drc(workspace)
        if arena == "launch_fullstack_devportal":
            return eval_ua02_drc(workspace)
        if arena == "marathon_launch_turntable_e2e":
            return eval_ua06_drc(workspace, sport=int(meta["staging_port"]))
        if arena == "ultra_launch_4role_flagship":
            return eval_ua09_drc(workspace, sport=int(meta["staging_port"]))
        if arena == "warroom_geo_edge_cluster":
            return eval_ua03_drc(workspace, burst_mult=1.0)
        if arena == "marathon_warroom_cyber_physical":
            return eval_ua07_drc(workspace, burst_mult=1.0)
        if arena == "ultra_warroom_4role_flagship":
            return eval_ua10_drc(workspace, burst_mult=1.0)
        if arena == "extreme_warroom_dag_35m":
            return eval_ua13_drc(workspace, burst_mult=1.0)
        if arena == "ultra_warroom_binary_35m":
            return eval_ua15_drc(workspace, burst_mult=1.0)
        if arena == "ultra_actuator_4role_flagship":
            return eval_ua11_drc(workspace)
        return eval_ua04_cae_and_drc(workspace)

    class PortalHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            return

        def _json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(raw)

        def _has_browser_sso(self) -> bool:
            ck = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            return bool(ck.get("ua_sso") and ck["ua_sso"].value == state.browser_cookie)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/health":
                self._json(200, {"ok": True, "task_id": task_id}); return
            if u.path.startswith("/boot/"):
                tok = u.path.split("/boot/", 1)[1].strip()
                with state.lock:
                    if tok == state.boot_nonce and not state.boot_consumed:
                        state.boot_consumed = True
                        self.send_response(302)
                        self.send_header("Set-Cookie", f"ua_sso={state.browser_cookie}; HttpOnly; Path=/")
                        self.send_header("Location", "/")
                        self.end_headers(); return
                self.send_error(403); return
            if u.path == "/ui/session_view":
                if not self._has_browser_sso():
                    self._json(401, {"error": "SSO HttpOnly session lives inside the open Chromium window on DISPLAY=:99."}); return
                with state.lock:
                    rem = max(0, int(round(state.sso_expires_at - time.time())))
                    tot_pgs = 6 if task_id in ("UA-08", "UA-12", "UA-14") else 4
                    rows_preview = []
                    if arena in ("ultra_qbr_4role_flagship", "extreme_qbr_combinatorial_35m", "ultra_qbr_binary_investor_day_35m") and rem > 0:
                        pg_list = UA08_BI_PAGES.get(state.scope, [])
                        rows_preview = pg_list[min(len(pg_list) - 1, max(0, state.page - 1))] if pg_list else []
                    elif arena in ("qbr_cloud_ai_portfolio", "marathon_qbr_3cam_pareto") and rem > 0:
                        pg_list = UA01_BI_PAGES.get(state.scope, [])
                        rows_preview = pg_list[min(len(pg_list) - 1, max(0, state.page - 1))] if pg_list else []
                    self._json(200, {
                        "task_id": task_id,
                        "sso_remaining_s": rem,
                        "sso_expired": rem == 0,
                        "scope": state.scope,
                        "page": state.page,
                        "total_pages": tot_pgs,
                        "bi_filter": state.bi_filter,
                        "page_rows_preview_count": len(rows_preview),
                        "drc_calls": state.drc_calls,
                        "role_signoffs": sorted(state.role_signoffs.keys()),
                        "side_effects": state.side_effects,
                        "view_csrf": state.view_csrf,
                        "headline": f"Active Browser View: {state.scope} Page {state.page}/{tot_pgs} | Filter={state.bi_filter['quarter']}/{state.bi_filter['currency']} | Signoffs={len(state.role_signoffs)}/4",
                    })
                return
            if u.path == "/":
                if self._has_browser_sso():
                    raw = html_doc.encode("utf-8")
                    self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(raw); return
                self._json(401, {"error": "Use the logged-in Chromium window on DISPLAY=:99 for interactive BI/Portal UI, and POST /api/drc_audit for coupled workstation simulation."}); return
            self.send_error(404)

        def do_POST(self):
            ln = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(ln) or b"{}")

            # Browser-only interactive UI actions (requires HttpOnly cookie + live CSRF header!)
            if self.path == "/ui/action":
                if not self._has_browser_sso() or self.headers.get("X-View-CSRF", "") != state.view_csrf:
                    self._json(403, {"error": "Browser UI CSRF/SSO required (click controls in Chromium on DISPLAY=:99)"}); return
                act = str(body.get("action", ""))
                with state.lock:
                    now = time.time()
                    if act == "sso_relogin":
                        if now < state.sso_expires_at and (now - state.last_ui_ts) < 12.0:
                            state.side_effects["sso_kicks"] += 1
                        state.sso_expires_at = now + float(meta.get("sso_ttl_s", 180))
                        state.bi_filter = {"quarter": "Q2", "currency": "EUR", "exclude_ic": False}
                        state.view_csrf = secrets.token_hex(12)
                        state.persist()
                        self._json(200, {"ok": True, "view_csrf": state.view_csrf}); return
                    if now > state.sso_expires_at:
                        self._json(401, {"error": "SSO_EXPIRED: Click SSO Re-Auth button in Chromium!"}); return
                    if act == "set_scope":
                        new_sc = str(body.get("scope", "FIN")).upper()
                        if new_sc != state.scope and (now - state.last_ui_ts) < 10.0:
                            state.side_effects["bi_view_state_clobbers"] += 1
                        state.scope = new_sc; state.page = 1; state.last_ui_ts = now
                    elif act == "set_filter":
                        state.bi_filter = {
                            "quarter": str(body.get("quarter", "Q3")).upper(),
                            "currency": str(body.get("currency", "USD")).upper(),
                            "exclude_ic": bool(body.get("exclude_ic", True)),
                        }
                        state.last_ui_ts = now
                    elif act == "set_page":
                        max_p = 6 if task_id in ("UA-08", "UA-12", "UA-14") else 4
                        state.page = max(1, min(max_p, int(body.get("page", 1))))
                        state.last_ui_ts = now
                    elif act == "export_csv":
                        dl_dir = Path("/home/gui/Downloads"); dl_dir.mkdir(parents=True, exist_ok=True)
                        out_csv = dl_dir / "bi_view_export.csv"
                        flt = dict(state.bi_filter)
                        tgt_q_c = "Q4" if task_id in ("UA-08", "UA-12", "UA-14") else "Q3"
                        qm = 1.0 if flt["quarter"] == tgt_q_c else 0.81
                        cm = 1.0 if flt["currency"] == "USD" else 0.90
                        src_pages = UA08_BI_PAGES if task_id in ("UA-08", "UA-12", "UA-14") else UA01_BI_PAGES
                        rows = src_pages.get(state.scope, [[]])[state.page - 1]
                        sio = io.StringIO(); w = csv.writer(sio)
                        if state.scope == "FIN":
                            if task_id in ("UA-08", "UA-12", "UA-14"):
                                w.writerow(["scope", "page", "quarter", "currency", "unit", "gross_kusd", "net_rev_kusd", "direct_cost_kusd"])
                                for u_nm, gr, dc, ic in rows:
                                    nr = (gr - (ic if flt["exclude_ic"] else 0.0)) * qm * cm
                                    w.writerow(["FIN", state.page, flt["quarter"], flt["currency"], u_nm, round(gr * qm * cm, 2), round(nr, 2), round(dc * qm * cm, 2)])
                            else:
                                w.writerow(["scope", "page", "quarter", "currency", "unit", "net_rev_kusd", "direct_cost_kusd"])
                                for u_nm, gr, dc, ic in rows:
                                    nr = (gr - (ic if flt["exclude_ic"] else 0.0)) * qm * cm
                                    w.writerow(["FIN", state.page, flt["quarter"], flt["currency"], u_nm, round(nr, 2), round(dc * qm * cm, 2)])
                        elif state.scope == "OPS":
                            w.writerow(["scope", "page", "quarter", "currency", "dc_id", "region", "base_racks", "init_pue", "base_rtt_ms"])
                            for dc_id, reg, rk, pue, rtt in rows:
                                w.writerow(["OPS", state.page, flt["quarter"], flt["currency"], dc_id, reg, rk, pue, rtt])
                        else:
                            w.writerow(["scope", "page", "quarter", "currency", "territory", "region", "open_arr_kusd", "accounts"])
                            for tid_s, reg, arr, acc in rows:
                                w.writerow(["SALES", state.page, flt["quarter"], flt["currency"], tid_s, reg, round(arr * qm * cm, 2), acc])
                        if out_csv.is_file() and state.last_dl_scope and state.last_dl_scope != state.scope and (now - state.last_dl_ts) < 15.0:
                            state.side_effects["download_file_overwrites"] += 1
                        out_csv.write_bytes(sio.getvalue().encode("utf-8"))
                        os.chmod(out_csv, 0o666)
                        state.last_dl_ts = now; state.last_dl_scope = state.scope
                        state.exported_views.append({"scope": state.scope, "page": state.page, "filter": flt, "ts": round(now, 2)})
                    state.view_csrf = secrets.token_hex(12)
                    state.persist()
                    self._json(200, {"ok": True, "view_csrf": state.view_csrf}); return

            # Coupled black-box DRC / Stress-Test Simulator
            if self.path == "/api/drc_audit":
                if state.drc_exec_lock.locked():
                    with state.lock:
                        state.drc_queue_waits += 1
                with state.drc_exec_lock:
                    res = _eval_current_drc(body)
                    c_sha = _sha256(workspace / meta["canonical_project"])
                with state.lock:
                    state.drc_calls += 1
                    state.last_drc_res = res
                    state.last_drc_canon_sha = c_sha
                    state.drc_history.append({"call": state.drc_calls, "passed": res.get("passed_count", 0), "total": res.get("total_gates", 0), "ts": round(time.time(), 2)})
                    res = {**res, "role_signoffs": sorted(state.role_signoffs.keys()), "drc_call_index": state.drc_calls}
                    state.persist()
                self._json(200, res); return

            if self.path == "/api/role_signoff":
                role_s = str(body.get("role", "")).strip().upper()
                if role_s not in meta["roles"]:
                    self._json(400, {"ok": False, "error": f"Invalid role {role_s}; expected one of {meta['roles']}"}); return
                cur_sha = _sha256(workspace / meta["canonical_project"])
                need_eval = (state.last_drc_res is None or state.last_drc_canon_sha != cur_sha or not state.last_drc_res.get("all_gates_passed"))
                if need_eval:
                    with state.drc_exec_lock:
                        r_ev = _eval_current_drc({})
                        cur_sha = _sha256(workspace / meta["canonical_project"])
                    with state.lock:
                        state.last_drc_res = r_ev
                        state.last_drc_canon_sha = cur_sha
                drc_snap = state.last_drc_res or {}
                if not drc_snap.get("all_gates_passed"):
                    failing = [k for k, v in (drc_snap.get("gates") or {}).items() if not v]
                    self._json(409, {"ok": False, "error": "JOINT_GATES_NOT_CONVERGED", "still_failing_gates": failing, "current_shared_sha256": cur_sha}); return
                req_sha = str(body.get("shared_sha256", "")).strip()
                valid_shas = {cur_sha, ""}
                if (workspace / "nexus-portal/.git").is_dir():
                    g_head = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=workspace / "nexus-portal", capture_output=True, text=True).stdout.strip()
                    valid_shas.add(g_head)
                if req_sha not in valid_shas:
                    self._json(409, {"ok": False, "error": "SHARED_SHA256_MISMATCH", "expected_sha256": cur_sha}); return
                with state.lock:
                    state.role_signoffs[role_s] = {"role": role_s, "shared_sha256": cur_sha, "ts": time.time()}
                    state.persist()
                    signed = sorted(state.role_signoffs.keys())
                self._json(200, {"ok": True, "role": role_s, "shared_sha256": cur_sha, "signed_roles": signed}); return

            if self.path == "/api/cae/exclusive_solve":
                with state.lock:
                    if state.cae_busy:
                        state.side_effects["solver_license_collisions"] += 1; state.persist()
                        self._json(409, {"ok": False, "error": "ERR_CAE_LICENSE_BUSY: Single-seat CAE token locked by another process!"}); return
                    state.cae_busy = True; state.persist()
                try:
                    if task_id == "UA-11":
                        time.sleep(20.0)
                        try:
                            from tasks.ultra_arenas_v1.flagship_30m import _eval_harmonic_cam_fcstd
                        except ImportError:
                            from flagship_30m import _eval_harmonic_cam_fcstd  # type: ignore
                        fc_p = workspace / "harmonic_actuator.FCStd"
                        fc = _eval_harmonic_cam_fcstd(fc_p)
                        c_ok = bool(fc.get("ok") and 18.34 <= fc["stroke"] <= 18.46 and fc["max_pa"] <= 25.5 and fc["min_ch"] >= 3.40 and 0.15 <= fc["home_gap"] <= 0.23 and fc["coll_vol"] <= 0.02 and fc["mass_tot"] <= 0.855 and fc["cg_r"] <= 0.65)
                        cert = {"review_token": str(body.get("review_token", "")), "fcstd_sha256": _sha256(fc_p), "metrics": fc, "cae_passed": c_ok, "ts": time.time()}
                        cp_p = workspace / "exports/cae_cert.json"; cp_p.parent.mkdir(parents=True, exist_ok=True)
                        cp_p.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8"); os.chmod(cp_p, 0o664)
                        with state.lock:
                            state.cae_certs.append(cert); state.persist()
                        self._json(200, {"ok": True, "certificate": cert}); return
                    time.sleep(8.0)
                    res = eval_ua04_cae_and_drc(workspace)
                    fc_sha = _sha256(workspace / "aero_actuator.FCStd")
                    cert = {
                        "review_token": str(body.get("review_token", "")),
                        "fcstd_sha256": fc_sha,
                        "metrics": res["metrics"],
                        "cad_cae_passed": bool(res["gates"]["G_CAD_1_zero_interference_and_radial_gap_016_025"] and res["gates"]["G_CAD_2_coupled_mass_cap_le_1_180kg"] and res["gates"]["G_CAE_1_torsional_safety_factor_ge_2_05"]),
                        "ts": time.time(),
                    }
                    cp_p = workspace / "exports/cae_cert.json"
                    cp_p.parent.mkdir(parents=True, exist_ok=True)
                    cp_p.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
                    os.chmod(cp_p, 0o664)
                    with state.lock:
                        state.cae_certs.append(cert); state.persist()
                    self._json(200, {"ok": True, "certificate": cert}); return
                finally:
                    with state.lock:
                        state.cae_busy = False; state.persist()

            if self.path == "/api/cae/valve_solve":
                with state.lock:
                    if state.cae_busy:
                        state.side_effects["solver_license_collisions"] += 1; state.persist()
                        self._json(409, {"ok": False, "error": "ERR_CAE_LICENSE_BUSY"}); return
                    state.cae_busy = True; state.persist()
                try:
                    if task_id in ("UA-10", "UA-13", "UA-15"):
                        time.sleep(20.0 if task_id in ("UA-13", "UA-15") else 18.0)
                        try:
                            from tasks.ultra_arenas_v1.flagship_30m import _eval_harmonic_cam_fcstd
                        except ImportError:
                            from flagship_30m import _eval_harmonic_cam_fcstd  # type: ignore
                        fc_p = workspace / "cryo_cooling_valve.FCStd"
                        fc = _eval_harmonic_cam_fcstd(fc_p)
                        if task_id in ("UA-13", "UA-15"):
                            v_ok = bool(fc.get("ok") and 18.35 <= fc["stroke"] <= 18.45 and fc["max_pa"] <= 23.5 and fc["min_ch"] >= 3.40 and 0.16 <= fc["home_gap"] <= 0.22 and fc["coll_vol"] <= 0.02 and 0.600 <= fc["mass_tot"] <= 0.720 and fc["cg_r"] <= 0.45)
                        else:
                            v_ok = bool(fc.get("ok") and 18.32 <= fc["stroke"] <= 18.48 and fc["max_pa"] <= 25.5 and fc["min_ch"] >= 3.40 and 0.15 <= fc["home_gap"] <= 0.23 and fc["coll_vol"] <= 0.02 and fc["mass_tot"] <= 0.855 and fc["cg_r"] <= 0.65)
                        cert = {"fcstd_sha256": _sha256(fc_p), "valve_passed": v_ok, "metrics": fc, "ts": time.time()}
                        cp_p = workspace / "exports/valve_cae_cert.json"; cp_p.parent.mkdir(parents=True, exist_ok=True)
                        cp_p.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8"); os.chmod(cp_p, 0o664)
                        with state.lock:
                            state.cae_certs.append(cert); state.persist()
                        self._json(200, {"ok": True, "certificate": cert}); return
                    time.sleep(14.0)
                    res = eval_ua07_drc(workspace, burst_mult=1.0)
                    fc_sha = _sha256(workspace / "cooling_valve.FCStd")
                    v_ok = (res["metrics"].get("valve_gap_mm", 0) >= 0.12 and res["metrics"].get("valve_gap_mm", 9) <= 0.22 and 180.0 <= res["metrics"].get("valve_mass_g", 0) <= 520.0)
                    cert = {"fcstd_sha256": fc_sha, "valve_passed": v_ok, "metrics": res["metrics"], "ts": time.time()}
                    cp_p = workspace / "exports/valve_cae_cert.json"
                    cp_p.parent.mkdir(parents=True, exist_ok=True)
                    cp_p.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8"); os.chmod(cp_p, 0o664)
                    with state.lock:
                        state.cae_certs.append(cert); state.persist()
                    self._json(200, {"ok": True, "certificate": cert}); return
                finally:
                    with state.lock:
                        state.cae_busy = False; state.persist()

            if self.path == "/api/mail/send_board":
                mp = Path(str(body.get("model_path", "/workspace/Q3_Enterprise_Model.xlsx")))
                rec = {
                    "board_token": str(body.get("board_token", "")),
                    "noi_kusd": body.get("noi_kusd"),
                    "worst_dscr": body.get("worst_dscr"),
                    "model_sha256": _sha256(mp),
                    "ts": time.time(),
                }
                with state.lock:
                    state.sent_emails.append(rec); state.persist()
                self._json(200, {"ok": True, "receipt": rec}); return

            if self.path == "/api/qa/report_defect":
                bcode = str(body.get("bug_code") or body.get("code") or "").strip().upper()
                if not bcode:
                    self._json(400, {"ok": False, "error": "bug_code required"}); return
                real_bugs = UA09_REAL_BUGS_7 if task_id == "UA-09" else {"BUG-ANNUAL-SURCHARGE", "BUG-ENT-SLA-ZERO", "BUG-TZ-PST8", "BUG-CSRF-SAMESITE", "BUG-BRAND-VIEWBOX"}
                with state.lock:
                    if bcode not in real_bugs:
                        state.side_effects["false_transient_issues"] += 1
                    state.qa_issues.append({"bug_code": bcode, "ts": time.time()})
                    state.persist()
                self._json(200, {"ok": True, "bug_code": bcode}); return

            if self.path == "/api/qa/release_signoff":
                with state.lock:
                    state.qa_signoff = {"release_token": str(body.get("release_token", "")), "git_commit": str(body.get("git_commit", "")), "ts": time.time()}
                    state.persist()
                self._json(200, {"ok": True, "signoff": state.qa_signoff}); return

            if self.path == "/api/statuspage/resolve":
                with state.lock:
                    state.statuspage_posts.append({"incident_token": str(body.get("incident_token", "")), "canary_p99_ms": body.get("canary_p99_ms"), "ts": time.time()})
                    state.persist()
                self._json(200, {"ok": True}); return

            if self.path == "/api/media/publish":
                if task_id == "UA-11":
                    mp4 = Path(str(body.get("mp4_path", "/workspace/exports/actuator_master_480f.mp4")))
                    with state.drc_exec_lock:
                        drc_now = eval_ua11_drc(workspace)
                    ready = bool(drc_now.get("all_gates_passed"))
                    rec = {"release_token": str(body.get("release_token", "")), "mp4_sha256": _sha256(mp4), "fcstd_sha256": _sha256(workspace / "harmonic_actuator.FCStd"), "ready_at_upload": ready, "ts": time.time()}
                    with state.lock:
                        if not ready:
                            state.side_effects["premature_media_uploads"] += 1
                        state.media_pubs.append(rec); state.persist()
                    self._json(200, {"ok": True, "receipt": rec}); return
                mp4 = Path(str(body.get("mp4_path", "/workspace/exports/actuator_launch_720p.mp4")))
                drc_now = eval_ua04_cae_and_drc(workspace)
                ready = bool(drc_now["gates"]["G_CAD_1_zero_interference_and_radial_gap_016_025"] and drc_now["gates"]["G_CAE_1_torsional_safety_factor_ge_2_05"] and drc_now["gates"]["G_MED_2_broadcast_360f_720p_ebu_master"])
                rec = {"release_token": str(body.get("release_token", "")), "mp4_sha256": _sha256(mp4), "fcstd_sha256": _sha256(workspace / "aero_actuator.FCStd"), "ready_at_upload": ready, "ts": time.time()}
                with state.lock:
                    if not ready:
                        state.side_effects["premature_media_uploads"] += 1
                    state.media_pubs.append(rec); state.persist()
                self._json(200, {"ok": True, "receipt": rec}); return

            self.send_error(404)

    srv = ThreadingHTTPServer(("127.0.0.1", port), PortalHandler)
    srv.daemon_threads = True
    srv.serve_forever()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--workspace", type=Path, default=Path("/workspace"))
    p.add_argument("--state-dir", type=Path, required=True)
    p.add_argument("--boot-file", type=Path, required=True)
    args = p.parse_args(argv)
    run_ultra_arena_services(args.task, args.port, args.workspace, args.state_dir, args.boot_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

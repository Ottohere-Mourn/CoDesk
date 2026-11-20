"""FC-03: Enterprise Multi-Entity Treasury & Tax Quarter-Close (Single-Session SSO BI Filters + Shared ~/Downloads CSV Canary + Live X11 Clipboard SVG + Multi-Sheet .xlsx Covenant + Executive PDF)."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    verify_stage_regime_purity,
    audit_protocol_transparency,
    post_json,
    sha256_file,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "FC-03"
PORTAL_PORT = 19430

META = {
    "id": TASK_ID,
    "title": "Enterprise Q4 Multi-Entity Treasury, BI Quarter-Close, X11 Clipboard Deck & Liquidity Covenant",
    "domain": "Enterprise FinOps / BI Analytics & Executive Publishing (SSO Chromium BI + X11 Clipboard + Shared Downloads + LibreOffice .xlsx + PDF)",
    "arena": "Single-Session SSO BI Filter/Currency Collisions, X11 Clipboard SVG Cross-Paste & Shared Board Model",
    "conflict_archetype": "sso_bi_filter_currency_hijack + shared_downloads_canary_contamination + x11_clipboard_svg_cross_paste + xlsx_covenant_coupling",
    "roles": ("revenue_treasury_lead", "ops_tax_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "Q4_Board_Model.xlsx",
    "conc_role_timeout_s": 2520,
    "seq_role_timeout_s": 2880,
}

REGIONS: tuple[str, ...] = (
    "AMER_NORTH",
    "AMER_LATAM",
    "EMEA_WEST",
    "EMEA_EAST",
    "APAC_DEV",
    "APAC_EMERG",
)

# Authoritative USD_K regional ledger figures (canary-checked to 0.1 USD_K!)
TRUE_IFRS_REVENUE_USD_K: dict[str, tuple[float, float, float]] = {
    # (gross_rev_usd_k, fx_hedge_adj_usd_k, net_rev_usd_k)
    "AMER_NORTH": (48250.0, -610.0, 47640.0),
    "AMER_LATAM": (14920.0, -485.0, 14435.0),
    "EMEA_WEST":  (36480.0,  315.0, 36795.0),
    "EMEA_EAST":  (11840.0, -290.0, 11550.0),
    "APAC_DEV":   (29760.0,  420.0, 30180.0),
    "APAC_EMERG": (18350.0, -350.0, 18000.0),
}
# Total net_rev_usd_k = 158600.0

TRUE_OPS_STATUTORY_USD_K: dict[str, tuple[float, float, float]] = {
    # (cloud_ops_usd_k, statutory_tax_usd_k, total_ops_tax_usd_k)
    "AMER_NORTH": (21400.0, 4120.0, 25520.0),
    "AMER_LATAM": ( 6850.0, 1680.0,  8530.0),
    "EMEA_WEST":  (16920.0, 3490.0, 20410.0),
    "EMEA_EAST":  ( 5430.0, 1090.0,  6520.0),
    "APAC_DEV":   (13280.0, 2740.0, 16020.0),
    "APAC_EMERG": ( 8620.0, 1780.0, 10400.0),
}
# Total ops_tax_usd_k = 87400.0; Consolidated EBITDA = 158600.0 - 87400.0 = 71200.0

REV_CANARY_TOKEN = "CANARY-REV-IFRS-88421"
OPS_CANARY_TOKEN = "CANARY-OPS-STAT-55319"

FX_HEDGE_PCT_RANGE = (38.0, 73.0)
INFRA_CAPEX_RANGE_USD_K = (15000.0, 28200.0)
COMMITTED_OUTFLOW_BAND_USD_K = (41200.0, 42800.0)
MAX_COMMITTED_OUTFLOW_USD_K = 42800.0

REV_STAGES = ("amer_reconcile", "emea_reconcile", "apac_reconcile", "fx_var_stress", "full_board_pack")
OPS_STAGES = ("amer_reconcile", "emea_reconcile", "apac_reconcile", "capex_tax_stress", "full_board_pack")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/Q4_Board_Model.xlsx",
    "/workspace/briefing/Q4_Executive_Pack.html",
    "/workspace/briefing/Q4_Executive_Pack.pdf",
    "/home/gui/Downloads/bi_region_extract.csv",
    "/api/bench/erp_covenant_audit",
    "/api/board/submit",
    "/api/board/status",
    "Revenue_FX",
    "Ops_Tax",
    "Treasury_Covenant",
    "Executive_Summary",
    "IFRS_REVENUE",
    "OPS_STATUTORY",
    "USD_K",
    "38.0",
    "73.0",
    "15000.0",
    "28200.0",
    "41200.0",
    "42800.0",
    "full_board_pack",
)


def _make_rev_rows(data_map: dict[str, tuple[float, float, float]]) -> list[list]:
    rows: list[list] = [["Region", "Gross_Rev_USD_K", "FX_Hedge_Adj_USD_K", "Net_Rev_USD_K"]]
    g_sum, a_sum, n_sum = 0.0, 0.0, 0.0
    for idx, reg in enumerate(REGIONS, start=2):
        g, a, n = data_map[reg]
        g_sum += g
        a_sum += a
        n_sum += n
        rows.append([reg, round(g, 2), round(a, 2), (f"=B{idx}+C{idx}", round(n, 2))])
    rows.append(["TOTAL", ("=SUM(B2:B7)", round(g_sum, 2)), ("=SUM(C2:C7)", round(a_sum, 2)), ("=SUM(D2:D7)", round(n_sum, 2))])
    return rows


def _make_ops_rows(data_map: dict[str, tuple[float, float, float]]) -> list[list]:
    rows: list[list] = [["Region", "Cloud_Ops_USD_K", "Statutory_Tax_USD_K", "Total_Ops_Tax_USD_K"]]
    c_sum, t_sum, tot_sum = 0.0, 0.0, 0.0
    for idx, reg in enumerate(REGIONS, start=2):
        c, t, tot = data_map[reg]
        c_sum += c
        t_sum += t
        tot_sum += tot
        rows.append([reg, round(c, 2), round(t, 2), (f"=B{idx}+C{idx}", round(tot, 2))])
    rows.append(["TOTAL", ("=SUM(B2:B7)", round(c_sum, 2)), ("=SUM(C2:C7)", round(t_sum, 2)), ("=SUM(D2:D7)", round(tot_sum, 2))])
    return rows


def _make_covenant_rows(hedge_pct: float, capex_usd_k: float) -> list[list]:
    margin_k = round(380.0 * hedge_pct, 2)
    outflow_k = round(margin_k + capex_usd_k, 2)
    return [
        ["Parameter", "Value", "Min_Allowed", "Max_Allowed"],
        ["FX_Hedge_Ratio_Pct", round(hedge_pct, 2), FX_HEDGE_PCT_RANGE[0], FX_HEDGE_PCT_RANGE[1]],
        ["Infra_CapEx_Commit_USD_K", round(capex_usd_k, 2), INFRA_CAPEX_RANGE_USD_K[0], INFRA_CAPEX_RANGE_USD_K[1]],
        ["Hedge_Margin_Cash_USD_K", ("=380*B2", margin_k), 0.0, 30000.0],
        ["Total_Committed_Outflow_USD_K", ("=B4+B3", outflow_k), COMMITTED_OUTFLOW_BAND_USD_K[0], COMMITTED_OUTFLOW_BAND_USD_K[1]],
    ]


def _make_exec_summary_rows(net_rev: float, tot_ops: float, outflow_k: float) -> list[list]:
    ebitda = round(net_rev - tot_ops, 2)
    headroom = round(MAX_COMMITTED_OUTFLOW_USD_K - outflow_k, 2)
    return [
        ["KPI", "Formula_Value", "Audit_Rule"],
        ["Total_IFRS_Net_Rev_USD_K", ("=Revenue_FX!D8", round(net_rev, 2)), "Must match 6-region IFRS_REVENUE USD_K BI sum"],
        ["Total_Ops_Tax_USD_K", ("=Ops_Tax!D8", round(tot_ops, 2)), "Must match 6-region OPS_STATUTORY USD_K BI sum"],
        ["Consolidated_EBITDA_USD_K", ("=B2-B3", ebitda), "Live cross-sheet formula =B2-B3"],
        ["Committed_Cash_Outflow_USD_K", ("=Treasury_Covenant!B5", round(outflow_k, 2)), "in [41200.0, 42800.0] USD_K"],
        ["Covenant_Headroom_USD_K", ("=42800-B5", headroom), ">= 0.0 USD_K"],
    ]


def verify_clean_workspace(workspace: Path) -> list[str]:
    allowed_root = {"Q4_Board_Model.xlsx", "briefing"}
    allowed_briefing = {"Q4_Executive_Pack.html", "Q4_Executive_Pack.pdf"}
    errs: list[str] = []
    if workspace.is_dir():
        extra_root = sorted(x.name for x in workspace.iterdir() if x.name not in allowed_root)
        if extra_root:
            errs.append(f"Unexpected non-release files/directories in /workspace: {extra_root} (use /tmp or $HOME for scratch scripts)")
    bdir = workspace / "briefing"
    if bdir.is_dir():
        extra_b = sorted(x.name for x in bdir.iterdir() if x.name not in allowed_briefing)
        if extra_b:
            errs.append(f"Unexpected non-release files in /workspace/briefing: {extra_b}")
    return errs


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Board Model, Covenant Envelope & Release Hygiene",
        f"- **Board Workbook**: {b}/workspace/Q4_Board_Model.xlsx{b} (4 worksheets: {b}Revenue_FX{b}, {b}Ops_Tax{b}, {b}Treasury_Covenant{b}, {b}Executive_Summary{b}; keep live Excel formulas in {b}D2:D8, B8:C8{b}, {b}Treasury_Covenant!B4:B5{b}, and {b}Executive_Summary!B2:B6{b}).",
        f"- **Treasury Cash-Outflow Covenant ({b}Treasury_Covenant{b})**:",
        f"  - {b}Treasury_Covenant!B2{b} ({b}FX_Hedge_Ratio_Pct{b}): **{b}[38.0, 73.0]{b}** ({b}B4 = 380 * B2{b}).",
        f"  - {b}Treasury_Covenant!B3{b} ({b}Infra_CapEx_Commit_USD_K{b}): **{b}[15000.0, 28200.0]{b}**.",
        f"  - {b}Treasury_Covenant!B5{b} ({b}Total_Committed_Outflow_USD_K = B4 + B3{b}): **{b}within [41200.0, 42800.0]{b} USD_K**.",
        f"- **Executive Briefing Deck**: {b}/workspace/briefing/Q4_Executive_Pack.html{b} rendered via headless Chromium to {b}/workspace/briefing/Q4_Executive_Pack.pdf{b} (ensure {b}#executive-kpi-banner{b} displays {b}OUTFLOW_USD_K=<Treasury_Covenant!B5 rounded to 1 decimal>{b} matching the live workbook).",
        f"- **Release Directory Hygiene**: {b}/workspace{b} is the final board packet directory and must contain ONLY {b}Q4_Board_Model.xlsx{b} and {b}briefing/Q4_Executive_Pack.{{html,pdf}}{b}. Store all helper scripts, logs, and scratch files in {b}$HOME{b} or {b}$TMPDIR{b} ({b}POST /api/board/submit{b} rejects unexpected files in {b}/workspace{b} with {b}HTTP 422{b}).",
        f"- **SSO BI Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & ERP Audit API**:",
        f"  - Use {b}desktop.screenshot{b} and {b}desktop.click{b} on the open Chromium SSO session ({b}DISPLAY=:99{b}) to configure BI filters, export regional CSVs to {b}/home/gui/Downloads/bi_region_extract.csv{b}, and copy the active SVG chart onto X11 {b}CLIPBOARD{b} ({b}xclip -selection clipboard -o{b}).",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/erp_covenant_audit{b}: progressive ordered stage verification ({b}amer_reconcile{b} -> {b}emea_reconcile{b} -> {b}apac_reconcile{b} -> stress stage -> {b}full_board_pack{b}). Update and save {b}/workspace/Q4_Board_Model.xlsx{b} at each regional stage before running that stage audit.",
        f"  - {b}GET http://127.0.0.1:{PORTAL_PORT}/api/board/status?subsystem=<subsystem>{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/board/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    rev_txt = "\n".join([
        f"# Quarter-Close Work Order — FC-03 ({b}revenue_treasury_lead{b})",
        "",
        f"Complete the Q4 6-region {b}IFRS_REVENUE{b} ({b}USD_K{b}) consolidation, FX hedge covenant sizing, and executive revenue waterfall slot.",
        "",
        "### Required Workflow",
        f"1. In the Chromium SSO BI Console ({b}DISPLAY=:99{b}), select {b}SCOPE = IFRS_REVENUE{b} and {b}CURRENCY = USD_K{b}.",
        f"2. Reconcile progressively by region group, saving {b}Revenue_FX{b} ({b}Rows 2..7{b} for {b}AMER_NORTH, AMER_LATAM, EMEA_WEST, EMEA_EAST, APAC_DEV, APAC_EMERG{b}, {b}Row 8{b} {b}TOTAL{b}) in {b}/workspace/Q4_Board_Model.xlsx{b} via {b}/home/gui/Downloads/bi_region_extract.csv{b} and qualifying each stage on {b}POST /api/bench/erp_covenant_audit{b} ({b}subsystem='revenue_treasury'{b}):",
        f"   - Stage 1: {b}amer_reconcile{b} ({b}AMER_NORTH, AMER_LATAM{b})",
        f"   - Stage 2: {b}emea_reconcile{b} ({b}EMEA_WEST, EMEA_EAST{b})",
        f"   - Stage 3: {b}apac_reconcile{b} ({b}APAC_DEV, APAC_EMERG{b})",
        f"   - Stage 4: Set {b}Treasury_Covenant!B2{b} ({b}FX_Hedge_Ratio_Pct{b}) in {b}[38.0, 73.0]{b} keeping {b}Treasury_Covenant!B5 within [41200.0, 42800.0]{b}, then run {b}fx_var_stress{b}.",
        f"3. Click {b}Copy Scope SVG to X11 Clipboard{b} in Chromium ({b}DISPLAY=:99{b}), paste {b}xclip -selection clipboard -o{b} into {b}#revenue-chart-slot{b} of {b}/workspace/briefing/Q4_Executive_Pack.html{b}, render {b}/workspace/briefing/Q4_Executive_Pack.pdf{b}, and run Stage 5 {b}full_board_pack{b}.",
        f"4. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/board/submit{b}:",
        f"   {b}{{\"subsystem\": \"revenue_treasury\", \"net_rev_total_usd_k\": <float>, \"fx_hedge_ratio_pct\": <float>, \"committed_outflow_usd_k\": <float>, \"pdf_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}IFRS_REVENUE{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    ops_txt = "\n".join([
        f"# Quarter-Close Work Order — FC-03 ({b}ops_tax_lead{b})",
        "",
        f"Complete the Q4 6-region {b}OPS_STATUTORY{b} ({b}EUR_K{b}) consolidation, infrastructure CapEx covenant sizing, and executive ops/tax waterfall slot.",
        "",
        "### Required Workflow",
        f"1. In the Chromium SSO BI Console ({b}DISPLAY=:99{b}), select {b}SCOPE = OPS_STATUTORY{b} and {b}CURRENCY = EUR_K{b}.",
        f"2. Reconcile progressively by region group, saving {b}Ops_Tax{b} ({b}Rows 2..7{b} for {b}AMER_NORTH, AMER_LATAM, EMEA_WEST, EMEA_EAST, APAC_DEV, APAC_EMERG{b}, {b}Row 8{b} {b}TOTAL{b}) in {b}/workspace/Q4_Board_Model.xlsx{b} via {b}/home/gui/Downloads/bi_region_extract.csv{b} and qualifying each stage on {b}POST /api/bench/erp_covenant_audit{b} ({b}subsystem='ops_tax'{b}):",
        f"   - Stage 1: {b}amer_reconcile{b} ({b}AMER_NORTH, AMER_LATAM{b})",
        f"   - Stage 2: {b}emea_reconcile{b} ({b}EMEA_WEST, EMEA_EAST{b})",
        f"   - Stage 3: {b}apac_reconcile{b} ({b}APAC_DEV, APAC_EMERG{b})",
        f"   - Stage 4: Set {b}Treasury_Covenant!B3{b} ({b}Infra_CapEx_Commit_USD_K{b}) in {b}[15000.0, 28200.0]{b} keeping {b}Treasury_Covenant!B5 within [41200.0, 42800.0]{b}, then run {b}capex_tax_stress{b}.",
        f"3. Click {b}Copy Scope SVG to X11 Clipboard{b} in Chromium ({b}DISPLAY=:99{b}), paste {b}xclip -selection clipboard -o{b} into {b}#ops-chart-slot{b} of {b}/workspace/briefing/Q4_Executive_Pack.html{b}, render {b}/workspace/briefing/Q4_Executive_Pack.pdf{b}, and run Stage 5 {b}full_board_pack{b}.",
        f"4. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/board/submit{b}:",
        f"   {b}{{\"subsystem\": \"ops_tax\", \"ops_tax_total_usd_k\": <float>, \"infra_capex_usd_k\": <float>, \"committed_outflow_usd_k\": <float>, \"pdf_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}OPS_STATUTORY{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"revenue_treasury_lead": rev_txt, "ops_tax_lead": ops_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "briefing").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    # Realistic v0 preliminary estimates (non-zero, pre-close Q3 carry-forward figures)
    v0_rev = {r: (round(v[0] * 0.91, 2), 0.0, round(v[0] * 0.91, 2)) for r, v in TRUE_IFRS_REVENUE_USD_K.items()}
    v0_ops = {r: (round(v[0] * 0.89, 2), round(v[1] * 0.89, 2), round((v[0] + v[1]) * 0.89, 2)) for r, v in TRUE_OPS_STATUTORY_USD_K.items()}
    v0_rev_sum = sum(x[2] for x in v0_rev.values())
    v0_ops_sum = sum(x[2] for x in v0_ops.values())
    v0_hedge = 37.0
    v0_capex = 14500.0
    v0_outflow = 380.0 * v0_hedge + v0_capex

    write_multisheet_xlsx(
        workspace / "Q4_Board_Model.xlsx",
        [
            ("Revenue_FX", _make_rev_rows(v0_rev)),
            ("Ops_Tax", _make_ops_rows(v0_ops)),
            ("Treasury_Covenant", _make_covenant_rows(v0_hedge, v0_capex)),
            ("Executive_Summary", _make_exec_summary_rows(v0_rev_sum, v0_ops_sum, v0_outflow)),
        ],
    )

    html_p = workspace / "briefing" / "Q4_Executive_Pack.html"
    html_p.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Q4 Consolidated Board Briefing Pack</title>
  <style>
    body { font-family: sans-serif; margin: 24px; color: #0f172a; }
    .slot { border: 1px solid #94a3b8; padding: 14px; margin-bottom: 18px; }
  </style>
</head>
<body>
  <h1>Q4 Consolidated Executive Briefing</h1>
  <div id="executive-kpi-banner" class="slot">OUTFLOW_USD_K=28560.0</div>
  <div id="revenue-chart-slot" class="slot">UNVERIFIED_Q3_PLACEHOLDER_REVENUE</div>
  <div id="ops-chart-slot" class="slot">UNVERIFIED_Q3_PLACEHOLDER_OPS</div>
</body>
</html>
""",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
            f"--print-to-pdf={workspace / 'briefing' / 'Q4_Executive_Pack.pdf'}",
            f"file://{html_p}",
        ],
        capture_output=True,
        timeout=30,
    )

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _build_scope_svg(scope: str, currency: str) -> str:
    import hashlib
    canary = REV_CANARY_TOKEN if (scope == "IFRS_REVENUE" and currency == "USD_K") else (
        OPS_CANARY_TOKEN if (scope == "OPS_STATUTORY" and currency == "EUR_K") else "SEAL-" + hashlib.sha256(f"{scope}:{currency}".encode()).hexdigest()[:12]
    )
    bar_w = 512 if scope == "IFRS_REVENUE" else 348
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="160" data-chart-seal="{canary}">'
        f'<rect width="640" height="160" fill="#0f172a"/>'
        f'<text x="18" y="42" fill="#38bdf8" font-family="monospace" font-size="15">Q4 Regional Consolidation Waterfall</text>'
        f'<rect x="18" y="74" width="{bar_w}" height="28" fill="#0284c7"/>'
        f'<text x="18" y="132" fill="#94a3b8" font-family="monospace" font-size="11">Audit Digest: {canary}</text>'
        f'</svg>'
    )


def _set_x11_clipboard(text_val: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
        tf.write(text_val)
        tmp_name = tf.name
    try:
        os.chmod(tmp_name, 0o644)
        subprocess.run(
            ["su", "-s", "/bin/bash", "gui", "-c", f"DISPLAY=:99 xclip -selection clipboard -i < {tmp_name} >/dev/null 2>&1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=6,
        )
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def verify_board_workbook(xlsx_p: Path, check_rev: bool, check_ops: bool, stage_filter: str = "all", check_oracle_canaries: bool = False) -> tuple[dict, list[str]]:
    if not xlsx_p.is_file():
        return {}, ["Missing /workspace/Q4_Board_Model.xlsx"]
    try:
        raw_sh = read_multisheet_xlsx(xlsx_p)
        ev_sh = evaluate_xlsx_via_libreoffice(xlsx_p)
    except Exception as exc:
        return {}, [f"Corrupted Q4_Board_Model.xlsx: {exc}"]

    errs: list[str] = []
    for sname in ("Revenue_FX", "Ops_Tax", "Treasury_Covenant", "Executive_Summary"):
        if sname not in raw_sh:
            errs.append(f"Missing worksheet {sname}")
    if errs:
        return {}, errs

    def _num(sh: dict, ref: str) -> float:
        v = (sh.get(ref) or {}).get("value")
        return float(v) if isinstance(v, (int, float)) else -999999.0

    # Check live formulas preserved
    for ref in ("B4", "B5"):
        if not (raw_sh["Treasury_Covenant"].get(ref) or {}).get("formula"):
            errs.append(f"Treasury_Covenant!{ref} missing live formula")
    for ref in ("B2", "B3", "B4", "B5", "B6"):
        if not (raw_sh["Executive_Summary"].get(ref) or {}).get("formula"):
            errs.append(f"Executive_Summary!{ref} missing live formula")

    stage_To_idxs = {
        "amer_reconcile": (0, 1),
        "emea_reconcile": (2, 3),
        "apac_reconcile": (4, 5),
    }
    idxs = stage_To_idxs.get(stage_filter, tuple(range(6)))

    if check_rev:
        r_ev = ev_sh["Revenue_FX"]
        r_raw = raw_sh["Revenue_FX"]
        for i in idxs:
            reg = REGIONS[i]
            row_i = i + 2
            b_v, c_v, d_v = _num(r_ev, f"B{row_i}"), _num(r_ev, f"C{row_i}"), _num(r_ev, f"D{row_i}")
            if b_v <= 1000.0 or abs((b_v + c_v) - d_v) > 0.5:
                errs.append(f"Revenue_FX row {row_i} ({reg}) invalid or B+C != D")
            if check_oracle_canaries:
                exp_g, exp_a, exp_n = TRUE_IFRS_REVENUE_USD_K[reg]
                if abs(b_v - exp_g) > 0.5 or abs(c_v - exp_a) > 0.5 or abs(d_v - exp_n) > 0.5:
                    errs.append(f"Canary mismatch Revenue_FX!{reg} != IFRS_REVENUE/USD_K")
        if stage_filter not in stage_To_idxs and not (r_raw.get("D8") or {}).get("formula"):
            errs.append("Revenue_FX!D8 missing =SUM formula")

    if check_ops:
        o_ev = ev_sh["Ops_Tax"]
        o_raw = raw_sh["Ops_Tax"]
        for i in idxs:
            reg = REGIONS[i]
            row_i = i + 2
            b_v, c_v, d_v = _num(o_ev, f"B{row_i}"), _num(o_ev, f"C{row_i}"), _num(o_ev, f"D{row_i}")
            if b_v <= 1000.0 or c_v <= 100.0 or abs((b_v + c_v) - d_v) > 0.5:
                errs.append(f"Ops_Tax row {row_i} ({reg}) invalid or B+C != D")
            if check_oracle_canaries:
                exp_c, exp_t, exp_tot = [round(x * 0.924, 2) for x in TRUE_OPS_STATUTORY_USD_K[reg]]
                if abs(b_v - exp_c) > 0.5 or abs(c_v - exp_t) > 0.5 or abs(d_v - exp_tot) > 0.5:
                    errs.append(f"Canary mismatch Ops_Tax!{reg} != OPS_STATUTORY/EUR_K")
        if stage_filter not in stage_To_idxs and not (o_raw.get("D8") or {}).get("formula"):
            errs.append("Ops_Tax!D8 missing =SUM formula")

    cov = ev_sh["Treasury_Covenant"]
    hedge_pct = _num(cov, "B2")
    capex_k = _num(cov, "B3")
    outflow_k = _num(cov, "B5")
    if check_rev and stage_filter in ("fx_var_stress", "full_board_pack", "all"):
        if not (FX_HEDGE_PCT_RANGE[0] <= hedge_pct <= FX_HEDGE_PCT_RANGE[1]):
            errs.append(f"Treasury_Covenant!B2 FX_Hedge_Ratio_Pct={hedge_pct} outside {list(FX_HEDGE_PCT_RANGE)}")
    if check_ops and stage_filter in ("capex_tax_stress", "full_board_pack", "all"):
        if not (INFRA_CAPEX_RANGE_USD_K[0] <= capex_k <= INFRA_CAPEX_RANGE_USD_K[1]):
            errs.append(f"Treasury_Covenant!B3 Infra_CapEx_Commit_USD_K={capex_k} outside {list(INFRA_CAPEX_RANGE_USD_K)}")
    if stage_filter in ("fx_var_stress", "capex_tax_stress", "full_board_pack", "all"):
        if not (COMMITTED_OUTFLOW_BAND_USD_K[0] - 0.05 <= outflow_k <= COMMITTED_OUTFLOW_BAND_USD_K[1] + 0.05):
            errs.append(f"Treasury_Covenant!B5 Total_Committed_Outflow_USD_K={outflow_k} outside required deployment band {list(COMMITTED_OUTFLOW_BAND_USD_K)}")

    summary = {
        "net_rev_total_usd_k": round(_num(ev_sh["Revenue_FX"], "D8"), 2),
        "ops_tax_total_usd_k": round(_num(ev_sh["Ops_Tax"], "D8"), 2),
        "ebitda_usd_k": round(_num(ev_sh["Executive_Summary"], "B4"), 2),
        "fx_hedge_ratio_pct": round(hedge_pct, 2),
        "infra_capex_usd_k": round(capex_k, 2),
        "committed_outflow_usd_k": round(outflow_k, 2),
    }
    return summary, errs


def verify_executive_pack(workspace: Path, check_rev: bool, check_ops: bool, check_oracle_canaries: bool = False) -> list[str]:
    html_p = workspace / "briefing" / "Q4_Executive_Pack.html"
    pdf_p = workspace / "briefing" / "Q4_Executive_Pack.pdf"
    errs: list[str] = []
    if not html_p.is_file():
        return ["Missing /workspace/briefing/Q4_Executive_Pack.html"]
    src = html_p.read_text(encoding="utf-8", errors="replace")
    if 'id="revenue-chart-slot"' not in src or 'id="ops-chart-slot"' not in src:
        errs.append("Q4_Executive_Pack.html missing #revenue-chart-slot or #ops-chart-slot container")
        return errs

    rev_idx = src.find('id="revenue-chart-slot"')
    ops_idx = src.find('id="ops-chart-slot"')
    rev_chunk = src[rev_idx:ops_idx] if rev_idx < ops_idx else src[rev_idx:]
    ops_chunk = src[ops_idx:rev_idx] if ops_idx < rev_idx else src[ops_idx:]

    if check_rev:
        if '<svg' not in rev_chunk or (check_oracle_canaries and REV_CANARY_TOKEN not in rev_chunk):
            errs.append("#revenue-chart-slot missing verified IFRS_REVENUE (USD_K) X11 clipboard SVG or contaminated by wrong scope/currency")
    if check_ops:
        if '<svg' not in ops_chunk or (check_oracle_canaries and OPS_CANARY_TOKEN not in ops_chunk):
            errs.append("#ops-chart-slot missing verified OPS_STATUTORY (EUR_K) X11 clipboard SVG or contaminated by wrong scope/currency")

    if not pdf_p.is_file() or pdf_p.stat().st_size < 4000:
        errs.append("Missing or empty /workspace/briefing/Q4_Executive_Pack.pdf")
    else:
        raw_pdf = pdf_p.read_bytes()
        if not raw_pdf.startswith(b"%PDF-"):
            errs.append("Q4_Executive_Pack.pdf is not a valid PDF document")
        if pdf_p.stat().st_mtime + 0.5 < html_p.stat().st_mtime:
            errs.append("Q4_Executive_Pack.pdf is older than Q4_Executive_Pack.html (not re-rendered after HTML edit)")
        cp_txt = subprocess.run(["pdftotext", str(pdf_p), "-"], capture_output=True, text=True, timeout=15)
        wb_s, _ = verify_board_workbook(workspace / "Q4_Board_Model.xlsx", check_rev=False, check_ops=False, stage_filter="none")
        exp_token = f"OUTFLOW_USD_K={wb_s.get('committed_outflow_usd_k', -1):.1f}"
        if cp_txt.returncode == 0 and exp_token not in cp_txt.stdout:
            errs.append(f"Q4_Executive_Pack.pdf text missing live {exp_token} matching Q4_Board_Model.xlsx")
    return errs


def run_monte_carlo_stress(summary: dict, fast_selfval: bool = False) -> dict:
    """Real NumPy correlated multi-currency FX & sovereign CapEx stress simulation over live workbook exposures."""
    import numpy as np

    rng = np.random.default_rng(20261120)
    hedge_frac = max(0.0, min(1.0, float(summary.get("fx_hedge_ratio_pct", 45.0)) / 100.0))
    capex_k = max(1000.0, float(summary.get("infra_capex_usd_k", 15000.0)))
    unhedged_exp = max(1000.0, float(summary.get("net_rev_total_usd_k", 158600.0)) * (1.0 - hedge_frac))

    cov = np.array([
        [0.0144, 0.0062, 0.0048, 0.0051, 0.0039, 0.0065],
        [0.0062, 0.0225, 0.0041, 0.0055, 0.0031, 0.0072],
        [0.0048, 0.0041, 0.0121, 0.0068, 0.0044, 0.0038],
        [0.0051, 0.0055, 0.0068, 0.0196, 0.0040, 0.0059],
        [0.0039, 0.0031, 0.0044, 0.0040, 0.0100, 0.0046],
        [0.0065, 0.0072, 0.0038, 0.0059, 0.0046, 0.0256],
    ], dtype=np.float64)
    chol = np.linalg.cholesky(cov)
    weights = np.array([0.30, 0.09, 0.23, 0.07, 0.19, 0.12], dtype=np.float64)

    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC03_STRESS_S", "195.0"))
    t_end = time.monotonic() + target_s
    losses = []
    paths_run = 0
    while True:
        z = rng.standard_normal((65536, 6))
        shocks = z @ chol.T
        port_loss = -(shocks @ weights) * unhedged_exp * 0.42
        losses.append(float(np.quantile(port_loss, 0.99)))
        paths_run += 65536
        if time.monotonic() >= t_end:
            break

    var99_k = round(float(sum(losses) / len(losses)), 2)
    sla_resilience_pct = round(min(99.5, 82.0 + 12.5 * ((capex_k - 12000.0) / 6000.0)), 2)
    return {
        "paths_simulated": paths_run,
        "fx_var99_usd_k": var99_k,
        "sla_resilience_pct": sla_resilience_pct,
    }


def render_bi_plate_png(scope: str, currency: str, selected_reg: str, bench_calls: int, rev_st: str, ops_st: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 520), (9, 14, 28))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 510)], outline=(56, 189, 248), width=2)
    dr.text(
        (26, 24),
        f"ENTERPRISE Q4 SSO BI CONSOLE  |  Active Scope: {scope}  |  Currency: {currency}  |  Selected Region: {selected_reg}",
        fill=(56, 189, 248),
    )
    dr.text(
        (26, 54),
        "Board Covenant: FX_Hedge [38.0, 73.0]% | Infra_CapEx [15000, 28200] USD_K | Outflow (380*Hedge + CapEx) in [41200.0, 42800.0] USD_K",
        fill=(226, 232, 240),
    )
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)

    fx_mult = 1.0 if currency == "USD_K" else 0.924
    src_map = TRUE_IFRS_REVENUE_USD_K if scope == "IFRS_REVENUE" else TRUE_OPS_STATUTORY_USD_K
    col_hdr = (
        f"REGION          SCOPE             CCY      GROSS_{currency:<6}   HEDGE_ADJ_{currency:<6}   NET_{currency:<6}"
        if scope == "IFRS_REVENUE"
        else f"REGION          SCOPE             CCY      CLOUD_OPS_{currency:<6} STAT_TAX_{currency:<6}  TOTAL_{currency:<6}"
    )
    dr.text((28, 102), col_hdr, fill=(251, 191, 36))
    y = 134
    for reg in REGIONS:
        c1, c2, c3 = [round(v * fx_mult, 2) for v in src_map[reg]]
        marker = ">>" if reg == selected_reg else "  "
        color = (125, 211, 252) if reg == selected_reg else (241, 245, 249)
        dr.text(
            (24, y),
            f"{marker} {reg:<12} {scope:<17} {currency:<8} {c1:>12.2f}     {c2:>12.2f}       {c3:>12.2f}",
            fill=color,
        )
        y += 32

    dr.line([(24, 344), (1196, 344)], fill=(51, 65, 85), width=1)
    dr.text(
        (28, 364),
        "Export Action writes Selected Region to /home/gui/Downloads/bi_region_extract.csv under ACTIVE Scope & Currency!",
        fill=(248, 250, 252),
    )
    dr.text(
        (28, 394),
        "Clipboard Action copies ACTIVE Scope & Currency verified <svg> chart onto X11 CLIPBOARD (DISPLAY=:99)!",
        fill=(248, 250, 252),
    )
    dr.text(
        (28, 456),
        f"Active View Basis: {scope} / {currency}  |  Selected Region Row: {selected_reg}",
        fill=(167, 243, 208),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Enterprise Q4 SSO BI Console — FC-03</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 6px 10px; cursor: pointer; font-family: monospace; font-weight: bold; font-size: 12px; }
    button:hover { background: #0284c7; }
    #msg { color: #38bdf8; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>SCOPE:</strong>
    <button onclick="upd({scope:'IFRS_REVENUE'})">IFRS_REVENUE</button>
    <button onclick="upd({scope:'OPS_STATUTORY'})">OPS_STATUTORY</button>
    <strong>CCY:</strong>
    <button onclick="upd({currency:'USD_K'})">USD_K</button>
    <button onclick="upd({currency:'EUR_K'})">EUR_K</button>
    <strong>REGION:</strong>
    <button onclick="upd({region:'AMER_NORTH'})">AMER_NORTH</button>
    <button onclick="upd({region:'AMER_LATAM'})">AMER_LATAM</button>
    <button onclick="upd({region:'EMEA_WEST'})">EMEA_WEST</button>
    <button onclick="upd({region:'EMEA_EAST'})">EMEA_EAST</button>
    <button onclick="upd({region:'APAC_DEV'})">APAC_DEV</button>
    <button onclick="upd({region:'APAC_EMERG'})">APAC_EMERG</button>
  </div>
  <div class="bar">
    <button onclick="doExtract()">Extract Selected Region (/home/gui/Downloads/bi_region_extract.csv)</button>
    <button onclick="doClip()">Copy Scope SVG to X11 Clipboard</button>
    <span id="msg">SSO BI Ready</span>
  </div>
  <canvas id="bi-canvas" width="1220" height="520"></canvas>
  <!-- Public protocol reference tokens:
       /workspace/Q4_Board_Model.xlsx /workspace/briefing/Q4_Executive_Pack.html /workspace/briefing/Q4_Executive_Pack.pdf
       /home/gui/Downloads/bi_region_extract.csv /api/bench/erp_covenant_audit /api/board/submit /api/board/status
       Revenue_FX Ops_Tax Treasury_Covenant Executive_Summary IFRS_REVENUE OPS_STATUTORY USD_K
       38.0 73.0 15000.0 28200.0 41200.0 42800.0 full_board_pack -->
  <script>
    function drawBi() {
      const cv = document.getElementById('bi-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/bi_plate.png?t=' + Date.now();
    }
    async function upd(b) {
      const r = await fetch('/api/ui/filter', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = d.scope + ' | ' + d.currency + ' | ' + d.region;
      drawBi();
    }
    async function doExtract() {
      const r = await fetch('/api/ui/extract_region', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Extracted ' + d.region + ' (' + d.scope + '/' + d.currency + ')';
      drawBi();
    }
    async function doClip() {
      const r = await fetch('/api/ui/copy_svg', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Copied X11 Clipboard SVG [' + d.scope + '/' + d.currency + ']';
      drawBi();
    }
    drawBi();
    setInterval(drawBi, 3500);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    state_lock = threading.Lock()
    sub_locks = {"revenue_treasury": threading.Lock(), "ops_tax": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {
            "scope": "IFRS_REVENUE",
            "currency": "USD_K",
            "region": "AMER_NORTH",
        },
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"revenue_treasury": {}, "ops_tax": {}},
        "qualified_stages": {"revenue_treasury": {}, "ops_tax": {}},
        "last_full_pack": {},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args) -> None:
            return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc03_sso")
                return bool(m and m.value == sso_cookie_val)
            except Exception:
                return False

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            qs = parse_qs(parsed.query)

            if p == "/health":
                self._json(200, {"ok": True, "task_id": TASK_ID})
                return

            if p == "/":
                if (qs.get("sso_boot") or [""])[0] == sso_boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"fc03_sso={sso_cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if p == "/ui/bi_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; use Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_bi_plate_png(
                        pstate["ui_session"]["scope"],
                        pstate["ui_session"]["currency"],
                        pstate["ui_session"]["region"],
                        pstate["bench_calls"],
                        (pstate["submissions"].get("revenue_treasury") or {}).get("status", "PENDING"),
                        (pstate["submissions"].get("ops_tax") or {}).get("status", "PENDING"),
                    )
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return

            if p == "/api/board/status":
                sub_q = (qs.get("subsystem") or [""])[0].strip().lower()
                if sub_q not in ("revenue_treasury", "ops_tax"):
                    self._json(400, {"error": "Pass ?subsystem=revenue_treasury or ?subsystem=ops_tax"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_stages": pstate["qualified_stages"][sub_q],
                        "last_full_pack": pstate["last_full_pack"].get(sub_q),
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return

            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/filter":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; click BI controls in Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    changed = False
                    if body.get("scope") in ("IFRS_REVENUE", "OPS_STATUTORY"):
                        if pstate["ui_session"]["scope"] != body["scope"]:
                            changed = True
                        pstate["ui_session"]["scope"] = body["scope"]
                    if body.get("currency") in ("USD_K", "EUR_K"):
                        if pstate["ui_session"]["currency"] != body["currency"]:
                            changed = True
                        pstate["ui_session"]["currency"] = body["currency"]
                    if body.get("region") in REGIONS:
                        pstate["ui_session"]["region"] = body["region"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/extract_region":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; click Extract in Chromium on DISPLAY=:99"})
                    return
                time.sleep(0.05 if fast_selfval else 5.5)
                dl_p = Path("/home/gui/Downloads/bi_region_extract.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    sc = pstate["ui_session"]["scope"]
                    ccy = pstate["ui_session"]["currency"]
                    reg = pstate["ui_session"]["region"]
                    fx_mult = 1.0 if ccy == "USD_K" else 0.924
                    src_map = TRUE_IFRS_REVENUE_USD_K if sc == "IFRS_REVENUE" else TRUE_OPS_STATUTORY_USD_K
                    v1, v2, v3 = [round(x * fx_mult, 2) for x in src_map[reg]]
                    hdr = "region,col_primary,col_secondary,col_total"
                    row = f"{reg},{v1},{v2},{v3}"
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(f"{hdr}\n{row}\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_p), "region": reg, "scope": sc, "currency": ccy})
                return

            if p == "/api/ui/copy_svg":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; click Copy SVG in Chromium on DISPLAY=:99"})
                    return
                time.sleep(0.05 if fast_selfval else 3.5)
                with state_lock:
                    sc = pstate["ui_session"]["scope"]
                    ccy = pstate["ui_session"]["currency"]
                    svg_txt = _build_scope_svg(sc, ccy)
                    pstate["clipboard_copies"] += 1
                    persist()
                _set_x11_clipboard(svg_txt)
                self._json(200, {"ok": True, "scope": sc, "currency": ccy})
                return

            if p == "/api/bench/erp_covenant_audit":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                valid_st = set(REV_STAGES) | set(OPS_STAGES)
                if sub not in ("revenue_treasury", "ops_tax") or stage not in valid_st:
                    self._json(400, {"error": f"Invalid subsystem={sub} or stage={stage}"})
                    return
                seq_list = REV_STAGES if sub == "revenue_treasury" else OPS_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Stage {stage} does not belong to {sub}"})
                    return
                st_idx = seq_list.index(stage)
                with state_lock:
                    prev_missing = [seq_list[i] for i in range(st_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_missing:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Qualify prerequisite stages first: {prev_missing}"})
                    return

                xlsx_p = workspace / "Q4_Board_Model.xlsx"
                pdf_p = workspace / "briefing" / "Q4_Executive_Pack.pdf"
                exp_reg = "IFRS_REVENUE" if sub == "revenue_treasury" else "OPS_STATUTORY"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["scope"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    wb_sum, wb_errs = verify_board_workbook(
                        xlsx_p,
                        check_rev=(sub == "revenue_treasury"),
                        check_ops=(sub == "ops_tax"),
                        stage_filter=stage,
                    )
                    errs = list(wb_errs)
                    if stage == "full_board_pack":
                        errs.extend(verify_executive_pack(
                            workspace,
                            check_rev=(sub == "revenue_treasury"),
                            check_ops=(sub == "ops_tax"),
                        ))
                    stress_res = run_monte_carlo_stress(wb_sum, fast_selfval=fast_selfval)
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                        if stage == "full_board_pack":
                            pstate["last_full_pack"][sub] = {
                                "passed": True,
                                "xlsx_sha256": sha256_file(xlsx_p),
                                "pdf_sha256": sha256_file(pdf_p),
                                "timestamp": time.time(),
                            }
                    pstate["bench_history"].append({
                        "timestamp": time.time(),
                        "subsystem": sub,
                        "stage": stage,
                        "passed": passed,
                        "elapsed_s": elapsed,
                    })
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "stage": stage,
                    "passed": passed,
                    "discrepancies": errs,
                    "workbook_summary": wb_sum,
                    "monte_carlo_stress": stress_res,
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/board/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("revenue_treasury", "ops_tax"):
                    self._json(400, {"error": "subsystem must be 'revenue_treasury' or 'ops_tax'"})
                    return

                xlsx_p = workspace / "Q4_Board_Model.xlsx"
                pdf_p = workspace / "briefing" / "Q4_Executive_Pack.pdf"
                wb_sum, wb_errs = verify_board_workbook(
                    xlsx_p,
                    check_rev=(sub == "revenue_treasury"),
                    check_ops=(sub == "ops_tax"),
                    stage_filter="all",
                )
                errs = list(wb_errs)
                errs.extend(verify_clean_workspace(workspace))
                errs.extend(verify_executive_pack(
                    workspace,
                    check_rev=(sub == "revenue_treasury"),
                    check_ops=(sub == "ops_tax"),
                ))

                req_stages = REV_STAGES if sub == "revenue_treasury" else OPS_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    missing = [st for st in req_stages if not q_map.get(st)]
                    if missing:
                        errs.append(f"Unqualified erp_covenant_audit stages for {sub}: {missing}")

                live_pdf_sha = sha256_file(pdf_p)
                try:
                    if str(body.get("pdf_sha256") or "") != live_pdf_sha:
                        errs.append("Submitted pdf_sha256 does not match /workspace/briefing/Q4_Executive_Pack.pdf")
                    if abs(float(body.get("committed_outflow_usd_k", -999)) - wb_sum.get("committed_outflow_usd_k", -1)) > 1.0:
                        errs.append(f"Submitted committed_outflow_usd_k != live {wb_sum.get('committed_outflow_usd_k')}")
                    if sub == "revenue_treasury":
                        if abs(float(body.get("net_rev_total_usd_k", -999)) - wb_sum.get("net_rev_total_usd_k", -1)) > 1.0:
                            errs.append("Submitted net_rev_total_usd_k != live Revenue_FX!D8")
                        if abs(float(body.get("fx_hedge_ratio_pct", -999)) - wb_sum.get("fx_hedge_ratio_pct", -1)) > 0.2:
                            errs.append("Submitted fx_hedge_ratio_pct != live Treasury_Covenant!B2")
                    else:
                        if abs(float(body.get("ops_tax_total_usd_k", -999)) - wb_sum.get("ops_tax_total_usd_k", -1)) > 1.0:
                            errs.append("Submitted ops_tax_total_usd_k != live Ops_Tax!D8")
                        if abs(float(body.get("infra_capex_usd_k", -999)) - wb_sum.get("infra_capex_usd_k", -1)) > 1.0:
                            errs.append("Submitted infra_capex_usd_k != live Treasury_Covenant!B3")
                except (TypeError, ValueError):
                    errs.append("Missing or non-numeric fields in submit payload")

                if errs:
                    self._json(422, {
                        "status": "REJECTED_BOARD_AUDIT",
                        "subsystem": sub,
                        "errors": errs,
                        "workbook_summary": wb_sum,
                    })
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "workbook_summary": wb_sum,
                    "pdf_sha256": live_pdf_sha,
                    "timestamp": time.time(),
                }
                with state_lock:
                    pstate["submissions"][sub] = rec
                    persist()
                self._json(200, rec)
                return

            self._json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={sso_boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def audit_case_transparency() -> dict:
    return audit_protocol_transparency(
        build_tickets_by_role(),
        PORTAL_HTML,
        REQUIRED_PUBLIC_TOKENS,
    )


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    xlsx_p = workspace / "Q4_Board_Model.xlsx"
    subs = portal_state.get("submissions") or {}
    rev_signed = (subs.get("revenue_treasury") or {}).get("status") == "APPROVED"
    ops_signed = (subs.get("ops_tax") or {}).get("status") == "APPROVED"
    closed_cnt = int(rev_signed) + int(ops_signed)

    wb_sum, rev_errs = verify_board_workbook(xlsx_p, check_rev=True, check_ops=False, stage_filter="all", check_oracle_canaries=True)
    _, ops_errs = verify_board_workbook(xlsx_p, check_rev=False, check_ops=True, stage_filter="all", check_oracle_canaries=True)
    _, both_errs = verify_board_workbook(xlsx_p, check_rev=True, check_ops=True, stage_filter="all", check_oracle_canaries=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "revenue_treasury", REV_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "ops_tax", OPS_STAGES[1:])
    pack_errs = verify_executive_pack(workspace, check_rev=True, check_ops=True, check_oracle_canaries=True) + verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs

    covenant_ok = bool(
        wb_sum
        and FX_HEDGE_PCT_RANGE[0] <= wb_sum.get("fx_hedge_ratio_pct", -1) <= FX_HEDGE_PCT_RANGE[1]
        and INFRA_CAPEX_RANGE_USD_K[0] <= wb_sum.get("infra_capex_usd_k", -1) <= INFRA_CAPEX_RANGE_USD_K[1]
        and COMMITTED_OUTFLOW_BAND_USD_K[0] - 0.05 <= wb_sum.get("committed_outflow_usd_k", 999999.0) <= COMMITTED_OUTFLOW_BAND_USD_K[1] + 0.05
    )
    trans = audit_case_transparency()

    invariants = {
        "revenue_treasury_signed_and_ifrs_exact": bool(len(pur_a_errs) == 0 and rev_signed and len(rev_errs) == 0),
        "ops_tax_signed_and_statutory_exact": bool(len(pur_b_errs) == 0 and ops_signed and len(ops_errs) == 0),
        "covenant_outflow_and_formulas_valid": bool(covenant_ok and len(both_errs) == 0),
        "x11_clipboard_svgs_and_pdf_pack_valid": bool(len(pack_errs) == 0),
    }
    inv_score = round(sum(1 for v in invariants.values() if v) / len(invariants), 4)
    joint_pass = all(invariants.values())

    return {
        "task_id": TASK_ID,
        "joint_pass": joint_pass,
        "invariants": invariants,
        "cross_role_invariant_score": inv_score,
        "closed_tickets_count": closed_cnt,
        "local_completion_rate": round(closed_cnt / 2.0, 4),
        "unaware_race_failure": bool(closed_cnt > 0 and not joint_pass),
        "total_bench_calls": int(portal_state.get("bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "workbook_summary": wb_sum,
        "diagnostics": {
            "revenue_errors": rev_errs,
            "ops_errors": ops_errs,
            "pack_errors": pack_errs,
        },
        "protocol_transparency": trans,
    }


def _patch_slot_in_html(html_p: Path, slot_id: str, svg_markup: str) -> None:
    import re

    src = html_p.read_text(encoding="utf-8")
    pattern = rf'(<div id="{slot_id}"[^>]*>)(.*?)(</div>)'
    updated = re.sub(pattern, rf"\1{svg_markup}\3", src, count=1, flags=re.DOTALL)
    html_p.write_text(updated, encoding="utf-8")


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    """Cooperative single-role solver using SSO extracts, X11 clipboard SVG, and live covenant inspection."""
    assert role in ("revenue_treasury_lead", "ops_tax_lead")
    base = f"http://127.0.0.1:{portal_port}"
    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}

    is_rev = (role == "revenue_treasury_lead")
    sc = "IFRS_REVENUE" if is_rev else "OPS_STATUTORY"
    sub = "revenue_treasury" if is_rev else "ops_tax"

    extracted: dict[str, tuple[float, float, float]] = {}
    dl_p = Path("/home/gui/Downloads/bi_region_extract.csv")
    for reg in REGIONS:
        req1 = urllib.request.Request(
            f"{base}/api/ui/filter",
            data=json.dumps({"scope": sc, "currency": ("USD_K" if is_rev else "EUR_K"), "region": reg}).encode("utf-8"),
            headers={"Content-Type": "application/json", **adm_hdr},
            method="POST",
        )
        urllib.request.urlopen(req1, timeout=10).read()
        req2 = urllib.request.Request(f"{base}/api/ui/extract_region", data=b"{}", headers=adm_hdr, method="POST")
        urllib.request.urlopen(req2, timeout=10).read()
        lines = dl_p.read_text(encoding="utf-8").strip().splitlines()
        parts = lines[-1].split(",")
        extracted[reg] = (float(parts[1]), float(parts[2]), float(parts[3]))

    req_clip = urllib.request.Request(f"{base}/api/ui/copy_svg", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(req_clip, timeout=10).read()
    cp_clip = subprocess.run(
        ["su", "-s", "/bin/bash", "gui", "-c", "DISPLAY=:99 xclip -selection clipboard -o"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    svg_txt = cp_clip.stdout.strip() or _build_scope_svg(sc, "USD_K" if is_rev else "EUR_K")

    xlsx_p = workspace / "Q4_Board_Model.xlsx"
    ev_now = evaluate_xlsx_via_libreoffice(xlsx_p)
    cur_hedge = float((ev_now.get("Treasury_Covenant", {}).get("B2") or {}).get("value") or 45.0)
    cur_capex = float((ev_now.get("Treasury_Covenant", {}).get("B3") or {}).get("value") or 15000.0)

    if is_rev:
        target_margin = max(380.0 * 38.2, min(380.0 * 72.5, 42000.0 - cur_capex))
        new_hedge = round(target_margin / 380.0, 2)
        new_capex = cur_capex
        update_single_sheet_xlsx(xlsx_p, "Revenue_FX", _make_rev_rows(extracted))
    else:
        cur_margin = 380.0 * cur_hedge
        new_hedge = cur_hedge
        new_capex = round(max(15050.0, min(28000.0, 42000.0 - cur_margin)), 1)
        update_single_sheet_xlsx(xlsx_p, "Ops_Tax", _make_ops_rows(extracted))

    update_single_sheet_xlsx(xlsx_p, "Treasury_Covenant", _make_covenant_rows(new_hedge, new_capex))
    ev_after = evaluate_xlsx_via_libreoffice(xlsx_p)
    rev_d8 = float((ev_after["Revenue_FX"].get("D8") or {}).get("value") or 158600.0)
    ops_d8 = float((ev_after["Ops_Tax"].get("D8") or {}).get("value") or 87400.0)
    outflow_b5 = float((ev_after["Treasury_Covenant"].get("B5") or {}).get("value") or (380.0 * new_hedge + new_capex))
    update_single_sheet_xlsx(xlsx_p, "Executive_Summary", _make_exec_summary_rows(rev_d8, ops_d8, outflow_b5))

    html_p = workspace / "briefing" / "Q4_Executive_Pack.html"
    pdf_p = workspace / "briefing" / "Q4_Executive_Pack.pdf"
    _patch_slot_in_html(html_p, "revenue-chart-slot" if is_rev else "ops-chart-slot", svg_txt)
    _patch_slot_in_html(html_p, "executive-kpi-banner", f"OUTFLOW_USD_K={outflow_b5:.1f}")
    subprocess.run(
        [
            "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
            f"--print-to-pdf={pdf_p}", f"file://{html_p}",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )

    stages = REV_STAGES if is_rev else OPS_STAGES
    for st in stages:
        code, resp = post_json(f"{base}/api/bench/erp_covenant_audit", {"subsystem": sub, "stage": st}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {st} failed: {resp}"

    wb_sum, _ = verify_board_workbook(xlsx_p, check_rev=False, check_ops=False, stage_filter="all")
    payload = {
        "subsystem": sub,
        "committed_outflow_usd_k": wb_sum["committed_outflow_usd_k"],
        "pdf_sha256": sha256_file(pdf_p),
    }
    if is_rev:
        payload["net_rev_total_usd_k"] = wb_sum["net_rev_total_usd_k"]
        payload["fx_hedge_ratio_pct"] = wb_sum["fx_hedge_ratio_pct"]
    else:
        payload["ops_tax_total_usd_k"] = wb_sum["ops_tax_total_usd_k"]
        payload["infra_capex_usd_k"] = wb_sum["infra_capex_usd_k"]
    code, sresp = post_json(f"{base}/api/board/submit", payload, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    """Gate 3: Simulate concurrent BI filter/clipboard collision + whole-workbook overwrite."""
    xlsx_p = workspace / "Q4_Board_Model.xlsx"
    html_p = workspace / "briefing" / "Q4_Executive_Pack.html"
    with tempfile.TemporaryDirectory() as tmp:
        snap_xlsx = Path(tmp) / "v0.xlsx"
        snap_html = Path(tmp) / "v0.html"
        shutil.copy2(xlsx_p, snap_xlsx)
        shutil.copy2(html_p, snap_html)

        solve_role("revenue_treasury_lead", workspace, portal_port, strict=True)

        # Second role overwrites workbook & briefing HTML from its initial snapshot + greedy covenant
        shutil.copy2(snap_xlsx, xlsx_p)
        shutil.copy2(snap_html, html_p)
        solve_role("ops_tax_lead", workspace, portal_port, strict=False)

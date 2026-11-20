"""FC-12: Multi-Desk Quantitative Stat-Arb & Macro-Rates Portfolio Risk Co-Optimization (SQLite Position Book + Cholesky VaR Engine + .xlsx Risk Pack + Crowded-Factor Cross-Margin + 6.5s Prime SPAN Canaries)."""
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

TASK_ID = "FC-12"
PORTAL_PORT = 19520

META = {
    "id": TASK_ID,
    "title": "Quantitative Stat-Arb & Macro-Rates Risk Book, Cholesky VaR & Prime SPAN Margin Equilibrium",
    "domain": "Quantitative Finance & Prime-Brokerage Risk (SQLite Position Book + Cholesky Factor VaR + LibreOffice .xlsx + SSO Prime SPAN Console)",
    "arena": "Crowded-Factor Margin Cross-Impact, Shared SQLite/XLSX Risk Book & 6.5s Prime SPAN Sweeps",
    "conflict_archetype": "crowded_factor_cross_margin_asymmetric_cap + async_6_5s_prime_span_canary + sqlite_and_xlsx_book_sync",
    "roles": ("stat_arb_equity_lead", "macro_rates_vol_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "quant_risk_desk/Prime_Risk_Pack.xlsx",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

BUCKETS = ("BKT_T1", "BKT_T2", "BKT_T3", "BKT_T4")

TRUE_STATARB_SPAN: dict[str, tuple[float, float]] = {
    "BKT_T1": (145.5, 290.0),
    "BKT_T2": (162.0, 325.0),
    "BKT_T3": (138.0, 276.0),
    "BKT_T4": (174.5, 348.0),
}
TRUE_MACRORATES_SPAN: dict[str, tuple[float, float]] = {
    "BKT_T1": (88.4, 195.0),
    "BKT_T2": (94.2, 210.0),
    "BKT_T3": (82.6, 184.0),
    "BKT_T4": (99.8, 224.0),
}

NOTIONAL_RANGE_MUSD = (58.0, 64.0)
CROSS_CROWD_BETA = 0.60
MAX_MARGIN_UTIL_PCT = 98.9

STATARB_STAGES = ("book_schema_gate", "alpha_notional_sizing", "span_haircut_sync", "crowded_margin_stress", "full_risk_signoff")
MACRO_STAGES = ("book_schema_gate", "dv01_notional_sizing", "span_haircut_sync", "crowded_margin_stress", "full_risk_signoff")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/quant_risk_desk/portfolio_positions.db",
    "/workspace/quant_risk_desk/Prime_Risk_Pack.xlsx",
    "StatArb_Margin",
    "MacroRates_Margin",
    "CME_CROSS_MARGIN_NET",
    "BILATERAL_GROSS",
    "/api/bench/cholesky_var_engine",
    "/api/quant/submit",
    "/api/quant/status",
    "58.0",
    "64.0",
    "0.60",
    "98.9",
    "full_risk_signoff",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "quant_risk_desk")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside quant_risk_desk: {extra_top}")
    qd = workspace / "quant_risk_desk"
    allowed = {"portfolio_positions.db", "Prime_Risk_Pack.xlsx"}
    if qd.is_dir():
        extra = sorted(
            x.name for x in qd.iterdir()
            if x.name not in allowed and not x.name.startswith("portfolio_positions.db-")
        )
        if extra:
            errs.append(f"Unexpected non-release files in /workspace/quant_risk_desk: {extra} (use /tmp or $HOME for scripts)")
    return errs


def inspect_quant_workspace(workspace: Path) -> dict:
    qd = workspace / "quant_risk_desk"
    db_p = qd / "portfolio_positions.db"
    xp = qd / "Prime_Risk_Pack.xlsx"
    if not db_p.is_file() or not xp.is_file():
        return {"ok": False, "error": "Missing portfolio_positions.db or Prime_Risk_Pack.xlsx"}

    try:
        with sqlite3.connect(str(db_p)) as conn:
            rows = conn.execute("SELECT desk, gross_notional_musd FROM desk_allocations").fetchall()
        alloc = {str(r[0]): float(r[1]) for r in rows}
        raw_sh = read_multisheet_xlsx(xp)
        ev_sh = evaluate_xlsx_via_libreoffice(xp)
    except Exception as exc:
        return {"ok": False, "error": f"Corrupted SQLite DB or XLSX: {exc}"}

    n_sa = float(alloc.get("STAT_ARB_EQUITY", 20.0))
    n_mr = float(alloc.get("MACRO_RATES_VOL", 20.0))
    util_sa = round(n_sa + CROSS_CROWD_BETA * n_mr, 3)
    util_mr = round(n_mr + CROSS_CROWD_BETA * n_sa, 3)

    return {
        "ok": True,
        "raw_sh": raw_sh,
        "ev_sh": ev_sh,
        "summary": {
            "stat_arb_notional_musd": round(n_sa, 3),
            "macro_rates_notional_musd": round(n_mr, 3),
            "stat_arb_margin_util_pct": util_sa,
            "macro_rates_margin_util_pct": util_mr,
        },
    }


def check_quant_constraints(
    info: dict,
    check_sa: bool,
    check_mr: bool,
    stage: str = "full_risk_signoff",
    check_oracle_canaries: bool = False,
) -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid workspace")]
    errs: list[str] = []
    s = info["summary"]
    raw_sh = info["raw_sh"]
    ev_sh = info["ev_sh"]

    def _num(sh: dict, ref: str) -> float:
        v = (sh.get(ref) or {}).get("value")
        return float(v) if isinstance(v, (int, float)) else -999.0

    for sn in ("StatArb_Margin", "MacroRates_Margin"):
        if sn not in raw_sh:
            errs.append(f"Missing worksheet {sn}")
    if errs:
        return errs

    if check_sa:
        if stage in ("alpha_notional_sizing", "span_haircut_sync", "crowded_margin_stress", "full_risk_signoff"):
            if not (NOTIONAL_RANGE_MUSD[0] <= s["stat_arb_notional_musd"] <= NOTIONAL_RANGE_MUSD[1]):
                errs.append(f"STAT_ARB_EQUITY gross_notional_musd={s['stat_arb_notional_musd']} outside {list(NOTIONAL_RANGE_MUSD)}")
        if stage in ("span_haircut_sync", "crowded_margin_stress", "full_risk_signoff"):
            for r_i in range(2, 6):
                if _num(ev_sh["StatArb_Margin"], f"B{r_i}") <= 0 or _num(ev_sh["StatArb_Margin"], f"C{r_i}") <= 0:
                    errs.append(f"StatArb_Margin row {r_i} missing positive haircut bps")
            if not (raw_sh["StatArb_Margin"].get("B6") or {}).get("formula"):
                errs.append("StatArb_Margin!B6 missing =SUM or =AVERAGE formula")
        if stage in ("crowded_margin_stress", "full_risk_signoff"):
            if s["stat_arb_margin_util_pct"] > MAX_MARGIN_UTIL_PCT:
                errs.append(f"stat_arb_margin_util_pct={s['stat_arb_margin_util_pct']}% exceeds {MAX_MARGIN_UTIL_PCT}%")

    if check_mr:
        if stage in ("dv01_notional_sizing", "span_haircut_sync", "crowded_margin_stress", "full_risk_signoff"):
            if not (NOTIONAL_RANGE_MUSD[0] <= s["macro_rates_notional_musd"] <= NOTIONAL_RANGE_MUSD[1]):
                errs.append(f"MACRO_RATES_VOL gross_notional_musd={s['macro_rates_notional_musd']} outside {list(NOTIONAL_RANGE_MUSD)}")
        if stage in ("span_haircut_sync", "crowded_margin_stress", "full_risk_signoff"):
            for r_i in range(2, 6):
                if _num(ev_sh["MacroRates_Margin"], f"B{r_i}") <= 0 or _num(ev_sh["MacroRates_Margin"], f"C{r_i}") <= 0:
                    errs.append(f"MacroRates_Margin row {r_i} missing positive haircut bps")
            if not (raw_sh["MacroRates_Margin"].get("B6") or {}).get("formula"):
                errs.append("MacroRates_Margin!B6 missing =SUM or =AVERAGE formula")
        if stage in ("crowded_margin_stress", "full_risk_signoff"):
            if s["macro_rates_margin_util_pct"] > MAX_MARGIN_UTIL_PCT:
                errs.append(f"macro_rates_margin_util_pct={s['macro_rates_margin_util_pct']}% exceeds {MAX_MARGIN_UTIL_PCT}%")

    if check_oracle_canaries:
        for idx, bkt in enumerate(BUCKETS, start=2):
            eb, ec = TRUE_STATARB_SPAN[bkt]
            if abs(_num(ev_sh["StatArb_Margin"], f"B{idx}") - eb) > 0.5 or abs(_num(ev_sh["StatArb_Margin"], f"C{idx}") - ec) > 1.0:
                errs.append(f"Canary mismatch StatArb_Margin {bkt} != CME_CROSS_MARGIN_NET {(eb, ec)}")
            mb, mc = TRUE_MACRORATES_SPAN[bkt]
            if abs(_num(ev_sh["MacroRates_Margin"], f"B{idx}") - mb) > 0.5 or abs(_num(ev_sh["MacroRates_Margin"], f"C{idx}") - mc) > 1.0:
                errs.append(f"Canary mismatch MacroRates_Margin {bkt} != BILATERAL_GROSS {(mb, mc)}")
    return errs


def run_cholesky_factor_var(summary: dict, fast_selfval: bool = False) -> dict:
    import numpy as np

    rng = np.random.default_rng(202612)
    cov = np.eye(24) * 0.04 + 0.012
    chol = np.linalg.cholesky(cov)
    w = np.ones(24) / 24.0 * (summary.get("stat_arb_notional_musd", 20.0) + summary.get("macro_rates_notional_musd", 20.0))
    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC12_VAR_S", "290.0"))
    t0 = time.monotonic()
    batches = 0
    es99 = 0.0
    while True:
        z = rng.standard_normal((32768, 24)) @ chol.T
        pnl = -(z @ w)
        q99 = np.quantile(pnl, 0.99)
        es99 = float(np.mean(pnl[pnl >= q99]))
        batches += 1
        if time.monotonic() - t0 >= target_s:
            break
    return {"mc_batches": batches, "expected_shortfall_99_musd": round(es99, 3), "elapsed_s": round(time.monotonic() - t0, 2)}


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Prime-Brokerage Risk Book, Crowded-Factor Margin Law & Hygiene",
        f"- **Risk Root**: {b}/workspace/quant_risk_desk{b}",
        f"  - SQLite WAL Position Book: {b}portfolio_positions.db{b} ({b}desk_allocations(desk TEXT PRIMARY KEY, gross_notional_musd REAL){b} for {b}STAT_ARB_EQUITY{b} and {b}MACRO_RATES_VOL{b}, each in **{b}[58.0, 64.0] MUSD{b}**).",
        f"  - Prime Risk Workbook: {b}Prime_Risk_Pack.xlsx{b} ({b}StatArb_Margin{b} and {b}MacroRates_Margin{b} sheets, {b}Rows 2..5{b} for {b}BKT_T1..BKT_T4{b}, {b}Row 6{b} live {b}=SUM{b} or {b}=AVERAGE{b} formula in {b}B6:C6{b}).",
        f"- **Crowded-Factor Cross-Impact Margin Law**:",
        f"  - Stat-Arb Margin Utilization: {b}stat_arb_margin_util_pct = stat_arb_notional_musd + 0.60 * macro_rates_notional_musd <= 98.9%{b}.",
        f"  - Macro-Rates Margin Utilization: {b}macro_rates_margin_util_pct = macro_rates_notional_musd + 0.60 * stat_arb_notional_musd <= 98.9%{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/quant_risk_desk{b} may contain ONLY {b}portfolio_positions.db{b} and {b}Prime_Risk_Pack.xlsx{b}.",
        f"- **SSO Prime SPAN Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & VaR Engine API**:",
        f"  - Select your clearing regime for your assigned subsystem, your desk ({b}STAT_ARB_EQUITY{b} or {b}MACRO_RATES_VOL{b}), and bucket ({b}BKT_T1..BKT_T4{b}), then click {b}Run 6.5s SPAN Haircut Sweep{b} to export {b}/home/gui/Downloads/span_haircut.csv{b}.",
        f"  - Note: each {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/cholesky_var_engine{b} run executes ~110s of Monte Carlo simulation (use {b}curl --max-time 300{b}). Pass {b}X-Role-Token{b} from {b}/session/ticket/role_token.txt{b} on {b}GET /api/quant/status{b}.",
    ]
    common_txt = "\n".join(common_lines)

    sa_txt = "\n".join([
        f"# Quant Risk Work Order — FC-12 ({b}stat_arb_equity_lead{b})",
        "",
        f"Size {b}STAT_ARB_EQUITY{b} notional in {b}portfolio_positions.db{b} and populate {b}StatArb_Margin{b} in {b}Prime_Risk_Pack.xlsx{b} under {b}CME_CROSS_MARGIN_NET{b}.",
        "",
        "### Stat-Arb Steps",
        f"1. Sweep {b}BKT_T1..BKT_T4{b} under **{b}CME_CROSS_MARGIN_NET{b}** + **{b}STAT_ARB_EQUITY{b}** on {b}DISPLAY=:99{b} into {b}StatArb_Margin!B2:C5{b} (keeping {b}B6:C6{b} formulas).",
        f"2. Set {b}STAT_ARB_EQUITY{b} {b}gross_notional_musd{b} in **{b}[58.0, 64.0]{b}** respecting both crowded-margin caps ({b}<= 98.9%{b}).",
        f"3. Certify ordered stages ({b}book_schema_gate -> alpha_notional_sizing -> span_haircut_sync -> crowded_margin_stress -> full_risk_signoff{b}) on {b}POST /api/bench/cholesky_var_engine{b} ({b}subsystem='stat_arb_equity'{b}) and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/quant/submit{b}:",
        f"   {b}{{\"subsystem\": \"stat_arb_equity\", \"notional_musd\": <float>, \"margin_util_pct\": <float>, \"xlsx_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}CME_CROSS_MARGIN_NET{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    mr_txt = "\n".join([
        f"# Quant Risk Work Order — FC-12 ({b}macro_rates_vol_lead{b})",
        "",
        f"Size {b}MACRO_RATES_VOL{b} notional in {b}portfolio_positions.db{b} and populate {b}MacroRates_Margin{b} in {b}Prime_Risk_Pack.xlsx{b} under {b}BILATERAL_GROSS{b}.",
        "",
        "### Macro-Rates Steps",
        f"1. Sweep {b}BKT_T1..BKT_T4{b} under **{b}BILATERAL_GROSS{b}** + **{b}MACRO_RATES_VOL{b}** on {b}DISPLAY=:99{b} into {b}MacroRates_Margin!B2:C5{b} (keeping {b}B6:C6{b} formulas).",
        f"2. Set {b}MACRO_RATES_VOL{b} {b}gross_notional_musd{b} in **{b}[58.0, 64.0]{b}** respecting both crowded-margin caps ({b}<= 98.9%{b}).",
        f"3. Certify ordered stages ({b}book_schema_gate -> dv01_notional_sizing -> span_haircut_sync -> crowded_margin_stress -> full_risk_signoff{b}) on {b}POST /api/bench/cholesky_var_engine{b} ({b}subsystem='macro_rates_vol'{b}) and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/quant/submit{b}:",
        f"   {b}{{\"subsystem\": \"macro_rates_vol\", \"notional_musd\": <float>, \"margin_util_pct\": <float>, \"xlsx_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}BILATERAL_GROSS{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"stat_arb_equity_lead": sa_txt, "macro_rates_vol_lead": mr_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    qd = workspace / "quant_risk_desk"
    qd.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(qd / "portfolio_positions.db")) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE desk_allocations(desk TEXT PRIMARY KEY, gross_notional_musd REAL);")
        conn.executemany("INSERT INTO desk_allocations(desk, gross_notional_musd) VALUES (?, ?)", [("STAT_ARB_EQUITY", 20.0), ("MACRO_RATES_VOL", 20.0)])
        conn.commit()

    sa_r = [["Bucket", "Init_Margin_Bps", "Stress_VaR_Bps"]] + [[b, 0.0, 0.0] for b in BUCKETS] + [["TOTAL", ("=SUM(B2:B5)", 0.0), ("=SUM(C2:C5)", 0.0)]]
    mr_r = [["Bucket", "Init_Margin_Bps", "Stress_VaR_Bps"]] + [[b, 0.0, 0.0] for b in BUCKETS] + [["TOTAL", ("=SUM(B2:B5)", 0.0), ("=SUM(C2:C5)", 0.0)]]
    write_multisheet_xlsx(qd / "Prime_Risk_Pack.xlsx", [("StatArb_Margin", sa_r), ("MacroRates_Margin", mr_r)])

    role_tokens = {}
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")
        tok = "rtok_" + secrets.token_hex(12)
        (rdir / "role_token.txt").write_text(tok + "\n", encoding="utf-8")
        role_tokens[role] = tok
    write_json(tickets_root / "role_tokens.json", role_tokens)


def render_quant_plate_png(clearing: str, desk: str, bkt: str, busy: bool) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 480), (10, 15, 25))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 470)], outline=(52, 211, 153), width=2)
    dr.text((24, 24), f"PRIME-BROKERAGE SPAN MARGIN CONSOLE  |  Clearing: {clearing}  |  Desk: {desk}  |  Bucket: {bkt}", fill=(52, 211, 153))
    dr.text((24, 54), "Crowded-Factor Margin Cap: N_i + 0.60 * N_j <= 98.9%  |  Notional in [58.0, 64.0] MUSD", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)
    st = "SPAN SCENARIO GRID COMPUTING (6.5s)..." if busy else "IDLE — Click [Run 6.5s SPAN Haircut Sweep]"
    dr.text((28, 118), f"SPAN Engine    : {st}", fill=(251, 191, 36))
    dr.text((28, 156), f"Export Target  : {clearing} / {desk} / {bkt} -> /home/gui/Downloads/span_haircut.csv", fill=(241, 245, 249))
    pts = [(60 + k * 14, int(390 - 150 * abs(math.sin(k / 15.0)))) for k in range(75)]
    dr.line(pts, fill=(56, 189, 248), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Prime SPAN Margin Console — FC-12</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 6px 10px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #059669; }
    #msg { color: #34d399; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>CLEARING:</strong>
    <button onclick="setQ({clearing:'CME_CROSS_MARGIN_NET'})">CME_CROSS_MARGIN_NET</button>
    <button onclick="setQ({clearing:'BILATERAL_GROSS'})">BILATERAL_GROSS</button>
    <strong>DESK:</strong>
    <button onclick="setQ({desk:'STAT_ARB_EQUITY'})">STAT_ARB_EQUITY</button>
    <button onclick="setQ({desk:'MACRO_RATES_VOL'})">MACRO_RATES_VOL</button>
    <strong>BUCKET:</strong>
    <button onclick="setQ({bkt:'BKT_T1'})">BKT_T1</button>
    <button onclick="setQ({bkt:'BKT_T2'})">BKT_T2</button>
    <button onclick="setQ({bkt:'BKT_T3'})">BKT_T3</button>
    <button onclick="setQ({bkt:'BKT_T4'})">BKT_T4</button>
  </div>
  <div class="bar">
    <button onclick="sweepSpan()">Run 6.5s SPAN Haircut Sweep (/home/gui/Downloads/span_haircut.csv)</button>
    <span id="msg">Prime SPAN SSO Active</span>
  </div>
  <canvas id="q-canvas" width="1220" height="480"></canvas>
  <!-- Public protocol tokens:
       /workspace/quant_risk_desk/portfolio_positions.db /workspace/quant_risk_desk/Prime_Risk_Pack.xlsx
       StatArb_Margin MacroRates_Margin CME_CROSS_MARGIN_NET BILATERAL_GROSS
       /api/bench/cholesky_var_engine /api/quant/submit /api/quant/status 58.0 64.0 0.60 98.9 full_risk_signoff -->
  <script>
    function drawQ() {
      const cv = document.getElementById('q-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/quant_plate.png?t=' + Date.now();
    }
    async function setQ(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.clearing || '') + ' | ' + (d.desk || '') + ' | ' + (d.bkt || '');
      drawQ();
    }
    async function sweepSpan() {
      document.getElementById('msg').textContent = 'Running 6.5s SPAN sweep...';
      drawQ();
      const r = await fetch('/api/ui/sweep_span', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Saved ' + (d.path || '');
      drawQ();
    }
    drawQ();
    setInterval(drawQ, 3000);
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

    rtok_p = state_dir / "role_tokens.json"
    role_tokens = json.loads(rtok_p.read_text(encoding="utf-8")) if rtok_p.is_file() else {}
    tok_to_sub = {
        role_tokens.get("stat_arb_equity_lead", ""): "stat_arb_equity",
        role_tokens.get("macro_rates_vol_lead", ""): "macro_rates_vol",
    }

    state_lock = threading.Lock()
    sub_locks = {"stat_arb_equity": threading.Lock(), "macro_rates_vol": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"clearing": "BILATERAL_GROSS", "desk": "STAT_ARB_EQUITY", "bkt": "BKT_T1", "busy": False},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"stat_arb_equity": {}, "macro_rates_vol": {}},
        "qualified_stages": {"stat_arb_equity": {}, "macro_rates_vol": {}},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a): return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc12_sso")
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
                    self.send_header("Set-Cookie", f"fc12_sso={sso_cookie_val}; Path=/; HttpOnly")
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
            if p == "/ui/quant_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    u = pstate["ui_session"]
                    png = render_quant_plate_png(u["clearing"], u["desk"], u["bkt"], bool(u["busy"]))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/quant/status":
                rtok = (self.headers.get("X-Role-Token") or "").strip()
                sub_q = tok_to_sub.get(rtok, "") if rtok else ""
                if not sub_q:
                    self._json(403, {"error": "Valid X-Role-Token header required"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_stages": pstate["qualified_stages"][sub_q],
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/view":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    changed = False
                    if body.get("clearing") in ("CME_CROSS_MARGIN_NET", "BILATERAL_GROSS"):
                        if pstate["ui_session"]["clearing"] != body["clearing"]:
                            changed = True
                        pstate["ui_session"]["clearing"] = body["clearing"]
                    if body.get("desk") in ("STAT_ARB_EQUITY", "MACRO_RATES_VOL"):
                        if pstate["ui_session"]["desk"] != body["desk"]:
                            changed = True
                        pstate["ui_session"]["desk"] = body["desk"]
                    if body.get("bkt") in BUCKETS:
                        pstate["ui_session"]["bkt"] = body["bkt"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/sweep_span":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    pstate["ui_session"]["busy"] = True
                time.sleep(0.05 if fast_selfval else 7.5)
                dl_p = Path("/home/gui/Downloads/span_haircut.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pstate["ui_session"]["busy"] = False
                    cl = pstate["ui_session"]["clearing"]
                    dk = pstate["ui_session"]["desk"]
                    bk = pstate["ui_session"]["bkt"]
                    exp_cl = "CME_CROSS_MARGIN_NET" if dk == "STAT_ARB_EQUITY" else "BILATERAL_GROSS"
                    mult = 1.0 if cl == exp_cl else 1.175
                    src_tbl = TRUE_STATARB_SPAN if dk == "STAT_ARB_EQUITY" else TRUE_MACRORATES_SPAN
                    v1, v2 = src_tbl[bk]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(f"bucket_id,init_margin_bps,stress_var_bps\n{bk},{round(v1*mult, 2)},{round(v2*mult, 2)}\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                self._json(200, {"ok": True, "path": str(dl_p)})
                return

            if p == "/api/bench/cholesky_var_engine":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("stat_arb_equity", "macro_rates_vol"):
                    self._json(400, {"error": "subsystem must be 'stat_arb_equity' or 'macro_rates_vol'"})
                    return
                seq_list = STATARB_STAGES if sub == "stat_arb_equity" else MACRO_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                exp_reg = "CME_CROSS_MARGIN_NET" if sub == "stat_arb_equity" else "BILATERAL_GROSS"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["clearing"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_quant_workspace(workspace)
                    errs = check_quant_constraints(
                        info,
                        check_sa=(sub == "stat_arb_equity"),
                        check_mr=(sub == "macro_rates_vol"),
                        stage=stage,
                        check_oracle_canaries=False,
                    )
                    mc = run_cholesky_factor_var(info.get("summary") or {}, fast_selfval=fast_selfval) if info.get("ok") else {}
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({"timestamp": time.time(), "subsystem": sub, "stage": stage, "passed": passed, "elapsed_s": elapsed})
                    persist()

                s = info.get("summary") or {}
                own_m = {
                    "own_notional_musd": s.get("stat_arb_notional_musd") if sub == "stat_arb_equity" else s.get("macro_rates_notional_musd"),
                    "own_margin_util_pct": s.get("stat_arb_margin_util_pct") if sub == "stat_arb_equity" else s.get("macro_rates_margin_util_pct"),
                }
                self._json(200, {"ok": True, "subsystem": sub, "stage": stage, "passed": passed, "discrepancies": errs, "desk_margin": own_m, "var_mc": mc, "elapsed_s": elapsed})
                return

            if p == "/api/quant/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("stat_arb_equity", "macro_rates_vol"):
                    self._json(400, {"error": "subsystem must be 'stat_arb_equity' or 'macro_rates_vol'"})
                    return
                info = inspect_quant_workspace(workspace)
                errs = check_quant_constraints(
                    info,
                    check_sa=(sub == "stat_arb_equity"),
                    check_mr=(sub == "macro_rates_vol"),
                    stage="full_risk_signoff",
                    check_oracle_canaries=False,
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = STATARB_STAGES if sub == "stat_arb_equity" else MACRO_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified cholesky_var_engine stages for {sub}: {unqual}")

                s = info.get("summary") or {}
                xlsx_sha = sha256_file(workspace / "quant_risk_desk" / "Prime_Risk_Pack.xlsx")
                exp_n = s.get("stat_arb_notional_musd", -1.0) if sub == "stat_arb_equity" else s.get("macro_rates_notional_musd", -1.0)
                exp_u = s.get("stat_arb_margin_util_pct", -1.0) if sub == "stat_arb_equity" else s.get("macro_rates_margin_util_pct", -1.0)
                try:
                    if abs(float(body.get("notional_musd", -999)) - exp_n) > 0.25:
                        errs.append(f"Submitted notional_musd != live {exp_n}")
                    if abs(float(body.get("margin_util_pct", -999)) - exp_u) > 0.35:
                        errs.append(f"Submitted margin_util_pct != live {exp_u}")
                    if str(body.get("xlsx_sha256") or "") != xlsx_sha:
                        errs.append("Submitted xlsx_sha256 != sha256(Prime_Risk_Pack.xlsx)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_RISK_SIGNOFF", "subsystem": sub, "errors": errs})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "notional_musd": exp_n,
                    "margin_util_pct": exp_u,
                    "xlsx_sha256": xlsx_sha,
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
    return audit_protocol_transparency(build_tickets_by_role(), PORTAL_HTML, REQUIRED_PUBLIC_TOKENS)


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    subs = portal_state.get("submissions") or {}
    sa_signed = (subs.get("stat_arb_equity") or {}).get("status") == "APPROVED"
    mr_signed = (subs.get("macro_rates_vol") or {}).get("status") == "APPROVED"
    closed_cnt = int(sa_signed) + int(mr_signed)

    info = inspect_quant_workspace(workspace)
    all_errs = check_quant_constraints(info, check_sa=True, check_mr=True, stage="full_risk_signoff", check_oracle_canaries=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "stat_arb_equity", STATARB_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "macro_rates_vol", MACRO_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()
    s = info.get("summary") or {}

    invariants = {
        "stat_arb_book_and_span_canaries_valid": bool(len(pur_a_errs) == 0 and sa_signed and info.get("ok") and not any("StatArb" in e or "STAT_ARB" in e for e in all_errs)),
        "macro_rates_book_and_span_canaries_valid": bool(len(pur_b_errs) == 0 and mr_signed and info.get("ok") and not any("MacroRates" in e or "MACRO_RATES" in e for e in all_errs)),
        "both_crowded_margin_caps_valid": bool(info.get("ok") and s.get("stat_arb_margin_util_pct", 999) <= MAX_MARGIN_UTIL_PCT and s.get("macro_rates_margin_util_pct", 999) <= MAX_MARGIN_UTIL_PCT),
        "workspace_clean_and_valid": bool(len(all_errs) == 0 and len(clean_errs) == 0),
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
        "quant_summary": s,
        "diagnostics": {
            "quant_and_canary_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("stat_arb_equity_lead", "macro_rates_vol_lead")
    qd = workspace / "quant_risk_desk"
    db_p = qd / "portfolio_positions.db"
    xp = qd / "Prime_Risk_Pack.xlsx"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_sa = (role == "stat_arb_equity_lead")
    dk = "STAT_ARB_EQUITY" if is_sa else "MACRO_RATES_VOL"
    sub = "stat_arb_equity" if is_sa else "macro_rates_vol"

    swept = {}
    for bkt in BUCKETS:
        r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"clearing": ("CME_CROSS_MARGIN_NET" if is_sa else "BILATERAL_GROSS"), "desk": dk, "bkt": bkt}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
        urllib.request.urlopen(r1, timeout=10).read()
        r2 = urllib.request.Request(f"{base}/api/ui/sweep_span", data=b"{}", headers=adm_hdr, method="POST")
        urllib.request.urlopen(r2, timeout=20).read()
        row = Path("/home/gui/Downloads/span_haircut.csv").read_text(encoding="utf-8").strip().splitlines()[-1].split(",")
        swept[bkt] = (float(row[1]), float(row[2]))

    with sqlite3.connect(str(db_p)) as conn:
        peer_dk = "MACRO_RATES_VOL" if is_sa else "STAT_ARB_EQUITY"
        pr = conn.execute("SELECT gross_notional_musd FROM desk_allocations WHERE desk = ?", (peer_dk,)).fetchone()
        peer_n = float(pr[0]) if pr else 20.0
        my_n = round(max(58.2, min(63.5, (98.6 - peer_n) / CROSS_CROWD_BETA, 98.6 - CROSS_CROWD_BETA * peer_n)), 2) if peer_n >= 58.0 else 61.2
        conn.execute("INSERT OR REPLACE INTO desk_allocations(desk, gross_notional_musd) VALUES (?, ?)", (dk, my_n))
        conn.commit()

    rows = [["Bucket", "Init_Margin_Bps", "Stress_VaR_Bps"]] + [[b, swept[b][0], swept[b][1]] for b in BUCKETS] + [["TOTAL", ("=SUM(B2:B5)", round(sum(swept[x][0] for x in BUCKETS), 2)), ("=SUM(C2:C5)", round(sum(swept[x][1] for x in BUCKETS), 2))]]
    update_single_sheet_xlsx(xp, "StatArb_Margin" if is_sa else "MacroRates_Margin", rows)

    stages = STATARB_STAGES if is_sa else MACRO_STAGES
    for stg in stages:
        code, resp = post_json(f"{base}/api/bench/cholesky_var_engine", {"subsystem": sub, "stage": stg}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {stg} failed: {resp}"

    s1 = inspect_quant_workspace(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/quant/submit", {
        "subsystem": sub,
        "notional_musd": s1["stat_arb_notional_musd"] if is_sa else s1["macro_rates_notional_musd"],
        "margin_util_pct": s1["stat_arb_margin_util_pct"] if is_sa else s1["macro_rates_margin_util_pct"],
        "xlsx_sha256": sha256_file(xp),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    qd = workspace / "quant_risk_desk"
    db_p = qd / "portfolio_positions.db"
    xp = qd / "Prime_Risk_Pack.xlsx"
    base = f"http://127.0.0.1:{portal_port}"
    solve_role("stat_arb_equity_lead", workspace, portal_port, strict=True)
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute("UPDATE desk_allocations SET gross_notional_musd = 63.0 WHERE desk = 'STAT_ARB_EQUITY'")
        conn.execute("UPDATE desk_allocations SET gross_notional_musd = 60.5 WHERE desk = 'MACRO_RATES_VOL'")
        conn.commit()
    rows = [["Bucket", "Init_Margin_Bps", "Stress_VaR_Bps"]] + [[b, TRUE_MACRORATES_SPAN[b][0]*1.175, TRUE_MACRORATES_SPAN[b][1]*1.175] for b in BUCKETS] + [["TOTAL", ("=SUM(B2:B5)", 400.0), ("=SUM(C2:C5)", 900.0)]]
    update_single_sheet_xlsx(xp, "MacroRates_Margin", rows)
    for stg in MACRO_STAGES:
        post_json(f"{base}/api/bench/cholesky_var_engine", {"subsystem": "macro_rates_vol", "stage": stg}, timeout_s=240)
    s1 = inspect_quant_workspace(workspace)["summary"]
    post_json(f"{base}/api/quant/submit", {"subsystem": "macro_rates_vol", "notional_musd": s1["macro_rates_notional_musd"], "margin_util_pct": s1["macro_rates_margin_util_pct"], "xlsx_sha256": sha256_file(xp)}, timeout_s=60)

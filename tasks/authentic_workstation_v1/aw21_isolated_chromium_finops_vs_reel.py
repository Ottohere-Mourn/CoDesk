"""AW-21: Isolated-Workspace Shared-Display StrataFin Cloud Recreation & 1080p FinOps Reel."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import functools
from http.cookies import SimpleCookie
import http.server
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
    launch_desktop_app_as_user,
    read_json_safe,
    resource_lock,
    write_json,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-21",
    "slug": "isolated_chromium_finops_vs_reel",
    "title": "StrataFin Cloud Staging Workstation: Zero-Spoiler Billing UI & VAT QA vs. Cluster RI Planner & 1080p Reel",
    "domain": "Enterprise FinOps Web Engineering & Media Production (Chromium + Inkscape 1.2 + FFmpeg + SQLite)",
    "track": "track1_isolated_ws",
    "workspace_mode": "isolated",
    "portal_port": 19621,
    "roles": ("design_qa_lead", "finops_demo_producer"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

FX_SF = {"USD": 1.0, "EUR": 1.08, "GBP": 1.26, "JPY": 0.0068}
EXPORT_HOTKEY = "Ctrl+Shift+E"
FRA_RUNBOOK_ID = "RB-STRATA-FRA94"

# (inv_id, country, b2b_vat_ok, currency, base_commit_local, overage_units, unit_rate_local, prior_rollover_local)
INVOICES = [
    ("INV-401", "DE", 1, "EUR", 40000.0, 1500, 12.0, 14000.0),
    ("INV-402", "FR", 0, "EUR", 28000.0, 800, 12.0, 4000.0),
    ("INV-403", "GB", 1, "GBP", 32000.0, 1400, 10.0, 9500.0),
    ("INV-404", "US", 1, "USD", 55000.0, 2200, 14.0, 10000.0),
    ("INV-405", "JP", 1, "JPY", 4800000.0, 1250, 1500.0, 1500000.0),
    ("INV-406", "NL", 1, "EUR", 36000.0, 950, 12.0, 6000.0),
]

# (cluster_id, region, term_type, committed_nodes, used_nodes, burst_nodes, ondemand_hr_usd, upfront_yr_usd, recurring_hr_usd)
CLUSTERS = [
    ("CLS-VA-01", "us-east-va", "standard_1yr", 40, 36, 0, 4.20, 438000.0, 1.50),
    ("CLS-FRA-02", "eu-central-fra", "convertible_1yr", 32, 32, 6, 4.80, 350400.0, 1.85),
    ("CLS-TYO-03", "ap-north-tyo", "standard_1yr", 24, 18, 0, 4.50, 262800.0, 1.60),
    ("CLS-DUB-04", "eu-west-dub", "convertible_1yr", 20, 20, 4, 4.40, 219000.0, 1.75),
]

TICKET_A = (
    "# Work Order — FinOps Billing & Design-System QA Lead (`design_qa_lead`)\n\n"
    "Explore every interactive surface of the **Billing & Tax Ledger** module inside **StrataFin Cloud** open in Chromium (`http://127.0.0.1:19621`), capture a verified desktop frame, audit the Q4 invoice ledger in `/workspace`, and recreate the **Billing & Tax Ledger** frontend:\n\n"
    "1. Read `/workspace/specs/FinOps_Billing_Policy.pdf` and query `/workspace/billing_invoices_q4.sqlite` (`invoices_q4`).\n"
    "2. In the open **Chromium** window (`StrataFin Cloud`), navigate to **Billing & Tax Ledger**, inspect its filter pills, `VAT & Tier Rules` modal, and `Audit Shortcuts` dialog, and click **Export Current View Frame** while the clean default desktop `Billing & Tax Ledger` view (no open modal, light surface) is active, copying the resulting PNG from `/home/user/Downloads/strata_view_capture.png` to `/workspace/captures/billing_desktop_1440x900.png`.\n"
    "3. Recreate the `Billing & Tax Ledger` view and its interactive filter/modal controls at `1440x900` inside `/workspace/recreated_billing/index.html` (`styles.css`, `app.js`).\n"
    "4. Compute 2-decimal USD invoice totals (`invoice_totals_usd`), `total_billed_usd`, and `eu_reverse_charge_ids` per policy, writing `/workspace/billing_audit.json` (`topbar_hex`, `rail_hex`, `export_hotkey`, `overage_discount_pct`, `eu_reverse_charge_ids`, `invoice_totals_usd`, `total_billed_usd`).\n"
)

TICKET_B = (
    "# Work Order — Cloud RI Planner & Executive Walkthrough Producer (`finops_demo_producer`)\n\n"
    "Explore every interactive surface of the **Cluster RI Planner** module inside **StrataFin Cloud** open in Chromium (`http://127.0.0.1:19621`), inspect the architecture SVG open in **Inkscape**, encode a `1440x900` H.264 walkthrough reel, and recreate the **Cluster RI Planner** frontend:\n\n"
    "1. Read `/workspace/specs/RI_Amortization_Manual.pdf`, query `/workspace/cluster_ri_telemetry.sqlite` (`ri_clusters`), and inspect `/workspace/arch/strata_arch_board.svg` (open in **Inkscape** on the desktop).\n"
    "2. In the open **Chromium** window (`StrataFin Cloud`), switch to **Cluster RI Planner**, inspect both sub-tabs (`Utilization Bars` and `Node Commitments`), open the `eu-central-fra` anomaly runbook drawer, and click **Export Current View Frame** while the clean default desktop `Cluster RI Planner` (`Utilization Bars`, no drawer, light surface) view is active, copying `/home/user/Downloads/strata_view_capture.png` to `/workspace/frames/ri_planner_live_1440x900.png`.\n"
    "3. Recreate the `Cluster RI Planner` view and its sub-tab/drawer controls at `1440x900` inside `/workspace/recreated_ri_planner/index.html` (`styles.css`, `app.js`), update `/workspace/arch/strata_arch_board.svg` to replace `RUNBOOK_PENDING` with the discovered `failover_runbook_id`, render `/workspace/frames/arch_card_1440x900.png` (`1440x900`) via `inkscape`, and encode `/workspace/reel/finops_walkthrough.mp4` (`1440x900` H.264 MP4, `8.0s..14.0s` total duration combining the architecture card and RI planner frames) via `ffmpeg`.\n"
    "4. Compute monthly cluster RI spend (`730` hrs/month), unused RI waste (`unused_ri_waste_usd`), and total monthly cloud spend (`total_monthly_spend_usd`), writing `/workspace/ri_amortization_audit.json` (`peak_region_id`, `peak_utilization_pct`, `failover_runbook_id`, `fra_committed_nodes`, `unused_ri_waste_usd`, `total_monthly_spend_usd`).\n"
)


def compute_aw21_oracle() -> dict[str, Any]:
    inv_usd: dict[str, float] = {}
    rc_ids: list[str] = []
    for iid, ctry, b2b, curr, bcom, u_ov, urate, rcred in INVOICES:
        elig_cred = min(rcred, 0.25 * bcom)
        ov_cost = min(u_ov, 1000) * urate + max(0, u_ov - 1000) * (0.80 * urate)
        sub_loc = bcom - elig_cred + ov_cost
        if ctry in ("DE", "FR", "NL") and b2b == 1:
            vat = 0.0
            rc_ids.append(iid)
        elif ctry in ("DE", "FR", "NL", "GB"):
            vat = 0.20
        elif ctry == "JP":
            vat = 0.10
        else:
            vat = 0.0
        inv_usd[iid] = round(sub_loc * (1.0 + vat) * FX_SF[curr], 2)

    tot_spend = 0.0
    tot_waste = 0.0
    for _cid, _reg, _tt, c_nodes, u_nodes, b_nodes, od_hr, up_yr, rec_hr in CLUSTERS:
        up_mo_per_node = (up_yr / 12.0) / c_nodes
        eff_node_mo = up_mo_per_node + rec_hr * 730.0
        unused_n = max(0, c_nodes - u_nodes)
        tot_waste += unused_n * eff_node_mo
        tot_spend += c_nodes * eff_node_mo + b_nodes * od_hr * 730.0

    return {
        "topbar_hex": "#0f172a",
        "rail_hex": "#1e293b",
        "export_hotkey": EXPORT_HOTKEY,
        "overage_discount_pct": 20,
        "eu_reverse_charge_ids": sorted(rc_ids),
        "invoice_totals_usd": inv_usd,
        "total_billed_usd": round(sum(inv_usd.values()), 2),
        "peak_region_id": "eu-central-fra",
        "peak_utilization_pct": 94,
        "failover_runbook_id": FRA_RUNBOOK_ID,
        "fra_committed_nodes": 32,
        "unused_ri_waste_usd": round(tot_waste, 2),
        "total_monthly_spend_usd": round(tot_spend, 2),
    }


def _render_portal_html(st: dict[str, Any], standalone: bool = False) -> str:
    mod = st.get("mod", "billing")
    flt = st.get("flt", "ALL")
    sub = st.get("sub", "bars")
    modal = st.get("modal", "")
    dark = bool(st.get("dark", False))

    bg_main = "#0b1120" if dark else "#f1f5f9"
    card_bg = "#1e293b" if dark else "#ffffff"
    txt_col = "#f8fafc" if dark else "#0f172a"

    if mod == "billing":
        rows_data = [
            ("INV-401", "DE", "EU_RC", "#2563eb", "EUR 40,000"),
            ("INV-402", "FR", "TAXED", "#16a34a", "EUR 28,000"),
            ("INV-403", "GB", "UK_VAT", "#d97706", "GBP 32,000"),
            ("INV-404", "US", "EXEMPT", "#475569", "USD 55,000"),
            ("INV-405", "JP", "JP_CT", "#0891b2", "JPY 4,800,000"),
            ("INV-406", "NL", "EU_RC", "#2563eb", "EUR 36,000"),
        ]
        vis_rows = [r for r in rows_data if flt == "ALL" or r[2] == flt]
        tr_html = "".join(
            f"<tr><td><b>{r[0]}</b></td><td>{r[1]}</td><td><span class='bdg' style='background:{r[3]};'>{r[2]}</span></td><td>{r[4]}</td></tr>"
            for r in vis_rows
        )
        stage = f"""
        <div class="kpis">
          <div class="kc" style="border-top:5px solid #2563eb;"><div>Q4 Commit Pipeline</div><div class="kv">$307.9K</div></div>
          <div class="kc" style="border-top:5px solid #16a34a;"><div>EU Reverse-Charge</div><div class="kv">2 Accts</div></div>
          <div class="kc" style="border-top:5px solid #d97706;"><div>Rollover Cap</div><div class="kv">25.0%</div></div>
          <div class="kc" style="border-top:5px solid #dc2626;"><div>Overage Tier &gt;1k</div><div class="kv">-20%</div></div>
        </div>
        <div style="margin-bottom:14px;">
          <a class="pill {'act' if flt=='ALL' else ''}" href="/ui?flt=ALL">ALL (6)</a>
          <a class="pill {'act' if flt=='EU_RC' else ''}" href="/ui?flt=EU_RC">EU_RC (2)</a>
          <a class="pill" href="/ui?modal=vat">VAT &amp; Tier Rules</a>
          <a class="pill" href="/ui?modal=hk">Audit Shortcuts</a>
        </div>
        <table><thead><tr><th>Invoice</th><th>Jurisdiction</th><th>Tax Regime</th><th>Base Commit</th></tr></thead><tbody>{tr_html}</tbody></table>
        """
    else:
        if sub == "bars":
            stage = """
            <div class="panel">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h2>Regional Cluster RI Utilization</h2>
                <div>
                  <a class="pill act" href="/ui?sub=bars">Utilization Bars</a>
                  <a class="pill" href="/ui?sub=nodes">Node Commitments</a>
                  <a class="pill" href="/ui?modal=drw">Open FRA Anomaly Runbook</a>
                </div>
              </div>
              <div style="margin-bottom:16px;"><div style="display:flex;justify-content:space-between;font-weight:700;"><span>us-east-va (CLS-VA-01)</span><span>90%</span></div><div class="barbg"><div style="width:90%;height:24px;background:#2563eb;border-radius:6px;"></div></div></div>
              <div style="margin-bottom:16px;"><div style="display:flex;justify-content:space-between;font-weight:700;color:#dc2626;"><span>eu-central-fra (CLS-FRA-02)</span><span>94%</span></div><div class="barbg"><div style="width:94%;height:24px;background:#dc2626;border-radius:6px;"></div></div></div>
              <div style="margin-bottom:16px;"><div style="display:flex;justify-content:space-between;font-weight:700;"><span>ap-north-tyo (CLS-TYO-03)</span><span>75%</span></div><div class="barbg"><div style="width:75%;height:24px;background:#10b981;border-radius:6px;"></div></div></div>
              <div><div style="display:flex;justify-content:space-between;font-weight:700;"><span>eu-west-dub (CLS-DUB-04)</span><span>88%</span></div><div class="barbg"><div style="width:88%;height:24px;background:#8b5cf6;border-radius:6px;"></div></div></div>
            </div>
            """
        else:
            stage = """
            <div class="panel">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h2>Committed RI Node Inventory</h2>
                <div>
                  <a class="pill" href="/ui?sub=bars">Utilization Bars</a>
                  <a class="pill act" href="/ui?sub=nodes">Node Commitments</a>
                </div>
              </div>
              <table><thead><tr><th>Cluster</th><th>Region</th><th>Committed Nodes</th><th>Used Nodes</th><th>Burst On-Demand</th></tr></thead><tbody>
                <tr><td>CLS-VA-01</td><td>us-east-va</td><td>40</td><td>36</td><td>0</td></tr>
                <tr><td>CLS-FRA-02</td><td>eu-central-fra</td><td>32</td><td>32</td><td>6</td></tr>
                <tr><td>CLS-TYO-03</td><td>ap-north-tyo</td><td>24</td><td>18</td><td>0</td></tr>
                <tr><td>CLS-DUB-04</td><td>eu-west-dub</td><td>20</td><td>20</td><td>4</td></tr>
              </tbody></table>
            </div>
            """

    ov_html = ""
    if modal == "vat":
        ov_html = """<div class="modal"><div class="mbox"><h3>VAT, FX &amp; Overage Tier Schedule</h3>
        <p>Spot FX: <code>USD=1.00, EUR=1.08, GBP=1.26, JPY=0.0068</code></p>
        <p>Rollover Cap: <code>25%</code> of base_commit_local | Overage &gt;1,000 units: <code>20%</code> discount (pay 80% of unit_rate_local)</p>
        <p>Tax: EU (DE/FR/NL) B2B=1 -&gt; <code>0%</code> reverse-charge; EU B2B=0 -&gt; <code>20%</code>; Post-Brexit UK (GB) -&gt; <code>20%</code>; JP -&gt; <code>10%</code>; US -&gt; <code>0%</code></p>
        <p style="margin-top:12px;"><a class="pill act" href="/ui?modal=none">Close</a></p></div></div>"""
    elif modal == "hk":
        ov_html = f"""<div class="modal"><div class="mbox"><h3>Billing Audit Keyboard Shortcuts</h3>
        <p>Ledger Batch Export Hotkey: <code>{EXPORT_HOTKEY}</code></p>
        <p style="margin-top:12px;"><a class="pill act" href="/ui?modal=none">Close</a></p></div></div>"""
    elif modal == "drw":
        ov_html = f"""<div class="drawer"><div style="background:#0f766e;color:#fff;padding:18px;font-weight:800;display:flex;justify-content:space-between;">
        <span>ANOMALY RUNBOOK | eu-central-fra</span><a style="color:#fff;" href="/ui?modal=none">Close</a></div>
        <div style="padding:20px;"><p>Runbook ID: <code>{FRA_RUNBOOK_ID}</code></p>
        <p>Shift 6 burst GPU inference replicas from eu-central-fra to eu-west-dub convertible pool.</p></div></div>"""

    cap_btn = "" if standalone else '<a href="/capture_frame" style="padding:7px 13px;background:#0284c7;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;">Export Current View Frame</a>'
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>StrataFin Cloud v5.4</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; font-family:DejaVu Sans,sans-serif; }}
  body {{ background:{bg_main}; color:{txt_col}; height:100vh; display:flex; flex-direction:column; overflow:hidden; }}
  #topbar {{ height:56px; background:#0f172a; color:#f8fafc; display:flex; align-items:center; justify-content:space-between; padding:0 22px; font-weight:800; }}
  #wrap {{ flex:1; display:flex; overflow:hidden; }}
  #rail {{ width:230px; background:#1e293b; color:#e2e8f0; padding:18px; display:flex; flex-direction:column; gap:10px; }}
  .nav {{ display:block; padding:11px 14px; border-radius:8px; color:#cbd5e1; text-decoration:none; font-weight:700; }}
  .nav.act {{ background:#2563eb; color:#ffffff; }}
  #stage {{ flex:1; padding:22px; overflow:auto; position:relative; }}
  .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:18px; }}
  .kc {{ background:{card_bg}; border:1px solid #cbd5e1; border-radius:10px; padding:16px; }}
  .kv {{ font-size:27px; font-weight:800; margin-top:6px; }}
  .panel {{ background:{card_bg}; border:1px solid #cbd5e1; border-radius:12px; padding:22px; }}
  .pill {{ display:inline-block; padding:7px 14px; border-radius:999px; border:1px solid #94a3b8; background:#fff; color:#0f172a; text-decoration:none; font-weight:700; margin-right:8px; }}
  .pill.act {{ background:#0f172a; color:#fff; border-color:#0f172a; }}
  .bdg {{ padding:4px 10px; border-radius:999px; color:#fff; font-size:12px; font-weight:700; }}
  .barbg {{ height:24px; background:#e2e8f0; border-radius:6px; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; background:{card_bg}; border:1px solid #cbd5e1; border-radius:10px; overflow:hidden; }}
  th, td {{ padding:12px 14px; border-bottom:1px solid #e2e8f0; text-align:left; font-size:13px; }}
  .modal {{ position:fixed; inset:0; background:rgba(15,23,42,0.62); display:flex; align-items:center; justify-content:center; z-index:50; }}
  .mbox {{ width:520px; background:#fff; color:#0f172a; padding:24px; border-radius:12px; line-height:1.65; }}
  .drawer {{ position:fixed; top:0; right:0; width:420px; height:100vh; background:#fff; color:#0f172a; box-shadow:-8px 0 24px rgba(0,0,0,0.3); z-index:45; }}
</style></head>
<body>
  <div id="topbar">
    <span>STRATAFIN CLOUD v5.4</span>
    <div style="display:flex;gap:10px;align-items:center;">
      <a href="/ui?toggle_dark=1" style="padding:7px 12px;background:#334155;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;">Toggle Dark Surface</a>
      {cap_btn}
    </div>
  </div>
  <div id="wrap">
    <div id="rail">
      <a class="nav {'act' if mod=='billing' else ''}" href="/ui?mod=billing">Billing &amp; Tax Ledger</a>
      <a class="nav {'act' if mod=='ri_planner' else ''}" href="/ui?mod=ri_planner">Cluster RI Planner</a>
    </div>
    <div id="stage">{stage}</div>
  </div>
  {ov_html}
</body></html>"""


def _shot_html_to_png(html_str: str, dst_png: Path) -> None:
    dst_png.parent.mkdir(parents=True, exist_ok=True)
    prof = Path(f"/tmp/aw21_sh_{secrets.token_hex(4)}")
    prof.mkdir(parents=True, exist_ok=True)
    hp = prof / "view.html"
    hp.write_text(html_str, encoding="utf-8")
    try:
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}", "--window-size=1440,900",
                f"--screenshot={dst_png}", f"file://{hp}",
            ],
            check=True, capture_output=True, timeout=25,
        )
    finally:
        shutil.rmtree(prof, ignore_errors=True)


INIT_ARCH_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">
  <rect x="0" y="0" width="1440" height="900" fill="#0f172a"/>
  <rect x="80" y="80" width="1280" height="740" rx="18" fill="#1e293b" stroke="#38bdf8" stroke-width="4"/>
  <text x="140" y="200" fill="#f8fafc" font-family="DejaVu Sans" font-size="42" font-weight="bold">StrataFin Multi-Region RI Architecture</text>
  <text x="140" y="310" fill="#38bdf8" font-family="DejaVu Sans" font-size="30">Active Anomaly Runbook: RUNBOOK_PENDING</text>
</svg>
"""


def build(workspace_root: Path, tickets_root: Path) -> None:
    ws_a = workspace_root / "design_qa_lead"
    ws_b = workspace_root / "finops_demo_producer"
    for d in (ws_a / "specs", ws_a / "captures", ws_a / "recreated_billing", ws_b / "specs", ws_b / "arch", ws_b / "frames", ws_b / "reel", ws_b / "recreated_ri_planner"):
        d.mkdir(parents=True, exist_ok=True)

    db_a = ws_a / "billing_invoices_q4.sqlite"
    db_a.unlink(missing_ok=True)
    con_a = sqlite3.connect(db_a)
    con_a.execute(
        "CREATE TABLE invoices_q4 (invoice_id TEXT PRIMARY KEY, country TEXT, b2b_vat_verified INTEGER, currency TEXT, base_commit_local REAL, overage_units INTEGER, unit_rate_local REAL, prior_rollover_local REAL)"
    )
    con_a.executemany("INSERT INTO invoices_q4 VALUES (?,?,?,?,?,?,?,?)", INVOICES)
    con_a.commit()
    con_a.close()

    (ws_a / "recreated_billing" / "index.html").write_text("<!doctype html><html><body>TODO Billing Recreation</body></html>\n", encoding="utf-8")
    (ws_a / "recreated_billing" / "styles.css").write_text("body { margin: 0; }\n", encoding="utf-8")
    (ws_a / "recreated_billing" / "app.js").write_text("// Billing recreation\n", encoding="utf-8")

    write_pdf_manual(
        ws_a / "specs" / "FinOps_Billing_Policy.pdf",
        "StrataFin Q4 Enterprise Billing, Rollover & VAT Policy",
        [
            (
                "1. Committed Rollover Cap & Tiered Overage Pricing",
                [
                    "Inspect the VAT & Tier Rules modal inside StrataFin Cloud (Billing & Tax Ledger) for spot FX rates, the prior_rollover_local cap (% of base_commit_local), and the discount applied to overage_units above 1,000 units.",
                    "Taxable local subtotal = base_commit_local - eligible_rollover_local + tiered_overage_local. Apply jurisdiction VAT/consumption tax from the modal (noting EU B2B reverse-charge vs post-Brexit GB rules), convert at Portal FX, and round each invoice USD total to 2 decimals.",
                ],
            ),
        ],
    )

    db_b = ws_b / "cluster_ri_telemetry.sqlite"
    db_b.unlink(missing_ok=True)
    con_b = sqlite3.connect(db_b)
    con_b.execute(
        "CREATE TABLE ri_clusters (cluster_id TEXT PRIMARY KEY, region TEXT, term_type TEXT, committed_nodes INTEGER, used_nodes INTEGER, burst_ondemand_nodes INTEGER, ondemand_hr_usd REAL, upfront_annual_usd REAL, recurring_hr_usd REAL)"
    )
    con_b.executemany("INSERT INTO ri_clusters VALUES (?,?,?,?,?,?,?,?,?)", CLUSTERS)
    con_b.commit()
    con_b.close()

    (ws_b / "arch" / "strata_arch_board.svg").write_text(INIT_ARCH_SVG, encoding="utf-8")
    (ws_b / "recreated_ri_planner" / "index.html").write_text("<!doctype html><html><body>TODO RI Planner Recreation</body></html>\n", encoding="utf-8")
    (ws_b / "recreated_ri_planner" / "styles.css").write_text("body { margin: 0; }\n", encoding="utf-8")
    (ws_b / "recreated_ri_planner" / "app.js").write_text("// RI planner recreation\n", encoding="utf-8")

    write_pdf_manual(
        ws_b / "specs" / "RI_Amortization_Manual.pdf",
        "StrataFin Monthly RI Amortization & Unused Capacity Accounting",
        [
            (
                "1. Monthly 730-Hour RI Amortization & Unused Waste",
                [
                    "Monthly amortized cost per committed node = (upfront_annual_usd / 12.0) / committed_nodes + recurring_hr_usd * 730.0.",
                    "All committed_nodes are billed every month regardless of utilization; unused_ri_waste_usd sums max(0, committed_nodes - used_nodes) * monthly_node_cost across all 4 clusters (rounded to 2 decimals).",
                    "total_monthly_spend_usd = sum(committed_nodes * monthly_node_cost + burst_ondemand_nodes * ondemand_hr_usd * 730.0) rounded to 2 decimals.",
                ],
            ),
        ],
    )

    (tickets_root / "design_qa_lead").mkdir(parents=True, exist_ok=True)
    (tickets_root / "finops_demo_producer").mkdir(parents=True, exist_ok=True)
    (tickets_root / "design_qa_lead" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "finops_demo_producer" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"mod": "billing", "flt": "ALL", "sub": "bars", "modal": "", "dark": False, "switches": 0, "captures": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw21_sess" in ck) and (ck["aw21_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw21_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 StrataFin Session Required</h3>")
                return
            if parsed.path == "/ui":
                with lock:
                    if "mod" in qs and qs["mod"][0] in ("billing", "ri_planner"):
                        if qs["mod"][0] != state["mod"]:
                            state["switches"] = int(state["switches"]) + 1
                        state["mod"] = qs["mod"][0]
                        state["modal"] = ""
                    if "flt" in qs and qs["flt"][0] in ("ALL", "EU_RC"):
                        state["flt"] = qs["flt"][0]
                    if "sub" in qs and qs["sub"][0] in ("bars", "nodes"):
                        state["sub"] = qs["sub"][0]
                    if "modal" in qs:
                        mv = qs["modal"][0]
                        state["modal"] = "" if mv == "none" else mv
                    if "toggle_dark" in qs:
                        state["dark"] = not bool(state["dark"])
                    write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            if parsed.path == "/capture_frame":
                with lock:
                    snap = dict(state)
                    state["captures"] = int(state["captures"]) + 1
                    write_json(state_file, state)
                dl = Path("/home/user/Downloads/strata_view_capture.png")
                _shot_html_to_png(_render_portal_html(snap, standalone=True), dl)
                subprocess.run(["chmod", "644", str(dl)], capture_output=True, timeout=5)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur_html = _render_portal_html(dict(state), standalone=False)
            self._send(200, cur_html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1440, 900))
    if "finops_demo_producer" in roles:
        svg_p = workspace_root / "finops_demo_producer" / "arch" / "strata_arch_board.svg"
        if svg_p.is_file():
            launch_desktop_app_as_user(f"nohup inkscape '{svg_p}' >/tmp/aw21_ink.log 2>&1 </dev/null &", wait_s=2.0)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    ora = compute_aw21_oracle()
    dl = Path("/home/user/Downloads/strata_view_capture.png")
    if role == "design_qa_lead":
        ws_a = workspace_root / "design_qa_lead"
        html_a = _render_portal_html({"mod": "billing", "flt": "ALL", "sub": "bars", "modal": "", "dark": False}, standalone=True)
        (ws_a / "recreated_billing" / "index.html").write_text(
            html_a + f"\n<!-- INV-401 INV-403 INV-406 {EXPORT_HOTKEY} 20% -->\n",
            encoding="utf-8",
        )
        if cooperative:
            with resource_lock("aw21_cap"):
                _shot_html_to_png(html_a, dl)
                shutil.copy2(dl, ws_a / "captures" / "billing_desktop_1440x900.png")
        else:
            # Uncoordinated capture happens while peer switched browser to dark RI modal!
            bad = _render_portal_html({"mod": "ri_planner", "flt": "ALL", "sub": "bars", "modal": "drw", "dark": True}, standalone=True)
            _shot_html_to_png(bad, ws_a / "captures" / "billing_desktop_1440x900.png")
        write_json(
            ws_a / "billing_audit.json",
            {
                "topbar_hex": ora["topbar_hex"],
                "rail_hex": ora["rail_hex"],
                "export_hotkey": ora["export_hotkey"],
                "overage_discount_pct": ora["overage_discount_pct"],
                "eu_reverse_charge_ids": ora["eu_reverse_charge_ids"],
                "invoice_totals_usd": ora["invoice_totals_usd"],
                "total_billed_usd": ora["total_billed_usd"],
            },
        )
    elif role == "finops_demo_producer":
        ws_b = workspace_root / "finops_demo_producer"
        html_b = _render_portal_html({"mod": "ri_planner", "flt": "ALL", "sub": "bars", "modal": "", "dark": False}, standalone=True)
        (ws_b / "recreated_ri_planner" / "index.html").write_text(
            html_b + f"\n<!-- CLS-FRA-02 {FRA_RUNBOOK_ID} 32 -->\n",
            encoding="utf-8",
        )
        svg_p = ws_b / "arch" / "strata_arch_board.svg"
        svg_p.write_text(INIT_ARCH_SVG.replace("RUNBOOK_PENDING", FRA_RUNBOOK_ID), encoding="utf-8")
        arch_png = ws_b / "frames" / "arch_card_1440x900.png"
        ri_png = ws_b / "frames" / "ri_planner_live_1440x900.png"
        subprocess.run(["inkscape", str(svg_p), "--export-type=png", f"--export-filename={arch_png}", "-w", "1440", "-h", "900"], check=True, capture_output=True, timeout=30)
        if cooperative:
            with resource_lock("aw21_cap"):
                _shot_html_to_png(html_b, dl)
                shutil.copy2(dl, ri_png)
        else:
            bad_b = _render_portal_html({"mod": "billing", "flt": "EU_RC", "sub": "bars", "modal": "vat", "dark": True}, standalone=True)
            _shot_html_to_png(bad_b, ri_png)
        mp4_p = ws_b / "reel" / "finops_walkthrough.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-t", "5", "-i", str(arch_png),
                "-loop", "1", "-t", "5", "-i", str(ri_png),
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
                "-map", "[v]", "-c:v", "libx264", "-r", "24", str(mp4_p),
            ],
            check=True, capture_output=True, timeout=45,
        )
        write_json(
            ws_b / "ri_amortization_audit.json",
            {
                "peak_region_id": ora["peak_region_id"],
                "peak_utilization_pct": ora["peak_utilization_pct"],
                "failover_runbook_id": ora["failover_runbook_id"],
                "fra_committed_nodes": ora["fra_committed_nodes"],
                "unused_ri_waste_usd": ora["unused_ri_waste_usd"],
                "total_monthly_spend_usd": ora["total_monthly_spend_usd"],
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("design_qa_lead", workspace_root, cooperative=False)
    solve_role("finops_demo_producer", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "design_qa_lead", workspace_root, True)
        fb = pool.submit(solve_role, "finops_demo_producer", workspace_root, True)
        fa.result()
        fb.result()


def _img_sim(cand_png: Path, ref_html_str: str) -> tuple[bool, float]:
    from PIL import Image

    if not cand_png.is_file():
        return False, 0.0
    ref_tmp = Path(f"/tmp/aw21_ref_{secrets.token_hex(4)}.png")
    try:
        im_c0 = Image.open(cand_png).convert("RGB")
        sz_ok = im_c0.size == (1440, 900)
        _shot_html_to_png(ref_html_str, ref_tmp)
        im_c = im_c0.resize((240, 150))
        im_r = Image.open(ref_tmp).convert("RGB").resize((240, 150))
        err = sum(
            (abs(im_c.getpixel((x, y))[0] - im_r.getpixel((x, y))[0]) + abs(im_c.getpixel((x, y))[1] - im_r.getpixel((x, y))[1]) + abs(im_c.getpixel((x, y))[2] - im_r.getpixel((x, y))[2])) / (3.0 * 255.0)
            for y in range(150)
            for x in range(240)
        ) / (240.0 * 150.0)
        return sz_ok, round(max(0.0, 1.0 - err * 2.8), 4)
    except Exception:
        return False, 0.0
    finally:
        ref_tmp.unlink(missing_ok=True)


def _eval_recreated_dir(app_dir: Path, ref_html_str: str) -> float:
    if not (app_dir / "index.html").is_file():
        return 0.0
    cand_tmp = Path(f"/tmp/aw21_cand_{secrets.token_hex(4)}.png")
    handler_cls = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(app_dir))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    ep = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    prof = Path(f"/tmp/aw21_pr_{secrets.token_hex(4)}")
    prof.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}", "--window-size=1440,900",
                f"--screenshot={cand_tmp}", f"http://127.0.0.1:{ep}/index.html",
            ],
            capture_output=True, timeout=25,
        )
        _sz, sim = _img_sim(cand_tmp, ref_html_str)
        return sim
    finally:
        srv.shutdown()
        srv.server_close()
        cand_tmp.unlink(missing_ok=True)
        shutil.rmtree(prof, ignore_errors=True)


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    ws_a = workspace_root / "design_qa_lead"
    ws_b = workspace_root / "finops_demo_producer"
    ora = compute_aw21_oracle()

    ja = read_json_safe(ws_a / "billing_audit.json")
    jb = read_json_safe(ws_b / "ri_amortization_audit.json")

    ref_a = _render_portal_html({"mod": "billing", "flt": "ALL", "sub": "bars", "modal": "", "dark": False}, standalone=True)
    ref_b = _render_portal_html({"mod": "ri_planner", "flt": "ALL", "sub": "bars", "modal": "", "dark": False}, standalone=True)

    cap_a_sz, cap_a_sim = _img_sim(ws_a / "captures" / "billing_desktop_1440x900.png", ref_a)
    cap_b_sz, cap_b_sim = _img_sim(ws_b / "frames" / "ri_planner_live_1440x900.png", ref_b)
    rec_a_sim = _eval_recreated_dir(ws_a / "recreated_billing", ref_a)
    rec_b_sim = _eval_recreated_dir(ws_b / "recreated_ri_planner", ref_b)

    src_a = "\n".join((ws_a / "recreated_billing" / fn).read_text(encoding="utf-8", errors="replace") for fn in ("index.html", "styles.css", "app.js") if (ws_a / "recreated_billing" / fn).is_file())
    src_b = "\n".join((ws_b / "recreated_ri_planner" / fn).read_text(encoding="utf-8", errors="replace") for fn in ("index.html", "styles.css", "app.js") if (ws_b / "recreated_ri_planner" / fn).is_file())
    svg_txt = (ws_b / "arch" / "strata_arch_board.svg").read_text(encoding="utf-8", errors="replace") if (ws_b / "arch" / "strata_arch_board.svg").is_file() else ""

    mp4_p = ws_b / "reel" / "finops_walkthrough.mp4"
    mp4_ok = False
    if mp4_p.is_file() and mp4_p.stat().st_size > 5000:
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height:format=duration", "-of", "json", str(mp4_p)],
            capture_output=True, text=True, timeout=15,
        )
        if pr.returncode == 0:
            try:
                inf = json.loads(pr.stdout)
                s0 = (inf.get("streams") or [{}])[0]
                dur = float((inf.get("format") or {}).get("duration") or 0.0)
                mp4_ok = s0.get("codec_name") == "h264" and int(s0.get("width", 0)) == 1440 and int(s0.get("height", 0)) == 900 and 7.5 <= dur <= 15.0
            except Exception:
                mp4_ok = False

    def _close(v: Any, exp: float, tol: float = 0.5) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    inv_got = ja.get("invoice_totals_usd") if isinstance(ja.get("invoice_totals_usd"), dict) else {}
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_modals_meta", str(ja.get("export_hotkey", "")).strip() == EXPORT_HOTKEY and ja.get("overage_discount_pct") == 20 and sorted(ja.get("eu_reverse_charge_ids") or []) == ora["eu_reverse_charge_ids"], 1.8, "Billing modal metadata / EU reverse-charge IDs mismatch"),
        *[(f"a_{iid.lower()}", _close(inv_got.get(iid), exp_v, 0.25), 0.7, f"{iid} USD total mismatch (expected {exp_v})") for iid, exp_v in ora["invoice_totals_usd"].items()],
        ("a_tot_billed", _close(ja.get("total_billed_usd"), ora["total_billed_usd"], 1.0), 1.6, f"total_billed_usd mismatch ({ora['total_billed_usd']})"),
        ("a_live_frame", cap_a_sz and cap_a_sim >= 0.94, 2.0, f"billing_desktop_1440x900.png corrupted by modal/dark/module switch (sim={cap_a_sim})"),
        ("a_rec_src", all(k in src_a for k in ("INV-401", "INV-403", "INV-406")), 1.4, "Recreated Billing bundle missing invoice rows"),
        ("a_rec_vis", rec_a_sim >= 0.85, 1.8, f"Recreated Billing visual similarity < 0.85 ({rec_a_sim})"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_drawer_meta", jb.get("failover_runbook_id") == FRA_RUNBOOK_ID and jb.get("peak_utilization_pct") == 94 and jb.get("fra_committed_nodes") == 32, 1.8, "RI runbook / committed nodes metadata mismatch"),
        ("b_ri_waste", _close(jb.get("unused_ri_waste_usd"), ora["unused_ri_waste_usd"], 2.0), 1.8, f"unused_ri_waste_usd mismatch ({ora['unused_ri_waste_usd']})"),
        ("b_ri_spend", _close(jb.get("total_monthly_spend_usd"), ora["total_monthly_spend_usd"], 3.0), 1.8, f"total_monthly_spend_usd mismatch ({ora['total_monthly_spend_usd']})"),
        ("b_live_frame", cap_b_sz and cap_b_sim >= 0.94, 2.0, f"ri_planner_live_1440x900.png corrupted by modal/dark/module switch (sim={cap_b_sim})"),
        ("b_svg_mp4", FRA_RUNBOOK_ID in svg_txt and mp4_ok, 1.8, "strata_arch_board.svg missing runbook ID or finops_walkthrough.mp4 invalid"),
        ("b_rec_src_vis", "CLS-FRA-02" in src_b and rec_b_sim >= 0.85, 1.8, f"Recreated RI Planner missing data or visual similarity < 0.85 ({rec_b_sim})"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_both_live_frames_unclobbered_and_reels_valid",
            cap_a_sz and cap_a_sim >= 0.94 and cap_b_sz and cap_b_sim >= 0.94 and mp4_ok,
            2.5,
            "Shared StrataFin Cloud Chromium session clobbered live module/theme/modal captures across concurrent roles",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"design_qa_lead": TICKET_A, "finops_demo_producer": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

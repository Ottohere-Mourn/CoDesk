"""AW-12: Zero-Spoiler 8-State Enterprise ERP Modular SPA Recreation from Live Chromium."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import functools
from http.cookies import SimpleCookie
import http.server
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    read_json_safe,
    resource_lock,
    write_json,
)

TASK_META: dict[str, Any] = {
    "id": "AW-12",
    "slug": "chromium_zerospoiler_suite_recreation",
    "title": "Zero-Spoiler 8-State Chronos ERP Modular SPA Recreation: Fulfillment Desk vs. Capacity & Failover Planner",
    "domain": "Interactive Web UI Exploration & Modular Frontend Engineering (Chromium + HTML5/CSS3/JS)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19612,
    "roles": ("orders_ui_eng", "capacity_ui_eng"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

TICKET_A = (
    "# Work Order — Fulfillment & SLA Frontend Engineer (`orders_ui_eng`)\n\n"
    "Explore every interactive control, filter pill, popover, and header shortcut dialog inside the **Orders & SLA** module of the live **Chronos ERP** application open in Chromium (`http://127.0.0.1:19612`), and implement the Orders route module inside `/workspace/chronos_suite`:\n\n"
    "1. Use the desktop GUI driver to click through all interactive buttons, filter pills (`ALL`, `HOLD_CUSTOMS`, `CHILLED_QA`), the `SLA Penalties` popover, and the `Shortcuts (?)` modal in the **Orders & SLA** view of Chromium.\n"
    "2. Implement `/workspace/chronos_suite/modules/orders_module.js` and wire it cleanly into the shared SPA shell (`/workspace/chronos_suite/index.html` and `styles.css`, preserving `<script src=\"modules/capacity_module.js\"></script>` and `#nav-capacity`!) so that loading `index.html` at `1440x900` renders the default **Orders & SLA** view (`#nav-orders`) and clicking `#filter-hold` filters to `HOLD_CUSTOMS` rows.\n"
    "3. Write `/workspace/chronos_suite/orders_discovery.json` with:\n"
    "   - `topbar_hex`, `rail_hex`, `hold_order_ids` (sorted list), `tier_a_penalty_usd_hr` (int), `shortcut_export_hotkey` (string)\n"
)

TICKET_B = (
    "# Work Order — Capacity & Failover Planner Frontend Engineer (`capacity_ui_eng`)\n\n"
    "Explore every interactive sub-tab, regional bar action, slide-over failover runbook drawer, and dark-surface toggle inside the **Capacity Planner** module of the live **Chronos ERP** application open in Chromium (`http://127.0.0.1:19612`), and implement the Capacity route module inside `/workspace/chronos_suite`:\n\n"
    "1. Switch to **Capacity Planner** in the left navigation rail of Chromium and click through `Utilization Bars`, `vCPU Quotas`, `Toggle Dark Surface`, and the clickable `eu-central-fra` utilization bar that opens the slide-over failover runbook drawer.\n"
    "2. Implement `/workspace/chronos_suite/modules/capacity_module.js` and wire it cleanly into the shared SPA shell (`/workspace/chronos_suite/index.html` and `styles.css`, preserving `<script src=\"modules/orders_module.js\"></script>` and `#nav-orders`!) so that clicking `#nav-capacity` at `1440x900` renders **Capacity Planner** and clicking `#open-drawer-eu` opens the failover runbook drawer.\n"
    "3. Write `/workspace/chronos_suite/capacity_discovery.json` with:\n"
    "   - `peak_region_id` (string), `peak_utilization_pct` (int), `failover_runbook_id` (string), `eu_reserved_vcpu_quota` (int), `drawer_banner_hex`\n"
)

SHELL_CSS = """* { box-sizing: border-box; margin: 0; padding: 0; font-family: DejaVu Sans, sans-serif; }
body { background: #f1f5f9; color: #0f172a; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
#topbar { height: 54px; background: #111827; color: #f8fafc; display: flex; align-items: center; justify-content: space-between; padding: 0 22px; font-weight: 800; }
#layout { flex: 1; display: flex; overflow: hidden; }
#rail { width: 224px; background: #1e293b; color: #e2e8f0; padding: 18px; display: flex; flex-direction: column; gap: 10px; }
.nav-btn { padding: 11px 14px; border-radius: 8px; border: none; text-align: left; font-weight: 700; font-size: 14px; cursor: pointer; background: transparent; color: #cbd5e1; text-decoration: none; display: block; }
.nav-btn.active { background: #2563eb; color: #ffffff; }
#stage { flex: 1; padding: 22px; overflow: auto; position: relative; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.kpi-card { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 16px; }
.kpi-val { font-size: 28px; font-weight: 800; margin-top: 6px; }
.pill { padding: 7px 14px; border-radius: 999px; border: 1px solid #94a3b8; background: #ffffff; color: #0f172a; font-weight: 700; cursor: pointer; margin-right: 8px; text-decoration: none; display: inline-block; font-size: 13px; }
.pill.active { background: #0f172a; color: #ffffff; border-color: #0f172a; }
.badge { padding: 4px 10px; border-radius: 999px; color: #fff; font-size: 12px; font-weight: 700; }
table { width: 100%; border-collapse: collapse; background: #ffffff; border-radius: 10px; overflow: hidden; border: 1px solid #cbd5e1; }
th, td { padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: left; font-size: 13px; }
th { background: #f8fafc; font-weight: 700; }
.compact-dark #cap-surface { background: #0f172a !important; color: #f8fafc !important; }
"""

REF_ORDERS_JS = """window.ChronosOrders = (function() {
  const ORDERS = [
    {id:'ORD-901', region:'DE-FRA', status:'DISPATCHED', color:'#16a34a', val:'$48,200', carrier:'DHL ColdChain'},
    {id:'ORD-904', region:'CH-ZRH', status:'HOLD_CUSTOMS', color:'#dc2626', val:'$91,500', carrier:'SwissFreight'},
    {id:'ORD-907', region:'FR-PAR', status:'CHILLED_QA', color:'#2563eb', val:'$34,800', carrier:'ChronoMed'},
    {id:'ORD-909', region:'NL-AMS', status:'DISPATCHED', color:'#16a34a', val:'$62,100', carrier:'EuroLink'},
    {id:'ORD-911', region:'GB-LON', status:'HOLD_CUSTOMS', color:'#dc2626', val:'$77,400', carrier:'ChannelCargo'},
    {id:'ORD-915', region:'SE-STO', status:'CHILLED_QA', color:'#2563eb', val:'$29,600', carrier:'NordicBio'}
  ];
  let filter = 'ALL';
  function render(stage) {
    const rows = ORDERS.filter(r => filter === 'ALL' || r.status === filter);
    stage.innerHTML = `<div class="kpi-grid">
      <div class="kpi-card" style="border-top:4px solid #2563eb;"><div>GMV Pipeline</div><div class="kpi-val">$1.42M</div></div>
      <div class="kpi-card" style="border-top:4px solid #16a34a;"><div>On-Time SLA</div><div class="kpi-val">98.7%</div></div>
      <div class="kpi-card" style="border-top:4px solid #dc2626;"><div>Customs Holds</div><div class="kpi-val">2</div></div>
      <div class="kpi-card" style="border-top:4px solid #d97706;"><div>Median Dispatch</div><div class="kpi-val">22.4m</div></div>
    </div>
    <div style="margin-bottom:14px;">
      <button id="filter-all" class="pill ${filter==='ALL'?'active':''}" onclick="window.ChronosOrders.setFilter('ALL')">ALL (6)</button>
      <button id="filter-hold" class="pill ${filter==='HOLD_CUSTOMS'?'active':''}" onclick="window.ChronosOrders.setFilter('HOLD_CUSTOMS')">HOLD_CUSTOMS (2)</button>
      <button id="filter-qa" class="pill ${filter==='CHILLED_QA'?'active':''}" onclick="window.ChronosOrders.setFilter('CHILLED_QA')">CHILLED_QA (2)</button>
    </div>
    <table><thead><tr><th>Order ID</th><th>Hub</th><th>Status</th><th>Value</th><th>Carrier</th></tr></thead><tbody>` +
    rows.map(r => `<tr><td><b>${r.id}</b></td><td>${r.region}</td><td><span class="badge" style="background:${r.color};">${r.status}</span></td><td>${r.val}</td><td>${r.carrier}</td></tr>`).join('') +
    `</tbody></table><!-- $450/hr Alt+Shift+M -->`;
  }
  return { render, setFilter(f) { filter = f; window.renderChronos(); } };
})();
"""

REF_CAPACITY_JS = """window.ChronosCapacity = (function() {
  let capTab = 'bars', drawerOpen = false, darkCap = false;
  function render(stage) {
    document.body.className = darkCap ? 'compact-dark' : '';
    let h = `<div id="cap-surface" style="background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;padding:22px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
        <h2>Regional Compute &amp; Fulfillment Capacity</h2>
        <div>
          <button id="subtab-bars" class="pill ${capTab==='bars'?'active':''}" onclick="window.ChronosCapacity.setTab('bars')">Utilization Bars</button>
          <button id="subtab-quotas" class="pill ${capTab==='quotas'?'active':''}" onclick="window.ChronosCapacity.setTab('quotas')">vCPU Quotas</button>
          <button id="toggle-compact" class="pill" onclick="window.ChronosCapacity.toggleDark()">Toggle Dark Surface</button>
        </div>
      </div>`;
    if (capTab === 'bars') {
      h += `<div style="display:flex;flex-direction:column;gap:16px;margin-bottom:20px;">
        <div><div style="display:flex;justify-content:space-between;font-weight:700;"><span>us-east-va</span><span>84%</span></div><div style="height:22px;background:#e2e8f0;border-radius:6px;"><div style="width:84%;height:22px;background:#2563eb;border-radius:6px;"></div></div></div>
        <div id="open-drawer-eu" onclick="window.ChronosCapacity.setDrawer(true)" style="cursor:pointer;"><div style="display:flex;justify-content:space-between;font-weight:700;color:#dc2626;"><span>eu-central-fra (Click for Failover Runbook)</span><span>93%</span></div><div style="height:22px;background:#fee2e2;border-radius:6px;"><div style="width:93%;height:22px;background:#dc2626;border-radius:6px;"></div></div></div>
        <div><div style="display:flex;justify-content:space-between;font-weight:700;"><span>ap-north-tyo</span><span>61%</span></div><div style="height:22px;background:#e2e8f0;border-radius:6px;"><div style="width:61%;height:22px;background:#10b981;border-radius:6px;"></div></div></div>
      </div>`;
    } else {
      h += `<table><thead><tr><th>Cluster</th><th>Reserved vCPU Quota</th><th>Burst Ceiling</th></tr></thead><tbody>
        <tr><td>us-east-va</td><td>4800</td><td>6000</td></tr>
        <tr><td>eu-central-fra</td><td>6400</td><td>7200</td></tr>
        <tr><td>ap-north-tyo</td><td>3200</td><td>4400</td></tr>
      </tbody></table>`;
    }
    h += `</div><!-- 6400 RB-FAILOVER-EU93 nl-ams-standby -->`;
    if (drawerOpen) {
      h += `<div id="remediation-drawer" style="position:fixed;top:0;right:0;width:420px;height:100vh;background:#ffffff;color:#0f172a;box-shadow:-8px 0 24px rgba(0,0,0,0.28);z-index:40;">
        <div style="background:#0f766e;color:#ffffff;padding:18px;font-weight:800;display:flex;justify-content:space-between;">
          <span>FAILOVER RUNBOOK | eu-central-fra</span><button onclick="window.ChronosCapacity.setDrawer(false)" style="background:none;border:none;color:#fff;font-weight:800;cursor:pointer;">X</button>
        </div>
        <div style="padding:20px;line-height:1.7;">
          <p><b>Runbook ID:</b> <code>RB-FAILOVER-EU93</code></p>
          <p>Drain 35% of Kafka partitions from <code>eu-central-fra</code> to <code>nl-ams-standby</code> when utilization exceeds 90%.</p>
        </div>
      </div>`;
    }
    stage.innerHTML = h;
  }
  return { render, setTab(t) { capTab = t; window.renderChronos(); }, setDrawer(v) { drawerOpen = v; window.renderChronos(); }, toggleDark() { darkCap = !darkCap; window.renderChronos(); } };
})();
"""

REF_INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"/><title>Chronos Cloud ERP v6.2</title>
<link rel="stylesheet" href="styles.css"/></head>
<body>
  <div id="topbar">
    <span>CHRONOS CLOUD ERP v6.2</span>
    <div style="display:flex;gap:10px;">
      <button id="btn-sla-popover" onclick="window.toggleSla && window.toggleSla()" style="padding:6px 12px;border-radius:6px;background:#1d4ed8;color:#fff;border:none;font-weight:700;cursor:pointer;">SLA Penalties</button>
      <button id="btn-shortcuts" onclick="window.toggleShortcuts && window.toggleShortcuts()" style="padding:6px 12px;border-radius:6px;background:#334155;color:#fff;border:none;font-weight:700;cursor:pointer;">Shortcuts (?)</button>
    </div>
  </div>
  <div id="layout">
    <div id="rail">
      <button id="nav-orders" class="nav-btn active" onclick="window.setChronosMod('orders')">Orders &amp; SLA</button>
      <button id="nav-capacity" class="nav-btn" onclick="window.setChronosMod('capacity')">Capacity Planner</button>
    </div>
    <div id="stage"></div>
  </div>
  <script src="modules/orders_module.js"></script>
  <script src="modules/capacity_module.js"></script>
  <script>
    window.chronosMod = 'orders';
    window.setChronosMod = function(m) { window.chronosMod = m; window.renderChronos(); };
    window.renderChronos = function() {
      document.getElementById('nav-orders').className = 'nav-btn' + (window.chronosMod==='orders'?' active':'');
      document.getElementById('nav-capacity').className = 'nav-btn' + (window.chronosMod==='capacity'?' active':'');
      const st = document.getElementById('stage');
      if (window.chronosMod === 'orders' && window.ChronosOrders) window.ChronosOrders.render(st);
      else if (window.chronosMod === 'capacity' && window.ChronosCapacity) window.ChronosCapacity.render(st);
    };
    window.renderChronos();
  </script>
</body></html>
"""


def _render_live_erp_html(st: dict[str, Any]) -> str:
    mod = st.get("mod", "orders")
    flt = st.get("filter", "ALL")
    sla = bool(st.get("slaOpen", False))
    sc = bool(st.get("scOpen", False))
    ctab = st.get("capTab", "bars")
    drw = bool(st.get("drawerOpen", False))
    drk = bool(st.get("darkCap", False))

    orders = [
        ("ORD-901", "DE-FRA", "DISPATCHED", "#16a34a", "$48,200", "DHL ColdChain"),
        ("ORD-904", "CH-ZRH", "HOLD_CUSTOMS", "#dc2626", "$91,500", "SwissFreight"),
        ("ORD-907", "FR-PAR", "CHILLED_QA", "#2563eb", "$34,800", "ChronoMed"),
        ("ORD-909", "NL-AMS", "DISPATCHED", "#16a34a", "$62,100", "EuroLink"),
        ("ORD-911", "GB-LON", "HOLD_CUSTOMS", "#dc2626", "$77,400", "ChannelCargo"),
        ("ORD-915", "SE-STO", "CHILLED_QA", "#2563eb", "$29,600", "NordicBio"),
    ]
    if mod == "orders":
        vis = [r for r in orders if flt == "ALL" or r[2] == flt]
        trs = "".join(f"<tr><td><b>{r[0]}</b></td><td>{r[1]}</td><td><span class='badge' style='background:{r[3]};'>{r[2]}</span></td><td>{r[4]}</td><td>{r[5]}</td></tr>" for r in vis)
        stage = f"""<div class="kpi-grid">
          <div class="kpi-card" style="border-top:4px solid #2563eb;"><div>GMV Pipeline</div><div class="kpi-val">$1.42M</div></div>
          <div class="kpi-card" style="border-top:4px solid #16a34a;"><div>On-Time SLA</div><div class="kpi-val">98.7%</div></div>
          <div class="kpi-card" style="border-top:4px solid #dc2626;"><div>Customs Holds</div><div class="kpi-val">2</div></div>
          <div class="kpi-card" style="border-top:4px solid #d97706;"><div>Median Dispatch</div><div class="kpi-val">22.4m</div></div>
        </div>
        <div style="margin-bottom:14px;">
          <a id="filter-all" class="pill {'active' if flt=='ALL' else ''}" href="/ui?filter=ALL">ALL (6)</a>
          <a id="filter-hold" class="pill {'active' if flt=='HOLD_CUSTOMS' else ''}" href="/ui?filter=HOLD_CUSTOMS">HOLD_CUSTOMS (2)</a>
          <a id="filter-qa" class="pill {'active' if flt=='CHILLED_QA' else ''}" href="/ui?filter=CHILLED_QA">CHILLED_QA (2)</a>
        </div>
        <table><thead><tr><th>Order ID</th><th>Hub</th><th>Status</th><th>Value</th><th>Carrier</th></tr></thead><tbody>{trs}</tbody></table>"""
    else:
        inner = (
            """<div style="display:flex;flex-direction:column;gap:16px;margin-bottom:20px;">
              <div><div style="display:flex;justify-content:space-between;font-weight:700;"><span>us-east-va</span><span>84%</span></div><div style="height:22px;background:#e2e8f0;border-radius:6px;"><div style="width:84%;height:22px;background:#2563eb;border-radius:6px;"></div></div></div>
              <a id="open-drawer-eu" href="/ui?drawer=1" style="text-decoration:none;color:inherit;display:block;"><div style="display:flex;justify-content:space-between;font-weight:700;color:#dc2626;"><span>eu-central-fra (Click for Failover Runbook)</span><span>93%</span></div><div style="height:22px;background:#fee2e2;border-radius:6px;"><div style="width:93%;height:22px;background:#dc2626;border-radius:6px;"></div></div></a>
              <div><div style="display:flex;justify-content:space-between;font-weight:700;"><span>ap-north-tyo</span><span>61%</span></div><div style="height:22px;background:#e2e8f0;border-radius:6px;"><div style="width:61%;height:22px;background:#10b981;border-radius:6px;"></div></div></div>
            </div>"""
            if ctab == "bars"
            else """<table><thead><tr><th>Cluster</th><th>Reserved vCPU Quota</th><th>Burst Ceiling</th></tr></thead><tbody>
              <tr><td>us-east-va</td><td>4800</td><td>6000</td></tr>
              <tr><td>eu-central-fra</td><td>6400</td><td>7200</td></tr>
              <tr><td>ap-north-tyo</td><td>3200</td><td>4400</td></tr>
            </tbody></table>"""
        )
        stage = f"""<div id="cap-surface" style="background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;padding:22px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
            <h2>Regional Compute &amp; Fulfillment Capacity</h2>
            <div>
              <a id="subtab-bars" class="pill {'active' if ctab=='bars' else ''}" href="/ui?capTab=bars">Utilization Bars</a>
              <a id="subtab-quotas" class="pill {'active' if ctab=='quotas' else ''}" href="/ui?capTab=quotas">vCPU Quotas</a>
              <a id="toggle-compact" class="pill" href="/ui?toggleDark=1">Toggle Dark Surface</a>
            </div>
          </div>{inner}</div>"""

    ov = ""
    if sla:
        ov += """<div id="sla-popover" style="position:fixed;top:62px;right:140px;width:320px;background:#1e293b;color:#f8fafc;padding:18px;border-radius:10px;box-shadow:0 12px 28px rgba(0,0,0,0.35);z-index:30;">
          <h4 style="margin-bottom:8px;color:#38bdf8;">Contractual SLA Penalty Schedule</h4>
          <p>Tier-A ColdChain Breach: <b>$450/hr</b></p><p>Tier-B Standard Delay: <b>$180/hr</b></p></div>"""
    if sc:
        ov += """<div id="shortcuts-modal" style="position:fixed;inset:0;background:rgba(15,23,42,0.6);display:flex;align-items:center;justify-content:center;z-index:50;">
          <div style="width:420px;background:#ffffff;color:#0f172a;padding:22px;border-radius:12px;">
            <h3 style="margin-bottom:12px;">Operator Keyboard Shortcuts</h3>
            <p>Batch Manifest Export Hotkey: <code>Alt+Shift+M</code></p>
            <a href="/ui?toggleSc=1" style="display:inline-block;margin-top:14px;padding:8px 14px;background:#111827;color:#fff;text-decoration:none;border-radius:6px;">Close</a>
          </div></div>"""
    if drw:
        ov += """<div id="remediation-drawer" style="position:fixed;top:0;right:0;width:420px;height:100vh;background:#ffffff;color:#0f172a;box-shadow:-8px 0 24px rgba(0,0,0,0.28);z-index:40;">
          <div style="background:#0f766e;color:#ffffff;padding:18px;font-weight:800;display:flex;justify-content:space-between;">
            <span>FAILOVER RUNBOOK | eu-central-fra</span><a href="/ui?drawer=0" style="color:#fff;text-decoration:none;font-weight:800;">X</a>
          </div>
          <div style="padding:20px;line-height:1.7;">
            <p><b>Runbook ID:</b> <code>RB-FAILOVER-EU93</code></p>
            <p>Drain 35% of Kafka partitions from <code>eu-central-fra</code> to <code>nl-ams-standby</code> when utilization exceeds 90%.</p>
          </div></div>"""

    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>Chronos Cloud ERP v6.2</title>
<style>{SHELL_CSS}</style></head>
<body class="{'compact-dark' if drk else ''}">
  <div id="topbar">
    <span>CHRONOS CLOUD ERP v6.2</span>
    <div style="display:flex;gap:10px;">
      <a id="btn-sla-popover" href="/ui?toggleSla=1" style="padding:6px 12px;border-radius:6px;background:#1d4ed8;color:#fff;text-decoration:none;font-weight:700;">SLA Penalties</a>
      <a id="btn-shortcuts" href="/ui?toggleSc=1" style="padding:6px 12px;border-radius:6px;background:#334155;color:#fff;text-decoration:none;font-weight:700;">Shortcuts (?)</a>
    </div>
  </div>
  <div id="layout">
    <div id="rail">
      <a id="nav-orders" class="nav-btn {'active' if mod=='orders' else ''}" href="/ui?mod=orders">Orders &amp; SLA</a>
      <a id="nav-capacity" class="nav-btn {'active' if mod=='capacity' else ''}" href="/ui?mod=capacity">Capacity Planner</a>
    </div>
    <div id="stage">{stage}</div>
  </div>
  {ov}
</body></html>"""


def build(workspace_root: Path, tickets_root: Path) -> None:
    cs = workspace_root / "shared" / "chronos_suite"
    (cs / "modules").mkdir(parents=True, exist_ok=True)
    (cs / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'/><title>Chronos Cloud ERP v6.2</title>"
        "<link rel='stylesheet' href='styles.css'/></head>"
        "<body><div id='topbar'><span>CHRONOS CLOUD ERP v6.2</span></div>"
        "<div id='layout'><div id='rail'>"
        "<button id='nav-orders' class='nav-btn active'>Orders &amp; SLA</button>"
        "<button id='nav-capacity' class='nav-btn'>Capacity Planner</button>"
        "</div><div id='stage'>TODO</div></div>"
        "<script src='modules/orders_module.js'></script>"
        "<script src='modules/capacity_module.js'></script>"
        "<script src='app.js'></script></body></html>\n",
        encoding="utf-8",
    )
    (cs / "styles.css").write_text("body { margin: 0; font-family: DejaVu Sans, sans-serif; }\n", encoding="utf-8")
    (cs / "app.js").write_text("// Shared SPA router shell\n", encoding="utf-8")
    (cs / "modules" / "orders_module.js").write_text("// TODO: Orders & SLA route module\n", encoding="utf-8")
    (cs / "modules" / "capacity_module.js").write_text("// TODO: Capacity Planner route module\n", encoding="utf-8")
    (tickets_root / "orders_ui_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "capacity_ui_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "orders_ui_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "capacity_ui_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"mod": "orders", "filter": "ALL", "slaOpen": False, "scOpen": False, "capTab": "bars", "drawerOpen": False, "darkCap": False, "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw12_sess" in ck) and (ck["aw12_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw12_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Chronos ERP Session Required</h3>")
                return
            if parsed.path == "/ui":
                with lock:
                    if "mod" in qs and qs["mod"][0] in ("orders", "capacity"):
                        if qs["mod"][0] != state["mod"]:
                            state["switches"] = int(state["switches"]) + 1
                        state["mod"] = qs["mod"][0]
                        state["drawerOpen"] = False
                    if "filter" in qs and qs["filter"][0] in ("ALL", "HOLD_CUSTOMS", "CHILLED_QA"):
                        state["filter"] = qs["filter"][0]
                    if "capTab" in qs and qs["capTab"][0] in ("bars", "quotas"):
                        state["capTab"] = qs["capTab"][0]
                    if "drawer" in qs:
                        state["drawerOpen"] = qs["drawer"][0] == "1"
                    if "toggleSla" in qs:
                        state["slaOpen"] = not bool(state["slaOpen"])
                    if "toggleSc" in qs:
                        state["scOpen"] = not bool(state["scOpen"])
                    if "toggleDark" in qs:
                        state["darkCap"] = not bool(state["darkCap"])
                    write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                html = _render_live_erp_html(dict(state))
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    boot_studio_browser(state_dir, window_size=(1440, 900))


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    cs = workspace_root / "shared" / "chronos_suite"
    (cs / "modules").mkdir(parents=True, exist_ok=True)
    if role == "orders_ui_eng":
        write_json(
            cs / "orders_discovery.json",
            {
                "topbar_hex": "#111827",
                "rail_hex": "#1e293b",
                "hold_order_ids": ["ORD-904", "ORD-911"],
                "tier_a_penalty_usd_hr": 450,
                "shortcut_export_hotkey": "Alt+Shift+M",
            },
        )
        (cs / "modules" / "orders_module.js").write_text(REF_ORDERS_JS, encoding="utf-8")
        if cooperative:
            with resource_lock("aw12_app"):
                (cs / "styles.css").write_text(SHELL_CSS, encoding="utf-8")
                (cs / "index.html").write_text(REF_INDEX_HTML, encoding="utf-8")
        else:
            (cs / "styles.css").write_text(SHELL_CSS, encoding="utf-8")
            (cs / "index.html").write_text(REF_INDEX_HTML.replace("modules/capacity_module.js", "modules/missing_cap.js"), encoding="utf-8")
    elif role == "capacity_ui_eng":
        write_json(
            cs / "capacity_discovery.json",
            {
                "peak_region_id": "eu-central-fra",
                "peak_utilization_pct": 93,
                "failover_runbook_id": "RB-FAILOVER-EU93",
                "eu_reserved_vcpu_quota": 6400,
                "drawer_banner_hex": "#0f766e",
            },
        )
        (cs / "modules" / "capacity_module.js").write_text(REF_CAPACITY_JS, encoding="utf-8")
        if cooperative:
            with resource_lock("aw12_app"):
                (cs / "styles.css").write_text(SHELL_CSS, encoding="utf-8")
                (cs / "index.html").write_text(REF_INDEX_HTML, encoding="utf-8")
        else:
            (cs / "styles.css").write_text(SHELL_CSS, encoding="utf-8")
            (cs / "index.html").write_text(REF_INDEX_HTML.replace("modules/orders_module.js", "modules/missing_ord.js"), encoding="utf-8")


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("orders_ui_eng", workspace_root, cooperative=False)
    solve_role("capacity_ui_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "orders_ui_eng", workspace_root, True)
        fb = pool.submit(solve_role, "capacity_ui_eng", workspace_root, True)
        fa.result()
        fb.result()


def _eval_dom_click_sim(cs_dir: Path, click_js: str, ref_state: dict[str, Any]) -> float:
    from PIL import Image

    tmp_suite = Path(f"/tmp/aw12_suite_{secrets.token_hex(4)}")
    prof = Path(f"/tmp/aw12_ev_{secrets.token_hex(4)}")
    shutil.copytree(cs_dir, tmp_suite)
    prof.mkdir(parents=True, exist_ok=True)
    idx_p = tmp_suite / "index.html"
    if idx_p.is_file() and click_js:
        raw = idx_p.read_text(encoding="utf-8", errors="replace")
        hook = f"<script>window.addEventListener('load',()=>{{setTimeout(()=>{{try{{{click_js}}}catch(e){{}}}},120);}});</script>"
        idx_p.write_text(raw + "\n" + hook, encoding="utf-8")

    handler_cls = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_suite))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    ep = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cand_png = prof / "cand.png"
    ref_html = prof / "ref.html"
    ref_png = prof / "ref.png"
    try:
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}", "--virtual-time-budget=800", "--window-size=1440,900",
                f"--screenshot={cand_png}", f"http://127.0.0.1:{ep}/index.html",
            ],
            capture_output=True, timeout=25,
        )
        ref_html.write_text(_render_live_erp_html(ref_state), encoding="utf-8")
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}", "--window-size=1440,900",
                f"--screenshot={ref_png}", f"file://{ref_html}",
            ],
            capture_output=True, timeout=25,
        )
        if cand_png.is_file() and ref_png.is_file():
            ic = Image.open(cand_png).convert("RGB").resize((240, 150))
            ir = Image.open(ref_png).convert("RGB").resize((240, 150))
            err = sum(
                (abs(ic.getpixel((x, y))[0] - ir.getpixel((x, y))[0]) + abs(ic.getpixel((x, y))[1] - ir.getpixel((x, y))[1]) + abs(ic.getpixel((x, y))[2] - ir.getpixel((x, y))[2])) / (3.0 * 255.0)
                for y in range(150)
                for x in range(240)
            ) / (240.0 * 150.0)
            return round(max(0.0, 1.0 - err * 2.8), 4)
        return 0.0
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(tmp_suite, ignore_errors=True)
        shutil.rmtree(prof, ignore_errors=True)


def _norm_str_list(val: Any) -> list[str]:
    if not isinstance(val, list):
        return []
    out: list[str] = []
    for item in val:
        if isinstance(item, dict):
            oid = item.get("order_id") or item.get("id") or ""
            if oid:
                out.append(str(oid))
        elif isinstance(item, (str, int, float)):
            out.append(str(item))
    return sorted(out)


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    cs = workspace_root / "shared" / "chronos_suite"
    ja = read_json_safe(cs / "orders_discovery.json")
    jb = read_json_safe(cs / "capacity_discovery.json")
    ord_js = (cs / "modules" / "orders_module.js").read_text(encoding="utf-8", errors="replace") if (cs / "modules" / "orders_module.js").is_file() else ""
    cap_js = (cs / "modules" / "capacity_module.js").read_text(encoding="utf-8", errors="replace") if (cs / "modules" / "capacity_module.js").is_file() else ""
    idx_txt = (cs / "index.html").read_text(encoding="utf-8", errors="replace") if (cs / "index.html").is_file() else ""
    suite_txt = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(cs.rglob("*"))
        if p.is_file() and p.suffix.lower() in {".js", ".html"}
    ) if cs.is_dir() else ""

    sim_ord = _eval_dom_click_sim(cs, "document.getElementById('nav-orders')?.click();", {"mod": "orders", "filter": "ALL"})
    sim_hld = _eval_dom_click_sim(cs, "document.getElementById('nav-orders')?.click(); setTimeout(()=>document.getElementById('filter-hold')?.click(), 60);", {"mod": "orders", "filter": "HOLD_CUSTOMS"})
    sim_cap = _eval_dom_click_sim(cs, "document.getElementById('nav-capacity')?.click();", {"mod": "capacity", "capTab": "bars"})
    sim_drw = _eval_dom_click_sim(cs, "document.getElementById('nav-capacity')?.click(); setTimeout(()=>document.getElementById('open-drawer-eu')?.click(), 60);", {"mod": "capacity", "capTab": "bars", "drawerOpen": True})

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_hex", str(ja.get("topbar_hex", "")).lower() == "#111827" and str(ja.get("rail_hex", "")).lower() == "#1e293b", 1.2, "topbar_hex or rail_hex mismatch"),
        ("a_hold_ids", _norm_str_list(ja.get("hold_order_ids")) == ["ORD-904", "ORD-911"], 1.4, "hold_order_ids mismatch"),
        ("a_sla_pen", ja.get("tier_a_penalty_usd_hr") == 450, 1.6, "tier_a_penalty_usd_hr hidden popover value mismatch (450)"),
        ("a_hotkey", str(ja.get("shortcut_export_hotkey", "")).strip() == "Alt+Shift+M", 1.6, "shortcut_export_hotkey modal value mismatch (Alt+Shift+M)"),
        ("a_mod_orders_js", all(x in ord_js for x in ("ORD-901", "ORD-904", "ORD-911")) and ("450" in suite_txt), 1.8, "modules/orders_module.js missing order rows or chronos_suite missing SLA $450 metadata"),
        ("a_vis_ord_86", sim_ord >= 0.86, 1.8, f"Orders default visual similarity < 0.86 ({sim_ord})"),
        ("a_vis_ord_95", sim_ord >= 0.95, 1.8, f"Orders fine pixel fidelity < 0.95 ({sim_ord})"),
        ("a_vis_hold_94", sim_hld >= 0.94, 1.8, f"Filtered HOLD_CUSTOMS click fidelity < 0.94 ({sim_hld})"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_peak_reg", jb.get("peak_region_id") == "eu-central-fra" and jb.get("peak_utilization_pct") == 93, 1.4, "peak_region_id or peak_utilization_pct mismatch"),
        ("b_runbook", jb.get("failover_runbook_id") == "RB-FAILOVER-EU93", 1.6, "failover_runbook_id drawer value mismatch (RB-FAILOVER-EU93)"),
        ("b_quota", jb.get("eu_reserved_vcpu_quota") == 6400, 1.6, "eu_reserved_vcpu_quota sub-tab value mismatch (6400)"),
        ("b_drw_hex", str(jb.get("drawer_banner_hex", "")).lower() == "#0f766e", 1.2, "drawer_banner_hex mismatch (#0f766e)"),
        ("b_mod_cap_js", all(x in cap_js for x in ("eu-central-fra", "RB-FAILOVER-EU93", "6400")), 1.8, "modules/capacity_module.js missing Capacity / Quotas / Failover drawer content"),
        ("b_vis_cap_86", sim_cap >= 0.86, 1.8, f"Capacity view visual similarity < 0.86 ({sim_cap})"),
        ("b_vis_cap_95", sim_cap >= 0.95, 1.8, f"Capacity fine pixel fidelity < 0.95 ({sim_cap})"),
        ("b_vis_drw_94", sim_drw >= 0.94, 1.8, f"Failover drawer click fidelity < 0.94 ({sim_drw})"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_spa_shell_mounts_both_route_modules",
            "orders_module.js" in idx_txt and "capacity_module.js" in idx_txt and sim_ord >= 0.86 and sim_cap >= 0.86,
            2.5,
            "Shared SPA shell index.html/styles.css broke one route module due to concurrent overwrite",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"orders_ui_eng": TICKET_A, "capacity_ui_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

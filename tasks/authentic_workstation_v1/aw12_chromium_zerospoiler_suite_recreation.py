"""AW-12: Zero-Spoiler 8-State Enterprise ERP Web Suite Recreation from Live Chromium."""
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
    "title": "Zero-Spoiler 8-State Chronos ERP Suite Recreation: Fulfillment Desk vs. Capacity & Failover Planner",
    "domain": "Interactive Web UI Exploration & Frontend Engineering (Chromium + HTML5/CSS3/JS)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19612,
    "roles": ("orders_ui_eng", "capacity_ui_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

TICKET_A = (
    "# Work Order — Fulfillment & SLA Frontend Engineer (`orders_ui_eng`)\n\n"
    "Explore every interactive control, filter, popover, and header utility dialog inside the **Orders & SLA** module of the live **Chronos ERP** application open in Chromium (`http://127.0.0.1:19612`), and recreate it faithfully inside `/workspace/chronos_suite` (`/workspace/chronos_suite/index.html`, `styles.css`, `app.js`):\n\n"
    "1. Use the desktop GUI driver to click through all interactive buttons, filter pills, popovers, and header icons in the **Orders & SLA** view of Chromium, noting exact layout proportions, hex colors, KPI values, order rows, filtered subsets, and hidden popover/modal details.\n"
    "2. Build `/workspace/chronos_suite/index.html`, `styles.css`, and `app.js` so that clicking the matching navigation item, filter buttons, SLA breakdown control, and header shortcut button reproduces the visual layout and interactive DOM states at `1440x900`.\n"
    "3. Write `/workspace/chronos_suite/orders_discovery.json` with:\n"
    "   - `topbar_hex`, `rail_hex`, `hold_order_ids` (sorted list), `tier_a_penalty_usd_hr` (int), `shortcut_export_hotkey` (string)\n"
)

TICKET_B = (
    "# Work Order — Capacity & Failover Planner Frontend Engineer (`capacity_ui_eng`)\n\n"
    "Explore every interactive sub-tab, chart, regional row action, and density/theme toggle inside the **Capacity Planner** module of the live **Chronos ERP** application open in Chromium (`http://127.0.0.1:19612`), and recreate it faithfully inside `/workspace/chronos_suite` (`/workspace/chronos_suite/index.html`, `styles.css`, `app.js`):\n\n"
    "1. Switch to **Capacity Planner** in the left navigation rail of Chromium and click through its utilization bars, lower sub-tabs, slide-over failover runbook drawer, and compact/dark-panel toggle.\n"
    "2. Implement the **Capacity Planner** navigation view and all of its interactive sub-states inside `/workspace/chronos_suite/index.html`, `styles.css`, and `app.js` at `1440x900`.\n"
    "3. Write `/workspace/chronos_suite/capacity_discovery.json` with:\n"
    "   - `peak_region_id` (string), `peak_utilization_pct` (int), `failover_runbook_id` (string), `eu_reserved_vcpu_quota` (int), `drawer_banner_hex`\n"
)

REFERENCE_APP_HTML = """<!doctype html>
<html><head><meta charset="utf-8"/><title>Chronos Cloud ERP v6.2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: DejaVu Sans, sans-serif; }
  body { background: #f1f5f9; color: #0f172a; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  #topbar { height: 54px; background: #111827; color: #f8fafc; display: flex; align-items: center; justify-content: space-between; padding: 0 22px; font-weight: 800; }
  #layout { flex: 1; display: flex; overflow: hidden; }
  #rail { width: 224px; background: #1e293b; color: #e2e8f0; padding: 18px; display: flex; flex-direction: column; gap: 10px; }
  .nav-btn { padding: 11px 14px; border-radius: 8px; border: none; text-align: left; font-weight: 700; font-size: 14px; cursor: pointer; background: transparent; color: #cbd5e1; }
  .nav-btn.active { background: #2563eb; color: #ffffff; }
  #stage { flex: 1; padding: 22px; overflow: auto; position: relative; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
  .kpi-card { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 16px; }
  .kpi-val { font-size: 28px; font-weight: 800; margin-top: 6px; }
  .pill { padding: 7px 14px; border-radius: 999px; border: 1px solid #94a3b8; background: #ffffff; font-weight: 700; cursor: pointer; margin-right: 8px; }
  .pill.active { background: #0f172a; color: #ffffff; border-color: #0f172a; }
  .badge { padding: 4px 10px; border-radius: 999px; color: #fff; font-size: 12px; font-weight: 700; }
  table { width: 100%; border-collapse: collapse; background: #ffffff; border-radius: 10px; overflow: hidden; border: 1px solid #cbd5e1; }
  th, td { padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: left; font-size: 13px; }
  th { background: #f8fafc; font-weight: 700; }
  .compact-dark #cap-surface { background: #0f172a !important; color: #f8fafc !important; }
</style></head>
<body>
  <div id="topbar">
    <span>CHRONOS CLOUD ERP v6.2</span>
    <div style="display:flex;gap:10px;">
      <button id="btn-sla-popover" onclick="toggleSla()" style="padding:6px 12px;border-radius:6px;background:#1d4ed8;color:#fff;border:none;font-weight:700;cursor:pointer;">SLA Penalties</button>
      <button id="btn-shortcuts" onclick="toggleShortcuts()" style="padding:6px 12px;border-radius:6px;background:#334155;color:#fff;border:none;font-weight:700;cursor:pointer;">Shortcuts (?)</button>
    </div>
  </div>
  <div id="layout">
    <div id="rail">
      <button id="nav-orders" class="nav-btn active" onclick="setMod('orders')">Orders &amp; SLA</button>
      <button id="nav-capacity" class="nav-btn" onclick="setMod('capacity')">Capacity Planner</button>
    </div>
    <div id="stage"></div>
  </div>
  <script>
    const ORDERS = [
      {id:'ORD-901', region:'DE-FRA', status:'DISPATCHED', color:'#16a34a', val:'$48,200', carrier:'DHL ColdChain'},
      {id:'ORD-904', region:'CH-ZRH', status:'HOLD_CUSTOMS', color:'#dc2626', val:'$91,500', carrier:'SwissFreight'},
      {id:'ORD-907', region:'FR-PAR', status:'CHILLED_QA', color:'#2563eb', val:'$34,800', carrier:'ChronoMed'},
      {id:'ORD-909', region:'NL-AMS', status:'DISPATCHED', color:'#16a34a', val:'$62,100', carrier:'EuroLink'},
      {id:'ORD-911', region:'GB-LON', status:'HOLD_CUSTOMS', color:'#dc2626', val:'$77,400', carrier:'ChannelCargo'},
      {id:'ORD-915', region:'SE-STO', status:'CHILLED_QA', color:'#2563eb', val:'$29,600', carrier:'NordicBio'}
    ];
    let state = {mod:'orders', filter:'ALL', slaOpen:false, scOpen:false, capTab:'bars', drawerOpen:false, darkCap:false};
    const qs = new URLSearchParams(window.location.search);
    if (qs.get('mod')) state.mod = qs.get('mod');
    if (qs.get('filter')) state.filter = qs.get('filter');
    if (qs.get('sla')==='1') state.slaOpen = true;
    if (qs.get('sc')==='1') state.scOpen = true;
    if (qs.get('captab')) state.capTab = qs.get('captab');
    if (qs.get('drawer')==='1') state.drawerOpen = true;
    if (qs.get('dark')==='1') state.darkCap = true;

    function setMod(m){ state.mod=m; render(); }
    function setFilter(f){ state.filter=f; render(); }
    function toggleSla(){ state.slaOpen=!state.slaOpen; render(); }
    function toggleShortcuts(){ state.scOpen=!state.scOpen; render(); }
    function setCapTab(t){ state.capTab=t; render(); }
    function toggleDrawer(v){ state.drawerOpen=v; render(); }
    function toggleDarkCap(){ state.darkCap=!state.darkCap; render(); }

    function render(){
      document.getElementById('nav-orders').className = 'nav-btn' + (state.mod==='orders'?' active':'');
      document.getElementById('nav-capacity').className = 'nav-btn' + (state.mod==='capacity'?' active':'');
      document.body.className = state.darkCap ? 'compact-dark' : '';
      let h = '';
      if (state.mod === 'orders') {
        const rows = ORDERS.filter(r => state.filter==='ALL' || r.status===state.filter);
        h += `<div class="kpi-grid">
          <div class="kpi-card" style="border-top:4px solid #2563eb;"><div>GMV Pipeline</div><div class="kpi-val">$1.42M</div></div>
          <div class="kpi-card" style="border-top:4px solid #16a34a;"><div>On-Time SLA</div><div class="kpi-val">98.7%</div></div>
          <div class="kpi-card" style="border-top:4px solid #dc2626;"><div>Customs Holds</div><div class="kpi-val">2</div></div>
          <div class="kpi-card" style="border-top:4px solid #d97706;"><div>Median Dispatch</div><div class="kpi-val">22.4m</div></div>
        </div>
        <div style="margin-bottom:14px;">
          <button id="filter-all" class="pill ${state.filter==='ALL'?'active':''}" onclick="setFilter('ALL')">ALL (6)</button>
          <button id="filter-hold" class="pill ${state.filter==='HOLD_CUSTOMS'?'active':''}" onclick="setFilter('HOLD_CUSTOMS')">HOLD_CUSTOMS (2)</button>
          <button id="filter-qa" class="pill ${state.filter==='CHILLED_QA'?'active':''}" onclick="setFilter('CHILLED_QA')">CHILLED_QA (2)</button>
        </div>
        <table><thead><tr><th>Order ID</th><th>Hub</th><th>Status</th><th>Value</th><th>Carrier</th></tr></thead><tbody>` +
        rows.map(r => `<tr><td><b>${r.id}</b></td><td>${r.region}</td><td><span class="badge" style="background:${r.color};">${r.status}</span></td><td>${r.val}</td><td>${r.carrier}</td></tr>`).join('') +
        `</tbody></table>`;
      } else {
        h += `<div id="cap-surface" style="background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;padding:22px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
            <h2>Regional Compute &amp; Fulfillment Capacity</h2>
            <div>
              <button id="subtab-bars" class="pill ${state.capTab==='bars'?'active':''}" onclick="setCapTab('bars')">Utilization Bars</button>
              <button id="subtab-quotas" class="pill ${state.capTab==='quotas'?'active':''}" onclick="setCapTab('quotas')">vCPU Quotas</button>
              <button id="toggle-compact" class="pill" onclick="toggleDarkCap()">Toggle Dark Surface</button>
            </div>
          </div>`;
        if (state.capTab === 'bars') {
          h += `<div style="display:flex;flex-direction:column;gap:16px;margin-bottom:20px;">
            <div><div style="display:flex;justify-content:space-between;font-weight:700;"><span>us-east-va</span><span>84%</span></div><div style="height:22px;background:#e2e8f0;border-radius:6px;"><div style="width:84%;height:22px;background:#2563eb;border-radius:6px;"></div></div></div>
            <div id="open-drawer-eu" onclick="toggleDrawer(true)" style="cursor:pointer;"><div style="display:flex;justify-content:space-between;font-weight:700;color:#dc2626;"><span>eu-central-fra (Click for Failover Runbook)</span><span>93%</span></div><div style="height:22px;background:#fee2e2;border-radius:6px;"><div style="width:93%;height:22px;background:#dc2626;border-radius:6px;"></div></div></div>
            <div><div style="display:flex;justify-content:space-between;font-weight:700;"><span>ap-north-tyo</span><span>61%</span></div><div style="height:22px;background:#e2e8f0;border-radius:6px;"><div style="width:61%;height:22px;background:#10b981;border-radius:6px;"></div></div></div>
          </div>`;
        } else {
          h += `<table><thead><tr><th>Cluster</th><th>Reserved vCPU Quota</th><th>Burst Ceiling</th></tr></thead><tbody>
            <tr><td>us-east-va</td><td>4800</td><td>6000</td></tr>
            <tr><td>eu-central-fra</td><td>6400</td><td>7200</td></tr>
            <tr><td>ap-north-tyo</td><td>3200</td><td>4400</td></tr>
          </tbody></table>`;
        }
        h += `</div>`;
      }
      if (state.slaOpen) {
        h += `<div id="sla-popover" style="position:fixed;top:62px;right:140px;width:320px;background:#1e293b;color:#f8fafc;padding:18px;border-radius:10px;box-shadow:0 12px 28px rgba(0,0,0,0.35);z-index:30;">
          <h4 style="margin-bottom:8px;color:#38bdf8;">Contractual SLA Penalty Schedule</h4>
          <p>Tier-A ColdChain Breach: <b>$450/hr</b></p>
          <p>Tier-B Standard Delay: <b>$180/hr</b></p>
        </div>`;
      }
      if (state.scOpen) {
        h += `<div id="shortcuts-modal" style="position:fixed;inset:0;background:rgba(15,23,42,0.6);display:flex;align-items:center;justify-content:center;z-index:50;">
          <div style="width:420px;background:#ffffff;color:#0f172a;padding:22px;border-radius:12px;">
            <h3 style="margin-bottom:12px;">Operator Keyboard Shortcuts</h3>
            <p>Batch Manifest Export Hotkey: <code>Alt+Shift+M</code></p>
            <button onclick="toggleShortcuts()" style="margin-top:14px;padding:8px 14px;background:#111827;color:#fff;border:none;border-radius:6px;">Close</button>
          </div>
        </div>`;
      }
      if (state.drawerOpen) {
        h += `<div id="remediation-drawer" style="position:fixed;top:0;right:0;width:420px;height:100vh;background:#ffffff;color:#0f172a;box-shadow:-8px 0 24px rgba(0,0,0,0.28);z-index:40;">
          <div style="background:#0f766e;color:#ffffff;padding:18px;font-weight:800;display:flex;justify-content:space-between;">
            <span>FAILOVER RUNBOOK | eu-central-fra</span><button onclick="toggleDrawer(false)" style="background:none;border:none;color:#fff;font-weight:800;cursor:pointer;">X</button>
          </div>
          <div style="padding:20px;line-height:1.7;">
            <p><b>Runbook ID:</b> <code>RB-FAILOVER-EU93</code></p>
            <p>Drain 35% of Kafka partitions from <code>eu-central-fra</code> to <code>nl-ams-standby</code> when utilization exceeds 90%.</p>
          </div>
        </div>`;
      }
      document.getElementById('stage').innerHTML = h;
    }
    render();
  </script>
</body></html>"""


def build(workspace_root: Path, tickets_root: Path) -> None:
    cs = workspace_root / "shared" / "chronos_suite"
    cs.mkdir(parents=True, exist_ok=True)
    (cs / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'/><link rel='stylesheet' href='styles.css'/></head>"
        "<body><div id='app'>TODO</div><script src='app.js'></script></body></html>\n",
        encoding="utf-8",
    )
    (cs / "styles.css").write_text("body { margin: 0; }\n", encoding="utf-8")
    (cs / "app.js").write_text("// Chronos ERP recreation\n", encoding="utf-8")
    (tickets_root / "orders_ui_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "capacity_ui_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "orders_ui_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "capacity_ui_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    write_json(state_file, {"requests": 0})
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
            self._send(200, REFERENCE_APP_HTML.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    boot_studio_browser(state_dir, window_size=(1440, 900))


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    cs = workspace_root / "shared" / "chronos_suite"
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
        if cooperative:
            with resource_lock("aw12_app"):
                (cs / "index.html").write_text(REFERENCE_APP_HTML, encoding="utf-8")
        else:
            (cs / "index.html").write_text(REFERENCE_APP_HTML.replace("RB-FAILOVER-EU93", "MISSING_B").replace("6400", "0"), encoding="utf-8")
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
        if cooperative:
            with resource_lock("aw12_app"):
                (cs / "index.html").write_text(REFERENCE_APP_HTML, encoding="utf-8")
        else:
            (cs / "index.html").write_text(REFERENCE_APP_HTML.replace("ORD-904", "MISSING_A").replace("$450/hr", "$0"), encoding="utf-8")


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("orders_ui_eng", workspace_root, cooperative=False)
    solve_role("capacity_ui_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "orders_ui_eng", workspace_root, True)
        fb = pool.submit(solve_role, "capacity_ui_eng", workspace_root, True)
        fa.result()
        fb.result()


def _eval_app_state(base_url: str, click_js: str, ref_qs: str) -> tuple[str, float]:
    from PIL import Image

    prof = Path(f"/tmp/aw12_ev_{secrets.token_hex(4)}")
    prof.mkdir(parents=True, exist_ok=True)
    cand_png = prof / "cand.png"
    ref_html = prof / "ref.html"
    ref_png = prof / "ref.png"
    try:
        # Inject click_js via wrapper iframe or inline script on temp copy? Even cleaner: evaluate via wrapper HTML on same origin!
        cp_dom = subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                f"--user-data-dir={prof}", "--virtual-time-budget=1200", "--dump-dom", f"{base_url}{ref_qs}",
            ],
            capture_output=True, text=True, timeout=25,
        )
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}", "--window-size=1440,900",
                f"--screenshot={cand_png}", f"{base_url}{ref_qs}",
            ],
            capture_output=True, timeout=25,
        )
        ref_html.write_text(REFERENCE_APP_HTML, encoding="utf-8")
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}", "--window-size=1440,900",
                f"--screenshot={ref_png}", f"file://{ref_html}{ref_qs}",
            ],
            capture_output=True, timeout=25,
        )
        sim = 0.0
        if cand_png.is_file() and ref_png.is_file():
            ic = Image.open(cand_png).convert("RGB").resize((240, 150))
            ir = Image.open(ref_png).convert("RGB").resize((240, 150))
            err = sum(
                (abs(ic.getpixel((x, y))[0] - ir.getpixel((x, y))[0]) + abs(ic.getpixel((x, y))[1] - ir.getpixel((x, y))[1]) + abs(ic.getpixel((x, y))[2] - ir.getpixel((x, y))[2])) / (3.0 * 255.0)
                for y in range(150)
                for x in range(240)
            ) / (240.0 * 150.0)
            sim = round(max(0.0, 1.0 - err * 2.8), 4)
        return (cp_dom.stdout if cp_dom.returncode == 0 else ""), sim
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    cs = workspace_root / "shared" / "chronos_suite"
    ja = read_json_safe(cs / "orders_discovery.json")
    jb = read_json_safe(cs / "capacity_discovery.json")
    src_all = "\n".join(
        (cs / fn).read_text(encoding="utf-8", errors="replace")
        for fn in ("index.html", "styles.css", "app.js")
        if (cs / fn).is_file()
    )

    handler_cls = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(cs))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    ep = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{ep}/index.html"
        dom_ord, sim_ord = _eval_app_state(base, "", "?mod=orders")
        dom_hld, sim_hld = _eval_app_state(base, "", "?mod=orders&filter=HOLD_CUSTOMS")
        dom_cap, sim_cap = _eval_app_state(base, "", "?mod=capacity")
        dom_drw, sim_drw = _eval_app_state(base, "", "?mod=capacity&drawer=1")
    finally:
        srv.shutdown()
        srv.server_close()

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_hex", str(ja.get("topbar_hex", "")).lower() == "#111827" and str(ja.get("rail_hex", "")).lower() == "#1e293b", 1.2, "topbar_hex or rail_hex mismatch"),
        ("a_hold_ids", sorted(ja.get("hold_order_ids") or []) == ["ORD-904", "ORD-911"], 1.4, "hold_order_ids mismatch"),
        ("a_sla_pen", ja.get("tier_a_penalty_usd_hr") == 450, 1.6, "tier_a_penalty_usd_hr hidden popover value mismatch (450)"),
        ("a_hotkey", str(ja.get("shortcut_export_hotkey", "")).strip() == "Alt+Shift+M", 1.6, "shortcut_export_hotkey modal value mismatch (Alt+Shift+M)"),
        ("a_src_orders_data", all(x in src_all for x in ("ORD-901", "ORD-904", "ORD-911", "$450", "Alt+Shift+M")), 1.8, "Recreated frontend bundle missing order rows / SLA popover / shortcut modal"),
        ("a_vis_ord_86", sim_ord >= 0.86, 1.8, f"Orders default visual similarity < 0.86 ({sim_ord})"),
        ("a_vis_ord_96", sim_ord >= 0.965, 1.8, f"Orders fine pixel fidelity < 0.965 ({sim_ord})"),
        ("a_vis_hold_96", sim_hld >= 0.96, 1.8, f"Filtered HOLD_CUSTOMS pixel fidelity < 0.96 ({sim_hld})"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_peak_reg", jb.get("peak_region_id") == "eu-central-fra" and jb.get("peak_utilization_pct") == 93, 1.4, "peak_region_id or peak_utilization_pct mismatch"),
        ("b_runbook", jb.get("failover_runbook_id") == "RB-FAILOVER-EU93", 1.6, "failover_runbook_id drawer value mismatch (RB-FAILOVER-EU93)"),
        ("b_quota", jb.get("eu_reserved_vcpu_quota") == 6400, 1.6, "eu_reserved_vcpu_quota sub-tab value mismatch (6400)"),
        ("b_drw_hex", str(jb.get("drawer_banner_hex", "")).lower() == "#0f766e", 1.2, "drawer_banner_hex mismatch (#0f766e)"),
        ("b_src_cap_data", all(x in src_all for x in ("eu-central-fra", "RB-FAILOVER-EU93", "6400", "nl-ams-standby")), 1.8, "Recreated frontend bundle missing Capacity / Quotas / Failover drawer content"),
        ("b_vis_cap_86", sim_cap >= 0.86, 1.8, f"Capacity view visual similarity < 0.86 ({sim_cap})"),
        ("b_vis_cap_96", sim_cap >= 0.965, 1.8, f"Capacity fine pixel fidelity < 0.965 ({sim_cap})"),
        ("b_vis_drw_96", sim_drw >= 0.96, 1.8, f"Failover drawer pixel fidelity < 0.96 ({sim_drw})"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_unified_bundle_retains_both_modules",
            all(x in src_all for x in ("ORD-904", "$450", "Alt+Shift+M", "RB-FAILOVER-EU93", "6400")),
            2.5,
            "Shared /workspace/chronos_suite bundle lost one role's recreated module due to concurrent file overwrite",
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

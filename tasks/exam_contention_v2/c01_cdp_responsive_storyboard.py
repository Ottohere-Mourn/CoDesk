"""EC2-C01: Singleton :9222 CDP Responsive Web QA vs. Unobstructed 1920x1080 6-Scene Storyboard GIF.

Track 1 — Isolated Workspaces, Shared Display / Singleton Browser / Framebuffer Contention:
  - Role A (responsive_qa_lead) and Role B (motion_demo_producer) have 100% isolated /workspace directories.
  - Both roles interact with a single pre-authenticated Chromium instance (--remote-debugging-port=9222, SingletonLock)
    and the shared 1920x1080 X11 screen (DISPLAY=:99).
  - Resizing Chromium to 390x844 / 820x1180 / 1440x900 for responsive QA vs. holding 1920x1080 F11 fullscreen
    for unobstructed 6-scene screen capture collides directly in both CUA and CDP/CLI workflows.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    read_json_safe,
    write_json,
)

TASK_ID = "EC2-C01"
QA_PORT = 19101
STORY_PORT = 19112
CDP_PORT = 9222

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Singleton CDP Responsive Web QA vs. Unobstructed 1920x1080 6-Scene Storyboard Capture",
    "domain": "Full-Stack Responsive Web QA & Fullscreen Product Motion Capture",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "singleton_cdp_browser_tab_and_geometry_race",
        "fullscreen_framebuffer_photobombing",
        "responsive_breakpoint_vs_kiosk_capture",
    ),
    "roles": ("responsive_qa_lead", "motion_demo_producer"),
    "portal_port": QA_PORT,
    "extra_ports": (STORY_PORT, CDP_PORT),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

# 36 deterministic incidents: (id, sev, elapsed_min, weight, acked)
# SLA rules (shown inside the '?' Hotkey & SLA Modal):
#   P1 breached if elapsed_min > 15; P2 breached if elapsed_min > 45; P3 breached if elapsed_min > 180.
INCIDENTS: list[tuple[str, str, int, int, bool]] = [
    ("INC-101", "P1", 22, 4, False),
    ("INC-102", "P1", 11, 3, True),
    ("INC-103", "P1", 29, 5, False),
    ("INC-104", "P1", 15, 2, True),   # boundary 15 -> NOT breached (>15)
    ("INC-105", "P1", 19, 4, True),
    ("INC-106", "P1", 34, 6, False),
    ("INC-107", "P2", 52, 3, True),
    ("INC-108", "P2", 45, 2, False),  # boundary 45 -> NOT breached (>45)
    ("INC-109", "P2", 61, 4, True),
    ("INC-110", "P2", 28, 2, True),
    ("INC-111", "P2", 74, 5, False),
    ("INC-112", "P2", 49, 3, True),
    ("INC-113", "P2", 38, 2, True),
    ("INC-114", "P2", 83, 4, True),
    ("INC-115", "P3", 195, 2, True),
    ("INC-116", "P3", 180, 1, True),  # boundary 180 -> NOT breached (>180)
    ("INC-117", "P3", 240, 3, False),
    ("INC-118", "P3", 120, 1, True),
    ("INC-119", "P3", 210, 2, True),
    ("INC-120", "P3", 95,  1, True),
    ("INC-121", "P1", 17, 5, False),
    ("INC-122", "P2", 55, 3, True),
    ("INC-123", "P3", 160, 1, True),
    ("INC-124", "P2", 67, 4, True),
]


def _compute_qa_oracle() -> dict[str, Any]:
    sla_lim = {"P1": 15, "P2": 45, "P3": 180}
    breached = [r[0] for r in INCIDENTS if r[2] > sla_lim[r[1]]]
    p1_unacked = sorted(r[0] for r in INCIDENTS if r[1] == "P1" and not r[4])
    w_sum = sum(r[3] for r in INCIDENTS)
    w_mttr = round(sum(r[2] * r[3] for r in INCIDENTS) / w_sum, 2)
    return {
        "total_incidents": len(INCIDENTS),
        "sla_breached_count": len(breached),
        "p1_unacked_ids": p1_unacked,
        "weighted_mean_mttr_min": w_mttr,
        "mobile_overflow_px": 46,
        "mobile_ack_btn_height_px": 30,
        "tablet_filter_zindex_inverted": True,
        "desktop_escape_closes_modal": False,
        "wcag_low_contrast_selector": ".muted-owner-badge",
    }


QA_ORACLE = _compute_qa_oracle()

# 6 Keynote scenes: (scene_idx, title, bar_rgb, center_rgb, throughput_gbps, savings_musd, kpi_code)
KEYNOTE_SCENES: list[tuple[int, str, tuple[int, int, int], tuple[int, int, int], float, float, str]] = [
    (1, "Global Edge Mesh Topology",     (14, 165, 233),  (15, 23, 42),  142.5, 1.85, "NEB-S1-4820"),
    (2, "Zero-Copy RDMA Fabric",         (16, 185, 129),  (17, 24, 39),  218.0, 2.40, "NEB-S2-7319"),
    (3, "Adaptive Tail-Latency Shield",  (139, 92, 246),  (23, 23, 38),  196.4, 3.15, "NEB-S3-6094"),
    (4, "Multi-Region Quorum Failover",  (245, 158, 11),  (28, 25, 23),  174.8, 2.90, "NEB-S4-5512"),
    (5, "Autonomous Cold-Tier Compactor",(236, 72, 153),  (24, 20, 36),  264.2, 4.60, "NEB-S5-8841"),
    (6, "FY2026 Fleet Efficiency Close", (34, 197, 94),   (12, 26, 30),  231.6, 5.25, "NEB-S6-9903"),
]


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    qa_md = "\n".join([
        f"# Responsive Web QA & Accessibility Audit Work Order — {b}responsive_qa_lead{b}",
        "",
        "## Scope & Deliverables",
        f"Audit the authenticated **IncidentPulse On-Call Console** open in the workstation Chromium session at {b}http://127.0.0.1:{QA_PORT}/{b} and write all deliverables into {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Three Breakpoint Evidence Captures**: Inspect IncidentPulse at three exact viewport sizes and save clean PNG captures of the rendered IncidentPulse interface:",
        f"   - {b}/workspace/screenshots/mobile_390x844.png{b} (viewport {b}390 x 844{b})",
        f"   - {b}/workspace/screenshots/tablet_820x900.png{b} (viewport {b}820 x 900{b})",
        f"   - {b}/workspace/screenshots/desktop_1440x900.png{b} (viewport {b}1440 x 900{b})",
        f"2. **Interactive Policy & UI Defect Audit ({b}/workspace/QA_AUDIT_REPORT.json{b})**:",
        f"   - Open the in-app **SLA & Shortcut Reference Modal** ({b}?{b} key or **SLA Policy (?)** button) to read the exact per-severity SLA breach minute thresholds and test whether pressing {b}Escape{b} closes the modal.",
        "   - Measure the responsive CSS/DOM defects across the three breakpoints and write JSON with exact keys:",
        f"     - {b}\"total_incidents\"{b}: integer total rows in the live incident table",
        f"     - {b}\"sla_breached_count\"{b}: integer count of rows strictly exceeding their severity's SLA threshold",
        f"     - {b}\"p1_unacked_ids\"{b}: sorted list of {b}INC-...{b} IDs with severity {b}P1{b} and status {b}UNACKED{b}",
        f"     - {b}\"weighted_mean_mttr_min\"{b}: {b}sum(elapsed_min * impact_weight) / sum(impact_weight){b} across all rows, rounded to 2 decimal places",
        f"     - {b}\"mobile_overflow_px\"{b}: integer horizontal pixel overflow ({b}documentElement.scrollWidth - innerWidth{b}) at {b}390 x 844{b}",
        f"     - {b}\"mobile_ack_btn_height_px\"{b}: rendered pixel height of {b}#ack-selected-btn{b} at {b}390 x 844{b}",
        f"     - {b}\"tablet_filter_zindex_inverted\"{b}: boolean ({b}true{b} if {b}#sticky-filter-bar{b} has lower z-index than {b}#incident-table-header{b} at {b}820 x 900{b})",
        f"     - {b}\"desktop_escape_closes_modal\"{b}: boolean ({b}true{b} if {b}Escape{b} closes {b}#sla-modal{b}, else {b}false{b})",
        f"     - {b}\"wcag_low_contrast_selector\"{b}: CSS class selector (e.g. {b}\".class-name\"{b}) of the badge element in the incident table failing WCAG contrast (< 2.0:1)",
        "",
    ])

    story_md = "\n".join([
        f"# Fullscreen 6-Scene Keynote Capture & Telemetry Work Order — {b}motion_demo_producer{b}",
        "",
        "## Scope & Deliverables",
        f"Capture an unobstructed {b}1920 x 1080{b} fullscreen 6-scene product reel and telemetry manifest from the authenticated **NebulaOps Live Keynote** open in the workstation Chromium session at {b}http://127.0.0.1:{STORY_PORT}/{b}, saving all deliverables into {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Unobstructed {b}1920 x 1080{b} Keyframes ({b}/workspace/frames/scene_1.png{b} .. {b}scene_6.png{b})**:",
        f"   - NebulaOps renders its live telemetry stage ONLY when displayed in full {b}1920 x 1080{b} fullscreen ({b}F11{b} / {b}innerWidth >= 1860{b} and {b}innerHeight >= 1000{b}); smaller viewports pause the stage with a warning banner.",
        f"   - Step through all 6 scenes ({b}Scene 1{b} through {b}Scene 6{b}) in fullscreen and capture each unobstructed {b}1920 x 1080{b} screen frame to {b}/workspace/frames/scene_1.png{b} .. {b}/workspace/frames/scene_6.png{b} (verify no browser address bar, pause warning, or other window overlaps the stage).",
        f"2. **Animated Product Reel ({b}/workspace/nebula_keynote.gif{b})**:",
        f"   - Assemble the 6 captured scenes in order into an animated looping GIF ({b}>= 6{b} frames, resolution at least {b}960 x 540{b}).",
        f"3. **Keynote Telemetry Manifest ({b}/workspace/KEYNOTE_TELEMETRY.json{b})**:",
        "   - Extract the live metrics displayed across the 6 fullscreen scenes into JSON with exact keys:",
        f"     - {b}\"scene_codes\"{b}: ordered 6-element list of {b}NEB-S1-...{b} through {b}NEB-S6-...{b} verification codes",
        f"     - {b}\"peak_throughput_gbps\"{b}: maximum {b}throughput_gbps{b} across the 6 scenes (float)",
        f"     - {b}\"total_annual_savings_musd\"{b}: sum of {b}annual_savings_musd{b} across all 6 scenes, rounded to 2 decimal places",
        "",
    ])
    return {"responsive_qa_lead": qa_md, "motion_demo_producer": story_md}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    for role, ws in workspace_map.items():
        ws.mkdir(parents=True, exist_ok=True)
        if role == "responsive_qa_lead":
            (ws / "screenshots").mkdir(parents=True, exist_ok=True)
            (ws / "README_QA.txt").write_text(
                "Target: http://127.0.0.1:19101/ (pre-authenticated in workstation Chromium).\n"
                "Save 3 breakpoint PNGs in /workspace/screenshots/ and audit JSON in /workspace/QA_AUDIT_REPORT.json.\n",
                encoding="utf-8",
            )
        else:
            (ws / "frames").mkdir(parents=True, exist_ok=True)
            (ws / "README_KEYNOTE.txt").write_text(
                "Target: http://127.0.0.1:19112/ (pre-authenticated in workstation Chromium).\n"
                "Save 6 fullscreen 1920x1080 frames in /workspace/frames/scene_1..6.png, /workspace/nebula_keynote.gif, and /workspace/KEYNOTE_TELEMETRY.json.\n",
                encoding="utf-8",
            )
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_qa_html() -> str:
    rows_html = []
    for inc_id, sev, el_m, wt, acked in INCIDENTS:
        st = "ACKED" if acked else "UNACKED"
        rows_html.append(
            f"<tr data-sev='{sev}' data-elapsed='{el_m}' data-weight='{wt}' data-status='{st}'>"
            f"<td>{inc_id}</td><td><span class='sev-{sev.lower()}'>{sev}</span></td>"
            f"<td>{el_m}</td><td>{wt}</td><td><span class='sla-pill'>{st}</span></td>"
            f"<td><span class='muted-owner-badge'>SRE-ONCALL</span></td></tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>IncidentPulse On-Call Console</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: system-ui, sans-serif; background: #f1f5f9; color: #0f172a; }}
    #qa-brand-bar {{ height: 28px; background: rgb(14, 165, 233); color: #fff; font-weight: 700; font-size: 13px; padding: 4px 14px; display: flex; justify-content: space-between; }}
    header {{ background: #0f172a; color: #f8fafc; padding: 12px 18px; display: flex; justify-content: space-between; align-items: center; }}
    #mobile-nav-drawer {{ display: none; }}
    #sticky-filter-bar {{ position: sticky; top: 0; background: #e2e8f0; padding: 10px 18px; z-index: 5; display: flex; gap: 10px; align-items: center; }}
    #ack-selected-btn {{ height: 44px; padding: 0 16px; background: #0284c7; color: #fff; border: none; border-radius: 4px; font-weight: 600; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    #incident-table-header {{ position: relative; z-index: 2; background: #cbd5e1; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 10px; font-size: 13px; text-align: left; }}
    .muted-owner-badge {{ background: #64748b; color: #7c8594; padding: 2px 6px; border-radius: 3px; font-size: 11px; }}
    .sla-pill {{ display: inline-block; padding: 2px 6px; background: #e0f2fe; border-radius: 3px; }}
    #sla-modal {{ display: none; position: fixed; inset: 0; background: rgba(15,23,42,0.65); z-index: 50; align-items: center; justify-content: center; }}
    #sla-modal.open {{ display: flex; }}
    .modal-card {{ background: #fff; padding: 22px; border-radius: 8px; width: 460px; border: 2px solid #0f172a; }}
    @media (max-width: 767px) {{
      #mobile-nav-drawer {{ display: block; width: 436px; background: #1e293b; color: #bae6fd; padding: 8px 14px; font-size: 12px; }}
      #ack-selected-btn {{ height: 30px; font-size: 12px; }}
    }}
    @media (min-width: 768px) and (max-width: 1199px) {{
      #sticky-filter-bar {{ z-index: 1; }}
      #incident-table-header {{ z-index: 12; }}
      .sla-pill {{ max-width: 48px; overflow: hidden; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
  <div id="qa-brand-bar"><span>INCIDENTPULSE-QA-SURFACE</span><span id="vp-readout">VP</span></div>
  <div id="mobile-nav-drawer">Mobile On-Call Drawer — Active Escalation Queue (24 Live Incidents)</div>
  <header>
    <div><strong>IncidentPulse — Production On-Call Triage</strong></div>
    <button id="open-sla-btn" onclick="openModal()">SLA Policy (?)</button>
  </header>
  <div id="sticky-filter-bar">
    <span><strong>Queue:</strong> 24 Active Incidents</span>
    <button id="ack-selected-btn">Acknowledge Selected</button>
  </div>
  <main style="padding: 12px 18px;">
    <table>
      <thead id="incident-table-header">
        <tr><th>ID</th><th>Severity</th><th>Elapsed (min)</th><th>Impact Weight</th><th>Status</th><th>Owner</th></tr>
      </thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table>
  </main>
  <div id="sla-modal">
    <div class="modal-card">
      <h3>IncidentPulse SLA Breach Thresholds</h3>
      <ul>
        <li><strong>P1 Critical:</strong> Breached when <code>elapsed_min &gt; 15</code></li>
        <li><strong>P2 High:</strong> Breached when <code>elapsed_min &gt; 45</code></li>
        <li><strong>P3 Standard:</strong> Breached when <code>elapsed_min &gt; 180</code></li>
      </ul>
      <p style="font-size:12px;color:#475569;">Weighted MTTR = sum(elapsed_min * impact_weight) / sum(impact_weight).</p>
      <button id="modal-close-btn" onclick="closeModal()">Close Policy Modal</button>
    </div>
  </div>
  <script>
    function updVp() {{
      document.getElementById('vp-readout').textContent = window.innerWidth + 'x' + window.innerHeight;
    }}
    window.addEventListener('resize', updVp); updVp();
    function openModal() {{ document.getElementById('sla-modal').classList.add('open'); }}
    function closeModal() {{ document.getElementById('sla-modal').classList.remove('open'); }}
    window.addEventListener('keydown', (e) => {{
      if (e.key === '?') openModal();
      // Legacy defect: checks non-standard 'Esc' instead of 'Escape'
      if (e.key === 'Esc') closeModal();
    }});
  </script>
</body>
</html>
"""


def _render_story_html() -> str:
    scenes_js = json.dumps([
        {
            "idx": s[0],
            "title": s[1],
            "bar": f"rgb({s[2][0]},{s[2][1]},{s[2][2]})",
            "bg": f"rgb({s[3][0]},{s[3][1]},{s[3][2]})",
            "gbps": s[4],
            "musd": s[5],
            "code": s[6],
        }
        for s in KEYNOTE_SCENES
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>NebulaOps Live Keynote</title>
  <style>
    html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; font-family: system-ui, sans-serif; background: #090d16; color: #f8fafc; }}
    #pause-guard {{ display: none; position: fixed; inset: 0; background: rgb(180, 83, 9); color: #fff; z-index: 100; flex-direction: column; align-items: center; justify-content: center; text-align: center; }}
    #stage {{ width: 100vw; height: 100vh; display: flex; flex-direction: column; justify-content: space-between; }}
    #top-sig-bar {{ height: 96px; width: 100%; display: flex; align-items: center; justify-content: space-between; padding: 0 48px; font-size: 28px; font-weight: 800; box-sizing: border-box; }}
    #center-card {{ margin: auto; width: 1120px; height: 560px; border-radius: 18px; border: 4px solid rgba(255,255,255,0.22); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 22px; }}
    #bottom-nav {{ height: 74px; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: space-between; padding: 0 48px; box-sizing: border-box; }}
    button {{ background: #1e293b; color: #f8fafc; border: 1px solid #64748b; padding: 8px 18px; border-radius: 6px; font-size: 15px; cursor: pointer; }}
  </style>
</head>
<body>
  <div id="pause-guard">
    <h1>STAGE PREVIEW PAUSED — FULLSCREEN 1920x1080 REQUIRED</h1>
    <p id="guard-dim" style="font-size:22px;font-family:monospace;"></p>
  </div>
  <div id="stage">
    <div id="top-sig-bar"><span id="sc-title">Scene</span><span id="sc-code" style="font-family:monospace;">CODE</span></div>
    <div id="center-card">
      <div style="font-size:22px;letter-spacing:2px;opacity:0.85;">NEBULAOPS PRODUCTION TELEMETRY</div>
      <div id="sc-gbps" style="font-size:64px;font-weight:800;">0.0 Gbps</div>
      <div id="sc-musd" style="font-size:32px;color:#fde047;">Annualized Fleet Savings: $0.00M</div>
    </div>
    <div id="bottom-nav">
      <div>
        <button id="prev-btn" onclick="step(-1)">Prev Scene</button>
        <button id="next-btn" onclick="step(1)">Next Scene</button>
      </div>
      <div id="sc-indicator" style="font-family:monospace;font-size:18px;">1 / 6</div>
    </div>
  </div>
  <script>
    const SCENES = {scenes_js};
    let cur = 0;
    function render() {{
      const isFs = (window.innerWidth >= 1840 && window.innerHeight >= 950);
      const pg = document.getElementById('pause-guard');
      if (!isFs) {{
        pg.style.display = 'flex';
        document.getElementById('guard-dim').textContent = 'Current viewport: ' + window.innerWidth + 'x' + window.innerHeight + ' (press F11 or maximize to 1920x1080)';
      }} else {{
        pg.style.display = 'none';
      }}
      const s = SCENES[cur];
      document.body.style.background = s.bg;
      document.getElementById('center-card').style.background = s.bg;
      const bar = document.getElementById('top-sig-bar');
      bar.style.background = s.bar;
      document.getElementById('sc-title').textContent = 'Scene ' + s.idx + ': ' + s.title;
      document.getElementById('sc-code').textContent = s.code;
      document.getElementById('sc-gbps').textContent = s.gbps.toFixed(1) + ' Gbps';
      document.getElementById('sc-musd').textContent = 'Annualized Fleet Savings: $' + s.musd.toFixed(2) + 'M';
      document.getElementById('sc-indicator').textContent = s.idx + ' / 6';
    }}
    function step(d) {{ cur = (cur + d + SCENES.length) % SCENES.length; render(); }}
    function setScene(idx1) {{ if (idx1 >= 1 && idx1 <= 6) {{ cur = idx1 - 1; render(); }} }}
    window.addEventListener('resize', render);
    window.addEventListener('keydown', (e) => {{
      if (e.key === 'ArrowRight') step(1);
      if (e.key === 'ArrowLeft') step(-1);
      if (e.key >= '1' && e.key <= '6') setScene(parseInt(e.key));
    }});
    const u = new URLSearchParams(window.location.search);
    if (u.get('scene')) setScene(parseInt(u.get('scene')));
    render();
  </script>
</body>
</html>
"""


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    qa_cookie = secrets.token_hex(18)
    story_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "qa_hits": 0,
        "story_hits": 0,
        "contention_events": 0,
        "viewport_preemptions": 0,
    }
    write_json(state_p, pstate)

    def _make_handler(cookie_name: str, cookie_val: str, html_fn: Any, hit_key: str) -> Any:
        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *_a: Any) -> None: return

            def _authed(self) -> bool:
                if self.headers.get("X-Internal-Admin") == admin_key:
                    return True
                c = SimpleCookie()
                try:
                    c.load(self.headers.get("Cookie") or "")
                    m = c.get(cookie_name)
                    return bool(m and m.value == cookie_val)
                except Exception:
                    return False

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/health":
                    raw = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                qs = parse_qs(parsed.query)
                if (qs.get("sso_boot") or [""])[0] == boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"{cookie_name}={cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if not self._authed():
                    raw = b'{"error":"Authenticated workstation Chromium session required"}'
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                with lock:
                    pstate[hit_key] += 1
                    write_json(state_p, pstate)
                body = html_fn().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        return H

    srv_qa = ThreadingHTTPServer(("127.0.0.1", port), _make_handler("ec2_qa_sso", qa_cookie, _render_qa_html, "qa_hits"))
    srv_st = ThreadingHTTPServer(("127.0.0.1", STORY_PORT), _make_handler("ec2_story_sso", story_cookie, _render_story_html, "story_hits"))
    threading.Thread(target=srv_st.serve_forever, daemon=True).start()

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(
        json.dumps({
            "mode": "singleton_cdp_chromium",
            "cdp_port": CDP_PORT,
            "urls": [
                f"http://127.0.0.1:{port}/?sso_boot={boot_secret}",
                f"http://127.0.0.1:{STORY_PORT}/?sso_boot={boot_secret}",
            ],
        }) + "\n",
        encoding="utf-8",
    )
    srv_qa.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_p = state_dir / "boot_url"
    if not boot_p.is_file():
        return
    cfg = json.loads(boot_p.read_text(encoding="utf-8"))
    boot_p.unlink(missing_ok=True)
    urls = " ".join(f'"{u}"' for u in cfg["urls"])
    prof_dir = "/opt/ec2_state/chr_shared"
    cmd = (
        f"mkdir -p {prof_dir} && chown -R 1000:0 {prof_dir} && "
        "su -s /bin/bash user -c '"
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; "
        f"nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
        f"--force-renderer-accessibility --remote-debugging-port={CDP_PORT} --remote-allow-origins=* "
        f"--user-data-dir={prof_dir} --window-position=40,30 --window-size=1440,900 {urls} "
        ">/tmp/singleton_chr.log 2>&1 </dev/null &'"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=25)
    time.sleep(2.2)


def _check_rgb_close(c1: tuple[int, int, int], c2: tuple[int, int, int], tol: int = 38) -> bool:
    return all(abs(int(a) - int(b)) <= tol for a, b in zip(c1, c2))


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image
    ws_a = workspace_map["responsive_qa_lead"]
    ws_b = workspace_map["motion_demo_producer"]

    rep_a = read_json_safe(ws_a / "QA_AUDIT_REPORT.json")
    shots_a: dict[str, bool] = {}
    for fn, exp_w, exp_h in (
        ("mobile_390x844.png", 390, 844),
        ("tablet_820x900.png", 820, 900),
        ("desktop_1440x900.png", 1440, 900),
    ):
        fp = ws_a / "screenshots" / fn
        ok_img = False
        if fp.is_file() and fp.stat().st_size > 1500:
            try:
                with Image.open(fp) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    # Accept either exact viewport capture or window capture within +-90px chrome margin
                    dim_ok = abs(w - exp_w) <= 60 and abs(h - exp_h) <= 130
                    # Check top brand bar cyan-blue signature or dark header presence
                    has_cyan = any(
                        _check_rgb_close(rgb.getpixel(( min(w - 1, 80), y )), (14, 165, 233), tol=45)
                        for y in range(0, min(h, 150), 3)
                    )
                    ok_img = bool(dim_ok and has_cyan)
            except Exception:
                ok_img = False
        shots_a[fn] = ok_img

    checks_a: list[tuple[str, bool, float, str]] = [
        ("shot_mobile_390", shots_a["mobile_390x844.png"], 0.10, "Missing or invalid mobile_390x844.png"),
        ("shot_tablet_820", shots_a["tablet_820x900.png"], 0.10, "Missing or invalid tablet_820x900.png"),
        ("shot_desktop_1440", shots_a["desktop_1440x900.png"], 0.10, "Missing or invalid desktop_1440x900.png"),
        ("total_and_breached", rep_a.get("total_incidents") == QA_ORACLE["total_incidents"] and rep_a.get("sla_breached_count") == QA_ORACLE["sla_breached_count"], 0.15, f"sla_breached_count={rep_a.get('sla_breached_count')} != {QA_ORACLE['sla_breached_count']}"),
        ("p1_unacked_ids", rep_a.get("p1_unacked_ids") == QA_ORACLE["p1_unacked_ids"], 0.10, "p1_unacked_ids mismatch"),
        ("weighted_mttr", isinstance(rep_a.get("weighted_mean_mttr_min"), (int, float)) and abs(float(rep_a["weighted_mean_mttr_min"]) - QA_ORACLE["weighted_mean_mttr_min"]) <= 0.15, 0.10, f"weighted_mean_mttr_min={rep_a.get('weighted_mean_mttr_min')} != {QA_ORACLE['weighted_mean_mttr_min']}"),
        ("mobile_overflow_and_btn", isinstance(rep_a.get("mobile_overflow_px"), (int, float)) and abs(float(rep_a["mobile_overflow_px"]) - QA_ORACLE["mobile_overflow_px"]) <= 12 and isinstance(rep_a.get("mobile_ack_btn_height_px"), (int, float)) and abs(float(rep_a["mobile_ack_btn_height_px"]) - 30) <= 3, 0.15, "mobile_overflow_px or mobile_ack_btn_height_px inaccurate"),
        ("tablet_zindex", rep_a.get("tablet_filter_zindex_inverted") is True, 0.08, "tablet_filter_zindex_inverted not detected"),
        ("desktop_escape_bug", rep_a.get("desktop_escape_closes_modal") is False, 0.06, "desktop_escape_closes_modal should be false"),
        ("wcag_selector", str(rep_a.get("wcag_low_contrast_selector", "")).strip() in (".muted-owner-badge", "span.muted-owner-badge"), 0.06, "wcag_low_contrast_selector mismatch"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = []
    for idx, _title, bar_rgb, bg_rgb, _gbps, _musd, _code in KEYNOTE_SCENES:
        fp = ws_b / "frames" / f"scene_{idx}.png"
        frame_ok = False
        if fp.is_file() and fp.stat().st_size > 4000:
            try:
                with Image.open(fp) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    if w >= 1860 and h >= 1020:
                        bg_px = rgb.getpixel((120, h // 2))
                        # Ensure NOT pause-guard amber (180, 83, 9) and matches scene signature
                        not_paused = not _check_rgb_close(bg_px, (180, 83, 9), tol=30)
                        bar_hit = any(
                            _check_rgb_close(rgb.getpixel((180, yy)), bar_rgb, tol=42)
                            for yy in range(20, 190, 8)
                        )
                        frame_ok = bool(not_paused and bar_hit and _check_rgb_close(bg_px, bg_rgb, tol=40))
            except Exception:
                frame_ok = False
        checks_b.append((f"scene_{idx}_frame", frame_ok, 0.10, f"scene_{idx}.png missing, not 1920x1080 fullscreen, paused, or photobombed"))

    gif_p = ws_b / "nebula_keynote.gif"
    gif_ok = False
    if gif_p.is_file() and gif_p.stat().st_size > 8000:
        try:
            with Image.open(gif_p) as gim:
                n_frames = getattr(gim, "n_frames", 1)
                gw, gh = gim.size
                gif_ok = bool(n_frames >= 6 and gw >= 960 and gh >= 540)
        except Exception:
            gif_ok = False
    checks_b.append(("animated_gif_6frames", gif_ok, 0.15, "nebula_keynote.gif missing, <6 frames, or <960x540"))

    rep_b = read_json_safe(ws_b / "KEYNOTE_TELEMETRY.json")
    exp_codes = [s[6] for s in KEYNOTE_SCENES]
    exp_peak = max(s[4] for s in KEYNOTE_SCENES)
    exp_sav = round(sum(s[5] for s in KEYNOTE_SCENES), 2)
    checks_b.append(("scene_codes", rep_b.get("scene_codes") == exp_codes, 0.10, "KEYNOTE_TELEMETRY.json scene_codes mismatch"))
    checks_b.append(("peak_throughput", isinstance(rep_b.get("peak_throughput_gbps"), (int, float)) and abs(float(rep_b["peak_throughput_gbps"]) - exp_peak) <= 0.2, 0.08, "peak_throughput_gbps mismatch"))
    checks_b.append(("total_savings", isinstance(rep_b.get("total_annual_savings_musd"), (int, float)) and abs(float(rep_b["total_annual_savings_musd"]) - exp_sav) <= 0.05, 0.07, "total_annual_savings_musd mismatch"))

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=None,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.90,
    )


def _cdp_activate_and_resize(url_substr: str, x: int, y: int, w: int, h: int, fullscreen: bool = False) -> None:
    import urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5) as r:
        tabs = json.loads(r.read().decode("utf-8"))
    for t in tabs:
        if url_substr in str(t.get("url", "")):
            tid = t["id"]
            urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/activate/{tid}", timeout=5).read()
            break
    fs_cmd = 'wmctrl -i -r "$wid" -b add,maximized_vert,maximized_horz,fullscreen 2>/dev/null || true;' if fullscreen else ""
    gui_cmd = (
        "export DISPLAY=:99; "
        "wid=$(wmctrl -lx | grep -i chromium | tail -n 1 | awk '{print $1}'); "
        "if [ -n \"$wid\" ]; then "
        "  wmctrl -i -r \"$wid\" -b remove,fullscreen,maximized_vert,maximized_horz 2>/dev/null || true; "
        f"  wmctrl -i -r \"$wid\" -e 0,{x},{y},{w},{h} 2>/dev/null || true; "
        "  wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.2; "
        f"  {fs_cmd} "
        "fi"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_cmd], capture_output=True, timeout=10)
    time.sleep(0.5)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    from PIL import Image
    assert role in ("responsive_qa_lead", "motion_demo_producer")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "responsive_qa_lead":
            (ws / "screenshots").mkdir(parents=True, exist_ok=True)
            for fn, vw, vh in (
                ("mobile_390x844.png", 390, 844),
                ("tablet_820x900.png", 820, 900),
                ("desktop_1440x900.png", 1440, 900),
            ):
                _cdp_activate_and_resize(f":{port}", 20, 10, vw, min(1060, vh + 85), fullscreen=False)
                out_p = ws / "screenshots" / fn
                subprocess.run(
                    ["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 import -window root -crop {vw}x{vh}+20+90 +repage {out_p}"],
                    check=True, capture_output=True, timeout=10,
                )
            write_json(ws / "QA_AUDIT_REPORT.json", QA_ORACLE)
        else:
            (ws / "frames").mkdir(parents=True, exist_ok=True)
            _cdp_activate_and_resize(f":{STORY_PORT}", 0, 0, 1920, 1080, fullscreen=True)
            frames_pil: list[Any] = []
            for idx in range(1, 7):
                subprocess.run(
                    ["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 xdotool mousemove 960 540 click 1 key --clearmodifiers {idx}"],
                    check=True, capture_output=True, timeout=10,
                )
                time.sleep(0.35)
                fp = ws / "frames" / f"scene_{idx}.png"
                subprocess.run(
                    ["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 import -window root {fp}"],
                    check=True, capture_output=True, timeout=10,
                )
                frames_pil.append(Image.open(fp).convert("RGB").resize((960, 540)))
            frames_pil[0].save(
                ws / "nebula_keynote.gif",
                save_all=True,
                append_images=frames_pil[1:],
                duration=350,
                loop=0,
            )
            write_json(
                ws / "KEYNOTE_TELEMETRY.json",
                {
                    "scene_codes": [s[6] for s in KEYNOTE_SCENES],
                    "peak_throughput_gbps": max(s[4] for s in KEYNOTE_SCENES),
                    "total_annual_savings_musd": round(sum(s[5] for s in KEYNOTE_SCENES), 2),
                },
            )

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (Shared-Screen Track): Role A resizes singleton Chromium to 390x844 mid-capture while Role B records."""
    solve_role("responsive_qa_lead", workspace_map, port, careful_conc=False)
    solve_role("motion_demo_producer", workspace_map, port, careful_conc=False)
    # Now simulate unguarded concurrent resize + tab switch during Scene 3 & 4 capture:
    _cdp_activate_and_resize(f":{port}", 20, 20, 390, 844, fullscreen=False)
    ws_b = workspace_map["motion_demo_producer"]
    for idx in (3, 4):
        fp = ws_b / "frames" / f"scene_{idx}.png"
        subprocess.run(["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 import -window root {fp}"], check=True, capture_output=True, timeout=10)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    st["viewport_preemptions"] = int(st.get("viewport_preemptions", 0)) + 2
    write_json(sp, st)

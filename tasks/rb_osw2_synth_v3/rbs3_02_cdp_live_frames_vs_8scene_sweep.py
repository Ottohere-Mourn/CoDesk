"""RBS3-02: Singleton :9222 4-Breakpoint Pixel-Verified FinOps QA vs. 8-Scene 0.7s Fullscreen Sweep Reel.

Grounded in OSW2-P5 (Role A 0.939 -> 0.000) & EC2-C01 (both models dropped -0.050 / -0.085) + LAW_8:
  - Both roles share ONE singleton Chromium (--remote-debugging-port=9222) and DISPLAY=:99.
  - Role A must capture 4 live PNGs at exact responsive breakpoints (375x812, 768x900, 1024x768, 1440x900),
    each rendering a distinct CSS @media ribbon color, plus audit 30 FinOps rows & 2 interactive modals.
  - Role B must hold unobstructed 1920x1080 fullscreen (`>=1840x940` and `visibilityState==='visible'`) across
    the full 0.7s live sweep of each of 8 telemetry scenes to unlock each scene's canvas bar & KPI code.
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
import urllib.request

from tasks.rb_osw2_synth_v3.common import (
    advisory_lock,
    boot_singleton_cdp_chromium,
    build_grade_payload,
    cdp_eval_js,
    cdp_list_targets,
    read_json_safe,
    write_json,
)

TASK_ID = "RBS3-02"
PORTAL_PORT = 19502
ORBIT_PORT = 19512
CDP_PORT = 9222

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Singleton :9222 4-Breakpoint Pixel-Verified FinOps QA vs. 8-Scene Live Fullscreen Telemetry Sweep",
    "domain": "Responsive FinOps Web QA & Unobstructed Fullscreen Motion Telemetry Capture",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING",
        "LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
    ),
    "roles": ("finops_viewport_auditor", "orbit_reel_director"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (ORBIT_PORT,),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1080,
    "iso_role_timeout_s": 1080,
    "max_cua_calls": 42,
    "factory_blueprint": {
        "horizon_band": "non_saturated_coupled_contention",
        "total_subchecks": 40,
        "cli_bypass_resistance": 0.98,
        "role_a": {
            "slug": "finops_viewport_auditor",
            "est_role_seconds": 480.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "singleton_cdp_browser",
                "viewport_resize_vs_fullscreen_capture",
                "modal_file_or_rule_dialog",
            ],
        },
        "role_b": {
            "slug": "orbit_reel_director",
            "est_role_seconds": 500.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "singleton_cdp_browser",
                "viewport_resize_vs_fullscreen_capture",
                "overlapping_docks_or_root_screencap",
            ],
        },
    },
}

# 30 FinOps cloud invoices: (inv_id, tier, overage_pct, usd_amt, disputed)
# SLA breach rule (in '?' SLA Drawer): T1 breached if overage_pct > 12; T2 if > 25; T3 if > 40.
FINOPS_ROWS: list[tuple[str, str, int, float, bool]] = [
    ("INV-201", "T1", 18, 4200.0, True),
    ("INV-202", "T1",  9, 3100.0, False),
    ("INV-203", "T1", 12, 2800.0, False),  # boundary 12 -> NOT breached (>12)
    ("INV-204", "T1", 24, 5600.0, True),
    ("INV-205", "T1", 15, 3900.0, False),
    ("INV-206", "T2", 31, 2700.0, False),
    ("INV-207", "T2", 25, 2200.0, False),  # boundary 25 -> NOT breached (>25)
    ("INV-208", "T2", 19, 1850.0, False),
    ("INV-209", "T2", 38, 3400.0, True),
    ("INV-210", "T2", 29, 2600.0, False),
    ("INV-211", "T3", 48, 1500.0, False),
    ("INV-212", "T3", 40, 1200.0, False),  # boundary 40 -> NOT breached (>40)
    ("INV-213", "T3", 33,  980.0, False),
    ("INV-214", "T3", 55, 1750.0, True),
    ("INV-215", "T1", 21, 6100.0, True),
    ("INV-216", "T2", 27, 2950.0, False),
    ("INV-217", "T3", 44, 1420.0, False),
    ("INV-218", "T1",  7, 2400.0, False),
    ("INV-219", "T2", 34, 3150.0, False),
    ("INV-220", "T3", 18,  890.0, False),
    ("INV-221", "T1", 14, 4700.0, False),
    ("INV-222", "T2", 22, 2100.0, False),
    ("INV-223", "T3", 52, 1680.0, True),
    ("INV-224", "T1", 19, 5300.0, True),
]

BREAKPOINT_SPECS: list[tuple[str, int, int, tuple[int, int, int]]] = [
    ("vp_375x812.png",  375, 812, (244, 63, 94)),    # #F43F5E coral (<600px)
    ("vp_768x900.png",  768, 900, (99, 102, 241)),   # #6366F1 indigo (600..900px)
    ("vp_1024x768.png", 1024, 768, (245, 158, 11)),  # #F59E0B amber (901..1200px)
    ("vp_1440x900.png", 1440, 900, (16, 185, 129)),  # #10B981 emerald (>1200px)
]


def _compute_finops_oracle() -> dict[str, Any]:
    caps = {"T1": 12, "T2": 25, "T3": 40}
    breached = [r[0] for r in FINOPS_ROWS if r[2] > caps[r[1]]]
    t1_disp = sorted(r[0] for r in FINOPS_ROWS if r[1] == "T1" and r[4])
    breach_usd = round(sum(r[3] for r in FINOPS_ROWS if r[2] > caps[r[1]]), 2)
    # FX modal rule: EUR->USD 1.085, JPY->USD 0.0068, surcharge 2.5% on disputed T1
    fx_eur_rate = 1.085
    return {
        "total_invoices": len(FINOPS_ROWS),
        "breached_count": len(breached),
        "t1_disputed_ids": t1_disp,
        "breached_total_usd": breach_usd,
        "fx_eur_usd_rate": fx_eur_rate,
        "mobile_375_overflow_px": 165,
        "mobile_approve_btn_height_px": 28,
        "fx_modal_escape_closes": False,
    }


FINOPS_ORACLE = _compute_finops_oracle()

# 8 OrbitMesh scenes: (idx, name, bar_rgb, bg_rgb, latency_ms, flux_gbps, kpi_code)
ORBIT_SCENES: list[tuple[int, str, tuple[int, int, int], tuple[int, int, int], float, float, str]] = [
    (1, "LEO_ISL_BACKBONE",    (6, 182, 212),   (11, 18, 32), 14.2, 184.0, "ORB-S1-3190"),
    (2, "GROUND_GATEWAY_EU",   (59, 130, 246),  (13, 20, 36), 21.8, 146.5, "ORB-S2-5824"),
    (3, "KA_BAND_BEAM_HOP",    (139, 92, 246),  (18, 16, 36), 18.6, 212.4, "ORB-S3-7401"),
    (4, "OPTICAL_DOPPLER_PLL", (236, 72, 153),  (24, 15, 30),  9.4, 295.0, "ORB-S4-6618"),
    (5, "POLAR_HANDOFF_RING",  (245, 158, 11),  (24, 20, 16), 27.5, 128.2, "ORB-S5-4093"),
    (6, "EPHEMERIS_KALMAN",    (16, 185, 129),  (10, 24, 24), 11.9, 176.8, "ORB-S6-8527"),
    (7, "SOLAR_FLARE_FEC",     (99, 102, 241),  (15, 18, 38), 33.1, 118.6, "ORB-S7-2946"),
    (8, "CONSTELLATION_SYNC",  (20, 184, 166),  (11, 24, 28), 16.0, 248.5, "ORB-S8-9175"),
]


def _build_finops_html() -> str:
    tr_html = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}%</td><td>${r[3]:.2f}</td><td>{'YES' if r[4] else 'NO'}</td></tr>"
        for r in FINOPS_ROWS
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>GridFlow FinOps</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f8fafc;color:#0f172a;overflow-x:auto;}}
#bpRibbon{{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;color:#fff;font-weight:700;background:#10b981;}}
@media (max-width: 1200px){{#bpRibbon{{background:#f59e0b;}}}}
@media (max-width: 900px){{#bpRibbon{{background:#6366f1;}}}}
@media (max-width: 599px){{#bpRibbon{{background:#f43f5e;}}}}
#wideHero{{width:540px;background:#e2e8f0;padding:8px;box-sizing:border-box;border:2px solid #475569;}}
#approveBtn{{height:28px;line-height:24px;padding:0 12px;box-sizing:border-box;background:#0f172a;color:#fff;border:none;}}
table{{border-collapse:collapse;width:96%;margin:10px auto;background:#fff;}}
th,td{{border:1px solid #cbd5e1;padding:5px 8px;font-size:12px;}}
.dlg{{display:none;position:fixed;left:18%;top:16%;width:440px;background:#fff;border:3px solid #0f172a;padding:16px;z-index:60;}}
</style></head><body>
<div id="bpRibbon"><span>GridFlow FinOps Cloud Billing Audit</span><span id="vpTxt"></span></div>
<div style="padding:10px 16px;display:flex;gap:10px;align-items:center;">
  <button id="approveBtn">Approve Batch</button>
  <button onclick="document.getElementById('slaDrawer').style.display='block'">SLA Thresholds (?)</button>
  <button onclick="document.getElementById('fxModal').style.display='block'">FX Matrix (Ctrl+K)</button>
</div>
<div id="wideHero">Multi-Cloud Commitment Utilization Banner (Fixed 540px Hero)</div>
<table><thead><tr><th>Invoice</th><th>Tier</th><th>Overage</th><th>Amount_USD</th><th>Disputed</th></tr></thead><tbody>{tr_html}</tbody></table>
<div id="slaDrawer" class="dlg">
  <h3>Tier SLA Breach Rules</h3>
  <p>Strictly breached when <code>Overage &gt; 12%</code> (T1), <code>Overage &gt; 25%</code> (T2), or <code>Overage &gt; 40%</code> (T3).</p>
  <button onclick="document.getElementById('slaDrawer').style.display='none'">Close</button>
</div>
<div id="fxModal" class="dlg" role="dialog" aria-label="Preferences">
  <h3>FX Settlement Matrix</h3>
  <p><code>fx_eur_usd_rate = 1.085</code> | <code>fx_jpy_usd_rate = 0.0068</code></p>
  <button onclick="document.getElementById('fxModal').style.display='none'">Close FX</button>
</div>
<script>
function upd(){{ document.getElementById('vpTxt').textContent = window.innerWidth + 'x' + window.innerHeight; }}
window.addEventListener('resize', upd); upd();
window.addEventListener('keydown', e=>{{
  if(e.key==='?') document.getElementById('slaDrawer').style.display='block';
  if(e.ctrlKey && e.key.toLowerCase()==='k'){{ e.preventDefault(); document.getElementById('fxModal').style.display='block'; }}
  if(e.key==='Escape'){{ document.getElementById('slaDrawer').style.display='none'; /* intentional defect: fxModal ignores Escape */ }}
}});
</script></body></html>"""


def _build_orbit_html() -> str:
    sc_js = json.dumps([
        {"idx": s[0], "name": s[1], "bar": f"rgb({s[2][0]},{s[2][1]},{s[2][2]})", "bg": f"rgb({s[3][0]},{s[3][1]},{s[3][2]})"}
        for s in ORBIT_SCENES
    ])
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>OrbitMesh Telemetry</title>
<style>
html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;font-family:monospace;background:#1e1b18;color:#f8fafc;}}
#sigBar{{height:88px;width:100%;display:flex;align-items:center;justify-content:space-between;padding:0 28px;box-sizing:border-box;font-size:22px;font-weight:700;background:#991b1b;}}
#mainArea{{height:calc(100% - 88px);display:flex;flex-direction:column;align-items:center;justify-content:center;}}
button{{padding:8px 14px;font-size:15px;font-weight:700;cursor:pointer;margin:0 6px;}}
</style></head><body>
<div id="sigBar"><span id="scTitle">NOT_SWEPT</span><span id="scStatus">REQUIRE F11 FULLSCREEN + 0.6s SWEEP</span></div>
<div id="mainArea">
  <div>
    <button onclick="setSc(cur-1)">Prev</button>
    <button id="btnSweep" onclick="runSweep()">Run Fullscreen Sweep (Space)</button>
    <button onclick="setSc(cur+1)">Next</button>
  </div>
  <h1 id="scCode" style="font-size:46px;margin-top:28px;">LOCKED</h1>
  <p id="scMetrics" style="font-size:24px;">Viewport must remain &gt;=1840x940 &amp; visible during sweep</p>
</div>
<script>
const SCS = {sc_js};
let cur = 0;
function markDirty(){{
  const s = SCS[cur];
  document.body.style.background = '#78350f';
  document.getElementById('sigBar').style.background = '#991b1b';
  document.getElementById('scTitle').textContent = 'SCENE ' + s.idx + ': ' + s.name + ' [UNVERIFIED]';
  document.getElementById('scCode').textContent = 'LOCKED';
}}
function setSc(k){{ cur = (k + SCS.length) % SCS.length; markDirty(); }}
async function runSweep(){{
  const s = SCS[cur];
  const w0 = window.innerWidth, h0 = window.innerHeight, v0 = document.visibilityState;
  await new Promise(r => setTimeout(r, 600));
  const w1 = window.innerWidth, h1 = window.innerHeight, v1 = document.visibilityState;
  const q = `/api/orbit/sweep?idx=${{s.idx}}&w0=${{w0}}&h0=${{h0}}&w1=${{w1}}&h1=${{h1}}&vis=${{(v0==='visible'&&v1==='visible')?1:0}}`;
  const resp = await fetch(q);
  const d = await resp.json();
  if(d.ok){{
    document.body.style.background = s.bg;
    document.getElementById('sigBar').style.background = s.bar;
    document.getElementById('scTitle').textContent = 'SCENE ' + s.idx + ': ' + s.name;
    document.getElementById('scStatus').textContent = 'SWEEP_VERIFIED_1920x1080';
    document.getElementById('scCode').textContent = d.code;
    document.getElementById('scMetrics').textContent = 'Latency=' + d.lat + ' ms | Flux=' + d.flux + ' Gbps';
  }} else {{
    markDirty();
    document.getElementById('scStatus').textContent = 'SWEEP_ABORTED (' + w1 + 'x' + h1 + ')';
  }}
}}
window.addEventListener('resize', () => {{ if(window.innerWidth < 1840 || window.innerHeight < 940) markDirty(); }});
window.addEventListener('keydown', e => {{
  if(e.key >= '1' && e.key <= '8'){{ cur = parseInt(e.key) - 1; markDirty(); }}
  if(e.key === ' '){{ e.preventDefault(); runSweep(); }}
}});
markDirty();
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Multi-Breakpoint FinOps Responsive & Modal QA Work Order — {b}finops_viewport_auditor{b}",
        "",
        "## Scope & Deliverables",
        f"Audit **GridFlow FinOps** at {b}http://127.0.0.1:{PORTAL_PORT}/{b} in the workstation Chromium browser (`127.0.0.1:9222`) across four exact responsive viewports and both interactive policy modals.",
        "",
        "Deliverables:",
        f"1. **Four Live Breakpoint PNG Captures ({b}/workspace/captures/{b})**:",
        "   - Resize and capture the live rendered GridFlow FinOps viewport (including its responsive `#bpRibbon` top bar) at four exact resolutions:",
        f"     - {b}/workspace/captures/vp_375x812.png{b} (`375 x 812`)",
        f"     - {b}/workspace/captures/vp_768x900.png{b} (`768 x 900`)",
        f"     - {b}/workspace/captures/vp_1024x768.png{b} (`1024 x 768`)",
        f"     - {b}/workspace/captures/vp_1440x900.png{b} (`1440 x 900`)",
        f"2. **FinOps QA Audit JSON ({b}/workspace/FINOPS_QA.json{b})** with exact keys:",
        f"   - {b}\"total_invoices\"{b} (int), {b}\"breached_count\"{b} (int: invoices strictly exceeding their Tier SLA cap from the `?` SLA drawer), {b}\"t1_disputed_ids\"{b} (sorted list of disputed `T1` invoice IDs), {b}\"breached_total_usd\"{b} (float, 2 decimals)",
        f"   - {b}\"fx_eur_usd_rate\"{b} (float from `Ctrl+K` FX modal), {b}\"mobile_375_overflow_px\"{b} (int: horizontal overflow of `#wideHero` at `375px` width), {b}\"mobile_approve_btn_height_px\"{b} (int: rendered height of `#approveBtn`), and {b}\"fx_modal_escape_closes\"{b} (bool: whether `Escape` closes `#fxModal`).",
        "",
    ])
    role_b = "\n".join([
        f"# 8-Scene Unobstructed 1920x1080 OrbitMesh Telemetry Reel Work Order — {b}orbit_reel_director{b}",
        "",
        "## Scope & Deliverables",
        f"Capture an unobstructed `1920x1080` fullscreen 8-scene telemetry walkthrough of **OrbitMesh Telemetry** at {b}http://127.0.0.1:{ORBIT_PORT}/{b} in the workstation Chromium browser (`127.0.0.1:9222`).",
        "",
        "Deliverables:",
        f"1. **8 Verified Fullscreen Scene PNGs ({b}/workspace/frames/scene_1.png{b} .. {b}scene_8.png{b})**:",
        "   - Place Chromium into unobstructed `1920x1080` fullscreen (`F11` / `>=1840x940` visible tab) and for each scene `1..8`, run its `0.6s` Fullscreen Sweep (`Space` or `Run Fullscreen Sweep`) so `#sigBar` switches from red/amber to the scene's verified color band and displays its `ORB-S*` code, then save a `1920x1080` PNG of the rendered screen.",
        f"2. **Animated Walkthrough GIF ({b}/workspace/orbit_walkthrough.gif{b})**:",
        "   - Combine all 8 verified scene frames in order into an animated GIF (`>= 8` frames, `>= 960x540`).",
        f"3. **Telemetry Manifest ({b}/workspace/ORBIT_MANIFEST.json{b})** with exact keys:",
        f"   - {b}\"scene_codes\"{b} (list of 8 `ORB-S1-...` .. `ORB-S8-...` strings), {b}\"mean_latency_ms\"{b} (float, rounded to 2 decimals), and {b}\"total_flux_gbps\"{b} (float, rounded to 1 decimal).",
        "",
    ])
    return {"finops_viewport_auditor": role_a, "orbit_reel_director": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["finops_viewport_auditor"]
    ws_b = workspace_map["orbit_reel_director"]
    (ws_a / "captures").mkdir(parents=True, exist_ok=True)
    (ws_b / "frames").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_tok = secrets.token_hex(16)
    sso_val = secrets.token_hex(18)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0, "aborted_sweeps": 0})
    fin_bytes = _build_finops_html().encode("utf-8")
    orb_bytes = _build_orbit_html().encode("utf-8")
    orb_map = {s[0]: (s[4], s[5], s[6]) for s in ORBIT_SCENES}
    lock = threading.Lock()

    def _ok_cookie(hdrs: Any, cname: str) -> bool:
        c = SimpleCookie()
        try:
            c.load(hdrs.get("Cookie") or "")
            m = c.get(cname)
            return bool(m and m.value == sso_val)
        except Exception:
            return False

    class FinHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302); self.send_header("Set-Cookie", f"rbs302_fin={sso_val}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not _ok_cookie(self.headers, "rbs302_fin"):
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: use live Chromium"); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(fin_bytes))); self.end_headers(); self.wfile.write(fin_bytes)

    class OrbHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302); self.send_header("Set-Cookie", f"rbs302_orb={sso_val}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not _ok_cookie(self.headers, "rbs302_orb"):
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: use live Chromium"); return
            if parsed.path == "/api/orbit/sweep":
                idx = int((qs.get("idx") or ["1"])[0])
                w0 = int((qs.get("w0") or ["0"])[0]); h0 = int((qs.get("h0") or ["0"])[0])
                w1 = int((qs.get("w1") or ["0"])[0]); h1 = int((qs.get("h1") or ["0"])[0])
                vis = (qs.get("vis") or ["0"])[0] == "1"
                ok = bool(vis and w0 >= 1840 and h0 >= 940 and w1 >= 1840 and h1 >= 940 and idx in orb_map)
                if not ok:
                    with lock:
                        st = read_json_safe(state_dir / "service_state.json")
                        st["aborted_sweeps"] = int(st.get("aborted_sweeps", 0)) + 1
                        write_json(state_dir / "service_state.json", st)
                lat, flux, code = orb_map.get(idx, (0.0, 0.0, "LOCKED"))
                raw = json.dumps({"ok": ok, "lat": lat if ok else None, "flux": flux if ok else None, "code": code if ok else "SWEEP_ABORTED"}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
                return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(orb_bytes))); self.end_headers(); self.wfile.write(orb_bytes)

    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", ORBIT_PORT), OrbHandler).serve_forever, daemon=True).start()
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(
        json.dumps({"urls": [f"http://127.0.0.1:{port}/?sso_boot={boot_tok}", f"http://127.0.0.1:{ORBIT_PORT}/?sso_boot={boot_tok}"]}) + "\n",
        encoding="utf-8",
    )
    ThreadingHTTPServer(("127.0.0.1", port), FinHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    cfg = read_json_safe(state_dir / "boot_url")
    boot_singleton_cdp_chromium(list(cfg.get("urls") or []), window_size=(1440, 900))


def _rgb_close(c1: tuple[int, int, int], c2: tuple[int, int, int], tol: int = 42) -> bool:
    return all(abs(int(c1[i]) - int(c2[i])) <= tol for i in range(3))


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image

    ws_a = workspace_map["finops_viewport_auditor"]
    ws_b = workspace_map["orbit_reel_director"]
    qa = read_json_safe(ws_a / "FINOPS_QA.json")

    checks_a: list[tuple[str, bool, float, str]] = []
    for fn, ew, eh, exp_rgb in BREAKPOINT_SPECS:
        fp = ws_a / "captures" / fn
        dim_ok, col_ok = False, False
        if fp.is_file() and fp.stat().st_size > 1200:
            try:
                with Image.open(fp) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    dim_ok = abs(w - ew) <= 55 and abs(h - eh) <= 130
                    col_ok = any(_rgb_close(rgb.getpixel((min(w - 1, 70), yy)), exp_rgb, tol=42) for yy in range(0, min(h, 130), 3))
            except Exception:
                dim_ok, col_ok = False, False
        checks_a.append((f"a_{fn}_dim", dim_ok, 0.05, f"{fn} missing or wrong dimensions (expected ~{ew}x{eh})"))
        checks_a.append((f"a_{fn}_ribbon_rgb", dim_ok and col_ok, 0.06, f"{fn} missing responsive @media ribbon color {exp_rgb}"))

    checks_a.extend([
        ("a_json_exists", (ws_a / "FINOPS_QA.json").is_file(), 0.04, "Missing FINOPS_QA.json"),
        ("a_tot_inv", qa.get("total_invoices") == FINOPS_ORACLE["total_invoices"], 0.04, "total_invoices != 24"),
        ("a_breached_cnt", qa.get("breached_count") == FINOPS_ORACLE["breached_count"], 0.07, f"breached_count != {FINOPS_ORACLE['breached_count']}"),
        ("a_t1_disputed", qa.get("t1_disputed_ids") == FINOPS_ORACLE["t1_disputed_ids"], 0.06, "t1_disputed_ids mismatch"),
        ("a_breached_usd", isinstance(qa.get("breached_total_usd"), (int, float)) and abs(float(qa["breached_total_usd"]) - FINOPS_ORACLE["breached_total_usd"]) <= 1.0, 0.07, f"breached_total_usd != {FINOPS_ORACLE['breached_total_usd']}"),
        ("a_fx_eur", isinstance(qa.get("fx_eur_usd_rate"), (int, float)) and abs(float(qa["fx_eur_usd_rate"]) - 1.085) <= 0.005, 0.05, "fx_eur_usd_rate != 1.085"),
        ("a_overflow_165", isinstance(qa.get("mobile_375_overflow_px"), (int, float)) and abs(float(qa["mobile_375_overflow_px"]) - 165) <= 14, 0.06, "mobile_375_overflow_px != 165"),
        ("a_btn_h_28", isinstance(qa.get("mobile_approve_btn_height_px"), (int, float)) and abs(float(qa["mobile_approve_btn_height_px"]) - 28) <= 3, 0.05, "mobile_approve_btn_height_px != 28"),
        ("a_fx_esc_false", qa.get("fx_modal_escape_closes") is False, 0.05, "fx_modal_escape_closes should be False"),
        ("a_no_boundary_false_pos", bool(qa) and qa.get("breached_count") != 18, 0.04, "Counted >= instead of strict > on SLA boundary rows"),
        ("a_all_4_pngs", sum(1 for fn, *_ in BREAKPOINT_SPECS if (ws_a / "captures" / fn).is_file()) == 4, 0.04, "Fewer than 4 capture PNGs saved"),
        ("a_t1_disp_count4", len(qa.get("t1_disputed_ids") or []) == 4, 0.04, "t1_disputed_ids length != 4"),
    ])

    # --- Role B: 8 fullscreen sweep frames + GIF + manifest (20 subchecks) ---
    checks_b: list[tuple[str, bool, float, str]] = []
    valid_frames = 0
    for idx, _nm, bar_rgb, bg_rgb, _lat, _flx, _cd in ORBIT_SCENES:
        fp = ws_b / "frames" / f"scene_{idx}.png"
        f_ok = False
        if fp.is_file() and fp.stat().st_size > 3000:
            try:
                with Image.open(fp) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    if w >= 1840 and h >= 980:
                        bg_px = rgb.getpixel((140, h // 2))
                        not_dirty = not _rgb_close(bg_px, (120, 53, 15), tol=32)
                        bar_ok = any(_rgb_close(rgb.getpixel((200, yy)), bar_rgb, tol=42) for yy in range(15, 175, 8))
                        f_ok = bool(not_dirty and bar_ok and _rgb_close(bg_px, bg_rgb, tol=38))
            except Exception:
                f_ok = False
        if f_ok:
            valid_frames += 1
        checks_b.append((f"b_scene_{idx}_png", f_ok, 0.06, f"scene_{idx}.png missing, <1840x980, un-swept, or photobombed"))

    gif_p = ws_b / "orbit_walkthrough.gif"
    gif_ok = False
    if gif_p.is_file() and gif_p.stat().st_size > 6000:
        try:
            with Image.open(gif_p) as gim:
                gif_ok = getattr(gim, "n_frames", 1) >= 8 and gim.size[0] >= 960 and gim.size[1] >= 540
        except Exception:
            gif_ok = False

    man = read_json_safe(ws_b / "ORBIT_MANIFEST.json")
    exp_codes = [s[6] for s in ORBIT_SCENES]
    codes = man.get("scene_codes") if isinstance(man.get("scene_codes"), list) else []
    code_hits = sum(1 for i, c in enumerate(exp_codes) if i < len(codes) and codes[i] == c)
    true_mean_lat = round(sum(s[4] for s in ORBIT_SCENES) / 8.0, 2)
    true_tot_flux = round(sum(s[5] for s in ORBIT_SCENES), 1)

    checks_b.extend([
        ("b_frames_half4", valid_frames >= 4, 0.05, f"Verified fullscreen frames {valid_frames}/8 < 4"),
        ("b_frames_6", valid_frames >= 6, 0.05, f"Verified fullscreen frames {valid_frames}/8 < 6"),
        ("b_gif_exists", gif_p.is_file(), 0.04, "Missing orbit_walkthrough.gif"),
        ("b_gif_8frames", gif_ok, 0.06, "orbit_walkthrough.gif <8 frames or <960x540"),
        ("b_man_exists", (ws_b / "ORBIT_MANIFEST.json").is_file(), 0.04, "Missing ORBIT_MANIFEST.json"),
        ("b_codes_half4", code_hits >= 4, 0.05, f"scene_codes accurate {code_hits}/8 < 4"),
        ("b_codes_6", code_hits >= 6, 0.05, f"scene_codes accurate {code_hits}/8 < 6"),
        ("b_codes_all8", code_hits == 8, 0.06, f"scene_codes accurate {code_hits}/8 != 8"),
        ("b_mean_lat", isinstance(man.get("mean_latency_ms"), (int, float)) and abs(float(man["mean_latency_ms"]) - true_mean_lat) <= 0.15, 0.05, f"mean_latency_ms != {true_mean_lat}"),
        ("b_tot_flux", isinstance(man.get("total_flux_gbps"), (int, float)) and abs(float(man["total_flux_gbps"]) - true_tot_flux) <= 0.4, 0.05, f"total_flux_gbps != {true_tot_flux}"),
        ("b_all8_png_files", sum(1 for i in range(1, 9) if (ws_b / "frames" / f"scene_{i}.png").is_file()) == 8, 0.02, "Fewer than 8 scene PNG files"),
    ])

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=None,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=1.0,
    )


def _activate_and_geom(url_sub: str, x: int, y: int, w: int, h: int, fs: bool) -> str:
    tabs = cdp_list_targets(CDP_PORT)
    tgt = next(t for t in tabs if url_sub in str(t.get("url", "")))
    urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/activate/{tgt['id']}", timeout=5).read()
    fs_sh = 'wmctrl -i -r "$wid" -b add,maximized_vert,maximized_horz,fullscreen 2>/dev/null || true;' if fs else ""
    sh = (
        "export DISPLAY=:99; "
        "wid=$(wmctrl -lx | grep -i chromium | tail -n 1 | awk '{print $1}'); "
        "if [ -n \"$wid\" ]; then "
        "  wmctrl -i -r \"$wid\" -b remove,fullscreen,maximized_vert,maximized_horz 2>/dev/null || true; "
        f"  wmctrl -i -r \"$wid\" -e 0,{x},{y},{w},{h} 2>/dev/null || true; "
        "  wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.2; "
        f"  {fs_sh} "
        "fi"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", sh], check=True, capture_output=True, timeout=10)
    time.sleep(0.35)
    return str(tgt["webSocketDebuggerUrl"])


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    from PIL import Image

    assert role in ("finops_viewport_auditor", "orbit_reel_director")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "finops_viewport_auditor":
            (ws / "captures").mkdir(parents=True, exist_ok=True)
            for fn, vw, vh, _rgb in BREAKPOINT_SPECS:
                _activate_and_geom(f":{port}", 20, 10, vw, min(1050, vh + 85), fs=False)
                out_p = ws / "captures" / fn
                subprocess.run(
                    ["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 import -window root -crop {vw}x{vh}+20+92 +repage {out_p}"],
                    check=True, capture_output=True, timeout=10,
                )
            write_json(ws / "FINOPS_QA.json", FINOPS_ORACLE)
        else:
            (ws / "frames").mkdir(parents=True, exist_ok=True)
            ws_url = _activate_and_geom(f":{ORBIT_PORT}", 0, 0, 1920, 1080, fs=True)
            pil_frames: list[Any] = []
            codes_out: list[str] = []
            for idx in range(1, 9):
                cdp_eval_js(ws_url, f"setSc({idx - 1}); runSweep().then(()=>document.getElementById('scCode').textContent);")
                time.sleep(0.15)
                fp = ws / "frames" / f"scene_{idx}.png"
                subprocess.run(
                    ["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 import -window root {fp}"],
                    check=True, capture_output=True, timeout=10,
                )
                pil_frames.append(Image.open(fp).convert("RGB").resize((960, 540)))
                codes_out.append(ORBIT_SCENES[idx - 1][6])
            pil_frames[0].save(ws / "orbit_walkthrough.gif", save_all=True, append_images=pil_frames[1:], duration=350, loop=0)
            write_json(
                ws / "ORBIT_MANIFEST.json",
                {
                    "scene_codes": codes_out,
                    "mean_latency_ms": round(sum(s[4] for s in ORBIT_SCENES) / 8.0, 2),
                    "total_flux_gbps": round(sum(s[5] for s in ORBIT_SCENES), 1),
                },
            )

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_4 + LAW_8): Concurrent 375x812 resize aborts OrbitMesh fullscreen sweep on scenes 6..8."""
    solve_role("finops_viewport_auditor", workspace_map, port, careful_conc=False)
    solve_role("orbit_reel_director", workspace_map, port, careful_conc=False)
    ws_b = workspace_map["orbit_reel_director"]
    for k in (6, 7, 8):
        (ws_b / "frames" / f"scene_{k}.png").unlink(missing_ok=True)
    bad = read_json_safe(ws_b / "ORBIT_MANIFEST.json")
    bad["scene_codes"] = bad["scene_codes"][:5] + ["SWEEP_ABORTED"] * 3
    write_json(ws_b / "ORBIT_MANIFEST.json", bad)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 5
    write_json(sp, st)

"""Browser-session-only 4-tab visual <canvas> & signoff consoles for QH-01..QH-04.

Runs as UID 0 storing state in /opt/quad_state (0700). Authenticated via a one-time
/boot/<nonce> URL opened by Chromium (UID 1001) on DISPLAY=:99, setting an HttpOnly
cookie inside Chromium's isolated profile. Thus CLI scripts (UID 1000) cannot bypass
the GUI via curl or file reads, while agents freely use CLI for all /workspace files
and desktop GUI tools (screenshot, click, type_text, key) for the live Console.
"""
from __future__ import annotations

import argparse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
import urllib.parse


PORTAL_SPECS = {
    "QH-01": {
        "console_title": "QH-01 Launch Studio Console",
        "tab_names": {"B": "Module 1: 3D Scene", "C": "Module 2: Brand Assets", "D": "Module 3: Pricing", "A": "Module 4: Release QA"},
        "cards": {
            "B": {"role": "MODULE 1 — 3D INDUSTRIAL DESIGN", "line1": "TARGET HEIGHT = 1.50 m", "line2": "CAMERA LENS = 55 mm", "line3": "SHELL RGB = (20, 150, 168)", "swatch": "#1496A8"},
            "C": {"role": "MODULE 2 — BRAND PACKAGING", "line1": "RIBBON RGB = (20, 150, 168)", "line2": "BADGE STROKE = 3.0 px", "line3": "PROMO TAG = LAUNCH-26", "swatch": "#1496A8"},
            "D": {"role": "MODULE 3 — COMMERCIAL PRICING", "line1": "APPROVED MSRP = 240 USD", "line2": "PRODUCT SKU = AX-900", "line3": "MARGIN = MSRP - COST - FEE", "swatch": "#F59E0B"},
            "A": {"role": "MODULE 4 — LAUNCH QA RELEASE", "line1": "PRESS CARD = 640 x 480", "line2": "SAMPLES = 16 (CYCLES)", "line3": "RECORD CURRENT Z & SHA12", "swatch": "#10B981"},
        },
    },
    "QH-02": {
        "console_title": "QH-02 Smart-Grid Emergency Console",
        "tab_names": {"B": "Module 1: Fault GIS", "C": "Module 2: Tie-Line DAG", "D": "Module 3: Tariff Reserve", "A": "Module 4: Dispatch Lock"},
        "cards": {
            "B": {"role": "MODULE 1 — FAULT ISOLATION GIS", "line1": "TRIP 4 FAULTED FEEDERS:", "line2": "F-02, F-06, F-11, F-15", "line3": "status=TRIPPED, mw_flow=0", "swatch": "#EF4444"},
            "C": {"role": "MODULE 2 — TIE-LINE REROUTING", "line1": "TIE CODE = TIE-NORTH-7", "line2": "BONUS = +18.0 MW", "line3": "TARGET = SUB-04", "swatch": "#38BDF8"},
            "D": {"role": "MODULE 3 — TARIFF RESERVE", "line1": "SURGE MULT = 1.35", "line2": "BASE MWH = 400", "line3": "BASE RATE = 80 USD/MWH", "swatch": "#F59E0B"},
            "A": {"role": "MODULE 4 — CHIEF DISPATCHER", "line1": "LAYOUT = Grid_Headroom_Atlas", "line2": "TAG = DEFICIT_SUBS=<int>", "line3": "LOCK QGZ SHA12 & DEFICIT", "swatch": "#10B981"},
        },
    },
    "QH-03": {
        "console_title": "QH-03 Robotics Workcell PLM Console",
        "tab_names": {"B": "Module 1: Base CAD", "C": "Module 2: Mating Mount", "D": "Module 3: Safety Panel", "A": "Module 4: Digital Twin"},
        "cards": {
            "B": {"role": "MODULE 1 — BASE CAD ECO", "line1": "NEW BORE = 58.0 mm", "line2": "NEW BOLT R = 44.0 mm", "line3": "ECO TAG = ECO-5844", "swatch": "#38BDF8"},
            "C": {"role": "MODULE 2 — MATING MOUNT CAD", "line1": "CLEARANCE = 0.40 mm", "line2": "SENSOR Z = 72.0 mm", "line3": "READ BORE/BOLT FROM FCSTD", "swatch": "#A78BFA"},
            "D": {"role": "MODULE 3 — SAFETY PANEL SVG", "line1": "ACCENT HEX = #0EA5E9", "line2": "FRAME STROKE = 2.5 px", "line3": "BADGE TEXT = SAFE-72", "swatch": "#0EA5E9"},
            "A": {"role": "MODULE 4 — DIGITAL TWIN QA", "line1": "TWIN RES = 640 x 360", "line2": "SCALE = mm / 100.0 (m)", "line3": "RECORD CURRENT BORE & SHA12", "swatch": "#10B981"},
        },
    },
    "QH-04": {
        "console_title": "QH-04 Master Control Room (MCR) Console",
        "tab_names": {"B": "Module 1: Conform NLE", "C": "Module 2: Lower-3rd GFX", "D": "Module 3: Audio & Cue", "A": "Module 4: On-Air Master"},
        "cards": {
            "B": {"role": "MODULE 1 — SEG-2 CONFORM", "line1": "SEG-2 = 96 FRAMES (4.0s)", "line2": "COLOR = #D4AF37 GOLD", "line3": "NEW TOTAL = 192 FRAMES", "swatch": "#D4AF37"},
            "C": {"role": "MODULE 2 — GIMP LOWER-THIRD", "line1": "BAR RGB = (16, 185, 129)", "line2": "RECT = (60, 300, 520, 44)", "line3": "TAG = GFX-10B981", "swatch": "#10B981"},
            "D": {"role": "MODULE 3 — AUDIO & CUE SHEET", "line1": "TARGET = -23.0 LUFS", "line2": "DURATION = 8.0 SEC", "line3": "SHOW CODE = SHOW-904", "swatch": "#F59E0B"},
            "A": {"role": "MODULE 4 — ON-AIR DIRECTOR", "line1": "RESOLUTION = 640 x 360", "line2": "FPS = 24 (yuv420p)", "line3": "LOCK MLT SHA12 & FRAMES", "swatch": "#EF4444"},
        },
    },
}


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def build_portal_html(task_id: str) -> str:
    spec = PORTAL_SPECS[task_id]
    tn = spec["tab_names"]
    spec_json = json.dumps(spec, ensure_ascii=False)
    return f'''<!doctype html>
<html><head><meta charset="utf-8"/><title>{spec["console_title"]}</title>
<style>
* {{ box-sizing: border-box; font-family: DejaVu Sans, Liberation Sans, sans-serif; }}
body {{ margin: 0; padding: 12px 18px; background: #0b1120; color: #f1f5f9; overflow: hidden; user-select: none; }}
.hdr {{ display: flex; justify-content: space-between; align-items: center; height: 42px; margin-bottom: 8px; }}
.hdr h1 {{ font-size: 20px; margin: 0; color: #38bdf8; }}
.status-pill {{ background: #1e293b; border: 1px solid #334155; padding: 5px 12px; border-radius: 6px; font-size: 13px; color: #fbbf24; }}
.tabs {{ display: flex; gap: 10px; height: 44px; margin-bottom: 10px; }}
.tab-btn {{ flex: 1; background: #1e293b; color: #cbd5e1; border: 2px solid #334155; border-radius: 8px; font-size: 15px; font-weight: 700; cursor: pointer; }}
.tab-btn.active {{ background: #2563eb; color: #ffffff; border-color: #60a5fa; }}
.pane {{ display: none; background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 16px; height: 520px; }}
.pane.active {{ display: flex; gap: 20px; align-items: stretch; }}
.left-cv {{ width: 570px; flex-shrink: 0; }}
.right-fm {{ flex: 1; display: flex; flex-direction: column; justify-content: flex-start; }}
.form-row {{ display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }}
.form-row label {{ font-size: 14px; font-weight: 700; color: #93c5fd; }}
.form-row input {{ width: 100%; height: 40px; padding: 6px 12px; font-size: 16px; background: #020617; color: #f8fafc; border: 2px solid #475569; border-radius: 6px; }}
.act-btn {{ height: 42px; padding: 0 24px; font-size: 15px; font-weight: 700; background: #059669; color: #fff; border: none; border-radius: 8px; cursor: pointer; }}
.state-box {{ margin-top: 14px; padding: 10px 14px; background: #020617; border: 1px solid #1e293b; border-radius: 8px; font-family: monospace; font-size: 13px; color: #a7f3d0; white-space: pre-wrap; height: 145px; overflow: hidden; }}
</style></head><body>
<div class="hdr">
  <h1>{spec["console_title"]}</h1>
  <div class="status-pill" id="top_status">Workstation Single-Preview Console</div>
</div>
<div class="tabs">
  <button class="tab-btn" id="btn_tabB" onclick="switchRoleTab('B')">{tn['B']}</button>
  <button class="tab-btn" id="btn_tabC" onclick="switchRoleTab('C')">{tn['C']}</button>
  <button class="tab-btn" id="btn_tabD" onclick="switchRoleTab('D')">{tn['D']}</button>
  <button class="tab-btn" id="btn_tabA" onclick="switchRoleTab('A')">{tn['A']}</button>
</div>

<div class="pane active" id="pane0" style="align-items:center;justify-content:center;flex-direction:column">
  <h2 style="color:#60a5fa;margin:0 0 12px">Select Module Tab Above to Open Visual Spec &amp; Stage Buffer</h2>
  <p style="color:#94a3b8;font-size:16px">Note: This workstation has ONE shared 8-second live preview buffer. Switching tabs during an uncommitted preview aborts it.</p>
</div>

<div class="pane" id="paneB">
  <div class="left-cv"><canvas id="cv_B" width="560" height="470"></canvas></div>
  <div class="right-fm">
    <h3 style="margin:0 0 12px;color:#38bdf8">{tn['B']} — Preview &amp; Commit</h3>
    <div class="form-row"><label>Primary Tag / Metric:</label><input id="in_b_val" onfocus="this.select()" placeholder="Enter metric or code"/></div>
    <div style="display:flex;gap:10px"><button class="act-btn" style="background:#2563eb;flex:1" onclick="stageRole('B', document.getElementById('in_b_val').value)">[1] Stage Preview (8s)</button><button class="act-btn" style="flex:1" onclick="commitRole('B')">[2] Commit Verified</button></div>
    <div class="state-box" id="box_B">Status: idle.</div>
  </div>
</div>

<div class="pane" id="paneC">
  <div class="left-cv"><canvas id="cv_C" width="560" height="470"></canvas></div>
  <div class="right-fm">
    <h3 style="margin:0 0 12px;color:#38bdf8">{tn['C']} — Preview &amp; Commit</h3>
    <div class="form-row"><label>Primary Tag / Metric:</label><input id="in_c_val" onfocus="this.select()" placeholder="Enter tag or metric"/></div>
    <div style="display:flex;gap:10px"><button class="act-btn" style="background:#2563eb;flex:1" onclick="stageRole('C', document.getElementById('in_c_val').value)">[1] Stage Preview (8s)</button><button class="act-btn" style="flex:1" onclick="commitRole('C')">[2] Commit Verified</button></div>
    <div class="state-box" id="box_C">Status: idle.</div>
  </div>
</div>

<div class="pane" id="paneD">
  <div class="left-cv"><canvas id="cv_D" width="560" height="470"></canvas></div>
  <div class="right-fm">
    <h3 style="margin:0 0 12px;color:#fbbf24">{tn['D']} — Preview &amp; Commit</h3>
    <div class="form-row"><label>Code / Tag:</label><input id="in_d_code" onfocus="this.select()" placeholder="Enter code / tag"/></div>
    <div class="form-row"><label>Computed Value:</label><input id="in_d_num" onfocus="this.select()" placeholder="Enter computed numeric value"/></div>
    <div style="display:flex;gap:10px"><button class="act-btn" style="background:#2563eb;flex:1" onclick="stageRole('D', document.getElementById('in_d_code').value + '|' + document.getElementById('in_d_num').value)">[1] Stage Preview (8s)</button><button class="act-btn" style="background:#d97706;flex:1" onclick="commitRole('D')">[2] Commit Verified</button></div>
    <div class="state-box" id="box_D">Status: idle.</div>
  </div>
</div>

<div class="pane" id="paneA">
  <div class="left-cv"><canvas id="cv_A" width="560" height="470"></canvas></div>
  <div class="right-fm">
    <h3 style="margin:0 0 12px;color:#34d399">{tn['A']} — Preview &amp; Lock</h3>
    <div class="form-row"><label>Canonical SHA256 (first 12 hex):</label><input id="in_a_sha" onfocus="this.select()" placeholder="12 hex chars"/></div>
    <div class="form-row"><label>Final Summary Metric:</label><input id="in_a_metric" onfocus="this.select()" placeholder="Verified metric"/></div>
    <div style="display:flex;gap:10px"><button class="act-btn" style="background:#2563eb;flex:1" onclick="stageRole('A', document.getElementById('in_a_sha').value + '|' + document.getElementById('in_a_metric').value)">[1] Stage Preview (8s)</button><button class="act-btn" style="flex:1" onclick="commitRole('A')">[2] Commit Verified</button></div>
    <div class="state-box" id="box_A">Status: idle.</div>
  </div>
</div>

<script>
const SPEC = {spec_json};
function drawRoleCanvas(r) {{
  const cv = document.getElementById('cv_' + r);
  const ctx = cv.getContext('2d');
  const card = SPEC.cards[r];
  ctx.fillStyle = '#090f1d';
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.strokeStyle = card.swatch;
  ctx.lineWidth = 4;
  ctx.strokeRect(10, 10, 540, 450);
  ctx.fillStyle = card.swatch;
  ctx.fillRect(380, 28, 145, 44);
  ctx.fillStyle = '#38bdf8';
  ctx.font = 'bold 21px DejaVu Sans, sans-serif';
  ctx.fillText(card.role, 28, 56);
  ctx.fillStyle = '#94a3b8';
  ctx.font = 'bold 15px DejaVu Sans, sans-serif';
  ctx.fillText('VISUAL SPECIFICATION CARD (HTML5 Canvas)', 28, 96);
  ctx.fillStyle = '#f8fafc';
  ctx.font = 'bold 27px DejaVu Sans Mono, monospace';
  ctx.fillText(card.line1, 28, 175);
  ctx.fillStyle = '#fde047';
  ctx.fillText(card.line2, 28, 250);
  ctx.fillStyle = '#a7f3d0';
  ctx.font = 'bold 23px DejaVu Sans Mono, monospace';
  ctx.fillText(card.line3, 28, 325);
}}
['B','C','D','A'].forEach(drawRoleCanvas);

async function switchRoleTab(r) {{
  document.getElementById('pane0').classList.remove('active');
  ['B','C','D','A'].forEach(k => {{
    document.getElementById('pane' + k).classList.toggle('active', k === r);
    document.getElementById('btn_tab' + k).classList.toggle('active', k === r);
  }});
  document.getElementById('top_status').textContent = 'Shared Workstation · Active Tab: TAB ' + r;
  await fetch('/ui/tab', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{tab: r}})}});
}}

async function stageRole(role, val) {{
  await fetch('/ui/stage', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{role: role, value: val}})}});
  await refreshState();
}}
async function commitRole(role) {{
  await fetch('/ui/submit', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{role: role}})}});
  await refreshState();
}}

async function refreshState() {{
  try {{
    const r = await fetch('/ui/state');
    if (!r.ok) return;
    const st = await r.json();
    ['B','C','D','A'].forEach(k => {{
      const mine = (st.submissions && st.submissions[k]) ? st.submissions[k] : null;
      let pv = 'none';
      if (st.preview && st.preview.role === k) {{
        const rem = Math.max(0, st.preview_remaining_s || 0).toFixed(1);
        pv = rem > 0 ? ('VERIFYING (' + rem + 's left) val=' + st.preview.value) : ('READY_TO_COMMIT val=' + st.preview.value);
      }} else if (st.preview) {{
        pv = 'BUSY (occupied by another module)';
      }}
      document.getElementById('box_' + k).textContent = 'Preview Buffer: ' + pv + (st.buffer_tainted ? ' [TAINTED]' : '') + String.fromCharCode(10) + 'Committed: ' + (mine ? JSON.stringify(mine) : 'none');
    }});
  }} catch (e) {{}}
}}
setInterval(refreshState, 900);
refreshState();
</script></body></html>'''


def run_quad_portal(task_id: str, port: int, state_dir: Path, boot_file: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    boot_nonce = secrets.token_urlsafe(24)
    session_cookie_val = secrets.token_hex(24)
    boot_consumed = {"used": False}
    state_file = state_dir / "portal_state.json"
    state = {
        "task_id": task_id,
        "active_tab": "0",
        "tab_switches": 0,
        "preview": None,
        "preview_aborts": 0,
        "buffer_tainted": False,
        "submissions": {},
        "submission_log": [],
        "clobber_count": 0,
        "unauthorized_cli_attempts": 0,
    }
    atomic_write_json(state_file, state)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/boot/{boot_nonce}\n", encoding="utf-8")
    html_doc = build_portal_html(task_id)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_unused):
            return

        def _authed(self) -> bool:
            raw_c = self.headers.get("Cookie", "")
            if not raw_c:
                return False
            jar = cookies.SimpleCookie()
            jar.load(raw_c)
            return "quad_ui_session" in jar and jar["quad_ui_session"].value == session_cookie_val

        def _reply_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/health":
                self._reply_json(200, {"ready": True, "task_id": task_id})
                return
            if parsed.path == f"/boot/{boot_nonce}":
                with lock:
                    if boot_consumed["used"]:
                        self._reply_json(403, {"error": "boot nonce already consumed"})
                        return
                    boot_consumed["used"] = True
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"quad_ui_session={session_cookie_val}; HttpOnly; Path=/; SameSite=Strict")
                self.end_headers()
                return
            if not self._authed():
                with lock:
                    state["unauthorized_cli_attempts"] += 1
                    atomic_write_json(state_file, state)
                self._reply_json(401, {"error": "Session lives inside the authenticated Chromium browser window open on DISPLAY=:99. Use desktop GUI tools (screenshot, click, type_text, key) to view the Visual Spec Canvas and submit signoffs."})
                return
            if parsed.path == "/ui/state":
                with lock:
                    out_st = dict(state)
                    if state["preview"]:
                        out_st["preview_remaining_s"] = round(max(0.0, 8.0 - (time.time() - state["preview"]["staged_at"])), 2)
                    self._reply_json(200, out_st)
                return
            raw = html_doc.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if not self._authed():
                with lock:
                    state["unauthorized_cli_attempts"] += 1
                    atomic_write_json(state_file, state)
                self._reply_json(401, {"error": "Use the authenticated Chromium GUI window on DISPLAY=:99."})
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8", errors="replace") or "{}")
            parsed = urllib.parse.urlparse(self.path)
            now = time.time()
            if parsed.path == "/ui/tab":
                with lock:
                    new_tab = str(body.get("tab", "0"))
                    if state["active_tab"] != new_tab:
                        if state["preview"] and state["preview"]["role"] != new_tab:
                            state["preview"] = None
                            state["preview_aborts"] += 1
                            if state["preview_aborts"] >= 2:
                                state["buffer_tainted"] = True
                        state["active_tab"] = new_tab
                        state["tab_switches"] += 1
                        atomic_write_json(state_file, state)
                self._reply_json(200, {"ok": True, "active_tab": state["active_tab"]})
                return
            if parsed.path == "/ui/stage":
                role = str(body.get("role", "")).upper()
                val = str(body.get("value", "")).strip()
                with lock:
                    if state["preview"] and state["preview"]["role"] != role:
                        state["preview_aborts"] += 1
                        if state["preview_aborts"] >= 2:
                            state["buffer_tainted"] = True
                    state["preview"] = {"role": role, "value": val, "staged_at": now}
                    atomic_write_json(state_file, state)
                self._reply_json(200, {"ok": True, "staged": state["preview"]})
                return
            if parsed.path == "/ui/submit":
                role = str(body.get("role", "")).upper()
                with lock:
                    pv = state["preview"]
                    if not pv or pv["role"] != role or (now - pv["staged_at"]) < 7.8:
                        self._reply_json(409, {"ok": False, "error": "Must Stage Preview and wait 8s undisturbed before Commit"})
                        return
                    val = pv["value"]
                    state["preview"] = None
                    if role in state["submissions"] and state["submissions"][role]["value"] != val:
                        state["clobber_count"] += 1
                    rec = {"role": role, "value": val, "tab_at_submit": state["active_tab"], "tainted_at_commit": state["buffer_tainted"], "timestamp": now}
                    state["submissions"][role] = rec
                    state["submission_log"].append(rec)
                    atomic_write_json(state_file, state)
                self._reply_json(200, {"ok": True, "recorded": rec})
                return
            self._reply_json(404, {"ok": False})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    srv.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--boot-file", type=Path, required=True)
    args = parser.parse_args()
    run_quad_portal(args.task, args.port, args.state_dir.resolve(), args.boot_file.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

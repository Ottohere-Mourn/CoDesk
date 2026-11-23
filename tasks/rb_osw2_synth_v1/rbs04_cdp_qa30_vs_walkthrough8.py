"""RBS-04: Deep OSW2-P5 Twin — Multi-Viewport/Modal Live Web QA vs. 8-Scene 1920x1080 Walkthrough GIF.

Grounded in OSWorld-V2 Empirical Laws (OSW2-P5 v2/029 + v2/045 under Qwen-CUA + CLI):
  - LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE: One singleton Chromium instance
    (`--remote-debugging-port=9222`) hosts both `:19304` (CloudDesk Event Ticketing) and
    `:19314` (PulseOps 8-Scene Telemetry). Role A must resize across 3 breakpoints (390x844,
    768x1024, 1440x900) and probe 5 modals/drawers for a 16-metric QA audit, while Role B
    requires unobstructed 1920x1080 F11 fullscreen across 8 interactive filter scenes.
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

from tasks.rb_osw2_synth_v1.common import (
    advisory_lock,
    boot_singleton_cdp_chromium,
    build_grade_payload,
    cdp_call,
    cdp_eval_js,
    cdp_list_targets,
    make_opaque_seal,
    read_json_safe,
    write_json,
)

TASK_ID = "RBS-04"
PORTAL_PORT = 19304
PULSE_PORT = 19314

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Singleton :9222 CDP 3-Viewport/5-Modal Ticketing QA vs. 8-Scene 1920x1080 Fullscreen Walkthrough",
    "domain": "Multi-Breakpoint Web QA Engineering & Fullscreen Product Telemetry Motion Recording",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE",
        "LAW_1_KEYSTROKE_MISROUTING",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
    ),
    "roles": ("web_qa_auditor", "walkthrough_producer"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (PULSE_PORT,),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "compact_live_qa",
        "total_subchecks": 32,
        "cli_bypass_resistance": 0.95,
        "role_a": {
            "slug": "web_qa_auditor",
            "est_role_seconds": 460.0,
            "traits": [
                "singleton_cdp_browser",
                "viewport_resize_vs_fullscreen_capture",
                "modal_file_or_rule_dialog",
            ],
        },
        "role_b": {
            "slug": "walkthrough_producer",
            "est_role_seconds": 480.0,
            "traits": [
                "singleton_cdp_browser",
                "viewport_resize_vs_fullscreen_capture",
                "overlapping_docks_or_root_screencap",
            ],
        },
    },
}

QA_ORACLE = {
    "mobile_390_overflow_px": 148,
    "mobile_390_cta_height_px": 30,
    "mobile_390_wcag_touch_pass": False,
    "tablet_768_seat_cols": 4,
    "desktop_1440_seat_cols": 8,
    "vip_modal_escape_closes": False,
    "vip_surcharge_usd": 45,
    "promo_case_bug_code": "EARLYBIRD26",
    "promo_discount_pct": 15,
    "eu_vat_rate_pct": 21,
    "cart_3vip_eu_total_usd": 496.10,
    "refund_cutoff_hours": 72,
    "qa_session_seal": make_opaque_seal("rbs04_qa", "CLOUDDESK_3VP_5MODAL"),
}

WALKTHROUGH_SCENES: list[tuple[int, str, str, float]] = [
    (1, "EU_EDGE_INGRESS", "P99_LATENCY", 18.4),
    (2, "US_CORE_ROUTING", "DROP_PPM", 42.0),
    (3, "APAC_KAFKA_LAG", "CONSUMER_SKEW", 310.5),
    (4, "DB_SHARD_LOCKS", "WAIT_MS", 94.2),
    (5, "GPU_KV_CACHE", "EVICT_PCT", 12.8),
    (6, "CDN_TLS_HANDSHAKE", "P95_MS", 27.6),
    (7, "AUTH_TOKEN_SPIKE", "RPS_K", 64.5),
    (8, "GLOBAL_SLO_BURN", "BUDGET_REM_PCT", 83.2),
]

SCENE_SEALS = {
    idx: f"PLS-S{idx}-" + make_opaque_seal("rbs04_pls", f"{idx}:{reg}:{met}")[-6:]
    for idx, reg, met, _val in WALKTHROUGH_SCENES
}


def _build_ticketing_html() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>CloudDesk Event Ticketing</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f8fafc;color:#0f172a;overflow-x:auto;}}
header{{background:#1e1b4b;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;align-items:center;}}
#heroBanner{{width:538px;background:#e0e7ff;padding:10px;border:2px solid #6366f1;box-sizing:border-box;margin:10px 0;}}
#ctaBook{{padding:0 14px;background:#2563eb;color:#fff;border:none;font-weight:700;cursor:pointer;}}
.grid{{display:grid;gap:10px;padding:12px 18px;}}
.card{{background:#fff;border:1px solid #cbd5e1;padding:10px;border-radius:6px;}}
.modal{{display:none;position:fixed;inset:0;background:rgba(15,23,42,0.55);align-items:center;justify-content:center;}}
.modal.open{{display:flex;}}
.mbox{{background:#fff;padding:18px;border-radius:8px;min-width:380px;}}
</style></head><body>
<header><strong>CloudDesk Summit 2026 Ticketing</strong><span id="vpTag" style="font-family:monospace;">VP</span></header>
<main style="padding:10px 18px;">
  <div id="heroBanner">Keynote Pass Allocation — Fixed 538px Banner (Check Horizontal Overflow on 390px Mobile)</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
    <button id="ctaBook" onclick="openCart()">Checkout Selected Passes</button>
    <button onclick="openVip()">VIP Lounge Upgrade Modal</button>
    <button onclick="openRefund()">Refund & SLA Policy Modal</button>
    <input id="promoIn" placeholder="Enter promo code..." />
    <button onclick="applyPromo()">Apply Promo</button>
    <select id="taxRegion" onchange="recalcCart()"><option value="US">US (0% VAT)</option><option value="EU">EU (21% VAT)</option></select>
    <input id="qtyVip" type="number" value="3" min="1" max="10" onchange="recalcCart()" style="width:60px;"/>
  </div>
  <div id="probeReadout" style="font-family:monospace;background:#0f172a;color:#38bdf8;padding:10px;border-radius:6px;">Resize & interact to inspect layout probes</div>
  <div id="seatGrid" class="grid"></div>
</main>
<div id="vipModal" class="modal"><div class="mbox">
  <h3>VIP Upgrade Terms</h3>
  <p>VIP Surcharge: +$45 per ticket over $120 Base Pass ($165 VIP Subtotal/ticket). Promo code <code>EARLYBIRD26</code> (case-sensitive uppercase only!) grants 15% off before EU 21% VAT.</p>
  <p>Note: Escape key handler intentionally unbound (accessibility defect) — must click Close VIP button.</p>
  <button onclick="document.getElementById('vipModal').classList.remove('open')">Close VIP</button>
</div></div>
<div id="refundModal" class="modal"><div class="mbox">
  <h3>Refund Cutoff & QA Session Seal</h3>
  <p id="refundTxt"></p>
  <button onclick="document.getElementById('refundModal').classList.remove('open')">Close Policy</button>
</div></div>
<script>
let promoOk = false;
async function syncLayout(){{
  const w = window.innerWidth, h = window.innerHeight;
  const cta = document.getElementById('ctaBook');
  cta.style.height = (w <= 480 ? '30px' : '44px');
  const cols = (w < 600 ? 2 : (w < 1100 ? 4 : 8));
  const sg = document.getElementById('seatGrid');
  sg.style.gridTemplateColumns = 'repeat('+cols+', 1fr)';
  if(!sg.children.length){{
    for(let i=1;i<=16;i++){{const d=document.createElement('div');d.className='card';d.textContent='Seat S-'+i;sg.appendChild(d);}}
  }}
  const ov = Math.max(0, 538 - w);
  document.getElementById('vpTag').textContent = w+'x'+h+' | cols='+cols+' | overflow='+ov+'px | ctaH='+cta.offsetHeight+'px';
  try{{await fetch('/api/qa/vp',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{w,h}})}});}}catch(_e){{}}
  recalcCart();
}}
function applyPromo(){{
  const v = document.getElementById('promoIn').value;
  promoOk = (v === 'EARLYBIRD26');
  recalcCart();
}}
function recalcCart(){{
  const q = parseInt(document.getElementById('qtyVip').value || '3', 10);
  const reg = document.getElementById('taxRegion').value;
  let sub = q * (120 + 45);
  if(promoOk) sub = sub * 0.85;
  const tot = (reg === 'EU' ? sub * 1.21 : sub);
  document.getElementById('probeReadout').textContent =
    'qty='+q+' VIP($165) | promoApplied='+promoOk+' | region='+reg+' | totalUSD='+tot.toFixed(2);
}}
function openCart(){{recalcCart();}}
function openVip(){{document.getElementById('vipModal').classList.add('open');}}
async function openRefund(){{
  document.getElementById('refundModal').classList.add('open');
  const r = await fetch('/api/qa/refund');
  const d = await r.json();
  document.getElementById('refundTxt').textContent = 'Refund Cutoff: ' + d.cutoff_hours + ' hours prior | QA_SESSION_SEAL=' + d.seal;
}}
window.addEventListener('resize', syncLayout);
window.addEventListener('keydown', (e)=>{{
  if(e.key==='Escape') document.getElementById('refundModal').classList.remove('open');
}});
syncLayout();
</script></body></html>"""


def _build_pulseops_html() -> str:
    scenes_js = json.dumps([
        {"idx": i, "region": r, "metric": m}
        for i, r, m, _v in WALKTHROUGH_SCENES
    ])
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>PulseOps Telemetry Reel</title>
<style>
html,body{{margin:0;padding:0;width:100%;height:100%;background:#090d16;color:#f8fafc;overflow:hidden;font-family:system-ui,sans-serif;}}
#topStatus{{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;font-family:monospace;font-size:15px;}}
#ctrlRow{{height:48px;background:#111827;display:flex;align-items:center;gap:10px;padding:0 24px;}}
button,select{{padding:6px 10px;font-weight:600;cursor:pointer;}}
</style></head><body>
<div id="topStatus">Initializing...</div>
<div id="ctrlRow">
  <button onclick="setScene(-1)">Prev Scene</button>
  <button onclick="setScene(1)">Next Scene</button>
  <select id="selRegion" onchange="draw()"></select>
  <select id="selMetric" onchange="draw()"></select>
  <button id="pauseBtn" onclick="paused=!paused;draw()">Toggle Play/Pause</button>
</div>
<canvas id="cv" width="1920" height="978"></canvas>
<script>
const SC = {scenes_js};
let cur = 0;
let paused = false;
const sr = document.getElementById('selRegion');
const sm = document.getElementById('selMetric');
SC.forEach(s=>{{
  const o1=document.createElement('option');o1.value=s.region;o1.textContent=s.region;sr.appendChild(o1);
  const o2=document.createElement('option');o2.value=s.metric;o2.textContent=s.metric;sm.appendChild(o2);
}});
function setScene(d){{cur=(cur+d+SC.length)%SC.length;draw();}}
async function jumpScene(idx0, reg, met){{cur=idx0;sr.value=reg;sm.value=met;paused=false;await draw();}}
async function draw(){{
  const s = SC[cur];
  const w = window.innerWidth, h = window.innerHeight;
  const q = `/api/pls/frame?idx=${{s.idx}}&reg=${{encodeURIComponent(sr.value)}}&met=${{encodeURIComponent(sm.value)}}&w=${{w}}&h=${{h}}&paused=${{paused?1:0}}`;
  let d = {{liveOk:false, val:'LOCKED', seal:'NEED_FULLSCREEN_1920x1080_AND_MATCHING_FILTER'}};
  try{{const r = await fetch(q); d = await r.json();}}catch(_e){{}}
  const liveOk = Boolean(d.liveOk);
  const bar = document.getElementById('topStatus');
  bar.style.background = liveOk ? '#065f46' : '#991b1b';
  bar.textContent = liveOk
    ? ('FULLSCREEN_LIVE_OK | SCENE ' + s.idx + '/8 [' + s.region + '/' + s.metric + '] | VAL=' + d.val + ' | SEAL=' + d.seal)
    : ('NOT_READY (w=' + w + 'x' + h + ', need >=1880x1000 F11, filter=' + s.region + '+' + s.metric + ', paused=' + paused + ')');
  const ctx = document.getElementById('cv').getContext('2d');
  ctx.fillStyle = liveOk ? '#0f172a' : '#29151b';
  ctx.fillRect(0, 0, 1920, 978);
  const hues = ['#06b6d4','#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981','#6366f1','#14b8a6'];
  ctx.fillStyle = hues[cur];
  ctx.fillRect(90, 90, 260 + cur * 140, 420);
  ctx.fillStyle = '#f8fafc';
  ctx.font = 'bold 38px monospace';
  ctx.fillText('SCENE ' + s.idx + ': ' + s.region + ' / ' + s.metric, 90, 600);
  if(liveOk){{
    ctx.fillStyle = '#34d399';
    ctx.fillText('METRIC=' + d.val + ' | ' + d.seal, 90, 670);
  }}
}}
window.addEventListener('resize', draw);
sr.value = SC[0].region; sm.value = SC[0].metric;
draw();
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Multi-Viewport & Modal Ticketing Web QA Work Order — {b}web_qa_auditor{b}",
        "",
        "## Scope & Deliverables",
        f"Audit **CloudDesk Event Ticketing** at {b}http://127.0.0.1:{PORTAL_PORT}/{b} in the live Chromium browser (remote debugging active on {b}127.0.0.1:9222{b}) across three responsive viewports (`390x844`, `768x1024`, `1440x900`) and all interactive modals/calculators.",
        "",
        "Deliverables:",
        f"1. **Structured QA Audit JSON ({b}/workspace/QA_AUDIT_30.json{b})** with exact keys:",
        f"   - {b}\"mobile_390_overflow_px\"{b} (int: horizontal banner overflow in px at `390px` viewport width)",
        f"   - {b}\"mobile_390_cta_height_px\"{b} (int: rendered height of `#ctaBook` at `390px` width) and {b}\"mobile_390_wcag_touch_pass\"{b} (bool: whether height `>= 44` px)",
        f"   - {b}\"tablet_768_seat_cols\"{b} (int: grid columns at `768px` width) and {b}\"desktop_1440_seat_cols\"{b} (int: grid columns at `1440px` width)",
        f"   - {b}\"vip_modal_escape_closes\"{b} (bool: whether pressing `Escape` closes `#vipModal`) and {b}\"vip_surcharge_usd\"{b} (int)",
        f"   - {b}\"promo_case_bug_code\"{b} (string), {b}\"promo_discount_pct\"{b} (int), {b}\"eu_vat_rate_pct\"{b} (int)",
        f"   - {b}\"cart_3vip_eu_total_usd\"{b} (float: total USD for `3` VIP passes with valid promo applied under `EU` VAT, rounded to 2 decimals)",
        f"   - {b}\"refund_cutoff_hours\"{b} (int) and {b}\"qa_session_seal\"{b} (string `ATTEST-...` revealed in the Refund Policy modal after visiting all 3 viewports)",
        f"2. **Markdown Defect Summary ({b}/workspace/QA_REPORT.md{b})**: Concise report summarizing the mobile overflow/touch-target defect, VIP modal Escape-key defect, and promo case-sensitivity behavior.",
        "",
    ])

    role_b = "\n".join([
        f"# 8-Scene Fullscreen 1920x1080 Telemetry Walkthrough Work Order — {b}walkthrough_producer{b}",
        "",
        "## Scope & Deliverables",
        f"Record an unobstructed `1920x1080` fullscreen 8-scene product walkthrough of **PulseOps Telemetry** at {b}http://127.0.0.1:{PULSE_PORT}/{b} in the live Chromium browser.",
        "",
        "Deliverables:",
        f"1. **8 Unobstructed Fullscreen Scene PNGs ({b}/workspace/frames/scene_1.png{b} .. {b}scene_8.png{b})**:",
        "   - Place Chromium into unobstructed `1920x1080` fullscreen (`F11` / `>= 1880x1000` viewport, unpaused) and step through Scenes `1..8`, selecting each scene's matching `Region` and `Metric` dropdown so the top status bar turns green (`FULLSCREEN_LIVE_OK`) before capturing each `1920x1080` PNG.",
        f"2. **Animated Walkthrough GIF ({b}/workspace/pulseops_walkthrough.gif{b})**:",
        "   - Assemble all 8 captured scenes in order into an animated GIF (`>= 8` frames, resolution `>= 960x540`).",
        f"3. **Walkthrough Telemetry Manifest ({b}/workspace/WALKTHROUGH_MANIFEST.json{b})** with exact keys:",
        f"   - {b}\"scene_seals\"{b}: list of the 8 `PLS-S1-...` .. `PLS-S8-...` seals in scene order",
        f"   - {b}\"scene_values\"{b}: object mapping `\"1\"..\"8\"` to each scene's numeric `VAL`",
        f"   - {b}\"sum_scene_values\"{b}: float sum of all 8 scene `VAL` numbers (rounded to 1 decimal)",
        "",
    ])
    return {"web_qa_auditor": role_a, "walkthrough_producer": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    for ws in workspace_map.values():
        (ws / "frames").mkdir(parents=True, exist_ok=True)
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
    vp_seen = {"390": False, "768": False, "1440": False}
    lock = threading.Lock()
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})
    qa_bytes = _build_ticketing_html().encode("utf-8")
    pls_bytes = _build_pulseops_html().encode("utf-8")
    sc_lookup = {i: (r, m, v, SCENE_SEALS[i]) for i, r, m, v in WALKTHROUGH_SCENES}

    def _check_cookie(hdrs: Any, cname: str) -> bool:
        c = SimpleCookie()
        try:
            c.load(hdrs.get("Cookie") or "")
            m = c.get(cname)
            return bool(m and m.value == sso_val)
        except Exception:
            return False

    class QaHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302); self.send_header("Set-Cookie", f"rbs04_qa_sso={sso_val}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not _check_cookie(self.headers, "rbs04_qa_sso"):
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: use live Chromium session"); return
            if parsed.path == "/api/qa/refund":
                with lock:
                    all_vp = all(vp_seen.values())
                raw = json.dumps({"cutoff_hours": 72, "seal": QA_ORACLE["qa_session_seal"] if all_vp else "VISIT_ALL_3_VIEWPORTS_FIRST"}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(qa_bytes))); self.end_headers(); self.wfile.write(qa_bytes)

        def do_POST(self) -> None:
            if not _check_cookie(self.headers, "rbs04_qa_sso"):
                self.send_response(401); self.end_headers(); return
            ln = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(ln).decode("utf-8")) if ln > 0 else {}
            w = int(body.get("w") or 0)
            with lock:
                if abs(w - 390) <= 25: vp_seen["390"] = True
                if abs(w - 768) <= 30: vp_seen["768"] = True
                if w >= 1360: vp_seen["1440"] = True
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    class PlsHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302); self.send_header("Set-Cookie", f"rbs04_pls_sso={sso_val}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not _check_cookie(self.headers, "rbs04_pls_sso"):
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: use live Chromium session"); return
            if parsed.path == "/api/pls/frame":
                idx = int((qs.get("idx") or ["1"])[0])
                reg = (qs.get("reg") or [""])[0]
                met = (qs.get("met") or [""])[0]
                w = int((qs.get("w") or ["0"])[0])
                h = int((qs.get("h") or ["0"])[0])
                paused = (qs.get("paused") or ["0"])[0] == "1"
                exp_r, exp_m, val, seal = sc_lookup.get(idx, ("", "", 0.0, ""))
                live_ok = bool(w >= 1860 and h >= 920 and not paused and reg == exp_r and met == exp_m)
                raw = json.dumps({"liveOk": live_ok, "val": val if live_ok else None, "seal": seal if live_ok else "NOT_FULLSCREEN_OR_FILTER"}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(pls_bytes))); self.end_headers(); self.wfile.write(pls_bytes)

    t_pls = threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", PULSE_PORT), PlsHandler).serve_forever, daemon=True)
    t_pls.start()
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(
        json.dumps(
            {
                "urls": [
                    f"http://127.0.0.1:{port}/?sso_boot={boot_tok}",
                    f"http://127.0.0.1:{PULSE_PORT}/?sso_boot={boot_tok}",
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ThreadingHTTPServer(("127.0.0.1", port), QaHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    bf = state_dir / "boot_url"
    cfg = json.loads(bf.read_text(encoding="utf-8"))
    bf.unlink(missing_ok=True)
    boot_singleton_cdp_chromium(list(cfg["urls"]))


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image

    ws_a = workspace_map["web_qa_auditor"]
    ws_b = workspace_map["walkthrough_producer"]

    qa = read_json_safe(ws_a / "QA_AUDIT_30.json")
    md_txt = (ws_a / "QA_REPORT.md").read_text(encoding="utf-8", errors="replace").lower() if (ws_a / "QA_REPORT.md").is_file() else ""

    checks_a: list[tuple[str, bool, float, str]] = [
        ("qa_json_present", bool(qa), 0.05, "Missing /workspace/QA_AUDIT_30.json"),
        ("qa_mob_overflow", isinstance(qa.get("mobile_390_overflow_px"), (int, float)) and abs(float(qa["mobile_390_overflow_px"]) - 148) <= 8, 0.07, "mobile_390_overflow_px != 148"),
        ("qa_mob_cta_h", qa.get("mobile_390_cta_height_px") == 30, 0.06, "mobile_390_cta_height_px != 30"),
        ("qa_mob_wcag", qa.get("mobile_390_wcag_touch_pass") is False, 0.06, "mobile_390_wcag_touch_pass != false"),
        ("qa_tab_cols", qa.get("tablet_768_seat_cols") == 4, 0.06, "tablet_768_seat_cols != 4"),
        ("qa_desk_cols", qa.get("desktop_1440_seat_cols") == 8, 0.06, "desktop_1440_seat_cols != 8"),
        ("qa_vip_esc", qa.get("vip_modal_escape_closes") is False, 0.07, "vip_modal_escape_closes != false"),
        ("qa_vip_surcharge", qa.get("vip_surcharge_usd") == 45, 0.05, "vip_surcharge_usd != 45"),
        ("qa_promo_code", qa.get("promo_case_bug_code") == "EARLYBIRD26", 0.06, "promo_case_bug_code != 'EARLYBIRD26'"),
        ("qa_promo_pct", qa.get("promo_discount_pct") == 15, 0.05, "promo_discount_pct != 15"),
        ("qa_eu_vat", qa.get("eu_vat_rate_pct") == 21, 0.05, "eu_vat_rate_pct != 21"),
        ("qa_cart_total", isinstance(qa.get("cart_3vip_eu_total_usd"), (int, float)) and abs(float(qa["cart_3vip_eu_total_usd"]) - 496.10) <= 0.15, 0.09, "cart_3vip_eu_total_usd != 496.10"),
        ("qa_refund_hrs", qa.get("refund_cutoff_hours") == 72, 0.05, "refund_cutoff_hours != 72"),
        ("qa_session_seal", qa.get("qa_session_seal") == QA_ORACLE["qa_session_seal"], 0.10, "qa_session_seal invalid (must visit 390/768/1440 & open Refund modal)"),
        ("qa_md_exists", len(md_txt) >= 120, 0.06, "QA_REPORT.md missing or too short"),
        ("qa_md_defects", all(w in md_txt for w in ("overflow", "escape", "earlybird26")), 0.06, "QA_REPORT.md missing key defect findings"),
    ]

    mf = read_json_safe(ws_b / "WALKTHROUGH_MANIFEST.json")
    clean_frames = 0
    for idx in range(1, 9):
        fp = ws_b / f"frames/scene_{idx}.png"
        if fp.is_file() and fp.stat().st_size > 3000:
            try:
                with Image.open(fp) as im:
                    rgb = im.convert("RGB")
                    if rgb.size == (1920, 1080):
                        # Check green FULLSCREEN_LIVE_OK top bar (#065f46 -> R<35, G in 75..125, B in 50..95)
                        green_ok = False
                        for sy in range(6, 130, 6):
                            r, g, b_c = rgb.getpixel((960, sy))
                            if r < 40 and 70 <= g <= 130 and 45 <= b_c <= 100:
                                green_ok = True
                                break
                        if green_ok:
                            clean_frames += 1
            except Exception:
                pass

    gif_p = ws_b / "pulseops_walkthrough.gif"
    gif_ok = False
    if gif_p.is_file() and gif_p.stat().st_size > 4000:
        try:
            with Image.open(gif_p) as gim:
                gif_ok = getattr(gim, "n_frames", 1) >= 8 and gim.size[0] >= 960 and gim.size[1] >= 540
        except Exception:
            gif_ok = False

    exp_seals = [SCENE_SEALS[i] for i in range(1, 9)]
    got_seals = mf.get("scene_seals") if isinstance(mf.get("scene_seals"), list) else []
    seal_hits = sum(1 for i, s in enumerate(exp_seals) if i < len(got_seals) and got_seals[i] == s)
    got_vals = mf.get("scene_values") if isinstance(mf.get("scene_values"), dict) else {}
    val_hits = sum(1 for i, _r, _m, v in WALKTHROUGH_SCENES if isinstance(got_vals.get(str(i)), (int, float)) and abs(float(got_vals[str(i)]) - v) <= 0.2)
    exp_sum = round(sum(v for _, _, _, v in WALKTHROUGH_SCENES), 1)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("wt_frames_atleast4", clean_frames >= 4, 0.08, f"Only {clean_frames}/8 fullscreen green-status frames"),
        ("wt_frames_atleast6", clean_frames >= 6, 0.08, f"Only {clean_frames}/8 fullscreen green-status frames"),
        ("wt_frames_all8", clean_frames == 8, 0.12, f"scene_1..8.png fullscreen clean {clean_frames}/8 != 8/8"),
        ("wt_scene1_ok", (ws_b / "frames/scene_1.png").is_file(), 0.04, "Missing scene_1.png"),
        ("wt_scene4_ok", (ws_b / "frames/scene_4.png").is_file(), 0.04, "Missing scene_4.png"),
        ("wt_scene8_ok", (ws_b / "frames/scene_8.png").is_file(), 0.04, "Missing scene_8.png"),
        ("wt_gif_8frames", gif_ok, 0.12, "pulseops_walkthrough.gif missing, <8 frames, or <960x540"),
        ("wt_mf_exists", bool(mf), 0.04, "Missing WALKTHROUGH_MANIFEST.json"),
        ("wt_seals_half", seal_hits >= 4, 0.06, f"scene_seals {seal_hits}/8"),
        ("wt_seals_6", seal_hits >= 6, 0.06, f"scene_seals {seal_hits}/8"),
        ("wt_seals_all8", seal_hits == 8, 0.10, f"scene_seals {seal_hits}/8 != 8/8"),
        ("wt_vals_half", val_hits >= 4, 0.05, f"scene_values {val_hits}/8"),
        ("wt_vals_all8", val_hits == 8, 0.07, f"scene_values {val_hits}/8 != 8/8"),
        ("wt_sum_val", isinstance(mf.get("sum_scene_values"), (int, float)) and abs(float(mf["sum_scene_values"]) - exp_sum) <= 0.3, 0.06, f"sum_scene_values != {exp_sum}"),
        ("wt_order_intact", len(got_seals) == 8, 0.02, "scene_seals length != 8"),
        ("wt_vals_keys", len(got_vals) == 8, 0.02, "scene_values keys != 8"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=None,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.88,
    )


def _resize_chr(x: int, y: int, w: int, h: int, fullscreen: bool = False) -> None:
    fs = "wmctrl -i -r \"$wid\" -b add,fullscreen 2>/dev/null || true;" if fullscreen else ""
    sh = (
        "export DISPLAY=:99; "
        "wid=$(wmctrl -lx | grep -i chromium | tail -n 1 | awk '{print $1}'); "
        "if [ -n \"$wid\" ]; then "
        "  wmctrl -i -r \"$wid\" -b remove,fullscreen,maximized_vert,maximized_horz 2>/dev/null || true; "
        f"  wmctrl -i -r \"$wid\" -e 0,{x},{y},{w},{h} 2>/dev/null || true; "
        "  wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.25; "
        f"  {fs} "
        "fi"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", sh], capture_output=True, timeout=10)
    time.sleep(0.45)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    from PIL import Image

    assert role in ("web_qa_auditor", "walkthrough_producer")
    ws = workspace_map[role]

    def _work() -> None:
        targets = cdp_list_targets(9222)
        if role == "web_qa_auditor":
            t_qa = next(t for t in targets if str(port) in t.get("url", ""))
            import urllib.request as ur
            ur.urlopen(f"http://127.0.0.1:9222/json/activate/{t_qa['id']}", timeout=5).read()
            ws_qa = t_qa["webSocketDebuggerUrl"]
            _resize_chr(20, 20, 1440, 920, fullscreen=False)
            for vw, vh in ((390, 844), (768, 1024), (1440, 900)):
                cdp_call(ws_qa, "Emulation.setDeviceMetricsOverride", {"width": vw, "height": vh, "deviceScaleFactor": 1, "mobile": vw < 600})
                time.sleep(0.15)
                cdp_eval_js(ws_qa, "syncLayout();")
            cdp_call(ws_qa, "Emulation.clearDeviceMetricsOverride", {})
            seal = cdp_eval_js(ws_qa, "openRefund().then(()=>document.getElementById('refundTxt').textContent);")
            assert QA_ORACLE["qa_session_seal"] in str(seal)
            write_json(ws / "QA_AUDIT_30.json", QA_ORACLE)
            (ws / "QA_REPORT.md").write_text(
                "# CloudDesk Ticketing QA Report\n\n"
                "- Mobile 390px horizontal overflow (148px) on fixed 538px hero banner and 30px CTA button (<44px WCAG touch target).\n"
                "- VIP modal Escape key handler fails to close modal (`vip_modal_escape_closes = false`).\n"
                "- Promo code `EARLYBIRD26` is strictly case-sensitive uppercase before 21% EU VAT.\n",
                encoding="utf-8",
            )
        else:
            t_pls = next(t for t in targets if str(PULSE_PORT) in t.get("url", ""))
            import urllib.request as ur
            ur.urlopen(f"http://127.0.0.1:9222/json/activate/{t_pls['id']}", timeout=5).read()
            _resize_chr(0, 0, 1920, 1080, fullscreen=True)
            ws_url = t_pls["webSocketDebuggerUrl"]
            fdir = ws / "frames"
            fdir.mkdir(parents=True, exist_ok=True)
            imgs = []
            for idx, reg, met, _val in WALKTHROUGH_SCENES:
                cdp_eval_js(ws_url, f"jumpScene({idx - 1}, {json.dumps(reg)}, {json.dumps(met)});")
                time.sleep(0.22)
                fp = fdir / f"scene_{idx}.png"
                subprocess.run(["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 import -window root {fp}"], check=True, capture_output=True, timeout=10)
                imgs.append(Image.open(fp).convert("RGB").resize((960, 540)))
            imgs[0].save(ws / "pulseops_walkthrough.gif", save_all=True, append_images=imgs[1:], duration=300, loop=0)
            write_json(
                ws / "WALKTHROUGH_MANIFEST.json",
                {
                    "scene_seals": [SCENE_SEALS[i] for i, _, _, _ in WALKTHROUGH_SCENES],
                    "scene_values": {str(i): v for i, _, _, v in WALKTHROUGH_SCENES},
                    "sum_scene_values": round(sum(v for _, _, _, v in WALKTHROUGH_SCENES), 1),
                },
            )
            cdp_call(ws_url, "Page.bringToFront")

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_4 Singleton CDP Collision): Role A resizes Chromium to 390px mid-walkthrough, spoiling scenes 6..8."""
    solve_role("web_qa_auditor", workspace_map, port, careful_conc=False)
    solve_role("walkthrough_producer", workspace_map, port, careful_conc=False)
    ws_b = workspace_map["walkthrough_producer"]
    _resize_chr(30, 30, 390, 844, fullscreen=False)
    for idx in (6, 7, 8):
        subprocess.run(
            ["su", "-s", "/bin/bash", "user", "-c", f"DISPLAY=:99 import -window root {ws_b}/frames/scene_{idx}.png"],
            check=True,
            capture_output=True,
            timeout=10,
        )
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

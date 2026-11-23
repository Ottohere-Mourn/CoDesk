"""RBS2-03: GeoCurve 5-Knot Silhouette Fitting vs. Live :9222 Visual Blog Theme Reverse-Engineering.

Grounded in OSWorld-V2 (OSW2-P15 GeoGebra Vase Curve Fitting + Local Blog Theme Recreation):
  - LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI: GeoCurve renders its 5-knot target amphora silhouette
    purely via QPainter (zero coordinates in AT-SPI text; must drag 5 knots K0..K4 onto the curve).
  - LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB + LAW_4: Overlapping GeoCurve CAD window and
    singleton `:9222` HttpOnly Chromium (hosting the live reference blog & candidate preview).
"""
from __future__ import annotations

import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.rb_osw2_synth_v2.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    boot_singleton_cdp_chromium,
    build_grade_payload,
    cdp_eval_js,
    cdp_list_targets,
    make_opaque_seal,
    read_json_safe,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS2-03"
PORTAL_PORT = 19403

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "GeoCurve 5-Knot Rotational Silhouette Fitting vs. :9222 Editorial Blog Theme Recreation",
    "domain": "Parametric Curve-of-Revolution CAD Fitting & Responsive Frontend Theme Reverse-Engineering",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB",
        "LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE",
    ),
    "roles": ("curve_cad_modeler", "visual_theme_recreator"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1680,
    "iso_role_timeout_s": 1680,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "high_granularity_visual_recreation",
        "total_subchecks": 38,
        "cli_bypass_resistance": 0.97,
        "role_a": {
            "slug": "curve_cad_modeler",
            "est_role_seconds": 520.0,
            "traits": [
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "custom_2d_canvas_drag",
            ],
        },
        "role_b": {
            "slug": "visual_theme_recreator",
            "est_role_seconds": 540.0,
            "traits": [
                "singleton_cdp_browser",
                "overlapping_docks_or_root_screencap",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
            ],
        },
    },
}

GEOCURVE_SALT = "geocurve-amphora-rbs203"
Z_STATIONS_MM = [0.0, 25.0, 50.0, 75.0, 100.0]
TARGET_RADII_MM = [28.0, 44.0, 22.0, 38.0, 18.0]
INIT_RADII_MM = [16.0, 24.0, 45.0, 19.0, 34.0]

BLOG_THEME_ORACLE = {
    "brand_title": "Meridian Systems Journal",
    "header_bg_hex": "#0F172A",
    "accent_hex": "#E11D48",
    "dark_surface_hex": "#111827",
    "desktop_grid_cols": 3,
    "mobile_breakpoint_px": 700,
    "featured_article_count": 6,
    "reading_wpm_basis": 220,
    "theme_spec_seal": make_opaque_seal("rbs203_blog", "MERIDIAN_THEME_V2"),
}


def eval_vessel_fit(radii: list[float]) -> dict[str, Any]:
    rms = math.sqrt(sum((float(radii[i]) - TARGET_RADII_MM[i]) ** 2 for i in range(5)) / 5.0)
    # Simpson's rule over 4 intervals of h=25mm: V_mm3 = pi * (h/3) * (r0^2 + 4*r1^2 + 2*r2^2 + 4*r3^2 + r4^2)
    r2 = [float(r) ** 2 for r in radii]
    vol_mm3 = math.pi * (25.0 / 3.0) * (r2[0] + 4.0 * r2[1] + 2.0 * r2[2] + 4.0 * r2[3] + r2[4])
    vol_cm3 = round(vol_mm3 / 1000.0, 2)
    qualified = bool(rms <= 2.2)
    r_tag = ":".join(f"{float(r):.1f}" for r in radii)
    seal = "GEO-FIT-" + hashlib.sha256(f"{GEOCURVE_SALT}:{r_tag}:{qualified}".encode()).hexdigest()[:10].upper() if qualified else "UNFITTED_SILHOUETTE"
    return {
        "z_stations_mm": Z_STATIONS_MM,
        "fitted_radii_mm": [round(float(r), 2) for r in radii],
        "rms_radial_error_mm": round(rms, 3),
        "simpson_volume_cm3": vol_cm3,
        "qualified": qualified,
        "fit_seal": seal,
    }


GEOCURVE_QT_SOURCE = f"""import hashlib, json, math, os, sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QShortcut
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt, QPointF

SALT = {json.dumps(GEOCURVE_SALT)}
ZS = {json.dumps(Z_STATIONS_MM)}
TGT = {json.dumps(TARGET_RADII_MM)}

def eval_fit(rs):
    rms = math.sqrt(sum((rs[i] - TGT[i])**2 for i in range(5)) / 5.0)
    r2 = [r*r for r in rs]
    v_cm3 = round(math.pi * (25.0/3.0) * (r2[0] + 4*r2[1] + 2*r2[2] + 4*r2[3] + r2[4]) / 1000.0, 2)
    ok = (rms <= 2.2)
    r_tag = ":".join(f"{{r:.1f}}" for r in rs)
    seal = "GEO-FIT-" + hashlib.sha256(f"{{SALT}}:{{r_tag}}:{{ok}}".encode()).hexdigest()[:10].upper() if ok else "UNFITTED_SILHOUETTE"
    return {{"z_stations_mm":ZS,"fitted_radii_mm":[round(r,2) for r in rs],"rms_radial_error_mm":round(rms,3),
            "simpson_volume_cm3":v_cm3,"qualified":ok,"fit_seal":seal}}

class RevolveCanvas(QWidget):
    def __init__(self, on_chg):
        super().__init__()
        self.setMinimumSize(780, 450)
        self.rs = {json.dumps(INIT_RADII_MM)}
        self.drag_i = None
        self.on_chg = on_chg

    def z2x(self, z): return 90.0 + z * 6.0
    def r2y(self, r): return 390.0 - r * 6.5
    def y2r(self, sy): return round(max(8.0, min(54.0, (390.0 - sy) / 6.5)), 1)

    def mousePressEvent(self, ev):
        p = ev.pos()
        for i in range(5):
            if math.hypot(p.x() - self.z2x(ZS[i]), p.y() - self.r2y(self.rs[i])) <= 24.0:
                self.drag_i = i
                break

    def mouseMoveEvent(self, ev):
        if self.drag_i is None:
            return
        self.rs[self.drag_i] = self.y2r(ev.pos().y())
        self.on_chg()
        self.update()

    def mouseReleaseEvent(self, _ev):
        self.drag_i = None

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(15, 23, 42))
        # Axis z-line at y=390
        qp.setPen(QPen(QColor(148, 163, 184), 2, Qt.DashDotLine))
        qp.drawLine(50, 390, 730, 390)
        # Green reference amphora silhouette (visual target — no numeric target text!)
        qp.setPen(QPen(QColor(52, 211, 153), 4, Qt.DashLine))
        for i in range(4):
            qp.drawLine(QPointF(self.z2x(ZS[i]), self.r2y(TGT[i])), QPointF(self.z2x(ZS[i+1]), self.r2y(TGT[i+1])))
        qp.setBrush(QBrush(QColor(16, 185, 129)))
        for i in range(5):
            qp.drawEllipse(QPointF(self.z2x(ZS[i]), self.r2y(TGT[i])), 7.0, 7.0)

        # Current orange user curve + draggable handles K0..K4
        qp.setPen(QPen(QColor(249, 115, 22), 3))
        for i in range(4):
            qp.drawLine(QPointF(self.z2x(ZS[i]), self.r2y(self.rs[i])), QPointF(self.z2x(ZS[i+1]), self.r2y(self.rs[i+1])))
        qp.setBrush(QBrush(QColor(249, 115, 22)))
        qp.setPen(QPen(QColor(255, 255, 255), 2))
        qp.setFont(QFont("Monospace", 9, QFont.Bold))
        for i in range(5):
            sx, sy = self.z2x(ZS[i]), self.r2y(self.rs[i])
            qp.drawEllipse(QPointF(sx, sy), 12.0, 12.0)
            qp.drawText(int(sx - 26), int(sy - 16), f"K{{i}}={{self.rs[i]:.1f}}")

class GeoCurveWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoCurve Revolve Studio")
        self.setGeometry(50, 60, 860, 600)
        cw = QWidget(); lay = QVBoxLayout(cw)
        self.g_lbl = QLabel()
        self.g_lbl.setStyleSheet("font-family: monospace; padding: 6px; background: #1e293b; color: #f8fafc;")
        lay.addWidget(self.g_lbl)
        self.cv = RevolveCanvas(self.refresh)
        lay.addWidget(self.cv)
        row = QHBoxLayout()
        b_exp = QPushButton("&Export Fitted Vessel JSON (/home/user/Downloads/vessel_fit.json) [Ctrl+E]")
        b_exp.clicked.connect(self.export_fit)
        row.addWidget(b_exp)
        lay.addLayout(row)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_fit)
        self.refresh()

    def refresh(self):
        st = eval_fit(self.cv.rs)
        self.g_lbl.setText(f"RMS_Radial_Err={{st['rms_radial_error_mm']}} mm (need <=2.2) | SimpsonVol={{st['simpson_volume_cm3']}} cm3 | Qualified={{st['qualified']}}")

    def export_fit(self):
        st = eval_fit(self.cv.rs)
        p = Path("/home/user/Downloads/vessel_fit.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, indent=2) + "\\n")
        os.chmod(p, 0o644)
        self.g_lbl.setText(f"Saved (qualified={{st['qualified']}}, seal={{st['fit_seal']}})")

app = QApplication(sys.argv)
app.setApplicationName("geocurve-revolve")
w = GeoCurveWin()
w.show()
sys.exit(app.exec_())
"""


def _build_blog_ref_html() -> str:
    return """<!doctype html><html><head><meta charset="utf-8"/><title>Meridian Systems Journal — Reference</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#f8fafc;color:#0f172a;}
body.dark{background:#111827;color:#f8fafc;}
header{background:#0F172A;color:#fff;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:4px solid #E11D48;}
.layout{display:grid;grid-template-columns:220px 1fr;gap:20px;padding:20px 24px;}
#tocNav{position:sticky;top:16px;background:#e2e8f0;padding:12px;border-radius:8px;height:fit-content;}
body.dark #tocNav{background:#1f2937;}
#articleGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}
@media (max-width: 700px){#articleGrid{grid-template-columns:1fr;}}
.post-card{border:1px solid #cbd5e1;border-top:4px solid #E11D48;padding:14px;border-radius:8px;background:#fff;}
body.dark .post-card{background:#1f2937;border-color:#374151;border-top-color:#E11D48;}
</style></head><body>
<header>
  <h1>Meridian Systems Journal</h1>
  <div>
    <button id="themeToggle" onclick="document.body.classList.toggle('dark')">Toggle Dark Theme (Ctrl+J)</button>
    <button onclick="loadSpec()">Theme Spec Inspector</button>
  </div>
</header>
<div class="layout">
  <nav id="tocNav"><strong>Topics TOC</strong><ul><li>Kernel I/O</li><li>Consensus</li><li>Compilers</li></ul><div id="specOut" style="font-family:monospace;font-size:12px;margin-top:8px;"></div></nav>
  <section id="articleGrid"></section>
</div>
<script>
const posts = [
  ['Zero-Copy io_uring Pipelines', 880], ['Raft Lease Read Linearizability', 1100], ['eBPF Verifier Abstract Domains', 660],
  ['NUMA-Aware Slab Allocators', 1320], ['WasmGC Tail-Call Trampolines', 440], ['NVMe-oF TCP Pacing', 1540]
];
const g = document.getElementById('articleGrid');
posts.forEach(([t, words], i)=>{
  const mins = Math.ceil(words / 220);
  const c = document.createElement('article');
  c.className = 'post-card';
  c.innerHTML = `<h3>${i+1}. ${t}</h3><p class="read-badge">${mins} min read (${words}w @ 220 WPM)</p>`;
  g.appendChild(c);
});
async function loadSpec(){
  const r = await fetch('/api/theme_spec');
  const d = await r.json();
  document.getElementById('specOut').textContent = 'SEAL=' + d.seal + ' | darkBg=#111827 | bp=700px';
}
window.addEventListener('keydown', e=>{if(e.ctrlKey && e.key.toLowerCase()==='j'){e.preventDefault();document.body.classList.toggle('dark');}});
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Rotational Amphora Curve Fitting & SVG Blueprint Work Order — {b}curve_cad_modeler{b}",
        "",
        "## Scope & Deliverables",
        f"Fit the 5-knot rotational profile (`K0..K4`) onto the green reference amphora silhouette in **GeoCurve Revolve Studio** and generate the certified CAD deliverables in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Signed Silhouette Fit JSON ({b}/workspace/vessel_fit.json{b})**:",
        f"   - Drag the 5 orange handles `K0..K4` onto the green reference markers until `rms_radial_error_mm <= 2.2` (`Qualified=True`), export `/home/user/Downloads/vessel_fit.json` (`Ctrl+E`), and copy it to {b}/workspace/vessel_fit.json{b}.",
        f"2. **Parametric Profile SVG Blueprint ({b}/workspace/vessel_profile.svg{b})**:",
        "   - Generate a valid SVG (`width=\"800\" height=\"500\"`) containing `<polyline>` or `<path>` elements for both the upper (`+r(z)`) and mirrored lower (`-r(z)`) meridian profiles plus `<circle>` markers for all 5 fitted knots `K0..K4` and text showing `simpson_volume_cm3` and `fit_seal`.",
        "",
    ])

    role_b = "\n".join([
        f"# Editorial Blog Theme Reverse-Engineering Work Order — {b}visual_theme_recreator{b}",
        "",
        "## Scope & Deliverables",
        f"Inspect the live reference blog at {b}http://127.0.0.1:{PORTAL_PORT}/{b} in Chromium and recreate the theme as a clean static site under {b}/workspace/blog_site/{b} plus specification manifest.",
        "",
        "Deliverables:",
        f"1. **Recreated Responsive Blog Theme ({b}/workspace/blog_site/index.html{b}, {b}styles.css{b}, {b}app.js{b})**:",
        "   - Match the reference header (`Meridian Systems Journal`, `#0F172A` background, `#E11D48` accent border), sticky `#tocNav`, `#articleGrid` (`3` columns on desktop, `1` column at `@media (max-width: 700px)`), all `6` featured `.post-card` articles with `220 WPM` reading-time badges, and `#themeToggle` (`Ctrl+J` toggling `.dark` with `#111827` dark surface).",
        f"2. **Theme Specification Manifest ({b}/workspace/THEME_SPEC.json{b})** with exact keys:",
        f"   - {b}\"brand_title\"{b}, {b}\"header_bg_hex\"{b}, {b}\"accent_hex\"{b}, {b}\"dark_surface_hex\"{b}, {b}\"desktop_grid_cols\"{b} (int), {b}\"mobile_breakpoint_px\"{b} (int), {b}\"featured_article_count\"{b} (int), {b}\"reading_wpm_basis\"{b} (int), {b}\"theme_spec_seal\"{b} (string from `Theme Spec Inspector`).",
        "",
    ])
    return {"curve_cad_modeler": role_a, "visual_theme_recreator": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    workspace_map["curve_cad_modeler"].mkdir(parents=True, exist_ok=True)
    (workspace_map["visual_theme_recreator"] / "blog_site").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    stage_private_studio_script(state_dir, "geocurve_ref.py", GEOCURVE_QT_SOURCE)
    boot_tok = secrets.token_hex(16)
    sso_val = secrets.token_hex(18)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})
    html_b = _build_blog_ref_html().encode("utf-8")

    class BlogHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None: return
        def _ok(self) -> bool:
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("rbs203_sso")
                return bool(m and m.value == sso_val)
            except Exception:
                return False
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302); self.send_header("Set-Cookie", f"rbs203_sso={sso_val}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not self._ok():
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: inspect in live Chromium"); return
            if parsed.path == "/api/theme_spec":
                raw = json.dumps({"seal": BLOG_THEME_ORACLE["theme_spec_seal"]}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(html_b))); self.end_headers(); self.wfile.write(html_b)

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"url": f"http://127.0.0.1:{port}/?sso_boot={boot_tok}"}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), BlogHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    bf = state_dir / "boot_url"
    cfg = json.loads(bf.read_text(encoding="utf-8"))
    bf.unlink(missing_ok=True)
    boot_singleton_cdp_chromium([cfg["url"]], window_pos=(460, 50), window_size=(1180, 820))
    boot_isolated_studio_scripts(state_dir, ["geocurve_ref.py"], wait_s=2.2)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["curve_cad_modeler"]
    ws_b = workspace_map["visual_theme_recreator"]

    vf = read_json_safe(ws_a / "vessel_fit.json")
    rs = vf.get("fitted_radii_mm") if isinstance(vf.get("fitted_radii_mm"), list) and len(vf["fitted_radii_mm"]) == 5 else [0.0] * 5
    re_fit = eval_vessel_fit([float(x) for x in rs]) if vf else {"qualified": False, "fit_seal": "NONE", "rms_radial_error_mm": 99.0, "simpson_volume_cm3": 0.0}
    seal_ok = bool(vf and re_fit["qualified"] and vf.get("fit_seal") == re_fit["fit_seal"])
    svg_p = ws_a / "vessel_profile.svg"
    svg_txt = svg_p.read_text(encoding="utf-8", errors="replace") if svg_p.is_file() else ""

    knot_hits = sum(1 for i, tgt_r in enumerate(TARGET_RADII_MM) if abs(float(rs[i]) - tgt_r) <= 2.5)

    # 19 subchecks for Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json_exists", bool(vf), 0.05, "Missing vessel_fit.json"),
        ("a_knot_k0", abs(float(rs[0]) - 28.0) <= 2.5, 0.05, f"K0={rs[0]} != 28.0"),
        ("a_knot_k1", abs(float(rs[1]) - 44.0) <= 2.5, 0.05, f"K1={rs[1]} != 44.0"),
        ("a_knot_k2", abs(float(rs[2]) - 22.0) <= 2.5, 0.05, f"K2={rs[2]} != 22.0"),
        ("a_knot_k3", abs(float(rs[3]) - 38.0) <= 2.5, 0.05, f"K3={rs[3]} != 38.0"),
        ("a_knot_k4", abs(float(rs[4]) - 18.0) <= 2.5, 0.05, f"K4={rs[4]} != 18.0"),
        ("a_knots_atleast3", knot_hits >= 3, 0.05, f"Only {knot_hits}/5 knots fitted"),
        ("a_rms_ok", float(re_fit["rms_radial_error_mm"]) <= 2.2, 0.08, f"rms_radial_error_mm={re_fit['rms_radial_error_mm']} > 2.2"),
        ("a_qualified", bool(re_fit["qualified"]), 0.06, "Vessel profile not qualified"),
        ("a_authentic_seal", seal_ok, 0.10, "fit_seal invalid or not exported from GeoCurve GUI"),
        ("a_vol_accurate", abs(float(vf.get("simpson_volume_cm3", -99)) - re_fit["simpson_volume_cm3"]) <= 2.0 and re_fit["qualified"], 0.06, "simpson_volume_cm3 inaccurate"),
        ("a_z_stations", vf.get("z_stations_mm") == Z_STATIONS_MM, 0.04, "z_stations_mm mismatch"),
        ("a_svg_exists", svg_p.is_file() and "<svg" in svg_txt, 0.05, "Missing or invalid vessel_profile.svg"),
        ("a_svg_dims", "800" in svg_txt and "500" in svg_txt, 0.04, "SVG missing 800x500 dimensions"),
        ("a_svg_curves", (svg_txt.count("<polyline") + svg_txt.count("<path")) >= 2, 0.06, "SVG lacks upper & lower mirrored profile curves"),
        ("a_svg_circles", svg_txt.count("<circle") >= 5, 0.05, "SVG lacks >=5 knot circle markers"),
        (
            "a_svg_vol_label",
            bool(vf)
            and any(
                tok in svg_txt
                for tok in (
                    str(int(re_fit["simpson_volume_cm3"])),
                    str(int(round(re_fit["simpson_volume_cm3"]))),
                )
            ),
            0.04,
            "SVG missing Simpson volume label",
        ),
        ("a_svg_seal_label", seal_ok and str(re_fit["fit_seal"]) in svg_txt, 0.04, "SVG missing fit_seal label"),
        ("a_xml_wellformed", "</svg>" in svg_txt, 0.03, "SVG not closed cleanly"),
    ]

    ts = read_json_safe(ws_b / "THEME_SPEC.json")
    bdir = ws_b / "blog_site"
    idx_h = (bdir / "index.html").read_text(encoding="utf-8", errors="replace") if (bdir / "index.html").is_file() else ""
    css_t = (bdir / "styles.css").read_text(encoding="utf-8", errors="replace") if (bdir / "styles.css").is_file() else ""
    js_t = (bdir / "app.js").read_text(encoding="utf-8", errors="replace") if (bdir / "app.js").is_file() else ""
    all_web = (idx_h + "\n" + css_t + "\n" + js_t)
    all_low = all_web.lower()

    # 19 subchecks for Role B (19 + 19 = 38 total subchecks!)
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_spec_exists", bool(ts), 0.04, "Missing THEME_SPEC.json"),
        ("b_spec_title", ts.get("brand_title") == "Meridian Systems Journal", 0.05, "brand_title mismatch"),
        ("b_spec_hdr_hex", str(ts.get("header_bg_hex", "")).upper() == "#0F172A", 0.05, "header_bg_hex != '#0F172A'"),
        ("b_spec_acc_hex", str(ts.get("accent_hex", "")).upper() == "#E11D48", 0.05, "accent_hex != '#E11D48'"),
        ("b_spec_dark_hex", str(ts.get("dark_surface_hex", "")).upper() == "#111827", 0.05, "dark_surface_hex != '#111827'"),
        ("b_spec_cols_bp", ts.get("desktop_grid_cols") == 3 and ts.get("mobile_breakpoint_px") == 700, 0.06, "desktop_grid_cols or mobile_breakpoint_px mismatch"),
        ("b_spec_cnt_wpm", ts.get("featured_article_count") == 6 and ts.get("reading_wpm_basis") == 220, 0.06, "featured_article_count or reading_wpm_basis mismatch"),
        ("b_spec_seal", ts.get("theme_spec_seal") == BLOG_THEME_ORACLE["theme_spec_seal"], 0.09, "theme_spec_seal mismatch"),
        ("b_html_exists", (bdir / "index.html").is_file(), 0.05, "Missing blog_site/index.html"),
        ("b_css_exists", (bdir / "styles.css").is_file(), 0.04, "Missing blog_site/styles.css"),
        ("b_js_exists", (bdir / "app.js").is_file(), 0.04, "Missing blog_site/app.js"),
        ("b_brand_in_html", "meridian systems journal" in all_low, 0.05, "index.html missing Meridian Systems Journal header"),
        ("b_colors_in_css", "#0f172a" in all_low and "#e11d48" in all_low and "#111827" in all_low, 0.06, "CSS missing #0F172A, #E11D48, or #111827"),
        ("b_toc_sticky", "tocnav" in all_low and "sticky" in all_low, 0.05, "Missing sticky #tocNav"),
        ("b_grid_3col", "articlegrid" in all_low and ("repeat(3" in all_low or "1fr 1fr 1fr" in all_low), 0.06, "Missing 3-column #articleGrid"),
        ("b_media_700", "@media" in all_low and "700px" in all_low, 0.06, "Missing @media 700px mobile breakpoint"),
        ("b_six_cards", all_low.count("post-card") >= 6 or ("io_uring" in all_low and "nvme-of" in all_low), 0.05, "Missing 6 featured post-card articles"),
        ("b_read_badges", "min read" in all_low, 0.04, "Missing 220 WPM min read badges"),
        ("b_dark_toggle_ctrlj", "themetoggle" in all_low and "dark" in all_low, 0.05, "Missing #themeToggle dark-mode handler"),
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


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    assert role in ("curve_cad_modeler", "visual_theme_recreator")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "curve_cad_modeler":
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'GeoCurve Revolve Studio' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,40,50,860,600; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.35; "
                "python3 - <<'PY'\n"
                "import io, subprocess\n"
                "from PIL import Image\n"
                "raw = subprocess.check_output(['import', '-window', 'root', 'png:-'])\n"
                "im = Image.open(io.BytesIO(raw)).convert('RGB')\n"
                "# Locate orange handle & green target dot right at each station vertical column\n"
                "xbands = [(128, 156), (278, 306), (428, 456), (578, 606), (728, 756)]\n"
                "for (x0, x1) in xbands:\n"
                "    org = [(x, y) for x in range(x0, x1) for y in range(110, 560) if im.getpixel((x,y))[0]>225 and 95<=im.getpixel((x,y))[1]<=140 and im.getpixel((x,y))[2]<45]\n"
                "    grn = [(x, y) for x in range(x0, x1) for y in range(110, 560) if im.getpixel((x,y))[0]<70 and im.getpixel((x,y))[1]>170 and 110<=im.getpixel((x,y))[2]<=170]\n"
                "    cx = sum(p[0] for p in org)//len(org); cy = sum(p[1] for p in org)//len(org)\n"
                "    ty = sum(p[1] for p in grn)//len(grn)\n"
                "    subprocess.run(['xdotool', 'mousemove', str(cx), str(cy), 'mousedown', '1'], check=True)\n"
                "    for k in range(1, 9):\n"
                "        subprocess.run(['xdotool', 'mousemove', str(cx), str(cy + int((ty - cy)*k/8))], check=True)\n"
                "    subprocess.run(['xdotool', 'mouseup', '1'], check=True)\n"
                "PY\n"
                "sleep 0.2; wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.15; "
                "xdotool key --clearmodifiers ctrl+e; sleep 0.35"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=25)
            vf = read_json_safe(Path("/home/user/Downloads/vessel_fit.json"))
            write_json(ws / "vessel_fit.json", vf)
            up_pts = " ".join(f"{100 + int(z*6)},{250 - int(r*4)}" for z, r in zip(Z_STATIONS_MM, vf["fitted_radii_mm"]))
            lo_pts = " ".join(f"{100 + int(z*6)},{250 + int(r*4)}" for z, r in zip(Z_STATIONS_MM, vf["fitted_radii_mm"]))
            circs = "\n".join(f'  <circle cx="{100 + int(z*6)}" cy="{250 - int(r*4)}" r="5" fill="#F97316"/>' for z, r in zip(Z_STATIONS_MM, vf["fitted_radii_mm"]))
            (ws / "vessel_profile.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500">\n'
                f'  <polyline points="{up_pts}" fill="none" stroke="#10B981" stroke-width="3"/>\n'
                f'  <polyline points="{lo_pts}" fill="none" stroke="#10B981" stroke-width="3"/>\n'
                f'{circs}\n'
                f'  <text x="80" y="470">Volume={vf["simpson_volume_cm3"]} cm3 | {vf["fit_seal"]}</text>\n'
                f'</svg>\n',
                encoding="utf-8",
            )
        else:
            targets = cdp_list_targets(9222)
            t_b = next(t for t in targets if str(port) in t.get("url", ""))
            out = cdp_eval_js(t_b["webSocketDebuggerUrl"], "loadSpec().then(()=>document.getElementById('specOut').textContent);")
            assert BLOG_THEME_ORACLE["theme_spec_seal"] in str(out)
            write_json(ws / "THEME_SPEC.json", BLOG_THEME_ORACLE)
            bdir = ws / "blog_site"
            bdir.mkdir(parents=True, exist_ok=True)
            (bdir / "styles.css").write_text(
                "body{margin:0;background:#f8fafc;color:#0f172a;} body.dark{background:#111827;color:#f8fafc;}\n"
                "header{background:#0F172A;border-bottom:4px solid #E11D48;padding:16px;}\n"
                "#tocNav{position:sticky;top:16px;}\n"
                "#articleGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}\n"
                "@media (max-width: 700px){#articleGrid{grid-template-columns:1fr;}}\n"
                ".post-card{border-top:4px solid #E11D48;padding:12px;}\n",
                encoding="utf-8",
            )
            (bdir / "app.js").write_text(
                "document.getElementById('themeToggle').onclick=()=>document.body.classList.toggle('dark');\n"
                "window.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key.toLowerCase()==='j')document.body.classList.toggle('dark');});\n",
                encoding="utf-8",
            )
            cards = "".join(
                f'<article class="post-card"><h3>{t}</h3><p class="read-badge">{(w+219)//220} min read</p></article>'
                for t, w in [
                    ("Zero-Copy io_uring Pipelines", 880), ("Raft Lease Read Linearizability", 1100),
                    ("eBPF Verifier Abstract Domains", 660), ("NUMA-Aware Slab Allocators", 1320),
                    ("WasmGC Tail-Call Trampolines", 440), ("NVMe-oF TCP Pacing", 1540),
                ]
            )
            (bdir / "index.html").write_text(
                "<!doctype html><html><head><meta charset='utf-8'/><link rel='stylesheet' href='styles.css'/></head><body>"
                "<header><h1>Meridian Systems Journal</h1><button id='themeToggle'>Dark</button></header>"
                f"<nav id='tocNav'>TOC</nav><section id='articleGrid'>{cards}</section>"
                "<script src='app.js'></script></body></html>\n",
                encoding="utf-8",
            )

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_5 + LAW_7): Chromium overlaps GeoCurve mid-drag, leaving K3/K4 unfitted."""
    solve_role("curve_cad_modeler", workspace_map, port, careful_conc=False)
    solve_role("visual_theme_recreator", workspace_map, port, careful_conc=False)
    ws_a = workspace_map["curve_cad_modeler"]
    unfitted = eval_vessel_fit([28.0, 44.0, 22.0, 19.0, 34.0])
    write_json(ws_a / "vessel_fit.json", unfitted)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

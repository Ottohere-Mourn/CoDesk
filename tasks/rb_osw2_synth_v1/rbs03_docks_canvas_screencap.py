"""RBS-03: 5-Window Floating-Dock 2D Cam Canvas Drag vs. Root-Screen Thermal Capture & SnapCallout.

Grounded in RecreationBench Empirical Laws (RB-B5 7-Dock Pencil2D + ksnip & RB-B7 SolveSpace + Bruno):
  - LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB: VectorDocks2D spawns a main 2D canvas plus
    4 floating QDockWidget tool windows that physically overlap ThermalBoard Target at (580, 90).
    Role A's coordinate drag on cam handles H1..H3 collides with Role B raising ThermalBoard Target
    to capture an unobstructed 8-zone thermal image and recreate SnapCallout Studio.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any

from tasks.rb_osw2_synth_v1.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    build_grade_payload,
    evaluate_recreated_gui_app,
    read_json_safe,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS-03"
PORTAL_PORT = 19303

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "5-Window Floating-Dock 2D Cam Canvas Drag vs. Unobstructed PCB Thermal Capture & SnapCallout",
    "domain": "2D Cam-Linkage Interactive CAD Docks & X11 Thermal Region Capture / Annotation Tooling",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB",
        "LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("dock_cam_engineer", "thermal_snap_engineer"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "recreation_explore_build_verify",
        "total_subchecks": 28,
        "cli_bypass_resistance": 0.96,
        "role_a": {
            "slug": "dock_cam_engineer",
            "est_role_seconds": 520.0,
            "traits": [
                "custom_2d_canvas_drag",
                "overlapping_docks_or_root_screencap",
                "candidate_window_launch_on_shared_display",
            ],
        },
        "role_b": {
            "slug": "thermal_snap_engineer",
            "est_role_seconds": 530.0,
            "traits": [
                "overlapping_docks_or_root_screencap",
                "candidate_window_launch_on_shared_display",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

CAM_SALT = "vectordocks-cam-rbs03"
DOCK_SPEC_ORACLE = {
    "spindle_rpm": 1800,
    "follower_roller_mm": 12.5,
    "onion_skin_frames": 5,
    "dock_law_seal": "CAMDOCK-5518",
}

# 8 PCB thermal zones: (zone_id, rgb_swatch, temp_c)
THERMAL_ZONES: list[tuple[str, tuple[int, int, int], float]] = [
    ("Z1_INPUT_CHOKE", (42, 157, 143), 64.2),
    ("Z2_VRM_NORTH",   (230, 57, 70),  91.4),   # > 85.0 C hotspot
    ("Z3_DDR5_BANK_A", (69, 123, 157), 71.8),
    ("Z4_PCIE_RETMR",  (233, 196, 106), 79.5),
    ("Z5_ASIC_DIE",    (214, 40, 40),  96.8),   # > 85.0 C hotspot
    ("Z6_BMC_FLASH",   (82, 183, 136), 58.6),
    ("Z7_QSFP_CAGE",   (244, 102, 58), 88.2),   # > 85.0 C hotspot
    ("Z8_CLK_SYNTH",   (106, 76, 147), 69.0),
]

THERMAL_ORACLE = {
    "emissivity_coeff": 0.94,
    "thermal_cal_seal": "THERM-CAL-8820",
    "hotspot_threshold_c": 85.0,
    "hotspot_zones": ["Z2_VRM_NORTH", "Z5_ASIC_DIE", "Z7_QSFP_CAGE"],
    "peak_zone_id": "Z5_ASIC_DIE",
    "peak_temp_c": 96.8,
    "mean_board_temp_c": round(sum(z[2] for z in THERMAL_ZONES) / len(THERMAL_ZONES), 2),
}


def eval_cam_handles(h1: float, h2: float, h3: float) -> dict[str, Any]:
    # Target smooth cycloidal lift: h1 in [16..24], h2 in [34..44], h3 in [18..26] (initial is 8, 56, 9 -> high pressure angle & accel!)
    dh1 = abs(h2 - h1)
    dh2 = abs(h2 - h3)
    pressure_deg = round(11.5 + 0.42 * max(dh1, dh2) + 0.18 * abs(h1 - h3), 2)
    peak_acc = round(5.8 + 0.19 * (dh1 + dh2) * 0.5 + 0.12 * abs(h2 - 38.0), 2)
    min_rad = round(42.0 - 0.35 * max(0.0, h2 - 36.0) - 0.45 * max(0.0, 16.0 - min(h1, h3)), 2)
    qualified = bool(
        14.0 <= h1 <= 26.0
        and 32.0 <= h2 <= 44.0
        and 14.0 <= h3 <= 26.0
        and pressure_deg <= 28.0
        and peak_acc <= 14.5
        and min_rad >= 22.0
    )
    sig = f"{CAM_SALT}:{h1:.1f}:{h2:.1f}:{h3:.1f}:{qualified}"
    seal = "CAM-CERT-" + hashlib.sha256(sig.encode("utf-8")).hexdigest()[:10].upper() if qualified else "UNQUALIFIED_CAM"
    return {
        "handles_mm": [round(h1, 2), round(h2, 2), round(h3, 2)],
        "max_pressure_angle_deg": pressure_deg,
        "peak_accel_m_s2": peak_acc,
        "min_pitch_radius_mm": min_rad,
        "qualified": qualified,
        "cam_cert_seal": seal,
    }


VECTORDOCKS_QT_SOURCE = f"""import hashlib, json, math, os, sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDockWidget, QShortcut
)
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt, QPointF

SALT = {json.dumps(CAM_SALT)}
DOCK = {json.dumps(DOCK_SPEC_ORACLE)}

def eval_cam(h1, h2, h3):
    dh1, dh2 = abs(h2 - h1), abs(h2 - h3)
    pdeg = round(11.5 + 0.42*max(dh1, dh2) + 0.18*abs(h1 - h3), 2)
    acc = round(5.8 + 0.095*(dh1 + dh2) + 0.12*abs(h2 - 38.0), 2)
    mrad = round(42.0 - 0.35*max(0.0, h2 - 36.0) - 0.45*max(0.0, 16.0 - min(h1, h3)), 2)
    ok = (14.0<=h1<=26.0 and 32.0<=h2<=44.0 and 14.0<=h3<=26.0 and pdeg<=28.0 and acc<=14.5 and mrad>=22.0)
    sig = f"{{SALT}}:{{h1:.1f}}:{{h2:.1f}}:{{h3:.1f}}:{{ok}}"
    seal = "CAM-CERT-" + hashlib.sha256(sig.encode()).hexdigest()[:10].upper() if ok else "UNQUALIFIED_CAM"
    return {{"handles_mm":[round(h1,2),round(h2,2),round(h3,2)],"max_pressure_angle_deg":pdeg,
            "peak_accel_m_s2":acc,"min_pitch_radius_mm":mrad,"qualified":ok,"cam_cert_seal":seal}}

class CamCanvas(QWidget):
    def __init__(self, on_upd):
        super().__init__()
        self.setMinimumSize(620, 440)
        self.h = [8.0, 56.0, 9.0]  # Initial unqualified cam profile!
        self.drag_idx = None
        self.on_upd = on_upd
        self.xs = [140.0, 310.0, 480.0]

    def h2y(self, v):
        return 380.0 - v * 5.2

    def y2h(self, sy):
        return round(max(4.0, min(62.0, (380.0 - sy) / 5.2)), 1)

    def mousePressEvent(self, ev):
        p = ev.pos()
        for i, xv in enumerate(self.xs):
            yv = self.h2y(self.h[i])
            if math.hypot(p.x() - xv, p.y() - yv) <= 26.0:
                self.drag_idx = i
                break

    def mouseMoveEvent(self, ev):
        if self.drag_idx is None:
            return
        self.h[self.drag_idx] = self.y2h(ev.pos().y())
        self.on_upd()
        self.update()

    def mouseReleaseEvent(self, _ev):
        self.drag_idx = None

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(17, 24, 39))
        # Target green corridor band
        qp.fillRect(100, int(self.h2y(26)), 80, int(self.h2y(14) - self.h2y(26)), QColor(16, 185, 129, 45))
        qp.fillRect(270, int(self.h2y(44)), 80, int(self.h2y(32) - self.h2y(44)), QColor(16, 185, 129, 45))
        qp.fillRect(440, int(self.h2y(26)), 80, int(self.h2y(14) - self.h2y(26)), QColor(16, 185, 129, 45))

        pts = [QPointF(40.0, 380.0)] + [QPointF(self.xs[i], self.h2y(self.h[i])) for i in range(3)] + [QPointF(580.0, 380.0)]
        qp.setPen(QPen(QColor(56, 189, 248), 3))
        for i in range(len(pts) - 1):
            qp.drawLine(pts[i], pts[i + 1])
        for i in range(3):
            cx, cy = self.xs[i], self.h2y(self.h[i])
            qp.setBrush(QBrush(QColor(249, 115, 22)))
            qp.setPen(QPen(QColor(255, 255, 255), 2))
            qp.drawEllipse(QPointF(cx, cy), 13.0, 13.0)
            qp.setFont(QFont("Monospace", 10, QFont.Bold))
            qp.drawText(int(cx - 32), int(cy - 18), f"H{{i+1}}={{self.h[i]:.1f}}mm")

class VectorDocksWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VectorDocks2D Studio")
        self.setGeometry(40, 50, 680, 580)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        self.gauge_lbl = QLabel()
        self.gauge_lbl.setStyleSheet("font-family: monospace; font-size: 12px; padding: 6px; background: #1f2937; color: #f9fafb;")
        lay.addWidget(self.gauge_lbl)
        self.canvas = CamCanvas(self.refresh)
        lay.addWidget(self.canvas)
        row = QHBoxLayout()
        btn = QPushButton("&Export Certified Cam Profile (/home/user/Downloads/cam_certified.json) [Ctrl+E]")
        btn.clicked.connect(self.export_cam)
        row.addWidget(btn)
        self.msg_lbl = QLabel("Drag orange handles H1..H3 into green bands, then Export.")
        row.addWidget(self.msg_lbl)
        lay.addLayout(row)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_cam)

        # 4 Floating QDockWidget panels overlapping (620..1240, 110..620)!
        docks = [
            ("Timeline Dock", 620, 110, f"Spindle Speed: {{DOCK['spindle_rpm']}} RPM\\nCycle Steps: 360 deg"),
            ("Onion-Skin Dock", 920, 110, f"Onion-Skin Frames: {{DOCK['onion_skin_frames']}}\\nOverlay Opacity: 40%"),
            ("Roller & Snap Dock", 620, 360, f"Follower Roller Diameter: {{DOCK['follower_roller_mm']}} mm\\nGrid Snap: 0.5 mm"),
            ("Cam Law Inspector Dock", 920, 360, f"Dock Law Seal: {{DOCK['dock_law_seal']}}\\nEnvelope: Angle<=28 deg, Acc<=14.5, R>=22"),
        ]
        self.floating_docks = []
        for title, dx, dy, txt in docks:
            dk = QDockWidget(title, self)
            lbl = QLabel(txt)
            lbl.setStyleSheet("padding: 12px; font-family: monospace; background: #fef3c7; color: #111827;")
            dk.setWidget(lbl)
            dk.setFloating(True)
            dk.setGeometry(dx, dy, 280, 190)
            dk.show()
            self.floating_docks.append(dk)
        self.refresh()

    def refresh(self):
        st = eval_cam(*self.canvas.h)
        tag = "PASS" if st["qualified"] else "OUT_OF_SPEC"
        self.gauge_lbl.setText(
            f"[{{tag}}] Angle={{st['max_pressure_angle_deg']}}/28.0 deg | Acc={{st['peak_accel_m_s2']}}/14.5 | MinR={{st['min_pitch_radius_mm']}}/>=22.0"
        )

    def export_cam(self):
        st = eval_cam(*self.canvas.h)
        p = Path("/home/user/Downloads/cam_certified.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, indent=2) + "\\n")
        os.chmod(p, 0o644)
        self.msg_lbl.setText(f"Exported (qualified={{st['qualified']}}, seal={{st['cam_cert_seal']}})")

app = QApplication(sys.argv)
app.setApplicationName("vectordocks2d-studio")
w = VectorDocksWin()
w.show()
sys.exit(app.exec_())
"""

THERMALBOARD_QT_SOURCE = f"""import json, sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QShortcut
from PyQt5.QtGui import QPainter, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt

ZONES = {json.dumps([(z[0], list(z[1]), z[2]) for z in THERMAL_ZONES])}
ORACLE = {json.dumps(THERMAL_ORACLE)}

class ThermalGrid(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(840, 480)

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(241, 245, 249))
        for idx, (zid, rgb, tc) in enumerate(ZONES):
            r, c = idx // 4, idx % 4
            x0, y0 = 30 + c * 200, 25 + r * 220
            qp.fillRect(x0, y0, 175, 165, QColor(rgb[0], rgb[1], rgb[2]))
            qp.setPen(QColor(15, 23, 42))
            qp.setFont(QFont("Monospace", 10, QFont.Bold))
            qp.drawText(x0 + 4, y0 + 188, f"{{zid}}: {{tc:.1f}}C")

class ThermalBoardWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ThermalBoard Target")
        self.setGeometry(580, 90, 900, 620)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        hdr = QHBoxLayout()
        b_cal = QPushButton("&Show Emissivity & Calibration Seal [F8]")
        b_cal.clicked.connect(self.reveal_cal)
        hdr.addWidget(b_cal)
        self.cal_lbl = QLabel("Press F8 to display IR Emissivity & Calibration Seal before capturing.")
        self.cal_lbl.setStyleSheet("font-family: monospace; padding: 6px; background: #e2e8f0; color: #0f172a;")
        hdr.addWidget(self.cal_lbl)
        lay.addLayout(hdr)
        lay.addWidget(ThermalGrid())
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("F8"), self, activated=self.reveal_cal)

    def reveal_cal(self):
        self.cal_lbl.setText(
            f"EMISSIVITY={{ORACLE['emissivity_coeff']}} | CAL_SEAL={{ORACLE['thermal_cal_seal']}} | HOTSPOT_LIMIT=>85.0C"
        )

app = QApplication(sys.argv)
app.setApplicationName("thermalboard-target")
w = ThermalBoardWin()
w.show()
w.lower()  # Starts underneath VectorDocks2D's 4 floating QDockWidgets!
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# 2D Cam-Linkage Interactive Optimization & Viewer Work Order — {b}dock_cam_engineer{b}",
        "",
        "## Scope & Deliverables",
        f"Calibrate the 3-handle cam profile in the live **VectorDocks2D Studio** desktop application and build a standalone cam-profile viewer in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Interactive Cam Handle Drag & Signed Export ({b}/workspace/cam_certified.json{b})**:",
        f"   - In **VectorDocks2D Studio**, drag the three orange cam handles {b}H1{b}, {b}H2{b}, and {b}H3{b} until all three gauges pass ({b}max_pressure_angle_deg <= 28.0{b}, {b}peak_accel_m_s2 <= 14.5{b}, {b}min_pitch_radius_mm >= 22.0{b}), export {b}/home/user/Downloads/cam_certified.json{b} (`Ctrl+E`), verify {b}\"qualified\": true{b}, and copy it to {b}/workspace/cam_certified.json{b}.",
        f"2. **Floating Dock Parameter Manifest ({b}/workspace/CAM_DOCK_SPEC.json{b})**:",
        "   - Inspect all four floating dock windows (`Timeline Dock`, `Onion-Skin Dock`, `Roller & Snap Dock`, `Cam Law Inspector Dock`) and record exact keys:",
        f"     - {b}\"spindle_rpm\"{b} (int), {b}\"follower_roller_mm\"{b} (float), {b}\"onion_skin_frames\"{b} (int), {b}\"dock_law_seal\"{b} (string)",
        f"3. **Standalone CamViewer GUI ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Create an executable GUI launcher {b}/workspace/recreation/run_app.sh{b} opening a window titled {b}CamProfile Viewer{b} (`>= 620 x 420` px) displaying the certified `handles_mm`, `cam_cert_seal`, `spindle_rpm`, and `dock_law_seal`.",
        "",
    ])

    role_b = "\n".join([
        f"# Unobstructed PCB Thermal Capture & SnapCallout Annotator Work Order — {b}thermal_snap_engineer{b}",
        "",
        "## Scope & Deliverables",
        f"Audit the 8-zone infrared PCB board in the live **ThermalBoard Target** window on the workstation and build the **SnapCallout Annotator** desktop utility in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Unobstructed Thermal Target Capture ({b}/workspace/pcb_thermal_clean.png{b})**:",
        f"   - Bring **ThermalBoard Target** cleanly to the foreground so none of its 8 color thermal zones (`Z1..Z8`) are covered by floating dock panels, press `F8` so the emissivity & calibration banner is visible, and save a clean window PNG (`>= 840 x 540` px) to {b}/workspace/pcb_thermal_clean.png{b}.",
        f"2. **Hotspot Audit Report ({b}/workspace/THERMAL_HOTSPOT_AUDIT.json{b})**:",
        "   - Record exact keys from **ThermalBoard Target**:",
        f"     - {b}\"emissivity_coeff\"{b} (float), {b}\"thermal_cal_seal\"{b} (string), {b}\"hotspot_threshold_c\"{b} (`85.0`)",
        f"     - {b}\"hotspot_zones\"{b} (sorted list of zone IDs strictly exceeding `85.0 C`), {b}\"peak_zone_id\"{b} (string), {b}\"peak_temp_c\"{b} (float), {b}\"mean_board_temp_c\"{b} (float rounded to 2 decimals)",
        f"3. **Standalone SnapCallout GUI ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Create an executable GUI launcher {b}/workspace/recreation/run_app.sh{b} opening a window titled {b}SnapCallout Studio{b} (`>= 640 x 420` px) listing the 3 hotspot zones, peak temperature, and `thermal_cal_seal` with callout filter controls.",
        "",
    ])
    return {"dock_cam_engineer": role_a, "thermal_snap_engineer": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    for ws in workspace_map.values():
        (ws / "recreation").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    stage_private_studio_script(state_dir, "vectordocks_ref.py", VECTORDOCKS_QT_SOURCE)
    stage_private_studio_script(state_dir, "thermalboard_ref.py", THERMALBOARD_QT_SOURCE)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            raw = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text('{"mode":"rbs03_docks_thermal"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_isolated_studio_scripts(state_dir, ["thermalboard_ref.py", "vectordocks_ref.py"], wait_s=2.5)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image

    ws_a = workspace_map["dock_cam_engineer"]
    ws_b = workspace_map["thermal_snap_engineer"]

    cert = read_json_safe(ws_a / "cam_certified.json")
    hs = cert.get("handles_mm") if isinstance(cert.get("handles_mm"), list) and len(cert["handles_mm"]) == 3 else [0.0, 0.0, 0.0]
    re_cam = eval_cam_handles(float(hs[0]), float(hs[1]), float(hs[2])) if cert else {"qualified": False, "cam_cert_seal": "NONE"}
    cam_seal_ok = bool(cert and re_cam["qualified"] and cert.get("cam_cert_seal") == re_cam["cam_cert_seal"])
    dock_sp = read_json_safe(ws_a / "CAM_DOCK_SPEC.json")
    gui_a = evaluate_recreated_gui_app(ws_a / "recreation/run_app.sh", disp_num=115, expected_title_sub="CamProfile")
    ax_a = gui_a["initial_ax_text"]

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_cert_exists", bool(cert), 0.06, "Missing /workspace/cam_certified.json"),
        ("a_pressure_ok", bool(cert) and float(re_cam.get("max_pressure_angle_deg", 99)) <= 28.0, 0.08, "max_pressure_angle_deg > 28.0"),
        ("a_accel_ok", bool(cert) and float(re_cam.get("peak_accel_m_s2", 99)) <= 14.5, 0.08, "peak_accel_m_s2 > 14.5"),
        ("a_radius_ok", bool(cert) and float(re_cam.get("min_pitch_radius_mm", 0)) >= 22.0, 0.08, "min_pitch_radius_mm < 22.0"),
        ("a_authentic_cam_seal", cam_seal_ok, 0.10, "cam_cert_seal invalid or cam not exported from VectorDocks2D"),
        ("a_dock_rpm", dock_sp.get("spindle_rpm") == 1800, 0.06, "spindle_rpm != 1800"),
        ("a_dock_roller", dock_sp.get("follower_roller_mm") == 12.5, 0.06, "follower_roller_mm != 12.5"),
        ("a_dock_onion", dock_sp.get("onion_skin_frames") == 5, 0.06, "onion_skin_frames != 5"),
        ("a_dock_seal", dock_sp.get("dock_law_seal") == "CAMDOCK-5518", 0.08, "dock_law_seal != 'CAMDOCK-5518'"),
        ("a_viewer_exists", gui_a["script_exists"], 0.06, "Missing /workspace/recreation/run_app.sh"),
        ("a_viewer_mapped", gui_a["window_mapped"] and "camprofile" in gui_a["window_title"].lower(), 0.08, "CamProfile Viewer window not mapped"),
        ("a_viewer_visual", gui_a["visual_nonblank"] and gui_a["win_w"] >= 580, 0.07, "CamProfile Viewer visual check failed"),
        ("a_viewer_ax_seal", "CAMDOCK-5518" in ax_a or "1800" in ax_a, 0.07, "CamProfile Viewer AT-SPI missing dock_law_seal/rpm"),
        ("a_viewer_ax_cert", bool(cam_seal_ok and str(re_cam["cam_cert_seal"]) in ax_a), 0.06, "CamProfile Viewer AT-SPI missing cam_cert_seal"),
    ]

    aud_b = read_json_safe(ws_b / "THERMAL_HOTSPOT_AUDIT.json")
    png_b = ws_b / "pcb_thermal_clean.png"
    zone_hits = 0
    if png_b.is_file() and png_b.stat().st_size > 2500:
        try:
            with Image.open(png_b) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                if w >= 800 and h >= 500:
                    # Verify distinct zone colors across the 2x4 grid (not covered by amber #fef3c7 floating docks!)
                    for _zid, target_rgb, _tc in THERMAL_ZONES:
                        found = False
                        for sx in range(20, w - 20, 14):
                            for sy in range(40, h - 20, 14):
                                px = rgb.getpixel((sx, sy))
                                if all(abs(px[k] - target_rgb[k]) <= 18 for k in range(3)):
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            zone_hits += 1
        except Exception:
            zone_hits = 0

    gui_b = evaluate_recreated_gui_app(ws_b / "recreation/run_app.sh", disp_num=116, expected_title_sub="SnapCallout")
    ax_b = gui_b["initial_ax_text"]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_png_exists", png_b.is_file() and zone_hits >= 5, 0.08, f"pcb_thermal_clean.png missing or heavily occluded ({zone_hits}/8 zones visible)"),
        ("b_png_all8_unobstructed", zone_hits == 8, 0.10, f"pcb_thermal_clean.png occluded by floating docks ({zone_hits}/8 != 8/8 zones)"),
        ("b_emissivity", aud_b.get("emissivity_coeff") == 0.94, 0.06, "emissivity_coeff != 0.94 (F8 banner)"),
        ("b_cal_seal", aud_b.get("thermal_cal_seal") == "THERM-CAL-8820", 0.09, "thermal_cal_seal != 'THERM-CAL-8820' (F8 banner)"),
        ("b_hotspot_list", sorted(aud_b.get("hotspot_zones") or []) == THERMAL_ORACLE["hotspot_zones"], 0.09, "hotspot_zones mismatch"),
        ("b_peak_zone", aud_b.get("peak_zone_id") == "Z5_ASIC_DIE" and aud_b.get("peak_temp_c") == 96.8, 0.08, "peak_zone_id or peak_temp_c mismatch"),
        ("b_mean_temp", isinstance(aud_b.get("mean_board_temp_c"), (int, float)) and abs(float(aud_b["mean_board_temp_c"]) - THERMAL_ORACLE["mean_board_temp_c"]) <= 0.25, 0.07, "mean_board_temp_c mismatch"),
        ("b_threshold", aud_b.get("hotspot_threshold_c") == 85.0, 0.05, "hotspot_threshold_c != 85.0"),
        ("b_app_exists", gui_b["script_exists"], 0.06, "Missing /workspace/recreation/run_app.sh"),
        ("b_app_mapped", gui_b["window_mapped"] and "snapcallout" in gui_b["window_title"].lower(), 0.08, "SnapCallout Studio window not mapped"),
        ("b_app_visual", gui_b["visual_nonblank"] and gui_b["win_w"] >= 580, 0.08, "SnapCallout Studio visual check failed"),
        ("b_app_ax_hotspots", all(z in ax_b for z in ("Z2_VRM_NORTH", "Z5_ASIC_DIE", "Z7_QSFP_CAGE")), 0.08, "SnapCallout AT-SPI missing hotspot zones"),
        ("b_app_ax_seal", "THERM-CAL-8820" in ax_b and "96.8" in ax_b, 0.08, "SnapCallout AT-SPI missing thermal_cal_seal or 96.8C"),
    ]
    # Add 14th subcheck on Role B so 14+14 = 28 exact subchecks
    checks_b.append(("b_app_controls", any(w in ax_b.lower() for w in ("callout", "filter", "hotspot", "export")), 0.00 if False else 0.06, "SnapCallout missing callout/filter controls"))

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
    del port
    assert role in ("dock_cam_engineer", "thermal_snap_engineer")
    ws = workspace_map[role]
    rec = ws / "recreation"
    rec.mkdir(parents=True, exist_ok=True)

    def _work() -> None:
        if role == "dock_cam_engineer":
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'VectorDocks2D Studio' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,40,50,680,580; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.35; "
                "python3 - <<'PY'\n"
                "import io, subprocess\n"
                "from PIL import Image\n"
                "raw = subprocess.check_output(['import', '-window', 'root', 'png:-'])\n"
                "im = Image.open(io.BytesIO(raw)).convert('RGB')\n"
                "pts = []\n"
                "for x in range(60, 700, 2):\n"
                "    for y in range(90, 610, 2):\n"
                "        r, g, b = im.getpixel((x, y))\n"
                "        if r > 220 and 90 <= g <= 145 and b < 55:\n"
                "            pts.append((x, y))\n"
                "b1 = [p for p in pts if p[0] < 260]\n"
                "b2 = [p for p in pts if 260 <= p[0] < 430]\n"
                "b3 = [p for p in pts if p[0] >= 430]\n"
                "# H1: 8->20 (dy = -62px), H2: 56->38 (dy = +94px), H3: 9->20 (dy = -57px)\n"
                "for bucket, dy in ((b1, -62), (b2, 94), (b3, -57)):\n"
                "    cx = sum(p[0] for p in bucket)//len(bucket)\n"
                "    cy = sum(p[1] for p in bucket)//len(bucket)\n"
                "    subprocess.run(['xdotool', 'mousemove', str(cx), str(cy), 'mousedown', '1'], check=True)\n"
                "    for k in range(1, 8):\n"
                "        subprocess.run(['xdotool', 'mousemove', str(cx), str(int(cy + dy*k/7))], check=True)\n"
                "    subprocess.run(['xdotool', 'mouseup', '1'], check=True)\n"
                "PY\n"
                "sleep 0.2; wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.15; "
                "xdotool key --clearmodifiers ctrl+e; sleep 0.4"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=25)
            cert = json.loads(Path("/home/user/Downloads/cam_certified.json").read_text(encoding="utf-8"))
            write_json(ws / "cam_certified.json", cert)
            write_json(ws / "CAM_DOCK_SPEC.json", DOCK_SPEC_ORACLE)
            viewer_py = (
                "import sys\nfrom PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton\n"
                f"CERT = {repr(cert)}\nDOCK = {repr(DOCK_SPEC_ORACLE)}\n"
                "app = QApplication(sys.argv)\nw = QMainWindow(); w.setWindowTitle('CamProfile Viewer'); w.resize(660, 460)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#0f172a;color:#f8fafc;'); v = QVBoxLayout(cw)\n"
                "l1 = QLabel('Certified Handles: ' + str(CERT['handles_mm']) + ' | Seal: ' + str(CERT['cam_cert_seal']))\n"
                "l1.setStyleSheet('background:#1e293b;color:#38bdf8;padding:8px;')\n"
                "l2 = QLabel('Spindle RPM: ' + str(DOCK['spindle_rpm']) + ' | Dock Seal: ' + str(DOCK['dock_law_seal']))\n"
                "l2.setStyleSheet('background:#065f46;color:#ecfdf5;padding:8px;')\n"
                "b1 = QPushButton('Refresh Cam Curve'); b1.setStyleSheet('background:#2563eb;color:#ffffff;padding:8px;')\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1)\n"
                "w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "viewer.py").write_text(viewer_py, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/viewer.py\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)
        else:
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'ThermalBoard Target' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,760,80,900,620; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.35; "
                "xdotool key --clearmodifiers F8; sleep 0.35; "
                f"import -window \"$wid\" {ws}/pcb_thermal_clean.png"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=20)
            write_json(ws / "THERMAL_HOTSPOT_AUDIT.json", THERMAL_ORACLE)
            snap_py = (
                "import sys\nfrom PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton\n"
                f"OR = {json.dumps(THERMAL_ORACLE)}\n"
                "app = QApplication(sys.argv)\nw = QMainWindow(); w.setWindowTitle('SnapCallout Studio'); w.resize(680, 460)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#0f172a;color:#f8fafc;'); v = QVBoxLayout(cw)\n"
                "hz = ', '.join(OR['hotspot_zones'])\n"
                "l1 = QLabel('Hotspot Zones: ' + hz); l1.setStyleSheet('background:#7f1d1d;color:#fecaca;padding:8px;')\n"
                "l2 = QLabel('Peak: ' + str(OR['peak_zone_id']) + ' = ' + str(OR['peak_temp_c']) + 'C | Seal: ' + str(OR['thermal_cal_seal']))\n"
                "l2.setStyleSheet('background:#1e293b;color:#38bdf8;padding:8px;')\n"
                "b1 = QPushButton('Filter Hotspot Callouts'); b1.setStyleSheet('background:#2563eb;color:#ffffff;padding:8px;')\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1)\n"
                "w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "snap.py").write_text(snap_py, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/snap.py\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_5 Floating-Dock Photobombing): Floating docks raised above ThermalBoard occlude root capture."""
    solve_role("dock_cam_engineer", workspace_map, port, careful_conc=False)
    solve_role("thermal_snap_engineer", workspace_map, port, careful_conc=False)
    ws_b = workspace_map["thermal_snap_engineer"]
    occlude_sh = (
        "export DISPLAY=:99; "
        "for dw in $(xdotool search --onlyvisible --name 'Dock'); do wmctrl -i -a \"$dw\" 2>/dev/null || true; done; "
        "sleep 0.3; "
        f"import -window root -crop 900x620+580+90 +repage {ws_b}/pcb_thermal_clean.png"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", occlude_sh], check=True, capture_output=True, timeout=15)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

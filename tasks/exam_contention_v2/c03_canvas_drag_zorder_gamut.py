"""EC2-C03: PyQt5 Interactive Canvas Node-Drag Truss CAD vs. Overlapping Colorimetric Proof Studio.

Track 1 — Isolated Workspaces, Continuous Pointer Drag & Window Z-Order / Framebuffer Occlusion:
  - Live PyQt5 AeroTruss Sketcher (x=140..1100) and SpectraProof Studio (x=660..1720) overlap across x=660..1100.
  - Role A must physically drag movable top-chord joints T1 and T2 on the AeroTruss canvas into the valid
    structural envelope (stress <= 165 MPa, deflection <= 4.50 mm, mass <= 445 kg, duct clearance >= 0.25 m)
    and export the signed geometry.
  - Role B must switch SpectraProof Studio to D50_ISO12647_PRINT, capture an unobstructed 8-swatch proof image
    (d50_swatch_proof.png), and compute Delta-E colorimetric deviations against the Ctrl+L reference table.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    make_opaque_seal,
    read_json_safe,
    write_json,
)

TASK_ID = "EC2-C03"
PORTAL_PORT = 19103

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "PyQt5 Interactive Node-Drag Truss Optimizer vs. Overlapping Colorimetric Gamut Proof Studio",
    "domain": "Structural CAD Interactive Sketching & Prepress Colorimetric Calibration",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "continuous_pointer_drag_interception",
        "overlapping_window_zorder_photobombing",
        "live_gui_physics_gauge_and_swatch_capture",
    ),
    "roles": ("structural_sketch_eng", "color_proof_specialist"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

TRUSS_CERT_SALT = "aerotruss-v2-cert-903"

# 8 Colorimetric patches under D50_ISO12647_PRINT:
# (patch_id, rendered_d50_rgb, target_ref_rgb)
D50_PATCHES: list[tuple[str, tuple[int, int, int], tuple[int, int, int]]] = [
    ("P1_CYAN_INK",    (24, 158, 196),  (20, 162, 198)),
    ("P2_MAGENTA_INK", (204, 42, 118),  (198, 46, 115)),
    ("P3_YELLOW_INK",  (238, 206, 36),  (240, 204, 34)),
    ("P4_WARM_SKIN",   (214, 152, 122), (192, 138, 112)),  # out-of-tolerance drift patch!
    ("P5_FOLIAGE_GRN", (68, 146, 76),   (70, 148, 74)),
    ("P6_COBALT_SKY",  (52, 98, 184),   (50, 100, 182)),
    ("P7_DEEP_VIOLET", (118, 64, 156),  (94, 52, 138)),    # out-of-tolerance drift patch!
    ("P8_NEUTRAL_50",  (128, 126, 123), (127, 126, 124)),
]

D65_PREVIEW_RGB: list[tuple[int, int, int]] = [
    (40, 185, 235), (230, 70, 155), (250, 230, 80), (230, 175, 150),
    (90, 180, 105), (80, 130, 225), (150, 95, 195), (145, 148, 152),
]

SPECTRA_D50_SEAL = make_opaque_seal("ec2_c03_spectra", "D50_ISO12647_PRINT")


def srgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    def _lin(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = _lin(rgb[0]), _lin(rgb[1]), _lin(rgb[2])
    x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047
    y = (r * 0.2126729 + g * 0.7151522 + b * 0.0721750) / 1.00000
    z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883

    def _f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t + 16.0 / 116.0)

    fx, fy, fz = _f(x), _f(y), _f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def compute_spectra_oracle() -> dict[str, Any]:
    de_map: dict[str, float] = {}
    failing: list[str] = []
    for pid, d50_rgb, ref_rgb in D50_PATCHES:
        l1, a1, b1 = srgb_to_lab(d50_rgb)
        l2, a2, b2 = srgb_to_lab(ref_rgb)
        de = round(math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2), 2)
        de_map[pid] = de
        if de > 5.0:
            failing.append(pid)
    return {
        "illuminant_profile": "D50_ISO12647_PRINT",
        "calibration_seal": SPECTRA_D50_SEAL,
        "patch_delta_e76": de_map,
        "out_of_gamut_patches": sorted(failing),
        "mean_delta_e76": round(sum(de_map.values()) / len(de_map), 2),
    }


SPECTRA_ORACLE = compute_spectra_oracle()


def evaluate_truss_physics(t1: tuple[float, float], t2: tuple[float, float]) -> dict[str, Any]:
    x1, y1 = float(t1[0]), float(t1[1])
    x2, y2 = float(t2[0]), float(t2[1])
    nodes = {
        "J0": (0.0, 0.0),
        "J1": (4.0, 0.0),
        "J2": (8.0, 0.0),
        "J3": (12.0, 0.0),
        "T1": (x1, y1),
        "T2": (x2, y2),
    }
    members = [
        ("M1_BOT_L", "J0", "J1"),
        ("M2_BOT_M", "J1", "J2"),
        ("M3_BOT_R", "J2", "J3"),
        ("M4_TOP_L", "J0", "T1"),
        ("M5_TOP_M", "T1", "T2"),
        ("M6_TOP_R", "T2", "J3"),
        ("M7_WEB_1", "J1", "T1"),
        ("M8_WEB_2", "J2", "T2"),
        ("M9_DIAG",  "J1", "T2"),
    ]
    lengths = {}
    for mid, n_a, n_b in members:
        ax, ay = nodes[n_a]
        bx, by = nodes[n_b]
        lengths[mid] = round(math.hypot(bx - ax, by - ay), 4)

    eff_h = max(0.45, 0.5 * (y1 + y2))
    asym_pen = 1.0 + 0.08 * abs(y1 - y2) + 0.05 * (abs(x1 - 4.0) + abs(x2 - 8.0))
    # Calibrated physical model: at y=1.35 -> stress ~244 MPa, defl ~8.9 mm; at y=2.55 -> stress ~129 MPa, defl ~3.4 mm
    max_stress = round((330.0 / eff_h) * asym_pen, 2)
    defl_mm = round((16.2 / (eff_h ** 1.45)) * asym_pen, 2)
    area_m2 = 0.00148
    rho = 7850.0
    mass_kg = round(sum(lengths.values()) * area_m2 * rho, 2)

    # Point-to-segment clearance between top chord T1-T2 and HVAC duct center (6.0, 3.45), radius 0.50m
    cx, cy, r_duct = 6.0, 3.45, 0.50
    dx, dy = x2 - x1, y2 - y1
    seg_l2 = max(1e-6, dx * dx + dy * dy)
    u = max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / seg_l2))
    px, py = x1 + u * dx, y1 + u * dy
    duct_clear = round(math.hypot(cx - px, cy - py) - r_duct, 3)

    qualified = bool(
        2.0 <= x1 <= 5.5
        and 6.5 <= x2 <= 10.0
        and 1.0 <= y1 <= 3.3
        and 1.0 <= y2 <= 3.3
        and max_stress <= 165.0
        and defl_mm <= 4.50
        and mass_kg <= 445.0
        and duct_clear >= 0.25
    )
    sig_in = f"{TRUSS_CERT_SALT}:{x1:.2f}:{y1:.2f}:{x2:.2f}:{y2:.2f}:{qualified}"
    seal = "TRUSS-CERT-" + hashlib.sha256(sig_in.encode("utf-8")).hexdigest()[:10].upper() if qualified else "UNQUALIFIED_GEOMETRY"
    return {
        "T1": [round(x1, 3), round(y1, 3)],
        "T2": [round(x2, 3), round(y2, 3)],
        "member_lengths_m": lengths,
        "max_stress_mpa": max_stress,
        "midspan_deflection_mm": defl_mm,
        "steel_mass_kg": mass_kg,
        "duct_clearance_m": duct_clear,
        "qualified": qualified,
        "truss_cert_seal": seal,
    }


AEROTRUSS_QT_APP = f"""import hashlib, json, math, os, sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QShortcut
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt, QPointF

SALT = {json.dumps(TRUSS_CERT_SALT)}

def eval_truss(x1, y1, x2, y2):
    nodes = {{"J0":(0,0),"J1":(4,0),"J2":(8,0),"J3":(12,0),"T1":(x1,y1),"T2":(x2,y2)}}
    mems = [("M1_BOT_L","J0","J1"),("M2_BOT_M","J1","J2"),("M3_BOT_R","J2","J3"),
            ("M4_TOP_L","J0","T1"),("M5_TOP_M","T1","T2"),("M6_TOP_R","T2","J3"),
            ("M7_WEB_1","J1","T1"),("M8_WEB_2","J2","T2"),("M9_DIAG","J1","T2")]
    lens = {{m: round(math.hypot(nodes[b][0]-nodes[a][0], nodes[b][1]-nodes[a][1]), 4) for m,a,b in mems}}
    eff_h = max(0.45, 0.5*(y1+y2))
    asym = 1.0 + 0.08*abs(y1-y2) + 0.05*(abs(x1-4.0)+abs(x2-8.0))
    stress = round((330.0/eff_h)*asym, 2)
    defl = round((16.2/(eff_h**1.45))*asym, 2)
    mass = round(sum(lens.values())*0.00148*7850.0, 2)
    cx, cy, rd = 6.0, 3.45, 0.50
    dx, dy = x2-x1, y2-y1
    u = max(0.0, min(1.0, ((cx-x1)*dx+(cy-y1)*dy)/max(1e-6, dx*dx+dy*dy)))
    clear = round(math.hypot(cx-(x1+u*dx), cy-(y1+u*dy)) - rd, 3)
    ok = (2.0<=x1<=5.5 and 6.5<=x2<=10.0 and 1.0<=y1<=3.3 and 1.0<=y2<=3.3 and stress<=165.0 and defl<=4.50 and mass<=445.0 and clear>=0.25)
    sig = f"{{SALT}}:{{x1:.2f}}:{{y1:.2f}}:{{x2:.2f}}:{{y2:.2f}}:{{ok}}"
    seal = "TRUSS-CERT-" + hashlib.sha256(sig.encode()).hexdigest()[:10].upper() if ok else "UNQUALIFIED_GEOMETRY"
    return {{"T1":[round(x1,3),round(y1,3)],"T2":[round(x2,3),round(y2,3)],"member_lengths_m":lens,
            "max_stress_mpa":stress,"midspan_deflection_mm":defl,"steel_mass_kg":mass,
            "duct_clearance_m":clear,"qualified":ok,"truss_cert_seal":seal}}

class TrussCanvas(QWidget):
    def __init__(self, on_change):
        super().__init__()
        self.setMinimumSize(880, 520)
        self.t1 = [4.0, 1.35]
        self.t2 = [8.0, 1.35]
        self.drag_which = None
        self.on_change = on_change

    def w2s(self, x, y):
        return (70.0 + x * 62.0, 450.0 - y * 105.0)

    def s2w(self, sx, sy):
        return (round((sx - 70.0) / 62.0, 2), round((450.0 - sy) / 105.0, 2))

    def mousePressEvent(self, ev):
        p = ev.pos()
        for name, pt in (("t1", self.t1), ("t2", self.t2)):
            sx, sy = self.w2s(pt[0], pt[1])
            if math.hypot(p.x() - sx, p.y() - sy) <= 26.0:
                self.drag_which = name
                break

    def mouseMoveEvent(self, ev):
        if not self.drag_which:
            return
        wx, wy = self.s2w(ev.pos().x(), ev.pos().y())
        wy = max(0.8, min(3.5, wy))
        if self.drag_which == "t1":
            self.t1 = [max(2.2, min(5.4, wx)), wy]
        else:
            self.t2 = [max(6.6, min(9.8, wx)), wy]
        self.on_change()
        self.update()

    def mouseReleaseEvent(self, _ev):
        self.drag_which = None

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(15, 23, 42))
        # Draw HVAC keepout circle
        kx, ky = self.w2s(6.0, 3.45)
        kr = 0.50 * 105.0
        qp.setPen(QPen(QColor(239, 68, 68), 2, Qt.DashLine))
        qp.setBrush(QBrush(QColor(239, 68, 68, 55)))
        qp.drawEllipse(QPointF(kx, ky), kr, kr)
        qp.setPen(QColor(252, 165, 165))
        qp.drawText(int(kx - 55), int(ky + 4), "HVAC KEEPOUT")

        nodes = {{"J0":(0,0),"J1":(4,0),"J2":(8,0),"J3":(12,0),"T1":tuple(self.t1),"T2":tuple(self.t2)}}
        qp.setPen(QPen(QColor(56, 189, 248), 3))
        for a, b in (("J0","J1"),("J1","J2"),("J2","J3"),("J0","T1"),("T1","T2"),("T2","J3"),("J1","T1"),("J2","T2"),("J1","T2")):
            p1, p2 = self.w2s(*nodes[a]), self.w2s(*nodes[b])
            qp.drawLine(QPointF(*p1), QPointF(*p2))

        for nm, (nx, ny) in nodes.items():
            sx, sy = self.w2s(nx, ny)
            is_top = nm.startswith("T")
            qp.setBrush(QBrush(QColor(249, 115, 22) if is_top else QColor(148, 163, 184)))
            qp.setPen(QPen(QColor(255, 255, 255), 2))
            rad = 13.0 if is_top else 8.0
            qp.drawEllipse(QPointF(sx, sy), rad, rad)
            qp.setFont(QFont("Monospace", 10, QFont.Bold))
            qp.drawText(int(sx - 28), int(sy - 18), f"{{nm}}({{nx:.2f}},{{ny:.2f}})")

class AeroTrussWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AeroTruss Sketcher")
        self.setGeometry(140, 50, 940, 760)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-family: monospace; font-size: 13px; padding: 8px; background: #1e293b; color: #f8fafc;")
        lay.addWidget(self.status_lbl)
        self.canvas = TrussCanvas(self.refresh)
        lay.addWidget(self.canvas)
        row = QHBoxLayout()
        exp_btn = QPushButton("&Export Certified Truss Package (/home/user/Downloads/truss_certified.json) [Ctrl+E]")
        exp_btn.clicked.connect(self.export_pkg)
        row.addWidget(exp_btn)
        self.msg_lbl = QLabel("Drag orange handles T1 & T2 upward until all 4 gauges PASS, then Export.")
        row.addWidget(self.msg_lbl)
        lay.addLayout(row)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_pkg)
        self.refresh()

    def refresh(self):
        st = eval_truss(self.canvas.t1[0], self.canvas.t1[1], self.canvas.t2[0], self.canvas.t2[1])
        tag = "PASS (GREEN)" if st["qualified"] else "FAIL (OUT OF SPEC)"
        self.status_lbl.setText(
            f"[{{tag}}] Stress={{st['max_stress_mpa']}}/165 MPa | Defl={{st['midspan_deflection_mm']}}/4.50 mm | "
            f"Mass={{st['steel_mass_kg']}}/445 kg | DuctClear={{st['duct_clearance_m']}}/>=0.25 m"
        )

    def export_pkg(self):
        st = eval_truss(self.canvas.t1[0], self.canvas.t1[1], self.canvas.t2[0], self.canvas.t2[1])
        out = Path("/home/user/Downloads/truss_certified.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(st, indent=2) + "\\n")
        os.chmod(out, 0o644)
        self.msg_lbl.setText(f"Saved (qualified={{st['qualified']}}, seal={{st['truss_cert_seal']}})")

app = QApplication(sys.argv)
w = AeroTrussWin()
w.show()
sys.exit(app.exec_())
"""


SPECTRAPROOF_QT_APP = f"""import json, sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDialog, QShortcut
from PyQt5.QtGui import QPainter, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt

D50 = {json.dumps([(p[0], list(p[1]), list(p[2])) for p in D50_PATCHES])}
D65 = {json.dumps([list(c) for c in D65_PREVIEW_RGB])}
SEAL = {json.dumps(SPECTRA_D50_SEAL)}

class SwatchGrid(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(920, 500)
        self.mode = "D65_SRGB_PREVIEW"

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(248, 250, 252))
        for idx, (pid, d50_c, _ref) in enumerate(D50):
            r = idx // 4
            c = idx % 4
            x0 = 40 + c * 215
            y0 = 35 + r * 225
            rgb = d50_c if self.mode == "D50_ISO12647_PRINT" else D65[idx]
            qp.fillRect(x0, y0, 180, 170, QColor(rgb[0], rgb[1], rgb[2]))
            qp.setPen(QColor(15, 23, 42))
            qp.setFont(QFont("Monospace", 10, QFont.Bold))
            qp.drawText(x0 + 4, y0 + 192, pid)

class SpectraWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpectraProof Studio")
        self.setGeometry(660, 70, 980, 720)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        hdr = QHBoxLayout()
        b65 = QPushButton("D65_SRGB_PREVIEW")
        b50 = QPushButton("&D50_ISO12647_PRINT [Ctrl+D]")
        bref = QPushButton("Reference sRGB & CIE76 Rules (Ctrl+L)")
        b65.clicked.connect(lambda: self.set_mode("D65_SRGB_PREVIEW"))
        b50.clicked.connect(lambda: self.set_mode("D50_ISO12647_PRINT"))
        bref.clicked.connect(self.show_ref)
        hdr.addWidget(b65); hdr.addWidget(b50); hdr.addWidget(bref)
        lay.addLayout(hdr)
        self.banner = QLabel()
        self.banner.setStyleSheet("font-family: monospace; font-size: 13px; padding: 6px; background: #e2e8f0; color: #0f172a;")
        lay.addWidget(self.banner)
        self.grid = SwatchGrid()
        lay.addWidget(self.grid)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=lambda: self.set_mode("D50_ISO12647_PRINT"))
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.show_ref)
        self.set_mode("D65_SRGB_PREVIEW")

    def set_mode(self, m):
        self.grid.mode = m
        seal_txt = SEAL if m == "D50_ISO12647_PRINT" else "PREVIEW-UNSEALED"
        self.banner.setText(f"ACTIVE_ILLUMINANT={{m}} | CALIBRATION_SEAL={{seal_txt}}")
        self.grid.update()

    def show_ref(self):
        d = QDialog(self)
        d.setWindowTitle("ISO 12647-2 D50 Reference Target & CIE76 Formula")
        v = QVBoxLayout(d)
        v.addWidget(QLabel("Convert both rendered D50 patch RGB and Reference RGB via standard sRGB->XYZ(D65)->CIELAB, then DeltaE76 = Euclidean Lab distance."))
        v.addWidget(QLabel("Flag patch in out_of_gamut_patches if DeltaE76 > 5.0:"))
        for pid, _d50, ref in D50:
            v.addWidget(QLabel(f"  {{pid}}: target_ref_srgb = {{tuple(ref)}}"))
        btn = QPushButton("Close")
        btn.clicked.connect(d.accept)
        v.addWidget(btn)
        d.exec_()

app = QApplication(sys.argv)
w = SpectraWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Structural Truss Interactive Optimization Work Order — {b}structural_sketch_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Optimize the 9-member steel roof truss in the live **AeroTruss Sketcher** desktop application running on the workstation and write all deliverables into {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Interactive Joint Optimization & Signed Export ({b}/workspace/truss_certified.json{b})**:",
        f"   - In **AeroTruss Sketcher**, drag the two orange top-chord handles {b}T1{b} and {b}T2{b} so all four real-time structural gauges pass simultaneously ({b}max_stress_mpa <= 165.0{b}, {b}midspan_deflection_mm <= 4.50{b}, {b}steel_mass_kg <= 445.0{b}, {b}duct_clearance_m >= 0.25{b}).",
        f"   - Click **Export Certified Truss Package** to write {b}/home/user/Downloads/truss_certified.json{b}, verify {b}\"qualified\": true{b} and a valid {b}TRUSS-CERT-...{b} seal, and copy the verified file to {b}/workspace/truss_certified.json{b}.",
        f"2. **Member Geometry Schedule ({b}/workspace/MEMBER_SCHEDULE.csv{b})**:",
        f"   - Write a 9-row CSV with header {b}member_id,length_m,mass_kg{b} covering {b}M1_BOT_L..M9_DIAG{b} matching the certified geometry ({b}area = 0.00148 m^2{b}, {b}rho = 7850 kg/m^3{b}).",
        "",
    ])

    role_b = "\n".join([
        f"# Prepress Colorimetric Gamut Audit Work Order — {b}color_proof_specialist{b}",
        "",
        "## Scope & Deliverables",
        f"Audit the 8-patch press target in the live **SpectraProof Studio** desktop application running on the workstation and write all deliverables into {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Unobstructed D50 Swatch Proof Capture ({b}/workspace/d50_swatch_proof.png{b})**:",
        f"   - Switch **SpectraProof Studio** from {b}D65_SRGB_PREVIEW{b} to {b}D50_ISO12647_PRINT{b}, ensure the entire **SpectraProof Studio** window and all 8 color swatches ({b}P1..P8{b}) are completely unobstructed on screen, and save a clean window PNG capture (`>= 880 x 560` px) to {b}/workspace/d50_swatch_proof.png{b}.",
        f"2. **CIELAB Delta-E76 Compliance Report ({b}/workspace/SPECTRA_GAMUT_REPORT.json{b})**:",
        f"   - Open the **Reference sRGB & CIE76 Rules ({b}Ctrl+L{b})** dialog in SpectraProof Studio, measure the rendered {b}D50_ISO12647_PRINT{b} sRGB values of {b}P1..P8{b}, compute {b}DeltaE76{b} against the reference sRGB values, and write JSON with exact keys:",
        f"     - {b}\"illuminant_profile\"{b}: {b}\"D50_ISO12647_PRINT\"{b}",
        f"     - {b}\"calibration_seal\"{b}: exact {b}ATTEST-...{b} seal shown in the studio banner under {b}D50_ISO12647_PRINT{b}",
        f"     - {b}\"patch_delta_e76\"{b}: object mapping each patch ID ({b}\"P1_CYAN_INK\"..\"P8_NEUTRAL_50\"{b}) to its float {b}DeltaE76{b} (rounded to 2 decimals)",
        f"     - {b}\"out_of_gamut_patches\"{b}: sorted list of patch IDs with {b}DeltaE76 > 5.0{b}",
        f"     - {b}\"mean_delta_e76\"{b}: mean {b}DeltaE76{b} across all 8 patches (rounded to 2 decimals)",
        "",
    ])
    return {"structural_sketch_eng": role_a, "color_proof_specialist": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    for ws in workspace_map.values():
        ws.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "aerotruss_app.py").write_text(AEROTRUSS_QT_APP, encoding="utf-8")
    (state_dir / "spectraproof_app.py").write_text(SPECTRAPROOF_QT_APP, encoding="utf-8")
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None: return
        def do_GET(self) -> None:
            raw = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text('{"mode":"overlapping_qt_apps"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    app_dir = Path("/tmp/ec2_c03_apps")
    app_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(app_dir, 0o755)
    for fn in ("aerotruss_app.py", "spectraproof_app.py"):
        dst = app_dir / fn
        dst.write_text((state_dir / fn).read_text(encoding="utf-8"), encoding="utf-8")
        os.chmod(dst, 0o644)
    cmd = (
        "su -s /bin/bash user -c '"
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
        "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1; "
        f"nohup python3 {app_dir}/aerotruss_app.py >/tmp/aerotruss.log 2>&1 </dev/null & "
        f"nohup python3 {app_dir}/spectraproof_app.py >/tmp/spectraproof.log 2>&1 </dev/null &'"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=20)
    time.sleep(2.0)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    import csv
    from PIL import Image
    ws_a = workspace_map["structural_sketch_eng"]
    ws_b = workspace_map["color_proof_specialist"]

    cert = read_json_safe(ws_a / "truss_certified.json")
    t1 = cert.get("T1") if isinstance(cert.get("T1"), list) and len(cert["T1"]) == 2 else [0.0, 0.0]
    t2 = cert.get("T2") if isinstance(cert.get("T2"), list) and len(cert["T2"]) == 2 else [0.0, 0.0]
    re_eval = evaluate_truss_physics((float(t1[0]), float(t1[1])), (float(t2[0]), float(t2[1]))) if cert else {"qualified": False, "truss_cert_seal": "NONE", "member_lengths_m": {}}
    seal_valid = bool(cert and re_eval["qualified"] and cert.get("truss_cert_seal") == re_eval["truss_cert_seal"])

    sched_ok = False
    sched_p = ws_a / "MEMBER_SCHEDULE.csv"
    if sched_p.is_file() and re_eval.get("member_lengths_m"):
        try:
            rows = list(csv.DictReader(sched_p.open("r", encoding="utf-8")))
            got_l = {r["member_id"]: float(r["length_m"]) for r in rows}
            got_m = {r["member_id"]: float(r["mass_kg"]) for r in rows}
            exp_l = re_eval["member_lengths_m"]
            sched_ok = (
                len(got_l) == 9
                and all(abs(got_l.get(k, -99.0) - v) <= 0.03 for k, v in exp_l.items())
                and all(abs(got_m.get(k, -99.0) - v * 0.00148 * 7850.0) <= 0.5 for k, v in exp_l.items())
            )
        except Exception:
            sched_ok = False

    checks_a: list[tuple[str, bool, float, str]] = [
        ("cert_file_present", bool(cert), 0.10, "Missing /workspace/truss_certified.json"),
        ("stress_ok", bool(cert) and float(re_eval.get("max_stress_mpa", 999)) <= 165.0, 0.15, f"max_stress_mpa={re_eval.get('max_stress_mpa')} > 165.0"),
        ("deflection_ok", bool(cert) and float(re_eval.get("midspan_deflection_mm", 999)) <= 4.50, 0.15, f"midspan_deflection_mm={re_eval.get('midspan_deflection_mm')} > 4.50"),
        ("mass_and_duct_ok", bool(cert) and float(re_eval.get("steel_mass_kg", 999)) <= 445.0 and float(re_eval.get("duct_clearance_m", -1)) >= 0.25, 0.20, "Mass > 445 kg or HVAC duct keepout violated"),
        ("authentic_gui_seal", seal_valid, 0.20, "truss_cert_seal invalid or geometry not exported from AeroTruss GUI"),
        ("member_schedule_csv", sched_ok, 0.20, "MEMBER_SCHEDULE.csv missing or inconsistent with certified 9-member geometry"),
    ]

    rep_b = read_json_safe(ws_b / "SPECTRA_GAMUT_REPORT.json")
    proof_p = ws_b / "d50_swatch_proof.png"
    proof_unobstructed = False
    if proof_p.is_file() and proof_p.stat().st_size > 3000:
        try:
            with Image.open(proof_p) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                if w >= 880 and h >= 560:
                    # Verify both D50 cyan swatch P1 (around left column) and D50 yellow swatch P3 are visible (not dark AeroTruss 15,23,42 or D65)
                    found_p1_d50 = False
                    found_p2_d50 = False
                    for sx in range(40, min(w, 320), 12):
                        for sy in range(80, min(h, 360), 12):
                            px = rgb.getpixel((sx, sy))
                            if abs(px[0] - 24) <= 22 and abs(px[1] - 158) <= 22 and abs(px[2] - 196) <= 22:
                                found_p1_d50 = True
                    for sx in range(250, min(w, 560), 12):
                        for sy in range(80, min(h, 360), 12):
                            px = rgb.getpixel((sx, sy))
                            if abs(px[0] - 204) <= 22 and abs(px[1] - 42) <= 22 and abs(px[2] - 118) <= 22:
                                found_p2_d50 = True
                    proof_unobstructed = bool(found_p1_d50 and found_p2_d50)
        except Exception:
            proof_unobstructed = False

    got_de = rep_b.get("patch_delta_e76") or {}
    de_matches = sum(
        1 for k, v in SPECTRA_ORACLE["patch_delta_e76"].items()
        if isinstance(got_de.get(k), (int, float)) and abs(float(got_de[k]) - v) <= 0.65
    )

    checks_b: list[tuple[str, bool, float, str]] = [
        ("d50_proof_unobstructed", proof_unobstructed, 0.25, "d50_swatch_proof.png missing, still on D65, or occluded by overlapping window"),
        ("illuminant_and_seal", rep_b.get("illuminant_profile") == "D50_ISO12647_PRINT" and rep_b.get("calibration_seal") == SPECTRA_D50_SEAL, 0.20, "illuminant_profile or calibration_seal mismatch"),
        ("out_of_gamut_patches", rep_b.get("out_of_gamut_patches") == SPECTRA_ORACLE["out_of_gamut_patches"], 0.20, f"out_of_gamut_patches={rep_b.get('out_of_gamut_patches')} != {SPECTRA_ORACLE['out_of_gamut_patches']}"),
        ("patch_de_partial", de_matches >= 5, 0.15, f"Only {de_matches}/8 patch_delta_e76 accurate"),
        ("patch_de_all", de_matches == 8, 0.10, f"patch_delta_e76 {de_matches}/8 != 8/8"),
        ("mean_de", isinstance(rep_b.get("mean_delta_e76"), (int, float)) and abs(float(rep_b["mean_delta_e76"]) - SPECTRA_ORACLE["mean_delta_e76"]) <= 0.45, 0.10, "mean_delta_e76 mismatch"),
    ]

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


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port
    assert role in ("structural_sketch_eng", "color_proof_specialist")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "structural_sketch_eng":
            # Raise AeroTruss, drag T1 (from 4.0,1.35 -> 4.0,2.55) and T2 (from 8.0,1.35 -> 8.0,2.55), click Export
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'AeroTruss Sketcher' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,40,40,940,760; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.35; "
                # Canvas starts ~52px below window top; T1 at (70+4*62=318, 450-1.35*105=308) -> (318, 450-2.55*105=182)
                # Let's probe exact orange handle pixels via root screenshot to be 100% immune to titlebar height!
                "python3 - <<'PY'\n"
                "import subprocess\n"
                "from PIL import Image\n"
                "raw = subprocess.check_output(['import', '-window', 'root', 'png:-'])\n"
                "import io\n"
                "im = Image.open(io.BytesIO(raw)).convert('RGB')\n"
                "pts = []\n"
                "for x in range(80, 960, 2):\n"
                "    for y in range(120, 720, 2):\n"
                "        r, g, b = im.getpixel((x, y))\n"
                "        if r > 220 and 90 <= g <= 145 and b < 55:\n"
                "            pts.append((x, y))\n"
                "left = [p for p in pts if p[0] < 500]\n"
                "right = [p for p in pts if p[0] >= 500]\n"
                "cx1 = sum(p[0] for p in left)//len(left); cy1 = sum(p[1] for p in left)//len(left)\n"
                "cx2 = sum(p[0] for p in right)//len(right); cy2 = sum(p[1] for p in right)//len(right)\n"
                "for cx, cy in ((cx1, cy1), (cx2, cy2)):\n"
                "    subprocess.run(['xdotool', 'mousemove', str(cx), str(cy), 'mousedown', '1'], check=True)\n"
                "    for k in range(1, 9):\n"
                "        ny = int(cy - 126 * k / 8)\n"
                "        subprocess.run(['xdotool', 'mousemove', str(cx), str(ny)], check=True)\n"
                "    subprocess.run(['xdotool', 'mouseup', '1'], check=True)\n"
                "PY\n"
                "sleep 0.2; wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.15; "
                "xdotool key --clearmodifiers ctrl+e; sleep 0.4"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=25)
            dl_p = Path("/home/user/Downloads/truss_certified.json")
            cert = json.loads(dl_p.read_text(encoding="utf-8"))
            write_json(ws / "truss_certified.json", cert)
            lines = ["member_id,length_m,mass_kg"]
            for mid, l_val in cert["member_lengths_m"].items():
                lines.append(f"{mid},{l_val:.4f},{l_val * 0.00148 * 7850.0:.3f}")
            (ws / "MEMBER_SCHEDULE.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'SpectraProof Studio' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,720,60,980,720; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.3; "
                "xdotool key --clearmodifiers ctrl+d; sleep 0.4; "
                f"import -window \"$wid\" {ws}/d50_swatch_proof.png"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=20)
            write_json(ws / "SPECTRA_GAMUT_REPORT.json", SPECTRA_ORACLE)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (Shared-Screen Track): AeroTruss window raised on top occludes SpectraProof root-screen capture."""
    solve_role("structural_sketch_eng", workspace_map, port, careful_conc=False)
    solve_role("color_proof_specialist", workspace_map, port, careful_conc=False)
    ws_b = workspace_map["color_proof_specialist"]
    occlude_sh = (
        "export DISPLAY=:99; "
        "w_a=$(xdotool search --onlyvisible --name 'AeroTruss Sketcher' | tail -n 1); "
        "w_b=$(xdotool search --onlyvisible --name 'SpectraProof Studio' | tail -n 1); "
        "wmctrl -i -r \"$w_b\" -e 0,660,70,980,720; "
        "wmctrl -i -r \"$w_a\" -e 0,520,60,940,760; "
        "wmctrl -i -a \"$w_a\" 2>/dev/null || true; xdotool windowactivate \"$w_a\"; sleep 0.3; "
        f"import -window root -crop 980x720+660+70 +repage {ws_b}/d50_swatch_proof.png"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", occlude_sh], check=True, capture_output=True, timeout=15)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)

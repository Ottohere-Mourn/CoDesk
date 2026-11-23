"""RBS3-03: Single-Instance Mutable VectorForge MDI CAD (`Alt+1` HVAC vs `Alt+2` Busbar) + Coupled Stack.

Grounded in OSW2-P3 WPS MDI (1.0 -> 0.0) & OSW2-P4 GIMP Single-Instance (1.0 -> 0.90 -> 0.00) + LAW_6/7/8:
  - ONE single live PyQt5 `VectorForge MEP Studio` process holds both sibling layers (`[Alt+1] HVAC_Plenum`
    and `[Alt+2] Busbar_Riser`), a global `MM`/`INCH` unit mode (`[U]`), and a cryptographically signed
    `Export Signed MEP Bundle (Ctrl+S)` action.
  - Cross-tab mouse drags mutate whichever layer is active, and `Total_Ceiling_Stack_mm` is coupled into a
    tight `[636.0, 644.0] mm` dual-lever band.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sqlite3
import subprocess
from typing import Any

from tasks.rb_osw2_synth_v3.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    build_grade_payload,
    read_json_safe,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS3-03"
PORTAL_PORT = 19503
VF_SALT = "vectorforge-mep-rbs303"
STACK_BAND_MM = (636.0, 644.0)

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Single-Instance Mutable VectorForge MDI (`Alt+1` HVAC vs `Alt+2` Busbar) & Coupled Ceiling Stack",
    "domain": "MEP Building Systems CAD Coordination (HVAC Plenum & Busbar Riser Single-Instance MDI)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING",
        "LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("hvac_plenum_eng", "busbar_riser_eng"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1080,
    "iso_role_timeout_s": 1080,
    "max_cua_calls": 42,
    "factory_blueprint": {
        "horizon_band": "non_saturated_coupled_contention",
        "total_subchecks": 40,
        "cli_bypass_resistance": 0.98,
        "role_a": {
            "slug": "hvac_plenum_eng",
            "est_role_seconds": 500.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "custom_2d_canvas_drag",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "busbar_riser_eng",
            "est_role_seconds": 500.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "custom_2d_canvas_drag",
                "iterative_keyboard_shortcuts",
            ],
        },
    },
}

X_STATIONS = [0, 1, 2, 3, 4]
HVAC_INIT_Y = [18.0, 42.0, 15.0, 44.0, 20.0]
HVAC_TGT_Y = [34.0, 20.0, 38.0, 22.0, 36.0]
BUS_INIT_Y = [40.0, 16.0, 43.0, 18.0, 41.0]
BUS_TGT_Y = [22.0, 38.0, 20.0, 36.0, 24.0]

# 8 HVAC zones -> active zones (`status='ACTIVE_SUPPLY'`) require max duct height = 290 mm (draft v0 had 315 mm from decommissioned zone)
HVAC_ZONES = [
    ("ZN-01", "ACTIVE_SUPPLY",  920, 260),
    ("ZN-02", "ACTIVE_SUPPLY", 1180, 285),
    ("ZN-03", "DECOMMISSIONED",1650, 315),
    ("ZN-04", "ACTIVE_SUPPLY", 1240, 290),
    ("ZN-05", "ACTIVE_SUPPLY",  880, 250),
    ("ZN-06", "DECOMMISSIONED",1590, 312),
    ("ZN-07", "ACTIVE_SUPPLY", 1100, 275),
    ("ZN-08", "ACTIVE_SUPPLY", 1040, 270),
]
TRUE_DUCT_BASE_MM = 290
TRUE_ACTIVE_CFM_SUM = sum(z[2] for z in HVAC_ZONES if z[1] == "ACTIVE_SUPPLY")

# 8 Busbar feeders -> active feeders (`status='ENERGIZED'`) require max tray height = 290 mm (draft v0 had 315 mm from retired feeder)
BUS_FEEDERS = [
    ("FD-01", "ENERGIZED",  630, 265),
    ("FD-02", "RETIRED",   1250, 315),
    ("FD-03", "ENERGIZED",  800, 290),
    ("FD-04", "ENERGIZED",  500, 250),
    ("FD-05", "RETIRED",   1180, 310),
    ("FD-06", "ENERGIZED",  720, 280),
    ("FD-07", "ENERGIZED",  680, 275),
    ("FD-08", "ENERGIZED",  590, 260),
]
TRUE_TRAY_BASE_MM = 290
TRUE_ENERGIZED_AMPS_SUM = sum(f[2] for f in BUS_FEEDERS if f[1] == "ENERGIZED")


def compute_bundle_state(
    hvac_y: list[float],
    bus_y: list[float],
    duct_mm: int,
    tray_mm: int,
    trim_a: int,
    trim_b: int,
) -> dict[str, Any]:
    rms_a = round(math.sqrt(sum((hvac_y[i] - HVAC_TGT_Y[i]) ** 2 for i in range(5)) / 5.0), 3)
    rms_b = round(math.sqrt(sum((bus_y[i] - BUS_TGT_Y[i]) ** 2 for i in range(5)) / 5.0), 3)
    stack_mm = duct_mm + tray_mm + trim_a + trim_b
    payload_str = (
        ":".join(f"{v:.1f}" for v in hvac_y)
        + "|"
        + ":".join(f"{v:.1f}" for v in bus_y)
        + f"|{duct_mm}:{tray_mm}:{trim_a}:{trim_b}"
    )
    sig = "VF-SIG-" + hashlib.sha256(f"{VF_SALT}:{payload_str}".encode("utf-8")).hexdigest()[:12].upper()
    return {
        "hvac_nodes_mm": [round(v, 1) for v in hvac_y],
        "busbar_nodes_mm": [round(v, 1) for v in bus_y],
        "hvac_rms_mm": rms_a,
        "busbar_rms_mm": rms_b,
        "duct_base_mm": int(duct_mm),
        "tray_base_mm": int(tray_mm),
        "damper_trim_mm": int(trim_a),
        "standoff_trim_mm": int(trim_b),
        "total_ceiling_stack_mm": int(stack_mm),
        "bundle_signature": sig,
    }


VECTORFORGE_QT_SOURCE = f"""import hashlib, json, math, os, sys
from pathlib import Path
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QShortcut, QSpinBox, QTabWidget, QVBoxLayout, QWidget
)

SALT = {json.dumps(VF_SALT)}
H_TGT = {json.dumps(HVAC_TGT_Y)}
B_TGT = {json.dumps(BUS_TGT_Y)}

class LayerCanvas(QWidget):
    def __init__(self, ys_init, tgts, handle_rgb, ring_rgb, on_chg):
        super().__init__()
        self.setMinimumSize(820, 390)
        self.ys = list(ys_init)
        self.tgts = list(tgts)
        self.hrgb = handle_rgb
        self.rrgb = ring_rgb
        self.drag_i = None
        self.on_chg = on_chg

    def i2x(self, i): return 120.0 + i * 145.0
    def v2y(self, v): return 350.0 - v * 6.0
    def y2v(self, sy): return round(max(8.0, min(52.0, (350.0 - sy) / 6.0)), 1)

    def mousePressEvent(self, ev):
        p = ev.pos()
        for i in range(5):
            if math.hypot(p.x() - self.i2x(i), p.y() - self.v2y(self.ys[i])) <= 24.0:
                self.drag_i = i
                break

    def mouseMoveEvent(self, ev):
        if self.drag_i is None:
            return
        self.ys[self.drag_i] = self.y2v(ev.pos().y())
        self.on_chg()
        self.update()

    def mouseReleaseEvent(self, _ev):
        self.drag_i = None

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), QColor(13, 20, 34))
        # Target polyline & target rings (LAW_7 visual target — never exposed as numeric target text!)
        qp.setPen(QPen(QColor(*self.rrgb), 3, Qt.DashLine))
        for i in range(4):
            qp.drawLine(QPointF(self.i2x(i), self.v2y(self.tgts[i])), QPointF(self.i2x(i + 1), self.v2y(self.tgts[i + 1])))
        qp.setBrush(QBrush(QColor(*self.rrgb)))
        for i in range(5):
            qp.drawEllipse(QPointF(self.i2x(i), self.v2y(self.tgts[i])), 8.0, 8.0)
        # Draggable user handles
        qp.setPen(QPen(QColor(*self.hrgb), 3))
        for i in range(4):
            qp.drawLine(QPointF(self.i2x(i), self.v2y(self.ys[i])), QPointF(self.i2x(i + 1), self.v2y(self.ys[i + 1])))
        qp.setBrush(QBrush(QColor(*self.hrgb)))
        qp.setPen(QPen(QColor(255, 255, 255), 2))
        qp.setFont(QFont("DejaVu Sans Mono", 9, QFont.Bold))
        for i in range(5):
            sx, sy = self.i2x(i), self.v2y(self.ys[i])
            qp.drawEllipse(QPointF(sx, sy), 12.0, 12.0)
            qp.drawText(int(sx - 20), int(sy - 16), f"N{{i}}")
        qp.end()

class VectorForgeWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VectorForge MEP Studio")
        self.setGeometry(60, 35, 980, 620)
        self.unit_mode = "MM"
        cw = QWidget(); v = QVBoxLayout(cw)
        self.hdr = QLabel()
        self.hdr.setStyleSheet("padding:7px;background:#0f172a;color:#38bdf8;font-weight:bold;")
        v.addWidget(self.hdr)
        self.tabs = QTabWidget()
        self.cv_a = LayerCanvas({json.dumps(HVAC_INIT_Y)}, H_TGT, (249, 115, 22), (16, 185, 129), self.refresh)
        self.cv_b = LayerCanvas({json.dumps(BUS_INIT_Y)}, B_TGT, (6, 182, 212), (245, 158, 11), self.refresh)
        self.tabs.addTab(self.cv_a, "[Alt+1] HVAC_Plenum_Layer")
        self.tabs.addTab(self.cv_b, "[Alt+2] Busbar_Riser_Layer")
        self.tabs.currentChanged.connect(lambda _: self.refresh())
        v.addWidget(self.tabs)

        ctrl = QHBoxLayout()
        self.sp_duct = QSpinBox(); self.sp_duct.setRange(220, 360); self.sp_duct.setValue(315)
        self.sp_trim_a = QSpinBox(); self.sp_trim_a.setRange(5, 50); self.sp_trim_a.setValue(12)
        self.sp_tray = QSpinBox(); self.sp_tray.setRange(220, 360); self.sp_tray.setValue(315)
        self.sp_trim_b = QSpinBox(); self.sp_trim_b.setRange(5, 50); self.sp_trim_b.setValue(12)
        for lbl_txt, sp in (("DuctBase:", self.sp_duct), ("DamperTrim:", self.sp_trim_a), ("TrayBase:", self.sp_tray), ("StandoffTrim:", self.sp_trim_b)):
            ctrl.addWidget(QLabel(lbl_txt))
            sp.valueChanged.connect(lambda _: self.refresh())
            ctrl.addWidget(sp)
        v.addLayout(ctrl)

        brow = QHBoxLayout()
        bt1 = QPushButton("Tab 1: &HVAC (Alt+1)"); bt1.clicked.connect(lambda: self.tabs.setCurrentIndex(0))
        bt2 = QPushButton("Tab 2: &Busbar (Alt+2)"); bt2.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        bu = QPushButton("Toggle &Unit MM/IN (U)"); bu.clicked.connect(self.toggle_unit)
        bp = QPushButton("&Preferences (Ctrl+P)"); bp.clicked.connect(self.open_prefs)
        bs = QPushButton("&Export Signed Bundle (Ctrl+S)"); bs.clicked.connect(self.export_bundle)
        for b in (bt1, bt2, bu, bp, bs):
            brow.addWidget(b)
        v.addLayout(brow)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Alt+1"), self, activated=lambda: self.tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Alt+2"), self, activated=lambda: self.tabs.setCurrentIndex(1))
        QShortcut(QKeySequence("F5"), self, activated=lambda: (self.sp_duct.setFocus(), self.sp_duct.selectAll()))
        QShortcut(QKeySequence("F6"), self, activated=lambda: (self.sp_trim_a.setFocus(), self.sp_trim_a.selectAll()))
        QShortcut(QKeySequence("F7"), self, activated=lambda: (self.sp_tray.setFocus(), self.sp_tray.selectAll()))
        QShortcut(QKeySequence("F8"), self, activated=lambda: (self.sp_trim_b.setFocus(), self.sp_trim_b.selectAll()))
        QShortcut(QKeySequence("U"), self, activated=self.toggle_unit)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.export_bundle)
        self.refresh()

    def toggle_unit(self):
        self.unit_mode = "INCH" if self.unit_mode == "MM" else "MM"
        self.refresh()

    def _state(self):
        hy, by = self.cv_a.ys, self.cv_b.ys
        ra = round(math.sqrt(sum((hy[i] - H_TGT[i])**2 for i in range(5)) / 5.0), 3)
        rb = round(math.sqrt(sum((by[i] - B_TGT[i])**2 for i in range(5)) / 5.0), 3)
        dm, tm = self.sp_duct.value(), self.sp_tray.value()
        ta, tb = self.sp_trim_a.value(), self.sp_trim_b.value()
        stk = dm + tm + ta + tb
        p_s = ":".join(f"{{x:.1f}}" for x in hy) + "|" + ":".join(f"{{x:.1f}}" for x in by) + f"|{{dm}}:{{tm}}:{{ta}}:{{tb}}"
        sig = "VF-SIG-" + hashlib.sha256(f"{{SALT}}:{{p_s}}".encode()).hexdigest()[:12].upper()
        return {{"hvac_nodes_mm":[round(x,1) for x in hy],"busbar_nodes_mm":[round(x,1) for x in by],
                "hvac_rms_mm":ra,"busbar_rms_mm":rb,"duct_base_mm":dm,"tray_base_mm":tm,
                "damper_trim_mm":ta,"standoff_trim_mm":tb,"total_ceiling_stack_mm":stk,
                "unit_mode":self.unit_mode,"bundle_signature":sig}}

    def refresh(self):
        st = self._state()
        self.hdr.setText(
            f"ActiveTab={{self.tabs.currentIndex()+1}} | Unit={{self.unit_mode}} | "
            f"HVAC_RMS={{st['hvac_rms_mm']}}mm | Bus_RMS={{st['busbar_rms_mm']}}mm | "
            f"Total_Ceiling_Stack={{st['total_ceiling_stack_mm']}}mm (target 636..644mm)"
        )

    def open_prefs(self):
        d = QDialog(self); d.setWindowTitle("Preferences"); d.setModal(True); d.resize(480, 210)
        dv = QVBoxLayout(d)
        dv.addWidget(QLabel("VectorForge MEP Clearance & Tolerance Rules"))
        dv.addWidget(QLabel("1. Fit Layer Nodes to target rings: RMS <= 2.5 mm; export requires Unit=MM."))
        dv.addWidget(QLabel("2. Coupled Ceiling Stack: DuctBase + TrayBase + DamperTrim + StandoffTrim in [636, 644] mm."))
        dv.addWidget(QLabel("3. Export writes /home/user/Downloads/vectorforge_bundle.json"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); dv.addWidget(bc)
        d.exec_()

    def export_bundle(self):
        st = self._state()
        if self.unit_mode != "MM":
            st["bundle_signature"] = "INVALID_UNIT_MUST_BE_MM"
        p = Path("/home/user/Downloads/vectorforge_bundle.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, indent=2) + "\\n")
        os.chmod(p, 0o666)
        self.hdr.setText(f"Exported bundle (Stack={{st['total_ceiling_stack_mm']}}mm, sig={{st['bundle_signature']}})")

app = QApplication(sys.argv)
w = VectorForgeWin(); w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# HVAC Plenum CAD Fitting & Ceiling Stack Coordination Work Order — {b}hvac_plenum_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the `HVAC_Plenum_Layer` (`Alt+1`) fitting and static-pressure duct sizing in the live **VectorForge MEP Studio** window on the desktop and `/workspace/mep/airflow_schedule.sqlite`.",
        "",
        "Deliverables:",
        f"1. **Database Reconciliation ({b}/workspace/mep/HVAC_REPORT.json{b})**:",
        "   - Query `/workspace/mep/airflow_schedule.sqlite` (`zones` table), include **only** `status='ACTIVE_SUPPLY'` zones (excluding `DECOMMISSIONED`), and compute `active_cfm_sum` (int: sum of `airflow_cfm`) and `required_duct_base_mm` (int: maximum `min_duct_height_mm` across `ACTIVE_SUPPLY` zones).",
        "   - Write `/workspace/mep/HVAC_REPORT.json` with keys `active_cfm_sum`, `required_duct_base_mm`, `damper_trim_mm`, `hvac_rms_mm`, and `bundle_signature`.",
        f"2. **Live VectorForge CAD Fitting & Signed Bundle ({b}/workspace/mep/vectorforge_bundle.json{b})**:",
        "   - In **VectorForge MEP Studio** (`Preferences` via `Ctrl+P`), ensure `Unit=MM`, align all 5 orange `HVAC_Plenum_Layer` (`Alt+1`) handles `N0..N4` onto their green target rings (`hvac_rms_mm <= 2.5`), set `DuctBase` to `required_duct_base_mm`, and adjust `DamperTrim` (`[5, 50]`) so `Total_Ceiling_Stack` lands inside `[636, 644]` mm without disturbing `Busbar_Riser_Layer`.",
        "   - Export `/home/user/Downloads/vectorforge_bundle.json` (`Ctrl+S`) and save the final signed JSON to `/workspace/mep/vectorforge_bundle.json`.",
        "",
    ])
    role_b = "\n".join([
        f"# Busbar Riser CAD Fitting & Ceiling Stack Coordination Work Order — {b}busbar_riser_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the `Busbar_Riser_Layer` (`Alt+2`) fitting and feeder tray sizing in the live **VectorForge MEP Studio** window on the desktop and `/workspace/mep/feeder_ampacity.sqlite`.",
        "",
        "Deliverables:",
        f"1. **Database Reconciliation ({b}/workspace/mep/BUSBAR_REPORT.json{b})**:",
        "   - Query `/workspace/mep/feeder_ampacity.sqlite` (`feeders` table), include **only** `status='ENERGIZED'` feeders (excluding `RETIRED`), and compute `energized_amps_sum` (int: sum of `ampacity_a`) and `required_tray_base_mm` (int: maximum `min_tray_height_mm` across `ENERGIZED` feeders).",
        "   - Write `/workspace/mep/BUSBAR_REPORT.json` with keys `energized_amps_sum`, `required_tray_base_mm`, `standoff_trim_mm`, `busbar_rms_mm`, and `bundle_signature`.",
        f"2. **Live VectorForge CAD Fitting & Signed Bundle ({b}/workspace/mep/vectorforge_bundle.json{b})**:",
        "   - In **VectorForge MEP Studio** (`Preferences` via `Ctrl+P`), ensure `Unit=MM`, align all 5 cyan `Busbar_Riser_Layer` (`Alt+2`) handles `N0..N4` onto their gold target rings (`busbar_rms_mm <= 2.5`), set `TrayBase` to `required_tray_base_mm`, and adjust `StandoffTrim` (`[5, 50]`) so `Total_Ceiling_Stack` lands inside `[636, 644]` mm without disturbing `HVAC_Plenum_Layer`.",
        "   - Export `/home/user/Downloads/vectorforge_bundle.json` (`Ctrl+S`) and save the final signed JSON to `/workspace/mep/vectorforge_bundle.json`.",
        "",
    ])
    return {"hvac_plenum_eng": role_a, "busbar_riser_eng": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    mep = ws / "mep"
    mep.mkdir(parents=True, exist_ok=True)

    db_a = mep / "airflow_schedule.sqlite"
    db_a.unlink(missing_ok=True)
    with sqlite3.connect(str(db_a)) as conn:
        conn.execute("CREATE TABLE zones (zone_id TEXT PRIMARY KEY, status TEXT, airflow_cfm INTEGER, min_duct_height_mm INTEGER)")
        for r in HVAC_ZONES:
            conn.execute("INSERT INTO zones VALUES (?,?,?,?)", r)
        conn.commit()

    db_b = mep / "feeder_ampacity.sqlite"
    db_b.unlink(missing_ok=True)
    with sqlite3.connect(str(db_b)) as conn:
        conn.execute("CREATE TABLE feeders (feeder_id TEXT PRIMARY KEY, status TEXT, ampacity_a INTEGER, min_tray_height_mm INTEGER)")
        for r in BUS_FEEDERS:
            conn.execute("INSERT INTO feeders VALUES (?,?,?,?)", r)
        conn.commit()

    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map, boot_file
    state_dir.mkdir(parents=True, exist_ok=True)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    stage_private_studio_script(state_dir, "vectorforge_ref.py", VECTORFORGE_QT_SOURCE)
    boot_isolated_studio_scripts(state_dir, ["vectorforge_ref.py"], wait_s=2.2)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    mep = ws / "mep"
    bnd = read_json_safe(mep / "vectorforge_bundle.json")
    rep_a = read_json_safe(mep / "HVAC_REPORT.json")
    rep_b = read_json_safe(mep / "BUSBAR_REPORT.json")

    hy = bnd.get("hvac_nodes_mm") if isinstance(bnd.get("hvac_nodes_mm"), list) and len(bnd["hvac_nodes_mm"]) == 5 else [0.0] * 5
    by = bnd.get("busbar_nodes_mm") if isinstance(bnd.get("busbar_nodes_mm"), list) and len(bnd["busbar_nodes_mm"]) == 5 else [0.0] * 5
    dm = int(bnd.get("duct_base_mm") or 0)
    tm = int(bnd.get("tray_base_mm") or 0)
    ta = int(bnd.get("damper_trim_mm") or 0)
    tb = int(bnd.get("standoff_trim_mm") or 0)
    re_st = compute_bundle_state([float(x) for x in hy], [float(x) for x in by], dm, tm, ta, tb) if bnd else {
        "hvac_rms_mm": 99.0, "busbar_rms_mm": 99.0, "total_ceiling_stack_mm": 0, "bundle_signature": "NONE"
    }
    sig_authentic = bool(bnd and bnd.get("unit_mode") == "MM" and bnd.get("bundle_signature") == re_st["bundle_signature"])

    h_hits = sum(1 for i, t in enumerate(HVAC_TGT_Y) if abs(float(hy[i]) - t) <= 2.8)
    b_hits = sum(1 for i, t in enumerate(BUS_TGT_Y) if abs(float(by[i]) - t) <= 2.8)

    # 18 checks for Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_rep_exists", (mep / "HVAC_REPORT.json").is_file(), 0.05, "Missing HVAC_REPORT.json"),
        ("a_bnd_exists", (mep / "vectorforge_bundle.json").is_file(), 0.05, "Missing vectorforge_bundle.json"),
        ("a_cfm_sum", rep_a.get("active_cfm_sum") == TRUE_ACTIVE_CFM_SUM, 0.07, f"active_cfm_sum != {TRUE_ACTIVE_CFM_SUM}"),
        ("a_req_duct_290", rep_a.get("required_duct_base_mm") == TRUE_DUCT_BASE_MM, 0.07, "required_duct_base_mm != 290"),
        ("a_bnd_duct_290", dm == TRUE_DUCT_BASE_MM, 0.07, f"Bundle duct_base_mm={dm} != 290"),
        ("a_trim_range", 5 <= ta <= 50, 0.05, f"damper_trim_mm={ta} outside [5, 50]"),
        ("a_node_h0", abs(float(hy[0]) - HVAC_TGT_Y[0]) <= 2.8, 0.05, f"H0={hy[0]} != {HVAC_TGT_Y[0]}"),
        ("a_node_h1", abs(float(hy[1]) - HVAC_TGT_Y[1]) <= 2.8, 0.05, f"H1={hy[1]} != {HVAC_TGT_Y[1]}"),
        ("a_node_h2", abs(float(hy[2]) - HVAC_TGT_Y[2]) <= 2.8, 0.05, f"H2={hy[2]} != {HVAC_TGT_Y[2]}"),
        ("a_node_h3", abs(float(hy[3]) - HVAC_TGT_Y[3]) <= 2.8, 0.05, f"H3={hy[3]} != {HVAC_TGT_Y[3]}"),
        ("a_node_h4", abs(float(hy[4]) - HVAC_TGT_Y[4]) <= 2.8, 0.05, f"H4={hy[4]} != {HVAC_TGT_Y[4]}"),
        ("a_nodes_3", h_hits >= 3, 0.05, f"HVAC nodes fitted {h_hits}/5 < 3"),
        ("a_nodes_5", h_hits == 5, 0.06, f"HVAC nodes fitted {h_hits}/5 != 5"),
        ("a_rms_le_2p5", float(re_st["hvac_rms_mm"]) <= 2.5, 0.08, f"hvac_rms_mm={re_st['hvac_rms_mm']} > 2.5"),
        ("a_sig_authentic", sig_authentic, 0.08, "bundle_signature invalid or not exported in MM mode"),
        ("a_rep_sig_match", bool(sig_authentic and str(rep_a.get("bundle_signature") or "").startswith("VF-SIG-")), 0.04, "HVAC_REPORT missing valid VF-SIG signature"),
        ("a_rep_trim_match", isinstance(rep_a.get("damper_trim_mm"), int) and 5 <= int(rep_a["damper_trim_mm"]) <= 50 and bnd != {}, 0.04, "HVAC_REPORT damper_trim_mm invalid"),
        ("a_unit_mm", bnd.get("unit_mode") == "MM", 0.04, "VectorForge unit_mode != MM"),
    ]

    # 18 checks for Role B
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_rep_exists", (mep / "BUSBAR_REPORT.json").is_file(), 0.05, "Missing BUSBAR_REPORT.json"),
        ("b_bnd_exists", (mep / "vectorforge_bundle.json").is_file(), 0.05, "Missing vectorforge_bundle.json"),
        ("b_amps_sum", rep_b.get("energized_amps_sum") == TRUE_ENERGIZED_AMPS_SUM, 0.07, f"energized_amps_sum != {TRUE_ENERGIZED_AMPS_SUM}"),
        ("b_req_tray_290", rep_b.get("required_tray_base_mm") == TRUE_TRAY_BASE_MM, 0.07, "required_tray_base_mm != 290"),
        ("b_bnd_tray_290", tm == TRUE_TRAY_BASE_MM, 0.07, f"Bundle tray_base_mm={tm} != 290"),
        ("b_trim_range", 5 <= tb <= 50, 0.05, f"standoff_trim_mm={tb} outside [5, 50]"),
        ("b_node_b0", abs(float(by[0]) - BUS_TGT_Y[0]) <= 2.8, 0.05, f"B0={by[0]} != {BUS_TGT_Y[0]}"),
        ("b_node_b1", abs(float(by[1]) - BUS_TGT_Y[1]) <= 2.8, 0.05, f"B1={by[1]} != {BUS_TGT_Y[1]}"),
        ("b_node_b2", abs(float(by[2]) - BUS_TGT_Y[2]) <= 2.8, 0.05, f"B2={by[2]} != {BUS_TGT_Y[2]}"),
        ("b_node_b3", abs(float(by[3]) - BUS_TGT_Y[3]) <= 2.8, 0.05, f"B3={by[3]} != {BUS_TGT_Y[3]}"),
        ("b_node_b4", abs(float(by[4]) - BUS_TGT_Y[4]) <= 2.8, 0.05, f"B4={by[4]} != {BUS_TGT_Y[4]}"),
        ("b_nodes_3", b_hits >= 3, 0.05, f"Busbar nodes fitted {b_hits}/5 < 3"),
        ("b_nodes_5", b_hits == 5, 0.06, f"Busbar nodes fitted {b_hits}/5 != 5"),
        ("b_rms_le_2p5", float(re_st["busbar_rms_mm"]) <= 2.5, 0.08, f"busbar_rms_mm={re_st['busbar_rms_mm']} > 2.5"),
        ("b_sig_authentic", sig_authentic, 0.08, "bundle_signature invalid or not exported in MM mode"),
        ("b_rep_sig_match", bool(sig_authentic and str(rep_b.get("bundle_signature") or "").startswith("VF-SIG-")), 0.04, "BUSBAR_REPORT missing valid VF-SIG signature"),
        ("b_rep_trim_match", isinstance(rep_b.get("standoff_trim_mm"), int) and 5 <= int(rep_b["standoff_trim_mm"]) <= 50 and bnd != {}, 0.04, "BUSBAR_REPORT standoff_trim_mm invalid"),
        ("b_unit_mm", bnd.get("unit_mode") == "MM", 0.04, "VectorForge unit_mode != MM"),
    ]

    # 4 joint coupled checks -> total 40 subchecks (total weight 0.16 <= 0.20 cap!)
    stk = int(re_st["total_ceiling_stack_mm"])
    stk_ok = sig_authentic and (STACK_BAND_MM[0] <= stk <= STACK_BAND_MM[1])
    dbs_ok = (mep / "airflow_schedule.sqlite").is_file() and (mep / "feeder_ampacity.sqlite").is_file()
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_coupled_stack_band", stk_ok, 0.08, f"Coupled Total_Ceiling_Stack_mm={stk} outside [636, 644] mm"),
        ("j_authentic_export", sig_authentic, 0.04, "vectorforge_bundle.json lacks authentic GUI signature"),
        ("j_sqlite_intact", dbs_ok, 0.02, "SQLite schedule files missing"),
        ("j_unit_mm_final", bnd.get("unit_mode") == "MM", 0.02, "Final exported unit_mode != MM"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.88,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port
    assert role in ("hvac_plenum_eng", "busbar_riser_eng")
    ws = next(iter(workspace_map.values()))
    mep = ws / "mep"

    def _work() -> None:
        is_a = (role == "hvac_plenum_eng")
        tab_key = "alt+1" if is_a else "alt+2"
        # First export current state so we read peer's live base+trim values accurately
        prep_sh = (
            "export DISPLAY=:99; "
            "wid=$(xdotool search --onlyvisible --name 'VectorForge MEP Studio' | tail -n 1); "
            "wmctrl -i -r \"$wid\" -e 0,40,35,980,620; "
            "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.25; "
            f"xdotool key --clearmodifiers {tab_key}; sleep 0.2; "
            "xdotool key --clearmodifiers ctrl+s; sleep 0.25"
        )
        subprocess.run(["su", "-s", "/bin/bash", "user", "-c", prep_sh], check=True, capture_output=True, timeout=15)
        cur_bnd = read_json_safe(Path("/home/user/Downloads/vectorforge_bundle.json"))
        if cur_bnd.get("unit_mode") == "INCH":
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", "DISPLAY=:99 xdotool key --clearmodifiers u; sleep 0.15"], check=True, capture_output=True, timeout=10)

        # Drag the 5 handles on the active tab onto their target dots via root screenshot pixel matching
        drag_py = (
            "export DISPLAY=:99; python3 - <<'PY'\n"
            "import io, subprocess\n"
            "from PIL import Image\n"
            "raw = subprocess.check_output(['import', '-window', 'root', 'png:-'])\n"
            "im = Image.open(io.BytesIO(raw)).convert('RGB')\n"
            f"is_a = {repr(is_a)}\n"
            "# Window at x=40 -> stations at ~40+12+120+i*145 = 172, 317, 462, 607, 752\n"
            "xbands = [(150, 195), (295, 340), (440, 485), (585, 630), (730, 775)]\n"
            "for (x0, x1) in xbands:\n"
            "    if is_a:\n"
            "        src = [(x,y) for x in range(x0,x1) for y in range(110,510) if im.getpixel((x,y))[0]>220 and 95<=im.getpixel((x,y))[1]<=140 and im.getpixel((x,y))[2]<45]\n"
            "        tgt = [(x,y) for x in range(x0,x1) for y in range(110,510) if im.getpixel((x,y))[0]<45 and im.getpixel((x,y))[1]>165 and 110<=im.getpixel((x,y))[2]<=150]\n"
            "    else:\n"
            "        src = [(x,y) for x in range(x0,x1) for y in range(110,510) if im.getpixel((x,y))[0]<35 and 160<=im.getpixel((x,y))[1]<=205 and im.getpixel((x,y))[2]>190]\n"
            "        tgt = [(x,y) for x in range(x0,x1) for y in range(110,510) if im.getpixel((x,y))[0]>220 and 140<=im.getpixel((x,y))[1]<=175 and im.getpixel((x,y))[2]<35]\n"
            "    cx = sum(p[0] for p in src)//len(src); cy = sum(p[1] for p in src)//len(src)\n"
            "    ty = sum(p[1] for p in tgt)//len(tgt)\n"
            "    subprocess.run(['xdotool','mousemove',str(cx),str(cy),'mousedown','1'],check=True)\n"
            "    for k in range(1,9):\n"
            "        subprocess.run(['xdotool','mousemove',str(cx),str(cy+int((ty-cy)*k/8))],check=True)\n"
            "    subprocess.run(['xdotool','mouseup','1'],check=True)\n"
            "PY"
        )
        subprocess.run(["su", "-s", "/bin/bash", "user", "-c", drag_py], check=True, capture_output=True, timeout=25)

        # Set spinboxes via AT-SPI Value interface or qwen-cua-driver / pyatspi on :99, then Ctrl+S!
        if is_a:
            other_sum = int(cur_bnd.get("tray_base_mm", 315)) + int(cur_bnd.get("standoff_trim_mm", 12))
            new_trim = max(5, min(50, 640 - (TRUE_DUCT_BASE_MM + other_sum)))
            fk_base, base_val, fk_trim, trim_val = "F5", TRUE_DUCT_BASE_MM, "F6", new_trim
        else:
            other_sum = int(cur_bnd.get("duct_base_mm", 315)) + int(cur_bnd.get("damper_trim_mm", 12))
            new_trim = max(5, min(50, 640 - (TRUE_TRAY_BASE_MM + other_sum)))
            fk_base, base_val, fk_trim, trim_val = "F7", TRUE_TRAY_BASE_MM, "F8", new_trim

        spin_sh = (
            "export DISPLAY=:99; "
            "wid=$(xdotool search --onlyvisible --name 'VectorForge MEP Studio' | tail -n 1); "
            "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.15; "
            f"xdotool key --clearmodifiers {fk_base}; sleep 0.08; xdotool type --clearmodifiers --delay 15 {base_val}; xdotool key --clearmodifiers Return; sleep 0.08; "
            f"xdotool key --clearmodifiers {fk_trim}; sleep 0.08; xdotool type --clearmodifiers --delay 15 {trim_val}; xdotool key --clearmodifiers Return; sleep 0.08; "
            "xdotool key --clearmodifiers ctrl+s; sleep 0.25"
        )
        subprocess.run(["su", "-s", "/bin/bash", "user", "-c", spin_sh], check=True, capture_output=True, timeout=15)
        final_bnd = read_json_safe(Path("/home/user/Downloads/vectorforge_bundle.json"))
        write_json(mep / "vectorforge_bundle.json", final_bnd)
        if is_a:
            write_json(
                mep / "HVAC_REPORT.json",
                {
                    "active_cfm_sum": TRUE_ACTIVE_CFM_SUM,
                    "required_duct_base_mm": TRUE_DUCT_BASE_MM,
                    "damper_trim_mm": final_bnd["damper_trim_mm"],
                    "hvac_rms_mm": final_bnd["hvac_rms_mm"],
                    "bundle_signature": final_bnd["bundle_signature"],
                },
            )
        else:
            write_json(
                mep / "BUSBAR_REPORT.json",
                {
                    "energized_amps_sum": TRUE_ENERGIZED_AMPS_SUM,
                    "required_tray_base_mm": TRUE_TRAY_BASE_MM,
                    "standoff_trim_mm": final_bnd["standoff_trim_mm"],
                    "busbar_rms_mm": final_bnd["busbar_rms_mm"],
                    "bundle_signature": final_bnd["bundle_signature"],
                },
            )

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_6 MDI Tab Switch + LAW_8 Dual-Lever Stack Drift): Stale trims push stack to 626mm (<636mm)."""
    solve_role("hvac_plenum_eng", workspace_map, port, careful_conc=False)
    solve_role("busbar_riser_eng", workspace_map, port, careful_conc=False)
    ws = next(iter(workspace_map.values()))
    bad = compute_bundle_state(HVAC_TGT_Y, BUS_INIT_Y, 290, 290, 23, 23)
    bad["unit_mode"] = "MM"
    write_json(ws / "mep" / "vectorforge_bundle.json", bad)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 5
    write_json(sp, st)

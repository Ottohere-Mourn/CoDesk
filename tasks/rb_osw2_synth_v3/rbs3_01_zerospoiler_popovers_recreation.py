"""RBS3-01: Zero-Spoiler 5-Surface Deep Recreation — Autohide F10 QMenu, 3-Tab Twin Preferences & QPainter Bars.

Grounded in RB-B3 KSudoku (-42.3%), RB-B4 GTK4 Popover (menu=0/5), RB-B6 wxMEdit (61.5% misrouting) & LAW_8:
  - Zero-spoiler task.md: no hidden menu names, tab titles, build codes, calibration constants, or bar values leaked.
  - 5 distinct interactive GUI surfaces per reference app on shared :99:
    (1) Startup modal wizard, (2) 3-mode QPainter 6-bar visual canvas (1/2/3), (3) focus-loss autohiding F10 QMenu,
    (4) twin 'Preferences' (Ctrl+P) 3-tab modal dialog, (5) twin 'About' (F1) modal dialog.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Any

from tasks.rb_osw2_synth_v3.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    build_grade_payload,
    evaluate_recreated_gui_app,
    read_json_safe,
    run_cli_probe_json,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS3-01"
ALLOW_SYNTHETIC_TARGET_APP = True
PORTAL_PORT = 19501

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Zero-Spoiler 5-Surface Recreation: Autohide F10 Popovers, 3-Tab Twin Preferences & QPainter EQ/Packet Studios",
    "domain": "Zero-Source Multi-Surface Desktop Audio DSP & Network Packet Studio Recreation",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("spectrumpad_recreator", "packetforge_recreator"),
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
            "slug": "spectrumpad_recreator",
            "est_role_seconds": 500.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "autohide_popover_or_ephemeral_menu",
                "candidate_window_launch_on_shared_display",
                "twin_named_modals",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "packetforge_recreator",
            "est_role_seconds": 500.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "autohide_popover_or_ephemeral_menu",
                "candidate_window_launch_on_shared_display",
                "twin_named_modals",
                "iterative_keyboard_shortcuts",
            ],
        },
    },
}

SPAD_ORACLE: dict[str, Any] = {
    "app_title": "SpectrumPad Studio",
    "build_code": "SPAD-4.2.8-RT",
    "modes": ["STUDIO_FLAT", "VOCAL_AIR", "SUB_BASS"],
    "mode2_band_gains_db": [-6, 4, 9, -3, 7, 2],
    "menu_actions": [
        "Normalize Peak (-1 dBFS)",
        "Export FIR Impulse",
        "Phase Invert Bus",
        "Lock Reference Curve",
    ],
    "pref_tabs": ["Engine", "Calibration", "Export"],
    "calibration_offset_db": -2.75,
    "export_format": "WAV_FLOAT32",
    "accent_hex": "#10B981",
}

PKTF_ORACLE: dict[str, Any] = {
    "app_title": "PacketForge Analyzer",
    "build_code": "PKTF-3.9.1-DPDK",
    "modes": ["INGRESS_SYN", "RDMA_BURST", "QUIC_HANDSHAKE"],
    "mode2_latencies_ms": [15, 45, 30, 65, 20, 50],
    "menu_actions": [
        "Decode VLAN Tags",
        "Export PCAP Digest",
        "Reset Ring Counters",
        "Freeze Jitter Histogram",
    ],
    "pref_tabs": ["Capture", "ClockSync", "Export"],
    "ptp_skew_ppm": 18.5,
    "export_format": "PCAPNG_ZSTD",
    "accent_hex": "#06B6D4",
}

SPAD_QT_SOURCE = f"""import sys
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QColor, QFont, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPushButton, QShortcut, QTabWidget, QVBoxLayout, QWidget
)

MODES = {repr(SPAD_ORACLE["modes"])}
BARS_BY_MODE = {{
    0: [0, 0, 0, 0, 0, 0],
    1: {repr(SPAD_ORACLE["mode2_band_gains_db"])},
    2: [8, 6, 2, -2, -5, -7],
}}
MENU_ITEMS = {repr(SPAD_ORACLE["menu_actions"])}

class EqCanvas(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setMinimumSize(780, 340)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(15, 23, 42))
        p.setFont(QFont("DejaVu Sans Mono", 9, QFont.Bold))
        y0 = 180
        for db in (-9, -6, -3, 0, 3, 6, 9):
            yy = y0 - db * 14
            p.setPen(QPen(QColor(71, 85, 105) if db != 0 else QColor(148, 163, 184), 1 if db != 0 else 2))
            p.drawLine(75, yy, 745, yy)
            p.setPen(QColor(203, 213, 225))
            p.drawText(14, yy + 4, f"{{db:+d}} dB")
        vals = BARS_BY_MODE[self.win.mode_idx]
        freqs = ["63Hz", "250Hz", "1kHz", "2.5kHz", "6kHz", "14kHz"]
        for i, v in enumerate(vals):
            bx = 105 + i * 104
            top = min(y0, y0 - v * 14)
            bh = max(4, abs(v * 14))
            p.fillRect(bx, top, 56, bh, QColor(16, 185, 129))
            p.setPen(QPen(QColor(236, 253, 245), 2))
            p.drawRect(bx, top, 56, bh)
            p.drawText(bx + 6, 326, f"B{{i+1}}:{{freqs[i]}}")
        p.end()

class SpadWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpectrumPad Studio")
        self.resize(860, 540)
        self.mode_idx = 0
        self.last_act = "NONE"
        cw = QWidget(); v = QVBoxLayout(cw)
        self.hdr = QLabel()
        self.hdr.setStyleSheet("padding:6px;background:#064e3b;color:#ecfdf5;font-weight:bold;")
        v.addWidget(self.hdr)
        self.cv = EqCanvas(self)
        v.addWidget(self.cv)
        row = QHBoxLayout()
        for i, m in enumerate(MODES):
            b = QPushButton(f"[{{i+1}}] {{m}}"); b.clicked.connect(lambda _=False, k=i: self.set_mode(k)); row.addWidget(b)
        self.btn_menu = QPushButton("&Tools Menu (F10)"); self.btn_menu.clicked.connect(self.open_menu); row.addWidget(self.btn_menu)
        bp = QPushButton("&Preferences (Ctrl+P)"); bp.clicked.connect(self.open_prefs); row.addWidget(bp)
        ba = QPushButton("&About (F1)"); ba.clicked.connect(self.open_about); row.addWidget(ba)
        v.addLayout(row)
        self.setCentralWidget(cw)
        for i, ks in enumerate(["1", "2", "3"]):
            QShortcut(QKeySequence(ks), self, activated=lambda k=i: self.set_mode(k))
        QShortcut(QKeySequence("F10"), self, activated=self.open_menu)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)
        QShortcut(QKeySequence("F1"), self, activated=self.open_about)
        self.refresh()

    def show_startup_wizard(self):
        d = QDialog(self); d.setWindowTitle("Select Audio Profile"); d.setModal(True); d.resize(400, 170)
        dv = QVBoxLayout(d); dv.addWidget(QLabel("Select Studio Audio Engine Profile (48kHz / 64-bit DSP):"))
        ok = QPushButton("Activate Studio Engine"); ok.clicked.connect(d.accept); dv.addWidget(ok)
        d.exec_()

    def set_mode(self, idx):
        self.mode_idx = idx
        self.refresh()

    def refresh(self):
        self.hdr.setText(f"Active Preset: {{MODES[self.mode_idx]}} | LastTool={{self.last_act}}")
        self.cv.update()

    def open_menu(self):
        m = QMenu(self)
        for lbl in MENU_ITEMS:
            act = m.addAction(lbl)
            act.triggered.connect(lambda _=False, x=lbl: self._on_act(x))
        m.popup(self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height())))

    def _on_act(self, x):
        self.last_act = x
        self.refresh()

    def open_prefs(self):
        d = QDialog(self); d.setWindowTitle("Preferences"); d.setModal(True); d.resize(460, 260)
        dv = QVBoxLayout(d); tabs = QTabWidget()
        t1 = QWidget(); l1 = QVBoxLayout(t1); l1.addWidget(QLabel("DSP Sample Rate: 48000 Hz | Block: 256")); tabs.addTab(t1, "Engine")
        t2 = QWidget(); l2 = QVBoxLayout(t2); l2.addWidget(QLabel("calibration_offset_db = -2.75")); tabs.addTab(t2, "Calibration")
        t3 = QWidget(); l3 = QVBoxLayout(t3); l3.addWidget(QLabel("export_format = WAV_FLOAT32 | accent_hex = #10B981")); tabs.addTab(t3, "Export")
        dv.addWidget(tabs)
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); dv.addWidget(bc)
        d.exec_()

    def open_about(self):
        d = QDialog(self); d.setWindowTitle("About"); d.setModal(True); d.resize(380, 180)
        dv = QVBoxLayout(d)
        dv.addWidget(QLabel("SpectrumPad Studio — Mastering EQ Workbench"))
        dv.addWidget(QLabel("build_code = SPAD-4.2.8-RT"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); dv.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
w = SpadWin(); w.show()
from PyQt5.QtCore import QTimer
QTimer.singleShot(250, w.show_startup_wizard)
sys.exit(app.exec_())
"""

PKTF_QT_SOURCE = f"""import sys
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QColor, QFont, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPushButton, QShortcut, QTabWidget, QVBoxLayout, QWidget
)

MODES = {repr(PKTF_ORACLE["modes"])}
BARS_BY_MODE = {{
    0: [10, 10, 10, 10, 10, 10],
    1: {repr(PKTF_ORACLE["mode2_latencies_ms"])},
    2: [55, 25, 40, 20, 60, 35],
}}
MENU_ITEMS = {repr(PKTF_ORACLE["menu_actions"])}

class PktCanvas(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setMinimumSize(780, 340)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(12, 19, 34))
        p.setFont(QFont("DejaVu Sans Mono", 9, QFont.Bold))
        yb = 300
        for ms in (0, 15, 30, 45, 60, 75):
            yy = int(yb - ms * 3.4)
            p.setPen(QPen(QColor(65, 80, 105) if ms != 0 else QColor(148, 163, 184), 1 if ms != 0 else 2))
            p.drawLine(75, yy, 745, yy)
            p.setPen(QColor(203, 213, 225))
            p.drawText(12, yy + 4, f"{{ms:2d}} ms")
        vals = BARS_BY_MODE[self.win.mode_idx]
        lanes = ["L0:ARP", "L1:TCP", "L2:RoCE", "L3:NVMe", "L4:QUIC", "L5:PTP"]
        for i, v in enumerate(vals):
            bx = 105 + i * 104
            bh = max(4, int(round(v * 3.4)))
            top = yb - bh
            p.fillRect(bx, top, 56, bh, QColor(6, 182, 212))
            p.setPen(QPen(QColor(236, 254, 255), 2))
            p.drawRect(bx, top, 56, bh)
            p.drawText(bx + 4, 326, lanes[i])
        p.end()

class PktfWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PacketForge Analyzer")
        self.resize(860, 540)
        self.mode_idx = 0
        self.last_act = "NONE"
        cw = QWidget(); v = QVBoxLayout(cw)
        self.hdr = QLabel()
        self.hdr.setStyleSheet("padding:6px;background:#164e63;color:#ecfeff;font-weight:bold;")
        v.addWidget(self.hdr)
        self.cv = PktCanvas(self)
        v.addWidget(self.cv)
        row = QHBoxLayout()
        for i, m in enumerate(MODES):
            b = QPushButton(f"[{{i+1}}] {{m}}"); b.clicked.connect(lambda _=False, k=i: self.set_mode(k)); row.addWidget(b)
        self.btn_menu = QPushButton("&Tools Menu (F10)"); self.btn_menu.clicked.connect(self.open_menu); row.addWidget(self.btn_menu)
        bp = QPushButton("&Preferences (Ctrl+P)"); bp.clicked.connect(self.open_prefs); row.addWidget(bp)
        ba = QPushButton("&About (F1)"); ba.clicked.connect(self.open_about); row.addWidget(ba)
        v.addLayout(row)
        self.setCentralWidget(cw)
        for i, ks in enumerate(["1", "2", "3"]):
            QShortcut(QKeySequence(ks), self, activated=lambda k=i: self.set_mode(k))
        QShortcut(QKeySequence("F10"), self, activated=self.open_menu)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)
        QShortcut(QKeySequence("F1"), self, activated=self.open_about)
        self.refresh()

    def show_startup_wizard(self):
        d = QDialog(self); d.setWindowTitle("Select Capture Interface"); d.setModal(True); d.resize(400, 170)
        dv = QVBoxLayout(d); dv.addWidget(QLabel("Bind PacketForge Ring Buffer (mlx5_0 100GbE):"))
        ok = QPushButton("Attach Capture Ring"); ok.clicked.connect(d.accept); dv.addWidget(ok)
        d.exec_()

    def set_mode(self, idx):
        self.mode_idx = idx
        self.refresh()

    def refresh(self):
        self.hdr.setText(f"Capture View: {{MODES[self.mode_idx]}} | LastTool={{self.last_act}}")
        self.cv.update()

    def open_menu(self):
        m = QMenu(self)
        for lbl in MENU_ITEMS:
            act = m.addAction(lbl)
            act.triggered.connect(lambda _=False, x=lbl: self._on_act(x))
        m.popup(self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height())))

    def _on_act(self, x):
        self.last_act = x
        self.refresh()

    def open_prefs(self):
        d = QDialog(self); d.setWindowTitle("Preferences"); d.setModal(True); d.resize(460, 260)
        dv = QVBoxLayout(d); tabs = QTabWidget()
        t1 = QWidget(); l1 = QVBoxLayout(t1); l1.addWidget(QLabel("Ring Slots: 4096 | SnapLen: 9000B")); tabs.addTab(t1, "Capture")
        t2 = QWidget(); l2 = QVBoxLayout(t2); l2.addWidget(QLabel("ptp_skew_ppm = 18.5")); tabs.addTab(t2, "ClockSync")
        t3 = QWidget(); l3 = QVBoxLayout(t3); l3.addWidget(QLabel("export_format = PCAPNG_ZSTD | accent_hex = #06B6D4")); tabs.addTab(t3, "Export")
        dv.addWidget(tabs)
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); dv.addWidget(bc)
        d.exec_()

    def open_about(self):
        d = QDialog(self); d.setWindowTitle("About"); d.setModal(True); d.resize(380, 180)
        dv = QVBoxLayout(d)
        dv.addWidget(QLabel("PacketForge Analyzer — DPDK Telemetry Studio"))
        dv.addWidget(QLabel("build_code = PKTF-3.9.1-DPDK"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); dv.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
w = PktfWin(); w.show()
from PyQt5.QtCore import QTimer
QTimer.singleShot(250, w.show_startup_wizard)
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Zero-Source Audio DSP Studio Recreation Work Order — {b}spectrumpad_recreator{b}",
        "",
        "## Scope & Deliverables",
        "Explore the live **SpectrumPad Studio** desktop application running on the workstation display — including its startup wizard, all 3 preset views (`1`, `2`, `3`) and their 6-band visual EQ bar values (in integer dB), its `F10` Tools popup menu actions, all tabs of its `Preferences` (`Ctrl+P`) dialog, and its `About` (`F1`) dialog — and build a standalone GUI recreation.",
        "",
        "Deliverables:",
        f"1. **Standalone Recreated GUI Application ({b}/workspace/recreation/run_app.sh{b})**:",
        "   - Launching `bash /workspace/recreation/run_app.sh` (with no arguments) must open a desktop window titled `SpectrumPad Studio` (`>= 760x480`) reproducing the 3 preset views (`1`/`2`/`3`), the 6-band visual EQ canvas, the `F10` Tools menu items, the multi-tab `Preferences` (`Ctrl+P`) dialog, and the `About` (`F1`) dialog.",
        f"   - Running `bash /workspace/recreation/run_app.sh --dump-spec-json` must print a single JSON object with exact keys: {b}\"app_title\"{b}, {b}\"build_code\"{b}, {b}\"modes\"{b} (list of 3 strings in `1..3` order), {b}\"mode2_band_gains_db\"{b} (list of 6 integers read from preset `[2]`'s 6 visual EQ bars `B1..B6`), {b}\"menu_actions\"{b} (list of 4 strings from the `F10` popup menu), {b}\"pref_tabs\"{b} (list of 3 tab titles in `Preferences`), {b}\"calibration_offset_db\"{b} (float from `Preferences` tab 2), {b}\"export_format\"{b} (string from tab 3), and {b}\"accent_hex\"{b} (string `#RRGGBB` from tab 3).",
        f"2. **Discovered Specification JSON ({b}/workspace/DISCOVERED_SPEC.json{b})**:",
        "   - Save the same JSON object to `/workspace/DISCOVERED_SPEC.json`.",
        "",
    ])
    role_b = "\n".join([
        f"# Zero-Source Network Packet Studio Recreation Work Order — {b}packetforge_recreator{b}",
        "",
        "## Scope & Deliverables",
        "Explore the live **PacketForge Analyzer** desktop application running on the workstation display — including its startup wizard, all 3 capture views (`1`, `2`, `3`) and their 6-lane visual latency bars (in integer ms), its `F10` Tools popup menu actions, all tabs of its `Preferences` (`Ctrl+P`) dialog, and its `About` (`F1`) dialog — and build a standalone GUI recreation.",
        "",
        "Deliverables:",
        f"1. **Standalone Recreated GUI Application ({b}/workspace/recreation/run_app.sh{b})**:",
        "   - Launching `bash /workspace/recreation/run_app.sh` (with no arguments) must open a desktop window titled `PacketForge Analyzer` (`>= 760x480`) reproducing the 3 capture views (`1`/`2`/`3`), the 6-lane visual latency canvas, the `F10` Tools menu items, the multi-tab `Preferences` (`Ctrl+P`) dialog, and the `About` (`F1`) dialog.",
        f"   - Running `bash /workspace/recreation/run_app.sh --dump-spec-json` must print a single JSON object with exact keys: {b}\"app_title\"{b}, {b}\"build_code\"{b}, {b}\"modes\"{b} (list of 3 strings in `1..3` order), {b}\"mode2_latencies_ms\"{b} (list of 6 integers read from view `[2]`'s 6 visual bars `L0..L5`), {b}\"menu_actions\"{b} (list of 4 strings from the `F10` popup menu), {b}\"pref_tabs\"{b} (list of 3 tab titles in `Preferences`), {b}\"ptp_skew_ppm\"{b} (float from `Preferences` tab 2), {b}\"export_format\"{b} (string from tab 3), and {b}\"accent_hex\"{b} (string `#RRGGBB` from tab 3).",
        f"2. **Discovered Specification JSON ({b}/workspace/DISCOVERED_SPEC.json{b})**:",
        "   - Save the same JSON object to `/workspace/DISCOVERED_SPEC.json`.",
        "",
    ])
    return {"spectrumpad_recreator": role_a, "packetforge_recreator": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    for ws in workspace_map.values():
        (ws / "recreation").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map, boot_file
    state_dir.mkdir(parents=True, exist_ok=True)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    stage_private_studio_script(state_dir, "spad_ref.py", SPAD_QT_SOURCE)
    stage_private_studio_script(state_dir, "pktf_ref.py", PKTF_QT_SOURCE)
    boot_isolated_studio_scripts(state_dir, ["spad_ref.py", "pktf_ref.py"], wait_s=2.4)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["spectrumpad_recreator"]
    ws_b = workspace_map["packetforge_recreator"]

    sh_a = ws_a / "recreation" / "run_app.sh"
    sp_a = read_json_safe(ws_a / "DISCOVERED_SPEC.json") or run_cli_probe_json(sh_a, ["--dump-spec-json"])
    cli_a = run_cli_probe_json(sh_a, ["--dump-spec-json"])
    ev_a = evaluate_recreated_gui_app(
        sh_a,
        disp_num=121,
        expected_title_sub="SpectrumPad",
        key_sequences=[("accept_wizard", "Return"), ("mode2", "2"), ("prefs", "ctrl+p")],
    )
    ax_a_all = (ev_a["initial_ax_text"] + " " + " ".join(ev_a["after_keys_ax"].values())).lower()
    bars_a = sp_a.get("mode2_band_gains_db") if isinstance(sp_a.get("mode2_band_gains_db"), list) else []
    bars_a_hits = sum(
        1
        for i, tgt in enumerate(SPAD_ORACLE["mode2_band_gains_db"])
        if i < len(bars_a) and isinstance(bars_a[i], (int, float)) and abs(float(bars_a[i]) - tgt) <= 1.0
    )
    menus_a = [str(x) for x in (sp_a.get("menu_actions") or [])]
    menu_a_hits = sum(1 for m in SPAD_ORACLE["menu_actions"] if m in menus_a)
    tabs_a = [str(x) for x in (sp_a.get("pref_tabs") or [])]

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_script_exists", sh_a.is_file(), 0.04, "Missing recreation/run_app.sh"),
        ("a_cli_dump_works", bool(cli_a), 0.04, "--dump-spec-json returned empty/invalid JSON"),
        ("a_win_mapped", ev_a["window_mapped"], 0.06, "SpectrumPad candidate window failed to map"),
        ("a_win_size", ev_a["win_w"] >= 720 and ev_a["win_h"] >= 440, 0.04, f"SpectrumPad size {ev_a['win_w']}x{ev_a['win_h']} < 720x440"),
        ("a_visual_rich", ev_a["visual_nonblank"] and ev_a["unique_colors_sampled"] >= 5, 0.05, "SpectrumPad visual canvas blank/monochrome"),
        ("a_ax_modes", "vocal_air" in ax_a_all or "studio_flat" in ax_a_all, 0.05, "AT-SPI missing preset mode controls"),
        ("a_ax_prefs", "calibration" in ax_a_all or "2.75" in ax_a_all or "preferences" in ax_a_all, 0.05, "AT-SPI missing Preferences/Calibration UI"),
        ("a_build_code", sp_a.get("build_code") == SPAD_ORACLE["build_code"], 0.06, f"build_code={sp_a.get('build_code')!r} != 'SPAD-4.2.8-RT'"),
        ("a_modes_3", sp_a.get("modes") == SPAD_ORACLE["modes"], 0.05, "modes list != ['STUDIO_FLAT','VOCAL_AIR','SUB_BASS']"),
        ("a_bars_half3", bars_a_hits >= 3, 0.05, f"EQ visual bars accurate {bars_a_hits}/6 < 3"),
        ("a_bars_5", bars_a_hits >= 5, 0.05, f"EQ visual bars accurate {bars_a_hits}/6 < 5"),
        ("a_bars_all6", bars_a_hits == 6, 0.06, f"EQ visual bars accurate {bars_a_hits}/6 != 6"),
        ("a_menu_half2", menu_a_hits >= 2, 0.05, f"F10 menu items discovered {menu_a_hits}/4 < 2"),
        ("a_menu_3", menu_a_hits >= 3, 0.05, f"F10 menu items discovered {menu_a_hits}/4 < 3"),
        ("a_menu_all4", menu_a_hits == 4, 0.06, f"F10 menu items discovered {menu_a_hits}/4 != 4"),
        ("a_pref_tabs_3", tabs_a == SPAD_ORACLE["pref_tabs"], 0.06, f"pref_tabs={tabs_a} != {SPAD_ORACLE['pref_tabs']}"),
        ("a_cal_offset", isinstance(sp_a.get("calibration_offset_db"), (int, float)) and abs(float(sp_a["calibration_offset_db"]) - (-2.75)) <= 0.05, 0.06, "calibration_offset_db != -2.75"),
        ("a_export_fmt", sp_a.get("export_format") == "WAV_FLOAT32", 0.04, "export_format != 'WAV_FLOAT32'"),
        ("a_accent_hex", str(sp_a.get("accent_hex") or "").upper() == "#10B981", 0.04, "accent_hex != '#10B981'"),
        ("a_spec_file", (ws_a / "DISCOVERED_SPEC.json").is_file(), 0.04, "Missing DISCOVERED_SPEC.json"),
    ]

    sh_b = ws_b / "recreation" / "run_app.sh"
    sp_b = read_json_safe(ws_b / "DISCOVERED_SPEC.json") or run_cli_probe_json(sh_b, ["--dump-spec-json"])
    cli_b = run_cli_probe_json(sh_b, ["--dump-spec-json"])
    ev_b = evaluate_recreated_gui_app(
        sh_b,
        disp_num=122,
        expected_title_sub="PacketForge",
        key_sequences=[("accept_wizard", "Return"), ("mode2", "2"), ("prefs", "ctrl+p")],
    )
    ax_b_all = (ev_b["initial_ax_text"] + " " + " ".join(ev_b["after_keys_ax"].values())).lower()
    bars_b = sp_b.get("mode2_latencies_ms") if isinstance(sp_b.get("mode2_latencies_ms"), list) else []
    bars_b_hits = sum(
        1
        for i, tgt in enumerate(PKTF_ORACLE["mode2_latencies_ms"])
        if i < len(bars_b) and isinstance(bars_b[i], (int, float)) and abs(float(bars_b[i]) - tgt) <= 2.0
    )
    menus_b = [str(x) for x in (sp_b.get("menu_actions") or [])]
    menu_b_hits = sum(1 for m in PKTF_ORACLE["menu_actions"] if m in menus_b)
    tabs_b = [str(x) for x in (sp_b.get("pref_tabs") or [])]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_script_exists", sh_b.is_file(), 0.04, "Missing recreation/run_app.sh"),
        ("b_cli_dump_works", bool(cli_b), 0.04, "--dump-spec-json returned empty/invalid JSON"),
        ("b_win_mapped", ev_b["window_mapped"], 0.06, "PacketForge candidate window failed to map"),
        ("b_win_size", ev_b["win_w"] >= 720 and ev_b["win_h"] >= 440, 0.04, f"PacketForge size {ev_b['win_w']}x{ev_b['win_h']} < 720x440"),
        ("b_visual_rich", ev_b["visual_nonblank"] and ev_b["unique_colors_sampled"] >= 5, 0.05, "PacketForge visual canvas blank/monochrome"),
        ("b_ax_modes", "rdma_burst" in ax_b_all or "ingress_syn" in ax_b_all, 0.05, "AT-SPI missing capture view controls"),
        ("b_ax_prefs", "clocksync" in ax_b_all or "18.5" in ax_b_all or "preferences" in ax_b_all, 0.05, "AT-SPI missing Preferences/ClockSync UI"),
        ("b_build_code", sp_b.get("build_code") == PKTF_ORACLE["build_code"], 0.06, f"build_code={sp_b.get('build_code')!r} != 'PKTF-3.9.1-DPDK'"),
        ("b_modes_3", sp_b.get("modes") == PKTF_ORACLE["modes"], 0.05, "modes list != ['INGRESS_SYN','RDMA_BURST','QUIC_HANDSHAKE']"),
        ("b_bars_half3", bars_b_hits >= 3, 0.05, f"Latency visual bars accurate {bars_b_hits}/6 < 3"),
        ("b_bars_5", bars_b_hits >= 5, 0.05, f"Latency visual bars accurate {bars_b_hits}/6 < 5"),
        ("b_bars_all6", bars_b_hits == 6, 0.06, f"Latency visual bars accurate {bars_b_hits}/6 != 6"),
        ("b_menu_half2", menu_b_hits >= 2, 0.05, f"F10 menu items discovered {menu_b_hits}/4 < 2"),
        ("b_menu_3", menu_b_hits >= 3, 0.05, f"F10 menu items discovered {menu_b_hits}/4 < 3"),
        ("b_menu_all4", menu_b_hits == 4, 0.06, f"F10 menu items discovered {menu_b_hits}/4 != 4"),
        ("b_pref_tabs_3", tabs_b == PKTF_ORACLE["pref_tabs"], 0.06, f"pref_tabs={tabs_b} != {PKTF_ORACLE['pref_tabs']}"),
        ("b_ptp_skew", isinstance(sp_b.get("ptp_skew_ppm"), (int, float)) and abs(float(sp_b["ptp_skew_ppm"]) - 18.5) <= 0.1, 0.06, "ptp_skew_ppm != 18.5"),
        ("b_export_fmt", sp_b.get("export_format") == "PCAPNG_ZSTD", 0.04, "export_format != 'PCAPNG_ZSTD'"),
        ("b_accent_hex", str(sp_b.get("accent_hex") or "").upper() == "#06B6D4", 0.04, "accent_hex != '#06B6D4'"),
        ("b_spec_file", (ws_b / "DISCOVERED_SPEC.json").is_file(), 0.04, "Missing DISCOVERED_SPEC.json"),
    ]

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


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port
    assert role in ("spectrumpad_recreator", "packetforge_recreator")
    ws = workspace_map[role]
    rec = ws / "recreation"
    rec.mkdir(parents=True, exist_ok=True)

    def _work() -> None:
        if role == "spectrumpad_recreator":
            write_json(ws / "DISCOVERED_SPEC.json", SPAD_ORACLE)
            py_src = (
                "import json, sys\n"
                f"OR = {repr(SPAD_ORACLE)}\n"
                "if '--dump-spec-json' in sys.argv:\n"
                "    print(json.dumps(OR)); sys.exit(0)\n"
                "from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton\n"
                "app = QApplication(sys.argv); w = QMainWindow(); w.setWindowTitle('SpectrumPad Studio'); w.resize(820, 520)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#0f172a;color:#ecfdf5;'); v = QVBoxLayout(cw)\n"
                "l1 = QLabel('STUDIO_FLAT | VOCAL_AIR | SUB_BASS | Calibration -2.75 dB'); l1.setStyleSheet('background:#064e3b;color:#10b981;padding:10px;')\n"
                "l2 = QLabel('EQ Gains: -6 +4 +9 -3 +7 +2 | Preferences | WAV_FLOAT32'); l2.setStyleSheet('background:#1e293b;color:#38bdf8;padding:10px;')\n"
                "b1 = QPushButton('Preferences'); b1.setStyleSheet('background:#10b981;color:#052e16;padding:8px;')\n"
                "b2 = QPushButton('Normalize Peak (-1 dBFS)'); b2.setStyleSheet('background:#2563eb;color:#fff;padding:8px;')\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1); v.addWidget(b2); w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "app.py").write_text(py_src, encoding="utf-8")
        else:
            write_json(ws / "DISCOVERED_SPEC.json", PKTF_ORACLE)
            py_src = (
                "import json, sys\n"
                f"OR = {repr(PKTF_ORACLE)}\n"
                "if '--dump-spec-json' in sys.argv:\n"
                "    print(json.dumps(OR)); sys.exit(0)\n"
                "from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton\n"
                "app = QApplication(sys.argv); w = QMainWindow(); w.setWindowTitle('PacketForge Analyzer'); w.resize(820, 520)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#0c1322;color:#ecfeff;'); v = QVBoxLayout(cw)\n"
                "l1 = QLabel('INGRESS_SYN | RDMA_BURST | QUIC_HANDSHAKE | ClockSync 18.5 ppm'); l1.setStyleSheet('background:#164e63;color:#06b6d4;padding:10px;')\n"
                "l2 = QLabel('Latencies: 15 45 30 65 20 50 | Preferences | PCAPNG_ZSTD'); l2.setStyleSheet('background:#1e293b;color:#f59e0b;padding:10px;')\n"
                "b1 = QPushButton('Preferences'); b1.setStyleSheet('background:#06b6d4;color:#083344;padding:8px;')\n"
                "b2 = QPushButton('Decode VLAN Tags'); b2.setStyleSheet('background:#7c3aed;color:#fff;padding:8px;')\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1); v.addWidget(b2); w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "app.py").write_text(py_src, encoding="utf-8")
        sh = rec / "run_app.sh"
        sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/app.py\" \"$@\"\n", encoding="utf-8")
        os.chmod(sh, 0o755)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_3 Autohide F10 QMenu + LAW_2 Twin Preferences): Focus loss dismisses F10 menu & swaps Preferences."""
    solve_role("spectrumpad_recreator", workspace_map, port, careful_conc=False)
    solve_role("packetforge_recreator", workspace_map, port, careful_conc=False)
    ws_b = workspace_map["packetforge_recreator"]
    bad = read_json_safe(ws_b / "DISCOVERED_SPEC.json")
    bad["menu_actions"] = []
    bad["ptp_skew_ppm"] = -2.75
    bad["pref_tabs"] = SPAD_ORACLE["pref_tabs"]
    write_json(ws_b / "DISCOVERED_SPEC.json", bad)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 4
    write_json(sp, st)

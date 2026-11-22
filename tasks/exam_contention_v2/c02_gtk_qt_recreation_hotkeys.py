"""EC2-C02: GTK3 Self-Hiding Popover VibraScope vs. PyQt5 Hotkey TelemetryHex Recreation.

Track 1 — Isolated Workspaces, Exploration-as-Oracle & Global Hotkey/Popover Contention:
  - Live reference GTK3 and PyQt5 applications run from /opt/ec2_state inside the display container
    (source code inaccessible to role containers).
  - Role A explores VibraScope Reference (GTK3 HeaderBar + F10 auto-hiding Popover + Ctrl+K modal)
    and builds /workspace/vibrascope_recreated.py + /workspace/VIBRASCOPE_REPORT.json.
  - Role B explores TelemetryHex Reference (PyQt5 QMainWindow + Alt+D & Ctrl+G modals + Escape)
    and builds /workspace/telemetryhex_recreated.py + /workspace/DECODED_TELEMETRY.json.
  - Global X11 shortcuts (F10, Ctrl+K, Alt+D, Ctrl+G, Escape) and candidate test windows collide on DISPLAY=:99.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import random
import struct
import subprocess
import time
from typing import Any

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    read_json_safe,
    write_json,
)

TASK_ID = "EC2-C02"
PORTAL_PORT = 19102

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "GTK3 Self-Hiding Popover VibraScope vs. PyQt5 Hotkey TelemetryHex App Recreation",
    "domain": "Desktop Scientific Instrument & Binary Protocol Tooling Recreation",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "exploration_as_oracle_live_reference_apps",
        "gtk_popover_focus_loss_autohide",
        "global_hotkey_and_escape_modal_misrouting",
        "candidate_gui_window_launch_preemption",
    ),
    "roles": ("gtk_spectrum_developer", "qt_protocol_developer"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

VSCOPE_SEAL = "VSCOPE-CAL-8834"
WINDOW_GAINS = {
    "FLAT_TOP": 4.182,
    "BLACKMAN_HARRIS": 2.794,
    "KAISER_B9": 3.126,
}
BPFO_ORDER = 3.584

THEX_SEAL = "THEX-SPEC-5192"
CHAN_SCALES: dict[int, tuple[str, float, float]] = {
    0: ("BUS_VOLT_V", 0.0125, 28.0),
    1: ("COIL_TEMP_C", 0.0400, -15.0),
    2: ("GYRO_DPS", 0.0250, 0.0),
    3: ("THRUST_MN", 0.1500, 50.0),
}


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def _generate_turbine_channels() -> list[dict[str, Any]]:
    rng = random.Random(20261122)
    modes = ("FLAT_TOP", "BLACKMAN_HARRIS", "KAISER_B9")
    rows: list[dict[str, Any]] = []
    specs = [
        (1800, "FLAT_TOP", 0.18, 0.86, 0.17),         # crest 4.78, corr_bpfo 0.711 -> CRITICAL_FAULT
        (2400, "BLACKMAN_HARRIS", 0.22, 0.62, 0.09),  # crest 2.82, corr_bpfo 0.251 -> NOMINAL
        (3000, "KAISER_B9", 0.19, 0.70, 0.13),        # crest 3.68, corr_bpfo 0.406 -> EARLY_WEAR
        (1500, "FLAT_TOP", 0.16, 0.48, 0.06),         # NOMINAL
        (3600, "BLACKMAN_HARRIS", 0.25, 1.15, 0.24),  # crest 4.60, corr_bpfo 0.671 -> CRITICAL_FAULT
        (2100, "KAISER_B9", 0.21, 0.64, 0.14),        # corr_bpfo 0.438 -> EARLY_WEAR
        (1800, "BLACKMAN_HARRIS", 0.17, 0.51, 0.08),  # NOMINAL
        (2700, "FLAT_TOP", 0.20, 0.91, 0.16),         # crest 4.55, corr_bpfo 0.669 -> CRITICAL_FAULT
        (3300, "KAISER_B9", 0.23, 0.81, 0.10),        # crest 3.52 -> EARLY_WEAR
        (1200, "FLAT_TOP", 0.14, 0.39, 0.05),         # NOMINAL
        (2400, "KAISER_B9", 0.22, 0.98, 0.21),        # crest 4.45, corr_bpfo 0.656 -> CRITICAL_FAULT
        (1950, "BLACKMAN_HARRIS", 0.18, 0.55, 0.15),  # corr_bpfo 0.419 -> EARLY_WEAR
        (2850, "FLAT_TOP", 0.15, 0.44, 0.07),         # NOMINAL
        (3150, "BLACKMAN_HARRIS", 0.24, 0.72, 0.11),  # NOMINAL
        (1650, "KAISER_B9", 0.20, 0.71, 0.09),        # crest 3.55 -> EARLY_WEAR
        (3450, "FLAT_TOP", 0.19, 0.85, 0.12),         # crest 4.47, corr_bpfo 0.502 (<0.62!) -> EARLY_WEAR
    ]
    for i, (rpm, wm, rms, pk, bp) in enumerate(specs, 1):
        _ = rng.random()
        rows.append({
            "channel_id": f"CH-{i:02d}",
            "rpm": rpm,
            "window_mode": wm,
            "raw_rms_g": rms,
            "raw_peak_g": pk,
            "raw_bpfo_g": bp,
        })
    return rows


TURBINE_CHANNELS = _generate_turbine_channels()


def _compute_vibrascope_oracle() -> dict[str, Any]:
    verdicts: dict[str, str] = {}
    corr_bpfo_map: dict[str, float] = {}
    crit: list[str] = []
    wear: list[str] = []
    for r in TURBINE_CHANNELS:
        cid = r["channel_id"]
        g = WINDOW_GAINS[r["window_mode"]]
        crest = r["raw_peak_g"] / r["raw_rms_g"]
        c_bpfo = round(r["raw_bpfo_g"] * g, 4)
        corr_bpfo_map[cid] = c_bpfo
        if crest >= 4.35 and c_bpfo >= 0.62:
            st = "CRITICAL_FAULT"
            crit.append(cid)
        elif crest >= 3.40 or c_bpfo >= 0.38:
            st = "EARLY_WEAR"
            wear.append(cid)
        else:
            st = "NOMINAL"
        verdicts[cid] = st
    return {
        "calibration_seal": VSCOPE_SEAL,
        "window_gains": WINDOW_GAINS,
        "bpfo_order_ratio": BPFO_ORDER,
        "channel_verdicts": verdicts,
        "critical_channels": sorted(crit),
        "early_wear_channels": sorted(wear),
        "_corr_bpfo_map": corr_bpfo_map,
    }


VSCOPE_ORACLE = _compute_vibrascope_oracle()


def _build_downlink_packets() -> tuple[bytes, dict[str, Any]]:
    rng = random.Random(20260819)
    raw_bytes = bytearray()
    crc_err_seqs: list[int] = []
    dummy_seqs: list[int] = []
    chan_vals: dict[str, list[float]] = {v[0]: [] for v in CHAN_SCALES.values()}
    valid_op = 0

    for seq in range(1, 41):
        chan = (seq - 1) % 4
        raw_i16 = rng.randint(-1200, 2600)
        flags = 0x01
        if seq in (6, 15, 27, 34):
            flags |= 0x04  # CALIBRATION_DUMMY bit
        hdr = struct.pack(">HHBBh", 0xA55A, seq, chan, flags, raw_i16)
        crc = crc16_modbus(hdr)
        if seq in (4, 13, 22, 31, 38):
            crc ^= 0x00FF  # Inject CRC corruption
            crc_err_seqs.append(seq)
        elif flags & 0x04:
            dummy_seqs.append(seq)
        else:
            valid_op += 1
            cname, sc, off = CHAN_SCALES[chan]
            chan_vals[cname].append(raw_i16 * sc + off)
        raw_bytes.extend(hdr + struct.pack(">H", crc))

    means = {k: round(sum(vs) / len(vs), 3) for k, vs in chan_vals.items()}
    return bytes(raw_bytes), {
        "protocol_seal": THEX_SEAL,
        "total_frames": 40,
        "valid_operational_count": valid_op,
        "crc_error_seqs": sorted(crc_err_seqs),
        "dummy_excluded_seqs": sorted(dummy_seqs),
        "channel_means": means,
    }


DOWNLINK_BYTES, THEX_ORACLE = _build_downlink_packets()


REF_VIBRASCOPE_GTK_PY = f"""import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

class VibraRefWin(Gtk.Window):
    def __init__(self):
        super().__init__(title="VibraScope Reference")
        self.set_default_size(880, 760)
        hb = Gtk.HeaderBar(title="VibraScope Reference", subtitle="Turbine Bearing Envelope Analyzer")
        hb.set_show_close_button(False)
        self.set_titlebar(hb)

        self.menu_btn = Gtk.MenuButton(label="Calibration & Gains (F10)")
        pop = Gtk.Popover()
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=12)
        pbox.pack_start(Gtk.Label(label="Proprietary Window Amplitude Correction Gains:"), False, False, 0)
        pbox.pack_start(Gtk.Label(label="FLAT_TOP = 4.182   |   BLACKMAN_HARRIS = 2.794   |   KAISER_B9 = 3.126"), False, False, 0)
        pbox.pack_start(Gtk.Label(label="Calibration Seal: {VSCOPE_SEAL}"), False, False, 0)
        pop.add(pbox)
        pbox.show_all()
        self.menu_btn.set_popover(pop)
        hb.pack_start(self.menu_btn)

        rules_btn = Gtk.Button(label="Bearing Fault Rules (Ctrl+K)")
        rules_btn.connect("clicked", self.open_rules)
        hb.pack_end(rules_btn)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
        vbox.pack_start(Gtk.Label(label="Live Reference Instrument — Open F10 Popover for Window Gains & Seal; Press Ctrl+K for Bearing Fault Rules."), False, False, 4)

        store = Gtk.ListStore(str, int, str, str)
        store.append(["CH-01", 1800, "FLAT_TOP", "Sample Preview Row — Load /workspace/turbine_captures.csv in your recreated app"])
        store.append(["CH-02", 2400, "BLACKMAN_HARRIS", "Use corr_bpfo_g = raw_bpfo_g * window_gain; crest = raw_peak_g / raw_rms_g"])
        tv = Gtk.TreeView(model=store)
        for idx, col_t in enumerate(("Channel", "RPM", "Window", "Notes")):
            ren = Gtk.CellRendererText()
            tv.append_column(Gtk.TreeViewColumn(col_t, ren, text=idx))
        vbox.pack_start(tv, True, True, 0)
        self.add(vbox)
        self.connect("key-press-event", self.on_key)

    def on_key(self, _w, ev):
        keyname = Gdk.keyval_name(ev.keyval) or ""
        ctrl = bool(ev.state & Gdk.ModifierType.CONTROL_MASK)
        if keyname == "F10":
            self.menu_btn.set_active(not self.menu_btn.get_active())
            return True
        if ctrl and keyname.lower() == "k":
            self.open_rules(None)
            return True
        return False

    def open_rules(self, _btn):
        dlg = Gtk.Dialog(title="VibraScope Bearing Fault Rules", transient_for=self, flags=0)
        dlg.add_button("Close", Gtk.ResponseType.CLOSE)
        box = dlg.get_content_area()
        box.set_spacing(8)
        for ln in (
            "1. BPFO Harmonic Order Ratio: bpfo_hz = (rpm / 60.0) * 3.584",
            "2. Corrected BPFO Amplitude: corr_bpfo_g = raw_bpfo_g * window_gain",
            "3. Crest Factor: crest_factor = raw_peak_g / raw_rms_g",
            "4. Severity Classification:",
            "   - CRITICAL_FAULT : crest_factor >= 4.35 AND corr_bpfo_g >= 0.62",
            "   - EARLY_WEAR     : not CRITICAL_FAULT, and (crest_factor >= 3.40 OR corr_bpfo_g >= 0.38)",
            "   - NOMINAL        : otherwise",
        ):
            lbl = Gtk.Label(label=ln, xalign=0.0)
            box.pack_start(lbl, False, False, 2)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

win = VibraRefWin()
win.move(20, 35)
win.show_all()
Gtk.main()
"""


REF_TELEMETRYHEX_QT_PY = f"""import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QDialog, QShortcut
from PyQt5.QtGui import QKeySequence

class TelemetryRefWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TelemetryHex Reference")
        self.setGeometry(950, 35, 930, 760)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        hdr = QHBoxLayout()
        b_crc = QPushButton("CRC & Frame Spec (Alt+D)")
        b_crc.clicked.connect(self.show_crc_spec)
        b_scl = QPushButton("Channel Affine Scales (Ctrl+G)")
        b_scl.clicked.connect(self.show_scale_spec)
        hdr.addWidget(b_crc)
        hdr.addWidget(b_scl)
        lay.addLayout(hdr)
        lay.addWidget(QLabel("Reference Downlink Decoder — Inspect Alt+D & Ctrl+G dialogs to recreate TelemetryHex Inspector."))
        tbl = QTableWidget(4, 3)
        tbl.setHorizontalHeaderLabels(["Field Bytes", "Big-Endian Type", "Description"])
        for r, row in enumerate([
            ("0..1 / 2..3", "uint16 sync / uint16 seq", "Sync word 0xA55A, 1-based packet sequence"),
            ("4 / 5", "uint8 chan / uint8 flags", "Channel 0..3; bit 0x04 = CALIBRATION_DUMMY"),
            ("6..7", "int16 raw_sample", "Signed 16-bit sensor ADC count"),
            ("8..9", "uint16 crc16", "Trailing 16-bit frame check word (see Alt+D)"),
        ]):
            for c, val in enumerate(row):
                tbl.setItem(r, c, QTableWidgetItem(val))
        tbl.resizeColumnsToContents()
        lay.addWidget(tbl)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Alt+D"), self, activated=self.show_crc_spec)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.show_scale_spec)

    def show_crc_spec(self):
        d = QDialog(self)
        d.setWindowTitle("TelemetryHex Frame & CRC Specification")
        v = QVBoxLayout(d)
        for s in (
            "Frame Size: Fixed 10 bytes big-endian (>HHBBhH)",
            "Sync Word: 0xA55A | Protocol Seal: {THEX_SEAL}",
            "CRC Algorithm: CRC-16/MODBUS over bytes 0..7 (init=0xFFFF, reflected poly=0xA001)",
            "Operational Filter: Reject bad CRC first; then exclude frames where (flags & 0x04) != 0 (CALIBRATION_DUMMY).",
        ):
            v.addWidget(QLabel(s))
        btn = QPushButton("Close (Esc)")
        btn.clicked.connect(d.accept)
        v.addWidget(btn)
        d.exec_()

    def show_scale_spec(self):
        d = QDialog(self)
        d.setWindowTitle("TelemetryHex Channel Engineering Scales")
        v = QVBoxLayout(d)
        for s in (
            "Affine Conversion: eng_value = raw_i16 * scale + offset",
            "  chan 0 -> BUS_VOLT_V  : scale = 0.0125, offset = +28.0",
            "  chan 1 -> COIL_TEMP_C : scale = 0.0400, offset = -15.0",
            "  chan 2 -> GYRO_DPS    : scale = 0.0250, offset =   0.0",
            "  chan 3 -> THRUST_MN   : scale = 0.1500, offset = +50.0",
        ):
            v.addWidget(QLabel(s))
        btn = QPushButton("Close (Esc)")
        btn.clicked.connect(d.accept)
        v.addWidget(btn)
        d.exec_()

app = QApplication(sys.argv)
w = TelemetryRefWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Scientific Instrument Recreation Work Order — {b}gtk_spectrum_developer{b}",
        "",
        "## Scope & Deliverables",
        f"A live reference desktop application (**VibraScope Reference**) is running on the workstation display. Its source code is not stored in {b}/workspace{b}—inspect the running application (including its {b}F10{b} calibration popover and {b}Ctrl+K{b} bearing fault rules dialog) to determine its exact signal-processing constants and classification thresholds.",
        "",
        "Deliverables in `/workspace`:",
        f"1. **Working Desktop GUI Application ({b}/workspace/vibrascope_recreated.py{b})**:",
        f"   - Executable via {b}python3 /workspace/vibrascope_recreated.py{b} on X11, opening a main window titled **{b}VibraScope Inspector{b}** displaying the 16 analyzed channels from {b}/workspace/turbine_captures.csv{b} along with their corrected BPFO amplitudes, crest factors, and fault verdicts.",
        f"2. **Visual Verification Capture ({b}/workspace/vibrascope_ui.png{b})**:",
        f"   - Launch your {b}VibraScope Inspector{b} window and save a clean PNG screenshot of it (`>= 500 x 350` px) to {b}/workspace/vibrascope_ui.png{b}.",
        f"3. **Batch Analysis Output ({b}/workspace/VIBRASCOPE_REPORT.json{b})**:",
        f"   - Process all 16 rows in {b}/workspace/turbine_captures.csv{b} using the exact reference rules and save JSON with keys:",
        f"     - {b}\"calibration_seal\"{b}: exact calibration seal string from the reference {b}F10{b} popover",
        f"     - {b}\"window_gains\"{b}: object mapping {b}\"FLAT_TOP\"{b}, {b}\"BLACKMAN_HARRIS\"{b}, {b}\"KAISER_B9\"{b} to their float gains",
        f"     - {b}\"bpfo_order_ratio\"{b}: float BPFO harmonic ratio from the {b}Ctrl+K{b} dialog",
        f"     - {b}\"channel_verdicts\"{b}: object mapping {b}\"CH-01\"..\"CH-16\"{b} to {b}\"CRITICAL_FAULT\"{b}, {b}\"EARLY_WEAR\"{b}, or {b}\"NOMINAL\"{b}",
        f"     - {b}\"critical_channels\"{b}: sorted list of channel IDs classified {b}\"CRITICAL_FAULT\"{b}",
        f"     - {b}\"early_wear_channels\"{b}: sorted list of channel IDs classified {b}\"EARLY_WEAR\"{b}",
        "",
    ])

    role_b = "\n".join([
        f"# Downlink Protocol Inspector Recreation Work Order — {b}qt_protocol_developer{b}",
        "",
        "## Scope & Deliverables",
        f"A live reference desktop application (**TelemetryHex Reference**) is running on the workstation display. Its source code is not stored in {b}/workspace{b}—inspect the running application (including its {b}Alt+D{b} frame/CRC specification dialog and {b}Ctrl+G{b} channel affine scale dialog) to determine its exact binary packet format, CRC check, dummy-frame filter, and engineering conversions.",
        "",
        "Deliverables in `/workspace`:",
        f"1. **Working Desktop GUI Application ({b}/workspace/telemetryhex_recreated.py{b})**:",
        f"   - Executable via {b}python3 /workspace/telemetryhex_recreated.py{b} on X11, opening a main window titled **{b}TelemetryHex Inspector{b}** displaying decoded packets and channel summaries for {b}/workspace/downlink_capture.bin{b}.",
        f"2. **Visual Verification Capture ({b}/workspace/telemetryhex_ui.png{b})**:",
        f"   - Launch your {b}TelemetryHex Inspector{b} window and save a clean PNG screenshot of it (`>= 500 x 350` px) to {b}/workspace/telemetryhex_ui.png{b}.",
        f"3. **Decoded Telemetry Summary ({b}/workspace/DECODED_TELEMETRY.json{b})**:",
        f"   - Decode all 40 packets in {b}/workspace/downlink_capture.bin{b} and save JSON with exact keys:",
        f"     - {b}\"protocol_seal\"{b}: exact protocol seal string from the reference {b}Alt+D{b} dialog",
        f"     - {b}\"total_frames\"{b}: integer total packets (`40`)",
        f"     - {b}\"valid_operational_count\"{b}: integer count of CRC-valid non-dummy packets",
        f"     - {b}\"crc_error_seqs\"{b}: sorted integer list of 1-based {b}seq{b} numbers failing CRC",
        f"     - {b}\"dummy_excluded_seqs\"{b}: sorted integer list of CRC-valid {b}seq{b} numbers excluded as {b}CALIBRATION_DUMMY{b}",
        f"     - {b}\"channel_means\"{b}: object mapping {b}\"BUS_VOLT_V\"{b}, {b}\"COIL_TEMP_C\"{b}, {b}\"GYRO_DPS\"{b}, {b}\"THRUST_MN\"{b} to their mean engineering values across valid operational packets (rounded to 3 decimal places)",
        "",
    ])
    return {"gtk_spectrum_developer": role_a, "qt_protocol_developer": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["gtk_spectrum_developer"]
    ws_b = workspace_map["qt_protocol_developer"]
    ws_a.mkdir(parents=True, exist_ok=True)
    ws_b.mkdir(parents=True, exist_ok=True)

    lines = ["channel_id,rpm,window_mode,raw_rms_g,raw_peak_g,raw_bpfo_g"]
    for r in TURBINE_CHANNELS:
        lines.append(f"{r['channel_id']},{r['rpm']},{r['window_mode']},{r['raw_rms_g']:.4f},{r['raw_peak_g']:.4f},{r['raw_bpfo_g']:.4f}")
    (ws_a / "turbine_captures.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (ws_b / "downlink_capture.bin").write_bytes(DOWNLINK_BYTES)

    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "ref_vibrascope.py").write_text(REF_VIBRASCOPE_GTK_PY, encoding="utf-8")
    (state_dir / "ref_telemetryhex.py").write_text(REF_TELEMETRYHEX_QT_PY, encoding="utf-8")
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0, "misrouted_hotkeys_sim": 0})

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
    boot_file.write_text('{"mode":"native_ref_apps"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    cmd = (
        "su -s /bin/bash user -c '"
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
        "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
        "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1; "
        f"nohup python3 {state_dir}/ref_vibrascope.py >/tmp/ref_vscope.log 2>&1 </dev/null & "
        f"nohup python3 {state_dir}/ref_telemetryhex.py >/tmp/ref_thex.log 2>&1 </dev/null &'"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=20)
    time.sleep(2.0)


def _verify_gui_script_launches(script_path: Path, expected_title_substr: str) -> bool:
    if not script_path.is_file():
        return False
    probe_sh = (
        f"xvfb-run -a -s '-screen 0 1280x800x24' bash -lc '"
        f"python3 {script_path} >/tmp/gui_probe.log 2>&1 & pid=$!; "
        "ok=0; for _i in $(seq 1 16); do "
        f"  if xdotool search --name \"{expected_title_substr}\" >/dev/null 2>&1; then ok=1; break; fi; "
        "  sleep 0.3; "
        "done; kill $pid 2>/dev/null || true; exit $((1 - ok))'"
    )
    cp = subprocess.run(["bash", "-lc", probe_sh], capture_output=True, timeout=20)
    return cp.returncode == 0


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image
    ws_a = workspace_map["gtk_spectrum_developer"]
    ws_b = workspace_map["qt_protocol_developer"]

    rep_a = read_json_safe(ws_a / "VIBRASCOPE_REPORT.json")
    ui_a_ok = False
    if (ws_a / "vibrascope_ui.png").is_file():
        try:
            with Image.open(ws_a / "vibrascope_ui.png") as im:
                ui_a_ok = im.size[0] >= 500 and im.size[1] >= 350
        except Exception:
            ui_a_ok = False
    app_a_launches = _verify_gui_script_launches(ws_a / "vibrascope_recreated.py", "VibraScope Inspector")
    wg = rep_a.get("window_gains") or {}
    gains_ok = all(isinstance(wg.get(k), (int, float)) and abs(float(wg[k]) - v) <= 0.005 for k, v in WINDOW_GAINS.items())
    cv = rep_a.get("channel_verdicts") or {}
    matched_verdicts = sum(1 for k, v in VSCOPE_ORACLE["channel_verdicts"].items() if cv.get(k) == v)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("app_a_launches_x11", app_a_launches, 0.20, "vibrascope_recreated.py missing or did not open 'VibraScope Inspector' window"),
        ("ui_a_screenshot", ui_a_ok, 0.10, "vibrascope_ui.png missing or < 500x350"),
        ("calibration_seal", rep_a.get("calibration_seal") == VSCOPE_SEAL, 0.15, f"calibration_seal={rep_a.get('calibration_seal')!r} != {VSCOPE_SEAL!r}"),
        ("window_gains", gains_ok, 0.15, "window_gains mismatch (F10 popover)"),
        ("bpfo_ratio", isinstance(rep_a.get("bpfo_order_ratio"), (int, float)) and abs(float(rep_a["bpfo_order_ratio"]) - BPFO_ORDER) <= 0.005, 0.10, "bpfo_order_ratio mismatch (Ctrl+K modal)"),
        ("verdicts_half", matched_verdicts >= 12, 0.10, f"Only {matched_verdicts}/16 channel_verdicts accurate"),
        ("verdicts_all", matched_verdicts == 16, 0.10, f"channel_verdicts {matched_verdicts}/16 != 16/16"),
        ("crit_and_wear_lists", rep_a.get("critical_channels") == VSCOPE_ORACLE["critical_channels"] and rep_a.get("early_wear_channels") == VSCOPE_ORACLE["early_wear_channels"], 0.10, "critical_channels or early_wear_channels mismatch"),
    ]

    rep_b = read_json_safe(ws_b / "DECODED_TELEMETRY.json")
    ui_b_ok = False
    if (ws_b / "telemetryhex_ui.png").is_file():
        try:
            with Image.open(ws_b / "telemetryhex_ui.png") as im:
                ui_b_ok = im.size[0] >= 500 and im.size[1] >= 350
        except Exception:
            ui_b_ok = False
    app_b_launches = _verify_gui_script_launches(ws_b / "telemetryhex_recreated.py", "TelemetryHex Inspector")
    cm = rep_b.get("channel_means") or {}
    means_matched = sum(
        1 for k, v in THEX_ORACLE["channel_means"].items()
        if isinstance(cm.get(k), (int, float)) and abs(float(cm[k]) - v) <= 0.02
    )

    checks_b: list[tuple[str, bool, float, str]] = [
        ("app_b_launches_x11", app_b_launches, 0.20, "telemetryhex_recreated.py missing or did not open 'TelemetryHex Inspector' window"),
        ("ui_b_screenshot", ui_b_ok, 0.10, "telemetryhex_ui.png missing or < 500x350"),
        ("protocol_seal", rep_b.get("protocol_seal") == THEX_SEAL, 0.15, f"protocol_seal={rep_b.get('protocol_seal')!r} != {THEX_SEAL!r}"),
        ("frame_counts", rep_b.get("total_frames") == 40 and rep_b.get("valid_operational_count") == THEX_ORACLE["valid_operational_count"], 0.12, "total_frames or valid_operational_count mismatch"),
        ("crc_error_seqs", rep_b.get("crc_error_seqs") == THEX_ORACLE["crc_error_seqs"], 0.13, "crc_error_seqs mismatch"),
        ("dummy_excluded_seqs", rep_b.get("dummy_excluded_seqs") == THEX_ORACLE["dummy_excluded_seqs"], 0.10, "dummy_excluded_seqs mismatch"),
        ("channel_means_partial", means_matched >= 2, 0.10, "channel_means missing/inaccurate"),
        ("channel_means_exact", means_matched == 4, 0.10, f"channel_means {means_matched}/4 != 4/4"),
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
    assert role in ("gtk_spectrum_developer", "qt_protocol_developer")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "gtk_spectrum_developer":
            (ws / "vibrascope_recreated.py").write_text(
                "import tkinter as tk\n"
                "r = tk.Tk(); r.title('VibraScope Inspector'); r.geometry('680x440+60+60')\n"
                "tk.Label(r, text='VibraScope Inspector — 16 Channels Reconciled').pack(pady=20)\n"
                "r.mainloop()\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "su", "-s", "/bin/bash", "user", "-c",
                    f"DISPLAY=:99 python3 {ws}/vibrascope_recreated.py >/tmp/vs_gt.log 2>&1 & pid=$!; sleep 0.9; "
                    f"wid=$(DISPLAY=:99 xdotool search --onlyvisible --name 'VibraScope Inspector' | tail -n 1); "
                    f"DISPLAY=:99 import -window \"$wid\" {ws}/vibrascope_ui.png; kill $pid 2>/dev/null || true",
                ],
                check=True, capture_output=True, timeout=15,
            )
            out_a = {k: v for k, v in VSCOPE_ORACLE.items() if not k.startswith("_")}
            write_json(ws / "VIBRASCOPE_REPORT.json", out_a)
        else:
            (ws / "telemetryhex_recreated.py").write_text(
                "import tkinter as tk\n"
                "r = tk.Tk(); r.title('TelemetryHex Inspector'); r.geometry('680x440+760+60')\n"
                "tk.Label(r, text='TelemetryHex Inspector — 40 Downlink Packets Decoded').pack(pady=20)\n"
                "r.mainloop()\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "su", "-s", "/bin/bash", "user", "-c",
                    f"DISPLAY=:99 python3 {ws}/telemetryhex_recreated.py >/tmp/th_gt.log 2>&1 & pid=$!; sleep 0.9; "
                    f"wid=$(DISPLAY=:99 xdotool search --onlyvisible --name 'TelemetryHex Inspector' | tail -n 1); "
                    f"DISPLAY=:99 import -window \"$wid\" {ws}/telemetryhex_ui.png; kill $pid 2>/dev/null || true",
                ],
                check=True, capture_output=True, timeout=15,
            )
            write_json(ws / "DECODED_TELEMETRY.json", THEX_ORACLE)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (Shared-Screen Track): Global F10/Escape hotkey collision hides VibraScope popover before seal read."""
    solve_role("gtk_spectrum_developer", workspace_map, port, careful_conc=False)
    solve_role("qt_protocol_developer", workspace_map, port, careful_conc=False)
    # Simulate focus switch to TelemetryHex causing F10 popover auto-hide & missed window gains/seal:
    ws_a = workspace_map["gtk_spectrum_developer"]
    rep_a = read_json_safe(ws_a / "VIBRASCOPE_REPORT.json")
    rep_a["calibration_seal"] = "MISSED_POPOVER_AUTOHIDE"
    rep_a["window_gains"] = {"FLAT_TOP": 1.0, "BLACKMAN_HARRIS": 1.0, "KAISER_B9": 1.0}
    write_json(ws_a / "VIBRASCOPE_REPORT.json", rep_a)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    st["misrouted_hotkeys_sim"] = int(st.get("misrouted_hotkeys_sim", 0)) + 2
    write_json(sp, st)

"""RBS-02: Focus-Loss Autohiding F10 CSD Popover vs. Multi-Mode Hex Editor Hotkeys Recreation.

Grounded in RecreationBench Empirical Laws (RB-B4 Spedread+Breathing & RB-B6 wxFormBuilder+wxMEdit):
  - LAW_1_KEYSTROKE_MISROUTING: HexPulse Editor requires iterative keyboard shortcuts (Alt+1/2/3,
    Ctrl+G, Ctrl+F, F6) that route to X11 active focus despite AT-SPI `app=` clicks.
  - LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH: CadenceReader uses client-side HeaderBar + modal
    autohiding `Gtk.Popover` menus (`F10` and `Ctrl+Shift+M`) that immediately vanish when peer
    actions shift X11 focus or map candidate windows onto `:99`.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
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

TASK_ID = "RBS-02"
PORTAL_PORT = 19302

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Autohiding F10 CSD Popover CadenceReader vs. Multi-Mode Hotkey HexPulse App Recreation",
    "domain": "Modern GTK HeaderBar Speed-Reading Studio & Binary Telemetry Hex Inspector Recreation",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_1_KEYSTROKE_MISROUTING",
        "LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
    ),
    "roles": ("csd_cadence_dev", "hex_packet_dev"),
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
            "slug": "csd_cadence_dev",
            "est_role_seconds": 520.0,
            "traits": [
                "autohide_popover_or_ephemeral_menu",
                "candidate_window_launch_on_shared_display",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "hex_packet_dev",
            "est_role_seconds": 540.0,
            "traits": [
                "iterative_keyboard_shortcuts",
                "atspi_click_plus_global_hotkeys",
                "candidate_window_launch_on_shared_display",
            ],
        },
    },
}

CADENCE_ORACLE = {
    "default_wpm": 340,
    "orp_short_idx": 1,
    "orp_medium_idx": 2,
    "orp_long_idx": 3,
    "comma_pause_mult": 1.6,
    "period_pause_mult": 2.5,
    "breathing_inhale_hold_exhale": "4-7-8",
    "popover_calibration_code": "CSD-ORP-6182",
}

# 32-byte canonical telemetry frame embedded inside HexPulse Editor
PACKET_BYTES = [
    0xA5, 0x5A, 0x02, 0x18, 0x00, 0x2C, 0x13, 0x88,
    0x4E, 0x45, 0x42, 0x37, 0x01, 0xF4, 0x00, 0xDC,
    0xDE, 0xAD, 0xBE, 0xEF, 0x00, 0x10, 0x27, 0x10,
    0x48, 0x58, 0x50, 0x32, 0x03, 0xE8, 0x9C, 0x41,
]

HEXPULSE_ORACLE = {
    "packet_length_bytes": 32,
    "sync_word_hex": "A55A",
    "ascii_tag_at_0x08": "NEB7",
    "uint16_be_at_0x06": 5000,
    "uint16_be_at_0x16": 10000,
    "deadbeef_offset_hex": "0x10",
    "crc16_xor_sum_hex": hex(sum(PACKET_BYTES) & 0xFFFF).upper().replace("0X", "0x"),
    "decoder_seal": "HEXP-DEC-4410",
}

CADENCE_GTK_SOURCE = f"""import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
GLib.set_prgname('cadencereader-studio')

ORACLE = {json.dumps(CADENCE_ORACLE)}
WORDS = ["Synchronize", "accessibility", "popovers", "carefully", "across", "shared", "workstations."]

class CadenceReaderWin(Gtk.Window):
    def __init__(self):
        super().__init__(title="CadenceReader Studio")
        self.set_default_size(760, 520)
        self.idx = 0

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.props.title = "CadenceReader Studio"
        hb.props.subtitle = "CSD Speed-Reader & 4-7-8 Breathing Timer"
        self.set_titlebar(hb)

        self.menu_btn = Gtk.MenuButton(label="Primary Menu (F10)")
        self.pop_main = Gtk.Popover()
        self.pop_main.set_modal(True)
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        pbox.set_margin_top(10); pbox.set_margin_bottom(10); pbox.set_margin_start(12); pbox.set_margin_end(12)
        pbox.add(Gtk.Label(label=f"Popover Calibration Code: {{ORACLE['popover_calibration_code']}}"))
        pbox.add(Gtk.Label(label="ORP Pivot Indices: len<=5 -> 1 | len 6..9 -> 2 | len>=10 -> 3"))
        pbox.add(Gtk.Label(label=f"Punctuation Multipliers: comma={{ORACLE['comma_pause_mult']}}x | period={{ORACLE['period_pause_mult']}}x"))
        pbox.show_all()
        self.pop_main.add(pbox)
        self.menu_btn.set_popover(self.pop_main)
        hb.pack_end(self.menu_btn)

        self.cad_btn = Gtk.MenuButton(label="Cadence Presets (F9)")
        self.pop_cad = Gtk.Popover()
        self.pop_cad.set_modal(True)
        cbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cbox.set_margin_top(10); cbox.set_margin_bottom(10); cbox.set_margin_start(12); cbox.set_margin_end(12)
        cbox.add(Gtk.Label(label=f"Default WPM: {{ORACLE['default_wpm']}}"))
        cbox.add(Gtk.Label(label=f"Breathing Cycle (Inhale-Hold-Exhale): {{ORACLE['breathing_inhale_hold_exhale']}}"))
        cbox.show_all()
        self.pop_cad.add(cbox)
        self.cad_btn.set_popover(self.pop_cad)
        hb.pack_start(self.cad_btn)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        vbox.set_margin_top(24); vbox.set_margin_bottom(18); vbox.set_margin_start(24); vbox.set_margin_end(24)
        self.add(vbox)

        self.word_lbl = Gtk.Label()
        vbox.pack_start(self.word_lbl, True, True, 0)

        ctrls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        b_prev = Gtk.Button(label="Prev Word")
        b_prev.connect("clicked", lambda *_: self.step(-1))
        b_next = Gtk.Button(label="Next Word (Space)")
        b_next.connect("clicked", lambda *_: self.step(1))
        ctrls.pack_start(b_prev, False, False, 0)
        ctrls.pack_start(b_next, False, False, 0)
        vbox.pack_start(ctrls, False, False, 0)

        self.status_lbl = Gtk.Label(label="WPM: 340 | Mode: ORP_ACTIVE | Press F10 or F9 for Popover Specs")
        vbox.pack_start(self.status_lbl, False, False, 0)
        self.connect("key-press-event", self.on_key)
        self.connect("focus-out-event", self.on_focus_out)
        self.render_word()

    def on_focus_out(self, *_a):
        self.pop_main.popdown()
        self.pop_cad.popdown()
        return False

    def on_key(self, _w, ev):
        from gi.repository import Gdk
        kn = Gdk.keyval_name(ev.keyval)
        if kn == "F10":
            self.pop_main.popup()
            return True
        if kn == "F9":
            self.pop_cad.popup()
            return True
        if kn == "space":
            self.step(1)
            return True
        return False

    def step(self, d):
        self.idx = (self.idx + d) % len(WORDS)
        self.render_word()

    def render_word(self):
        w = WORDS[self.idx]
        piv = 1 if len(w) <= 5 else (2 if len(w) <= 9 else 3)
        self.word_lbl.set_text(f"Token [{{self.idx+1}}/{{len(WORDS)}}]: {{w}} (ORP_idx={{piv}})")

w = CadenceReaderWin()
w.connect("destroy", Gtk.main_quit)
w.show_all()
Gtk.main()
"""

HEXPULSE_QT_SOURCE = f"""import json, sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QPlainTextEdit, QDialog, QShortcut, QLineEdit
)
from PyQt5.QtGui import QKeySequence, QFont

DATA = {json.dumps(PACKET_BYTES)}
ORACLE = {json.dumps(HEXPULSE_ORACLE)}

class HexPulseWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HexPulse Editor")
        self.resize(860, 580)
        self.mode = "HEX"
        cw = QWidget()
        lay = QVBoxLayout(cw)
        tbar = QHBoxLayout()
        for m, hk in (("TEXT", "Alt+1"), ("COLUMN", "Alt+2"), ("HEX", "Alt+3")):
            btn = QPushButton(f"{{m}} Mode ({{hk}})")
            btn.clicked.connect(lambda _=False, mv=m: self.set_mode(mv))
            tbar.addWidget(btn)
        b_go = QPushButton("Go to Offset (Ctrl+G)")
        b_go.clicked.connect(self.go_offset)
        b_dec = QPushButton("Frame Decoder (F6)")
        b_dec.clicked.connect(self.show_decoder)
        tbar.addWidget(b_go); tbar.addWidget(b_dec)
        lay.addLayout(tbar)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(QFont("Monospace", 11))
        lay.addWidget(self.view)

        self.status_lbl = QLabel()
        lay.addWidget(self.status_lbl)
        self.setCentralWidget(cw)

        QShortcut(QKeySequence("Alt+1"), self, activated=lambda: self.set_mode("TEXT"))
        QShortcut(QKeySequence("Alt+2"), self, activated=lambda: self.set_mode("COLUMN"))
        QShortcut(QKeySequence("Alt+3"), self, activated=lambda: self.set_mode("HEX"))
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.go_offset)
        QShortcut(QKeySequence("F6"), self, activated=self.show_decoder)
        self.set_mode("HEX")

    def set_mode(self, m):
        self.mode = m
        if m == "HEX":
            rows = []
            for off in range(0, len(DATA), 8):
                chunk = DATA[off:off+8]
                hx = " ".join(f"{{b:02X}}" for b in chunk)
                asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                rows.append(f"0x{{off:02X}}: {{hx:<23}} |{{asc}}|")
            self.view.setPlainText("\\n".join(rows))
        elif m == "COLUMN":
            rows = [f"Col[{{i:02d}}] = 0x{{b:02X}} ({{b:3d}})" for i, b in enumerate(DATA)]
            self.view.setPlainText("\\n".join(rows))
        else:
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in DATA)
            self.view.setPlainText(f"ASCII_PAYLOAD: {{asc}}")
        self.status_lbl.setText(f"ACTIVE_MODE={{m}} | Length={{len(DATA)}} bytes | Press Ctrl+G or F6")

    def go_offset(self):
        d = QDialog(self)
        d.setWindowTitle("Go to Byte Offset")
        d.setModal(True)
        v = QVBoxLayout(d)
        ed = QLineEdit("0x10")
        lbl = QLabel("Offset 0x10 -> 4-byte marker DE AD BE EF; Offset 0x06 -> uint16_be 5000; Offset 0x16 -> uint16_be 10000")
        v.addWidget(ed); v.addWidget(lbl)
        bc = QPushButton("Close")
        bc.clicked.connect(d.accept)
        v.addWidget(bc)
        d.exec_()

    def show_decoder(self):
        d = QDialog(self)
        d.setWindowTitle("Telemetry Frame Header Decoder")
        d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"Sync Word: {{ORACLE['sync_word_hex']}} | ASCII Tag @0x08: {{ORACLE['ascii_tag_at_0x08']}}"))
        v.addWidget(QLabel(f"Checksum (16-bit byte sum): {{ORACLE['crc16_xor_sum_hex']}}"))
        v.addWidget(QLabel(f"Decoder Seal: {{ORACLE['decoder_seal']}}"))
        bc = QPushButton("Close")
        bc.clicked.connect(d.accept)
        v.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
app.setApplicationName("hexpulse-editor")
w = HexPulseWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# CSD Speed-Reader & Breathing Studio Recreation Work Order — {b}csd_cadence_dev{b}",
        "",
        "## Objective",
        f"Explore the live **CadenceReader Studio** GTK HeaderBar application on the workstation (no reference source code exists in {b}/workspace{b}) and recreate both its runnable desktop GUI and specification manifest.",
        "",
        "## Required Deliverables",
        f"1. **Standalone Runnable GUI Application ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Build an executable launcher {b}/workspace/recreation/run_app.sh{b} opening a window titled {b}CadenceReader Studio{b} (`>= 680 x 440` px) with HeaderBar/toolbar buttons, ORP word stepping (`Prev Word`, `Next Word` / `Space`), and both popover menus (`Primary Menu` on `F10` and `Cadence Presets` on `F9`).",
        f"2. **Specification Manifest ({b}/workspace/SPEC_CADENCE.json{b})**:",
        "   - Inspect both popovers (`F10` and `F9`) and record exact keys:",
        f"     - {b}\"default_wpm\"{b} (int), {b}\"orp_short_idx\"{b} (int), {b}\"orp_medium_idx\"{b} (int), {b}\"orp_long_idx\"{b} (int)",
        f"     - {b}\"comma_pause_mult\"{b} (float), {b}\"period_pause_mult\"{b} (float), {b}\"breathing_inhale_hold_exhale\"{b} (string), {b}\"popover_calibration_code\"{b} (string)",
        "",
    ])

    role_b = "\n".join([
        f"# Multi-Mode Binary Hex Inspector Recreation Work Order — {b}hex_packet_dev{b}",
        "",
        "## Objective",
        f"Explore the live **HexPulse Editor** desktop application on the workstation (no reference source code exists in {b}/workspace{b}) across its `TEXT` (`Alt+1`), `COLUMN` (`Alt+2`), and `HEX` (`Alt+3`) modes plus its `Go to Offset` (`Ctrl+G`) and `Frame Decoder` (`F6`) dialogs, then recreate both the GUI application and packet specification manifest.",
        "",
        "## Required Deliverables",
        f"1. **Standalone Runnable GUI Application ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Build an executable launcher {b}/workspace/recreation/run_app.sh{b} opening a window titled {b}HexPulse Editor{b} (`>= 720 x 460` px) supporting `TEXT` / `COLUMN` / `HEX` mode switching (`Alt+1`, `Alt+2`, `Alt+3`), `Ctrl+G` offset lookup, and `F6` Frame Decoder over the 32-byte telemetry packet.",
        f"2. **Packet Specification Manifest ({b}/workspace/SPEC_HEXPULSE.json{b})**:",
        "   - Record exact keys from the 32-byte packet and `F6` / `Ctrl+G` dialogs:",
        f"     - {b}\"packet_length_bytes\"{b} (int), {b}\"sync_word_hex\"{b} (string), {b}\"ascii_tag_at_0x08\"{b} (string)",
        f"     - {b}\"uint16_be_at_0x06\"{b} (int), {b}\"uint16_be_at_0x16\"{b} (int), {b}\"deadbeef_offset_hex\"{b} (string), {b}\"crc16_xor_sum_hex\"{b} (string), {b}\"decoder_seal\"{b} (string)",
        "",
    ])
    return {"csd_cadence_dev": role_a, "hex_packet_dev": role_b}


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
    stage_private_studio_script(state_dir, "cadence_ref.py", CADENCE_GTK_SOURCE)
    stage_private_studio_script(state_dir, "hexpulse_ref.py", HEXPULSE_QT_SOURCE)
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
    boot_file.write_text('{"mode":"rbs02_csd_hex"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_isolated_studio_scripts(state_dir, ["cadence_ref.py", "hexpulse_ref.py"], wait_s=2.4)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["csd_cadence_dev"]
    ws_b = workspace_map["hex_packet_dev"]

    spec_a = read_json_safe(ws_a / "SPEC_CADENCE.json")
    gui_a = evaluate_recreated_gui_app(
        ws_a / "recreation/run_app.sh",
        disp_num=115,
        expected_title_sub="CadenceReader",
        key_sequences=[("f10", "F10"), ("Escape", "Escape"), ("f9", "F9"), ("space", "space")],
    )
    ax_a_init = gui_a["initial_ax_text"]
    ax_a_all = ax_a_init + "\n" + "\n".join(gui_a["after_keys_ax"].values())

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_script_exists", gui_a["script_exists"], 0.06, "Missing /workspace/recreation/run_app.sh"),
        ("a_win_mapped", gui_a["window_mapped"] and "cadencereader" in gui_a["window_title"].lower(), 0.08, "CadenceReader window not mapped"),
        ("a_visual_layout", gui_a["visual_nonblank"] and gui_a["win_w"] >= 620 and gui_a["win_h"] >= 400, 0.08, "CadenceReader visual dimensions/colors check failed"),
        ("a_ax_header_buttons", any(k in ax_a_all.lower() for k in ("primary menu", "cadence", "f10", "f9")), 0.08, "AT-SPI missing HeaderBar menu/cadence buttons"),
        ("a_ax_word_token", "orp" in ax_a_all.lower() or "340" in ax_a_all, 0.07, "AT-SPI missing ORP word display or WPM status"),
        ("a_ax_f10_popover", "CSD-ORP-6182" in ax_a_all or "1.6" in ax_a_all, 0.08, "F10 popover failed AT-SPI inspection"),
        ("a_ax_f9_popover", "4-7-8" in ax_a_all, 0.07, "F9 cadence popover missing 4-7-8 breathing cycle"),
        ("a_ax_step_controls", "next" in ax_a_all.lower() and "prev" in ax_a_all.lower(), 0.06, "Missing Prev/Next stepping buttons"),
        ("a_spec_wpm", spec_a.get("default_wpm") == 340, 0.06, "SPEC default_wpm != 340"),
        ("a_spec_orp_indices", (spec_a.get("orp_short_idx"), spec_a.get("orp_medium_idx"), spec_a.get("orp_long_idx")) == (1, 2, 3), 0.07, "SPEC ORP indices != (1, 2, 3)"),
        ("a_spec_pauses", spec_a.get("comma_pause_mult") == 1.6 and spec_a.get("period_pause_mult") == 2.5, 0.07, "SPEC punctuation pause multipliers mismatch (F10 autohide popover)"),
        ("a_spec_breathing", spec_a.get("breathing_inhale_hold_exhale") == "4-7-8", 0.07, "SPEC breathing_inhale_hold_exhale != '4-7-8' (F9 autohide popover)"),
        ("a_spec_cal_code", spec_a.get("popover_calibration_code") == CADENCE_ORACLE["popover_calibration_code"], 0.09, "SPEC popover_calibration_code != 'CSD-ORP-6182'"),
        ("a_spec_complete", len(spec_a) >= 8, 0.06, "SPEC_CADENCE.json incomplete"),
    ]

    spec_b = read_json_safe(ws_b / "SPEC_HEXPULSE.json")
    gui_b = evaluate_recreated_gui_app(
        ws_b / "recreation/run_app.sh",
        disp_num=116,
        expected_title_sub="HexPulse",
        key_sequences=[("alt_1", "alt+1"), ("alt_3", "alt+3"), ("ctrl_g", "ctrl+g"), ("Escape", "Escape"), ("f6", "F6")],
    )
    ax_b_init = gui_b["initial_ax_text"]
    ax_b_all = ax_b_init + "\n" + "\n".join(gui_b["after_keys_ax"].values())

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_script_exists", gui_b["script_exists"], 0.06, "Missing /workspace/recreation/run_app.sh"),
        ("b_win_mapped", gui_b["window_mapped"] and "hexpulse" in gui_b["window_title"].lower(), 0.08, "HexPulse window not mapped"),
        ("b_visual_layout", gui_b["visual_nonblank"] and gui_b["win_w"] >= 660 and gui_b["win_h"] >= 420, 0.08, "HexPulse visual dimensions/colors check failed"),
        ("b_ax_modes", all(k in ax_b_all.lower() for k in ("text", "column", "hex")), 0.08, "AT-SPI missing TEXT/COLUMN/HEX mode controls"),
        ("b_ax_hex_dump", ("A5" in ax_b_all and "NEB7" in ax_b_all), 0.08, "Hex/ASCII view missing A5 5A or NEB7 payload"),
        ("b_ax_ctrl_g_dialog", ("0x10" in ax_b_all or "Offset" in gui_b["after_keys_ax"].get("ctrl_g", "")), 0.07, "Ctrl+G Go-to-Offset dialog failed AT-SPI check"),
        ("b_ax_f6_decoder", ("HEXP-DEC-4410" in ax_b_all or "Decoder" in gui_b["after_keys_ax"].get("f6", "")), 0.08, "F6 Frame Decoder dialog failed AT-SPI check"),
        ("b_spec_len_sync", spec_b.get("packet_length_bytes") == 32 and str(spec_b.get("sync_word_hex", "")).upper().replace("0X", "") == "A55A", 0.07, "SPEC packet_length_bytes or sync_word_hex mismatch"),
        ("b_spec_ascii_tag", spec_b.get("ascii_tag_at_0x08") == "NEB7", 0.07, "SPEC ascii_tag_at_0x08 != 'NEB7'"),
        ("b_spec_u16_06", spec_b.get("uint16_be_at_0x06") == 5000, 0.06, "SPEC uint16_be_at_0x06 != 5000"),
        ("b_spec_u16_16", spec_b.get("uint16_be_at_0x16") == 10000, 0.06, "SPEC uint16_be_at_0x16 != 10000"),
        ("b_spec_deadbeef", str(spec_b.get("deadbeef_offset_hex", "")).lower() == "0x10", 0.07, "SPEC deadbeef_offset_hex != '0x10'"),
        ("b_spec_crc_sum", str(spec_b.get("crc16_xor_sum_hex", "")).lower() == HEXPULSE_ORACLE["crc16_xor_sum_hex"].lower(), 0.07, "SPEC crc16_xor_sum_hex mismatch"),
        ("b_spec_decoder_seal", spec_b.get("decoder_seal") == HEXPULSE_ORACLE["decoder_seal"], 0.07, "SPEC decoder_seal != 'HEXP-DEC-4410' (F6 modal)"),
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
    del port
    assert role in ("csd_cadence_dev", "hex_packet_dev")
    ws = workspace_map[role]
    rec = ws / "recreation"
    rec.mkdir(parents=True, exist_ok=True)

    def _work() -> None:
        if role == "csd_cadence_dev":
            (rec / "app.py").write_text(CADENCE_GTK_SOURCE, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/app.py\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)
            write_json(ws / "SPEC_CADENCE.json", CADENCE_ORACLE)
        else:
            (rec / "app.py").write_text(HEXPULSE_QT_SOURCE, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/app.py\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)
            write_json(ws / "SPEC_HEXPULSE.json", HEXPULSE_ORACLE)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_1 + LAW_3): Peer focus steal auto-dismisses F10 CSD popover and misroutes F6 key."""
    solve_role("csd_cadence_dev", workspace_map, port, careful_conc=False)
    solve_role("hex_packet_dev", workspace_map, port, careful_conc=False)
    bad_a = dict(CADENCE_ORACLE)
    bad_a["popover_calibration_code"] = "POPOVER_AUTOHIDDEN_ON_FOCUS_LOSS"
    bad_a["comma_pause_mult"] = 1.0
    write_json(workspace_map["csd_cadence_dev"] / "SPEC_CADENCE.json", bad_a)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

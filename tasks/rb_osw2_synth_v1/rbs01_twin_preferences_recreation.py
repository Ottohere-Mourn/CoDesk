"""RBS-01: Twin 'Preferences' Modal & File-Chooser Hijack in Full Desktop App Recreation.

Grounded in RecreationBench Empirical Laws (RB-B2 FSearch+Xarchiver & RB-B3 DB Browser+KSudoku):
  - LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP: Both VaultSearch Studio (GTK3) and LogicGrid Studio
    (PyQt5) spawn modal dialogs titled exactly "Preferences" (Ctrl+P) plus secondary modal
    "Choose Archive Preset" (Ctrl+O) / "Cage Sum Inspector" (Ctrl+K) dialogs onto :99.
  - LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH: Reference binaries run under isolated `studio_ui`
    with zero source code in role workspaces; both roles must explore, implement standalone
    GUI apps (`/workspace/recreation/run_app.sh`), and launch candidate windows onto `:99`.
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

TASK_ID = "RBS-01"
PORTAL_PORT = 19301

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Twin 'Preferences' Modal & File-Chooser Hijack: GTK3 VaultSearch vs. Qt5 LogicGrid App Recreation",
    "domain": "Desktop Archive/Search Utility & Two-Stage Constraint Puzzle GUI Recreation",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("gtk_vaultsearch_dev", "qt_logicgrid_dev"),
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
            "slug": "gtk_vaultsearch_dev",
            "est_role_seconds": 540.0,
            "traits": [
                "twin_named_modals",
                "modal_file_or_rule_dialog",
                "candidate_window_launch_on_shared_display",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "qt_logicgrid_dev",
            "est_role_seconds": 560.0,
            "traits": [
                "twin_named_modals",
                "modal_file_or_rule_dialog",
                "candidate_window_launch_on_shared_display",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

# Reference Oracle Constants (compiled strictly inside studio_ui-only reference binaries)
VAULT_ENTRIES: list[tuple[str, str, int]] = [
    ("fw_bootloader_a.bin", "Firmware", 49152),
    ("fw_fpga_bitstream.rpd", "Firmware", 131072),
    ("fw_pmu_microcode.bin", "Firmware", 24576),
    ("tel_imu_200hz.parquet", "Telemetry", 86400),
    ("tel_gnss_rtk.cbor", "Telemetry", 43200),
    ("tel_canbus_frame.log", "Telemetry", 61440),
    ("tel_thermal_ring.csv", "Telemetry", 28800),
    ("sch_order_v3.avro", "Schemas", 12288),
    ("sch_ledger_event.proto", "Schemas", 16384),
    ("sch_audit_envelope.json", "Schemas", 9600),
    ("fw_radio_dsp.elf", "Firmware", 98304),
    ("tel_lidar_scan04.laz", "Telemetry", 163840),
]

VAULT_PREFS_ORACLE = {
    "index_block_kib": 64,
    "archive_magic_prefix": "VLT26-IDX",
    "glob_case_policy": "ASCII_FOLD_INSENSITIVE",
    "preset_bundle_code": "ARC-PRESET-904",
    "poly_checksum_mod": 99991,
    "all_entries_count": len(VAULT_ENTRIES),
    "total_bytes": sum(x[2] for x in VAULT_ENTRIES),
    "firmware_bytes": sum(x[2] for x in VAULT_ENTRIES if x[1] == "Firmware"),
    "poly_checksum_all": sum((i + 1) * x[2] for i, x in enumerate(VAULT_ENTRIES)) % 99991,
}

LOGICGRID_ORACLE = {
    "board_dimension": 6,
    "default_variant": "6x6_CAGE_SUM",
    "cage_target_total": 126,
    "conflict_penalty_pts": 15,
    "preferences_theme_token": "LGRID-PREF-7741",
    "cage_A1_B1_sum": 9,
    "cage_C2_D2_E2_sum": 12,
    "first_hint_cell": "R1C3=4",
}

VAULTSEARCH_GTK_SOURCE = f"""import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
GLib.set_prgname('vaultsearch-studio')

ENTRIES = {json.dumps(VAULT_ENTRIES)}
ORACLE = {json.dumps(VAULT_PREFS_ORACLE)}

class VaultSearchWin(Gtk.Window):
    def __init__(self):
        super().__init__(title="VaultSearch Studio")
        self.set_default_size(820, 620)
        self.move(60, 60)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(6); vbox.set_margin_bottom(6); vbox.set_margin_start(8); vbox.set_margin_end(8)
        self.add(vbox)

        accel = Gtk.AccelGroup()
        self.add_accel_group(accel)
        mbar = Gtk.MenuBar()
        file_m = Gtk.MenuItem(label="File")
        f_sub = Gtk.Menu()
        mi_open = Gtk.MenuItem(label="Choose Archive Preset... (Ctrl+O)")
        mi_open.connect("activate", self.on_choose_preset)
        mi_open.add_accelerator("activate", accel, ord('o'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        f_sub.append(mi_open)
        file_m.set_submenu(f_sub)

        edit_m = Gtk.MenuItem(label="Edit")
        e_sub = Gtk.Menu()
        mi_pref = Gtk.MenuItem(label="Preferences (Ctrl+P)")
        mi_pref.connect("activate", self.on_prefs)
        mi_pref.add_accelerator("activate", accel, ord('p'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        e_sub.append(mi_pref)
        edit_m.set_submenu(e_sub)

        tools_m = Gtk.MenuItem(label="Tools")
        t_sub = Gtk.Menu()
        mi_chk = Gtk.MenuItem(label="Checksum Verifier (Ctrl+M)")
        mi_chk.connect("activate", self.on_checksum)
        mi_chk.add_accelerator("activate", accel, ord('m'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        t_sub.append(mi_chk)
        tools_m.set_submenu(t_sub)

        mbar.append(file_m); mbar.append(edit_m); mbar.append(tools_m)
        vbox.pack_start(mbar, False, False, 0)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Filter filename substring...")
        self.search_entry.connect("changed", lambda *_: self.refresh_table())
        bar.pack_start(self.search_entry, True, True, 0)

        self.cat_combo = Gtk.ComboBoxText()
        for c in ("All", "Firmware", "Telemetry", "Schemas"):
            self.cat_combo.append_text(c)
        self.cat_combo.set_active(0)
        self.cat_combo.connect("changed", lambda *_: self.refresh_table())
        bar.pack_start(self.cat_combo, False, False, 0)

        btn_pref = Gtk.Button(label="Preferences (Ctrl+P)")
        btn_pref.connect("clicked", self.on_prefs)
        bar.pack_start(btn_pref, False, False, 0)

        btn_chk = Gtk.Button(label="Checksum (Ctrl+M)")
        btn_chk.connect("clicked", self.on_checksum)
        bar.pack_start(btn_chk, False, False, 0)
        vbox.pack_start(bar, False, False, 0)

        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_monospace(True)
        sc = Gtk.ScrolledWindow()
        sc.add(self.textview)
        vbox.pack_start(sc, True, True, 0)

        self.status_lbl = Gtk.Label(xalign=0.0)
        vbox.pack_start(self.status_lbl, False, False, 0)
        self.refresh_table()

    def refresh_table(self):
        q = self.search_entry.get_text().strip().lower()
        cat = self.cat_combo.get_active_text() or "All"
        lines = []
        tot = 0
        cnt = 0
        for fn, c, b in ENTRIES:
            if cat != "All" and c != cat:
                continue
            if q and q not in fn.lower():
                continue
            lines.append(f"{{fn:<26}} | {{c:<10}} | {{b:>8}} bytes")
            tot += b
            cnt += 1
        self.textview.get_buffer().set_text("\\n".join(lines))
        self.status_lbl.set_text(f"Showing {{cnt}} / {{len(ENTRIES)}} members | Filtered Bytes: {{tot}}")

    def on_prefs(self, *_a):
        d = Gtk.Dialog(title="Preferences", transient_for=self, flags=0)
        d.set_modal(True)
        d.set_default_size(460, 250)
        box = d.get_content_area()
        box.set_spacing(8)
        box.add(Gtk.Label(label=f"Index Block Size (KiB): {{ORACLE['index_block_kib']}}"))
        box.add(Gtk.Label(label=f"Archive Magic Prefix: {{ORACLE['archive_magic_prefix']}}"))
        box.add(Gtk.Label(label=f"Glob Case Policy: {{ORACLE['glob_case_policy']}}"))
        d.add_button("Close", Gtk.ResponseType.CLOSE)
        d.show_all()
        d.run()
        d.destroy()

    def on_choose_preset(self, *_a):
        d = Gtk.Dialog(title="Choose Archive Preset", transient_for=self, flags=0)
        d.set_modal(True)
        d.set_default_size(440, 210)
        box = d.get_content_area()
        box.set_spacing(8)
        box.add(Gtk.Label(label=f"Active Archive Bundle Code: {{ORACLE['preset_bundle_code']}}"))
        box.add(Gtk.Label(label="12 members loaded across Firmware, Telemetry, and Schemas"))
        d.add_button("OK", Gtk.ResponseType.OK)
        d.show_all()
        d.run()
        d.destroy()

    def on_checksum(self, *_a):
        d = Gtk.Dialog(title="Checksum Verifier", transient_for=self, flags=0)
        d.set_modal(True)
        d.set_default_size(480, 220)
        box = d.get_content_area()
        box.set_spacing(8)
        box.add(Gtk.Label(label="Formula: sum((idx_1based) * bytes) mod 99991 over full 12-entry manifest order"))
        box.add(Gtk.Label(label=f"Verified Full-Manifest Checksum: {{ORACLE['poly_checksum_all']}}"))
        d.add_button("Close", Gtk.ResponseType.CLOSE)
        d.show_all()
        d.run()
        d.destroy()

w = VaultSearchWin()
w.connect("destroy", Gtk.main_quit)
w.show_all()
Gtk.main()
"""

LOGICGRID_QT_SOURCE = f"""import json, sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QStackedWidget, QDialog, QShortcut, QLineEdit
)
from PyQt5.QtGui import QKeySequence

ORACLE = {json.dumps(LOGICGRID_ORACLE)}
GIVEN = {{(0,0):"2", (0,3):"5", (1,1):"6", (2,2):"3", (3,4):"1", (4,5):"4", (5,0):"6"}}

class LogicGridWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogicGrid Studio")
        self.setGeometry(920, 60, 820, 640)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Page 0: Welcome Screen (2-stage UI like KSudoku)
        w0 = QWidget()
        l0 = QVBoxLayout(w0)
        l0.addWidget(QLabel("LogicGrid Studio — Select Constraint Puzzle Variant"))
        self.variant_cb = QComboBox()
        self.variant_cb.addItems(["6x6_CAGE_SUM", "4x4_THERMO_LITE"])
        l0.addWidget(self.variant_cb)
        btn_start = QPushButton("Start Puzzle Board")
        btn_start.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        l0.addWidget(btn_start)
        btn_pref0 = QPushButton("Preferences (Ctrl+P)")
        btn_pref0.clicked.connect(self.show_prefs)
        l0.addWidget(btn_pref0)
        self.stack.addWidget(w0)

        # Page 1: Active 6x6 Board
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        tbar = QHBoxLayout()
        b_back = QPushButton("Back to Welcome")
        b_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        b_hint = QPushButton("Hint Step (Ctrl+H)")
        b_hint.clicked.connect(self.apply_hint)
        b_cage = QPushButton("Cage Inspector (Ctrl+K)")
        b_cage.clicked.connect(self.show_cages)
        b_pref = QPushButton("Preferences (Ctrl+P)")
        b_pref.clicked.connect(self.show_prefs)
        for b in (b_back, b_hint, b_cage, b_pref):
            tbar.addWidget(b)
        l1.addLayout(tbar)

        grid = QGridLayout()
        self.cells = {{}}
        for r in range(6):
            for c in range(6):
                ed = QLineEdit(GIVEN.get((r, c), ""))
                ed.setAccessibleName(f"cell_r{{r+1}}_c{{c+1}}")
                if (r, c) in GIVEN:
                    ed.setReadOnly(True)
                grid.addWidget(ed, r, c)
                self.cells[(r, c)] = ed
        l1.addLayout(grid)
        self.status_lbl = QLabel("Variant: 6x6_CAGE_SUM | Given: 7/36 | Hint: ready")
        l1.addWidget(self.status_lbl)
        self.stack.addWidget(w1)

        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.show_prefs)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.show_cages)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self.apply_hint)

    def apply_hint(self):
        self.stack.setCurrentIndex(1)
        self.cells[(0, 2)].setText("4")
        self.status_lbl.setText(f"Hint Applied: {{ORACLE['first_hint_cell']}} | TargetSum={{ORACLE['cage_target_total']}}")

    def show_prefs(self):
        # Same window title "Preferences" as VaultSearch Studio -> Twin-Modal Contention!
        d = QDialog(self)
        d.setWindowTitle("Preferences")
        d.setModal(True)
        d.resize(440, 230)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"Board Dimension: {{ORACLE['board_dimension']}}x{{ORACLE['board_dimension']}}"))
        v.addWidget(QLabel(f"Conflict Penalty Points: {{ORACLE['conflict_penalty_pts']}}"))
        v.addWidget(QLabel(f"Preferences Theme Token: {{ORACLE['preferences_theme_token']}}"))
        bc = QPushButton("Close")
        bc.clicked.connect(d.accept)
        v.addWidget(bc)
        d.exec_()

    def show_cages(self):
        d = QDialog(self)
        d.setWindowTitle("Cage Sum Inspector")
        d.setModal(True)
        d.resize(450, 240)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"Total 6x6 Board Sum: {{ORACLE['cage_target_total']}}"))
        v.addWidget(QLabel(f"Cage [R1C1+R1C2] Target Sum: {{ORACLE['cage_A1_B1_sum']}}"))
        v.addWidget(QLabel(f"Cage [R2C3+R2C4+R2C5] Target Sum: {{ORACLE['cage_C2_D2_E2_sum']}}"))
        v.addWidget(QLabel(f"Canonical First Hint Cell: {{ORACLE['first_hint_cell']}}"))
        bc = QPushButton("Close")
        bc.clicked.connect(d.accept)
        v.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
app.setApplicationName("logicgrid-studio")
w = LogicGridWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Desktop Application Recreation Work Order — {b}gtk_vaultsearch_dev{b}",
        "",
        "## Objective",
        f"Explore the live **VaultSearch Studio** desktop application running on the workstation (no reference source code is present in {b}/workspace{b}) and build a faithful standalone desktop GUI recreation plus specification manifest in {b}/workspace{b}.",
        "",
        "## Required Deliverables",
        f"1. **Standalone Runnable GUI Application ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Create an executable launcher {b}/workspace/recreation/run_app.sh{b} (using GTK3 or PyQt5) that opens a main window titled {b}VaultSearch Studio{b} (`>= 700 x 500` px) on the active `DISPLAY`.",
        "   - Reproduce the interactive controls and dialogs observed in the reference app:",
        "     - Substring filter input and category selector (`All`, `Firmware`, `Telemetry`, `Schemas`) over the exact 12 archive members and byte sizes.",
        "     - Live status bar showing `Showing <k> / 12 members | Filtered Bytes: <sum>`.",
        f"     - Modal **Preferences** dialog (`Ctrl+P`), **Choose Archive Preset** dialog (`Ctrl+O`), and **Checksum Verifier** dialog (`Ctrl+M`) displaying the exact configuration values and checksum from the reference app.",
        f"2. **Reverse-Engineered Specification Manifest ({b}/workspace/SPEC_VAULTSEARCH.json{b})**:",
        "   - Record the exact values inspected from the reference app's table and three dialogs:",
        f"     - {b}\"index_block_kib\"{b} (int), {b}\"archive_magic_prefix\"{b} (string), {b}\"glob_case_policy\"{b} (string), {b}\"preset_bundle_code\"{b} (string)",
        f"     - {b}\"all_entries_count\"{b} (int), {b}\"total_bytes\"{b} (int), {b}\"firmware_bytes\"{b} (int), {b}\"poly_checksum_all\"{b} (int)",
        "",
        "## Self-Verification",
        f"Launch your {b}/workspace/recreation/run_app.sh{b} window to verify its layout, accessible controls, and `Ctrl+P` / `Ctrl+M` dialogs before finishing (clean up stray test processes when done).",
        "",
    ])

    role_b = "\n".join([
        f"# Desktop Application Recreation Work Order — {b}qt_logicgrid_dev{b}",
        "",
        "## Objective",
        f"Explore the live **LogicGrid Studio** desktop application running on the workstation (no reference source code is present in {b}/workspace{b}) across both its welcome screen and active puzzle board, and build a faithful standalone desktop GUI recreation plus specification manifest in {b}/workspace{b}.",
        "",
        "## Required Deliverables",
        f"1. **Standalone Runnable GUI Application ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Create an executable launcher {b}/workspace/recreation/run_app.sh{b} (using PyQt5 or GTK3) that opens a main window titled {b}LogicGrid Studio{b} (`>= 700 x 500` px) on the active `DISPLAY`.",
        "   - Reproduce both the Welcome variant selector (`6x6_CAGE_SUM`, `4x4_THERMO_LITE`, `Start Puzzle Board`) and the 6x6 puzzle grid (with the 7 given cells), toolbar actions, `Hint Step` (`Ctrl+H`), modal **Preferences** dialog (`Ctrl+P`), and modal **Cage Sum Inspector** dialog (`Ctrl+K`).",
        f"2. **Reverse-Engineered Specification Manifest ({b}/workspace/SPEC_LOGICGRID.json{b})**:",
        "   - Record the exact rules and tokens inspected from the reference app's welcome screen, board, `Preferences`, `Cage Sum Inspector`, and `Hint Step`:",
        f"     - {b}\"board_dimension\"{b} (int), {b}\"default_variant\"{b} (string), {b}\"cage_target_total\"{b} (int), {b}\"conflict_penalty_pts\"{b} (int)",
        f"     - {b}\"preferences_theme_token\"{b} (string), {b}\"cage_A1_B1_sum\"{b} (int), {b}\"cage_C2_D2_E2_sum\"{b} (int), {b}\"first_hint_cell\"{b} (string)",
        "",
        "## Self-Verification",
        f"Launch your {b}/workspace/recreation/run_app.sh{b} window to verify its welcome-to-board navigation, accessible widgets, and `Ctrl+P` / `Ctrl+K` / `Ctrl+H` shortcuts before finishing.",
        "",
    ])
    return {"gtk_vaultsearch_dev": role_a, "qt_logicgrid_dev": role_b}


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
    stage_private_studio_script(state_dir, "vaultsearch_ref.py", VAULTSEARCH_GTK_SOURCE)
    stage_private_studio_script(state_dir, "logicgrid_ref.py", LOGICGRID_QT_SOURCE)
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
    boot_file.write_text('{"mode":"rbs01_twin_prefs"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_isolated_studio_scripts(state_dir, ["vaultsearch_ref.py", "logicgrid_ref.py"], wait_s=2.4)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["gtk_vaultsearch_dev"]
    ws_b = workspace_map["qt_logicgrid_dev"]

    spec_a = read_json_safe(ws_a / "SPEC_VAULTSEARCH.json")
    gui_a = evaluate_recreated_gui_app(
        ws_a / "recreation/run_app.sh",
        disp_num=115,
        expected_title_sub="VaultSearch",
        key_sequences=[("ctrl_p", "ctrl+p"), ("Escape", "Escape"), ("ctrl_m", "ctrl+m")],
    )
    ax_a_init = gui_a["initial_ax_text"]
    ax_a_all = ax_a_init + "\n" + "\n".join(gui_a["after_keys_ax"].values())

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_script_exists", gui_a["script_exists"], 0.06, "Missing /workspace/recreation/run_app.sh"),
        ("a_win_mapped", gui_a["window_mapped"] and "vaultsearch" in gui_a["window_title"].lower(), 0.08, f"VaultSearch window not mapped (got {gui_a['window_title']!r})"),
        ("a_visual_layout", gui_a["visual_nonblank"] and gui_a["win_w"] >= 650 and gui_a["win_h"] >= 450, 0.08, f"Window visual check failed ({gui_a['win_w']}x{gui_a['win_h']})"),
        ("a_ax_controls", any(k in ax_a_init.lower() for k in ("firmware", "search", "filter", "preferences")), 0.08, "AT-SPI tree lacks filter/category/preferences controls"),
        ("a_ax_members", sum(1 for fn, _, _ in VAULT_ENTRIES if fn in ax_a_init) >= 6, 0.08, "AT-SPI tree missing >=6 archive member rows"),
        ("a_ax_status_summary", ("12" in ax_a_init and str(VAULT_PREFS_ORACLE["total_bytes"]) in ax_a_init.replace(",", "")), 0.07, "Status bar missing 12-member / total-bytes summary"),
        ("a_ax_prefs_modal", ("VLT26-IDX" in ax_a_all or "Preferences" in gui_a["after_keys_ax"].get("ctrl_p", "")), 0.08, "Ctrl+P Preferences dialog failed AT-SPI check"),
        ("a_ax_checksum_modal", str(VAULT_PREFS_ORACLE["poly_checksum_all"]) in ax_a_all, 0.07, "Ctrl+M Checksum dialog missing verified checksum"),
        ("a_spec_block_kib", spec_a.get("index_block_kib") == VAULT_PREFS_ORACLE["index_block_kib"], 0.06, "SPEC index_block_kib != 64"),
        ("a_spec_magic_prefix", spec_a.get("archive_magic_prefix") == VAULT_PREFS_ORACLE["archive_magic_prefix"], 0.08, "SPEC archive_magic_prefix != 'VLT26-IDX' (Preferences modal)"),
        ("a_spec_case_policy", spec_a.get("glob_case_policy") == VAULT_PREFS_ORACLE["glob_case_policy"], 0.06, "SPEC glob_case_policy mismatch"),
        ("a_spec_preset_code", spec_a.get("preset_bundle_code") == VAULT_PREFS_ORACLE["preset_bundle_code"], 0.07, "SPEC preset_bundle_code != 'ARC-PRESET-904' (Ctrl+O modal)"),
        ("a_spec_bytes", spec_a.get("total_bytes") == VAULT_PREFS_ORACLE["total_bytes"] and spec_a.get("firmware_bytes") == VAULT_PREFS_ORACLE["firmware_bytes"], 0.06, "SPEC total_bytes or firmware_bytes mismatch"),
        ("a_spec_checksum", spec_a.get("poly_checksum_all") == VAULT_PREFS_ORACLE["poly_checksum_all"], 0.07, "SPEC poly_checksum_all mismatch (Ctrl+M modal)"),
    ]

    spec_b = read_json_safe(ws_b / "SPEC_LOGICGRID.json")
    gui_b = evaluate_recreated_gui_app(
        ws_b / "recreation/run_app.sh",
        disp_num=116,
        expected_title_sub="LogicGrid",
        key_sequences=[("ctrl_h", "ctrl+h"), ("ctrl_p", "ctrl+p"), ("Escape", "Escape"), ("ctrl_k", "ctrl+k")],
    )
    ax_b_init = gui_b["initial_ax_text"]
    ax_b_all = ax_b_init + "\n" + "\n".join(gui_b["after_keys_ax"].values())

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_script_exists", gui_b["script_exists"], 0.06, "Missing /workspace/recreation/run_app.sh"),
        ("b_win_mapped", gui_b["window_mapped"] and "logicgrid" in gui_b["window_title"].lower(), 0.08, f"LogicGrid window not mapped (got {gui_b['window_title']!r})"),
        ("b_visual_layout", gui_b["visual_nonblank"] and gui_b["win_w"] >= 650 and gui_b["win_h"] >= 450, 0.08, f"Window visual check failed ({gui_b['win_w']}x{gui_b['win_h']})"),
        ("b_ax_welcome_variant", "6x6_CAGE_SUM" in ax_b_all, 0.07, "AT-SPI missing 6x6_CAGE_SUM variant"),
        ("b_ax_hint_action", "R1C3=4" in ax_b_all or "126" in ax_b_all, 0.08, "Ctrl+H hint / board state not exposed in AT-SPI"),
        ("b_ax_prefs_modal", ("LGRID-PREF-7741" in ax_b_all or "Preferences" in gui_b["after_keys_ax"].get("ctrl_p", "")), 0.08, "Ctrl+P Preferences modal failed AT-SPI check"),
        ("b_ax_cage_modal", ("Cage" in ax_b_all and ("126" in ax_b_all or "12" in ax_b_all)), 0.07, "Ctrl+K Cage Inspector modal failed AT-SPI check"),
        ("b_ax_interactive_buttons", any(w in ax_b_all.lower() for w in ("start", "hint", "preferences", "cage")), 0.08, "Missing interactive toolbar/welcome buttons"),
        ("b_spec_dim_variant", spec_b.get("board_dimension") == 6 and spec_b.get("default_variant") == "6x6_CAGE_SUM", 0.06, "SPEC board_dimension or default_variant mismatch"),
        ("b_spec_cage_total", spec_b.get("cage_target_total") == LOGICGRID_ORACLE["cage_target_total"], 0.07, "SPEC cage_target_total != 126"),
        ("b_spec_penalty", spec_b.get("conflict_penalty_pts") == LOGICGRID_ORACLE["conflict_penalty_pts"], 0.06, "SPEC conflict_penalty_pts != 15 (Preferences modal)"),
        ("b_spec_pref_token", spec_b.get("preferences_theme_token") == LOGICGRID_ORACLE["preferences_theme_token"], 0.08, "SPEC preferences_theme_token != 'LGRID-PREF-7741' (twin Preferences modal)"),
        ("b_spec_cage_sums", spec_b.get("cage_A1_B1_sum") == 9 and spec_b.get("cage_C2_D2_E2_sum") == 12, 0.06, "SPEC cage sums mismatch (Ctrl+K modal)"),
        ("b_spec_first_hint", spec_b.get("first_hint_cell") == LOGICGRID_ORACLE["first_hint_cell"], 0.07, "SPEC first_hint_cell != 'R1C3=4'"),
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
    assert role in ("gtk_vaultsearch_dev", "qt_logicgrid_dev")
    ws = workspace_map[role]
    rec = ws / "recreation"
    rec.mkdir(parents=True, exist_ok=True)

    def _work() -> None:
        if role == "gtk_vaultsearch_dev":
            (rec / "app.py").write_text(VAULTSEARCH_GTK_SOURCE, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/app.py\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)
            write_json(ws / "SPEC_VAULTSEARCH.json", VAULT_PREFS_ORACLE)
        else:
            (rec / "app.py").write_text(LOGICGRID_QT_SOURCE, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/app.py\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)
            write_json(ws / "SPEC_LOGICGRID.json", LOGICGRID_ORACLE)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_2 Twin-Preferences Hijack): Role B reads Role A's 'Preferences' modal during collision."""
    solve_role("gtk_vaultsearch_dev", workspace_map, port, careful_conc=False)
    solve_role("qt_logicgrid_dev", workspace_map, port, careful_conc=False)
    ws_b = workspace_map["qt_logicgrid_dev"]
    corrupted = dict(LOGICGRID_ORACLE)
    corrupted["preferences_theme_token"] = "HIJACKED_BY_PEER_PREFERENCES_MODAL"
    corrupted["conflict_penalty_pts"] = 0
    write_json(ws_b / "SPEC_LOGICGRID.json", corrupted)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)

"""RBS2-04: FlowForge BPMN Deadlock Canvas vs. Always-on-Top QuickStamp Clipboard Palette.

Grounded in RecreationBench (RB-B12 Camunda BPMN + Smile Clipboard & RB-B13 Always-on-Top Pomatez):
  - LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB: QuickStamp Palette launches with
    `Qt.WindowStaysOnTopHint` (`_NET_WM_STATE_ABOVE`) right at (420, 170), directly occluding
    FlowForge BPMN Canvas's central gateway repair switches!
  - LAW_1 + Shared X11 CLIPBOARD: Clicking any snippet tile in QuickStamp overwrites the X11
    clipboard while FlowForge copies its signed BPMN remediation seal to the clipboard (`Ctrl+B`).
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from tasks.rb_osw2_synth_v2.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    build_grade_payload,
    evaluate_recreated_gui_app,
    get_x11_clipboard,
    read_json_safe,
    run_cli_probe_json,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS2-04"
PORTAL_PORT = 19404

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "FlowForge BPMN Deadlock Canvas vs. Always-on-Top QuickStamp Clipboard Palette",
    "domain": "BPMN Workflow Deadlock Verification & Always-on-Top Snippet/Pomodoro Utility Recreation",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_1_KEYSTROKE_MISROUTING",
        "LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH",
    ),
    "roles": ("bpmn_engine_architect", "topmost_palette_dev"),
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
            "slug": "bpmn_engine_architect",
            "est_role_seconds": 530.0,
            "traits": [
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "custom_2d_canvas_drag",
                "overlapping_docks_or_root_screencap",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "topmost_palette_dev",
            "est_role_seconds": 520.0,
            "traits": [
                "overlapping_docks_or_root_screencap",
                "autohide_popover_or_ephemeral_menu",
                "candidate_window_launch_on_shared_display",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

BPMN_SALT = "flowforge-bpmn-rbs204"
BPMN_SEAL_OK = "BPMN-CERT-" + hashlib.sha256(f"{BPMN_SALT}:True:True".encode()).hexdigest()[:10].upper()
BPMN_ORACLE = {
    "swimlanes": ["INGEST_API", "RISK_DECISION", "CLEARING_SETTLE"],
    "deadlock_gateway_id": "GW_RETRY_SPLIT",
    "missing_boundary_task_id": "TASK_LEDGER_DEBIT",
    "critical_path_ms": 485,
    "timeout_sla_ms": 150,
    "bpmn_remediation_seal": BPMN_SEAL_OK,
}

PALETTE_ORACLE = {
    "categories": ["EMOJI_STATUS", "SQL_SNIPPETS", "K8S_PROBES", "GIT_TRAILERS"],
    "focus_sprint_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "clipboard_prefix_tag": "QSTAMP_V2",
    "palette_settings_seal": "QSTP-TOP-5520",
}

FLOWFORGE_QT_SOURCE = f"""import hashlib, json, subprocess, sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDialog, QShortcut
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt

SALT = {json.dumps(BPMN_SALT)}
OR = {json.dumps(BPMN_ORACLE)}

class BpmnCanvas(QWidget):
    def __init__(self, on_chg):
        super().__init__()
        self.setMinimumSize(860, 440)
        self.fix_gw = False
        self.fix_comp = False
        self.on_chg = on_chg

    def mousePressEvent(self, ev):
        x, y = ev.pos().x(), ev.pos().y()
        # Two interactive canvas nodes right in the middle (occluded by QuickStamp at 420..880, 170..590!)
        if 340 <= x <= 510 and 165 <= y <= 245:
            self.fix_gw = not self.fix_gw
            self.on_chg(); self.update()
        elif 540 <= x <= 730 and 295 <= y <= 375:
            self.fix_comp = not self.fix_comp
            self.on_chg(); self.update()

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(15, 23, 42))
        lanes = [("INGEST_API (95ms)", 30), ("RISK_DECISION (170ms)", 155), ("CLEARING_SETTLE (220ms)", 280)]
        qp.setFont(QFont("Monospace", 10, QFont.Bold))
        for title, ly in lanes:
            qp.setPen(QPen(QColor(71, 85, 105), 2))
            qp.drawRect(20, ly, 820, 115)
            qp.setPen(QColor(148, 163, 184))
            qp.drawText(30, ly + 22, f"SWIMLANE: {{title}}")

        # Gateway node GW_RETRY_SPLIT at (345, 175, 160, 65)
        qp.fillRect(345, 175, 160, 65, QColor(16, 185, 129) if self.fix_gw else QColor(185, 28, 28))
        qp.setPen(QColor(255, 255, 255))
        qp.drawText(352, 202, "GW_RETRY_SPLIT")
        qp.drawText(352, 226, "TIMEOUT_150ms: ON" if self.fix_gw else "LIVELOCK! Click Fix")

        # Compensation node TASK_LEDGER_DEBIT at (545, 300, 180, 65)
        qp.fillRect(545, 300, 180, 65, QColor(16, 185, 129) if self.fix_comp else QColor(185, 28, 28))
        qp.drawText(552, 327, "TASK_LEDGER_DEBIT")
        qp.drawText(552, 351, "COMPENSATE: ON" if self.fix_comp else "NO_BOUNDARY! Click")

        qp.setPen(QColor(56, 189, 248))
        qp.drawText(30, 425, "Critical Path: 95 + 170 + 220 = 485 ms | Click both red defect nodes on canvas, then Ctrl+B")

class FlowForgeWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowForge BPMN Studio")
        self.resize(920, 590)
        cw = QWidget(); lay = QVBoxLayout(cw)
        tbar = QHBoxLayout()
        b_sim = QPushButton("Token Reachability Simulator [F5]")
        b_cp = QPushButton("Copy Remediated BPMN Seal to Clipboard [Ctrl+B]")
        b_sim.clicked.connect(self.show_sim)
        b_cp.clicked.connect(self.copy_seal)
        tbar.addWidget(b_sim); tbar.addWidget(b_cp)
        lay.addLayout(tbar)
        self.cv = BpmnCanvas(self.upd)
        lay.addWidget(self.cv)
        self.st_lbl = QLabel("Deadlocks active — click red BPMN nodes on canvas to remediate.")
        lay.addWidget(self.st_lbl)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("F5"), self, activated=self.show_sim)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.copy_seal)

    def upd(self):
        self.st_lbl.setText(f"GW_RETRY_SPLIT_fixed={{self.cv.fix_gw}} | TASK_LEDGER_DEBIT_fixed={{self.cv.fix_comp}}")

    def show_sim(self):
        d = QDialog(self); d.setWindowTitle("BPMN Reachability Simulator"); d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel("Swimlanes: INGEST_API -> RISK_DECISION -> CLEARING_SETTLE"))
        v.addWidget(QLabel("Critical Path Latency: 485 ms | Gateway Timeout SLA: 150 ms"))
        v.addWidget(QLabel(f"Clean Reachability: {{self.cv.fix_gw and self.cv.fix_comp}}"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); v.addWidget(bc)
        d.exec_()

    def copy_seal(self):
        ok = (self.cv.fix_gw and self.cv.fix_comp)
        sig = hashlib.sha256(f"{{SALT}}:{{self.cv.fix_gw}}:{{self.cv.fix_comp}}".encode()).hexdigest()[:10].upper()
        seal = f"BPMN-CERT-{{sig}}" if ok else "DEADLOCK_UNRESOLVED"
        subprocess.run(["xclip", "-selection", "clipboard"], input=seal.encode(), check=False)
        self.st_lbl.setText(f"Copied seal to X11 clipboard (resolved={{ok}})")

app = QApplication(sys.argv)
app.setApplicationName("flowforge-bpmn")
w = FlowForgeWin()
w.show()
sys.exit(app.exec_())
"""

QUICKSTAMP_QT_SOURCE = f"""import json, subprocess, sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QDialog, QShortcut
)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt

OR = {json.dumps(PALETTE_ORACLE)}
TILES = {{
    "EMOJI_STATUS": ["[OK_GREEN]", "[WARN_AMBER]", "[SEV1_PAGER]"],
    "SQL_SNIPPETS": ["EXPLAIN ANALYZE", "LOCK TABLE NOWAIT", "VACUUM FREEZE"],
    "K8S_PROBES": ["kubectl get pods -A", "kubectl top node", "kubectl rollout undo"],
    "GIT_TRAILERS": ["Signed-off-by:", "Co-authored-by:", "Reviewed-by:"],
}}

class QuickStampWin(QMainWindow):
    def __init__(self):
        # Launches Always-on-Top directly occluding FlowForge BPMN Canvas at (380, 170)!
        super().__init__(None, Qt.WindowStaysOnTopHint)
        self.setWindowTitle("QuickStamp Topmost Palette")
        self.resize(470, 380)
        cw = QWidget(); lay = QVBoxLayout(cw)
        hdr = QHBoxLayout()
        b_set = QPushButton("Sprint & Clipboard Settings [F10]")
        b_set.clicked.connect(self.open_settings)
        hdr.addWidget(b_set)
        lay.addLayout(hdr)

        tabs = QTabWidget()
        for cat, items in TILES.items():
            page = QWidget(); pv = QVBoxLayout(page)
            for it in items:
                btn = QPushButton(f"Copy {{it}}")
                btn.clicked.connect(lambda _=False, txt=it: self.copy_tile(txt))
                pv.addWidget(btn)
            tabs.addTab(page, cat)
        lay.addWidget(tabs)
        self.st_lbl = QLabel("Always-on-Top Palette | Click any tile to write QSTAMP_V2:<tile> to clipboard")
        lay.addWidget(self.st_lbl)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("F10"), self, activated=self.open_settings)

    def copy_tile(self, txt):
        payload = f"{{OR['clipboard_prefix_tag']}}:{{txt}}"
        subprocess.run(["xclip", "-selection", "clipboard"], input=payload.encode(), check=False)
        self.st_lbl.setText(f"Copied {{payload}}")

    def open_settings(self):
        d = QDialog(self); d.setWindowTitle("QuickStamp Settings"); d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"Pomodoro Cadence: Focus={{OR['focus_sprint_minutes']}}m | ShortBreak={{OR['short_break_minutes']}}m | LongBreak={{OR['long_break_minutes']}}m"))
        v.addWidget(QLabel(f"Clipboard Prefix: {{OR['clipboard_prefix_tag']}} | Seal: {{OR['palette_settings_seal']}}"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); v.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
app.setApplicationName("quickstamp-palette")
w = QuickStampWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# BPMN Workflow Deadlock Remediation & Verifier Work Order — {b}bpmn_engine_architect{b}",
        "",
        "## Scope & Deliverables",
        f"Remediate both topological defects on the live **FlowForge BPMN Studio** canvas, capture the signed clipboard seal, and build a standalone BPMN verifier in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **BPMN Remediation Manifest ({b}/workspace/BPMN_REMEDIATION.json{b})**:",
        "   - Click both red defect nodes (`GW_RETRY_SPLIT` and `TASK_LEDGER_DEBIT`) on the **FlowForge BPMN Studio** canvas so both turn green, verify `Clean Reachability: True` in `F5`, copy the signed BPMN seal via `Ctrl+B`, and record exact keys:",
        f"     - {b}\"swimlanes\"{b} (3-item list in top-to-bottom order), {b}\"deadlock_gateway_id\"{b} (string), {b}\"missing_boundary_task_id\"{b} (string)",
        f"     - {b}\"critical_path_ms\"{b} (int), {b}\"timeout_sla_ms\"{b} (int), {b}\"bpmn_remediation_seal\"{b} (`BPMN-CERT-...`)",
        f"2. **Standalone FlowForge Verifier GUI + CLI ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Opens a window titled {b}FlowForge Verifier{b} (`>= 660 x 420` px) displaying the 3 swimlanes, `critical_path_ms`, and `bpmn_remediation_seal`, AND supports `--verify-bpmn-json` printing `{{\"critical_path_ms\": ..., \"bpmn_remediation_seal\": ...}}`.",
        "",
    ])

    role_b = "\n".join([
        f"# Topmost Snippet & Pomodoro Palette Recreation Work Order — {b}topmost_palette_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Explore all 4 category tabs and `F10` settings of **QuickStamp Topmost Palette** on the workstation and build its standalone recreation in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Palette Specification Manifest ({b}/workspace/PALETTE_SPEC.json{b})** with exact keys:",
        f"   - {b}\"categories\"{b} (4-item list in tab order), {b}\"focus_sprint_minutes\"{b} (int), {b}\"short_break_minutes\"{b} (int), {b}\"long_break_minutes\"{b} (int), {b}\"clipboard_prefix_tag\"{b} (string), {b}\"palette_settings_seal\"{b} (string)",
        f"2. **Standalone QuickStamp GUI + CLI ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Opens a window titled {b}QuickStamp Palette{b} (`>= 440 x 340` px) exposing the 4 snippet tabs, clipboard copy buttons, and `F10` settings dialog, AND supports `--self-test-json` printing `{{\"categories\": [...], \"palette_settings_seal\": ...}}`.",
        "",
    ])
    return {"bpmn_engine_architect": role_a, "topmost_palette_dev": role_b}


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
    stage_private_studio_script(state_dir, "flowforge_ref.py", FLOWFORGE_QT_SOURCE)
    stage_private_studio_script(state_dir, "quickstamp_ref.py", QUICKSTAMP_QT_SOURCE)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None: return
        def do_GET(self) -> None:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text('{"mode":"rbs2_04"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_isolated_studio_scripts(state_dir, ["flowforge_ref.py", "quickstamp_ref.py"], wait_s=2.4)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["bpmn_engine_architect"]
    ws_b = workspace_map["topmost_palette_dev"]

    bp = read_json_safe(ws_a / "BPMN_REMEDIATION.json")
    sh_a = ws_a / "recreation/run_app.sh"
    cli_a = run_cli_probe_json(sh_a, ["--verify-bpmn-json"])
    gui_a = evaluate_recreated_gui_app(sh_a, disp_num=115, expected_title_sub="FlowForge")
    ax_a = gui_a["initial_ax_text"]

    # 19 subchecks for Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json_exists", bool(bp), 0.04, "Missing BPMN_REMEDIATION.json"),
        ("a_swimlanes", bp.get("swimlanes") == BPMN_ORACLE["swimlanes"], 0.07, "swimlanes mismatch"),
        ("a_gw_id", bp.get("deadlock_gateway_id") == "GW_RETRY_SPLIT", 0.06, "deadlock_gateway_id != 'GW_RETRY_SPLIT'"),
        ("a_task_id", bp.get("missing_boundary_task_id") == "TASK_LEDGER_DEBIT", 0.06, "missing_boundary_task_id != 'TASK_LEDGER_DEBIT'"),
        ("a_crit_ms", bp.get("critical_path_ms") == 485, 0.06, "critical_path_ms != 485"),
        ("a_sla_ms", bp.get("timeout_sla_ms") == 150, 0.05, "timeout_sla_ms != 150"),
        ("a_bpmn_seal", bp.get("bpmn_remediation_seal") == BPMN_SEAL_OK, 0.12, f"bpmn_remediation_seal={bp.get('bpmn_remediation_seal')!r} != {BPMN_SEAL_OK!r} (occluded node or clipboard race)"),
        ("a_sh_exists", gui_a["script_exists"], 0.04, "Missing recreation/run_app.sh"),
        ("a_win_mapped", gui_a["window_mapped"] and "flowforge" in gui_a["window_title"].lower(), 0.07, "FlowForge Verifier window not mapped"),
        ("a_visual_ok", gui_a["visual_nonblank"] and gui_a["win_w"] >= 620, 0.06, "FlowForge Verifier visual check failed"),
        ("a_visual_colors", gui_a["unique_colors_sampled"] >= 4, 0.04, "FlowForge Verifier lacks styled colors"),
        ("a_ax_lanes", all(x in ax_a for x in ("INGEST_API", "RISK_DECISION", "CLEARING_SETTLE")), 0.07, "AT-SPI missing swimlane names"),
        ("a_ax_crit", "485" in ax_a, 0.05, "AT-SPI missing 485ms critical path"),
        ("a_ax_seal", BPMN_SEAL_OK in ax_a, 0.06, "AT-SPI missing certified BPMN seal"),
        ("a_cli_crit", cli_a.get("critical_path_ms") == 485, 0.05, "--verify-bpmn-json critical_path_ms != 485"),
        ("a_cli_seal", cli_a.get("bpmn_remediation_seal") == BPMN_SEAL_OK, 0.06, "--verify-bpmn-json seal mismatch"),
        ("a_lanes_len", len(bp.get("swimlanes") or []) == 3, 0.02, "swimlanes length != 3"),
        ("a_no_qstamp_leak", not str(bp.get("bpmn_remediation_seal", "")).startswith("QSTAMP"), 0.01, "Clipboard overwritten by QuickStamp"),
        ("a_win_h", gui_a["win_h"] >= 380, 0.01, "Window height < 380"),
    ]

    ps = read_json_safe(ws_b / "PALETTE_SPEC.json")
    sh_b = ws_b / "recreation/run_app.sh"
    cli_b = run_cli_probe_json(sh_b, ["--self-test-json"])
    gui_b = evaluate_recreated_gui_app(sh_b, disp_num=116, expected_title_sub="QuickStamp", key_sequences=[("f10", "F10")])
    ax_b = gui_b["initial_ax_text"] + "\n" + "\n".join(gui_b["after_keys_ax"].values())

    # 19 subchecks for Role B (19 + 19 = 38 total subchecks!)
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json_exists", bool(ps), 0.04, "Missing PALETTE_SPEC.json"),
        ("b_cats", ps.get("categories") == PALETTE_ORACLE["categories"], 0.08, "categories mismatch"),
        ("b_focus_25", ps.get("focus_sprint_minutes") == 25, 0.05, "focus_sprint_minutes != 25"),
        ("b_sbreak_5", ps.get("short_break_minutes") == 5, 0.05, "short_break_minutes != 5"),
        ("b_lbreak_15", ps.get("long_break_minutes") == 15, 0.05, "long_break_minutes != 15"),
        ("b_prefix", ps.get("clipboard_prefix_tag") == "QSTAMP_V2", 0.06, "clipboard_prefix_tag != 'QSTAMP_V2'"),
        ("b_seal", ps.get("palette_settings_seal") == "QSTP-TOP-5520", 0.10, "palette_settings_seal != 'QSTP-TOP-5520' (F10 modal)"),
        ("b_sh_exists", gui_b["script_exists"], 0.04, "Missing recreation/run_app.sh"),
        ("b_win_mapped", gui_b["window_mapped"] and "quickstamp" in gui_b["window_title"].lower(), 0.07, "QuickStamp window not mapped"),
        ("b_visual_ok", gui_b["visual_nonblank"] and gui_b["win_w"] >= 400 and gui_b["win_h"] >= 300, 0.07, "QuickStamp visual check failed"),
        ("b_visual_colors", gui_b["unique_colors_sampled"] >= 4, 0.04, "QuickStamp styling blank"),
        ("b_ax_tabs", sum(1 for c in PALETTE_ORACLE["categories"] if c in ax_b) >= 3, 0.07, "AT-SPI missing category tabs"),
        ("b_ax_copy_btns", "copy" in ax_b.lower(), 0.05, "AT-SPI missing Copy snippet buttons"),
        ("b_ax_f10", "QSTP-TOP-5520" in ax_b or "25" in ax_b, 0.06, "AT-SPI missing F10 settings info"),
        ("b_cli_cats", cli_b.get("categories") == PALETTE_ORACLE["categories"], 0.06, "--self-test-json categories mismatch"),
        ("b_cli_seal", cli_b.get("palette_settings_seal") == "QSTP-TOP-5520", 0.06, "--self-test-json seal mismatch"),
        ("b_cats_len", len(ps.get("categories") or []) == 4, 0.02, "categories length != 4"),
        ("b_k8s_cat", "K8S_PROBES" in (ps.get("categories") or []), 0.02, "Missing K8S_PROBES"),
        ("b_git_cat", "GIT_TRAILERS" in (ps.get("categories") or []), 0.01, "Missing GIT_TRAILERS"),
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
    assert role in ("bpmn_engine_architect", "topmost_palette_dev")
    ws = workspace_map[role]
    rec = ws / "recreation"
    rec.mkdir(parents=True, exist_ok=True)

    def _work() -> None:
        if role == "bpmn_engine_architect":
            # Move QuickStamp out of the way first so FlowForge nodes at (345,175) and (545,300) aren't occluded!
            gui_sh = (
                "export DISPLAY=:99; "
                "qw=$(xdotool search --onlyvisible --name 'QuickStamp' | tail -n 1 || true); "
                "[ -n \"$qw\" ] && wmctrl -i -r \"$qw\" -e 0,1320,620,450,360 || true; "
                "wid=$(xdotool search --onlyvisible --name 'FlowForge BPMN Studio' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,40,40,920,590; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.3; "
                "python3 - <<'PY'\n"
                "import io, subprocess\n"
                "from PIL import Image\n"
                "raw = subprocess.check_output(['import', '-window', 'root', 'png:-'])\n"
                "im = Image.open(io.BytesIO(raw)).convert('RGB')\n"
                "# Click the two red defect rectangles (185,28,28) in left (<560) and right (>=560) halves\n"
                "reds = [(x, y) for x in range(320, 860, 4) for y in range(180, 520, 4) if im.getpixel((x,y))[0]>165 and im.getpixel((x,y))[1]<45 and im.getpixel((x,y))[2]<45]\n"
                "r1 = [p for p in reds if p[0] < 560]\n"
                "r2 = [p for p in reds if p[0] >= 560]\n"
                "for bucket in (r1, r2):\n"
                "    if bucket:\n"
                "        cx = sum(p[0] for p in bucket)//len(bucket); cy = sum(p[1] for p in bucket)//len(bucket)\n"
                "        subprocess.run(['xdotool', 'mousemove', str(cx), str(cy), 'click', '1'], check=True)\n"
                "PY\n"
                "sleep 0.25; wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.15; "
                "xdotool key --clearmodifiers ctrl+b; sleep 0.3"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=20)
            seal = get_x11_clipboard()
            write_json(ws / "BPMN_REMEDIATION.json", {**BPMN_ORACLE, "bpmn_remediation_seal": seal})
            app_py = (
                "import json, sys\n"
                f"OR = {repr(BPMN_ORACLE)}\n"
                "if '--verify-bpmn-json' in sys.argv:\n"
                "    print(json.dumps({'critical_path_ms': OR['critical_path_ms'], 'bpmn_remediation_seal': OR['bpmn_remediation_seal']}))\n"
                "    sys.exit(0)\n"
                "from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton\n"
                "app = QApplication(sys.argv); w = QMainWindow(); w.setWindowTitle('FlowForge Verifier'); w.resize(700, 440)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#0f172a;color:#f8fafc;'); v = QVBoxLayout(cw)\n"
                "l1 = QLabel('Swimlanes: ' + ' -> '.join(OR['swimlanes'])); l1.setStyleSheet('background:#1e293b;color:#38bdf8;padding:8px;')\n"
                "l2 = QLabel('Critical Path: 485 ms | Seal: ' + OR['bpmn_remediation_seal']); l2.setStyleSheet('background:#065f46;color:#ecfdf5;padding:8px;')\n"
                "b1 = QPushButton('Run Reachability Check'); b1.setStyleSheet('background:#2563eb;color:#fff;padding:8px;')\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1); w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "verifier.py").write_text(app_py, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/verifier.py\" \"$@\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)
        else:
            write_json(ws / "PALETTE_SPEC.json", PALETTE_ORACLE)
            app_py = (
                "import json, sys\n"
                f"OR = {repr(PALETTE_ORACLE)}\n"
                "if '--self-test-json' in sys.argv:\n"
                "    print(json.dumps({'categories': OR['categories'], 'palette_settings_seal': OR['palette_settings_seal']}))\n"
                "    sys.exit(0)\n"
                "from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton\n"
                "app = QApplication(sys.argv); w = QMainWindow(); w.setWindowTitle('QuickStamp Palette'); w.resize(480, 380)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#1e1b4b;color:#fff;'); v = QVBoxLayout(cw)\n"
                "tabs = QTabWidget()\n"
                "for c in OR['categories']:\n"
                "    p = QWidget(); pv = QVBoxLayout(p); b = QPushButton('Copy ' + c); b.setStyleSheet('background:#2563eb;color:#fff;'); pv.addWidget(b); tabs.addTab(p, c)\n"
                "v.addWidget(tabs)\n"
                "l1 = QLabel('Focus: 25m | Seal: ' + OR['palette_settings_seal']); l1.setStyleSheet('background:#059669;color:#fff;padding:6px;')\n"
                "v.addWidget(l1); w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "palette.py").write_text(app_py, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/palette.py\" \"$@\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_5 Topmost Occlusion + Clipboard Overwrite): QuickStamp tile overwrites BPMN clipboard seal."""
    solve_role("bpmn_engine_architect", workspace_map, port, careful_conc=False)
    solve_role("topmost_palette_dev", workspace_map, port, careful_conc=False)
    ws_a = workspace_map["bpmn_engine_architect"]
    bad = read_json_safe(ws_a / "BPMN_REMEDIATION.json")
    bad["bpmn_remediation_seal"] = "QSTAMP_V2:[OK_GREEN]"
    write_json(ws_a / "BPMN_REMEDIATION.json", bad)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

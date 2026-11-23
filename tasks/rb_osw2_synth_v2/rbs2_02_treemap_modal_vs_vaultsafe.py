"""RBS2-02: Dual Startup Modal Wizards & Twin Preferences — TreeStat Cushion Treemap vs. VaultSafe.

Grounded in RecreationBench (RB-B10 QDirStat startup modal + RB-B11 CherryTree/PasswordSafe):
  - LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP: Both TreeStat Analyzer and VaultSafe Hierarchy launch
    initial modal dialogs onto `:99` AND share identical `"Preferences"` (`Ctrl+P`) modal titles.
  - LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI: TreeStat renders its 8 directory quota blocks purely onto
    a custom QPainter 2D treemap canvas (zero AT-SPI labels on blocks; click block to inspect).
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Any

from tasks.rb_osw2_synth_v2.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    build_grade_payload,
    evaluate_recreated_gui_app,
    read_json_safe,
    run_cli_probe_json,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS2-02"
PORTAL_PORT = 19402

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Dual Startup Modals & Twin Preferences: QPainter TreeStat Treemap vs. VaultSafe Recreation",
    "domain": "Filesystem Treemap Visualization & Encrypted Credential Hierarchy GUI Recreation",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH",
    ),
    "roles": ("treemap_analyzer_dev", "cipher_vault_dev"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1680,
    "iso_role_timeout_s": 1680,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "high_granularity_visual_recreation",
        "total_subchecks": 40,
        "cli_bypass_resistance": 0.97,
        "role_a": {
            "slug": "treemap_analyzer_dev",
            "est_role_seconds": 550.0,
            "traits": [
                "twin_named_modals",
                "modal_file_or_rule_dialog",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
            ],
        },
        "role_b": {
            "slug": "cipher_vault_dev",
            "est_role_seconds": 550.0,
            "traits": [
                "twin_named_modals",
                "modal_file_or_rule_dialog",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
            ],
        },
    },
}

# 8 Treemap blocks: (dir_id, gib, stale_days, color_rgb)
TREEMAP_BLOCKS: list[tuple[str, float, int, tuple[int, int, int]]] = [
    ("/var/cache/ckpt_shard0", 68.5, 124, (220, 38, 38)),
    ("/var/log/envoy_trace",   42.0,  96, (234, 88, 12)),
    ("/opt/models/llama_fp8",  84.0,  18, (37, 99, 235)),
    ("/srv/parquet/tick_2024", 55.5, 142, (185, 28, 28)),
    ("/home/build/ccache",     31.0,  91, (217, 119, 6)),
    ("/usr/local/cuda_sdk",    29.0,  12, (16, 185, 129)),
    ("/var/tmp/core_dumps",    38.0, 108, (225, 29, 72)),
    ("/srv/pg_wal_archive",    46.0,  45, (124, 58, 237)),
]
# Purge rule (in Preferences Ctrl+P): stale_days >= 90 -> 5 blocks: 68.5+42.0+55.5+31.0+38.0 = 235.0 GiB!
TREESTAT_ORACLE = {
    "mounted_snapshot": "NVME_POOL_04",
    "stale_cutoff_days": 90,
    "total_volume_gib": round(sum(b[1] for b in TREEMAP_BLOCKS), 1),
    "reclaimable_stale_gib": round(sum(b[1] for b in TREEMAP_BLOCKS if b[2] >= 90), 1),
    "reclaimable_dirs": sorted(b[0] for b in TREEMAP_BLOCKS if b[2] >= 90),
    "largest_active_dir": "/opt/models/llama_fp8",
    "preferences_quota_seal": "TSTAT-QUOTA-6630",
}

VAULTSAFE_ORACLE = {
    "unlock_pin_code": "7391",
    "kdf_algorithm": "ARGON2ID_64MIB",
    "kdf_iterations": 4,
    "auto_lock_seconds": 180,
    "rotation_overdue_entries": ["INFRA_JUMP_ED25519", "PROD_WILDCARD_TLS", "PG_REPLICA_SCRAM"],
    "entropy_bits_min": 128,
    "preferences_vault_seal": "VSAFE-KDF-9912",
}

TREESTAT_QT_SOURCE = f"""import json, sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDialog, QComboBox, QShortcut
)
from PyQt5.QtGui import QPainter, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt, QTimer

BLOCKS = {json.dumps([(b[0], b[1], b[2], list(b[3])) for b in TREEMAP_BLOCKS])}
OR = {json.dumps(TREESTAT_ORACLE)}

class TreemapCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(780, 430)
        self.loaded = False
        self.sel = 0

    def mousePressEvent(self, ev):
        if not self.loaded:
            return
        c = min(3, max(0, (ev.pos().x() - 20) // 185))
        r = min(1, max(0, (ev.pos().y() - 20) // 175))
        self.sel = r * 4 + c
        self.update()

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(17, 24, 39))
        if not self.loaded:
            qp.setPen(QColor(248, 250, 252))
            qp.setFont(QFont("Monospace", 13, QFont.Bold))
            qp.drawText(60, 210, "Select Snapshot NVME_POOL_04 in Startup Dialog (or click Mount Snapshot)")
            return
        for idx, (dpath, gib, sdays, rgb) in enumerate(BLOCKS):
            r, c = idx // 4, idx % 4
            x0, y0 = 20 + c * 188, 20 + r * 175
            qp.fillRect(x0, y0, 176, 160, QColor(rgb[0], rgb[1], rgb[2]))
            if idx == self.sel:
                qp.setPen(QColor(255, 255, 255))
                qp.drawRect(x0 - 2, y0 - 2, 180, 164)
            qp.setPen(QColor(255, 255, 255))
            qp.setFont(QFont("Monospace", 8, QFont.Bold))
            qp.drawText(x0 + 6, y0 + 34, dpath.split("/")[-1])
            qp.drawText(x0 + 6, y0 + 62, f"{{gib:.1f}} GiB")
            qp.drawText(x0 + 6, y0 + 90, f"stale={{sdays}}d")
        sel_b = BLOCKS[self.sel]
        qp.setFont(QFont("Monospace", 11, QFont.Bold))
        qp.drawText(20, 405, f"SELECTED BLOCK [{{self.sel+1}}/8]: path={{sel_b[0]}} | size={{sel_b[1]}} GiB | stale_days={{sel_b[2]}}")

class TreeStatWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TreeStat Disk Analyzer")
        self.setGeometry(50, 60, 840, 590)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        tbar = QHBoxLayout()
        b_mnt = QPushButton("Select Scan Snapshot [Ctrl+O]")
        b_prv = QPushButton("Prev Block")
        b_nxt = QPushButton("Next Block [Tab]")
        b_prf = QPushButton("Preferences [Ctrl+P]")
        b_mnt.clicked.connect(self.open_scan_modal)
        b_prv.clicked.connect(lambda: self.step(-1))
        b_nxt.clicked.connect(lambda: self.step(1))
        b_prf.clicked.connect(self.open_prefs)
        for b in (b_mnt, b_prv, b_nxt, b_prf):
            tbar.addWidget(b)
        lay.addLayout(tbar)
        self.cv = TreemapCanvas()
        lay.addWidget(self.cv)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_scan_modal)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)
        QTimer.singleShot(250, self.open_scan_modal)

    def step(self, d):
        self.cv.loaded = True
        self.cv.sel = (self.cv.sel + d) % len(BLOCKS)
        self.cv.update()

    def open_scan_modal(self):
        d = QDialog(self)
        d.setWindowTitle("Select Scan Snapshot")
        d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel("Choose Filesystem Volume Snapshot to Mount:"))
        cb = QComboBox(); cb.addItems(["NVME_POOL_04", "SCRATCH_EMPTY"])
        v.addWidget(cb)
        ok = QPushButton("Mount Selected Snapshot")
        def _acc():
            if cb.currentText() == "NVME_POOL_04":
                self.cv.loaded = True
                self.cv.update()
            d.accept()
        ok.clicked.connect(_acc)
        v.addWidget(ok)
        d.exec_()

    def open_prefs(self):
        # Exact same modal title "Preferences" as VaultSafe!
        d = QDialog(self)
        d.setWindowTitle("Preferences")
        d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"Cleanup Purge Stale Cutoff (days >=): {{OR['stale_cutoff_days']}}"))
        v.addWidget(QLabel(f"Preferences Quota Seal: {{OR['preferences_quota_seal']}}"))
        bc = QPushButton("Close")
        bc.clicked.connect(d.accept)
        v.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
app.setApplicationName("treestat-analyzer")
w = TreeStatWin()
w.show()
sys.exit(app.exec_())
"""

VAULTSAFE_QT_SOURCE = f"""import json, sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QDialog, QShortcut
)
from PyQt5.QtGui import QPainter, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt, QTimer

OR = {json.dumps(VAULTSAFE_ORACLE)}
FOLDERS = [
    ("Infra_SSH", [("INFRA_JUMP_ED25519", "ROTATION_OVERDUE_112D"), ("BASTION_CA_CERT", "VALID_18D")]),
    ("Prod_TLS",  [("PROD_WILDCARD_TLS", "ROTATION_OVERDUE_95D"), ("INTERNAL_MTLS_LEAF", "VALID_11D")]),
    ("DB_Rotations", [("PG_REPLICA_SCRAM", "ROTATION_OVERDUE_104D"), ("REDIS_ACL_TOKEN", "VALID_22D")]),
]

class VaultCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(780, 420)
        self.unlocked = False
        self.f_idx = 0

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(24, 24, 37))
        qp.setFont(QFont("Monospace", 11, QFont.Bold))
        if not self.unlocked:
            qp.setPen(QColor(248, 113, 113))
            qp.drawText(45, 190, "VAULT LOCKED — Unlock via Ctrl+U (Emergency Audit PIN is in Help F1)")
            return
        fname, items = FOLDERS[self.f_idx]
        qp.setPen(QColor(52, 211, 153))
        qp.drawText(40, 50, f"UNLOCKED FOLDER [{{self.f_idx+1}}/3]: {{fname}} (Switch folders: F2 / F3 / F4)")
        qp.setPen(QColor(248, 250, 252))
        for i, (k, st) in enumerate(items):
            qp.drawText(55, 110 + i * 55, f"Entry: {{k:<24}} | Status: {{st}}")

class VaultSafeWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VaultSafe Hierarchy")
        self.setGeometry(910, 60, 840, 590)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        tbar = QHBoxLayout()
        b_un = QPushButton("Unlock Vault [Ctrl+U]")
        b_h1 = QPushButton("PIN Policy Help [F1]")
        b_f2 = QPushButton("Folder 1 [F2]")
        b_f3 = QPushButton("Folder 2 [F3]")
        b_f4 = QPushButton("Folder 3 [F4]")
        b_pf = QPushButton("Preferences [Ctrl+P]")
        b_un.clicked.connect(self.open_unlock)
        b_h1.clicked.connect(self.open_help)
        b_f2.clicked.connect(lambda: self.set_f(0))
        b_f3.clicked.connect(lambda: self.set_f(1))
        b_f4.clicked.connect(lambda: self.set_f(2))
        b_pf.clicked.connect(self.open_prefs)
        for b in (b_un, b_h1, b_f2, b_f3, b_f4, b_pf):
            tbar.addWidget(b)
        lay.addLayout(tbar)
        self.cv = VaultCanvas()
        lay.addWidget(self.cv)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Ctrl+U"), self, activated=self.open_unlock)
        QShortcut(QKeySequence("F1"), self, activated=self.open_help)
        QShortcut(QKeySequence("F2"), self, activated=lambda: self.set_f(0))
        QShortcut(QKeySequence("F3"), self, activated=lambda: self.set_f(1))
        QShortcut(QKeySequence("F4"), self, activated=lambda: self.set_f(2))
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)
        QTimer.singleShot(300, self.open_unlock)

    def set_f(self, idx):
        self.cv.f_idx = idx
        self.cv.update()

    def open_help(self):
        d = QDialog(self); d.setWindowTitle("Emergency Audit PIN Policy"); d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"Read-Only Auditor PIN: {{OR['unlock_pin_code']}} | Minimum Generator Entropy: {{OR['entropy_bits_min']}} bits"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); v.addWidget(bc)
        d.exec_()

    def open_unlock(self):
        d = QDialog(self); d.setWindowTitle("Unlock Master Vault"); d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel("Enter 4-Digit Auditor PIN (check Help F1 if needed):"))
        ed = QLineEdit()
        v.addWidget(ed)
        ok = QPushButton("Unlock")
        def _try():
            if ed.text().strip() == OR["unlock_pin_code"]:
                self.cv.unlocked = True
                self.cv.update()
            d.accept()
        ok.clicked.connect(_try)
        v.addWidget(ok)
        d.exec_()

    def open_prefs(self):
        d = QDialog(self); d.setWindowTitle("Preferences"); d.setModal(True)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"KDF: {{OR['kdf_algorithm']}} | Iterations: {{OR['kdf_iterations']}} | AutoLock: {{OR['auto_lock_seconds']}}s"))
        v.addWidget(QLabel(f"Preferences Vault Seal: {{OR['preferences_vault_seal']}}"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); v.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
app.setApplicationName("vaultsafe-hierarchy")
w = VaultSafeWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Cushion Treemap Disk Analyzer Recreation Work Order — {b}treemap_analyzer_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Explore **TreeStat Disk Analyzer** on the workstation (mount `NVME_POOL_04` in its startup modal, inspect all 8 treemap blocks and `Preferences` `Ctrl+P`) and build its standalone recreation in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Quota & Reclaim Audit Manifest ({b}/workspace/TREESTAT_AUDIT.json{b})** with exact keys:",
        f"   - {b}\"mounted_snapshot\"{b} (string), {b}\"stale_cutoff_days\"{b} (int), {b}\"total_volume_gib\"{b} (float), {b}\"reclaimable_stale_gib\"{b} (float: sum of GiB for blocks with `stale >= stale_cutoff_days`)",
        f"   - {b}\"reclaimable_dirs\"{b} (sorted list of full directory paths with `stale >= stale_cutoff_days`), {b}\"largest_active_dir\"{b} (full path of largest block with `stale < stale_cutoff_days`), {b}\"preferences_quota_seal\"{b} (string)",
        f"2. **Standalone TreeStat GUI + CLI ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Opens a window titled {b}TreeStat Disk Analyzer{b} (`>= 680 x 440` px) displaying the 8 blocks, reclaimable summary, and `Ctrl+P` Preferences dialog, AND supports `--self-test-json` printing `{{\"reclaimable_stale_gib\": ..., \"preferences_quota_seal\": ...}}`.",
        "",
    ])

    role_b = "\n".join([
        f"# Hierarchical Credential Vault Recreation Work Order — {b}cipher_vault_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Explore **VaultSafe Hierarchy** on the workstation (check `F1` PIN Policy Help, unlock via `Ctrl+U`, inspect Folders 1..3 via `F2/F3/F4` and `Preferences` `Ctrl+P`) and build its standalone recreation in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Security & Rotation Manifest ({b}/workspace/VAULTSAFE_AUDIT.json{b})** with exact keys:",
        f"   - {b}\"unlock_pin_code\"{b} (string), {b}\"kdf_algorithm\"{b} (string), {b}\"kdf_iterations\"{b} (int), {b}\"auto_lock_seconds\"{b} (int)",
        f"   - {b}\"rotation_overdue_entries\"{b} (sorted list of the 3 overdue entry names across Folders 1..3), {b}\"entropy_bits_min\"{b} (int), {b}\"preferences_vault_seal\"{b} (string)",
        f"2. **Standalone VaultSafe GUI + CLI ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Opens a window titled {b}VaultSafe Hierarchy{b} (`>= 680 x 440` px) with folder navigation, overdue entries, and `Ctrl+P` Preferences dialog, AND supports `--self-test-json` printing `{{\"kdf_algorithm\": ..., \"rotation_overdue_entries\": [...], \"preferences_vault_seal\": ...}}`.",
        "",
    ])
    return {"treemap_analyzer_dev": role_a, "cipher_vault_dev": role_b}


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
    stage_private_studio_script(state_dir, "treestat_ref.py", TREESTAT_QT_SOURCE)
    stage_private_studio_script(state_dir, "vaultsafe_ref.py", VAULTSAFE_QT_SOURCE)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None: return
        def do_GET(self) -> None:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text('{"mode":"rbs2_02"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_isolated_studio_scripts(state_dir, ["treestat_ref.py", "vaultsafe_ref.py"], wait_s=2.6)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["treemap_analyzer_dev"]
    ws_b = workspace_map["cipher_vault_dev"]

    aud_a = read_json_safe(ws_a / "TREESTAT_AUDIT.json")
    sh_a = ws_a / "recreation/run_app.sh"
    cli_a = run_cli_probe_json(sh_a, ["--self-test-json"])
    gui_a = evaluate_recreated_gui_app(sh_a, disp_num=115, expected_title_sub="TreeStat", key_sequences=[("ctrl_p", "ctrl+p")])
    ax_a = gui_a["initial_ax_text"] + "\n" + "\n".join(gui_a["after_keys_ax"].values())

    got_reclaim = sorted(aud_a.get("reclaimable_dirs") or [])
    exp_reclaim = TREESTAT_ORACLE["reclaimable_dirs"]
    rec_hits = sum(1 for d in exp_reclaim if d in got_reclaim)

    # 20 subchecks for Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json_exists", bool(aud_a), 0.04, "Missing TREESTAT_AUDIT.json"),
        ("a_snap_name", aud_a.get("mounted_snapshot") == "NVME_POOL_04", 0.05, "mounted_snapshot != 'NVME_POOL_04'"),
        ("a_cutoff_90", aud_a.get("stale_cutoff_days") == 90, 0.05, "stale_cutoff_days != 90"),
        ("a_tot_gib", isinstance(aud_a.get("total_volume_gib"), (int, float)) and abs(float(aud_a["total_volume_gib"]) - TREESTAT_ORACLE["total_volume_gib"]) <= 0.2, 0.06, "total_volume_gib mismatch"),
        ("a_reclaim_gib", isinstance(aud_a.get("reclaimable_stale_gib"), (int, float)) and abs(float(aud_a["reclaimable_stale_gib"]) - TREESTAT_ORACLE["reclaimable_stale_gib"]) <= 0.2, 0.08, "reclaimable_stale_gib != 235.0"),
        ("a_reclaim_3", rec_hits >= 3, 0.05, f"reclaimable_dirs {rec_hits}/5"),
        ("a_reclaim_all5", got_reclaim == exp_reclaim, 0.07, "reclaimable_dirs != exact 5 stale paths"),
        ("a_largest_active", aud_a.get("largest_active_dir") == "/opt/models/llama_fp8", 0.06, "largest_active_dir != '/opt/models/llama_fp8'"),
        ("a_quota_seal", aud_a.get("preferences_quota_seal") == "TSTAT-QUOTA-6630", 0.08, "preferences_quota_seal != 'TSTAT-QUOTA-6630' (twin Preferences modal)"),
        ("a_sh_exists", gui_a["script_exists"], 0.04, "Missing recreation/run_app.sh"),
        ("a_win_mapped", gui_a["window_mapped"] and "treestat" in gui_a["window_title"].lower(), 0.06, "TreeStat window not mapped"),
        ("a_visual_ok", gui_a["visual_nonblank"] and gui_a["win_w"] >= 640, 0.06, "TreeStat visual check failed"),
        ("a_visual_colors", gui_a["unique_colors_sampled"] >= 5, 0.04, "TreeStat lacks multi-color treemap rendering"),
        ("a_ax_blocks", any(k in ax_a for k in ("ckpt_shard0", "llama_fp8", "235.0")), 0.05, "TreeStat AT-SPI missing block/summary info"),
        ("a_ax_prefs", "TSTAT-QUOTA-6630" in ax_a or "Preferences" in gui_a["after_keys_ax"].get("ctrl_p", ""), 0.05, "TreeStat Ctrl+P Preferences failed"),
        ("a_cli_gib", isinstance(cli_a.get("reclaimable_stale_gib"), (int, float)) and abs(float(cli_a["reclaimable_stale_gib"]) - 235.0) <= 0.2, 0.05, "--self-test-json reclaimable_stale_gib mismatch"),
        ("a_cli_seal", cli_a.get("preferences_quota_seal") == "TSTAT-QUOTA-6630", 0.05, "--self-test-json preferences_quota_seal mismatch"),
        ("a_no_active_in_stale", "/opt/models/llama_fp8" not in got_reclaim, 0.02, "Active dir wrongly marked stale"),
        ("a_no_wal_in_stale", "/srv/pg_wal_archive" not in got_reclaim, 0.02, "45d WAL wrongly marked stale"),
        ("a_win_height", gui_a["win_h"] >= 400, 0.02, "Window height < 400"),
    ]

    aud_b = read_json_safe(ws_b / "VAULTSAFE_AUDIT.json")
    sh_b = ws_b / "recreation/run_app.sh"
    cli_b = run_cli_probe_json(sh_b, ["--self-test-json"])
    gui_b = evaluate_recreated_gui_app(sh_b, disp_num=116, expected_title_sub="VaultSafe", key_sequences=[("ctrl_p", "ctrl+p")])
    ax_b = gui_b["initial_ax_text"] + "\n" + "\n".join(gui_b["after_keys_ax"].values())

    got_ov = sorted(aud_b.get("rotation_overdue_entries") or [])
    exp_ov = sorted(VAULTSAFE_ORACLE["rotation_overdue_entries"])

    # 20 subchecks for Role B (20 + 20 = 40 total subchecks!)
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json_exists", bool(aud_b), 0.04, "Missing VAULTSAFE_AUDIT.json"),
        ("b_pin", str(aud_b.get("unlock_pin_code", "")) == "7391", 0.06, "unlock_pin_code != '7391'"),
        ("b_kdf_alg", aud_b.get("kdf_algorithm") == "ARGON2ID_64MIB", 0.06, "kdf_algorithm != 'ARGON2ID_64MIB'"),
        ("b_kdf_iter", aud_b.get("kdf_iterations") == 4, 0.05, "kdf_iterations != 4"),
        ("b_autolock", aud_b.get("auto_lock_seconds") == 180, 0.05, "auto_lock_seconds != 180"),
        ("b_ov_atleast2", sum(1 for x in exp_ov if x in got_ov) >= 2, 0.06, "Fewer than 2 overdue entries found"),
        ("b_ov_exact3", got_ov == exp_ov, 0.08, f"rotation_overdue_entries={got_ov} != {exp_ov}"),
        ("b_entropy", aud_b.get("entropy_bits_min") == 128, 0.05, "entropy_bits_min != 128"),
        ("b_vault_seal", aud_b.get("preferences_vault_seal") == "VSAFE-KDF-9912", 0.08, "preferences_vault_seal != 'VSAFE-KDF-9912' (twin Preferences modal)"),
        ("b_sh_exists", gui_b["script_exists"], 0.04, "Missing recreation/run_app.sh"),
        ("b_win_mapped", gui_b["window_mapped"] and "vaultsafe" in gui_b["window_title"].lower(), 0.06, "VaultSafe window not mapped"),
        ("b_visual_ok", gui_b["visual_nonblank"] and gui_b["win_w"] >= 640, 0.06, "VaultSafe visual check failed"),
        ("b_ax_entries", any(k in ax_b for k in ("INFRA_JUMP_ED25519", "PROD_WILDCARD_TLS", "PG_REPLICA_SCRAM")), 0.06, "VaultSafe AT-SPI missing overdue entries"),
        ("b_ax_prefs", "VSAFE-KDF-9912" in ax_b or "Preferences" in gui_b["after_keys_ax"].get("ctrl_p", ""), 0.05, "VaultSafe Ctrl+P Preferences failed"),
        ("b_cli_kdf", cli_b.get("kdf_algorithm") == "ARGON2ID_64MIB", 0.05, "--self-test-json kdf_algorithm mismatch"),
        ("b_cli_ov", sorted(cli_b.get("rotation_overdue_entries") or []) == exp_ov, 0.05, "--self-test-json rotation_overdue_entries mismatch"),
        ("b_cli_seal", cli_b.get("preferences_vault_seal") == "VSAFE-KDF-9912", 0.04, "--self-test-json preferences_vault_seal mismatch"),
        ("b_no_valid_in_ov", "BASTION_CA_CERT" not in got_ov and "REDIS_ACL_TOKEN" not in got_ov, 0.02, "Valid entry wrongly flagged overdue"),
        ("b_visual_colors", gui_b["unique_colors_sampled"] >= 4, 0.02, "VaultSafe visual styling blank"),
        ("b_win_height", gui_b["win_h"] >= 400, 0.02, "Window height < 400"),
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
    assert role in ("treemap_analyzer_dev", "cipher_vault_dev")
    ws = workspace_map[role]
    rec = ws / "recreation"
    rec.mkdir(parents=True, exist_ok=True)

    def _work() -> None:
        if role == "treemap_analyzer_dev":
            write_json(ws / "TREESTAT_AUDIT.json", TREESTAT_ORACLE)
            app_py = (
                "import json, sys\n"
                f"OR = {repr(TREESTAT_ORACLE)}\n"
                "if '--self-test-json' in sys.argv:\n"
                "    print(json.dumps({'reclaimable_stale_gib': OR['reclaimable_stale_gib'], 'preferences_quota_seal': OR['preferences_quota_seal']}))\n"
                "    sys.exit(0)\n"
                "from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QDialog, QShortcut\n"
                "from PyQt5.QtGui import QKeySequence\n"
                "app = QApplication(sys.argv); w = QMainWindow(); w.setWindowTitle('TreeStat Disk Analyzer'); w.resize(720, 480)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#0f172a;color:#f8fafc;'); v = QVBoxLayout(cw)\n"
                "l1 = QLabel('Reclaimable: 235.0 GiB | ckpt_shard0 | llama_fp8'); l1.setStyleSheet('background:#dc2626;color:#fff;padding:10px;')\n"
                "l2 = QLabel('Quota Seal: ' + OR['preferences_quota_seal']); l2.setStyleSheet('background:#2563eb;color:#fff;padding:10px;')\n"
                "b1 = QPushButton('Preferences'); b1.setStyleSheet('background:#059669;color:#fff;padding:8px;')\n"
                "def sp():\n"
                "    d = QDialog(w); d.setWindowTitle('Preferences'); lv = QVBoxLayout(d); lv.addWidget(QLabel(OR['preferences_quota_seal'])); d.show()\n"
                "b1.clicked.connect(sp); QShortcut(QKeySequence('Ctrl+P'), w, activated=sp)\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1); w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "treestat.py").write_text(app_py, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/treestat.py\" \"$@\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)
        else:
            write_json(ws / "VAULTSAFE_AUDIT.json", VAULTSAFE_ORACLE)
            app_py = (
                "import json, sys\n"
                f"OR = {repr(VAULTSAFE_ORACLE)}\n"
                "if '--self-test-json' in sys.argv:\n"
                "    print(json.dumps({'kdf_algorithm': OR['kdf_algorithm'], 'rotation_overdue_entries': OR['rotation_overdue_entries'], 'preferences_vault_seal': OR['preferences_vault_seal']}))\n"
                "    sys.exit(0)\n"
                "from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QDialog, QShortcut\n"
                "from PyQt5.QtGui import QKeySequence\n"
                "app = QApplication(sys.argv); w = QMainWindow(); w.setWindowTitle('VaultSafe Hierarchy'); w.resize(720, 480)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#181825;color:#f8fafc;'); v = QVBoxLayout(cw)\n"
                "l1 = QLabel('Overdue: ' + ', '.join(OR['rotation_overdue_entries'])); l1.setStyleSheet('background:#7c3aed;color:#fff;padding:10px;')\n"
                "l2 = QLabel('KDF: ' + OR['kdf_algorithm'] + ' | Seal: ' + OR['preferences_vault_seal']); l2.setStyleSheet('background:#059669;color:#fff;padding:10px;')\n"
                "b1 = QPushButton('Preferences'); b1.setStyleSheet('background:#2563eb;color:#fff;padding:8px;')\n"
                "def sp():\n"
                "    d = QDialog(w); d.setWindowTitle('Preferences'); lv = QVBoxLayout(d); lv.addWidget(QLabel(OR['preferences_vault_seal'])); d.show()\n"
                "b1.clicked.connect(sp); QShortcut(QKeySequence('Ctrl+P'), w, activated=sp)\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1); w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "vaultsafe.py").write_text(app_py, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/vaultsafe.py\" \"$@\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_2 Dual Startup Modal & Twin Preferences Hijack): Swapped Preferences seal under collision."""
    solve_role("treemap_analyzer_dev", workspace_map, port, careful_conc=False)
    solve_role("cipher_vault_dev", workspace_map, port, careful_conc=False)
    ws_a = workspace_map["treemap_analyzer_dev"]
    bad = read_json_safe(ws_a / "TREESTAT_AUDIT.json")
    bad["preferences_quota_seal"] = VAULTSAFE_ORACLE["preferences_vault_seal"]
    bad["reclaimable_stale_gib"] = 0.0
    write_json(ws_a / "TREESTAT_AUDIT.json", bad)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

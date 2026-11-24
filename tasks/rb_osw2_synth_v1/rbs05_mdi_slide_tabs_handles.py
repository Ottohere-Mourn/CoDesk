"""RBS-05: Deep OSW2-P3 Twin — Single-Window Multi-Tab DeckCraft MDI Handle Drag & Eyedropper.

Grounded in OSWorld-V2 Empirical Laws (OSW2-P3 v2/063 + v2/066 & OSW2-P13 WPS MDI):
  - LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN: One single-window MDI presentation
    editor (`DeckCraft Studio`) hosts two sibling deck tabs (`Tab 1: SiriLaunch_Deck` on Alt+1
    and `Tab 2: CloudArch_Deck` on Alt+2), sharing ONE active tab, ONE Eyedropper color
    register (`Alt+E`), ONE Speaker-Notes modal (`Ctrl+N`), and ONE `Ctrl+S` save target.
  - LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB: Dragging yellow callout/connector handles
    on the active slide canvas fails or mutates the wrong deck if the peer switches MDI tabs.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from typing import Any

from tasks.rb_osw2_synth_v1.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    build_grade_payload,
    read_json_safe,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS-05"
PORTAL_PORT = 19305

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Single-Window Multi-Tab DeckCraft MDI: Siri Bubble-Handle Drag vs. Cloud Topology Eyedropper",
    "domain": "Single-Window MDI Presentation Design, Bezier Handle Routing & Brand Eyedropper Styling",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN",
        "LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("launch_deck_designer", "arch_deck_designer"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "deep_coupled_workbench",
        "total_subchecks": 28,
        "cli_bypass_resistance": 0.97,
        "role_a": {
            "slug": "launch_deck_designer",
            "est_role_seconds": 480.0,
            "traits": [
                "single_instance_mdi_or_soffice",
                "custom_2d_canvas_drag",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "arch_deck_designer",
            "est_role_seconds": 490.0,
            "traits": [
                "single_instance_mdi_or_soffice",
                "custom_2d_canvas_drag",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

MDI_SIGN_SALT = "deckcraft-mdi-rbs05-912"
LAUNCH_SWATCH_HEX = "#0EA5E9"
ARCH_SWATCH_HEX = "#10B981"

LAUNCH_NOTES_ORACLE = {
    "deck_id": "SIRI_LAUNCH_2026",
    "target_anchor_xy": [520, 210],
    "ring_zorder_mode": "INTERLEAVED_RING_FRONT",
    "brand_swatch_hex": LAUNCH_SWATCH_HEX,
    "kpi_card_gap_px": 24,
    "speaker_notes_code": "NOTES-SIRI-3301",
}

ARCH_NOTES_ORACLE = {
    "deck_id": "CLOUD_ARCH_Q4",
    "target_port_xy": [610, 250],
    "connector_routing_mode": "ORTHOGONAL_24PX_SNAP",
    "theme_swatch_hex": ARCH_SWATCH_HEX,
    "footer_margin_px": 32,
    "speaker_notes_code": "NOTES-ARCH-7705",
}


def compute_deck_seal(deck_id: str, handle_ok: bool, z_ok: bool, swatch: str, layout_ok: bool) -> str:
    raw = f"{MDI_SIGN_SALT}:{deck_id}:{handle_ok}:{z_ok}:{swatch}:{layout_ok}"
    return "DCF-SEAL-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10].upper()


DECKCRAFT_MDI_QT_SOURCE = f"""import hashlib, json, math, os, sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QDialog, QShortcut
)
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QKeySequence, QPixmap
from PyQt5.QtCore import Qt, QPointF

SALT = {json.dumps(MDI_SIGN_SALT)}
L_OR = {json.dumps(LAUNCH_NOTES_ORACLE)}
A_OR = {json.dumps(ARCH_NOTES_ORACLE)}

def make_seal(did, h_ok, z_ok, sw, l_ok):
    raw = f"{{SALT}}:{{did}}:{{h_ok}}:{{z_ok}}:{{sw}}:{{l_ok}}"
    return "DCF-SEAL-" + hashlib.sha256(raw.encode()).hexdigest()[:10].upper()

class DeckCanvas(QWidget):
    def __init__(self, kind, on_change):
        super().__init__()
        self.kind = kind  # 'launch' or 'arch'
        self.on_change = on_change
        self.setMinimumSize(860, 440)
        self.handle = [190, 350] if kind == "launch" else [220, 360]
        self.target = L_OR["target_anchor_xy"] if kind == "launch" else A_OR["target_port_xy"]
        self.z_fixed = False
        self.layout_fixed = False
        self.applied_swatch = "#94A3B8"
        self.dragging = False

    def handle_ok(self):
        return math.hypot(self.handle[0] - self.target[0], self.handle[1] - self.target[1]) <= 36.0

    def mousePressEvent(self, ev):
        p = ev.pos()
        if math.hypot(p.x() - self.handle[0], p.y() - self.handle[1]) <= 28.0:
            self.dragging = True

    def mouseMoveEvent(self, ev):
        if not self.dragging:
            return
        self.handle = [max(40, min(820, ev.pos().x())), max(40, min(400, ev.pos().y()))]
        self.on_change()
        self.update()

    def mouseReleaseEvent(self, _ev):
        self.dragging = False

    def paintEvent(self, _ev):
        qp = QPainter(self)
        bg = QColor(15, 23, 42) if self.kind == "launch" else QColor(24, 24, 37)
        qp.fillRect(self.rect(), bg)
        # Reference swatch chip at top-right (740, 30, 90, 45)
        ref_hex = L_OR["brand_swatch_hex"] if self.kind == "launch" else A_OR["theme_swatch_hex"]
        qp.fillRect(730, 28, 95, 44, QColor(ref_hex))
        qp.setPen(QColor(255, 255, 255))
        qp.setFont(QFont("Monospace", 9, QFont.Bold))
        qp.drawText(732, 22, f"REF:{{ref_hex}}")

        # Applied theme card
        qp.fillRect(45, 45, 250, 110, QColor(self.applied_swatch))
        qp.setPen(QColor(255, 255, 255))
        qp.drawText(55, 85, f"Applied Swatch: {{self.applied_swatch}}")
        qp.drawText(55, 112, f"Z-Order Fixed: {{self.z_fixed}}")
        qp.drawText(55, 138, f"Grid/Bounds Fixed: {{self.layout_fixed}}")

        # Target anchor ring (green dashed)
        tx, ty = self.target
        qp.setPen(QPen(QColor(52, 211, 153), 3, Qt.DashLine))
        qp.setBrush(QBrush(QColor(16, 185, 129, 50)))
        qp.drawEllipse(QPointF(tx, ty), 28.0, 28.0)
        qp.drawText(tx - 45, ty - 34, f"TARGET({{tx}},{{ty}})")

        # Connector / Bubble tail line + Yellow Drag Handle (250, 204, 21)
        qp.setPen(QPen(QColor(250, 204, 21), 3))
        qp.drawLine(170, 260, self.handle[0], self.handle[1])
        qp.setBrush(QBrush(QColor(250, 204, 21)))
        qp.setPen(QPen(QColor(15, 23, 42), 2))
        qp.drawEllipse(QPointF(self.handle[0], self.handle[1]), 14.0, 14.0)
        qp.setPen(QColor(254, 240, 138))
        qp.drawText(self.handle[0] - 38, self.handle[1] + 28, f"HANDLE({{self.handle[0]}},{{self.handle[1]}})")

class DeckCraftMDI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeckCraft Studio MDI")
        self.resize(960, 660)
        # Single shared Eyedropper register across the entire MDI window!
        self.shared_eyedropper_hex = "#94A3B8"

        cw = QWidget()
        lay = QVBoxLayout(cw)
        tbar = QHBoxLayout()
        b_t1 = QPushButton("Tab 1: SiriLaunch [Alt+1]")
        b_t2 = QPushButton("Tab 2: CloudArch [Alt+2]")
        b_eye = QPushButton("Sample Tab Ref Swatch [Alt+E]")
        b_app = QPushButton("Apply Eyedropper to Active Tab [Alt+A]")
        b_zo = QPushButton("Fix Z-Order / Connector Layer [Alt+Z]")
        b_ly = QPushButton("Snap KPI / Footer Bounds [Alt+G]")
        b_nt = QPushButton("Speaker Notes [Ctrl+N]")
        b_sv = QPushButton("Save & Export Active Tab [Ctrl+S]")
        for b in (b_t1, b_t2, b_eye, b_app, b_zo, b_ly, b_nt, b_sv):
            tbar.addWidget(b)
        lay.addLayout(tbar)

        self.banner = QLabel()
        self.banner.setStyleSheet("font-family: monospace; font-size: 12px; padding: 6px; background: #1e293b; color: #f8fafc;")
        lay.addWidget(self.banner)

        self.tabs = QTabWidget()
        self.cv_launch = DeckCanvas("launch", self.refresh)
        self.cv_arch = DeckCanvas("arch", self.refresh)
        self.tabs.addTab(self.cv_launch, "Tab 1: SiriLaunch_Deck.dcf")
        self.tabs.addTab(self.cv_arch, "Tab 2: CloudArch_Deck.dcf")
        self.tabs.currentChanged.connect(lambda *_: self.refresh())
        lay.addWidget(self.tabs)
        self.setCentralWidget(cw)

        b_t1.clicked.connect(lambda: self.tabs.setCurrentIndex(0))
        b_t2.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        b_eye.clicked.connect(self.sample_swatch)
        b_app.clicked.connect(self.apply_swatch)
        b_zo.clicked.connect(self.fix_zorder)
        b_ly.clicked.connect(self.fix_layout)
        b_nt.clicked.connect(self.show_notes)
        b_sv.clicked.connect(self.save_active)

        QShortcut(QKeySequence("Alt+1"), self, activated=lambda: self.tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Alt+2"), self, activated=lambda: self.tabs.setCurrentIndex(1))
        QShortcut(QKeySequence("Alt+E"), self, activated=self.sample_swatch)
        QShortcut(QKeySequence("Alt+A"), self, activated=self.apply_swatch)
        QShortcut(QKeySequence("Alt+Z"), self, activated=self.fix_zorder)
        QShortcut(QKeySequence("Alt+G"), self, activated=self.fix_layout)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.show_notes)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_active)
        self.refresh()

    def active_cv(self):
        return self.cv_launch if self.tabs.currentIndex() == 0 else self.cv_arch

    def sample_swatch(self):
        cv = self.active_cv()
        self.shared_eyedropper_hex = L_OR["brand_swatch_hex"] if cv.kind == "launch" else A_OR["theme_swatch_hex"]
        self.refresh()

    def apply_swatch(self):
        cv = self.active_cv()
        cv.applied_swatch = self.shared_eyedropper_hex
        cv.update()
        self.refresh()

    def fix_zorder(self):
        cv = self.active_cv()
        cv.z_fixed = True
        cv.update()
        self.refresh()

    def fix_layout(self):
        cv = self.active_cv()
        cv.layout_fixed = True
        cv.update()
        self.refresh()

    def show_notes(self):
        cv = self.active_cv()
        info = L_OR if cv.kind == "launch" else A_OR
        d = QDialog(self)
        d.setWindowTitle("Speaker Notes & Layout Spec")
        d.setModal(True)
        v = QVBoxLayout(d)
        for k, val in info.items():
            v.addWidget(QLabel(f"{{k}}: {{val}}"))
        bc = QPushButton("Close")
        bc.clicked.connect(d.accept)
        v.addWidget(bc)
        d.exec_()

    def save_active(self):
        cv = self.active_cv()
        is_l = (cv.kind == "launch")
        info = L_OR if is_l else A_OR
        did = info["deck_id"]
        h_ok = cv.handle_ok()
        seal = make_seal(did, h_ok, cv.z_fixed, cv.applied_swatch, cv.layout_fixed)
        out_dir = Path("/workspace/decks")
        exp_dir = Path("/workspace/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        exp_dir.mkdir(parents=True, exist_ok=True)
        fn = "SiriLaunch_Deck.dcf.json" if is_l else "CloudArch_Deck.dcf.json"
        payload = {{
            "deck_id": did,
            "handle_xy": cv.handle,
            "handle_on_target": h_ok,
            "z_fixed": cv.z_fixed,
            "applied_swatch": cv.applied_swatch,
            "layout_fixed": cv.layout_fixed,
            "deck_seal": seal,
        }}
        p = out_dir / fn
        p.write_text(json.dumps(payload, indent=2) + "\\n")
        os.chmod(p, 0o666)
        pix = cv.grab()
        png_p = exp_dir / ("launch_deck_final.png" if is_l else "arch_deck_final.png")
        pix.save(str(png_p), "PNG")
        os.chmod(png_p, 0o666)
        self.banner.setText(f"SAVED {{fn}} | handle_ok={{h_ok}} | swatch={{cv.applied_swatch}} | seal={{seal}}")

    def refresh(self):
        cv = self.active_cv()
        nm = "Tab1:SiriLaunch" if cv.kind == "launch" else "Tab2:CloudArch"
        self.banner.setText(
            f"ACTIVE={{nm}} | SharedEyedropper={{self.shared_eyedropper_hex}} | "
            f"HandleOK={{cv.handle_ok()}} | Z={{cv.z_fixed}} | Swatch={{cv.applied_swatch}} | Grid={{cv.layout_fixed}}"
        )

app = QApplication(sys.argv)
w = DeckCraftMDI()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Launch Keynote Slide Remediation Work Order — {b}launch_deck_designer{b}",
        "",
        "## Scope & Deliverables",
        f"Remediate **Tab 1: SiriLaunch_Deck.dcf** inside the live **DeckCraft Studio MDI** presentation editor and write your verification manifest in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Interactive Slide Remediation & Signed Export ({b}/workspace/decks/SiriLaunch_Deck.dcf.json{b} & {b}/workspace/exports/launch_deck_final.png{b})**:",
        "   - Select **Tab 1: SiriLaunch_Deck.dcf** (`Alt+1`) and inspect its **Speaker Notes** (`Ctrl+N`).",
        "   - Drag the yellow speech-bubble tail `HANDLE` onto the green `TARGET(520,210)` anchor ring (`handle_on_target = true`).",
        "   - Sample Tab 1's reference swatch into the Eyedropper (`Alt+E`) and apply it to Tab 1 (`Alt+A`, verifying `#0EA5E9`), enable ring Z-order interleaving (`Alt+Z`), snap KPI card spacing (`Alt+G`), and save/export Tab 1 (`Ctrl+S`).",
        f"2. **Launch Deck Audit Manifest ({b}/workspace/LAUNCH_DECK_AUDIT.json{b})** with exact keys:",
        f"   - {b}\"deck_id\"{b}, {b}\"target_anchor_xy\"{b}, {b}\"ring_zorder_mode\"{b}, {b}\"brand_swatch_hex\"{b}, {b}\"kpi_card_gap_px\"{b}, {b}\"speaker_notes_code\"{b}, and {b}\"verified_deck_seal\"{b} (`DCF-SEAL-...` from the saved `.dcf.json`).",
        "",
    ])

    role_b = "\n".join([
        f"# Cloud Architecture Topology Deck Remediation Work Order — {b}arch_deck_designer{b}",
        "",
        "## Scope & Deliverables",
        f"Remediate **Tab 2: CloudArch_Deck.dcf** inside the live **DeckCraft Studio MDI** presentation editor and write your verification manifest in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **Interactive Slide Remediation & Signed Export ({b}/workspace/decks/CloudArch_Deck.dcf.json{b} & {b}/workspace/exports/arch_deck_final.png{b})**:",
        "   - Select **Tab 2: CloudArch_Deck.dcf** (`Alt+2`) and inspect its **Speaker Notes** (`Ctrl+N`).",
        "   - Drag the yellow orthogonal connector `HANDLE` onto the green `TARGET(610,250)` port ring (`handle_on_target = true`).",
        "   - Sample Tab 2's reference swatch into the Eyedropper (`Alt+E`) and apply it to Tab 2 (`Alt+A`, verifying `#10B981`), fix connector layer Z-order (`Alt+Z`), snap footer bounds (`Alt+G`), and save/export Tab 2 (`Ctrl+S`).",
        f"2. **Architecture Deck Audit Manifest ({b}/workspace/ARCH_DECK_AUDIT.json{b})** with exact keys:",
        f"   - {b}\"deck_id\"{b}, {b}\"target_port_xy\"{b}, {b}\"connector_routing_mode\"{b}, {b}\"theme_swatch_hex\"{b}, {b}\"footer_margin_px\"{b}, {b}\"speaker_notes_code\"{b}, and {b}\"verified_deck_seal\"{b} (`DCF-SEAL-...` from the saved `.dcf.json`).",
        "",
    ])
    return {"launch_deck_designer": role_a, "arch_deck_designer": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    (ws / "decks").mkdir(parents=True, exist_ok=True)
    (ws / "exports").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    stage_private_studio_script(state_dir, "deckcraft_mdi.py", DECKCRAFT_MDI_QT_SOURCE)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            raw = b'{"ok":true}'
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text('{"mode":"rbs05_mdi"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_isolated_studio_scripts(state_dir, ["deckcraft_mdi.py"], wait_s=2.4)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image

    ws = next(iter(workspace_map.values()))
    d_a = read_json_safe(ws / "decks/SiriLaunch_Deck.dcf.json")
    d_b = read_json_safe(ws / "decks/CloudArch_Deck.dcf.json")
    aud_a = read_json_safe(ws / "LAUNCH_DECK_AUDIT.json")
    aud_b = read_json_safe(ws / "ARCH_DECK_AUDIT.json")

    exp_seal_a = compute_deck_seal("SIRI_LAUNCH_2026", True, True, LAUNCH_SWATCH_HEX, True)
    exp_seal_b = compute_deck_seal("CLOUD_ARCH_Q4", True, True, ARCH_SWATCH_HEX, True)

    png_a = ws / "exports/launch_deck_final.png"
    png_b = ws / "exports/arch_deck_final.png"
    pa_ok = False
    if png_a.is_file() and png_a.stat().st_size > 1500:
        try:
            with Image.open(png_a) as im:
                pa_ok = im.size[0] >= 800 and im.size[1] >= 400
        except Exception:
            pa_ok = False
    pb_ok = False
    if png_b.is_file() and png_b.stat().st_size > 1500:
        try:
            with Image.open(png_b) as im:
                pb_ok = im.size[0] >= 800 and im.size[1] >= 400
        except Exception:
            pb_ok = False

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_dcf_exists", bool(d_a), 0.06, "Missing SiriLaunch_Deck.dcf.json"),
        ("a_handle_target", d_a.get("handle_on_target") is True, 0.12, "Tab 1 bubble handle not on target (520,210)"),
        ("a_z_fixed", d_a.get("z_fixed") is True, 0.08, "Tab 1 ring z_fixed != true"),
        ("a_swatch_hex", str(d_a.get("applied_swatch", "")).upper() == LAUNCH_SWATCH_HEX, 0.10, f"Tab 1 applied_swatch={d_a.get('applied_swatch')} != {LAUNCH_SWATCH_HEX} (shared Eyedropper collision)"),
        ("a_layout_fixed", d_a.get("layout_fixed") is True, 0.08, "Tab 1 layout_fixed != true"),
        ("a_authentic_seal", d_a.get("deck_seal") == exp_seal_a, 0.12, "Tab 1 deck_seal invalid or incomplete"),
        ("a_export_png", pa_ok, 0.08, "Missing or invalid exports/launch_deck_final.png"),
        ("a_aud_deck_id", aud_a.get("deck_id") == "SIRI_LAUNCH_2026", 0.05, "Audit deck_id mismatch"),
        ("a_aud_anchor", aud_a.get("target_anchor_xy") == [520, 210], 0.05, "Audit target_anchor_xy != [520, 210]"),
        ("a_aud_zmode", aud_a.get("ring_zorder_mode") == "INTERLEAVED_RING_FRONT", 0.05, "Audit ring_zorder_mode mismatch"),
        ("a_aud_swatch", str(aud_a.get("brand_swatch_hex", "")).upper() == LAUNCH_SWATCH_HEX, 0.05, "Audit brand_swatch_hex mismatch"),
        ("a_aud_gap", aud_a.get("kpi_card_gap_px") == 24, 0.05, "Audit kpi_card_gap_px != 24"),
        ("a_aud_notes_code", aud_a.get("speaker_notes_code") == "NOTES-SIRI-3301", 0.06, "Audit speaker_notes_code != 'NOTES-SIRI-3301'"),
        ("a_aud_seal_match", aud_a.get("verified_deck_seal") == exp_seal_a, 0.05, "Audit verified_deck_seal mismatch"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_dcf_exists", bool(d_b), 0.06, "Missing CloudArch_Deck.dcf.json"),
        ("b_handle_target", d_b.get("handle_on_target") is True, 0.12, "Tab 2 connector handle not on target (610,250)"),
        ("b_z_fixed", d_b.get("z_fixed") is True, 0.08, "Tab 2 z_fixed != true"),
        ("b_swatch_hex", str(d_b.get("applied_swatch", "")).upper() == ARCH_SWATCH_HEX, 0.10, f"Tab 2 applied_swatch={d_b.get('applied_swatch')} != {ARCH_SWATCH_HEX} (shared Eyedropper collision)"),
        ("b_layout_fixed", d_b.get("layout_fixed") is True, 0.08, "Tab 2 layout_fixed != true"),
        ("b_authentic_seal", d_b.get("deck_seal") == exp_seal_b, 0.12, "Tab 2 deck_seal invalid or incomplete"),
        ("b_export_png", pb_ok, 0.08, "Missing or invalid exports/arch_deck_final.png"),
        ("b_aud_deck_id", aud_b.get("deck_id") == "CLOUD_ARCH_Q4", 0.05, "Audit deck_id mismatch"),
        ("b_aud_port", aud_b.get("target_port_xy") == [610, 250], 0.05, "Audit target_port_xy != [610, 250]"),
        ("b_aud_rmode", aud_b.get("connector_routing_mode") == "ORTHOGONAL_24PX_SNAP", 0.05, "Audit connector_routing_mode mismatch"),
        ("b_aud_swatch", str(aud_b.get("theme_swatch_hex", "")).upper() == ARCH_SWATCH_HEX, 0.05, "Audit theme_swatch_hex mismatch"),
        ("b_aud_margin", aud_b.get("footer_margin_px") == 32, 0.05, "Audit footer_margin_px != 32"),
        ("b_aud_notes_code", aud_b.get("speaker_notes_code") == "NOTES-ARCH-7705", 0.06, "Audit speaker_notes_code != 'NOTES-ARCH-7705'"),
        ("b_aud_seal_match", aud_b.get("verified_deck_seal") == exp_seal_b, 0.05, "Audit verified_deck_seal mismatch"),
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
    assert role in ("launch_deck_designer", "arch_deck_designer")
    ws = next(iter(workspace_map.values()))

    def _work() -> None:
        is_l = (role == "launch_deck_designer")
        tab_key = "alt+1" if is_l else "alt+2"
        tx, ty = (520, 210) if is_l else (610, 250)
        gui_sh = (
            "export DISPLAY=:99; "
            "wid=$(xdotool search --onlyvisible --name 'DeckCraft Studio MDI' | tail -n 1); "
            "wmctrl -i -r \"$wid\" -e 0,120,60,960,660; "
            "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.3; "
            f"xdotool key --clearmodifiers {tab_key}; sleep 0.35; "
            "python3 - <<'PY'\n"
            "import io, subprocess\n"
            "from PIL import Image\n"
            "raw = subprocess.check_output(['import', '-window', 'root', 'png:-'])\n"
            "im = Image.open(io.BytesIO(raw)).convert('RGB')\n"
            "yel, grn = [], []\n"
            "for x in range(140, 1060, 2):\n"
            "    for y in range(160, 700, 2):\n"
            "        r, g, b = im.getpixel((x, y))\n"
            "        if r > 225 and 185 <= g <= 220 and b < 55:\n"
            "            yel.append((x, y))\n"
            "        elif r < 65 and g > 185 and 125 <= b <= 175:\n"
            "            grn.append((x, y))\n"
            "hx = sum(p[0] for p in yel)//len(yel); hy = sum(p[1] for p in yel)//len(yel)\n"
            "gx = sum(p[0] for p in grn)//len(grn); gy = sum(p[1] for p in grn)//len(grn)\n"
            "subprocess.run(['xdotool', 'mousemove', str(hx), str(hy), 'mousedown', '1'], check=True)\n"
            "for k in range(1, 9):\n"
            "    nx = int(hx + (gx - hx)*k/8); ny = int(hy + (gy - hy)*k/8)\n"
            "    subprocess.run(['xdotool', 'mousemove', str(nx), str(ny)], check=True)\n"
            "subprocess.run(['xdotool', 'mouseup', '1'], check=True)\n"
            "PY\n"
            "sleep 0.2; wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.15; "
            f"xdotool key --clearmodifiers {tab_key}; sleep 0.15; "
            "xdotool key --clearmodifiers alt+e; sleep 0.15; "
            "xdotool key --clearmodifiers alt+a; sleep 0.15; "
            "xdotool key --clearmodifiers alt+z; sleep 0.15; "
            "xdotool key --clearmodifiers alt+g; sleep 0.15; "
            "xdotool key --clearmodifiers ctrl+s; sleep 0.45"
        )
        del tx, ty
        subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=25)
        if is_l:
            saved = read_json_safe(ws / "decks/SiriLaunch_Deck.dcf.json")
            write_json(ws / "LAUNCH_DECK_AUDIT.json", {**LAUNCH_NOTES_ORACLE, "verified_deck_seal": saved["deck_seal"]})
        else:
            saved = read_json_safe(ws / "decks/CloudArch_Deck.dcf.json")
            write_json(ws / "ARCH_DECK_AUDIT.json", {**ARCH_NOTES_ORACLE, "verified_deck_seal": saved["deck_seal"]})

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_6 MDI Tab & Shared Eyedropper Collision): Peer switches to Tab 2 mid-Eyedropper apply."""
    solve_role("launch_deck_designer", workspace_map, port, careful_conc=False)
    solve_role("arch_deck_designer", workspace_map, port, careful_conc=False)
    # Simulate shared Eyedropper overwrite: Tab 1 accidentally saved with Tab 2's #10B981 swatch!
    race_sh = (
        "export DISPLAY=:99; "
        "wid=$(xdotool search --onlyvisible --name 'DeckCraft Studio MDI' | tail -n 1); "
        "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.2; "
        "xdotool key --clearmodifiers alt+2; sleep 0.15; "
        "xdotool key --clearmodifiers alt+e; sleep 0.15; "
        "xdotool key --clearmodifiers alt+1; sleep 0.15; "
        "xdotool key --clearmodifiers alt+a; sleep 0.15; "
        "xdotool key --clearmodifiers ctrl+s; sleep 0.4"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", race_sh], check=True, capture_output=True, timeout=15)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

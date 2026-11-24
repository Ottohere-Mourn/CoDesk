"""RBS2-01: CutForge Video NLE Timeline/Watermark/Masking vs. ScoreCanvas Musical Staff Transcriber.

Grounded in OSWorld-V2 (OSW2-P10/P11 Shotcut + MuseScore) & RecreationBench (LAW_1 + LAW_5 + LAW_7):
  - LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI: CutForge NLE renders watermark crop height (84px) and
    3 hazard mask boxes purely onto a custom QPainter video preview canvas across keyframes
    1/2/3; ScoreCanvas renders an 8-measure treble staff purely via QPainter noteheads.
  - LAW_1_KEYSTROKE_MISROUTING: Both apps bind single-key shortcuts `1`, `2`, `3`, `Space`, and
    `Ctrl+E` on shared `:99`, causing cross-window transport/measure jumps under concurrency.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
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

TASK_ID = "RBS2-01"
PORTAL_PORT = 19401

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "CutForge NLE Watermark-Crop & Hazard Masking vs. ScoreCanvas 8-Bar Staff Transcription",
    "domain": "Non-Linear Video Editing (FFmpeg/NLE) & Musical Staff Transcription / GUI Tooling",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_1_KEYSTROKE_MISROUTING",
        "LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB",
    ),
    "roles": ("video_timeline_editor", "score_transcriber_dev"),
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
            "slug": "video_timeline_editor",
            "est_role_seconds": 540.0,
            "traits": [
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "custom_2d_canvas_drag",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "score_transcriber_dev",
            "est_role_seconds": 560.0,
            "traits": [
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "iterative_keyboard_shortcuts",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

NLE_SALT = "cutforge-nle-rbs201"
WATERMARK_CROP_TOP_PX = 84
# Raw clip is 1280x804 -> cropping top 84px yields clean 1280x720!
# 3 hazard keyframes (kf_idx, frame_no, t_sec, x, y_after_crop, w, h)
HAZARD_KEYFRAMES: list[tuple[int, int, float, int, int, int, int]] = [
    (1, 24, 1.0, 260, 180, 160, 120),
    (2, 72, 3.0, 560, 220, 160, 120),
    (3, 120, 5.0, 860, 190, 160, 120),
]

MELODY_MEASURES: list[tuple[int, str, int, str]] = [
    (1, "E", 4, "quarter"),
    (2, "G", 4, "quarter"),
    (3, "A", 4, "half"),
    (4, "C", 5, "quarter"),
    (5, "D", 5, "quarter"),
    (6, "B", 4, "half"),
    (7, "G", 4, "quarter"),
    (8, "E", 4, "whole"),
]
SCORE_ORACLE = {
    "tempo_bpm": 108,
    "time_signature": "4/4",
    "key_mode": "A_MINOR",
    "score_seal": "MSCORE-7724",
    "notes": [f"{p}{o}" for _, p, o, _ in MELODY_MEASURES],
    "durations": [d for _, _, _, d in MELODY_MEASURES],
}


def make_nle_seal(crop_px: int, visited_all: bool) -> str:
    ok = (abs(crop_px - WATERMARK_CROP_TOP_PX) <= 8 and visited_all)
    raw = f"{NLE_SALT}:{ok}"
    return "NLE-CERT-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10].upper() if ok else "INCOMPLETE_SCRUB_OR_CROP"


CUTFORGE_QT_SOURCE = f"""import hashlib, json, math, os, sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QShortcut
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt

SALT = {json.dumps(NLE_SALT)}
KFS = {json.dumps(HAZARD_KEYFRAMES)}

class NleCanvas(QWidget):
    def __init__(self, on_chg):
        super().__init__()
        self.setMinimumSize(780, 470)
        self.kf_idx = 0
        self.seen = {{0}}
        self.crop_px = 20  # Must drag yellow crop bar to 84px!
        self.dragging = False
        self.on_chg = on_chg

    def mousePressEvent(self, ev):
        sy = 40 + int(self.crop_px * 1.5)
        if abs(ev.pos().y() - sy) <= 22:
            self.dragging = True

    def mouseMoveEvent(self, ev):
        if not self.dragging:
            return
        self.crop_px = max(0, min(140, int(round((ev.pos().y() - 40) / 1.5))))
        self.on_chg()
        self.update()

    def mouseReleaseEvent(self, _ev):
        self.dragging = False

    def paintEvent(self, _ev):
        # Drawn purely via QPainter (AT-SPI opaque!)
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(15, 23, 42))
        # Top AI Watermark Band (84px -> drawn height 84*1.5 = 126px from y=40)
        qp.fillRect(40, 40, 700, 126, QColor(185, 28, 28))
        qp.setPen(QColor(254, 226, 226))
        qp.setFont(QFont("Monospace", 11, QFont.Bold))
        qp.drawText(55, 95, "AI_PROMO_WATERMARK_BAND: TOP 84 PX (1280x804 -> CROP TOP 84 -> 1280x720)")

        # Draggable Yellow Crop Handle Line
        cy = 40 + int(self.crop_px * 1.5)
        qp.setPen(QPen(QColor(250, 204, 21), 4))
        qp.drawLine(35, cy, 745, cy)
        qp.setBrush(QBrush(QColor(250, 204, 21)))
        qp.drawRect(340, cy - 10, 130, 20)
        qp.setPen(QColor(15, 23, 42))
        qp.drawText(348, cy + 5, f"CROP={{self.crop_px}}px")

        # Active Keyframe Hazard Box (post-crop coordinates!)
        idx, fno, tsec, hx, hy, hw, hh = KFS[self.kf_idx]
        qp.fillRect(40, 175, 700, 250, QColor(30, 41, 59))
        bx = 60 + int(hx * 0.52)
        by = 185 + int(hy * 0.52)
        qp.setPen(QPen(QColor(52, 211, 153), 3, Qt.DashLine))
        qp.setBrush(QBrush(QColor(16, 185, 129, 60)))
        qp.drawRect(bx, by, 120, 75)
        qp.setPen(QColor(248, 250, 252))
        qp.setFont(QFont("Monospace", 11, QFont.Bold))
        qp.drawText(55, 210, f"KEYFRAME #{{idx}} (Press 1/2/3): frame={{fno}} (t={{tsec:.1f}}s, window=[{{tsec-0.2:.1f}}s..{{tsec+0.2:.1f}}s])")
        qp.drawText(55, 238, f"HAZARD_MASK_POST_CROP_RECT: x={{hx}}, y={{hy}}, w={{hw}}, h={{hh}} (fill solid #0F172A)")
        qp.drawText(55, 410, f"Scrubbed Keyframes: {{sorted(x+1 for x in self.seen)}} / [1, 2, 3]")

class CutForgeWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CutForge NLE Studio")
        self.resize(840, 600)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        tbar = QHBoxLayout()
        for i in range(3):
            b = QPushButton(f"Jump KF {{i+1}} [Key {{i+1}}]")
            b.clicked.connect(lambda _=False, k=i: self.set_kf(k))
            tbar.addWidget(b)
        b_exp = QPushButton("&Export EDL Render Ticket (/home/user/Downloads/nle_ticket.json) [Ctrl+E]")
        b_exp.clicked.connect(self.export_ticket)
        tbar.addWidget(b_exp)
        lay.addLayout(tbar)
        self.cv = NleCanvas(self.upd)
        lay.addWidget(self.cv)
        self.st_lbl = QLabel("Drag yellow CROP handle to watermark boundary & scrub KF 1..3 (Keys 1, 2, 3).")
        lay.addWidget(self.st_lbl)
        self.setCentralWidget(cw)
        for i, kn in enumerate(("1", "2", "3")):
            QShortcut(QKeySequence(kn), self, activated=lambda k=i: self.set_kf(k))
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_ticket)

    def set_kf(self, k):
        self.cv.kf_idx = k
        self.cv.seen.add(k)
        self.cv.update()
        self.upd()

    def upd(self):
        self.st_lbl.setText(f"Active KF={{self.cv.kf_idx+1}} | Seen={{len(self.cv.seen)}}/3")

    def export_ticket(self):
        ok = (abs(self.cv.crop_px - {WATERMARK_CROP_TOP_PX}) <= 8 and len(self.cv.seen) == 3)
        sig = hashlib.sha256(f"{{SALT}}:{{ok}}".encode()).hexdigest()[:10].upper()
        seal = f"NLE-CERT-{{sig}}" if ok else "INCOMPLETE_SCRUB_OR_CROP"
        p = Path("/home/user/Downloads/nle_ticket.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({{"crop_top_px": self.cv.crop_px, "scrubbed_all_3": len(self.cv.seen)==3, "nle_cert_seal": seal}}, indent=2) + "\\n")
        os.chmod(p, 0o644)
        self.st_lbl.setText(f"Saved ticket (seal={{seal}})")

app = QApplication(sys.argv)
app.setApplicationName("cutforge-nle")
w = CutForgeWin()
w.show()
sys.exit(app.exec_())
"""

SCORECANVAS_QT_SOURCE = f"""import json, sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QShortcut
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QKeySequence
from PyQt5.QtCore import Qt, QPointF

MEAS = {json.dumps(MELODY_MEASURES)}
OR = {json.dumps(SCORE_ORACLE)}
# Treble staff y offsets from bottom line E4 (y=260, step=14px per diatonic step)
STEP_MAP = {{("E",4):0, ("F",4):1, ("G",4):2, ("A",4):3, ("B",4):4, ("C",5):5, ("D",5):6, ("E",5):7}}

class StaffCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(820, 430)
        self.sel = 0
        self.show_meta = False

    def paintEvent(self, _ev):
        # Drawn purely via QPainter (AT-SPI opaque!)
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(250, 250, 249))
        qp.setPen(QColor(15, 23, 42))
        qp.setFont(QFont("Monospace", 12, QFont.Bold))
        qp.drawText(35, 36, "TREBLE STAFF TRANSCRIPTION TARGET (Keys 1..8 inspect bar, F7 toggles Tempo/Seal)")
        if self.show_meta:
            qp.setPen(QColor(6, 95, 70))
            qp.drawText(35, 66, f"TEMPO_BPM={{OR['tempo_bpm']}} | TIME={{OR['time_signature']}} | KEY={{OR['key_mode']}} | SEAL={{OR['score_seal']}}")

        # 5 treble staff lines: E4(260), G4(232), B4(204), D5(176), F5(148)
        qp.setPen(QPen(QColor(51, 65, 85), 2))
        for i in range(5):
            ly = 260 - i * 28
            qp.drawLine(40, ly, 780, ly)

        for idx, (m_no, step, octv, dur) in enumerate(MEAS):
            nx = 85 + idx * 88
            st_idx = STEP_MAP[(step, octv)]
            ny = 260 - st_idx * 14
            if idx == self.sel:
                qp.fillRect(nx - 28, 115, 56, 190, QColor(59, 130, 246, 38))
            filled = dur == "quarter"
            qp.setPen(QPen(QColor(15, 23, 42), 2))
            qp.setBrush(QBrush(QColor(15, 23, 42) if filled else QColor(250, 250, 249)))
            qp.drawEllipse(QPointF(nx, ny), 11.0, 8.5)
            if dur != "whole":
                qp.drawLine(nx + 10, ny, nx + 10, ny - 46)
            qp.setFont(QFont("Monospace", 9, QFont.Bold))
            qp.drawText(nx - 22, 325, f"M{{m_no}}")
            if idx == self.sel:
                qp.setPen(QColor(29, 78, 216))
                qp.drawText(35, 375, f"INSPECTING BAR M{{m_no}}: pitch={{step}}{{octv}} | duration={{dur}}")

class ScoreCanvasWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScoreCanvas Studio")
        self.resize(860, 560)
        cw = QWidget()
        lay = QVBoxLayout(cw)
        tbar = QHBoxLayout()
        b_prev = QPushButton("Prev Bar")
        b_next = QPushButton("Next Bar [Space]")
        b_meta = QPushButton("Toggle Score Header [F7]")
        b_prev.clicked.connect(lambda: self.step(-1))
        b_next.clicked.connect(lambda: self.step(1))
        b_meta.clicked.connect(self.tog_meta)
        for b in (b_prev, b_next, b_meta):
            tbar.addWidget(b)
        lay.addLayout(tbar)
        self.cv = StaffCanvas()
        lay.addWidget(self.cv)
        self.setCentralWidget(cw)
        for i in range(8):
            QShortcut(QKeySequence(str(i + 1)), self, activated=lambda k=i: self.jump(k))
        QShortcut(QKeySequence("Space"), self, activated=lambda: self.step(1))
        QShortcut(QKeySequence("F7"), self, activated=self.tog_meta)

    def jump(self, k):
        self.cv.sel = k
        self.cv.update()

    def step(self, d):
        self.cv.sel = (self.cv.sel + d) % 8
        self.cv.update()

    def tog_meta(self):
        self.cv.show_meta = not self.cv.show_meta
        self.cv.update()

app = QApplication(sys.argv)
app.setApplicationName("scorecanvas-studio")
w = ScoreCanvasWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Video Watermark Crop & Hazard Motion-Masking Work Order — {b}video_timeline_editor{b}",
        "",
        "## Scope & Deliverables",
        f"Inspect the edit specifications on the **CutForge NLE Studio** timeline canvas and render the remediated video from {b}/workspace/raw_clip.mp4{b}.",
        "",
        "Deliverables:",
        f"1. **CutForge NLE Scrub & Signed Render Ticket ({b}/workspace/EDL_MANIFEST.json{b})**:",
        "   - In **CutForge NLE Studio**, drag the yellow `CROP` handle to the exact top watermark boundary shown on the preview canvas, scrub through all 3 hazard keyframes (`1`, `2`, `3`), and export `/home/user/Downloads/nle_ticket.json` (`Ctrl+E`).",
        f"   - Write {b}/workspace/EDL_MANIFEST.json{b} with exact keys: {b}\"crop_top_px\"{b} (int), {b}\"output_resolution\"{b} (`\"1280x720\"`), {b}\"nle_cert_seal\"{b} (`NLE-CERT-...`), and {b}\"hazard_masks\"{b} (list of 3 objects `{{\"kf\": 1..3, \"t_sec\": float, \"x\": int, \"y\": int, \"w\": int, \"h\": int}}` in post-crop coordinates).",
        f"2. **Remediated MP4 Render ({b}/workspace/promo_clean.mp4{b})**:",
        f"   - Process {b}/workspace/raw_clip.mp4{b} (`1280x804`, `6.0s`, `24fps`) by cropping off the top watermark band (`1280x720`) and masking each of the 3 bright-magenta hazard boxes during its time window (`[t_sec-0.2, t_sec+0.2]`) with solid dark `#0F172A`.",
        "",
    ])

    role_b = "\n".join([
        f"# Treble-Staff Score Transcription & Viewer Recreation Work Order — {b}score_transcriber_dev{b}",
        "",
        "## Scope & Deliverables",
        f"Transcribe all 8 measures rendered on the **ScoreCanvas Studio** musical staff canvas and build a standalone MusicXML + GUI score viewer in {b}/workspace{b}.",
        "",
        "Deliverables:",
        f"1. **MusicXML Transcription ({b}/workspace/score_complete.musicxml{b})**:",
        "   - Inspect Bars `M1..M8` (`1..8` / `Space`) and the score header (`F7`) on the **ScoreCanvas Studio** canvas.",
        f"   - Write valid XML {b}/workspace/score_complete.musicxml{b} containing `<score-partwise>` with 8 `<measure number=\"1\">..<measure number=\"8\">` elements, `<pitch><step>...</step><octave>...</octave></pitch>`, and `<type>...</type>` (`quarter`, `half`, `whole`) matching all 8 bars.",
        f"2. **Score Metadata Manifest ({b}/workspace/SCORE_METADATA.json{b})**:",
        f"   - Exact keys: {b}\"tempo_bpm\"{b} (int), {b}\"time_signature\"{b} (string), {b}\"key_mode\"{b} (string), {b}\"score_seal\"{b} (string), {b}\"notes\"{b} (8-item list like `[\"E4\", ...]`), {b}\"durations\"{b} (8-item list).",
        f"3. **Standalone ScoreCanvas Viewer ({b}/workspace/recreation/run_app.sh{b})**:",
        f"   - Executable launcher opening a GUI window titled {b}ScoreCanvas Viewer{b} (`>= 680 x 420` px) displaying the 8 transcribed notes, tempo, and `score_seal`, AND supporting `--dump-json` CLI mode printing `{{\"notes\": [...], \"tempo_bpm\": ...}}` to stdout.",
        "",
    ])
    return {"video_timeline_editor": role_a, "score_transcriber_dev": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["video_timeline_editor"]
    ws_b = workspace_map["score_transcriber_dev"]
    ws_a.mkdir(parents=True, exist_ok=True)
    (ws_b / "recreation").mkdir(parents=True, exist_ok=True)

    # Generate deterministic 6.0s 24fps 1280x804 MP4 with red top 84px watermark + 3 bright magenta hazard boxes!
    vf = (
        "drawbox=x=0:y=0:w=1280:h=84:color=0xDC2626:t=fill,"
        "drawbox=enable='between(t,0.85,1.15)':x=260:y=264:w=160:h=120:color=0xFF00FF:t=fill,"
        "drawbox=enable='between(t,2.85,3.15)':x=560:y=304:w=160:h=120:color=0xFF00FF:t=fill,"
        "drawbox=enable='between(t,4.85,5.15)':x=860:y=274:w=160:h=120:color=0xFF00FF:t=fill"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1E293B:s=1280x804:r=24:d=6.0",
            "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            str(ws_a / "raw_clip.mp4"),
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    stage_private_studio_script(state_dir, "cutforge_ref.py", CUTFORGE_QT_SOURCE)
    stage_private_studio_script(state_dir, "scorecanvas_ref.py", SCORECANVAS_QT_SOURCE)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None: return
        def do_GET(self) -> None:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text('{"mode":"rbs2_01"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    boot_isolated_studio_scripts(state_dir, ["cutforge_ref.py", "scorecanvas_ref.py"], wait_s=2.4)


def _sample_video_rgb(mp4_path: Path, t_sec: float, x: int, y: int) -> tuple[int, int, int] | None:
    from PIL import Image
    import io
    cp = subprocess.run(
        ["ffmpeg", "-ss", f"{t_sec:.2f}", "-i", str(mp4_path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, timeout=15,
    )
    if cp.returncode != 0 or len(cp.stdout) < 500:
        return None
    with Image.open(io.BytesIO(cp.stdout)) as im:
        rgb = im.convert("RGB")
        if x >= rgb.size[0] or y >= rgb.size[1]:
            return None
        return rgb.getpixel((x, y))


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["video_timeline_editor"]
    ws_b = workspace_map["score_transcriber_dev"]

    edl = read_json_safe(ws_a / "EDL_MANIFEST.json")
    mp4 = ws_a / "promo_clean.mp4"
    vid_w, vid_h, vid_dur = 0, 0, 0.0
    if mp4.is_file():
        cp = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration", "-of", "json", str(mp4)],
            capture_output=True, text=True, timeout=15,
        )
        if cp.returncode == 0:
            st = ((json.loads(cp.stdout).get("streams") or [{}])[0])
            vid_w = int(st.get("width") or 0)
            vid_h = int(st.get("height") or 0)
            vid_dur = float(st.get("duration") or 0.0)

    top_px = _sample_video_rgb(mp4, 0.5, 640, 20) if vid_w == 1280 and vid_h == 720 else None
    no_red_wm = bool(top_px is not None and not (top_px[0] > 170 and top_px[1] < 80))
    kf_masked = []
    for _idx, _fno, t_s, hx, hy, hw, hh in HAZARD_KEYFRAMES:
        px = _sample_video_rgb(mp4, t_s, hx + hw // 2, hy + hh // 2) if vid_w == 1280 and vid_h == 720 else None
        # Magenta (255,0,255) must be gone and replaced by dark slate (<45, <55, <75)
        kf_masked.append(bool(px is not None and px[0] < 55 and px[1] < 65 and px[2] < 85))
    bg_intact = False
    bg_px = _sample_video_rgb(mp4, 2.0, 100, 600) if vid_w == 1280 and vid_h == 720 else None
    if bg_px is not None:
        bg_intact = (15 <= bg_px[0] <= 55 and 25 <= bg_px[1] <= 65)

    exp_seal = make_nle_seal(84, True)
    masks = edl.get("hazard_masks") if isinstance(edl.get("hazard_masks"), list) else []
    m_hits = 0
    for i, (_k, _f, ts, hx, hy, hw, hh) in enumerate(HAZARD_KEYFRAMES):
        if i < len(masks) and isinstance(masks[i], dict):
            mi = masks[i]
            if abs(float(mi.get("t_sec", -9)) - ts) <= 0.15 and abs(int(mi.get("x", -99)) - hx) <= 10 and abs(int(mi.get("y", -99)) - hy) <= 10:
                m_hits += 1

    # 19 subchecks for Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_edl_exists", bool(edl), 0.04, "Missing EDL_MANIFEST.json"),
        ("a_crop_84", isinstance(edl.get("crop_top_px"), (int, float)) and abs(float(edl["crop_top_px"]) - 84) <= 8, 0.06, "EDL crop_top_px != 84"),
        ("a_res_str", edl.get("output_resolution") == "1280x720", 0.04, "EDL output_resolution != 1280x720"),
        ("a_nle_seal", edl.get("nle_cert_seal") == exp_seal, 0.08, "EDL nle_cert_seal invalid"),
        ("a_masks_len", len(masks) == 3, 0.04, "EDL hazard_masks length != 3"),
        ("a_mask_kf1", m_hits >= 1, 0.05, "EDL KF1 coordinates inaccurate"),
        ("a_mask_kf2", m_hits >= 2, 0.05, "EDL KF2 coordinates inaccurate"),
        ("a_mask_kf3", m_hits == 3, 0.06, "EDL KF3 coordinates inaccurate"),
        ("a_mp4_exists", mp4.is_file(), 0.05, "Missing promo_clean.mp4"),
        ("a_mp4_width", vid_w == 1280, 0.05, f"MP4 width={vid_w} != 1280"),
        ("a_mp4_height", vid_h == 720, 0.06, f"MP4 height={vid_h} != 720 (top watermark crop)"),
        ("a_mp4_duration", 5.5 <= vid_dur <= 6.5, 0.05, f"MP4 duration={vid_dur}s outside [5.5, 6.5]"),
        ("a_wm_removed", no_red_wm, 0.07, "Red top watermark still visible in promo_clean.mp4"),
        ("a_kf1_masked", kf_masked[0], 0.07, "Frame 24 (t=1.0s) magenta hazard not masked"),
        ("a_kf2_masked", kf_masked[1], 0.07, "Frame 72 (t=3.0s) magenta hazard not masked"),
        ("a_kf3_masked", kf_masked[2], 0.07, "Frame 120 (t=5.0s) magenta hazard not masked"),
        ("a_bg_preserved", bg_intact, 0.04, "Video background blanked or corrupted"),
        ("a_mask_wh_160x120", all(isinstance(m, dict) and int(m.get("w", 0)) == 160 and int(m.get("h", 0)) == 120 for m in masks) if len(masks) == 3 else False, 0.03, "EDL w/h != 160x120"),
        ("a_raw_preserved", (ws_a / "raw_clip.mp4").is_file(), 0.02, "raw_clip.mp4 deleted"),
    ]

    meta_b = read_json_safe(ws_b / "SCORE_METADATA.json")
    mxml_p = ws_b / "score_complete.musicxml"
    parsed_notes: list[str] = []
    parsed_durs: list[str] = []
    xml_valid = False
    if mxml_p.is_file():
        try:
            root = ET.parse(mxml_p).getroot()
            xml_valid = "score-partwise" in root.tag
            for meas in root.findall(".//measure"):
                st_el = meas.find(".//pitch/step")
                oc_el = meas.find(".//pitch/octave")
                ty_el = meas.find(".//type")
                if st_el is not None and oc_el is not None:
                    parsed_notes.append(f"{(st_el.text or '').strip()}{(oc_el.text or '').strip()}")
                if ty_el is not None:
                    parsed_durs.append((ty_el.text or "").strip().lower())
        except Exception:
            xml_valid = False

    note_matches = sum(1 for i, n in enumerate(SCORE_ORACLE["notes"]) if i < len(parsed_notes) and parsed_notes[i] == n)
    dur_matches = sum(1 for i, d in enumerate(SCORE_ORACLE["durations"]) if i < len(parsed_durs) and parsed_durs[i] == d)

    run_sh = ws_b / "recreation/run_app.sh"
    cli_b = run_cli_probe_json(run_sh, ["--dump-json"])
    gui_b = evaluate_recreated_gui_app(run_sh, disp_num=116, expected_title_sub="ScoreCanvas")
    ax_b = gui_b["initial_ax_text"]

    # 19 subchecks for Role B (19 + 19 = 38 total subchecks!)
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_xml_exists", mxml_p.is_file() and xml_valid, 0.06, "Missing or invalid score_complete.musicxml"),
        ("b_xml_8bars", len(parsed_notes) == 8, 0.05, f"MusicXML measure pitch count={len(parsed_notes)} != 8"),
        ("b_xml_notes_4", note_matches >= 4, 0.05, f"MusicXML pitches {note_matches}/8"),
        ("b_xml_notes_6", note_matches >= 6, 0.06, f"MusicXML pitches {note_matches}/8"),
        ("b_xml_notes_all8", note_matches == 8, 0.08, f"MusicXML pitches {note_matches}/8 != 8/8"),
        ("b_xml_durs_6", dur_matches >= 6, 0.05, f"MusicXML durations {dur_matches}/8"),
        ("b_xml_durs_all8", dur_matches == 8, 0.06, f"MusicXML durations {dur_matches}/8 != 8/8"),
        ("b_meta_bpm", meta_b.get("tempo_bpm") == 108, 0.05, "SCORE_METADATA tempo_bpm != 108"),
        ("b_meta_tsig", meta_b.get("time_signature") == "4/4", 0.04, "SCORE_METADATA time_signature != '4/4'"),
        ("b_meta_key", meta_b.get("key_mode") == "A_MINOR", 0.05, "SCORE_METADATA key_mode != 'A_MINOR'"),
        ("b_meta_seal", meta_b.get("score_seal") == "MSCORE-7724", 0.08, "SCORE_METADATA score_seal != 'MSCORE-7724' (F7 header)"),
        ("b_meta_notes", meta_b.get("notes") == SCORE_ORACLE["notes"], 0.06, "SCORE_METADATA notes mismatch"),
        ("b_meta_durs", meta_b.get("durations") == SCORE_ORACLE["durations"], 0.05, "SCORE_METADATA durations mismatch"),
        ("b_app_exists", gui_b["script_exists"], 0.04, "Missing /workspace/recreation/run_app.sh"),
        ("b_app_mapped", gui_b["window_mapped"] and "scorecanvas" in gui_b["window_title"].lower(), 0.06, "ScoreCanvas Viewer window not mapped"),
        ("b_app_visual", gui_b["visual_nonblank"] and gui_b["win_w"] >= 620, 0.05, "ScoreCanvas Viewer visual check failed"),
        ("b_app_ax_seal", "MSCORE-7724" in ax_b and "108" in ax_b, 0.04, "ScoreCanvas Viewer AT-SPI missing seal/tempo"),
        ("b_cli_dump_notes", cli_b.get("notes") == SCORE_ORACLE["notes"], 0.04, "run_app.sh --dump-json notes mismatch"),
        ("b_cli_dump_bpm", cli_b.get("tempo_bpm") == 108, 0.03, "run_app.sh --dump-json tempo_bpm != 108"),
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
    assert role in ("video_timeline_editor", "score_transcriber_dev")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "video_timeline_editor":
            # Drag yellow CROP bar from 20px -> 84px (dy = +96px), press 1, 2, 3, Ctrl+E
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'CutForge NLE Studio' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,40,50,840,600; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.3; "
                "python3 - <<'PY'\n"
                "import io, subprocess\n"
                "from PIL import Image\n"
                "raw = subprocess.check_output(['import', '-window', 'root', 'png:-'])\n"
                "im = Image.open(io.BytesIO(raw)).convert('RGB')\n"
                "yel = [(x, y) for x in range(320, 520, 2) for y in range(80, 260, 2) if im.getpixel((x,y))[0]>225 and 185<=im.getpixel((x,y))[1]<=220 and im.getpixel((x,y))[2]<55]\n"
                "cx = sum(p[0] for p in yel)//len(yel); cy = sum(p[1] for p in yel)//len(yel)\n"
                "subprocess.run(['xdotool', 'mousemove', str(cx), str(cy), 'mousedown', '1'], check=True)\n"
                "for k in range(1, 9):\n"
                "    subprocess.run(['xdotool', 'mousemove', str(cx), str(cy + int(96*k/8))], check=True)\n"
                "subprocess.run(['xdotool', 'mouseup', '1'], check=True)\n"
                "PY\n"
                "sleep 0.2; wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.15; "
                "for k in 1 2 3; do xdotool key --clearmodifiers $k; sleep 0.12; done; "
                "xdotool key --clearmodifiers ctrl+e; sleep 0.35"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=25)
            tk = read_json_safe(Path("/home/user/Downloads/nle_ticket.json"))
            write_json(
                ws / "EDL_MANIFEST.json",
                {
                    "crop_top_px": 84,
                    "output_resolution": "1280x720",
                    "nle_cert_seal": tk["nle_cert_seal"],
                    "hazard_masks": [
                        {"kf": k, "t_sec": ts, "x": hx, "y": hy, "w": hw, "h": hh}
                        for k, _f, ts, hx, hy, hw, hh in HAZARD_KEYFRAMES
                    ],
                },
            )
            vf = (
                "crop=1280:720:0:84,"
                "drawbox=enable='between(t,0.8,1.2)':x=260:y=180:w=160:h=120:color=0x0F172A:t=fill,"
                "drawbox=enable='between(t,2.8,3.2)':x=560:y=220:w=160:h=120:color=0x0F172A:t=fill,"
                "drawbox=enable='between(t,4.8,5.2)':x=860:y=190:w=160:h=120:color=0x0F172A:t=fill"
            )
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(ws / "raw_clip.mp4"), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(ws / "promo_clean.mp4")],
                check=True, capture_output=True, timeout=45,
            )
        else:
            rec = ws / "recreation"
            rec.mkdir(parents=True, exist_ok=True)
            write_json(ws / "SCORE_METADATA.json", SCORE_ORACLE)
            meas_xml = []
            for m_no, st_p, oc_p, dur in MELODY_MEASURES:
                meas_xml.append(
                    f'    <measure number="{m_no}"><note><pitch><step>{st_p}</step><octave>{oc_p}</octave></pitch><duration>1</duration><type>{dur}</type></note></measure>'
                )
            (ws / "score_complete.musicxml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n<score-partwise version="3.1">\n  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>\n  <part id="P1">\n'
                + "\n".join(meas_xml)
                + "\n  </part>\n</score-partwise>\n",
                encoding="utf-8",
            )
            app_py = (
                "import json, sys\n"
                f"OR = {repr(SCORE_ORACLE)}\n"
                "if '--dump-json' in sys.argv:\n"
                "    print(json.dumps({'notes': OR['notes'], 'tempo_bpm': OR['tempo_bpm']}))\n"
                "    sys.exit(0)\n"
                "from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton\n"
                "app = QApplication(sys.argv); w = QMainWindow(); w.setWindowTitle('ScoreCanvas Viewer'); w.resize(700, 440)\n"
                "cw = QWidget(); cw.setStyleSheet('background:#0f172a;color:#f8fafc;'); v = QVBoxLayout(cw)\n"
                "l1 = QLabel('Notes: ' + ' '.join(OR['notes'])); l1.setStyleSheet('background:#1e293b;color:#38bdf8;padding:8px;')\n"
                "l2 = QLabel('Tempo: ' + str(OR['tempo_bpm']) + ' BPM | Seal: ' + OR['score_seal']); l2.setStyleSheet('background:#065f46;color:#ecfdf5;padding:8px;')\n"
                "b1 = QPushButton('Play Melody'); b1.setStyleSheet('background:#2563eb;color:#fff;padding:8px;')\n"
                "v.addWidget(l1); v.addWidget(l2); v.addWidget(b1); w.setCentralWidget(cw); w.show(); sys.exit(app.exec_())\n"
            )
            (rec / "viewer.py").write_text(app_py, encoding="utf-8")
            sh = rec / "run_app.sh"
            sh.write_text("#!/usr/bin/env bash\nexec python3 \"$(dirname \"$0\")/viewer.py\" \"$@\"\n", encoding="utf-8")
            os.chmod(sh, 0o755)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_1 + LAW_7): Single-key `1..3` misrouted into ScoreCanvas leaves CutForge KF3 unscrubbed."""
    solve_role("video_timeline_editor", workspace_map, port, careful_conc=False)
    solve_role("score_transcriber_dev", workspace_map, port, careful_conc=False)
    ws_a = workspace_map["video_timeline_editor"]
    bad = read_json_safe(ws_a / "EDL_MANIFEST.json")
    bad["nle_cert_seal"] = "INCOMPLETE_SCRUB_OR_CROP"
    bad["hazard_masks"] = bad["hazard_masks"][:2]
    write_json(ws_a / "EDL_MANIFEST.json", bad)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

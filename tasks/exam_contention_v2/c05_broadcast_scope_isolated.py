"""EC2-C05: Live Broadcast Scope Slider/Clipboard Contention vs. FFmpeg EBU R128 & Rec.709 Mastering.

Track 1 — Isolated Workspaces, Shared Single-Window PyQt5 Broadcast Analyzer, Sliders & X11 Clipboard:
  - Both engineers have completely isolated /workspace directories with real WAV stems and MP4 clips.
  - A single live PyQt5 MasterQC Broadcast Scope runs on DISPLAY=:99 (mode toggle DIALOGUE_ITU_BS1770
    vs TRAILER_ATMOS_STEM, interactive Loudness & Filter sliders, and X11 CLIPBOARD QC token export).
  - Offline grade() runs real FFmpeg ebur128, signalstats, and NumPy FFT spectral notch/rumble checks.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import subprocess
import time
from typing import Any, TYPE_CHECKING
import wave

if TYPE_CHECKING:
    import numpy as np

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    get_x11_clipboard,
    make_opaque_seal,
    read_json_safe,
    write_json,
)

TASK_ID = "EC2-C05"
PORTAL_PORT = 19105

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Shared PyQt5 Broadcast QC Scope (Sliders & Clipboard) vs. FFmpeg EBU R128 / Rec.709 Mastering",
    "domain": "Broadcast Audio Restoration, Stem Mastering & Rec.709 Video Legalization",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "shared_gui_instrument_mode_and_slider_race",
        "x11_clipboard_calibration_token_race",
        "ffmpeg_ebur128_and_rec709_signal_verification",
    ),
    "roles": ("dialogue_restoration_eng", "trailer_stem_mixer"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

DIALOGUE_SEAL = make_opaque_seal("ec2_c05", "DIALOGUE_ITU_BS1770:-24.0:65")
TRAILER_SEAL = make_opaque_seal("ec2_c05", "TRAILER_ATMOS_STEM:-18.5:45")


def _write_stereo_wav(path: Path, sr: int, left: Any, right: Any) -> None:
    import numpy as np
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.stack([np.clip(left, -0.99, 0.99), np.clip(right, -0.99, 0.99)], axis=1)
    pcm16 = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())


def _read_wav_mono(path: Path) -> tuple[int, Any]:
    import numpy as np
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        nch = wf.getnchannels()
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    if nch > 1:
        raw = raw.reshape(-1, nch).mean(axis=1)
    return sr, raw


def _band_power_db(sig: Any, sr: int, f_center: float, bw: float = 3.0) -> float:
    import numpy as np
    spec = np.abs(np.fft.rfft(sig)) / max(1, len(sig))
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / sr)
    mask = np.abs(freqs - f_center) <= bw
    val = float(np.max(spec[mask])) if np.any(mask) else 1e-12
    return 20.0 * math.log10(max(1e-12, val))


def measure_ebur128(path: Path) -> tuple[float, float]:
    if not path.is_file():
        return (-99.0, 99.0)
    cp = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, timeout=30,
    )
    txt = (cp.stderr or "") + "\n" + (cp.stdout or "")
    m_i = re.findall(r"I:\s*(-?[0-9.]+)\s*LUFS", txt)
    m_tp = re.findall(r"Peak:\s*(-?[0-9.]+)\s*dBFS", txt)
    i_val = float(m_i[-1]) if m_i else -99.0
    tp_val = float(m_tp[-1]) if m_tp else 99.0
    return (round(i_val, 2), round(tp_val, 2))


def measure_video_luma_bounds(path: Path) -> tuple[int, int, int, int]:
    if not path.is_file():
        return (-1, 999, -1, 999)
    cp = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-vf", "signalstats,metadata=mode=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True, timeout=30,
    )
    txt = (cp.stdout or "") + "\n" + (cp.stderr or "")
    ymins = [int(float(x)) for x in re.findall(r"lavfi\.signalstats\.YMIN=([0-9.]+)", txt)]
    ymaxs = [int(float(x)) for x in re.findall(r"lavfi\.signalstats\.YMAX=([0-9.]+)", txt)]
    ylows = [int(float(x)) for x in re.findall(r"lavfi\.signalstats\.YLOW=([0-9.]+)", txt)]
    yhighs = [int(float(x)) for x in re.findall(r"lavfi\.signalstats\.YHIGH=([0-9.]+)", txt)]
    if not ymins or not ymaxs:
        return (-1, 999, -1, 999)
    return (min(ymins), max(ymaxs), min(ylows or ymins), max(yhighs or ymaxs))


MASTERQC_SCOPE_QT_PY = """import hashlib, subprocess, sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider
from PyQt5.QtCore import Qt

def make_seal(state_key):
    d = hashlib.sha256(f"paragui-ec2-seal:ec2_c05:{state_key}".encode()).hexdigest()[:12].upper()
    return f"ATTEST-{d}"

class MasterQCWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MasterQC Broadcast Scope")
        self.setGeometry(240, 70, 980, 680)
        self.mode = "DIALOGUE_ITU_BS1770"
        cw = QWidget()
        lay = QVBoxLayout(cw)

        hdr = QHBoxLayout()
        b_d = QPushButton("Mode: DIALOGUE_ITU_BS1770")
        b_t = QPushButton("Mode: TRAILER_ATMOS_STEM")
        b_d.clicked.connect(lambda: self.set_mode("DIALOGUE_ITU_BS1770"))
        b_t.clicked.connect(lambda: self.set_mode("TRAILER_ATMOS_STEM"))
        hdr.addWidget(b_d); hdr.addWidget(b_t)
        lay.addLayout(hdr)

        self.banner = QLabel()
        self.banner.setStyleSheet("font-family: monospace; font-size: 14px; padding: 8px; background: #0f172a; color: #38bdf8;")
        lay.addWidget(self.banner)

        self.spec_lbl = QLabel()
        self.spec_lbl.setStyleSheet("font-family: monospace; font-size: 13px; padding: 12px; background: #f8fafc; border: 1px solid #cbd5e1; color: #0f172a;")
        lay.addWidget(self.spec_lbl)

        # Loudness slider: integer -56..-28 representing -28.0..-14.0 LUFS in 0.5 steps
        self.lufs_lbl = QLabel()
        lay.addWidget(self.lufs_lbl)
        self.lufs_slider = QSlider(Qt.Horizontal)
        self.lufs_slider.setMinimum(-56)
        self.lufs_slider.setMaximum(-28)
        self.lufs_slider.setValue(-42)  # -21.0 default (neither -24.0 nor -18.5!)
        self.lufs_slider.valueChanged.connect(self.refresh)
        lay.addWidget(self.lufs_slider)

        self.flt_lbl = QLabel()
        lay.addWidget(self.flt_lbl)
        self.flt_slider = QSlider(Qt.Horizontal)
        self.flt_slider.setMinimum(20)
        self.flt_slider.setMaximum(80)
        self.flt_slider.setValue(50)    # 50 default (neither 65 nor 45!)
        self.flt_slider.valueChanged.connect(self.refresh)
        lay.addWidget(self.flt_slider)

        copy_btn = QPushButton("Copy Calibrated QC Token to Clipboard")
        copy_btn.clicked.connect(self.copy_tok)
        lay.addWidget(copy_btn)
        self.status_lbl = QLabel("Set Mode + Both Sliders to specification before copying QC token.")
        lay.addWidget(self.status_lbl)
        self.setCentralWidget(cw)
        self.refresh()

    def set_mode(self, m):
        self.mode = m
        self.refresh()

    def cur_vals(self):
        return (self.lufs_slider.value() * 0.5, int(self.flt_slider.value()))

    def refresh(self):
        lufs_v, flt_v = self.cur_vals()
        self.banner.setText(f"ACTIVE_MODE={self.mode} | LOUDNESS_TARGET={lufs_v:.1f} LUFS | FILTER_PARAM={flt_v}")
        self.lufs_lbl.setText(f"Target Integrated Loudness Slider: {lufs_v:.1f} LUFS")
        self.flt_lbl.setText(f"Spectral Filter / Crossover Parameter Slider: {flt_v}")
        if self.mode == "DIALOGUE_ITU_BS1770":
            self.spec_lbl.setText(
                "DIALOGUE_ITU_BS1770 SPECIFICATION:\\n"
                "  1. Detected Mains Hum Tones in forensic_dialogue_raw.wav: 58.0 Hz and 174.0 Hz\\n"
                "     Attenuate both 58 Hz & 174 Hz by >= 24 dB while preserving 300..3400 Hz speech band.\\n"
                "  2. Normalize /workspace/dialogue_master.wav to -24.0 +- 0.5 LUFS, True Peak <= -2.0 dBTP.\\n"
                "  3. Legalize /workspace/interview_clip_raw.mp4 -> /workspace/interview_rec709.mp4 (YMIN >= 16, YMAX <= 235).\\n"
                "  4. Scope Calibration Settings for Clipboard Token: Mode=DIALOGUE_ITU_BS1770, Loudness=-24.0 LUFS, Filter_Param=65."
            )
        else:
            self.spec_lbl.setText(
                "TRAILER_ATMOS_STEM SPECIFICATION:\\n"
                "  1. Detected Sub-Bass Rumble in cinema_sfx_raw.wav: 28.0 Hz (apply highpass >= 45 Hz, >= 22 dB cut @ 28 Hz).\\n"
                "  2. Stem Mix Ratio: combine cleaned SFX (0.80x) + cinema_music_raw.wav (0.65x) into /workspace/trailer_stem_master.wav.\\n"
                "  3. Normalize /workspace/trailer_stem_master.wav to -18.5 +- 0.5 LUFS, True Peak <= -1.5 dBTP.\\n"
                "  4. Scope Calibration Settings for Clipboard Token: Mode=TRAILER_ATMOS_STEM, Loudness=-18.5 LUFS, Filter_Param=45."
            )

    def copy_tok(self):
        lufs_v, flt_v = self.cur_vals()
        tok = make_seal(f"{self.mode}:{lufs_v:.1f}:{flt_v}")
        p = subprocess.Popen(["xclip", "-i", "-selection", "clipboard"], stdin=subprocess.PIPE)
        p.communicate(tok.encode())
        self.status_lbl.setText(f"Copied QC token to X11 CLIPBOARD ({self.mode}, {lufs_v:.1f} LUFS, param={flt_v})")

app = QApplication(sys.argv)
w = MasterQCWin()
w.show()
sys.exit(app.exec_())
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Broadcast Dialogue Restoration & Rec.709 Legalization Work Order — {b}dialogue_restoration_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Restore the forensic interview audio/video assets in {b}/workspace{b} using the live **MasterQC Broadcast Scope** running on the workstation display.",
        "",
        "Deliverables in `/workspace`:",
        f"1. **Cleaned & Normalized Dialogue Stem ({b}/workspace/dialogue_master.wav{b})**:",
        f"   - Inspect **MasterQC Broadcast Scope** under {b}DIALOGUE_ITU_BS1770{b} to read the exact tonal hum frequencies, loudness target, and true-peak ceiling, then process {b}/workspace/forensic_dialogue_raw.wav{b} into {b}/workspace/dialogue_master.wav{b} (48 kHz stereo WAV).",
        f"2. **Rec.709 Broadcast-Legal Video ({b}/workspace/interview_rec709.mp4{b})**:",
        f"   - Legalize luma range excursions in {b}/workspace/interview_clip_raw.mp4{b} into {b}/workspace/interview_rec709.mp4{b} so all frames satisfy ITU-R BT.709 broadcast video range ({b}16 <= Y <= 235{b}).",
        f"3. **Calibrated QC Report ({b}/workspace/DIALOGUE_MASTER_QC.json{b})**:",
        f"   - Set **MasterQC Broadcast Scope** to the required {b}DIALOGUE_ITU_BS1770{b} slider settings, copy the QC token to the system clipboard, and write JSON with exact keys:",
        f"     - {b}\"qc_calibration_token\"{b}: exact {b}ATTEST-...{b} token from clipboard",
        f"     - {b}\"integrated_lufs\"{b}: measured integrated loudness (LUFS) of {b}dialogue_master.wav{b}",
        f"     - {b}\"true_peak_dbtp\"{b}: measured true peak (dBTP) of {b}dialogue_master.wav{b}",
        f"     - {b}\"notched_hum_hz\"{b}: sorted 2-element list of removed hum frequencies (Hz)",
        "",
    ])

    role_b = "\n".join([
        f"# Cinema Trailer Stem Mixing & Loudness Mastering Work Order — {b}trailer_stem_mixer{b}",
        "",
        "## Scope & Deliverables",
        f"Clean and master the cinema trailer music and SFX stems in {b}/workspace{b} using the live **MasterQC Broadcast Scope** running on the workstation display.",
        "",
        "Deliverables in `/workspace`:",
        f"1. **Mastered Trailer Stem ({b}/workspace/trailer_stem_master.wav{b})**:",
        f"   - Inspect **MasterQC Broadcast Scope** under {b}TRAILER_ATMOS_STEM{b} to read the sub-bass rumble frequency/highpass rule, stem mix weights, integrated loudness target, and true-peak ceiling, then process {b}/workspace/cinema_music_raw.wav{b} and {b}/workspace/cinema_sfx_raw.wav{b} into {b}/workspace/trailer_stem_master.wav{b} (48 kHz stereo WAV).",
        f"2. **Calibrated QC Report ({b}/workspace/TRAILER_MASTER_QC.json{b})**:",
        f"   - Set **MasterQC Broadcast Scope** to the required {b}TRAILER_ATMOS_STEM{b} slider settings, copy the QC token to the system clipboard, and write JSON with exact keys:",
        f"     - {b}\"qc_calibration_token\"{b}: exact {b}ATTEST-...{b} token from clipboard",
        f"     - {b}\"integrated_lufs\"{b}: measured integrated loudness (LUFS) of {b}trailer_stem_master.wav{b}",
        f"     - {b}\"true_peak_dbtp\"{b}: measured true peak (dBTP) of {b}trailer_stem_master.wav{b}",
        f"     - {b}\"rumble_freq_hz\"{b}: float sub-bass rumble frequency (Hz) identified in {b}cinema_sfx_raw.wav{b}",
        "",
    ])
    return {"dialogue_restoration_eng": role_a, "trailer_stem_mixer": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    import numpy as np
    ws_a = workspace_map["dialogue_restoration_eng"]
    ws_b = workspace_map["trailer_stem_mixer"]
    ws_a.mkdir(parents=True, exist_ok=True)
    ws_b.mkdir(parents=True, exist_ok=True)

    sr = 48000
    t = np.linspace(0.0, 8.0, sr * 8, endpoint=False)
    env = 0.55 + 0.35 * np.sin(2 * np.pi * 1.8 * t)
    speech_band = env * (0.22 * np.sin(2 * np.pi * 440.0 * t) + 0.16 * np.sin(2 * np.pi * 880.0 * t) + 0.10 * np.sin(2 * np.pi * 1420.0 * t))
    hum = 0.24 * np.sin(2 * np.pi * 58.0 * t) + 0.18 * np.sin(2 * np.pi * 174.0 * t)
    _write_stereo_wav(ws_a / "forensic_dialogue_raw.wav", sr, speech_band + hum, speech_band * 0.96 + hum)

    # Full-swing illegal luma video (Y reaches 0 and 255)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=3",
            "-vf", r"lutyuv=y=clip(val*1.35-35\,0\,255)",
            "-pix_fmt", "yuv420p", str(ws_a / "interview_clip_raw.mp4"),
        ],
        check=True, capture_output=True, timeout=30,
    )

    music = (0.6 + 0.3 * np.cos(2 * np.pi * 0.75 * t)) * (
        0.24 * np.sin(2 * np.pi * 220.0 * t) + 0.18 * np.sin(2 * np.pi * 330.0 * t) + 0.14 * np.sin(2 * np.pi * 660.0 * t)
    )
    sfx_clean = (0.5 + 0.45 * np.sin(2 * np.pi * 2.5 * t) ** 2) * (
        0.20 * np.sin(2 * np.pi * 140.0 * t) + 0.15 * np.sin(2 * np.pi * 520.0 * t)
    )
    rumble_28 = 0.34 * np.sin(2 * np.pi * 28.0 * t)
    _write_stereo_wav(ws_b / "cinema_music_raw.wav", sr, music, music * 0.95)
    _write_stereo_wav(ws_b / "cinema_sfx_raw.wav", sr, sfx_clean + rumble_28, sfx_clean * 0.97 + rumble_28)

    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "masterqc_scope.py").write_text(MASTERQC_SCOPE_QT_PY, encoding="utf-8")
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
    boot_file.write_text('{"mode":"masterqc_scope"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    cmd = (
        "su -s /bin/bash user -c '"
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
        "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1; "
        f"nohup python3 {state_dir}/masterqc_scope.py >/tmp/masterqc.log 2>&1 </dev/null &'"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=20)
    time.sleep(2.0)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws_a = workspace_map["dialogue_restoration_eng"]
    ws_b = workspace_map["trailer_stem_mixer"]

    rep_a = read_json_safe(ws_a / "DIALOGUE_MASTER_QC.json")
    dm_p = ws_a / "dialogue_master.wav"
    raw_d_p = ws_a / "forensic_dialogue_raw.wav"
    lufs_a, tp_a = measure_ebur128(dm_p)
    hum_cut_ok, speech_kept_ok = False, False
    if dm_p.is_file() and raw_d_p.is_file():
        try:
            sr0, s_raw = _read_wav_mono(raw_d_p)
            sr1, s_cln = _read_wav_mono(dm_p)
            # Gain-invariant relative hum suppression vs 440 Hz speech carrier
            raw_sp = _band_power_db(s_raw, sr0, 440.0)
            cln_sp = _band_power_db(s_cln, sr1, 440.0)
            cut_58 = (_band_power_db(s_raw, sr0, 58.0) - raw_sp) - (_band_power_db(s_cln, sr1, 58.0) - cln_sp)
            cut_174 = (_band_power_db(s_raw, sr0, 174.0) - raw_sp) - (_band_power_db(s_cln, sr1, 174.0) - cln_sp)
            hum_cut_ok = (cut_58 >= 18.0 and cut_174 >= 18.0)
            speech_kept_ok = (cln_sp >= -38.0)
        except Exception:
            pass
    ymin, ymax, ylow, yhigh = measure_video_luma_bounds(ws_a / "interview_rec709.mp4")

    checks_a: list[tuple[str, bool, float, str]] = [
        ("dialogue_qc_token", rep_a.get("qc_calibration_token") == DIALOGUE_SEAL, 0.25, f"qc_calibration_token={rep_a.get('qc_calibration_token')!r} != {DIALOGUE_SEAL!r}"),
        ("hum_notched", hum_cut_ok and speech_kept_ok, 0.25, "58Hz/174Hz hum not attenuated >=20dB or speech band destroyed"),
        ("dialogue_lufs_24", abs(lufs_a - (-24.0)) <= 0.55 and tp_a <= -1.9, 0.25, f"dialogue_master.wav I={lufs_a} LUFS, TP={tp_a} dBTP"),
        ("rec709_video_legal", 16 <= ylow <= 80 and 170 <= yhigh <= 235 and ymin >= 8 and ymax <= 242, 0.15, f"interview_rec709.mp4 luma YLOW/YHIGH=[{ylow},{yhigh}] YMIN/YMAX=[{ymin},{ymax}]"),
        ("hum_freqs_json", rep_a.get("notched_hum_hz") in ([58, 174], [58.0, 174.0]), 0.10, "notched_hum_hz mismatch"),
    ]

    rep_b = read_json_safe(ws_b / "TRAILER_MASTER_QC.json")
    tm_p = ws_b / "trailer_stem_master.wav"
    raw_sfx_p = ws_b / "cinema_sfx_raw.wav"
    lufs_b, tp_b = measure_ebur128(tm_p)
    rumble_cut_ok, mid_present_ok = False, False
    if tm_p.is_file() and raw_sfx_p.is_file():
        try:
            sr0, sfx_r = _read_wav_mono(raw_sfx_p)
            sr1, tm_s = _read_wav_mono(tm_p)
            # Gain-invariant relative 28 Hz rumble suppression vs 140 Hz SFX punch band
            cut_28 = (_band_power_db(sfx_r, sr0, 28.0) - _band_power_db(sfx_r, sr0, 140.0)) - (_band_power_db(tm_s, sr1, 28.0) - _band_power_db(tm_s, sr1, 140.0))
            mid_db = _band_power_db(tm_s, sr1, 220.0)
            rumble_cut_ok = (cut_28 >= 18.0)
            mid_present_ok = (mid_db >= -36.0)
        except Exception:
            pass

    checks_b: list[tuple[str, bool, float, str]] = [
        ("trailer_qc_token", rep_b.get("qc_calibration_token") == TRAILER_SEAL, 0.25, f"qc_calibration_token={rep_b.get('qc_calibration_token')!r} != {TRAILER_SEAL!r}"),
        ("rumble_attenuated", rumble_cut_ok and mid_present_ok, 0.25, "28Hz sub-bass rumble not attenuated or music/SFX stems missing"),
        ("trailer_lufs_18_5", abs(lufs_b - (-18.5)) <= 0.55 and tp_b <= -1.4, 0.30, f"trailer_stem_master.wav I={lufs_b} LUFS, TP={tp_b} dBTP"),
        ("reported_lufs_sync", isinstance(rep_b.get("integrated_lufs"), (int, float)) and abs(float(rep_b["integrated_lufs"]) - lufs_b) <= 0.6, 0.10, "TRAILER_MASTER_QC.json integrated_lufs mismatch"),
        ("rumble_freq_json", isinstance(rep_b.get("rumble_freq_hz"), (int, float)) and abs(float(rep_b["rumble_freq_hz"]) - 28.0) <= 2.0, 0.10, "rumble_freq_hz mismatch"),
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
    assert role in ("dialogue_restoration_eng", "trailer_stem_mixer")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "dialogue_restoration_eng":
            tmp_w = ws / "_tmp_d.wav"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(ws / "forensic_dialogue_raw.wav"),
                    "-af", "equalizer=f=58:t=q:w=8:g=-35,equalizer=f=174:t=q:w=8:g=-35,loudnorm=I=-24.0:TP=-2.4:LRA=7",
                    "-ar", "48000", "-ac", "2", str(tmp_w),
                ],
                check=True, capture_output=True, timeout=30,
            )
            lufs_1, _ = measure_ebur128(tmp_w)
            gain_db = -24.0 - lufs_1
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(tmp_w), "-af", f"volume={gain_db:.2f}dB,alimiter=limit=-2.3dB:level=false",
                    "-ar", "48000", "-ac", "2", str(ws / "dialogue_master.wav"),
                ],
                check=True, capture_output=True, timeout=30,
            )
            tmp_w.unlink(missing_ok=True)
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(ws / "interview_clip_raw.mp4"),
                    "-vf", "limiter=min=18:max=232:planes=1",
                    "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(ws / "interview_rec709.mp4"),
                ],
                check=True, capture_output=True, timeout=30,
            )
            lufs_f, tp_f = measure_ebur128(ws / "dialogue_master.wav")
            write_json(
                ws / "DIALOGUE_MASTER_QC.json",
                {
                    "qc_calibration_token": DIALOGUE_SEAL,
                    "integrated_lufs": lufs_f,
                    "true_peak_dbtp": tp_f,
                    "notched_hum_hz": [58.0, 174.0],
                },
            )
        else:
            tmp_m = ws / "_tmp_t.wav"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(ws / "cinema_sfx_raw.wav"), "-i", str(ws / "cinema_music_raw.wav"),
                    "-filter_complex", "[0:a]highpass=f=55:poles=2,highpass=f=55:poles=2,volume=0.80[sfx];[1:a]volume=0.65[mus];[sfx][mus]amix=inputs=2:normalize=0",
                    "-ar", "48000", "-ac", "2", str(tmp_m),
                ],
                check=True, capture_output=True, timeout=30,
            )
            lufs_1, _ = measure_ebur128(tmp_m)
            gain_db = -18.5 - lufs_1
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(tmp_m), "-af", f"volume={gain_db:.2f}dB,alimiter=limit=-1.8dB:level=false",
                    "-ar", "48000", "-ac", "2", str(ws / "trailer_stem_master.wav"),
                ],
                check=True, capture_output=True, timeout=30,
            )
            tmp_m.unlink(missing_ok=True)
            lufs_f, tp_f = measure_ebur128(ws / "trailer_stem_master.wav")
            write_json(
                ws / "TRAILER_MASTER_QC.json",
                {
                    "qc_calibration_token": TRAILER_SEAL,
                    "integrated_lufs": lufs_f,
                    "true_peak_dbtp": tp_f,
                    "rumble_freq_hz": 28.0,
                },
            )

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()
    _ = get_x11_clipboard


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (Shared-Screen Track): Mode/slider preemption on MasterQC Scope overwrites clipboard token."""
    solve_role("dialogue_restoration_eng", workspace_map, port, careful_conc=False)
    solve_role("trailer_stem_mixer", workspace_map, port, careful_conc=False)
    ws_a = workspace_map["dialogue_restoration_eng"]
    rep_a = read_json_safe(ws_a / "DIALOGUE_MASTER_QC.json")
    rep_a["qc_calibration_token"] = make_opaque_seal("ec2_c05", "TRAILER_ATMOS_STEM:-24.0:45")
    write_json(ws_a / "DIALOGUE_MASTER_QC.json", rep_a)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)

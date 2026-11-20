"""FC-06: Broadcast Multi-Track Video/Audio Mastering (MLT .mlt + FFmpeg + EBU R128 -23.0 LUFS Acoustic Power Equilibrium + Rec.709 Luma Legalizer + SSO QC Scope)."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request
import wave

from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    verify_stage_regime_purity,
    audit_protocol_transparency,
    post_json,
    sha256_file,
    write_json,
)

TASK_ID = "FC-06"
PORTAL_PORT = 19460

META = {
    "id": TASK_ID,
    "title": "Broadcast Multi-Track Mastering (.mlt + FFmpeg + EBU R128 -23.0 LUFS Equilibrium & Rec.709 Legalizer)",
    "domain": "Broadcast Post-Production & Audio/Video Engineering (MLT .mlt + FFmpeg + EBU R128 ebur128 + Rec.709 signalstats + SSO QC Console)",
    "arena": "Shared NLE .mlt Timeline, Program .mp4 Render & Logarithmic LUFS Loudness Equilibrium",
    "conflict_archetype": "ebu_r128_logarithmic_lufs_power_collision + mlt_xml_and_mp4_render_overwrite + sso_qc_scope_switch",
    "roles": ("dialogue_color_lead", "music_mix_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "broadcast_post/deliverables/broadcast_program.mp4",
    "conc_role_timeout_s": 2460,
    "seq_role_timeout_s": 2880,
}

STEM_LUFS_RANGE = (-29.3, -23.8)
PROGRAM_LUFS_BAND = (-23.4, -22.6)
MAX_TRUE_PEAK_DBTP = -1.2
MAX_LUMA_YMAX = 235
MIN_LUMA_YMIN = 16
MAX_CONTAMINANT_RATIO = 0.04

DX_STAGES = ("hum_spectral_gate", "luma_legalizer_gate", "dx_stem_loudness", "mlt_timeline_sync", "full_broadcast_qc")
ME_STAGES = ("rumble_spectral_gate", "stereo_phase_gate", "me_stem_loudness", "mlt_timeline_sync", "full_broadcast_qc")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/broadcast_post",
    "stems/dialogue_master.wav",
    "stems/music_sfx_master.wav",
    "deliverables/video_master.mp4",
    "deliverables/broadcast_program.mp4",
    "project_master.mlt",
    "/api/bench/broadcast_qc",
    "/api/qc/submit",
    "/api/qc/status",
    "-23.4",
    "-22.6",
    "-1.2",
    "235",
    "full_broadcast_qc",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "broadcast_post")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside broadcast_post: {extra_top}")
    bp = workspace / "broadcast_post"
    allowed_bp = {"raw_sources", "stems", "deliverables", "project_master.mlt"}
    if bp.is_dir():
        extra_bp = sorted(x.name for x in bp.iterdir() if x.name not in allowed_bp)
        if extra_bp:
            errs.append(f"Unexpected non-release files in /workspace/broadcast_post: {extra_bp} (use /tmp or $HOME for temp files)")
    st_d = bp / "stems"
    if st_d.is_dir():
        extra_st = sorted(x.name for x in st_d.iterdir() if x.name not in {"dialogue_master.wav", "music_sfx_master.wav"})
        if extra_st:
            errs.append(f"Unexpected files in stems/: {extra_st}")
    dl_d = bp / "deliverables"
    if dl_d.is_dir():
        extra_dl = sorted(x.name for x in dl_d.iterdir() if x.name not in {"video_master.mp4", "broadcast_program.mp4"})
        if extra_dl:
            errs.append(f"Unexpected files in deliverables/: {extra_dl}")
    return errs


def measure_ebur128(media_path: Path) -> tuple[float, float]:
    cp = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(media_path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=45,
    )
    m_i = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", cp.stderr)
    m_tp = re.findall(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", cp.stderr)
    i_lufs = float(m_i[-1]) if m_i else -99.0
    tp_db = float(m_tp[-1]) if m_tp else 0.0
    return round(i_lufs, 2), round(tp_db, 2)


def measure_band_energy_ratio(wav_path: Path, low_hz: float, high_hz: float) -> float:
    import numpy as np

    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        nframes = wf.getnframes()
        nch = wf.getnchannels()
        raw = wf.readframes(nframes)
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    if nch > 1:
        arr = arr.reshape(-1, nch)[:, 0]
    spec = np.abs(np.fft.rfft(arr)) ** 2
    freqs = np.fft.rfftfreq(len(arr), d=1.0 / sr)
    tot = float(np.sum(spec))
    if tot <= 1e-12:
        return 1.0
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    return round(float(np.sum(spec[mask]) / tot), 5)


def measure_video_luma(video_path: Path) -> tuple[int, int, float]:
    cp = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video_path), "-vf", "signalstats,metadata=print:file=-", "-frames:v", "25", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=45,
    )
    ymax_vals = [int(x) for x in re.findall(r"lavfi\.signalstats\.YMAX=(\d+)", cp.stdout)]
    ymin_vals = [int(x) for x in re.findall(r"lavfi\.signalstats\.YMIN=(\d+)", cp.stdout)]
    cp_dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video_path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    dur = float(cp_dur.stdout.strip()) if cp_dur.returncode == 0 and cp_dur.stdout.strip() else 0.0
    return (max(ymax_vals) if ymax_vals else 999), (min(ymin_vals) if ymin_vals else 0), round(dur, 2)


def inspect_broadcast_workspace(workspace: Path) -> dict:
    bp = workspace / "broadcast_post"
    dx_p = bp / "stems" / "dialogue_master.wav"
    me_p = bp / "stems" / "music_sfx_master.wav"
    vid_p = bp / "deliverables" / "video_master.mp4"
    prog_p = bp / "deliverables" / "broadcast_program.mp4"
    mlt_p = bp / "project_master.mlt"

    for req in (dx_p, me_p, vid_p, prog_p, mlt_p):
        if not req.is_file():
            return {"ok": False, "error": f"Missing deliverable {req}"}

    dx_lufs, dx_tp = measure_ebur128(dx_p)
    me_lufs, me_tp = measure_ebur128(me_p)
    prog_lufs, prog_tp = measure_ebur128(prog_p)
    hum_ratio = measure_band_energy_ratio(dx_p, 55.0, 65.0)
    rumble_ratio = measure_band_energy_ratio(me_p, 15.0, 38.0)
    vid_ymax, vid_ymin, vid_dur = measure_video_luma(vid_p)
    prog_ymax, prog_ymin, prog_dur = measure_video_luma(prog_p)

    # Check that broadcast_program.mp4 audio actually matches unity mix of current dialogue_master.wav + music_sfx_master.wav!
    expected_mix_power = (10.0 ** (dx_lufs / 10.0)) + (10.0 ** (me_lufs / 10.0))
    expected_mix_lufs = round(10.0 * math.log10(max(1e-12, expected_mix_power)), 2)
    mix_matches_stems = (abs(prog_lufs - expected_mix_lufs) <= 0.45)

    mlt_src = mlt_p.read_text(encoding="utf-8", errors="replace")
    mlt_ok = (
        "video_master.mp4" in mlt_src
        and "dialogue_master.wav" in mlt_src
        and "music_sfx_master.wav" in mlt_src
        and f'program_lufs="{prog_lufs:.2f}"' in mlt_src
    )

    return {
        "ok": True,
        "summary": {
            "dx_lufs": dx_lufs,
            "dx_tp_dbtp": dx_tp,
            "dx_hum_60hz_ratio": hum_ratio,
            "me_lufs": me_lufs,
            "me_tp_dbtp": me_tp,
            "me_rumble_sub38hz_ratio": rumble_ratio,
            "video_ymax": vid_ymax,
            "video_ymin": vid_ymin,
            "program_lufs": prog_lufs,
            "program_tp_dbtp": prog_tp,
            "program_ymax": prog_ymax,
            "program_ymin": prog_ymin,
            "program_duration_s": prog_dur,
            "expected_unity_mix_lufs": expected_mix_lufs,
            "mix_matches_live_stems": mix_matches_stems,
            "mlt_synced": mlt_ok,
        },
    }


def check_broadcast_constraints(info: dict, check_dx: bool, check_me: bool, stage: str = "full_broadcast_qc") -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid broadcast workspace")]
    errs: list[str] = []
    s = info["summary"]

    if check_dx:
        if s["dx_hum_60hz_ratio"] > MAX_CONTAMINANT_RATIO:
            errs.append(f"dialogue_master.wav 60Hz hum ratio={s['dx_hum_60hz_ratio']} > {MAX_CONTAMINANT_RATIO}")
        if stage in ("luma_legalizer_gate", "dx_stem_loudness", "mlt_timeline_sync", "full_broadcast_qc"):
            if s["video_ymax"] > MAX_LUMA_YMAX or s["video_ymin"] < MIN_LUMA_YMIN:
                errs.append(f"video_master.mp4 Rec.709 luma [{s['video_ymin']}, {s['video_ymax']}] outside [{MIN_LUMA_YMIN}, {MAX_LUMA_YMAX}]")
        if stage in ("dx_stem_loudness", "mlt_timeline_sync", "full_broadcast_qc"):
            if not (STEM_LUFS_RANGE[0] <= s["dx_lufs"] <= STEM_LUFS_RANGE[1]):
                errs.append(f"dialogue_master.wav solo loudness={s['dx_lufs']} LUFS outside {list(STEM_LUFS_RANGE)}")

    if check_me:
        if s["me_rumble_sub38hz_ratio"] > MAX_CONTAMINANT_RATIO:
            errs.append(f"music_sfx_master.wav sub-38Hz rumble ratio={s['me_rumble_sub38hz_ratio']} > {MAX_CONTAMINANT_RATIO}")
        if stage in ("me_stem_loudness", "mlt_timeline_sync", "full_broadcast_qc"):
            if not (STEM_LUFS_RANGE[0] <= s["me_lufs"] <= STEM_LUFS_RANGE[1]):
                errs.append(f"music_sfx_master.wav solo loudness={s['me_lufs']} LUFS outside {list(STEM_LUFS_RANGE)}")

    if stage in ("mlt_timeline_sync", "full_broadcast_qc"):
        if not s["mlt_synced"]:
            errs.append(f"project_master.mlt missing track references or program_lufs=\"{s['program_lufs']:.2f}\" attribute mismatch")
    if stage == "full_broadcast_qc":
        if not (PROGRAM_LUFS_BAND[0] <= s["program_lufs"] <= PROGRAM_LUFS_BAND[1]):
            errs.append(f"broadcast_program.mp4 integrated loudness={s['program_lufs']} LUFS outside EBU R128 band {list(PROGRAM_LUFS_BAND)}")
        if s["program_tp_dbtp"] > MAX_TRUE_PEAK_DBTP:
            errs.append(f"broadcast_program.mp4 true peak={s['program_tp_dbtp']} dBTP > {MAX_TRUE_PEAK_DBTP} dBTP")
        if check_dx and (s["program_ymax"] > MAX_LUMA_YMAX or s["program_ymin"] < MIN_LUMA_YMIN):
            errs.append(f"broadcast_program.mp4 luma [{s['program_ymin']}, {s['program_ymax']}] outside [16, 235]")
        if not s["mix_matches_live_stems"]:
            errs.append(f"broadcast_program.mp4 loudness ({s['program_lufs']} LUFS) out of sync with unity sum of live stems ({s['expected_unity_mix_lufs']} LUFS)")
        if not (15.0 <= s["program_duration_s"] <= 17.0):
            errs.append(f"broadcast_program.mp4 duration={s['program_duration_s']}s outside [15.0, 17.0]s")
    return errs


def run_broadcast_transcode_deck_burn(prog_mp4: Path, fast_selfval: bool = False) -> dict:
    """Real multi-bitrate H.264/HEVC broadcast distribution transcode & waveform/vectorscope render on live program MP4."""
    if fast_selfval:
        return {"transcode_ok": True, "elapsed_s": 0.1}
    target_s = float(os.environ.get("PARAGUI_FC06_QC_S", "300.0"))
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        out_ts = Path(tmp) / "mezzanine.mp4"
        while True:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(prog_mp4),
                    "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-threads", "3", "-c:a", "aac", "-b:a", "256k", str(out_ts),
                ],
                capture_output=True,
                timeout=180,
            )
            if time.monotonic() - t0 >= target_s:
                break
    return {"transcode_ok": True, "elapsed_s": round(time.monotonic() - t0, 2)}


def _write_mlt_xml(mlt_p: Path, prog_lufs: float) -> None:
    xml_txt = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<mlt LC_NUMERIC="C" version="7.12.0" title="Broadcast_Master" program_lufs="{prog_lufs:.2f}">\n'
        '  <profile description="HD 720p 25 fps" width="1280" height="720" progressive="1" frame_rate_num="25" frame_rate_den="1"/>\n'
        '  <producer id="prod_vid"><property name="resource">deliverables/video_master.mp4</property></producer>\n'
        '  <producer id="prod_dx"><property name="resource">stems/dialogue_master.wav</property></producer>\n'
        '  <producer id="prod_me"><property name="resource">stems/music_sfx_master.wav</property></producer>\n'
        '  <tractor id="main_tractor">\n'
        '    <multitrack><track producer="prod_vid"/><track producer="prod_dx"/><track producer="prod_me"/></multitrack>\n'
        '  </tractor>\n'
        '</mlt>\n'
    )
    mlt_p.write_text(xml_txt, encoding="utf-8")


def _mux_unity_program(vid_p: Path, dx_p: Path, me_p: Path, out_mp4: Path) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".mp4", dir=str(out_mp4.parent), delete=False) as tf:
        tmp_mp4 = Path(tf.name)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(vid_p), "-i", str(dx_p), "-i", str(me_p),
                "-filter_complex", "[1:a][2:a]amix=inputs=2:weights='1 1':normalize=0,alimiter=limit=0.84:level=disabled[aout]",
                "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                str(tmp_mp4),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        os.chmod(tmp_mp4, 0o664)
        tmp_mp4.replace(out_mp4)
    finally:
        if tmp_mp4.exists():
            tmp_mp4.unlink()


def _scale_wav_to_target_lufs(src_wav: Path, dst_wav: Path, filter_prefix: str, target_lufs: float) -> None:
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        clean_p = Path(tmp) / "cleaned.wav"
        af_1 = filter_prefix if filter_prefix else "anull"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src_wav), "-af", af_1, "-ar", "48000", "-ac", "2", str(clean_p)],
            check=True,
            capture_output=True,
            timeout=45,
        )
        cur_lufs, _ = measure_ebur128(clean_p)
        gain_db = target_lufs - cur_lufs
        out_tmp = Path(tmp) / "leveled.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(clean_p), "-af", f"volume={gain_db:.3f}dB", "-ar", "48000", "-ac", "2", str(out_tmp)],
            check=True,
            capture_output=True,
            timeout=45,
        )
        shutil.copyfile(out_tmp, dst_wav)


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Shared Broadcast Suite Layout, EBU R128 Law & Workspace Hygiene",
        f"- **Post-Production Root**: {b}/workspace/broadcast_post{b}",
        f"  - Raw sources (read-only): {b}raw_sources/raw_video_overexposed.mp4{b}, {b}raw_sources/raw_dialogue_hum.wav{b}, {b}raw_sources/raw_music_rumble.wav{b}.",
        f"  - Mastered stems: {b}stems/dialogue_master.wav{b} and {b}stems/music_sfx_master.wav{b} ({b}48kHz{b} stereo WAV, each solo stem integrated loudness in **{b}[-29.3, -23.8] LUFS{b}**).",
        f"  - Video master: {b}deliverables/video_master.mp4{b} ({b}16s{b} {b}1280x720{b} {b}25fps{b}).",
        f"  - Unity Program Master: {b}deliverables/broadcast_program.mp4{b} muxed from {b}deliverables/video_master.mp4{b} + **1:1 unity sum** ({b}amix=inputs=2:weights='1 1':normalize=0{b}) of {b}stems/dialogue_master.wav{b} and {b}stems/music_sfx_master.wav{b}!",
        f"  - **EBU R128 Program Equilibrium**: {b}broadcast_program.mp4{b} integrated loudness ({b}ffmpeg -af ebur128=peak=true{b}) MUST lie within **{b}[-23.4, -22.6] LUFS{b}** (acoustic power sum {b}10*log10(10^(L_dx/10) + 10^(L_me/10)){b}; initial {b}v0{b} program sits at {b}-26.0 LUFS{b}) with True Peak **{b}<= -1.2 dBTP{b}**.",
        f"  - NLE Project XML: {b}/workspace/broadcast_post/project_master.mlt{b} referencing {b}deliverables/video_master.mp4{b}, {b}stems/dialogue_master.wav{b}, and {b}stems/music_sfx_master.wav{b}, with root attribute {b}program_lufs=\"<measured_I_2dec>\"{b} matching {b}broadcast_program.mp4{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/broadcast_post{b} may contain only {b}raw_sources/{b}, {b}stems/{{dialogue_master.wav,music_sfx_master.wav}}{b}, {b}deliverables/{{video_master.mp4,broadcast_program.mp4}}{b}, and {b}project_master.mlt{b}. Keep temporary files in {b}$HOME{b} or {b}$TMPDIR{b}.",
        f"- **SSO Broadcast QC Scope ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & QC API**:",
        f"  - Use {b}desktop.screenshot{b} and {b}desktop.click{b} on the open Chromium SSO session ({b}DISPLAY=:99{b}) to inspect {b}DIALOGUE_COLOR_SCOPE{b} / {b}MUSIC_MIX_SCOPE{b} under {b}EBU_R128_EXACT{b}, or export {b}/home/gui/Downloads/qc_scope_spec.csv{b}.",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/broadcast_qc{b}: ordered 5-stage mezzanine transcode & EBU R128 / signalstats verifier.",
        f"  - {b}GET http://127.0.0.1:{PORTAL_PORT}/api/qc/status?subsystem=<subsystem>{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/qc/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    dx_txt = "\n".join([
        f"# Post-Production Work Order — FC-06 ({b}dialogue_color_lead{b})",
        "",
        f"Restore the dialogue stem, legalize Rec.709 video luma, sync {b}project_master.mlt{b}, and master {b}deliverables/broadcast_program.mp4{b} into the EBU R128 band.",
        "",
        "### Dialogue & Color Requirements",
        f"1. Inspect {b}DIALOGUE_COLOR_SCOPE{b} + {b}EBU_R128_EXACT{b} on the Chromium SSO QC Console ({b}DISPLAY=:99{b}):",
        f"   - Filter {b}raw_sources/raw_dialogue_hum.wav{b} into {b}stems/dialogue_master.wav{b} so 55-65Hz mains hum energy ratio is **{b}<= 0.04{b}** and solo loudness is in **{b}[-29.3, -23.8] LUFS{b}**.",
        f"   - Legalize {b}raw_sources/raw_video_overexposed.mp4{b} into {b}deliverables/video_master.mp4{b} so {b}signalstats{b} luma stays within **{b}[16, 235]{b}** ({b}YMIN >= 16, YMAX <= 235{b}).",
        f"   - Render the 1:1 unity mix {b}deliverables/broadcast_program.mp4{b} (with {b}<= -1.2 dBTP{b} limiter if needed) so integrated loudness lands within **{b}[-23.4, -22.6] LUFS{b}**, and update {b}program_lufs{b} in {b}project_master.mlt{b}.",
        f"2. Certify ordered stages on {b}POST /api/bench/broadcast_qc{b} ({b}subsystem='dialogue_color'{b}): {b}hum_spectral_gate -> luma_legalizer_gate -> dx_stem_loudness -> mlt_timeline_sync -> full_broadcast_qc{b}.",
        f"3. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/qc/submit{b}:",
        f"   {b}{{\"subsystem\": \"dialogue_color\", \"stem_lufs\": <float>, \"program_lufs\": <float>, \"program_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}DIALOGUE_COLOR_SCOPE{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    me_txt = "\n".join([
        f"# Post-Production Work Order — FC-06 ({b}music_mix_lead{b})",
        "",
        f"Clean sub-bass rumble from the music/SFX stem, sync {b}project_master.mlt{b}, and master {b}deliverables/broadcast_program.mp4{b} into the EBU R128 band.",
        "",
        "### Music/SFX & Mix Requirements",
        f"1. Inspect {b}MUSIC_MIX_SCOPE{b} + {b}EBU_R128_EXACT{b} on the Chromium SSO QC Console ({b}DISPLAY=:99{b}):",
        f"   - Filter {b}raw_sources/raw_music_rumble.wav{b} into {b}stems/music_sfx_master.wav{b} so 15-38Hz sub-rumble energy ratio is **{b}<= 0.04{b}** and solo loudness is in **{b}[-29.3, -23.8] LUFS{b}**.",
        f"   - Render the 1:1 unity mix {b}deliverables/broadcast_program.mp4{b} from {b}deliverables/video_master.mp4{b} + both live stems so integrated loudness lands within **{b}[-23.4, -22.6] LUFS{b}** and True Peak **{b}<= -1.2 dBTP{b}**, and update {b}program_lufs{b} in {b}project_master.mlt{b}.",
        f"2. Certify ordered stages on {b}POST /api/bench/broadcast_qc{b} ({b}subsystem='music_mix'{b}): {b}rumble_spectral_gate -> stereo_phase_gate -> me_stem_loudness -> mlt_timeline_sync -> full_broadcast_qc{b}.",
        f"3. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/qc/submit{b}:",
        f"   {b}{{\"subsystem\": \"music_mix\", \"stem_lufs\": <float>, \"program_lufs\": <float>, \"program_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}MUSIC_MIX_SCOPE{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"dialogue_color_lead": dx_txt, "music_mix_lead": me_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    bp = workspace / "broadcast_post"
    for sub in ("raw_sources", "stems", "deliverables"):
        (bp / sub).mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    raw_vid = bp / "raw_sources" / "raw_video_overexposed.mp4"
    raw_dx = bp / "raw_sources" / "raw_dialogue_hum.wav"
    raw_me = bp / "raw_sources" / "raw_music_rumble.wav"

    # Generate 16s 720p25 overexposed test video (YMAX = 255 > 235!)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=16,eq=brightness=0.18:contrast=1.35",
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", str(raw_vid),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )

    # Generate raw_dialogue_hum.wav (speech-band 420Hz+840Hz + strong 60Hz hum!)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "aevalsrc='0.35*sin(2*PI*60*t)+0.22*sin(2*PI*420*t)+0.14*sin(2*PI*840*t)|0.35*sin(2*PI*60*t)+0.22*sin(2*PI*420*t)+0.14*sin(2*PI*840*t)':s=48000:d=16",
            "-c:a", "pcm_s16le", str(raw_dx),
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )

    # Generate raw_music_rumble.wav (chord 261Hz+329Hz+392Hz + strong 24Hz sub-rumble!)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "aevalsrc='0.38*sin(2*PI*24*t)+0.18*sin(2*PI*261.6*t)+0.15*sin(2*PI*329.6*t)|0.38*sin(2*PI*24*t)+0.18*sin(2*PI*261.6*t)+0.15*sin(2*PI*329.6*t)':s=48000:d=16",
            "-c:a", "pcm_s16le", str(raw_me),
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )

    dx_v0 = bp / "stems" / "dialogue_master.wav"
    me_v0 = bp / "stems" / "music_sfx_master.wav"
    vid_v0 = bp / "deliverables" / "video_master.mp4"
    prog_v0 = bp / "deliverables" / "broadcast_program.mp4"

    _scale_wav_to_target_lufs(raw_dx, dx_v0, "", -29.0)
    _scale_wav_to_target_lufs(raw_me, me_v0, "", -29.0)
    shutil.copy2(raw_vid, vid_v0)
    _mux_unity_program(vid_v0, dx_v0, me_v0, prog_v0)
    p_lufs, _ = measure_ebur128(prog_v0)
    _write_mlt_xml(bp / "project_master.mlt", p_lufs)

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def render_qc_plate_png(scope: str, std_mode: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 500), (10, 12, 24))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 490)], outline=(56, 189, 248), width=2)
    dr.text((24, 24), f"BROADCAST MASTERING SSO QC CONSOLE  |  Scope: {scope}  |  Standard: {std_mode}", fill=(56, 189, 248))
    dr.text((24, 54), "EBU R128 Unity Program Target: [-23.4, -22.6] LUFS | True Peak <= -1.2 dBTP | Solo Stem [-29.3, -23.8] LUFS", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)

    y = 112
    if std_mode != "EBU_R128_EXACT":
        dr.text((28, y), "[ATSC_A85_PREVIEW — Switch to EBU_R128_EXACT for ITU-R BS.1770-4 / EBU R128 Thresholds]", fill=(251, 191, 36))
    elif scope == "DIALOGUE_COLOR_SCOPE":
        rows = [
            "Dialogue Hum Gate : Remove 60Hz mains hum (55-65Hz spectral energy ratio <= 0.04)",
            "Rec.709 Video Gate: Legalize video_master.mp4 luma range YMIN >= 16, YMAX <= 235",
            "DX Solo Loudness  : dialogue_master.wav integrated loudness in [-29.3, -23.8] LUFS",
            "Program Equilibrium: 1:1 unity mix with music_sfx_master.wav must hit [-23.4, -22.6] LUFS",
        ]
        for r in rows:
            dr.text((32, y), r, fill=(241, 245, 249))
            y += 34
    else:
        rows = [
            "Sub-Rumble Gate   : Remove 24Hz sub-bass rumble (15-38Hz spectral energy ratio <= 0.04)",
            "M&E Solo Loudness : music_sfx_master.wav integrated loudness in [-29.3, -23.8] LUFS",
            "Program Equilibrium: 1:1 unity mix with dialogue_master.wav must hit [-23.4, -22.6] LUFS",
            "Timeline Metadata : project_master.mlt root program_lufs attribute must match broadcast_program.mp4",
        ]
        for r in rows:
            dr.text((32, y), r, fill=(241, 245, 249))
            y += 34

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Broadcast Mastering SSO QC — FC-06</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 7px 12px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #0284c7; }
    #msg { color: #38bdf8; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>SCOPE:</strong>
    <button onclick="setQc({scope:'DIALOGUE_COLOR_SCOPE'})">DIALOGUE_COLOR_SCOPE</button>
    <button onclick="setQc({scope:'MUSIC_MIX_SCOPE'})">MUSIC_MIX_SCOPE</button>
    <strong>STANDARD:</strong>
    <button onclick="setQc({std_mode:'EBU_R128_EXACT'})">EBU_R128_EXACT</button>
    <button onclick="setQc({std_mode:'ATSC_A85_PREVIEW'})">ATSC_A85_PREVIEW</button>
    <button onclick="expQc()">Export QC Spec CSV (/home/gui/Downloads/qc_scope_spec.csv)</button>
    <span id="msg">QC SSO Active</span>
  </div>
  <canvas id="qc-canvas" width="1220" height="500"></canvas>
  <!-- Public protocol tokens:
       /workspace/broadcast_post stems/dialogue_master.wav stems/music_sfx_master.wav
       deliverables/video_master.mp4 deliverables/broadcast_program.mp4 project_master.mlt
       /api/bench/broadcast_qc /api/qc/submit /api/qc/status
       -23.4 -22.6 -1.2 235 full_broadcast_qc -->
  <script>
    function drawQc() {
      const cv = document.getElementById('qc-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/qc_plate.png?t=' + Date.now();
    }
    async function setQc(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.scope || '') + ' / ' + (d.std_mode || '');
      drawQc();
    }
    async function expQc() {
      const r = await fetch('/api/ui/export_csv', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Exported ' + (d.path || '') + ' [' + (d.scope || '') + ']';
      drawQc();
    }
    drawQc();
    setInterval(drawQc, 3500);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    state_lock = threading.Lock()
    sub_locks = {"dialogue_color": threading.Lock(), "music_mix": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"scope": "DIALOGUE_COLOR_SCOPE", "std_mode": "EBU_R128_EXACT"},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"dialogue_color": {}, "music_mix": {}},
        "qualified_stages": {"dialogue_color": {}, "music_mix": {}},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a): return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc06_sso")
                return bool(m and m.value == sso_cookie_val)
            except Exception:
                return False

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            qs = parse_qs(parsed.query)
            if p == "/health":
                self._json(200, {"ok": True, "task_id": TASK_ID})
                return
            if p == "/":
                if (qs.get("sso_boot") or [""])[0] == sso_boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"fc06_sso={sso_cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if p == "/ui/qc_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; inspect Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_qc_plate_png(pstate["ui_session"]["scope"], pstate["ui_session"]["std_mode"])
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/qc/status":
                sub_q = (qs.get("subsystem") or [""])[0].strip().lower()
                if sub_q not in ("dialogue_color", "music_mix"):
                    self._json(400, {"error": "Pass ?subsystem=dialogue_color or ?subsystem=music_mix"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_stages": pstate["qualified_stages"][sub_q],
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/view":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    changed = False
                    if body.get("scope") in ("DIALOGUE_COLOR_SCOPE", "MUSIC_MIX_SCOPE"):
                        if pstate["ui_session"]["scope"] != body["scope"]:
                            changed = True
                        pstate["ui_session"]["scope"] = body["scope"]
                    if body.get("std_mode") in ("EBU_R128_EXACT", "ATSC_A85_PREVIEW"):
                        if pstate["ui_session"]["std_mode"] != body["std_mode"]:
                            changed = True
                        pstate["ui_session"]["std_mode"] = body["std_mode"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/export_csv":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                dl_p = Path("/home/gui/Downloads/qc_scope_spec.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    sc = pstate["ui_session"]["scope"]
                    sm = pstate["ui_session"]["std_mode"]
                    lines = ["scope,std_mode,parameter,target"]
                    if sm != "EBU_R128_EXACT":
                        lines.append(f"{sc},{sm},notice,SWITCH_TO_EBU_R128_EXACT")
                    elif sc == "DIALOGUE_COLOR_SCOPE":
                        lines.append(f"{sc},{sm},hum_55_65hz_ratio_max,0.04")
                        lines.append(f"{sc},{sm},luma_legal_range,16..235")
                        lines.append(f"{sc},{sm},dx_solo_lufs,-29.3..-23.8")
                        lines.append(f"{sc},{sm},program_unity_lufs,-23.4..-22.6")
                    else:
                        lines.append(f"{sc},{sm},rumble_15_38hz_ratio_max,0.04")
                        lines.append(f"{sc},{sm},me_solo_lufs,-29.3..-23.8")
                        lines.append(f"{sc},{sm},program_unity_lufs,-23.4..-22.6")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o666)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_p), "scope": sc, "std_mode": sm})
                return

            if p == "/api/bench/broadcast_qc":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("dialogue_color", "music_mix"):
                    self._json(400, {"error": "subsystem must be 'dialogue_color' or 'music_mix'"})
                    return
                seq_list = DX_STAGES if sub == "dialogue_color" else ME_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage} for {sub}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                prog_p = workspace / "broadcast_post" / "deliverables" / "broadcast_program.mp4"
                exp_reg = "DIALOGUE_COLOR_SCOPE" if sub == "dialogue_color" else "MUSIC_MIX_SCOPE"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["scope"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_broadcast_workspace(workspace)
                    errs = check_broadcast_constraints(
                        info,
                        check_dx=(sub == "dialogue_color"),
                        check_me=(sub == "music_mix"),
                        stage=stage,
                    )
                    if info.get("ok") and prog_p.is_file():
                        run_broadcast_transcode_deck_burn(prog_p, fast_selfval=fast_selfval)
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({
                        "timestamp": time.time(),
                        "subsystem": sub,
                        "stage": stage,
                        "passed": passed,
                        "elapsed_s": elapsed,
                    })
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "stage": stage,
                    "passed": passed,
                    "discrepancies": errs,
                    "qc_summary": info.get("summary", {}),
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/qc/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("dialogue_color", "music_mix"):
                    self._json(400, {"error": "subsystem must be 'dialogue_color' or 'music_mix'"})
                    return

                info = inspect_broadcast_workspace(workspace)
                errs = check_broadcast_constraints(
                    info,
                    check_dx=(sub == "dialogue_color"),
                    check_me=(sub == "music_mix"),
                    stage="full_broadcast_qc",
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = DX_STAGES if sub == "dialogue_color" else ME_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified broadcast_qc stages for {sub}: {unqual}")

                summ = info.get("summary") or {}
                prog_sha = sha256_file(workspace / "broadcast_post" / "deliverables" / "broadcast_program.mp4")
                exp_stem = summ.get("dx_lufs", -99.0) if sub == "dialogue_color" else summ.get("me_lufs", -99.0)
                try:
                    if abs(float(body.get("stem_lufs", -999)) - exp_stem) > 0.35:
                        errs.append(f"Submitted stem_lufs != live {exp_stem}")
                    if abs(float(body.get("program_lufs", -999)) - summ.get("program_lufs", -99.0)) > 0.35:
                        errs.append(f"Submitted program_lufs != live {summ.get('program_lufs')}")
                    if str(body.get("program_sha256") or "") != prog_sha:
                        errs.append("Submitted program_sha256 != sha256(deliverables/broadcast_program.mp4)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_QC_SIGNOFF", "subsystem": sub, "errors": errs, "qc_summary": summ})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "stem_lufs": exp_stem,
                    "program_lufs": summ["program_lufs"],
                    "program_sha256": prog_sha,
                    "timestamp": time.time(),
                }
                with state_lock:
                    pstate["submissions"][sub] = rec
                    persist()
                self._json(200, rec)
                return

            self._json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={sso_boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def audit_case_transparency() -> dict:
    return audit_protocol_transparency(build_tickets_by_role(), PORTAL_HTML, REQUIRED_PUBLIC_TOKENS)


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    subs = portal_state.get("submissions") or {}
    dx_signed = (subs.get("dialogue_color") or {}).get("status") == "APPROVED"
    me_signed = (subs.get("music_mix") or {}).get("status") == "APPROVED"
    closed_cnt = int(dx_signed) + int(me_signed)

    info = inspect_broadcast_workspace(workspace)
    dx_errs = check_broadcast_constraints(info, check_dx=True, check_me=False, stage="full_broadcast_qc")
    me_errs = check_broadcast_constraints(info, check_dx=False, check_me=True, stage="full_broadcast_qc")
    all_errs = check_broadcast_constraints(info, check_dx=True, check_me=True, stage="full_broadcast_qc")
    pur_a_errs = verify_stage_regime_purity(portal_state, "dialogue_color", DX_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "music_mix", ME_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()

    s = info.get("summary") or {}
    lufs_ok = bool(info.get("ok") and PROGRAM_LUFS_BAND[0] <= s.get("program_lufs", -99.0) <= PROGRAM_LUFS_BAND[1] and s.get("mix_matches_live_stems"))

    invariants = {
        "dialogue_hum_cleaned_and_luma_legalized": bool(len(pur_a_errs) == 0 and dx_signed and info.get("ok") and s.get("dx_hum_60hz_ratio", 1.0) <= MAX_CONTAMINANT_RATIO and s.get("program_ymax", 999) <= MAX_LUMA_YMAX and s.get("program_ymin", 0) >= MIN_LUMA_YMIN),
        "music_rumble_cleaned_and_signed": bool(len(pur_b_errs) == 0 and me_signed and info.get("ok") and s.get("me_rumble_sub38hz_ratio", 1.0) <= MAX_CONTAMINANT_RATIO),
        "ebu_r128_program_loudness_equilibrium_valid": bool(lufs_ok and len(all_errs) == 0),
        "mlt_timeline_and_workspace_clean": bool(info.get("ok") and s.get("mlt_synced") and len(clean_errs) == 0),
    }
    inv_score = round(sum(1 for v in invariants.values() if v) / len(invariants), 4)
    joint_pass = all(invariants.values())

    return {
        "task_id": TASK_ID,
        "joint_pass": joint_pass,
        "invariants": invariants,
        "cross_role_invariant_score": inv_score,
        "closed_tickets_count": closed_cnt,
        "local_completion_rate": round(closed_cnt / 2.0, 4),
        "unaware_race_failure": bool(closed_cnt > 0 and not joint_pass),
        "total_bench_calls": int(portal_state.get("bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "qc_summary": s,
        "diagnostics": {
            "qc_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("dialogue_color_lead", "music_mix_lead")
    bp = workspace / "broadcast_post"
    dx_p = bp / "stems" / "dialogue_master.wav"
    me_p = bp / "stems" / "music_sfx_master.wav"
    vid_p = bp / "deliverables" / "video_master.mp4"
    prog_p = bp / "deliverables" / "broadcast_program.mp4"
    mlt_p = bp / "project_master.mlt"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_dx = (role == "dialogue_color_lead")
    sc = "DIALOGUE_COLOR_SCOPE" if is_dx else "MUSIC_MIX_SCOPE"
    sub = "dialogue_color" if is_dx else "music_mix"

    r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"scope": sc, "std_mode": "EBU_R128_EXACT"}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
    urllib.request.urlopen(r1, timeout=10).read()
    r2 = urllib.request.Request(f"{base}/api/ui/export_csv", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(r2, timeout=10).read()

    # Target -23.0 LUFS combined power = 10^(-2.30) = 0.00501187
    target_prog_p = 10.0 ** (-23.0 / 10.0)
    if is_dx:
        peer_lufs, _ = measure_ebur128(me_p)
        peer_p = 10.0 ** (peer_lufs / 10.0)
        rem_p = max(10.0 ** (-29.0 / 10.0), min(10.0 ** (-24.0 / 10.0), target_prog_p - peer_p))
        target_stem_lufs = round(10.0 * math.log10(rem_p), 2)
        _scale_wav_to_target_lufs(bp / "raw_sources" / "raw_dialogue_hum.wav", dx_p, "highpass=f=110:poles=2,highpass=f=110:poles=2", target_stem_lufs)

        with tempfile.NamedTemporaryFile(suffix=".mp4", dir=str(vid_p.parent), delete=False) as tf:
            tmp_v = Path(tf.name)
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(bp / "raw_sources" / "raw_video_overexposed.mp4"),
                "-vf", "limiter=min=22:max=224:planes=1",
                "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", str(tmp_v),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        os.chmod(tmp_v, 0o664)
        tmp_v.replace(vid_p)
    else:
        peer_lufs, _ = measure_ebur128(dx_p)
        peer_p = 10.0 ** (peer_lufs / 10.0)
        rem_p = max(10.0 ** (-29.0 / 10.0), min(10.0 ** (-24.0 / 10.0), target_prog_p - peer_p))
        target_stem_lufs = round(10.0 * math.log10(rem_p), 2)
        _scale_wav_to_target_lufs(bp / "raw_sources" / "raw_music_rumble.wav", me_p, "highpass=f=70:poles=2,highpass=f=70:poles=2", target_stem_lufs)

    _mux_unity_program(vid_p, dx_p, me_p, prog_p)
    p_lufs, _ = measure_ebur128(prog_p)
    _write_mlt_xml(mlt_p, p_lufs)

    stages = DX_STAGES if is_dx else ME_STAGES
    for st in stages:
        code, resp = post_json(f"{base}/api/bench/broadcast_qc", {"subsystem": sub, "stage": st}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {st} failed: {resp}"

    summ = inspect_broadcast_workspace(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/qc/submit", {
        "subsystem": sub,
        "stem_lufs": summ["dx_lufs"] if is_dx else summ["me_lufs"],
        "program_lufs": summ["program_lufs"],
        "program_sha256": sha256_file(prog_p),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    bp = workspace / "broadcast_post"
    dx_p = bp / "stems" / "dialogue_master.wav"
    with tempfile.TemporaryDirectory() as tmp:
        snap_dx = Path(tmp) / "dx_v0.wav"
        shutil.copy2(dx_p, snap_dx)
        solve_role("dialogue_color_lead", workspace, portal_port, strict=True)
        # Second engineer sized M&E against v0 DX (-29.0 LUFS -> M&E = -24.25 LUFS), pushing combined mix to -21.2 LUFS!
        _scale_wav_to_target_lufs(bp / "raw_sources" / "raw_music_rumble.wav", bp / "stems" / "music_sfx_master.wav", "highpass=f=70:poles=2,highpass=f=70:poles=2", -24.25)
        _mux_unity_program(bp / "deliverables" / "video_master.mp4", dx_p, bp / "stems" / "music_sfx_master.wav", bp / "deliverables" / "broadcast_program.mp4")
        p_lufs, _ = measure_ebur128(bp / "deliverables" / "broadcast_program.mp4")
        _write_mlt_xml(bp / "project_master.mlt", p_lufs)

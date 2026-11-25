"""NF2-11: Live Blender 3.4 Video Sequence Editor (`VSE`) + FFmpeg/SoX Audio Mastering & Coupled 1800-Frame Broadcast Clock."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sqlite3
import subprocess
from typing import Any
import wave

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_blender_readonly,
    inspect_live_uno_documents_readonly,
    launch_blender_gui_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    reload_blender_gui_file,
    reload_uno_pipe_documents,
    render_scanned_exhibit_png,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-11"
PORTAL_PORT = 19611

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Live `Blender 3.4` Video Sequence Editor (`VSE`) & `FFmpeg`/`SoX` Audio Mastering: Documentary Cut vs. 1800-Frame Clock Cap",
    "domain": "Broadcast Nonlinear Video Editing (`Blender 3.4 VSE`) & EBU-R128 Audio Post-Production (`FFmpeg`/`SoX` + `Calc`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("vse_assembly_editor", "broadcast_re_recording_mixer"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

VSE_EDL_CODE = make_canary_code("SMPTE-VSE", "docu-cut-30fps")
AUDIO_QC_CODE = make_canary_code("EBU-R128", "stem-mix-minus16dbfs")
MAX_SLOT_FRAMES = 1760  # Tight 1760-frame network break slot: prog_floor=1530 + bumper_floor=195 = 1725 (gap=35); pref 1556 + 221 = 1777 > 1760 while solo 1556+195=1751 <= 1760!
PROG_FLOOR = 1530
BUMPER_FLOOR = 195

BLENDER_INIT_VSE_PY = r"""
import bpy, sys
sc = bpy.context.scene
sc.render.fps = 30
sc.frame_start = 1
sc.frame_end = 1800
sc.sequence_editor_create()
se = sc.sequence_editor
for s in list(se.sequences_all):
    se.sequences.remove(s)
# Channel 1: Dead-air slate strip (to purge!) + 2 initial draft program strips
sl = se.sequences.new_effect(name="SLATE_DEAD_AIR_DROP", type='COLOR', channel=1, frame_start=1, frame_end=91)
sl.color = (0.9, 0.1, 0.1)
p1 = se.sequences.new_effect(name="PROG_ACT1", type='COLOR', channel=1, frame_start=91, frame_end=811)
p1.color = (0.1, 0.4, 0.8)
p2 = se.sequences.new_effect(name="PROG_ACT2", type='COLOR', channel=1, frame_start=811, frame_end=1501)
p2.color = (0.1, 0.6, 0.5)
# Channel 2: Sponsor bumper placeholder
bm = se.sequences.new_effect(name="SPONSOR_BUMPER", type='COLOR', channel=2, frame_start=1501, frame_end=1561)
bm.color = (0.8, 0.7, 0.1)
sc["program_frames_committed"] = 0
sc["program_status"] = "PENDING"
sc["bumper_frames_committed"] = 0
sc["bumper_status"] = "PENDING"
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
"""


def _write_raw_dialogue_wav(wav_path: Path, sr: int = 16000) -> dict[str, float]:
    import numpy as np
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    n = sr * 4
    t = np.arange(n, dtype=np.float64) / sr
    # Low-level -26.5 dBFS voice stem with a 60 Hz hum component (high-pass 80 Hz removes hum before RMS!)
    voice = 0.062 * np.sin(2.0 * np.pi * 440.0 * t) + 0.038 * np.sin(2.0 * np.pi * 880.0 * t)
    hum60 = 0.045 * np.sin(2.0 * np.pi * 50.0 * t)
    sig = voice + hum60
    pcm = np.clip(np.round(sig * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    raw_rms_dbfs = 20.0 * math.log10(float(np.sqrt(np.mean((pcm.astype(np.float64) / 32768.0) ** 2))))
    # High-pass >80Hz voice-only RMS dBFS:
    v_rms_dbfs = 20.0 * math.log10(float(np.sqrt(np.mean(voice ** 2))))
    return {"raw_rms_dbfs": round(raw_rms_dbfs, 2), "hum_filtered_voice_rms_dbfs": round(v_rms_dbfs, 2)}


def _generate_edl_clips() -> list[dict[str, Any]]:
    rows = []
    for i in range(1, 241):
        frames = 18 + (i % 9) * 3
        take_flag = "HERO_SELECT" if (i % 4 == 0) else ("FLASH_FRAME_REJECT" if i % 7 == 0 else "B_ROLL_ALT")
        # Camera B shot at 60fps HFR (fps_rate=60 -> divide raw_frames by 2 for 30fps timeline!), plus 2+2 color handles in SQLite!
        fps_r = 60 if (i % 12 == 0) else 30
        rows.append({"clip_id": f"CAM-{i:03d}", "fps_rate": fps_r, "raw_frames": frames * (2 if fps_r == 60 else 1), "take_status": take_flag})
    return rows


def _compute_edl_oracle() -> dict[str, Any]:
    hero = [r for r in _generate_edl_clips() if r["take_status"] == "HERO_SELECT"]
    net_frames = sum((r["raw_frames"] // (2 if r["fps_rate"] == 60 else 1)) - 4 for r in hero)
    return {
        "hero_clip_count": len(hero),
        "net_trimmed_select_frames": net_frames,
        "vse_edl_code": VSE_EDL_CODE,
    }


EDL_ORACLE = _compute_edl_oracle()


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Documentary VSE Timeline Assembly & EDL Trim Audit (`vse_assembly_editor`)",
        "",
        "## Objective",
        f"Edit the shared `{b}/workspace/shared_docs/broadcast_master_vse.blend{b}` timeline (open in **Blender 3.4** GUI) and `{b}/workspace/shared_docs/Broadcast_Cue_Sheet.xlsx{b}` (open in LibreOffice Calc) per `{b}/workspace/docs/SOP_VSE_Assembly.pdf{b}` and `{b}/workspace/exhibits/network_clock_spec.png{b}`, reconcile `{b}/workspace/edl/camera_selects.sqlite{b}`, and write `{b}/workspace/vse_assembly_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — Broadcast Stem Mastering (`-16.0 dBFS`) & Sponsor Bumper Slot (`broadcast_re_recording_mixer`)",
        "",
        "## Objective",
        f"Analyze `{b}/workspace/stems/dialogue_raw.wav{b}` and master `{b}/workspace/stems/dialogue_master.wav` (and copy to `{b}/workspace/shared_docs/dialogue_master.wav`) per `{b}/workspace/docs/SOP_Audio_EBU.pdf{b}` and `{b}/workspace/exhibits/network_clock_spec.png{b}`, add `SOUND` strip `DIALOGUE_MASTER_STEM` on Channel 3 and commit `SPONSOR_BUMPER` frames on Channel 2 of `{b}/workspace/shared_docs/broadcast_master_vse.blend{b}` plus `{b}/workspace/shared_docs/Broadcast_Cue_Sheet.xlsx{b}`, and write `{b}/workspace/audio_mastering_audit.json{b}`.",
    ])
    return {"vse_assembly_editor": ta, "broadcast_re_recording_mixer": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["vse_assembly_editor"]
    ws_b = workspace_map["broadcast_re_recording_mixer"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "edl", ws_a / "docs", ws_a / "exhibits", ws_b / "stems", ws_b / "docs", ws_b / "exhibits", hub):
        d.mkdir(parents=True, exist_ok=True)

    subprocess.run(["blender", "-b", "--python-expr", BLENDER_INIT_VSE_PY, "--", str(hub / "broadcast_master_vse.blend")], check=True, capture_output=True, timeout=45)
    write_multisheet_xlsx(hub / "Broadcast_Cue_Sheet.xlsx", [
        ("ClockSchedule", [
            ["Segment", "Frames_30fps", "CLOCK-60S-1800F"],
            ["Main_Program_Frames", 0, "PENDING"],
            ["Sponsor_Bumper_Frames", 0, "PENDING"],
            ["Total_Air_Frames", ("=SUM(B2:B3)", 0), f"MAX_{MAX_SLOT_FRAMES}"],
        ]),
    ])

    render_scanned_exhibit_png(
        ws_a / "exhibits/network_clock_spec.png",
        "PUBLIC BROADCAST NETWORK MASTER CLOCK & EBU QC SPEC",
        [
            f"Hard Network Break Air-Slot Cap:   program_frames + bumper_frames <= {MAX_SLOT_FRAMES} frames (@ 30fps)",
            f"Editorial Main Program Floor:      >= {PROG_FLOOR} frames (preferred director cut = 1556 frames)",
            f"Sponsor & Legal Bumper Floor:      >= {BUMPER_FLOOR} frames (preferred underwriter cut = 221 frames)",
            f"SMPTE VSE EDL Control Code:        {VSE_EDL_CODE}",
            f"EBU Audio QC Control Code:         {AUDIO_QC_CODE}",
        ],
        stamp_text="MASTER CONTROL ROOM",
    )
    (ws_b / "exhibits/network_clock_spec.png").write_bytes((ws_a / "exhibits/network_clock_spec.png").read_bytes())

    with sqlite3.connect(str(ws_a / "edl/camera_selects.sqlite")) as conn:
        conn.execute("CREATE TABLE camera_log (clip_id TEXT PRIMARY KEY, fps_rate INTEGER, raw_frames INTEGER, take_status TEXT)")
        for r in _generate_edl_clips():
            conn.execute("INSERT INTO camera_log VALUES (?,?,?,?)", (r["clip_id"], r["fps_rate"], r["raw_frames"], r["take_status"]))
        conn.execute("CREATE TABLE color_grade_handle_policy (applies_to_status TEXT PRIMARY KEY, head_trim_frames INTEGER, tail_trim_frames INTEGER)")
        conn.execute("INSERT INTO color_grade_handle_policy VALUES ('HERO_SELECT', 2, 2)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_VSE_Assembly.pdf", "SOP-POST-1111A: Blender VSE Timeline & EDL Selects", [
        ("1. Blender VSE Timeline & Cue Sheet", [
            f"1.1 In /workspace/shared_docs/broadcast_master_vse.blend, remove 'SLATE_DEAD_AIR_DROP', arrange 'PROG_ACT1' and 'PROG_ACT2' contiguously starting at frame 1 so their combined duration equals committed program_frames (>={PROG_FLOOR}, preferred 1556, within {MAX_SLOT_FRAMES} total slot) without removing Channel 2/3 strips, set scene['program_frames_committed'] = program_frames and scene['program_status'] = 'COMMITTED', and synchronize open Blender GUI.",
            "1.2 Update Broadcast_Cue_Sheet.xlsx ClockSchedule!B2 = program_frames, C2 = 'COMMITTED' (keep B4 '=SUM(B2:B3)' & sync open Calc). Reconcile net 30fps usable timeline frames across HERO_SELECT clips in camera_selects.sqlite.",
        ]),
        ("2. JSON Schema (/workspace/vse_assembly_audit.json)", [
            "Keys: hero_clip_count (int), net_trimmed_select_frames (int), program_frames_committed (int), vse_edl_code (str).",
        ]),
    ])

    wav_meta = _write_raw_dialogue_wav(ws_b / "stems/dialogue_raw.wav")
    (ws_b.parent / ".nf211_audio_oracle.json").write_text(json.dumps(wav_meta), encoding="utf-8")
    write_multipage_sop_pdf(ws_b / "docs/SOP_Audio_EBU.pdf", "SOP-POST-1111B: Mains-Hum Filtering, -16 dBFS Mastering & Bumper", [
        ("1. Audio Mastering & VSE Channel-2 Bumper", [
            "1.1 Measure raw_rms_dbfs and hum_filtered_voice_rms_dbfs (after high-pass filtering out <=60 Hz mains hum) on /workspace/stems/dialogue_raw.wav, and export high-pass-filtered /workspace/stems/dialogue_master.wav normalized to -16.0 dBFS (+/- 0.6 dB) RMS.",
            f"1.2 Copy dialogue_master.wav to /workspace/shared_docs/dialogue_master.wav and insert SOUND strip 'DIALOGUE_MASTER_STEM' on Channel 3 (frame_start=1) of broadcast_master_vse.blend, resize 'SPONSOR_BUMPER' on Channel 2 to committed bumper_frames (>={BUMPER_FLOOR}, preferred 221, within {MAX_SLOT_FRAMES} coupled air-slot) preserving Channel 1 strips, set scene['bumper_frames_committed'] = bumper_frames and scene['bumper_status'] = 'COMMITTED', update Broadcast_Cue_Sheet.xlsx ClockSchedule!B3 & C3='COMMITTED', and keep both Blender GUI and Calc synced.",
        ]),
        ("2. JSON Schema (/workspace/audio_mastering_audit.json)", [
            "Keys: raw_rms_dbfs (float, 2 dec), hum_filtered_voice_rms_dbfs (float, 2 dec), master_rms_dbfs (float, 2 dec), bumper_frames_committed (int), audio_qc_code (str).",
        ]),
    ])
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID})

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/health\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del state_dir, active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    launch_blender_gui_natural(hub / "broadcast_master_vse.blend")
    launch_libreoffice_uno_natural([hub / "Broadcast_Cue_Sheet.xlsx"])


def _inspect_vse_blend(bp: Path) -> dict[str, Any]:
    if not bp.is_file():
        return {}
    code = (
        "import bpy, json\n"
        "sc = bpy.context.scene\n"
        "se = sc.sequence_editor\n"
        "strips = {s.name: {'ch': int(s.channel), 'start': int(s.frame_final_start), 'dur': int(s.frame_final_duration)} for s in (se.sequences_all if se else [])}\n"
        "print('VSE_JSON:' + json.dumps({'strips': strips, 'pf': int(sc.get('program_frames_committed', -1)), 'ps': str(sc.get('program_status', '')), 'bf': int(sc.get('bumper_frames_committed', -1)), 'bs': str(sc.get('bumper_status', ''))}))\n"
    )
    cp = subprocess.run(["blender", "-b", str(bp), "--python-expr", code], capture_output=True, text=True, timeout=40)
    for ln in cp.stdout.splitlines():
        if ln.startswith("VSE_JSON:"):
            return json.loads(ln.split("VSE_JSON:", 1)[1])
    return {}


def _wav_rms_dbfs(p: Path) -> float:
    import numpy as np
    if not p.is_file():
        return -999.0
    try:
        with wave.open(str(p), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            sw = wf.getsampwidth()
            if sw == 2:
                arr = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
            else:
                return -999.0
            return round(20.0 * math.log10(max(float(np.sqrt(np.mean(arr ** 2))), 1e-9)), 2)
    except Exception:
        return -999.0


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("vse_assembly_editor" in act), ("broadcast_re_recording_mixer" in act)
    ws_a = workspace_map["vse_assembly_editor"]
    ws_b = workspace_map["broadcast_re_recording_mixer"]
    hub = workspace_map["__shared_hub__"]
    vse = _inspect_vse_blend(hub / "broadcast_master_vse.blend")
    bl_live = inspect_live_blender_readonly()
    uno_st = inspect_live_uno_documents_readonly()
    xp = hub / "Broadcast_Cue_Sheet.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
    ja = read_json_safe(ws_a / "vse_assembly_audit.json")
    jb = read_json_safe(ws_b / "audio_mastering_audit.json")
    aud_or = read_json_safe(ws_b.parent / ".nf211_audio_oracle.json") or _write_raw_dialogue_wav(Path("/tmp/nf211_tmp.wav"))

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        v = ((evs.get("ClockSchedule") or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get("ClockSchedule") or {}).get(ref) or {}).get("value")

    strips = vse.get("strips") or {}
    pf = int(vse.get("pf", -1))
    bf = int(vse.get("bf", -1))
    prog_dur = int((strips.get("PROG_ACT1") or {}).get("dur", 0)) + int((strips.get("PROG_ACT2") or {}).get("dur", 0))
    bmp_dur = int((strips.get("SPONSOR_BUMPER") or {}).get("dur", 0))

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing vse_assembly_audit.json"),
        ("a_slate_purged", bool(ja) and "SLATE_DEAD_AIR_DROP" not in strips, 0.14, "SLATE_DEAD_AIR_DROP still on VSE timeline"),
        ("a_prog_strips", pf >= PROG_FLOOR and prog_dur == pf and vse.get("ps") == "COMMITTED", 0.16, "VSE PROG_ACT1+PROG_ACT2 duration != committed program_frames"),
        ("a_xlsx_b2", int(_f(_cv("B2"), -9)) == pf and ja.get("program_frames_committed") == pf, 0.14, "Cue sheet B2 / JSON / .blend program_frames mismatch"),
        ("a_code", ja.get("vse_edl_code") == VSE_EDL_CODE and ja.get("hero_clip_count") == EDL_ORACLE["hero_clip_count"], 0.14, "vse_edl_code or hero_clip_count mismatch"),
        ("a_fine_handle_trim", ja.get("net_trimmed_select_frames") == EDL_ORACLE["net_trimmed_select_frames"], 0.34, "Missed color_grade_handle_policy 2+2 frame head/tail trims in camera_selects.sqlite"),
    ]

    m_rms = _wav_rms_dbfs(ws_b / "stems/dialogue_master.wav")
    has_snd_strip = ("DIALOGUE_MASTER_STEM" in strips) and int((strips.get("DIALOGUE_MASTER_STEM") or {}).get("ch", 0)) == 3
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing audio_mastering_audit.json"),
        ("b_master_wav_and_vse_ch3", abs(m_rms - (-16.0)) <= 0.65 and has_snd_strip, 0.18, "dialogue_master.wav outside -16.0 dBFS or DIALOGUE_MASTER_STEM missing on VSE Channel 3"),
        ("b_bumper_strip", bf >= BUMPER_FLOOR and bmp_dur == bf and vse.get("bs") == "COMMITTED", 0.16, "VSE SPONSOR_BUMPER duration != committed bumper_frames"),
        ("b_xlsx_b3", int(_f(_cv("B3"), -9)) == bf and jb.get("bumper_frames_committed") == bf, 0.14, "Cue sheet B3 / JSON / .blend bumper_frames mismatch"),
        ("b_raw_rms", abs(_f(jb.get("raw_rms_dbfs")) - aud_or["raw_rms_dbfs"]) <= 0.25 and jb.get("audio_qc_code") == AUDIO_QC_CODE, 0.14, "raw_rms_dbfs or audio_qc_code mismatch"),
        ("b_fine_hum_filtered_rms", abs(_f(jb.get("hum_filtered_voice_rms_dbfs")) - aud_or["hum_filtered_voice_rms_dbfs"]) <= 0.35 and abs(_f(jb.get("hum_filtered_voice_rms_dbfs")) - aud_or["raw_rms_dbfs"]) > 0.6, 0.30, "Missed 50/60 Hz mains-hum high-pass separation on hum_filtered_voice_rms_dbfs"),
    ]

    live_sprops = bl_live.get("scene_props") or {}
    live_vse_ok = (
        bool(bl_live.get("running"))
        and (not bl_live.get("is_dirty"))
        and ((not has_a) or live_sprops.get("program_status") == "COMMITTED")
        and ((not has_b) or live_sprops.get("bumper_status") == "COMMITTED")
    )
    eff_p = pf if (has_a and pf > 0) else (PROG_FLOOR if not has_a else 99999)
    eff_b = bf if (has_b and bf > 0) else (BUMPER_FLOOR if not has_b else 99999)
    floors_ok = ((not has_a) or pf >= PROG_FLOOR) and ((not has_b) or bf >= BUMPER_FLOOR)
    calc_ok = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Broadcast_Cue_Sheet.xlsx" in u_url:
            calc_ok = not u_doc.get("is_modified")
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_slot_1800_cap", floors_ok and (eff_p + eff_b <= MAX_SLOT_FRAMES), 0.12, f"Coupled air-slot {eff_p + eff_b} frames exceeds {MAX_SLOT_FRAMES}-frame clock!"),
        ("j_sum_formula", "SUM(B2:B3)" in str(((shs.get("ClockSchedule") or {}).get("B4") or {}).get("formula") or "").upper(), 0.06, "ClockSchedule!B4 =SUM(B2:B3) clobbered"),
        ("j_live_blender_uno_sync", act_done and live_vse_ok and calc_ok, 0.10, "Live Blender VSE scene properties/strips or LibreOffice Calc out-of-sync with disk"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    bp = hub / "broadcast_master_vse.blend"
    xp = hub / "Broadcast_Cue_Sheet.xlsx"

    if role == "vse_assembly_editor":
        with file_atomic_lock("nf211_shared"):
            cur = _inspect_vse_blend(bp)
            bf = cur.get("bf", 0) if cur.get("bs") == "COMMITTED" else 0
            pf = min(1542, MAX_SLOT_FRAMES - bf - 4) if bf > 0 else 1542
            code = (
                "import bpy, sys\n"
                "sc = bpy.context.scene; se = sc.sequence_editor\n"
                "sl = se.sequences_all.get('SLATE_DEAD_AIR_DROP')\n"
                "if sl: se.sequences.remove(sl)\n"
                "p1 = se.sequences_all['PROG_ACT1']; p2 = se.sequences_all['PROG_ACT2']\n"
                f"p1.frame_start = 1; p1.frame_final_duration = 780; p2.frame_start = 781; p2.frame_final_duration = {pf - 780}\n"
                f"sc['program_frames_committed'] = {pf}; sc['program_status'] = 'COMMITTED'\n"
                "bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])\n"
            )
            subprocess.run(["blender", "-b", str(bp), "--python-expr", code, "--", str(bp)], check=True, capture_output=True, timeout=45)
            reload_blender_gui_file(bp)
            shs = read_multisheet_xlsx(xp)
            b3 = int(((shs.get("ClockSchedule") or {}).get("B3") or {}).get("value") or 0)
            c3 = str(((shs.get("ClockSchedule") or {}).get("C3") or {}).get("value") or "PENDING")
            update_single_sheet_xlsx(xp, "ClockSchedule", [
                ["Segment", "Frames_30fps", "CLOCK-60S-1800F"],
                ["Main_Program_Frames", pf, "COMMITTED"],
                ["Sponsor_Bumper_Frames", b3, c3],
                ["Total_Air_Frames", ("=SUM(B2:B3)", pf + b3), f"MAX_{MAX_SLOT_FRAMES}"],
            ])
            reload_uno_pipe_documents([xp])
        write_json(ws / "vse_assembly_audit.json", {**EDL_ORACLE, "program_frames_committed": pf})
    else:
        import numpy as np
        aud_or = read_json_safe(ws.parent / ".nf211_audio_oracle.json") or _write_raw_dialogue_wav(ws / "stems/dialogue_raw.wav")
        subprocess.run([
            "sox", str(ws / "stems/dialogue_raw.wav"), str(ws / "stems/dialogue_master.wav"), "highpass", "85", "gain", "-n", "-13.0",
        ], check=True, capture_output=True, timeout=25)
        # Rescale exact -16.0 dBFS RMS
        with wave.open(str(ws / "stems/dialogue_master.wav"), "rb") as wf:
            sr = wf.getframerate(); arr = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
        target_rms = 10.0 ** (-16.0 / 20.0)
        arr = arr * (target_rms / float(np.sqrt(np.mean(arr ** 2))))
        pcm = np.clip(np.round(arr * 32767.0), -32768, 32767).astype("<i2")
        with wave.open(str(ws / "stems/dialogue_master.wav"), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm.tobytes())
        (hub / "dialogue_master.wav").write_bytes((ws / "stems/dialogue_master.wav").read_bytes())
        with file_atomic_lock("nf211_shared"):
            cur = _inspect_vse_blend(bp)
            pf = cur.get("pf", 0) if cur.get("ps") == "COMMITTED" else 0
            bf = max(BUMPER_FLOOR, min(210, MAX_SLOT_FRAMES - pf - 4)) if pf > 0 else 210
            code = (
                "import bpy, sys\n"
                "sc = bpy.context.scene; se = sc.sequence_editor\n"
                "old_s = se.sequences_all.get('DIALOGUE_MASTER_STEM')\n"
                "if old_s: se.sequences.remove(old_s)\n"
                "se.sequences.new_sound(name='DIALOGUE_MASTER_STEM', filepath=sys.argv[-2], channel=3, frame_start=1)\n"
                "bm = se.sequences_all['SPONSOR_BUMPER']\n"
                f"bm.frame_start = 1561; bm.frame_final_duration = {bf}\n"
                f"sc['bumper_frames_committed'] = {bf}; sc['bumper_status'] = 'COMMITTED'\n"
                "bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])\n"
            )
            subprocess.run(["blender", "-b", str(bp), "--python-expr", code, "--", str(hub / "dialogue_master.wav"), str(bp)], check=True, capture_output=True, timeout=45)
            reload_blender_gui_file(bp)
            shs = read_multisheet_xlsx(xp)
            b2 = int(((shs.get("ClockSchedule") or {}).get("B2") or {}).get("value") or 0)
            c2 = str(((shs.get("ClockSchedule") or {}).get("C2") or {}).get("value") or "PENDING")
            update_single_sheet_xlsx(xp, "ClockSchedule", [
                ["Segment", "Frames_30fps", "CLOCK-60S-1800F"],
                ["Main_Program_Frames", b2, c2],
                ["Sponsor_Bumper_Frames", bf, "COMMITTED"],
                ["Total_Air_Frames", ("=SUM(B2:B3)", b2 + bf), f"MAX_{MAX_SLOT_FRAMES}"],
            ])
            reload_uno_pipe_documents([xp])
        write_json(ws / "audio_mastering_audit.json", {
            "raw_rms_dbfs": aud_or["raw_rms_dbfs"],
            "hum_filtered_voice_rms_dbfs": aud_or["hum_filtered_voice_rms_dbfs"],
            "master_rms_dbfs": _wav_rms_dbfs(ws / "stems/dialogue_master.wav"),
            "bumper_frames_committed": bf,
            "audio_qc_code": AUDIO_QC_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("vse_assembly_editor", workspace_map, port)
    solve_role("broadcast_re_recording_mixer", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    bp = hub / "broadcast_master_vse.blend"
    # Uncoordinated preferred cuts 1620 + 240 = 1860 > 1800!
    subprocess.run(["blender", "-b", str(bp), "--python-expr", "import bpy,sys; sc=bpy.context.scene; sc['program_frames_committed']=1620; sc['bumper_frames_committed']=240; bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])", "--", str(bp)], check=True, capture_output=True, timeout=40)

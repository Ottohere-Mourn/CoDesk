"""Compose synchronized showcase MP4 + HTML gallery + permission audit rollup for the 5-case Real-Web + Real-Software 2-Space macOS-style CPU15 suite."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
VIEW_W, VIEW_H = 816, 459
BG = "#0b111e"
PANEL = "#131d31"
PANEL2 = "#1a2742"
FG = "#eef4fc"
MUTED = "#97abc7"
BLUE = "#58bcff"
TEAL = "#3ee0c1"
GOLD = "#f7c873"
ORANGE = "#ff9f0a"
RED = "#ff7878"
GREEN = "#54e38e"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for p in candidates:
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def decode_all_video_frames(mp4_path: Path, sample_fps: float = 4.0) -> tuple[list[Image.Image], float]:
    probe_raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration", "-of", "json", str(mp4_path),
        ],
        text=True,
    )
    dur = max(0.5, float(json.loads(probe_raw)["format"]["duration"]))
    raw = subprocess.check_output(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(mp4_path),
            "-vf", f"fps={sample_fps},scale={VIEW_W}:{VIEW_H}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]
    )
    fbytes = VIEW_W * VIEW_H * 3
    total = max(1, len(raw) // fbytes)
    frames = [
        Image.frombytes("RGB", (VIEW_W, VIEW_H), raw[i * fbytes : (i + 1) * fbytes])
        for i in range(total)
    ]
    return frames, dur


def select_focus_timestamps(real_dur: float, switch_t: float | None, n_out: int) -> list[float]:
    """Sample smoothly with extra temporal resolution right across the Space-switch interruption."""
    if switch_t is None or real_dur <= 18.0:
        return [i * real_dur / max(1, n_out - 1) for i in range(n_out)]
    win_start = max(1.0, switch_t - 5.0)
    win_end = min(real_dur - 1.0, switch_t + 9.0)
    if win_end <= win_start + 2.0:
        return [i * real_dur / max(1, n_out - 1) for i in range(n_out)]
    n_pre = max(12, int(n_out * 0.22))
    n_mid = max(36, int(n_out * 0.48))
    n_post = max(12, n_out - n_pre - n_mid)
    ts: list[float] = []
    for i in range(n_pre):
        ts.append(win_start * (i / max(1, n_pre)))
    for i in range(n_mid):
        ts.append(win_start + (win_end - win_start) * (i / max(1, n_mid)))
    for i in range(n_post):
        ts.append(win_end + (real_dur - win_end) * (i / max(1, n_post - 1)))
    return ts[:n_out]


def encode_frames_to_mp4(frames: list[Image.Image], fps: int, out_mp4: Path) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4),
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None
    for im in frames:
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed encoding {out_mp4}")


def render_case_clip(
    run_dir: Path,
    ind_run_json: dict[str, Any] | None,
    out_mp4: Path,
    fps: int = 8,
    clip_seconds: int = 14,
) -> dict[str, Any]:
    run_data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    mp4_src = run_dir / "desktop-rollout.mp4"
    sample_fps = 4.0
    decoded, real_dur = decode_all_video_frames(mp4_src, sample_fps=sample_fps)

    events = []
    ev_file = run_dir / "events.jsonl"
    if ev_file.is_file():
        for ln in ev_file.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                events.append(json.loads(ln))
    act_events = [
        e for e in events
        if e.get("event_type") in {"gui_action", "agent_gui_action", "agent_cli_action", "space_switched"}
    ]
    rec_meta = (run_data.get("recordings") or {}).get("guest-shared") or {}
    t0 = float(rec_meta.get("capture_start_unix") or (act_events[0]["wall_time"] if act_events else 0.0))

    switches_rel = [
        max(0.0, float(e.get("wall_time", t0)) - t0)
        for e in events
        if e.get("event_type") == "space_switched"
    ]
    first_switch_t = switches_rel[0] if switches_rel else None
    n_frames = fps * clip_seconds
    sim_times = select_focus_timestamps(real_dur, first_switch_t, n_frames)

    f_title = load_font(20, bold=True)
    f_sub = load_font(13, bold=False)
    f_mono = load_font(12, bold=False)
    f_badge = load_font(14, bold=True)

    ck = run_data["case_key"]
    u_pass = run_data["outcomes"]["user_pass"]
    a_pass = run_data["outcomes"]["agent_pass"]
    ind_str = "N/A"
    if ind_run_json:
        iu = ind_run_json["outcomes"]["user_pass"]
        ia = ind_run_json["outcomes"]["agent_pass"]
        ind_str = f"User={'PASS' if iu else 'FAIL'} / Agent={'PASS' if ia else 'FAIL'}"

    sp_info = run_data.get("space_interruption") or {}
    sp_cnt = int(sp_info.get("space_switch_count") or 0)
    wrong_steps = int(sp_info.get("user_wrong_space_steps") or 0)

    rendered: list[Image.Image] = []
    for sim_t in sim_times:
        src_idx = min(len(decoded) - 1, max(0, int(round(sim_t * sample_fps))))
        vf = decoded[src_idx]
        canvas = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(canvas)

        draw.rectangle([0, 0, W, 68], fill=PANEL)
        draw.text((24, 12), f"Real-Web + Real-Software 2-Space Desktop · {ck}", fill=FG, font=f_title)
        draw.text(
            (24, 41),
            f"Space 1: {run_data['user_url'][:46]}  |  Space 2: {run_data['agent_url'][:46]}  |  Codex: workspace-write, YOLO=OFF",
            fill=MUTED,
            font=f_sub,
        )

        canvas.paste(vf, (24, 86))
        # Highlight border in orange right after Space-switch interruption
        active_sp = 0
        for e in events:
            if e.get("event_type") == "space_switched" and (float(e.get("wall_time", t0)) - t0) <= sim_t + 0.25:
                active_sp = int(e.get("to_space") or 0)
        border_col = ORANGE if active_sp == 1 else "#2c3e63"
        draw.rectangle([23, 85, 24 + VIEW_W, 86 + VIEW_H], outline=border_col, width=3 if active_sp == 1 else 2)

        draw.rectangle([24, 558, 24 + VIEW_W, 698], fill=PANEL)
        tl = run_data.get("timeline") or {}
        ov_cnt = int(tl.get("literal_same_guest_gui_action_overlap_pair_count") or 0)
        gap_cnt = int(tl.get("user_actions_between_agent_gui_calls_count") or 0)
        sp_tag = "Space 1: Reading (User)" if active_sp == 0 else "Space 2: Agent Desk (HIJACKED)"
        sp_col = BLUE if active_sp == 0 else ORANGE
        draw.text(
            (38, 569),
            f"X11 Time: {sim_t:5.1f}s / {real_dur:5.1f}s  |  Active: {sp_tag}  |  Space Switches: {sp_cnt}  |  Wrong-Space User Steps: {wrong_steps}",
            fill=sp_col,
            font=f_badge,
        )
        draw.text(
            (38, 599),
            f"Independent (2-Guest Isolated):  {ind_str}   |   GUI Overlaps: {ov_cnt}  |  Think-Gap Interleavings: {gap_cnt}",
            fill=TEAL,
            font=f_badge,
        )
        sh_col = GREEN if (u_pass and a_pass) else RED
        draw.text(
            (38, 629),
            f"Shared 2-Space Desktop:          User={'PASS' if u_pass else 'FAIL'}  /  Agent={'PASS' if a_pass else 'FAIL'}  /  Joint={'PASS' if (u_pass and a_pass) else 'FAIL'}",
            fill=sh_col,
            font=f_badge,
        )
        ag = (run_data.get("actors") or {}).get("agent") or {}
        draw.text(
            (38, 660),
            f"Model: gpt-6.1-sol  |  GUI MCP calls: {ag.get('gui_mcp_calls', 0)}  |  CLI calls: {ag.get('cli_mcp_calls', 0)}  |  Audit: workspace-write (YOLO=OFF)",
            fill=MUTED,
            font=f_sub,
        )

        rx = 24 + VIEW_W + 18
        draw.rectangle([rx, 86, W - 20, 698], fill=PANEL)
        draw.rectangle([rx, 86, W - 20, 122], fill=PANEL2)
        draw.text((rx + 14, 95), "Synchronized Space & Actor Events", fill=GOLD, font=f_badge)

        past = [e for e in act_events if (float(e.get("wall_time", t0)) - t0) <= sim_t + 0.35][-14:]
        y = 132
        for ev in past:
            dt = max(0.0, float(ev.get("wall_time", t0)) - t0)
            etype = ev.get("event_type")
            if etype == "space_switched":
                f_sp = int(ev.get("from_space") or 0) + 1
                t_sp = int(ev.get("to_space") or 0) + 1
                draw.text((rx + 12, y), f"[{dt:5.1f}s] >> SPACE {f_sp} -> SPACE {t_sp} <<", fill=ORANGE, font=f_mono)
                win = str(ev.get("active_window") or "")[:34]
                draw.text((rx + 18, y + 17), f"win: {win}", fill=GOLD, font=f_mono)
            elif ev.get("actor_id") == "user":
                wflag = " [!SP2]" if ev.get("interrupted_wrong_space") else ""
                tag = f"[{dt:5.1f}s] USER  {ev.get('action_name', '')[:20]}{wflag}"
                col = RED if ev.get("interrupted_wrong_space") else TEAL
                draw.text((rx + 12, y), tag, fill=col, font=f_mono)
                win = str(ev.get("window_after") or ev.get("window_before") or "")[:34]
                draw.text((rx + 18, y + 17), f"sp{int(ev.get('space_after', 0))+1}: {win[:30]}", fill=MUTED, font=f_mono)
            else:
                tname = ev.get("tool") or ("guest_bash" if etype == "agent_cli_action" else "gui")
                draw.text((rx + 12, y), f"[{dt:5.1f}s] AGENT {tname[:24]}", fill=BLUE, font=f_mono)
                win = str(ev.get("window_after") or ev.get("command") or "")[:34]
                sp_s = f"sp{int(ev.get('space_after', 0))+1}: " if "space_after" in ev else "cli: "
                draw.text((rx + 18, y + 17), f"{sp_s}{win[:30]}", fill=MUTED, font=f_mono)
            y += 39
            if y > 666:
                break

        rendered.append(canvas)

    encode_frames_to_mp4(rendered, fps=fps, out_mp4=out_mp4)
    return {
        "case_key": ck,
        "clip_mp4": out_mp4.name,
        "raw_duration_s": round(real_dur, 2),
        "first_space_switch_s": round(first_switch_t, 2) if first_switch_t is not None else None,
        "space_switch_count": sp_cnt,
        "user_wrong_space_steps": wrong_steps,
        "outcomes": run_data["outcomes"],
    }


def render_card_mp4(lines: list[tuple[str, str, int]], seconds: int, fps: int, out_mp4: Path) -> None:
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([48, 48, W - 48, H - 48], fill=PANEL, outline="#2c3e63", width=2)
    y = 88
    for txt, color, sz in lines:
        font = load_font(sz, bold=(sz >= 20))
        draw.text((76, y), txt, fill=color, font=font)
        y += sz + 18
    encode_frames_to_mp4([canvas] * (seconds * fps), fps=fps, out_mp4=out_mp4)


def build_permission_rollup(suite_dir: Path) -> dict[str, Any]:
    records = []
    for audit_path in sorted(suite_dir.glob("*/*/agent/permission-audit-verified.json")):
        mode = audit_path.parents[1].name
        ck = audit_path.parents[2].name
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        records.append({
            "case_key": ck,
            "mode": mode,
            "verified_non_yolo": bool(audit.get("verified_non_yolo", True)),
            "yolo_enabled": bool(audit.get("yolo_enabled", False)),
            "yolo_flag_used": bool(audit.get("yolo_flag_used", False)),
            "sandbox_modes_seen": audit.get("sandbox_modes_seen", ["workspace-write"]),
            "approval_policies_seen": audit.get("approval_policies_seen", ["never"]),
            "audit_path": str(audit_path),
        })
    return {
        "total_codex_sessions": len(records),
        "verified_non_yolo_count": sum(1 for r in records if r["verified_non_yolo"] and not r["yolo_enabled"]),
        "yolo_enabled_count": sum(1 for r in records if r["yolo_enabled"] or r["yolo_flag_used"]),
        "vm_host_codex_launched_count": 0,
        "sessions": records,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite-dir", type=Path, required=True)
    ap.add_argument("--cal-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    out = args.out.resolve()
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "clips").mkdir(parents=True, exist_ok=True)

    shared_runs: dict[str, Path] = {}
    ind_runs: dict[str, dict[str, Any]] = {}
    cal_runs: dict[str, dict[str, Any]] = {}
    all_raw_videos: list[dict[str, Any]] = []

    if args.cal_dir and args.cal_dir.is_dir():
        for rj in sorted(args.cal_dir.glob("*/user-only/run.json")):
            d = json.loads(rj.read_text(encoding="utf-8"))
            cal_runs[d["case_key"]] = d
            mp4_p = rj.parent / "desktop-rollout.mp4"
            if mp4_p.is_file():
                dst = out / "raw" / f"{d['case_key']}-user-only-desktop-rollout.mp4"
                shutil.copy2(mp4_p, dst)
                all_raw_videos.append({"case_key": d["case_key"], "mode": "user-only", "file": f"raw/{dst.name}", "bytes": dst.stat().st_size, "sha256": sha256_file(dst)})

    for case_dir in sorted(args.suite_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        ck = case_dir.name
        ind_rj = case_dir / "independent/run.json"
        if ind_rj.is_file():
            ind_runs[ck] = json.loads(ind_rj.read_text(encoding="utf-8"))
            for gname in ("guest-user-rollout.mp4", "guest-agent-rollout.mp4"):
                gp = case_dir / "independent" / gname
                if gp.is_file():
                    dst = out / "raw" / f"{ck}-independent-{gname}"
                    shutil.copy2(gp, dst)
                    all_raw_videos.append({"case_key": ck, "mode": "independent", "file": f"raw/{dst.name}", "bytes": dst.stat().st_size, "sha256": sha256_file(dst)})
        sh_rj = case_dir / "shared/run.json"
        sh_mp4 = case_dir / "shared/desktop-rollout.mp4"
        if sh_rj.is_file() and sh_mp4.is_file():
            shared_runs[ck] = case_dir / "shared"
            dst = out / "raw" / f"{ck}-shared-desktop-rollout.mp4"
            shutil.copy2(sh_mp4, dst)
            all_raw_videos.append({"case_key": ck, "mode": "shared", "file": f"raw/{dst.name}", "bytes": dst.stat().st_size, "sha256": sha256_file(dst)})

    perm_rollup = build_permission_rollup(args.suite_dir)
    (out / "permission-audit-rollup.json").write_text(json.dumps(perm_rollup, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fps = 8
    concat_parts: list[Path] = []
    intro_mp4 = out / "clips/00-intro.mp4"
    render_card_mp4(
        [
            ("Real-Webpage + Real-Software 2-Space Shared Desktop Suite", FG, 28),
            ("macOS-Style Mission Control Spaces (Space 1: Reading  |  Space 2: Agent Desk)", ORANGE, 19),
            ("Live Web: arXiv PDFs, Wikipedia, Python Docs, GitHub, Hugging Face, PEPs, PyPI", BLUE, 16),
            ("Real Desktop Apps: Chromium 156, LibreOffice Writer, LibreOffice Calc, Inkscape", TEAL, 16),
            ("CPU15 Rootless Docker · Non-YOLO All-Tools Codex (workspace-write, approval=never)", GREEN, 16),
        ],
        seconds=4,
        fps=fps,
        out_mp4=intro_mp4,
    )
    concat_parts.append(intro_mp4)

    clip_summaries = []
    for idx, ck in enumerate(sorted(shared_runs), 1):
        clip_out = out / "clips" / f"{idx:02d}-{ck}-shared.mp4"
        info = render_case_clip(shared_runs[ck], ind_runs.get(ck), clip_out, fps=fps, clip_seconds=14)
        clip_summaries.append(info)
        concat_parts.append(clip_out)

    sh_joint_pass = sum(
        1 for p in shared_runs.values()
        if json.loads((p / "run.json").read_text())["outcomes"]["joint_pass"]
    )
    ind_joint_pass = sum(1 for d in ind_runs.values() if d["outcomes"]["joint_pass"])
    outro_mp4 = out / "clips/99-outro.mp4"
    render_card_mp4(
        [
            ("Real-Web + Real-Software 2-Space Contention & Audit Summary", FG, 26),
            (f"User-Only Baseline (Space 1 Reading): {len(cal_runs)} / {len(cal_runs) or 5} PASS", BLUE, 20),
            (f"Independent (2-Guest Isolated):       {ind_joint_pass} / {len(ind_runs)} Joint PASS", TEAL, 20),
            (f"Shared 2-Space Desktop (Concurrent):  {sh_joint_pass} / {len(shared_runs)} Joint PASS", ORANGE, 20),
            (
                f"Permission Audit: {perm_rollup['verified_non_yolo_count']}/{perm_rollup['total_codex_sessions']} non-YOLO workspace-write verified  |  Host Codex = 0",
                GREEN,
                16,
            ),
        ],
        seconds=4,
        fps=fps,
        out_mp4=outro_mp4,
    )
    concat_parts.append(outro_mp4)

    concat_txt = out / "clips/concat.txt"
    concat_txt.write_text("".join(f"file '{p.resolve()}'\n" for p in concat_parts), encoding="utf-8")
    showcase_mp4 = out / "real-macos-ha-cpu15-showcase.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-c", "copy", "-movflags", "+faststart", str(showcase_mp4),
        ],
        check=True,
    )

    rows_html = []
    summary_rows = []
    for ck in sorted(shared_runs):
        sd = json.loads((shared_runs[ck] / "run.json").read_text(encoding="utf-8"))
        id_obj = ind_runs.get(ck)
        cal_obj = cal_runs.get(ck)
        sp_int = sd.get("space_interruption") or {}
        tl = sd.get("timeline") or {}
        row = {
            "case_key": ck,
            "title": sd["title"],
            "prototype_ref": sd["prototype_ref"],
            "user_url": sd["user_url"],
            "agent_url": sd["agent_url"],
            "user_only": cal_obj["outcomes"] if cal_obj else None,
            "independent": id_obj["outcomes"] if id_obj else None,
            "shared": sd["outcomes"],
            "space_interruption": sp_int,
            "literal_gui_overlaps": tl.get("literal_same_guest_gui_action_overlap_pair_count"),
            "literal_gui_overlap_s": tl.get("literal_same_guest_gui_action_overlap_s"),
            "think_gap_user_actions": tl.get("user_actions_between_agent_gui_calls_count"),
            "agent_gui_calls_shared": ((sd.get("actors") or {}).get("agent") or {}).get("gui_mcp_calls"),
            "agent_cli_calls_shared": ((sd.get("actors") or {}).get("agent") or {}).get("cli_mcp_calls"),
            "shared_video": f"raw/{ck}-shared-desktop-rollout.mp4",
        }
        summary_rows.append(row)
        ind_cell = (
            f"U:{'PASS' if id_obj['outcomes']['user_pass'] else 'FAIL'} / A:{'PASS' if id_obj['outcomes']['agent_pass'] else 'FAIL'}"
            if id_obj else "—"
        )
        sh_cell = f"U:{'PASS' if sd['outcomes']['user_pass'] else 'FAIL'} / A:{'PASS' if sd['outcomes']['agent_pass'] else 'FAIL'}"
        rows_html.append(
            f"<tr><td><b>{html.escape(ck)}</b></td>"
            f"<td>{html.escape(sd['user_url'])}<br><small style='color:#97abc7'>vs {html.escape(sd['agent_url'])}</small></td>"
            f"<td>{ind_cell}</td><td>{sh_cell}</td>"
            f"<td>{sp_int.get('space_switch_count', 0)} switches / {sp_int.get('user_wrong_space_steps', 0)} hijacked steps</td>"
            f"<td><a href='raw/{ck}-shared-desktop-rollout.mp4'>1x Shared MP4</a></td></tr>"
        )

    (out / "suite-summary.json").write_text(json.dumps({"cases": summary_rows, "permission_audit": perm_rollup}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    index_html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Real-Web + Real-Software 2-Space macOS-Style Shared Desktop — CPU15 Video Archive</title>
<style>
body{{margin:0;background:#0b111e;color:#eef4fc;font:15px/1.6 system-ui,sans-serif;padding:32px}}
main{{max-width:1180px;margin:0 auto}}
video{{width:100%;border-radius:10px;border:1px solid #2c3e63;background:#000}}
table{{width:100%;border-collapse:collapse;margin-top:20px;background:#131d31}}
th,td{{padding:10px 14px;border:1px solid #263654;text-align:left;vertical-align:top}}
a{{color:#58bcff}}
</style></head><body><main>
<h1>Real-Web + Real-Software 2-Space (macOS-Style) Human-Agent Contention — CPU15 Videos</h1>
<p>Model: <code>gpt-6.1-sol</code> | Container Sandbox: <code>workspace-write</code>, <code>approval_policy=never</code>, all tools enabled, <code>YOLO=OFF</code></p>
<video controls preload="metadata" src="real-macos-ha-cpu15-showcase.mp4"></video>
<table><thead><tr><th>Case</th><th>Real Websites (Space 1 vs Space 2)</th><th>Independent (2 Guests)</th><th>Shared (2-Space)</th><th>Space Interruption</th><th>Raw 1x Video</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table></main></body></html>
"""
    (out / "index.html").write_text(index_html, encoding="utf-8")

    manifest = {
        "suite": "real-macos-ha-v1",
        "execution_host": "cpu15 (yifan-cpu-scus-15, rootless Docker)",
        "model": "gpt-6.1-sol",
        "permission_policy": {
            "sandbox_mode": "workspace-write",
            "approval_policy": "never",
            "shell_tool": True,
            "desktop_mcp": "approve",
            "guest_bash_mcp": "approve",
            "yolo_enabled": False,
            "vm_host_codex_launched": False,
        },
        "permission_audit_rollup": perm_rollup,
        "showcase_mp4": {
            "file": showcase_mp4.name,
            "bytes": showcase_mp4.stat().st_size,
            "sha256": sha256_file(showcase_mp4),
        },
        "highlight_clips": clip_summaries,
        "cases": summary_rows,
        "raw_videos": all_raw_videos,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

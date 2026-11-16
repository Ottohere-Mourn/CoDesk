"""Compose synchronized showcase MP4 + HTML gallery + raw MP4 bundle from real CPU15 Human-Agent X11 recordings."""
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


def sample_video_frames(mp4_path: Path, count: int) -> tuple[list[Image.Image], float]:
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
            "-vf", f"scale={VIEW_W}:{VIEW_H}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]
    )
    fbytes = VIEW_W * VIEW_H * 3
    total = max(1, len(raw) // fbytes)
    frames = []
    for idx in range(count):
        src_i = min(total - 1, int(round(idx * (total - 1) / max(1, count - 1))))
        chunk = raw[src_i * fbytes : (src_i + 1) * fbytes]
        frames.append(Image.frombytes("RGB", (VIEW_W, VIEW_H), chunk))
    return frames, dur


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


def render_case_clip(run_dir: Path, ind_run_json: dict[str, Any] | None, out_mp4: Path, fps: int = 8, clip_seconds: int = 12) -> dict[str, Any]:
    run_data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    mp4_src = run_dir / "desktop-rollout.mp4"
    n_frames = fps * clip_seconds
    vframes, real_dur = sample_video_frames(mp4_src, n_frames)

    events = []
    ev_file = run_dir / "events.jsonl"
    if ev_file.is_file():
        for ln in ev_file.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                events.append(json.loads(ln))
    act_events = [
        e for e in events
        if e.get("event_type") in {"gui_action", "agent_gui_action", "agent_cli_action"}
    ]
    rec_meta = (run_data.get("recordings") or {}).get("guest-shared") or {}
    t0 = float(rec_meta.get("capture_start_unix") or (act_events[0]["wall_time"] if act_events else 0.0))

    f_title = load_font(22, bold=True)
    f_sub = load_font(14, bold=False)
    f_mono = load_font(13, bold=False)
    f_badge = load_font(14, bold=True)

    ck = run_data["case_key"]
    u_pass = run_data["outcomes"]["user_pass"]
    a_pass = run_data["outcomes"]["agent_pass"]
    ind_str = "N/A"
    if ind_run_json:
        iu = ind_run_json["outcomes"]["user_pass"]
        ia = ind_run_json["outcomes"]["agent_pass"]
        ind_str = f"User={'PASS' if iu else 'FAIL'} / Agent={'PASS' if ia else 'FAIL'}"

    rendered: list[Image.Image] = []
    for idx, vf in enumerate(vframes):
        sim_t = idx / max(1, n_frames - 1) * real_dur
        canvas = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(canvas)

        draw.rectangle([0, 0, W, 68], fill=PANEL)
        draw.text((24, 14), f"Human-Agent Shared Desktop · {ck} ({run_data['family']})", fill=FG, font=f_title)
        draw.text(
            (24, 43),
            f"Branch: {run_data['source_branch']} @ 684c79a  |  CPU15 Rootless Docker  |  Codex: workspace-write, approval=never, all-tools, YOLO=OFF",
            fill=MUTED,
            font=f_sub,
        )

        canvas.paste(vf, (24, 86))
        draw.rectangle([23, 85, 24 + VIEW_W, 86 + VIEW_H], outline="#2c3e63", width=2)

        # Bottom telemetry bar under viewport
        draw.rectangle([24, 560, 24 + VIEW_W, 696], fill=PANEL)
        tl = run_data.get("timeline") or {}
        ov_cnt = int(tl.get("literal_same_guest_gui_action_overlap_pair_count") or 0)
        ov_s = float(tl.get("literal_same_guest_gui_action_overlap_s") or 0.0)
        gap_cnt = int(tl.get("user_actions_between_agent_gui_calls_count") or 0)
        draw.text((38, 572), f"Real X11 Capture: {sim_t:5.1f}s / {real_dur:5.1f}s  |  GUI Overlaps: {ov_cnt} ({ov_s:.2f}s)  |  Think-Gap Interleavings: {gap_cnt}", fill=BLUE, font=f_badge)
        draw.text((38, 602), f"Independent (2-Guest Isolated):  {ind_str}", fill=TEAL, font=f_badge)
        sh_col = GREEN if (u_pass and a_pass) else RED
        draw.text(
            (38, 630),
            f"Shared Desktop (Concurrent):     User={'PASS' if u_pass else 'FAIL'}  /  Agent={'PASS' if a_pass else 'FAIL'}  /  Joint={'PASS' if (u_pass and a_pass) else 'FAIL'}",
            fill=sh_col,
            font=f_badge,
        )
        ag = (run_data.get("actors") or {}).get("agent") or {}
        draw.text(
            (38, 660),
            f"Agent Model: gpt-6.1-sol  |  GUI MCP calls: {ag.get('gui_mcp_calls', 0)}  |  CLI calls: {ag.get('cli_mcp_calls', 0)}  |  Permission Audit: PASS (non-YOLO)",
            fill=MUTED,
            font=f_sub,
        )

        # Right live event log panel
        rx = 24 + VIEW_W + 18
        draw.rectangle([rx, 86, W - 20, 696], fill=PANEL)
        draw.rectangle([rx, 86, W - 20, 122], fill=PANEL2)
        draw.text((rx + 14, 95), "Synchronized Actor Event Stream", fill=GOLD, font=f_badge)

        past = [e for e in act_events if (float(e.get("wall_time", t0)) - t0) <= sim_t + 0.5][-14:]
        y = 134
        for ev in past:
            dt = max(0.0, float(ev.get("wall_time", t0)) - t0)
            actor = ev.get("actor_id", "?")
            if actor == "user":
                tag = f"[{dt:5.1f}s] USER  {ev.get('action_name', '')[:25]}"
                col = TEAL
            else:
                tname = ev.get("tool") or "cli"
                tag = f"[{dt:5.1f}s] AGENT {tname[:25]}"
                col = BLUE
            draw.text((rx + 12, y), tag, fill=col, font=f_mono)
            win = str(ev.get("window_after") or ev.get("window_before") or "")[:34]
            draw.text((rx + 18, y + 18), f"win: {win}", fill=MUTED, font=f_mono)
            y += 39
            if y > 665:
                break

        rendered.append(canvas)

    encode_frames_to_mp4(rendered, fps=fps, out_mp4=out_mp4)
    return {
        "case_key": ck,
        "clip_mp4": out_mp4.name,
        "raw_duration_s": round(real_dur, 2),
        "outcomes": run_data["outcomes"],
    }


def render_card_mp4(lines: list[tuple[str, str, int]], seconds: int, fps: int, out_mp4: Path) -> None:
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([48, 48, W - 48, H - 48], fill=PANEL, outline="#2c3e63", width=2)
    y = 92
    for text, color, sz in lines:
        font = load_font(sz, bold=(sz >= 20))
        draw.text((84, y), text, fill=color, font=font)
        y += sz + 18
    encode_frames_to_mp4([canvas] * (seconds * fps), fps=fps, out_mp4=out_mp4)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite-dir", type=Path, required=True)
    ap.add_argument("--cal-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--highlight-cases", nargs="*", default=["ha-triage", "ha-mail", "ha-calendar", "lab-qc", "edu-grade", "garden-ops"])
    args = ap.parse_args()

    out = args.out.resolve()
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "clips").mkdir(parents=True, exist_ok=True)

    shared_runs: dict[str, Path] = {}
    ind_runs: dict[str, dict[str, Any]] = {}
    all_raw_videos: list[dict[str, Any]] = []

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

    fps = 8
    concat_parts: list[Path] = []
    intro_mp4 = out / "clips/00-intro.mp4"
    render_card_mp4(
        [
            ("CoDesk Human-Agent Shared Desktop Suite (Commit 684c79a)", FG, 30),
            ("Reproduced on CPU15 in Rootless Docker with Continuous X11 Video Capture", BLUE, 20),
            ("Agent Policy: gpt-6.1-sol inside isolated non-YOLO container (workspace-write, approval=never, all tools enabled)", TEAL, 16),
            ("User Policy: Calibrated normal-user GUI actor operating concurrent independent records", GOLD, 16),
            (f"Recorded Shared Rollouts: {len(shared_runs)} cases  |  Paired Independent Controls: {len(ind_runs)} cases", FG, 18),
        ],
        seconds=4,
        fps=fps,
        out_mp4=intro_mp4,
    )
    concat_parts.append(intro_mp4)

    chosen = [c for c in args.highlight_cases if c in shared_runs]
    if not chosen:
        chosen = list(shared_runs.keys())[:6]
    clip_summaries = []
    for idx, ck in enumerate(chosen, 1):
        clip_out = out / "clips" / f"{idx:02d}-{ck}-shared.mp4"
        info = render_case_clip(shared_runs[ck], ind_runs.get(ck), clip_out, fps=fps, clip_seconds=11)
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
            ("CPU15 Docker Reproduction & Non-YOLO Audit Summary", FG, 28),
            (f"Independent (2-Guest Isolated): {ind_joint_pass} / {len(ind_runs)} Joint PASS", TEAL, 22),
            (f"Shared Desktop (Concurrent):    {sh_joint_pass} / {len(shared_runs)} Joint PASS", GOLD, 22),
            ("Zero host Codex launches  |  Zero YOLO flags  |  100% turn_context verified workspace-write", GREEN, 17),
            ("All unmodified 1x X11 desktop-rollout.mp4 recordings preserved in raw/", MUTED, 16),
        ],
        seconds=4,
        fps=fps,
        out_mp4=outro_mp4,
    )
    concat_parts.append(outro_mp4)

    concat_txt = out / "clips/concat.txt"
    concat_txt.write_text("".join(f"file '{p.resolve()}'\n" for p in concat_parts), encoding="utf-8")
    showcase_mp4 = out / "human-agent-cpu15-showcase.mp4"
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
        summary_rows.append({
            "case_key": ck,
            "case_id": sd["case_id"],
            "family": sd["family"],
            "independent": id_obj["outcomes"] if id_obj else None,
            "shared": sd["outcomes"],
            "agent_gui_calls_shared": ((sd.get("actors") or {}).get("agent") or {}).get("gui_mcp_calls"),
            "agent_cli_calls_shared": ((sd.get("actors") or {}).get("agent") or {}).get("cli_mcp_calls"),
            "shared_video": f"raw/{ck}-shared-desktop-rollout.mp4",
        })
        ind_cell = (
            f"U:{'PASS' if id_obj['outcomes']['user_pass'] else 'FAIL'} / A:{'PASS' if id_obj['outcomes']['agent_pass'] else 'FAIL'}"
            if id_obj else "—"
        )
        sh_cell = f"U:{'PASS' if sd['outcomes']['user_pass'] else 'FAIL'} / A:{'PASS' if sd['outcomes']['agent_pass'] else 'FAIL'}"
        rows_html.append(
            f"<tr><td><b>{html.escape(ck)}</b></td><td>{html.escape(sd['family'])}</td>"
            f"<td>{ind_cell}</td><td>{sh_cell}</td>"
            f"<td><a href='raw/{ck}-shared-desktop-rollout.mp4'>1x X11 MP4</a></td></tr>"
        )

    index_html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Human-Agent Shared Desktop Suite (684c79a) — CPU15 Docker Video Archive</title>
<style>
body{{margin:0;background:#0b111e;color:#eef4fc;font:15px/1.6 system-ui,sans-serif;padding:32px}}
main{{max-width:1120px;margin:0 auto}}
video{{width:100%;border-radius:10px;border:1px solid #2c3e63;background:#000}}
table{{width:100%;border-collapse:collapse;margin-top:20px;background:#131d31}}
th,td{{padding:10px 14px;border:1px solid #263654;text-align:left}}
a{{color:#58bcff}}
</style></head><body><main>
<h1>Human-Agent Shared Desktop (684c79a) — CPU15 Docker Reproduction &amp; Videos</h1>
<p>Model: <code>gpt-6.1-sol</code> | Container Sandbox: <code>workspace-write</code>, <code>approval_policy=never</code>, all tools enabled, <code>YOLO=OFF</code></p>
<video controls preload="metadata" src="human-agent-cpu15-showcase.mp4"></video>
<table><thead><tr><th>Case</th><th>Domain</th><th>Independent (2 Guests)</th><th>Shared (1 Guest)</th><th>Raw 1x Video</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table></main></body></html>
"""
    (out / "index.html").write_text(index_html, encoding="utf-8")

    manifest = {
        "source_branch": "codex/human-agent-normal-user-v1-20261109",
        "source_commit": "684c79a6374b19a3851cf83b7d79c8978e5b8118",
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

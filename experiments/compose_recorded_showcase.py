"""Compose a synchronized showcase video + HTML gallery from real CPU15 desktop recordings.

Every desktop frame in the left viewport is decoded directly from each task's
real X11 desktop-rollout.mp4 captured on CPU15 (ffmpeg -f x11grab -i :99.0),
synchronized by wall-clock timestamp with actions.jsonl, version_timeline.jsonl,
and real exported workspace artifacts. Unmodified 1x desktop-rollout.mp4 files
are also preserved side by side in raw/.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


W, H = 1280, 720
VIEW_W, VIEW_H = 800, 450
BG = "#0b1020"
PANEL = "#141d30"
PANEL2 = "#1b2740"
FG = "#edf3fc"
MUTED = "#98abc6"
BLUE = "#5cbdff"
TEAL = "#47dec3"
RED = "#ff7b7b"
GOLD = "#f6c875"

TASK_LABELS = {
    "AR-07": {
        "software": "Chromium 156 + FinOps Portal",
        "headline": "共享浏览器会话抢占与合规锁死",
    },
    "AR-08": {
        "software": "Chromium 156 + Inkscape 1.2",
        "headline": "单槽位暂存台并发覆盖与青色主题失配",
    },
    "AR-04": {
        "software": "GIMP 2.10 (XCF + Script-Fu)",
        "headline": "印前压平样张过期（导出后底图被改青色）",
    },
    "AR-03": {
        "software": "FreeCAD 0.20 (OpenCASCADE + STEP)",
        "headline": "止口端盖按旧参数加工，销孔干涉碰撞",
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def summarize_cmd(tool_name: str, args: dict) -> str:
    if tool_name.startswith("desktop."):
        short = tool_name.split(".", 1)[1]
        if short == "screenshot":
            return "GUI screenshot()"
        if short == "click":
            return f"GUI click({args.get('x')}, {args.get('y')})"
        if short == "type_text":
            return f"GUI type({str(args.get('text', ''))[:22]!r})"
        return f"GUI {short}({json.dumps(args, ensure_ascii=False)[:24]})"
    cmd = " ".join(str(args.get("command", "")).strip().split())
    for prefix in ("set -euo pipefail;", "set -e;", "python3 - <<'PY'", "python3 -c"):
        if cmd.startswith(prefix):
            cmd = cmd[len(prefix):].strip()
    return ("CLI: " + cmd)[:44]


def sample_video_frames(ffmpeg_exe: str, mp4_path: Path, count: int) -> list[Image.Image]:
    cmd = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error",
        "-i", str(mp4_path),
        "-vf", f"scale={VIEW_W}:{VIEW_H}",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    frame_bytes = VIEW_W * VIEW_H * 3
    total = max(1, len(raw) // frame_bytes)
    frames = []
    for idx in range(count):
        src_idx = min(total - 1, int(idx * total / max(1, count)))
        off = src_idx * frame_bytes
        frames.append(Image.frombytes("RGB", (VIEW_W, VIEW_H), raw[off : off + frame_bytes]))
    return frames


def format_failure_summary(tid: str, report: dict) -> tuple[str, str]:
    diag = (report.get("grade") or {}).get("diagnostics") or {}
    joint = "PASS" if report.get("joint_pass") else "FAIL"
    if tid == "AR-07":
        clobbers = len(diag.get("session_clobber_events") or [])
        return joint, f"terminal_locked={diag.get('terminal_locked')} · 会话抢占事件 {clobbers} 次"
    if tid == "AR-08":
        return joint, f"staging_tainted={diag.get('tainted')} · SVG 重渲染误差 {diag.get('nav_rgb_diff', 0):.2f}"
    if tid == "AR-04":
        return joint, f"样张 vs 最终 XCF 像素均值差 {diag.get('proof_diff', 0):.2f}（阈值 <= 2.5）"
    if tid == "AR-03":
        return joint, f"止口 {diag.get('pilot_od')}mm vs 座孔 {diag.get('bore_d')}mm · 销干涉 {diag.get('pin_carrier', 0):.1f} mm³"
    return joint, ", ".join(report.get("failed_checks") or ["completed"])[:56]


class Composer:
    def __init__(self, font_path: Path):
        self.font_path = font_path
        self.fonts: dict[int, ImageFont.FreeTypeFont] = {}

    def text(self, draw: ImageDraw.ImageDraw, xy: tuple[float, float], txt: str, size: int = 20, fill: str = FG, anchor: str | None = None):
        if size not in self.fonts:
            self.fonts[size] = ImageFont.truetype(str(self.font_path), size)
        draw.text(xy, str(txt), font=self.fonts[size], fill=fill, anchor=anchor)

    def render_intro(self, items: list[dict]) -> Image.Image:
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((40, 28, 490, 62), radius=8, fill=PANEL2)
        self.text(d, (54, 33), "CPU15 实机重跑录制 · gpt-6-astra (high)", 18, TEAL)
        self.text(d, (1240, 34), "workspace-write 沙箱 · 禁开 YOLO", 18, GOLD, "ra")
        self.text(d, (40, 82), "共享桌面多智能体并发 Rollout 实录", 38, FG)
        self.text(d, (40, 136), "左侧为容器内 Xvfb :99 真实 X11 屏幕录像；右侧同步展示 A/B 实时工具调用与落盘产物。", 21, MUTED)
        for i, item in enumerate(items):
            y = 196 + i * 112
            d.rounded_rectangle((40, y, 1240, y + 96), radius=12, fill=PANEL)
            tid = item["id"]
            rep = item["report"]
            joint, detail = format_failure_summary(tid, rep)
            self.text(d, (62, y + 16), f"{tid} · {item['software']}", 24, BLUE)
            self.text(d, (62, y + 52), item["headline"], 20, FG)
            badge_col = RED if joint == "FAIL" else TEAL
            self.text(d, (1216, y + 16), f"并发评分: {joint}  (重叠 {rep['overlap_seconds']:.1f}s)", 21, badge_col, "ra")
            self.text(d, (1216, y + 54), detail, 18, GOLD, "ra")
        self.text(d, (40, 668), "同目录 raw/ 下附带全部未剪辑 1x 原始 X11 桌面录像（desktop-rollout.mp4）。", 18, MUTED)
        return im

    def render_task_frame(self, item: dict, vid_frame: Image.Image, cur_rel: float, is_summary_hold: bool) -> Image.Image:
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        tid = item["id"]
        rep = item["report"]
        dur = item["duration"]
        joint, detail = format_failure_summary(tid, rep)

        d.rounded_rectangle((32, 18, 330, 50), radius=7, fill=PANEL2)
        self.text(d, (44, 22), f"{tid} · 真实 X11 录像 ({dur:.0f}s -> 16s)", 16, TEAL)
        self.text(d, (344, 22), f"{item['software']} — {item['headline']}", 18, FG)
        self.text(d, (1248, 22), f"并发重叠 {rep['overlap_seconds']:.1f}s · {joint}", 19, RED if joint == "FAIL" else TEAL, "ra")

        d.rounded_rectangle((30, 62, 34 + VIEW_W, 66 + VIEW_H), radius=8, outline="#334155", width=2)
        im.paste(vid_frame, (32, 64))
        d.rounded_rectangle((44, 74, 260, 102), radius=6, fill="#020617")
        self.text(d, (54, 78), f"DISPLAY :99  +{cur_rel:05.1f}s / {dur:05.1f}s", 15, GOLD)

        d.rounded_rectangle((32, 526, 832, 698), radius=10, fill=PANEL)
        x0, x1 = 208, 810
        def x_of(t_s: float) -> float:
            return x0 + (x1 - x0) * max(0.0, min(1.0, t_s / max(1.0, dur)))

        for r_idx, (role, col) in enumerate([("A", BLUE), ("B", TEAL)]):
            y = 546 + r_idx * 42
            sp = item["spans"][role]
            act_info = rep["actors"][role]
            self.text(d, (46, y - 2), f"Role {role} ({act_info['cli_calls']} CLI/{act_info['gui_action_calls']} GUI)", 15, col)
            d.rounded_rectangle((x0, y + 2, x1, y + 18), radius=4, fill="#1e293b")
            xs, xe = x_of(sp["start"]), x_of(sp["end"])
            d.rounded_rectangle((xs, y + 2, max(xs + 2, xe), y + 18), radius=4, outline=col, width=1)
            if cur_rel > sp["start"]:
                d.rounded_rectangle((xs, y + 2, max(xs + 2, min(xe, x_of(cur_rel))), y + 18), radius=4, fill=col)

        self.text(d, (46, 628), "共享工程版本", 15, MUTED)
        d.line((x0, 638, x1, 638), fill="#475569", width=2)
        cur_sha = item["versions"][0]["sha256"][:10] if item["versions"] else "n/a"
        for ver in item["versions"]:
            xv = x_of(ver["rel"])
            reached = ver["rel"] <= cur_rel
            d.ellipse((xv - 5, 633, xv + 5, 643), fill=GOLD if reached else "#475569")
            if reached:
                cur_sha = ver["sha256"][:10]
        px = x_of(cur_rel)
        d.line((px, 540, px, 646), fill=FG, width=2)
        self.text(d, (46, 662), f"最终诊断: {detail}" if is_summary_hold else f"当前共享文件 SHA256: {cur_sha}…  |  {detail}", 16, GOLD if is_summary_hold else FG)

        d.rounded_rectangle((848, 62, 1248, 698), radius=10, fill=PANEL)
        self.text(d, (864, 76), "实时双智能体动作流 (actions.jsonl)", 18, FG)
        past = [ev for ev in item["events"] if ev["rel"] <= cur_rel + 0.05][-8:]
        y_ev = 110
        if not past:
            self.text(d, (864, y_ev), "等待首个工具调用…", 16, MUTED)
        for ev in past:
            col = BLUE if ev["role"] == "A" else TEAL
            d.rounded_rectangle((862, y_ev, 1234, y_ev + 42), radius=6, fill=PANEL2)
            self.text(d, (872, y_ev + 4), f"+{ev['rel']:05.1f}s  Role {ev['role']}", 14, col)
            self.text(d, (872, y_ev + 22), ev["summary"], 13, FG)
            y_ev += 48

        thumbs = item["artifact_thumbs"]
        if thumbs:
            self.text(d, (864, 506), "实跑落盘产物对比 (/workspace/exports)", 16, GOLD)
            for idx, (label, thumb_im) in enumerate(thumbs[:2]):
                tx = 864 + idx * 188
                d.rounded_rectangle((tx - 2, 534, tx + 174, 666), radius=6, outline="#475569", width=1)
                im.paste(thumb_im, (tx, 536))
                self.text(d, (tx, 670), label, 13, MUTED)
        else:
            self.text(d, (864, 520), "评分未通过项 (grade.json):", 16, GOLD)
            for idx, fc in enumerate((rep.get("failed_checks") or ["none"])[:4]):
                self.text(d, (864, 548 + idx * 28), f"- {fc}", 15, RED if fc != "none" else TEAL)
        return im


def encode_mp4(ffmpeg_exe: str, out_path: Path, frames, fps: int) -> None:
    cmd = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-an",
        "-c:v", "libx264", "-threads", "2", "-preset", "fast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed encoding {out_path}")
    except BaseException:
        proc.kill()
        proc.wait()
        raise


def collect_thumbs(cond_dir: Path, tid: str) -> list[tuple[str, Image.Image]]:
    candidates: list[tuple[str, Path]] = []
    if tid == "AR-04":
        candidates = [
            ("A: press_proof_flat.png", cond_dir / "workspace/exports/press_proof_flat.png"),
            ("B: color_graded_preview.png", cond_dir / "workspace/exports/color_graded_preview.png"),
        ]
    elif tid == "AR-08":
        candidates = [
            ("A: nav_sheet_300dpi.png", cond_dir / "workspace/exports/nav_sheet_300dpi.png"),
            ("Final X11 (:99)", cond_dir / "desktop-final.png"),
        ]
    elif tid == "AR-03" and (cond_dir / "workspace/exports/pinion_carrier_render.png").is_file():
        candidates = [
            ("A: pinion_carrier.step", cond_dir / "workspace/exports/pinion_carrier_render.png"),
            ("B: main_casing + 销碰撞", cond_dir / "workspace/exports/assembly_collision_render.png"),
        ]
    else:
        candidates = [
            ("Initial X11 (:99)", cond_dir / "desktop-initial.png"),
            ("Final X11 (:99)", cond_dir / "desktop-final.png"),
        ]
    out = []
    for label, p in candidates:
        if p.is_file():
            with Image.open(p) as raw_im:
                rgb = raw_im.convert("RGB").resize((172, 128))
            out.append((label, rgb))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--tasks", nargs="*", default=["AR-07", "AR-08", "AR-04", "AR-03"])
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--ffmpeg", default=None)
    args = parser.parse_args()

    ffmpeg_exe = args.ffmpeg
    if not ffmpeg_exe:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    out = args.out.resolve()
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "clips").mkdir(parents=True, exist_ok=True)
    composer = Composer(args.font.resolve())

    play_seconds = 16
    hold_seconds = 4
    items = []
    for tid in args.tasks:
        cond_dir = args.run_root.resolve() / tid / "ma_sd_full_cli"
        if not (cond_dir / "report.json").is_file() or not (cond_dir / "desktop-rollout.mp4").is_file():
            continue
        rep = json.loads((cond_dir / "report.json").read_text())
        rec = json.loads((cond_dir / "recording.json").read_text())
        t0 = float(rec["capture_start_unix"])
        dur = max(1.0, float(rec["media"]["format"]["duration"]))
        raw_mp4 = out / "raw" / f"{tid}-desktop-rollout.mp4"
        shutil.copy2(cond_dir / "desktop-rollout.mp4", raw_mp4)
        shutil.copy2(cond_dir / "report.json", out / "raw" / f"{tid}-report.json")
        shutil.copy2(cond_dir / "recording.json", out / "raw" / f"{tid}-recording.json")

        events = []
        for role in ("A", "B"):
            act_file = cond_dir / f"actor_{role}/actions.jsonl"
            if act_file.is_file():
                for line in act_file.read_text().splitlines():
                    if line.strip():
                        row = json.loads(line)
                        events.append({
                            "role": role,
                            "rel": max(0.0, float(row["timestamp"]) - t0),
                            "tool": row["tool"],
                            "summary": summarize_cmd(row["tool"], row.get("args") or {}),
                        })
        events.sort(key=lambda r: r["rel"])
        versions = []
        ver_file = cond_dir / "version_timeline.jsonl"
        if ver_file.is_file():
            for line in ver_file.read_text().splitlines():
                if line.strip():
                    v = json.loads(line)
                    versions.append({"rel": max(0.0, float(v["timestamp"]) - t0), "sha256": v["sha256"]})
        spans = {
            role: {
                "start": max(0.0, float(rep["actors"][role]["first_tool_ts"]) - t0),
                "end": max(0.0, float(rep["actors"][role]["last_tool_ts"]) - t0),
            }
            for role in ("A", "B")
        }
        meta = TASK_LABELS.get(tid, {"software": tid, "headline": tid})
        items.append({
            "id": tid,
            "software": meta["software"],
            "headline": meta["headline"],
            "report": rep,
            "recording": rec,
            "duration": dur,
            "raw_mp4": raw_mp4,
            "events": events,
            "versions": versions,
            "spans": spans,
            "artifact_thumbs": collect_thumbs(cond_dir, tid),
        })

    if not items:
        raise RuntimeError("No completed recorded rollouts found")

    intro_im = composer.render_intro(items)
    intro_im.save(out / "poster.png")
    segments = []
    intro_clip = out / "clips/00-intro.mp4"
    encode_mp4(ffmpeg_exe, intro_clip, (intro_im for _ in range(5 * args.fps)), args.fps)
    segments.append(intro_clip)

    for item in items:
        tid = item["id"]
        sampled = sample_video_frames(ffmpeg_exe, item["raw_mp4"], play_seconds * args.fps)
        clip_path = out / "clips" / f"{tid}-showcase.mp4"

        def gen_frames():
            for i, vframe in enumerate(sampled):
                cur_rel = item["duration"] * (i / max(1, len(sampled) - 1))
                yield composer.render_task_frame(item, vframe, cur_rel, False)
            final_im = composer.render_task_frame(item, sampled[-1], item["duration"], True)
            final_im.save(out / f"{tid}-final.png")
            for _ in range(hold_seconds * args.fps):
                yield final_im

        encode_mp4(ffmpeg_exe, clip_path, gen_frames(), args.fps)
        segments.append(clip_path)

    concat_txt = out / "clips/concat.txt"
    concat_txt.write_text("".join(f"file '{p.name}'\n" for p in segments))
    showcase_mp4 = out / "cpu15-concurrent-rollouts-showcase.mp4"
    subprocess.run(
        [ffmpeg_exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", "-movflags", "+faststart", str(showcase_mp4)],
        check=True,
    )

    cards = "".join(
        f"<section><h2>{it['id']} · {html.escape(it['software'])} — {html.escape(it['headline'])}</h2>"
        f"<p>原始 1x 桌面录像（{it['duration']:.1f}s，10fps X11 直录）：<a href='raw/{it['id']}-desktop-rollout.mp4' download>下载原始录像</a> · <a href='raw/{it['id']}-report.json'>查看 report.json</a></p>"
        f"<video controls preload='metadata' poster='{it['id']}-final.png' src='raw/{it['id']}-desktop-rollout.mp4'></video></section>"
        for it in items
    )
    (out / "index.html").write_text(
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>CPU15 并发 Rollout 实机桌面录像</title>"
        "<style>body{background:#0b1020;color:#edf3fc;font:17px/1.6 system-ui,sans-serif;max-width:1100px;margin:36px auto;padding:0 20px}"
        "video{width:100%;border-radius:12px;background:#141d30}a{color:#5cbdff}section{margin:36px 0}</style>"
        "<h1>CPU15 并发 Rollout 实机桌面录像（gpt-6-astra, high）</h1>"
        "<p>合集视频（左：真实 X11 :99 桌面录像；右：同步双智能体工具流与落盘产物）：</p>"
        "<video controls preload='metadata' poster='poster.png' src='cpu15-concurrent-rollouts-showcase.mp4'></video>"
        f"<p><a href='cpu15-concurrent-rollouts-showcase.mp4' download>下载合集 MP4</a></p>{cards}</html>",
        encoding="utf-8",
    )
    manifest = {
        "showcase_mp4": str(showcase_mp4),
        "showcase_bytes": showcase_mp4.stat().st_size,
        "showcase_sha256": sha256_file(showcase_mp4),
        "tasks": [
            {
                "id": it["id"],
                "joint_pass": it["report"]["joint_pass"],
                "overlap_seconds": it["report"]["overlap_seconds"],
                "raw_duration_s": it["duration"],
                "raw_mp4": f"raw/{it['id']}-desktop-rollout.mp4",
                "raw_sha256": sha256_file(it["raw_mp4"]),
            }
            for it in items
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

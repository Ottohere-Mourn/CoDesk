"""Make explicitly labelled log animations from saved Astra concurrency reports.

No desktop frames or per-action traces are reconstructed. Geometry and document
icons are explanatory schematics; timing and result numbers come from evidence.
Requires Pillow and an ffmpeg executable (or imageio-ffmpeg).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


W, H = 1280, 720
BG = "#0b1020"
PANEL = "#151e32"
FG = "#edf3fc"
MUTED = "#9aaec8"
BLUE = "#5cbdff"
TEAL = "#47dec3"
RED = "#ff8585"
GOLD = "#f6c875"
CASE_SECONDS = 26
INTRO_SECONDS = 6
OUTRO_SECONDS = 6
ANIMATION_START = 5
ANIMATION_END = 20
SPECS = {
    "AR-03": {
        "software": "FreeCAD", "title": "装配孔位失配",
        "a": "A：加工行星架，导出 STEP", "b": "B：45 组计算后更新壳体参数",
        "summary": "旧参数产物与最终壳体无法正确配合",
        "caption": "最终检查：量规销与行星架发生实体干涉。",
    },
    "AR-04": {
        "software": "GIMP", "title": "打样图已经过期",
        "a": "A：加裁切标记，导出印前样张", "b": "B：8 组试验后更新色彩与促销带",
        "summary": "已导出的 PNG 与最终 XCF 不一致",
        "caption": "最终检查：样张与最终工程重新压平的像素不一致。",
    },
    "AR-05": {
        "software": "MLT / FFmpeg", "title": "母版比最终工程短了 2 秒",
        "a": "A：编码播出母版并完成 QC", "b": "B：慢放重剪镜头，延长时间线",
        "summary": "交付的 MP4 没有跟上最终时间线",
        "caption": "最终检查：MP4 为 72 帧，最终工程要求 120 帧。",
    },
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_evidence(source, out):
    summary = json.loads((source / "SUMMARY.json").read_text())
    result = []
    for tid, spec in SPECS.items():
        folder = source / tid / "ma_sd_full_cli"
        report = json.loads((folder / "report.json").read_text())
        rows = [json.loads(line) for line in (folder / "version_timeline.jsonl").read_text().splitlines() if line.strip()]
        actors = report["actors"]
        assert report["valid_model_run"] and not report["joint_pass"]
        assert all(actor["status"] == "done" for actor in actors.values())
        assert summary["tasks"][tid]["seq_ba_full_cli"] == "PASS"
        start = min(rows[0]["timestamp"], *(a["first_tool_ts"] for a in actors.values()))
        end = max(rows[-1]["timestamp"], *(a["last_tool_ts"] for a in actors.values()))
        spans = {role: {"start": actor["first_tool_ts"] - start,
                        "end": actor["last_tool_ts"] - start,
                        "gui": actor["gui_action_calls"], "cli": actor["cli_calls"]}
                 for role, actor in actors.items()}
        dest = out / "evidence" / tid
        dest.mkdir(parents=True, exist_ok=True)
        files = {}
        for name in ("report.json", "version_timeline.jsonl", "grade.json"):
            shutil.copy2(folder / name, dest / name)
            files[name] = sha(dest / name)
        seq_dest = dest / "sequential-report.json"
        shutil.copy2(source / tid / "seq_ba_full_cli/report.json", seq_dest)
        files[seq_dest.name] = sha(seq_dest)
        result.append(dict(spec, id=tid, start=start, end=end, span=end-start,
            utc=datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            spans=spans, versions=[dict(row, relative=row["timestamp"]-start) for row in rows],
            report=report, source_files=files))
    (out / "evidence.json").write_text(json.dumps({
        "kind": "real-log-visualization-not-desktop-recording",
        "model": summary["model"], "effort": summary["effort"], "cases": result,
        "limitations": ["No original desktop screenshots or full action traces available locally",
            "Version hashes do not identify their author or exact semantic change",
            "Tool first/last timestamp intervals do not imply continuous activity",
            "Final artifact schematics are explanations, not measured screenshots",
            "Historical 2026-11-11 runs; not reruns under the updated CPU15 sandbox policy"],
    }, ensure_ascii=False, indent=2) + "\n")
    return result


class Canvas:
    def __init__(self, font):
        self.font_path = font
        self.fonts = {}

    def text(self, draw, xy, text, size=24, fill=FG, anchor=None):
        if size not in self.fonts:
            self.fonts[size] = ImageFont.truetype(str(self.font_path), size)
        draw.text(xy, str(text), font=self.fonts[size], fill=fill, anchor=anchor)

    def base(self, title, subtitle):
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((40, 28, 265, 60), radius=8, fill="#233149")
        self.text(d, (52, 30), "ASTRA HIGH  /  2026-11-11", 16)
        self.text(d, (1240, 32), "真实日志可视化 · 非桌面录像", 21, GOLD, "ra")
        self.text(d, (40, 78), title, 37)
        self.text(d, (40, 132), subtitle, 22, MUTED)
        self.text(d, (40, 685), "来源：已保存的 report.json、版本时间线和评分；示意图不代表真实软件画面。", 16, MUTED)
        return im

    def intro(self, cases, t):
        im = self.base("两位智能体，同时修改一个工程", "Full GUI+CLI 可用；这三个例子的实测操作均为 CLI。")
        d = ImageDraw.Draw(im)
        self.text(d, (40, 199), "三个真实并发实验", 30)
        for i, case in enumerate(cases):
            y = 257 + i * 87
            d.rounded_rectangle((40, y, 1240, y + 71), radius=14, fill=PANEL)
            self.text(d, (62, y + 15), case["id"], 27, BLUE)
            self.text(d, (205, y + 15), case["software"], 27)
            self.text(d, (610, y + 19), case["title"], 24, MUTED)
        self.text(d, (42, 552), "看什么：A/B 工具事件区间 → 工程版本变化 → 最终产物失配", 27, TEAL)
        self.text(d, (42, 603), "原始桌面截图暂不可取；片中不补造操作步骤，也不推断每次写入的作者。", 21, MUTED)
        return im

    def schematic(self, d, case, final):
        tid = case["id"]
        diag = case["report"]["grade"]["diagnostics"]
        self.text(d, (64, 227), "最终产物示意" if final else "任务目标示意", 17, MUTED)
        self.text(d, (682, 227), "最终工程示意" if final else "任务目标示意", 17, MUTED)
        if tid == "AR-03":
            for x, color, label, value in [(164, BLUE, "行星架止口", f"{diag['pilot_od']:.1f} mm"),
                                          (782, TEAL, "最终壳体座孔", f"{diag['bore_d']:.1f} mm")]:
                d.ellipse((x-52, 267, x+52, 371), outline=color, width=6)
                d.ellipse((x-30, 289, x+30, 349), outline="#60718e", width=3)
                for a in range(6):
                    a *= math.pi / 3
                    px, py = x+43*math.cos(a), 319+43*math.sin(a)
                    d.ellipse((px-4, py-4, px+4, py+4), fill=color)
                self.text(d, (x+90, 275), label if final else ("加工并导出 STEP" if x<600 else "计算并更新壳体"), 23)
                self.text(d, (x+90, 317), value if final else ("读取共享参数" if x<600 else "45 组 STL 扫描"), 30, color)
        elif tid == "AR-04":
            for x, color, ext in [(105, BLUE, "PNG"), (724, TEAL, "XCF")]:
                d.rounded_rectangle((x, 268, x+104, 370), radius=8, outline=color, width=3)
                d.rectangle((x+15, 283, x+88, 322), fill=color)
                d.line((x+15, 335, x+88, 335), fill=MUTED, width=2)
                self.text(d, (x+20, 343), ext, 17)
            self.text(d, (252, 278), "印前样张", 26)
            self.text(d, (252, 321), "已导出" if final else "添加裁切标记", 29, BLUE)
            self.text(d, (869, 278), "共享多图层工程", 25)
            self.text(d, (869, 321), "已改色" if final else "8 组色彩试验", 29, TEAL)
        else:
            for x, color, label, value, frames in [(70, BLUE, "交付 MP4", "72 帧 / 3.0 s", 72),
                                                  (690, TEAL, "最终 MLT", "120 帧 / 5.0 s", 120)]:
                self.text(d, (x, 272), label if final else ("母版编码 + QC" if x<600 else "慢放重剪镜头"), 26)
                width = int(470 * (frames / 120)) if final else 470
                d.rounded_rectangle((x, 326, x+width, 365), radius=5, fill=color)
                for i in range(1, max(1, width//39)):
                    d.line((x+i*39, 331, x+i*39, 359), fill=BG, width=2)
                self.text(d, (x+470, 274), value if final else ("导出 MP4" if x<600 else "更新 MLT"), 22, color, "ra")

    def case(self, case, t):
        final = t >= ANIMATION_END
        progress = max(0, min(1, (t-ANIMATION_START)/(ANIMATION_END-ANIMATION_START)))
        now = case["span"]*progress
        overlap = case["report"]["overlap_seconds"]
        subtitle = case["summary"] if final else f"工具事件区间重叠 {overlap:.2f} s  ·  未加跨智能体锁  ·  {case['utc']}"
        im = self.base(f"{case['id']}  {case['software']}  /  {case['title']}", subtitle)
        d = ImageDraw.Draw(im)
        for x, color, role in [(40, BLUE, "a"), (660, TEAL, "b")]:
            d.rounded_rectangle((x, 179, x+580, 392), radius=14, fill=PANEL)
            self.text(d, (x+23, 191), case[role], 22, color)
        self.schematic(d, case, final)

        if final:
            diag = case["report"]["grade"]["diagnostics"]
            outcome = {
                "AR-03": f"装配干涉体积  {diag.get('pin_carrier', 0):,.2f} mm³",
                "AR-04": f"样张重渲染像素均值差  {diag.get('proof_diff', 0):.3f}",
                "AR-05": f"母版缺少  {diag.get('exp_frames', 0)-diag.get('frames_a', 0)} 帧（按 24 fps 为 2 秒）",
            }[case["id"]]
            self.text(d, (40, 403), "并发联合评分：FAIL", 24, RED)
            self.text(d, (435, 403), outcome, 24, GOLD)
            self.text(d, (1240, 407), "顺序对照：PASS", 20, TEAL, "ra")
        else:
            self.text(d, (40, 403), "工具首末事件区间（区间内不代表持续执行）", 21, MUTED)
            self.text(d, (1240, 403), f"时间轴 {case['span']:.1f}s → 15s · {case['span']/15:.1f}×", 20, MUTED, "ra")

        x0, x1 = 254, 1214
        def x_at(value):
            return x0+(x1-x0)*value/case["span"]
        for idx, (role, color) in enumerate([( "A", BLUE), ("B", TEAL)]):
            y = 456 + idx*50
            span = case["spans"][role]
            self.text(d, (42, y-2), f"{role} · {span['cli']} CLI / {span['gui']} GUI", 19, color)
            d.rounded_rectangle((x0, y, x1, y+21), radius=5, fill="#1c2940")
            xa, xb = x_at(span["start"]), x_at(span["end"])
            d.rounded_rectangle((xa, y, max(xa+2, xb), y+21), radius=5, outline=color, width=2)
            if now > span["start"]:
                d.rounded_rectangle((xa, y, max(xa+2, min(x_at(now),xb)), y+21), radius=5, fill=color)
            self.text(d, (x1, y+22), f"{span['start']:.1f}–{span['end']:.1f}s", 14, MUTED, "ra")
        self.text(d, (42, 554), "工程版本（采样）", 19, MUTED)
        d.line((x0, 567, x1, 567), fill="#52617c", width=2)
        last_hash = case["versions"][0]["sha256"]
        for idx, version in enumerate(case["versions"]):
            x = x_at(version["relative"])
            seen = version["relative"] <= now
            d.ellipse((x-5, 562, x+5, 572), fill=GOLD if seen else "#52617c")
            self.text(d, (x, 581), f"{version['relative']:.1f}s", 14, MUTED, "ma")
            if seen:
                last_hash=version["sha256"]
        px = x_at(now)
        d.line((px, 447, px, 574), fill=FG, width=2)
        self.text(d, (42, 613), f"日志时间  +{now:05.1f}s  /  版本 SHA-256 {last_hash[:12]}…", 19, FG)
        self.text(d, (42, 648), case["caption"] if final else "只展示日志记录的版本变化；无法据哈希判断每次保存的作者及具体内容。", 19, RED if final else MUTED)
        return im

    def outro(self, cases, t):
        im = self.base("会操作软件，也可能交付过期产物", "这些是一次历史实验的观察结果，不代表未来每次并发运行都会失败。")
        d = ImageDraw.Draw(im)
        self.text(d, (42, 211), "共享工程持续变化，最终一致性才是评分关键。", 33, TEAL)
        for idx, case in enumerate(cases):
            y = 290+idx*78
            self.text(d, (43, y), case["software"], 26, BLUE)
            self.text(d, (348, y), case["summary"], 25)
        self.text(d, (43, 560), "素材范围：真实时间戳、版本哈希、工具计数、最终评分", 25)
        self.text(d, (43, 610), "不是桌面录像；没有重跑模型；原始逐步操作与截图尚未取回。", 22, GOLD)
        return im


def encode(ffmpeg, path, frames, fps, log):
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
        "-threads", "2", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)]
    with log.open("wb") as stderr:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=stderr)
        try:
            for im in frames:
                proc.stdin.write(im.tobytes())
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed; see {log}")
        except BaseException:
            proc.kill()
            proc.wait()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--fps", type=int, default=20)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.ffmpeg:
        import imageio_ffmpeg
        args.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cases = load_evidence(args.source, out)
    canvas = Canvas(args.font)
    canvas.intro(cases, 0).save(out / "poster.png")
    segments=[]
    encode(args.ffmpeg, out / "intro.mp4", (canvas.intro(cases, i/args.fps) for i in range(INTRO_SECONDS*args.fps)), args.fps, out / "intro.encode.log")
    segments.append("intro.mp4")
    for case in cases:
        filename=case["id"]+"-log-animation.mp4"
        encode(args.ffmpeg, out / filename, (canvas.case(case, i/args.fps) for i in range(CASE_SECONDS*args.fps)), args.fps, out / (case["id"]+".encode.log"))
        canvas.case(case, CASE_SECONDS).save(out / (case["id"]+"-final.png"))
        segments.append(filename)
        print("encoded",filename,flush=True)
    encode(args.ffmpeg, out / "outro.mp4", (canvas.outro(cases, i/args.fps) for i in range(OUTRO_SECONDS*args.fps)), args.fps, out / "outro.encode.log")
    segments.append("outro.mp4")
    concat=out / "concat.txt"
    concat.write_text("".join(f"file '{filename}'\n" for filename in segments))
    subprocess.run([args.ffmpeg,"-hide_banner","-loglevel","error","-y","-f","concat","-safe","1","-i",str(concat),"-c","copy","-movflags","+faststart",str(out/"astra-concurrent-examples.mp4")],check=True)
    contact=Image.new("RGB",(W,H*len(cases)),BG)
    for i,case in enumerate(cases):contact.paste(canvas.case(case,CASE_SECONDS),(0,i*H))
    contact.resize((640,1080)).save(out/"contact-sheet.png")
    duration=INTRO_SECONDS+CASE_SECONDS*len(cases)+OUTRO_SECONDS
    links="".join(f'<section><h2>{c["id"]} · {html.escape(c["software"])}：{c["title"]}</h2><video controls preload="metadata" poster="{c["id"]}-final.png" src="{c["id"]}-log-animation.mp4"></video><p>{c["summary"]}。<a href="evidence/{c["id"]}/report.json">原始评分与时间</a></p></section>' for c in cases)
    (out/"index.html").write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Astra 并发实验 · 日志动画</title><style>body{background:#0b1020;color:#edf3fc;font:18px/1.6 system-ui,sans-serif;max-width:1080px;margin:40px auto;padding:0 20px}h1{font-size:36px}h2{font-size:24px}a{color:#5cbdff}video{display:block;width:100%;border-radius:14px;background:#151e32}section{margin:40px 0}.notice{border-left:4px solid #f6c875;background:#151e32;padding:18px}small{color:#9aaec8}</style><h1>Astra high：三个并发实验例子</h1><p class="notice"><strong>真实日志可视化，非桌面录像。</strong>使用 2026-11-11 已保存的时间戳、文件版本和评分；没有补造逐步操作。图示仅解释最终结果。原始截图所在 CPU10 暂不可连接。</p><video controls preload="metadata" poster="poster.png" src="astra-concurrent-examples.mp4"></video><p>合集 90 秒 · 无声中文字幕 · <a href="astra-concurrent-examples.mp4" download>下载 MP4</a> · <a href="evidence.json">数据与来源</a></p>'''+links+'''<small>工具首末事件之间不代表持续执行；版本哈希不能单独确定作者与具体改动。历史结果不是新版 CPU15 沙箱策略下的重跑。</small></html>''')
    files=[p for p in out.iterdir() if p.suffix in {".mp4",".png",".html",".json"}]
    (out/"SHA256SUMS").write_text("".join(f"{sha(p)}  {p.name}\n" for p in sorted(files)))
    print(json.dumps({"output":str(out),"duration_s":duration,"resolution":[W,H],"fps":args.fps,"cases":len(cases)},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()

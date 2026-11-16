"""Record real X11 desktop video during new sandboxed Astra GUI+CLI rollouts.

Run with PARAGUI_ASTRA_DESKTOP_IMAGE and CODESK_CODEX_CONTAINER_IMAGE set to
the restored images. No synthetic desktop frames are used. CLI activity can
leave the visible GUI unchanged; retain action logs alongside the recording.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import time

from PIL import Image, ImageStat

from experiments.astra_races_v2 import (
    AstraSharedDesktop, DESKTOP_IMAGE, MODEL_NAME, REASONING_EFFORT,
    run_astra_actor, run_condition,
)
from experiments.codesk_container_codex import DEFAULT_CONTAINER_IMAGE


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class RecordedDesktop(AstraSharedDesktop):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recording = False
        self.capture_info = {}

    def checked(self, *args, timeout=30):
        return subprocess.run(["docker", "exec", self.container_name, *args],
            check=True, capture_output=True, timeout=timeout)

    def sync_permissions(self):
        if self.created:
            subprocess.run(
                ["docker", "exec", self.container_name, "chmod", "-R", "a+rX,ug+w", "/workspace", "/var/agent_work"],
                capture_output=True,
                timeout=20,
            )

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 180) -> dict:
        try:
            return super().exec_role(role, command_str, cwd=cwd, timeout_s=timeout_s)
        finally:
            self.sync_permissions()

    def capture_frame(self, name):
        raw = self.checked("env", "DISPLAY=:99", "import", "-window", "root", "png:-").stdout
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        if image.size != (1280, 720) or max(ImageStat.Stat(image).stddev) < 3:
            raise RuntimeError("X11 screenshot is blank or has unexpected dimensions")
        (self.cond_dir / name).write_bytes(raw)

    def start(self):
        try:
            super().start()
            self.capture_frame("desktop-initial.png")
            cmd = ("date +%s.%N > /tmp/rollout-start.txt; echo $$ > /tmp/rollout-ffmpeg.pid; "
                "exec ffmpeg -hide_banner -loglevel warning -nostdin -y "
                "-f x11grab -video_size 1280x720 -framerate 10 -draw_mouse 1 -i :99.0 "
                "-c:v libx264 -threads 2 -preset veryfast -crf 22 -pix_fmt yuv420p "
                "-t 1800 /tmp/rollout.mkv > /tmp/rollout-ffmpeg.log 2>&1")
            subprocess.run(["docker", "exec", "-d", self.container_name, "bash", "-lc", cmd],
                check=True, capture_output=True, timeout=20)
            time.sleep(1)
            self.checked("bash", "-lc", "kill -0 $(cat /tmp/rollout-ffmpeg.pid)")
            self.recording = True
            self.capture_info = {
                "kind": "real-x11-desktop-recording", "rerun": True,
                "task_id": self.task_id, "capture_start_unix": float(self.checked("cat", "/tmp/rollout-start.txt").stdout),
                "resolution": [1280, 720], "fps": 10,
                "desktop_image": DESKTOP_IMAGE, "agent_image": DEFAULT_CONTAINER_IMAGE,
                "model": MODEL_NAME, "reasoning_effort": REASONING_EFFORT,
                "sandbox_mode": "workspace-write", "yolo_enabled": False,
                "note": "Continuous X11 capture. CLI calls may not change the open GUI. No reconstructed frames.",
            }
            save(self.cond_dir / "recording.json", self.capture_info)
        except BaseException:
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
                self.created = False
            raise

    def finish_recording(self):
        if not self.recording:
            return
        self.capture_frame("desktop-final.png")
        self.checked("bash", "-lc", "kill -INT $(cat /tmp/rollout-ffmpeg.pid)")
        for _ in range(60):
            probe = subprocess.run(["docker", "exec", self.container_name, "bash", "-lc",
                "kill -0 $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null"], capture_output=True, timeout=10)
            if probe.returncode:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Recorder did not stop cleanly")
        self.recording = False
        self.checked("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "/tmp/rollout.mkv",
            "-c", "copy", "-movflags", "+faststart", "/tmp/desktop-rollout.mp4", timeout=60)
        for remote, name in [("/tmp/desktop-rollout.mp4", "desktop-rollout.mp4"),
                             ("/tmp/rollout-ffmpeg.log", "recording-ffmpeg.log")]:
            subprocess.run(["docker", "cp", self.container_name+":"+remote, str(self.cond_dir/name)],
                check=True, capture_output=True, timeout=60)
        probe = json.loads(self.checked("ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames:format=duration",
            "-of", "json", "/tmp/desktop-rollout.mp4").stdout)
        assert float(probe["format"]["duration"]) > 0
        path=self.cond_dir/"desktop-rollout.mp4"
        self.capture_info.update(capture_end_unix=time.time(), media=probe,
            bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        save(self.cond_dir/"recording.json",self.capture_info)

    def stop_and_grade(self):
        try:
            self.sync_permissions()
            self.finish_recording()
        except BaseException:
            # Keep raw output even on recording-validation failures.
            subprocess.run(["docker", "cp", self.container_name+":/tmp/rollout.mkv",
                str(self.cond_dir/"recording-incomplete.mkv")], capture_output=True, timeout=30)
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
                self.created=False
            raise
        return super().stop_and_grade()


def preflight(args, api):
    dest=args.out/"preflight"
    if dest.exists():
        raise RuntimeError("Use a new --out directory; preflight evidence must not be overwritten")
    desk=RecordedDesktop(dest,"AR-04",args.code_root)
    desk.build_pristine()
    desk.start()
    prompt=("This is an infrastructure preflight, not an engineering ticket. "
        "Call desktop.screenshot once. Call guest_bash to run `printf 'GUEST_CLI_OK\\n'`. "
        "Use your built-in shell tool to write /session/work/sandbox-probe.txt containing LOCAL_SHELL_OK. "
        "Do not edit the desktop project. Then finish with PREFLIGHT_OK.")
    (desk.ticket_a/"task.md").write_text(prompt)
    actor=None
    try:
        actor=run_astra_actor("A",desk,dest/"actor_A",desk.ticket_a,api,args.codex_bin,timeout_s=300)
        actions=[json.loads(line) for line in (dest/"actor_A/actions.jsonl").read_text().splitlines() if line.strip()]
        assert actor["status"]=="done" and actor["permission_audit_ok"],actor
        assert any(row["tool"]=="desktop.screenshot" for row in actions),"No real screenshot call"
        assert any(row["tool"].startswith("guest_bash.") for row in actions),"No Guest CLI call"
        assert (desk.work_a/"sandbox-probe.txt").read_text().strip()=="LOCAL_SHELL_OK","Local sandbox shell did not run"
        save(dest/"preflight-result.json",{"passed":True,"actor":actor})
    except Exception as exc:
        save(dest/"preflight-result.json",{"passed":False,"actor":actor,"error":str(exc)})
        raise
    finally:
        desk.stop_and_grade()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--api-json",type=Path,required=True)
    parser.add_argument("--codex-bin",type=Path,required=True)
    parser.add_argument("--tasks",nargs="*",default=["AR-03","AR-04","AR-07","AR-08"])
    parser.add_argument("--workers",type=int,default=2)
    parser.add_argument("--preflight-only",action="store_true")
    parser.add_argument("--skip-preflight",action="store_true")
    args=parser.parse_args()
    args.code_root=args.code_root.resolve();args.out=args.out.resolve();args.codex_bin=args.codex_bin.resolve()
    api=json.loads(args.api_json.read_text())
    args.out.mkdir(parents=True,exist_ok=True)
    if not args.skip_preflight:
        preflight(args,api)
        print("PREFLIGHT_PASS",flush=True)
    if args.preflight_only:return
    results={}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fut_map = {}
        for tid in args.tasks:
            print("START", tid, flush=True)
            fut_map[pool.submit(run_condition, tid, "ma_sd_full_cli", args.out, args.code_root, api, args.codex_bin, desktop_cls=RecordedDesktop)] = tid
        for fut in as_completed(fut_map):
            tid = fut_map[fut]
            try:
                report = fut.result()
                results[tid] = {"status": "complete", "report": report}
            except Exception as exc:
                results[tid] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            save(args.out / "recording-suite-status.json", results)
            print("FINISHED", tid, results[tid]["status"], flush=True)


if __name__=="__main__":
    main()

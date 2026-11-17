"""Internet-enabled real-web + real-software 4-agent ultra-long-horizon runner (gpt-6.1-sol only, non-YOLO)."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import threading
import time

from experiments.deepseek_v41_eval import analyze_race_awareness
from experiments.thematic_arenas_v1 import make_arena_handlers, run_arena_actor
from tasks.thematic_arenas_v1.suite import sha256_file, write_json
from tasks.ultra_arenas_v1.catalog import UA_BY_ID, ULTRA_ARENAS_CATALOG

DESKTOP_IMAGE = os.environ.get("PARAGUI_UA_DESKTOP_IMAGE", "paragui/astra-recording-desktop:20261113")


def build_ultra_prompt(role: str, ticket_md: str, timeout_s: int, coord_mode: str = "no_comm") -> str:
    coord_note = ""
    if coord_mode == "shared_scratchpad":
        coord_note = (
            "\nShared Coordination Scratchpad: `/workspace/.coord/SCRATCHPAD.md` and `/workspace/.coord/locks/` are available to record active critical sections and completed milestones.\n"
        )
    return (
        f"You are operating an internet-connected Linux engineering workstation (`DISPLAY=:99`, `1280x720`) with `/workspace` (budget: {timeout_s}s).\n"
        "You have full GUI tools (`desktop`: `screenshot`, `click`, `type_text`, `key`, `wait`) and full workstation CLI (`guest_bash`).\n"
        "Start with `desktop.screenshot` to inspect the live open Chromium window and desktop applications on `DISPLAY=:99`.\n"
        f"Iterate systematically against the workstation `/api/drc_audit` simulator until every required gate is green.{coord_note}\n\n"
        f"{ticket_md}\n"
    )


class UltraArenaDesktop:
    def __init__(self, cond_dir: Path, task_id: str, code_root: Path, coord_mode: str = "no_comm", record_video: bool = True):
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.coord_mode = coord_mode
        self.record_video = record_video
        self.meta = UA_BY_ID[task_id]
        self.roles: tuple[str, ...] = tuple(self.meta["roles"])
        self.workspace = cond_dir / "workspace"
        self.tickets_root = cond_dir / "tickets"
        self.versions_log = cond_dir / "version_timeline.jsonl"
        self.portal_state_out = cond_dir / "portal_state.json"
        self.container_name = f"paragui-ua-{task_id.lower()}-{secrets.token_hex(5)}"
        self.created = False
        self.recording = False
        self._stop_evt = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self.version_hashes: list[str] = []
        self._t0 = time.monotonic()

    def sync_permissions(self) -> None:
        if self.created:
            subprocess.run(["docker", "exec", self.container_name, "chmod", "-R", "a+rX,ug+w", "/workspace"], capture_output=True, timeout=20)

    def build_pristine(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.tickets_root.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
            "-v", f"{self.code_root}:/code:ro",
            "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.tickets_root}:/tickets",
            "-e", "PYTHONPATH=/code", "--entrypoint", "python3", DESKTOP_IMAGE,
            "-m", "tasks.ultra_arenas_v1.builders", "build",
            "--task", self.task_id, "--workspace", "/workspace", "--tickets-root", "/tickets",
        ], check=True, capture_output=True, text=True, timeout=300)
        if self.coord_mode == "shared_scratchpad":
            (self.workspace / ".coord/locks").mkdir(parents=True, exist_ok=True)
            (self.workspace / ".coord/SCRATCHPAD.md").write_text(f"# {self.task_id} Shared Scratchpad\n", encoding="utf-8")

    def start(self) -> None:
        self._t0 = time.monotonic()
        mounts = ["-v", f"{self.workspace}:/workspace"]
        for r in self.roles:
            mounts.extend(["-v", f"{self.tickets_root / r}:/var/tickets/{r}:ro"])
        # Desktop container has LIVE OUTBOUND INTERNET (no --network none) for real external websites!
        desk_cpus = os.environ.get("PARAGUI_UA_CPUS", "5")
        subprocess.run([
            "docker", "run", "-d", "--name", self.container_name,
            "--cpus", desk_cpus, "--memory", "8g", "--shm-size", "1g",
            "--security-opt", "no-new-privileges",
            "--label", "org.paragui.kind=ultra-arena-desktop",
            *mounts, DESKTOP_IMAGE, "sleep", "infinity",
        ], check=True, capture_output=True, text=True, timeout=90)
        self.created = True
        init_sh = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "id -u studio_ui >/dev/null 2>&1 || useradd -m -u 1001 -s /bin/bash studio_ui; "
            "mkdir -p /opt/ua_state /tmp/runtime-gui /tmp/runtime-studio /home/gui/Downloads /home/studio_ui/.config/chromium; "
            "chmod 700 /opt/ua_state /tmp/runtime-gui /tmp/runtime-studio /home/studio_ui; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chown -R 1001:1001 /tmp/runtime-studio /home/studio_ui; "
            "chmod -R g+rwX /workspace /home/gui && chmod 777 /home/gui/Downloads"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", init_sh], check=True, capture_output=True, timeout=30)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/ultra_arenas_v1/catalog.py"), f"{self.container_name}:/opt/ua_state/catalog.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/ultra_arenas_v1/flagship_30m.py"), f"{self.container_name}:/opt/ua_state/flagship_30m.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/ultra_arenas_v1/extreme_35m.py"), f"{self.container_name}:/opt/ua_state/extreme_35m.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/ultra_arenas_v1/engines.py"), f"{self.container_name}:/opt/ua_state/engines.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/thematic_arenas_v1/xlsx_utils.py"), f"{self.container_name}:/opt/ua_state/xlsx_utils.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "exec", self.container_name, "chmod", "700", "/opt/ua_state/catalog.py", "/opt/ua_state/flagship_30m.py", "/opt/ua_state/extreme_35m.py", "/opt/ua_state/engines.py", "/opt/ua_state/xlsx_utils.py"], check=True, capture_output=True, timeout=15)

        pport = int(self.meta["portal_port"])
        subprocess.run([
            "docker", "exec", "-d", self.container_name,
            "python3", "/opt/ua_state/engines.py",
            "--task", self.task_id, "--port", str(pport),
            "--workspace", "/workspace", "--state-dir", "/opt/ua_state", "--boot-file", "/opt/ua_state/boot_url",
        ], check=True, capture_output=True, timeout=20)
        for _ in range(40):
            chk = subprocess.run(["docker", "exec", self.container_name, "curl", "-fsS", f"http://127.0.0.1:{pport}/health"], capture_output=True, timeout=5)
            if chk.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"Ultra arena {self.task_id} portal failed health check")

        boot_x11 = "Xvfb :99 -screen 0 1280x720x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 1; export DISPLAY=:99; openbox >/tmp/openbox.log 2>&1 &"
        subprocess.run(["docker", "exec", "-d", "--user", "1000:0", "-e", "HOME=/home/gui", self.container_name, "bash", "-lc", boot_x11], check=True, capture_output=True, timeout=20)
        time.sleep(1.2)
        launch_chr = (
            "cp /opt/ua_state/boot_url /home/studio_ui/boot_url && rm -f /opt/ua_state/boot_url && "
            "chown 1001:1001 /home/studio_ui/boot_url && chmod 600 /home/studio_ui/boot_url && "
            "su -s /bin/bash studio_ui -c 'export DISPLAY=:99 HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/runtime-studio; "
            "u=$(cat /home/studio_ui/boot_url); rm -f /home/studio_ui/boot_url; "
            "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
            "--user-data-dir=/home/studio_ui/.config/chromium --window-size=1280,720 --window-position=0,0 \"$u\" >/tmp/studio_browser.log 2>&1 </dev/null &'"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", launch_chr], check=True, capture_output=True, timeout=25)
        time.sleep(3.0)
        self.exec_role(self.roles[0], "xdotool search --onlyvisible --name . | tail -n 1 | xargs -r -I{} wmctrl -i -r {} -b add,maximized_vert,maximized_horz || true", timeout_s=10)

        if self.record_video:
            rec_cmd = (
                "date +%s.%N > /tmp/rollout-start.txt; echo $$ > /tmp/rollout-ffmpeg.pid; "
                "exec ffmpeg -hide_banner -loglevel warning -nostdin -y "
                "-f x11grab -video_size 1280x720 -framerate 6 -draw_mouse 1 -i :99.0 "
                "-c:v libx264 -threads 2 -preset veryfast -crf 24 -pix_fmt yuv420p "
                "-t 5400 /tmp/rollout.mkv > /tmp/rollout-ffmpeg.log 2>&1"
            )
            subprocess.run(["docker", "exec", "-d", self.container_name, "bash", "-lc", rec_cmd], check=True, capture_output=True, timeout=20)
            self.recording = True
        self._sample_once()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _sample_once(self) -> None:
        canon = self.workspace / self.meta["canonical_project"]
        sha = ""
        if str(self.meta["canonical_project"]).endswith(".git/HEAD") and (self.workspace / "nexus-portal/.git").is_dir():
            cp = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=self.workspace / "nexus-portal", capture_output=True, text=True)
            sha = cp.stdout.strip()
        if canon.is_file():
            sha = sha or sha256_file(canon)
            if sha and (not self.version_hashes or self.version_hashes[-1] != sha):
                self.version_hashes.append(sha)
                with self.versions_log.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"timestamp": time.time(), "sha256": sha}) + "\n")

    def _watch_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._sample_once()
            except Exception:
                pass
            self._stop_evt.wait(0.4)

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 240) -> dict:
        try:
            cp = subprocess.run([
                "docker", "exec", "--user", "1000:0", "-w", cwd,
                "-e", "DISPLAY=:99", "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                "-e", f"AGENT_TICKET_DIR=/var/tickets/{role}",
                self.container_name, "bash", "-lc", "umask 0002; " + command_str,
            ], capture_output=True, text=True, timeout=timeout_s)
            return {"ok": cp.returncode == 0, "returncode": cp.returncode, "stdout": cp.stdout[-12000:], "stderr": cp.stderr[-6000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "stdout": "", "stderr": f"Timed out after {timeout_s}s"}
        finally:
            self.sync_permissions()

    def screenshot_base64(self) -> str:
        cp = subprocess.run(["docker", "exec", "--user", "1000:0", "-e", "DISPLAY=:99", self.container_name, "import", "-window", "root", "png:-"], capture_output=True, timeout=20)
        return base64.b64encode(cp.stdout).decode("ascii")

    def stop_and_grade(self, wall_override_s: float | None = None) -> tuple[dict, dict, int]:
        wall_s = wall_override_s if wall_override_s is not None else round(time.monotonic() - self._t0, 2)
        self._stop_evt.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=3)
        self._sample_once()
        pstate = {}
        try:
            if self.created:
                if self.recording:
                    subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "if [ -f /tmp/rollout-ffmpeg.pid ]; then kill -INT $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null || true; fi; sleep 1; ffmpeg -y -i /tmp/rollout.mkv -c copy -movflags +faststart /tmp/desktop-rollout.mp4 >/dev/null 2>&1 || true"], capture_output=True, timeout=45)
                    subprocess.run(["docker", "cp", f"{self.container_name}:/tmp/desktop-rollout.mp4", str(self.cond_dir / "desktop-rollout.mp4")], capture_output=True, timeout=30)
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/ua_state/portal_state.json", str(self.portal_state_out)], capture_output=True, timeout=15)
                if self.portal_state_out.is_file():
                    pstate = json.loads(self.portal_state_out.read_text(encoding="utf-8"))
        finally:
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=25)
                self.created = False
        if not self.portal_state_out.is_file():
            write_json(self.portal_state_out, {})
        grade_out = self.cond_dir / "grade.json"
        subprocess.run([
            "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
            "-v", f"{self.code_root}:/code:ro", "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.portal_state_out}:/portal_state.json:ro", "-v", f"{self.cond_dir}:/out",
            "-e", "PYTHONPATH=/code", "--entrypoint", "python3", DESKTOP_IMAGE,
            "-m", "tasks.ultra_arenas_v1.builders", "grade",
            "--task", self.task_id, "--workspace", "/workspace",
            "--portal-state", "/portal_state.json", "--wall-seconds", str(wall_s), "--out", "/out/grade.json",
        ], check=True, capture_output=True, text=True, timeout=420)
        return json.loads(grade_out.read_text(encoding="utf-8")), pstate, len(self.version_hashes)


def self_validate_ultra(task_id: str, out_dir: Path, code_root: Path) -> dict:
    meta = UA_BY_ID[task_id]
    cdir = out_dir / task_id
    if cdir.exists():
        shutil.rmtree(cdir, ignore_errors=True)
    d0 = UltraArenaDesktop(cdir / "pristine", task_id, code_root, record_video=False)
    d0.build_pristine()
    g0, _, _ = d0.stop_and_grade(wall_override_s=float(meta["critical_section_lower_bound_s"]))

    d1 = UltraArenaDesktop(cdir / "ref_pass", task_id, code_root, record_video=False)
    d1.build_pristine(); d1.start()
    try:
        subprocess.run(["docker", "exec", d1.container_name, "mkdir", "-p", "/tmp/ref_pkg"], check=True, capture_output=True)
        subprocess.run(["docker", "cp", str(code_root / "tasks"), f"{d1.container_name}:/tmp/ref_pkg/tasks"], check=True, capture_output=True)
        cp = d1.exec_role(d1.roles[0], f"PYTHONPATH=/tmp/ref_pkg python3 -m tasks.ultra_arenas_v1.builders solve_ref --task {task_id} --workspace /workspace", timeout_s=600)
        if not cp["ok"]:
            raise RuntimeError(f"{task_id} solve_ref failed: {cp['stderr']}")
    finally:
        g1, _, _ = d1.stop_and_grade()

    d2 = UltraArenaDesktop(cdir / "sim_race", task_id, code_root, record_video=False)
    d2.build_pristine(); d2.start()
    try:
        subprocess.run(["docker", "exec", d2.container_name, "mkdir", "-p", "/tmp/ref_pkg"], check=True, capture_output=True)
        subprocess.run(["docker", "cp", str(code_root / "tasks"), f"{d2.container_name}:/tmp/ref_pkg/tasks"], check=True, capture_output=True)
        cp = d2.exec_role(d2.roles[0], f"PYTHONPATH=/tmp/ref_pkg python3 -m tasks.ultra_arenas_v1.builders sim_race --task {task_id} --workspace /workspace", timeout_s=120)
        if not cp["ok"]:
            raise RuntimeError(f"{task_id} sim_race failed: {cp['stderr']}")
    finally:
        g2, _, _ = d2.stop_and_grade()

    ok = (not g0["joint_pass"]) and g1["joint_pass"] and g1["canary_passed"] and (not g2["joint_pass"]) and (not g2["canary_passed"])
    res = {
        "task_id": task_id,
        "pristine_pass": g0["joint_pass"],
        "ref_pass": g1["joint_pass"],
        "ref_rubric": g1["final_rubric_score"],
        "ref_gates": g1["gates"],
        "race_pass": g2["joint_pass"],
        "race_side_effects": g2["collateral_side_effects"]["total"],
        "valid_calibration": ok,
    }
    write_json(cdir / "self_validation.json", res)
    return res


def run_ultra_benchmark_case(task_id: str, coord_mode: str, out_dir: Path, code_root: Path, api_cfg: dict, codex_bin: Path) -> dict:
    meta = UA_BY_ID[task_id]
    roles = tuple(meta["roles"])
    cond_dir = out_dir / task_id / f"quad_concurrent_{coord_mode}"
    if (cond_dir / "report.json").is_file():
        ex = json.loads((cond_dir / "report.json").read_text(encoding="utf-8"))
        if ex.get("valid_model_run"):
            return ex
    if cond_dir.exists():
        shutil.rmtree(cond_dir, ignore_errors=True)
    cond_dir.mkdir(parents=True, exist_ok=True)

    desk = UltraArenaDesktop(cond_dir, task_id, code_root, coord_mode=coord_mode, record_video=True)
    desk.build_pristine(); desk.start()
    t0 = time.monotonic()
    t_lim = int(meta["conc_role_timeout_s"])
    actors: dict[str, dict] = {}
    bar = threading.Barrier(len(roles))
    try:
        with ThreadPoolExecutor(max_workers=len(roles)) as pool:
            futs = {}
            for r in roles:
                adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                alog = adir / "actions.jsonl"; alog.touch()
                tdir = desk.tickets_root / r
                ptxt = build_ultra_prompt(r, (tdir / "task.md").read_text(encoding="utf-8"), t_lim, coord_mode)
                h = make_arena_handlers(desk, r, alog, bar)
                futs[pool.submit(run_arena_actor, r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)] = r
            for fut in as_completed(futs):
                actors[futs[fut]] = fut.result()
    finally:
        wall_s = round(time.monotonic() - t0, 2)
        grade_res, pstate, ver_cnt = desk.stop_and_grade(wall_override_s=wall_s)

    # Compute real 4-agent overlap window & sum of active agent wall times
    sum_actor_wall_s = round(sum(a["wall_seconds"] for a in actors.values()), 2)
    awareness = analyze_race_awareness(cond_dir, roles)
    rep = {
        "task_id": task_id,
        "arena": meta["arena"],
        "coord_mode": coord_mode,
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "valid_model_run": all(a["status"] in {"done", "timeout"} for a in actors.values()),
        "joint_pass": grade_res["joint_pass"],
        "canary_passed": grade_res["canary_passed"],
        "milestone_score": grade_res["milestone_score"],
        "final_rubric_score": grade_res["final_rubric_score"],
        "drc_calls_count": grade_res["drc_calls_count"],
        "efficiency": grade_res["efficiency"],
        "collateral_side_effects": grade_res["collateral_side_effects"],
        "passed_roles_count": grade_res["passed_roles_count"],
        "gui_action_calls": sum(a["gui_action_calls"] for a in actors.values()),
        "gui_observation_calls": sum(a["gui_observation_calls"] for a in actors.values()),
        "cli_calls": sum(a["cli_calls"] for a in actors.values()),
        "distinct_project_versions": ver_cnt,
        "sum_actor_wall_seconds": sum_actor_wall_s,
        "wall_seconds": wall_s,
        "race_awareness": awareness,
        "actors": actors,
        "grade": grade_res,
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("self_validate", "benchmark"), default="self_validate")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--code-root", type=Path, required=True)
    p.add_argument("--api-json", type=Path, default=None)
    p.add_argument("--codex-bin", type=Path, default=Path("/codex/codex"))
    p.add_argument("--coord-mode", choices=("no_comm", "shared_scratchpad"), default="no_comm")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--tasks", nargs="*", default=[r["id"] for r in ULTRA_ARENAS_CATALOG])
    args = p.parse_args(argv)
    out_dir = args.out.resolve(); out_dir.mkdir(parents=True, exist_ok=True)
    code_root = args.code_root.resolve()

    if args.mode == "self_validate":
        res = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            fmap = {pool.submit(self_validate_ultra, tid, out_dir, code_root): tid for tid in args.tasks}
            for fut in as_completed(fmap):
                tid = fmap[fut]; r = fut.result(); res[tid] = r
                print(f"UA_VALIDATED {tid}: valid={r['valid_calibration']} ref_pass={r['ref_pass']} rub={r['ref_rubric']} race_pass={r['race_pass']}", flush=True)
        write_json(out_dir / "SELF_VALIDATION_SUMMARY.json", {"all_valid": all(v["valid_calibration"] for v in res.values()), "cases": dict(sorted(res.items()))})
        return 0 if all(v["valid_calibration"] for v in res.values()) else 1

    assert args.api_json is not None
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fmap = {pool.submit(run_ultra_benchmark_case, tid, args.coord_mode, out_dir, code_root, api_cfg, args.codex_bin.resolve()): tid for tid in args.tasks}
        for fut in as_completed(fmap):
            tid = fmap[fut]; rep = fut.result(); results[tid] = rep
            write_json(out_dir / "live-progress.json", {
                k: {
                    "joint_pass": v["joint_pass"], "canary": v["canary_passed"],
                    "milestone": v["milestone_score"], "rubric": v["final_rubric_score"],
                    "drc_calls": v["drc_calls_count"], "side_effects": v["collateral_side_effects"]["total"],
                    "wall_s": v["wall_seconds"], "sum_actor_s": v["sum_actor_wall_seconds"],
                } for k, v in sorted(results.items())
            })
            print(f"DONE {tid}: joint={rep['joint_pass']} canary={rep['canary_passed']} rub={rep['final_rubric_score']} drc={rep['drc_calls_count']} side={rep['collateral_side_effects']['total']} wall={rep['wall_seconds']}s sum_actor={rep['sum_actor_wall_seconds']}s", flush=True)
    write_json(out_dir / "SUMMARY.json", {
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "coord_mode": args.coord_mode,
        "joint_pass_count": sum(1 for v in results.values() if v["joint_pass"]),
        "total_tasks": len(results),
        "results": dict(sorted(results.items())),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

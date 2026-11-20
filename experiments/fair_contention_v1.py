"""Artisan 2-agent fair-contention runner with mandatory 4-gate bidirectional validation (strictly non-YOLO)."""
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
from experiments.thematic_arenas_v1 import run_arena_actor
from tasks.fair_contention_v1.common import role_scratch_dir, sha256_file, write_json
from tasks.fair_contention_v1.registry import FAIR_CONTENTION_CATALOG, FC_BY_ID, get_case_module

DESKTOP_IMAGE = os.environ.get("PARAGUI_FC_DESKTOP_IMAGE", "paragui/astra-recording-desktop:20261113")


def build_fair_dual_prompt(ticket_md: str, timeout_s: int) -> str:
    b = chr(96)
    return (
        f"You are operating an internet-connected Linux engineering workstation ({b}DISPLAY=:99{b}, {b}1280x720{b}) with production workspace {b}/workspace{b} (time budget: {timeout_s}s).\n"
        f"You have full GUI tools ({b}desktop{b}: {b}screenshot{b}, {b}click{b}, {b}type_text{b}, {b}key{b}, {b}wait{b}) and full workstation CLI ({b}guest_bash{b}).\n"
        f"Any reference files under {b}/session/ticket/{b} are mounted inside your local session container ({b}/session/ticket/{b}), while {b}/workspace{b} lives on the workstation via {b}guest_bash{b}.\n"
        f"Start with {b}desktop.screenshot{b} to inspect the open Chromium console on {b}DISPLAY=:99{b} and verify active UI context and {b}<canvas>{b} specifications (note: heavy {b}/api/bench/...{b} stages run multi-minute physical simulations; always pass {b}--max-time 350{b} to {b}curl{b}).\n\n"
        f"{ticket_md}\n"
    )


def make_fc_handlers(desk: "FairContentionDesktop", role: str, action_log: Path, barrier: threading.Barrier | None) -> dict:
    bar_done = {"v": False}
    log_lock = threading.Lock()

    def sync_once() -> None:
        if barrier is not None and not bar_done["v"]:
            bar_done["v"] = True
            try:
                barrier.wait(timeout=45)
            except threading.BrokenBarrierError:
                pass

    def log_act(tool_name: str, args: dict) -> None:
        with log_lock:
            with action_log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"timestamp": time.time(), "role": role, "tool": tool_name, "args": args}, ensure_ascii=False) + "\n")

    desktop_schemas = [
        {"name": "screenshot", "description": "Capture current 1280x720 X11 desktop screenshot.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "click", "description": "Click mouse button at (x, y).", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "integer", "default": 1}}, "required": ["x", "y"]}},
        {"name": "type_text", "description": "Type text into focused window.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
        {"name": "key", "description": "Send key press (e.g. Return, ctrl+l, Tab).", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
        {"name": "wait", "description": "Sleep seconds (max 15).", "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 2.0}}}},
    ]
    bash_schema = {
        "name": "guest_bash",
        "description": "Execute bash command on the workstation as UID 1000 in /workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "cwd": {"type": "string", "default": "/workspace"}, "timeout": {"type": "number", "default": 350}},
            "required": ["command"],
        },
    }

    def call_desktop(name: str, arguments: dict) -> dict:
        sync_once()
        log_act(f"desktop.{name}", arguments)
        if name == "screenshot":
            b64 = desk.screenshot_base64()
            return {"content": [{"type": "image", "data": b64, "mimeType": "image/png"}], "isError": False}
        if name == "click":
            x, y = int(arguments["x"]), int(arguments["y"])
            btn = int(arguments.get("button", 1))
            desk.exec_role(role, f"xdotool mousemove --sync {x} {y} click {btn}", timeout_s=15)
            time.sleep(0.25)
            b64 = desk.screenshot_base64()
            return {"content": [{"type": "text", "text": f"Clicked ({x},{y})"}, {"type": "image", "data": b64, "mimeType": "image/png"}], "isError": False}
        if name == "type_text":
            txt = shlex.quote(str(arguments["text"]))
            desk.exec_role(role, f"xdotool type --delay 18 -- {txt}", timeout_s=20)
            return {"content": [{"type": "text", "text": "Typed text"}], "isError": False}
        if name == "key":
            raw_k = str(arguments["key"]).strip()
            low_k = raw_k.lower().replace(" ", "")
            if low_k in ("f12", "ctrl+shift+i", "ctrl+shift+j", "ctrl+shift+c", "control+shift+i", "control+shift+j", "control+shift+c"):
                return {"content": [{"type": "text", "text": "Key blocked by enterprise browser policy"}], "isError": False}
            k = shlex.quote(raw_k)
            desk.exec_role(role, f"xdotool key --clearmodifiers {k}", timeout_s=15)
            return {"content": [{"type": "text", "text": f"Sent key {k}"}], "isError": False}
        if name == "wait":
            s = min(15.0, max(0.2, float(arguments.get("seconds", 2.0))))
            time.sleep(s)
            return {"content": [{"type": "text", "text": f"Waited {s}s"}], "isError": False}
        return {"content": [{"type": "text", "text": f"Unknown desktop tool {name}"}], "isError": True}

    def call_bash(_name: str, arguments: dict) -> dict:
        sync_once()
        log_act("guest_bash.guest_bash", arguments)
        t_lim = int(min(540, max(5, float(arguments.get("timeout", 350)))))
        cwd_val = str(arguments.get("cwd") or "/workspace")
        res = desk.exec_role(role, str(arguments["command"]), cwd=cwd_val, timeout_s=t_lim)
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
    }


class FairContentionDesktop:
    def __init__(self, cond_dir: Path, task_id: str, code_root: Path, record_video: bool = True, fast_selfval: bool = False):
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.record_video = record_video
        self.fast_selfval = fast_selfval
        self.meta = FC_BY_ID[task_id]
        self.roles: tuple[str, ...] = tuple(self.meta["roles"])
        assert len(self.roles) == 2, f"Expected strictly 2 roles, got {self.roles}"
        self.workspace = cond_dir / "workspace"
        self.x11_dir = cond_dir / "x11_unix"
        self.downloads_dir = cond_dir / "shared_downloads"
        self.tickets_root = cond_dir / "tickets"
        self.versions_log = cond_dir / "version_timeline.jsonl"
        self.portal_state_out = cond_dir / "portal_state.json"
        self.container_name = f"paragui-fc-{task_id.lower()}-{secrets.token_hex(5)}"
        self.role_containers: dict[str, str] = {}
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
            "-m", "tasks.fair_contention_v1.registry", "build",
            "--task", self.task_id, "--workspace", "/workspace", "--tickets-root", "/tickets",
        ], check=True, capture_output=True, text=True, timeout=300)

    def start(self) -> None:
        self._t0 = time.monotonic()
        self.x11_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.x11_dir, 0o777)
        os.chmod(self.downloads_dir, 0o777)
        desk_cpus = os.environ.get("PARAGUI_FC_CPUS", "8")
        subprocess.run([
            "docker", "run", "-d", "--name", self.container_name,
            "--cpus", desk_cpus, "--memory", "12g", "--shm-size", "1g",
            "--security-opt", "no-new-privileges",
            "--label", "org.paragui.kind=fair-contention-desktop",
            "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.x11_dir}:/tmp/.X11-unix",
            "-v", f"{self.downloads_dir}:/home/gui/Downloads",
            DESKTOP_IMAGE, "sleep", "infinity",
        ], check=True, capture_output=True, text=True, timeout=90)
        self.created = True
        init_sh = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "id -u studio_ui >/dev/null 2>&1 || useradd -m -u 1001 -s /bin/bash studio_ui; "
            "mkdir -p /opt/fc_state/pkg/tasks/thematic_arenas_v1 /tmp/runtime-gui /tmp/runtime-studio /home/gui/Downloads /home/studio_ui/.config/chromium; "
            "touch /opt/fc_state/pkg/tasks/__init__.py /opt/fc_state/pkg/tasks/thematic_arenas_v1/__init__.py; "
            "chown 0:0 /opt/fc_state && chmod 700 /opt/fc_state /tmp/runtime-gui /tmp/runtime-studio /home/studio_ui; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chown -R 1001:1001 /tmp/runtime-studio /home/studio_ui; "
            "chmod 1777 /tmp/.X11-unix && chmod -R g+rwX /workspace /home/gui && chown 0:0 /home/gui/Downloads && chmod 755 /home/gui/Downloads"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", init_sh], check=True, capture_output=True, timeout=30)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/fair_contention_v1"), f"{self.container_name}:/opt/fc_state/pkg/tasks/fair_contention_v1"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/thematic_arenas_v1/xlsx_utils.py"), f"{self.container_name}:/opt/fc_state/pkg/tasks/thematic_arenas_v1/xlsx_utils.py"], check=True, capture_output=True, timeout=20)
        if (self.tickets_root / "role_tokens.json").is_file():
            subprocess.run(["docker", "cp", str(self.tickets_root / "role_tokens.json"), f"{self.container_name}:/opt/fc_state/role_tokens.json"], check=True, capture_output=True, timeout=15)
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "chown -R 0:0 /opt/fc_state && chmod -R 700 /opt/fc_state"], check=True, capture_output=True, timeout=15)

        pport = int(self.meta["portal_port"])
        sim_cmd = ["docker", "exec", "-d", "-e", "PYTHONPATH=/opt/fc_state/pkg"]
        if self.fast_selfval:
            sim_cmd.extend(["-e", "PARAGUI_FC_FAST_SELFVAL=1"])
        for env_k, env_v in os.environ.items():
            if env_k.startswith("PARAGUI_FC") and env_k != "PARAGUI_FC_FAST_SELFVAL":
                sim_cmd.extend(["-e", f"{env_k}={env_v}"])
        sim_cmd.extend([
            self.container_name, "python3", "-m", "tasks.fair_contention_v1.registry", "simulate",
            "--task", self.task_id, "--port", str(pport),
            "--workspace", "/workspace", "--state-dir", "/opt/fc_state", "--boot-file", "/opt/fc_state/boot_url",
        ])
        subprocess.run(sim_cmd, check=True, capture_output=True, timeout=20)
        for _ in range(50):
            chk = subprocess.run(["docker", "exec", self.container_name, "curl", "-fsS", f"http://127.0.0.1:{pport}/health"], capture_output=True, timeout=5)
            if chk.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"Fair contention {self.task_id} portal failed health check")

        boot_x11 = (
            "mkdir -p /home/gui/.config/openbox; "
            "cat > /home/gui/.config/openbox/rc.xml <<'OBEOF'\n"
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<openbox_config xmlns=\"http://openbox.org/3.4/rc\"><keyboard>"
            "<keybind key=\"F12\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "<keybind key=\"C-S-I\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "<keybind key=\"C-S-J\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "<keybind key=\"C-S-C\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "<keybind key=\"C-U\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "</keyboard></openbox_config>\nOBEOF\n"
            "Xvfb :99 -screen 0 1280x720x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 1; "
            "export DISPLAY=:99; xmodmap -e 'keycode 96 = NoSymbol' >/dev/null 2>&1 || true; openbox --config-file /home/gui/.config/openbox/rc.xml >/tmp/openbox.log 2>&1 &"
        )
        subprocess.run(["docker", "exec", "-d", "--user", "1000:0", "-e", "HOME=/home/gui", self.container_name, "bash", "-lc", boot_x11], check=True, capture_output=True, timeout=20)
        time.sleep(1.2)
        launch_chr = (
            "cp /opt/fc_state/boot_url /home/studio_ui/boot_url && rm -f /opt/fc_state/boot_url && "
            "chown 1001:1001 /home/studio_ui/boot_url && chmod 600 /home/studio_ui/boot_url && "
            "su -s /bin/bash studio_ui -c 'export DISPLAY=:99 HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/runtime-studio; "
            "u=$(cat /home/studio_ui/boot_url); rm -f /home/studio_ui/boot_url; "
            "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
            "--user-data-dir=/home/studio_ui/.config/chromium --window-size=1280,720 --window-position=0,0 \"$u\" >/tmp/studio_browser.log 2>&1 </dev/null &'"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", launch_chr], check=True, capture_output=True, timeout=25)
        time.sleep(2.5)
        for r_idx, r_name in enumerate(self.roles):
            rc_name = f"{self.container_name}-r{r_idx}"
            subprocess.run([
                "docker", "run", "-d", "--name", rc_name,
                "--cpus", "4", "--memory", "6g", "--shm-size", "512m",
                "--security-opt", "no-new-privileges",
                "--network", f"container:{self.container_name}",
                "--label", "org.paragui.kind=fair-contention-role-user",
                "-v", f"{self.workspace}:/workspace",
                "-v", f"{self.x11_dir}:/tmp/.X11-unix",
                "-v", f"{self.downloads_dir}:/home/gui/Downloads",
                DESKTOP_IMAGE, "sleep", "infinity",
            ], check=True, capture_output=True, text=True, timeout=60)
            self.role_containers[r_name] = rc_name
            r_init = (
                "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
                "mkdir -p /tmp/runtime-gui /home/gui/work; "
                "chown -R 1000:0 /tmp/runtime-gui /home/gui"
            )
            subprocess.run(["docker", "exec", rc_name, "bash", "-lc", r_init], check=True, capture_output=True, timeout=20)
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
        if str(self.meta["canonical_project"]).endswith(".git/HEAD"):
            git_root = canon.parent.parent
            if (git_root / ".git").is_dir():
                cp = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=git_root, capture_output=True, text=True)
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

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 355) -> dict:
        jdir = role_scratch_dir(self.task_id, role)
        target_ctr = self.role_containers.get(role, self.container_name)
        try:
            cp = subprocess.run([
                "docker", "exec", "--user", "1000:0", "-w", cwd,
                "-e", "DISPLAY=:99", "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                "-e", "HISTFILE=/dev/null", "-e", f"TMPDIR={jdir}",
                target_ctr, "bash", "-lc", f"mkdir -p {jdir}; umask 0002; " + command_str,
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
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/fc_state/portal_state.json", str(self.portal_state_out)], capture_output=True, timeout=15)
                if self.portal_state_out.is_file():
                    pstate = json.loads(self.portal_state_out.read_text(encoding="utf-8"))
        finally:
            for rc_name in list(self.role_containers.values()):
                subprocess.run(["docker", "rm", "-f", rc_name], capture_output=True, timeout=20)
            self.role_containers.clear()
            if self.created:
                subprocess.run(["docker", "exec", self.container_name, "chmod", "-R", "a+rwX", "/workspace", "/home/gui/Downloads", "/tmp/.X11-unix"], capture_output=True, timeout=15)
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
            "-m", "tasks.fair_contention_v1.registry", "grade",
            "--task", self.task_id, "--workspace", "/workspace",
            "--portal-state", "/portal_state.json", "--wall-seconds", str(wall_s), "--out", "/out/grade.json",
        ], check=True, capture_output=True, text=True, timeout=300)
        return json.loads(grade_out.read_text(encoding="utf-8")), pstate, len(self.version_hashes)


def self_validate_fair_case(task_id: str, out_dir: Path, code_root: Path) -> dict:
    """Enforce all 4 mandatory gates: pristine_fail + seq(A->B)_pass + seq(B->A)_pass + sim_race_fail + transparency."""
    cdir = out_dir / task_id
    if cdir.exists():
        subprocess.run(["docker", "run", "--rm", "-v", f"{out_dir}:/out", "--entrypoint", "bash", DESKTOP_IMAGE, "-lc", f"rm -rf /out/{task_id}"], capture_output=True, timeout=30)
        shutil.rmtree(cdir, ignore_errors=True)
    meta = FC_BY_ID[task_id]
    role_a, role_b = meta["roles"]
    mod = get_case_module(task_id)
    trans = mod.audit_case_transparency()

    # Gate 1: Pristine negative control
    d0 = FairContentionDesktop(cdir / "pristine", task_id, code_root, record_video=False, fast_selfval=True)
    d0.build_pristine()
    g0, _, _ = d0.stop_and_grade(wall_override_s=0.0)

    def _run_root_cmd(desk: FairContentionDesktop, subcmd: list[str], timeout_s: int = 420) -> None:
        cp = subprocess.run(
            ["docker", "exec", "-e", "PYTHONPATH=/opt/fc_state/pkg", desk.container_name, "python3", "-m", "tasks.fair_contention_v1.registry", *subcmd],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if cp.returncode != 0:
            raise RuntimeError(f"{task_id} {subcmd} failed (rc={cp.returncode}): {cp.stderr[-1200:] or cp.stdout[-1200:]}")

    # Gate 2a: Forward sequential positive control seq(A -> B)
    d_ab = FairContentionDesktop(cdir / "seq_ab", task_id, code_root, record_video=False, fast_selfval=True)
    d_ab.build_pristine()
    d_ab.start()
    try:
        _run_root_cmd(d_ab, ["solve_role", "--task", task_id, "--role", role_a, "--workspace", "/workspace"])
        _run_root_cmd(d_ab, ["solve_role", "--task", task_id, "--role", role_b, "--workspace", "/workspace"])
    finally:
        g_ab, _, _ = d_ab.stop_and_grade()

    # Gate 2b: Reverse sequential positive control seq(B -> A)
    d_ba = FairContentionDesktop(cdir / "seq_ba", task_id, code_root, record_video=False, fast_selfval=True)
    d_ba.build_pristine()
    d_ba.start()
    try:
        _run_root_cmd(d_ba, ["solve_role", "--task", task_id, "--role", role_b, "--workspace", "/workspace"])
        _run_root_cmd(d_ba, ["solve_role", "--task", task_id, "--role", role_a, "--workspace", "/workspace"])
    finally:
        g_ba, _, _ = d_ba.stop_and_grade()

    # Gate 3: Naive concurrent race negative control
    d_race = FairContentionDesktop(cdir / "sim_race", task_id, code_root, record_video=False, fast_selfval=True)
    d_race.build_pristine()
    d_race.start()
    try:
        _run_root_cmd(d_race, ["sim_race", "--task", task_id, "--workspace", "/workspace"])
    finally:
        g_race, _, _ = d_race.stop_and_grade()

    all_gates_ok = (
        (not g0["joint_pass"])
        and bool(g_ab["joint_pass"])
        and bool(g_ba["joint_pass"])
        and (not g_race["joint_pass"])
        and bool(trans["ok"])
    )
    res = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "conflict_archetype": meta["conflict_archetype"],
        "roles": [role_a, role_b],
        "gate1_pristine_pass": g0["joint_pass"],
        "gate2a_seq_ab_pass": g_ab["joint_pass"],
        "gate2a_invariants": g_ab["invariants"],
        "gate2b_seq_ba_pass": g_ba["joint_pass"],
        "gate2b_invariants": g_ba["invariants"],
        "gate3_sim_race_pass": g_race["joint_pass"],
        "gate3_race_invariants": g_race["invariants"],
        "gate4_protocol_transparency": trans,
        "all_4_gates_valid": all_gates_ok,
    }
    write_json(cdir / "self_validation.json", res)
    return res


def run_fair_case(task_id: str, mode: str, out_dir: Path, code_root: Path, api_cfg: dict, codex_bin: Path) -> dict:
    meta = FC_BY_ID[task_id]
    model_slug = str(api_cfg.get("model", "gpt-6.1-sol")).replace(".", "_")
    cond_name = f"{mode}_{model_slug}"
    cond_dir = out_dir / task_id / cond_name
    if (cond_dir / "report.json").is_file():
        ex = json.loads((cond_dir / "report.json").read_text(encoding="utf-8"))
        if ex.get("valid_model_run"):
            return ex
    if cond_dir.exists():
        subprocess.run(["docker", "run", "--rm", "-v", f"{cond_dir.parent}:/p", "--entrypoint", "bash", DESKTOP_IMAGE, "-lc", f"rm -rf /p/{cond_name}"], capture_output=True, timeout=30)
        shutil.rmtree(cond_dir, ignore_errors=True)
    cond_dir.mkdir(parents=True, exist_ok=True)

    desk = FairContentionDesktop(cond_dir, task_id, code_root, record_video=True, fast_selfval=False)
    desk.build_pristine()
    desk.start()
    t0 = time.monotonic()
    roles = tuple(meta["roles"])
    actors: dict[str, dict] = {}
    try:
        if mode == "benchmark":
            t_lim = int(meta["conc_role_timeout_s"])
            bar = threading.Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futs = {}
                for r in roles:
                    adir = cond_dir / f"actor_{r}"
                    adir.mkdir(parents=True, exist_ok=True)
                    alog = adir / "actions.jsonl"
                    alog.touch()
                    tdir = desk.tickets_root / r
                    ptxt = build_fair_dual_prompt((tdir / "task.md").read_text(encoding="utf-8"), t_lim)
                    h = make_fc_handlers(desk, r, alog, bar)
                    futs[pool.submit(run_arena_actor, r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)] = r
                for fut in as_completed(futs):
                    actors[futs[fut]] = fut.result()
        else:
            seq_roles = roles if mode == "seq_ab" else (roles[1], roles[0])
            t_lim = int(meta["seq_role_timeout_s"])
            for r in seq_roles:
                adir = cond_dir / f"actor_{r}"
                adir.mkdir(parents=True, exist_ok=True)
                alog = adir / "actions.jsonl"
                alog.touch()
                tdir = desk.tickets_root / r
                ptxt = build_fair_dual_prompt((tdir / "task.md").read_text(encoding="utf-8"), t_lim)
                h = make_fc_handlers(desk, r, alog, None)
                actors[r] = run_arena_actor(r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)
    finally:
        wall_s = round(time.monotonic() - t0, 2)
        grade_res, _pstate, ver_cnt = desk.stop_and_grade(wall_override_s=wall_s)

    sum_actor_s = round(sum(a["wall_seconds"] for a in actors.values()), 2)
    awareness = analyze_race_awareness(cond_dir, roles)
    aware_cnt = sum(1 for rv in (awareness.get("roles") or {}).values() if rv.get("explicit_race_mentions", 0) > 0)
    rep = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "conflict_archetype": meta["conflict_archetype"],
        "concurrency_agents": 2,
        "mode": mode,
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "valid_model_run": all(a["status"] in {"done", "timeout"} for a in actors.values()),
        "joint_pass": grade_res["joint_pass"],
        "unaware_race_failure": grade_res["unaware_race_failure"],
        "local_completion_rate": grade_res["local_completion_rate"],
        "closed_tickets_count": grade_res["closed_tickets_count"],
        "cross_role_invariant_score": grade_res["cross_role_invariant_score"],
        "invariants": grade_res["invariants"],
        "total_bench_calls": grade_res["total_bench_calls"],
        "session_hijacks": grade_res["session_hijacks"],
        "download_overwrites": grade_res["download_overwrites"],
        "gui_action_calls": sum(a["gui_action_calls"] for a in actors.values()),
        "gui_observation_calls": sum(a["gui_observation_calls"] for a in actors.values()),
        "cli_calls": sum(a["cli_calls"] for a in actors.values()),
        "distinct_project_versions": ver_cnt,
        "sum_actor_wall_seconds": sum_actor_s,
        "wall_seconds": wall_s,
        "explicit_race_aware_roles_count": aware_cnt,
        "race_awareness": awareness,
        "actors": actors,
        "grade": grade_res,
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("self_validate", "benchmark", "seq_ab", "seq_ba"), default="self_validate")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--code-root", type=Path, required=True)
    p.add_argument("--api-json", type=Path, default=None)
    p.add_argument("--codex-bin", type=Path, default=Path("/codex/codex"))
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--tasks", nargs="*", default=[r["id"] for r in FAIR_CONTENTION_CATALOG])
    args = p.parse_args(argv)
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    code_root = args.code_root.resolve()

    if args.mode == "self_validate":
        res = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            fmap = {pool.submit(self_validate_fair_case, tid, out_dir, code_root): tid for tid in args.tasks}
            for fut in as_completed(fmap):
                tid = fmap[fut]
                r = fut.result()
                res[tid] = r
                print(
                    f"FC_VALIDATED {tid}: all_4_gates={r['all_4_gates_valid']} "
                    f"pristine={r['gate1_pristine_pass']} seq_ab={r['gate2a_seq_ab_pass']} "
                    f"seq_ba={r['gate2b_seq_ba_pass']} sim_race={r['gate3_sim_race_pass']} "
                    f"transparent={r['gate4_protocol_transparency']['ok']}",
                    flush=True,
                )
        write_json(out_dir / "SELF_VALIDATION_SUMMARY.json", {
            "all_valid": all(v["all_4_gates_valid"] for v in res.values()),
            "cases": dict(sorted(res.items())),
        })
        return 0 if all(v["all_4_gates_valid"] for v in res.values()) else 1

    assert args.api_json is not None
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fmap = {pool.submit(run_fair_case, tid, args.mode, out_dir, code_root, api_cfg, args.codex_bin.resolve()): tid for tid in args.tasks}
        for fut in as_completed(fmap):
            tid = fmap[fut]
            rep = fut.result()
            results[tid] = rep
            write_json(out_dir / "live-progress.json", {
                k: {
                    "mode": v["mode"],
                    "model": v["model"],
                    "joint_pass": v["joint_pass"],
                    "closed": v["closed_tickets_count"],
                    "inv_score": v["cross_role_invariant_score"],
                    "bench_calls": v["total_bench_calls"],
                    "aware_roles": v["explicit_race_aware_roles_count"],
                    "wall_s": v["wall_seconds"],
                } for k, v in sorted(results.items())
            })
            print(
                f"DONE {tid} [{rep['mode']}|{rep['model']}]: joint={rep['joint_pass']} "
                f"closed={rep['closed_tickets_count']}/2 inv={rep['cross_role_invariant_score']} "
                f"bench={rep['total_bench_calls']} aware={rep['explicit_race_aware_roles_count']}/2 "
                f"wall={rep['wall_seconds']}s",
                flush=True,
            )
    write_json(out_dir / f"SUMMARY_{args.mode}.json", {
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "mode": args.mode,
        "concurrency_agents": 2,
        "joint_pass_count": sum(1 for v in results.values() if v["joint_pass"]),
        "total_tasks": len(results),
        "results": dict(sorted(results.items())),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

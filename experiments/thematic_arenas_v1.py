"""Containerized non-YOLO 4-agent runner & zero-LLM validator for Thematic Arenas (TA-A1..TA-E1)."""
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

from experiments.codesk_container_codex import (
    CONTAINER_ENTRY_SOURCE,
    DEFAULT_CODEX_BINARY,
    DEFAULT_CONTAINER_IMAGE,
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    codex_requirements_mount,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.deepseek_v41_eval import analyze_race_awareness, start_dsv41_relay
from experiments.long_horizon_v1 import build_lh_config_template, start_lh_relay
from tasks.thematic_arenas_v1.catalog import TA_BY_ID, THEMATIC_ARENAS_CATALOG
from tasks.thematic_arenas_v1.suite import sha256_file, write_json

DESKTOP_IMAGE = os.environ.get("PARAGUI_ARENA_DESKTOP_IMAGE", "paragui/astra-recording-desktop:20261113")


def build_arena_prompt(role: str, ticket_md: str, timeout_s: int, coord_mode: str) -> str:
    coord_block = ""
    if coord_mode == "shared_scratchpad":
        coord_block = (
            "\nSHARED COORDINATION SCRATCHPAD ENABLED:\n"
            "- Multiple colleague agents may be working concurrently on this same workstation.\n"
            "- A shared coordination directory `/workspace/.coord/` (`SCRATCHPAD.md` and `/workspace/.coord/locks/`) is available.\n"
            "- Before mutating shared state (BI filters, shared Downloads, `.xlsx` sheets, Git index, Staging redeploys, Cluster restarts, or CAE solver), check and update `/workspace/.coord/SCRATCHPAD.md` or use `flock` under `/workspace/.coord/locks/` so your agreements survive context compaction.\n"
        )
    return (
        f"You are engineering/operations agent `{role}` working on a live Linux desktop (`DISPLAY=:99`, `1280x720`) with `/workspace`.\n"
        "You have BOTH full GUI (`desktop`: `screenshot`, `click`, `move`, `type_text`, `key`, `scroll`, `wait`) AND full CLI (`guest_bash`).\n"
        "Important visual specifications, audit restatements, and telemetry are rendered onto the live Chromium `<canvas>` on `DISPLAY=:99` — take a `desktop.screenshot` to read exact codes, weights, and thresholds.\n"
        f"Complete all requirements in your assigned ticket within {timeout_s}s without corrupting shared deliverables.{coord_block}\n\n"
        f"=== ASSIGNED TICKET ({role}) ===\n{ticket_md}\n"
    )


def make_arena_handlers(desk: "ThematicArenaDesktop", role: str, action_log: Path, barrier: threading.Barrier | None) -> dict:
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
        "description": "Execute bash command on the shared workstation as UID 1000 in /workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "cwd": {"type": "string", "default": "/workspace"}, "timeout": {"type": "number", "default": 240}},
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
            k = shlex.quote(str(arguments["key"]))
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
        t_lim = int(min(340, max(5, float(arguments.get("timeout", 240)))))
        cwd_val = str(arguments.get("cwd") or "/workspace")
        res = desk.exec_role(role, str(arguments["command"]), cwd=cwd_val, timeout_s=t_lim)
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
    }


class ThematicArenaDesktop:
    def __init__(self, cond_dir: Path, task_id: str, code_root: Path, coord_mode: str = "no_comm", record_video: bool = True):
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.coord_mode = coord_mode
        self.record_video = record_video
        self.meta = TA_BY_ID[task_id]
        self.roles: tuple[str, ...] = tuple(self.meta["roles"])
        self.workspace = cond_dir / "workspace"
        self.tickets_root = cond_dir / "tickets"
        self.versions_log = cond_dir / "version_timeline.jsonl"
        self.portal_state_out = cond_dir / "portal_state.json"
        self.container_name = f"paragui-arena-{task_id.lower()}-{secrets.token_hex(5)}"
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
            "-e", "PYTHONPATH=/code",
            "--entrypoint", "python3",
            DESKTOP_IMAGE,
            "-m", "tasks.thematic_arenas_v1.suite", "build",
            "--task", self.task_id,
            "--workspace", "/workspace",
            "--tickets-root", "/tickets",
        ], check=True, capture_output=True, text=True, timeout=240)
        if self.coord_mode == "shared_scratchpad":
            cdir = self.workspace / ".coord/locks"
            cdir.mkdir(parents=True, exist_ok=True)
            (self.workspace / ".coord/SCRATCHPAD.md").write_text(
                f"# {self.task_id} Shared Coordination Scratchpad\n\nRecord active critical-section ownership and completed milestones below.\n",
                encoding="utf-8",
            )

    def start(self) -> None:
        self._t0 = time.monotonic()
        mounts = ["-v", f"{self.workspace}:/workspace"]
        for r in self.roles:
            mounts.extend(["-v", f"{self.tickets_root / r}:/var/tickets/{r}:ro"])
        subprocess.run([
            "docker", "run", "-d", "--name", self.container_name,
            "--network", "none", "--cpus", "4", "--memory", "6g", "--shm-size", "1g",
            "--security-opt", "no-new-privileges",
            "--label", "org.paragui.kind=arena-desktop",
            *mounts, DESKTOP_IMAGE, "sleep", "infinity",
        ], check=True, capture_output=True, text=True, timeout=90)
        self.created = True
        init_users = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "id -u studio_ui >/dev/null 2>&1 || useradd -m -u 1001 -s /bin/bash studio_ui; "
            "mkdir -p /opt/arena_state /tmp/runtime-gui /tmp/runtime-studio /home/gui/Downloads /home/studio_ui/.config/chromium; "
            "chmod 700 /opt/arena_state /tmp/runtime-gui /tmp/runtime-studio /home/studio_ui; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chown -R 1001:1001 /tmp/runtime-studio /home/studio_ui; "
            "chmod -R g+rwX /workspace /home/gui && chmod 777 /home/gui/Downloads"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", init_users], check=True, capture_output=True, timeout=30)
        for fname in ("catalog.py", "services.py"):
            subprocess.run(["docker", "cp", str(self.code_root / f"tasks/thematic_arenas_v1/{fname}"), f"{self.container_name}:/opt/arena_state/{fname}"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "exec", self.container_name, "chmod", "700", "/opt/arena_state/catalog.py", "/opt/arena_state/services.py"], check=True, capture_output=True, timeout=15)

        pport = int(self.meta["portal_port"])
        subprocess.run([
            "docker", "exec", "-d", self.container_name,
            "python3", "/opt/arena_state/services.py",
            "--task", self.task_id,
            "--port", str(pport),
            "--workspace", "/workspace",
            "--state-dir", "/opt/arena_state",
            "--boot-file", "/opt/arena_state/boot_url",
        ], check=True, capture_output=True, timeout=20)
        for _ in range(35):
            chk = subprocess.run(["docker", "exec", self.container_name, "curl", "-fsS", f"http://127.0.0.1:{pport}/health"], capture_output=True, timeout=5)
            if chk.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"Arena portal {self.task_id} failed health check")

        boot_x11 = "Xvfb :99 -screen 0 1280x720x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 1; export DISPLAY=:99; openbox >/tmp/openbox.log 2>&1 &"
        subprocess.run(["docker", "exec", "-d", "--user", "1000:0", "-e", "HOME=/home/gui", self.container_name, "bash", "-lc", boot_x11], check=True, capture_output=True, timeout=20)
        time.sleep(1.2)
        launch_browser = (
            "cp /opt/arena_state/boot_url /home/studio_ui/boot_url && rm -f /opt/arena_state/boot_url && "
            "chown 1001:1001 /home/studio_ui/boot_url && chmod 600 /home/studio_ui/boot_url && "
            "su -s /bin/bash studio_ui -c 'export DISPLAY=:99 HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/runtime-studio; "
            "u=$(cat /home/studio_ui/boot_url); rm -f /home/studio_ui/boot_url; "
            "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
            "--user-data-dir=/home/studio_ui/.config/chromium --window-size=1280,720 --window-position=0,0 --app=\"$u\" >/tmp/studio_browser.log 2>&1 </dev/null &'"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", launch_browser], check=True, capture_output=True, timeout=25)
        time.sleep(2.5)
        self.exec_role(self.roles[0], "xdotool search --onlyvisible --name . | tail -n 1 | xargs -r -I{} wmctrl -i -r {} -b add,maximized_vert,maximized_horz || true", timeout_s=10)

        if self.record_video:
            rec_cmd = (
                "date +%s.%N > /tmp/rollout-start.txt; echo $$ > /tmp/rollout-ffmpeg.pid; "
                "exec ffmpeg -hide_banner -loglevel warning -nostdin -y "
                "-f x11grab -video_size 1280x720 -framerate 8 -draw_mouse 1 -i :99.0 "
                "-c:v libx264 -threads 2 -preset veryfast -crf 23 -pix_fmt yuv420p "
                "-t 2700 /tmp/rollout.mkv > /tmp/rollout-ffmpeg.log 2>&1"
            )
            subprocess.run(["docker", "exec", "-d", self.container_name, "bash", "-lc", rec_cmd], check=True, capture_output=True, timeout=20)
            self.recording = True
        self._sample_once()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _sample_once(self) -> None:
        canon = self.workspace / self.meta["canonical_project"]
        if canon.is_file():
            sha = sha256_file(canon)
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
            self._stop_evt.wait(0.3)

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 210) -> dict:
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
                    subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "if [ -f /tmp/rollout-ffmpeg.pid ]; then kill -INT $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null || true; fi; sleep 1; ffmpeg -y -i /tmp/rollout.mkv -c copy -movflags +faststart /tmp/desktop-rollout.mp4 >/dev/null 2>&1 || true"], capture_output=True, timeout=35)
                    subprocess.run(["docker", "cp", f"{self.container_name}:/tmp/desktop-rollout.mp4", str(self.cond_dir / "desktop-rollout.mp4")], capture_output=True, timeout=25)
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/arena_state/portal_state.json", str(self.portal_state_out)], capture_output=True, timeout=15)
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
            "-v", f"{self.code_root}:/code:ro",
            "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.portal_state_out}:/portal_state.json:ro",
            "-v", f"{self.cond_dir}:/out",
            "-e", "PYTHONPATH=/code",
            "--entrypoint", "python3",
            DESKTOP_IMAGE,
            "-m", "tasks.thematic_arenas_v1.suite", "grade",
            "--task", self.task_id,
            "--workspace", "/workspace",
            "--portal-state", "/portal_state.json",
            "--wall-seconds", str(wall_s),
            "--out", "/out/grade.json",
        ], check=True, capture_output=True, text=True, timeout=180)
        return json.loads(grade_out.read_text(encoding="utf-8")), pstate, len(self.version_hashes)


def run_arena_actor(
    role: str,
    handlers: dict,
    actor_dir: Path,
    ticket_dir: Path,
    prompt_text: str,
    api_cfg: dict,
    codex_bin: Path,
    timeout_s: int,
) -> dict:
    raw_model = str(api_cfg.get("model", "gpt-6.1-sol"))
    is_deepseek = raw_model.startswith("deepseek")
    codex_model = "deepseek-v4.1" if is_deepseek else raw_model
    upstream_model = raw_model if is_deepseek else str(api_cfg.get("upstream_model_sol") or api_cfg.get("upstream_model") or raw_model)
    effort = str(api_cfg.get("reasoning_effort", "high"))
    session_dir = actor_dir / "container_session"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")
    write_json(session_dir / "codex-home/models-catalog.json", {"models": [{
        "slug": codex_model,
        "display_name": codex_model,
        "description": "Thematic Arena hybrid GUI+CLI desktop agent.",
        "default_reasoning_level": effort,
        "supported_reasoning_levels": [{"effort": lv, "description": lv} for lv in ("low", "medium", "high", "xhigh")],
        "shell_type": "unified_exec",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 1,
        "additional_speed_tiers": [],
        "service_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "model_messages": None,
        "include_skills_usage_instructions": False,
        "include_plugin_usage_instructions": False,
        "include_apps_usage_instructions": False,
        "default_reasoning_summary": "none",
        "support_verbosity": False,
        "default_verbosity": "low",
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": "text_and_image",
        "truncation_policy": {"mode": "tokens", "limit": 10000},
        "supports_parallel_tool_calls": False,
        "supports_image_detail_original": True,
        "context_window": 262144,
        "max_context_window": 262144,
        "comp_hash": "",
        "effective_context_window_percent": 95,
        "experimental_supported_tools": [],
        "input_modalities": ["text", "image"],
        "supports_search_tool": False,
        "use_responses_lite": False,
        "tool_mode": "direct",
        "multi_agent_version": "v2",
        "base_instructions": "You are a senior hybrid GUI+CLI workstation agent. Complete your assigned ticket accurately while preserving shared deliverables.",
    }]})
    tmpl = build_lh_config_template(codex_model, effort)
    validate_container_config_text(tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(tmpl, encoding="utf-8")
    (session_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o770 if item.is_dir() else 0o660)
        except OSError:
            pass

    if is_deepseek:
        relay_srv, relay_port = start_dsv41_relay(api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl", codex_model=codex_model, upstream_model=upstream_model)
    else:
        relay_srv, relay_port = start_lh_relay(api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl", model_name=codex_model, upstream_model=upstream_model)
    bridge = HostActorBridge(None, relay_port, handlers, image_history_keep=4, max_request_images=24)
    bridge.start()
    cname = f"paragui-arena-codex-{role.lower()}-{secrets.token_hex(5)}"
    create_cmd = [
        "docker", "create", "--name", cname, "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,size=256m", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "2048", "--cpus", "2", "--memory", "3g", "--user", "1000:0",
        "--label", "org.paragui.kind=arena-codex-actor",
        "-v", f"{session_dir}:/session", "-v", f"{session_dir / 'bridge'}:/bridge:ro",
        "-v", f"{ticket_dir}:/session/ticket:ro", "-v", f"{bridge.ipc_dir}:/ipc",
        "-v", f"{codex_bin.parent}:/codex:ro", "-w", "/session",
        "-e", "HOME=/session", "-e", "CODEX_HOME=/session/codex-home",
        "-e", "CODESK_CONTAINER_PERMISSION_MODE=container-unrestricted",
        "-e", "TOKIO_WORKER_THREADS=4", "-e", "PYTHONDONTWRITEBYTECODE=1",
        *codex_requirements_mount(), DEFAULT_CONTAINER_IMAGE, "python3", "/bridge/container_entry.py",
    ]
    t_start = time.time()
    cid = None
    timed_out = False
    try:
        cid = subprocess.run(create_cmd, check=True, capture_output=True, text=True, timeout=45).stdout.strip()
        with (actor_dir / "stdout.log").open("w", encoding="utf-8") as out_f, (actor_dir / "stderr.log").open("w", encoding="utf-8") as err_f:
            proc = subprocess.Popen(["docker", "start", "-a", cid], stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f, start_new_session=True)
            while proc.poll() is None:
                if time.time() - t_start > timeout_s:
                    timed_out = True
                    subprocess.run(["docker", "kill", cid], capture_output=True, timeout=15)
                    proc.wait(timeout=10)
                    break
                time.sleep(0.5)
        t_end = time.time()
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{session_dir}:/session", DEFAULT_CONTAINER_IMAGE, "chmod", "-R", "ug+rwX", "/session"], capture_output=True, timeout=20)
        audit = verify_container_permission_audit(session_dir, expected_model=codex_model, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        action_log = actor_dir / "actions.jsonl"
        acts = [json.loads(ln) for ln in action_log.read_text(encoding="utf-8").splitlines() if ln.strip()] if action_log.is_file() else []
        gui_obs = sum(1 for a in acts if a["tool"] in {"desktop.screenshot", "desktop.wait"})
        gui_act = sum(1 for a in acts if a["tool"].startswith("desktop.") and a["tool"] not in {"desktop.screenshot", "desktop.wait"})
        cli_c = sum(1 for a in acts if a["tool"].startswith("guest_bash."))
        return {
            "role": role,
            "status": "timeout" if timed_out else ("done" if proc.returncode == 0 else "error"),
            "exit_code": proc.returncode,
            "wall_seconds": round(t_end - t_start, 2),
            "gui_observation_calls": gui_obs,
            "gui_action_calls": gui_act,
            "cli_calls": cli_c,
            "permission_audit_ok": True,
        }
    finally:
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20)
        bridge.close()
        relay_srv.shutdown()
        relay_srv.server_close()


def self_validate_case(task_id: str, out_dir: Path, code_root: Path) -> dict:
    meta = TA_BY_ID[task_id]
    roles = tuple(meta["roles"])
    case_dir = out_dir / task_id
    if case_dir.exists():
        shutil.rmtree(case_dir, ignore_errors=True)

    # 1. Pristine check
    d_pris = ThematicArenaDesktop(case_dir / "pristine", task_id, code_root, record_video=False)
    d_pris.build_pristine()
    g_pris, _, _ = d_pris.stop_and_grade(wall_override_s=float(meta["critical_section_lower_bound_s"]))

    # 2. Sequential cooperative reference solve against live services
    d_seq = ThematicArenaDesktop(case_dir / "sequential_ref", task_id, code_root, record_video=False)
    d_seq.build_pristine(); d_seq.start()
    try:
        subprocess.run(["docker", "exec", d_seq.container_name, "mkdir", "-p", "/tmp/ref_pkg"], check=True, capture_output=True, timeout=10)
        subprocess.run(["docker", "cp", str(code_root / "tasks"), f"{d_seq.container_name}:/tmp/ref_pkg/tasks"], check=True, capture_output=True, timeout=20)
        for r in roles:
            cp = d_seq.exec_role(r, f"PYTHONPATH=/tmp/ref_pkg python3 -c \"from tasks.thematic_arenas_v1.solvers import solve_role; from pathlib import Path; solve_role('{task_id}', '{r}', Path('/workspace'))\"", timeout_s=120)
            if not cp["ok"]:
                raise RuntimeError(f"{task_id} ref role {r} failed: {cp['stderr']}")
    finally:
        g_seq, _, _ = d_seq.stop_and_grade()

    # 3. Simulated uncoordinated race + delayed canary / side-effect verification
    d_race = ThematicArenaDesktop(case_dir / "simulated_race", task_id, code_root, record_video=False)
    d_race.build_pristine(); d_race.start()
    try:
        subprocess.run(["docker", "exec", d_race.container_name, "mkdir", "-p", "/tmp/ref_pkg"], check=True, capture_output=True, timeout=10)
        subprocess.run(["docker", "cp", str(code_root / "tasks"), f"{d_race.container_name}:/tmp/ref_pkg/tasks"], check=True, capture_output=True, timeout=20)
        cp = d_race.exec_role(roles[0], f"PYTHONPATH=/tmp/ref_pkg python3 -c \"from tasks.thematic_arenas_v1.solvers import simulate_uncoordinated_race; from pathlib import Path; simulate_uncoordinated_race('{task_id}', Path('/workspace'))\"", timeout_s=120)
        if not cp["ok"]:
            raise RuntimeError(f"{task_id} race sim failed: {cp['stderr']}")
    finally:
        g_race, _, _ = d_race.stop_and_grade()

    res = {
        "task_id": task_id,
        "pristine_joint_pass": g_pris["joint_pass"],
        "pristine_canary": g_pris["canary_passed"],
        "seq_ref_joint_pass": g_seq["joint_pass"],
        "seq_ref_canary": g_seq["canary_passed"],
        "seq_ref_rubric": g_seq["final_rubric_score"],
        "seq_ref_milestones": g_seq["milestone_score"],
        "seq_ref_side_effects": g_seq["collateral_side_effects"]["total"],
        "race_joint_pass": g_race["joint_pass"],
        "race_canary": g_race["canary_passed"],
        "race_side_effects": g_race["collateral_side_effects"]["total"],
        "valid_calibration": bool(
            (not g_pris["joint_pass"])
            and g_seq["joint_pass"]
            and g_seq["canary_passed"]
            and g_seq["collateral_side_effects"]["total"] == 0
            and (not g_race["joint_pass"])
            and (not g_race["canary_passed"])
            and g_race["collateral_side_effects"]["total"] > 0
        ),
    }
    write_json(case_dir / "self_validation.json", res)
    return res


def run_benchmark_case(
    task_id: str,
    condition: str,
    coord_mode: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict,
    codex_bin: Path,
    record_video: bool = True,
) -> dict:
    meta = TA_BY_ID[task_id]
    roles = tuple(meta["roles"])
    cond_dir = out_dir / task_id / f"{condition}_{coord_mode}"
    if (cond_dir / "report.json").is_file():
        ex = json.loads((cond_dir / "report.json").read_text(encoding="utf-8"))
        if ex.get("valid_model_run"):
            return ex
    if cond_dir.exists():
        shutil.rmtree(cond_dir, ignore_errors=True)
    cond_dir.mkdir(parents=True, exist_ok=True)

    desk = ThematicArenaDesktop(cond_dir, task_id, code_root, coord_mode=coord_mode, record_video=record_video)
    desk.build_pristine(); desk.start()
    t0 = time.monotonic()
    t_lim = int(meta["conc_role_timeout_s"])
    actors: dict[str, dict] = {}
    try:
        if condition == "seq_4role":
            for r in roles:
                adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                alog = adir / "actions.jsonl"; alog.touch()
                tdir = desk.tickets_root / r
                ptxt = build_arena_prompt(r, (tdir / "task.md").read_text(encoding="utf-8"), t_lim, coord_mode)
                h = make_arena_handlers(desk, r, alog, None)
                actors[r] = run_arena_actor(r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)
        elif condition == "quad_concurrent":
            bar = threading.Barrier(len(roles))
            with ThreadPoolExecutor(max_workers=len(roles)) as pool:
                futs = {}
                for r in roles:
                    adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                    alog = adir / "actions.jsonl"; alog.touch()
                    tdir = desk.tickets_root / r
                    ptxt = build_arena_prompt(r, (tdir / "task.md").read_text(encoding="utf-8"), t_lim, coord_mode)
                    h = make_arena_handlers(desk, r, alog, bar)
                    futs[pool.submit(run_arena_actor, r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)] = r
                for fut in as_completed(futs):
                    actors[futs[fut]] = fut.result()
        else:
            raise ValueError(condition)
        wall_s = round(time.monotonic() - t0, 2)
    finally:
        wall_s = round(time.monotonic() - t0, 2)
        grade_res, _pstate, ver_cnt = desk.stop_and_grade(wall_override_s=wall_s)

    awareness = analyze_race_awareness(cond_dir, roles)
    rep = {
        "task_id": task_id,
        "arena": meta["arena"],
        "variant": meta["variant"],
        "condition": condition,
        "coord_mode": coord_mode,
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "valid_model_run": all(a["status"] in {"done", "timeout"} for a in actors.values()),
        "joint_pass": grade_res["joint_pass"],
        "canary_passed": grade_res["canary_passed"],
        "milestone_score": grade_res["milestone_score"],
        "final_rubric_score": grade_res["final_rubric_score"],
        "efficiency": grade_res["efficiency"],
        "collateral_side_effects": grade_res["collateral_side_effects"],
        "passed_roles_count": grade_res["passed_roles_count"],
        "gui_action_calls": sum(a["gui_action_calls"] for a in actors.values()),
        "gui_observation_calls": sum(a["gui_observation_calls"] for a in actors.values()),
        "cli_calls": sum(a["cli_calls"] for a in actors.values()),
        "distinct_project_versions": ver_cnt,
        "race_awareness": awareness,
        "actors": actors,
        "grade": grade_res,
        "wall_seconds": wall_s,
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("self_validate", "benchmark", "rescore"), default="self_validate")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--code-root", type=Path, required=True)
    p.add_argument("--api-json", type=Path, default=None)
    p.add_argument("--codex-bin", type=Path, default=DEFAULT_CODEX_BINARY)
    p.add_argument("--condition", choices=("quad_concurrent", "seq_4role"), default="quad_concurrent")
    p.add_argument("--coord-mode", choices=("no_comm", "shared_scratchpad"), default="no_comm")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--tasks", nargs="*", default=[r["id"] for r in THEMATIC_ARENAS_CATALOG])
    args = p.parse_args(argv)
    out_dir = args.out.resolve(); out_dir.mkdir(parents=True, exist_ok=True)
    code_root = args.code_root.resolve()

    if args.mode == "rescore":
        results = {}
        for tid in args.tasks:
            cdir = out_dir / tid / f"{args.condition}_{args.coord_mode}"
            rep = json.loads((cdir / "report.json").read_text(encoding="utf-8"))
            subprocess.run([
                "docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "4g",
                "-v", f"{code_root}:/code:ro", "-v", f"{cdir / 'workspace'}:/workspace",
                "-v", f"{cdir / 'portal_state.json'}:/portal_state.json:ro", "-v", f"{cdir}:/out",
                "-e", "PYTHONPATH=/code", "--entrypoint", "python3", DESKTOP_IMAGE,
                "-m", "tasks.thematic_arenas_v1.suite", "grade",
                "--task", tid, "--workspace", "/workspace", "--portal-state", "/portal_state.json",
                "--wall-seconds", str(rep["wall_seconds"]), "--out", "/out/grade.json",
            ], check=True)
            g = json.loads((cdir / "grade.json").read_text(encoding="utf-8"))
            rep.update({
                "joint_pass": g["joint_pass"], "canary_passed": g["canary_passed"],
                "milestone_score": g["milestone_score"], "final_rubric_score": g["final_rubric_score"],
                "efficiency": g["efficiency"], "collateral_side_effects": g["collateral_side_effects"],
                "passed_roles_count": g["passed_roles_count"], "grade": g,
            })
            write_json(cdir / "report.json", rep)
            results[tid] = rep
            print(f"RESCORED {tid}: joint={g['joint_pass']} canary={g['canary_passed']} ms={g['milestone_score']} rub={g['final_rubric_score']} eff={g['efficiency']['efficiency_score']} side={g['collateral_side_effects']['total']} wall={rep['wall_seconds']}s", flush=True)
        write_json(out_dir / "SUMMARY.json", {
            "model": next(iter(results.values()))["model"] if results else "unknown",
            "condition": args.condition, "coord_mode": args.coord_mode,
            "joint_pass_count": sum(1 for v in results.values() if v["joint_pass"]),
            "total_tasks": len(results), "results": dict(sorted(results.items())),
        })
        return 0

    if args.mode == "self_validate":
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            fmap = {pool.submit(self_validate_case, tid, out_dir, code_root): tid for tid in args.tasks}
            for fut in as_completed(fmap):
                tid = fmap[fut]
                r = fut.result()
                results[tid] = r
                print(f"VALIDATED {tid}: valid={r['valid_calibration']} seq_pass={r['seq_ref_joint_pass']} race_pass={r['race_joint_pass']} race_side_effects={r['race_side_effects']}", flush=True)
        write_json(out_dir / "SELF_VALIDATION_SUMMARY.json", {"all_valid": all(v["valid_calibration"] for v in results.values()), "cases": dict(sorted(results.items()))})
        return 0 if all(v["valid_calibration"] for v in results.values()) else 1

    assert args.api_json is not None, "--api-json required for benchmark mode"
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fmap = {
            pool.submit(run_benchmark_case, tid, args.condition, args.coord_mode, out_dir, code_root, api_cfg, args.codex_bin.resolve()): tid
            for tid in args.tasks
        }
        for fut in as_completed(fmap):
            tid = fmap[fut]
            rep = fut.result()
            results[tid] = rep
            write_json(out_dir / "live-progress.json", {
                k: {
                    "joint_pass": v["joint_pass"],
                    "canary": v["canary_passed"],
                    "milestone": v["milestone_score"],
                    "rubric": v["final_rubric_score"],
                    "eff": v["efficiency"]["efficiency_score"],
                    "side_effects": v["collateral_side_effects"]["total"],
                    "wall_s": v["wall_seconds"],
                } for k, v in sorted(results.items())
            })
            print(f"DONE {tid} ({args.condition}/{args.coord_mode}): joint={rep['joint_pass']} canary={rep['canary_passed']} ms={rep['milestone_score']} rub={rep['final_rubric_score']} eff={rep['efficiency']['efficiency_score']} side={rep['collateral_side_effects']['total']} wall={rep['wall_seconds']}s", flush=True)
    write_json(out_dir / "SUMMARY.json", {
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "condition": args.condition,
        "coord_mode": args.coord_mode,
        "joint_pass_count": sum(1 for v in results.values() if v["joint_pass"]),
        "total_tasks": len(results),
        "results": dict(sorted(results.items())),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

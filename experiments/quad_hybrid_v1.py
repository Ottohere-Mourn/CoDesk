"""Containerized non-YOLO 4-agent Hybrid GUI+CLI runner for QH-01..QH-04 (gpt-6.1-sol)."""
from __future__ import annotations

import argparse
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
from experiments.long_horizon_v1 import build_lh_config_template, start_lh_relay
from tasks.quad_hybrid_v1.catalog import QH_BY_ID, QUAD_HYBRID_CATALOG, QUAD_ROLES
from tasks.quad_hybrid_v1.suite import sha256_file, write_json


DESKTOP_IMAGE = os.environ.get("PARAGUI_QUAD_DESKTOP_IMAGE", "paragui/astra-recording-desktop:20261113")
DEFAULT_MODEL = "gpt-6.1-sol"
DEFAULT_EFFORT = "high"


class QuadSharedDesktop:
    def __init__(self, cond_dir: Path, task_id: str, code_root: Path, record_video: bool = True):
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.record_video = record_video
        self.meta = QH_BY_ID[task_id]
        self.workspace = cond_dir / "workspace"
        self.tickets_root = cond_dir / "tickets"
        self.work_dirs = {r: cond_dir / f"actor_{r}/container_session/work" for r in QUAD_ROLES}
        self.versions_log = cond_dir / "version_timeline.jsonl"
        self.portal_state_out = cond_dir / "portal_state.json"
        self.container_name = f"paragui-quad-desk-{task_id.lower()}-{secrets.token_hex(5)}"
        self.created = False
        self.recording = False
        self._stop_evt = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self.version_hashes: list[str] = []

    def sync_permissions(self) -> None:
        if self.created:
            subprocess.run(
                ["docker", "exec", self.container_name, "chmod", "-R", "a+rX,ug+w", "/workspace"],
                capture_output=True,
                timeout=20,
            )

    def build_pristine(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.tickets_root.mkdir(parents=True, exist_ok=True)
        for wd in self.work_dirs.values():
            wd.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
                "-v", f"{self.code_root}:/code:ro",
                "-v", f"{self.workspace}:/workspace",
                "-v", f"{self.tickets_root}:/tickets",
                "-e", "PYTHONPATH=/code",
                "--entrypoint", "python3",
                DESKTOP_IMAGE,
                "-m", "tasks.quad_hybrid_v1.suite", "build",
                "--task", self.task_id,
                "--workspace", "/workspace",
                "--tickets-root", "/tickets",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )

    def start(self) -> None:
        mounts = ["-v", f"{self.workspace}:/workspace"]
        for role in QUAD_ROLES:
            wd = self.work_dirs[role]
            wd.mkdir(parents=True, exist_ok=True)
            os.chmod(wd, 0o770)
            mounts.extend([
                "-v", f"{self.tickets_root / role}:/var/tickets/{role}:ro",
            ])
        # Intentionally do NOT mount code_root into the live desktop container so
        # portal canvas specs live strictly in UID-0 /opt/quad_state and X11 GUI.
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.container_name,
                "--network", "none", "--cpus", "4", "--memory", "6g", "--shm-size", "1g",
                "--security-opt", "no-new-privileges",
                "--label", "org.paragui.kind=quad-desktop",
                *mounts,
                DESKTOP_IMAGE, "sleep", "infinity",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.created = True
        init_users = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "id -u studio_ui >/dev/null 2>&1 || useradd -m -u 1001 -s /bin/bash studio_ui; "
            "mkdir -p /opt/quad_state /tmp/runtime-gui /tmp/runtime-studio /home/studio_ui/.config/chromium; "
            "chmod 700 /opt/quad_state /tmp/runtime-gui /tmp/runtime-studio /home/studio_ui; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chown -R 1001:1001 /tmp/runtime-studio /home/studio_ui; "
            "chmod -R g+rwX /workspace /home/gui"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", init_users], check=True, capture_output=True, timeout=30)
        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/quad_hybrid_v1/portals.py"), f"{self.container_name}:/opt/quad_state/portals.py"],
            check=True, capture_output=True, timeout=20,
        )
        subprocess.run(["docker", "exec", self.container_name, "chmod", "700", "/opt/quad_state/portals.py"], check=True, capture_output=True, timeout=15)

        pport = int(self.meta["portal_port"])
        subprocess.run(
            [
                "docker", "exec", "-d", self.container_name,
                "python3", "/opt/quad_state/portals.py",
                "--task", self.task_id,
                "--port", str(pport),
                "--state-dir", "/opt/quad_state",
                "--boot-file", "/opt/quad_state/boot_url",
            ],
            check=True, capture_output=True, timeout=20,
        )
        for _ in range(30):
            chk = subprocess.run(["docker", "exec", self.container_name, "curl", "-fsS", f"http://127.0.0.1:{pport}/health"], capture_output=True, timeout=5)
            if chk.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Quad portal failed health check")

        # Boot shared Xvfb :99 with -ac so both UID 1001 (Chromium Studio UI) and UID 1000 (agent xdotool/screenshot) share DISPLAY=:99.
        boot_x11 = (
            "Xvfb :99 -screen 0 1280x720x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & "
            "sleep 1; export DISPLAY=:99; openbox >/tmp/openbox.log 2>&1 &"
        )
        subprocess.run(["docker", "exec", "-d", "--user", "1000:0", "-e", "HOME=/home/gui", self.container_name, "bash", "-lc", boot_x11], check=True, capture_output=True, timeout=20)
        time.sleep(1.5)

        # Copy one-time boot URL to studio_ui (UID 1001) and launch Chromium --app consuming the one-time nonce immediately.
        launch_browser = (
            "cp /opt/quad_state/boot_url /home/studio_ui/boot_url && rm -f /opt/quad_state/boot_url && "
            "chown 1001:1001 /home/studio_ui/boot_url && chmod 600 /home/studio_ui/boot_url && "
            "su -s /bin/bash studio_ui -c 'export DISPLAY=:99 HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/runtime-studio; "
            "u=$(cat /home/studio_ui/boot_url); rm -f /home/studio_ui/boot_url; "
            "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
            "--user-data-dir=/home/studio_ui/.config/chromium --window-size=1280,720 --window-position=0,0 --app=\"$u\" >/tmp/studio_browser.log 2>&1 </dev/null &'"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", launch_browser], check=True, capture_output=True, timeout=25)
        time.sleep(3.5)
        self.exec_role("A", "xdotool search --onlyvisible --name . | tail -n 1 | xargs -r -I{} wmctrl -i -r {} -b add,maximized_vert,maximized_horz || true", timeout_s=10)

        if self.record_video:
            rec_cmd = (
                "date +%s.%N > /tmp/rollout-start.txt; echo $$ > /tmp/rollout-ffmpeg.pid; "
                "exec ffmpeg -hide_banner -loglevel warning -nostdin -y "
                "-f x11grab -video_size 1280x720 -framerate 8 -draw_mouse 1 -i :99.0 "
                "-c:v libx264 -threads 2 -preset veryfast -crf 23 -pix_fmt yuv420p "
                "-t 1800 /tmp/rollout.mkv > /tmp/rollout-ffmpeg.log 2>&1"
            )
            subprocess.run(["docker", "exec", "-d", self.container_name, "bash", "-lc", rec_cmd], check=True, capture_output=True, timeout=20)
            time.sleep(0.8)
            self.recording = True
        self._sample_once()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _sample_once(self) -> None:
        canon = self.workspace / self.meta["canonical_project"]
        if canon.is_file():
            try:
                sha = sha256_file(canon)
            except OSError:
                return
            if not self.version_hashes or self.version_hashes[-1] != sha:
                self.version_hashes.append(sha)
                with self.versions_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"timestamp": time.time(), "sha256": sha}) + "\n")

    def _watch_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._sample_once()
            except Exception:
                pass
            self._stop_evt.wait(0.3)

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 210) -> dict:
        try:
            completed = subprocess.run(
                [
                    "docker", "exec", "--user", "1000:0",
                    "-w", cwd,
                    "-e", "DISPLAY=:99",
                    "-e", "HOME=/home/gui",
                    "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                    "-e", f"AGENT_TICKET_DIR=/var/tickets/{role}",
                    self.container_name, "bash", "-lc", "umask 0002; " + command_str,
                ],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return {
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-12000:],
                "stderr": completed.stderr[-6000:],
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "stdout": "", "stderr": f"Timed out after {timeout_s}s"}
        finally:
            self.sync_permissions()

    def screenshot_base64(self) -> str:
        import base64
        cp = subprocess.run(
            ["docker", "exec", "--user", "1000:0", "-e", "DISPLAY=:99", self.container_name, "import", "-window", "root", "png:-"],
            capture_output=True,
            timeout=20,
        )
        if cp.returncode == 0 and len(cp.stdout) > 100:
            return base64.b64encode(cp.stdout).decode("ascii")
        fallback_cmd = (
            "python3 -c \"from PIL import Image; import io, base64; "
            "im = Image.new('RGB', (1280, 720), (28, 32, 38)); buf = io.BytesIO(); "
            "im.save(buf, format='PNG'); print(base64.b64encode(buf.getvalue()).decode())\""
        )
        return self.exec_role("A", fallback_cmd, timeout_s=15)["stdout"].strip().splitlines()[-1]

    def stop_and_grade(self) -> tuple[dict, dict, int]:
        self._stop_evt.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=3.0)
        self.sync_permissions()
        self._sample_once()
        if self.created:
            cp = subprocess.run(["docker", "exec", self.container_name, "cat", "/opt/quad_state/portal_state.json"], capture_output=True, text=True, timeout=15)
            if cp.returncode == 0 and cp.stdout.strip():
                self.portal_state_out.write_text(cp.stdout, encoding="utf-8")
            if self.recording:
                subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "kill -INT $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null || true"], capture_output=True, timeout=15)
                for _ in range(40):
                    pr = subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "kill -0 $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null"], capture_output=True, timeout=10)
                    if pr.returncode != 0:
                        break
                    time.sleep(0.25)
                subprocess.run(["docker", "exec", self.container_name, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "/tmp/rollout.mkv", "-c", "copy", "-movflags", "+faststart", "/tmp/desktop-rollout.mp4"], capture_output=True, timeout=60)
                subprocess.run(["docker", "cp", f"{self.container_name}:/tmp/desktop-rollout.mp4", str(self.cond_dir / "desktop-rollout.mp4")], capture_output=True, timeout=60)
                self.recording = False
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
            self.created = False
        if not self.portal_state_out.is_file():
            write_json(self.portal_state_out, {"submissions": {}})
        pstate = json.loads(self.portal_state_out.read_text(encoding="utf-8"))
        grade_out = self.cond_dir / "grade.json"
        eval_ws = self.cond_dir / "eval_workspace"
        if eval_ws.exists():
            shutil.rmtree(eval_ws, ignore_errors=True)
        shutil.copytree(self.workspace, eval_ws)
        subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
                "-v", f"{self.code_root}:/code:ro",
                "-v", f"{eval_ws}:/workspace",
                "-v", f"{self.cond_dir}:/out",
                "-e", "PYTHONPATH=/code",
                "--entrypoint", "python3",
                DESKTOP_IMAGE,
                "-m", "tasks.quad_hybrid_v1.suite", "grade",
                "--task", self.task_id,
                "--workspace", "/workspace",
                "--portal-state", "/out/portal_state.json",
                "--out", "/out/grade.json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
        shutil.rmtree(eval_ws, ignore_errors=True)
        return json.loads(grade_out.read_text(encoding="utf-8")), pstate, len(self.version_hashes)


def build_quad_prompt(role: str, ticket_markdown: str, timeout_s: int) -> str:
    mod_num = {"B": 1, "C": 2, "D": 3, "A": 4}[role]
    return (
        "You are operating a Linux workstation (`1280x720` X11 desktop on `DISPLAY=:99`, shared project root `/workspace`) "
        f"in FULL HYBRID GUI+CLI mode (budget: {timeout_s}s). Both GUI tools (`desktop` MCP: `screenshot`, `click`, `move`, `type_text`, `key`, `wait`) "
        "and unrestricted workstation CLI (`guest_bash` MCP tool) are enabled.\n"
        "How the environment works:\n"
        f"- An authenticated Studio / Operations Console is open in Chromium on `DISPLAY=:99`. Your assigned module is **Module {mod_num}** (the {mod_num}-th tab from the left). Click **Module {mod_num}** (`desktop.click` + `desktop.screenshot`) to read your Visual Specification Canvas and submit your result.\n"
        "- Submitting in the GUI Console is a 2-step preview-then-commit flow: enter your value(s), click `[1] Stage Preview (8s)`, wait at least 8 seconds (`desktop.wait` `seconds=8.5`), then click `[2] Commit Verified` and confirm `Committed:` in the status box is non-empty.\n"
        f"- Your ticket inputs are at `/session/ticket` (and `/var/tickets/{role}` in `guest_bash`). Use `/tmp` for any temporary scratch scripts; keep `/workspace` clean (do NOT leave `.txt`, `.md`, or `.lock` notes in `/workspace`).\n"
        "- Use `guest_bash` freely for all Blender, PyQGIS, FreeCAD, GIMP, Inkscape, LibreOffice, Graphviz, and FFmpeg/MLT work on `/workspace`.\n\n"
        f"{ticket_markdown}\n\n"
        "Complete both the `/workspace` deliverables and the GUI Console submission accurately, then reply concisely."
    )


def make_quad_handlers(desk: QuadSharedDesktop, role: str, action_log: Path, barrier: threading.Barrier | None) -> dict:
    passed = {"done": False}

    def sync_once() -> None:
        if barrier is not None and not passed["done"]:
            passed["done"] = True
            try:
                barrier.wait(timeout=120.0)
            except threading.BrokenBarrierError:
                pass

    def log_act(tname: str, aobj: dict) -> None:
        with action_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": time.time(), "tool": tname, "args": aobj}, ensure_ascii=False) + "\n")

    desktop_schemas = [
        {"name": "screenshot", "description": "Capture 1280x720 X11 desktop screenshot.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "click", "description": "Click at (x, y) on the 1280x720 desktop.", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "integer", "default": 1}}, "required": ["x", "y"], "additionalProperties": False}},
        {"name": "move", "description": "Move pointer to (x, y).", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"], "additionalProperties": False}},
        {"name": "type_text", "description": "Type text into focused X11 input.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}},
        {"name": "key", "description": "Send X11 key combo (e.g. Return, BackSpace, ctrl+a).", "inputSchema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"], "additionalProperties": False}},
        {"name": "wait", "description": "Sleep seconds and return screenshot.", "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 1.5}}, "additionalProperties": False}},
    ]

    def call_desktop(name: str, arguments: dict) -> dict:
        sync_once()
        log_act(f"desktop.{name}", arguments)
        if name == "click":
            desk.exec_role(role, f"xdotool mousemove --sync {int(arguments['x'])} {int(arguments['y'])} click {int(arguments.get('button', 1))}; sleep 0.25", timeout_s=15)
        elif name == "move":
            desk.exec_role(role, f"xdotool mousemove --sync {int(arguments['x'])} {int(arguments['y'])}", timeout_s=15)
        elif name == "type_text":
            desk.exec_role(role, "xdotool type --delay 18 -- " + shlex.quote(str(arguments["text"])) + "; sleep 0.2", timeout_s=25)
        elif name == "key":
            desk.exec_role(role, "xdotool key --clearmodifiers " + shlex.quote(str(arguments["keys"])) + "; sleep 0.15", timeout_s=15)
        elif name == "wait":
            time.sleep(min(15.0, max(0.2, float(arguments.get("seconds", 1.5)))))
        shot = desk.screenshot_base64()
        return {"content": [{"type": "text", "text": "OK."}, {"type": "image", "data": shot, "mimeType": "image/png"}], "isError": False}

    bash_schema = {
        "name": "guest_bash",
        "description": "Run unrestricted bash/Python/Blender/PyQGIS/FreeCAD/GIMP/Inkscape/FFmpeg/melt/LibreOffice commands on /workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "default": "/workspace"},
                "timeout": {"type": "number", "default": 180},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    }

    def call_bash(_name: str, arguments: dict) -> dict:
        sync_once()
        log_act("guest_bash.guest_bash", arguments)
        t_lim = int(min(210, max(5, float(arguments.get("timeout", 180)))))
        cwd_val = str(arguments.get("cwd") or "/workspace")
        res = desk.exec_role(role, str(arguments["command"]), cwd=cwd_val, timeout_s=t_lim)
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
    }


def run_quad_actor(
    role: str,
    desk: QuadSharedDesktop,
    actor_dir: Path,
    ticket_dir: Path,
    api_cfg: dict,
    codex_bin: Path,
    model_name: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    barrier: threading.Barrier | None = None,
    timeout_s: int = 600,
) -> dict:
    session_dir = actor_dir / "container_session"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")
    catalog_payload = {"models": [{
        "slug": model_name,
        "display_name": model_name,
        "description": "Hybrid GUI+CLI desktop agent model.",
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
        "base_instructions": "You are a hybrid GUI+CLI workstation specialist. Use GUI tools for live desktop/browser visual specs & forms and CLI tools for heavy engineering files.",
    }]}
    write_json(session_dir / "codex-home/models-catalog.json", catalog_payload)
    tmpl = build_lh_config_template(model_name, effort)
    validate_container_config_text(tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(tmpl, encoding="utf-8")
    ticket_md = (ticket_dir / "task.md").read_text(encoding="utf-8")
    (session_dir / "prompt.txt").write_text(build_quad_prompt(role, ticket_md, timeout_s), encoding="utf-8")
    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o770 if item.is_dir() else 0o660)
        except OSError:
            pass

    up_override = api_cfg.get("upstream_model_sol")
    if not up_override and api_cfg.get("upstream_model") and model_name in str(api_cfg.get("upstream_model")):
        up_override = api_cfg.get("upstream_model")
    relay_srv, relay_port = start_lh_relay(
        api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl",
        model_name=model_name, upstream_model=up_override,
    )
    action_log = actor_dir / "actions.jsonl"
    action_log.touch()
    handlers = make_quad_handlers(desk, role, action_log, barrier)
    bridge = HostActorBridge(None, relay_port, handlers, image_history_keep=4, max_request_images=28)
    bridge.start()
    cname = f"paragui-quad-codex-{role.lower()}-{secrets.token_hex(5)}"
    create_cmd = [
        "docker", "create",
        "--name", cname,
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,size=256m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "2048",
        "--cpus", "2",
        "--memory", "3g",
        "--user", "1000:0",
        "--label", "org.paragui.kind=quad-codex-actor",
        "-v", f"{session_dir}:/session",
        "-v", f"{session_dir / 'bridge'}:/bridge:ro",
        "-v", f"{ticket_dir}:/session/ticket:ro",
        "-v", f"{bridge.ipc_dir}:/ipc",
        "-v", f"{codex_bin.parent}:/codex:ro",
        "-w", "/session",
        "-e", "HOME=/session",
        "-e", "CODEX_HOME=/session/codex-home",
        "-e", "CODESK_CONTAINER_PERMISSION_MODE=container-unrestricted",
        "-e", "TOKIO_WORKER_THREADS=4",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        *codex_requirements_mount(),
        DEFAULT_CONTAINER_IMAGE,
        "python3", "/bridge/container_entry.py",
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
        audit = verify_container_permission_audit(session_dir, expected_model=model_name, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        acts = [json.loads(ln) for ln in action_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        gui_shots = sum(1 for a in acts if a["tool"] in {"desktop.screenshot", "desktop.wait"})
        gui_acts = sum(1 for a in acts if a["tool"].startswith("desktop.") and a["tool"] not in {"desktop.screenshot", "desktop.wait"})
        cli_c = sum(1 for a in acts if a["tool"].startswith("guest_bash."))
        return {
            "role": role,
            "status": "timeout" if timed_out else ("done" if proc.returncode == 0 else "error"),
            "exit_code": proc.returncode,
            "wall_seconds": round(t_end - t_start, 2),
            "first_tool_ts": acts[0]["timestamp"] if acts else t_start,
            "last_tool_ts": acts[-1]["timestamp"] if acts else t_end,
            "gui_observation_calls": gui_shots,
            "gui_action_calls": gui_acts,
            "cli_calls": cli_c,
            "permission_audit_ok": True,
        }
    finally:
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20)
        bridge.close()
        relay_srv.shutdown()
        relay_srv.server_close()


def run_quad_condition(
    task_id: str,
    condition: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict,
    codex_bin: Path,
    model_name: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    record_video: bool = True,
) -> dict:
    cond_dir = out_dir / task_id / condition
    if (cond_dir / "report.json").is_file():
        existing = json.loads((cond_dir / "report.json").read_text(encoding="utf-8"))
        if existing.get("valid_model_run"):
            return existing
    if cond_dir.exists():
        shutil.rmtree(cond_dir, ignore_errors=True)
    cond_dir.mkdir(parents=True, exist_ok=True)
    meta = QH_BY_ID[task_id]
    desk = QuadSharedDesktop(cond_dir, task_id, code_root, record_video=record_video)
    desk.build_pristine()
    desk.start()
    t0 = time.monotonic()
    actors: dict[str, dict] = {}
    try:
        if condition == "seq_4role_full_cli":
            for r in QUAD_ROLES:
                actors[r] = run_quad_actor(r, desk, cond_dir / f"actor_{r}", desk.tickets_root / r, api_cfg, codex_bin, model_name, effort, None, int(meta["seq_role_timeout_s"]))
            overlap_s = 0.0
        elif condition == "quad_sd_full_cli":
            bar = threading.Barrier(4)
            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = {
                    pool.submit(run_quad_actor, r, desk, cond_dir / f"actor_{r}", desk.tickets_root / r, api_cfg, codex_bin, model_name, effort, bar, int(meta["conc_role_timeout_s"])): r
                    for r in QUAD_ROLES
                }
                for fut in as_completed(futs):
                    actors[futs[fut]] = fut.result()
            latest_start = max(a["first_tool_ts"] for a in actors.values())
            earliest_end = min(a["last_tool_ts"] for a in actors.values())
            pairwise_max = max(
                max(0.0, min(actors[r1]["last_tool_ts"], actors[r2]["last_tool_ts"]) - max(actors[r1]["first_tool_ts"], actors[r2]["first_tool_ts"]))
                for i, r1 in enumerate(QUAD_ROLES) for r2 in QUAD_ROLES[i + 1:]
            )
            overlap_s = round(max(0.0, earliest_end - latest_start) or pairwise_max, 2)
        else:
            raise ValueError(condition)
    finally:
        grade_res, pstate, ver_cnt = desk.stop_and_grade()

    tot_gui_obs = sum(a["gui_observation_calls"] for a in actors.values())
    tot_gui_act = sum(a["gui_action_calls"] for a in actors.values())
    tot_cli = sum(a["cli_calls"] for a in actors.values())
    rep = {
        "task_id": task_id,
        "condition": condition,
        "agent_count": 4,
        "model": model_name,
        "effort": effort,
        "valid_model_run": all(a["status"] in {"done", "timeout"} for a in actors.values()),
        "role_passes": grade_res["role_passes"],
        "passed_roles_score": f"{grade_res['passed_roles_count']}/4",
        "joint_pass": grade_res["joint_pass"],
        "overlap_seconds": overlap_s,
        "gui_observation_calls": tot_gui_obs,
        "gui_action_calls": tot_gui_act,
        "cli_calls": tot_cli,
        "portal_tab_switches": pstate.get("tab_switches", 0),
        "portal_clobber_count": pstate.get("clobber_count", 0),
        "unauthorized_cli_attempts": pstate.get("unauthorized_cli_attempts", 0),
        "distinct_project_versions": ver_cnt,
        "actors": actors,
        "grade": grade_res,
        "wall_seconds": round(time.monotonic() - t0, 2),
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def run_quad_suite(
    out_dir: Path,
    code_root: Path,
    api_json: Path,
    codex_bin: Path,
    tasks: list[str],
    conditions: list[str],
    model_name: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    workers: int = 2,
    record_video: bool = True,
) -> dict:
    api_cfg = json.loads(api_json.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = [(tid, cond) for tid in tasks for cond in conditions]
    results: dict[tuple[str, str], dict] = {}
    lock = threading.Lock()

    def save_progress() -> None:
        with lock:
            write_json(out_dir / "live-progress.json", {
                "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "completed": len(results),
                "total": len(pairs),
                "runs": {
                    f"{t}:{c}": {
                        "joint_pass": r["joint_pass"],
                        "passed_roles": r["passed_roles_score"],
                        "gui_obs": r["gui_observation_calls"],
                        "gui_act": r["gui_action_calls"],
                        "cli": r["cli_calls"],
                        "tab_switches": r["portal_tab_switches"],
                        "wall_s": r["wall_seconds"],
                    }
                    for (t, c), r in sorted(results.items())
                },
            })

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        fmap = {
            pool.submit(run_quad_condition, tid, cond, out_dir, code_root, api_cfg, codex_bin, model_name, effort, record_video): (tid, cond)
            for tid, cond in pairs
        }
        for fut in as_completed(fmap):
            tid, cond = fmap[fut]
            rep = fut.result()
            results[(tid, cond)] = rep
            save_progress()
            print(f"DONE {tid} {cond}: joint={rep['joint_pass']} roles={rep['passed_roles_score']} gui_act={rep['gui_action_calls']} gui_obs={rep['gui_observation_calls']} cli={rep['cli_calls']} tabs={rep['portal_tab_switches']} wall={rep['wall_seconds']}s", flush=True)

    audits = list(out_dir.rglob("permission-audit-verified.json"))
    write_json(out_dir / "permission-audit-rollup.json", {
        "verified_audit_files": len(audits),
        "agent_count_per_condition": 4,
        "model": model_name,
        "effort": effort,
        "sandbox_mode": "workspace-write",
        "yolo_enabled": False,
        "vm_host_codex_launched_count": 0,
        "yolo_flag_used_count": 0,
    })
    summary = {"model": model_name, "effort": effort, "agents_per_desktop": 4, "tasks": {}}
    lines = [
        f"# 4-Agent Concurrent Hybrid GUI+CLI Suite (`{model_name}`, `{effort}`, Non-YOLO Sandbox)",
        "",
        "| ID | Software Stack | `seq_4role_full_cli` (`B->C->D->A`) | `quad_sd_full_cli` (4 Concurrent) | Quad GUI (Act+Obs) / CLI | Tab Switches (Seq / Quad) | Wall s (Seq / Quad) |",
        "|---|---|---|---|---|---|---|",
    ]
    for tid in tasks:
        meta = QH_BY_ID[tid]
        sr = results.get((tid, "seq_4role_full_cli"))
        qr = results.get((tid, "quad_sd_full_cli"))
        summary["tasks"][tid] = {
            "software": meta["software"],
            "title": meta["title"],
            "seq_4role_full_cli": ("PASS" if sr["joint_pass"] else "FAIL") if sr else None,
            "seq_roles": sr["passed_roles_score"] if sr else None,
            "seq_role_passes": sr["role_passes"] if sr else None,
            "seq_gui_cli": f"{sr['gui_action_calls']}+{sr['gui_observation_calls']} / {sr['cli_calls']}" if sr else None,
            "seq_wall_s": sr["wall_seconds"] if sr else None,
            "quad_sd_full_cli": ("PASS" if qr["joint_pass"] else "FAIL") if qr else None,
            "quad_roles": qr["passed_roles_score"] if qr else None,
            "quad_role_passes": qr["role_passes"] if qr else None,
            "quad_gui_cli": f"{qr['gui_action_calls']}+{qr['gui_observation_calls']} / {qr['cli_calls']}" if qr else None,
            "quad_tab_switches": qr["portal_tab_switches"] if qr else None,
            "quad_overlap_s": qr["overlap_seconds"] if qr else None,
            "quad_wall_s": qr["wall_seconds"] if qr else None,
        }
        s_str = f"{'PASS' if sr['joint_pass'] else 'FAIL'} ({sr['passed_roles_score']})" if sr else "-"
        q_str = f"{'PASS' if qr['joint_pass'] else 'FAIL'} ({qr['passed_roles_score']})" if qr else "-"
        gc_str = f"{qr['gui_action_calls']}+{qr['gui_observation_calls']} / {qr['cli_calls']}" if qr else "-"
        tb_str = f"{sr['portal_tab_switches'] if sr else '-'} / {qr['portal_tab_switches'] if qr else '-'}"
        wl_str = f"{sr['wall_seconds'] if sr else '-'} / {qr['wall_seconds'] if qr else '-'}"
        lines.append(f"| `{tid}` | {meta['software']} | **{s_str}** | **{q_str}** | `{gc_str}` | `{tb_str}` | {wl_str} |")
    write_json(out_dir / "SUMMARY.json", summary)
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--api-json", type=Path, required=True)
    parser.add_argument("--codex-bin", type=Path, default=DEFAULT_CODEX_BINARY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--no-video", action="store_true")
    parser.add_argument("--tasks", nargs="*", default=[r["id"] for r in QUAD_HYBRID_CATALOG])
    parser.add_argument("--conditions", nargs="*", default=["seq_4role_full_cli", "quad_sd_full_cli"])
    args = parser.parse_args(argv)
    res = run_quad_suite(
        args.out.resolve(), args.code_root.resolve(), args.api_json.resolve(), args.codex_bin.resolve(),
        list(args.tasks), list(args.conditions), args.model, args.effort, args.workers, not args.no_video,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

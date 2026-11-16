"""Containerized non-YOLO Full Hybrid GUI+CLI runner for the 4 professional-software race tasks."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import requests
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time

from experiments.codesk_container_codex import (
    CONTAINER_ENTRY_SOURCE,
    DEFAULT_CODEX_BINARY,
    DEFAULT_CONTAINER_IMAGE,
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    validate_container_config_text,
    codex_requirements_mount,
    verify_container_permission_audit,
)
from experiments.responses_relay import prepare_image_history
from tasks.professional_races_v1.suite import (
    CATALOG_BY_ID,
    TASK_CATALOG,
    analyze_version_history,
    probe_lightweight_signals,
    role_prompts,
    sha256_file,
    write_json,
)


DESKTOP_IMAGE = "paragui/weavebench-pairs:20261103"
MODEL_NAME = "gpt-6.1-sol"


def start_local_upstream_relay(upstream_base: str, api_key: str, event_log: Path) -> tuple[ThreadingHTTPServer, int]:
    target_url = upstream_base.rstrip("/") + "/responses"

    class RelayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_unused):
            return

        def do_POST(self):
            started = time.monotonic()
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            try:
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict) and isinstance(parsed.get("input"), list) and not parsed.get("previous_response_id"):
                    parsed, _audit = prepare_image_history(parsed, keep=6, max_images=45)
                raw_body = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            except Exception:
                pass
            resp = None
            attempts = []
            for retry_idx in range(8):
                cand = requests.post(
                    target_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": self.headers.get("Accept", "text/event-stream"),
                    },
                    data=raw_body,
                    stream=True,
                    timeout=(20, 300),
                )
                attempts.append({"attempt": retry_idx + 1, "status": cand.status_code})
                if cand.status_code in (429, 502, 503, 504) and retry_idx < 7:
                    retry_hdr = cand.headers.get("Retry-After")
                    try:
                        wait_s = min(max(float(retry_hdr), 5.0), 35.0) if retry_hdr else (8.0 + 4.0 * retry_idx)
                    except ValueError:
                        wait_s = 12.0
                    cand.close()
                    time.sleep(wait_s)
                    continue
                resp = cand
                break
            if resp is None:
                self.send_error(502, "Upstream unavailable")
                return
            with resp:
                self.send_response(resp.status_code)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "text/event-stream"))
                self.send_header("Connection", "close")
                self.end_headers()
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                self.close_connection = True
                with event_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"time": time.time(), "status": resp.status_code, "attempts": attempts, "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), RelayHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_port


class SharedAppDesktop:
    def __init__(self, run_dir: Path, label: str, task_id: str, code_root: Path, desktop_image: str = DESKTOP_IMAGE):
        self.run_dir = run_dir
        self.label = label
        self.task_id = task_id
        self.code_root = code_root
        self.desktop_image = desktop_image
        self.workspace = run_dir / f"workspace_{label}"
        self.versions_dir = run_dir / f"saved_versions_{label}"
        self.versions_log = run_dir / f"version_timeline_{label}.jsonl"
        self.container_name = f"paragui-profrace-desk-{label}-{secrets.token_hex(5)}"
        self.created = False
        self._watch_stop = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self.history_rows: list[dict] = []

    def build_pristine(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
                "-v", f"{self.code_root}:/code:ro",
                "-v", f"{self.workspace}:/workspace",
                "-e", "PYTHONPATH=/code",
                "--entrypoint", "python3",
                self.desktop_image,
                "-m", "tasks.professional_races_v1.suite", "build",
                "--task", self.task_id, "--workspace", "/workspace",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )

    def start(self) -> None:
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.container_name,
                "--network", "none", "--cpus", "4", "--memory", "8g", "--shm-size", "1g",
                "--security-opt", "no-new-privileges",
                "--label", "org.paragui.kind=profrace-desktop",
                "-v", f"{self.workspace}:/workspace",
                self.desktop_image, "sleep", "infinity",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.created = True
        setup_user = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "mkdir -p /tmp/runtime-gui /home/gui/.config; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chmod -R g+rwX /workspace /home/gui; "
            "chmod 700 /tmp/runtime-gui"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", setup_user], check=True, capture_output=True, timeout=30)
        app_cmd = shlex.join(CATALOG_BY_ID[self.task_id]["gui_launch"])
        x11_boot = (
            "umask 0002; "
            "Xvfb :99 -screen 0 1280x720x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & "
            "sleep 1; export DISPLAY=:99; "
            "dbus-daemon --session --fork --address=unix:path=/tmp/runtime-gui/bus; "
            "openbox >/tmp/openbox.log 2>&1 & "
            f"sleep 1; nohup {app_cmd} >/tmp/gui_app.log 2>&1 </dev/null &"
        )
        subprocess.run(
            [
                "docker", "exec", "-d", "--user", "1000:0",
                "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus",
                self.container_name, "bash", "-lc", x11_boot,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        win_hint = CATALOG_BY_ID[self.task_id]["window_match"]
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline:
            out = self.exec_user("wmctrl -lp || true", timeout_s=10)["stdout"]
            if win_hint.lower() in out.lower() or len(out.strip().splitlines()) >= 1:
                self.exec_user("xdotool search --onlyvisible --name . | tail -n 1 | xargs -r -I{} wmctrl -i -r {} -b add,maximized_vert,maximized_horz || true", timeout_s=10)
                break
            time.sleep(1.0)
        self._record_snapshot()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _record_snapshot(self) -> None:
        snap = probe_lightweight_signals(self.task_id, self.workspace)
        snap["timestamp"] = time.time()
        sha = snap.get("project_sha256")
        canon_file = self.workspace / CATALOG_BY_ID[self.task_id]["canonical_project"]
        if sha and canon_file.is_file():
            archived = self.versions_dir / f"{sha}_{canon_file.name}"
            if not archived.exists():
                try:
                    shutil.copy2(canon_file, archived)
                except OSError:
                    pass
        if not self.history_rows or self.history_rows[-1].get("project_sha256") != sha or self.history_rows[-1].get("gpkg_sha256") != snap.get("gpkg_sha256"):
            self.history_rows.append(snap)
            with self.versions_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(snap, ensure_ascii=False) + "\n")

    def _watch_loop(self) -> None:
        while not self._watch_stop.is_set():
            try:
                self._record_snapshot()
            except Exception:
                pass
            self._watch_stop.wait(0.20)

    def exec_user(self, command_str: str, cwd: str = "/workspace", timeout_s: int = 120) -> dict:
        completed = subprocess.run(
            [
                "docker", "exec", "--user", "1000:0",
                "-w", cwd,
                "-e", "DISPLAY=:99",
                "-e", "HOME=/home/gui",
                "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus",
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

    def screenshot_base64(self) -> str:
        shot_cmd = (
            "python3 -c \"import subprocess, base64, tempfile; "
            "p = tempfile.mktemp(suffix='.png'); "
            "subprocess.run(['import', '-window', 'root', p], check=True); "
            "print(base64.b64encode(open(p,'rb').read()).decode())\""
        )
        res = self.exec_user(shot_cmd, timeout_s=20)
        if res["ok"] and res["stdout"].strip():
            return res["stdout"].strip().splitlines()[-1]
        fallback_cmd = (
            "python3 -c \"from PIL import Image; import io, base64; "
            "im = Image.new('RGB', (1280, 720), (30, 34, 40)); buf = io.BytesIO(); "
            "im.save(buf, format='PNG'); print(base64.b64encode(buf.getvalue()).decode())\""
        )
        return self.exec_user(fallback_cmd, timeout_s=15)["stdout"].strip().splitlines()[-1]

    def stop(self) -> dict:
        self._watch_stop.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=3.0)
        try:
            self._record_snapshot()
        except Exception:
            pass
        if self.created:
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
            self.created = False
        return analyze_version_history(self.history_rows)

    def grade(self, out_json: Path) -> dict:
        eval_ws = self.run_dir / f"eval_copy_{self.label}"
        if eval_ws.exists():
            shutil.rmtree(eval_ws)
        shutil.copytree(self.workspace, eval_ws)
        subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
                "-v", f"{self.code_root}:/code:ro",
                "-v", f"{eval_ws}:/workspace",
                "-v", f"{out_json.parent}:/out",
                "-e", "PYTHONPATH=/code",
                "--entrypoint", "python3",
                self.desktop_image,
                "-m", "tasks.professional_races_v1.suite", "grade",
                "--task", self.task_id, "--workspace", "/workspace",
                "--out", f"/out/{out_json.name}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
        return json.loads(out_json.read_text(encoding="utf-8"))


def build_full_cli_config_template(model_name: str) -> str:
    return f'''model = {json.dumps(model_name)}
model_provider = "profrace"
model_reasoning_effort = "medium"
model_catalog_json = "/session/codex-home/models-catalog.json"
model_context_window = 262144
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "disabled"
mcp_optional_startup_grace_ms = 0

[model_providers.profrace]
name = "profrace"
base_url = "http://127.0.0.1:__CONTAINER_RELAY_PORT__/v1"
requires_openai_auth = false
wire_api = "responses"
supports_websockets = false
request_max_retries = 6
stream_max_retries = 6
stream_idle_timeout_ms = 300000

[features]
shell_tool = true
unified_exec = false
multi_agent = false
image_generation = false

[sandbox_workspace_write]
writable_roots = ["/session", "/tmp", "/ipc"]
network_access = true

[mcp_servers.desktop]
command = "python3"
args = ["/bridge/mcp_proxy.py", "desktop"]
enabled = true
required = true
enabled_tools = ["screenshot", "click", "move", "type_text", "key", "wait"]
startup_timeout_sec = 45
tool_timeout_sec = 120
default_tools_approval_mode = "approve"

[mcp_servers.guest_bash]
command = "python3"
args = ["/bridge/mcp_proxy.py", "guest_bash"]
enabled = true
required = true
enabled_tools = ["guest_bash"]
startup_timeout_sec = 30
tool_timeout_sec = 180
default_tools_approval_mode = "approve"
'''


def build_agent_prompt(role_instruction: str) -> str:
    return (
        "You are operating a Linux workstation (1280x720 X11 GUI on DISPLAY=:99, workspace at `/workspace`) "
        "in FULL HYBRID GUI+CLI mode. Both GUI controls (`desktop` MCP: screenshot, click, move, type_text, key, wait) "
        "and full unrestricted CLI/programming on the target workstation (`guest_bash` MCP tool, or "
        "`python3 /bridge/guest_bash.py '<bash command>'` from your container shell) are enabled. "
        "Note that `/workspace` lives on the target workstation accessed through `guest_bash` and `desktop`, "
        "not in your local `/session` scratch directory. Use native CLI/Python APIs (`blender -b`, `pyqgis`, "
        "`freecadcmd`, `inkscape`, `python3`) and GUI tools freely.\n\n"
        f"Task: {role_instruction}\n\n"
        "Verify all required deliverables and project changes in `/workspace` before finishing, then reply concisely."
    )


def make_mcp_handlers_for_desktop(
    desk: SharedAppDesktop,
    action_log: Path,
    start_barrier: threading.Barrier | None = None,
) -> dict:
    barrier_done = {"passed": False}

    def wait_barrier_once() -> None:
        if start_barrier is not None and not barrier_done["passed"]:
            barrier_done["passed"] = True
            try:
                start_barrier.wait(timeout=60.0)
            except threading.BrokenBarrierError:
                pass

    def record_call(tool_name: str, args_obj: dict) -> None:
        with action_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": time.time(), "tool": tool_name, "args": args_obj}, ensure_ascii=False) + "\n")

    desktop_schemas = [
        {"name": "screenshot", "description": "Capture current 1280x720 X11 desktop screenshot.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "click", "description": "Click at (x, y) on the 1280x720 desktop.", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "integer", "default": 1}}, "required": ["x", "y"], "additionalProperties": False}},
        {"name": "move", "description": "Move pointer to (x, y).", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"], "additionalProperties": False}},
        {"name": "type_text", "description": "Type text into the focused X11 window.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}},
        {"name": "key", "description": "Send X11 key combo (e.g. Return, ctrl+s).", "inputSchema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"], "additionalProperties": False}},
        {"name": "wait", "description": "Sleep seconds and return a fresh screenshot.", "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 2.0}}, "additionalProperties": False}},
    ]

    def call_desktop(name: str, arguments: dict) -> dict:
        wait_barrier_once()
        record_call(f"desktop.{name}", arguments)
        if name == "click":
            x_pos = int(arguments["x"])
            y_pos = int(arguments["y"])
            btn = int(arguments.get("button", 1))
            desk.exec_user(f"xdotool mousemove --sync {x_pos} {y_pos} click {btn}", timeout_s=15)
        elif name == "move":
            desk.exec_user(f"xdotool mousemove --sync {int(arguments['x'])} {int(arguments['y'])}", timeout_s=15)
        elif name == "type_text":
            desk.exec_user("xdotool type --delay 15 -- " + shlex.quote(str(arguments["text"])), timeout_s=20)
        elif name == "key":
            desk.exec_user("xdotool key --clearmodifiers " + shlex.quote(str(arguments["keys"])), timeout_s=15)
        elif name == "wait":
            time.sleep(min(15.0, max(0.2, float(arguments.get("seconds", 2.0)))))
        img_b64 = desk.screenshot_base64()
        return {"content": [{"type": "text", "text": "OK."}, {"type": "image", "data": img_b64, "mimeType": "image/png"}], "isError": False}

    bash_schema = {
        "name": "guest_bash",
        "description": "Run an unrestricted bash command or Python/Blender/PyQGIS/FreeCAD/Inkscape script in /workspace on the workstation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "default": "/workspace"},
                "timeout": {"type": "number", "default": 120},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    }

    def call_guest_bash(name: str, arguments: dict) -> dict:
        wait_barrier_once()
        record_call("guest_bash.guest_bash", arguments)
        timeout_val = int(min(180, max(5, float(arguments.get("timeout", 120)))))
        cwd_val = str(arguments.get("cwd") or "/workspace")
        res = desk.exec_user(str(arguments["command"]), cwd=cwd_val, timeout_s=timeout_val)
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_guest_bash},
    }


def run_container_codex_actor(
    role: str,
    desk: SharedAppDesktop,
    instruction: str,
    actor_dir: Path,
    api_cfg: dict,
    codex_bin: Path,
    start_barrier: threading.Barrier | None = None,
    timeout_s: int = 900,
) -> dict:
    actor_dir.mkdir(parents=True, exist_ok=True)
    session_dir = actor_dir / "container_session"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")
    catalog_payload = {"models": [{
        "slug": MODEL_NAME,
        "display_name": MODEL_NAME,
        "description": "Vision-capable hybrid GUI+CLI model.",
        "default_reasoning_level": "medium",
        "supported_reasoning_levels": [{"effort": lv, "description": lv} for lv in ("low", "medium", "high")],
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
        "base_instructions": "You are a hybrid GUI+CLI engineering agent. Complete your assigned ticket accurately.",
    }]}
    write_json(session_dir / "codex-home/models-catalog.json", catalog_payload)
    tmpl = build_full_cli_config_template(MODEL_NAME)
    validate_container_config_text(tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(tmpl, encoding="utf-8")
    (session_dir / "prompt.txt").write_text(build_agent_prompt(instruction), encoding="utf-8")
    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o770 if item.is_dir() else 0o660)
        except OSError:
            pass

    relay_server, relay_port = start_local_upstream_relay(api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl")
    action_log = actor_dir / "actions.jsonl"
    action_log.touch()
    handlers = make_mcp_handlers_for_desktop(desk, action_log, start_barrier=start_barrier)
    bridge = HostActorBridge(None, relay_port, handlers)
    bridge.start()

    cname = f"paragui-profrace-codex-{role.lower()}-{secrets.token_hex(5)}"
    owner_tok = secrets.token_hex(12)
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
        "--memory", "4g",
        "--user", "1000:0",
        "--label", "org.paragui.kind=profrace-codex-actor",
        "--label", f"org.paragui.owner={owner_tok}",
        "-v", f"{session_dir}:/session",
        "-v", f"{session_dir / 'bridge'}:/bridge:ro",
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
        audit = verify_container_permission_audit(session_dir, expected_model=MODEL_NAME, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        action_rows = [json.loads(line) for line in action_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        gui_calls = sum(1 for row in action_rows if row["tool"].startswith("desktop.") and row["tool"] not in {"desktop.screenshot", "desktop.wait"})
        obs_calls = sum(1 for row in action_rows if row["tool"] in {"desktop.screenshot", "desktop.wait"})
        cli_calls = sum(1 for row in action_rows if row["tool"].startswith("guest_bash."))
        first_ts = action_rows[0]["timestamp"] if action_rows else t_start
        last_ts = action_rows[-1]["timestamp"] if action_rows else t_end
        return {
            "role": role,
            "status": "timeout" if timed_out else ("done" if proc.returncode == 0 else "error"),
            "exit_code": proc.returncode,
            "wall_seconds": round(t_end - t_start, 2),
            "first_tool_ts": first_ts,
            "last_tool_ts": last_ts,
            "gui_action_calls": gui_calls,
            "observation_calls": obs_calls,
            "cli_calls": cli_calls,
            "permission_audit_ok": True,
        }
    finally:
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20)
        bridge.close()
        relay_server.shutdown()
        relay_server.server_close()


def run_task_condition(
    task_id: str,
    condition: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict,
    codex_bin: Path,
) -> dict:
    cond_dir = out_dir / task_id / condition
    cond_dir.mkdir(parents=True, exist_ok=True)
    prompts = role_prompts(task_id)
    started = time.monotonic()

    if condition == "ma_id":
        desk_a = SharedAppDesktop(cond_dir, "isolated_A", task_id, code_root)
        desk_b = SharedAppDesktop(cond_dir, "isolated_B", task_id, code_root)
        desk_a.build_pristine()
        desk_b.build_pristine()
        desk_a.start()
        desk_b.start()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_a = pool.submit(run_container_codex_actor, "A", desk_a, prompts["A"], cond_dir / "actor_A", api_cfg, codex_bin)
                fut_b = pool.submit(run_container_codex_actor, "B", desk_b, prompts["B"], cond_dir / "actor_B", api_cfg, codex_bin)
                res_a = fut_a.result()
                res_b = fut_b.result()
        finally:
            hist_a = desk_a.stop()
            hist_b = desk_b.stop()
        grade_a = desk_a.grade(cond_dir / "grade_A.json")
        grade_b = desk_b.grade(cond_dir / "grade_B.json")
        report = {
            "task_id": task_id,
            "condition": condition,
            "valid_model_run": res_a["status"] == "done" and res_b["status"] == "done",
            "role_a_pass": grade_a["role_a_pass"],
            "role_b_pass": grade_b["role_b_pass"],
            "joint_pass": grade_a["role_a_pass"] and grade_b["role_b_pass"],
            "actors": {"A": res_a, "B": res_b},
            "grades": {"A": grade_a, "B": grade_b},
            "version_history": {"A": hist_a, "B": hist_b},
            "wall_seconds": round(time.monotonic() - started, 2),
        }
        write_json(cond_dir / "report.json", report)
        return report

    desk = SharedAppDesktop(cond_dir, "shared", task_id, code_root)
    desk.build_pristine()
    desk.start()
    try:
        if condition == "seq_ba_full_cli":
            res_b = run_container_codex_actor("B", desk, prompts["B"], cond_dir / "actor_B", api_cfg, codex_bin)
            res_a = run_container_codex_actor("A", desk, prompts["A"], cond_dir / "actor_A", api_cfg, codex_bin)
            overlap_s = 0.0
        elif condition == "ma_sd_full_cli":
            barrier = threading.Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_a = pool.submit(run_container_codex_actor, "A", desk, prompts["A"], cond_dir / "actor_A", api_cfg, codex_bin, barrier)
                fut_b = pool.submit(run_container_codex_actor, "B", desk, prompts["B"], cond_dir / "actor_B", api_cfg, codex_bin, barrier)
                res_a = fut_a.result()
                res_b = fut_b.result()
            overlap_s = round(max(0.0, min(res_a["last_tool_ts"], res_b["last_tool_ts"]) - max(res_a["first_tool_ts"], res_b["first_tool_ts"])), 2)
        else:
            raise ValueError(f"Unsupported condition: {condition}")
    finally:
        hist_shared = desk.stop()
    grade_shared = desk.grade(cond_dir / "grade_shared.json")
    race_Mechanisms_triggered = []
    if hist_shared.get("lost_update_observed"):
        race_Mechanisms_triggered.append("project_file_lost_update_regression")
    if not grade_shared["role_a_pass"] and res_a["status"] == "done":
        for chk_name, chk_ok in grade_shared["checks_a"].items():
            if not chk_ok:
                race_Mechanisms_triggered.append(f"role_a_violated:{chk_name}")
    if not grade_shared["role_b_pass"] and res_b["status"] == "done":
        for chk_name, chk_ok in grade_shared["checks_b"].items():
            if not chk_ok:
                race_Mechanisms_triggered.append(f"role_b_violated:{chk_name}")
    report = {
        "task_id": task_id,
        "condition": condition,
        "valid_model_run": res_a["status"] == "done" and res_b["status"] == "done",
        "role_a_pass": grade_shared["role_a_pass"],
        "role_b_pass": grade_shared["role_b_pass"],
        "joint_pass": grade_shared["joint_pass"],
        "tool_window_overlap_seconds": overlap_s,
        "actors": {"A": res_a, "B": res_b},
        "grade": grade_shared,
        "version_history": hist_shared,
        "race_diagnosis": {
            "concurrent_overlap_confirmed": overlap_s > 0.0,
            "distinct_project_saves": hist_shared.get("distinct_project_versions", 0),
            "lost_update_regressions": hist_shared.get("lost_update_regressions", []),
            "triggered_failure_signals": race_Mechanisms_triggered,
        },
        "wall_seconds": round(time.monotonic() - started, 2),
    }
    write_json(cond_dir / "report.json", report)
    return report


def run_benchmark_suite(out_dir: Path, code_root: Path, api_json: Path, codex_bin: Path, tasks: list[str]) -> dict:
    api_cfg = json.loads(api_json.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    conditions = ["ma_id", "seq_ba_full_cli", "ma_sd_full_cli"]
    jobs = [(tid, cond) for tid in tasks for cond in conditions]
    results_by_task: dict[str, dict] = {tid: {} for tid in tasks}
    with ThreadPoolExecutor(max_workers=3) as pool:
        fmap = {
            pool.submit(run_task_condition, tid, cond, out_dir, code_root, api_cfg, codex_bin): (tid, cond)
            for tid, cond in jobs
        }
        for fut in as_completed(fmap):
            tid, cond = fmap[fut]
            rep = fut.result()
            results_by_task[tid][cond] = rep
            write_json(out_dir / "suite_progress.json", results_by_task)
    rollup = {"model": MODEL_NAME, "mode": "Full Hybrid GUI+CLI (container-unrestricted, non-YOLO host)", "tasks": {}}
    md_lines = [
        f"# Professional-Software Race Suite ({MODEL_NAME}, Full Hybrid GUI+CLI)",
        "",
        "| Task | Software | `ma_id` (Isolated) | `seq_ba_full_cli` (Sequential Shared) | `ma_sd_full_cli` (Concurrent Shared) | Overlap (s) | FullCLI GUI/CLI Calls | Observed Race Signals |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for tid in tasks:
        tmeta = CATALOG_BY_ID[tid]
        t_res = results_by_task[tid]
        c_id = "PASS" if t_res["ma_id"]["joint_pass"] else "FAIL"
        c_seq = "PASS" if t_res["seq_ba_full_cli"]["joint_pass"] else "FAIL"
        conc = t_res["ma_sd_full_cli"]
        c_conc = "PASS" if conc["joint_pass"] else "FAIL"
        gui_tot = conc["actors"]["A"]["gui_action_calls"] + conc["actors"]["B"]["gui_action_calls"]
        cli_tot = conc["actors"]["A"]["cli_calls"] + conc["actors"]["B"]["cli_calls"]
        sigs = ", ".join(conc["race_diagnosis"]["triggered_failure_signals"][:2]) or "none"
        rollup["tasks"][tid] = {
            "software": tmeta["software"],
            "ma_id": c_id,
            "seq_ba_full_cli": c_seq,
            "ma_sd_full_cli": c_conc,
            "target_pass_pass_fail": (c_id == "PASS" and c_seq == "PASS" and c_conc == "FAIL"),
            "concurrent_overlap_s": conc["tool_window_overlap_seconds"],
            "concurrent_gui_cli": f"{gui_tot}/{cli_tot}",
            "race_diagnosis": conc["race_diagnosis"],
        }
        md_lines.append(f"| `{tid}` | {tmeta['software']} | **{c_id}** | **{c_seq}** | **{c_conc}** | {conc['tool_window_overlap_seconds']} | {gui_tot}/{cli_tot} | `{sigs}` |")
    write_json(out_dir / "SUMMARY.json", rollup)
    (out_dir / "SUMMARY.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return rollup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--api-json", type=Path, required=True)
    parser.add_argument("--codex-bin", type=Path, default=DEFAULT_CODEX_BINARY)
    parser.add_argument("--tasks", nargs="*", default=[item["id"] for item in TASK_CATALOG])
    args = parser.parse_args(argv)
    res = run_benchmark_suite(args.out.resolve(), args.code_root.resolve(), args.api_json.resolve(), args.codex_bin.resolve(), list(args.tasks))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

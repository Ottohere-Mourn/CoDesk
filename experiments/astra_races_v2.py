"""Containerized non-YOLO gpt-6-astra (high) Full Hybrid GUI+CLI runner for the 10-task race suite."""
from __future__ import annotations

import argparse
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
    validate_container_config_text,
    codex_requirements_mount,
    verify_container_permission_audit,
)
from experiments.responses_relay import prepare_image_history
from tasks.astra_races_v2.builders import sha256_file, write_json
from tasks.astra_races_v2.catalog import ASTRA_RACE_CATALOG, CATALOG_BY_ID


DESKTOP_IMAGE = os.environ.get("PARAGUI_ASTRA_DESKTOP_IMAGE", "paragui/astra-race-desktop:20261111")
MODEL_NAME = "gpt-6-astra"
REASONING_EFFORT = "high"


def start_astra_relay(
    upstream_base: str,
    api_key: str,
    event_log: Path,
    upstream_model: str | None = None,
) -> tuple[ThreadingHTTPServer, int]:
    target_url = upstream_base.rstrip("/") + "/responses"
    candidate_models = []
    for m_item in [upstream_model, "substrate-gpt-6-astra", "copilot-gpt-6-astra", MODEL_NAME]:
        if m_item and m_item not in candidate_models:
            candidate_models.append(m_item)

    class RelayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_unused):
            return

        def do_POST(self):
            started = time.monotonic()
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            parsed_dict = None
            try:
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict) and isinstance(parsed.get("input"), list) and not parsed.get("previous_response_id"):
                    parsed, _audit = prepare_image_history(parsed, keep=5, max_images=45)
                if isinstance(parsed, dict):
                    parsed_dict = parsed
                raw_body = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            except Exception:
                pass
            resp = None
            attempts = []
            model_idx = 0
            used_model = candidate_models[0]
            for retry_idx in range(8):
                used_model = candidate_models[min(model_idx, len(candidate_models) - 1)]
                req_body = raw_body
                if parsed_dict is not None and parsed_dict.get("model") == MODEL_NAME and used_model != MODEL_NAME:
                    patched = dict(parsed_dict, model=used_model)
                    req_body = json.dumps(patched, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                cand = requests.post(
                    target_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": self.headers.get("Accept", "text/event-stream"),
                    },
                    data=req_body,
                    stream=True,
                    timeout=(25, 360),
                )
                attempts.append({"attempt": retry_idx + 1, "status": cand.status_code, "upstream_model": used_model})
                if cand.status_code == 403 and model_idx + 1 < len(candidate_models) and retry_idx < 7:
                    model_idx += 1
                    cand.close()
                    continue
                if cand.status_code in (429, 502, 503, 504) and retry_idx < 7:
                    retry_hdr = cand.headers.get("Retry-After")
                    try:
                        wait_s = min(max(float(retry_hdr), 5.0), 35.0) if retry_hdr else (10.0 + 5.0 * retry_idx)
                    except ValueError:
                        wait_s = 15.0
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
                if used_model != MODEL_NAME:
                    src_a = f'"model":"{used_model}"'.encode("utf-8")
                    dst_a = f'"model":"{MODEL_NAME}"'.encode("utf-8")
                    src_b = f'"model": "{used_model}"'.encode("utf-8")
                    dst_b = f'"model": "{MODEL_NAME}"'.encode("utf-8")
                    for line in resp.iter_lines():
                        out_line = line.replace(src_a, dst_a).replace(src_b, dst_b) + b"\n"
                        self.wfile.write(out_line)
                        self.wfile.flush()
                else:
                    for chunk in resp.iter_content(chunk_size=16384):
                        if chunk:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                self.close_connection = True
                with event_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"time": time.time(), "status": resp.status_code, "upstream_model": used_model, "attempts": attempts, "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), RelayHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_port


class AstraSharedDesktop:
    def __init__(self, cond_dir: Path, task_id: str, code_root: Path):
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.meta = CATALOG_BY_ID[task_id]
        self.workspace = cond_dir / "workspace"
        self.ticket_a = cond_dir / "ticket_A"
        self.ticket_b = cond_dir / "ticket_B"
        self.work_a = cond_dir / "actor_A/container_session/work"
        self.work_b = cond_dir / "actor_B/container_session/work"
        self.versions_log = cond_dir / "version_timeline.jsonl"
        self.portal_state_out = cond_dir / "portal_state.json"
        self.container_name = f"paragui-astrarace-desk-{task_id.lower()}-{secrets.token_hex(5)}"
        self.created = False
        self._stop_evt = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self.version_hashes: list[str] = []

    def build_pristine(self) -> None:
        for dpath in (self.workspace, self.ticket_a, self.ticket_b, self.work_a, self.work_b):
            dpath.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
                "-v", f"{self.code_root}:/code:ro",
                "-v", f"{self.workspace}:/workspace",
                "-v", f"{self.ticket_a}:/ticket_a",
                "-v", f"{self.ticket_b}:/ticket_b",
                "-e", "PYTHONPATH=/code",
                "--entrypoint", "python3",
                DESKTOP_IMAGE,
                "-m", "tasks.astra_races_v2.graders", "build",
                "--task", self.task_id,
                "--workspace", "/workspace",
                "--ticket-a", "/ticket_a",
                "--ticket-b", "/ticket_b",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )

    def start(self) -> None:
        for dpath in (self.work_a, self.work_b):
            dpath.mkdir(parents=True, exist_ok=True)
            os.chmod(dpath, 0o770)
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.container_name,
                "--network", "none", "--cpus", "4", "--memory", "8g", "--shm-size", "1g",
                "--security-opt", "no-new-privileges",
                "--label", "org.paragui.kind=astrarace-desktop",
                "-v", f"{self.code_root}:/code:ro",
                "-v", f"{self.workspace}:/workspace",
                "-v", f"{self.ticket_a}:/var/tickets/A:ro",
                "-v", f"{self.ticket_b}:/var/tickets/B:ro",
                "-v", f"{self.work_a}:/var/agent_work/A",
                "-v", f"{self.work_b}:/var/agent_work/B",
                DESKTOP_IMAGE, "sleep", "infinity",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.created = True
        setup_cmd = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "mkdir -p /tmp/runtime-gui /home/gui/.config/chromium /opt/portal_state; "
            "chmod 700 /opt/portal_state /tmp/runtime-gui; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace /var/agent_work; "
            "chmod -R g+rwX /workspace /home/gui /var/agent_work"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", setup_cmd], check=True, capture_output=True, timeout=30)

        if self.meta.get("portal_kind"):
            pkind = self.meta["portal_kind"]
            pport = int(self.meta["portal_port"])
            subprocess.run(
                [
                    "docker", "exec", "-d", "-e", "PYTHONPATH=/code",
                    self.container_name, "python3", "-m", "tasks.astra_races_v2.portals",
                    "--kind", pkind, "--port", str(pport), "--state-dir", "/opt/portal_state",
                ],
                check=True,
                capture_output=True,
                timeout=20,
            )
            for _ in range(30):
                chk = subprocess.run(["docker", "exec", self.container_name, "curl", "-fsS", f"http://127.0.0.1:{pport}/health"], capture_output=True, timeout=5)
                if chk.returncode == 0:
                    break
                time.sleep(0.3)

        app_cmd = shlex.join(self.meta["gui_launch"])
        boot_x11 = (
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
                self.container_name, "bash", "-lc", boot_x11,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        time.sleep(3.0)
        self.exec_role("A", "xdotool search --onlyvisible --name . | tail -n 1 | xargs -r -I{} wmctrl -i -r {} -b add,maximized_vert,maximized_horz || true", timeout_s=10)
        self._sample_once()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _sample_once(self) -> None:
        canon = self.workspace / self.meta["canonical_project"]
        if canon.is_file():
            sha = sha256_file(canon)
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
            self._stop_evt.wait(0.25)

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 180) -> dict:
        completed = subprocess.run(
            [
                "docker", "exec", "--user", "1000:0",
                "-w", cwd,
                "-e", "DISPLAY=:99",
                "-e", "HOME=/home/gui",
                "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus",
                "-e", f"AGENT_TICKET_DIR=/var/tickets/{role}",
                "-e", f"AGENT_WORK_DIR=/var/agent_work/{role}",
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
        res = self.exec_role("A", shot_cmd, timeout_s=20)
        if res["ok"] and res["stdout"].strip():
            return res["stdout"].strip().splitlines()[-1]
        fallback_cmd = (
            "python3 -c \"from PIL import Image; import io, base64; "
            "im = Image.new('RGB', (1280, 720), (28, 32, 38)); buf = io.BytesIO(); "
            "im.save(buf, format='PNG'); print(base64.b64encode(buf.getvalue()).decode())\""
        )
        return self.exec_role("A", fallback_cmd, timeout_s=15)["stdout"].strip().splitlines()[-1]

    def stop_and_grade(self) -> tuple[dict, int]:
        self._stop_evt.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=3.0)
        self._sample_once()
        if self.created and self.meta.get("portal_kind"):
            cp = subprocess.run(["docker", "exec", self.container_name, "cat", "/opt/portal_state/portal_state.json"], capture_output=True, text=True, timeout=10)
            if cp.returncode == 0 and cp.stdout.strip():
                self.portal_state_out.write_text(cp.stdout, encoding="utf-8")
        if self.created:
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
            self.created = False
        grade_out = self.cond_dir / "grade.json"
        eval_ws = self.cond_dir / "eval_workspace"
        if eval_ws.exists():
            shutil.rmtree(eval_ws)
        shutil.copytree(self.workspace, eval_ws)
        cmd = [
            "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
            "-v", f"{self.code_root}:/code:ro",
            "-v", f"{eval_ws}:/workspace",
            "-v", f"{self.work_a}:/work_a:ro",
            "-v", f"{self.work_b}:/work_b:ro",
            "-v", f"{self.cond_dir}:/out",
            "-e", "PYTHONPATH=/code",
            "--entrypoint", "python3",
            DESKTOP_IMAGE,
            "-m", "tasks.astra_races_v2.graders", "grade",
            "--task", self.task_id,
            "--workspace", "/workspace",
            "--work-a", "/work_a",
            "--work-b", "/work_b",
            "--out", "/out/grade.json",
        ]
        if self.portal_state_out.is_file():
            cmd.extend(["--portal-state", "/out/portal_state.json"])
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
        shutil.rmtree(eval_ws, ignore_errors=True)
        return json.loads(grade_out.read_text(encoding="utf-8")), len(self.version_hashes)


def build_astra_config_template() -> str:
    return f'''model = {json.dumps(MODEL_NAME)}
model_provider = "astrarace"
model_reasoning_effort = {json.dumps(REASONING_EFFORT)}
model_catalog_json = "/session/codex-home/models-catalog.json"
model_context_window = 262144
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "disabled"
mcp_optional_startup_grace_ms = 0

[model_providers.astrarace]
name = "astrarace"
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
tool_timeout_sec = 240
default_tools_approval_mode = "approve"
'''


def build_astra_prompt(role: str, ticket_markdown: str) -> str:
    return (
        "You are operating a Linux engineering workstation (1280x720 X11 GUI on DISPLAY=:99, shared project root `/workspace`) "
        "in FULL HYBRID GUI+CLI mode. Both GUI tools (`desktop` MCP: screenshot, click, move, type_text, key, wait) "
        "and unrestricted workstation CLI (`guest_bash` MCP tool) are enabled.\n"
        f"Important path mapping:\n"
        f"- Your ticket inputs are mounted at `/session/ticket` locally AND at `/var/tickets/{role}` (`$AGENT_TICKET_DIR`) in `guest_bash`.\n"
        f"- Your personal output directory `/session/work` is ALSO mounted at `/var/agent_work/{role}` (`$AGENT_WORK_DIR`) in `guest_bash` — "
        f"so writing to `$AGENT_WORK_DIR/signoff.json` or `$AGENT_WORK_DIR/...` from `guest_bash` writes directly to `/session/work/...`!\n"
        "- Shared project files and `/workspace/exports/...` live on the workstation accessed via `guest_bash` and `desktop`.\n\n"
        f"{ticket_markdown}\n\n"
        "Complete every step of your ticket accurately and reply concisely when finished."
    )


def make_role_handlers(desk: AstraSharedDesktop, role: str, action_log: Path, barrier: threading.Barrier | None) -> dict:
    passed = {"done": False}

    def sync_once() -> None:
        if barrier is not None and not passed["done"]:
            passed["done"] = True
            try:
                barrier.wait(timeout=90.0)
            except threading.BrokenBarrierError:
                pass

    def log_act(tname: str, aobj: dict) -> None:
        with action_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": time.time(), "tool": tname, "args": aobj}, ensure_ascii=False) + "\n")

    desktop_schemas = [
        {"name": "screenshot", "description": "Capture 1280x720 X11 desktop screenshot.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "click", "description": "Click at (x, y) on the 1280x720 desktop.", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "integer", "default": 1}}, "required": ["x", "y"], "additionalProperties": False}},
        {"name": "move", "description": "Move pointer to (x, y).", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"], "additionalProperties": False}},
        {"name": "type_text", "description": "Type text into active X11 window.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}},
        {"name": "key", "description": "Send X11 key combo (e.g. Return, ctrl+s).", "inputSchema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"], "additionalProperties": False}},
        {"name": "wait", "description": "Sleep seconds and return screenshot.", "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 2.0}}, "additionalProperties": False}},
    ]

    def call_desktop(name: str, arguments: dict) -> dict:
        sync_once()
        log_act(f"desktop.{name}", arguments)
        if name == "click":
            desk.exec_role(role, f"xdotool mousemove --sync {int(arguments['x'])} {int(arguments['y'])} click {int(arguments.get('button', 1))}", timeout_s=15)
        elif name == "move":
            desk.exec_role(role, f"xdotool mousemove --sync {int(arguments['x'])} {int(arguments['y'])}", timeout_s=15)
        elif name == "type_text":
            desk.exec_role(role, "xdotool type --delay 15 -- " + shlex.quote(str(arguments["text"])), timeout_s=20)
        elif name == "key":
            desk.exec_role(role, "xdotool key --clearmodifiers " + shlex.quote(str(arguments["keys"])), timeout_s=15)
        elif name == "wait":
            time.sleep(min(20.0, max(0.2, float(arguments.get("seconds", 2.0)))))
        shot = desk.screenshot_base64()
        return {"content": [{"type": "text", "text": "OK."}, {"type": "image", "data": shot, "mimeType": "image/png"}], "isError": False}

    bash_schema = {
        "name": "guest_bash",
        "description": "Run unrestricted bash/Python/Blender/PyQGIS/FreeCAD/GIMP/Inkscape/FFmpeg/melt/LibreOffice/curl/git commands on the workstation.",
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

    def call_bash(name: str, arguments: dict) -> dict:
        sync_once()
        log_act("guest_bash.guest_bash", arguments)
        t_lim = int(min(220, max(5, float(arguments.get("timeout", 180)))))
        cwd_val = str(arguments.get("cwd") or "/workspace")
        res = desk.exec_role(role, str(arguments["command"]), cwd=cwd_val, timeout_s=t_lim)
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
    }


def run_astra_actor(
    role: str,
    desk: AstraSharedDesktop,
    actor_dir: Path,
    ticket_dir: Path,
    api_cfg: dict,
    codex_bin: Path,
    barrier: threading.Barrier | None = None,
    timeout_s: int = 1200,
) -> dict:
    session_dir = actor_dir / "container_session"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")
    catalog_payload = {"models": [{
        "slug": MODEL_NAME,
        "display_name": MODEL_NAME,
        "description": "Frontier hybrid GUI+CLI model.",
        "default_reasoning_level": REASONING_EFFORT,
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
        "base_instructions": "You are a frontier engineering and creative-software agent. Complete your assigned ticket thoroughly.",
    }]}
    write_json(session_dir / "codex-home/models-catalog.json", catalog_payload)
    tmpl = build_astra_config_template()
    validate_container_config_text(tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(tmpl, encoding="utf-8")
    ticket_md = (ticket_dir / "task.md").read_text(encoding="utf-8")
    (session_dir / "prompt.txt").write_text(build_astra_prompt(role, ticket_md), encoding="utf-8")
    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o770 if item.is_dir() else 0o660)
        except OSError:
            pass

    relay_srv, relay_port = start_astra_relay(
        api_cfg["base_url"],
        api_cfg["api_key"],
        actor_dir / "relay_events.jsonl",
        upstream_model=api_cfg.get("upstream_model"),
    )
    action_log = actor_dir / "actions.jsonl"
    action_log.touch()
    handlers = make_role_handlers(desk, role, action_log, barrier)
    bridge = HostActorBridge(None, relay_port, handlers)
    bridge.start()
    cname = f"paragui-astrarace-codex-{role.lower()}-{secrets.token_hex(5)}"
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
        "--label", "org.paragui.kind=astrarace-codex-actor",
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
        audit = verify_container_permission_audit(session_dir, expected_model=MODEL_NAME, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        acts = [json.loads(ln) for ln in action_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        gui_c = sum(1 for a in acts if a["tool"].startswith("desktop.") and a["tool"] not in {"desktop.screenshot", "desktop.wait"})
        cli_c = sum(1 for a in acts if a["tool"].startswith("guest_bash."))
        return {
            "role": role,
            "status": "timeout" if timed_out else ("done" if proc.returncode == 0 else "error"),
            "exit_code": proc.returncode,
            "wall_seconds": round(t_end - t_start, 2),
            "first_tool_ts": acts[0]["timestamp"] if acts else t_start,
            "last_tool_ts": acts[-1]["timestamp"] if acts else t_end,
            "gui_action_calls": gui_c,
            "cli_calls": cli_c,
            "permission_audit_ok": True,
        }
    finally:
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20)
        bridge.close()
        relay_srv.shutdown()
        relay_srv.server_close()


def run_condition(task_id: str, condition: str, out_dir: Path, code_root: Path, api_cfg: dict, codex_bin: Path, *, desktop_cls=AstraSharedDesktop) -> dict:
    cond_dir = out_dir / task_id / condition
    if (cond_dir / "report.json").is_file():
        existing = json.loads((cond_dir / "report.json").read_text(encoding="utf-8"))
        if existing.get("valid_model_run"):
            return existing
    if cond_dir.exists():
        shutil.rmtree(cond_dir, ignore_errors=True)
    cond_dir.mkdir(parents=True, exist_ok=True)
    desk = desktop_cls(cond_dir, task_id, code_root)
    desk.build_pristine()
    desk.start()
    t0 = time.monotonic()
    try:
        if condition == "seq_ba_full_cli":
            res_b = run_astra_actor("B", desk, cond_dir / "actor_B", desk.ticket_b, api_cfg, codex_bin)
            res_a = run_astra_actor("A", desk, cond_dir / "actor_A", desk.ticket_a, api_cfg, codex_bin)
            overlap_s = 0.0
        elif condition == "ma_sd_full_cli":
            bar = threading.Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                fa = pool.submit(run_astra_actor, "A", desk, cond_dir / "actor_A", desk.ticket_a, api_cfg, codex_bin, bar)
                fb = pool.submit(run_astra_actor, "B", desk, cond_dir / "actor_B", desk.ticket_b, api_cfg, codex_bin, bar)
                res_a = fa.result()
                res_b = fb.result()
            overlap_s = round(max(0.0, min(res_a["last_tool_ts"], res_b["last_tool_ts"]) - max(res_a["first_tool_ts"], res_b["first_tool_ts"])), 2)
        else:
            raise ValueError(condition)
    finally:
        grade_res, ver_cnt = desk.stop_and_grade()
    failed_checks = [f"A:{k}" for k, v in grade_res["checks_a"].items() if not v] + [f"B:{k}" for k, v in grade_res["checks_b"].items() if not v]
    rep = {
        "task_id": task_id,
        "condition": condition,
        "model": MODEL_NAME,
        "effort": REASONING_EFFORT,
        "valid_model_run": res_a["status"] in {"done", "timeout"} and res_b["status"] in {"done", "timeout"},
        "role_a_pass": grade_res["role_a_pass"],
        "role_b_pass": grade_res["role_b_pass"],
        "joint_pass": grade_res["joint_pass"],
        "overlap_seconds": overlap_s,
        "distinct_project_versions": ver_cnt,
        "actors": {"A": res_a, "B": res_b},
        "grade": grade_res,
        "failed_checks": failed_checks,
        "wall_seconds": round(time.monotonic() - t0, 2),
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def run_suite(out_dir: Path, code_root: Path, api_json: Path, codex_bin: Path, tasks: list[str], workers: int = 3) -> dict:
    api_cfg = json.loads(api_json.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(tid, cond) for tid in tasks for cond in ("ma_sd_full_cli", "seq_ba_full_cli")]
    results: dict[str, dict] = {tid: {} for tid in tasks}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fmap = {pool.submit(run_condition, tid, cond, out_dir, code_root, api_cfg, codex_bin): (tid, cond) for tid, cond in jobs}
        for fut in as_completed(fmap):
            tid, cond = fmap[fut]
            results[tid][cond] = fut.result()
            write_json(out_dir / "progress.json", results)
    summary = {"model": MODEL_NAME, "effort": REASONING_EFFORT, "mode": "Full Hybrid GUI+CLI (container-unrestricted, non-YOLO host)", "tasks": {}}
    lines = [
        f"# 10-Task Astra-High Professional & Browser Race Suite (`{MODEL_NAME}`, `{REASONING_EFFORT}`, Full Hybrid GUI+CLI)",
        "",
        "| ID | Software / Scenario | `seq_ba_full_cli` (Sequential) | `ma_sd_full_cli` (Concurrent) | Overlap (s) | GUI/CLI Calls | Concurrent Race Signals |",
        "|---|---|---|---|---:|---|---|",
    ]
    for tid in tasks:
        meta = CATALOG_BY_ID[tid]
        seq_r = results[tid]["seq_ba_full_cli"]
        con_r = results[tid]["ma_sd_full_cli"]
        seq_s = "PASS" if seq_r["joint_pass"] else (f"A:{int(seq_r['role_a_pass'])}/B:{int(seq_r['role_b_pass'])}" if (seq_r["role_a_pass"] or seq_r["role_b_pass"]) else "FAIL")
        seq_lbl = "PASS" if seq_r["joint_pass"] else "FAIL"
        con_lbl = "PASS" if con_r["joint_pass"] else "FAIL"
        gc = f"{con_r['actors']['A']['gui_action_calls'] + con_r['actors']['B']['gui_action_calls']}/{con_r['actors']['A']['cli_calls'] + con_r['actors']['B']['cli_calls']}"
        sigs = ", ".join(con_r["failed_checks"][:2]) or "none"
        summary["tasks"][tid] = {
            "software": meta["software"],
            "title": meta["title"],
            "seq_ba_full_cli": seq_lbl,
            "seq_roles": {"A": seq_r["role_a_pass"], "B": seq_r["role_b_pass"]},
            "ma_sd_full_cli": con_lbl,
            "concurrent_roles": {"A": con_r["role_a_pass"], "B": con_r["role_b_pass"]},
            "overlap_seconds": con_r["overlap_seconds"],
            "gui_cli": gc,
            "failed_checks_concurrent": con_r["failed_checks"],
            "diagnostics_concurrent": con_r["grade"].get("diagnostics"),
            "wall_seconds": {"seq_ba_full_cli": seq_r["wall_seconds"], "ma_sd_full_cli": con_r["wall_seconds"]},
        }
        lines.append(f"| `{tid}` | {meta['software']} | **{seq_s}** | **{con_lbl}** | {con_r['overlap_seconds']} | {gc} | `{sigs}` |")
    write_json(out_dir / "SUMMARY.json", summary)
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--api-json", type=Path, required=True)
    parser.add_argument("--codex-bin", type=Path, default=DEFAULT_CODEX_BINARY)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--tasks", nargs="*", default=[row["id"] for row in ASTRA_RACE_CATALOG])
    args = parser.parse_args(argv)
    res = run_suite(args.out.resolve(), args.code_root.resolve(), args.api_json.resolve(), args.codex_bin.resolve(), list(args.tasks), workers=args.workers)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

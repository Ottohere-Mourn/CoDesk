"""Exam-style 5-case dual-agent (GUI + CLI) contention runner with 5-gate well-posedness check (EC-01..EC-05)."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import threading
import time
from typing import Any


from experiments.codesk_container_codex import (
    CONTAINER_ENTRY_SOURCE,
    DEFAULT_CONTAINER_IMAGE,
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    codex_requirements_mount,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.deepseek_v41_eval import analyze_race_awareness
from experiments.long_horizon_v1 import start_lh_relay
from tasks.exam_contention_v1.common import semantic_doc_equal, write_json
from tasks.exam_contention_v1.registry import EC_BY_ID, EXAM_CONTENTION_CATALOG

DESKTOP_IMAGE = os.environ.get("PARAGUI_EC_DESKTOP_IMAGE", "paragui/astra-recording-desktop:20261113")
AGENT_IMAGE = os.environ.get("CODESK_CODEX_CONTAINER_IMAGE", "paragui/codex-sandbox:20261113")
SCREEN_W, SCREEN_H = 1920, 1080
MODEL_W, MODEL_H = 1280, 720
SCALE_X, SCALE_Y = SCREEN_W / MODEL_W, SCREEN_H / MODEL_H


def build_ec_codex_config(model_name: str, effort: str) -> str:
    return f"""model = {json.dumps(model_name)}
model_provider = "ecbench"
model_reasoning_effort = {json.dumps(effort)}
model_catalog_json = "/session/codex-home/models-catalog.json"
model_context_window = 262144
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "disabled"
mcp_optional_startup_grace_ms = 0

[model_providers.ecbench]
name = "ecbench"
base_url = "http://127.0.0.1:__CONTAINER_RELAY_PORT__/v1"
requires_openai_auth = false
wire_api = "responses"
supports_websockets = false
request_max_retries = 6
stream_max_retries = 6
stream_idle_timeout_ms = 360000

[features]
shell_tool = true
unified_exec = false
multi_agent = false
image_generation = false

[sandbox_workspace_write]
writable_roots = ["/session", "/tmp", "/ipc"]
network_access = true

[apps._default]
enabled = true
default_tools_approval_mode = "approve"

[mcp_servers.desktop]
command = "python3"
args = ["/bridge/mcp_proxy.py", "desktop"]
enabled = true
required = true
enabled_tools = ["screenshot", "click", "click_and_type", "drag", "move", "type_text", "key", "scroll", "wait"]
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
tool_timeout_sec = 300
default_tools_approval_mode = "approve"
"""


def build_exam_agent_prompt(ticket_md: str, timeout_s: int) -> str:
    b = chr(96)
    return (
        f"You are operating a Linux engineering workstation (1280x720 normalized display view, workspace {b}/workspace{b}).\n"
        "You have full access to both GUI desktop interaction tools and workstation shell commands.\n\n"
        f"{ticket_md}\n"
    )


def make_ec_handlers(desk: "ExamContentionDesktop", role: str, action_log: Path, barrier: threading.Barrier | None) -> dict[str, Any]:
    bar_done = {"v": False}
    log_lock = threading.Lock()
    stats = {"gui_obs": 0, "gui_act": 0, "cli": 0}

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

    def sx(x: int | float) -> int:
        return max(0, min(SCREEN_W - 1, int(round(float(x) * SCALE_X))))

    def sy(y: int | float) -> int:
        return max(0, min(SCREEN_H - 1, int(round(float(y) * SCALE_Y))))

    desktop_schemas = [
        {"name": "screenshot", "description": "Capture current 1280x720 desktop screenshot.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "click", "description": "Click mouse button at (x, y) in 1280x720 coordinates.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "button": {"type": "integer", "default": 1}}, "required": ["x", "y"]}},
        {"name": "click_and_type", "description": "Click at (x, y) and type text.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "text": {"type": "string"}, "press_enter": {"type": "boolean", "default": False}}, "required": ["x", "y", "text"]}},
        {"name": "drag", "description": "Smooth drag from (x1, y1) to (x2, y2) in 1280x720 coordinates.", "inputSchema": {"type": "object", "properties": {"x1": {"type": "number"}, "y1": {"type": "number"}, "x2": {"type": "number"}, "y2": {"type": "number"}}, "required": ["x1", "y1", "x2", "y2"]}},
        {"name": "move", "description": "Move pointer to (x, y).", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]}},
        {"name": "type_text", "description": "Type text into focused window.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
        {"name": "key", "description": "Send key press (e.g. Return, ctrl+s, Tab).", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
        {"name": "scroll", "description": "Scroll wheel at (x, y); positive clicks=down, negative=up.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "clicks": {"type": "integer", "default": 4}}, "required": ["x", "y"]}},
        {"name": "wait", "description": "Pause seconds (max 15).", "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 2.0}}}},
    ]
    bash_schema = {
        "name": "guest_bash",
        "description": "Execute bash command on the workstation as UID 1000 in /workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "cwd": {"type": "string", "default": "/workspace"}, "timeout": {"type": "number", "default": 180}},
            "required": ["command"],
        },
    }

    def call_desktop(name: str, arguments: dict) -> dict:
        sync_once()
        log_act(f"desktop.{name}", arguments)
        if name == "screenshot":
            stats["gui_obs"] += 1
            return {"content": [{"type": "image", "data": desk.screenshot_model_b64(), "mimeType": "image/png"}], "isError": False}
        stats["gui_act"] += 1
        if name == "click":
            px, py = sx(arguments["x"]), sy(arguments["y"])
            btn = int(arguments.get("button", 1))
            desk.exec_x11(f"xdotool mousemove --sync {px} {py} click {btn}", timeout_s=15)
            time.sleep(0.25)
            return {"content": [{"type": "text", "text": f"Clicked ({arguments['x']},{arguments['y']})"}, {"type": "image", "data": desk.screenshot_model_b64(), "mimeType": "image/png"}], "isError": False}
        if name == "click_and_type":
            px, py = sx(arguments["x"]), sy(arguments["y"])
            txt = shlex.quote(str(arguments["text"]))
            ent = " && xdotool key --clearmodifiers Return" if arguments.get("press_enter") else ""
            desk.exec_x11(f"xdotool mousemove --sync {px} {py} click 1 && sleep 0.15 && xdotool type --delay 16 -- {txt}{ent}", timeout_s=25)
            time.sleep(0.25)
            return {"content": [{"type": "text", "text": "Clicked and typed"}, {"type": "image", "data": desk.screenshot_model_b64(), "mimeType": "image/png"}], "isError": False}
        if name == "drag":
            x1, y1 = sx(arguments["x1"]), sy(arguments["y1"])
            x2, y2 = sx(arguments["x2"]), sy(arguments["y2"])
            steps = 12
            pts = " && ".join(
                f"xdotool mousemove {int(x1 + (x2 - x1) * k / steps)} {int(y1 + (y2 - y1) * k / steps)} && sleep 0.04"
                for k in range(1, steps + 1)
            )
            desk.exec_x11(f"xdotool mousemove --sync {x1} {y1} mousedown 1 && {pts} && xdotool mouseup 1", timeout_s=20)
            time.sleep(0.25)
            return {"content": [{"type": "text", "text": "Dragged"}, {"type": "image", "data": desk.screenshot_model_b64(), "mimeType": "image/png"}], "isError": False}
        if name == "move":
            desk.exec_x11(f"xdotool mousemove --sync {sx(arguments['x'])} {sy(arguments['y'])}", timeout_s=10)
            return {"content": [{"type": "text", "text": "Moved"}], "isError": False}
        if name == "type_text":
            desk.exec_x11(f"xdotool type --delay 16 -- {shlex.quote(str(arguments['text']))}", timeout_s=20)
            return {"content": [{"type": "text", "text": "Typed text"}], "isError": False}
        if name == "key":
            raw_k = str(arguments["key"]).strip()
            if raw_k.lower().replace(" ", "") in ("f12", "ctrl+shift+i", "ctrl+shift+j", "ctrl+shift+c"):
                return {"content": [{"type": "text", "text": "Key ignored"}], "isError": False}
            desk.exec_x11(f"xdotool key --clearmodifiers {shlex.quote(raw_k)}", timeout_s=15)
            return {"content": [{"type": "text", "text": f"Sent key {raw_k}"}], "isError": False}
        if name == "scroll":
            px, py = sx(arguments["x"]), sy(arguments["y"])
            clicks = int(arguments.get("clicks", 4))
            btn = 5 if clicks >= 0 else 4
            cnt = max(1, min(20, abs(clicks)))
            desk.exec_x11(f"xdotool mousemove --sync {px} {py} click --repeat {cnt} --delay 35 {btn}", timeout_s=15)
            time.sleep(0.2)
            return {"content": [{"type": "text", "text": f"Scrolled {clicks}"}, {"type": "image", "data": desk.screenshot_model_b64(), "mimeType": "image/png"}], "isError": False}
        if name == "wait":
            s = min(15.0, max(0.2, float(arguments.get("seconds", 2.0))))
            time.sleep(s)
            return {"content": [{"type": "text", "text": f"Waited {s}s"}], "isError": False}
        return {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True}

    def call_bash(_name: str, arguments: dict) -> dict:
        sync_once()
        stats["cli"] += 1
        log_act("guest_bash.guest_bash", arguments)
        t_lim = int(min(280, max(5, float(arguments.get("timeout", 180)))))
        cwd_val = str(arguments.get("cwd") or "/workspace")
        res = desk.exec_role(role, str(arguments["command"]), cwd=cwd_val, timeout_s=t_lim)
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
        "_stats": stats,
    }


class ExamContentionDesktop:
    def __init__(self, cond_dir: Path, task_id: str, code_root: Path, record_video: bool = True):
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.record_video = record_video
        self.meta = EC_BY_ID[task_id]
        self.roles: tuple[str, str] = tuple(self.meta["roles"])
        self.workspace = cond_dir / "workspace"
        self.x11_dir = cond_dir / "x11_unix"
        self.downloads_dir = cond_dir / "shared_downloads"
        self.lo_profile_dir = cond_dir / "lo_profile"
        self.tickets_root = cond_dir / "tickets"
        self.service_state_out = cond_dir / "service_state.json"
        self.container_name = f"paragui-ec-{task_id.lower()}-{secrets.token_hex(5)}"
        self.role_containers: dict[str, str] = {}
        self.created = False
        self.recording = False
        self._t0 = time.monotonic()

    def sync_permissions(self) -> None:
        if self.created:
            subprocess.run(["docker", "exec", self.container_name, "chmod", "-R", "a+rX,ug+w", "/workspace"], capture_output=True, timeout=15)

    def build_pristine(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.tickets_root.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
            "-v", f"{self.code_root}:/code:ro",
            "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.tickets_root}:/tickets",
            "-e", "PYTHONPATH=/code", "--entrypoint", "python3", DESKTOP_IMAGE,
            "-m", "tasks.exam_contention_v1.registry", "build",
            "--task", self.task_id, "--workspace", "/workspace", "--tickets-root", "/tickets",
        ], check=True, capture_output=True, text=True, timeout=240)

    def start(self) -> None:
        self._t0 = time.monotonic()
        for d in (self.x11_dir, self.downloads_dir, self.lo_profile_dir):
            d.mkdir(parents=True, exist_ok=True)
            os.chmod(d, 0o777)
        desk_cpus = os.environ.get("PARAGUI_EC_CPUS", "4")
        subprocess.run([
            "docker", "run", "-d", "--name", self.container_name,
            "--cpus", desk_cpus, "--memory", "10g", "--shm-size", "1g",
            "--security-opt", "no-new-privileges",
            "--label", "org.paragui.kind=exam-contention-desktop",
            "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.x11_dir}:/tmp/.X11-unix",
            "-v", f"{self.downloads_dir}:/home/gui/Downloads",
            "-v", f"{self.lo_profile_dir}:/home/gui/.config/libreoffice",
            DESKTOP_IMAGE, "sleep", "infinity",
        ], check=True, capture_output=True, text=True, timeout=90)
        self.created = True

        init_sh = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "id -u studio_ui >/dev/null 2>&1 || useradd -m -u 1001 -s /bin/bash studio_ui; "
            "mkdir -p /opt/ec_state/pkg/tasks/thematic_arenas_v1 /tmp/runtime-gui /tmp/runtime-studio "
            "/home/gui/Downloads /home/gui/.config/openbox /home/gui/.config/libreoffice /home/studio_ui/.config/chromium; "
            "touch /opt/ec_state/pkg/tasks/__init__.py /opt/ec_state/pkg/tasks/thematic_arenas_v1/__init__.py; "
            "chown 0:0 /opt/ec_state && chmod 700 /opt/ec_state /tmp/runtime-studio /home/studio_ui; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chown -R 1001:1001 /tmp/runtime-studio /home/studio_ui; "
            "chmod 1777 /tmp/.X11-unix && chmod -R g+rwX /workspace /home/gui && chown 0:0 /home/gui/Downloads && chmod 755 /home/gui/Downloads"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", init_sh], check=True, capture_output=True, timeout=30)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/exam_contention_v1"), f"{self.container_name}:/opt/ec_state/pkg/tasks/exam_contention_v1"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/thematic_arenas_v1/xlsx_utils.py"), f"{self.container_name}:/opt/ec_state/pkg/tasks/thematic_arenas_v1/xlsx_utils.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "chown -R 0:0 /opt/ec_state && chmod -R 700 /opt/ec_state"], check=True, capture_output=True, timeout=15)

        pport = int(self.meta["portal_port"])
        subprocess.run([
            "docker", "exec", "-d", "-e", "PYTHONPATH=/opt/ec_state/pkg",
            self.container_name, "python3", "-m", "tasks.exam_contention_v1.registry", "serve",
            "--task", self.task_id, "--port", str(pport),
            "--workspace", "/workspace", "--state-dir", "/opt/ec_state", "--boot-file", "/opt/ec_state/boot_url",
        ], check=True, capture_output=True, timeout=20)
        for _ in range(50):
            chk = subprocess.run(["docker", "exec", self.container_name, "curl", "-fsS", f"http://127.0.0.1:{pport}/health"], capture_output=True, timeout=5)
            if chk.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"{self.task_id} portal failed health check")

        boot_x11 = (
            "cat > /home/gui/.config/openbox/rc.xml <<'OBEOF'\n"
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<openbox_config xmlns=\"http://openbox.org/3.4/rc\"><keyboard>"
            "<keybind key=\"F12\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "<keybind key=\"C-S-I\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "<keybind key=\"C-S-J\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "<keybind key=\"C-S-C\"><action name=\"Execute\"><command>/bin/true</command></action></keybind>"
            "</keyboard></openbox_config>\nOBEOF\n"
            "Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 1; "
            "export DISPLAY=:99; xmodmap -e 'keycode 96 = NoSymbol' >/dev/null 2>&1 || true; "
            "dbus-launch --sh-syntax > /tmp/dbus.env 2>/dev/null || true; "
            "openbox --config-file /home/gui/.config/openbox/rc.xml >/tmp/openbox.log 2>&1 &"
        )
        subprocess.run(["docker", "exec", "-d", "--user", "1000:0", "-e", "HOME=/home/gui", self.container_name, "bash", "-lc", boot_x11], check=True, capture_output=True, timeout=20)
        time.sleep(1.5)

        launch_chr = (
            "cp /opt/ec_state/boot_url /home/studio_ui/boot_url && rm -f /opt/ec_state/boot_url && "
            "chown 1001:1001 /home/studio_ui/boot_url && chmod 600 /home/studio_ui/boot_url && "
            "su -s /bin/bash studio_ui -c 'export DISPLAY=:99 HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/runtime-studio; "
            "u=$(cat /home/studio_ui/boot_url); rm -f /home/studio_ui/boot_url; "
            "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
            "--user-data-dir=/home/studio_ui/.config/chromium --window-size=1240,860 \"$u\" >/tmp/studio_browser.log 2>&1 </dev/null &'"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", launch_chr], check=True, capture_output=True, timeout=25)

        open_doc = str(self.meta.get("open_gui_doc") or "")
        unsaved_tag = str(self.meta.get("open_gui_unsaved_tag") or "")
        if open_doc:
            doc_name = Path(open_doc).stem
            if unsaved_tag and open_doc.endswith(".odt"):
                q_txt = shlex.quote(f"[DESK_SESSION_TAG] {unsaved_tag}")
                dirty_cmd = (
                    "xdotool key --clearmodifiers Escape 2>/dev/null || true; sleep 0.2; "
                    f"xdotool type --clearmodifiers --delay 18 -- {q_txt} 2>/dev/null || true; "
                    "xdotool key --clearmodifiers Return 2>/dev/null || true; "
                )
            elif unsaved_tag and open_doc.endswith(".xlsx"):
                q_txt = shlex.quote(unsaved_tag)
                dirty_cmd = (
                    "xdotool key --clearmodifiers Escape 2>/dev/null || true; sleep 0.2; "
                    "xdotool key --clearmodifiers Right Right 2>/dev/null || true; sleep 0.2; "
                    f"xdotool type --clearmodifiers --delay 18 -- {q_txt} 2>/dev/null || true; "
                    "xdotool key --clearmodifiers Return 2>/dev/null || true; "
                )
            else:
                dirty_cmd = "xdotool key --clearmodifiers space BackSpace 2>/dev/null || true; "
            lo_cmd = (
                f"export DISPLAY=:99 HOME=/home/gui XDG_RUNTIME_DIR=/tmp/runtime-gui; "
                f"nohup libreoffice --norestore --nologo --nofirststartwizard '{open_doc}' >/tmp/lo_boot.log 2>&1 & "
                "sleep 4.8; "
                f"wid=$(xdotool search --onlyvisible --name '{doc_name}' | tail -n 1); "
                "if [ -n \"$wid\" ]; then "
                "  xdotool windowactivate --sync \"$wid\" 2>/dev/null || true; sleep 0.3; "
                f"  {dirty_cmd}"
                "fi"
            )
            subprocess.run(["docker", "exec", "--user", "1000:0", self.container_name, "bash", "-lc", lo_cmd], check=True, capture_output=True, timeout=30)

        for r_idx, r_name in enumerate(self.roles):
            rc_name = f"{self.container_name}-r{r_idx}"
            subprocess.run([
                "docker", "run", "-d", "--name", rc_name,
                "--cpus", "3", "--memory", "6g", "--shm-size", "512m",
                "--security-opt", "no-new-privileges",
                "--network", f"container:{self.container_name}",
                "--label", "org.paragui.kind=exam-contention-role",
                "-v", f"{self.workspace}:/workspace",
                "-v", f"{self.downloads_dir}:/home/gui/Downloads",
                "-v", f"{self.lo_profile_dir}:/home/gui/.config/libreoffice",
                DESKTOP_IMAGE, "sleep", "infinity",
            ], check=True, capture_output=True, text=True, timeout=60)
            self.role_containers[r_name] = rc_name
            subprocess.run([
                "docker", "exec", rc_name, "bash", "-lc",
                "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
                "chmod 700 /usr/bin/xmessage /usr/bin/gxmessage /usr/bin/notify-send /usr/bin/xdotool 2>/dev/null || true; "
                "mkdir -p /tmp/runtime-gui /home/gui/work && chown -R 1000:0 /tmp/runtime-gui /home/gui",
            ], check=True, capture_output=True, timeout=20)

        if self.record_video:
            rec_cmd = (
                "echo $$ > /tmp/rollout-ffmpeg.pid; "
                "exec ffmpeg -hide_banner -loglevel warning -nostdin -y "
                "-f x11grab -video_size 1920x1080 -framerate 6 -draw_mouse 1 -i :99.0 "
                "-vf scale=1280:720 -c:v libx264 -threads 2 -preset veryfast -crf 24 -pix_fmt yuv420p "
                "-t 3600 /tmp/rollout.mkv >/tmp/rollout-ffmpeg.log 2>&1"
            )
            subprocess.run(["docker", "exec", "-d", self.container_name, "bash", "-lc", rec_cmd], check=True, capture_output=True, timeout=20)
            self.recording = True

    def exec_x11(self, command_str: str, timeout_s: int = 25) -> dict[str, Any]:
        cp = subprocess.run([
            "docker", "exec", "--user", "1000:0",
            "-e", "DISPLAY=:99", "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
            self.container_name, "bash", "-lc", command_str,
        ], capture_output=True, text=True, timeout=timeout_s)
        return {"ok": cp.returncode == 0, "returncode": cp.returncode}

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 200) -> dict[str, Any]:
        target_ctr = self.role_containers.get(role, self.container_name)
        jdir = f"/tmp/work_{role.lower()}"
        try:
            cp = subprocess.run([
                "docker", "exec", "--user", "1000:0", "-w", cwd,
                "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                "-e", "HISTFILE=/dev/null", "-e", f"TMPDIR={jdir}",
                target_ctr, "bash", "-lc", f"mkdir -p {jdir}; umask 0002; " + command_str,
            ], capture_output=True, text=True, timeout=timeout_s)
            return {"ok": cp.returncode == 0, "returncode": cp.returncode, "stdout": cp.stdout[-12000:], "stderr": cp.stderr[-6000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "stdout": "", "stderr": f"Timed out after {timeout_s}s"}
        finally:
            self.sync_permissions()

    def screenshot_model_b64(self) -> str:
        from PIL import Image
        cp = subprocess.run(["docker", "exec", "--user", "1000:0", "-e", "DISPLAY=:99", self.container_name, "import", "-window", "root", "png:-"], capture_output=True, timeout=20)
        im = Image.open(io.BytesIO(cp.stdout)).convert("RGB")
        if im.size != (MODEL_W, MODEL_H):
            im = im.resize((MODEL_W, MODEL_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def stop_and_grade(self, wall_override_s: float | None = None) -> dict[str, Any]:
        wall_s = wall_override_s if wall_override_s is not None else round(time.monotonic() - self._t0, 2)
        sstate: dict[str, Any] = {}
        try:
            if self.created:
                open_doc = str(self.meta.get("open_gui_doc") or "")
                split_brain = False
                if open_doc:
                    host_doc = self.workspace / Path(open_doc).relative_to("/workspace")
                    pre_snap = self.cond_dir / f".pre_flush_{host_doc.name}"
                    if host_doc.is_file():
                        pre_snap.write_bytes(host_doc.read_bytes())
                    doc_stem = Path(open_doc).stem
                    flush_sh = (
                        "export DISPLAY=:99; "
                        f"wid=$(xdotool search --onlyvisible --name '{doc_stem}' | tail -n 1); "
                        "if [ -n \"$wid\" ]; then "
                        "  xdotool windowactivate --sync \"$wid\" 2>/dev/null || true; sleep 0.3; "
                        "  xdotool key --clearmodifiers ctrl+s 2>/dev/null || true; sleep 1.0; "
                        "  wmctrl -l | grep -qiE 'Confirm|Changed|Modified' && xdotool key --clearmodifiers Return && sleep 1.0 || true; "
                        "fi"
                    )
                    subprocess.run(["docker", "exec", "--user", "1000:0", self.container_name, "bash", "-lc", flush_sh], capture_output=True, timeout=20)
                    if pre_snap.is_file() and host_doc.is_file() and not semantic_doc_equal(pre_snap, host_doc):
                        split_brain = True
                    if pre_snap.is_file():
                        pre_snap.unlink()

                if self.recording:
                    subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "if [ -f /tmp/rollout-ffmpeg.pid ]; then kill -INT $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null || true; fi; sleep 1; ffmpeg -y -i /tmp/rollout.mkv -c copy -movflags +faststart /tmp/desktop-rollout.mp4 >/dev/null 2>&1 || true"], capture_output=True, timeout=45)
                    subprocess.run(["docker", "cp", f"{self.container_name}:/tmp/desktop-rollout.mp4", str(self.cond_dir / "desktop-rollout.mp4")], capture_output=True, timeout=30)
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/ec_state/service_state.json", str(self.service_state_out)], capture_output=True, timeout=15)
                if self.service_state_out.is_file():
                    sstate = json.loads(self.service_state_out.read_text(encoding="utf-8"))
                sstate["open_gui_split_brain"] = split_brain
                write_json(self.service_state_out, sstate)
        finally:
            for rc in list(self.role_containers.values()):
                subprocess.run(["docker", "rm", "-f", rc], capture_output=True, timeout=20)
            self.role_containers.clear()
            if self.created:
                subprocess.run(["docker", "exec", self.container_name, "chmod", "-R", "a+rwX", "/workspace", "/home/gui/Downloads", "/home/gui/.config/libreoffice", "/tmp/.X11-unix"], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=25)
                self.created = False
        if not self.service_state_out.is_file():
            write_json(self.service_state_out, sstate)

        grade_out = self.cond_dir / "grade.json"
        subprocess.run([
            "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
            "-v", f"{self.code_root}:/code:ro", "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.service_state_out}:/service_state.json:ro", "-v", f"{self.cond_dir}:/out",
            "-e", "PYTHONPATH=/code", "--entrypoint", "python3", DESKTOP_IMAGE,
            "-m", "tasks.exam_contention_v1.registry", "grade",
            "--task", self.task_id, "--workspace", "/workspace",
            "--service-state", "/service_state.json", "--wall-seconds", str(wall_s), "--out", "/out/grade.json",
        ], check=True, capture_output=True, text=True, timeout=240)
        return json.loads(grade_out.read_text(encoding="utf-8"))


def run_ec_actor(
    role: str,
    handlers: dict[str, Any],
    actor_dir: Path,
    ticket_dir: Path,
    prompt_text: str,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    timeout_s: int,
) -> dict[str, Any]:
    session_dir = actor_dir / "container_session"
    for rel in ("codex-home", "work", "bridge"):
        (session_dir / rel).mkdir(parents=True, exist_ok=True)
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")
    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")

    codex_model = str(api_cfg.get("model", "gpt-6.1-sol"))
    upstream_model = str(api_cfg.get("upstream_model_sol") or api_cfg.get("upstream_model") or codex_model)
    effort = str(api_cfg.get("reasoning_effort", "high"))

    write_json(session_dir / "codex-home/models-catalog.json", {"models": [{
        "slug": codex_model,
        "display_name": codex_model,
        "description": "Exam contention benchmark agent",
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
        "base_instructions": "You are an autonomous workstation engineer. Complete your work order accurately and verify your deliverables before finishing.",
    }]})
    tmpl = build_ec_codex_config(codex_model, effort)
    validate_container_config_text(tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(tmpl, encoding="utf-8")
    (session_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o770 if item.is_dir() else 0o660)
        except OSError:
            pass

    relay_srv, relay_port = start_lh_relay(api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl", model_name=codex_model, upstream_model=upstream_model)
    bridge = HostActorBridge(None, relay_port, {k: v for k, v in handlers.items() if not k.startswith("_")}, image_history_keep=12, max_request_images=24)
    bridge.start()
    cname = f"paragui-ec-codex-{role.lower()}-{secrets.token_hex(5)}"
    create_cmd = [
        "docker", "create", "--name", cname, "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,size=256m", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "2048", "--cpus", "2", "--memory", "3g", "--user", "1000:0",
        "--label", "org.paragui.kind=ec-codex-actor",
        "-v", f"{session_dir}:/session", "-v", f"{session_dir / 'bridge'}:/bridge:ro",
        "-v", f"{ticket_dir}:/session/ticket:ro", "-v", f"{bridge.ipc_dir}:/ipc",
        "-v", f"{codex_bin.parent}:/codex:ro", "-w", "/session",
        "-e", "HOME=/session", "-e", "CODEX_HOME=/session/codex-home",
        "-e", "CODESK_CONTAINER_PERMISSION_MODE=container-unrestricted",
        "-e", "TOKIO_WORKER_THREADS=4", "-e", "PYTHONDONTWRITEBYTECODE=1",
        *codex_requirements_mount(), AGENT_IMAGE, "python3", "/bridge/container_entry.py",
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
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{session_dir}:/session", AGENT_IMAGE, "chmod", "-R", "ug+rwX", "/session"], capture_output=True, timeout=20)
        audit = verify_container_permission_audit(session_dir, expected_model=codex_model, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        audit_ok = True
        st = handlers["_stats"]
        return {
            "role": role,
            "status": "timeout" if timed_out else ("done" if proc.returncode == 0 else "error"),
            "returncode": proc.returncode,
            "wall_seconds": round(time.time() - t_start, 2),
            "permission_audit_ok": bool(audit_ok),
            "gui_observation_calls": st["gui_obs"],
            "gui_action_calls": st["gui_act"],
            "cli_calls": st["cli"],
        }
    finally:
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20)
        bridge.close()
        relay_srv.shutdown()
        relay_srv.server_close()


def self_validate_exam_case(task_id: str, out_dir: Path, code_root: Path) -> dict[str, Any]:
    """Run all 5 deterministic ground-truth well-posedness gates under real tool timing."""
    meta = EC_BY_ID[task_id]
    role_a, role_b = meta["roles"]
    case_dir = out_dir / task_id
    case_dir.mkdir(parents=True, exist_ok=True)

    def _run_root(desk: ExamContentionDesktop, subcmd: list[str], timeout_s: int = 300) -> str:
        cp = subprocess.run(
            ["docker", "exec", "-e", "PYTHONPATH=/opt/ec_state/pkg", desk.container_name, "python3", "-m", "tasks.exam_contention_v1.registry", *subcmd],
            capture_output=True, text=True, timeout=timeout_s,
        )
        if cp.returncode != 0:
            raise RuntimeError(f"{task_id} {subcmd} failed (rc={cp.returncode}): {cp.stderr[-1200:] or cp.stdout[-1200:]}")
        return cp.stdout

    d1 = ExamContentionDesktop(case_dir / "gate1_pristine", task_id, code_root, record_video=False)
    d1.build_pristine()
    g1 = d1.stop_and_grade(wall_override_s=0.0)

    d2 = ExamContentionDesktop(case_dir / "gate2_seq_ab", task_id, code_root, record_video=False)
    d2.build_pristine(); d2.start()
    try:
        _run_root(d2, ["solve_role", "--task", task_id, "--role", role_a, "--workspace", "/workspace"])
        _run_root(d2, ["solve_role", "--task", task_id, "--role", role_b, "--workspace", "/workspace"])
    finally:
        g2 = d2.stop_and_grade()

    d3 = ExamContentionDesktop(case_dir / "gate3_seq_ba", task_id, code_root, record_video=False)
    d3.build_pristine(); d3.start()
    try:
        _run_root(d3, ["solve_role", "--task", task_id, "--role", role_b, "--workspace", "/workspace"])
        _run_root(d3, ["solve_role", "--task", task_id, "--role", role_a, "--workspace", "/workspace"])
    finally:
        g3 = d3.stop_and_grade()

    d4 = ExamContentionDesktop(case_dir / "gate4_naive_race", task_id, code_root, record_video=False)
    d4.build_pristine(); d4.start()
    try:
        _run_root(d4, ["sim_naive_race", "--task", task_id, "--workspace", "/workspace"])
    finally:
        g4 = d4.stop_and_grade()

    d5 = ExamContentionDesktop(case_dir / "gate5_careful_conc", task_id, code_root, record_video=False)
    d5.build_pristine(); d5.start()
    t5_start = time.monotonic()
    try:
        _run_root(d5, ["sim_careful_conc", "--task", task_id, "--workspace", "/workspace"])
        careful_s = round(time.monotonic() - t5_start, 2)
    finally:
        g5 = d5.stop_and_grade()

    conc_budget_s = float(meta["conc_role_timeout_s"])
    slack_ok = careful_s <= 0.55 * conc_budget_s
    hygiene = g2.get("prompt_hygiene") or {"ok": False}

    all_5_valid = (
        (g1["joint_pass"] is False)
        and (g2["joint_pass"] is True)
        and (g3["joint_pass"] is True)
        and (g4["joint_pass"] is False)
        and (g5["joint_pass"] is True)
        and slack_ok
        and bool(hygiene.get("ok"))
    )

    out = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "roles": list(meta["roles"]),
        "gate1_pristine_pass": g1["joint_pass"],
        "gate2_seq_ab_pass": g2["joint_pass"],
        "gate3_seq_ba_pass": g3["joint_pass"],
        "gate4_naive_race_pass": g4["joint_pass"],
        "gate5_careful_conc_pass": g5["joint_pass"],
        "gate5_careful_conc_seconds": careful_s,
        "conc_role_timeout_s": conc_budget_s,
        "gate5_within_55pct_budget": slack_ok,
        "prompt_hygiene": hygiene,
        "all_5_gates_valid": all_5_valid,
        "diagnostics": {
            "seq_ab_errors": g2["errors_a"] + g2["errors_b"] + g2["errors_joint"],
            "seq_ba_errors": g3["errors_a"] + g3["errors_b"] + g3["errors_joint"],
            "naive_race_errors": g4["errors_a"] + g4["errors_b"] + g4["errors_joint"],
            "careful_conc_errors": g5["errors_a"] + g5["errors_b"] + g5["errors_joint"],
        },
    }
    write_json(case_dir / "self_validation.json", out)
    return out


def run_exam_case(
    task_id: str,
    mode: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict[str, Any],
    codex_bin: Path,
) -> dict[str, Any]:
    meta = EC_BY_ID[task_id]
    ra, rb = meta["roles"]
    model_slug = str(api_cfg.get("model", "gpt-6.1-sol")).replace(".", "_")
    cond_dir = out_dir / task_id / f"{mode}_{model_slug}"
    cond_dir.mkdir(parents=True, exist_ok=True)

    desk = ExamContentionDesktop(cond_dir, task_id, code_root, record_video=True)
    desk.build_pristine()
    desk.start()
    actors: dict[str, Any] = {}
    t0 = time.monotonic()
    try:
        if mode == "shared":
            t_lim = int(meta["conc_role_timeout_s"])
            bar = threading.Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futs = {}
                for r in (ra, rb):
                    adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                    alog = adir / "actions.jsonl"; alog.touch()
                    tdir = desk.tickets_root / r
                    ptxt = build_exam_agent_prompt((tdir / "task.md").read_text(encoding="utf-8"), t_lim)
                    h = make_ec_handlers(desk, r, alog, bar)
                    futs[pool.submit(run_ec_actor, r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)] = r
                for fut in as_completed(futs):
                    actors[futs[fut]] = fut.result()
        elif mode in ("seq_ab", "seq_ba"):
            t_lim = int(meta["seq_role_timeout_s"])
            order = (ra, rb) if mode == "seq_ab" else (rb, ra)
            for r in order:
                adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                alog = adir / "actions.jsonl"; alog.touch()
                tdir = desk.tickets_root / r
                ptxt = build_exam_agent_prompt((tdir / "task.md").read_text(encoding="utf-8"), t_lim)
                h = make_ec_handlers(desk, r, alog, None)
                actors[r] = run_ec_actor(r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)
        else:
            raise ValueError(f"Unsupported mode {mode}")
    finally:
        wall_s = round(time.monotonic() - t0, 2)
        grade_res = desk.stop_and_grade(wall_override_s=wall_s)

    awareness = analyze_race_awareness(cond_dir, (ra, rb))
    aware_cnt = sum(1 for rv in (awareness.get("roles") or {}).values() if rv.get("explicit_race_mentions", 0) > 0)
    rep = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "archetypes": list(meta["archetypes"]),
        "mode": mode,
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "valid_model_run": all(a["status"] in {"done", "timeout"} and a["permission_audit_ok"] for a in actors.values()),
        "all_non_yolo_verified": all(a["permission_audit_ok"] for a in actors.values()),
        "pass_a": grade_res["pass_a"],
        "pass_b": grade_res["pass_b"],
        "joint_pass": grade_res["joint_pass"],
        "gui_action_calls": sum(a["gui_action_calls"] for a in actors.values()),
        "gui_observation_calls": sum(a["gui_observation_calls"] for a in actors.values()),
        "cli_calls": sum(a["cli_calls"] for a in actors.values()),
        "wall_seconds": wall_s,
        "explicit_race_aware_roles_count": aware_cnt,
        "race_awareness": awareness,
        "actors": actors,
        "grade": grade_res,
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("self_validate", "seq_ab", "seq_ba", "shared"), default="self_validate")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--code-root", type=Path, required=True)
    ap.add_argument("--api-json", type=Path, default=None)
    ap.add_argument("--codex-bin", type=Path, default=Path("/codex/codex"))
    ap.add_argument("--effort", default="high")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--tasks", nargs="*", default=[m["id"] for m in EXAM_CONTENTION_CATALOG])
    args = ap.parse_args(argv)
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    code_root = args.code_root.resolve()

    if args.mode == "self_validate":
        res = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            fmap = {pool.submit(self_validate_exam_case, tid, out_dir, code_root): tid for tid in args.tasks}
            for fut in as_completed(fmap):
                tid = fmap[fut]
                r = fut.result()
                res[tid] = r
                print(
                    f"EC_VALIDATED {tid}: all_5_gates={r['all_5_gates_valid']} "
                    f"(pristine={r['gate1_pristine_pass']}, seq_ab={r['gate2_seq_ab_pass']}, "
                    f"seq_ba={r['gate3_seq_ba_pass']}, naive_race={r['gate4_naive_race_pass']}, "
                    f"careful_conc={r['gate5_careful_conc_pass']} in {r['gate5_careful_conc_seconds']}s)",
                    flush=True,
                )
        all_ok = all(v["all_5_gates_valid"] for v in res.values())
        write_json(out_dir / "SELF_VALIDATION_5GATE_SUMMARY.json", {"all_5_gates_valid": all_ok, "cases": dict(sorted(res.items()))})
        return 0 if all_ok else 1

    assert args.api_json is not None, "--api-json required for model evaluation modes"
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    api_cfg["reasoning_effort"] = args.effort
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fmap = {pool.submit(run_exam_case, tid, args.mode, out_dir, code_root, api_cfg, args.codex_bin.resolve()): tid for tid in args.tasks}
        for fut in as_completed(fmap):
            tid = fmap[fut]
            rep = fut.result()
            results[tid] = rep
            print(
                f"DONE {tid} [{rep['mode']}|{rep['model']}]: joint={rep['joint_pass']} "
                f"(A={rep['pass_a']}, B={rep['pass_b']}) GUI={rep['gui_action_calls']+rep['gui_observation_calls']} "
                f"CLI={rep['cli_calls']} aware={rep['explicit_race_aware_roles_count']}/2 wall={rep['wall_seconds']}s",
                flush=True,
            )
            write_json(out_dir / f"SUMMARY_{args.mode}_{api_cfg.get('model','model')}.json", {
                "mode": args.mode,
                "model": api_cfg.get("model"),
                "effort": args.effort,
                "joint_pass_count": sum(1 for v in results.values() if v["joint_pass"]),
                "total_tasks": len(results),
                "results": dict(sorted(results.items())),
            })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Multi-driver (qwen-cua-driver 0.27.0 / xdotool) GUI+CLI contention runner & 5-gate validator for exam_contention_v2."""
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
import shutil
import subprocess
import threading
import time
from typing import Any

from experiments.codesk_container_codex import (
    CONTAINER_ENTRY_SOURCE,
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    codex_requirements_mount,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.deepseek_v41_eval import analyze_race_awareness
from experiments.long_horizon_v1 import start_lh_relay
from tasks.exam_contention_v2.common import read_json_safe, semantic_doc_equal, write_json
from tasks.exam_contention_v2.registry import (
    CANDIDATE_POOL_CATALOG,
    EC2_BY_ID,
    RETAINED_TOP5_IDS,
)

DESKTOP_IMAGE = os.environ.get("PARAGUI_EC2_DESKTOP_IMAGE", "paragui/qwen-cua-desktop:20261120")
AGENT_IMAGE = os.environ.get("CODESK_CODEX_CONTAINER_IMAGE", "paragui/codex-sandbox:20261113")
SCREEN_W, SCREEN_H = 1920, 1080
MODEL_W, MODEL_H = 1280, 720
SCALE_X, SCALE_Y = SCREEN_W / MODEL_W, SCREEN_H / MODEL_H

OPENBOX_RC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <desktops><number>1</number><firstdesk>1</firstdesk></desktops>
  <margins><top>0</top><bottom>0</bottom><left>0</left><right>0</right></margins>
  <placement><policy>UnderMouse</policy><center>yes</center></placement>
  <keyboard>
    <keybind key="A-Tab">
      <action name="NextWindow">
        <dialog>no</dialog>
        <finalactions><action name="Focus"/><action name="Raise"/><action name="Unshade"/></finalactions>
      </action>
    </keybind>
  </keyboard>
  <applications>
    <application class="*"><focus>yes</focus><decor>yes</decor><maximized>no</maximized></application>
  </applications>
</openbox_config>
"""


def _parse_codex_usage(stdout_path: Path) -> dict[str, Any]:
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}
    turns = 0
    if stdout_path.is_file():
        for line in stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = ev.get("usage") if ev.get("type") == "turn.completed" else None
            if isinstance(usage, dict):
                turns += 1
                for k in totals:
                    if isinstance(usage.get(k), int):
                        totals[k] += usage[k]
    return {"available": turns > 0, "turns": turns, **totals}


def build_ec2_codex_config(model_name: str, effort: str, gui_driver: str = "qwen_cua") -> str:
    if gui_driver == "qwen_cua":
        gui_mcp_block = """[mcp_servers.qwen_cua_driver]
command = "python3"
args = ["/bridge/mcp_proxy.py", "qwen_cua_driver"]
enabled = true
required = true
startup_timeout_sec = 45
tool_timeout_sec = 120
default_tools_approval_mode = "approve"
"""
    else:
        gui_mcp_block = """[mcp_servers.desktop]
command = "python3"
args = ["/bridge/mcp_proxy.py", "desktop"]
enabled = true
required = true
enabled_tools = ["screenshot", "click", "click_and_type", "drag", "move", "type_text", "key", "scroll", "wait"]
startup_timeout_sec = 45
tool_timeout_sec = 120
default_tools_approval_mode = "approve"
"""
    return f"""model = {json.dumps(model_name)}
model_provider = "ec2bench"
model_reasoning_effort = {json.dumps(effort)}
model_catalog_json = "/session/codex-home/models-catalog.json"
model_context_window = 262144
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "disabled"
mcp_optional_startup_grace_ms = 0

[model_providers.ec2bench]
name = "ec2bench"
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

{gui_mcp_block}
[mcp_servers.guest_bash]
command = "python3"
args = ["/bridge/mcp_proxy.py", "guest_bash"]
enabled = true
required = true
enabled_tools = ["guest_bash"]
startup_timeout_sec = 30
tool_timeout_sec = 240
default_tools_approval_mode = "approve"
"""


def build_ec2_agent_prompt(ticket_md: str, role: str, timeout_s: int, gui_driver: str, max_cua_calls: int) -> str:
    b = chr(96)
    sess_id = f"s_{role[:10]}"
    if gui_driver == "qwen_cua":
        drv_line = (
            f"- Desktop GUI MCP server: {b}qwen_cua_driver{b} (budget: {max_cua_calls} calls; pass {b}session={json.dumps(sess_id)}{b} where supported). "
            f"Use {b}get_state{b} to list running apps, {b}get_ax_state_and_screenshot{b} / {b}get_screenshot{b} to inspect windows, and act via {b}click{b}, {b}drag{b}, {b}type_text{b}, {b}press_key{b}, {b}hotkey{b}, etc.\n"
        )
    else:
        drv_line = f"- Desktop GUI MCP server: {b}desktop{b} (1280x720 normalized coordinates).\n"
    return (
        f"Workstation runtime notes (Ubuntu/Debian X11 {b}DISPLAY=:99{b} 1920x1080, workspace {b}/workspace{b}, time budget: {timeout_s}s):\n"
        f"{drv_line}"
        f"- Workstation shell MCP tool: {b}guest_bash{b} (runs in {b}/workspace{b} with {b}DISPLAY=:99{b}, AT-SPI2 bus, and standard Linux CLI tools enabled).\n\n"
        f"{ticket_md}\n"
    )


class ExamV2Desktop:
    """Containerized X11 + AT-SPI2 + qwen-cua-driver desktop with isolated or shared per-role workstation containers."""

    def __init__(
        self,
        cond_dir: Path,
        task_id: str,
        code_root: Path,
        active_roles: tuple[str, ...] | None = None,
        record_video: bool = False,
        registry_module: str = "tasks.exam_contention_v2.registry",
        meta_map: dict[str, dict[str, Any]] | None = None,
        extra_task_packages: tuple[str, ...] = (),
    ) -> None:
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.registry_module = registry_module
        self.extra_task_packages = extra_task_packages
        self.meta = (meta_map or EC2_BY_ID)[task_id]
        self.all_roles: tuple[str, str] = tuple(self.meta["roles"])
        self.active_roles: tuple[str, ...] = active_roles or self.all_roles
        self.record_video = record_video

        self.ws_root = cond_dir / "workspaces"
        self.tickets_root = cond_dir / "tickets"
        self.service_state_out = cond_dir / "service_state.json"

        tok = secrets.token_hex(4)
        slug = task_id.lower().replace("-", "")
        self.container_name = f"paragui-ec2-{slug}-{tok}"
        self.x11_vol = f"paragui-ec2-x11-{slug}-{tok}"
        self.xdg_vol = f"paragui-ec2-xdg-{slug}-{tok}"
        self.dl_vol = f"paragui-ec2-dl-{slug}-{tok}"
        self.lo_vol = f"paragui-ec2-lo-{slug}-{tok}"
        self.role_containers: dict[str, str] = {}
        self.created = False
        self.recording = False
        self.atspi_addr = ""

    def gui_env_args(self) -> list[str]:
        envs = [
            "-e", "DISPLAY=:99",
            "-e", "HOME=/home/user",
            "-e", "XDG_RUNTIME_DIR=/run/user/1000",
            "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
            "-e", "GTK_MODULES=gail:atk-bridge",
            "-e", "GNOME_ACCESSIBILITY=1",
            "-e", "ACCESSIBILITY_ENABLED=1",
            "-e", "QT_ACCESSIBILITY=1",
            "-e", "QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1",
            "-e", "SAL_USE_VCLPLUGIN=gtk3",
            "-e", "QWEN_CUA_SOCKET=/run/user/1000/qwen-cua.sock",
            "-e", "PATH=/usr/local/bin:/usr/bin:/bin",
            "-e", "LANG=C.UTF-8",
        ]
        if self.atspi_addr:
            envs.extend(["-e", f"AT_SPI_BUS_ADDRESS={self.atspi_addr}", "-e", f"AT_SPI_BUS={self.atspi_addr}"])
        return envs

    def build_pristine(self) -> None:
        self.ws_root.mkdir(parents=True, exist_ok=True)
        self.tickets_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "6g",
                "-v", f"{self.code_root}:/code:ro",
                "-v", f"{self.ws_root}:/ws_root",
                "-v", f"{self.tickets_root}:/tickets",
                "-e", "PYTHONPATH=/code", "--entrypoint", "python3", DESKTOP_IMAGE,
                "-m", self.registry_module, "build",
                "--task", self.task_id, "--workspace-root", "/ws_root", "--tickets-root", "/tickets",
            ],
            check=True, capture_output=True, text=True, timeout=240,
        )
        for p in [self.ws_root, *self.ws_root.rglob("*")]:
            try:
                os.chmod(p, 0o777 if p.is_dir() else 0o666)
            except OSError:
                pass

    def start(self) -> None:
        for v in (self.x11_vol, self.xdg_vol, self.dl_vol, self.lo_vol):
            subprocess.run(["docker", "volume", "create", v], check=True, capture_output=True, timeout=20)
        self.created = True

        desk_cpus = os.environ.get("PARAGUI_EC2_CPUS", "4")
        desk_ws_mounts = ["-v", f"{self.ws_root}:/ws_root"]
        if self.meta["workspace_mode"] == "shared":
            desk_ws_mounts.extend(["-v", f"{self.ws_root / 'shared'}:/workspace"])
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.container_name,
                "--ipc=shareable", "--cpus", desk_cpus, "--memory", "8g", "--shm-size", "1g",
                "--security-opt", "no-new-privileges",
                "--label", "org.paragui.kind=exam-contention-v2-desktop",
                *desk_ws_mounts,
                "-v", f"{self.x11_vol}:/tmp/.X11-unix",
                "-v", f"{self.xdg_vol}:/run/user/1000",
                "-v", f"{self.dl_vol}:/home/user/Downloads",
                "-v", f"{self.lo_vol}:/home/user/.config",
                DESKTOP_IMAGE, "sleep", "infinity",
            ],
            check=True, capture_output=True, text=True, timeout=75,
        )

        init_sh = (
            "id -u user >/dev/null 2>&1 || useradd -m -u 1000 -g 0 -s /bin/bash user; "
            "mkdir -p /opt/ec2_state/pkg/tasks/thematic_arenas_v1 /run/user/1000 /tmp/.X11-unix "
            "/home/user/Downloads /home/user/.config/openbox; "
            "touch /opt/ec2_state/pkg/tasks/__init__.py /opt/ec2_state/pkg/tasks/thematic_arenas_v1/__init__.py; "
            "printf '#!/bin/sh\\nexec /usr/bin/xclip -selection clipboard >/dev/null 2>&1\\n' > /usr/local/bin/pbcopy; "
            "printf '#!/bin/sh\\nexec /usr/bin/xclip -selection clipboard -o\\n' > /usr/local/bin/pbpaste; "
            "chmod 755 /usr/local/bin/pbcopy /usr/local/bin/pbpaste; "
            "chmod 1777 /tmp/.X11-unix; "
            "chown -R 1000:0 /run/user/1000 /home/user /ws_root; "
            "chmod -R ug+rwX /home/user /ws_root; "
            "chmod 700 /run/user/1000 /opt/ec2_state"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", init_sh], check=True, capture_output=True, timeout=30)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/exam_contention_v2"), f"{self.container_name}:/opt/ec2_state/pkg/tasks/exam_contention_v2"], check=True, capture_output=True, timeout=20)
        for pkg_rel in self.extra_task_packages:
            subprocess.run(["docker", "cp", str(self.code_root / pkg_rel), f"{self.container_name}:/opt/ec2_state/pkg/{pkg_rel}"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/thematic_arenas_v1/xlsx_utils.py"), f"{self.container_name}:/opt/ec2_state/pkg/tasks/thematic_arenas_v1/xlsx_utils.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "chown -R 0:0 /opt/ec2_state && chmod -R 700 /opt/ec2_state"], check=True, capture_output=True, timeout=15)
        subprocess.run(["docker", "exec", "-i", "--user", "1000:0", self.container_name, "bash", "-lc", "cat > /home/user/.config/openbox/rc.xml"], input=OPENBOX_RC_XML.encode("utf-8"), check=True, capture_output=True, timeout=10)

        pport = int(self.meta["portal_port"])
        subprocess.run(
            [
                "docker", "exec", "-d", "-e", "PYTHONPATH=/opt/ec2_state/pkg",
                self.container_name, "python3", "-m", self.registry_module, "serve",
                "--task", self.task_id, "--port", str(pport),
                "--workspace-root", "/ws_root", "--state-dir", "/opt/ec2_state", "--boot-file", "/opt/ec2_state/boot_url",
            ],
            check=True, capture_output=True, timeout=20,
        )
        for _ in range(60):
            chk = subprocess.run(["docker", "exec", self.container_name, "curl", "-fsS", f"http://127.0.0.1:{pport}/health"], capture_output=True, timeout=5)
            if chk.returncode == 0:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError(f"{self.task_id} portal failed health check")

        boot_x11 = (
            "export XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:99 HOME=/home/user; "
            "Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset -nolisten tcp >/tmp/xvfb.log 2>&1 & "
            "sleep 0.9; "
            "dbus-daemon --session --fork --address=unix:path=/run/user/1000/bus; "
            "export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; "
            "/usr/libexec/at-spi-bus-launcher --launch-immediately >/tmp/atspi.log 2>&1 & "
            "sleep 0.8; "
            "AT_ADDR=$(dbus-send --session --dest=org.a11y.Bus --print-reply /org/a11y/bus org.a11y.Bus.GetAddress 2>/dev/null | sed -n 's/.*string \"\\(.*\\)\"/\\1/p' || true); "
            "printf '%s' \"$AT_ADDR\" > /run/user/1000/atspi_addr; "
            "dbus-send --session --dest=org.a11y.Bus --type=method_call /org/a11y/bus org.freedesktop.DBus.Properties.Set string:org.a11y.Status string:IsEnabled variant:boolean:true >/dev/null 2>&1 || true; "
            "dbus-send --session --dest=org.a11y.Bus --type=method_call /org/a11y/bus org.freedesktop.DBus.Properties.Set string:org.a11y.Status string:ScreenReaderEnabled variant:boolean:true >/dev/null 2>&1 || true; "
            "if [ -n \"$AT_ADDR\" ]; then DBUS_SESSION_BUS_ADDRESS=\"$AT_ADDR\" /usr/libexec/at-spi2-registryd --use-gnome-session >/tmp/reg.log 2>&1 & fi; "
            "xsetroot -solid '#1e293b' || true; "
            "openbox >/tmp/openbox.log 2>&1 & "
            "sleep 0.6"
        )
        subprocess.run(["docker", "exec", "--user", "1000:0", "-e", "HOME=/home/user", "-e", "XDG_RUNTIME_DIR=/run/user/1000", self.container_name, "bash", "-lc", boot_x11], check=True, capture_output=True, timeout=30)
        self.atspi_addr = subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "cat /run/user/1000/atspi_addr 2>/dev/null || true"], capture_output=True, text=True, timeout=10).stdout.strip()

        # Boot task-specific desktop apps (GTK3/PyQt5/GIMP/Chromium) inside desk_container before starting qwen-cua-driver
        subprocess.run(
            [
                "docker", "exec", "-e", "PYTHONPATH=/opt/ec2_state/pkg",
                self.container_name, "python3", "-m", self.registry_module, "boot_apps",
                "--task", self.task_id, "--workspace-root", "/ws_root", "--state-dir", "/opt/ec2_state",
            ],
            check=True, capture_output=True, text=True, timeout=60,
        )

        # Open any configured LibreOffice documents using natural WM placement (optional 4th entry `custom_geom` only for special cases)
        for idx, doc_entry in enumerate(self.meta.get("open_gui_docs") or ()):
            doc_p, unsaved_tag, kind = doc_entry[0], doc_entry[1], doc_entry[2]
            custom_geom = doc_entry[3] if len(doc_entry) > 3 else None
            stem = Path(doc_p).stem
            geom_cmd = (
                f"wmctrl -i -r \"$wid\" -b remove,maximized_vert,maximized_horz 2>/dev/null || true; "
                f"wmctrl -i -r \"$wid\" -e {shlex.quote(str(custom_geom))} 2>/dev/null || true; "
                if custom_geom
                else ""
            )
            if unsaved_tag and kind == "writer":
                q_txt = shlex.quote(f"[DESK_SESSION_TAG] {unsaved_tag}")
                dirty = (
                    f"sleep 1.8; wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.3; "
                    f"eval $(xdotool getwindowgeometry --shell \"$wid\" 2>/dev/null || true); "
                    f"xdotool mousemove $(( ${{X:-300}} + ${{WIDTH:-800}} / 2 )) $(( ${{Y:-100}} + 320 )) click 1; sleep 0.3; "
                    f"xdotool key --clearmodifiers ctrl+Home; sleep 0.15; "
                    f"xdotool type --clearmodifiers --delay 18 -- {q_txt}; xdotool key --clearmodifiers Return;"
                )
            elif unsaved_tag and kind == "calc":
                q_txt = shlex.quote(unsaved_tag)
                dirty = f"xdotool key --clearmodifiers Escape; sleep 0.2; xdotool key --clearmodifiers Right Right; sleep 0.2; xdotool type --clearmodifiers --delay 16 -- {q_txt}; xdotool key --clearmodifiers Return;"
            else:
                dirty = ""
            lo_sh = (
                "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
                "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
                "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" SAL_USE_VCLPLUGIN=gtk3; "
                f"nohup libreoffice --norestore --nologo --nofirststartwizard {shlex.quote(doc_p)} >/tmp/lo_boot_{idx}.log 2>&1 & "
                "wid=''; for _w in $(seq 1 25); do "
                f"  wid=$(xdotool search --onlyvisible --name {shlex.quote(stem)} 2>/dev/null | tail -n 1 || true); "
                "  [ -n \"$wid\" ] && break; sleep 0.4; done; sleep 0.8; "
                "if [ -n \"$wid\" ]; then "
                f"  {geom_cmd}"
                "  wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.35; "
                f"  {dirty} "
                "fi"
            )
            subprocess.run(["docker", "exec", "--user", "1000:0", self.container_name, "bash", "-lc", lo_sh], check=True, capture_output=True, timeout=35)

        # Start qwen-cua-driver daemon after initial apps are mapped
        start_cua = (
            "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
            "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
            "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
            "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
            "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 SAL_USE_VCLPLUGIN=gtk3; "
            "qwen-cua-driver telemetry disable >/dev/null 2>&1 || true; "
            "nohup qwen-cua-driver serve --no-overlay --permission-mode standard --grant existing-profile "
            "--socket /run/user/1000/qwen-cua.sock >/tmp/qwen_serve.log 2>&1 </dev/null & "
            "for _i in $(seq 1 35); do [ -S /run/user/1000/qwen-cua.sock ] && break; sleep 0.2; done"
        )
        subprocess.run(["docker", "exec", "--user", "1000:0", self.container_name, "bash", "-lc", start_cua], check=True, capture_output=True, timeout=20)

        # Launch per-role workstation containers (100% open GUI + CLI, isolated or shared /workspace)
        for r_idx, r_name in enumerate(self.active_roles):
            rc_name = f"{self.container_name}-r{r_idx}"
            role_ws = (self.ws_root / r_name) if self.meta["workspace_mode"] == "isolated" else (self.ws_root / "shared")
            role_ws.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    "docker", "run", "-d", "--name", rc_name,
                    "--cpus", "3", "--memory", "6g", "--shm-size", "512m",
                    "--security-opt", "no-new-privileges",
                    "--network", f"container:{self.container_name}",
                    "--ipc", f"container:{self.container_name}",
                    "--label", "org.paragui.kind=exam-contention-v2-role",
                    "-v", f"{role_ws}:/workspace",
                    "-v", f"{self.x11_vol}:/tmp/.X11-unix",
                    "-v", f"{self.xdg_vol}:/run/user/1000",
                    "-v", f"{self.dl_vol}:/home/user/Downloads",
                    "-v", f"{self.lo_vol}:/home/user/.config",
                    DESKTOP_IMAGE, "sleep", "infinity",
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )
            self.role_containers[r_name] = rc_name
            subprocess.run(
                [
                    "docker", "exec", rc_name, "bash", "-lc",
                    "id -u user >/dev/null 2>&1 || useradd -m -u 1000 -g 0 -s /bin/bash user; "
                    "printf '#!/bin/sh\\nexec /usr/bin/xclip -selection clipboard >/dev/null 2>&1\\n' > /usr/local/bin/pbcopy; "
                    "printf '#!/bin/sh\\nexec /usr/bin/xclip -selection clipboard -o\\n' > /usr/local/bin/pbpaste; "
                    "chmod 755 /usr/local/bin/pbcopy /usr/local/bin/pbpaste; "
                    "mkdir -p /home/user/work && chown -R 1000:0 /home/user",
                ],
                check=True, capture_output=True, timeout=20,
            )

    def exec_desk_user(self, cmd: str, timeout_s: float = 25.0) -> dict[str, Any]:
        try:
            cp = subprocess.run(
                ["docker", "exec", "--user", "1000:0", *self.gui_env_args(), self.container_name, "bash", "-lc", cmd],
                capture_output=True, text=True, timeout=timeout_s,
            )
            return {"ok": cp.returncode == 0, "returncode": cp.returncode, "stdout": cp.stdout[-8000:], "stderr": cp.stderr[-4000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "stdout": "", "stderr": f"Timed out after {timeout_s}s"}

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 200) -> dict[str, Any]:
        target_ctr = self.role_containers.get(role, self.container_name)
        jdir = f"/tmp/work_{role.lower()}"
        try:
            cp = subprocess.run(
                [
                    "docker", "exec", "--user", "1000:0", "-w", cwd,
                    *self.gui_env_args(), "-e", "HISTFILE=/dev/null", "-e", f"TMPDIR={jdir}",
                    target_ctr, "bash", "-lc", f"mkdir -p {jdir}; umask 0002; " + command_str,
                ],
                capture_output=True, text=True, timeout=timeout_s,
            )
            return {"ok": cp.returncode == 0, "returncode": cp.returncode, "stdout": cp.stdout[-12000:], "stderr": cp.stderr[-6000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "stdout": "", "stderr": f"Timed out after {timeout_s}s"}
        finally:
            subprocess.run(["docker", "exec", self.container_name, "chmod", "-R", "a+rX,ug+w", "/ws_root"], capture_output=True, timeout=15)

    def snapshot_x11_state(self) -> dict[str, Any]:
        res = self.exec_desk_user(
            "act=$(xdotool getactivewindow 2>/dev/null || true); "
            "act_title=$([ -n \"$act\" ] && xdotool getwindowname \"$act\" 2>/dev/null || true); "
            "loc=$(xdotool getmouselocation --shell 2>/dev/null | tr '\\n' ' ' || true); "
            "clip=$(timeout 1s xclip -selection clipboard -o 2>/dev/null | head -c 160 || true); "
            "wcnt=$(wmctrl -l 2>/dev/null | wc -l || echo 0); "
            "printf \"ACTIVE\\t%s\\t%s\\nMOUSE\\t%s\\nCLIP\\t%s\\nWCNT\\t%s\\n\" \"$act\" \"$act_title\" \"$loc\" \"$clip\" \"$wcnt\"",
            timeout_s=8.0,
        )
        act_id, act_title, mouse_s, clip_val, wcnt = "", "", "", "", 0
        for ln in (res.get("stdout") or "").splitlines():
            if ln.startswith("ACTIVE\t"):
                parts = ln.split("\t", 2)
                act_id = parts[1].strip() if len(parts) > 1 else ""
                act_title = parts[2].strip() if len(parts) > 2 else ""
            elif ln.startswith("MOUSE\t"):
                mouse_s = ln[6:].strip()
            elif ln.startswith("CLIP\t"):
                clip_val = ln[5:]
            elif ln.startswith("WCNT\t"):
                try:
                    wcnt = int(ln[5:].strip())
                except ValueError:
                    wcnt = 0
        return {"active_id": act_id, "active_title": act_title, "mouse": mouse_s, "clipboard": clip_val, "window_count": wcnt}

    def screenshot_model_b64(self) -> str:
        from PIL import Image
        cp = subprocess.run(["docker", "exec", "--user", "1000:0", "-e", "DISPLAY=:99", self.container_name, "import", "-window", "root", "png:-"], capture_output=True, timeout=15)
        if cp.returncode == 0 and cp.stdout[:8] == b"\x89PNG\r\n\x1a\n":
            im = Image.open(io.BytesIO(cp.stdout)).convert("RGB").resize((MODEL_W, MODEL_H))
        else:
            im = Image.new("RGB", (MODEL_W, MODEL_H), (30, 41, 59))
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def stop_and_grade(self, wall_override_s: float = 0.0) -> dict[str, Any]:
        grade_out = self.cond_dir / "grade.json"
        try:
            if self.created:
                split_brain = False
                for doc_p, _tag, _kind in (self.meta.get("open_gui_docs") or ()):
                    stem = Path(doc_p).stem
                    pre_snap = self.cond_dir / f"_pre_{Path(doc_p).name}"
                    post_snap = self.cond_dir / f"_post_{Path(doc_p).name}"
                    subprocess.run(["docker", "cp", f"{self.container_name}:{doc_p}", str(pre_snap)], capture_output=True, timeout=15)
                    flush_sh = (
                        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000; "
                        f"wid=$(xdotool search --onlyvisible --name {shlex.quote(stem)} | tail -n 1); "
                        "if [ -n \"$wid\" ]; then "
                        "  wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.3; "
                        "  xdotool key --clearmodifiers ctrl+s 2>/dev/null || true; sleep 0.9; "
                        "  wmctrl -l | grep -qiE 'Confirm|Changed|Modified' && xdotool key --clearmodifiers Return && sleep 0.8 || true; "
                        "fi"
                    )
                    self.exec_desk_user(flush_sh, timeout_s=15.0)
                    subprocess.run(["docker", "cp", f"{self.container_name}:{doc_p}", str(post_snap)], capture_output=True, timeout=15)
                    if pre_snap.is_file() and post_snap.is_file():
                        if not semantic_doc_equal(pre_snap, post_snap):
                            split_brain = True
                            # Restore pre_snap so CLI disk work earns accurate partial credit while split_brain is recorded
                            subprocess.run(["docker", "cp", str(pre_snap), f"{self.container_name}:{doc_p}"], capture_output=True, timeout=15)
                            subprocess.run(["docker", "exec", self.container_name, "chown", "1000:0", doc_p], capture_output=True, timeout=10)
                    pre_snap.unlink(missing_ok=True)
                    post_snap.unlink(missing_ok=True)

                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/ec2_state/service_state.json", str(self.service_state_out)], capture_output=True, timeout=15)
                sdata = read_json_safe(self.service_state_out)
                sdata["open_gui_split_brain"] = split_brain
                write_json(self.service_state_out, sdata)
                subprocess.run(["docker", "cp", str(self.service_state_out), f"{self.container_name}:/opt/ec2_state/service_state.json"], capture_output=True, timeout=15)

                subprocess.run(
                    [
                        "docker", "exec", "-e", "PYTHONPATH=/opt/ec2_state/pkg",
                        self.container_name, "python3", "-m", self.registry_module, "grade",
                        "--task", self.task_id, "--workspace-root", "/ws_root",
                        "--state-file", "/opt/ec2_state/service_state.json",
                        "--wall-seconds", str(round(wall_override_s, 2)),
                        "--out", "/opt/ec2_state/grade.json",
                    ],
                    check=True, capture_output=True, text=True, timeout=240,
                )
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/ec2_state/grade.json", str(grade_out)], check=True, capture_output=True, timeout=20)
        finally:
            for rc in list(self.role_containers.values()):
                subprocess.run(["docker", "rm", "-f", rc], capture_output=True, timeout=25)
            self.role_containers.clear()
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
                self.created = False
            for v in (self.x11_vol, self.xdg_vol, self.dl_vol, self.lo_vol):
                subprocess.run(["docker", "volume", "rm", "-f", v], capture_output=True, timeout=15)
        return json.loads(grade_out.read_text(encoding="utf-8"))


class RoleMcpBridge:
    """Swappable GUI driver bridge (qwen_cua_driver 0.27.0 or xdotool desktop MCP) + guest_bash with rich telemetry."""

    def __init__(
        self,
        *,
        desk: ExamV2Desktop,
        role: str,
        gui_driver: str,
        max_cua_calls: int,
        action_log: Path,
        shared_timeline: list[dict[str, Any]],
        timeline_lock: threading.Lock,
        barrier: threading.Barrier | None,
    ) -> None:
        self.desk = desk
        self.role = role
        self.gui_driver = gui_driver
        self.max_cua_calls = max_cua_calls
        self.action_log = action_log
        self.shared_timeline = shared_timeline
        self.timeline_lock = timeline_lock
        self.barrier = barrier
        self._synced = False
        self._rpc_lock = threading.Lock()
        self._rpc_id = 0
        self.cua_act_calls = 0
        self.cua_obs_calls = 0
        self.cli_calls = 0
        self.first_call_wall: float | None = None
        self.last_call_wall: float | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._cua_tools: list[dict[str, Any]] = []

        if gui_driver == "qwen_cua":
            self._proc = subprocess.Popen(
                [
                    "docker", "exec", "-i", "--user", "1000:0",
                    *desk.gui_env_args(), desk.container_name,
                    "qwen-cua-driver", "mcp", "--socket", "/run/user/1000/qwen-cua.sock",
                ],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
            )
            self._rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": f"ec2-{role}", "version": "1.0"},
            })
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            self._proc.stdin.flush()
            self._cua_tools = self._rpc("tools/list", {}).get("tools") or []

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def _sync_once(self) -> None:
        if self.barrier is not None and not self._synced:
            self._synced = True
            try:
                self.barrier.wait(timeout=60.0)
            except threading.BrokenBarrierError:
                pass

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert self._proc is not None and self._proc.stdin is not None and self._proc.stdout is not None
        with self._rpc_lock:
            self._rpc_id += 1
            rid = self._rpc_id
            self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
            self._proc.stdin.flush()
            while True:
                ln = self._proc.stdout.readline()
                if not ln:
                    raise RuntimeError(f"qwen-cua-driver closed stdout for {self.role}")
                msg = json.loads(ln)
                if msg.get("id") == rid:
                    if "error" in msg:
                        raise RuntimeError(str(msg["error"]))
                    return msg.get("result") or {}

    def _log_event(self, server: str, tool: str, args: dict[str, Any], sw: float, ew: float, before: dict[str, Any], after: dict[str, Any]) -> None:
        if self.first_call_wall is None:
            self.first_call_wall = sw
        self.last_call_wall = ew
        ev = {
            "timestamp": sw,
            "start_wall": round(sw, 4),
            "end_wall": round(ew, 4),
            "duration_s": round(ew - sw, 4),
            "role": self.role,
            "server": server,
            "tool": f"{server}.{tool}",
            "raw_tool": tool,
            "args": args,
            "win_before": before["active_title"],
            "win_after": after["active_title"],
            "win_id_before": before["active_id"],
            "win_id_after": after["active_id"],
            "pointer_moved": bool(before["mouse"] and after["mouse"] and before["mouse"] != after["mouse"]),
            "clipboard_changed": bool(before["clipboard"] != after["clipboard"]),
        }
        with self.timeline_lock:
            self.shared_timeline.append(ev)
            with self.action_log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    def handlers(self) -> dict[str, Any]:
        bash_schema = {
            "name": "guest_bash",
            "description": "Execute bash command on your Linux workstation in /workspace (DISPLAY=:99 and AT-SPI2 connected).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string", "default": "/workspace"},
                    "timeout": {"type": "number", "default": 180},
                },
                "required": ["command"],
            },
        }

        def call_bash(_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            self._sync_once()
            self.cli_calls += 1
            before = self.desk.snapshot_x11_state()
            sw = time.time()
            t_lim = int(min(220, max(5, float(arguments.get("timeout", 180)))))
            cwd_v = str(arguments.get("cwd") or "/workspace")
            res = self.desk.exec_role(self.role, str(arguments["command"]), cwd=cwd_v, timeout_s=t_lim)
            ew = time.time()
            after = self.desk.snapshot_x11_state()
            self._log_event("guest_bash", "guest_bash", arguments, sw, ew, before, after)
            return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

        if self.gui_driver == "qwen_cua":
            mut_set = {
                "click", "double_click", "right_click", "drag", "scroll",
                "type_text", "set_value", "press_key", "hotkey", "key_down", "key_up", "paste", "select_text",
            }

            def call_qwen(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                self._sync_once()
                if (self.cua_act_calls + self.cua_obs_calls) >= self.max_cua_calls:
                    return {"content": [{"type": "text", "text": f"CUA budget ({self.max_cua_calls}) reached; finish verification via guest_bash."}], "isError": True}
                if name in mut_set:
                    self.cua_act_calls += 1
                else:
                    self.cua_obs_calls += 1
                before = self.desk.snapshot_x11_state()
                sw = time.time()
                try:
                    out = self._rpc("tools/call", {"name": name, "arguments": arguments})
                except Exception as exc:
                    out = {"content": [{"type": "text", "text": f"CUA error: {exc}"}], "isError": True}
                ew = time.time()
                after = self.desk.snapshot_x11_state()
                self._log_event("qwen_cua_driver", name, arguments, sw, ew, before, after)
                return out

            return {
                "qwen_cua_driver": {"list": lambda: self._cua_tools, "call": call_qwen},
                "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
            }

        # Fallback coordinate-based xdotool driver (--gui-driver xdotool)
        desktop_schemas = [
            {"name": "screenshot", "description": "Capture 1280x720 screenshot.", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "click", "description": "Click (x, y) in 1280x720 coordinates.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "button": {"type": "integer", "default": 1}}, "required": ["x", "y"]}},
            {"name": "click_and_type", "description": "Click (x, y) and type text.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "text": {"type": "string"}, "press_enter": {"type": "boolean", "default": False}}, "required": ["x", "y", "text"]}},
            {"name": "drag", "description": "Drag (x1, y1) -> (x2, y2).", "inputSchema": {"type": "object", "properties": {"x1": {"type": "number"}, "y1": {"type": "number"}, "x2": {"type": "number"}, "y2": {"type": "number"}}, "required": ["x1", "y1", "x2", "y2"]}},
            {"name": "move", "description": "Move pointer.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]}},
            {"name": "type_text", "description": "Type text.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
            {"name": "key", "description": "Send key press.", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
            {"name": "scroll", "description": "Scroll wheel.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "clicks": {"type": "integer", "default": 4}}, "required": ["x", "y"]}},
            {"name": "wait", "description": "Wait seconds.", "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 2.0}}}},
        ]

        def sx(x: float) -> int:
            return max(0, min(SCREEN_W - 1, int(round(float(x) * SCALE_X))))

        def sy(y: float) -> int:
            return max(0, min(SCREEN_H - 1, int(round(float(y) * SCALE_Y))))

        def call_desktop(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            self._sync_once()
            before = self.desk.snapshot_x11_state()
            sw = time.time()
            if name == "screenshot":
                self.cua_obs_calls += 1
                res = {"content": [{"type": "image", "data": self.desk.screenshot_model_b64(), "mimeType": "image/png"}], "isError": False}
            else:
                self.cua_act_calls += 1
                if name == "click":
                    self.desk.exec_desk_user(f"xdotool mousemove --sync {sx(arguments['x'])} {sy(arguments['y'])} click {int(arguments.get('button',1))}")
                elif name == "click_and_type":
                    ent = " && xdotool key --clearmodifiers Return" if arguments.get("press_enter") else ""
                    self.desk.exec_desk_user(f"xdotool mousemove --sync {sx(arguments['x'])} {sy(arguments['y'])} click 1 && sleep 0.15 && xdotool type --delay 16 -- {shlex.quote(str(arguments['text']))}{ent}")
                elif name == "drag":
                    x1, y1, x2, y2 = sx(arguments["x1"]), sy(arguments["y1"]), sx(arguments["x2"]), sy(arguments["y2"])
                    pts = " && ".join(f"xdotool mousemove {int(x1+(x2-x1)*k/10)} {int(y1+(y2-y1)*k/10)} && sleep 0.04" for k in range(1, 11))
                    self.desk.exec_desk_user(f"xdotool mousemove --sync {x1} {y1} mousedown 1 && {pts} && xdotool mouseup 1")
                elif name == "move":
                    self.desk.exec_desk_user(f"xdotool mousemove --sync {sx(arguments['x'])} {sy(arguments['y'])}")
                elif name == "type_text":
                    self.desk.exec_desk_user(f"xdotool type --delay 16 -- {shlex.quote(str(arguments['text']))}")
                elif name == "key":
                    self.desk.exec_desk_user(f"xdotool key --clearmodifiers {shlex.quote(str(arguments['key']))}")
                elif name == "scroll":
                    c = int(arguments.get("clicks", 4))
                    self.desk.exec_desk_user(f"xdotool mousemove --sync {sx(arguments['x'])} {sy(arguments['y'])} click --repeat {max(1,min(20,abs(c)))} --delay 35 {5 if c>=0 else 4}")
                elif name == "wait":
                    time.sleep(min(15.0, max(0.2, float(arguments.get("seconds", 2.0)))))
                time.sleep(0.2)
                res = {"content": [{"type": "text", "text": f"Executed {name}"}, {"type": "image", "data": self.desk.screenshot_model_b64(), "mimeType": "image/png"}], "isError": False}
            ew = time.time()
            after = self.desk.snapshot_x11_state()
            self._log_event("desktop", name, arguments, sw, ew, before, after)
            return res

        return {
            "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
            "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
        }


def summarize_ec2_telemetry(timeline: list[dict[str, Any]], roles: tuple[str, str], b_a: RoleMcpBridge | None, b_b: RoleMcpBridge | None) -> dict[str, Any]:
    ordered = sorted(timeline, key=lambda r: r.get("start_wall", 0.0))
    switches = 0
    prev_role = None
    focus_flips = 0
    prev_win = ""
    misrouted_keys = 0
    key_tools = {"press_key", "hotkey", "type_text", "key"}

    for ev in ordered:
        r = ev["role"]
        if prev_role is not None and r != prev_role:
            switches += 1
        prev_role = r
        wa = ev.get("win_after") or ""
        if prev_win and wa and wa != prev_win:
            focus_flips += 1
        if wa:
            prev_win = wa
        if ev.get("raw_tool") in key_tools:
            target_app = str((ev.get("args") or {}).get("app") or "").lower()
            wb = str(ev.get("win_before") or "").lower()
            if target_app and wb and (target_app.split("/")[-1][:6] not in wb):
                misrouted_keys += 1
            elif not wb:
                misrouted_keys += 1

    overlap_s = 0.0
    if b_a and b_b and b_a.first_call_wall and b_a.last_call_wall and b_b.first_call_wall and b_b.last_call_wall:
        overlap_s = max(0.0, min(b_a.last_call_wall, b_b.last_call_wall) - max(b_a.first_call_wall, b_b.first_call_wall))
    elif len(roles) == 2:
        ev_a = [e for e in ordered if e.get("role") == roles[0]]
        ev_b = [e for e in ordered if e.get("role") == roles[1]]
        if ev_a and ev_b:
            a0, a1 = float(ev_a[0]["start_wall"]), float(ev_a[-1].get("end_wall", ev_a[-1]["start_wall"]))
            b0, b1 = float(ev_b[0]["start_wall"]), float(ev_b[-1].get("end_wall", ev_b[-1]["start_wall"]))
            overlap_s = max(0.0, min(a1, b1) - max(a0, b0))

    return {
        "total_events": len(ordered),
        "interleaving_role_switches": switches,
        "overlap_seconds": round(overlap_s, 2),
        "focus_flips": focus_flips,
        "misrouted_keystrokes": misrouted_keys,
        "pointer_moves": sum(1 for e in ordered if e.get("pointer_moved")),
        "clipboard_changes": sum(1 for e in ordered if e.get("clipboard_changed")),
        "roles": list(roles),
    }


def run_ec2_actor(
    *,
    desk: ExamV2Desktop,
    role: str,
    actor_dir: Path,
    prompt_text: str,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    timeout_s: int,
    gui_driver: str,
    max_cua_calls: int,
    shared_timeline: list[dict[str, Any]],
    timeline_lock: threading.Lock,
    barrier: threading.Barrier | None,
) -> tuple[dict[str, Any], RoleMcpBridge]:
    session_dir = actor_dir / "container_session"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")

    model_name = str(api_cfg.get("model", "gpt-6.1-sol"))
    effort = str(api_cfg.get("reasoning_effort", "high"))
    (session_dir / "codex-home/models-catalog.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "slug": model_name,
                        "display_name": model_name,
                        "description": "Qwen CUA Driver + Codex hybrid desktop agent.",
                        "default_reasoning_level": effort,
                        "supported_reasoning_levels": [{"effort": e, "description": e} for e in ("low", "medium", "high", "xhigh")],
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
                        "base_instructions": "You are a precise computer-use and workstation engineering agent.",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    cfg_tmpl = build_ec2_codex_config(model_name, effort, gui_driver=gui_driver)
    validate_container_config_text(cfg_tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(cfg_tmpl, encoding="utf-8")
    (session_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o777 if item.is_dir() else 0o666)
        except OSError:
            pass

    action_log = actor_dir / "actions.jsonl"
    action_log.touch()
    mcp_bridge = RoleMcpBridge(
        desk=desk,
        role=role,
        gui_driver=gui_driver,
        max_cua_calls=max_cua_calls,
        action_log=action_log,
        shared_timeline=shared_timeline,
        timeline_lock=timeline_lock,
        barrier=barrier,
    )
    up_override = api_cfg.get("upstream_model_sol") if "sol" in model_name else api_cfg.get("upstream_model")
    relay_srv, relay_port = start_lh_relay(
        api_cfg["base_url"],
        api_cfg["api_key"],
        actor_dir / "relay.jsonl",
        model_name=model_name,
        upstream_model=up_override,
    )
    host_bridge = HostActorBridge(None, relay_port, mcp_bridge.handlers(), image_history_keep=4, max_request_images=28)
    host_bridge.start()
    for sp in (host_bridge.ipc_dir, host_bridge.relay_sock, host_bridge.mcp_sock):
        try:
            os.chmod(sp, 0o777 if sp.is_dir() else 0o666)
        except OSError:
            pass

    cname = f"paragui-ec2-codex-{role[:16]}-{secrets.token_hex(4)}"
    stdout_p = actor_dir / "codex-stdout.jsonl"
    stderr_p = actor_dir / "codex-stderr.log"
    t0 = time.monotonic()
    status = "done"
    rc = -1
    try:
        with stdout_p.open("w", encoding="utf-8") as out_f, stderr_p.open("w", encoding="utf-8") as err_f:
            proc = subprocess.Popen(
                [
                    "docker", "run", "--rm", "--name", cname,
                    "--network", "none", "--cpus", "2", "--memory", "4g",
                    "--pids-limit", "2048", "--security-opt", "no-new-privileges",
                    "--cap-drop", "ALL", "--read-only",
                    "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g",
                    "--user", "1000:0",
                    "-v", f"{session_dir}:/session",
                    "-v", f"{session_dir / 'bridge'}:/bridge:ro",
                    "-v", f"{host_bridge.ipc_dir}:/ipc",
                    "-v", f"{codex_bin.parent}:/codex:ro",
                    "-w", "/session",
                    "-e", "HOME=/session",
                    "-e", "CODEX_HOME=/session/codex-home",
                    "-e", "CODESK_CONTAINER_PERMISSION_MODE=container-unrestricted",
                    "-e", "TOKIO_WORKER_THREADS=4",
                    "-e", "PYTHONDONTWRITEBYTECODE=1",
                    *codex_requirements_mount(),
                    AGENT_IMAGE, "python3", "/bridge/container_entry.py",
                ],
                stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f, text=True,
            )
            try:
                rc = proc.wait(timeout=timeout_s)
                if rc != 0:
                    status = f"nonzero_exit_{rc}"
            except subprocess.TimeoutExpired:
                status = "timeout"
                subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=20)
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
    finally:
        subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-v", f"{session_dir}:/session", AGENT_IMAGE, "chmod", "-R", "a+rwX", "/session"],
            capture_output=True, timeout=20,
        )
        host_bridge.close()
        relay_srv.shutdown()
        relay_srv.server_close()
        mcp_bridge.close()

    perm_ok = False
    try:
        audit = verify_container_permission_audit(session_dir, expected_model=model_name, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        perm_ok = True
    except Exception as exc:
        write_json(actor_dir / "permission-audit-error.json", {"error": str(exc)})

    usage = _parse_codex_usage(stdout_p)
    summary = {
        "role": role,
        "status": status,
        "returncode": rc,
        "wall_seconds": round(time.monotonic() - t0, 2),
        "permission_audit_ok": perm_ok,
        "gui_driver": gui_driver,
        "gui_action_calls": mcp_bridge.cua_act_calls,
        "gui_observation_calls": mcp_bridge.cua_obs_calls,
        "cli_calls": mcp_bridge.cli_calls,
        "usage": usage,
    }
    write_json(actor_dir / "actor_summary.json", summary)
    return summary, mcp_bridge


def _run_desk_reg(d: ExamV2Desktop, extra_args: list[str], timeout_s: int = 240) -> str:
    cp = subprocess.run(
        ["docker", "exec", "-e", "PYTHONPATH=/opt/ec2_state/pkg", d.container_name, "python3", "-m", d.registry_module, *extra_args],
        check=True, capture_output=True, text=True, timeout=timeout_s,
    )
    return cp.stdout


def self_validate_ec2_case(task_id: str, out_dir: Path, code_root: Path) -> dict[str, Any]:
    meta = EC2_BY_ID[task_id]
    ra, rb = meta["roles"]
    cdir = out_dir / task_id
    cdir.mkdir(parents=True, exist_ok=True)

    # Gate 1: pristine_fail
    d1 = ExamV2Desktop(cdir / "gate1_pristine", task_id, code_root)
    d1.build_pristine()
    try:
        d1.start()
    finally:
        g1 = d1.stop_and_grade()

    # Gate 2: gt_seq_ab_exists
    d2 = ExamV2Desktop(cdir / "gate2_seq_ab", task_id, code_root)
    d2.build_pristine()
    try:
        d2.start()
        _run_desk_reg(d2, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
        _run_desk_reg(d2, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
    finally:
        g2 = d2.stop_and_grade()

    # Gate 3: gt_seq_ba_exists
    d3 = ExamV2Desktop(cdir / "gate3_seq_ba", task_id, code_root)
    d3.build_pristine()
    try:
        d3.start()
        _run_desk_reg(d3, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
        _run_desk_reg(d3, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
    finally:
        g3 = d3.stop_and_grade()

    # Gate 4: gt_contention_surface_active
    d4 = ExamV2Desktop(cdir / "gate4_contention", task_id, code_root)
    d4.build_pristine()
    try:
        d4.start()
        _run_desk_reg(d4, ["sim_contention", "--task", task_id, "--workspace-root", "/ws_root", "--state-dir", "/opt/ec2_state"])
    finally:
        g4 = d4.stop_and_grade()

    # Gate 5: gt_careful_conc_feasible
    d5 = ExamV2Desktop(cdir / "gate5_careful_conc", task_id, code_root)
    d5.build_pristine()
    t5_0 = time.monotonic()
    t5_s = 9999.0
    try:
        d5.start()
        t5_0 = time.monotonic()
        _run_desk_reg(d5, ["careful_conc", "--task", task_id, "--workspace-root", "/ws_root"])
        t5_s = round(time.monotonic() - t5_0, 2)
    finally:
        g5 = d5.stop_and_grade(wall_override_s=round(time.monotonic() - t5_0, 2))

    conc_budget = float(meta["conc_role_timeout_s"])
    gate4_active = (g4["joint_pass"] is False) and (g4["mean_score"] < 0.99)
    all_ok = (
        g1["joint_pass"] is False
        and g1["mean_score"] <= 0.20
        and g2["joint_pass"] is True
        and g2["mean_score"] >= 0.99
        and g3["joint_pass"] is True
        and g3["mean_score"] >= 0.99
        and gate4_active
        and g5["joint_pass"] is True
        and g5["mean_score"] >= 0.99
        and t5_s <= 0.55 * conc_budget
        and bool(g2["prompt_hygiene"]["ok"])
    )
    out = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "track": meta["track"],
        "workspace_mode": meta["workspace_mode"],
        "roles": [ra, rb],
        "gate1_pristine_pass": g1["joint_pass"],
        "gate1_pristine_score": g1["mean_score"],
        "gate2_seq_ab_pass": g2["joint_pass"],
        "gate2_seq_ab_score": g2["mean_score"],
        "gate3_seq_ba_pass": g3["joint_pass"],
        "gate3_seq_ba_score": g3["mean_score"],
        "gate4_contention_pass": g4["joint_pass"],
        "gate4_contention_score": g4["mean_score"],
        "gate4_contention_surface_active": gate4_active,
        "gate5_careful_conc_pass": g5["joint_pass"],
        "gate5_careful_conc_score": g5["mean_score"],
        "gate5_careful_conc_seconds": t5_s,
        "conc_role_timeout_s": conc_budget,
        "gate5_within_55pct_budget": t5_s <= 0.55 * conc_budget,
        "prompt_hygiene": g2["prompt_hygiene"],
        "all_5_gates_valid": all_ok,
        "diagnostics": {
            "seq_ab_errors": g2["errors_a"] + g2["errors_b"] + g2["errors_joint"],
            "seq_ba_errors": g3["errors_a"] + g3["errors_b"] + g3["errors_joint"],
            "contention_errors": g4["errors_a"] + g4["errors_b"] + g4["errors_joint"],
            "careful_conc_errors": g5["errors_a"] + g5["errors_b"] + g5["errors_joint"],
        },
    }
    write_json(cdir / "self_validation_5gate.json", out)
    return out


def run_ec2_case(
    task_id: str,
    mode: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    gui_driver: str = "qwen_cua",
) -> dict[str, Any]:
    meta = EC2_BY_ID[task_id]
    ra, rb = meta["roles"]
    m_slug = str(api_cfg.get("model", "model")).replace(".", "_")
    cond_dir = out_dir / task_id / f"{mode}_{m_slug}"
    cond_dir.mkdir(parents=True, exist_ok=True)
    max_cua = int(meta.get("max_cua_calls", 65))

    if mode == "isolated":
        lim = int(meta["iso_role_timeout_s"])
        t0 = time.monotonic()

        def _run_iso_role(role: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
            sub_dir = cond_dir / f"iso_{role}"
            desk_r = ExamV2Desktop(sub_dir, task_id, code_root, active_roles=(role,), record_video=False)
            desk_r.build_pristine()
            t_md = (desk_r.tickets_root / role / "task.md").read_text(encoding="utf-8")
            desk_r.start()
            tl_r: list[dict[str, Any]] = []
            lk_r = threading.Lock()
            rt0 = time.monotonic()
            try:
                act_s, br_r = run_ec2_actor(
                    desk=desk_r,
                    role=role,
                    actor_dir=cond_dir / f"actor_{role}",
                    prompt_text=build_ec2_agent_prompt(t_md, role, lim, gui_driver, max_cua),
                    api_cfg=api_cfg,
                    codex_bin=codex_bin,
                    timeout_s=lim,
                    gui_driver=gui_driver,
                    max_cua_calls=max_cua,
                    shared_timeline=tl_r,
                    timeline_lock=lk_r,
                    barrier=None,
                )
            finally:
                gr_r = desk_r.stop_and_grade(wall_override_s=round(time.monotonic() - rt0, 2))
            tel_r = summarize_ec2_telemetry(tl_r, (ra, rb), br_r if role == ra else None, br_r if role == rb else None)
            return act_s, gr_r, tel_r

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(_run_iso_role, ra)
            fb = pool.submit(_run_iso_role, rb)
            act_a, gr_a, tel_a = fa.result()
            act_b, gr_b, tel_b = fb.result()

        wall_s = round(time.monotonic() - t0, 2)
        grade_res = {
            "task_id": task_id,
            "score_a": gr_a["score_a"],
            "score_b": gr_b["score_b"],
            "mean_score": round(0.5 * (gr_a["score_a"] + gr_b["score_b"]), 4),
            "pass_a": gr_a["pass_a"],
            "pass_b": gr_b["pass_b"],
            "joint_pass": bool(gr_a["pass_a"] and gr_b["pass_b"]),
            "subchecks_a": gr_a["subchecks_a"],
            "subchecks_b": gr_b["subchecks_b"],
            "errors_a": gr_a["errors_a"],
            "errors_b": gr_b["errors_b"],
            "errors_joint": [],
            "prompt_hygiene": gr_a["prompt_hygiene"],
            "telemetry_a": gr_a.get("telemetry"),
            "telemetry_b": gr_b.get("telemetry"),
        }
        actors = {ra: act_a, rb: act_b}
        contention_tel = {
            "total_events": tel_a["total_events"] + tel_b["total_events"],
            "interleaving_role_switches": 0,
            "overlap_seconds": 0.0,
            "focus_flips": tel_a["focus_flips"] + tel_b["focus_flips"],
            "misrouted_keystrokes": 0,
            "pointer_moves": tel_a["pointer_moves"] + tel_b["pointer_moves"],
            "clipboard_changes": tel_a["clipboard_changes"] + tel_b["clipboard_changes"],
        }
        write_json(cond_dir / "grade.json", grade_res)
    else:
        desk = ExamV2Desktop(cond_dir, task_id, code_root, active_roles=(ra, rb), record_video=False)
        desk.build_pristine()
        tickets = {r: (desk.tickets_root / r / "task.md").read_text(encoding="utf-8") for r in (ra, rb)}
        desk.start()
        shared_tl: list[dict[str, Any]] = []
        tl_lock = threading.Lock()
        actors = {}
        bridges: dict[str, RoleMcpBridge] = {}
        t0 = time.monotonic()
        try:
            if mode == "shared":
                lim = int(meta["conc_role_timeout_s"])
                bar = threading.Barrier(2)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futs = {
                        pool.submit(
                            run_ec2_actor,
                            desk=desk,
                            role=r,
                            actor_dir=cond_dir / f"actor_{r}",
                            prompt_text=build_ec2_agent_prompt(tickets[r], r, lim, gui_driver, max_cua),
                            api_cfg=api_cfg,
                            codex_bin=codex_bin,
                            timeout_s=lim,
                            gui_driver=gui_driver,
                            max_cua_calls=max_cua,
                            shared_timeline=shared_tl,
                            timeline_lock=tl_lock,
                            barrier=bar,
                        ): r
                        for r in (ra, rb)
                    }
                    for fut in as_completed(futs):
                        rn = futs[fut]
                        actors[rn], bridges[rn] = fut.result()
            elif mode in ("seq_ab", "seq_ba"):
                lim = int(meta["iso_role_timeout_s"])
                seq_order = (ra, rb) if mode == "seq_ab" else (rb, ra)
                for r in seq_order:
                    actors[r], bridges[r] = run_ec2_actor(
                        desk=desk,
                        role=r,
                        actor_dir=cond_dir / f"actor_{r}",
                        prompt_text=build_ec2_agent_prompt(tickets[r], r, lim, gui_driver, max_cua),
                        api_cfg=api_cfg,
                        codex_bin=codex_bin,
                        timeout_s=lim,
                        gui_driver=gui_driver,
                        max_cua_calls=max_cua,
                        shared_timeline=shared_tl,
                        timeline_lock=tl_lock,
                        barrier=None,
                    )
            else:
                raise ValueError(f"Unsupported mode {mode}")
        finally:
            wall_s = round(time.monotonic() - t0, 2)
            grade_res = desk.stop_and_grade(wall_override_s=wall_s)
        contention_tel = summarize_ec2_telemetry(shared_tl, (ra, rb), bridges.get(ra), bridges.get(rb))
        write_json(cond_dir / "timeline.json", shared_tl)

    awareness = analyze_race_awareness(cond_dir, (ra, rb))
    aware_cnt = sum(1 for rv in (awareness.get("roles") or {}).values() if rv.get("explicit_race_mentions", 0) > 0)
    tot_in_tok = sum(int((a.get("usage") or {}).get("input_tokens", 0)) for a in actors.values())
    tot_out_tok = sum(int((a.get("usage") or {}).get("output_tokens", 0)) for a in actors.values())
    tot_turns = sum(int((a.get("usage") or {}).get("turns", 0)) for a in actors.values())

    rep = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "track": meta["track"],
        "workspace_mode": meta["workspace_mode"],
        "archetypes": list(meta["archetypes"]),
        "mode": mode,
        "gui_driver": gui_driver,
        "model": api_cfg.get("model", "gpt-6.1-sol"),
        "valid_model_run": all(a["status"] in {"done", "timeout"} and a["permission_audit_ok"] for a in actors.values()),
        "all_non_yolo_verified": all(a["permission_audit_ok"] for a in actors.values()),
        "score_a": grade_res["score_a"],
        "score_b": grade_res["score_b"],
        "mean_score": grade_res["mean_score"],
        "pass_a": grade_res["pass_a"],
        "pass_b": grade_res["pass_b"],
        "joint_pass": grade_res["joint_pass"],
        "gui_action_calls": sum(a["gui_action_calls"] for a in actors.values()),
        "gui_observation_calls": sum(a["gui_observation_calls"] for a in actors.values()),
        "cli_calls": sum(a["cli_calls"] for a in actors.values()),
        "input_tokens_total": tot_in_tok,
        "output_tokens_total": tot_out_tok,
        "turns_total": tot_turns,
        "wall_seconds": wall_s,
        "contention_telemetry": contention_tel,
        "explicit_race_aware_roles_count": aware_cnt,
        "race_awareness": awareness,
        "actors": actors,
        "grade": grade_res,
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    os.umask(0o000)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("self_validate", "isolated", "seq_ab", "seq_ba", "shared"), default="self_validate")
    ap.add_argument("--gui-driver", choices=("qwen_cua", "xdotool"), default="qwen_cua")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--code-root", type=Path, required=True)
    ap.add_argument("--api-json", type=Path, default=None)
    ap.add_argument("--codex-bin", type=Path, default=Path("/codex/codex"))
    ap.add_argument("--effort", default="high")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--tasks", nargs="*", default=[m["id"] for m in CANDIDATE_POOL_CATALOG])
    args = ap.parse_args(argv)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    code_root = args.code_root.resolve()
    task_list = list(RETAINED_TOP5_IDS) if args.tasks == ["top5"] else list(args.tasks)

    if args.mode == "self_validate":
        res = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            fmap = {pool.submit(self_validate_ec2_case, tid, out_dir, code_root): tid for tid in task_list}
            for fut in as_completed(fmap):
                tid = fmap[fut]
                try:
                    r = fut.result()
                except Exception as exc:
                    print(f"EC2_SV_ERROR {tid}: {exc}", flush=True)
                    res[tid] = {"task_id": tid, "all_5_gates_valid": False, "error": str(exc)}
                    continue
                res[tid] = r
                print(
                    f"EC2_VALIDATED {tid}: all_5_gates={r['all_5_gates_valid']} "
                    f"(pristine={r['gate1_pristine_score']}, seq_ab={r['gate2_seq_ab_score']}, "
                    f"seq_ba={r['gate3_seq_ba_score']}, contention={r['gate4_contention_score']}, "
                    f"careful_conc={r['gate5_careful_conc_score']} in {r['gate5_careful_conc_seconds']}s)",
                    flush=True,
                )
        all_ok = all(v["all_5_gates_valid"] for v in res.values())
        write_json(out_dir / "SELF_VALIDATION_5GATE_SUMMARY.json", {"all_5_gates_valid": all_ok, "cases": dict(sorted(res.items()))})
        return 0 if all_ok else 1

    assert args.api_json is not None, "--api-json required for model modes"
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    api_cfg["reasoning_effort"] = args.effort
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fmap = {
            pool.submit(run_ec2_case, tid, args.mode, out_dir, code_root, api_cfg, args.codex_bin.resolve(), args.gui_driver): tid
            for tid in task_list
        }
        for fut in as_completed(fmap):
            tid = fmap[fut]
            rep = fut.result()
            results[tid] = rep
            ct = rep["contention_telemetry"]
            print(
                f"DONE {tid} [{rep['mode']}|{rep['model']}]: mean_score={rep['mean_score']} "
                f"(A={rep['score_a']}, B={rep['score_b']}, joint={rep['joint_pass']}) "
                f"GUI={rep['gui_action_calls']+rep['gui_observation_calls']} CLI={rep['cli_calls']} "
                f"tok={rep['input_tokens_total']} flips={ct['focus_flips']} miskey={ct['misrouted_keystrokes']} wall={rep['wall_seconds']}s",
                flush=True,
            )
            write_json(
                out_dir / f"SUMMARY_{args.mode}_{api_cfg.get('model','model')}.json",
                {
                    "mode": args.mode,
                    "model": api_cfg.get("model"),
                    "effort": args.effort,
                    "gui_driver": args.gui_driver,
                    "mean_score_avg": round(sum(v["mean_score"] for v in results.values()) / max(1, len(results)), 4),
                    "joint_pass_count": sum(1 for v in results.values() if v["joint_pass"]),
                    "total_tasks": len(results),
                    "results": dict(sorted(results.items())),
                },
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

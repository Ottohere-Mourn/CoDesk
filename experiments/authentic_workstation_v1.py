"""Clean multi-agent GUI+CLI runner & 5-gate validator for authentic_workstation_v1 (AW-01..AW-22; curated Top-5)."""
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
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    codex_requirements_mount,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.deepseek_v41_eval import analyze_race_awareness
from experiments.exam_contention_v2 import (
    AGENT_IMAGE,
    DESKTOP_IMAGE,
    MODEL_H,
    MODEL_W,
    OPENBOX_RC_XML,
    SCALE_X,
    SCALE_Y,
    SCREEN_H,
    SCREEN_W,
    _parse_codex_usage,
    build_ec2_codex_config,
    summarize_ec2_telemetry,
)
from experiments.long_horizon_v1 import start_lh_relay
from tasks.authentic_workstation_v1.common import read_json_safe, write_json
from tasks.authentic_workstation_v1.registry import AW_BY_ID, AW_CATALOG, RETAINED_TOP5_IDS

AW_REGISTRY_MOD = "tasks.authentic_workstation_v1.registry"


def build_aw_agent_prompt(ticket_md: str, role: str, timeout_s: int, gui_driver: str) -> str:
    _ = timeout_s
    b = chr(96)
    sess_id = f"s_{role[:10]}"
    if gui_driver == "qwen_cua":
        drv_line = (
            f"- Desktop GUI MCP server: {b}qwen_cua_driver{b} (pass {b}session={json.dumps(sess_id)}{b} where supported). "
            f"Use {b}get_state{b} to list open desktop windows, {b}get_ax_state_and_screenshot{b} / {b}get_screenshot{b} to inspect live applications on the 1920x1080 display, and act via {b}click{b}, {b}drag{b}, {b}type_text{b}, {b}press_key{b}, {b}hotkey{b}, etc.\n"
        )
    else:
        drv_line = f"- Desktop GUI MCP server: {b}desktop{b} (1280x720 normalized screen coordinates).\n"
    return (
        f"Workstation runtime notes (Linux 1920x1080 desktop + CLI workspace {b}/workspace{b}):\n"
        f"{drv_line}"
        f"- Workstation shell MCP tool: {b}guest_bash{b} (executes Linux CLI commands, Python, SQLite, GDAL/OGR, FreeCADCmd, Inkscape CLI, LibreOffice headless, lrelease, ffmpeg, git, and localhost HTTP calls in {b}/workspace{b}; {b}/home/user/Downloads{b} is mounted read-only; interact with and verify live desktop GUI windows via the Desktop GUI MCP server).\n\n"
        f"{ticket_md}\n"
    )


class AuthenticWorkstationDesktop:
    """Clean X11 + AT-SPI2 desktop container paired with X11-isolated, PID/net-shared per-role CLI containers."""

    def __init__(
        self,
        cond_dir: Path,
        task_id: str,
        code_root: Path,
        active_roles: tuple[str, ...] | None = None,
    ) -> None:
        self.cond_dir = cond_dir
        self.task_id = task_id
        self.code_root = code_root
        self.registry_module = AW_REGISTRY_MOD
        self.meta = AW_BY_ID[task_id]
        self.all_roles: tuple[str, str] = tuple(self.meta["roles"])
        self.active_roles: tuple[str, ...] = active_roles or self.all_roles

        self.ws_root = cond_dir / "workspaces"
        self.tickets_root = cond_dir / "tickets"
        self.service_state_out = cond_dir / "service_state.json"

        tok = secrets.token_hex(4)
        slug = task_id.lower().replace("-", "")
        self.container_name = f"paragui-aw-{slug}-{tok}"
        self.dl_vol = f"paragui-aw-dl-{slug}-{tok}"
        self.sp_vol = f"paragui-aw-sp-{slug}-{tok}"
        self.role_containers: dict[str, str] = {}
        self.created = False
        self.atspi_addr = ""

    def desk_x11_env(self) -> list[str]:
        envs = [
            "-e", "DISPLAY=:99",
            "-e", "XAUTHORITY=/tmp/x99.auth",
            "-e", "HOME=/home/user",
            "-e", "XDG_RUNTIME_DIR=/run/user/1000",
            "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
            "-e", "GTK_MODULES=gail:atk-bridge",
            "-e", "GNOME_ACCESSIBILITY=1",
            "-e", "ACCESSIBILITY_ENABLED=1",
            "-e", "QT_ACCESSIBILITY=1",
            "-e", "QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1",
            "-e", "QTWEBENGINE_DISABLE_SANDBOX=1",
            "-e", "LIBGL_ALWAYS_SOFTWARE=1",
            "-e", "QT_X11_NO_MITSHM=1",
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
                "-e", "HOME=/tmp",
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
        subprocess.run(["docker", "volume", "create", self.dl_vol], check=True, capture_output=True, timeout=20)
        if self.meta.get("mount_studio_ro"):
            subprocess.run(["docker", "volume", "create", self.sp_vol], check=True, capture_output=True, timeout=20)
        self.created = True

        desk_cpus = os.environ.get("PARAGUI_AW_CPUS", "4")
        desk_ws_mounts = ["-v", f"{self.ws_root}:/ws_root"]
        if self.meta["workspace_mode"] == "shared":
            desk_ws_mounts.extend(["-v", f"{self.ws_root / 'shared'}:/workspace"])
        if self.meta.get("mount_studio_ro"):
            desk_ws_mounts.extend(["-v", f"{self.sp_vol}:/srv/studio_project"])
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.container_name,
                "--ipc=shareable", "--cpus", desk_cpus, "--memory", "8g", "--shm-size", "1g",
                "--security-opt", "no-new-privileges",
                "--label", "org.paragui.kind=authentic-workstation-v1-desktop",
                *desk_ws_mounts,
                "-v", f"{self.dl_vol}:/home/user/Downloads",
                DESKTOP_IMAGE, "sleep", "infinity",
            ],
            check=True, capture_output=True, text=True, timeout=75,
        )

        init_sh = (
            "id -u user >/dev/null 2>&1 || useradd -m -u 1000 -g 0 -s /bin/bash user; "
            "mkdir -p /opt/aw_state/pkg/tasks/thematic_arenas_v1 /run/user/1000 "
            "/home/user/Downloads /srv/studio_project /home/user/.config/openbox; "
            "touch /opt/aw_state/pkg/tasks/__init__.py /opt/aw_state/pkg/tasks/thematic_arenas_v1/__init__.py; "
            "git config --system --add safe.directory '*' && "
            "git config --system user.name 'Workstation Engineer' && "
            "git config --system user.email 'eng@workstation.local'; "
            "chmod 1777 /tmp; chmod 755 /srv/studio_project; "
            "chown -R 1000:0 /run/user/1000 /home/user /ws_root; "
            "chmod -R ug+rwX /home/user /ws_root; "
            "chmod 700 /run/user/1000 /opt/aw_state"
        )
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", init_sh], check=True, capture_output=True, timeout=30)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/authentic_workstation_v1"), f"{self.container_name}:/opt/aw_state/pkg/tasks/authentic_workstation_v1"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "cp", str(self.code_root / "tasks/thematic_arenas_v1/xlsx_utils.py"), f"{self.container_name}:/opt/aw_state/pkg/tasks/thematic_arenas_v1/xlsx_utils.py"], check=True, capture_output=True, timeout=20)
        subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "chown -R 0:0 /opt/aw_state && chmod -R 700 /opt/aw_state"], check=True, capture_output=True, timeout=15)
        subprocess.run(["docker", "exec", "-i", "--user", "1000:0", self.container_name, "bash", "-lc", "cat > /home/user/.config/openbox/rc.xml"], input=OPENBOX_RC_XML.encode("utf-8"), check=True, capture_output=True, timeout=10)

        pport = int(self.meta["portal_port"])
        subprocess.run(
            [
                "docker", "exec", "-d", "-e", "PYTHONPATH=/opt/aw_state/pkg",
                self.container_name, "python3", "-m", self.registry_module, "serve",
                "--task", self.task_id, "--port", str(pport),
                "--workspace-root", "/ws_root", "--state-dir", "/opt/aw_state", "--boot-file", "/opt/aw_state/boot_url",
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
            "export XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:99 XAUTHORITY=/tmp/x99.auth HOME=/home/user; "
            "COOKIE=$(python3 -c 'import secrets; print(secrets.token_hex(16))'); "
            "xauth -f /tmp/x99.auth add :99 . \"$COOKIE\" && chmod 644 /tmp/x99.auth; "
            "Xvfb :99 -screen 0 1920x1080x24 -auth /tmp/x99.auth +extension GLX +render -noreset -nolisten tcp >/tmp/xvfb.log 2>&1 </dev/null & "
            "sleep 0.9; "
            "dbus-daemon --session --fork --address=unix:path=/run/user/1000/bus; "
            "export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; "
            "/usr/libexec/at-spi-bus-launcher --launch-immediately >/tmp/atspi.log 2>&1 </dev/null & "
            "sleep 0.8; "
            "AT_ADDR=$(dbus-send --session --dest=org.a11y.Bus --print-reply /org/a11y/bus org.a11y.Bus.GetAddress 2>/dev/null | sed -n 's/.*string \"\\(.*\\)\"/\\1/p' || true); "
            "printf '%s' \"$AT_ADDR\" > /run/user/1000/atspi_addr; "
            "dbus-send --session --dest=org.a11y.Bus --type=method_call /org/a11y.Bus org.freedesktop.DBus.Properties.Set string:org.a11y.Status string:IsEnabled variant:boolean:true >/dev/null 2>&1 || true; "
            "if [ -n \"$AT_ADDR\" ]; then DBUS_SESSION_BUS_ADDRESS=\"$AT_ADDR\" /usr/libexec/at-spi2-registryd --use-gnome-session >/tmp/reg.log 2>&1 </dev/null & fi; "
            "xsetroot -solid '#1e293b' || true; "
            "openbox >/tmp/openbox.log 2>&1 </dev/null & "
            "sleep 0.6"
        )
        subprocess.run(["docker", "exec", "--user", "1000:0", "-e", "HOME=/home/user", "-e", "XDG_RUNTIME_DIR=/run/user/1000", self.container_name, "bash", "-lc", boot_x11], check=True, capture_output=True, timeout=30)
        self.atspi_addr = subprocess.run(["docker", "exec", self.container_name, "bash", "-lc", "cat /run/user/1000/atspi_addr 2>/dev/null || true"], capture_output=True, text=True, timeout=10).stdout.strip()

        # Boot real open-source desktop apps ONLY for active_roles (scoped isolated mode!)
        subprocess.run(
            [
                "docker", "exec", "-e", "PYTHONPATH=/opt/aw_state/pkg",
                self.container_name, "python3", "-m", self.registry_module, "boot_apps",
                "--task", self.task_id, "--workspace-root", "/ws_root", "--state-dir", "/opt/aw_state",
                "--active-roles", ",".join(self.active_roles),
            ],
            check=True, capture_output=True, text=True, timeout=90,
        )

        start_cua = (
            "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
            "export DISPLAY=:99 XAUTHORITY=/tmp/x99.auth HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
            "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
            "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
            "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 SAL_USE_VCLPLUGIN=gtk3; "
            "qwen-cua-driver telemetry disable >/dev/null 2>&1 || true; "
            "nohup qwen-cua-driver serve --no-overlay --permission-mode standard --grant existing-profile "
            "--socket /run/user/1000/qwen-cua.sock >/tmp/qwen_serve.log 2>&1 </dev/null & "
            "for _i in $(seq 1 35); do [ -S /run/user/1000/qwen-cua.sock ] && break; sleep 0.2; done"
        )
        subprocess.run(["docker", "exec", "--user", "1000:0", self.container_name, "bash", "-lc", start_cua], check=True, capture_output=True, timeout=25)

        # Launch per-role CLI containers (shares --network and --pid, NO X11/AT-SPI sockets, read-only ~/Downloads)
        for r_idx, r_name in enumerate(self.active_roles):
            rc_name = f"{self.container_name}-r{r_idx}"
            role_ws = (self.ws_root / r_name) if self.meta["workspace_mode"] == "isolated" else (self.ws_root / "shared")
            role_ws.mkdir(parents=True, exist_ok=True)
            extra_ro = ["-v", f"{self.sp_vol}:/srv/studio_project:ro"] if self.meta.get("mount_studio_ro") else []
            subprocess.run(
                [
                    "docker", "run", "-d", "--name", rc_name,
                    "--cpus", "3", "--memory", "6g", "--shm-size", "512m",
                    "--security-opt", "no-new-privileges",
                    "--network", f"container:{self.container_name}",
                    "--pid", f"container:{self.container_name}",
                    "--label", "org.paragui.kind=authentic-workstation-v1-role",
                    "-v", f"{role_ws}:/workspace",
                    "-v", f"{self.dl_vol}:/home/user/Downloads:ro",
                    *extra_ro,
                    DESKTOP_IMAGE, "sleep", "infinity",
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )
            self.role_containers[r_name] = rc_name
            subprocess.run(
                [
                    "docker", "exec", rc_name, "bash", "-lc",
                    "id -u cli_user >/dev/null 2>&1 || useradd -m -u 2000 -g 0 -s /bin/bash cli_user; "
                    "git config --system --add safe.directory '*' && "
                    "git config --system user.name 'Workstation Engineer' && "
                    "git config --system user.email 'eng@workstation.local'; "
                    "mkdir -p /home/cli_user/work && chown -R 2000:0 /home/cli_user && chmod -R ug+rwX /workspace",
                ],
                check=True, capture_output=True, timeout=20,
            )

    def exec_desk_user(self, cmd: str, timeout_s: float = 25.0) -> dict[str, Any]:
        try:
            cp = subprocess.run(
                ["docker", "exec", "--user", "1000:0", *self.desk_x11_env(), self.container_name, "bash", "-lc", cmd],
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
                    "docker", "exec", "--user", "2000:0", "-w", cwd,
                    "-e", "HOME=/home/cli_user", "-e", "LANG=C.UTF-8",
                    "-e", "HISTFILE=/dev/null", "-e", f"TMPDIR={jdir}",
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

        cp = subprocess.run(["docker", "exec", "--user", "1000:0", "-e", "DISPLAY=:99", "-e", "XAUTHORITY=/tmp/x99.auth", self.container_name, "import", "-window", "root", "png:-"], capture_output=True, timeout=15)
        if cp.returncode == 0 and cp.stdout[:8] == b"\x89PNG\r\n\x1a\n":
            im = Image.open(io.BytesIO(cp.stdout)).convert("RGB").resize((MODEL_W, MODEL_H))
        else:
            im = Image.new("RGB", (MODEL_W, MODEL_H), (30, 41, 59))
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def stop_and_grade(self, wall_override_s: float = 0.0, active_mode: str = "shared") -> dict[str, Any]:
        """100% read-only post-episode grading (never injects keystrokes or mutates workspace files)."""
        grade_out = self.cond_dir / "grade.json"
        try:
            if self.created:
                w_snap = self.exec_desk_user("wmctrl -lx 2>/dev/null || true", timeout_s=8.0)
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/aw_state/service_state.json", str(self.service_state_out)], capture_output=True, timeout=15)
                sdata = read_json_safe(self.service_state_out)
                sdata["open_windows_at_exit"] = [ln.strip() for ln in (w_snap.get("stdout") or "").splitlines() if ln.strip()]
                write_json(self.service_state_out, sdata)
                subprocess.run(["docker", "cp", str(self.service_state_out), f"{self.container_name}:/opt/aw_state/service_state.json"], capture_output=True, timeout=15)

                subprocess.run(
                    [
                        "docker", "exec", "-e", "HOME=/tmp", "-e", "PYTHONPATH=/opt/aw_state/pkg",
                        self.container_name, "python3", "-m", self.registry_module, "grade",
                        "--task", self.task_id, "--workspace-root", "/ws_root",
                        "--state-file", "/opt/aw_state/service_state.json",
                        "--wall-seconds", str(round(wall_override_s, 2)),
                        "--active-mode", active_mode,
                        "--out", "/opt/aw_state/grade.json",
                    ],
                    check=True, capture_output=True, text=True, timeout=240,
                )
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/aw_state/grade.json", str(grade_out)], check=True, capture_output=True, timeout=20)
        finally:
            for rc in list(self.role_containers.values()):
                subprocess.run(["docker", "rm", "-f", rc], capture_output=True, timeout=25)
            self.role_containers.clear()
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
                self.created = False
            subprocess.run(["docker", "volume", "rm", "-f", self.dl_vol], capture_output=True, timeout=15)
            if self.meta.get("mount_studio_ro"):
                subprocess.run(["docker", "volume", "rm", "-f", self.sp_vol], capture_output=True, timeout=15)
        return json.loads(grade_out.read_text(encoding="utf-8"))


class AwRoleMcpBridge:
    """GUI driver bridge (qwen-cua-driver 0.27.0 on desk_container) + X11-isolated guest_bash on role_container."""

    def __init__(
        self,
        *,
        desk: AuthenticWorkstationDesktop,
        role: str,
        gui_driver: str,
        action_log: Path,
        shared_timeline: list[dict[str, Any]],
        timeline_lock: threading.Lock,
        barrier: threading.Barrier | None,
    ) -> None:
        self.desk = desk
        self.role = role
        self.gui_driver = gui_driver
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
                    *desk.desk_x11_env(), desk.container_name,
                    "qwen-cua-driver", "mcp", "--socket", "/run/user/1000/qwen-cua.sock",
                ],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
            )
            self._rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": f"aw-{role}", "version": "1.0"},
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
            "description": (
                "Execute bash command in /workspace on your Linux CLI workstation "
                "(Python, SQLite, GDAL/OGR, FreeCADCmd, Inkscape CLI, LibreOffice headless, lrelease, ffmpeg, git, localhost; "
                "/home/user/Downloads is read-only; use the GUI MCP server for live X11 windows)."
            ),
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

        desktop_schemas = [
            {"name": "screenshot", "description": "Capture 1280x720 screenshot.", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "click", "description": "Click (x, y) in 1280x720 coordinates.", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "button": {"type": "integer", "default": 1}}, "required": ["x", "y"]}},
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
                    self.desk.exec_desk_user(f"xdotool mousemove --sync {sx(arguments['x'])} {sy(arguments['y'])} click {int(arguments.get('button', 1))}")
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
                    self.desk.exec_desk_user(f"xdotool mousemove --sync {sx(arguments['x'])} {sy(arguments['y'])} click --repeat {max(1, min(20, abs(c)))} --delay 35 {5 if c >= 0 else 4}")
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


def run_aw_actor(
    *,
    desk: AuthenticWorkstationDesktop,
    role: str,
    actor_dir: Path,
    prompt_text: str,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    timeout_s: int,
    gui_driver: str,
    shared_timeline: list[dict[str, Any]],
    timeline_lock: threading.Lock,
    barrier: threading.Barrier | None,
) -> tuple[dict[str, Any], AwRoleMcpBridge]:
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
                        "description": "Authentic workstation hybrid GUI+CLI agent.",
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
    mcp_bridge = AwRoleMcpBridge(
        desk=desk,
        role=role,
        gui_driver=gui_driver,
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

    cname = f"paragui-aw-codex-{role[:16]}-{secrets.token_hex(4)}"
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


def _run_aw_reg(d: AuthenticWorkstationDesktop, extra_args: list[str], timeout_s: int = 240) -> str:
    cp = subprocess.run(
        [
            "docker", "exec", "-e", "HOME=/tmp", "-e", "PYTHONPATH=/opt/aw_state/pkg",
            d.container_name, "python3", "-m", d.registry_module, *extra_args,
        ],
        check=True, capture_output=True, text=True, timeout=timeout_s,
    )
    return cp.stdout


def self_validate_aw_case(task_id: str, out_dir: Path, code_root: Path) -> dict[str, Any]:
    meta = AW_BY_ID[task_id]
    ra, rb = meta["roles"]
    cdir = out_dir / task_id
    cdir.mkdir(parents=True, exist_ok=True)

    d1 = AuthenticWorkstationDesktop(cdir / "gate1_pristine", task_id, code_root)
    d1.build_pristine()
    try:
        d1.start()
    finally:
        g1 = d1.stop_and_grade(active_mode="shared")

    d2 = AuthenticWorkstationDesktop(cdir / "gate2_seq_ab", task_id, code_root)
    d2.build_pristine()
    try:
        d2.start()
        _run_aw_reg(d2, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
        _run_aw_reg(d2, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
    finally:
        g2 = d2.stop_and_grade(active_mode="seq_ab")

    d3 = AuthenticWorkstationDesktop(cdir / "gate3_seq_ba", task_id, code_root)
    d3.build_pristine()
    try:
        d3.start()
        _run_aw_reg(d3, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
        _run_aw_reg(d3, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
    finally:
        g3 = d3.stop_and_grade(active_mode="seq_ba")

    d4 = AuthenticWorkstationDesktop(cdir / "gate4_contention", task_id, code_root)
    d4.build_pristine()
    try:
        d4.start()
        _run_aw_reg(d4, ["sim_contention", "--task", task_id, "--workspace-root", "/ws_root", "--state-dir", "/opt/aw_state"])
    finally:
        g4 = d4.stop_and_grade(active_mode="shared")

    d5 = AuthenticWorkstationDesktop(cdir / "gate5_careful_conc", task_id, code_root)
    d5.build_pristine()
    t5_0 = time.monotonic()
    t5_s = 9999.0
    try:
        d5.start()
        t5_0 = time.monotonic()
        _run_aw_reg(d5, ["careful_conc", "--task", task_id, "--workspace-root", "/ws_root"])
        t5_s = round(time.monotonic() - t5_0, 2)
    finally:
        g5 = d5.stop_and_grade(wall_override_s=round(time.monotonic() - t5_0, 2), active_mode="shared")

    conc_budget = float(meta["conc_role_timeout_s"])
    gate4_active = (g4["joint_pass"] is False) or (g4["mean_score"] < 0.95)
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


def run_aw_case(
    task_id: str,
    mode: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    gui_driver: str = "qwen_cua",
) -> dict[str, Any]:
    meta = AW_BY_ID[task_id]
    ra, rb = meta["roles"]
    m_slug = str(api_cfg.get("model", "model")).replace(".", "_")
    cond_dir = out_dir / task_id / f"{mode}_{m_slug}"
    cond_dir.mkdir(parents=True, exist_ok=True)

    existing_grade = cond_dir / "grade.json"
    existing_actors = {r: cond_dir / f"actor_{r}" / "actor_summary.json" for r in (ra, rb)}
    if existing_grade.is_file() and all(p.is_file() for p in existing_actors.values()):
        grade_res = read_json_safe(existing_grade)
        actors = {r: read_json_safe(existing_actors[r]) for r in (ra, rb)}
        wall_s = round(max(float(actors[ra]["wall_seconds"]), float(actors[rb]["wall_seconds"])), 2)
        if mode == "isolated":
            per_r_tel = {}
            for r in (ra, rb):
                al = cond_dir / f"actor_{r}" / "actions.jsonl"
                evs = [json.loads(ln) for ln in al.read_text(encoding="utf-8").splitlines() if ln.strip()] if al.is_file() else []
                per_r_tel[r] = summarize_ec2_telemetry(evs, (ra, rb), None, None)
            contention_tel = {
                "total_events": per_r_tel[ra]["total_events"] + per_r_tel[rb]["total_events"],
                "interleaving_role_switches": 0,
                "overlap_seconds": 0.0,
                "focus_flips": per_r_tel[ra]["focus_flips"] + per_r_tel[rb]["focus_flips"],
                "misrouted_keystrokes": 0,
                "pointer_moves": per_r_tel[ra]["pointer_moves"] + per_r_tel[rb]["pointer_moves"],
                "clipboard_changes": per_r_tel[ra]["clipboard_changes"] + per_r_tel[rb]["clipboard_changes"],
            }
        else:
            stl_p = cond_dir / "shared_timeline.json"
            shared_tl = json.loads(stl_p.read_text(encoding="utf-8")) if stl_p.is_file() else []
            contention_tel = summarize_ec2_telemetry(shared_tl, (ra, rb), None, None)
    elif mode == "isolated":
        lim = int(meta["iso_role_timeout_s"])
        t0 = time.monotonic()

        def _run_iso(role: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
            sub_d = cond_dir / f"iso_{role}"
            desk_r = AuthenticWorkstationDesktop(sub_d, task_id, code_root, active_roles=(role,))
            desk_r.build_pristine()
            t_md = (desk_r.tickets_root / role / "task.md").read_text(encoding="utf-8")
            desk_r.start()
            tl_r: list[dict[str, Any]] = []
            lk_r = threading.Lock()
            rt0 = time.monotonic()
            try:
                act_s, br_r = run_aw_actor(
                    desk=desk_r,
                    role=role,
                    actor_dir=cond_dir / f"actor_{role}",
                    prompt_text=build_aw_agent_prompt(t_md, role, lim, gui_driver),
                    api_cfg=api_cfg,
                    codex_bin=codex_bin,
                    timeout_s=lim,
                    gui_driver=gui_driver,
                    shared_timeline=tl_r,
                    timeline_lock=lk_r,
                    barrier=None,
                )
            finally:
                gr_r = desk_r.stop_and_grade(wall_override_s=round(time.monotonic() - rt0, 2), active_mode="isolated")
            tel_r = summarize_ec2_telemetry(tl_r, (ra, rb), br_r if role == ra else None, br_r if role == rb else None)
            return act_s, gr_r, tel_r

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(_run_iso, ra)
            fb = pool.submit(_run_iso, rb)
            act_a, gr_a, tel_a = fa.result()
            act_b, gr_b, tel_b = fb.result()

        wall_s = round(time.monotonic() - t0, 2)
        grade_res = {
            "task_id": task_id,
            "active_mode": "isolated",
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
        desk = AuthenticWorkstationDesktop(cond_dir, task_id, code_root, active_roles=(ra, rb))
        desk.build_pristine()
        tickets = {r: (desk.tickets_root / r / "task.md").read_text(encoding="utf-8") for r in (ra, rb)}
        desk.start()
        shared_tl: list[dict[str, Any]] = []
        tl_lock = threading.Lock()
        actors = {}
        bridges: dict[str, AwRoleMcpBridge] = {}
        t0 = time.monotonic()
        try:
            lim = int(meta["conc_role_timeout_s"])
            bar = threading.Barrier(2) if mode == "shared" else None
            if mode == "shared":
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futs = {
                        pool.submit(
                            run_aw_actor,
                            desk=desk,
                            role=r,
                            actor_dir=cond_dir / f"actor_{r}",
                            prompt_text=build_aw_agent_prompt(tickets[r], r, lim, gui_driver),
                            api_cfg=api_cfg,
                            codex_bin=codex_bin,
                            timeout_s=lim,
                            gui_driver=gui_driver,
                            shared_timeline=shared_tl,
                            timeline_lock=tl_lock,
                            barrier=bar,
                        ): r
                        for r in (ra, rb)
                    }
                    for f in as_completed(futs):
                        rk = futs[f]
                        actors[rk], bridges[rk] = f.result()
            else:
                order = (ra, rb) if mode == "seq_ab" else (rb, ra)
                for rk in order:
                    actors[rk], bridges[rk] = run_aw_actor(
                        desk=desk,
                        role=rk,
                        actor_dir=cond_dir / f"actor_{rk}",
                        prompt_text=build_aw_agent_prompt(tickets[rk], rk, lim, gui_driver),
                        api_cfg=api_cfg,
                        codex_bin=codex_bin,
                        timeout_s=lim,
                        gui_driver=gui_driver,
                        shared_timeline=shared_tl,
                        timeline_lock=tl_lock,
                        barrier=None,
                    )
            wall_s = round(time.monotonic() - t0, 2)
        finally:
            grade_res = desk.stop_and_grade(wall_override_s=round(time.monotonic() - t0, 2), active_mode=mode)
        contention_tel = summarize_ec2_telemetry(shared_tl, (ra, rb), bridges.get(ra), bridges.get(rb))
        write_json(cond_dir / "shared_timeline.json", shared_tl)

    awareness = analyze_race_awareness(cond_dir, (ra, rb))
    aware_cnt = sum(1 for rv in (awareness.get("roles") or {}).values() if rv.get("explicit_race_mentions", 0) > 0)

    tot_in_tok = sum(int(((actors[r].get("usage") or {}).get("input_tokens") or 0)) for r in (ra, rb))
    tot_out_tok = sum(int(((actors[r].get("usage") or {}).get("output_tokens") or 0)) for r in (ra, rb))
    tot_gui_act = sum(int(actors[r].get("gui_action_calls", 0)) for r in (ra, rb))
    tot_gui_obs = sum(int(actors[r].get("gui_observation_calls", 0)) for r in (ra, rb))
    tot_cli = sum(int(actors[r].get("cli_calls", 0)) for r in (ra, rb))

    rep = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "track": meta["track"],
        "workspace_mode": meta["workspace_mode"],
        "mode": mode,
        "gui_driver": gui_driver,
        "model": api_cfg.get("model"),
        "effort": api_cfg.get("reasoning_effort"),
        "wall_seconds": wall_s,
        "role_wall_seconds": {r: actors[r]["wall_seconds"] for r in (ra, rb)},
        "score_a": grade_res["score_a"],
        "score_b": grade_res["score_b"],
        "mean_score": grade_res["mean_score"],
        "pass_a": grade_res["pass_a"],
        "pass_b": grade_res["pass_b"],
        "joint_pass": grade_res["joint_pass"],
        "gui_action_calls": tot_gui_act,
        "gui_observation_calls": tot_gui_obs,
        "cli_calls": tot_cli,
        "input_tokens_total": tot_in_tok,
        "output_tokens_total": tot_out_tok,
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
    ap.add_argument("--retained-only", action="store_true", help="Run only curated Top-5 RETAINED_TOP5_IDS")
    ap.add_argument("--tasks", nargs="*", default=None)
    args = ap.parse_args(argv)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    code_root = args.code_root.resolve()
    if args.tasks:
        task_list = list(args.tasks)
    elif args.retained_only:
        task_list = list(RETAINED_TOP5_IDS)
    else:
        task_list = [m["id"] for m in AW_CATALOG]

    if args.mode == "self_validate":
        res = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            fmap = {pool.submit(self_validate_aw_case, tid, out_dir, code_root): tid for tid in task_list}
            for fut in as_completed(fmap):
                tid = fmap[fut]
                try:
                    r = fut.result()
                except Exception as exc:
                    print(f"AW_SV_ERROR {tid}: {exc}", flush=True)
                    res[tid] = {"task_id": tid, "all_5_gates_valid": False, "error": str(exc)}
                    continue
                res[tid] = r
                print(
                    f"AW_VALIDATED {tid}: all_5_gates={r['all_5_gates_valid']} "
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
            pool.submit(run_aw_case, tid, args.mode, out_dir, code_root, api_cfg, args.codex_bin.resolve(), args.gui_driver): tid
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
                f"tok={rep['input_tokens_total']} flips={ct['focus_flips']} miskey={ct['misrouted_keystrokes']} "
                f"ov={ct['overlap_seconds']}s wall={rep['wall_seconds']}s",
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

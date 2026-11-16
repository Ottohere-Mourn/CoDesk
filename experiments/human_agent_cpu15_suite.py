"""CPU15 Rootless-Docker + Non-YOLO All-Tools Codex + X11 Video Runner for the 17 Human-Agent Cases (commit 684c79a)."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import hashlib
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
    DEFAULT_CODEX_BINARY,
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    codex_requirements_mount,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.long_horizon_v1 import start_lh_relay
from tasks.human_agent_v1.actors import ScriptedGUIActor
from tasks.human_agent_v1.catalog import (
    ACTIVE_16_KEYS,
    CASE_BY_KEY,
    HUMAN_AGENT_17_CATALOG,
    HumanAgentCaseSpec,
    SOURCE_BRANCH,
    SOURCE_COMMIT,
    get_case_prompts,
    get_user_actions,
)
from tasks.human_agent_v1.eventlog import EventLog
from tasks.human_agent_v1.human_schedule import timeline_metrics, wait_for_first_agent_input

DESKTOP_IMAGE = os.environ.get("PARAGUI_HA_DESKTOP_IMAGE", "paragui/astra-recording-desktop:20261113")
AGENT_IMAGE = os.environ.get("CODESK_CODEX_CONTAINER_IMAGE", "paragui/codex-sandbox:20261113")
DEFAULT_MODEL = "gpt-6.1-sol"
DEFAULT_EFFORT = "medium"
MODES = ("user-only", "agent-only", "independent", "shared", "shared-lock")
SCREEN_W, SCREEN_H = 1920, 1080
MODEL_W, MODEL_H = 1280, 720
SCALE_X, SCALE_Y = SCREEN_W / MODEL_W, SCREEN_H / MODEL_H


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_ha_codex_config_template(model_name: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> str:
    return f"""model = {json.dumps(model_name)}
model_provider = "codeskha"
model_reasoning_effort = {json.dumps(effort)}
model_catalog_json = "/session/codex-home/models-catalog.json"
model_context_window = 262144
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "disabled"
mcp_optional_startup_grace_ms = 0

[model_providers.codeskha]
name = "codeskha"
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
enabled_tools = ["screenshot", "click", "drag", "move", "type_text", "key", "scroll", "wait", "declare_infeasible"]
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
"""


def build_ha_agent_prompt(spec: HumanAgentCaseSpec, agent_task: str, max_steps: int) -> str:
    cleaned = agent_task
    for phrase in (
        "Use the visible GUI only; do not use shell or hidden evaluator state.",
        "Use only the visible GUI; do not use hidden evaluator state or CLI.",
        "Use the visible GUI only, not CLI, direct HTTP endpoints, or hidden evaluator state.",
        "Use the visible GUI only; no shell, direct HTTP, or hidden evaluator state.",
        "Use the visible GUI only; do not use CLI, hidden evaluator state, or direct HTTP endpoints.",
    ):
        cleaned = cleaned.replace(phrase, "").strip()
    return (
        "You are operating an Ubuntu/Linux desktop (1280x720 model viewport mapped to 1920x1080 X11 DISPLAY=:99) "
        "in non-YOLO workspace-write sandbox mode with all tools enabled (desktop GUI MCP, guest_bash workstation CLI, "
        "and local sandbox shell).\n"
        "Important workflow rules:\n"
        f"- Your GUI action budget is {max_steps} desktop tool calls. Every desktop action returns an updated 1280x720 screenshot.\n"
        "- The target CoDesk web application is ALREADY OPEN in the visible Chromium window on DISPLAY=:99.\n"
        "- Start with desktop.screenshot to inspect the open screen, then navigate and complete the workflow through the visible browser UI "
        "(click, type_text, key, scroll, wait) so page visits, form state, and saved confirmation are visibly verified on screen.\n"
        "- Do not inspect or modify private evaluator state.\n\n"
        f"Task ({spec.case_id}):\n{cleaned}\n\n"
        "Start with desktop.screenshot, complete the task carefully, verify the visible confirmation on screen, and reply in one concise line."
    )


OPENBOX_RC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <margins>
    <top>27</top>
    <bottom>0</bottom>
    <left>68</left>
    <right>0</right>
  </margins>
  <keyboard>
    <keybind key="A-Tab">
      <action name="NextWindow">
        <dialog>no</dialog>
        <finalactions>
          <action name="Focus"/>
          <action name="Raise"/>
          <action name="Unshade"/>
        </finalactions>
      </action>
    </keybind>
  </keyboard>
  <applications>
    <application class="*">
      <focus>yes</focus>
      <decor>no</decor>
      <maximized>true</maximized>
    </application>
    <application title="Open File">
      <focus>yes</focus>
      <decor>yes</decor>
      <maximized>false</maximized>
    </application>
  </applications>
</openbox_config>
"""


class DockerHumanAgentGuest:
    """Airgapped X11 desktop container (:99, 1920x1080) with UID-0 hidden backend + continuous ffmpeg capture."""

    def __init__(
        self,
        *,
        spec: HumanAgentCaseSpec,
        guest_id: str,
        run_id: str,
        guest_dir: Path,
        code_root: Path,
        record_video: bool = True,
    ):
        self.spec = spec
        self.guest_id = guest_id
        self.run_id = run_id
        self.guest_dir = guest_dir
        self.code_root = code_root
        self.record_video = record_video
        self.workspace = guest_dir / "workspace"
        self.container_name = f"paragui-ha-{spec.key}-{guest_id}-{secrets.token_hex(4)}"
        self.created = False
        self.recording = False
        self.capture_info: dict[str, Any] = {}
        self.runtime_info: dict[str, Any] = {}

    def _root_exec(self, argv: list[str], timeout: float = 60.0, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "exec", self.container_name, *argv],
            capture_output=True,
            timeout=timeout,
            check=check,
        )

    def exec_gui(self, command_str: str, cwd: str = "/home/gui", timeout_s: float = 90.0) -> dict[str, Any]:
        try:
            cp = subprocess.run(
                [
                    "docker", "exec", "--user", "1000:0",
                    "-w", cwd,
                    "-e", "DISPLAY=:99",
                    "-e", "HOME=/home/gui",
                    "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                    "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus",
                    "-e", "PYTHONPATH=/opt/ha_pyshim",
                    "-e", "LANG=C.UTF-8",
                    "-e", "LANGUAGE=en_GB",
                    self.container_name, "bash", "-lc", "umask 0002; " + command_str,
                ],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "stdout": cp.stdout[-12000:],
                "stderr": cp.stderr[-6000:],
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "stdout": "", "stderr": f"Timed out after {timeout_s}s"}

    def active_window_info(self) -> dict[str, str | None]:
        res = self.exec_gui(
            'wid=$(xdotool getactivewindow 2>/dev/null) || exit 0; '
            'title=$(xdotool getwindowname "$wid" 2>/dev/null || true); '
            'printf "%s\\t%s" "$wid" "$title"',
            timeout_s=15,
        )
        val = (res.get("stdout") or "").strip()
        if "\t" not in val:
            return {"id": None, "title": val or None}
        wid, title = val.split("\t", 1)
        return {"id": wid or None, "title": title or None}

    def active_window(self) -> str | None:
        return self.active_window_info()["title"]

    def screenshot(self, patience: float | None = None) -> bytes:
        deadline = time.monotonic() + float(patience or 30.0)
        while True:
            cp = subprocess.run(
                ["docker", "exec", "--user", "1000:0", "-e", "DISPLAY=:99", self.container_name, "import", "-window", "root", "png:-"],
                capture_output=True,
                timeout=20,
            )
            if cp.returncode == 0 and len(cp.stdout) > 1000:
                return cp.stdout
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Guest {self.guest_id} failed to return X11 screenshot")
            time.sleep(1.0)

    def screenshot_downscaled_b64(self) -> tuple[str, bytes]:
        from PIL import Image
        raw = self.screenshot(patience=25.0)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.size != (MODEL_W, MODEL_H):
            im = im.resize((MODEL_W, MODEL_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        png = buf.getvalue()
        return base64.b64encode(png).decode("ascii"), png

    def run_pyautogui(self, code: str) -> str:
        script = "import pyautogui, time; pyautogui.FAILSAFE = False\n" + code
        res = self.exec_gui("python3 - <<'PY'\n" + script + "\nPY", timeout_s=90.0)
        if not res["ok"]:
            raise RuntimeError(f"run_pyautogui failed ({res['returncode']}): {res['stderr'] or res['stdout']}")
        return res["stdout"]

    def _open_chromium_window(self, profile: str, url: str, expected_title: str, new_window: bool = True) -> None:
        pq = shlex.quote(profile)
        uq = shlex.quote(url)
        tq = shlex.quote(expected_title)
        logq = shlex.quote(f"{profile}-launch.log")
        nw = "--new-window" if new_window else ""
        cmd = (
            f"mkdir -p {pq}/Default; "
            f"(DISPLAY=:99 chromium --no-sandbox --test-type --lang=en-GB --no-first-run "
            f"--no-default-browser-check --disable-gpu --disable-dev-shm-usage "
            f"--password-store=basic --user-data-dir={pq} {nw} {uq} >{logq} 2>&1 &); "
            f"for i in $(seq 1 40); do "
            f"  if wmctrl -l 2>/dev/null | grep -Fqi {tq}; then exit 0; fi; "
            f"  sleep 0.5; "
            f"done; "
            f"wmctrl -lpG 2>&1 || true; tail -n 40 {logq} 2>/dev/null || true; exit 1"
        )
        res = self.exec_gui(cmd, timeout_s=45.0)
        if not res["ok"]:
            raise RuntimeError(f"Chromium failed to load {expected_title!r}: {res['stdout']} {res['stderr']}")

    def start(self) -> dict[str, Any]:
        self.guest_dir.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        os.chmod(self.workspace, 0o770)
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.container_name,
                "--network", "none", "--cpus", "4", "--memory", "6g", "--shm-size", "1g",
                "--security-opt", "no-new-privileges",
                "--label", "org.paragui.kind=ha-desktop",
                "-v", f"{self.workspace}:/workspace",
                DESKTOP_IMAGE, "sleep", "infinity",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.created = True
        init_sh = (
            "id -u gui >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash gui; "
            "mkdir -p /opt/ha_backend /opt/ha_code/tasks /opt/ha_pyshim "
            "/tmp/runtime-gui /home/gui/.config/openbox /home/gui/Downloads; "
            "chmod 700 /opt/ha_backend /opt/ha_code; "
            "chmod 755 /opt/ha_pyshim; "
            "cp /usr/lib/chromium/locales/en-US.pak /usr/lib/chromium/locales/en-GB.pak 2>/dev/null || true; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chmod -R g+rwX /home/gui /workspace"
        )
        self._root_exec(["bash", "-lc", init_sh], timeout=30)

        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/human_agent_v1"), f"{self.container_name}:/opt/ha_code/tasks/human_agent_v1"],
            check=True,
            capture_output=True,
            timeout=20,
        )
        self._root_exec(["bash", "-lc", "printf '' > /opt/ha_code/tasks/__init__.py && chmod -R 700 /opt/ha_code"], timeout=15)
        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/human_agent_v1/pyautogui_shim.py"), f"{self.container_name}:/opt/ha_pyshim/pyautogui.py"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/human_agent_v1/desktop_chrome.py"), f"{self.container_name}:/opt/ha_pyshim/desktop_chrome.py"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        self._root_exec(["chmod", "644", "/opt/ha_pyshim/pyautogui.py", "/opt/ha_pyshim/desktop_chrome.py"], timeout=10)
        subprocess.run(
            ["docker", "exec", "-i", "--user", "1000:0", self.container_name, "bash", "-lc", "cat > /home/gui/.config/openbox/rc.xml"],
            input=OPENBOX_RC_XML.encode("utf-8"),
            check=True,
            capture_output=True,
            timeout=10,
        )

        subprocess.run(
            [
                "docker", "exec", "-d", "-e", "PYTHONPATH=/opt/ha_code",
                self.container_name, "python3", "-m", "tasks.human_agent_v1.backend_daemon",
                "serve", "--case", self.spec.key,
                "--state-dir", "/opt/ha_backend/state",
                "--run-id", f"{self.run_id}-{self.guest_id}",
            ],
            check=True,
            capture_output=True,
            timeout=20,
        )
        for _ in range(40):
            chk = self._root_exec(["test", "-f", "/opt/ha_backend/state/runtime.json"], timeout=5, check=False)
            if chk.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Backend daemon failed to start for {self.spec.key}")
        raw_rt = self._root_exec(["cat", "/opt/ha_backend/state/runtime.json"], timeout=10).stdout.decode("utf-8")
        self.runtime_info = json.loads(raw_rt)

        top_label = shlex.quote(f"CoDesk Shared Desktop · {self.spec.key} ({self.guest_id})")
        boot_x11 = (
            "Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & "
            "sleep 0.8; export DISPLAY=:99; "
            "dbus-daemon --session --fork --address=unix:path=/tmp/runtime-gui/bus; "
            "openbox >/tmp/openbox.log 2>&1 & "
            f"sleep 0.6; python3 /opt/ha_pyshim/desktop_chrome.py {top_label} >/tmp/chrome_bar.log 2>&1 &"
        )
        subprocess.run(
            [
                "docker", "exec", "-d", "--user", "1000:0",
                "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                self.container_name, "bash", "-lc", boot_x11,
            ],
            check=True,
            capture_output=True,
            timeout=20,
        )
        time.sleep(1.4)
        (self.guest_dir / "desktop-before-apps.png").write_bytes(self.screenshot(patience=20))

        urls = self.runtime_info["urls"]
        profile = f"/tmp/chr-{self.spec.key}-{self.guest_id}"
        if self.spec.kind == "single_app":
            self._open_chromium_window(profile, urls["app_url"] + self.spec.initial_path, self.spec.expected_title)
        elif self.spec.kind == "po_archive":
            pref_cmd = (
                f"mkdir -p {shlex.quote(profile)}/Default /home/gui/Downloads && "
                f"python3 -c \"import json, pathlib; "
                f"pathlib.Path({(profile + '/Default/Preferences')!r}).write_text(json.dumps({{'download': {{'default_directory': '/home/gui/Downloads', 'prompt_for_download': False, 'directory_upgrade': True}}}}))\""
            )
            self.exec_gui(pref_cmd, timeout_s=15)
            self._open_chromium_window(profile, urls["app_url"] + "/portal", "Vendor Portal")
            time.sleep(0.5)
            self._open_chromium_window(profile, urls["app_url"] + "/agent", "Procurement Review Queue")
            self.exec_gui("wid=$(wmctrl -l | grep -Fi 'Procurement Review Queue' | tail -n1 | awk '{print $1}'); [ -z \"$wid\" ] || wmctrl -ia \"$wid\"", timeout_s=10)
        elif self.spec.kind in {"triage", "ticket"}:
            pw = self._root_exec(["cat", "/opt/ha_backend/state/login_secret.txt"], timeout=10).stdout.decode("utf-8").strip()
            self._open_chromium_window(profile, urls["handoff_url"] + "/", "Shift Handoff")
            time.sleep(0.5)
            self._open_chromium_window(profile, urls["ttr_url"] + "/login?actor=S", "Sign in")
            time.sleep(0.6)
            self.run_pyautogui(
                f"time.sleep(0.3); pyautogui.write({pw!r}, interval=0.01); pyautogui.press('tab'); pyautogui.press('enter'); time.sleep(1.6); pyautogui.press('esc')"
            )
            self._root_exec(["rm", "-f", "/opt/ha_backend/state/login_secret.txt"], timeout=5, check=False)
            self.exec_gui("wid=$(wmctrl -l | grep -Fi 'Case queue' | tail -n1 | awk '{print $1}'); [ -z \"$wid\" ] || wmctrl -ia \"$wid\"", timeout_s=10)

        time.sleep(0.6)
        setup_png = self.screenshot(patience=20)
        (self.guest_dir / "setup.png").write_bytes(setup_png)

        if self.record_video:
            rec_cmd = (
                "date +%s.%N > /tmp/rollout-start.txt; echo $$ > /tmp/rollout-ffmpeg.pid; "
                "exec ffmpeg -hide_banner -loglevel warning -nostdin -y "
                "-f x11grab -video_size 1920x1080 -framerate 10 -draw_mouse 1 -i :99.0 "
                "-vf scale=1280:720 "
                "-c:v libx264 -threads 2 -preset veryfast -crf 22 -pix_fmt yuv420p "
                "-t 1800 /tmp/rollout.mkv > /tmp/rollout-ffmpeg.log 2>&1"
            )
            subprocess.run(["docker", "exec", "-d", self.container_name, "bash", "-lc", rec_cmd], check=True, capture_output=True, timeout=20)
            time.sleep(0.8)
            self._root_exec(["bash", "-lc", "kill -0 $(cat /tmp/rollout-ffmpeg.pid)"], timeout=10)
            self.recording = True
            self.capture_info = {
                "kind": "real-x11-human-agent-desktop-recording",
                "case_key": self.spec.key,
                "case_id": self.spec.case_id,
                "guest_id": self.guest_id,
                "capture_start_unix": float(self._root_exec(["cat", "/tmp/rollout-start.txt"], timeout=10).stdout.decode().strip()),
                "x11_resolution": [1920, 1080],
                "encoded_resolution": [1280, 720],
                "fps": 10,
                "desktop_image": DESKTOP_IMAGE,
                "agent_image": AGENT_IMAGE,
                "sandbox_mode": "workspace-write",
                "yolo_enabled": False,
            }
            write_json(self.guest_dir / "recording.json", self.capture_info)

        windows = self.exec_gui("wmctrl -lpG 2>/dev/null || true", timeout_s=10)["stdout"]
        return {
            "guest_id": self.guest_id,
            "container_name": self.container_name,
            "urls": urls,
            "manifests": self.runtime_info["manifests"],
            "active_window": self.active_window(),
            "window_inventory": windows,
            "setup_screenshot_bytes": len(setup_png),
        }

    def evaluate_and_stop(self, mp4_dest: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        eval_res: dict[str, Any] = {}
        try:
            if self.created:
                try:
                    (self.guest_dir / "final.png").write_bytes(self.screenshot(patience=15))
                except Exception:
                    pass
                if self.recording:
                    self._root_exec(["bash", "-lc", "kill -INT $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null || true"], timeout=15, check=False)
                    for _ in range(50):
                        pr = self._root_exec(["bash", "-lc", "kill -0 $(cat /tmp/rollout-ffmpeg.pid) 2>/dev/null"], timeout=10, check=False)
                        if pr.returncode != 0:
                            break
                        time.sleep(0.2)
                    self.recording = False
                    self._root_exec(
                        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "/tmp/rollout.mkv", "-c", "copy", "-movflags", "+faststart", "/tmp/desktop-rollout.mp4"],
                        timeout=60,
                    )
                    mp4_dest.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["docker", "cp", f"{self.container_name}:/tmp/desktop-rollout.mp4", str(mp4_dest)], check=True, capture_output=True, timeout=60)
                    subprocess.run(["docker", "cp", f"{self.container_name}:/tmp/rollout-ffmpeg.log", str(self.guest_dir / "recording-ffmpeg.log")], capture_output=True, timeout=30)
                    probe_raw = self._root_exec(
                        [
                            "ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_frames:format=duration",
                            "-of", "json", "/tmp/desktop-rollout.mp4",
                        ],
                        timeout=20,
                    ).stdout.decode("utf-8")
                    probe = json.loads(probe_raw)
                    self.capture_info.update(
                        capture_end_unix=time.time(),
                        video_path=str(mp4_dest),
                        bytes=mp4_dest.stat().st_size,
                        sha256=sha256_bytes(mp4_dest.read_bytes()),
                        media=probe,
                    )
                    write_json(self.guest_dir / "recording.json", self.capture_info)

                has_rt = self._root_exec(["test", "-f", "/opt/ha_backend/state/runtime.json"], timeout=5, check=False)
                if has_rt.returncode == 0:
                    ev_cp = self._root_exec(
                        ["env", "PYTHONPATH=/opt/ha_code", "python3", "-m", "tasks.human_agent_v1.backend_daemon", "evaluate", "--state-dir", "/opt/ha_backend/state"],
                        timeout=30,
                    )
                    eval_res = json.loads(ev_cp.stdout.decode("utf-8"))
                    backend_archive = self.guest_dir / "backend_state"
                    backend_archive.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["docker", "cp", f"{self.container_name}:/opt/ha_backend/state/.", str(backend_archive)], capture_output=True, timeout=30)
        finally:
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
                self.created = False
        return eval_res, self.capture_info


def make_ha_mcp_handlers(
    *,
    guest: DockerHumanAgentGuest,
    event_log: EventLog,
    action_log: Path,
    shots_dir: Path,
    max_steps: int,
    lock_path: Path | None,
) -> dict[str, Any]:
    state = {"calls": 0, "infeasible": False}
    state_lock = threading.Lock()
    shots_dir.mkdir(parents=True, exist_ok=True)

    desktop_schemas = [
        {"name": "screenshot", "description": "Take a 1280x720 screenshot of the desktop.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {
            "name": "click",
            "description": "Move the mouse to (x, y) on the 1280x720 viewport and click.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "button": {"type": "string", "default": "left"},
                    "clicks": {"type": "integer", "default": 1},
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
        {
            "name": "drag",
            "description": "Drag from (x1, y1) to (x2, y2) on the 1280x720 viewport.",
            "inputSchema": {
                "type": "object",
                "properties": {"x1": {"type": "number"}, "y1": {"type": "number"}, "x2": {"type": "number"}, "y2": {"type": "number"}},
                "required": ["x1", "y1", "x2", "y2"],
                "additionalProperties": False,
            },
        },
        {
            "name": "move",
            "description": "Move the mouse pointer to (x, y) on the 1280x720 viewport.",
            "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"], "additionalProperties": False},
        },
        {
            "name": "type_text",
            "description": "Type text at the current keyboard focus.",
            "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False},
        },
        {
            "name": "key",
            "description": "Press a key or chord, e.g. 'Return', 'Tab', 'ctrl+a', 'alt+Left'. Multiple chords separated by spaces.",
            "inputSchema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"], "additionalProperties": False},
        },
        {
            "name": "scroll",
            "description": "Scroll at (x, y). direction: up|down|left|right; amount: wheel notches.",
            "inputSchema": {
                "type": "object",
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "direction": {"type": "string", "default": "down"}, "amount": {"type": "integer", "default": 3}},
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
        {
            "name": "wait",
            "description": "Wait seconds (max 20) and return a fresh screenshot.",
            "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 2.0}}, "additionalProperties": False},
        },
        {
            "name": "declare_infeasible",
            "description": "Declare that the task is impossible as specified.",
            "inputSchema": {"type": "object", "properties": {"reason": {"type": "string", "default": ""}}, "additionalProperties": False},
        },
    ]

    def _xy(x: float, y: float) -> tuple[int, int]:
        return int(round(float(x) * SCALE_X)), int(round(float(y) * SCALE_Y))

    def call_desktop(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with state_lock:
            state["calls"] += 1
            step_n = state["calls"]
        if name == "declare_infeasible":
            state["infeasible"] = True
            row = {"timestamp": time.time(), "step": step_n, "tool": f"desktop.{name}", "args": arguments, "status": "infeasible"}
            with action_log.open("a", encoding="utf-8") as h:
                h.write(json.dumps(row, ensure_ascii=False) + "\n")
            return {"content": [{"type": "text", "text": "Declared infeasible."}], "isError": False}
        if step_n > max_steps:
            row = {"timestamp": time.time(), "step": step_n, "tool": f"desktop.{name}", "args": arguments, "status": "out_of_budget"}
            with action_log.open("a", encoding="utf-8") as h:
                h.write(json.dumps(row, ensure_ascii=False) + "\n")
            return {"content": [{"type": "text", "text": f"Action budget used up ({max_steps} calls). Stop now and reply concisely."}], "isError": True}

        req_mono = time.monotonic()
        fd = None
        lock_wait = 0.0
        if lock_path is not None:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            lock_wait = time.monotonic() - req_mono
            event_log.emit("agent", "action_lock", guest_id=guest.guest_id, tool=name, lock_wait_s=round(lock_wait, 6))

        start_wall, start_mono = time.time(), time.monotonic()
        before = guest.active_window()
        err_msg = None
        code_ran = None
        try:
            if name == "click":
                X, Y = _xy(arguments["x"], arguments["y"])
                clicks = max(1, int(arguments.get("clicks", 1)))
                btn = str(arguments.get("button", "left"))
                code_ran = f"pyautogui.click({X}, {Y}, clicks={clicks}, interval=0.08, button={btn!r})"
                guest.run_pyautogui(code_ran)
            elif name == "drag":
                X1, Y1 = _xy(arguments["x1"], arguments["y1"])
                X2, Y2 = _xy(arguments["x2"], arguments["y2"])
                code_ran = f"pyautogui.moveTo({X1}, {Y1}); pyautogui.dragTo({X2}, {Y2}, duration=0.5, button='left')"
                guest.run_pyautogui(code_ran)
            elif name == "move":
                X, Y = _xy(arguments["x"], arguments["y"])
                code_ran = f"pyautogui.moveTo({X}, {Y})"
                guest.run_pyautogui(code_ran)
            elif name == "type_text":
                code_ran = f"pyautogui.write({str(arguments['text'])!r}, interval=0.02)"
                guest.run_pyautogui(code_ran)
            elif name == "key":
                chords = [
                    "pyautogui.hotkey(*" + repr([p.strip() for p in ch.split("+") if p.strip()]) + "); time.sleep(0.06)"
                    for ch in str(arguments["keys"]).split()
                ]
                code_ran = "; ".join(chords)
                if code_ran:
                    guest.run_pyautogui(code_ran)
            elif name == "scroll":
                X, Y = _xy(arguments["x"], arguments["y"])
                amt = int(arguments.get("amount", 3))
                direction = str(arguments.get("direction", "down"))
                fn = {
                    "up": f"pyautogui.scroll({amt})",
                    "down": f"pyautogui.scroll({-amt})",
                    "left": f"pyautogui.hscroll({-amt})",
                    "right": f"pyautogui.hscroll({amt})",
                }.get(direction, f"pyautogui.scroll({-amt})")
                code_ran = f"pyautogui.moveTo({X}, {Y}); {fn}"
                guest.run_pyautogui(code_ran)
            elif name == "wait":
                time.sleep(min(20.0, max(0.2, float(arguments.get("seconds", 2.0)))))
            elif name == "screenshot":
                pass
            else:
                raise ValueError(f"Unknown desktop tool {name!r}")
            time.sleep(0.45)
            b64_png, png_bytes = guest.screenshot_downscaled_b64()
            shot_file = shots_dir / f"agent-{step_n:03d}-{name}.png"
            shot_file.write_bytes(png_bytes)
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}"[:500]
            b64_png, shot_file = "", None
        after = guest.active_window()
        end_wall, end_mono = time.time(), time.monotonic()
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

        event_log.emit(
            "agent",
            "agent_gui_action",
            episode_id="agent",
            guest_id=guest.guest_id,
            step=step_n,
            tool=name,
            args=arguments,
            code=code_ran,
            start_wall=start_wall,
            start_monotonic=start_mono,
            end_wall=end_wall,
            end_monotonic=end_mono,
            duration_s=round(end_mono - start_mono, 6),
            lock_wait_s=round(lock_wait, 6),
            window_before=before,
            window_after=after,
            screenshot_path=str(shot_file) if shot_file else None,
            status="error" if err_msg else "ok",
            error=err_msg,
        )
        with action_log.open("a", encoding="utf-8") as h:
            h.write(
                json.dumps(
                    {
                        "timestamp": end_wall,
                        "step": step_n,
                        "tool": f"desktop.{name}",
                        "args": arguments,
                        "window_before": before,
                        "window_after": after,
                        "status": "error" if err_msg else "ok",
                        "error": err_msg,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        if err_msg:
            return {"content": [{"type": "text", "text": f"Error: {err_msg}"}], "isError": True}
        return {
            "content": [
                {"type": "text", "text": f"OK (step {step_n}/{max_steps}, active window: {after or 'unknown'})."},
                {"type": "image", "data": b64_png, "mimeType": "image/png"},
            ],
            "isError": False,
        }

    bash_schema = {
        "name": "guest_bash",
        "description": "Run bash commands as unprivileged desktop user on /workspace inside the desktop container.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "default": "/workspace"},
                "timeout": {"type": "number", "default": 60},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    }

    def call_bash(_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        start_wall, start_mono = time.time(), time.monotonic()
        t_lim = float(min(120.0, max(5.0, float(arguments.get("timeout", 60.0)))))
        cwd_val = str(arguments.get("cwd") or "/workspace")
        res = guest.exec_gui(str(arguments["command"]), cwd=cwd_val, timeout_s=t_lim)
        end_wall, end_mono = time.time(), time.monotonic()
        event_log.emit(
            "agent",
            "agent_cli_action",
            episode_id="agent",
            guest_id=guest.guest_id,
            command=str(arguments["command"])[:400],
            start_wall=start_wall,
            start_monotonic=start_mono,
            end_wall=end_wall,
            end_monotonic=end_mono,
            duration_s=round(end_mono - start_mono, 6),
            returncode=res["returncode"],
        )
        with action_log.open("a", encoding="utf-8") as h:
            h.write(
                json.dumps(
                    {"timestamp": end_wall, "tool": "guest_bash.guest_bash", "args": arguments, "returncode": res["returncode"]},
                    ensure_ascii=False,
                )
                + "\n"
            )
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
    }


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


def run_containerized_codex_agent(
    *,
    spec: HumanAgentCaseSpec,
    guest: DockerHumanAgentGuest,
    actor_dir: Path,
    prompt_text: str,
    event_log: EventLog,
    shots_dir: Path,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    model_name: str,
    effort: str,
    max_steps: int,
    timeout_s: int,
    lock_path: Path | None,
) -> dict[str, Any]:
    session_dir = actor_dir / "container_session"
    ticket_dir = actor_dir / "ticket"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    ticket_dir.mkdir(parents=True, exist_ok=True)
    (ticket_dir / "task.md").write_text(prompt_text, encoding="utf-8")

    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")

    catalog_payload = {
        "models": [
            {
                "slug": model_name,
                "display_name": model_name,
                "description": "All-tools non-YOLO sandboxed desktop workflow agent.",
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
                "base_instructions": "You are a careful desktop workflow agent operating an open web application via desktop tools in a shared workstation.",
            }
        ]
    }
    write_json(session_dir / "codex-home/models-catalog.json", catalog_payload)
    tmpl = build_ha_codex_config_template(model_name, effort)
    validate_container_config_text(tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(tmpl, encoding="utf-8")
    (session_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")

    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o770 if item.is_dir() else 0o660)
        except OSError:
            pass

    up_override = api_cfg.get("upstream_model_sol") if "sol" in model_name else api_cfg.get("upstream_model")
    if not up_override and api_cfg.get("upstream_model") and model_name in str(api_cfg.get("upstream_model")):
        up_override = api_cfg.get("upstream_model")
    relay_srv, relay_port = start_lh_relay(
        api_cfg["base_url"],
        api_cfg["api_key"],
        actor_dir / "relay_events.jsonl",
        model_name=model_name,
        upstream_model=up_override,
    )
    action_log = actor_dir / "actions.jsonl"
    action_log.touch()
    handlers = make_ha_mcp_handlers(
        guest=guest,
        event_log=event_log,
        action_log=action_log,
        shots_dir=shots_dir,
        max_steps=max_steps,
        lock_path=lock_path,
    )
    bridge = HostActorBridge(None, relay_port, handlers, image_history_keep=4, max_request_images=28)
    bridge.start()

    cname = f"paragui-ha-codex-{spec.key}-{secrets.token_hex(4)}"
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
        "--label", "org.paragui.kind=ha-codex-actor",
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
        AGENT_IMAGE,
        "python3", "/bridge/container_entry.py",
    ]
    t_start = time.time()
    cid = None
    timed_out = False
    event_log.emit("agent", "actor_started", guest_id=guest.guest_id, model=model_name, effort=effort)
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
        subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-v", f"{session_dir}:/session", AGENT_IMAGE, "chmod", "-R", "ug+rwX", "/session"],
            capture_output=True,
            timeout=20,
        )
        audit = verify_container_permission_audit(session_dir, expected_model=model_name, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        acts = [json.loads(ln) for ln in action_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        gui_calls = sum(1 for a in acts if a["tool"].startswith("desktop."))
        cli_calls = sum(1 for a in acts if a["tool"].startswith("guest_bash."))
        usage = _parse_codex_usage(actor_dir / "stdout.log")
        status = "timeout" if timed_out else ("done" if proc.returncode == 0 else "error")
        event_log.emit("agent", "actor_finished", guest_id=guest.guest_id, status=status, gui_calls=gui_calls, cli_calls=cli_calls)
        return {
            "status": status,
            "exit_code": proc.returncode,
            "wall_seconds": round(t_end - t_start, 2),
            "gui_mcp_calls": gui_calls,
            "cli_mcp_calls": cli_calls,
            "token_usage": usage,
            "permission_audit_ok": True,
            "permission_mode": "container-unrestricted",
            "sandbox_mode": "workspace-write",
            "approval_policy": "never",
            "yolo_enabled": False,
            "vm_host_codex_launched": False,
        }
    finally:
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20)
        bridge.close()
        relay_srv.shutdown()
        relay_srv.server_close()


def run_case_condition(
    *,
    case_key: str,
    mode: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict[str, Any] | None,
    codex_bin: Path | None,
    model_name: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    budget_override: int | None = None,
    timeout_override: int | None = None,
    record_video: bool = True,
    user_start_trigger: str = "simultaneous",
) -> dict[str, Any]:
    if case_key not in CASE_BY_KEY:
        raise ValueError(f"Unknown case {case_key!r}")
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}")
    spec = CASE_BY_KEY[case_key]
    out_dir = out_dir.resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty run dir: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"{spec.case_id}-{mode}-{time.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}"
    started_mono = time.monotonic()
    event_log = EventLog(out_dir / "events.jsonl", run_id=run_id, started_mono=started_mono)
    needs_user = mode in {"user-only", "independent", "shared", "shared-lock"}
    needs_agent = mode in {"agent-only", "independent", "shared", "shared-lock"}
    if needs_agent and (api_cfg is None or codex_bin is None):
        raise ValueError(f"Mode {mode!r} requires --api-json and --codex-bin")

    gids = ["guest-user", "guest-agent"] if mode == "independent" else ["guest-shared"]
    guests: dict[str, DockerHumanAgentGuest] = {}
    setups: dict[str, dict[str, Any]] = {}
    evals: dict[str, dict[str, Any]] = {}
    recordings: dict[str, dict[str, Any]] = {}
    lock_path = (out_dir / "locks/shared-action.lock") if mode == "shared-lock" else None
    max_steps = int(budget_override or spec.agent_budget)
    timeout_s = int(timeout_override or spec.agent_timeout_s)

    event_log.emit(
        "orchestrator",
        "run_started",
        case_key=case_key,
        case_id=spec.case_id,
        case_version=spec.version,
        mode=mode,
        source_branch=SOURCE_BRANCH,
        source_commit=SOURCE_COMMIT,
        user_start_trigger=user_start_trigger,
    )
    user_summary = None
    agent_summary = None
    error_text = None
    try:
        for gid in gids:
            g = DockerHumanAgentGuest(
                spec=spec,
                guest_id=gid,
                run_id=run_id,
                guest_dir=out_dir / "guests" / gid,
                code_root=code_root,
                record_video=record_video,
            )
            guests[gid] = g
            setups[gid] = g.start()

        user_gid = "guest-user" if mode == "independent" else "guest-shared"
        agent_gid = "guest-agent" if mode == "independent" else "guest-shared"
        user_actions = get_user_actions(spec)

        def _do_user() -> dict[str, Any]:
            if needs_agent and user_start_trigger == "first-agent-input":
                wait_for_first_agent_input(out_dir / "events.jsonl", event_log, timeout_s=180.0)
            actor = ScriptedGUIActor(
                actor_id="user",
                guest=guests[user_gid],
                actions=user_actions,
                event_log=event_log,
                out=out_dir,
                guest_id=user_gid,
                lock_path=lock_path,
            )
            return actor.run()

        def _do_agent() -> dict[str, Any]:
            agent_task, _user_task = get_case_prompts(spec, setups[agent_gid]["urls"])
            prompt = build_ha_agent_prompt(spec, agent_task, max_steps=max_steps)
            return run_containerized_codex_agent(
                spec=spec,
                guest=guests[agent_gid],
                actor_dir=out_dir / "agent",
                prompt_text=prompt,
                event_log=event_log,
                shots_dir=out_dir / "shots",
                api_cfg=api_cfg or {},
                codex_bin=codex_bin or DEFAULT_CODEX_BINARY,
                model_name=model_name,
                effort=effort,
                max_steps=max_steps,
                timeout_s=timeout_s,
                lock_path=lock_path,
            )

        if needs_user and needs_agent:
            with ThreadPoolExecutor(max_workers=2) as pool:
                fu_agent = pool.submit(_do_agent)
                fu_user = pool.submit(_do_user)
                user_summary = fu_user.result()
                agent_summary = fu_agent.result()
        elif needs_user:
            user_summary = _do_user()
        elif needs_agent:
            agent_summary = _do_agent()
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
    finally:
        for gid, g in guests.items():
            mp4_name = "desktop-rollout.mp4" if len(gids) == 1 else f"{gid}-rollout.mp4"
            try:
                ev, rec = g.evaluate_and_stop(out_dir / mp4_name)
                evals[gid] = ev
                recordings[gid] = rec
            except Exception as stop_exc:
                if not error_text:
                    error_text = f"Stop/Eval {gid}: {type(stop_exc).__name__}: {stop_exc}"

    rows = (
        [json.loads(ln) for ln in (out_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        if (out_dir / "events.jsonl").is_file()
        else []
    )
    timeline = timeline_metrics(rows)

    user_eval = (evals.get("guest-user" if mode == "independent" else "guest-shared") or {}).get("user") if needs_user else None
    agent_eval = (evals.get("guest-agent" if mode == "independent" else "guest-shared") or {}).get("agent") if needs_agent else None
    user_pass = bool(user_eval and user_eval.get("success")) if needs_user else None
    agent_pass = bool(agent_eval and agent_eval.get("success")) if needs_agent else None
    if needs_user and needs_agent:
        joint_pass = bool(user_pass and agent_pass)
    elif needs_user:
        joint_pass = bool(user_pass)
    else:
        joint_pass = bool(agent_pass)

    result = {
        "case_key": case_key,
        "case_id": spec.case_id,
        "case_version": spec.version,
        "family": spec.family,
        "title": spec.title,
        "source_branch": SOURCE_BRANCH,
        "source_commit": SOURCE_COMMIT,
        "run_id": run_id,
        "mode": mode,
        "status": "error" if error_text else "complete",
        "error": error_text,
        "experiment_valid": error_text is None
        and (not needs_agent or bool(agent_summary and agent_summary.get("gui_mcp_calls", 0) > 0 and agent_summary.get("permission_audit_ok"))),
        "outcomes": {
            "user_pass": user_pass,
            "agent_pass": agent_pass,
            "joint_pass": joint_pass,
        },
        "oracle": {
            "user": user_eval,
            "agent": agent_eval,
        },
        "actors": {
            "user": user_summary,
            "agent": agent_summary,
        },
        "permission_policy": {
            "mode": "container-unrestricted" if needs_agent else "no-model",
            "sandbox_mode": "workspace-write" if needs_agent else None,
            "approval_policy": "never" if needs_agent else None,
            "all_tools_enabled": True if needs_agent else None,
            "yolo_enabled": False,
            "vm_host_codex_launched": False,
        },
        "timeline": timeline,
        "recordings": recordings,
        "setups": setups,
        "elapsed_s": round(time.monotonic() - started_mono, 2),
    }
    write_json(out_dir / "run.json", result)
    return result


def run_preflight(out_dir: Path, code_root: Path, api_cfg: dict[str, Any], codex_bin: Path, model_name: str, effort: str) -> dict[str, Any]:
    dest = out_dir / "preflight"
    spec = CASE_BY_KEY["lab-qc"]
    guest = DockerHumanAgentGuest(
        spec=spec,
        guest_id="guest-preflight",
        run_id="preflight",
        guest_dir=dest / "guest",
        code_root=code_root,
        record_video=True,
    )
    event_log = EventLog(dest / "events.jsonl", run_id="preflight", started_mono=time.monotonic())
    try:
        guest.start()
        prompt = (
            "Infrastructure preflight check (not a grading run):\n"
            "1. Call desktop.screenshot once to verify GUI vision.\n"
            "2. Call guest_bash to run 'printf GUEST_CLI_OK' and verify workstation CLI.\n"
            "3. Use your built-in local shell tool to write '/session/work/local_shell_probe.txt' containing 'LOCAL_SHELL_OK'.\n"
            "Do not submit any form. Reply with PREFLIGHT_OK."
        )
        actor = run_containerized_codex_agent(
            spec=spec,
            guest=guest,
            actor_dir=dest / "agent",
            prompt_text=prompt,
            event_log=event_log,
            shots_dir=dest / "shots",
            api_cfg=api_cfg,
            codex_bin=codex_bin,
            model_name=model_name,
            effort=effort,
            max_steps=10,
            timeout_s=240,
            lock_path=None,
        )
        acts = [json.loads(ln) for ln in (dest / "agent/actions.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert actor["status"] == "done" and actor["permission_audit_ok"], f"Preflight actor failed: {actor}"
        assert any(a["tool"] == "desktop.screenshot" for a in acts), "desktop.screenshot was not called"
        assert any(a["tool"] == "guest_bash.guest_bash" for a in acts), "guest_bash was not called"
        probe_txt = (dest / "agent/container_session/work/local_shell_probe.txt").read_text(encoding="utf-8").strip()
        assert probe_txt == "LOCAL_SHELL_OK", f"Unexpected local shell probe: {probe_txt!r}"
    finally:
        _ev, rec = guest.evaluate_and_stop(dest / "desktop-rollout.mp4")
    summary = {"passed": True, "actor": actor, "recording": rec}
    write_json(dest / "preflight-result.json", summary)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="*", default=list(ACTIVE_16_KEYS))
    ap.add_argument("--modes", nargs="*", default=["shared"])
    ap.add_argument("--api-json", type=Path, default=None)
    ap.add_argument("--codex-bin", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--user-start-trigger", default="simultaneous", choices=["simultaneous", "first-agent-input"])
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()

    code_root = args.code_root.resolve()
    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8")) if args.api_json else None
    codex_bin = args.codex_bin.resolve() if args.codex_bin else None

    if args.preflight or args.preflight_only:
        if api_cfg is None or codex_bin is None:
            raise ValueError("--preflight requires --api-json and --codex-bin")
        pf = run_preflight(out_root, code_root, api_cfg, codex_bin, args.model, args.effort)
        print("PREFLIGHT_PASS", json.dumps({"wall_s": pf["actor"]["wall_seconds"], "mp4_bytes": pf["recording"].get("bytes")}), flush=True)
        if args.preflight_only:
            return 0

    case_keys = list(args.cases)
    if case_keys == ["all17"]:
        case_keys = [c.key for c in HUMAN_AGENT_17_CATALOG]
    elif case_keys == ["active16"]:
        case_keys = list(ACTIVE_16_KEYS)

    jobs = [(ck, m) for ck in case_keys for m in args.modes]
    suite_status: dict[str, Any] = {"jobs": {}, "source_branch": SOURCE_BRANCH, "source_commit": SOURCE_COMMIT}
    lock = threading.Lock()

    def _job(ck: str, m: str) -> dict[str, Any]:
        print(f"START {ck} [{m}]", flush=True)
        res = run_case_condition(
            case_key=ck,
            mode=m,
            out_dir=out_root / ck / m,
            code_root=code_root,
            api_cfg=api_cfg,
            codex_bin=codex_bin,
            model_name=args.model,
            effort=args.effort,
            record_video=not args.no_video,
            user_start_trigger=args.user_start_trigger,
        )
        with lock:
            suite_status["jobs"][f"{ck}/{m}"] = {
                "status": res["status"],
                "experiment_valid": res["experiment_valid"],
                "outcomes": res["outcomes"],
                "elapsed_s": res["elapsed_s"],
                "error": res["error"],
            }
            write_json(out_root / "suite-status.json", suite_status)
        print(f"DONE {ck} [{m}] -> {res['outcomes']} ({res['elapsed_s']}s) err={res['error']}", flush=True)
        return res

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [pool.submit(_job, ck, m) for ck, m in jobs]
        for f in as_completed(futs):
            f.result()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

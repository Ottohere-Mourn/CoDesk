"""CPU15 Rootless-Docker Real-Web + Real-Software 2-Space (macOS-style) Human-Agent Runner (Non-YOLO All-Tools Codex)."""
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
    DEFAULT_CODEX_BINARY,
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    codex_requirements_mount,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.human_agent_cpu15_suite import (
    AGENT_IMAGE,
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    DESKTOP_IMAGE,
    MODEL_H,
    MODEL_W,
    SCALE_X,
    SCALE_Y,
    _parse_codex_usage,
    build_ha_codex_config_template,
    sha256_bytes,
    write_json,
)
from experiments.long_horizon_v1 import start_lh_relay
from tasks.human_agent_v1.actors import GUIAction
from tasks.human_agent_v1.eventlog import EventLog
from tasks.human_agent_v1.human_schedule import timeline_metrics
from tasks.real_macos_ha_v1.catalog import (
    REAL_CASE_BY_KEY,
    REAL_MACOS_5_CATALOG,
    RealMacOSCaseSpec,
    evaluate_workspace,
    get_real_user_actions,
)

MODES = ("user-only", "agent-only", "independent", "shared")

MACOS_OPENBOX_RC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <desktops>
    <number>2</number>
    <firstdesk>1</firstdesk>
    <names>
      <name>Space 1</name>
      <name>Space 2</name>
    </names>
    <popupTime>400</popupTime>
  </desktops>
  <margins>
    <top>30</top>
    <bottom>60</bottom>
    <left>0</left>
    <right>0</right>
  </margins>
  <keyboard>
    <keybind key="C-Right">
      <action name="GoToDesktop"><to>right</to><wrap>no</wrap></action>
    </keybind>
    <keybind key="C-Left">
      <action name="GoToDesktop"><to>left</to><wrap>no</wrap></action>
    </keybind>
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
      <decor>yes</decor>
      <maximized>no</maximized>
    </application>
  </applications>
</openbox_config>
"""


def build_real_macos_agent_prompt(spec: RealMacOSCaseSpec) -> str:
    return (
        "You are operating a live internet-connected workstation (1280x720 model viewport mapped to 1920x1080 X11 DISPLAY=:99, "
        "shared workspace '/workspace') in non-YOLO workspace-write sandbox mode with ALL tools enabled "
        "(desktop GUI MCP, guest_bash workstation CLI, and local sandbox shell).\n"
        "Desktop layout (macOS-style 2-Space environment):\n"
        "- Top Menu Bar (y=10 in 1280x720 viewport) has clickable Space switcher pills: "
        "'Space 1: Reading' at (755, 10) and 'Space 2: Agent Desk' at (878, 10). You can also switch Spaces with key('ctrl+Right') / key('ctrl+Left') or the bottom Dock.\n"
        "- Your assigned browser window (open on the real external target website) and desktop application "
        "(LibreOffice Calc / LibreOffice Writer / Inkscape) are already open on **Space 2 ('Space 2: Agent Desk')**.\n"
        "Workflow instructions:\n"
        "1. Start with desktop.screenshot to inspect the current desktop.\n"
        "2. Switch to **Space 2** via desktop.click(x=878, y=10) (or desktop.key(keys='ctrl+Right')) so Space 2 is visible on screen, "
        "and visually inspect your live webpage and open desktop application on Space 2 using desktop GUI calls.\n"
        "3. You may freely combine GUI actions on Space 2 and guest_bash CLI commands on '/workspace/agent_work' (for LibreOffice, Inkscape, curl, or Python ODF helpers) "
        "to verify exact facts and ensure your final output file is cleanly saved (note: if you regenerate an .ods/.odt file from guest_bash, either reopen it with "
        "'-env:UserInstallation=file:///tmp/lo-space2' or avoid pressing ctrl+s in an older in-memory LibreOffice window), then take a final desktop.screenshot on Space 2.\n"
        "4. Never touch '/workspace/user_docs'.\n\n"
        f"Task ({spec.key}):\n{spec.agent_task}\n\n"
        "Complete the task accurately, verify on Space 2, and reply concisely."
    )


class RealMacOSDesktopGuest:
    """Internet-enabled rootless Docker X11 desktop (:99, 1920x1080, 2 Spaces) with real websites, real apps, and ffmpeg video."""

    def __init__(
        self,
        *,
        spec: RealMacOSCaseSpec,
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
        self.container_name = f"paragui-rw-{spec.key[:12]}-{guest_id}-{secrets.token_hex(4)}"
        self.created = False
        self.recording = False
        self.capture_info: dict[str, Any] = {}

    def _root_exec(self, argv: list[str], timeout: float = 90.0, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "exec", self.container_name, *argv],
            capture_output=True,
            timeout=timeout,
            check=check,
        )

    def exec_gui(self, command_str: str, cwd: str = "/workspace", timeout_s: float = 120.0) -> dict[str, Any]:
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

    def active_space(self) -> int:
        res = self.exec_gui("wmctrl -d 2>/dev/null || true", timeout_s=10)
        for ln in (res.get("stdout") or "").splitlines():
            parts = ln.split()
            if len(parts) >= 2 and parts[1] == "*":
                try:
                    return int(parts[0])
                except ValueError:
                    return 0
        return 0

    def active_window_info(self) -> dict[str, Any]:
        res = self.exec_gui(
            "sp=$(wmctrl -d 2>/dev/null | awk '$2==\"*\"{print $1}'); "
            '[ -z "$sp" ] && sp=0; '
            'wid=$(xdotool getactivewindow 2>/dev/null || true); '
            'title=$([ -n "$wid" ] && xdotool getwindowname "$wid" 2>/dev/null || true); '
            'printf "%s\\t%s\\t%s" "$sp" "$wid" "$title"',
            timeout_s=12,
        )
        parts = (res.get("stdout") or "").split("\t")
        sp = 0
        try:
            sp = int(parts[0].strip()) if parts and parts[0].strip() else 0
        except ValueError:
            sp = 0
        wid = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        title = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        return {"space": sp, "id": wid, "title": title}

    def active_window(self) -> str | None:
        return self.active_window_info()["title"]

    def screenshot(self, patience: float = 25.0) -> bytes:
        deadline = time.monotonic() + patience
        while True:
            cp = subprocess.run(
                ["docker", "exec", "--user", "1000:0", "-e", "DISPLAY=:99", self.container_name, "import", "-window", "root", "png:-"],
                capture_output=True,
                timeout=20,
            )
            if cp.returncode == 0 and len(cp.stdout) > 1000:
                return cp.stdout
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Guest {self.guest_id} X11 screenshot timeout")
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

    def start(self) -> dict[str, Any]:
        self.guest_dir.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        os.chmod(self.workspace, 0o770)

        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.container_name,
                "--cpus", "4", "--memory", "6g", "--shm-size", "1g",
                "--security-opt", "no-new-privileges",
                "--label", "org.paragui.kind=rw-macos-desktop",
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
            "mkdir -p /opt/ha_code/tasks /opt/ha_pyshim /tmp/runtime-gui /home/gui/.config/openbox /home/gui/Downloads; "
            "chmod 700 /opt/ha_code; chmod 755 /opt/ha_pyshim; "
            "chown -R 1000:0 /tmp/runtime-gui /home/gui /workspace; "
            "chmod -R g+rwX /home/gui /workspace"
        )
        self._root_exec(["bash", "-lc", init_sh], timeout=30)

        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/human_agent_v1"), f"{self.container_name}:/opt/ha_code/tasks/human_agent_v1"],
            check=True, capture_output=True, timeout=20,
        )
        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/real_macos_ha_v1"), f"{self.container_name}:/opt/ha_code/tasks/real_macos_ha_v1"],
            check=True, capture_output=True, timeout=20,
        )
        self._root_exec(["bash", "-lc", "printf '' > /opt/ha_code/tasks/__init__.py && chmod -R 700 /opt/ha_code"], timeout=10)
        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/human_agent_v1/pyautogui_shim.py"), f"{self.container_name}:/opt/ha_pyshim/pyautogui.py"],
            check=True, capture_output=True, timeout=15,
        )
        subprocess.run(
            ["docker", "cp", str(self.code_root / "tasks/real_macos_ha_v1/macos_shell.py"), f"{self.container_name}:/opt/ha_pyshim/macos_shell.py"],
            check=True, capture_output=True, timeout=15,
        )
        self._root_exec(["chmod", "644", "/opt/ha_pyshim/pyautogui.py", "/opt/ha_pyshim/macos_shell.py"], timeout=10)
        subprocess.run(
            ["docker", "exec", "-i", "--user", "1000:0", self.container_name, "bash", "-lc", "cat > /home/gui/.config/openbox/rc.xml"],
            input=MACOS_OPENBOX_RC_XML.encode("utf-8"),
            check=True, capture_output=True, timeout=10,
        )

        seed_py = (
            f"from pathlib import Path; "
            f"from tasks.real_macos_ha_v1.catalog import REAL_CASE_BY_KEY, build_initial_workspace; "
            f"build_initial_workspace(REAL_CASE_BY_KEY[{self.spec.key!r}], Path('/workspace'))"
        )
        self._root_exec(["env", "PYTHONPATH=/opt/ha_code", "python3", "-c", seed_py], timeout=60)
        self._root_exec(["bash", "-lc", "chown -R 1000:0 /workspace && chmod -R ug+rwX /workspace"], timeout=15)

        label_q = shlex.quote(self.spec.key)
        boot_x11 = (
            "Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 & "
            "sleep 0.9; export DISPLAY=:99; "
            "dbus-daemon --session --fork --address=unix:path=/tmp/runtime-gui/bus; "
            "openbox >/tmp/openbox.log 2>&1 & "
            f"sleep 0.8; python3 /opt/ha_pyshim/macos_shell.py {label_q} >/tmp/macos_shell.log 2>&1 &"
        )
        subprocess.run(
            [
                "docker", "exec", "-d", "--user", "1000:0",
                "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                self.container_name, "bash", "-lc", boot_x11,
            ],
            check=True, capture_output=True, timeout=20,
        )
        time.sleep(1.8)

        a_url = shlex.quote(self.spec.agent_url)
        a_doc = shlex.quote("/workspace/" + self.spec.agent_doc_rel)
        if self.spec.agent_app_kind in {"calc", "writer"}:
            a_app_cmd = f"libreoffice --norestore --nologo --nofirststartwizard -env:UserInstallation=file:///tmp/lo-space2 {a_doc}"
        else:
            a_app_cmd = f"inkscape {a_doc}"
        setup_s2 = (
            "wmctrl -s 1; sleep 0.4; "
            f"(chromium --no-sandbox --test-type --no-first-run --no-default-browser-check --disable-gpu "
            f"--disable-dev-shm-usage --user-data-dir=/tmp/chr-space2 --window-position=14,36 --window-size=1120,964 "
            f"--new-window {a_url} >/tmp/chr_s2.log 2>&1 &); "
            f"({a_app_cmd} >/tmp/app_s2.log 2>&1 &); "
            "for i in $(seq 1 24); do "
            "  cnt=$(wmctrl -l | awk '$2==1{c++} END{print c+0}'); "
            "  [ \"$cnt\" -ge 2 ] && break; sleep 0.5; "
            "done; "
            "sleep 1.5; "
            "for wid in $(wmctrl -l | awk '$2==1{print $1}'); do "
            "  title=$(xdotool getwindowname \"$wid\" 2>/dev/null || true); "
            "  wmctrl -i -r \"$wid\" -b remove,maximized_vert,maximized_horz || true; "
            "  case \"$title\" in "
            "    *Chromium*) wmctrl -i -r \"$wid\" -e 0,14,36,1120,964 || true ;; "
            "    *) wmctrl -i -r \"$wid\" -e 0,1146,36,760,964 || true ;; "
            "  esac; "
            "done"
        )
        self.exec_gui(setup_s2, timeout_s=45.0)
        (self.guest_dir / "setup-space2.png").write_bytes(self.screenshot(patience=20))

        u_url = shlex.quote(self.spec.user_url)
        u_doc = shlex.quote("/workspace/" + self.spec.user_doc_rel)
        u_base = shlex.quote(Path(self.spec.user_doc_rel).name)
        a_base = shlex.quote(Path(self.spec.agent_doc_rel).name)
        setup_s1 = (
            "chr_wid=''; wmctrl -s 0; sleep 0.4; "
            f"(chromium --no-sandbox --test-type --no-first-run --no-default-browser-check --disable-gpu "
            f"--disable-dev-shm-usage --user-data-dir=/tmp/chr-space1 --window-position=14,36 --window-size=1120,964 "
            f"--new-window {u_url} >/tmp/chr_s1.log 2>&1 &); "
            f"(libreoffice --norestore --nologo --nofirststartwizard -env:UserInstallation=file:///tmp/lo-space1 {u_doc} >/tmp/app_s1.log 2>&1 &); "
            "for i in $(seq 1 28); do "
            f"  if wmctrl -l | grep -Fq {u_base} && [ \"$(wmctrl -l | grep -ci chromium)\" -ge 2 ]; then break; fi; "
            "  sleep 0.5; "
            "done; "
            "sleep 2.8; "
            "for wid in $(wmctrl -l | awk '{print $1}'); do "
            "  title=$(xdotool getwindowname \"$wid\" 2>/dev/null || true); "
            f"  case \"$title\" in *{u_base}*) wmctrl -i -r \"$wid\" -t 0 || true ;; *{a_base}*) wmctrl -i -r \"$wid\" -t 1 || true ;; esac; "
            "done; "
            "for wid in $(wmctrl -l | awk '$2==0{print $1}'); do "
            "  title=$(xdotool getwindowname \"$wid\" 2>/dev/null || true); "
            "  wmctrl -i -r \"$wid\" -b remove,maximized_vert,maximized_horz || true; "
            "  case \"$title\" in "
            "    *Chromium*) wmctrl -i -r \"$wid\" -e 0,14,36,1120,964 || true; chr_wid=\"$wid\" ;; "
            "    *LibreOffice*) wmctrl -i -r \"$wid\" -e 0,1146,36,760,964 || true ;; "
            "  esac; "
            "done; "
            "wmctrl -s 0; sleep 0.3; "
            "[ -n \"$chr_wid\" ] && wmctrl -ia \"$chr_wid\" || true"
        )
        self.exec_gui(setup_s1, timeout_s=50.0)
        time.sleep(1.0)
        setup_png = self.screenshot(patience=20)
        (self.guest_dir / "setup-space1.png").write_bytes(setup_png)

        if self.record_video:
            rec_cmd = (
                "date +%s.%N > /tmp/rollout-start.txt; echo $$ > /tmp/rollout-ffmpeg.pid; "
                "exec ffmpeg -hide_banner -loglevel warning -nostdin -y "
                "-f x11grab -video_size 1920x1080 -framerate 10 -draw_mouse 1 -i :99.0 "
                "-vf scale=1280:720 "
                "-c:v libx264 -threads 2 -preset veryfast -crf 21 -pix_fmt yuv420p "
                "-t 1800 /tmp/rollout.mkv > /tmp/rollout-ffmpeg.log 2>&1"
            )
            subprocess.run(["docker", "exec", "-d", self.container_name, "bash", "-lc", rec_cmd], check=True, capture_output=True, timeout=20)
            time.sleep(0.8)
            self._root_exec(["bash", "-lc", "kill -0 $(cat /tmp/rollout-ffmpeg.pid)"], timeout=10)
            self.recording = True
            self.capture_info = {
                "kind": "real-web-real-software-macos-2space-x11-recording",
                "case_key": self.spec.key,
                "guest_id": self.guest_id,
                "capture_start_unix": float(self._root_exec(["cat", "/tmp/rollout-start.txt"], timeout=10).stdout.decode().strip()),
                "x11_resolution": [1920, 1080],
                "encoded_resolution": [1280, 720],
                "fps": 10,
                "user_url": self.spec.user_url,
                "agent_url": self.spec.agent_url,
                "sandbox_mode": "workspace-write",
                "yolo_enabled": False,
            }
            write_json(self.guest_dir / "recording.json", self.capture_info)

        return {
            "guest_id": self.guest_id,
            "container_name": self.container_name,
            "active_space": self.active_space(),
            "active_window": self.active_window(),
            "windows": self.exec_gui("wmctrl -lpG 2>/dev/null || true", timeout_s=10)["stdout"],
        }

    def stop_and_collect(self, mp4_dest: Path) -> dict[str, Any]:
        try:
            if self.created:
                self._root_exec(["bash", "-lc", "chmod -R a+rX /workspace"], timeout=15, check=False)
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
                    probe_raw = self._root_exec(
                        [
                            "ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_frames:format=duration",
                            "-of", "json", "/tmp/desktop-rollout.mp4",
                        ],
                        timeout=20,
                    ).stdout.decode("utf-8")
                    self.capture_info.update(
                        capture_end_unix=time.time(),
                        video_path=str(mp4_dest),
                        bytes=mp4_dest.stat().st_size,
                        sha256=sha256_bytes(mp4_dest.read_bytes()),
                        media=json.loads(probe_raw),
                    )
                    write_json(self.guest_dir / "recording.json", self.capture_info)
        finally:
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
                self.created = False
        return self.capture_info


class SpaceTransitionMonitor:
    """Polls active X11 desktop Space (0 vs 1) to record exact screen-switch interruption timestamps."""

    def __init__(self, guest: RealMacOSDesktopGuest, event_log: EventLog, poll_s: float = 0.35):
        self.guest = guest
        self.event_log = event_log
        self.poll_s = poll_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.transitions = 0

    def start(self) -> None:
        def _loop() -> None:
            last_sp = 0
            while not self._stop.is_set():
                try:
                    info = self.guest.active_window_info()
                    sp = info["space"]
                    if sp != last_sp:
                        self.transitions += 1
                        self.event_log.emit(
                            "desktop_wm",
                            "space_switched",
                            guest_id=self.guest.guest_id,
                            from_space=last_sp,
                            to_space=sp,
                            active_window=info["title"],
                            transition_index=self.transitions,
                        )
                        last_sp = sp
                except Exception:
                    pass
                self._stop.wait(self.poll_s)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)


def run_space_aware_user(
    *,
    guest: RealMacOSDesktopGuest,
    actions: list[GUIAction],
    event_log: EventLog,
    shots_dir: Path,
) -> dict[str, Any]:
    shots_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    event_log.emit("user", "actor_started", guest_id=guest.guest_id)
    interrupted_space_steps = 0
    errors: list[str] = []
    for step, act in enumerate(actions, 1):
        if act.delay_before_s:
            time.sleep(act.delay_before_s)
        sw, sm = time.time(), time.monotonic()
        before = guest.active_window_info()
        err = None
        try:
            guest.run_pyautogui(act.code)
            png = guest.screenshot(patience=20.0)
            (shots_dir / f"user-{step:03d}-{act.name}.png").write_bytes(png)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"[:400]
            errors.append(err)
        after = guest.active_window_info()
        ew, em = time.time(), time.monotonic()
        wrong_space = before["space"] != 0 or after["space"] != 0
        if wrong_space:
            interrupted_space_steps += 1
        event_log.emit(
            "user",
            "gui_action",
            episode_id="user",
            guest_id=guest.guest_id,
            step=step,
            action_name=act.name,
            expected_app=act.expected_app,
            start_wall=sw,
            start_monotonic=sm,
            end_wall=ew,
            end_monotonic=em,
            duration_s=round(em - sm, 6),
            space_before=before["space"],
            space_after=after["space"],
            window_before=before["title"],
            window_after=after["title"],
            interrupted_wrong_space=wrong_space,
            error=err,
        )
    elapsed = round(time.monotonic() - started, 2)
    summary = {
        "actions": len(actions),
        "interrupted_wrong_space_steps": interrupted_space_steps,
        "elapsed_s": elapsed,
        "errors": errors,
    }
    event_log.emit("user", "actor_finished", guest_id=guest.guest_id, **summary)
    return summary


def make_real_macos_mcp_handlers(
    *,
    guest: RealMacOSDesktopGuest,
    event_log: EventLog,
    action_log: Path,
    shots_dir: Path,
    max_steps: int,
) -> dict[str, Any]:
    state = {"calls": 0}
    state_lock = threading.Lock()
    shots_dir.mkdir(parents=True, exist_ok=True)

    desktop_schemas = [
        {"name": "screenshot", "description": "Take a 1280x720 screenshot of the current active Space.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {
            "name": "click",
            "description": "Move mouse to (x, y) on 1280x720 viewport and click.",
            "inputSchema": {
                "type": "object",
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "button": {"type": "string", "default": "left"}, "clicks": {"type": "integer", "default": 1}},
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
        {
            "name": "drag",
            "description": "Drag from (x1, y1) to (x2, y2) on 1280x720 viewport.",
            "inputSchema": {
                "type": "object",
                "properties": {"x1": {"type": "number"}, "y1": {"type": "number"}, "x2": {"type": "number"}, "y2": {"type": "number"}},
                "required": ["x1", "y1", "x2", "y2"],
                "additionalProperties": False,
            },
        },
        {"name": "move", "description": "Move pointer to (x, y).", "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"], "additionalProperties": False}},
        {"name": "type_text", "description": "Type text at current focus.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}},
        {"name": "key", "description": "Press key or chord (e.g. Return, Tab, ctrl+s, ctrl+Right, ctrl+Left).", "inputSchema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"], "additionalProperties": False}},
        {
            "name": "scroll",
            "description": "Scroll at (x, y). direction: up|down|left|right.",
            "inputSchema": {
                "type": "object",
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "direction": {"type": "string", "default": "down"}, "amount": {"type": "integer", "default": 4}},
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
        {"name": "wait", "description": "Wait seconds (max 20) and return screenshot.", "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number", "default": 2.0}}, "additionalProperties": False}},
        {"name": "declare_infeasible", "description": "Declare task infeasible.", "inputSchema": {"type": "object", "properties": {"reason": {"type": "string", "default": ""}}, "additionalProperties": False}},
    ]

    def _xy(x: float, y: float) -> tuple[int, int]:
        return int(round(float(x) * SCALE_X)), int(round(float(y) * SCALE_Y))

    def call_desktop(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with state_lock:
            state["calls"] += 1
            step_n = state["calls"]
        if step_n > max_steps:
            return {"content": [{"type": "text", "text": f"GUI budget ({max_steps}) exhausted. Finish and reply concisely."}], "isError": True}
        sw, sm = time.time(), time.monotonic()
        before = guest.active_window_info()
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
                code_ran = f"pyautogui.moveTo({X1}, {Y1}); pyautogui.dragTo({X2}, {Y2}, duration=0.5)"
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
                amt = int(arguments.get("amount", 4))
                direction = str(arguments.get("direction", "down"))
                fn = f"pyautogui.scroll({amt if direction == 'up' else -amt})"
                code_ran = f"pyautogui.moveTo({X}, {Y}); {fn}"
                guest.run_pyautogui(code_ran)
            elif name == "wait":
                time.sleep(min(20.0, max(0.2, float(arguments.get("seconds", 2.0)))))
            elif name in {"screenshot", "declare_infeasible"}:
                pass
            time.sleep(0.45)
            b64_png, png_bytes = guest.screenshot_downscaled_b64()
            shot_file = shots_dir / f"agent-{step_n:03d}-{name}.png"
            shot_file.write_bytes(png_bytes)
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}"[:500]
            b64_png, shot_file = "", None
        after = guest.active_window_info()
        ew, em = time.time(), time.monotonic()
        event_log.emit(
            "agent",
            "agent_gui_action",
            episode_id="agent",
            guest_id=guest.guest_id,
            step=step_n,
            tool=name,
            args=arguments,
            code=code_ran,
            start_wall=sw,
            start_monotonic=sm,
            end_wall=ew,
            end_monotonic=em,
            duration_s=round(em - sm, 6),
            space_before=before["space"],
            space_after=after["space"],
            window_before=before["title"],
            window_after=after["title"],
            screenshot_path=str(shot_file) if shot_file else None,
            status="error" if err_msg else "ok",
            error=err_msg,
        )
        with action_log.open("a", encoding="utf-8") as h:
            h.write(
                json.dumps(
                    {
                        "timestamp": ew,
                        "step": step_n,
                        "tool": f"desktop.{name}",
                        "args": arguments,
                        "space_before": before["space"],
                        "space_after": after["space"],
                        "window_after": after["title"],
                        "status": "error" if err_msg else "ok",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        if err_msg:
            return {"content": [{"type": "text", "text": f"Error: {err_msg}"}], "isError": True}
        return {
            "content": [
                {"type": "text", "text": f"OK (step {step_n}/{max_steps}, Space {after['space'] + 1}, active window: {after['title'] or 'desktop'})."},
                {"type": "image", "data": b64_png, "mimeType": "image/png"},
            ],
            "isError": False,
        }

    bash_schema = {
        "name": "guest_bash",
        "description": "Run workstation bash/Python/LibreOffice/Inkscape/curl commands on /workspace/agent_work inside the internet-connected desktop container.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "default": "/workspace/agent_work"},
                "timeout": {"type": "number", "default": 90},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    }

    def call_bash(_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        sw, sm = time.time(), time.monotonic()
        t_lim = float(min(150.0, max(5.0, float(arguments.get("timeout", 90.0)))))
        cwd_val = str(arguments.get("cwd") or "/workspace/agent_work")
        res = guest.exec_gui(str(arguments["command"]), cwd=cwd_val, timeout_s=t_lim)
        ew, em = time.time(), time.monotonic()
        event_log.emit(
            "agent",
            "agent_cli_action",
            episode_id="agent",
            guest_id=guest.guest_id,
            command=str(arguments["command"])[:400],
            start_wall=sw,
            start_monotonic=sm,
            end_wall=ew,
            end_monotonic=em,
            duration_s=round(em - sm, 6),
            returncode=res["returncode"],
        )
        with action_log.open("a", encoding="utf-8") as h:
            h.write(
                json.dumps({"timestamp": ew, "tool": "guest_bash.guest_bash", "args": arguments, "returncode": res["returncode"]}, ensure_ascii=False) + "\n"
            )
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": not res["ok"]}

    return {
        "desktop": {"list": lambda: desktop_schemas, "call": call_desktop},
        "guest_bash": {"list": lambda: [bash_schema], "call": call_bash},
    }


def run_real_macos_codex_agent(
    *,
    spec: RealMacOSCaseSpec,
    guest: RealMacOSDesktopGuest,
    actor_dir: Path,
    event_log: EventLog,
    shots_dir: Path,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    model_name: str,
    effort: str,
) -> dict[str, Any]:
    session_dir = actor_dir / "container_session"
    ticket_dir = actor_dir / "ticket"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    ticket_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = build_real_macos_agent_prompt(spec)
    (ticket_dir / "task.md").write_text(prompt_text, encoding="utf-8")

    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")

    catalog_payload = {
        "models": [
            {
                "slug": model_name,
                "display_name": model_name,
                "description": "All-tools non-YOLO sandboxed multi-Space desktop agent.",
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
                "base_instructions": "You are a real-web and real-software desktop agent operating Space 2 with GUI and CLI tools.",
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
    relay_srv, relay_port = start_lh_relay(
        api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl",
        model_name=model_name, upstream_model=up_override,
    )
    action_log = actor_dir / "actions.jsonl"
    action_log.touch()
    handlers = make_real_macos_mcp_handlers(
        guest=guest, event_log=event_log, action_log=action_log, shots_dir=shots_dir, max_steps=spec.agent_budget,
    )
    bridge = HostActorBridge(None, relay_port, handlers, image_history_keep=4, max_request_images=28)
    bridge.start()

    cname = f"paragui-rw-codex-{spec.key[:12]}-{secrets.token_hex(4)}"
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
        "--label", "org.paragui.kind=rw-codex-actor",
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
                if time.time() - t_start > spec.agent_timeout_s:
                    timed_out = True
                    subprocess.run(["docker", "kill", cid], capture_output=True, timeout=15)
                    proc.wait(timeout=10)
                    break
                time.sleep(0.5)
        t_end = time.time()
        subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-v", f"{session_dir}:/session", AGENT_IMAGE, "chmod", "-R", "ug+rwX", "/session"],
            capture_output=True, timeout=20,
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


def run_real_case_condition(
    *,
    case_key: str,
    mode: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict[str, Any] | None,
    codex_bin: Path | None,
    model_name: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    record_video: bool = True,
) -> dict[str, Any]:
    spec = REAL_CASE_BY_KEY[case_key]
    out_dir = out_dir.resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"Non-empty output dir: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"{spec.key}-{mode}-{time.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}"
    started_mono = time.monotonic()
    event_log = EventLog(out_dir / "events.jsonl", run_id=run_id, started_mono=started_mono)
    needs_user = mode in {"user-only", "independent", "shared"}
    needs_agent = mode in {"agent-only", "independent", "shared"}
    gids = ["guest-user", "guest-agent"] if mode == "independent" else ["guest-shared"]

    guests: dict[str, RealMacOSDesktopGuest] = {}
    monitors: dict[str, SpaceTransitionMonitor] = {}
    setups: dict[str, dict[str, Any]] = {}
    recordings: dict[str, dict[str, Any]] = {}
    user_summary = None
    agent_summary = None
    error_text = None

    try:
        for gid in gids:
            g = RealMacOSDesktopGuest(
                spec=spec, guest_id=gid, run_id=run_id,
                guest_dir=out_dir / "guests" / gid, code_root=code_root, record_video=record_video,
            )
            guests[gid] = g
            setups[gid] = g.start()
            mon = SpaceTransitionMonitor(g, event_log)
            mon.start()
            monitors[gid] = mon

        u_gid = "guest-user" if mode == "independent" else "guest-shared"
        a_gid = "guest-agent" if mode == "independent" else "guest-shared"

        def _user_fn() -> dict[str, Any]:
            return run_space_aware_user(
                guest=guests[u_gid],
                actions=get_real_user_actions(spec),
                event_log=event_log,
                shots_dir=out_dir / "shots",
            )

        def _agent_fn() -> dict[str, Any]:
            return run_real_macos_codex_agent(
                spec=spec,
                guest=guests[a_gid],
                actor_dir=out_dir / "agent",
                event_log=event_log,
                shots_dir=out_dir / "shots",
                api_cfg=api_cfg or {},
                codex_bin=codex_bin or DEFAULT_CODEX_BINARY,
                model_name=model_name,
                effort=effort,
            )

        if needs_user and needs_agent:
            with ThreadPoolExecutor(max_workers=2) as pool:
                fa = pool.submit(_agent_fn)
                fu = pool.submit(_user_fn)
                user_summary = fu.result()
                agent_summary = fa.result()
        elif needs_user:
            user_summary = _user_fn()
        elif needs_agent:
            agent_summary = _agent_fn()
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
    finally:
        for mon in monitors.values():
            mon.stop()
        for gid, g in guests.items():
            mp4_name = "desktop-rollout.mp4" if len(gids) == 1 else f"{gid}-rollout.mp4"
            try:
                recordings[gid] = g.stop_and_collect(out_dir / mp4_name)
            except Exception as stop_exc:
                if not error_text:
                    error_text = f"Stop {gid}: {type(stop_exc).__name__}: {stop_exc}"

    events = (
        [json.loads(ln) for ln in (out_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        if (out_dir / "events.jsonl").is_file()
        else []
    )
    timeline = timeline_metrics(events)
    space_switches = [e for e in events if e.get("event_type") == "space_switched"]

    u_gid = "guest-user" if mode == "independent" else "guest-shared"
    a_gid = "guest-agent" if mode == "independent" else "guest-shared"
    u_events = [e for e in events if e.get("guest_id") == u_gid]
    a_events = [e for e in events if e.get("guest_id") == a_gid]

    u_eval = evaluate_workspace(spec, out_dir / "guests" / u_gid / "workspace", u_events)["user"] if needs_user else None
    a_eval = evaluate_workspace(spec, out_dir / "guests" / a_gid / "workspace", a_events)["agent"] if needs_agent else None
    u_pass = bool(u_eval and u_eval["success"]) if needs_user else None
    a_pass = bool(a_eval and a_eval["success"]) if needs_agent else None
    joint_pass = bool(u_pass and a_pass) if (needs_user and needs_agent) else bool(u_pass if needs_user else a_pass)

    result = {
        "case_key": case_key,
        "title": spec.title,
        "prototype_ref": spec.prototype_ref,
        "user_url": spec.user_url,
        "agent_url": spec.agent_url,
        "mode": mode,
        "run_id": run_id,
        "status": "error" if error_text else "complete",
        "error": error_text,
        "outcomes": {"user_pass": u_pass, "agent_pass": a_pass, "joint_pass": joint_pass},
        "oracle": {"user": u_eval, "agent": a_eval},
        "actors": {"user": user_summary, "agent": agent_summary},
        "space_interruption": {
            "space_switch_count": len(space_switches),
            "user_wrong_space_steps": (user_summary or {}).get("interrupted_wrong_space_steps", 0),
            "switches": [
                {
                    "run_elapsed_s": s.get("run_elapsed_s"),
                    "from_space": s.get("from_space"),
                    "to_space": s.get("to_space"),
                    "active_window": s.get("active_window"),
                }
                for s in space_switches
            ],
        },
        "timeline": timeline,
        "permission_policy": {
            "sandbox_mode": "workspace-write" if needs_agent else None,
            "approval_policy": "never" if needs_agent else None,
            "all_tools_enabled": True if needs_agent else None,
            "yolo_enabled": False,
            "vm_host_codex_launched": False,
        },
        "recordings": recordings,
        "elapsed_s": round(time.monotonic() - started_mono, 2),
    }
    write_json(out_dir / "run.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="*", default=[c.key for c in REAL_MACOS_5_CATALOG])
    ap.add_argument("--modes", nargs="*", default=["shared"])
    ap.add_argument("--api-json", type=Path, default=None)
    ap.add_argument("--codex-bin", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    code_root = args.code_root.resolve()
    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8")) if args.api_json else None
    codex_bin = args.codex_bin.resolve() if args.codex_bin else None

    jobs = [(ck, m) for ck in args.cases for m in args.modes]
    status_map: dict[str, Any] = {}
    lock = threading.Lock()

    def _run_one(ck: str, m: str) -> dict[str, Any]:
        print(f"START {ck} [{m}]", flush=True)
        res = run_real_case_condition(
            case_key=ck,
            mode=m,
            out_dir=out_root / ck / m,
            code_root=code_root,
            api_cfg=api_cfg,
            codex_bin=codex_bin,
            model_name=args.model,
            effort=args.effort,
        )
        with lock:
            status_map[f"{ck}/{m}"] = {
                "outcomes": res["outcomes"],
                "space_switches": res["space_interruption"]["space_switch_count"],
                "user_wrong_space_steps": res["space_interruption"]["user_wrong_space_steps"],
                "elapsed_s": res["elapsed_s"],
                "error": res["error"],
            }
            write_json(out_root / "suite-status.json", status_map)
        print(
            f"DONE {ck} [{m}] -> {res['outcomes']} "
            f"switches={res['space_interruption']['space_switch_count']} "
            f"wrong_space_steps={res['space_interruption']['user_wrong_space_steps']} "
            f"({res['elapsed_s']}s) err={res['error']}",
            flush=True,
        )
        return res

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [pool.submit(_run_one, ck, m) for ck, m in jobs]
        for f in as_completed(futs):
            f.result()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

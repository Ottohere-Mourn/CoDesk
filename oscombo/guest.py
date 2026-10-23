"""The shared Guest: a booted OSWorld ``DesktopEnv`` plus direct calls to its in-VM HTTP server.

Several agents use one ``Guest`` from different threads; every call here is a stateless HTTP request.
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests


class InfraError(RuntimeError):
    """The Guest or the host failed, not the agent. Messages start with "INFRA" so result filters can find them."""

    def __init__(self, message: str):
        super().__init__(message if message.startswith("INFRA") else f"INFRA: {message}")


class Guest:
    def __init__(self, env: Any):
        self.env = env

    @property
    def url(self) -> str:
        """Base URL of the in-VM server (screenshot, execute, ...), e.g. for an external harness or MCP server."""
        return f"http://{self.env.vm_ip}:{self.env.server_port}"

    def execute(self, argv: list[str], timeout: float = 60) -> dict:
        r = requests.post(f"{self.url}/execute", json={"command": argv, "shell": False, "timeout": 30},
                          timeout=(5, timeout))
        r.raise_for_status()
        return r.json()

    def active_window(self) -> str | None:
        """Title of the focused window, recorded before every action (cross-agent interference metric)."""
        try:
            out = self.execute(["bash", "-lc", "xdotool getactivewindow getwindowname 2>/dev/null || true"], 30)
            return (out.get("output") or "").strip() or None
        except Exception:
            return None

    def screenshot(self, patience: float | None = None) -> bytes:
        """PNG bytes; a slow (TCG) Guest under load may return nothing for a while, so retry up to ``patience`` s."""
        patience = float(os.environ.get("OSCOMBO_SHOT_PATIENCE", "120")) if patience is None else patience
        shot = self.env.controller.get_screenshot()
        deadline = time.monotonic() + patience
        while not shot and time.monotonic() < deadline:
            time.sleep(5)
            shot = self.env.controller.get_screenshot()
        if not shot:
            raise InfraError(f"no Guest screenshot for {patience:.0f} s")
        return shot

    def accessibility_tree(self) -> str | None:
        return self.env.controller.get_accessibility_tree()

    def run_pyautogui(self, code: str) -> Any:
        return self.env.controller.execute_python_command(code)

    def quiet_notifications(self) -> None:
        """GNOME notification banners (e.g. "Low Disk Space") can cover click targets; turn them off. Long runs
        also must not blank or lock the screen."""
        self.execute(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])
        self.execute(["bash", "-c", "gsettings set org.gnome.desktop.session idle-delay 0; "
                                    "gsettings set org.gnome.desktop.screensaver lock-enabled false"])

    def wait_desktop(self, patience: float | None = None) -> bytes:
        """Under heavy host load the screen sometimes stays black after setup (a black 1080p PNG is ~6.5 KB) and
        agents starting on it give up within a few steps: nudge the pointer until the desktop is drawn, else INFRA."""
        patience = float(os.environ.get("OSCOMBO_DESKTOP_PATIENCE", "240")) if patience is None else patience
        t0 = time.time()
        while True:
            shot = self.env.controller.get_screenshot() or b""
            if len(shot) > 20000:
                return shot
            if time.time() - t0 > patience:
                raise InfraError(f"Guest screen still black {patience:.0f} s after setup")
            try:
                self.execute(["bash", "-c", "DISPLAY=:0 xdotool mousemove_relative -- 1 1 mousemove_relative -- -1 -1"])
            except Exception:
                pass
            time.sleep(15)

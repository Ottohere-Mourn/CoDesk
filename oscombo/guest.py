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
        """GNOME notification banners (e.g. "Low Disk Space") can cover click targets; turn them off."""
        self.execute(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])

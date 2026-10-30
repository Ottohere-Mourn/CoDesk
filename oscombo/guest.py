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
        if getattr(self.env, "provider_name", None) == "local":
            command = argv[2] if len(argv) >= 3 and argv[:2] == ["bash", "-lc"] else argv
            result = self.env.controller.run_bash_script(command, timeout=timeout) if isinstance(command, str) else self.env.setup_controller.execute(command, timeout=timeout)
            return result
        r = requests.post(f"{self.url}/execute", json={"command": argv, "shell": False, "timeout": 30},
                          timeout=(5, timeout))
        r.raise_for_status()
        return r.json()

    def active_window(self) -> str | None:
        """Title of the focused window, recorded before every action (cross-agent interference metric)."""
        try:
            if getattr(self.env, "provider_name", None) == "local":
                if not self.env.display:
                    return None
                result = self.env.setup_controller.execute(
                    ["xdotool", "getactivewindow", "getwindowname"], timeout=30)
                return (result.stdout or "").strip() or None
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
        result = self.env.controller.execute_python_command(code)
        if getattr(self.env, "provider_name", None) == "local" and result.get("status") != "success":
            raise InfraError(f"local pyautogui action failed: {result.get('error', 'unknown error').strip()}")
        return result

    def quiet_notifications(self) -> None:
        """GNOME notification banners (e.g. "Low Disk Space") can cover click targets; turn them off."""
        self.execute(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])

    def adapt_case(self, case_id: str, run_root: str, *, role: str, guest_root: str = "/tmp/codesk",
                   app_url: str | None = None, source_dir: str | None = None) -> dict[str, Any]:
        """Stage an actor-visible case workspace and launch its desktop entry app."""
        from .collab.desktop_adapters import adapt_case
        return adapt_case(self, case_id, run_root, role=role, guest_root=guest_root,
                          app_url=app_url, source_dir=source_dir)

    def collect_case_artifacts(self, case_id: str, run_root: str, *, role: str,
                               guest_root: str = "/tmp/codesk") -> dict[str, Any]:
        """Copy visible outputs back as run evidence; case APIs perform canonical commits."""
        from .collab.desktop_adapters import collect_case_artifacts
        return collect_case_artifacts(self, case_id, run_root, role=role, guest_root=guest_root)

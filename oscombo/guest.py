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
        guest_timeout = max(1, min(120, int(timeout)))
        r = requests.post(f"{self.url}/execute", json={"command": argv, "shell": False,
                                                        "timeout": guest_timeout},
                          timeout=(5, timeout))
        if not r.ok:
            raise InfraError(f"Guest execute HTTP {r.status_code}: {r.text[:1000]}")
        return r.json()

    def active_window_info(self) -> dict[str, str | None]:
        """Focused X11 window identity and title; titles can change without focus changing."""
        try:
            command = 'wid=$(xdotool getactivewindow 2>/dev/null) || exit 0; title=$(xdotool getwindowname "$wid" 2>/dev/null || true); printf "%s\t%s" "$wid" "$title"'
            if getattr(self.env, "provider_name", None) == "local":
                if not self.env.display:
                    return {"id": None, "title": None}
                result = self.env.setup_controller.execute(["bash", "-lc", command], timeout=30)
                value = (result.stdout or "").strip()
            else:
                out = self.execute(["bash", "-lc", command], 30)
                value = (out.get("output") or "").strip()
            if "\t" not in value:
                return {"id": None, "title": value or None}
            window_id, title = value.split("\t", 1)
            return {"id": window_id or None, "title": title or None}
        except Exception:
            return {"id": None, "title": None}

    def active_window(self) -> str | None:
        """Title of the focused window, recorded before actions."""
        return self.active_window_info()["title"]

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
        self.execute(["bash", "-c", "gsettings set org.gnome.desktop.session idle-delay 0; "
                                    "gsettings set org.gnome.desktop.screensaver lock-enabled false"])

    def wait_desktop(self, patience: float | None = None) -> bytes:
        """Wait for the Guest desktop to render; nudge X11 if setup left a black screen."""
        patience = float(os.environ.get("OSCOMBO_DESKTOP_PATIENCE", "240")) if patience is None else patience
        started = time.time()
        while True:
            shot = self.env.controller.get_screenshot() or b""
            if len(shot) > 20000:
                return shot
            if time.time() - started > patience:
                raise InfraError(f"Guest screen still black {patience:.0f} s after setup")
            try:
                self.execute(["bash", "-c", "DISPLAY=:0 xdotool mousemove_relative -- 1 1 mousemove_relative -- -1 -1"])
            except Exception:
                pass
            time.sleep(15)

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

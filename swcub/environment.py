"""Docker/Xvfb-backed real desktop and shared-workspace adapter."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import time
import uuid
from typing import Any, Protocol, Sequence, runtime_checkable

from .core import EventLog


class EnvironmentError(RuntimeError):
    pass


@runtime_checkable
class EnvironmentAdapter(Protocol):
    """Common actor-facing reset/observe/act contract for desktop adapters."""
    environment_id: str
    log: EventLog

    def reset(self, **kwargs: Any) -> Any: ...
    def observe(self, actor_id: str, interface: str) -> Any: ...
    def act(self, actor_id: str, interface: str, action: Any) -> Any: ...
    def snapshot(self) -> dict[str, Any]: ...
    def close(self) -> None: ...


class DockerX11Workspace:
    """One Ubuntu container, one Xvfb display, one Tk GUI, and one shared CSV."""

    IMAGE = "swcub-v0:local"

    def __init__(self, project_root: Path, log: EventLog | None = None,
                 command_timeout: float = 20.0):
        self.project_root = project_root.resolve()
        self.log = log or EventLog()
        self.command_timeout = command_timeout
        self.container_name = ""
        self.environment_id = ""
        self.workspace: Path | None = None
        self.csv_path: Path | None = None
        self.window_id: str | None = None
        self.stale_gui_write = False
        self.episode = 0

    def _run(self, argv: Sequence[str], *, timeout: float | None = None,
             check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(list(map(str, argv)), text=True,
                              stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                              stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
                              timeout=timeout or self.command_timeout)
        if check and proc.returncode:
            raise EnvironmentError(
                f"command failed ({proc.returncode}): {list(argv)!r}\n"
                f"stdout={proc.stdout[-2000:] if proc.stdout else ''}\n"
                f"stderr={proc.stderr[-2000:] if proc.stderr else ''}")
        return proc

    def build(self) -> None:
        self._run(["docker", "build", "--tag", self.IMAGE,
                   "--file", self.project_root / "Dockerfile", self.project_root], timeout=900)

    def reset(self, *, stale_gui_write: bool = False) -> str:
        previous_id = self.environment_id
        if self.container_name:
            self.close_container()
        self._cleanup_workspace()
        self.episode += 1
        self.environment_id = f"swcub-episode-{self.episode}-{uuid.uuid4().hex[:8]}"
        self.container_name = self.environment_id
        self.stale_gui_write = stale_gui_write
        self.workspace = Path(tempfile.mkdtemp(prefix=f"{self.environment_id}-"))
        self.csv_path = self.workspace / "shared.csv"
        self.csv_path.write_text("id,actor,value\n", encoding="utf-8")
        self.window_id = None
        self._run(["docker", "run", "--detach", "--rm", "--name", self.container_name,
                   "--volume", f"{self.workspace}:/workspace", "--workdir", "/workspace",
                   self.IMAGE, "sleep", "infinity"])
        self._run(["docker", "exec", "--detach", self.container_name,
                   "Xvfb", ":99", "-screen", "0", "1024x768x24", "-ac", "-nolisten", "tcp"])
        self._wait_for_x()
        app_args = ["docker", "exec", "--detach", "--env", "DISPLAY=:99", self.container_name,
                    "python3", "/opt/swcub/gui_workspace.py", "--csv", "/workspace/shared.csv"]
        if stale_gui_write:
            app_args.append("--stale-write")
        self._run(app_args)
        self._wait_for_gui()
        snap = self.snapshot()
        self.log.record("environment", "reset", "docker_x11.reset", {"environment_id": previous_id}, snap,
                        details={"environment_id": self.environment_id, "episode": self.episode,
                                 "stale_gui_write": stale_gui_write})
        return self.environment_id

    def _wait_for_x(self) -> None:
        deadline = time.monotonic() + 20
        last = ""
        while time.monotonic() < deadline:
            proc = self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                              "xdpyinfo"], check=False, timeout=3)
            if proc.returncode == 0:
                return
            last = proc.stderr or "waiting for Xvfb"
            time.sleep(0.2)
        raise EnvironmentError(f"Xvfb failed to become ready: {last}")

    def _wait_for_gui(self) -> None:
        deadline = time.monotonic() + 20
        last = ""
        while time.monotonic() < deadline:
            proc = self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                              "xdotool", "search", "--onlyvisible", "--name", "Shared Workspace"],
                             check=False, timeout=3)
            if proc.returncode == 0 and proc.stdout.strip():
                self.window_id = proc.stdout.strip().splitlines()[-1]
                return
            last = proc.stderr or proc.stdout or "waiting for the Tk window"
            time.sleep(0.2)
        self._container_logs()
        raise EnvironmentError(f"Tk GUI failed to become visible: {last}")

    def _container_logs(self) -> None:
        if self.container_name:
            proc = self._run(["docker", "exec", self.container_name, "sh", "-c",
                              "cat /tmp/.X99-lock 2>/dev/null; ps aux"], check=False)
            print(proc.stdout, proc.stderr)

    def _csv_bytes(self) -> bytes:
        if self.csv_path is None:
            return b""
        return self.csv_path.read_bytes()

    def snapshot(self) -> dict[str, Any]:
        raw = self._csv_bytes()
        return {"environment_id": self.environment_id,
                "container": self.container_name,
                "csv_sha256": hashlib.sha256(raw).hexdigest(),
                "csv_bytes": len(raw),
                "window_id": self.window_id}

    def observe(self, actor_id: str, interface: str = "gui") -> dict[str, Any]:
        if interface != "gui":
            raise ValueError(f"unsupported observation interface: {interface}")
        return self.observe_gui(actor_id)

    def act(self, actor_id: str, interface: str, action: Any) -> Any:
        if interface == "gui" and isinstance(action, dict) and action.get("op") == "submit":
            return self.gui_submit(actor_id, str(action["value"]))
        if interface == "cli" and isinstance(action, (list, tuple)):
            return self.cli_command(actor_id, action)
        raise ValueError(f"unsupported {interface} action: {action!r}")

    def observe_gui(self, actor_id: str) -> dict[str, Any]:
        if not self.window_id:
            raise EnvironmentError("GUI window has not started")
        before = self.snapshot()
        title = self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                           "xdotool", "getwindowname", self.window_id]).stdout.strip()
        screenshot_guest = f"/workspace/{actor_id}-screen.xwd"
        self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                   "xwd", "-silent", "-root", "-out", screenshot_guest])
        screenshot = self.workspace / f"{actor_id}-screen.xwd"
        self._run(["docker", "cp", f"{self.container_name}:{screenshot_guest}", screenshot])
        visual = {"window_title": title,
                  "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                  "screenshot_bytes": screenshot.stat().st_size}
        self.log.record(actor_id, "observation", "x11.screenshot", before, self.snapshot(),
                        details={"environment_id": self.environment_id, **visual})
        return visual

    def gui_submit(self, actor_id: str, value: str) -> None:
        if not self.window_id:
            raise EnvironmentError("GUI window has not started")
        before = self.snapshot()
        self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                   "xdotool", "windowfocus", "--sync", self.window_id])
        self.log.record(actor_id, "gui", "xdotool.windowfocus", before, self.snapshot(),
                        details={"environment_id": self.environment_id, "window_id": self.window_id})
        before = self.snapshot()
        self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                   "xdotool", "type", "--clearmodifiers", "--delay", "2", value])
        self.log.record(actor_id, "gui", "xdotool.type", before, self.snapshot(),
                        details={"environment_id": self.environment_id, "text": value})
        before = self.snapshot()
        self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                   "xdotool", "key", "Return"])
        time.sleep(0.2)
        self.log.record(actor_id, "gui", "xdotool.key_return", before, self.snapshot(),
                        details={"environment_id": self.environment_id})

    def cli_command(self, actor_id: str, command: Sequence[str]) -> str:
        if not command or command[0] != "python3":
            raise ValueError("scripted CLI adapter only permits pinned Python workspace commands")
        before = self.snapshot()
        result = self._run(["docker", "exec", self.container_name, *command])
        self.log.record(actor_id, "cli", "docker.exec", before, self.snapshot(),
                        details={"environment_id": self.environment_id,
                                 "argv": list(command), "stdout": result.stdout.strip()})
        return result.stdout.strip()

    def copy_artifacts(self, out: Path) -> None:
        if self.workspace is None:
            return
        out.mkdir(parents=True, exist_ok=True)
        for path in self.workspace.glob("*-screen.xwd"):
            (out / path.name).write_bytes(path.read_bytes())
        if self.csv_path:
            (out / "shared.csv").write_bytes(self.csv_path.read_bytes())

    def close_container(self) -> None:
        if self.container_name:
            self._run(["docker", "rm", "--force", self.container_name], check=False, timeout=30)
            self.container_name = ""
        self.window_id = None

    def close(self) -> None:
        self.close_container()
        self._cleanup_workspace()
        self.csv_path = None

    def _cleanup_workspace(self) -> None:
        if self.workspace and self.workspace.exists():
            for path in self.workspace.iterdir():
                if path.is_file():
                    path.unlink()
            self.workspace.rmdir()
        self.workspace = None


class ActorContext:
    """Role-limited tools. There is intentionally no evaluator or raw workspace path."""

    def __init__(self, actor_id: str, environment: EnvironmentAdapter, role: str):
        self.actor_id = actor_id
        self.environment_id = environment.environment_id
        self._environment = environment
        self._role = role

    def observe(self) -> dict[str, Any]:
        if self._role != "gui":
            raise PermissionError("this actor has no GUI observation capability")
        return self._environment.observe(self.actor_id, "gui")

    def submit_gui(self, value: str) -> None:
        if self._role != "gui":
            raise PermissionError("this actor has no GUI input capability")
        self._environment.act(self.actor_id, "gui", {"op": "submit", "value": value})

    def run_cli(self, command: Sequence[str]) -> str:
        if self._role != "cli":
            raise PermissionError("this actor has no CLI capability")
        return self._environment.act(self.actor_id, "cli", command)

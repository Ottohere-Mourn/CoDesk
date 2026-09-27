"""Docker/Xvfb-backed real desktop and shared-workspace adapter."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any, Protocol, Sequence, runtime_checkable

from .core import EventLog
from .resource_safety import (PROJECT_NAME, ResourceLedger, ensure_resource_identity,
                              cleanup_docker_cli_container, verify_owned_directory)


class EnvironmentError(RuntimeError):
    pass


@runtime_checkable
class EnvironmentAdapter(Protocol):
    """Common actor-facing reset/observe/act contract for desktop adapters."""
    environment_id: str
    log: EventLog

    def reset(self, **kwargs: Any) -> Any: ...
    def observe(self, actor_id: str, interface: str) -> Any: ...
    def act(self, actor_id: str, interface: str, action: Any,
            observed_revision: int | None = None) -> Any: ...
    def snapshot(self) -> dict[str, Any]: ...
    def close(self) -> None: ...


class DockerX11Workspace:
    """One Ubuntu container, one Xvfb display, one Tk GUI, and one shared CSV."""

    IMAGE = "swcub-v0:local"

    def __init__(self, project_root: Path, log: EventLog | None = None,
                 command_timeout: float = 20.0, image: str | None = None):
        self.project_root = project_root.resolve()
        self.image = image or self.IMAGE
        self.log = log or EventLog()
        self.command_timeout = command_timeout
        self.resource_identity = ensure_resource_identity()
        self.resource_ledger = ResourceLedger(self.resource_identity.ledger_path)
        self.image_id: str | None = None
        self.container_name = ""
        self.container_id = ""
        self.environment_id = ""
        self.workspace: Path | None = None
        self.csv_path: Path | None = None
        self.state_path: Path | None = None
        self.window_id: str | None = None
        self.window_ids: dict[str, str] = {}
        self.task = "csv"
        self.stale_gui_write = False
        self.episode = 0
        self.revision = 0

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
        existing = self._run(["docker", "image", "inspect", self.image], check=False)
        if existing.returncode == 0:
            raise EnvironmentError(f"refusing to replace pre-existing image tag {self.image!r}; "
                                   "choose a new tag or use --skip-build")
        command = ["docker", "build", "--tag", self.image,
                   "--label", f"org.swcub.project={PROJECT_NAME}",
                   "--label", f"org.swcub.run-id={self.resource_identity.run_id}",
                   "--label", f"org.swcub.owner-token={self.resource_identity.owner_token}",
                   "--file", self.project_root / "Dockerfile", self.project_root]
        self._run(command, timeout=900)
        rows = json.loads(self._run(["docker", "image", "inspect", self.image]).stdout)
        if len(rows) != 1:
            raise EnvironmentError("image build did not return exactly one image")
        image = rows[0]
        labels = ((image.get("Config") or {}).get("Labels") or {})
        if any(labels.get(key) != value
               for key, value in self.resource_identity.labels.items()):
            raise EnvironmentError("built image ownership labels do not match this run")
        self.image_id = image["Id"]
        self.resource_ledger.record_created_resource("image", self.image_id,
                                                     self.resource_identity, tag=self.image)

    def reset(self, *, stale_gui_write: bool = False, task: str = "csv") -> str:
        if task not in {"csv", "focus"}:
            raise ValueError(f"unknown task environment: {task}")
        previous_id = self.environment_id
        if self.container_name:
            self.close_container()
        self._cleanup_workspace()
        self.episode += 1
        self.environment_id = f"swcub-episode-{self.episode}-{uuid.uuid4().hex[:8]}"
        self.container_name = self.environment_id
        self.stale_gui_write = stale_gui_write
        self.task = task
        self.revision = 0
        self.workspace = Path(tempfile.mkdtemp(prefix=f"{self.environment_id}-"))
        workspace_id = uuid.uuid4().hex
        marker = {"project": PROJECT_NAME, "run_id": self.resource_identity.run_id,
                  "owner_token": self.resource_identity.owner_token,
                  "resource_id": workspace_id, "path": str(self.workspace.resolve())}
        (self.workspace / ".swcub-resource.json").write_text(
            json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
        self.workspace_id = workspace_id
        self.resource_ledger.record_created_resource("directory", workspace_id,
                                                     self.resource_identity,
                                                     path=str(self.workspace.resolve()))
        self.csv_path = self.workspace / "shared.csv"
        self.csv_path.write_text("id,actor,value\n", encoding="utf-8")
        self.state_path = self.workspace / "focus_state.json"
        if task == "focus":
            self.state_path.write_text(json.dumps({"Document": "", "Chat": ""}), encoding="utf-8")
        self.window_id = None
        self.window_ids = {}
        run_argv = ["docker", "run", "--detach", "--name", self.container_name]
        for key, value in self.resource_identity.labels.items():
            run_argv.extend(["--label", f"{key}={value}"])
        run_argv.extend([
                   "--volume", f"{self.workspace}:/workspace", "--workdir", "/workspace",
                   self.image, "sleep", "infinity"])
        self.container_id = self._run(run_argv).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", self.container_id):
            raise EnvironmentError("docker run did not return a full container ID; leaving resource untouched")
        attrs = self._inspect_owned_container()
        self.resource_ledger.created_container(self.container_id, self.resource_identity,
                                               name=self.container_name,
                                               image=str(attrs.get("Config", {}).get("Image", self.image)))
        self._run(["docker", "exec", "--detach", self.container_name,
                   "Xvfb", ":99", "-screen", "0", "1024x768x24", "-ac", "-nolisten", "tcp"])
        self._wait_for_x()
        if task == "csv":
            app_args = ["docker", "exec", "--detach", "--env", "DISPLAY=:99", self.container_name,
                        "python3", "/opt/swcub/gui_workspace.py", "--csv", "/workspace/shared.csv"]
            if stale_gui_write:
                app_args.append("--stale-write")
        else:
            app_args = ["docker", "exec", "--detach", "--env", "DISPLAY=:99", self.container_name,
                        "python3", "/opt/swcub/focus_workspace.py", "--state", "/workspace/focus_state.json"]
        self._run(app_args)
        self._wait_for_gui()
        if task == "focus":
            self.gui_focus("environment", "Document")
        snap = self.snapshot()
        self.log.record("environment", "reset", "docker_x11.reset", {"environment_id": previous_id}, snap,
                        details={"environment_id": self.environment_id, "episode": self.episode,
                                 "stale_gui_write": stale_gui_write, "task": task})
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
        titles = ["Shared Workspace"] if self.task == "csv" else ["Document", "Chat"]
        last = ""
        while time.monotonic() < deadline:
            found: dict[str, str] = {}
            for title in titles:
                proc = self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                                  "xdotool", "search", "--onlyvisible", "--name", f"^{title}$"],
                                 check=False, timeout=3)
                if proc.returncode == 0 and proc.stdout.strip():
                    found[title] = proc.stdout.strip().splitlines()[-1]
            if len(found) == len(titles):
                self.window_ids = found
                self.window_id = found.get("Shared Workspace", found.get("Document"))
                return
            last = f"visible windows {found}; expected {titles}"
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
        state_raw = self.state_path.read_bytes() if self.state_path and self.state_path.exists() else b""
        return {"environment_id": self.environment_id,
                "resource_run_id": self.resource_identity.run_id,
                "revision": self.revision,
                "container": self.container_name,
                "container_id": self.container_id,
                "csv_sha256": hashlib.sha256(raw).hexdigest(),
                "csv_bytes": len(raw),
                "application_state_sha256": hashlib.sha256(state_raw).hexdigest(),
                "window_id": self.window_id,
                "windows": dict(self.window_ids),
                "task": self.task}

    def observe(self, actor_id: str, interface: str = "gui") -> dict[str, Any]:
        if interface != "gui":
            raise ValueError(f"unsupported observation interface: {interface}")
        return self.observe_gui(actor_id)

    def act(self, actor_id: str, interface: str, action: Any,
            observed_revision: int | None = None) -> Any:
        if observed_revision is None:
            observed_revision = self.revision
        if interface == "gui" and isinstance(action, dict):
            op = action.get("op")
            if op == "submit":
                return self.gui_submit(actor_id, str(action["value"]), observed_revision)
            if op == "focus":
                return self.gui_focus(actor_id, str(action["window"]), observed_revision)
            if op == "type":
                return self.gui_type_text(actor_id, str(action["value"]), observed_revision)
            if op == "key":
                return self.gui_press_key(actor_id, str(action["key"]), observed_revision)
        if interface == "cli" and isinstance(action, (list, tuple)):
            return self.cli_command(actor_id, action, observed_revision)
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
        screenshot_bytes = screenshot.read_bytes()
        visual = {"window_title": title,
                  "screenshot_format": "xwd",
                  "screenshot_width": 1024,
                  "screenshot_height": 768,
                  "screenshot": screenshot_bytes,
                  "screenshot_sha256": hashlib.sha256(screenshot_bytes).hexdigest(),
                  "screenshot_bytes": len(screenshot_bytes)}
        logged_visual = {key: value for key, value in visual.items() if key != "screenshot"}
        self.log.record(actor_id, "observation", "x11.screenshot", before, self.snapshot(),
                        observed_revision=self.revision,
                        details={"environment_id": self.environment_id, **logged_visual})
        return visual

    def _xdotool(self, actor_id: str, action: str, *argv: str,
                 observed_revision: int | None = None, mutates_state: bool = False) -> None:
        before = self.snapshot()
        self._run(["docker", "exec", "--env", "DISPLAY=:99", self.container_name,
                   "xdotool", *argv])
        if mutates_state:
            time.sleep(0.2)
            after_action = self.snapshot()
            if (after_action["csv_sha256"] != before["csv_sha256"]
                    or after_action["application_state_sha256"]
                    != before["application_state_sha256"]):
                self.revision += 1
        self.log.record(actor_id, "gui", action, before, self.snapshot(),
                        observed_revision=observed_revision,
                        details={"environment_id": self.environment_id, "argv": list(argv),
                                 "revision_before_action": before["revision"],
                                 "revision_after_action": self.revision})

    def gui_focus(self, actor_id: str, window: str,
                  observed_revision: int | None = None) -> None:
        window_id = self.window_ids.get(window)
        if window_id is None and window == "Shared Workspace":
            window_id = self.window_id
        if window_id is None:
            raise EnvironmentError(f"window {window!r} not visible; have {self.window_ids}")
        self._xdotool(actor_id, "xdotool.windowfocus", "windowfocus", "--sync", window_id,
                      observed_revision=observed_revision)
        if self.task == "focus":
            # X11 top-level focus and Tk child-widget focus are distinct without a WM.
            self._xdotool(actor_id, "xdotool.click_entry", "mousemove", "--window", window_id,
                          "120", "63", observed_revision=observed_revision)
            self._xdotool(actor_id, "xdotool.click", "click", "1",
                          observed_revision=observed_revision)

    def gui_type_text(self, actor_id: str, value: str,
                      observed_revision: int | None = None) -> None:
        self._xdotool(actor_id, "xdotool.type", "type", "--clearmodifiers", "--delay", "2", value,
                      observed_revision=observed_revision)

    def gui_press_key(self, actor_id: str, key: str,
                      observed_revision: int | None = None) -> None:
        self._xdotool(actor_id, "xdotool.key", "key", key,
                      observed_revision=observed_revision,
                      mutates_state=key.lower() in {"return", "enter"})

    def gui_submit(self, actor_id: str, value: str,
                   observed_revision: int | None = None) -> None:
        if not self.window_id:
            raise EnvironmentError("GUI window has not started")
        self.gui_focus(actor_id, "Shared Workspace" if self.task == "csv" else "Document",
                       observed_revision)
        self.gui_type_text(actor_id, value, observed_revision)
        self.gui_press_key(actor_id, "Return", observed_revision)

    def cli_command(self, actor_id: str, command: Sequence[str],
                    observed_revision: int | None = None) -> str:
        if not command or command[0] != "python3":
            raise ValueError("scripted CLI adapter only permits pinned Python workspace commands")
        before = self.snapshot()
        result = self._run(["docker", "exec", self.container_name, *command])
        after = self.snapshot()
        if (after["csv_sha256"] != before["csv_sha256"]
                or after["application_state_sha256"] != before["application_state_sha256"]):
            self.revision += 1
        self.log.record(actor_id, "cli", "docker.exec", before, self.snapshot(),
                        observed_revision=observed_revision,
                        details={"environment_id": self.environment_id,
                                 "revision_before_action": before["revision"],
                                 "revision_after_action": self.revision,
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
        if self.state_path and self.state_path.exists():
            (out / "focus_state.json").write_bytes(self.state_path.read_bytes())

    def close_container(self) -> None:
        if self.container_id:
            cleanup_docker_cli_container(
                self.container_id, self.resource_identity, reason="DockerX11Workspace.close",
                inspect_fn=lambda container_id: self._inspect_container(container_id))
            self.container_id = ""
            self.container_name = ""
        self.window_id = None

    def close(self) -> None:
        self.close_container()
        self._cleanup_workspace()
        self.csv_path = None
        self.state_path = None

    def _cleanup_workspace(self) -> None:
        if self.workspace and self.workspace.exists():
            if self.workspace.is_symlink() or self.workspace.parent.resolve() != Path(tempfile.gettempdir()).resolve():
                raise EnvironmentError("refusing workspace cleanup outside the exact temporary directory")
            marker_path = self.workspace / ".swcub-resource.json"
            if not marker_path.is_file() or marker_path.is_symlink():
                raise EnvironmentError("refusing workspace cleanup without its ownership marker")
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            verify_owned_directory(self.workspace, marker, self.resource_identity, self.workspace_id)
            if not self.resource_ledger.has_created_resource(
                    "directory", self.workspace_id, self.resource_identity):
                raise EnvironmentError("refusing workspace cleanup without this run's ledger entry")
            self.resource_ledger.record_destroyed_resource(
                "directory", self.workspace_id, self.resource_identity,
                path=str(self.workspace.resolve()))
            shutil.rmtree(self.workspace)
        self.workspace = None

    def _inspect_container(self, container_id: str) -> dict[str, Any]:
        proc = self._run(["docker", "inspect", "--type", "container", container_id])
        rows = json.loads(proc.stdout)
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise EnvironmentError("docker inspect did not return exactly one container")
        from .resource_safety import verify_container_identity
        verify_container_identity(container_id, rows[0], self.resource_identity)
        return rows[0]

    def _inspect_owned_container(self) -> dict[str, Any]:
        attrs = self._inspect_container(self.container_id)
        if attrs.get("Id") != self.container_id:
            raise EnvironmentError("container inspect ID differs from docker run's full ID")
        return attrs


class ActorContext:
    """Role-limited tools. There is intentionally no evaluator or raw workspace path."""

    def __init__(self, actor_id: str, environment: EnvironmentAdapter, role: str):
        self.actor_id = actor_id
        self.environment_id = environment.environment_id
        self._environment = environment
        self._role = role
        self._observed_revision: int | None = None

    def _require_gui(self) -> None:
        if self._role not in {"gui", "human_replay"}:
            raise PermissionError("this actor has no GUI capability")

    def observe(self) -> dict[str, Any]:
        self._require_gui()
        observation = self._environment.observe(self.actor_id, "gui")
        revision = getattr(self._environment, "revision", None)
        self._observed_revision = revision if type(revision) is int else None
        return observation

    def refresh_observation(self) -> dict[str, Any]:
        """Fetch a new observation when an adapter reports a transient empty frame."""
        self._require_gui()
        refresh = getattr(self._environment, "refresh_observation", None)
        if not callable(refresh):
            return self.observe()
        observation = refresh(self.actor_id)
        revision = getattr(self._environment, "revision", None)
        self._observed_revision = revision if type(revision) is int else None
        return observation

    def _act(self, interface: str, action: Any) -> Any:
        return self._environment.act(self.actor_id, interface, action,
                                     observed_revision=self._observed_revision)

    def submit_gui(self, value: str) -> None:
        self._require_gui()
        self._act("gui", {"op": "submit", "value": value})

    def focus_window(self, title: str) -> None:
        self._require_gui()
        self._act("gui", {"op": "focus", "window": title})

    def type_text(self, value: str) -> None:
        self._require_gui()
        self._act("gui", {"op": "type", "value": value})

    def click(self, x: int, y: int) -> None:
        self._require_gui()
        self._act("gui", {"op": "click", "x": x, "y": y})

    def press_key(self, key: str) -> None:
        self._require_gui()
        self._act("gui", {"op": "key", "key": key})

    def execute_gui_action(self, action: str) -> None:
        """Execute an action string emitted by a native computer-use framework.

        This method is for adapters that already speak the environment's native
        action protocol (for example OSWorld agents returning PyAutoGUI code).
        It does not add planning or action parsing.
        """
        self._require_gui()
        if not isinstance(action, str) or not action.strip():
            raise ValueError("native GUI action must be a non-empty string")
        self._act("gui", action)

    def run_cli(self, command: Sequence[str]) -> str:
        if self._role != "cli":
            raise PermissionError("this actor has no CLI capability")
        return self._act("cli", command)

#!/usr/bin/env python3
"""Run one scripted CoDesk Writer/Calc V1 episode on pinned OSWorld Guests."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen
import uuid
import xml.etree.ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OSWORLD_V2_DIR = Path(os.environ.get(
    "OSWORLD_V2_DIR", ROOT.parent / "_deps/OSWorld-V2-osworld-v2.1")).resolve()
sys.path.insert(0, str(OSWORLD_V2_DIR))

from desktop_env.desktop_env import DesktopEnv
from mm_agents.qwen3vl_agent import Qwen3VLAgent
from swcub.actors import ScriptedCalcActor, ScriptedWriterActor
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.evaluator import GuestLibreOfficeBindingEvaluator
from swcub.osworld_agent_actor import OSWorldAgentActor, OSWorldAgentActorError
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.osworld_readiness import wait_for_guest_desktop
from swcub.comparison_metrics import summarize_focus_events
from swcub.provenance import source_path_label
from swcub.resource_safety import PROJECT_NAME, ResourceLedger, ensure_resource_identity
from swcub.task_factory import render_calc_fods, render_writer_fodt
from swcub.shared_workspace import (GUEST_WORKSPACE_MOUNT, SHARED_WORKSPACE_TAG,
                                    guest_mount_command, validate_condition_topology,
                                    write_backend_marker)


TASK_ID = "CODESK-TA-OFFICE-001"
TASK_VERSION = "1.0.0"
TASK_APP_SETUP_TIMEOUT_SECONDS = 120
WRITER_PATH = "/tmp/swcub_office/document.fodt"
CALC_PATH = "/tmp/swcub_office/table.fods"
WRITER_DRAFT = "Quarterly status report"
WRITER_FINAL = "Approved by GUI actor"
CALC_DRAFT = [["Record", "Status"], ["Quarterly", "Draft"]]
CALC_FINAL = [["Record", "Status"], ["Quarterly", "Approved"]]
MODEL_STEP_BUDGET = 20
MODEL_STARTUP_TIMEOUT_SECONDS = 1800
MODEL_INTERLEAVED_SCHEDULE = [
    actor_id
    for _ in range(MODEL_STEP_BUDGET)
    for actor_id in ("writer_actor", "calc_actor")
]


class LocalQwenInferenceClient:
    """Thin transport for the pinned OSWorld agent and one shared inference worker."""

    def __init__(self, port: int | None = None, *, endpoint: str | None = None,
                 event_callback=None):
        if endpoint:
            self.base_url = endpoint.rstrip("/")
        elif port is not None:
            self.base_url = f"http://127.0.0.1:{port}"
        else:
            raise ValueError("provide a worker port or SSH-forwarded loopback endpoint")
        self.url = f"{self.base_url}/infer"
        self.event_callback = event_callback

    def complete(self, payload: dict[str, Any], _model: str,
                 actor_id: str = "unknown_actor") -> str:
        request_id = uuid.uuid4().hex[:16]
        body = json.dumps({"messages": payload["messages"],
                           "max_new_tokens": min(int(payload.get("max_tokens", 512)), 512)
                           }).encode("utf-8")
        request = Request(self.url, data=body,
                          headers={"Content-Type": "application/json",
                                   "X-CoDesk-Request-ID": request_id}, method="POST")
        started = time.monotonic()
        if self.event_callback:
            self.event_callback({"event": "request_start", "actor_id": actor_id,
                                 "request_id": request_id, "request_bytes": len(body)})
        try:
            with urlopen(request, timeout=600) as response:
                response_body = response.read()
            result = json.loads(response_body)
            if not isinstance(result, dict) or not isinstance(result.get("text"), str):
                raise ValueError("invalid model-worker response schema")
        except Exception as exc:
            if self.event_callback:
                self.event_callback({"event": "request_error", "actor_id": actor_id,
                    "request_id": request_id, "elapsed_ms": round(
                        (time.monotonic() - started) * 1000, 2),
                    "error_type": type(exc).__name__})
            raise
        if self.event_callback:
            self.event_callback({"event": "response", "actor_id": actor_id,
                "request_id": request_id, "elapsed_ms": round(
                    (time.monotonic() - started) * 1000, 2),
                "response_bytes": len(response_body), "response_chars": len(result["text"])})
        return result["text"]


def start_local_qwen_worker(out: Path) -> tuple[subprocess.Popen[bytes],
                                                LocalQwenInferenceClient,
                                                dict[str, Any]]:
    """Start the repository's local, offline Qwen worker without changing the agent."""
    host_python = os.environ.get("SWCUB_MODEL_PYTHON", "/opt/miniconda3/bin/python")
    model_path = Path(os.environ.get(
        "SWCUB_LOCAL_VLM_PATH", "/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct"))
    device = os.environ.get("SWCUB_LOCAL_VLM_DEVICE", "auto")
    if not Path(host_python).is_file():
        raise FileNotFoundError(f"configured local model Python is missing: {host_python}")
    config_path = model_path / "config.json"
    if not model_path.is_dir() or not config_path.is_file():
        raise FileNotFoundError(f"local Qwen model config is missing under {model_path}")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
    worker_env = os.environ.copy()
    worker_env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "HF_HUB_DISABLE_TELEMETRY": "1"})
    worker_env.setdefault("CUDA_VISIBLE_DEVICES", "0,2,3,4,5,6,7")
    log_path = out / "model_worker.log"
    with log_path.open("w", encoding="utf-8") as worker_log:
        process = subprocess.Popen(
            [host_python, str(ROOT / "scripts/local_qwen_worker.py"),
             "--model", str(model_path), "--device", device, "--port", str(port)],
            env=worker_env, stdout=worker_log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + MODEL_STARTUP_TIMEOUT_SECONDS
    health_url = f"http://127.0.0.1:{port}/health"
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"local Qwen worker exited; see {log_path}")
            try:
                with urlopen(health_url, timeout=5) as response:
                    health = json.loads(response.read())
                break
            except Exception:
                time.sleep(2)
        else:
            raise TimeoutError(
                f"local Qwen worker did not become ready within "
                f"{MODEL_STARTUP_TIMEOUT_SECONDS} seconds")
    except BaseException:
        stop_local_qwen_worker(process)
        raise
    worker_instance_id = str(uuid.uuid4())
    return process, LocalQwenInferenceClient(port), {
        "name": model_path.name,
        "path": str(model_path),
        "config_sha256": sha256_file(config_path),
        "device": device,
        "worker": "scripts/local_qwen_worker.py; local_files_only",
        "worker_instance_id": worker_instance_id,
        "worker_pid": process.pid,
        "worker_sharing": "one local inference process shared by both actor objects",
        "worker_bind": "127.0.0.1",
        "effective_generation": {"max_new_tokens": 512, "do_sample": False,
                                 "agent_temperature": 0.0, "agent_top_p": 0.9,
                                 "note": "local worker uses deterministic greedy decoding"},
        "inference_request_timeout_seconds": 600,
        "agent_framework": "OSWorld-V2.1 Qwen3VLAgent",
        "agent_source": str(OSWORLD_V2_DIR / "mm_agents/qwen3vl_agent.py"),
        "coordinate_type": "relative 0..999; native OSWorld parser scales to screenshot pixels",
        "step_budget_per_actor": MODEL_STEP_BUDGET,
        "health": health,
    }


def stop_local_qwen_worker(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_source_state() -> dict[str, Any]:
    def git(*args: str) -> str | None:
        proc = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                              text=True, check=False, timeout=10)
        return proc.stdout.strip() if proc.returncode == 0 else None
    return {"commit": git("rev-parse", "HEAD"),
            "dirty_paths": (git("status", "--porcelain") or "").splitlines()}


def flat_writer() -> bytes:
    return render_writer_fodt([WRITER_DRAFT])


def flat_calc() -> bytes:
    return render_calc_fods(CALC_DRAFT)


def seed_shared_backend(host_dir: Path) -> dict[str, dict[str, Any]]:
    """Seed only the fresh run-owned shared workspace before Guest mounts it."""
    if not host_dir.is_dir() or any(host_dir.iterdir()):
        raise SetupReadinessError("shared backend is missing or not empty before seeding",
                                  {"backend_path": str(host_dir)})
    manifest: dict[str, dict[str, Any]] = {}
    for filename, data in (("document.fodt", flat_writer()),
                           ("table.fods", flat_calc())):
        destination = host_dir / filename
        with destination.open("xb") as stream:
            stream.write(data)
        destination.chmod(0o666)
        manifest[filename] = {"sha256": hashlib.sha256(data).hexdigest(),
                              "size_bytes": len(data), "mode": "0666"}
    return manifest


class EpisodeBindings(dict[str, tuple[OSWorldSharedEpisode, DesktopEnv]]):
    """Host-side handles for all desktops participating in one task episode."""


class SetupReadinessError(RuntimeError):
    """Raised before actor turns when the task state or application is not ready."""

    def __init__(self, message: str, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def guest_command(desktop: DesktopEnv, argv: list[str], timeout: int = 45) -> str:
    response = requests.post(
        f"http://{desktop.vm_ip}:{desktop.server_port}/execute",
        json={"command": argv, "shell": False, "timeout": timeout},
        timeout=(5, timeout + 10))
    response.raise_for_status()
    payload = response.json()
    if payload.get("returncode", 0) not in (0, None):
        raise RuntimeError(f"Guest command failed: {payload!r}")
    return str(payload.get("output", ""))


def make_desktop(binding: str, log: EventLog, out: Path,
                 workspace_backend_host_dir: Path | None = None,
                 workspace_backend_id: str | None = None) -> tuple[OSWorldSharedEpisode, DesktopEnv]:
    guest_image = Path(os.environ.get(
        "SWCUB_OSWORLD_GUEST_IMAGE",
        OSWORLD_V2_DIR / "docker_vm_data/osworld-v2-ubuntu-x86.qcow2")).resolve()
    workspace_env_key = "SWCUB_OSWORLD_SHARED_WORKSPACE_HOST_DIR"
    prior_workspace_env = os.environ.get(workspace_env_key)
    if workspace_backend_host_dir is None:
        os.environ.pop(workspace_env_key, None)
    else:
        if not workspace_backend_host_dir.is_dir():
            raise SetupReadinessError("shared backend directory is missing",
                                      {"backend_id": workspace_backend_id})
        os.environ[workspace_env_key] = str(workspace_backend_host_dir.resolve())
    try:
        desktop = DesktopEnv(provider_name="docker", path_to_vm=str(guest_image),
                             cache_dir=os.environ.get(
                                 "SWCUB_OSWORLD_CACHE_DIR",
                                 str(OSWORLD_V2_DIR / "task-cache")),
                             os_type="Ubuntu", action_space="pyautogui")
    finally:
        if prior_workspace_env is None:
            os.environ.pop(workspace_env_key, None)
        else:
            os.environ[workspace_env_key] = prior_workspace_env
    episode = OSWorldSharedEpisode(
        desktop, cli_executor=lambda raw, desktop=desktop: guest_command(desktop, shlex.split(raw)))
    episode.log = log
    try:
        episode.reset(task_config=None)
        wait_for_guest_desktop(episode, desktop, timeout=300, retry_interval=5)
        if workspace_backend_host_dir is not None:
            guest_command(desktop, ["bash", "-lc", guest_mount_command(sudo_password=desktop.client_password)], timeout=60)
            episode.log.record(
                "environment", "workspace_mount", "writer_calc.shared_backend_mount",
                {"mounted": False}, {"mounted": True},
                details={"backend_id": workspace_backend_id,
                         "transport": "qemu-9p",
                         "mount_tag": SHARED_WORKSPACE_TAG,
                         "guest_mountpoint": GUEST_WORKSPACE_MOUNT,
                         "desktop_binding": binding})
    except BaseException as exc:
        before = episode.snapshot()
        episode.log.record("environment", "startup_error", "guest.startup_abort",
                           before, before, outcome="failed",
                           details={"desktop_binding": binding,
                                    "error": f"{type(exc).__name__}: {exc}"})
        try:
            episode.copy_artifacts(out / "guest-readiness-failure" / binding)
        except Exception:
            pass
        try:
            episode.log.write(out / "events.jsonl")
        except Exception:
            pass
        try:
            episode.close()
        except Exception as close_error:
            (out / f"{binding}-close-error.txt").write_text(
                f"{type(close_error).__name__}: {close_error}\n", encoding="utf-8")
        raise
    out.mkdir(parents=True, exist_ok=True)
    return episode, desktop


def read_seeded_state(episode: OSWorldSharedEpisode, desktop: DesktopEnv) -> dict[str, Any]:
    writer_raw = guest_command(desktop, ["cat", WRITER_PATH])
    calc_raw = guest_command(desktop, ["cat", CALC_PATH])
    writer_text = GuestLibreOfficeBindingEvaluator._parse_writer(writer_raw)
    calc_cells = GuestLibreOfficeBindingEvaluator._parse_calc(calc_raw)
    calc_root = ET.fromstring(calc_raw)
    table_ns = GuestLibreOfficeBindingEvaluator.TABLE_NS
    sheets = [node.get(f"{{{table_ns}}}name") for node in
              calc_root.iter(f"{{{table_ns}}}table")]
    return {"writer_text": writer_text, "calc_cells": calc_cells,
            "calc_sheet_names": sheets}


def save_final_odf_artifacts(environments: EpisodeBindings, out: Path) -> dict[str, Any]:
    saved: dict[str, Any] = {}
    for binding, (_episode, desktop) in environments.items():
        target = out / "final-odf" / binding
        target.mkdir(parents=True, exist_ok=True)
        files = {}
        for guest_path, filename in ((WRITER_PATH, "document.fodt"),
                                     (CALC_PATH, "table.fods")):
            raw = guest_command(desktop, ["cat", guest_path])
            data = raw.encode("utf-8")
            destination = target / filename
            destination.write_bytes(data)
            files[filename] = {"path": str(destination.relative_to(out)),
                               "sha256": hashlib.sha256(data).hexdigest(),
                               "size_bytes": len(data)}
        saved[binding] = files
    return saved


def _document_title_matches(title: str | None, app: str, path: str) -> bool:
    if not title:
        return False
    normalized = title.casefold()
    expected_name = Path(path).name.casefold()
    app_name = "libreoffice writer" if app == "writer" else "libreoffice calc"
    return expected_name in normalized and app_name in normalized


def _document_is_read_only(title: str | None) -> bool:
    return bool(title and "read-only" in title.casefold())


def _setup_capture(episode: OSWorldSharedEpisode, out: Path, label: str,
                   persist: bool = False) -> dict[str, Any]:
    observation = episode.observation if isinstance(episode.observation, dict) else {}
    screenshot = observation.get("screenshot")
    tree = observation.get("accessibility_tree")
    if persist:
        capture_dir = out / "setup-validation"
        capture_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(screenshot, bytes):
            (capture_dir / f"{label}.png").write_bytes(screenshot)
        if isinstance(tree, str) and tree.strip():
            # These compact artifacts make active-window evidence auditable.
            (capture_dir / f"{label}.accessibility.xml").write_text(tree, encoding="utf-8")
    return {"active_window_title": episode._active_window_title(),
            "accessibility_tree_available": isinstance(tree, str) and bool(tree.strip()),
            "accessibility_tree_chars": len(tree) if isinstance(tree, str) else 0,
            "screenshot_available": isinstance(screenshot, bytes) and bool(screenshot)}


def wait_for_app_document(episode: OSWorldSharedEpisode, desktop: DesktopEnv,
                          app: str, path: str, out: Path,
                          timeout: float = TASK_APP_SETUP_TIMEOUT_SECONDS) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    attempts = 0
    last_capture: dict[str, Any] = {}
    last_error: str | None = None
    while time.monotonic() < deadline:
        attempts += 1
        try:
            episode.refresh_observation(source="task_setup")
            last_capture = _setup_capture(episode, out,
                                          f"{app}-window-attempt-{attempts:02d}")
            if _document_title_matches(last_capture["active_window_title"], app, path):
                if _document_is_read_only(last_capture["active_window_title"]):
                    _setup_capture(episode, out, f"{app}-read-only-window", persist=True)
                    raise SetupReadinessError(
                        f"{app} opened {Path(path).name!r} read-only; task setup is not writable",
                        {"app": app, "expected_document": Path(path).name,
                         "active_window_title": last_capture["active_window_title"],
                         "attempt": attempts})
                _setup_capture(episode, out, f"{app}-window-ready", persist=True)
                result = {"app": app, "expected_document": Path(path).name,
                          "active_window_title": last_capture["active_window_title"],
                          "attempts": attempts, "ready": True,
                          "screenshot": last_capture["screenshot_available"],
                          "accessibility_tree": last_capture["accessibility_tree_available"]}
                episode.log.record("task_setup", "healthcheck", "office.document_ready",
                                   {"ready": False}, result, outcome="ready",
                                   details={"guest_container_id": episode.snapshot().get(
                                       "guest_container_id"), **result})
                return result
            last_error = "active title does not identify the requested office document"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        episode.log.record("task_setup", "healthcheck", "office.document_readiness_retry",
                           {"ready": False}, {"ready": False}, outcome="retry",
                           details={"app": app, "expected_document": Path(path).name,
                                    "attempt": attempts,
                                    "active_window_title": last_capture.get("active_window_title"),
                                    "reason": last_error,
                                    "guest_container_id": episode.snapshot().get(
                                        "guest_container_id")})
        time.sleep(2)
    diagnostics = {"app": app, "expected_document": Path(path).name,
                   "attempts": attempts, "last_error": last_error,
                   "last_observation": last_capture}
    _setup_capture(episode, out, f"{app}-readiness-failed", persist=True)
    raise SetupReadinessError(
        f"{app} did not open {Path(path).name!r} in an active, observable window "
        f"within {timeout:.0f}s; last title={last_capture.get('active_window_title')!r}",
        diagnostics)


def _capture_guest_office_trace(desktop: DesktopEnv, app: str, out: Path) -> dict[str, Any]:
    prefix = f"/tmp/swcub-lo-{app}.trace"
    code = (
        "from pathlib import Path; import json; "
        f"ps=sorted(Path('/tmp').glob('swcub-lo-{app}.trace*')); "
        "rows=[{'name':p.name,'text':p.read_text(errors='replace')} for p in ps]; "
        "print(json.dumps(rows))")
    raw = guest_command(desktop, ["python3", "-c", code], timeout=60)
    rows = json.loads(raw) if raw.strip() else []
    trace_dir = out / "syscall-trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    target = trace_dir / f"{app}-full.json"
    target.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    text = "\n".join(item["text"] for item in rows)
    relevant = [line for line in text.splitlines()
                if "/tmp/swcub_office" in line or " = -1 " in line]
    summary = trace_dir / f"{app}-relevant.txt"
    summary.write_text("\n".join(relevant) + ("\n" if relevant else ""),
                       encoding="utf-8")
    return {"enabled": True, "trace_prefix": prefix, "files": len(rows),
            "full_trace": target.name, "relevant_trace": summary.name,
            "relevant_lines": len(relevant)}


def seed_and_open(episode: OSWorldSharedEpisode, desktop: DesktopEnv,
                  open_apps: list[str], out: Path,
                  initialize_workspace: bool = True,
                  shared_backend: bool = False) -> dict[str, Any]:
    if initialize_workspace:
        writer_b64 = base64.b64encode(flat_writer()).decode("ascii")
        calc_b64 = base64.b64encode(flat_calc()).decode("ascii")
        seed_code = (
            "from pathlib import Path; import base64; p=Path('/tmp/swcub_office'); p.mkdir(exist_ok=True); "
            f"Path('{WRITER_PATH}').write_bytes(base64.b64decode('{writer_b64}')); "
            f"Path('{CALC_PATH}').write_bytes(base64.b64decode('{calc_b64}'))")
        episode.cli_action("task_setup", "python3 -c " + shlex.quote(seed_code))
    availability = guest_command(desktop, ["bash", "-lc", "soffice --version 2>&1"])
    if "LibreOffice" not in availability:
        raise SetupReadinessError(f"unexpected LibreOffice version response: {availability!r}",
                                  {"version_output": availability})
    initial_expected = {"writer_text": WRITER_DRAFT, "calc_cells": CALC_DRAFT,
                        "calc_sheet_names": ["Sheet1"]}
    initial_state = read_seeded_state(episode, desktop)
    shared_file_access = None
    if shared_backend:
        probe_code = (
            "import json,os,stat,tempfile; from pathlib import Path; "
            f"p=Path('{WRITER_PATH}'); d=p.parent; "
            "st=p.stat(); t=d/'.codesk-write-probe'; u=d/'.codesk-write-probe-renamed'; "
            "t.write_text('probe'); os.replace(t,u); u.unlink(); "
            "print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),"
            "'target_mode':stat.S_IMODE(st.st_mode),'target_uid':st.st_uid,"
            "'target_gid':st.st_gid,'target_write_access':os.access(p,os.W_OK),"
            "'directory_mode':stat.S_IMODE(d.stat().st_mode),"
            "'atomic_create_rename_delete':'pass'}))")
        try:
            shared_file_access = json.loads(guest_command(
                desktop, ["python3", "-c", probe_code]))
        except Exception as exc:
            raise SetupReadinessError("Guest could not create/rename/delete in shared backend",
                                      {"shared_backend_probe_error":
                                       f"{type(exc).__name__}: {exc}"}) from exc
        if not shared_file_access.get("target_write_access"):
            raise SetupReadinessError("shared backend task document is not writable in Guest",
                                      {"shared_backend_probe": shared_file_access})
    if initial_state != initial_expected:
        raise SetupReadinessError("seeded Flat ODF state does not match the task initial state",
                                  {"expected_initial_state": initial_expected,
                                   "actual_initial_state": initial_state})
    opened: list[dict[str, Any]] = []
    trace_io = os.environ.get("SWCUB_TRACE_OFFICE_IO") == "1"
    trace_binary = None
    if trace_io:
        trace_binary = guest_command(desktop, ["bash", "-lc", "command -v strace || true"]).strip()
        if not trace_binary:
            raise SetupReadinessError("SWCUB_TRACE_OFFICE_IO=1 but strace is not installed in Guest")
    trace_results: list[dict[str, Any]] = []
    for app in open_apps:
        flag = "--writer" if app == "writer" else "--calc"
        path = WRITER_PATH if app == "writer" else CALC_PATH
        soffice = (f"soffice --nologo --norestore --nofirststartwizard {flag} "
                   f"{shlex.quote(path)}")
        if trace_io:
            trace_prefix = f"/tmp/swcub-lo-{app}.trace"
            syscalls = ("openat,creat,truncate,ftruncate,rename,renameat,renameat2,"
                        "unlink,unlinkat,flock,fcntl,fsync,fdatasync,chmod,fchmod,fchmodat")
            soffice = (f"{shlex.quote(trace_binary)} -ff -ttt -s 256 -yy "
                       f"-e trace={syscalls} -o {shlex.quote(trace_prefix)} " + soffice)
        launch = f"{soffice} >/tmp/swcub_office/{app}-launch.log 2>&1 & sleep 7"
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
        app_ready = wait_for_app_document(episode, desktop, app, path, out)

        # Prove that the loaded document accepts GUI input and that the named
        # file remains the active document while a no-content save is persisted.
        setup_context = ActorContext("task_setup", episode, "gui")
        if app == "writer":
            setup_context.press_key("ctrl+end")
        else:
            setup_context.press_key("ctrl+home")
            setup_context.press_key("right")
            setup_context.press_key("down")
        setup_context.observe()
        probe_capture = _setup_capture(episode, out, f"{app}-interactive-probe", persist=True)
        if not _document_title_matches(probe_capture["active_window_title"], app, path):
            raise SetupReadinessError(
                f"{app} stopped being the active requested document during its GUI probe",
                {"app_ready": app_ready, "probe": probe_capture})
        setup_context.press_key("ctrl+s")
        episode.refresh_observation(source="task_setup")
        after_save_capture = _setup_capture(episode, out, f"{app}-after-noop-save", persist=True)
        persisted_state = read_seeded_state(episode, desktop)
        if (not _document_title_matches(after_save_capture["active_window_title"], app, path)
                or persisted_state != initial_expected):
            trace_result = (_capture_guest_office_trace(desktop, app, out)
                            if trace_io else {"enabled": False})
            trace_results.append(trace_result)
            raise SetupReadinessError(
                f"{app} no-op GUI save changed or lost the seeded document state",
                {"app_ready": app_ready, "probe": probe_capture,
                 "after_save": after_save_capture,
                 "shared_backend_access": shared_file_access,
                 "syscall_trace": trace_result,
                 "expected_initial_state": initial_expected,
                 "actual_persisted_state": persisted_state})
        if trace_io:
            trace_results.append(_capture_guest_office_trace(desktop, app, out))
        opened.append({"app": app, "document": Path(path).name,
                       "window_readiness": app_ready,
                       "interactive": True, "active_window_after_probe": probe_capture[
                           "active_window_title"],
                       "active_window_after_save": after_save_capture["active_window_title"],
                       "initial_state_persisted": True,
                       "calc_sheet_name": "Sheet1" if app == "calc" else None,
                       "calc_target_cell_navigation": "A1 -> B2 by Home, Right, Down"
                           if app == "calc" else None,
                       "screenshot_evidence": [f"{app}-interactive-probe.png",
                                               f"{app}-after-noop-save.png"]})
    return {"libreoffice_version": availability.strip(),
            "initial_state_verified": True, "opened_documents": opened,
            "shared_backend_access": shared_file_access,
            "syscall_trace": trace_results,
            "ready": len(opened) == len(open_apps)}


def condition_plan(condition: str) -> tuple[dict[str, str], dict[str, list[str]], list[str]]:
    if condition in {"solo", "ma_id"}:
        bindings = {"writer_actor": "writer_desktop", "calc_actor": "calc_desktop"}
        apps = {"writer_desktop": ["writer"], "calc_desktop": ["calc"]}
        schedule = ["writer_actor", "writer_actor", "calc_actor"]
    else:
        bindings = {"writer_actor": "shared_desktop", "calc_actor": "shared_desktop"}
        # Calc is deliberately opened first and Writer is initially foreground.
        apps = {"shared_desktop": ["calc", "writer"]}
        schedule = ["writer_actor", "calc_actor", "writer_actor"]
    return bindings, apps, schedule


def expected_states(condition: str, bindings: dict[str, str]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    if condition == "ma_sd":
        states = {"shared_desktop": {"writer_text": WRITER_FINAL,
                                      "calc_cells": CALC_FINAL}}
    else:
        states = {"writer_desktop": {"writer_text": WRITER_FINAL,
                                      "calc_cells": CALC_DRAFT},
                  "calc_desktop": {"writer_text": WRITER_DRAFT,
                                    "calc_cells": CALC_FINAL}}
    goals = {
        "writer_actor": {"desktop_binding": bindings["writer_actor"],
                         "field": "writer_text", "expected": WRITER_FINAL},
        "calc_actor": {"desktop_binding": bindings["calc_actor"],
                       "field": "calc_cells", "expected": CALC_FINAL},
    }
    return states, goals


def initial_states(bindings: dict[str, str]) -> dict[str, dict[str, Any]]:
    initial = {"writer_text": WRITER_DRAFT, "calc_cells": CALC_DRAFT}
    return {binding: dict(initial) for binding in sorted(set(bindings.values()))}


def is_guest_transport_error(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout, TimeoutError)):
        return True
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return type(status) is int and status >= 500


def run_actors(condition: str, environments: EpisodeBindings,
               actor_bindings: dict[str, str], schedule: list[str], log: EventLog,
               actor_implementation: str = "scripted",
               qwen_client: LocalQwenInferenceClient | None = None,
               out: Path | None = None) -> dict[str, Any]:
    recover_writer = condition != "ma_sd"
    if actor_implementation == "scripted":
        actors: dict[str, Any] = {
            "writer_actor": ScriptedWriterActor(recover_focus=recover_writer),
            "calc_actor": ScriptedCalcActor()}
    elif actor_implementation == "qwen3vl":
        if qwen_client is None or out is None:
            raise ValueError("Qwen actors require the shared local client and artifact path")
        prompts = {
            "writer_actor": (
                'In LibreOffice Writer, click inside the visible existing paragraph '
                '"Quarterly status report", replace the full document with exactly '
                '"Approved by GUI actor", and save. Do not edit the spreadsheet.'),
            "calc_actor": (
                'In LibreOffice Calc, change cell B2 from "Draft" to "Approved" and save. '
                'Keep all other cells unchanged and do not edit the Writer document.')}
        actors = {}

        actor_specs: dict[str, dict[str, Any]] = {}

        def record_model_step(record: dict[str, Any]) -> None:
            actor_id = str(record.get("actor_id", "unknown_actor"))
            binding = actor_bindings[actor_id]
            episode = environments[binding][0]
            state = episode.snapshot()
            log.record(actor_id, "model_decision", "osworld.qwen3vl.predict", state, state,
                       observed_revision=(record.get("observed_revision")
                           if type(record.get("observed_revision")) is int else None),
                       details={"desktop_binding": binding, **record})
            event = log.events[-1]
            record["event_seq"] = event.seq
            record["ts_utc"] = event.ts_utc

        for actor_id in ("writer_actor", "calc_actor"):
            agent = Qwen3VLAgent(
                platform="ubuntu", model="qwen3-vl", max_tokens=512,
                action_space="pyautogui", observation_type="screenshot",
                coordinate_type="relative")
            # Keep the official OSWorld planner, grounding, action schema and parser.
            agent.call_llm = lambda payload, model, client=qwen_client, aid=actor_id: \
                client.complete(payload, model, actor_id=aid)
            artifact_directory = out / "model-actors" / actor_id
            actors[actor_id] = OSWorldAgentActor(
                agent, prompts[actor_id], actor_id=actor_id,
                max_steps=MODEL_STEP_BUDGET, event_callback=record_model_step,
                artifact_directory=artifact_directory)
            actor_specs[actor_id] = {
                "actor_instance_id": str(uuid.uuid4()),
                "actor_id": actor_id,
                "task_goal": ("replace and save the Writer document" if actor_id == "writer_actor"
                              else "set Calc Sheet1 B2 to Approved and save"),
                "prompt": prompts[actor_id],
                "prompt_sha256": hashlib.sha256(prompts[actor_id].encode()).hexdigest(),
                "agent_class": type(agent).__name__,
                "history_n": agent.history_n,
                "action_budget": MODEL_STEP_BUDGET,
                "desktop_binding": actor_bindings[actor_id],
                "observation_directory": str(artifact_directory / "observations"),
                "debug_message_directory": str(artifact_directory / "draft" / "message_cache"),
            }
    else:
        raise ValueError(f"unknown actor implementation: {actor_implementation}")
    contexts = {actor_id: ActorContext(actor_id, environments[actor_bindings[actor_id]][0], "gui")
                for actor_id in actors}
    results: dict[str, dict[str, Any]] = {
        actor_id: {"success": True, "completed": False, "turns": 0,
                   "desktop_binding": actor_bindings[actor_id],
                   "environment_id": contexts[actor_id].environment_id}
        for actor_id in actors}
    turn_times_ms = {actor_id: 0.0 for actor_id in actors}
    environment_invalid = False
    environment_invalid_reason: str | None = None
    model_service_failure = False
    completed: set[str] = set()
    failed: set[str] = set()
    for turn_index, actor_id in enumerate(schedule, 1):
        if actor_id in completed or actor_id in failed:
            continue
        env = environments[actor_bindings[actor_id]][0]
        before = env.snapshot()
        log.record("coordinator", "schedule", "writer_calc.actor_turn_begin",
                   before, before, details={"actor_id": actor_id,
                       "desktop_binding": actor_bindings[actor_id],
                       "turn_index": turn_index, "schedule_index": turn_index - 1})
        turn_started = time.monotonic()
        try:
            step = getattr(actors[actor_id], "run_step", None)
            done = (bool(step(contexts[actor_id])) if callable(step)
                    else actors[actor_id].run(contexts[actor_id]) is None)
            results[actor_id]["turns"] += 1
            results[actor_id]["completed"] = done
            if done:
                completed.add(actor_id)
            log.record("orchestrator", "schedule", "writer_calc.actor_turn",
                       before, env.snapshot(), details={"actor_id": actor_id,
                           "desktop_binding": actor_bindings[actor_id],
                           "turn_index": turn_index, "schedule": schedule,
                           "completed": done})
        except Exception as exc:
            results[actor_id]["turns"] += 1
            results[actor_id]["success"] = False
            results[actor_id]["error"] = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, OSWorldAgentActorError):
                if exc.stage == "observation":
                    failure_class = "environment_invalid"
                    environment_invalid = True
                    environment_invalid_reason = "guest_observation_or_accessibility_failure"
                elif exc.stage == "model_inference":
                    failure_class = "model_service_failure"
                    model_service_failure = True
                elif exc.stage == "gui_action" and is_guest_transport_error(exc.cause):
                    failure_class = "environment_invalid"
                    environment_invalid = True
                    environment_invalid_reason = "guest_action_transport_failure"
                else:
                    failure_class = "model_action_execution_failure"
                results[actor_id]["failure_stage"] = exc.stage
            else:
                failure_class = "model_task_failure"
            results[actor_id]["failure_class"] = failure_class
            failed.add(actor_id)
            log.record(actor_id, "actor", "writer_calc.turn", before, env.snapshot(),
                       outcome="failed", details={"error": results[actor_id]["error"],
                                                  "failure_class": failure_class,
                                                  "desktop_binding": actor_bindings[actor_id]})
            if actor_implementation == "scripted" or environment_invalid or model_service_failure:
                break
        finally:
            turn_times_ms[actor_id] += (time.monotonic() - turn_started) * 1000
    for actor_id, result in results.items():
        if not result["completed"] and result["success"]:
            result["success"] = False
            result["error"] = "actor did not complete within its declared turn budget"
    if actor_implementation == "qwen3vl" and out is not None:
        traces = [record for actor in actors.values() for record in actor.trace]
        traces.sort(key=lambda record: record.get("event_seq", 0))
        trace_path = out / "model_trace.jsonl"
        trace_path.write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in traces),
            encoding="utf-8")
        for actor_id, actor in actors.items():
            results[actor_id].update({"agent": type(actor.agent).__name__,
                                      "model_steps": len(actor.trace),
                                      "step_budget": actor.max_steps,
                                      "actor_instance_id": actor_specs[actor_id][
                                          "actor_instance_id"],
                                      "actor_config": actor_specs[actor_id],
                                      "model_turn_elapsed_ms": round(
                                          turn_times_ms[actor_id], 2),
                                      "submitted_gui_action_count": sum(
                                          1 for event in log.events
                                          if event.actor == actor_id
                                          and event.kind == "gui"
                                          and event.action == "osworld.step"),
                                      "trace_file": trace_path.name})
        results["_episode_runtime"] = {"environment_invalid": environment_invalid,
                                       "environment_invalid_reason": environment_invalid_reason,
                                       "model_service_failure": model_service_failure,
                                       "schedule_turn_count": len(schedule),
                                       "schedule_policy": "round-robin one model decision per actor turn"}
    return results


def verify_ledger(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    created = {row["resource_id"] for row in rows
               if row.get("resource_type") == "container" and row.get("event") == "created"}
    destroyed = {row["resource_id"] for row in rows
                 if row.get("resource_type") == "container" and row.get("event") == "destroyed"}
    return {"container_count": len(created), "container_ids": sorted(created),
            "all_containers_have_destroy_record": bool(created) and created <= destroyed,
            "labels_consistent": all(
                row.get("labels", {}).get("org.swcub.project") == PROJECT_NAME
                for row in rows if row.get("resource_type") == "container")}


def write_provenance(out: Path, report: dict[str, Any]) -> None:
    artifacts = {}
    for path in sorted(out.rglob("*")):
        if (not path.is_file() or path.name == "provenance.json"
                or "overlays" in path.parts):
            continue
        artifacts[str(path.relative_to(out))] = sha256_file(path)
    source_files = [ROOT / "tasks/codesk_writer_calc_v1.json",
                    ROOT / "scripts/run_writer_calc_v1.py", ROOT / "swcub/actors.py",
                    ROOT / "swcub/evaluator.py", ROOT / "swcub/osworld_adapter.py",
                    ROOT / "swcub/osworld_readiness.py", ROOT / "swcub/comparison_metrics.py",
                    ROOT / "scripts/local_qwen_worker.py",
                    OSWORLD_V2_DIR / "mm_agents/qwen3vl_agent.py"]
    source_hashes = {source_path_label(path, ROOT, (("osworld-v2.1", OSWORLD_V2_DIR),)):
                     sha256_file(path)
                     for path in source_files if path.is_file()}
    manifest_path = ROOT / "outputs/osworld-v2.1/environment/release_manifest.json"
    ledger = out / "resource-events.jsonl"
    overlays = [{"path": str(path.relative_to(out)), "size_bytes": path.stat().st_size}
                for path in sorted((out / "overlays").rglob("*")) if path.is_file()]
    runtime = subprocess.run(["docker", "image", "inspect",
                              os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE",
                                  "swcub/osworld-v2.1-qemu-runtime:local")],
                             capture_output=True, text=True, check=False, timeout=20)
    runtime_id = None
    if runtime.returncode == 0:
        runtime_id = json.loads(runtime.stdout)[0].get("Id")
    task = json.loads((ROOT / "tasks/codesk_writer_calc_v1.json").read_text())
    provenance = {
        "metadata_schema_version": 1,
        "benchmark": {"name": "CoDesk", "suite": "CoDesk-V1-Real-App-Track-A", "suite_version": "1"},
        "task": {"task_id": TASK_ID, "task_version": TASK_VERSION,
                 "instance_id": task["instance_id"], "condition": report["condition"],
                 "repeat": report["repeat"], "schedule": report["schedule"]},
        "actors": report["actors"],
        "evaluator": {"class": "GuestLibreOfficeBindingEvaluator",
                       "hidden_state_access": "post_episode_only"},
        "environment": {"release": "osworld-v2.1", "guest_image": str(Path(os.environ.get(
            "SWCUB_OSWORLD_GUEST_IMAGE", OSWORLD_V2_DIR / "docker_vm_data/osworld-v2-ubuntu-x86.qcow2")).resolve()),
            "runtime_image": os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE",
                                             "swcub/osworld-v2.1-qemu-runtime:local"),
            "runtime_image_id": runtime_id,
            "release_manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
            "desktop_bindings": report["desktop_bindings"], "overlay_files": overlays,
            "workspace_topology": report.get("workspace_topology")},
        "resources": {"run_id": os.environ["SWCUB_RUN_ID"],
                       "owner_labels": {"org.swcub.project": PROJECT_NAME,
                           "org.swcub.run-id": os.environ["SWCUB_RUN_ID"],
                           "org.swcub.owner-token": os.environ["SWCUB_OWNER_TOKEN"]},
                       "ledger_path": str(ledger), "ledger_sha256": sha256_file(ledger),
                       "lifecycle": report["resource_lifecycle"]},
        "source": {"repository": git_source_state(), "sha256": source_hashes},
        "model": report.get("model"), "artifact_sha256": artifacts}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=("solo", "ma_id", "ma_sd"), required=True)
    parser.add_argument("--repeat", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    parser.add_argument("--actor-implementation", choices=("scripted", "qwen3vl"),
                        default="scripted")
    parser.add_argument("--backend-topology",
                        choices=("legacy_per_actor_clone", "same_workspace"),
                        default=os.environ.get("SWCUB_BACKEND_TOPOLOGY",
                                               "legacy_per_actor_clone"))
    args = parser.parse_args()
    out = args.artifact_parent.expanduser().resolve() / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "overlays").mkdir()
    same_workspace_backend = (
        args.backend_topology == "same_workspace"
        and args.condition in {"ma_id", "ma_sd"})
    workspace_backend_id = f"backend-{uuid.uuid4().hex[:16]}" if same_workspace_backend else None
    workspace_backend_host_dir = (out / "workspace-backend-task"
                                  if same_workspace_backend else None)
    owner = secrets.token_hex(32)
    if workspace_backend_host_dir is not None:
        write_backend_marker(workspace_backend_host_dir,
                             backend_id=workspace_backend_id or "",
                             run_id=args.run_id, condition=args.condition)
    ledger_path = out / "resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID": args.run_id, "SWCUB_OWNER_TOKEN": owner,
                       "SWCUB_RESOURCE_LEDGER": str(ledger_path),
                       "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger_path)
    (out / "run-owner-marker.json").write_text(json.dumps({
        "project": "CoDesk", "historical_project_label": PROJECT_NAME,
        "run_id": identity.run_id, "owner_token": owner,
        "purpose": "OSWorld V2.1 copy-on-write overlays for Writer/Calc Track A"}, indent=2) + "\n")

    started = utc_now()
    log = EventLog()
    environments = EpisodeBindings()
    model_worker: subprocess.Popen[bytes] | None = None
    qwen_client: LocalQwenInferenceClient | None = None
    report: dict[str, Any] = {"task_id": TASK_ID, "task_version": TASK_VERSION,
        "instance_id": "writer-calc-independent-edits-v1-seed0", "condition": args.condition,
        "repeat": args.repeat, "started_utc": started, "model": None,
        "actor_implementation": args.actor_implementation,
        "artifact_directory": str(out),
        "run_id": args.run_id, "resource_run_id": identity.run_id,
        "resource_ledger": str(ledger_path), "schedule": [], "actors": {},
        "desktop_bindings": {},
        "workspace_topology": {"mode": args.backend_topology,
            "backend_id": workspace_backend_id,
            "host_backend_path": (str(workspace_backend_host_dir)
                                  if workspace_backend_host_dir else None),
            "mount_transport": "qemu-9p" if workspace_backend_host_dir else None,
            "guest_mountpoint": GUEST_WORKSPACE_MOUNT if workspace_backend_host_dir else None},
        "setup_validation": {"ready": False,
            "apps": {}, "initial_state": None}}
    current_stage = "guest_startup"
    try:
        actor_bindings, apps_by_binding, schedule = condition_plan(args.condition)
        if args.actor_implementation == "qwen3vl":
            schedule = MODEL_INTERLEAVED_SCHEDULE.copy()
        report["schedule"] = schedule
        report["actor_bindings"] = actor_bindings
        if workspace_backend_host_dir is not None:
            seed_manifest = seed_shared_backend(workspace_backend_host_dir)
            report["workspace_topology"]["seed_manifest"] = seed_manifest
            log.record("task_setup", "backend_seed", "writer_calc.seed_shared_backend",
                       {"backend_empty": True}, seed_manifest,
                       details={"backend_id": workspace_backend_id,
                                "permissions": "task ODF files mode 0666"})
        for setup_index, (binding, apps) in enumerate(apps_by_binding.items()):
            episode, desktop = make_desktop(
                binding, log, out, workspace_backend_host_dir, workspace_backend_id)
            environments[binding] = (episode, desktop)
            current_stage = "application_setup"
            setup_result = seed_and_open(
                episode, desktop, apps, out,
                initialize_workspace=(workspace_backend_host_dir is None),
                shared_backend=(workspace_backend_host_dir is not None))
            report.setdefault("guest_app_versions", {})[binding] = setup_result[
                "libreoffice_version"]
            report["setup_validation"]["apps"][binding] = setup_result
            if setup_result.get("shared_backend_access"):
                report["setup_validation"]["shared_backend_guest_access"] = setup_result[
                    "shared_backend_access"]
        report["setup_validation"].update({"ready": True,
            "initial_state": initial_states(actor_bindings),
            "checks": ["named Writer/Calc active-window title",
                       "document is not opened read-only",
                       "GUI keyboard input accepted",
                       "Calc Sheet1/B2 navigation probe",
                       "no-op save preserved exact seeded Flat ODF state"],
            "shared_backend_guest_access": report.get("shared_backend_guest_access"),
            "shared_backend_initial_files": report["workspace_topology"].get(
                "seed_manifest")})
        initial_guest_ids = {binding: episode.snapshot().get("guest_container_id")
                             for binding, (episode, _desktop) in environments.items()}
        distinct_guest_ids = {guest_id for guest_id in initial_guest_ids.values() if guest_id}
        isolation_valid = (len(distinct_guest_ids) == (1 if args.condition == "ma_sd" else 2))
        report["desktop_isolation"] = {"valid": isolation_valid,
            "guest_container_ids": initial_guest_ids,
            "definition": ("one shared Guest desktop" if args.condition == "ma_sd"
                           else "separate Guest desktops")}
        if not isolation_valid:
            raise RuntimeError(f"desktop binding contract violated: {initial_guest_ids!r}")
        if workspace_backend_host_dir is not None:
            actor_sessions = {}
            for actor_id, binding in actor_bindings.items():
                episode = environments[binding][0]
                actor_sessions[actor_id] = {
                    "actor_id": actor_id,
                    "backend_id": workspace_backend_id,
                    "desktop_session_id": episode.environment_id}
            topology = validate_condition_topology(args.condition, {
                actor_id: __import__("swcub.shared_workspace", fromlist=["ActorSession"]).ActorSession(**values)
                for actor_id, values in actor_sessions.items()})
            report["workspace_topology"]["identity_check"] = topology
            report["workspace_topology"]["actor_bindings"] = actor_sessions
            log.record("coordinator", "topology_check", "writer_calc.same_backend_topology",
                       {"valid": False}, topology, details={
                           "backend_id": workspace_backend_id,
                           "condition": args.condition})
        if args.condition in {"solo", "ma_id"}:
            # Both clean independent desktops begin with their assigned app focused.
            # They share neither window state nor input; schedule order is deterministic.
            environments["writer_desktop"][0].refresh_observation("task_setup")
            environments["calc_desktop"][0].refresh_observation("task_setup")

        if args.actor_implementation == "qwen3vl":
            current_stage = "model_startup"
            remote_url = os.environ.get("SWCUB_QWEN_INFERENCE_URL", "").strip()
            if remote_url:
                from urllib.parse import urlsplit
                parsed = urlsplit(remote_url)
                if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
                        or not parsed.port or parsed.path not in {"", "/"}):
                    raise ValueError("remote Qwen URL must be an SSH-forwarded HTTP loopback endpoint")
                with urlopen(remote_url.rstrip("/") + "/health", timeout=10) as response:
                    model_metadata = json.loads(response.read())
                if (not model_metadata.get("ready")
                        or model_metadata.get("model") != "Qwen3-VL-30B-A3B-Instruct"):
                    raise RuntimeError("remote health did not identify the expected Qwen3-VL-30B-A3B model")
                inference_events_path = out / "remote_inference_events.jsonl"
                def record_remote_event(event: dict[str, Any]) -> None:
                    record = {"logged_unix_ns": time.time_ns(),
                              "client_host": socket.gethostname(), **event}
                    with inference_events_path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                qwen_client = LocalQwenInferenceClient(
                    endpoint=remote_url, event_callback=record_remote_event)
                report["model"] = {**model_metadata,
                    "inference_host": os.environ.get("SWCUB_QWEN_INFERENCE_HOST", "4090"),
                    "inference_transport": "SSH port forward to inference loopback",
                    "worker_sharing": "one remote inference process shared by two independent actor objects",
                    "worker_instance_id": model_metadata.get("worker_instance_id"),
                    "model_serving": "remote existing Qwen service"}
            else:
                model_worker, qwen_client, model_metadata = start_local_qwen_worker(out)
                report["model"] = model_metadata
        current_stage = "actor_execution"
        actors = run_actors(args.condition, environments, actor_bindings, schedule, log,
                            actor_implementation=args.actor_implementation,
                            qwen_client=qwen_client, out=out)
        actor_runtime = actors.pop("_episode_runtime", {})
        # Release model resources before hidden-state scoring and Guest reset.
        stop_local_qwen_worker(model_worker)
        model_worker = None
        if report.get("model"):
            report["model"].update({
                "steps_by_actor": {actor_id: actor.get("model_steps", 0)
                                   for actor_id, actor in actors.items()},
                "trace_file": "model_trace.jsonl"})
            report["model"]["scripted_fallback"] = False
        expected, goals = expected_states(args.condition, actor_bindings)
        initial = initial_states(actor_bindings)
        evaluator = GuestLibreOfficeBindingEvaluator(
            lambda binding, path: guest_command(environments[binding][1], ["cat", path]),
            expected, goals, initial)
        grading = evaluator.evaluate()
        log.record("evaluator", "evaluation", "writer_calc.exact_odf_state",
                   {"bindings": sorted(environments)}, grading,
                   outcome="pass" if grading["success"] else "fail",
                   details={"hidden_state_access": "post_episode_only"})
        final_odf_files = save_final_odf_artifacts(environments, out)
        log.record("evaluator", "artifact", "writer_calc.final_odf_export",
                   {"bindings": sorted(environments)}, final_odf_files,
                   details={"post_episode_only": True,
                            "contains_evaluator_visible_final_documents": True})
        focus_by_binding = {
            binding: summarize_focus_events([event for event in log.events
                if event.details.get("environment_id") == episode.environment_id])
            for binding, (episode, _desktop) in environments.items()}
        focus = {
            "by_desktop_binding": focus_by_binding,
            "switches_observed_between_gui_actions": sum(
                item["switches_observed_between_gui_actions"] for item in focus_by_binding.values()),
            "recovery_action_count": sum(item["recovery_action_count"]
                                          for item in focus_by_binding.values()),
            "focus_mismatch_action_count": sum(item["focus_mismatch_action_count"]
                                                for item in focus_by_binding.values()),
            "unintended_focus_action_count": sum(item["unintended_focus_action_count"]
                                                 for item in focus_by_binding.values()),
            "mis_input_action_count": sum(item["mis_input_action_count"]
                                           for item in focus_by_binding.values()),
            "unknown_input_action_count": sum(item["unknown_input_action_count"]
                                              for item in focus_by_binding.values()),
            "mis_input_actions": [row for item in focus_by_binding.values()
                                  for row in item["mis_input_actions"]],
            "unknown_input_actions": [row for item in focus_by_binding.values()
                                      for row in item["unknown_input_actions"]],
            "focus_events": [row for item in focus_by_binding.values()
                             for row in item["focus_events"]]}
        activations = [{"seq": event.seq, "actor_id": event.actor,
                        "before": event.details.get("active_window_before"),
                        "after": event.details.get("active_window_after"),
                        "desktop_binding": actor_bindings.get(event.actor)}
                       for event in log.events if event.kind == "gui"
                       and event.details.get("active_window_before")
                       != event.details.get("active_window_after")]
        misinputs = focus.get("mis_input_actions", [])
        shared_interference = False
        if args.condition == "ma_sd":
            shared_interference = (
                not grading["success"] and bool(misinputs)
                and bool(grading.get("contamination_events")))
            if args.actor_implementation == "scripted":
                # Keep the frozen scripted negative-control interpretation.
                scenario_success = bool(shared_interference)
                outcome = ("shared_focus_interference_attributed" if shared_interference
                           else "expected_interference_not_attributed")
            else:
                scenario_success = bool(grading["success"])
                outcome = ("all_actor_goals_met" if scenario_success else
                           "shared_focus_interference_supported" if shared_interference else
                           "actor_goal_failure_without_attributed_interference")
        else:
            scenario_success = bool(grading["success"] and all(
                item.get("success") for item in grading["actor_goal_success"].values()))
            outcome = "all_isolated_goals_met" if scenario_success else "isolated_goal_failure"
        if args.actor_implementation == "qwen3vl":
            if actor_runtime.get("environment_invalid") or actor_runtime.get(
                    "model_service_failure"):
                outcome = "environment_invalid"
            report["episode_validity"] = {
                "valid_for_agent_success_rate": not (
                    actor_runtime.get("environment_invalid", False)
                    or actor_runtime.get("model_service_failure", False)),
                "reason": (actor_runtime.get("environment_invalid_reason")
                           if actor_runtime.get("environment_invalid") else
                           "local_model_service_failure"
                           if actor_runtime.get("model_service_failure") else None),
            }
            if actor_runtime.get("environment_invalid") or actor_runtime.get(
                    "model_service_failure"):
                scenario_success = False
        else:
            report["episode_validity"] = {
                "valid_for_agent_success_rate": True,
                "reason": None,
            }
        report.update({"actors": actors, "evaluation": grading,
            "final_odf_files": final_odf_files,
            "focus_metrics": focus, "focus_transitions": focus.get("focus_events", []),
            "window_activation_events": activations,
            "keyboard_routing": focus.get("mis_input_actions", [])
                                + focus.get("unknown_input_actions", []),
            "contamination_events": grading.get("contamination_events", []),
            "failure_attribution": {"task_state_failure": not grading["success"],
                "focus_input_conflict": bool(misinputs),
                "misrouted_input_count": len(misinputs),
                "unknown_route_count": focus.get("unknown_input_action_count", 0),
                "cross_actor_stale_observations": sum(
                    1 for event in log.events if event.kind == "gui"
                    and event.details.get("stale_due_other_actor") is True)},
            "scenario_success": scenario_success, "scenario_outcome": outcome,
            "schedule_protocol": {"policy": actor_runtime.get("schedule_policy",
                    "scripted fixed schedule"), "planned_turn_slots": len(schedule),
                    "submitted_turn_count": sum(
                        1 for event in log.events
                        if event.action == "writer_calc.actor_turn"),
                    "model_decision_budget_per_actor": MODEL_STEP_BUDGET
                        if args.actor_implementation == "qwen3vl" else None,
                    "actions_submitted_serially": True},
            "desktop_bindings": {binding: {"environment_id": episode.environment_id,
                "guest_container_id": episode.snapshot().get("guest_container_id")}
                for binding, (episode, _) in environments.items()}})
        if report.get("model"):
            model_actor_errors = {actor_id: result.get("error")
                                  for actor_id, result in actors.items()
                                  if result.get("error")}
            if actor_runtime.get("environment_invalid"):
                report["model_failure_class"] = next((
                    result.get("failure_class") for result in actors.values()
                    if result.get("failure_class")), "environment_invalid")
            elif actor_runtime.get("model_service_failure"):
                report["model_failure_class"] = "model_service_failure"
            elif grading["success"]:
                report["model_failure_class"] = "none"
            elif shared_interference:
                report["model_failure_class"] = "shared_desktop_interference_supported"
            elif model_actor_errors:
                report["model_failure_class"] = next((
                    result.get("failure_class") for result in actors.values()
                    if result.get("failure_class")), "model_task_failure")
            else:
                report["model_failure_class"] = "unattributed_goal_failure"
            report["model_actor_errors"] = model_actor_errors
        report["environment_health"] = {binding: dict(episode.environment_health)
                                         for binding, (episode, _) in environments.items()}
        for binding, (episode, _) in environments.items():
            episode.copy_artifacts(out / "screenshots" / binding)

        reset_rows = {}
        reset_success = True
        reset_backend_host_dir = None
        reset_backend_id = None
        workspace_env_key = "SWCUB_OSWORLD_SHARED_WORKSPACE_HOST_DIR"
        prior_workspace_env = os.environ.get(workspace_env_key)
        if workspace_backend_host_dir is not None:
            reset_backend_host_dir = out / "workspace-backend-reset"
            reset_backend_id = f"backend-{uuid.uuid4().hex[:16]}"
            write_backend_marker(reset_backend_host_dir, backend_id=reset_backend_id,
                                 run_id=args.run_id, condition=args.condition,
                                 generation="reset")
            os.environ[workspace_env_key] = str(reset_backend_host_dir.resolve())
            report["workspace_topology"]["reset_backend_id"] = reset_backend_id
        for binding, (episode, desktop) in environments.items():
            before = episode.snapshot()
            old_id = before.get("guest_container_id")
            episode.reset(task_config=None)
            wait_for_guest_desktop(episode, desktop, timeout=300, retry_interval=5)
            if reset_backend_host_dir is not None:
                guest_command(desktop, ["bash", "-lc", guest_mount_command(sudo_password=desktop.client_password)], timeout=60)
            clean = guest_command(desktop, ["bash", "-lc",
                f"test ! -e {WRITER_PATH} && test ! -e {CALC_PATH} && echo reset-clean"])
            fresh_id = episode.snapshot().get("guest_container_id")
            binding_ok = clean.strip() == "reset-clean" and bool(old_id) and old_id != fresh_id
            reset_success = reset_success and binding_ok
            log.record("evaluator", "reset_check", "writer_calc.clean_reset",
                       before, episode.snapshot(), outcome="pass" if binding_ok else "fail",
                       details={"desktop_binding": binding, "previous_guest_container_id": old_id,
                                "new_guest_container_id": fresh_id,
                                "task_files_absent": clean.strip() == "reset-clean"})
            reset_rows[binding] = {"success": binding_ok, "task_files_absent": clean.strip() == "reset-clean",
                                   "previous_guest_container_id": old_id,
                                   "new_guest_container_id": fresh_id}
            episode.copy_artifacts(out / "reset-check" / binding)
        report["reset_check"] = {"success": reset_success, "desktops": reset_rows}
        if prior_workspace_env is None:
            os.environ.pop(workspace_env_key, None)
        else:
            os.environ[workspace_env_key] = prior_workspace_env

        current_stage = "resource_finalization"
        for binding, (episode, _) in environments.items():
            episode.close()
        environments.clear()
        report["resource_lifecycle"] = verify_ledger(ledger_path)
        report["finished_utc"] = utc_now()
        report["elapsed_seconds"] = round((datetime.fromisoformat(report["finished_utc"])
                                            - datetime.fromisoformat(started)).total_seconds(), 3)
        report["success"] = bool(scenario_success and reset_success and isolation_valid
                                 and report["resource_lifecycle"]["all_containers_have_destroy_record"]
                                 and report["resource_lifecycle"]["labels_consistent"])
        report["provenance_status"] = "complete"
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        log.write(out / "events.jsonl")
        try:
            write_provenance(out, report)
        except Exception as provenance_error:
            # Provenance finalization is a separate integrity stage. Preserve
            # the completed task/evaluator report instead of relabeling it as
            # an actor or episode runtime failure.
            report["provenance_status"] = "failed"
            report["provenance_error"] = (
                f"{type(provenance_error).__name__}: {provenance_error}")
            (out / "report.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
            (out / "provenance-error.txt").write_text(
                report["provenance_error"] + "\n", encoding="utf-8")
            log.record("provenance", "finalization_error", "episode.provenance",
                       {"status": "pending"}, {"status": "failed"}, outcome="failed",
                       details={"error": report["provenance_error"]})
            log.write(out / "events.jsonl")
            print(json.dumps({"condition": args.condition, "repeat": args.repeat,
                              "scenario_success": scenario_success,
                              "reset_success": reset_success,
                              "provenance_status": "failed",
                              "artifact_dir": str(out),
                              "episode_seconds": report["elapsed_seconds"]}))
            return 3
        print(json.dumps({"condition": args.condition, "repeat": args.repeat,
                          "scenario_success": scenario_success, "reset_success": reset_success,
                          "provenance_status": "complete", "artifact_dir": str(out),
                          "episode_seconds": report["elapsed_seconds"]}))
        return 0 if report["success"] else 1
    except (Exception, KeyboardInterrupt) as exc:
        stop_local_qwen_worker(model_worker)
        model_worker = None
        is_setup_failure = current_stage in {"guest_startup", "application_setup"}
        report["finished_utc"] = utc_now()
        report["error"] = f"{type(exc).__name__}: {exc}"
        interrupted = isinstance(exc, KeyboardInterrupt)
        report["episode_status"] = ("operator_interrupted" if interrupted else
                                     "readiness_failed" if is_setup_failure else
                                     "runtime_failed")
        report["failure_stage"] = current_stage
        report["episode_validity"] = {"valid_for_agent_success_rate": False,
                                       "reason": report["episode_status"]}
        if args.actor_implementation == "qwen3vl":
            report["model_failure_class"] = (
                "model_service_failure" if current_stage == "model_startup" else
                "environment_readiness_failure"
                if current_stage in {"guest_startup", "application_setup"} else
                "runner_or_environment_failure")
        if isinstance(exc, SetupReadinessError):
            report["setup_failure_diagnostics"] = exc.diagnostics
        for binding, (episode, desktop) in list(environments.items()):
            try:
                episode.copy_artifacts(out / "setup-failure-screenshots" / binding)
                report.setdefault("setup_failure_observations", {})[binding] = {
                    "active_window_title": episode._active_window_title(),
                    "environment_health": dict(episode.environment_health),
                    "guest_container_id": episode.snapshot().get("guest_container_id")}
                try:
                    report["setup_failure_observations"][binding]["saved_initial_state"] = (
                        read_seeded_state(episode, desktop))
                except Exception as state_error:
                    report["setup_failure_observations"][binding]["state_read_error"] = (
                        f"{type(state_error).__name__}: {state_error}")
            except Exception as capture_error:
                report.setdefault("evidence_capture_errors", []).append(
                    f"{binding}: {type(capture_error).__name__}: {capture_error}")
        log.record("task_setup" if is_setup_failure else "orchestrator", "episode_error",
                   "writer_calc.episode_abort", {"stage": current_stage},
                   {"status": report["episode_status"], "error": report["error"]},
                   outcome=report["episode_status"],
                   details={"setup_failure_diagnostics": report.get(
                       "setup_failure_diagnostics", {})})
        for episode, _desktop in environments.values():
            try:
                episode.close()
            except Exception:
                pass
        environments.clear()
        try:
            report["resource_lifecycle"] = verify_ledger(ledger_path)
        except Exception as ledger_error:
            report["resource_lifecycle"] = {"verification_error":
                f"{type(ledger_error).__name__}: {ledger_error}"}
        (out / "error.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        log.write(out / "events.jsonl")
        try:
            report["provenance_status"] = "complete"
            (out / "error.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            write_provenance(out, report)
        except Exception as provenance_error:
            report["provenance_status"] = "failed"
            (out / "provenance-error.txt").write_text(
                f"{type(provenance_error).__name__}: {provenance_error}\n", encoding="utf-8")
            (out / "error.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 130 if interrupted else 2 if is_setup_failure else 1
    finally:
        stop_local_qwen_worker(model_worker)
        for episode, _desktop in environments.values():
            try:
                episode.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

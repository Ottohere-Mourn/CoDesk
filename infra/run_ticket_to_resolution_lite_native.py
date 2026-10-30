#!/usr/bin/env python3
"""Run native-QEMU controls or screenshot-driven Ticket-to-Resolution Lite episodes."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import quote

import requests

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

OSWORLD = Path("/opt/data/private/mjh/OSWorld-V2")
IMAGE = Path("/opt/data/private/mjh/deps/osworld/images/osworld-v2-ubuntu-x86.qcow2")
QEMU_PREFIX = Path("/opt/data/private/mjh/deps/qemu/jammy-6.2/root")
MODEL_CONFIG = Path("/opt/data/private/mjh/secrets/codesk-gui-pilot.json")
RUNS = Path("/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite")
MODEL = "gpt-6.1-sol"
MODEL_RELAY_OUTPUT_BUDGET = 12000
GUEST_SERVICE_PORT = 8765
GUEST_SERVICE_HOST = "10.0.2.100"
VCPUS = 4
RAM = "6G"
BASE_IMAGE_SHA256 = "28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a"
BASE_IMAGE_SIZE = 14891810816
GUEST_CAPTURE_SHA256 = "915cc325a5cc14ae47aa89fc83ba09da0b64ad742374b161a10666f5d1648273"


def _write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)
    path.chmod(mode)


def _append(path: Path, value: dict[str, Any], lock: threading.Lock | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    context = lock if lock is not None else nullcontext()
    with context, path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _image_fingerprint() -> dict[str, int]:
    stat = IMAGE.stat()
    if stat.st_size != BASE_IMAGE_SIZE:
        raise RuntimeError("OSWorld Guest image size changed from the fully hashed baseline")
    return {"device": stat.st_dev, "inode": stat.st_ino, "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns}


def _process_metrics(pid: int | None) -> dict[str, Any]:
    if not pid:
        return {"alive": False}
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().split()
        ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        status = Path(f"/proc/{pid}/status").read_text()
        result: dict[str, Any] = {
            "pid": pid,
            "alive": True,
            "cpu_user_s": round(int(stat[13]) / ticks, 2),
            "cpu_system_s": round(int(stat[14]) / ticks, 2),
        }
        for name in ("VmRSS", "VmHWM"):
            match = re.search(rf"^{name}:\s+(\d+)\s+kB$", status, re.M)
            if match:
                result[name.lower() + "_mib"] = round(int(match.group(1)) / 1024, 1)
        return result
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
        return {"pid": pid, "alive": False}


def _bypass_proxy_for_local_services() -> None:
    for name in ("NO_PROXY", "no_proxy"):
        values = [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]
        for local in ("127.0.0.1", "localhost", "::1", GUEST_SERVICE_HOST):
            if local not in values:
                values.append(local)
        os.environ[name] = ",".join(values)


class ObservedGuest:
    """Forward one Actor's desktop calls while recording input, focus, and returned screenshots."""

    def __init__(self, actor: str, guest_key: str, guest: Any, root: Path,
                 input_lock: threading.Lock | None = None):
        self.actor = actor
        self.guest_key = guest_key
        self.guest = guest
        self.root = root
        self.input_lock = input_lock
        self.log = root / "desktop_requests.jsonl"
        self.log_lock = threading.Lock()
        self.image_count = 0
        self.image_lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def do_GET(self):
                self._forward()

            def do_POST(self):
                self._forward()

            def _forward(self):
                body = None
                if self.command == "POST":
                    body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                code = ""
                if self.path.split("?", 1)[0] == "/execute" and body:
                    try:
                        command = json.loads(body).get("command", [])
                        if isinstance(command, list) and command:
                            code = str(command[-1])
                    except (ValueError, TypeError):
                        pass
                gui_input = self.command == "POST" and self.path.split("?", 1)[0] == "/execute" and any(
                    marker in code for marker in (
                        "pyautogui.click", "pyautogui.write", "pyautogui.press",
                        "pyautogui.hotkey", "pyautogui.moveTo", "pyautogui.scroll"))
                row = {
                    "actor": outer.actor,
                    "guest_key": outer.guest_key,
                    "method": self.command,
                    "path": self.path.split("?", 1)[0],
                    "started_unix": time.time(),
                    "gui_input": gui_input,
                    "window_samples_atomic": False,
                }
                if gui_input:
                    row["code"] = code
                lock_context = outer.input_lock if gui_input and outer.input_lock else nullcontext()
                queued_at = time.monotonic()
                try:
                    with lock_context:
                        row["input_lock_wait_s"] = round(time.monotonic() - queued_at, 4)
                        if gui_input:
                            row["focus_before"] = outer._focus()
                        upstream = requests.request(
                            self.command, outer.guest.url + self.path, data=body,
                            headers={key: self.headers[key] for key in ("Content-Type", "Authorization")
                                     if key in self.headers},
                            timeout=(15, 180))
                        row["response_status"] = upstream.status_code
                        row["forward_finished_unix"] = time.time()
                        if gui_input:
                            row["focus_after"] = outer._focus()
                        if "image/png" in upstream.headers.get("Content-Type", "") or upstream.content.startswith(b"\x89PNG"):
                            row["screenshot"] = outer._save_screenshot(upstream.content)
                        self.send_response(upstream.status_code)
                        self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/octet-stream"))
                        self.send_header("Content-Length", str(len(upstream.content)))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(upstream.content)
                except Exception as exc:
                    row["error_type"] = type(exc).__name__
                    try:
                        self.send_error(502, "Guest forwarding failed")
                    except OSError:
                        pass
                finally:
                    row["finished_unix"] = time.time()
                    _append(outer.log, row, outer.log_lock)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def _focus(self) -> dict[str, Any]:
        try:
            result = self.guest.execute([
                "bash", "-lc",
                "printf 'ACTIVE='; xdotool getactivewindow getwindowname 2>/dev/null || true; "
                "printf 'WINDOWS_BEGIN\\n'; wmctrl -lpGx 2>/dev/null || true; printf 'WINDOWS_END\\n'",
            ], timeout=15)
            return {"at_unix": time.time(), "output": result.get("output", ""),
                    "status": result.get("status")}
        except Exception as exc:
            return {"at_unix": time.time(), "error_type": type(exc).__name__}

    def _save_screenshot(self, payload: bytes) -> dict[str, Any]:
        with self.image_lock:
            self.image_count += 1
            target = self.root / "screenshots" / self.actor / f"desktop-{self.image_count:04d}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        return {"path": str(target.relative_to(self.root)), "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest()}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


def _input_overlap(path: Path) -> dict[str, Any]:
    events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    inputs = [row for row in events if row.get("gui_input")]
    overlaps = []
    focus_changes = []
    for index, current in enumerate(inputs):
        before = current.get("focus_before", {}).get("output")
        after = current.get("focus_after", {}).get("output")
        if before and after and before != after:
            focus_changes.append(index)
        for prior_index, prior in enumerate(inputs[:index]):
            same_guest = current.get("guest_key") == prior.get("guest_key")
            overlaps_time = max(current["started_unix"], prior["started_unix"]) < min(
                current.get("finished_unix", current["started_unix"]),
                prior.get("finished_unix", prior["started_unix"]))
            if same_guest and current["actor"] != prior["actor"] and overlaps_time:
                overlaps.append([prior_index, index])
    return {
        "gui_input_count": len(inputs),
        "cross_actor_same_guest_overlap_pairs": overlaps,
        "focus_changed_during_input_indices": focus_changes,
        "window_sampling_atomic": False,
        "focus_or_misrouting_requires_screenshot_review": True,
    }


def _load_model_config() -> tuple[dict[str, Any], dict[str, Any]]:
    if MODEL_CONFIG.is_symlink() or not MODEL_CONFIG.is_file():
        raise FileNotFoundError(f"private model configuration is unavailable: {MODEL_CONFIG}")
    if MODEL_CONFIG.stat().st_mode & 0o077:
        raise PermissionError("private model configuration permissions must be 0600")
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    required = ("api_key", "base_url", "fallback_base_url")
    if any(not isinstance(config.get(key), str) or not config[key] for key in required):
        raise ValueError("private model configuration is incomplete")
    expected = {
        "base_url": "https://api.haogpt.net/v1",
        "fallback_base_url": "https://docode.cc/v1",
    }
    for key, value in expected.items():
        if config[key].rstrip("/") != value:
            raise ValueError(f"configured {key} does not match the requested endpoint")
    safe = {"model_requested": MODEL, "configured_model": config.get("model"),
            "preferred_endpoint": expected["base_url"], "fallback_endpoint": expected["fallback_base_url"]}
    return config, safe


def _probe_model_catalog(config: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for label, base in (("preferred", config["base_url"]), ("fallback", config["fallback_base_url"])):
        started = time.monotonic()
        try:
            response = requests.get(
                base.rstrip("/") + "/models",
                headers={"Authorization": "Bearer " + config["api_key"]},
                timeout=(8, 20))
            model_ids = []
            if response.ok:
                body = response.json()
                model_ids = [item["id"] for item in body.get("data", [])
                             if isinstance(item, dict) and isinstance(item.get("id"), str)]
            rows.append({
                "endpoint": label, "http_status": response.status_code,
                "elapsed_s": round(time.monotonic() - started, 3),
                "requested_model_listed": MODEL in model_ids,
                "matching_model_ids": [item for item in model_ids if "6.1" in item.lower() or "sol" in item.lower()],
            })
        except Exception as exc:
            rows.append({"endpoint": label, "error_type": type(exc).__name__,
                         "elapsed_s": round(time.monotonic() - started, 3)})
    return {"model": MODEL, "endpoints": rows,
            "pass": len(rows) == 2 and all(row.get("requested_model_listed") for row in rows)}


def _start_model_relay(root: Path, role: str, config: dict[str, Any]) -> tuple[subprocess.Popen, str, str]:
    from_env = f"CODESK_TTR_LITE_UPSTREAM_{role}"
    token_env = f"CODESK_TTR_LITE_RELAY_{role}"
    token = secrets.token_urlsafe(32)
    os.environ[token_env] = token
    os.environ[from_env] = config["api_key"]
    folder = root / "model_relays" / role
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    ready_path = folder / "ready.json"
    event_path = folder / "events.jsonl"
    command = [
        sys.executable, "-m", "oscombo.responses_tool_image_relay",
        "--upstream", config["base_url"],
        "--fallback-upstream", config["fallback_base_url"],
        "--api-key-env", from_env,
        "--client-token-env", token_env,
        "--ready-file", str(ready_path),
        "--event-log", str(event_path),
        "--output-token-budget", str(MODEL_RELAY_OUTPUT_BUDGET),
        "--size-aware-upload-timeout",
    ]
    relay_env = os.environ.copy()
    relay_env[from_env] = config["api_key"]
    relay_env[token_env] = token
    log = (folder / "relay.log").open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=PROJECT, env=relay_env, stdout=log,
                               stderr=subprocess.STDOUT, start_new_session=True)
    log.close()
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("model relay exited before readiness")
            if ready_path.is_file():
                ready = json.loads(ready_path.read_text(encoding="utf-8"))
                if ready.get("pid") == process.pid and ready.get("host") == "127.0.0.1":
                    os.environ.pop(from_env, None)
                    return process, f"http://127.0.0.1:{ready['port']}/v1", token_env
            time.sleep(0.2)
        raise TimeoutError("model relay readiness timed out")
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        os.environ.pop(from_env, None)
        os.environ.pop(token_env, None)
        raise


def _configure_native_environment(root: Path, run_id: str, app_host_port: int) -> None:
    os.environ.update({
        "OSWORLD_DIR": str(OSWORLD),
        "OSCOMBO_BACKEND": "native-qemu-tcg",
        "OSCOMBO_NATIVE_RAM": RAM,
        "OSCOMBO_NATIVE_CPUS": str(VCPUS),
        "OSCOMBO_NATIVE_BOOT_TIMEOUT": "900",
        "OSCOMBO_NATIVE_STOP_TIMEOUT": "30",
        "OSCOMBO_QEMU_PREFIX": str(QEMU_PREFIX),
        "OSCOMBO_QEMU": str(QEMU_PREFIX / "bin" / "qemu-system-x86_64"),
        "OSCOMBO_QEMU_IMG": str(QEMU_PREFIX / "bin" / "qemu-img"),
        "OSCOMBO_QEMU_PRIVATE_LOADER": "1",
        "OSCOMBO_RUN_LABEL": run_id,
        "OSCOMBO_NATIVE_STATE_DIR": str(root / "native-qemu"),
        "OSCOMBO_NATIVE_PORT_LOCK": str(root / "native-qemu" / "ports.lock"),
        "OSCOMBO_STAGE_TMPDIR": str(root / "host-stage"),
        "OSCOMBO_NATIVE_GUESTFWD": json.dumps([
            {"guest_port": GUEST_SERVICE_PORT, "host_port": app_host_port}]),
    })


def _focus_sample(guest: Any) -> dict[str, Any]:
    try:
        result = guest.execute(["bash", "-lc", "xdotool getactivewindow getwindowname 2>/dev/null || true"], 15)
        return {"at_unix": time.time(), "title": result.get("output", "").strip()}
    except Exception as exc:
        return {"at_unix": time.time(), "error_type": type(exc).__name__}


def _screenshot(guest: Any, path: Path) -> dict[str, Any]:
    from io import BytesIO
    from PIL import Image
    from oscombo.desktop_tools import frame_content

    payload = guest.screenshot(patience=45)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    with Image.open(BytesIO(payload)) as image:
        return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload), "size": [image.width, image.height],
                **frame_content(image)}


def _resource_diagnostics_command(profile: str) -> str:
    """Return bounded Guest memory, process-limit, and direct cgroup probes."""
    nl = chr(10)
    cgroup_probe = nl.join((
        "from pathlib import Path",
        "group = Path('/sys/fs/cgroup')",
        "for line in Path('/proc/self/cgroup').read_text().splitlines():",
        "    fields = line.split(':', 2)",
        "    if len(fields) != 3:",
        "        continue",
        "    hierarchy, controllers, relative = fields",
        "    relative = relative.lstrip('/')",
        "    if hierarchy == '0' and not controllers:",
        "        group = Path('/sys/fs/cgroup') / relative",
        "        break",
        "    if 'memory' in controllers.split(','):",
        "        group = Path('/sys/fs/cgroup/memory') / relative",
        "print('CGROUP_MEMORY_DIR=' + str(group))",
        "for name in ('memory.events', 'memory.oom_control', 'memory.failcnt',",
        "             'memory.max_usage_in_bytes', 'memory.usage_in_bytes',",
        "             'memory.current', 'memory.max', 'pids.current', 'pids.max',",
        "             'pids.events'):",
        "    path = group / name",
        "    try:",
        "        value = path.read_text().strip()",
        "    except OSError:",
        "        continue",
        "    print(name + ':')",
        "    print(value)",
    ))
    return (
        "printf 'RESOURCE_DIAGNOSTICS_BEGIN\\n'; free -h 2>&1 || true; "
        "df -h /tmp /dev/shm 2>&1 || true; "
        "grep -E 'MemTotal|MemAvailable|MemFree|SwapFree' /proc/meminfo 2>/dev/null || true; "
        "printf 'PROCESS_LIMITS_BEGIN\\n'; printf 'ulimit_user='; ulimit -u; printf 'ulimit_nofile='; ulimit -n; "
        "printf 'process_count='; ps -e --no-headers 2>/dev/null | wc -l; "
        "printf 'user_process_count='; ps -u 1000 --no-headers 2>/dev/null | wc -l; "
        "printf 'threads_max='; cat /proc/sys/kernel/threads-max 2>/dev/null || true; "
        "printf 'pid_max='; cat /proc/sys/kernel/pid_max 2>/dev/null || true; "
        "printf 'CGROUP_PATHS\\n'; cat /proc/self/cgroup 2>&1 || true; "
        "python3 - <<'PYCGROUP'" + nl + cgroup_probe + nl + "PYCGROUP" + nl
        + "printf 'MEMORY_PRESSURE_BEGIN\\n'; cat /proc/pressure/memory 2>&1 || true; printf 'MEMORY_PRESSURE_END\\n'; "
        + f"find {shlex.quote(profile)}/Crashpad -maxdepth 3 -type f -printf '%P %s bytes\\n' 2>/dev/null | tail -n 20; "
        + "printf 'RESOURCE_DIAGNOSTICS_END\\n'"
    )


def _wait_for_guest_desktop(guest: Any, run_root: Path, key: str,
                            report: dict[str, Any], timeout: float = 900) -> dict[str, Any]:
    from io import BytesIO
    from PIL import Image
    from oscombo.desktop_tools import frame_content

    started = time.monotonic()
    deadline = started + timeout
    samples = []
    index = 0
    while time.monotonic() < deadline:
        path = run_root / "screenshots" / "setup" / f"{key}-desktop-readiness-{index:02d}.png"
        try:
            payload = guest.screenshot(patience=45)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            with Image.open(BytesIO(payload)) as image:
                evidence = {"path": str(path.relative_to(run_root)),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "bytes": len(payload), "size": [image.width, image.height],
                            **frame_content(image)}
        except Exception as exc:
            evidence = {"error_type": type(exc).__name__, "error": str(exc)[:500]}
        evidence["time_unix"] = time.time()
        evidence["elapsed_s"] = round(time.monotonic() - started, 2)
        samples.append(evidence)
        report["desktop_readiness"] = {"guest_key": key, "timeout_s": timeout,
                                        "samples": samples, "ready": bool(evidence.get("content_ready"))}
        report["status"] = "GUEST_DESKTOP_STARTUP"
        report["stage"] = f"waiting_for_visible_desktop_{key}"
        _write_json(run_root / "progress.json", report)
        if evidence.get("content_ready"):
            return report["desktop_readiness"]
        index += 1
        time.sleep(min(30, max(0, deadline - time.monotonic())))
    report["desktop_readiness"] = {"guest_key": key, "timeout_s": timeout,
                                    "samples": samples, "ready": False}
    _write_json(run_root / "progress.json", report)
    raise TimeoutError(f"Guest {key} desktop stayed black/flat for {timeout:.0f}s")


def _apply_guest_png_fix(guest: Any, run_root: Path, run_id: str, key: str) -> dict[str, Any]:
    evidence_dir = run_root / "guest_runtime" / key
    evidence_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    source = guest.execute(["sha256sum", "/home/user/server/src/capture.py"], timeout=15)
    actual_sha = (source.get("output", "").split() or [None])[0]
    if source.get("returncode", 0) != 0 or actual_sha != GUEST_CAPTURE_SHA256:
        result = {"status": "not_applied", "observed_guest_capture_sha256": actual_sha,
                  "expected_audited_sha256": GUEST_CAPTURE_SHA256,
                  "reason": "Guest screenshot source does not match the audited original"}
        _write_json(evidence_dir / "png-fix-result.json", result)
        return result

    helper = PROJECT / "infra" / "fix_guest_png_encoding.py"
    if not helper.is_file():
        raise FileNotFoundError(f"run-overlay PNG repair helper is missing: {helper}")
    helper_b64 = base64.b64encode(helper.read_bytes()).decode("ascii")
    guest_root = f"/home/user/codesk-runs/{run_id}/{key}"
    guest_helper = f"{guest_root}/fix_guest_png_encoding.py"
    guest_command = (
        f"set -e; mkdir -p {shlex.quote(guest_root)}; "
        f"printf %s {shlex.quote(helper_b64)} | base64 -d > {shlex.quote(guest_helper)}; "
        f"python3 {shlex.quote(guest_helper)} {shlex.quote(guest_root)} {GUEST_CAPTURE_SHA256}"
    )
    command_error = None
    try:
        guest.execute(["/bin/bash", "-lc", guest_command], timeout=60)
    except Exception as exc:
        command_error = f"{type(exc).__name__}: {exc}"[:500]

    ready_deadline = time.monotonic() + 240
    while time.monotonic() < ready_deadline:
        try:
            probe = guest.execute(["/bin/echo", "CODESK_GUEST_SERVICE_READY"], timeout=8)
            if probe.get("returncode", 0) == 0 and "CODESK_GUEST_SERVICE_READY" in probe.get("output", ""):
                break
        except Exception:
            pass
        time.sleep(5)
    else:
        result = {"status": "restart_timeout", "observed_guest_capture_sha256": actual_sha,
                  "expected_audited_sha256": GUEST_CAPTURE_SHA256,
                  "command_error": command_error,
                  "restart_wait_seconds": 240}
        _write_json(evidence_dir / "png-fix-result.json", result)
        raise TimeoutError("Guest service did not restart after the guarded PNG overlay repair")

    report_path = f"{guest_root}/png-fix.json"
    report_result = guest.execute(["/bin/cat", report_path], timeout=15)
    if report_result.get("returncode", 0) != 0:
        raise RuntimeError("Guest PNG repair restarted but did not persist its guarded report")
    repair_report = json.loads(report_result.get("output", "{}"))
    if (repair_report.get("source_sha256") != GUEST_CAPTURE_SHA256
            or repair_report.get("scope") != "This Guest overlay only; base qcow2 unchanged"
            or repair_report.get("new_sha256") == GUEST_CAPTURE_SHA256):
        raise RuntimeError("Guest PNG repair metadata failed its source/scope checks")
    after = guest.execute([
        "/bin/bash", "-lc",
        "printf 'CAPTURE='; sha256sum /home/user/server/src/capture.py; "
        "printf 'MAINPID='; systemctl show osworld -p MainPID --value; "
        "printf 'ACTIVE='; systemctl is-active osworld; "
        "stat -c 'OWNER=%u MODE=%a' /home/user/server/src/capture.py",
    ], timeout=20)
    after_lines = (after.get("output", "").splitlines() if after.get("returncode", 1) == 0 else [])
    current_sha = next((line.split()[0].removeprefix("CAPTURE=") for line in after_lines
                        if line.startswith("CAPTURE=") and len(line.split()) > 1), None)
    current_pid = next((line.split("=", 1)[1] for line in after_lines if line.startswith("MAINPID=")), None)
    if (current_sha != repair_report["new_sha256"] or not current_pid or int(current_pid) <= 1
            or current_pid == str(repair_report.get("old_pid"))
            or "ACTIVE=active" not in after.get("output", "")):
        raise RuntimeError("Guest PNG repair file hash or restarted service PID did not verify")
    for guest_path, host_name in (
        (f"{guest_root}/capture.original.py", "capture.original.py"),
        (f"{guest_root}/capture.patch.diff", "capture.patch.diff"),
    ):
        encoded = guest.execute(["/usr/bin/base64", "-w0", guest_path], timeout=20)
        if encoded.get("returncode", 0) != 0:
            raise RuntimeError(f"could not collect run-owned Guest repair evidence: {host_name}")
        (evidence_dir / host_name).write_bytes(base64.b64decode(encoded["output"]))
        (evidence_dir / host_name).chmod(0o600)
    original_path = evidence_dir / "capture.original.py"
    if _sha256(original_path) != GUEST_CAPTURE_SHA256:
        raise RuntimeError("collected original Guest screenshot source failed its audited SHA")
    result = {"status": "applied_and_service_restarted", "observed_guest_capture_sha256": actual_sha,
              "observed_guest_capture_after_sha256": current_sha,
              "guest_osworld_service_new_pid": int(current_pid),
              "command_http_error_expected_from_self_restart": command_error,
              "repair": repair_report, "evidence_directory": str(evidence_dir)}
    _write_json(evidence_dir / "png-fix-result.json", result)
    return result


def _guest_http_probe(guest: Any, url: str) -> dict[str, Any]:
    command = ("curl --noproxy '*' --connect-timeout 5 --max-time 15 -fsS "
               f"-o /dev/null -w 'http=%{{http_code}} bytes=%{{size_download}} content_type=%{{content_type}}\\n' "
               f"{shlex.quote(url)}")
    result = guest.execute(["/bin/bash", "-lc", command], timeout=25)
    return {"url_path": url.split("/", 3)[-1], "status": result.get("status"),
            "returncode": result.get("returncode"), "output": result.get("output", "")[-500:],
            "error": result.get("error", "")[-500:]}


def _guest_network_diagnostic(guest: Any) -> dict[str, Any]:
    command = (
        "python3 -c 'import json,os,socket; "
        "print(json.dumps({\"proxy_variables_set\":sorted(k for k in os.environ "
        "if k.lower() in {\"http_proxy\",\"https_proxy\",\"all_proxy\"}), "
        "\"no_proxy_set\":any(k.lower()==\"no_proxy\" for k in os.environ)}))'; "
        "ip -brief address 2>/dev/null; ip route 2>/dev/null"
    )
    result = guest.execute(["/bin/bash", "-lc", command], timeout=20)
    return {"returncode": result.get("returncode"),
            "output": result.get("output", "")[-2500:],
            "error": result.get("error", "")[-500:]}


def _host_network_diagnostic(env: Any, service_port: int, run_root: Path) -> dict[str, Any]:
    """Capture only run-relevant host sockets and app requests after a Guest HTTP failure."""
    manifest = getattr(env.provider, "manifest", {})
    guestfwd = manifest.get("guestfwd", [])
    relevant_ports = {int(service_port)}
    relevant_ports.update(int(row["host_port"]) for row in guestfwd if row.get("host_port"))
    try:
        result = subprocess.run(["ss", "-antp"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.splitlines()
        sockets = [line for line in lines[1:] if any(f":{port}" in line for port in relevant_ports)]
        ss_error = result.stderr[-500:] if result.returncode else ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        sockets = []
        ss_error = f"{type(exc).__name__}: {exc}"
    access_log = run_root / "db" / "case.http.jsonl"
    try:
        requests_seen = access_log.read_text(encoding="utf-8").splitlines()[-20:]
    except OSError as exc:
        requests_seen = [f"{type(exc).__name__}: {exc}"]
    return {
        "guestfwd": guestfwd,
        "qemu_pid": manifest.get("pid"),
        "service_port": int(service_port),
        "matching_host_tcp_sockets": sockets,
        "ss_error": ss_error,
        "case_http_tail": requests_seen,
    }


def _guest_health_probe(guest: Any) -> dict[str, Any]:
    result = guest.execute([
        "/bin/bash", "-lc",
        f"curl --noproxy '*' --connect-timeout 5 --max-time 15 -fsS "
        f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/health",
    ], timeout=25)
    return {"status": result.get("status"), "returncode": result.get("returncode"),
            "output": result.get("output", "")[-500:],
            "error": result.get("error", "")[-500:]}


def _ensure_guest_runtime_libraries() -> None:
    library_dir = Path("/opt/data/private/mjh/deps/libgl-runtime/root/usr/lib/x86_64-linux-gnu")
    if not (library_dir / "libGL.so.1").is_file():
        return
    current = os.environ.get("LD_LIBRARY_PATH", "")
    entries = [item for item in current.split(os.pathsep) if item]
    if str(library_dir) in entries:
        return
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join([str(library_dir), *entries])
    if os.environ.get("CODESK_GUI_LIB_REEXEC") == "1":
        return
    os.environ["CODESK_GUI_LIB_REEXEC"] = "1"
    os.execvpe(sys.executable, [sys.executable, *sys.argv], os.environ.copy())


def _role_window(guest: Any, role: str, profile: str) -> dict[str, Any]:
    program = (
        "import os,sys; profile=sys.argv[1]; "
        "exec(\"for entry in os.scandir('/proc'):\\n"
        " if not entry.name.isdigit(): continue\\n"
        " try:\\n"
        "  args=open('/proc/'+entry.name+'/cmdline','rb').read().decode(errors='ignore')\\n"
        "  exe=os.readlink('/proc/'+entry.name+'/exe').lower()\\n"
        "  if profile in args and ('chrome' in exe or 'chromium' in exe): print(entry.name)\\n"
        " except OSError: pass\")"
    )
    probe = guest.execute(["bash", "-lc", f"python3 -c {shlex.quote(program)} {shlex.quote(profile)}"], 20)
    pids = set(str(probe.get("output", "")).split())
    windows = guest.execute(["bash", "-lc", "wmctrl -lpGx 2>/dev/null || true"], 20).get("output", "")
    selected = None
    for line in windows.splitlines():
        fields = line.split()
        if fields and (f"CoDesk{role}" in line or (len(fields) > 2 and fields[2] in pids)):
            selected = fields[0]
            break
    if not selected:
        raise RuntimeError(
            f"cannot locate the signed-in {role} browser window; "
            f"profile_process_ids={sorted(pids)!r}; window_list={windows[-2000:]!r}; "
            f"process_probe={probe.get('output', '')[-1000:]!r}; "
            f"process_probe_error={probe.get('error', '')[-1000:]!r}"
        )
    activated = guest.execute(["wmctrl", "-ia", selected], 15)
    return {"role": role, "window_id": selected, "profile_process_ids": sorted(pids),
            "window_list": windows, "activation_status": activated.get("status")}


def _selected_browser_title(window: dict[str, Any]) -> str:
    """Return the wmctrl row for the selected browser window, not another role's tab."""
    window_id = str(window.get("window_id", ""))
    for line in str(window.get("window_list", "")).splitlines():
        fields = line.split(None, 1)
        if fields and fields[0] == window_id:
            return line
    return ""


def _guest_devtools_page_snapshot(guest: Any, port: int) -> dict[str, Any]:
    """Read one Chromium page snapshot through CDP using Guest standard-library Python."""
    program = r'''
import base64, json, os, socket, struct, time, urllib.request, urllib.parse
port = __PORT__
targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=4))
target = next((x for x in targets if x.get("type") == "page"), None)
if target is None:
    raise RuntimeError("DevTools returned no page target")
url = urllib.parse.urlsplit(target["webSocketDebuggerUrl"])
sock = socket.create_connection(("127.0.0.1", port), timeout=4)
sock.settimeout(4)
key = base64.b64encode(os.urandom(16)).decode()
request = (f"GET {url.path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode()
sock.sendall(request)
buffer = b""
while b"\r\n\r\n" not in buffer:
    buffer += sock.recv(4096)
headers, buffer = buffer.split(b"\r\n\r\n", 1)
status_line = headers.split(b"\r\n", 1)[0].split()
if len(status_line) < 2 or status_line[1] != b"101":
    raise RuntimeError(headers.decode("latin1", "replace"))
expression = "JSON.stringify({href:location.href,title:document.title,readyState:document.readyState,bodyText:(document.body&&document.body.innerText||'').slice(0,1200),htmlLength:(document.documentElement&&document.documentElement.outerHTML||'').length,resources:performance.getEntriesByType('resource').map(x=>({name:x.name,transferSize:x.transferSize,duration:x.duration}))})"
def send_command(command_id, method, params):
    payload = json.dumps({"id": command_id, "method": method, "params": params}).encode()
    mask = os.urandom(4)
    length = len(payload)
    if length < 126:
        frame = bytes([0x81, 0x80 | length])
    elif length < 65536:
        frame = bytes([0x81, 0x80 | 126]) + struct.pack("!H", length)
    else:
        frame = bytes([0x81, 0x80 | 127]) + struct.pack("!Q", length)
    sock.sendall(frame + mask + bytes(value ^ mask[index % 4] for index, value in enumerate(payload)))
def read_exact(size):
    global buffer
    while len(buffer) < size:
        buffer += sock.recv(4096)
    result, buffer = buffer[:size], buffer[size:]
    return result
def read_reply(command_id):
    for _ in range(40):
        first, second = read_exact(2)
        opcode, length = first & 15, second & 127
        if length == 126:
            length = struct.unpack("!H", read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", read_exact(8))[0]
        mask_key = read_exact(4) if second & 128 else None
        data = read_exact(length)
        if mask_key:
            data = bytes(value ^ mask_key[index % 4] for index, value in enumerate(data))
        if opcode == 1:
            message = json.loads(data)
            if message.get("id") == command_id:
                return message
        elif opcode == 8:
            break
    return None
send_command(1, "Runtime.evaluate", {"expression": expression, "returnByValue": True})
original = read_reply(1)
static_html = "<!doctype html><title>CoDesk static smoke</title><body>Static render OK</body>"
data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(static_html)
send_command(2, "Page.navigate", {"url": data_url})
navigation = read_reply(2)
time.sleep(1.5)
static_expression = "JSON.stringify({href:location.href,title:document.title,readyState:document.readyState,bodyText:(document.body&&document.body.innerText||'').slice(0,200)})"
send_command(3, "Runtime.evaluate", {"expression": static_expression, "returnByValue": True})
static_result = read_reply(3)
sock.close()
print(json.dumps({"target": {key: target.get(key) for key in ("title", "url", "type", "id")},
                  "cdp": original, "static_smoke_navigation": navigation,
                  "static_smoke": static_result}, ensure_ascii=False))
'''.replace("__PORT__", str(int(port)))
    result = guest.execute(["python3", "-c", program], timeout=20)
    output = (result.get("output") or "").strip()
    try:
        snapshot = json.loads(output)
    except json.JSONDecodeError:
        snapshot = None
    return {"status": result.get("status"), "returncode": result.get("returncode"),
            "snapshot": snapshot, "output": output[-6000:],
            "error": (result.get("error") or "")[-2000:]}


def _visible_browser_navigate(guest: Any, url: str) -> None:
    """Navigate using the visible omnibox, with focus/selection settling delays."""
    code = (
        "import pyautogui,time; pyautogui.hotkey('ctrl','l'); time.sleep(0.5); "
        "pyautogui.hotkey('ctrl','a'); pyautogui.write(" + repr(url) +
        ", interval=0.01); time.sleep(0.3); pyautogui.press('enter')"
    )
    guest.run_pyautogui(code)


def _configure_chrome_profile(guest: Any, profile: str) -> dict[str, Any]:
    """Disable password-manager prompts in a new synthetic Guest profile."""
    setup = r"""
import json, os, sys
root = sys.argv[1]
os.makedirs(os.path.join(root, "Default"), exist_ok=True)
prefs_path = os.path.join(root, "Default", "Preferences")
created = not os.path.exists(prefs_path)
if created:
    prefs = {"credentials_enable_service": False,
             "profile": {"password_manager_enabled": False,
                         "password_manager_leak_detection": False}}
    with open(prefs_path, "w", encoding="utf-8") as stream:
        json.dump(prefs, stream)
print(json.dumps({"preferences_path": prefs_path, "created": created}))
"""
    result = guest.execute(["python3", "-c", setup, profile], timeout=15)
    if result.get("returncode", 0) != 0:
        raise RuntimeError("could not disable Chrome password prompts: " +
                           str(result.get("error", ""))[-500:])
    try:
        return json.loads((result.get("output") or "").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"preferences_path": str(Path(profile) / "Default" / "Preferences"),
                "created": None}


def _launch_browser(guest: Any, role: str, url: str, profile: str, run_root: Path) -> dict[str, Any]:
    probe = guest.execute([
        "bash", "-lc",
        "command -v google-chrome || command -v chromium-browser || command -v chromium",
    ], 20)
    browser = (probe.get("output") or "").strip().splitlines()
    if probe.get("returncode", 0) != 0 or not browser:
        raise RuntimeError("OSWorld Guest has no supported Chromium browser")
    binary = browser[-1]
    # Chromium runs only inside this disposable, synthetic OSWorld Guest. Keep
    # its DevTools endpoint on guest loopback and sample the document read-only
    # on failure. The last attempt showed --remote-debugging-address does not
    # broaden this Chrome build's listener beyond loopback.
    remote_debugging_port = 19222 if role == "A" else 19223
    remote_debugging_address = "127.0.0.1"
    profile_prefs = _configure_chrome_profile(guest, profile)
    browser_log = f"/tmp/codesk-ttr-lite-{role}.log"
    browser_exit = f"/tmp/codesk-ttr-lite-{role}.exit"
    browser_pid = f"/tmp/codesk-ttr-lite-{role}.pid"
    browser_command = (
        f"{shlex.quote(binary)} --no-first-run --no-default-browser-check "
        f"--start-maximized "
        f"--disable-session-crashed-bubble --user-data-dir={shlex.quote(profile)} "
        f"--no-sandbox --disable-dev-shm-usage "
        f"--password-store=basic --disable-save-password-bubble "
        f"--disable-features=PasswordManagerOnboarding,PasswordLeakDetection "
        f"--remote-debugging-address={remote_debugging_address} --remote-debugging-port={remote_debugging_port} "
        f"--disable-gpu --disable-extensions --no-proxy-server "
        f"--class=CoDesk{role} --new-window {shlex.quote(url)} "
        f">{shlex.quote(browser_log)} 2>&1 </dev/null"
    )
    monitor_script = (
        f"printf '%s\\n' \"$$\" > {shlex.quote(browser_pid)}; "
        f"{browser_command}; browser_rc=$?; "
        f"printf 'browser_exit=%s\\n' \"$browser_rc\" >> {shlex.quote(browser_log)}; "
        f"printf '%s\\n' \"$browser_rc\" > {shlex.quote(browser_exit)}; "
        f"exit \"$browser_rc\""
    )
    command = (
        f"rm -f {shlex.quote(browser_exit)} {shlex.quote(browser_pid)}; "
        f"nohup bash -lc {shlex.quote(monitor_script)} >/dev/null 2>&1 </dev/null &"
    )
    result = guest.execute(["bash", "-lc", command], timeout=25)
    if result.get("returncode", 0) != 0:
        raise RuntimeError(f"could not launch the {role} browser window")
    launch_log = guest.execute([
        "bash", "-lc", f"cat {shlex.quote('/tmp/codesk-ttr-lite-' + role + '.log')} 2>/dev/null || true",
    ], 10)
    _write_json(run_root / "screenshots" / "setup" / f"{role}-browser-launch.json", {
        "browser": binary, "profile": profile, "url": url,
        "launch_status": result.get("status"), "launch_returncode": result.get("returncode"),
        "process_exit_status_file": browser_exit,
        "process_pid_file": browser_pid,
        "remote_debugging_address": remote_debugging_address,
        "remote_debugging_port": remote_debugging_port,
        "launch_flags": ["--no-sandbox", "--disable-dev-shm-usage", "--password-store=basic",
                         "--disable-save-password-bubble", "--start-maximized",
                         "--disable-features=PasswordManagerOnboarding,PasswordLeakDetection"],
        "password_manager_prefs_disabled": True,
        "password_manager_preferences": profile_prefs,
        "launch_log": launch_log.get("output", "")[-4000:],
    })
    deadline = time.monotonic() + 180
    last_error = None
    next_screenshot = 0.0
    next_navigation_retry = time.monotonic() + 25
    navigation_retries = 0
    while time.monotonic() < deadline:
        try:
            window = _role_window(guest, role, profile)
            title = _selected_browser_title(window)
            # The Guest screenshot endpoint can return the desktop wallpaper
            # while Chrome is still loading; wallpaper also passes the generic
            # nonblack/content-ready test. Do not type a role credential until
            # this exact profile's browser window has the Case Desk document.
            if "Case Desk" not in title:
                last_error = f"{role} browser document is not loaded yet: {title[-240:]}"
                # A few OSWorld boots leave Chrome's initial navigation at
                # about:blank even though the address bar shows the app URL.
                # Recover through the visible browser UI, not DevTools, and
                # retain retry count in the run evidence.
                now = time.monotonic()
                if navigation_retries < 2 and now >= next_navigation_retry:
                    _visible_browser_navigate(guest, url)
                    navigation_retries += 1
                    next_navigation_retry = now + 35
            elif time.monotonic() >= next_screenshot:
                shot = _screenshot(guest, run_root / "screenshots" / "setup" / f"{role}-login.png")
                next_screenshot = time.monotonic() + 5
                if shot["content_ready"]:
                    return {"browser": binary, "profile": profile, "url": url,
                            "window": window, "login_screenshot": shot,
                            "visible_navigation_retries": navigation_retries,
                            "readiness_s": round(180 - max(0, deadline - time.monotonic()), 2)}
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(2)
    screenshot = None
    try:
        screenshot = _screenshot(guest, run_root / "screenshots" / "setup" / f"{role}-login-failed.png")
    except Exception as exc:
        screenshot = {"error": f"{type(exc).__name__}: {exc}"}
    diagnostic_command = (
        "printf 'WINDOWS_BEGIN\\n'; wmctrl -lpGx 2>&1 || true; printf 'WINDOWS_END\\n'; "
        "printf 'PROCESSES_BEGIN\\n'; ps -eo pid,ppid,stat,etime,%cpu,rss,args "
        "| grep -E '[c]hrome|[c]hromium|[X]org|[X]vfb|[o]penbox|[g]nome-shell' || true; "
        "printf 'PROCESSES_END\\n'; "
        f"printf 'BROWSER_LOG_BEGIN\\n'; cat {shlex.quote(browser_log)} 2>&1 || true; "
        "printf 'BROWSER_LOG_END\\n'; "
        f"printf 'BROWSER_MONITOR_BEGIN\\n'; printf 'pid='; cat {shlex.quote(browser_pid)} 2>&1 || true; "
        f"printf '\\nexit='; cat {shlex.quote(browser_exit)} 2>&1 || true; printf '\\nBROWSER_MONITOR_END\\n'; "
        f"printf 'CHROME_CRASH_FILES_BEGIN\\n'; find {shlex.quote(profile)}/Crashpad /var/crash -maxdepth 3 -type f "
        "-printf '%p %s bytes\\n' 2>/dev/null | tail -n 20; printf 'CHROME_CRASH_FILES_END\\n'; "
        f"printf 'DEVTOOLS_VERSION_BEGIN\\n'; curl -sS --max-time 3 http://127.0.0.1:{remote_debugging_port}/json/version 2>&1 || true; "
        "printf '\\nDEVTOOLS_VERSION_END\\n'; "
        f"printf 'DEVTOOLS_TARGETS_BEGIN\\n'; curl -sS --max-time 3 http://127.0.0.1:{remote_debugging_port}/json/list 2>&1 || true; "
        "printf '\\nDEVTOOLS_TARGETS_END\\n'; "
        "printf 'KERNEL_EVENTS_BEGIN\\n'; (dmesg -T 2>/dev/null || sudo -n dmesg -T 2>/dev/null || true) "
        "| grep -Ei 'out of memory|oom|killed process|chrome|chromium' | tail -n 30 || true; "
        "printf 'KERNEL_EVENTS_END\\n'; "
    )
    diagnostic_errors: list[str] = []
    try:
        diagnostic = guest.execute(["bash", "-lc", diagnostic_command], 45)
    except Exception as exc:
        diagnostic = {"output": "", "error": f"{type(exc).__name__}: {exc}"}
        diagnostic_errors.append(f"browser diagnostics: {type(exc).__name__}: {exc}")
    resource_command = _resource_diagnostics_command(profile)
    try:
        resources = guest.execute(["bash", "-lc", resource_command], 45)
    except Exception as exc:
        resources = {"output": "", "error": f"{type(exc).__name__}: {exc}"}
        diagnostic_errors.append(f"resource diagnostics: {type(exc).__name__}: {exc}")
    diagnostic_output = (diagnostic.get("output", "") + "\n" +
                         resources.get("output", "")[-5000:])[-15000:]
    for label, response in (("browser diagnostics", diagnostic),
                            ("resource diagnostics", resources)):
        error = response.get("error")
        if error:
            diagnostic_errors.append(f"{label} returned error: {error}")
    if diagnostic_errors:
        diagnostic_output += "\nDIAGNOSTIC_COLLECTION_ERRORS\n" + "\n".join(diagnostic_errors)
    try:
        page_snapshot = _guest_devtools_page_snapshot(guest, remote_debugging_port)
    except Exception as exc:
        page_snapshot = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        diagnostic_errors.append(f"CDP snapshot: {type(exc).__name__}: {exc}")
        diagnostic_output += f"\nCDP_SNAPSHOT_ERROR: {type(exc).__name__}: {exc}"
    _write_json(run_root / "screenshots" / "setup" / f"{role}-cdp-document-snapshot.json",
                page_snapshot)
    (run_root / "screenshots" / "setup" / f"{role}-login-failed-diagnostics.txt").write_text(
        diagnostic_output, encoding="utf-8")
    raise TimeoutError(
        f"{role} login page did not become visible: {last_error}; "
        f"screenshot={screenshot}; diagnostics={diagnostic_output[-1500:]}"
    )


def _login_browser(guest: Any, role: str, password: str, profile: str,
                   run_root: Path) -> dict[str, Any]:
    window = _role_window(guest, role, profile)
    if "Case Desk" not in _selected_browser_title(window):
        raise RuntimeError(f"{role} login refused: the Case Desk document is not loaded")
    guest.run_pyautogui(
        "import pyautogui; pyautogui.write(" + repr(password) +
        ", interval=0.004); pyautogui.press('tab'); pyautogui.press('enter')")
    deadline = time.monotonic() + 45
    last_title = ""
    while time.monotonic() < deadline:
        window = _role_window(guest, role, profile)
        last_title = _selected_browser_title(window)
        if "Case Desk" in last_title and f"{role} ·" in last_title:
            # Chrome can leave a native "Save password?" bubble focused after
            # sign-in. That browser UI traps subsequent keyboard navigation, so
            # form controls appear to accept input while no application fields
            # change. Dismiss it before any GUI workflow starts.
            guest.run_pyautogui("import pyautogui,time; time.sleep(1); pyautogui.press('esc'); time.sleep(0.3)")
            screenshot = _screenshot(guest, run_root / "screenshots" / "setup" / f"{role}-ready.png")
            return {"window": window, "screenshot": screenshot, "login_submitted": True,
                    "login_verified_by_window_title": True,
                    "post_login_browser_prompts_dismissed": ["escape"]}
        time.sleep(2)
    raise RuntimeError(f"{role} login did not reach its authenticated Case Desk page; "
                       f"observed_window={last_title[-500:]!r}")


def _switch_url(guest: Any, role: str, profile: str, url: str) -> dict[str, Any]:
    window = _role_window(guest, role, profile)
    _visible_browser_navigate(guest, url)
    deadline = time.monotonic() + 30
    last_title = ""
    while time.monotonic() < deadline:
        window = _role_window(guest, role, profile)
        last_title = _selected_browser_title(window)
        if "Case Desk" in last_title and f"{role} ·" in last_title:
            return {"window": window, "url": url, "completed": True,
                    "navigation_verified_by_window_title": True}
        time.sleep(1)
    raise RuntimeError(f"{role} browser did not finish navigation to the authenticated Case Desk page; "
                       f"observed_window={last_title[-500:]!r}")


def _logged_gui_action(guest: Any, run_root: Path, scenario: str, actor: str,
                       label: str, code: str, guest_key: str) -> dict[str, Any]:
    before = _focus_sample(guest)
    started = time.time()
    result = guest.run_pyautogui(code)
    after = _focus_sample(guest)
    frame = _screenshot(guest, run_root / "screenshots" / "controls" / scenario /
                        f"{actor}-{label}.png")
    event = {"scenario": scenario, "actor": actor, "guest_key": guest_key, "label": label,
             "code": code, "started_unix": started, "finished_unix": time.time(),
             "window_before": before, "window_after": after, "window_samples_atomic": False,
             "screenshot": frame}
    _append(run_root / "gui_actions.jsonl", event)
    if result.get("status") not in {None, "success"} or result.get("returncode", 0) != 0:
        raise RuntimeError(f"{actor} scripted GUI action failed: {label}")
    return event


def _prepare_episode(run_root: Path, run_id: str, condition: str,
                     app_url: str) -> dict[str, Any]:
    from oscombo.collab.ticket_to_resolution.runner import make_plan, prepare_run
    from oscombo.collab.ticket_to_resolution.lite_v1 import CASE_ID, CASE_VERSION, SOURCE_CASE_ID
    from oscombo.collab.ticket_to_resolution.lite_v1 import spec as lite_spec

    created = prepare_run(run_root, run_id)
    plan = make_plan(condition, run_id, app_url=app_url,
                     steps_per_role=lite_spec.ROLE_BUDGET["A"]["steps"], tokens_per_role=12000)
    plan.update({"case_id": CASE_ID, "case_version": CASE_VERSION,
                 "source_case_id": SOURCE_CASE_ID, "case_variant": "lite-v1",
                 "role_budgets": lite_spec.ROLE_BUDGET,
                 "model": MODEL, "effort": "medium"})
    _write_json(run_root / "run_config.json", plan)
    _write_json(run_root / "lite_version.json", {
        "case_id": CASE_ID, "case_version": CASE_VERSION,
        "source_case_id": SOURCE_CASE_ID, "task_card": "oscombo/collab/ticket_to_resolution/lite_v1/TASK_CARD_ZH.md",
        "action_target": {"A": 6, "B": 7, "combined": 13},
    })
    return created


def _start_services(run_root: Path, run_id: str, credentials: dict[str, str],
                    variant: str) -> tuple[Any, threading.Thread, Any, threading.Thread, int]:
    from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server as make_protocol_server
    from oscombo.collab.ticket_to_resolution.webapp import make_server as make_case_server

    _bypass_proxy_for_local_services()
    case_server = make_case_server(
        run_root / "db" / "case.sqlite3", credentials,
        host="127.0.0.1", port=0, variant=variant)
    case_thread = threading.Thread(target=case_server.serve_forever, daemon=True)
    case_thread.start()
    protocol_store = ProtocolStore(run_root / "collaboration", run_id)
    tokens = json.loads((run_root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    read_messages = protocol_store.messages
    read_log_lock = threading.Lock()

    def audited_read_messages(actor: str, after: float = 0.0):
        messages = read_messages(actor, after)
        _append(run_root / "collaboration_reads.jsonl", {
            "time_unix": time.time(), "reader": actor, "after_unix": after,
            "message_ids": [message.get("message_id", message.get("id")) for message in messages],
            "senders": [message.get("sender", message.get("actor")) for message in messages],
        }, read_log_lock)
        return messages

    protocol_store.messages = audited_read_messages
    protocol_server = make_protocol_server(protocol_store, tokens, host="127.0.0.1", port=0)
    protocol_thread = threading.Thread(target=protocol_server.serve_forever, daemon=True)
    protocol_thread.start()
    for _ in range(50):
        try:
            response = requests.get(f"http://127.0.0.1:{case_server.server_port}/health", timeout=2)
            if response.ok and response.json().get("ready"):
                break
        except requests.RequestException:
            pass
        time.sleep(0.1)
    else:
        raise TimeoutError("host case service did not become ready")
    return case_server, case_thread, protocol_server, protocol_thread, case_server.server_port


def _boot_desktops(run_root: Path, run_id: str, condition: str, app_port: int,
                   report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    from oscombo.osworld import activate
    from oscombo.combo import boot
    from oscombo.guest import Guest

    if not IMAGE.is_file() or not OSWORLD.is_dir():
        raise FileNotFoundError("the pinned OSWorld checkout or Guest qcow2 is missing")
    if not (QEMU_PREFIX / "bin" / "qemu-system-x86_64").is_file():
        raise FileNotFoundError("the private native QEMU runtime is missing")
    _configure_native_environment(run_root, run_id, app_port)
    activate()
    if condition == "collaborative_shared":
        keys = ("shared",)
        actor_guest_keys = {"A": "shared", "B": "shared"}
    elif condition == "collaborative_isolated":
        keys = ("A", "B")
        actor_guest_keys = {"A": "A", "B": "B"}
    else:
        keys = ("S",)
        actor_guest_keys = {"S": "S"}
    environments: dict[str, Any] = {}
    guests: dict[str, Any] = {}
    setup: dict[str, Any] = {}
    try:
        for guest_key in keys:
            cache = run_root / "cache" / guest_key
            cache.mkdir(parents=True, exist_ok=True)
            os.environ.pop("OSCOMBO_NATIVE_QMP_SOCKET", None)
            report["status"] = "GUEST_BOOT"
            report["stage"] = f"booting_guest_{guest_key}"
            _write_json(run_root / "progress.json", report)
            started = time.monotonic()
            env = boot(str(IMAGE), str(cache))
            environments[guest_key] = env
            guests[guest_key] = Guest(env)
            provider = env.provider
            if provider.manifest.get("base_image_read_only") is not True:
                raise RuntimeError("native QEMU did not verify the base image as read-only")
            probes = report.setdefault("guest_http_probes", {}).setdefault(guest_key, [])
            guest_health = _guest_health_probe(guests[guest_key])
            health_record = {"path": "health-before-capture-repair", **guest_health}
            if guest_health.get("returncode", 0) != 0 or '"ready":true' not in guest_health.get("output", ""):
                health_record["network_diagnostic"] = _guest_network_diagnostic(guests[guest_key])
                probes.append(health_record)
                _write_json(run_root / "progress.json", report)
                raise RuntimeError(f"Guest {guest_key} direct connection to the shared host case service failed")
            probes.append(health_record)
            capture_fix = _apply_guest_png_fix(guests[guest_key], run_root, run_id, guest_key)
            report.setdefault("guest_capture_fixes", {})[guest_key] = capture_fix
            probe_roles = ("A", "B") if condition == "collaborative_shared" else (guest_key,)
            repeat_health = guests[guest_key].execute([
                "/bin/bash", "-lc",
                f"curl --noproxy '*' --connect-timeout 5 --max-time 15 -fsS "
                f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/health",
            ], timeout=25)
            probes.append({"path": "health-repeat", "status": repeat_health.get("status"),
                           "returncode": repeat_health.get("returncode"),
                           "output": repeat_health.get("output", "")[-500:],
                           "error": repeat_health.get("error", "")[-500:]})
            if repeat_health.get("returncode", 0) != 0:
                raise RuntimeError(f"Guest {guest_key} second request to the shared service failed")
            for actor in probe_roles:
                login_url = f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/login?actor={actor}"
                probe = _guest_http_probe(guests[guest_key], login_url)
                probes.append({"path": f"login-{actor}", **probe})
                if probe["returncode"] != 0:
                    report["guest_http_probes"][guest_key] = probes
                    _write_json(run_root / "progress.json", report)
                    raise RuntimeError(f"Guest {guest_key} cannot fetch Case Desk login for {actor}: "
                                       f"{probe['error'] or probe['output']}")
            _write_json(run_root / "progress.json", report)
            desktop_readiness = _wait_for_guest_desktop(guests[guest_key], run_root, guest_key, report)
            setup[guest_key] = {
                "boot_s": round(time.monotonic() - started, 2),
                "desktop_readiness": desktop_readiness,
                "provider": provider.manifest.get("provider"),
                "qemu": provider.manifest.get("qemu"),
                "qemu_version": provider.manifest.get("qemu_version"),
                "pid": provider.process.pid if provider.process else None,
                "ports": provider.manifest.get("ports"),
                "overlay": str(provider.overlay_path) if provider.overlay_path else None,
                "guestfwd": provider.manifest.get("guestfwd"),
                "capture_fix": capture_fix,
                "base_image_read_only": True,
                "host_case_service_reachable": True,
                "metrics_at_ready": _process_metrics(provider.process.pid if provider.process else None),
            }
            report["setup"] = setup
            _write_json(run_root / "progress.json", report)
    except Exception:
        guest_cleanup = _close_guests(environments)
        guest_verified = all(
            not row["qemu_alive_after_close"] and not row["overlay_exists_after_close"]
            and row["close_error_type"] is None
            and all(row["forwarded_ports_released"].values()) for row in guest_cleanup)
        report["guest_setup_failure_cleanup"] = {
            "guests": guest_cleanup, "verified": guest_verified,
        }
        _write_json(run_root / "progress.json", report)
        raise
    report["guest_count"] = len(guests)
    report["role_to_guest"] = actor_guest_keys
    return environments, guests, actor_guest_keys


def _prepare_browsers(run_root: Path, run_id: str, condition: str,
                      credentials: dict[str, str], guests: dict[str, Any],
                      actor_guest_keys: dict[str, str], app_port: int) -> tuple[dict[str, str], dict[str, Any]]:
    browser_profiles: dict[str, str] = {}
    browser_reports: dict[str, Any] = {}
    roles = ("S",) if condition == "single_agent" else ("A", "B")
    for role in roles:
        guest_key = actor_guest_keys[role]
        guest = guests[guest_key]
        profile = f"/tmp/codesk-ttr-lite-{run_id}-{role}"
        login_url = f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/login?actor={role}"
        route_probe = _guest_http_probe(guest, login_url)
        if route_probe.get("returncode", 0) != 0:
            time.sleep(5)
            route_probe = _guest_http_probe(guest, login_url)
        if route_probe.get("returncode", 0) != 0:
            raise RuntimeError(f"Guest {guest_key} cannot load the Case Desk sign-in page: "
                               f"{route_probe.get('error') or route_probe.get('output', '')}")
        _screenshot(guest, run_root / "screenshots" / "setup" / f"{role}-desktop-before-browser.png")
        launched = _launch_browser(guest, role, login_url, profile, run_root)
        logged_in = _login_browser(guest, role, credentials[role], profile, run_root)
        browser_profiles[role] = profile
        browser_reports[role] = {"guest_key": guest_key, "launch": launched, "login": logged_in}
    if condition == "collaborative_shared":
        focus = _role_window(guests["shared"], "A", browser_profiles["A"])
    else:
        focus = None
    return browser_profiles, {"roles": browser_reports, "initial_shared_focus": focus,
                              "session_identity_check": "per-role login submitted; verified against server session table"}


def _control_gui_actions(run_root: Path, run_id: str, scenario: str, condition: str,
                         guests: dict[str, Any], actor_guest_keys: dict[str, str],
                         browser_profiles: dict[str, str], app_port: int,
                         credentials: dict[str, str], protocol_server: Any) -> dict[str, Any]:
    from oscombo.collab.data_to_deck.collab_tools import CollaborationClient
    from oscombo.collab.ticket_to_resolution.database import CaseStore
    from oscombo.collab.ticket_to_resolution.oracle import evaluate
    from oscombo.collab.ticket_to_resolution import spec as case_spec
    from oscombo.collab.ticket_to_resolution.runner import hidden_manifest_path
    from oscombo.collab.ticket_to_resolution.lite_v1 import spec as lite_spec

    guest_for = {role: guests[key] for role, key in actor_guest_keys.items()}
    guest_key_for = actor_guest_keys
    clients = {}
    tokens = json.loads((run_root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    for role in ("A", "B"):
        clients[role] = CollaborationClient(
            f"http://127.0.0.1:{protocol_server.server_port}", role, tokens[role])
    app_url = f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/lite"
    for role in ("A", "B"):
        _switch_url(guest_for[role], role, browser_profiles[role], app_url)

    verifier = guest_for["A"]
    _role_window(verifier, "A", browser_profiles["A"])
    # The Lite form uses radio inputs. Each field is a separately logged GUI
    # action: select the focused first option with Space, then advance through
    # groups with Tab. ArrowDown selects the USB-C dock (L2).
    _logged_gui_action(verifier, run_root, scenario, "A", "eligibility",
                       "import pyautogui; pyautogui.press('space')", guest_key_for["A"])
    _logged_gui_action(verifier, run_root, scenario, "A", "affected-line",
                       "import pyautogui; pyautogui.press('tab'); pyautogui.press('down'); pyautogui.press('space')", guest_key_for["A"])
    _logged_gui_action(verifier, run_root, scenario, "A", "delivery-evidence",
                       "import pyautogui; pyautogui.press('tab'); pyautogui.press('space')", guest_key_for["A"])
    _logged_gui_action(verifier, run_root, scenario, "A", "shipping-treatment",
                       "import pyautogui; pyautogui.press('tab'); pyautogui.press('space')", guest_key_for["A"])
    chosen_amount = "80.00" if scenario == "negative" else "88.00"
    _logged_gui_action(verifier, run_root, scenario, "A", "proposed-total",
                       f"import pyautogui; pyautogui.press('tab'); pyautogui.write('{chosen_amount}')",
                       guest_key_for["A"])
    _logged_gui_action(verifier, run_root, scenario, "A", "save-review",
                       "import pyautogui,time; pyautogui.press('tab'); pyautogui.press('enter'); time.sleep(1)",
                       guest_key_for["A"])

    store = CaseStore(run_root / "db" / case_spec.FIXTURE_DB)
    deadline = time.monotonic() + 45
    reviews = []
    while time.monotonic() < deadline:
        reviews = store.list_reviews()
        if reviews:
            break
        time.sleep(0.5)
    if not reviews:
        raise TimeoutError("scripted A did not save a Case Review")
    review = reviews[-1]
    message = clients["A"].send_message(
        "B", f"Case Review {review['id']} is saved and ready for your independent check.")
    received = []
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        received = clients["B"].read_messages()
        if received:
            break
        time.sleep(0.5)
    if not received:
        raise RuntimeError("scripted B could not read A's saved-review handoff")

    processor = guest_for["B"]
    _role_window(processor, "B", browser_profiles["B"])
    time.sleep(3.5)
    _logged_gui_action(processor, run_root, scenario, "B", "refund-line",
                       "import pyautogui; pyautogui.press('down'); pyautogui.press('space')", guest_key_for["B"])
    _logged_gui_action(processor, run_root, scenario, "B", "refund-shipping",
                       "import pyautogui; pyautogui.press('tab'); pyautogui.press('space')", guest_key_for["B"])
    _logged_gui_action(processor, run_root, scenario, "B", "refund-total",
                       f"import pyautogui; pyautogui.press('tab'); pyautogui.write('{chosen_amount}')",
                       guest_key_for["B"])
    refund_attempt = _logged_gui_action(
        processor, run_root, scenario, "B", "issue-refund",
        "import pyautogui,time; pyautogui.press('tab'); pyautogui.press('enter'); time.sleep(1)",
        guest_key_for["B"])
    time.sleep(1.5)
    if scenario == "positive":
        _logged_gui_action(processor, run_root, scenario, "B", "resolution-code",
                           "import pyautogui; pyautogui.press('space')",
                           guest_key_for["B"])
        _logged_gui_action(processor, run_root, scenario, "B", "resolution-note",
                           "import pyautogui; pyautogui.press('tab'); pyautogui.write("
                           "'Verified the damaged item and completed the supported refund.')",
                           guest_key_for["B"])
        _logged_gui_action(processor, run_root, scenario, "B", "resolve-ticket",
                           "import pyautogui,time; pyautogui.press('tab'); pyautogui.press('enter'); "
                           "time.sleep(1)", guest_key_for["B"])
    result = evaluate(run_root / "db" / case_spec.FIXTURE_DB,
                      hidden_manifest_path(run_root), condition)
    return {
        "scenario": scenario,
        "expected_business_success": scenario == "positive",
        "actor_steps": {role: sum(1 for line in (run_root / "gui_actions.jsonl").read_text().splitlines()
                                  if json.loads(line).get("scenario") == scenario
                                  and json.loads(line).get("actor") == role)
                        for role in ("A", "B")},
        "message_id": message.get("message_id"),
        "message_read_by_B": bool(received),
        "review_id": review["id"],
        "refund_attempt_screenshot": refund_attempt["screenshot"],
        "oracle": result,
    }


def _run_scripted_controls(run_root: Path, run_id: str, condition: str,
                           guests: dict[str, Any], actor_guest_keys: dict[str, str],
                           browser_profiles: dict[str, str], protocol_server: Any,
                           app_port: int, scenarios: tuple[str, ...] = ("positive", "negative")) -> dict[str, Any]:
    from oscombo.collab.ticket_to_resolution.database import CaseStore
    from oscombo.collab.ticket_to_resolution.runner import hidden_manifest_path

    outcomes: dict[str, Any] = {}
    started = time.monotonic()
    for scenario in scenarios:
        if outcomes:
            reset = _reset_for_next_control(
                run_root, run_id, condition, guests, actor_guest_keys, browser_profiles, app_port)
            outcomes.setdefault("resets", []).append(reset)
            if not reset["pristine_state_verified"]:
                raise RuntimeError("backend reset did not restore the pristine fixture")
        outcome = _control_gui_actions(
            run_root, run_id, scenario, condition, guests, actor_guest_keys,
            browser_profiles, app_port, {}, protocol_server)
        _write_json(run_root / "controls" / f"{scenario}-oracle.json", outcome["oracle"])
        outcomes[scenario] = outcome
    final_reset = _reset_for_next_control(
        run_root, run_id, condition, guests, actor_guest_keys, browser_profiles, app_port)
    outcomes["final_reset"] = final_reset
    if not final_reset["pristine_state_verified"]:
        raise RuntimeError("final backend reset did not restore the pristine fixture")
    outcomes["elapsed_s"] = round(time.monotonic() - started, 2)
    outcomes["input_interference"] = _input_overlap(run_root / "desktop_requests.jsonl")
    return outcomes


def _port_released(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _close_server(server: Any, thread: threading.Thread | None) -> None:
    if server is None:
        return
    try:
        server.shutdown()
    except Exception:
        pass
    try:
        server.server_close()
    except Exception:
        pass
    if thread is not None:
        thread.join(timeout=5)
    access_log = getattr(server, "access_log", None)
    if access_log is not None:
        try:
            access_log.close()
        except Exception:
            pass


def _close_guests(environments: dict[str, Any]) -> list[dict[str, Any]]:
    cleanup = []
    for key, env in reversed(list(environments.items())):
        provider = getattr(env, "provider", None)
        pid = getattr(getattr(provider, "process", None), "pid", None)
        overlay = Path(provider.overlay_path) if getattr(provider, "overlay_path", None) else None
        ports = getattr(provider, "manifest", {}).get("ports") or {}
        metrics_before = _process_metrics(pid)
        try:
            env.close()
            close_error = None
        except Exception as exc:
            close_error = type(exc).__name__
        released_ports = {name: _port_released(int(port)) for name, port in ports.items()}
        cleanup.append({
            "guest_key": key,
            "pid": pid,
            "metrics_before_close": metrics_before,
            "metrics_at_stop": getattr(provider, "manifest", {}).get("metrics_at_stop"),
            "qemu_alive_after_close": bool(_process_metrics(pid).get("alive")),
            "overlay_exists_after_close": bool(overlay and overlay.exists()),
            "forwarded_ports_released": released_ports,
            "close_error_type": close_error,
        })
    return cleanup


def run_controls(args: argparse.Namespace) -> int:
    from oscombo.collab.ticket_to_resolution.runner import make_plan
    from oscombo.collab.ticket_to_resolution.lite_v1 import CASE_ID, CASE_VERSION, SOURCE_CASE_ID

    run_root = args.run_root.absolute()
    run_id = args.run_id
    if not run_id.startswith("ttr-lite-") or "/" in run_id or "\\" in run_id:
        raise ValueError("run IDs must start with ttr-lite- and contain no path separators")
    if run_root.is_symlink() or (run_root.exists() and any(run_root.iterdir())):
        raise FileExistsError("run root exists and is non-empty; preserve it and choose a fresh path")
    run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_root.chmod(0o700)
    os.umask(0o077)
    _bypass_proxy_for_local_services()
    app_url = f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/login"
    from oscombo.collab.ticket_to_resolution.runner import prepare_run
    created = prepare_run(run_root, run_id)
    plan = make_plan(args.condition, run_id, app_url=app_url,
                     steps_per_role=15, tokens_per_role=12000)
    plan.update({"case_id": CASE_ID, "case_version": CASE_VERSION,
                 "source_case_id": SOURCE_CASE_ID, "case_variant": "lite-v1",
                 "model": None, "effort": None})
    _write_json(run_root / "run_config.json", plan)
    _write_json(run_root / "lite_version.json", {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "source_case_id": SOURCE_CASE_ID,
        "task_card": "oscombo/collab/ticket_to_resolution/lite_v1/TASK_CARD_ZH.md",
        "scripted_action_target": {"A": 6, "B": 7, "combined": 13},
    })
    credentials = json.loads((run_root / "secrets" / "browser_credentials.json").read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "schema": "codesk.ticket-to-resolution-lite.controls.v1",
        "run_id": run_id, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "source_case_id": SOURCE_CASE_ID, "condition": args.condition,
        "mode": "real_guest_scripted_controls", "status": "STARTING",
        "provider": "native-qemu-tcg", "acceleration": "TCG",
        "vcpus_per_guest": VCPUS, "ram_per_guest": RAM,
        "base_image": str(IMAGE), "base_image_sha256_before": BASE_IMAGE_SHA256,
        "base_image_fingerprint_before": _image_fingerprint(),
        "base_image_hash_basis": "full SHA-256 verified before and after the prior owned Guest setup",
        "model_called": False, "run_root": str(run_root), "created": created,
        "started_unix": time.time(), "setup": {}, "controls": {},
    }
    _write_json(run_root / "progress.json", report)
    envs: dict[str, Any] = {}
    guests: dict[str, Any] = {}
    proxies: list[ObservedGuest] = []
    case_server = protocol_server = None
    case_thread = protocol_thread = None
    service_port = None
    try:
        case_server, case_thread, protocol_server, protocol_thread, service_port = _start_services(
            run_root, run_id, credentials, "lite-v1")
        _configure_native_environment(run_root, run_id, service_port)
        from oscombo.osworld import activate
        from oscombo.combo import boot
        from oscombo.guest import Guest

        activate()
        if args.condition == "collaborative_shared":
            guest_keys = ("shared",)
            actor_guest_keys = {"A": "shared", "B": "shared"}
        elif args.condition == "collaborative_isolated":
            guest_keys = ("A", "B")
            actor_guest_keys = {"A": "A", "B": "B"}
        else:
            raise ValueError("scripted controls require shared or isolated collaboration")
        for key in guest_keys:
            cache = run_root / "cache" / key
            cache.mkdir(parents=True, exist_ok=True)
            os.environ.pop("OSCOMBO_NATIVE_QMP_SOCKET", None)
            report["stage"] = f"booting_guest_{key}"
            report["status"] = "GUEST_BOOT"
            _write_json(run_root / "progress.json", report)
            started = time.monotonic()
            env = boot(str(IMAGE), str(cache))
            envs[key] = env
            guests[key] = Guest(env)
            if env.provider.manifest.get("base_image_read_only") is not True:
                raise RuntimeError("native QEMU did not verify the base image as read-only")
            probes = report.setdefault("guest_http_probes", {}).setdefault(key, [])
            reachable = _guest_health_probe(guests[key])
            health_record = {"path": "health-before-capture-repair", **reachable}
            if reachable.get("returncode", 0) != 0 or '"ready":true' not in reachable.get("output", ""):
                health_record["network_diagnostic"] = _guest_network_diagnostic(guests[key])
                probes.append(health_record)
                _write_json(run_root / "progress.json", report)
                raise RuntimeError(f"Guest {key} direct connection to the shared case service failed")
            probes.append(health_record)
            capture_fix = _apply_guest_png_fix(guests[key], run_root, args.run_id, key)
            report.setdefault("guest_capture_fixes", {})[key] = capture_fix
            repeat_health = guests[key].execute([
                "/bin/bash", "-lc",
                f"curl --noproxy '*' --connect-timeout 5 --max-time 15 -fsS "
                f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/health",
            ], timeout=25)
            probes.append({"path": "health-repeat", "status": repeat_health.get("status"),
                           "returncode": repeat_health.get("returncode"),
                           "output": repeat_health.get("output", "")[-500:],
                           "error": repeat_health.get("error", "")[-500:]})
            if repeat_health.get("returncode", 0) != 0:
                probes[-1]["network_diagnostic"] = {
                    "guest": _guest_network_diagnostic(guests[key]),
                    "host": _host_network_diagnostic(env, service_port, run_root),
                }
                _write_json(run_root / "progress.json", report)
                raise RuntimeError(f"Guest {key} second request to the shared service failed")
            actor = "A" if key == "shared" else key
            login_url = f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/login?actor={actor}"
            probe = _guest_http_probe(guests[key], login_url)
            probes.append({"path": f"login-{actor}", **probe})
            if probe["returncode"] != 0:
                _write_json(run_root / "progress.json", report)
                raise RuntimeError(f"Guest {key} cannot fetch Case Desk login for {actor}: "
                                   f"{probe['error'] or probe['output']}")
            _write_json(run_root / "progress.json", report)
            desktop_readiness = _wait_for_guest_desktop(guests[key], run_root, key, report)
            report["setup"][key] = {
                "boot_s": round(time.monotonic() - started, 2),
                "desktop_readiness": desktop_readiness,
                "pid": env.provider.process.pid if env.provider.process else None,
                "qemu_version": env.provider.manifest.get("qemu_version"),
                "ports": env.provider.manifest.get("ports"),
                "guestfwd": env.provider.manifest.get("guestfwd"),
                "capture_fix": capture_fix,
                "host_case_service_reachable": True,
                "metrics_at_ready": _process_metrics(env.provider.process.pid if env.provider.process else None),
            }
            _write_json(run_root / "progress.json", report)

        browser_profiles, browser_report = _prepare_browsers(
            run_root, run_id, args.condition, credentials, guests, actor_guest_keys, service_port)
        expected_roles = ["A", "B"]
        session_actors = sorted(session["actor"] for session in case_server.sessions.values())
        distinct_sessions = (len(case_server.sessions) >= 2 and set(session_actors) == {"A", "B"})
        report["identity_check"] = {
            "browser_profiles": browser_profiles, "session_actors": session_actors,
            "expected_actors": expected_roles, "distinct_sessions": distinct_sessions,
        }
        report["browsers"] = browser_report
        if not distinct_sessions:
            raise RuntimeError("browser identity check failed before controls: expected authenticated "
                               f"A and B sessions, observed actors={session_actors!r}")
        report["role_to_guest"] = actor_guest_keys
        report["shared_backend"] = {
            "database_path": str(run_root / "db" / "case.sqlite3"),
            "host_bind": "127.0.0.1",
            "guest_service_address": f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}",
            "host_app_port": service_port,
            "all_guests_use_same_host_service": True,
        }
        report["status"] = "CONTROLS_RUNNING"
        _write_json(run_root / "progress.json", report)
        report["stage"] = "scripted_controls"
        report["controls"] = _run_scripted_controls(
            run_root, run_id, args.condition, guests, actor_guest_keys,
            browser_profiles, protocol_server, service_port, tuple(args.scenarios))
        positive = report["controls"].get("positive")
        positive_ok = (positive is None or (
            positive["oracle"]["joint_business_success"]
            and positive["actor_steps"] == {"A": 6, "B": 7}
            and positive["message_read_by_B"]
            and positive["oracle"]["process_evidence"]["review_opened_in_gui_by_B"]
        ))
        negative = report["controls"].get("negative")
        negative_oracle = (negative or {}).get("oracle", {})
        negative_observed = negative_oracle.get("observed", {})
        negative_process = negative_oracle.get("process_evidence", {})
        negative_rejection = negative_process.get("rejected_operations", [])
        negative_ok = (negative is None or (
            not negative_oracle.get("joint_business_success")
            and negative["actor_steps"] == {"A": 6, "B": 4}
            and negative["message_read_by_B"]
            # The negative control deliberately saves an incorrect total. It
            # must be authored by A, then independently rejected by B; it is
            # incorrect for this control to require a valid-review pass.
            and not negative_oracle.get("review_pass")
            and negative_observed.get("review_count") == 1
            and negative_observed.get("review_recorded_by_expected_actor")
            and negative_observed.get("refund_count") == 0
            and negative_observed.get("order_status") == "PAID"
            and negative_observed.get("order_remaining_cents") == 23500
            and negative_observed.get("ticket_status") == "REVIEWED"
            and negative_oracle.get("protected_state_pass")
            and negative_process.get("review_opened_in_gui_by_B")
            and negative_process.get("rejected_operation_count") == 1
            and negative_rejection[0].get("details_json", "").find('"error_code":"REVIEW_INVALID"') >= 0
        ))
        expected_scenarios = set(args.scenarios)
        report["controls_pass"] = bool(
            positive_ok and negative_ok and expected_scenarios
            == (set(report["controls"]) & {"positive", "negative"}))
        report["status"] = "CONTROL_PASS" if report["controls_pass"] else "CONTROL_FAIL"
    except Exception as exc:
        report["status"] = "INFRA_FAIL"
        report["failure"] = {"type": type(exc).__name__, "message": str(exc),
                             "traceback": traceback.format_exc()}
    finally:
        for proxy in proxies:
            proxy.close()
        _close_server(protocol_server, protocol_thread)
        _close_server(case_server, case_thread)
        report["cleanup"] = _close_guests(envs)
        report["cleanup_verified"] = all(
            not row["qemu_alive_after_close"] and not row["overlay_exists_after_close"]
            and row["close_error_type"] is None
            and all(row["forwarded_ports_released"].values()) for row in report["cleanup"])
        report["service_port_released"] = _port_released(service_port) if service_port else None
        report["protocol_port_released"] = (
            _port_released(protocol_server.server_port) if protocol_server else None)
        report["cleanup_verified"] = bool(
            report["cleanup_verified"] and report["service_port_released"]
            and report["protocol_port_released"])
        report["base_image_fingerprint_after"] = _image_fingerprint()
        report["base_image_unchanged"] = (
            report["base_image_fingerprint_before"] == report["base_image_fingerprint_after"])
        report["base_image_sha256_after"] = (
            BASE_IMAGE_SHA256 if report["base_image_unchanged"] else _sha256(IMAGE))
        report["elapsed_total_s"] = round(time.time() - report["started_unix"], 2)
        report["desktop_interference"] = _input_overlap(run_root / "desktop_requests.jsonl")
        _write_json(run_root / "result.json", report)
        _write_json(run_root / "progress.json", report)
        print(json.dumps({"run_id": run_id, "status": report["status"],
                          "controls_pass": report.get("controls_pass"),
                          "cleanup_verified": report.get("cleanup_verified"),
                          "run_root": str(run_root)}, ensure_ascii=False), flush=True)
    return 0 if report.get("controls_pass") and report.get("cleanup_verified") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("controls",), required=True)
    parser.add_argument("--condition", choices=("collaborative_shared", "collaborative_isolated"),
                        required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--scenarios", nargs="+", choices=("positive", "negative"),
                        default=("positive", "negative"))
    args = parser.parse_args()
    if args.run_root is None:
        args.run_root = RUNS / args.run_id
    return run_controls(args)


def _reset_for_next_control(run_root: Path, run_id: str, condition: str,
                            guests: dict[str, Any], actor_guest_keys: dict[str, str],
                            browser_profiles: dict[str, str], app_port: int) -> dict[str, Any]:
    from oscombo.collab.ticket_to_resolution.runner import reset_owned_run
    from oscombo.collab.ticket_to_resolution.database import CaseStore, business_snapshot, connect
    from oscombo.collab.ticket_to_resolution import spec as case_spec

    reset = reset_owned_run(run_root, run_id)
    roles = ("A", "B") if condition != "single_agent" else ("S",)
    for role in roles:
        key = actor_guest_keys[role]
        _switch_url(guests[key], role, browser_profiles[role],
                    f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/lite")
    state = business_snapshot(run_root / "db" / case_spec.FIXTURE_DB)
    store = CaseStore(run_root / "db" / case_spec.FIXTURE_DB)
    conn = connect(store.db_path)
    try:
        review_count = conn.execute("SELECT count(*) FROM reviews").fetchone()[0]
        refund_count = conn.execute("SELECT count(*) FROM refunds").fetchone()[0]
    finally:
        conn.close()
    target_ticket = next(row for row in state["tickets"] if row["id"] == case_spec.TICKET_ID)
    clean = target_ticket["status"] == "OPEN" and review_count == 0 and refund_count == 0
    return {**reset, "pristine_state_verified": clean}


def _boot_and_prepare(run_root: Path, run_id: str, condition: str, variant: str,
                      report: dict[str, Any], prepared: bool = False) -> tuple[
                          dict[str, Any], dict[str, Any], dict[str, str], Any,
                          threading.Thread, Any, threading.Thread, int,
                          dict[str, str], dict[str, Any]]:
    _bypass_proxy_for_local_services()
    if not prepared:
        _prepare_episode(run_root, run_id, condition,
                         f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}/login")
    credentials = json.loads((run_root / "secrets" / "browser_credentials.json").read_text(encoding="utf-8"))
    case_server, case_thread, protocol_server, protocol_thread, app_port = _start_services(
        run_root, run_id, credentials, variant)
    envs: dict[str, Any] = {}
    try:
        envs, guests, actor_guest_keys = _boot_desktops(run_root, run_id, condition, app_port, report)
        browser_profiles, browser_report = _prepare_browsers(
            run_root, run_id, condition, credentials, guests, actor_guest_keys, app_port)
        service_url = f"http://{GUEST_SERVICE_HOST}:{GUEST_SERVICE_PORT}"
        report["browsers"] = browser_report
        report["shared_backend"] = {
            "host_service_bind": "127.0.0.1",
            "guest_address": service_url,
            "host_port_forwarded_to_all_guests": app_port,
            "database_path": str(run_root / "db" / "case.sqlite3"),
            "backend_topology": "one host service and one run-scoped database for all role sessions",
        }
        expected = ["S"] if condition == "single_agent" else ["A", "B"]
        session_actors = sorted(session["actor"] for session in case_server.sessions.values())
        if session_actors != expected:
            raise RuntimeError(f"Guest browser sessions do not match the assigned roles: {session_actors}")
        report["identity_check"] = {
            "actor_passwords_are_run_scoped": True,
            "browser_profiles": browser_profiles,
            "session_actors": session_actors,
            "expected_actors": expected,
        }
        return (envs, guests, actor_guest_keys, case_server, case_thread, protocol_server,
                protocol_thread, app_port, browser_profiles, credentials)
    except Exception:
        guest_cleanup = _close_guests(envs)
        if not guest_cleanup:
            guest_setup = report.get("guest_setup_failure_cleanup") or {}
            guest_cleanup = guest_setup.get("guests", [])
        stage = report.get("stage")
        guest_verified = all(
            not row["qemu_alive_after_close"] and not row["overlay_exists_after_close"]
            and row["close_error_type"] is None
            and all(row["forwarded_ports_released"].values()) for row in guest_cleanup)
        if not guest_cleanup and not (isinstance(stage, str) and stage.startswith("booting_guest_")):
            guest_verified = True
        case_port = case_server.server_port if case_server else None
        protocol_port = protocol_server.server_port if protocol_server else None
        _close_server(protocol_server, protocol_thread)
        _close_server(case_server, case_thread)
        service_released = _port_released(case_port) if case_port else True
        protocol_released = _port_released(protocol_port) if protocol_port else True
        report["setup_failure_cleanup"] = {
            "guests": guest_cleanup, "guest_cleanup_verified": guest_verified,
            "service_port_released": service_released,
            "protocol_port_released": protocol_released,
            "verified": bool(guest_verified and service_released and protocol_released),
        }
        _write_json(run_root / "progress.json", report)
        raise


if __name__ == "__main__":
    _ensure_guest_runtime_libraries()
    raise SystemExit(main())

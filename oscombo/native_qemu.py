"""Native host QEMU provider for the pinned OSWorld DesktopEnv API.

It intentionally uses the official Guest HTTP server through QEMU user-mode port
forwarding.  Only VM lifecycle is implemented here; screenshot, input, reset and
task setup remain OSWorld's existing controllers and DesktopEnv implementation.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import shlex
import signal
import sys
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from .qemu_image_ops import create_guest_overlay, inspect_base_image, readonly_backed_disk_args
from desktop_env.providers.base import Provider, VMManager


DEFAULT_STATE_ROOT = Path("/opt/data/private/mjh/runs/codesk/native-qemu")
PORTS = {"server": 5000, "vnc": 8006, "vlc": 8080, "chromium": 9222}


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return value[:100] or "manual"


def _available_port(used: set[int], preferred: int) -> int:
    for port in range(preferred, 65500):
        if port in used:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
        used.add(port)
        return port
    raise RuntimeError(f"no free loopback port near {preferred}")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _proc_metrics(pid: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().split()
        ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        result["cpu_user_s"] = round(int(fields[13]) / ticks, 2)
        result["cpu_system_s"] = round(int(fields[14]) / ticks, 2)
        status = Path(f"/proc/{pid}/status").read_text()
        for key in ("VmRSS", "VmHWM"):
            match = re.search(rf"^{key}:\s+(\d+)\s+kB$", status, re.M)
            if match:
                result[key.lower() + "_mib"] = round(int(match.group(1)) / 1024, 1)
    except (FileNotFoundError, IndexError, ValueError, PermissionError):
        pass
    return result


def _owned_qemu_pid(manifest: dict[str, Any], run_id: str) -> tuple[int | None, str | None]:
    """Find a QEMU only when both its executable and random CoDesk instance name match the manifest."""
    expected_name = f"oscombo-{_safe_name(run_id)}-{str(manifest.get('instance_id', ''))[:8]}"
    expected_binary = str(manifest.get("qemu", ""))
    if not expected_binary or not manifest.get("instance_id"):
        return None, None
    requested_pid = int(manifest.get("pid", 0) or 0)
    candidates = [requested_pid] if requested_pid > 1 else []
    try:
        candidates.extend(int(entry.name) for entry in os.scandir("/proc") if entry.name.isdigit())
    except OSError:
        pass
    seen: set[int] = set()
    for pid in candidates:
        if pid in seen:
            continue
        seen.add(pid)
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            args = [item.decode(errors="replace") for item in argv if item]
        except (OSError, ProcessLookupError):
            continue
        # A private glibc loader wrapper leaves the loader at argv[0], followed by
        # --argv0 <wrapper path> ... <QEMU binary>. Accept that exact shape only
        # when the process executable is the private loader and the expected
        # randomized instance name is present in the same command line.
        try:
            proc_exe = Path(f"/proc/{pid}/exe").resolve()
        except OSError:
            proc_exe = Path()
        is_direct = bool(args and args[0] == expected_binary)
        is_private_loader = ("--argv0" in args and expected_binary in args
                             and proc_exe.name == "ld-linux-x86-64.so.2")
        if (is_direct or is_private_loader) and "-name" in args:
            index = args.index("-name")
            if index + 1 < len(args) and args[index + 1] == expected_name:
                return pid, "manifest_pid" if pid == requested_pid else "exact_cmdline_recovery"
    return None, None


class NativeQemuVMManager(VMManager):
    """OSWorld manager shim; the user supplies the immutable base qcow2 directly."""

    def initialize_registry(self, **kwargs):
        return None

    def add_vm(self, vm_path, **kwargs):
        return None

    def delete_vm(self, vm_path, **kwargs):
        return None

    def occupy_vm(self, vm_path, pid, **kwargs):
        return None

    def list_free_vms(self, **kwargs):
        return []

    def check_and_clean(self, **kwargs):
        return None

    def get_vm_path(self, os_type, **kwargs):
        raise RuntimeError("native-qemu-tcg requires an explicit OSWORLD_GUEST_IMAGE qcow2 path")


class NativeQemuTcgProvider(Provider):
    """Start one OSWorld qcow2 Guest with host QEMU TCG and user-mode networking."""

    def __init__(self, region: str | None = None):
        super().__init__(region)
        self.process: subprocess.Popen | None = None
        self.server_port: int | None = None
        self.vnc_port: int | None = None
        self.chromium_port: int | None = None
        self.vlc_port: int | None = None
        self.instance_id = uuid.uuid4().hex
        self.run_id = _safe_name(os.environ.get("OSCOMBO_RUN_LABEL", "manual"))
        configured = os.environ.get("OSCOMBO_NATIVE_STATE_DIR")
        self.state_root = Path(configured).expanduser().resolve() if configured else DEFAULT_STATE_ROOT / self.run_id
        self.instance_dir = self.state_root / "guests" / self.instance_id
        self.overlay_path: Path | None = None
        self.manifest_path = self.instance_dir / "manifest.json"
        self.manifest: dict[str, Any] = {
            "schema": "oscombo.native-qemu.v1", "owner": "CoDesk", "run_id": self.run_id,
            "instance_id": self.instance_id, "status": "created", "created_unix": time.time(),
        }
        self._lock = threading.RLock()
        self._port_lock_handle = None

    def _write_manifest(self) -> None:
        self.instance_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(self.manifest_path, self.manifest)

    def _port_bundle(self) -> dict[str, int]:
        lock_path = Path(os.environ.get("OSCOMBO_NATIVE_PORT_LOCK",
                                      str(DEFAULT_STATE_ROOT / ".port-allocation.lock"))).expanduser()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock = open(lock_path, "a+")
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            used: set[int] = set()
            starts = dict(PORTS)
            if os.environ.get("OSCOMBO_NATIVE_DIAG_SSH") == "1":
                starts["ssh"] = 10022
            ports = {name: _available_port(used, start) for name, start in starts.items()}
            self._port_lock_handle = lock
            return ports
        except Exception:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()
            raise

    def _release_port_lock(self) -> None:
        lock = self._port_lock_handle
        self._port_lock_handle = None
        if lock is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    def _wait_host_forwards(self, ports: dict[str, int], timeout: float = 10) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                raise RuntimeError(f"QEMU exited while binding forwarded ports: {self.process.returncode}")
            bound = []
            for port in ports.values():
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind(("127.0.0.1", port))
                    except OSError:
                        bound.append(True)
                    else:
                        bound.append(False)
            if all(bound):
                return
            time.sleep(0.05)
        raise TimeoutError(f"QEMU did not bind all forwarded host ports in {timeout:.0f}s")

    @staticmethod
    def _binary(env_name: str, fallback: Path) -> str:
        value = os.environ.get(env_name)
        path = Path(value).expanduser() if value else fallback
        found = shutil.which(str(path)) if not path.is_absolute() else str(path)
        if not found or not Path(found).is_file() or not os.access(found, os.X_OK):
            raise RuntimeError(f"{env_name} executable not found: {path}")
        return str(Path(found).resolve())

    @staticmethod
    def _prefix() -> Path:
        return Path(os.environ.get("OSCOMBO_QEMU_PREFIX", "/opt/data/private/mjh/deps/qemu/ubuntu-focal")).expanduser()

    def _qemu(self) -> str:
        return self._binary("OSCOMBO_QEMU", self._prefix() / "usr/bin/qemu-system-x86_64")

    def _qemu_img(self) -> str:
        return self._binary("OSCOMBO_QEMU_IMG", self._prefix() / "usr/bin/qemu-img")

    @staticmethod
    def _runtime_env() -> dict[str, str]:
        env = dict(os.environ)
        prefix = NativeQemuTcgProvider._prefix()
        private_libs = [str(prefix / "usr/lib/x86_64-linux-gnu"), str(prefix / "usr/lib"),
                        str(prefix / "lib/x86_64-linux-gnu"), str(prefix / "lib")]
        # Keep QEMU on its packaged libraries. In particular, inherited user
        # LD_LIBRARY_PATH entries can override dependencies. A private-loader
        # wrapper passes --library-path directly, so leave the variable empty:
        # even its /bin/sh interpreter must not load private libc pre-exec.
        if env.get("OSCOMBO_QEMU_PRIVATE_LOADER", "").strip().lower() in {"1", "true", "yes"}:
            env["LD_LIBRARY_PATH"] = ""
        else:
            env["LD_LIBRARY_PATH"] = os.pathsep.join(private_libs)
        data_dir = prefix / "usr/share/qemu"
        if data_dir.is_dir():
            env["QEMU_DATA_DIR"] = str(data_dir)
        module_dir = prefix / "usr/lib/x86_64-linux-gnu/qemu"
        if module_dir.is_dir():
            env["QEMU_MODULE_DIR"] = str(module_dir)
        return env

    def prepare_volume(self, path_to_vm: str, volume_size: int | None, os_type: str):
        if volume_size:
            raise NotImplementedError("native-qemu-tcg currently uses the fixed OSWorld base disk size")

    def start_emulator(self, path_to_vm: str, headless: bool, os_type: str | None = None, *args, **kwargs):
        with self._lock:
            if self.process and self.process.poll() is None:
                raise RuntimeError("native QEMU Guest is already running")
            base = Path(path_to_vm).expanduser().resolve(strict=True)
            guestfwd_raw = os.environ.get("OSCOMBO_NATIVE_GUESTFWD", "[]")
            try:
                guestfwd = json.loads(guestfwd_raw)
            except json.JSONDecodeError as exc:
                raise ValueError("OSCOMBO_NATIVE_GUESTFWD must be a JSON list of guest_port/host_port objects") from exc
            if not isinstance(guestfwd, list):
                raise ValueError("OSCOMBO_NATIVE_GUESTFWD must be a JSON list")
            guest_ports: set[int] = set()
            for entry in guestfwd:
                if not isinstance(entry, dict):
                    raise ValueError("each native guestfwd entry must be an object")
                guest_port = int(entry.get("guest_port", 0))
                host_port = int(entry.get("host_port", 0))
                if not 1 <= guest_port <= 65535 or not 1 <= host_port <= 65535:
                    raise ValueError("native guestfwd ports must be in 1..65535")
                if guest_port in guest_ports:
                    raise ValueError(f"duplicate native guestfwd guest port: {guest_port}")
                guest_ports.add(guest_port)
            qemu, qemu_img = self._qemu(), self._qemu_img()
            self.instance_dir.mkdir(parents=True, exist_ok=True)
            self.overlay_path = self.instance_dir / "guest-overlay.qcow2"
            if self.overlay_path.exists():
                self.overlay_path.unlink()
            image_info = inspect_base_image(qemu_img, base, self._runtime_env())
            create_guest_overlay(qemu_img, base, self.overlay_path,
                                 int(image_info.get("virtual-size", 0)), self._runtime_env())

            ram = os.environ.get("OSCOMBO_NATIVE_RAM", "4G")
            cpus = os.environ.get("OSCOMBO_NATIVE_CPUS", "2")
            vcpus = int(cpus)
            boot_timeout = float(os.environ.get("OSCOMBO_NATIVE_BOOT_TIMEOUT", "600"))
            if vcpus < 1 or boot_timeout <= 0:
                raise ValueError("OSCOMBO_NATIVE_CPUS and OSCOMBO_NATIVE_BOOT_TIMEOUT must be positive")
            qemu_version = self._version(qemu)
            ports = self._port_bundle()
            self.server_port = ports["server"]
            self.vnc_port = ports["vnc"]
            self.vlc_port = ports["vlc"]
            self.chromium_port = ports["chromium"]
            serial_log = self.instance_dir / "serial.log"
            qemu_log = self.instance_dir / "qemu.log"
            guestfwd_log = self.instance_dir / "guestfwd-relay.jsonl"
            pidfile = self.instance_dir / "qemu.pid"
            forwarding = ",".join((
                f"hostfwd=tcp:127.0.0.1:{self.server_port}-:5000",
                f"hostfwd=tcp:127.0.0.1:{self.vnc_port}-:8006",
                f"hostfwd=tcp:127.0.0.1:{self.vlc_port}-:8080",
                f"hostfwd=tcp:127.0.0.1:{self.chromium_port}-:9222",
            ))
            if "ssh" in ports:
                forwarding += f",hostfwd=tcp:127.0.0.1:{ports['ssh']}-:22"
            guestfwd_proxy = Path(__file__).with_name("qemu_guestfwd_proxy.py").resolve()
            if guestfwd and not guestfwd_proxy.is_file():
                raise RuntimeError(f"QEMU guestfwd proxy helper is missing: {guestfwd_proxy}")
            for entry in guestfwd:
                guest_port = int(entry["guest_port"])
                host_port = int(entry["host_port"])
                # A direct -tcp: target is backed by one QEMU chardev and in
                # practice only serves the first TCP connection.  The cmd:
                # backend starts a fresh byte-stream relay for every Guest
                # connection, allowing health checks and later API calls too.
                proxy_command = shlex.join((sys.executable, str(guestfwd_proxy), str(host_port),
                                            str(guestfwd_log)))
                forwarding += f",guestfwd=tcp:10.0.2.100:{guest_port}-cmd:{proxy_command}"
            try:
                cmd = [qemu, "-L", str(self._prefix() / "usr/share/qemu"), "-name",
                       f"oscombo-{self.run_id}-{self.instance_id[:8]}", "-machine", "pc",
                       "-accel", "tcg,thread=multi", "-cpu",
                       os.environ.get("OSCOMBO_NATIVE_CPU_MODEL", "Haswell-noTSX"),
                       "-m", ram, "-smp", cpus, "-rtc", "base=utc",
                       *readonly_backed_disk_args(base, self.overlay_path),
                       "-netdev", f"user,id=net0,restrict=off,{forwarding}", "-device", "e1000,netdev=net0",
                       "-vga", "std", "-display", "none", "-monitor", "none", "-serial", f"file:{serial_log}",
                       "-pidfile", str(pidfile), "-boot", "order=c"]
                no_reboot = os.environ.get("OSCOMBO_NATIVE_NO_REBOOT", "1").strip().lower()
                if no_reboot not in {"0", "false", "no", "off"}:
                    cmd.append("-no-reboot")
                qmp_socket = os.environ.get("OSCOMBO_NATIVE_QMP_SOCKET")
                if qmp_socket:
                    qmp_path = Path(qmp_socket).expanduser().resolve()
                    qmp_path.parent.mkdir(parents=True, exist_ok=True)
                    cmd.extend(["-qmp", f"unix:{qmp_path},server=on,wait=off"])
                uefi_firmware = os.environ.get("OSCOMBO_NATIVE_UEFI_FIRMWARE")
                if uefi_firmware:
                    firmware_path = Path(uefi_firmware).expanduser().resolve(strict=True)
                    cmd.extend(["-bios", str(firmware_path)])
                self.manifest.update({"status": "starting", "base_image": str(base),
                                      "base_image_read_only": True, "overlay": str(self.overlay_path),
                                      "overlay_owned": True, "qemu": qemu, "qemu_version": qemu_version,
                                      "pidfile": str(pidfile), "ports": ports, "guestfwd": guestfwd,
                                      "acceleration": "tcg",
                                      "vcpus": vcpus, "ram": ram, "boot_timeout_s": boot_timeout,
                                      "started_unix": time.time(), "command": cmd,
                                      "guestfwd_log": str(guestfwd_log) if guestfwd else None})
                if uefi_firmware:
                    self.manifest["uefi_firmware"] = str(firmware_path)
                self._write_manifest()
                qemu_log_handle = open(qemu_log, "ab", buffering=0)
                try:
                    self.process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=qemu_log_handle,
                                                    stderr=subprocess.STDOUT, close_fds=True,
                                                    env=self._runtime_env())
                finally:
                    qemu_log_handle.close()
                self.manifest.update({"status": "booting", "pid": self.process.pid})
                self._write_manifest()
                self._wait_host_forwards(ports)
                self._release_port_lock()
            except Exception as exc:
                self._release_port_lock()
                if self.process is not None:
                    self.stop_emulator(path_to_vm)
                else:
                    self.manifest.update({"status": "spawn_failed", "base_image": str(base),
                                          "overlay": str(self.overlay_path), "overlay_owned": True,
                                          "error": f"{type(exc).__name__}: {exc}"})
                    if self.overlay_path.exists():
                        self.overlay_path.unlink()
                        self.manifest["overlay_removed"] = True
                    self._write_manifest()
                raise
            try:
                self._wait_ready(boot_timeout)
            except Exception as exc:
                self.manifest.update({"status": "readiness_failed", "error": f"{type(exc).__name__}: {exc}",
                                      "metrics": self._metrics()})
                self._write_manifest()
                self.stop_emulator(path_to_vm)
                raise
            self.manifest.update({"status": "ready", "ready_unix": time.time(),
                                  "startup_s": round(time.time() - self.manifest["started_unix"], 2),
                                  "metrics_at_ready": self._metrics()})
            self._write_manifest()

    @staticmethod
    def _version(qemu: str) -> str:
        result = subprocess.run([qemu, "--version"], capture_output=True, text=True, timeout=10,
                                env=NativeQemuTcgProvider._runtime_env())
        return result.stdout.splitlines()[0] if result.stdout else "unknown"

    def _wait_ready(self, timeout: float) -> None:
        assert self.process is not None and self.server_port is not None
        deadline = time.monotonic() + timeout
        last_error = "no response"
        url = f"http://127.0.0.1:{self.server_port}/screenshot"
        while time.monotonic() < deadline:
            status = self.process.poll()
            if status is not None:
                tail = (self.instance_dir / "qemu.log").read_text(errors="replace")[-3000:]
                raise RuntimeError(f"QEMU exited during boot (status {status}): {tail}")
            try:
                response = requests.get(url, timeout=(3, 60))
                if response.status_code == 200 and response.content:
                    return
                last_error = f"HTTP {response.status_code}"
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(3)
        raise TimeoutError(f"Guest screenshot endpoint not ready in {timeout:.0f}s; last error: {last_error}")

    def _metrics(self) -> dict[str, Any]:
        result = _proc_metrics(self.process.pid) if self.process else {}
        if self.overlay_path and self.overlay_path.exists():
            disk = self.overlay_path.stat()
            result["overlay_bytes"] = disk.st_size
            result["overlay_allocated_bytes"] = disk.st_blocks * 512
        if self.process:
            result["process_alive"] = self.process.poll() is None
        return result

    def get_ip_address(self, path_to_vm: str) -> str:
        if not all((self.server_port, self.chromium_port, self.vnc_port, self.vlc_port)):
            raise RuntimeError("native QEMU Guest has not allocated its forwarded ports")
        return f"127.0.0.1:{self.server_port}:{self.chromium_port}:{self.vnc_port}:{self.vlc_port}"

    def save_state(self, path_to_vm: str, snapshot_name: str):
        raise NotImplementedError("native-qemu-tcg reset creates a clean overlay; snapshots are not implemented")

    def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str) -> str:
        self.stop_emulator(path_to_vm)
        return path_to_vm

    def stop_emulator(self, path_to_vm: str, region=None, *args, **kwargs):
        with self._lock:
            proc = self.process
            if proc is None:
                return
            metrics_before_stop = self._metrics()
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=float(os.environ.get("OSCOMBO_NATIVE_STOP_TIMEOUT", "30")))
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
            metrics = self._metrics()
            self.manifest.update({"status": "stopped", "stopped_unix": time.time(), "metrics_at_stop": metrics,
                                  "metrics_before_stop": metrics_before_stop, "exit_code": proc.returncode})
            pidfile = Path(self.manifest.get("pidfile", ""))
            try:
                if pidfile.is_file() and pidfile.resolve().is_relative_to(self.instance_dir.resolve()):
                    if pidfile.read_text().strip() == str(proc.pid):
                        pidfile.unlink()
                        self.manifest["pidfile_removed"] = True
            except OSError as exc:
                self.manifest["pidfile_cleanup_error"] = str(exc)
            if self.overlay_path and self.overlay_path.exists():
                try:
                    self.overlay_path.unlink()
                    self.manifest["overlay_removed"] = True
                except OSError as exc:
                    self.manifest["overlay_removed"] = False
                    self.manifest["cleanup_error"] = str(exc)
            self._write_manifest()
            self.process = None
            self.server_port = self.vnc_port = self.vlc_port = self.chromium_port = None


def cleanup_native_run(run_id: str, state_root: Path | str | None = None) -> dict[str, Any]:
    """Stop only QEMU processes named and recorded inside this exact CoDesk run directory."""
    root = Path(state_root or os.environ.get("OSCOMBO_NATIVE_STATE_DIR", DEFAULT_STATE_ROOT / _safe_name(run_id)))
    root = root.expanduser().resolve()
    result: dict[str, Any] = {"run_id": _safe_name(run_id), "state_root": str(root), "stopped": [],
                              "stale_overlays_removed": [], "skipped": []}
    guests = root / "guests"
    if not guests.is_dir():
        result["status"] = "no_owned_guests"
        return result
    for manifest_path in guests.glob("*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("owner") != "CoDesk" or manifest.get("run_id") != _safe_name(run_id):
                result["skipped"].append({"manifest": str(manifest_path), "reason": "ownership mismatch"})
                continue
            pidfile = Path(manifest.get("pidfile", ""))
            qemu_pid, pid_source = _owned_qemu_pid(manifest, run_id)
            # Never signal a PID merely because it appears in a pidfile or manifest:
            # PID reuse and stale files must not affect another user's process.
            pid = qemu_pid or 0
            instance_id = str(manifest.get("instance_id", ""))
            cmdline_path = Path(f"/proc/{pid}/cmdline")
            overlay = Path(manifest.get("overlay", ""))
            owned_overlay = (overlay.is_file() and overlay.resolve().is_relative_to((root / "guests").resolve()))
            if pid <= 1 or not cmdline_path.exists():
                if owned_overlay:
                    overlay.unlink()
                    if pidfile.is_file() and pidfile.resolve().is_relative_to((root / "guests").resolve()):
                        try:
                            if pidfile.read_text().strip() == str(pid):
                                pidfile.unlink()
                        except OSError:
                            pass
                    manifest.update({"status": "stale_overlay_cleaned", "cleaned_unix": time.time(),
                                     "cleanup_owned": True, "overlay_removed": True})
                    _atomic_json(manifest_path, manifest)
                    result["stale_overlays_removed"].append({"pid": pid, "instance_id": instance_id})
                else:
                    result["skipped"].append({"pid": pid, "reason": "process absent; no owned overlay"})
                continue
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and Path(f"/proc/{pid}/cmdline").exists():
                time.sleep(0.2)
            if Path(f"/proc/{pid}/cmdline").exists():
                os.kill(pid, signal.SIGKILL)
            if owned_overlay:
                overlay.unlink()
            if pidfile.is_file() and pidfile.resolve().is_relative_to((root / "guests").resolve()):
                try:
                    if pidfile.read_text().strip() == str(pid):
                        pidfile.unlink()
                except OSError:
                    pass
            manifest.update({"status": "cleaned_after_parent_exit", "cleaned_unix": time.time(),
                             "cleanup_owned": True, "overlay_removed": not overlay.exists()})
            _atomic_json(manifest_path, manifest)
            result["stopped"].append({"pid": pid, "pid_source": pid_source, "instance_id": instance_id,
                                      "overlay_removed": not overlay.exists()})
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            result["skipped"].append({"manifest": str(manifest_path), "reason": f"{type(exc).__name__}: {exc}"})
    result["status"] = ("cleaned" if result["stopped"] or result["stale_overlays_removed"]
                        else "no_live_owned_guest")
    return result

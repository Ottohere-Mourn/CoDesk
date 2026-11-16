"""Native host QEMU + hardware KVM provider compatible with OSWorld DesktopEnv and swcub ledgers."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

import requests


PORTS = {"server": 5000, "vnc": 8006, "vlc": 8080, "chromium": 9222}


def verify_host_kvm_access() -> dict[str, Any]:
    descriptor = os.open("/dev/kvm", os.O_RDWR | os.O_CLOEXEC)
    try:
        api_version = fcntl.ioctl(descriptor, 0xAE00, 0)
    finally:
        os.close(descriptor)
    return {"open_read_write": True, "kvm_api_version": api_version}


def _safe_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return cleaned[:96] or "manual"


def _find_free_port(used: set[int], start_port: int) -> int:
    for candidate in range(start_port, 65000):
        if candidate in used:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
        used.add(candidate)
        return candidate
    raise RuntimeError(f"No free loopback port starting from {start_port}")


class _ContainerMetadataShim:
    """Expose read-only mount and ownership label metadata expected by Case 3/4 and swcub."""

    def __init__(self, resource_id: str, labels: dict[str, str], base_image: Path, overlay_path: Path):
        self.id = resource_id
        self.attrs = {
            "Id": resource_id,
            "Config": {"Labels": dict(labels)},
            "Mounts": [
                {"Source": str(base_image), "Destination": "/System.qcow2", "RW": False},
                {"Source": str(overlay_path), "Destination": "/vm-overlay", "RW": True},
            ],
        }

    def reload(self) -> None:
        return None


def install_native_kvm_into_osworld() -> None:
    """Register NativeQemuKvmProvider as the OSWorld 'docker' provider when CODESK_USE_NATIVE_KVM=1."""
    if os.environ.get("CODESK_USE_NATIVE_KVM", "1") != "1":
        return
    import desktop_env.providers as providers_pkg
    from desktop_env.providers.base import Provider, VMManager

    if getattr(providers_pkg, "_codesk_native_kvm_installed", False):
        return

    class NativeKvmVMManager(VMManager):
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
            configured = os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE") or os.environ.get("OSCOMBO_GUEST_IMAGE")
            if not configured:
                raise RuntimeError("Explicit OSWorld Guest qcow2 path required")
            return configured

    class NativeQemuKvmProvider(Provider):
        def __init__(self, region: str | None = None):
            super().__init__(region)
            self.process: subprocess.Popen | None = None
            self.server_port: int | None = None
            self.vnc_port: int | None = None
            self.chromium_port: int | None = None
            self.vlc_port: int | None = None
            self.instance_id = uuid.uuid4().hex
            self.resource_id = hashlib.sha256(f"native-kvm:{self.instance_id}:{time.time_ns()}".encode()).hexdigest()
            self.container: _ContainerMetadataShim | None = None
            self._lock = threading.RLock()
            self._port_lock_handle = None
            self.overlay_path: Path | None = None
            self.instance_dir: Path | None = None
            self.manifest: dict = {}

        @staticmethod
        def _qemu_prefix() -> Path:
            return Path(os.environ["CODESK_QEMU_PREFIX"]).expanduser().resolve()

        @classmethod
        def _qemu_env(cls) -> dict[str, str]:
            prefix = cls._qemu_prefix()
            libs = [
                str(prefix / "usr/lib/x86_64-linux-gnu"),
                str(prefix / "lib/x86_64-linux-gnu"),
                str(prefix / "usr/lib"),
                str(prefix / "lib"),
            ]
            env = dict(os.environ)
            env["LD_LIBRARY_PATH"] = os.pathsep.join(libs)
            env["QEMU_DATA_DIR"] = str(prefix / "usr/share/qemu")
            module_dir = prefix / "usr/lib/x86_64-linux-gnu/qemu"
            if module_dir.is_dir():
                env["QEMU_MODULE_DIR"] = str(module_dir)
            return env

        def prepare_volume(self, path_to_vm: str, volume_size: int | None, os_type: str):
            return None

        def finalize_volume(self, *args, **kwargs):
            return None

        def _allocate_ports(self, state_root: Path) -> dict[str, int]:
            lock_file = Path(os.environ.get("CODESK_PORT_LOCK_FILE", str(state_root.parent / ".kvm-ports.lock")))
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            handle = open(lock_file, "a+")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                used: set[int] = set()
                allocated = {name: _find_free_port(used, start) for name, start in PORTS.items()}
                self._port_lock_handle = handle
                return allocated
            except Exception:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
                raise

        def _release_port_lock(self) -> None:
            handle = self._port_lock_handle
            self._port_lock_handle = None
            if handle is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()

        def _record_ledger(self, event: str, **details: Any) -> dict[str, str]:
            run_id = os.environ.get("SWCUB_RUN_ID") or os.environ.get("OSCOMBO_RUN_LABEL") or "manual"
            owner_token = os.environ.get("SWCUB_OWNER_TOKEN", "")
            labels = {
                "oscombo": "1",
                "oscombo.run": run_id,
                "org.swcub.project": "shared-workspace-benchmark-v0",
                "org.swcub.run-id": run_id,
                "org.swcub.owner-token": owner_token,
                "org.codesk.backend": "native-qemu-kvm",
            }
            ledger_raw = os.environ.get("SWCUB_RESOURCE_LEDGER")
            if ledger_raw:
                ledger_path = Path(ledger_raw).expanduser().resolve()
                ledger_path.parent.mkdir(parents=True, exist_ok=True)
                row = {
                    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "event": event,
                    "resource_type": "container",
                    "resource_id": self.resource_id,
                    "project": "shared-workspace-benchmark-v0",
                    "run_id": run_id,
                    "labels": {
                        "org.swcub.project": "shared-workspace-benchmark-v0",
                        "org.swcub.run-id": run_id,
                        "org.swcub.owner-token": owner_token,
                    },
                    "backend": "native-qemu-kvm",
                    **details,
                }
                encoded = (json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
                descriptor = os.open(ledger_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    os.write(descriptor, encoded)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return labels

        def start_emulator(self, path_to_vm: str, headless: bool, os_type: str | None = None, *args, **kwargs):
            with self._lock:
                verify_host_kvm_access()
                base_image = Path(path_to_vm).expanduser().resolve(strict=True)
                prefix = self._qemu_prefix()
                qemu_bin = str(prefix / "usr/bin/qemu-system-x86_64")
                qemu_img = str(prefix / "usr/bin/qemu-img")
                run_id = _safe_label(os.environ.get("SWCUB_RUN_ID") or os.environ.get("OSCOMBO_RUN_LABEL") or "manual")
                overlay_root = Path(
                    os.environ.get("SWCUB_OSWORLD_OVERLAY_HOST_DIR")
                    or os.environ.get("OSCOMBO_OVERLAY_DIR")
                    or os.environ.get("OSCOMBO_NATIVE_STATE_DIR")
                    or f"/tmp/codesk-kvm-{run_id}"
                ).expanduser().resolve()
                self.instance_dir = overlay_root / f"kvm-{self.instance_id[:12]}"
                self.instance_dir.mkdir(parents=True, exist_ok=True)
                self.overlay_path = self.instance_dir / "overlay.qcow2"
                if self.overlay_path.exists():
                    self.overlay_path.unlink()
                subprocess.run(
                    [qemu_img, "create", "-q", "-f", "qcow2", "-F", "qcow2", "-b", str(base_image), str(self.overlay_path)],
                    env=self._qemu_env(),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                ports = self._allocate_ports(overlay_root)
                self.server_port = ports["server"]
                self.vnc_port = ports["vnc"]
                self.vlc_port = ports["vlc"]
                self.chromium_port = ports["chromium"]
                forwarding = ",".join((
                    f"hostfwd=tcp:127.0.0.1:{self.server_port}-:5000",
                    f"hostfwd=tcp:127.0.0.1:{self.vnc_port}-:8006",
                    f"hostfwd=tcp:127.0.0.1:{self.vlc_port}-:8080",
                    f"hostfwd=tcp:127.0.0.1:{self.chromium_port}-:9222",
                ))
                guestfwd_raw = os.environ.get("OSCOMBO_NATIVE_GUESTFWD", "[]")
                guestfwd = json.loads(guestfwd_raw)
                guestfwd_proxy = os.environ.get("CODESK_GUESTFWD_PROXY")
                for entry in guestfwd:
                    guest_port = int(entry["guest_port"])
                    host_port = int(entry["host_port"])
                    if not guestfwd_proxy:
                        raise RuntimeError("CODESK_GUESTFWD_PROXY required when OSCOMBO_NATIVE_GUESTFWD is set")
                    proxy_cmd = shlex.join((
                        "/usr/bin/env",
                        "-u",
                        "LD_LIBRARY_PATH",
                        "-u",
                        "PYTHONPATH",
                        sys.executable,
                        "-S",
                        "-W",
                        "ignore",
                        guestfwd_proxy,
                        str(host_port),
                        str(self.instance_dir / "guestfwd.jsonl"),
                    ))
                    forwarding += f",guestfwd=tcp:10.0.2.100:{guest_port}-cmd:{proxy_cmd}"
                ram = os.environ.get("CODESK_GUEST_RAM", "6G")
                cpus = os.environ.get("CODESK_GUEST_CPUS", "4")
                serial_log = self.instance_dir / "serial.log"
                qemu_log = self.instance_dir / "qemu.log"
                pid_file = self.instance_dir / "qemu.pid"
                vm_name = f"codesk-{run_id[:40]}-{self.instance_id[:8]}"
                command = [
                    qemu_bin,
                    "-L", str(prefix / "usr/share/qemu"),
                    "-name", vm_name,
                    "-machine", "pc",
                    "-accel", "kvm",
                    "-cpu", "host",
                    "-m", ram,
                    "-smp", str(cpus),
                    "-rtc", "base=utc",
                    "-drive", f"file={self.overlay_path},format=qcow2,if=ide,index=0",
                    "-netdev", f"user,id=net0,restrict=off,{forwarding}",
                    "-device", "e1000,netdev=net0",
                    "-vga", "std",
                    "-display", "none",
                    "-monitor", "none",
                    "-serial", f"file:{serial_log}",
                    "-pidfile", str(pid_file),
                    "-no-reboot",
                    "-boot", "order=c",
                ]
                try:
                    with open(qemu_log, "ab", buffering=0) as log_handle:
                        self.process = subprocess.Popen(
                            command,
                            stdin=subprocess.DEVNULL,
                            stdout=log_handle,
                            stderr=subprocess.STDOUT,
                            close_fds=True,
                            env=self._qemu_env(),
                            start_new_session=True,
                        )
                    deadline = time.monotonic() + 15.0
                    while time.monotonic() < deadline:
                        if self.process.poll() is not None:
                            tail = qemu_log.read_text(errors="replace")[-2000:]
                            raise RuntimeError(f"QEMU KVM exited early ({self.process.returncode}): {tail}")
                        bound_all = True
                        for port in ports.values():
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check_sock:
                                try:
                                    check_sock.bind(("127.0.0.1", port))
                                except OSError:
                                    continue
                                bound_all = False
                                break
                        if bound_all:
                            break
                        time.sleep(0.1)
                    self._release_port_lock()
                except Exception:
                    self._release_port_lock()
                    self.stop_emulator(path_to_vm)
                    raise
                labels = self._record_ledger(
                    "created", name=vm_name, image="native-qemu-kvm:" + base_image.name, pid=self.process.pid
                )
                self.container = _ContainerMetadataShim(self.resource_id, labels, base_image, self.overlay_path)
                self.manifest = {
                    "resource_id": self.resource_id,
                    "provider": "native-qemu-kvm",
                    "qemu": str(qemu_bin),
                    "qemu_version": "8.2.2",
                    "vm_name": vm_name,
                    "pid": self.process.pid,
                    "ports": ports,
                    "guestfwd": guestfwd,
                    "base_image": str(base_image),
                    "base_image_read_only": not os.access(base_image, os.W_OK),
                    "overlay": str(self.overlay_path),
                    "acceleration": "kvm",
                }
                (self.instance_dir / "manifest.json").write_text(
                    json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8"
                )
                try:
                    self._wait_for_http_screenshot(float(os.environ.get("CODESK_KVM_BOOT_TIMEOUT", "240")))
                except Exception:
                    self.stop_emulator(path_to_vm)
                    raise

        def _wait_for_http_screenshot(self, timeout_s: float) -> None:
            deadline = time.monotonic() + timeout_s
            url = f"http://127.0.0.1:{self.server_port}/screenshot"
            last_err = "not started"
            while time.monotonic() < deadline:
                if self.process and self.process.poll() is not None:
                    tail = (self.instance_dir / "qemu.log").read_text(errors="replace")[-2000:]
                    raise RuntimeError(f"QEMU exited during boot ({self.process.returncode}): {tail}")
                try:
                    resp = requests.get(url, timeout=(3, 25))
                    if resp.status_code == 200 and len(resp.content) > 500:
                        return
                    last_err = f"HTTP {resp.status_code} ({len(resp.content)} bytes)"
                except requests.RequestException as exc:
                    last_err = f"{type(exc).__name__}: {exc}"
                time.sleep(2.0)
            raise TimeoutError(f"KVM Guest screenshot server not ready in {timeout_s}s: {last_err}")

        def get_ip_address(self, path_to_vm: str) -> str:
            if not all((self.server_port, self.chromium_port, self.vnc_port, self.vlc_port)):
                raise RuntimeError("KVM Guest ports not allocated")
            return f"127.0.0.1:{self.server_port}:{self.chromium_port}:{self.vnc_port}:{self.vlc_port}"

        def save_state(self, path_to_vm: str, snapshot_name: str):
            raise NotImplementedError("NativeQemuKvmProvider uses fresh qcow2 overlays per episode")

        def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str) -> str:
            self.stop_emulator(path_to_vm)
            return path_to_vm

        def stop_emulator(self, path_to_vm: str, region=None, *args, **kwargs):
            with self._lock:
                proc = self.process
                self.process = None
                was_recorded = self.container is not None
                self.container = None
                if proc is not None:
                    if proc.poll() is None:
                        try:
                            os.killpg(proc.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        try:
                            proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            proc.wait(timeout=10)
                if self.overlay_path and self.overlay_path.exists():
                    try:
                        self.overlay_path.unlink()
                    except OSError:
                        pass
                if was_recorded:
                    self._record_ledger("destroy_requested")
                    self._record_ledger("destroyed")
                self.server_port = None
                self.vnc_port = None
                self.chromium_port = None
                self.vlc_port = None

    original_factory = providers_pkg.create_vm_manager_and_provider

    def patched_factory(provider_name: str, region: str, use_proxy: bool = False, use_public_ip: bool = False):
        if provider_name.lower().strip() in {"docker", "native-qemu-kvm", "native-qemu-tcg"}:
            return NativeKvmVMManager(), NativeQemuKvmProvider(region)
        return original_factory(provider_name, region, use_proxy=use_proxy, use_public_ip=use_public_ip)

    providers_pkg.create_vm_manager_and_provider = patched_factory
    import desktop_env.desktop_env as desktop_env_mod
    desktop_env_mod.create_vm_manager_and_provider = patched_factory
    providers_pkg._codesk_native_kvm_installed = True

"""BC-only hook around formal oscombo setup/teardown callbacks.

The installed oscombo remains the runner. This hook only stages case inputs
after the runner's shared Guest reset, records actor PIDs, and reads declared
Guest artifacts immediately before the runner calls env.close().
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import time
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


CHUNK_CHARS = 48_000


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _run_guest(env: Any, script: str, *, timeout: int = 120) -> dict[str, Any]:
    # The workspace directory may not exist yet immediately after OSWorld
    # reset. Bootstrap from the guaranteed home directory, then use absolute
    # workspace paths in the script itself.
    result = env.controller.run_bash_script(script, timeout=timeout, working_dir="/home/user")
    if not isinstance(result, dict) or result.get("status") == "error" or int(result.get("returncode", -1)) != 0:
        status = result.get("status") if isinstance(result, dict) else "no-result"
        returncode = result.get("returncode") if isinstance(result, dict) else None
        detail = (result.get("error") or result.get("message") or result.get("output") or result.get("stderr")) if isinstance(result, dict) else None
        if detail:
            detail = str(detail)
            detail = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [REDACTED]", detail)
            detail = re.sub(r"\bsk-[A-Za-z0-9_-]{20,}\b", "[REDACTED]", detail)
            detail = re.sub(r"(?i)(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", detail)
            detail = detail[:240]
        raise RuntimeError(f"Guest operation failed (status={status}, returncode={returncode}, detail={detail or 'unavailable'})")
    return result


def _setup_shell_command(command: str, setup_log: str) -> str:
    """Close request pipes in detached child processes while retaining logs."""
    path = shlex.quote(setup_log)
    return "( " + command + " ) > " + path + " 2>&1; code=$?; tail -c 12000 " + path + "; exit $code"


def _guest_asset_tar(root: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for item in sorted(root.rglob("*")):
            if item.is_symlink():
                raise ValueError(f"Guest staging payload may not contain symlinks: {item.name}")
            relative = item.relative_to(root).as_posix()
            if item.is_file():
                archive.add(item, arcname=relative, recursive=False)
            elif item.is_dir():
                info = tarfile.TarInfo(relative.rstrip("/") + "/")
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                archive.addfile(info)
    return buffer.getvalue()


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = item.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(item.read_bytes())
    return digest.hexdigest()


def _probe_service(env: Any, url: str, timeout_s: int = 30) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("BC guest service health checks must target a loopback HTTP URL")
    encoded_url = json.dumps(url)
    script = (
        "python3 - <<'PY'\n"
        "import json, time, urllib.request\n"
        f"url = {encoded_url}\n"
        f"deadline = time.time() + {int(timeout_s)}\n"
        "while time.time() < deadline:\n"
        "    try:\n"
        "        with urllib.request.urlopen(url, timeout=2) as response:\n"
        "            if response.status == 200:\n"
        "                print(json.dumps({'ready': True, 'status': response.status}))\n"
        "                raise SystemExit(0)\n"
        "    except Exception:\n"
        "        time.sleep(0.5)\n"
        "print(json.dumps({'ready': False}))\n"
        "raise SystemExit(1)\n"
        "PY"
    )
    try:
        result = env.controller.run_bash_script(script, timeout=timeout_s + 10, working_dir="/home/user/workspace")
        output = str(result.get("output", "")) if isinstance(result, dict) else ""
        ready = isinstance(result, dict) and result.get("status") != "error" and int(result.get("returncode", 1)) == 0
        return {"url": url, "ready": ready, "status_code": 200 if ready else None,
                "response_note": "loopback health check; response body suppressed"}
    except Exception as exc:
        return {"url": url, "ready": False, "error_type": type(exc).__name__}


def _stage_and_setup(env: Any, plan: dict[str, Any]) -> dict[str, Any]:
    source = Path(plan["guest_assets_source"]).resolve(strict=True)
    workspace = str(plan["guest_workspace"])
    target = f"{workspace}/.bc-case-assets"
    b64path = f"{workspace}/.bc-case-payload.tar.gz.b64"
    tarpath = f"{workspace}/.bc-case-payload.tar.gz"
    archive_bytes = _guest_asset_tar(source)
    encoded = base64.b64encode(archive_bytes).decode("ascii")
    _run_guest(env, "umask 077; mkdir -p " + shlex.quote(workspace) + "; rm -f "
               + shlex.quote(b64path) + " " + shlex.quote(tarpath) + "; : > " + shlex.quote(b64path))
    for offset in range(0, len(encoded), CHUNK_CHARS):
        chunk = encoded[offset:offset + CHUNK_CHARS]
        _run_guest(env, "printf '%s' " + shlex.quote(chunk) + " >> " + shlex.quote(b64path), timeout=30)
    _run_guest(env, "base64 -d " + shlex.quote(b64path) + " > " + shlex.quote(tarpath)
               + " && rm -rf " + shlex.quote(target) + " && mkdir -p " + shlex.quote(target)
               + " && tar -xzf " + shlex.quote(tarpath) + " -C " + shlex.quote(target)
               + " && rm -f " + shlex.quote(b64path) + " " + shlex.quote(tarpath))
    verify_code = (
        "import hashlib,json,pathlib\n"
        f"root=pathlib.Path({target!r})\n"
        "d=hashlib.sha256()\n"
        "for p in sorted(x for x in root.rglob('*') if x.is_file()):\n"
        " r=p.relative_to(root).as_posix().encode('utf-8'); d.update(len(r).to_bytes(4,'big')); d.update(r); d.update(p.read_bytes())\n"
        "print(d.hexdigest())\n"
    )
    check = env.controller.run_python_script(verify_code, timeout=60)
    actual = str(check.get("output", "")).strip() if isinstance(check, dict) else ""
    # The Guest execute service may include interpreter banners; use the last
    # 64-hex line only, never trust an unparseable or mismatching digest.
    hashes = [line.strip() for line in actual.splitlines() if len(line.strip()) == 64]
    if not hashes or hashes[-1] != plan["guest_assets_sha256"]:
        raise RuntimeError("Guest staged asset digest did not match the host manifest")

    role_src = f"{target}/role-private"
    role_dst = f"{workspace}/private"
    _run_guest(env, "mkdir -p " + shlex.quote(role_dst)
               + " && for role in actor_a actor_b; do mkdir -p " + shlex.quote(role_dst)
               + "/$role; if [ -d " + shlex.quote(role_src) + "/$role ]; then cp -a "
               + shlex.quote(role_src) + "/$role/. " + shlex.quote(role_dst) + "/$role/; fi; done")
    setup_command = plan.get("guest_setup_command")
    if setup_command:
        argv = [str(arg).replace(".bc-case-assets", ".bc-case-assets") for arg in setup_command]
        if len(argv) > 1 and argv[0] == "python3":
            argv[1] = target + "/setup.py"
            argv[argv.index("--source-dir") + 1] = target
        command = " ".join(shlex.quote(arg) for arg in argv)
        # subprocess.communicate waits for inherited GUI/service pipes even
        # after setup exits. Redirect the entire child tree to a Guest log to
        # prevent timeouts and automatic replay of non-idempotent setup.
        setup_log = f"{workspace}/.bc-setup.log"
        wrapped = _setup_shell_command(command, setup_log)
        setup_result = _run_guest(env, wrapped, timeout=180)
        _atomic_json(Path(plan["capture_root"]) / "guest-setup-output.json", {
            "returncode": setup_result.get("returncode"),
            "output": str(setup_result.get("output", ""))[-12000:],
            "guest_log": setup_log,
        })
    services = [_probe_service(env, str(row["url"])) for row in plan.get("guest_services", [])]
    if any(row.get("ready") is not True for row in services):
        raise RuntimeError("A declared Guest service failed its loopback readiness probe")
    _run_guest(env, "rm -rf " + shlex.quote(target) + " " + shlex.quote(b64path) + " " + shlex.quote(tarpath))
    cleanup_check = env.controller.run_bash_script(
        "test ! -e " + shlex.quote(target) + " && test ! -e " + shlex.quote(b64path)
        + " && test -d " + shlex.quote(role_dst + "/actor_a")
        + " && test -d " + shlex.quote(role_dst + "/actor_b"),
        timeout=20, working_dir=workspace,
    )
    if not isinstance(cleanup_check, dict) or cleanup_check.get("status") == "error" or int(cleanup_check.get("returncode", -1)) != 0:
        raise RuntimeError("Guest setup payload cleanup or role path preparation was not verified")
    return {
        "setup_completed": bool(setup_command),
        "guest_assets_sha256": plan["guest_assets_sha256"],
        "guest_workspace": workspace,
        "setup_payload_removed": True,
        "role_private_guest_paths": {"actor_a": role_dst + "/actor_a", "actor_b": role_dst + "/actor_b"},
        "services": services,
        "asset_archive_size_bytes": len(archive_bytes),
        "verified_at_unix_ms": time.time_ns() // 1_000_000,
    }


def _guest_container(env: Any) -> tuple[str, dict[str, Any]]:
    provider = getattr(env, "provider", None)
    container = getattr(provider, "container", None)
    if container is None:
        raise RuntimeError("Formal OSWorld provider did not expose the live shared Guest container")
    container.reload()
    attrs = container.attrs or {}
    mounts = [{
        "source": row.get("Source"), "destination": row.get("Destination"),
        "read_write": bool(row.get("RW")), "type": row.get("Type"),
    } for row in attrs.get("Mounts", [])]
    raw_labels = (attrs.get("Config") or {}).get("Labels", {})
    # SWCUB labels include an ephemeral owner capability. Retain ordinary
    # run metadata only; never archive the capability value.
    labels = {key: value for key, value in raw_labels.items()
              if not any(secret in str(key).lower() for secret in ("token", "secret", "password", "credential"))}
    return str(container.id), {"name": attrs.get("Name"), "image": (attrs.get("Config") or {}).get("Image"),
                              "mounts": mounts, "labels": labels}


def _wait_container_absent(container_id: str, timeout_s: float = 25.0) -> bool:
    """Confirm this exact Guest was removed; tolerate asynchronous teardown."""
    deadline = time.monotonic() + timeout_s
    needle = container_id.encode("ascii", "ignore")
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(["docker", "inspect", container_id],
                                    capture_output=True, timeout=15, check=False)
            if result.returncode == 0:
                time.sleep(0.5)
                continue
            stderr = (result.stderr or b"").lower()
            if needle.lower() in stderr and (b"no such object" in stderr or b"not found" in stderr):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _expand_snapshot_directories(env: Any, plan: dict[str, Any]) -> list[dict[str, Any]]:
    from pipeline.host_snapshots import SnapshotItem, validate_snapshot_items
    specs = plan.get("host_snapshot_directories", [])
    validate_snapshot_items([SnapshotItem(**x) for x in specs])
    result = []
    for spec in specs:
        if spec["kind"] != "deliverable":
            raise ValueError("Only deliverable directories may be recursively captured")
        code = (
            "import json,pathlib\n"
            f"workspace=pathlib.Path({plan['guest_workspace']!r}).resolve()\n"
            f"root=pathlib.Path({spec['guest_path']!r})\n"
            "assert root.resolve().is_relative_to(workspace) and not root.is_symlink()\n"
            "files=[]; size=0\n"
            "if root.exists():\n"
            " assert root.is_dir()\n"
            " for p in sorted(root.rglob('*')):\n"
            "  assert not p.is_symlink(), 'Symlink in output directory'\n"
            "  if p.is_file():\n"
            "   assert p.resolve().is_relative_to(root.resolve())\n"
            "   n=p.stat().st_size; assert n<=268435456\n"
            "   size+=n; files.append(p.relative_to(root).as_posix())\n"
            "   assert len(files)<=10000 and size<=1073741824\n"
            "print(json.dumps({'files':files}))\n"
        )
        response = env.controller.run_python_script(code, timeout=30)
        if not isinstance(response, dict) or response.get("status") != "success" or int(response.get("returncode",0)) != 0:
            raise RuntimeError("Read-only output directory enumeration failed")
        lines = [x for x in str(response.get("output", "")).splitlines() if x.strip().startswith('{')]
        if not lines:
            raise RuntimeError("Output directory listing had no structured receipt")
        for rel in json.loads(lines[-1])["files"]:
            path = PurePosixPath(rel)
            if path.is_absolute() or '..' in path.parts or not path.parts:
                raise ValueError("Invalid relative output file")
            result.append({"guest_path": str(PurePosixPath(spec["guest_path"])/path),
                           "archive_path": str(PurePosixPath(spec["archive_path"])/path), "kind":"deliverable"})
    return result


def _snapshot_allowlist(env: Any, plan: dict[str, Any]) -> list[dict[str, Any]]:
    capture_root = Path(plan["capture_root"])
    out = []
    directory_items = _expand_snapshot_directories(env, plan)
    explicit = list(plan.get("host_snapshots", []))
    seen = {row["guest_path"] for row in explicit}
    expanded = [row for row in directory_items if row["guest_path"] not in seen]
    from pipeline.host_snapshots import SnapshotItem, validate_snapshot_items
    rows = explicit + expanded
    validate_snapshot_items([SnapshotItem(**row) for row in rows])
    for row in rows:
        guest_path = str(row["guest_path"])
        guest = PurePosixPath(guest_path)
        if not guest.is_absolute() or ".." in guest.parts:
            raise ValueError("Snapshot allowlist contains a non-canonical Guest path")
        # Deliverable files are optional: their absence is an Oracle-scored
        # task outcome, not a reason to invalidate teardown evidence. Verify
        # existence read-only inside the Guest before asking OSWorld to copy.
        exists_code = (
            "import json,pathlib\n"
            f"root=pathlib.Path({plan['guest_workspace']!r}).resolve()\n"
            f"path=pathlib.Path({guest_path!r})\n"
            "exists=path.is_file() and path.resolve().is_relative_to(root)\n"
            "print(json.dumps(exists))\n"
        )
        exists_result = env.controller.run_python_script(exists_code, timeout=15)
        if (not isinstance(exists_result, dict) or exists_result.get("status") != "success"
                or int(exists_result.get("returncode", 0)) != 0):
            raise RuntimeError("Allowlisted Guest file existence check failed")
        output = str(exists_result.get("output", "")) if isinstance(exists_result, dict) else ""
        parsed = [line.strip().lower() for line in output.splitlines() if line.strip().lower() in {"true", "false"}]
        if not parsed:
            raise RuntimeError("Allowlisted Guest file existence check returned no boolean result")
        if parsed[-1] == "false":
            if row["kind"] == "deliverable":
                out.append({"guest_path": guest_path, "archive_path": row["archive_path"],
                            "kind": row["kind"], "missing": True,
                            "capture_stage": "after-agent-completion-before-env-close"})
                continue
            raise FileNotFoundError(f"Required allowlisted Guest evidence is missing: {Path(guest_path).name}")
        payload = env.controller.get_file(guest_path)
        if not isinstance(payload, (bytes, bytearray)):
            raise RuntimeError(f"Allowlisted Guest read failed for {Path(guest_path).name}")
        digest = hashlib.sha256(payload).hexdigest()
        target = capture_root / "guest-files" / digest[:16]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        out.append({"guest_path": guest_path, "archive_path": row["archive_path"],
                    "kind": row["kind"], "captured_path": str(target),
                    "size_bytes": len(payload), "sha256": digest,
                    "capture_stage": "after-agent-completion-before-env-close"})
    http = []
    for row in plan.get("host_http_snapshots", []):
        url = str(row["url"])
        parsed = urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("HTTP receipt allowlist can only target loopback Guest services")
        code = (
            "import base64,json,urllib.request,urllib.error\n"
            "try:\n"
            f" r=urllib.request.urlopen({url!r},timeout=10)\n"
            "except urllib.error.HTTPError as error:\n"
            " r=error\n"
            "print(json.dumps({'status_code':r.status,'body_b64':base64.b64encode(r.read()).decode('ascii')}))\n"
        )
        response = env.controller.run_python_script(code, timeout=20)
        if not isinstance(response, dict) or response.get("status") != "success":
            raise RuntimeError("Guest loopback HTTP receipt could not be recovered")
        lines = [line for line in str(response.get("output", "")).splitlines() if line.strip().startswith("{")]
        if not lines:
            raise RuntimeError("Guest loopback HTTP receipt had no structured payload")
        decoded = json.loads(lines[-1])
        body = base64.b64decode(decoded["body_b64"], validate=True)
        archive_path = str(row["archive_path"])
        target = capture_root / "http" / Path(archive_path).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        http.append({"id": row["id"], "url": url, "status_code": int(decoded["status_code"]),
                     "captured_path": str(target), "size_bytes": len(body),
                     "sha256": hashlib.sha256(body).hexdigest()})
    _atomic_json(capture_root / "snapshot-capture.json", {"guest_files": out, "http": http, "directory_items": directory_items})
    return out



def _raid_boot_disk_volumes(volumes: dict, overlay_dir: str) -> tuple[dict, Path]:
    """Bind the image's actual writable /boot.qcow2, not an unused directory."""
    root = Path(overlay_dir).resolve()
    if not root.is_relative_to(Path("/mnt/raid1")):
        raise ValueError("Actual Guest boot disk must be on RAID")
    root.mkdir(parents=True, exist_ok=True)
    disk = root / "boot.qcow2"
    # Do not truncate/reuse an existing disk belonging to any Guest.
    with disk.open("xb"):
        pass
    result = dict(volumes)
    result[str(disk)] = {"bind": "/boot.qcow2", "mode": "rw"}
    return result, disk


def _install_actual_raid_boot_bind(plan: dict) -> None:
    # This module is installed only in a dedicated NEW BC runner process.
    # Do not edit the shared OSWorld provider or affect running C/BC processes.
    from docker.models.containers import ContainerCollection
    original = ContainerCollection.run
    def run_with_actual_boot_bind(collection, image, *args, **kwargs):
        expected = os.environ.get("SWCUB_OSWORLD_OVERLAY_HOST_DIR")
        volumes = kwargs.get("volumes", {})
        labels = kwargs.get("labels", {}) or {}
        run = labels.get("org.swcub.run-id")
        if expected and run == os.environ.get("SWCUB_RUN_ID"):
            kwargs["volumes"], disk = _raid_boot_disk_volumes(volumes, expected)
            _atomic_json(Path(plan["capture_root"]) / "actual-boot-disk-plan.json", {
                "host_path": str(disk), "container_path": "/boot.qcow2",
                "reason": "Official image writes /boot.qcow2; /vm-overlay alone is insufficient",
            })
        return original(collection, image, *args, **kwargs)
    ContainerCollection.run = run_with_actual_boot_bind


def install_formal_capture_hook() -> None:
    """Install only in the dedicated BC runner subprocess (never old C runs)."""
    plan_path_raw = os.environ.get("CODEDESK_BC_CAPTURE_PLAN")
    if not plan_path_raw:
        return
    plan_path = Path(plan_path_raw)
    if not plan_path.is_file():
        raise RuntimeError("BC capture plan is missing")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    from oscombo import combo

    if getattr(combo, "_bc_capture_hook_installed", False):
        return
    _install_actual_raid_boot_bind(plan)
    original_boot = combo.boot
    original_setup_tasks = combo.setup_tasks

    def setup_tasks_with_assets(env, tasks, probe=None):
        result = original_setup_tasks(env, tasks, probe)
        receipt = _stage_and_setup(env, plan)
        _atomic_json(Path(plan["capture_root"]) / "guest-preparation-receipt.json", receipt)
        result["bc_guest_preparation"] = receipt
        return result

    def boot_with_capture(image, cache_dir):
        env = original_boot(image, cache_dir)
        container_id, container_facts = _guest_container(env)
        expected_storage = os.environ.get("SWCUB_OSWORLD_STORAGE_HOST_DIR")
        expected_overlay = os.environ.get("SWCUB_OSWORLD_OVERLAY_HOST_DIR")
        if expected_storage:
            mounts = container_facts.get("mounts", [])
            observed = {m.get("destination"): m for m in mounts}
            okay = all(
                observed.get(dest, {}).get("type") == "bind"
                and observed[dest].get("source") == expected
                and Path(expected).resolve().is_relative_to(Path("/mnt/raid1"))
                for dest, expected in (("/storage", expected_storage), ("/vm-overlay", expected_overlay), ("/boot.qcow2", str(Path(expected_overlay) / "boot.qcow2") if expected_overlay else None))
                if expected
            )
            _atomic_json(Path(plan["capture_root"]) / "guest-storage-receipt.json", {
                "storage_on_raid": okay, "actual_boot_disk_on_raid": okay, "mounts": mounts, "verified_at_unix_ms": time.time_ns() // 1_000_000,
            })
            if not okay:
                env.close()
                raise RuntimeError("New BC Guest is missing required RAID storage/actual boot disk bind mounts")
        _atomic_json(Path(plan["capture_root"]) / "guest-container-entry.json", {
            "container_id": container_id, "facts": container_facts,
        })
        original_close = env.close

        def close_with_allowlist_capture():
            capture_error = None
            try:
                _snapshot_allowlist(env, plan)
            except Exception as exc:
                capture_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
            close_error = None
            try:
                original_close()
            except Exception as exc:
                close_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
                raise
            finally:
                # Provider teardown can return before Docker's removal is
                # visible. Poll the one exact container ID, never all Guests.
                absent = _wait_container_absent(container_id)
                receipt = {
                    "guest_container_id": container_id,
                    "container_facts": container_facts,
                    "allowlisted_snapshots_captured": capture_error is None,
                    "capture_error": capture_error,
                    "env_close_completed": close_error is None,
                    "container_absent_after_close": absent,
                    "teardown_verified": capture_error is None and close_error is None and absent,
                    "capture_stage": "after-runner-evaluation-before-env-close",
                    "verified_at_unix_ms": time.time_ns() // 1_000_000,
                }
                _atomic_json(Path(plan["capture_root"]) / "teardown-receipt.json", receipt)
            if capture_error:
                raise RuntimeError("Allowlisted Guest evidence capture failed before teardown")

        env.close = close_with_allowlist_capture
        return env

    combo.boot = boot_with_capture
    combo.setup_tasks = setup_tasks_with_assets

    # Record the two real Codex process IDs when the unchanged formal harness
    # launches them. This wraps only subprocesses whose actor name and binary
    # match the expected Codex CLI call.
    from oscombo.harness import external
    real_popen = subprocess.Popen

    def popen_with_actor_pid(args, *popen_args, **popen_kwargs):
        process = real_popen(args, *popen_args, **popen_kwargs)
        argv = [str(value) for value in (args if isinstance(args, (list, tuple)) else [args])]
        env = popen_kwargs.get("env") or {}
        actor_name = str(env.get("OSCOMBO_NAME", ""))
        if "exec" in argv and Path(argv[0]).name.startswith("codex") and actor_name in {"agentA", "agentB"}:
            _atomic_json(Path(plan["capture_root"]) / f"{actor_name}-process.json", {
                "actor_name": actor_name, "pid": process.pid,
                "uid": os.getuid() if hasattr(os, "getuid") else None,
                "gid": os.getgid() if hasattr(os, "getgid") else None,
                "home": env.get("HOME"), "codex_home": env.get("CODEX_HOME"),
                "cwd": str(popen_kwargs.get("cwd") or ""),
                "binary": argv[0], "created_at_unix_ms": time.time_ns() // 1_000_000,
            })
        return process

    external.subprocess.Popen = popen_with_actor_pid
    combo._bc_capture_hook_installed = True

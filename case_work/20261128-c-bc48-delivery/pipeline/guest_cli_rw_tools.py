"""Full read/write/execute Guest CLI MCP proxy, strictly inside the OSWorld Guest.

The coordinator submits an argv array with ``bash -lc`` as the Guest command;
the coordinator itself never invokes that shell. CWD must resolve under the
per-episode Guest workspace. Host files, Oracle and queue controls are not
mounted in or addressed by this service.
"""

from __future__ import annotations

import json
import os
import posixpath
import time
from pathlib import PurePosixPath
from typing import Any

import requests

from .timeline import sanitize

def _reserve_call(name: str) -> int:
    from oscombo.desktop_tools import reserve_call

    return reserve_call(name)


def _log(row: dict[str, Any]) -> None:
    from oscombo.desktop_tools import _log as action_log

    action_log(row)


URL = os.environ.get("OSCOMBO_GUEST_URL", "").rstrip("/")
ROOT = posixpath.normpath(os.environ.get("OSCOMBO_CLI_ROOT", "/home/user/workspace"))
MAX_COMMAND_CHARS = 16_384
MAX_TIMEOUT_SEC = min(30, max(1, int(os.environ.get("OSCOMBO_CLI_MAX_TIMEOUT_SEC", "30"))))
MAX_OUTPUT_BYTES = min(1_000_000, max(256, int(os.environ.get("OSCOMBO_CLI_MAX_OUTPUT_BYTES", "1000000"))))


def _validate_cwd(cwd: str | None) -> str:
    path = cwd or ROOT
    raw = PurePosixPath(path)
    if not raw.is_absolute() or ".." in raw.parts or "\x00" in path:
        raise ValueError("cwd must be an absolute Guest workspace path without traversal")
    normalized = posixpath.normpath(path)
    if normalized != ROOT and not normalized.startswith(ROOT.rstrip("/") + "/"):
        raise PermissionError("cwd is outside the per-episode Guest workspace")
    return normalized


def _request(argv: list[str], timeout: int) -> dict[str, Any]:
    if not URL:
        raise RuntimeError("OSCOMBO_GUEST_URL is not configured")
    response = requests.post(
        URL + "/execute",
        json={"command": argv, "shell": False, "timeout": timeout},
        timeout=(5, timeout + 10),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Guest execute endpoint returned a non-object payload")
    return payload


def _canonical_root_and_cwd(cwd: str) -> tuple[str, str]:
    root_data = _request(["/usr/bin/realpath", "-e", "--", ROOT], 10)
    cwd_data = _request(["/usr/bin/realpath", "-e", "--", cwd], 10)
    root_real = str(root_data.get("output", "")).strip().rstrip("/") or "/"
    cwd_real = str(cwd_data.get("output", "")).strip().rstrip("/") or "/"
    if root_data.get("returncode", 1) != 0 or cwd_data.get("returncode", 1) != 0:
        raise ValueError("Guest workspace/cwd must already exist")
    if cwd_real != root_real and not cwd_real.startswith(root_real.rstrip("/") + "/"):
        raise PermissionError("resolved Guest CLI cwd escapes the per-episode workspace")
    return root_real, cwd_real


def run_guest_cli(command: str, *, cwd: str | None = None, timeout_sec: int = 30) -> dict[str, Any]:
    """Run arbitrary Guest shell work, with CWD rooted in the task workspace.

    This tool does not use a host subprocess shell. ``bash`` is an argv item
    sent to the OSWorld Guest's execute endpoint, which executes inside the VM.
    """
    started = time.monotonic()
    raw_args = {"command": command, "cwd": cwd, "timeout_sec": timeout_sec}
    call_number = None
    try:
        if not isinstance(command, str) or not command.strip() or len(command) > MAX_COMMAND_CHARS or "\x00" in command:
            raise ValueError("command must be a non-empty Guest shell string within the size limit")
        timeout = int(timeout_sec)
        if not 1 <= timeout <= MAX_TIMEOUT_SEC:
            raise ValueError(f"timeout_sec must be in [1, {MAX_TIMEOUT_SEC}]")
        guest_cwd = _validate_cwd(cwd)
        call_number = _reserve_call("guest_cli")
        resolved_root, resolved_cwd = _canonical_root_and_cwd(guest_cwd)
        # Lock is intentionally not held while the Guest process runs. GUI and
        # CLI operations can overlap on the shared desktop, exposing real task
        # conflicts instead of turning a long CLI command into a global mutex.
        payload = _request(
            ["/usr/bin/env", "-C", resolved_cwd, "/bin/bash", "-lc", command], timeout
        )
        output = str(payload.get("output", ""))
        output_raw = output.encode("utf-8", "replace")
        truncated = len(output_raw) > MAX_OUTPUT_BYTES
        if truncated:
            output = output_raw[:MAX_OUTPUT_BYTES].decode("utf-8", "replace")
        result = {
            "ok": payload.get("returncode", 0) == 0,
            "returncode": payload.get("returncode", 0),
            "cwd": resolved_cwd,
            "output": output,
            "output_truncated": truncated,
            "execution_site": "osworld_guest",
            "workspace_root": resolved_root,
        }
        _log({
            "t": time.time(), "n": call_number, "tool": "guest_cli",
            "args": sanitize({"command": command, "cwd": resolved_cwd}),
            "result": sanitize(result), "tool_elapsed_s": round(time.monotonic() - started, 4),
            "execution_site": "osworld_guest", "shell": True,
        })
        return result
    except Exception as exc:
        _log({
            "t": time.time(), "n": call_number, "tool": "guest_cli",
            "args": sanitize(raw_args), "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            "tool_elapsed_s": round(time.monotonic() - started, 4),
            "execution_site": "osworld_guest", "shell": True,
        })
        raise


def mcp_main() -> None:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("guest-cli-rw")

    @mcp.tool(description=(
        "Run a shell command inside the isolated OSWorld Guest. Commands can read, create, edit and execute "
        "files in the Guest workspace. The working directory must be within the per-episode workspace. "
        "This is not a host shell; the host Oracle, ground truth and queue controls are not exposed."
    ))
    def guest_cli(command: str, cwd: str | None = None, timeout_sec: int = 30) -> dict[str, Any]:
        return run_guest_cli(command, cwd=cwd, timeout_sec=timeout_sec)

    mcp.run()


if __name__ == "__main__":
    mcp_main()

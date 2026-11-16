"""Runtime modules staged into the 19-case bundle for Hybrid v2, Guest CLI, action gates, and containerized non-YOLO Codex."""
from __future__ import annotations

import hashlib


F01_PROMPTS = {
    "actor_a": (
        'LibreOffice Writer is active and the complete existing paragraph is selected. '
        'Replace it by typing exactly "Approved by GUI actor", then save with Ctrl+S. '
        'Do not use Ctrl+A, menus, or Ctrl+V. Do not edit Calc.'
    ),
    "actor_b": (
        'LibreOffice Calc is active and cell B2 is already selected. '
        'Replace Draft by typing exactly "Approved", press Enter to commit, then save with Ctrl+S. '
        'Do not navigate to another cell or switch applications. Do not edit Writer.'
    ),
}

C03_PROMPTS = {
    "actor_a": (
        "In LibreOffice Calc, the complete source range A1:B2 is selected. Copy it. "
        "After the coordination pause, Calc cell A4 will already be selected for you. "
        "Do not click or navigate; press Ctrl+V to paste, then save with Ctrl+S. "
        "Preserve the source, guard cells, and every other cell. Do not edit Writer."
    ),
    "actor_b": (
        'LibreOffice Writer is active and the first paragraph "NOTE-571" is selected. Copy it. '
        "The document already has a blank second paragraph immediately below it. "
        "Click inside that existing blank paragraph and paste exactly one copy there. "
        "Do NOT press Enter or create any paragraphs. Keep the first paragraph unchanged and save with Ctrl+S. "
        "Do not switch applications; the coordinator handles the next actor window. Do not edit Calc."
    ),
}

EXPECTED_PROMPT_SHAS = {
    ("F-01", "actor_a"): "bb6970b4b394e4c602b81688dbad5b62d4045834a4a59a50649edeade22d0529",
    ("F-01", "actor_b"): "13e7c1681ab28f9eacb9de99d0d95c82e1692b1ed23837f10017a41987d84859",
    ("C-03", "actor_a"): "82a3077c4072c9707d6614f23b7f0393622f9c42d5ff5a4ac8ad654ba4cb6558",
    ("C-03", "actor_b"): "4302d4c03491d6c41220c922f5aff75be812daee8d2afaa40ba5833e220e20c9",
}


def verify_reconstructed_prompt_hashes() -> dict[str, str]:
    verified = {}
    for task_name, mapping in (("F-01", F01_PROMPTS), ("C-03", C03_PROMPTS)):
        for role, text in mapping.items():
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            expected = EXPECTED_PROMPT_SHAS[(task_name, role)]
            if digest != expected:
                raise ValueError(f"Prompt SHA mismatch for {task_name}/{role}: {digest} != {expected}")
            verified[f"{task_name}:{role}"] = digest
    return verified


GUEST_CLI_TOOLS_SOURCE = r'''"""Restricted read-only Guest CLI executor and MCP tool for CoDesk Hybrid v2."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import posixpath
import sys
import time
from typing import Any

import requests


DEFAULT_ALLOWED = ("pwd", "ls", "cat", "stat", "grep", "head", "tail")


@contextmanager
def action_lock():
    lock_path = os.environ.get("OSCOMBO_ACTION_LOCK_FILE")
    if not lock_path:
        yield None
        return
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    with open(lock_path, "a+") as handle:
        started = time.monotonic()
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield round(time.monotonic() - started, 6)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _normalize_inside_root(candidate: str, root: str, base_cwd: str) -> str:
    norm_root = posixpath.normpath(root)
    joined = candidate if candidate.startswith("/") else posixpath.join(base_cwd, candidate)
    resolved = posixpath.normpath(joined)
    if resolved != norm_root and not resolved.startswith(norm_root.rstrip("/") + "/"):
        raise ValueError(f"Path {candidate!r} escapes assigned Guest CLI root {norm_root!r}")
    return resolved


def _append_log(entry: dict[str, Any]) -> None:
    log_path = os.environ.get("OSCOMBO_ACTION_LOG")
    if not log_path:
        return
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_guest_cli(argv: list[str], cwd: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    cli_root = os.environ.get("OSCOMBO_CLI_ROOT") or cwd or "/tmp"
    allowed_raw = os.environ.get("OSCOMBO_CLI_ALLOWED_COMMANDS", ",".join(DEFAULT_ALLOWED))
    allowed = {item.strip() for item in allowed_raw.split(",") if item.strip()}
    max_timeout = float(os.environ.get("OSCOMBO_CLI_MAX_TIMEOUT_SEC", "20"))
    max_bytes = int(os.environ.get("OSCOMBO_CLI_MAX_OUTPUT_BYTES", "12000"))
    guest_url = os.environ.get("OSCOMBO_GUEST_URL", "http://127.0.0.1:5000").rstrip("/")
    try:
        if not isinstance(argv, list) or not argv or not all(isinstance(part, str) and part for part in argv):
            raise ValueError("argv must be a non-empty list of non-empty strings")
        binary = posixpath.basename(argv[0]) if "/" not in argv[0] else argv[0]
        if binary not in allowed:
            raise ValueError(f"Command {argv[0]!r} is not in allowed read-only set {sorted(allowed)}")
        effective_cwd = _normalize_inside_root(cwd or cli_root, cli_root, cli_root)
        for token in argv[1:]:
            if token.startswith("-"):
                if token.startswith("--file="):
                    _normalize_inside_root(token.split("=", 1)[1], cli_root, effective_cwd)
                continue
            if "/" in token or ".." in token or token.startswith("~"):
                if token.startswith("~"):
                    raise ValueError("Home-relative paths are forbidden in restricted Guest CLI")
                _normalize_inside_root(token, cli_root, effective_cwd)
        command = ["/usr/bin/env", "-C", effective_cwd, binary, *argv[1:]]
        with action_lock() as lock_wait_s:
            response = requests.post(
                guest_url + "/execute",
                json={"command": command, "shell": False, "timeout": max_timeout},
                timeout=(5, max_timeout + 10),
            )
            response.raise_for_status()
            payload = response.json()
        raw_out = str(payload.get("output") or "")
        raw_err = str(payload.get("error") or "")
        combined = raw_out if not raw_err else (raw_out + ("\n" if raw_out else "") + raw_err)
        encoded = combined.encode("utf-8", errors="replace")
        truncated = len(encoded) > max_bytes
        if truncated:
            combined = encoded[:max_bytes].decode("utf-8", errors="ignore")
        returncode = int(payload.get("returncode", 0) or 0)
        ok = payload.get("status", "success") == "success" and returncode == 0
        result = {
            "ok": ok,
            "returncode": returncode,
            "cwd": effective_cwd,
            "output": combined,
            "truncated": truncated,
            "lock_wait_s": lock_wait_s,
        }
        _append_log({
            "t": time.time(),
            "tool": "run_guest_cli",
            "actor_id": os.environ.get("OSCOMBO_ACTOR_ID"),
            "episode_id": os.environ.get("OSCOMBO_EPISODE_ID"),
            "guest_key": os.environ.get("OSCOMBO_GUEST_KEY"),
            "condition": os.environ.get("OSCOMBO_CONDITION"),
            "args": {"argv": argv, "cwd": cwd},
            "result": {"status": "ok" if ok else "error", "returncode": returncode},
            "tool_elapsed_s": round(time.monotonic() - started, 4),
        })
        return result
    except Exception as exc:
        err = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        _append_log({
            "t": time.time(),
            "tool": "run_guest_cli",
            "actor_id": os.environ.get("OSCOMBO_ACTOR_ID"),
            "episode_id": os.environ.get("OSCOMBO_EPISODE_ID"),
            "args": {"argv": argv, "cwd": cwd},
            "error": err["error"],
            "tool_elapsed_s": round(time.monotonic() - started, 4),
        })
        return err


TOOL_SCHEMA = {
    "name": "run_guest_cli",
    "description": (
        "Run one read-only argv command (pwd, ls, cat, stat, grep, head, tail) inside your assigned "
        "Guest CLI directory without a shell. Each call starts a fresh process."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "argv": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": "Command and arguments, e.g. ['ls'] or ['cat', 'policy.txt'].",
            },
            "cwd": {
                "type": "string",
                "description": "Optional subdirectory inside your assigned CLI root.",
            },
        },
        "required": ["argv"],
        "additionalProperties": False,
    },
}


def mcp_main() -> None:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("guest_cli")

    @mcp.tool(description=TOOL_SCHEMA["description"])
    def guest_cli_call(argv: list[str], cwd: str | None = None) -> dict[str, Any]:
        return run_guest_cli(argv, cwd)

    guest_cli_call.__name__ = "run_guest_cli"
    mcp.run()


if __name__ == "__main__":
    if sys.argv[1:] == ["--mcp"]:
        mcp_main()
    else:
        parsed = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        print(json.dumps(run_guest_cli(parsed.get("argv", []), parsed.get("cwd")), ensure_ascii=False))
'''


GUEST_BASH_TOOLS_SOURCE = r'''"""WeaveBench-style unrestricted Guest Bash/CLI executor for the shared desktop arm."""
from __future__ import annotations

import base64
import fcntl
import io
import json
import os
import sys
import time
from typing import Any

from PIL import Image as PILImage
import requests


GUEST_BASH_SCHEMA = {
    "name": "guest_bash",
    "description": (
        "Execute a Bash command or script directly inside the shared target Ubuntu desktop VM "
        "(with DISPLAY=:0, Python/UNO, curl, xdotool, files, and apps available). "
        "Bounded timeout (default 30s, max 90s); returns stdout/stderr, returncode, and optional screenshot."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Bash command or inline script to run on the target Guest desktop.",
            },
            "cwd": {
                "type": "string",
                "description": "Optional working directory inside the Guest VM.",
            },
            "timeout": {
                "type": "number",
                "default": 30.0,
                "description": "Timeout in seconds (1..90).",
            },
            "screenshot": {
                "type": "boolean",
                "default": False,
                "description": "Set true to also capture and return a fresh 1280x720 desktop screenshot.",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    },
}


def _reserve_step(log_path: str | None, budget: int) -> tuple[int, bool]:
    if not log_path:
        return 1, True
    state_path = os.path.join(os.path.dirname(log_path), "tool_state.json")
    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
    with open(state_path + ".lock", "a+") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            state = json.load(open(state_path)) if os.path.exists(state_path) else {
                "calls": 0, "scale": [1.5, 1.5], "guest_screenshot_size": None, "model_screenshot_size": [1280, 720]
            }
            if state["calls"] >= budget:
                return state["calls"], False
            state["calls"] += 1
            step_no = state["calls"]
            json.dump(state, open(state_path, "w"))
            return step_no, True
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def run_guest_bash(
    command: str,
    cwd: str | None = None,
    timeout: float = 30.0,
    screenshot: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    guest_url = os.environ.get("OSCOMBO_GUEST_URL", "http://127.0.0.1:5000").rstrip("/")
    log_path = os.environ.get("OSCOMBO_ACTION_LOG")
    budget = int(os.environ.get("OSCOMBO_MAX_STEPS") or "45")
    step_no, allowed = _reserve_step(log_path, budget)
    if not allowed:
        return {
            "ok": False,
            "returncode": -1,
            "output": f"Action budget used up ({budget} tool calls). Stop now and reply with one short line.",
        }
    if not isinstance(command, str) or not command.strip():
        return {"ok": False, "returncode": 2, "output": "Supply a non-empty Bash command"}
    bounded_timeout = min(90.0, max(1.0, float(timeout or 30.0)))
    target_cwd = cwd or os.environ.get("OSCOMBO_CLI_ROOT") or "/tmp"
    wrapped_py = (
        "import os, subprocess, sys\n"
        f"cwd = {target_cwd!r}\n"
        "if not os.path.isdir(cwd): cwd = '/tmp'\n"
        "env = dict(os.environ)\n"
        "env.setdefault('DISPLAY', ':0')\n"
        "if os.path.exists('/run/user/1000/bus'):\n"
        "    env.setdefault('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/run/user/1000/bus')\n"
        f"cp = subprocess.run(['bash', '-lc', {command!r}], cwd=cwd, env=env, capture_output=True, text=True, timeout={bounded_timeout})\n"
        "sys.stdout.write(cp.stdout[-16384:])\n"
        "if cp.stderr:\n"
        "    sys.stdout.write(('\\n[stderr]\\n' if cp.stdout else '[stderr]\\n') + cp.stderr[-8192:])\n"
        "raise SystemExit(cp.returncode)\n"
    )
    image_b64 = None
    try:
        resp = requests.post(
            guest_url + "/execute",
            json={"command": ["python3", "-c", wrapped_py], "shell": False, "timeout": bounded_timeout + 5},
            timeout=(5, bounded_timeout + 15),
        )
        resp.raise_for_status()
        payload = resp.json()
        output = str(payload.get("output") or "")
        if payload.get("error"):
            output = (output + "\n" + str(payload["error"])).strip()
        returncode = int(payload.get("returncode", 0) or 0)
        ok = returncode == 0
        if screenshot:
            shot_resp = requests.get(guest_url + "/screenshot", timeout=30)
            if shot_resp.status_code == 200 and shot_resp.content:
                im = PILImage.open(io.BytesIO(shot_resp.content)).convert("RGB")
                buf = io.BytesIO()
                im.resize((1280, 720), PILImage.LANCZOS).save(buf, "PNG")
                image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        result = {
            "ok": ok,
            "returncode": returncode,
            "cwd": target_cwd,
            "output": output[:24000],
            "image": image_b64,
        }
        if log_path:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps({
                    "t": time.time(),
                    "n": step_no,
                    "tool": "guest_bash",
                    "actor_id": os.environ.get("OSCOMBO_ACTOR_ID"),
                    "episode_id": os.environ.get("OSCOMBO_EPISODE_ID"),
                    "guest_key": os.environ.get("OSCOMBO_GUEST_KEY"),
                    "condition": os.environ.get("OSCOMBO_CONDITION"),
                    "model": os.environ.get("OSCOMBO_MODEL"),
                    "args": {"command": command[:1000], "cwd": cwd, "timeout": bounded_timeout, "screenshot": screenshot},
                    "code": command[:1000],
                    "executed": True,
                    "action_attempted": True,
                    "action_succeeded": ok,
                    "tool_elapsed_s": round(time.monotonic() - started, 4),
                    "result": {"status": "ok" if ok else "nonzero", "returncode": returncode},
                }, ensure_ascii=False) + "\n")
        return result
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        if log_path:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps({
                    "t": time.time(),
                    "n": step_no,
                    "tool": "guest_bash",
                    "args": {"command": command[:1000], "cwd": cwd},
                    "executed": False,
                    "error": err_msg,
                    "tool_elapsed_s": round(time.monotonic() - started, 4),
                }, ensure_ascii=False) + "\n")
        return {"ok": False, "returncode": -1, "error": err_msg, "output": err_msg}


if __name__ == "__main__":
    raw_arg = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(run_guest_bash(
        raw_arg.get("command", ""),
        cwd=raw_arg.get("cwd"),
        timeout=float(raw_arg.get("timeout", 30.0)),
        screenshot=bool(raw_arg.get("screenshot", False)),
    ), ensure_ascii=False))
'''


HYBRID_V2_MODULE_SOURCE = r'''"""Hybrid v2 runtime configuration for CoDesk."""
from __future__ import annotations

import os
import sys
import sysconfig

MCP_PYTHON = os.environ.get("CODESK_MCP_PYTHON", sys.executable)
MCP_SITE = os.environ.get("CODESK_MCP_SITE", sysconfig.get_paths().get("purelib", ""))
'''


DESKTOP_GATE_LOCK_HELPERS = r'''
def _normalize_actor_token(value: str | None) -> str:
    if not value:
        return ""
    cleaned = str(value).strip()
    if cleaned.lower().startswith("actor_"):
        cleaned = cleaned[6:]
    return cleaned.upper()


@contextmanager
def action_lock():
    lock_file = os.environ.get("OSCOMBO_ACTION_LOCK_FILE") or os.environ.get("OSCOMBO_DESKTOP_LOCK_FILE")
    if not lock_file:
        yield None
        return
    os.makedirs(os.path.dirname(lock_file) or ".", exist_ok=True)
    with open(lock_file, "a+") as handle:
        started = time.monotonic()
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield round(time.monotonic() - started, 6)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _gate_arg_matches(cfg: dict, args: dict) -> bool:
    arg_name = cfg.get("argument")
    if not arg_name:
        return True
    if arg_name not in args:
        return False
    raw_val = args.get(arg_name)
    numeric_coord = arg_name in {"x", "y", "x1", "y1", "x2", "y2"} or isinstance(raw_val, (int, float))
    if numeric_coord and not isinstance(raw_val, bool):
        try:
            norm = str(int(round(float(raw_val))))
        except (TypeError, ValueError):
            return False
        if cfg.get("contains") is not None and str(cfg["contains"]).strip() == norm:
            return True
        if cfg.get("contains_any") and norm in {str(item).strip() for item in cfg["contains_any"]}:
            return True
        return False
    text_val = str(raw_val).lower()
    if cfg.get("contains") is not None and str(cfg["contains"]).lower() in text_val:
        return True
    if cfg.get("contains_any") and any(str(item).lower() in text_val for item in cfg["contains_any"]):
        return True
    return False


def _check_and_hold_gate(tool_name: str, args: dict):
    cfg_path = os.environ.get("OSCOMBO_MCP_GATE_CONFIG")
    if not cfg_path or not os.path.isfile(cfg_path):
        return None
    try:
        with open(cfg_path, encoding="utf-8") as handle:
            cfg = json.load(handle)
    except Exception:
        return None
    expected_actor = _normalize_actor_token(cfg.get("actor_id"))
    current_actor = _normalize_actor_token(os.environ.get("OSCOMBO_ACTOR_ID"))
    if expected_actor and current_actor and expected_actor != current_actor:
        return None
    if cfg.get("tool") and cfg.get("tool") != tool_name:
        return None
    if not _gate_arg_matches(cfg, args):
        return None
    signal_dir = cfg.get("signal_dir")
    if not signal_dir:
        return None
    os.makedirs(signal_dir, exist_ok=True)
    pending_path = os.path.join(signal_dir, "pending.json")
    release_path = os.path.join(signal_dir, "release.json")
    dispatched_path = os.path.join(signal_dir, "dispatched.json")
    if os.path.exists(dispatched_path) or os.path.exists(pending_path):
        return None
    pending_payload = {
        "gate_id": cfg.get("gate_id"),
        "actor_id": os.environ.get("OSCOMBO_ACTOR_ID") or cfg.get("actor_id"),
        "episode_id": os.environ.get("OSCOMBO_EPISODE_ID"),
        "guest_key": os.environ.get("OSCOMBO_GUEST_KEY"),
        "tool": tool_name,
        "args": args,
        "pending_unix": time.time(),
    }
    tmp_pending = pending_path + f".{os.getpid()}.tmp"
    with open(tmp_pending, "w", encoding="utf-8") as stream:
        json.dump(pending_payload, stream, indent=2)
        stream.write("\n")
    os.replace(tmp_pending, pending_path)
    timeout_s = float(cfg.get("timeout_seconds", 3500))
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if os.path.isfile(release_path):
            return {"signal_dir": signal_dir, "gate_id": cfg.get("gate_id")}
        time.sleep(0.1)
    raise TimeoutError(f"MCP gate {cfg.get('gate_id')} timed out waiting for release.json")


def _mark_gate_dispatched(gate_info: dict | None, tool_name: str, args: dict) -> None:
    if not gate_info:
        return
    dispatched_path = os.path.join(gate_info["signal_dir"], "dispatched.json")
    tmp_path = dispatched_path + f".{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as stream:
        json.dump({
            "gate_id": gate_info.get("gate_id"),
            "tool": tool_name,
            "args": args,
            "dispatched_unix": time.time(),
        }, stream, indent=2)
        stream.write("\n")
    os.replace(tmp_path, dispatched_path)
'''


RESPONSES_RELAY_SOURCE = r'''"""Loopback Responses relay with token budgets, image-history windowing, and 429 Retry-After backoff."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time

import requests

from experiments.responses_relay import prepare_image_history


def summarize_request(raw: bytes) -> dict:
    try:
        body = json.loads(raw)
    except Exception:
        return {"request_json": False}
    tools = []
    for item in body.get("tools") or []:
        if isinstance(item, dict):
            name = item.get("name") or (item.get("function") or {}).get("name")
            if isinstance(name, str):
                tools.append(name)
    images = 0

    def count_img(node):
        nonlocal images
        if isinstance(node, dict):
            if node.get("type") in {"input_image", "image_url"}:
                images += 1
            for child in node.values():
                count_img(child)
        elif isinstance(node, list):
            for child in node:
                count_img(child)

    count_img(body.get("input"))
    return {
        "request_json": True,
        "model": body.get("model"),
        "stream": bool(body.get("stream")),
        "tool_count": len(tools),
        "image_parts": images,
    }


def make_server(
    host: str,
    port: int,
    upstream: str,
    api_key: str,
    event_log: Path | None = None,
    *,
    client_token: str,
    fallback_upstream: str | None = None,
    output_token_budget: int | None = None,
    response_token_cap: int | None = None,
    reserve_on_missing_usage: bool = False,
    image_history_keep: int = 12,
    max_request_images: int = 45,
) -> ThreadingHTTPServer:
    upstreams = [("preferred", upstream.rstrip("/") + "/responses")]
    if fallback_upstream and fallback_upstream.rstrip("/") != upstream.rstrip("/"):
        upstreams.append(("fallback", fallback_upstream.rstrip("/") + "/responses"))
    budget_lock = threading.Lock()
    budgets_by_actor: dict[str, dict] = {}

    def actor_budget(actor_key: str) -> dict:
        return budgets_by_actor.setdefault(actor_key, {"output_tokens": 0, "usage_unknown": False})

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            return

        def do_GET(self):
            if self.path.rstrip("/") == "/health":
                payload = json.dumps({"ready": True, "pid": os.getpid()}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_error(404)

        def do_POST(self):
            clean_path = self.path.split("?", 1)[0].rstrip("/")
            actor_key = "default"
            if clean_path.startswith("/actor/") and clean_path.endswith("/v1/responses"):
                parts = clean_path.split("/")
                if len(parts) >= 3:
                    actor_key = parts[2]
            elif clean_path != "/v1/responses":
                self.send_error(404)
                return
            if not hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {client_token}"):
                self.send_error(401)
                return
            started = time.monotonic()
            attempts = []
            response_started = False
            if output_token_budget is not None:
                budget_lock.acquire()
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 48 * 1024 * 1024:
                    self.send_error(413)
                    return
                raw = self.rfile.read(length)
                body = json.loads(raw)
                if isinstance(body, dict) and isinstance(body.get("input"), list) and not body.get("previous_response_id"):
                    try:
                        body, _img_audit = prepare_image_history(
                            body, keep=image_history_keep, max_images=max_request_images
                        )
                    except Exception:
                        pass
                state = actor_budget(actor_key)
                if output_token_budget is not None:
                    remaining = output_token_budget - state["output_tokens"]
                    if remaining <= 0 or state["usage_unknown"]:
                        if event_log is not None:
                            event_log.parent.mkdir(parents=True, exist_ok=True)
                            with event_log.open("a", encoding="utf-8") as stream:
                                stream.write(json.dumps({
                                    "time": time.time(),
                                    "actor": actor_key,
                                    "budget_stop": True,
                                    "output_tokens_used": state["output_tokens"],
                                    "output_token_budget": output_token_budget,
                                    "usage_unknown": state["usage_unknown"],
                                }) + "\n")
                        self.send_error(409, "actor output token budget exhausted")
                        return
                    cap = remaining
                    if response_token_cap is not None:
                        cap = min(cap, int(response_token_cap))
                    existing_cap = body.get("max_output_tokens")
                    body["max_output_tokens"] = min(int(existing_cap), cap) if existing_cap else cap
                elif response_token_cap is not None and not body.get("max_output_tokens"):
                    body["max_output_tokens"] = int(response_token_cap)
                raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                request_meta = summarize_request(raw)
                upstream_response = None
                selected_endpoint = None
                for label, target in upstreams:
                    for retry_idx in range(8):
                        resp = requests.post(
                            target,
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json",
                                "Accept": self.headers.get("Accept", "text/event-stream"),
                            },
                            data=raw,
                            stream=True,
                            timeout=(20, 300),
                        )
                        attempts.append({
                            "endpoint": label,
                            "attempt": retry_idx + 1,
                            "status": resp.status_code,
                        })
                        if resp.status_code in (429, 502, 503, 504) and retry_idx < 7:
                            retry_after = resp.headers.get("Retry-After")
                            try:
                                sleep_s = min(max(float(retry_after), 5.0), 35.0) if retry_after else (10.0 + 5.0 * retry_idx)
                            except ValueError:
                                sleep_s = 15.0
                            resp.close()
                            time.sleep(sleep_s)
                            continue
                        upstream_response = resp
                        selected_endpoint = label
                        break
                    if upstream_response is not None:
                        break
                if upstream_response is None:
                    raise RuntimeError("No upstream response obtained")
                with upstream_response:
                    status = upstream_response.status_code
                    self.send_response(status)
                    self.send_header("Content-Type", upstream_response.headers.get("Content-Type", "text/event-stream"))
                    if "Retry-After" in upstream_response.headers:
                        self.send_header("Retry-After", upstream_response.headers["Retry-After"])
                    self.send_header("Connection", "close")
                    self.end_headers()
                    response_started = True
                    pending = b""
                    usage = None
                    streamed_bytes = 0
                    for chunk in upstream_response.iter_content(chunk_size=16384):
                        if not chunk:
                            continue
                        streamed_bytes += len(chunk)
                        pending += chunk
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            stripped = line.strip()
                            if stripped.startswith(b"data:"):
                                stripped = stripped[5:].strip()
                            if not stripped or stripped == b"[DONE]":
                                continue
                            try:
                                ev = json.loads(stripped)
                                resp_obj = ev.get("response")
                                cand = resp_obj.get("usage") if isinstance(resp_obj, dict) else ev.get("usage")
                                if isinstance(cand, dict):
                                    usage = cand
                            except Exception:
                                pass
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    if usage is None and pending.strip():
                        try:
                            tail = pending.strip()
                            if tail.startswith(b"data:"):
                                tail = tail[5:].strip()
                            ev = json.loads(tail)
                            resp_obj = ev.get("response")
                            cand = resp_obj.get("usage") if isinstance(resp_obj, dict) else ev.get("usage")
                            if isinstance(cand, dict):
                                usage = cand
                        except Exception:
                            pass
                    if output_token_budget is not None and status == 200:
                        if isinstance(usage, dict) and isinstance(usage.get("output_tokens"), int):
                            state["output_tokens"] += usage["output_tokens"]
                        elif reserve_on_missing_usage:
                            estimated_missing = min(int(response_token_cap or 256), max(32, min(256, streamed_bytes // 32)))
                            state["output_tokens"] += estimated_missing
                        else:
                            state["output_tokens"] += 256
                    self.close_connection = True
                if event_log is not None:
                    event_log.parent.mkdir(parents=True, exist_ok=True)
                    with event_log.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({
                            "time": time.time(),
                            "actor": actor_key,
                            **request_meta,
                            "request_bytes": len(raw),
                            "upstream_status": status,
                            "selected_endpoint": selected_endpoint,
                            "endpoint_attempts": attempts,
                            "usage": usage,
                            "output_tokens_used": state["output_tokens"] if output_token_budget is not None else None,
                            "elapsed_s": round(time.monotonic() - started, 3),
                        }) + "\n")
            except Exception as exc:
                if event_log is not None:
                    event_log.parent.mkdir(parents=True, exist_ok=True)
                    with event_log.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({
                            "time": time.time(),
                            "actor": actor_key,
                            "error_type": type(exc).__name__,
                            "endpoint_attempts": attempts,
                            "elapsed_s": round(time.monotonic() - started, 3),
                        }) + "\n")
                self.close_connection = True
                if not response_started:
                    try:
                        self.send_error(502, "Responses relay upstream error")
                    except OSError:
                        pass
            finally:
                if output_token_budget is not None:
                    budget_lock.release()

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--fallback-upstream")
    parser.add_argument("--api-key-env", required=True)
    parser.add_argument("--client-token-env", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--promote-tool-image", action="store_true")
    parser.add_argument("--task-reminder-env")
    parser.add_argument("--output-token-budget", type=int, default=None)
    parser.add_argument("--response-token-cap", type=int, default=None)
    parser.add_argument("--reserve-on-missing-usage", action="store_true")
    parser.add_argument("--size-aware-upload-timeout", action="store_true")
    args = parser.parse_args()
    api_key = os.environ.get(args.api_key_env)
    client_token = os.environ.get(args.client_token_env)
    if not api_key or not client_token:
        parser.error("Missing required relay key or client token environment variable")
    server = make_server(
        args.host,
        args.port,
        args.upstream,
        api_key,
        args.event_log,
        client_token=client_token,
        fallback_upstream=args.fallback_upstream,
        output_token_budget=args.output_token_budget,
        response_token_cap=args.response_token_cap,
        reserve_on_missing_usage=args.reserve_on_missing_usage,
    )
    if args.ready_file:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.write_text(json.dumps({
            "pid": os.getpid(),
            "host": args.host,
            "port": server.server_port,
        }) + "\n", encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
'''


CONTAINER_CODEX_HARNESS_REPLACEMENT = r'''
class CodexHarness(CommandHarness):
    """Containerized non-YOLO Codex CLI harness using airgapped Docker + Unix-socket MCP bridge."""

    def prepare(self, ctx: AgentContext) -> None:
        super().prepare(ctx)
        self.full_cli = bool(self.opts.get("full_cli")) or os.environ.get("CODESK_FULL_CLI_ARM") == "1"
        self._permission_mode = "container-unrestricted" if self.full_cli else "container-read-only-mcp"
        self.collaboration = self.opts.get("collaboration")
        if self.collaboration:
            required = {"actor", "url", "token_env"}
            missing = required - set(self.collaboration.keys())
            if missing:
                raise ValueError(f"options.collaboration missing: {sorted(missing)}")
            if self.collaboration["actor"] not in {"A", "B", "S"}:
                raise ValueError("collaboration actor must be A, B, or S")
            if not os.environ.get(self.collaboration["token_env"]):
                raise ValueError(f"collaboration token env unset: {self.collaboration['token_env']}")
        self.session_dir = self.dir / "container_session"
        for sub in ("codex-home", "work", "bridge"):
            (self.session_dir / sub).mkdir(parents=True, exist_ok=True)
        os.chmod(self.session_dir, 0o770)
        os.chmod(self.session_dir / "codex-home", 0o770)
        os.chmod(self.session_dir / "work", 0o770)
        from experiments.codesk_container_codex import (
            CONTAINER_ENTRY_SOURCE,
            DEFAULT_CODEX_BINARY,
            DEFAULT_CONTAINER_IMAGE,
            GUEST_BASH_BRIDGE_CLI_SOURCE,
            MCP_PROXY_SOURCE,
            validate_container_config_text,
        )
        (self.session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
        (self.session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
        if self.full_cli:
            (self.session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")
        model = require_model(self.spec)
        base_inst = (
            "You are a hybrid GUI+CLI agent operating a shared Ubuntu desktop. "
            "Use full CLI/programming tools (guest_bash, Python/UNO, shell, curl) and GUI tools together as most effective."
            if self.full_cli
            else "You are a GUI agent. Use only the tools supplied for this task."
        )
        (self.session_dir / "codex-home/models-catalog.json").write_text(json.dumps({"models": [{
            "slug": model,
            "display_name": model,
            "description": "Configured vision-capable GUI agent model for CoDesk computer-use tasks.",
            "default_reasoning_level": self.spec.get("effort") or "medium",
            "supported_reasoning_levels": [
                {"effort": level, "description": f"{level} reasoning"}
                for level in ("low", "medium", "high", "xhigh")
            ],
            "shell_type": "unified_exec",
            "visibility": "list",
            "supported_in_api": True,
            "priority": 1,
            "additional_speed_tiers": [],
            "service_tiers": [],
            "availability_nux": None,
            "upgrade": None,
            "model_messages": None,
            "include_skills_usage_instructions": False,
            "include_plugin_usage_instructions": False,
            "include_apps_usage_instructions": False,
            "default_reasoning_summary": "none",
            "support_verbosity": False,
            "default_verbosity": "low",
            "apply_patch_tool_type": "freeform",
            "web_search_tool_type": "text_and_image",
            "truncation_policy": {"mode": "tokens", "limit": 10000},
            "supports_parallel_tool_calls": False,
            "supports_image_detail_original": True,
            "context_window": 262144,
            "max_context_window": 262144,
            "comp_hash": "",
            "effective_context_window_percent": 95,
            "experimental_supported_tools": [],
            "input_modalities": ["text", "image"],
            "supports_search_tool": False,
            "use_responses_lite": False,
            "tool_mode": "direct",
            "multi_agent_version": "v2",
            "base_instructions": base_inst,
        }]}, indent=2) + "\n", encoding="utf-8")
        self._codex_binary = Path(os.environ.get("CODESK_CONTAINER_CODEX_BIN", str(DEFAULT_CODEX_BINARY)))
        self.binary = str(self._codex_binary)
        self._container_image = os.environ.get("CODESK_CODEX_CONTAINER_IMAGE", DEFAULT_CONTAINER_IMAGE)
        template_toml = self._build_container_config_template(ctx)
        validate_container_config_text(template_toml.replace("__CONTAINER_RELAY_PORT__", "18080"), mode=self._permission_mode)
        (self.session_dir / "codex-home/config.template.toml").write_text(template_toml, encoding="utf-8")
        (self.session_dir / "prompt.txt").write_text(self.prompt(ctx), encoding="utf-8")
        for dir_candidate in (self.dir.parent, self.dir, self.session_dir):
            if dir_candidate.is_dir():
                try:
                    os.chmod(dir_candidate, 0o770)
                except OSError:
                    pass
        for session_item in self.session_dir.rglob("*"):
            try:
                os.chmod(session_item, 0o770 if session_item.is_dir() else 0o660)
            except OSError:
                pass
        self.harness_version = self.version(str(self._codex_binary)) or "codex-cli-container"

    def prompt(self, ctx: AgentContext) -> str:
        if getattr(self, "full_cli", False):
            instruction_text = ctx.instruction
            if "FULL HYBRID GUI+CLI mode" in instruction_text:
                return instruction_text + self.opts.get("prompt_suffix", "")
            return (
                "You are operating a real shared Ubuntu 22.04 GNOME desktop (1280x720 GUI screenshots) in "
                "WeaveBench-style FULL HYBRID GUI+CLI mode (shared desktop, no cross-agent lock). Another "
                "independent agent works concurrently on the SAME live desktop, applications, and filesystem. "
                "Both GUI tools ('desktop' MCP: screenshot, click, type_text, key, scroll, drag, move, wait) "
                "AND full unrestricted CLI/programming on the shared Guest VM ('guest_bash' MCP tool, or "
                "python3 /bridge/guest_bash.py '<bash command>' from your container shell) are fully enabled. "
                f"The sudo password is '{client_password()}'. You may freely combine Bash commands, Python scripts, "
                "LibreOffice UNO, file inspection/editing, curl to local task endpoints, xdotool, and GUI controls — "
                "this hybrid permission overrides any GUI-only restriction phrased in the task text below. "
                "Do not tamper with running evaluation web server source code or forge logs.\n\n"
                f"Task: {instruction_text}\n\n"
                "Verify live application state and saved files agree, satisfy required collaboration handoffs, and reply concisely when done."
            ) + self.opts.get("prompt_suffix", "")
        return super().prompt(ctx)

    def _resolve_mcp_python(self) -> str:
        mcp_python = self.opts.get("mcp_python") or os.environ.get("CODESK_MCP_PYTHON") or sys.executable
        candidate = Path(mcp_python)
        if candidate.is_file():
            return os.path.abspath(candidate)
        return sys.executable

    def _desktop_env(self, ctx: AgentContext) -> dict[str, str]:
        opts = self.opts
        env = dict(os.environ)
        env.update({
            "OSCOMBO_GUEST_URL": ctx.guest.url,
            "OSCOMBO_ACTION_LOG": str(self.action_log),
            "OSCOMBO_MAX_STEPS": str(ctx.max_steps),
            "OSCOMBO_MODEL": str(require_model(self.spec)),
            "OSCOMBO_ACTOR_ID": str(getattr(ctx.guest, "actor", None) or ctx.name),
            "OSCOMBO_GUEST_KEY": str(getattr(ctx.guest, "guest_key", None) or "guest"),
            "PYTHONPATH": _pythonpath(),
        })
        if opts.get("episode_id"):
            env["OSCOMBO_EPISODE_ID"] = str(opts["episode_id"])
        if opts.get("condition"):
            env["OSCOMBO_CONDITION"] = str(opts["condition"])
        if opts.get("action_lock_file"):
            env["OSCOMBO_ACTION_LOCK_FILE"] = str(opts["action_lock_file"])
        if opts.get("desktop_lock_file"):
            env["OSCOMBO_DESKTOP_LOCK_FILE"] = str(opts["desktop_lock_file"])
            env["OSCOMBO_ACTION_LOCK_FILE"] = str(opts["desktop_lock_file"])
        if opts.get("type_text_mode"):
            env["OSCOMBO_TYPE_TEXT_MODE"] = str(opts["type_text_mode"])
        if "min_non_black_pixel_fraction" in opts:
            env["OSCOMBO_SCREENSHOT_MIN_NON_BLACK_FRACTION"] = str(float(opts["min_non_black_pixel_fraction"]))
        if opts.get("require_nonflat_screenshot"):
            env["OSCOMBO_SCREENSHOT_REQUIRE_NONFLAT"] = "1"
        if opts.get("screenshot_stop_file"):
            env["OSCOMBO_SCREENSHOT_STOP_FILE"] = str(opts["screenshot_stop_file"])
        if "desktop_tool_cooldown_sec" in opts:
            env["OSCOMBO_MCP_TURN_COOLDOWN_SEC"] = str(float(opts["desktop_tool_cooldown_sec"]))
        if "desktop_screenshot_settle_sec" in opts:
            env["OSCOMBO_MCP_SETTLE"] = str(float(opts["desktop_screenshot_settle_sec"]))
        for extra_k, extra_v in (opts.get("mcp_env_overrides") or {}).items():
            env[str(extra_k)] = str(extra_v)
        if self.full_cli:
            env.pop("OSCOMBO_ACTION_LOCK_FILE", None)
            env.pop("OSCOMBO_DESKTOP_LOCK_FILE", None)
            env.pop("OSCOMBO_MCP_GATE_CONFIG", None)
        return env

    def _build_container_config_template(self, ctx: AgentContext) -> str:
        import urllib.parse
        opts = self.opts
        raw_base = opts.get("base_url") or os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:18080/v1")
        parsed = urllib.parse.urlparse(raw_base)
        path_part = parsed.path or "/v1"
        key_env = opts.get("api_key_env", "OPENAI_API_KEY")
        auth_mode = opts.get("auth_mode", "auto")
        has_local_token = bool(os.environ.get(key_env)) and key_env not in {"OPENAI_API_KEY", "SWCUB_SOL_API_KEY", "LLMPROXY_API_KEY"}
        if auth_mode == "none" or not has_local_token:
            auth_line = "requires_openai_auth = false"
            self._container_relay_token_env = None
        else:
            auth_line = f'env_key = {json.dumps(key_env)}'
            self._container_relay_token_env = key_env
        request_retries = max(4, min(10, int(opts.get("request_retries", 6))))
        stream_retries = max(4, min(10, int(opts.get("stream_retries", request_retries))))
        desktop_timeout = int(opts.get("desktop_tool_timeout_sec", 300))
        approval_val = "never" if self.full_cli else "on-request"
        sandbox_val = "workspace-write" if self.full_cli else "read-only"
        shell_bool = "true" if self.full_cli else "false"
        workspace_write_block = ""
        if self.full_cli:
            workspace_write_block = """
[sandbox_workspace_write]
writable_roots = ["/session", "/tmp", "/ipc"]
network_access = true
"""
        guest_bash_block = ""
        if self.full_cli:
            guest_bash_block = """
[mcp_servers.guest_bash]
command = "python3"
args = ["/bridge/mcp_proxy.py", "guest_bash"]
enabled = true
required = true
enabled_tools = ["guest_bash"]
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "approve"
"""
        guest_cli_block = ""
        if opts.get("hybrid_v2"):
            guest_cli_block = """
[mcp_servers.guest_cli]
command = "python3"
args = ["/bridge/mcp_proxy.py", "guest_cli"]
enabled = true
required = true
enabled_tools = ["run_guest_cli"]
startup_timeout_sec = 30
tool_timeout_sec = 60
default_tools_approval_mode = "approve"
"""
        collab_block = ""
        if self.collaboration:
            collab_block = """
[mcp_servers.collaboration]
command = "python3"
args = ["/bridge/mcp_proxy.py", "collaboration"]
enabled = true
required = true
enabled_tools = ["send_message", "read_messages", "send_attachment", "read_attachment"]
startup_timeout_sec = 30
tool_timeout_sec = 30
default_tools_approval_mode = "approve"
"""
        return f"""model = {json.dumps(require_model(self.spec))}
model_provider = "oscombo"
model_reasoning_effort = {json.dumps(self.spec.get("effort") or "medium")}
model_catalog_json = "/session/codex-home/models-catalog.json"
model_context_window = 262144
approval_policy = {json.dumps(approval_val)}
sandbox_mode = {json.dumps(sandbox_val)}
web_search = "disabled"
mcp_optional_startup_grace_ms = 0

[model_providers.oscombo]
name = "oscombo"
base_url = "http://127.0.0.1:__CONTAINER_RELAY_PORT__{path_part}"
{auth_line}
wire_api = "responses"
supports_websockets = false
request_max_retries = {request_retries}
stream_max_retries = {stream_retries}
stream_idle_timeout_ms = 300000

[features]
shell_tool = {shell_bool}
unified_exec = false
multi_agent = false
image_generation = false
{workspace_write_block}
[mcp_servers.desktop]
command = "python3"
args = ["/bridge/mcp_proxy.py", "desktop"]
enabled = true
required = true
enabled_tools = ["screenshot", "click", "drag", "move", "type_text", "key", "scroll", "wait", "declare_infeasible"]
startup_timeout_sec = 60
tool_timeout_sec = {desktop_timeout}
default_tools_approval_mode = "approve"
{guest_bash_block}{guest_cli_block}{collab_block}"""

    def _make_mcp_handlers(self, ctx: AgentContext) -> dict:
        from oscombo.desktop_tools import TOOLS as DESKTOP_TOOL_DESC
        mcp_python = self._resolve_mcp_python()
        desktop_env = self._desktop_env(ctx)
        desktop_timeout = int(self.opts.get("desktop_tool_timeout_sec", 300)) + 30

        desktop_schemas = [
            {"name": "screenshot", "description": DESKTOP_TOOL_DESC["screenshot"],
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "click", "description": DESKTOP_TOOL_DESC["click"],
             "inputSchema": {"type": "object", "properties": {
                 "x": {"type": "integer"}, "y": {"type": "integer"},
                 "button": {"type": "string", "default": "left"},
                 "clicks": {"type": "integer", "default": 1},
             }, "required": ["x", "y"], "additionalProperties": False}},
            {"name": "drag", "description": DESKTOP_TOOL_DESC["drag"],
             "inputSchema": {"type": "object", "properties": {
                 "x1": {"type": "integer"}, "y1": {"type": "integer"},
                 "x2": {"type": "integer"}, "y2": {"type": "integer"},
             }, "required": ["x1", "y1", "x2", "y2"], "additionalProperties": False}},
            {"name": "move", "description": DESKTOP_TOOL_DESC["move"],
             "inputSchema": {"type": "object", "properties": {
                 "x": {"type": "integer"}, "y": {"type": "integer"},
             }, "required": ["x", "y"], "additionalProperties": False}},
            {"name": "type_text", "description": DESKTOP_TOOL_DESC["type_text"],
             "inputSchema": {"type": "object", "properties": {
                 "text": {"type": "string"},
             }, "required": ["text"], "additionalProperties": False}},
            {"name": "key", "description": DESKTOP_TOOL_DESC["key"],
             "inputSchema": {"type": "object", "properties": {
                 "keys": {"type": "string"},
             }, "required": ["keys"], "additionalProperties": False}},
            {"name": "scroll", "description": DESKTOP_TOOL_DESC["scroll"],
             "inputSchema": {"type": "object", "properties": {
                 "x": {"type": "integer"}, "y": {"type": "integer"},
                 "direction": {"type": "string", "default": "down"},
                 "amount": {"type": "integer", "default": 3},
             }, "required": ["x", "y"], "additionalProperties": False}},
            {"name": "wait", "description": DESKTOP_TOOL_DESC["wait"],
             "inputSchema": {"type": "object", "properties": {
                 "seconds": {"type": "number", "default": 2.0},
             }, "additionalProperties": False}},
            {"name": "declare_infeasible", "description": DESKTOP_TOOL_DESC["declare_infeasible"],
             "inputSchema": {"type": "object", "properties": {
                 "reason": {"type": "string"},
             }, "required": ["reason"], "additionalProperties": False}},
        ]

        def call_desktop(name: str, arguments: dict) -> dict:
            completed = subprocess.run(
                [mcp_python, "-m", "oscombo.desktop_tools", name, json.dumps(arguments)],
                env=desktop_env,
                capture_output=True,
                text=True,
                timeout=desktop_timeout,
            )
            if completed.returncode != 0:
                return {"content": [{"type": "text", "text": f"Error: {completed.stderr[-600:]}"}], "isError": True}
            payload = json.loads(completed.stdout)
            if payload.get("error"):
                return {"content": [{"type": "text", "text": str(payload["error"])}], "isError": True}
            content = [{"type": "text", "text": str(payload.get("text") or "OK.")}]
            if payload.get("image"):
                content.append({"type": "image", "data": payload["image"], "mimeType": "image/png"})
            return {"content": content, "isError": False}

        handlers = {"desktop": {"list": lambda: desktop_schemas, "call": call_desktop}}

        if self.full_cli:
            from oscombo.guest_bash_tools import GUEST_BASH_SCHEMA
            bash_env = dict(desktop_env)
            if self.opts.get("cli_root"):
                bash_env["OSCOMBO_CLI_ROOT"] = str(self.opts["cli_root"])

            def call_guest_bash(name: str, arguments: dict) -> dict:
                if name != "guest_bash":
                    return {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True}
                completed = subprocess.run(
                    [mcp_python, "-m", "oscombo.guest_bash_tools", json.dumps(arguments)],
                    env=bash_env,
                    capture_output=True,
                    text=True,
                    timeout=110,
                )
                if completed.returncode != 0:
                    return {"content": [{"type": "text", "text": completed.stderr[-600:]}], "isError": True}
                parsed_out = json.loads(completed.stdout)
                img_data = parsed_out.pop("image", None)
                content = [{"type": "text", "text": json.dumps(parsed_out, ensure_ascii=False)}]
                if img_data:
                    content.append({"type": "image", "data": img_data, "mimeType": "image/png"})
                return {"content": content, "isError": not bool(parsed_out.get("ok"))}

            handlers["guest_bash"] = {"list": lambda: [GUEST_BASH_SCHEMA], "call": call_guest_bash}

        if self.opts.get("hybrid_v2"):
            from oscombo.guest_cli_tools import TOOL_SCHEMA as CLI_SCHEMA
            cli_dir = self.dir / "guest_cli"
            cli_dir.mkdir(parents=True, exist_ok=True)
            cli_env = dict(desktop_env)
            cli_env.update({
                "OSCOMBO_ACTION_LOG": str(cli_dir / "actions.jsonl"),
                "OSCOMBO_CLI_ROOT": str(self.opts.get("cli_root") or "/tmp"),
                "OSCOMBO_CLI_ALLOWED_COMMANDS": "pwd,ls,cat,stat,grep,head,tail",
                "OSCOMBO_CLI_MAX_TIMEOUT_SEC": "20",
                "OSCOMBO_CLI_MAX_OUTPUT_BYTES": "12000",
            })

            def call_guest_cli(name: str, arguments: dict) -> dict:
                if name != "run_guest_cli":
                    return {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True}
                completed = subprocess.run(
                    [mcp_python, "-m", "oscombo.guest_cli_tools", json.dumps(arguments)],
                    env=cli_env,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                if completed.returncode != 0:
                    return {"content": [{"type": "text", "text": completed.stderr[-600:]}], "isError": True}
                parsed_out = json.loads(completed.stdout)
                return {
                    "content": [{"type": "text", "text": json.dumps(parsed_out, ensure_ascii=False)}],
                    "isError": not bool(parsed_out.get("ok")),
                }

            handlers["guest_cli"] = {"list": lambda: [CLI_SCHEMA], "call": call_guest_cli}

        if self.collaboration:
            from oscombo.collab.data_to_deck.collab_tools import CollaborationClient
            collab_schemas = [
                {"name": "send_message",
                 "description": "Send a task-related message to the other Actor. Use recipient A, B, or all.",
                 "inputSchema": {"type": "object", "properties": {
                     "recipient": {"type": "string"},
                     "body": {"type": "string"},
                     "attachment_ids": {"type": "array", "items": {"type": "string"}},
                 }, "required": ["recipient", "body"], "additionalProperties": False}},
                {"name": "read_messages",
                 "description": "Read messages addressed to this Actor after a Unix timestamp; after=0 reads all.",
                 "inputSchema": {"type": "object", "properties": {
                     "after": {"type": "number", "default": 0},
                 }, "additionalProperties": False}},
                {"name": "send_attachment",
                 "description": "Attach a UTF-8 or binary file supplied as base64. Returns an attachment ID and SHA-256.",
                 "inputSchema": {"type": "object", "properties": {
                     "filename": {"type": "string"},
                     "content_base64": {"type": "string"},
                 }, "required": ["filename", "content_base64"], "additionalProperties": False}},
                {"name": "read_attachment",
                 "description": "Read an attachment by ID.",
                 "inputSchema": {"type": "object", "properties": {
                     "attachment_id": {"type": "string"},
                 }, "required": ["attachment_id"], "additionalProperties": False}},
            ]

            def call_collab(name: str, arguments: dict) -> dict:
                import base64 as _b64
                client = CollaborationClient(
                    self.collaboration["url"],
                    self.collaboration["actor"],
                    os.environ[self.collaboration["token_env"]],
                )
                if name == "send_message":
                    res = client.send_message(arguments["recipient"], arguments["body"], arguments.get("attachment_ids"))
                elif name == "read_messages":
                    res = client.read_messages(float(arguments.get("after", 0)))
                elif name == "send_attachment":
                    raw_bytes = _b64.b64decode(arguments["content_base64"], validate=True)
                    res = client.send_attachment(arguments["filename"], raw_bytes)
                elif name == "read_attachment":
                    res = client.read_attachment(arguments["attachment_id"])
                else:
                    return {"content": [{"type": "text", "text": f"Unknown collaboration tool {name}"}], "isError": True}
                return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": False}

            handlers["collaboration"] = {"list": lambda: collab_schemas, "call": call_collab}

        return handlers

    def run(self, ctx: AgentContext, append_logs: bool = False) -> AgentResult:
        import secrets as _secrets
        import urllib.parse
        from experiments.codesk_container_codex import HostActorBridge, verify_container_permission_audit, codex_requirements_mount

        raw_base = self.opts.get("base_url") or os.environ.get("OPENAI_BASE_URL", "")
        parsed = urllib.parse.urlparse(raw_base)
        if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
            raise RuntimeError(f"ContainerizedCodexHarness requires a host loopback relay base_url, got {raw_base!r}")

        bridge = HostActorBridge(None, parsed.port, self._make_mcp_handlers(ctx))
        bridge.start()
        container_name = f"codesk-codex-{ctx.name.lower()}-{_secrets.token_hex(6)}"
        owner_token = _secrets.token_hex(16)
        create_cmd = [
            "docker", "create",
            "--name", container_name,
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,size=256m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "2048",
            "--cpus", "2",
            "--memory", "4g",
            "--user", "1000:0",
            "--label", "org.paragui.kind=codesk-codex-actor",
            "--label", f"org.paragui.owner={owner_token}",
            "-v", f"{self.session_dir}:/session",
            "-v", f"{self.session_dir / 'bridge'}:/bridge:ro",
            "-v", f"{bridge.ipc_dir}:/ipc",
            "-v", f"{self._codex_binary.parent}:/codex:ro",
            "-w", "/session",
            "-e", "HOME=/session",
            "-e", "CODEX_HOME=/session/codex-home",
            "-e", f"CODESK_CONTAINER_PERMISSION_MODE={self._permission_mode}",
            "-e", "TOKIO_WORKER_THREADS=4",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
        ]
        if self._container_relay_token_env:
            create_cmd += ["-e", f"{self._container_relay_token_env}={os.environ[self._container_relay_token_env]}"]
        create_cmd += [*codex_requirements_mount(), self._container_image, "python3", "/bridge/container_entry.py"]

        result = AgentResult(status="running")
        timeout = float(self.opts.get("timeout", 2400))
        started = time.monotonic()
        container_id = None
        try:
            created = subprocess.run(create_cmd, capture_output=True, text=True, timeout=45, check=True)
            container_id = created.stdout.strip()
            log_mode = "a" if append_logs else "w"
            with open(self.dir / "stdout.log", log_mode, encoding="utf-8") as out_f, open(self.dir / "stderr.log", log_mode, encoding="utf-8") as err_f:
                proc = subprocess.Popen(
                    ["docker", "start", "-a", container_id],
                    stdin=subprocess.DEVNULL,
                    stdout=out_f,
                    stderr=err_f,
                    start_new_session=True,
                )
                while proc.poll() is None:
                    if ctx.stop.is_set() or time.monotonic() - started > timeout:
                        subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=15)
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL)
                            proc.wait(timeout=5)
                        result.status = "timeout"
                        break
                    time.sleep(1.0)
            result.extra["exit_code"] = proc.returncode
            result.extra["agent_s"] = round(time.monotonic() - started, 1)
            audit = verify_container_permission_audit(
                self.session_dir,
                expected_model=require_model(self.spec),
                permission_mode=self._permission_mode,
            )
            (self.dir / "permission-audit-verified.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
            result.extra["permission_audit"] = audit["entry_audit"]
            result.trace = self.trace(ctx)
            used = sum(1 for row in result.trace if row.get("tool") != "declare_infeasible")
            if (self.dir / "INFEASIBLE").exists():
                result.status = "fail"
            elif result.status == "timeout":
                pass
            elif used >= self.budget:
                result.status = "max_steps"
            elif proc.returncode == 0:
                result.status = "done"
            else:
                result.status = "error"
                result.error = f"exit code {proc.returncode}: " + (self.dir / "stderr.log").read_text(encoding="utf-8", errors="replace")[-300:]
            return result
        finally:
            if container_id:
                inspected = subprocess.run(
                    ["docker", "inspect", container_id],
                    capture_output=True, text=True, timeout=15
                )
                if inspected.returncode == 0:
                    info = json.loads(inspected.stdout)[0]
                    labels = (info.get("Config") or {}).get("Labels") or {}
                    if info.get("Id") == container_id and labels.get("org.paragui.owner") == owner_token:
                        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, timeout=20)
            bridge.close()

    def resume_in_container(self, ctx: AgentContext, resume_prompt: str, timeout_s: float) -> AgentResult:
        if timeout_s <= 0:
            timeout_res = AgentResult(status="timeout")
            timeout_res.extra.update({"exit_code": None, "agent_s": 0.0, "resumed_after_external_update": True})
            timeout_res.trace = self.trace(ctx)
            return timeout_res
        resume_path = self.session_dir / "resume_prompt.txt"
        resume_path.write_text(resume_prompt, encoding="utf-8")
        try:
            os.chmod(resume_path, 0o660)
        except OSError:
            pass
        old_timeout = self.opts.get("timeout")
        self.opts["timeout"] = max(15, int(timeout_s))
        try:
            resumed_res = self.run(ctx, append_logs=True)
            resumed_res.extra["resumed_after_external_update"] = True
            return resumed_res
        finally:
            if resume_path.exists():
                resume_path.unlink()
            if old_timeout is None:
                self.opts.pop("timeout", None)
            else:
                self.opts["timeout"] = old_timeout

    def prompt(self, ctx: AgentContext) -> str:
        if self.full_cli:
            cli_hint = self.opts.get("cli_root") or "/tmp"
            collab_note = ""
            if self.collaboration:
                collab_note = (
                    "\nCollaboration MCP tools (send_message, read_messages, send_attachment, read_attachment) "
                    "are available to coordinate and exchange required handoff messages with the other actor."
                )
            return (
                "You are operating a real shared Ubuntu 22.04 desktop (1280x720 GUI screenshots) in the "
                "WeaveBench-style FULL HYBRID GUI+CLI mode (shared desktop, no cross-agent lock).\n"
                "Another independent agent works concurrently on the SAME live desktop, applications, and filesystem.\n"
                "Both GUI tools ('desktop' MCP: screenshot, click, type_text, key, scroll, drag, move, wait) AND "
                "full unrestricted CLI/programming on the shared Guest VM ('guest_bash' MCP tool, or "
                "python3 /bridge/guest_bash.py '<bash command>' from your container shell) are fully enabled.\n"
                "You may freely use Bash commands, Python scripts, LibreOffice UNO, file inspection/editing, curl to "
                "local task endpoints, xdotool, and GUI controls — this hybrid permission overrides any GUI-only or "
                "read-only-CLI restriction phrased in the task text below.\n"
                f"Your task CLI directory (if applicable) is '{cli_hint}', and sudo password is '{client_password()}'.\n"
                "Preserve the co-agent's work, ensure saved files and live application state agree, satisfy any "
                "required collaboration handoffs, and do not tamper with running web server source code or forge logs."
                f"{collab_note}\n\nTask: {ctx.instruction}\n"
            )
        text = super().prompt(ctx)
        if self.opts.get("hybrid_v2"):
            cli_root = self.opts.get("cli_root") or "/tmp"
            text += (
                f"\n\nRestricted read-only Guest CLI is available via MCP tool 'run_guest_cli' "
                f"(allowed commands: pwd, ls, cat, stat, grep, head, tail) scoped to '{cli_root}'. "
                "Each call runs a fresh process without a shell."
            )
        if self.collaboration:
            text += (
                "\n\nCollaboration tools are available through MCP: send_message, read_messages, "
                "send_attachment, and read_attachment. Use them to exchange task evidence or ask for "
                "clarification. You may decide when communication is useful; there is no required "
                "message count or timing. The collaboration API exposes no evaluator or hidden state."
            )
        return text
'''


LIVE_PILOT_REPLACEMENT = r'''
def _run_model_actor(
    role: str,
    guest: Any,
    instruction: str,
    run_root: Path,
    model: str,
    base_url: str,
    api_key_env: str,
    mcp_python: str,
    collab_url: str | None,
    token_env: str | None,
    max_steps: int = 60,
    effort: str = "medium",
    timeout: float = 1200,
    local_qwen: bool = False,
    request_retries: int = 5,
    tool_cooldown_sec: float = 0.0,
    relay_client_token_env: str | None = None,
    hybrid_v2: bool = False,
    condition: str | None = None,
    episode_id: str | None = None,
    cli_root: str | None = None,
    action_lock_file: str | None = None,
    mcp_env_overrides: dict[str, str] | None = None,
    task_id: str | None = None,
    desktop_tool_timeout_sec: int = 300,
    full_cli: bool = False,
) -> dict[str, Any]:
    from oscombo.harness.base import AgentContext
    from oscombo.harness.external import CodexHarness
    guest.actor = role
    actor_root = run_root / "actor_runs" / role
    actor_root.mkdir(parents=True, exist_ok=True)
    options = {
        "base_url": base_url,
        "api_key_env": relay_client_token_env or api_key_env,
        "mcp_python": mcp_python,
        "timeout": timeout,
        "auth_mode": "none" if local_qwen else "auto",
        "request_retries": request_retries,
        "stream_retries": request_retries,
        "desktop_tool_cooldown_sec": tool_cooldown_sec,
        "hybrid_v2": bool(hybrid_v2),
        "condition": condition,
        "episode_id": episode_id,
        "cli_root": cli_root,
        "action_lock_file": action_lock_file,
        "mcp_env_overrides": dict(mcp_env_overrides or {}),
        "desktop_tool_timeout_sec": int(desktop_tool_timeout_sec),
        "full_cli": bool(full_cli) or os.environ.get("CODESK_FULL_CLI_ARM") == "1",
    }
    if relay_client_token_env:
        options["redact_env_keys"] = [api_key_env]
    if collab_url and token_env:
        options["collaboration"] = {"actor": role, "url": collab_url, "token_env": token_env}
    actor_spec = {"harness": "codex", "model": model, "effort": effort, "options": options}
    ctx = AgentContext(
        name=role,
        task_id=task_id or getattr(spec, "CASE_ID", "CODESK-TASK"),
        instruction=instruction,
        guest=guest,
        out=actor_root,
        max_steps=max_steps,
        spec=actor_spec,
        t0=time.time(),
    )
    harness = CodexHarness(actor_spec)
    harness.prepare(ctx)
    started = time.monotonic()
    result = harness.run(ctx)
    trace_path = actor_root / "trace.json"
    trace_path.write_text(json.dumps(result.trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "actor": role,
        "guest_key": getattr(guest, "guest_key", "guest"),
        "status": result.status,
        "steps": len(result.trace),
        "elapsed_s": round(time.monotonic() - started, 2),
        "model": model,
        "endpoint": base_url,
        "effort": effort,
        "trace_path": str(trace_path.relative_to(run_root)),
        "error": result.error,
        "harness_version": harness.harness_version,
        "permission_audit": result.extra.get("permission_audit"),
    }
    _append(run_root / "actors.jsonl", summary)
    return summary


def _start_codex_compat_relay(
    run_root: Path,
    upstream: str,
    api_key_env: str,
    client_token: str,
    client_token_env: str,
    *,
    output_token_budget: int | None = None,
    response_token_cap: int | None = None,
    reserve_on_missing_usage: bool = False,
    size_aware_upload_timeout: bool = False,
) -> tuple[subprocess.Popen, str]:
    import requests
    ready = run_root / "codex_relay_ready.json"
    log_path = run_root / "codex_relay.log"
    cmd = [
        sys.executable, "-u", "-m", "oscombo.responses_tool_image_relay",
        "--upstream", upstream,
        "--api-key-env", api_key_env,
        "--client-token-env", client_token_env,
        "--ready-file", str(ready),
        "--event-log", str(run_root / "codex_relay_events.jsonl"),
    ]
    if output_token_budget is not None:
        cmd += ["--output-token-budget", str(int(output_token_budget))]
    if response_token_cap is not None:
        cmd += ["--response-token-cap", str(int(response_token_cap))]
    if reserve_on_missing_usage:
        cmd.append("--reserve-on-missing-usage")
    if size_aware_upload_timeout:
        cmd.append("--size-aware-upload-timeout")
    relay_env = {
        name: os.environ[name]
        for name in (
            "PATH", "HOME", "PYTHONPATH", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "no_proxy", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
        )
        if name in os.environ
    }
    relay_env.update({
        api_key_env: os.environ[api_key_env],
        client_token_env: client_token,
        "PYTHONUNBUFFERED": "1",
    })
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            cmd,
            cwd=Path(__file__).resolve().parents[3],
            env=relay_env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Codex compatibility relay exited {process.returncode}; see {log_path}")
        if ready.exists():
            info = json.loads(ready.read_text(encoding="utf-8"))
            if info.get("pid") == process.pid:
                base = f"http://127.0.0.1:{info['port']}/v1"
                try:
                    response = requests.get(f"http://127.0.0.1:{info['port']}/health", timeout=2)
                    if response.ok and response.json().get("ready"):
                        return process, base
                except requests.RequestException:
                    pass
        time.sleep(0.2)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    raise TimeoutError(f"Codex compatibility relay not ready within 25s; see {log_path}")
'''


RECONSTRUCTED_WORKFLOWS_HELPER_SOURCE = r'''"""Reconstructed F-01 / C-03 Guest desktop setup and SHA-verified prompts from protocol docs."""
from __future__ import annotations

import base64
from pathlib import Path
import shlex
import time

from scripts import run_writer_calc_v1 as base

PROMPTS = {
    "F-01": {
        "actor_a": (
            'LibreOffice Writer is active and the complete existing paragraph is selected. '
            'Replace it by typing exactly "Approved by GUI actor", then save with Ctrl+S. '
            'Do not use Ctrl+A, menus, or Ctrl+V. Do not edit Calc.'
        ),
        "actor_b": (
            'LibreOffice Calc is active and cell B2 is already selected. '
            'Replace Draft by typing exactly "Approved", press Enter to commit, then save with Ctrl+S. '
            'Do not navigate to another cell or switch applications. Do not edit Writer.'
        ),
    },
    "C-03": {
        "actor_a": (
            "In LibreOffice Calc, the complete source range A1:B2 is selected. Copy it. "
            "After the coordination pause, Calc cell A4 will already be selected for you. "
            "Do not click or navigate; press Ctrl+V to paste, then save with Ctrl+S. "
            "Preserve the source, guard cells, and every other cell. Do not edit Writer."
        ),
        "actor_b": (
            'LibreOffice Writer is active and the first paragraph "NOTE-571" is selected. Copy it. '
            "The document already has a blank second paragraph immediately below it. "
            "Click inside that existing blank paragraph and paste exactly one copy there. "
            "Do NOT press Enter or create any paragraphs. Keep the first paragraph unchanged and save with Ctrl+S. "
            "Do not switch applications; the coordinator handles the next actor window. Do not edit Calc."
        ),
    },
}


def _guest_active_window_title(desktop) -> str:
    return base.guest_command(
        desktop,
        ["bash", "-lc", "wid=$(xdotool getactivewindow 2>/dev/null || true); xdotool getwindowname \"$wid\" 2>/dev/null || true"],
        timeout=20,
    ).strip()


def _setup_model_desktop(episode, desktop, out_dir: Path, workflow, apps: list[str]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    for file_path, content in workflow.files().items():
        encoded = base64.b64encode(content).decode("ascii")
        py_code = (
            f"from pathlib import Path; import base64; p=Path({file_path!r}); "
            f"p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(base64.b64decode({encoded!r}))"
        )
        episode.cli_action("workflow_seed", "python3 -c " + shlex.quote(py_code))
    readiness = {}
    for app_name in apps:
        lower = app_name.lower()
        doc_path = workflow.writer_path if lower == "writer" else workflow.calc_path
        flag = "--writer" if lower == "writer" else "--calc"
        launch = (
            f"export DISPLAY=:0; nohup soffice --nologo --norestore --nofirststartwizard {flag} "
            f"{shlex.quote(doc_path)} >/tmp/codesk-{lower}.log 2>&1 </dev/null & sleep 6"
        )
        episode.cli_action("workflow_launch_" + lower, "bash -lc " + shlex.quote(launch))
        readiness[lower] = base.wait_for_app_document(episode, desktop, lower, doc_path, out_dir / ("ready-" + lower), timeout=150)
        if lower == "calc":
            if workflow.template_id == "clipboard_calc_rectangle_v1":
                sel_cmd = (
                    "xdotool key --clearmodifiers ctrl+Home; sleep .2; "
                    "xdotool keydown Shift; xdotool key Right; xdotool key Down; xdotool keyup Shift; sleep .3"
                )
            else:
                sel_cmd = "xdotool key --clearmodifiers ctrl+Home; sleep .2; xdotool key Right; xdotool key Down; sleep .3"
            episode.cli_action("workflow_preselect_calc", "bash -lc " + shlex.quote(sel_cmd))
        else:
            if workflow.template_id == "clipboard_calc_rectangle_v1":
                sel_cmd = (
                    "xdotool key --clearmodifiers ctrl+Home; sleep .2; "
                    "xdotool keydown Shift; xdotool key End; xdotool keyup Shift; sleep .3"
                )
            else:
                sel_cmd = "xdotool key --clearmodifiers ctrl+a; sleep .3"
            episode.cli_action("workflow_preselect_writer", "bash -lc " + shlex.quote(sel_cmd))
    time.sleep(1.0)
    return {"apps": apps, "readiness": readiness}
'''


RECONSTRUCTED_CALC_HELPER_SOURCE = r'''"""Reconstructed Calc selection / undo-redo helper module matching 0.2.2 evidence manifests."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import time

from scripts import probe_selection_active_object_v1 as task
from scripts import run_writer_calc_v1 as base

TASK_VERSION = "0.2.2-explicit-cell-nav-undo-sequence"


def _setup(binding: str, log, out: Path):
    ep, desk = base.make_desktop(binding, log, out / binding, require_a11y_tree=False)
    try:
        encoded = base64.b64encode(task.render_calc_fods(task.INITIAL)).decode("ascii")
        create = (
            f"from pathlib import Path; import base64; target_path=Path({task.GUEST_PATH!r}); "
            f"target_path.parent.mkdir(parents=True,exist_ok=True); target_path.write_bytes(base64.b64decode({encoded!r}))"
        )
        task.cmd(desk, ["python3", "-c", create], timeout=20)
        task.cmd(
            desk,
            [
                "bash", "-lc",
                f"export DISPLAY=:0; nohup soffice --nologo --norestore --nofirststartwizard "
                f"--accept='socket,host=localhost,port=2002;urp;StarOffice.ComponentContext' "
                f"--calc {task.GUEST_PATH} >/tmp/codesk-calc-soffice.log 2>&1 </dev/null & sleep 7",
            ],
            timeout=20,
        )
        ready = base.wait_for_app_document(ep, desk, "calc", task.GUEST_PATH, out / binding / "readiness", timeout=150)
        return ep, desk, ready
    except Exception:
        ep.close()
        raise


def _uno_cell(desk, address: str) -> str:
    py = (
        "import json,uno; c=uno.getComponentContext(); "
        "r=c.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',c); "
        "x=r.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); "
        "d=x.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',x); "
        f"s=d.getCurrentComponent().getSheets().getByIndex(0); q=s.getCellRangeByName({address!r}); "
        "print(json.dumps({'value':q.getString()}))"
    )
    raw = task.cmd(desk, ["python3", "-c", py], timeout=15).strip().splitlines()[-1]
    return json.loads(raw)["value"]


def _disk_grid(desk) -> list[list[str]]:
    raw = task.cmd(desk, ["cat", task.GUEST_PATH], timeout=20)
    return base.GuestLibreOfficeBindingEvaluator._parse_calc(raw)


def _cell(grid: list[list[str]], address: str) -> str:
    col = ord(address[0].upper()) - ord("A")
    row = int(address[1:]) - 1
    if 0 <= row < len(grid) and 0 <= col < len(grid[row]):
        return grid[row][col]
    return ""


def _evaluate(desk, roles: list[str], mechanism: str) -> dict:
    grid = _disk_grid(desk)
    expected = [list(row) for row in task.INITIAL]
    if "actor_a" in roles:
        expected[1][1] = "A-7319" if mechanism == "selection" else "B2 seed"
    if "actor_b" in roles:
        expected[2][2] = "B-2042"
    return {
        "actual_grid": grid,
        "expected_grid": expected,
        "success": grid == expected,
    }
'''


RECONSTRUCTED_WRITER_OVERWRITE_HELPER_SOURCE = r'''"""Reconstructed Writer Insert/Overwrite helper matching EDIT-v040 and FIND-v020 manifests."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import shlex
import time

from scripts import run_writer_calc_v1 as base
from swcub.environment import ActorContext

DOC = (
    "Release status: STATUS | HOLD-FOR-REVIEW",
    "Reviewer code: ____; change only this fixed-width code.",
    "Guard phrase: DO-NOT-ALTER-THIS-LINE",
)
A_TARGET = "Release status: STATUS | READY HOLD-FOR-REVIEW"
A_OVERWRITE_SIGNATURE = "Release status: STATUS | READY OR-REVIEW"
B_TARGET = "Reviewer code: AB12; change only this fixed-width code."
GUARD = "Guard phrase: DO-NOT-ALTER-THIS-LINE"


def window_identity(desktop) -> dict:
    command = (
        "wid=$(xdotool getactivewindow 2>/dev/null || true); "
        "title=$(xdotool getwindowname \"$wid\" 2>/dev/null || true); "
        "cls=$(xprop -id \"$wid\" WM_CLASS 2>/dev/null | tail -1 || true); "
        "printf \"%s\\t%s\\t%s\\n\" \"$wid\" \"$title\" \"$cls\""
    )
    parts = base.guest_command(desktop, ["bash", "-lc", command]).strip().split("\t")
    while len(parts) < 3:
        parts.append("")
    return {"xid": parts[0], "title": parts[1], "wm_class": parts[2]}


def writer_text(desktop) -> str:
    raw = base.guest_command(desktop, ["cat", base.WRITER_PATH], timeout=30)
    return base.GuestLibreOfficeBindingEvaluator._parse_writer(raw)


def capture(ep_or_ctx, out: Path, label: str) -> dict:
    if hasattr(ep_or_ctx, "refresh_observation"):
        obs = ep_or_ctx.refresh_observation(source="writer_" + label)
    else:
        obs = ep_or_ctx.observe()
    shot = obs.get("screenshot") if isinstance(obs, dict) else None
    folder = out / "observations"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{label}.png"
    if isinstance(shot, bytes) and shot:
        target.write_bytes(shot)
    return {
        "screenshot_available": isinstance(shot, bytes) and bool(shot),
        "screenshot_sha256": hashlib.sha256(shot).hexdigest() if isinstance(shot, bytes) else None,
        "observation_file": str(target.relative_to(out)) if isinstance(shot, bytes) and shot else None,
    }


def wait_writer_ready(episode, desktop, out: Path, timeout: float = 240.0) -> dict:
    return base.wait_for_app_document(episode, desktop, "writer", base.WRITER_PATH, out / "readiness", timeout=int(timeout))


def setup_writer(episode, desktop, binding: str, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    data = base.render_writer_fodt(list(DOC))
    encoded = base64.b64encode(data).decode("ascii")
    code = (
        f"from pathlib import Path; import base64; p=Path({base.WRITER_PATH!r}); "
        f"p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(base64.b64decode({encoded!r}))"
    )
    episode.cli_action("task_setup", "python3 -c " + shlex.quote(code))
    launch = (
        f"export DISPLAY=:0; nohup soffice --nologo --norestore --nofirststartwizard --writer "
        f"{shlex.quote(base.WRITER_PATH)} >/tmp/codesk-edit-overwrite.log 2>&1 </dev/null & "
        "echo $! >/tmp/codesk-edit-overwrite.pid; sleep 7"
    )
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
    ready = wait_writer_ready(episode, desktop, out, timeout=240.0)
    episode.refresh_observation(source="writer_overwrite_ready")
    setup_ctx = ActorContext("task_setup", episode, "gui")
    setup_ctx.execute_gui_action("pyautogui.hotkey('ctrl', 'home')")
    setup_ctx.execute_gui_action("pyautogui.press('right', presses=25)")
    seed_obs = capture(episode, out, f"{binding}-cursor-seeded")
    return {
        "binding": binding,
        "ready": ready,
        "initial_text": writer_text(desktop),
        "window": window_identity(desktop),
        "cursor_seed_actions": ["ctrl+home", "right x25"],
        "cursor_seed_observation": seed_obs,
    }
'''


CWD1_CODEX_RUNNER_SOURCE = r'''#!/usr/bin/env python3
"""CWD-1 v0.2.4 migrated to unified containerized non-YOLO CodexHarness + Responses."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid

from oscombo.collab.data_to_deck.live_pilot import _run_model_actor, _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.guest import Guest
from oscombo.harness.hybrid_v2 import MCP_PYTHON
from scripts import probe_cwd_bundle_v2_scripted as controls
from scripts import run_sol_cwd_bundle_v2 as cwd_spec
from scripts import run_writer_calc_v1 as base
from swcub.core import EventLog
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state, evaluate_tar_exact_files

MODEL = "gpt-6.1-sol"
BUDGET = 20
TOKEN_BUDGET = 12000
ARMS = ("ma_id", "ma_sd", "ma_sd_lock")


def _json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_arm(parent: Path, condition: str, baseline: dict | None = None) -> dict:
    shared = condition != "ma_id"
    prompts = cwd_spec.prompts()
    prompt_sha = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in prompts.items()}
    f_sha = cwd_spec.fixture_sha()
    if shared:
        if not baseline or not baseline.get("valid_model_run") or not baseline.get("task_success"):
            raise RuntimeError("CWD-1 shared arms require passing MA-ID baseline")
    run_id = f"cwd-v024-codex-sol61-{condition}-{uuid.uuid4().hex[:8]}"
    out = parent / run_id
    out.mkdir(parents=True, exist_ok=False)
    for sub in ("actor_runs", "protocol_gate", "locks", "collaboration", "overlays", "actor_a", "actor_b", "shared"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    ledger = out / "resource-events.jsonl"
    os.environ.update({
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(ledger),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays"),
    })
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    ensure_resource_identity(ledger)
    log = EventLog()
    endpoint = (os.environ.get("CODESK_SOL_ENDPOINT") or os.environ.get("SWCUB_SOL_BASE_URL")).rstrip("/")
    bindings = {"A": "shared", "B": "shared"} if shared else {"A": "actor_a", "B": "actor_b"}
    guest_keys = ["shared"] if shared else ["actor_a", "actor_b"]
    signal_dir = out / "protocol_gate" / "actor_a"
    signal_dir.mkdir(parents=True, exist_ok=True)
    gate_cfg = out / "protocol_gate" / "gate-config.json"
    gate_id = run_id + "-A-held-relative-write"
    _json(gate_cfg, {
        "gate_id": gate_id,
        "actor_id": "A",
        "tool": "type_text",
        "argument": "text",
        "contains": "release-note.txt",
        "signal_dir": str(signal_dir),
        "timeout_seconds": 3500,
    })
    envs, desktops, setups, statuses, relays = {}, {}, {}, {}, []
    server = None
    started = time.monotonic()
    report = {
        "run_id": run_id,
        "case_id": cwd_spec.CASE_ID,
        "task_version": cwd_spec.TASK_VERSION,
        "condition": condition,
        "actor_implementation": "ContainerizedCodexHarness",
        "model": {"model": MODEL, "endpoint": endpoint, "effort": "medium", "steps_per_actor": BUDGET},
        "fixture_sha256": f_sha,
        "prompt_sha256": prompt_sha,
        "valid_model_run": False,
        "protocol_valid": False,
        "task_success": False,
    }
    try:
        for gkey in guest_keys:
            ep, desk = base.make_desktop(gkey, log, out / gkey, require_a11y_tree=False)
            envs[gkey] = ep
            desktops[gkey] = desk
            setups[gkey] = cwd_spec.setup_terminal(ep, desk, gkey)
        report["setup"] = setups
        store = ProtocolStore(out / "collaboration", run_id)
        tokens = {role: secrets.token_urlsafe(32) for role in ("A", "B")}
        server = make_server(store, tokens)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        token_envs = {}
        for role in ("A", "B"):
            env_name = f"CODESK_CWD_COLLAB_{role}_{uuid.uuid4().hex[:8].upper()}"
            os.environ[env_name] = tokens[role]
            token_envs[role] = env_name

        def run_role(role: str):
            actor_dir = out / "actor_runs" / role
            actor_dir.mkdir(parents=True, exist_ok=True)
            relay_env = f"CODESK_CWD_RELAY_{role}_{uuid.uuid4().hex[:8].upper()}"
            os.environ[relay_env] = secrets.token_urlsafe(32)
            relay_proc, relay_url = _start_codex_compat_relay(
                actor_dir, endpoint, "SWCUB_SOL_API_KEY", os.environ[relay_env], relay_env,
                output_token_budget=TOKEN_BUDGET, response_token_cap=2048, reserve_on_missing_usage=True,
            )
            relays.append(relay_proc)
            guest = Guest(desktops[bindings[role]])
            guest.guest_key = bindings[role]
            guest.actor = role
            lock_path = str(out / "locks/gui-actions.lock") if condition == "ma_sd_lock" else None
            override = {"OSCOMBO_MCP_GATE_CONFIG": str(gate_cfg)} if role == "A" else None
            return _run_model_actor(
                role, guest, prompts["actor_" + role.lower()], out, MODEL, relay_url,
                "SWCUB_SOL_API_KEY", MCP_PYTHON, f"http://127.0.0.1:{server.server_port}",
                token_envs[role], max_steps=BUDGET, effort="medium", timeout=2400,
                request_retries=5, relay_client_token_env=relay_env, hybrid_v2=False,
                condition=condition, episode_id=f"{run_id}-{role}",
                action_lock_file=lock_path, mcp_env_overrides=override,
                task_id=f"{cwd_spec.CASE_ID}@{cwd_spec.TASK_VERSION}", desktop_tool_timeout_sec=3600,
            )

        pending_path = signal_dir / "pending.json"
        release_path = signal_dir / "release.json"
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut_a = pool.submit(run_role, "A")
            deadline = time.monotonic() + 1800
            pending = None
            while time.monotonic() < deadline and pending is None and not fut_a.done():
                if pending_path.is_file():
                    try:
                        pending = json.loads(pending_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                time.sleep(0.4)
            statuses["B"] = run_role("B")
            _json(release_path, {"gate_id": gate_id, "reason": "B finished; release A relative write"})
            statuses["A"] = fut_a.result(timeout=1800)

        desk_a = desktops[bindings["A"]]
        desk_b = desktops[bindings["B"]]
        a_expected = cwd_spec.read_exact(desk_a, f"{cwd_spec.ROOT_GUEST}/work/a/deliverables/release-note.txt")
        a_wrong = cwd_spec.read_exact(desk_a, f"{cwd_spec.ROOT_GUEST}/work/b/deliverables/release-note.txt")
        b_check = cwd_spec.read_exact(desk_b, f"{cwd_spec.ROOT_GUEST}/work/b/deliverables/check.txt")
        bundle_bytes = cwd_spec.read_exact_bytes(desk_b, f"{cwd_spec.ROOT_GUEST}/work/b/qa-bundle.tar.gz")
        bundle_local = out / "qa-bundle.tar.gz"
        bundle_eval = {"pass": False}
        if bundle_bytes is not None:
            bundle_local.write_bytes(bundle_bytes)
            bundle_eval = evaluate_tar_exact_files(str(bundle_local), {"deliverables/check.txt": cwd_spec.B_VALUE.encode("utf-8")})
        a_ok = (a_expected == cwd_spec.A_VALUE) and (a_wrong is None)
        b_ok = (b_check == cwd_spec.B_VALUE) and bool(bundle_eval.get("pass"))
        task_success = bool(a_ok and b_ok)
        actors_ok = all(statuses.get(r, {}).get("status") in {"done", "max_steps", "fail"} for r in ("A", "B"))
        report.update({
            "actor_results": statuses,
            "pending_gate": pending,
            "protocol_valid": bool(pending is not None),
            "valid_model_run": bool(actors_ok and pending is not None),
            "task_success": task_success,
            "model_task_outcome": "PASS" if task_success else "FAIL",
            "evaluation": {
                "a_expected_exact": a_expected == cwd_spec.A_VALUE,
                "a_wrong_path_present": a_wrong is not None,
                "a_wrong_value": a_wrong,
                "b_check_exact": b_check == cwd_spec.B_VALUE,
                "b_bundle": bundle_eval,
                "task_success": task_success,
            },
            "status": "completed",
        })
    except Exception as exc:
        report.update({"status": "invalid_setup_or_runtime", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        for gkey, ep in envs.items():
            try:
                ep.close()
            except Exception:
                pass
        for proc in relays:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
        report["wall_seconds"] = round(time.monotonic() - started, 2)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["reset_success"] = bool((report.get("resource_lifecycle") or {}).get("all_containers_have_destroy_record"))
        _json(out / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    args = parser.parse_args()
    parent = args.artifact_parent.expanduser().resolve() / f"cwd1-sol61-{time.strftime('%Y%m%d-%H%M%S')}-triplet"
    parent.mkdir(parents=True, exist_ok=True)
    rows = []
    baseline = None
    for arm in ARMS:
        row = run_arm(parent, arm, baseline)
        rows.append(row)
        if arm == "ma_id":
            baseline = row
            if not row.get("valid_model_run") or not row.get("task_success"):
                break
        elif not row.get("valid_model_run"):
            break
    summary = {
        "case": "CWD-1",
        "task_version": cwd_spec.TASK_VERSION,
        "model": MODEL,
        "arms": [
            {
                "run_id": r["run_id"],
                "condition": r["condition"],
                "valid": r.get("valid_model_run"),
                "protocol_valid": r.get("protocol_valid"),
                "success": r.get("task_success"),
                "outcome": r.get("model_task_outcome"),
                "wall_seconds": r.get("wall_seconds"),
            }
            for r in rows
        ],
    }
    _json(parent / "triplet_result.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
'''

"""Run CoDesk Codex agents strictly inside isolated non-YOLO Docker containers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import socketserver
import subprocess
import threading
import time

from experiments.responses_relay import prepare_image_history


DEFAULT_CONTAINER_IMAGE = os.environ.get("CODESK_CODEX_CONTAINER_IMAGE", "paragui/professional-rootless:20261103")
DEFAULT_CODEX_BINARY = Path("/data/users/yuke/paraGUI/weavebench/official-pairs-20261103-r1/runtime/codex/codex")
FORBIDDEN_ARGS = {"--yolo", "--dangerously-bypass-approvals-and-sandbox"}
PERMISSION_MODES = ("container-read-only-mcp", "container-unrestricted")


def codex_requirements_mount() -> list[str]:
    requirements = Path(__file__).resolve().parents[1] / "configs/codex.requirements.toml"
    if not requirements.is_file():
        raise RuntimeError("Missing mandatory Codex sandbox requirements")
    return [
        "--security-opt", "seccomp=unconfined",
        "--security-opt", "apparmor=unconfined",
        "--mount", f"type=bind,src={requirements},dst=/etc/codex/requirements.toml,readonly",
    ]


def container_permission_policy(mode: str = "container-read-only-mcp") -> dict:
    if mode not in PERMISSION_MODES:
        raise ValueError(f"Unknown container permission mode: {mode!r}")
    unrestricted = mode == "container-unrestricted"
    return {
        "mode": mode,
        "scope": "docker-container-only",
        "vm_host_codex_launched": False,
        "sandbox_mode": "workspace-write" if unrestricted else "read-only",
        "approval_policy": "never" if unrestricted else "on-request",
        "shell_tool": unrestricted,
        "unified_exec": False,
        "yolo_flag_used": False,
        "yolo_enabled": False,
        "yolo_equivalent": False,
    }


def non_yolo_policy() -> dict:
    return container_permission_policy("container-read-only-mcp")


def validate_container_config_text(config_toml: str, mode: str = "container-read-only-mcp") -> dict:
    import tomllib
    policy = container_permission_policy(mode)
    parsed = tomllib.loads(config_toml)
    sandbox = parsed.get("sandbox_mode")
    approval = parsed.get("approval_policy")
    features = parsed.get("features") or {}
    if sandbox != policy["sandbox_mode"]:
        raise ValueError(f"Codex sandbox_mode={sandbox!r} does not match {policy['sandbox_mode']!r}")
    if approval != policy["approval_policy"]:
        raise ValueError(f"Codex approval_policy={approval!r} does not match {policy['approval_policy']!r}")
    if features.get("shell_tool") is not policy["shell_tool"]:
        raise ValueError(f"Codex shell_tool={features.get('shell_tool')!r} does not match {policy['shell_tool']!r}")
    if features.get("unified_exec") is not policy["unified_exec"]:
        raise ValueError(f"Codex unified_exec={features.get('unified_exec')!r} does not match {policy['unified_exec']!r}")
    lowered = config_toml.lower()
    if any(value in lowered for value in (*FORBIDDEN_ARGS, "danger-full-access", "external-sandbox")):
        raise ValueError("Forbidden YOLO / sandbox bypass in Codex config")
    return parsed


def validate_non_yolo_config_text(config_toml: str) -> dict:
    return validate_container_config_text(config_toml, mode="container-read-only-mcp")


CONTAINER_ENTRY_SOURCE = r'''"""Entry guard running inside the airgapped Docker container."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import tomllib


FORBIDDEN_FLAGS = {"--yolo", "--dangerously-bypass-approvals-and-sandbox"}
MODES = {
    "container-read-only-mcp": {
        "sandbox_mode": "read-only",
        "approval_policy": "on-request",
        "shell_tool": False,
        "unified_exec": False,
        "yolo_equivalent": False,
    },
    "container-unrestricted": {
        "sandbox_mode": "workspace-write",
        "approval_policy": "never",
        "shell_tool": True,
        "unified_exec": False,
        "yolo_equivalent": False,
    },
}


def require_isolated_container() -> None:
    if not Path("/.dockerenv").is_file():
        raise RuntimeError("Refusing to launch experimental Codex outside Docker container")
    if os.getuid() == 0:
        raise RuntimeError("Refusing to launch experimental Codex as root")
    if os.environ.get("HOME") != "/session" or os.environ.get("CODEX_HOME") != "/session/codex-home":
        raise RuntimeError("Refusing to use host or non-isolated CODEX_HOME")
    if Path.cwd() != Path("/session"):
        raise RuntimeError("Expected /session working directory inside container")


def verify_config(config_path: Path, mode: str) -> dict:
    if mode not in MODES:
        raise RuntimeError(f"Unknown container permission mode: {mode!r}")
    expected = MODES[mode]
    raw = config_path.read_text(encoding="utf-8")
    parsed = tomllib.loads(raw)
    if parsed.get("sandbox_mode") != expected["sandbox_mode"]:
        raise RuntimeError(f"Forbidden sandbox_mode: {parsed.get('sandbox_mode')!r}")
    if parsed.get("approval_policy") != expected["approval_policy"]:
        raise RuntimeError(f"Forbidden approval_policy: {parsed.get('approval_policy')!r}")
    features = parsed.get("features") or {}
    if features.get("shell_tool") is not expected["shell_tool"] or features.get("unified_exec") is not expected["unified_exec"]:
        raise RuntimeError("Shell/unified_exec mismatch in CoDesk Codex container")
    if any(value in raw.lower() for value in (*FORBIDDEN_FLAGS, "danger-full-access", "external-sandbox")):
        raise RuntimeError("Forbidden YOLO / sandbox bypass detected")
    return parsed


def pipe_bytes(source: socket.socket, sink: socket.socket) -> None:
    try:
        while True:
            chunk = source.recv(65536)
            if not chunk:
                break
            sink.sendall(chunk)
    except OSError:
        pass
    finally:
        try:
            sink.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def start_relay_forwarder(unix_sock_path: str) -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(32)
    local_port = listener.getsockname()[1]

    def accept_loop() -> None:
        while True:
            try:
                client, _addr = listener.accept()
            except OSError:
                break
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                upstream.connect(unix_sock_path)
            except OSError:
                client.close()
                upstream.close()
                continue
            t1 = threading.Thread(target=pipe_bytes, args=(client, upstream), daemon=True)
            t2 = threading.Thread(target=pipe_bytes, args=(upstream, client), daemon=True)
            t1.start()
            t2.start()

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    return listener, local_port


def main() -> int:
    require_isolated_container()
    os.umask(0o002)
    mode = os.environ.get("CODESK_CONTAINER_PERMISSION_MODE", "container-read-only-mcp")
    expected = MODES[mode]
    config_path = Path("/session/codex-home/config.toml")
    template_text = Path("/session/codex-home/config.template.toml").read_text(encoding="utf-8")
    listener, port = start_relay_forwarder("/ipc/relay.sock")
    rendered = template_text.replace("__CONTAINER_RELAY_PORT__", str(port))
    config_path.write_text(rendered, encoding="utf-8")
    config_path.chmod(0o640)
    verify_config(config_path, mode)
    resume_file = Path("/session/resume_prompt.txt")
    if resume_file.is_file():
        resume_text = resume_file.read_text(encoding="utf-8")
        command = [
            "/codex/codex", "exec", "resume", "--last", "--all", "--json",
            "--skip-git-repo-check", resume_text,
        ]
    else:
        prompt_text = Path("/session/prompt.txt").read_text(encoding="utf-8")
        command = [
            "/codex/codex", "exec", "--json", "--color", "never",
            "--skip-git-repo-check", "-C", "/session/work", prompt_text,
        ]
    if any(arg in FORBIDDEN_FLAGS for arg in command):
        raise RuntimeError("Forbidden YOLO CLI flag")
    audit = {
        "docker_marker": True,
        "permission_mode": mode,
        "scope": "docker-container-only",
        "vm_host_codex_launched": False,
        "uid": os.getuid(),
        "gid": os.getgid(),
        "home": os.environ["HOME"],
        "codex_home": os.environ["CODEX_HOME"],
        "cwd": str(Path.cwd()),
        "sandbox_mode": expected["sandbox_mode"],
        "approval_policy": expected["approval_policy"],
        "shell_tool": expected["shell_tool"],
        "unified_exec": expected["unified_exec"],
        "yolo_flag_used": False,
        "yolo_enabled": expected["yolo_equivalent"],
        "yolo_equivalent": expected["yolo_equivalent"],
        "local_relay_port": port,
    }
    Path("/session/permission-audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    try:
        completed = subprocess.run(command, stdin=subprocess.DEVNULL)
        return int(completed.returncode)
    finally:
        for root_dir, dir_names, file_names in os.walk("/session"):
            for dname in dir_names:
                try:
                    os.chmod(os.path.join(root_dir, dname), 0o770)
                except OSError:
                    pass
            for fname in file_names:
                try:
                    os.chmod(os.path.join(root_dir, fname), 0o660)
                except OSError:
                    pass
        listener.close()


if __name__ == "__main__":
    raise SystemExit(main())
'''


GUEST_BASH_BRIDGE_CLI_SOURCE = r'''"""CLI helper inside /bridge allowing container shell_tool to run commands on the shared Guest VM."""
import json
import socket
import sys


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 /bridge/guest_bash.py '<bash command>' [cwd]\n")
        return 2
    args = {"command": sys.argv[1]}
    if len(sys.argv) >= 3:
        args["cwd"] = sys.argv[2]
    request = {"op": "call", "server": "guest_bash", "name": "guest_bash", "arguments": args}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(120.0)
        sock.connect("/ipc/mcp.sock")
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
        chunks = []
        while True:
            block = sock.recv(65536)
            if not block:
                break
            chunks.append(block)
            if b"\n" in block:
                break
    reply = json.loads(b"".join(chunks).split(b"\n", 1)[0].decode("utf-8"))
    if "rpc_error" in reply:
        sys.stderr.write(reply["rpc_error"] + "\n")
        return 1
    for item in reply.get("content") or []:
        if item.get("type") == "text":
            sys.stdout.write(item.get("text", "") + "\n")
    return 1 if reply.get("isError") else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


MCP_PROXY_SOURCE = r'''"""Stdlib MCP JSON-RPC stdio server forwarding over Unix socket to host bridge."""
import json
import socket
import sys


def call_host(payload: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3660.0)
        client.connect("/ipc/mcp.sock")
        client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        chunks = []
        while True:
            block = client.recv(65536)
            if not block:
                break
            chunks.append(block)
            if b"\n" in block:
                break
    raw = b"".join(chunks).split(b"\n", 1)[0]
    return json.loads(raw.decode("utf-8"))


def handle_request(server_name: str, message: dict) -> dict:
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": f"codesk-{server_name}", "version": "1.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        response = call_host({"op": "list", "server": server_name})
        if "error" in response:
            raise RuntimeError(response["error"])
        return {"tools": response["tools"]}
    if method == "tools/call":
        response = call_host({
            "op": "call",
            "server": server_name,
            "name": params.get("name"),
            "arguments": params.get("arguments") or {},
        })
        if "rpc_error" in response:
            raise RuntimeError(response["rpc_error"])
        return {"content": response["content"], "isError": bool(response.get("isError", False))}
    raise ValueError(f"Unsupported MCP method: {method!r}")


def main() -> int:
    server_name = sys.argv[1]
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        message = json.loads(stripped)
        if "id" not in message:
            continue
        reply = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            reply["result"] = handle_request(server_name, message)
        except Exception as error:
            reply["error"] = {"code": -32603, "message": str(error)}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


class _ThreadedUnixStreamServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class HostActorBridge:
    """Host-side Unix-domain-socket forwarder for one containerized Codex actor."""

    def __init__(self, ipc_dir: Path | None, relay_host_port: int, mcp_handlers: dict,
                 image_history_keep: int = 12, max_request_images: int = 45):
        import secrets
        import shutil
        self._shutil = shutil
        self._owned_short_dir = False
        if ipc_dir is None or len(str(ipc_dir)) > 60:
            self.ipc_dir = Path(f"/tmp/c19-{secrets.token_hex(8)}")
            self._owned_short_dir = True
        else:
            self.ipc_dir = ipc_dir
        self.ipc_dir.mkdir(parents=True, exist_ok=True, mode=0o770)
        os.chmod(self.ipc_dir, 0o770)
        self.relay_sock = self.ipc_dir / "relay.sock"
        self.mcp_sock = self.ipc_dir / "mcp.sock"
        for sock_path in (self.relay_sock, self.mcp_sock):
            if sock_path.exists():
                sock_path.unlink()
        self.relay_host_port = int(relay_host_port)
        self.mcp_handlers = mcp_handlers
        self.image_history_keep = image_history_keep
        self.max_request_images = max_request_images
        self._relay_server = None
        self._mcp_server = None
        self._threads = []

    def start(self) -> None:
        outer = self

        class RelayHandler(socketserver.BaseRequestHandler):
            def handle(self):
                upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    upstream.connect(("127.0.0.1", outer.relay_host_port))
                    outer._forward_http_with_image_window(self.request, upstream)
                except OSError:
                    pass
                finally:
                    try:
                        upstream.close()
                    except OSError:
                        pass

        class McpHandler(socketserver.StreamRequestHandler):
            def handle(self):
                raw = self.rfile.readline()
                if not raw:
                    return
                try:
                    request = json.loads(raw.decode("utf-8"))
                    server_name = request.get("server")
                    handler = outer.mcp_handlers.get(server_name)
                    if handler is None:
                        reply = {"rpc_error": f"Unknown MCP server {server_name!r}"}
                    elif request.get("op") == "list":
                        reply = {"tools": handler["list"]()}
                    elif request.get("op") == "call":
                        reply = handler["call"](request.get("name"), request.get("arguments") or {})
                    else:
                        reply = {"rpc_error": f"Unknown op {request.get('op')!r}"}
                except Exception as error:
                    reply = {"rpc_error": f"{type(error).__name__}: {error}"}
                self.wfile.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()

        self._relay_server = _ThreadedUnixStreamServer(str(self.relay_sock), RelayHandler)
        self._mcp_server = _ThreadedUnixStreamServer(str(self.mcp_sock), McpHandler)
        os.chmod(self.relay_sock, 0o660)
        os.chmod(self.mcp_sock, 0o660)
        for srv in (self._relay_server, self._mcp_server):
            thread = threading.Thread(target=srv.serve_forever, daemon=True)
            thread.start()
            self._threads.append(thread)

    def _forward_http_with_image_window(self, client_sock: socket.socket, upstream_sock: socket.socket) -> None:
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = client_sock.recv(65536)
            if not chunk:
                return
            buffer += chunk
        header_bytes, rest = buffer.split(b"\r\n\r\n", 1)
        header_lines = header_bytes.decode("latin-1").split("\r\n")
        request_line = header_lines[0]
        content_length = 0
        rebuilt_headers = [request_line]
        for line in header_lines[1:]:
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
            else:
                rebuilt_headers.append(line)
        body = rest
        while len(body) < content_length:
            chunk = client_sock.recv(min(65536, content_length - len(body)))
            if not chunk:
                break
            body += chunk
        if request_line.startswith("POST ") and content_length > 0:
            try:
                payload = json.loads(body.decode("utf-8"))
                if isinstance(payload, dict) and isinstance(payload.get("input"), list) and not payload.get("previous_response_id"):
                    trimmed, _audit = prepare_image_history(
                        payload, keep=self.image_history_keep, max_images=self.max_request_images
                    )
                    if trimmed is not payload:
                        body = json.dumps(trimmed, ensure_ascii=False).encode("utf-8")
            except Exception:
                pass
        rebuilt_headers.append(f"Content-Length: {len(body)}")
        upstream_sock.sendall(("\r\n".join(rebuilt_headers) + "\r\n\r\n").encode("latin-1") + body)
        try:
            upstream_sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        while True:
            resp_chunk = upstream_sock.recv(65536)
            if not resp_chunk:
                break
            client_sock.sendall(resp_chunk)
        try:
            client_sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass

    def close(self) -> None:
        for srv in (self._relay_server, self._mcp_server):
            if srv is not None:
                try:
                    srv.shutdown()
                    srv.server_close()
                except OSError:
                    pass
        for sock_path in (self.relay_sock, self.mcp_sock):
            try:
                sock_path.unlink(missing_ok=True)
            except OSError:
                pass
        if self._owned_short_dir and self.ipc_dir.exists():
            try:
                self._shutil.rmtree(self.ipc_dir, ignore_errors=True)
            except OSError:
                pass


def verify_container_permission_audit(
    session_dir: Path,
    expected_model: str | None = None,
    permission_mode: str = "container-read-only-mcp",
) -> dict:
    policy = container_permission_policy(permission_mode)
    audit_path = session_dir / "permission-audit.json"
    if not audit_path.is_file():
        raise RuntimeError("Missing container permission-audit.json")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    expected = {
        "docker_marker": True,
        "home": "/session",
        "codex_home": "/session/codex-home",
        "cwd": "/session",
        "sandbox_mode": policy["sandbox_mode"],
        "approval_policy": policy["approval_policy"],
        "shell_tool": policy["shell_tool"],
        "unified_exec": policy["unified_exec"],
        "yolo_flag_used": False,
        "yolo_enabled": policy["yolo_enabled"],
        "yolo_equivalent": policy["yolo_equivalent"],
    }
    for key, value in expected.items():
        if audit.get(key) != value:
            raise RuntimeError(f"Container permission audit mismatch on {key}: {audit.get(key)!r} != {value!r}")
    if int(audit.get("uid", 0)) <= 0:
        raise RuntimeError("Container ran as root UID")
    turn_contexts = []
    sessions_root = session_dir / "codex-home" / "sessions"
    if sessions_root.is_dir():
        for session_file in sorted(sessions_root.rglob("*.jsonl")):
            for line in session_file.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("type") != "turn_context":
                    continue
                payload = row.get("payload") or {}
                sandbox_type = (payload.get("sandbox_policy") or {}).get("type")
                approval = payload.get("approval_policy")
                if (payload.get("permission_profile") or {}).get("type") == "disabled":
                    raise RuntimeError("Forbidden disabled permission profile in Codex turn_context")
                if sandbox_type != policy["sandbox_mode"] or approval != policy["approval_policy"]:
                    raise RuntimeError("Codex turn_context permissions do not match the container sandbox policy")
                if expected_model and payload.get("model") and payload.get("model") != expected_model:
                    raise RuntimeError("Unexpected model in Codex turn_context")
                turn_contexts.append({
                    "approval_policy": approval,
                    "sandbox_type": sandbox_type,
                    "cwd": payload.get("cwd"),
                })
    if not turn_contexts:
        raise RuntimeError("No Codex turn_context available to verify effective sandbox permissions")
    return {"entry_audit": audit, "turn_contexts": turn_contexts}

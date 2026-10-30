from __future__ import annotations

import ast
import base64
import builtins
import hashlib
import json
import os
import socketserver
import struct
import symtable
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra.run_ticket_to_resolution_lite_native import _guest_devtools_page_snapshot


class FakeGuest:
    def execute(self, command, timeout=20):
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=timeout, check=False)
        return {"status": "success", "returncode": result.returncode,
                "output": result.stdout, "error": result.stderr}


class FakeDevToolsHandler(socketserver.StreamRequestHandler):
    def handle(self):
        first = self.rfile.readline().decode("ascii", "replace").strip()
        headers = {}
        while True:
            line = self.rfile.readline()
            if not line or line == b"\r\n":
                break
            key, _, value = line.decode("ascii", "replace").partition(":")
            headers[key.lower()] = value.strip()
        if first.startswith("GET /json/list "):
            port = self.server.server_address[1]
            body = json.dumps([{
                "type": "page", "title": "", "url": "http://10.0.2.100:8765/login?actor=A",
                "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/page/test",
            }]).encode()
            self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n")
            self.wfile.write(f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode())
            self.wfile.write(body)
            return
        key = headers["sec-websocket-key"]
        accept = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        self.wfile.write(b"HTTP/1.1 101 WebSocket Protocol Handshake\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n")
        self.wfile.write(b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
        for _ in range(3):
            first_two = self.rfile.read(2)
            length = first_two[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.rfile.read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.rfile.read(8))[0]
            mask = self.rfile.read(4)
            payload = self.rfile.read(length)
            command = json.loads(bytes(value ^ mask[index % 4] for index, value in enumerate(payload)))
            if command["id"] == 1:
                assert command["method"] == "Runtime.evaluate"
                result = {"result": {"type": "string", "value": json.dumps({
                    "href": "http://10.0.2.100:8765/login?actor=A", "title": "",
                    "readyState": "loading", "bodyText": "", "htmlLength": 0, "resources": []})}}
            elif command["id"] == 2:
                assert command["method"] == "Page.navigate"
                assert command["params"]["url"].startswith("data:text/html")
                result = {"frameId": "test-frame", "loaderId": "test-loader"}
            else:
                assert command["id"] == 3 and command["method"] == "Runtime.evaluate"
                result = {"result": {"type": "string", "value": json.dumps({
                    "href": "data:text/html;charset=utf-8,test", "title": "CoDesk static smoke",
                    "readyState": "complete", "bodyText": "Static render OK"})}}
            response = json.dumps({"id": command["id"], "result": result}).encode()
            if len(response) < 126:
                frame = bytes([0x81, len(response)])
            elif len(response) < 65536:
                frame = bytes([0x81, 126]) + struct.pack("!H", len(response))
            else:
                frame = bytes([0x81, 127]) + struct.pack("!Q", len(response))
            self.wfile.write(frame + response)


def test_devtools_page_snapshot_reads_read_only_document_state():
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = Server(("127.0.0.1", 0), FakeDevToolsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        snapshot = _guest_devtools_page_snapshot(FakeGuest(), server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert snapshot["returncode"] == 0, snapshot
    assert snapshot["snapshot"]["target"]["url"].endswith("actor=A")
    value = snapshot["snapshot"]["cdp"]["result"]["result"]["value"]
    assert json.loads(value)["readyState"] == "loading"
    static = snapshot["snapshot"]["static_smoke"]["result"]["result"]["value"]
    assert json.loads(static)["bodyText"] == "Static render OK"


def test_chrome_guest_profile_disables_password_prompts_without_overwriting_existing_prefs(tmp_path):
    from infra.run_ticket_to_resolution_lite_native import _configure_chrome_profile

    profile = tmp_path / "fresh-profile"
    first = _configure_chrome_profile(FakeGuest(), str(profile))
    prefs_path = profile / "Default" / "Preferences"
    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
    assert first["created"] is True
    assert prefs["credentials_enable_service"] is False
    assert prefs["profile"]["password_manager_enabled"] is False
    assert prefs["profile"]["password_manager_leak_detection"] is False

    prefs_path.write_text('{"user_setting": "preserve"}', encoding="utf-8")
    second = _configure_chrome_profile(FakeGuest(), str(profile))
    assert second["created"] is False
    assert json.loads(prefs_path.read_text(encoding="utf-8")) == {"user_setting": "preserve"}


def test_browser_navigation_waits_for_omnibox_and_replaces_full_address():
    from infra.run_ticket_to_resolution_lite_native import _visible_browser_navigate

    class RecordingGuest:
        def __init__(self):
            self.code = None

        def run_pyautogui(self, code):
            self.code = code

    guest = RecordingGuest()
    url = "http://10.0.2.100:8765/login?actor=A"
    _visible_browser_navigate(guest, url)
    assert guest.code is not None
    assert "hotkey('ctrl','l'); time.sleep(0.5)" in guest.code
    assert "hotkey('ctrl','a')" in guest.code
    assert "interval=0.01" in guest.code
    assert "press('enter')" in guest.code
    assert url in guest.code


def test_model_episode_relay_state_names_are_declared_and_consistent():
    source = Path(__file__).resolve().parents[1] / "infra" / "run_ticket_to_resolution_lite_model.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "run_episode")
    stores = {node.id for node in ast.walk(function)
              if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
    loads = {node.id for node in ast.walk(function)
             if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    assert {"relay_urls", "relay_env_names", "relay_token_envs"} <= stores
    assert {"relay_urls", "relay_env_names", "relay_token_envs"} <= loads
    assert "env_vars_to_clear" not in loads

    main = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = [node.func for node in ast.walk(main) if isinstance(node, ast.Call)]
    assert any(isinstance(node, ast.Attribute) and node.attr == "_ensure_guest_runtime_libraries"
               for node in calls)


def test_model_runner_has_no_undefined_global_references():
    source = Path(__file__).resolve().parents[1] / "infra" / "run_ticket_to_resolution_lite_model.py"
    root = symtable.symtable(source.read_text(encoding="utf-8"), str(source), "exec")
    module_names = {symbol.get_name() for symbol in root.get_symbols()}
    missing = []

    def visit(scope):
        for symbol in scope.get_symbols():
            if (symbol.is_global() and symbol.is_referenced()
                    and symbol.get_name() not in module_names
                    and not hasattr(builtins, symbol.get_name())):
                missing.append((scope.get_name(), scope.get_lineno(), symbol.get_name()))
        for child in scope.get_children():
            visit(child)

    visit(root)
    assert missing == []



def test_resource_diagnostics_command_reads_cgroup_without_shell_quote_errors(tmp_path):
    from infra.run_ticket_to_resolution_lite_native import _resource_diagnostics_command

    profile = tmp_path / "chrome-profile"
    profile.mkdir()
    result = FakeGuest().execute(["bash", "-lc", _resource_diagnostics_command(str(profile))],
                                 timeout=15)

    assert result["returncode"] == 0, result
    assert "RESOURCE_DIAGNOSTICS_BEGIN" in result["output"]
    assert "CGROUP_MEMORY_DIR=" in result["output"]
    assert "MemAvailable" in result["output"]
    assert "PROCESS_LIMITS_BEGIN" in result["output"]
    assert "pids.current" in _resource_diagnostics_command(str(profile))
    assert "awk: " not in result["output"]
    assert "SyntaxError" not in result["output"]

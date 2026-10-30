from __future__ import annotations

import json
import os
import select
import socket
import subprocess
import sys
import threading
from pathlib import Path


PROXY = Path(__file__).resolve().parents[1] / "oscombo" / "qemu_guestfwd_proxy.py"


def test_guestfwd_proxy_bridges_both_directions_while_connection_is_open(tmp_path: Path):
    request = b"GET /health HTTP/1.1\r\nHost: casedesk\r\n\r\n"
    response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"
    received: list[bytes] = []
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    server_errors: list[BaseException] = []

    def serve_one_connection():
        try:
            conn, _ = listener.accept()
            with conn:
                conn.settimeout(5)
                chunks = bytearray()
                while b"\r\n\r\n" not in chunks:
                    part = conn.recv(4096)
                    if not part:
                        break
                    chunks.extend(part)
                received.append(bytes(chunks))
                conn.sendall(response)
                conn.shutdown(socket.SHUT_WR)
                # Wait for the client to close its side after receiving the
                # response; this catches accidental half-close coupling.
                while conn.recv(4096):
                    pass
        except BaseException as exc:
            server_errors.append(exc)

    server_thread = threading.Thread(target=serve_one_connection, daemon=True)
    server_thread.start()
    relay_log_path = tmp_path / "guestfwd-relay.jsonl"
    process = subprocess.Popen(
        [sys.executable, str(PROXY), str(port), str(relay_log_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    try:
        process.stdin.write(request)
        process.stdin.flush()
        ready, _, _ = select.select([process.stdout], [], [], 5)
        assert ready, "proxy did not forward host response while Guest input remained open"
        first = os.read(process.stdout.fileno(), len(response))
        assert first == response
        process.stdin.close()
        process.stdin = None
        assert process.wait(timeout=5) == 0
        assert process.stdout.read() == b""
        relay_log = process.stderr.read().decode(errors="replace")
        assert "guestfwd-relay" in relay_log, relay_log
        summary = json.loads(relay_log.split("guestfwd-relay ", 1)[1])
        assert summary["guest_to_host_bytes"] == len(request)
        assert summary["host_to_guest_bytes"] == len(response)
        saved_summary = json.loads(relay_log_path.read_text().split("guestfwd-relay ", 1)[1])
        assert saved_summary == summary
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        listener.close()
    server_thread.join(timeout=5)
    assert not server_thread.is_alive(), "test host did not observe proxy connection close"
    assert not server_errors, server_errors
    assert received == [request]

from __future__ import annotations

import base64
import hashlib
import importlib.util
import socket
import struct
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gate5_reference", ROOT / "CONC-01/integration/gate5_reference.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def read_exact(sock: socket.socket, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise RuntimeError("client disconnected")
        data.extend(chunk)
    return bytes(data)


class WebSocketTests(unittest.TestCase):
    def test_minimal_cdp_websocket_handshake_and_masked_frame(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        received = {}
        failure = []

        def server():
            try:
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(3)
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        request.extend(conn.recv(4096))
                    key = next(line.split(b":", 1)[1].strip() for line in request.split(b"\r\n")
                                if line.lower().startswith(b"sec-websocket-key:"))
                    accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
                    conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                                 b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
                    first, second = read_exact(conn, 2)
                    self.assertEqual(first & 0x0F, 1)
                    self.assertTrue(second & 0x80)
                    length = second & 0x7F
                    if length == 126:
                        length = struct.unpack("!H", read_exact(conn, 2))[0]
                    mask = read_exact(conn, 4)
                    payload = read_exact(conn, length)
                    received["payload"] = bytes(b ^ mask[i % 4] for i, b in enumerate(payload)).decode("utf-8")
                    reply = b"{\"id\":7,\"result\":{\"ok\":true}}"
                    conn.sendall(bytes([0x81, len(reply)]) + reply)
            except Exception as exc:  # surfaced in the test thread
                failure.append(exc)
            finally:
                listener.close()

        worker = threading.Thread(target=server, daemon=True)
        worker.start()
        client = MODULE.CDPWebSocket(f"ws://127.0.0.1:{port}/devtools/page/test", timeout=3)
        client.send("{\"id\":7,\"method\":\"Page.enable\"}")
        answer = client.recv()
        client.close()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failure, [])
        self.assertEqual(received.get("payload"), "{\"id\":7,\"method\":\"Page.enable\"}")
        self.assertIn('"ok":true', answer)


if __name__ == "__main__":
    unittest.main()

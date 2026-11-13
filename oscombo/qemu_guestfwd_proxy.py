"""Bridge one QEMU usernet guestfwd cmd: stream to a loopback TCP service.

QEMU starts this process once per incoming Guest TCP connection. Its stdin and
stdout are the two directions of that connection; stderr is left to QEMU's
normal log. No HTTP parsing is performed so keep-alive and arbitrary payloads
remain byte-transparent. A byte-count-only completion line helps distinguish a
relay stall from a browser/rendering problem without logging request contents.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time


def _guest_to_host(sock: socket.socket, stats: dict[str, int], lock: threading.Lock) -> None:
    try:
        while True:
            data = os.read(0, 65536)
            if not data:
                break
            sock.sendall(data)
            with lock:
                stats["guest_to_host_bytes"] += len(data)
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
    except OSError:
        # The host may close first (e.g. Connection: close); the reverse pump
        # then exits and the QEMU-owned process is allowed to terminate.
        pass


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise BrokenPipeError("QEMU guestfwd output pipe closed")
        view = view[written:]


def _record_summary(summary: dict[str, int | float], log_path: str | None) -> None:
    line = ("guestfwd-relay " + json.dumps(summary, sort_keys=True) + "\n").encode()
    if log_path:
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    print(line.decode().rstrip(), file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) not in {1, 2}:
        print("usage: qemu_guestfwd_proxy.py HOST_PORT [LOG_PATH]", file=sys.stderr)
        return 2
    log_path = args[1] if len(args) == 2 else None
    try:
        host_port = int(args[0])
    except ValueError:
        print("HOST_PORT must be an integer", file=sys.stderr)
        return 2
    if not 1 <= host_port <= 65535:
        print("HOST_PORT must be in 1..65535", file=sys.stderr)
        return 2

    try:
        sock = socket.create_connection(("127.0.0.1", host_port), timeout=10)
        sock.settimeout(None)
    except OSError as exc:
        print(f"guestfwd loopback connect failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    stats = {"guest_to_host_bytes": 0, "host_to_guest_bytes": 0}
    stats_lock = threading.Lock()
    started = time.monotonic()
    with sock:
        pump = threading.Thread(target=_guest_to_host, args=(sock, stats, stats_lock), daemon=True,
                                name="guestfwd-stdin-to-tcp")
        pump.start()
        try:
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                _write_all(1, data)
                with stats_lock:
                    stats["host_to_guest_bytes"] += len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError as exc:
            print(f"guestfwd TCP read failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        pump.join(timeout=0.25)

    with stats_lock:
        summary = dict(stats)
    summary.update({"host_port": host_port, "elapsed_s": round(time.monotonic() - started, 4)})
    _record_summary(summary, log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

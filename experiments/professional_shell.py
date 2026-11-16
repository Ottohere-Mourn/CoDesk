"""Bounded command runner invoked as the unprivileged user in the desktop container."""
from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import time


def execute(command, timeout, *, cwd="/workspace", output_limit=16384):
    process = subprocess.Popen(["bash", "-c", command], cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map() or process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                for key, _ in selector.select(min(remaining, .1)):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    available = output_limit - len(output[key.data])
                    output[key.data].extend(chunk[:available])
                    truncated[key.data] |= len(chunk) > available
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()
        process.stderr.close()
    return {**{name: value.decode(errors="replace") for name, value in output.items()},
        "exit_code": process.returncode, "timed_out": timed_out,
        "output_truncated": truncated, "output_limit_bytes_per_stream": output_limit}


if __name__ == "__main__":
    print(json.dumps(execute(sys.argv[1], float(sys.argv[2]))))

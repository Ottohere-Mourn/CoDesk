#!/usr/bin/env python3
"""Opt-in, run-overlay-only PNG encoding fix; never write the qcow2 base."""
import difflib
import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

target = Path("/home/user/server/src/capture.py")
run_root = Path(sys.argv[1]).resolve()
expected_sha = sys.argv[2]
original = target.read_bytes()
assert hashlib.sha256(original).hexdigest() == expected_sha, "Guest capture.py differs from audited source"
assert target.stat().st_uid == os.getuid(), "capture.py is not owned by the service user"
text = original.decode()
needle = 'elif normalized_format == "PNG":\n        save_kwargs["optimize"] = True'
assert text.count(needle) == 1, "PNG branch mismatch"
updated = text.replace(needle, 'elif normalized_format == "PNG":\n        save_kwargs["optimize"] = False\n        save_kwargs["compress_level"] = 1')
updated += '''

# CoDesk diagnostic: timings only; image geometry, pixels, cursor and MIME stay unchanged.
def _codesk_timed_stage(name, function):
    def timed(*args, **kwargs):
        from flask import has_request_context, request
        probe_id = request.headers.get("X-CoDesk-Probe-ID", "controller") if has_request_context() else "backend"
        started = time.monotonic()
        elapsed = None
        try:
            result = function(*args, **kwargs)
            elapsed = time.monotonic() - started
            if name == "encode" and has_request_context() and request.headers.get("X-CoDesk-Validate-Pixels") == "1":
                checked = time.monotonic()
                original_image = args[0]
                with Image.open(io.BytesIO(result[0])) as decoded:
                    assert decoded.size == original_image.size and decoded.mode == original_image.mode
                    assert decoded.tobytes() == original_image.tobytes(), "Lossless PNG pixel mismatch"
                logger.warning("CODESK_PIXEL_VALIDATION id=%s equal=true seconds=%.6f", probe_id, time.monotonic() - checked)
            return result
        finally:
            logger.warning("CODESK_CAPTURE_TIMING id=%s stage=%s seconds=%.6f", probe_id, name, elapsed if elapsed is not None else time.monotonic() - started)
    return timed
capture_screen_image = _codesk_timed_stage("capture_cursor", capture_screen_image)
encode_image_bytes = _codesk_timed_stage("encode", encode_image_bytes)
'''
compile(updated, str(target), "exec")
pid = int(subprocess.check_output(["systemctl", "show", "osworld", "-p", "MainPID", "--value"]))
assert pid > 1 and Path(f"/proc/{pid}").stat().st_uid == os.getuid(), "Service PID ownership mismatch"
assert b"/home/user/server/main.py" in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0"), "Service command mismatch"
restart = subprocess.check_output(["systemctl", "show", "osworld", "-p", "Restart", "--value"], text=True).strip()
assert restart == "on-failure", "Service restart policy changed"
run_root.mkdir(exist_ok=True)
(run_root / "capture.original.py").write_bytes(original)
(run_root / "capture.patch.diff").write_text("".join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True), fromfile="capture.original.py", tofile="capture.py")))
temporary = target.with_name(f"capture.py.codesk-{os.getpid()}")
original_mode = target.stat().st_mode & 0o777
temporary.write_text(updated)
temporary.chmod(original_mode)
os.replace(temporary, target)
report = {"old_pid": pid, "source_sha256": expected_sha,
          "new_sha256": hashlib.sha256(updated.encode()).hexdigest(),
          "original_mode": original_mode, "deployed_mode": target.stat().st_mode & 0o777,
          "owner_uid": target.stat().st_uid,
          "change": "lossless PNG optimize=False, compress_level=1; stage timing logs",
          "scope": "This Guest overlay only; base qcow2 unchanged",
          "restart": "SIGUSR1 to exact owned service PID; systemd Restart=on-failure restarts it"}
(run_root / "png-fix.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
# SIGUSR1 terminates the idle single-worker server without a core dump; the existing
# systemd on-failure policy restarts it. No sudo or unit-file change is required.
os.kill(pid, signal.SIGUSR1)

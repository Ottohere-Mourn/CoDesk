#!/usr/bin/env python3
"""Read-only X11 clipboard probe for a CoDesk Guest.

Prints JSON only. Payload bytes are never returned, only their digest. Reading a
selection requests its TARGETS/text representation from the current owner; this
may invoke the owner's normal selection-conversion handler. Consequently this
probe is instrumentation, not proof of non-perturbation; compare on/off controls.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run(argv: list[str], timeout: float = 1.5) -> bytes:
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=True, timeout=timeout, env=os.environ.copy())
    return result.stdout


def x11_owner() -> str | None:
    libname = ctypes.util.find_library("X11")
    if not libname:
        raise RuntimeError("libX11 unavailable")
    x11 = ctypes.cdll.LoadLibrary(libname)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XGetSelectionOwner.restype = ctypes.c_ulong
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(os.environ.get("DISPLAY", "").encode() or None)
    if not display:
        raise RuntimeError("cannot open X11 display")
    try:
        atom = x11.XInternAtom(display, b"CLIPBOARD", 0)
        owner = int(x11.XGetSelectionOwner(display, atom))
        return None if owner == 0 else f"0x{owner:x}"
    finally:
        x11.XCloseDisplay(display)


def window_info() -> dict[str, str | None]:
    def query(*args: str) -> str | None:
        try:
            return run(["xdotool", *args]).decode("utf-8", "replace").strip() or None
        except (OSError, subprocess.SubprocessError):
            return None
    return {"active_window_xid": query("getactivewindow"),
            "active_window_title": query("getactivewindow", "getwindowname"),
            "focused_xid": query("getwindowfocus"),
            "focused_title": query("getwindowfocus", "getwindowname")}


def sample(state_path: Path) -> dict[str, object]:
    started = time.monotonic_ns()
    owner = x11_owner()
    target_output = run(["xclip", "-selection", "clipboard", "-o", "-t", "TARGETS"])
    targets = sorted({line.strip().decode("ascii", "replace") for line in
                      target_output.splitlines() if line.strip()})
    payload = None
    for target in ("UTF8_STRING", "text/plain;charset=utf-8", "STRING"):
        if target not in targets:
            continue
        try:
            payload = run(["xclip", "-selection", "clipboard", "-o", "-t", target])
            break
        except subprocess.SubprocessError:
            continue
    # Avoid recording an impossible mixed snapshot if ownership changed while
    # TARGETS/text were being requested. Bounded retry is handled by the caller.
    owner_after = x11_owner()
    if owner_after != owner:
        raise RuntimeError("clipboard owner changed during sampling")
    digest = hashlib.sha256(payload).hexdigest() if payload is not None else None
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prior = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        prior = None
    state = {"owner_xid": owner, "payload_sha256": digest, "targets": targets}
    changed = prior is not None and any(prior.get(k) != state[k]
                                        for k in ("owner_xid", "payload_sha256", "targets"))
    generation = int(prior.get("generation", 0)) + int(changed) if prior else 0
    state_path.write_text(json.dumps({**state, "generation": generation}, sort_keys=True),
                          encoding="utf-8")
    return {**state, "payload_bytes": len(payload) if payload is not None else None,
            "generation": generation, **window_info(), "status": "ok",
            "sample_duration_ms": round((time.monotonic_ns() - started) / 1_000_000, 3),
            "payload_read": payload is not None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-path", required=True)
    args = parser.parse_args()
    try:
        result = sample(Path(args.state_path))
    except Exception as exc:  # Probe failures are structured, never silent.
        result = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())

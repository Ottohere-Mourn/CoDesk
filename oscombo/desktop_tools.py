"""Computer-use tools over the OSWorld Guest's HTTP server, shared by external harnesses (codex via MCP, pi via CLI).

Both harnesses get exactly the same tool surface and behaviour: screenshot, click, drag, move, type_text, key,
scroll, wait, declare_infeasible. Screenshots are downscaled to 1280x720 for the model and coordinates are mapped
back; actions run as pyautogui code inside the Guest. Every call (screenshots included) counts against the budget
and returns a fresh screenshot. An optional per-desktop file lock can serialize one action and its screenshot.

  python -m oscombo.desktop_tools --mcp                 # MCP stdio server (codex); needs the ``mcp`` package (<2)
  python -m oscombo.desktop_tools <tool> '<json args>'  # one call, prints {"text": ..., "image": base64|null} (pi)

Env: OSCOMBO_GUEST_URL (http://localhost:5000), OSCOMBO_ACTION_LOG (jsonl, one line per call with the focused
window title before the action; the call counter lives next to it), OSCOMBO_MAX_STEPS (budget, default 45: some
computer-use endpoints accept at most 50 images per request). ``declare_infeasible`` writes ``INFEASIBLE`` next
to the action log.
"""
from __future__ import annotations

import base64
import fcntl
import io
import json
import math
import numbers
import os
import sys
import threading
import time
from contextlib import contextmanager

import requests
from PIL import Image as PILImage

URL = os.environ.get("OSCOMBO_GUEST_URL", "http://localhost:5000").rstrip("/")
LOG = os.environ.get("OSCOMBO_ACTION_LOG")
BUDGET = int(os.environ.get("OSCOMBO_MAX_STEPS") or "45")
SETTLE = float(os.environ.get("OSCOMBO_MCP_SETTLE", "1.0"))
TYPE_TEXT_MODE = os.environ.get("OSCOMBO_TYPE_TEXT_MODE", "write")
DESKTOP_LOCK_FILE = os.environ.get("OSCOMBO_DESKTOP_LOCK_FILE")
TOOL_RESULT_COOLDOWN = max(0.0, float(os.environ.get("OSCOMBO_MCP_TURN_COOLDOWN_SEC", "0")))
_cooldown_lock = threading.Lock()
_last_tool_result_at: float | None = None
MODEL_W, MODEL_H = 1280, 720
PREFIX = "import pyautogui; import time; pyautogui.FAILSAFE = False; {cmd}"
KEYMAP = {"return": "enter", "escape": "esc", "control": "ctrl", "super": "win", "page_up": "pageup",
          "page_down": "pagedown", "prior": "pageup", "next": "pagedown", "kp_enter": "enter", "alt_l": "alt",
          "control_l": "ctrl", "shift_l": "shift"}
OUT_OF_BUDGET = f"Action budget used up ({BUDGET} tool calls). Stop now and reply with one line saying what you did."
COORDINATE_CONTRACT = ("Coordinates use pixels in the most recently returned 1280x720 screenshot, "
                       "origin at top-left; valid x is 0..1279 and y is 0..719. "
                       "Out-of-range coordinates are rejected without execution or clamping, "
                       "and the rejection is returned with a fresh screenshot.")
TOOLS = {
    "screenshot": "Take a screenshot of the whole desktop, resized to 1280x720 for the model.",
    "click": f"{COORDINATE_CONTRACT} Move the mouse to (x, y) and click. button: left|right|middle. clicks: 1 or 2 (double click).",
    "drag": f"{COORDINATE_CONTRACT} Press the left button at (x1, y1), drag to (x2, y2), release.",
    "move": f"{COORDINATE_CONTRACT} Move the mouse to (x, y) without clicking (hover).",
    "type_text": "Type text at the current keyboard focus. Use key() for Enter/Tab/shortcuts.",
    "key": "Press a key or chord, e.g. 'Return', 'Tab', 'ctrl+s', 'alt+F4'. Several presses separated by spaces.",
    "scroll": f"{COORDINATE_CONTRACT} Scroll at (x, y). direction: up|down|left|right. amount: number of wheel notches.",
    "wait": "Wait for the UI to update (seconds, max 30), then take a screenshot.",
    "declare_infeasible": "Call this (instead of acting) if you are confident the task cannot be done as specified.",
}


@contextmanager
def _state():
    """Call counter + coordinate scale, shared by all processes of one agent; locked, since a harness may issue
    several tool calls at once (pi does) and each runs in its own process."""
    path = os.path.join(os.path.dirname(LOG), "tool_state.json") if LOG else None
    if not path:
        yield {"calls": 0, "scale": [1.5, 1.5], "guest_screenshot_size": None,
               "model_screenshot_size": [MODEL_W, MODEL_H]}
        return
    with open(path + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        st = json.load(open(path)) if os.path.exists(path) else {
            "calls": 0, "scale": [1.5, 1.5], "guest_screenshot_size": None,
            "model_screenshot_size": [MODEL_W, MODEL_H]}
        st.setdefault("guest_screenshot_size", None)
        st.setdefault("model_screenshot_size", [MODEL_W, MODEL_H])
        try:
            yield st
        finally:
            json.dump(st, open(path, "w"))


@contextmanager
def _desktop_lock():
    if not DESKTOP_LOCK_FILE:
        yield
        return
    with open(DESKTOP_LOCK_FILE, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _guest(argv: list[str], timeout: float = 120) -> dict:
    r = requests.post(URL + "/execute", json={"command": argv, "shell": False}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _active_window() -> str | None:
    try:
        out = _guest(["bash", "-lc", "xdotool getactivewindow getwindowname 2>/dev/null || true"], 30)
        return (out.get("output") or "").strip() or None
    except Exception:
        return None


def _py(code: str) -> None:
    out = _guest(["python", "-c", PREFIX.format(cmd=code)])
    if out.get("status") != "success" or out.get("returncode", 0) != 0:
        raise RuntimeError(f"Guest command failed: {out.get('error') or out.get('output')}")


def _shot() -> tuple[bytes, list[float], list[int]]:
    time.sleep(SETTLE)
    r = None
    for _ in range(5):
        r = requests.get(URL + "/screenshot", timeout=120)
        if r.status_code == 200 and r.content:
            break
        time.sleep(2)
    r.raise_for_status()
    im = PILImage.open(io.BytesIO(r.content)).convert("RGB")
    scale = [im.width / MODEL_W, im.height / MODEL_H]
    buf = io.BytesIO()
    im.resize((MODEL_W, MODEL_H), PILImage.LANCZOS).save(buf, "PNG")
    return buf.getvalue(), scale, [im.width, im.height]


def _coordinate_audit(name: str, args: dict, scale: list[float],
                      guest_size: list[int] | None) -> dict | None:
    """Validate screenshot-space coordinates without changing model output."""
    keys = {"click": ("x", "y"), "move": ("x", "y"), "scroll": ("x", "y"),
            "drag": ("x1", "y1", "x2", "y2")}.get(name)
    if keys is None:
        return None
    raw = {key: args.get(key) for key in keys}
    audit = {"status": "rejected", "raw_model_coordinates": raw,
             "model_screenshot_size": [MODEL_W, MODEL_H],
             "guest_screenshot_size": guest_size, "scale": scale,
             "mapped_guest_coordinates": None, "reason": None}
    if guest_size is None:
        audit["reason"] = "no_observation_yet"
        return audit
    try:
        values = {key: float(args[key]) for key in keys}
    except (KeyError, TypeError, ValueError, OverflowError):
        audit["reason"] = "coordinate_missing_or_non_numeric"
        return audit
    if any(not math.isfinite(value) for value in values.values()):
        audit["reason"] = "coordinate_not_finite"
        return audit
    if any(isinstance(args[key], bool) or not isinstance(args[key], numbers.Real) for key in keys):
        audit["reason"] = "coordinate_must_be_numeric"
        return audit
    for key, value in values.items():
        axis = "x" if key.startswith("x") else "y"
        upper = MODEL_W if axis == "x" else MODEL_H
        if value < 0 or value >= upper:
            audit["reason"] = f"{key}_outside_model_screenshot_[0,{upper})"
            audit["mapped_guest_coordinates"] = {
                k: [int(round(values[pair[0]] * scale[0])),
                    int(round(values[pair[1]] * scale[1]))]
                for k, pair in (("start", ("x1", "y1")), ("end", ("x2", "y2")))
                if pair[0] in values
            } if name == "drag" else [int(round(values["x"] * scale[0])),
                                      int(round(values["y"] * scale[1]))]
            return audit
    if name == "drag":
        mapped = {"start": [int(round(values["x1"] * scale[0])), int(round(values["y1"] * scale[1]))],
                  "end": [int(round(values["x2"] * scale[0])), int(round(values["y2"] * scale[1]))]}
        mapped_points = mapped.values()
    else:
        mapped = [int(round(values["x"] * scale[0])), int(round(values["y"] * scale[1]))]
        mapped_points = (mapped,)
    audit["mapped_guest_coordinates"] = mapped
    if any(x < 0 or x >= guest_size[0] or y < 0 or y >= guest_size[1]
           for x, y in mapped_points):
        audit["reason"] = "mapped_coordinate_outside_guest_screenshot"
        return audit
    audit["status"] = "accepted"
    return audit


def _k(name: str) -> str:
    n = name.strip().lower()
    return KEYMAP.get(n, n)


def _code(name: str, args: dict, scale: list[float]) -> str | None:
    def xy(x, y):
        return int(round(float(x) * scale[0])), int(round(float(y) * scale[1]))

    if name == "click":
        X, Y = xy(args["x"], args["y"])
        return (f"pyautogui.click({X}, {Y}, clicks={int(args.get('clicks', 1))}, interval=0.08, "
                f"button={args.get('button', 'left')!r})")
    if name == "drag":
        X1, Y1 = xy(args["x1"], args["y1"])
        X2, Y2 = xy(args["x2"], args["y2"])
        return f"pyautogui.moveTo({X1}, {Y1}); pyautogui.dragTo({X2}, {Y2}, duration=0.6, button='left')"
    if name == "move":
        X, Y = xy(args["x"], args["y"])
        return f"pyautogui.moveTo({X}, {Y})"
    if name == "type_text":
        if TYPE_TEXT_MODE == "paste":
            # VSCode auto-indents physical Enter keys, so writing multiline
            # source character by character does not preserve the text.
            encoded = base64.b64encode(args["text"].encode("utf-8")).decode("ascii")
            return ("import base64, subprocess; "
                    "_clip = subprocess.Popen(['xclip', '-selection', 'clipboard'], "
                    "stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, "
                    "stderr=subprocess.DEVNULL, start_new_session=True); "
                    f"_clip.stdin.write(base64.b64decode({encoded!r})); "
                    "_clip.stdin.close(); time.sleep(0.4); pyautogui.hotkey('ctrl', 'v')")
        return f"pyautogui.write({args['text']!r}, interval=0.02)"
    if name == "key":
        return "; ".join(f"pyautogui.hotkey(*{[_k(p) for p in chord.split('+')]!r}); time.sleep(0.06)"
                         for chord in str(args["keys"]).split())
    if name == "scroll":
        X, Y = xy(args["x"], args["y"])
        a = int(args.get("amount", 3))
        fn = {"up": f"pyautogui.scroll({a})", "down": f"pyautogui.scroll({-a})",
              "left": f"pyautogui.hscroll({-a})", "right": f"pyautogui.hscroll({a})"}[args.get("direction", "down")]
        return f"pyautogui.moveTo({X}, {Y}); {fn}"
    if name in ("wait", "screenshot"):
        return None
    raise ValueError(f"unknown tool {name}")


def _log(rec: dict) -> None:
    if LOG:
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")


def _wait_before_tool_result() -> float:
    """Throttle successive model turns by delaying tool results, without changing actions."""
    global _last_tool_result_at
    if TOOL_RESULT_COOLDOWN <= 0:
        return 0.0
    with _cooldown_lock:
        now = time.monotonic()
        delay = TOOL_RESULT_COOLDOWN if _last_tool_result_at is None else max(
            0.0, TOOL_RESULT_COOLDOWN - (now - _last_tool_result_at))
        if delay:
            time.sleep(delay)
        _last_tool_result_at = time.monotonic()
        return round(delay, 3)


def run_tool(name: str, args: dict) -> tuple[str, bytes | None]:
    """Execute one tool call; returns (text, png bytes or None)."""
    with _desktop_lock():
        return _run_tool_locked(name, args)


def _run_tool_locked(name: str, args: dict) -> tuple[str, bytes | None]:
    tool_started_at = time.time()
    with _state() as st:  # reserve a call number (and read the latest scale) atomically
        if name != "declare_infeasible" and st["calls"] >= BUDGET:
            return OUT_OF_BUDGET, None
        st["calls"] += 1
        n, scale = st["calls"], st["scale"]
        input_guest_size = st.get("guest_screenshot_size")
    if name == "declare_infeasible":
        if LOG:
            with open(os.path.join(os.path.dirname(LOG), "INFEASIBLE"), "w") as f:
                f.write(str(args.get("reason", "")))
        _log({"t": time.time(), "n": n, "tool": name, "args": args, "window_before": None, "code": None})
        return "Recorded the task as infeasible. Stop now.", None
    audit = _coordinate_audit(name, args, scale, input_guest_size)
    if audit is not None and audit["status"] == "rejected":
        reason = audit["reason"]
        mapped = audit.get("mapped_guest_coordinates")
        message = (f"REJECTED: no desktop action was executed. {reason}; raw model coordinates="
                   f"{audit['raw_model_coordinates']}, mapped Guest coordinates={mapped}, "
                   f"model screenshot={audit['model_screenshot_size']}, "
                   f"source Guest screenshot={input_guest_size}, scale={scale}. "
                   f"Coordinates are screenshot pixels (x 0..{MODEL_W-1}, y 0..{MODEL_H-1}); "
                   "re-observe and choose a valid coordinate. No coordinate was clamped or corrected.")
        before = _active_window()
        png, new_scale, guest_size = _shot()
        _store_observation(new_scale, guest_size)
        _save_screenshot(n, png)
        cooldown = _wait_before_tool_result()
        _log({"t": time.time(), "n": n, "tool": name, "args": args,
              "window_before": before, "code": None, "executed": False,
              "coordinate_audit": audit,
              "tool_result_cooldown_s": cooldown,
              "returned_observation": {"model_screenshot_size": [MODEL_W, MODEL_H],
                                       "guest_screenshot_size": guest_size,
                                       "scale": new_scale},
              "result": message})
        return message, png
    code = _code(name, args, scale)
    if name == "wait":
        time.sleep(min(float(args.get("seconds", 2.0)), 30))
    before = _active_window() if code else None
    action_started_at = time.time()
    action_error = None
    try:
        if code:
            _py(code)
    except Exception as exc:
        action_error = exc
    action_ended_at = time.time()
    after = _active_window() if code else None
    shot_started_at = time.time()
    try:
        png, new_scale, guest_size = _shot()
    except Exception as exc:
        _log({"t": time.time(), "n": n, "tool": name, "args": args, "code": code,
              "started_at": tool_started_at, "action_started_at": action_started_at,
              "action_ended_at": action_ended_at, "window_before": before,
              "window_after": after, "window_samples_atomic": bool(DESKTOP_LOCK_FILE),
              "error": f"{type(exc).__name__}: {exc}", "phase": "screenshot",
              "action_error": str(action_error) if action_error else None})
        raise
    shot_ended_at = time.time()
    _store_observation(new_scale, guest_size)
    _save_screenshot(n, png)
    cooldown = _wait_before_tool_result()
    _log({"t": time.time(), "n": n, "tool": name, "args": args,
          "window_before": before, "code": code, "executed": bool(code),
          "window_after": after, "window_samples_atomic": bool(DESKTOP_LOCK_FILE),
          "started_at": tool_started_at, "action_started_at": action_started_at,
          "action_ended_at": action_ended_at, "screenshot_started_at": shot_started_at,
          "screenshot_ended_at": shot_ended_at,
          "screenshot_s": shot_ended_at - shot_started_at,
          "action_error": str(action_error) if action_error else None,
          "tool_result_cooldown_s": cooldown,
          "coordinate_audit": audit,
          "input_observation": {"model_screenshot_size": [MODEL_W, MODEL_H],
                                "guest_screenshot_size": input_guest_size,
                                "scale": scale},
          "returned_observation": {"model_screenshot_size": [MODEL_W, MODEL_H],
                                   "guest_screenshot_size": guest_size,
                                   "scale": new_scale}})
    if action_error is not None:
        raise action_error
    left = BUDGET - n
    return (f"OK. {left} tool calls left." if left <= 5 else "OK."), png


def _store_observation(scale: list[float], guest_size: list[int]) -> None:
    with _state() as st:
        st["scale"] = scale
        st["guest_screenshot_size"] = guest_size
        st["model_screenshot_size"] = [MODEL_W, MODEL_H]


def _save_screenshot(n: int, png: bytes) -> None:
    if LOG:
        shots = os.path.join(os.path.dirname(LOG), "shots")
        os.makedirs(shots, exist_ok=True)
        with open(os.path.join(shots, f"{n:03d}.png"), "wb") as f:
            f.write(png)


def mcp_main() -> None:
    from mcp.server.fastmcp import FastMCP, Image

    mcp = FastMCP("desktop")

    def out(res):
        text, png = res
        return [text, Image(data=png, format="png")] if png else text

    @mcp.tool(description=TOOLS["screenshot"])
    def screenshot():
        return out(run_tool("screenshot", {}))

    @mcp.tool(description=TOOLS["click"])
    def click(x: int, y: int, button: str = "left", clicks: int = 1):
        return out(run_tool("click", {"x": x, "y": y, "button": button, "clicks": clicks}))

    @mcp.tool(description=TOOLS["drag"])
    def drag(x1: int, y1: int, x2: int, y2: int):
        return out(run_tool("drag", {"x1": x1, "y1": y1, "x2": x2, "y2": y2}))

    @mcp.tool(description=TOOLS["move"])
    def move(x: int, y: int):
        return out(run_tool("move", {"x": x, "y": y}))

    @mcp.tool(description=TOOLS["type_text"])
    def type_text(text: str):
        return out(run_tool("type_text", {"text": text}))

    @mcp.tool(description=TOOLS["key"])
    def key(keys: str):
        return out(run_tool("key", {"keys": keys}))

    @mcp.tool(description=TOOLS["scroll"])
    def scroll(x: int, y: int, direction: str = "down", amount: int = 3):
        return out(run_tool("scroll", {"x": x, "y": y, "direction": direction, "amount": amount}))

    @mcp.tool(description=TOOLS["wait"])
    def wait(seconds: float = 2.0):
        return out(run_tool("wait", {"seconds": seconds}))

    @mcp.tool(description=TOOLS["declare_infeasible"])
    def declare_infeasible(reason: str):
        return out(run_tool("declare_infeasible", {"reason": reason}))

    mcp.run()


def main(argv: list[str]) -> None:
    if argv == ["--mcp"]:
        mcp_main()
        return
    try:
        text, png = run_tool(argv[0], json.loads(argv[1]) if len(argv) > 1 else {})
        print(json.dumps({"text": text, "image": base64.b64encode(png).decode() if png else None}))
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))


if __name__ == "__main__":
    main(sys.argv[1:])

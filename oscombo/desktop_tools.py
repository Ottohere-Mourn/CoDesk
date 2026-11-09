"""Computer-use tools over the OSWorld Guest's HTTP server, shared by external harnesses (codex via MCP, pi via CLI).

Both harnesses get exactly the same tool surface and behaviour: screenshot, click, drag, move, type_text, key,
scroll, wait, declare_infeasible. Screenshots are downscaled to 1280x720 for the model and coordinates are mapped
back; actions run as pyautogui code inside the Guest. Every call (screenshots included) counts against the budget
and returns a fresh screenshot. By default calls are not coordinated; if OSCOMBO_ACTION_LOCK_FILE is set, a run-wide
flock serializes one complete MCP call (including its returned screenshot), but never the model inference interval.

  python -m oscombo.desktop_tools --mcp                 # MCP stdio server (codex); needs the ``mcp`` package (<2)
  python -m oscombo.desktop_tools <tool> '<json args>'  # one call, prints {"text": ..., "image": base64|null} (pi)

Env: OSCOMBO_GUEST_URL, OSCOMBO_ACTION_LOG (per-actor jsonl), OSCOMBO_RUN_ID, OSCOMBO_ACTOR_ID, optional
OSCOMBO_ACTION_LOCK_FILE and OSCOMBO_ACTION_LOCK_EVENTS_FILE (shared lock-call result/timing jsonl), and
OSCOMBO_MAX_STEPS (budget, default 45). ``declare_infeasible`` writes ``INFEASIBLE`` next to the action log.
"""
from __future__ import annotations

import base64
import fcntl
import io
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

import requests
from PIL import Image as PILImage

from .eventlog import append_jsonl

URL = os.environ.get("OSCOMBO_GUEST_URL", "http://localhost:5000").rstrip("/")
LOG = os.environ.get("OSCOMBO_ACTION_LOG")
UNIFIED_EVENT_LOG = os.environ.get("OSCOMBO_UNIFIED_EVENT_LOG")
BUDGET = int(os.environ.get("OSCOMBO_MAX_STEPS") or "45")
SETTLE = float(os.environ.get("OSCOMBO_MCP_SETTLE", "1.0"))
MODEL_W, MODEL_H = 1280, 720
PREFIX = "import pyautogui; import time; pyautogui.FAILSAFE = False; {cmd}"
KEYMAP = {"return": "enter", "escape": "esc", "control": "ctrl", "super": "win", "page_up": "pageup",
          "page_down": "pagedown", "prior": "pageup", "next": "pagedown", "kp_enter": "enter", "alt_l": "alt",
          "control_l": "ctrl", "shift_l": "shift"}
OUT_OF_BUDGET = f"Action budget used up ({BUDGET} tool calls). Stop now and reply with one line saying what you did."
TOOLS = {
    "screenshot": "Take a screenshot of the whole desktop (1280x720).",
    "click": "Move the mouse to (x, y) and click. button: left|right|middle. clicks: 1 or 2 (double click).",
    "drag": "Press the left button at (x1, y1), drag to (x2, y2), release.",
    "move": "Move the mouse to (x, y) without clicking (hover).",
    "type_text": "Type text at the current keyboard focus. Use key() for Enter/Tab/shortcuts.",
    "key": "Press a key or chord, e.g. 'Return', 'Tab', 'ctrl+s', 'alt+F4'. Several presses separated by spaces.",
    "scroll": "Scroll at (x, y). direction: up|down|left|right. amount: number of wheel notches.",
    "wait": "Wait for the UI to update (seconds, max 30), then take a screenshot.",
    "declare_infeasible": "Call this (instead of acting) if you are confident the task cannot be done as specified.",
}


@contextmanager
def _state():
    """Call counter + coordinate scale, shared by all processes of one agent; locked, since a harness may issue
    several tool calls at once (pi does) and each runs in its own process."""
    path = os.path.join(os.path.dirname(LOG), "tool_state.json") if LOG else None
    if not path:
        yield {"calls": 0, "scale": [1.5, 1.5]}
        return
    with open(path + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        st = json.load(open(path)) if os.path.exists(path) else {"calls": 0, "scale": [1.5, 1.5]}
        try:
            yield st
        finally:
            json.dump(st, open(path, "w"))


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


def _shot() -> tuple[bytes, list[float]]:
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
    return buf.getvalue(), scale


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
    now_wall, now_mono = time.time(), time.monotonic()
    rec.setdefault("event_id", uuid.uuid4().hex)
    rec.setdefault("timestamp_utc", datetime.fromtimestamp(now_wall, timezone.utc).isoformat())
    rec.setdefault("wall_time", now_wall)
    rec.setdefault("monotonic_time", now_mono)
    run_start = os.environ.get("OSCOMBO_RUN_START_MONO")
    if run_start:
        rec.setdefault("run_elapsed_s", round(now_mono-float(run_start), 6))
    rec.setdefault("event_type", "agent_gui_action")
    rec.setdefault("run_id", os.environ.get("OSCOMBO_RUN_ID"))
    rec.setdefault("actor_id", os.environ.get("OSCOMBO_ACTOR_ID"))
    rec.setdefault("episode_id", os.environ.get("OSCOMBO_EPISODE_ID") or rec.get("actor_id"))
    if LOG:
        append_jsonl(LOG, rec)
    if UNIFIED_EVENT_LOG and os.path.abspath(UNIFIED_EVENT_LOG) != os.path.abspath(LOG or ""):
        append_jsonl(UNIFIED_EVENT_LOG, rec)


@contextmanager
def action_lock(tool: str | None = None, args: dict | None = None):
    """Optional run-wide mutex for one complete GUI MCP call, including its returned screenshot.

    This is deliberately not an episode/transaction lock: Codex inference happens outside this context.
    """
    path = os.environ.get("OSCOMBO_ACTION_LOCK_FILE")
    if not path:
        yield None
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    requested_wall, requested_mono = time.time(), time.monotonic()
    with open(path, "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        acquired_wall, acquired_mono = time.time(), time.monotonic()
        event = {"event_type": "action_lock", "run_id": os.environ.get("OSCOMBO_RUN_ID"),
                 "actor_id": os.environ.get("OSCOMBO_ACTOR_ID"), "tool": tool, "args": args or {},
                 "lock_file": path, "requested_at": requested_wall, "acquired_at": acquired_wall,
                 "lock_wait_s": round(acquired_mono - requested_mono, 6)}
        try:
            yield event
        finally:
            event["released_at"] = time.time()
            event["lock_held_s"] = round(time.monotonic() - acquired_mono, 6)
            event_path = os.environ.get("OSCOMBO_ACTION_LOCK_EVENTS_FILE") or (path + ".events.jsonl")
            event_parent = os.path.dirname(event_path)
            if event_parent:
                os.makedirs(event_parent, exist_ok=True)
            append_jsonl(event_path, event)
            if UNIFIED_EVENT_LOG:
                append_jsonl(UNIFIED_EVENT_LOG, event)
            fcntl.flock(lock, fcntl.LOCK_UN)


def _run_tool_unlocked(name: str, args: dict, lock_info: dict | None = None) -> tuple[str, bytes | None]:
    """Execute one desktop call; caller owns the optional run-wide lock."""
    started_wall, started_mono = time.time(), time.monotonic()
    with _state() as st:
        if name != "declare_infeasible" and st["calls"] >= BUDGET:
            ended_wall, ended_mono = time.time(), time.monotonic()
            _log({"t": started_wall, "n": st["calls"], "tool": name, "args": args, "code": None,
                  "status": "out_of_budget", "start_wall": started_wall, "start_monotonic": started_mono,
                  "end_wall": ended_wall, "end_monotonic": ended_mono,
                  "duration_s": round(ended_mono-started_mono, 6),
                  "lock_wait_s": (lock_info or {}).get("lock_wait_s", 0)})
            return OUT_OF_BUDGET, None
        st["calls"] += 1
        n, scale = st["calls"], st["scale"]
    if name == "declare_infeasible":
        if LOG:
            with open(os.path.join(os.path.dirname(LOG), "INFEASIBLE"), "w") as f:
                f.write(str(args.get("reason", "")))
        ended_wall, ended_mono = time.time(), time.monotonic()
        _log({"t": started_wall, "n": n, "tool": name, "args": args, "window_before": _active_window(),
              "window_after": _active_window(), "code": None, "status": "ok",
              "start_wall": started_wall, "start_monotonic": started_mono,
              "end_wall": ended_wall, "end_monotonic": ended_mono,
              "duration_s": round(ended_mono-started_mono, 6),
              "lock_wait_s": (lock_info or {}).get("lock_wait_s", 0)})
        return "Recorded the task as infeasible. Stop now and reply with one short line.", None
    code = _code(name, args, scale)
    if name == "wait":
        time.sleep(min(float(args.get("seconds", 2.0)), 30))
    before = _active_window()
    if code:
        _py(code)
    png, scale = _shot()
    after = _active_window()
    ended_wall, ended_mono = time.time(), time.monotonic()
    with _state() as st:
        st["scale"] = scale
    screenshot_path = None
    if LOG:
        shots = os.path.join(os.path.dirname(LOG), "shots")
        os.makedirs(shots, exist_ok=True)
        screenshot_path = os.path.join(shots, f"{n:03d}.png")
        with open(screenshot_path, "wb") as f:
            f.write(png)
    expected_app = os.environ.get("OSCOMBO_EXPECTED_APP")
    key_chords = [chord.strip().lower() for chord in str(args.get("keys", "")).split()]
    deliberate_switch = name == "key" and any(chord in {
        "alt+tab", "alt+shift+tab", "ctrl+tab", "ctrl+page_down", "ctrl+pageup"
    } for chord in key_chords)
    target_activated = bool(expected_app and expected_app.lower() not in (before or "").lower()
                            and expected_app.lower() in (after or "").lower())
    focus_switch = deliberate_switch or target_activated
    input_action = bool(code and name not in {"screenshot", "wait", "declare_infeasible"} and not focus_switch)
    misrouted = bool(expected_app and input_action and expected_app.lower() not in (before or "").lower())
    _log({"t": started_wall, "n": n, "tool": name, "args": args, "window_before": before,
          "window_after": after, "expected_app": expected_app or None, "focus_switch_action": focus_switch,
          "target_activated": target_activated, "misrouted_focus_before": misrouted, "code": code, "status": "ok",
          "start_wall": started_wall, "start_monotonic": started_mono,
          "end_wall": ended_wall, "end_monotonic": ended_mono,
          "duration_s": round(ended_mono-started_mono, 6),
          "lock_wait_s": (lock_info or {}).get("lock_wait_s", 0),
          "screenshot_path": screenshot_path, "screenshot_bytes": len(png)})
    left = BUDGET - n
    return (f"OK. {left} tool calls left." if left <= 5 else "OK."), png


def run_tool(name: str, args: dict) -> tuple[str, bytes | None]:
    """Execute one full MCP tool call under the optional cross-Actor desktop mutex."""
    with action_lock(name, args) as event:
        try:
            result = _run_tool_unlocked(name, args, event)
            if event is not None:
                event.update({"status": "ok", "result_text": result[0], "image_returned": result[1] is not None})
            return result
        except Exception as exc:
            if event is not None:
                event.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]})
            raise


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

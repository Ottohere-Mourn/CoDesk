"""Computer-use tools over the OSWorld Guest's HTTP server, shared by external harnesses (codex via MCP, pi via CLI).

Both harnesses get exactly the same tool surface and behaviour: screenshot, click, drag, move, type_text, key,
scroll, wait, declare_infeasible. Screenshots are downscaled to 1280x720 for the model and coordinates are mapped
back; actions run as pyautogui code inside the Guest. Every call (screenshots included) counts against the budget
and returns a fresh screenshot. Nothing here coordinates with other agents on the same desktop.

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
import os
import sys
import time
from contextlib import contextmanager

import requests
from PIL import Image as PILImage

URL = os.environ.get("OSCOMBO_GUEST_URL", "http://localhost:5000").rstrip("/")
LOG = os.environ.get("OSCOMBO_ACTION_LOG")
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
    if LOG:
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")


def run_tool(name: str, args: dict) -> tuple[str, bytes | None]:
    """Execute one tool call; returns (text, png bytes or None)."""
    with _state() as st:  # reserve a call number (and read the latest scale) atomically
        if name != "declare_infeasible" and st["calls"] >= BUDGET:
            return OUT_OF_BUDGET, None
        st["calls"] += 1
        n, scale = st["calls"], st["scale"]
    if name == "declare_infeasible":
        if LOG:
            with open(os.path.join(os.path.dirname(LOG), "INFEASIBLE"), "w") as f:
                f.write(str(args.get("reason", "")))
        _log({"t": time.time(), "n": n, "tool": name, "args": args, "window_before": None, "code": None})
        return "Recorded the task as infeasible. Stop now.", None
    code = _code(name, args, scale)
    if name == "wait":
        time.sleep(min(float(args.get("seconds", 2.0)), 30))
    before = _active_window() if code else None
    if code:
        _py(code)
    _log({"t": time.time(), "n": n, "tool": name, "args": args, "window_before": before, "code": code})
    png, scale = _shot()
    with _state() as st:
        st["scale"] = scale
    if LOG:  # what the model saw, for trajectory viewers
        shots = os.path.join(os.path.dirname(LOG), "shots")
        os.makedirs(shots, exist_ok=True)
        with open(os.path.join(shots, f"{n:03d}.png"), "wb") as f:
            f.write(png)
    left = BUDGET - n
    return (f"OK. {left} tool calls left." if left <= 5 else "OK."), png


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

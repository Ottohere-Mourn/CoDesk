"""Computer-use MCP server over the OSWorld Guest's HTTP server, for external agent harnesses (codex, ...).

Every action tool returns a fresh screenshot. Screenshots are downscaled to ``OSCOMBO_MCP_WIDTH`` x
``OSCOMBO_MCP_HEIGHT`` (default 1280x720) for the model and coordinates are mapped back to the Guest screen.

Env:
  OSCOMBO_GUEST_URL    in-VM server, e.g. http://localhost:5000 (set by the external harness)
  OSCOMBO_ACTION_LOG   jsonl action log (optional); the harness turns it into the run trace
  OSCOMBO_MCP_SETTLE   seconds to wait before each screenshot (default 1.0)
  OSCOMBO_MAX_STEPS    tool-call budget; further calls are refused (default: unlimited)

``declare_infeasible`` writes ``INFEASIBLE`` next to the action log; the harness reports that as FAIL.
Run: ``python -m oscombo.mcp_server`` (stdio transport; needs the ``mcp`` package).
"""
from __future__ import annotations

import io
import json
import os
import time

import requests
from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage

URL = os.environ.get("OSCOMBO_GUEST_URL", "http://localhost:5000").rstrip("/")
LOG = os.environ.get("OSCOMBO_ACTION_LOG")
SETTLE = float(os.environ.get("OSCOMBO_MCP_SETTLE", "1.0"))
MODEL_W = int(os.environ.get("OSCOMBO_MCP_WIDTH", "1280"))
MODEL_H = int(os.environ.get("OSCOMBO_MCP_HEIGHT", "720"))
MAX_STEPS = int(os.environ.get("OSCOMBO_MAX_STEPS", "0"))
PREFIX = "import pyautogui; import time; pyautogui.FAILSAFE = False; {cmd}"

mcp = FastMCP("desktop")
_scale = [1.5, 1.5]  # Guest px per model px, refreshed on every screenshot
_calls = [0]


def _active_window() -> str | None:
    try:
        r = requests.post(URL + "/execute", json={"command": ["bash", "-lc",
                          "xdotool getactivewindow getwindowname 2>/dev/null || true"], "shell": False}, timeout=30)
        return (r.json().get("output") or "").strip() or None
    except Exception:
        return None


def _log(tool: str, **kw) -> None:
    _calls[0] += 1
    if MAX_STEPS and _calls[0] > MAX_STEPS and tool != "declare_infeasible":
        raise RuntimeError(f"Step budget of {MAX_STEPS} tool calls is exhausted. Stop now and give your final "
                           "answer.")
    if not LOG:
        return
    rec = {"t": time.time(), "tool": tool, **kw}
    if tool not in ("screenshot", "wait", "declare_infeasible"):
        rec["window_before"] = _active_window()
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _py(cmd: str) -> None:
    r = requests.post(URL + "/execute", json={"command": ["python", "-c", PREFIX.format(cmd=cmd)], "shell": False},
                      timeout=120)
    r.raise_for_status()
    out = r.json()
    if out.get("status") != "success" or out.get("returncode", 0) != 0:
        raise RuntimeError(f"Guest command failed: {out.get('error') or out.get('output')}")


def _xy(x: int, y: int) -> tuple[int, int]:
    return int(round(x * _scale[0])), int(round(y * _scale[1]))


def _shot() -> Image:
    time.sleep(SETTLE)
    for _ in range(5):
        r = requests.get(URL + "/screenshot", timeout=120)
        if r.status_code == 200:
            break
        time.sleep(2)
    r.raise_for_status()
    im = PILImage.open(io.BytesIO(r.content)).convert("RGB")
    _scale[0], _scale[1] = im.width / MODEL_W, im.height / MODEL_H
    buf = io.BytesIO()
    im.resize((MODEL_W, MODEL_H), PILImage.LANCZOS).save(buf, "PNG")
    return Image(data=buf.getvalue(), format="png")


@mcp.tool()
def screenshot() -> Image:
    """Take a screenshot of the whole desktop."""
    _log("screenshot")
    return _shot()


@mcp.tool()
def click(x: int, y: int, button: str = "left", clicks: int = 1) -> Image:
    """Move the mouse to (x, y) and click. button: left|right|middle. clicks: 1 or 2 (double click)."""
    _log("click", x=x, y=y, button=button, clicks=clicks)
    X, Y = _xy(x, y)
    _py(f"pyautogui.click({X}, {Y}, clicks={int(clicks)}, interval=0.08, button={button!r})")
    return _shot()


@mcp.tool()
def drag(x1: int, y1: int, x2: int, y2: int) -> Image:
    """Press the left button at (x1, y1), drag to (x2, y2), release."""
    _log("drag", x1=x1, y1=y1, x2=x2, y2=y2)
    X1, Y1 = _xy(x1, y1)
    X2, Y2 = _xy(x2, y2)
    _py(f"pyautogui.moveTo({X1}, {Y1}); pyautogui.dragTo({X2}, {Y2}, duration=0.6, button='left')")
    return _shot()


@mcp.tool()
def move(x: int, y: int) -> Image:
    """Move the mouse to (x, y) without clicking (hover)."""
    _log("move", x=x, y=y)
    X, Y = _xy(x, y)
    _py(f"pyautogui.moveTo({X}, {Y})")
    return _shot()


@mcp.tool()
def type_text(text: str) -> Image:
    """Type text at the current keyboard focus. Use key() for Enter/Tab/shortcuts."""
    _log("type_text", text=text)
    _py(f"pyautogui.write({text!r}, interval=0.02)")
    return _shot()


# xdotool-style names -> pyautogui names
KEYMAP = {"return": "enter", "escape": "esc", "control": "ctrl", "super": "win", "page_up": "pageup",
          "page_down": "pagedown", "prior": "pageup", "next": "pagedown", "kp_enter": "enter", "alt_l": "alt",
          "control_l": "ctrl", "shift_l": "shift"}


def _k(name: str) -> str:
    n = name.strip().lower()
    return KEYMAP.get(n, n)


@mcp.tool()
def key(keys: str) -> Image:
    """Press a key or chord, e.g. 'Return', 'Tab', 'ctrl+s', 'ctrl+shift+t', 'alt+F4'.
    Several presses can be separated by spaces: 'Down Down Return'."""
    _log("key", keys=keys)
    cmds = [f"pyautogui.hotkey(*{[_k(p) for p in chord.split('+')]!r}); time.sleep(0.06)" for chord in keys.split()]
    _py("; ".join(cmds))
    return _shot()


@mcp.tool()
def scroll(x: int, y: int, direction: str = "down", amount: int = 3) -> Image:
    """Scroll at (x, y). direction: up|down|left|right. amount: number of wheel notches."""
    _log("scroll", x=x, y=y, direction=direction, amount=amount)
    X, Y = _xy(x, y)
    a = int(amount)
    fn = {"up": f"pyautogui.scroll({a})", "down": f"pyautogui.scroll({-a})",
          "left": f"pyautogui.hscroll({-a})", "right": f"pyautogui.hscroll({a})"}[direction]
    _py(f"pyautogui.moveTo({X}, {Y}); {fn}")
    return _shot()


@mcp.tool()
def wait(seconds: float = 2.0) -> Image:
    """Wait for the UI to update, then take a screenshot."""
    _log("wait", seconds=seconds)
    time.sleep(min(seconds, 30))
    return _shot()


@mcp.tool()
def declare_infeasible(reason: str) -> str:
    """Call this (instead of acting) if you are confident the task cannot be done as specified."""
    _log("declare_infeasible", reason=reason)
    if LOG:
        with open(os.path.join(os.path.dirname(LOG), "INFEASIBLE"), "w") as f:
            f.write(reason)
    return "Recorded the task as infeasible. Stop now."


if __name__ == "__main__":
    mcp.run()

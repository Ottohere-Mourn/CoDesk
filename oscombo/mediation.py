"""Optional desktop mediation for several step-loop agents on one Guest (harness-level fixes, as a product would add).

``broker1``    input broker: one agent at a time gets the desktop for "bring my window to the front + screenshot"
               and for "bring my window to the front + run my action batch"; agents still think concurrently.
``broker2``    broker1 + window ownership: keyboard input aimed at a window owned only by another agent is refused
               and the agent is told so.
``selfguard``  each agent protects only itself (no lock, no shared registry): before every observation and every
               input it brings its own window back to the front, and types at full speed.

Window ownership comes from setup provenance: the windows that appeared while a task's setup ran belong to that
task (``combo.setup_tasks`` records them), with the task app's window title as a fallback for windows no setup
claimed (broker); windows that appear during an agent's own batch become its own.
External harnesses (codex, pi, command) run unmodified: mediation applies to the ``step`` harness only.
"""
from __future__ import annotations

import collections
import re
import threading
import time

from .guest import Guest

MODES = ("none", "broker1", "broker2", "selfguard")
KEYBOARD = re.compile(r"typewrite|write\(|hotkey|press\(|keyDown")
REFUSED_NOTICE = ("System notice: keyboard input was not delivered because the focused window ('{window}') belongs "
                  "to another agent working on this computer. Work only in your own task's windows.")


class _Windows:
    def __init__(self, guest: Guest):
        self.guest = guest

    def sh(self, cmd: str) -> str:
        try:
            return self.guest.execute(["bash", "-lc", cmd], 60).get("output") or ""
        except Exception:
            return ""

    def visible(self) -> set[str]:
        return set(self.sh("xdotool search --onlyvisible --name . 2>/dev/null").split())

    def titled(self) -> dict[str, str]:
        out = self.sh('for w in $(xdotool search --onlyvisible --name . 2>/dev/null); do '
                      'echo "$w $(xdotool getwindowname $w 2>/dev/null)"; done')
        return {ln.split(" ", 1)[0]: (ln.split(" ", 1) + [""])[1] for ln in out.splitlines() if ln.strip()}

    def active(self) -> str:
        return self.sh("xdotool getactivewindow 2>/dev/null").strip()

    def activate(self, wid: str, pause: float = 0.3) -> None:
        self.sh(f"xdotool windowactivate --sync {wid} 2>/dev/null; sleep {pause}")

    def settle(self, timeout: float = 40.0) -> set[str]:
        """Window list once it stops changing (apps launched by a setup appear asynchronously)."""
        prev, deadline = self.visible(), time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(5)
            cur = self.visible()
            if cur == prev:
                return cur
            prev = cur
        return prev


class DesktopBroker:
    """Shared by all agents of a run (``broker1`` / ``broker2``)."""

    def __init__(self, guest: Guest, setup_windows: dict[str, set[str]], level: int,
                 app_titles: dict[str, str] | None = None):
        self.w = _Windows(guest)
        self.level = level
        self.lock = threading.Lock()
        self.owner: dict[str, set[str]] = collections.defaultdict(set)
        self.home: dict[str, str | None] = {}
        for name, wins in setup_windows.items():
            self.home[name] = next(iter(sorted(wins)), None)
            for wid in wins:
                self.owner[wid].add(name)
        # fallback for windows no setup claimed (e.g. an app that came up after the setup window was recorded):
        # owned by the agents whose task app the title matches
        for wid, title in self.w.titled().items() if app_titles else ():
            if wid not in self.owner:
                for name, pattern in app_titles.items():
                    if re.search(pattern, title):
                        self.owner[wid].add(name)
                        self.home[name] = self.home.get(name) or wid
        self.stats = collections.Counter()

    def bring_home(self, name: str) -> None:
        wins = self.w.visible()
        wid = self.home.get(name)
        if wid not in wins:  # home window closed: fall back to any window this agent still owns
            wid = next((x for x in sorted(wins) if name in self.owner.get(x, ())), None)
            self.home[name] = wid
        if wid and self.w.active() != wid:
            self.w.activate(wid)
            self.stats["focus_restored"] += 1

    def after_batch(self, name: str, before: set[str]) -> None:
        for wid in self.w.visible() - before:
            if wid not in self.owner:
                self.owner[wid].add(name)
        act = self.w.active()
        if name in self.owner.get(act, ()):
            self.home[name] = act

    def refuses(self, name: str, code: str) -> bool:
        if self.level < 2 or not KEYBOARD.search(code):
            return False
        owners = self.owner.get(self.w.active(), set())
        if owners and name not in owners:
            self.stats["refused"] += 1
            return True
        return False


class SelfGuard:
    """One per agent (``selfguard``); it knows nothing about the other agents."""

    def __init__(self, guest: Guest, windows: set[str]):
        self.w = _Windows(guest)
        self.own = set(windows)
        self.pids = {p for p in (self._pid(x) for x in windows) if p}
        self.home = next(iter(sorted(windows)), None)
        self.stats = collections.Counter()

    def _pid(self, wid: str) -> str:
        return self.w.sh(f"xdotool getwindowpid {wid} 2>/dev/null").strip()

    def mine(self, wid: str) -> bool:
        return bool(wid) and (wid in self.own or (self._pid(wid) or "-") in self.pids)

    def front(self) -> None:
        act = self.w.active()
        if self.home and act != self.home and not self.mine(act):
            self.w.activate(self.home, 0.2)
            self.stats["refocus_before_look"] += 1

    def wrap(self, code: str) -> str:
        """Same Guest process first puts focus back on my window if needed, then acts; text typed at full speed."""
        if not self.home:
            return code
        mine = " ".join(sorted(self.own))
        code = re.sub(r"interval=[0-9.]+", "interval=0", code)
        return ("import subprocess as _sp\n"
                "_a = _sp.run(['xdotool', 'getactivewindow'], capture_output=True, text=True).stdout.strip()\n"
                f"if _a not in '{mine}'.split():\n"
                f"    _sp.run(['xdotool', 'windowactivate', '--sync', '{self.home}'])\n" + code)

    def adopt_new(self, before: set[str]) -> None:
        """A window that appeared during my own action and is now in front was opened by me."""
        act = self.w.active()
        if act and act not in before and act not in self.own:
            self.own.add(act)
            pid = self._pid(act)
            if pid:
                self.pids.add(pid)
            self.stats["adopted"] += 1
        if act in self.own:
            self.home = act


def window_probe(guest: Guest):
    """Callable for ``combo.setup_tasks``: the settled set of visible windows."""
    return _Windows(guest).settle

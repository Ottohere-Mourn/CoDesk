"""Scripted User/Agent actors for the Human-Agent Shared Desktop minimum PoC."""
from __future__ import annotations

import fcntl
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .eventlog import EventLog


@dataclass(frozen=True)
class GUIAction:
    name: str
    code: str
    expected_app: str | None = None
    delay_before_s: float = 0.0


class ScriptedGUIActor:
    """Open-loop GUI replay; per-action lock includes focus reads and post-action screenshot, not think time."""

    def __init__(self, *, actor_id: str, guest: Any, actions: Iterable[GUIAction], event_log: EventLog,
                 out: str | Path, guest_id: str, lock_path: str | Path | None = None,
                 strategy: str = "fixed", report_line: str = "Status verified: PO-441 completed.",
                 start_barrier: threading.Barrier | None = None,
                 pause_after: dict[str, tuple[threading.Event, threading.Event]] | None = None,
                 post_action_hook: Callable[[str, GUIAction, dict[str, Any]], Any] | None = None):
        if strategy not in {"fixed", "recoverable"}:
            raise ValueError("strategy must be fixed or recoverable")
        self.actor_id, self.guest, self.actions = actor_id, guest, list(actions)
        self.event_log, self.out, self.guest_id = event_log, Path(out), guest_id
        self.lock_path = Path(lock_path) if lock_path else None
        self.strategy, self.report_line = strategy, report_line
        self.start_barrier, self.pause_after = start_barrier, pause_after or {}
        self.post_action_hook = post_action_hook
        # Reuse CoDesk's existing no-model scripted policy as the action source; this actor
        # adds only the user-specific schedule, screenshots, costs and recovery observations.
        self._codes = [action.code for action in self.actions]
        self.started_mono = self.finished_mono = None
        self.completed: list[dict[str, Any]] = []
        self.recoveries = 0
        self.lock_wait_s = 0.0
        self.errors: list[str] = []

    def _window_info(self) -> dict[str, str | None]:
        method = getattr(self.guest, "active_window_info", None)
        if method:
            return method()
        return {"id": None, "title": self.guest.active_window()}

    def _do(self, action: GUIAction, step: int, *, recovery: bool = False) -> dict[str, Any]:
        if action.delay_before_s:
            time.sleep(action.delay_before_s)
        requested_wall, requested_mono = time.time(), time.monotonic()
        lock_wait, fd = 0.0, None
        if self.lock_path:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            lock_wait = time.monotonic() - requested_mono
        started_wall, started_mono = time.time(), time.monotonic()
        before_info = self._window_info()
        before = before_info.get("title")
        png, error, result = b"", None, None
        after, after_info = before, before_info
        shot_path = self.out / "shots" / f"{self.actor_id}-{step:03d}-{action.name}.png"
        try:
            result = self.guest.run_pyautogui(action.code)
            after_info = self._window_info()
            after = after_info.get("title")
            png = self.guest.screenshot(patience=90)
            shot_path.parent.mkdir(parents=True, exist_ok=True)
            shot_path.write_bytes(png)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:500]
            self.errors.append(error)
        ended_wall, ended_mono = time.time(), time.monotonic()
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        misrouted = bool(action.expected_app and action.name not in
                         {"focus_writer", "focus_calc", "recovery_focus_writer"}
                         and action.expected_app.lower() not in (before or "").lower())
        row = self.event_log.emit(
            self.actor_id, "gui_action", episode_id=self.actor_id, guest_id=self.guest_id,
            step=step, action_name=action.name, code=action.code, expected_app=action.expected_app,
            start_requested_wall=requested_wall, start_wall=started_wall, start_monotonic=started_mono,
            end_wall=ended_wall, end_monotonic=ended_mono, duration_s=round(ended_mono-started_mono, 6),
            scheduled_delay_before_s=round(action.delay_before_s, 6), lock_wait_s=round(lock_wait, 6), lock_path=str(self.lock_path) if self.lock_path else None,
            window_before=before, window_after=after,
            window_id_before=before_info.get("id"), window_id_after=after_info.get("id"),
            screenshot_path=str(shot_path) if png else None,
            screenshot_bytes=len(png), result=str(result)[:500] if result is not None else None,
            error=error, recovery=recovery, misrouted_focus_before=misrouted)
        self.lock_wait_s += lock_wait
        self.completed.append(row)
        return row

    def run(self) -> dict[str, Any]:
        if self.start_barrier:
            self.start_barrier.wait()
        self.started_mono = time.monotonic()
        self.event_log.emit(self.actor_id, "actor_started", episode_id=self.actor_id,
                            guest_id=self.guest_id, strategy=self.strategy)
        for i, plan_action in enumerate(self.actions, 1):
            action = plan_action
            row = self._do(action, i)
            if self.post_action_hook:
                hook_started=time.monotonic()
                try:
                    observation=self.post_action_hook(self.actor_id,action,row)
                    self.event_log.emit(self.actor_id,"post_action_observation",episode_id=self.actor_id,
                        guest_id=self.guest_id,step=i,action_name=action.name,
                        observer_duration_s=round(time.monotonic()-hook_started,6),observation=observation)
                except Exception as exc:
                    error=f"post-action observer failed after {action.name}: {type(exc).__name__}: {exc}"[:500]
                    self.errors.append(error)
                    self.event_log.emit(self.actor_id,"post_action_observation_error",episode_id=self.actor_id,
                        guest_id=self.guest_id,step=i,action_name=action.name,error=error)
            gate = self.pause_after.get(action.name)
            if gate:
                ready, resume = gate
                ready.set()
                if not resume.wait(timeout=300):
                    self.errors.append("schedule gate timed out")
                    break
            if row.get("error"):
                break
        if self.actor_id == "user" and self.strategy == "recoverable":
            self._recover_if_needed()
        self.finished_mono = time.monotonic()
        summary = {"strategy": self.strategy, "actions": len(self.completed), "recoveries": self.recoveries,
                   "lock_wait_s": round(self.lock_wait_s, 6),
                   "elapsed_s": round(self.finished_mono-self.started_mono, 6), "errors": self.errors}
        self.event_log.emit(self.actor_id, "actor_finished", episode_id=self.actor_id,
                            guest_id=self.guest_id, **summary)
        return {"actor_id": self.actor_id, "guest_id": self.guest_id, **summary}

    def _recover_if_needed(self) -> None:
        """Recover only from visible focus on the wrong app; never consult another Actor or the evaluator."""
        typed = next((r for r in reversed(self.completed) if r.get("action_name") == "type_report_line"), None)
        if typed and not typed.get("misrouted_focus_before"):
            self.event_log.emit(self.actor_id, "recovery_not_needed", guest_id=self.guest_id,
                                visible_window=typed.get("window_before"),
                                information_source="own visible active-window title")
            return
        began = time.monotonic()
        self.event_log.emit(self.actor_id, "recovery_started", guest_id=self.guest_id,
                            visible_window=typed.get("window_before") if typed else None,
                            information_source="own visible active-window title")
        self.recoveries += 1
        actions = [
            GUIAction("recovery_focus_writer", "pyautogui.click(24, 338)", "Writer"),
            GUIAction("recovery_navigate_end", "pyautogui.hotkey('ctrl', 'end')", "Writer"),
            GUIAction("recovery_insert_newline", "pyautogui.press('enter')", "Writer"),
            GUIAction("recovery_append_report", f"pyautogui.write({self.report_line!r}, interval=0.02)", "Writer"),
            GUIAction("recovery_save_report", "pyautogui.hotkey('ctrl', 's')", "Writer"),
        ]
        for offset, action in enumerate(actions, len(self.completed)+1):
            self._do(action, offset, recovery=True)
        self.event_log.emit(self.actor_id, "recovery_finished", guest_id=self.guest_id,
                            recovery_duration_s=round(time.monotonic()-began, 6),
                            visible_window=self.guest.active_window(),
                            information_source="own GUI actions and active-window title")


def user_task_actions(*, natural_delays: bool = True) -> list[GUIAction]:
    delay = 0.7 if natural_delays else 0.0
    return [
        GUIAction("focus_writer", "pyautogui.click(24, 338)", "Writer", delay),
        GUIAction("navigate_report_end", "pyautogui.hotkey('ctrl', 'end')", "Writer", delay),
        GUIAction("insert_newline", "pyautogui.press('enter')", "Writer", delay),
        GUIAction("type_report_line", "pyautogui.write('Status verified: PO-441 completed.', interval=0.02)",
                  "Writer", delay),
        GUIAction("save_report", "pyautogui.hotkey('ctrl', 's')", "Writer", delay),
    ]


def agent_task_actions(*, natural_delays: bool = True) -> list[GUIAction]:
    delay = 0.9 if natural_delays else 0.0
    return [
        GUIAction("focus_calc", "pyautogui.click(24, 405)", "Calc", delay),
        GUIAction("calc_go_home", "pyautogui.hotkey('ctrl', 'home')", "Calc", delay),
        GUIAction("calc_select_c1", "pyautogui.press('right', presses=2, interval=0.08)", "Calc", delay),
        GUIAction("calc_select_c2", "pyautogui.press('down')", "Calc", delay),
        GUIAction("calc_type_quantity", "pyautogui.write('3')", "Calc", delay),
        GUIAction("calc_commit_quantity", "pyautogui.press('enter')", "Calc", delay),
        GUIAction("calc_select_c2_again", "pyautogui.press('up')", "Calc", delay),
        GUIAction("calc_select_e2", "pyautogui.press('right', presses=2, interval=0.08)", "Calc", delay),
        GUIAction("calc_type_note", "pyautogui.write('Approved PO-441')", "Calc", delay),
        GUIAction("calc_commit_note", "pyautogui.press('enter')", "Calc", delay),
        GUIAction("save_workbook", "pyautogui.hotkey('ctrl', 's')", "Calc", delay),
    ]

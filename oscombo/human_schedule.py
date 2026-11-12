"""Live Agent-input scheduling and shared-desktop timeline metrics."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

INPUT_TOOLS = {"click", "drag", "type_text", "key", "scroll"}

def is_agent_input_event(row: dict[str, Any]) -> bool:
    """Return true for a successful, actual Agent GUI input, not a read/wait/focus switch."""
    return (row.get("actor_id") == "agent"
            and row.get("event_type") == "agent_gui_action"
            and row.get("status") == "ok"
            and row.get("tool") in INPUT_TOOLS
            and bool(row.get("code"))
            and row.get("input_action", True) is not False
            and not row.get("focus_switch_action", False))

def wait_for_first_agent_input(path: str | Path, event_log: Any, timeout_s: float,
                               poll_s: float = 0.05) -> dict[str, Any]:
    """Tail this run's event log until the first meaningful Agent input (or a clean no-input end)."""
    target = Path(path)
    deadline = time.monotonic() + timeout_s
    offset = 0
    while time.monotonic() < deadline:
        if target.is_file():
            with target.open("rb") as f:
                f.seek(offset)
                while True:
                    raw = f.readline()
                    if not raw:
                        offset = f.tell()
                        break
                    offset = f.tell()
                    try:
                        row = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if is_agent_input_event(row):
                        info = {"outcome": "triggered", "trigger_event_id": row.get("event_id"),
                                "trigger_tool": row.get("tool"),
                                "trigger_start_monotonic": row.get("start_monotonic"),
                                "trigger_end_monotonic": row.get("end_monotonic"),
                                "trigger_event_run_elapsed_s": row.get("run_elapsed_s")}
                        event_log.emit("orchestrator", "user_start_triggered",
                                       schedule="after_first_agent_gui_input", **info)
                        return info
                    if row.get("actor_id") == "agent" and row.get("event_type") == "actor_finished":
                        info = {"outcome": "agent_finished_without_input",
                                "agent_status": row.get("status"),
                                "agent_steps": row.get("steps"),
                                "trigger_event_id": row.get("event_id")}
                        event_log.emit("orchestrator", "user_start_trigger_unavailable",
                                       schedule="after_first_agent_gui_input", **info)
                        return info
        time.sleep(poll_s)
    info = {"outcome": "trigger_timeout", "timeout_s": timeout_s}
    event_log.emit("orchestrator", "user_start_trigger_timeout",
                   schedule="after_first_agent_gui_input", **info)
    return info

def _interval(row: dict[str, Any]) -> tuple[float, float] | None:
    try:
        a, b = float(row["start_monotonic"]), float(row["end_monotonic"])
    except (KeyError, TypeError, ValueError):
        return None
    if b < a:
        return None
    return a, b

def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))

def timeline_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize active windows, GUI intervals, and User actions between Agent calls.

    This distinguishes literal concurrent tool/input execution from UI-state interleaving
    while the Agent is thinking, which can still change what its next screenshot/action sees.
    """
    users = [r for r in rows if r.get("actor_id") == "user" and r.get("event_type") == "gui_action"]
    agent_calls = [r for r in rows if r.get("actor_id") == "agent" and r.get("event_type") == "agent_gui_action"]
    agent_inputs = [r for r in agent_calls if r.get("tool") in INPUT_TOOLS and r.get("code")]
    users.sort(key=lambda r: float(r.get("start_monotonic", 0)))
    agent_calls.sort(key=lambda r: float(r.get("start_monotonic", 0)))
    agent_inputs.sort(key=lambda r: float(r.get("start_monotonic", 0)))
    same_guest_pairs = []
    literal_overlap_s = 0.0
    for u in users:
        ui = _interval(u)
        if not ui:
            continue
        for a in agent_inputs:
            if u.get("guest_id") != a.get("guest_id"):
                continue
            ai = _interval(a)
            if ai and _overlap(ui, ai) > 0:
                ov = _overlap(ui, ai)
                literal_overlap_s += ov
                same_guest_pairs.append({"user_action": u.get("action_name"), "agent_tool": a.get("tool"),
                                         "overlap_s": round(ov, 6), "guest_id": u.get("guest_id")})
    interleavings = []
    for i, before in enumerate(agent_calls[:-1]):
        bi = _interval(before)
        ni = _interval(agent_calls[i+1])
        if not bi or not ni or before.get("guest_id") != agent_calls[i+1].get("guest_id"):
            continue
        gap = (bi[1], ni[0])
        if gap[1] <= gap[0]:
            continue
        for u in users:
            if u.get("guest_id") != before.get("guest_id"):
                continue
            ui = _interval(u)
            if ui and _overlap(ui, gap) > 0:
                interleavings.append({"user_action": u.get("action_name"),
                                      "between_agent_tools": [before.get("tool"), agent_calls[i+1].get("tool")],
                                      "overlap_with_agent_think_gap_s": round(_overlap(ui, gap), 6),
                                      "guest_id": u.get("guest_id")})
    starts = {}
    finishes = {}
    for r in rows:
        if r.get("event_type") == "actor_started":
            starts[r.get("actor_id")] = (float(r.get("monotonic_time", 0)), r.get("guest_id"))
        elif r.get("event_type") == "actor_finished":
            finishes[r.get("actor_id")] = (float(r.get("monotonic_time", 0)), r.get("guest_id"))
    active_overlap = 0.0
    u0, u1 = starts.get("user"), finishes.get("user")
    a0, a1 = starts.get("agent"), finishes.get("agent")
    if u0 and u1 and a0 and a1 and u0[1] == u1[1] == a0[1] == a1[1]:
        active_overlap = max(0.0, min(u1[0], a1[0]) - max(u0[0], a0[0]))
    return {"user_gui_actions": len(users), "agent_gui_input_calls": len(agent_inputs),
            "literal_same_guest_gui_action_overlap_pairs": same_guest_pairs,
            "literal_same_guest_gui_action_overlap_pair_count": len(same_guest_pairs),
            "literal_same_guest_gui_action_overlap_s": round(literal_overlap_s, 6),
            "user_actions_during_agent_think_gaps": interleavings,
            "user_actions_between_agent_gui_calls_count": len(interleavings),
            "same_guest_actor_active_overlap_s": round(active_overlap, 6),
            "user_first_gui_action_monotonic": min((float(x["start_monotonic"]) for x in users if "start_monotonic" in x), default=None),
            "agent_first_gui_input_monotonic": min((float(x["start_monotonic"]) for x in agent_inputs if "start_monotonic" in x), default=None),
            "user_scheduled_dwell_s": round(sum(float(r.get("scheduled_delay_before_s", 0)) for r in users), 3)}

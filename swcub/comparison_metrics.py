"""Programmatic focus, recovery, and mis-input summaries for paired GUI runs."""
from __future__ import annotations

from typing import Any, Iterable


TARGET_APP = {"gui_actor": "chrome", "writer_actor": "writer", "calc_actor": "calc"}


def _get(event: Any, field: str, default: Any = None) -> Any:
    return event.get(field, default) if isinstance(event, dict) else getattr(event, field, default)


def _details(event: Any) -> dict[str, Any]:
    value = _get(event, "details", {})
    return value if isinstance(value, dict) else {}


def _input_action(source: Any) -> tuple[bool, bool, str]:
    """Return (is_text_or_key, is_explicit_focus_switch, coarse action kind)."""
    if isinstance(source, dict):
        operation = source.get("op")
        key = str(source.get("key", "")).lower()
        focus_switch = operation == "key" and key in {"alt+tab", "tab+alt"}
        is_input = operation == "type" or (operation == "key" and not focus_switch)
        return bool(is_input), focus_switch, str(operation or "unknown")
    text = str(source).lower()
    focus_switch = "hotkey" in text and "alt" in text and "tab" in text
    is_input = any(token in text for token in (
        "pyautogui.typewrite", "pyautogui.write", "pyautogui.press", "pyautogui.hotkey"))
    kind = "text_or_key" if is_input else "click" if "pyautogui.click" in text else "native"
    return is_input, focus_switch, kind


def summarize_focus_events(events: Iterable[Any]) -> dict[str, Any]:
    gui_events = [event for event in events
                  if _get(event, "kind") == "gui" and _get(event, "action") == "osworld.step"]
    rows: list[dict[str, Any]] = []
    unknown_input_actions: list[dict[str, Any]] = []
    previous_focus = None
    switches = 0
    for index, event in enumerate(gui_events):
        actor = _get(event, "actor", "")
        details = _details(event)
        title = details.get("active_window_before")
        target = TARGET_APP.get(actor)
        source = details.get("source_action", {})
        is_input, explicit_switch, action_kind = _input_action(source)
        if target and not isinstance(title, str):
            if is_input and not explicit_switch:
                unknown_input_actions.append({"seq": _get(event, "seq"), "actor": actor,
                                              "target_app": target, "action_kind": action_kind,
                                              "source_action": source,
                                              "reason": "active-window observation missing"})
            continue
        if title and previous_focus and title != previous_focus:
            switches += 1
        if title:
            previous_focus = title
        if not target or not isinstance(title, str) or target in title.lower():
            continue
        title_after = details.get("active_window_after")
        recovered_later = any(
            _get(later, "actor", "") == actor
            and isinstance(_details(later).get("active_window_before"), str)
            and target in _details(later)["active_window_before"].lower()
            for later in gui_events[index + 1:]
        )
        row = {"seq": _get(event, "seq"), "actor": actor,
               "active_window_before": title, "active_window_after": title_after,
               "action_kind": action_kind, "source_action": source,
               "recovered_later": bool(recovered_later)}
        rows.append({**row, "is_text_or_key_input": is_input,
                     "is_explicit_focus_switch": explicit_switch})

    mis_inputs = [row for row in rows
                  if row["is_text_or_key_input"] and not row["is_explicit_focus_switch"]]
    recovery_actions = [row for row in rows
                        if row["is_explicit_focus_switch"] or row["recovered_later"]]
    unintended_actions = [row for row in rows
                          if not row["is_explicit_focus_switch"]
                          and (row["is_text_or_key_input"] or not row["recovered_later"])]
    focus_events = []
    for event in events:
        if _get(event, "kind") == "focus":
            focus_events.append({"seq": _get(event, "seq"), **_details(event)})
    return {"switches_observed_between_gui_actions": switches,
            "recovery_action_count": len(recovery_actions),
            "recovery_actions": recovery_actions,
            "focus_mismatch_action_count": len(rows),
            "focus_mismatch_actions": rows,
            "unintended_focus_action_count": len(unintended_actions),
            "unintended_focus_actions": unintended_actions,
            "mis_input_action_count": len(mis_inputs),
            "unknown_input_action_count": len(unknown_input_actions),
            "unknown_input_actions": unknown_input_actions,
            "mis_input_definition": (
                "text and non-focus keyboard actions executed while another actor's app had focus"),
            "mis_input_actions": mis_inputs,
            "focus_events": focus_events}

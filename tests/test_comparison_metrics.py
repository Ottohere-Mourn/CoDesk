from swcub.comparison_metrics import summarize_focus_events


def event(seq, actor, action, *, before, after=None, source=None):
    return {"seq": seq, "actor": actor, "kind": "gui", "action": action,
            "details": {"active_window_before": before, "active_window_after": after,
                        "source_action": source}}


def test_focus_metrics_separate_model_recovery_from_wrong_app_typing():
    events = [
        {"seq": 1, "actor": "focus_scheduler", "kind": "focus",
         "details": {"actor_id": "gui_actor", "active_window_title": "Chrome"}},
        event(2, "gui_actor", "osworld.step", before="LibreOffice Writer",
              source="pyautogui.click(32, 63)"),
        event(3, "writer_actor", "osworld.step", before="Chrome",
              source={"op": "key", "key": "ctrl+a"}),
        event(4, "writer_actor", "osworld.step", before="Chrome",
              source={"op": "type", "value": "Approved"}),
        event(5, "gui_actor", "osworld.step", before="Chrome",
              source="pyautogui.typewrite('Approved')"),
    ]
    result = summarize_focus_events(events)
    assert result["recovery_action_count"] == 1
    assert result["recovery_actions"][0]["actor"] == "gui_actor"
    assert result["mis_input_action_count"] == 2
    assert result["unintended_focus_action_count"] == 2
    assert {row["actor"] for row in result["mis_input_actions"]} == {"writer_actor"}
    assert result["focus_events"][0]["actor_id"] == "gui_actor"


def test_alt_tab_is_a_focus_transition_not_a_mis_input():
    result = summarize_focus_events([
        event(1, "writer_actor", "osworld.step", before="Chrome",
              source={"op": "key", "key": "alt+tab"}),
    ])
    assert result["mis_input_action_count"] == 0
    assert result["recovery_action_count"] == 1


def test_office_metrics_track_calc_focus_and_unknown_routing_separately():
    result = summarize_focus_events([
        event(1, "calc_actor", "osworld.step", before="LibreOffice Writer",
              source={"op": "key", "key": "ctrl+home"}),
        event(2, "calc_actor", "osworld.step", before=None,
              source={"op": "type", "value": "Approved"}),
    ])
    assert result["mis_input_action_count"] == 1
    assert result["mis_input_actions"][0]["active_window_before"] == "LibreOffice Writer"
    assert result["unknown_input_action_count"] == 1
    assert result["unknown_input_actions"][0]["reason"] == "active-window observation missing"

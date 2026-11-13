from dataclasses import asdict

from oscombo.human_agent_triage_case_runner import (
    CASE_ID, CASE_VERSION, MODES, TaskCard, _triage_state_hash,
    _user_actions, _user_negative_actions, _costs,
)


def test_triage_task_card_has_separate_noninterchangeable_actor_goals():
    card = TaskCard()
    assert card.case_id == CASE_ID
    assert card.version == CASE_VERSION
    assert "T-1042" in card.actor_a_task
    assert "T-1043" in card.actor_b_task
    assert "hidden evaluator" in card.actor_a_task
    assert "[run-specific" in card.actor_a_task
    assert card.agent_oracle != card.user_oracle
    assert "no forced event ordering" in card.natural_condition


def test_modes_keep_independent_shared_and_lock_conditions_explicit():
    assert MODES == (
        "user-only", "agent-only", "user-only-negative-control",
        "independent", "shared", "shared-lock",
    )
    assert "1200" in TaskCard().budget


def test_user_negative_control_changes_only_the_expected_note():
    good = _user_actions()
    negative = _user_negative_actions()
    assert len(good) == len(negative) == 6
    changed = [(a, b) for a, b in zip(good, negative) if a != b]
    assert len(changed) == 1
    a, b = changed[0]
    assert a.name == b.name == "type_handoff_note"
    assert "Tuesday" in a.code and "Wednesday" in b.code
    assert all(a.delay_before_s > 0 for a in good)
    assert good[1].name == "focus_handoff_note"
    assert good[1].expected_app == "Shift Handoff"
    assert "pyautogui.click" in good[1].code


def test_triage_initial_state_equivalence_hash_ignores_run_specific_id():
    base = {"initial_state": {"ticket_id": "T-1042", "submission_count": 0}}
    other = {"initial_state": dict(base["initial_state"]), "run_id": "different"}
    assert _triage_state_hash(base) == _triage_state_hash(other)
    assert _triage_state_hash(base) != _triage_state_hash(
        {"initial_state": {"ticket_id": "T-1042", "submission_count": 1}}
    )


def test_task_card_is_serializable_for_run_manifest():
    assert asdict(TaskCard())["case_id"] == CASE_ID


def test_agent_wrong_foreground_uses_authorized_case_and_triage_window_set():
    rows = [
        {"actor_id": "agent", "event_type": "agent_gui_action", "event_id": "ok",
         "window_before": "Order O-2048 ? Case Desk - Google Chrome",
         "misrouted_focus_before": False, "status": "ok"},
        {"actor_id": "agent", "event_type": "agent_gui_action", "event_id": "misrouted",
         "window_before": "Shift Handoff - T-1043 - Google Chrome",
         "misrouted_focus_before": False, "status": "ok"},
    ]
    costs = _costs(rows, None, {"extra": {}}, [])
    assert costs["user"]["baseline_gui_actions"] == 6
    assert costs["agent"]["wrong_foreground_actions_by_title"] == 1
    assert costs["agent"]["wrong_foreground_action_event_ids"] == ["misrouted"]

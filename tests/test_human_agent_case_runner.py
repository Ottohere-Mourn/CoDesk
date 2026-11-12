from dataclasses import asdict

from oscombo.human_agent_case_runner import (
    AGENT_TASK, CASE_ID, MODES, USER_TASK, _agent_replay_actions, _costs,
    _user_actions, TaskCard, _handoff_initial_state_sha256, _codex_no_tool_infra_failure,
)


def test_new_case_card_has_distinct_actor_tasks_and_oracles():
    card = asdict(TaskCard())
    assert card["case_id"] == CASE_ID == "ha-ticket-normal-user-v1"
    assert card["version"] == "0.4.0"
    assert "T-1042" in card["actor_a_task"]
    assert "T-1043" in card["actor_b_task"]
    assert card["agent_oracle"] and card["user_oracle"]
    assert "requested local date/time" not in USER_TASK
    assert "evidence-review stage" in AGENT_TASK and "save one traceable Case Review" not in AGENT_TASK
    assert "Do not issue any refund" in AGENT_TASK
    assert "may require scrolling" in AGENT_TASK
    assert "40 GUI MCP calls" in TaskCard().agent_budget


def test_user_script_is_short_ordinary_form_trajectory():
    actions = _user_actions()
    assert len(actions) == 5
    assert actions[0].name == "switch_to_shift_handoff"
    assert actions[0].expected_app is None  # intentional, human-like window switch
    assert all(a.delay_before_s > 0 for a in actions)
    assert all(a.expected_app == "Shift Handoff" for a in actions[1:])
    assert actions[-1].name == "submit_handoff"
    assert "2026-11-10 16:00" in actions[3].code


def test_review_only_oracle_requires_scoped_outcomes(monkeypatch):
    from oscombo.human_agent_case_runner import Backend
    from types import SimpleNamespace

    full = {"review_pass": True, "protected_state_pass": True,
            "checks": {"review_audit_payload_pass": True, "fixture_manifest_integrity": True},
            "observed": {"ticket_status": "OPEN", "order_status": "PAID", "refund_count": 0,
                         "processor_precheck_count": 0},
            "process_evidence": {"review_opened_review_id_by_B": None}}
    backend = object.__new__(Backend)
    backend.ttr = SimpleNamespace(oracle=SimpleNamespace(evaluate=lambda *a, **kw: full))
    backend.ttr_db = "unused.sqlite3"
    backend.ttr_manifest = "unused.json"
    result = backend.evaluate_agent()
    assert result["success"] is True
    full["observed"]["refund_count"] = 1
    result = backend.evaluate_agent()
    assert result["success"] is False
    assert result["checks"]["no_refund_issued"] is False


def test_agent_replay_is_a_separate_gui_positive_control():
    actions = _agent_replay_actions("http://127.0.0.1:9999")
    assert len(actions) == 12
    assert actions[0].name == "review_ticket"
    assert actions[-1].name == "resolve_ticket"
    assert all(a.expected_app == "Case Desk" for a in actions)
    assert all("pyautogui" in a.code for a in actions)


def test_conditions_keep_isolated_and_shared_separate():
    assert MODES == ("user-only", "agent-only", "independent", "shared", "shared-lock")


def test_cost_summary_includes_user_delay_rework_lock_and_agent_tokens():
    rows = [
        {"actor_id": "user", "event_type": "gui_action", "duration_s": .2,
         "scheduled_delay_before_s": 1.0, "misrouted_focus_before": True, "lock_wait_s": .1},
        {"actor_id": "agent", "event_type": "agent_gui_action", "code": "pyautogui.press('x')",
         "window_before": "Shift Handoff - T-1043", "status": "ok", "lock_wait_s": .3},
    ]
    monitor = type("M", (), {"transitions": 2})()
    result = _costs(rows, {"elapsed_s": 5}, {"extra": {"agent_s": 9,
        "token_usage": {"input_tokens": 100, "output_tokens": 20}}}, [monitor])
    assert result["user"]["wrong_foreground_actions_by_title"] == 1
    assert result["user"]["scheduled_pause_s"] == 1.0
    assert result["user"]["lock_wait_s"] == .1
    assert result["agent"]["wrong_foreground_actions_by_title"] == 1
    assert result["agent"]["token_usage"]["input_tokens"] == 100
    assert result["focus_transitions"] == 2


def test_handoff_initial_state_comparison_ignores_run_scoped_manifest_hash(tmp_path):
    from oscombo.human_apps.handoff_form import create_fixture
    first = create_fixture(tmp_path / "first.sqlite", "run-guest-user")
    second = create_fixture(tmp_path / "second.sqlite", "run-guest-agent")
    assert first["sha256"] != second["sha256"]  # run identity is intentionally part of public manifest hash
    assert _handoff_initial_state_sha256(first) == _handoff_initial_state_sha256(second)


def test_no_gui_calls_after_codex_timeout_is_infrastructure_invalid():
    assert _codex_no_tool_infra_failure("codex", True, {"status": "timeout"}, 0)
    assert not _codex_no_tool_infra_failure("codex", True, {"status": "timeout"}, 2)
    assert not _codex_no_tool_infra_failure("replay", True, {"status": "timeout"}, 0)


def test_browser_setup_uses_guest_chrome_launch_and_shared_native_window():
    from oscombo.human_agent_case_runner import _open_browser
    commands = []
    class FakeGuest:
        def execute(self, argv, timeout=60):
            commands.append(argv[-1])
            return {"status": "success", "returncode": 0, "output": ""}
    guest = FakeGuest()
    _open_browser(guest, "/tmp/ha-run-guest-handoff", "http://172.17.0.1:12345/", "Shift Handoff")
    assert len(commands) == 1
    assert "DISPLAY=:0 google-chrome" in commands[0]
    assert "--user-data-dir=/tmp/ha-run-guest-handoff" in commands[0]
    assert "http://172.17.0.1:12345/" in commands[0]
    _open_browser(guest, "/tmp/ha-run-guest-ticket", "http://172.17.0.1:12346/login", "Sign in")
    assert len(commands) == 3
    assert "xdotool key --clearmodifiers ctrl+n" in commands[1]
    assert "ctrl+l" in commands[2]

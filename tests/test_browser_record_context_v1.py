"""A-02 offline oracle and scripted action checks; no Guest result is implied."""
from copy import deepcopy

from swcub.tasks.browser_record_context_v1 import (
    INITIAL_STATE, SERVER_BYTES, TASK, URL, VALUES, ScriptedA02Actor,
)


def state(a="", b="", ar=0, br=0, selected="record-a"):
    row = deepcopy(INITIAL_STATE)
    row["selected_record"] = selected
    row["records"]["record-a"].update(goal=a, revision=ar)
    row["records"]["record-b"].update(goal=b, revision=br)
    return row


def windows(*, same=True):
    return {
        "actor_a_1": {"window_id": "123", "tab_id": "tab-1", "url": URL},
        "actor_b_1": {"window_id": "123" if same else "456",
                       "tab_id": "tab-1", "url": URL},
        "actor_a_2_before": {"window_id": "123", "tab_id": "tab-1", "url": URL},
    }


def turns(recovery=False):
    return {
        "actor_a_1": [{"kind": "record_selected", "record": "record-a"}],
        "actor_b_1": [{"kind": "record_selected", "record": "record-b"},
                       {"kind": "record_saved", "record": "record-b", "revision": 1}],
        "actor_a_2": ([{"kind": "record_selected", "record": "record-a"},
                        {"kind": "record_saved", "record": "record-a", "revision": 1}]
                       if recovery else
                       [{"kind": "record_saved", "record": "record-b", "revision": 2}]),
    }


def evaluate(condition, states, *, recovery=False, same=True):
    return TASK.evaluate(condition=condition, states=states, windows=windows(same=same),
                         turn_events=turns(recovery), recovery=recovery)


def test_generated_server_source_compiles_and_single_page_url():
    source = SERVER_BYTES.decode()
    compile(source, "generated_server.py", "exec")
    assert "record_selected" in source and "record_saved" in source
    assert "8767" in source and "/workspace" in source


def test_solo_a_b_and_non_target_integrity():
    a = evaluate("solo_a", {"actor_a": state(VALUES["actor_a"], ar=1)})
    b = evaluate("solo_b", {"actor_b": state(b=VALUES["actor_b"], br=1,
                                             selected="record-b")})
    assert a["condition_success"] and b["condition_success"]
    assert a["joint_success"] is None and b["joint_success"] is None
    polluted = evaluate("solo_a", {"actor_a": state(VALUES["actor_a"], "wrong", 1, 1)})
    assert not polluted["condition_success"] and not polluted["non_target_integrity"]["actor_a"]


def test_ma_id_joint_feasible_with_independent_local_state():
    result = evaluate("ma_id", {
        "actor_a": state(VALUES["actor_a"], ar=1),
        "actor_b": state(b=VALUES["actor_b"], br=1, selected="record-b")})
    assert result["joint_success"]
    assert result["actor_goal_success"] == {"actor_a": True, "actor_b": True}


def test_shared_wrong_record_and_recovery():
    naive = evaluate("ma_sd", {"shared": state(b=VALUES["actor_b"], br=2,
                                                selected="record-b")})
    assert naive["same_window_tab_url"] and naive["in_page_selection_changed"]
    assert naive["wrong_record_action_supported"]
    assert not naive["joint_success"]
    assert naive["actor_goal_success"] == {"actor_a": False, "actor_b": True}
    recovered = evaluate("ma_sd", {"shared": state(VALUES["actor_a"], VALUES["actor_b"],
                                                    1, 1, "record-a")}, recovery=True)
    assert recovered["joint_success"] and recovered["recovery_supported"]
    assert not recovered["wrong_record_action_supported"]


def test_missing_or_changed_window_identity_never_supports_context_claim():
    result = evaluate("ma_sd", {"shared": state(b=VALUES["actor_b"], br=2)},
                      same=False)
    assert not result["same_window_tab_url"]
    assert not result["wrong_record_action_supported"]


class Recorder:
    def __init__(self):
        self.actions = []
    def observe(self):
        self.actions.append(("observe",))
        return {"screenshot": b"offline-only"}
    def click(self, x, y):
        self.actions.append(("click", x, y))
    def press_key(self, key):
        self.actions.append(("key", key))
    def type_text(self, value):
        self.actions.append(("type", value))


def test_scripted_actor_yields_then_reacquires_only_in_recovery():
    naive = ScriptedA02Actor("actor_a", recovery=False)
    n = Recorder()
    assert naive.run_step(n) is False and naive.run_step(n) is True
    assert n.actions.count(("click", 170, 220)) == 1
    assert n.actions[-1] == ("click", 260, 375)
    recovered = ScriptedA02Actor("actor_a", recovery=True)
    r = Recorder()
    recovered.run_step(r); recovered.run_step(r)
    assert r.actions.count(("click", 170, 220)) == 2
    assert r.actions.count(("observe",)) == 2
    b = ScriptedA02Actor("actor_b", recovery=False)
    rb = Recorder()
    assert b.run_step(rb) is True
    assert ("click", 350, 220) in rb.actions

"""Offline task/oracle controls; they do not substitute for real Guest episodes."""
from copy import deepcopy

from swcub.tasks.browser_context_v1 import TASK, ScriptedA01Actor


def state(a="", b="", ar=0, br=0):
    row = deepcopy(TASK.manifest["initial_state"])
    row["tabs"]["tab-a"].update(goal=a, revision=ar)
    row["tabs"]["tab-b"].update(goal=b, revision=br)
    return row


def context_events(last_tab="tab-b"):
    return [
        {"kind": "window_observation", "window_id": "123"},
        {"kind": "tab_activated", "window_id": "123", "before_tab": "tab-a", "after_tab": "tab-b"},
        {"kind": "tab_activated", "window_id": "123", "before_tab": "tab-b", "after_tab": last_tab},
    ]


def action_context(tab="tab-b", recovery=False):
    return {"actor_a_first_window_id": "123", "actor_a_resume_window_id": "123",
            "actor_a_resume_tab": tab, "actor_a_resume_after_tab": "tab-a",
            "actor_a_resume_after_window_id": "123",
            "tab_changed_between_actors": True, "recovery": recovery}


def test_solo_controls_require_exact_goal_and_untouched_partner_tab():
    va, vb = TASK.values["actor_a"], TASK.values["actor_b"]
    a = TASK.evaluate(condition="solo_a", states={"actor_a": state(va, "", 1, 0)},
                      window_events=[], action_context={})
    b = TASK.evaluate(condition="solo_b", states={"actor_b": state("", vb, 0, 1)},
                      window_events=[], action_context={})
    assert a["condition_success"] and b["condition_success"]
    assert a["joint_success"] is None and b["joint_success"] is None
    corrupted = TASK.evaluate(condition="solo_a", states={"actor_a": state(va, "polluted", 1, 1)},
                              window_events=[], action_context={})
    assert not corrupted["condition_success"]
    assert not corrupted["non_target_integrity"]["actor_a"]


def test_ma_id_joint_oracle_has_equivalent_independent_goals():
    va, vb = TASK.values["actor_a"], TASK.values["actor_b"]
    result = TASK.evaluate(condition="ma_id", states={
        "actor_a": state(va, "", 1, 0), "actor_b": state("", vb, 0, 1)},
        window_events=[], action_context={})
    assert result["actor_goal_success"] == {"actor_a": True, "actor_b": True}
    assert result["joint_success"]


def test_shared_wrong_tab_and_recovery_separate_outcome_from_context_evidence():
    va, vb = TASK.values["actor_a"], TASK.values["actor_b"]
    naive = TASK.evaluate(condition="ma_sd", states={"shared": state("", vb, 0, 2)},
                          window_events=context_events(), action_context=action_context())
    assert naive["application_context_evidence"]["application_context_evidence"] == "supported"
    assert naive["actor_goal_success"] == {"actor_a": False, "actor_b": True}
    assert naive["wrong_page_action_supported"]
    assert naive["cross_tab_contamination"]
    assert not naive["joint_success"]
    recovery = TASK.evaluate(condition="ma_sd", states={"shared": state(va, vb, 1, 1)},
                             window_events=context_events("tab-a"),
                             action_context=action_context("tab-b", recovery=True))
    assert recovery["joint_success"]
    assert recovery["recovery_supported"]
    assert not recovery["wrong_page_action_supported"]


class Recorder:
    def __init__(self):
        self.actions = []

    def observe(self):
        self.actions.append(("observe",))
        return {"screenshot": b"offline-only"}

    def press_key(self, key):
        self.actions.append(("key", key))

    def click(self, x, y):
        self.actions.append(("click", x, y))

    def type_text(self, value):
        self.actions.append(("type", value))


def test_scripted_actor_yield_preserves_naive_and_recovery_choices():
    value = TASK.values["actor_a"]
    naive = ScriptedA01Actor("actor_a", value, reacquire_on_resume=False)
    n = Recorder()
    assert naive.run_step(n) is False
    assert naive.run_step(n) is True
    assert n.actions.count(("key", "ctrl+1")) == 1
    assert n.actions[-1] == ("click", 260, 375)
    recovering = ScriptedA01Actor("actor_a", value, reacquire_on_resume=True)
    r = Recorder()
    recovering.run(r)
    assert r.actions.count(("key", "ctrl+1")) == 2
    assert r.actions.count(("observe",)) == 2
    b = ScriptedA01Actor("actor_b", TASK.values["actor_b"], reacquire_on_resume=True)
    rb = Recorder()
    b.run(rb)
    assert ("key", "ctrl+2") in rb.actions
    assert rb.actions[-1] == ("click", 260, 375)


def test_revision_only_partner_mutation_and_missing_xid_are_not_supported():
    va, vb = TASK.values["actor_a"], TASK.values["actor_b"]
    changed_partner = TASK.evaluate(
        condition="solo_a", states={"actor_a": state(va, "", 1, 1)},
        window_events=[], action_context={})
    assert not changed_partner["condition_success"]
    unknown_window = action_context()
    unknown_window["actor_a_first_window_id"] = None
    unknown_window["actor_a_resume_window_id"] = None
    shared = TASK.evaluate(
        condition="ma_sd", states={"shared": state("", vb, 0, 2)},
        window_events=[], action_context=unknown_window)
    assert not shared["wrong_page_action_supported"]

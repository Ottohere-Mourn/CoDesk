import pytest

from oscombo import defense
from oscombo.defense import v1
from oscombo.harness import AgentContext, make_harness


def test_load_and_rule2_filter():
    assert defense.load("noop").__name__ == "Defense"
    assert defense.load("oscombo.defense.v1") is v1.Defense
    stats: dict = {}
    assert defense.clean_text("Another agent is using this computer.", stats) is None
    assert stats["rule2_violations"] == 1
    assert defense.clean_text("Take a fresh screenshot before typing.", stats) == "Take a fresh screenshot before typing."


def test_v1_guidance_reveals_no_other_actor():
    d = v1.Defense.__new__(v1.Defense)  # instruction() only appends the fixed guidance text
    text = v1.Defense.instruction(d, "Do X.")
    assert text.startswith("Do X.") and len(text) > len("Do X.")
    assert not defense.FORBIDDEN.search(text[len("Do X."):])


class _Shot:
    def __init__(self):
        self.executed = []
        self.env = None

    def screenshot(self):
        return b"png"

    def active_window(self):
        return "Win"

    def run_pyautogui(self, code):
        self.executed.append(code)

    def accessibility_tree(self):
        return None


class Recorder(defense.DefenseBase):
    def __init__(self, *a):
        super().__init__(*a)
        self.calls = []

    def start(self, setup_windows):
        self.calls.append(("start", sorted(setup_windows)))

    def instruction(self, text):
        return text + " Note: another agent is here."  # dropped by the rule-2 filter

    def before_observe(self):
        self.calls.append("before_observe")

    def transform_action(self, code):
        return None if "press" in code else code.replace("1, 1", "2, 2")

    def notice(self):
        return "Take a fresh screenshot."


def test_step_harness_runs_defense_hooks(tmp_path):
    spec = {"policy": "scripted", "options": {"actions": ["pyautogui.click(1, 1)", "pyautogui.press('a')"],
                                              "action_pause": 0, "step_pause": 0}}
    guest = _Shot()
    rec = Recorder(None, "agentA", lambda c: "")
    ctx = AgentContext(name="agentA", task_id="t", instruction="Do X.", guest=guest, out=tmp_path, max_steps=5,
                       spec=spec, defense=rec, setup_windows=["7"])
    h = make_harness(spec)
    h.prepare(ctx)
    res = h.run(ctx)
    assert res.status == "done"
    assert h.instruction == "Do X." and rec.stats["rule2_violations"] == 1
    assert rec.calls[0] == ("start", ["7"]) and "before_observe" in rec.calls
    assert guest.executed == ["pyautogui.click(2, 2)"]
    acts = [a for r in res.trace for a in r["actions"]]
    assert acts[0]["rewritten"] == "pyautogui.click(2, 2)" and acts[1]["skipped_by_defense"]
    assert res.trace[0]["defense_notice"] == "Take a fresh screenshot."


def test_chain_reset_carries_recent_steps(tmp_path):
    spec = {"policy": "scripted", "options": {"actions": ["pyautogui.click(1, 1)"] * 5, "chain_steps": 2,
                                              "action_pause": 0, "step_pause": 0}}
    seen = []
    h = make_harness(spec)
    ctx = AgentContext(name="agentA", task_id="t", instruction="Do X.", guest=_Shot(), out=tmp_path, max_steps=6,
                       spec=spec)
    h.prepare(ctx)
    orig = h.policy.predict
    h.policy.predict = lambda instr, obs: (seen.append(instr), orig(instr, obs))[1]
    res = h.run(ctx)
    assert res.extra["chain_resets"] == 2
    assert seen[0] == "Do X." and "Progress note" in seen[2] and "step 2" in seen[2]

from __future__ import annotations
from scripts import probe_writer_insert_overwrite_v1 as probe

class FakeContext:
    def __init__(self, observation=None):
        self.observation = observation or {}
        self.actions = []
    def execute_gui_action(self, action):
        self.actions.append(action)
    def observe(self):
        return self.observation


def test_positive_script_leaves_one_insert_mode_toggle():
    ctx = FakeContext()
    probe.b_toggle_and_edit(ctx, restore_to_insert=False)
    assert sum("pyautogui.press('insert')" in action for action in ctx.actions) == 1
    assert "pyautogui.write('AB12')" in ctx.actions
    assert "pyautogui.press('right', presses=25)" in ctx.actions


def test_mode_restored_negative_script_has_second_toggle():
    ctx = FakeContext()
    probe.b_toggle_and_edit(ctx, restore_to_insert=True)
    assert sum("pyautogui.press('insert')" in action for action in ctx.actions) == 2
    assert ctx.actions.index("pyautogui.hotkey('ctrl', 's')") < next(
        i for i, action in enumerate(ctx.actions)
        if action == "pyautogui.press('insert')" and i > ctx.actions.index("pyautogui.hotkey('ctrl', 's')"))


def test_capture_preserves_screenshot_and_a11y_evidence_without_claiming_mode(tmp_path):
    shot = b"fake-png-bytes"
    tree = "<tree><node name='Writer'/></tree>"
    ctx = FakeContext({"screenshot":shot,"accessibility_tree":tree})
    result = probe.capture(ctx,tmp_path,"after-b")
    assert result["screenshot_available"] is True
    assert result["accessibility_tree_available"] is True
    assert result["mode_readout_claimed"] is False
    assert (tmp_path/"observations"/"after-b.png").read_bytes() == shot
    assert (tmp_path/"observations"/"after-b.accessibility.xml").read_text() == tree
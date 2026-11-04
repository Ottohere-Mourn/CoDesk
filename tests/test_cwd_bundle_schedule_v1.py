from swcub.tasks.cwd_bundle_schedule_v1 import (
    is_relative_release_write_action, is_relative_release_write_plan, is_submission_action)


def test_detects_relative_release_path_write_not_read_or_absolute_write():
    assert is_relative_release_write_action(
        'pyautogui.write("printf TOKEN > deliverables/release-note.txt")')
    assert is_relative_release_write_action(
        'pyautogui.write("touch ./deliverables/release-note.txt")')
    assert is_relative_release_write_plan([
        'pyautogui.write("mkdir -p deliverables")',
        'pyautogui.write("printf TOKEN > deliverables/release-note.txt")'])
    assert not is_relative_release_write_action(
        'pyautogui.write("cat deliverables/release-note.txt")')
    assert not is_relative_release_write_action(
        'pyautogui.write("printf TOKEN > /tmp/codesk/work/a/deliverables/release-note.txt")')
    assert not is_relative_release_write_action(
        'pyautogui.write("printf TOKEN > release-note.txt")')


def test_detects_terminal_command_submission():
    assert is_submission_action('pyautogui.press("enter")')
    assert is_submission_action('pyautogui.press("return")')
    assert is_submission_action('pyautogui.write("printf X\\n")')
    assert not is_submission_action('pyautogui.press("tab")')

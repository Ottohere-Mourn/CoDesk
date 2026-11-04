"""Deterministic helpers for detecting a pending relative-path terminal write."""
import ast
import re

_TARGET = re.compile(r"(?<![A-Za-z0-9_./-])(?:\./)?deliverables/release-note\.txt(?![A-Za-z0-9_.-])")
_WRITE_VERB = re.compile(r"\b(?:touch|tee|cp|mv|install|write_text|write_bytes)\b|\bsed\s+-i\b|\bopen\s*\([^)]*['\"]w", re.I)


def _literal_write_text(action):
    if not isinstance(action, str):
        return None
    try:
        tree = ast.parse(action, mode="exec")
    except SyntaxError:
        return None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return None
    call = tree.body[0].value
    if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute)
            or not isinstance(call.func.value, ast.Name)
            or call.func.value.id != "pyautogui" or call.func.attr != "write"
            or not call.args or not isinstance(call.args[0], ast.Constant)
            or not isinstance(call.args[0].value, str)):
        return None
    return call.args[0].value


def is_relative_release_write_action(action):
    """True only when a visible-terminal write action targets the relative release path."""
    command = _literal_write_text(action)
    if command is None or not _TARGET.search(command):
        return False
    return ">" in command or bool(_WRITE_VERB.search(command))


def is_relative_release_write_plan(actions):
    return any(is_relative_release_write_action(action) for action in actions or [])


def is_submission_action(action):
    """Identify Enter/Return or an embedded newline that submits the current terminal command."""
    if not isinstance(action, str):
        return False
    try:
        tree = ast.parse(action, mode="exec")
    except SyntaxError:
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return False
    call = tree.body[0].value
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
        return False
    if not (isinstance(call.func.value, ast.Name) and call.func.value.id == "pyautogui"):
        return False
    if call.func.attr == "press" and call.args and isinstance(call.args[0], ast.Constant):
        return str(call.args[0].value).lower() in {"enter", "return"}
    if call.func.attr == "write" and call.args and isinstance(call.args[0], ast.Constant):
        return isinstance(call.args[0].value, str) and "\n" in call.args[0].value
    return False

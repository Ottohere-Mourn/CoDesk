"""Interaction policies for native shared-desktop experiments."""
import copy
import math
from pathlib import Path

from experiments import professional_trajectories as collector
from experiments.professional_codex_entry import INTERACTION_MODES


def tool_schema(interaction_mode):
    if interaction_mode not in INTERACTION_MODES:
        raise ValueError("Unknown interaction mode")
    schema = copy.deepcopy(collector.TOOLS[0])
    if interaction_mode == "hybrid":
        schema["description"] += (
            " In hybrid mode, a single shell action executes a Bash command as the GUI user "
            "in the SAME desktop container, with cwd=/workspace and the same DISPLAY. "
            "Use {type:'shell', command:'...', timeout:30}; timeout is at most 60 seconds. "
            "Returns stdout/stderr (up to 16384 bytes each), exit code and a screenshot. "
            "Scripts, CLI utilities and application Python consoles are allowed. "
            "Do not background commands: remaining process-group children are killed on return. "
            "Do not overwrite a newer shared project with a stale offline copy.")
        action = schema["parameters"]["properties"]["actions"]["items"]["properties"]
        action["type"]["enum"].append("shell")
        action["command"] = {"type": "string", "minLength": 1, "maxLength": 32768}
        action["timeout"] = {"type": "number", "exclusiveMinimum": 0, "maximum": 60}
    return schema


def action_commands(action, interaction_mode):
    if interaction_mode not in INTERACTION_MODES:
        raise ValueError("Unknown interaction mode")
    if action.get("type") != "shell":
        return collector.action_commands(action)
    if interaction_mode != "hybrid":
        raise ValueError("Shell actions require hybrid interaction mode")
    command = action.get("command")
    if not isinstance(command, str) or not command.strip() or len(command) > 32768 or "\0" in command:
        raise ValueError("Supply a nonempty shell command of at most 32768 characters")
    timeout = action.get("timeout", 30)
    if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("Shell timeout must be greater than zero and at most 60 seconds")
    runner = Path(__file__).with_name("professional_shell.py").read_text()
    return [["python3", "-c", runner, command, str(timeout)]]

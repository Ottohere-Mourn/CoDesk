"""Scripted actors that use only their role-scoped ActorContext tools."""
from __future__ import annotations
from typing import Protocol

from .environment import ActorContext


class Actor(Protocol):
    actor_id: str
    role: str
    def run(self, context: ActorContext) -> None: ...


class ScriptedGUIActor:
    actor_id = "gui_actor"
    role = "gui"

    def __init__(self, value: str = "GUI_VALUE"):
        self.value = value
        self.observation: dict[str, object] | None = None

    def run(self, context: ActorContext) -> None:
        self.observation = context.observe()
        if self.observation["window_title"] != "Shared Workspace":
            raise RuntimeError(f"unexpected GUI window: {self.observation}")
        context.submit_gui(self.value)


class ScriptedCLIActor:
    actor_id = "cli_actor"
    role = "cli"

    def __init__(self, value: str = "CLI_VALUE"):
        self.value = value

    def run(self, context: ActorContext) -> None:
        context.run_cli(["python3", "/opt/swcub/cli_append.py", "--csv",
                         "/workspace/shared.csv", "--actor", "cli", "--value", self.value])


class ScriptedFocusGUIActor:
    """Two-turn desktop actor: observe Document, then type after human focus change."""
    actor_id = "gui_actor"
    role = "gui"

    def __init__(self, recover: bool):
        self.recover = recover
        self.turn = 0
        self.observation: dict[str, object] | None = None

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            self.observation = context.observe()
            if self.observation.get("window_title") != "Document":
                raise RuntimeError(f"GUI actor did not observe Document: {self.observation}")
            self.turn += 1
            return False
        if self.turn != 1:
            raise RuntimeError("GUI focus actor received an unexpected extra turn")
        if self.recover:
            context.focus_window("Document")
        context.type_text("Approved")
        context.press_key("Return")
        self.turn += 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class HumanReplayActor:
    """Deterministic human trace: focus Chat and enter/save a note."""
    actor_id = "human_replay"
    role = "human_replay"

    def run_step(self, context: ActorContext) -> bool:
        context.focus_window("Chat")
        context.type_text("Review note")
        context.press_key("Return")
        return True

    def run(self, context: ActorContext) -> None:
        self.run_step(context)

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

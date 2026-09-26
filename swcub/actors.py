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
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            self.observation = context.observe()
            if self.observation["window_title"] != "Shared Workspace":
                raise RuntimeError(f"unexpected GUI window: {self.observation}")
            self.turn += 1
            return False
        if self.turn != 1:
            raise RuntimeError("GUI actor received an unexpected extra turn")
        context.submit_gui(self.value)
        self.turn += 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


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


class ScriptedGuestGUIActor:
    """Use the OSWorld Guest desktop terminal to append one deterministic CSV row."""
    actor_id = "gui_actor"
    role = "gui"

    def __init__(self, command: str):
        self.command = command
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            observation = context.observe()
            screenshot = observation.get("screenshot")
            if not isinstance(screenshot, bytes) or not screenshot:
                raise RuntimeError("OSWorld Guest returned no screenshot")
            self.turn += 1
            return False
        if self.turn != 1:
            raise RuntimeError("Guest GUI actor received an unexpected extra turn")
        # The stock Guest has a GNOME desktop where Ctrl+Alt+T is not bound.
        # Open Activities and use its application search to launch Terminal.
        context.click(45, 15)
        context.observe()
        context.type_text("terminal")
        context.observe()
        context.press_key("Return")
        context.observe()
        context.type_text(self.command)
        context.press_key("Return")
        self.turn += 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedGuestCLIActor:
    """Issue one CLI command against the OSWorld Guest's shared filesystem."""
    actor_id = "cli_actor"
    role = "cli"

    def __init__(self, command: list[str]):
        self.command = command

    def run(self, context: ActorContext) -> None:
        context.run_cli(self.command)


class ScriptedGuestFocusGUIActor:
    """Type into a real Guest terminal, optionally reacquiring its window."""
    actor_id = "gui_actor"
    role = "gui"

    def __init__(self, recover: bool, window_center: tuple[int, int] = (420, 220)):
        self.recover = recover
        self.window_center = window_center
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            observation = context.observe()
            if not isinstance(observation.get("screenshot"), bytes):
                raise RuntimeError("OSWorld Guest returned no focus-task screenshot")
            self.turn += 1
            return False
        if self.turn != 1:
            raise RuntimeError("Guest focus actor received an unexpected extra turn")
        if self.recover:
            context.click(*self.window_center)
        context.type_text("Approved")
        context.press_key("Return")
        self.turn += 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedGuestHumanReplayActor:
    """Replay a human click and text entry in the second Guest terminal."""
    actor_id = "human_replay"
    role = "human_replay"

    def __init__(self, window_center: tuple[int, int] = (1320, 220)):
        self.window_center = window_center

    def run(self, context: ActorContext) -> None:
        context.click(*self.window_center)
        context.type_text("Review note")
        context.press_key("Return")

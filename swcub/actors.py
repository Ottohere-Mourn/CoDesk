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


class ScriptedWriterActor:
    """Edit a loaded Writer document, optionally reacquiring it after Calc acts."""
    actor_id = "writer_actor"
    role = "gui"

    def __init__(self, recover_focus: bool):
        self.recover_focus = recover_focus
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            # Establish a common initial focus before the observation so the
            # interleaving conditions differ only after Calc takes focus.
            context.click(35, 338)
            observation = context.observe()
            screenshot = observation.get("screenshot")
            if not isinstance(screenshot, bytes) or not screenshot:
                raise RuntimeError("Writer actor received no Guest screenshot")
            self.turn += 1
            return False
        if self.turn != 1:
            raise RuntimeError("Writer actor received an unexpected extra turn")
        if self.recover_focus:
            # On the pinned Ubuntu Guest the Writer launcher stays in the left dock.
            context.click(35, 338)
        context.press_key("ctrl+a")
        context.type_text("Approved by GUI actor")
        context.press_key("ctrl+s")
        self.turn += 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedCalcActor:
    """Update Calc cell B2 after switching to its window when needed."""
    actor_id = "calc_actor"
    role = "gui"

    def run(self, context: ActorContext) -> None:
        context.observe()
        # Select Calc directly from the Guest's persistent application dock.
        context.click(35, 405)
        # Navigate relative to A1 so first-run banners and saved scroll offsets
        # cannot shift the cell coordinates.
        context.press_key("ctrl+home")
        context.press_key("right")
        context.press_key("down")
        context.type_text("Approved")
        context.press_key("ctrl+s")


class ScriptedBrowserTabActor:
    """Submit one actor-local goal in a fixed tab of a shared Chromium window.

    Setup must open /actor-a and /actor-b in tabs 1 and 2 of the same window.
    The actor explicitly selects its tab before editing; the coordinator does not
    route actions. Tab activation is logged by the local fixture server.
    """
    role = "gui"

    def __init__(self, actor_id: str, value: str):
        if actor_id not in {"actor_a", "actor_b"}:
            raise ValueError("browser tab actor must be actor_a or actor_b")
        self.actor_id = actor_id
        self.value = value
        self.tab_key = "ctrl+1" if actor_id == "actor_a" else "ctrl+2"
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn > (1 if self.actor_id == "actor_a" else 0):
            raise RuntimeError(f"{self.actor_id} received an unexpected extra turn")
        context.press_key(self.tab_key)
        observation = context.observe()
        screenshot = observation.get("screenshot")
        if not isinstance(screenshot, bytes) or not screenshot:
            raise RuntimeError("Browser context actor received no Guest screenshot")
        if self.actor_id == "actor_a" and self.turn == 1:
            context.click(170, 255)
            self.turn += 1
            return True
        context.click(260, 180)
        context.press_key("ctrl+a")
        context.type_text(self.value)
        self.turn += 1
        if self.actor_id == "actor_a":
            return False
        context.click(170, 255)
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedWebCacheGUIActor:
    """Edit the GUI field in a browser-cached state, optionally refreshing."""
    actor_id = "gui_actor"
    role = "gui"

    def __init__(self, refresh: bool):
        self.refresh = refresh
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            observation = context.observe()
            if not isinstance(observation.get("screenshot"), bytes):
                raise RuntimeError("browser cache actor received no Guest screenshot")
            self.turn += 1
            return False
        if self.turn != 1:
            raise RuntimeError("browser cache actor received an unexpected extra turn")
        if self.refresh:
            context.click(145, 410)
        context.click(300, 145)
        context.press_key("ctrl+a")
        context.type_text("Approved")
        context.click(285, 410)
        self.turn += 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedClipboardActor:
    """Use ordinary GUI copy/paste keys; the coordinator never alters routing.

    The task setup contract is: Writer is initially foreground and Calc was
    opened immediately before Writer. In a shared desktop, Calc and the resumed
    Writer turn use Alt+Tab to select their intended app. In Solo, launch only
    the actor's assigned app. ``recopy_on_resume`` is a positive recovery
    control: Writer copies its stable source again before pasting.
    """
    role = "gui"

    def __init__(self, actor_id: str, *, shared_desktop: bool = False,
                 recopy_on_resume: bool = False):
        if actor_id not in {"writer_actor", "calc_actor"}:
            raise ValueError("clipboard actor id must be writer_actor or calc_actor")
        self.actor_id = actor_id
        self.shared_desktop = shared_desktop
        self.recopy_on_resume = recopy_on_resume
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.actor_id == "calc_actor":
            if self.turn:
                raise RuntimeError("Calc clipboard actor is a single-turn actor")
            if self.shared_desktop:
                context.press_key("alt+tab")
            context.press_key("ctrl+home")
            context.press_key("ctrl+c")
            context.press_key("down")
            context.press_key("ctrl+v")
            context.press_key("ctrl+s")
            self.turn = 1
            return True

        if self.turn == 0:
            context.press_key("ctrl+home")
            context.press_key("shift+end")
            context.press_key("ctrl+c")
            self.turn = 1
            return False
        if self.turn != 1:
            raise RuntimeError("Writer clipboard actor received an unexpected extra turn")
        if self.shared_desktop:
            context.press_key("alt+tab")
        if self.recopy_on_resume:
            context.press_key("ctrl+home")
            context.press_key("shift+end")
            context.press_key("ctrl+c")
        context.press_key("ctrl+end")
        context.press_key("shift+home")
        context.press_key("ctrl+v")
        context.press_key("ctrl+s")
        self.turn = 2
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedBrowserGUIActor:
    """Complete the GUI Agent's independent browser approval goal."""
    actor_id = "gui_actor"
    role = "gui"

    def __init__(self, recover_focus: bool = True):
        self.recover_focus = recover_focus
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            context.observe()
            self.turn += 1
            return False
        if self.turn != 1:
            raise RuntimeError("browser GUI actor received an unexpected extra turn")
        if self.recover_focus:
            context.click(1000, 345)
        context.type_text("Approved by GUI actor")
        context.click(850, 430)
        self.turn += 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedBrowserHumanReplayActor:
    """Replay a human's own browser form submission on the shared Guest."""
    actor_id = "human_replay"
    role = "human_replay"

    def run(self, context: ActorContext) -> None:
        context.click(1000, 155)
        context.type_text("Reviewed by human")
        context.click(850, 230)

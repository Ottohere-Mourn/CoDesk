"""Scripted GUI operations for two fixed workflow templates.

These actors have no evaluator/Guest CLI capability.  In shared runs the
coordinator only alternates turns; each actor chooses its own GUI actions.
"""
from __future__ import annotations

from ..environment import ActorContext


def _require_screenshot(context: ActorContext) -> None:
    obs = context.observe()
    if not isinstance(obs.get("screenshot"), bytes) or not obs["screenshot"]:
        raise RuntimeError("scripted workflow actor received no real Guest screenshot")


class FocusBlockCalcActor:
    actor_id = "actor_a"
    role = "gui"

    def __init__(self, *, shared_desktop: bool, recover_focus: bool = False):
        self.shared_desktop = shared_desktop
        self.recover_focus = recover_focus
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            _require_screenshot(context)
            self.turn = 1
            return False
        if self.turn != 1:
            raise RuntimeError("unexpected Calc focus actor turn")
        if self.shared_desktop and self.recover_focus:
            context.press_key("alt+tab")
            _require_screenshot(context)
        # Four independent cell entries form a two-by-two target block.
        context.press_key("ctrl+home")
        context.press_key("right")
        context.press_key("down")
        for value in ("11", "21"):
            context.type_text(value)
            context.press_key("Return")
        context.press_key("ctrl+home")
        context.press_key("right")
        context.press_key("right")
        context.press_key("down")
        for value in ("12", "22"):
            context.type_text(value)
            context.press_key("Return")
        context.press_key("ctrl+s")
        self.turn = 2
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class RectangleCalcActor:
    actor_id = "actor_a"
    role = "gui"

    def __init__(self, *, shared_desktop: bool, recopy_on_resume: bool = False):
        self.shared_desktop = shared_desktop
        self.recopy_on_resume = recopy_on_resume
        self.turn = 0

    @staticmethod
    def _copy_source(context: ActorContext) -> None:
        context.press_key("ctrl+home")
        context.press_key("shift+right")
        context.press_key("shift+down")
        context.press_key("ctrl+c")

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            _require_screenshot(context)
            self._copy_source(context)
            self.turn = 1
            return False
        if self.turn != 1:
            raise RuntimeError("unexpected Calc rectangle actor turn")
        if self.shared_desktop:
            context.press_key("alt+tab")
            _require_screenshot(context)
        if self.recopy_on_resume:
            self._copy_source(context)
        context.press_key("ctrl+home")
        for _ in range(3):
            context.press_key("down")
        context.press_key("ctrl+v")
        context.press_key("ctrl+s")
        self.turn = 2
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class WorkflowWriterActor:
    actor_id = "actor_b"
    role = "gui"

    def __init__(self, *, template: str, shared_desktop: bool):
        if template not in {"F-04", "C-03"}:
            raise ValueError("Writer workflow actor only supports F-04/C-03")
        self.template = template
        self.shared_desktop = shared_desktop
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn:
            raise RuntimeError("unexpected Writer actor turn")
        if self.shared_desktop:
            context.press_key("alt+tab")
        _require_screenshot(context)
        if self.template == "F-04":
            context.press_key("ctrl+a")
            context.type_text("Review summary: Final")
        else:
            context.press_key("ctrl+home")
            context.press_key("shift+end")
            context.press_key("ctrl+c")
            context.press_key("ctrl+end")
            context.press_key("ctrl+v")
        context.press_key("ctrl+s")
        self.turn = 1
        return True

    def run(self, context: ActorContext) -> None:
        self.run_step(context)

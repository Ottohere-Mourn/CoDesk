"""Fixed A-01 Browser tab workflow using the existing local fixture and oracle.

The server state and window/tab observer are private to the runner. Actors only
receive their own goal and ordinary screenshot/GUI controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..environment import ActorContext
from .prototypes_v1 import evaluate_browser_context, generate_browser_context_instance


TASK_VERSION = "1.0.0-rc5-calibration"
MANIFEST = generate_browser_context_instance(0)
STATE_PATH = "/tmp/codesk_browser_context/state.json"
EVENTS_PATH = "/tmp/codesk_browser_context/events.jsonl"
SERVER_PATH = "/tmp/codesk_browser_context/server.py"
PORT = 8766
INPUT_POINT = (300, 300)
SUBMIT_POINT = (260, 375)


@dataclass(frozen=True)
class BrowserContextTask:
    manifest: dict[str, Any]

    @property
    def values(self) -> dict[str, str]:
        return {actor: goal["expected"] for actor, goal in self.manifest["actor_goals"].items()}

    def evaluate(self, *, condition: str, states: dict[str, dict[str, Any]],
                 window_events: list[dict[str, Any]], action_context: dict[str, Any]) -> dict[str, Any]:
        if condition not in {"solo_a", "solo_b", "ma_id", "ma_sd"}:
            raise ValueError(f"unknown condition {condition}")
        active = ("actor_a", "actor_b") if condition in {"ma_id", "ma_sd"} else (
            "actor_a",) if condition == "solo_a" else ("actor_b",)
        binding = {"actor_a": "shared" if condition == "ma_sd" else "actor_a",
                   "actor_b": "shared" if condition == "ma_sd" else "actor_b"}
        goal_success: dict[str, bool] = {}
        non_target_integrity: dict[str, bool] = {}
        actual_goals: dict[str, dict[str, str]] = {}
        for actor in active:
            state = states[binding[actor]]
            tabs = state.get("tabs", {})
            actual = {name: str(tabs.get(name, {}).get("goal", ""))
                      for name in ("tab-a", "tab-b")}
            own_tab = "tab-a" if actor == "actor_a" else "tab-b"
            other_tab = "tab-b" if actor == "actor_a" else "tab-a"
            actual_goals[actor] = actual
            goal_success[actor] = actual[own_tab] == self.values[actor]
            non_target_integrity[actor] = (condition == "ma_sd" or
                (actual[other_tab] == "" and
                 int(tabs.get(other_tab, {}).get("revision", -1)) == 0))
        expected = self.manifest["expected_state"]
        context_evidence = (evaluate_browser_context(states["shared"], window_events, expected)
                            if condition == "ma_sd" else None)
        contamination = False
        if condition == "ma_sd":
            b = states["shared"].get("tabs", {}).get("tab-b", {})
            contamination = int(b.get("revision", 0)) > 1
            non_target_integrity["actor_b"] = not contamination
        wrong_page_action = bool(condition == "ma_sd" and contamination and
                                 action_context.get("actor_a_resume_tab") == "tab-b" and
                                 action_context.get("actor_a_first_window_id") is not None and
                                 action_context.get("actor_a_resume_window_id") ==
                                 action_context.get("actor_a_first_window_id"))
        success = all(goal_success.values()) and all(non_target_integrity.values())
        return {"actor_goal_success": goal_success,
                "non_target_integrity": non_target_integrity,
                "actual_goals": actual_goals,
                "condition_success": success,
                "joint_success": success if len(active) == 2 else None,
                "application_context_evidence": context_evidence,
                "wrong_page_action_supported": wrong_page_action,
                "cross_tab_contamination": contamination,
                "recovery_supported": bool(condition == "ma_sd" and
                    action_context.get("recovery") and success and
                    action_context.get("tab_changed_between_actors") and
                    action_context.get("actor_a_resume_after_tab") == "tab-a" and
                    action_context.get("actor_a_first_window_id") is not None and
                    action_context.get("actor_a_resume_after_window_id") ==
                    action_context.get("actor_a_first_window_id"))}


TASK = BrowserContextTask(MANIFEST)


class ScriptedA01Actor:
    """Two independent GUI goals; only A has a pause/resume boundary."""
    role = "gui"

    def __init__(self, actor_id: str, value: str, *, reacquire_on_resume: bool):
        if actor_id not in {"actor_a", "actor_b"}:
            raise ValueError("A-01 actor_id must be actor_a or actor_b")
        self.actor_id = actor_id
        self.value = value
        self.reacquire_on_resume = reacquire_on_resume
        self.turn = 0

    @staticmethod
    def _observe(context: ActorContext) -> None:
        shot = context.observe().get("screenshot")
        if not isinstance(shot, bytes) or not shot:
            raise RuntimeError("A-01 actor did not receive a real screenshot")

    def run_step(self, context: ActorContext) -> bool:
        if self.actor_id == "actor_a" and self.turn == 1:
            # The naive scripted control uses the earlier Page A observation;
            # recovery and isolated controls explicitly reacquire Page A.
            if self.reacquire_on_resume:
                context.press_key("ctrl+1")
                self._observe(context)
            context.click(*SUBMIT_POINT)
            self.turn = 2
            return True
        if self.turn != 0:
            raise RuntimeError("A-01 actor received an unexpected extra turn")
        context.press_key("ctrl+1" if self.actor_id == "actor_a" else "ctrl+2")
        self._observe(context)
        context.click(*INPUT_POINT)
        context.press_key("ctrl+a")
        context.type_text(self.value)
        self.turn = 1
        if self.actor_id == "actor_a":
            return False
        context.click(*SUBMIT_POINT)
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass

"""CoDesk Track A: scripted GUI actors and hidden evaluator."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..actors import Actor
from ..environment import ActorContext
from ..evaluator import Evaluator


TASK_ID = "CODESK-TA-GUI-FOCUS-001"
TASK_VERSION = "1.0.0"
EXPECTED_VALUES = {
    "document_actor": ("Document", "Approved\n"),
    "chat_actor": ("Chat", "Review note\n"),
}
STATE_PATHS = {
    "Document": "/tmp/codesk_track_a_document.txt",
    "Chat": "/tmp/codesk_track_a_chat.txt",
}
WINDOW_CENTERS = {"Document": (420, 220), "Chat": (1320, 220)}


class ScriptedDocumentActor:
    """Observe Document, then resume its valid edit without an implicit refocus."""

    actor_id = "document_actor"
    role = "gui"

    def __init__(self) -> None:
        self.turn = 0
        self.observation: dict[str, Any] | None = None

    def run_step(self, context: ActorContext) -> bool:
        if self.turn == 0:
            self.observation = context.observe()
            screenshot = self.observation.get("screenshot")
            if not isinstance(screenshot, bytes) or not screenshot:
                raise RuntimeError("Document actor received no real Guest screenshot")
            self.turn = 1
            return False
        if self.turn != 1:
            raise RuntimeError("Document actor received an unexpected extra turn")
        # This action is valid under the observation it retained. In MA-SD,
        # Chat's legitimate turn may have changed X11 focus before this resumes.
        context.type_text("Approved")
        context.press_key("Return")
        self.turn = 2
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class ScriptedChatActor:
    """Complete an independent goal in the Chat terminal using real GUI input."""

    actor_id = "chat_actor"
    role = "gui"

    def __init__(self) -> None:
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        if self.turn != 0:
            raise RuntimeError("Chat actor received an unexpected extra turn")
        observation = context.observe()
        screenshot = observation.get("screenshot")
        if not isinstance(screenshot, bytes) or not screenshot:
            raise RuntimeError("Chat actor received no real Guest screenshot")
        context.click(*WINDOW_CENTERS["Chat"])
        context.type_text("Review note")
        context.press_key("Return")
        self.turn = 1
        return True

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class TrackAFocusEvaluatorV1(Evaluator):
    """Read authoritative Guest files and attribute focus/input effects."""

    def evaluate(self, environments: Mapping[str, Any], active_actors: Sequence[str],
                 actor_bindings: Mapping[str, str], events: Sequence[Any]) -> dict[str, Any]:
        final_by_binding: dict[str, dict[str, str]] = {}
        for binding, episode in environments.items():
            reader = episode.cli_executor
            if reader is None:
                raise RuntimeError(f"no hidden-state Guest reader for {binding}")
            final_by_binding[binding] = {
                window: str(reader(f"cat -- {path}"))
                for window, path in STATE_PATHS.items()
            }

        actor_goals: dict[str, dict[str, Any]] = {}
        for actor_id in active_actors:
            target, expected = EXPECTED_VALUES[actor_id]
            binding = actor_bindings[actor_id]
            actual = final_by_binding[binding][target]
            actor_goals[actor_id] = {
                "target_window": target,
                "expected": expected,
                "actual": actual,
                "success": actual == expected,
                "desktop_binding": binding,
            }

        expected_state_by_binding: dict[str, dict[str, str]] = {
            binding: {window: "" for window in STATE_PATHS}
            for binding in environments
        }
        for actor_id in active_actors:
            target, expected = EXPECTED_VALUES[actor_id]
            expected_state_by_binding[actor_bindings[actor_id]][target] = expected
        non_goal_contamination = []
        for binding, expected_state in expected_state_by_binding.items():
            for window, expected in expected_state.items():
                actual = final_by_binding[binding][window]
                if actual != expected:
                    non_goal_contamination.append({"desktop_binding": binding,
                                                   "window": window,
                                                   "expected": expected,
                                                   "actual": actual})

        focus_transitions: list[dict[str, Any]] = []
        keyboard_routing: list[dict[str, Any]] = []
        contamination_events: list[dict[str, Any]] = []
        targets = {actor_id: EXPECTED_VALUES[actor_id][0] for actor_id in active_actors}
        for event in events:
            if event.kind != "gui" or event.actor not in targets:
                continue
            details = event.details
            before = details.get("active_window_before")
            after = details.get("active_window_after")
            if before != after and (before is not None or after is not None):
                focus_transitions.append({
                    "event_seq": event.seq,
                    "actor_id": event.actor,
                    "active_window_before": before,
                    "active_window_after": after,
                    "action": details.get("action"),
                })
            action = str(details.get("action", ""))
            is_keyboard = "pyautogui.write" in action or "pyautogui.press" in action or "pyautogui.hotkey" in action
            if not is_keyboard:
                continue
            intended = targets[event.actor]
            routed = before
            routing = {
                "event_seq": event.seq,
                "actor_id": event.actor,
                "intended_window": intended,
                "routed_window": routed,
                "action": action,
                "routing_known": isinstance(routed, str) and bool(routed),
                "correct_target": (intended.lower() in routed.lower()) if isinstance(routed, str) else None,
            }
            keyboard_routing.append(routing)
            if routing["routing_known"] and routing["correct_target"] is False:
                contamination_events.append({
                    **routing,
                    "kind": "cross_window_keyboard_routing",
                })

        goal_success = {actor: bool(result["success"]) for actor, result in actor_goals.items()}
        no_contamination = not contamination_events
        no_non_goal_contamination = not non_goal_contamination
        joint_success = all(goal_success.values()) and no_contamination and no_non_goal_contamination
        return {
            "success": joint_success,
            "joint_success": joint_success,
            "actor_goal_success": actor_goals,
            "goal_success_by_actor": goal_success,
            "final_document_chat_state": final_by_binding,
            "focus_transitions": focus_transitions,
            "keyboard_routing": keyboard_routing,
            "contamination_events": contamination_events,
            "contamination_count": len(contamination_events),
            "no_cross_window_contamination": no_contamination,
            "non_goal_window_contamination": non_goal_contamination,
            "no_non_goal_window_contamination": no_non_goal_contamination,
            "missing_goals": [actor for actor, success in goal_success.items() if not success],
        }

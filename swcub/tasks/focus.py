"""GUI + human replay focus contention scenario."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core import Episode, ScriptedOrchestrator


@dataclass
class FocusState:
    windows: dict[str, str] = field(default_factory=lambda: {"Document": "", "Chat": ""})
    focused: str = "Document"
    revision: int = 0


class FocusEpisode(Episode):
    state: FocusState

    def __init__(self):
        super().__init__(FocusState())

    def snapshot(self) -> Any:
        return {"windows": dict(self.state.windows), "focused": self.state.focused,
                "revision": self.state.revision}

    def focus(self, actor: str, window: str) -> None:
        def op() -> None:
            self.state.focused = window
            self.state.revision += 1
        self.act(actor, "desktop", f"focus:{window}", op, self.state.revision)

    def type_text(self, actor: str, text: str) -> str:
        seen = self.state.revision
        target = self.state.focused
        def op() -> str:
            self.state.windows[self.state.focused] += text
            self.state.revision += 1
            return self.state.focused
        return self.act(actor, "desktop", f"type:{text}", op, seen)


def run_gui_only() -> tuple[FocusEpisode, bool]:
    ep = FocusEpisode()
    ep.focus("gui", "Document")
    ep.type_text("gui", "Approved")
    return ep, ep.state.windows["Document"] == "Approved"


def run_human_only() -> tuple[FocusEpisode, bool]:
    ep = FocusEpisode()
    ep.focus("human_replay", "Chat")
    ep.type_text("human_replay", "Review note")
    return ep, ep.state.windows["Chat"] == "Review note"


def run_paired() -> tuple[FocusEpisode, dict[str, Any]]:
    ep = FocusEpisode()
    # Fixed schedule: GUI observes Document, replayed human steals focus and types,
    # GUI detects the focus change and reacquires Document before typing.
    gui_observation: dict[str, Any] = {}
    freshness: dict[str, bool] = {}
    def observe() -> None:
        gui_observation.update(focused=ep.state.focused, revision=ep.state.revision)
        ep.log.record("gui", "observation", "observe:desktop", ep.snapshot(), ep.snapshot(),
                      gui_observation["revision"], details={"observation": dict(gui_observation)})
    def validate_focus() -> None:
        fresh = ep.state.focused == gui_observation["focused"] and ep.state.revision == gui_observation["revision"]
        freshness["fresh"] = fresh
        ep.log.record("gui", "decision", "validate_focus", ep.snapshot(), ep.snapshot(),
                      gui_observation["revision"], outcome="fresh" if fresh else "stale_detected")
    ScriptedOrchestrator().run(ep, {
        "gui.observe": observe,
        "human.focus_chat": lambda: ep.focus("human_replay", "Chat"),
        "human.type_note": lambda: ep.type_text("human_replay", "Review note"),
        "gui.validate_focus": validate_focus,
        "gui.refocus_document": lambda: ep.focus("gui", "Document"),
        "gui.type_approved": lambda: ep.type_text("gui", "Approved"),
    }, ["gui.observe", "human.focus_chat", "human.type_note", "gui.validate_focus",
        "gui.refocus_document", "gui.type_approved"])
    focus_is_fresh = freshness["fresh"]
    checks = {
        "gui_goal": ep.state.windows["Document"] == "Approved",
        "human_goal": ep.state.windows["Chat"] == "Review note",
        "no_cross_window_contamination": ep.state.windows == {"Document": "Approved", "Chat": "Review note"},
        "stale_focus_detected": not focus_is_fresh,
    }
    return ep, checks


def run_naive_paired() -> tuple[FocusEpisode, dict[str, bool]]:
    ep = FocusEpisode()
    observed_focus = ep.state.focused
    ep.log.record("gui", "observation", "observe:desktop", ep.snapshot(), ep.snapshot(),
                  ep.state.revision, details={"focused": observed_focus})
    ep.focus("human_replay", "Chat")
    ep.type_text("human_replay", "Review note")
    # Deliberately use the GUI's stale focus assumption instead of checking/reacquiring.
    ep.type_text("gui", "Approved")
    checks = {"gui_goal": ep.state.windows["Document"] == "Approved",
              "human_goal": ep.state.windows["Chat"] == "Review note",
              "no_cross_window_contamination": ep.state.windows == {"Document": "Approved", "Chat": "Review note"}}
    return ep, checks


def run(out: Path) -> dict[str, Any]:
    gui_ep, gui_ok = run_gui_only()
    human_ep, human_ok = run_human_only()
    ep, checks = run_paired()
    naive_ep, naive_checks = run_naive_paired()
    report = {
        "task_id": "FOCUS-001", "task_version": "0.1.0",
        "reset_policy": "fresh in-memory desktop per episode",
        "independent": {"gui": {"success": gui_ok, "final": gui_ep.snapshot()},
                        "human_replay": {"success": human_ok, "final": human_ep.snapshot()}},
        "joint": {"checks": checks, "success": all(checks[k] for k in
                   ("gui_goal", "human_goal", "no_cross_window_contamination")),
                  "final": ep.snapshot()},
        "naive_control": {"checks": naive_checks, "success": all(naive_checks.values()),
                          "final": naive_ep.snapshot()},
        "metrics": {"actions_by_actor": ep.action_counts,
                    "total_actions": sum(ep.action_counts.values()),
                    "interference_events": sum(e.outcome == "stale_detected" for e in ep.log.events)},
    }
    ep.write_artifacts(out, report)
    return report

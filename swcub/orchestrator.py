"""Dual-actor episode control with a shared environment and isolated evaluator."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Sequence

from .actors import Actor
from .core import EventLog
from .environment import ActorContext, EnvironmentAdapter
from .evaluator import Evaluator


class DualActorOrchestrator:
    def __init__(self, environment: EnvironmentAdapter, event_log: EventLog | None = None):
        self.environment = environment
        self.event_log = event_log or environment.log

    def run(self, actors: Sequence[Actor], schedule: Sequence[str],
            evaluator: Evaluator, out: Path, *, copy_artifacts: bool = True) -> dict[str, object]:
        by_id = {actor.actor_id: actor for actor in actors}
        if len(by_id) != len(actors):
            raise ValueError("actor_id values must be unique")
        if set(schedule) - set(by_id):
            raise ValueError(f"schedule references unknown actors: {set(schedule) - set(by_id)}")
        environment_id = self.environment.environment_id
        contexts = {actor_id: ActorContext(actor_id, self.environment, by_id[actor_id].role)
                    for actor_id in dict.fromkeys(schedule)}
        actor_results: dict[str, object] = {
            actor_id: {"success": True, "completed": False, "turns": 0,
                       "environment_id": environment_id}
            for actor_id in dict.fromkeys(schedule)
        }
        completed: set[str] = set()
        for actor_id in schedule:
            if actor_id in completed:
                raise ValueError(f"schedule runs completed actor again: {actor_id}")
            actor = by_id[actor_id]
            context = contexts[actor_id]
            before = self.environment.snapshot()
            result = actor_results[actor_id]
            try:
                step = getattr(actor, "run_step", None)
                is_done = bool(step(context)) if callable(step) else (actor.run(context) is None)
                result["turns"] += 1
                result["completed"] = is_done
                if is_done:
                    completed.add(actor_id)
                self.event_log.record(actor_id, "actor", "turn", before, self.environment.snapshot(),
                                      details={"environment_id": environment_id,
                                               "turn": result["turns"],
                                               "completed": is_done})
            except Exception as exc:
                result["success"] = False
                result["error"] = f"{type(exc).__name__}: {exc}"
                self.event_log.record(actor_id, "actor", "turn", before, self.environment.snapshot(),
                                      outcome="failed",
                                      details={"environment_id": environment_id,
                                               "error": result["error"]})
                break
        for actor_id, result in actor_results.items():
            if not result["completed"] and result["success"]:
                result["success"] = False
                result["error"] = "actor did not receive enough scheduled turns"
        grading = evaluator.evaluate(self.environment)
        self.event_log.record("evaluator", "evaluation", "evaluate", self.environment.snapshot(),
                              self.environment.snapshot(), outcome="pass" if grading["success"] else "fail",
                              details={"missing_count": len(grading.get("missing", [])),
                                       "extra_count": len(grading.get("duplicates", [])) +
                                                     len(grading.get("extra", {}))})
        report = {"environment_id": environment_id, "schedule": list(schedule),
                  "actors": actor_results, "evaluation": grading}
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        self.event_log.write(out / "events.jsonl")
        if copy_artifacts:
            self.environment.copy_artifacts(out)
        return report

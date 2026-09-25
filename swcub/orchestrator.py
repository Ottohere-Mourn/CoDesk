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
            evaluator: Evaluator, out: Path) -> dict[str, object]:
        by_id = {actor.actor_id: actor for actor in actors}
        if len(by_id) != len(actors):
            raise ValueError("actor_id values must be unique")
        if set(schedule) - set(by_id):
            raise ValueError(f"schedule references unknown actors: {set(schedule) - set(by_id)}")
        environment_id = self.environment.environment_id
        actor_results: dict[str, object] = {}
        for actor_id in schedule:
            actor = by_id[actor_id]
            context = ActorContext(actor_id, self.environment, actor.role)
            before = self.environment.snapshot()
            try:
                actor.run(context)
                actor_results[actor_id] = {"success": True, "environment_id": context.environment_id}
                outcome = "completed"
            except Exception as exc:
                actor_results[actor_id] = {"success": False, "error": f"{type(exc).__name__}: {exc}",
                                           "environment_id": context.environment_id}
                outcome = "failed"
                self.event_log.record(actor_id, "actor", "run", before, self.environment.snapshot(),
                                      outcome=outcome,
                                      details={"environment_id": environment_id,
                                               "error": actor_results[actor_id]["error"]})
                break
            self.event_log.record(actor_id, "actor", "run", before, self.environment.snapshot(),
                                  details={"environment_id": environment_id, "outcome": outcome})
        grading = evaluator.evaluate(self.environment)
        self.event_log.record("evaluator", "evaluation", "required_rows", self.environment.snapshot(),
                              self.environment.snapshot(), outcome="pass" if grading["success"] else "fail",
                              details={"missing_count": len(grading["missing"]),
                                       "extra_rows": max(0, int(grading["actual_rows"]) - int(grading["expected_rows"]))})
        report = {"environment_id": environment_id, "schedule": list(schedule),
                  "actors": actor_results, "evaluation": grading}
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        self.event_log.write(out / "events.jsonl")
        self.environment.copy_artifacts(out)
        return report

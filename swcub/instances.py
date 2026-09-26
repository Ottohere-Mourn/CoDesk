"""Reusable task-instance records, deterministic trigger schedules, and summaries."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from statistics import median
from typing import Any, Callable, Iterable


INSTANCE_SCHEMA_VERSION = 1


class TaskInstanceError(ValueError):
    """Raised when a task instance cannot be replayed deterministically."""


@dataclass(frozen=True)
class TriggeredTurn:
    actor_id: str
    trigger: dict[str, Any] | str = "episode_started"


@dataclass(frozen=True)
class TaskInstanceSpec:
    task_id: str
    instance_id: str
    seed: int
    environment: dict[str, Any]
    initial_state: dict[str, Any]
    actors: dict[str, str]
    turns: tuple[TriggeredTurn, ...]
    evaluator: dict[str, Any]
    expected_state: dict[str, Any]
    actor_goals: dict[str, dict[str, Any]]
    schema_version: int = INSTANCE_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Any) -> "TaskInstanceSpec":
        if not isinstance(data, dict):
            raise TaskInstanceError("instance root must be an object")
        if data.get("schema_version") != INSTANCE_SCHEMA_VERSION:
            raise TaskInstanceError(f"schema_version must be {INSTANCE_SCHEMA_VERSION}")
        for name in ("task_id", "instance_id"):
            if not isinstance(data.get(name), str) or not data[name]:
                raise TaskInstanceError(f"{name} must be a non-empty string")
        seed = data.get("seed")
        if type(seed) is not int or seed < 0:
            raise TaskInstanceError("seed must be a non-negative integer")
        environment, initial = data.get("environment"), data.get("initial_state")
        actors, evaluator, expected = (data.get("actors"), data.get("evaluator"),
                                       data.get("expected_state"))
        if not isinstance(environment, dict) or not environment:
            raise TaskInstanceError("environment must be a non-empty object")
        if not isinstance(initial, dict):
            raise TaskInstanceError("initial_state must be an object")
        if (not isinstance(actors, dict) or len(actors) < 2
                or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                       for k, v in actors.items())):
            raise TaskInstanceError("actors must map at least two unique actor ids to roles")
        raw_turns = data.get("schedule")
        if not isinstance(raw_turns, list) or not raw_turns:
            raise TaskInstanceError("schedule must be a non-empty array")
        turns: list[TriggeredTurn] = []
        for index, raw in enumerate(raw_turns):
            if not isinstance(raw, dict) or raw.get("actor_id") not in actors:
                raise TaskInstanceError(f"schedule[{index}] references an unknown actor")
            trigger = raw.get("trigger", "episode_started")
            if trigger != "episode_started":
                if (not isinstance(trigger, dict) or set(trigger) != {"after_actor_turn"}
                        or not isinstance(trigger["after_actor_turn"], dict)):
                    raise TaskInstanceError(f"schedule[{index}] has an invalid trigger")
                dependency = trigger["after_actor_turn"]
                if (set(dependency) != {"actor_id", "count"}
                        or dependency.get("actor_id") not in actors
                        or type(dependency.get("count")) is not int
                        or dependency["count"] < 1):
                    raise TaskInstanceError(f"schedule[{index}] has an invalid turn dependency")
            turns.append(TriggeredTurn(raw["actor_id"], deepcopy(trigger)))
        if not isinstance(evaluator, dict) or not evaluator.get("type"):
            raise TaskInstanceError("evaluator.type is required")
        if not isinstance(expected, dict) or not expected:
            raise TaskInstanceError("expected_state must be a non-empty object")
        actor_goals = data.get("actor_goals", {})
        if (not isinstance(actor_goals, dict)
                or set(actor_goals) - set(actors)
                or any(not isinstance(goal, dict) or not goal for goal in actor_goals.values())):
            raise TaskInstanceError("actor_goals must map known actor ids to non-empty goals")
        spec = cls(data["task_id"], data["instance_id"], seed, deepcopy(environment),
                   deepcopy(initial), dict(actors), tuple(turns), deepcopy(evaluator),
                   deepcopy(expected), deepcopy(actor_goals))
        spec.materialize_schedule()
        return spec

    def materialize_schedule(self) -> list[str]:
        """Resolve turns when their actor-turn prerequisites have been reached."""
        remaining = list(self.turns)
        counts = {actor_id: 0 for actor_id in self.actors}
        result: list[str] = []
        while remaining:
            ready_index = None
            for index, turn in enumerate(remaining):
                trigger = turn.trigger
                if trigger == "episode_started":
                    ready_index = index
                    break
                dependency = trigger["after_actor_turn"]
                if counts[dependency["actor_id"]] >= dependency["count"]:
                    ready_index = index
                    break
            if ready_index is None:
                waits = [turn.trigger for turn in remaining]
                raise TaskInstanceError(f"trigger schedule deadlock: {waits!r}")
            turn = remaining.pop(ready_index)
            result.append(turn.actor_id)
            counts[turn.actor_id] += 1
        return result

    def initialize(self, reset_environment: Callable[[str, int], Any],
                   apply_initial_state: Callable[[Any, dict[str, Any]], None]) -> Any:
        """Create a fresh adapter episode, then let its task adapter seed state."""
        environment = reset_environment(self.instance_id, self.seed)
        apply_initial_state(environment, deepcopy(self.initial_state))
        return environment


def aggregate_reports(reports: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize task episodes and per-actor outcomes from saved JSON reports."""
    rows = list(reports)
    if not rows:
        raise ValueError("at least one episode report is required")
    actors: dict[str, dict[str, int]] = {}
    for row in rows:
        for actor_id, outcome in row.get("individual_goals", {}).items():
            tally = actors.setdefault(actor_id, {"episodes": 0, "successes": 0})
            tally["episodes"] += 1
            tally["successes"] += int(bool(outcome.get("success")))
    durations = [float(row["elapsed_seconds"]) for row in rows
                 if isinstance(row.get("elapsed_seconds"), (int, float))]
    return {
        "episodes": len(rows),
        "interpretation": ("Descriptive counts across mixed solo, recovery, and intentional negative-control "
                           "policies; not an overall performance rate."),
        "task_ids": sorted({str(row.get("task_id", row.get("task_instance_id", "unknown")))
                             for row in rows}),
        "evaluation_successes": sum(bool(row.get("evaluation", {}).get("success"))
                                     for row in rows),
        "reset_successes": sum(bool(row.get("reset_check", {}).get("success"))
                                for row in rows),
        "actor_goals": {actor_id: {**counts,
                                    "success_rate": counts["successes"] / counts["episodes"]}
                        for actor_id, counts in sorted(actors.items())},
        "elapsed_seconds_median": median(durations) if durations else None,
        "scenario_outcomes": sorted({str(row.get("scenario_outcome", "unknown"))
                                      for row in rows}),
    }

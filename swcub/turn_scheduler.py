"""Small deterministic turn controller for cooperative/shared desktop episodes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass
class ActorTurnState:
    turns: int = 0
    completed: bool = False
    paused: bool = False
    yielded: bool = False
    error: str | None = None


class TurnScheduler:
    """Round-robin scheduler; each turn is one actor ``run_step`` call.

    Actors own their application logic. The scheduler only limits and orders
    calls, exposes pause/resume/yield, and can reset actor-local state plus an
    injected environment reset callback.
    """

    def __init__(self, actors: Mapping[str, Any], contexts: Mapping[str, Any], *,
                 step_budget: int, reset_environment: Callable[[], Any] | None = None):
        if step_budget < 1:
            raise ValueError("step_budget must be positive")
        if set(actors) != set(contexts):
            raise ValueError("actors and contexts must have identical actor IDs")
        if not actors:
            raise ValueError("at least one actor is required")
        self.actors = dict(actors)
        self.contexts = dict(contexts)
        self.step_budget = step_budget
        self.reset_environment = reset_environment
        self.states = {actor_id: ActorTurnState() for actor_id in actors}
        self.order = list(actors)
        self.cursor = 0

    def pause(self, actor_id: str) -> None:
        self._state(actor_id).paused = True
        method = getattr(self.actors[actor_id], "pause", None)
        if callable(method):
            method()

    def resume(self, actor_id: str) -> None:
        state = self._state(actor_id)
        state.paused = False
        method = getattr(self.actors[actor_id], "resume", None)
        if callable(method):
            method()

    def yield_actor(self, actor_id: str) -> None:
        self._state(actor_id).yielded = True
        method = getattr(self.actors[actor_id], "yield_turn", None)
        if callable(method):
            method()

    def _state(self, actor_id: str) -> ActorTurnState:
        if actor_id not in self.states:
            raise KeyError(f"unknown actor {actor_id!r}")
        return self.states[actor_id]

    def next_actor(self) -> str | None:
        # A yielded actor gives one available turn to its peers. If every
        # remaining actor yielded or is paused, clear the one-turn yield marker
        # and let the first runnable actor continue instead of deadlocking.
        for allow_yielded in (False, True):
            for offset in range(len(self.order)):
                index = (self.cursor + offset) % len(self.order)
                actor_id = self.order[index]
                state = self.states[actor_id]
                if state.completed or state.paused or state.error:
                    continue
                if state.yielded and not allow_yielded:
                    state.yielded = False
                    continue
                self.cursor = (index + 1) % len(self.order)
                return actor_id
        return None

    def run_next(self) -> str | None:
        actor_id = self.next_actor()
        if actor_id is None:
            return None
        actor = self.actors[actor_id]
        context = self.contexts[actor_id]
        state = self.states[actor_id]
        if state.turns >= self.step_budget:
            state.error = f"actor exceeded step budget {self.step_budget}"
            return actor_id
        try:
            step = getattr(actor, "run_step", None)
            if callable(step):
                state.completed = bool(step(context))
            else:
                actor.run(context)
                state.completed = True
            state.turns += 1
        except Exception as exc:
            state.turns += 1
            state.error = f"{type(exc).__name__}: {exc}"
        finally:
            state.yielded = state.yielded or bool(getattr(actor, "yield_requested", False))
        if not state.completed and state.turns >= self.step_budget and not state.error:
            state.error = f"actor exceeded step budget {self.step_budget}"
        return actor_id

    def run_until_blocked(self) -> dict[str, ActorTurnState]:
        while self.run_next() is not None:
            pass
        return self.states

    def reset(self) -> Any:
        """Reset environment first, then actor history and scheduler counters."""
        result = self.reset_environment() if self.reset_environment else None
        for actor in self.actors.values():
            reset_actor = getattr(actor, "reset", None)
            if callable(reset_actor):
                reset_actor()
            resume = getattr(actor, "resume", None)
            if callable(resume):
                resume()
        self.states = {actor_id: ActorTurnState() for actor_id in self.order}
        self.cursor = 0
        return result

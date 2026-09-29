from __future__ import annotations

import base64

import pytest

from swcub.environment import ActorContext
from swcub.osworld_agent_actor import OSWorldAgentActor
from swcub.turn_scheduler import TurnScheduler


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
    "fV8AAAAASUVORK5CYII="
)


class FakeAgent:
    def __init__(self, actions: list[list[str]]):
        self.actions = list(actions)
        self.calls: list[tuple[str, dict]] = []
        self.reset_count = 0

    def predict(self, instruction, observation):
        self.calls.append((instruction, observation))
        return "fake response", self.actions.pop(0)

    def reset(self):
        self.reset_count += 1


class FakeContext:
    def __init__(self, actor_id: str):
        self.actor_id = actor_id
        self.environment_id = f"env-{actor_id}"
        self._observed_revision = 0
        self.actions: list[str] = []

    def observe(self, actor_id: str, interface: str):
        assert interface == "gui"
        self._observed_revision += 1
        return {"screenshot": _PNG, "actor_id": self.actor_id,
                "revision": self._observed_revision}

    def refresh_observation(self, actor_id: str):
        return self.observe(actor_id, "gui")

    def act(self, actor_id: str, interface: str, action, observed_revision=None):
        assert interface == "gui"
        self.actions.append(action)


def test_actor_instances_keep_observations_traces_and_histories_separate():
    writer_model = FakeAgent([["click(1, 2)"], ["DONE"]])
    calc_model = FakeAgent([["click(3, 4)"], ["DONE"]])
    writer_context = FakeContext("writer")
    calc_context = FakeContext("calc")
    writer = OSWorldAgentActor(writer_model, "edit Writer", actor_id="writer_actor")
    calc = OSWorldAgentActor(calc_model, "edit Calc", actor_id="calc_actor")

    assert writer.run_step(ActorContext("writer_actor", writer_context, "gui")) is False
    assert calc.run_step(ActorContext("calc_actor", calc_context, "gui")) is False
    assert writer.run_step(ActorContext("writer_actor", writer_context, "gui")) is True
    assert calc.run_step(ActorContext("calc_actor", calc_context, "gui")) is True

    assert writer_context.actions == ["click(1, 2)"]
    assert calc_context.actions == ["click(3, 4)"]
    assert [row["actor_id"] for row in writer.trace] == ["writer_actor", "writer_actor"]
    assert [row["actor_id"] for row in calc.trace] == ["calc_actor", "calc_actor"]
    assert writer_model.calls[0][1]["actor_id"] == "writer"
    assert calc_model.calls[0][1]["actor_id"] == "calc"


def test_pause_resume_yield_and_step_budget_are_actor_local():
    agent = OSWorldAgentActor(FakeAgent([["DONE"]]), "task", max_steps=1)
    context = ActorContext("writer_actor", FakeContext("writer"), "gui")
    agent.pause()
    assert agent.run_step(context) is False
    assert agent.steps == 0

    agent.resume()
    agent.yield_turn()
    assert agent.yield_requested is True
    assert agent.run_step(context) is True
    assert agent.steps == 1
    assert agent.yield_requested is False
    with pytest.raises(RuntimeError, match="did not terminate within"):
        agent.terminated = False
        agent.run_step(context)


def test_reset_clears_only_the_selected_actor_trace():
    writer_model = FakeAgent([["DONE"]])
    calc_model = FakeAgent([["DONE"]])
    writer = OSWorldAgentActor(writer_model, "writer")
    calc = OSWorldAgentActor(calc_model, "calc")
    writer.run_step(ActorContext("writer_actor", FakeContext("writer"), "gui"))
    calc.run_step(ActorContext("calc_actor", FakeContext("calc"), "gui"))

    writer.reset()

    assert writer.trace == []
    assert calc.trace
    assert writer_model.reset_count == 2
    assert calc_model.reset_count == 1


def test_scheduler_yield_and_pause_resume_work_with_osworld_agent_actor():
    writer = OSWorldAgentActor(FakeAgent([["DONE"]]), "writer", actor_id="writer_actor")
    calc = OSWorldAgentActor(FakeAgent([["click(3, 4)"], ["DONE"]]), "calc",
                             actor_id="calc_actor")
    scheduler = TurnScheduler(
        {"writer_actor": writer, "calc_actor": calc},
        {"writer_actor": ActorContext("writer_actor", FakeContext("writer"), "gui"),
         "calc_actor": ActorContext("calc_actor", FakeContext("calc"), "gui")},
        step_budget=2,
    )

    scheduler.yield_actor("writer_actor")
    assert scheduler.run_next() == "calc_actor"
    scheduler.pause("writer_actor")
    assert scheduler.run_next() == "calc_actor"
    scheduler.resume("writer_actor")
    assert scheduler.run_next() == "writer_actor"
    assert scheduler.states["writer_actor"].completed

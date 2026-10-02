from __future__ import annotations

import base64
from pathlib import Path
import json
from pathlib import Path

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


class CacheWritingAgent(FakeAgent):
    def predict(self, instruction, observation):
        cache = Path("draft/message_cache/messages_step_0.json")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(instruction, encoding="utf-8")
        return super().predict(instruction, observation)


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


def test_actor_observations_and_official_agent_debug_cache_are_isolated(tmp_path):
    original_cwd = Path.cwd()
    writer_dir = tmp_path / "model-actors" / "writer_actor"
    calc_dir = tmp_path / "model-actors" / "calc_actor"
    writer = OSWorldAgentActor(CacheWritingAgent([["DONE"]]), "Writer prompt",
                               actor_id="writer_actor", artifact_directory=writer_dir)
    calc = OSWorldAgentActor(CacheWritingAgent([["DONE"]]), "Calc prompt",
                             actor_id="calc_actor", artifact_directory=calc_dir)

    writer.run_step(ActorContext("writer_actor", FakeContext("writer"), "gui"))
    calc.run_step(ActorContext("calc_actor", FakeContext("calc"), "gui"))

    assert Path.cwd() == original_cwd
    assert (writer_dir / "draft/message_cache/messages_step_0.json").read_text() == "Writer prompt"
    assert (calc_dir / "draft/message_cache/messages_step_0.json").read_text() == "Calc prompt"
    assert (writer_dir / "observations/step-001.png").is_file()
    assert (calc_dir / "observations/step-001.png").is_file()
    assert writer.trace[0]["observation_file"] == "model-actors/writer_actor/observations/step-001.png"
    assert calc.trace[0]["observation_file"] == "model-actors/calc_actor/observations/step-001.png"


def test_actor_observations_and_official_debug_cache_are_saved_per_actor(tmp_path):
    class DebugAgent(FakeAgent):
        def predict(self, instruction, observation):
            Path("draft/message_cache").mkdir(parents=True, exist_ok=True)
            Path("draft/message_cache/messages_step_0.json").write_text(
                json.dumps({"instruction": instruction,
                            "screenshot_size": len(observation["screenshot"])}))
            return super().predict(instruction, observation)

    writer_dir = tmp_path / "model-actors" / "writer_actor"
    calc_dir = tmp_path / "model-actors" / "calc_actor"
    writer = OSWorldAgentActor(DebugAgent([["DONE"]]), "writer",
                               actor_id="writer_actor", artifact_directory=writer_dir)
    calc = OSWorldAgentActor(DebugAgent([["DONE"]]), "calc",
                             actor_id="calc_actor", artifact_directory=calc_dir)
    original_cwd = Path.cwd()

    assert writer.run_step(ActorContext("writer_actor", FakeContext("writer"), "gui"))
    assert calc.run_step(ActorContext("calc_actor", FakeContext("calc"), "gui"))

    assert Path.cwd() == original_cwd
    assert (writer_dir / "observations/step-001.png").is_file()
    assert (calc_dir / "observations/step-001.png").is_file()
    writer_cache = writer_dir / "draft/message_cache/messages_step_0.json"
    calc_cache = calc_dir / "draft/message_cache/messages_step_0.json"
    assert writer_cache.is_file() and calc_cache.is_file()
    assert json.loads(writer_cache.read_text())["instruction"] == "writer"
    assert json.loads(calc_cache.read_text())["instruction"] == "calc"
    assert writer.trace[0]["observation_file"].endswith("writer_actor/observations/step-001.png")
    assert calc.trace[0]["observation_file"].endswith("calc_actor/observations/step-001.png")


def test_action_boundary_pause_preserves_unexecuted_native_actions():
    model = FakeAgent([["copy", "paste", "save"]])
    context = FakeContext("writer")
    actor = OSWorldAgentActor(model, "task", actor_id="actor_a")
    boundaries = []

    def pause_after_copy(current, action):
        boundaries.append(action)
        if action == "copy":
            current.pause()

    actor.action_boundary_callback = pause_after_copy
    assert actor.run_step(ActorContext("actor_a", context, "gui")) is False
    assert actor.paused is True
    assert context.actions == ["copy"]
    assert model.calls and len(model.calls) == 1

    actor.resume()
    assert actor.run_step(ActorContext("actor_a", context, "gui")) is False
    assert context.actions == ["copy", "paste", "save"]
    assert len(model.calls) == 1  # Resume continues the same native response/history.
    assert boundaries == ["copy", "paste", "save"]

from pathlib import Path

from swcub.core import EventLog
from swcub.orchestrator import DualActorOrchestrator


class TinyEnvironment:
    environment_id = "tiny-env"

    def __init__(self):
        self.log = EventLog()
        self.revision = 0

    def snapshot(self):
        return {"revision": self.revision}

    def observe(self, actor_id, interface):
        return {"screenshot": b"visible"}

    def act(self, actor_id, interface, action, observed_revision=None):
        self.revision += 1

    def copy_artifacts(self, _out):
        pass


class OneTurnActor:
    actor_id = "a"
    role = "gui"

    def run_step(self, context):
        context.observe()
        context.press_key("tab")
        return True


class PassingEvaluator:
    def evaluate(self, _environment):
        return {"success": True}


def test_before_actor_turn_hook_runs_before_each_active_turn(tmp_path: Path):
    env = TinyEnvironment()
    calls = []
    report = DualActorOrchestrator(env).run(
        [OneTurnActor()], ["a", "a"], PassingEvaluator(), tmp_path,
        before_actor_turn=lambda actor, index: calls.append((actor.actor_id, index)),
        copy_artifacts=False,
    )
    assert report["actors"]["a"]["completed"] is True
    assert calls == [("a", 1)]

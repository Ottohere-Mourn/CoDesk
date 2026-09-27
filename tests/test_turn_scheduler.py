from swcub.turn_scheduler import TurnScheduler


class SteppedActor:
    def __init__(self, actor_id, complete_after=2):
        self.actor_id = actor_id
        self.complete_after = complete_after
        self.calls = 0
        self.paused = False

    def run_step(self, _context):
        if self.paused:
            return False
        self.calls += 1
        return self.calls >= self.complete_after

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def reset(self):
        self.calls = 0
        self.paused = False


def test_round_robin_budget_pause_resume_yield_and_reset():
    actors = {"a": SteppedActor("a"), "b": SteppedActor("b")}
    resets = []
    scheduler = TurnScheduler(actors, {"a": object(), "b": object()}, step_budget=3,
                              reset_environment=lambda: resets.append("reset"))
    scheduler.pause("b")
    assert scheduler.run_next() == "a"
    assert actors["a"].calls == 1
    assert actors["b"].calls == 0
    scheduler.yield_actor("a")
    scheduler.resume("b")
    assert scheduler.run_next() == "b"
    assert scheduler.run_next() == "b"
    assert scheduler.run_next() == "a"
    assert scheduler.states["a"].completed
    assert scheduler.states["b"].completed
    assert scheduler.run_next() is None

    scheduler.pause("a")
    scheduler.reset()
    assert resets == ["reset"]
    assert actors["a"].calls == actors["b"].calls == 0
    assert scheduler.states["a"].turns == scheduler.states["b"].turns == 0
    assert not scheduler.states["a"].paused


def test_step_budget_is_enforced():
    actor = SteppedActor("slow", complete_after=10)
    scheduler = TurnScheduler({"slow": actor}, {"slow": object()}, step_budget=2)
    scheduler.run_until_blocked()
    assert scheduler.states["slow"].turns == 2
    assert scheduler.states["slow"].error == "actor exceeded step budget 2"

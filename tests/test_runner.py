import json

import pytest

from oscombo import combo, runner
from oscombo.guest import Guest

from fakes import FakeEnv, task

TASKS = {"chrome/a": task("a"), "calc/b": task("b"), "code/c": task("c")}
CLICK = "pyautogui.click(10, 10)"


@pytest.fixture
def fake_osworld(monkeypatch, tmp_path):
    envs: list[FakeEnv] = []

    def boot(image, cache_dir):
        envs.append(FakeEnv())
        return envs[-1]

    monkeypatch.setenv("OSWORLD_DIR", str(tmp_path))
    monkeypatch.setattr(combo, "boot", boot)
    monkeypatch.setattr(runner, "load_task", lambda spec: TASKS[spec])
    monkeypatch.setattr(Guest, "execute", lambda self, argv, timeout=60: {"output": "Some Window"})
    return envs


def config(tmp_path, mode, tasks, actions=(CLICK,), **kw):
    spec = {"harness": "step", "policy": "scripted",
            "options": {"actions": list(actions), "action_pause": 0, "step_pause": 0}}
    return runner.RunConfig(mode=mode, tasks=tasks, out=tmp_path / "run", agents=[spec], max_steps=5,
                            image="guest.qcow2", setup_settle=0, isolated_boot_stagger=0, **kw)


@pytest.mark.parametrize("mode", ["sequential", "parallel"])
def test_shared_modes(fake_osworld, tmp_path, mode):
    r = runner.run(config(tmp_path, mode, ["chrome/a", "calc/b", "code/c"]))
    assert r.get("error") is None, r.get("traceback")
    assert r["scores"] == {"a": 1.0, "b": 1.0, "c": 1.0}
    assert {k: (v["status"], v["steps"]) for k, v in r["agents"].items()} == {
        "agentA": ("done", 2), "agentB": ("done", 2), "agentC": ("done", 2)}
    assert len(fake_osworld) == 1 and fake_osworld[0].closed
    assert fake_osworld[0].controller.executed == [CLICK] * 3
    trace = [json.loads(line) for line in (tmp_path / "run/trace.jsonl").read_text().splitlines()]
    assert trace[0]["actions"][0]["window_before"] == "Some Window"
    assert json.loads((tmp_path / "run/result.json").read_text())["task_ids"] == ["a", "b", "c"]


def test_solo(fake_osworld, tmp_path):
    r = runner.run(config(tmp_path, "solo", ["chrome/a"]))
    assert r["scores"] == {"a": 1.0}


def test_isolated_uses_one_guest_per_task(fake_osworld, tmp_path):
    r = runner.run(config(tmp_path, "isolated", ["chrome/a", "calc/b"]))
    assert r["scores"] == {"a": 1.0, "b": 1.0}
    assert len(fake_osworld) == 2
    assert [e.controller.executed for e in fake_osworld] == [[CLICK], [CLICK]]


def test_shadow_only_first_agent_acts_and_is_scored(fake_osworld, tmp_path):
    r = runner.run(config(tmp_path, "shadow", ["chrome/a", "calc/b"]))
    assert r["scores"] == {"a": 1.0}
    assert list(r["agents"]) == ["agentA"]
    assert fake_osworld[0].controller.executed == [CLICK]


def test_declared_fail_reaches_the_evaluator(fake_osworld, tmp_path):
    r = runner.run(config(tmp_path, "parallel", ["chrome/a", "calc/b"], actions=(CLICK, "FAIL")))
    assert {v["status"] for v in r["agents"].values()} == {"fail"}
    assert r["scores"] == {"a": 0.0, "b": 0.0}


def test_dead_guest_is_infra_and_skips_evaluation(fake_osworld, tmp_path, monkeypatch):
    monkeypatch.setenv("OSCOMBO_SHOT_PATIENCE", "0")
    orig_boot = combo.boot

    def dead_boot(image, cache_dir):
        env = orig_boot(image, cache_dir)
        env.controller.shots = False
        return env

    monkeypatch.setattr(combo, "boot", dead_boot)
    r = runner.run(config(tmp_path, "parallel", ["chrome/a", "calc/b"]))
    assert r["error"].startswith("INFRA")
    assert r["scores"] == {"a": None, "b": None}
    assert all("INFRA" in v["error"] for v in r["agents"].values())


def test_per_agent_specs_and_bad_policy(fake_osworld, tmp_path):
    cfg = config(tmp_path, "parallel", ["chrome/a", "calc/b"])
    cfg.agents = [cfg.agents[0], {"policy": "no-such-policy"}]
    r = runner.run(cfg)
    assert r["agents"]["agentA"]["status"] == "done"
    assert r["agents"]["agentB"]["status"] == "error" and "no-such-policy" in r["agents"]["agentB"]["error"]


def test_config_checks():
    with pytest.raises(ValueError):
        runner.RunConfig("solo", ["a", "b"], None, [{}]).check()
    with pytest.raises(ValueError):
        runner.RunConfig("parallel", ["a", "a"], None, [{}]).check()
    with pytest.raises(ValueError):
        runner.RunConfig("parallel", ["a", "b", "c"], None, [{}, {}]).check()


@pytest.mark.parametrize("med", ["broker2", "selfguard"])
def test_parallel_with_mediation_and_hint(fake_osworld, tmp_path, monkeypatch, med):
    monkeypatch.setattr("oscombo.mediation.time.sleep", lambda s: None)
    cfg = config(tmp_path, "parallel", ["chrome/a", "calc/b"], mediation=med)
    cfg.agents = [{**cfg.agents[0], "coagent_hint": True}]
    r = runner.run(cfg)
    assert r.get("error") is None, r.get("traceback")
    assert r["variant"] == f"{med}+hint" and len(r["setup_windows"]) == 2
    assert {v["status"] for v in r["agents"].values()} == {"done"}
    assert "mediation_stats" in r

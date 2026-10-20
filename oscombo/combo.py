"""Boot a Guest, set up several OSWorld tasks in it, and score each task with its own official evaluator.

Setup: the first task goes through the official ``DesktopEnv.reset``; further tasks run their setup steps
through the same setup controller. Identical declarative steps (e.g. two Chrome tasks launching Chrome on the
same debugging port) run once. OSWorld 2.0 task classes run their own ``setup()``.

Evaluation is decoupled across tasks: (1) every task's non-restarting postconfig steps (activate window, save,
sleep) run first, one call per task so a failing step cannot skip another task's save, (2) then
process-restarting steps (e.g. Chrome pkill + relaunch to flush prefs), deduplicated, (3) then each task's
getters/metric run with its postconfig already applied. Evaluating tasks one after another with their full
postconfig lets task A's Chrome relaunch steal focus from task B's "activate Calc + Ctrl+S" and silently drop B's
unsaved edit. OSWorld 2.0 task classes evaluate inside their own ``evaluate()``, which cannot
be split; balance their order (swap A/B) instead.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

from .guest import InfraError
from .osworld import client_password, score_value, task_get

RESTART_STEP_TYPES = {"launch"}


def boot(image: str, cache_dir: str) -> Any:
    """Start a fresh Guest from ``image`` (qcow2) with the docker provider."""
    from desktop_env.desktop_env import DesktopEnv
    try:
        return DesktopEnv(provider_name="docker", path_to_vm=image, cache_dir=cache_dir, os_type="Ubuntu",
                          action_space="pyautogui", require_a11y_tree=False, client_password=client_password())
    except Exception as exc:  # container start / VM readiness: retryable infrastructure failure
        raise InfraError(f"VM failed to boot: {type(exc).__name__}: {exc}") from exc


def _key(step: dict) -> str:
    return json.dumps(step, sort_keys=True)


def dedupe_setup(tasks: list[Any]) -> tuple[list[list[dict]], list[str]]:
    """Declarative setup steps of tasks[1:] minus steps already run by an earlier task (task 0 runs in full)."""
    done = {_key(c) for c in (task_get(tasks[0], "config") or [])}
    per_task, skipped = [], []
    for t in tasks[1:]:
        cfg = []
        for c in task_get(t, "config") or []:
            if _key(c) in done:
                skipped.append(c["type"])
                continue
            done.add(_key(c))
            cfg.append(c)
        per_task.append(cfg)
    return per_task, skipped


def setup_tasks(env: Any, tasks: list[Any], probe: Callable[[], set[str]] | None = None) -> dict:
    """Set up all ``tasks`` in the one Guest; raises if any setup fails.

    With ``probe`` (returns the visible window ids), the windows that appeared during each task's setup are
    recorded as ``setup_windows[i]`` (setup provenance, used by the mediation layer).
    """
    seen = probe() if probe else set()
    windows: list[list[str]] = []

    def record() -> None:
        nonlocal seen
        if probe:
            now = probe()
            windows.append(sorted(now - seen))
            seen = now

    env.reset(task_config=tasks[0])
    record()
    extra_cfgs, skipped = dedupe_setup(tasks)
    for t, cfg in zip(tasks[1:], extra_cfgs):
        env._set_task_info(t)
        env.setup_controller.reset_cache_dir(env.cache_dir)
        if env._has_custom_setup(t):
            ok, _ = env._setup_task(t, False)
        else:
            ok = env.setup_controller.setup(cfg, False)
        if not ok:
            raise RuntimeError(f"setup failed for {task_get(t, 'id')}")
        record()
    info: dict = {"skipped_duplicate_setup_steps": skipped}
    if probe:
        info["setup_windows"] = windows
    return info


def postconfig_phases(tasks: list[Any]) -> tuple[list[list[dict]], list[dict]]:
    """Per task, its non-restarting postconfig steps; plus all restarting steps, deduplicated across tasks."""
    save: list[list[dict]] = []
    restart: list[dict] = []
    seen: set[str] = set()
    for t in tasks:
        mine = []
        for step in (task_get(t, "evaluator") or {}).get("postconfig", []) or []:
            if step["type"] in RESTART_STEP_TYPES:
                if _key(step) not in seen:
                    seen.add(_key(step))
                    restart.append(step)
            else:
                mine.append(step)
        save.append(mine)
    return save, restart


def _run_steps(env: Any, steps: list[dict], label: str, result: dict, retries: int = 3) -> None:
    """Run postconfig steps; one task's failure must not skip the others' steps (each call is isolated)."""
    for _ in range(retries):
        try:
            if env.setup_controller.setup(steps, False):
                return
            err = "Guest control server not ready"
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"[:300]
        time.sleep(10)
    result.setdefault("eval_errors", {})[f"postconfig_{label}"] = err


def evaluate_tasks(env: Any, tasks: list[Any], declared_fail: list[bool], result: dict) -> dict[str, float | None]:
    """Score every task in the shared Guest. ``declared_fail[i]``: agent i ended with FAIL (infeasible claim)."""
    settle = float(os.environ.get("OSCOMBO_EVAL_SETTLE_SECONDS", "0"))
    if settle > 0:  # slow Guests may still be flushing an application save
        time.sleep(settle)
    save, restart = postconfig_phases(tasks)
    result["eval_postconfig"] = {"save": [[s["type"] for s in steps] for steps in save],
                                 "restart": [s["type"] for s in restart]}
    for t, steps in zip(tasks, save):
        if steps:
            _run_steps(env, steps, f"save:{task_get(t, 'id')}", result)
    if restart:
        _run_steps(env, restart, "restart", result)
    scores: dict[str, float | None] = {}
    for t, failed in zip(tasks, declared_fail):
        env._set_task_info(t)
        if env.evaluator:
            env.evaluator = {**env.evaluator, "postconfig": []}  # already applied above
        env.action_history = ["FAIL"] if failed else []
        scores[task_get(t, "id")] = evaluate_one(env, t, result)
    return scores


def evaluate_one(env: Any, task: Any, result: dict) -> float | None:
    """Official evaluation of the task currently loaded in ``env``; ``None`` if the evaluator itself crashed."""
    try:
        return score_value(env.evaluate())
    except Exception as exc:
        result.setdefault("eval_errors", {})[task_get(task, "id")] = f"{type(exc).__name__}: {exc}"[:300]
        return None

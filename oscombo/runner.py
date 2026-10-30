"""Run modes for composite OSWorld tasks and the per-run record.

  solo        one task alone in a fresh Guest (baseline)
  sequential  all task setups in one Guest; agent A runs to completion, then agent B, ...
  parallel    all task setups in one Guest; all agents run concurrently (threads, released by one barrier)
  isolated    control: agents run concurrently through the same code path, but each task in its own Guest
  shadow      control: all task setups in one Guest; agent A works, the other agents only poll the Guest
              (screenshot, think time, focused window) without acting, so the Guest sees the same client load

Each agent only sees its own task instruction. Every task is scored by its own official evaluator
(see ``combo.py`` for the decoupled multi-task evaluation).

Output directory: ``result.json`` (summary), ``trace.jsonl`` (one line per agent step), ``start.png`` /
``end.png``, ``<agent>-stepNN.png`` (step-loop harness), ``<agent>/`` (external harnesses).
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import combo, mediation
from .guest import Guest, InfraError
from .harness import AgentContext, AgentResult, make_harness
from .osworld import load_task, osworld_dir, task_get

MODES = ("solo", "sequential", "parallel", "isolated", "shadow")
# instruction suffix of the co-agent prompt ablation ("coagent_hint": true in an agent spec): it only states the fact
COAGENT_HINT = ("\n\nNote: this computer may be shared. Another agent may be operating the same desktop at the same "
                "time, working on its own task in its own windows, so windows, focus or content can change because of "
                "it.")


@dataclass
class RunConfig:
    mode: str
    tasks: list[str]                    # task specs, e.g. chrome/<uuid>, v2/052
    out: Path
    agents: list[dict]                  # one spec per task, or a single spec shared by all agents
    max_steps: int = 25
    image: str | None = None            # Guest qcow2; default $OSCOMBO_GUEST_IMAGE
    cache_dir: str | None = None        # per-run task cache; default <out>/cache (never share across runs)
    setup_settle: float = 20.0          # s after setup before the agents start (apps opened by setup settle)
    quiet_notifications: bool = True
    isolated_boot_stagger: float = 30.0
    mediation: str = "none"             # none | broker1 | broker2 | selfguard (parallel mode, step harness)
    extra: dict[str, Any] = field(default_factory=dict)  # free-form labels copied into result.json

    def check(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if (self.mode == "solo") != (len(self.tasks) == 1):
            raise ValueError("solo takes exactly one task, the other modes two or more")
        if len(set(self.tasks)) != len(self.tasks):
            raise ValueError("tasks of one run must be distinct (scores are keyed by task id)")
        if len(self.agents) not in (1, len(self.tasks)):
            raise ValueError("give one agent spec per task, or one shared spec")
        if self.mediation not in mediation.MODES:
            raise ValueError(f"mediation must be one of {mediation.MODES}")

    def agent_spec(self, i: int) -> dict:
        return self.agents[i if len(self.agents) > 1 else 0]

    def variant(self) -> str:
        """Condition label beyond the mode, used by ``analyze``: mediation and prompt ablations."""
        parts = [] if self.mediation == "none" else [self.mediation]
        if any(a.get("coagent_hint") for a in self.agents):
            parts.append("hint")
        if any(a.get("instruction_suffix") for a in self.agents):
            parts.append("suffix")
        return "+".join(parts)


def instruction_for(task: Any, spec: dict) -> str:
    return (task_get(task, "instruction") + (COAGENT_HINT if spec.get("coagent_hint") else "")
            + spec.get("instruction_suffix", ""))


def endpoint(spec: dict) -> str | None:
    """Model endpoint an agent talks to (recorded per run; the key is never recorded)."""
    return spec.get("base_url") or spec.get("options", {}).get("base_url") or os.environ.get("OPENAI_BASE_URL")


class AgentSlot:
    """One agent: its harness, context and result; exceptions become status ``error``."""

    def __init__(self, i: int, task: Any, spec: dict, guest: Guest, out: Path, max_steps: int):
        self.name = f"agent{chr(ord('A') + i)}"
        self.task = task
        self.spec = spec
        self.ctx = AgentContext(name=self.name, task_id=str(task_get(task, "id")),
                                instruction=instruction_for(task, spec), guest=guest, out=out,
                                max_steps=max_steps, spec=spec)
        self.result = AgentResult()
        self.harness = None

    def prepare(self) -> None:
        try:
            self.harness = make_harness(self.spec)
            self.harness.prepare(self.ctx)
        except Exception as exc:
            self._fail(exc)

    def run(self, barrier: threading.Barrier | None = None) -> None:
        if barrier is not None:
            barrier.wait()  # all agents observe and start at the same moment
        if self.harness is None or self.result.status == "error":
            return
        try:
            self.result = self.harness.run(self.ctx)
        except Exception as exc:
            self._fail(exc)

    def _fail(self, exc: Exception) -> None:
        self.result.status, self.result.error = "error", f"{type(exc).__name__}: {exc}"[:500]
        self.result.trace.append({"error": traceback.format_exc()[-2000:]})

    @property
    def infra_failed(self) -> bool:
        return "INFRA" in (self.result.error or "")

    def summary(self) -> dict:
        return {"task": self.ctx.task_id, "harness": self.spec.get("harness", "step"),
                "policy": self.spec.get("policy"), "model": self.spec.get("model"), "status": self.result.status,
                "endpoint": endpoint(self.spec), "error": self.result.error, "steps": self.result.steps,
                **self.result.extra}


class ShadowPoller:
    """Loads the shared Guest like a second agent would (screenshot, think, read the focused window) but never acts."""

    def __init__(self, guest: Guest):
        self.guest = guest
        self.stop = threading.Event()

    def run(self, barrier: threading.Barrier | None = None) -> None:
        if barrier is not None:
            barrier.wait()
        while not self.stop.is_set():
            self.guest.env.controller.get_screenshot()
            self.stop.wait(random.uniform(3.0, 8.0))  # roughly one model call
            self.guest.active_window()


def _run_threads(targets: list, barrier: bool = True) -> None:
    b = threading.Barrier(len(targets)) if barrier else None
    threads = [threading.Thread(target=t, args=(b,)) for t in targets]
    for th in threads:
        th.start()
    for th in threads:
        th.join()


def code_version() -> dict:
    def rev(path: Path) -> str | None:
        try:
            head = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                                  timeout=10).stdout.strip()
            dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"],
                                   capture_output=True, text=True, timeout=10).stdout.strip()
            return head + ("+dirty" if dirty else "") if head else None
        except Exception:
            return None
    return {"oscombo": rev(Path(__file__).resolve().parent), "osworld": rev(osworld_dir())}


def run(cfg: RunConfig) -> dict:
    cfg.check()
    cfg.out.mkdir(parents=True, exist_ok=True)
    image = cfg.image or os.environ.get("OSCOMBO_GUEST_IMAGE")
    cache = Path(cfg.cache_dir or cfg.out / "cache")
    result: dict[str, Any] = {"mode": cfg.mode, "tasks": cfg.tasks, "max_steps": cfg.max_steps,
                              "variant": cfg.variant(), "mediation": cfg.mediation, "agent_specs": cfg.agents,
                              "code": code_version(), **cfg.extra}
    slots: list[AgentSlot] = []
    t0 = time.time()
    try:
        local_backend = os.environ.get("OSCOMBO_BACKEND", "docker").lower() in {"local", "x11", "xephyr"}
        if not image and not local_backend:
            raise ValueError("no Guest image: set OSCOMBO_GUEST_IMAGE or pass --image")
        tasks = [load_task(s) for s in cfg.tasks]
        result["task_ids"] = [str(task_get(t, "id")) for t in tasks]
        result["instructions"] = [task_get(t, "instruction") for t in tasks]
        if cfg.mode == "isolated":
            _run_isolated(cfg, image, cache, tasks, result, slots, t0)
        else:
            _run_shared(cfg, image, cache, tasks, result, slots, t0)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:500]
        result["traceback"] = traceback.format_exc()[-3000:]
    finally:
        result["agents"] = {s.name: s.summary() for s in slots}
        result["total_s"] = round(time.time() - t0, 1)
        with open(cfg.out / "trace.jsonl", "w") as f:
            for s in slots:
                for rec in s.result.trace:
                    f.write(json.dumps({"agent": s.name, **rec}) + "\n")
        with open(cfg.out / "result.json", "w") as f:
            json.dump(result, f, indent=2)
    return result


def _shot(guest: Guest, path: Path) -> None:
    try:
        path.write_bytes(guest.env.controller.get_screenshot() or b"")
    except Exception:
        pass


def _run_shared(cfg: RunConfig, image: str, cache: Path, tasks: list, result: dict, slots: list, t0: float) -> None:
    env = combo.boot(image, str(cache))
    try:
        guest = Guest(env)
        result["boot_s"] = round(time.time() - t0, 1)
        if cfg.quiet_notifications:
            guest.quiet_notifications()
        mediate = cfg.mediation != "none" and cfg.mode == "parallel"
        result.update(combo.setup_tasks(env, tasks, mediation.window_probe(guest) if mediate else None))
        time.sleep(cfg.setup_settle)
        _shot(guest, cfg.out / "start.png")
        result["setup_s"] = round(time.time() - t0 - result["boot_s"], 1)

        active = tasks[:1] if cfg.mode == "shadow" else tasks  # shadow: only agent A acts and is evaluated
        slots += [AgentSlot(i, t, cfg.agent_spec(i), guest, cfg.out, cfg.max_steps) for i, t in enumerate(active)]
        if mediate:
            _attach_mediation(cfg, guest, slots, result)
        for s in slots:
            s.prepare()
        t_agents = time.time()
        for s in slots:
            s.ctx.t0 = t_agents
        if cfg.mode == "parallel":
            _run_threads([s.run for s in slots])
        elif cfg.mode == "shadow":
            pollers = [ShadowPoller(guest) for _ in tasks[1:]]
            barrier = threading.Barrier(len(pollers) + 1)
            threads = [threading.Thread(target=p.run, args=(barrier,)) for p in pollers]
            for th in threads:
                th.start()
            slots[0].run(barrier)
            for p in pollers:
                p.stop.set()
            for th in threads:
                th.join()
        else:  # solo, sequential
            for s in slots:
                s.run()
        result["agents_s"] = round(time.time() - t_agents, 1)
        if mediate:
            stats = [s.ctx.broker.stats for s in slots[:1] if s.ctx.broker]
            stats += [s.ctx.guard.stats for s in slots if s.ctx.guard]
            result["mediation_stats"] = [dict(x) for x in stats]
        _shot(guest, cfg.out / "end.png")

        if any(s.infra_failed for s in slots):  # dead Guest: evaluation would hang; the run gets retried
            result["scores"] = {str(task_get(t, "id")): None for t in active}
            result["error"] = "INFRA: Guest stopped answering during the agent phase; evaluation skipped"
            return
        result["scores"] = combo.evaluate_tasks(env, active, [s.result.status == "fail" for s in slots], result)
    finally:
        try:
            env.close()
        except Exception:
            pass


def _attach_mediation(cfg: RunConfig, guest: Guest, slots: list, result: dict) -> None:
    windows = {s.name: set(w) for s, w in zip(slots, result.get("setup_windows", []))}
    if cfg.mediation.startswith("broker"):
        from .analyze import APP_PATTERNS, app_of
        titles = {s.name: APP_PATTERNS.get(app_of(spec, {}), "$^") for s, spec in zip(slots, cfg.tasks)}
        broker = mediation.DesktopBroker(guest, windows, level=int(cfg.mediation[-1]), app_titles=titles)
        for s in slots:
            s.ctx.broker = broker
    else:
        for s in slots:
            s.ctx.guard = mediation.SelfGuard(guest, windows.get(s.name, set()))
    unmediated = [s.name for s in slots if s.spec.get("harness", "step") != "step"]
    if unmediated:  # external harnesses run unmodified
        result["mediation_skipped"] = unmediated


def _run_isolated(cfg: RunConfig, image: str, cache: Path, tasks: list, result: dict, slots: list,
                  t0: float) -> None:
    envs: list = [None] * len(tasks)
    errors: list = [None] * len(tasks)

    def boot(i: int) -> None:
        time.sleep(cfg.isolated_boot_stagger * i)  # do not race the provider's host-port allocation
        try:
            envs[i] = combo.boot(image, str(cache / f"guest{i}"))
            if cfg.quiet_notifications:
                Guest(envs[i]).quiet_notifications()
            envs[i].reset(task_config=tasks[i])
        except Exception as exc:
            errors[i] = f"{type(exc).__name__}: {exc}"

    try:
        _run_threads([lambda _b, i=i: boot(i) for i in range(len(tasks))], barrier=False)
        if any(errors):
            raise InfraError(f"VM failed / setup failed: {errors}")
        result["boot_s"] = round(time.time() - t0, 1)
        time.sleep(cfg.setup_settle)
        slots += [AgentSlot(i, t, cfg.agent_spec(i), Guest(envs[i]), cfg.out, cfg.max_steps)
                  for i, t in enumerate(tasks)]
        for s in slots:
            _shot(s.ctx.guest, cfg.out / f"start{s.name[-1]}.png")
            s.prepare()
        t_agents = time.time()
        for s in slots:
            s.ctx.t0 = t_agents
        _run_threads([s.run for s in slots])
        result["agents_s"] = round(time.time() - t_agents, 1)
        scores = {}
        for t, s, env in zip(tasks, slots, envs):
            tid = str(task_get(t, "id"))
            if s.infra_failed:
                scores[tid] = None
                result["error"] = "INFRA: Guest stopped answering during the agent phase; evaluation skipped"
                continue
            env.action_history = ["FAIL"] if s.result.status == "fail" else []
            scores[tid] = combo.evaluate_one(env, t, result)  # own Guest: the official evaluation as in solo
        result["scores"] = scores
    finally:
        for env in envs:
            if env is not None:
                try:
                    env.close()
                except Exception:
                    pass

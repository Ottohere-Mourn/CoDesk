"""Command line: ``python -m oscombo {run,queue,analyze,cleanup} ...``

run      one run (one Guest, or one per task in isolated mode)
matrix   expand a combo file into a run list (modes x task orders x repeats, plus solo baselines)
queue    a list of runs with a concurrency cap, one infra-retry pass, optional tarball
analyze  aggregate results (see oscombo/analyze.py)
cleanup  remove the Guest containers of a run that was killed (docker label ``oscombo.run``)

Agent spec (model + harness) for ``run``: either flags shared by all agents (``--harness``, ``--policy``,
``--model``, ``--effort``, ``--opt key=value``), or ``--agents`` with a json list (inline or a file) holding one
spec per task, e.g. ``[{"policy": "openai-cua", "model": "m1"}, {"harness": "codex", "model": "m2"}]``.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path


def _value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _set_opt(opts: dict, item: str) -> None:
    key, _, value = item.partition("=")
    *path, leaf = key.split(".")
    for part in path:
        opts = opts.setdefault(part, {})
    opts[leaf] = _value(value)


def agent_specs(a: argparse.Namespace) -> list[dict]:
    if a.agents:
        text = Path(a.agents).read_text() if os.path.exists(a.agents) else a.agents
        specs = json.loads(text)
        return specs if isinstance(specs, list) else [specs]
    spec: dict = {"harness": a.harness, "policy": a.policy, "model": a.model, "effort": a.effort, "options": {}}
    if a.max_tokens:
        spec["max_tokens"] = a.max_tokens
    if a.base_url:
        spec["base_url"] = a.base_url
    for item in a.opt:
        _set_opt(spec["options"], item)
    return [{k: v for k, v in spec.items() if v is not None}]


def add_run_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--harness", default=os.environ.get("OSCOMBO_HARNESS", "step"),
                    help="step | command | codex | module:Class")
    ap.add_argument("--policy", default=os.environ.get("OSCOMBO_POLICY", "openai-cua"),
                    help="step harness only: openai-cua | chat-pyautogui | responses-pyautogui | osworld-agent | "
                         "scripted | module:factory")
    ap.add_argument("--model", default=os.environ.get("OSCOMBO_MODEL"))
    ap.add_argument("--effort", default=os.environ.get("OSCOMBO_REASONING_EFFORT", "medium"))
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--base-url", help="model endpoint for transports that accept one (default OPENAI_BASE_URL)")
    ap.add_argument("--opt", action="append", default=[], metavar="KEY=VALUE",
                    help="harness/policy option (json value; dotted keys nest), repeatable")
    ap.add_argument("--agents", help="json list of per-agent specs, inline or a file (overrides the flags above)")
    ap.add_argument("--max-steps", type=int, default=int(os.environ.get("OSCOMBO_MAX_STEPS", "25")))
    ap.add_argument("--image", help="Guest qcow2 (default $OSCOMBO_GUEST_IMAGE)")
    ap.add_argument("--setup-settle", type=float, default=20.0)
    ap.add_argument("--label", action="append", default=[], metavar="KEY=VALUE", help="extra field in result.json")


def cmd_run(a: argparse.Namespace) -> int:
    from . import osworld, runner
    extra: dict = {}
    for item in a.label:
        _set_opt(extra, item)
    # resolve user paths before activate() changes into the OSWorld checkout
    tasks = [str(Path(t).resolve()) if t.endswith((".json", ".py")) else t for t in a.tasks]
    cfg = runner.RunConfig(mode=a.mode, tasks=tasks, out=Path(a.out).resolve(), agents=agent_specs(a),
                           max_steps=a.max_steps, image=str(Path(a.image).resolve()) if a.image else None,
                           setup_settle=a.setup_settle, extra=extra)
    osworld.activate()
    result = runner.run(cfg)
    print(json.dumps({k: result.get(k) for k in ("mode", "tasks", "scores", "agents", "error")}, indent=1))
    return 0


def read_list(path: str) -> list[list[str]]:
    """Run list: one run per line, ``<name> <mode> <task> [<task> ...]``; ``#`` starts a comment."""
    runs = []
    for line in Path(path).read_text().splitlines():
        parts = shlex.split(line, comments=True)
        if parts:
            if len(parts) < 3:
                raise ValueError(f"bad run line: {line!r}")
            runs.append(parts)
    return runs


def short(spec: str) -> str:
    domain, _, uid = spec.partition("/")
    return f"{domain}_{uid[:8]}" if domain != "v2" else f"v2_{uid}"


def matrix(combos: list[list[str]], prefix: str, modes: list[str], solo: int) -> list[str]:
    """Run list lines. Every task order is a rotation of the combo (A first, B first, ...); ``modes`` are
    ``mode:repeats`` items; ``solo`` baseline runs per distinct task."""
    lines, tasks = [], []
    for label, *combo in combos:
        tasks += [t for t in combo if t not in tasks]
        for item in modes:
            mode, _, reps = item.partition(":")
            orders = [combo] if mode == "isolated" else [combo[i:] + combo[:i] for i in range(len(combo))]
            for k, order in enumerate(orders):
                for r in range(1, int(reps or 1) + 1):
                    lines.append(f"{prefix}-{label}-{mode[:3]}-o{k + 1}-r{r} {mode} {' '.join(order)}")
    for t in tasks:
        lines += [f"{prefix}-solo-{short(t)}-r{r} solo {t}" for r in range(1, solo + 1)]
    return lines


def remove_containers(run_name: str) -> int:
    ids = subprocess.run(["docker", "ps", "-aq", "--filter", f"label=oscombo.run={run_name}"],
                         capture_output=True, text=True).stdout.split()
    if ids:
        subprocess.run(["docker", "rm", "-f", *ids], capture_output=True)
    return len(ids)


def cmd_queue(a: argparse.Namespace) -> int:
    from .analyze import is_infra
    root = Path(a.out_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    passthrough = a.run_args
    log = open(root / f"queue_{Path(a.list).stem}.log", "a")

    def say(msg: str) -> None:
        log.write(f"{time.strftime('%H:%M:%S', time.gmtime())} {msg}\n")
        log.flush()

    repo = str(Path(__file__).resolve().parents[1])
    pythonpath = repo + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    active: dict[str, tuple[subprocess.Popen, float]] = {}  # run name -> (process, start time)

    def launch(run: list[str]) -> None:
        name, mode, *tasks = run
        out = root / name
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        cmd = [sys.executable, "-m", "oscombo", "run", "--mode", mode, "--tasks", *tasks, "--out", str(out),
               "--label", f"run={name}", *passthrough]
        with open(out / "driver.log", "w") as driver:
            p = subprocess.Popen(cmd, stdout=driver, stderr=subprocess.STDOUT, start_new_session=True,
                                 env={**os.environ, "OSCOMBO_RUN_LABEL": name, "PYTHONPATH": pythonpath})
        active[name] = (p, time.monotonic())
        say(f"start {name}")

    def finished(name: str) -> None:
        f = root / name / "result.json"
        r = json.loads(f.read_text()) if f.exists() else {}
        agents = {k: (v["status"], v["steps"]) for k, v in (r.get("agents") or {}).items()}
        say(f"done  {name} scores={r.get('scores')} agents={agents} {(r.get('error') or '')[:120]}")

    def drain(runs: list[list[str]]) -> None:
        todo = [r for r in runs if not (root / r[0] / "result.json").exists()]
        while todo or active:
            for name, (p, started) in list(active.items()):
                if p.poll() is not None:
                    del active[name]
                    finished(name)
                elif a.run_timeout and time.monotonic() - started > a.run_timeout:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
                    del active[name]
                    say(f"kill  {name} after {a.run_timeout:.0f}s, removed {remove_containers(name)} container(s)")
            if todo and len(active) < a.lanes:
                launch(todo.pop(0))
                time.sleep(a.stagger)  # do not boot several Guests in the same second
                continue
            time.sleep(10)

    runs = read_list(a.list)
    drain(runs)
    retry = []
    for run in runs:
        f = root / run[0] / "result.json"
        if not f.exists() or is_infra(json.loads(f.read_text())):
            if f.exists():
                (root / "_infra").mkdir(exist_ok=True)
                shutil.move(str(root / run[0]), str(root / "_infra" / f"{run[0]}.{time.strftime('%H%M%S')}"))
            retry.append(run)
    say(f"infra-retry pass: {len(retry)} run(s)")
    drain(retry)
    if a.archive:
        Path(a.archive).mkdir(parents=True, exist_ok=True)
        tgz = Path(a.archive) / f"{Path(a.list).stem}_{time.strftime('%Y%m%d_%H%M', time.gmtime())}.tgz"
        with tarfile.open(tgz, "w:gz") as tar:
            for run in runs:
                if (root / run[0]).exists():
                    tar.add(root / run[0], arcname=run[0])
        say(f"archived to {tgz}")
    say("queue finished")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="oscombo", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="one run")
    p.add_argument("--mode", required=True, choices=("solo", "sequential", "parallel", "isolated", "shadow"))
    p.add_argument("--tasks", nargs="+", required=True, help="task specs: <domain>/<uuid>, v2/<NNN>, or a file")
    p.add_argument("--out", required=True)
    add_run_args(p)

    m = sub.add_parser("matrix", help="expand a combo file into a run list (stdout)")
    m.add_argument("combos", help="combo file: <label> <task> <task> [...] per line")
    m.add_argument("--prefix", required=True, help="run name prefix, e.g. the experiment id")
    m.add_argument("--mode", action="append", metavar="MODE:REPEATS",
                   help="default: parallel:2 sequential:1; controls: isolated:1 shadow:1")
    m.add_argument("--solo", type=int, default=1, help="solo baseline runs per distinct task")

    q = sub.add_parser("queue", help="a list of runs with a concurrency cap")
    q.add_argument("list", help="run list file: <name> <mode> <task> [<task> ...] per line")
    q.add_argument("--out-root", required=True)
    q.add_argument("--lanes", type=int, default=4, help="max concurrent runs (Guests per run: 1, isolated: N)")
    q.add_argument("--stagger", type=float, default=20.0, help="s between launches")
    q.add_argument("--run-timeout", type=float, default=0, help="kill a run after this many s (0 = never)")
    q.add_argument("--archive", help="write a tarball of the runs here when done")
    q.epilog = "Arguments after `--` are passed to every `run` (model, harness, max steps, ...)."

    sub.add_parser("analyze", help="aggregate results (see `oscombo analyze --help`)")

    c = sub.add_parser("cleanup", help="remove the Guest containers of a killed run")
    c.add_argument("run_name")

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["analyze"]:
        from .analyze import main as analyze_main
        return analyze_main(argv[1:])
    run_args = argv[argv.index("--") + 1:] if "--" in argv else []
    a = ap.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    a.run_args = run_args
    logging.basicConfig(level=os.environ.get("OSCOMBO_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "matrix":
        print("\n".join(matrix(read_list(a.combos), a.prefix, a.mode or ["parallel:2", "sequential:1"], a.solo)))
        return 0
    if a.cmd == "queue":
        return cmd_queue(a)
    if a.cmd == "cleanup":
        print(f"removed {remove_containers(a.run_name)} container(s)")
        return 0
    return 2

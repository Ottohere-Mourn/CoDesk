"""One frozen original OSWorld pair, one native harness, one execution mode."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import time
from types import SimpleNamespace

from experiments.freehand_vm10 import install_provider, load_module, save


def install_observer(project, output, watched):
    from oscombo import combo
    module = load_module("paragui_mini_osworld_agent", project / "runtime/mini_osworld/agent.py")
    original_setup, original_evaluate = combo.setup_tasks, combo.evaluate_tasks
    state = {}
    root = "/home/user/.paragui-observer"
    q = shlex.quote
    def setup(env, tasks, probe=None):
        result = original_setup(env, tasks, probe)
        rpc = module.FreehandOSWorldAgent()
        rpc.env = SimpleNamespace(controller=env.controller)
        state["rpc"] = rpc
        try:
            rpc._bash("mkdir -p " + q(root))
            rpc._upload((Path(__file__).parent / "guest_observer.py").read_bytes(), root + "/observer.py")
            rpc._upload(json.dumps(watched).encode(), root + "/watch.json")
            rpc._bash("nohup setsid env DISPLAY=:0 python3 " + q(root + "/observer.py") + " " + q(root)
                      + " > " + q(root + "/observer.log") + " 2>&1 < /dev/null &")
        except Exception as error:
            save(output / "observer-error.json", {"stage": "start", "error": str(error)})
        return result
    def evaluate(env, tasks, declared_fail, result):
        rpc = state.get("rpc")
        if rpc is not None:
            try:
                rpc._bash("touch " + q(root + "/STOP"))
                time.sleep(0.7)
                data = rpc._file(root + "/events.jsonl")
                if data:
                    (output / "observer.jsonl").write_bytes(data)
                rpc._bash("tar -czf /tmp/paragui-observer.tar.gz -C /home/user .paragui-observer", timeout=60)
                data = rpc._file("/tmp/paragui-observer.tar.gz", timeout=90)
                if data:
                    (output / "observer.tar.gz").write_bytes(data)
            except Exception as error:
                save(output / "observer-error.json", {"stage": "collect", "error": str(error)})
        return original_evaluate(env, tasks, declared_fail, result)
    combo.setup_tasks, combo.evaluate_tasks = setup, evaluate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--pair", required=True)
    parser.add_argument("--harness", choices=["codex", "freehand"], required=True)
    parser.add_argument("--mode", choices=["parallel", "sequential"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args(argv)
    project, output = args.project.resolve(), args.out.resolve()
    if (output / "experiment.json").exists():
        raise FileExistsError(f"Existing trial: {output}")
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((project / "manifest.json").read_text())
    case = next(c for c in manifest["cases"] if c["name"] == args.pair)
    config = json.loads((project / "private/api.json").read_text())
    os.environ.update(API_URL=config["base_url"].rstrip("/") + "/responses", API_KEY=config["api_key"],
        MODEL=config["model"], REASONING_EFFORT=config.get("reasoning_effort", "high"),
        OPENAI_BASE_URL=config["base_url"], OSWORLD_DIR=str(project / "source"),
        OSWORLD_BENCHMARK_RELEASE="osworld-v2.1")
    sys.path.insert(0, str(project / "runtime"))
    from oscombo.osworld import activate
    activate()
    install_provider(project, output)
    install_observer(project, output, case.get("watch_files", []))
    from oscombo.runner import RunConfig, run
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"Received signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    harness = "experiments.codex_vm10:CodexGuestHarness" if args.harness == "codex" else "experiments.freehand_vm10:FreehandHarness"
    agent = {"harness": harness, "model": config["model"], "effort": config.get("reasoning_effort", "high"),
             "instruction_suffix": "\nThe task VM's sudo password is osworld-public-evaluation.",
             "options": {"project": str(project), "agent_path": str(project / "runtime/mini_osworld/agent.py"),
                         "timeout": args.timeout}}
    experiment = {"pair": args.pair, "harness": args.harness, "mode": args.mode,
        "tasks": case["tasks"], "resource": case["resource"], "candidate_risk": case["risk"],
        "model": config["model"], "base_url": config["base_url"], "effort": agent["effort"],
        "timeout_per_agent_s": args.timeout, "capabilities": "Bash, files, scripts, GUI inside guest",
        "guest_vcpus": 4, "guest_ram": "8G", "started_at": time.time(),
        "observer": "Passive focus and small-file snapshots at 0.5-second intervals"}
    save(output / "experiment.json", experiment)
    result = run(RunConfig(mode=args.mode, tasks=case["tasks"], out=output, agents=[agent], max_steps=1000,
        image=str(project / "source/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"),
        extra={"pair": args.pair, "comparison_harness": args.harness,
               "trace_step_unit": "model_response", "focus_interference_measured": False,
               "observer_available": True}))
    print(json.dumps({"pair": args.pair, "harness": args.harness, "mode": args.mode,
        "scores": result.get("scores"), "error": result.get("error"),
        "agents": {name: {k: value.get(k) for k in ["status", "error", "steps", "usage"]}
                   for name, value in result.get("agents", {}).items()}}), flush=True)
    return int(bool(result.get("error") or result.get("eval_errors") or
                    any(a.get("status") == "error" for a in result.get("agents", {}).values())))


if __name__ == "__main__":
    raise SystemExit(main())

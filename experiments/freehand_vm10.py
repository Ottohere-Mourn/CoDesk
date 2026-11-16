"""Run oscombo with mini-harness's existing Freehand OSWorld adapter on VM10.

The model runs inside the shared guest. Only the host gateway receives the API
key. Freehand's initial 1000-turn budget remains editable by the agent; the host
enforces a separate wall-clock limit. Trace steps count model responses, not GUI
actions, and do not provide oscombo's focused-window interference metric.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace
import uuid

from oscombo.harness.base import AgentContext, AgentResult, Harness


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def load_module(name: str, path: Path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load mini-harness adapter: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def read_trace(directory: Path, t0: float) -> tuple[list[dict], dict]:
    """Preserve successful model responses and separately count failed requests."""
    calls = {}
    blobs = directory / "blobs.jsonl"
    if blobs.exists():
        for line in blobs.open():
            record = json.loads(line)
            value = record["v"]
            if isinstance(value, dict) and value.get("type") in ("function_call", "custom_tool_call"):
                calls[record["h"]] = value
    trace, failures = [], []
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    usage_records = requests = 0
    events = directory / "requests.jsonl"
    for line in events.open() if events.exists() else []:
        event = json.loads(line)
        if event.get("kind") == "request":
            requests += 1
        if event.get("kind") != "response":
            continue
        if not event.get("ok"):
            failures.append({k: event.get(k) for k in ("n", "status", "error", "latency_s")})
            continue
        tools = [calls[h] for h in event.get("output", []) if h in calls]
        trace.append({"step": len(trace) + 1, "t": round(event["ts"] - t0, 3),
                      "infer_s": event.get("latency_s"), "tool_calls": tools,
                      "actions": [], "done": any(c.get("name") == "finish" for c in tools),
                      "fail": False})
        if event.get("usage"):
            usage_records += 1
            for key in usage:
                usage[key] += event["usage"].get(key) or 0
    return trace, {"model_requests": requests, "model_responses": len(trace),
                   "api_errors": failures, "usage": usage if usage_records else None,
                   "usage_records": usage_records, "step_unit": "model_response"}


def outcome_status(outcome: dict, error: str | None) -> str:
    if error or outcome.get("error"):
        return "error"
    if outcome.get("status") == "completed":
        return "done"
    if outcome.get("status") == "time_budget_exhausted":
        return "timeout"
    if outcome.get("agent_status") == "stopped_max_turns":
        return "max_steps"
    return "error"


class FreehandHarness(Harness):
    def prepare(self, ctx: AgentContext) -> None:
        options = self.spec.get("options", {})
        module = load_module("paragui_mini_osworld_agent", Path(options["agent_path"]))
        self.directory = ctx.out / ctx.name
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "instruction.txt").write_text(ctx.instruction)
        self.agent = module.FreehandOSWorldAgent(
            model=self.spec["model"], reasoning_effort=self.spec.get("effort") or "high",
            timeout_sec=float(options.get("timeout", 1800)),
        )
        # Share the controller/desktop, while keeping per-agent bookkeeping apart.
        self.agent.env = SimpleNamespace(controller=ctx.guest.env.controller,
                                         provider=ctx.guest.env.provider,
                                         user_simulator=None, action_history=[])
        self.agent.result_dir = str(self.directory)
        from experiments.guest_rpc import protect_guest_reads
        protect_guest_reads(self.agent, self.directory)

    def run(self, ctx: AgentContext) -> AgentResult:
        started = time.time()
        state = {"agent": ctx.name, "task": ctx.task_id, "status": "running",
                 "started_at": started, "model": self.spec["model"]}
        save(self.directory / "state.json", state)
        error = None
        try:
            self.agent.predict(ctx.instruction)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        outcome = self.agent.last_outcome or {}
        status = outcome_status(outcome, error)
        if status == "error" and not error:
            error = outcome.get("error") or f"Freehand stopped: {outcome.get('agent_status')}"
        trace, metrics = read_trace(self.directory / "freehand/phase-01/gateway-trace", ctx.t0)
        save(self.directory / "state.json", state | {"status": status, "error": error,
                                                      "finished_at": time.time(), **metrics})
        return AgentResult(status=status, error=error, trace=trace,
                           extra={"agent_s": round(time.time() - started, 3), **metrics,
                                  "freehand_outcome": outcome, "initial_max_turns": 1000,
                                  "wall_timeout_s": self.agent.timeout_sec})


def install_provider(project: Path, output: Path) -> None:
    """Use the already installed KVM image and network with this run's own disks."""
    import requests
    import desktop_env.desktop_env as desktop_module
    from desktop_env.providers.docker.provider import DockerProvider

    network = json.loads((project / "network.json").read_text())
    original_factory = desktop_module.create_vm_manager_and_provider
    containers = []

    class ParaGUIProvider(DockerProvider):
        def __init__(self, region=None):
            super().__init__(region)
            self.network_config = network
            self.environment.update(RAM_SIZE="8G", CPU_CORES="4", DISK_SIZE="64G",
                                    USER_PORTS="3000,5000,5910,8000,8080,8081,9222")
            self.private_ip = None

        def start_emulator(self, path_to_vm, headless, os_type):
            if os_type != "Ubuntu" or not Path("/dev/kvm").exists():
                raise RuntimeError("This experiment requires Ubuntu and KVM")
            name = "paragui-freehand-" + uuid.uuid4().hex[:12]
            storage = project / "vm-storage" / name
            storage.mkdir(parents=True, exist_ok=False)
            devices = ["/dev/kvm"]
            if Path("/dev/net/tun").exists():
                devices.append("/dev/net/tun")
            self.container = self.client.containers.run(
                "happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9",
                name=name, environment=self.environment, cap_add=["NET_ADMIN"], devices=devices,
                volumes={str(Path(path_to_vm).resolve()): {"bind": "/System.qcow2", "mode": "ro"},
                         str(storage): {"bind": "/storage", "mode": "rw"}},
                network=network["network"], nano_cpus=4_000_000_000, mem_limit="10g", shm_size="1g",
                labels={"mini-harness.project": "paragui", "paragui.run": output.name}, detach=True,
            )
            self.container.reload()
            self.private_ip = self.container.attrs["NetworkSettings"]["Networks"][network["network"]]["IPAddress"]
            self.server_port, self.chromium_port, self.vnc_port, self.vlc_port = 5000, 9222, 8006, 8080
            containers.append({"name": name, "id": self.container.id, "ip": self.private_ip,
                               "storage": str(storage), "created_at": time.time()})
            save(output / "containers.json", {"containers": containers})
            session = requests.Session()
            session.trust_env = False
            deadline = time.monotonic() + 600
            try:
                while time.monotonic() < deadline:
                    self.container.reload()
                    if self.container.status != "running":
                        raise RuntimeError("Guest container exited during boot")
                    try:
                        response = session.get(f"http://{self.private_ip}:5000/screenshot", timeout=10)
                        if response.status_code == 200 and response.content.startswith(b"\x89PNG"):
                            return
                    except requests.RequestException:
                        pass
                    time.sleep(2)
                raise TimeoutError("Guest did not become ready within 600 seconds")
            except BaseException:
                self.stop_emulator(path_to_vm)
                raise
            finally:
                session.close()

        def get_ip_address(self, path_to_vm):
            if self.private_ip is None:
                raise RuntimeError("Guest has not started")
            return f"{self.private_ip}:5000:9222:8006:8080"

        def stop_emulator(self, path_to_vm, region=None, *args, **kwargs):
            if self.container is not None:
                container = self.container
                (output / f"{container.name}.log").write_bytes(container.logs(tail=300))
                try:
                    container.stop(timeout=20)
                finally:
                    container.remove(v=True, force=True)
                    self.container = None
                    self.private_ip = None
                for record in containers:
                    if record["id"] == container.id:
                        record["stopped_at"] = time.time()
                save(output / "containers.json", {"containers": containers})

    def factory(provider_name, region=None, **kwargs):
        manager, provider = original_factory(provider_name, region, **kwargs)
        return manager, ParaGUIProvider(region) if provider_name == "docker" else provider

    desktop_module.create_vm_manager_and_provider = factory


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("/data/yuke/paraGUI"))
    parser.add_argument("--osworld", type=Path, default=Path("/data/yuke/osworld-freehand/source"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--mode", choices=["parallel", "sequential", "solo"], default="parallel")
    parser.add_argument("--tasks", nargs="+", default=[
        "chrome/bb5e4c0d-f964-439c-97b6-bdb9747de3f4",
        "libreoffice_calc/42e0a640-4f19-4b28-973d-729602b5a4a7",
    ])
    args = parser.parse_args(argv)
    project, output = args.project.resolve(), args.out.resolve()
    if (output / "result.json").exists() or (output / "experiment.json").exists():
        raise FileExistsError(f"Refusing to overwrite an existing result: {output}")
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads((project / "private/api.json").read_text())
    os.environ.update(API_URL=config["base_url"].rstrip("/") + "/responses", API_KEY=config["api_key"],
                      MODEL=config["model"], REASONING_EFFORT=config.get("reasoning_effort", "high"),
                      OPENAI_BASE_URL=config["base_url"], OSWORLD_DIR=str(args.osworld.resolve()),
                      OSWORLD_BENCHMARK_RELEASE="osworld-v2.1")
    sys.path.insert(0, str(project / "runtime"))
    from oscombo.osworld import activate
    activate()
    install_provider(project, output)
    from oscombo.runner import RunConfig, run

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"Received signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    save(output / "experiment.json", {"model": config["model"], "base_url": config["base_url"],
        "reasoning_effort": config.get("reasoning_effort", "high"), "mode": args.mode,
        "tasks": args.tasks, "agent_timeout_s": args.timeout, "guest_vcpus": 4, "guest_ram": "8G",
        "harness": "mini-harness Freehand", "desktop_access": "Bash, files, scripts, and GUI in guest",
        "image_history_limit": 4, "initial_max_turns": 1000, "started_at": time.time()})
    result = run(RunConfig(mode=args.mode, tasks=args.tasks, out=output, max_steps=1000,
        image=str(args.osworld.resolve() / "docker_vm_data/osworld-v2-ubuntu-x86.qcow2"),
        agents=[{"harness": "experiments.freehand_vm10:FreehandHarness", "model": config["model"],
                 "effort": config.get("reasoning_effort", "high"), "options": {
                     "agent_path": str(project / "runtime/mini_osworld/agent.py"), "timeout": args.timeout}}],
        extra={"experiment": "OSWorld original mixed desktop tasks via mini-harness",
               "trace_step_unit": "model_response", "focus_interference_measured": False}))
    print(json.dumps({"out": str(output), "scores": result.get("scores"), "error": result.get("error"),
                      "agents": {k: {f: v.get(f) for f in ("status", "steps", "error", "usage")}
                                 for k, v in result.get("agents", {}).items()}}), flush=True)
    return int(bool(result.get("error") or result.get("eval_errors") or
                    any(v.get("status") == "error" for v in result.get("agents", {}).values())))


if __name__ == "__main__":
    raise SystemExit(main())

"""Batch-runner plugins. Fake execution is test-only; A6000 refuses incomplete task bindings."""
from __future__ import annotations
import importlib,os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from .fake_runtime_backend_v1 import FakeGuestBackend,fake_actor_factory
from .runtime_execution_v1 import DeterministicRuntimeScheduler,EventGate,Outcome,RuntimeExecutor
from .runtime_v1 import RuntimeBackendUnavailable

class FakeRuntimePlugin:
    """Exercises orchestration only. Never benchmark, Guest, or model evidence."""
    def __init__(self): self.executor=RuntimeExecutor()
    def execute_run(self,adapter,plan,run,output):
        active=list(run["active_actors"]); backend=FakeGuestBackend()
        policy=plan["topologies"][run["topology"]]["schedule_policy_id"]
        gate=None if "round-robin" in policy else EventGate([{"kind":"action_complete","actor_id":a} for a in active])
        scheduler=DeterministicRuntimeScheduler(fake_actor_factory,backend,step_budget=20,gate=gate)
        result=self.executor.execute(adapter,plan,run,backend,scheduler,Path(output))
        result["evidence_class"]="FAKE_ORCHESTRATION_ONLY";result["fake_backend_only"]=True
        Path(output,"result.json").write_text(__import__("json").dumps(result,indent=2,sort_keys=True)+"\n")
        return result

class A6000RuntimePlugin:
    """Real executor factory. It does not start anything until execute_run()."""
    def __init__(self,repo_root:Path): self.repo_root=repo_root
    def _binding_registry(self):
        spec=os.environ.get("SWCUB_RUNTIME_BINDING_FACTORY","")
        if not spec: return None
        module,attr=spec.split(":",1);return getattr(importlib.import_module(module),attr)()
    def execute_run(self,adapter,plan,run,output):
        import json
        out=Path(output);out.mkdir(parents=True,exist_ok=True);binding=plan.get("runtime_execution_binding",{})
        registry=self._binding_registry(); row=(registry or {}).get(plan["workflow_id"],{})
        missing=[]
        for key in ("setup","initial_verifier","evaluator","event_gate"):
            if not callable(row.get(key)):missing.append(key)
        if registry is None:missing.append("SWCUB_RUNTIME_BINDING_FACTORY")
        endpoint=os.environ.get("SWCUB_QWEN_INFERENCE_URL","").strip()
        if str(run.get("model","")).lower().startswith("qwen") and not endpoint:missing.append("SWCUB_QWEN_INFERENCE_URL")
        if endpoint:
            parsed=urlsplit(endpoint)
            if parsed.scheme!="http" or parsed.hostname not in {"127.0.0.1","localhost"} or not parsed.port:
                missing.append("loopback/reverse-tunnel endpoint URL policy")
            else:
                try:
                    with urlopen(endpoint.rstrip("/")+"/health",timeout=10) as response: health=json.loads(response.read())
                    if not health.get("ready") or health.get("model")!="Qwen3-VL-30B-A3B-Instruct":
                        missing.append("pinned Qwen endpoint health")
                except Exception as exc: missing.append(f"Qwen endpoint health: {type(exc).__name__}")
        if missing:
            result={"run_id":run["run_id"],"base_run_id":run.get("base_run_id"),
              "instance_id":run["instance_id"],"workflow_id":run["workflow_id"],
              "status":Outcome.BLOCKED_RUNTIME_BACKEND.value,"guest_started":False,
              "missing_components":missing,"unresolved_plan_components":binding.get("missing_components",[]),
              "evidence_class":"PREFLIGHT_ONLY"}
            (out/"result.json").write_text(json.dumps(result,indent=2)+"\n");return result
        from .osworld_guest_backend_v1 import A6000OSWorldBackend
        from .osworld_qwen_actor_factory import OSWorldQwenActorFactory
        observers={plan["workflow_id"]:row["evaluator"]}
        backend=A6000OSWorldBackend.from_environment(self.repo_root)
        backend.evaluator_observers=observers
        backend.workflow_setup_handlers={plan["workflow_id"]:row["setup"]}
        scheduler_holder={}
        actor_factory=OSWorldQwenActorFactory(backend.osworld_root,endpoint,max_steps=20,
          event_sink=lambda event:scheduler_holder.get("scheduler") and scheduler_holder["scheduler"].observe_event(event))
        policy=plan["topologies"][run["topology"]]["schedule_policy_id"]
        gate=row["event_gate"](plan,run)
        scheduler=DeterministicRuntimeScheduler(actor_factory,backend,step_budget=20,gate=gate)
        scheduler_holder["scheduler"]=scheduler
        result=RuntimeExecutor().execute(adapter,plan,run,backend,scheduler,out)
        result["evidence_class"]="REAL_OSWORLD_RUNTIME_UNVALIDATED"
        (out/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        return result

def build_fake_executor(): return FakeRuntimePlugin()
def build_a6000_executor(): return A6000RuntimePlugin(Path(__file__).resolve().parents[1])

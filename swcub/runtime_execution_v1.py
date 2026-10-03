"""Runtime episode lifecycle, deterministic scheduler, and explicit outcome taxonomy.

This module orchestrates existing OSWorld agents and injected backends. It does
not implement model planning, grounding, or action parsing.
"""
from __future__ import annotations
from dataclasses import asdict
from enum import Enum
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Protocol, Sequence
from .runtime_v1 import RuntimeBackendUnavailable, WorkflowRuntimeAdapter

class Outcome(str, Enum):
    SUCCESS="SUCCESS"; TASK_FAILURE="TASK_FAILURE"; MODEL_FAILURE="MODEL_FAILURE"
    INVALID_INFRA="INVALID_INFRA"; BLOCKED_RESOURCE="BLOCKED_RESOURCE"
    BLOCKED_RUNTIME_BACKEND="BLOCKED_RUNTIME_BACKEND"; RESET_FAILURE="RESET_FAILURE"
    EVALUATOR_FAILURE="EVALUATOR_FAILURE"; TIMEOUT="TIMEOUT"

class ActorFactory(Protocol):
    def __call__(self, spec: Any, artifact_dir: Path, action_boundary: Callable[[str, Any], None]) -> Any: ...
class ContextProvider(Protocol):
    def actor_context(self, actor_id: str, guest: Any) -> Any: ...
    def action_count(self, guest: Any) -> int: ...
    def refresh_after_turn(self, guests: Sequence[Any]) -> None: ...

class EventGate:
    """Consume observer events in a fixed order; never changes actor prompts/actions."""
    def __init__(self, expected: Sequence[Mapping[str, Any]]):
        self.expected=[dict(row) for row in expected]; self.index=0; self.events=[]
    @property
    def complete(self): return self.index >= len(self.expected)
    def observe(self, event: Mapping[str, Any]) -> bool:
        row=dict(event); row["gate_index"]=self.index; self.events.append(row)
        def value_at(obj,path):
            value=obj
            for part in path.split("."):
                if not isinstance(value,Mapping) or part not in value: return None
                value=value[part]
            return value
        if not self.complete and all(value_at(row,k)==v for k,v in self.expected[self.index].items()):
            self.index+=1; return True
        return False

class DeterministicRuntimeScheduler:
    """Run existing actors through run_step(), switching only after action completion."""
    def __init__(self, actor_factory: ActorFactory, context_provider: ContextProvider, *,
                 step_budget=20, max_actions_per_turn=1, timeout_seconds=900,
                 event_sink: Callable[[dict[str,Any]],None]|None=None, gate: EventGate|None=None):
        if min(step_budget,max_actions_per_turn)<1 or timeout_seconds<=0: raise ValueError("invalid scheduler limits")
        self.actor_factory=actor_factory; self.context_provider=context_provider
        self.step_budget=step_budget; self.max_actions_per_turn=max_actions_per_turn
        self.timeout_seconds=timeout_seconds; self.event_sink=event_sink or (lambda _e:None); self.gate=gate
        self.event_history=[]
    def execute(self, actor_specs, schedule_policy_id, guests, topology, artifact_root,
                active_actor_ids=None):
        if topology not in {"solo","ma_id","ma_sd"}: raise ValueError("unsupported topology")
        active=set(active_actor_ids or [x.actor_id for x in actor_specs])
        specs=[x for x in actor_specs if x.actor_id in active]
        if not specs or {x.actor_id for x in specs}!=active: raise ValueError("actor selection mismatch")
        if topology=="solo" and (len(specs)!=1 or len(guests)!=1): raise ValueError("Solo requires one actor/Guest")
        if topology=="ma_id" and len(guests)!=len(specs): raise ValueError("MA-ID requires one Guest per actor")
        if topology=="ma_sd" and len(guests)!=1: raise ValueError("MA-SD requires one shared Guest")
        if not isinstance(schedule_policy_id,str) or not schedule_policy_id:
            raise RuntimeBackendUnavailable("missing frozen schedule policy id")
        if "round-robin" in schedule_policy_id and schedule_policy_id!="round_robin_v1":
            mode="round_robin_v1"
        elif schedule_policy_id in {"round_robin_v1","fixed_order_v1","event_gated_v1"}:
            mode=schedule_policy_id
        else:
            # Frozen workflow policies are namespaced task protocols. Their
            # observer-event gate must be injected; do not silently flatten them.
            mode="event_gated_v1"
        artifact_root.mkdir(parents=True,exist_ok=True)
        guest_for={s.actor_id:guests[0 if topology!="ma_id" else i] for i,s in enumerate(specs)}
        actors={}; states={s.actor_id:{"terminated":False,"turns":0,"gui_actions":0,"error":None} for s in specs}
        action_count={}; paused=set(); order=[s.actor_id for s in specs]
        def boundary(actor_id, action):
            action_count[actor_id]=action_count.get(actor_id,0)+1
            try: action_payload=json.dumps(action,sort_keys=True,ensure_ascii=False,default=str)
            except Exception: action_payload=repr(action)
            self._emit({"kind":"action_complete","actor_id":actor_id,"action_in_turn":action_count[actor_id],
                "action_type":type(action).__name__,"action_payload":action_payload})
            if action_count[actor_id]>=self.max_actions_per_turn:
                pause=getattr(actors[actor_id],"pause",None)
                if callable(pause): pause()
                paused.add(actor_id)
        for s in specs:
            actors[s.actor_id]=self.actor_factory(s,artifact_root/"actors"/s.actor_id,
                lambda action,aid=s.actor_id:boundary(aid,action))
            reset=getattr(actors[s.actor_id],"reset",None)
            if callable(reset): reset()
        contexts={aid:self.context_provider.actor_context(aid,guest_for[aid]) for aid in order}
        start=time.monotonic(); cursor=0; turns=0; errors={}; terminated=set()
        while len(terminated)+len(errors)<len(order):
            if time.monotonic()-start>self.timeout_seconds:
                for aid in order:
                    if aid not in terminated and aid not in errors: errors[aid]="TIMEOUT: episode deadline exceeded"
                break
            runnable=[a for a in order if a not in terminated and a not in errors]
            if not runnable: break
            if mode=="fixed_order_v1": chosen=runnable[0]
            elif mode=="event_gated_v1":
                if self.gate is None:
                    raise RuntimeBackendUnavailable(f"schedule policy {schedule_policy_id} requires an injected event gate")
                if not self.gate.complete:
                    next_actor=self.gate.expected[self.gate.index].get("actor_id")
                    chosen=next((a for a in runnable if a==next_actor),runnable[cursor%len(runnable)])
                else: chosen=runnable[cursor%len(runnable)]
            else: chosen=runnable[cursor%len(runnable)]
            cursor=(order.index(chosen)+1)%len(order); paused.discard(chosen)
            resume=getattr(actors[chosen],"resume",None)
            if callable(resume): resume()
            before=self.context_provider.action_count(guest_for[chosen]); action_count[chosen]=0
            self._emit({"kind":"actor_resume","actor_id":chosen,"turn":states[chosen]["turns"]+1,"topology":topology})
            try:
                done=bool(actors[chosen].run_step(contexts[chosen]))
            except TimeoutError as exc: errors[chosen]=f"TIMEOUT: {exc}"; done=False
            except Exception as exc: errors[chosen]=f"MODEL_FAILURE: {type(exc).__name__}: {exc}"; done=False
            states[chosen]["turns"]+=1
            states[chosen]["gui_actions"]+=max(0,self.context_provider.action_count(guest_for[chosen])-before)
            states[chosen]["terminated"]=bool(getattr(actors[chosen],"terminated",done))
            if done or states[chosen]["terminated"]: terminated.add(chosen)
            if states[chosen]["turns"]>=self.step_budget and chosen not in terminated and chosen not in errors:
                errors[chosen]=f"MODEL_FAILURE: actor exceeded {self.step_budget} turns"
            self.context_provider.refresh_after_turn(guests)
            self._emit({"kind":"turn_complete","actor_id":chosen,"turn":states[chosen]["turns"],"terminated":states[chosen]["terminated"]})
            turns+=1
        for aid,error in errors.items(): states[aid]["error"]=error
        status="SCHEDULER_COMPLETE" if not errors else ("TIMEOUT" if any(x.startswith("TIMEOUT") for x in errors.values()) else "MODEL_FAILURE")
        return {"status":status,"actor_terminated":{a:a in terminated for a in order},"actor_execution":states,
                "errors":errors,"turns":turns,"gui_actions":{a:states[a]["gui_actions"] for a in order},
                "gate_events":self.gate.events if self.gate else [],"schedule_policy_id":schedule_policy_id,
                "elapsed_seconds":round(time.monotonic()-start,3)}
    def observe_event(self,event):
        row={"ts_unix_ns":time.time_ns(),**dict(event)}
        self.event_history.append(row)
        advanced=self.gate.observe(row) if self.gate else False
        self.event_sink(row)
        if advanced: self.event_sink({"ts_unix_ns":time.time_ns(),"kind":"gate_advanced","gate_index":self.gate.index})
        return advanced
    def _emit(self,event): self.observe_event(event)

class RuntimeExecutor:
    """Run lifecycle; oracle outcome remains independent of actor termination."""
    def execute(self, adapter: WorkflowRuntimeAdapter, plan: dict[str,Any], run_config: dict[str,Any],
                backend: Any, scheduler: DeterministicRuntimeScheduler, output: Path):
        run_id=run_config["run_id"]; topology=run_config["topology"]; active=list(run_config["active_actors"])
        output.mkdir(parents=True,exist_ok=True); ep=output/"events.jsonl"
        def emit(e):
            with ep.open("a",encoding="utf-8") as f: f.write(json.dumps(e,sort_keys=True,ensure_ascii=False)+"\n")
        prior_event_sink=scheduler.event_sink
        def dispatch_event(event):
            emit(event)
            prior_event_sink(event)
        scheduler.event_sink=dispatch_event
        result={"run_id":run_id,"base_run_id":run_config.get("base_run_id"),"instance_id":plan["instance_id"],
                "workflow_id":plan["workflow_id"],"topology":topology,"status":"STARTING",
                "actor_terminated":{},"oracle_success":None,"joint_success":None,"infra_valid":False}
        emit({"kind":"run_started","run_id":run_id,"plan_sha256":plan.get("plan_sha256")})
        provenance={"run_id":run_id,"base_run_id":run_config.get("base_run_id"),
          "instance_id":plan["instance_id"],"workflow_id":plan["workflow_id"],
          "plan_sha256":plan.get("plan_sha256"),"plan_provenance":plan.get("provenance"),
          "model":run_config.get("model"),"backend_class":type(backend).__name__,"fake_backend_only":bool(getattr(backend,"FAKE_BACKEND_ONLY",False)),
          "started_unix_ns":time.time_ns(),"host":__import__("socket").gethostname()}
        (output/"provenance.json").write_text(json.dumps(provenance,indent=2,sort_keys=True)+"\n")
        guests=[]
        try:
            set_callback=getattr(backend,"set_scheduler_event_callback",None)
            if callable(set_callback): set_callback(scheduler.observe_event)
            backend.scheduler_event_history=scheduler.event_history
            backend.active_actor_ids=active
            guests=adapter.prepare(plan,topology,backend)
            execution=scheduler.execute(adapter.get_actor_specs(plan,active),
                plan["topologies"][topology]["schedule_policy_id"],guests,topology,output,active_actor_ids=active)
            result["scheduler"]=execution; result["actor_terminated"]=execution["actor_terminated"]
            result["infra_valid"]=True
            try:
                actual=backend.collect_hidden_state(guests,plan)
                score=adapter.evaluate(plan,_StateBackend(actual),guests,active)
                result["evaluator"]=score; result["oracle_success"]=bool(score.get("joint_success")); result["joint_success"]=result["oracle_success"]
            except RuntimeBackendUnavailable as exc:
                result["status"]=Outcome.BLOCKED_RUNTIME_BACKEND.value
                result["evaluator_error"]=f"{type(exc).__name__}: {exc}"
            except Exception as exc:
                result["status"]=Outcome.EVALUATOR_FAILURE.value; result["evaluator_error"]=f"{type(exc).__name__}: {exc}"
            if result["status"]!=Outcome.EVALUATOR_FAILURE.value:
                sched=execution["status"]
                result["status"]=sched if sched in {Outcome.MODEL_FAILURE.value,Outcome.TIMEOUT.value} else (Outcome.SUCCESS.value if result["oracle_success"] else Outcome.TASK_FAILURE.value)
        except RuntimeBackendUnavailable as exc:
            result.update(status=Outcome.INVALID_INFRA.value,infra_valid=False,failure_reason="readiness_or_backend",error=str(exc))
        except Exception as exc:
            result.update(status=Outcome.INVALID_INFRA.value,infra_valid=False,failure_reason="runtime_exception",error=f"{type(exc).__name__}: {exc}")
        finally:
            if guests:
                try: result["artifacts"]=adapter.collect_artifacts(plan,backend,guests,output)
                except Exception as exc: result["artifact_error"]=f"{type(exc).__name__}: {exc}"
                try: result["reset"]=adapter.reset(plan,backend,guests)
                except Exception as exc: result["reset_error"]=f"{type(exc).__name__}: {exc}"; result["status"]=Outcome.RESET_FAILURE.value
                try: result["cleanup"]=adapter.cleanup(plan,backend,guests)
                except Exception as exc: result["cleanup_error"]=f"{type(exc).__name__}: {exc}"
        result["completed_unix_ns"]=time.time_ns()
        (output/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        return result

class _StateBackend:
    def __init__(self,state): self.state=state
    def collect_hidden_state(self,*_args): return self.state

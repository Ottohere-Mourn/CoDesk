"""InstanceSpec-driven workflow runtime registry and offline plan compiler.

Compiling plans is offline. The lifecycle methods require a GuestBackend and a
turn scheduler; this module never creates a Guest by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Protocol, Sequence

from .production_v1 import canonical_bytes, sha256, workflow_registry

RUNTIME_SCHEMA_VERSION = 1
TOPOLOGIES = ("solo", "ma_id", "ma_sd")
ARTIFACTS = ("events.jsonl", "screenshots/", "actor-traces/", "report.json",
             "provenance.json", "resource-events.jsonl", "reset.json")


class RuntimeCompileError(ValueError):
    pass


class RuntimeBackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeActorSpec:
    actor_id: str
    task_domain: str
    goal: str
    target_objects: tuple[str, ...]
    operation: str
    initial_value: str
    expected_value: str
    observation_history_scope: str
    action_budget_scope: str


class GuestBackend(Protocol):
    """Only an explicitly configured implementation may perform Guest effects."""
    def create_owned_guest(self, run_id: str, guest_slot: str, ownership: dict[str, Any]) -> Any: ...
    def clone_workspace(self, plan: dict[str, Any], guest: Any, workspace_id: str) -> None: ...
    def copy_fixture(self, guest: Any, source: Path, guest_path: str, sha256_hex: str) -> None: ...
    def launch_application(self, guest: Any, app: str, target: str) -> None: ...
    def wait_application_ready(self, guest: Any, app: str, target: str) -> dict[str, Any]: ...
    def observe_initial_state(self, guest: Any, plan: dict[str, Any]) -> dict[str, Any]: ...
    def verify_initial_state(self, guest: Any, plan: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]: ...
    def collect_hidden_state(self, guests: Sequence[Any], plan: dict[str, Any]) -> dict[str, Any]: ...
    def collect_artifacts(self, guests: Sequence[Any], plan: dict[str, Any], output: Path) -> dict[str, Any]: ...
    def reset_guest(self, guest: Any, plan: dict[str, Any]) -> dict[str, Any]: ...
    def cleanup_owned_guest(self, guest: Any, ownership: dict[str, Any]) -> dict[str, Any]: ...


class TurnScheduler(Protocol):
    def execute(self, actor_specs: Sequence[RuntimeActorSpec], schedule_policy_id: str,
                guests: Sequence[Any], topology: str, artifact_root: Path) -> dict[str, Any]: ...


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _runtime_commit() -> str:
    result=subprocess.run(["git","-C",str(Path(__file__).resolve().parents[1]),"rev-parse","HEAD"],
                          capture_output=True,text=True)
    return result.stdout.strip() if result.returncode==0 else "unknown"


def _safe_child(root: Path, relative: str) -> Path:
    candidate=(root/relative).resolve()
    if root.resolve() not in candidate.parents:
        raise RuntimeCompileError(f"path escapes suite root: {relative}")
    return candidate


class WorkflowRuntimeAdapter:
    """Declarative adapter: binds one frozen workflow to the shared runtime API."""
    def __init__(self, workflow: dict[str, Any]):
        self.workflow_id=workflow["workflow_id"]
        self.family=workflow["family"]
        self.validation_level=workflow["validation_level"]
        self.required_apps=tuple(dict.fromkeys(workflow.get("required_apps",workflow["task_domains"])))
        self.schedule_policy_id=workflow["schedule_policy_id"]
        self.workflow=workflow
        self.supported_topologies=TOPOLOGIES

    def _validate_record(self, instance: dict[str, Any], suite_root: Path) -> dict[str, Any]:
        if instance.get("workflow_id")!=self.workflow_id or instance.get("family")!=self.family:
            raise RuntimeCompileError("instance does not match registered workflow/family")
        actor_rows=instance.get("actor_goals") or []
        if not actor_rows or len(actor_rows)<2 or len({a["actor_id"] for a in actor_rows})!=len(actor_rows):
            raise RuntimeCompileError("instance must define unique actor goal specs")
        if instance.get("schedule_policy_id")!=self.schedule_policy_id:
            raise RuntimeCompileError("schedule policy differs from frozen workflow contract")
        targets=instance.get("target_objects",{})
        if len(actor_rows)>=2 and set(targets.get("A",[])) & set(targets.get("B",[])):
            raise RuntimeCompileError("Actor A/B targets overlap")
        fixtures=[]
        for asset in instance.get("fixture_files",[]):
            path=_safe_child(suite_root,asset["path"])
            if not path.is_file() or _sha_file(path)!=asset["sha256"]:
                raise RuntimeCompileError(f"fixture missing or hash mismatch: {asset['path']}")
            fixtures.append({**asset,"host_path":str(path)})
        if not fixtures: raise RuntimeCompileError("instance has no fixture assets")
        evaluator_path=_safe_child(suite_root,instance["evaluator_path"])
        if not evaluator_path.is_file() or _sha_file(evaluator_path)!=instance["evaluator_sha256"]:
            raise RuntimeCompileError("private evaluator missing or hash mismatch")
        evaluator=json.loads(evaluator_path.read_text(encoding="utf-8"))
        if not evaluator.get("expected_state") or not evaluator.get("initial_state"):
            raise RuntimeCompileError("evaluator is missing initial/expected state")
        if set(instance.get("topology_compatibility",{}))!=set(TOPOLOGIES):
            raise RuntimeCompileError("topology compatibility contract incomplete")
        if not instance.get("provenance",{}).get("source_code_sha256"):
            raise RuntimeCompileError("source provenance missing")
        return {"fixtures":fixtures,"evaluator_path":str(evaluator_path),
                "evaluator":evaluator,"actor_rows":actor_rows}

    def compile_instance(self, instance: dict[str, Any], suite_root: Path,
                         run_id: str | None=None, selected_topologies: Sequence[str]=TOPOLOGIES) -> dict[str, Any]:
        checked=self._validate_record(instance,suite_root)
        if not selected_topologies or not set(selected_topologies)<=set(self.supported_topologies):
            raise RuntimeCompileError("unsupported or empty topology selection")
        actors=[RuntimeActorSpec(a["actor_id"],a["task_domain"],a["goal"],
                  tuple(a["target_objects"]),a["operation"],a["initial_value"],a["expected_value"],
                  f"{instance['instance_id']}/{a['actor_id']}",f"{instance['instance_id']}/{a['actor_id']}")
                for a in checked["actor_rows"]]
        app_assets=[]
        for fixture in checked["fixtures"]:
            ext=Path(fixture["path"]).suffix.lower()
            if ext in {".fodt",".odt"}: app="Writer"
            elif ext in {".fods",".ods"}: app="Calc"
            elif ext in {".html",".htm"}: app="Browser"
            elif ext in {".sh"}: app="Terminal"
            else: app="Support"
            app_assets.append({"app":app,"fixture":fixture["path"],"host_path":fixture["host_path"],"sha256":fixture["sha256"],
                               "guest_path":f"/home/oem/codesk/{instance['instance_id']}/{Path(fixture['path']).name}"})
        topology_plans={}
        for topology in selected_topologies:
            if topology=="solo":
                slots=[{"run_variant":"solo_a","active_actors":[actors[0].actor_id],"guest_slots":["solo"]},
                       {"run_variant":"solo_b","active_actors":[actors[1].actor_id],"guest_slots":["solo"]}]
            elif topology=="ma_id":
                slots=[{"run_variant":"ma_id","active_actors":[a.actor_id for a in actors],"guest_slots":[f"actor_{a.actor_id}" for a in actors],
                        "fixture_equivalence":"same fixture hashes; task-relevant workspace seed equivalent"}]
            else:
                slots=[{"run_variant":"ma_sd","active_actors":[a.actor_id for a in actors],"guest_slots":["shared"],
                        "shared_state":[instance["treatment_relevant_state"]]}]
            topology_plans[topology]={"desktop_count":len(actors) if topology=="ma_id" else 1,
                "variants":slots,"schedule_policy_id":self.schedule_policy_id,
                "actor_histories_are_independent":True,
                "task_fixture_sha256":instance["signatures"]["fixture"]}
        run_id=run_id or f"plan-{instance['instance_id']}"
        plan={"runtime_schema_version":RUNTIME_SCHEMA_VERSION,"benchmark_version":instance["benchmark_version"],
          "family":self.family,"workflow_id":self.workflow_id,"instance_id":instance["instance_id"],
          "run_id":run_id,"adapter_id":f"codesk.runtime.{self.workflow_id.lower()}.v1",
          "adapter_status":"PLAN_COMPILED_GUEST_RUNTIME_UNVALIDATED","validation_level":self.validation_level,
          "operation_graph":self.workflow["operation_graph"],"workflow_description":self.workflow["description"],
          "workflow_semantic_schema":self.workflow["semantic_parameter_schema"],
          "required_apps":list(self.required_apps),"fixture_assets":app_assets,
          "prepare_steps":[{"op":"materialize_verified_fixtures"},{"op":"create_workspace_from_instance_spec"},
             {"op":"launch_apps_from_fixture_types"},{"op":"verify_initial_state_from_private_evaluator"}],
          "initial_gui_state":{"target_objects":instance["target_objects"],
             "semantic_parameters":instance["semantic_parameters"],
             "treatment_state":instance["treatment_relevant_state"]},
          "actors":[asdict(a) for a in actors],"topologies":topology_plans,
          "evaluator_binding":{"path":instance["evaluator_path"],"sha256":instance["evaluator_sha256"],
             "host_path":checked["evaluator_path"],
             "adapter":checked["evaluator"].get("adapter"),"private_expected_state":True},
          "reset_binding":{"metadata":instance["reset_metadata"],"fixture_hashes":[x["sha256"] for x in checked["fixtures"]],
             "verify_initial_state":True,"verify_resource_cleanup":True},
          "artifact_contract":{"root_template":f"runs/{run_id}","required":list(ARTIFACTS),
             "provenance":instance["provenance"]},
          "ownership":{"owner_uid_required":True,"run_id":run_id,"labels_required":["project=codesk","run_id="+run_id],
             "cleanup":"only full IDs recorded by this run's ledger"},
          "provenance":{"instance_manifest_sha256":instance["manifest_entry_sha256"],
             "generator_source_commit":instance["provenance"]["source_commit"],
             "generator_source_sha256":instance["provenance"]["source_code_sha256"],
             "runtime_adapter_source_sha256":_sha_file(Path(__file__).resolve()),
             "runtime_adapter_commit":_runtime_commit()}}
        from .runtime_bindings_v1 import compile_workflow_binding
        plan["runtime_execution_binding"]=compile_workflow_binding(
            plan,Path(__file__).resolve().parents[1])
        plan["plan_sha256"]=sha256(canonical_bytes(plan))
        return plan

    def prepare(self, plan: dict[str, Any], topology: str, backend: GuestBackend) -> list[Any]:
        guests=[]
        if topology not in plan["topologies"]: raise RuntimeCompileError(f"topology not compiled: {topology}")
        guest_slots=plan["topologies"][topology]["variants"][0]["guest_slots"]
        try:
            for slot in guest_slots:
                guest=backend.create_owned_guest(plan["run_id"],slot,plan["ownership"]);guests.append(guest)
                backend.clone_workspace(plan,guest,plan["instance_id"])
                for asset in plan["fixture_assets"]:
                    backend.copy_fixture(guest,Path(asset["host_path"]),asset["guest_path"],asset["sha256"])
                self.launch(plan,backend,guest)
            return guests
        except BaseException as exc:
            cleanup_errors=[]
            for guest in reversed(guests):
                try: backend.cleanup_owned_guest(guest,plan["ownership"])
                except Exception as cleanup_exc: cleanup_errors.append(f"{type(cleanup_exc).__name__}: {cleanup_exc}")
            suffix=("; owned Guest cleanup failed and resources were preserved: "+" | ".join(cleanup_errors)) if cleanup_errors else "; created run-owned Guests cleaned"
            raise RuntimeBackendUnavailable(f"prepare failed: {type(exc).__name__}: {exc}{suffix}") from exc

    def launch(self, plan: dict[str, Any], backend: GuestBackend, guest: Any) -> dict[str, Any]:
        readiness={}
        app_assets=[asset for asset in plan["fixture_assets"] if asset["app"] in plan["required_apps"]]
        for app in plan["required_apps"]:
            matches=[asset for asset in app_assets if asset["app"]==app]
            if not matches:raise RuntimeBackendUnavailable(f"no fixture target for required app {app}")
            for asset in matches:
                target=asset["guest_path"]
                key=f"{app}:{Path(target).name}"
                backend.launch_application(guest,app,target)
                readiness[key]=backend.wait_application_ready(guest,app,target)
                if not readiness[key].get("ready"):
                    raise RuntimeBackendUnavailable(f"{app} readiness failed: {readiness[key]}")
        prepare_workflow=getattr(backend,"prepare_workflow",None)
        if callable(prepare_workflow): prepare_workflow(plan,guest)
        observed=backend.observe_initial_state(guest,plan)
        verification=backend.verify_initial_state(guest,plan,observed)
        if not verification.get("verified"):
            raise RuntimeBackendUnavailable(f"initial state mismatch: {verification}")
        return readiness

    def get_actor_specs(self, plan: dict[str, Any], active_actor_ids: Sequence[str] | None=None) -> list[RuntimeActorSpec]:
        allowed=set(active_actor_ids) if active_actor_ids is not None else None
        return [RuntimeActorSpec(**row) for row in plan["actors"] if allowed is None or row["actor_id"] in allowed]

    def run(self, plan: dict[str, Any], scheduler: TurnScheduler, guests: Sequence[Any],
            topology: str, artifact_root: Path, active_actor_ids: Sequence[str] | None=None) -> dict[str, Any]:
        if topology not in plan["topologies"]: raise RuntimeCompileError(f"topology not compiled: {topology}")
        return scheduler.execute(self.get_actor_specs(plan,active_actor_ids),self.schedule_policy_id,guests,topology,artifact_root)

    def evaluate(self, plan: dict[str, Any], backend: GuestBackend, guests: Sequence[Any],
                 active_actor_ids: Sequence[str] | None=None) -> dict[str, Any]:
        from .production_v1 import evaluate_oracle
        actual=backend.collect_hidden_state(guests,plan)
        evaluator=json.loads(Path(plan["evaluator_binding"]["host_path"]).read_text())
        # Private evaluator files store the evaluator body; evaluate_oracle consumes
        # a manifest-shaped record with that body under the `evaluator` key.
        spec=evaluator if "evaluator" in evaluator else {"evaluator":evaluator}
        return evaluate_oracle(spec,actual,
             tuple(active_actor_ids or [x["actor_id"] for x in plan["actors"]]))

    def collect_artifacts(self, plan: dict[str, Any], backend: GuestBackend, guests: Sequence[Any], output: Path) -> dict[str, Any]:
        output.mkdir(parents=True,exist_ok=True)
        return backend.collect_artifacts(guests,plan,output)

    def reset(self, plan: dict[str, Any], backend: GuestBackend, guests: Sequence[Any]) -> list[dict[str, Any]]:
        results=[backend.reset_guest(guest,plan) for guest in guests]
        if any(not row.get("verified") for row in results):
            raise RuntimeBackendUnavailable(f"reset verification failed: {results}")
        return results

    def cleanup(self, plan: dict[str, Any], backend: GuestBackend, guests: Sequence[Any]) -> list[dict[str, Any]]:
        results=[backend.cleanup_owned_guest(guest,plan["ownership"]) for guest in guests]
        if any(not row.get("ownership_verified") for row in results):
            raise RuntimeBackendUnavailable(f"resource ownership cleanup not verified: {results}")
        return results

    def execute(self, plan: dict[str, Any], topology: str, backend: GuestBackend,
                scheduler: TurnScheduler, output: Path, active_actor_ids: Sequence[str] | None=None) -> dict[str, Any]:
        """Execute via explicitly supplied owned-resource backend and scheduler."""
        guests=[];result={"run_id":plan["run_id"],"status":"starting","topology":topology,
                         "workflow_id":self.workflow_id,"instance_id":plan["instance_id"]}
        try:
            guests=self.prepare(plan,topology,backend)
            result["actor_execution"]=self.run(plan,scheduler,guests,topology,output,active_actor_ids)
            result["evaluation"]=self.evaluate(plan,backend,guests,active_actor_ids)
            result["status"]="PASS" if result["evaluation"].get("joint_success") else "TASK_FAILURE"
        except RuntimeBackendUnavailable as exc:
            result.update({"status":"INVALID_INFRA","failure_reason":"readiness_or_backend","error":str(exc)})
        except Exception as exc:
            result.update({"status":"INVALID_INFRA","failure_reason":"runtime_exception","error":repr(exc)})
        finally:
            if guests:
                try:result["artifacts"]=self.collect_artifacts(plan,backend,guests,output)
                except Exception as exc:result["artifact_error"]=repr(exc)
                try:result["reset"]=self.reset(plan,backend,guests)
                except Exception as exc:result["reset_error"]=repr(exc);result["status"]="INVALID_INFRA"
                try:result["cleanup"]=self.cleanup(plan,backend,guests)
                except Exception as exc:result["cleanup_error"]=repr(exc);result["status"]="INVALID_INFRA"
        output.mkdir(parents=True,exist_ok=True)
        (output/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        return result


class WorkflowRuntimeRegistry:
    def __init__(self, adapters: dict[str, WorkflowRuntimeAdapter]): self._adapters=adapters
    def get(self, workflow_id: str) -> WorkflowRuntimeAdapter:
        try:return self._adapters[workflow_id]
        except KeyError as exc:raise RuntimeCompileError(f"workflow adapter missing: {workflow_id}") from exc
    def workflow_ids(self) -> tuple[str,...]: return tuple(sorted(self._adapters))
    def compile(self, record: dict[str, Any], suite_root: Path,
                selected_topologies: Sequence[str]=TOPOLOGIES) -> dict[str, Any]:
        return self.get(record["workflow_id"]).compile_instance(record,suite_root,selected_topologies=selected_topologies)


def build_runtime_registry() -> WorkflowRuntimeRegistry:
    return WorkflowRuntimeRegistry({row["workflow_id"]:WorkflowRuntimeAdapter(row) for row in workflow_registry()})


def bind_run_plan(template_plan: dict[str, Any], run_config: dict[str, Any]) -> dict[str, Any]:
    """Bind immutable instance plan to one run-owned artifact/resource identity."""
    plan=json.loads(json.dumps(template_plan))
    run_id=run_config["run_id"]
    plan["run_id"]=run_id
    plan["artifact_contract"]["root_template"]=run_config["artifact_path"]
    plan["ownership"]["run_id"]=run_id
    plan["ownership"]["labels_required"]=["project=codesk","run_id="+run_id]
    plan.pop("plan_sha256",None)
    plan["plan_sha256"]=sha256(canonical_bytes(plan))
    return plan


def compile_suite(manifest_path: Path, suite_root: Path, output_path: Path,
                  selected_topologies: Sequence[str]=TOPOLOGIES) -> dict[str, Any]:
    from .production_v1 import read_manifest
    registry=build_runtime_registry();records=read_manifest(manifest_path);plans=[];counts={}
    for record in records:
        plan=registry.compile(record,suite_root,selected_topologies)
        plans.append(plan);counts[record["workflow_id"]]=counts.get(record["workflow_id"],0)+1
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text("".join(json.dumps(p,sort_keys=True,separators=(",",":"))+"\n" for p in plans),encoding="utf-8")
    return {"compiled":len(plans),"failed":0,"workflow_counts":counts,"topologies":list(selected_topologies),
            "runtime_backend_attached":False,"plans_path":str(output_path)}

import json,tempfile,unittest,subprocess,sys
from pathlib import Path
from swcub.production_v1 import read_manifest
from swcub.runtime_v1 import build_runtime_registry
from swcub.runtime_execution_v1 import (DeterministicRuntimeScheduler,EventGate,Outcome,RuntimeExecutor)
from swcub.fake_runtime_backend_v1 import FakeGuestBackend,fake_actor_factory
ROOT=Path(__file__).resolve().parents[1]; SUITE=ROOT/"benchmarks/codesk_v1"
class RuntimeExecutionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=read_manifest(SUITE/"manifest.jsonl");cls.registry=build_runtime_registry()
 def run_one(self,row,topology="ma_sd",active=("A","B"),backend=None,actor_factory=fake_actor_factory,scheduler_kwargs=None):
  backend=backend or FakeGuestBackend();adapter=self.registry.get(row["workflow_id"])
  plan=adapter.compile_instance(row,SUITE,run_id="offline-run-0001")
  cfg={"run_id":"offline-run-0001","base_run_id":"offline-base-0001","topology":topology,"active_actors":list(active)}
  with tempfile.TemporaryDirectory() as tmp:
   events=[];kwargs=dict(scheduler_kwargs or {})
   policy=plan["topologies"][topology]["schedule_policy_id"]
   if "round-robin" not in policy and "gate" not in kwargs:
    kwargs["gate"]=EventGate([{"kind":"action_complete","actor_id":aid} for aid in active])
   scheduler=DeterministicRuntimeScheduler(actor_factory,backend,step_budget=3,event_sink=events.append,**kwargs)
   result=RuntimeExecutor().execute(adapter,plan,cfg,backend,scheduler,Path(tmp))
   result["_test_provenance_exists"]=(Path(tmp)/"provenance.json").is_file()
   return result,backend,events
 def test_fifteen_workflows_complete_fake_ma_sd_lifecycle(self):
  seen=set()
  for row in self.rows:
   if row["workflow_id"] in seen: continue
   seen.add(row["workflow_id"]);result,backend,_=self.run_one(row)
   self.assertEqual(result["status"],Outcome.SUCCESS.value,(row["workflow_id"],result))
   self.assertTrue(result["infra_valid"]);self.assertTrue(result["oracle_success"]);self.assertTrue(result["_test_provenance_exists"])
   self.assertTrue(result["reset"][0]["verified"]);self.assertTrue(result["cleanup"][0]["ownership_verified"])
   self.assertTrue(all(g.cleaned for g in backend.guests))
  self.assertEqual(len(seen),15)
 def test_solo_a_solo_b_ma_id_and_ma_sd_guest_counts(self):
  row=next(r for r in self.rows if r["workflow_id"]=="F-01")
  for actor in ("A","B"):
   result,backend,_=self.run_one(row,"solo",(actor,))
   self.assertEqual(result["status"],Outcome.SUCCESS.value);self.assertEqual(len(backend.guests),1)
  result,backend,_=self.run_one(row,"ma_id")
  self.assertEqual(result["status"],Outcome.SUCCESS.value);self.assertEqual(len(backend.guests),2)
  result,backend,_=self.run_one(row,"ma_sd")
  self.assertEqual(result["status"],Outcome.SUCCESS.value);self.assertEqual(len(backend.guests),1)
 def test_event_gate_consumes_only_observed_events(self):
  row=next(r for r in self.rows if r["workflow_id"]=="F-01")
  gate=EventGate([{"kind":"action_complete","actor_id":"A"},{"kind":"action_complete","actor_id":"B"}])
  result,_,events=self.run_one(row,scheduler_kwargs={"gate":gate})
  self.assertTrue(gate.complete);self.assertEqual(result["status"],Outcome.SUCCESS.value)
  self.assertTrue(any(x.get("kind")=="gate_advanced" for x in events))
 def test_task_failure_and_timeout_are_distinct_from_infra(self):
  row=next(r for r in self.rows if r["workflow_id"]=="F-01")
  class Noop:
   terminated=False
   def reset(self): pass
   def run_step(self,context): self.terminated=True; return True
  result,_,_=self.run_one(row,actor_factory=lambda *_:Noop())
  self.assertEqual(result["status"],Outcome.TASK_FAILURE.value);self.assertTrue(result["infra_valid"])
  class TimedOut:
   terminated=False
   def reset(self): pass
   def run_step(self,context): raise TimeoutError("simulated actor turn timeout")
  result,_,_=self.run_one(row,actor_factory=lambda *_:TimedOut())
  self.assertEqual(result["status"],Outcome.TIMEOUT.value);self.assertTrue(result["infra_valid"])
 def test_invalid_infra_reset_failure_and_cleanup_ownership(self):
  row=next(r for r in self.rows if r["workflow_id"]=="F-01")
  result,backend,_=self.run_one(row,backend=FakeGuestBackend(fail_at="readiness"))
  self.assertEqual(result["status"],Outcome.INVALID_INFRA.value);self.assertFalse(result["infra_valid"])
  self.assertTrue(all(g.cleaned for g in backend.guests),"partially prepared run-owned Guests must be safely cleaned")
  result,_,_=self.run_one(row,backend=FakeGuestBackend(fail_reset=True))
  self.assertEqual(result["status"],Outcome.RESET_FAILURE.value)
  backend=FakeGuestBackend();g=backend.create_owned_guest("offline-run-0001","shared",{"run_id":"offline-run-0001"})
  with self.assertRaises(RuntimeError): backend.cleanup_owned_guest(g,{"run_id":"other-run-9999"})
 def test_batch_runner_fake_execute_runs_full_state_machine_and_marks_evidence(self):
  row=next(r for r in self.rows if r["workflow_id"]=="F-01")
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);results=root/"fake-runs";plan=root/"plan.jsonl"
   cmd=[sys.executable,str(ROOT/"scripts/run_benchmark.py"),"--manifest",str(SUITE/"manifest.jsonl"),
    "--suite-root",str(SUITE),"--instance",row["instance_id"],"--topology","ma_sd","--model","test",
    "--backend","fake","--execute","--plan",str(plan),"--results",str(results)]
   proc=subprocess.run(cmd,check=True,capture_output=True,text=True)
   result=json.loads(next(results.glob("*/result.json")).read_text())
   summary=json.loads(proc.stdout)
   self.assertEqual(result["status"],Outcome.SUCCESS.value)
   self.assertEqual(result["evidence_class"],"FAKE_ORCHESTRATION_ONLY")
   self.assertEqual(summary["result_status_counts"],{"SUCCESS":1})
   self.assertFalse(summary["guest_started"])
 def test_a6000_batch_plugin_blocks_missing_bindings_without_guest(self):
  row=next(r for r in self.rows if r["workflow_id"]=="F-01")
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);results=root/"preflight";plan=root/"plan.jsonl"
   cmd=[sys.executable,str(ROOT/"scripts/run_benchmark.py"),"--manifest",str(SUITE/"manifest.jsonl"),
    "--suite-root",str(SUITE),"--instance",row["instance_id"],"--topology","ma_sd","--model","qwen3vl",
    "--backend","a6000","--execute","--plan",str(plan),"--results",str(results)]
   proc=subprocess.run(cmd,check=True,capture_output=True,text=True)
   result=json.loads(next(results.glob("*/result.json")).read_text())
   summary=json.loads(proc.stdout)
   self.assertEqual(result["status"],Outcome.BLOCKED_RUNTIME_BACKEND.value)
   self.assertFalse(result["guest_started"]);self.assertFalse(summary["guest_started"])
   self.assertIn("exact_hidden_state_observer",result["unresolved_plan_components"])
 def test_fake_backend_cannot_be_mistaken_for_guest_evidence(self):
  self.assertTrue(FakeGuestBackend.FAKE_BACKEND_ONLY)
 def test_static_a6000_backend_preflight_has_no_guest_side_effects(self):
  from swcub.osworld_guest_backend_v1 import A6000OSWorldBackend
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);repo=root/"repo";osw=root/"osworld";provider=osw/"desktop_env/providers/docker/provider.py"
   repo.mkdir();provider.parent.mkdir(parents=True);provider.write_text("SWCUB_OWNED_RESOURCE_SAFETY")
   (osw/"desktop_env").mkdir(exist_ok=True);(osw/"desktop_env/desktop_env.py").write_text("pinned")
   image=root/"guest.qcow2";image.write_bytes(b"offline fixture")
   cache_parent=root/"cache";cache_parent.mkdir();artifacts=root/"artifacts";artifacts.mkdir()
   backend=A6000OSWorldBackend(repo_root=repo,guest_image=image,osworld_root=osw,cache_dir=cache_parent/"task-cache",
      runtime_image="unused:offline",artifact_root=artifacts)
   report=backend.static_preflight()
   self.assertEqual(report["status"],"CODE_READY");self.assertFalse(report["guest_started"])
if __name__=="__main__":unittest.main()

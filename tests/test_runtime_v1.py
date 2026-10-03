import json,tempfile,unittest
from pathlib import Path
import subprocess,sys
from swcub.production_v1 import read_manifest
from swcub.runtime_v1 import build_runtime_registry,compile_suite,TOPOLOGIES

ROOT=Path(__file__).resolve().parents[1]
SUITE=ROOT/"benchmarks/codesk_v1"

class RuntimeAdapterTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.records=read_manifest(SUITE/"manifest.jsonl");cls.registry=build_runtime_registry()
 def test_registry_has_all_fifteen_adapters(self):
  self.assertEqual(len(self.registry.workflow_ids()),15)
  self.assertEqual(set(self.registry.workflow_ids()),{r["workflow_id"] for r in self.records})
 def test_all_instances_compile_topologies_fixtures_goals_eval_reset_provenance(self):
  with tempfile.TemporaryDirectory() as temp:
   out=Path(temp)/"plans.jsonl"
   result=compile_suite(SUITE/"manifest.jsonl",SUITE,out)
   self.assertEqual(result["compiled"],600);self.assertEqual(result["failed"],0)
   plans=[json.loads(line) for line in out.read_text().splitlines()]
   self.assertEqual(len(plans),600)
   for plan in plans:
    self.assertEqual(set(plan["topologies"]),set(TOPOLOGIES))
    self.assertEqual(len(plan["actors"]),2)
    self.assertTrue(plan["evaluator_binding"]["private_expected_state"])
    self.assertTrue(plan["reset_binding"]["verify_initial_state"])
    self.assertTrue(plan["provenance"]["generator_source_sha256"])
    self.assertTrue(plan["provenance"]["runtime_adapter_source_sha256"])
    self.assertTrue(plan["ownership"]["labels_required"])
    self.assertTrue(all(Path(x["host_path"]).is_file() for x in plan["fixture_assets"]))
    self.assertEqual(plan["topologies"]["ma_id"]["desktop_count"],2)
    self.assertEqual(plan["topologies"]["ma_sd"]["desktop_count"],1)
    self.assertEqual(len(plan["topologies"]["solo"]["variants"]),2)
 def test_all_ten_legacy_anchor_workflows_have_instance_bound_semantic_plan(self):
  anchors={"F-01":{"Writer","Calc"},"F-04":{"Calc","Writer"},"F-02":{"Writer","Browser"},
   "C-01":{"Writer","Calc"},"C-03":{"Calc","Writer"},"C-02":{"Browser","Writer"},
   "A-01":{"Browser"},"A-02":{"Browser"},"S-01":{"Calc"},"U-01":{"Calc"}}
  for wid,apps in anchors.items():
   rec=next(r for r in self.records if r["workflow_id"]==wid)
   plan=self.registry.compile(rec,SUITE)
   self.assertEqual(set(plan["required_apps"]),apps)
   self.assertEqual(plan["instance_id"],rec["instance_id"])
   self.assertEqual(list(plan["actors"][0]["target_objects"]),rec["actor_goals"][0]["target_objects"])
  # F-01's selected legacy anchor shape is Writer text + Calc B2; matching the
  # operation/topology is semantic equivalence, not byte-for-byte fixture equivalence.
  f01=next(r for r in self.records if r["workflow_id"]=="F-01" and r["target_objects"]["B"]==["calc/B2"])
  f01plan=self.registry.compile(f01,SUITE)
  self.assertIn("Writer",f01plan["required_apps"]);self.assertIn("Calc",f01plan["required_apps"])
 def test_five_new_workflows_keep_original_validation_levels(self):
  expected={"F-N1":"guest_solo","C-N1":"offline","A-N1":"offline","S-N1":"offline","U-N1":"offline"}
  for rec in self.records:
   if rec["workflow_id"] in expected:
    plan=self.registry.compile(rec,SUITE)
    self.assertEqual(plan["validation_level"],expected[rec["workflow_id"]])
    self.assertEqual(plan["adapter_status"],"PLAN_COMPILED_GUEST_RUNTIME_UNVALIDATED")
 def test_cli_resume_skip_and_bounded_invalid_infra_retry(self):
  rec=next(r for r in self.records if r["workflow_id"]=="F-01")
  with tempfile.TemporaryDirectory() as temp:
   tmp=Path(temp);results=tmp/"results";planfile=tmp/"plan.jsonl"
   cmd=[sys.executable,str(ROOT/"scripts/run_benchmark.py"),"--manifest",str(SUITE/"manifest.jsonl"),
    "--suite-root",str(SUITE),"--instance",rec["instance_id"],"--topology","solo","--model","test",
    "--dry-run","--plan",str(planfile),"--results",str(results)]
   subprocess.run(cmd,check=True,capture_output=True,text=True)
   first=[json.loads(x) for x in planfile.read_text().splitlines()]
   self.assertEqual(len(first),2)
   completed=first[0];done_dir=results/"completed";done_dir.mkdir(parents=True)
   (done_dir/"result.json").write_text(json.dumps({"run_id":completed["run_id"],"base_run_id":completed["base_run_id"],"status":"PASS"}))
   subprocess.run(cmd+["--resume"],check=True,capture_output=True,text=True)
   resumed=[json.loads(x) for x in planfile.read_text().splitlines()]
   self.assertEqual(len(resumed),1)
   invalid=resumed[0];invalid_dir=results/"invalid";invalid_dir.mkdir()
   (invalid_dir/"result.json").write_text(json.dumps({"run_id":invalid["run_id"],"base_run_id":invalid["base_run_id"],"status":"INVALID_INFRA"}))
   subprocess.run(cmd+["--resume","--max-infra-retries","1"],check=True,capture_output=True,text=True)
   retry=[json.loads(x) for x in planfile.read_text().splitlines()]
   retried=[x for x in retry if x["base_run_id"]==invalid["base_run_id"]]
   self.assertEqual(len(retried),1);self.assertEqual(retried[0]["attempt"],2)
 def test_execute_without_backend_is_per_run_blocked_and_never_starts_guest(self):
  rec=next(r for r in self.records if r["workflow_id"]=="F-01")
  with tempfile.TemporaryDirectory() as temp:
   tmp=Path(temp);results=tmp/"results";planfile=tmp/"plan.jsonl"
   cmd=[sys.executable,str(ROOT/"scripts/run_benchmark.py"),"--manifest",str(SUITE/"manifest.jsonl"),
    "--suite-root",str(SUITE),"--instance",rec["instance_id"],"--topology","ma_sd","--model","test",
    "--execute","--plan",str(planfile),"--results",str(results)]
   completed=subprocess.run(cmd,check=True,capture_output=True,text=True)
   status=list(results.glob("*/execution-status.json"))
   self.assertEqual(len(status),1);payload=json.loads(status[0].read_text())
   self.assertEqual(payload["status"],"BLOCKED_RUNTIME_BACKEND");self.assertFalse(payload["guest_started"])
   self.assertIn("runtime_backend_missing_runs",completed.stdout)
 def test_smoke_entrypoint_compiles_five_families_to_run_plan(self):
  with tempfile.TemporaryDirectory() as temp:
   plan=Path(temp)/"smoke.jsonl"
   subprocess.run([sys.executable,str(ROOT/"scripts/run_smoke_suite.py"),"--model","test","--plan",str(plan)],
                  check=True,capture_output=True,text=True)
   rows=[json.loads(line) for line in plan.read_text().splitlines()]
   self.assertEqual(len(rows),20)
   self.assertEqual(len({r["instance_id"] for r in rows}),5)

if __name__=="__main__":unittest.main()

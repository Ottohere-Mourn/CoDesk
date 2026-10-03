#!/usr/bin/env python3
"""Offline test bundle: generator, byte determinism, oracle controls, manifest and run-plan expansion."""
import json,tempfile,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import (workflow_registry,build_instance,_profile_catalog,generate_workflow,
  evaluate_oracle,_positive_state,_negative_state,read_manifest,audit_records,make_run_plan,sha256)

with tempfile.TemporaryDirectory(prefix="codesk-v1-offline-") as tmp:
 root=Path(tmp);allrows=[]
 for row in workflow_registry():
  wid=row["workflow_id"];out=root/wid
  for d in ("instances","fixtures","evaluators"): (out/d).mkdir(parents=True,exist_ok=True)
  catalog=_profile_catalog(wid,2026)
  hand=[]
  for domain,profile,layout in catalog[:3]:
   s=build_instance(wid,domain,profile,layout,2026,Path(__file__).resolve().parents[1])
   s2=build_instance(wid,domain,profile,layout,2026,Path(__file__).resolve().parents[1])
   assert s.instance_id==s2.instance_id and s.signatures==s2.signatures and s.fixture_files==s2.fixture_files
   assert evaluate_oracle(s,_positive_state(s))["joint_success"]
   assert not evaluate_oracle(s,_negative_state(s))["joint_success"]
   from swcub.production_v1 import materialize
   hand.append(materialize(s,out));allrows.append(hand[-1])
  (out/"manifest.jsonl").write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n" for x in hand))
  reread=read_manifest(out/"manifest.jsonl");assert len(reread)==3
  for rec in reread:
   for asset in rec["fixture_files"]:assert sha256((out/asset["path"]).read_bytes())==asset["sha256"]
   ev=out/rec["evaluator_path"]
   assert sha256(ev.read_bytes())==rec["evaluator_sha256"]
 assert len(allrows)==45
 audit=audit_records(allrows);assert audit["generated"]==45 and audit["duplicate_rejected"]==0,audit
 plan=make_run_plan(allrows[:1],["solo","ma_id","ma_sd"],"qwen3vl",2)
 assert len(plan)==8, len(plan) # Solo A/B × 2 plus MA-ID and MA-SD × 2
 # Aggregator fixture validates grouping and exclusion rules; these rows are synthetic
 # test inputs, not benchmark episode results.
 results=root/"aggregator-inputs"; (results/"pass").mkdir(parents=True);(results/"infra").mkdir()
 base={"family":"focus_input_routing","workflow_id":"F-01","topology":"ma_sd","model":"test-only",
  "actor_success":{"A":True,"B":False},"joint_success":False,"scheduled_exposure":True,
  "actual_exposure":False,"observed_interference":False,"autonomous_recovery":False,
  "recovery_success":False,"action_count":3,"episode_seconds":1.2}
 (results/"pass"/"result.json").write_text(json.dumps({**base,"run_id":"test-pass","status":"TASK_FAILURE"}))
 (results/"infra"/"result.json").write_text(json.dumps({**base,"run_id":"test-infra","status":"INVALID_INFRA"}))
 agg=root/"aggregate-output"
 subprocess.run([sys.executable,str(Path(__file__).with_name("aggregate_benchmark_results.py")),str(results),"--output-dir",str(agg)],check=True,capture_output=True,text=True)
 summary=json.loads((agg/"summary.json").read_text());assert summary["invalid_infra_count"]==1
 assert summary["groups"][0]["episodes"]==1 and summary["groups"][0]["actual_exposure"]==0
 assert summary["groups"][0]["invalid_infra_count"]==1
 print(json.dumps({"status":"PASS","workflows":len(workflow_registry()),"instances":len(allrows),
   "positive_oracles":45,"negative_oracles":45,"plan_rows_for_one_instance":len(plan),
   "aggregator_test":"PASS (synthetic test rows only)","audit":audit},indent=2))

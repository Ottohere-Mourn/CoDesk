import json,tempfile,unittest
from pathlib import Path

from swcub.production_v1 import (workflow_registry,_profile_catalog,build_instance,
 evaluate_oracle,_positive_state,_negative_state,materialize,read_manifest,make_run_plan)

class ProductionV1Tests(unittest.TestCase):
 def test_thirty_workflows_and_determinism(self):
  rows=workflow_registry();self.assertEqual(len(rows),30)
  self.assertEqual(sum(row["workflow_id"].startswith(("F-05","F-06","F-07","C-04","C-05","C-06","A-03","A-04","A-05","S-02","S-03","S-04","U-02","U-03","U-04")) for row in rows),15)
  root=Path(__file__).resolve().parents[1]
  for row in rows:
   wid=row['workflow_id'];d,p,l=_profile_catalog(wid,7)[0]
   a=build_instance(wid,d,p,l,7,root);b=build_instance(wid,d,p,l,7,root)
   self.assertEqual(a.instance_id,b.instance_id);self.assertEqual(a.signatures,b.signatures)
   self.assertEqual(a.fixture_files,b.fixture_files)
   self.assertTrue(evaluate_oracle(a,_positive_state(a))['joint_success'])
   self.assertFalse(evaluate_oracle(a,_negative_state(a))['joint_success'])

 def test_diversity_context_profiles_are_task_relevant_and_oracle_visible(self):
  from swcub.diversity_context_v1 import CONTEXTS
  from swcub.production_v1 import _PROFILE_ROWS,DOMAINS,LAYOUTS
  expected={"A-02","A-03","C-01","C-06","F-01","F-06","S-01","S-02","S-04","U-03","U-N1"}
  self.assertEqual(set(CONTEXTS),expected)
  for wid in sorted(expected):
   profiles=_PROFILE_ROWS[wid]
   self.assertEqual(len(profiles),5)
   self.assertEqual(len({p["schema"]["state_context"]["profile"] for p in profiles}),5)
   operation_graph=next(x["operation_graph"] for x in workflow_registry() if x["workflow_id"]==wid)
   schedule=next(x["schedule_policy_id"] for x in workflow_registry() if x["workflow_id"]==wid)
   signatures=set()
   for profile in profiles:
    spec=build_instance(wid,DOMAINS[0],profile,LAYOUTS[0],2026,Path(__file__).resolve().parents[1])
    self.assertEqual(spec.semantic_parameters["operation_graph"],operation_graph)
    self.assertEqual(spec.schedule_policy_id,schedule)
    self.assertTrue(evaluate_oracle(spec,_positive_state(spec))["joint_success"])
    rec=__import__("swcub.production_v1",fromlist=["to_record"]).to_record(spec)
    signatures.add(rec["signatures"]["fixture"])
    broken=_positive_state(spec);broken["context_state"]={"profile":"corrupted"}
    self.assertFalse(evaluate_oracle(spec,broken)["joint_success"])
   self.assertEqual(len(signatures),5)

 def test_manifest_materialization_and_hash(self):
  root=Path(__file__).resolve().parents[1];wid='F-01';d,p,l=_profile_catalog(wid,3)[0]
  spec=build_instance(wid,d,p,l,3,root)
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);(out/'instances').mkdir();(out/'fixtures').mkdir();(out/'evaluators').mkdir()
   rec=materialize(spec,out);(out/'manifest.jsonl').write_text(json.dumps(rec)+'\n')
   self.assertEqual(read_manifest(out/'manifest.jsonl')[0]['instance_id'],spec.instance_id)
 def test_run_plan_topologies_and_actor_count(self):
  root=Path(__file__).resolve().parents[1];wid='F-01';d,p,l=_profile_catalog(wid,3)[0]
  s=build_instance(wid,d,p,l,3,root)
  from swcub.production_v1 import to_record
  plan=make_run_plan([to_record(s)],['solo','ma_id','ma_sd'],'qwen',2)
  self.assertEqual(len(plan),8)
  self.assertEqual(sum(x['topology']=='solo' for x in plan),4)
  self.assertTrue(all(x['active_actors'] for x in plan))
  base=plan[0]['base_run_id']
  retry=make_run_plan([to_record(s)],['solo'],'qwen',1,infra_attempts={base:1},max_infra_retries=1)
  self.assertEqual(retry[0]['attempt'],2)
  all_solo_bases={x['base_run_id'] for x in make_run_plan([to_record(s)],['solo'],'qwen',1)}
  self.assertEqual(make_run_plan([to_record(s)],['solo'],'qwen',1,completed_run_ids=all_solo_bases),[])
  exhausted={run_id:2 for run_id in all_solo_bases}
  self.assertEqual(make_run_plan([to_record(s)],['solo'],'qwen',1,infra_attempts=exhausted,max_infra_retries=1),[])

if __name__=='__main__':unittest.main()

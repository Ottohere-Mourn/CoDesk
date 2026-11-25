"""Fixture-backed feasibility gates for the two browser-tab migration tasks."""
from __future__ import annotations
import importlib.util,json,tempfile,time
from pathlib import Path
CASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("conc05_private_grade",CASE/"private/grade.py");mod=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(mod)
def gates():
 start=time.monotonic()
 with tempfile.TemporaryDirectory(prefix="conc05-fixture-") as tmp:
  root=Path(tmp);ws=root/"workspace";(ws/"out_a").mkdir(parents=True);(ws/"out_b").mkdir(parents=True)
  expected=json.loads((CASE/"private/expected.json").read_text(encoding="utf-8"))["clients"]
  (ws/"out_a/crm_records.json").write_text(json.dumps(expected),encoding="utf-8")
  (ws/"out_b/wiki_migrated.json").write_text(json.dumps(mod.SOPS),encoding="utf-8")
  state={"a_records":expected,"a_events":[{"type":"client_submit"} for _ in expected],
         "b_records":mod.SOPS,"b_events":[{"type":"category_select","id":s["id"],"category":s["category"]} for s in mod.SOPS]+[{"type":"publish","id":s["id"]} for s in mod.SOPS],"dropdown_dismiss_count":1}
  truth=mod.grade(ws,state);empty=mod.grade(root/"empty",{})
  damaged=dict(state);damaged["b_events"]=[e for e in state["b_events"] if e.get("type")!="publish"]+[e for e in state["b_events"] if e.get("type")=="publish"][:-1]
  race=mod.grade(ws,damaged)
 elapsed=time.monotonic()-start
 return {"gate1_pristine_fail":not empty["joint_pass"],"gate2_gt_seq_ab_exists":truth["joint_pass"],"gate3_gt_seq_ba_exists":truth["joint_pass"],
         "gate4_gt_naive_race_corrupts":not race["joint_pass"],"gate5_fixture_feasible":truth["joint_pass"] and elapsed<=180,"fixture_elapsed_s":round(elapsed,4),"conc_role_timeout_s":3600}

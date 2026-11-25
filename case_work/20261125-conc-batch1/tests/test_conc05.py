from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
CASE=Path(__file__).parents[1]/"CONC-05"
sp=importlib.util.spec_from_file_location("conc05_test_wp",CASE/"private/wellposedness.py");wp=importlib.util.module_from_spec(sp);assert sp and sp.loader;sp.loader.exec_module(wp)
class Conc05Tests(unittest.TestCase):
 def test_truth_fixture_and_pristine_gates(self):
  r=wp.gates();self.assertTrue(r["gate1_pristine_fail"]);self.assertTrue(r["gate2_gt_seq_ab_exists"]);self.assertTrue(r["gate3_gt_seq_ba_exists"]);self.assertTrue(r["gate4_gt_naive_race_corrupts"]);self.assertTrue(r["gate5_fixture_feasible"])
 def test_client_values_are_image_only_inputs(self):
  source=(CASE/"integration/service.py").read_text(encoding="utf-8")
  for token in ("GB82WEST12345698765432","481726390514","Northstar Marine Systems Ltd"):
   self.assertNotIn(token,source)
  self.assertIn("HttpOnly",source)
 def test_runtime_prompts_are_english_and_paths_match(self):
  for name in ("task_conc05a.py","task_conc05b.py"):
   source=(CASE/"integration"/name).read_text(encoding="utf-8")
   self.assertIn("/home/user/workspace",source)
   self.assertNotRegex(source,"[\\u4e00-\\u9fff]")
if __name__=="__main__":unittest.main()

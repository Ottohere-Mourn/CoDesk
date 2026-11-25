from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
CASE=Path(__file__).parents[1]/"CONC-06"
sp=importlib.util.spec_from_file_location("conc06_test_wp",CASE/"private/wellposedness.py");wp=importlib.util.module_from_spec(sp);assert sp and sp.loader;sp.loader.exec_module(wp)
class Conc06Tests(unittest.TestCase):
    def test_truth_fixture_and_pristine_gates(self):
        r=wp.gates();self.assertTrue(r["gate1_pristine_fail"]);self.assertTrue(r["gate2_gt_seq_ab_exists"]);self.assertTrue(r["gate3_gt_seq_ba_exists"]);self.assertTrue(r["gate4_gt_naive_race_corrupts"]);self.assertTrue(r["gate5_fixture_feasible"])
    def test_private_adjustments_absent_from_service_source(self):
        svc=(CASE/"integration/service.py").read_text(encoding="utf-8")
        self.assertIn("Target Adjustment",(CASE/"integration/build_assets.py").read_text(encoding="utf-8"))
        for value in ("35000","22500","41250","10750"):self.assertNotIn(value,svc)
        self.assertIn("HttpOnly",svc)
    def test_runtime_prompts_are_english_and_paths_match(self):
        for n in ("task_conc06a.py","task_conc06b.py"):
            s=(CASE/"integration"/n).read_text(encoding="utf-8");self.assertIn("/home/user/workspace",s);self.assertNotRegex(s,"[\\u4e00-\\u9fff]")
if __name__=="__main__":unittest.main()

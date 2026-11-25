from __future__ import annotations
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

CASE=Path(__file__).parents[1]/"CONC-04"
sys.path.insert(0,str(CASE/"integration"))
spec=importlib.util.spec_from_file_location("conc04_test_wp",CASE/"private/wellposedness.py")
wp=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(wp)

class Conc04Tests(unittest.TestCase):
    def test_truth_fixture_passes_both_role_oracles(self):
        with tempfile.TemporaryDirectory() as t:
            result,_,_=wp._make_truth(Path(t))
        self.assertTrue(result["joint_pass"],result["flags"])
        self.assertEqual(result["actor_a"],1.0)
        self.assertEqual(result["actor_b"],1.0)

    def test_pristine_workspace_fails_and_bad_drag_trace_fails(self):
        result=wp.gates()
        self.assertTrue(result["gate1_pristine_fail"])
        self.assertTrue(result["gate4_gt_naive_race_corrupts"])

    def test_annotation_ground_truth_is_not_in_frontend_service(self):
        src=(CASE/"integration/service.py").read_text(encoding="utf-8")
        self.assertNotIn("TRUTH",src)
        self.assertNotIn("265, 115, 315, 165",src)
        self.assertIn("HttpOnly",src)
        self.assertEqual(len(list((CASE/"guest").rglob("*.png"))),0)

if __name__=="__main__": unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
CASE = ROOT / "CONC-02"
sys.path.insert(0, str(CASE / "private"))
sys.path.insert(0, str(CASE / "integration"))
import wellposedness


class Conc02Tests(unittest.TestCase):
    def test_truth_solution_passes_both_role_oracles_in_both_orders(self):
        result = wellposedness.gates()
        self.assertTrue(result["gate1_pristine_fail"])
        self.assertTrue(result["gate2_gt_seq_ab_exists"])
        self.assertTrue(result["gate3_gt_seq_ba_exists"])
        self.assertTrue(result["gate4_gt_naive_race_corrupts"])
        self.assertTrue(result["gate5_fixture_feasible"])
        self.assertFalse(result["gate5_real_tool_timing"])

    def test_runtime_text_is_english_and_guest_workspace_is_consistent(self):
        runtime_files = [
            *CASE.joinpath("integration").glob("*.py"),
            *CASE.joinpath("private").glob("*.py"),
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)
        self.assertFalse(any("\u4e00" <= c <= "\u9fff" for c in text))
        self.assertIn("/home/user/workspace/out_a/Q4_Finance_Final.pptx", text)
        self.assertIn("/home/user/workspace/out_b/Product_Launch_Final.pptx", text)
        self.assertNotIn("another agent", text.lower())


if __name__ == "__main__":
    unittest.main()

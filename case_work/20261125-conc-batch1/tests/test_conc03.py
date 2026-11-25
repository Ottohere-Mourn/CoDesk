from __future__ import annotations

import sys
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
CASE = ROOT / "CONC-03"
sys.path.insert(0, str(CASE / "integration"))
sys.path.insert(0, str(CASE / "private"))


def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


build_assets = load_file("conc03_test_asset_builder", CASE / "integration" / "build_assets.py")
wellposedness = load_file("conc03_test_wellposedness", CASE / "private" / "wellposedness.py")


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


class Conc03Tests(unittest.TestCase):
    def test_deterministic_gates_and_truth_fixture(self):
        result = wellposedness.gates()
        self.assertTrue(result["gate1_pristine_fail"])
        self.assertTrue(result["gate2_gt_seq_ab_exists"])
        self.assertTrue(result["gate3_gt_seq_ba_exists"])
        self.assertTrue(result["gate4_gt_naive_race_corrupts"])
        self.assertTrue(result["gate5_fixture_feasible"])

    def test_runtime_code_is_english_and_assets_have_expected_files(self):
        sources = [*CASE.joinpath("integration").glob("*.py"), *CASE.joinpath("private").glob("*.py")]
        for path in sources:
            self.assertFalse(has_cjk(path.read_text(encoding="utf-8")), path.name)
        with tempfile.TemporaryDirectory(prefix="conc03-assets-test-") as temp:
            dest = Path(temp) / "CONC-03"
            build_assets.build(dest)
            guest = dest / "guest"
            self.assertTrue((guest / "in_a/receipts/receipt_EXP-401.png").is_file())
            self.assertTrue((guest / "in_a/receipts/receipt_EXP-402.png").is_file())
            self.assertTrue((guest / "in_a/receipts/receipt_EXP-403.png").is_file())
            for filename in ("icon_helmet.png", "icon_hazard.png", "icon_exit.png"):
                self.assertTrue((guest / "in_b/icons" / filename).is_file())
            self.assertEqual((guest / "out_b/Safety_Brief.pptx").stat().st_size > 1000, True)
            self.assertFalse(has_cjk((guest / "in_b/safety_spec.txt").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()

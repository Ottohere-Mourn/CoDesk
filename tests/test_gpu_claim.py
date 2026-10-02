import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/resource/gpu_claim.py"
spec = importlib.util.spec_from_file_location("gpu_claim", SCRIPT)
gpu_claim = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gpu_claim)

class EligibilityTests(unittest.TestCase):
    def base(self):
        return {"memory_used_mib": 0, "utilization_gpu_pct": 0, "compute_processes": []}
    def test_idle_gpu_is_eligible(self):
        self.assertTrue(gpu_claim.is_eligible(self.base()))
    def test_any_compute_pid_blocks_even_if_zero_util(self):
        row = self.base()
        row["compute_processes"] = [{"pid": 1234, "used_memory_mib": 0}]
        self.assertFalse(gpu_claim.is_eligible(row))
    def test_memory_threshold_blocks(self):
        row = self.base()
        row["memory_used_mib"] = 513
        self.assertFalse(gpu_claim.is_eligible(row))
    def test_utilization_threshold_blocks(self):
        row = self.base()
        row["utilization_gpu_pct"] = 6
        self.assertFalse(gpu_claim.is_eligible(row))

if __name__ == "__main__":
    unittest.main()

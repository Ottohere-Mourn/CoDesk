import unittest
from scripts import siteact_state_fixture_v1 as fx

class SiteActStateTests(unittest.TestCase):
    def test_ready_snapshot_exact_pass(self):
        s=fx.new_state()
        fx.create_snapshot(s,fx.EXPECTED_READY_SNAPSHOT)
        self.assertTrue(fx.score_ready_actor(s))
    def test_wrong_source_reference_rejected(self):
        s=fx.new_state(); v=dict(fx.EXPECTED_READY_SNAPSHOT); v["calibration_id"]="CAL-99"
        with self.assertRaises(ValueError): fx.create_snapshot(s,v)
    def test_deviation_updates_latest_gate_without_mutating_evidence(self):
        s=fx.new_state(); before=[dict(x) for x in s["evidence"]]
        fx.log_deviation_and_hold(s,fx.DEVIATION["deviation_id"],fx.DEVIATION["reason_code"])
        self.assertEqual(s["evidence"],before)
        self.assertTrue(fx.score_deviation_actor(s))
    def test_shared_stale_snapshot_is_distinct_from_wrong_deviation(self):
        s=fx.new_state();fx.create_snapshot(s,fx.EXPECTED_READY_SNAPSHOT)
        fx.log_deviation_and_hold(s,fx.DEVIATION["deviation_id"],fx.DEVIATION["reason_code"])
        self.assertTrue(fx.expected_shared_stale_signature(s))
        self.assertFalse(fx.score_shared_final(s))
    def test_current_hold_snapshot_recovery_passes(self):
        s=fx.new_state();fx.create_snapshot(s,fx.EXPECTED_READY_SNAPSHOT)
        fx.log_deviation_and_hold(s,fx.DEVIATION["deviation_id"],fx.DEVIATION["reason_code"])
        fx.create_snapshot(s,{**fx.EXPECTED_HOLD_SNAPSHOT})
        s["events"].append({"action":"SNAPSHOT_REVALIDATED","revision":s["revision"]})
        self.assertTrue(fx.score_shared_final(s))
    def test_wrong_or_duplicate_deviation_rejected(self):
        s=fx.new_state()
        with self.assertRaises(ValueError): fx.log_deviation_and_hold(s,"PD-WRONG",fx.DEVIATION["reason_code"])
        fx.log_deviation_and_hold(s,fx.DEVIATION["deviation_id"],fx.DEVIATION["reason_code"])
        with self.assertRaises(ValueError): fx.log_deviation_and_hold(s,fx.DEVIATION["deviation_id"],fx.DEVIATION["reason_code"])

if __name__ == "__main__": unittest.main()

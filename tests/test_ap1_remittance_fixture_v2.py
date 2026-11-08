import copy
import unittest

from scripts import ap1_remittance_fixture_v2 as fx


class AP1RemittanceV2Tests(unittest.TestCase):
    def test_isolated_actor_local_workspaces_both_pass(self):
        result = fx.ma_id_control()
        self.assertTrue(result["private_states_distinct"])
        self.assertTrue(result["actor_a"]["success"], result["actor_a"])
        self.assertTrue(result["actor_b"]["success"], result["actor_b"])
        self.assertEqual(result["a_total_cents"], 214000)
        self.assertEqual(result["b_invoice_071_balance_cents"], 95000)

    def test_four_invoice_reconciliation_has_exact_rows_and_exception(self):
        state = fx.fresh_state()
        fx.prepare_payment_draft(state)
        result = fx.evaluate_a(state)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["expected_rows"], [
            {"invoice_id": "INV-AP-071", "amount_cents": 120000},
            {"invoice_id": "INV-AP-072", "amount_cents": 30000},
            {"invoice_id": "INV-AP-073", "amount_cents": 64000},
        ])
        self.assertEqual(result["expected_total_cents"], 214000)
        self.assertEqual(state["exceptions"], [fx.EXPECTED_EXCEPTION])
        self.assertNotIn("INV-AP-074", {row["invoice_id"] for row in result["actual_rows"]})

    def test_shared_credit_update_invalidates_old_batch(self):
        result = fx.shared_stale_control()
        self.assertFalse(result["success"], result)
        self.assertFalse(result["actor_a"]["success"])
        self.assertTrue(result["actor_b"]["success"])
        self.assertEqual(result["actor_a"]["expected_total_cents"], 189000)
        self.assertEqual(result["actor_a"]["actual_total_cents"], 214000)
        self.assertEqual(result["actor_a"]["draft_source_revision"], 1)
        self.assertEqual(result["actor_a"]["ledger_revision"], 2)

    def test_rebuild_after_credit_update_is_normal_recovery(self):
        result = fx.shared_recovery_control()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["actor_a"]["actual_total_cents"], 189000)
        self.assertEqual(result["actor_a"]["draft_source_revision"], 2)
        self.assertTrue(result["actor_b"]["success"])

    def test_per_action_lock_does_not_change_terminal_business_oracle(self):
        shared = fx.shared_stale_control()
        shared_lock = fx.shared_stale_control()
        self.assertEqual(shared, shared_lock)
        self.assertFalse(shared_lock["success"])

    def test_credit_cannot_be_applied_twice(self):
        state = fx.fresh_state()
        fx.apply_credit(state)
        with self.assertRaises(ValueError):
            fx.apply_credit(state)
        self.assertEqual(state["ledger"]["INV-AP-071"]["open_cents"], 95000)
        self.assertEqual(state["ledger_revision"], 2)
        self.assertEqual(len(state["audit"]), 1)

    def test_credit_on_disputed_or_wrong_invoice_is_not_silently_accepted(self):
        state = fx.fresh_state()
        state["credits"]["CN-AP-019"]["invoice_id"] = "INV-AP-074"
        with self.assertRaises(ValueError):
            fx.apply_credit(state)

    def test_wrong_credit_amount_fails_actor_b_oracle(self):
        state = fx.fresh_state()
        fx.apply_credit(state)
        state["audit"][0]["amount_cents"] = 24000
        self.assertFalse(fx.evaluate_b(state)["success"])

    def test_disputed_invoice_in_payment_batch_fails(self):
        state = fx.fresh_state()
        fx.prepare_payment_draft(state)
        state["payment_draft"]["rows"].append({"invoice_id": "INV-AP-074", "amount_cents": 18000})
        state["payment_draft"]["total_cents"] += 18000
        self.assertFalse(fx.evaluate_a(state)["success"])

    def test_source_mutation_fails_and_recovery_does_not_modify_sources(self):
        state = fx.fresh_state()
        fx.prepare_payment_draft(state)
        state["source_hashes"]["RA-221"] = "changed"
        self.assertFalse(fx.evaluate_a(state)["success"])
        recovered = fx.shared_recovery_control()
        self.assertTrue(recovered["success"])
        self.assertEqual(fx.fresh_state()["source_hashes"], fx.SOURCE_HASHES)


if __name__ == "__main__":
    unittest.main()

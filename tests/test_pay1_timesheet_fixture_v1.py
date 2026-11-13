import copy, unittest
from scripts import pay1_timesheet_fixture_v1 as fx


class Pay1OfflineContractTests(unittest.TestCase):
    def test_isolated_tasks_pass_on_identical_initial_clones(self):
        a, b = fx.fresh_state(), fx.fresh_state()
        fx.append_payment(a, hours_tenths=fx.INITIAL_HOURS_TENTHS)
        fx.apply_signed_correction(b)
        result = fx.evaluate_isolated(a, b)
        self.assertTrue(result["success"], result)
        self.assertEqual(a["timecard"]["approved_hours_tenths"], 80)
        self.assertEqual(b["timecard"]["approved_hours_tenths"], 60)

    def test_shared_stale_submission_fails_only_payment_task(self):
        state = fx.fresh_state()
        fx.apply_signed_correction(state)
        fx.append_payment(state, hours_tenths=fx.INITIAL_HOURS_TENTHS)
        result = fx.evaluate_shared(state)
        self.assertFalse(result["success"])
        self.assertFalse(result["A"]["one_exact_current_payment"])
        self.assertTrue(result["B"]["success"])

    def test_completion_order_late_correction_invalidates_completed_payroll_line(self):
        state = fx.fresh_state()
        fx.append_payment(state, hours_tenths=fx.INITIAL_HOURS_TENTHS)
        self.assertTrue(fx.evaluate_actor(state, "A")["success"])
        fx.apply_signed_correction(state)
        self.assertTrue(fx.evaluate_actor(state, "B")["success"])
        result = fx.evaluate_shared(state)
        self.assertFalse(result["A"]["one_exact_current_payment"])
        self.assertTrue(result["B"]["success"])
        self.assertFalse(result["success"])

    def test_shared_reread_and_recovery_passes(self):
        state = fx.fresh_state()
        fx.apply_signed_correction(state)
        fx.append_payment(state, hours_tenths=fx.CORRECTED_HOURS_TENTHS)
        self.assertTrue(fx.evaluate_shared(state)["success"])

    def test_shared_stale_payment_can_be_voided_and_replaced_normally(self):
        state = fx.fresh_state()
        fx.apply_signed_correction(state)
        fx.append_payment(state, hours_tenths=fx.INITIAL_HOURS_TENTHS)
        stale_id = state["payment_lines"][0]["payment_id"]
        fx.void_payment(state, stale_id)
        fx.append_payment(state, hours_tenths=fx.CORRECTED_HOURS_TENTHS)
        result = fx.evaluate_shared(state)
        self.assertTrue(result["success"], result)
        self.assertEqual([row["status"] for row in state["payment_lines"]], ["voided", "submitted"])

    def test_unlogged_void_or_multiple_active_payments_do_not_pass(self):
        state = fx.fresh_state()
        fx.apply_signed_correction(state)
        fx.append_payment(state, hours_tenths=fx.INITIAL_HOURS_TENTHS)
        state["payment_lines"][0]["status"] = "voided"
        fx.append_payment(state, hours_tenths=fx.CORRECTED_HOURS_TENTHS)
        self.assertFalse(fx.evaluate_shared(state)["A"]["success"])
        state = fx.fresh_state()
        fx.apply_signed_correction(state)
        fx.append_payment(state, hours_tenths=fx.CORRECTED_HOURS_TENTHS)
        fx.append_payment(state, hours_tenths=fx.CORRECTED_HOURS_TENTHS)
        self.assertFalse(fx.evaluate_shared(state)["A"]["success"])

    def test_wrong_employee_week_amount_or_duplicate_payment_fails(self):
        for mutate in (
            lambda s: s["payment_lines"][0].update(employee_id="E-09"),
            lambda s: s["payment_lines"][0].update(week_id="W18"),
            lambda s: s["payment_lines"][0].update(amount_cents=25599),
            lambda s: s["payment_lines"].append(copy.deepcopy(s["payment_lines"][0])),
        ):
            state = fx.fresh_state()
            fx.append_payment(state, hours_tenths=80)
            mutate(state)
            self.assertFalse(fx.evaluate_actor(state, "A")["success"])

    def test_actor_ownership_is_enforced(self):
        state = fx.fresh_state()
        fx.apply_signed_correction(state, actor="A")
        self.assertFalse(fx.evaluate_actor(state, "B")["success"])
        state = fx.fresh_state()
        fx.append_payment(state, hours_tenths=80, actor="B")
        self.assertFalse(fx.evaluate_actor(state, "A")["success"])
        self.assertFalse(fx.evaluate_actor(state, "B")["payment_untouched"])

    def test_unproven_or_mutated_sources_fail(self):
        state = fx.fresh_state()
        fx.append_payment(state, hours_tenths=80)
        state["source_fixture_sha256"] = "0" * 64
        self.assertFalse(fx.evaluate_actor(state, "A")["success"])
        state = fx.fresh_state()
        fx.apply_signed_correction(state)
        state["audit_log"][0]["authorized_by"] = "UNSIGNED"
        self.assertFalse(fx.evaluate_actor(state, "B")["success"])

    def test_unrelated_record_mutation_fails(self):
        state = fx.fresh_state()
        fx.append_payment(state, hours_tenths=80)
        state["unrelated_guard"]["approved_hours_tenths"] = 60
        self.assertFalse(fx.evaluate_actor(state, "A")["success"])


if __name__ == "__main__":
    unittest.main()

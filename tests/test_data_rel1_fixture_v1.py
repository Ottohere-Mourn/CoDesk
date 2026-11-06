"""Unit tests for the DATA-REL1 offline workspace-local contract."""
import copy
import unittest

from scripts import data_rel1_fixture_v1 as fx


class DataRel1FixtureTests(unittest.TestCase):
    def test_ma_id_private_workspaces_both_pass_same_oracle(self):
        workspace_a = fx.initial_workspace()
        fx.build_ready_package(workspace_a)
        workspace_b = fx.initial_workspace()
        fx.register_exclusion(workspace_b, fx.RESTRICTION_EVIDENCE)
        result = fx.evaluate_episode({"A": workspace_a, "B": workspace_b})
        self.assertTrue(result["actors"]["A"]["success"], result)
        self.assertTrue(result["actors"]["B"]["success"], result)
        self.assertTrue(result["success"], result)

    def test_shared_late_exclusion_invalidates_old_ready_package(self):
        shared = fx.initial_workspace()
        fx.build_ready_package(shared)
        self.assertTrue(fx.evaluate_actor(shared, "A")["success"])
        fx.register_exclusion(shared, fx.RESTRICTION_EVIDENCE)
        result = fx.evaluate_episode({"A": shared, "B": shared})
        self.assertFalse(result["actors"]["A"]["success"], result)
        self.assertTrue(result["actors"]["B"]["success"], result)
        self.assertFalse(result["success"], result)
        self.assertFalse(
            result["actors"]["A"]["checks"]["rows_match_current_eligible_subjects"]
        )

    def test_revoke_quarantine_and_rebuild_recovers(self):
        shared = fx.initial_workspace()
        old = fx.build_ready_package(shared, "PKG-OLD")
        fx.register_exclusion(shared, fx.RESTRICTION_EVIDENCE)
        fx.revoke_and_quarantine(shared, old["package_id"])
        fresh = fx.build_ready_package(shared, "PKG-CURRENT")
        self.assertEqual(fresh["row_subject_ids"], ["SUB-22"])
        result = fx.evaluate_episode({"A": shared, "B": shared})
        self.assertTrue(result["actors"]["A"]["success"], result)
        self.assertTrue(result["actors"]["B"]["success"], result)
        self.assertTrue(result["success"], result)
        self.assertEqual(old["status"], "REVOKED")
        self.assertEqual(old["artifact_location"], "QUARANTINE")

    def test_revoked_but_exposed_old_export_still_fails(self):
        shared = fx.initial_workspace()
        old = fx.build_ready_package(shared, "PKG-OLD")
        fx.register_exclusion(shared, fx.RESTRICTION_EVIDENCE)
        old["status"] = "REVOKED"
        old["artifact_location"] = "STAGING_ACTIVE"
        old["manifest_sha256"] = fx._package_digest(old)
        fx.build_ready_package(shared, "PKG-CURRENT")
        result = fx.evaluate_actor(shared, "A")
        self.assertFalse(result["success"], result)
        self.assertFalse(
            result["checks"]["restricted_artifacts_not_active_or_exposed"]
        )

    def test_revocation_without_required_audit_fails(self):
        shared = fx.initial_workspace()
        old = fx.build_ready_package(shared, "PKG-OLD")
        fx.register_exclusion(shared, fx.RESTRICTION_EVIDENCE)
        old["status"] = "REVOKED"
        old["artifact_location"] = "QUARANTINE"
        old["manifest_sha256"] = fx._package_digest(old)
        fx.build_ready_package(shared, "PKG-CURRENT")
        result = fx.evaluate_actor(shared, "A")
        self.assertFalse(result["success"], result)
        self.assertFalse(
            result["checks"]["restricted_artifacts_not_active_or_exposed"]
        )

    def test_external_release_is_rejected_even_without_current_exclusion(self):
        workspace = fx.initial_workspace()
        package = fx.build_ready_package(workspace)
        package["status"] = "RELEASED"
        package["artifact_location"] = "EXTERNAL_RELEASE"
        package["manifest_sha256"] = fx._package_digest(package)
        fx.build_ready_package(workspace, "PKG-CURRENT")
        result = fx.evaluate_actor(workspace, "A")
        self.assertFalse(result["success"], result)
        self.assertFalse(
            result["checks"]["packages_remain_in_local_staging_or_quarantine"]
        )

    def test_external_release_switch_must_remain_disabled(self):
        workspace = fx.initial_workspace()
        fx.build_ready_package(workspace)
        workspace["release_policy"]["external_release_enabled"] = True
        result = fx.evaluate_actor(workspace, "A")
        self.assertFalse(result["success"], result)
        self.assertFalse(result["checks"]["external_release_disabled"])

    def test_restriction_requires_explicit_unreleased_package_rule(self):
        workspace = fx.initial_workspace()
        workspace["release_policy"]["unreleased_packages_must_match_current_policy"] = False
        fx.register_exclusion(workspace, fx.RESTRICTION_EVIDENCE)
        result = fx.evaluate_actor(workspace, "B")
        self.assertFalse(result["success"], result)
        self.assertFalse(
            result["checks"]["exactly_one_active_source_verified_exclusion"]
        )

    def test_wrong_source_evidence_cannot_complete_privacy_task(self):
        shared = fx.initial_workspace()
        wrong = copy.deepcopy(fx.RESTRICTION_EVIDENCE)
        wrong["approved_by"] = "UNAUTHORIZED"
        with self.assertRaises(ValueError):
            fx.register_exclusion(shared, wrong)
        self.assertFalse(fx.evaluate_actor(shared, "B")["success"])

    def test_manifest_mutation_invalidates_hash_and_oracle(self):
        workspace = fx.initial_workspace()
        package = fx.build_ready_package(workspace)
        package["row_subject_ids"].remove("SUB-17")
        result = fx.evaluate_actor(workspace, "A")
        self.assertFalse(result["success"], result)
        self.assertFalse(result["checks"]["manifest_hash_valid"])
        self.assertFalse(
            result["checks"]["rows_match_current_eligible_subjects"]
        )

    def test_duplicate_active_ready_packages_fail(self):
        workspace = fx.initial_workspace()
        fx.build_ready_package(workspace, "PKG-1")
        fx.build_ready_package(workspace, "PKG-2")
        result = fx.evaluate_actor(workspace, "A")
        self.assertFalse(result["success"], result)
        self.assertEqual(
            result["reason"], "requires_exactly_one_active_ready_package"
        )

    def test_duplicate_exclusion_source_is_rejected(self):
        workspace = fx.initial_workspace()
        fx.register_exclusion(workspace, fx.RESTRICTION_EVIDENCE)
        with self.assertRaises(ValueError):
            fx.register_exclusion(workspace, fx.RESTRICTION_EVIDENCE)

    def test_package_audit_version_must_match_manifest(self):
        workspace = fx.initial_workspace()
        fx.build_ready_package(workspace)
        workspace["audit_log"][0]["policy_version"] = 99
        result = fx.evaluate_actor(workspace, "A")
        self.assertFalse(result["success"], result)
        self.assertFalse(result["checks"]["build_audit_present"])

    def test_exclusion_audit_version_must_match_restriction(self):
        workspace = fx.initial_workspace()
        fx.register_exclusion(workspace, fx.RESTRICTION_EVIDENCE)
        workspace["audit_log"][0]["policy_version"] = 99
        result = fx.evaluate_actor(workspace, "B")
        self.assertFalse(result["success"], result)
        self.assertFalse(result["checks"]["matching_actor_audit_present"])

    def test_oracle_has_no_condition_argument(self):
        workspace = fx.initial_workspace()
        fx.build_ready_package(workspace)
        self.assertEqual(
            fx.evaluate_actor(workspace, "A"),
            fx.evaluate_actor(workspace, "A"),
        )


if __name__ == "__main__":
    unittest.main()

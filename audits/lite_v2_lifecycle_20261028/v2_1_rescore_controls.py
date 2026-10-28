"""Retrospectively score real GUI v2.0.0 artifacts with independent v2.1 Oracle."""
from __future__ import annotations

import json
from pathlib import Path

from oscombo.collab.data_to_deck_lite_v2_1.oracle import evaluate


RUNS = {
    "scripted_shared_positive": ("cdd-lite-v2-scripted-shared-pos-v2-20261027T143400Z", True),
    "scripted_isolated_positive": ("cdd-lite-v2-scripted-isolated-pos-v2-20261027T143730Z", True),
    "scripted_shared_negative": ("cdd-lite-v2-scripted-shared-neg-20261027T142025Z", False),
    "model_shared_20261028": ("cdd-lite-v2-life-shared-20261028T090600Z", True),
    "model_isolated_20261028": ("cdd-lite-v2-life-isolated-20261028T092900Z", True),
}


def main() -> None:
    root = Path(__file__).resolve().parents[2] / "runs"
    out = {}
    for label, (run_id, expected) in RUNS.items():
        run = root / run_id
        score = evaluate(run / "fixtures/quarterly_authority.ods",
                         run / "artifacts/A/verified_analysis.ods",
                         run / "fixtures/management_draft.odp",
                         run / "artifacts/B/final_management_brief.odp")
        out[label] = {"run_id": run_id, "original_case_version": "2.0.0",
                      "rescore_case_version": score["case_version"],
                      "a_success": score["actors"]["A"]["success"],
                      "b_success": score["actors"]["B"]["success"],
                      "joint_success": score["joint_success"],
                      "expected_control_outcome": expected,
                      "control_matches_expectation": score["joint_success"] == expected,
                      "scope": "retrospective scorer check; original run Oracle unchanged"}
    target = Path(__file__).with_name("v2_1_rescore_controls.json")
    target.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

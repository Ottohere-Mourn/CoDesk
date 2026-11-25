#!/usr/bin/env python3
"""Run CONC-02 deterministic validity gates and any archived Guest Gate-5 evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "private"))
sys.path.insert(0, str(HERE / "integration"))
import wellposedness

OBSERVATION = HERE / "private" / "gate5_guest_observation.json"


def self_validate():
    result = wellposedness.gates()
    try:
        observation = json.loads(OBSERVATION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        observation = None
    timeout = float((observation or {}).get("conc_role_timeout_s", result["conc_role_timeout_s"]))
    elapsed = float((observation or {}).get("careful_conc_elapsed_s", float("inf")))
    overlap = float((observation or {}).get("overlap_s", 0.0))
    g5 = bool(observation and observation.get("reference_guest_replay") is True
              and observation.get("schedule_complete") is True
              and observation.get("joint_pass") is True
              and overlap > 0 and elapsed <= 0.55 * timeout)
    result["gate5_careful_conc_feasible"] = g5
    result["gate5_real_tool_timing"] = g5
    result["careful_conc_elapsed_s"] = elapsed if observation else None
    result["all_gates_pass"] = all(result[key] for key in (
        "gate1_pristine_fail", "gate2_gt_seq_ab_exists", "gate3_gt_seq_ba_exists",
        "gate4_gt_naive_race_corrupts", "gate5_careful_conc_feasible"))
    return result


def main():
    result = self_validate()
    keys = ("gate1_pristine_fail", "gate2_gt_seq_ab_exists", "gate3_gt_seq_ba_exists",
            "gate4_gt_naive_race_corrupts", "gate5_fixture_feasible", "gate5_careful_conc_feasible")
    for key in keys:
        print(f"{key}={'PASS' if result.get(key) else 'PENDING/FAIL'}")
    print(f"gate5_real_tool_timing={result['gate5_real_tool_timing']}")
    print(f"fixture_elapsed_s={result['fixture_elapsed_s']}")
    print(f"all_gates_pass={result['all_gates_pass']}")
    return 0 if result["all_gates_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

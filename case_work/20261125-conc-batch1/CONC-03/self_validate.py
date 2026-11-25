#!/usr/bin/env python3
"""Run deterministic CONC-03 gates and summarize any real Guest evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "private"))
sys.path.insert(0, str(HERE / "integration"))
from wellposedness import gates

OBSERVATION = HERE / "private" / "gate5_guest_observation.json"


def main():
    result = gates()
    observation = None
    try:
        observation = json.loads(OBSERVATION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    result["gate5_careful_conc_feasible"] = bool(observation and observation.get("joint_pass") is True
        and observation.get("schedule_complete") is True and observation.get("overlap_s", 0) > 0
        and observation.get("careful_conc_elapsed_s", float("inf")) <= 0.55 * result["conc_role_timeout_s"])
    result["gate5_real_tool_timing"] = bool(observation and observation.get("reference_guest_replay") is True
        and observation.get("schedule_complete") is True and observation.get("joint_pass") is True)
    result["all_gates_pass"] = all(result[k] for k in ("gate1_pristine_fail", "gate2_gt_seq_ab_exists",
        "gate3_gt_seq_ba_exists", "gate4_gt_naive_race_corrupts", "gate5_careful_conc_feasible"))
    for key in ("gate1_pristine_fail", "gate2_gt_seq_ab_exists", "gate3_gt_seq_ba_exists",
                "gate4_gt_naive_race_corrupts", "gate5_fixture_feasible", "gate5_careful_conc_feasible"):
        print(f"{key}={'PASS' if result.get(key) else 'PENDING/FAIL'}")
    print(f"gate5_real_tool_timing={result['gate5_real_tool_timing']}")
    print(f"fixture_elapsed_s={result['fixture_elapsed_s']}")
    print(f"all_gates_pass={result['all_gates_pass']}")
    return 0 if result["all_gates_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

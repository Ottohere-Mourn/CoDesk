#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from private.wellposedness import gates

HERE=Path(__file__).resolve().parent;OBS=HERE/"private/gate5_guest_observation.json"
def main():
    r=gates()
    try:obs=json.loads(OBS.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):obs=None
    r["gate5_careful_conc_feasible"]=bool(obs and obs.get("joint_pass") and obs.get("schedule_complete"))
    r["gate5_real_tool_timing"]=bool(obs and obs.get("reference_guest_replay") and obs.get("joint_pass"))
    for k in ("gate1_pristine_fail","gate2_gt_seq_ab_exists","gate3_gt_seq_ba_exists","gate4_gt_naive_race_corrupts","gate5_fixture_feasible","gate5_careful_conc_feasible"):
        print(f"{k}={'PASS' if r.get(k) else 'PENDING/FAIL'}")
    print(f"gate5_real_tool_timing={r['gate5_real_tool_timing']}");print(f"fixture_elapsed_s={r['fixture_elapsed_s']}")
    print(f"real_guest_observation={'PRESENT' if obs else 'PENDING'}")
    # Permit queueing only after all local, deterministic preflight checks pass.
    return 0 if all(r.get(k,False) for k in ("gate1_pristine_fail","gate2_gt_seq_ab_exists","gate3_gt_seq_ba_exists","gate4_gt_naive_race_corrupts","gate5_fixture_feasible")) else 2
if __name__=="__main__":raise SystemExit(main())

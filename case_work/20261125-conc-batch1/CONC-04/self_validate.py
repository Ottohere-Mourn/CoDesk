#!/usr/bin/env python3
"""Run CONC-04 deterministic fixture checks; real Guest Gate 5 remains separate."""
from __future__ import annotations
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"private"));sys.path.insert(0,str(HERE/"integration"))
from wellposedness import gates
OBS=HERE/"private/gate5_guest_observation.json"

def main():
    result=gates(); obs=None
    try: obs=json.loads(OBS.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): pass
    result["gate5_careful_conc_feasible"]=bool(obs and obs.get("joint_pass") and obs.get("schedule_complete"))
    result["gate5_real_tool_timing"]=bool(obs and obs.get("reference_guest_replay") and obs.get("joint_pass"))
    result["all_gates_pass"]=all(result.get(k,False) for k in ("gate1_pristine_fail","gate2_gt_seq_ab_exists","gate3_gt_seq_ba_exists","gate4_gt_naive_race_corrupts","gate5_careful_conc_feasible"))
    for k in ("gate1_pristine_fail","gate2_gt_seq_ab_exists","gate3_gt_seq_ba_exists","gate4_gt_naive_race_corrupts","gate5_fixture_feasible","gate5_careful_conc_feasible"):
        print(f"{k}={'PASS' if result.get(k) else 'PENDING/FAIL'}")
    print(f"gate5_real_tool_timing={result['gate5_real_tool_timing']}")
    print(f"fixture_elapsed_s={result['fixture_elapsed_s']}")
    print(f"all_gates_pass={result['all_gates_pass']}")
    return 0 if result["all_gates_pass"] else 2
if __name__=="__main__": raise SystemExit(main())

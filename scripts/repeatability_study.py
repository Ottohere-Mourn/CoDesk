#!/usr/bin/env python3
"""Small real-container replay check; measures scripted determinism, not agents."""
from __future__ import annotations
import hashlib
import json
import shutil
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swcub.actors import HumanReplayActor, ScriptedCLIActor, ScriptedFocusGUIActor, ScriptedGUIActor
from swcub.core import EventLog
from swcub.environment import DockerX11Workspace
from swcub.evaluator import FocusStateEvaluator, RequiredRowsEvaluator
from swcub.orchestrator import DualActorOrchestrator


POLICIES = {
    "csv_gui_then_cli": ("csv", ["gui_actor", "cli_actor"], False, "csv"),
    "csv_cli_then_gui": ("csv", ["cli_actor", "gui_actor"], False, "csv"),
    "focus_recovery": ("focus", ["gui_actor", "human_replay", "gui_actor"], True, "focus"),
    "focus_stale_failure": ("focus", ["gui_actor", "human_replay", "gui_actor"], False, "focus"),
}


def actors_for(policy: str):
    if policy.startswith("csv_"):
        return [ScriptedGUIActor(), ScriptedCLIActor()]
    return [ScriptedFocusGUIActor(recover=policy == "focus_recovery"), HumanReplayActor()]


def main() -> int:
    repetitions = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    if repetitions < 1 or repetitions > 20:
        raise SystemExit("repetitions must be between 1 and 20")
    out = ROOT / "outputs" / "repeatability"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = DockerX11Workspace(ROOT, command_timeout=30)
    trial_rows: list[dict[str, object]] = []
    try:
        env.build()
        for policy, (task, schedule, recover, state_kind) in POLICIES.items():
            for index in range(1, repetitions + 1):
                env.log = EventLog()
                episode = env.reset(task=task)
                trial_out = out / policy / f"trial-{index:02d}"
                if task == "csv":
                    evaluator = RequiredRowsEvaluator()
                else:
                    evaluator = FocusStateEvaluator()
                start = time.monotonic()
                report = DualActorOrchestrator(env).run(
                    actors_for(policy), schedule, evaluator, trial_out, copy_artifacts=False)
                elapsed = time.monotonic() - start
                state_path = env.csv_path if state_kind == "csv" else env.state_path
                assert state_path is not None
                state_bytes = state_path.read_bytes()
                success = bool(report["evaluation"]["success"])
                wanted_success = policy != "focus_stale_failure"
                row = {
                    "policy": policy,
                    "trial": index,
                    "environment_id": episode,
                    "evaluation_success": success,
                    "expected_success": wanted_success,
                    "expected_outcome": success == wanted_success,
                    "state_sha256": hashlib.sha256(state_bytes).hexdigest(),
                    "elapsed_seconds": round(elapsed, 3),
                    "schedule": schedule,
                }
                trial_rows.append(row)
                print(f"{policy} {index}/{repetitions}: success={success} "
                      f"state={row['state_sha256'][:12]} elapsed={elapsed:.2f}s", flush=True)
    finally:
        env.close()

    grouped: dict[str, list[dict[str, object]]] = {}
    for row in trial_rows:
        grouped.setdefault(str(row["policy"]), []).append(row)
    policies = {}
    all_valid = True
    for policy, rows in grouped.items():
        hashes = sorted({str(row["state_sha256"]) for row in rows})
        valid = all(bool(row["expected_outcome"]) for row in rows) and len(hashes) == 1
        all_valid &= valid
        times = [float(row["elapsed_seconds"]) for row in rows]
        policies[policy] = {
            "episodes": len(rows),
            "expected_outcome_rate": sum(bool(r["expected_outcome"]) for r in rows) / len(rows),
            "evaluation_success_count": sum(bool(r["evaluation_success"]) for r in rows),
            "unique_final_state_hashes": len(hashes),
            "final_state_sha256": hashes[0] if len(hashes) == 1 else hashes,
            "elapsed_seconds": {"min": round(min(times), 3),
                                "median": round(statistics.median(times), 3),
                                "max": round(max(times), 3)},
            "repeatability_check": "PASS" if valid else "FAIL",
        }
    result = {
        "purpose": "bounded scripted replay repeatability check on fresh Docker/Xvfb environments",
        "episodes_per_policy": repetitions,
        "total_episodes": len(trial_rows),
        "policies": policies,
        "trials": trial_rows,
        "all_checks_passed": all_valid,
        "limitations": [
            "This validates deterministic scripted outcomes only; it is not a model or human study.",
            "Serial actor schedules are replayed in fresh containers; simultaneous input is not measured.",
            "Elapsed time includes scheduled actor turns, evaluation, and report/log writes, but not image build or reset.",
        ],
    }
    (out / "study.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# Repeatability Study", "", result["purpose"], "",
             f"Episodes: {len(trial_rows)} total, {repetitions} per policy.", "",
             "| Policy | Expected outcomes | Unique final states | Median episode time | Check |",
             "|---|---:|---:|---:|---|"]
    for policy, item in policies.items():
        lines.append(f"| {policy} | {int(item['expected_outcome_rate'] * item['episodes'])}/{item['episodes']} "
                     f"| {item['unique_final_state_hashes']} | {item['elapsed_seconds']['median']:.3f}s "
                     f"| {item['repeatability_check']} |")
    lines += ["", "These are scripted infrastructure checks. They provide no model, human, or benchmark-validity evidence.",
              "See `study.json` for trial hashes, environment IDs, and timings.", ""]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"all_checks_passed": all_valid, "policies": policies}, indent=2))
    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

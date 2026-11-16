"""Produce a non-executable, matched calibration plan for unbuilt v3 candidates."""
import argparse
import copy
import json
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parent
CONDITIONS = {
    "solo_a": ("a",),
    "solo_b": ("b",),
    "sequential_ab": ("a", "b"),
    "sequential_ba": ("b", "a"),
    "parallel_shared": ("a", "b"),
    "parallel_isolated_api_control": ("a", "b"),
}


def make_plan(catalog, pair_ids, harnesses, repetitions, *, isolated_control=False):
    pairs = {pair["id"]: pair for pair in catalog["pairs"]}
    if not pair_ids or len(set(pair_ids)) != len(pair_ids) or set(pair_ids) - pairs.keys():
        raise ValueError("Select unique known pair IDs")
    if not harnesses or len(set(harnesses)) != len(harnesses) or set(harnesses) - {"codex", "freehand"}:
        raise ValueError("Select unique supported harnesses")
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("Repetitions must be a positive integer")
    modes = list(catalog["conditions"])
    if set(modes) != set(CONDITIONS) - {"parallel_isolated_api_control"} or len(modes) != 5:
        raise ValueError("The five matched primary conditions are required")
    if isolated_control:
        modes.append("parallel_isolated_api_control")
    jobs = []
    blockers = {}
    publication_blockers = {}
    for pair_id in pair_ids:
        pair = pairs[pair_id]
        blockers[pair_id] = [name for name in catalog["calibration_prerequisites"] if not pair["readiness"].get(name)]
        publication_blockers[pair_id] = [name for name in catalog["required_readiness"] if not pair["readiness"].get(name)]
        for repetition in range(1, repetitions + 1):
            ordered_harnesses = list(harnesses)
            if repetition % 2 == 0:
                ordered_harnesses.reverse()
            for harness in ordered_harnesses:
                ordered_modes = list(modes)
                random.Random(f"{catalog['dataset']}:{pair_id}:{harness}:{repetition}").shuffle(ordered_modes)
                for mode in ordered_modes:
                    roles = list(CONDITIONS[mode])
                    jobs.append({
                        "id": f"{pair_id}-{harness}-instance-{repetition:03d}-{mode}",
                        "pair": pair_id, "harness": harness, "condition": mode, "roles": roles,
                        "input_variant": f"{pair_id}-instance-{repetition:03d}",
                        "input_manifest_sha256": None,
                        "fresh_environment": True,
                        "shared_desktop": mode != "parallel_isolated_api_control",
                        "shared_final_project": mode != "parallel_isolated_api_control",
                        "simultaneous_agents": 2 if mode.startswith("parallel_") else 1,
                        "agent_rollouts": len(roles),
                        "budget_per_agent": copy.deepcopy(catalog["baseline_budget"]),
                    })
    return {
        "schema_version": 1, "dataset": catalog["dataset"], "plan_only": True,
        "execution_supported": False, "calibration_readiness_blockers": blockers,
        "publication_readiness_blockers": publication_blockers,
        "score_scope": "solo scores are not joint outcomes; primary joint outcomes use one common final project",
        "repetition_scope": "matched generated input variants; these are not repeated stochastic runs of one fixed input",
        "api_control_scope": "isolated parallel is an optional diagnostic, never a replacement for shared parallel",
        "totals": {"conditions": len(jobs), "agent_rollouts": sum(job["agent_rollouts"] for job in jobs)},
        "jobs": jobs,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", nargs="+", default=["p10"])
    parser.add_argument("--harnesses", nargs="+", default=["codex", "freehand"])
    parser.add_argument("--repetitions", type=int, default=1, help="Matched input variants, not model randomness seeds")
    parser.add_argument("--isolated-control", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    catalog = json.loads((ROOT / "catalog.json").read_text())
    plan = make_plan(catalog, args.pairs, args.harnesses, args.repetitions, isolated_control=args.isolated_control)
    content = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        with args.out.open("x") as stream:
            stream.write(content)
    else:
        print(content, end="")


if __name__ == "__main__":
    main()

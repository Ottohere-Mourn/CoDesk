"""Execute the first matched p10 calibration only after native authoring gates pass."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from experiments.professional_native_batch import validate_preflight
from experiments.professional_trajectories import hashes, save
from tasks.professional_v3.protocol import make_plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "root", "credentials", "freehand-runtime", "codex-binary", "validation", "codex-preflight", "freehand-preflight", "resource-gate"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1]
    validation = json.loads(args.validation.read_text())
    assert json.loads((args.dataset.parent / "extra-authoring-checks.json").read_text())["passed"]
    assert validation["passed"] and set(validation["cases"]) == {"pristine", "a_only", "b_only", "ab", "ba"}
    assert len(validation["negative_controls"]) >= 5
    assert hashes(args.dataset / "dataset/pairs/p10/inputs") == validation["input_hashes"]
    for name, digest in validation["source_hashes"].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest, name
    for harness in ("codex", "freehand"):
        root = getattr(args, harness + "_preflight")
        validate_preflight(root, harness, "container-unrestricted", "hybrid", 4)
        manifest = json.loads((root / "manifest.json").read_text())
        assert manifest["tasks"] == ["p10a", "p10b"]
        for task in manifest["tasks"]:
            assert json.loads((root / task / "result.json").read_text())["input_hashes"] == validation["input_hashes"]
    catalog = json.loads((source / "tasks/professional_v3/catalog.json").read_text())
    plan = make_plan(catalog, ["p10"], ["codex", "freehand"], 1)
    args.root.mkdir(parents=True, exist_ok=False)
    input_manifest = {"inputs": validation["input_hashes"],
        "prompts": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (args.dataset / "dataset/pairs/p10").glob("task_?.md")}}
    save(args.root / "input-manifest.json", input_manifest)
    manifest_digest = hashlib.sha256((args.root / "input-manifest.json").read_bytes()).hexdigest()
    for job in plan["jobs"]:
        job["input_manifest_sha256"] = manifest_digest
    progress = {"status": "running", "started_at": time.time(), "model": "gpt-6-astra", "phase": "calibration",
        "conditions": [dict(job, status="pending") for job in plan["jobs"]], "authoring_validation": str(args.validation),
        "totals": plan["totals"], "not_a_hardness_claim": True}
    def write():
        save(args.root / "progress.json", progress)
        lines = ["# p10 native hybrid calibration", "", "| Harness | Condition | State | A | B | Joint success |", "|---|---|---|---:|---:|---|"]
        for job in progress["conditions"]:
            scores = job.get("scores", {})
            lines.append(f"| {job['harness']} | {job['condition']} | {job['status']} | {scores.get('a', '—')} | {scores.get('b', '—')} | {job.get('joint_success', '—')} |")
        lines += ["", "One input variant; model variability and input generalization are not yet calibrated.",
                  "Solo conditions are not joint outcomes; agent/API/environment failure and task correctness remain separate."]
        (args.root / "REPORT.md").write_text("\n".join(lines) + "\n")
    write()
    for job in progress["conditions"]:
        result = subprocess.run([sys.executable, str(args.resource_gate), "--out", str(args.root), "--stage", job["id"]])
        if result.returncode:
            progress.update(status="resource_gate_failed", finished_at=time.time())
            write()
            return 1
        job.update(status="running", started_at=time.time())
        write()
        directory = args.root / job["id"]
        command = [sys.executable, "-u", "-m", "experiments.professional_v3", "--dataset", str(args.dataset),
            "--credentials", str(args.credentials), "--out", str(directory), "--harness", job["harness"],
            "--condition", job["condition"], "--freehand-runtime", str(args.freehand_runtime), "--codex-binary", str(args.codex_binary)]
        with (args.root / (job["id"] + ".log")).open("w") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        job.update(exit_code=result.returncode, finished_at=time.time(), status="finished" if result.returncode == 0 else "error")
        summary = directory / "summary.json"
        if summary.exists():
            agents = json.loads(summary.read_text())
            job["scores"] = {agent["task"][-1]: agent.get("score") for agent in agents}
            job["agent_statuses"] = [agent["status"] for agent in agents]
            job["joint_success"] = all(agent.get("evaluation", {}).get(agent["task"][-1], {}).get("success", False) for agent in agents) if len(agents) == 2 else None
        write()
        if result.returncode:
            progress.update(status="stopped_on_error", finished_at=time.time())
            write()
            return 1
    progress.update(status="finished", finished_at=time.time())
    write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

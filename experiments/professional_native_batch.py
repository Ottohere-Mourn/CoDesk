"""Durable six-condition pilot; failed conditions remain separate and unmodified."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from experiments.professional_trajectories import save
from experiments.professional_codex_entry import INTERACTION_MODES, PERMISSION_MODES, permissions
from experiments.professional_native import hybrid_smoke_passed
from experiments.responses_relay import image_history_policy


CONDITIONS = [("p3", "codex"), ("p3", "freehand"), ("p1", "freehand"),
              ("p1", "codex"), ("p2", "codex"), ("p2", "freehand")]


def write_report(root, progress):
    lines = ["# Professional software: native Codex / Freehand parallel pilot", "",
        f"{len(progress['conditions'])} selected conditions from three pairs × two harnesses. One shared desktop per condition; no sequential controls yet.",
        "Codex container-only permissions: " + json.dumps(progress["codex_permissions"]),
        "No host or VM Codex settings are changed. Interaction mode: " + progress["interaction_mode"],
        "Freehand: unmodified native loop and supervisor, isolated editable context.",
        "Outbound image-history policy: " + json.dumps(progress["image_history_policy"]),
        "Task access for both: shared desktop broker. Hybrid permits CLI/code; GUI-only is a labelled ablation.",
        "", "| Pair | Harness | State | A score | B score |", "|---|---|---|---:|---:|"]
    for condition in progress["conditions"]:
        scores = condition.get("scores", [None, None])
        lines.append(f"| {condition['pair']} | {condition['harness']} | {condition['status']} | {scores[0]} | {scores[1]} |")
    lines += ["", "Scores are six-check fractions, not success rates. Completion and scoring are separate.",
        "Reference/grader files and provider credentials are absent from agent containers.",
        "Original FreeCAD SVG and QGIS note-string grading limitations are unchanged."]
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")
    save(root / "progress.json", progress)


def validate_preflight(root, harness, mode, interaction_mode="gui-only", image_history_limit=None):
    if root is None or not json.loads((root / "validation.json").read_text())["passed"]:
        raise ValueError("A passing native screenshot preflight is required for " + harness)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("harness") != harness or not manifest.get("smoke"):
        raise ValueError("Preflight must be a screenshot smoke run of the selected harness")
    if manifest.get("interaction_mode", "gui-only") != interaction_mode:
        raise ValueError("Preflight interaction mode does not match the requested batch")
    if image_history_limit is not None and manifest.get("image_history_policy") != image_history_policy(image_history_limit):
        raise ValueError("Preflight image-history policy does not match the requested batch")
    if harness == "codex" and manifest.get("codex_permissions") != permissions(mode, interaction_mode):
        raise ValueError("Codex preflight permissions do not match the requested batch")
    if interaction_mode == "hybrid" and (len(manifest.get("tasks", [])) != 2 or not all(
            hybrid_smoke_passed(root / task) for task in manifest["tasks"])):
        raise ValueError("Hybrid preflight requires successful screenshot and target CLI calls from both agents")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "dataset", "credentials", "freehand-runtime", "codex-binary"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--codex-preflight", type=Path)
    parser.add_argument("--freehand-preflight", type=Path)
    parser.add_argument("--codex-permissions", choices=PERMISSION_MODES, default="reviewed")
    parser.add_argument("--interaction-mode", choices=INTERACTION_MODES, default="hybrid")
    parser.add_argument("--image-history-limit", type=int, default=4)
    parser.add_argument("--harnesses", nargs="+", choices=["codex", "freehand"], default=["codex", "freehand"])
    args = parser.parse_args(argv)
    if not 1 <= args.image_history_limit <= 50:
        parser.error("--image-history-limit must be between 1 and this provider's 50-image request budget")
    for harness in args.harnesses:
        root = getattr(args, harness + "_preflight")
        try:
            validate_preflight(root, harness, args.codex_permissions, args.interaction_mode, args.image_history_limit)
        except (ValueError, OSError) as error:
            parser.error(str(error))
    args.root.mkdir(parents=True, exist_ok=False)
    progress = {"status": "running", "started_at": time.time(), "interaction_mode": args.interaction_mode,
        "image_history_policy": image_history_policy(args.image_history_limit),
        "codex_permissions": permissions(args.codex_permissions, args.interaction_mode) if "codex" in args.harnesses else None,
        "conditions": [
        {"pair": pair, "harness": harness, "status": "pending"} for pair, harness in CONDITIONS if harness in args.harnesses]}
    write_report(args.root, progress)
    for condition in progress["conditions"]:
        name = condition["pair"] + "-" + condition["harness"] + "-parallel"
        condition.update(status="running", started_at=time.time(), directory=name)
        write_report(args.root, progress)
        command = [sys.executable, "-u", "-m", "experiments.professional_native",
            "--dataset", str(args.dataset), "--credentials", str(args.credentials),
            "--out", str(args.root / name), "--harness", condition["harness"],
            "--freehand-runtime", str(args.freehand_runtime), "--codex-binary", str(args.codex_binary),
            "--pair", condition["pair"], "--mode", "parallel", "--interaction-mode", args.interaction_mode,
            "--image-history-limit", str(args.image_history_limit),
            "--max-actions", "300", "--max-turns", "90", "--timeout", "1500"]
        if condition["harness"] == "codex":
            command += ["--codex-permissions", args.codex_permissions]
        with (args.root / (name + ".log")).open("wb") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        condition.update(exit_code=result.returncode, finished_at=time.time(),
            status="finished" if result.returncode == 0 else "error")
        summary = args.root / name / "summary.json"
        if summary.exists():
            agents = json.loads(summary.read_text())
            condition.update(scores=[agent.get("score") for agent in agents],
                agent_statuses=[agent["status"] for agent in agents])
        write_report(args.root, progress)
        if result.returncode:
            progress.update(status="stopped_on_error", finished_at=time.time())
            write_report(args.root, progress)
            return 1
    progress.update(status="finished", finished_at=time.time())
    write_report(args.root, progress)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

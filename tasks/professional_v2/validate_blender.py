"""Validate p4 references in a fresh Docker workspace, without calling any agent."""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image, ImageStat

if __package__:
    from .grade_blender import grade
else:
    from grade_blender import grade


SOURCE = Path(__file__).resolve().parent
NATIVE = "HingeStudio.blend"


def gui_pixels_ready(image):
    if image.width < 640 or image.height < 400:
        return False
    content = image.convert("RGB").crop((0, 60, image.width, image.height - 30))
    return max(ImageStat.Stat(content).stddev) > 8


def run_case(operation, workspace):
    report = workspace / f"{operation}.json"
    result = subprocess.run(["blender", "-b", "-t", "2", "--python", str(SOURCE / "blender_hinge.py"),
                             "--", operation, str(workspace), str(report)],
                            capture_output=True, text=True, timeout=180)
    (workspace / f"{operation}.log").write_text(result.stdout + result.stderr)
    if result.returncode or not report.exists():
        raise RuntimeError(f"{operation} failed in {workspace}: {(result.stdout + result.stderr)[-1500:]}")
    return json.loads(report.read_text())


def gui_reopen(workspace):
    environment = dict(os.environ, DISPLAY=":98")
    logs = []
    processes = []
    try:
        for name, argv in (
            ("xvfb", ["Xvfb", ":98", "-screen", "0", "1280x800x24", "-nolisten", "tcp"]),
            ("openbox", ["openbox"]),
            ("blender-gui", ["blender", "-t", "2", str(workspace / NATIVE)]),
        ):
            logfile = (workspace / f"{name}.log").open("w")
            logs.append(logfile)
            processes.append(subprocess.Popen(argv, stdout=logfile, stderr=logfile, env=environment))
            time.sleep(2)
        windows = []
        for attempt in range(20):
            probe = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "blender"],
                                   capture_output=True, text=True, env=environment)
            windows = probe.stdout.split()
            if windows:
                break
            if processes[-1].poll() is not None:
                raise RuntimeError("Blender GUI exited before showing a window")
            time.sleep(1)
        if not windows:
            raise RuntimeError("No visible Blender window")
        subprocess.run(["xdotool", "windowactivate", "--sync", windows[-1]], check=True, env=environment, timeout=15)
        subprocess.run(["xdotool", "key", "alt+F10"], check=True, env=environment, timeout=15)
        consecutive_ready = 0
        for attempt in range(45):
            if processes[-1].poll() is not None:
                raise RuntimeError("Blender GUI exited during readiness check")
            screenshot = workspace / "gui-reopen.png"
            subprocess.run(["scrot", "--overwrite", str(screenshot)], check=True, env=environment, timeout=15)
            with Image.open(screenshot) as image:
                consecutive_ready = consecutive_ready + 1 if gui_pixels_ready(image) else 0
            if consecutive_ready >= 2:
                return {"visible_window": True, "nonblank_content": True,
                        "readiness_samples": attempt + 1, "screenshot": "gui-reopen.png", "agent_actions": 0}
            time.sleep(1)
        raise RuntimeError("Blender window remained blank; do not treat window existence as GUI readiness")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for logfile in logs:
            logfile.close()


def validate(root, gui):
    root.mkdir(parents=True, exist_ok=False)
    initial = root / "input"
    initial.mkdir()
    run_case("build", initial)
    baseline = run_case("inspect", initial)
    states = {"initial": baseline}
    reports = {"initial": grade(baseline, baseline)}
    for label, sequence in (("a", ("ref-a",)), ("b", ("ref-b",)),
                            ("ab", ("ref-a", "ref-b")), ("ba", ("ref-b", "ref-a"))):
        workspace = root / label
        workspace.mkdir()
        shutil.copy2(initial / NATIVE, workspace / NATIVE)
        for operation in sequence:
            run_case(operation, workspace)
        states[label] = run_case("inspect", workspace)
        reports[label] = grade(states[label], baseline)
    conditions = {
        "initial_not_solved": all(role["score"] < 1 for role in reports["initial"]["roles"].values()),
        "a_only_passes_a": reports["a"]["roles"]["a"]["score"] == 1,
        "b_only_passes_b": reports["b"]["roles"]["b"]["score"] == 1,
        "a_preserves_b_inputs": states["a"]["materials"] == baseline["materials"],
        "b_preserves_a_inputs": states["b"]["motion"] == baseline["motion"],
        "both_orders_pass_both": all(reports[label]["roles"][role]["score"] == 1
                                      for label in ("ab", "ba") for role in ("a", "b")),
        "semantic_order_equivalence": states["ab"] == states["ba"],
        "all_preservation_gates": all(report["gate_passed"] for report in reports.values()),
    }
    negative = copy.deepcopy(states["ab"])
    negative["materials"]["ShellFinish"]["values"]["Base Color"] = [1, 0, 0, 1]
    conditions["wrong_color_rejected"] = not grade(negative, baseline)["roles"]["b"]["checks"]["shell_color"]
    negative = copy.deepcopy(states["ab"])
    negative["motion"]["curves"] = []
    conditions["missing_editable_keys_rejected"] = not grade(negative, baseline)["roles"]["a"]["checks"]["editable_rotation_keys"]
    negative = copy.deepcopy(states["ab"])
    negative["invariants"]["objects"].pop("CaseBase")
    conditions["deleted_asset_gates_scores"] = all(role["score"] == 0 for role in grade(negative, baseline)["roles"].values())
    for label in ("input", "ab"):
        run_case("render", root / label)
    gui_results = {label: gui_reopen(root / label) for label in ("input", "ab")} if gui else {}
    if gui:
        conditions["gui_windows_nonblank"] = all(result["nonblank_content"] for result in gui_results.values())
    manifest = {
        "dataset": "paraGUI-professional-v2-p4", "time_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "scripted_native_reference_validation", "agent_trajectories": 0,
        "harness_registered": False, "blender_version": baseline["blender_version"],
        "conditions": conditions, "passed": all(conditions.values()), "scores": reports,
        "gui_reopen": gui_results,
        "limitations": ["Not a GUI agent rollout", "GUI smoke does not establish solo-agent solvability",
                        "Structured grader is not an exhaustive adversarial validator", "No shared-desktop concurrency pilot yet"],
        "hashes": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in sorted(root.rglob("*")) if path.is_file()},
        "source_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(SOURCE.glob("*.py"))},
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if not manifest["passed"]:
        raise RuntimeError(f"Reference validation failed: {conditions}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if not Path("/.dockerenv").exists():
        parser.error("Run validation only inside the professional Docker image")
    manifest = validate(args.output, args.gui)
    print(json.dumps({"passed": manifest["passed"], "conditions": manifest["conditions"]}, indent=2))


if __name__ == "__main__":
    main()

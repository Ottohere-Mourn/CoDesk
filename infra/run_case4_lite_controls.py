"""Scripted real-Guest positive/negative controls for Case 4 Lite v1.0.0.

All project and manifest edits are PyAutoGUI actions in Kdenlive and VS Code.
The host only copies saved Guest files for scoring and fresh-Guest reopen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
import traceback

from oscombo.collab.data_to_deck.protocol import ProtocolStore
from oscombo.collab.timeline_and_assets_lite_v1 import spec
from oscombo.collab.timeline_and_assets_lite_v1.oracle import project_state
from oscombo.collab.timeline_and_assets_lite_v1.runner import (
    configure_run, evaluate_run, prepare_run, reset_owned_run,
)

from .run_case3_lite_pair_pilot import boot_guest
from .run_case3_lite_single_pilot import guest_shell
from .run_case4_lite_pair_pilot import open_kdenlive, open_manifest_editor, record


def gui_action(env, root: Path, role: str, label: str, code: str, settle: float = 2) -> None:
    before = guest_shell(env, "xdotool getactivewindow getwindowname; true", 15).strip()
    response = env.controller.execute_python_command("import pyautogui, time; " + code)
    time.sleep(settle)
    after = guest_shell(env, "xdotool getactivewindow getwindowname; true", 15).strip()
    number = sum(1 for line in (root / "control_actions.jsonl").read_text().splitlines()
                 if line.strip()) + 1 if (root / "control_actions.jsonl").exists() else 1
    shot = root / "screenshots" / f"control-{number:02d}-{role}-{label}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(env.controller.get_screenshot())
    record(root, "control_actions.jsonl", {
        "n": number, "role": role, "label": label, "code": code,
        "window_before": before, "window_after": after,
        "response": str(response)[:250], "screenshot": str(shot), "time": time.time(),
    })


def edit_project(env, root: Path) -> None:
    guest_shell(env, "wmctrl -a 'GreenLoop.kdenlive'; true", 15)
    time.sleep(20)
    gui_action(env, root, "B", "select-outtake", "pyautogui.click(294, 674)")
    gui_action(env, root, "B", "delete-outtake", "pyautogui.press('delete')", 3)
    gui_action(env, root, "B", "move-wash", 
               "pyautogui.moveTo(380, 594); pyautogui.dragTo(296, 675, duration=0.6)", 4)
    gui_action(env, root, "B", "save-project", "pyautogui.hotkey('ctrl', 's')", 5)


def edit_manifest(env, root: Path, middle_source: str) -> None:
    for attempt in range(1, 5):
        active = guest_shell(env, "for id in $(xdotool search --name 'shot_manifest.txt' "
                             "2>/dev/null); do xdotool windowmap $id; "
                             "xdotool windowactivate --sync $id; break; done; sleep 2; "
                             "xdotool getactivewindow getwindowname; true", 20)
        record(root, "control_focus.jsonl", {"attempt": attempt, "active": active,
                                               "time": time.time()})
        if "shot_manifest.txt" in active:
            break
        if "Welcome - Visual Studio Code" in active:
            gui_action(env, root, "A", f"select-manifest-tab-{attempt}",
                       "pyautogui.click(691, 261)", 2)
        else:
            gui_action(env, root, "A", f"restore-editor-{attempt}",
                       "pyautogui.click(35, 200)", 3)
    else:
        raise RuntimeError(f"manifest editor focus failed: {active[:200]}")
    gui_action(env, root, "A", "manifest-focus", "pyautogui.click(831, 310)")
    gui_action(env, root, "A", "manifest-first-line", 
               "pyautogui.hotkey('ctrl', 'home'); pyautogui.hotkey('shift', 'end'); "
               f"pyautogui.write('middle_source={middle_source}', interval=0.02)")
    gui_action(env, root, "A", "save-manifest", "pyautogui.hotkey('ctrl', 's')", 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=spec.CONDITIONS, required=True)
    parser.add_argument("--scenario", choices=("positive", "wrong-manifest"), required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    run_id = root.name
    prepare_run(root, run_id)
    configure_run(root, args.condition)
    os.environ["SWCUB_OWNER_TOKEN"] = secrets.token_hex(32)
    sys.path.insert(0, str(args.provider))
    sys.path.insert(0, "/home/mjh/Projects/Shared-Workspace-Benchmark-V0")
    os.chdir(args.provider)
    result = {"run_id": run_id, "condition": args.condition,
              "scenario": args.scenario, "case_version": spec.CASE_VERSION,
              "image": str(args.image), "runtime": args.runtime,
              "status": "STARTED", "started_epoch": time.time()}
    envs = {}
    try:
        envs["A"] = boot_guest(root, args.overlay_root, run_id, "A",
                              args.image, args.runtime, args.provider)
        open_kdenlive(envs["A"], root, "A")
        envs["B"] = (boot_guest(root, args.overlay_root, run_id, "B",
                               args.image, args.runtime, args.provider)
                     if args.condition == "collaborative_isolated" else envs["A"])
        if args.condition == "collaborative_isolated":
            open_kdenlive(envs["B"], root, "B")
        open_manifest_editor(envs["A"], root, run_id)
        result["initial_project_sha256"] = hashlib.sha256(
            envs["B"].controller.get_file(f"{spec.GUEST_ROOT}/{spec.PROJECT}")).hexdigest()
        result["initial_manifest_sha256"] = hashlib.sha256(
            envs["A"].controller.get_file(f"{spec.GUEST_ROOT}/shot_manifest.txt")).hexdigest()

        store = ProtocolStore(root / "collaboration", run_id)
        store.send("A", "B", "Use clip_02.mp4 instead of clip_04.mp4 at frames 75-174 (3-7 seconds).", [])
        edit_project(envs["B"], root)
        b_project = envs["B"].controller.get_file(f"{spec.GUEST_ROOT}/{spec.PROJECT}")
        if not b_project:
            raise RuntimeError("B project was unreadable after GUI save")
        (root / "B_saved_project.kdenlive").write_bytes(b_project)
        result["B_saved_project_state"] = project_state(root / "B_saved_project.kdenlive")
        edit_manifest(envs["A"], root,
                      "clip_02.mp4" if args.scenario == "positive" else "clip_04.mp4")
        project = envs["B"].controller.get_file(f"{spec.GUEST_ROOT}/{spec.PROJECT}")
        manifest = envs["A"].controller.get_file(f"{spec.GUEST_ROOT}/shot_manifest.txt")
        if not project or not manifest:
            raise RuntimeError("GUI control did not leave readable saved Guest artifacts")
        (root / "workspace" / spec.PROJECT).write_bytes(project)
        (root / "workspace/shot_manifest.txt").write_bytes(manifest)
        result["saved_project_sha256"] = hashlib.sha256(project).hexdigest()
        result["saved_manifest_sha256"] = hashlib.sha256(manifest).hexdigest()
        result["saved_project_state"] = project_state(root / "workspace" / spec.PROJECT)
        result["oracle"] = evaluate_run(root)
        checks = result["oracle"]["checks"]
        result["business_control_pass"] = (
            all(checks.values()) if args.scenario == "positive"
            else not checks["asset_manifest_saved"] and all(
                value for name, value in checks.items() if name != "asset_manifest_saved"))

        for env in {id(env): env for env in envs.values()}.values():
            env.close()
        envs.clear()
        envs["reopen"] = boot_guest(root, args.overlay_root, run_id, "reopen",
                                   args.image, args.runtime, args.provider)
        open_kdenlive(envs["reopen"], root, "reopen")
        open_manifest_editor(envs["reopen"], root, run_id)
        reopened = envs["reopen"].controller.get_file(f"{spec.GUEST_ROOT}/{spec.PROJECT}")
        reopened_manifest = envs["reopen"].controller.get_file(
            f"{spec.GUEST_ROOT}/shot_manifest.txt")
        (root / "guest_reopened_project.kdenlive").write_bytes(reopened)
        (root / "guest_reopen_initial.png").write_bytes(
            envs["reopen"].controller.get_screenshot())
        result["fresh_guest_reopen"] = {
            "saved_project_bytes_match": reopened == project,
            "saved_manifest_bytes_match": reopened_manifest == manifest,
            "native_project_parseable": project_state(root / "guest_reopened_project.kdenlive")
                                         == result["saved_project_state"],
            "screenshot": str(root / "guest_reopen_initial.png"),
        }
        result["reopen_verified"] = all(
            value for key, value in result["fresh_guest_reopen"].items()
            if key != "screenshot")
        envs["reopen"].close()
        envs.clear()
        result["reset"] = reset_owned_run(root)
        result["status"] = ("CONTROL_PASS" if result["business_control_pass"]
                            and result["reopen_verified"]
                            and result["reset"]["status"] == "RESET_VERIFIED"
                            else "CONTROL_FAIL")
    except Exception as exc:
        result.update({"status": "INFRA_OR_CONTROL_ERROR",
                       "error_type": type(exc).__name__, "error": str(exc)[:1000],
                       "traceback": traceback.format_exc()[-4000:]})
    finally:
        for env in {id(env): env for env in envs.values()}.values():
            try:
                env.close()
            except Exception as exc:
                result.setdefault("cleanup_errors", []).append(
                    f"{type(exc).__name__}: {str(exc)[:200]}")
        if result.get("oracle") is not None and result.get("reset") is None:
            try:
                result["reset"] = reset_owned_run(root)
            except Exception as exc:
                result["reset_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        result["finished_epoch"] = time.time()
        (root / "control_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({key: result.get(key) for key in
                          ("run_id", "scenario", "status", "business_control_pass",
                           "reopen_verified", "error_type")}), flush=True)


if __name__ == "__main__":
    main()

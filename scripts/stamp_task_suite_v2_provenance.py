#!/usr/bin/env python3
"""Stamp all completed V2 task-suite reports with a shared provenance schema."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swcub.provenance import TASK_VERSION, stamp_episode_provenance


DEFAULT_MANIFEST = ROOT / "tasks/task_suite_v2.json"
DEFAULT_RUN_ROOT = Path("/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2")
OSWORLD_CHECKOUT = Path(os.environ.get("OSWORLD_V2_DIR", ROOT.parent / "_deps/OSWorld-V2-osworld-v2.1"))
GUEST_IMAGE = Path(os.environ.get(
    "SWCUB_OSWORLD_GUEST_IMAGE",
    "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"))
RELEASE_MANIFEST = ROOT / "outputs/osworld-v2.1/environment/release_manifest.json"


def _source_files(task_id: str) -> list[Path]:
    base = [ROOT / "swcub/actors.py", ROOT / "swcub/evaluator.py",
            ROOT / "swcub/orchestrator.py", ROOT / "swcub/osworld_adapter.py",
            ROOT / "swcub/core.py", ROOT / "swcub/provenance.py",
            ROOT / "tasks/task_suite_v2.json",
            ROOT / "scripts/stamp_task_suite_v2_provenance.py"]
    if task_id == "SWCUB-FOCUS-ROUTING-001":
        return base + [ROOT / "scripts/run_osworld_v2_1_shared_csv.py"]
    return base + [ROOT / "swcub/osworld_agent_actor.py",
                   ROOT / "swcub/tasks/web_workspace.py",
                   ROOT / "tasks/instances/browser_gui_cli.json",
                   ROOT / "scripts/run_osworld_v2_1_browser.py"]


def _actor_metadata(task_id: str, actor_ids: set[str]) -> dict[str, dict[str, str]]:
    classes = {
        "SWCUB-FOCUS-ROUTING-001": {
            "gui_actor": ("ScriptedGuestFocusGUIActor", "gui"),
            "human_replay": ("ScriptedGuestHumanReplayActor", "human_replay"),
        },
        "SWCUB-STALE-MERGE-001": {
            "gui_actor": ("ScriptedWebCacheGUIActor", "gui"),
            "cli_actor": ("ScriptedGuestCLIActor", "cli"),
        },
    }[task_id]
    return {actor_id: {"class": classes[actor_id][0], "role": classes[actor_id][1]}
            for actor_id in actor_ids}


def stamp_suite(manifest_path: Path, run_root: Path) -> list[Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    written: list[Path] = []
    for task in manifest["tasks"]:
        task_id = task["task_id"]
        if task.get("task_version") != TASK_VERSION:
            raise ValueError(f"{task_id}: task_version must be {TASK_VERSION}")
        for episode in task["episodes"]:
            declared = episode.get("artifact_dir")
            out = (ROOT / declared).resolve() if declared else (run_root / episode["episode_id"]).resolve()
            if not out.is_dir():
                raise FileNotFoundError(f"episode directory does not exist: {out}")
            report_path = out / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("scenario") != episode["scenario"]:
                raise ValueError(f"{episode['episode_id']}: report scenario mismatch")
            if not (out / "resource-events.jsonl").is_file():
                raise ValueError(f"{episode['episode_id']}: missing ownership ledger")
            stamp_episode_provenance(
                out, report, repo_root=ROOT, task_id=task_id,
                task_version=TASK_VERSION, condition=episode["condition"],
                seed=0, actor_metadata=_actor_metadata(task_id, set(report["actors"])),
                evaluator_class=task["evaluator"], source_files=_source_files(task_id),
                osworld_checkout=OSWORLD_CHECKOUT,
                release_manifest=RELEASE_MANIFEST, guest_image=GUEST_IMAGE)
            written.append(report_path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    args = parser.parse_args()
    paths = stamp_suite(args.manifest, args.run_root)
    print(json.dumps({"stamped_reports": len(paths), "reports": list(map(str, paths))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

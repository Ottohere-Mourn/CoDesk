"""Integrity tests verifying that this branch tracks ONLY the 23 selected cases, strict 1.0 grading, clean imports, and 184 trajectories."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import re
import subprocess

from tasks.curated_23cases_v1.registry import (
    SELECTED_23_CATALOG,
    SELECTED_23_IDS,
    SELECTED_23_MODULES,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_exact_23_selected_cases_and_zero_unselected_task_files() -> None:
    assert len(SELECTED_23_IDS) == 23
    assert len(SELECTED_23_CATALOG) == 23
    assert len(SELECTED_23_MODULES) == 23

    manifest = json.loads((REPO_ROOT / "lists/curated_23cases_and_trajectories_20261125.json").read_text(encoding="utf-8"))
    expected_source_files = {c["source_file"] for c in manifest["cases"]}
    assert len(expected_source_files) == 23

    cp = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "tasks"], capture_output=True, text=True, check=True)
    tracked_case_files = {
        rel
        for rel in cp.stdout.splitlines()
        if rel.endswith(".py") and Path(rel).name not in ("__init__.py", "common.py", "registry.py", "xlsx_utils.py")
    }
    assert tracked_case_files == expected_source_files


def test_strict_zero_error_pass_standard() -> None:
    cp = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "tasks"], capture_output=True, text=True, check=True)
    for rel in cp.stdout.splitlines():
        if not rel.endswith(".py"):
            continue
        py_f = REPO_ROOT / rel
        no_comm = chr(10).join(ln for ln in py_f.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))
        for m in re.finditer(r"pass_threshold\s*(?::\s*float\s*)?=\s*(0\.\d+)", no_comm):
            assert float(m.group(1)) >= 0.999, f"{py_f} still has lax pass_threshold={m.group(1)}"

    troot = REPO_ROOT / "trajectories/curated_23cases_20261125"
    for tid in SELECTED_23_IDS:
        for ep in (troot / tid).iterdir():
            if not ep.is_dir():
                continue
            rep = json.loads((ep / "report.json").read_text(encoding="utf-8"))
            g = rep.get("grade") or rep
            zero_err = (len(g.get("errors_a") or []) == 0 and len(g.get("errors_b") or []) == 0 and len(g.get("errors_joint") or []) == 0)
            if rep["joint_pass"]:
                assert zero_err, f"{tid}/{ep.name} marked joint_pass=True despite errors"
                assert abs(float(rep["mean_score"]) - 1.0) < 1e-6, f"{tid}/{ep.name} joint_pass=True with mean_score={rep['mean_score']}"
            else:
                assert (not zero_err) or float(rep["mean_score"]) < 0.9999


def test_all_runners_import_cleanly_without_legacy_packages() -> None:
    for runner_mod in (
        "experiments.curated_8cases_v1",
        "experiments.authentic_workstation_v1",
        "experiments.novel_frontier_v1",
        "experiments.novel_frontier_v2",
    ):
        mod = importlib.import_module(runner_mod)
        assert mod is not None


def test_all_92_episodes_and_184_actor_trajectories_present() -> None:
    troot = REPO_ROOT / "trajectories/curated_23cases_20261125"
    case_dirs = {d.name for d in troot.iterdir() if d.is_dir()}
    assert case_dirs == set(SELECTED_23_IDS)
    episodes = 0
    actors = 0
    for tid in SELECTED_23_IDS:
        eps = [d for d in (troot / tid).iterdir() if d.is_dir()]
        assert len(eps) == 4, f"{tid} has {len(eps)} episodes"
        episodes += len(eps)
        for ep in eps:
            acts = [d for d in ep.iterdir() if d.is_dir() and d.name.startswith("actor_")]
            assert len(acts) == 2, f"{tid}/{ep.name} has {len(acts)} actors"
            actors += len(acts)
            for ad in acts:
                assert (ad / "actions.jsonl").stat().st_size > 10
                assert (ad / "codex_events.jsonl").stat().st_size > 10
    assert episodes == 92
    assert actors == 184

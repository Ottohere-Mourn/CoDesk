"""Task catalog contract checks; these do not execute desktop scenarios."""
from __future__ import annotations
import copy
import json
from pathlib import Path

import pytest

from swcub.task_manifest import TaskManifestError, validate_task_manifest


ROOT = Path(__file__).resolve().parents[1]


def load_manifest():
    return json.loads((ROOT / "tasks" / "v0_manifest.json").read_text(encoding="utf-8"))


def test_v0_manifest_lists_both_real_scenarios_and_controls():
    assert validate_task_manifest(load_manifest()) == {"tasks": 2, "interactions": 4}


def test_manifest_rejects_missing_independent_actor_goal():
    manifest = copy.deepcopy(load_manifest())
    del manifest["tasks"][0]["independent_solutions"]["cli"]

    with pytest.raises(TaskManifestError, match="one goal per actor role"):
        validate_task_manifest(manifest)


def test_manifest_rejects_non_deterministic_or_ungraded_interaction():
    manifest = copy.deepcopy(load_manifest())
    del manifest["tasks"][1]["interactions"][0]["deterministic"]
    del manifest["tasks"][1]["interactions"][1]["final_state"]

    with pytest.raises(TaskManifestError, match="deterministic=true"):
        validate_task_manifest(manifest)


def test_manifest_reports_invalid_actor_id_values_without_crashing():
    manifest = copy.deepcopy(load_manifest())
    manifest["tasks"][0]["actor_ids"]["gui"] = ["gui_actor"]

    with pytest.raises(TaskManifestError, match="actor_ids values"):
        validate_task_manifest(manifest)

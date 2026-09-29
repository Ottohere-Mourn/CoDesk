import hashlib
import json
from pathlib import Path

import pytest

from scripts.run_codesk_experiment import verify_episode
from swcub.runner.config import validate_config


BASE = {
    "schema_version": 1,
    "experiment_id": "track-a-runner-test",
    "task_family": "track_a_v1",
    "task_version": "1.0.0",
    "episodes": [
        {"condition": "solo_document", "repeat": 1},
        {"condition": "solo_chat", "repeat": 1},
        {"condition": "ma_id", "repeat": 1},
        {"condition": "ma_sd", "repeat": 1},
    ],
    "max_workers": 2,
    "max_concurrent_guests": 4,
    "startup_stagger_seconds": 15,
    "artifact_root": "/tmp/codesk-test-artifacts",
}


def test_v1_config_accepts_solo_and_shared_conditions():
    validate_config(BASE)


def test_v1_config_rejects_duplicate_episodes():
    config = {**BASE, "episodes": [
        {"condition": "ma_sd", "repeat": 1},
        {"condition": "ma_sd", "repeat": 1},
    ]}
    with pytest.raises(ValueError, match="duplicate episode"):
        validate_config(config)


def test_v1_config_requires_two_guest_slots_for_ma_id():
    config = {**BASE, "max_concurrent_guests": 1}
    with pytest.raises(ValueError, match="MA-ID episodes require"):
        validate_config(config)


def test_v1_config_rejects_unpinned_task_version():
    config = {**BASE, "task_version": "1.1.0"}
    with pytest.raises(ValueError, match="frozen task_version"):
        validate_config(config)


def test_writer_calc_v1_config_accepts_all_three_conditions():
    config = {**BASE, "task": "writer_calc_v1", "task_family": "writer_calc_v1",
              "episodes": [{"condition": condition, "repeat": 1}
                           for condition in ("solo", "ma_id", "ma_sd")]}
    validate_config(config)


def test_writer_calc_v1_paired_solo_requires_two_guest_slots():
    config = {**BASE, "task": "writer_calc_v1", "task_family": "writer_calc_v1",
              "episodes": [{"condition": "solo", "repeat": 1}],
              "max_workers": 1, "max_concurrent_guests": 1}
    with pytest.raises(ValueError, match="paired solo"):
        validate_config(config)


def test_setup_readiness_failure_is_preserved_but_excluded_from_scenario_denominator(tmp_path):
    spec = {"job_id": "0001-solo-r01", "run_id": "setup-invalid-run",
            "condition": "solo", "repeat": 1,
            "task_id": "CODESK-TA-OFFICE-001", "task_version": "1.0.0",
            "task_family": "writer_calc_v1",
            "artifact_parent": str(tmp_path / "episodes" / "0001-solo-r01")}
    run_dir = Path(spec["artifact_parent"]) / spec["run_id"]
    run_dir.mkdir(parents=True)
    files = {
        "error.json": {"task_id": spec["task_id"], "task_version": spec["task_version"],
                       "condition": "solo", "repeat": 1, "model": None,
                       "episode_status": "readiness_failed", "failure_stage": "application_setup",
                       "error": "Writer document title was not ready"},
        "events.jsonl": "{}\n",
        "resource-events.jsonl": "{}\n",
        "run-owner-marker.json": json.dumps({"run_id": spec["run_id"]}),
    }
    for name, value in files.items():
        content = value if isinstance(value, str) else json.dumps(value)
        (run_dir / name).write_text(content, encoding="utf-8")
    artifact_hashes = {name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
                       for name in files}
    provenance = {"task": {"task_id": spec["task_id"],
                           "task_version": spec["task_version"]},
                  "model": None, "artifact_sha256": artifact_hashes}
    (run_dir / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    error = json.loads((run_dir / "error.json").read_text())
    error["resource_lifecycle"] = {"labels_consistent": True,
                                   "all_containers_have_destroy_record": True}
    # The lifecycle field is part of the hashed error evidence, so update both
    # error.json and its provenance digest together before running verification.
    (run_dir / "error.json").write_text(json.dumps(error), encoding="utf-8")
    provenance["artifact_sha256"]["error.json"] = hashlib.sha256(
        (run_dir / "error.json").read_bytes()).hexdigest()
    (run_dir / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")

    result = verify_episode(spec, {"exit_code": 2})
    assert result["episode_status"] == "readiness_failed"
    assert result["scenario_success"] is None
    assert result["reset_success"] is None
    assert result["artifact_integrity"] is True

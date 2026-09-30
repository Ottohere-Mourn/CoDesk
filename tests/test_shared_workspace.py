from pathlib import Path

import pytest

from swcub.shared_workspace import (
    ActorSession,
    WorkspaceTopologyError,
    guest_mount_command,
    qemu_virtfs_device,
    validate_condition_topology,
    write_backend_marker,
)


def sessions(a_backend="backend-0001", b_backend="backend-0001",
             a_desktop="desktop-a", b_desktop="desktop-b"):
    return {
        "writer_actor": ActorSession("writer_actor", a_backend, a_desktop),
        "calc_actor": ActorSession("calc_actor", b_backend, b_desktop),
    }


def test_ma_id_requires_same_backend_and_distinct_desktops():
    result = validate_condition_topology("ma_id", sessions())
    assert result["same_authoritative_backend"] is True
    assert result["same_desktop_session"] is False


def test_ma_sd_requires_same_backend_and_same_desktop():
    result = validate_condition_topology(
        "ma_sd", sessions(a_desktop="desktop-shared", b_desktop="desktop-shared"))
    assert result["same_authoritative_backend"] is True
    assert result["same_desktop_session"] is True


@pytest.mark.parametrize("condition, values", [
    ("ma_id", {"a_desktop": "same", "b_desktop": "same"}),
    ("ma_sd", {"a_desktop": "one", "b_desktop": "two"}),
    ("ma_id", {"a_backend": "backend-a", "b_backend": "backend-b"}),
])
def test_topology_rejects_mismatched_backend_or_desktop(condition, values):
    with pytest.raises(WorkspaceTopologyError):
        validate_condition_topology(condition, sessions(**values))


def test_qemu_and_guest_mount_args_are_deterministic():
    assert qemu_virtfs_device() == [
        "-virtfs",
        "local,path=/codesk-workspace,mount_tag=codesk_workspace,"
        "security_model=none,id=codesk_workspace",
    ]
    command = guest_mount_command()
    assert "mount -t 9p" in command
    assert "version=9p2000.L" in command
    assert "codesk_workspace /tmp/swcub_office" in command


def test_backend_marker_requires_fresh_path_and_records_run_ownership(tmp_path: Path):
    root = tmp_path / "backend"
    marker = write_backend_marker(root, backend_id="backend-0001",
                                  run_id="run-0000001", condition="ma_id")
    assert marker.is_file()
    assert marker.parent == tmp_path  # ownership metadata stays outside the Guest export
    assert marker.parent == tmp_path  # ownership metadata stays outside the Guest export
    assert '"generation": "task"' in marker.read_text()
    with pytest.raises(FileExistsError):
        write_backend_marker(root, backend_id="backend-0001",
                            run_id="run-0000001", condition="ma_id")


def test_runner_config_accepts_same_workspace_only_for_office_family(tmp_path):
    from swcub.runner.config import validate_config
    config = {
        "schema_version": 1,
        "experiment_id": "a6000-wc-maid",
        "task": "writer_calc_v1",
        "task_family": "writer_calc_v1",
        "task_version": "1.0.0",
        "backend_topology": "same_workspace",
        "episodes": [{"condition": "ma_id", "repeat": 1}],
        "max_workers": 1,
        "max_concurrent_guests": 2,
        "artifact_root": str(tmp_path),
    }
    validate_config(config)
    config["task"] = config["task_family"] = "track_a_v1"
    with pytest.raises(ValueError, match="only for writer_calc_v1"):
        validate_config(config)


def test_runner_config_accepts_same_workspace_only_for_office_family(tmp_path):
    from swcub.runner.config import validate_config
    config = {
        "schema_version": 1,
        "experiment_id": "a6000-wc-maid",
        "task": "writer_calc_v1",
        "task_family": "writer_calc_v1",
        "task_version": "1.0.0",
        "backend_topology": "same_workspace",
        "episodes": [{"condition": "ma_id", "repeat": 1}],
        "max_workers": 1,
        "max_concurrent_guests": 2,
        "artifact_root": str(tmp_path),
    }
    validate_config(config)
    config["task"] = config["task_family"] = "track_a_v1"
    with pytest.raises(ValueError, match="only for writer_calc_v1"):
        validate_config(config)

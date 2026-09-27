from __future__ import annotations

import json
import subprocess

import pytest

from scripts.cleanup_owned_resources import clean_one
from swcub.resource_safety import (
    OWNER_LABEL, PROJECT_LABEL, PROJECT_NAME, RUN_LABEL, ResourceIdentity,
    ResourceLedger, cleanup_docker_cli_container, remove_verified_image,
    verify_container_identity,
    verify_owned_directory,
)


FULL_ID = "a" * 64
FULL_IMAGE_ID = "sha256:" + "d" * 64


def make_identity(tmp_path):
    return ResourceIdentity("experiment-run-0001", "b" * 64,
                            tmp_path / "resource-events.jsonl")


def inspected(identity, *, container_id=FULL_ID, status="exited", labels=None):
    return {"Id": container_id,
            "Config": {"Labels": labels or identity.labels},
            "State": {"Status": status, "Running": status == "running"}}


def ledger_container(identity, container_id=FULL_ID):
    ledger = ResourceLedger(identity.ledger_path)
    ledger.record("run_started", "run", identity.run_id, identity)
    ledger.created_container(
        container_id, identity, name="swcub-episode-1", image="swcub-v0:run")


def test_identity_refuses_partial_environment_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("SWCUB_RUN_ID", "provided-run-0001")
    monkeypatch.delenv("SWCUB_OWNER_TOKEN", raising=False)
    monkeypatch.delenv("SWCUB_RESOURCE_LEDGER", raising=False)
    from swcub.resource_safety import ensure_resource_identity
    with pytest.raises(RuntimeError, match="must be set together"):
        ensure_resource_identity(tmp_path / "ledger.jsonl")


@pytest.mark.parametrize("bad", ["a" * 12, "container-name", "b" * 64])
def test_verify_requires_full_matching_id(tmp_path, bad):
    identity = make_identity(tmp_path)
    with pytest.raises(RuntimeError):
        verify_container_identity(bad, inspected(identity), identity)


@pytest.mark.parametrize("label,value", [
    (PROJECT_LABEL, "another-project"),
    (RUN_LABEL, "another-run-0001"),
    (OWNER_LABEL, "c" * 64),
])
def test_verify_refuses_each_ownership_label_mismatch(tmp_path, label, value):
    identity = make_identity(tmp_path)
    labels = identity.labels | {label: value}
    with pytest.raises(RuntimeError, match="ownership label mismatch"):
        verify_container_identity(FULL_ID, inspected(identity, labels=labels), identity)


def test_cleanup_cli_dry_run_is_read_only_and_apply_removes_only_exact_id(tmp_path):
    identity = make_identity(tmp_path)
    ledger_container(identity)
    state = {"status": "running"}
    calls = []

    def inspect_fn(container_id):
        assert container_id == FULL_ID
        return inspected(identity, status=state["status"])

    def runner(args, **kwargs):
        calls.append(args)
        if args[1] == "stop":
            state["status"] = "exited"
        return subprocess.CompletedProcess(args, 0, "", "")

    dry = clean_one(identity.ledger_path, FULL_ID, apply=False,
                    runner=runner, inspect_fn=inspect_fn)
    assert "dry run only" in dry
    assert calls == []

    result = clean_one(identity.ledger_path, FULL_ID, apply=True,
                       runner=runner, inspect_fn=inspect_fn)
    assert "removed verified" in result
    assert calls == [["docker", "stop", "--time", "10", FULL_ID],
                     ["docker", "rm", FULL_ID]]
    rows = [json.loads(line) for line in identity.ledger_path.read_text().splitlines()]
    assert [row["event"] for row in rows] == ["run_started", "created", "destroy_requested", "destroyed"]
    assert all(row["labels"] == identity.labels for row in rows)


def test_cleanup_refuses_unledgered_container_without_running_docker(tmp_path):
    identity = make_identity(tmp_path)
    called = []
    with pytest.raises(RuntimeError, match="ledger record"):
        clean_one(identity.ledger_path, FULL_ID, apply=True,
                  runner=lambda *args, **kwargs: called.append(args),
                  inspect_fn=lambda _container_id: inspected(identity))
    assert called == []


def test_cleanup_refuses_created_row_without_matching_run_start(tmp_path):
    identity = make_identity(tmp_path)
    ResourceLedger(identity.ledger_path).created_container(
        FULL_ID, identity, name="owned", image="swcub:local")
    with pytest.raises(RuntimeError, match="current-run start"):
        clean_one(identity.ledger_path, FULL_ID, apply=False,
                  inspect_fn=lambda _container_id: inspected(identity))


def test_cleanup_refuses_same_id_with_other_project_label(tmp_path):
    identity = make_identity(tmp_path)
    ledger_container(identity)
    called = []
    foreign = identity.labels | {PROJECT_LABEL: "someone-elses-project"}
    with pytest.raises(RuntimeError, match="ownership label mismatch"):
        clean_one(identity.ledger_path, FULL_ID, apply=True,
                  runner=lambda *args, **kwargs: called.append(args),
                  inspect_fn=lambda _container_id: inspected(identity, labels=foreign))
    assert called == []


def test_direct_adapter_cleanup_verifies_ledger_before_stopping(tmp_path):
    identity = make_identity(tmp_path)
    calls = []

    class FakeContainer:
        id = FULL_ID
        name = "swcub-owned"
        attrs = inspected(identity, status="running")

        def reload(self):
            calls.append("reload")

        def stop(self, timeout):
            calls.append(("stop", timeout))
            self.attrs["State"]["Status"] = "exited"
            self.attrs["State"]["Running"] = False

        def remove(self):
            calls.append("remove")

    container = FakeContainer()
    with pytest.raises(RuntimeError, match="absent from this run"):
        cleanup_docker_cli_container(FULL_ID, identity, reason="test",
                                     inspect_fn=lambda _id: container.attrs)
    assert calls == []

    ledger_container(identity)
    from swcub.resource_safety import remove_verified_container
    remove_verified_container(container, identity, reason="test")
    assert calls == ["reload", ("stop", 10), "reload", "remove"]


def test_directory_ownership_marker_must_match_all_fields(tmp_path):
    identity = make_identity(tmp_path)
    path = tmp_path / "owned"
    expected = {"project": PROJECT_NAME, "run_id": identity.run_id,
                "owner_token": identity.owner_token, "resource_id": "dir-0001",
                "path": str(path.resolve())}
    verify_owned_directory(path, expected, identity, "dir-0001")
    with pytest.raises(RuntimeError, match="marker mismatch"):
        verify_owned_directory(path, expected | {"owner_token": "c" * 64},
                               identity, "dir-0001")


def test_image_cleanup_requires_ledger_full_id_and_all_labels(tmp_path):
    identity = make_identity(tmp_path)
    ledger = ResourceLedger(identity.ledger_path)
    ledger.record("run_started", "run", identity.run_id, identity)
    ledger.record_created_resource("image", FULL_IMAGE_ID, identity, tag="swcub-test")
    inspect_calls = []
    remove_calls = []

    def inspect_fn(image_id):
        inspect_calls.append(image_id)
        return {"Id": FULL_IMAGE_ID,
                "Config": {"Labels": {**identity.labels,
                                       "org.opencontainers.image.ref.name": "ubuntu"}}}

    def runner(args, **kwargs):
        remove_calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    remove_verified_image(FULL_IMAGE_ID, identity, reason="test",
                          runner=runner, inspect_fn=inspect_fn)
    assert inspect_calls == [FULL_IMAGE_ID, FULL_IMAGE_ID]
    assert remove_calls == [["docker", "image", "rm", FULL_IMAGE_ID]]
    rows = [json.loads(line) for line in identity.ledger_path.read_text().splitlines()]
    assert [row["event"] for row in rows] == [
        "run_started", "created", "destroy_requested", "destroyed"]
    assert all(row["labels"] == identity.labels for row in rows)


def test_image_cleanup_refuses_foreign_labels_before_removal(tmp_path):
    identity = make_identity(tmp_path)
    ledger = ResourceLedger(identity.ledger_path)
    ledger.record("run_started", "run", identity.run_id, identity)
    ledger.record_created_resource("image", FULL_IMAGE_ID, identity)
    labels = identity.labels | {OWNER_LABEL: "e" * 64}
    calls = []
    with pytest.raises(RuntimeError, match="ownership label mismatch"):
        remove_verified_image(FULL_IMAGE_ID, identity, reason="test",
                              runner=lambda args, **kwargs: calls.append(args),
                              inspect_fn=lambda _id: {"Id": FULL_IMAGE_ID,
                                                      "Config": {"Labels": labels}})
    assert calls == []

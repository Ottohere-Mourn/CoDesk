import base64
import json
import shlex
import threading
from pathlib import Path

import pytest

from oscombo.collab.data_to_deck import spec
from oscombo.collab.data_to_deck.fixtures import build_fixture, _ods, authority_sheets
from oscombo.collab.data_to_deck.workspace_bridge import SavedArtifactBridge, digest
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.collab.data_to_deck.collab_tools import CollaborationClient


class Files:
    """In-memory controller double. No Guest or GUI success is claimed here."""
    def __init__(self, files):
        self.files = dict(files)
        self.fail_transfer = False

    def get_file(self, path):
        return self.files.get(path)

    def run_bash_script(self, script, timeout=30):
        if self.fail_transfer:
            return {"status": "error"}
        lines = script.splitlines()
        self.files[shlex.split(lines[-1])[-1]] = base64.b64decode(shlex.split(lines[-2])[2])
        return {"status": "success"}


def setup_bridge(tmp_path, shared=False):
    fixture = tmp_path / "fixture"
    build_fixture(fixture)
    files = {f"/task/{spec.OUTPUTS[r]}": (fixture / spec.FIXTURE_NAMES[n]).read_bytes()
             for r, n in (("A", "authority"), ("B", "draft"))}
    a = Files(files)
    b = a if shared else Files(files)
    bridge = SavedArtifactBridge(tmp_path / "versions", "test", "/task", {"A": a, "B": b},
                                 {"A": "shared" if shared else "A", "B": "shared" if shared else "B"})
    bridge.sync()
    return bridge, a, b


def edited_workbook(tmp_path):
    sheets = authority_sheets()
    sheets["Reconciliation"].append(["progress", "note", "draft", "status", "public input"])
    path = tmp_path / "draft.ods"
    _ods(path, sheets)
    return path.read_bytes()


@pytest.mark.parametrize("shared", [False, True])
def test_saved_outputs_versioned_and_peer_reads_exact_bytes(tmp_path, shared):
    bridge, a, b = setup_bridge(tmp_path, shared)
    path = f"/task/{spec.OUTPUTS['A']}"
    initial = a.get_file(path)
    a.files[path] = edited_workbook(tmp_path)
    revision = bridge.publish("A")
    assert revision["revision"] == 1
    assert revision["sha256"] == digest(b.get_file(path))
    assert (bridge.root / "A/revision-000000.ods").read_bytes() == initial
    assert bridge.publish("A")["revision"] == 1  # no duplicate version for repeated publication
    ownership = json.loads((bridge.root / "ownership.json").read_text())
    assert ownership["writer_roles"][spec.OUTPUTS["A"]] == "A"
    assert set(bridge.snapshot()) == {"A", "B"}


def test_non_owner_change_is_preserved_and_rejected(tmp_path):
    bridge, a, b = setup_bridge(tmp_path)
    path = f"/task/{spec.OUTPUTS['A']}"
    b.files[path] = b"unexpected non-owner edit"
    a.files[path] = edited_workbook(tmp_path)
    with pytest.raises(RuntimeError, match="non-owner"):
        bridge.publish("A")
    assert b.files[path] == b"unexpected non-owner edit"
    assert bridge.snapshot()["A"]["revision"] == 0


def test_failed_transfer_can_retry_without_losing_revision(tmp_path):
    bridge, a, b = setup_bridge(tmp_path)
    path = f"/task/{spec.OUTPUTS['A']}"
    a.files[path] = edited_workbook(tmp_path)
    b.fail_transfer = True
    with pytest.raises(RuntimeError, match="transfer"):
        bridge.publish("A")
    b.fail_transfer = False
    assert bridge.publish("A")["revision"] == 1
    assert a.files[path] == b.files[path]


def test_partial_save_and_wrong_type_are_not_transferred(tmp_path):
    bridge, a, b = setup_bridge(tmp_path)
    path = f"/task/{spec.OUTPUTS['A']}"
    initial = b.files[path]
    a.files[path] = b"unfinished zip save"
    with pytest.raises(Exception):
        bridge.publish("A")
    assert b.files[path] == initial
    a.files[path] = a.files[f"/task/{spec.OUTPUTS['B']}"]
    with pytest.raises(RuntimeError, match="document type"):
        bridge.publish("A")
    with pytest.raises(ValueError, match="owned"):
        bridge.publish("../../oracle")


def test_http_publication_bound_to_authenticated_role(tmp_path):
    bridge, a, b = setup_bridge(tmp_path)
    server = make_server(ProtocolStore(tmp_path / "messages", "test"), {"A": "a", "B": "b"})
    server.workspace_bridge = bridge
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = CollaborationClient(f"http://127.0.0.1:{server.server_port}", "A", "a")
    try:
        assert client.publish_saved_artifact()["actor"] == "A"
        assert set(client.list_saved_artifacts()) == {"A", "B"}
        with pytest.raises(RuntimeError, match="400"):
            client._request("/artifacts/publish", "POST", {"actor": "B", "path": "/private/gold"})
        assert not (bridge.root / "private").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

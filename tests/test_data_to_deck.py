import base64
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from oscombo.collab.data_to_deck import spec
from oscombo.collab.data_to_deck.collab_tools import CollaborationClient
from oscombo.collab.data_to_deck.fixtures import build_fixture, _ods
from oscombo.collab.data_to_deck.oracle import (
    _numeric_equal, evaluate, read_ods, write_gold_analysis, write_gold_deck,
)
from oscombo.collab.data_to_deck.plan import make_plan, validate_live_prerequisites
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.collab.data_to_deck.provenance import RunLedger, collect_artifacts


def test_fixed_fixture_is_deterministic_and_contains_expected_initial_state(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    first, second = build_fixture(a), build_fixture(b)
    assert first == second
    schema = json.loads((Path(__file__).parents[1] / "oscombo/collab/data_to_deck/instance_schema.json").read_text())
    assert schema["properties"]["case_id"]["const"] == first["case_id"]
    assert set(first["fixture_sha256"]) == set(schema["properties"]["fixture_sha256"]["required"])
    sheets = read_ods(a / spec.FIXTURE_NAMES["authority"])
    assert set(sheets) == {"Sales", "Costs", "Quarterly_Summary", "KPI_Definitions", "Reconciliation"}
    assert sheets["Reconciliation"] == [["Section", "Metric", "Value", "Unit", "Evidence"]]
    assert len(sheets["Sales"]) == 13
    assert len(sheets["Costs"]) == 13


def test_oracle_positive_and_negative_examples(tmp_path):
    src = tmp_path / "source"
    build_fixture(src)
    analysis = tmp_path / "analysis.ods"
    deck = tmp_path / "final.odp"
    write_gold_analysis(src / spec.FIXTURE_NAMES["authority"], analysis)
    write_gold_deck(src / spec.FIXTURE_NAMES["draft"], deck)
    result = evaluate(src / spec.FIXTURE_NAMES["authority"], analysis,
                      src / spec.FIXTURE_NAMES["draft"], deck)
    assert result["actors"]["A"]["success"] is True
    assert result["actors"]["B"]["success"] is True
    assert result["joint_success"] is True
    assert all(result["issues_resolved"].values())

    negative = evaluate(src / spec.FIXTURE_NAMES["authority"],
                        src / spec.FIXTURE_NAMES["authority"],
                        src / spec.FIXTURE_NAMES["draft"], src / spec.FIXTURE_NAMES["draft"])
    assert negative["joint_success"] is False
    assert negative["actors"]["B"]["checks"]["r1_q3_revenue_corrected_in_both_slides"] is False


def test_oracle_protects_non_target_workbook_content(tmp_path):
    src = tmp_path / "source"
    build_fixture(src)
    original = read_ods(src / spec.FIXTURE_NAMES["authority"])
    gold = tmp_path / "gold.ods"
    write_gold_analysis(src / spec.FIXTURE_NAMES["authority"], gold)
    modified = read_ods(gold)
    modified["Sales"][1][2] = 999
    tampered = tmp_path / "tampered.ods"
    _ods(tampered, modified)
    result = evaluate(src / spec.FIXTURE_NAMES["authority"], tampered,
                      src / spec.FIXTURE_NAMES["draft"], src / spec.FIXTURE_NAMES["draft"])
    assert result["actors"]["A"]["protected_content"]["Sales"] is False
    assert result["actors"]["A"]["success"] is False


def test_protection_does_not_accept_small_integer_cell_changes(tmp_path):
    src = tmp_path / "source"
    build_fixture(src)
    changed = read_ods(src / spec.FIXTURE_NAMES["authority"])
    changed["Costs"][1][2] += 1e-10
    tampered = tmp_path / "tampered.ods"
    _ods(tampered, changed)
    result = evaluate(src / spec.FIXTURE_NAMES["authority"], tampered,
                      src / spec.FIXTURE_NAMES["draft"], src / spec.FIXTURE_NAMES["draft"])
    assert result["actors"]["A"]["protected_content"]["Costs"] is False
    assert result["actors"]["A"]["success"] is False


def test_read_ods_expands_repeated_cells_and_rows(tmp_path):
    path = tmp_path / "repeated.ods"
    content = b'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
 <office:body><office:spreadsheet><table:table table:name="Data">
  <table:table-row>
   <table:table-cell office:value-type="string"><text:p>Region</text:p></table:table-cell>
   <table:table-cell office:value-type="string"><text:p>Amount</text:p></table:table-cell>
   <table:table-cell office:value-type="string"><text:p>Amount</text:p></table:table-cell>
  </table:table-row>
  <table:table-row table:number-rows-repeated="2">
   <table:table-cell office:value-type="string"><text:p>West</text:p></table:table-cell>
   <table:table-cell office:value-type="float" office:value="4.25" table:number-columns-repeated="2"><text:p>4.25</text:p></table:table-cell>
  </table:table-row>
 </table:table></office:spreadsheet></office:body>
</office:document-content>'''
    with ZipFile(path, "w") as zf:
        info = ZipInfo("mimetype", (2020, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_STORED
        zf.writestr(info, b"application/vnd.oasis.opendocument.spreadsheet")
        zf.writestr("content.xml", content, compress_type=ZIP_DEFLATED)

    assert read_ods(path)["Data"] == [
        ["Region", "Amount", "Amount"],
        ["West", 4.25, 4.25],
        ["West", 4.25, 4.25],
    ]


def test_numeric_comparison_only_accepts_decimal_serialization_noise():
    # Calc may serialize a ratio one final decimal digit differently; that is
    # representational noise. Integer-valued amounts and meaningful changes
    # remain exact failures.
    assert _numeric_equal(0.451515151515152, 0.45151515151515154)
    assert _numeric_equal(0.451851851851852, 122 / 270)
    assert not _numeric_equal(38.0000000001, 38)
    assert not _numeric_equal(0.45 + 5e-15, 0.45)
    assert not _numeric_equal(0.450001, 0.45)


@pytest.mark.skipif(shutil.which("libreoffice") is None, reason="LibreOffice is not installed")
def test_libreoffice_ods_save_roundtrip_passes_official_oracle(tmp_path):
    source_dir = tmp_path / "source"
    build_fixture(source_dir)

    def resave_ods(source: Path, label: str) -> Path:
        out_dir = tmp_path / f"{label}-saved"
        out_dir.mkdir()
        profile = (tmp_path / f"lo-profile-{label}").as_uri()
        completed = subprocess.run(
            ["libreoffice", f"-env:UserInstallation={profile}", "--headless",
             "--convert-to", "ods", "--outdir", str(out_dir), str(source)],
            check=True, capture_output=True, text=True, timeout=90,
        )
        saved = out_dir / source.name
        assert saved.is_file(), completed.stdout + completed.stderr
        return saved

    # Exercise both sides of a real LibreOffice open/save round trip. The
    # output workbook contains the same protected source sheets plus the gold
    # reconciliation, as in the Guest smoke workflow.
    authority_before = source_dir / spec.FIXTURE_NAMES["authority"]
    authority_after = resave_ods(authority_before, "authority")
    analysis_before = tmp_path / "analysis.ods"
    write_gold_analysis(authority_after, analysis_before)
    analysis_after = resave_ods(analysis_before, "analysis")

    deck = tmp_path / "final.odp"
    write_gold_deck(source_dir / spec.FIXTURE_NAMES["draft"], deck)
    result = evaluate(authority_after, analysis_after,
                      source_dir / spec.FIXTURE_NAMES["draft"], deck)
    assert all(result["actors"]["A"]["protected_content"].values())
    assert result["actors"]["A"]["success"] is True
    assert result["actors"]["B"]["success"] is True
    assert result["joint_success"] is True


def test_condition_plans_hold_budget_and_message_capability_constant():
    plans = [make_plan(c) for c in spec.CONDITIONS]
    assert {p.total_model_token_budget for p in plans} == {spec.TOTAL_MODEL_TOKEN_BUDGET}
    assert all(p.message_api and p.attachment_api for p in plans)
    assert [(p.guest_count, p.desktop_sessions) for p in plans] == [
        (1, ("guest-0",)), (2, ("guest-A", "guest-B")), (1, ("guest-0",))]
    assert sum(v["model_tokens"] for v in plans[0].role_budgets.values()) == plans[0].total_model_token_budget
    assert sum(v["model_tokens"] for v in plans[1].role_budgets.values()) == plans[0].total_model_token_budget
    assert validate_live_prerequisites({"OSWORLD_DIR": "", "OSCOMBO_GUEST_IMAGE": ""})


def test_protocol_http_message_attachment_and_actor_identity(tmp_path):
    store = ProtocolStore(tmp_path, "run-test")
    tokens = {"A": "secret-a", "B": "secret-b"}
    server = make_server(store, tokens)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(path, method="GET", actor="A", payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Authorization": f"Bearer {tokens[actor]}",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read()

    try:
        status, raw = request("/attachments", "POST", payload={
            "filename": "analysis.txt", "content_base64": base64.b64encode(b"verified").decode()})
        attachment = json.loads(raw)
        assert status == 201
        status, raw = request("/messages", "POST", payload={"recipient": "B", "body": "See attachment",
                                                            "attachment_ids": [attachment["attachment_id"]]})
        message = json.loads(raw)
        assert status == 201 and message["actor"] == "A"
        status, raw = request("/messages", actor="B")
        assert status == 200 and json.loads(raw)[0]["message_id"] == message["message_id"]
        status, raw = request(f"/attachments/{attachment['attachment_id']}", actor="B")
        assert status == 200 and raw == b"verified"
        req = urllib.request.Request(base + "/messages", headers={"Authorization": "Bearer nope"})
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req, timeout=5)
        assert err.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_actor_collaboration_clients_exchange_messages_and_attachments(tmp_path):
    store = ProtocolStore(tmp_path / "collab-client", "cdd-client-test")
    tokens = {"A": "secret-a", "B": "secret-b"}
    server = make_server(store, tokens)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    a = CollaborationClient(base, "A", tokens["A"])
    b = CollaborationClient(base, "B", tokens["B"])
    try:
        attachment = a.send_attachment("west-analysis.txt", b"West profit delta is -11k; causality is not established.")
        first = a.send_message("B", "Verified initial findings attached.", [attachment["attachment_id"]])
        received = b.read_messages()
        assert len(received) == 1 and received[0]["message_id"] == first["message_id"]
        assert b.read_attachment(attachment["attachment_id"])["content"] == (
            "West profit delta is -11k; causality is not established.")

        reply = b.send_message("A", "Please confirm whether the evidence establishes causation.")
        assert a.read_messages()[0]["message_id"] == reply["message_id"]
        assert json.loads(store.log_path.read_text().splitlines()[-1])["actor"] == "B"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_model_tokens_authenticate_with_the_already_started_server(tmp_path, monkeypatch):
    import os
    from oscombo.collab.data_to_deck.live_pilot import _model_collaboration_tokens

    tokens = {"A": "registered-a", "B": "registered-b"}
    server = make_server(ProtocolStore(tmp_path / "protocol", "model-auth"), tokens)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    for role in tokens:
        monkeypatch.setenv(f"CODESK_CDD_COLLAB_TOKEN_{role}", "previous-episode")
    try:
        envs = _model_collaboration_tokens(tokens, ("A", "B"))
        base = f"http://127.0.0.1:{server.server_port}"
        a = CollaborationClient(base, "A", os.environ[envs["A"]])
        b = CollaborationClient(base, "B", os.environ[envs["B"]])
        message = a.send_message("B", "saved output available")
        assert b.read_messages()[0]["message_id"] == message["message_id"]
        with pytest.raises(RuntimeError, match="401"):
            CollaborationClient(base, "A", "previous-episode").read_messages()
        assert _model_collaboration_tokens(tokens, ()) == {}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_codex_harness_exposes_case_collaboration_mcp_only_when_opted_in(tmp_path):
    from types import SimpleNamespace
    from oscombo.harness.external import CodexHarness
    from oscombo.harness.base import AgentContext

    token_name = "CODESK_TEST_COLLAB_TOKEN"
    import os
    os.environ[token_name] = "must-not-appear-in-config"
    collaboration = {"actor": "A", "url": "http://127.0.0.1:12345", "token_env": token_name}
    spec_for_agent = {"model": "test-model", "options": {
        "collaboration": collaboration, "mcp_python": "/tmp/codesk-mcp/bin/python"}}
    harness = CodexHarness(spec_for_agent)
    harness.opts = spec_for_agent["options"]
    harness.collaboration = collaboration
    harness.action_log = tmp_path / "actions.jsonl"
    ctx = AgentContext("agentA", "CDD-RECON-001", "Verify the report.",
                       SimpleNamespace(url="http://127.0.0.1:4321"), tmp_path, 10, spec_for_agent)

    config = harness.config(ctx)
    assert "[mcp_servers.collaboration]" in config
    assert "oscombo.collab.data_to_deck.collab_tools" in config
    assert 'command = "/tmp/codesk-mcp/bin/python"' in config
    assert 'PYTHONPATH = ' in config
    assert 'CODESK_COLLAB_ACTOR = "A"' in config
    assert 'CODESK_COLLAB_TOKEN = "must-not-appear-in-config"' in config
    assert "send_message" in harness.prompt(ctx)

    default = CodexHarness({"model": "test-model", "options": {}})
    default.opts = {}
    default.collaboration = None
    default.action_log = tmp_path / "default-actions.jsonl"
    assert "[mcp_servers.collaboration]" not in default.config(ctx)
    os.environ.pop(token_name, None)


def test_codex_harness_resolves_project_relative_mcp_interpreter(tmp_path):
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from oscombo.harness.external import CodexHarness
    from oscombo.harness.base import AgentContext

    interpreter = tmp_path / "mcp-venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("", encoding="utf-8")
    relative = os.path.relpath(interpreter, Path.cwd())
    actor_spec = {"model": "test-model", "options": {"mcp_python": relative}}
    harness = CodexHarness(actor_spec)
    harness.opts = actor_spec["options"]
    harness.collaboration = None
    harness.action_log = tmp_path / "actions.jsonl"
    ctx = AgentContext("agentA", "CDD-RECON-001", "Verify the report.",
                       SimpleNamespace(url="http://127.0.0.1:4321"), tmp_path, 10, actor_spec)

    config = harness.config(ctx)
    assert f'command = "{os.path.abspath(interpreter)}"' in config


def test_codex_harness_preserves_virtualenv_interpreter_symlink(tmp_path):
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from oscombo.harness.external import CodexHarness
    from oscombo.harness.base import AgentContext

    target = tmp_path / "base-python"
    target.write_text("", encoding="utf-8")
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(target)
    relative = os.path.relpath(interpreter, Path.cwd())
    actor_spec = {"model": "test-model", "options": {"mcp_python": relative}}
    harness = CodexHarness(actor_spec)
    harness.opts = actor_spec["options"]
    harness.collaboration = None
    harness.action_log = tmp_path / "actions.jsonl"
    ctx = AgentContext("agentA", "CDD-RECON-001", "Verify the report.",
                       SimpleNamespace(url="http://127.0.0.1:4321"), tmp_path, 10, actor_spec)

    config = harness.config(ctx)
    assert f'command = "{os.path.abspath(interpreter)}"' in config
    assert f'command = "{interpreter.resolve()}"' not in config


def test_model_episode_with_no_actor_execution_is_invalid_infrastructure():
    from oscombo.collab.data_to_deck.live_pilot import _episode_result_status

    assert _episode_result_status(False, True, {
        "A": {"status": "error", "steps": 0},
    }, True) == "INVALID_INFRA_OR_RUNNER_ERROR"
    assert _episode_result_status(False, True, {
        "A": {"status": "max_steps", "steps": 60},
    }, True) == "FAIL"


def test_live_pilot_anchors_mcp_venv_path_before_guest_chdir(tmp_path):
    import os
    from pathlib import Path
    from oscombo.collab.data_to_deck.live_pilot import _absolute_existing_command

    target = tmp_path / "python-base"
    target.write_text("", encoding="utf-8")
    executable = tmp_path / ".venv" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(target)
    relative = os.path.relpath(executable, Path.cwd())

    result = _absolute_existing_command(relative)
    assert result == os.path.abspath(executable)
    assert result != str(executable.resolve())


def test_run_ledger_records_source_and_artifact_hashes(tmp_path):
    ledger = RunLedger(tmp_path / "run", {"run_id": "test-001", "condition": "collaborative_shared"})
    ledger.record("A", "action_end", guest_id="guest-1", window_id="win-7",
                  window_title="Calc", details={"action": "Ctrl+S"})
    (tmp_path / "writer.odp").write_bytes(b"saved-odp")
    manifest = collect_artifacts(tmp_path / "run", [{"actor": "B", "source_path": str(tmp_path / "writer.odp"),
                                                      "local_path": "B/final.odp"}])
    assert manifest["artifacts"][0]["sha256"]
    event = json.loads((tmp_path / "run" / "gui_events.jsonl").read_text())
    assert event["actor"] == "A" and event["window_id"] == "win-7"
    assert (tmp_path / "run" / "artifacts" / "B" / "final.odp").read_bytes() == b"saved-odp"
    with pytest.raises(ValueError):
        collect_artifacts(tmp_path / "fresh-run", [{"actor": "A", "source_path": str(tmp_path / "writer.odp"),
                                                      "local_path": "../escape"}])


def test_guest_file_adapter_accepts_osworld_controller_or_environment(tmp_path):
    from types import SimpleNamespace
    from oscombo.collab.data_to_deck.live_pilot import GuestFiles

    class Controller:
        def get_file(self, path):
            assert path == "/tmp/output.ods"
            return b"guest-output"

    controller = Controller()
    out_controller = tmp_path / "controller.ods"
    out_env = tmp_path / "environment.ods"
    GuestFiles({"controller": controller}).copy_from_guest("controller", "/tmp/output.ods", out_controller)
    GuestFiles({"env": SimpleNamespace(controller=controller)}).copy_from_guest("env", "/tmp/output.ods", out_env)
    assert out_controller.read_bytes() == b"guest-output"
    assert out_env.read_bytes() == b"guest-output"

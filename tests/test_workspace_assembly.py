from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from oscombo.collab.data_to_deck.protocol import ProtocolStore
from oscombo.collab.workspace_assembly import spec
from oscombo.collab.workspace_assembly.fixtures import _report_odt, build_fixture, is_real_odt, tree_hashes
from oscombo.collab.workspace_assembly.oracle import evaluate
from oscombo.collab.workspace_assembly.runner import configure_run, evaluate_run, make_plan, prepare_run, reset_run

FIXTURES = Path(__file__).parents[1] / "oscombo/collab/workspace_assembly/fixtures"
INITIAL = FIXTURES / "initial_workspace"
GOLD = FIXTURES / "private/gold_workspace"


def test_real_fixtures_gold_initial_and_formats():
    assert is_real_odt(INITIAL / spec.REPORT_SOURCE)
    assert is_real_odt(GOLD / spec.REPORT_FINAL)
    assert (INITIAL / "incoming/vendor_terms_final_v2.pdf").read_bytes().startswith(b"%PDF-1.")
    assert (INITIAL / "incoming/q3_chart_final.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    result = evaluate(GOLD, INITIAL)
    assert result["joint_success"] is True
    assert result["actors"]["A"]["success"] and result["actors"]["B"]["success"]
    assert evaluate(INITIAL, INITIAL)["joint_success"] is False


def test_fixture_builder_is_reproducible_and_public_manifest_excludes_gold(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    public_first, public_second = build_fixture(first), build_fixture(second)
    assert public_first == public_second
    assert tree_hashes(first / "initial_workspace") == tree_hashes(second / "initial_workspace")
    assert tree_hashes(first / "private/gold_workspace") == tree_hashes(second / "private/gold_workspace")
    assert "gold_files" not in public_first


@pytest.mark.parametrize(
    "mutation",
    ["broken_report_links", "missing_attachment", "wrong_manifest_hash", "changed_attachment",
     "changed_protected_file", "extra_file"],
)
def test_workspace_negative_controls_fail(mutation, tmp_path):
    candidate = tmp_path / mutation
    shutil.copytree(GOLD, candidate)
    if mutation == "broken_report_links":
        _report_odt(candidate / spec.REPORT_FINAL, final=False)
    elif mutation == "missing_attachment":
        (candidate / spec.ATTACHMENTS[0]["target"]).unlink()
    elif mutation == "wrong_manifest_hash":
        path = candidate / spec.MANIFEST_FINAL
        content = path.read_text(encoding="utf-8")
        path.write_text(content.replace("9d649b06", "00000000"), encoding="utf-8")
    elif mutation == "changed_attachment":
        with (candidate / spec.ATTACHMENTS[0]["target"]).open("ab") as stream:
            stream.write(b"tamper")
    elif mutation == "changed_protected_file":
        (candidate / "archive/q2_baseline.txt").write_text("modified\n", encoding="utf-8")
    else:
        (candidate / "delivery/unlisted.tmp").write_text("extra", encoding="utf-8")
    result = evaluate(candidate, INITIAL)
    assert result["joint_success"] is False
    assert result["errors"]


def _lo_uno_save(document: Path, profile: Path) -> None:
    binary = shutil.which("libreoffice") or shutil.which("soffice")
    python = Path("/usr/bin/python3")
    if binary is None or not python.is_file():
        pytest.skip("LibreOffice system UNO runtime unavailable")
    probe = subprocess.run([str(python), "-c", "import uno"], capture_output=True, text=True, timeout=10)
    if probe.returncode:
        pytest.skip("Python UNO module unavailable")
    script = '''
import os, socket, subprocess, sys, time
import uno
from com.sun.star.beans import PropertyValue
from pathlib import Path
profile, document = Path(sys.argv[1]), Path(sys.argv[2])
sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
cmd = [sys.argv[3], "--headless", "--nologo", "--nodefault", "--nofirststartwizard",
       f"-env:UserInstallation={profile.as_uri()}",
       f"--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager", "--norestore"]
env = os.environ.copy(); env.update({"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1"})
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=env)
try:
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = None
    for _ in range(120):
        try:
            ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
            break
        except Exception:
            time.sleep(0.1)
    if ctx is None:
        raise RuntimeError("LibreOffice UNO listener did not become ready")
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = PropertyValue(); hidden.Name = "Hidden"; hidden.Value = True
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(document)), "_blank", 0, (hidden,))
    if doc is None:
        raise RuntimeError("Writer could not open ODT")
    doc.store(); doc.close(True); desktop.terminate()
    print("UNO_SAVE_PASS")
finally:
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate(); proc.wait(timeout=5)
'''
    proc = subprocess.run([str(python), "-c", script, str(profile), str(document), binary],
                          capture_output=True, text=True, timeout=45)
    assert proc.returncode == 0 and "UNO_SAVE_PASS" in proc.stdout, proc.stdout + proc.stderr


def test_writer_same_path_headless_roundtrip_preserves_links(tmp_path):
    candidate = tmp_path / "workspace"
    shutil.copytree(GOLD, candidate)
    document = candidate / spec.REPORT_FINAL
    _lo_uno_save(document, tmp_path / "profile")
    result = evaluate(candidate, INITIAL)
    assert result["joint_success"] is True, result


def test_conditions_share_backend_and_message_capability():
    plans = [make_plan(condition, "same-run") for condition in spec.CONDITIONS]
    assert {plan["workspace_backend_id"] for plan in plans} == {"CDD-WA-001/same-run/canonical-project"}
    assert {plan["workspace_backend_topology"] for plan in plans} == {spec.CONDITION_RULES["backend"]}
    assert all(plan["message_capabilities_equal"] and plan["filesystem_state_is_not_gui_interference"]
               for plan in plans)
    assert [plan["desktop_count"] for plan in plans] == [1, 2, 1]


def test_prepare_message_reset_provenance_and_archive(tmp_path):
    root = tmp_path / "run"
    prepare_run(root, "run-wa-test")
    configure_run(root, "collaborative_shared")
    history = root / "history"
    history.mkdir()
    shutil.move(str(root / "workspace"), str(history / "workspace-before-test-completion"))
    shutil.copytree(GOLD, root / "workspace")
    result = evaluate_run(root)
    assert result["joint_success"] is True
    provenance = json.loads((root / "provenance.json").read_text())
    assert provenance["gui_action_trace"] == "NOT_PRESENT_OFFLINE"
    reset = reset_run(root, "run-wa-test")
    assert reset["reset_verified"] is True
    assert tree_hashes(root / "workspace") == tree_hashes(root / "oracle/initial_workspace")
    assert Path(reset["snapshot"]).is_dir()
    protocol = ProtocolStore(tmp_path / "collaboration", "wa-protocol")
    attachment = protocol.put_attachment("A", "manifest.csv", b"asset_id,path\n")
    protocol.send("A", "B", "Files organized; manifest attached.", [attachment["attachment_id"]])
    assert protocol.messages("B")[0]["actor"] == "A"
    assert protocol.get_attachment("B", attachment["attachment_id"]) == b"asset_id,path\n"

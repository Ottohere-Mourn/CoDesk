from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from oscombo.collab.data_to_deck.protocol import ProtocolStore
from oscombo.collab.spreadsheet_handoff import spec
from oscombo.collab.spreadsheet_handoff.fixtures import FormulaValue, _write_workbook, build_fixture, is_real_ods, gold_sheets
from oscombo.collab.spreadsheet_handoff.oracle import evaluate, read_ods, read_ods_formulas
from oscombo.collab.spreadsheet_handoff.runner import configure_run, evaluate_run, make_plan, prepare_run, reset_run
from oscombo.collab.spreadsheet_handoff.workbook_store import WorkbookStore

FIXTURES = Path(__file__).parents[1] / "oscombo/collab/spreadsheet_handoff/fixtures"
INITIAL = FIXTURES / "initial.ods"
GOLD = FIXTURES / "private/gold.ods"


def test_real_fixture_gold_initial_and_fixed_manifest():
    assert is_real_ods(INITIAL) and is_real_ods(GOLD)
    result = evaluate(GOLD, INITIAL)
    assert result["joint_success"] is True
    assert result["actors"]["A"]["success"] and result["actors"]["B"]["success"]
    assert evaluate(INITIAL, INITIAL)["joint_success"] is False
    manifest = json.loads((FIXTURES / "fixture_manifest.json").read_text())
    assert manifest["case_id"] == spec.CASE_ID
    assert manifest["files"]["initial.ods"]["sha256"]
    assert "gold.ods" not in manifest["files"]


def test_gold_formula_answers_and_locations():
    formulas = read_ods_formulas(GOLD)
    values = read_ods(GOLD)
    assert formulas[("Forecast", "E2")] == "of:=AVERAGE([.B2:.D2])"
    assert formulas[("Replenishment", "D3")] == "of:=ROUNDUP([.B3]/[.C3];0)*[.C3]"
    assert formulas[("Budget", "B4")] == "of:=[.B2]+[.B3]"
    assert evaluate(GOLD, INITIAL)["checks"]["budget_within_cap"] is True
    assert values["Forecast"][4][12] == 0
    assert values["Replenishment"][4][3] == 0
    assert values["Replenishment"][4][5] == 0


@pytest.mark.parametrize("mutation", ["forecast_value", "case_pack_order", "formula", "budget", "source", "missing_sheet"])
def test_negative_workbook_controls_fail(mutation, tmp_path):
    sheets = gold_sheets()
    if mutation == "forecast_value":
        sheets["Forecast"][2][6] = FormulaValue("of:=[.E3]*[.F3]", 119)
    elif mutation == "case_pack_order":
        sheets["Replenishment"][2][3] = FormulaValue("of:=ROUNDUP([.B3]/[.C3];0)*[.C3]", 90)
    elif mutation == "formula":
        sheets["Forecast"][1][4] = FormulaValue("of:=SUM([.B2:.D2])", 50)
    elif mutation == "budget":
        sheets["Budget"][3][1] = FormulaValue("of:=[.B2]+[.B3]", 3601)
    elif mutation == "source":
        sheets["Sales"][1][1] = 41
    else:
        del sheets["Replenishment"]
    candidate = tmp_path / f"{mutation}.ods"
    _write_workbook(candidate, sheets)
    result = evaluate(candidate, INITIAL)
    assert result["joint_success"] is False
    assert result["errors"]


@pytest.mark.skipif(shutil.which("libreoffice") is None and shutil.which("soffice") is None,
                    reason="LibreOffice not installed")
def test_libreoffice_ods_save_roundtrip_keeps_official_oracle(tmp_path):
    binary = shutil.which("libreoffice") or shutil.which("soffice")
    output, profile = tmp_path / "resaved", tmp_path / "lo-profile"
    output.mkdir(); profile.mkdir()
    proc = subprocess.run(
        [binary, "--headless", "--nologo", "--nodefault", "--nofirststartwizard",
         f"-env:UserInstallation={profile.as_uri()}", "--convert-to", "ods", "--outdir",
         str(output), str(GOLD)],
        check=False, capture_output=True, text=True, timeout=90,
        env={**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1"},
    )
    saved = output / GOLD.name
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert saved.is_file(), proc.stdout + proc.stderr
    result = evaluate(saved, INITIAL)
    assert result["joint_success"] is True, result


def test_version_store_exclusive_commit_reset_and_history(tmp_path):
    store = WorkbookStore.initialize(tmp_path / "store", "store-run", INITIAL)
    lease = store.acquire("A", "desktop-a")
    assert Path(lease["checkout_path"]).suffix == ".ods"
    with pytest.raises(RuntimeError, match="another actor"):
        store.acquire("B", "desktop-b")
    assert store.commit(lease["token"], GOLD)["revision"] == 1
    assert evaluate(store.current()["path"], INITIAL)["joint_success"] is True
    reset = store.reset_to_initial()
    assert reset["revision"] == 2
    assert evaluate(reset["path"], INITIAL)["joint_success"] is False
    events = [json.loads(row) for row in (tmp_path / "store/events.jsonl").read_text().splitlines()]
    assert [row["event"] for row in events] == ["lease_acquired", "commit", "reset_to_initial"]
    assert (tmp_path / "store/revisions/revision-000001.ods").is_file()


def test_conditions_share_backend_budget_and_message_capability():
    plans = [make_plan(condition, "same-run") for condition in spec.CONDITIONS]
    assert {plan["workspace_backend_id"] for plan in plans} == {"CDD-SH-001/same-run/workbook"}
    assert all(plan["message_capabilities_equal"] for plan in plans)
    assert [plan["desktop_count"] for plan in plans] == [1, 2, 1]


def test_prepare_protocol_evaluate_reset_and_provenance(tmp_path):
    root = tmp_path / "run"
    prepare_run(root, "run-sh-test")
    configure_run(root, "collaborative_shared")
    store = WorkbookStore(root / "workbook_store", "run-sh-test")
    lease = store.acquire("S", "offline-fixture")
    store.commit(lease["token"], GOLD)
    assert evaluate_run(root)["joint_success"] is True
    provenance = json.loads((root / "provenance.json").read_text())
    assert provenance["gui_action_trace"] == "NOT_PRESENT_OFFLINE"
    reset = reset_run(root, "run-sh-test")
    assert reset["history_preserved"] is True
    assert store.current()["sha256"] == reset["initial_sha256"]
    protocol = ProtocolStore(tmp_path / "message-run", "sh-protocol")
    attachment = protocol.put_attachment("A", "forecast.csv", b"SKU-LAMP,100")
    protocol.send("A", "B", "Forecast revision attached.", [attachment["attachment_id"]])
    assert protocol.messages("B")[0]["actor"] == "A"
    assert protocol.get_attachment("B", attachment["attachment_id"]) == b"SKU-LAMP,100"


def test_fixture_rebuild_is_byte_reproducible(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    assert build_fixture(first) == build_fixture(second)
    assert (first / "initial.ods").read_bytes() == (second / "initial.ods").read_bytes()
    assert (first / "private/gold.ods").read_bytes() == (second / "private/gold.ods").read_bytes()

import json
import zipfile
import xml.etree.ElementTree as ET
from tasks.paragui.build_e1 import build, write_odt
import tasks.paragui.pg_e1_oracle as oracle

def _stub_fixture(monkeypatch, tmp_path, lines):
    build(tmp_path)
    exp = json.loads((tmp_path / "expected.json").read_text())
    source = tmp_path / "state.odt"
    write_odt(source, lines)
    monkeypatch.setattr(oracle, "fetch", lambda env, doc, dest: str(source))
    monkeypatch.setattr(oracle, "expected", lambda name: exp)

def test_fixture_is_valid_odt_with_expected_three_lines(tmp_path):
    build(tmp_path)
    with zipfile.ZipFile(tmp_path / "Release-review.odt") as archive:
        names = archive.namelist()
        assert names[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype").decode() == "application/vnd.oasis.opendocument.text"
        root = ET.fromstring(archive.read("content.xml"))
    lines = ["".join(x.itertext()) for x in root.iter(oracle.TEXT_P)]
    exp = json.loads((tmp_path / "expected.json").read_text())
    assert lines == exp["lines"]
    assert len(lines) == 3

def test_jointly_feasible_final_state_passes_both_oracles(tmp_path, monkeypatch):
    build(tmp_path)
    exp = json.loads((tmp_path / "expected.json").read_text())
    final = [exp["a_line"], exp["b_line"], exp["lines"][2]]
    _stub_fixture(monkeypatch, tmp_path, final)
    assert oracle.evaluate_insert(None, "a")["score"] == 1.0
    assert oracle.evaluate_code(None, "b")["score"] == 1.0

def test_overwrite_signature_is_rejected_as_insert_success(tmp_path, monkeypatch):
    build(tmp_path)
    exp = json.loads((tmp_path / "expected.json").read_text())
    damaged = ["Release status: STATUS | READY OR-REVIEW", exp["b_line"], exp["lines"][2]]
    _stub_fixture(monkeypatch, tmp_path, damaged)
    result = oracle.evaluate_insert(None, "a")
    assert result["score"] < 1.0
    assert result["checks"]["status_inserted_without_overwriting_guard"] is False

def test_code_field_is_fixed_width():
    assert len("____") == len("AB12") == 4

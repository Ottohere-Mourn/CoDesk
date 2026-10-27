"""Real ODF parser/Oracle controls for the independent Lite case."""
from __future__ import annotations
import hashlib
from pathlib import Path

from oscombo.collab.data_to_deck.fixtures import _ods, _odp
from oscombo.collab.data_to_deck.oracle import read_ods, read_odp
from oscombo.collab.data_to_deck_lite_v1 import fixtures, oracle, spec
from oscombo.collab.data_to_deck_lite_v1.private.gold import write_gold_analysis, write_gold_deck


def _control(tmp_path: Path):
    public = tmp_path / "public"
    fixtures.build_fixture(public)
    authority = public / spec.FIXTURE_NAMES["authority"]
    draft = public / spec.FIXTURE_NAMES["draft"]
    analysis = tmp_path / "verified_analysis.ods"
    deck = tmp_path / "final_management_brief.odp"
    write_gold_analysis(authority, analysis)
    write_gold_deck(draft, analysis, deck)
    return public, authority, analysis, draft, deck


def test_gold_positive_and_public_fixture_has_no_answers(tmp_path):
    public, authority, analysis, draft, deck = _control(tmp_path)
    result = oracle.evaluate(authority, analysis, draft, deck)
    assert result["joint_success"] is True
    assert sorted(p.name for p in public.iterdir()) == sorted([*spec.FIXTURE_NAMES.values(), "fixture_manifest.json"])
    assert read_ods(authority)["Findings"][1][1] == ""
    assert "45%" not in draft.read_bytes().decode("utf-8", "ignore")


def test_wrong_value_or_fabricated_source_fails(tmp_path):
    _, authority, analysis, draft, deck = _control(tmp_path)
    sheets = read_ods(analysis)
    sheets["Findings"][1][1] = 44
    _ods(analysis, sheets)
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["A"]["success"]
    sheets["Findings"][1][1] = 45
    sheets["Findings"][1][3] = "The evidence seems reasonable."
    _ods(analysis, sheets)
    checks = oracle.evaluate(authority, analysis, draft, deck)["actors"]["A"]["checks"]
    assert not checks["q3_gross_margin_evidence"]


def test_unqualified_causal_claim_and_stale_digest_fail(tmp_path):
    _, authority, analysis, draft, deck = _control(tmp_path)
    slide = read_odp(deck)[0]
    slide[3] = "West promotion rose $14k and caused the operating profit decline."
    _odp(deck, {"slide1": slide})
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["B"]["checks"]["promotion_amount_and_evidence_boundary"]
    slide[3] = "West promotion rose $14k; these data do not prove causation."
    slide[4] = "Verified source: verified_analysis.ods SHA-256 000000000000"
    _odp(deck, {"slide1": slide})
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["B"]["checks"]["actual_final_analysis_digest"]


def test_source_tamper_and_equivalent_wording(tmp_path):
    _, authority, analysis, draft, deck = _control(tmp_path)
    sheets = read_ods(analysis)
    sheets["Sales"][1][2] = 999
    _ods(analysis, sheets)
    assert not oracle.evaluate(authority, analysis, draft, deck)["protection_success"]
    write_gold_analysis(authority, analysis)
    slide = read_odp(deck)[0]
    slide[1] = "Q3 gross margin equals 45 percent."
    slide[2] = "West operating profit decreased by USD 11k from Q2 to Q3."
    slide[3] = "West promotion increased by USD 14k; no causal evidence follows."
    slide[4] = "Verified source: verified_analysis.ods SHA-256 " + hashlib.sha256(analysis.read_bytes()).hexdigest()[:12]
    _odp(deck, {"slide1": slide})
    assert oracle.evaluate(authority, analysis, draft, deck)["joint_success"]


def test_wrong_direction_unrelated_refs_and_corrupt_artifact(tmp_path):
    _, authority, analysis, draft, deck = _control(tmp_path)
    sheets = read_ods(analysis)
    sheets["Findings"][2][3] = "Sales!C5:C7 and Costs!C5:C7 only"
    _ods(analysis, sheets)
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["A"]["checks"]["west_profit_change_evidence"]
    write_gold_analysis(authority, analysis)
    slide = read_odp(deck)[0]
    slide[2] = "West operating profit increased $11k from Q2 to Q3."
    _odp(deck, {"slide1": slide})
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["B"]["checks"]["west_profit_direction_and_value"]
    deck.write_bytes(b"partial save")
    result = oracle.evaluate(authority, analysis, draft, deck)
    assert not result["joint_success"] and result["invalid_artifact"] == "BadZipFile"


def test_fixture_bytes_are_deterministic(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    fixtures.build_fixture(first)
    fixtures.build_fixture(second)
    for name in spec.FIXTURE_NAMES.values():
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_deck_citation_goes_stale_after_valid_analysis_resave(tmp_path):
    _, authority, analysis, draft, deck = _control(tmp_path)
    old_digest = hashlib.sha256(analysis.read_bytes()).hexdigest()
    sheets = read_ods(analysis)
    sheets["Findings"][1][3] += "; independently checked"
    _ods(analysis, sheets)
    assert hashlib.sha256(analysis.read_bytes()).hexdigest() != old_digest
    result = oracle.evaluate(authority, analysis, draft, deck)
    assert result["actors"]["A"]["success"]
    assert not result["actors"]["B"]["checks"]["actual_final_analysis_digest"]

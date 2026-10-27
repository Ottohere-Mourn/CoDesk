"""Artifact controls for the independent Lite v2 Oracle."""
from __future__ import annotations
from pathlib import Path
from oscombo.collab.data_to_deck.fixtures import _ods, _odp
from oscombo.collab.data_to_deck.oracle import read_ods, read_odp
from oscombo.collab.data_to_deck_lite_v2 import fixtures, oracle, spec
from oscombo.collab.data_to_deck_lite_v2.private.gold import write_gold_analysis, write_gold_deck


def _gold(tmp_path: Path):
    fixtures.build_fixture(tmp_path / "fixture")
    root = tmp_path / "fixture"
    authority = root / spec.FIXTURE_NAMES["authority"]
    draft = root / spec.FIXTURE_NAMES["draft"]
    analysis, deck = tmp_path / "a.ods", tmp_path / "b.odp"
    write_gold_analysis(authority, analysis)
    write_gold_deck(draft, analysis, deck)
    return authority, analysis, draft, deck


def test_positive_and_public_fixture_has_blank_result(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    assert oracle.evaluate(authority, analysis, draft, deck)["joint_success"]
    assert read_ods(authority)["West_Finance"][5][1] == ""
    assert "fell" not in " ".join(read_odp(draft)[0]).casefold()


def test_wrong_analysis_or_evidence_rejected(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    sheets = read_ods(analysis)
    sheets["West_Finance"][5][1] = -10
    _ods(analysis, sheets)
    checks = oracle.evaluate(authority, analysis, draft, deck)["actors"]["A"]["checks"]
    assert not checks["correct_signed_profit_change"]
    sheets["West_Finance"][5][1] = -11
    sheets["West_Finance"][5][3] = "B4:E4 only"
    _ods(analysis, sheets)
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["A"]["checks"]["evidence_covers_q2_q3_inputs"]


def test_deck_wrong_direction_missing_source_and_equivalent_wording(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    page = read_odp(deck)[0]
    page[1] = "West operating profit increased $11k from Q2 to Q3. Source: verified_analysis.ods."
    _odp(deck, {"slide1": page})
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["B"]["checks"]["correct_direction"]
    page[1] = "West operating profit declined by USD 11k from Q2 to Q3."
    _odp(deck, {"slide1": page})
    assert not oracle.evaluate(authority, analysis, draft, deck)["actors"]["B"]["checks"]["names_saved_analysis"]
    page[1] += " Verified source: verified_analysis.ods."
    _odp(deck, {"slide1": page})
    assert oracle.evaluate(authority, analysis, draft, deck)["joint_success"]


def test_source_tamper_rejected_and_fixture_deterministic(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    sheets = read_ods(analysis)
    sheets["West_Finance"][3][4] = 1
    _ods(analysis, sheets)
    assert not oracle.evaluate(authority, analysis, draft, deck)["protection_success"]
    fixtures.build_fixture(tmp_path / "repeat")
    for name in spec.FIXTURE_NAMES.values():
        assert (tmp_path / "fixture" / name).read_bytes() == (tmp_path / "repeat" / name).read_bytes()

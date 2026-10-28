"""Independent positive/negative controls for the v2.1 scorer correction."""
from __future__ import annotations

from pathlib import Path

from oscombo.collab.data_to_deck.fixtures import _ods, _odp
from oscombo.collab.data_to_deck.oracle import read_ods, read_odp
from oscombo.collab.data_to_deck_lite_v2 import fixtures as old_fixtures, oracle as old_oracle
from oscombo.collab.data_to_deck_lite_v2_1 import fixtures, oracle, spec
from oscombo.collab.data_to_deck_lite_v2_1.private.gold import write_gold_analysis, write_gold_deck


def _gold(tmp_path: Path):
    root = tmp_path / "fixture"
    fixtures.build_fixture(root)
    authority = root / spec.FIXTURE_NAMES["authority"]
    draft = root / spec.FIXTURE_NAMES["draft"]
    analysis, deck = tmp_path / "a.ods", tmp_path / "b.odp"
    write_gold_analysis(authority, analysis)
    write_gold_deck(draft, analysis, deck)
    return authority, analysis, draft, deck


def test_positive_and_fixture_bytes_match_v2(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    assert oracle.evaluate(authority, analysis, draft, deck)["joint_success"]
    assert oracle.evaluate(authority, analysis, draft, deck)["case_version"] == "2.0.1"
    old_fixtures.build_fixture(tmp_path / "old")
    for name in spec.FIXTURE_NAMES.values():
        assert (tmp_path / "fixture" / name).read_bytes() == (tmp_path / "old" / name).read_bytes()


def test_equivalent_unit_order_is_accepted_without_changing_old_oracle(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    page = read_odp(deck)[0]
    page[1] = "West Q3 operating profit decreased by 11 USD thousands versus Q2; source: verified_analysis.ods."
    _odp(deck, {"slide1": page})
    assert oracle.evaluate(authority, analysis, draft, deck)["joint_success"]
    assert not old_oracle.evaluate(authority, analysis, draft, deck)["joint_success"]


def test_wrong_amount_unit_direction_and_source_rejected(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    page = read_odp(deck)[0]
    for body, failed_check in [
        ("West Q3 operating profit decreased by 10 USD thousands versus Q2; source: verified_analysis.ods.",
         "correct_amount_and_unit"),
        ("West Q3 operating profit decreased by 11 USD millions versus Q2; source: verified_analysis.ods.",
         "correct_amount_and_unit"),
        ("West Q3 operating profit increased by 11 USD thousands versus Q2; source: verified_analysis.ods.",
         "correct_direction"),
        ("West Q3 operating profit decreased by 11 USD thousands versus Q2.",
         "names_saved_analysis"),
    ]:
        page[1] = body
        _odp(deck, {"slide1": page})
        score = oracle.evaluate(authority, analysis, draft, deck)
        assert not score["joint_success"]
        assert not score["actors"]["B"]["checks"][failed_check]


def test_wrong_saved_analysis_still_rejected(tmp_path):
    authority, analysis, draft, deck = _gold(tmp_path)
    page = read_odp(deck)[0]
    page[1] = "West Q3 operating profit decreased by 11 USD thousands versus Q2; source: verified_analysis.ods."
    _odp(deck, {"slide1": page})
    sheets = read_ods(analysis)
    sheets["West_Finance"][5][1] = -10
    _ods(analysis, sheets)
    score = oracle.evaluate(authority, analysis, draft, deck)
    assert not score["actors"]["A"]["success"]
    assert not score["actors"]["B"]["checks"]["matches_saved_analysis_value"]

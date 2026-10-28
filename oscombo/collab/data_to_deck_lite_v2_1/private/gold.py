"""Evaluator-side controls. Never mounted for Actors."""
from __future__ import annotations
from pathlib import Path
from oscombo.collab.data_to_deck.fixtures import _ods, _odp
from oscombo.collab.data_to_deck.oracle import read_ods, read_odp


def expected_change(sheets: dict) -> int:
    rows = sheets["West_Finance"]
    q2, q3 = rows[2], rows[3]
    profit = lambda row: row[1] - row[2] - row[3] - row[4]
    return profit(q3) - profit(q2)


def write_gold_analysis(authority: str | Path, output: str | Path) -> None:
    sheets = read_ods(authority)
    sheets["West_Finance"][5][1] = expected_change(sheets)
    sheets["West_Finance"][5].append("B3:E4")
    _ods(Path(output), sheets)


def write_gold_deck(draft: str | Path, analysis: str | Path, output: str | Path) -> None:
    pages = read_odp(draft)
    value = read_ods(analysis)["West_Finance"][5][1]
    pages[0][1] = (f"West operating profit fell ${abs(value)}k from Q2 to Q3. "
                   "Source: verified_analysis.ods.")
    _odp(Path(output), {"slide1": pages[0]})

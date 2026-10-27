"""Hidden positive-control answers; only run by evaluator-side tests and Smoke."""
from __future__ import annotations
import hashlib
from pathlib import Path
from oscombo.collab.data_to_deck.fixtures import _ods, _odp
from oscombo.collab.data_to_deck.oracle import read_ods, read_odp


def gold_findings_rows() -> list[list[object]]:
    return [
        ["Metric", "Value", "Unit", "Evidence"],
        ["Q3 gross margin", 45, "%", "Sales!C5:C7 = 300; Costs!C5:C7 = 165; (300-165)/300"],
        ["West operating-profit change (Q3-Q2)", -11, "USD_k",
         "Sales!C4, Costs!C4:E4 => Q2 24; Sales!C7, Costs!C7:E7 => Q3 13"],
    ]


def write_gold_analysis(authority: str | Path, output: str | Path) -> None:
    sheets = read_ods(authority)
    sheets["Findings"] = gold_findings_rows()
    _ods(Path(output), sheets)


def write_gold_deck(draft: str | Path, analysis: str | Path, output: str | Path) -> None:
    pages = read_odp(draft)
    page = pages[0]
    page[1] = "Q3 gross margin: 45%."
    page[2] = "West operating profit fell $11k from Q2 to Q3."
    page[3] = "West promotion spending rose $14k; the figures do not establish causation."
    page[4] = ("Verified source: verified_analysis.ods SHA-256 "
               + hashlib.sha256(Path(analysis).read_bytes()).hexdigest()[:12])
    _odp(Path(output), {"slide1": page})

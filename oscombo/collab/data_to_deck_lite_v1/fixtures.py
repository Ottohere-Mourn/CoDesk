"""Deterministic public ODF fixture for Lite v1; no Gold is included."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from oscombo.collab.data_to_deck.fixtures import _ods, _odp
from . import spec

SALES = (("Q2", "North", 110), ("Q2", "South", 90), ("Q2", "West", 70),
         ("Q3", "North", 120), ("Q3", "South", 95), ("Q3", "West", 85))
COSTS = (("Q2", "North", 60, 5, 3), ("Q2", "South", 50, 5, 3),
         ("Q2", "West", 38, 4, 4), ("Q3", "North", 66, 6, 4),
         ("Q3", "South", 52, 5, 2), ("Q3", "West", 47, 7, 18))


def authority_sheets() -> dict[str, list[list[object]]]:
    return {
        "Sales": [["Quarter", "Region", "Revenue_USD_k"], *map(list, SALES)],
        "Costs": [["Quarter", "Region", "COGS_USD_k", "Fulfillment_USD_k", "Promotion_USD_k"],
                  *map(list, COSTS)],
        "KPI_Definitions": [
            ["Metric", "Definition"],
            ["Gross margin", "(Revenue - COGS) / Revenue; report as percent"],
            ["Operating profit", "Revenue - COGS - fulfillment - promotion; report in USD thousands"],
            ["Change", "Q3 minus Q2; a negative value is a decline"],
            ["Causality", "A simultaneous cost change is not proof of cause"],
        ],
        "Findings": [
            ["Metric", "Value", "Unit", "Evidence"],
            ["Q3 gross margin", "", "%", ""],
            ["West operating-profit change (Q3-Q2)", "", "USD_k", ""],
        ],
    }


def draft_slide() -> list[str]:
    return [
        "Q3 Review | Finance",
        "Q3 gross margin: 31%",
        "West operating profit increased $11k from Q2 to Q3.",
        "West promotion spending increased and caused the profit change.",
        "Verified source: pending Agent A analysis.",
    ]


def build_fixture(root: str | Path) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise FileExistsError(f"Lite fixture destination is not empty: {root}")
    _ods(root / spec.FIXTURE_NAMES["authority"], authority_sheets())
    _odp(root / spec.FIXTURE_NAMES["draft"], {"slide1": draft_slide()})
    (root / spec.FIXTURE_NAMES["brief"]).write_text(
        "Q3 Review | Finance — public case brief\n\n"
        "A verifies Q3 gross margin and the West operating-profit change from Q2 to Q3. "
        "In the Findings sheet, use the preprinted metric and unit columns; fill Value and Evidence. "
        "Evidence should cite source cells in Sales and Costs. The six Q2/Q3 region rows are aligned: "
        "Q2 is rows 2–4 and Q3 is rows 5–7; West is row 4 or 7.\n\n"
        "B revises the one-slide draft, using the latest saved A revision before finalizing. "
        "Correct gross margin, West profit direction/amount, and the promotion/causality statement. "
        "The last line must cite the final A workbook's SHA-256 first 12 hex characters. "
        "Both may work concurrently. Only each role's output file is writable by that role. "
        "Messages and attachments are available in both desktop conditions.\n",
        encoding="utf-8")
    files = {name: {"sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
                    "bytes": (root / name).stat().st_size}
             for name in spec.FIXTURE_NAMES.values()}
    manifest = {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
                "fixture_sha256": files, "conditions": spec.CONDITIONS,
                "outputs": spec.OUTPUTS, "role_budgets": spec.ROLE_BUDGET}
    (root / "fixture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest

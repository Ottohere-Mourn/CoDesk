"""Deterministic public ODF fixture for Lite v2; contains no answers."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from oscombo.collab.data_to_deck.fixtures import _ods, _odp
from . import spec


def authority_sheets() -> dict[str, list[list[object]]]:
    return {"West_Finance": [
        ["West finance | USD thousands"],
        ["Quarter", "Revenue", "COGS", "Fulfill", "Promo"],
        ["Q2", 70, 38, 4, 4],
        ["Q3", 85, 47, 7, 18],
        ["Operating profit = Revenue - COGS - Fulfillment - Promotion"],
        ["Change Q3-Q2", "", "Evidence", ""],
    ]}


def draft_slide() -> list[str]:
    return ["West Q3 | Management Brief",
            "West Q3 vs Q2 profit: [await A result]. Source: [await A analysis]."]


def build_fixture(root: str | Path) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise FileExistsError(f"Lite v2 fixture destination is not empty: {root}")
    _ods(root / spec.FIXTURE_NAMES["authority"], authority_sheets())
    _odp(root / spec.FIXTURE_NAMES["draft"], {"slide1": draft_slide()})
    (root / spec.FIXTURE_NAMES["brief"]).write_text(
        "# West Q3 management brief\n\n"
        "The workbook gives West Q2 and Q3 revenue and three expense categories, all in USD thousands. "
        "Operating profit = Revenue - COGS - Fulfillment - Promotion. "
        "A enters the signed Q3-minus-Q2 profit change in B6 and cites the source cells in D6, "
        "then saves, publishes and sends B a verified handoff. "
        "B may prepare the slide immediately, but must use A's saved analysis and message before finalizing "
        "the one conclusion box and citing verified_analysis.ods. "
        "The output copies are already open. Only each role's output may be edited. "
        "Both roles have the same collaboration tools in either desktop condition.\n",
        encoding="utf-8")
    files = {name: {"sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
                    "bytes": (root / name).stat().st_size}
             for name in spec.FIXTURE_NAMES.values()}
    manifest = {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
                "fixture_sha256": files, "conditions": spec.CONDITIONS,
                "outputs": spec.OUTPUTS, "role_budgets": spec.ROLE_BUDGET}
    (root / "fixture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest

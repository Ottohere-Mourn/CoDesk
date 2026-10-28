"""Secondary, post hoc wording sensitivity; never overwrites the frozen Oracle."""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys

from oscombo.collab.data_to_deck_lite_v2 import oracle


def extended_amount(text: str, value: float) -> bool:
    """Also accept the financial-report unit order '<number> USD thousands'."""
    if oracle_amount(text, value):
        return True
    magnitude = str(int(abs(value))) if float(value).is_integer() else str(abs(value))
    return bool(re.search(rf"(?<!\d){re.escape(magnitude)}(?:\.0+)?\s+USD\s+thousands?\b",
                          text, re.I))


oracle_amount = oracle._amount


def audit(root: Path) -> dict:
    frozen = json.loads((root / "oracle.json").read_text())
    oracle._amount = extended_amount
    try:
        sensitivity = oracle.evaluate(
            root / "fixtures/quarterly_authority.ods",
            root / "artifacts/A/verified_analysis.ods",
            root / "fixtures/management_draft.odp",
            root / "artifacts/B/final_management_brief.odp")
    finally:
        oracle._amount = oracle_amount
    result = {"run_id": root.name, "frozen_joint_success": frozen.get("joint_success"),
              "frozen_actor_success": {r: frozen.get("actors", {}).get(r, {}).get("success") for r in "AB"},
              "secondary_equivalent_wording_joint_success": sensitivity["joint_success"],
              "secondary_actor_success": {r: sensitivity["actors"][r]["success"] for r in "AB"},
              "changed_b_checks": {k: [frozen["actors"]["B"]["checks"].get(k), v]
                                   for k, v in sensitivity["actors"]["B"]["checks"].items()
                                   if frozen["actors"]["B"]["checks"].get(k) != v},
              "status": "post_hoc_sensitivity_only_not_formal_score",
              "rule": "additional unit expression: correct numeric amount followed by USD thousands"}
    (root / "oracle_equivalence_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1]).resolve()), indent=2))

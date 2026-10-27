"""Evaluator-side Lite Oracle. Never mounted or exposed to Actor tools."""
from __future__ import annotations
import hashlib
import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from oscombo.collab.data_to_deck.oracle import read_ods, read_odp, _content_equal
from . import spec
from .fixtures import authority_sheets, draft_slide


def _numeric(value: object, expected: float, unit: str) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        match = re.fullmatch(r"\s*([+\-−]?\d+(?:\.\d+)?)\s*(?:%|pct|percent)?\s*", value, re.I)
        if not match:
            return False
        num = float(match.group(1).replace("−", "-"))
    else:
        return False
    return math.isfinite(num) and math.isclose(num, expected, abs_tol=1e-8, rel_tol=0)


def _has_refs(evidence: object, required: tuple[str, ...]) -> bool:
    if not isinstance(evidence, str):
        return False
    normalized = re.sub(r"[\s$']", "", evidence.casefold())
    return all(bool(re.search(r"(?<![a-z])" + ref.replace("!", "[!.]?") + r"(?!\d)", normalized))
               for ref in required)


def _number_with_unit(text: str, n: int, unit: str) -> bool:
    if unit == "%":
        return bool(re.search(rf"(?<!\d){n}(?:\.0+)?\s*(?:%|percent\b|pct\b)", text))
    return bool(re.search(rf"(?<!\d)(?:\$\s*)?{n}(?:\.0+)?\s*(?:k\b|thousand\b|usd[_\s-]*k\b)|\$\s*{n},000\b", text))


def _negative_direction(text: str) -> bool:
    return bool(re.search(r"\b(?:fell|fall|decreased?|declined?|dropped?|down|lower|negative|reduced?)\b", text)
                or re.search(r"(?<!\d)-\s*\$?\s*11(?:\.0+)?", text))


def _causal_boundary(text: str) -> bool:
    lowered = text.casefold()
    qualified = any(re.search(pattern, lowered) for pattern in (
        r"(?:do(?:es)?|did)\s+not\s+(?:establish|prove|show|demonstrate)",
        r"(?:cannot|can't|can not)\s+(?:infer|establish|prove|conclude|attribute)",
        r"(?:no|insufficient)\s+(?:causal\s+)?evidence",
        r"\b(?:unproven|uncertain|unsupported)\b.{0,30}\b(?:cause|causal|attribut)",
        r"\b(?:cause|causal|attribut)\w*\b.{0,30}\b(?:unproven|uncertain|unsupported)\b",
        r"\bcorrelation\b.{0,30}\bnot\b.{0,20}\bcausation\b",
    ))
    if not qualified:
        return False
    for clause in re.split(r"[.;]", lowered):
        if (re.search(r"\b(?:promotion|campaign)\b.{0,100}\b(?:caused|led to|explains|was responsible for)\b", clause)
                and not re.search(r"\b(?:not|cannot|can't|no evidence|unproven|unsupported)\b", clause)):
            return False
    return True


def _invalid(reason: str) -> dict:
    return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
            "actors": {"A": {"success": False, "checks": {}},
                       "B": {"success": False, "checks": {}}},
            "joint_success": False, "protection_success": False,
            "invalid_artifact": reason}


def evaluate(authority_path: str | Path, analysis_path: str | Path,
             draft_path: str | Path, final_deck_path: str | Path) -> dict:
    try:
        authoritative = read_ods(authority_path)
        analysis = read_ods(analysis_path)
        draft = read_odp(draft_path)
        pages = read_odp(final_deck_path)
    except (OSError, zipfile.BadZipFile, ET.ParseError, ValueError, KeyError) as exc:
        return _invalid(type(exc).__name__)
    source = authority_sheets()
    protected = {name: (_content_equal(authoritative.get(name), source[name])
                        and _content_equal(analysis.get(name), source[name]))
                 for name in ("Sales", "Costs", "KPI_Definitions")}
    findings = analysis.get("Findings", [])
    labels = source["Findings"]
    shape = len(findings) == 3 and all(len(r) >= 4 for r in findings)
    checks_a = {"protected_" + k: v for k, v in protected.items()}
    checks_a["findings_shape_and_labels"] = shape and all(
        findings[i][0] == labels[i][0] and findings[i][2] == labels[i][2] for i in range(3))
    if shape:
        checks_a["q3_gross_margin_value"] = _numeric(findings[1][1], 45, "%")
        checks_a["q3_gross_margin_evidence"] = _has_refs(
            findings[1][3], ("sales!c5:c7", "costs!c5:c7"))
        checks_a["west_profit_change_value"] = _numeric(findings[2][1], -11, "USD_k")
        checks_a["west_profit_change_evidence"] = _has_refs(
            findings[2][3], ("sales!c4", "costs!c4:e4", "sales!c7", "costs!c7:e7"))
    actor_a = all(checks_a.values())

    shape_b = len(pages) == 1 and len(pages[0]) == 5
    slide = pages[0] if shape_b else [""] * 5
    margin, profit, promotion, citation = (str(x).casefold() for x in slide[1:5])
    digest = hashlib.sha256(Path(analysis_path).read_bytes()).hexdigest()[:12]
    checks_b = {
        "one_slide_five_frames": shape_b,
        "preserved_title": bool(draft and draft[0] and slide[0] == draft_slide()[0] == draft[0][0]),
        "gross_margin_meaning_and_value": bool("q3" in margin and "gross" in margin
                                               and "margin" in margin and _number_with_unit(margin, 45, "%")),
        "west_profit_direction_and_value": bool(all(x in profit for x in ("west", "operating", "profit", "q2", "q3"))
                                                and _number_with_unit(profit, 11, "k")
                                                and _negative_direction(profit)
                                                and not re.search(r"\b(?:rose|increased|improved)\b", profit)),
        "promotion_amount_and_evidence_boundary": bool("west" in promotion and "promotion" in promotion
                                                       and _number_with_unit(promotion, 14, "k")
                                                       and ("+" in promotion or re.search(r"\b(?:rose|increased|up|higher)\b", promotion))
                                                       and _causal_boundary(promotion)),
        "actual_final_analysis_digest": bool("verified_analysis.ods" in citation and digest in citation),
        "analysis_verified_for_handoff": actor_a,
    }
    actor_b = all(checks_b.values())
    return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
            "actors": {"A": {"success": actor_a, "checks": checks_a},
                       "B": {"success": actor_b, "checks": checks_b}},
            "joint_success": actor_a and actor_b, "protection_success": all(protected.values()),
            "analysis_sha256": hashlib.sha256(Path(analysis_path).read_bytes()).hexdigest(),
            "behavioral_handoff": "requires separate message/revision/GUI trace audit; not inferred by Oracle"}

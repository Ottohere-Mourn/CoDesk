"""Evaluator-side artifact Oracle. Behavioral handoff is audited separately."""
from __future__ import annotations
import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from oscombo.collab.data_to_deck.oracle import read_ods, read_odp, _content_equal
from . import spec
from .fixtures import authority_sheets, draft_slide


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        match = re.fullmatch(r"\s*([+\-−]?\d+(?:\.\d+)?)\s*(?:k|USD[_\s-]*k)?\s*", value, re.I)
        if not match:
            return None
        result = float(match.group(1).replace("−", "-"))
    else:
        return None
    return result if math.isfinite(result) else None


def _evidence(value: object) -> bool:
    if not isinstance(value, str):
        return False
    s = re.sub(r"[\s$']", "", value.casefold())
    if re.search(r"(?<![a-z])(?:west_finance[!.])?b3:e4(?!\d)", s):
        return True
    # All eight individual cells also count, with or without sheet prefixes.
    return all(re.search(rf"(?<![a-z])(?:west_finance[!.])?{column}{row}(?!\d)", s)
               for row in (3, 4) for column in "bcde")


def _direction(text: str, value: float) -> bool:
    negative = value < 0
    if negative:
        return bool(re.search(r"\b(?:fell|fall|decreased?|declined?|dropped?|down|lower|negative|reduced?)\b", text)
                    or re.search(r"(?<!\d)-\s*\$?\s*\d", text)) and not bool(
                        re.search(r"\b(?:rose|increased|improved|grew|higher)\b", text))
    return bool(re.search(r"\b(?:rose|increased|improved|grew|higher|up|positive)\b", text)
                or re.search(r"(?<!\d)\+\s*\$?\s*\d", text))


def _amount(text: str, value: float) -> bool:
    n = abs(value)
    magnitude = str(int(n)) if n.is_integer() else str(n)
    return bool(re.search(rf"(?<!\d)(?:[+\-−]\s*)?(?:\$\s*)?{re.escape(magnitude)}(?:\.0+)?\s*"
                          r"(?:k\b|thousand\b|USD[_\s-]*k\b)", text, re.I)
                or re.search(rf"\$\s*{int(n) * 1000:,}\b", text))


def _invalid(reason: str) -> dict:
    return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
            "actors": {"A": {"success": False, "checks": {}},
                       "B": {"success": False, "checks": {}}},
            "joint_success": False, "protection_success": False,
            "invalid_artifact": reason}


def evaluate(authority_path: str | Path, analysis_path: str | Path,
             draft_path: str | Path, final_deck_path: str | Path) -> dict:
    try:
        authority = read_ods(authority_path)
        analysis = read_ods(analysis_path)
        draft = read_odp(draft_path)
        pages = read_odp(final_deck_path)
    except (OSError, zipfile.BadZipFile, ET.ParseError, ValueError, KeyError) as exc:
        return _invalid(type(exc).__name__)
    expected = authority_sheets()
    base = expected["West_Finance"]
    arows = analysis.get("West_Finance", [])
    auth_rows = authority.get("West_Finance", [])
    authority_intact = bool(len(auth_rows) == 6
                            and all(_content_equal(auth_rows[i], base[i]) for i in range(5))
                            and auth_rows[5][:3] == base[5][:3])
    source_intact = bool(authority_intact and len(arows) == 6 and
                         all(_content_equal(arows[i], base[i]) for i in range(5)))
    labels_intact = bool(len(arows) >= 6 and len(arows[5]) >= 4
                         and arows[5][0] == base[5][0] and arows[5][2] == base[5][2])
    q2, q3 = base[2], base[3]
    profit = lambda r: r[1] - r[2] - r[3] - r[4]
    expected_change = profit(q3) - profit(q2)
    actual = _number(arows[5][1]) if labels_intact else None
    checks_a = {"source_intact": source_intact, "output_labels_intact": labels_intact,
                "correct_signed_profit_change": actual is not None and math.isclose(actual, expected_change, abs_tol=1e-8),
                "evidence_covers_q2_q3_inputs": _evidence(arows[5][3]) if labels_intact else False}
    a_success = all(checks_a.values())
    shape = bool(len(pages) == 1 and len(pages[0]) >= 2)
    title = pages[0][0] if shape else ""
    body = " ".join(pages[0][1:]).casefold() if shape else ""
    numeric_source = actual if a_success else float(expected_change)
    checks_b = {
        "one_slide_with_title_and_conclusion": shape,
        "title_preserved": bool(shape and draft and draft[0] and title == draft_slide()[0] == draft[0][0]),
        "resolved_placeholder": bool(body and "[await" not in body and "pending" not in body),
        "west_operating_profit_q2_q3": bool("west" in body and "operating" in body and "profit" in body
                                            and "q2" in body and "q3" in body),
        "correct_direction": _direction(body, numeric_source),
        "correct_amount_and_unit": _amount(body, numeric_source),
        "names_saved_analysis": "verified_analysis.ods" in body,
        "analysis_verified_for_handoff": a_success,
    }
    b_success = all(checks_b.values())
    return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
            "actors": {"A": {"success": a_success, "checks": checks_a},
                       "B": {"success": b_success, "checks": checks_b}},
            "joint_success": a_success and b_success, "protection_success": source_intact,
            "expected_change_evaluator_only": expected_change,
            "behavioral_handoff": "audit messages, saved revisions and GUI action chronology separately"}

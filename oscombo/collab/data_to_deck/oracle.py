"""Hidden-state, programmatic oracle for the Data-to-Deck V0 case."""
from __future__ import annotations

import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from . import spec
from .fixtures import NS, authority_sheets


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


_MAX_EXPANDED_CELLS = 1_000_000


def _repeat_count(element: ET.Element, attribute: str) -> int:
    raw = element.attrib.get(_q("table", attribute), "1")
    try:
        count = int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid ODS {attribute}: {raw!r}") from exc
    if count < 1:
        raise ValueError(f"invalid ODS {attribute}: {raw!r}")
    return count


def read_ods(path: str | Path) -> dict[str, list[list[object]]]:
    """Read populated ODS cells, expanding the repetition syntax used by Calc.

    ODF permits a cell or row to represent repeated logical cells/rows.  These
    repetitions are part of the sheet data, not formatting, so they must be
    expanded before the evaluator compares workbook contents.  Trailing empty
    cells and empty rows are ignored as they carry no cell value.  A hard cap
    protects the evaluator from malformed or unexpectedly huge repeat counts.
    """
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    result: dict[str, list[list[object]]] = {}
    for table in root.findall(f".//{_q('table', 'table')}"):
        name = table.attrib.get(_q("table", "name"), "")
        rows: list[list[object]] = []
        expanded_cells = 0
        for row in table.iter(_q("table", "table-row")):
            values: list[object] = []
            for cell in list(row):
                if cell.tag not in (_q("table", "table-cell"), _q("table", "covered-table-cell")):
                    continue
                typ = cell.attrib.get(_q("office", "value-type"))
                raw = cell.attrib.get(_q("office", "value"))
                if typ == "float" and raw is not None:
                    val: object = float(raw)
                    if val.is_integer():
                        val = int(val)
                else:
                    val = "".join(t.text or "" for t in cell.findall(f".//{_q('text', 'p')}"))
                repeat = _repeat_count(cell, "number-columns-repeated")
                values.extend([val] * repeat)
                expanded_cells += repeat
                if expanded_cells > _MAX_EXPANDED_CELLS:
                    raise ValueError(f"ODS sheet {name!r} exceeds expanded-cell limit")
            while values and values[-1] == "":
                values.pop()
            if values:
                row_repeat = _repeat_count(row, "number-rows-repeated")
                if expanded_cells + len(values) * (row_repeat - 1) > _MAX_EXPANDED_CELLS:
                    raise ValueError(f"ODS sheet {name!r} exceeds expanded-cell limit")
                rows.extend([values.copy() for _ in range(row_repeat)])
                expanded_cells += len(values) * (row_repeat - 1)
        result[name] = rows
    return result


def read_odp(path: str | Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    pages = []
    for page in root.findall(f".//{_q('draw', 'page')}"):
        pages.append([" ".join(t.text or "" for t in p.findall(f".//{_q('text', 'span')}"))
                      if p.findall(f".//{_q('text', 'span')}" ) else (p.text or "")
                      for p in page.findall(f".//{_q('text', 'p')}")])
    return pages


def _gold_reconciliation_rows() -> list[list[object]]:
    q2, q3 = spec.GOLD_QUARTERS["Q2"], spec.GOLD_QUARTERS["Q3"]
    rows: list[list[object]] = [["Section", "Metric", "Value", "Unit", "Evidence"]]
    fields = ("revenue", "cogs", "fulfillment", "promotion", "total_cost", "operating_profit")
    for field in fields:
        rows.append(["quarter_delta", field, q3[field] - q2[field], "USD_k", f"Quarterly_Summary Q3 - Q2 ({field})"])
    rows.extend([
        ["quarter_delta", "revenue_growth", (q3["revenue"] - q2["revenue"]) / q2["revenue"], "fraction", "Quarterly_Summary revenue Q3 vs Q2"],
        ["quarter_delta", "profit_growth", (q3["operating_profit"] - q2["operating_profit"]) / q2["operating_profit"], "fraction", "Quarterly_Summary operating_profit Q3 vs Q2"],
        ["quarter_delta", "margin_change_pp", (q3["operating_margin"] - q2["operating_margin"]) * 100, "percentage_points", "Quarterly_Summary operating_margin Q3 - Q2"],
    ])
    for region in spec.REGIONS:
        rows.append(["region_delta", region, spec.GOLD_REGIONAL_PROFIT["Q3"][region] - spec.GOLD_REGIONAL_PROFIT["Q2"][region], "USD_k", f"Sales and Costs Q3 - Q2 ({region})"])
    for field in ("revenue", "promotion", "operating_profit"):
        if field == "revenue":
            v = next(s[2] for s in spec.SALES if s[:2] == ("Q3", "West")) - next(s[2] for s in spec.SALES if s[:2] == ("Q2", "West"))
        elif field == "promotion":
            v = next(c[4] for c in spec.COSTS if c[:2] == ("Q3", "West")) - next(c[4] for c in spec.COSTS if c[:2] == ("Q2", "West"))
        else:
            v = spec.GOLD_REGIONAL_PROFIT["Q3"]["West"] - spec.GOLD_REGIONAL_PROFIT["Q2"]["West"]
        rows.append(["west_delta", field, v, "USD_k", f"Sales/Costs West Q3 - Q2 ({field})"])
    rows.append(["evidence_boundary", "causality", "not_established", "status", "Observational totals do not establish cause"])
    return rows


def write_gold_analysis(source_ods: str | Path, output_ods: str | Path) -> None:
    """Test helper: copy source sheets and insert the exact gold analysis."""
    from .fixtures import _ods
    source = read_ods(source_ods)
    source["Reconciliation"] = _gold_reconciliation_rows()
    _ods(Path(output_ods), source)


def write_gold_deck(source_odp: str | Path, output_odp: str | Path) -> None:
    """Test helper: produce a positive ODP while preserving all correct draft text."""
    from .fixtures import _odp
    pages = read_odp(source_odp)
    pages[0][2] = "Q3 revenue: $300k"
    pages[1][1] = "Q3 revenue: $300k"
    pages[1][2] = "Gross Margin: 45% (Q3)"
    pages[1][3] = "Operating Margin: 31% (Q3)"
    pages[2][2] = "Q2 to Q3 bridge: revenue +$30k; total cost +$35k; operating profit -$5k."
    pages[2][3] = "West: revenue +$15k, promotion expense +$14k, operating profit -$11k. These data do not establish causality."
    _odp(Path(output_odp), {f"slide{i+1}": p for i, p in enumerate(pages)})


def _numeric_equal(a: object, b: object, tolerance: float = 1e-15) -> bool:
    if (isinstance(a, (int, float)) and not isinstance(a, bool)
            and isinstance(b, (int, float)) and not isinstance(b, bool)):
        # Currency/count cells and integral answers must remain exact.  The
        # tolerance is only for non-integral values whose decimal serialization
        # can differ by a final floating-point digit across ODF save cycles.
        if float(b).is_integer():
            return float(a) == float(b)
        return math.isclose(float(a), float(b), rel_tol=tolerance, abs_tol=tolerance)
    return a == b


def _content_equal(actual: object, expected: object) -> bool:
    """Compare workbook values exactly, except representation noise in decimals."""
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _content_equal(a, e) for a, e in zip(actual, expected))
    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        return _numeric_equal(actual, expected)
    return actual == expected


def _rows_as_map(rows: list[list[object]]) -> dict[tuple[object, object], list[object]]:
    return {(r[0], r[1]): r for r in rows[1:] if len(r) >= 5}


def evaluate(authority_path: str | Path, analysis_path: str | Path,
             draft_path: str | Path, final_deck_path: str | Path) -> dict[str, object]:
    """Score only supplied deliverables; expected answers remain module-private."""
    authoritative = read_ods(authority_path)
    analysis = read_ods(analysis_path)
    pages = read_odp(final_deck_path)
    original_pages = read_odp(draft_path)
    source_expected = authority_sheets()
    protected_sheets = ("Sales", "Costs", "Quarterly_Summary", "KPI_Definitions")
    protection = {name: _content_equal(authoritative.get(name), source_expected[name])
                  and _content_equal(analysis.get(name), source_expected[name])
                  for name in protected_sheets}

    expected_rows = _rows_as_map(_gold_reconciliation_rows())
    reconciliation_rows = analysis.get("Reconciliation", [])
    observed_rows = _rows_as_map(reconciliation_rows)
    analysis_checks = {}
    row_keys = [(r[0], r[1]) for r in reconciliation_rows[1:] if len(r) >= 2]
    analysis_checks["exact_row_set"] = len(row_keys) == len(expected_rows) and len(set(row_keys)) == len(expected_rows)
    for key, expected_row in expected_rows.items():
        actual = observed_rows.get(key)
        analysis_checks[f"{key[0]}:{key[1]}"] = bool(
            actual and len(actual) >= 5 and _numeric_equal(actual[2], expected_row[2])
            and actual[3] == expected_row[3] and isinstance(actual[4], str) and bool(actual[4].strip()))

    flat = [" ".join(page) for page in pages]
    all_text = " ".join(flat).casefold()
    slide_count_ok = len(pages) == 3
    # Preserve title and correct untouched statements from the original draft.
    original_text = [t for p in original_pages for t in p]
    required_preserved = ("Quarterly Performance | Management Review", "Revenue grew across the year; operating profit is the operating result after COGS, fulfillment, and promotion.",
                          "Q4 revenue: $330k", "Margin and Cost Profile", "Q3 promotion expense increased to $24k.",
                          "Q2 to Q3: What Changed", "Q2 operating profit: $98k; Q3 operating profit: $93k.")
    preserved = {t: t in original_text and t.casefold() in all_text for t in required_preserved}
    deck_checks = {
        "three_slides": slide_count_ok,
        "r1_q3_revenue_corrected_in_both_slides": sum("q3 revenue: $300k" in p.casefold() for p in flat) >= 2
            and "310" not in all_text,
        "r2_metric_definitions_correct": "gross margin: 45%" in all_text and "operating margin: 31%" in all_text
            and "gross margin: 31%" not in all_text,
        "r3_causality_qualified": "causality" in all_text and ("not establish" in all_text or "not established" in all_text)
            and "caused the q3 profit decline" not in all_text,
        "q2_q3_bridge_present": all(s in all_text for s in ("revenue +$30k", "total cost +$35k", "operating profit -$5k")),
        "west_evidence_present": all(s in all_text for s in ("west:", "revenue +$15k", "promotion expense +$14k", "operating profit -$11k")),
    }
    deck_checks.update({f"preserved:{k}": v for k, v in preserved.items()})
    actor_a = all(analysis_checks.values()) and all(protection.values())
    actor_b = all(deck_checks.values())
    joint = actor_a and actor_b
    return {
        "case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
        "actors": {"A": {"success": actor_a, "checks": analysis_checks, "protected_content": protection},
                   "B": {"success": actor_b, "checks": deck_checks}},
        "joint_success": joint,
        "issues_resolved": {"R1": deck_checks["r1_q3_revenue_corrected_in_both_slides"],
                   "R2": deck_checks["r2_metric_definitions_correct"],
                   "R3": deck_checks["r3_causality_qualified"]},
        "protection_success": all(protection.values()),
    }

"""Structural ODS oracle; value and float rules reuse Data-to-Deck's parser."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from oscombo.collab.data_to_deck.fixtures import NS
from oscombo.collab.data_to_deck.oracle import _content_equal, _numeric_equal, read_ods

from . import spec
from .fixtures import FormulaValue, gold_sheets, is_real_ods


def _tag(prefix: str, name: str) -> str:
    return f"{{{NS[prefix]}}}{name}"


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def normalize_formula(formula: str) -> str:
    """Normalize only ODF/Calc spelling differences, not formula semantics."""
    value = formula.strip().casefold().replace("of:=", "=").replace("$", "")
    value = value.replace("[", "").replace("]", "").replace(";", ",")
    value = value.replace(".", "")
    return re.sub(r"\s+", "", value)


def read_ods_formulas(path: str | Path) -> dict[tuple[str, str], str]:
    """Read formula locations while honoring ODF repeated rows/cells.

    The value oracle uses the existing Data-to-Deck `read_ods`, which expands
    repeated ODF structures and limits expansion. This companion reader records
    formula text at its spreadsheet coordinate; populated formula cells in our
    gold fixture are never repeated, but repeated cells around them are counted.
    """
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    found: dict[tuple[str, str], str] = {}
    for table in root.findall(f".//{_tag('table', 'table')}"):
        sheet = table.attrib.get(_tag("table", "name"), "")
        row_index = 0
        for row in table.iter(_tag("table", "table-row")):
            row_repeat = int(row.attrib.get(_tag("table", "number-rows-repeated"), "1"))
            col_index = 0
            for cell in list(row):
                if cell.tag not in (_tag("table", "table-cell"), _tag("table", "covered-table-cell")):
                    continue
                col_repeat = int(cell.attrib.get(_tag("table", "number-columns-repeated"), "1"))
                formula = cell.attrib.get(_tag("table", "formula"))
                if formula:
                    for dr in range(row_repeat):
                        for dc in range(col_repeat):
                            coordinate = f"{_column_name(col_index + dc + 1)}{row_index + dr + 1}"
                            found[(sheet, coordinate)] = formula
                col_index += col_repeat
            row_index += row_repeat
    return found


def _expected_values() -> dict[str, list[list[object]]]:
    result: dict[str, list[list[object]]] = {}
    for sheet, rows in gold_sheets().items():
        result[sheet] = [[cell.value if isinstance(cell, FormulaValue) else cell for cell in row]
                         for row in rows]
    return result


def _expected_formulas() -> dict[tuple[str, str], str]:
    formulas: dict[tuple[str, str], str] = {}
    for sheet, rows in gold_sheets().items():
        for row_num, row in enumerate(rows, start=1):
            for col_num, cell in enumerate(row, start=1):
                if isinstance(cell, FormulaValue):
                    formulas[(sheet, f"{_column_name(col_num)}{row_num}")] = normalize_formula(cell.formula)
    return formulas


def evaluate(workbook_path: str | Path, initial_path: str | Path | None = None) -> dict[str, object]:
    """Check forecast, purchasing, budget, formulas, and protected source state."""
    path = Path(workbook_path)
    checks: dict[str, bool] = {"real_ods_container": is_real_ods(path)}
    if not checks["real_ods_container"]:
        return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
                "checks": checks, "joint_success": False, "errors": ["not a valid ODS container"]}
    try:
        actual = read_ods(path)
        formula_actual = {key: normalize_formula(value) for key, value in read_ods_formulas(path).items()}
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
                "checks": checks, "joint_success": False, "errors": [f"unreadable ODS: {exc}"]}

    expected = _expected_values()
    checks["sheet_set_exact"] = set(actual) == set(expected)
    for sheet in ("Sales", "Inventory", "Rules"):
        checks[f"protected_source:{sheet}"] = sheet in actual and _content_equal(actual.get(sheet), expected[sheet])
    if initial_path is not None:
        try:
            before = read_ods(initial_path)
            checks["protected_inputs_match_fixture"] = all(
                _content_equal(before.get(name), actual.get(name)) for name in ("Sales", "Inventory", "Rules"))
        except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError):
            checks["protected_inputs_match_fixture"] = False

    for sheet in ("Forecast", "Replenishment", "Budget"):
        checks[f"gold_values:{sheet}"] = sheet in actual and _content_equal(actual.get(sheet), expected[sheet])
    formula_expected = _expected_formulas()
    checks["formula_locations_and_semantics"] = formula_actual == formula_expected
    if formula_actual != formula_expected:
        checks["formula_diff"] = {
            "missing_or_changed": {f"{s}!{c}": expected_formula
                                   for (s, c), expected_formula in formula_expected.items()
                                   if formula_actual.get((s, c)) != expected_formula},
            "unexpected": {f"{s}!{c}": value for (s, c), value in formula_actual.items()
                           if (s, c) not in formula_expected},
        }
    # Cross-role consistency is explicit: B's order inputs must be A's net
    # requirements, and each A row must be marked reviewed after the B plan.
    forecast_rows = actual.get("Forecast", [])[1:5]
    order_rows = actual.get("Replenishment", [])[1:5]
    checks["A_B_sku_order_alignment"] = (
        len(forecast_rows) == len(order_rows) == len(spec.SALES)
        and all(len(f) > 12 and len(o) > 1 and f[0] == o[0] and _numeric_equal(f[12], o[1])
                for f, o in zip(forecast_rows, order_rows)))
    checks["A_final_review_present"] = (
        len(forecast_rows) == len(spec.SALES)
        and all(len(row) > 14 and row[14] == "REVIEWED" for row in forecast_rows))
    budget_rows = actual.get("Budget", [])
    checks["budget_within_cap"] = (
        len(budget_rows) > 4 and len(budget_rows[3]) > 1
        and _numeric_equal(budget_rows[3][1], spec.GOLD_TOTAL)
        and spec.GOLD_TOTAL <= spec.BUDGET_CAP)
    errors = [name for name, passed in checks.items() if name != "formula_diff" and passed is not True]
    return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
            "actors": {"A": {"success": all(checks.get(k, False) for k in checks
                                                   if k.startswith(("protected_", "gold_values:Forecast", "A_final_review")))},
                        "B": {"success": all(checks.get(k, False) for k in checks
                                                   if k.startswith(("gold_values:Replenishment", "gold_values:Budget", "formula_", "budget_"))) }},
            "checks": checks, "joint_success": not errors, "errors": errors,
            "inference_boundary": "static Oracle result; does not establish GUI, collaboration, exposure, or recovery"}

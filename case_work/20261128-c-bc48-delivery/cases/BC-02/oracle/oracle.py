"""Host-side offline Oracle for BC-02. Never copy this directory into the Guest."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
import shutil
import subprocess
import sys
import zipfile
import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree as ET

from pipeline.grade import make_grade

# Private evaluator targets. Do not mirror this module into Guest assets.
HISTORY = [
    ["Q4-4101", "2026-10-02", "Atlas Labs", "East", 10000.0, "Closed"],
    ["Q4-4102", "2026-10-05", "Meridian Health", "West", 12400.0, "Closed"],
    ["Q4-4103", "2026-10-09", "Pinecone Studio", "Central", 8900.0, "Closed"],
    ["Q4-4104", "2026-10-12", "Redwood Systems", "East", 15600.0, "Closed"],
]
NEW_ORDERS = [
    ["Q4-5101", "2026-10-21", "Northstar Bio", "East", 14800.0, "Closed"],
    ["Q4-5102", "2026-10-22", "Meridian Health", "West", 9750.0, "Closed"],
    ["Q4-5103", "2026-10-23", "Pinecone Studio", "Central", 21600.0, "Closed"],
    ["Q4-5104", "2026-10-24", "Redwood Systems", "East", 12350.0, "Closed"],
    ["Q4-5105", "2026-10-25", "Blue Harbor", "West", 18750.0, "Closed"],
]
EXPENSE_ROWS = [
    ["Sales", "2026-Q4", "CC-110", 18300.0, 18900.0],
    ["Research", "2026-Q4", "CC-220", 42600.0, 41600.0],
    ["Operations", "2026-Q4", "CC-310", 21750.0, 20750.0],
    ["Support", "2026-Q4", "CC-410", 12800.0, 13200.0],
    ["Security", "2026-Q4", "CC-520", 15300.0, 14800.0],
]
TARGET_COSTS = [18300.0, 42600.0, 21750.0, 12800.0, 15300.0]

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS = {"m": _MAIN, "r": _REL, "p": _PKG_REL}


@dataclass
class WorkbookData:
    sheets: dict[str, dict[str, object]]
    formulas: dict[str, dict[str, str]]
    print_areas: dict[str, str]
    page_setup: dict[str, dict[str, str]]


def normalize_formula(formula: str) -> str:
    value = formula.strip().lstrip("=").upper()
    value = re.sub(r"\s+", "", value).replace("$", "")
    return value.replace("[.", "").replace("]", "").replace(".", "!")


def read_workbook(path: str | Path) -> WorkbookData:
    """Parse only the OOXML parts needed by this host-side Oracle."""
    with zipfile.ZipFile(path, "r") as archive:
        try:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(node.itertext()) for node in shared_root.findall("m:si", _NS)]
        except KeyError:
            shared_strings = []
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {node.attrib["Id"]: node.attrib["Target"] for node in rel_root}
        date_styles = set()
        try:
            styles = ET.fromstring(archive.read('xl/styles.xml'))
            formats = {int(x.get('numFmtId')): x.get('formatCode','') for x in styles.findall('m:numFmts/m:numFmt',_NS)}
            for i,x in enumerate(styles.findall('m:cellXfs/m:xf',_NS)):
                fid = int(x.get('numFmtId','0'))
                fmt = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]', '', formats.get(fid,'')).lower()
                if fid in set(range(14,23)) or re.search(r'[yd]',fmt):date_styles.add(i)
        except KeyError:
            pass
        epoch = datetime(1904,1,1) if (root.find('m:workbookPr',_NS) is not None and root.find('m:workbookPr',_NS).get('date1904') in ('1','true')) else datetime(1899,12,30)
        sheets: dict[str, dict[str, object]] = {}
        formulas: dict[str, dict[str, str]] = {}
        page_setup: dict[str, dict[str, str]] = {}
        for sheet in root.findall("m:sheets/m:sheet", _NS):
            name = sheet.attrib["name"]
            target = targets[sheet.attrib[f"{{{_REL}}}id"]]
            xml_path = target if target.startswith("xl/") else "xl/" + target
            sheet_root = ET.fromstring(archive.read(xml_path))
            values: dict[str, object] = {}
            form_map: dict[str, str] = {}
            for cell in sheet_root.findall(".//m:c", _NS):
                ref, kind = cell.attrib["r"], cell.attrib.get("t", "")
                value_node = cell.find("m:v", _NS)
                value: object = value_node.text if value_node is not None and value_node.text is not None else None
                if kind == "inlineStr":
                    inline = cell.find("m:is", _NS)
                    value = "".join(inline.itertext()) if inline is not None else ""
                elif kind == "s" and value is not None:
                    value = shared_strings[int(value)]
                elif value is not None and kind != "s":
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                if isinstance(value,(int,float)) and int(cell.get('s','0')) in date_styles:
                    value = (epoch + timedelta(days=value)).date().isoformat()
                values[ref] = value
                formula_node = cell.find("m:f", _NS)
                if formula_node is not None:
                    form_map[ref] = formula_node.text or ""
            sheets[name] = values
            formulas[name] = form_map
            setup_node = sheet_root.find("m:pageSetup", _NS)
            page_setup[name] = dict(setup_node.attrib) if setup_node is not None else {}
        print_areas: dict[str, str] = {}
        defined = root.find("m:definedNames", _NS)
        if defined is not None:
            for node in defined.findall("m:definedName", _NS):
                if node.attrib.get("name") == "_xlnm.Print_Area":
                    print_areas[node.attrib.get("localSheetId", "")] = node.text or ""
    return WorkbookData(sheets, formulas, print_areas, page_setup)


def _check(check_id: str, weight: float, passed: bool, evidence, *, required: bool = True, score: float | None = None):
    return {
        "id": check_id, "weight": weight, "passed": bool(passed),
        "score": float(bool(passed)) if score is None else max(0.0, min(1.0, float(score))),
        "required": required, "evidence": evidence,
    }


def _number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_number(actual, expected: float, tolerance: float = 0.01) -> bool:
    number = _number(actual)
    return number is not None and math.isclose(number, expected, abs_tol=tolerance, rel_tol=0.0)


def _formula(data: WorkbookData, sheet: str, cell: str) -> str:
    return normalize_formula(data.formulas.get(sheet, {}).get(cell, ""))


def extract_pdf_text(path: Path) -> str:
    exe = shutil.which("pdftotext")
    if exe:
        result = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, check=True, timeout=20)
        return result.stdout.decode("utf-8", "replace")
    try:
        import fitz
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except ImportError as exc:
        raise RuntimeError("No PDF text extractor is available to the host-side Oracle.") from exc


def _pdf(path: Path, required_text: list[str], text_reader: Callable[[Path], str]) -> tuple[bool, dict]:
    try:
        raw = path.read_bytes()
        if not raw.startswith(b"%PDF-") or len(raw) < 80:
            return False, {"exists": True, "valid_pdf_signature": False}
        text = text_reader(path)
        def contains(token):
            # Compare complete numeric tokens, not substrings: honor currency grouping
            # and percent rounding without changing the required monetary value.
            if re.fullmatch(r'\d+(?:\.\d+)?%?',token):
                percent = token.endswith('%'); want=float(token.rstrip('%'))
                for m in re.finditer(r'(?<![\w.])([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(\s*%)?(?![\w.])',text):
                    if bool(m.group(2)) != percent:continue
                    if math.isclose(float(m.group(1).replace(',','')),want,abs_tol=.051 if percent else .005,rel_tol=0):return True
                return False
            return token.casefold() in text.casefold()
        missing = [token for token in required_text if not contains(token)]
        return not missing, {"exists": True, "bytes": len(raw), "missing_text": missing}
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return False, {"exists": path.exists(), "error": type(exc).__name__}


def _load(path: Path) -> tuple[WorkbookData | None, str | None]:
    try:
        return read_workbook(path), None
    except (OSError, ValueError, KeyError, Exception) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:180]}"


def grade_case(workspace: str | Path, run_id: str = "offline", pdf_text_reader: Callable[[Path], str] | None = None) -> dict:
    workspace = Path(workspace)
    workbook_path = workspace / "q4_ops.xlsx"
    revenue_pdf = workspace / "revenue_summary.pdf"
    expense_pdf = workspace / "expense_summary.pdf"
    pdf_text_reader = pdf_text_reader or extract_pdf_text
    data, parse_error = _load(workbook_path)
    sheets = data.sheets if data else {}

    actor_a = []
    for index, row_number in enumerate(range(6, 11), 1):
        expected = NEW_ORDERS[index - 1]
        cells = [sheets.get("Revenue", {}).get(f"{col}{row_number}") for col in "ABCDEF"]
        matches = (
            cells[0] == expected[0] and cells[1] == expected[1] and cells[2] == expected[2]
            and cells[3] == expected[3] and _same_number(cells[4], expected[4]) and cells[5] == expected[5]
        )
        actor_a.append(_check(f"A{index:02d}", 0.10, matches, {"row": row_number, "values": cells}))
    a_formula_ok = (
        _formula(data, "Summary", "B2") in {"SUM(REVENUE!E2:E10)", "SUM(REVENUE.E2:E10)"}
        and _formula(data, "Summary", "B3") in {'COUNTIF(REVENUE!F2:F10,"CLOSED")', 'COUNTIF(REVENUE.F2:F10,"CLOSED")'}
        and _formula(data, "Summary", "B4") in {"AVERAGE(REVENUE!E2:E10)", "AVERAGE(REVENUE.E2:E10)"}
        if data else False
    )
    a_formula_values = (
        _same_number(sheets.get("Summary", {}).get("B2"), 124150.0)
        and _same_number(sheets.get("Summary", {}).get("B3"), 9)
        and _same_number(sheets.get("Summary", {}).get("B4"), 124150.0 / 9)
    )
    actor_a.append(_check("A06", 0.15, a_formula_ok and a_formula_values, {"formula_ok": a_formula_ok, "values_ok": a_formula_values}))
    a_pdf_ok, a_pdf_evidence = _pdf(revenue_pdf, ["Q4 Revenue Summary", "124150"], pdf_text_reader)
    actor_a.append(_check("A07", 0.15, a_pdf_ok, a_pdf_evidence))
    a_structure = data is not None and set(data.sheets) == {"Revenue", "Expenses", "Summary", "Control"}
    a_history_ok = all(
        sheets.get("Revenue", {}).get(f"{col}{row}") == value
        for row, values in enumerate(HISTORY, 2)
        for col, value in zip("ABCDEF", values)
    ) if data else False
    actor_a.append(_check("A08", 0.10, workbook_path.is_file() and a_structure and a_history_ok, {"exists": workbook_path.is_file(), "parse_error": parse_error, "sheets": sorted(sheets)}))
    summary_area = data.print_areas.get("2", "") if data else ""
    a_layout_score = 1.0 if "SUMMARY" in summary_area.upper() and "$A$1:$C$8" in summary_area.upper() else 0.0
    actor_a.append(_check("A09", 0.10, a_layout_score == 1.0, {"print_area": summary_area}, required=False, score=a_layout_score))

    actor_b = []
    cost_rows = [sheets.get("Expenses", {}).get(f"E{row}") for row in range(2, 7)]
    for index, (row_number, expected) in enumerate(zip(range(2, 7), TARGET_COSTS), 1):
        match = _same_number(cost_rows[index - 1], expected)
        actor_b.append(_check(f"B{index:02d}", 0.10, match, {"row": row_number, "approved_cost_usd": cost_rows[index - 1]}))
    expected_formula = [
        normalize_formula(f"E{row}/SUM($E$2:$E$6)") for row in range(2, 7)
    ]
    actual_formulas = [_formula(data, "Expenses", f"F{row}") for row in range(2, 7)] if data else []
    formulas_ok = actual_formulas == expected_formula
    shares = [_number(sheets.get("Expenses", {}).get(f"F{row}")) for row in range(2, 7)]
    shares_ok = all(value is not None for value in shares) and math.isclose(sum(shares or []), 1.0, abs_tol=0.001)
    actor_b.append(_check("B06", 0.20, formulas_ok and shares_ok, {"formulas_ok": formulas_ok, "shares": shares, "sum": sum(shares) if all(x is not None for x in shares) else None}))
    expense_pdf_ok, expense_pdf_evidence = _pdf(
        expense_pdf,
        ["Sales", "Research", "Operations", "Support", "Security", "18300", "42600", "21750", "12800", "15300", "16.5%", "38.5%", "19.6%", "11.6%", "13.8%"],
        pdf_text_reader,
    )
    actor_b.append(_check("B07", 0.15, expense_pdf_ok, expense_pdf_evidence))
    expense_structure_ok = (
        data is not None and set(data.sheets) == {"Revenue", "Expenses", "Summary", "Control"}
        and all(sheets.get("Expenses", {}).get(f"{col}{row}") == value
                for row, values in enumerate(EXPENSE_ROWS, 2)
                for col, value in zip("ABCD", values[:4]))
    )
    actor_b.append(_check("B08", 0.10, expense_structure_ok, {"parse_error": parse_error, "source_columns_preserved": expense_structure_ok}))
    expense_area = data.print_areas.get("1", "") if data else ""
    b_layout_score = 1.0 if "EXPENSES" in expense_area.upper() and "$A$1:$F$8" in expense_area.upper() else 0.0
    actor_b.append(_check("B09", 0.05, b_layout_score == 1.0, {"print_area": expense_area}, required=False, score=b_layout_score))

    all_revenue = all(
        sheets.get("Revenue", {}).get(f"{col}{row}") == value
        for row, values in enumerate(HISTORY + NEW_ORDERS, 2)
        for col, value in zip("ABCDEF", values)
    ) if data else False
    all_costs = all(_same_number(sheets.get("Expenses", {}).get(f"E{row}"), expected) for row, expected in zip(range(2, 7), TARGET_COSTS)) if data else False
    control_ok = (
        _formula(data, "Control", "B2") in {"SUMMARY!B2", "SUMMARY.B2"}
        and _formula(data, "Control", "B3") in {"SUM(EXPENSES!E2:E6)", "SUM(EXPENSES.E2:E6)"}
        and _formula(data, "Control", "B4") == "B2-B3"
        and _same_number(sheets.get("Control", {}).get("B2"), 124150.0)
        and _same_number(sheets.get("Control", {}).get("B3"), 110750.0)
        and _same_number(sheets.get("Control", {}).get("B4"), 13400.0)
    ) if data else False
    j03 = a_pdf_ok and expense_pdf_ok
    j04 = data is not None and a_history_ok and expense_structure_ok
    joint = [
        _check("J01", 1.0, all_revenue and all_costs, {"all_revenue_rows": all_revenue, "all_expense_costs": all_costs}),
        _check("J02", 1.0, control_ok, {"control_chain_ok": control_ok}),
        _check("J03", 1.0, j03, {"revenue_pdf_ok": a_pdf_ok, "expense_pdf_ok": expense_pdf_ok}),
        _check("J04", 1.0, j04, {"history_and_source_fields_preserved": j04, "parse_error": parse_error}),
    ]
    reasons = [f"Workbook could not be parsed: {parse_error}"] if parse_error else []
    return make_grade(
        case_id="BC-02", run_id=run_id, actor_a_checks=actor_a, actor_b_checks=actor_b,
        joint_checks=joint, pass_threshold_a=0.80, pass_threshold_b=0.80,
        failure_reasons=reasons,
        run_metadata={"oracle": "BC-02 offline deterministic", "workspace": str(workspace), "pdf_extractor": getattr(pdf_text_reader, "__name__", "injected")},
    )


def grade_episode(snapshot_root: Path, receipt: dict, run_id: str) -> dict:
    """Pipeline adapter for deliverables recovered into guest-output/."""
    return grade_case(snapshot_root.parent / "guest-output", run_id=run_id)

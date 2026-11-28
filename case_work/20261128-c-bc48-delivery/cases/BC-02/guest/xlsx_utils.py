"""Small standard-library OOXML helpers for the BC-02 starter workbook."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"m": MAIN, "r": REL, "p": PKG_REL}
ET.register_namespace("", MAIN)
ET.register_namespace("r", REL)

REVENUE_HEADERS = ["order_id", "order_date", "customer", "region", "revenue_usd", "status"]
EXPENSE_HEADERS = ["department", "month", "cost_center", "voucher_total_usd", "approved_cost_usd", "share_of_total"]
HISTORY = [
    ["Q4-4101", "2026-10-02", "Atlas Labs", "East", 10000.0, "Closed"],
    ["Q4-4102", "2026-10-05", "Meridian Health", "West", 12400.0, "Closed"],
    ["Q4-4103", "2026-10-09", "Pinecone Studio", "Central", 8900.0, "Closed"],
    ["Q4-4104", "2026-10-12", "Redwood Systems", "East", 15600.0, "Closed"],
]
EXPENSE_ROWS = [
    ["Sales", "2026-Q4", "CC-110", 18300.0, 18900.0],
    ["Research", "2026-Q4", "CC-220", 42600.0, 41600.0],
    ["Operations", "2026-Q4", "CC-310", 21750.0, 20750.0],
    ["Support", "2026-Q4", "CC-410", 12800.0, 13200.0],
    ["Security", "2026-Q4", "CC-520", 15300.0, 14800.0],
]


def q(tag: str) -> str:
    return f"{{{MAIN}}}{tag}"


def _cell(ref: str, value=None, *, formula: str | None = None, style: int = 0) -> ET.Element:
    attrs = {"r": ref}
    if style:
        attrs["s"] = str(style)
    cell = ET.Element(q("c"), attrs)
    if formula is not None:
        ET.SubElement(cell, q("f")).text = formula
        ET.SubElement(cell, q("v")).text = "" if value is None else str(value)
    elif isinstance(value, str):
        cell.set("t", "inlineStr")
        inline = ET.SubElement(cell, q("is"))
        text = ET.SubElement(inline, q("t"))
        if value[:1].isspace() or value[-1:].isspace():
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text.text = value
    elif value is not None:
        ET.SubElement(cell, q("v")).text = str(value)
    return cell


def _sheet(rows: list[list], formulas: dict[str, tuple[str, object]] | None = None, *, cols: list[tuple[int, int, float]] | None = None, page_setup: bool = False) -> bytes:
    root = ET.Element(q("worksheet"))
    ET.SubElement(root, q("sheetPr")).append(ET.Element(q("pageSetUpPr"), {"fitToPage": "1"}))
    ET.SubElement(root, q("dimension"), {"ref": "A1:F10"})
    ET.SubElement(root, q("sheetViews")).append(ET.Element(q("sheetView"), {"workbookViewId": "0", "showGridLines": "1"}))
    ET.SubElement(root, q("sheetFormatPr"), {"defaultRowHeight": "18"})
    if cols:
        columns = ET.SubElement(root, q("cols"))
        for first, last, width in cols:
            ET.SubElement(columns, q("col"), {"min": str(first), "max": str(last), "width": str(width), "customWidth": "1"})
    data = ET.SubElement(root, q("sheetData"))
    formulas = formulas or {}
    for row_number, values in enumerate(rows, 1):
        row = ET.SubElement(data, q("row"), {"r": str(row_number)})
        for column_number, value in enumerate(values, 1):
            ref = f"{_column(column_number)}{row_number}"
            if ref in formulas:
                form, cached = formulas[ref]
                style = 3 if ref[0] == "F" else (2 if ref[0] in "BCE" else 0)
                row.append(_cell(ref, cached, formula=form, style=style))
            elif value is not None:
                style = 1 if row_number == 1 else (2 if isinstance(value, (int, float)) else 0)
                row.append(_cell(ref, value, style=style))
    if page_setup:
        ET.SubElement(root, q("printOptions"), {"horizontalCentered": "1"})
        ET.SubElement(root, q("pageMargins"), {"left": "0.25", "right": "0.25", "top": "0.4", "bottom": "0.4", "header": "0.2", "footer": "0.2"})
        ET.SubElement(root, q("pageSetup"), {"orientation": "landscape", "paperSize": "1", "fitToWidth": "1", "fitToHeight": "1"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _column(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _styles() -> bytes:
    root = ET.Element(q("styleSheet"))
    fonts = ET.SubElement(root, q("fonts"), {"count": "2"})
    ET.SubElement(fonts, q("font"))
    bold = ET.SubElement(fonts, q("font"))
    ET.SubElement(bold, q("b"))
    fills = ET.SubElement(root, q("fills"), {"count": "2"})
    ET.SubElement(fills, q("fill")).append(ET.Element(q("patternFill"), {"patternType": "none"}))
    fill = ET.SubElement(fills, q("fill"))
    pattern = ET.SubElement(fill, q("patternFill"), {"patternType": "solid"})
    ET.SubElement(pattern, q("fgColor"), {"rgb": "FFDCE6F1"})
    ET.SubElement(pattern, q("bgColor"), {"indexed": "64"})
    borders = ET.SubElement(root, q("borders"), {"count": "1"})
    ET.SubElement(borders, q("border"))
    numfmts = ET.SubElement(root, q("numFmts"), {"count": "2"})
    ET.SubElement(numfmts, q("numFmt"), {"numFmtId": "164", "formatCode": "$#,##0.00"})
    ET.SubElement(numfmts, q("numFmt"), {"numFmtId": "165", "formatCode": "0.0%"})
    style_xfs = ET.SubElement(root, q("cellStyleXfs"), {"count": "1"})
    ET.SubElement(style_xfs, q("xf"), {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"})
    xfs = ET.SubElement(root, q("cellXfs"), {"count": "4"})
    ET.SubElement(xfs, q("xf"), {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0", "xfId": "0"})
    ET.SubElement(xfs, q("xf"), {"numFmtId": "0", "fontId": "1", "fillId": "1", "borderId": "0", "xfId": "0", "applyFont": "1", "applyFill": "1"})
    ET.SubElement(xfs, q("xf"), {"numFmtId": "164", "fontId": "0", "fillId": "0", "borderId": "0", "xfId": "0", "applyNumberFormat": "1"})
    ET.SubElement(xfs, q("xf"), {"numFmtId": "165", "fontId": "0", "fillId": "0", "borderId": "0", "xfId": "0", "applyNumberFormat": "1"})
    styles = ET.SubElement(root, q("cellStyles"), {"count": "1"})
    ET.SubElement(styles, q("cellStyle"), {"name": "Normal", "xfId": "0", "builtinId": "0"})
    ET.SubElement(root, q("dxfs"), {"count": "0"})
    ET.SubElement(root, q("tableStyles"), {"count": "0", "defaultTableStyle": "TableStyleMedium2", "defaultPivotStyle": "PivotStyleLight16"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_workbook(
    path: str | Path,
    *,
    revenue_rows: list[list] | None = None,
    expense_costs: list[float] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    revenue = [REVENUE_HEADERS, *[list(row) for row in HISTORY]]
    revenue_rows = [list(row) for row in (revenue_rows or [])]
    if any(len(row) != 6 for row in revenue_rows):
        raise ValueError("Revenue rows must contain the six Revenue columns")
    revenue.extend(revenue_rows)
    costs = list(expense_costs) if expense_costs is not None else [float(row[4]) for row in EXPENSE_ROWS]
    if len(costs) != len(EXPENSE_ROWS):
        raise ValueError(f"Expected {len(EXPENSE_ROWS)} expense costs")
    summary = [
        ["Q4 Revenue Summary", None, None],
        ["Total Revenue", None, "USD"],
        ["Closed Orders", None, "Orders"],
        ["Average Order Value", None, "USD"],
    ]
    all_revenue_rows = HISTORY + revenue_rows
    total_revenue = sum(float(row[4]) for row in all_revenue_rows)
    closed_count = sum(1 for row in all_revenue_rows if str(row[5]).casefold() == "closed")
    summary_formulas = {
        "B2": ("SUM(Revenue!E2:E10)", total_revenue),
        "B3": ('COUNTIF(Revenue!F2:F10,"Closed")', closed_count),
        "B4": ("AVERAGE(Revenue!E2:E10)", round(total_revenue / closed_count, 8) if closed_count else 0),
    }
    expenses = [EXPENSE_HEADERS]
    for i, row in enumerate(EXPENSE_ROWS):
        expenses.append([*row[:4], costs[i], None])
    expense_formulas = {}
    if expense_costs is not None:
        for row_number, cost in enumerate(costs, 2):
            expense_formulas[f"F{row_number}"] = (f"E{row_number}/SUM($E$2:$E$6)", round(cost / sum(costs), 10))
    expense_total = sum(costs)
    control = [
        ["Control Check", "Value"],
        ["Revenue Total", None],
        ["Approved Expense Total", None],
        ["Revenue Less Approved Expenses", None],
    ]
    control_formulas = {
        "B2": ("Summary!B2", total_revenue),
        "B3": ("SUM(Expenses!E2:E6)", expense_total),
        "B4": ("B2-B3", total_revenue - expense_total),
    }
    sheets = {
        "xl/worksheets/sheet1.xml": _sheet(revenue, cols=[(1, 1, 15), (2, 2, 14), (3, 3, 23), (4, 4, 14), (5, 5, 18), (6, 6, 12)]),
        "xl/worksheets/sheet2.xml": _sheet(expenses, expense_formulas, cols=[(1, 1, 18), (2, 2, 14), (3, 3, 14), (4, 6, 21)], page_setup=True),
        "xl/worksheets/sheet3.xml": _sheet(summary, summary_formulas, cols=[(1, 1, 32), (2, 2, 21), (3, 3, 18)], page_setup=True),
        "xl/worksheets/sheet4.xml": _sheet(control, control_formulas, cols=[(1, 1, 30), (2, 2, 22)]),
    }
    workbook = ET.Element(q("workbook"))
    ET.SubElement(workbook, q("bookViews")).append(ET.Element(q("workbookView"), {"activeTab": "2"}))
    sheet_list = ET.SubElement(workbook, q("sheets"))
    names = ["Revenue", "Expenses", "Summary", "Control"]
    for i, name in enumerate(names, 1):
        ET.SubElement(sheet_list, q("sheet"), {"name": name, "sheetId": str(i), f"{{{REL}}}id": f"rId{i}"})
    defined = ET.SubElement(workbook, q("definedNames"))
    ET.SubElement(defined, q("definedName"), {"name": "_xlnm.Print_Area", "localSheetId": "1"}).text = "'Expenses'!$A$1:$F$8"
    ET.SubElement(defined, q("definedName"), {"name": "_xlnm.Print_Area", "localSheetId": "2"}).text = "'Summary'!$A$1:$C$8"
    ET.SubElement(workbook, q("calcPr"), {"calcMode": "auto", "fullCalcOnLoad": "1", "forceFullCalc": "1"})
    rels = ET.Element(f"{{{PKG_REL}}}Relationships")
    for i in range(1, 5):
        ET.SubElement(rels, f"{{{PKG_REL}}}Relationship", {"Id": f"rId{i}", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", "Target": f"worksheets/sheet{i}.xml"})
    ET.SubElement(rels, f"{{{PKG_REL}}}Relationship", {"Id": "rId5", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "Target": "styles.xml"})
    content = ET.Element(f"{{{CONTENT}}}Types")
    ET.SubElement(content, f"{{{CONTENT}}}Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(content, f"{{{CONTENT}}}Default", {"Extension": "xml", "ContentType": "application/xml"})
    ET.SubElement(content, f"{{{CONTENT}}}Override", {"PartName": "/xl/workbook.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"})
    ET.SubElement(content, f"{{{CONTENT}}}Override", {"PartName": "/xl/styles.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"})
    for i in range(1, 5):
        ET.SubElement(content, f"{{{CONTENT}}}Override", {"PartName": f"/xl/worksheets/sheet{i}.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"})
    root_rels = ET.Element(f"{{{PKG_REL}}}Relationships")
    ET.SubElement(root_rels, f"{{{PKG_REL}}}Relationship", {"Id": "rId1", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "Target": "xl/workbook.xml"})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", ET.tostring(content, encoding="utf-8", xml_declaration=True))
        archive.writestr("_rels/.rels", ET.tostring(root_rels, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/workbook.xml", ET.tostring(workbook, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/_rels/workbook.xml.rels", ET.tostring(rels, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/styles.xml", _styles())
        for name, data in sheets.items():
            archive.writestr(name, data)
    return path


@dataclass
class WorkbookData:
    sheets: dict[str, dict[str, object]]
    formulas: dict[str, dict[str, str]]
    print_areas: dict[str, str]
    page_setup: dict[str, dict[str, str]]


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.itertext()) for node in root.findall("m:si", NS)]


def read_workbook(path: str | Path) -> WorkbookData:
    with zipfile.ZipFile(path, "r") as archive:
        shared = _shared_strings(archive)
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {node.attrib["Id"]: node.attrib["Target"] for node in rel_root}
        sheets: dict[str, dict[str, object]] = {}
        formulas: dict[str, dict[str, str]] = {}
        page_setup: dict[str, dict[str, str]] = {}
        for sheet in root.findall("m:sheets/m:sheet", NS):
            name = sheet.attrib["name"]
            target = targets[sheet.attrib[f"{{{REL}}}id"]]
            xml_path = target if target.startswith("xl/") else "xl/" + target
            sheet_root = ET.fromstring(archive.read(xml_path))
            values: dict[str, object] = {}
            form_map: dict[str, str] = {}
            for cell in sheet_root.findall(".//m:c", NS):
                ref, kind = cell.attrib["r"], cell.attrib.get("t", "")
                formula_node = cell.find("m:f", NS)
                value_node = cell.find("m:v", NS)
                value: object = value_node.text if value_node is not None and value_node.text is not None else None
                if kind == "inlineStr":
                    inline = cell.find("m:is", NS)
                    value = "".join(inline.itertext()) if inline is not None else ""
                elif kind == "s" and value is not None:
                    value = shared[int(value)]
                elif kind == "b" and value is not None:
                    value = value == "1"
                elif value is not None:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                values[ref] = value
                if formula_node is not None:
                    form_map[ref] = formula_node.text or ""
            sheets[name] = values
            formulas[name] = form_map
            setup_node = sheet_root.find("m:pageSetup", NS)
            page_setup[name] = dict(setup_node.attrib) if setup_node is not None else {}
        print_areas = {}
        defined = root.find("m:definedNames", NS)
        if defined is not None:
            for node in defined.findall("m:definedName", NS):
                if node.attrib.get("name") == "_xlnm.Print_Area":
                    print_areas[node.attrib.get("localSheetId", "")] = node.text or ""
    return WorkbookData(sheets, formulas, print_areas, page_setup)


def normalize_formula(formula: str) -> str:
    value = formula.strip().lstrip("=").upper()
    value = re.sub(r"\s+", "", value).replace("$", "")
    value = value.replace("[.", "").replace("]", "")
    value = value.replace(".", "!")
    return value

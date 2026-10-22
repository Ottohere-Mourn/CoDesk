"""Deterministic real ODS fixtures for Spreadsheet Handoff."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from oscombo.collab.data_to_deck.fixtures import NS, _manifest_xml, _write_odf

from . import CASE_ID, CASE_VERSION
from . import spec


@dataclass(frozen=True)
class FormulaValue:
    formula: str
    value: float


def _cell(value: object) -> str:
    if isinstance(value, FormulaValue):
        formula = escape(value.formula, {'"': "&quot;"})
        shown = format(value.value, ".15g")
        return (f'<table:table-cell office:value-type="float" office:value="{shown}" '
                f'table:formula="{formula}"><text:p>{shown}</text:p></table:table-cell>')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        shown = format(value, ".15g")
        return (f'<table:table-cell office:value-type="float" office:value="{shown}">'
                f'<text:p>{shown}</text:p></table:table-cell>')
    return (f'<table:table-cell office:value-type="string"><text:p>{escape(str(value))}'
            '</text:p></table:table-cell>')


def _write_workbook(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    tables = []
    for name, rows in sheets.items():
        row_xml = "".join("<table:table-row>" + "".join(_cell(value) for value in row)
                          + "</table:table-row>" for row in rows)
        tables.append(f'<table:table table:name="{escape(name)}">{row_xml}</table:table>')
    content = (f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="{NS['office']}" xmlns:table="{NS['table']}"
 xmlns:text="{NS['text']}" xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2"
 office:version="1.2"><office:body><office:spreadsheet>{''.join(tables)}
 </office:spreadsheet></office:body></office:document-content>''').encode()
    common = (f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="{NS['office']}" xmlns:style="{NS['style']}"
 office:version="1.2"><office:styles/></office:document-styles>''').encode()
    mimetype = "application/vnd.oasis.opendocument.spreadsheet"
    _write_odf(path, mimetype, {
        "content.xml": content, "styles.xml": common,
        "meta.xml": (f'''<?xml version="1.0"?><office:document-meta xmlns:office="{NS['office']}"
 office:version="1.2"><office:meta/></office:document-meta>''').encode(),
        "settings.xml": (f'''<?xml version="1.0"?><office:document-settings xmlns:office="{NS['office']}"
 office:version="1.2"><office:settings/></office:document-settings>''').encode(),
        "META-INF/manifest.xml": _manifest_xml(mimetype, "content.xml"),
    })


def source_sheets() -> dict[str, list[list[object]]]:
    return {
        "Sales": [["SKU", "Month_1", "Month_2", "Month_3"], *[list(row) for row in spec.SALES]],
        "Inventory": [["SKU", "On_Hand", "Inbound", "Safety_Stock", "Case_Pack", "Unit_Cost_USD"],
                      *[list(row) for row in spec.INVENTORY]],
        "Rules": [["Rule", "Value", "Notes"],
                  ["Forecast_Horizon_Months", spec.HORIZON_MONTHS, "Next two months"],
                  ["Freight_USD", spec.FREIGHT, "Fixed per purchase order"],
                  ["Budget_Cap_USD", spec.BUDGET_CAP, "Do not exceed including freight"],
                  ["Average_Demand", "Arithmetic mean", "Mean of the three complete sales months"],
                  ["Order_Rounding", "Round up by Case_Pack", "Zero net requirement remains zero"]],
    }


def initial_sheets() -> dict[str, list[list[object]]]:
    sheets = source_sheets()
    sheets["Forecast"] = [["SKU", "Month_1", "Month_2", "Month_3", "Avg_Monthly",
                           "Horizon_Months", "Forecast_Units", "Safety_Stock", "Target_Stock",
                           "On_Hand", "Inbound", "Available_Stock", "Net_Requirement",
                           "Evidence", "A_Review"]]
    for sku, m1, m2, m3 in spec.SALES:
        sheets["Forecast"].append([sku, m1, m2, m3, "", spec.HORIZON_MONTHS, "", "", "", "", "", "", "",
                                    f"Sales row for {sku}; Inventory row for stock figures", "PENDING"])
    sheets["Replenishment"] = [["SKU", "Net_Requirement", "Case_Pack", "Order_Quantity",
                                "Unit_Cost_USD", "Extended_Cost_USD", "Procurement_Reason", "B_Review"]]
    sheets["Replenishment"].extend([[row[0], "", "", "", "", "", "", "PENDING"] for row in spec.INVENTORY])
    sheets["Budget"] = [["Metric", "Value", "Evidence"],
                        ["Purchase_Subtotal_USD", "", "Replenishment rows 2-5"],
                        ["Freight_USD", spec.FREIGHT, "Rules sheet"],
                        ["Total_Spend_USD", "", "Purchase subtotal plus freight"],
                        ["Budget_Cap_USD", spec.BUDGET_CAP, "Rules sheet"],
                        ["Remaining_USD", "", "Budget cap minus total spend"],
                        ["Status", "PENDING", "WITHIN_BUDGET or OVER_BUDGET"]]
    return sheets


def gold_sheets() -> dict[str, list[list[object]]]:
    sheets = source_sheets()
    forecast: list[list[object]] = [["SKU", "Month_1", "Month_2", "Month_3", "Avg_Monthly",
                                    "Horizon_Months", "Forecast_Units", "Safety_Stock", "Target_Stock",
                                    "On_Hand", "Inbound", "Available_Stock", "Net_Requirement",
                                    "Evidence", "A_Review"]]
    replenishment: list[list[object]] = [["SKU", "Net_Requirement", "Case_Pack", "Order_Quantity",
                                         "Unit_Cost_USD", "Extended_Cost_USD", "Procurement_Reason", "B_Review"]]
    for row_index, (sales, inv) in enumerate(zip(spec.SALES, spec.INVENTORY), start=2):
        sku, m1, m2, m3 = sales
        _, on_hand, inbound, safety, pack, cost = inv
        answer = spec.GOLD[sku]
        forecast.append([sku, m1, m2, m3,
                         FormulaValue(f"of:=AVERAGE([.B{row_index}:.D{row_index}])", answer["average"]),
                         spec.HORIZON_MONTHS,
                         FormulaValue(f"of:=[.E{row_index}]*[.F{row_index}]", answer["forecast"]),
                         safety,
                         FormulaValue(f"of:=[.G{row_index}]+[.H{row_index}]", answer["target"]),
                         on_hand, inbound,
                         FormulaValue(f"of:=[.J{row_index}]+[.K{row_index}]", answer["available"]),
                         FormulaValue(f"of:=MAX(0;[.I{row_index}]-[.L{row_index}])", answer["net"]),
                         f"Sales row {row_index}; Inventory row {row_index}; Rules!B2",
                         "REVIEWED"])
        replenishment.append([
            sku, answer["net"], pack,
            FormulaValue(f"of:=ROUNDUP([.B{row_index}]/[.C{row_index}];0)*[.C{row_index}]", answer["order"]),
            cost,
            FormulaValue(f"of:=[.D{row_index}]*[.E{row_index}]", answer["cost"]),
            "Case-pack rounded forecast net requirement; preserve order eligibility.", "REVIEWED"])
    forecast.append(["TOTAL", "", "", "", "", "", "", "", "", "", "", "", "", "", "REVIEWED"])
    replenishment.append(["TOTAL", "", "", "", "",
                         FormulaValue("of:=SUM([.F2:.F5])", spec.GOLD_PURCHASE_SUBTOTAL), "", "REVIEWED"])
    sheets["Forecast"] = forecast
    sheets["Replenishment"] = replenishment
    sheets["Budget"] = [["Metric", "Value", "Evidence"],
                        ["Purchase_Subtotal_USD", FormulaValue("of:=Replenishment.F6", spec.GOLD_PURCHASE_SUBTOTAL),
                         "Sum of Replenishment extended costs"],
                        ["Freight_USD", spec.FREIGHT, "Rules!B3"],
                        ["Total_Spend_USD", FormulaValue("of:=[.B2]+[.B3]", spec.GOLD_TOTAL),
                         "Purchase subtotal plus fixed freight"],
                        ["Budget_Cap_USD", spec.BUDGET_CAP, "Rules!B4"],
                        ["Remaining_USD", FormulaValue("of:=[.B5]-[.B4]", spec.GOLD_REMAINING),
                         "Budget cap minus total spend"],
                        ["Status", "WITHIN_BUDGET", "Total spend does not exceed cap"]]
    return sheets


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_fixture(output: str | Path) -> dict[str, Any]:
    root = Path(output)
    if root.exists() and (root.is_symlink() or any(root.iterdir())):
        raise FileExistsError(f"fixture output must be a new/empty owned directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    initial = root / "initial.ods"
    gold = root / "private" / "gold.ods"
    _write_workbook(initial, initial_sheets())
    _write_workbook(gold, gold_sheets())
    public_files = {"initial.ods": {"sha256": _sha256(initial), "bytes": initial.stat().st_size}}
    manifest = {"schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
                "fixture_id": "SH-RESTOCK-001", "seed": 0, "files": public_files,
                "source_sheets": ["Sales", "Inventory", "Rules"],
                "actor_outputs": {"A": "Forecast", "B": ["Replenishment", "Budget"]},
                "notes": "only initial.ods and this public manifest are in Actor workspaces"}
    (root / "fixture_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    oracle_manifest = {"schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
                       "initial_sha256": _sha256(initial), "gold_sha256": _sha256(gold),
                       "gold_file": "private/gold.ods", "gold_visibility": "evaluator only"}
    (root / "private" / "oracle_manifest.json").write_text(
        json.dumps(oracle_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def copy_fixture(destination: str | Path) -> dict[str, Any]:
    dest = Path(destination)
    if dest.exists() and (dest.is_symlink() or any(dest.iterdir())):
        raise FileExistsError(f"destination must be empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent / "fixtures"
    shutil.copy2(source / "initial.ods", dest / "initial.ods")
    shutil.copy2(source / "fixture_manifest.json", dest / "fixture_manifest.json")
    return json.loads((dest / "fixture_manifest.json").read_text(encoding="utf-8"))


def is_real_ods(path: str | Path) -> bool:
    import zipfile
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.read("mimetype").decode() == "application/vnd.oasis.opendocument.spreadsheet"
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError):
        return False

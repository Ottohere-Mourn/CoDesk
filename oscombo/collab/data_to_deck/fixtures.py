"""Deterministic ODF fixture creation for Data-to-Deck Reconciliation V0."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from . import spec

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
}


def _cell(value: object) -> str:
    if isinstance(value, (int, float)):
        return (f'<table:table-cell office:value-type="float" office:value="{value}">'
                f'<text:p>{value}</text:p></table:table-cell>')
    return (f'<table:table-cell office:value-type="string"><text:p>{escape(str(value))}'
            '</text:p></table:table-cell>')


def _sheet(name: str, rows: list[list[object]]) -> str:
    body = "".join("<table:table-row>" + "".join(_cell(c) for c in row)
                   + "</table:table-row>" for row in rows)
    return f'<table:table table:name="{escape(name)}">{body}</table:table>'


def authority_sheets() -> dict[str, list[list[object]]]:
    sales = [["Quarter", "Region", "Revenue_USD_k"], *[list(r) for r in spec.SALES]]
    costs = [["Quarter", "Region", "COGS_USD_k", "Fulfillment_USD_k", "Promotion_USD_k"],
             *[list(r) for r in spec.COSTS]]
    summary = [["Quarter", "Revenue", "COGS", "Fulfillment", "Promotion", "Total_Cost",
                "Operating_Profit", "Gross_Margin", "Operating_Margin"]]
    for q in spec.QUARTERS:
        g = spec.GOLD_QUARTERS[q]
        summary.append([q, g["revenue"], g["cogs"], g["fulfillment"], g["promotion"],
                        g["total_cost"], g["operating_profit"], g["gross_margin"],
                        g["operating_margin"]])
    definitions = [
        ["Metric", "Definition"],
        ["Revenue", "Sum of regional Sales.Revenue_USD_k for quarter"],
        ["Gross Margin", "(Revenue - COGS) / Revenue"],
        ["Operating Profit", "Revenue - COGS - Fulfillment - Promotion"],
        ["Operating Margin", "Operating Profit / Revenue"],
        ["Promotion", "Promotion expense; association is not causal evidence"],
        ["Currency", "USD thousands unless stated otherwise"],
    ]
    reconciliation = [["Section", "Metric", "Value", "Unit", "Evidence"]]
    return {"Sales": sales, "Costs": costs, "Quarterly_Summary": summary,
            "KPI_Definitions": definitions, "Reconciliation": reconciliation}


def _manifest_xml(mimetype: str, content_name: str) -> bytes:
    return (f'''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="{mimetype}"/>
 <manifest:file-entry manifest:full-path="{content_name}" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>
</manifest:manifest>''').encode()


def _write_odf(path: Path, mimetype: str, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        info = zipfile.ZipInfo("mimetype", (2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, mimetype.encode())
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)


def _ods(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    tables = "".join(_sheet(name, rows) for name, rows in sheets.items())
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="{NS['office']}" xmlns:table="{NS['table']}" xmlns:text="{NS['text']}" office:version="1.2">
 <office:body><office:spreadsheet>{tables}</office:spreadsheet></office:body>
</office:document-content>'''.encode()
    common = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="{NS['office']}" xmlns:style="{NS['style']}" office:version="1.2"><office:styles/></office:document-styles>'''.encode()
    _write_odf(path, "application/vnd.oasis.opendocument.spreadsheet", {
        "content.xml": content, "styles.xml": common,
        "meta.xml": b'<?xml version="1.0"?><office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:meta/></office:document-meta>',
        "settings.xml": b'<?xml version="1.0"?><office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:settings/></office:document-settings>',
        "META-INF/manifest.xml": _manifest_xml("application/vnd.oasis.opendocument.spreadsheet", "content.xml"),
    })


SLIDES = {
    "slide1": ["Quarterly Performance | Management Review", "Revenue grew across the year; operating profit is the operating result after COGS, fulfillment, and promotion.", "Q3 revenue: $310k", "Q4 revenue: $330k"],
    "slide2": ["Margin and Cost Profile", "Q3 revenue is $310k.", "Gross Margin: 31% (Q3)", "Operating Margin: 31% (Q3)", "Q3 promotion expense increased to $24k."],
    "slide3": ["Q2 to Q3: What Changed", "Q2 operating profit: $98k; Q3 operating profit: $93k.", "West discount campaign caused the Q3 profit decline.", "Complete the regional profit bridge and distinguish evidence from explanation."],
}


def _text_frame(text: str, index: int) -> str:
    # All source strings are plain text; escaping makes the generated XML safe.
    return (f'<draw:frame draw:style-name="gr1" draw:text-style-name="P1" '
            f'svg:width="25cm" svg:height="1.2cm" svg:x="1cm" svg:y="{1 + index * 1.3}cm">'
            f'<draw:text-box><text:p>{escape(text)}</text:p></draw:text-box></draw:frame>')


def _odp(path: Path, slides: dict[str, list[str]]) -> None:
    pages = "".join(
        f'<draw:page draw:name="{name}" draw:style-name="dp1" presentation:presentation-page-layout-name="AL1T0">'
        + "".join(_text_frame(text, i) for i, text in enumerate(lines)) + "</draw:page>"
        for name, lines in slides.items())
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="{NS['office']}" xmlns:style="{NS['style']}" xmlns:text="{NS['text']}" xmlns:draw="{NS['draw']}" xmlns:presentation="{NS['presentation']}" xmlns:svg="{NS['svg']}" office:version="1.2">
 <office:automatic-styles><style:style style:name="gr1" style:family="graphic"><style:graphic-properties draw:fill="none" draw:stroke="none"/></style:style><style:style style:name="dp1" style:family="drawing-page"/></office:automatic-styles>
 <office:body><office:presentation>{pages}</office:presentation></office:body>
</office:document-content>'''.encode()
    styles = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="{NS['office']}" xmlns:style="{NS['style']}" xmlns:text="{NS['text']}" xmlns:fo="{NS['fo']}" office:version="1.2">
 <office:styles><style:style style:name="P1" style:family="paragraph"><style:text-properties fo:font-size="20pt"/></style:style></office:styles>
 <office:automatic-styles><style:presentation-page-layout style:name="AL1T0"/></office:automatic-styles>
 <office:master-styles><style:master-page style:name="Default" style:page-layout-name="AL1T0"/></office:master-styles>
</office:document-styles>'''
    styles = styles.encode()
    _write_odf(path, "application/vnd.oasis.opendocument.presentation", {
        "content.xml": content, "styles.xml": styles,
        "meta.xml": b'<?xml version="1.0"?><office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:meta/></office:document-meta>',
        "settings.xml": b'<?xml version="1.0"?><office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:settings/></office:document-settings>',
        "META-INF/manifest.xml": _manifest_xml("application/vnd.oasis.opendocument.presentation", "content.xml"),
    })


def build_fixture(output: str | Path) -> dict[str, object]:
    """Create deterministic source documents; returns hashes for provenance."""
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    _ods(root / spec.FIXTURE_NAMES["authority"], authority_sheets())
    _odp(root / spec.FIXTURE_NAMES["draft"], SLIDES)
    brief = """# Data-to-Deck Collaborative Reconciliation\n\nAmounts are USD thousands.\n\n`quarterly_authority.ods` is the authoritative source. `management_draft.odp` is an unfinished report and may contain errors. Preserve correct draft content while completing the requested reconciliation. Both actors can read both files. Actor A writes only the Calc output; Actor B writes only the Impress output.\n"""
    (root / spec.FIXTURE_NAMES["brief"]).write_text(brief, encoding="utf-8")
    result = {}
    for name in (spec.FIXTURE_NAMES["authority"], spec.FIXTURE_NAMES["draft"], spec.FIXTURE_NAMES["brief"]):
        data = (root / name).read_bytes()
        result[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    manifest = {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
                "fixture_sha256": result, "seed": 0,
                "conditions": list(spec.CONDITIONS),
                "role_budgets": spec.ROLE_BUDGET,
                "outputs": spec.OUTPUTS}
    (root / "fixture_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest

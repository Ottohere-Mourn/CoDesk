"""Deterministic OpenDocument Writer fixture for EDIT-MODE1."""
import json
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

LINES = [
    "Release status: STATUS | HOLD-FOR-REVIEW",
    "Reviewer code: ____; change only this fixed-width code.",
    "Guard phrase: DO-NOT-ALTER-THIS-LINE",
]
OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
FO = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
MANIFEST = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
MIMETYPE = "application/vnd.oasis.opendocument.text"

def _xml(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

def write_odt(path, lines):
    """Write a small but standards-shaped ODT; mimetype is first and uncompressed."""
    for prefix, uri in (("office", OFFICE), ("text", TEXT), ("style", STYLE),
                        ("fo", FO), ("manifest", MANIFEST)):
        ET.register_namespace(prefix, uri)

    content = ET.Element(f"{{{OFFICE}}}document-content", {f"{{{OFFICE}}}version": "1.2"})
    body = ET.SubElement(content, f"{{{OFFICE}}}body")
    doc = ET.SubElement(body, f"{{{OFFICE}}}text")
    for line in lines:
        ET.SubElement(doc, f"{{{TEXT}}}p").text = line

    styles = ET.Element(f"{{{OFFICE}}}document-styles", {f"{{{OFFICE}}}version": "1.2"})
    office_styles = ET.SubElement(styles, f"{{{OFFICE}}}styles")
    default = ET.SubElement(office_styles, f"{{{STYLE}}}default-style", {f"{{{STYLE}}}family": "paragraph"})
    ET.SubElement(default, f"{{{STYLE}}}paragraph-properties", {f"{{{FO}}}line-height": "100%"})
    ET.SubElement(styles, f"{{{OFFICE}}}automatic-styles")
    ET.SubElement(styles, f"{{{OFFICE}}}master-styles")

    meta = ET.Element(f"{{{OFFICE}}}document-meta", {f"{{{OFFICE}}}version": "1.2"})
    ET.SubElement(meta, f"{{{OFFICE}}}meta")
    settings = ET.Element(f"{{{OFFICE}}}document-settings", {f"{{{OFFICE}}}version": "1.2"})
    ET.SubElement(settings, f"{{{OFFICE}}}settings")

    manifest = ET.Element(f"{{{MANIFEST}}}manifest", {f"{{{MANIFEST}}}version": "1.2"})
    ET.SubElement(manifest, f"{{{MANIFEST}}}file-entry", {
        f"{{{MANIFEST}}}full-path": "/", f"{{{MANIFEST}}}version": "1.2",
        f"{{{MANIFEST}}}media-type": MIMETYPE})
    for name in ("content.xml", "styles.xml", "meta.xml", "settings.xml"):
        ET.SubElement(manifest, f"{{{MANIFEST}}}file-entry", {
            f"{{{MANIFEST}}}full-path": name, f"{{{MANIFEST}}}media-type": "text/xml"})

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, MIMETYPE)
        zf.writestr("content.xml", _xml(content), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("styles.xml", _xml(styles), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("meta.xml", _xml(meta), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("settings.xml", _xml(settings), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("META-INF/manifest.xml", _xml(manifest), compress_type=zipfile.ZIP_DEFLATED)

def build(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_odt(out / "Release-review.odt", LINES)
    expected = {"lines": LINES,
                "a_line": "Release status: STATUS | READY HOLD-FOR-REVIEW",
                "b_line": "Reviewer code: AB12; change only this fixed-width code."}
    (out / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    build(sys.argv[1])

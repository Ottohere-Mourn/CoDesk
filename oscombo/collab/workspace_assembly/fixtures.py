"""Deterministic document and attachment fixtures for Workspace Assembly."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw

from oscombo.collab.data_to_deck.fixtures import NS, _manifest_xml, _write_odf

from . import CASE_ID, CASE_VERSION
from . import spec

TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
XLINK_NS = "http://www.w3.org/1999/xlink"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tree_hashes(root: str | Path) -> dict[str, str]:
    base = Path(root)
    result = {}
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        if path.is_symlink():
            raise ValueError(f"fixture tree must not contain symlinks: {path}")
        result[path.relative_to(base).as_posix()] = _sha(path)
    return result


def _report_odt(path: Path, *, final: bool) -> None:
    hrefs = dict(spec.REPORT_LINKS)
    if not final:
        hrefs = {"Q3 revenue chart": "q3_chart_final.png",
                 "Vendor terms": "vendor_terms_final_v2.pdf",
                 "Week 42 inventory snapshot": "inventory_week42.csv",
                 "Supplier compliance summary": "supplier_compliance_note.txt"}
    paragraphs = [
        '<text:h text:outline-level="1">Quarterly Supply Review</text:h>',
        "Project Aurora reviews Q3 supply readiness and supporting evidence.",
        "Revenue increased in the latest quarter; inventory coverage should be checked before the next order.",
        "The following attachments support the report and should remain byte-identical during handoff:",
    ]
    for label in spec.REPORT_LINKS:
        paragraphs.append(f'<text:p><text:a xlink:href="{escape(hrefs[label], {chr(34): "&quot;"})}">{escape(label)}</text:a></text:p>')
    paragraphs.extend([
        "Prepared for the operations review team.",
        "Do not treat the prior-quarter baseline as part of this delivery.",
    ])
    body = "".join(f"<text:p>{p}</text:p>" if not p.startswith("<text:") else p for p in paragraphs)
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="{NS['office']}" xmlns:text="{TEXT_NS}"
 xmlns:xlink="{XLINK_NS}" office:version="1.2">
 <office:body><office:text>{body}</office:text></office:body>
</office:document-content>'''.encode("utf-8")
    styles = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="{NS['office']}" xmlns:style="{NS['style']}"
 office:version="1.2"><office:styles><style:default-style style:family="paragraph"/></office:styles>
 <office:automatic-styles/><office:master-styles/></office:document-styles>'''.encode()
    mimetype = "application/vnd.oasis.opendocument.text"
    _write_odf(path, mimetype, {
        "content.xml": content, "styles.xml": styles,
        "meta.xml": (f'''<?xml version="1.0"?><office:document-meta xmlns:office="{NS['office']}"
 office:version="1.2"><office:meta/></office:document-meta>''').encode(),
        "settings.xml": (f'''<?xml version="1.0"?><office:document-settings xmlns:office="{NS['office']}"
 office:version="1.2"><office:settings/></office:document-settings>''').encode(),
        "META-INF/manifest.xml": _manifest_xml(mimetype, "content.xml"),
    })


def _pdf_escape(value: str) -> bytes:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("ascii")


def _one_page_pdf(lines: list[str]) -> bytes:
    commands = [b"BT", b"/F1 16 Tf", b"50 740 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append(b"0 -28 Td")
        commands.extend((b"(" + _pdf_escape(line) + b") Tj",))
    commands.append(b"ET")
    stream = b"\n".join(commands)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def _png_chart(path: Path) -> None:
    image = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 18), "Quarterly revenue (USD k)", fill="#182230")
    values = [("Q1", 240), ("Q2", 270), ("Q3", 300)]
    baseline, max_height = 300, 220
    for idx, (quarter, value) in enumerate(values):
        x0 = 120 + idx * 150
        height = int(value / 330 * max_height)
        draw.rectangle((x0, baseline - height, x0 + 76, baseline), fill="#3b82a0")
        draw.text((x0 + 25, baseline + 10), quarter, fill="#182230")
        draw.text((x0 + 18, baseline - height - 22), str(value), fill="#182230")
    draw.line((60, baseline, 590, baseline), fill="#46515c", width=2)
    image.save(path, format="PNG", optimize=False)


def _write_csv(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["SKU", "Description", "On hand", "Inbound", "Snapshot date"])
        writer.writerow(["SKU-LAMP", "Desk lamp", 42, 18, "2026-10-16"])
        writer.writerow(["SKU-MUG", "Ceramic mug", 50, 10, "2026-10-16"])
        writer.writerow(["SKU-CABLE", "USB-C cable", 150, 30, "2026-10-16"])


def _attachment_manifest(path: Path, workspace: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["asset_id", "relative_path", "sha256", "description"])
        for item in spec.ATTACHMENTS:
            target_rel = item["target"].removeprefix("delivery/")
            target = workspace / item["target"]
            writer.writerow([item["asset_id"], target_rel, _sha(target), item["description"]])


def _create_initial_tree(root: Path) -> None:
    incoming = root / "incoming"
    incoming.mkdir(parents=True)
    _report_odt(incoming / "Quarterly_Supply_Report.odt", final=False)
    _png_chart(incoming / "q3_chart_final.png")
    (incoming / "vendor_terms_final_v2.pdf").write_bytes(
        _one_page_pdf(["Aurora Vendor Terms", "Payment: net 30 days", "Delivery lead time: 14 days"]))
    _write_csv(incoming / "inventory_week42.csv")
    (incoming / "supplier_compliance_note.txt").write_text(
        "Supplier compliance review: current certificates verified for the Q3 delivery window.\n", encoding="utf-8")
    (incoming / "README.md").write_text(
        "Incoming project files for the operations handoff. Preserve this note.\n", encoding="utf-8")
    (incoming / "Project_Brief.md").write_text(spec.PUBLIC_ASSET_BRIEF, encoding="utf-8")
    archive = root / "archive"
    archive.mkdir()
    (archive / "q2_baseline.txt").write_text(
        "Prior-quarter baseline retained for reference; do not include in the new delivery.\n", encoding="utf-8")


def _create_gold_tree(initial: Path, gold: Path) -> None:
    shutil.copytree(initial, gold)
    delivery = gold / "delivery"
    attachments_dir = delivery / "attachments"
    attachments_dir.mkdir(parents=True)
    for item in spec.ATTACHMENTS:
        source = gold / item["source"]
        target = gold / item["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    (gold / spec.REPORT_SOURCE).unlink()
    _report_odt(delivery / "Quarterly_Supply_Report.odt", final=True)
    _attachment_manifest(delivery / "attachment_manifest.csv", gold)


def build_fixture(output: str | Path) -> dict[str, object]:
    root = Path(output)
    if root.exists() and (root.is_symlink() or any(root.iterdir())):
        raise FileExistsError(f"fixture output must be new/empty: {root}")
    initial = root / "initial_workspace"
    gold = root / "private" / "gold_workspace"
    root.mkdir(parents=True, exist_ok=True)
    _create_initial_tree(initial)
    gold.parent.mkdir(parents=True, exist_ok=True)
    _create_gold_tree(initial, gold)
    initial_hashes, gold_hashes = tree_hashes(initial), tree_hashes(gold)
    public_manifest = {
        "schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "fixture_id": "WA-PROJECT-AURORA-001", "seed": 0,
        "initial_tree_sha256": hashlib.sha256(json.dumps(initial_hashes, sort_keys=True).encode()).hexdigest(),
        "initial_files": initial_hashes,
        "task_brief": "incoming/Project_Brief.md",
        "gold_visibility": "private evaluator fixture; do not mount for actors",
    }
    private_manifest = {
        "schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "initial_tree_sha256": public_manifest["initial_tree_sha256"],
        "gold_tree_sha256": hashlib.sha256(json.dumps(gold_hashes, sort_keys=True).encode()).hexdigest(),
        "gold_files": gold_hashes,
        "expected_report_links": spec.REPORT_LINKS,
        "moved_assets": [{**item, "sha256": initial_hashes[item["source"]]} for item in spec.ATTACHMENTS],
    }
    (root / "fixture_manifest.json").write_text(json.dumps(public_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "private" / "oracle_manifest.json").write_text(
        json.dumps(private_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return public_manifest


def copy_fixture(destination: str | Path) -> dict[str, object]:
    dest = Path(destination)
    if dest.exists() and (dest.is_symlink() or any(dest.iterdir())):
        raise FileExistsError(f"destination must be empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent / "fixtures"
    shutil.copytree(source / "initial_workspace", dest / "workspace")
    shutil.copy2(source / "fixture_manifest.json", dest / "fixture_manifest.json")
    return json.loads((dest / "fixture_manifest.json").read_text(encoding="utf-8"))


def is_real_odt(path: str | Path) -> bool:
    import zipfile
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.read("mimetype").decode() == "application/vnd.oasis.opendocument.text"
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError):
        return False


def read_odt(path: str | Path) -> tuple[str, dict[str, str]]:
    import zipfile
    from xml.etree import ElementTree as ET
    if not is_real_odt(path):
        raise ValueError("not a real OpenDocument Text file")
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    text_p = f"{{{TEXT_NS}}}p"
    text_h = f"{{{TEXT_NS}}}h"
    text_a = f"{{{TEXT_NS}}}a"
    xlink_href = f"{{{XLINK_NS}}}href"
    paragraphs = []
    links = {}
    for node in root.iter():
        if node.tag in (text_p, text_h):
            paragraphs.append("".join(node.itertext()))
        if node.tag == text_a:
            links["".join(node.itertext())] = node.attrib.get(xlink_href, "")
    return "\n".join(paragraphs), links

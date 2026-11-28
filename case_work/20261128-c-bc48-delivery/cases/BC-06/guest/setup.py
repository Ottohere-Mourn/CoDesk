from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def write_pdf(path: Path, lines: list[str]) -> None:
    def esc(s): return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = ("BT\n/F1 10 Tf\n48 748 Td\n" + "\n".join(("0 -14 Td\n" if i else "") + f"({esc(line)}) Tj" for i, line in enumerate(lines)) + "\nET").encode("ascii", "replace")
    bodies = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
              b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
              b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    out = bytearray(b"%PDF-1.4\n"); offsets = [0]
    for i, body in enumerate(bodies, 1): offsets.append(len(out)); out.extend(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(out); out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]: out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()); path.write_bytes(out)


def make_odt(path: Path):
    sections = [
        ("Section 1 - Scope", "The parties provide managed operations services during the contract term."),
        ("Section 2 - Payment Terms", "Payment terms: Net 45. Late fee: 0.5% monthly."),
        ("Section 3 - Confidentiality", "Each party protects confidential information using reasonable safeguards."),
        ("Section 4 - Service Level Agreement", "Availability target: 99.0%. P99 latency target: 500 ms."),
        ("Section 5 - Credit and Cap", "Credit reserve: 3%. Annual liability cap: $600,000."),
        ("Section 6 - Security", "The provider maintains documented access controls and incident response."),
        ("Section 7 - Remedies and Termination", "Service credit: 5%. Termination notice: 90 days."),
        ("Section 8 - Data Handling", "Customer data is retained only for the approved service period."),
        ("Section 9 - Audit", "Records are available for a reasonable compliance review."),
        ("Section 10 - Subprocessors", "Subprocessors must meet the stated contractual controls."),
        ("Section 11 - Disputes", "The parties will first seek a documented good-faith resolution."),
        ("Section 12 - General", "This agreement is governed by the executed order form."),
    ]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:text>']
    for heading, body in sections:
        xml.append(f"<text:h text:outline-level=\"1\">{heading}</text:h><text:p>{body}</text:p>")
    xml.append("</office:text></office:body></office:document-content>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text", compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", "".join(xml))
        z.writestr("styles.xml", '<?xml version="1.0"?><office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" office:version="1.2"><office:styles><style:default-style style:family="paragraph"/></office:styles></office:document-styles>')
        z.writestr("settings.xml", '<?xml version="1.0"?><office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" office:version="1.2"><office:settings><config:config-item-set config:name="ooo:configuration-settings"><config:config-item config:name="RecordChanges" config:type="boolean">true</config:config-item></config:config-item-set></office:settings></office:document-settings>')
        z.writestr("meta.xml", '<?xml version="1.0"?><office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:meta/></office:document-meta>')
        z.writestr("META-INF/manifest.xml", '<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/></manifest:manifest>')


def main():
    p = argparse.ArgumentParser(); p.add_argument("--source-dir", required=True); p.add_argument("--workspace", required=True); p.add_argument("--open-writer", action="store_true")
    a = p.parse_args(); root = Path(a.workspace).expanduser().resolve() / "legal"; root.mkdir(parents=True, exist_ok=True)
    make_odt(root / "msa_contract.odt")
    with (root / "billing_incidents.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["incident_id", "quarter", "record_type", "amount_usd", "due_date", "paid_date"])
        for i in range(1, 21):
            late = i in {3, 11, 15}; amount = {3: 12000, 11: 9400, 15: 8700}.get(i, 900 + i * 43)
            w.writerow([f"BILL-{1000+i}", "Q3", "INVOICE", amount, "2026-08-01", "2026-08-16" if late else "2026-08-01"])
        for i in range(21, 41):
            record_type = "TEST" if i == 21 else "VOID" if i == 22 else "INVOICE"
            quarter = "Q3" if i <= 22 else "Q2"
            w.writerow([f"BILL-{1000+i}", quarter, record_type, 500, "2026-08-01", "2026-08-25" if i == 23 else "2026-08-01"])
    with (root / "uptime_telemetry.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["outage_id", "window_start", "minutes", "planned_maintenance", "available", "p99_ms", "severity"])
        for i in range(1, 61):
            planned = 1 if i in {4, 8, 12, 16, 20, 24, 28, 32, 36, 40} else 0
            down = i in {17, 41, 53}
            p99 = 420 if i in {17, 41, 53, 55, 57, 59} else 210 + (i % 6) * 7
            w.writerow([f"OUT-{200+i}", f"2026-{(i%9)+1:02d}-{(i%27)+1:02d}T00:00:00Z", 5 if down else 0, planned, 0 if down else 1, p99, "SEV1" if down else "SEV3"])
    write_pdf(root / "policy_handbook.pdf", [
        "CONTRACT POLICY HANDBOOK - REV 7", "Billing: use Q3 INVOICE rows only; TEST and VOID records do not enter the denominator.",
        "Overdue means paid_date is more than 10 calendar days after due_date. Overdue rate is count / valid Q3 invoice count.",
        "Tier 2 applies from 10.00% through 19.99% overdue: Net 30; late fee 1.5% monthly; reserve 8%; annual cap $1,200,000.",
        "Commercial evidence: cite the three overdue incidents with the largest amount, descending amount, then incident ID.",
        "Availability: use a fixed 90-day denominator of 129600 minutes; sum unplanned downtime minutes only and exclude planned maintenance.",
        "P99 breach means p99_ms > 300. Gold tier: availability >= 99.50% and at most 8 P99 breaches.",
        "Gold technical terms: availability 99.50%; P99 latency < 300 ms; service credit 10%; termination notice 30 days.",
        "Technical evidence: cite the three highest severity outage IDs; break ties by outage ID ascending.",
        "Maintain Track Changes; do not accept changes. Comments must cite the evidence IDs and the derived tier.",
    ])
    # A second rules copy is explicit, concise, and is read independently by each role.
    (root / "review_checklist.txt").write_text("Preserve Sections 1, 3, 6, 8-12. Keep edits in the assigned contract sections. Save audit JSON and PDF output.\n", encoding="utf-8")
    if a.open_writer: subprocess.Popen(["soffice", str(root / "msa_contract.odt")], start_new_session=True)


if __name__ == "__main__": main()

"""Helpers to seed and inspect real LibreOffice Writer (.odt) and Calc (.ods) documents."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def create_seed_odt(dest_odt: Path, heading_text: str) -> None:
    dest_odt.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        txt = Path(tmp) / (dest_odt.stem + ".txt")
        txt.write_text(heading_text.rstrip() + "\n\n", encoding="utf-8")
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "odt", "--outdir", str(dest_odt.parent), str(txt)],
            check=True,
            capture_output=True,
            timeout=45,
        )


def create_seed_ods(dest_ods: Path, header_csv_line: str) -> None:
    dest_ods.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        csv_p = Path(tmp) / (dest_ods.stem + ".csv")
        csv_p.write_text(header_csv_line.rstrip() + "\n", encoding="utf-8")
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "ods", "--outdir", str(dest_ods.parent), str(csv_p)],
            check=True,
            capture_output=True,
            timeout=45,
        )


def extract_odf_text(odf_path: Path) -> str:
    if not odf_path.is_file():
        return ""
    try:
        with zipfile.ZipFile(odf_path, "r") as zf:
            xml_bytes = zf.read("content.xml")
        root = ET.fromstring(xml_bytes)
        chunks = [t.strip() for t in root.itertext() if t and t.strip()]
        return "\n".join(chunks)
    except Exception:
        return ""

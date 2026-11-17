"""Pure-stdlib + LibreOffice OOXML (.xlsx) multi-sheet builder, updater, and formula verifier."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

CellSpec = str | int | float | tuple[str, float | int | str | None]
# A tuple ("=SUM(B2:B13)", cached_val) writes an Excel formula <f>...</f> with optional cached value.


def _col_letter(idx_1based: int) -> str:
    out = []
    n = idx_1based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out.append(chr(ord("A") + rem))
    return "".join(reversed(out))


def _col_index(letters: str) -> int:
    acc = 0
    for ch in letters:
        acc = acc * 26 + (ord(ch.upper()) - ord("A") + 1)
    return acc


def write_multisheet_xlsx(path: Path, sheets: list[tuple[str, list[list[CellSpec]]]]) -> None:
    """Write a clean, standard-compliant multi-sheet OOXML .xlsx file supporting live formulas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{overrides}</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    sheet_entries = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _) in enumerate(sheets, start=1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets>{sheet_entries}</sheets></workbook>'
    )
    wb_rels_entries = "".join(
        f'<Relationship Id="rId{i}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">{wb_rels_entries}</Relationships>'
    )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        for i, (_sname, rows) in enumerate(sheets, start=1):
            row_chunks = []
            for r_idx, row in enumerate(rows, start=1):
                c_chunks = []
                for c_idx, cell in enumerate(row, start=1):
                    ref = f"{_col_letter(c_idx)}{r_idx}"
                    if cell is None or cell == "":
                        continue
                    if isinstance(cell, tuple):
                        formula_raw, cached = cell
                        f_txt = escape(str(formula_raw).lstrip("="))
                        if isinstance(cached, (int, float)):
                            c_chunks.append(f'<c r="{ref}"><f>{f_txt}</f><v>{cached}</v></c>')
                        else:
                            c_chunks.append(f'<c r="{ref}"><f>{f_txt}</f></c>')
                    elif isinstance(cell, str) and cell.startswith("="):
                        f_txt = escape(cell[1:])
                        c_chunks.append(f'<c r="{ref}"><f>{f_txt}</f></c>')
                    elif isinstance(cell, (int, float)) and not isinstance(cell, bool):
                        c_chunks.append(f'<c r="{ref}"><v>{cell}</v></c>')
                    else:
                        s_txt = escape(str(cell))
                        c_chunks.append(f'<c r="{ref}" t="inlineStr"><is><t>{s_txt}</t></is></c>')
                row_chunks.append(f'<row r="{r_idx}">{"".join(c_chunks)}</row>')
            ws_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<worksheet xmlns="{MAIN_NS}"><sheetData>{"".join(row_chunks)}</sheetData></worksheet>'
            )
            zf.writestr(f"xl/worksheets/sheet{i}.xml", ws_xml)


def read_multisheet_xlsx(path: Path) -> dict[str, dict[str, dict[str, str | float | None]]]:
    """Read sheet -> cell_ref (e.g. B2) -> {value, formula} from any OOXML .xlsx file."""
    out: dict[str, dict[str, dict[str, str | float | None]]] = {}
    with ZipFile(path, "r") as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.findall(f"{{{MAIN_NS}}}si"):
                shared_strings.append("".join(si.itertext()))
        wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
        rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {}
        for rel in rels_root:
            rid = rel.attrib.get("Id", "")
            tgt = rel.attrib.get("Target", "").lstrip("/")
            if not tgt.startswith("xl/"):
                tgt = "xl/" + tgt
            rid_to_target[rid] = tgt
        sheets_el = wb_root.find(f"{{{MAIN_NS}}}sheets")
        if sheets_el is None:
            return out
        for sh in sheets_el:
            sname = sh.attrib["name"]
            rid = sh.attrib.get(f"{{{REL_NS}}}id", "")
            ws_path = rid_to_target.get(rid, "")
            if not ws_path or ws_path not in zf.namelist():
                continue
            ws_root = ET.fromstring(zf.read(ws_path))
            sdict: dict[str, dict[str, str | float | None]] = {}
            for c_el in ws_root.iter(f"{{{MAIN_NS}}}c"):
                ref = c_el.attrib.get("r", "")
                ctype = c_el.attrib.get("t", "")
                f_el = c_el.find(f"{{{MAIN_NS}}}f")
                v_el = c_el.find(f"{{{MAIN_NS}}}v")
                is_el = c_el.find(f"{{{MAIN_NS}}}is")
                formula = f_el.text.strip() if (f_el is not None and f_el.text) else None
                val: str | float | None = None
                if ctype == "s" and v_el is not None and v_el.text is not None:
                    idx = int(v_el.text.strip())
                    val = shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
                elif ctype == "inlineStr" and is_el is not None:
                    val = "".join(is_el.itertext())
                elif ctype in ("str", "b") and v_el is not None:
                    val = v_el.text or ""
                elif v_el is not None and v_el.text is not None:
                    raw_v = v_el.text.strip()
                    try:
                        val = float(raw_v)
                    except ValueError:
                        val = raw_v
                sdict[ref] = {"value": val, "formula": formula}
            out[sname] = sdict
    return out


def update_single_sheet_xlsx(path: Path, target_sheet: str, rows: list[list[CellSpec]]) -> None:
    """Cooperatively update ONLY target_sheet inside an existing multi-sheet .xlsx, preserving peer sheets & formulas."""
    existing = read_multisheet_xlsx(path)
    rebuilt: list[tuple[str, list[list[CellSpec]]]] = []
    found = False
    for sname, sdict in existing.items():
        if sname == target_sheet:
            rebuilt.append((sname, rows))
            found = True
            continue
        max_r = 0
        max_c = 0
        parsed_cells: dict[tuple[int, int], CellSpec] = {}
        for ref, info in sdict.items():
            m = re.match(r"^([A-Z]+)(\d+)$", ref)
            if not m:
                continue
            c_i = _col_index(m.group(1))
            r_i = int(m.group(2))
            max_r = max(max_r, r_i)
            max_c = max(max_c, c_i)
            if info["formula"]:
                parsed_cells[(r_i, c_i)] = ("=" + str(info["formula"]), info["value"])
            else:
                parsed_cells[(r_i, c_i)] = info["value"] if info["value"] is not None else ""
        grid: list[list[CellSpec]] = []
        for r_i in range(1, max_r + 1):
            grid.append([parsed_cells.get((r_i, c_i), "") for c_i in range(1, max_c + 1)])
        rebuilt.append((sname, grid))
    if not found:
        rebuilt.append((target_sheet, rows))
    write_multisheet_xlsx(path, rebuilt)


def evaluate_xlsx_via_libreoffice(path: Path) -> dict[str, dict[str, dict[str, str | float | None]]]:
    """Recalculate all cross-sheet formulas via headless LibreOffice round-trip when available."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            ods_p = tmp_dir / "eval.ods"
            cp1 = subprocess.run(
                ["libreoffice", "--headless", "--norestore", "--convert-to", "ods", "--outdir", str(tmp_dir), str(path)],
                capture_output=True, text=True, timeout=45,
            )
            cand_ods = tmp_dir / (path.stem + ".ods")
            if cp1.returncode == 0 and cand_ods.is_file():
                cand_ods.rename(ods_p)
                cp2 = subprocess.run(
                    ["libreoffice", "--headless", "--norestore", "--convert-to", "xlsx", "--outdir", str(tmp_dir), str(ods_p)],
                    capture_output=True, text=True, timeout=45,
                )
                eval_xlsx = tmp_dir / "eval.xlsx"
                if cp2.returncode == 0 and eval_xlsx.is_file():
                    return read_multisheet_xlsx(eval_xlsx)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return read_multisheet_xlsx(path)

"""Blind deterministic final-artifact grader for CONC-02."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageStat
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def load_expected():
    """Load the host-only answer key staged beside (never uploaded with) Guest assets."""
    root = Path(os.environ.get("PARAGUI_TASK_ASSETS", ""))
    path = root / "CONC-02" / "private" / "expected.json"
    if not path.is_file():
        raise FileNotFoundError(f"CONC-02 private expected data missing at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _slide_text(slide):
    values = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False):
            values.append(shape.text_frame.text)
        if getattr(shape, "has_table", False):
            values.extend(cell.text for row in shape.table.rows for cell in row.cells)
    return "\n".join(values)


def _table(slide):
    return next((shape.table for shape in slide.shapes if getattr(shape, "has_table", False)), None)


def _cell_rgb(cell):
    try:
        return tuple(cell.fill.fore_color.rgb) if cell.fill.fore_color.rgb else None
    except (AttributeError, TypeError):
        return None


def _is_highlight(cell):
    rgb = _cell_rgb(cell)
    return rgb is not None and rgb not in {(255, 255, 255), (248, 250, 252), (43, 73, 99)}


def _row_index(table, label):
    for i, row in enumerate(table.rows):
        if row.cells and row.cells[0].text.strip() == label:
            return i
    return None


def _find_banner(slide):
    candidates = []
    for shape in slide.shapes:
        if shape.width >= int(7 * 914400) and shape.height >= int(0.65 * 914400):
            try:
                rgb = shape.fill.fore_color.rgb
                if rgb:
                    candidates.append((shape, tuple(rgb)))
            except (AttributeError, TypeError):
                pass
    return candidates[0] if candidates else (None, None)


def _fill_rgb_ok(actual, expected):
    return actual is not None and all(abs(actual[i] - expected[i]) <= 3 for i in range(3))


def _notes(slide):
    try:
        return slide.notes_slide.notes_text_frame.text
    except Exception:
        return ""


def _inside(shape, prs):
    return shape.left >= 0 and shape.top >= 0 and shape.left + shape.width <= prs.slide_width and shape.top + shape.height <= prs.slide_height


def _overlap(a, b):
    return a.left < b.left + b.width and a.left + a.width > b.left and a.top < b.top + b.height and a.top + a.height > b.top


def _font_size(shape):
    sizes = [run.font.size.pt for p in shape.text_frame.paragraphs for run in p.runs if run.font.size]
    return max(sizes, default=0)


def _body_fits(shape):
    if shape.top + shape.height > int(6.55 * 914400):
        return False
    text = shape.text_frame.text.strip()
    if not text:
        return False
    # Long bullet blocks need real vertical room; a large font in the original one-inch box is not sufficient.
    size = _font_size(shape)
    return shape.height >= int(2.45 * 914400) or (shape.height >= int(1.9 * 914400) and size <= 20)


def _render(pdf_path: Path, render_dir: Path):
    pdfinfo, pdftoppm = shutil.which("pdfinfo"), shutil.which("pdftoppm")
    if not pdf_path.is_file():
        return [], False
    if not pdfinfo or not pdftoppm:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            if len(doc) != 4:
                return [], False
            render_dir.mkdir(parents=True, exist_ok=True)
            pages = []
            for index, page in enumerate(doc, 1):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                pix.save(str(render_dir / f"render-{index}.png"))
                pages.append(Image.open(render_dir / f"render-{index}.png").convert("RGB"))
            return pages, len(pages) == 4
        except Exception:
            return [], False
    info = subprocess.run([pdfinfo, str(pdf_path)], capture_output=True, text=True, timeout=30)
    m = re.search(r"^Pages:\s+(\d+)\s*$", info.stdout, re.M)
    if info.returncode or not m or int(m.group(1)) != 4:
        return [], False
    render_dir.mkdir(parents=True, exist_ok=True)
    prefix = render_dir / "render"
    proc = subprocess.run([pdftoppm, "-f", "1", "-l", "4", "-r", "120", "-png", str(pdf_path), str(prefix)],
                          capture_output=True, text=True, timeout=90)
    if proc.returncode:
        return [], False
    pages = []
    for index in range(1, 5):
        png = render_dir / f"render-{index}.png"
        if png.exists():
            pages.append(Image.open(png).convert("RGB"))
    return pages, len(pages) == 4


def _near_color(image, rgb, box=None, tolerance=16):
    if image is None:
        return False
    im = image.crop(box) if box else image
    px = im.convert("RGB").load()
    count = 0
    step = max(1, im.width // 900)
    for y in range(0, im.height, max(1, im.height // 600)):
        for x in range(0, im.width, step):
            r, g, b = px[x, y]
            if max(abs(r - rgb[0]), abs(g - rgb[1]), abs(b - rgb[2])) <= tolerance:
                count += 1
                if count >= 15:
                    return True
    return False


def _has_detail(image, box=None):
    if image is None:
        return False
    im = (image.crop(box) if box else image).convert("RGB")
    stat = ImageStat.Stat(im)
    return sum(stat.stddev) > 40


def _bottom_clean(image):
    if image is None:
        return False
    gray = image.convert("L")
    y0 = int(gray.height * 0.965)
    pixels = gray.crop((0, y0, gray.width, gray.height)).getdata()
    dark = sum(1 for p in pixels if p < 100)
    return dark <= max(12, gray.width // 80)


def grade(pptx_path: Path, pdf_path: Path, role: str, expected: dict, render_dir: Path):
    checks = []
    if not Path(pptx_path).is_file():
        checks = [False] * 12
        return {"score": 0.0, "checks": checks, "flags": [f"{role.upper()}{i:02d}" for i in range(1, 13)]}
    try:
        prs = Presentation(str(pptx_path))
        slides = list(prs.slides)
    except Exception:
        return {"score": 0.0, "checks": [False] * 12, "flags": [f"{role.upper()}{i:02d}" for i in range(1, 13)]}

    e = expected[role]
    checks.append(len(slides) == 4)  # 01: package parses and has four slides
    checks.append(e["title"] in _slide_text(slides[0]))  # 02: title
    _, color = _find_banner(slides[0])
    checks.append(_fill_rgb_ok(color, tuple(e["banner_rgb"])))  # 03: image-derived banner color

    if role == "a":
        task_slide = slides[1]
        checks.append(_table_has_values(_table(task_slide), e["corrections"]))  # 04
        checks.append(_row_is_highlighted(_table(task_slide), e["highlight_row"]))  # 05
        media_slide = slides[2]
        hashes = _embedded_image_hashes(media_slide)
        checks.append(all(x in hashes for x in e["image_sha256"]))  # 06
        imgs = [s for s in media_slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
        caption = next((s for s in media_slide.shapes if getattr(s, "has_text_frame", False) and "provisional" in s.text.lower()), None)
        checks.append(len(imgs) >= 2 and caption is not None and all(_inside(s, prs) and not _overlap(s, caption) for s in imgs))  # 07
        body = _body_shape(slides[3])
        content = _slide_text(slides[3])
        checks.append(body is not None and all(p in content for p in e["points"]))  # 08
        notes = _notes(slides[3]).lower()
        checks.append(all(token in notes for token in ("supplier rebates remain within the contracted tier", "do not annualize")))  # 09
        checks.append(body is not None and _body_fits(body))  # 10
    else:
        checks.append("Product Overview" in _slide_text(slides[1]) and "Launch Parameters" in _slide_text(slides[2]))  # 04
        checks.append(_table_has_values(_table(slides[2]), e["corrections"]))  # 05
        checks.append(_row_is_highlighted(_table(slides[2]), e["highlight_row"]))  # 06
        media_slide = slides[1]
        hashes = _embedded_image_hashes(media_slide)
        checks.append(all(x in hashes for x in e["image_sha256"]))  # 07
        imgs = [s for s in media_slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
        title = next((s for s in media_slide.shapes if getattr(s, "has_text_frame", False) and "flexible platform" in s.text.lower()), None)
        caption = next((s for s in media_slide.shapes if getattr(s, "has_text_frame", False) and "safe area" in s.text.lower()), None)
        checks.append(len(imgs) >= 2 and title is not None and caption is not None and all(_inside(s, prs) and not _overlap(s, title) and not _overlap(s, caption) for s in imgs))  # 08
        body = _body_shape(slides[3])
        content = _slide_text(slides[3])
        checks.append(body is not None and all(p in content for p in e["points"]))  # 09
        notes = _notes(slides[3]).lower()
        checks.append(all(token in notes for token in ("42% pro and 31% max", "before the regional safety review")))  # 10

    pages, rendered = _render(Path(pdf_path), Path(render_dir))
    checks.append(rendered)  # 11 for A; 11 for B
    if role == "a":
        details = len(pages) == 4 and all(_has_detail(p) for p in pages) and _near_color(pages[0], tuple(e["banner_rgb"])) and _has_detail(pages[2]) and _bottom_clean(pages[3])
    else:
        details = (len(pages) == 4 and all(_has_detail(p) for p in pages)
                   and _near_color(pages[0], tuple(e["banner_rgb"])) and _has_detail(pages[1])
                   and _has_detail(pages[2]) and body is not None and _body_fits(body) and _bottom_clean(pages[3]))
    checks.append(details)  # final render inspection
    checks = checks[:12]
    return {"score": sum(checks) / 12, "checks": checks,
            "flags": [f"{role.upper()}{i:02d}" for i, ok in enumerate(checks, 1) if not ok],
            "render_dir": str(render_dir)}


def _table_has_values(table, targets):
    if table is None:
        return False
    headers = [c.text.strip() for c in table.rows[0].cells]
    for key, value in targets.items():
        row_label, col_label = key.split("|", 1)
        row = _row_index(table, row_label)
        try:
            col = headers.index(col_label)
        except ValueError:
            return False
        if row is None or table.cell(row, col).text.strip() != value:
            return False
    return True


def _row_is_highlighted(table, label):
    if table is None:
        return False
    row = _row_index(table, label)
    if row is None:
        return False
    cells = table.rows[row].cells
    return all(all(run.font.bold is True for p in cell.text_frame.paragraphs for run in p.runs if run.text.strip()) and _is_highlight(cell)
               for cell in cells)


def _embedded_image_hashes(slide):
    return {hashlib.sha256(shape.image.blob).hexdigest() for shape in slide.shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE}


def _body_shape(slide):
    choices = [s for s in slide.shapes if getattr(s, "has_text_frame", False)
               and ("summarybody" in s.name.lower() or "revenue rose" in s.text.lower()
                    or "helios max leads" in s.text.lower() or len(s.text) > 180)]
    return max(choices, key=lambda s: len(s.text), default=None)

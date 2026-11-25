"""Deterministic answer-key checks for CONC-02; never invokes an LLM."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import fitz
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches, Pt

from grade import _find_banner, _row_index, grade
from build_assets import build as build_assets


def _set_text(shape, value: str, size: int | None = None, bold: bool | None = None):
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    p = frame.paragraphs[0]
    run = p.add_run()
    run.text = value
    run.font.name = "Liberation Sans"
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold


def _shape(slide, name):
    return next((x for x in slide.shapes if x.name == name), None)


def _remove(slide, name):
    shape = _shape(slide, name)
    if shape is not None:
        shape._element.getparent().remove(shape._element)


def _table(slide):
    return next(x.table for x in slide.shapes if getattr(x, "has_table", False))


def _truth_pptx(path: Path, role: str, assets: Path, expected: dict):
    prs = Presentation(str(path))
    e = expected[role]
    if role == "b":
        ids = prs.slides._sldIdLst
        item = ids[2]
        ids.remove(item)
        ids.insert(1, item)
    _set_text(_shape(prs.slides[0], "SlideTitle"), e["title"], 27, True)
    banner, _ = _find_banner(prs.slides[0])
    banner.fill.solid()
    banner.fill.fore_color.rgb = RGBColor(*e["banner_rgb"])
    target_slide = prs.slides[2] if role == "b" else prs.slides[1]
    table = _table(target_slide)
    headers = [c.text.strip() for c in table.rows[0].cells]
    for key, value in e["corrections"].items():
        row_label, col_label = key.split("|", 1)
        row = _row_index(table, row_label)
        col = headers.index(col_label)
        table.cell(row, col).text = value
    row = _row_index(table, e["highlight_row"])
    for cell in table.rows[row].cells:
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(255, 238, 170)
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font.bold = True
    media_slide = prs.slides[2] if role == "a" else prs.slides[1]
    if role == "a":
        _remove(media_slide, "ChartPlaceholderA")
        _remove(media_slide, "ChartPlaceholderB")
        image_names = ("chart_rev.png", "chart_margin.png")
    else:
        _remove(media_slide, "ProductImagePlaceholderA")
        _remove(media_slide, "ProductImagePlaceholderB")
        image_names = ("prod_front.png", "prod_side.png")
    for filename, x in zip(image_names, (0.95, 6.9)):
        media_slide.shapes.add_picture(str(assets / "guest" / f"in_{role}" / filename),
                                       Inches(x), Inches(2.0), width=Inches(5.4), height=Inches(3.05))
    final_slide = prs.slides[3]
    body = _shape(final_slide, "SummaryBody")
    body.left, body.top = Inches(1.0), Inches(1.78)
    body.width, body.height = Inches(11.2), Inches(4.3)
    points = e["points"]
    _set_text(body, "\n".join("• " + point for point in points), 17, False)
    final_slide.notes_slide.notes_text_frame.text = e["notes"]
    prs.save(path)


def _color(rgb):
    return tuple(x / 255 for x in rgb)


def _truth_pdf(path: Path, role: str, assets: Path, expected: dict):
    """Create a deterministic rendered answer key for offline grading of the generated deck edits."""
    e = expected[role]
    doc = fitz.open()
    w, h = 960, 540
    navy = (0.11, 0.18, 0.25)
    gray = (0.36, 0.42, 0.48)
    bg = (0.97, 0.98, 0.99)
    def page(title, kicker):
        p = doc.new_page(width=w, height=h)
        p.draw_rect(fitz.Rect(0, 0, w, h), color=bg, fill=bg)
        p.insert_text((54, 42), title, fontsize=23, fontname="helv", color=navy)
        p.insert_text((56, 64), kicker, fontsize=10, fontname="helv", color=gray)
        p.draw_line((54, 75), (906, 75), color=(0.82, 0.85, 0.88), width=1)
        return p
    p = page(e["title"], "NORTHSTAR INTERNAL REVIEW • DECEMBER 2026")
    p.draw_rect(fitz.Rect(55, 118, 905, 236), color=_color(e["banner_rgb"]), fill=_color(e["banner_rgb"]))
    p.insert_text((150, 184), "NORTHSTAR QUARTERLY REVIEW", fontsize=26, fontname="helv", color=(1, 1, 1))
    p.insert_text((190, 275), "Operating outcomes, investment priorities and delivery plan", fontsize=16, fontname="helv", color=navy)
    p.insert_text((56, 486), "Prepared for executive review", fontsize=9, fontname="helv", color=gray)

    def draw_table(p, is_finance):
        if is_finance:
            table_data = (["Quarter", "Revenue ($M)", "Gross margin", "EBITDA ($M)"],
                          ["Q1", "82.4", "18.2%", "11.5"], ["Q2", "96.4", "20.1%", "15.2"],
                          ["Q3", "107.3", "22.6%", "19.6"], ["Q4", "128.7", "23.2%", "31.2"])
        else:
            table_data = (["Model", "Display", "Battery (mAh)", "Weight (kg)", "Launch price"],
                          ["Helios Go", "14-inch OLED", "4100", "1.28", "$899"],
                          ["Helios Pro", "16-inch OLED", "5300", "1.45", "$1,299"],
                          ["Helios Max", "16-inch OLED", "6100", "1.62", "$1,699"],
                          ["Helios Studio", "17-inch OLED", "6800", "1.94", "$2,099"])
        top, row_h = 120, 52
        cols = len(table_data[0])
        col_w = 850 / cols
        for r, row in enumerate(table_data):
            for c, cell in enumerate(row):
                x0, y0 = 55 + c * col_w, top + r * row_h
                fill = (0.17, 0.29, 0.39) if r == 0 else ((1.0, 0.93, 0.66) if (is_finance and r == 4) or (not is_finance and r == 3) else (1, 1, 1))
                p.draw_rect(fitz.Rect(x0, y0, x0 + col_w, y0 + row_h), color=(0.78, 0.81, 0.84), fill=fill, width=0.7)
                p.insert_text((x0 + 8, y0 + 31), str(cell), fontsize=10, fontname="hebo" if (r == 0 or (is_finance and r == 4) or (not is_finance and r == 3)) else "helv",
                              color=(1, 1, 1) if r == 0 else navy)
        p.insert_text((56, 430), "Values reconciled to the approved close memo.", fontsize=11, fontname="helv", color=gray)

    if role == "a":
        p = page("Quarterly Operating Results", "FINANCE • BOARD PACKET")
        draw_table(p, True)
        p = page("Performance Drivers", "REVENUE AND MARGIN TRENDS")
        imgs = ("chart_rev.png", "chart_margin.png")
    else:
        p = page("Product Overview", "DESIGN • DISPLAY • MOBILITY")
        p.insert_text((56, 103), "A flexible platform for modern teams", fontsize=16, fontname="hebo", color=navy)
        imgs = ("prod_front.png", "prod_side.png")
    for filename, x in zip(imgs, (55, 505)):
        p.insert_image(fitz.Rect(x, 130, x + 400, 355), filename=str(assets / "guest" / f"in_{role}" / filename))
    p.insert_text((56, 425), "All objects remain within the slide safe area.", fontsize=11, fontname="helv", color=gray)

    if role == "b":
        p = page("Launch Parameters", "ENGINEERING SPECIFICATIONS")
        draw_table(p, False)

    p = page("Management Summary" if role == "a" else "Launch Readout", "KEY OBSERVATIONS AND ACTIONS" if role == "a" else "PUBLIC RELEASE • SPEAKER SUMMARY")
    y = 125
    for i, point in enumerate(e["points"], 1):
        lines = [point[j:j+105] for j in range(0, len(point), 105)]
        p.insert_text((70, y), f"{i}.", fontsize=13, fontname="hebo", color=navy)
        p.insert_textbox(fitz.Rect(105, y - 16, 890, y + 54), " ".join(lines), fontsize=13, fontname="helv", color=navy)
        y += 78
    p.insert_text((56, 470), "CONFIDENTIAL • INTERNAL USE", fontsize=9, fontname="helv", color=gray)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def _ground_truth(root: Path):
    guest, private = build_assets(root)
    expected = json.loads((private / "expected.json").read_text(encoding="utf-8"))
    for role in ("a", "b"):
        pptx = guest / f"out_{role}" / ("Q4_Finance_Final.pptx" if role == "a" else "Product_Launch_Final.pptx")
        _truth_pptx(pptx, role, root, expected)
        _truth_pdf(guest / f"out_{role}" / ("Q4_Finance_Final.pdf" if role == "a" else "Product_Launch_Final.pdf"), role, root, expected)
    return guest, expected


def _check(root: Path):
    guest, expected = _ground_truth(root)
    scores = {}
    for role in ("a", "b"):
        pptx = guest / f"out_{role}" / ("Q4_Finance_Final.pptx" if role == "a" else "Product_Launch_Final.pptx")
        pdf = guest / f"out_{role}" / ("Q4_Finance_Final.pdf" if role == "a" else "Product_Launch_Final.pdf")
        scores[role] = grade(pptx, pdf, role, expected, root / "rendered" / role)
    return scores


def gates():
    import os
    from pathlib import Path
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="conc02-gates-") as temp:
        base = Path(temp)
        os.environ["PARAGUI_TASK_ASSETS"] = str(base / "base-assets")
        pristine_guest, pristine_private = build_assets(base / "pristine")
        pristine_expected = json.loads((pristine_private / "expected.json").read_text(encoding="utf-8"))
        pristine_scores = {}
        for role in ("a", "b"):
            pptx = pristine_guest / f"out_{role}" / ("Q4_Finance_Final.pptx" if role == "a" else "Product_Launch_Final.pptx")
            pdf = pristine_guest / f"out_{role}" / ("Q4_Finance_Final.pdf" if role == "a" else "Product_Launch_Final.pdf")
            pristine_scores[role] = grade(pptx, pdf, role, pristine_expected, base / "rendered-pristine" / role)
        g1 = all(pristine_scores[r]["score"] < 1.0 for r in ("a", "b"))
        ab = _check(base / "ab")
        ba = _check(base / "ba")
        g2 = all(ab[r]["score"] == 1.0 for r in ("a", "b"))
        g3 = all(ba[r]["score"] == 1.0 for r in ("a", "b"))
        # A focus-preemption race sends an A title edit to B's active presentation.
        race = _check(base / "race")
        race_b_path = base / "race/guest/out_b/Product_Launch_Final.pptx"
        race_b = Presentation(str(race_b_path))
        _set_text(_shape(race_b.slides[0], "SlideTitle"), "Q4 2026 Financial Review", 27, True)
        race_b.save(str(race_b_path))
        race_expected = json.loads((base / "race/private/expected.json").read_text(encoding="utf-8"))
        race["b"] = grade(race_b_path, base / "race/guest/out_b/Product_Launch_Final.pdf", "b",
                           race_expected, base / "rendered-race" / "b")
        g4 = not all(race[r]["score"] == 1.0 for r in ("a", "b"))
    return {"gate1_pristine_fail": g1, "gate2_gt_seq_ab_exists": g2,
            "gate3_gt_seq_ba_exists": g3, "gate4_gt_naive_race_corrupts": g4,
            "gate5_fixture_feasible": g2 and g3,
            "fixture_elapsed_s": round(time.perf_counter() - started, 3),
            "gate5_real_tool_timing": False, "conc_role_timeout_s": 7200,
            "note": "Gate 5 requires a real Guest reference replay; fixture score is not timing evidence."}

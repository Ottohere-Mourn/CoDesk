"""Build English-only source decks and visual inputs for CONC-02."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt


COLORS = {"a": (0x1B, 0x5E, 0x20), "b": (0x0D, 0x47, 0xA1)}
A_POINTS = [
    "Revenue rose 18% quarter over quarter as enterprise renewals and channel expansion offset slower consumer demand.",
    "Gross margin reached 23.2% after supply-chain costs normalized; disciplined pricing contributed more than temporary accrual reversals.",
    "Net cash generation funded the expanded infrastructure plan while preserving the board's liquidity floor.",
]
A_NOTES = "The margin step-up is recurring only if supplier rebates remain within the contracted tier; do not annualize the one-time inventory release."
B_POINTS = [
    "Helios Max leads the lineup with a 16-inch OLED display, 32 GB memory, and a 6100 mAh battery.",
    "Launch inventory is staged across three fulfillment hubs, with priority allocation reserved for enterprise pilots.",
    "Regional certification remains on the critical path, so initial sell-through targets should be treated as gated rather than committed.",
]
B_NOTES = "The pre-order mix is 42% Pro and 31% Max; do not publish a shipment date before the regional safety review is complete."


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _make_visual(path: Path, kind: str, title: str):
    im = Image.new("RGB", (640, 360), "white")
    d = ImageDraw.Draw(im)
    navy = (28, 50, 75)
    teal = (22, 146, 132)
    d.rectangle((0, 0, 639, 54), fill=navy)
    d.text((26, 15), title, fill="white", font=_font(23))
    if kind == "chart":
        d.line((70, 290, 590, 290), fill=(110, 125, 140), width=2)
        d.line((70, 80, 70, 290), fill=(110, 125, 140), width=2)
        points = [(80, 250), (170, 225), (260, 205), (350, 173), (440, 153), (560, 105)]
        if "Margin" in title:
            points = [(80, 245), (170, 232), (260, 221), (350, 188), (440, 160), (560, 125)]
        d.line(points, fill=teal, width=5)
        for x, y in points:
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=teal)
        for i, lab in enumerate(("Q1", "Q2", "Q3", "Q4", "Plan", "Outlook")):
            d.text((76 + i * 82, 305), lab, fill=navy, font=_font(14))
        d.text((90, 75), "Quarterly performance", fill=(80, 92, 105), font=_font(15))
    else:
        d.rounded_rectangle((120, 95, 520, 278), radius=18, fill=(222, 232, 240), outline=navy, width=3)
        if "Front" in title:
            d.rectangle((155, 125, 488, 252), fill=(19, 30, 43), outline=(80, 100, 120), width=3)
            d.rectangle((171, 139, 472, 236), fill=(78, 128, 154))
            d.text((190, 170), "HELIOS DISPLAY", fill="white", font=_font(22))
            d.ellipse((300, 248, 340, 268), fill=(160, 170, 178))
        else:
            d.polygon([(180, 160), (455, 145), (500, 252), (155, 266)], fill=(26, 37, 49), outline=navy)
            d.line((183, 167, 455, 153), fill=(142, 178, 197), width=3)
            d.rectangle((265, 258, 375, 272), fill=(150, 161, 170))
    im.save(path)


def _hex(rgb):
    return "#%02X%02X%02X" % rgb


def _shape_name(shape, name):
    try:
        shape._element.nvSpPr.cNvPr.set("name", name)
    except Exception:
        pass


def _text(slide, name, x, y, w, h, value, size=22, bold=False, color=(30, 44, 58), align=PP_ALIGN.LEFT):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    _shape_name(shape, name)
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.08)
    frame.margin_right = Inches(0.08)
    frame.margin_top = Inches(0.04)
    frame.margin_bottom = Inches(0.04)
    p = frame.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = value
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*color)
    run.font.name = "Liberation Sans"
    return shape


def _slide_base(prs, title, kicker):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(248, 250, 252)
    _text(slide, "SlideTitle", 0.7, 0.42, 11.7, 0.65, title, 27, True, (27, 43, 60))
    _text(slide, "Kicker", 0.76, 1.05, 11.4, 0.34, kicker, 12, False, (89, 105, 120))
    _text(slide, "Footer", 0.76, 6.72, 11.8, 0.2, "NORTHSTAR INTERNAL • DECEMBER 2026", 9, False, (110, 122, 132))
    return slide


def _add_banner(slide):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.72), Inches(1.74), Inches(11.9), Inches(1.35))
    _shape_name(sh, "CoverBanner")
    sh.fill.solid()
    sh.fill.fore_color.rgb = RGBColor(138, 145, 152)
    sh.line.fill.background()
    _text(slide, "BannerLabel", 1.0, 2.03, 10.7, 0.72, "NORTHSTAR QUARTERLY REVIEW", 25, True, (255, 255, 255), PP_ALIGN.CENTER)


def _table(slide, rows, cols, x, y, w, h, values, name="DataTable"):
    shape = slide.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w), Inches(h))
    _shape_name(shape, name)
    table = shape.table
    table.first_row = True
    for r in range(rows):
        for c in range(cols):
            cell = table.cell(r, c)
            cell.text = str(values[r][c])
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.05)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(*( (43, 73, 99) if r == 0 else (255, 255, 255) ))
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.name = "Liberation Sans"
                    run.font.size = Pt(13 if r else 14)
                    run.font.bold = bool(r == 0)
                    run.font.color.rgb = RGBColor(*( (255, 255, 255) if r == 0 else (39, 52, 66) ))
    return table


def _make_deck(path: Path, role: str, images: dict[str, Path]):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    if role == "a":
        s1 = _slide_base(prs, "Q4 Financial Briefing", "FINANCE • BOARD PACKET • VERSION 1.7")
        _add_banner(s1)
        _text(s1, "CoverSub", 1.2, 3.43, 10.8, 0.7, "Quarterly performance, cash discipline and outlook", 19, False, (57, 70, 83), PP_ALIGN.CENTER)
        s2 = _slide_base(prs, "Quarterly Operating Results", "Reported values include preliminary accruals")
        vals = [["Quarter", "Revenue ($M)", "Gross margin", "EBITDA ($M)"], ["Q1", "82.4", "18.2%", "11.5"],
                ["Q2", "92.1", "20.1%", "15.2"], ["Q3", "107.3", "21.1%", "19.6"], ["Q4", "124.0", "23.2%", "29.4"]]
        _table(s2, 5, 4, 0.95, 1.65, 11.4, 3.45, vals)
        _text(s2, "TableNote", 0.95, 5.35, 11.4, 0.6, "Values shown in USD millions unless otherwise noted. Final figures require review against the close memo.", 13, False, (79, 93, 108))
        s3 = _slide_base(prs, "Performance Drivers", "REVENUE AND MARGIN TRENDS")
        _text(s3, "ChartPlaceholderA", 0.9, 1.6, 5.5, 4.65, "Insert the revenue trend chart here", 17, False, (145, 153, 160), PP_ALIGN.CENTER)
        _text(s3, "ChartPlaceholderB", 6.9, 1.6, 5.5, 4.65, "Insert the margin trend chart here", 17, False, (145, 153, 160), PP_ALIGN.CENTER)
        _text(s3, "BottomCaption", 0.9, 6.35, 11.6, 0.46, "All values are provisional until finance close approval.", 12, False, (85, 98, 110))
        s4 = _slide_base(prs, "Management Summary", "KEY OBSERVATIONS AND ACTIONS")
        _text(s4, "SummaryBody", 1.0, 2.2, 11.2, 1.0, "Summary points will be inserted after the operating review.", 30, False, (41, 55, 70))
        _text(s4, "SummaryFooter", 1.0, 6.25, 11.0, 0.35, "CONFIDENTIAL • INTERNAL USE", 11, True, (87, 96, 105))
        notes = "Preliminary close notes are pending review."
        title = "Q4_Finance_Final.pptx"
    else:
        s1 = _slide_base(prs, "Project Helios", "PRODUCT MARKETING • LAUNCH PACKET • VERSION 0.9")
        _add_banner(s1)
        _text(s1, "CoverSub", 1.2, 3.43, 10.8, 0.7, "Premium hardware platform launch overview", 19, False, (57, 70, 83), PP_ALIGN.CENTER)
        s2 = _slide_base(prs, "Launch Parameters", "ENGINEERING SPECIFICATIONS • REVISION 4")
        vals = [["Model", "Display", "Battery (mAh)", "Weight (kg)", "Launch price"],
                ["Helios Go", "14-inch OLED", "4100", "1.28", "$899"],
                ["Helios Pro", "16-inch OLED", "5200", "1.45", "$1,249"],
                ["Helios Max", "16-inch OLED", "5900", "1.68", "$1,699"],
                ["Helios Studio", "17-inch OLED", "6800", "1.94", "$2,099"]]
        _table(s2, 5, 5, 0.78, 1.66, 11.8, 3.65, vals)
        _text(s2, "TableNote", 0.82, 5.45, 11.5, 0.5, "Configuration values are subject to regional certification and final packaging review.", 13, False, (79, 93, 108))
        s3 = _slide_base(prs, "Product Overview", "DESIGN • DISPLAY • MOBILITY")
        _text(s3, "ProductTitle", 0.95, 1.55, 11.4, 0.45, "A flexible platform for modern teams", 21, True, (40, 57, 76))
        _text(s3, "ProductImagePlaceholderA", 0.9, 2.12, 5.5, 3.75, "Insert front view", 17, False, (145, 153, 160), PP_ALIGN.CENTER)
        _text(s3, "ProductImagePlaceholderB", 6.9, 2.12, 5.5, 3.75, "Insert side view", 17, False, (145, 153, 160), PP_ALIGN.CENTER)
        _text(s3, "BottomCaption", 0.9, 6.35, 11.6, 0.46, "Product images must remain inside the safe area.", 12, False, (85, 98, 110))
        s4 = _slide_base(prs, "Launch Readout", "PUBLIC RELEASE • SPEAKER SUMMARY")
        _text(s4, "SummaryBody", 1.0, 2.2, 11.2, 1.0, "Launch highlights will be inserted after regional review.", 30, False, (41, 55, 70))
        _text(s4, "SummaryFooter", 1.0, 6.25, 11.0, 0.35, "NORTHSTAR PRODUCT GROUP", 11, True, (87, 96, 105))
        notes = "Launch notes are pending regional review."
        title = "Product_Launch_Final.pptx"
    try:
        s4.notes_slide.notes_text_frame.text = notes
    except Exception as exc:
        raise RuntimeError("python-pptx notes support is required to create the draft") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)


def build(destination: Path):
    dest = Path(destination)
    guest = dest / "guest"
    for role, color in COLORS.items():
        (guest / f"in_{role}").mkdir(parents=True, exist_ok=True)
        im = Image.new("RGB", (320, 200), color)
        im.save(guest / f"in_{role}" / f"brand_swatch_{role}.png")
    _make_visual(guest / "in_a/chart_rev.png", "chart", "Quarterly Revenue ($M)")
    _make_visual(guest / "in_a/chart_margin.png", "chart", "Gross Margin (%)")
    _make_visual(guest / "in_b/prod_front.png", "product", "Helios • Front View")
    _make_visual(guest / "in_b/prod_side.png", "product", "Helios • Side View")
    a_memo = """FINANCE REVIEW MEMO — DECEMBER 2026

Cover title: Q4 2026 Financial Review

Correct the four preliminary table values:
- Q2 Revenue ($M): 96.4
- Q3 Gross margin: 22.6%
- Q4 Revenue ($M): 128.7
- Q4 EBITDA ($M): 31.2

Highlight every cell in the quarter with the highest revenue. Add both supplied charts to slide 3 and keep the bottom caveat visible.

Slide 4 key points:
1. Revenue rose 18% quarter over quarter as enterprise renewals and channel expansion offset slower consumer demand.
2. Gross margin reached 23.2% after supply-chain costs normalized; disciplined pricing contributed more than temporary accrual reversals.
3. Net cash generation funded the expanded infrastructure plan while preserving the board's liquidity floor.

Speaker note: The margin step-up is recurring only if supplier rebates remain within the contracted tier; do not annualize the one-time inventory release.
"""
    b_memo = """PRODUCT LAUNCH MEMO — DECEMBER 2026

Cover title: Project Helios v2.4 Launch

Correct the four preliminary specifications:
- Helios Pro battery (mAh): 5300
- Helios Pro launch price: $1,299
- Helios Max battery (mAh): 6100
- Helios Max weight (kg): 1.62

Move the product overview slide before the launch-parameters slide. Highlight every cell in the Helios Max row.

Slide 4 key points:
1. Helios Max leads the lineup with a 16-inch OLED display, 32 GB memory, and a 6100 mAh battery.
2. Launch inventory is staged across three fulfillment hubs, with priority allocation reserved for enterprise pilots.
3. Regional certification remains on the critical path, so initial sell-through targets should be treated as gated rather than committed.

Speaker note: The pre-order mix is 42% Pro and 31% Max; do not publish a shipment date before the regional safety review is complete.
"""
    (guest / "in_a/finance_memo.txt").write_text(a_memo, encoding="utf-8")
    (guest / "in_b/launch_memo.txt").write_text(b_memo, encoding="utf-8")
    _make_deck(guest / "out_a/Q4_Finance_Final.pptx", "a", {})
    _make_deck(guest / "out_b/Product_Launch_Final.pptx", "b", {})
    expected = {
        "a": {"title": "Q4 2026 Financial Review", "banner_rgb": list(COLORS["a"]),
              "corrections": {"Q2|Revenue ($M)": "96.4", "Q3|Gross margin": "22.6%", "Q4|Revenue ($M)": "128.7", "Q4|EBITDA ($M)": "31.2"},
              "highlight_row": "Q4", "images": ["chart_rev.png", "chart_margin.png"],
              "points": A_POINTS, "notes": A_NOTES},
        "b": {"title": "Project Helios v2.4 Launch", "banner_rgb": list(COLORS["b"]),
              "corrections": {"Helios Pro|Battery (mAh)": "5300", "Helios Pro|Launch price": "$1,299", "Helios Max|Battery (mAh)": "6100", "Helios Max|Weight (kg)": "1.62"},
              "highlight_row": "Helios Max", "images": ["prod_front.png", "prod_side.png"],
              "points": B_POINTS, "notes": B_NOTES},
    }
    for role in ("a", "b"):
        for image in expected[role]["images"]:
            expected[role]["image_sha256"] = expected[role].get("image_sha256", []) + [hashlib.sha256((guest / f"in_{role}" / image).read_bytes()).hexdigest()]
    private = dest / "private"
    private.mkdir(parents=True, exist_ok=True)
    (private / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return guest, private


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("destination", type=Path)
    args = ap.parse_args()
    guest, private = build(args.destination)
    print(f"guest-assets={guest}")
    print(f"private-oracle={private}")


if __name__ == "__main__":
    main()

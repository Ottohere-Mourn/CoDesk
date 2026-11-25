"""Generate English-only CONC-03 receipts, safety icons, and slide draft."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


TITLES = [
    "Personal Protective Equipment",
    "Recognize and Report Hazards",
    "Keep Emergency Exits Clear",
]
FOOTERS = ["SAF-01", "SAF-02", "SAF-03"]
ICON_FILES = ["icon_helmet.png", "icon_hazard.png", "icon_exit.png"]


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _receipt(path: Path, claim_id: str, total: str, verified: bool) -> None:
    im = Image.new("RGB", (1000, 1300), "#F2F4F6")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((100, 55, 900, 1245), radius=28, fill="white", outline="#D5DDE5", width=4)
    d.rectangle((100, 55, 900, 250), fill="#16324F")
    d.text((150, 100), "NORTHSTAR BUSINESS TRAVEL", fill="white", font=_font(35))
    d.text((153, 165), "ITEMIZED EXPENSE RECEIPT", fill="#C9D8E6", font=_font(20))
    d.text((150, 300), "Claim reference", fill="#607080", font=_font(19))
    d.text((150, 335), claim_id, fill="#162B3D", font=_font(30))
    d.text((150, 410), "Merchant", fill="#607080", font=_font(19))
    d.text((150, 445), "Harbor & Pine Conference Center", fill="#162B3D", font=_font(24))
    d.text((150, 510), "Date", fill="#607080", font=_font(19))
    d.text((150, 545), "November 18, 2026", fill="#162B3D", font=_font(24))
    d.line((145, 610, 855, 610), fill="#CBD4DD", width=3)
    d.text((150, 645), "Description", fill="#607080", font=_font(19))
    d.text((150, 685), "Registration, local transit, and meals", fill="#162B3D", font=_font(21))
    d.text((150, 755), "Subtotal", fill="#4A5D70", font=_font(21))
    d.text((720, 755), total, fill="#162B3D", font=_font(24))
    d.text((150, 815), "Tax and fees", fill="#4A5D70", font=_font(21))
    d.text((720, 815), "$0.00", fill="#162B3D", font=_font(24))
    d.line((145, 870, 855, 870), fill="#CBD4DD", width=3)
    d.text((150, 900), "AMOUNT PAID", fill="#16324F", font=_font(23))
    d.text((650, 890), total, fill="#16324F", font=_font(35))
    # A textured, rotated seal visually authenticates the scanned original.
    if verified:
        d.ellipse((590, 1000, 835, 1170), outline="#C62828", width=11)
        d.ellipse((602, 1012, 823, 1158), outline="#C62828", width=3)
        d.text((623, 1055), "VERIFIED", fill="#C62828", font=_font(29))
        d.text((651, 1100), "FINANCE", fill="#C62828", font=_font(18))
    else:
        d.ellipse((590, 1000, 835, 1170), outline="#C62828", width=11)
        d.ellipse((602, 1012, 823, 1158), outline="#C62828", width=3)
        d.text((630, 1055), "REVIEWED", fill="#C62828", font=_font(27))
        d.text((651, 1100), "FINANCE", fill="#C62828", font=_font(18))
    im.save(path)


def _icon(path: Path, kind: str) -> None:
    im = Image.new("RGBA", (320, 320), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    if kind == "helmet":
        d.arc((55, 57, 265, 250), 180, 360, fill="#173B57", width=24)
        d.rounded_rectangle((48, 170, 272, 230), radius=20, fill="#F9C846", outline="#173B57", width=10)
        d.rectangle((145, 72, 174, 173), fill="#173B57")
        d.rectangle((73, 230, 246, 252), fill="#173B57")
    elif kind == "hazard":
        d.polygon([(160, 35), (292, 274), (28, 274)], fill="#F5BE36", outline="#173B57", width=13)
        d.rounded_rectangle((148, 105, 172, 200), radius=10, fill="#173B57")
        d.ellipse((148, 218, 172, 242), fill="#173B57")
    else:
        d.rounded_rectangle((60, 48, 255, 272), radius=22, outline="#173B57", width=15)
        d.rectangle((110, 90, 202, 235), fill="#2E9D6F")
        d.line((142, 164, 232, 164), fill="white", width=17)
        d.polygon([(217, 131), (262, 164), (217, 197)], fill="white")
    im.save(path)


def _text(slide, name: str, x: float, y: float, w: float, h: float, value: str,
          size: int, *, bold: bool = False, color=(31, 49, 66)):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    shape.name = name
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = value
    run.font.name = "Liberation Sans"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*color)
    return shape


def _draft_deck(path: Path) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    for i, title in enumerate(TITLES, start=1):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(246, 249, 251)
        topbar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.18))
        topbar.fill.solid()
        topbar.fill.fore_color.rgb = RGBColor(30, 104, 105)
        _text(slide, f"Title_{i}", 0.78, 0.48, 11.7, 0.65, f"Safety Topic {i}", 27, bold=True)
        _text(slide, f"Body_{i}", 0.85, 1.63, 7.7, 3.1,
              "Replace this draft text with the approved safety guidance. Keep instructions concise, actionable, and easy to scan.", 20)
        _text(slide, f"Footer_{i}", 0.85, 6.67, 2.4, 0.42, f"DRAFT-{i:02d}", 15, bold=True, color=(85, 100, 114))
        placeholder = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.15), Inches(2.0), Inches(2.55), Inches(2.55))
        placeholder.name = f"IconPlaceholder_{i}"
        placeholder.fill.solid()
        placeholder.fill.fore_color.rgb = RGBColor(230, 237, 241)
        placeholder.line.color.rgb = RGBColor(190, 204, 214)
        _text(slide, f"IconHint_{i}", 9.38, 2.95, 2.1, 0.5, "Insert safety icon", 14, color=(96, 112, 125))
    prs.save(path)


def build(destination: Path) -> None:
    root = Path(destination)
    a = root / "guest" / "in_a" / "receipts"
    b = root / "guest" / "in_b" / "icons"
    drafts = root / "guest" / "out_b"
    a.mkdir(parents=True, exist_ok=True)
    b.mkdir(parents=True, exist_ok=True)
    drafts.mkdir(parents=True, exist_ok=True)
    _receipt(a / "receipt_EXP-401.png", "EXP-401", "$420.00", True)
    _receipt(a / "receipt_EXP-402.png", "EXP-402", "$395.00", True)
    _receipt(a / "receipt_EXP-403.png", "EXP-403", "$185.00", True)
    for kind, filename in zip(("helmet", "hazard", "exit"), ICON_FILES):
        _icon(b / filename, kind)
    (root / "guest" / "in_b" / "safety_spec.txt").write_text(
        "Safety Briefing Deck Requirements\n\n"
        "Slide 1 title: Personal Protective Equipment\nFooter: SAF-01\nIcon: icon_helmet.png\n"
        "Guidance: Wear a fitted helmet, eye protection, and task-appropriate gloves before entering the work area.\n\n"
        "Slide 2 title: Recognize and Report Hazards\nFooter: SAF-02\nIcon: icon_hazard.png\n"
        "Guidance: Stop work, isolate the area, and report spills, exposed wiring, or unstable loads to the shift lead.\n\n"
        "Slide 3 title: Keep Emergency Exits Clear\nFooter: SAF-03\nIcon: icon_exit.png\n"
        "Guidance: Keep exit routes and door swing areas clear; use the nearest marked exit during an alarm.\n\n"
        "Place one supplied icon on the right side of each slide, fully within the slide and clear of title, body, and footer text.",
        encoding="utf-8")
    _draft_deck(drafts / "Safety_Brief.pptx")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("destination", type=Path)
    build(ap.parse_args().destination)


if __name__ == "__main__":
    main()

"""Generate the English-only raster onboarding packets; values stay host-side."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CASE=Path(__file__).resolve().parents[1]
def _font(size=18,bold=False):
    names=("DejaVuSans-Bold.ttf","arialbd.ttf") if bold else ("DejaVuSans.ttf","arial.ttf")
    for n in names:
        try:return ImageFont.truetype(n,size)
        except OSError:pass
    return ImageFont.load_default()

def build(destination:Path)->Path:
    expected=json.loads((CASE/"private/expected.json").read_text(encoding="utf-8"))
    out=Path(destination)/"CONC-05/guest/in_a/onboarding_forms";out.mkdir(parents=True,exist_ok=True)
    for i,row in enumerate(expected["clients"],1):
        im=Image.new("RGB",(1000,690),"#f6f8fb");d=ImageDraw.Draw(im)
        d.rounded_rectangle((34,30,966,658),radius=18,fill="white",outline="#cbd5e1",width=3)
        d.rectangle((34,30,966,115),fill="#123b5d")
        d.text((62,52),"NORTHSHORE COMMERCIAL BANK",font=_font(24,True),fill="white")
        d.text((64,132),"CORPORATE ACCOUNT APPLICATION",font=_font(20,True),fill="#123b5d")
        d.text((64,170),f"APPLICATION REF  AC-{2026}-{i:04d}",font=_font(14,True),fill="#64748b")
        fields=[("LEGAL COMPANY NAME",row["company_name"]),("INTERNATIONAL ACCOUNT (IBAN)",row["iban"]),("TAX IDENTIFICATION NUMBER",row["tax_id"]),("CLIENT SERVICE TIER",row["tier"])]
        y=225
        for label,value in fields:
            d.rounded_rectangle((64,y,936,y+72),radius=7,fill="#f8fafc",outline="#d7dee7",width=2)
            d.text((84,y+8),label,font=_font(12,True),fill="#667085")
            d.text((84,y+32),value,font=_font(22,True),fill="#182b49")
            y+=91
        d.text((64,604),"For authorized business servicing only",font=_font(13),fill="#667085")
        im.save(out/f"application_{i:02d}.png",format="PNG",optimize=True)
    return out

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("destination",type=Path);print(build(ap.parse_args().destination))

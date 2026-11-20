"""FC-07: Commercial Offset Packaging Prepress (4-Channel CMYK Separation TIFF + Inkscape SVG Dieline + ISO 12647-2 TAC [268%, 284%] Equilibrium + SSO Soft-Proof Console)."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    verify_stage_regime_purity,
    audit_protocol_transparency,
    post_json,
    sha256_file,
    write_json,
)

TASK_ID = "FC-07"
PORTAL_PORT = 19470

META = {
    "id": TASK_ID,
    "title": "Commercial Offset Packaging Prepress (CMYK Separation TIFF + Inkscape SVG Dieline + ISO 12647-2 TAC Equilibrium)",
    "domain": "Graphic Arts & Print Prepress Engineering (CMYK Separation Plate + GIMP/PIL + Inkscape SVG + ISO 12647-2 Densitometer)",
    "arena": "Shared 4-Channel CMYK Plate, Vector Dieline SVG & Total Area Ink Coverage Equilibrium",
    "conflict_archetype": "cmy_vs_k_channel_plate_overwrite + iso12647_tac_268_284_equilibrium + dieline_svg_and_proof_png_sync",
    "roles": ("brand_keyart_lead", "regulatory_kplate_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "prepress_pack/cmyk_separations.tiff",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

# Pixel geometry: 1200 x 800 CMYK plate
# Shadow rich-black zone: X in [300:900], Y in [200:560]
# Trim bleed frame: outer 40px border; Fine K-text regulatory band: X in [200:1000], Y in [620:720]
CMY_SHADOW_RANGE_PCT = (176.0, 235.0)
BLEED_CMY_MIN_PCT = 140.0
K_SHADOW_RANGE_PCT = (48.0, 99.0)
REG_TEXT_K_MIN_PCT = 88.0
TAC_SHADOW_BAND_PCT = (268.0, 284.0)

BRAND_STAGES = ("bleed_trim_gate", "cmy_chroma_gate", "barcode_svg_gate", "composite_proof_gate", "full_press_check")
KPLATE_STAGES = ("k_typography_gate", "k_underbase_gate", "diecut_svg_gate", "composite_proof_gate", "full_press_check")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/prepress_pack",
    "cmyk_separations.tiff",
    "dieline_overlay.svg",
    "press_proof_composite.png",
    "#ean13-barcode-group",
    "#die-cut-lines",
    "/api/bench/prepress_densitometer",
    "/api/prepress/submit",
    "/api/prepress/status",
    "176.0",
    "235.0",
    "48.0",
    "99.0",
    "268.0",
    "284.0",
    "full_press_check",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "prepress_pack")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside prepress_pack: {extra_top}")
    pp = workspace / "prepress_pack"
    allowed = {"cmyk_separations.tiff", "dieline_overlay.svg", "press_proof_composite.png"}
    if pp.is_dir():
        extra = sorted(x.name for x in pp.iterdir() if x.name not in allowed)
        if extra:
            errs.append(f"Unexpected non-release files in /workspace/prepress_pack: {extra} (use /tmp or $HOME for temp files)")
    return errs


def inspect_prepress_pack(workspace: Path) -> dict:
    import numpy as np
    from PIL import Image

    pp = workspace / "prepress_pack"
    tiff_p = pp / "cmyk_separations.tiff"
    svg_p = pp / "dieline_overlay.svg"
    proof_p = pp / "press_proof_composite.png"

    for req in (tiff_p, svg_p, proof_p):
        if not req.is_file():
            return {"ok": False, "error": f"Missing {req}"}

    im = Image.open(tiff_p)
    if im.mode != "CMYK" or im.size != (1200, 800):
        return {"ok": False, "error": f"cmyk_separations.tiff must be 1200x800 mode='CMYK', got mode={im.mode}, size={im.size}"}

    arr_pct = np.asarray(im, dtype=np.float64) * (100.0 / 255.0)  # shape (800, 1200, 4)
    shadow = arr_pct[200:560, 300:900, :]
    cmy_shadow_pct = round(float(np.mean(np.sum(shadow[:, :, :3], axis=2))), 2)
    k_shadow_pct = round(float(np.mean(shadow[:, :, 3])), 2)
    tac_shadow_pct = round(cmy_shadow_pct + k_shadow_pct, 2)

    bleed_top = arr_pct[0:40, :, :3]
    bleed_cmy_pct = round(float(np.mean(np.sum(bleed_top, axis=2))), 2)

    reg_band_k = arr_pct[620:720, 200:1000, 3]
    reg_k_p90_pct = round(float(np.percentile(reg_band_k, 90)), 2)

    svg_src = svg_p.read_text(encoding="utf-8", errors="replace")
    barcode_ok = ('id="ean13-barcode-group"' in svg_src and 'data-ean="4006381333931"' in svg_src)
    diecut_ok = ('id="die-cut-lines"' in svg_src and 'stroke="#ff00aa"' in svg_src.lower())
    svg_tac_ok = (f'data-tac-pct="{tac_shadow_pct:.1f}"' in svg_src)

    proof_im = Image.open(proof_p)
    proof_ok = (
        proof_im.size == (1200, 800)
        and proof_p.stat().st_mtime + 0.5 >= max(tiff_p.stat().st_mtime, svg_p.stat().st_mtime)
    )

    return {
        "ok": True,
        "summary": {
            "cmy_shadow_pct": cmy_shadow_pct,
            "k_shadow_pct": k_shadow_pct,
            "tac_shadow_pct": tac_shadow_pct,
            "bleed_cmy_pct": bleed_cmy_pct,
            "reg_text_k_p90_pct": reg_k_p90_pct,
            "barcode_svg_ok": barcode_ok,
            "diecut_svg_ok": diecut_ok,
            "svg_tac_attr_synced": svg_tac_ok,
            "proof_png_synced": proof_ok,
        },
    }


def check_prepress_constraints(info: dict, check_brand: bool, check_kplate: bool, stage: str = "full_press_check") -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid prepress files")]
    errs: list[str] = []
    s = info["summary"]

    if check_brand:
        if s["bleed_cmy_pct"] < BLEED_CMY_MIN_PCT:
            errs.append(f"Outer 40px trim bleed CMY coverage={s['bleed_cmy_pct']}% < {BLEED_CMY_MIN_PCT}%")
        if stage in ("cmy_chroma_gate", "barcode_svg_gate", "composite_proof_gate", "full_press_check"):
            if not (CMY_SHADOW_RANGE_PCT[0] <= s["cmy_shadow_pct"] <= CMY_SHADOW_RANGE_PCT[1]):
                errs.append(f"Hero shadow CMY sum={s['cmy_shadow_pct']}% outside {list(CMY_SHADOW_RANGE_PCT)}%")
        if stage in ("barcode_svg_gate", "composite_proof_gate", "full_press_check"):
            if not s["barcode_svg_ok"]:
                errs.append("dieline_overlay.svg missing #ean13-barcode-group with data-ean='4006381333931'")

    if check_kplate:
        if s["reg_text_k_p90_pct"] < REG_TEXT_K_MIN_PCT:
            errs.append(f"Regulatory band [200:1000, 620:720] K-plate P90={s['reg_text_k_p90_pct']}% < {REG_TEXT_K_MIN_PCT}%")
        if stage in ("k_underbase_gate", "diecut_svg_gate", "composite_proof_gate", "full_press_check"):
            if not (K_SHADOW_RANGE_PCT[0] <= s["k_shadow_pct"] <= K_SHADOW_RANGE_PCT[1]):
                errs.append(f"Hero shadow K-plate mean={s['k_shadow_pct']}% outside {list(K_SHADOW_RANGE_PCT)}%")
        if stage in ("diecut_svg_gate", "composite_proof_gate", "full_press_check"):
            if not s["diecut_svg_ok"]:
                errs.append("dieline_overlay.svg missing #die-cut-lines with magenta stroke='#ff00aa'")

    if stage in ("composite_proof_gate", "full_press_check"):
        if not s["proof_png_synced"]:
            errs.append("press_proof_composite.png not 1200x800 or older than cmyk_separations.tiff / dieline_overlay.svg")
        if not s["svg_tac_attr_synced"]:
            errs.append(f"dieline_overlay.svg root missing data-tac-pct='{s['tac_shadow_pct']:.1f}' matching live TIFF")

    if stage == "full_press_check":
        if not (TAC_SHADOW_BAND_PCT[0] <= s["tac_shadow_pct"] <= TAC_SHADOW_BAND_PCT[1]):
            errs.append(f"Hero shadow Total Area Ink Coverage TAC={s['tac_shadow_pct']}% outside ISO 12647-2 band {list(TAC_SHADOW_BAND_PCT)}%")
    return errs


def run_halftone_rip_simulation(tiff_p: Path, fast_selfval: bool = False) -> dict:
    """Real AM halftone screen moire & dot-gain RIP rasterizer over live 1200x800 CMYK plate."""
    import numpy as np
    from PIL import Image

    im = Image.open(tiff_p)
    arr = np.asarray(im, dtype=np.float64) / 255.0
    yy, xx = np.meshgrid(np.linspace(0, 40.0, 800), np.linspace(0, 60.0, 1200), indexing="ij")
    angles = (0.2618, 1.3090, 0.0, 0.7854)  # 15, 75, 0, 45 deg CMYK halftone screens
    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC07_RIP_S", "295.0"))
    t0 = time.monotonic()
    passes = 0
    dot_gain = 0.0
    while True:
        acc = 0.0
        for ch, ang in enumerate(angles):
            u = xx * np.cos(ang) + yy * np.sin(ang)
            v = -xx * np.sin(ang) + yy * np.cos(ang)
            screen = 0.5 + 0.25 * (np.cos(25.0 * u + 0.1 * passes) + np.cos(25.0 * v))
            dots = (arr[:, :, ch] > screen).astype(np.float64)
            acc += float(np.mean(dots))
        dot_gain = round(acc * 25.0, 3)
        passes += 1
        if time.monotonic() - t0 >= target_s:
            break
    return {"rip_passes": passes, "halftone_density": dot_gain, "elapsed_s": round(time.monotonic() - t0, 2)}


def _render_composite_proof(tiff_p: Path, svg_p: Path, proof_p: Path) -> None:
    from PIL import Image

    base_rgb = Image.open(tiff_p).convert("RGBA")
    with tempfile.TemporaryDirectory() as tmp:
        ov_png = Path(tmp) / "ov.png"
        subprocess.run(
            ["inkscape", str(svg_p), "--export-type=png", f"--export-filename={ov_png}", "-w", "1200", "-h", "800"],
            check=True,
            capture_output=True,
            timeout=45,
        )
        ov_im = Image.open(ov_png).convert("RGBA")
        comp = Image.alpha_composite(base_rgb, ov_im).convert("RGB")
        comp.save(proof_p, format="PNG")


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Prepress Package Layout, ISO 12647-2 Ink Law & Hygiene",
        f"- **Prepress Directory**: {b}/workspace/prepress_pack{b}",
        f"  - Master 4-Channel Plate: {b}cmyk_separations.tiff{b} ({b}1200x800{b}, 8-bit {b}CMYK{b} mode where pixel {b}0..255{b} corresponds to {b}0..100%{b} ink).",
        f"    - Hero shadow densitometer zone: {b}X in [300, 900), Y in [200, 560){b} ({b}arr[200:560, 300:900]{b}).",
        f"    - Outer trim bleed band: top 40px {b}Y in [0, 40){b}.",
        f"    - Regulatory fine-print band: {b}X in [200, 1000), Y in [620, 720){b}.",
        f"  - **ISO 12647-2 Two-Sided Total Area Ink Coverage ({b}TAC{b}) Equilibrium**:",
        f"    - In the hero shadow zone ({b}arr[200:560, 300:900]{b}), {b}TAC_Pct = mean(C% + M% + Y%) + mean(K%){b} MUST lie within **{b}[268.0, 284.0]%{b}** (initial {b}v0{b} plate sits at washed-out {b}219.0%{b}).",
        f"  - Vector Dieline & Overprint SVG: {b}dieline_overlay.svg{b} ({b}1200x800{b} SVG containing root attribute {b}data-tac-pct=\"<tac_shadow_pct_1dec>\"{b}, {b}#ean13-barcode-group{b}, and {b}#die-cut-lines{b}).",
        f"  - Composite Press Soft-Proof: {b}press_proof_composite.png{b} ({b}1200x800{b} PNG composited from {b}cmyk_separations.tiff{b} + Inkscape-rendered {b}dieline_overlay.svg{b}).",
        f"- **Workspace Hygiene**: {b}/workspace/prepress_pack{b} may contain ONLY {b}cmyk_separations.tiff{b}, {b}dieline_overlay.svg{b}, and {b}press_proof_composite.png{b}. Store scripts/temp files in {b}$HOME{b} or {b}$TMPDIR{b}.",
        f"- **SSO Soft-Proof Scope ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & RIP Densitometer API**:",
        f"  - Inspect {b}BRAND_CMY_PLATE{b} / {b}KPLATE_DIELINE{b} under {b}ISO_12647_PCT{b} on the open Chromium SSO session ({b}DISPLAY=:99{b}).",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/prepress_densitometer{b}: ordered 5-stage halftone RIP & densitometer check.",
        f"  - {b}GET http://127.0.0.1:{PORTAL_PORT}/api/prepress/status?subsystem=<subsystem>{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/prepress/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    brand_txt = "\n".join([
        f"# Prepress Work Order — FC-07 ({b}brand_keyart_lead{b})",
        "",
        f"Calibrate the {b}C, M, Y{b} process channels, trim bleed, and EAN-13 barcode vector in {b}/workspace/prepress_pack{b}.",
        "",
        "### Brand & CMY Requirements",
        f"1. Inspect {b}BRAND_CMY_PLATE{b} + {b}ISO_12647_PCT{b} on the Chromium SSO Soft-Proof Console ({b}DISPLAY=:99{b}):",
        f"   - Extend outer 40px top bleed ({b}Y in [0, 40){b}) in {b}cmyk_separations.tiff{b} so mean {b}C% + M% + Y% >= 140.0%{b}.",
        f"   - Calibrate hero shadow ({b}X in [300, 900), Y in [200, 560){b}) {b}C, M, Y{b} channels so {b}cmy_shadow_pct{b} is in **{b}[176.0, 235.0]%{b}** and combined {b}tac_shadow_pct = cmy_shadow_pct + k_shadow_pct{b} lands within **{b}[268.0, 284.0]%{b}**.",
        f"   - Add {b}<g id=\"ean13-barcode-group\" data-ean=\"4006381333931\">...</g>{b} and update root {b}data-tac-pct{b} in {b}dieline_overlay.svg{b}, and render {b}press_proof_composite.png{b}.",
        f"2. Certify ordered stages on {b}POST /api/bench/prepress_densitometer{b} ({b}subsystem='brand_keyart'{b}): {b}bleed_trim_gate -> cmy_chroma_gate -> barcode_svg_gate -> composite_proof_gate -> full_press_check{b}.",
        f"3. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/prepress/submit{b}:",
        f"   {b}{{\"subsystem\": \"brand_keyart\", \"channel_pct\": <cmy_shadow_pct>, \"tac_shadow_pct\": <tac_shadow_pct>, \"proof_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}BRAND_CMY_PLATE{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    k_txt = "\n".join([
        f"# Prepress Work Order — FC-07 ({b}regulatory_kplate_lead{b})",
        "",
        f"Calibrate the {b}K{b} black key plate (shadow underbase + fine regulatory text) and magenta die-cut lines in {b}/workspace/prepress_pack{b}.",
        "",
        "### K-Plate & Dieline Requirements",
        f"1. Inspect {b}KPLATE_DIELINE{b} + {b}ISO_12647_PCT{b} on the Chromium SSO Soft-Proof Console ({b}DISPLAY=:99{b}):",
        f"   - Render crisp regulatory black bars/glyphs in {b}X in [200, 1000), Y in [620, 720){b} on channel {b}K{b} of {b}cmyk_separations.tiff{b} so 90th-percentile {b}K% >= 88.0%{b}.",
        f"   - Calibrate hero shadow ({b}X in [300, 900), Y in [200, 560){b}) {b}K{b} channel so {b}k_shadow_pct{b} is in **{b}[48.0, 99.0]%{b}** and combined {b}tac_shadow_pct = cmy_shadow_pct + k_shadow_pct{b} lands within **{b}[268.0, 284.0]%{b}**.",
        f"   - Add {b}<g id=\"die-cut-lines\" stroke=\"#ff00aa\">...</g>{b} and update root {b}data-tac-pct{b} in {b}dieline_overlay.svg{b}, and render {b}press_proof_composite.png{b}.",
        f"2. Certify ordered stages on {b}POST /api/bench/prepress_densitometer{b} ({b}subsystem='regulatory_kplate'{b}): {b}k_typography_gate -> k_underbase_gate -> diecut_svg_gate -> composite_proof_gate -> full_press_check{b}.",
        f"3. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/prepress/submit{b}:",
        f"   {b}{{\"subsystem\": \"regulatory_kplate\", \"channel_pct\": <k_shadow_pct>, \"tac_shadow_pct\": <tac_shadow_pct>, \"proof_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}KPLATE_DIELINE{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"brand_keyart_lead": brand_txt, "regulatory_kplate_lead": k_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    import numpy as np
    from PIL import Image

    pp = workspace / "prepress_pack"
    pp.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    # v0 CMYK 1200x800: unbleached white top border (bleed=0%), shadow CMY=174.0%, shadow K=45.0% -> v0 TAC=219.0%
    arr = np.zeros((800, 1200, 4), dtype=np.uint8)
    arr[40:760, 40:1160, 0] = int(round(40.0 * 2.55))
    arr[40:760, 40:1160, 1] = int(round(30.0 * 2.55))
    arr[40:760, 40:1160, 2] = int(round(20.0 * 2.55))
    # Hero shadow zone [200:560, 300:900]: C=68%, M=58%, Y=48% -> sum=174%; K=45%
    arr[200:560, 300:900, 0] = int(round(68.0 * 2.55))
    arr[200:560, 300:900, 1] = int(round(58.0 * 2.55))
    arr[200:560, 300:900, 2] = int(round(48.0 * 2.55))
    arr[200:560, 300:900, 3] = int(round(45.0 * 2.55))

    tiff_p = pp / "cmyk_separations.tiff"
    Image.fromarray(arr, mode="CMYK").save(tiff_p, format="TIFF")

    svg_p = pp / "dieline_overlay.svg"
    svg_p.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800" data-tac-pct="219.0">\n'
        '  <rect x="40" y="40" width="1120" height="720" fill="none" stroke="#94a3b8" stroke-width="1"/>\n'
        '</svg>\n',
        encoding="utf-8",
    )
    _render_composite_proof(tiff_p, svg_p, pp / "press_proof_composite.png")

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def render_prepress_plate_png(plate_view: str, unit_mode: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 500), (14, 12, 24))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 490)], outline=(244, 114, 182), width=2)
    dr.text((24, 24), f"OFFSET PREPRESS SSO SOFT-PROOF CONSOLE  |  Plate: {plate_view}  |  Scale: {unit_mode}", fill=(244, 114, 182))
    dr.text((24, 54), "ISO 12647-2 Shadow Zone [300:900, 200:560] Equilibrium: TAC (C%+M%+Y%+K%) in [268.0, 284.0]%", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)

    y = 112
    if unit_mode != "ISO_12647_PCT":
        dr.text((28, y), "[RAW_8BIT_PREVIEW — Switch to ISO_12647_PCT for Exact Ink Coverage Percentages & EAN]", fill=(251, 191, 36))
    elif plate_view == "BRAND_CMY_PLATE":
        rows = [
            "Top 40px Bleed Gate : Y in [0, 40) mean(C% + M% + Y%) >= 140.0%",
            "Shadow CMY Chroma   : arr[200:560, 300:900] mean(C% + M% + Y%) in [176.0, 235.0]%",
            "Barcode SVG Element : <g id='ean13-barcode-group' data-ean='4006381333931'>...</g>",
            "ISO 12647-2 TAC Band: Shadow CMY% + K% must land in [268.0, 284.0]%",
        ]
        for r in rows:
            dr.text((32, y), r, fill=(241, 245, 249))
            y += 34
    else:
        rows = [
            "Regulatory K-Text   : arr[620:720, 200:1000] 90th-percentile K% >= 88.0%",
            "Shadow K Underbase  : arr[200:560, 300:900] mean(K%) in [48.0, 99.0]%",
            "Die-Cut SVG Element : <g id='die-cut-lines' stroke='#ff00aa'>...</g>",
            "ISO 12647-2 TAC Band: Shadow CMY% + K% must land in [268.0, 284.0]%",
        ]
        for r in rows:
            dr.text((32, y), r, fill=(241, 245, 249))
            y += 34

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Offset Prepress Soft-Proof — FC-07</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 7px 12px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #db2777; }
    #msg { color: #f472b6; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>PLATE:</strong>
    <button onclick="setPp({plate_view:'BRAND_CMY_PLATE'})">BRAND_CMY_PLATE</button>
    <button onclick="setPp({plate_view:'KPLATE_DIELINE'})">KPLATE_DIELINE</button>
    <strong>SCALE:</strong>
    <button onclick="setPp({unit_mode:'ISO_12647_PCT'})">ISO_12647_PCT</button>
    <button onclick="setPp({unit_mode:'RAW_8BIT_PREVIEW'})">RAW_8BIT_PREVIEW</button>
    <button onclick="expPp()">Export Densitometer Spec CSV (/home/gui/Downloads/prepress_spec.csv)</button>
    <span id="msg">Soft-Proof SSO Active</span>
  </div>
  <canvas id="pp-canvas" width="1220" height="500"></canvas>
  <!-- Public protocol tokens:
       /workspace/prepress_pack cmyk_separations.tiff dieline_overlay.svg press_proof_composite.png
       #ean13-barcode-group #die-cut-lines
       /api/bench/prepress_densitometer /api/prepress/submit /api/prepress/status
       176.0 235.0 48.0 99.0 268.0 284.0 full_press_check -->
  <script>
    function drawPp() {
      const cv = document.getElementById('pp-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/pp_plate.png?t=' + Date.now();
    }
    async function setPp(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.plate_view || '') + ' / ' + (d.unit_mode || '');
      drawPp();
    }
    async function expPp() {
      const r = await fetch('/api/ui/export_csv', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Exported ' + (d.path || '') + ' [' + (d.plate_view || '') + ']';
      drawPp();
    }
    drawPp();
    setInterval(drawPp, 3500);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    state_lock = threading.Lock()
    sub_locks = {"brand_keyart": threading.Lock(), "regulatory_kplate": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"plate_view": "BRAND_CMY_PLATE", "unit_mode": "ISO_12647_PCT"},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"brand_keyart": {}, "regulatory_kplate": {}},
        "qualified_stages": {"brand_keyart": {}, "regulatory_kplate": {}},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a): return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc07_sso")
                return bool(m and m.value == sso_cookie_val)
            except Exception:
                return False

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            qs = parse_qs(parsed.query)
            if p == "/health":
                self._json(200, {"ok": True, "task_id": TASK_ID})
                return
            if p == "/":
                if (qs.get("sso_boot") or [""])[0] == sso_boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"fc07_sso={sso_cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if p == "/ui/pp_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; inspect Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_prepress_plate_png(pstate["ui_session"]["plate_view"], pstate["ui_session"]["unit_mode"])
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/prepress/status":
                sub_q = (qs.get("subsystem") or [""])[0].strip().lower()
                if sub_q not in ("brand_keyart", "regulatory_kplate"):
                    self._json(400, {"error": "Pass ?subsystem=brand_keyart or ?subsystem=regulatory_kplate"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_stages": pstate["qualified_stages"][sub_q],
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/view":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    changed = False
                    if body.get("plate_view") in ("BRAND_CMY_PLATE", "KPLATE_DIELINE"):
                        if pstate["ui_session"]["plate_view"] != body["plate_view"]:
                            changed = True
                        pstate["ui_session"]["plate_view"] = body["plate_view"]
                    if body.get("unit_mode") in ("ISO_12647_PCT", "RAW_8BIT_PREVIEW"):
                        if pstate["ui_session"]["unit_mode"] != body["unit_mode"]:
                            changed = True
                        pstate["ui_session"]["unit_mode"] = body["unit_mode"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/export_csv":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                dl_p = Path("/home/gui/Downloads/prepress_spec.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pv = pstate["ui_session"]["plate_view"]
                    um = pstate["ui_session"]["unit_mode"]
                    lines = ["metric,target"]
                    if um != "ISO_12647_PCT":
                        lines.append("preview_bits,8")
                    elif pv == "BRAND_CMY_PLATE":
                        lines.append("bleed_top40_cmy_min_pct,140.0")
                        lines.append("shadow_cmy_range_pct,176.0..235.0")
                        lines.append("ean13_code,4006381333931")
                        lines.append("shadow_tac_band_pct,268.0..284.0")
                    else:
                        lines.append("reg_text_k_p90_min_pct,88.0")
                        lines.append("shadow_k_range_pct,48.0..99.0")
                        lines.append("diecut_stroke_hex,#ff00aa")
                        lines.append("shadow_tac_band_pct,268.0..284.0")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o666)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_p), "plate_view": pv, "unit_mode": um})
                return

            if p == "/api/bench/prepress_densitometer":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("brand_keyart", "regulatory_kplate"):
                    self._json(400, {"error": "subsystem must be 'brand_keyart' or 'regulatory_kplate'"})
                    return
                seq_list = BRAND_STAGES if sub == "brand_keyart" else KPLATE_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                tiff_p = workspace / "prepress_pack" / "cmyk_separations.tiff"
                exp_reg = "BRAND_CMY_PLATE" if sub == "brand_keyart" else "KPLATE_DIELINE"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["plate_view"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_prepress_pack(workspace)
                    errs = check_prepress_constraints(
                        info,
                        check_brand=(sub == "brand_keyart"),
                        check_kplate=(sub == "regulatory_kplate"),
                        stage=stage,
                    )
                    rip = run_halftone_rip_simulation(tiff_p, fast_selfval=fast_selfval) if info.get("ok") else {}
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({
                        "timestamp": time.time(),
                        "subsystem": sub,
                        "stage": stage,
                        "passed": passed,
                        "elapsed_s": elapsed,
                    })
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "stage": stage,
                    "passed": passed,
                    "discrepancies": errs,
                    "densitometry": info.get("summary", {}),
                    "halftone_rip": rip,
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/prepress/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("brand_keyart", "regulatory_kplate"):
                    self._json(400, {"error": "subsystem must be 'brand_keyart' or 'regulatory_kplate'"})
                    return

                info = inspect_prepress_pack(workspace)
                errs = check_prepress_constraints(
                    info,
                    check_brand=(sub == "brand_keyart"),
                    check_kplate=(sub == "regulatory_kplate"),
                    stage="full_press_check",
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = BRAND_STAGES if sub == "brand_keyart" else KPLATE_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified prepress_densitometer stages for {sub}: {unqual}")

                summ = info.get("summary") or {}
                proof_sha = sha256_file(workspace / "prepress_pack" / "press_proof_composite.png")
                exp_ch = summ.get("cmy_shadow_pct", -1.0) if sub == "brand_keyart" else summ.get("k_shadow_pct", -1.0)
                try:
                    if abs(float(body.get("channel_pct", -999)) - exp_ch) > 0.8:
                        errs.append(f"Submitted channel_pct != live {exp_ch}")
                    if abs(float(body.get("tac_shadow_pct", -999)) - summ.get("tac_shadow_pct", -1.0)) > 0.8:
                        errs.append(f"Submitted tac_shadow_pct != live {summ.get('tac_shadow_pct')}")
                    if str(body.get("proof_sha256") or "") != proof_sha:
                        errs.append("Submitted proof_sha256 != sha256(press_proof_composite.png)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_PREPRESS_SIGNOFF", "subsystem": sub, "errors": errs, "densitometry": summ})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "channel_pct": exp_ch,
                    "tac_shadow_pct": summ["tac_shadow_pct"],
                    "proof_sha256": proof_sha,
                    "timestamp": time.time(),
                }
                with state_lock:
                    pstate["submissions"][sub] = rec
                    persist()
                self._json(200, rec)
                return

            self._json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={sso_boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def audit_case_transparency() -> dict:
    return audit_protocol_transparency(build_tickets_by_role(), PORTAL_HTML, REQUIRED_PUBLIC_TOKENS)


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    subs = portal_state.get("submissions") or {}
    b_signed = (subs.get("brand_keyart") or {}).get("status") == "APPROVED"
    k_signed = (subs.get("regulatory_kplate") or {}).get("status") == "APPROVED"
    closed_cnt = int(b_signed) + int(k_signed)

    info = inspect_prepress_pack(workspace)
    b_errs = check_prepress_constraints(info, check_brand=True, check_kplate=False, stage="full_press_check")
    k_errs = check_prepress_constraints(info, check_brand=False, check_kplate=True, stage="full_press_check")
    all_errs = check_prepress_constraints(info, check_brand=True, check_kplate=True, stage="full_press_check")
    pur_a_errs = verify_stage_regime_purity(portal_state, "brand_keyart", BRAND_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "regulatory_kplate", KPLATE_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()

    s = info.get("summary") or {}
    tac_ok = bool(info.get("ok") and TAC_SHADOW_BAND_PCT[0] <= s.get("tac_shadow_pct", -1.0) <= TAC_SHADOW_BAND_PCT[1])

    invariants = {
        "brand_cmy_bleed_and_barcode_valid": bool(len(pur_a_errs) == 0 and b_signed and info.get("ok") and s.get("bleed_cmy_pct", 0) >= BLEED_CMY_MIN_PCT and s.get("barcode_svg_ok")),
        "kplate_typography_and_diecut_valid": bool(len(pur_b_errs) == 0 and k_signed and info.get("ok") and s.get("reg_text_k_p90_pct", 0) >= REG_TEXT_K_MIN_PCT and s.get("diecut_svg_ok")),
        "iso12647_tac_equilibrium_valid": bool(tac_ok and len(all_errs) == 0),
        "svg_proof_and_workspace_clean": bool(info.get("ok") and s.get("proof_png_synced") and s.get("svg_tac_attr_synced") and len(clean_errs) == 0),
    }
    inv_score = round(sum(1 for v in invariants.values() if v) / len(invariants), 4)
    joint_pass = all(invariants.values())

    return {
        "task_id": TASK_ID,
        "joint_pass": joint_pass,
        "invariants": invariants,
        "cross_role_invariant_score": inv_score,
        "closed_tickets_count": closed_cnt,
        "local_completion_rate": round(closed_cnt / 2.0, 4),
        "unaware_race_failure": bool(closed_cnt > 0 and not joint_pass),
        "total_bench_calls": int(portal_state.get("bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "densitometry": s,
        "diagnostics": {
            "prepress_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    import numpy as np
    from PIL import Image

    assert role in ("brand_keyart_lead", "regulatory_kplate_lead")
    pp = workspace / "prepress_pack"
    tiff_p = pp / "cmyk_separations.tiff"
    svg_p = pp / "dieline_overlay.svg"
    proof_p = pp / "press_proof_composite.png"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_brand = (role == "brand_keyart_lead")
    pv = "BRAND_CMY_PLATE" if is_brand else "KPLATE_DIELINE"
    sub = "brand_keyart" if is_brand else "regulatory_kplate"

    r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"plate_view": pv, "unit_mode": "ISO_12647_PCT"}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
    urllib.request.urlopen(r1, timeout=10).read()
    r2 = urllib.request.Request(f"{base}/api/ui/export_csv", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(r2, timeout=10).read()

    arr = np.array(Image.open(tiff_p), dtype=np.uint8)
    live0 = inspect_prepress_pack(workspace)["summary"]
    if is_brand:
        arr[0:40, :, 0] = int(round(60.0 * 2.55))
        arr[0:40, :, 1] = int(round(55.0 * 2.55))
        arr[0:40, :, 2] = int(round(45.0 * 2.55))
        target_cmy = max(177.0, min(233.0, 276.0 - live0["k_shadow_pct"]))
        per_ch = int(round((target_cmy / 3.0) * 2.55))
        arr[200:560, 300:900, 0:3] = per_ch
    else:
        arr[620:720, 200:1000, 3] = int(round(94.0 * 2.55))
        target_k = max(49.0, min(98.0, 276.0 - live0["cmy_shadow_pct"]))
        arr[200:560, 300:900, 3] = int(round(target_k * 2.55))

    Image.fromarray(arr, mode="CMYK").save(tiff_p, format="TIFF")
    live1 = inspect_prepress_pack(workspace)["summary"]

    svg_src = svg_p.read_text(encoding="utf-8")
    svg_src = re.sub(r'data-tac-pct="[^"]*"', f'data-tac-pct="{live1["tac_shadow_pct"]:.1f}"', svg_src)
    if is_brand and 'id="ean13-barcode-group"' not in svg_src:
        svg_src = svg_src.replace("</svg>", '  <g id="ean13-barcode-group" data-ean="4006381333931"><rect x="920" y="620" width="160" height="80" fill="#ffffff"/></g>\n</svg>')
    if (not is_brand) and 'id="die-cut-lines"' not in svg_src:
        svg_src = svg_src.replace("</svg>", '  <g id="die-cut-lines" stroke="#ff00aa" fill="none"><rect x="38" y="38" width="1124" height="724" stroke-width="2"/></g>\n</svg>')
    svg_p.write_text(svg_src, encoding="utf-8")
    _render_composite_proof(tiff_p, svg_p, proof_p)

    stages = BRAND_STAGES if is_brand else KPLATE_STAGES
    for st in stages:
        code, resp = post_json(f"{base}/api/bench/prepress_densitometer", {"subsystem": sub, "stage": st}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {st} failed: {resp}"

    summ = inspect_prepress_pack(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/prepress/submit", {
        "subsystem": sub,
        "channel_pct": summ["cmy_shadow_pct"] if is_brand else summ["k_shadow_pct"],
        "tac_shadow_pct": summ["tac_shadow_pct"],
        "proof_sha256": sha256_file(proof_p),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    pp = workspace / "prepress_pack"
    tiff_p = pp / "cmyk_separations.tiff"
    svg_p = pp / "dieline_overlay.svg"
    with tempfile.TemporaryDirectory() as tmp:
        snap_t = Path(tmp) / "v0.tiff"
        snap_s = Path(tmp) / "v0.svg"
        shutil.copy2(tiff_p, snap_t)
        shutil.copy2(svg_p, snap_s)
        solve_role("brand_keyart_lead", workspace, portal_port, strict=True)
        shutil.copy2(snap_t, tiff_p)
        shutil.copy2(snap_s, svg_p)
        solve_role("regulatory_kplate_lead", workspace, portal_port, strict=False)

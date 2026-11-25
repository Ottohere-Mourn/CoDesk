"""AW-02: Veridian Espresso Carton Prepress — GIMP Retouch & CMYK TAC vs. Inkscape Dieline & Regulatory Proof."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    extract_pdf_text,
    launch_desktop_app_as_user,
    read_json_safe,
    resource_lock,
    write_json,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-02",
    "slug": "gimp_inkscape_packaging",
    "title": "Veridian Espresso Carton Prepress: GIMP Retouch & CMYK TAC vs. Inkscape Dieline & Dual-Market Proof",
    "domain": "Graphic Prepress & Packaging Engineering (GIMP 2.10 + Inkscape 1.2 + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19602,
    "roles": ("retouch_color_artist", "prepress_dieline_eng"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

SWATCHES_RAW: list[tuple[str, float, float, float, float, float, str]] = [
    ("Brand_Obsidian", 78.0, 68.0, 64.0, 92.0, 0.34, "#183a5a"),
    ("Roast_Bronze", 24.0, 52.0, 88.0, 18.0, 0.22, "#b46922"),
    ("Shadow_Plum", 72.0, 84.0, 58.0, 88.0, 0.16, "#2c1635"),
    ("Crema_Ivory", 4.0, 7.0, 18.0, 0.0, 0.28, "#f6efe2"),
]
SPOT_METALLIC_COV_FRAC = 0.09  # 5th press unit Pantone 871C spot metallic (100% solid spot, exempt from CMYK TAC)

ALUMINIUM_SHELL_TARE_G = 1.15
# (subsample_id, gross_capsule_g, caffeine_mg_per_g_roast, moisture_pct, lab_disposition)
COA_SAMPLES: list[tuple[str, float, float, float, str]] = [
    ("SUB-01", 6.77, 12.20, 2.8, "RELEASED"),
    ("SUB-02", 6.73, 12.10, 2.9, "RELEASED"),
    ("SUB-03", 6.75, 12.15, 2.7, "RELEASED"),
    ("SUB-04", 6.75, 12.15, 2.8, "RELEASED"),
    ("SUB-05", 7.60, 16.80, 6.4, "QUARANTINE_MOISTURE"),
]

GS1_PREFIX_12 = "590481203749"
ALLERGEN_CODE = "ALG-EU-SOY0-NUT0-2026"
FSC_CERT_ID = "FSC-C184920-MIX"
COLOR_PROFILE_TAG = "FOGRA39-GCR300-VERIDIAN"

TICKET_A = (
    "# Work Order — Packaging Color & Retouch Artist (`retouch_color_artist`)\n\n"
    "Complete the hero artwork retouching, CMYK Total Area Coverage (TAC) preflight, and SVG artwork layer in `/workspace/packaging_kit`:\n\n"
    "1. Review `/workspace/packaging_kit/specs/Print_Color_Prepress_Spec.pdf` and inspect `/workspace/packaging_kit/press_quote.sqlite` plus the **Veridian Prepress Portal** open in Chromium (`http://127.0.0.1:19602`, `Color Swatch & ICC Profile` tab).\n"
    "2. In the open **GIMP** window on the desktop (`hero_capsule_raw.xcf`), sample the uppercase `#RRGGBB` hex color of the `Gold_Capsule_Crest` center (`hero_crest_hex`), hide or remove `FPO_DRAFT_WATERMARK`, and export the clean `800x600` raster master to `/workspace/packaging_kit/assets/hero_capsule_clean.png`.\n"
    "3. Apply the FOGRA39 300% process-CMYK TAC scaling rule from `Print_Color_Prepress_Spec.pdf` and compute both process CMYK ink volume (`total_press_ink_ml`) and 5th-unit spot metallic ink volume (`spot_metallic_ink_ml`) across the scheduled press run.\n"
    "4. Update `<g id=\"artwork_panel\">` in `/workspace/packaging_kit/carton_master.svg` (preserving all sibling `<g>` groups!) so its `<image>` links `assets/hero_capsule_clean.png` and sets `data-color-profile` to the portal ICC tag, render `/workspace/packaging_kit/Artwork_Panel_Check.png` via `inkscape` (refreshing `Carton_Composite_Preview.png` / `Carton_Press_Proof.pdf` if already present), and write `/workspace/packaging_kit/color_preflight_report.json` with:\n"
    "   - `icc_profile_tag`, `hero_crest_hex`, `over_tac_swatches` (sorted list)\n"
    "   - `adjusted_cmyk` (mapping each process swatch -> `[C, M, Y, K]` rounded to 1 decimal)\n"
    "   - `total_press_ink_ml`, `spot_metallic_ink_ml`, and `hero_png_clean` (`true`)\n"
)

TICKET_B = (
    "# Work Order — Structural Prepress & Regulatory Dieline Engineer (`prepress_dieline_eng`)\n\n"
    "Complete the structural dieline, GS1 EAN-13 barcode, dual-market regulatory panel, and press-ready PDF proof in `/workspace/packaging_kit`:\n\n"
    "1. Review `/workspace/packaging_kit/specs/Print_Color_Prepress_Spec.pdf`, query `/workspace/packaging_kit/press_quote.sqlite` (`sku_packaging`, `roast_lot_coa`), and inspect the **Veridian Prepress Portal** in Chromium (`http://127.0.0.1:19602`, `Dual-Market Regulatory` tab) to obtain `allergen_trace_code` and `fsc_board_cert_id`.\n"
    "2. Compute the 13-digit GS1 EAN-13 barcode, net roasted coffee carton weight in grams (`net_carton_mass_g`, net of capsule tare!) and US FDA ounces (`net_carton_mass_oz`, 1 decimal), accepted caffeine per capsule (`accepted_caffeine_mg_per_capsule`), and EU EFSA brewed espresso caffeine per 100 mL (`efsa_caffeine_mg_per_100ml`, 1 decimal, accounting for extraction yield in the spec!).\n"
    "3. Update `<g id=\"dieline_cut_crease\">`, `<g id=\"nutrition_regulatory_panel\">`, and `<g id=\"ean13_barcode\">` inside `/workspace/packaging_kit/carton_master.svg` (preserving `<g id=\"artwork_panel\">`!) with cut stroke `#EC008C`, dashed crease stroke `#00AEEF`, `3.0mm` bleed frame, full 13-digit EAN-13 text, net weights, brewed caffeine per 100 mL, `allergen_trace_code`, and `fsc_board_cert_id`.\n"
    "4. Export `/workspace/packaging_kit/Carton_Press_Proof.pdf` and `/workspace/packaging_kit/Carton_Composite_Preview.png` from `carton_master.svg` via `inkscape`, and write `/workspace/packaging_kit/dieline_compliance.json` with:\n"
    "   - `ean13_full`, `ean13_check_digit`, `net_carton_mass_g`, `net_carton_mass_oz`\n"
    "   - `accepted_caffeine_mg_per_capsule`, `efsa_caffeine_mg_per_100ml`\n"
    "   - `allergen_trace_code`, `fsc_board_cert_id`, `bleed_mm`\n"
)


def compute_color_oracle() -> dict[str, Any]:
    over_tac: list[str] = []
    adj_map: dict[str, list[float]] = {}
    cartons = 25000.0
    area_m2_per_carton = 620.0 / 10000.0
    laydown_g_m2 = 1.35
    density_g_ml = 1.08
    # Short-run (<30,000 cartons) makeready waste is 8.5% per press_waste_tiers table!
    waste_mult = 1.085
    tot_grams = 0.0

    for name, c, m, y, k, cov_frac, _hx in SWATCHES_RAW:
        raw_tac = c + m + y + k
        if raw_tac > 300.0:
            over_tac.append(name)
            sc = (300.0 - k) / (c + m + y)
            c_a, m_a, y_a = round(c * sc, 1), round(m * sc, 1), round(y * sc, 1)
        else:
            c_a, m_a, y_a = round(c, 1), round(m, 1), round(y, 1)
        k_a = round(k, 1)
        adj_map[name] = [c_a, m_a, y_a, k_a]
        tac_frac = (c_a + m_a + y_a + k_a) / 100.0
        tot_grams += cartons * waste_mult * area_m2_per_carton * cov_frac * tac_frac * laydown_g_m2

    # Spot metallic 871C uses 1.80 g/m^2 metallic flake laydown and 1.20 g/mL metallic ink density
    spot_grams = cartons * waste_mult * area_m2_per_carton * SPOT_METALLIC_COV_FRAC * 1.0 * 1.80
    return {
        "icc_profile_tag": COLOR_PROFILE_TAG,
        "hero_crest_hex": "#D49B28",
        "over_tac_swatches": sorted(over_tac),
        "adjusted_cmyk": adj_map,
        "total_press_ink_ml": round(tot_grams / density_g_ml, 2),
        "spot_metallic_ink_ml": round(spot_grams / 1.20, 2),
        "hero_png_clean": True,
    }


def compute_dieline_oracle() -> dict[str, Any]:
    digits = [int(ch) for ch in GS1_PREFIX_12]
    odd_s = sum(digits[0::2])
    even_s = sum(digits[1::2])
    chk = (10 - ((odd_s + 3 * even_s) % 10)) % 10
    ean13 = f"{GS1_PREFIX_12}{chk}"

    valid = [r for r in COA_SAMPLES if r[4] == "RELEASED"]
    avg_net_roast_g = sum((r[1] - ALUMINIUM_SHELL_TARE_G) for r in valid) / len(valid)
    avg_caff_per_g = sum(r[2] for r in valid) / len(valid)
    avg_caff_cap = round(avg_net_roast_g * avg_caff_per_g, 2)
    carton_g = round(10.0 * avg_net_roast_g, 1)
    carton_oz = round(carton_g / 28.349523125, 1)
    # Brewed espresso extraction efficiency is 88.0% into a 40.0 mL beverage per spec!
    efsa_100ml = round((avg_caff_cap * 0.88) * (100.0 / 40.0), 1)
    return {
        "ean13_full": ean13,
        "ean13_check_digit": chk,
        "net_carton_mass_g": carton_g,
        "net_carton_mass_oz": carton_oz,
        "accepted_caffeine_mg_per_capsule": avg_caff_cap,
        "efsa_caffeine_mg_per_100ml": efsa_100ml,
        "allergen_trace_code": ALLERGEN_CODE,
        "fsc_board_cert_id": FSC_CERT_ID,
        "bleed_mm": 3.0,
    }


INITIAL_CARTON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="1200" height="840" viewBox="0 0 1200 840">
  <rect id="sheet_bg" x="0" y="0" width="1200" height="840" fill="#f8fafc"/>
  <g id="artwork_panel" data-color-profile="UNSET_PROFILE">
    <rect id="front_panel_fill" x="80" y="80" width="520" height="680" fill="#183a5a"/>
    <rect id="fpo_placeholder" x="120" y="140" width="440" height="330" fill="#ff00aa"/>
    <text x="140" y="540" fill="#f6efe2" font-family="DejaVu Sans" font-size="28" font-weight="bold">VERIDIAN INTENSO NO. 9</text>
  </g>
  <g id="dieline_cut_crease" data-bleed-mm="0.0">
    <rect id="cut_outline" x="80" y="80" width="1040" height="680" fill="none" stroke="#64748b" stroke-width="2"/>
    <line id="fold_spine" x1="600" y1="80" x2="600" y2="760" stroke="#94a3b8" stroke-width="1"/>
  </g>
  <g id="nutrition_regulatory_panel">
    <rect x="640" y="110" width="440" height="420" fill="#ffffff" stroke="#cbd5e1"/>
    <text id="reg_net_wt" x="665" y="170" fill="#0f172a" font-family="DejaVu Sans" font-size="20">Net Wt: TBD_NET_WT</text>
    <text id="reg_caffeine" x="665" y="220" fill="#0f172a" font-family="DejaVu Sans" font-size="20">EFSA Brew Caffeine: TBD_CAFFEINE</text>
    <text id="reg_allergen" x="665" y="270" fill="#0f172a" font-family="DejaVu Sans" font-size="18">Allergen Trace: TBD_ALLERGEN</text>
    <text id="reg_fsc" x="665" y="320" fill="#0f172a" font-family="DejaVu Sans" font-size="18">Board Stock: TBD_FSC</text>
  </g>
  <g id="ean13_barcode">
    <rect x="640" y="560" width="320" height="150" fill="#ffffff" stroke="#0f172a"/>
    <text id="ean13_digits" x="670" y="680" fill="#0f172a" font-family="DejaVu Sans Mono" font-size="24">590481203749X</text>
  </g>
</svg>
"""


def build(workspace_root: Path, tickets_root: Path) -> None:
    pkg = workspace_root / "shared" / "packaging_kit"
    (pkg / "assets").mkdir(parents=True, exist_ok=True)
    (pkg / "specs").mkdir(parents=True, exist_ok=True)
    (pkg / "carton_master.svg").write_text(INITIAL_CARTON_SVG, encoding="utf-8")

    db_p = pkg / "press_quote.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute(
        "CREATE TABLE swatch_coverage (swatch_name TEXT PRIMARY KEY, panel_coverage_fraction REAL, hex_preview TEXT)"
    )
    for nm, _c, _m, _y, _k, cov, hx in SWATCHES_RAW:
        con.execute("INSERT INTO swatch_coverage VALUES (?,?,?)", (nm, cov, hx))
    con.execute(
        "CREATE TABLE press_parameters (param_key TEXT PRIMARY KEY, param_val REAL, unit TEXT)"
    )
    con.executemany(
        "INSERT INTO press_parameters VALUES (?,?,?)",
        [
            ("carton_run_qty", 25000.0, "cartons"),
            ("carton_print_area_cm2", 620.0, "cm2"),
            ("specific_ink_laydown_g_m2", 1.35, "g_per_m2"),
            ("ink_density_g_ml", 1.08, "g_per_ml"),
            ("standard_longrun_waste_pct_ge_30k", 5.0, "percent"),
            ("shortrun_waste_pct_lt_30k", 8.5, "percent"),
            ("spot_metallic_871c_coverage_frac", SPOT_METALLIC_COV_FRAC, "fraction"),
            ("spot_metallic_laydown_g_m2", 1.80, "g_per_m2"),
            ("spot_metallic_density_g_ml", 1.20, "g_per_ml"),
            ("capsules_per_carton", 10.0, "count"),
            ("standard_espresso_shot_ml", 40.0, "ml"),
            ("espresso_caffeine_extraction_yield", 0.88, "fraction"),
        ],
    )
    con.execute(
        "CREATE TABLE sku_packaging (sku_code TEXT PRIMARY KEY, gs1_prefix_12 TEXT, dieline_bleed_mm REAL, aluminium_shell_tare_g REAL)"
    )
    con.execute("INSERT INTO sku_packaging VALUES ('VER-ESP-09', ?, 3.0, ?)", (GS1_PREFIX_12, ALUMINIUM_SHELL_TARE_G))
    con.execute(
        "CREATE TABLE roast_lot_coa (subsample_id TEXT PRIMARY KEY, gross_capsule_mass_g REAL, "
        "caffeine_mg_per_g_roast REAL, moisture_pct REAL, lab_disposition TEXT)"
    )
    con.executemany("INSERT INTO roast_lot_coa VALUES (?,?,?,?,?)", COA_SAMPLES)
    con.commit()
    con.close()

    write_pdf_manual(
        pkg / "specs" / "Print_Color_Prepress_Spec.pdf",
        "Veridian Packaging Prepress & Dual-Market Regulatory Specification",
        [
            (
                "1. Hero Raster Retouching in GIMP",
                [
                    "The studio camera master hero_capsule_raw.xcf is open in GIMP on the desktop. Sample the RGB fill of the Gold_Capsule_Crest layer and record its uppercase hex string (#RRGGBB) as hero_crest_hex.",
                    "Hide or remove the bright magenta FPO_DRAFT_WATERMARK overlay while preserving Roast_Backdrop and Gold_Capsule_Crest at 800x600, and export to /workspace/packaging_kit/assets/hero_capsule_clean.png.",
                ],
            ),
            (
                "2. FOGRA39 CMYK Total Area Coverage (TAC <= 300%) & Ink Estimation",
                [
                    "Retrieve raw CMYK values (C, M, Y, K in %) and the ICC profile tag from the Veridian Prepress Portal (Color Swatch & ICC Profile view).",
                    "For any 4-color process swatch whose raw TAC exceeds 300.0%, hold K fixed and proportionally scale C, M, Y so adjusted TAC equals 300.0% (rounding each channel to 1 decimal). Process ink usage applies the run-size-appropriate makeready spoilage rate from press_parameters (<30,000 cartons vs >=30,000 cartons!), multiplying run_qty * (1 + waste) * area_m2 * panel_coverage_fraction * (adjusted_TAC / 100) * specific_ink_laydown_g_m2, divided by ink_density_g_ml.",
                    "Separately compute 5th-unit Pantone 871C metallic spot ink volume (spot_metallic_ink_ml, 100% solid coverage over spot_metallic_871c_coverage_frac, using its dedicated metallic laydown and density in press_parameters).",
                ],
            ),
            (
                "3. GS1 EAN-13, COA Outlier Exclusion & Dual-Market Nutrition Rules",
                [
                    "Include only roast_lot_coa subsamples with lab_disposition = 'RELEASED'. Note that gross_capsule_mass_g includes the empty aluminium capsule shell (aluminium_shell_tare_g in sku_packaging); subtract shell tare first to get net roasted coffee per capsule!",
                    "Compute dry-roast caffeine per capsule (net_roast_g * caffeine_mg_per_g_roast), net 10-capsule carton mass in grams and avoirdupois ounces (1 oz = 28.349523125 g), and EU EFSA brewed beverage caffeine per 100 mL for a 40.0 mL shot after applying espresso_caffeine_extraction_yield from press_parameters.",
                    "Compute the standard Modulo-10 GS1 EAN-13 check digit for the 12-digit prefix in sku_packaging.",
                ],
            ),
            (
                "4. Shared SVG Layer Contract & Press Proof Output",
                [
                    "carton_master.svg contains four top-level groups: artwork_panel, dieline_cut_crease, nutrition_regulatory_panel, and ean13_barcode. Preserve all sibling groups when saving!",
                    "Dieline standard: outer bleed rectangle 3.0 mm outside trim (data-bleed-mm='3.0'), cut lines in #EC008C, and fold/crease lines in dashed #00AEEF.",
                ],
            ),
        ],
    )

    (tickets_root / "retouch_color_artist").mkdir(parents=True, exist_ok=True)
    (tickets_root / "prepress_dieline_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "retouch_color_artist" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "prepress_dieline_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "color", "tab_switches": 0, "downloads_exported": []}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw02_sess" in ck) and (ck["aw02_sess"].value == tok)

        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", extra_hdrs: list[tuple[str, str]] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for hk, hv in (extra_hdrs or []):
                self.send_header(hk, hv)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/health":
                self._send(200, b'{"ok":true}', "application/json")
                return
            if parsed.path == "/auth":
                if (qs.get("token") or [""])[0] == tok:
                    self._send(302, b"", extra_hdrs=[("Set-Cookie", f"aw02_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Authenticated Browser Session Required (Inspect open Chromium window)</h3>")
                return
            if parsed.path == "/switch":
                new_tab = (qs.get("tab") or ["color"])[0]
                with lock:
                    if new_tab in ("color", "regulatory") and new_tab != state["active_tab"]:
                        state["active_tab"] = new_tab
                        state["tab_switches"] = int(state["tab_switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", extra_hdrs=[("Location", "/")])
                return
            if parsed.path == "/export_current":
                with lock:
                    cur = state["active_tab"]
                    dl_dir = Path("/home/user/Downloads")
                    dl_dir.mkdir(parents=True, exist_ok=True)
                    if cur == "color":
                        out_p = dl_dir / "veridian_color_swatches.json"
                        write_json(
                            out_p,
                            {
                                "icc_profile_tag": COLOR_PROFILE_TAG,
                                "swatches": [
                                    {"name": nm, "C": c, "M": m, "Y": y, "K": k}
                                    for nm, c, m, y, k, _cov, _hx in SWATCHES_RAW
                                ],
                            },
                        )
                    else:
                        out_p = dl_dir / "veridian_regulatory_codes.json"
                        write_json(
                            out_p,
                            {
                                "allergen_trace_code": ALLERGEN_CODE,
                                "fsc_board_cert_id": FSC_CERT_ID,
                                "cut_stroke_hex": "#EC008C",
                                "crease_stroke_hex": "#00AEEF",
                            },
                        )
                    os_chmod = out_p
                    os_chmod.chmod(0o644)
                    state["downloads_exported"].append(out_p.name)
                    write_json(state_file, state)
                self._send(302, b"", extra_hdrs=[("Location", "/?exported=1")])
                return

            with lock:
                cur = state["active_tab"]
            if cur == "color":
                rows_html = "".join(
                    f"<tr><td>{nm}</td><td>{c}</td><td>{m}</td><td>{y}</td><td>{k}</td><td>{c+m+y+k:.1f}%</td></tr>"
                    for nm, c, m, y, k, _cov, _hx in SWATCHES_RAW
                )
                panel_html = f"""
                <h2>Color Swatch &amp; ICC Profile Specification</h2>
                <p><b>Certified ICC Profile Tag:</b> <code>{COLOR_PROFILE_TAG}</code></p>
                <table border="1" cellpadding="8" style="border-collapse:collapse;margin-top:12px;">
                  <tr><th>Swatch Name</th><th>C (%)</th><th>M (%)</th><th>Y (%)</th><th>K (%)</th><th>Raw TAC</th></tr>
                  {rows_html}
                </table>"""
            else:
                panel_html = f"""
                <h2>Dual-Market Regulatory &amp; Structural Board Signoff</h2>
                <ul style="line-height:1.9;font-size:16px;margin-top:12px;">
                  <li><b>Mandatory Allergen Trace Code:</b> <code>{ALLERGEN_CODE}</code></li>
                  <li><b>FSC Certified Board Stock ID:</b> <code>{FSC_CERT_ID}</code></li>
                  <li><b>Cut Contour Spot Hex:</b> <code>#EC008C</code> | <b>Crease Contour Spot Hex:</b> <code>#00AEEF</code> (dashed)</li>
                  <li><b>Required Outer Bleed Margin:</b> <code>3.0 mm</code></li>
                </ul>"""

            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Veridian Prepress Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:28px;background:#f8fafc;color:#0f172a;}}
            .nav a{{display:inline-block;padding:10px 18px;margin-right:10px;border-radius:6px;background:#1e293b;color:#fff;text-decoration:none;font-weight:700;}}
            .box{{margin-top:20px;padding:24px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}
            .btn{{display:inline-block;margin-top:16px;padding:10px 18px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            </style></head><body>
            <h1>Veridian Packaging &amp; Regulatory Portal (Active View: {cur.upper()})</h1>
            <div class="nav">
              <a href="/switch?tab=color" id="tab-color">Color Swatch &amp; ICC Profile</a>
              <a href="/switch?tab=regulatory" id="tab-regulatory">Dual-Market Regulatory</a>
            </div>
            <div class="box">{panel_html}
              <div><a class="btn" href="/export_current" id="btn-export">Export Active View JSON to ~/Downloads</a></div>
            </div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def _create_gimp_xcf(xcf_path: Path) -> None:
    xcf_path.parent.mkdir(parents=True, exist_ok=True)
    scm = (
        '(let* ((img (car (gimp-image-new 800 600 RGB))) '
        '(bg (car (gimp-layer-new img 800 600 RGB-IMAGE "Roast_Backdrop" 100 LAYER-MODE-NORMAL))) '
        '(crest (car (gimp-layer-new img 400 300 RGBA-IMAGE "Gold_Capsule_Crest" 100 LAYER-MODE-NORMAL))) '
        '(fpo (car (gimp-layer-new img 800 160 RGBA-IMAGE "FPO_DRAFT_WATERMARK" 100 LAYER-MODE-NORMAL)))) '
        '(gimp-image-insert-layer img bg 0 0) '
        '(gimp-context-set-foreground \'(24 58 90)) (gimp-drawable-fill bg FILL-FOREGROUND) '
        '(gimp-image-insert-layer img crest 0 0) (gimp-layer-set-offsets crest 200 150) '
        '(gimp-context-set-foreground \'(212 155 40)) (gimp-drawable-fill crest FILL-FOREGROUND) '
        '(gimp-image-insert-layer img fpo 0 0) (gimp-layer-set-offsets fpo 0 0) '
        '(gimp-context-set-foreground \'(255 0 170)) (gimp-drawable-fill fpo FILL-FOREGROUND) '
        f'(gimp-xcf-save 0 img fpo "{xcf_path}" "{xcf_path}") (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=40)


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1240, 840))

    master_dir = Path("/opt/aw02_masters")
    master_dir.mkdir(parents=True, exist_ok=True)
    xcf_p = master_dir / "hero_capsule_raw.xcf"
    _create_gimp_xcf(xcf_p)
    subprocess.run(["chown", "-R", "1000:0", str(master_dir)], check=True, capture_output=True, timeout=10)
    subprocess.run(["chmod", "700", str(master_dir)], check=True, capture_output=True, timeout=10)

    svg_p = workspace_root / "shared" / "packaging_kit" / "carton_master.svg"
    if "retouch_color_artist" in roles:
        launch_desktop_app_as_user(
            f"nohup gimp --no-splash '{xcf_p}' >/tmp/aw02_gimp.log 2>&1 </dev/null &",
            wait_s=3.2,
        )
    if roles & {"retouch_color_artist", "prepress_dieline_eng"}:
        launch_desktop_app_as_user(
            f"nohup inkscape '{svg_p}' >/tmp/aw02_inkscape.log 2>&1 </dev/null &",
            wait_s=2.6,
        )


def _export_clean_hero_from_xcf(xcf_path: Path, out_png: Path) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    scm = (
        f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xcf_path}" "{xcf_path}"))) '
        '(layers (cadr (gimp-image-get-layers img))) '
        '(top-layer (aref layers 0))) '
        '(gimp-item-set-visible top-layer FALSE) '
        '(let ((merged (car (gimp-image-merge-visible-layers img CLIP-TO-IMAGE)))) '
        f'(file-png-save-defaults RUN-NONINTERACTIVE img merged "{out_png}" "{out_png}")) '
        '(gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=40)


def _update_svg_group(svg_path: Path, group_id: str, new_group_xml: str, cooperative: bool = True) -> None:
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    src = svg_path.read_text(encoding="utf-8") if cooperative else INITIAL_CARTON_SVG
    root = ET.fromstring(src)
    new_el = ET.fromstring(new_group_xml)
    for idx, child in enumerate(list(root)):
        if child.attrib.get("id") == group_id:
            root.remove(child)
            root.insert(idx, new_el)
            break
    else:
        root.append(new_el)
    svg_path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    pkg = workspace_root / "shared" / "packaging_kit"
    svg_p = pkg / "carton_master.svg"
    if role == "retouch_color_artist":
        ora_a = compute_color_oracle()
        _export_clean_hero_from_xcf(Path("/opt/aw02_masters/hero_capsule_raw.xcf"), pkg / "assets" / "hero_capsule_clean.png")
        art_xml = (
            f'<g xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'id="artwork_panel" data-color-profile="{COLOR_PROFILE_TAG}">'
            '<rect id="front_panel_fill" x="80" y="80" width="520" height="680" fill="#183a5a"/>'
            '<image id="hero_capsule_img" x="120" y="140" width="440" height="330" '
            'href="assets/hero_capsule_clean.png" xlink:href="assets/hero_capsule_clean.png"/>'
            '<text x="140" y="540" fill="#f6efe2" font-family="DejaVu Sans" font-size="28" font-weight="bold">VERIDIAN INTENSO NO. 9</text>'
            "</g>"
        )
        if cooperative:
            with resource_lock("aw02_carton_svg"):
                _update_svg_group(svg_p, "artwork_panel", art_xml, cooperative=True)
                if (pkg / "Carton_Composite_Preview.png").is_file():
                    subprocess.run(["inkscape", str(svg_p), "--export-type=png", f"--export-filename={pkg / 'Carton_Composite_Preview.png'}"], check=True, capture_output=True, timeout=35)
                if (pkg / "Carton_Press_Proof.pdf").is_file():
                    subprocess.run(["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={pkg / 'Carton_Press_Proof.pdf'}"], check=True, capture_output=True, timeout=35)
        else:
            _update_svg_group(svg_p, "artwork_panel", art_xml, cooperative=False)
        subprocess.run(
            ["inkscape", str(svg_p), "--export-type=png", f"--export-filename={pkg / 'Artwork_Panel_Check.png'}"],
            check=True, capture_output=True, timeout=35,
        )
        write_json(pkg / "color_preflight_report.json", ora_a)
    elif role == "prepress_dieline_eng":
        ora_b = compute_dieline_oracle()
        die_xml = (
            '<g xmlns="http://www.w3.org/2000/svg" id="dieline_cut_crease" data-bleed-mm="3.0">'
            '<rect id="bleed_outline" x="68" y="68" width="1064" height="704" fill="none" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4,4"/>'
            '<rect id="cut_outline" x="80" y="80" width="1040" height="680" fill="none" stroke="#EC008C" stroke-width="1.5"/>'
            '<line id="fold_spine" x1="600" y1="80" x2="600" y2="760" stroke="#00AEEF" stroke-width="1.5" stroke-dasharray="8,4"/>'
            "</g>"
        )
        reg_xml = (
            '<g xmlns="http://www.w3.org/2000/svg" id="nutrition_regulatory_panel">'
            '<rect x="640" y="110" width="440" height="420" fill="#ffffff" stroke="#cbd5e1"/>'
            f'<text id="reg_net_wt" x="665" y="170" fill="#0f172a" font-family="DejaVu Sans" font-size="20">Net Wt: {ora_b["net_carton_mass_g"]} g ({ora_b["net_carton_mass_oz"]} oz)</text>'
            f'<text id="reg_caffeine" x="665" y="220" fill="#0f172a" font-family="DejaVu Sans" font-size="20">EFSA Brew Caffeine: {ora_b["efsa_caffeine_mg_per_100ml"]} mg/100mL</text>'
            f'<text id="reg_allergen" x="665" y="270" fill="#0f172a" font-family="DejaVu Sans" font-size="18">Allergen Trace: {ALLERGEN_CODE}</text>'
            f'<text id="reg_fsc" x="665" y="320" fill="#0f172a" font-family="DejaVu Sans" font-size="18">Board Stock: {FSC_CERT_ID}</text>'
            "</g>"
        )
        ean_xml = (
            '<g xmlns="http://www.w3.org/2000/svg" id="ean13_barcode">'
            '<rect x="640" y="560" width="320" height="150" fill="#ffffff" stroke="#0f172a"/>'
            f'<text id="ean13_digits" x="670" y="680" fill="#0f172a" font-family="DejaVu Sans Mono" font-size="24">{ora_b["ean13_full"]}</text>'
            "</g>"
        )
        if cooperative:
            with resource_lock("aw02_carton_svg"):
                _update_svg_group(svg_p, "dieline_cut_crease", die_xml, cooperative=True)
                _update_svg_group(svg_p, "nutrition_regulatory_panel", reg_xml, cooperative=True)
                _update_svg_group(svg_p, "ean13_barcode", ean_xml, cooperative=True)
        else:
            _update_svg_group(svg_p, "dieline_cut_crease", die_xml, cooperative=False)
            _update_svg_group(svg_p, "nutrition_regulatory_panel", reg_xml, cooperative=True)
            _update_svg_group(svg_p, "ean13_barcode", ean_xml, cooperative=True)
        subprocess.run(
            ["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={pkg / 'Carton_Press_Proof.pdf'}"],
            check=True, capture_output=True, timeout=35,
        )
        subprocess.run(
            ["inkscape", str(svg_p), "--export-type=png", f"--export-filename={pkg / 'Carton_Composite_Preview.png'}"],
            check=True, capture_output=True, timeout=35,
        )
        write_json(pkg / "dieline_compliance.json", ora_b)


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    """Gate 4: uncoordinated full-file overwrite of carton_master.svg clobbers peer's SVG groups."""
    solve_role("retouch_color_artist", workspace_root, cooperative=False)
    solve_role("prepress_dieline_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    """Gate 5: genuinely concurrent execution with per-group XML merge lock, then composite refresh."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "retouch_color_artist", workspace_root, True)
        fb = pool.submit(solve_role, "prepress_dieline_eng", workspace_root, True)
        fa.result()
        fb.result()
    pkg = workspace_root / "shared" / "packaging_kit"
    svg_p = pkg / "carton_master.svg"
    with resource_lock("aw02_carton_svg"):
        subprocess.run(["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={pkg / 'Carton_Press_Proof.pdf'}"], check=True, capture_output=True, timeout=35)
        subprocess.run(["inkscape", str(svg_p), "--export-type=png", f"--export-filename={pkg / 'Carton_Composite_Preview.png'}"], check=True, capture_output=True, timeout=35)


def _check_hero_png(path: Path) -> bool:
    from PIL import Image

    if not path.is_file():
        return False
    try:
        im = Image.open(path).convert("RGB")
        if im.size != (800, 600):
            return False
        top_px = im.getpixel((400, 80))  # Must be navy (24, 58, 90), NOT magenta (255, 0, 170)
        mid_px = im.getpixel((400, 300))  # Must be gold (212, 155, 40)
        navy_ok = all(abs(int(top_px[i]) - c) <= 22 for i, c in enumerate((24, 58, 90)))
        gold_ok = all(abs(int(mid_px[i]) - c) <= 22 for i, c in enumerate((212, 155, 40)))
        return navy_ok and gold_ok
    except Exception:
        return False


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    pkg = workspace_root / "shared" / "packaging_kit"
    ora_a = compute_color_oracle()
    ora_b = compute_dieline_oracle()

    rep_a = read_json_safe(pkg / "color_preflight_report.json")
    rep_b = read_json_safe(pkg / "dieline_compliance.json")
    svg_txt = (pkg / "carton_master.svg").read_text(encoding="utf-8", errors="replace") if (pkg / "carton_master.svg").is_file() else ""
    proof_txt = extract_pdf_text(pkg / "Carton_Press_Proof.pdf")
    hero_ok = _check_hero_png(pkg / "assets" / "hero_capsule_clean.png")

    adj_got = rep_a.get("adjusted_cmyk") if isinstance(rep_a.get("adjusted_cmyk"), dict) else {}

    def _cmyk_ok(sname: str) -> bool:
        vals = adj_got.get(sname)
        exp = ora_a["adjusted_cmyk"][sname]
        if not isinstance(vals, list) or len(vals) != 4:
            return False
        return all(isinstance(vals[i], (int, float)) and abs(float(vals[i]) - exp[i]) <= 0.25 for i in range(4)) and sum(float(x) for x in vals) <= 300.1

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_hero_png_clean", hero_ok, 2.5, "assets/hero_capsule_clean.png missing, wrong resolution, or still has magenta FPO layer"),
        ("a_icc_tag", str(rep_a.get("icc_profile_tag", "")).strip() == COLOR_PROFILE_TAG, 1.5, "icc_profile_tag from portal missing/wrong"),
        ("a_crest_hex", str(rep_a.get("hero_crest_hex", "")).strip().upper() == "#D49B28", 1.5, "hero_crest_hex sampled from GIMP layer mismatch (expected #D49B28)"),
        ("a_over_tac_list", sorted(rep_a.get("over_tac_swatches") or []) == ora_a["over_tac_swatches"], 1.5, "over_tac_swatches mismatch"),
        ("a_cmyk_obsidian", _cmyk_ok("Brand_Obsidian"), 1.5, "Brand_Obsidian GCR 300% CMYK scaling mismatch"),
        ("a_cmyk_plum", _cmyk_ok("Shadow_Plum"), 1.5, "Shadow_Plum GCR 300% CMYK scaling mismatch"),
        ("a_cmyk_bronze", _cmyk_ok("Roast_Bronze"), 1.0, "Roast_Bronze CMYK mismatch"),
        ("a_cmyk_ivory", _cmyk_ok("Crema_Ivory"), 1.0, "Crema_Ivory CMYK mismatch"),
        (
            "a_ink_ml",
            isinstance(rep_a.get("total_press_ink_ml"), (int, float))
            and abs(float(rep_a["total_press_ink_ml"]) - ora_a["total_press_ink_ml"]) <= 3.5,
            2.0,
            f"total_press_ink_ml mismatch (expected {ora_a['total_press_ink_ml']} using 8.5% short-run waste)",
        ),
        (
            "a_spot_ink_ml",
            isinstance(rep_a.get("spot_metallic_ink_ml"), (int, float))
            and abs(float(rep_a["spot_metallic_ink_ml"]) - ora_a["spot_metallic_ink_ml"]) <= 2.5,
            1.6,
            f"spot_metallic_ink_ml mismatch (expected {ora_a['spot_metallic_ink_ml']})",
        ),
        ("a_svg_art_linked", "hero_capsule_clean.png" in svg_txt and "fpo_placeholder" not in svg_txt, 1.8, "carton_master.svg artwork_panel missing hero_capsule_clean.png or still has fpo_placeholder"),
        ("a_svg_icc_attr", COLOR_PROFILE_TAG in svg_txt, 1.2, "carton_master.svg missing data-color-profile ICC tag"),
        ("a_art_check_png", (pkg / "Artwork_Panel_Check.png").is_file() and (pkg / "Artwork_Panel_Check.png").stat().st_size > 4000, 1.0, "Artwork_Panel_Check.png missing"),
    ]

    def _num_ok(obj: dict[str, Any], k: str, exp: float, tol: float = 0.15) -> bool:
        v = obj.get(k)
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    comp_png_no_fpo = False
    comp_p = pkg / "Carton_Composite_Preview.png"
    if comp_p.is_file():
        try:
            from PIL import Image

            cim = Image.open(comp_p).convert("RGB")
            px_c = cim.getpixel((300, 220))
            comp_png_no_fpo = not (px_c[0] > 220 and px_c[1] < 40 and px_c[2] > 130)
        except Exception:
            comp_png_no_fpo = False

    proof_pdf_p = pkg / "Carton_Press_Proof.pdf"
    proof_pdf_valid = False
    if proof_pdf_p.is_file() and proof_pdf_p.stat().st_size > 3000:
        if ora_b["ean13_full"] in proof_txt and ALLERGEN_CODE in proof_txt:
            proof_pdf_valid = True
        else:
            # Support prepress text-to-path PDF exports via poppler pdftoppm raster check
            cp_ppm = subprocess.run(
                ["pdftoppm", "-png", "-r", "72", "-singlefile", str(proof_pdf_p), "/tmp/aw02_proof_chk"],
                capture_output=True, timeout=20,
            )
            proof_pdf_valid = cp_ppm.returncode == 0 and Path("/tmp/aw02_proof_chk.png").is_file() and (ora_b["ean13_full"] in svg_txt)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_ean13_full", str(rep_b.get("ean13_full", "")).strip() == ora_b["ean13_full"], 1.8, f"ean13_full mismatch (expected {ora_b['ean13_full']})"),
        ("b_ean13_chk", rep_b.get("ean13_check_digit") == ora_b["ean13_check_digit"], 1.0, "ean13_check_digit mismatch"),
        ("b_mass_g", _num_ok(rep_b, "net_carton_mass_g", ora_b["net_carton_mass_g"], 0.15), 1.8, f"net_carton_mass_g mismatch (expected {ora_b['net_carton_mass_g']} after subtracting shell tare)"),
        ("b_mass_oz", _num_ok(rep_b, "net_carton_mass_oz", ora_b["net_carton_mass_oz"], 0.12), 1.2, "net_carton_mass_oz mismatch"),
        ("b_caff_cap", _num_ok(rep_b, "accepted_caffeine_mg_per_capsule", ora_b["accepted_caffeine_mg_per_capsule"], 0.25), 1.5, f"accepted_caffeine_mg_per_capsule mismatch (expected {ora_b['accepted_caffeine_mg_per_capsule']})"),
        ("b_efsa_100ml", _num_ok(rep_b, "efsa_caffeine_mg_per_100ml", ora_b["efsa_caffeine_mg_per_100ml"], 0.35), 2.0, f"efsa_caffeine_mg_per_100ml mismatch (expected {ora_b['efsa_caffeine_mg_per_100ml']} with 88% brew yield)"),
        ("b_allergen_code", str(rep_b.get("allergen_trace_code", "")).strip() == ALLERGEN_CODE, 1.5, "allergen_trace_code from portal missing/wrong"),
        ("b_fsc_id", str(rep_b.get("fsc_board_cert_id", "")).strip() == FSC_CERT_ID, 1.5, "fsc_board_cert_id from portal missing/wrong"),
        ("b_svg_dieline", "#ec008c" in svg_txt.lower() and "#00aeef" in svg_txt.lower() and '3.0' in svg_txt, 1.5, "carton_master.svg missing #EC008C cut / #00AEEF crease / 3.0mm bleed"),
        ("b_svg_reg_ean", ora_b["ean13_full"] in svg_txt and ALLERGEN_CODE in svg_txt and FSC_CERT_ID in svg_txt, 1.8, "carton_master.svg missing EAN-13 or regulatory codes"),
        ("b_proof_pdf", proof_pdf_valid, 1.5, "Carton_Press_Proof.pdf missing or invalid"),
        ("b_comp_png_exists", comp_p.is_file() and comp_p.stat().st_size > 5000, 1.0, "Carton_Composite_Preview.png missing"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_svg_preserves_both_roles",
            "hero_capsule_clean.png" in svg_txt
            and COLOR_PROFILE_TAG in svg_txt
            and "#ec008c" in svg_txt.lower()
            and ora_b["ean13_full"] in svg_txt
            and ALLERGEN_CODE in svg_txt,
            2.0,
            "Shared carton_master.svg lost either artwork_panel or dieline/regulatory/EAN-13 groups due to overwrite",
        ),
        (
            "j_composite_proof_clean_hero_and_ean",
            hero_ok and comp_png_no_fpo and proof_pdf_valid,
            2.0,
            "Composite preview / press proof still shows FPO magenta block or lacks clean GIMP hero + EAN-13",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"retouch_color_artist": TICKET_A, "prepress_dieline_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

"""AW-09: Single-Instance GIMP Dual-XCF Retouching & Shared Inkscape Campaign Sheet."""
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
from typing import Any
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    launch_studio_app,
    read_json_safe,
    resource_lock,
    write_json,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-09",
    "slug": "gimp_inkscape_brand_launch_kit",
    "title": "Single-Instance GIMP Dual-Master Retouching & Shared Inkscape Campaign Sheet",
    "domain": "Creative Studio Retouching & Vector Layout (GIMP 2.10 + Inkscape 1.2 + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19609,
    "roles": ("packshot_retouch_designer", "banner_layout_designer"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
    "mount_studio_ro": True,
}

CAMPAIGN_CODE = "SOLARIS-AW26-PRINT"

TICKET_A = (
    "# Work Order — Product Packshot Retouch Designer (`packshot_retouch_designer`)\n\n"
    "Retouch the studio packshot master in **GIMP**, complete the spot/CMYK ink estimate, and integrate the left packshot panel in `/workspace/campaign`:\n\n"
    "1. In the open **GIMP** window on the desktop, select the `packshot_master.xcf` image tab (`640x480`), hide or delete the bright magenta `FPO_WATERMARK_TOP` layer while keeping `Cobalt_Base` and `Amber_Bottle` visible, and use GIMP's `File -> Export As...` dialog to export `/srv/studio_project/exports/packshot_clean.png` (you can inspect `/srv/studio_project/exports/` read-only from your shell to confirm export).\n"
    "2. Review `/workspace/campaign/specs/Solaris_Brand_Spec.pdf`, query `/workspace/campaign/print_run.sqlite`, and check the **Solaris Brand Portal** in Chromium (`http://127.0.0.1:19609`, `Packshot Color & Ink` tab) to compute `adjusted_navy_cmyk` (`[C,M,Y,K]` scaled to `300.0%` TAC holding `K` fixed) and `packshot_ink_ml` (2 decimals), writing `/workspace/campaign/packshot_preflight.json` (`campaign_code`, `bottle_core_hex`, `adjusted_navy_cmyk`, `packshot_ink_ml`).\n"
    "3. Copy `/srv/studio_project/exports/packshot_clean.png` to `/workspace/campaign/assets/packshot_clean.png`, update `<g id=\"left_packshot_panel\">` in `/workspace/campaign/campaign_sheet.svg` to link `assets/packshot_clean.png` and include `campaign_code`, and render `/workspace/campaign/campaign_preview.png` via `inkscape`.\n"
)

TICKET_B = (
    "# Work Order — Lifestyle Hero & Copy Layout Designer (`banner_layout_designer`)\n\n"
    "Retouch the lifestyle hero master in **GIMP**, complete the GS1 coupon barcode & bleed calculation, and integrate the right lifestyle/barcode panel in `/workspace/campaign`:\n\n"
    "1. In the open **GIMP** window on the desktop, select the `lifestyle_hero.xcf` image tab (`640x480`), hide or delete the bright red `ALIGNMENT_GRID_OVERLAY` layer while keeping `Forest_Canvas` and `Cyan_Horizon` visible, and use GIMP's `File -> Export As...` dialog to export `/srv/studio_project/exports/lifestyle_clean.png`.\n"
    "2. Review `/workspace/campaign/specs/Solaris_Brand_Spec.pdf`, query `/workspace/campaign/print_run.sqlite`, and check the **Solaris Brand Portal** in Chromium (`http://127.0.0.1:19609`, `Headline & GS1 Coupon` tab) to compute the 13-digit EAN-13 coupon barcode (`ean13_coupon`), grosstrimmed poster area in square meters (`gross_bleed_area_m2`, 4 decimals including `4.0 mm` bleed on all 4 sides of `420 x 594 mm` A2!), and `paper_stock_kg` across the run, writing `/workspace/campaign/banner_layout_audit.json` (`campaign_code`, `horizon_accent_hex`, `ean13_coupon`, `gross_bleed_area_m2`, `paper_stock_kg`).\n"
    "3. Copy `/srv/studio_project/exports/lifestyle_clean.png` to `/workspace/campaign/assets/lifestyle_clean.png`, update `<g id=\"right_lifestyle_panel\">` in `/workspace/campaign/campaign_sheet.svg` to link `assets/lifestyle_clean.png` and render the `ean13_coupon` text, and export `/workspace/campaign/campaign_preview.png` and `/workspace/campaign/campaign_proof.pdf` via `inkscape`.\n"
)

INITIAL_CAMPAIGN_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="620" viewBox="0 0 1200 620">
  <rect x="0" y="0" width="1200" height="620" fill="#f8fafc"/>
  <g id="left_packshot_panel">
    <rect id="fpo_left" x="40" y="40" width="520" height="540" fill="#ff00aa"/>
    <text x="60" y="550" fill="#ffffff" font-family="DejaVu Sans" font-size="22">PENDING_PACKSHOT</text>
  </g>
  <g id="right_lifestyle_panel">
    <rect id="fpo_right" x="620" y="40" width="540" height="540" fill="#ff1111"/>
    <text x="640" y="550" fill="#ffffff" font-family="DejaVu Sans Mono" font-size="22">PENDING_EAN13</text>
  </g>
</svg>
"""


def compute_aw09_oracle() -> dict[str, Any]:
    # Navy CMYK: (82, 70, 62, 90) -> raw=304 > 300 -> scale=(300-90)/(82+70+62)=210/214
    sc = 210.0 / 214.0
    c_a, m_a, y_a, k_a = round(82.0 * sc, 1), round(70.0 * sc, 1), round(62.0 * sc, 1), 90.0
    # 18,000 sheets, 1.07 waste, packshot panel 0.085 m^2, cov 0.40, laydown 1.40 g/m^2, density 1.05 g/mL
    ink_g = 18000.0 * 1.07 * 0.085 * 0.40 * ((c_a + m_a + y_a + k_a) / 100.0) * 1.40
    ink_ml = round(ink_g / 1.05, 2)

    pref = "401829304615"
    digs = [int(x) for x in pref]
    chk = (10 - ((sum(digs[0::2]) + 3 * sum(digs[1::2])) % 10)) % 10
    ean13 = f"{pref}{chk}"
    # A2 trim 420x594 mm + 4mm bleed on all 4 edges -> 428 x 602 mm!
    bleed_m2 = round((0.428 * 0.602), 4)
    # 18,000 sheets * 1.07 waste * bleed_m2 * 250 gsm / 1000
    paper_kg = round(18000.0 * 1.07 * bleed_m2 * 0.250, 2)
    return {
        "campaign_code": CAMPAIGN_CODE,
        "bottle_core_hex": "#E68A1E",
        "adjusted_navy_cmyk": [c_a, m_a, y_a, k_a],
        "packshot_ink_ml": ink_ml,
        "horizon_accent_hex": "#14B8A6",
        "ean13_coupon": ean13,
        "gross_bleed_area_m2": bleed_m2,
        "paper_stock_kg": paper_kg,
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    cp_dir = workspace_root / "shared" / "campaign"
    (cp_dir / "assets").mkdir(parents=True, exist_ok=True)
    (cp_dir / "specs").mkdir(parents=True, exist_ok=True)
    (cp_dir / "campaign_sheet.svg").write_text(INITIAL_CAMPAIGN_SVG, encoding="utf-8")

    db_p = cp_dir / "print_run.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE run_specs (key TEXT PRIMARY KEY, val REAL, unit TEXT)")
    con.executemany(
        "INSERT INTO run_specs VALUES (?,?,?)",
        [
            ("press_sheet_qty", 18000.0, "sheets"),
            ("spoilage_allowance_pct", 7.0, "percent"),
            ("packshot_panel_area_m2", 0.085, "m2"),
            ("navy_coverage_frac", 0.40, "fraction"),
            ("ink_laydown_g_m2", 1.40, "g_m2"),
            ("ink_density_g_ml", 1.05, "g_ml"),
            ("a2_trim_width_mm", 420.0, "mm"),
            ("a2_trim_height_mm", 594.0, "mm"),
            ("bleed_each_edge_mm", 4.0, "mm"),
            ("board_grammage_gsm", 250.0, "g_m2"),
        ],
    )
    con.commit()
    con.close()

    write_pdf_manual(
        cp_dir / "specs" / "Solaris_Brand_Spec.pdf",
        "Solaris AW26 Campaign Prepress & Studio Retouching Standard",
        [
            (
                "1. GIMP Studio Masters & Export Directory",
                [
                    "Two camera XCF files (packshot_master.xcf and lifestyle_hero.xcf) are open as tabs inside GIMP on the desktop. Export clean 640x480 PNGs directly from GIMP into /srv/studio_project/exports/ after hiding each file's top FPO/grid overlay layer.",
                ],
            ),
            (
                "2. Process TAC Scaling, Ink Volume & Bleed Stock Calculation",
                [
                    "Scale C, M, Y proportionally while holding K fixed whenever raw C+M+Y+K exceeds 300.0% (1 decimal). Compute packshot_ink_ml = press_sheet_qty * (1 + spoilage/100) * packshot_panel_area_m2 * navy_coverage_frac * (adjusted_TAC/100) * ink_laydown_g_m2 / ink_density_g_ml.",
                    "Gross untrimmed sheet size adds bleed_each_edge_mm to ALL FOUR edges (width + 2*bleed, height + 2*bleed)! Compute gross_bleed_area_m2 (4 decimals) and paper_stock_kg = press_sheet_qty * (1 + spoilage/100) * gross_bleed_area_m2 * (board_grammage_gsm / 1000).",
                ],
            ),
        ],
    )

    (tickets_root / "packshot_retouch_designer").mkdir(parents=True, exist_ok=True)
    (tickets_root / "banner_layout_designer").mkdir(parents=True, exist_ok=True)
    (tickets_root / "packshot_retouch_designer" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "banner_layout_designer" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "packshot", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw09_sess" in ck) and (ck["aw09_sess"].value == tok)

        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", hdrs: list[tuple[str, str]] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for hk, hv in (hdrs or []):
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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw09_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Solaris Brand Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["packshot"])[0]
                with lock:
                    if t in ("packshot", "banner") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "packshot":
                body = f"""<h2>Packshot Color &amp; Navy Swatch Spec</h2>
                <p><b>Campaign Code:</b> <code>{CAMPAIGN_CODE}</code></p>
                <p><b>Solaris Deep Navy Raw CMYK:</b> <code>C=82.0%, M=70.0%, Y=62.0%, K=90.0%</code> (Raw TAC 304.0%)</p>"""
            else:
                body = f"""<h2>Headline &amp; GS1 Coupon Spec</h2>
                <p><b>Campaign Code:</b> <code>{CAMPAIGN_CODE}</code></p>
                <p><b>GS1 12-Digit Coupon Prefix:</b> <code>401829304615</code></p>"""
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Solaris Brand Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>Solaris Brand Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=packshot">Packshot Color &amp; Ink</a><a href="/tab?id=banner">Headline &amp; GS1 Coupon</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def _build_xcf(path: Path, bg_rgb: tuple[int, int, int], core_rgb: tuple[int, int, int], ov_rgb: tuple[int, int, int], base_n: str, core_n: str, ov_n: str) -> None:
    scm = (
        f'(let* ((img (car (gimp-image-new 640 480 RGB))) '
        f'(bg (car (gimp-layer-new img 640 480 RGB-IMAGE "{base_n}" 100 LAYER-MODE-NORMAL))) '
        f'(cr (car (gimp-layer-new img 320 240 RGBA-IMAGE "{core_n}" 100 LAYER-MODE-NORMAL))) '
        f'(ov (car (gimp-layer-new img 640 140 RGBA-IMAGE "{ov_n}" 100 LAYER-MODE-NORMAL)))) '
        f'(gimp-image-insert-layer img bg 0 0) (gimp-context-set-foreground \'({bg_rgb[0]} {bg_rgb[1]} {bg_rgb[2]})) (gimp-drawable-fill bg FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img cr 0 0) (gimp-layer-set-offsets cr 160 120) (gimp-context-set-foreground \'({core_rgb[0]} {core_rgb[1]} {core_rgb[2]})) (gimp-drawable-fill cr FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img ov 0 0) (gimp-layer-set-offsets ov 0 0) (gimp-context-set-foreground \'({ov_rgb[0]} {ov_rgb[1]} {ov_rgb[2]})) (gimp-drawable-fill ov FILL-FOREGROUND) '
        f'(gimp-xcf-save 0 img ov "{path}" "{path}") (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=35)


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1180, 780))
    priv = Path("/opt/aw09_masters")
    priv.mkdir(parents=True, exist_ok=True)
    p1 = priv / "packshot_master.xcf"
    p2 = priv / "lifestyle_hero.xcf"
    _build_xcf(p1, (18, 46, 88), (230, 138, 30), (255, 0, 170), "Cobalt_Base", "Amber_Bottle", "FPO_WATERMARK_TOP")
    _build_xcf(p2, (16, 62, 52), (20, 184, 166), (245, 20, 20), "Forest_Canvas", "Cyan_Horizon", "ALIGNMENT_GRID_OVERLAY")
    subprocess.run(["bash", "-lc", "id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; mkdir -p /srv/studio_project/exports && chown -R studio_ui:studio_ui /opt/aw09_masters /srv/studio_project && chmod 700 /opt/aw09_masters && chmod 755 /srv/studio_project /srv/studio_project/exports"], check=True, capture_output=True, timeout=15)

    xcf_args = []
    if "packshot_retouch_designer" in roles:
        xcf_args.append(f"'{p1}'")
    if "banner_layout_designer" in roles:
        xcf_args.append(f"'{p2}'")
    if xcf_args:
        launch_studio_app(f"nohup gimp --no-splash {' '.join(xcf_args)} >/tmp/aw09_gimp.log 2>&1 </dev/null &", wait_s=3.4)


def _export_clean(xcf_p: Path, out_p: Path) -> None:
    out_p.parent.mkdir(parents=True, exist_ok=True)
    scm = (
        f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xcf_p}" "{xcf_p}"))) '
        '(layers (cadr (gimp-image-get-layers img)))) '
        '(gimp-item-set-visible (aref layers 0) FALSE) '
        '(let ((m (car (gimp-image-merge-visible-layers img CLIP-TO-IMAGE)))) '
        f'(file-png-save-defaults RUN-NONINTERACTIVE img m "{out_p}" "{out_p}")) (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=35)
    out_p.chmod(0o644)


def _replace_svg_g(svg_p: Path, gid: str, g_xml: str, coop: bool) -> None:
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    root = ET.fromstring(svg_p.read_text(encoding="utf-8") if coop else INITIAL_CAMPAIGN_SVG)
    nel = ET.fromstring(g_xml)
    for i, ch in enumerate(list(root)):
        if ch.attrib.get("id") == gid:
            root.remove(ch)
            root.insert(i, nel)
            break
    svg_p.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    cp_dir = workspace_root / "shared" / "campaign"
    svg_p = cp_dir / "campaign_sheet.svg"
    ora = compute_aw09_oracle()
    exp_dir = Path("/srv/studio_project/exports")
    exp_dir.mkdir(parents=True, exist_ok=True)

    if role == "packshot_retouch_designer":
        _export_clean(Path("/opt/aw09_masters/packshot_master.xcf"), exp_dir / "packshot_clean.png")
        (cp_dir / "assets" / "packshot_clean.png").write_bytes((exp_dir / "packshot_clean.png").read_bytes())
        g_a = (
            f'<g xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" id="left_packshot_panel">'
            '<image x="40" y="40" width="520" height="390" href="assets/packshot_clean.png" xlink:href="assets/packshot_clean.png"/>'
            f'<text x="60" y="520" fill="#0f172a" font-family="DejaVu Sans" font-size="22">{CAMPAIGN_CODE}</text></g>'
        )
        if cooperative:
            with resource_lock("aw09_svg"):
                _replace_svg_g(svg_p, "left_packshot_panel", g_a, True)
                subprocess.run(["inkscape", str(svg_p), "--export-type=png", f"--export-filename={cp_dir / 'campaign_preview.png'}"], check=True, capture_output=True, timeout=30)
        else:
            _replace_svg_g(svg_p, "left_packshot_panel", g_a, False)
        write_json(
            cp_dir / "packshot_preflight.json",
            {
                "campaign_code": CAMPAIGN_CODE,
                "bottle_core_hex": ora["bottle_core_hex"],
                "adjusted_navy_cmyk": ora["adjusted_navy_cmyk"],
                "packshot_ink_ml": ora["packshot_ink_ml"],
            },
        )
    elif role == "banner_layout_designer":
        _export_clean(Path("/opt/aw09_masters/lifestyle_hero.xcf"), exp_dir / "lifestyle_clean.png")
        (cp_dir / "assets" / "lifestyle_clean.png").write_bytes((exp_dir / "lifestyle_clean.png").read_bytes())
        g_b = (
            f'<g xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" id="right_lifestyle_panel">'
            '<image x="620" y="40" width="520" height="390" href="assets/lifestyle_clean.png" xlink:href="assets/lifestyle_clean.png"/>'
            f'<text x="640" y="520" fill="#0f172a" font-family="DejaVu Sans Mono" font-size="24">{ora["ean13_coupon"]}</text></g>'
        )
        if cooperative:
            with resource_lock("aw09_svg"):
                _replace_svg_g(svg_p, "right_lifestyle_panel", g_b, True)
                subprocess.run(["inkscape", str(svg_p), "--export-type=png", f"--export-filename={cp_dir / 'campaign_preview.png'}"], check=True, capture_output=True, timeout=30)
                subprocess.run(["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={cp_dir / 'campaign_proof.pdf'}"], check=True, capture_output=True, timeout=30)
        else:
            _replace_svg_g(svg_p, "right_lifestyle_panel", g_b, False)
            subprocess.run(["inkscape", str(svg_p), "--export-type=png", f"--export-filename={cp_dir / 'campaign_preview.png'}"], check=True, capture_output=True, timeout=30)
            subprocess.run(["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={cp_dir / 'campaign_proof.pdf'}"], check=True, capture_output=True, timeout=30)
        write_json(
            cp_dir / "banner_layout_audit.json",
            {
                "campaign_code": CAMPAIGN_CODE,
                "horizon_accent_hex": ora["horizon_accent_hex"],
                "ean13_coupon": ora["ean13_coupon"],
                "gross_bleed_area_m2": ora["gross_bleed_area_m2"],
                "paper_stock_kg": ora["paper_stock_kg"],
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("packshot_retouch_designer", workspace_root, cooperative=False)
    solve_role("banner_layout_designer", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "packshot_retouch_designer", workspace_root, True)
        fb = pool.submit(solve_role, "banner_layout_designer", workspace_root, True)
        fa.result()
        fb.result()
    cp_dir = workspace_root / "shared" / "campaign"
    with resource_lock("aw09_svg"):
        subprocess.run(["inkscape", str(cp_dir / "campaign_sheet.svg"), "--export-type=png", f"--export-filename={cp_dir / 'campaign_preview.png'}"], check=True, capture_output=True, timeout=30)
        subprocess.run(["inkscape", str(cp_dir / "campaign_sheet.svg"), "--export-type=pdf", f"--export-filename={cp_dir / 'campaign_proof.pdf'}"], check=True, capture_output=True, timeout=30)


def _verify_png_colors(path: Path, top_rgb: tuple[int, int, int], mid_rgb: tuple[int, int, int]) -> bool:
    from PIL import Image

    if not path.is_file():
        return False
    try:
        im = Image.open(path).convert("RGB")
        if im.size != (640, 480):
            return False
        pt = im.getpixel((320, 50))
        pm = im.getpixel((320, 240))
        return all(abs(int(pt[i]) - top_rgb[i]) <= 24 for i in range(3)) and all(abs(int(pm[i]) - mid_rgb[i]) <= 24 for i in range(3))
    except Exception:
        return False


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    cp_dir = workspace_root / "shared" / "campaign"
    exp_dir = Path("/srv/studio_project/exports")
    ora = compute_aw09_oracle()
    ja = read_json_safe(cp_dir / "packshot_preflight.json")
    jb = read_json_safe(cp_dir / "banner_layout_audit.json")
    svg_txt = (cp_dir / "campaign_sheet.svg").read_text(encoding="utf-8", errors="replace") if (cp_dir / "campaign_sheet.svg").is_file() else ""

    gimp_a_ok = _verify_png_colors(exp_dir / "packshot_clean.png", (18, 46, 88), (230, 138, 30))
    gimp_b_ok = _verify_png_colors(exp_dir / "lifestyle_clean.png", (16, 62, 52), (20, 184, 166))

    cmyk_got = ja.get("adjusted_navy_cmyk") if isinstance(ja.get("adjusted_navy_cmyk"), list) else []
    cmyk_ok = len(cmyk_got) == 4 and all(isinstance(cmyk_got[i], (int, float)) and abs(float(cmyk_got[i]) - ora["adjusted_navy_cmyk"][i]) <= 0.25 for i in range(4))

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_gimp_studio_export", gimp_a_ok, 2.6, "/srv/studio_project/exports/packshot_clean.png missing or still has magenta FPO layer"),
        ("a_code_hex", ja.get("campaign_code") == CAMPAIGN_CODE and str(ja.get("bottle_core_hex", "")).upper() == "#E68A1E", 1.5, "campaign_code or bottle_core_hex (#E68A1E) mismatch"),
        ("a_navy_cmyk", cmyk_ok, 1.6, "adjusted_navy_cmyk mismatch"),
        ("a_ink_ml", isinstance(ja.get("packshot_ink_ml"), (int, float)) and abs(float(ja["packshot_ink_ml"]) - ora["packshot_ink_ml"]) <= 2.5, 1.8, f"packshot_ink_ml mismatch ({ora['packshot_ink_ml']})"),
        ("a_svg_left", "packshot_clean.png" in svg_txt and "fpo_left" not in svg_txt, 1.8, "campaign_sheet.svg missing packshot_clean.png"),
        ("a_preview_png", (cp_dir / "campaign_preview.png").is_file() and (cp_dir / "campaign_preview.png").stat().st_size > 4000, 1.2, "campaign_preview.png missing"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_gimp_studio_export", gimp_b_ok, 2.6, "/srv/studio_project/exports/lifestyle_clean.png missing or still has red grid layer"),
        ("b_code_hex", jb.get("campaign_code") == CAMPAIGN_CODE and str(jb.get("horizon_accent_hex", "")).upper() == "#14B8A6", 1.5, "campaign_code or horizon_accent_hex (#14B8A6) mismatch"),
        ("b_ean13", str(jb.get("ean13_coupon", "")).strip() == ora["ean13_coupon"], 1.6, f"ean13_coupon mismatch ({ora['ean13_coupon']})"),
        ("b_bleed_area", isinstance(jb.get("gross_bleed_area_m2"), (int, float)) and abs(float(jb["gross_bleed_area_m2"]) - ora["gross_bleed_area_m2"]) <= 0.0005, 1.8, f"gross_bleed_area_m2 mismatch ({ora['gross_bleed_area_m2']}, add 4mm on all 4 sides)"),
        ("b_paper_kg", isinstance(jb.get("paper_stock_kg"), (int, float)) and abs(float(jb["paper_stock_kg"]) - ora["paper_stock_kg"]) <= 2.0, 1.8, f"paper_stock_kg mismatch ({ora['paper_stock_kg']})"),
        ("b_svg_right_pdf", "lifestyle_clean.png" in svg_txt and ora["ean13_coupon"] in svg_txt and (cp_dir / "campaign_proof.pdf").is_file(), 1.8, "campaign_sheet.svg or campaign_proof.pdf missing lifestyle_clean.png / EAN-13"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_both_gimp_exports_and_svg_panels_clean",
            gimp_a_ok and gimp_b_ok and "packshot_clean.png" in svg_txt and "lifestyle_clean.png" in svg_txt and ora["ean13_coupon"] in svg_txt,
            2.5,
            "Single-instance GIMP export collision or shared campaign_sheet.svg overwrite lost one role's retouched panel",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"packshot_retouch_designer": TICKET_A, "banner_layout_designer": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

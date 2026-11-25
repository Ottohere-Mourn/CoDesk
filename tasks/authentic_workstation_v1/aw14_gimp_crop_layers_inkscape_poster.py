"""AW-14: Single-Instance GIMP Multi-Layer Hide + Image Scale & Shared Inkscape Scientific Poster."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

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
    "id": "AW-14",
    "slug": "gimp_crop_layers_inkscape_poster",
    "title": "Single-Instance GIMP 4-Layer Hide & 600x400 Scale + Live Inkscape Symposium Poster",
    "domain": "Scientific Imaging & Vector Poster Production (GIMP 2.10 + Inkscape 1.2 + Chromium + 72-Row SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19614,
    "roles": ("microscopy_img_analyst", "gel_blot_analyst"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
    "mount_studio_ro": True,
}

SYMPOSIUM_ID = "BIOPHOTON-2026-P18"

TICKET_A = (
    "# Work Order — Fluorescence Microscopy Imaging Analyst (`microscopy_img_analyst`)\n\n"
    "Process the multi-layer microscopy capture inside **GIMP**, update Panel A in the shared **Inkscape** poster (`/workspace/assay/poster_layout.svg`), and compute Beer-Lambert concentration metrics from the 48-well micro-plate dataset in `/workspace/assay`:\n\n"
    "1. In the open **GIMP** window on the desktop, select the `fluorescence_a.xcf` (`900x600`) image tab, hide **both** non-production FPO/calibration layers while keeping `DAPI_Nuclei_Bg` and `GFP_Signal_Core` visible, scale the image canvas to exact **`600x400`** (`Image -> Scale Image...`), and export via `File -> Export As...` to `/srv/studio_project/exports/fluorescence_600x400.png` (`/srv/studio_project` is mounted read-only in your terminal for post-export verification).\n"
    "2. Read `/workspace/assay/specs/Assay_Imaging_Protocol.pdf`, query `/workspace/assay/plate_readings.sqlite` (`cuvette_od`), and inspect the **BioPhoton Portal** in Chromium (`http://127.0.0.1:19614`, `Fluorophore Extinction` tab) to compute QC-filtered `mean_blank_corrected_od` (3 decimals), `sample_conc_um` (2 decimals), and `gfp_core_hex`, writing `/workspace/assay/microscopy_metrics.json` (`symposium_id`, `valid_sample_well_count`, `gfp_core_hex`, `mean_blank_corrected_od`, `sample_conc_um`).\n"
    "3. Update `<g id=\"panel_a\">` in `/workspace/assay/poster_layout.svg` (preserving `<g id=\"panel_b\">`!) so the Panel A caption includes `SYMPOSIUM_ID` and `sample_conc_um`.\n"
)

TICKET_B = (
    "# Work Order — Gel Electrophoresis & Blot Analyst (`gel_blot_analyst`)\n\n"
    "Process the multi-layer gel blot capture inside **GIMP**, update Panel B in the shared **Inkscape** poster (`/workspace/assay/poster_layout.svg`), and compute housekeeping-normalized fold-change metrics from the 24-lane densitometry dataset in `/workspace/assay`:\n\n"
    "1. In the open **GIMP** window on the desktop, select the `electrophoresis_b.xcf` (`900x600`) image tab, hide **both** non-production ruler/QC layers while keeping `Gel_Matrix_Bg` and `Target_Band_Cyan` visible, scale the image canvas to exact **`600x400`** (`Image -> Scale Image...`), and export via `File -> Export As...` to `/srv/studio_project/exports/electrophoresis_600x400.png` (`/srv/studio_project` is mounted read-only in your terminal for post-export verification).\n"
    "2. Read `/workspace/assay/specs/Assay_Imaging_Protocol.pdf`, query `/workspace/assay/plate_readings.sqlite` (`densitometry_lanes`), and inspect the **BioPhoton Portal** in Chromium (`http://127.0.0.1:19614`, `Housekeeping Normalization` tab) to compute QC-filtered `control_norm_ratio` (3 decimals), `treated_fold_change` (2 or 3 decimals), and `band_cyan_hex`, writing `/workspace/assay/blot_metrics.json` (`symposium_id`, `valid_lane_count`, `band_cyan_hex`, `control_norm_ratio`, `treated_fold_change`).\n"
    "3. Update `<g id=\"panel_b\">` in `/workspace/assay/poster_layout.svg` (preserving `<g id=\"panel_a\">`!) so the Panel B caption includes `SYMPOSIUM_ID` and `treated_fold_change`, and export `/workspace/assay/poster_proof.pdf` via `inkscape`.\n"
)

INIT_POSTER_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="540" viewBox="0 0 1000 540">
  <rect x="0" y="0" width="1000" height="540" fill="#f8fafc"/>
  <g id="panel_a"><text x="50" y="120" font-family="DejaVu Sans" font-size="22">PANEL_A_PENDING</text></g>
  <g id="panel_b"><text x="520" y="120" font-family="DejaVu Sans" font-size="22">PANEL_B_PENDING</text></g>
</svg>
"""


def _build_plate_rows() -> tuple[list[tuple[str, str, str, float]], list[tuple[str, str, str, float, float]]]:
    cuv_rows: list[tuple[str, str, str, float]] = []
    blanks = [0.042, 0.048, 0.044, 0.046, 0.043, 0.047, 0.045, 0.045]
    for idx, od in enumerate(blanks, start=1):
        cuv_rows.append((f"W-B{idx:02d}", "blank", "VALID", od))
    base_samp = [0.680, 0.710, 0.690, 0.700] * 8
    for idx, od in enumerate(base_samp, start=1):
        cuv_rows.append((f"W-S{idx:02d}", "sample", "VALID", od))
    for idx in range(1, 5):
        cuv_rows.append((f"W-X{idx:02d}", "sample", "BUBBLE_ARTIFACT", 1.420 + 0.03 * idx))
    for idx in range(5, 9):
        cuv_rows.append((f"W-X{idx:02d}", "sample", "SATURATED_OVERFLOW", 3.950))

    lane_rows: list[tuple[str, str, str, float, float]] = []
    scales_c = [0.95, 1.05, 0.98, 1.02, 0.96, 1.04, 0.99, 1.01]
    for idx, s in enumerate(scales_c, start=1):
        lane_rows.append((f"LN-C{idx:02d}", "Control", "VALID", round(120.0 + 800.0 * s, 2), round(120.0 + 1000.0 * s, 2)))
    scales_t = [0.94, 1.06, 0.97, 1.03, 0.95, 1.05, 0.98, 1.02, 0.96, 1.04, 0.99, 1.01]
    for idx, s in enumerate(scales_t, start=1):
        lane_rows.append((f"LN-T{idx:02d}", "Treated_24h", "VALID", round(120.0 + 1840.0 * s, 2), round(120.0 + 800.0 * s, 2)))
    for idx in range(1, 5):
        lane_rows.append((f"LN-X{idx:02d}", "Treated_24h", "HEMOLYZED_EXCLUDE", 3100.0, 410.0))
    return cuv_rows, lane_rows


def compute_aw14_oracle() -> dict[str, Any]:
    od_corr = 0.650
    conc_um = 52.00
    return {
        "symposium_id": SYMPOSIUM_ID,
        "valid_sample_well_count": 32,
        "gfp_core_hex": "#22C55E",
        "mean_blank_corrected_od": od_corr,
        "sample_conc_um": conc_um,
        "valid_lane_count": 20,
        "band_cyan_hex": "#06B6D4",
        "control_norm_ratio": 0.800,
        "treated_fold_change_exact": 2.875,
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    ad = workspace_root / "shared" / "assay"
    (ad / "specs").mkdir(parents=True, exist_ok=True)
    (ad / "poster_layout.svg").write_text(INIT_POSTER_SVG, encoding="utf-8")

    cuv_rows, lane_rows = _build_plate_rows()
    db_p = ad / "plate_readings.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE cuvette_od (well_id TEXT PRIMARY KEY, kind TEXT, qc_flag TEXT, od_488nm REAL)")
    con.executemany("INSERT INTO cuvette_od VALUES (?,?,?,?)", cuv_rows)
    con.execute("CREATE TABLE densitometry_lanes (lane_id TEXT PRIMARY KEY, cohort TEXT, qc_flag TEXT, target_raw REAL, actin_housekeeping_raw REAL)")
    con.executemany("INSERT INTO densitometry_lanes VALUES (?,?,?,?,?)", lane_rows)
    con.commit()
    con.close()

    write_pdf_manual(
        ad / "specs" / "Assay_Imaging_Protocol.pdf",
        "Symposium Optical Assay & Multi-Layer GIMP Protocol",
        [
            (
                "1. 48-Well Micro-Cuvette Beer-Lambert Concentration",
                [
                    "Exclude any well where qc_flag != 'VALID' (such as BUBBLE_ARTIFACT or SATURATED_OVERFLOW). Compute mean_blank_corrected_od = mean(valid sample od_488nm) - mean(valid blank od_488nm).",
                    "Using epsilon_mM_cm and optical_path_cm from the BioPhoton Portal (Fluorophore Extinction tab), compute micromolar concentration sample_conc_um = (mean_blank_corrected_od / (epsilon_mM_cm * optical_path_cm)) * 1000.0.",
                ],
            ),
            (
                "2. 24-Lane Housekeeping-Normalized Western Blot Fold-Change",
                [
                    "Include only lanes with qc_flag = 'VALID' (excluding HEMOLYZED_EXCLUDE). Subtract membrane_bg_intensity (from BioPhoton Portal, Housekeeping Normalization tab) from BOTH target_raw and actin_housekeeping_raw on every valid lane.",
                    "Compute each cohort's normalized ratio (target_net / actin_net) across Control and Treated_24h, then compute treated_fold_change = Treated_24h_norm_ratio / Control_norm_ratio.",
                ],
            ),
            (
                "3. GIMP 4-Layer Cleanup & 600x400 Scaling",
                [
                    "In GIMP, hide both non-production top layers (DRAFT_STAMP_MAGENTA and CALIBRATION_CROSSHAIR_YELLOW in fluorescence_a.xcf; LANE_RULER_RED and QC_BANNER_ORANGE in electrophoresis_b.xcf), scale image dimensions to 600x400, and export PNG to /srv/studio_project/exports/.",
                ],
            ),
        ],
    )
    (tickets_root / "microscopy_img_analyst").mkdir(parents=True, exist_ok=True)
    (tickets_root / "gel_blot_analyst").mkdir(parents=True, exist_ok=True)
    (tickets_root / "microscopy_img_analyst" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "gel_blot_analyst" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "fluor", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw14_sess" in ck) and (ck["aw14_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw14_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 BioPhoton Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["fluor"])[0]
                with lock:
                    if t in ("fluor", "blot") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "fluor":
                body = f"<h2>Fluorophore Extinction ({SYMPOSIUM_ID})</h2><p><code>epsilon_mM_cm = 25.0</code> | <code>optical_path_cm = 0.50</code></p>"
            else:
                body = f"<h2>Housekeeping Densitometry ({SYMPOSIUM_ID})</h2><p><code>membrane_bg_intensity = 120.0</code></p>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>BioPhoton Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>BioPhoton Assay Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=fluor">Fluorophore Extinction</a><a href="/tab?id=blot">Housekeeping Normalization</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def _make_4layer_xcf(path: Path, bg: tuple[int, int, int], core: tuple[int, int, int], ov1: tuple[int, int, int], ov2: tuple[int, int, int], n_bg: str, n_core: str, n_ov1: str, n_ov2: str) -> None:
    scm = (
        f'(let* ((img (car (gimp-image-new 900 600 RGB))) '
        f'(l_bg (car (gimp-layer-new img 900 600 RGB-IMAGE "{n_bg}" 100 LAYER-MODE-NORMAL))) '
        f'(l_cr (car (gimp-layer-new img 450 300 RGBA-IMAGE "{n_core}" 100 LAYER-MODE-NORMAL))) '
        f'(l_o2 (car (gimp-layer-new img 900 180 RGBA-IMAGE "{n_ov2}" 100 LAYER-MODE-NORMAL))) '
        f'(l_o1 (car (gimp-layer-new img 900 180 RGBA-IMAGE "{n_ov1}" 100 LAYER-MODE-NORMAL)))) '
        f'(gimp-image-insert-layer img l_bg 0 0) (gimp-context-set-foreground \'({bg[0]} {bg[1]} {bg[2]})) (gimp-drawable-fill l_bg FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img l_cr 0 0) (gimp-layer-set-offsets l_cr 225 150) (gimp-context-set-foreground \'({core[0]} {core[1]} {core[2]})) (gimp-drawable-fill l_cr FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img l_o2 0 0) (gimp-layer-set-offsets l_o2 0 420) (gimp-context-set-foreground \'({ov2[0]} {ov2[1]} {ov2[2]})) (gimp-drawable-fill l_o2 FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img l_o1 0 0) (gimp-layer-set-offsets l_o1 0 0) (gimp-context-set-foreground \'({ov1[0]} {ov1[1]} {ov1[2]})) (gimp-drawable-fill l_o1 FILL-FOREGROUND) '
        f'(gimp-xcf-save 0 img l_o1 "{path}" "{path}") (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=35)


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1160, 760))
    priv = Path("/opt/aw14_masters")
    priv.mkdir(parents=True, exist_ok=True)
    xa = priv / "fluorescence_a.xcf"
    xb = priv / "electrophoresis_b.xcf"
    _make_4layer_xcf(xa, (15, 23, 66), (34, 197, 94), (255, 0, 170), (250, 204, 21), "DAPI_Nuclei_Bg", "GFP_Signal_Core", "DRAFT_STAMP_MAGENTA", "CALIBRATION_CROSSHAIR_YELLOW")
    _make_4layer_xcf(xb, (24, 32, 44), (6, 182, 212), (239, 68, 68), (249, 115, 22), "Gel_Matrix_Bg", "Target_Band_Cyan", "LANE_RULER_RED", "QC_BANNER_ORANGE")
    subprocess.run(
        [
            "bash",
            "-lc",
            "id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; "
            "mkdir -p /srv/studio_project/exports && "
            "chown -R studio_ui:studio_ui /opt/aw14_masters /srv/studio_project && "
            "chmod 700 /opt/aw14_masters && chmod -R 755 /srv/studio_project",
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )

    args = []
    if "microscopy_img_analyst" in roles:
        args.append(f"'{xa}'")
    if "gel_blot_analyst" in roles:
        args.append(f"'{xb}'")
    if args:
        launch_studio_app(f"nohup gimp --no-splash {' '.join(args)} >/tmp/aw14_gimp.log 2>&1 </dev/null &", wait_s=3.4)
    launch_studio_app("nohup inkscape '/ws_root/shared/assay/poster_layout.svg' >/tmp/aw14_ink.log 2>&1 </dev/null &", wait_s=2.2)


def _clean_scale_xcf(xcf_p: Path, out_p: Path) -> None:
    out_p.parent.mkdir(parents=True, exist_ok=True)
    scm = (
        f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xcf_p}" "{xcf_p}"))) '
        '(layers (cadr (gimp-image-get-layers img)))) '
        '(gimp-item-set-visible (aref layers 0) FALSE) '
        '(gimp-item-set-visible (aref layers 1) FALSE) '
        '(gimp-image-scale img 600 400) '
        '(let ((m (car (gimp-image-merge-visible-layers img CLIP-TO-IMAGE)))) '
        f'(file-png-save-defaults RUN-NONINTERACTIVE img m "{out_p}" "{out_p}")) (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=35)
    subprocess.run(["chmod", "644", str(out_p)], capture_output=True, timeout=5)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    ad = workspace_root / "shared" / "assay"
    svg_p = ad / "poster_layout.svg"
    ora = compute_aw14_oracle()
    exp_d = Path("/srv/studio_project/exports")
    exp_d.mkdir(parents=True, exist_ok=True)

    if role == "microscopy_img_analyst":
        _clean_scale_xcf(Path("/opt/aw14_masters/fluorescence_a.xcf"), exp_d / "fluorescence_600x400.png")
        write_json(
            ad / "microscopy_metrics.json",
            {
                "symposium_id": SYMPOSIUM_ID,
                "valid_sample_well_count": ora["valid_sample_well_count"],
                "gfp_core_hex": ora["gfp_core_hex"],
                "mean_blank_corrected_od": ora["mean_blank_corrected_od"],
                "sample_conc_um": ora["sample_conc_um"],
            },
        )
        if cooperative:
            with resource_lock("aw14_svg"):
                txt = svg_p.read_text(encoding="utf-8")
                svg_p.write_text(txt.replace("PANEL_A_PENDING", f"{SYMPOSIUM_ID} | {ora['sample_conc_um']} uM"), encoding="utf-8")
        else:
            svg_p.write_text(INIT_POSTER_SVG.replace("PANEL_A_PENDING", f"{SYMPOSIUM_ID} | {ora['sample_conc_um']} uM"), encoding="utf-8")
    elif role == "gel_blot_analyst":
        _clean_scale_xcf(Path("/opt/aw14_masters/electrophoresis_b.xcf"), exp_d / "electrophoresis_600x400.png")
        write_json(
            ad / "blot_metrics.json",
            {
                "symposium_id": SYMPOSIUM_ID,
                "valid_lane_count": ora["valid_lane_count"],
                "band_cyan_hex": ora["band_cyan_hex"],
                "control_norm_ratio": ora["control_norm_ratio"],
                "treated_fold_change": ora["treated_fold_change_exact"],
            },
        )
        if cooperative:
            with resource_lock("aw14_svg"):
                txt = svg_p.read_text(encoding="utf-8")
                svg_p.write_text(txt.replace("PANEL_B_PENDING", f"{SYMPOSIUM_ID} | {ora['treated_fold_change_exact']}x"), encoding="utf-8")
                subprocess.run(["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={ad / 'poster_proof.pdf'}"], check=True, capture_output=True, timeout=30)
        else:
            svg_p.write_text(INIT_POSTER_SVG.replace("PANEL_B_PENDING", f"{SYMPOSIUM_ID} | {ora['treated_fold_change_exact']}x"), encoding="utf-8")
            subprocess.run(["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={ad / 'poster_proof.pdf'}"], check=True, capture_output=True, timeout=30)


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("microscopy_img_analyst", workspace_root, cooperative=False)
    solve_role("gel_blot_analyst", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "microscopy_img_analyst", workspace_root, True)
        fb = pool.submit(solve_role, "gel_blot_analyst", workspace_root, True)
        fa.result()
        fb.result()
    ad = workspace_root / "shared" / "assay"
    with resource_lock("aw14_svg"):
        subprocess.run(["inkscape", str(ad / "poster_layout.svg"), "--export-type=pdf", f"--export-filename={ad / 'poster_proof.pdf'}"], check=True, capture_output=True, timeout=30)


def _check_scaled_png(path: Path, bg_rgb: tuple[int, int, int], core_rgb: tuple[int, int, int]) -> tuple[bool, bool]:
    from PIL import Image

    if not path.is_file():
        return False, False
    try:
        im = Image.open(path).convert("RGB")
        size_ok = im.size == (600, 400)
        w, h = im.size
        p_top = im.getpixel((w // 2, int(h * 0.08)))
        p_bot = im.getpixel((w // 2, int(h * 0.92)))
        p_mid = im.getpixel((w // 2, h // 2))
        layers_ok = (
            all(abs(int(p_top[i]) - bg_rgb[i]) <= 26 for i in range(3))
            and all(abs(int(p_bot[i]) - bg_rgb[i]) <= 26 for i in range(3))
            and all(abs(int(p_mid[i]) - core_rgb[i]) <= 26 for i in range(3))
        )
        return size_ok, layers_ok
    except Exception:
        return False, False


def _svg_has_float(svg_txt: str, target: float, tol: float) -> bool:
    for m in re.findall(r"\d+(?:\.\d+)?", svg_txt):
        try:
            if abs(float(m) - target) <= tol:
                return True
        except ValueError:
            continue
    return False


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    ad = workspace_root / "shared" / "assay"
    exp_d = Path("/srv/studio_project/exports")
    ora = compute_aw14_oracle()
    ja = read_json_safe(ad / "microscopy_metrics.json")
    jb = read_json_safe(ad / "blot_metrics.json")
    svg_txt = (ad / "poster_layout.svg").read_text(encoding="utf-8", errors="replace") if (ad / "poster_layout.svg").is_file() else ""

    sz_a, ly_a = _check_scaled_png(exp_d / "fluorescence_600x400.png", (15, 23, 66), (34, 197, 94))
    sz_b, ly_b = _check_scaled_png(exp_d / "electrophoresis_600x400.png", (24, 32, 44), (6, 182, 212))

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_gimp_layers_hidden", ly_a, 2.4, "fluorescence_600x400.png missing or still shows magenta/yellow artifact layers"),
        ("a_gimp_scaled_600x400", sz_a, 2.2, "fluorescence_600x400.png not scaled to exact 600x400 in GIMP"),
        ("a_hex", str(ja.get("gfp_core_hex", "")).upper() == "#22C55E", 1.2, "gfp_core_hex mismatch (#22C55E)"),
        ("a_conc_um", ja.get("valid_sample_well_count") == 32 and isinstance(ja.get("sample_conc_um"), (int, float)) and abs(float(ja["sample_conc_um"]) - ora["sample_conc_um"]) <= 0.5, 1.8, f"sample_conc_um or valid_sample_well_count mismatch ({ora['sample_conc_um']})"),
        ("a_svg_panel_a", _svg_has_float(svg_txt, ora["sample_conc_um"], 0.5) and SYMPOSIUM_ID in svg_txt, 1.6, "poster_layout.svg missing Panel A sample_conc_um caption"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_gimp_layers_hidden", ly_b, 2.4, "electrophoresis_600x400.png missing or still shows red/orange artifact layers"),
        ("b_gimp_scaled_600x400", sz_b, 2.2, "electrophoresis_600x400.png not scaled to exact 600x400 in GIMP"),
        ("b_hex", str(jb.get("band_cyan_hex", "")).upper() == "#06B6D4", 1.2, "band_cyan_hex mismatch (#06B6D4)"),
        ("b_fold", jb.get("valid_lane_count") == 20 and isinstance(jb.get("treated_fold_change"), (int, float)) and abs(float(jb["treated_fold_change"]) - ora["treated_fold_change_exact"]) <= 0.03, 1.8, f"treated_fold_change or valid_lane_count mismatch ({ora['treated_fold_change_exact']})"),
        ("b_svg_panel_b", _svg_has_float(svg_txt, ora["treated_fold_change_exact"], 0.025) and SYMPOSIUM_ID in svg_txt and (ad / "poster_proof.pdf").is_file(), 1.6, "poster_layout.svg / poster_proof.pdf missing Panel B fold-change caption (~2.875)"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_shared_poster_retains_both_panels",
            "PANEL_A_PENDING" not in svg_txt
            and "PANEL_B_PENDING" not in svg_txt
            and _svg_has_float(svg_txt, ora["sample_conc_um"], 0.5)
            and _svg_has_float(svg_txt, ora["treated_fold_change_exact"], 0.025),
            2.5,
            "Concurrent overwrite on /workspace/assay/poster_layout.svg lost Panel A or Panel B",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"microscopy_img_analyst": TICKET_A, "gel_blot_analyst": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

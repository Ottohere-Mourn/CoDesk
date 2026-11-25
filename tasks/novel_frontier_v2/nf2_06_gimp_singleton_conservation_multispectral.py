"""NF2-06: Singleton GIMP 2.10 (`org.gimp.GIMP.UI`) Dual-.xcf Focus/Tab Contention — Art Conservation UV Varnish vs. X-Ray Craquelure."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
from typing import Any
from urllib.parse import urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    inspect_live_x11_window_titles_readonly,
    launch_chromium_natural,
    launch_gimp_gui_natural,
    make_canary_code,
    read_json_safe,
    write_json,
    write_multipage_sop_pdf,
)

TASK_ID = "NF2-06"
PORTAL_PORT = 19606

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Singleton `GIMP 2.10` (`org.gimp.GIMP.UI`) Multi-`.xcf` Tab Contention: UV-Fluorescence Varnish Retouch vs. X-Ray Dendrochronology",
    "domain": "Museum Art Conservation Multispectral Imaging (`GIMP 2.10` `.xcf`) & Archaeometric Spectroscopy (`SQLite`)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("uv_varnish_conservator", "xray_craquelure_analyst"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

UV_REG_CODE = make_canary_code("LOUVRE-UV", "mastic-varnish-365nm")
XRAY_REG_CODE = make_canary_code("LOUVRE-XR", "baltic-oak-panel-42kv")


def _build_xcf_via_gimp(xcf_path: Path, w: int, h: int, bg_rgb: tuple[int, int, int], ov_name: str, ov_rgb: tuple[int, int, int]) -> None:
    xcf_path.parent.mkdir(parents=True, exist_ok=True)
    scm = (
        f'(let* ((img (car (gimp-image-new {w} {h} RGB))) '
        f'(bg (car (gimp-layer-new img {w} {h} RGB-IMAGE "Master_Scan" 100 LAYER-MODE-NORMAL))) '
        f'(ov (car (gimp-layer-new img {w} {h} RGBA-IMAGE "{ov_name}" 100 LAYER-MODE-NORMAL)))) '
        f'(gimp-image-insert-layer img bg 0 0) '
        f'(gimp-context-set-foreground \x27({bg_rgb[0]} {bg_rgb[1]} {bg_rgb[2]})) '
        f'(gimp-drawable-fill bg FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img ov 0 0) '
        f'(gimp-context-set-foreground \x27({ov_rgb[0]} {ov_rgb[1]} {ov_rgb[2]})) '
        f'(gimp-drawable-fill ov FILL-FOREGROUND) '
        f'(gimp-xcf-save 0 img ov "{xcf_path}" "{xcf_path}") '
        f'(gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=45)


def _inspect_xcf(xcf_path: Path) -> dict[str, Any]:
    if not xcf_path.is_file():
        return {"valid": False}
    out_json = Path(f"/tmp/nf206_xcf_{secrets.token_hex(4)}.json")
    scm = (
        f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xcf_path}" "{xcf_path}"))) '
        f'(w (car (gimp-image-width img))) (h (car (gimp-image-height img))) '
        f'(lyrs (cadr (gimp-image-get-layers img))) '
        f'(n (car (gimp-image-get-layers img))) '
        f'(p (open-output-file "{out_json}"))) '
        f'(display (string-append "{{\\"w\\":" (number->string w) ",\\"h\\":" (number->string h) ",\\"n\\":" (number->string n) "}}") p) '
        f'(close-output-port p) (gimp-quit 0))'
    )
    try:
        subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=35)
        d = read_json_safe(out_json)
        out_json.unlink(missing_ok=True)
        return {"valid": True, **d}
    except Exception:
        return {"valid": False}


def _generate_ftir_rows() -> list[dict[str, Any]]:
    pigments = [("LAPIS_ULTRAMARINE", 1018.0), ("VERMILION_HGS", 344.0), ("LEAD_TIN_YELLOW", 455.0), ("AZURITE_COPPER", 952.0)]
    rows = []
    for i in range(1, 341):
        pg, wn = pigments[(i - 1) % 4]
        raw_abs = round(0.42 + (i % 13) * 0.035 + (0.28 if pg == "LAPIS_ULTRAMARINE" else 0.0), 4)
        rows.append({
            "spot_id": i, "pigment_class": pg, "wavenumber_cm1": wn, "raw_absorbance": raw_abs,
            "later_overpaint_flag": 1 if (i % 9 == 0) else 0,
            "scan_quality": "CLEAN_ATR" if (i % 23 != 0) else "FLUORESCENCE_SATURATED",
        })
    return rows


def _generate_dendro_rows() -> list[dict[str, Any]]:
    # 3 planks x 110 annual rings (330 rows) in microns!
    rows = []
    for plank in ("PLANK_A_BALTIC", "PLANK_B_BALTIC", "PLANK_C_RESTORED_1890"):
        for yr_idx in range(1, 111):
            w_um = 1420 + int(280 * ((yr_idx * 7) % 11) / 10.0)
            is_sapwood = 1 if yr_idx > 102 else 0
            rows.append({
                "ring_row": len(rows) + 1, "plank_id": plank, "ring_seq": yr_idx,
                "ring_width_microns": w_um, "is_sapwood": is_sapwood,
            })
    return rows


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    # Role A: Blank parchment baseline absorbance = 0.0480 in secondary table substrate_blank_baseline!
    frows = [r for r in _generate_ftir_rows() if r["scan_quality"] == "CLEAN_ATR" and r["later_overpaint_flag"] == 0]
    by_pg: dict[str, list[float]] = {}
    for r in frows:
        by_pg.setdefault(r["pigment_class"], []).append(r["raw_absorbance"] - 0.0480)
    pg_means = {k: round(sum(v) / len(v), 4) for k, v in sorted(by_pg.items())}
    or_a = {
        "authentic_spot_count": len(frows),
        "pigment_net_absorbance": pg_means,
        "dominant_pigment": max(pg_means, key=lambda k: pg_means[k]),
        "uv_registry_code": UV_REG_CODE,
    }

    # Role B: Exclude 1890 restoration plank PLANK_C_RESTORED_1890; last heartwood ring = 1518 CE (crossdate_anchor in SQLite),
    # plus Baltic oak minimum missing-sapwood/seasoning allowance: max(0, 15 - observed_sapwood_rings) + 4yr seasoning!
    # Observed sapwood rings per original plank = 8 (103..110), so terminus post quem felling year = 1518 + 8 + (15 - 8) + 4 = 1537!
    drows = [r for r in _generate_dendro_rows() if r["plank_id"] != "PLANK_C_RESTORED_1890"]
    mean_mm = sum(r["ring_width_microns"] / 1000.0 for r in drows) / len(drows)
    obs_sap = sum(1 for r in drows if r["plank_id"] == "PLANK_A_BALTIC" and r["is_sapwood"] == 1)  # 8
    tpq_year = 1518 + obs_sap + max(0, 15 - obs_sap) + 4  # 1537
    or_b = {
        "original_ring_measurement_count": len(drows),
        "mean_original_ring_width_mm": round(mean_mm, 4),
        "observed_sapwood_rings_per_plank": obs_sap,
        "earliest_panel_usage_year_ce": tpq_year,
        "xray_registry_code": XRAY_REG_CODE,
    }
    return or_a, or_b


UV_ORACLE, XRAY_ORACLE = _compute_oracles()

PORTAL_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Museum Multispectral Registry</title>
<style>body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace} .box{background:#1e293b;padding:16px;border:1px solid #334155;margin-top:12px}</style></head><body>
<h2>Conservation Lab Multispectral Imaging Registry</h2>
<div class="box">
  <h3>365nm UV-Fluorescence Varnish Protocol</h3>
  <p>In GIMP (`panel_uv_fluorescence.xcf`), hide/remove layer <code>Calibration_Magenta_Veil</code> so the cobalt-blue varnish layer is exposed, resize/crop canvas to <code>640x480</code>, save `.xcf` cleanly, and export `/workspace/exports/uv_varnish_proof.png`.</p>
  <p>UV Registry Code: <strong style="color:#4ade80">__UV_CODE__</strong></p>
</div>
<div class="box">
  <h3>42kV X-Radiography Panel Protocol</h3>
  <p>In GIMP (`panel_xray_underdrawing.xcf`), hide/remove layer <code>Cradle_Artifact_Red</code> so the emerald X-ray plate is exposed, resize/crop canvas to <code>600x450</code>, save `.xcf` cleanly, and export `/workspace/exports/xray_underdrawing_clean.png`.</p>
  <p>X-Ray Registry Code: <strong style="color:#38bdf8">__XR_CODE__</strong></p>
</div>
</body></html>""".replace("__UV_CODE__", UV_REG_CODE).replace("__XR_CODE__", XRAY_REG_CODE)


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — UV-Fluorescence Varnish Master & FTIR Pigment Spectroscopy (`uv_varnish_conservator`)",
        "",
        "## Objective",
        f"Process `{b}/workspace/imaging/panel_uv_fluorescence.xcf{b}` in the open **GIMP 2.10** session per `http://127.0.0.1:{PORTAL_PORT}/registry` (exporting `{b}/workspace/exports/uv_varnish_proof.png{b}` and keeping GIMP saved), analyze `{b}/workspace/spectra/ftir_pigment_spectra.sqlite{b}` per `{b}/workspace/docs/SOP_UV_FTIR.pdf{b}`, and write `{b}/workspace/uv_conservation_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — X-Radiography Panel Master & Baltic Oak Dendrochronology (`xray_craquelure_analyst`)",
        "",
        "## Objective",
        f"Process `{b}/workspace/imaging/panel_xray_underdrawing.xcf{b}` in the open **GIMP 2.10** session per `http://127.0.0.1:{PORTAL_PORT}/registry` (exporting `{b}/workspace/exports/xray_underdrawing_clean.png{b}` and keeping GIMP saved), analyze `{b}/workspace/dendro/dendro_ring_widths.sqlite{b}` per `{b}/workspace/docs/SOP_XRay_Dendro.pdf{b}`, and write `{b}/workspace/xray_dendro_audit.json{b}`.",
    ])
    return {"uv_varnish_conservator": ta, "xray_craquelure_analyst": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["uv_varnish_conservator"]
    ws_b = workspace_map["xray_craquelure_analyst"]
    for d in (ws_a / "imaging", ws_a / "exports", ws_a / "spectra", ws_a / "docs", ws_b / "imaging", ws_b / "exports", ws_b / "dendro", ws_b / "docs"):
        d.mkdir(parents=True, exist_ok=True)

    _build_xcf_via_gimp(ws_a / "imaging/panel_uv_fluorescence.xcf", 800, 600, (28, 88, 195), "Calibration_Magenta_Veil", (215, 25, 185))
    _build_xcf_via_gimp(ws_b / "imaging/panel_xray_underdrawing.xcf", 800, 600, (24, 168, 92), "Cradle_Artifact_Red", (210, 32, 32))

    with sqlite3.connect(str(ws_a / "spectra/ftir_pigment_spectra.sqlite")) as conn:
        conn.execute("CREATE TABLE atr_spots (spot_id INTEGER PRIMARY KEY, pigment_class TEXT, wavenumber_cm1 REAL, raw_absorbance REAL, later_overpaint_flag INTEGER, scan_quality TEXT)")
        for r in _generate_ftir_rows():
            conn.execute("INSERT INTO atr_spots VALUES (?,?,?,?,?,?)", (r["spot_id"], r["pigment_class"], r["wavenumber_cm1"], r["raw_absorbance"], r["later_overpaint_flag"], r["scan_quality"]))
        conn.execute("CREATE TABLE substrate_blank_baseline (medium TEXT PRIMARY KEY, blank_absorbance REAL)")
        conn.execute("INSERT INTO substrate_blank_baseline VALUES ('AGED_RABBIT_SKIN_GLUE_GROUND', 0.0480)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_UV_FTIR.pdf", "SOP-CONS-606A: UV Varnish Proofing & ATR-FTIR Pigment Analysis", [
        ("1. GIMP .xcf Proofing & FTIR Net Absorbance", [
            "1.1 Complete the GIMP layer/canvas proofing on /workspace/imaging/panel_uv_fluorescence.xcf -> /workspace/exports/uv_varnish_proof.png.",
            "1.2 Filter /workspace/spectra/ftir_pigment_spectra.sqlite to original non-overpaint CLEAN_ATR spots, subtract any ground-layer blank baseline stored in the database, and report mean net absorbance per pigment class.",
        ]),
        ("2. JSON Schema (/workspace/uv_conservation_audit.json)", [
            "Keys: authentic_spot_count (int), pigment_net_absorbance (dict), dominant_pigment (str), uv_registry_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "dendro/dendro_ring_widths.sqlite")) as conn:
        conn.execute("CREATE TABLE oak_rings (ring_row INTEGER PRIMARY KEY, plank_id TEXT, ring_seq INTEGER, ring_width_microns INTEGER, is_sapwood INTEGER)")
        for r in _generate_dendro_rows():
            conn.execute("INSERT INTO oak_rings VALUES (?,?,?,?,?)", (r["ring_row"], r["plank_id"], r["ring_seq"], r["ring_width_microns"], r["is_sapwood"]))
        conn.execute("CREATE TABLE baltic_oak_dating_rules (outer_heartwood_year_ce INTEGER, min_baltic_sapwood_rings INTEGER, panel_seasoning_years INTEGER)")
        conn.execute("INSERT INTO baltic_oak_dating_rules VALUES (1518, 15, 4)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_XRay_Dendro.pdf", "SOP-CONS-606B: X-Radiography Master & Baltic Oak Panel Dating", [
        ("1. GIMP .xcf Proofing & Terminus Post Quem Dating", [
            "1.1 Complete the GIMP layer/canvas proofing on /workspace/imaging/panel_xray_underdrawing.xcf -> /workspace/exports/xray_underdrawing_clean.png.",
            "1.2 Exclude 19th-century restoration planks in /workspace/dendro/dendro_ring_widths.sqlite, convert ring widths from microns to millimeters, and compute earliest_panel_usage_year_ce using the heartwood anchor, minimum Baltic sapwood ring count, and seasoning allowance in SQLite.",
        ]),
        ("2. JSON Schema (/workspace/xray_dendro_audit.json)", [
            "Keys: original_ring_measurement_count (int), mean_original_ring_width_mm (float, 4 dec), observed_sapwood_rings_per_plank (int), earliest_panel_usage_year_ce (int), xray_registry_code (str).",
        ]),
    ])
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID})

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self.send_response(403); self.end_headers(); return
                raw = b"<html><body><script>location.href='/registry';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"cons_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "cons_sso" not in c or c["cons_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            raw = PORTAL_HTML.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or META["roles"])
    xcfs = []
    if "uv_varnish_conservator" in roles:
        xcfs.append(workspace_map["uv_varnish_conservator"] / "imaging/panel_uv_fluorescence.xcf")
    if "xray_craquelure_analyst" in roles:
        xcfs.append(workspace_map["xray_craquelure_analyst"] / "imaging/panel_xray_underdrawing.xcf")
    launch_gimp_gui_natural(xcfs)
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def _check_png(p: Path, w: int, h: int, dom_idx: int) -> bool:
    from PIL import Image
    if not p.is_file():
        return False
    try:
        with Image.open(p) as im:
            rgb = im.convert("RGB")
            if rgb.size != (w, h):
                return False
            px = rgb.getpixel((w // 2, h // 2))
            return px[dom_idx] > max(px[(dom_idx + 1) % 3], px[(dom_idx + 2) % 3]) + 45
    except Exception:
        return False


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ws_a = workspace_map["uv_varnish_conservator"]
    ws_b = workspace_map["xray_craquelure_analyst"]
    ja = read_json_safe(ws_a / "uv_conservation_audit.json")
    jb = read_json_safe(ws_b / "xray_dendro_audit.json")
    xcf_a = _inspect_xcf(ws_a / "imaging/panel_uv_fluorescence.xcf")
    xcf_b = _inspect_xcf(ws_b / "imaging/panel_xray_underdrawing.xcf")
    titles = inspect_live_x11_window_titles_readonly()
    dirty_uv = any("*panel_uv_fluorescence" in t for t in titles)
    dirty_xr = any("*panel_xray_underdrawing" in t for t in titles)

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    pm = ja.get("pigment_net_absorbance") if isinstance(ja.get("pigment_net_absorbance"), dict) else {}
    exp_pm = UV_ORACLE["pigment_net_absorbance"]

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.07, "Missing uv_conservation_audit.json"),
        ("a_xcf_dim", xcf_a.get("w") == 640 and xcf_a.get("h") == 480, 0.14, "panel_uv_fluorescence.xcf not resized/cropped to 640x480"),
        ("a_png_proof", _check_png(ws_a / "exports/uv_varnish_proof.png", 640, 480, 2), 0.16, "uv_varnish_proof.png missing, wrong size, or magenta veil still visible"),
        ("a_gimp_clean", bool(ja) and not dirty_uv, 0.10, "Open GIMP window holds unsaved *panel_uv_fluorescence buffer"),
        ("a_spot_cnt", ja.get("authentic_spot_count") == UV_ORACLE["authentic_spot_count"], 0.11, "authentic_spot_count mismatch"),
        ("a_dom_pg", ja.get("dominant_pigment") == "LAPIS_ULTRAMARINE" and ja.get("uv_registry_code") == UV_REG_CODE, 0.12, "dominant_pigment or uv_registry_code mismatch"),
        ("a_pg_coarse", sum(1 for k, v in exp_pm.items() if abs(_f(pm.get(k)) - v) <= 0.06) == 4, 0.08, "pigment_net_absorbance coarse off"),
        ("a_fine_blank_sub", sum(1 for k, v in exp_pm.items() if abs(_f(pm.get(k)) - v) <= 0.001) == 4, 0.22, "Missed substrate_blank_baseline 0.0480 subtraction in SQLite"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.07, "Missing xray_dendro_audit.json"),
        ("b_xcf_dim", xcf_b.get("w") == 600 and xcf_b.get("h") == 450, 0.14, "panel_xray_underdrawing.xcf not resized/cropped to 600x450"),
        ("b_png_proof", _check_png(ws_b / "exports/xray_underdrawing_clean.png", 600, 450, 1), 0.16, "xray_underdrawing_clean.png missing, wrong size, or red cradle artifact visible"),
        ("b_gimp_clean", bool(jb) and not dirty_xr, 0.10, "Open GIMP window holds unsaved *panel_xray_underdrawing buffer"),
        ("b_ring_cnt", jb.get("original_ring_measurement_count") == XRAY_ORACLE["original_ring_measurement_count"], 0.11, "Failed to exclude PLANK_C_RESTORED_1890"),
        ("b_width_mm", abs(_f(jb.get("mean_original_ring_width_mm")) - XRAY_ORACLE["mean_original_ring_width_mm"]) <= 0.002, 0.10, "mean_original_ring_width_mm off (check microns->mm)"),
        ("b_code", jb.get("xray_registry_code") == XRAY_REG_CODE and jb.get("observed_sapwood_rings_per_plank") == 8, 0.10, "xray_registry_code or sapwood count mismatch"),
        ("b_fine_tpq_1537", jb.get("earliest_panel_usage_year_ce") == XRAY_ORACLE["earliest_panel_usage_year_ce"], 0.22, f"earliest_panel_usage_year_ce != {XRAY_ORACLE['earliest_panel_usage_year_ce']} (check min 15 Baltic sapwood rings + 4yr seasoning)"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    if role == "uv_varnish_conservator":
        xp = ws / "imaging/panel_uv_fluorescence.xcf"
        pp = ws / "exports/uv_varnish_proof.png"
        scm = (
            f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xp}" "{xp}"))) '
            f'(top (aref (cadr (gimp-image-get-layers img)) 0)) '
            f'(bg (aref (cadr (gimp-image-get-layers img)) 1))) '
            f'(gimp-item-set-visible top FALSE) (gimp-image-remove-layer img top) '
            f'(gimp-image-scale img 640 480) '
            f'(gimp-xcf-save 0 img bg "{xp}" "{xp}") '
            f'(file-png-save-defaults RUN-NONINTERACTIVE img bg "{pp}" "{pp}") '
            f'(gimp-quit 0))'
        )
        subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=45)
        write_json(ws / "uv_conservation_audit.json", UV_ORACLE)
    else:
        xp = ws / "imaging/panel_xray_underdrawing.xcf"
        pp = ws / "exports/xray_underdrawing_clean.png"
        scm = (
            f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xp}" "{xp}"))) '
            f'(top (aref (cadr (gimp-image-get-layers img)) 0)) '
            f'(bg (aref (cadr (gimp-image-get-layers img)) 1))) '
            f'(gimp-item-set-visible top FALSE) (gimp-image-remove-layer img top) '
            f'(gimp-image-scale img 600 450) '
            f'(gimp-xcf-save 0 img bg "{xp}" "{xp}") '
            f'(file-png-save-defaults RUN-NONINTERACTIVE img bg "{pp}" "{pp}") '
            f'(gimp-quit 0))'
        )
        subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=45)
        write_json(ws / "xray_dendro_audit.json", XRAY_ORACLE)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    from PIL import Image
    del state_dir
    solve_role("uv_varnish_conservator", workspace_map, port)
    solve_role("xray_craquelure_analyst", workspace_map, port)
    # Singleton GIMP tab focus race: Role B accidentally scales/exports 600x450 onto Role A's active tab!
    Image.new("RGB", (600, 450), (24, 168, 92)).save(workspace_map["uv_varnish_conservator"] / "exports/uv_varnish_proof.png")
    _build_xcf_via_gimp(workspace_map["uv_varnish_conservator"] / "imaging/panel_uv_fluorescence.xcf", 600, 450, (24, 168, 92), "Clobbered", (215, 25, 185))

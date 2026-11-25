"""NF2-18: Singleton GIMP 2.10 Shared `.xcf` Prepress Master + Open Writer — GMP Blister GS1 DataMatrix vs. Braille Ink-TAC Cap."""
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
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    inspect_live_x11_window_titles_readonly,
    launch_chromium_natural,
    launch_gimp_gui_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_odt_plain_text,
    sync_uno_writer_text,
    write_json,
    write_multipage_sop_pdf,
    write_simple_odt,
)

TASK_ID = "NF2-18"
PORTAL_PORT = 19618

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Singleton `GIMP 2.10` Shared `.xcf` Prepress Master & Open Writer: GS1-128 DataMatrix vs. Marburg Braille Ink-TAC Cap",
    "domain": "GMP Pharmaceutical Packaging Prepress (`GIMP 2.10` `.xcf` + `LibreOffice Writer` + GS1 Serialization)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("gs1_datamatrix_eng", "braille_artwork_lead"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

GS1_QA_CODE = make_canary_code("GS1-GTIN14", "fmd-eu-2016-161")
BRAILLE_QA_CODE = make_canary_code("EN15823", "marburg-medium-dot")
GRAVURE_TAC_CAP_PCT = 275.0  # GS1 UV+Black floor 118.0 + Braille White+Cyan floor 142.0 = 260.0 <= 275.0; pref 136.0 + 158.0 = 294.0 > 275.0!
GS1_TAC_FLOOR = 118.0
BRAILLE_TAC_FLOOR = 142.0


def _gs1_mod10_check_digit(d13: str) -> int:
    # GS1 GTIN-14: positions from right (excluding check digit) alternate weights 3, 1, 3, 1... (for 13 digits, index 0 has weight 3!)
    tot = sum(int(ch) * (3 if idx % 2 == 0 else 1) for idx, ch in enumerate(d13))
    return (10 - (tot % 10)) % 10


def _generate_gtin_rows() -> list[dict[str, Any]]:
    rows = []
    for i in range(1, 301):
        base13 = f"034009{3000000 + i:07d}"
        good_cd = _gs1_mod10_check_digit(base13)
        cd = (good_cd + 1) % 10 if (i % 19 == 0) else good_cd
        # Secondary table market_withdrawn_prefixes withdraws prefix '034009300015' (i=150..159)!
        rows.append({"lot_seq": i, "gtin14": base13 + str(cd), "pack_status": "ACTIVE" if i % 29 != 0 else "RECALLED_SAMPLE"})
    return rows


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — GS1 GTIN-14 Serialization Audit & Shared `.xcf` Prepress Master (`gs1_datamatrix_eng`)",
        "",
        "## Objective",
        f"Remove `Registration_Magenta_Crosshair` in `{b}/workspace/shared_docs/gmp_blister_foil.xcf{b}` (open in **GIMP 2.10**), export `{b}/workspace/proofs/gs1_foil_proof.png{b}`, commit your `gs1_uv_tac_pct` in `{b}/workspace/shared_docs/gravure_ink_budget.json{b}` and sign `{b}/workspace/shared_docs/Artwork_Approval_Record.odt{b}` (open in Writer) per `http://127.0.0.1:{PORTAL_PORT}/gmp-art` and `{b}/workspace/docs/SOP_GS1_Foil.pdf{b}`, audit `{b}/workspace/gtin/serialization_300.sqlite{b}`, and write `{b}/workspace/gs1_serialization_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — EN 15823 Marburg Medium Braille Pitch & Shared `.xcf` Prepress (`braille_artwork_lead`)",
        "",
        "## Objective",
        f"Scale `{b}/workspace/shared_docs/gmp_blister_foil.xcf{b}` (open in **GIMP 2.10**) to `720x480`, export `{b}/workspace/proofs/braille_foil_proof.png{b}`, commit your `braille_white_tac_pct` in `{b}/workspace/shared_docs/gravure_ink_budget.json{b}` and sign `{b}/workspace/shared_docs/Artwork_Approval_Record.odt{b}` (open in Writer) per `http://127.0.0.1:{PORTAL_PORT}/gmp-art` and `{b}/workspace/docs/SOP_Braille_15823.pdf{b}`, audit `{b}/workspace/braille/carton_panels.sqlite{b}`, and write `{b}/workspace/braille_prepress_audit.json{b}`.",
    ])
    return {"gs1_datamatrix_eng": ta, "braille_artwork_lead": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["gs1_datamatrix_eng"]
    ws_b = workspace_map["braille_artwork_lead"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "gtin", ws_a / "proofs", ws_a / "docs", ws_b / "braille", ws_b / "proofs", ws_b / "docs", hub):
        d.mkdir(parents=True, exist_ok=True)

    xp = hub / "gmp_blister_foil.xcf"
    scm = (
        f'(let* ((img (car (gimp-image-new 900 600 RGB))) '
        f'(bg (car (gimp-layer-new img 900 600 RGB-IMAGE "Foil_Silver_Base" 100 LAYER-MODE-NORMAL))) '
        f'(ov (car (gimp-layer-new img 900 600 RGBA-IMAGE "Registration_Magenta_Crosshair" 100 LAYER-MODE-NORMAL)))) '
        f'(gimp-image-insert-layer img bg 0 0) (gimp-context-set-foreground \x27(35 125 205)) (gimp-drawable-fill bg FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img ov 0 0) (gimp-context-set-foreground \x27(220 25 190)) (gimp-drawable-fill ov FILL-FOREGROUND) '
        f'(gimp-xcf-save 0 img ov "{xp}" "{xp}") (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=45)

    write_json(hub / "gravure_ink_budget.json", {
        "press_id": "BOBST-GRAVURE-03", "max_total_tac_pct": GRAVURE_TAC_CAP_PCT,
        "gs1_uv_tac_pct": 0.0, "gs1_status": "PENDING",
        "braille_white_tac_pct": 0.0, "braille_status": "PENDING",
    })
    write_simple_odt(hub / "Artwork_Approval_Record.odt", "GMP Packaging Release Record", [
        ("LOT", "[GMP-FOIL-2026] Cold-Form Aluminum Blister Release"),
        ("STATUS", "Awaiting GS1 Serialization and EN 15823 Braille approvals."),
    ])

    with sqlite3.connect(str(ws_a / "gtin/serialization_300.sqlite")) as conn:
        conn.execute("CREATE TABLE gtin_records (lot_seq INTEGER PRIMARY KEY, gtin14 TEXT, pack_status TEXT)")
        for r in _generate_gtin_rows():
            conn.execute("INSERT INTO gtin_records VALUES (?,?,?)", (r["lot_seq"], r["gtin14"], r["pack_status"]))
        conn.execute("CREATE TABLE mah_withdrawn_prefixes (gtin_prefix12 TEXT PRIMARY KEY, reason TEXT)")
        conn.execute("INSERT INTO mah_withdrawn_prefixes VALUES ('03400930015', 'MA_SUSPENDED_DO_NOT_SERIALIZE')")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_GS1_Foil.pdf", "SOP-PKG-1818A: GS1 Modulo-10 Check Digit & Blister Foil UV TAC", [
        ("1. GIMP Foil Master & GS1 Validation", [
            f"1.1 In /workspace/shared_docs/gmp_blister_foil.xcf, remove/hide Registration_Magenta_Crosshair (preserving any 720x480 canvas scaling) and export /workspace/proofs/gs1_foil_proof.png.",
            f"1.2 Commit gs1_uv_tac_pct (>={GS1_TAC_FLOOR}%, preferred 129.0%, within {GRAVURE_TAC_CAP_PCT}% coupled TAC cap) in gravure_ink_budget.json (gs1_status='COMMITTED') and sign Artwork_Approval_Record.odt with gs1_qa_code from /gmp-art.",
            "1.3 Count ACTIVE GTIN-14 records in serialization_300.sqlite that have a valid GS1 Modulo-10 check digit AND do not match withdrawn MAH prefixes in SQLite.",
        ]),
        ("2. JSON Schema (/workspace/gs1_serialization_audit.json)", [
            "Keys: valid_release_gtin_count (int), check_digit_failure_count (int), gs1_uv_tac_committed_pct (float, 1 dec), gs1_qa_code (str).",
        ]),
    ])

    # Role B: Marburg Medium Braille cell pitch: 6.0 mm inter-cell horizontal, 10.0 mm inter-line vertical, plus 3.5 mm blister heat-seal flange keep-out per edge (2*3.5 = 7.0 mm subtracted from panel width & height in SQLite)!
    with sqlite3.connect(str(ws_b / "braille/carton_panels.sqlite")) as conn:
        conn.execute("CREATE TABLE foil_panels (panel_id TEXT PRIMARY KEY, raw_width_mm REAL, raw_height_mm REAL, market_active INTEGER)")
        for k in range(1, 25):
            conn.execute("INSERT INTO foil_panels VALUES (?,?,?,?)", (f"PNL-{k:02d}", 98.0 + (k % 5) * 6.0, 52.0 + (k % 3) * 10.0, 1 if k % 8 != 0 else 0))
        conn.execute("CREATE TABLE marburg_medium_spec (cell_pitch_x_mm REAL, line_pitch_y_mm REAL, heat_seal_flange_margin_each_side_mm REAL)")
        conn.execute("INSERT INTO marburg_medium_spec VALUES (6.0, 10.0, 3.5)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_Braille_15823.pdf", "SOP-PKG-1818B: EN 15823 Marburg Medium Braille Capacity & Foil TAC", [
        ("1. GIMP Foil Scaling & Braille Cell Capacity", [
            f"1.1 Scale /workspace/shared_docs/gmp_blister_foil.xcf to 720x480 (preserving removal of Registration_Magenta_Crosshair) and export /workspace/proofs/braille_foil_proof.png.",
            f"1.2 Commit braille_white_tac_pct (>={BRAILLE_TAC_FLOOR}%, preferred 153.0%, within {GRAVURE_TAC_CAP_PCT}% coupled TAC cap) in gravure_ink_budget.json (braille_status='COMMITTED') and sign Artwork_Approval_Record.odt with braille_qa_code from /gmp-art.",
            "1.3 Sum total integer Marburg Medium Braille cells floor(usable_w / 6.0) * floor(usable_h / 10.0) across market_active=1 panels in carton_panels.sqlite after deducting heat-seal flange margins on all 4 sides.",
        ]),
        ("2. JSON Schema (/workspace/braille_prepress_audit.json)", [
            "Keys: active_panel_count (int), total_marburg_cell_capacity (int), braille_white_tac_committed_pct (float, 1 dec), braille_qa_code (str).",
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
    html = (
        "<!doctype html><html><body style='background:#0f172a;color:#f8fafc;font-family:monospace;margin:20px'>"
        f"<h2>GMPGravure Blister Foil Prepress Control</h2>"
        f"<p>Dryer Total Ink Coverage Cap: <code>gs1_uv_tac_pct + braille_white_tac_pct &lt;= {GRAVURE_TAC_CAP_PCT:.1f}%</code></p>"
        f"<p>GS1 QA Sign Code: <strong style='color:#4ade80'>{GS1_QA_CODE}</strong> | EN 15823 Braille Code: <strong style='color:#38bdf8'>{BRAILLE_QA_CODE}</strong></p>"
        "</body></html>"
    ).encode("utf-8")

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
                raw = b"<html><body><script>location.href='/gmp-art';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"gmp_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "gmp_sso" not in c or c["gmp_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    launch_gimp_gui_natural([hub / "gmp_blister_foil.xcf"])
    launch_libreoffice_uno_natural([hub / "Artwork_Approval_Record.odt"])
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def _gtin_oracles() -> tuple[int, int]:
    active = [r for r in _generate_gtin_rows() if r["pack_status"] == "ACTIVE"]
    bad_cd = sum(1 for r in active if int(r["gtin14"][-1]) != _gs1_mod10_check_digit(r["gtin14"][:13]))
    valid_rel = sum(
        1 for r in active
        if int(r["gtin14"][-1]) == _gs1_mod10_check_digit(r["gtin14"][:13])
        and not r["gtin14"].startswith("03400930015")
    )
    return valid_rel, bad_cd


def _braille_oracles() -> tuple[int, int]:
    cnt = 0
    cells = 0
    for k in range(1, 25):
        if k % 8 == 0:
            continue
        cnt += 1
        uw = (98.0 + (k % 5) * 6.0) - 7.0
        uh = (52.0 + (k % 3) * 10.0) - 7.0
        cells += int(uw // 6.0) * int(uh // 10.0)
    return cnt, cells


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    from PIL import Image
    act = set(active_roles or META["roles"])
    has_a, has_b = ("gs1_datamatrix_eng" in act), ("braille_artwork_lead" in act)
    ws_a = workspace_map["gs1_datamatrix_eng"]
    ws_b = workspace_map["braille_artwork_lead"]
    hub = workspace_map["__shared_hub__"]
    bud = read_json_safe(hub / "gravure_ink_budget.json")
    odt_txt = read_odt_plain_text(hub / "Artwork_Approval_Record.odt")
    uno_st = inspect_live_uno_documents_readonly()
    titles = inspect_live_x11_window_titles_readonly()
    ja = read_json_safe(ws_a / "gs1_serialization_audit.json")
    jb = read_json_safe(ws_b / "braille_prepress_audit.json")

    gt_rel, gt_bad = _gtin_oracles()
    br_cnt, br_cells = _braille_oracles()
    g_tac = float(bud.get("gs1_uv_tac_pct") or -1.0)
    b_tac = float(bud.get("braille_white_tac_pct") or -1.0)

    png_a_ok = False
    if (ws_a / "proofs/gs1_foil_proof.png").is_file():
        with Image.open(ws_a / "proofs/gs1_foil_proof.png") as im:
            r_c, _g, b_c = im.convert("RGB").getpixel((100, 100))
            png_a_ok = b_c > r_c + 40

    png_b_ok = False
    if (ws_b / "proofs/braille_foil_proof.png").is_file():
        with Image.open(ws_b / "proofs/braille_foil_proof.png") as im:
            png_b_ok = im.size == (720, 480)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing gs1_serialization_audit.json"),
        ("a_png", png_a_ok, 0.18, "gs1_foil_proof.png missing or magenta crosshair still visible"),
        ("a_tac_odt", g_tac >= GS1_TAC_FLOOR and bud.get("gs1_status") == "COMMITTED" and GS1_QA_CODE in odt_txt and ja.get("gs1_qa_code") == GS1_QA_CODE, 0.22, "GS1 TAC or Writer signoff missing"),
        ("a_bad_cd", ja.get("check_digit_failure_count") == gt_bad, 0.18, "GS1 Mod-10 check_digit_failure_count mismatch"),
        ("a_fine_withdrawn_prefix", ja.get("valid_release_gtin_count") == gt_rel, 0.34, f"valid_release_gtin_count != {gt_rel} (missed mah_withdrawn_prefixes '03400930015')"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing braille_prepress_audit.json"),
        ("b_png_720", png_b_ok, 0.18, "braille_foil_proof.png missing or not 720x480"),
        ("b_tac_odt", b_tac >= BRAILLE_TAC_FLOOR and bud.get("braille_status") == "COMMITTED" and BRAILLE_QA_CODE in odt_txt and jb.get("braille_qa_code") == BRAILLE_QA_CODE, 0.22, "Braille TAC or Writer signoff missing"),
        ("b_cnt", jb.get("active_panel_count") == br_cnt, 0.18, "active_panel_count != 21"),
        ("b_fine_flange_cells", jb.get("total_marburg_cell_capacity") == br_cells, 0.34, f"total_marburg_cell_capacity != {br_cells} (missed 2*3.5mm heat-seal flange deduction)"),
    ]

    eff_g = g_tac if (has_a and g_tac > 0) else (GS1_TAC_FLOOR if not has_a else 999.0)
    eff_b = b_tac if (has_b and b_tac > 0) else (BRAILLE_TAC_FLOOR if not has_b else 999.0)
    fl_ok = ((not has_a) or g_tac >= GS1_TAC_FLOOR) and ((not has_b) or b_tac >= BRAILLE_TAC_FLOOR)
    uno_ok = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Artwork_Approval_Record.odt" in u_url:
            uno_ok = not u_doc.get("is_modified")
    gimp_ok = not any("*gmp_blister_foil" in t for t in titles)
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_tac_275_cap", fl_ok and (eff_g + eff_b <= GRAVURE_TAC_CAP_PCT), 0.12, f"Coupled gravure TAC {eff_g + eff_b:.1f}% exceeds {GRAVURE_TAC_CAP_PCT:.1f}%!"),
        ("j_gui_sync", act_done and uno_ok and gimp_ok, 0.10, "Open Writer or GIMP holds unsaved dirty state"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    xp = hub / "gmp_blister_foil.xcf"
    bp = hub / "gravure_ink_budget.json"
    odt_p = hub / "Artwork_Approval_Record.odt"

    with file_atomic_lock("nf218_shared"):
        bud = read_json_safe(bp)
        if role == "gs1_datamatrix_eng":
            b_cur = float(bud.get("braille_white_tac_pct") or 0.0) if bud.get("braille_status") == "COMMITTED" else 0.0
            val = round(max(GS1_TAC_FLOOR, min(124.0, GRAVURE_TAC_CAP_PCT - b_cur - 2.0)) if b_cur > 0 else 124.0, 1)
            bud["gs1_uv_tac_pct"] = val; bud["gs1_status"] = "COMMITTED"
            pp = ws / "proofs/gs1_foil_proof.png"
            scm = (
                f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xp}" "{xp}"))) '
                f'(n (car (gimp-image-get-layers img))) '
                f'(bg (aref (cadr (gimp-image-get-layers img)) (- n 1)))) '
                f'(if (> n 1) (gimp-image-remove-layer img (aref (cadr (gimp-image-get-layers img)) 0))) '
                f'(gimp-xcf-save 0 img bg "{xp}" "{xp}") '
                f'(file-png-save-defaults RUN-NONINTERACTIVE img bg "{pp}" "{pp}") (gimp-quit 0))'
            )
            subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=45)
            sign = GS1_QA_CODE
        else:
            g_cur = float(bud.get("gs1_uv_tac_pct") or 0.0) if bud.get("gs1_status") == "COMMITTED" else 0.0
            val = round(max(BRAILLE_TAC_FLOOR, min(146.0, GRAVURE_TAC_CAP_PCT - g_cur - 2.0)) if g_cur > 0 else 146.0, 1)
            bud["braille_white_tac_pct"] = val; bud["braille_status"] = "COMMITTED"
            pp = ws / "proofs/braille_foil_proof.png"
            scm = (
                f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xp}" "{xp}"))) '
                f'(n (car (gimp-image-get-layers img))) '
                f'(act (aref (cadr (gimp-image-get-layers img)) 0))) '
                f'(gimp-image-scale img 720 480) '
                f'(gimp-xcf-save 0 img act "{xp}" "{xp}") '
                f'(file-png-save-defaults RUN-NONINTERACTIVE img act "{pp}" "{pp}") (gimp-quit 0))'
            )
            subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=45)
            sign = BRAILLE_QA_CODE
        write_json(bp, bud)
        cur_t = read_odt_plain_text(odt_p)
        lines = [ln for ln in cur_t.splitlines() if ln.strip() and sign not in ln]
        lines.append(f"[SIGN] {role}: {sign}")
        sync_uno_writer_text(odt_p, "\n".join(lines))

    if role == "gs1_datamatrix_eng":
        gt_rel, gt_bad = _gtin_oracles()
        write_json(ws / "gs1_serialization_audit.json", {
            "valid_release_gtin_count": gt_rel, "check_digit_failure_count": gt_bad,
            "gs1_uv_tac_committed_pct": val, "gs1_qa_code": GS1_QA_CODE,
        })
    else:
        br_cnt, br_cells = _braille_oracles()
        write_json(ws / "braille_prepress_audit.json", {
            "active_panel_count": br_cnt, "total_marburg_cell_capacity": br_cells,
            "braille_white_tac_committed_pct": val, "braille_qa_code": BRAILLE_QA_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("gs1_datamatrix_eng", workspace_map, port)
    solve_role("braille_artwork_lead", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    write_json(hub / "gravure_ink_budget.json", {"gs1_uv_tac_pct": 136.0, "gs1_status": "COMMITTED", "braille_white_tac_pct": 158.0, "braille_status": "COMMITTED"})

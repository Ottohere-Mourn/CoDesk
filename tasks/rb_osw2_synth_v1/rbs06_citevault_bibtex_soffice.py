"""RBS-06: Deep OSW2-P8/P9 + P1 Twin — CiteVault SQLite, BibTeX Repair & Single soffice.bin Meta-Analysis.

Grounded in OSWorld-V2 Empirical Laws (OSW2-P8/P9 Zotero/BibTeX + OSW2-P1/P2 Single soffice.bin):
  - LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN: Single running `soffice.bin` holds both
    `Survey_Manuscript.odt` (Writer, unsaved SURVEY-DESK-806) and `Evidence_Synthesis.xlsx`
    (Calc, unsaved META-CALC-806) alongside shared `citevault.sqlite`.
  - LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP: Shared HttpOnly Preprint Registry (`:19306`),
    `~/Downloads/registry_feed.csv` overwrite, and single-slot X11 clipboard seals.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.rb_osw2_synth_v1.common import (
    advisory_lock,
    build_grade_payload,
    convert_doc_to_pdf_isolated,
    extract_pdf_text,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    read_json_safe,
    read_odt_plain_text,
    reload_open_libreoffice_docs,
    set_x11_clipboard,
    write_json,
    write_simple_odt,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "RBS-06"
PORTAL_PORT = 19306
WRITER_DESK_TAG = "SURVEY-DESK-806"
CALC_DESK_TAG = "META-CALC-806"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "CiteVault SQLite & BibTeX Dedup + Single soffice.bin (Writer + Calc) Meta-Analysis",
    "domain": "Academic Systematic Review, BibTeX Curation & Biostatistics Meta-Analysis",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("bib_manuscript_editor", "evidence_quant_analyst"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (
        ("/workspace/meta_review/Evidence_Synthesis.xlsx", CALC_DESK_TAG, "calc"),
        ("/workspace/meta_review/Survey_Manuscript.odt", WRITER_DESK_TAG, "writer"),
    ),
    "conc_role_timeout_s": 1680,
    "iso_role_timeout_s": 1680,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "deep_coupled_workbench",
        "total_subchecks": 32,
        "cli_bypass_resistance": 0.94,
        "role_a": {
            "slug": "bib_manuscript_editor",
            "est_role_seconds": 540.0,
            "traits": [
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "twin_named_modals",
            ],
        },
        "role_b": {
            "slug": "evidence_quant_analyst",
            "est_role_seconds": 560.0,
            "traits": [
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "twin_named_modals",
            ],
        },
    },
}

# 20 studies: (st_id, bib_key, first_author, year, doi, registry_status, log_rr, se)
STUDIES_TRUTH: list[tuple[str, str, str, int, str, str, float, float]] = [
    ("ST-01", "chen2023adaptive",   "Chen",      2023, "10.1000/jbi.2023.01", "ELIGIBLE_PRIMARY",       -0.24, 0.10),
    ("ST-02", "patel2023cohort",    "Patel",     2023, "10.1000/jbi.2023.02", "ELIGIBLE_PRIMARY",       -0.18, 0.12),
    ("ST-03", "muller2024trial",    "Muller",    2024, "10.1000/jbi.2024.03", "ELIGIBLE_PRIMARY",       -0.31, 0.08),
    ("ST-04", "vega2022preprint",   "Vega",      2022, "10.1000/pre.2022.04", "RETRACTED_DATA_ANOMALY",  0.65, 0.07),
    ("ST-05", "sato2024multicenter","Sato",      2024, "10.1000/jbi.2024.05", "ELIGIBLE_PRIMARY",       -0.22, 0.11),
    ("ST-06", "okafor2023pragmatic","Okafor",    2023, "10.1000/jbi.2023.06", "ELIGIBLE_PRIMARY",       -0.27, 0.09),
    ("ST-07", "lindqvist2024nordic","Lindqvist", 2024, "10.1000/jbi.2024.07", "ELIGIBLE_PRIMARY",       -0.19, 0.14),
    ("ST-08", "kim2025phase3",      "Kim",       2025, "10.1000/jbi.2025.08", "ELIGIBLE_PRIMARY",       -0.35, 0.08),
    ("ST-09", "rossi2023duplicate", "Rossi",     2023, "10.1000/pre.2023.09", "SUPERSEDED_DUPLICATE",    0.52, 0.06),
    ("ST-10", "silva2024cluster",   "Silva",     2024, "10.1000/jbi.2024.10", "ELIGIBLE_PRIMARY",       -0.21, 0.10),
    ("ST-11", "novak2025registry",  "Novak",     2025, "10.1000/jbi.2025.11", "ELIGIBLE_PRIMARY",       -0.29, 0.09),
    ("ST-12", "haddad2024icu",      "Haddad",    2024, "10.1000/jbi.2024.12", "ELIGIBLE_PRIMARY",       -0.16, 0.15),
    ("ST-13", "park2025stepped",    "Park",      2025, "10.1000/jbi.2025.13", "ELIGIBLE_PRIMARY",       -0.28, 0.10),
    ("ST-14", "barton2022retracted","Barton",    2022, "10.1000/pre.2022.14", "RETRACTED_CONSENT",       0.71, 0.05),
    ("ST-15", "gomez2024onc",       "Gomez",     2024, "10.1000/jbi.2024.15", "ELIGIBLE_PRIMARY",       -0.25, 0.11),
    ("ST-16", "keller2025acute",    "Keller",    2025, "10.1000/jbi.2025.16", "ELIGIBLE_PRIMARY",       -0.33, 0.09),
    ("ST-17", "mensah2024ward",     "Mensah",    2024, "10.1000/jbi.2024.17", "ELIGIBLE_PRIMARY",       -0.20, 0.13),
    ("ST-18", "dubois2023interim",  "Dubois",    2023, "10.1000/pre.2023.18", "SUPERSEDED_INTERIM",      0.48, 0.06),
    ("ST-19", "tanaka2025elderly",  "Tanaka",    2025, "10.1000/jbi.2025.19", "ELIGIBLE_PRIMARY",       -0.26, 0.10),
    ("ST-20", "alvarez2025global",  "Alvarez",   2025, "10.1000/jbi.2025.20", "ELIGIBLE_PRIMARY",       -0.30, 0.08),
]

RETRACTION_SEAL = make_opaque_seal("rbs06", "RETRACTION_WATCH:BIB_CURATED")
BIOSTAT_SEAL = make_opaque_seal("rbs06", "COHORT_EFFECT_SIZES:IVW_POOLED")

ELIGIBLE_STUDIES = [s for s in STUDIES_TRUTH if s[5] == "ELIGIBLE_PRIMARY"]
EXCLUDED_IDS = {s[0] for s in STUDIES_TRUTH if s[5] != "ELIGIBLE_PRIMARY"}
TRUE_SUM_W = round(sum(1.0 / (s[7] ** 2) for s in ELIGIBLE_STUDIES), 4)
TRUE_SUM_WY = round(sum((1.0 / (s[7] ** 2)) * s[6] for s in ELIGIBLE_STUDIES), 4)
TRUE_POOLED_LOGRR = round(TRUE_SUM_WY / TRUE_SUM_W, 4)


def _make_weights_sheet(eligible_only: bool, desk_tag: str = "") -> list[list]:
    rows: list[list] = [["Study_ID", "InvVar_Weight_W", desk_tag, "Weighted_Effect_WY"]]
    src = ELIGIBLE_STUDIES if eligible_only else STUDIES_TRUTH[:5]
    for st_id, _bk, _au, _yr, _doi, _st, lrr, se in src:
        w = round(1.0 / (se * se), 4)
        wy = round(w * lrr, 4)
        rows.append([st_id, w, "INCLUDED" if eligible_only else "UNVERIFIED", wy])
    return rows


def _make_summary_sheet(inc_cnt: int, sum_w: float, sum_wy: float, biostat_seal: str, bib_seal: str) -> list[list]:
    pooled = round(sum_wy / max(1e-6, sum_w), 4)
    return [
        ["Metric", "Value", "Notes"],
        ["Included_Eligible_Studies", inc_cnt, "MUST_EQUAL_16"],
        ["Total_InvVar_Weight", round(sum_w, 4), "SUM_W"],
        ["Total_Weighted_LogRR", round(sum_wy, 4), "SUM_WY"],
        ["Pooled_FixedEffect_LogRR", ("=B4/B3", pooled), "FORMULA_REQUIRED"],
        ["Biostat_Synthesis_Seal", biostat_seal, ""],
        ["Editorial_Retraction_Seal", bib_seal, ""],
    ]


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Systematic Review Curation & BibTeX Remediation Work Order — {b}bib_manuscript_editor{b}",
        "",
        "## Scope & Deliverables",
        f"Curate the 20-study literature database in {b}/workspace/meta_review/citevault.sqlite{b}, clean the BibTeX bibliography, and finalize {b}Survey_Manuscript.odt{b}.",
        f"Both {b}/workspace/meta_review/Survey_Manuscript.odt{b} (with an active session tag {b}SURVEY-DESK-806{b}) and {b}Evidence_Synthesis.xlsx{b} (with an active session tag in {b}Study_Weights!C1{b}) are open in LibreOffice alongside the Preprint & Retraction Registry at {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Under {b}VIEW = RETRACTION_WATCH{b} on {b}http://127.0.0.1:{PORTAL_PORT}/{b}, export {b}/home/user/Downloads/registry_feed.csv{b} and copy the Editorial Retraction Seal to the clipboard.",
        f"2. Update {b}citevault.sqlite{b} table {b}studies{b}: set {b}curation_status = 'INCLUDED_ELIGIBLE'{b} for all `ELIGIBLE_PRIMARY` studies (`16` studies) and {b}'EXCLUDED_RETRACTED'{b} for all retracted/superseded studies (`4` studies).",
        f"3. Write {b}/workspace/meta_review/references_clean.bib{b} containing `@article{{<bib_key>, ...}}` entries (with `author`, `year`, and `doi` fields) for **only** the `16` eligible primary studies.",
        f"4. Record the Editorial Retraction Seal in {b}Evidence_Synthesis.xlsx{b} cell {b}Pooled_Summary!B7{b} (preserving all other sheets, formulas, and {b}Study_Weights!C1{b}), update {b}Survey_Manuscript.odt{b} so it contains `INCLUDED_STUDIES=16`, `EXCLUDED_RETRACTED=4`, the Editorial Retraction Seal, and the active {b}SURVEY-DESK-806{b} tag, and export {b}/workspace/meta_review/Survey_Manuscript.pdf{b}.",
        "",
    ])

    role_b = "\n".join([
        f"# Biostatistics Inverse-Variance Meta-Analysis Work Order — {b}evidence_quant_analyst{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the 16-study inverse-variance fixed-effect meta-analysis in {b}/workspace/meta_review/Evidence_Synthesis.xlsx{b} and render the forest plot.",
        f"Both {b}/workspace/meta_review/Evidence_Synthesis.xlsx{b} (with an active session tag in {b}Study_Weights!C1{b}) and {b}Survey_Manuscript.odt{b} are open in LibreOffice alongside {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Under {b}VIEW = COHORT_EFFECT_SIZES{b} on {b}http://127.0.0.1:{PORTAL_PORT}/{b}, export {b}/home/user/Downloads/registry_feed.csv{b} (cross-checking against `RETRACTION_WATCH` / `citevault.sqlite` so the 4 retracted/superseded studies `ST-04, ST-09, ST-14, ST-18` are **excluded**) and copy the Biostatistics Synthesis Seal to the clipboard.",
        f"2. Populate {b}Evidence_Synthesis.xlsx{b}:",
        f"   - In {b}Study_Weights{b}: list the `16` eligible studies in `A2:D17` with `w_i = 1 / se_i^2` in col `B` and `w_i * log_rr_i` in col `D`, preserving the active desk tag in {b}Study_Weights!C1{b}.",
        f"   - In {b}Pooled_Summary{b}: set `B2 = 16`, `B3 = sum(w_i)`, `B4 = sum(w_i * log_rr_i)`, formula {b}=B4/B3{b} in `B5` (`Pooled_FixedEffect_LogRR`), and the Biostatistics Synthesis Seal in `B6` (preserving `B7`).",
        f"3. Render a clean forest plot PNG (`>= 800 x 480` px) to {b}/workspace/meta_review/forest_plot.png{b} and export {b}/workspace/meta_review/Evidence_Summary.pdf{b} from {b}Evidence_Synthesis.xlsx{b}.",
        "",
    ])
    return {"bib_manuscript_editor": role_a, "evidence_quant_analyst": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    mr = ws / "meta_review"
    mr.mkdir(parents=True, exist_ok=True)
    db_p = mr / "citevault.sqlite"
    if db_p.exists():
        db_p.unlink()
    conn = sqlite3.connect(str(db_p))
    conn.execute(
        "CREATE TABLE studies (study_id TEXT PRIMARY KEY, bib_key TEXT, first_author TEXT, pub_year INTEGER, doi TEXT, curation_status TEXT)"
    )
    for st_id, bk, au, yr, doi, _st, _lrr, _se in STUDIES_TRUTH:
        conn.execute("INSERT INTO studies VALUES (?,?,?,?,?,?)", (st_id, bk, au, yr, doi, "UNSCREENED"))
    conn.commit()
    conn.close()

    write_simple_odt(
        mr / "Survey_Manuscript.odt",
        "2026 Systematic Review & Meta-Analysis Draft",
        [
            ("PRISMA_COUNTS", "INCLUDED_STUDIES=TBD | EXCLUDED_RETRACTED=TBD"),
            ("EDITORIAL_RETRACTION_SEAL", "PENDING_RETRACTION_SEAL"),
        ],
    )
    write_multisheet_xlsx(
        mr / "Evidence_Synthesis.xlsx",
        [
            ("Study_Weights", _make_weights_sheet(eligible_only=False, desk_tag="")),
            ("Pooled_Summary", _make_summary_sheet(20, 100.0, 0.0, "PENDING", "PENDING")),
        ],
    )
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_registry_html(view_mode: str) -> str:
    if view_mode == "RETRACTION_WATCH":
        rows = "".join(f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{s[4]}</td><td>{s[5]}</td></tr>" for s in STUDIES_TRUTH[:6])
        tbl = f"<h3>Retraction & Duplicate Watch (Preview 6/20 — Export CSV for all 20)</h3><table><thead><tr><th>ID</th><th>BibKey</th><th>DOI</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>"
    else:
        rows = "".join(f"<tr><td>{s[0]}</td><td>{s[2]} ({s[3]})</td><td>{s[6]:.3f}</td><td>{s[7]:.3f}</td></tr>" for s in STUDIES_TRUTH[:6])
        tbl = f"<h3>Cohort Effect Sizes log(RR) & SE (Preview 6/20 — Export CSV for all 20)</h3><table><thead><tr><th>ID</th><th>Study</th><th>log_rr</th><th>se</th></tr></thead><tbody>{rows}</tbody></table>"
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>Preprint & Retraction Registry</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f8fafc;}}header{{background:#0f172a;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;}}
.bar{{background:#e2e8f0;padding:10px 18px;display:flex;gap:10px;flex-wrap:wrap;}}button{{padding:6px 12px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-top:10px;}}th,td{{border:1px solid #cbd5e1;padding:6px 10px;}}</style></head>
<body>
<header><strong>Global Preprint & Trial Integrity Registry</strong><span style="font-family:monospace;">VIEW={view_mode}</span></header>
<div class="bar">
  <button onclick="setV('RETRACTION_WATCH')">RETRACTION_WATCH</button>
  <button onclick="setV('COHORT_EFFECT_SIZES')">COHORT_EFFECT_SIZES</button>
  <button onclick="expCsv()">Export Full 20-Study CSV (/home/user/Downloads/registry_feed.csv)</button>
  <button onclick="cpSeal()">Copy Active View Seal to Clipboard</button>
  <span id="msg" style="font-family:monospace;font-size:12px;">Ready</span>
</div>
<main style="padding:14px 18px;">{tbl}</main>
<script>
async function setV(v){{await fetch('/api/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{view:v}})}});location.reload();}}
async function expCsv(){{const r=await fetch('/api/export',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Saved ['+d.view+']';}}
async function cpSeal(){{const r=await fetch('/api/seal',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Copied ['+d.view+']';}}
</script></body></html>"""


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "view": "RETRACTION_WATCH",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "contention_events": 0,
    }
    write_json(state_p, pstate)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a: Any) -> None:
            return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("rbs06_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True}); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_secret:
                self.send_response(302); self.send_header("Set-Cookie", f"rbs06_sso={sso_cookie}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"}); return
            with lock:
                raw = _render_registry_html(pstate["view"]).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_POST(self) -> None:
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"}); return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            if self.path == "/api/state":
                with lock:
                    if body.get("view") in ("RETRACTION_WATCH", "COHORT_EFFECT_SIZES") and pstate["view"] != body["view"]:
                        pstate["view"] = body["view"]
                        pstate["session_switches"] += 1
                        write_json(state_p, pstate)
                    self._send_json(200, {"ok": True, "view": pstate["view"]})
                return
            if self.path == "/api/export":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.25 if is_adm else 3.0)
                dl_p = Path("/home/user/Downloads/registry_feed.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    vw = pstate["view"]
                    if vw == "RETRACTION_WATCH":
                        lines = ["study_id,bib_key,doi,registry_status"] + [f"{s[0]},{s[1]},{s[4]},{s[5]}" for s in STUDIES_TRUTH]
                    else:
                        lines = ["study_id,first_author,pub_year,log_rr,se"] + [f"{s[0]},{s[2]},{s[3]},{s[6]:.4f},{s[7]:.4f}" for s in STUDIES_TRUTH]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    os.chmod(dl_p, 0o644)
                    pstate["download_exports"] += 1
                    write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "view": vw})
                return
            if self.path == "/api/seal":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.2 if is_adm else 1.2)
                with lock:
                    vw = pstate["view"]
                    seal = RETRACTION_SEAL if vw == "RETRACTION_WATCH" else BIOSTAT_SEAL
                    pstate["clipboard_copies"] += 1
                    write_json(state_p, pstate)
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "view": vw})
                return
            self._send_json(404, {"error": "Not found"})

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"mode": "studio_sso", "url": f"http://127.0.0.1:{port}/?sso_boot={boot_secret}"}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    from tasks.exam_contention_v2.c06_impress_calc_actuarial import boot_desktop_apps as _boot_sso
    _boot_sso(workspace_map, state_dir)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image

    ws = next(iter(workspace_map.values()))
    mr = ws / "meta_review"
    db_p = mr / "citevault.sqlite"
    bib_p = mr / "references_clean.bib"
    odt_p = mr / "Survey_Manuscript.odt"
    xp = mr / "Evidence_Synthesis.xlsx"
    pdf_a = mr / "Survey_Manuscript.pdf"
    pdf_b = mr / "Evidence_Summary.pdf"
    png_b = mr / "forest_plot.png"

    db_map = {}
    if db_p.is_file():
        with sqlite3.connect(str(db_p)) as conn:
            for sid, cst in conn.execute("SELECT study_id, curation_status FROM studies"):
                db_map[sid] = cst

    inc_ok = sum(1 for s in ELIGIBLE_STUDIES if db_map.get(s[0]) == "INCLUDED_ELIGIBLE")
    exc_ok = sum(1 for sid in EXCLUDED_IDS if db_map.get(sid) == "EXCLUDED_RETRACTED")

    bib_txt = bib_p.read_text(encoding="utf-8", errors="replace") if bib_p.is_file() else ""
    bib_elig_hits = sum(1 for s in ELIGIBLE_STUDIES if s[1] in bib_txt and s[4] in bib_txt)
    bib_no_retracted = not any(s[1] in bib_txt for s in STUDIES_TRUTH if s[0] in EXCLUDED_IDS)

    odt_txt = read_odt_plain_text(odt_p)
    pa_txt = extract_pdf_text(pdf_a)
    raw_sh = read_multisheet_xlsx(xp) if xp.is_file() else {}
    ev_sh = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}

    def _v(sh: str, ref: str) -> float:
        val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return float(val) if isinstance(val, (int, float)) else -9999.0

    def _s(sh: str, ref: str) -> str:
        val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return str(val or "").strip()

    def _f(sh: str, ref: str) -> bool:
        return bool(((raw_sh.get(sh) or {}).get(ref) or {}).get("formula"))

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_db_eligible16", inc_ok == 16, 0.12, f"citevault INCLUDED_ELIGIBLE {inc_ok}/16"),
        ("a_db_excluded4", exc_ok == 4, 0.10, f"citevault EXCLUDED_RETRACTED {exc_ok}/4"),
        ("a_bib_exists", bib_p.is_file(), 0.05, "Missing references_clean.bib"),
        ("a_bib_half", bib_elig_hits >= 10, 0.07, f"BibTeX eligible entries {bib_elig_hits}/16"),
        ("a_bib_all16", bib_elig_hits == 16, 0.10, f"BibTeX eligible entries {bib_elig_hits}/16 != 16/16"),
        ("a_bib_clean", bib_p.is_file() and bib_no_retracted, 0.10, "references_clean.bib still contains retracted/superseded keys"),
        ("a_bib_article_fmt", bib_txt.lower().count("@article") >= 16, 0.06, "BibTeX @article count < 16"),
        ("a_odt_counts", "INCLUDED_STUDIES=16" in odt_txt and "EXCLUDED_RETRACTED=4" in odt_txt, 0.08, "Survey_Manuscript.odt missing PRISMA counts"),
        ("a_odt_seal", RETRACTION_SEAL in odt_txt, 0.08, "Survey_Manuscript.odt missing Editorial_Retraction_Seal"),
        ("a_xlsx_b7_seal", _s("Pooled_Summary", "B7") == RETRACTION_SEAL, 0.08, "Pooled_Summary!B7 missing Editorial_Retraction_Seal"),
        ("a_pdf_exists", pdf_a.is_file(), 0.04, "Missing Survey_Manuscript.pdf"),
        ("a_pdf_seal", RETRACTION_SEAL in pa_txt, 0.04, "Survey_Manuscript.pdf missing Retraction Seal"),
        ("a_pdf_counts", "INCLUDED_STUDIES=16" in pa_txt, 0.04, "Survey_Manuscript.pdf missing INCLUDED_STUDIES=16"),
        ("a_pdf_desk_tag", WRITER_DESK_TAG in pa_txt, 0.04, f"Survey_Manuscript.pdf missing {WRITER_DESK_TAG}"),
    ]

    forest_ok = False
    if png_b.is_file() and png_b.stat().st_size > 2000:
        try:
            with Image.open(png_b) as im:
                forest_ok = im.size[0] >= 800 and im.size[1] >= 480
        except Exception:
            forest_ok = False
    pb_txt = extract_pdf_text(pdf_b)
    wt_rows = sum(1 for r_idx in range(2, 18) if _s("Study_Weights", f"A{r_idx}").startswith("ST-") and _s("Study_Weights", f"A{r_idx}") not in EXCLUDED_IDS)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_wt_rows12", wt_rows >= 12, 0.07, f"Study_Weights eligible rows {wt_rows}/16"),
        ("b_wt_rows16", wt_rows == 16, 0.10, f"Study_Weights eligible rows {wt_rows}/16 != 16"),
        ("b_no_excl_in_wt", not any(_s("Study_Weights", f"A{r}") in EXCLUDED_IDS for r in range(2, 22)), 0.09, "Study_Weights still includes retracted studies"),
        ("b_inc_count_16", abs(_v("Pooled_Summary", "B2") - 16.0) <= 0.01, 0.07, "Pooled_Summary!B2 != 16"),
        ("b_sum_w", abs(_v("Pooled_Summary", "B3") - TRUE_SUM_W) <= 1.5, 0.10, f"Total_InvVar_Weight={_v('Pooled_Summary','B3')} != {TRUE_SUM_W}"),
        ("b_sum_wy", abs(_v("Pooled_Summary", "B4") - TRUE_SUM_WY) <= 0.8, 0.10, f"Total_Weighted_LogRR={_v('Pooled_Summary','B4')} != {TRUE_SUM_WY}"),
        ("b_pooled_formula", _f("Pooled_Summary", "B5"), 0.07, "Pooled_Summary!B5 missing formula"),
        ("b_pooled_val", abs(_v("Pooled_Summary", "B5") - TRUE_POOLED_LOGRR) <= 0.008, 0.10, f"Pooled_FixedEffect_LogRR={_v('Pooled_Summary','B5')} != {TRUE_POOLED_LOGRR}"),
        ("b_biostat_seal", _s("Pooled_Summary", "B6") == BIOSTAT_SEAL, 0.09, "Pooled_Summary!B6 missing Biostat_Synthesis_Seal"),
        ("b_forest_png", forest_ok, 0.07, "forest_plot.png missing or <800x480"),
        ("b_pdf_exists", pdf_b.is_file(), 0.04, "Missing Evidence_Summary.pdf"),
        ("b_pdf_val", "-0.26" in pb_txt or str(round(TRUE_POOLED_LOGRR, 3)) in pb_txt, 0.04, "Evidence_Summary.pdf missing pooled logRR"),
        ("b_pdf_seal", BIOSTAT_SEAL in pb_txt, 0.03, "Evidence_Summary.pdf missing Biostat Seal"),
        ("b_st01_weight", abs(_v("Study_Weights", "B2") - 100.0) <= 1.0 or wt_rows == 16, 0.03, "Study_Weights!B2 inaccurate"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_writer_desk_tag", WRITER_DESK_TAG in odt_txt, 0.06, f"Survey_Manuscript.odt lost {WRITER_DESK_TAG}"),
        ("j_calc_desk_tag", _s("Study_Weights", "C1") == CALC_DESK_TAG, 0.06, f"Study_Weights!C1 lost {CALC_DESK_TAG}"),
        ("j_sheets_preserved", "Study_Weights" in ev_sh and "Pooled_Summary" in ev_sh, 0.07, "Evidence_Synthesis.xlsx lost Study_Weights or Pooled_Summary sheet"),
        ("j_no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.06, "Open soffice.bin window held stale unsaved buffer"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=1.0,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    from PIL import Image, ImageDraw

    assert role in ("bib_manuscript_editor", "evidence_quant_analyst")
    ws = next(iter(workspace_map.values()))
    mr = ws / "meta_review"
    db_p = mr / "citevault.sqlite"
    odt_p = mr / "Survey_Manuscript.odt"
    xp = mr / "Evidence_Synthesis.xlsx"
    adm_p = Path("/opt/ec2_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        flush_open_libreoffice_to_disk(odt_p)
        is_a = (role == "bib_manuscript_editor")
        vw = "RETRACTION_WATCH" if is_a else "COHORT_EFFECT_SIZES"
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/state", data=json.dumps({"view": vw}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/export", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        seal_v = get_x11_clipboard()

        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev.get("Study_Weights") or {}).get("C1", {}).get("value") or CALC_DESK_TAG)
        cur_b6 = str((ev.get("Pooled_Summary") or {}).get("B6", {}).get("value") or "PENDING")
        cur_b7 = str((ev.get("Pooled_Summary") or {}).get("B7", {}).get("value") or "PENDING")
        cur_cnt = int(float((ev.get("Pooled_Summary") or {}).get("B2", {}).get("value") or 20))
        cur_sw = float((ev.get("Pooled_Summary") or {}).get("B3", {}).get("value") or 100.0)
        cur_swy = float((ev.get("Pooled_Summary") or {}).get("B4", {}).get("value") or 0.0)

        if is_a:
            with sqlite3.connect(str(db_p), timeout=15.0) as conn:
                for s in STUDIES_TRUTH:
                    st_v = "INCLUDED_ELIGIBLE" if s[5] == "ELIGIBLE_PRIMARY" else "EXCLUDED_RETRACTED"
                    conn.execute("UPDATE studies SET curation_status=? WHERE study_id=?", (st_v, s[0]))
                conn.commit()
            bib_entries = [
                f"@article{{{s[1]},\n  author = {{{s[2]}}},\n  year = {{{s[3]}}},\n  doi = {{{s[4]}}}\n}}"
                for s in ELIGIBLE_STUDIES
            ]
            (mr / "references_clean.bib").write_text("\n\n".join(bib_entries) + "\n", encoding="utf-8")
            cur_odt = read_odt_plain_text(odt_p)
            paras = [("DESK_SESSION_TAG", WRITER_DESK_TAG)] if WRITER_DESK_TAG in cur_odt else [("DESK_SESSION_TAG", WRITER_DESK_TAG)]
            paras.extend([
                ("PRISMA_COUNTS", "INCLUDED_STUDIES=16 | EXCLUDED_RETRACTED=4"),
                ("EDITORIAL_RETRACTION_SEAL", seal_v),
            ])
            write_simple_odt(odt_p, "2026 Systematic Review & Meta-Analysis Final", paras)
            update_single_sheet_xlsx(xp, "Pooled_Summary", _make_summary_sheet(cur_cnt, cur_sw, cur_swy, cur_b6, seal_v))
            convert_doc_to_pdf_isolated(odt_p, mr / "Survey_Manuscript.pdf")
        else:
            update_single_sheet_xlsx(xp, "Study_Weights", _make_weights_sheet(eligible_only=True, desk_tag=desk_c1))
            update_single_sheet_xlsx(xp, "Pooled_Summary", _make_summary_sheet(16, TRUE_SUM_W, TRUE_SUM_WY, seal_v, cur_b7))
            im = Image.new("RGB", (920, 540), (248, 250, 252))
            dr = ImageDraw.Draw(im)
            dr.rectangle([40, 40, 880, 500], outline=(15, 23, 42), width=2)
            dr.line([(560, 60), (560, 480)], fill=(100, 116, 139), width=2)
            for idx, s in enumerate(ELIGIBLE_STUDIES):
                y = 72 + idx * 24
                cx = int(560 + s[6] * 400)
                hw = int(s[7] * 1.96 * 400)
                dr.line([(cx - hw, y), (cx + hw, y)], fill=(37, 99, 235), width=2)
                dr.rectangle([cx - 4, y - 4, cx + 4, y + 4], fill=(29, 78, 216))
            im.save(mr / "forest_plot.png", "PNG")
            convert_doc_to_pdf_isolated(xp, mr / "Evidence_Summary.pdf")

        reload_open_libreoffice_docs([xp, odt_p])

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_6 + LAW_2): Concurrent Pooled_Summary sheet write clobbers peer's clipboard seal."""
    ws = next(iter(workspace_map.values()))
    xp = ws / "meta_review/Evidence_Synthesis.xlsx"
    solve_role("bib_manuscript_editor", workspace_map, port, careful_conc=False)
    solve_role("evidence_quant_analyst", workspace_map, port, careful_conc=False)
    # Role B's stale snapshot overwrote B7 back to 'PENDING'
    update_single_sheet_xlsx(xp, "Pooled_Summary", _make_summary_sheet(16, TRUE_SUM_W, TRUE_SUM_WY, BIOSTAT_SEAL, "PENDING"))
    update_single_sheet_xlsx(xp, "Study_Weights", _make_weights_sheet(eligible_only=True, desk_tag=""))
    reload_open_libreoffice_docs([xp, ws / "meta_review/Survey_Manuscript.odt"])
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)

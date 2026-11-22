"""EC2-C06: Single-Instance LibreOffice (Writer 8-Page Board Pack + Calc Solvency Model) Split-Brain.

Track 2 — Shared Process / Shared Profile / Coupled Artifact Contention (Full GUI + CLI):
  - A single running soffice.bin instance holds BOTH Solvency_II_Model.xlsx (Calc, with unsaved desk tag)
    AND Q4_Board_Brief.odt (Writer, 8-page board pack with off-page margin indents & font defects), sharing the default
    LibreOffice profile lock (/home/user/.config/libreoffice) plus an HttpOnly Reinsurance/Asset Portal.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from tasks.exam_contention_v2.common import (
    _xml_esc,
    advisory_lock,
    build_grade_payload,
    convert_doc_to_pdf_isolated,
    extract_pdf_text,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    pdf_page_count,
    read_json_safe,
    reload_open_libreoffice_docs,
    set_x11_clipboard,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "EC2-C06"
PORTAL_PORT = 19106
CALC_DESK_TAG = "ACTUARY-DESK-402"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Single-Instance LibreOffice Writer 8-Page Board Pack & Calc Solvency II Split-Brain",
    "domain": "Insurance Actuarial Reserving, Solvency II Capital & Executive Deck Production",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "libreoffice_single_instance_calc_and_writer_lock",
        "gui_dirty_buffer_vs_disk_cli_split_brain",
        "shared_httponly_portal_and_x11_clipboard",
        "bidirectional_solvency_coverage_envelope",
    ),
    "roles": ("reserving_actuary", "investor_deck_lead"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (
        ("/workspace/board_pack/Solvency_II_Model.xlsx", CALC_DESK_TAG, "calc"),
        ("/workspace/board_pack/Q4_Board_Brief.odt", "", "writer"),
    ),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

TREATY_SEAL = make_opaque_seal("ec2_c06", "TREATY_RETENTION_VIEW:NET_CAP")
ASSET_SEAL = make_opaque_seal("ec2_c06", "ASSET_HAIRCUT_VIEW:SII_SHOCK")

# Exact Actuarial Oracle (M USD):
# Gross incurred paid+case in claims_triangle.db (POSTED & non-salvage-void) * LDF, capped per cat event:
#   AUTO_LIAB : net incurred 74.00 * LDF 1.25 = 92.50 M
#   COMM_PROP : net incurred 57.00 * LDF 1.20 = 68.40 M
#   CYBER_EO  : net incurred 31.50 * LDF 1.40 = 44.10 M
#   Total_Ultimate_IBNR_M = 205.00 M
TRUE_LOB_ULTIMATE = {
    "AUTO_LIAB": 92.50,
    "COMM_PROP": 68.40,
    "CYBER_EO": 44.10,
}
TRUE_TOTAL_IBNR_M = 205.00

# Asset Portfolio Oracle (M USD):
#   Gross_Admitted_Bonds_M = 386.00 M (exclude NON_ADMITTED_AFFILIATE rows in asset CSV)
#   Solvency_Market_Haircut_M = -29.50 M
#   Net_Admitted_Assets_M = 356.50 M
TRUE_ADMITTED_BONDS_M = 386.00
TRUE_MARKET_HAIRCUT_M = -29.50
TRUE_NET_ASSETS_M = 356.50

SCR_FIXED_M = 145.00
SUBDEBT_RANGE_M = (38.0, 58.0)
SIDECAR_RANGE_M = (26.0, 46.0)
SOLVENCY_RATIO_BAND = (1.62, 1.66)

ASSET_CSV_ROWS: list[tuple[str, str, float, float, str]] = [
    ("BND-01", "SOVEREIGN_AAA", 112.0, 0.025, "ADMITTED"),
    ("BND-02", "CORP_IG_AA",     94.0, 0.065, "ADMITTED"),
    ("BND-03", "MUNI_REV_A",     76.0, 0.085, "ADMITTED"),
    ("BND-04", "COVERED_MTG",    64.0, 0.110, "ADMITTED"),
    ("BND-05", "INFRA_GREEN",    40.0, 0.177, "ADMITTED"),
    ("BND-06", "AFFIL_NOTE",     48.0, 0.350, "NON_ADMITTED_AFFILIATE"),
    ("BND-07", "INTERCO_LOAN",   32.0, 0.400, "NON_ADMITTED_AFFILIATE"),
]
# Verify haircut sum on ADMITTED: 112*0.025(2.80) + 94*0.065(6.11) + 76*0.085(6.46) + 64*0.110(7.04) + 40*0.17725(7.09) = 29.50!
ASSET_CSV_ROWS[4] = ("BND-05", "INFRA_GREEN", 40.0, 0.17725, "ADMITTED")


def _build_claims_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    rng = random.Random(20260606)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE claims_ledger (
            claim_id TEXT PRIMARY KEY,
            lob TEXT NOT NULL,
            status TEXT NOT NULL,
            reins_flag TEXT NOT NULL,
            incurred_musd REAL NOT NULL
        )
        """
    )
    rows: list[tuple] = []
    idx = 1
    for lob, target_sum, n in (("AUTO_LIAB", 74.0, 180), ("COMM_PROP", 57.0, 150), ("CYBER_EO", 31.5, 120)):
        ws = [rng.uniform(0.6, 1.7) for _ in range(n)]
        s = sum(ws)
        vals = [round(target_sum * w / s, 5) for w in ws[:-1]]
        vals.append(round(target_sum - sum(vals), 5))
        for v in vals:
            rows.append((f"CLM-{idx:04d}", lob, "OPEN_RESERVE", "NET_RETAINED", v))
            idx += 1
    # Trap rows to exclude: VOID_DUPLICATE and CEDED_EXCESS_LAYER
    for _ in range(60):
        rows.append((f"CLM-{idx:04d}", "AUTO_LIAB", "VOID_DUPLICATE", "NET_RETAINED", round(rng.uniform(0.2, 0.9), 3)))
        idx += 1
    for _ in range(55):
        rows.append((f"CLM-{idx:04d}", "COMM_PROP", "OPEN_RESERVE", "CEDED_EXCESS_LAYER", round(rng.uniform(0.3, 1.1), 3)))
        idx += 1
    rng.shuffle(rows)
    conn.executemany("INSERT INTO claims_ledger VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def write_board_odt(
    path: Path,
    *,
    fix_defects: bool = False,
    net_assets_str: str = "TBD",
    solvency_ratio_str: str = "TBD",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    font_body = "Liberation Sans" if fix_defects else "Comic Sans MS"
    bad_margin = "0.0cm" if fix_defects else "20.5cm"  # Page width is 21.0cm -> 20.5cm left margin overflows off-page!

    manifest_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">\n'
        '  <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
        '  <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>\n'
        '  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
        '</manifest:manifest>\n'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"/>\n'
    )
    paras_xml = []
    slide_titles = [
        "1. Q4 Solvency II Executive Overview [DECK_CONTROL: BOARD-REV9-402]",
        "2. Underwriting Portfolio Mix",
        "3. Motor & Liability Loss Emergence",
        "4. Catastrophe Reinsurance Program",
        "5. Fixed-Income Investment Allocation",
        "6. Market Risk Stress & Haircut Schedule",
        "7. Subordinated Debt & Sidecar Facilities",
        "8. Final Solvency II Capital Sign-Off",
    ]
    for idx, stitle in enumerate(slide_titles, 1):
        t_style = "TitleP1" if idx == 1 else "TitleBreakP"
        b_style = "BodyShiftP" if idx in (3, 5, 7) else "BodyNormP"
        body_line = (
            f"NET_ADMITTED_ASSETS_M={net_assets_str} | SOLVENCY_COVERAGE_RATIO={solvency_ratio_str}"
            if idx == 8
            else f"Board Review Section {idx} — Corporate Standard Typography Required"
        )
        paras_xml.append(f'    <text:p text:style-name="{t_style}">{_xml_esc(stitle)}</text:p>')
        paras_xml.append(f'    <text:p text:style-name="{b_style}">{_xml_esc(body_line)}</text:p>')
    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
        'office:version="1.2">\n'
        '  <office:automatic-styles>\n'
        '    <style:style style:name="TitleP1" style:family="paragraph">'
        '<style:text-properties style:font-name="Liberation Sans" fo:font-size="18pt" fo:font-weight="bold"/></style:style>\n'
        '    <style:style style:name="TitleBreakP" style:family="paragraph">'
        '<style:paragraph-properties fo:break-before="page"/>'
        '<style:text-properties style:font-name="Liberation Sans" fo:font-size="18pt" fo:font-weight="bold"/></style:style>\n'
        f'    <style:style style:name="BodyNormP" style:family="paragraph">'
        f'<style:paragraph-properties fo:margin-left="0.0cm"/>'
        f'<style:text-properties style:font-name="{font_body}" fo:font-size="13pt"/></style:style>\n'
        f'    <style:style style:name="BodyShiftP" style:family="paragraph">'
        f'<style:paragraph-properties fo:margin-left="{bad_margin}"/>'
        f'<style:text-properties style:font-name="{font_body}" fo:font-size="13pt"/></style:style>\n'
        '  </office:automatic-styles>\n'
        '  <office:body><office:text>\n' + "\n".join(paras_xml) + '\n  </office:text></office:body>\n'
        '</office:document-content>\n'
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("META-INF/manifest.xml", manifest_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("styles.xml", styles_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", content_xml, compress_type=ZIP_DEFLATED)


def inspect_board_odt(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"ok": False}
    try:
        with ZipFile(path, "r") as zf:
            raw_xml = zf.read("content.xml").decode("utf-8", errors="replace")
        root = ET.fromstring(raw_xml)
        paras = [el for el in root.iter() if el.tag.endswith("}p") or el.tag.endswith("}h")]
        off_canvas = 0
        for pp in root.iter():
            if pp.tag.endswith("}paragraph-properties"):
                ml = next((v for k, v in pp.attrib.items() if k.endswith("}margin-left")), "0cm")
                m_l = re.match(r"([0-9.]+)cm", ml)
                if m_l and float(m_l.group(1)) > 5.0:
                    off_canvas += 1
        all_txt = " ".join("".join(p.itertext()) for p in paras)
        has_comic = "Comic Sans" in raw_xml
        return {
            "ok": True,
            "section_count": sum(1 for p in paras if "Board Review Section" in "".join(p.itertext()) or "NET_ADMITTED_ASSETS_M=" in "".join(p.itertext())),
            "off_canvas_frames": off_canvas,
            "has_comic_sans": has_comic,
            "has_rev_tag": "BOARD-REV9-402" in all_txt,
            "text": all_txt,
        }
    except Exception:
        return {"ok": False}


def _make_ibnr_sheet(auto_m: float, prop_m: float, cyber_m: float, desk_tag: str = "", seal: str = "PENDING") -> list[list]:
    tot = round(auto_m + prop_m + cyber_m, 2)
    return [
        ["Line_Of_Business", "Ultimate_Loss_MUSD", desk_tag],
        ["AUTO_LIAB_Ultimate_M", round(auto_m, 2), "LDF_APPLIED"],
        ["COMM_PROP_Ultimate_M", round(prop_m, 2), "LDF_APPLIED"],
        ["CYBER_EO_Ultimate_M", round(cyber_m, 2), "LDF_APPLIED"],
        ["Total_Ultimate_IBNR_M", ("=SUM(B2:B4)", tot), "CONSOLIDATED_IBNR"],
        ["Treaty_Actuarial_Seal", seal, "CLIPBOARD_SEAL"],
    ]


def _make_asset_sheet(bonds_m: float, haircut_m: float, seal: str = "PENDING") -> list[list]:
    net = round(bonds_m + haircut_m, 2)
    return [
        ["Asset_Item", "Amount_MUSD", "Basis"],
        ["Gross_Admitted_Bonds_M", round(bonds_m, 2), "ADMITTED_ONLY"],
        ["Solvency_Market_Haircut_M", round(haircut_m, 2), "NEGATIVE_SHOCK"],
        ["Net_Admitted_Assets_M", ("=SUM(B2:B3)", net), "ELIGIBLE_ASSETS"],
        ["Asset_Stress_Seal", seal, "CLIPBOARD_SEAL"],
    ]


def _make_cap_sheet(subdebt_m: float, sidecar_m: float, net_asset_m: float, ibnr_m: float) -> list[list]:
    own = round(net_asset_m - ibnr_m + subdebt_m + sidecar_m, 2)
    rat = round(own / SCR_FIXED_M, 4)
    return [
        ["Capital_Item", "Value", "Rule"],
        ["SCR_Required_Capital_M", SCR_FIXED_M, "FIXED_REGULATORY_SCR"],
        ["Tier2_Subordinated_Notes_M", round(subdebt_m, 2), "ACTUARY_SIZED"],
        ["Catastrophe_Sidecar_Collateral_M", round(sidecar_m, 2), "DECK_LEAD_SIZED"],
        ["Total_Eligible_Own_Funds_M", ("=Asset_Portfolio!B4-IBNR_Reserve!B5+B3+B4", own), "OWN_FUNDS"],
        ["Solvency_Coverage_Ratio", ("=B5/B2", rat), "TARGET_1.62_TO_1.66"],
    ]


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    act_md = "\n".join([
        f"# Actuarial Reserving & Solvency II Work Order — {b}reserving_actuary{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the Q4 Ultimate Loss & IBNR valuation and subordinated debt sizing in {b}/workspace/board_pack{b}.",
        f"Both {b}/workspace/board_pack/Solvency_II_Model.xlsx{b} (with an active desk control tag in {b}IBNR_Reserve!C1{b}) and {b}Q4_Board_Brief.odt{b} are currently open in LibreOffice alongside the Solvency II Reinsurance & Asset Portal at {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Reconcile net retained open reserves from {b}/workspace/board_pack/claims_triangle.db{b} (include only {b}status='OPEN_RESERVE'{b} and {b}reins_flag='NET_RETAINED'{b}) multiplied by the LOB Loss Development Factors in {b}TREATY_RETENTION_VIEW{b} on {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        f"2. Under {b}VIEW = TREATY_RETENTION_VIEW{b}, copy the Treaty Actuarial Seal to the clipboard and record it in {b}IBNR_Reserve!B6{b}; populate {b}IBNR_Reserve!B2:B5{b} (formula {b}=SUM(B2:B4){b} in {b}B5{b}) and size only {b}Capital_Structure!B3{b} ({b}Tier2_Subordinated_Notes_M{b} in {b}[38.0, 58.0]{b}) so {b}Capital_Structure!B6{b} lands in {b}[1.62, 1.66]{b}, preserving all sheets, formulas, and {b}IBNR_Reserve!C1{b}.",
        f"3. Export {b}/workspace/board_pack/Actuarial_Opinion.pdf{b} from {b}Solvency_II_Model.xlsx{b}.",
        "",
    ])

    deck_md = "\n".join([
        f"# Solvency II Asset Haircut & Executive Board Pack Work Order — {b}investor_deck_lead{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the Solvency II admitted bond haircut schedule, sidecar collateral sizing, and 8-page Writer executive board pack remediation in {b}/workspace/board_pack{b}.",
        f"Both {b}/workspace/board_pack/Q4_Board_Brief.odt{b} and {b}Solvency_II_Model.xlsx{b} (with an active desk control tag in {b}IBNR_Reserve!C1{b}) are currently open in LibreOffice alongside {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Under {b}VIEW = ASSET_HAIRCUT_VIEW{b} on {b}http://127.0.0.1:{PORTAL_PORT}/{b}, export {b}/home/user/Downloads/sii_schedule.csv{b} (include only {b}ADMITTED{b} bonds; enter {b}Solvency_Market_Haircut_M{b} as a negative {b}-sum(par_musd * shock_pct){b} in {b}Asset_Portfolio!B3{b}), copy the Asset Stress Seal to {b}Asset_Portfolio!B5{b}, and size only {b}Capital_Structure!B4{b} ({b}Catastrophe_Sidecar_Collateral_M{b} in {b}[26.0, 46.0]{b}) so {b}Capital_Structure!B6{b} lands in {b}[1.62, 1.66]{b}, preserving {b}IBNR_Reserve!C1{b}.",
        f"2. Remediate {b}/workspace/board_pack/Q4_Board_Brief.odt{b} (8 pages, one section per page): replace any {b}Comic Sans MS{b} styling with {b}Liberation Sans{b}, reset the corrupted {b}20.5cm{b} left-margin indents (on Sections 3, 5, 7) back to {b}<= 2.0cm{b}, update Section 8 (Page 8) with the reconciled {b}NET_ADMITTED_ASSETS_M{b} (`356.50`) and compliant {b}SOLVENCY_COVERAGE_RATIO{b}, preserve {b}BOARD-REV9-402{b} on Page 1 and all 8 page breaks, and export the 8-page {b}/workspace/board_pack/Q4_Board_Brief.pdf{b}.",
        "",
    ])
    return {"reserving_actuary": act_md, "investor_deck_lead": deck_md}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    bp = ws / "board_pack"
    bp.mkdir(parents=True, exist_ok=True)
    _build_claims_db(bp / "claims_triangle.db")
    write_board_odt(bp / "Q4_Board_Brief.odt", fix_defects=False)
    write_multisheet_xlsx(
        bp / "Solvency_II_Model.xlsx",
        [
            ("IBNR_Reserve", _make_ibnr_sheet(90.0, 68.0, 44.0, desk_tag="", seal="PENDING")),
            ("Asset_Portfolio", _make_asset_sheet(388.0, -30.0, seal="PENDING")),
            ("Capital_Structure", _make_cap_sheet(55.0, 43.0, 358.0, 202.0)),
        ],
    )
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_sii_html(view_mode: str) -> str:
    if view_mode == "TREATY_RETENTION_VIEW":
        body = (
            "<h3>Actuarial Treaty Retention & Loss Development Factors (LDF)</h3>"
            "<table><thead><tr><th>LOB</th><th>Tail LDF</th><th>Claims DB Filter</th></tr></thead><tbody>"
            "<tr><td>AUTO_LIAB</td><td>1.250</td><td>status='OPEN_RESERVE' AND reins_flag='NET_RETAINED'</td></tr>"
            "<tr><td>COMM_PROP</td><td>1.200</td><td>status='OPEN_RESERVE' AND reins_flag='NET_RETAINED'</td></tr>"
            "<tr><td>CYBER_EO</td><td>1.400</td><td>status='OPEN_RESERVE' AND reins_flag='NET_RETAINED'</td></tr>"
            "</tbody></table>"
        )
    else:
        rows = "".join(
            f"<tr><td>{bid}</td><td>{cat}</td><td>{par:.2f}</td><td>{shk*100:.3f}%</td><td>{adm}</td></tr>"
            for bid, cat, par, shk, adm in ASSET_CSV_ROWS[:4]
        )
        body = (
            "<h3>Solvency II Fixed-Income Stress Schedule (Previewing 4 of 7 — Export CSV for all 7)</h3>"
            f"<table><thead><tr><th>Bond ID</th><th>Class</th><th>Par (M USD)</th><th>Shock %</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>Solvency II Portal</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f8fafc;}}header{{background:#0f172a;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;}}
.bar{{background:#e2e8f0;padding:10px 18px;display:flex;gap:10px;flex-wrap:wrap;}}button{{padding:6px 12px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-top:10px;}}th,td{{border:1px solid #cbd5e1;padding:7px 10px;text-align:left;}}</style></head>
<body>
<header><strong>Solvency II Actuarial & Asset Risk Portal</strong><span style="font-family:monospace;">VIEW={view_mode}</span></header>
<div class="bar">
  <button onclick="setV('TREATY_RETENTION_VIEW')">TREATY_RETENTION_VIEW</button>
  <button onclick="setV('ASSET_HAIRCUT_VIEW')">ASSET_HAIRCUT_VIEW</button>
  <button onclick="expCsv()">Export Schedule CSV (/home/user/Downloads/sii_schedule.csv)</button>
  <button onclick="cpSeal()">Copy Active View Seal to Clipboard</button>
  <span id="msg" style="font-family:monospace;font-size:12px;">Ready</span>
</div>
<main style="padding:16px 18px;">{body}</main>
<script>
async function setV(v){{await fetch('/api/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{view:v}})}});location.reload();}}
async function expCsv(){{const r=await fetch('/api/export',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Exported ['+d.view+']';}}
async function cpSeal(){{const r=await fetch('/api/seal',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Copied seal ['+d.view+']';}}
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
        "view": "TREATY_RETENTION_VIEW",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "contention_events": 0,
    }
    write_json(state_p, pstate)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a: Any) -> None: return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec2_c06_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True})
                return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_secret:
                self.send_response(302)
                self.send_header("Set-Cookie", f"ec2_c06_sso={sso_cookie}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not self._authed():
                self._send_json(401, {"error": "Authenticated browser session required"})
                return
            with lock:
                raw = _render_sii_html(pstate["view"]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            if self.path == "/api/state":
                with lock:
                    nv = body.get("view")
                    if nv in ("TREATY_RETENTION_VIEW", "ASSET_HAIRCUT_VIEW") and nv != pstate["view"]:
                        pstate["view"] = nv
                        pstate["session_switches"] += 1
                        write_json(state_p, pstate)
                    self._send_json(200, {"ok": True, "view": pstate["view"]})
                return
            if self.path == "/api/export":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 3.2)
                dl_p = Path("/home/user/Downloads/sii_schedule.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    vw = pstate["view"]
                    if vw == "ASSET_HAIRCUT_VIEW":
                        lines = ["bond_id,asset_class,par_musd,shock_pct,admissibility"]
                        for bid, cat, par, shk, adm in ASSET_CSV_ROWS:
                            lines.append(f"{bid},{cat},{par:.2f},{shk:.5f},{adm}")
                    else:
                        lines = ["lob,tail_ldf", "AUTO_LIAB,1.250", "COMM_PROP,1.200", "CYBER_EO,1.400"]
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
                    suffix = "NET_CAP" if vw == "TREATY_RETENTION_VIEW" else "SII_SHOCK"
                    seal = make_opaque_seal("ec2_c06", f"{vw}:{suffix}")
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
    del workspace_map
    boot_p = state_dir / "boot_url"
    if boot_p.is_file():
        cfg = json.loads(boot_p.read_text(encoding="utf-8"))
        boot_p.unlink(missing_ok=True)
        u = cfg["url"]
        cmd = (
            "id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; "
            "mkdir -p /tmp/rt-studio /home/studio_ui/.config/chromium && chown -R studio_ui:studio_ui /tmp/rt-studio /home/studio_ui && "
            f"su -s /bin/bash studio_ui -c 'export DISPLAY=:99 HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/rt-studio; "
            f"nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
            f"--window-position=0,0 --window-size=940,1040 \"{u}\" >/tmp/studio_chr.log 2>&1 </dev/null &'; "
            "for _i in $(seq 1 20); do DISPLAY=:99 wmctrl -lx 2>/dev/null | grep -qi chromium && break; sleep 0.3; done; sleep 0.5"
        )
        subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=25)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    bp = ws / "board_pack"
    xp = bp / "Solvency_II_Model.xlsx"
    odt_p = bp / "Q4_Board_Brief.odt"
    pdf_a = bp / "Actuarial_Opinion.pdf"
    pdf_b = bp / "Q4_Board_Brief.pdf"

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

    pdf_a_txt = extract_pdf_text(pdf_a).replace(",", "")
    checks_a: list[tuple[str, bool, float, str]] = [
        ("lob_auto", abs(_v("IBNR_Reserve", "B2") - 92.50) <= 0.3, 0.15, f"AUTO_LIAB={_v('IBNR_Reserve','B2')} != 92.50"),
        ("lob_prop_cyber", abs(_v("IBNR_Reserve", "B3") - 68.40) <= 0.3 and abs(_v("IBNR_Reserve", "B4") - 44.10) <= 0.3, 0.20, "COMM_PROP or CYBER_EO ultimate mismatch"),
        ("ibnr_total_formula", _f("IBNR_Reserve", "B5") and abs(_v("IBNR_Reserve", "B5") - TRUE_TOTAL_IBNR_M) <= 0.5, 0.15, "IBNR_Reserve!B5 missing formula or != 205.00"),
        ("treaty_seal", _s("IBNR_Reserve", "B6") == TREATY_SEAL, 0.20, "IBNR_Reserve!B6 missing valid Treaty_Actuarial_Seal"),
        ("subdebt_bounds", abs(_v("IBNR_Reserve", "B5") - TRUE_TOTAL_IBNR_M) <= 0.5 and SUBDEBT_RANGE_M[0] <= _v("Capital_Structure", "B3") <= SUBDEBT_RANGE_M[1], 0.15, "Tier2_Subordinated_Notes_M uncalibrated or out of [38, 58]"),
        ("actuarial_pdf", pdf_a.is_file() and ("205" in pdf_a_txt), 0.15, "Actuarial_Opinion.pdf missing or lacks 205.00 IBNR"),
    ]

    deck_info = inspect_board_odt(odt_p)
    pdf_b_pages = pdf_page_count(pdf_b)
    pdf_b_txt = extract_pdf_text(pdf_b).replace(",", "")
    checks_b: list[tuple[str, bool, float, str]] = [
        ("admitted_assets", abs(_v("Asset_Portfolio", "B2") - TRUE_ADMITTED_BONDS_M) <= 0.4 and abs(_v("Asset_Portfolio", "B3") - TRUE_MARKET_HAIRCUT_M) <= 0.3 and _f("Asset_Portfolio", "B4"), 0.20, "Asset_Portfolio B2:B4 inaccurate"),
        ("asset_seal", _s("Asset_Portfolio", "B5") == ASSET_SEAL, 0.15, "Asset_Portfolio!B5 missing valid Asset_Stress_Seal"),
        ("sidecar_bounds", abs(_v("Asset_Portfolio", "B2") - TRUE_ADMITTED_BONDS_M) <= 0.4 and SIDECAR_RANGE_M[0] <= _v("Capital_Structure", "B4") <= SIDECAR_RANGE_M[1], 0.10, "Catastrophe_Sidecar_Collateral_M uncalibrated or out of [26, 46]"),
        ("odt_typography_fixed", bool(deck_info.get("ok")) and deck_info.get("section_count") == 8 and not deck_info.get("has_comic_sans"), 0.15, "Q4_Board_Brief.odt still has Comic Sans MS or != 8 sections"),
        ("odt_margins_in_bounds", bool(deck_info.get("ok")) and deck_info.get("off_canvas_frames") == 0 and bool(deck_info.get("has_rev_tag")), 0.20, "Q4_Board_Brief.odt still has >5cm off-page left margins or lost BOARD-REV9-402"),
        ("deck_pdf_8pages", pdf_b_pages >= 8 and "356.5" in pdf_b_txt, 0.20, f"Q4_Board_Brief.pdf pages={pdf_b_pages} < 8 or missing 356.50 assets"),
    ]

    rat = _v("Capital_Structure", "B6")
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("calc_desk_tag", _s("IBNR_Reserve", "C1") == CALC_DESK_TAG, 0.08, f"IBNR_Reserve!C1={_s('IBNR_Reserve','C1')!r} != {CALC_DESK_TAG!r}"),
        ("solvency_ratio_band", _f("Capital_Structure", "B5") and _f("Capital_Structure", "B6") and SOLVENCY_RATIO_BAND[0] <= rat <= SOLVENCY_RATIO_BAND[1], 0.12, f"Solvency_Coverage_Ratio={rat} outside {list(SOLVENCY_RATIO_BAND)}"),
        ("no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.05, "Open LibreOffice window held stale unsaved buffer inconsistent with disk"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.90,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    assert role in ("reserving_actuary", "investor_deck_lead")
    ws = next(iter(workspace_map.values()))
    bp = ws / "board_pack"
    xp = bp / "Solvency_II_Model.xlsx"
    odt_p = bp / "Q4_Board_Brief.odt"
    adm_p = Path("/opt/ec2_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_a = (role == "reserving_actuary")
        vw = "TREATY_RETENTION_VIEW" if is_a else "ASSET_HAIRCUT_VIEW"
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/state", data=json.dumps({"view": vw}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/export", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        seal_v = get_x11_clipboard()

        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev["IBNR_Reserve"].get("C1") or {}).get("value") or CALC_DESK_TAG)
        cur_ibnr = float((ev["IBNR_Reserve"].get("B5") or {}).get("value") or 202.0)
        cur_asset = float((ev["Asset_Portfolio"].get("B4") or {}).get("value") or 358.0)
        cur_sub = float((ev["Capital_Structure"].get("B3") or {}).get("value") or 55.0)
        cur_side = float((ev["Capital_Structure"].get("B4") or {}).get("value") or 43.0)

        tgt_own = 1.64 * SCR_FIXED_M  # 237.80 M
        if is_a:
            new_sub = round(max(SUBDEBT_RANGE_M[0], min(SUBDEBT_RANGE_M[1], tgt_own - (cur_asset - TRUE_TOTAL_IBNR_M) - cur_side)), 2)
            update_single_sheet_xlsx(xp, "IBNR_Reserve", _make_ibnr_sheet(92.50, 68.40, 44.10, desk_tag=desk_c1, seal=seal_v))
            update_single_sheet_xlsx(xp, "Capital_Structure", _make_cap_sheet(new_sub, cur_side, cur_asset, TRUE_TOTAL_IBNR_M))
            convert_doc_to_pdf_isolated(xp, bp / "Actuarial_Opinion.pdf")
        else:
            new_side = round(max(SIDECAR_RANGE_M[0], min(SIDECAR_RANGE_M[1], tgt_own - (TRUE_NET_ASSETS_M - cur_ibnr) - cur_sub)), 2)
            update_single_sheet_xlsx(xp, "Asset_Portfolio", _make_asset_sheet(TRUE_ADMITTED_BONDS_M, TRUE_MARKET_HAIRCUT_M, seal=seal_v))
            update_single_sheet_xlsx(xp, "Capital_Structure", _make_cap_sheet(cur_sub, new_side, TRUE_NET_ASSETS_M, cur_ibnr))
            rat_now = round((TRUE_NET_ASSETS_M - cur_ibnr + cur_sub + new_side) / SCR_FIXED_M, 4)
            write_board_odt(odt_p, fix_defects=True, net_assets_str="356.50", solvency_ratio_str=f"{rat_now:.4f}")
            convert_doc_to_pdf_isolated(odt_p, bp / "Q4_Board_Brief.pdf")

        reload_open_libreoffice_docs([xp, odt_p])

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (Shared-State Track): Concurrent stale-snapshot sizing undershoots Solvency II ratio (<1.62)."""
    ws = next(iter(workspace_map.values()))
    bp = ws / "board_pack"
    xp = bp / "Solvency_II_Model.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "v0.xlsx"
        shutil.copy2(xp, snap)
        solve_role("reserving_actuary", workspace_map, port, careful_conc=False)
        solve_role("investor_deck_lead", workspace_map, port, careful_conc=False)
        # Both sized against v0 simultaneously: sub=41.80, side=28.30 -> ratio=1.5283 < 1.62
        update_single_sheet_xlsx(xp, "Capital_Structure", _make_cap_sheet(41.80, 28.30, TRUE_NET_ASSETS_M, TRUE_TOTAL_IBNR_M))
        reload_open_libreoffice_docs([xp, bp / "Q4_Board_Brief.odt"])
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)

"""EC-03: 1U Sheet-Metal Enclosure FreeCAD B-Rep, Inkscape Prepress & Thermal/EMI Preload Coupling.

Contention Archetypes:
  1. Monolithic FreeCAD .FCStd ZIP & Multi-Solid STEP Assembly Lost-Update.
  2. In-Memory LibreOffice Calc Dirty Buffer vs. Disk CLI Split-Brain (Thermal_EMI_BOM.xlsx with unsaved desk ECN tag).
  4. Shared Authenticated PLM Portal (Metric mm vs NEMA mil toggle + paginated 14-row ~/Downloads/iec_enclosure_spec.csv).
  5. Bidirectional Fastener/Gasket Preload Envelope ([246.0, 252.0] Ncm) + 3D B-Rep Keepout Verification.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.exam_contention_v1.common import (
    advisory_lock,
    find_unexpected_workspace_files,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    reload_open_libreoffice_window,
    render_scanned_document_png,
    set_x11_clipboard,
    verify_prompt_driver_and_ban_clean,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "EC-03"
PORTAL_PORT = 18803
DESK_TAG = "DESK-ECN-REVC-308"
THERMAL_ECN_SEAL = make_opaque_seal("ec03", "THERMAL_CFD:IEC_60297_METRIC_MM")
EMC_ECN_SEAL = make_opaque_seal("ec03", "EMC_BULKHEAD:NEMA_IMPERIAL_MIL")
ALLOWED_ENC_FILES = {
    "chassis_housing.FCStd",
    "Thermal_EMI_BOM.xlsx",
    "Engineering_Standard_IEC.md",
    "front_bezel_silkscreen.svg",
    "release/chassis_housing.step",
    "release/front_bezel_proof.png",
    "scans/top_lid_keepout_revC.png",
    "scans/rear_io_callout.png",
}

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "1U Sheet-Metal Enclosure FreeCAD B-Rep, Inkscape Prepress & Thermal/EMI Preload Coupling",
    "domain": "Mechanical CAD, EMC Shielding & Industrial Artwork Prepress",
    "archetypes": (
        "monolithic_fcstd_zip_and_step_lost_update",
        "libreoffice_calc_dirty_buffer_split_brain",
        "shared_httponly_plm_unit_toggle_and_downloads",
        "bidirectional_fastener_preload_gasket_envelope",
    ),
    "roles": ("mech_thermal_eng", "emi_prepress_eng"),
    "portal_port": PORTAL_PORT,
    "open_gui_doc": "/workspace/enclosure_revC/Thermal_EMI_BOM.xlsx",
    "open_gui_unsaved_tag": DESK_TAG,
    "conc_role_timeout_s": 1800,
    "seq_role_timeout_s": 1800,
}

RHO_AL6061_G_MM3 = 0.00270
LID_SOLID_FULL_VOL_MM3 = 220.0 * 160.0 * 2.5   # 88,000.0 mm^3
REAR_SOLID_FULL_VOL_MM3 = 220.0 * 3.0 * 41.5   # 27,390.0 mm^3

VENT_AREA_RANGE_MM2 = (3758.0, 4600.0)   # 0.0165 * A >= 62.0 W -> A >= 3757.58 mm^2
# 6 Rear I/O cutouts (in mm):
#   2x OPT-QSFP28 (19.0 x 10.0) = 380.0 mm^2
#   2x ETH-RJ45-DUAL (32.0 x 15.0) = 960.0 mm^2
#   1x MGT-SFP-PLUS (15.0 x 10.0) = 150.0 mm^2
#   1x PWR-DC48V (16.0 x 10.0) = 160.0 mm^2
# Exact total = 1,650.0 mm^2
TRUE_IO_AREA_MM2 = 1650.0

TOP_TORQUE_RANGE_NCM = (108.0, 154.0)
REAR_PRELOAD_RANGE_NCM = (92.0, 138.0)
COMBINED_PRELOAD_BAND_NCM = (244.0, 252.0)

PLM_LIBRARY_MM: list[tuple[str, str, float, float]] = [
    ("THM-SLOT-STD", "Standard Top-Lid Convection Louver Slot", 36.0, 5.6),
    ("OPT-QSFP28", "QSFP28 Optical Transceiver Cage", 19.0, 10.0),
    ("ETH-RJ45-DUAL", "Dual-Stack Shielded RJ45 Block", 32.0, 15.0),
    ("USB-TYPEC-IND", "Industrial Retaining USB-C", 11.0, 6.5),
    ("DB9-RS232", "D-Sub 9-Pin Serial Console", 25.0, 12.5),
    ("SMA-GNSS-BLK", "Bulkhead GNSS Coax Port", 8.0, 8.0),
    ("OPT-QSFP-DD", "QSFP-DD 400G Cage", 21.5, 11.0),
    ("ETH-RJ45-QUAD", "Quad-Port RJ45 Gang", 60.0, 15.0),
    ("FAN-40MM-GRD", "40mm Fan Finger Guard", 38.0, 38.0),
    ("MGT-SFP-PLUS", "10G Management SFP+ Cage", 15.0, 10.0),
    ("BNC-10MHZ-SYNC", "10MHz Timing Reference Port", 12.0, 12.0),
    ("LED-LIGHTPIPE-4", "Quad Status Lightpipe Array", 14.0, 4.0),
    ("PWR-DC48V", "Telecom -48VDC Terminal Block", 16.0, 10.0),
    ("PWR-AC-C14", "IEC C14 AC Inlet", 28.0, 20.5),
]


FREECAD_BUILD_OR_UPDATE_PY = r"""
import json, os, sys
from pathlib import Path
for p in ("/usr/lib/freecad-python3/lib", "/usr/lib/freecad/lib"):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.append(p)
import FreeCAD, Part

fcstd_p = Path(sys.argv[1])
mode = sys.argv[2]
step_p = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None

if mode == "init":
    doc = FreeCAD.newDocument("EnclosureRevC")
    lid = doc.addObject("Part::Feature", "TopVentCover")
    lid.Shape = Part.makeBox(220.0, 160.0, 2.5, FreeCAD.Vector(0.0, 0.0, 41.5))
    rear = doc.addObject("Part::Feature", "RearIOBulkhead")
    rear.Shape = Part.makeBox(220.0, 3.0, 41.5, FreeCAD.Vector(0.0, 157.0, 0.0))
    doc.recompute()
    doc.saveAs(str(fcstd_p))
    if step_p:
        Part.export([lid, rear], str(step_p))
    print("CAD_JSON:" + json.dumps({"ok": True}), flush=True)
    os._exit(0)

doc = FreeCAD.openDocument(str(fcstd_p))
lid = doc.getObject("TopVentCover")
rear = doc.getObject("RearIOBulkhead")

if mode == "vent":
    base = Part.makeBox(220.0, 160.0, 2.5, FreeCAD.Vector(0.0, 0.0, 41.5))
    cuts = []
    for x0 in (18.0, 60.0, 124.0, 166.0):
        for r in range(5):
            y0 = 20.0 + r * 25.0
            cuts.append(Part.makeBox(36.0, 5.6, 4.0, FreeCAD.Vector(x0, y0, 41.0)))
    lid.Shape = base.cut(Part.makeCompound(cuts))
    doc.recompute()
    doc.save()
    if step_p:
        Part.export([lid, rear], str(step_p))
    print("CAD_JSON:" + json.dumps({"ok": True}), flush=True)
    os._exit(0)
elif mode == "io":
    base = Part.makeBox(220.0, 3.0, 41.5, FreeCAD.Vector(0.0, 157.0, 0.0))
    cuts = [
        Part.makeBox(19.0, 5.0, 10.0, FreeCAD.Vector(14.0, 156.0, 14.0)),
        Part.makeBox(19.0, 5.0, 10.0, FreeCAD.Vector(40.0, 156.0, 14.0)),
        Part.makeBox(32.0, 5.0, 15.0, FreeCAD.Vector(68.0, 156.0, 12.0)),
        Part.makeBox(32.0, 5.0, 15.0, FreeCAD.Vector(108.0, 156.0, 12.0)),
        Part.makeBox(15.0, 5.0, 10.0, FreeCAD.Vector(148.0, 156.0, 14.0)),
        Part.makeBox(16.0, 5.0, 10.0, FreeCAD.Vector(172.0, 156.0, 14.0)),
    ]
    rear.Shape = base.cut(Part.makeCompound(cuts))
    doc.recompute()
    doc.save()
    if step_p:
        Part.export([lid, rear], str(step_p))
    print("CAD_JSON:" + json.dumps({"ok": True}), flush=True)
    os._exit(0)
elif mode == "inspect":
    lid_vol = float(lid.Shape.Volume) if lid else -1.0
    rear_vol = float(rear.Shape.Volume) if rear else -1.0
    keepout_viol_mm3 = 0.0
    if lid:
        full_lid = Part.makeBox(220.0, 160.0, 2.5, FreeCAD.Vector(0.0, 0.0, 41.5))
        removed = full_lid.cut(lid.Shape)
        inner_ok = Part.makeBox(196.0, 136.0, 2.5, FreeCAD.Vector(12.0, 12.0, 41.5))
        perim_ko = full_lid.cut(inner_ok)
        boss_ko = Part.makeBox(16.0, 160.0, 2.5, FreeCAD.Vector(102.0, 0.0, 41.5))
        keepout_viol_mm3 = float(removed.common(perim_ko).Volume) + float(removed.common(boss_ko).Volume)
    step_ok = False
    if step_p and step_p.is_file():
        s_sh = Part.read(str(step_p))
        step_ok = abs(float(s_sh.Volume) - (lid_vol + rear_vol)) < 25.0 and len(s_sh.Solids) >= 2
    out = {
        "ok": bool(lid and rear and lid.Shape.isValid() and rear.Shape.isValid()),
        "lid_vol_mm3": round(lid_vol, 2),
        "rear_vol_mm3": round(rear_vol, 2),
        "vent_area_mm2": round((88000.0 - lid_vol) / 2.5, 2),
        "io_area_mm2": round((27390.0 - rear_vol) / 3.0, 2),
        "lid_mass_g": round(lid_vol * 0.00270, 2),
        "rear_mass_g": round(rear_vol * 0.00270, 2),
        "keepout_viol_mm3": round(keepout_viol_mm3, 3),
        "step_synced": step_ok,
    }
    print("CAD_JSON:" + json.dumps(out), flush=True)
    os._exit(0)
"""


def _run_freecad(fcstd_p: Path, mode: str, step_p: Path | None = None) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tf:
        tf.write(FREECAD_BUILD_OR_UPDATE_PY)
        sp = tf.name
    try:
        cp = subprocess.run(
            [sys.executable, sp, str(fcstd_p), mode, str(step_p or "")],
            capture_output=True,
            text=True,
            timeout=90,
        )
        for ln in cp.stdout.splitlines():
            if ln.startswith("CAD_JSON:"):
                return json.loads(ln[len("CAD_JSON:"):])
        return {"ok": cp.returncode == 0, "stderr": cp.stderr[-400:]}
    finally:
        try:
            os.unlink(sp)
        except OSError:
            pass


def _make_vent_sheet(lid_mass_g: float, vent_area_mm2: float, desk_tag: str = "", ecn_seal: str = "PENDING") -> list[list]:
    q_w = round(0.0165 * vent_area_mm2, 2)
    return [
        ["Metric", "Value", desk_tag],
        ["TopVentCover_Mass_g", round(lid_mass_g, 2), "AL6061_RHO"],
        ["Vent_Cutout_Area_mm2", round(vent_area_mm2, 2), "THERMAL_CUTOUT"],
        ["Natural_Convection_Capacity_W", ("=0.0165*B3", q_w), "IEC_CONVECTION"],
        ["PLM_Thermal_ECN_Seal", ecn_seal, "CLIPBOARD_ATTEST"],
    ]


def _make_emi_sheet(rear_mass_g: float, io_area_mm2: float, ecn_seal: str = "PENDING") -> list[list]:
    return [
        ["Metric", "Value", "Spec"],
        ["RearIOBulkhead_Mass_g", round(rear_mass_g, 2), "AL6061_RHO"],
        ["Rear_IO_Cutout_Area_mm2", round(io_area_mm2, 2), "BULKHEAD_6PORT"],
        ["EMC_6GHz_Attenuation_Margin_dB", ("=78.0-0.008*B3", round(78.0 - 0.008 * io_area_mm2, 2)), "WAVEGUIDE_MARGIN"],
        ["PLM_EMC_ECN_Seal", ecn_seal, "CLIPBOARD_ATTEST"],
    ]


def _make_joint_sheet(top_tq: float, rear_pl: float) -> list[list]:
    comb = round(top_tq + rear_pl, 2)
    return [
        ["Parameter", "Torque_Or_Preload_Ncm", "Compliance_Ref"],
        ["Top_Cover_Torque_Spec_Ncm", round(top_tq, 2), "TOP_FLANGE"],
        ["Rear_Gasket_Preload_Ncm", round(rear_pl, 2), "BECU_GASKET"],
        ["Combined_Fastener_Preload_Ncm", ("=B2+B3", comb), "FRAME_FLATNESS"],
    ]


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    mech_md = "\n".join([
        f"# Mechanical & Thermal Engineering Work Order — {b}mech_thermal_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the Rev-C top ventilation lid machining and thermal schedule for the 1U telecom chassis in {b}/workspace/enclosure_revC{b}.",
        f"The BOM/compliance workbook {b}/workspace/enclosure_revC/Thermal_EMI_BOM.xlsx{b} is currently open in LibreOffice Calc on the workstation (with an active ECN control tag in {b}Thermal_Vent_Schedule!C1{b}) alongside the Hardware PLM Portal at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/enclosure_revC/Engineering_Standard_IEC.md{b}, scanned mechanical keepout drawing {b}/workspace/enclosure_revC/scans/top_lid_keepout_revC.png{b}, and the Hardware PLM Portal ({b}http://127.0.0.1:{PORTAL_PORT}{b}).",
        f"2. Machine ventilation through-cutouts on solid {b}TopVentCover{b} in {b}/workspace/enclosure_revC/chassis_housing.FCStd{b} meeting all thermal dissipation, structural area, outer gasket keepout, and central heatsink boss keepout requirements while preserving all other solids, and export the complete multi-solid assembly to {b}/workspace/enclosure_revC/release/chassis_housing.step{b}.",
        f"3. In the PLM Portal ({b}DISCIPLINE = THERMAL_CFD{b}, {b}UNIT_SYSTEM = IEC_60297_METRIC_MM{b}), export the metric 14-item feature catalog CSV and copy the Thermal ECN Sign-Off Seal to the system clipboard for {b}Thermal_Vent_Schedule!B5{b}; populate {b}Thermal_Vent_Schedule!B2:B4{b} and size only {b}Joint_Compliance!B2{b} ({b}Top_Cover_Torque_Spec_Ncm{b}) so {b}Joint_Compliance!B4{b} satisfies the frame preload specification, preserving all sheets, formulas, and {b}Thermal_Vent_Schedule!C1{b}. Keep {b}/workspace/enclosure_revC{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])

    emi_md = "\n".join([
        f"# EMC Shielding & Silkscreen Prepress Work Order — {b}emi_prepress_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the Rev-C rear I/O bulkhead machining, conductive gasket preload, and front-bezel prepress artwork in {b}/workspace/enclosure_revC{b}.",
        f"The BOM/compliance workbook {b}/workspace/enclosure_revC/Thermal_EMI_BOM.xlsx{b} is currently open in LibreOffice Calc on the workstation (with an active ECN control tag in {b}Thermal_Vent_Schedule!C1{b}) alongside the Hardware PLM Portal at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/enclosure_revC/Engineering_Standard_IEC.md{b}, scanned rear bulkhead & artwork drawing {b}/workspace/enclosure_revC/scans/rear_io_callout.png{b}, and the complete PLM cutout specification CSV from {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        f"2. Machine all required rear bulkhead through-cutouts on solid {b}RearIOBulkhead{b} in {b}/workspace/enclosure_revC/chassis_housing.FCStd{b} while preserving all other solids, and export the complete multi-solid assembly to {b}/workspace/enclosure_revC/release/chassis_housing.step{b}.",
        f"3. Update {b}/workspace/enclosure_revC/front_bezel_silkscreen.svg{b} with all required silkscreen SVG group IDs specified in {b}scans/rear_io_callout.png{b} and render the 2x prepress proof PNG to {b}/workspace/enclosure_revC/release/front_bezel_proof.png{b} via Inkscape.",
        f"4. Per Telcordia/FCC EMC sign-off rules in {b}Engineering_Standard_IEC.md{b}, set the PLM Portal to {b}DISCIPLINE = EMC_BULKHEAD{b} and {b}UNIT_SYSTEM = NEMA_IMPERIAL_MIL{b}, copy the EMC ECN Sign-Off Seal to the system clipboard and record it in {b}EMI_Shielding_Schedule!B5{b}; populate {b}EMI_Shielding_Schedule!B2:B4{b} (metric mass/area) and size only {b}Joint_Compliance!B3{b} ({b}Rear_Gasket_Preload_Ncm{b}) so {b}Joint_Compliance!B4{b} satisfies the frame preload specification, preserving all sheets, formulas, and {b}Thermal_Vent_Schedule!C1{b}. Keep {b}/workspace/enclosure_revC{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])
    return {"mech_thermal_eng": mech_md, "emi_prepress_eng": emi_md}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    b = chr(96)
    enc = workspace / "enclosure_revC"
    (enc / "release").mkdir(parents=True, exist_ok=True)
    (enc / "scans").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    fcstd_p = enc / "chassis_housing.FCStd"
    step_p = enc / "release" / "chassis_housing.step"
    _run_freecad(fcstd_p, "init", step_p)

    (enc / "Engineering_Standard_IEC.md").write_text(
        "\n".join([
            "# IEC 60297-3-101 Rev-C — 1U Carrier Enclosure Mechanical, Thermal & EMC Standard",
            "",
            f"1. **Alloy & Native CAD Geometry ({b}chassis_housing.FCStd{b})**:",
            f"   - Alloy: Aluminum 6061-T6, density {b}rho = 0.00270 g/mm^3{b}. All CAD units are metric millimeters ({b}mm{b}).",
            f"   - Note: The PLM Portal previews only 4 of 14 library features on screen and exports all 14 items to {b}/home/gui/Downloads/iec_enclosure_spec.csv{b} in the currently active unit system ({b}IEC_60297_METRIC_MM{b} vs {b}NEMA_IMPERIAL_MIL{b}, where {b}1000 mil = 25.4 mm{b}).",
            f"   - **PLM ECN Seal Governance**: Thermal CFD sign-off seals ({b}Thermal_Vent_Schedule!B5{b}) MUST be generated under {b}DISCIPLINE = THERMAL_CFD{b} and {b}UNIT_SYSTEM = IEC_60297_METRIC_MM{b}, whereas Telcordia/NEMA EMC bulkhead sign-off seals ({b}EMI_Shielding_Schedule!B5{b}) MUST be generated under {b}DISCIPLINE = EMC_BULKHEAD{b} and {b}UNIT_SYSTEM = NEMA_IMPERIAL_MIL{b} (all CAD geometry and workbook areas/masses remain in metric {b}mm{b} / {b}mm^2{b} / {b}g{b}).",
            "",
            f"2. **TopVentCover Thermal & Structural Specification ({b}Thermal_Vent_Schedule{b})**:",
            f"   - Blank solid: {b}220.0 x 160.0 x 2.5 mm{b} ({b}Z = 41.5..44.0 mm{b}).",
            f"   - Natural convection correlation: {b}Q_conv_W = 0.0165 * Vent_Cutout_Area_mm2{b} (formula {b}=0.0165*B3{b} in {b}Thermal_Vent_Schedule!B4{b}).",
            f"   - Carrier payload requires **{b}Q_conv_W >= 62.0 W{b}** ({b}Vent_Cutout_Area_mm2 >= 3758.0 mm^2{b}), and structural deflection limits open area to **{b}<= 4600.0 mm^2{b}**.",
            f"   - Respect both no-cut keepout zones defined in {b}scans/top_lid_keepout_revC.png{b} (zero Boolean volume intersection).",
            "",
            f"3. **RearIOBulkhead EMC & Silkscreen Prepress ({b}EMI_Shielding_Schedule{b})**:",
            f"   - Blank solid: {b}220.0 x 3.0 x 41.5 mm{b} ({b}Y = 157.0..160.0 mm{b}). Machine all 6 non-overlapping rear I/O ports listed on {b}scans/rear_io_callout.png{b} completely through the 3.0 mm wall.",
            f"   - Waveguide attenuation margin formula in {b}EMI_Shielding_Schedule!B4{b}: {b}=78.0-0.008*B3{b} (must remain >= 62.0 dB).",
            f"   - Export {b}front_bezel_silkscreen.svg{b} to {b}release/front_bezel_proof.png{b} at exact 2x prepress resolution ({b}1760 x 360 px{b}).",
            "",
            f"4. **Conductive Gasket & Flange Flatness Preload Window ({b}Joint_Compliance{b})**:",
            f"   - {b}Top_Cover_Torque_Spec_Ncm{b} ({b}B2{b}): permitted range **{b}[108.0, 154.0] Ncm{b}**.",
            f"   - {b}Rear_Gasket_Preload_Ncm{b} ({b}B3{b}): permitted range **{b}[92.0, 138.0] Ncm{b}**.",
            f"   - {b}Combined_Fastener_Preload_Ncm{b} ({b}B4 = =B2+B3{b}): MUST evaluate within **{b}[244.0, 252.0] Ncm{b}**.",
            "",
        ]),
        encoding="utf-8",
    )

    render_scanned_document_png(
        enc / "scans" / "top_lid_keepout_revC.png",
        "DRAWING REV-C1: TOP VENT COVER GASKET & HEATSINK BOSS KEEPOUTS",
        [
            "Solid: TopVentCover (X: 0..220 mm, Y: 0..160 mm, Z: 41.5..44.0 mm)",
            "MANDATORY NO-CUT SOLID ZONES (0.0 mm^3 cutout intersection allowed):",
            "  1. Outer EMI Gasket Perimeter: 12.0 mm margin on all 4 outer edges",
            "     (No cutouts permitted where X < 12, X > 208, Y < 12, or Y > 148 mm)",
            "  2. Central Heatsink Standoff Spine: Full-depth strip X = 102.0..118.0 mm",
            "     across entire Y = 0..160 mm span (split vent arrays left & right).",
        ],
        stamp_text="MECH KEEPOUT REV-C",
        tilt_deg=1.6,
    )
    render_scanned_document_png(
        enc / "scans" / "rear_io_callout.png",
        "DRAWING REV-C2: REAR BULKHEAD 6-PORT SCHEDULE & BEZEL ARTWORK",
        [
            "RearIOBulkhead (Y = 157..160 mm) — Machine 6 Non-Overlapping Ports:",
            "  - Qty 2 x PLM Code OPT-QSFP28    (High-Speed Optical Uplinks)",
            "  - Qty 2 x PLM Code ETH-RJ45-DUAL (Dual-Stack Copper Trunk)",
            "  - Qty 1 x PLM Code MGT-SFP-PLUS  (Out-of-Band 10G Management)",
            "  - Qty 1 x PLM Code PWR-DC48V     (-48VDC Redundant Feed)",
            "Front Bezel SVG Prepress (880x180 -> export 1760x360 PNG):",
            "  Include these three non-empty <g> group IDs in front_bezel_silkscreen.svg:",
            "    1) id=\"iec-emc-class-a-badge\"",
            "    2) id=\"port-legend-qsfp\"",
            "    3) id=\"thermal-airflow-notice\"",
        ],
        stamp_text="EMC & PREPRESS REV-C",
        tilt_deg=-1.7,
    )

    (enc / "front_bezel_silkscreen.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="180" viewBox="0 0 880 180">\n'
        '  <rect width="880" height="180" fill="#1e293b"/>\n'
        '  <text x="24" y="42" fill="#f8fafc" font-family="monospace" font-size="18">ATLAS-1U TELECOM CARRIER</text>\n'
        '</svg>\n',
        encoding="utf-8",
    )

    write_multisheet_xlsx(
        enc / "Thermal_EMI_BOM.xlsx",
        [
            ("Thermal_Vent_Schedule", _make_vent_sheet(LID_SOLID_FULL_VOL_MM3 * RHO_AL6061_G_MM3, 0.0, desk_tag="", ecn_seal="PENDING")),
            ("EMI_Shielding_Schedule", _make_emi_sheet(REAR_SOLID_FULL_VOL_MM3 * RHO_AL6061_G_MM3, 0.0, ecn_seal="PENDING")),
            ("Joint_Compliance", _make_joint_sheet(148.0, 134.0)),
        ],
    )

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_plm_html(unit_mode: str, discipline: str, view_tab: str = "CATALOG") -> str:
    is_mil = (unit_mode == "NEMA_IMPERIAL_MIL")
    u_lbl = "mil (0.001 in)" if is_mil else "mm (IEC Metric)"
    mult = (1000.0 / 25.4) if is_mil else 1.0
    rows = "".join(
        f"<tr><td>{code}</td><td>{desc}</td><td>{w * mult:.2f}</td><td>{h * mult:.2f}</td></tr>"
        for code, desc, w, h in PLM_LIBRARY_MM[:4]
    )
    if view_tab == "DRAWINGS":
        body_main = (
            "<h3>Authenticated Rev-C Scanned Engineering Drawings</h3>"
            "<p><img src='/scans/top_lid_keepout_revC.png' style='max-width:860px;border:1px solid #94a3b8;margin-bottom:10px;' /></p>"
            "<p><img src='/scans/rear_io_callout.png' style='max-width:860px;border:1px solid #94a3b8;' /></p>"
        )
    else:
        body_main = (
            f"<h3>Standard Cutout Catalog — Previewing 4 of {len(PLM_LIBRARY_MM)} Items ({u_lbl})</h3>"
            f"<p style='font-size:13px;color:#334155;'>Click <strong>Export Full 14-Item Spec CSV</strong> to download all {len(PLM_LIBRARY_MM)} connector and power cutout specifications in the active unit system.</p>"
            f"<table><thead><tr><th>PLM Code</th><th>Description</th><th>Width ({u_lbl})</th><th>Height ({u_lbl})</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>IEC 60297 Mechanical & EMC PLM Portal</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    header {{ background: #0f172a; color: #f8fafc; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }}
    .badge {{ background: #0369a1; padding: 4px 10px; border-radius: 4px; font-family: monospace; }}
    .toolbar {{ background: #e2e8f0; padding: 10px 20px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    button {{ background: #ffffff; border: 1px solid #475569; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-weight: 600; }}
    button.active {{ background: #0f172a; color: #ffffff; }}
    main {{ padding: 20px; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; margin-top: 10px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; font-size: 13px; }}
    th {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <header>
    <div><strong>Atlas Hardware PLM — 1U Enclosure Standard Feature Library</strong></div>
    <div class="badge" id="plm-banner">DISCIPLINE={discipline} | UNIT_SYSTEM={unit_mode}</div>
  </header>
  <div class="toolbar">
    <strong>Discipline:</strong>
    <button class="{'active' if discipline == 'THERMAL_CFD' else ''}" onclick="setPlm({{discipline:'THERMAL_CFD'}})">THERMAL_CFD</button>
    <button class="{'active' if discipline == 'EMC_BULKHEAD' else ''}" onclick="setPlm({{discipline:'EMC_BULKHEAD'}})">EMC_BULKHEAD</button>
    <strong>Dimension Unit System:</strong>
    <button class="{'active' if unit_mode == 'IEC_60297_METRIC_MM' else ''}" onclick="setPlm({{unit_mode:'IEC_60297_METRIC_MM'}})">IEC_60297_METRIC_MM</button>
    <button class="{'active' if unit_mode == 'NEMA_IMPERIAL_MIL' else ''}" onclick="setPlm({{unit_mode:'NEMA_IMPERIAL_MIL'}})">NEMA_IMPERIAL_MIL</button>
    <button class="{'active' if view_tab == 'CATALOG' else ''}" onclick="setPlm({{view_tab:'CATALOG'}})">Catalog (4/14)</button>
    <button class="{'active' if view_tab == 'DRAWINGS' else ''}" onclick="setPlm({{view_tab:'DRAWINGS'}})">Drawings (2 Scans)</button>
    <button onclick="expPlm()">Export Full 14-Item Spec CSV (/home/gui/Downloads/iec_enclosure_spec.csv)</button>
    <button onclick="copyEcn()">Copy ECN Sign-Off Seal to Clipboard</button>
    <span id="msg" style="font-family:monospace;font-size:12px;color:#0369a1;">Ready</span>
  </div>
  <main>
    {body_main}
  </main>
  <script>
    async function setPlm(p) {{
      const r = await fetch('/api/plm/state', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(p)}});
      if (r.ok) window.location.reload();
    }}
    async function expPlm() {{
      document.getElementById('msg').textContent = 'Exporting 14-item PLM catalog...';
      const r = await fetch('/api/plm/export_csv', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Saved 14 items [' + d.unit_mode + ']') : 'Error';
    }}
    async function copyEcn() {{
      const r = await fetch('/api/plm/copy_seal', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Copied ECN seal [' + d.discipline + '/' + d.unit_mode + ']') : 'Error';
    }}
  </script>
</body>
</html>
"""


def run_portal_service(port: int, workspace: Path, state_dir: Path, boot_file: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "discipline": "THERMAL_CFD",
        "unit_mode": "NEMA_IMPERIAL_MIL",
        "view_tab": "CATALOG",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
    }

    def persist() -> None:
        write_json(state_p, pstate)

    persist()

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
                m = c.get("ec03_plm_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True, "task_id": TASK_ID})
                return
            if parsed.path == "/":
                qs = parse_qs(parsed.query)
                if (qs.get("sso_boot") or [""])[0] == boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"ec03_plm_sso={sso_cookie}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated PLM session required"})
                    return
                with lock:
                    html = _render_plm_html(pstate["unit_mode"], pstate["discipline"], pstate["view_tab"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path.startswith("/scans/"):
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated PLM session required"})
                    return
                fn = Path(parsed.path).name
                fp = workspace / "enclosure_revC" / "scans" / fn
                if fp.is_file() and fp.suffix == ".png":
                    raw_png = fp.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(raw_png)))
                    self.end_headers()
                    self.wfile.write(raw_png)
                    return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self._authed():
                self._send_json(401, {"error": "Authenticated PLM session required"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            except Exception:
                body = {}

            if parsed.path == "/api/plm/state":
                with lock:
                    changed = False
                    if body.get("discipline") in ("THERMAL_CFD", "EMC_BULKHEAD"):
                        if pstate["discipline"] != body["discipline"]:
                            changed = True
                        pstate["discipline"] = body["discipline"]
                    if body.get("unit_mode") in ("IEC_60297_METRIC_MM", "NEMA_IMPERIAL_MIL"):
                        if pstate["unit_mode"] != body["unit_mode"]:
                            changed = True
                        pstate["unit_mode"] = body["unit_mode"]
                    if body.get("view_tab") in ("CATALOG", "DRAWINGS"):
                        if pstate["view_tab"] != body["view_tab"]:
                            changed = True
                        pstate["view_tab"] = body["view_tab"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "discipline": pstate["discipline"], "unit_mode": pstate["unit_mode"]})
                return

            if parsed.path == "/api/plm/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.4 if is_adm else 4.2)
                dl_p = Path("/home/gui/Downloads/iec_enclosure_spec.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    um = pstate["unit_mode"]
                    mult = (1000.0 / 25.4) if um == "NEMA_IMPERIAL_MIL" else 1.0
                    lines = ["plm_code,description,width,height"]
                    for code, desc, w, h in PLM_LIBRARY_MM:
                        lines.append(f"{code},{desc},{w * mult:.2f},{h * mult:.2f}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "path": str(dl_p), "unit_mode": um})
                return

            if parsed.path == "/api/plm/copy_seal":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 1.5)
                with lock:
                    disc = pstate["discipline"]
                    um = pstate["unit_mode"]
                    seal = make_opaque_seal("ec03", f"{disc}:{um}")
                    pstate["clipboard_copies"] += 1
                    persist()
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "discipline": disc, "unit_mode": um})
                return

            self._send_json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def grade(workspace: Path, service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image
    enc = workspace / "enclosure_revC"
    fcstd_p = enc / "chassis_housing.FCStd"
    step_p = enc / "release" / "chassis_housing.step"
    svg_p = enc / "front_bezel_silkscreen.svg"
    proof_p = enc / "release" / "front_bezel_proof.png"
    xp = enc / "Thermal_EMI_BOM.xlsx"

    errs_a: list[str] = []
    errs_b: list[str] = []
    errs_joint: list[str] = []

    cad = _run_freecad(fcstd_p, "inspect", step_p) if fcstd_p.is_file() else {"ok": False}
    if not cad.get("ok"):
        errs_joint.append(f"Invalid chassis_housing.FCStd: {cad}")
    else:
        va = float(cad.get("vent_area_mm2", 0.0))
        ia = float(cad.get("io_area_mm2", 0.0))
        kv = float(cad.get("keepout_viol_mm3", 0.0))
        if not (VENT_AREA_RANGE_MM2[0] <= va <= VENT_AREA_RANGE_MM2[1]):
            errs_a.append(f"TopVentCover vent_area_mm2={va} outside {list(VENT_AREA_RANGE_MM2)}")
        if kv > 0.5:
            errs_a.append(f"TopVentCover cutouts violate gasket or central heatsink keepout by {kv} mm3")
        if abs(ia - TRUE_IO_AREA_MM2) > 25.0:
            errs_b.append(f"RearIOBulkhead io_area_mm2={ia} != {TRUE_IO_AREA_MM2} +- 25")
        if not cad.get("step_synced"):
            errs_joint.append("release/chassis_housing.step missing or out of sync with live .FCStd")

    svg_txt = svg_p.read_text(encoding="utf-8", errors="replace") if svg_p.is_file() else ""
    for req_id in ("iec-emc-class-a-badge", "port-legend-qsfp", "thermal-airflow-notice"):
        if f'id="{req_id}"' not in svg_txt and f"id='{req_id}'" not in svg_txt:
            errs_b.append(f"front_bezel_silkscreen.svg missing #{req_id}")
    if not (proof_p.is_file() and proof_p.stat().st_size > 1500):
        errs_b.append("release/front_bezel_proof.png missing or invalid")
    else:
        try:
            with Image.open(proof_p) as im:
                if im.size != (1760, 360):
                    errs_b.append(f"front_bezel_proof.png dimensions={im.size} != (1760, 360)")
        except Exception as exc:
            errs_b.append(f"Invalid PNG proof: {exc}")

    if not xp.is_file():
        errs_joint.append("Missing Thermal_EMI_BOM.xlsx")
    else:
        try:
            raw_sh = read_multisheet_xlsx(xp)
            ev_sh = evaluate_xlsx_via_libreoffice(xp)

            def _v(sh: str, ref: str) -> float:
                val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
                return float(val) if isinstance(val, (int, float)) else -9999.0

            def _s(sh: str, ref: str) -> str:
                val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
                return str(val or "").strip()

            def _f(sh: str, ref: str) -> bool:
                return bool(((raw_sh.get(sh) or {}).get(ref) or {}).get("formula"))

            if _s("Thermal_Vent_Schedule", "C1") != DESK_TAG:
                errs_joint.append(f"Thermal_Vent_Schedule!C1 lost live Calc ECN tag ({_s('Thermal_Vent_Schedule', 'C1')!r} != {DESK_TAG!r})")
            if _s("Thermal_Vent_Schedule", "B5") != THERMAL_ECN_SEAL:
                errs_a.append("Thermal_Vent_Schedule!B5 missing valid PLM_Thermal_ECN_Seal")
            if _s("EMI_Shielding_Schedule", "B5") != EMC_ECN_SEAL:
                errs_b.append("EMI_Shielding_Schedule!B5 missing valid PLM_EMC_ECN_Seal")
            if cad.get("ok"):
                if abs(_v("Thermal_Vent_Schedule", "B2") - float(cad["lid_mass_g"])) > 1.5:
                    errs_a.append("Thermal_Vent_Schedule!B2 lid mass mismatch")
                if abs(_v("Thermal_Vent_Schedule", "B3") - float(cad["vent_area_mm2"])) > 5.0 or not _f("Thermal_Vent_Schedule", "B4"):
                    errs_a.append("Thermal_Vent_Schedule!B3/B4 area or convection formula invalid")
                if abs(_v("EMI_Shielding_Schedule", "B2") - float(cad["rear_mass_g"])) > 1.5:
                    errs_b.append("EMI_Shielding_Schedule!B2 rear mass mismatch")
                if abs(_v("EMI_Shielding_Schedule", "B3") - float(cad["io_area_mm2"])) > 5.0 or not _f("EMI_Shielding_Schedule", "B4"):
                    errs_b.append("EMI_Shielding_Schedule!B3/B4 area or attenuation formula invalid")

            tq = _v("Joint_Compliance", "B2")
            pl = _v("Joint_Compliance", "B3")
            cb = _v("Joint_Compliance", "B4")
            if not (TOP_TORQUE_RANGE_NCM[0] <= tq <= TOP_TORQUE_RANGE_NCM[1]):
                errs_a.append(f"Top_Cover_Torque={tq} outside {list(TOP_TORQUE_RANGE_NCM)}")
            if not (REAR_PRELOAD_RANGE_NCM[0] <= pl <= REAR_PRELOAD_RANGE_NCM[1]):
                errs_b.append(f"Rear_Gasket_Preload={pl} outside {list(REAR_PRELOAD_RANGE_NCM)}")
            if not _f("Joint_Compliance", "B4") or not (COMBINED_PRELOAD_BAND_NCM[0] <= cb <= COMBINED_PRELOAD_BAND_NCM[1]):
                errs_joint.append(f"Combined_Fastener_Preload={cb} outside {list(COMBINED_PRELOAD_BAND_NCM)} or missing formula")
        except Exception as exc:
            errs_joint.append(f"Workbook evaluation error: {exc}")

    if service_state.get("open_gui_split_brain") is True:
        errs_joint.append("Open LibreOffice Calc window held stale unsaved buffer inconsistent with disk")
    extra_files = find_unexpected_workspace_files(enc, ALLOWED_ENC_FILES)
    if extra_files:
        errs_joint.append(f"Unexpected scratch/coordination files in /workspace/enclosure_revC: {extra_files[:5]}")

    pass_a = len(errs_a) == 0 and len(errs_joint) == 0
    pass_b = len(errs_b) == 0 and len(errs_joint) == 0
    return {
        "task_id": TASK_ID,
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": pass_a and pass_b,
        "errors_a": errs_a,
        "errors_b": errs_b,
        "errors_joint": errs_joint,
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_driver_and_ban_clean(build_tickets_by_role()),
        "telemetry": service_state,
    }


def solve_role(role: str, workspace: Path, port: int, careful_conc: bool = False) -> None:
    assert role in ("mech_thermal_eng", "emi_prepress_eng")
    enc = workspace / "enclosure_revC"
    fcstd_p = enc / "chassis_housing.FCStd"
    step_p = enc / "release" / "chassis_housing.step"
    svg_p = enc / "front_bezel_silkscreen.svg"
    proof_p = enc / "release" / "front_bezel_proof.png"
    xp = enc / "Thermal_EMI_BOM.xlsx"
    adm_p = Path("/opt/ec_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_m = (role == "mech_thermal_eng")
        disc = "THERMAL_CFD" if is_m else "EMC_BULKHEAD"
        um_req = "IEC_60297_METRIC_MM" if is_m else "NEMA_IMPERIAL_MIL"
        urllib.request.urlopen(
            urllib.request.Request(
                f"{base}/api/plm/state",
                data=json.dumps({"discipline": disc, "unit_mode": um_req}).encode("utf-8"),
                headers={"Content-Type": "application/json", **adm_hdr},
                method="POST",
            ),
            timeout=10,
        ).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/plm/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/plm/copy_seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        ecn_seal = get_x11_clipboard()

        _run_freecad(fcstd_p, "vent" if is_m else "io", step_p)
        cad = _run_freecad(fcstd_p, "inspect", step_p)

        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev["Thermal_Vent_Schedule"].get("C1") or {}).get("value") or DESK_TAG)
        cur_tq = float((ev["Joint_Compliance"].get("B2") or {}).get("value") or 148.0)
        cur_pl = float((ev["Joint_Compliance"].get("B3") or {}).get("value") or 134.0)

        if is_m:
            tgt_p = 248.0
            new_tq = round(max(TOP_TORQUE_RANGE_NCM[0], min(TOP_TORQUE_RANGE_NCM[1], tgt_p - cur_pl)), 2)
            update_single_sheet_xlsx(xp, "Thermal_Vent_Schedule", _make_vent_sheet(float(cad["lid_mass_g"]), float(cad["vent_area_mm2"]), desk_tag=desk_c1, ecn_seal=ecn_seal))
            update_single_sheet_xlsx(xp, "Joint_Compliance", _make_joint_sheet(new_tq, cur_pl))
        else:
            tgt_p = 248.0
            new_pl = round(max(REAR_PRELOAD_RANGE_NCM[0], min(REAR_PRELOAD_RANGE_NCM[1], tgt_p - cur_tq)), 2)
            update_single_sheet_xlsx(xp, "EMI_Shielding_Schedule", _make_emi_sheet(float(cad["rear_mass_g"]), float(cad["io_area_mm2"]), ecn_seal=ecn_seal))
            update_single_sheet_xlsx(xp, "Joint_Compliance", _make_joint_sheet(cur_tq, new_pl))
            svg_p.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="180" viewBox="0 0 880 180">\n'
                '  <rect width="880" height="180" fill="#1e293b"/>\n'
                '  <text x="24" y="42" fill="#f8fafc" font-family="monospace" font-size="18">ATLAS-1U TELECOM CARRIER</text>\n'
                '  <g id="iec-emc-class-a-badge"><rect x="640" y="20" width="210" height="36" fill="#0284c7"/><text x="652" y="44" fill="#fff" font-size="14">IEC EMC CLASS A</text></g>\n'
                '  <g id="port-legend-qsfp"><text x="24" y="110" fill="#94a3b8" font-size="13">J1-J2 QSFP28 | J3-J4 RJ45 | MGT SFP+ | -48VDC</text></g>\n'
                '  <g id="thermal-airflow-notice"><text x="24" y="148" fill="#38bdf8" font-size="12">FRONT-TO-REAR CONVECTION — DO NOT BLOCK</text></g>\n'
                '</svg>\n',
                encoding="utf-8",
            )
            subprocess.run(["inkscape", str(svg_p), "--export-filename=" + str(proof_p), "--export-width=1760", "--export-height=360"], check=True, capture_output=True, timeout=30)

        reload_open_libreoffice_window(xp)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_naive_race(workspace: Path, port: int) -> None:
    enc = workspace / "enclosure_revC"
    fcstd_p = enc / "chassis_housing.FCStd"
    step_p = enc / "release" / "chassis_housing.step"
    xp = enc / "Thermal_EMI_BOM.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "v0.FCStd"
        snap.write_bytes(fcstd_p.read_bytes())
        solve_role("mech_thermal_eng", workspace, port, careful_conc=False)
        fcstd_p.write_bytes(snap.read_bytes())
        _run_freecad(fcstd_p, "io", step_p)
        update_single_sheet_xlsx(xp, "Joint_Compliance", _make_joint_sheet(110.8, 94.8))

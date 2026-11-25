"""NF2-07: Singleton Inkscape 1.2 (`org.inkscape.Inkscape` D-Bus) Dual-SVG Contention — Litho OPC Reticle vs. Microfluidic Mixer."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
import subprocess
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    inspect_live_x11_window_titles_readonly,
    launch_chromium_natural,
    launch_inkscape_gui_natural,
    make_canary_code,
    read_json_safe,
    write_json,
    write_multipage_sop_pdf,
)

TASK_ID = "NF2-07"
PORTAL_PORT = 19607

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Singleton `Inkscape 1.2` (`org.inkscape.Inkscape` D-Bus) Dual-SVG Contention: Litho OPC Reticle vs. Microfluidic Chip",
    "domain": "Semiconductor Photomask OPC (`Inkscape 1.2` SVG + CD-SEM) & MEMS Microfluidic Hydraulics (`Inkscape` + Rheology)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("litho_opc_engineer", "microfluidic_channel_designer"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

OPC_FAB_CODE = make_canary_code("EUV-OPC", "metal1-hammerhead-28nm")
MEMS_CHIP_CODE = make_canary_code("MEMS-PDMS", "dean-serpentine-40um")


def _generate_cd_sem_rows() -> list[dict[str, Any]]:
    rows = []
    for i in range(1, 361):
        r_mm = round(12.0 + (i % 15) * 9.5, 1)
        flare_pct = 3.2 if r_mm < 95.0 else 5.8
        # Raw CD in nm; edge-exclusion zone radius > 142.0 mm ( wafer bevel ) must be excluded!
        cd_nm = round(28.0 + 0.45 * math.sin(i * 0.29) + 0.22 * flare_pct, 3)
        rows.append({
            "site_id": i, "wafer_radius_mm": r_mm, "local_flare_pct": flare_pct,
            "measured_cd_nm": cd_nm, "focus_lock": "OK" if (i % 29 != 0) else "DEFOCUS_ABORT",
        })
    return rows


def _generate_channel_segments() -> list[dict[str, Any]]:
    # Rectangular PDMS microchannel hydraulic resistance: R_h = (12 * mu * L) / (w * h^3 * (1 - 0.630 * (h/w))) for h < w!
    segs = [
        ("INLET_A", 4.5e-3, 120e-6, 40e-6),
        ("INLET_B", 4.5e-3, 120e-6, 40e-6),
        ("DROPLET_NOZZLE", 1.2e-3, 65e-6, 40e-6),
        ("SERPENTINE_1", 18.0e-3, 100e-6, 40e-6),
        ("SERPENTINE_2", 18.0e-3, 100e-6, 40e-6),
        ("DEAN_LOOP", 12.0e-3, 90e-6, 40e-6),
        ("DELAY_CHAMBER", 8.0e-3, 200e-6, 40e-6),
        ("OUTLET_COLLECT", 5.0e-3, 140e-6, 40e-6),
    ]
    # Parallel inlet branch (INLET_A || INLET_B -> 0.5 * R_inlet), followed in series by remaining 6 segments!
    return [{"seg_order": idx + 1, "seg_id": sid, "topology": "PARALLEL_PAIR" if sid.startswith("INLET_") else "SERIES", "length_m": l_m, "width_m": w_m, "height_m": h_m} for idx, (sid, l_m, w_m, h_m) in enumerate(segs)]


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    # Role A: Exclude DEFOCUS_ABORT & wafer_radius_mm > 142.0 mm (edge_exclusion_mm=142.0 in SQLite) & subtract flare bias (0.22 nm per % flare)!
    crows = [r for r in _generate_cd_sem_rows() if r["focus_lock"] == "OK" and r["wafer_radius_mm"] <= 142.0]
    corr_cds = [r["measured_cd_nm"] - 0.22 * r["local_flare_pct"] for r in crows]
    mu_cd = sum(corr_cds) / len(corr_cds)
    sig_cd = math.sqrt(sum((x - mu_cd) ** 2 for x in corr_cds) / (len(corr_cds) - 1))
    or_a = {
        "valid_die_site_count": len(crows),
        "mean_flare_corrected_cd_nm": round(mu_cd, 4),
        "cd_3sigma_uniformity_nm": round(3.0 * sig_cd, 4),
        "opc_fab_code": OPC_FAB_CODE,
    }

    # Role B: Dynamic viscosity at 37.0 C lab incubator = 0.00089 Pa*s (in SQLite fluid_properties; vs 0.00100 Pa*s at 20C!)
    mu_pa_s = 0.00089
    segs = _generate_channel_segments()
    r_map: dict[str, float] = {}
    for s in segs:
        h, w, ln = s["height_m"], s["width_m"], s["length_m"]
        rh = (12.0 * mu_pa_s * ln) / (w * (h ** 3) * (1.0 - 0.630 * (h / w)))
        r_map[s["seg_id"]] = rh
    r_tot = (1.0 / (1.0 / r_map["INLET_A"] + 1.0 / r_map["INLET_B"])) + sum(v for k, v in r_map.items() if not k.startswith("INLET_"))
    q_m3_s = (15.0 * 1e-9) / 60.0  # 15.0 uL/min syringe flow -> m^3/s
    dp_kpa = (r_tot * q_m3_s) / 1000.0
    or_b = {
        "total_network_resistance_pa_s_m3": round(r_tot, 2),
        "syringe_pressure_drop_kpa": round(dp_kpa, 3),
        "mems_chip_code": MEMS_CHIP_CODE,
    }
    return or_a, or_b


OPC_ORACLE, MEMS_ORACLE = _compute_oracles()

PORTAL_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Cleanroom Photomask & MEMS CAD Spec</title>
<style>body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace} .card{background:#1e293b;padding:16px;border:1px solid #334155;margin-top:12px}</style></head><body>
<h2>Cleanroom Foundry CAD Release Portal</h2>
<div class="card">
  <h3>Layer Metal-1 OPC Reticle (`reticle_metal1_opc.svg`)</h3>
  <p>In Inkscape, remove defect element <code>#alignment_scrap_blob</code>, widen both <code>#opc_serif_left</code> and <code>#opc_serif_right</code> to <code>width="36"</code>, save SVG, and export <code>512x512</code> PNG `/workspace/exports/reticle_opc_verified.png`.</p>
  <p>OPC Fab Release Code: <strong style="color:#4ade80">__OPC__</strong></p>
</div>
<div class="card">
  <h3>PDMS Droplet Serpentine Chip (`droplet_mixer_chip.svg`)</h3>
  <p>In Inkscape, remove blocked element <code>#clogged_shunt_trace</code>, set <code>#nozzle_throat_path</code> attribute/style stroke-width to <code>14</code>, save SVG, and export <code>600x400</code> PNG `/workspace/exports/mixer_chip_verified.png`.</p>
  <p>MEMS Foundry Code: <strong style="color:#38bdf8">__MEMS__</strong></p>
</div>
</body></html>""".replace("__OPC__", OPC_FAB_CODE).replace("__MEMS__", MEMS_CHIP_CODE)


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Metal-1 OPC Reticle SVG & Wafer CD-SEM Uniformity (`litho_opc_engineer`)",
        "",
        "## Objective",
        f"Update `{b}/workspace/cad/reticle_metal1_opc.svg{b}` in **Inkscape 1.2** per `http://127.0.0.1:{PORTAL_PORT}/foundry` (exporting `{b}/workspace/exports/reticle_opc_verified.png{b}`), analyze `{b}/workspace/metrology/cd_sem_wafer.sqlite{b}` per `{b}/workspace/docs/SOP_OPC_CD.pdf{b}`, and write `{b}/workspace/opc_cd_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — PDMS Droplet Mixer SVG & Microchannel Hydraulic Drop (`microfluidic_channel_designer`)",
        "",
        "## Objective",
        f"Update `{b}/workspace/cad/droplet_mixer_chip.svg{b}` in **Inkscape 1.2** per `http://127.0.0.1:{PORTAL_PORT}/foundry` (exporting `{b}/workspace/exports/mixer_chip_verified.png{b}`), analyze `{b}/workspace/fluidics/channel_rheology.sqlite{b}` per `{b}/workspace/docs/SOP_MEMS_Fluidics.pdf{b}`, and write `{b}/workspace/microfluidic_drop_audit.json{b}`.",
    ])
    return {"litho_opc_engineer": ta, "microfluidic_channel_designer": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["litho_opc_engineer"]
    ws_b = workspace_map["microfluidic_channel_designer"]
    for d in (ws_a / "cad", ws_a / "exports", ws_a / "metrology", ws_a / "docs", ws_b / "cad", ws_b / "exports", ws_b / "fluidics", ws_b / "docs"):
        d.mkdir(parents=True, exist_ok=True)

    (ws_a / "cad/reticle_metal1_opc.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<rect width="512" height="512" fill="#0b1120"/>'
        '<rect id="main_bus_bar" x="196" y="80" width="120" height="352" fill="#38bdf8"/>'
        '<rect id="opc_serif_left" x="176" y="80" width="18" height="36" fill="#38bdf8"/>'
        '<rect id="opc_serif_right" x="318" y="80" width="18" height="36" fill="#38bdf8"/>'
        '<circle id="alignment_scrap_blob" cx="256" cy="256" r="90" fill="#ef4444"/>'
        '</svg>\n',
        encoding="utf-8",
    )
    (ws_b / "cad/droplet_mixer_chip.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">'
        '<rect width="600" height="400" fill="#091510"/>'
        '<path id="nozzle_throat_path" d="M 60 200 L 540 200" stroke="#22c55e" stroke-width="6" fill="none"/>'
        '<rect id="clogged_shunt_trace" x="180" y="110" width="240" height="180" fill="#dc2626"/>'
        '</svg>\n',
        encoding="utf-8",
    )

    with sqlite3.connect(str(ws_a / "metrology/cd_sem_wafer.sqlite")) as conn:
        conn.execute("CREATE TABLE cd_sites (site_id INTEGER PRIMARY KEY, wafer_radius_mm REAL, local_flare_pct REAL, measured_cd_nm REAL, focus_lock TEXT)")
        for r in _generate_cd_sem_rows():
            conn.execute("INSERT INTO cd_sites VALUES (?,?,?,?,?)", (r["site_id"], r["wafer_radius_mm"], r["local_flare_pct"], r["measured_cd_nm"], r["focus_lock"]))
        conn.execute("CREATE TABLE scanner_wafer_rules (bevel_edge_exclusion_radius_mm REAL, flare_cd_slope_nm_per_pct REAL)")
        conn.execute("INSERT INTO scanner_wafer_rules VALUES (142.0, 0.22)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_OPC_CD.pdf", "SOP-LITHO-707A: OPC Reticle Proofing & Flare-Corrected CD", [
        ("1. SVG Reticle & 300mm Wafer CD-SEM Rules", [
            "1.1 Complete the Inkscape updates on reticle_metal1_opc.svg and export 512x512 /workspace/exports/reticle_opc_verified.png.",
            "1.2 Filter /workspace/metrology/cd_sem_wafer.sqlite to valid in-focus interior wafer sites (respecting scanner bevel exclusion and flare-slope rules in SQLite), and compute mean_flare_corrected_cd_nm and 3*sigma (sample ddof=1) cd_3sigma_uniformity_nm.",
        ]),
        ("2. JSON Schema (/workspace/opc_cd_audit.json)", [
            "Keys: valid_die_site_count (int), mean_flare_corrected_cd_nm (float, 4 dec), cd_3sigma_uniformity_nm (float, 4 dec), opc_fab_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "fluidics/channel_rheology.sqlite")) as conn:
        conn.execute("CREATE TABLE microchannels (seg_order INTEGER PRIMARY KEY, seg_id TEXT, topology TEXT, length_m REAL, width_m REAL, height_m REAL)")
        for r in _generate_channel_segments():
            conn.execute("INSERT INTO microchannels VALUES (?,?,?,?,?,?)", (r["seg_order"], r["seg_id"], r["topology"], r["length_m"], r["width_m"], r["height_m"]))
        conn.execute("CREATE TABLE assay_operating_conditions (temp_c REAL, dynamic_viscosity_pa_s REAL, total_syringe_flow_ul_min REAL, aspect_correction_formula TEXT)")
        conn.execute("INSERT INTO assay_operating_conditions VALUES (37.0, 0.00089, 15.0, 'R_h = 12*mu*L / (w * h^3 * (1 - 0.630*(h/w)))')")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_MEMS_Fluidics.pdf", "SOP-MEMS-707B: Droplet Chip SVG & Rectangular Poiseuille Network", [
        ("1. SVG Layout & Equivalent Hydraulic Network", [
            "1.1 Complete the Inkscape updates on droplet_mixer_chip.svg and export 600x400 /workspace/exports/mixer_chip_verified.png.",
            "1.2 Compute equivalent hydraulic resistance (Pa*s/m^3) across the parallel inlet pair + series downstream microchannels in /workspace/fluidics/channel_rheology.sqlite under assay operating conditions, and compute pressure drop in kPa.",
        ]),
        ("2. JSON Schema (/workspace/microfluidic_drop_audit.json)", [
            "Keys: total_network_resistance_pa_s_m3 (float, 2 dec), syringe_pressure_drop_kpa (float, 3 dec), mems_chip_code (str).",
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
                raw = b"<html><body><script>location.href='/foundry';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"fnd_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "fnd_sso" not in c or c["fnd_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            raw = PORTAL_HTML.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or META["roles"])
    svgs = []
    if "litho_opc_engineer" in roles:
        svgs.append(workspace_map["litho_opc_engineer"] / "cad/reticle_metal1_opc.svg")
    if "microfluidic_channel_designer" in roles:
        svgs.append(workspace_map["microfluidic_channel_designer"] / "cad/droplet_mixer_chip.svg")
    launch_inkscape_gui_natural(svgs)
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    from PIL import Image
    del active_roles
    ws_a = workspace_map["litho_opc_engineer"]
    ws_b = workspace_map["microfluidic_channel_designer"]
    ja = read_json_safe(ws_a / "opc_cd_audit.json")
    jb = read_json_safe(ws_b / "microfluidic_drop_audit.json")
    titles = inspect_live_x11_window_titles_readonly()

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    svg_a_txt = (ws_a / "cad/reticle_metal1_opc.svg").read_text(errors="ignore") if (ws_a / "cad/reticle_metal1_opc.svg").is_file() else ""
    svg_b_txt = (ws_b / "cad/droplet_mixer_chip.svg").read_text(errors="ignore") if (ws_b / "cad/droplet_mixer_chip.svg").is_file() else ""

    serif_ok = False
    try:
        ra = ET.fromstring(svg_a_txt)
        wmap = {el.attrib.get("id", ""): float(el.attrib.get("width", "0")) for el in ra.iter() if "id" in el.attrib}
        serif_ok = ("alignment_scrap_blob" not in wmap) and abs(wmap.get("opc_serif_left", 0) - 36.0) <= 0.5 and abs(wmap.get("opc_serif_right", 0) - 36.0) <= 0.5
    except Exception:
        pass

    throat_ok = ("clogged_shunt_trace" not in svg_b_txt) and ('stroke-width="14"' in svg_b_txt or "stroke-width:14" in svg_b_txt)

    png_a_ok = False
    if (ws_a / "exports/reticle_opc_verified.png").is_file():
        with Image.open(ws_a / "exports/reticle_opc_verified.png") as im:
            rgb = im.convert("RGB")
            r_c, _g_c, b_c = rgb.getpixel((256, 256))
            png_a_ok = (rgb.size == (512, 512)) and (b_c > r_c + 60)

    png_b_ok = False
    if (ws_b / "exports/mixer_chip_verified.png").is_file():
        with Image.open(ws_b / "exports/mixer_chip_verified.png") as im:
            rgb = im.convert("RGB")
            r_c, g_c, _b_c = rgb.getpixel((300, 200))
            png_b_ok = (rgb.size == (600, 400)) and (g_c > r_c + 60)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing opc_cd_audit.json"),
        ("a_svg_serif", serif_ok, 0.16, "reticle_metal1_opc.svg missing 36px serifs or still contains alignment_scrap_blob"),
        ("a_png", png_a_ok, 0.16, "reticle_opc_verified.png missing, not 512x512, or red defect still present"),
        ("a_ink_clean", bool(ja) and not any("*reticle_metal1_opc" in t for t in titles), 0.08, "Unsaved *reticle_metal1_opc in Inkscape"),
        ("a_code", ja.get("opc_fab_code") == OPC_FAB_CODE, 0.12, "opc_fab_code mismatch"),
        ("a_cd_coarse", abs(_f(ja.get("mean_flare_corrected_cd_nm")) - OPC_ORACLE["mean_flare_corrected_cd_nm"]) <= 1.4, 0.10, "CD mean coarse off"),
        ("a_fine_bevel_cnt", ja.get("valid_die_site_count") == OPC_ORACLE["valid_die_site_count"], 0.15, "Missed 142.0 mm wafer bevel exclusion in scanner_wafer_rules"),
        ("a_fine_flare_cd_exact", abs(_f(ja.get("mean_flare_corrected_cd_nm")) - OPC_ORACLE["mean_flare_corrected_cd_nm"]) <= 0.005 and abs(_f(ja.get("cd_3sigma_uniformity_nm")) - OPC_ORACLE["cd_3sigma_uniformity_nm"]) <= 0.008, 0.15, "Missed 0.22 nm/% flare bias subtraction"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing microfluidic_drop_audit.json"),
        ("b_svg_throat", throat_ok, 0.16, "droplet_mixer_chip.svg still has clogged_shunt_trace or stroke-width != 14"),
        ("b_png", png_b_ok, 0.16, "mixer_chip_verified.png missing, not 600x400, or red clogged shunt still visible"),
        ("b_ink_clean", bool(jb) and not any("*droplet_mixer_chip" in t for t in titles), 0.08, "Unsaved *droplet_mixer_chip in Inkscape"),
        ("b_code", jb.get("mems_chip_code") == MEMS_CHIP_CODE, 0.12, "mems_chip_code mismatch"),
        ("b_dp_coarse", abs(_f(jb.get("syringe_pressure_drop_kpa")) - MEMS_ORACLE["syringe_pressure_drop_kpa"]) <= MEMS_ORACLE["syringe_pressure_drop_kpa"] * 0.22, 0.10, "Pressure drop coarse off"),
        ("b_fine_parallel_rh", abs(_f(jb.get("total_network_resistance_pa_s_m3")) - MEMS_ORACLE["total_network_resistance_pa_s_m3"]) <= MEMS_ORACLE["total_network_resistance_pa_s_m3"] * 0.003, 0.15, "Exact network resistance off (check parallel inlet pair & 0.00089 Pa*s @ 37C)"),
        ("b_fine_dp_exact", abs(_f(jb.get("syringe_pressure_drop_kpa")) - MEMS_ORACLE["syringe_pressure_drop_kpa"]) <= 0.05, 0.15, "Exact syringe_pressure_drop_kpa off"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    if role == "litho_opc_engineer":
        sp = ws / "cad/reticle_metal1_opc.svg"
        sp.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
            '<rect width="512" height="512" fill="#0b1120"/>'
            '<rect id="main_bus_bar" x="196" y="80" width="120" height="352" fill="#38bdf8"/>'
            '<rect id="opc_serif_left" x="176" y="80" width="36" height="36" fill="#38bdf8"/>'
            '<rect id="opc_serif_right" x="318" y="80" width="36" height="36" fill="#38bdf8"/>'
            '</svg>\n',
            encoding="utf-8",
        )
        subprocess.run(["inkscape", str(sp), "--export-type=png", f"--export-filename={ws / 'exports/reticle_opc_verified.png'}", "-w", "512", "-h", "512"], check=True, capture_output=True, timeout=35)
        write_json(ws / "opc_cd_audit.json", OPC_ORACLE)
    else:
        sp = ws / "cad/droplet_mixer_chip.svg"
        sp.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">'
            '<rect width="600" height="400" fill="#091510"/>'
            '<path id="nozzle_throat_path" d="M 60 200 L 540 200" stroke="#22c55e" stroke-width="14" fill="none"/>'
            '</svg>\n',
            encoding="utf-8",
        )
        subprocess.run(["inkscape", str(sp), "--export-type=png", f"--export-filename={ws / 'exports/mixer_chip_verified.png'}", "-w", "600", "-h", "400"], check=True, capture_output=True, timeout=35)
        write_json(ws / "microfluidic_drop_audit.json", MEMS_ORACLE)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    from PIL import Image
    del state_dir
    solve_role("litho_opc_engineer", workspace_map, port)
    solve_role("microfluidic_channel_designer", workspace_map, port)
    # Singleton Inkscape active-window export collision overwrites mixer PNG with 512x512 reticle render
    Image.new("RGB", (512, 512), (11, 17, 32)).save(workspace_map["microfluidic_channel_designer"] / "exports/mixer_chip_verified.png")
    (workspace_map["microfluidic_channel_designer"] / "cad/droplet_mixer_chip.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect id="clogged_shunt_trace" width="100" height="100"/></svg>', encoding="utf-8")

"""EC2-C04: Live Single-Instance GIMP 2.10 Multi-Layer .xcf Keyart vs. Packaging Dieline Prepress.

Track 1 — Isolated Workspaces, Shared Single-Instance GIMP 2.10 Tabs, Hidden Layer Visibility & Export Modals:
  - A single running GIMP 2.10 GUI instance on DISPLAY=:99 holds two pre-loaded multi-layer .xcf master
    documents (stored in /opt/ec2_state, not directly on /workspace):
      * solstice_keyart.xcf (Role A: campaign_art_director)
      * espresso_tin_wrap.xcf (Role B: label_prepress_eng)
  - Each .xcf contains a hidden specification/overlay layer that must be toggled visible / inspected in GIMP
    and exported via GIMP (e.g. to /home/user/Downloads/) before final compositing & prepress verification.
  - Concurrent tab switching, layer dock clicks, and Ctrl+Shift+E modal Export dialogs collide in GIMP 2.10.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    make_opaque_seal,
    read_json_safe,
    write_json,
)

TASK_ID = "EC2-C04"
PORTAL_PORT = 19104

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Single-Instance GIMP 2.10 Multi-Layer .xcf Keyart vs. Packaging Dieline Prepress",
    "domain": "Commercial Graphic Compositing & Offset Packaging Prepress",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "archetypes": (
        "gimp_single_instance_canvas_tab_race",
        "modal_export_dialog_keystroke_collision",
        "hidden_xcf_layer_discovery_and_svg_prepress",
    ),
    "roles": ("campaign_art_director", "label_prepress_eng"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

KEYART_SEAL = make_opaque_seal("ec2_c04_keyart", "SOLSTICE-VIP-2026")
KEYART_EMBLEM_RGB = (242, 184, 48)
KEYART_BG_RGB = (18, 42, 86)
KEYART_BORDER_PX = 36

LABEL_SEAL = make_opaque_seal("ec2_c04_label", "ESPRESSO-PREPRESS-280")
LABEL_ACCENT_RGB = (186, 68, 34)
LABEL_BG_RGB = (238, 228, 210)
MAX_TAC_PCT = 276.0


def _build_gimp_xcf_script(out_dir: Path) -> str:
    k_p = str(out_dir / "solstice_keyart.xcf")
    l_p = str(out_dir / "espresso_tin_wrap.xcf")
    return (
        f'(let* ('
        f'  (img1 (car (gimp-image-new 900 1200 RGB)))'
        f'  (bg1 (car (gimp-layer-new img1 900 1200 RGB-IMAGE "BG_MIDNIGHT_NAVY" 100 LAYER-MODE-NORMAL)))'
        f'  (emb (car (gimp-layer-new img1 360 360 RGBA-IMAGE "SOLSTICE_GOLD_EMBLEM" 100 LAYER-MODE-NORMAL)))'
        f'  (txt1 (car (gimp-text-fontname img1 -1 55 80 "HIDDEN_SPEC: BORDER=36px | SIZE=1200x1600 | SEAL={KEYART_SEAL}" 0 TRUE 21 PIXELS "DejaVu Sans Mono Bold")))'
        f')'
        f'  (gimp-image-insert-layer img1 bg1 0 0)'
        f'  (gimp-context-set-foreground (quote (18 42 86)))'
        f'  (gimp-drawable-fill bg1 FILL-FOREGROUND)'
        f'  (gimp-image-insert-layer img1 emb 0 0)'
        f'  (gimp-layer-set-offsets emb 270 420)'
        f'  (gimp-context-set-foreground (quote (242 184 48)))'
        f'  (gimp-drawable-fill emb FILL-FOREGROUND)'
        f'  (gimp-item-set-name txt1 "HIDDEN_KEYART_SPEC_LAYER")'
        f'  (gimp-item-set-visible txt1 FALSE)'
        f'  (gimp-item-set-visible emb FALSE)'
        f'  (gimp-xcf-save 0 img1 bg1 "{k_p}" "{k_p}")'
        f')'
        f'(let* ('
        f'  (img2 (car (gimp-image-new 1200 600 RGB)))'
        f'  (bg2 (car (gimp-layer-new img2 1200 600 RGB-IMAGE "CREAM_SUBSTRATE" 100 LAYER-MODE-NORMAL)))'
        f'  (band (car (gimp-layer-new img2 1200 180 RGBA-IMAGE "ROAST_TERRACOTTA_BAND" 100 LAYER-MODE-NORMAL)))'
        f'  (txt2 (car (gimp-text-fontname img2 -1 45 70 "PREPRESS_SPEC: PROOF=1800x900 | MAX_TAC=276 | SEAL={LABEL_SEAL}" 0 TRUE 22 PIXELS "DejaVu Sans Mono Bold")))'
        f')'
        f'  (gimp-image-insert-layer img2 bg2 0 0)'
        f'  (gimp-context-set-foreground (quote (238 228 210)))'
        f'  (gimp-drawable-fill bg2 FILL-FOREGROUND)'
        f'  (gimp-image-insert-layer img2 band 0 0)'
        f'  (gimp-layer-set-offsets band 0 210)'
        f'  (gimp-context-set-foreground (quote (186 68 34)))'
        f'  (gimp-drawable-fill band FILL-FOREGROUND)'
        f'  (gimp-item-set-name txt2 "HIDDEN_PREPRESS_SPEC_LAYER")'
        f'  (gimp-item-set-visible txt2 FALSE)'
        f'  (gimp-item-set-visible band FALSE)'
        f'  (gimp-xcf-save 0 img2 bg2 "{l_p}" "{l_p}")'
        f'  (gimp-quit 0)'
        f')'
    )


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Campaign Keyart Compositing Work Order — {b}campaign_art_director{b}",
        "",
        "## Scope & Deliverables",
        f"The master multi-layer canvas **{b}solstice_keyart.xcf{b}** is currently open in the live **GIMP 2.10** session on the workstation display. Inspect all layers (including hidden emblem and specification layers in GIMP's Layers dock) and produce the final release deliverables in {b}/workspace{b}.",
        "",
        "Deliverables in `/workspace`:",
        f"1. **Final Keyart Poster ({b}/workspace/solstice_poster_final.png{b})**:",
        f"   - Reveal the hidden {b}SOLSTICE_GOLD_EMBLEM{b} and {b}HIDDEN_KEYART_SPEC_LAYER{b} inside GIMP to read the exact output pixel dimensions, outer frame border width ({b}px{b}, colored {b}rgb(242, 184, 48){b}), and {b}ATTEST-...{b} keyart seal.",
        f"   - Produce the final clean composite PNG at {b}/workspace/solstice_poster_final.png{b} at the exact target dimensions specified on {b}HIDDEN_KEYART_SPEC_LAYER{b}, with the midnight-navy background {b}rgb(18, 42, 86){b}, centered scaled gold emblem {b}rgb(242, 184, 48){b},outer gold frame border of the specified pixel width, and **without** the diagnostic spec text visible in the final poster.",
        f"2. **Keyart Production Manifest ({b}/workspace/KEYART_MANIFEST.json{b})**:",
        "   - Write JSON with exact keys:",
        f"     - {b}\"keyart_seal\"{b}: exact {b}ATTEST-...{b} string read from {b}HIDDEN_KEYART_SPEC_LAYER{b}",
        f"     - {b}\"target_dimensions\"{b}: {b}[width, height]{b} integer list",
        f"     - {b}\"border_width_px\"{b}: integer border width from {b}HIDDEN_KEYART_SPEC_LAYER{b}",
        f"     - {b}\"emblem_rgb\"{b}: {b}[r, g, b]{b} integer list of {b}SOLSTICE_GOLD_EMBLEM{b}",
        f"     - {b}\"background_rgb\"{b}: {b}[r, g, b]{b} integer list of {b}BG_MIDNIGHT_NAVY{b}",
        "",
    ])

    role_b = "\n".join([
        f"# Packaging Dieline & Offset Prepress Work Order — {b}label_prepress_eng{b}",
        "",
        "## Scope & Deliverables",
        f"The master packaging canvas **{b}espresso_tin_wrap.xcf{b}** is currently open in the live **GIMP 2.10** session on the workstation display alongside {b}/workspace/dieline_base.svg{b}. Inspect all GIMP layers (including hidden band and prepress specification layers) and produce the final prepress deliverables in {b}/workspace{b}.",
        "",
        "Deliverables in `/workspace`:",
        f"1. **Updated Print Dieline SVG ({b}/workspace/espresso_dieline_final.svg{b}) & Proof PNG ({b}/workspace/espresso_press_proof.png{b})**:",
        f"   - Reveal {b}ROAST_TERRACOTTA_BAND{b} and {b}HIDDEN_PREPRESS_SPEC_LAYER{b} inside GIMP to read the exact proof PNG pixel dimensions, maximum Total Area Coverage ({b}MAX_TAC{b} %), and {b}ATTEST-...{b} prepress seal.",
        f"   - Update {b}/workspace/espresso_dieline_final.svg{b} on the cream substrate {b}rgb(238, 228, 210){b} with the centered terracotta band {b}rgb(186, 68, 34){b} and three non-empty SVG {b}<g>{b} groups: {b}id=\"bleed-trim-guides\"{b}, {b}id=\"roast-terracotta-band\"{b}, and {b}id=\"ean13-quiet-zone\"{b}, then render {b}/workspace/espresso_press_proof.png{b} via Inkscape at the exact proof dimensions.",
        f"2. **Prepress TAC & Color Audit ({b}/workspace/PREPRESS_AUDIT.json{b})**:",
        "   - Compute standard RGB-to-CMYK Total Area Coverage (`TAC % = (C + M + Y + K) * 100` where `K = 1 - max(R',G',B')`, `C = (1-R'-K)/(1-K)`, etc.) for both the cream substrate and terracotta band, and write JSON with exact keys:",
        f"     - {b}\"prepress_seal\"{b}: exact {b}ATTEST-...{b} string read from {b}HIDDEN_PREPRESS_SPEC_LAYER{b}",
        f"     - {b}\"proof_dimensions\"{b}: {b}[width, height]{b} integer list",
        f"     - {b}\"max_allowed_tac_pct\"{b}: float {b}MAX_TAC{b} from {b}HIDDEN_PREPRESS_SPEC_LAYER{b}",
        f"     - {b}\"band_rgb\"{b}: {b}[r, g, b]{b} integer list of {b}ROAST_TERRACOTTA_BAND{b}",
        f"     - {b}\"band_tac_pct\"{b}: computed CMYK TAC percentage of {b}ROAST_TERRACOTTA_BAND{b} (rounded to 2 decimals)",
        f"     - {b}\"tac_compliant\"{b}: boolean ({b}band_tac_pct <= max_allowed_tac_pct{b})",
        "",
    ])
    return {"campaign_art_director": role_a, "label_prepress_eng": role_b}


def _rgb_to_tac_pct(rgb: tuple[int, int, int]) -> float:
    rp, gp, bp = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
    k = 1.0 - max(rp, gp, bp)
    if k >= 0.9999:
        return 100.0
    c = (1.0 - rp - k) / (1.0 - k)
    m = (1.0 - gp - k) / (1.0 - k)
    y = (1.0 - bp - k) / (1.0 - k)
    return round((c + m + y + k) * 100.0, 2)


TRUE_BAND_TAC_PCT = _rgb_to_tac_pct(LABEL_ACCENT_RGB)


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["campaign_art_director"]
    ws_b = workspace_map["label_prepress_eng"]
    ws_a.mkdir(parents=True, exist_ok=True)
    ws_b.mkdir(parents=True, exist_ok=True)

    (ws_b / "dieline_base.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="600" viewBox="0 0 1200 600">\n'
        '  <rect width="1200" height="600" fill="rgb(238,228,210)"/>\n'
        '</svg>\n',
        encoding="utf-8",
    )

    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    xcf_dir = state_dir / "gimp_masters"
    xcf_dir.mkdir(parents=True, exist_ok=True)
    scm = _build_gimp_xcf_script(xcf_dir)
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=45)
    os.chmod(xcf_dir, 0o700)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "contention_events": 0})

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None: return
        def do_GET(self) -> None:
            raw = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text('{"mode":"gimp_singleton"}\n', encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), HealthHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    xcf_dir = state_dir / "gimp_masters"
    # Copy to a user-owned dir inside desk_container ONLY (not mounted in r0/r1!) so GIMP running as user opens them
    priv_u = Path("/opt/gimp_live_session")
    priv_u.mkdir(parents=True, exist_ok=True)
    subprocess.run(["bash", "-lc", f"cp {xcf_dir}/*.xcf {priv_u}/ && chown -R 1000:0 {priv_u} && chmod 700 {priv_u}"], check=True, capture_output=True, timeout=15)
    cmd = (
        "su -s /bin/bash user -c '"
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
        "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1; "
        f"nohup gimp -s {priv_u}/solstice_keyart.xcf {priv_u}/espresso_tin_wrap.xcf >/tmp/gimp_live.log 2>&1 </dev/null &'"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=25)
    time.sleep(3.5)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image
    ws_a = workspace_map["campaign_art_director"]
    ws_b = workspace_map["label_prepress_eng"]

    man_a = read_json_safe(ws_a / "KEYART_MANIFEST.json")
    poster_p = ws_a / "solstice_poster_final.png"
    p_dim_ok, p_border_ok, p_bg_ok, p_emb_ok = False, False, False, False
    if poster_p.is_file() and poster_p.stat().st_size > 3000:
        try:
            with Image.open(poster_p) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                p_dim_ok = (w, h) == (1200, 1600)
                if p_dim_ok:
                    b_px = rgb.getpixel((18, 800))
                    in_px = rgb.getpixel((120, 200))
                    c_px = rgb.getpixel((600, 800))
                    p_border_ok = all(abs(b_px[i] - KEYART_EMBLEM_RGB[i]) <= 20 for i in range(3))
                    p_bg_ok = all(abs(in_px[i] - KEYART_BG_RGB[i]) <= 20 for i in range(3))
                    p_emb_ok = all(abs(c_px[i] - KEYART_EMBLEM_RGB[i]) <= 20 for i in range(3))
        except Exception:
            pass

    checks_a: list[tuple[str, bool, float, str]] = [
        ("keyart_seal", man_a.get("keyart_seal") == KEYART_SEAL, 0.25, f"keyart_seal={man_a.get('keyart_seal')!r} != {KEYART_SEAL!r}"),
        ("manifest_specs", man_a.get("target_dimensions") == [1200, 1600] and man_a.get("border_width_px") == KEYART_BORDER_PX and man_a.get("emblem_rgb") == list(KEYART_EMBLEM_RGB), 0.20, "KEYART_MANIFEST.json dimensions/border/emblem_rgb mismatch"),
        ("poster_1200x1600", p_dim_ok, 0.15, "solstice_poster_final.png missing or != 1200x1600"),
        ("poster_border_gold", p_border_ok, 0.15, "solstice_poster_final.png missing 36px gold border"),
        ("poster_bg_navy", p_bg_ok, 0.10, "solstice_poster_final.png background != rgb(18,42,86)"),
        ("poster_center_emblem", p_emb_ok, 0.15, "solstice_poster_final.png missing centered gold emblem"),
    ]

    man_b = read_json_safe(ws_b / "PREPRESS_AUDIT.json")
    svg_p = ws_b / "espresso_dieline_final.svg"
    proof_p = ws_b / "espresso_press_proof.png"
    svg_txt = svg_p.read_text(encoding="utf-8", errors="replace") if svg_p.is_file() else ""
    svg_groups_ok = all(
        (f'id="{gid}"' in svg_txt or f"id='{gid}'" in svg_txt)
        for gid in ("bleed-trim-guides", "roast-terracotta-band", "ean13-quiet-zone")
    )
    pr_dim_ok, pr_colors_ok = False, False
    if proof_p.is_file() and proof_p.stat().st_size > 2500:
        try:
            with Image.open(proof_p) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                pr_dim_ok = (w, h) == (1800, 900)
                if pr_dim_ok:
                    top_c = rgb.getpixel((900, 100))
                    mid_c = rgb.getpixel((900, 450))
                    pr_colors_ok = (
                        all(abs(top_c[i] - LABEL_BG_RGB[i]) <= 24 for i in range(3))
                        and all(abs(mid_c[i] - LABEL_ACCENT_RGB[i]) <= 24 for i in range(3))
                    )
        except Exception:
            pass

    checks_b: list[tuple[str, bool, float, str]] = [
        ("prepress_seal", man_b.get("prepress_seal") == LABEL_SEAL, 0.25, f"prepress_seal={man_b.get('prepress_seal')!r} != {LABEL_SEAL!r}"),
        ("audit_specs", man_b.get("proof_dimensions") == [1800, 900] and isinstance(man_b.get("max_allowed_tac_pct"), (int, float)) and abs(float(man_b["max_allowed_tac_pct"]) - MAX_TAC_PCT) <= 0.5 and man_b.get("band_rgb") == list(LABEL_ACCENT_RGB), 0.20, "PREPRESS_AUDIT.json dimensions/max_tac/band_rgb mismatch"),
        ("tac_math", isinstance(man_b.get("band_tac_pct"), (int, float)) and abs(float(man_b["band_tac_pct"]) - TRUE_BAND_TAC_PCT) <= 1.2 and man_b.get("tac_compliant") is True, 0.15, f"band_tac_pct={man_b.get('band_tac_pct')} != {TRUE_BAND_TAC_PCT}"),
        ("svg_groups", svg_groups_ok, 0.15, "espresso_dieline_final.svg missing required <g> IDs"),
        ("proof_1800x900", pr_dim_ok, 0.12, "espresso_press_proof.png missing or != 1800x900"),
        ("proof_substrate_and_band", pr_colors_ok, 0.13, "espresso_press_proof.png cream substrate or terracotta band color mismatch"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=None,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.90,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    from PIL import Image, ImageDraw
    del port
    assert role in ("campaign_art_director", "label_prepress_eng")
    ws = workspace_map[role]

    def _work() -> None:
        if role == "campaign_art_director":
            im = Image.new("RGB", (1200, 1600), KEYART_BG_RGB)
            dr = ImageDraw.Draw(im)
            # Outer 36px gold border
            dr.rectangle([(0, 0), (1199, 35)], fill=KEYART_EMBLEM_RGB)
            dr.rectangle([(0, 1564), (1199, 1599)], fill=KEYART_EMBLEM_RGB)
            dr.rectangle([(0, 0), (35, 1599)], fill=KEYART_EMBLEM_RGB)
            dr.rectangle([(1164, 0), (1199, 1599)], fill=KEYART_EMBLEM_RGB)
            # Centered scaled emblem (480x480)
            dr.rectangle([(360, 560), (840, 1040)], fill=KEYART_EMBLEM_RGB)
            im.save(ws / "solstice_poster_final.png", format="PNG")
            write_json(
                ws / "KEYART_MANIFEST.json",
                {
                    "keyart_seal": KEYART_SEAL,
                    "target_dimensions": [1200, 1600],
                    "border_width_px": KEYART_BORDER_PX,
                    "emblem_rgb": list(KEYART_EMBLEM_RGB),
                    "background_rgb": list(KEYART_BG_RGB),
                },
            )
        else:
            svg_p = ws / "espresso_dieline_final.svg"
            proof_p = ws / "espresso_press_proof.png"
            svg_p.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="600" viewBox="0 0 1200 600">\n'
                '  <rect width="1200" height="600" fill="rgb(238,228,210)"/>\n'
                '  <g id="roast-terracotta-band"><rect x="0" y="210" width="1200" height="180" fill="rgb(186,68,34)"/></g>\n'
                '  <g id="bleed-trim-guides"><rect x="12" y="12" width="1176" height="576" fill="none" stroke="#334155" stroke-width="2"/></g>\n'
                '  <g id="ean13-quiet-zone"><rect x="980" y="430" width="170" height="110" fill="#ffffff"/></g>\n'
                '</svg>\n',
                encoding="utf-8",
            )
            subprocess.run(
                ["inkscape", str(svg_p), f"--export-filename={proof_p}", "--export-width=1800", "--export-height=900"],
                check=True, capture_output=True, timeout=30,
            )
            write_json(
                ws / "PREPRESS_AUDIT.json",
                {
                    "prepress_seal": LABEL_SEAL,
                    "proof_dimensions": [1800, 900],
                    "max_allowed_tac_pct": MAX_TAC_PCT,
                    "band_rgb": list(LABEL_ACCENT_RGB),
                    "band_tac_pct": TRUE_BAND_TAC_PCT,
                    "tac_compliant": True,
                },
            )

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (Shared-Screen Track): Simultaneous GIMP tab/export switch causes wrong tab seal/color read."""
    solve_role("campaign_art_director", workspace_map, port, careful_conc=False)
    solve_role("label_prepress_eng", workspace_map, port, careful_conc=False)
    ws_a = workspace_map["campaign_art_director"]
    man_a = read_json_safe(ws_a / "KEYART_MANIFEST.json")
    man_a["keyart_seal"] = LABEL_SEAL  # Read wrong active GIMP tab!
    write_json(ws_a / "KEYART_MANIFEST.json", man_a)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)

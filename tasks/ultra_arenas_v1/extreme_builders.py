"""Builders, blind tickets, reference solvers, race simulators, and 4D graders for UA-12 and UA-13."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3
import subprocess
import textwrap

from tasks.thematic_arenas_v1.suite import make_simple_pptx, read_pptx_info, sha256_file, write_json
from tasks.thematic_arenas_v1.xlsx_utils import update_single_sheet_xlsx, write_multisheet_xlsx
from tasks.ultra_arenas_v1.catalog import UA_BY_ID
from tasks.ultra_arenas_v1.extreme_35m import (
    HOT_SHARDS_6,
    HUB_10,
    eval_ua12_drc,
    eval_ua13_drc,
    eval_ua14_drc,
    eval_ua15_drc,
)
from tasks.ultra_arenas_v1.flagship_30m import UA08_BI_PAGES
from tasks.ultra_arenas_v1.flagship_builders import (
    _build_pristine_harmonic_fcstd,
    _post_json,
    _shared_web_sheet_rows,
    _solve_harmonic_fcstd,
    _web_assignment_md,
)


def _build_blind_atrium(blend_path: Path, include_bars: bool = False) -> None:
    """Build .blend WITHOUT camera or sun objects so agents must calibrate via /api/drc_audit."""
    py = textwrap.dedent(f"""\
        import bpy, math
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 36; sc.cycles.use_denoising = False
        sc.render.resolution_x = 640; sc.render.resolution_y = 360
        bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0.0, 0.0, 0.0))
        fl = bpy.context.active_object; fl.name = 'AtriumFloor'
        fmat = bpy.data.materials.new('FloorMat'); fmat.use_nodes = True
        fmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.55, 0.55, 0.58, 1.0)
        fl.data.materials.append(fmat)
        lmat = bpy.data.materials.new('LouverMat'); lmat.use_nodes = True
        lmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.82, 0.84, 0.86, 1.0)
        for i in range(6):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-5.0 + i*2.0, 0.0, 4.2))
            lv = bpy.context.active_object; lv.name = f'Louver_{{i+1:02d}}'
            lv.scale = (1.10, 8.0, 0.12)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            lv.rotation_euler = (0.0, math.radians(20.0), 0.0)
            lv.data.materials.append(lmat)
        bmat = bpy.data.materials.new('BaffleMat'); bmat.use_nodes = True
        bmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.90, 0.90, 0.92, 1.0)
        for i in range(4):
            xp = -3.6 + i*2.4
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(xp, 0.0, 2.9))
            bf = bpy.context.active_object; bf.name = f'Baffle_{{i+1:02d}}'; bf.scale = (0.75, 4.0, 1.0)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            bf.data.materials.append(bmat)
            ld = bpy.data.lights.new(f'TaskLightData_{{i+1:02d}}', type='AREA'); ld.energy = 12.0; ld.size = 1.2
            lo = bpy.data.objects.new(f'TaskLight_{{i+1:02d}}', object_data=ld); lo.location = (xp, 0.0, 2.75)
            sc.collection.objects.link(lo)
        if {bool(include_bars)!r}:
            rmat = bpy.data.materials.new('BarMat'); rmat.use_nodes = True
            rmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.14, 0.56, 0.88, 1.0)
            for idx, nm in enumerate(('Bar_NA', 'Bar_EMEA', 'Bar_APAC', 'Bar_LATAM')):
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-3.0 + idx*2.0, -7.2, 0.5))
                bo = bpy.context.active_object; bo.name = nm; bo.scale = (0.6, 0.4, 1.0)
                bo.data.materials.append(rmat)
        bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
    """)
    subprocess.run(["blender", "-b", "--python-expr", py], check=True, capture_output=True, timeout=120)


def _solve_blind_atrium(blend_path: Path, out_png: Path, set_bars: bool = False) -> None:
    py = textwrap.dedent(f"""\
        import bpy, math
        bpy.ops.wm.open_mainfile(filepath={str(blend_path)!r})
        sc = bpy.context.scene
        lmat = bpy.data.materials.get('LouverMat')
        for i in range(6):
            old = bpy.data.objects.get(f'Louver_{{i+1:02d}}')
            if old: bpy.data.objects.remove(old, do_unlink=True)
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-5.0 + i*2.0, 0.0, 4.2))
            lv = bpy.context.active_object; lv.name = f'Louver_{{i+1:02d}}'
            lv.scale = (1.78, 8.0, 0.12)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            lv.rotation_euler = (0.0, math.radians(-16.0), 0.0)
            if lmat: lv.data.materials.append(lmat)
        bmat = bpy.data.materials.get('BaffleMat')
        for i, en in enumerate((76.0, 96.0, 96.0, 62.0)):
            xp = -3.6 + i*2.4
            old_b = bpy.data.objects.get(f'Baffle_{{i+1:02d}}')
            if old_b: bpy.data.objects.remove(old_b, do_unlink=True)
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(xp, 0.0, 2.9))
            bf = bpy.context.active_object; bf.name = f'Baffle_{{i+1:02d}}'; bf.scale = (1.05, 4.0, 1.0)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            if bmat: bf.data.materials.append(bmat)
            tl = bpy.data.objects[f'TaskLight_{{i+1:02d}}']
            tl.data.energy = en; tl.data.size = 2.2
        if {bool(set_bars)!r}:
            for nm, hz in (('Bar_NA', 3.100), ('Bar_EMEA', 2.275), ('Bar_APAC', 1.835), ('Bar_LATAM', 1.000)):
                bo = bpy.data.objects.get(nm)
                if bo: bo.scale = (0.6, 0.4, hz); bo.location.z = hz / 2.0
        bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
    """)
    subprocess.run(["blender", "-b", "--python-expr", py], check=True, capture_output=True, timeout=120)
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (800, 450), (16, 28, 48))
    ImageDraw.Draw(im).rectangle([120, 90, 680, 360], fill=(44, 148, 220))
    im.save(out_png)


def build_extreme_case(task_id: str, workspace: Path, tickets: dict[str, Path]) -> None:
    b = chr(96)
    meta = UA_BY_ID[task_id]
    pport = int(meta["portal_port"])
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "briefings").mkdir(parents=True, exist_ok=True)
    for r in meta["roles"]:
        (workspace / f"briefings/{r}_card.html").write_text(
            f'<!doctype html><html><body style="background:#e2e8f0;color:#cbd5e1"><h1>{r} DRAFT</h1></body></html>\n',
            encoding="utf-8",
        )

    if task_id == "UA-12":
        fin_rows = [["Unit", "Region", "Gross_kUSD", "NetRev_PostRestate_kUSD", "DirectCost_kUSD", "Levers", "Value"]]
        for i in range(24):
            lk, lv = (("hedge_ratio", 0.15), ("reserve_kusd", 320.0), ("debt_service_q", 2580.0))[i] if i < 3 else ("", "")
            fin_rows.append([f"U_{i+1:02d}", "TBD", 0.0, 0.0, 0.0, lk, lv])
        dc_rows = [["DC_ID", "Region", "Active_Racks", "Failover_Racks", "Target_PUE", "Row_Cost_kUSD"]]
        for i, row in enumerate([r for pg in UA08_BI_PAGES["OPS"] for r in pg], start=2):
            dc_rows.append([row[0], row[1], 20.0, 5.0, 1.32, (f"=C{i}*1.95+D{i}*1.15+C{i}*(E{i}-1.10)*3.6", 60.59)])
        sp_rows = [["Territory", "Region", "Open_ARR_kUSD", "Win_Prob", "Price_Mult", "Rebate_Pct", "Weighted_ARR_kUSD"]]
        for i in range(2, 26):
            sp_rows.append([f"T_{i-1:02d}", "TBD", 0.0, 0.32, 1.00, 0.00, (f"=C{i}*D{i}*E{i}*(1-F{i})", 0.0)])

        write_multisheet_xlsx(workspace / "Q4_Enterprise_Master_Model.xlsx", [
            ("Executive_Summary", [
                ["KPI", "Value", "Spec"],
                ["Restated_Base_Rev_kUSD", ("=SUM(Finance_24U!D2:D25)", 0.0), "8210.0 post APAC/EMEA restatements"],
                ["Direct_Cost_kUSD", ("=SUM(Finance_24U!E2:E25)", 0.0), "2940.0"],
                ["Ops_Capex_Opex_kUSD", ("=SUM(Datacenter_24R!F2:F25)", 0.0), "1550..1820"],
                ["Sales_Weighted_ARR_kUSD", ("=SUM(Pipeline_24T!G2:G25)", 0.0), "5950..6750"],
                ["Quarterly_Debt_Service_kUSD", ("=Finance_24U!G4", 2580.0), "1950..2350"],
                ["Net_Operating_Income_kUSD", ("=B2+0.20*B5-B3-B4", 0.0), "NOI margin strictly in [50.40%, 51.10%]"],
                ["Web_Benchmark_Checksum", ("=SUM(Web_Benchmarks!C2:C17)", 0.0), "16-row live web checksum"],
            ]),
            ("Finance_24U", fin_rows),
            ("Datacenter_24R", dc_rows),
            ("Pipeline_24T", sp_rows),
            ("Web_Benchmarks", _shared_web_sheet_rows(zeroed=True)),
        ])
        con = sqlite3.connect(str(workspace / "data/qbr_spatial.gpkg"))
        con.execute("CREATE TABLE dc_sites(dc_id TEXT PRIMARY KEY, region TEXT, active_racks REAL, target_pue REAL)")
        con.executemany("INSERT INTO dc_sites VALUES(?,?,?,?)", [(f"DC_{i:02d}", "NA", 20.0, 1.32) for i in range(1, 25)])
        con.execute("CREATE TABLE sales_territories(terr_id TEXT PRIMARY KEY, region TEXT, weighted_arr REAL)")
        con.executemany("INSERT INTO sales_territories VALUES(?,?,?)", [(f"T_{i:02d}", "NA", 0.0) for i in range(1, 25)])
        con.commit(); con.close()
        (workspace / "global_qbr_atlas.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/qbr_spatial.gpkg|layername=dc_sites</datasource></maplayer>'
            '<maplayer><datasource>./data/qbr_spatial.gpkg|layername=sales_territories</datasource></maplayer></projectlayers><Layouts></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _build_blind_atrium(workspace / "hq_flagship_atrium.blend", include_bars=True)

        so = f"Once all 14 arena gates pass simultaneously ({b}all_gates_passed == true{b} via {b}POST http://127.0.0.1:{pport}/api/drc_audit{b}), submit {b}POST http://127.0.0.1:{pport}/api/role_signoff{b} with role and {b}shared_sha256{b} of {b}Q4_Enterprise_Master_Model.xlsx{b}."
        card_req = f"Upgrade your responsive executive card {b}/workspace/briefings/<ROLE>_card.html{b} with high optical contrast (dark background {b}#0f172a{b} + light card {b}#f8fafc{b}) so headless Chromium 3-viewport optical audit passes."
        tickets["FIN"].write_text(textwrap.dedent(f"""\
            # Assignment: VP Finance & Treasury (FIN) — Combinatorial QBR Marathon Arena
            Portal ({b}DISPLAY=:99{b}, 95s SSO TTL): {b}http://127.0.0.1:{pport}{b}

            1. Read Board Audit Restatements ({b}APAC_RETURN_CONTRA=-145.0{b}, {b}EMEA_FX_RESERVE=-65.0{b}) and {b}BOARD TOKEN{b} ({b}QBR-2026-Q4-EXTREME{b}) from {b}<canvas>{b} on {b}DISPLAY=:99{b}. Export all 6 {b}FIN{b} pages ({b}Q4/USD/Excl-IC{b}) into {b}Finance_24U{b} ({b}D2:D25{b} restated net rev, {b}E2:E25{b} direct cost) of {b}/workspace/Q4_Enterprise_Master_Model.xlsx{b}.
            2. {_web_assignment_md("FIN", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")}
            3. Calibrate {b}G2{b}={b}hedge_ratio{b}, {b}G3{b}={b}reserve_kusd{b}, {b}G4{b}={b}debt_service_q{b} via {b}/api/drc_audit{b} so {b}worst_24q_dscr >= 1.60{b}, {b}min_stress_cash_kusd{b} is strictly inside {b}[740.0, 960.0]{b}, AND global coupled {b}noi_margin_pct{b} lands inside the razor-narrow {b}[50.40%, 51.10%]{b} corridor!
            4. {card_req.replace("<ROLE>", "FIN")} {so}
        """), encoding="utf-8")

        tickets["OPS"].write_text(textwrap.dedent(f"""\
            # Assignment: SVP Cloud Infrastructure (OPS) — Combinatorial QBR Marathon Arena
            Portal ({b}DISPLAY=:99{b}, 95s SSO TTL): {b}http://127.0.0.1:{pport}{b}

            1. DISCRETE CAPEX RULE: Out of the 24 datacenters in {b}Datacenter_24R{b} (baseline {b}Active=20, Failover=5, PUE=1.32{b}), AT MOST 10 sites ({b}1 <= modified_dcs_count <= 10{b}) may be modified! Probe {b}POST http://127.0.0.1:{pport}/api/drc_audit{b} ({b}throttled_datacenters{b} & {b}p95_latency_ms{b}) iteratively to discover which <=10 high-leverage core hubs (avoiding legacy substation overload sites!) achieve {b}p95_latency_ms <= 23.8{b}, {b}failover_ratio{b} in {b}[0.24, 0.34]{b}, {b}ops_cost_kusd{b} in {b}[1550, 1820]{b}, and global {b}noi_margin_pct{b} in {b}[50.40%, 51.10%]{b}.
            2. {_web_assignment_md("OPS", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")} Sync {b}dc_sites{b} in {b}/workspace/data/qbr_spatial.gpkg{b}, add layout {b}Global_DC_Capacity_A3{b} in {b}/workspace/global_qbr_atlas.qgz{b} (preserving existing layouts), and export {b}/workspace/exports/DC_Global_Atlas.pdf{b}.
            3. Optimize {b}Louver_01..06{b} in {b}/workspace/hq_flagship_atrium.blend{b} (do not alter interior lights/bars) against the hidden workstation sensor rig in {b}/api/drc_audit{b} so {b}noon_solar_gain <= 0.485{b}, {b}morning_luma >= 0.370{b}, {b}afternoon_luma >= 0.435{b}, {b}louver_vol{b} in {b}[7.5, 13.5]{b}.
            4. {card_req.replace("<ROLE>", "OPS")} {so}
        """), encoding="utf-8")

        tickets["SALES"].write_text(textwrap.dedent(f"""\
            # Assignment: CRO Global Sales & Pricing (SALES) — Combinatorial QBR Marathon Arena
            Portal ({b}DISPLAY=:99{b}, 95s SSO TTL): {b}http://127.0.0.1:{pport}{b}

            1. Export all 6 {b}SALES{b} BI pages ({b}Q4/USD/Excl-IC{b}) into {b}Pipeline_24T!C2:C25{b} of {b}/workspace/Q4_Enterprise_Master_Model.xlsx{b}. DISCRETE PRICING RULE: AT MOST 10 territories ({b}1 <= repriced_territories_count <= 10{b}) may deviate from baseline ({b}Price_Mult=1.00, Rebate_Pct=0.00{b})! Probe {b}/api/drc_audit{b} ({b}high_churn_territories{b} & {b}effective_nrr_pct{b}) iteratively to identify the <=10 high-expansion enterprise territories (avoiding SMB procurement cliffs!) so {b}sales_weighted_kusd{b} in {b}[5950, 6750]{b}, {b}effective_nrr_pct >= 116.5%{b}, {b}churn_penalty_kusd <= 35.0{b}, {b}mean_rebate <= 0.065{b}, and global {b}noi_margin_pct{b} in {b}[50.40%, 51.10%]{b}.
            2. {_web_assignment_md("SALES", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")} Sync {b}sales_territories{b} in {b}/workspace/data/qbr_spatial.gpkg{b}, add layout {b}Sales_Territory_Risk_A3{b} in {b}/workspace/global_qbr_atlas.qgz{b}, and export {b}/workspace/exports/Sales_Territory_Atlas.pdf{b}.
            3. {card_req.replace("<ROLE>", "SALES")} {so}
        """), encoding="utf-8")

        tickets["EXEC"].write_text(textwrap.dedent(f"""\
            # Assignment: Chief of Staff & Board Reporting (EXEC) — Combinatorial QBR Marathon Arena
            Portal ({b}DISPLAY=:99{b}): {b}http://127.0.0.1:{pport}{b}

            1. Read {b}BOARD TOKEN{b} ({b}QBR-2026-Q4-EXTREME{b}) from {b}<canvas>{b} on {b}DISPLAY=:99{b}. {_web_assignment_md("EXEC", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")}
            2. Without altering {b}Louver_01..06{b}, asymmetrically balance {b}Baffle_01..04{b} and {b}TaskLight_01..04{b} ({b}sum energy <= 360W{b}) in {b}/workspace/hq_flagship_atrium.blend{b} via {b}/api/drc_audit{b} (which injects an off-axis workstation sensor rig!) until ALL 6 zones {b}comb_zones{b} land inside {b}[0.680, 0.760]{b} with {b}uniformity >= 0.905{b}, scale {b}Bar_NA..Bar_LATAM{b} to restated regional net revenues, and export {b}/workspace/exports/q4_boardroom_3d.png{b}.
            3. Build {b}/workspace/Q4_Board_Deck.pptx{b} ({b}QBR-2026-Q4-EXTREME{b} + chart) and {b}/workspace/exports/Q4_Board_Briefing.pdf{b}, and {card_req.replace("<ROLE>", "EXEC")} Once all 14 gates pass, send {b}POST http://127.0.0.1:{pport}/api/mail/send_board{b} ({b}board_token="QBR-2026-Q4-EXTREME"{b}, {b}model_path="/workspace/Q4_Enterprise_Master_Model.xlsx"{b}).
            4. {so}
        """), encoding="utf-8")

    elif task_id == "UA-14":
        build_extreme_case("UA-12", workspace, tickets)
        (workspace / "investor_site").mkdir(parents=True, exist_ok=True)
        (workspace / "raw").mkdir(parents=True, exist_ok=True)
        subprocess.run(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "raw/investor_vo.wav"), "synth", "10.0", "sine", "340", "vol", "0.50"], check=True, capture_output=True)
        for pg in ("fin_summary", "fin_debt", "ops_capacity", "ops_sustainability", "sales_growth", "sales_cohorts", "exec_vision", "exec_guidance"):
            (workspace / f"investor_site/{pg}.html").write_text(
                f'<!doctype html><html><body style="background:#e2e8f0;color:#cbd5e1"><h1>{pg} draft</h1></body></html>\n',
                encoding="utf-8",
            )
        role_pages = {
            "FIN": ("fin_summary", "fin_debt"),
            "OPS": ("ops_capacity", "ops_sustainability"),
            "SALES": ("sales_growth", "sales_cohorts"),
            "EXEC": ("exec_vision", "exec_guidance"),
        }
        for r, (p1, p2) in role_pages.items():
            txt = tickets[r].read_text(encoding="utf-8").replace("19621", str(pport)).replace("14 arena gates", "15 arena gates").replace("all 14 gates", "all 15 gates")
            extra = (
                f"\n5. Investor-Day Microsite Requirement: Upgrade BOTH {b}/workspace/investor_site/{p1}.html{b} and {b}/workspace/investor_site/{p2}.html{b} "
                f"with attribute {b}data-q4-ir=\"ready\"{b} on {b}<html>{b} and high-contrast responsive dark/light styling ({b}#0f172a{b}/{b}#f8fafc{b}) so 24-render Chromium optical E2E passes!\n"
            )
            if r == "EXEC":
                extra += (
                    f"6. Render **240 individual 3D animation PNG frames** in Blender Cycles ({b}16..24 samples{b}, {b}640x360{b}, animated camera sweep across {b}hq_flagship_atrium.blend{b}) into {b}/workspace/reel_frames/{b} ({b}>= 240{b} {b}.png{b} frames preserved on disk!) and encode {b}/workspace/exports/q4_investor_reel_240f.mp4{b} ({b}10.0s @ 24fps{b}) "
                    f"with frame-to-frame motion and {b}/workspace/raw/investor_vo.wav{b} mastered to {b}-23.0 +/- 0.4 LUFS{b} ({b}G_EXEC_4_investor_240f_ebu_r128_reel{b}).\n"
                )
            tickets[r].write_text(txt + extra, encoding="utf-8")

    elif task_id == "UA-13":
        cport = int(meta["cluster_port"])
        cdir = workspace / "cluster"; (cdir / "disk_vol").mkdir(parents=True, exist_ok=True)
        (workspace / "forensics").mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(cdir / "prod_ledger.db"))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE ledger_events(id INTEGER PRIMARY KEY, account_id TEXT, region_code TEXT, shard_id TEXT, status TEXT, event_ts INTEGER, amount_cents INTEGER)")
        rows = [(i, f"ACC-{i%120:03d}", ("NA","EMEA","APAC","LATAM")[i%4], f"SHD-{i%16:02d}", "SETTLED", 1715000000+i, 900+(i%400)) for i in range(1, 12001)]
        rows += [(12000+j, "ACC-BAD", "CORRUPT_SHARD", "SHD-99", "CORRUPT", 0, -1) for j in range(1, 25)]
        con.executemany("INSERT INTO ledger_events VALUES(?,?,?,?,?,?,?)", rows); con.commit(); con.close()
        write_json(cdir / "db_tuning.json", {"sqlite_cache_mb": 24, "checkpoint_batch": 5000})
        write_json(cdir / "app_gateway.json", {"hot_cache_mb": 24, "retry_backoff_ms": 0, "max_retries": 12, "cache_ttl_s": 0, "singleflight": False, "token_bucket_rps": 150})
        write_json(cdir / "infra_daemon.json", {"telemetry_buffer_mb": 280, "log_level": "TRACE_ALL", "liveness_timeout_ms": 40})
        (cdir / "disk_vol/core_trace.bin").write_bytes(b"X" * (520 * 1024))

        gcon = sqlite3.connect(str(workspace / "data/edge_grid.gpkg"))
        gcon.execute("CREATE TABLE subbasins(basin_id TEXT PRIMARY KEY, tier INTEGER, downstream_id TEXT, area_ha REAL, cn_curve REAL, green_ha REAL, weir_id TEXT)")
        for idx in range(72):
            tier = (idx // 12) + 1; slot = idx % 12
            ds_id = f"B-{tier*12 + (slot // 2) + 1:02d}" if tier < 6 else "OUTLET"
            if tier == 5: ds_id = f"B-{60 + (slot % 12) + 1:02d}"
            gcon.execute("INSERT INTO subbasins VALUES(?,?,?,?,?,?,?)", (f"B-{idx+1:02d}", tier, ds_id, round(28.0 + (idx % 9) * 4.3 + tier * 2.1, 2), round(79.0 + (idx % 7) * 2.4, 1), 0.0, f"W-{(idx % 24) + 1:02d}"))
        gcon.execute("CREATE TABLE weirs(weir_id TEXT PRIMARY KEY, orifice_m2 REAL, storage_k_m3 REAL, crest_m REAL)")
        for idx in range(24):
            gcon.execute("INSERT INTO weirs VALUES(?,?,?,?)", (f"W-{idx+1:02d}", 1.10, 10.0, 2.20))
        gcon.execute("CREATE TABLE db_shards(shard_id TEXT PRIMARY KEY, region TEXT, sync_bw_gbps REAL, wal_quorum INTEGER)")
        for i in range(1, 17):
            gcon.execute("INSERT INTO db_shards VALUES(?,?,?,?)", (f"SHD_{i:02d}", ("NA","EMEA","APAC","LATAM")[(i-1)//4], 1.2, 1))
        gcon.commit(); gcon.close()
        (workspace / "Metro_Edge_Grid.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/edge_grid.gpkg|layername=subbasins</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=weirs</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=db_shards</datasource></maplayer></projectlayers><Layouts></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _build_pristine_harmonic_fcstd(workspace / "cryo_cooling_valve.FCStd")
        _build_blind_atrium(workspace / "rack_thermal_twin.blend", include_bars=False)
        write_multisheet_xlsx(workspace / "Capacity_Master.xlsx", [
            ("Summary", [
                ["Metric", "Value", "Spec"],
                ["Total_Cluster_RAM_MB", ("=SUM(Allocations!B2:B4)", 328.0), "Tight corridor [515.0, 536.0] MB"],
                ["Littles_Law_Concurrency", ("=Allocations!B5*(Allocations!B6/1000)", 78.0), "L = lambda * W"],
                ["Web_Standards_Checksum", ("=SUM(Web_Standards!C2:C17)", 0.0), "16-row live web checksum"],
            ]),
            ("Allocations", [
                ["Component", "Value"],
                ["sqlite_cache_mb", 24.0], ["hot_cache_mb", 24.0], ["telemetry_buffer_mb", 280.0],
                ["arrival_rate_rps", 1200.0], ["target_p99_ms", 58.0],
            ]),
            ("Web_Standards", _shared_web_sheet_rows(zeroed=True)),
        ])
        so = f"Once all 10 arena gates pass simultaneously ({b}all_gates_passed == true{b} via {b}POST http://127.0.0.1:{pport}/api/drc_audit{b}), submit {b}POST http://127.0.0.1:{pport}/api/role_signoff{b} with role and {b}shared_sha256{b} of {b}Capacity_Master.xlsx{b}."
        card_req = f"Upgrade {b}/workspace/briefings/<ROLE>_card.html{b} with high optical contrast ({b}#0f172a{b}/{b}#f8fafc{b}) for headless Chromium 3-viewport verification."

        tickets["DB"].write_text(textwrap.dedent(f"""\
            # Assignment: Principal Database SRE (DB) — 72-Node DAG Cyber-Physical War-Room
            Portal ({b}DISPLAY=:99{b}): {b}http://127.0.0.1:{pport}{b} | Cluster: {b}http://127.0.0.1:{cport}/metrics{b}

            1. Wait for {b}sufficient_window_60s == true{b} in {b}/workspace/cluster/slow_query_ring.json{b} and archive {b}/workspace/forensics/db_fingerprint_60s.json{b}. Purge {b}region_code='CORRUPT_SHARD'{b} and build the 3 composite indexes {b}(account_id, event_ts){b}, {b}(region_code, status){b}, {b}(shard_id, event_ts){b} on {b}ledger_events{b}.
            2. Tune {b}db_tuning.json{b} ({b}sqlite_cache_mb >= 188{b}, {b}checkpoint_batch <= 400{b}) and {b}Allocations!B2{b} in {b}/workspace/Capacity_Master.xlsx{b} inside the tight {b}[515, 536] MB{b} global RAM corridor!
            3. DISCRETE SHARD QUORUM RULE: In {b}db_shards{b} of {b}/workspace/data/edge_grid.gpkg{b}, set {b}wal_quorum >= 2{b} on all 16 shards, and promote AT MOST 6 shards ({b}1 <= promoted_shards_count <= 6{b} with {b}sync_bw_gbps > 2.0{b})! Probe {b}/api/drc_audit{b} ({b}lagging_shards{b}) to identify the 6 write-skewed hot shards and bring {b}db_repl_lag_ms <= 29.0{b}. Register layout {b}DB_Replication_A3{b} in {b}/workspace/Metro_Edge_Grid.qgz{b} and export {b}/workspace/exports/db_replication_atlas.pdf{b}.
            4. {_web_assignment_md("DB", "Web_Standards", "Capacity_Master.xlsx")} {card_req.replace("<ROLE>", "DB")} {so}
        """), encoding="utf-8")

        tickets["APP"].write_text(textwrap.dedent(f"""\
            # Assignment: Backbone DAG & Gateway SRE (APP) — 72-Node DAG Cyber-Physical War-Room
            Portal ({b}DISPLAY=:99{b}): {b}http://127.0.0.1:{pport}{b} | Cluster: {b}http://127.0.0.1:{cport}{b} (Do NOT run hard restart or canary_burst before {b}db_fingerprint_60s.json{b} exists!)

            1. Tune {b}/workspace/cluster/app_gateway.json{b} ({b}hot_cache_mb >= 218{b}, {b}retry_backoff_ms{b} in {b}[150, 600]{b}, {b}max_retries{b} in {b}[1, 3]{b}, {b}cache_ttl_s >= 90{b}, {b}singleflight=true{b}, {b}token_bucket_rps{b} in {b}[950, 1800]{b}) and {b}Allocations!B3{b} in {b}Capacity_Master.xlsx{b} inside the tight {b}[515, 536] MB{b} global RAM corridor.
            2. Optimize the 72-subbasin 6-tier routing DAG ({b}subbasins{b}: {b}green_ha{b} on AT MOST 26 nodes {b}1 <= dag_modified_nodes <= 26{b} with {b}0 <= green_ha <= 0.22 * area_ha{b}) and 24 shapers ({b}weirs{b}: {b}orifice_m2, storage_k_m3, crest_m{b}, avoiding Tier-4 phase resonance near {b}orifice_m2=1.10{b}!) in {b}/workspace/data/edge_grid.gpkg{b} via {b}/api/drc_audit{b} so {b}dag_outlet_100yr <= 55.0{b}, {b}dag_overtopped_weirs == 0{b}, {b}dag_tier5_peak <= 16.0{b}, {b}dag_crit_500_exceed == 0{b}, {b}dag_recharge_balance_idx{b} strictly in {b}[0.315, 0.342]{b}, and {b}dag_total_capex <= 25.80{b}. Register layout {b}Edge_DAG_A3{b} in {b}Metro_Edge_Grid.qgz{b} and export {b}/workspace/exports/edge_reroute_map.pdf{b}.
            3. {_web_assignment_md("APP", "Web_Standards", "Capacity_Master.xlsx")} {card_req.replace("<ROLE>", "APP")} {so}
        """), encoding="utf-8")

        tickets["INFRA"].write_text(textwrap.dedent(f"""\
            # Assignment: Mechanical Cryo-Valve & Thermal Twin Lead (INFRA) — War-Room
            Portal ({b}DISPLAY=:99{b}): {b}http://127.0.0.1:{pport}{b}

            1. Tune {b}/workspace/cluster/infra_daemon.json{b} ({b}telemetry_buffer_mb{b} in {b}[95, 125]{b} inside the tight {b}[515, 536] MB{b} global RAM corridor, {b}log_level="INFO"{b}, {b}liveness_timeout_ms >= 800{b}), purge {b}core_trace.bin{b}, and update {b}Allocations!B4{b} in {b}Capacity_Master.xlsx{b}.
            2. Redesign the 4-part harmonic valve {b}/workspace/cryo_cooling_valve.FCStd{b} so {b}stroke{b} in {b}[18.35, 18.45] mm{b}, {b}max_pa <= 23.5 deg{b}, {b}min_ch >= 3.40 mm{b}, {b}home_gap{b} in {b}[0.16, 0.22] mm{b}, zero collision, Al-7075 {b}mass_tot{b} in {b}[0.600, 0.720] kg{b}, {b}cg_r <= 0.45 mm{b}, and certify via the 20s exclusive solver {b}POST http://127.0.0.1:{pport}/api/cae/valve_solve{b}.
            3. Tune {b}Louver_01..06{b} in {b}/workspace/rack_thermal_twin.blend{b} against the hidden workstation sensor rig in {b}/api/drc_audit{b} ({b}noon_solar_gain <= 0.485{b}, {b}morning_luma >= 0.370{b}). {_web_assignment_md("INFRA", "Web_Standards", "Capacity_Master.xlsx")} {card_req.replace("<ROLE>", "INFRA")} {so}
        """), encoding="utf-8")

        tickets["IC"].write_text(textwrap.dedent(f"""\
            # Assignment: Incident Commander & Aisle Optics Lead (IC) — War-Room
            Portal ({b}DISPLAY=:99{b}): {b}http://127.0.0.1:{pport}{b} | Cluster: {b}http://127.0.0.1:{cport}{b}

            1. Read {b}INCIDENT TOKEN{b} ({b}WARROOM-9913{b}) from {b}<canvas>{b} on {b}DISPLAY=:99{b}. {_web_assignment_md("IC", "Web_Standards", "Capacity_Master.xlsx")}
            2. Without altering {b}Louver_01..06{b}, asymmetrically balance {b}Baffle_01..04{b} and {b}TaskLight_01..04{b} ({b}sum energy <= 360W{b}) in {b}/workspace/rack_thermal_twin.blend{b} via {b}/api/drc_audit{b} until ALL 6 zones {b}comb_zones{b} fall in {b}[0.680, 0.760]{b} with {b}uniformity >= 0.905{b}, exporting {b}/workspace/exports/rack_thermal_forensics.png{b}.
            3. {card_req.replace("<ROLE>", "IC")} After {b}db_fingerprint_60s.json{b} exists and all 10 gates pass, run {b}POST http://127.0.0.1:{cport}/api/canary_burst{b} ({b}p99_ms <= 58.0{b}), export {b}/workspace/exports/INC_Postmortem_RCA.pdf{b} + {b}/workspace/WarRoom_Executive.pptx{b} ({b}WARROOM-9913{b}), post {b}POST http://127.0.0.1:{pport}/api/statuspage/resolve{b} with JSON {b}{{"incident_token": "WARROOM-9913", "canary_p99_ms": <p99>}}{b}, and {so}
        """), encoding="utf-8")

    elif task_id == "UA-15":
        cport = int(meta["cluster_port"])
        build_extreme_case("UA-13", workspace, tickets)
        (workspace / "status_portal").mkdir(parents=True, exist_ok=True)
        (workspace / "raw").mkdir(parents=True, exist_ok=True)
        subprocess.run(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "raw/warroom_vo.wav"), "synth", "10.0", "sine", "320", "vol", "0.50"], check=True, capture_output=True)
        for pg in ("db_wal", "db_quorum", "app_gateway", "app_dag", "infra_valve", "infra_thermal", "ic_timeline", "ic_postmortem"):
            (workspace / f"status_portal/{pg}.html").write_text(
                f'<!doctype html><html><body style="background:#e2e8f0;color:#cbd5e1"><h1>{pg} draft</h1></body></html>\n',
                encoding="utf-8",
            )
        role_pages = {
            "DB": ("db_wal", "db_quorum"),
            "APP": ("app_gateway", "app_dag"),
            "INFRA": ("infra_valve", "infra_thermal"),
            "IC": ("ic_timeline", "ic_postmortem"),
        }
        for r, (p1, p2) in role_pages.items():
            txt = tickets[r].read_text(encoding="utf-8").replace("19631", str(pport)).replace("19630", str(cport)).replace("all 10 arena gates", "all 11 arena gates").replace("all 10 gates", "all 11 gates")
            extra = (
                f"\n5. Status-Portal Requirement: Upgrade BOTH {b}/workspace/status_portal/{p1}.html{b} and {b}/workspace/status_portal/{p2}.html{b} "
                f"with {b}data-warroom-v2=\"ready\"{b} on {b}<html>{b} and high-contrast dark/light styling ({b}#0f172a{b}/{b}#f8fafc{b}) so 24-render Chromium optical E2E passes!\n"
            )
            if r == "IC":
                extra += (
                    f"6. Render **240 individual 3D animation PNG frames** in Blender Cycles ({b}16..24 samples{b}, {b}640x360{b}, animated camera sweep across {b}rack_thermal_twin.blend{b}) into {b}/workspace/reel_frames/{b} ({b}>= 240{b} {b}.png{b} frames preserved on disk!) and encode {b}/workspace/exports/warroom_forensics_240f.mp4{b} ({b}10.0s @ 24fps{b}) "
                    f"muxed with {b}/workspace/raw/warroom_vo.wav{b} mastered to {b}-23.0 +/- 0.4 LUFS{b} ({b}G_IC_3_forensics_240f_ebu_r128_reel{b}).\n"
                )
            tickets[r].write_text(txt + extra, encoding="utf-8")


def solve_extreme_ref(task_id: str, workspace: Path) -> None:
    from PIL import Image
    meta = UA_BY_ID[task_id]; pport = int(meta["portal_port"]); base = f"http://127.0.0.1:{pport}"
    for r in meta["roles"]:
        (workspace / f"briefings/{r}_card.html").write_text(
            f'<!doctype html><html><body style="background:#0f172a;color:#f8fafc"><div style="background:#f8fafc;color:#0f172a;padding:20px"><h1>{r} READY</h1></div></body></html>\n',
            encoding="utf-8",
        )
    if task_id == "UA-12":
        xlsx_p = workspace / "Q4_Enterprise_Master_Model.xlsx"
        fin_rows = [["Unit", "Region", "Gross_kUSD", "NetRev_PostRestate_kUSD", "DirectCost_kUSD", "Levers", "Value"]]
        for idx, (u, gr, dc, ic) in enumerate([r for pg in UA08_BI_PAGES["FIN"] for r in pg]):
            net = gr - ic - (65.0 if u == "EMEA_DACH_Cloud" else 0.0) - (145.0 if u == "APAC_JP_Enterprise" else 0.0)
            lk, lv = (("hedge_ratio", 0.85), ("reserve_kusd", 310.0), ("debt_service_q", 2050.0))[idx] if idx < 3 else ("", "")
            fin_rows.append([u, u.split("_")[0], gr, net, dc, lk, lv])
        update_single_sheet_xlsx(xlsx_p, "Finance_24U", fin_rows)

        dc_rows = [["DC_ID", "Region", "Active_Racks", "Failover_Racks", "Target_PUE", "Row_Cost_kUSD"]]
        tot_act = 0.0
        for idx, row in enumerate([r for pg in UA08_BI_PAGES["OPS"] for r in pg]):
            r_i = idx + 2
            ac, fo, pu = (32.0, 9.0, 1.23) if idx in HUB_10 else (20.0, 5.0, 1.32)
            tot_act += ac
            dc_rows.append([row[0], row[1], ac, fo, pu, (f"=C{r_i}*1.95+D{r_i}*1.15+C{r_i}*(E{r_i}-1.10)*3.6", 70.0)])
        update_single_sheet_xlsx(xlsx_p, "Datacenter_24R", dc_rows)

        sp_rows = [["Territory", "Region", "Open_ARR_kUSD", "Win_Prob", "Price_Mult", "Rebate_Pct", "Weighted_ARR_kUSD"]]
        w_sum = 0.0
        for idx, (tid_s, reg, oarr, _acc) in enumerate([r for pg in UA08_BI_PAGES["SALES"] for r in pg]):
            r_i = idx + 2
            pm, rb = (1.14, 0.06) if idx in HUB_10 else (1.00, 0.00)
            wv = round(oarr * 0.32 * pm * (1.0 - rb), 4); w_sum += wv
            sp_rows.append([tid_s, reg, oarr, 0.32, pm, rb, (f"=C{r_i}*D{r_i}*E{r_i}*(1-F{r_i})", wv)])
        update_single_sheet_xlsx(xlsx_p, "Pipeline_24T", sp_rows)
        update_single_sheet_xlsx(xlsx_p, "Web_Benchmarks", _shared_web_sheet_rows(zeroed=False))

        con = sqlite3.connect(str(workspace / "data/qbr_spatial.gpkg"))
        con.execute("UPDATE dc_sites SET active_racks = ?", (tot_act / 24.0,))
        con.execute("UPDATE sales_territories SET weighted_arr = ?", (w_sum / 24.0,))
        con.commit(); con.close()
        (workspace / "global_qbr_atlas.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/qbr_spatial.gpkg|layername=dc_sites</datasource></maplayer>'
            '<maplayer><datasource>./data/qbr_spatial.gpkg|layername=sales_territories</datasource></maplayer></projectlayers>'
            '<Layouts><Layout name="Global_DC_Capacity_A3"/><Layout name="Sales_Territory_Risk_A3"/></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _solve_blind_atrium(workspace / "hq_flagship_atrium.blend", workspace / "exports/q4_boardroom_3d.png", set_bars=True)
        png_b = (workspace / "exports/q4_boardroom_3d.png").read_bytes()
        for pn in ("DC_Global_Atlas.pdf", "Sales_Territory_Atlas.pdf", "Q4_Board_Briefing.pdf"):
            Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / f"exports/{pn}", "PDF")
        make_simple_pptx(workspace / "Q4_Board_Deck.pptx", ["QBR-2026-Q4-EXTREME"], chart_png_bytes=png_b)
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=300)
        assert drc.get("all_gates_passed") is True, drc
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q4-EXTREME", "noi_kusd": drc["metrics"]["noi_kusd"], "worst_dscr": drc["metrics"]["worst_24q_dscr"], "model_path": str(xlsx_p)})
        sha = sha256_file(xlsx_p)
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": sha}, timeout_s=180)
            assert code == 200, sr

    elif task_id == "UA-15":
        cport = int(meta["cluster_port"])
        (workspace / "reel_frames").mkdir(parents=True, exist_ok=True)
        for fi in range(1, 241):
            Image.new("RGB", (64, 36), (30, fi % 200, 90)).save(workspace / f"reel_frames/frame_{fi:04d}.png")
        for pg in ("db_wal", "db_quorum", "app_gateway", "app_dag", "infra_valve", "infra_thermal", "ic_timeline", "ic_postmortem"):
            (workspace / f"status_portal/{pg}.html").write_text(
                f'<!doctype html><html data-warroom-v2="ready"><body style="background:#0f172a;color:#f8fafc"><div style="background:#f8fafc;color:#0f172a;padding:20px"><h1>{pg}</h1></div></body></html>\n',
                encoding="utf-8",
            )
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=s=640x360:r=24:d=10.0",
            "-i", str(workspace / "raw/warroom_vo.wav"),
            "-filter_complex", "[1:a]loudnorm=I=-23.0:TP=-2.0:LRA=7.0[aout]",
            "-map", "0:v", "-map", "[aout]", "-frames:v", "240",
            "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(workspace / "exports/warroom_forensics_240f.mp4"),
        ], check=True, capture_output=True, timeout=90)
        write_json(workspace / "forensics/db_fingerprint_60s.json", {"sufficient_window_60s": True, "sampled_seconds": 60})
        con = sqlite3.connect(str(workspace / "cluster/prod_ledger.db"))
        con.execute("DELETE FROM ledger_events WHERE region_code = 'CORRUPT_SHARD'")
        con.execute("CREATE INDEX IF NOT EXISTS idx_1 ON ledger_events(account_id, event_ts)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_2 ON ledger_events(region_code, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_3 ON ledger_events(shard_id, event_ts)")
        con.commit(); con.close()
        write_json(workspace / "cluster/db_tuning.json", {"sqlite_cache_mb": 192.0, "checkpoint_batch": 250})
        write_json(workspace / "cluster/app_gateway.json", {"hot_cache_mb": 222.0, "retry_backoff_ms": 240.0, "max_retries": 2, "cache_ttl_s": 180.0, "singleflight": True, "token_bucket_rps": 1250.0})
        write_json(workspace / "cluster/infra_daemon.json", {"telemetry_buffer_mb": 110.0, "log_level": "INFO", "liveness_timeout_ms": 1000.0})
        (workspace / "cluster/disk_vol/core_trace.bin").write_bytes(b"")
        gcon = sqlite3.connect(str(workspace / "data/edge_grid.gpkg"))
        subs = list(gcon.execute("SELECT basin_id, area_ha FROM subbasins ORDER BY area_ha DESC LIMIT 25"))
        for bid, aha in subs:
            gcon.execute("UPDATE subbasins SET green_ha = ? WHERE basin_id = ?", (round(float(aha) * 0.192, 3), bid))
        gcon.execute("UPDATE weirs SET orifice_m2 = 1.72, storage_k_m3 = 26.5, crest_m = 1.45")
        gcon.execute("UPDATE db_shards SET wal_quorum = 2, sync_bw_gbps = 1.5")
        for sid in HOT_SHARDS_6:
            gcon.execute("UPDATE db_shards SET sync_bw_gbps = 8.0 WHERE shard_id = ?", (sid,))
        gcon.commit(); gcon.close()
        (workspace / "Metro_Edge_Grid.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/edge_grid.gpkg|layername=subbasins</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=weirs</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=db_shards</datasource></maplayer></projectlayers>'
            '<Layouts><Layout name="DB_Replication_A3"/><Layout name="Edge_DAG_A3"/></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _solve_harmonic_fcstd(workspace / "cryo_cooling_valve.FCStd")
        code, vr = _post_json(f"{base}/api/cae/valve_solve", {}, timeout_s=150)
        assert code == 200 and vr["certificate"]["valve_passed"] is True, vr
        _solve_blind_atrium(workspace / "rack_thermal_twin.blend", workspace / "exports/rack_thermal_forensics.png", set_bars=False)
        cap_p = workspace / "Capacity_Master.xlsx"
        update_single_sheet_xlsx(cap_p, "Allocations", [
            ["Component", "Value"],
            ["sqlite_cache_mb", 192.0], ["hot_cache_mb", 222.0], ["telemetry_buffer_mb", 110.0],
            ["arrival_rate_rps", 1200.0], ["target_p99_ms", 45.0],
        ])
        update_single_sheet_xlsx(cap_p, "Web_Standards", _shared_web_sheet_rows(zeroed=False))
        png_b = (workspace / "exports/rack_thermal_forensics.png").read_bytes()
        for pn in ("db_replication_atlas.pdf", "edge_reroute_map.pdf", "INC_Postmortem_RCA.pdf"):
            Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / f"exports/{pn}", "PDF")
        make_simple_pptx(workspace / "WarRoom_Executive.pptx", ["WARROOM-9913"], chart_png_bytes=png_b)
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=300)
        assert drc.get("all_gates_passed") is True, drc
        _, burst = _post_json(f"http://127.0.0.1:{cport}/api/canary_burst", {}, timeout_s=300)
        _post_json(f"{base}/api/statuspage/resolve", {"incident_token": "WARROOM-9913", "canary_p99_ms": burst["metrics"]["p99_ms"]})
        sha = sha256_file(cap_p)
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": sha}, timeout_s=180)
            assert code == 200, sr

    elif task_id == "UA-14":
        (workspace / "reel_frames").mkdir(parents=True, exist_ok=True)
        for fi in range(1, 241):
            Image.new("RGB", (64, 36), (fi % 200, 40, 90)).save(workspace / f"reel_frames/frame_{fi:04d}.png")
        for pg in ("fin_summary", "fin_debt", "ops_capacity", "ops_sustainability", "sales_growth", "sales_cohorts", "exec_vision", "exec_guidance"):
            (workspace / f"investor_site/{pg}.html").write_text(
                f'<!doctype html><html data-q4-ir="ready"><body style="background:#0f172a;color:#f8fafc"><div style="background:#f8fafc;color:#0f172a;padding:20px"><h1>{pg}</h1></div></body></html>\n',
                encoding="utf-8",
            )
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=s=640x360:r=24:d=10.0",
            "-i", str(workspace / "raw/investor_vo.wav"),
            "-filter_complex", "[1:a]loudnorm=I=-23.0:TP=-2.0:LRA=7.0[aout]",
            "-map", "0:v", "-map", "[aout]", "-frames:v", "240",
            "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(workspace / "exports/q4_investor_reel_240f.mp4"),
        ], check=True, capture_output=True, timeout=90)
        # Reuse UA-12 workbook/spatial/Cycles solver steps against UA-14 port
        xlsx_p = workspace / "Q4_Enterprise_Master_Model.xlsx"
        fin_rows = [["Unit", "Region", "Gross_kUSD", "NetRev_PostRestate_kUSD", "DirectCost_kUSD", "Levers", "Value"]]
        for idx, (u, gr, dc, ic) in enumerate([r for pg in UA08_BI_PAGES["FIN"] for r in pg]):
            net = gr - ic - (65.0 if u == "EMEA_DACH_Cloud" else 0.0) - (145.0 if u == "APAC_JP_Enterprise" else 0.0)
            lk, lv = (("hedge_ratio", 0.85), ("reserve_kusd", 310.0), ("debt_service_q", 2050.0))[idx] if idx < 3 else ("", "")
            fin_rows.append([u, u.split("_")[0], gr, net, dc, lk, lv])
        update_single_sheet_xlsx(xlsx_p, "Finance_24U", fin_rows)
        dc_rows = [["DC_ID", "Region", "Active_Racks", "Failover_Racks", "Target_PUE", "Row_Cost_kUSD"]]
        tot_act = 0.0
        for idx, row in enumerate([r for pg in UA08_BI_PAGES["OPS"] for r in pg]):
            r_i = idx + 2
            ac, fo, pu = (32.0, 9.0, 1.23) if idx in HUB_10 else (20.0, 5.0, 1.32)
            tot_act += ac
            dc_rows.append([row[0], row[1], ac, fo, pu, (f"=C{r_i}*1.95+D{r_i}*1.15+C{r_i}*(E{r_i}-1.10)*3.6", 70.0)])
        update_single_sheet_xlsx(xlsx_p, "Datacenter_24R", dc_rows)
        sp_rows = [["Territory", "Region", "Open_ARR_kUSD", "Win_Prob", "Price_Mult", "Rebate_Pct", "Weighted_ARR_kUSD"]]
        w_sum = 0.0
        for idx, (tid_s, reg, oarr, _acc) in enumerate([r for pg in UA08_BI_PAGES["SALES"] for r in pg]):
            r_i = idx + 2
            pm, rb = (1.14, 0.06) if idx in HUB_10 else (1.00, 0.00)
            wv = round(oarr * 0.32 * pm * (1.0 - rb), 4); w_sum += wv
            sp_rows.append([tid_s, reg, oarr, 0.32, pm, rb, (f"=C{r_i}*D{r_i}*E{r_i}*(1-F{r_i})", wv)])
        update_single_sheet_xlsx(xlsx_p, "Pipeline_24T", sp_rows)
        update_single_sheet_xlsx(xlsx_p, "Web_Benchmarks", _shared_web_sheet_rows(zeroed=False))
        con = sqlite3.connect(str(workspace / "data/qbr_spatial.gpkg"))
        con.execute("UPDATE dc_sites SET active_racks = ?", (tot_act / 24.0,))
        con.execute("UPDATE sales_territories SET weighted_arr = ?", (w_sum / 24.0,))
        con.commit(); con.close()
        (workspace / "global_qbr_atlas.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/qbr_spatial.gpkg|layername=dc_sites</datasource></maplayer>'
            '<maplayer><datasource>./data/qbr_spatial.gpkg|layername=sales_territories</datasource></maplayer></projectlayers>'
            '<Layouts><Layout name="Global_DC_Capacity_A3"/><Layout name="Sales_Territory_Risk_A3"/></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _solve_blind_atrium(workspace / "hq_flagship_atrium.blend", workspace / "exports/q4_boardroom_3d.png", set_bars=True)
        png_b = (workspace / "exports/q4_boardroom_3d.png").read_bytes()
        for pn in ("DC_Global_Atlas.pdf", "Sales_Territory_Atlas.pdf", "Q4_Board_Briefing.pdf"):
            Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / f"exports/{pn}", "PDF")
        make_simple_pptx(workspace / "Q4_Board_Deck.pptx", ["QBR-2026-Q4-EXTREME"], chart_png_bytes=png_b)
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=300)
        assert drc.get("all_gates_passed") is True, drc
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q4-EXTREME", "noi_kusd": drc["metrics"]["noi_kusd"], "worst_dscr": drc["metrics"]["worst_24q_dscr"], "model_path": str(xlsx_p)})
        sha = sha256_file(xlsx_p)
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": sha}, timeout_s=180)
            assert code == 200, sr

    elif task_id == "UA-13":
        cport = int(meta["cluster_port"])
        write_json(workspace / "forensics/db_fingerprint_60s.json", {"sufficient_window_60s": True, "sampled_seconds": 60})
        con = sqlite3.connect(str(workspace / "cluster/prod_ledger.db"))
        con.execute("DELETE FROM ledger_events WHERE region_code = 'CORRUPT_SHARD'")
        con.execute("CREATE INDEX IF NOT EXISTS idx_1 ON ledger_events(account_id, event_ts)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_2 ON ledger_events(region_code, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_3 ON ledger_events(shard_id, event_ts)")
        con.commit(); con.close()
        write_json(workspace / "cluster/db_tuning.json", {"sqlite_cache_mb": 192.0, "checkpoint_batch": 250})
        write_json(workspace / "cluster/app_gateway.json", {"hot_cache_mb": 222.0, "retry_backoff_ms": 240.0, "max_retries": 2, "cache_ttl_s": 180.0, "singleflight": True, "token_bucket_rps": 1250.0})
        write_json(workspace / "cluster/infra_daemon.json", {"telemetry_buffer_mb": 110.0, "log_level": "INFO", "liveness_timeout_ms": 1000.0})
        (workspace / "cluster/disk_vol/core_trace.bin").write_bytes(b"")

        gcon = sqlite3.connect(str(workspace / "data/edge_grid.gpkg"))
        subs = list(gcon.execute("SELECT basin_id, area_ha FROM subbasins ORDER BY area_ha DESC LIMIT 25"))
        for bid, aha in subs:
            gcon.execute("UPDATE subbasins SET green_ha = ? WHERE basin_id = ?", (round(float(aha) * 0.192, 3), bid))
        gcon.execute("UPDATE weirs SET orifice_m2 = 1.72, storage_k_m3 = 26.5, crest_m = 1.45")
        gcon.execute("UPDATE db_shards SET wal_quorum = 2, sync_bw_gbps = 1.5")
        for sid in HOT_SHARDS_6:
            gcon.execute("UPDATE db_shards SET sync_bw_gbps = 8.0 WHERE shard_id = ?", (sid,))
        gcon.commit(); gcon.close()
        (workspace / "Metro_Edge_Grid.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/edge_grid.gpkg|layername=subbasins</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=weirs</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=db_shards</datasource></maplayer></projectlayers>'
            '<Layouts><Layout name="DB_Replication_A3"/><Layout name="Edge_DAG_A3"/></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _solve_harmonic_fcstd(workspace / "cryo_cooling_valve.FCStd")
        code, vr = _post_json(f"{base}/api/cae/valve_solve", {}, timeout_s=150)
        assert code == 200 and vr["certificate"]["valve_passed"] is True, vr
        _solve_blind_atrium(workspace / "rack_thermal_twin.blend", workspace / "exports/rack_thermal_forensics.png", set_bars=False)
        cap_p = workspace / "Capacity_Master.xlsx"
        update_single_sheet_xlsx(cap_p, "Allocations", [
            ["Component", "Value"],
            ["sqlite_cache_mb", 192.0], ["hot_cache_mb", 222.0], ["telemetry_buffer_mb", 110.0],
            ["arrival_rate_rps", 1200.0], ["target_p99_ms", 45.0],
        ])
        update_single_sheet_xlsx(cap_p, "Web_Standards", _shared_web_sheet_rows(zeroed=False))
        png_b = (workspace / "exports/rack_thermal_forensics.png").read_bytes()
        for pn in ("db_replication_atlas.pdf", "edge_reroute_map.pdf", "INC_Postmortem_RCA.pdf"):
            Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / f"exports/{pn}", "PDF")
        make_simple_pptx(workspace / "WarRoom_Executive.pptx", ["WARROOM-9913"], chart_png_bytes=png_b)
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=300)
        assert drc.get("all_gates_passed") is True, drc
        _, burst = _post_json(f"http://127.0.0.1:{cport}/api/canary_burst", {}, timeout_s=300)
        _post_json(f"{base}/api/statuspage/resolve", {"incident_token": "WARROOM-9913", "canary_p99_ms": burst["metrics"]["p99_ms"]})
        sha = sha256_file(cap_p)
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": sha}, timeout_s=180)
            assert code == 200, sr


def sim_extreme_race(task_id: str, workspace: Path) -> None:
    meta = UA_BY_ID[task_id]; pport = int(meta["portal_port"]); base = f"http://127.0.0.1:{pport}"
    if task_id in ("UA-12", "UA-14"):
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q4-EXTREME", "noi_kusd": 99.0, "worst_dscr": 0.8, "model_path": str(workspace / "Q4_Enterprise_Master_Model.xlsx")})
    else:
        cport = int(meta["cluster_port"])
        _post_json(f"http://127.0.0.1:{cport}/api/restart", {"mode": "hard"})


def grade_extreme_case(task_id: str, workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    meta = UA_BY_ID[task_id]
    lb_s = float(meta["critical_section_lower_bound_s"])
    eff_wall = max(1.0, float(wall_seconds or lb_s))
    eff_score = round(min(1.0, lb_s / eff_wall), 4)
    side = dict(portal_state.get("collateral_side_effects") or {})
    if "total" not in side:
        side["total"] = sum(int(v) for v in side.values() if isinstance(v, (int, float)))
    signoffs = portal_state.get("role_signoffs") or {}
    canon_sha = sha256_file(workspace / meta["canonical_project"])

    if task_id in ("UA-12", "UA-14"):
        drc = eval_ua14_drc(workspace) if task_id == "UA-14" else eval_ua12_drc(workspace)
        g = drc.get("gates") or {}
        mails = portal_state.get("sent_emails") or []; last_m = mails[-1] if mails else {}
        pptx_txt, pptx_img = read_pptx_info(workspace / "Q4_Board_Deck.pptx")
        canary = bool(drc.get("all_gates_passed") and last_m.get("board_token") == "QBR-2026-Q4-EXTREME" and last_m.get("model_sha256") == canon_sha and "QBR-2026-Q4-EXTREME" in pptx_txt and pptx_img and len(signoffs) == 4)
        role_p = {
            "FIN": bool(g.get("G_FIN_1_restated_rev_8210_and_cost_2940") and g.get("G_FIN_2_stress_dscr_ge_1_60_and_cash_window_740_960") and g.get("G_FIN_3_razor_pareto_noi_margin_50_40_to_51_10") and "FIN" in signoffs),
            "OPS": bool(g.get("G_OPS_1_discrete_max_10_modified_dcs_and_p95_le_23_8ms") and g.get("G_OPS_2_failover_24_34pct_and_cost_1550_1820") and g.get("G_OPS_3_blind_cycles_louvers_and_qgis_dc_atlas") and "OPS" in signoffs),
            "SALES": bool(g.get("G_SALES_1_discrete_max_10_repriced_and_weighted_5950_6750") and g.get("G_SALES_2_nrr_ge_116_5_zero_cliff_churn") and g.get("G_SALES_3_qgis_sales_atlas_synced") and "SALES" in signoffs),
            "EXEC": canary,
        }
    else:
        drc = eval_ua15_drc(workspace, burst_mult=1.65) if task_id == "UA-15" else eval_ua13_drc(workspace, burst_mult=1.65)
        g = drc.get("gates") or {}
        poll = int(side.get("observation_pollutions", 0))
        sps = portal_state.get("statuspage_posts") or []
        canary = bool(drc.get("all_gates_passed") and poll == 0 and bool(sps) and sps[-1].get("incident_token") == "WARROOM-9913" and len(signoffs) == 4)
        role_p = {
            "DB": bool(g.get("G_DB_1_indexes_clean_and_max_6_hot_shards_promoted") and g.get("G_DB_2_forensics_60s_and_db_qgis_atlas") and poll == 0 and "DB" in signoffs),
            "APP": bool(g.get("G_APP_1_gateway_and_tight_515_536mb_ram_corridor") and g.get("G_APP_2_dag_72node_max_26_and_narrow_balance_0315_0342") and "APP" in signoffs),
            "INFRA": bool(g.get("G_INF_1_daemon_disk_and_blind_cycles_louvers") and g.get("G_INF_2_cavitation_harmonic_valve_and_20s_cae") and "INFRA" in signoffs),
            "IC": canary,
        }
    ms_score = round(sum(1 for v in g.values() if v) / max(1, len(g)), 4)
    rub_score = round(0.70 * ms_score + 0.30 * (1.0 if canary else 0.0), 4)
    return {
        "task_id": task_id, "arena": meta["arena"], "joint_pass": bool(all(role_p.values()) and canary),
        "canary_passed": canary, "milestone_score": ms_score, "final_rubric_score": rub_score,
        "role_pass": role_p, "passed_roles_count": sum(1 for v in role_p.values() if v),
        "role_signoffs_count": len(signoffs), "gates": g, "metrics": drc.get("metrics") or {},
        "drc_calls_count": int(portal_state.get("drc_calls", 0)),
        "efficiency": {"critical_section_lower_bound_s": lb_s, "actual_wall_s": round(eff_wall, 2), "score": eff_score},
        "collateral_side_effects": side,
    }

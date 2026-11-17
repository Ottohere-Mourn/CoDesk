"""Pristine builders, zero-hint tickets, reference solvers, race simulators, and 4D graders for UA-08..UA-11."""
from __future__ import annotations

import io
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import textwrap
import urllib.request

from tasks.thematic_arenas_v1.suite import make_simple_pptx, read_pptx_info, sha256_file, write_json
from tasks.thematic_arenas_v1.xlsx_utils import update_single_sheet_xlsx, write_multisheet_xlsx
from tasks.ultra_arenas_v1.catalog import UA_BY_ID
from tasks.ultra_arenas_v1.flagship_30m import (
    UA08_BI_PAGES,
    UA08_WEB_SPECS,
    UA09_REAL_BUGS_7,
    UA09_ROUTES_16,
    eval_ua08_drc,
    eval_ua09_drc,
    eval_ua10_drc,
    eval_ua11_drc,
)


def _post_json(url: str, payload: dict, timeout_s: int = 240) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"error": raw}


def _build_pristine_atrium(blend_path: Path, include_bars: bool = False) -> None:
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
            lv.scale = (1.12, 8.0, 0.12)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            lv.rotation_euler = (0.0, math.radians(18.0), 0.0)
            lv.data.materials.append(lmat)
        bmat = bpy.data.materials.new('BaffleMat'); bmat.use_nodes = True
        bmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.90, 0.90, 0.92, 1.0)
        for i in range(4):
            xp = -3.6 + i*2.4
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(xp, 0.0, 2.9))
            bf = bpy.context.active_object; bf.name = f'Baffle_{{i+1:02d}}'; bf.scale = (0.75, 4.0, 1.0)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            bf.data.materials.append(bmat)
            ld = bpy.data.lights.new(f'TaskLightData_{{i+1:02d}}', type='AREA'); ld.energy = 14.0; ld.size = 1.2
            lo = bpy.data.objects.new(f'TaskLight_{{i+1:02d}}', object_data=ld); lo.location = (xp, 0.0, 2.75)
            sc.collection.objects.link(lo)
        if {bool(include_bars)!r}:
            rmat = bpy.data.materials.new('BarMat'); rmat.use_nodes = True
            rmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.14, 0.56, 0.88, 1.0)
            for idx, nm in enumerate(('Bar_NA', 'Bar_EMEA', 'Bar_APAC', 'Bar_LATAM')):
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-3.0 + idx*2.0, -7.2, 0.5))
                bo = bpy.context.active_object; bo.name = nm; bo.scale = (0.6, 0.4, 1.0)
                bo.data.materials.append(rmat)
        sd = bpy.data.lights.new('SolarSunData', type='SUN'); sd.energy = 4.2
        so = bpy.data.objects.new('SolarSun', object_data=sd); so.location = (0, 0, 8.0); sc.collection.objects.link(so)
        cd = bpy.data.cameras.new('PlanCamData'); cd.type = 'ORTHO'; cd.ortho_scale = 13.0
        co = bpy.data.objects.new('PlanCam', object_data=cd); co.location = (0, 0, 3.8); sc.collection.objects.link(co); sc.camera = co
        bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
    """)
    subprocess.run(["blender", "-b", "--python-expr", py], check=True, capture_output=True, timeout=120)


def _solve_atrium(blend_path: Path, out_png: Path, wh: tuple[int, int] = (800, 450), set_bars: bool = False) -> None:
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
            lv.scale = (1.76, 8.0, 0.12)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            lv.rotation_euler = (0.0, math.radians(-14.0), 0.0)
            if lmat: lv.data.materials.append(lmat)
        bmat = bpy.data.materials.get('BaffleMat')
        for i in range(4):
            xp = -3.6 + i*2.4
            old_b = bpy.data.objects.get(f'Baffle_{{i+1:02d}}')
            if old_b: bpy.data.objects.remove(old_b, do_unlink=True)
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(xp, 0.0, 2.9))
            bf = bpy.context.active_object; bf.name = f'Baffle_{{i+1:02d}}'; bf.scale = (1.05, 4.0, 1.0)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            if bmat: bf.data.materials.append(bmat)
            tl = bpy.data.objects[f'TaskLight_{{i+1:02d}}']
            tl.data.energy = 82.0; tl.data.size = 2.2
        if {bool(set_bars)!r}:
            for nm, hz in (('Bar_NA', 3.100), ('Bar_EMEA', 2.275), ('Bar_APAC', 1.835), ('Bar_LATAM', 1.000)):
                bo = bpy.data.objects.get(nm)
                if bo:
                    bo.scale = (0.6, 0.4, hz); bo.location.z = hz / 2.0
        sc.render.engine = 'CYCLES'; sc.cycles.samples = 16
        sc.render.resolution_x = {wh[0]}; sc.render.resolution_y = {wh[1]}
        sc.render.filepath = {str(out_png)!r}
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
    """)
    subprocess.run(["blender", "-b", "--python-expr", py], check=True, capture_output=True, timeout=150)


def _build_pristine_harmonic_fcstd(fcstd_path: Path) -> None:
    py = textwrap.dedent(f"""\
        import FreeCAD, Part
        doc = FreeCAD.newDocument('HarmonicAssy')
        sh = doc.addObject('Spreadsheet::Sheet', 'SystemSpec')
        rows = [
            ('cam_r0_mm', '34.0'), ('cam_e1_mm', '6.0'), ('cam_h2_mm', '0.0'), ('cam_h3_mm', '0.0'),
            ('cam_thick_mm', '16.0'), ('housing_wall_mm', '5.0'), ('housing_inner_r_mm', '58.0'),
            ('follower_offset_mm', '44.0'), ('follower_roller_r_mm', '9.0'),
        ]
        for idx, (k, v) in enumerate(rows, start=1):
            sh.set(f'A{{idx}}', k); sh.set(f'B{{idx}}', v)
        h = doc.addObject('Part::Feature', 'HousingShell')
        h.Shape = Part.makeCylinder(64.0, 28.0).cut(Part.makeCylinder(58.0, 24.0, FreeCAD.Vector(0, 0, 4.0)))
        c = doc.addObject('Part::Feature', 'HarmonicCam')
        c.Shape = Part.makeCylinder(34.0, 16.0, FreeCAD.Vector(6.0, 0, 6.0))
        f = doc.addObject('Part::Feature', 'FollowerLink')
        f.Shape = Part.makeCylinder(9.0, 16.0, FreeCAD.Vector(44.0, 0, 6.0))
        t = doc.addObject('Part::Feature', 'TopCover')
        t.Shape = Part.makeCylinder(64.0, 7.0, FreeCAD.Vector(0, 0, 28.5))
        doc.recompute(); doc.saveAs({str(fcstd_path)!r})
    """)
    subprocess.run(["freecadcmd", "-c", py], check=True, capture_output=True, timeout=90)


def _solve_harmonic_fcstd(fcstd_path: Path, step_a: Path | None = None, step_b: Path | None = None) -> None:
    py = textwrap.dedent(f"""\
        import FreeCAD, Part, math
        doc = FreeCAD.openDocument({str(fcstd_path)!r})
        sh = doc.getObject('SystemSpec')
        r0, e1, h2, h3 = 34.0, 9.20, -1.25, 0.0
        vals = [('cam_r0_mm', r0), ('cam_e1_mm', e1), ('cam_h2_mm', h2), ('cam_h3_mm', h3),
                ('cam_thick_mm', 14.0), ('housing_wall_mm', 4.5), ('housing_inner_r_mm', 60.5),
                ('follower_offset_mm', 51.14), ('follower_roller_r_mm', 9.0)]
        for idx, (_k, v) in enumerate(vals, start=1):
            sh.set(f'B{{idx}}', str(v))
        pts = [FreeCAD.Vector((r0 + e1*math.cos(math.radians(a)) + h2*math.cos(math.radians(2*a)))*math.cos(math.radians(a)),
                              (r0 + e1*math.cos(math.radians(a)) + h2*math.cos(math.radians(2*a)))*math.sin(math.radians(a)), 6.0) for a in range(0, 360, 5)]
        bs = Part.BSplineCurve(); bs.interpolate(pts, PeriodicFlag=True)
        cam_sh = Part.Face(Part.Wire(bs.toShape())).extrude(FreeCAD.Vector(0, 0, 14.0))
        cam_sh = cam_sh.cut(Part.makeCylinder(12.0, 14.0, FreeCAD.Vector(14.0, 0, 6.0)))
        h_sh = Part.makeCylinder(65.0, 26.0).cut(Part.makeCylinder(60.5, 24.0, FreeCAD.Vector(0, 0, 2.0))).cut(Part.makeCylinder(22.0, 2.0))
        f_sh = Part.makeCylinder(9.0, 14.0, FreeCAD.Vector(51.14, 0, 6.0))
        t_sh = Part.makeCylinder(60.0, 8.6, FreeCAD.Vector(0, 0, 26.5)).cut(Part.makeCylinder(16.0, 8.6, FreeCAD.Vector(0, 0, 26.5)))
        parts = [h_sh, cam_sh, f_sh, t_sh]; vols = [float(p.Volume) for p in parts]; tot_v = sum(vols)
        sols = [s for p in parts for s in p.Solids]
        cg_x = sum(float(s.CenterOfMass.x)*float(s.Volume) for s in sols)/tot_v
        need_vx = -cg_x * tot_v
        boss_v = abs(need_vx) / 38.0
        boss_r = math.sqrt(max(3.5, boss_v / (math.pi * 6.0)))
        t_sh = t_sh.fuse(Part.makeCylinder(boss_r, 6.0, FreeCAD.Vector(-38.0 if need_vx < 0 else 38.0, 0, 35.1)))
        doc.getObject('HousingShell').Shape = h_sh
        doc.getObject('HarmonicCam').Shape = cam_sh
        doc.getObject('FollowerLink').Shape = f_sh
        doc.getObject('TopCover').Shape = t_sh
        doc.recompute()
        if {str(step_a) if step_a else ''!r}:
            Part.makeCompound([h_sh, t_sh]).exportStep({str(step_a) if step_a else ''!r})
        if {str(step_b) if step_b else ''!r}:
            Part.makeCompound([cam_sh, f_sh]).exportStep({str(step_b) if step_b else ''!r})
        doc.saveAs({str(fcstd_path)!r})
    """)
    subprocess.run(["freecadcmd", "-c", py], check=True, capture_output=True, timeout=120)


def _shared_web_sheet_rows(zeroed: bool = True) -> list[list]:
    rows: list[list] = [["Key", "Owner_Role", "Numeric_Value", "Source_Note"]]
    for key, val, owner in UA08_WEB_SPECS:
        rows.append([key, owner, 0.0 if zeroed else val, ""])
    return rows


def _web_assignment_md(role: str, sheet_name: str, xlsx_name: str) -> str:
    mapping = {
        "R1": (
            "rows `2..5` (`C2:C5`)",
            "`C2`=`pep8_max_line` (`https://peps.python.org/pep-0008/` code max line length), "
            "`C3`=`pep20_number` (`https://peps.python.org/pep-0020/` PEP number), "
            "`C4`=`pep484_number` (`https://peps.python.org/pep-0484/` PEP number), "
            "`C5`=`dscr_breakeven_ratio` (`https://en.wikipedia.org/wiki/Debt_service_coverage_ratio` breakeven DSCR ratio `1.0`)",
        ),
        "R2": (
            "rows `6..9` (`C6:C9`)",
            "`C6`=`ideal_pue_ratio` (`https://en.wikipedia.org/wiki/Power_usage_effectiveness` ideal PUE `1.0`), "
            "`C7`=`freecad_lgpl_ver` (`https://github.com/FreeCAD/FreeCAD` LGPL license version `2.1`), "
            "`C8`=`sqlite_major_ver` (`https://docs.python.org/3/library/sqlite3.html` SQLite major version `3.0`), "
            "`C9`=`resnet_arxiv_year` (`https://arxiv.org/abs/1512.03385` submission year)",
        ),
        "R3": (
            "rows `10..13` (`C10:C13`)",
            "`C10`=`flask_bsd_clauses` (`https://github.com/pallets/flask` BSD clause count `3`), "
            "`C11`=`requests_apache_ver` (`https://github.com/psf/requests` Apache license version `2.0`), "
            "`C12`=`httpx_bsd_clauses` (`https://github.com/encode/httpx` BSD clause count `3`), "
            "`C13`=`sqlalchemy_mit_flag` (`https://github.com/sqlalchemy/sqlalchemy` `1` if MIT licensed else `0`)",
        ),
        "R4": (
            "rows `14..17` (`C14:C17`)",
            "`C14`=`gpt2_vocab_size` (`https://huggingface.co/openai-community/gpt2` `config.json` `vocab_size`), "
            "`C15`=`bert_hidden_size` (`https://huggingface.co/google-bert/bert-base-uncased` `config.json` `hidden_size`), "
            "`C16`=`transformer_arxiv_year` (`https://arxiv.org/abs/1706.03762` submission year), "
            "`C17`=`gpt3_arxiv_year` (`https://arxiv.org/abs/2005.14165` submission year)",
        ),
    }
    slot = {"FIN": "R1", "FE": "R1", "DB": "R1", "CAD_HOUSING": "R1",
            "OPS": "R2", "DESIGN": "R2", "APP": "R2", "CAD_ROTOR": "R2",
            "SALES": "R3", "CMS": "R3", "INFRA": "R3", "CAE_LIT": "R3"}.get(role, "R4")
    rng, desc = mapping[slot]
    return (
        f"Visit the live external web pages assigned to `{role}` and update ONLY {rng} in shared sheet `{sheet_name}` of `/workspace/{xlsx_name}` "
        f"(preserving all other rows in `{sheet_name}` and all cross-sheet formulas!): {desc}."
    )


def build_flagship_case(task_id: str, workspace: Path, tickets: dict[str, Path]) -> None:
    meta = UA_BY_ID[task_id]
    pport = int(meta["portal_port"])
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    (workspace / "data").mkdir(parents=True, exist_ok=True)

    if task_id == "UA-08":
        fin_rows = [["Unit", "Region", "Gross_kUSD", "NetRev_PostRestate_kUSD", "DirectCost_kUSD", "Levers", "Value"]]
        for i in range(24):
            lk, lv = (("hedge_ratio", 0.15), ("reserve_kusd", 320.0), ("debt_service_q", 2580.0))[i] if i < 3 else ("", "")
            fin_rows.append([f"U_{i+1:02d}", "TBD", 0.0, 0.0, 0.0, lk, lv])
        dc_rows = [["DC_ID", "Region", "Active_Racks", "Failover_Racks", "Target_PUE", "Row_Cost_kUSD"]]
        for i, row in enumerate([r for pg in UA08_BI_PAGES["OPS"] for r in pg], start=2):
            dc_rows.append([row[0], row[1], 14, 1, row[3], (f"=C{i}*1.95+D{i}*1.15+C{i}*(E{i}-1.10)*3.6", 35.0)])
        sp_rows = [["Territory", "Region", "Open_ARR_kUSD", "Win_Prob", "Price_Mult", "Rebate_Pct", "Weighted_ARR_kUSD"]]
        for i in range(2, 26):
            sp_rows.append([f"T_{i-1:02d}", "TBD", 0.0, 0.32, 1.00, 0.00, (f"=C{i}*D{i}*E{i}*(1-F{i})", 0.0)])

        write_multisheet_xlsx(workspace / "Q4_Enterprise_Master_Model.xlsx", [
            ("Executive_Summary", [
                ["KPI", "Value", "Spec"],
                ["Restated_Base_Rev_kUSD", ("=SUM(Finance_24U!D2:D25)", 0.0), "Q4 USD Excl-IC minus APAC & EMEA restatements"],
                ["Direct_Cost_kUSD", ("=SUM(Finance_24U!E2:E25)", 0.0), "Q4 USD Excl-IC direct cost"],
                ["Ops_Capex_Opex_kUSD", ("=SUM(Datacenter_24R!F2:F25)", 0.0), "24-DC rack + cooling budget"],
                ["Sales_Weighted_ARR_kUSD", ("=SUM(Pipeline_24T!G2:G25)", 0.0), "24-territory weighted ARR"],
                ["Quarterly_Debt_Service_kUSD", ("=Finance_24U!G4", 2580.0), "Refinanced quarterly debt service (1950..2350)"],
                ["Net_Operating_Income_kUSD", ("=B2+0.20*B5-B3-B4", 0.0), "Coupled NOI"],
                ["Web_Benchmark_Checksum", ("=SUM(Web_Benchmarks!C2:C17)", 0.0), "16-row 4-role live web checksum"],
            ]),
            ("Finance_24U", fin_rows),
            ("Datacenter_24R", dc_rows),
            ("Pipeline_24T", sp_rows),
            ("Web_Benchmarks", _shared_web_sheet_rows(zeroed=True)),
        ])

        gpkg = workspace / "data/qbr_spatial.gpkg"
        con = sqlite3.connect(str(gpkg))
        con.execute("CREATE TABLE dc_sites(dc_id TEXT PRIMARY KEY, region TEXT, active_racks REAL, target_pue REAL)")
        con.executemany("INSERT INTO dc_sites VALUES(?,?,?,?)", [(f"DC_{i:02d}", "NA", 14.0, 1.38) for i in range(1, 25)])
        con.execute("CREATE TABLE sales_territories(terr_id TEXT PRIMARY KEY, region TEXT, weighted_arr REAL)")
        con.executemany("INSERT INTO sales_territories VALUES(?,?,?)", [(f"T_{i:02d}", "NA", 0.0) for i in range(1, 25)])
        con.commit(); con.close()
        qgs_xml = (
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/qbr_spatial.gpkg|layername=dc_sites</datasource></maplayer>'
            '<maplayer><datasource>./data/qbr_spatial.gpkg|layername=sales_territories</datasource></maplayer></projectlayers>'
            '<Layouts></Layouts></qgis>\n'
        )
        (workspace / "global_qbr_atlas.qgz").write_text(qgs_xml, encoding="utf-8")
        _build_pristine_atrium(workspace / "hq_flagship_atrium.blend", include_bars=True)

        so_note = f"Final Joint Convergence Step: Once ALL 15 arena gates pass simultaneously (`all_gates_passed == true` via `POST http://127.0.0.1:{pport}/api/drc_audit`), submit your mandatory role sign-off to `POST http://127.0.0.1:{pport}/api/role_signoff` (`{{\"role\": \"<ROLE>\", \"shared_sha256\": \"<sha256 of Q4_Enterprise_Master_Model.xlsx>\"}}`). Re-check and reconcile if coupled Pareto metrics shift."
        tickets["FIN"].write_text(textwrap.dedent(f"""\
            # Assignment: VP Finance & Treasury (`FIN`) — Q4 Operating Review Flagship Arena
            Shared Browser BI (`DISPLAY=:99`, 95s SSO TTL, shared `/home/gui/Downloads/bi_view_export.csv`): `http://127.0.0.1:{pport}`

            1. Take `desktop.screenshot` on `DISPLAY=:99` to read the two Board Audit Restatements (`APAC_RETURN_CONTRA` and `EMEA_FX_RESERVE`) and `BOARD TOKEN` from `<canvas>`. Use the Chromium BI controls (`Scope: FIN`, `Filter: Q4/USD/Excl-IC`, `Pages 1..6`) to export all 6 paginated Finance views (`24` business units) and populate `Finance_24U` (`D2:D25` restated net revenue, `E2:E25` direct cost) in `/workspace/Q4_Enterprise_Master_Model.xlsx` without breaking `Executive_Summary` formulas.
            2. {_web_assignment_md("FIN", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")}
            3. Calibrate treasury levers in `Finance_24U` (`G2`=`hedge_ratio` in `[0,1]`, `G3`=`reserve_kusd <= 1050`, `G4`=`debt_service_q` in `[1950, 2600]`) against `POST http://127.0.0.1:{pport}/api/drc_audit` so `worst_24q_dscr >= 1.56`, `min_stress_cash_kusd >= 720.0`, AND global coupled `noi_margin_pct` stays inside `[48.5%, 50.5%]`. Export `/workspace/exports/Treasury_Stress_Audit.pdf` (via LibreOffice) and Inkscape chart `/workspace/exports/ebitda_bridge_300dpi.png`.
            4. {so_note.replace("<ROLE>", "FIN")}
        """), encoding="utf-8")

        tickets["OPS"].write_text(textwrap.dedent(f"""\
            # Assignment: SVP Cloud Infrastructure & Sustainability (`OPS`) — Q4 Operating Review Flagship Arena
            Shared Browser BI (`DISPLAY=:99`, 95s SSO TTL): `http://127.0.0.1:{pport}`

            1. Export `Scope: OPS` (`Pages 1..6`, `Q4/USD/Excl-IC`) in Chromium on `DISPLAY=:99` and optimize `Active_Racks` (`C2:C25`), `Failover_Racks` (`D2:D25`), and `Target_PUE` (`E2:E25`, keeping `F2:F25` formulas intact) in `Datacenter_24R` of `/workspace/Q4_Enterprise_Master_Model.xlsx` via `/api/drc_audit` so `p95_latency_ms <= 24.2` (`throttled_datacenters` empty!), `failover_ratio` in `[0.24, 0.35]`, `ops_cost_kusd` in `[1450, 1880]`, `mean_pue <= 1.29`, and global `noi_margin_pct` in `[48.5%, 50.5%]`.
            2. {_web_assignment_md("OPS", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")}
            3. Sync `active_racks` & `target_pue` into `dc_sites` of `/workspace/data/qbr_spatial.gpkg`, register print layout `Global_DC_Capacity_A3` inside `/workspace/global_qbr_atlas.qgz` (preserving any existing layers/layouts!), and export `/workspace/exports/DC_Global_Atlas.pdf`.
            4. Optimize the 6 roof cooling louvers (`Louver_01..06` width/tilt, without moving `PlanCam`/`AtriumFloor` or interior lights/bars) in `/workspace/hq_flagship_atrium.blend` so 4-pass Cycles raytracing achieves `noon_solar_gain <= 0.495`, `morning_luma >= 0.360`, `afternoon_luma >= 0.420`, and `louver_vol` in `[7.5, 13.5]`.
            5. {so_note.replace("<ROLE>", "OPS")}
        """), encoding="utf-8")

        tickets["SALES"].write_text(textwrap.dedent(f"""\
            # Assignment: CRO Global Revenue & Pricing (`SALES`) — Q4 Operating Review Flagship Arena
            Shared Browser BI (`DISPLAY=:99`, 95s SSO TTL): `http://127.0.0.1:{pport}`

            1. Export `Scope: SALES` (`Pages 1..6`, `Q4/USD/Excl-IC`) in Chromium on `DISPLAY=:99` (`24` territories) into `Pipeline_24T` (`C2:C25` `Open_ARR_kUSD`, keeping `D2:D25=0.32` and `G2:G25` formulas intact) of `/workspace/Q4_Enterprise_Master_Model.xlsx`. Optimize `Price_Mult` (`E2:E25`) and `Rebate_Pct` (`F2:F25`) via `/api/drc_audit` (avoiding undisclosed territory elasticity cliffs!) so `sales_weighted_kusd` in `[5750, 6850]`, `effective_nrr_pct >= 115.0%`, `churn_penalty_kusd <= 48.0`, `mean_rebate <= 0.085`, and coupled `noi_margin_pct` in `[48.5%, 50.5%]`.
            2. {_web_assignment_md("SALES", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")}
            3. Sync converged territory `weighted_arr` into `sales_territories` of `/workspace/data/qbr_spatial.gpkg`, register layout `Sales_Territory_Risk_A3` in `/workspace/global_qbr_atlas.qgz` (preserving any existing layers/layouts!), and export `/workspace/exports/Sales_Territory_Atlas.pdf` + `/workspace/exports/nrr_cohort_curve.png`.
            4. {so_note.replace("<ROLE>", "SALES")}
        """), encoding="utf-8")

        tickets["EXEC"].write_text(textwrap.dedent(f"""\
            # Assignment: Chief of Staff & Board Reporting (`EXEC`) — Q4 Operating Review Flagship Arena
            Shared Browser Portal (`DISPLAY=:99`): `http://127.0.0.1:{pport}`

            1. Read `BOARD TOKEN` (`QBR-2026-Q4-FLAGSHIP`) and regional audit restatements from `<canvas>` on `DISPLAY=:99`. {_web_assignment_md("EXEC", "Web_Benchmarks", "Q4_Enterprise_Master_Model.xlsx")}
            2. Without altering `Louver_01..06`, calibrate `Baffle_01..04` and `TaskLight_01..04` (`sum energy <= 390W`) in `/workspace/hq_flagship_atrium.blend` so combined Cycles 6 floor zones `Z1..Z6` ALL fall inside `[0.635, 0.785]` with `uniformity >= 0.860`, AND scale `Bar_NA, Bar_EMEA, Bar_APAC, Bar_LATAM` Z-heights to match post-restatement regional net revenues (`NA`, `EMEA`, `APAC`, `LATAM`), rendering `/workspace/exports/q4_boardroom_3d.png` (`800x450`).
            3. Build `/workspace/Q4_Board_Deck.pptx` (containing `QBR-2026-Q4-FLAGSHIP` and embedded PNG chart) and `/workspace/exports/Q4_Board_Briefing.pdf`. Once all 15 DRC gates pass, send `POST http://127.0.0.1:{pport}/api/mail/send_board` (`{{"board_token": "QBR-2026-Q4-FLAGSHIP", "noi_kusd": <noi>, "worst_dscr": <dscr>, "model_path": "/workspace/Q4_Enterprise_Master_Model.xlsx"}}`).
            4. {so_note.replace("<ROLE>", "EXEC")}
        """), encoding="utf-8")

    elif task_id == "UA-09":
        sport = int(meta["staging_port"])
        repo = workspace / "nexus-portal"
        (repo / "templates").mkdir(parents=True, exist_ok=True)
        (repo / "static/assets").mkdir(parents=True, exist_ok=True)
        (workspace / "staging_data").mkdir(parents=True, exist_ok=True)
        (workspace / "raw").mkdir(parents=True, exist_ok=True)

        for rt in UA09_ROUTES_16:
            (repo / f"templates/{rt}.html").write_text(
                f'<!doctype html><html><body style="background:#e2e8f0;color:#cbd5e1"><h1>{rt} draft</h1></body></html>\n',
                encoding="utf-8",
            )
        write_json(repo / "portal_config.json", {
            "sqlite_pool_size": 1, "worker_threads": 1, "gzip_level": 1, "query_cache_mb": 8.0,
            "fts_max_results": 0, "annual_discount_pct": -20.0, "enterprise_sla_mult": 0.0,
            "changelog_tz": "PST-8", "csrf_cookie_samesite": False,
        })
        (repo / "static/assets/brand_mark.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48" viewBox="0 0 48 48"><rect width="160" height="48" fill="#0EA5E9"/></svg>\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "releng@nexus.local"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Nexus RelEng"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Seeded v6 staging pre-release with 7 launch blockers"], cwd=repo, check=True, capture_output=True)

        con = sqlite3.connect(str(workspace / "staging_data/nexus.db"))
        con.execute("CREATE TABLE cms_integrations(slug TEXT PRIMARY KEY, title TEXT, license_spdx TEXT, benchmark_num TEXT, asset_file TEXT, published INTEGER)")
        con.execute("CREATE VIRTUAL TABLE cms_fts USING fts5(slug, title, license_spdx, benchmark_num)")
        con.commit(); con.close()

        _build_pristine_atrium(workspace / "product_stage.blend", include_bars=False)
        subprocess.run(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "raw/reel_vo.wav"), "synth", "8.0", "sine", "360", "vol", "0.50"], check=True, capture_output=True)
        write_multisheet_xlsx(workspace / "QA_Master_Matrix.xlsx", [
            ("Summary", [
                ["Metric", "Value", "Target"],
                ["Total_Asset_KB", ("=Assets!B2", 0.0), "Must match /static/assets KB within [120, 1360]"],
                ["Sim_Page_P95_ms", ("=Perf!B2", 999.0), "Must match coupled DRC P95 <= 136.0 ms"],
                ["Web_Benchmark_Checksum", ("=SUM(Web_Benchmarks!C2:C17)", 0.0), "16-row 4-role live web checksum"],
            ]),
            ("Perf", [["Param", "Value"], ["sim_page_p95_ms", 999.0]]),
            ("Assets", [["Param", "Value"], ["total_asset_kb", 0.0]]),
            ("Web_Benchmarks", _shared_web_sheet_rows(zeroed=True)),
        ])

        so_note = f"Final Joint Convergence Step: Once `all_gates_passed == true` via `POST http://127.0.0.1:{pport}/api/drc_audit` and `git status` in `/workspace/nexus-portal` is clean on `main`, submit `POST http://127.0.0.1:{pport}/api/role_signoff` (`{{\"role\": \"<ROLE>\", \"shared_sha256\": \"<sha256 of /workspace/nexus-portal/.git/HEAD>\"}}`)."
        tickets["FE"].write_text(textwrap.dedent(f"""\
            # Assignment: Principal Full-Stack Engineer (`FE`) — Product Launch Flagship Arena
            Live Staging: `http://127.0.0.1:{sport}` | Portal (`DISPLAY=:99`): `http://127.0.0.1:{pport}` | Repo: `/workspace/nexus-portal`

            1. Upgrade all 16 route templates (`{", ".join(UA09_ROUTES_16)}`) in `/workspace/nexus-portal/templates/` with `data-nexus-v6="ready"`, responsive `@media (max-width: 768px)` CSS, and high optical contrast dark/light cards (fixing `BUG-CONTRAST-WASH`!).
            2. Fix all 7 pre-seeded defects across `portal_config.json` and `static/assets/brand_mark.svg` (`annual_discount_pct=20.0`, `enterprise_sla_mult=1.35`, `changelog_tz="UTC"`, `csrf_cookie_samesite=true`, `fts_max_results` in `[10, 100]`, `brand_mark.svg` `viewBox="0 0 160 48"`), and tune `sqlite_pool_size`, `worker_threads`, `gzip_level`, `query_cache_mb` so coupled `sim_page_p95_ms <= 136.0` ms and `staging_ram_mb <= 310.0` MB.
            3. {_web_assignment_md("FE", "Web_Benchmarks", "QA_Master_Matrix.xlsx")} Also update `Perf!B2` in `/workspace/QA_Master_Matrix.xlsx` with converged `sim_page_p95_ms`, commit cleanly to `main`, and `POST http://127.0.0.1:{sport}/api/redeploy`.
            4. {so_note.replace("<ROLE>", "FE")}
        """), encoding="utf-8")

        tickets["DESIGN"].write_text(textwrap.dedent(f"""\
            # Assignment: Creative Director & 3D Technical Artist (`DESIGN`) — Product Launch Flagship Arena
            Showroom: `/workspace/product_stage.blend` | Assets: `/workspace/nexus-portal/static/assets/` | Portal: `http://127.0.0.1:{pport}`

            1. Calibrate `Louver_01..06`, `Baffle_01..04`, and `TaskLight_01..04` in `/workspace/product_stage.blend` so 4-pass Cycles GI passes (`noon_solar_gain <= 0.495`, `morning_luma >= 0.350`, `comb_zones` in `[0.620, 0.790]`, `uniformity >= 0.855`), and render 4 hero stills into `/workspace/nexus-portal/static/assets/`: `hero_front.png` (`1280x640`), `hero_iso.png` (`800x500`), `hero_cutaway.png` (`800x500`), `hero_detail.png` (`800x500`).
            2. Export 6 GIMP feature cards (`feature_card_1..6.png`, `640x400`), 6 Inkscape badges (`badge_1..6.png`, `128x128`), AND a **192-frame (`8.0s @ 24fps`, `640x360`) animated 3D turntable MP4** `hero_turntable_192f.mp4` muxed with `/workspace/raw/reel_vo.wav` mastered to `-23.0 +/- 0.4 LUFS`, keeping total `/static/assets/*` size (across all files in `/static/assets/`) strictly inside `[120, 1360] KB`!
            3. {_web_assignment_md("DESIGN", "Web_Benchmarks", "QA_Master_Matrix.xlsx")} Update `Assets!B2` in `QA_Master_Matrix.xlsx` with final `total_asset_kb`, commit assets to `main`, and redeploy Staging.
            4. {so_note.replace("<ROLE>", "DESIGN")}
        """), encoding="utf-8")

        tickets["CMS"].write_text(textwrap.dedent(f"""\
            # Assignment: Technical Content & Search Lead (`CMS`) — Product Launch Flagship Arena
            Database: `/workspace/staging_data/nexus.db` | Assets: `/workspace/nexus-portal/static/assets/`

            1. Visit live external pages (`flask`, `requests`, `httpx`, `sqlalchemy`, `pydantic`, `gpt2`, `bert-base-uncased`, `arxiv/1706.03762`, `arxiv/1512.03385`, `arxiv/2005.14165`) and publish **32 integration articles** (`published=1`) in `cms_integrations` (including all 10 verified real-web slugs with accurate SPDX/numeric anchors) AND populate the `cms_fts` FTS5 full-text index.
            2. Create **6 integration architecture diagrams** `cms_arch_1.png`..`cms_arch_6.png` (`640x360`) via Inkscape/GIMP in `/workspace/nexus-portal/static/assets/` (keeping total `/static/assets/*` payload within the `1360 KB` budget!), bind all `cms_integrations.asset_file` entries to valid files, and commit cleanly to `main`.
            3. {_web_assignment_md("CMS", "Web_Benchmarks", "QA_Master_Matrix.xlsx")}
            4. {so_note.replace("<ROLE>", "CMS")}
        """), encoding="utf-8")

        tickets["QA"].write_text(textwrap.dedent(f"""\
            # Assignment: Release QA & Readiness Lead (`QA`) — Product Launch Flagship Arena
            Live Staging: `http://127.0.0.1:{sport}` | Portal (`DISPLAY=:99`): `http://127.0.0.1:{pport}`

            1. Audit the initial commit of `/workspace/nexus-portal` (`git log -p -n 1` + CSS/SVG/config) and report ONLY the 7 real pre-seeded defect codes to `POST http://127.0.0.1:{pport}/api/qa/report_defect`: `BUG-ANNUAL-SURCHARGE`, `BUG-ENT-SLA-ZERO`, `BUG-TZ-PST8`, `BUG-CSRF-SAMESITE`, `BUG-BRAND-VIEWBOX`, `BUG-FTS-LIMIT`, `BUG-CONTRAST-WASH`.
            2. {_web_assignment_md("QA", "Web_Benchmarks", "QA_Master_Matrix.xlsx")} Verify `Summary` formulas (`B2:B4`) in `/workspace/QA_Master_Matrix.xlsx` match converged `total_asset_kb` and `sim_page_p95_ms`, and generate `/workspace/exports/QA_Release_Report.pdf` + `/workspace/QA_Launch_Deck.pptx` (`NEXUS-V6-FLAGSHIP`).
            3. Once all 11 DRC gates pass and `git status` on `main` is clean, submit `POST http://127.0.0.1:{pport}/api/qa/release_signoff` (`{{"release_token": "NEXUS-V6-FLAGSHIP", "git_commit": "<HEAD_sha>"}}`).
            4. {so_note.replace("<ROLE>", "QA")}
        """), encoding="utf-8")

    elif task_id == "UA-10":
        cport = int(meta["cluster_port"])
        cdir = workspace / "cluster"
        (cdir / "disk_vol").mkdir(parents=True, exist_ok=True)
        (workspace / "forensics").mkdir(parents=True, exist_ok=True)

        con = sqlite3.connect(str(cdir / "prod_ledger.db"))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE ledger_events(id INTEGER PRIMARY KEY, account_id TEXT, region_code TEXT, shard_id TEXT, status TEXT, event_ts INTEGER, amount_cents INTEGER)")
        rows = [(i, f"ACC-{i%120:03d}", ("NA", "EMEA", "APAC", "LATAM")[i%4], f"SHD-{i%16:02d}", "SETTLED", 1715000000 + i, 900 + (i%400)) for i in range(1, 12001)]
        rows += [(12000 + j, "ACC-BAD", "CORRUPT_SHARD", "SHD-99", "CORRUPT", 0, -1) for j in range(1, 25)]
        con.executemany("INSERT INTO ledger_events VALUES(?,?,?,?,?,?,?)", rows)
        con.commit(); con.close()

        write_json(cdir / "db_tuning.json", {"sqlite_cache_mb": 24, "checkpoint_batch": 5000})
        write_json(cdir / "app_gateway.json", {"hot_cache_mb": 24, "retry_backoff_ms": 0, "max_retries": 12, "cache_ttl_s": 0, "singleflight": False, "token_bucket_rps": 150})
        write_json(cdir / "infra_daemon.json", {"telemetry_buffer_mb": 280, "log_level": "TRACE_ALL", "liveness_timeout_ms": 40})
        (cdir / "disk_vol/core_trace.bin").write_bytes(b"X" * (520 * 1024))

        gcon = sqlite3.connect(str(workspace / "data/edge_grid.gpkg"))
        gcon.execute("CREATE TABLE edge_pops(pop_id TEXT PRIMARY KEY, region TEXT, cable_status TEXT, capacity_gbps REAL, assigned_traffic_gbps REAL, base_rtt_ms REAL, cost_per_gbps REAL)")
        for i in range(1, 49):
            sev = "SEVERED" if i in (4, 11, 19, 27, 35, 43) else "ACTIVE"
            gcon.execute("INSERT INTO edge_pops VALUES(?,?,?,?,?,?,?)", (f"POP_{i:02d}", ("NA","EMEA","APAC","LATAM")[(i-1)//12], sev, 34.0, 20.0, 24.0 + (i%6)*2.1, round(0.068 + (i%5)*0.003, 4)))
        gcon.execute("CREATE TABLE db_shards(shard_id TEXT PRIMARY KEY, region TEXT, sync_bw_gbps REAL, wal_quorum INTEGER)")
        for i in range(1, 17):
            gcon.execute("INSERT INTO db_shards VALUES(?,?,?,?)", (f"SHD_{i:02d}", ("NA","EMEA","APAC","LATAM")[(i-1)//4], 1.2, 1))
        gcon.commit(); gcon.close()
        (workspace / "Metro_Edge_Grid.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/edge_grid.gpkg|layername=edge_pops</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=db_shards</datasource></maplayer></projectlayers><Layouts></Layouts></qgis>\n',
            encoding="utf-8",
        )

        _build_pristine_harmonic_fcstd(workspace / "cryo_cooling_valve.FCStd")
        _build_pristine_atrium(workspace / "rack_thermal_twin.blend", include_bars=False)
        write_multisheet_xlsx(workspace / "Capacity_Master.xlsx", [
            ("Summary", [
                ["Metric", "Value", "Spec"],
                ["Total_Cluster_RAM_MB", ("=SUM(Allocations!B2:B4)", 328.0), "Strict global ceiling <= 540.0 MB"],
                ["Littles_Law_Concurrency", ("=Allocations!B5*(Allocations!B6/1000)", 78.0), "L = lambda * W"],
                ["Web_Standards_Checksum", ("=SUM(Web_Standards!C2:C17)", 0.0), "16-row 4-role live web checksum"],
            ]),
            ("Allocations", [
                ["Component", "Value"],
                ["sqlite_cache_mb", 24.0], ["hot_cache_mb", 24.0], ["telemetry_buffer_mb", 280.0],
                ["arrival_rate_rps", 1200.0], ["target_p99_ms", 58.0],
            ]),
            ("Web_Standards", _shared_web_sheet_rows(zeroed=True)),
        ])
        (workspace / "INC_Postmortem_RCA.md").write_text("# Cyber-Physical Incident War-Room RCA\n\n## DB\nPENDING\n\n## APP\nPENDING\n\n## INFRA\nPENDING\n\n## IC\nPENDING\n", encoding="utf-8")

        so_note = f"Final Joint Convergence Step: Once `all_gates_passed == true` via `POST http://127.0.0.1:{pport}/api/drc_audit`, submit `POST http://127.0.0.1:{pport}/api/role_signoff` (`{{\"role\": \"<ROLE>\", \"shared_sha256\": \"<sha256 of Capacity_Master.xlsx>\"}}`)."
        tickets["DB"].write_text(textwrap.dedent(f"""\
            # Assignment: Principal Database SRE (`DB`) — Cyber-Physical Incident War-Room
            Console (`DISPLAY=:99`): `http://127.0.0.1:{pport}` | Cluster: `http://127.0.0.1:{cport}/metrics`

            1. Wait until `/workspace/cluster/slow_query_ring.json` reaches `sufficient_window_60s == true` (>= 60s undisturbed live sampling) and archive it to `/workspace/forensics/db_fingerprint_60s.json`.
            2. Delete corrupt rows (`region_code = 'CORRUPT_SHARD'`) and create 3 composite indexes `(account_id, event_ts)`, `(region_code, status)`, `(shard_id, event_ts)` on `ledger_events` in `/workspace/cluster/prod_ledger.db`. Tune `db_tuning.json` (`sqlite_cache_mb >= 185`, `checkpoint_batch <= 400`) and `Allocations!B2` in `/workspace/Capacity_Master.xlsx` inside the global **540 MB** cluster RAM cap!
            3. Tune `db_shards` in `/workspace/data/edge_grid.gpkg` (`sync_bw_gbps >= 6.0` so `db_repl_lag_ms <= 32.0`, `wal_quorum >= 2`, keeping coupled transit+replication cost `<= 84.0 kUSD/h`), add layout `DB_Replication_A3` to `/workspace/Metro_Edge_Grid.qgz`, and export `/workspace/exports/db_replication_atlas.pdf`.
            4. {_web_assignment_md("DB", "Web_Standards", "Capacity_Master.xlsx")}
            5. {so_note.replace("<ROLE>", "DB")}
        """), encoding="utf-8")

        tickets["APP"].write_text(textwrap.dedent(f"""\
            # Assignment: Edge Traffic & Gateway SRE (`APP`) — Cyber-Physical Incident War-Room
            Console (`DISPLAY=:99`): `http://127.0.0.1:{pport}` | Cluster: `http://127.0.0.1:{cport}` (DO NOT trigger `mode="hard"` restart or `/api/canary_burst` until `/workspace/forensics/db_fingerprint_60s.json` is archived!)

            1. Stabilize `/workspace/cluster/app_gateway.json` (`hot_cache_mb >= 215`, `retry_backoff_ms` in `[150, 600]`, `max_retries` in `[1, 3]`, `cache_ttl_s >= 90`, `singleflight = true`, `token_bucket_rps` in `[950, 1800]`) and update `Allocations!B3` in `/workspace/Capacity_Master.xlsx` within the **540 MB** global RAM cap.
            2. Rebalance `assigned_traffic_gbps` across the 48 POPs in `/workspace/data/edge_grid.gpkg` (`edge_pops`: total `960.0 Gbps`, all 6 `SEVERED` cables = `0.0 Gbps`, max POP utilization `<= 0.74` under non-linear queuing `4.2*u/(1-u)`, weighted RTT `<= 48.5 ms`, total transit+DB replication cost `<= 84.0 kUSD/h`), add layout `Edge_Reroute_A3` to `/workspace/Metro_Edge_Grid.qgz` (preserving existing layouts!), and export `/workspace/exports/edge_reroute_map.pdf`.
            3. {_web_assignment_md("APP", "Web_Standards", "Capacity_Master.xlsx")}
            4. {so_note.replace("<ROLE>", "APP")}
        """), encoding="utf-8")

        tickets["INFRA"].write_text(textwrap.dedent(f"""\
            # Assignment: Datacenter Mechanical/Thermal & Daemon Lead (`INFRA`) — Cyber-Physical War-Room
            Console (`DISPLAY=:99`): `http://127.0.0.1:{pport}` | Valve CAD: `/workspace/cryo_cooling_valve.FCStd`

            1. Fix `/workspace/cluster/infra_daemon.json` (`telemetry_buffer_mb` in `[90, 135]` within the **540 MB** global RAM cap, `log_level="INFO"`, `liveness_timeout_ms >= 800`), clear `/workspace/cluster/disk_vol/core_trace.bin` (< 100 KB), and update `Allocations!B4` in `/workspace/Capacity_Master.xlsx`.
            2. Redesign the 4-part harmonic liquid-cooling actuator `/workspace/cryo_cooling_valve.FCStd` (`SystemSpec` + 3D BRep solids `HousingShell`, `HarmonicCam`, `FollowerLink`, `TopCover` with profile `R(phi) = cam_r0 + cam_e1*cos(phi) + cam_h2*cos(2*phi) + cam_h3*cos(3*phi)`): `stroke` in `[18.32, 18.48] mm`, pressure angle `<= 25.5 deg`, 72-angle cam-housing clearance `>= 3.40 mm`, home film gap in `[0.15, 0.23] mm`, zero boolean collision, Al-7075 (`2.81 g/cm3`) total mass `<= 0.855 kg`, CG radial offset `<= 0.65 mm`, then certify via exclusive 18s solver `POST http://127.0.0.1:{pport}/api/cae/valve_solve`.
            3. Tune `Louver_01..06` in `/workspace/rack_thermal_twin.blend` so Cycles `noon_solar_gain <= 0.495` and `morning_luma >= 0.355`. {_web_assignment_md("INFRA", "Web_Standards", "Capacity_Master.xlsx")}
            4. {so_note.replace("<ROLE>", "INFRA")}
        """), encoding="utf-8")

        tickets["IC"].write_text(textwrap.dedent(f"""\
            # Assignment: Incident Commander & Digital Twin Lead (`IC`) — Cyber-Physical War-Room
            Console (`DISPLAY=:99`): `http://127.0.0.1:{pport}` | Cluster: `http://127.0.0.1:{cport}`

            1. Read `INCIDENT TOKEN` (`WARROOM-9910`) from `<canvas>` on `DISPLAY=:99`. {_web_assignment_md("IC", "Web_Standards", "Capacity_Master.xlsx")} Ensure `Summary` formulas (`B2:B4`) in `/workspace/Capacity_Master.xlsx` remain intact and match live RAM configs (`<= 540 MB`).
            2. Without altering `Louver_01..06`, calibrate `Baffle_01..04` and `TaskLight_01..04` in `/workspace/rack_thermal_twin.blend` so combined Cycles 6 aisle zones `Z1..Z6` fall in `[0.635, 0.785]` (`uniformity >= 0.860`), rendering `/workspace/exports/rack_thermal_forensics.png`.
            3. ONLY after `/workspace/forensics/db_fingerprint_60s.json` exists and all DRC gates pass, run `POST http://127.0.0.1:{cport}/api/canary_burst` (1.6x surge -> `p99_ms <= 58.0`, `error_rate == 0.0`), export `/workspace/exports/INC_Postmortem_RCA.pdf` + `/workspace/WarRoom_Executive.pptx`, and post `POST http://127.0.0.1:{pport}/api/statuspage/resolve` (`{{"incident_token": "WARROOM-9910", "canary_p99_ms": <p99>}}`).
            4. {so_note.replace("<ROLE>", "IC")}
        """), encoding="utf-8")

    elif task_id == "UA-11":
        for sub in ("raw", "vfx", "audio", "exports"):
            (workspace / sub).mkdir(parents=True, exist_ok=True)
        _build_pristine_harmonic_fcstd(workspace / "harmonic_actuator.FCStd")
        _build_pristine_atrium(workspace / "studio_cutaway.blend", include_bars=False)
        subprocess.run(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "raw/narration_20s.wav"), "synth", "20.0", "sine", "330", "vol", "0.52"], check=True, capture_output=True)
        write_multisheet_xlsx(workspace / "Engineering_Master_BOM.xlsx", [
            ("Summary", [
                ["Metric", "Value", "Notes"],
                ["Total_Volume_cm3", ("=SUM(Parts!B2:B5)", 0.0), "Sum of 4 CAD solids in cm3"],
                ["Total_Mass_g", ("=B2*2.81", 0.0), "Al-7075 mass in grams (must match CAD within 4g)"],
                ["Web_Literature_Checksum", ("=SUM(Web_Literature!C2:C17)", 0.0), "16-row 4-role live web checksum"],
            ]),
            ("Parts", [
                ["Solid", "Volume_cm3"],
                ["HousingShell", 0.0], ["HarmonicCam", 0.0], ["FollowerLink", 0.0], ["TopCover", 0.0],
            ]),
            ("Web_Literature", _shared_web_sheet_rows(zeroed=True)),
        ])

        so_note = f"Final Joint Convergence Step: Once `all_gates_passed == true` via `POST http://127.0.0.1:{pport}/api/drc_audit`, submit `POST http://127.0.0.1:{pport}/api/role_signoff` (`{{\"role\": \"<ROLE>\", \"shared_sha256\": \"<sha256 of harmonic_actuator.FCStd>\"}}`)."
        tickets["CAD_HOUSING"].write_text(textwrap.dedent(f"""\
            # Assignment: Structural Housing & Balancing Cover Lead (`CAD_HOUSING`) — Flagship Actuator Arena
            Assembly: `/workspace/harmonic_actuator.FCStd` | Portal (`DISPLAY=:99`): `http://127.0.0.1:{pport}`

            1. Optimize `HousingShell` (`housing_wall_mm`, `housing_inner_r_mm`, lightening cuts) and `TopCover` (solid volume `>= 82000 mm3` + eccentric counterweight boss to cancel cam/follower CG offset!) in `/workspace/harmonic_actuator.FCStd` without altering `HarmonicCam`/`FollowerLink`, achieving 72-angle cam-housing clearance `>= 3.40 mm`, zero boolean collision across all 4 solids, total 4-part Al-7075 (`2.81 g/cm3`) mass `<= 0.855 kg`, and static CG radial offset `<= 0.65 mm`. Export `/workspace/exports/housing_cover.step`.
            2. {_web_assignment_md("CAD_HOUSING", "Web_Literature", "Engineering_Master_BOM.xlsx")}
            3. {so_note.replace("<ROLE>", "CAD_HOUSING")}
        """), encoding="utf-8")

        tickets["CAD_ROTOR"].write_text(textwrap.dedent(f"""\
            # Assignment: Harmonic Cam & Hydrodynamic Follower Lead (`CAD_ROTOR`) — Flagship Actuator Arena
            Assembly: `/workspace/harmonic_actuator.FCStd` | Portal (`DISPLAY=:99`): `http://127.0.0.1:{pport}`

            1. Synthesize `HarmonicCam` (`R(phi) = cam_r0 + cam_e1*cos(phi) + cam_h2*cos(2*phi) + cam_h3*cos(3*phi)` in `SystemSpec` + 3D BRep solid with pocket cuts) and `FollowerLink` (`follower_offset_mm`, `follower_roller_r_mm`) in `/workspace/harmonic_actuator.FCStd` so peak-to-peak `stroke` is strictly in `[18.34, 18.46] mm`, max pressure angle across 72 steps `<= 25.5 deg`, home hydrodynamic film gap `distToShape` in `[0.15, 0.23] mm`, zero collision with `HousingShell`/`TopCover`, and total 4-part mass `<= 0.855 kg`. Export `/workspace/exports/cam_follower.step`.
            2. {_web_assignment_md("CAD_ROTOR", "Web_Literature", "Engineering_Master_BOM.xlsx")}
            3. {so_note.replace("<ROLE>", "CAD_ROTOR")}
        """), encoding="utf-8")

        tickets["CAE_LIT"].write_text(textwrap.dedent(f"""\
            # Assignment: Exclusive CAE Certification & Literature BOM Lead (`CAE_LIT`) — Flagship Actuator Arena
            Portal (`DISPLAY=:99`): `http://127.0.0.1:{pport}` | BOM: `/workspace/Engineering_Master_BOM.xlsx`

            1. Optimize the 6 studio skylight louvers (`Louver_01..06`) in `/workspace/studio_cutaway.blend` so Cycles `noon_solar_gain <= 0.495` and `morning_luma >= 0.355`.
            2. Once `harmonic_actuator.FCStd` kinematics & mass converge, run the 20s single-seat exclusive CAE solver (`POST http://127.0.0.1:{pport}/api/cae/exclusive_solve` with `{{"review_token": "AERO-ACT-FLAGSHIP"}}`; retry on `409`), update `Parts!B2:B5` (`Volume_cm3`) in `/workspace/Engineering_Master_BOM.xlsx` keeping `Summary` formulas intact, and export `/workspace/exports/Engineering_Whitepaper.pdf` via LibreOffice.
            3. {_web_assignment_md("CAE_LIT", "Web_Literature", "Engineering_Master_BOM.xlsx")}
            4. {so_note.replace("<ROLE>", "CAE_LIT")}
        """), encoding="utf-8")

        tickets["MEDIA_PUB"].write_text(textwrap.dedent(f"""\
            # Assignment: Studio Visualization & 480-Frame Broadcast Master Producer (`MEDIA_PUB`)
            Studio: `/workspace/studio_cutaway.blend` | Master: `/workspace/exports/actuator_master_480f.mp4` | Portal: `http://127.0.0.1:{pport}`

            1. Read `REVIEW TOKEN` (`AERO-ACT-FLAGSHIP`) from `<canvas>` on `DISPLAY=:99`. Without altering `Louver_01..06`, calibrate `Baffle_01..04` and `TaskLight_01..04` in `/workspace/studio_cutaway.blend` so combined Cycles 6 zones `Z1..Z6` land in `[0.635, 0.785]` (`uniformity >= 0.860`), rendering `/workspace/exports/cutaway_beauty.png` (`1280x720`).
            2. Produce the `20.0s` (`480` frames @ `24fps`, `1280x720`) H.264+AAC broadcast master `/workspace/exports/actuator_master_480f.mp4` within strict BT.709 legal luma `[16, 235]` (`YMIN >= 16`, `YMAX <= 235`) and EBU-R128 `-23.0 +/- 0.35 LUFS` from `/workspace/raw/narration_20s.wav`.
            3. {_web_assignment_md("MEDIA_PUB", "Web_Literature", "Engineering_Master_BOM.xlsx")} Once all DRC gates pass, publish via `POST http://127.0.0.1:{pport}/api/media/publish` (`{{"release_token": "AERO-ACT-FLAGSHIP", "mp4_path": "/workspace/exports/actuator_master_480f.mp4"}}`).
            4. {so_note.replace("<ROLE>", "MEDIA_PUB")}
        """), encoding="utf-8")
    else:
        raise ValueError(task_id)


def solve_flagship_ref(task_id: str, workspace: Path) -> None:
    from PIL import Image, ImageDraw
    meta = UA_BY_ID[task_id]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"

    if task_id == "UA-08":
        xlsx_p = workspace / "Q4_Enterprise_Master_Model.xlsx"
        fin_rows = [["Unit", "Region", "Gross_kUSD", "NetRev_PostRestate_kUSD", "DirectCost_kUSD", "Levers", "Value"]]
        flat_fin = [r for pg in UA08_BI_PAGES["FIN"] for r in pg]
        for idx, (u, gr, dc, ic) in enumerate(flat_fin):
            net = gr - ic
            if u == "EMEA_DACH_Cloud": net -= 65.0
            if u == "APAC_JP_Enterprise": net -= 145.0
            lk, lv = (("hedge_ratio", 0.85), ("reserve_kusd", 880.0), ("debt_service_q", 2050.0))[idx] if idx < 3 else ("", "")
            fin_rows.append([u, u.split("_")[0], gr, net, dc, lk, lv])
        update_single_sheet_xlsx(xlsx_p, "Finance_24U", fin_rows)

        dc_rows = [["DC_ID", "Region", "Active_Racks", "Failover_Racks", "Target_PUE", "Row_Cost_kUSD"]]
        for i, row in enumerate([r for pg in UA08_BI_PAGES["OPS"] for r in pg], start=2):
            dc_rows.append([row[0], row[1], 26.0, 7.0, 1.27, (f"=C{i}*1.95+D{i}*1.15+C{i}*(E{i}-1.10)*3.6", 74.662)])
        update_single_sheet_xlsx(xlsx_p, "Datacenter_24R", dc_rows)

        sp_rows = [["Territory", "Region", "Open_ARR_kUSD", "Win_Prob", "Price_Mult", "Rebate_Pct", "Weighted_ARR_kUSD"]]
        elast_caps = [1.11, 1.09, 1.06, 1.04, 1.10, 1.07, 1.05, 1.03, 1.10, 1.08, 1.06, 1.04, 1.09, 1.06, 1.04, 1.02, 1.11, 1.08, 1.06, 1.05, 1.04, 1.03, 1.02, 1.02]
        flat_sp = [r for pg in UA08_BI_PAGES["SALES"] for r in pg]
        w_sum = 0.0
        for idx, (tid_s, reg, oarr, _acc) in enumerate(flat_sp):
            r = idx + 2
            pm = min(elast_caps[idx], 1.075)
            rb = 0.055
            w_val = round(oarr * 0.32 * pm * (1.0 - rb), 4)
            w_sum += w_val
            sp_rows.append([tid_s, reg, oarr, 0.32, pm, rb, (f"=C{r}*D{r}*E{r}*(1-F{r})", w_val)])
        update_single_sheet_xlsx(xlsx_p, "Pipeline_24T", sp_rows)
        update_single_sheet_xlsx(xlsx_p, "Web_Benchmarks", _shared_web_sheet_rows(zeroed=False))

        con = sqlite3.connect(str(workspace / "data/qbr_spatial.gpkg"))
        con.execute("UPDATE dc_sites SET active_racks = 26.0, target_pue = 1.27")
        con.execute("UPDATE sales_territories SET weighted_arr = ?", (w_sum / 24.0,))
        con.commit(); con.close()
        (workspace / "global_qbr_atlas.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/qbr_spatial.gpkg|layername=dc_sites</datasource></maplayer>'
            '<maplayer><datasource>./data/qbr_spatial.gpkg|layername=sales_territories</datasource></maplayer></projectlayers>'
            '<Layouts><Layout name="Global_DC_Capacity_A3"/><Layout name="Sales_Territory_Risk_A3"/></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _solve_atrium(workspace / "hq_flagship_atrium.blend", workspace / "exports/q4_boardroom_3d.png", wh=(800, 450), set_bars=True)
        png_b = (workspace / "exports/q4_boardroom_3d.png").read_bytes()
        for pn in ("Treasury_Stress_Audit.pdf", "DC_Global_Atlas.pdf", "Sales_Territory_Atlas.pdf", "Q4_Board_Briefing.pdf"):
            Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / f"exports/{pn}", "PDF")
        for gn in ("ebitda_bridge_300dpi.png", "nrr_cohort_curve.png"):
            Image.new("RGB", (640, 360), (20, 40, 70)).save(workspace / f"exports/{gn}")
        make_simple_pptx(workspace / "Q4_Board_Deck.pptx", ["QBR-2026-Q4-FLAGSHIP"], chart_png_bytes=png_b)
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=240)
        assert drc.get("all_gates_passed") is True, drc
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q4-FLAGSHIP", "noi_kusd": drc["metrics"]["noi_kusd"], "worst_dscr": drc["metrics"]["worst_24q_dscr"], "model_path": str(xlsx_p)})
        sha = sha256_file(xlsx_p)
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": sha})
            assert code == 200, sr

    elif task_id == "UA-09":
        sport = int(meta["staging_port"])
        repo = workspace / "nexus-portal"; assets = repo / "static/assets"
        for rt in UA09_ROUTES_16:
            (repo / f"templates/{rt}.html").write_text(
                f'<!doctype html><html data-nexus-v6="ready"><head><style>@media (max-width:768px){{.box{{padding:8px}}}}</style></head>'
                f'<body style="background:#0f172a;color:#f8fafc"><div style="background:#f8fafc;color:#0f172a;padding:18px"><h1>{rt}</h1></div></body></html>\n',
                encoding="utf-8",
            )
        write_json(repo / "portal_config.json", {
            "sqlite_pool_size": 12, "worker_threads": 8, "gzip_level": 5, "query_cache_mb": 24.0,
            "fts_max_results": 50, "annual_discount_pct": 20.0, "enterprise_sla_mult": 1.35,
            "changelog_tz": "UTC", "csrf_cookie_samesite": True,
        })
        (assets / "brand_mark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48" viewBox="0 0 160 48"><rect width="160" height="48" fill="#0EA5E9"/></svg>\n', encoding="utf-8")
        _solve_atrium(workspace / "product_stage.blend", assets / "hero_front.png", wh=(1280, 640), set_bars=False)
        for fn, wh in (("hero_front.png", (1280, 640)), ("hero_iso.png", (800, 500)), ("hero_cutaway.png", (800, 500)), ("hero_detail.png", (800, 500))):
            im = Image.new("RGB", wh, (14, 22, 38)); ImageDraw.Draw(im).rectangle([80, 80, wh[0]-80, wh[1]-80], fill=(42, 156, 224)); im.save(assets / fn, optimize=True)
        for i in range(1, 7):
            Image.new("RGB", (640, 400), (22, 88, 142)).save(assets / f"feature_card_{i}.png", optimize=True)
            Image.new("RGB", (128, 128), (14, 165, 233)).save(assets / f"badge_{i}.png", optimize=True)
            Image.new("RGB", (640, 360), (28, 64, 110)).save(assets / f"cms_arch_{i}.png", optimize=True)
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=s=640x360:r=24:d=8.0",
            "-i", str(workspace / "raw/reel_vo.wav"),
            "-filter_complex", "[1:a]loudnorm=I=-23.0:TP=-2.0:LRA=7.0[aout]",
            "-map", "0:v", "-map", "[aout]", "-frames:v", "192",
            "-c:v", "libx264", "-crf", "31", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k",
            str(assets / "hero_turntable_192f.mp4"),
        ], check=True, capture_output=True, timeout=90)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Nexus v6 16-route flagship GA"], cwd=repo, check=True, capture_output=True)
        _post_json(f"http://127.0.0.1:{sport}/api/redeploy", {})

        con = sqlite3.connect(str(workspace / "staging_data/nexus.db"))
        seeds = [
            ("flask", "Flask", "BSD-3-Clause", "3.0", "cms_arch_1.png", 1),
            ("requests", "Requests", "Apache-2.0", "2.32", "cms_arch_2.png", 1),
            ("httpx", "HTTPX", "BSD-3-Clause", "0.27", "cms_arch_3.png", 1),
            ("sqlalchemy", "SQLAlchemy", "MIT", "2.0", "cms_arch_4.png", 1),
            ("pydantic", "Pydantic", "MIT", "2.9", "cms_arch_5.png", 1),
            ("gpt2", "GPT-2", "MIT", "50257", "cms_arch_6.png", 1),
            ("bert", "BERT", "Apache-2.0", "768", "cms_arch_1.png", 1),
            ("transformer", "Transformer", "Apache-2.0", "2017", "cms_arch_2.png", 1),
            ("resnet", "ResNet", "MIT", "2015", "cms_arch_3.png", 1),
            ("gpt3", "GPT-3", "MIT", "2020", "cms_arch_4.png", 1),
        ] + [(f"int_{i:02d}", f"Integration {i}", "MIT", str(200+i), f"cms_arch_{(i%6)+1}.png", 1) for i in range(11, 33)]
        con.executemany("INSERT OR REPLACE INTO cms_integrations VALUES(?,?,?,?,?,?)", seeds)
        con.execute("DELETE FROM cms_fts")
        con.executemany("INSERT INTO cms_fts(slug, title, license_spdx, benchmark_num) VALUES(?,?,?,?)", [(r[0], r[1], r[2], r[3]) for r in seeds])
        con.commit(); con.close()

        tot_kb = round(sum(p.stat().st_size for p in assets.glob("*") if p.is_file()) / 1024.0, 2)
        wire_kb = tot_kb * (0.42 + 0.58 * math.exp(-0.32 * 4))
        p95 = round(38.0 + (240.0 / 12) + (165.0 / 8) + 0.095 * wire_kb - min(18.0, 24.0 * 0.16), 2)
        qa_xlsx = workspace / "QA_Master_Matrix.xlsx"
        update_single_sheet_xlsx(qa_xlsx, "Assets", [["Param", "Value"], ["total_asset_kb", tot_kb]])
        update_single_sheet_xlsx(qa_xlsx, "Perf", [["Param", "Value"], ["sim_page_p95_ms", p95]])
        update_single_sheet_xlsx(qa_xlsx, "Web_Benchmarks", _shared_web_sheet_rows(zeroed=False))
        png_b = (assets / "hero_iso.png").read_bytes()
        Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / "exports/QA_Release_Report.pdf", "PDF")
        make_simple_pptx(workspace / "QA_Launch_Deck.pptx", ["NEXUS-V6-FLAGSHIP"], chart_png_bytes=png_b)
        for bc in sorted(UA09_REAL_BUGS_7):
            _post_json(f"{base}/api/qa/report_defect", {"bug_code": bc})
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=240)
        assert drc.get("all_gates_passed") is True, drc
        head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        _post_json(f"{base}/api/qa/release_signoff", {"release_token": "NEXUS-V6-FLAGSHIP", "git_commit": head_sha})
        canon_sha = sha256_file(repo / ".git/HEAD")
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": canon_sha})
            assert code == 200, sr

    elif task_id == "UA-10":
        cport = int(meta["cluster_port"])
        write_json(workspace / "forensics/db_fingerprint_60s.json", {"sufficient_window_60s": True, "sampled_seconds": 60})
        con = sqlite3.connect(str(workspace / "cluster/prod_ledger.db"))
        con.execute("DELETE FROM ledger_events WHERE region_code = 'CORRUPT_SHARD'")
        con.execute("CREATE INDEX IF NOT EXISTS idx_1 ON ledger_events(account_id, event_ts)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_2 ON ledger_events(region_code, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_3 ON ledger_events(shard_id, event_ts)")
        con.commit(); con.close()
        write_json(workspace / "cluster/db_tuning.json", {"sqlite_cache_mb": 195.0, "checkpoint_batch": 250})
        write_json(workspace / "cluster/app_gateway.json", {"hot_cache_mb": 225.0, "retry_backoff_ms": 240.0, "max_retries": 2, "cache_ttl_s": 180.0, "singleflight": True, "token_bucket_rps": 1250.0})
        write_json(workspace / "cluster/infra_daemon.json", {"telemetry_buffer_mb": 110.0, "log_level": "INFO", "liveness_timeout_ms": 1000.0})
        (workspace / "cluster/disk_vol/core_trace.bin").write_bytes(b"")

        gcon = sqlite3.connect(str(workspace / "data/edge_grid.gpkg"))
        for i in range(1, 49):
            val = 0.0 if i in (4, 11, 19, 27, 35, 43) else (960.0 / 42.0)
            gcon.execute("UPDATE edge_pops SET assigned_traffic_gbps = ? WHERE pop_id = ?", (val, f"POP_{i:02d}"))
        gcon.execute("UPDATE db_shards SET sync_bw_gbps = 6.5, wal_quorum = 2")
        gcon.commit(); gcon.close()
        (workspace / "Metro_Edge_Grid.qgz").write_text(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16">'
            '<projectlayers><maplayer><datasource>./data/edge_grid.gpkg|layername=edge_pops</datasource></maplayer>'
            '<maplayer><datasource>./data/edge_grid.gpkg|layername=db_shards</datasource></maplayer></projectlayers>'
            '<Layouts><Layout name="DB_Replication_A3"/><Layout name="Edge_Reroute_A3"/></Layouts></qgis>\n',
            encoding="utf-8",
        )
        _solve_harmonic_fcstd(workspace / "cryo_cooling_valve.FCStd")
        code, vr = _post_json(f"{base}/api/cae/valve_solve", {}, timeout_s=120)
        assert code == 200 and vr["certificate"]["valve_passed"] is True, vr
        _solve_atrium(workspace / "rack_thermal_twin.blend", workspace / "exports/rack_thermal_forensics.png", wh=(800, 450), set_bars=False)

        cap_p = workspace / "Capacity_Master.xlsx"
        update_single_sheet_xlsx(cap_p, "Allocations", [
            ["Component", "Value"],
            ["sqlite_cache_mb", 195.0], ["hot_cache_mb", 225.0], ["telemetry_buffer_mb", 110.0],
            ["arrival_rate_rps", 1200.0], ["target_p99_ms", 45.0],
        ])
        update_single_sheet_xlsx(cap_p, "Web_Standards", _shared_web_sheet_rows(zeroed=False))
        png_b = (workspace / "exports/rack_thermal_forensics.png").read_bytes()
        for pn in ("db_replication_atlas.pdf", "edge_reroute_map.pdf", "INC_Postmortem_RCA.pdf"):
            Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / f"exports/{pn}", "PDF")
        make_simple_pptx(workspace / "WarRoom_Executive.pptx", ["WARROOM-9910"], chart_png_bytes=png_b)
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=240)
        assert drc.get("all_gates_passed") is True, drc
        _, burst = _post_json(f"http://127.0.0.1:{cport}/api/canary_burst", {}, timeout_s=240)
        _post_json(f"{base}/api/statuspage/resolve", {"incident_token": "WARROOM-9910", "canary_p99_ms": burst["metrics"]["p99_ms"]})
        sha = sha256_file(cap_p)
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": sha})
            assert code == 200, sr

    elif task_id == "UA-11":
        fc_p = workspace / "harmonic_actuator.FCStd"
        _solve_harmonic_fcstd(fc_p, step_a=workspace / "exports/housing_cover.step", step_b=workspace / "exports/cam_follower.step")
        code, cert = _post_json(f"{base}/api/cae/exclusive_solve", {"review_token": "AERO-ACT-FLAGSHIP"}, timeout_s=150)
        assert code == 200 and cert["certificate"]["cae_passed"] is True, cert
        pc = cert["certificate"]["metrics"]["part_cm3"]
        bom_p = workspace / "Engineering_Master_BOM.xlsx"
        update_single_sheet_xlsx(bom_p, "Parts", [
            ["Solid", "Volume_cm3"],
            ["HousingShell", pc["HousingShell"]], ["HarmonicCam", pc["HarmonicCam"]],
            ["FollowerLink", pc["FollowerLink"]], ["TopCover", pc["TopCover"]],
        ])
        update_single_sheet_xlsx(bom_p, "Web_Literature", _shared_web_sheet_rows(zeroed=False))
        _solve_atrium(workspace / "studio_cutaway.blend", workspace / "exports/cutaway_beauty.png", wh=(1280, 720), set_bars=False)
        png_b = (workspace / "exports/cutaway_beauty.png").read_bytes()
        Image.open(io.BytesIO(png_b)).convert("RGB").save(workspace / "exports/Engineering_Whitepaper.pdf", "PDF")
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", "20.0", "-r", "24", "-i", str(workspace / "exports/cutaway_beauty.png"),
            "-i", str(workspace / "raw/narration_20s.wav"),
            "-filter_complex", "[0:v]lutrgb=r='clip(val,24,220)':g='clip(val,24,220)':b='clip(val,24,220)'[vout];[1:a]loudnorm=I=-23.0:TP=-2.0:LRA=7.0[aout]",
            "-map", "[vout]", "-map", "[aout]", "-frames:v", "480",
            "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(workspace / "exports/actuator_master_480f.mp4"),
        ], check=True, capture_output=True, timeout=120)
        _, drc = _post_json(f"{base}/api/drc_audit", {}, timeout_s=240)
        assert drc.get("all_gates_passed") is True, drc
        _post_json(f"{base}/api/media/publish", {"release_token": "AERO-ACT-FLAGSHIP", "mp4_path": "/workspace/exports/actuator_master_480f.mp4"})
        sha = sha256_file(fc_p)
        for r in meta["roles"]:
            code, sr = _post_json(f"{base}/api/role_signoff", {"role": r, "shared_sha256": sha})
            assert code == 200, sr


def sim_flagship_race(task_id: str, workspace: Path) -> None:
    meta = UA_BY_ID[task_id]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"
    if task_id == "UA-08":
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q4-FLAGSHIP", "noi_kusd": 100.0, "worst_dscr": 0.9, "model_path": str(workspace / "Q4_Enterprise_Master_Model.xlsx")})
        update_single_sheet_xlsx(workspace / "Q4_Enterprise_Master_Model.xlsx", "Web_Benchmarks", [["k", "r", "v", "n"], ["only_sales", "SALES", 9.0, ""]])
    elif task_id == "UA-09":
        _post_json(f"{base}/api/qa/report_defect", {"bug_code": "FALSE-WIP-CMS-TRANSIENT"})
    elif task_id == "UA-10":
        cport = int(meta["cluster_port"])
        _post_json(f"http://127.0.0.1:{cport}/api/restart", {"mode": "hard"})
    elif task_id == "UA-11":
        _post_json(f"{base}/api/media/publish", {"release_token": "AERO-ACT-FLAGSHIP", "mp4_path": "/workspace/missing_480f.mp4"})


def grade_flagship_case(task_id: str, workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    meta = UA_BY_ID[task_id]
    lb_s = float(meta["critical_section_lower_bound_s"])
    eff_wall = max(1.0, float(wall_seconds or lb_s))
    eff_score = round(min(1.0, lb_s / eff_wall), 4)
    side = dict(portal_state.get("collateral_side_effects") or {})
    if "total" not in side:
        side["total"] = sum(int(v) for v in side.values() if isinstance(v, (int, float)))
    signoffs = portal_state.get("role_signoffs") or {}
    canon_sha = sha256_file(workspace / meta["canonical_project"])

    if task_id == "UA-08":
        drc = eval_ua08_drc(workspace)
        g = drc.get("gates") or {}
        mails = portal_state.get("sent_emails") or []
        last_m = mails[-1] if mails else {}
        pptx_txt, pptx_img = read_pptx_info(workspace / "Q4_Board_Deck.pptx")
        canary = bool(
            drc.get("all_gates_passed")
            and last_m.get("board_token") == "QBR-2026-Q4-FLAGSHIP"
            and last_m.get("model_sha256") == canon_sha
            and "QBR-2026-Q4-FLAGSHIP" in pptx_txt and pptx_img
            and len(signoffs) == 4
        )
        role_p = {
            "FIN": bool(g.get("G_FIN_1_restated_rev_8210_and_cost_2940") and g.get("G_FIN_2_stress_24q_dscr_ge_1_56_cash_ge_720") and g.get("G_FIN_3_coupled_pareto_noi_margin_48_5_to_50_5") and g.get("G_FIN_4_treasury_pdf_and_bridge_png") and "FIN" in signoffs),
            "OPS": bool(g.get("G_OPS_1_coupled_p95_latency_le_24_2ms") and g.get("G_OPS_2_failover_24_35pct_and_cost_band") and g.get("G_OPS_3_cycles_6louver_solar_envelope") and g.get("G_OPS_4_qgis_dc_atlas_synced") and "OPS" in signoffs),
            "SALES": bool(g.get("G_SALES_1_weighted_pipeline_5750_to_6850") and g.get("G_SALES_2_nrr_ge_115_0_churn_le_48") and g.get("G_SALES_3_qgis_sales_atlas_and_curve") and "SALES" in signoffs),
            "EXEC": canary,
        }
    elif task_id == "UA-09":
        drc = eval_ua09_drc(workspace, sport=int(meta["staging_port"]))
        g = drc.get("gates") or {}
        filed = {str(x.get("bug_code") or "").upper() for x in (portal_state.get("qa_issues") or []) if str(x.get("bug_code") or "").strip()}
        false_cnt = sum(1 for c in filed if c not in UA09_REAL_BUGS_7)
        head_sha = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=workspace / "nexus-portal", capture_output=True, text=True).stdout.strip()
        so = portal_state.get("qa_signoff") or {}
        canary = bool(
            drc.get("all_gates_passed") and UA09_REAL_BUGS_7.issubset(filed) and false_cnt == 0
            and so.get("release_token") == "NEXUS-V6-FLAGSHIP" and so.get("git_commit") == head_sha
            and len(signoffs) == 4
        )
        role_p = {
            "FE": bool(g.get("G_FE_1_sixteen_responsive_routes") and g.get("G_FE_2_seven_seeded_bugs_remediated") and g.get("G_FE_3_coupled_p95_le_136ms_and_ram_le_310mb") and "FE" in signoffs),
            "DESIGN": bool(g.get("G_DES_1_cycles_showroom_and_4_heroes") and g.get("G_DES_2_gimp_6cards_and_inkscape_6badges") and g.get("G_DES_3_turntable_192f_ebu_r128_and_payload_cap") and "DESIGN" in signoffs),
            "CMS": bool(g.get("G_CMS_1_32_articles_fts5_and_6_arch_diagrams") and g.get("G_CMS_2_ten_live_web_facts_verified") and "CMS" in signoffs),
            "QA": canary,
        }
    elif task_id == "UA-10":
        drc = eval_ua10_drc(workspace, burst_mult=1.6)
        g = drc.get("gates") or {}
        poll = int(side.get("observation_pollutions", 0))
        sps = portal_state.get("statuspage_posts") or []
        canary = bool(drc.get("all_gates_passed") and poll == 0 and bool(sps) and sps[-1].get("incident_token") == "WARROOM-9910" and len(signoffs) == 4)
        role_p = {
            "DB": bool(g.get("G_DB_1_three_indexes_clean_shards_and_repl_lag") and g.get("G_DB_2_forensics_60s_and_db_qgis_atlas") and poll == 0 and "DB" in signoffs),
            "APP": bool(g.get("G_APP_1_gateway_singleflight_and_540mb_ram_corridor") and g.get("G_APP_2_qgis_48pop_reroute_and_cost_cap") and "APP" in signoffs),
            "INFRA": bool(g.get("G_INF_1_daemon_disk_and_cycles_thermal_louvers") and g.get("G_INF_2_harmonic_cryo_valve_72angle_and_cae") and "INFRA" in signoffs),
            "IC": canary,
        }
    else:
        drc = eval_ua11_drc(workspace)
        g = drc.get("gates") or {}
        pubs = portal_state.get("media_pubs") or []
        mp4_sha = sha256_file(workspace / "exports/actuator_master_480f.mp4")
        canary = bool(drc.get("all_gates_passed") and bool(pubs) and pubs[-1].get("release_token") == "AERO-ACT-FLAGSHIP" and pubs[-1].get("mp4_sha256") == mp4_sha and len(signoffs) == 4)
        role_p = {
            "CAD_HOUSING": bool(g.get("G_HOUS_1_cam_housing_clearance_and_cover_stiffness") and g.get("G_HOUS_2_coupled_4part_mass_le_0_855kg_and_cg_le_0_65mm") and "CAD_HOUSING" in signoffs),
            "CAD_ROTOR": bool(g.get("G_ROT_1_exact_stroke_18_34_to_18_46_and_pa_le_25_5") and g.get("G_ROT_2_hydrodynamic_gap_015_023_zero_collision") and "CAD_ROTOR" in signoffs),
            "CAE_LIT": bool(g.get("G_CAE_1_exclusive_20s_solver_cert_and_cycles_baffles") and g.get("G_CAE_2_coupled_bom_xlsx_and_whitepaper_pdf") and "CAE_LIT" in signoffs),
            "MEDIA_PUB": canary,
        }

    ms_score = round(sum(1 for v in g.values() if v) / max(1, len(g)), 4)
    rub_score = round(0.70 * ms_score + 0.30 * (1.0 if canary else 0.0), 4)
    return {
        "task_id": task_id,
        "arena": meta["arena"],
        "joint_pass": bool(all(role_p.values()) and canary),
        "canary_passed": canary,
        "milestone_score": ms_score,
        "final_rubric_score": rub_score,
        "role_pass": role_p,
        "passed_roles_count": sum(1 for v in role_p.values() if v),
        "role_signoffs_count": len(signoffs),
        "gates": g,
        "metrics": drc.get("metrics") or {},
        "drc_calls_count": int(portal_state.get("drc_calls", 0)),
        "efficiency": {
            "critical_section_lower_bound_s": lb_s,
            "actual_wall_s": round(eff_wall, 2),
            "score": eff_score,
        },
        "collateral_side_effects": side,
    }

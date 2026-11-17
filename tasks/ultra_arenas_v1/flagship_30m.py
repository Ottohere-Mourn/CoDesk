"""Flagship 30-55+ minute 4-agent high-overlap arenas (UA-08..UA-11) with native multi-software DRC."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import textwrap
import time
import urllib.request
from zipfile import ZipFile

try:
    from tasks.ultra_arenas_v1.catalog import UA_BY_ID
except ImportError:
    from catalog import UA_BY_ID  # type: ignore

try:
    from tasks.thematic_arenas_v1.xlsx_utils import (
        evaluate_xlsx_via_libreoffice,
        read_multisheet_xlsx,
    )
except ImportError:
    from xlsx_utils import (  # type: ignore
        evaluate_xlsx_via_libreoffice,
        read_multisheet_xlsx,
    )

FLAGSHIP_IDS = ("UA-08", "UA-09", "UA-10", "UA-11")

UA08_BI_PAGES = {
    "FIN": [
        [("NA_Cloud_Core", 520.0, 170.0, 20.0), ("NA_AI_Cluster", 470.0, 155.0, 20.0), ("NA_Data_Lake", 415.0, 140.0, 15.0), ("NA_SecOps", 365.0, 125.0, 15.0)],
        [("NA_DevTools", 435.0, 145.0, 15.0), ("NA_Edge_CDN", 395.0, 130.0, 15.0), ("NA_Vector_DB", 330.0, 110.0, 10.0), ("NA_Support_Pro", 290.0, 95.0, 10.0)],
        [("EMEA_DACH_Cloud", 415.0, 145.0, 15.0), ("EMEA_UK_AI", 375.0, 130.0, 15.0), ("EMEA_FR_Sovereign", 320.0, 110.0, 10.0), ("EMEA_Benelux_Core", 280.0, 95.0, 10.0)],
        [("EMEA_Nordics_AI", 310.0, 105.0, 10.0), ("EMEA_South_Suite", 270.0, 95.0, 10.0), ("EMEA_CEE_Platform", 235.0, 85.0, 5.0), ("EMEA_MEA_Gateway", 225.0, 85.0, 15.0)],
        [("APAC_JP_Enterprise", 610.0, 210.0, 20.0), ("APAC_SG_AI_Hub", 535.0, 185.0, 15.0), ("APAC_AU_Cloud", 465.0, 160.0, 15.0), ("APAC_KR_Edge", 430.0, 145.0, 10.0)],
        [("LATAM_BR_Cloud", 340.0, 115.0, 10.0), ("LATAM_MX_AI", 280.0, 95.0, 10.0), ("LATAM_Andean_Core", 225.0, 60.0, 5.0), ("LATAM_ConoSur_Edge", 185.0, 50.0, 5.0)],
    ],
    "OPS": [
        [(f"DC_{p*4+i+1:02d}", ("NA", "NA", "EMEA", "EMEA", "APAC", "LATAM")[p], 22 + ((p + i) % 5) * 2, round(1.33 + (i % 3) * 0.04, 2), round(18.0 + p * 2.5 + i * 1.4, 1)) for i in range(4)]
        for p in range(6)
    ],
    "SALES": [
        [(f"T_{p*4+i+1:02d}", ("NA", "NA", "EMEA", "EMEA", "APAC", "LATAM")[p], float(950 - i * 100), 90 + p * 12 + i * 15) for i in range(4)]
        for p in range(6)
    ],
}

# Exact ground-truth anchors verified live on external websites (16 rows, 4 per role)
UA08_WEB_SPECS = [
    ("pep8_max_line", 79.0, "FIN"),
    ("pep20_number", 20.0, "FIN"),
    ("pep484_number", 484.0, "FIN"),
    ("dscr_breakeven_ratio", 1.0, "FIN"),
    ("ideal_pue_ratio", 1.0, "OPS"),
    ("freecad_lgpl_ver", 2.1, "OPS"),
    ("sqlite_major_ver", 3.0, "OPS"),
    ("resnet_arxiv_year", 2015.0, "OPS"),
    ("flask_bsd_clauses", 3.0, "SALES"),
    ("requests_apache_ver", 2.0, "SALES"),
    ("httpx_bsd_clauses", 3.0, "SALES"),
    ("sqlalchemy_mit_flag", 1.0, "SALES"),
    ("gpt2_vocab_size", 50257.0, "EXEC"),
    ("bert_hidden_size", 768.0, "EXEC"),
    ("transformer_arxiv_year", 2017.0, "EXEC"),
    ("gpt3_arxiv_year", 2020.0, "EXEC"),
]
UA08_WEB_SUM = sum(x[1] for x in UA08_WEB_SPECS)  # 55676.1

UA09_ROUTES_16 = (
    "index", "pricing", "docs", "sdk", "integrations", "benchmarks", "security", "changelog",
    "enterprise", "status", "cli", "community", "architecture", "migration", "compliance", "telemetry",
)
UA09_REAL_BUGS_7 = {
    "BUG-ANNUAL-SURCHARGE",
    "BUG-ENT-SLA-ZERO",
    "BUG-TZ-PST8",
    "BUG-CSRF-SAMESITE",
    "BUG-BRAND-VIEWBOX",
    "BUG-FTS-LIMIT",
    "BUG-CONTRAST-WASH",
}


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _num(sheet: dict, ref: str, default: float = 0.0) -> float:
    v = (sheet.get(ref) or {}).get("value")
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _eval_cycles_atrium(blend_path: Path, samples: int = 48, check_bars: bool = False) -> dict:
    """Run real 4-pass Blender 3.4 Cycles global-illumination audit (~26-34s on 5 CPUs)."""
    from PIL import Image
    if not blend_path.is_file():
        return {"ok": False}
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        meta_p = td / "meta.json"
        py = textwrap.dedent(f"""\
            import bpy, bmesh, json, math
            bpy.ops.wm.open_mainfile(filepath={str(blend_path)!r})
            sc = bpy.context.scene
            sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
            sc.cycles.samples = {int(samples)}; sc.cycles.use_denoising = False; sc.cycles.max_bounces = 4
            sc.render.resolution_x = 640; sc.render.resolution_y = 360
            sun = bpy.data.objects['SolarSun']
            sc.camera = bpy.data.objects['PlanCam']
            tlights = [bpy.data.objects[f'TaskLight_{{i:02d}}'] for i in range(1, 5)]
            orig_e = [float(tl.data.energy) for tl in tlights]
            lvol = 0.0
            for i in range(1, 7):
                lv = bpy.data.objects[f'Louver_{{i:02d}}']
                bm = bmesh.new(); bm.from_object(lv, bpy.context.evaluated_depsgraph_get()); bm.transform(lv.matrix_world)
                lvol += abs(float(bm.calc_volume())); bm.free()
            bars = [float(bpy.data.objects[n].dimensions.z) for n in ('Bar_NA','Bar_EMEA','Bar_APAC','Bar_LATAM') if n in bpy.data.objects]
            for tl in tlights: tl.data.energy = 0.0
            for k, ang in [('morn', -42.0), ('noon', 12.0), ('aft', 48.0)]:
                sun.rotation_euler = (0.0, math.radians(ang), 0.0)
                sc.render.filepath = f'{td}/{{k}}.png'
                bpy.ops.render.render(write_still=True)
            for tl, en in zip(tlights, orig_e): tl.data.energy = en
            sun.rotation_euler = (0.0, math.radians(12.0), 0.0)
            sc.render.filepath = f'{td}/comb.png'
            bpy.ops.render.render(write_still=True)
            open({str(meta_p)!r}, 'w').write(json.dumps({{'power_w': sum(orig_e), 'louver_vol': round(lvol, 3), 'bars': bars}}))
        """)
        (td / "probe.py").write_text(py, encoding="utf-8")
        cp = subprocess.run(["blender", "-b", "--python", str(td / "probe.py")], capture_output=True, text=True, timeout=240)
        if cp.returncode != 0 or not meta_p.is_file():
            return {"ok": False}
        meta = json.loads(meta_p.read_text(encoding="utf-8"))

        def _stats(p: Path) -> tuple[float, list[float], float]:
            with Image.open(p) as im:
                g = [px / 255.0 for px in im.convert("L").tobytes()]
                w, h = im.size
                zs = []
                for zi in range(6):
                    x0, x1 = int(w * (0.08 + zi * 0.14)), int(w * (0.20 + zi * 0.14))
                    y0, y1 = int(h * 0.28), int(h * 0.72)
                    patch = [g[yy * w + xx] for yy in range(y0, y1) for xx in range(x0, x1)]
                    zs.append(round(sum(patch) / max(1, len(patch)), 4))
                sg = sorted(g)
                return round(sum(g) / len(g), 4), zs, round(sg[int(0.98 * len(sg))], 4)

        m_m, _, _ = _stats(td / "morn.png")
        n_m, _, n_p98 = _stats(td / "noon.png")
        a_m, _, _ = _stats(td / "aft.png")
        c_m, c_zs, c_p98 = _stats(td / "comb.png")
        unif = round(min(c_zs) / max(1e-6, max(c_zs)), 4)
        bars_ok = True
        if check_bars:
            bs = meta.get("bars") or []
            bars_ok = (
                len(bs) == 4 and bs[0] > 0.2
                and abs(bs[1] / bs[0] - 2275.0 / 3100.0) <= 0.035
                and abs(bs[2] / bs[0] - 1835.0 / 3100.0) <= 0.035
                and abs(bs[3] / bs[0] - 1000.0 / 3100.0) <= 0.035
            )
        return {
            "ok": True,
            "morning_luma": m_m,
            "noon_solar_gain": n_m,
            "afternoon_luma": a_m,
            "noon_p98": n_p98,
            "comb_mean": c_m,
            "comb_zones": c_zs,
            "comb_p98": c_p98,
            "uniformity": unif,
            "power_w": round(meta["power_w"], 2),
            "louver_vol": meta["louver_vol"],
            "bars_ok": bars_ok,
        }


def _eval_pyqgis_layouts(qgz_path: Path, required_layouts: tuple[str, ...]) -> tuple[bool, list[str]]:
    """Run real headless PyQGIS 300-DPI layout render audit (~6-9s)."""
    if not qgz_path.is_file():
        return False, []
    found = []
    try:
        with ZipFile(qgz_path, "r") as zq:
            qnames = [n for n in zq.namelist() if n.endswith(".qgs")]
            qxml = zq.read(qnames[0]).decode("utf-8", errors="replace") if qnames else ""
    except Exception:
        qxml = qgz_path.read_text(encoding="utf-8", errors="replace")
    for ln in required_layouts:
        if ln in qxml:
            found.append(ln)
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        qpy = textwrap.dedent(f"""\
            import os
            from qgis.core import QgsApplication, QgsLayoutExporter, QgsLayoutItemMap, QgsLayoutPoint, QgsLayoutSize, QgsPrintLayout, QgsProject, QgsUnitTypes
            os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
            qgs = QgsApplication([], False); qgs.initQgis()
            proj = QgsProject.instance(); ok = proj.read({str(qgz_path)!r})
            lyrs = list(proj.mapLayers().values())
            for idx in range(2):
                lay = QgsPrintLayout(proj); lay.initializeDefaults()
                mi = QgsLayoutItemMap(lay); mi.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutMillimeters))
                mi.attemptResize(QgsLayoutSize(400, 280, QgsUnitTypes.LayoutMillimeters))
                if lyrs: mi.setExtent(lyrs[0].extent())
                lay.addLayoutItem(mi)
                iset = QgsLayoutExporter.ImageExportSettings(); iset.dpi = 300
                QgsLayoutExporter(lay).exportToImage(f'{td}/m_{{idx}}.png', iset)
            proj.clear(); os._exit(0 if (ok and len(lyrs) >= 1) else 2)
        """)
        (td / "qrun.py").write_text(qpy, encoding="utf-8")
        env = dict(os.environ); env.setdefault("QT_QPA_PLATFORM", "offscreen")
        cp = subprocess.run(["python3", str(td / "qrun.py")], env=env, capture_output=True, text=True, timeout=120)
        q_ok = cp.returncode == 0 and len(found) == len(required_layouts)
    return q_ok, found


def _eval_harmonic_cam_fcstd(fcstd_path: Path) -> dict:
    """Run real 72-angle OpenCASCADE BRep harmonic cam-follower clearance & inertia sweep."""
    if not fcstd_path.is_file():
        return {"ok": False}
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        out_j = td / "fc_res.json"
        fpy = textwrap.dedent(f"""\
            import FreeCAD, Part, json, math
            doc = FreeCAD.openDocument({str(fcstd_path)!r})
            sh = doc.getObject('SystemSpec')
            spec = {{sh.get(f'A{{i}}'): float(sh.get(f'B{{i}}')) for i in range(1, 10)}}
            h_sh = doc.getObject('HousingShell').Shape
            c_sh = doc.getObject('HarmonicCam').Shape
            f_sh = doc.getObject('FollowerLink').Shape
            t_sh = doc.getObject('TopCover').Shape
            radii, pas = [], []
            min_ch = 999.0
            for step in range(72):
                phi = math.radians(step * 5.0)
                rv = spec['cam_r0_mm'] + spec['cam_e1_mm']*math.cos(phi) + spec['cam_h2_mm']*math.cos(2*phi) + spec['cam_h3_mm']*math.cos(3*phi)
                dr = -spec['cam_e1_mm']*math.sin(phi) - 2*spec['cam_h2_mm']*math.sin(2*phi) - 3*spec['cam_h3_mm']*math.sin(3*phi)
                pas.append(math.degrees(math.atan2(abs(dr), max(1.0, rv + spec['follower_roller_r_mm']))))
                radii.append(rv)
                if step % 2 == 0:
                    rc = c_sh.copy(); rc.rotate(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), step * 5.0)
                    d_ch = float(rc.distToShape(h_sh)[0])
                    if rc.common(h_sh).Volume > 0.01: d_ch = 0.0
                    min_ch = min(min_ch, d_ch)
            gap = float(c_sh.distToShape(f_sh)[0])
            coll = float(c_sh.common(f_sh).Volume + f_sh.common(h_sh).Volume + f_sh.common(t_sh).Volume + t_sh.common(c_sh).Volume + h_sh.common(t_sh).Volume)
            rho = 2.81e-6
            parts = [h_sh, c_sh, f_sh, t_sh]
            vols = [float(p.Volume) for p in parts]; tot_v = sum(vols)
            sols = [s for p in parts for s in p.Solids]
            cg_x = sum(float(s.CenterOfMass.x)*float(s.Volume) for s in sols)/max(1.0, tot_v)
            cg_y = sum(float(s.CenterOfMass.y)*float(s.Volume) for s in sols)/max(1.0, tot_v)
            open({str(out_j)!r}, 'w').write(json.dumps({{
                'ok': True, 'stroke': round(max(radii)-min(radii), 4), 'max_pa': round(max(pas), 3),
                'min_ch': round(min_ch, 3), 'home_gap': round(gap, 4), 'coll_vol': round(coll, 4),
                'mass_b': round((vols[0]+vols[1])*rho, 4), 'mass_tot': round(tot_v*rho, 4),
                'cg_r': round(math.hypot(cg_x, cg_y), 4), 'cover_v': round(vols[3], 1),
                'part_cm3': {{'HousingShell': round(vols[0]/1000.0,3), 'HarmonicCam': round(vols[1]/1000.0,3), 'FollowerLink': round(vols[2]/1000.0,3), 'TopCover': round(vols[3]/1000.0,3)}}
            }}))
        """)
        (td / "fc.py").write_text(fpy, encoding="utf-8")
        cp = subprocess.run(["freecadcmd", str(td / "fc.py")], capture_output=True, text=True, timeout=150)
        if cp.returncode != 0 or not out_j.is_file():
            return {"ok": False}
        return json.loads(out_j.read_text(encoding="utf-8"))


def eval_ua08_drc(workspace: Path) -> dict:
    """UA-08 Flagship QBR DRC: LibreOffice 6-sheet + 12k-path 24Q MC + PyQGIS 2-layout + 4-pass Cycles GI (~40s)."""
    t0 = time.monotonic()
    xlsx_p = workspace / "Q4_Enterprise_Master_Model.xlsx"
    if not xlsx_p.is_file():
        return {"ok": False, "error": "Missing /workspace/Q4_Enterprise_Master_Model.xlsx"}
    raw_wb = read_multisheet_xlsx(xlsx_p)
    ev_wb = evaluate_xlsx_via_libreoffice(xlsx_p)
    s_raw = raw_wb.get("Executive_Summary", {})
    s_ev = ev_wb.get("Executive_Summary", {})
    formulas_ok = all(bool((s_raw.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4", "B5", "B6", "B7", "B8"))

    base_rev = _num(s_ev, "B2")
    direct_cost = _num(s_ev, "B3")
    ops_cost = _num(s_ev, "B4")
    sales_weighted = _num(s_ev, "B5")
    debt_service_q = _num(s_ev, "B6")
    noi = _num(s_ev, "B7")
    web_sum = _num(s_ev, "B8")

    dc_sh = ev_wb.get("Datacenter_24R", {})
    dc_weights = [1.30, 1.24, 1.12, 1.05, 1.28, 1.15, 0.96, 1.08, 1.26, 1.18, 1.10, 0.94, 1.16, 1.06, 0.92, 0.88, 1.25, 1.18, 1.04, 1.02, 0.94, 0.90, 0.86, 0.84]
    dc_floors = [1.21, 1.19, 1.17, 1.23, 1.20, 1.18, 1.22, 1.24, 1.20, 1.18, 1.21, 1.25, 1.17, 1.22, 1.24, 1.26, 1.22, 1.25, 1.23, 1.20, 1.26, 1.24, 1.25, 1.26]
    tot_act = tot_fo = eff_cap = therm_pen = 0.0
    pues = []; hot_dcs = []
    for i in range(24):
        r = i + 2
        ac = _num(dc_sh, f"C{r}"); fo = _num(dc_sh, f"D{r}"); pu = _num(dc_sh, f"E{r}", 1.42)
        tot_act += ac; tot_fo += fo; pues.append(pu)
        sat = ac - 0.025 * max(0.0, ac - 33.0) ** 2
        eff_cap += (sat + 0.65 * fo) * dc_weights[i]
        if pu < dc_floors[i]:
            therm_pen += (dc_floors[i] - pu) * 92.0
            hot_dcs.append(f"DC_{i+1:02d}(wetbulb_throttle)")
        elif ac > 35.0:
            hot_dcs.append(f"DC_{i+1:02d}(grid_sat)")
    mean_pue = sum(pues) / 24.0

    sp_sh = ev_wb.get("Pipeline_24T", {})
    elast_caps = [1.11, 1.09, 1.06, 1.04, 1.10, 1.07, 1.05, 1.03, 1.10, 1.08, 1.06, 1.04, 1.09, 1.06, 1.04, 1.02, 1.11, 1.08, 1.06, 1.05, 1.04, 1.03, 1.02, 1.02]
    pms = []; rbs = []; churn = 0.0; churn_ts = []
    for i in range(24):
        r = i + 2
        pm = _num(sp_sh, f"E{r}", 1.0); rb = _num(sp_sh, f"F{r}", 0.0)
        pms.append(pm); rbs.append(rb)
        if pm > elast_caps[i]:
            churn += ((pm - elast_caps[i]) ** 2) * 4200.0
            churn_ts.append(f"T_{i+1:02d}(elasticity_cliff)")
        elif pm < 0.96:
            churn += (0.96 - pm) * 420.0
    mean_pm = sum(pms) / 24.0; mean_rb = sum(rbs) / 24.0
    eff_nrr = round(104.0 + 65.0 * (mean_pm - 0.95) + 88.0 * mean_rb - 0.025 * churn, 2)

    req_cap = 665.0 * (eff_nrr / 114.0)
    p95_lat = round(23.2 / max(0.35, eff_cap / max(1.0, req_cap)) + max(0.0, (mean_pue - 1.28) * 38.0) + therm_pen, 2)
    fo_ratio = tot_fo / max(1.0, tot_act)

    fin_sh = ev_wb.get("Finance_24U", {})
    hedge = _num(fin_sh, "G2", 0.15)
    reserve = _num(fin_sh, "G3", 320.0)
    worst_dscr = 99.0; min_cash = 99999.0
    for pi in range(6000):
        ph = (pi + 1) * 0.131
        m_shk = 1.0 - 0.11 * abs(math.sin(ph)) - 0.065 * (1.0 - min(1.0, hedge)) * abs(math.cos(ph * 1.7))
        p_spk = 1.0 + 0.14 * max(0.0, mean_pue - 1.25) * abs(math.sin(ph * 0.9))
        eb = (base_rev * m_shk + 0.20 * sales_weighted * m_shk - churn) - direct_cost - (ops_cost * p_spk) - (hedge * 65.0)
        dscr = eb / max(1.0, debt_service_q)
        cend = reserve + 0.35 * (eb - debt_service_q)
        if dscr < worst_dscr: worst_dscr = dscr
        if cend < min_cash: min_cash = cend

    tot_rev_eff = base_rev + 0.20 * sales_weighted
    noi_margin = round(100.0 * noi / max(1.0, tot_rev_eff), 2)

    q_ok, q_lays = _eval_pyqgis_layouts(workspace / "global_qbr_atlas.qgz", ("Global_DC_Capacity_A3", "Sales_Territory_Risk_A3"))
    gpkg_p = workspace / "data/qbr_spatial.gpkg"
    gpkg_dc_ok = gpkg_sales_ok = False
    if gpkg_p.is_file():
        try:
            con = sqlite3.connect(str(gpkg_p))
            dc_sum = float(con.execute("SELECT COALESCE(SUM(active_racks),0) FROM dc_sites").fetchone()[0])
            sl_sum = float(con.execute("SELECT COALESCE(SUM(weighted_arr),0) FROM sales_territories").fetchone()[0])
            con.close()
            gpkg_dc_ok = abs(dc_sum - tot_act) <= 3.0
            gpkg_sales_ok = abs(sl_sum - sales_weighted) <= 12.0
        except sqlite3.Error:
            pass

    cyc = _eval_cycles_atrium(workspace / "hq_flagship_atrium.blend", samples=48, check_bars=True)
    louver_ok = bool(
        cyc.get("ok") and cyc["noon_solar_gain"] <= 0.495
        and cyc["morning_luma"] >= 0.360 and cyc["afternoon_luma"] >= 0.420
        and 7.5 <= cyc["louver_vol"] <= 13.5
    )
    exec_gi_ok = bool(
        cyc.get("ok") and all(0.635 <= z <= 0.785 for z in cyc["comb_zones"])
        and cyc["uniformity"] >= 0.860 and cyc["power_w"] <= 390.0 and cyc["bars_ok"]
        and (workspace / "exports/q4_boardroom_3d.png").is_file()
    )

    gates = {
        "G_FIN_1_restated_rev_8210_and_cost_2940": math.isclose(base_rev, 8210.0, abs_tol=2.0) and math.isclose(direct_cost, 2940.0, abs_tol=2.0),
        "G_FIN_2_stress_24q_dscr_ge_1_56_cash_ge_720": worst_dscr >= 1.56 and min_cash >= 720.0 and reserve <= 1050.0,
        "G_FIN_3_coupled_pareto_noi_margin_48_5_to_50_5": 48.5 <= noi_margin <= 50.5,
        "G_FIN_4_treasury_pdf_and_bridge_png": (workspace / "exports/Treasury_Stress_Audit.pdf").is_file() and (workspace / "exports/ebitda_bridge_300dpi.png").is_file(),
        "G_OPS_1_coupled_p95_latency_le_24_2ms": p95_lat <= 24.2 and len(hot_dcs) == 0,
        "G_OPS_2_failover_24_35pct_and_cost_band": 0.24 <= fo_ratio <= 0.35 and 1450.0 <= ops_cost <= 1880.0 and mean_pue <= 1.29,
        "G_OPS_3_cycles_6louver_solar_envelope": louver_ok,
        "G_OPS_4_qgis_dc_atlas_synced": ("Global_DC_Capacity_A3" in q_lays) and gpkg_dc_ok and (workspace / "exports/DC_Global_Atlas.pdf").is_file(),
        "G_SALES_1_weighted_pipeline_5750_to_6850": 5750.0 <= sales_weighted <= 6850.0,
        "G_SALES_2_nrr_ge_115_0_churn_le_48": eff_nrr >= 115.0 and churn <= 48.0 and mean_rb <= 0.085,
        "G_SALES_3_qgis_sales_atlas_and_curve": ("Sales_Territory_Risk_A3" in q_lays) and gpkg_sales_ok and (workspace / "exports/Sales_Territory_Atlas.pdf").is_file() and (workspace / "exports/nrr_cohort_curve.png").is_file(),
        "G_WEB_all_4_roles_16_live_web_benchmarks": math.isclose(web_sum, UA08_WEB_SUM, abs_tol=0.5),
        "G_EXEC_1_summary_formulas_intact": formulas_ok,
        "G_EXEC_2_cycles_6zone_boardroom_and_bars": exec_gi_ok,
        "G_EXEC_3_board_pdf_and_pptx": (workspace / "exports/Q4_Board_Briefing.pdf").is_file() and (workspace / "Q4_Board_Deck.pptx").is_file(),
    }
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v), "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "base_rev_kusd": round(base_rev, 2), "direct_cost_kusd": round(direct_cost, 2),
            "ops_cost_kusd": round(ops_cost, 2), "sales_weighted_kusd": round(sales_weighted, 2),
            "noi_kusd": round(noi, 2), "noi_margin_pct": noi_margin,
            "worst_24q_dscr": round(worst_dscr, 4), "min_stress_cash_kusd": round(min_cash, 2),
            "p95_latency_ms": p95_lat, "failover_ratio": round(fo_ratio, 4), "mean_pue": round(mean_pue, 4),
            "effective_nrr_pct": eff_nrr, "churn_penalty_kusd": round(churn, 2),
            "web_benchmark_sum": round(web_sum, 2),
            "throttled_datacenters": hot_dcs[:8], "high_churn_territories": churn_ts[:8],
            "cycles_photometry": {k: cyc.get(k) for k in ("morning_luma", "noon_solar_gain", "afternoon_luma", "comb_zones", "uniformity", "power_w", "louver_vol", "bars_ok")},
        },
    }


def eval_ua09_drc(workspace: Path, sport: int = 19590) -> dict:
    """UA-09 Flagship Launch DRC: 18-render live Chromium optical E2E + Cycles Studio + 192f EBU-R128 MP4 + FTS5 (~42s)."""
    from PIL import Image
    t0 = time.monotonic()
    repo = workspace / "nexus-portal"
    assets = repo / "static/assets"
    db_p = workspace / "staging_data/nexus.db"

    routes_ok = all(
        (repo / f"templates/{rt}.html").is_file()
        and 'data-nexus-v6="ready"' in (repo / f"templates/{rt}.html").read_text(encoding="utf-8", errors="ignore")
        and "@media" in (repo / f"templates/{rt}.html").read_text(encoding="utf-8", errors="ignore")
        for rt in UA09_ROUTES_16
    )
    cfg = json.loads((repo / "portal_config.json").read_text(encoding="utf-8")) if (repo / "portal_config.json").is_file() else {}
    pool_sz = int(cfg.get("sqlite_pool_size", 1))
    workers = int(cfg.get("worker_threads", 1))
    gzip_lv = int(cfg.get("gzip_level", 1))
    qcache_mb = float(cfg.get("query_cache_mb", 16.0))
    fts_limit = int(cfg.get("fts_max_results", 0))
    ann_disc = float(cfg.get("annual_discount_pct", -20.0))
    ent_mult = float(cfg.get("enterprise_sla_mult", 0.0))
    tz_mode = str(cfg.get("changelog_tz", "PST-8"))
    csrf_ok = bool(cfg.get("csrf_cookie_samesite", False))
    svg_ok = (assets / "brand_mark.svg").is_file() and 'viewBox="0 0 160 48"' in (assets / "brand_mark.svg").read_text(encoding="utf-8", errors="ignore")

    hero_specs = [("hero_front.png", (1280, 640)), ("hero_iso.png", (800, 500)), ("hero_cutaway.png", (800, 500)), ("hero_detail.png", (800, 500))]
    heroes_ok = all((assets / fn).is_file() and Image.open(assets / fn).size == wh for fn, wh in hero_specs)
    cards_ok = all((assets / f"feature_card_{i}.png").is_file() and Image.open(assets / f"feature_card_{i}.png").size == (640, 400) for i in range(1, 7))
    badges_ok = all((assets / f"badge_{i}.png").is_file() and Image.open(assets / f"badge_{i}.png").size == (128, 128) for i in range(1, 7))
    cms_arch_ok = all((assets / f"cms_arch_{i}.png").is_file() and Image.open(assets / f"cms_arch_{i}.png").size == (640, 360) for i in range(1, 7))
    total_asset_kb = round(sum(p.stat().st_size for p in assets.glob("*") if p.is_file()) / 1024.0, 2) if assets.is_dir() else 99999.0

    staging_ram_mb = round(48.0 + pool_sz * 9.5 + workers * 14.0 + qcache_mb, 2)
    wire_kb = total_asset_kb * (0.42 + 0.58 * math.exp(-0.32 * max(0, gzip_lv - 1)))
    cpu_gzip_ms = 2.2 * (max(0, gzip_lv - 5) ** 2.1)
    sim_p95_ms = round(38.0 + (240.0 / max(1, min(pool_sz, 20))) + (165.0 / max(1, min(workers, 16))) + 0.095 * wire_kb + cpu_gzip_ms - min(18.0, qcache_mb * 0.16), 2)

    cyc = _eval_cycles_atrium(workspace / "product_stage.blend", samples=34, check_bars=False)
    stage_gi_ok = bool(
        cyc.get("ok") and cyc["noon_solar_gain"] <= 0.495 and cyc["morning_luma"] >= 0.350
        and all(0.620 <= z <= 0.790 for z in cyc["comb_zones"]) and cyc["uniformity"] >= 0.855
    )

    mp4_p = assets / "hero_turntable_192f.mp4"
    tt_ok = False; tt_frames = 0; tt_lufs = None
    if mp4_p.is_file():
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(mp4_p)], capture_output=True, text=True, timeout=30)
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            tt_frames = int(st.get("nb_read_frames") or 0)
            wh_ok = (int(st.get("width", 0)), int(st.get("height", 0))) == (640, 360)
        except Exception:
            wh_ok = False
        cp_l = subprocess.run(["ffmpeg", "-nostats", "-i", str(mp4_p), "-filter_complex", "ebur128=framelog=verbose", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        ms = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", cp_l.stderr)
        tt_lufs = float(ms[-1]) if ms else None
        if wh_ok and 188 <= tt_frames <= 196 and tt_lufs is not None and -23.5 <= tt_lufs <= -22.5:
            with tempfile.TemporaryDirectory() as tmp:
                f0, f1 = Path(tmp) / "f0.png", Path(tmp) / "f1.png"
                subprocess.run(["ffmpeg", "-y", "-ss", "0.3", "-i", str(mp4_p), "-frames:v", "1", str(f0)], capture_output=True, timeout=20)
                subprocess.run(["ffmpeg", "-y", "-ss", "4.0", "-i", str(mp4_p), "-frames:v", "1", str(f1)], capture_output=True, timeout=20)
                if f0.is_file() and f1.is_file():
                    p0 = list(Image.open(f0).convert("RGB").getdata())[::16]
                    p1 = list(Image.open(f1).convert("RGB").getdata())[::16]
                    diff = sum(abs(a[0]-b[0])+abs(a[1]-b[1])+abs(a[2]-b[2]) for a, b in zip(p0, p1)) / max(1, len(p0)*3)
                    tt_ok = diff >= 1.5

    vp_renders = 0; contrast_ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for rt in ("index", "pricing", "integrations", "architecture", "enterprise", "telemetry"):
            turl = f"http://127.0.0.1:{sport}/{rt}"
            try:
                urllib.request.urlopen(turl, timeout=1.5).read(64)
            except Exception:
                p_h = repo / f"templates/{rt}.html"
                turl = f"file://{p_h}" if p_h.is_file() else turl
            for vw, vh in ((1280, 720), (768, 1024), (390, 844)):
                sp = Path(tmp) / f"{rt}_{vw}.png"
                cp = subprocess.run([
                    "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                    f"--window-size={vw},{vh}", f"--screenshot={sp}", turl,
                ], capture_output=True, text=True, timeout=25)
                if cp.returncode == 0 and sp.is_file():
                    im = Image.open(sp).convert("L")
                    if im.size == (vw, vh):
                        vp_renders += 1
                        sg = sorted(px / 255.0 for px in list(im.getdata())[::25])
                        if (sg[int(0.97 * len(sg))] - sg[int(0.05 * len(sg))]) < 0.28:
                            contrast_ok = False

    cms_32 = 0; web_10 = 0; fts_hits = 0
    if db_p.is_file():
        try:
            con = sqlite3.connect(str(db_p))
            rows = con.execute("SELECT slug, license_spdx, benchmark_num, asset_file, published FROM cms_integrations").fetchall()
            exp10 = {"flask": "BSD", "requests": "Apache", "httpx": "BSD", "sqlalchemy": "MIT", "pydantic": "MIT", "gpt2": "50257", "bert": "768", "transformer": "2017", "resnet": "2015", "gpt3": "2020"}
            for slug, lic, bnum, af, pub in rows:
                if int(pub) == 1 and (assets / str(af)).is_file():
                    cms_32 += 1
                    for k, tok in exp10.items():
                        if k in str(slug).lower() and (tok.lower() in str(lic).lower() or tok in str(bnum)):
                            web_10 += 1
            fts_hits = con.execute("SELECT COUNT(*) FROM cms_fts WHERE cms_fts MATCH 'MIT OR Apache OR 50257'").fetchone()[0]
            con.close()
        except sqlite3.Error:
            pass

    qa_xlsx = workspace / "QA_Master_Matrix.xlsx"
    xlsx_ok = web_sheet_ok = False
    if qa_xlsx.is_file():
        raw_q = read_multisheet_xlsx(qa_xlsx)
        ev_q = evaluate_xlsx_via_libreoffice(qa_xlsx)
        sr = raw_q.get("Summary", {}); se = ev_q.get("Summary", {})
        f_ok = all(bool((sr.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4"))
        xlsx_ok = f_ok and abs(_num(se, "B2") - total_asset_kb) <= 12.0 and abs(_num(se, "B3") - sim_p95_ms) <= 4.0
        web_sheet_ok = math.isclose(_num(se, "B4"), UA08_WEB_SUM, abs_tol=0.5)

    git_clean = False
    if (repo / ".git").is_dir():
        st = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout.strip()
        br = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        git_clean = (st == "" and br == "main")

    gates = {
        "G_FE_1_sixteen_responsive_routes": routes_ok,
        "G_FE_2_seven_seeded_bugs_remediated": math.isclose(ann_disc, 20.0, abs_tol=0.1) and math.isclose(ent_mult, 1.35, abs_tol=0.02) and tz_mode == "UTC" and csrf_ok and svg_ok and 10 <= fts_limit <= 100 and contrast_ok,
        "G_FE_3_coupled_p95_le_136ms_and_ram_le_310mb": sim_p95_ms <= 136.0 and staging_ram_mb <= 310.0,
        "G_DES_1_cycles_showroom_and_4_heroes": stage_gi_ok and heroes_ok,
        "G_DES_2_gimp_6cards_and_inkscape_6badges": cards_ok and badges_ok,
        "G_DES_3_turntable_192f_ebu_r128_and_payload_cap": tt_ok and 120.0 <= total_asset_kb <= 1360.0,
        "G_CMS_1_32_articles_fts5_and_6_arch_diagrams": cms_32 >= 32 and fts_hits >= 4 and cms_arch_ok,
        "G_CMS_2_ten_live_web_facts_verified": web_10 >= 10,
        "G_WEB_shared_xlsx_16_live_web_benchmarks": web_sheet_ok,
        "G_QA_1_18_chromium_renders_and_coupled_xlsx": vp_renders == 18 and contrast_ok and xlsx_ok,
        "G_QA_2_pdf_pptx_and_clean_git_main": (workspace / "exports/QA_Release_Report.pdf").is_file() and (workspace / "QA_Launch_Deck.pptx").is_file() and git_clean,
    }
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v), "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "sim_page_p95_ms": sim_p95_ms, "staging_ram_mb": staging_ram_mb,
            "total_asset_kb": total_asset_kb, "turntable_frames": tt_frames, "turntable_lufs": tt_lufs,
            "cms_published_32": cms_32, "fts_hits": fts_hits, "web_10_count": web_10,
            "chromium_viewport_renders": vp_renders, "optical_contrast_ok": contrast_ok, "git_clean": git_clean,
        },
    }


def eval_ua10_drc(workspace: Path, burst_mult: float = 1.0) -> dict:
    """UA-10 Flagship Cyber-Physical War-Room DRC: FreeCAD 72-angle BRep + PyQGIS 48-POP + Cycles Thermal + 540MB RAM (~42s)."""
    t0 = time.monotonic()
    cdir = workspace / "cluster"
    db_p = cdir / "prod_ledger.db"
    has_i1 = has_i2 = has_i3 = False
    orphan_cnt = 999
    if db_p.is_file():
        try:
            con = sqlite3.connect(str(db_p))
            idxs = [str(r[1]) for r in con.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='ledger_events'").fetchall() if r[1]]
            orphan_cnt = int(con.execute("SELECT COUNT(*) FROM ledger_events WHERE region_code = 'CORRUPT_SHARD'").fetchone()[0])
            con.close()
            has_i1 = any("account_id" in s and "event_ts" in s for s in idxs)
            has_i2 = any("region_code" in s and "status" in s for s in idxs)
            has_i3 = any("shard_id" in s and "event_ts" in s for s in idxs)
        except sqlite3.Error:
            pass

    db_c = json.loads((cdir / "db_tuning.json").read_text()) if (cdir / "db_tuning.json").is_file() else {}
    ap_c = json.loads((cdir / "app_gateway.json").read_text()) if (cdir / "app_gateway.json").is_file() else {}
    in_c = json.loads((cdir / "infra_daemon.json").read_text()) if (cdir / "infra_daemon.json").is_file() else {}
    db_mb = float(db_c.get("sqlite_cache_mb", 24.0)); batch_sz = int(db_c.get("checkpoint_batch", 5000))
    ap_mb = float(ap_c.get("hot_cache_mb", 24.0)); backoff = float(ap_c.get("retry_backoff_ms", 0.0))
    retries = int(ap_c.get("max_retries", 12)); ttl_s = float(ap_c.get("cache_ttl_s", 0.0))
    sf = bool(ap_c.get("singleflight", False)); tb_rps = float(ap_c.get("token_bucket_rps", 150.0))
    in_mb = float(in_c.get("telemetry_buffer_mb", 280.0)); log_lv = str(in_c.get("log_level", "TRACE_ALL"))
    live_ms = float(in_c.get("liveness_timeout_ms", 40.0))
    disk_kb = ((cdir / "disk_vol/core_trace.bin").stat().st_size / 1024.0) if (cdir / "disk_vol/core_trace.bin").is_file() else 0.0

    tot_ram = round(db_mb + ap_mb + in_mb, 2)
    oom = tot_ram > 540.0

    q_ok, q_lays = _eval_pyqgis_layouts(workspace / "Metro_Edge_Grid.qgz", ("DB_Replication_A3", "Edge_Reroute_A3"))
    gpkg_p = workspace / "data/edge_grid.gpkg"
    sev_zero = False; max_util = 9.9; geo_rtt = 999.0; transit_cost = 999.0; repl_lag_ms = 999.0
    if gpkg_p.is_file():
        try:
            con = sqlite3.connect(str(gpkg_p))
            pops = con.execute("SELECT pop_id, cable_status, capacity_gbps, assigned_traffic_gbps, base_rtt_ms, cost_per_gbps FROM edge_pops").fetchall()
            shds = con.execute("SELECT shard_id, sync_bw_gbps, wal_quorum FROM db_shards").fetchall()
            con.close()
            tot_tr = sum(float(r[3]) for r in pops)
            tot_rep_bw = sum(float(r[1]) for r in shds)
            if abs(tot_tr - 960.0) <= 2.0 and len(shds) == 16 and all(int(r[2]) >= 2 for r in shds):
                sev_zero = all(float(r[3]) <= 0.01 for r in pops if r[1] == "SEVERED")
                utils = []; w_rtt = 0.0; t_cost = tot_rep_bw * 0.095
                for _pid, st_c, cap, asg, rtt, cpg in pops:
                    u = (float(asg) / max(0.1, float(cap))) if st_c != "SEVERED" else (9.9 if float(asg) > 0.01 else 0.0)
                    utils.append(u)
                    q_delay = 4.2 * u / max(0.06, 1.0 - min(0.94, u))
                    w_rtt += float(asg) * (float(rtt) + q_delay)
                    t_cost += float(asg) * float(cpg)
                max_util = max(utils); geo_rtt = w_rtt / max(1.0, tot_tr); transit_cost = t_cost
                min_sbw = min(float(r[1]) for r in shds)
                repl_lag_ms = round(185.0 / max(0.5, min_sbw), 2)
        except sqlite3.Error:
            pass

    fc_p = workspace / "cryo_cooling_valve.FCStd"
    fc = _eval_harmonic_cam_fcstd(fc_p)
    cert_p = workspace / "exports/valve_cae_cert.json"
    cert_ok = cert_p.is_file() and json.loads(cert_p.read_text()).get("fcstd_sha256") == _sha256(fc_p) and json.loads(cert_p.read_text()).get("valve_passed") is True
    valve_ok = bool(
        fc.get("ok") and 18.32 <= fc["stroke"] <= 18.48 and fc["max_pa"] <= 25.5
        and fc["min_ch"] >= 3.40 and 0.15 <= fc["home_gap"] <= 0.23 and fc["coll_vol"] <= 0.02
        and fc["mass_tot"] <= 0.855 and fc["cg_r"] <= 0.65 and cert_ok
    )

    cyc = _eval_cycles_atrium(workspace / "rack_thermal_twin.blend", samples=38, check_bars=False)
    therm_louver_ok = bool(cyc.get("ok") and cyc["noon_solar_gain"] <= 0.495 and cyc["morning_luma"] >= 0.355)
    aisle_gi_ok = bool(cyc.get("ok") and all(0.635 <= z <= 0.785 for z in cyc["comb_zones"]) and cyc["uniformity"] >= 0.860 and (workspace / "exports/rack_thermal_forensics.png").is_file())

    idx_pen = 0.0 if (has_i1 and has_i2 and has_i3 and orphan_cnt == 0 and batch_sz <= 400 and db_mb >= 185.0) else 195.0
    gw_ok = (150.0 <= backoff <= 600.0 and 1 <= retries <= 3 and ttl_s >= 90.0 and sf and 950.0 <= tb_rps <= 1800.0 and ap_mb >= 215.0)
    inf_ok = (log_lv == "INFO" and live_ms >= 800.0 and disk_kb <= 100.0 and 90.0 <= in_mb <= 135.0)
    p99_ms = round((19.5 * burst_mult + idx_pen + (0.0 if gw_ok else 140.0) + (0.0 if inf_ok else 85.0) + (0.0 if valve_ok else 45.0) + max(0.0, geo_rtt - 40.0) * 1.4), 2)
    if oom: p99_ms = 999.0
    err_rate = round(0.0 if (not oom and p99_ms <= 72.0 and sev_zero and max_util <= 0.74) else 0.16, 4)

    cap_p = workspace / "Capacity_Master.xlsx"
    cap_ok = web_ok = False
    if cap_p.is_file():
        rq = read_multisheet_xlsx(cap_p); eq = evaluate_xlsx_via_libreoffice(cap_p)
        sr = rq.get("Summary", {}); se = eq.get("Summary", {})
        f_ok = all(bool((sr.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4"))
        cap_ok = f_ok and abs(_num(se, "B2") - tot_ram) <= 2.0 and tot_ram <= 540.0
        web_ok = math.isclose(_num(se, "B4"), UA08_WEB_SUM, abs_tol=0.5)

    fp60 = workspace / "forensics/db_fingerprint_60s.json"
    fp_ok = fp60.is_file() and bool(json.loads(fp60.read_text()).get("sufficient_window_60s"))

    gates = {
        "G_DB_1_three_indexes_clean_shards_and_repl_lag": has_i1 and has_i2 and has_i3 and orphan_cnt == 0 and batch_sz <= 400 and repl_lag_ms <= 32.0,
        "G_DB_2_forensics_60s_and_db_qgis_atlas": fp_ok and ("DB_Replication_A3" in q_lays) and (workspace / "exports/db_replication_atlas.pdf").is_file(),
        "G_APP_1_gateway_singleflight_and_540mb_ram_corridor": gw_ok and (not oom) and db_mb >= 185.0 and ap_mb >= 215.0 and 90.0 <= in_mb <= 135.0,
        "G_APP_2_qgis_48pop_reroute_and_cost_cap": sev_zero and max_util <= 0.74 and geo_rtt <= 48.5 and transit_cost <= 84.0 and ("Edge_Reroute_A3" in q_lays) and (workspace / "exports/edge_reroute_map.pdf").is_file(),
        "G_INF_1_daemon_disk_and_cycles_thermal_louvers": inf_ok and therm_louver_ok,
        "G_INF_2_harmonic_cryo_valve_72angle_and_cae": valve_ok,
        "G_WEB_shared_xlsx_16_live_web_standards": web_ok,
        "G_IC_1_cycles_aisle_forensics_and_p99_le_58ms": aisle_gi_ok and p99_ms <= 58.0 and err_rate == 0.0,
        "G_IC_2_capacity_xlsx_rca_pdf_and_pptx": cap_ok and (workspace / "exports/INC_Postmortem_RCA.pdf").is_file() and (workspace / "WarRoom_Executive.pptx").is_file(),
    }
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v), "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "p99_ms": p99_ms, "error_rate": err_rate, "total_cluster_ram_mb": tot_ram, "oom_triggered": oom,
            "max_pop_utilization": round(max_util, 4), "geo_rtt_ms": round(geo_rtt, 2),
            "transit_plus_repl_cost_kusd_h": round(transit_cost, 2), "db_repl_lag_ms": repl_lag_ms,
            "valve_kinematics": {k: fc.get(k) for k in ("stroke", "max_pa", "min_ch", "home_gap", "coll_vol", "mass_tot", "cg_r")},
            "cycles_thermal": {k: cyc.get(k) for k in ("morning_luma", "noon_solar_gain", "comb_zones", "uniformity")},
        },
    }


def eval_ua11_drc(workspace: Path) -> dict:
    """UA-11 Flagship Aero-Actuator DRC: Zero-hint 72-angle Harmonic BRep + 4-pass Cycles Cutaway + 480f BT.709/EBU-R128 (~42s)."""
    t0 = time.monotonic()
    fc_p = workspace / "harmonic_actuator.FCStd"
    fc = _eval_harmonic_cam_fcstd(fc_p)
    cert_p = workspace / "exports/cae_cert.json"
    cert_ok = cert_p.is_file() and json.loads(cert_p.read_text()).get("fcstd_sha256") == _sha256(fc_p) and json.loads(cert_p.read_text()).get("cae_passed") is True

    cyc = _eval_cycles_atrium(workspace / "studio_cutaway.blend", samples=44, check_bars=False)
    cae_louver_ok = bool(cyc.get("ok") and cyc["noon_solar_gain"] <= 0.495 and cyc["morning_luma"] >= 0.355)
    media_gi_ok = bool(cyc.get("ok") and all(0.635 <= z <= 0.785 for z in cyc["comb_zones"]) and cyc["uniformity"] >= 0.860 and (workspace / "exports/cutaway_beauty.png").is_file())

    bom_p = workspace / "Engineering_Master_BOM.xlsx"
    bom_ok = web_ok = False
    if bom_p.is_file() and fc.get("ok"):
        rb = read_multisheet_xlsx(bom_p); eb = evaluate_xlsx_via_libreoffice(bom_p)
        sr = rb.get("Summary", {}); se = eb.get("Summary", {})
        f_ok = all(bool((sr.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4"))
        v_mass_g = _num(se, "B3")
        bom_ok = f_ok and abs(v_mass_g - fc["mass_tot"] * 1000.0) <= 4.0
        web_ok = math.isclose(_num(se, "B4"), UA08_WEB_SUM, abs_tol=0.5)

    mp4_p = workspace / "exports/actuator_master_480f.mp4"
    vid_ok = False; frames = 0; lufs = None; ymin = 0.0; ymax = 999.0
    if mp4_p.is_file():
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(mp4_p)], capture_output=True, text=True, timeout=45)
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            frames = int(st.get("nb_read_frames") or 0)
            wh_ok = (int(st.get("width", 0)), int(st.get("height", 0))) == (1280, 720)
        except Exception:
            wh_ok = False
        cp_l = subprocess.run(["ffmpeg", "-nostats", "-i", str(mp4_p), "-filter_complex", "ebur128=framelog=verbose", "-f", "null", "-"], capture_output=True, text=True, timeout=60)
        ms = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", cp_l.stderr)
        lufs = float(ms[-1]) if ms else None
        cp_s = subprocess.run(["ffmpeg", "-i", str(mp4_p), "-vf", "signalstats,metadata=print:file=-", "-frames:v", "48", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        yms = [float(x) for x in re.findall(r"YMIN=(\d+(?:\.\d+)?)", cp_s.stdout + cp_s.stderr)]
        yxs = [float(x) for x in re.findall(r"YMAX=(\d+(?:\.\d+)?)", cp_s.stdout + cp_s.stderr)]
        if yms and yxs:
            ymin, ymax = min(yms), max(yxs)
        vid_ok = wh_ok and (476 <= frames <= 484) and (lufs is not None and -23.4 <= lufs <= -22.6) and ymin >= 16.0 and ymax <= 235.0

    gates = {
        "G_HOUS_1_cam_housing_clearance_and_cover_stiffness": bool(fc.get("ok") and fc["min_ch"] >= 3.40 and fc["cover_v"] >= 82000.0 and (workspace / "exports/housing_cover.step").is_file()),
        "G_HOUS_2_coupled_4part_mass_le_0_855kg_and_cg_le_0_65mm": bool(fc.get("ok") and fc["mass_tot"] <= 0.855 and fc["cg_r"] <= 0.65),
        "G_ROT_1_exact_stroke_18_34_to_18_46_and_pa_le_25_5": bool(fc.get("ok") and 18.34 <= fc["stroke"] <= 18.46 and fc["max_pa"] <= 25.5),
        "G_ROT_2_hydrodynamic_gap_015_023_zero_collision": bool(fc.get("ok") and 0.15 <= fc["home_gap"] <= 0.23 and fc["coll_vol"] <= 0.02 and (workspace / "exports/cam_follower.step").is_file()),
        "G_CAE_1_exclusive_20s_solver_cert_and_cycles_baffles": cert_ok and cae_louver_ok,
        "G_CAE_2_coupled_bom_xlsx_and_whitepaper_pdf": bom_ok and (workspace / "exports/Engineering_Whitepaper.pdf").is_file(),
        "G_WEB_shared_xlsx_16_live_web_benchmarks": web_ok,
        "G_MED_1_cycles_6zone_studio_cutaway": media_gi_ok,
        "G_MED_2_480f_720p_bt709_ebu_r128_master": vid_ok,
    }
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v), "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "kinematics": {k: fc.get(k) for k in ("stroke", "max_pa", "min_ch", "home_gap", "coll_vol", "mass_b", "mass_tot", "cg_r", "cover_v", "part_cm3")},
            "cae_cert_valid": cert_ok,
            "studio_photometry": {k: cyc.get(k) for k in ("morning_luma", "noon_solar_gain", "comb_zones", "uniformity", "power_w")},
            "mp4_frames": frames, "mp4_lufs": lufs, "mp4_ymin": ymin, "mp4_ymax": ymax,
        },
    }

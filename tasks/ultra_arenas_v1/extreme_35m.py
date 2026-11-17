"""Extreme 35-55+ minute 4-agent combinatorial & blind-rig marathon arenas (UA-12, UA-13)."""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import textwrap
import time
import urllib.request

try:
    from tasks.ultra_arenas_v1.catalog import UA_BY_ID
except ImportError:
    from catalog import UA_BY_ID  # type: ignore

try:
    from tasks.thematic_arenas_v1.xlsx_utils import (
        evaluate_xlsx_via_libreoffice,
        read_multisheet_xlsx,
        update_single_sheet_xlsx,
        write_multisheet_xlsx,
    )
except ImportError:
    from xlsx_utils import (  # type: ignore
        evaluate_xlsx_via_libreoffice,
        read_multisheet_xlsx,
        update_single_sheet_xlsx,
        write_multisheet_xlsx,
    )

try:
    from tasks.ultra_arenas_v1.flagship_30m import (
        UA08_BI_PAGES,
        UA08_WEB_SPECS,
        UA08_WEB_SUM,
        _eval_harmonic_cam_fcstd,
        _eval_pyqgis_layouts,
        _num,
        _sha256,
    )
except ImportError:
    from flagship_30m import (  # type: ignore
        UA08_BI_PAGES,
        UA08_WEB_SPECS,
        UA08_WEB_SUM,
        _eval_harmonic_cam_fcstd,
        _eval_pyqgis_layouts,
        _num,
        _sha256,
    )

EXTREME_IDS = ("UA-12", "UA-13", "UA-14", "UA-15")
HUB_10 = {0, 1, 4, 5, 8, 9, 12, 13, 16, 17}
HOT_SHARDS_6 = {"SHD_01", "SHD_04", "SHD_07", "SHD_10", "SHD_13", "SHD_16"}


def _eval_blind_cycles_rig(blend_path: Path, samples: int = 50, check_bars: bool = False) -> dict:
    """Evaluate .blend using a hidden server-side oblique sensor rig (prevents local samples=4 proxy bypass)."""
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
            # Inject hidden workstation photometric rig & solar source
            sd = bpy.data.lights.new('HiddenSunData', type='SUN'); sd.energy = 4.2
            sun = bpy.data.objects.new('HiddenSun', object_data=sd); sun.location = (0.0, 0.0, 8.0)
            sc.collection.objects.link(sun)
            cd = bpy.data.cameras.new('HiddenRigData'); cd.type = 'ORTHO'; cd.ortho_scale = 13.5
            cam = bpy.data.objects.new('HiddenRig', object_data=cd); cam.location = (0.25, 0.0, 3.8); cam.rotation_euler = (0.0, 0.0, 0.0)
            sc.collection.objects.link(cam); sc.camera = cam
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

        def _st(p: Path) -> tuple[float, list[float]]:
            with Image.open(p) as im:
                g = [px / 255.0 for px in im.convert("L").tobytes()]
                w, h = im.size
                zs = [
                    round(sum(g[yy * w + xx] for yy in range(int(h * 0.28), int(h * 0.72)) for xx in range(int(w * (0.08 + zi * 0.14)), int(w * (0.20 + zi * 0.14)))) / max(1, (int(h * 0.72) - int(h * 0.28)) * (int(w * (0.20 + zi * 0.14)) - int(w * (0.08 + zi * 0.14)))), 4)
                    for zi in range(6)
                ]
                return round(sum(g) / len(g), 4), zs

        m_m, _ = _st(td / "morn.png")
        n_m, _ = _st(td / "noon.png")
        a_m, _ = _st(td / "aft.png")
        c_m, c_zs = _st(td / "comb.png")
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
            "ok": True, "morning_luma": m_m, "noon_solar_gain": n_m, "afternoon_luma": a_m,
            "comb_mean": c_m, "comb_zones": c_zs, "uniformity": unif,
            "power_w": round(meta["power_w"], 2), "louver_vol": meta["louver_vol"], "bars_ok": bars_ok,
        }


def _eval_chromium_role_cards(workspace: Path, roles: tuple[str, ...]) -> tuple[int, bool]:
    """Render each role's HTML briefing card across 3 viewports (12 real headless Chromium renders, ~12s)."""
    from PIL import Image
    renders = 0
    contrast_all = True
    with tempfile.TemporaryDirectory() as tmp:
        for r in roles:
            hp = workspace / f"briefings/{r}_card.html"
            if not hp.is_file():
                contrast_all = False
                continue
            for vw, vh in ((1280, 720), (768, 1024), (390, 844)):
                sp = Path(tmp) / f"{r}_{vw}.png"
                cp = subprocess.run([
                    "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                    f"--window-size={vw},{vh}", f"--screenshot={sp}", f"file://{hp}",
                ], capture_output=True, text=True, timeout=25)
                if cp.returncode == 0 and sp.is_file():
                    im = Image.open(sp).convert("L")
                    if im.size == (vw, vh):
                        renders += 1
                        sg = sorted(px / 255.0 for px in list(im.getdata())[::25])
                        if (sg[int(0.97 * len(sg))] - sg[int(0.05 * len(sg))]) < 0.28:
                            contrast_all = False
    return renders, (renders == len(roles) * 3 and contrast_all)


def eval_ua12_drc(workspace: Path) -> dict:
    """UA-12 Extreme QBR DRC: Max-10 DC & Max-10 Territory Combinatorics + 0.70% Pareto + Blind Cycles + 12x Chromium (~52s)."""
    t0 = time.monotonic()
    xlsx_p = workspace / "Q4_Enterprise_Master_Model.xlsx"
    if not xlsx_p.is_file():
        return {"ok": False, "error": "Missing Q4_Enterprise_Master_Model.xlsx"}
    raw_wb = read_multisheet_xlsx(xlsx_p)
    ev_wb = evaluate_xlsx_via_libreoffice(xlsx_p)
    s_raw = raw_wb.get("Executive_Summary", {}); s_ev = ev_wb.get("Executive_Summary", {})
    formulas_ok = all(bool((s_raw.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4", "B5", "B6", "B7", "B8"))

    base_rev = _num(s_ev, "B2"); direct_cost = _num(s_ev, "B3"); ops_cost = _num(s_ev, "B4")
    sales_weighted = _num(s_ev, "B5"); debt_q = _num(s_ev, "B6"); noi = _num(s_ev, "B7"); web_sum = _num(s_ev, "B8")

    dc_sh = ev_wb.get("Datacenter_24R", {})
    tot_act = tot_fo = eff_cap = therm_pen = 0.0
    mod_dcs = 0; pues = []; hot_dcs = []
    for i in range(24):
        r = i + 2
        ac = _num(dc_sh, f"C{r}", 20.0); fo = _num(dc_sh, f"D{r}", 5.0); pu = _num(dc_sh, f"E{r}", 1.32)
        if abs(ac - 20.0) > 0.1 or abs(fo - 5.0) > 0.1 or abs(pu - 1.32) > 0.005:
            mod_dcs += 1
        tot_act += ac; tot_fo += fo; pues.append(pu)
        w = 2.15 if i in HUB_10 else 0.55
        p_fl = 1.21 if i in HUB_10 else 1.29
        sat = ac - 0.028 * max(0.0, ac - 33.0) ** 2
        eff_cap += (sat + 0.65 * fo) * w
        if pu < p_fl:
            therm_pen += (p_fl - pu) * 95.0; hot_dcs.append(f"DC_{i+1:02d}(wetbulb_floor)")
        elif (i not in HUB_10) and ac > 25.0:
            therm_pen += 11.5; hot_dcs.append(f"DC_{i+1:02d}(legacy_substation_sat)")
    mean_pue = sum(pues) / 24.0

    sp_sh = ev_wb.get("Pipeline_24T", {})
    mod_terrs = 0; churn = 0.0; nrr_acc = 0.0; rbs = []; churn_ts = []
    for i in range(24):
        r = i + 2
        pm = _num(sp_sh, f"E{r}", 1.0); rb = _num(sp_sh, f"F{r}", 0.0); rbs.append(rb)
        if abs(pm - 1.0) > 0.002 or abs(rb) > 0.002:
            mod_terrs += 1
        cap = 1.18 if i in HUB_10 else 1.008
        nw = 2.25 if i in HUB_10 else 0.25
        if pm > cap:
            churn += ((pm - cap) ** 2) * 5200.0; churn_ts.append(f"T_{i+1:02d}(procurement_cliff)")
        elif pm < 0.98:
            churn += (0.98 - pm) * 500.0
        nrr_acc += nw * (65.0 * (pm - 0.95) + 88.0 * rb)
    mean_rb = sum(rbs) / 24.0
    eff_nrr = round(104.0 + (nrr_acc / 24.0) - 0.025 * churn, 2)

    req_cap = 835.0 * (eff_nrr / 116.0)
    p95_lat = round(23.5 / max(0.35, eff_cap / max(1.0, req_cap)) + max(0.0, (mean_pue - 1.30) * 38.0) + therm_pen, 2)
    fo_ratio = tot_fo / max(1.0, tot_act)

    fin_sh = ev_wb.get("Finance_24U", {})
    hedge = _num(fin_sh, "G2", 0.15); reserve = _num(fin_sh, "G3", 320.0)
    worst_dscr = 99.0; min_cash = 99999.0
    for pi in range(6000):
        ph = (pi + 1) * 0.131
        m_shk = 1.0 - 0.11 * abs(math.sin(ph)) - 0.065 * (1.0 - min(1.0, hedge)) * abs(math.cos(ph * 1.7))
        p_spk = 1.0 + 0.14 * max(0.0, mean_pue - 1.25) * abs(math.sin(ph * 0.9))
        eb = (base_rev * m_shk + 0.20 * sales_weighted * m_shk - churn) - direct_cost - (ops_cost * p_spk) - (hedge * 65.0)
        dscr = eb / max(1.0, debt_q); cend = reserve + 0.35 * (eb - debt_q)
        if dscr < worst_dscr: worst_dscr = dscr
        if cend < min_cash: min_cash = cend

    noi_margin = round(100.0 * noi / max(1.0, base_rev + 0.20 * sales_weighted), 2)
    q_ok, q_lays = _eval_pyqgis_layouts(workspace / "global_qbr_atlas.qgz", ("Global_DC_Capacity_A3", "Sales_Territory_Risk_A3"))
    gpkg_p = workspace / "data/qbr_spatial.gpkg"
    gpkg_dc_ok = gpkg_sl_ok = False
    if gpkg_p.is_file():
        try:
            con = sqlite3.connect(str(gpkg_p))
            dc_s = float(con.execute("SELECT COALESCE(SUM(active_racks),0) FROM dc_sites").fetchone()[0])
            sl_s = float(con.execute("SELECT COALESCE(SUM(weighted_arr),0) FROM sales_territories").fetchone()[0])
            con.close()
            gpkg_dc_ok = abs(dc_s - tot_act) <= 3.0; gpkg_sl_ok = abs(sl_s - sales_weighted) <= 12.0
        except sqlite3.Error:
            pass

    cyc = _eval_blind_cycles_rig(workspace / "hq_flagship_atrium.blend", samples=48, check_bars=True)
    louver_ok = bool(cyc.get("ok") and cyc["noon_solar_gain"] <= 0.485 and cyc["morning_luma"] >= 0.370 and cyc["afternoon_luma"] >= 0.435 and 7.5 <= cyc["louver_vol"] <= 13.5)
    exec_gi_ok = bool(cyc.get("ok") and all(0.680 <= z <= 0.760 for z in cyc["comb_zones"]) and cyc["uniformity"] >= 0.905 and cyc["power_w"] <= 360.0 and cyc["bars_ok"] and (workspace / "exports/q4_boardroom_3d.png").is_file())
    chr_cnt, chr_ok = _eval_chromium_role_cards(workspace, ("FIN", "OPS", "SALES", "EXEC"))

    gates = {
        "G_FIN_1_restated_rev_8210_and_cost_2940": math.isclose(base_rev, 8210.0, abs_tol=2.0) and math.isclose(direct_cost, 2940.0, abs_tol=2.0),
        "G_FIN_2_stress_dscr_ge_1_60_and_cash_window_740_960": worst_dscr >= 1.60 and 740.0 <= min_cash <= 960.0,
        "G_FIN_3_razor_pareto_noi_margin_50_40_to_51_10": 50.40 <= noi_margin <= 51.10,
        "G_OPS_1_discrete_max_10_modified_dcs_and_p95_le_23_8ms": 1 <= mod_dcs <= 10 and p95_lat <= 23.8 and len(hot_dcs) == 0,
        "G_OPS_2_failover_24_34pct_and_cost_1550_1820": 0.24 <= fo_ratio <= 0.34 and 1550.0 <= ops_cost <= 1820.0,
        "G_OPS_3_blind_cycles_louvers_and_qgis_dc_atlas": louver_ok and ("Global_DC_Capacity_A3" in q_lays) and gpkg_dc_ok and (workspace / "exports/DC_Global_Atlas.pdf").is_file(),
        "G_SALES_1_discrete_max_10_repriced_and_weighted_5950_6750": 1 <= mod_terrs <= 10 and 5950.0 <= sales_weighted <= 6750.0,
        "G_SALES_2_nrr_ge_116_5_zero_cliff_churn": eff_nrr >= 116.5 and churn <= 35.0 and mean_rb <= 0.065,
        "G_SALES_3_qgis_sales_atlas_synced": ("Sales_Territory_Risk_A3" in q_lays) and gpkg_sl_ok and (workspace / "exports/Sales_Territory_Atlas.pdf").is_file(),
        "G_WEB_all_4_roles_16_live_web_benchmarks": math.isclose(web_sum, UA08_WEB_SUM, abs_tol=0.5),
        "G_CARDS_all_4_roles_12_chromium_briefing_renders": chr_ok,
        "G_EXEC_1_summary_formulas_intact": formulas_ok,
        "G_EXEC_2_blind_asymmetric_6zone_gi_and_3d_bars": exec_gi_ok,
        "G_EXEC_3_board_pdf_and_pptx": (workspace / "exports/Q4_Board_Briefing.pdf").is_file() and (workspace / "Q4_Board_Deck.pptx").is_file(),
    }
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v), "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "base_rev_kusd": round(base_rev, 2), "ops_cost_kusd": round(ops_cost, 2), "sales_weighted_kusd": round(sales_weighted, 2),
            "noi_kusd": round(noi, 2), "noi_margin_pct": noi_margin, "worst_24q_dscr": round(worst_dscr, 4), "min_stress_cash_kusd": round(min_cash, 2),
            "modified_dcs_count": mod_dcs, "p95_latency_ms": p95_lat, "failover_ratio": round(fo_ratio, 4),
            "repriced_territories_count": mod_terrs, "effective_nrr_pct": eff_nrr, "churn_penalty_kusd": round(churn, 2),
            "throttled_datacenters": hot_dcs[:8], "high_churn_territories": churn_ts[:8],
            "chromium_card_renders": chr_cnt, "cycles_photometry": cyc,
        },
    }


def eval_ua13_drc(workspace: Path, burst_mult: float = 1.0) -> dict:
    """UA-13 Extreme War-Room DRC: 72-Node 6-Tier DAG + Max-6 Hot Shards + Cavitation Valve + Blind Cycles + 12x Chromium (~55s)."""
    t0 = time.monotonic()
    cdir = workspace / "cluster"; db_p = cdir / "prod_ledger.db"
    has_i1 = has_i2 = has_i3 = False; orphan_cnt = 999
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

    # 72-node 6-tier DAG + 24 shapers + 16 DB shards (max 6 promoted!)
    q_ok, q_lays = _eval_pyqgis_layouts(workspace / "Metro_Edge_Grid.qgz", ("DB_Replication_A3", "Edge_DAG_A3"))
    gpkg_p = workspace / "data/edge_grid.gpkg"
    out_100 = 999.0; overtopped = 99; t5_100 = 999.0; crit_500 = 99; rech = 0.0; mod_nodes = 0; tot_dag_cap = 999.0
    prom_shards = 0; repl_lag_ms = 999.0; lagging_shds = []
    if gpkg_p.is_file():
        try:
            con = sqlite3.connect(str(gpkg_p))
            subs = list(con.execute("SELECT basin_id, tier, downstream_id, area_ha, cn_curve, green_ha, weir_id FROM subbasins ORDER BY tier, basin_id"))
            weirs = {wid: (float(om), float(sk), float(cr)) for wid, om, sk, cr in con.execute("SELECT weir_id, orifice_m2, storage_k_m3, crest_m FROM weirs")}
            shds = con.execute("SELECT shard_id, sync_bw_gbps, wal_quorum FROM db_shards").fetchall()
            con.close()
            storms_mm = [48.0, 62.0, 75.0, 88.0, 102.0, 118.0, 134.0, 148.0, 165.0, 182.0, 205.0, 232.0]
            overtopped = 0; crit_500 = 0; out_100 = 0.0; t5_100 = 0.0
            for s_idx, rain_mm in enumerate(storms_mm):
                inflow = {r[0]: 0.0 for r in subs}; inflow["OUTLET"] = 0.0; w_vol = {w: 0.0 for w in weirs}
                for bid, tier, ds_id, area_ha, cn, green_ha, wid in subs:
                    af = float(area_ha); gf = max(0.0, min(af * 0.25, float(green_ha)))
                    eff_cn = float(cn) - (gf / af) * 38.0
                    pot_s = max(5.0, 25400.0 / eff_cn - 254.0)
                    q_d = ((max(0.0, rain_mm - 0.2 * pot_s)) ** 2) / (rain_mm + 0.8 * pot_s)
                    loc_q = (af * q_d * 0.00052) * (1.0 + 0.04 * (6 - int(tier)))
                    tot_in = loc_q + inflow[bid]; om, sk, cr = weirs[wid]
                    att = (om * math.sqrt(2 * 9.81 * cr)) / (om * math.sqrt(2 * 9.81 * cr) + sk * 0.32)
                    ps = 1.18 if (int(tier) == 4 and abs(om - 1.10) < 0.25) else 1.0
                    rq = tot_in * att * ps; w_vol[wid] += (tot_in - rq) * 1.35
                    if s_idx == 9 and int(tier) == 5: t5_100 = max(t5_100, rq)
                    if s_idx == 11 and int(tier) == 6 and rq > 11.4: crit_500 += 1
                    inflow[ds_id] = inflow.get(ds_id, 0.0) + rq * 0.86
                if s_idx == 9: out_100 = round(inflow["OUTLET"], 3)
                for w, vu in w_vol.items():
                    if vu > weirs[w][1] * 1.05: overtopped += 1
            mod_nodes = sum(1 for r in subs if float(r[5]) > 0.01 and float(r[5]) <= 0.2201 * float(r[3]))
            illegal_nodes = sum(1 for r in subs if float(r[5]) > 0.2201 * float(r[3]))
            if illegal_nodes > 0: mod_nodes = 99
            gr_sum = sum(float(r[5]) for r in subs); tot_ha = sum(float(r[3]) for r in subs)
            rech = round((gr_sum / max(1.0, tot_ha)) * 3.80, 4)
            grey_cap = sum(0.014 * sk + 0.11 * cr + 0.12 * max(0.0, 2.0 - om) for om, sk, cr in weirs.values())
            tot_dag_cap = round(grey_cap + gr_sum * 0.036, 3)

            lags = []
            for sid, sbw, wq in shds:
                bw = float(sbw)
                if bw > 2.0: prom_shards += 1
                w_skew = 210.0 if sid in HOT_SHARDS_6 else 28.0
                lg = w_skew / max(0.5, bw) + (0.0 if int(wq) >= 2 else 40.0)
                lags.append(lg)
                if lg > 29.0: lagging_shds.append(sid)
            repl_lag_ms = round(max(lags) if lags else 999.0, 2)
        except sqlite3.Error:
            pass

    fc_p = workspace / "cryo_cooling_valve.FCStd"
    fc = _eval_harmonic_cam_fcstd(fc_p)
    cert_p = workspace / "exports/valve_cae_cert.json"
    cert_ok = cert_p.is_file() and json.loads(cert_p.read_text()).get("fcstd_sha256") == _sha256(fc_p) and json.loads(cert_p.read_text()).get("valve_passed") is True
    valve_ok = bool(fc.get("ok") and 18.35 <= fc["stroke"] <= 18.45 and fc["max_pa"] <= 23.5 and fc["min_ch"] >= 3.40 and 0.16 <= fc["home_gap"] <= 0.22 and fc["coll_vol"] <= 0.02 and 0.600 <= fc["mass_tot"] <= 0.720 and fc["cg_r"] <= 0.45 and cert_ok)

    cyc = _eval_blind_cycles_rig(workspace / "rack_thermal_twin.blend", samples=48, check_bars=False)
    therm_ok = bool(cyc.get("ok") and cyc["noon_solar_gain"] <= 0.485 and cyc["morning_luma"] >= 0.370)
    aisle_ok = bool(cyc.get("ok") and all(0.680 <= z <= 0.760 for z in cyc["comb_zones"]) and cyc["uniformity"] >= 0.905 and cyc["power_w"] <= 360.0 and (workspace / "exports/rack_thermal_forensics.png").is_file())
    chr_cnt, chr_ok = _eval_chromium_role_cards(workspace, ("DB", "APP", "INFRA", "IC"))

    ram_corridor_ok = (515.0 <= tot_ram <= 536.0 and db_mb >= 188.0 and ap_mb >= 218.0 and 95.0 <= in_mb <= 125.0)
    gw_ok = (150.0 <= backoff <= 600.0 and 1 <= retries <= 3 and ttl_s >= 90.0 and sf and 950.0 <= tb_rps <= 1800.0)
    inf_ok = (log_lv == "INFO" and live_ms >= 800.0 and disk_kb <= 100.0)
    dag_ok = (out_100 <= 55.0 and overtopped == 0 and t5_100 <= 16.0 and crit_500 == 0 and 1 <= mod_nodes <= 26 and 0.315 <= rech <= 0.342 and tot_dag_cap <= 25.80)
    db_ok = (has_i1 and has_i2 and has_i3 and orphan_cnt == 0 and batch_sz <= 400 and 1 <= prom_shards <= 6 and repl_lag_ms <= 29.0)

    p99_ms = round(19.0 * burst_mult + (0.0 if db_ok else 160.0) + (0.0 if gw_ok else 130.0) + (0.0 if inf_ok else 80.0) + (0.0 if dag_ok else 95.0) + (0.0 if valve_ok else 45.0), 2)
    if not ram_corridor_ok: p99_ms = 999.0
    err_rate = 0.0 if (ram_corridor_ok and p99_ms <= 62.0) else 0.18

    cap_p = workspace / "Capacity_Master.xlsx"
    cap_ok = web_ok = False
    if cap_p.is_file():
        rq = read_multisheet_xlsx(cap_p); eq = evaluate_xlsx_via_libreoffice(cap_p)
        sr = rq.get("Summary", {}); se = eq.get("Summary", {})
        f_ok = all(bool((sr.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4"))
        cap_ok = f_ok and abs(_num(se, "B2") - tot_ram) <= 2.0 and ram_corridor_ok
        web_ok = math.isclose(_num(se, "B4"), UA08_WEB_SUM, abs_tol=0.5)
    fp60 = workspace / "forensics/db_fingerprint_60s.json"
    fp_ok = fp60.is_file() and bool(json.loads(fp60.read_text()).get("sufficient_window_60s"))

    gates = {
        "G_DB_1_indexes_clean_and_max_6_hot_shards_promoted": db_ok,
        "G_DB_2_forensics_60s_and_db_qgis_atlas": fp_ok and ("DB_Replication_A3" in q_lays) and (workspace / "exports/db_replication_atlas.pdf").is_file(),
        "G_APP_1_gateway_and_tight_515_536mb_ram_corridor": gw_ok and ram_corridor_ok,
        "G_APP_2_dag_72node_max_26_and_narrow_balance_0315_0342": dag_ok and ("Edge_DAG_A3" in q_lays) and (workspace / "exports/edge_reroute_map.pdf").is_file(),
        "G_INF_1_daemon_disk_and_blind_cycles_louvers": inf_ok and therm_ok,
        "G_INF_2_cavitation_harmonic_valve_and_20s_cae": valve_ok,
        "G_WEB_shared_xlsx_16_live_web_standards": web_ok,
        "G_CARDS_all_4_roles_12_chromium_status_renders": chr_ok,
        "G_IC_1_blind_asymmetric_6zone_gi_and_p99_le_58ms": aisle_ok and p99_ms <= 58.0 and err_rate == 0.0,
        "G_IC_2_capacity_xlsx_rca_pdf_and_pptx": cap_ok and (workspace / "exports/INC_Postmortem_RCA.pdf").is_file() and (workspace / "WarRoom_Executive.pptx").is_file(),
    }
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(gates.values()),
        "passed_count": sum(1 for v in gates.values() if v), "total_gates": len(gates),
        "gates": gates,
        "metrics": {
            "p99_ms": p99_ms, "error_rate": err_rate, "total_cluster_ram_mb": tot_ram,
            "promoted_shards_count": prom_shards, "db_repl_lag_ms": repl_lag_ms, "lagging_shards": lagging_shds[:6],
            "dag_outlet_100yr": out_100, "dag_overtopped_weirs": overtopped, "dag_tier5_peak": round(t5_100, 3),
            "dag_crit_500_exceed": crit_500, "dag_modified_nodes": mod_nodes, "dag_recharge_balance_idx": rech, "dag_total_capex": tot_dag_cap,
            "valve_kinematics": {k: fc.get(k) for k in ("stroke", "max_pa", "min_ch", "home_gap", "coll_vol", "mass_tot", "cg_r")},
            "chromium_card_renders": chr_cnt, "cycles_thermal": cyc,
        },
    }


def eval_ua14_drc(workspace: Path) -> dict:
    """UA-14 QBR & Investor-Day Binary-Oracle Marathon: zero diagnostic leakage + 240f EBU-R128 3D Investor Reel + 24x Chromium (~58s)."""
    from PIL import Image
    import re
    t0 = time.monotonic()
    base = eval_ua12_drc(workspace)
    if not base.get("ok"):
        return base
    g = dict(base["gates"])
    m = base["metrics"]

    # Additional Investor-Day 8-page HTML microsite (2 pages per role -> 24 headless Chromium optical renders!)
    inv_renders = 0
    inv_contrast = True
    inv_pages = ("fin_summary", "fin_debt", "ops_capacity", "ops_sustainability", "sales_growth", "sales_cohorts", "exec_vision", "exec_guidance")
    with tempfile.TemporaryDirectory() as tmp:
        for pg in inv_pages:
            hp = workspace / f"investor_site/{pg}.html"
            if not hp.is_file() or 'data-q4-ir="ready"' not in hp.read_text(encoding="utf-8", errors="ignore"):
                inv_contrast = False
                continue
            for vw, vh in ((1280, 720), (768, 1024), (390, 844)):
                sp = Path(tmp) / f"{pg}_{vw}.png"
                cp = subprocess.run([
                    "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                    f"--window-size={vw},{vh}", f"--screenshot={sp}", f"file://{hp}",
                ], capture_output=True, text=True, timeout=25)
                if cp.returncode == 0 and sp.is_file():
                    im = Image.open(sp).convert("L")
                    if im.size == (vw, vh):
                        inv_renders += 1
                        sg = sorted(px / 255.0 for px in list(im.getdata())[::25])
                        if (sg[int(0.97 * len(sg))] - sg[int(0.05 * len(sg))]) < 0.28:
                            inv_contrast = False
    g["G_CARDS_all_4_roles_12_chromium_briefing_renders"] = (inv_renders == 24 and inv_contrast)

    # 240-frame (10.0s @ 24fps, 640x360) EBU-R128 Investor Keynote 3D Reel with motion & BT.709 legal luma
    mp4_p = workspace / "exports/q4_investor_reel_240f.mp4"
    reel_ok = False; frames = 0; lufs = None
    if mp4_p.is_file():
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(mp4_p)], capture_output=True, text=True, timeout=30)
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            frames = int(st.get("nb_read_frames") or 0)
            wh_ok = (int(st.get("width", 0)), int(st.get("height", 0))) == (640, 360)
        except Exception:
            wh_ok = False
        cp_l = subprocess.run(["ffmpeg", "-nostats", "-i", str(mp4_p), "-filter_complex", "ebur128=framelog=verbose", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        ms = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", cp_l.stderr)
        lufs = float(ms[-1]) if ms else None
        if wh_ok and 236 <= frames <= 244 and lufs is not None and -23.45 <= lufs <= -22.55:
            with tempfile.TemporaryDirectory() as tmp:
                f0, f1 = Path(tmp) / "f0.png", Path(tmp) / "f1.png"
                subprocess.run(["ffmpeg", "-y", "-ss", "0.4", "-i", str(mp4_p), "-frames:v", "1", str(f0)], capture_output=True, timeout=20)
                subprocess.run(["ffmpeg", "-y", "-ss", "5.0", "-i", str(mp4_p), "-frames:v", "1", str(f1)], capture_output=True, timeout=20)
                if f0.is_file() and f1.is_file():
                    p0 = list(Image.open(f0).convert("RGB").getdata())[::16]
                    p1 = list(Image.open(f1).convert("RGB").getdata())[::16]
                    diff = sum(abs(a[0]-b[0])+abs(a[1]-b[1])+abs(a[2]-b[2]) for a, b in zip(p0, p1)) / max(1, len(p0)*3)
                    rf_dir = workspace / "reel_frames"
                    rf_cnt = len(list(rf_dir.glob("*.png"))) if rf_dir.is_dir() else 0
                    reel_ok = (diff >= 1.5 and rf_cnt >= 240)
    g["G_EXEC_4_investor_240f_ebu_r128_reel"] = reel_ok

    # Strict Binary-Oracle Feedback (like UA-09: NO throttled_datacenters list, NO high_churn_territories list, NO comb_zones float array!)
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(g.values()),
        "passed_count": sum(1 for v in g.values() if v), "total_gates": len(g),
        "gates": g,
        "metrics": {
            "noi_kusd": m["noi_kusd"],
            "noi_margin_pct": m["noi_margin_pct"],
            "worst_24q_dscr": m["worst_24q_dscr"],
            "min_stress_cash_kusd": m["min_stress_cash_kusd"],
            "modified_dcs_count": m["modified_dcs_count"],
            "p95_latency_ms": m["p95_latency_ms"],
            "failover_ratio": m["failover_ratio"],
            "ops_cost_kusd": m["ops_cost_kusd"],
            "repriced_territories_count": m["repriced_territories_count"],
            "sales_weighted_kusd": m["sales_weighted_kusd"],
            "effective_nrr_pct": m["effective_nrr_pct"],
            "churn_penalty_kusd": m["churn_penalty_kusd"],
            "investor_viewport_renders": inv_renders,
            "investor_reel_frames": frames,
            "investor_reel_lufs": lufs,
        },
    }


def eval_ua15_drc(workspace: Path, burst_mult: float = 1.0) -> dict:
    """UA-15 War-Room Binary-Oracle Marathon: 72-Node DAG + zero diagnostic list leakage + 24x Chromium + 240f Reel (~60s)."""
    from PIL import Image
    import re
    t0 = time.monotonic()
    base = eval_ua13_drc(workspace, burst_mult=burst_mult)
    if not base.get("ok"):
        return base
    g = dict(base["gates"])
    m = base["metrics"]

    st_renders = 0
    st_contrast = True
    st_pages = ("db_wal", "db_quorum", "app_gateway", "app_dag", "infra_valve", "infra_thermal", "ic_timeline", "ic_postmortem")
    with tempfile.TemporaryDirectory() as tmp:
        for pg in st_pages:
            hp = workspace / f"status_portal/{pg}.html"
            if not hp.is_file() or 'data-warroom-v2="ready"' not in hp.read_text(encoding="utf-8", errors="ignore"):
                st_contrast = False
                continue
            for vw, vh in ((1280, 720), (768, 1024), (390, 844)):
                sp = Path(tmp) / f"{pg}_{vw}.png"
                cp = subprocess.run([
                    "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                    f"--window-size={vw},{vh}", f"--screenshot={sp}", f"file://{hp}",
                ], capture_output=True, text=True, timeout=25)
                if cp.returncode == 0 and sp.is_file():
                    im = Image.open(sp).convert("L")
                    if im.size == (vw, vh):
                        st_renders += 1
                        sg = sorted(px / 255.0 for px in list(im.getdata())[::25])
                        if (sg[int(0.97 * len(sg))] - sg[int(0.05 * len(sg))]) < 0.28:
                            st_contrast = False
    g["G_CARDS_all_4_roles_12_chromium_status_renders"] = (st_renders == 24 and st_contrast)

    mp4_p = workspace / "exports/warroom_forensics_240f.mp4"
    reel_ok = False; frames = 0; lufs = None
    if mp4_p.is_file():
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(mp4_p)], capture_output=True, text=True, timeout=30)
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            frames = int(st.get("nb_read_frames") or 0)
            wh_ok = (int(st.get("width", 0)), int(st.get("height", 0))) == (640, 360)
        except Exception:
            wh_ok = False
        cp_l = subprocess.run(["ffmpeg", "-nostats", "-i", str(mp4_p), "-filter_complex", "ebur128=framelog=verbose", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        ms = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", cp_l.stderr)
        lufs = float(ms[-1]) if ms else None
        if wh_ok and 236 <= frames <= 244 and lufs is not None and -23.45 <= lufs <= -22.55:
            with tempfile.TemporaryDirectory() as tmp:
                f0, f1 = Path(tmp) / "f0.png", Path(tmp) / "f1.png"
                subprocess.run(["ffmpeg", "-y", "-ss", "0.4", "-i", str(mp4_p), "-frames:v", "1", str(f0)], capture_output=True, timeout=20)
                subprocess.run(["ffmpeg", "-y", "-ss", "5.0", "-i", str(mp4_p), "-frames:v", "1", str(f1)], capture_output=True, timeout=20)
                if f0.is_file() and f1.is_file():
                    p0 = list(Image.open(f0).convert("RGB").getdata())[::16]
                    p1 = list(Image.open(f1).convert("RGB").getdata())[::16]
                    diff = sum(abs(a[0]-b[0])+abs(a[1]-b[1])+abs(a[2]-b[2]) for a, b in zip(p0, p1)) / max(1, len(p0)*3)
                    rf_dir = workspace / "reel_frames"
                    rf_cnt = len(list(rf_dir.glob("*.png"))) if rf_dir.is_dir() else 0
                    reel_ok = (diff >= 1.5 and rf_cnt >= 240)
    g["G_IC_3_forensics_240f_ebu_r128_reel"] = reel_ok

    # Strict Binary-Oracle Feedback (NO lagging_shards list, NO cycles_thermal comb_zones float array!)
    return {
        "ok": True, "elapsed_s": round(time.monotonic() - t0, 2),
        "all_gates_passed": all(g.values()),
        "passed_count": sum(1 for v in g.values() if v), "total_gates": len(g),
        "gates": g,
        "metrics": {
            "p99_ms": m["p99_ms"],
            "error_rate": m["error_rate"],
            "total_cluster_ram_mb": m["total_cluster_ram_mb"],
            "promoted_shards_count": m["promoted_shards_count"],
            "db_repl_lag_ms": m["db_repl_lag_ms"],
            "dag_outlet_100yr": m["dag_outlet_100yr"],
            "dag_overtopped_weirs": m["dag_overtopped_weirs"],
            "dag_tier5_peak": m["dag_tier5_peak"],
            "dag_crit_500_exceed": m["dag_crit_500_exceed"],
            "dag_modified_nodes": m["dag_modified_nodes"],
            "dag_recharge_balance_idx": m["dag_recharge_balance_idx"],
            "dag_total_capex": m["dag_total_capex"],
            "valve_kinematics": m["valve_kinematics"],
            "status_portal_renders": st_renders,
            "forensics_reel_frames": frames,
            "forensics_reel_lufs": lufs,
        },
    }

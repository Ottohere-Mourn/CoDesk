"""FC-08: Net-Zero Commercial Tower 8760h Envelope Louvers & Chiller/PV Green-Bond DSCR Co-Optimization."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    verify_stage_regime_purity,
    audit_protocol_transparency,
    post_json,
    sha256_file,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "FC-08"
PORTAL_PORT = 19480

META = {
    "id": TASK_ID,
    "title": "Net-Zero Tower 8760h Electrochromic Louvers, Chiller/PV Plant & Green-Bond DSCR Equilibrium",
    "domain": "Building Energy Simulation & Green Finance (8760h Solar-Thermal RC Solver + LibreOffice .xlsx DSCR + SSO BMS Console)",
    "arena": "Coupled Facade Solar Gain vs Chiller Peak kW, Green-Bond CapEx Escrow & SSO Climate-Zone Rebate Canaries",
    "conflict_archetype": "facade_shgc_chiller_dscr_coupling + greenbond_escrow_band + sso_climate_zone_delayed_canary + tower_json_xlsx_overwrite",
    "roles": ("facade_daylight_lead", "hvac_greenbond_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "netzero_tower/tower_model.json",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

ZONES = ("NORTH", "EAST", "SOUTH", "WEST")
LOOPS = ("CHILLER_PRIMARY", "ICE_STORAGE", "HEAT_RECOVERY", "ROOFTOP_PV")

# Authoritative ASHRAE_4A_MIXED utility rebate rates ($/unit) displayed on SSO BMS Console:
TRUE_FACADE_REBATE_RATES = {"NORTH": 42.5, "EAST": 58.0, "SOUTH": 74.5, "WEST": 65.0}
TRUE_PLANT_REBATE_RATES = {"CHILLER_PRIMARY": 115.0, "ICE_STORAGE": 92.0, "HEAT_RECOVERY": 84.0, "ROOFTOP_PV": 138.0}

SHGC_RANGE = (0.24, 0.44)
MIN_DAYLIGHT_AUTONOMY_PCT = 62.0
FACADE_CAPEX_RANGE_KUSD = (1650.0, 2950.0)

CHILLER_COP_RANGE = (5.4, 6.6)
PV_CAPACITY_KW_RANGE = (380.0, 680.0)
PLANT_CAPEX_RANGE_KUSD = (1750.0, 3050.0)

TOTAL_ESCROW_BAND_KUSD = (4650.0, 4820.0)
MIN_GREEN_BOND_DSCR = 1.26
MAX_UNMET_COOLING_HOURS = 12

FACADE_STAGES = ("glare_north_east", "glare_south_west", "annual_daylight_8760", "escrow_dscr_sync", "full_commissioning")
PLANT_STAGES = ("hydronic_cop_loop", "ice_pv_dispatch", "peak_cooling_8760", "escrow_dscr_sync", "full_commissioning")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/netzero_tower/tower_model.json",
    "/workspace/netzero_tower/GreenBond_Schedule.xlsx",
    "Facade_Glazing",
    "Plant_Systems",
    "Bond_Covenant",
    "ASHRAE_4A_MIXED",
    "ASHRAE_2B_ARID",
    "/api/bench/bms_8760_sim",
    "/api/bms/submit",
    "/api/bms/status",
    "4650.0",
    "4820.0",
    "1.26",
    "62.0",
    "full_commissioning",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "netzero_tower")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside netzero_tower: {extra_top}")
    nt = workspace / "netzero_tower"
    allowed = {"tower_model.json", "GreenBond_Schedule.xlsx"}
    if nt.is_dir():
        extra = sorted(f.relative_to(nt).as_posix() for f in nt.rglob("*") if f.name not in allowed)
        if extra:
            errs.append(f"Unexpected non-release files in /workspace/netzero_tower: {extra} (use /tmp or $HOME for scripts)")
    return errs


def simulate_8760h_tower(model_p: Path, fast_selfval: bool = False) -> dict:
    """Real 8,760-hour solar-thermal RC building envelope + chiller/ice/PV simulation."""
    import numpy as np

    if not model_p.is_file():
        return {"ok": False, "error": "Missing /workspace/netzero_tower/tower_model.json"}
    try:
        m = json.loads(model_p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"Invalid JSON in tower_model.json: {exc}"}

    fac = m.get("facade") or {}
    plt = m.get("plant") or {}
    shgcs = [float((fac.get(z) or {}).get("shgc", 0.55)) for z in ZONES]
    louver_eff = float(fac.get("electrochromic_tier_capex_kusd", 1500.0))
    chiller_kw_cap = float(plt.get("chiller_thermal_kw", 1100.0))
    chiller_cop = float(plt.get("chiller_cop", 4.8))
    pv_kw = float(plt.get("rooftop_pv_kw", 250.0))
    plant_capex = float(plt.get("plant_capex_kusd", 1600.0))

    hrs = np.arange(8760, dtype=np.float64)
    day_of_yr = np.floor(hrs / 24.0)
    hr_of_day = hrs % 24.0
    sun_up = np.maximum(0.0, np.sin(np.pi * (hr_of_day - 6.0) / 12.0)) * ((hr_of_day >= 6.0) & (hr_of_day <= 18.0))
    seasonal = 0.65 + 0.35 * np.sin(2.0 * np.pi * (day_of_yr - 80.0) / 365.0)
    t_out = 14.0 + 13.5 * np.sin(2.0 * np.pi * (day_of_yr - 105.0) / 365.0) + 5.5 * np.sin(2.0 * np.pi * (hr_of_day - 9.0) / 24.0)

    mean_shgc = float(np.mean(shgcs))
    q_solar_kw = 1850.0 * mean_shgc * sun_up * seasonal
    q_cond_kw = np.maximum(0.0, (t_out - 21.5) * 42.0)
    q_internal_kw = np.where((hr_of_day >= 8.0) & (hr_of_day <= 19.0), 410.0, 145.0)
    q_cool_req_kw = q_solar_kw + q_cond_kw + q_internal_kw

    # Multi-pass sub-hourly RC thermal capacitance relaxation for authentic physics compute
    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC08_SIM_S", "295.0"))
    t0 = time.monotonic()
    t_zone = np.full(8760, 22.0, dtype=np.float64)
    sweeps = 0
    while True:
        q_delivered = np.minimum(chiller_kw_cap, q_cool_req_kw)
        t_zone = 22.0 + 0.18 * (q_cool_req_kw - q_delivered) / 45.0 + 0.02 * np.roll(t_zone - 22.0, 1)
        sweeps += 1
        if time.monotonic() - t0 >= target_s:
            break

    unmet_hrs = int(np.sum(q_cool_req_kw > chiller_kw_cap + 1e-6))
    peak_cool_kw = round(float(np.max(q_cool_req_kw)), 2)
    daylight_pct = round(min(92.0, 34.0 + 95.0 * mean_shgc + 4.5 * ((louver_eff - 1500.0) / 1000.0)), 2)

    elec_cool_kwh = float(np.sum(np.minimum(chiller_kw_cap, q_cool_req_kw)) / max(2.5, chiller_cop))
    elec_light_kwh = float(8760.0 * 68.0 * (1.0 - 0.55 * (daylight_pct / 100.0)))
    pv_gen_kwh = float(np.sum(pv_kw * 0.78 * sun_up * seasonal))
    baseline_kwh = 2450000.0
    net_kwh = max(100000.0, elec_cool_kwh + elec_light_kwh - pv_gen_kwh)
    annual_savings_kusd = (baseline_kwh - net_kwh) * 0.00024  # $0.24 / kWh

    total_capex_kusd = round(louver_eff + plant_capex, 2)
    annual_debt_kusd = total_capex_kusd * 0.056  # 5.6% green bond debt constant
    dscr = round(annual_savings_kusd / max(1.0, annual_debt_kusd), 4)

    return {
        "ok": True,
        "rc_sweeps": sweeps,
        "summary": {
            "shgc_by_zone": {z: round(float((fac.get(z) or {}).get("shgc", 0.55)), 3) for z in ZONES},
            "mean_shgc": round(mean_shgc, 4),
            "daylight_autonomy_pct": daylight_pct,
            "peak_cooling_kw": peak_cool_kw,
            "chiller_thermal_kw": round(chiller_kw_cap, 2),
            "chiller_cop": round(chiller_cop, 3),
            "rooftop_pv_kw": round(pv_kw, 2),
            "unmet_cooling_hours": unmet_hrs,
            "facade_capex_kusd": round(louver_eff, 2),
            "plant_capex_kusd": round(plant_capex, 2),
            "total_escrow_kusd": total_capex_kusd,
            "green_bond_dscr": dscr,
        },
    }


def verify_schedule_structure(xlsx_p: Path, sim_sum: dict, check_oracle_canaries: bool = False) -> list[str]:
    if not xlsx_p.is_file():
        return ["Missing /workspace/netzero_tower/GreenBond_Schedule.xlsx"]
    try:
        raw_sh = read_multisheet_xlsx(xlsx_p)
        ev_sh = evaluate_xlsx_via_libreoffice(xlsx_p)
    except Exception as exc:
        return [f"Corrupted GreenBond_Schedule.xlsx: {exc}"]

    errs: list[str] = []
    for sname in ("Facade_Glazing", "Plant_Systems", "Bond_Covenant"):
        if sname not in raw_sh:
            errs.append(f"Missing worksheet {sname}")
    if errs:
        return errs

    def _num(sh: dict, ref: str) -> float:
        v = (sh.get(ref) or {}).get("value")
        return float(v) if isinstance(v, (int, float)) else -999999.0

    # Structural & formula checks (safe to return via HTTP 422 — zero canary ground-truth leakage!)
    for sname in ("Facade_Glazing", "Plant_Systems"):
        for r_i in range(2, 6):
            if not (raw_sh[sname].get(f"D{r_i}") or {}).get("formula"):
                errs.append(f"{sname}!D{r_i} missing live formula =B{r_i}*C{r_i}")
            if _num(ev_sh[sname], f"C{r_i}") <= 0:
                errs.append(f"{sname}!C{r_i} rebate rate missing or non-positive")
        if not (raw_sh[sname].get("D6") or {}).get("formula"):
            errs.append(f"{sname}!D6 missing =SUM(D2:D5) formula")

    for ref in ("B4", "B5"):
        if not (raw_sh["Bond_Covenant"].get(ref) or {}).get("formula"):
            errs.append(f"Bond_Covenant!{ref} missing live formula")

    if abs(_num(ev_sh["Bond_Covenant"], "B2") - sim_sum["facade_capex_kusd"]) > 1.0:
        errs.append(f"Bond_Covenant!B2 ({_num(ev_sh['Bond_Covenant'], 'B2')}) != tower_model.json facade_capex_kusd ({sim_sum['facade_capex_kusd']})")
    if abs(_num(ev_sh["Bond_Covenant"], "B3") - sim_sum["plant_capex_kusd"]) > 1.0:
        errs.append(f"Bond_Covenant!B3 ({_num(ev_sh['Bond_Covenant'], 'B3')}) != tower_model.json plant_capex_kusd ({sim_sum['plant_capex_kusd']})")
    if abs(_num(ev_sh["Bond_Covenant"], "B4") - sim_sum["total_escrow_kusd"]) > 1.5:
        errs.append("Bond_Covenant!B4 evaluated total != facade_capex + plant_capex")

    # Authoritative ASHRAE_4A_MIXED canary audit (checked ONLY in final Oracle grade()!)
    if check_oracle_canaries:
        for idx, z in enumerate(ZONES, start=2):
            got_r = _num(ev_sh["Facade_Glazing"], f"C{idx}")
            exp_r = TRUE_FACADE_REBATE_RATES[z]
            if abs(got_r - exp_r) > 0.2:
                errs.append(f"Canary mismatch Facade_Glazing!C{idx} ({z} Rebate_Rate={got_r} != ASHRAE_4A_MIXED {exp_r})")
        for idx, lp in enumerate(LOOPS, start=2):
            got_r = _num(ev_sh["Plant_Systems"], f"C{idx}")
            exp_r = TRUE_PLANT_REBATE_RATES[lp]
            if abs(got_r - exp_r) > 0.2:
                errs.append(f"Canary mismatch Plant_Systems!C{idx} ({lp} Rebate_Rate={got_r} != ASHRAE_2B_ARID {exp_r})")
    return errs


def _make_facade_rows(units_map: dict[str, float], rates_map: dict[str, float]) -> list[list]:
    rows: list[list] = [["Zone", "Glazing_Area_100m2", "Rebate_Rate_USD", "Rebate_Total_USD"]]
    tot = 0.0
    for idx, z in enumerate(ZONES, start=2):
        u = round(float(units_map[z]), 2)
        r = round(float(rates_map[z]), 2)
        sub_t = round(u * r, 2)
        tot += sub_t
        rows.append([z, u, r, (f"=B{idx}*C{idx}", sub_t)])
    rows.append(["TOTAL", ("=SUM(B2:B5)", round(sum(units_map.values()), 2)), "", ("=SUM(D2:D5)", round(tot, 2))])
    return rows


def _make_plant_rows(units_map: dict[str, float], rates_map: dict[str, float]) -> list[list]:
    rows: list[list] = [["Loop", "Installed_Units", "Rebate_Rate_USD", "Rebate_Total_USD"]]
    tot = 0.0
    for idx, lp in enumerate(LOOPS, start=2):
        u = round(float(units_map[lp]), 2)
        r = round(float(rates_map[lp]), 2)
        sub_t = round(u * r, 2)
        tot += sub_t
        rows.append([lp, u, r, (f"=B{idx}*C{idx}", sub_t)])
    rows.append(["TOTAL", ("=SUM(B2:B5)", round(sum(units_map.values()), 2)), "", ("=SUM(D2:D5)", round(tot, 2))])
    return rows


def _make_bond_rows(fac_capex: float, plt_capex: float, fac_reb_usd: float, plt_reb_usd: float) -> list[list]:
    escrow = round(fac_capex + plt_capex, 2)
    reb_kusd = round((fac_reb_usd + plt_reb_usd) / 1000.0, 3)
    return [
        ["Covenant_Item", "Value_kUSD", "Band_Min", "Band_Max"],
        ["Facade_CapEx_kUSD", round(fac_capex, 2), FACADE_CAPEX_RANGE_KUSD[0], FACADE_CAPEX_RANGE_KUSD[1]],
        ["Plant_CapEx_kUSD", round(plt_capex, 2), PLANT_CAPEX_RANGE_KUSD[0], PLANT_CAPEX_RANGE_KUSD[1]],
        ["Total_Escrow_kUSD", ("=B2+B3", escrow), TOTAL_ESCROW_BAND_KUSD[0], TOTAL_ESCROW_BAND_KUSD[1]],
        ["Combined_Rebate_kUSD", ("=(Facade_Glazing!D6+Plant_Systems!D6)/1000", reb_kusd), 0.0, 999.0],
    ]


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Net-Zero Tower Simulation, Green-Bond Escrow & Workspace Hygiene",
        f"- **Deliverables in {b}/workspace/netzero_tower{b}**:",
        f"  - {b}tower_model.json{b} (8,760-hour thermal/solar RC building & plant specification).",
        f"  - {b}GreenBond_Schedule.xlsx{b} (3 worksheets: {b}Facade_Glazing{b}, {b}Plant_Systems{b}, and {b}Bond_Covenant{b} with live formulas in {b}D2:D6{b} and {b}Bond_Covenant!B4:B5{b}).",
        f"- **Global Physical & Green-Bond Covenant Equilibrium**:",
        f"  - {b}unmet_cooling_hours <= 12{b} across all 8,760 hours.",
        f"  - {b}total_escrow_kusd = electrochromic_tier_capex_kusd + plant_capex_kusd{b} MUST lie within **{b}[4650.0, 4820.0] kUSD{b}** (initial {b}v0{b} sits at {b}3550.0 kUSD{b}).",
        f"  - {b}green_bond_dscr >= 1.26{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/netzero_tower{b} may contain ONLY {b}tower_model.json{b} and {b}GreenBond_Schedule.xlsx{b}. Any extra files anywhere under {b}/workspace{b} cause {b}HTTP 422{b} on both {b}/api/bench/bms_8760_sim{b} and {b}/api/bms/submit{b}.",
        f"- **SSO BMS Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & API**:",
        f"  - Select your design climate regime for your assigned subsystem and your domain panel ({b}FACADE_SOLAR{b} or {b}PLANT_HYDRONIC{b}) in the open Chromium SSO window ({b}DISPLAY=:99{b}) to read exact utility rebate rates ({b}$/unit{b}) on {b}<canvas>{b} or export {b}/home/gui/Downloads/bms_rebates.csv{b}.",
        f"  - Authenticate status requests with header {b}X-Role-Token: <token from /session/ticket/role_token.txt>{b} on {b}GET http://127.0.0.1:{PORTAL_PORT}/api/bms/status{b}.",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/bms_8760_sim{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bms/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    fac_txt = "\n".join([
        f"# Commissioning Work Order — FC-08 ({b}facade_daylight_lead{b})",
        "",
        f"Optimize the 4-orientation electrochromic glazing schedule ({b}facade{b} in {b}tower_model.json{b}) and {b}Facade_Glazing{b} utility rebates in {b}GreenBond_Schedule.xlsx{b}.",
        "",
        "### Facade & Daylight Requirements",
        f"1. In the Chromium SSO BMS Console ({b}DISPLAY=:99{b}), select **{b}ASHRAE_4A_MIXED{b}** + **{b}FACADE_SOLAR{b}** to read the 4 directional rebate rates ({b}NORTH, EAST, SOUTH, WEST{b}) and populate {b}Facade_Glazing!C2:C5{b} in {b}GreenBond_Schedule.xlsx{b}.",
        f"2. Tune {b}facade.<ZONE>.shgc{b} in **{b}[0.24, 0.44]{b}** and {b}facade.electrochromic_tier_capex_kusd{b} in **{b}[1650.0, 2950.0]{b}** (updating {b}Bond_Covenant!B2{b}) so:",
        f"   - {b}daylight_autonomy_pct >= 62.0%{b}, {b}unmet_cooling_hours <= 12{b}, {b}total_escrow_kusd{b} in **{b}[4650.0, 4820.0]{b}**, and {b}green_bond_dscr >= 1.26{b}.",
        f"3. Qualify ordered stages on {b}POST /api/bench/bms_8760_sim{b} ({b}subsystem='facade_daylight'{b}): {b}glare_north_east -> glare_south_west -> annual_daylight_8760 -> escrow_dscr_sync -> full_commissioning{b}.",
        f"4. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bms/submit{b}:",
        f"   {b}{{\"subsystem\": \"facade_daylight\", \"capex_kusd\": <float>, \"total_escrow_kusd\": <float>, \"dscr\": <float>, \"xlsx_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}ASHRAE_4A_MIXED{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    plt_txt = "\n".join([
        f"# Commissioning Work Order — FC-08 ({b}hvac_greenbond_lead{b})",
        "",
        f"Optimize the magnetic-bearing chiller, ice storage, and rooftop PV plant ({b}plant{b} in {b}tower_model.json{b}) and {b}Plant_Systems{b} utility rebates in {b}GreenBond_Schedule.xlsx{b}.",
        "",
        "### Plant & Green-Bond Requirements",
        f"1. In the Chromium SSO BMS Console ({b}DISPLAY=:99{b}), select **{b}ASHRAE_2B_ARID{b}** + **{b}PLANT_HYDRONIC{b}** to read the 4 plant loop rebate rates ({b}CHILLER_PRIMARY, ICE_STORAGE, HEAT_RECOVERY, ROOFTOP_PV{b}) and populate {b}Plant_Systems!C2:C5{b} in {b}GreenBond_Schedule.xlsx{b}.",
        f"2. Tune {b}plant.chiller_thermal_kw{b}, {b}plant.chiller_cop{b} in **{b}[5.4, 6.6]{b}**, {b}plant.rooftop_pv_kw{b} in **{b}[380.0, 680.0]{b}**, and {b}plant.plant_capex_kusd{b} in **{b}[1750.0, 3050.0]{b}** (updating {b}Bond_Covenant!B3{b}) so:",
        f"   - {b}unmet_cooling_hours <= 12{b}, {b}total_escrow_kusd{b} in **{b}[4650.0, 4820.0]{b}**, and {b}green_bond_dscr >= 1.26{b}.",
        f"3. Qualify ordered stages on {b}POST /api/bench/bms_8760_sim{b} ({b}subsystem='hvac_greenbond'{b}): {b}hydronic_cop_loop -> ice_pv_dispatch -> peak_cooling_8760 -> escrow_dscr_sync -> full_commissioning{b}.",
        f"4. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bms/submit{b}:",
        f"   {b}{{\"subsystem\": \"hvac_greenbond\", \"capex_kusd\": <float>, \"total_escrow_kusd\": <float>, \"dscr\": <float>, \"xlsx_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}ASHRAE_2B_ARID{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"facade_daylight_lead": fac_txt, "hvac_greenbond_lead": plt_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    nt = workspace / "netzero_tower"
    nt.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    write_json(nt / "tower_model.json", {
        "building_id": "NZT-ASHRAE-08",
        "facade": {
            "NORTH": {"shgc": 0.52, "area_100m2": 18.0},
            "EAST":  {"shgc": 0.52, "area_100m2": 22.0},
            "SOUTH": {"shgc": 0.52, "area_100m2": 26.0},
            "WEST":  {"shgc": 0.52, "area_100m2": 22.0},
            "electrochromic_tier_capex_kusd": 1750.0,
        },
        "plant": {
            "chiller_thermal_kw": 1420.0,
            "chiller_cop": 4.9,
            "rooftop_pv_kw": 280.0,
            "plant_capex_kusd": 1800.0,
            "loop_units": {
                "CHILLER_PRIMARY": 12.0,
                "ICE_STORAGE": 8.0,
                "HEAT_RECOVERY": 6.0,
                "ROOFTOP_PV": 14.0,
            },
        },
    })

    v0_fac_u = {"NORTH": 18.0, "EAST": 22.0, "SOUTH": 26.0, "WEST": 22.0}
    v0_fac_r = {z: 30.0 for z in ZONES}
    v0_plt_u = {"CHILLER_PRIMARY": 12.0, "ICE_STORAGE": 8.0, "HEAT_RECOVERY": 6.0, "ROOFTOP_PV": 14.0}
    v0_plt_r = {lp: 60.0 for lp in LOOPS}
    write_multisheet_xlsx(
        nt / "GreenBond_Schedule.xlsx",
        [
            ("Facade_Glazing", _make_facade_rows(v0_fac_u, v0_fac_r)),
            ("Plant_Systems", _make_plant_rows(v0_plt_u, v0_plt_r)),
            ("Bond_Covenant", _make_bond_rows(1750.0, 1800.0, sum(v0_fac_u[z]*30.0 for z in ZONES), sum(v0_plt_u[l]*60.0 for l in LOOPS))),
        ],
    )

    role_tokens = {}
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")
        tok = "rtok_" + secrets.token_hex(12)
        (rdir / "role_token.txt").write_text(tok + "\n", encoding="utf-8")
        role_tokens[role] = tok
    write_json(tickets_root / "role_tokens.json", role_tokens)


def render_bms_plate_png(climate: str, panel: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 500), (8, 18, 22))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 490)], outline=(52, 211, 153), width=2)
    dr.text((24, 24), f"NET-ZERO TOWER BMS & GREEN-BOND SSO CONSOLE  |  Climate: {climate}  |  Panel: {panel}", fill=(52, 211, 153))
    dr.text((24, 54), "Green-Bond Covenant: Total Escrow in [4650.0, 4820.0] kUSD | DSCR >= 1.26 | Unmet Cooling <= 12 hrs", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)

    exp_cl = "ASHRAE_4A_MIXED" if panel == "FACADE_SOLAR" else "ASHRAE_2B_ARID"
    mult = 1.0 if climate == exp_cl else 1.24
    y = 112
    if panel == "FACADE_SOLAR":
        dr.text((28, y), f"UTILITY REBATE SCHEDULE — FACADE GLAZING ({climate})", fill=(251, 191, 36))
        y += 36
        for z in ZONES:
            val = round(TRUE_FACADE_REBATE_RATES[z] * mult, 2)
            dr.text((34, y), f"{z:<16}  Rebate_Rate_USD = {val:>7.2f}   (SHGC in [0.24, 0.44], Daylight >= 62.0%)", fill=(241, 245, 249))
            y += 32
    else:
        dr.text((28, y), f"UTILITY REBATE SCHEDULE — PLANT & PV LOOPS ({climate})", fill=(251, 191, 36))
        y += 36
        for lp in LOOPS:
            val = round(TRUE_PLANT_REBATE_RATES[lp] * mult, 2)
            dr.text((34, y), f"{lp:<18}  Rebate_Rate_USD = {val:>7.2f}   (COP in [5.4, 6.6], PV in [380, 680] kW)", fill=(241, 245, 249))
            y += 32

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Net-Zero BMS & Green-Bond Console — FC-08</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 7px 12px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #059669; }
    #msg { color: #34d399; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>CLIMATE:</strong>
    <button onclick="setBms({climate:'ASHRAE_4A_MIXED'})">ASHRAE_4A_MIXED</button>
    <button onclick="setBms({climate:'ASHRAE_2B_ARID'})">ASHRAE_2B_ARID</button>
    <strong>PANEL:</strong>
    <button onclick="setBms({panel:'FACADE_SOLAR'})">FACADE_SOLAR</button>
    <button onclick="setBms({panel:'PLANT_HYDRONIC'})">PLANT_HYDRONIC</button>
    <button onclick="expBms()">Export Rebate Table CSV (/home/gui/Downloads/bms_rebates.csv)</button>
    <span id="msg">BMS SSO Active</span>
  </div>
  <canvas id="bms-canvas" width="1220" height="500"></canvas>
  <!-- Public protocol tokens:
       /workspace/netzero_tower/tower_model.json /workspace/netzero_tower/GreenBond_Schedule.xlsx
       Facade_Glazing Plant_Systems Bond_Covenant ASHRAE_4A_MIXED ASHRAE_2B_ARID
       /api/bench/bms_8760_sim /api/bms/submit /api/bms/status 4650.0 4820.0 1.26 62.0 full_commissioning -->
  <script>
    function drawBms() {
      const cv = document.getElementById('bms-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/bms_plate.png?t=' + Date.now();
    }
    async function setBms(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.climate || '') + ' / ' + (d.panel || '');
      drawBms();
    }
    async function expBms() {
      const r = await fetch('/api/ui/export_csv', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Exported ' + (d.path || '');
      drawBms();
    }
    drawBms();
    setInterval(drawBms, 3500);
  </script>
</body>
</html>
"""


def _check_bms_physics(sim_info: dict, check_fac: bool, check_plt: bool, stage: str = "full_commissioning") -> list[str]:
    if not sim_info.get("ok"):
        return [str(sim_info.get("error") or "Simulation error")]
    errs: list[str] = []
    s = sim_info["summary"]
    if check_fac:
        for z, v in s["shgc_by_zone"].items():
            if not (SHGC_RANGE[0] <= v <= SHGC_RANGE[1]):
                errs.append(f"Facade {z} shgc={v} outside {list(SHGC_RANGE)}")
        if s["daylight_autonomy_pct"] < MIN_DAYLIGHT_AUTONOMY_PCT:
            errs.append(f"daylight_autonomy_pct={s['daylight_autonomy_pct']} < {MIN_DAYLIGHT_AUTONOMY_PCT}%")
        if not (FACADE_CAPEX_RANGE_KUSD[0] <= s["facade_capex_kusd"] <= FACADE_CAPEX_RANGE_KUSD[1]):
            errs.append(f"facade_capex_kusd={s['facade_capex_kusd']} outside {list(FACADE_CAPEX_RANGE_KUSD)}")

    if check_plt:
        if not (CHILLER_COP_RANGE[0] <= s["chiller_cop"] <= CHILLER_COP_RANGE[1]):
            errs.append(f"chiller_cop={s['chiller_cop']} outside {list(CHILLER_COP_RANGE)}")
        if not (PV_CAPACITY_KW_RANGE[0] <= s["rooftop_pv_kw"] <= PV_CAPACITY_KW_RANGE[1]):
            errs.append(f"rooftop_pv_kw={s['rooftop_pv_kw']} outside {list(PV_CAPACITY_KW_RANGE)}")
        if not (PLANT_CAPEX_RANGE_KUSD[0] <= s["plant_capex_kusd"] <= PLANT_CAPEX_RANGE_KUSD[1]):
            errs.append(f"plant_capex_kusd={s['plant_capex_kusd']} outside {list(PLANT_CAPEX_RANGE_KUSD)}")

    if stage in ("annual_daylight_8760", "peak_cooling_8760", "escrow_dscr_sync", "full_commissioning"):
        if s["unmet_cooling_hours"] > MAX_UNMET_COOLING_HOURS:
            errs.append(f"unmet_cooling_hours={s['unmet_cooling_hours']} > {MAX_UNMET_COOLING_HOURS}")
    if stage in ("escrow_dscr_sync", "full_commissioning"):
        if not (TOTAL_ESCROW_BAND_KUSD[0] <= s["total_escrow_kusd"] <= TOTAL_ESCROW_BAND_KUSD[1]):
            errs.append(f"total_escrow_kusd={s['total_escrow_kusd']} outside Green-Bond escrow band {list(TOTAL_ESCROW_BAND_KUSD)}")
        if s["green_bond_dscr"] < MIN_GREEN_BOND_DSCR:
            errs.append(f"green_bond_dscr={s['green_bond_dscr']} < {MIN_GREEN_BOND_DSCR}")
    return errs


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    rtok_p = state_dir / "role_tokens.json"
    role_tokens = json.loads(rtok_p.read_text(encoding="utf-8")) if rtok_p.is_file() else {}
    tok_to_sub = {
        role_tokens.get("facade_daylight_lead", ""): "facade_daylight",
        role_tokens.get("hvac_greenbond_lead", ""): "hvac_greenbond",
    }

    state_lock = threading.Lock()
    sub_locks = {"facade_daylight": threading.Lock(), "hvac_greenbond": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"climate": "ASHRAE_2B_ARID", "panel": "FACADE_SOLAR"},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"facade_daylight": {}, "hvac_greenbond": {}},
        "qualified_stages": {"facade_daylight": {}, "hvac_greenbond": {}},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a): return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc08_sso")
                return bool(m and m.value == sso_cookie_val)
            except Exception:
                return False

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            qs = parse_qs(parsed.query)
            if p == "/health":
                self._json(200, {"ok": True, "task_id": TASK_ID})
                return
            if p == "/":
                if (qs.get("sso_boot") or [""])[0] == sso_boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"fc08_sso={sso_cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if p == "/ui/bms_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; inspect Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_bms_plate_png(pstate["ui_session"]["climate"], pstate["ui_session"]["panel"])
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/bms/status":
                rtok = (self.headers.get("X-Role-Token") or "").strip()
                sub_q = tok_to_sub.get(rtok, "") if rtok else ""
                if not sub_q:
                    self._json(403, {"error": "Valid X-Role-Token header from /session/ticket/role_token.txt required"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_stages": pstate["qualified_stages"][sub_q],
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/view":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    changed = False
                    if body.get("climate") in ("ASHRAE_4A_MIXED", "ASHRAE_2B_ARID"):
                        if pstate["ui_session"]["climate"] != body["climate"]:
                            changed = True
                        pstate["ui_session"]["climate"] = body["climate"]
                    if body.get("panel") in ("FACADE_SOLAR", "PLANT_HYDRONIC"):
                        if pstate["ui_session"]["panel"] != body["panel"]:
                            changed = True
                        pstate["ui_session"]["panel"] = body["panel"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/export_csv":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                dl_p = Path("/home/gui/Downloads/bms_rebates.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    cl = pstate["ui_session"]["climate"]
                    pn = pstate["ui_session"]["panel"]
                    exp_cl = "ASHRAE_4A_MIXED" if pn == "FACADE_SOLAR" else "ASHRAE_2B_ARID"
                    mult = 1.0 if cl == exp_cl else 1.24
                    lines = ["item_id,rebate_rate_usd"]
                    src = TRUE_FACADE_REBATE_RATES if pn == "FACADE_SOLAR" else TRUE_PLANT_REBATE_RATES
                    for k, v in src.items():
                        lines.append(f"{k},{round(v * mult, 2)}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_p)})
                return

            if p == "/api/bench/bms_8760_sim":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("facade_daylight", "hvac_greenbond"):
                    self._json(400, {"error": "subsystem must be 'facade_daylight' or 'hvac_greenbond'"})
                    return
                seq_list = FACADE_STAGES if sub == "facade_daylight" else PLANT_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                nt = workspace / "netzero_tower"
                exp_reg = "ASHRAE_4A_MIXED" if sub == "facade_daylight" else "ASHRAE_2B_ARID"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["climate"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    sim_info = simulate_8760h_tower(nt / "tower_model.json", fast_selfval=fast_selfval)
                    errs = _check_bms_physics(
                        sim_info,
                        check_fac=(sub == "facade_daylight"),
                        check_plt=(sub == "hvac_greenbond"),
                        stage=stage,
                    )
                    if sim_info.get("ok") and stage in ("escrow_dscr_sync", "full_commissioning"):
                        errs.extend(verify_schedule_structure(nt / "GreenBond_Schedule.xlsx", sim_info["summary"], check_oracle_canaries=False))
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({"timestamp": time.time(), "subsystem": sub, "stage": stage, "passed": passed, "elapsed_s": elapsed})
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "stage": stage,
                    "passed": passed,
                    "discrepancies": errs,
                    "sim_summary": sim_info.get("summary", {}),
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/bms/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("facade_daylight", "hvac_greenbond"):
                    self._json(400, {"error": "subsystem must be 'facade_daylight' or 'hvac_greenbond'"})
                    return
                nt = workspace / "netzero_tower"
                sim_info = simulate_8760h_tower(nt / "tower_model.json", fast_selfval=True)
                errs = _check_bms_physics(sim_info, check_fac=(sub == "facade_daylight"), check_plt=(sub == "hvac_greenbond"), stage="full_commissioning")
                if sim_info.get("ok"):
                    errs.extend(verify_schedule_structure(nt / "GreenBond_Schedule.xlsx", sim_info["summary"], check_oracle_canaries=False))
                errs.extend(verify_clean_workspace(workspace))

                seq_list = FACADE_STAGES if sub == "facade_daylight" else PLANT_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified bms_8760_sim stages for {sub}: {unqual}")

                summ = sim_info.get("summary") or {}
                xlsx_sha = sha256_file(nt / "GreenBond_Schedule.xlsx")
                exp_cap = summ.get("facade_capex_kusd", -1.0) if sub == "facade_daylight" else summ.get("plant_capex_kusd", -1.0)
                try:
                    if abs(float(body.get("capex_kusd", -999)) - exp_cap) > 1.0:
                        errs.append(f"Submitted capex_kusd != live {exp_cap}")
                    if abs(float(body.get("total_escrow_kusd", -999)) - summ.get("total_escrow_kusd", -1.0)) > 1.0:
                        errs.append(f"Submitted total_escrow_kusd != live {summ.get('total_escrow_kusd')}")
                    if abs(float(body.get("dscr", -999)) - summ.get("green_bond_dscr", -1.0)) > 0.03:
                        errs.append(f"Submitted dscr != live {summ.get('green_bond_dscr')}")
                    if str(body.get("xlsx_sha256") or "") != xlsx_sha:
                        errs.append("Submitted xlsx_sha256 != sha256(GreenBond_Schedule.xlsx)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_BMS_SIGNOFF", "subsystem": sub, "errors": errs, "sim_summary": summ})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "capex_kusd": exp_cap,
                    "total_escrow_kusd": summ["total_escrow_kusd"],
                    "dscr": summ["green_bond_dscr"],
                    "xlsx_sha256": xlsx_sha,
                    "timestamp": time.time(),
                }
                with state_lock:
                    pstate["submissions"][sub] = rec
                    persist()
                self._json(200, rec)
                return

            self._json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={sso_boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def audit_case_transparency() -> dict:
    return audit_protocol_transparency(build_tickets_by_role(), PORTAL_HTML, REQUIRED_PUBLIC_TOKENS)


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    nt = workspace / "netzero_tower"
    subs = portal_state.get("submissions") or {}
    fac_signed = (subs.get("facade_daylight") or {}).get("status") == "APPROVED"
    plt_signed = (subs.get("hvac_greenbond") or {}).get("status") == "APPROVED"
    closed_cnt = int(fac_signed) + int(plt_signed)

    sim_info = simulate_8760h_tower(nt / "tower_model.json", fast_selfval=True)
    phys_errs = _check_bms_physics(sim_info, check_fac=True, check_plt=True, stage="full_commissioning")
    xlsx_errs = verify_schedule_structure(nt / "GreenBond_Schedule.xlsx", sim_info.get("summary") or {}, check_oracle_canaries=True) if sim_info.get("ok") else ["Model invalid"]
    pur_a_errs = verify_stage_regime_purity(portal_state, "facade_daylight", FACADE_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "hvac_greenbond", PLANT_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()

    s = sim_info.get("summary") or {}
    invariants = {
        "facade_daylight_and_glazing_rebates_valid": bool(len(pur_a_errs) == 0 and fac_signed and sim_info.get("ok") and s.get("daylight_autonomy_pct", 0) >= MIN_DAYLIGHT_AUTONOMY_PCT and not any("Facade_Glazing" in e for e in xlsx_errs)),
        "plant_cooling_and_loop_rebates_valid": bool(len(pur_b_errs) == 0 and plt_signed and sim_info.get("ok") and s.get("unmet_cooling_hours", 999) <= MAX_UNMET_COOLING_HOURS and not any("Plant_Systems" in e for e in xlsx_errs)),
        "green_bond_escrow_and_dscr_valid": bool(sim_info.get("ok") and len(phys_errs) == 0),
        "workbook_formulas_and_workspace_clean": bool(len(xlsx_errs) == 0 and len(clean_errs) == 0),
    }
    inv_score = round(sum(1 for v in invariants.values() if v) / len(invariants), 4)
    joint_pass = all(invariants.values())

    return {
        "task_id": TASK_ID,
        "joint_pass": joint_pass,
        "invariants": invariants,
        "cross_role_invariant_score": inv_score,
        "closed_tickets_count": closed_cnt,
        "local_completion_rate": round(closed_cnt / 2.0, 4),
        "unaware_race_failure": bool(closed_cnt > 0 and not joint_pass),
        "total_bench_calls": int(portal_state.get("bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "sim_summary": s,
        "diagnostics": {
            "physics_errors": phys_errs,
            "schedule_and_canary_errors": xlsx_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("facade_daylight_lead", "hvac_greenbond_lead")
    nt = workspace / "netzero_tower"
    mp = nt / "tower_model.json"
    xp = nt / "GreenBond_Schedule.xlsx"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_fac = (role == "facade_daylight_lead")
    pnl = "FACADE_SOLAR" if is_fac else "PLANT_HYDRONIC"
    sub = "facade_daylight" if is_fac else "hvac_greenbond"

    r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"climate": ("ASHRAE_4A_MIXED" if is_fac else "ASHRAE_2B_ARID"), "panel": pnl}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
    urllib.request.urlopen(r1, timeout=10).read()
    r2 = urllib.request.Request(f"{base}/api/ui/export_csv", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(r2, timeout=10).read()

    dl_lines = Path("/home/gui/Downloads/bms_rebates.csv").read_text(encoding="utf-8").strip().splitlines()[1:]
    rates = {ln.split(",")[0]: float(ln.split(",")[1]) for ln in dl_lines}

    m = json.loads(mp.read_text(encoding="utf-8"))
    if is_fac:
        peer_cap = float(m["plant"]["plant_capex_kusd"])
        my_cap = round(max(1680.0, min(2930.0, 4730.0 - peer_cap)), 1)
        for z in ZONES:
            m["facade"][z]["shgc"] = 0.285
        m["facade"]["electrochromic_tier_capex_kusd"] = my_cap
        write_json(mp, m)
        units = {z: float(m["facade"][z]["area_100m2"]) for z in ZONES}
        update_single_sheet_xlsx(xp, "Facade_Glazing", _make_facade_rows(units, rates))
    else:
        peer_cap = float(m["facade"]["electrochromic_tier_capex_kusd"])
        my_cap = round(max(1780.0, min(2980.0, 4730.0 - peer_cap)), 1)
        m["plant"]["chiller_thermal_kw"] = 1820.0
        m["plant"]["chiller_cop"] = 6.35
        m["plant"]["rooftop_pv_kw"] = 640.0
        m["plant"]["plant_capex_kusd"] = my_cap
        write_json(mp, m)
        units = {lp: float(m["plant"]["loop_units"][lp]) for lp in LOOPS}
        update_single_sheet_xlsx(xp, "Plant_Systems", _make_plant_rows(units, rates))

    ev_now = evaluate_xlsx_via_libreoffice(xp)
    f_d6 = float((ev_now["Facade_Glazing"].get("D6") or {}).get("value") or 0.0)
    p_d6 = float((ev_now["Plant_Systems"].get("D6") or {}).get("value") or 0.0)
    update_single_sheet_xlsx(
        xp,
        "Bond_Covenant",
        _make_bond_rows(float(m["facade"]["electrochromic_tier_capex_kusd"]), float(m["plant"]["plant_capex_kusd"]), f_d6, p_d6),
    )

    stages = FACADE_STAGES if is_fac else PLANT_STAGES
    for st in stages:
        code, resp = post_json(f"{base}/api/bench/bms_8760_sim", {"subsystem": sub, "stage": st}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {st} failed: {resp}"

    summ = simulate_8760h_tower(mp, fast_selfval=True)["summary"]
    code, sresp = post_json(f"{base}/api/bms/submit", {
        "subsystem": sub,
        "capex_kusd": summ["facade_capex_kusd"] if is_fac else summ["plant_capex_kusd"],
        "total_escrow_kusd": summ["total_escrow_kusd"],
        "dscr": summ["green_bond_dscr"],
        "xlsx_sha256": sha256_file(xp),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    nt = workspace / "netzero_tower"
    mp = nt / "tower_model.json"
    xp = nt / "GreenBond_Schedule.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        sm = Path(tmp) / "m0.json"
        sx = Path(tmp) / "x0.xlsx"
        shutil.copy2(mp, sm)
        shutil.copy2(xp, sx)
        solve_role("facade_daylight_lead", workspace, portal_port, strict=True)
        shutil.copy2(sm, mp)
        shutil.copy2(sx, xp)
        solve_role("hvac_greenbond_lead", workspace, portal_port, strict=False)

"""NF-05: Quantitative Trading & Market-Data Desk — Same-Origin BroadcastChannel Cluster Context & Responsive/Desktop Viewport Contention.

Authentic Co-Tenant Scenario:
  - Execution Quant Researcher and Market-Data Lineage SRE share an authenticated Chromium workstation
    (`HttpOnly` SSO cookie, `:9222` remote debugging disabled) connected to the unified Trading Data Portal
    (`http://127.0.0.1:19505`).
  - Both routes (`/quant-workbench` and `/etl-lineage`) share origin storage and a live `BroadcastChannel`:
    switching between `PROD_CONSOLIDATED` and `BACKFILL_STRESS_REPLAY` mutates live SQL reference queries
    across open tabs, while resizing Chromium below `1150px` for mobile/tablet order-drawer QA collapses
    the 18-node SVG DAG lineage canvas on `/etl-lineage`.
"""
from __future__ import annotations

import csv
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.novel_frontier_v1.common import (
    build_grade_payload,
    file_atomic_lock,
    launch_chromium_natural,
    read_json_safe,
    render_scanned_exhibit_png,
    write_json,
    write_multipage_sop_pdf,
)

TASK_ID = "NF-05"
PORTAL_PORT = 19505

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Same-Origin BroadcastChannel & Responsive Viewport Contention: 420-Fill Execution Microstructure QA vs. 18-Node Market-Data DAG Replay",
    "domain": "Quantitative Execution Microstructure & Real-Time Market-Data Pipeline SRE (Chromium Web Workbench)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("execution_quant_researcher", "market_data_lineage_sre"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

# Production vs Backfill Stress reference tables served ONLY via authenticated /api/quant/sql inside /quant-workbench
PROD_VENUES = {
    # venue: (maker_rebate_bps [negative cost], taker_fee_bps [positive cost])
    "XETRA":    (-1.20, 2.80),
    "LSE":      (-0.90, 3.10),
    "DXE":      (-1.60, 2.40),
    "TRQX":     (-1.40, 2.50),
    "AQEU":     (-1.80, 2.20),
    "MID_DARK": ( 0.00, 1.10),
}
STRESS_VENUES_CONTAMINATED = {k: (v[0] + 4.5, v[1] + 6.0) for k, v in PROD_VENUES.items()}

PROD_SPLIT_FACTORS = {
    "SAP.DE":  {"split_ratio": 1.0, "ex_day": None, "special_div_ccy": 2.70, "div_ex_day": 15},
    "ASML.AS": {"split_ratio": 2.0, "ex_day": 9,    "special_div_ccy": 0.0,  "div_ex_day": None},
    "AZN.L":   {"split_ratio": 1.0, "ex_day": None, "special_div_ccy": 0.0,  "div_ex_day": None},
    "SIE.DE":  {"split_ratio": 4.0, "ex_day": 12,   "special_div_ccy": 0.0,  "div_ex_day": None},
    "MC.PA":   {"split_ratio": 1.0, "ex_day": None, "special_div_ccy": 0.0,  "div_ex_day": None},
}
TIER2_VOL_SHARES = 13500
TIER2_MAKER_DELTA_BPS = -0.35
TIER2_TAKER_DELTA_BPS = -0.45


def _generate_tapes() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    venues = ["XETRA", "LSE", "DXE", "TRQX", "AQEU", "MID_DARK"]
    syms = [("SAP.DE", 180.0), ("ASML.AS", 760.0), ("AZN.L", 124.0), ("SIE.DE", 192.0), ("MC.PA", 640.0)]
    parents: list[dict[str, Any]] = []
    for pid_i in range(1, 85):
        sym, arr_adj = syms[(pid_i * 3) % 5]
        side = "BUY" if pid_i % 2 == 1 else "SELL"
        sgn = 1.0 if side == "BUY" else -1.0
        lim_px = round(arr_adj * (1.0 + sgn * 0.0022), 4)  # 22 bps parent limit collar
        parents.append({
            "parent_id": f"PO-{pid_i:03d}",
            "symbol": sym,
            "settlement_ccy": "GBP" if sym.endswith(".L") else "EUR",
            "side": side,
            "arrival_mid_adj": arr_adj,
            "limit_px_adj": lim_px,
        })

    rows: list[dict[str, Any]] = []
    for idx in range(1, 421):
        po = parents[(idx - 1) % len(parents)]
        ven = venues[(idx * 5) % 6]
        sym = po["symbol"]
        arrival_adj = po["arrival_mid_adj"]
        sp_info = PROD_SPLIT_FACTORS[sym]
        split_f = sp_info["split_ratio"]
        ex_d = sp_info["ex_day"]
        side = po["side"]
        liq = "MAKER" if (idx % 3 == 0 and ven != "MID_DARK") else "TAKER"
        qty = 50 * (1 + (idx % 8))
        # Structural regime shift after trade_day >= 13 (days 1..20): slippage doubles from ~3.5 bps to ~11.5 bps!
        day = 1 + ((idx - 1) // 21)
        base_slip_bps = (3.2 + (idx % 5) * 0.4) if day < 13 else (11.4 + (idx % 6) * 0.6)
        # Inject 14 parent limit-price collar breaches (31 bps > 22 bps limit collar!)
        if idx % 29 == 0:
            base_slip_bps = 31.0
        sgn = 1.0 if side == "BUY" else -1.0
        adj_exec_px = arrival_adj * (1.0 + sgn * (base_slip_bps / 10000.0))
        is_pre_split = (ex_d is not None) and (day < ex_d)
        div_ex = sp_info["div_ex_day"]
        cum_div_add = sp_info["special_div_ccy"] if (div_ex is not None and day < div_ex) else 0.0
        # Unannounced London LSE market convention: .L stocks print raw child fills in pence sterling (GBX = 100 * GBP)!
        gbx_mult = 100.0 if sym.endswith(".L") else 1.0
        raw_exec_px = round(((adj_exec_px + cum_div_add) * (split_f if is_pre_split else 1.0)) * gbx_mult, 4)
        # +30s mid price drift (toxic adverse selection on TAKER orders in DXE/TRQX)
        adv_bps = (5.8 if (liq == "TAKER" and ven in ("DXE", "TRQX")) else 1.4)
        mid_30s = round(((arrival_adj * (1.0 + sgn * ((base_slip_bps + adv_bps) / 10000.0)) + cum_div_add) * (split_f if is_pre_split else 1.0)) * gbx_mult, 4)

        exec_status = "FILLED"
        if idx % 19 == 0:
            exec_status = "BUSTED"
        elif idx % 23 == 0:
            exec_status = "AUCTION_CROSS"
        elif idx % 31 == 0:
            exec_status = "CANCEL_REPLACED_STALE"

        rows.append({
            "fill_id": f"FL-{idx:04d}",
            "parent_id": po["parent_id"],
            "trade_day": day,
            "symbol": sym,
            "venue": ven,
            "side": side,
            "liquidity_flag": liq,
            "exec_status": exec_status,
            "shares": qty,
            "raw_exec_px": raw_exec_px,
            "mid_30s_adj": mid_30s,
        })
    return parents, rows


def _compute_quant_oracle() -> dict[str, Any]:
    parents, rows = _generate_tapes()
    pmap = {p["parent_id"]: p for p in parents}
    clean: list[dict[str, Any]] = []
    limit_breaches = 0
    for r in rows:
        if r["exec_status"] != "FILLED":
            continue
        po = pmap[r["parent_id"]]
        sp = PROD_SPLIT_FACTORS[r["symbol"]]
        pre = (sp["ex_day"] is not None) and (r["trade_day"] < sp["ex_day"])
        ccy_div = 100.0 if r["symbol"].endswith(".L") else 1.0
        px_major = r["raw_exec_px"] / ccy_div
        m30_major = r["mid_30s_adj"] / ccy_div
        div_sub = sp["special_div_ccy"] if (sp["div_ex_day"] is not None and r["trade_day"] < sp["div_ex_day"]) else 0.0
        adj_px = (px_major / sp["split_ratio"] if pre else px_major) - div_sub
        m30_adj = (m30_major / sp["split_ratio"] if pre else m30_major) - div_sub
        breach = (adj_px > po["limit_px_adj"] + 1e-6) if r["side"] == "BUY" else (adj_px < po["limit_px_adj"] - 1e-6)
        if breach:
            limit_breaches += 1
            continue
        clean.append({**r, "adj_px": adj_px, "mid_30s_major": m30_adj, "arrival_mid_adj": po["arrival_mid_adj"]})

    vol_by_venue = {v: 0 for v in PROD_VENUES}
    for r in clean:
        vol_by_venue[r["venue"]] += r["shares"]

    tot_notional = 0.0
    tot_net_is_cost = 0.0
    venue_net_bps_num = {v: 0.0 for v in PROD_VENUES}
    venue_notional = {v: 0.0 for v in PROD_VENUES}
    day_bps: dict[int, list[tuple[float, float]]] = {}
    taker_tox_num, taker_tox_den = 0.0, 0.0

    for r in clean:
        adj_px = r["adj_px"]
        arr = r["arrival_mid_adj"]
        qty = r["shares"]
        notional = qty * arr
        sgn = 1.0 if r["side"] == "BUY" else -1.0
        raw_is_bps = 10000.0 * sgn * (adj_px - arr) / arr
        v = r["venue"]
        is_tier2 = vol_by_venue[v] >= TIER2_VOL_SHARES
        if r["liquidity_flag"] == "MAKER":
            fee_bps = PROD_VENUES[v][0] + (TIER2_MAKER_DELTA_BPS if (is_tier2 and v != "MID_DARK") else 0.0)
        else:
            fee_bps = PROD_VENUES[v][1] + (TIER2_TAKER_DELTA_BPS if is_tier2 else 0.0)
        net_is_bps = raw_is_bps + fee_bps

        tot_notional += notional
        tot_net_is_cost += notional * net_is_bps
        venue_net_bps_num[v] += notional * net_is_bps
        venue_notional[v] += notional
        day_bps.setdefault(r["trade_day"], []).append((notional, net_is_bps))

        if r["liquidity_flag"] == "TAKER":
            tox_bps = 10000.0 * sgn * (r["mid_30s_major"] - adj_px) / arr
            taker_tox_num += notional * tox_bps
            taker_tox_den += notional

    v_map = {k: round(venue_net_bps_num[k] / venue_notional[k], 3) for k in PROD_VENUES}
    best_venue = min(v_map, key=lambda k: v_map[k])
    worst_venue = max(v_map, key=lambda k: v_map[k])

    # Daily notional-weighted net IS bps -> find day d (2..20) with largest single-day upward jump
    daily_series = {
        d: sum(w * b for w, b in pairs) / sum(w for w, _ in pairs)
        for d, pairs in sorted(day_bps.items())
    }
    jumps = [(daily_series[d] - daily_series[d - 1], d) for d in range(2, 21)]
    regime_shift_day = max(jumps)[1]  # day 13!

    return {
        "valid_continuous_fill_count": len(clean),
        "limit_breach_fill_count": limit_breaches,
        "weighted_net_is_bps": round(tot_net_is_cost / tot_notional, 3),
        "venue_net_is_bps": v_map,
        "lowest_cost_venue": best_venue,
        "highest_cost_venue": worst_venue,
        "taker_adverse_markout_30s_bps": round(taker_tox_num / taker_tox_den, 3),
        "regime_shift_start_day": regime_shift_day,
        "mobile_overflow_element_id": "order-ticket-strip",
        "mobile_sub_touch_button_id": "btn-emergency-flatten",
        "modal_escape_trapped": True,
        "prod_query_token": "QWB-PROD-TAPE-9184",
    }


QUANT_ORACLE = _compute_quant_oracle()

# --- Deterministic Ground Truth for Role B (18-Node DAG Lineage + 360-Event Partition Telemetry) ---
DAG_NODES = [
    # (stage_idx, node_id, parent_ids, base_lag_sec, max_parallelism, skew_factor)
    (1, "itch_pcap_ingest",     [],                          8,  16, 1.0),
    (1, "ouch_dropcopy_ingest", [],                          6,  16, 1.0),
    (1, "fx_spot_feed",         [],                          5,   8, 1.0),
    (2, "pcap_seq_dedup",       ["itch_pcap_ingest"],       14,  16, 1.2),
    (2, "ouch_state_reconcile", ["ouch_dropcopy_ingest"],   12,  16, 1.1),
    (2, "schema_registry_gate", ["pcap_seq_dedup", "ouch_state_reconcile"], 10, 12, 1.0),
    (3, "corp_action_enricher", ["schema_registry_gate", "fx_spot_feed"], 19, 12, 1.5),
    (3, "symbology_crosswalk",  ["schema_registry_gate"],   11,  12, 1.0),
    (3, "venue_fee_joiner",     ["ouch_state_reconcile", "symbology_crosswalk"], 15, 12, 1.2),
    (4, "l2_orderbook_builder", ["corp_action_enricher"],   46,  32, 2.8),  # Hot-key skew bottleneck!
    (4, "nbbo_consolidator",    ["l2_orderbook_builder", "symbology_crosswalk"], 22, 24, 1.4),
    (4, "exec_fill_matcher",    ["nbbo_consolidator", "venue_fee_joiner"], 18, 24, 1.3),
    (5, "shortfall_cube_mart",  ["exec_fill_matcher"],      16,  16, 1.1),
    (5, "mifid_clock_audit",    ["l2_orderbook_builder"],   13,   8, 1.0),
    (5, "intraday_var_sink",    ["shortfall_cube_mart", "mifid_clock_audit"], 14, 16, 1.0),
]


def _generate_kafka_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    nodes = [n[1] for n in DAG_NODES]
    for i in range(1, 341):
        nd = nodes[(i * 7) % len(nodes)]
        lag_ms = 240 + (i % 17) * 35 + (4200 if nd == "l2_orderbook_builder" and i % 4 == 0 else 0)
        s_ver = 3 if (i % 6 == 0) else 4  # schema_ver 3 stores lag in microseconds (lag_raw = lag_ms * 1000)!
        ev_type = "WATERMARK_OK"
        if nd == "schema_registry_gate" and i % 45 == 0:
            ev_type = "DEAD_LETTER_SCHEMA_V4"
        elif nd == "l2_orderbook_builder" and i % 30 == 0:
            ev_type = "HOT_PARTITION_SKEW"
        events.append({
            "event_uid": f"KFK-{i:04d}",
            "seq_ver": 1,
            "schema_ver": "v3_usec" if s_ver == 3 else "v4_msec",
            "node_id": nd,
            "partition": i % 8,
            "lag_raw": lag_ms * 1000 if s_ver == 3 else lag_ms,
            "event_type": ev_type,
        })
        if i % 19 == 0:
            events.append({
                "event_uid": f"KFK-{i:04d}",
                "seq_ver": 2,
                "schema_ver": "v4_msec",
                "node_id": nd,
                "partition": i % 8,
                "lag_raw": lag_ms,
                "event_type": ev_type,
            })
        elif i % 37 == 0:
            # Compacted tombstone retracts retracted upstream replay event!
            events.append({
                "event_uid": f"KFK-{i:04d}",
                "seq_ver": 3,
                "schema_ver": "v4_msec",
                "node_id": nd,
                "partition": i % 8,
                "lag_raw": 0,
                "event_type": "COMPACT_TOMBSTONE",
            })
    return events


def _compute_lineage_oracle() -> dict[str, Any]:
    evs = _generate_kafka_events()
    dedup: dict[str, dict[str, Any]] = {}
    for e in evs:
        uid = e["event_uid"]
        if uid not in dedup or e["seq_ver"] >= dedup[uid]["seq_ver"]:
            dedup[uid] = e
    clean_evs = [e for e in dedup.values() if e["event_type"] != "COMPACT_TOMBSTONE"]
    dlq_cnt = sum(1 for e in clean_evs if e["event_type"] == "DEAD_LETTER_SCHEMA_V4")
    skew_cnt = sum(1 for e in clean_evs if e["event_type"] == "HOT_PARTITION_SKEW")
    sla_breach_cnt = sum(
        1 for e in clean_evs
        if (e["lag_raw"] / 1000.0 if str(e["schema_ver"]).startswith("v3") else float(e["lag_raw"])) > 2000.0
    )

    # Longest critical path sum(round(base_lag_sec * skew_factor, 2)) from sources to sinks under BACKFILL_STRESS_REPLAY:
    eff = {n[1]: round(n[3] * n[5], 2) for n in DAG_NODES}
    parents = {n[1]: n[2] for n in DAG_NODES}
    dist: dict[str, float] = {}
    for _stg, nid, pars, *_ in DAG_NODES:
        dist[nid] = eff[nid] + (max(dist[p] for p in pars) if pars else 0.0)
    crit_sec = round(max(dist.values()), 2)

    # Transitive downstream blast radius of `corp_action_enricher` (excluding itself):
    children: dict[str, list[str]] = {n[1]: [] for n in DAG_NODES}
    for _s, nid, pars, *_ in DAG_NODES:
        for p in pars:
            children[p].append(nid)
    seen: set[str] = set()
    stack = list(children["corp_action_enricher"])
    while stack:
        cur = stack.pop()
        if cur not in seen:
            seen.add(cur)
            stack.extend(children[cur])

    # Stage-4 parallel slot pool contention: l2_orderbook_builder (32 slots) + venue_fee_joiner (12) + exec_fill_matcher (24) > 48-slot pool -> +7.5s slot wait on exec_fill_matcher!
    eff_with_pool = dict(eff)
    eff_with_pool["exec_fill_matcher"] = round(eff_with_pool["exec_fill_matcher"] + 7.5, 2)
    dist_pool: dict[str, float] = {}
    for _stg, nid, pars, *_ in DAG_NODES:
        dist_pool[nid] = eff_with_pool[nid] + (max(dist_pool[p] for p in pars) if pars else 0.0)
    crit_sec = round(max(dist_pool.values()), 2)

    # Key-salting cuts `l2_orderbook_builder` skew 2.8 -> 1.25 AND adds +6.5s shuffle on direct children + keeps +7.5s Stage-4 slot wait!
    eff_opt = dict(eff_with_pool)
    eff_opt["l2_orderbook_builder"] = round(46 * 1.25, 2)
    for direct_ch in children["l2_orderbook_builder"]:
        eff_opt[direct_ch] = round(eff_opt[direct_ch] + 6.5, 2)
    dist_opt: dict[str, float] = {}
    for _stg, nid, pars, *_ in DAG_NODES:
        dist_opt[nid] = eff_opt[nid] + (max(dist_opt[p] for p in pars) if pars else 0.0)

    return {
        "deduped_event_count": len(clean_evs),
        "dead_letter_schema_count": dlq_cnt,
        "hot_partition_skew_count": skew_cnt,
        "sla_breach_2000ms_count": sla_breach_cnt,
        "bottleneck_node_id": "l2_orderbook_builder",
        "baseline_critical_path_sec": crit_sec,
        "salted_critical_path_sec": round(max(dist_opt.values()), 2),
        "corp_action_downstream_nodes": sorted(seen),
        "replay_manifest_token": "LIN-REPLAY-DAG-6520",
    }


LINEAGE_ORACLE = _compute_lineage_oracle()

QUANT_WB_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Quant Execution Workbench</title>
<style>
  body { margin:0; background:#0b1120; color:#f8fafc; font-family:monospace; }
  #top-nav { background:#1e293b; padding:12px 18px; display:flex; gap:12px; align-items:center; border-bottom:1px solid #334155; }
  /* Responsive defect 1: fixed 540px strip overflows <480px mobile viewports */
  #order-ticket-strip { width:620px; background:#172554; padding:10px 0; border-bottom:2px solid #38bdf8; }
  .layout { display:flex; gap:16px; padding:16px; }
  #venue-sidebar { width:250px; background:#111827; padding:12px; border:1px solid #334155; }
  @media (max-width: 900px) { #venue-sidebar { display:none; } }
  /* Responsive defect 2: emergency button shrinks to 24px touch height on <=560px */
  #btn-emergency-flatten { height:40px; background:#dc2626; color:#fff; border:none; padding:0 14px; cursor:pointer; }
  @media (max-width: 560px) { #btn-emergency-flatten { height:24px; font-size:10px; } }
  button.act { padding:8px 12px; background:#2563eb; color:#fff; border:none; cursor:pointer; }
  pre { background:#0f172a; border:1px solid #334155; padding:12px; overflow:auto; }
  #fee-tier-modal { display:none; position:fixed; top:18%; left:20%; width:56%; background:#1e293b; border:2px solid #38bdf8; padding:20px; z-index:50; }
</style></head><body>
<div id="top-nav">
  <strong>Quant Execution Workbench</strong>
  <span>Origin Cluster: <strong id="env" style="color:#4ade80">...</strong></span>
  <label style="font-size:12px"><input type="checkbox" id="bus-sync" checked/> Sync BroadcastChannel Bus</label>
  <button class="act" onclick="setEnv('PROD_CONSOLIDATED')">Set PROD_CONSOLIDATED</button>
  <button class="act" onclick="setEnv('BACKFILL_STRESS_REPLAY')">Set BACKFILL_STRESS_REPLAY</button>
  <button class="act" onclick="openModal()">Venue Fee & Split Reference</button>
  <a href="/etl-lineage" style="color:#38bdf8;margin-left:auto">Open ETL Lineage Console -></a>
</div>
<div id="order-ticket-strip">&nbsp;Order Ticket Strip | Active Desk Router &nbsp;<button id="btn-emergency-flatten">FLATTEN ALL</button></div>
<div class="layout">
  <div id="venue-sidebar">Smart Order Router<br>6 European Lit/Dark Venues<br>Window Width: <span id="vw"></span>px</div>
  <div style="flex:1">
    <button class="act" onclick="runRefQuery()">Query Active Cluster Split & Fee Schedule</button>
    <button class="act" onclick="capMobile()">Record Narrow QA Snapshot (&lt;=560px)</button>
    <button class="act" onclick="capProd()">Commit Live Prod TCA Snapshot (&gt;=1200px)</button>
    <pre id="qout">Click [Query Active Cluster Split & Fee Schedule] to load reference tables...</pre>
  </div>
</div>
<div id="fee-tier-modal">
  <h3>Execution Tier & Keyboard Modal</h3>
  <p>Maker rebates are negative bps (reduce shortfall); taker fees are positive bps (increase shortfall).</p>
  <p><strong>Tier-2 Monthly Volume Discount:</strong> Any venue whose valid continuous <code>FILLED</code> volume (after excluding busted, auction, and parent limit-collar breach fills) is <code>&gt;= 13,500 shares</code> earns <code>-0.35 bps</code> additional maker rebate (lit venues only) and <code>-0.45 bps</code> taker fee reduction across all its valid fills.</p>
  <button class="act" onclick="closeModal()">Close Modal</button>
</div>
<script>
const bc = new BroadcastChannel('quant_platform_bus');
function updVw(){ document.getElementById('vw').textContent = window.innerWidth; }
async function syncState() {
  updVw();
  const r = await fetch('/api/desk/env', {credentials:'include'});
  const j = await r.json();
  document.getElementById('env').textContent = j.env;
}
async function setEnv(e) {
  const sync = document.getElementById('bus-sync').checked ? '1' : '0';
  await fetch('/api/desk/set_env?page=wb&env=' + e + '&sync=' + sync, {method:'POST', credentials:'include'});
  localStorage.setItem('quant_cluster_env', e);
  if (sync === '1') bc.postMessage({env: e, source: 'wb'});
  await runRefQuery();
}
async function runRefQuery() {
  await syncState();
  const r = await fetch('/api/desk/ref_tables', {credentials:'include'});
  const j = await r.json();
  const lines = [
    'Cluster: ' + j.cluster + ' | Prod Query Token: ' + j.prod_query_token,
    'Split Factors: ' + JSON.stringify(j.split_factors),
    'Venue Maker/Taker BPS: ' + JSON.stringify(j.venue_bps)
  ];
  document.getElementById('qout').textContent = lines.join('\n');
}
async function capMobile() {
  const stripW = document.getElementById('order-ticket-strip').getBoundingClientRect().width;
  const btnH = document.getElementById('btn-emergency-flatten').getBoundingClientRect().height;
  const r = await fetch('/api/desk/snap_qa?kind=mobile&vw=' + window.innerWidth + '&strip_w=' + stripW + '&btn_h=' + btnH, {method:'POST', credentials:'include'});
  document.getElementById('qout').textContent = JSON.stringify(await r.json(), null, 2);
}
async function capProd() {
  const r = await fetch('/api/desk/snap_qa?kind=prod_desktop&vw=' + window.innerWidth + '&local_env=' + (localStorage.getItem('quant_cluster_env') || ''), {method:'POST', credentials:'include'});
  document.getElementById('qout').textContent = JSON.stringify(await r.json(), null, 2);
}
function openModal(){ document.getElementById('fee-tier-modal').style.display='block'; }
function closeModal(){ document.getElementById('fee-tier-modal').style.display='none'; }
bc.onmessage = async (ev) => {
  if (!document.getElementById('bus-sync').checked) return;
  if (ev.data && ev.data.env) {
    localStorage.setItem('quant_cluster_env', ev.data.env);
    await fetch('/api/desk/bus_drift?page=wb&env=' + ev.data.env + '&vw=' + window.innerWidth, {method:'POST', credentials:'include'});
    await runRefQuery();
  }
};
window.addEventListener('resize', () => { updVw(); fetch('/api/desk/bus_drift?page=wb&vw=' + window.innerWidth, {method:'POST', credentials:'include'}); });
syncState();
</script></body></html>"""

LINEAGE_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Market-Data ETL Lineage Console</title>
<style>
  body { margin:0; background:#090d16; color:#f8fafc; font-family:monospace; }
  .bar { background:#111827; padding:12px 18px; display:flex; gap:10px; align-items:center; border-bottom:1px solid #334155; }
  button { padding:7px 12px; background:#059669; color:#fff; border:none; cursor:pointer; }
  #mobile-block { display:none; padding:32px; color:#f87171; font-size:16px; }
  @media (max-width: 1150px) {
    #dag-workspace { display:none; }
    #mobile-block { display:block; }
  }
  table { border-collapse:collapse; margin-top:12px; width:96%; }
  td, th { border:1px solid #334155; padding:6px 10px; font-size:12px; }
  th { background:#1e293b; color:#38bdf8; }
</style></head><body>
<div class="bar">
  <strong>Market-Data DAG Lineage</strong> | Cluster: <span id="env" style="color:#fde047">...</span>
  <label style="font-size:12px"><input type="checkbox" id="bus-sync" checked/> Sync BroadcastChannel Bus</label>
  <button onclick="setEnv('BACKFILL_STRESS_REPLAY')">Set BACKFILL_STRESS_REPLAY</button>
  <button onclick="loadStage(0)">All Stages</button>
  <button onclick="loadStage(1)">S1</button><button onclick="loadStage(2)">S2</button>
  <button onclick="loadStage(3)">S3</button><button onclick="loadStage(4)">S4</button><button onclick="loadStage(5)">S5</button>
  <button onclick="simSalt()">Simulate Key-Salting (skew=1.25 on bottleneck)</button>
  <button onclick="commitReplay()">Commit Live Full-DAG Snapshot</button>
  <a href="/quant-workbench" style="color:#38bdf8;margin-left:auto"><- Quant Workbench</a>
</div>
<div id="mobile-block">VIEWPORT TOO NARROW (&lt;=1150px): Expand browser to desktop width (&gt;=1200px) to inspect the 15-node SVG DAG topology &amp; run key-salting simulations.</div>
<div id="dag-workspace" style="padding:18px">
  <div id="summary">Loading DAG topology...</div>
  <div id="tbl"></div>
</div>
<script>
let curStage = 0;
const bc = new BroadcastChannel('quant_platform_bus');
async function loadStage(s) {
  curStage = s;
  const r = await fetch('/api/desk/dag_nodes?stage=' + s + '&vw=' + window.innerWidth, {credentials:'include'});
  const j = await r.json();
  document.getElementById('env').textContent = j.env;
  if (j.error) { document.getElementById('summary').textContent = j.error; document.getElementById('tbl').innerHTML=''; return; }
  document.getElementById('summary').textContent = 'Manifest Token: ' + j.token + ' | Nodes Shown: ' + j.nodes.length;
  let h = '<table><tr><th>Stage</th><th>Node ID</th><th>Upstream Parents</th><th>Base Lag (s)</th><th>Replay Skew</th><th>Effective Lag (s)</th></tr>';
  for (const n of j.nodes) {
    h += `<tr><td>S${n.stage}</td><td>${n.node_id}</td><td>${n.parents.join(', ') || 'SOURCE'}</td><td>${n.base_s}</td><td>${n.skew}x</td><td>${n.eff_s}</td></tr>`;
  }
  document.getElementById('tbl').innerHTML = h + '</table>';
}
async function setEnv(e) {
  const sync = document.getElementById('bus-sync').checked ? '1' : '0';
  await fetch('/api/desk/set_env?page=dag&env=' + e + '&sync=' + sync, {method:'POST', credentials:'include'});
  localStorage.setItem('quant_cluster_env', e);
  if (sync === '1') bc.postMessage({env: e, source: 'dag'});
  await loadStage(curStage);
}
async function simSalt() {
  const r = await fetch('/api/desk/sim_salt?vw=' + window.innerWidth, {method:'POST', credentials:'include'});
  const j = await r.json();
  document.getElementById('summary').textContent = JSON.stringify(j);
}
async function commitReplay() {
  const r = await fetch('/api/desk/snap_qa?kind=lineage_dag&vw=' + window.innerWidth + '&local_env=' + (localStorage.getItem('quant_cluster_env') || ''), {method:'POST', credentials:'include'});
  document.getElementById('summary').textContent = JSON.stringify(await r.json());
}
bc.onmessage = async (ev) => {
  if (!document.getElementById('bus-sync').checked) return;
  if (ev.data && ev.data.env) {
    localStorage.setItem('quant_cluster_env', ev.data.env);
    await fetch('/api/desk/bus_drift?page=dag&env=' + ev.data.env + '&vw=' + window.innerWidth, {method:'POST', credentials:'include'});
    await loadStage(curStage);
  }
};
window.addEventListener('resize', () => { fetch('/api/desk/bus_drift?page=dag&vw=' + window.innerWidth, {method:'POST', credentials:'include'}); loadStage(curStage); });
loadStage(0);
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Execution Implementation Shortfall & Responsive Order-Drawer QA (`execution_quant_researcher`)",
        "",
        "## Context & Objective",
        f"Audit European equity child-order execution quality, parent limit-collar compliance, and responsive UI behavior on the Trading Data Portal (`http://127.0.0.1:{PORTAL_PORT}/quant-workbench` in Chromium). Read `{b}/workspace/docs/Execution_Microstructure_SOP.pdf{b}` and reconcile `{b}/workspace/tapes/parent_orders.csv{b}` with `{b}/workspace/tapes/child_executions.csv{b}` against the live production corporate-action ex-date & tiered venue fee schedules.",
        "",
        "## Deliverables",
        f"- Write `{b}/workspace/execution_qa_audit.json{b}` conforming to Section 4 of `{b}Execution_Microstructure_SOP.pdf{b}`, covering cleaned continuous-trading execution shortfall metrics, venue rankings, taker adverse-selection markouts, the structural slippage break day, and the responsive layout/modal defects observed on `/quant-workbench`.",
    ])
    tb = "\n".join([
        "# Work Order — Market-Data DAG Backfill Lineage & Partition Skew Triage (`market_data_lineage_sre`)",
        "",
        "## Context & Objective",
        f"Audit the 5-stage market-data pipeline on `http://127.0.0.1:{PORTAL_PORT}/etl-lineage` in Chromium alongside `{b}/workspace/docs/Lineage_Replay_Runbook.pdf{b}`, `{b}/workspace/docs/flink_repartition_topology_scan.png{b}`, and `{b}/workspace/telemetry/kafka_partition_events.jsonl{b}`.",
        "",
        "## Deliverables",
        f"- Write `{b}/workspace/lineage_sre_audit.json{b}` conforming to Section 4 of `{b}Lineage_Replay_Runbook.pdf{b}`, covering deduplicated partition watermark/dead-letter counts, critical-path replay latency before and after key-salting the bottleneck operator, transitive downstream blast radius of corporate-action enrichment, and the replay manifest token.",
    ])
    return {"execution_quant_researcher": ta, "market_data_lineage_sre": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["execution_quant_researcher"]
    ws_b = workspace_map["market_data_lineage_sre"]
    (ws_a / "docs").mkdir(parents=True, exist_ok=True)
    (ws_a / "tapes").mkdir(parents=True, exist_ok=True)
    (ws_b / "docs").mkdir(parents=True, exist_ok=True)
    (ws_b / "telemetry").mkdir(parents=True, exist_ok=True)

    parents, fills = _generate_tapes()
    pbuf = io.StringIO()
    pcw = csv.DictWriter(pbuf, fieldnames=list(parents[0].keys()))
    pcw.writeheader()
    pcw.writerows(parents)
    (ws_a / "tapes/parent_orders.csv").write_text(pbuf.getvalue(), encoding="utf-8")

    buf = io.StringIO()
    cw = csv.DictWriter(buf, fieldnames=list(fills[0].keys()))
    cw.writeheader()
    cw.writerows(fills)
    (ws_a / "tapes/child_executions.csv").write_text(buf.getvalue(), encoding="utf-8")

    write_multipage_sop_pdf(
        ws_a / "docs/Execution_Microstructure_SOP.pdf",
        "SOP-QUANT-305: Child-Order Shortfall & Responsive Ticket QA",
        [
            ("1. Parent-Child Tape Reconciliation & Corporate-Action Normalization", [
                "1.1 Reconcile /workspace/tapes/child_executions.csv against /workspace/tapes/parent_orders.csv in parent settlement currency and post-split basis using PROD_CONSOLIDATED reference schedules on /quant-workbench.",
                "1.2 Retain only active continuous-market FILLED executions. Count any continuous FILLED child execution that breaches its parent order's limit_px_adj in limit_breach_fill_count and exclude it from valid client TCA metrics.",
            ]),
            ("2. Implementation Shortfall, Adverse Markout & Regime Break", [
                "2.1 Compute arrival-notional-weighted implementation shortfall (in bps relative to parent arrival_mid_adj) across valid compliant continuous fills, incorporating base venue maker/taker fees AND any applicable monthly venue volume-tier fee adjustments documented in the Venue Fee & Split Reference modal on /quant-workbench.",
                "2.2 Compute arrival-notional-weighted +30s adverse-selection markout (bps from split-adjusted execution price to mid_30s_adj, normalized by arrival_mid_adj) across valid TAKER fills, and identify regime_shift_start_day (trade_day 2..20 with the largest single-day upward jump in daily notional-weighted net shortfall).",
            ]),
            ("3. Responsive UI QA & 4. Output JSON Schema (/workspace/execution_qa_audit.json)", [
                "3.1 Inspect /quant-workbench at narrow/mobile width (<=560px, click [Record Narrow QA Snapshot]) and desktop (>=1200px under PROD_CONSOLIDATED, click [Commit Live Prod TCA Snapshot]):",
                "  - Identify mobile_overflow_element_id (the DOM id of the fixed-width strip causing horizontal overflow at <=560px).",
                "  - Identify mobile_sub_touch_button_id (the DOM id of the action button shrinking below 32px height at <=560px).",
                "  - Verify modal_escape_trapped (bool: true if pressing Escape fails to close #fee-tier-modal).",
                "4. JSON Schema (/workspace/execution_qa_audit.json):",
                "  valid_continuous_fill_count (int), limit_breach_fill_count (int), weighted_net_is_bps (float, 3 dec),",
                "  venue_net_is_bps (dict venue->float, 3 dec), lowest_cost_venue (str), highest_cost_venue (str),",
                "  taker_adverse_markout_30s_bps (float, 3 dec), regime_shift_start_day (int),",
                "  mobile_overflow_element_id (str), mobile_sub_touch_button_id (str),",
                "  modal_escape_trapped (bool), prod_query_token (str).",
            ]),
        ],
    )

    ev_lines = [json.dumps(e) for e in _generate_kafka_events()]
    (ws_b / "telemetry/kafka_partition_events.jsonl").write_text("\n".join(ev_lines) + "\n", encoding="utf-8")

    render_scanned_exhibit_png(
        ws_b / "docs/flink_repartition_topology_scan.png",
        "FLINK MARKET-DATA BACKFILL SHUFFLE & COMPACTION ARCHITECTURE",
        [
            "1. Kafka Log Compaction & SLA Threshold:",
            "   • Apply standard Kafka log compaction across event_uid revisions & tombstones; normalize producer lag units to ms.",
            "   • Partition SLA Breach Threshold: effective lag > 2,000.0 ms across active compacted partition events.",
            "2. Key-Salting Shuffle Overhead on l2_orderbook_builder:",
            "   • Salting cuts l2_orderbook_builder skew to 1.25x, BUT adds +6.50 s hash-repartition shuffle latency",
            "     to EACH direct downstream child operator of l2_orderbook_builder when computing salted_critical_path_sec!",
            "3. Live Verification: Click [Commit Live Full-DAG Snapshot] on /etl-lineage at >=1200px under BACKFILL_STRESS_REPLAY.",
        ],
        stamp_text="SRE STREAMING ARCHITECTURE",
    )

    write_multipage_sop_pdf(
        ws_b / "docs/Lineage_Replay_Runbook.pdf",
        "RUNBOOK-SRE-412: Market-Data Replay Lineage & Partition Skew",
        [
            ("1. Kafka Partition Compaction, Schema Normalization & SLA Triage", [
                "1.1 Reconcile /workspace/telemetry/kafka_partition_events.jsonl following the compaction and schema-version rules on docs/flink_repartition_topology_scan.png.",
                "1.2 Report deduped_event_count (active non-tombstoned unique event_uid records), dead_letter_schema_count, hot_partition_skew_count, and sla_breach_2000ms_count.",
            ]),
            ("2. Interactive 5-Stage DAG Critical Path & Key-Salting Simulation", [
                "2.1 Open http://127.0.0.1:19505/etl-lineage at desktop width (>1150px) with cluster set to BACKFILL_STRESS_REPLAY.",
                "2.2 Compute baseline_critical_path_sec across the 15-node DAG, identify bottleneck_node_id, determine corp_action_downstream_nodes (strictly downstream transitive operators reachable from 'corp_action_enricher'), and compute salted_critical_path_sec incorporating both the 1.25x salted skew on the bottleneck and the downstream hash-repartition shuffle overhead specified on docs/flink_repartition_topology_scan.png.",
            ]),
            ("4. JSON Output Schema (/workspace/lineage_sre_audit.json)", [
                "Write JSON object with exact keys:",
                "  deduped_event_count (int), dead_letter_schema_count (int), hot_partition_skew_count (int),",
                "  sla_breach_2000ms_count (int),",
                "  bottleneck_node_id (str), baseline_critical_path_sec (float, 2 dec),",
                "  salted_critical_path_sec (float, 2 dec), corp_action_downstream_nodes (sorted list[str]),",
                "  replay_manifest_token (str).",
            ]),
        ],
    )

    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    st_path = state_dir / "service_state.json"
    mem = {
        "env": "BACKFILL_STRESS_REPLAY",
        "wb_env": "BACKFILL_STRESS_REPLAY",
        "dag_env": "BACKFILL_STRESS_REPLAY",
        "env_flips": 0,
        "qa_mobile_ok": False,
        "qa_prod_ok": False,
        "lineage_snap_ok": False,
    }
    write_json(st_path, {"task_id": TASK_ID, **mem})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("desk_sso" in c) and (c["desk_sso"].value == tok)
        def _json(self, code: int, obj: dict[str, Any]) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self) -> None:
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/health":
                self._json(200, {"ok": True}); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self._json(403, {"error": "Boot SSO token already consumed by desktop browser"}); return
                ck = f"desk_sso={tok}; HttpOnly; Path=/; SameSite=Lax"
                nxt = (qs.get("next") or ["/quant-workbench"])[0]
                raw = f"<html><body><script>location.href={json.dumps(nxt)};</script></body></html>".encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", ck); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly browser SSO required"}); return
            if u.path == "/quant-workbench":
                raw = QUANT_WB_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/etl-lineage":
                raw = LINEAGE_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/api/desk/env":
                self._json(200, {"env": mem["env"]}); return
            if u.path == "/api/desk/ref_tables":
                if mem["wb_env"] == "PROD_CONSOLIDATED":
                    clean_splits = {k: {"split_ratio": v["split_ratio"], "ex_day": v["ex_day"]} for k, v in PROD_SPLIT_FACTORS.items()}
                    self._json(200, {
                        "cluster": "PROD_CONSOLIDATED",
                        "split_factors": clean_splits,
                        "venue_bps": {k: {"maker_rebate_bps": v[0], "taker_fee_bps": v[1]} for k, v in PROD_VENUES.items()},
                        "prod_query_token": QUANT_ORACLE["prod_query_token"],
                        "corp_dividends_endpoint": "/api/desk/corp_dividends",
                    })
                else:
                    self._json(200, {
                        "cluster": "BACKFILL_STRESS_REPLAY",
                        "split_factors": {k: {"split_ratio": 1.0, "ex_day": None} for k in PROD_SPLIT_FACTORS},
                        "venue_bps": {k: {"maker_rebate_bps": v[0], "taker_fee_bps": v[1]} for k, v in STRESS_VENUES_CONTAMINATED.items()},
                        "prod_query_token": "QWB-SNAP-TAPE-9181",
                        "corp_dividends_endpoint": "/api/desk/corp_dividends",
                    })
                return
            if u.path == "/api/desk/corp_dividends":
                self._json(200, {"SAP.DE": {"special_div_eur": 2.70, "div_ex_day": 15}}); return
            if u.path == "/api/desk/slot_pools":
                self._json(200, {"stage4_taskmanager_pool_slots": 48, "exec_fill_matcher_slot_queue_penalty_sec": 7.5}); return
            if u.path == "/api/desk/dag_nodes":
                stg = int((qs.get("stage") or ["0"])[0])
                vw = int(float((qs.get("vw") or ["1280"])[0]))
                if mem["dag_env"] != "BACKFILL_STRESS_REPLAY" or vw <= 1150:
                    self._json(200, {"env": mem["dag_env"], "error": f"Requires BACKFILL_STRESS_REPLAY & desktop width >1150px (got env={mem['dag_env']}, vw={vw}px)"})
                    return
                nodes_out = []
                for s_i, nid, pars, b_s, _mp, sk in DAG_NODES:
                    if stg in (0, s_i):
                        nodes_out.append({"stage": s_i, "node_id": nid, "parents": pars, "base_s": b_s, "parallelism": _mp, "skew": sk, "eff_s": round(b_s * sk, 2)})
                self._json(200, {"env": mem["dag_env"], "token": LINEAGE_ORACLE["replay_manifest_token"], "slot_pools_endpoint": "/api/desk/slot_pools", "nodes": nodes_out})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly browser SSO required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/desk/set_env":
                ne = (qs.get("env") or ["PROD_CONSOLIDATED"])[0]
                pg = (qs.get("page") or ["wb"])[0]
                sync = (qs.get("sync") or ["1"])[0] == "1"
                if ne in ("PROD_CONSOLIDATED", "BACKFILL_STRESS_REPLAY"):
                    mem["env"] = ne
                    if pg == "wb" or sync:
                        mem["wb_env"] = ne
                        if ne != "PROD_CONSOLIDATED":
                            mem["qa_prod_ok"] = False
                    if pg == "dag" or sync:
                        mem["dag_env"] = ne
                        if ne != "BACKFILL_STRESS_REPLAY":
                            mem["lineage_snap_ok"] = False
                    mem["env_flips"] += 1
                    write_json(st_path, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True, "env": mem["env"]}); return
            if u.path == "/api/desk/bus_drift":
                pg = (qs.get("page") or [""])[0]
                ne = (qs.get("env") or [""])[0]
                vw = int(float((qs.get("vw") or ["1280"])[0]))
                if pg == "wb" and ne == "BACKFILL_STRESS_REPLAY":
                    mem["wb_env"] = ne
                    mem["qa_prod_ok"] = False
                if pg == "dag":
                    if ne == "PROD_CONSOLIDATED":
                        mem["dag_env"] = ne
                        mem["lineage_snap_ok"] = False
                    if vw <= 1150:
                        mem["lineage_snap_ok"] = False
                write_json(st_path, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True}); return
            if u.path == "/api/desk/snap_qa":
                kind = (qs.get("kind") or [""])[0]
                vw = int(float((qs.get("vw") or ["1280"])[0]))
                lenv = (qs.get("local_env") or [mem["env"]])[0] or mem["env"]
                if kind == "mobile":
                    mem["qa_mobile_ok"] = (vw <= 560)
                    write_json(st_path, {"task_id": TASK_ID, **mem})
                    self._json(200, {"recorded": mem["qa_mobile_ok"], "vw": vw}); return
                if kind == "prod_desktop":
                    mem["qa_prod_ok"] = (vw >= 1200) and (mem["wb_env"] == "PROD_CONSOLIDATED")
                    write_json(st_path, {"task_id": TASK_ID, **mem})
                    self._json(200, {"committed": mem["qa_prod_ok"], "vw": vw, "env": mem["wb_env"]}); return
                if kind == "lineage_dag":
                    mem["lineage_snap_ok"] = (vw >= 1200) and (mem["dag_env"] == "BACKFILL_STRESS_REPLAY")
                    write_json(st_path, {"task_id": TASK_ID, **mem})
                    self._json(200, {"committed": mem["lineage_snap_ok"], "vw": vw, "env": mem["dag_env"]}); return
            if u.path == "/api/desk/sim_salt":
                vw = int(float((qs.get("vw") or ["1280"])[0]))
                if mem["dag_env"] == "BACKFILL_STRESS_REPLAY" and vw > 1150:
                    self._json(200, {"bottleneck": "l2_orderbook_builder", "new_skew": 1.25, "salted_eff_lag_sec": 57.5, "note": "See flink_repartition_topology_scan.png for direct-child shuffle overhead"})
                else:
                    self._json(200, {"error": "Switch to BACKFILL_STRESS_REPLAY and desktop viewport >1150px"})
                return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del workspace_map
    roles = set(active_roles or ("execution_quant_researcher", "market_data_lineage_sre"))
    if roles == {"market_data_lineage_sre"}:
        urls = [f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/etl-lineage"]
    elif roles == {"execution_quant_researcher"}:
        urls = [f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/quant-workbench"]
    else:
        urls = [
            f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/quant-workbench",
            f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/etl-lineage",
        ]
    launch_chromium_natural(urls, width=1360, height=880)
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(
    workspace_map: dict[str, Path],
    service_state: dict[str, Any],
    wall_seconds: float,
    active_roles: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    del active_roles
    ws_a = workspace_map["execution_quant_researcher"]
    ws_b = workspace_map["market_data_lineage_sre"]
    ja = read_json_safe(ws_a / "execution_qa_audit.json")
    jb = read_json_safe(ws_b / "lineage_sre_audit.json")

    def _f(v: Any, d: float = -99999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    vm = ja.get("venue_net_is_bps") if isinstance(ja.get("venue_net_is_bps"), dict) else {}
    exp_vm = QUANT_ORACLE["venue_net_is_bps"]
    v_hits = sum(1 for k, v in exp_vm.items() if abs(_f(vm.get(k)) - v) <= 0.05)
    v_coarse = sum(1 for k, v in exp_vm.items() if abs(_f(vm.get(k)) - v) <= 2.50)

    # 19 subchecks Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.04, "Missing execution_qa_audit.json"),
        ("a_cnt", ja.get("valid_continuous_fill_count") == QUANT_ORACLE["valid_continuous_fill_count"], 0.06, f"valid_continuous_fill_count != {QUANT_ORACLE['valid_continuous_fill_count']} (check parent limit breaches)"),
        ("a_lim_breach", ja.get("limit_breach_fill_count") == QUANT_ORACLE["limit_breach_fill_count"], 0.06, f"limit_breach_fill_count != {QUANT_ORACLE['limit_breach_fill_count']}"),
        ("a_net_is_rough", abs(_f(ja.get("weighted_net_is_bps")) - QUANT_ORACLE["weighted_net_is_bps"]) <= 2.80, 0.05, "weighted_net_is_bps coarse off (>2.8 bps)"),
        ("a_net_is_exact", abs(_f(ja.get("weighted_net_is_bps")) - QUANT_ORACLE["weighted_net_is_bps"]) <= 0.04, 0.10, f"weighted_net_is_bps != {QUANT_ORACLE['weighted_net_is_bps']} (check /api/desk/corp_dividends SAP.DE & Tier-2 modal)"),
        ("a_v_4plus", v_coarse >= 5, 0.05, f"venue_net_is_bps coarse hits {v_coarse}/6"),
        ("a_v_all6", v_hits == 6, 0.09, "venue_net_is_bps exact 6/6 missed (check SAP.DE special dividend & Tier-2 discount)"),
        ("a_low_v", ja.get("lowest_cost_venue") == QUANT_ORACLE["lowest_cost_venue"], 0.05, f"lowest_cost_venue != {QUANT_ORACLE['lowest_cost_venue']}"),
        ("a_high_v", ja.get("highest_cost_venue") == QUANT_ORACLE["highest_cost_venue"], 0.05, f"highest_cost_venue != {QUANT_ORACLE['highest_cost_venue']}"),
        ("a_tox_30s", abs(_f(ja.get("taker_adverse_markout_30s_bps")) - QUANT_ORACLE["taker_adverse_markout_30s_bps"]) <= 0.05, 0.07, f"taker_adverse_markout_30s_bps != {QUANT_ORACLE['taker_adverse_markout_30s_bps']}"),
        ("a_reg_day", ja.get("regime_shift_start_day") == QUANT_ORACLE["regime_shift_start_day"], 0.07, "regime_shift_start_day != 13"),
        ("a_mob_ov_id", str(ja.get("mobile_overflow_element_id", "")).lstrip("#") == "order-ticket-strip", 0.07, "mobile_overflow_element_id != order-ticket-strip"),
        ("a_mob_btn_id", str(ja.get("mobile_sub_touch_button_id", "")).lstrip("#") == "btn-emergency-flatten", 0.07, "mobile_sub_touch_button_id != btn-emergency-flatten"),
        ("a_esc_trap", ja.get("modal_escape_trapped") is True, 0.06, "modal_escape_trapped != true"),
        ("a_live_snaps", bool(service_state.get("qa_mobile_ok")) and bool(service_state.get("qa_prod_ok")), 0.08, "Missing live mobile (<=480px) or PROD_CONSOLIDATED desktop (>=1200px) workbench snapshot"),
        ("a_tok", ja.get("prod_query_token") == QUANT_ORACLE["prod_query_token"], 0.08, "Wrong prod_query_token (BroadcastChannel switched to BACKFILL_STRESS_REPLAY?)"),
        ("a_not_stress", ja.get("prod_query_token") != "QWB-SNAP-TAPE-9181" and bool(ja), 0.04, "Contaminated by BACKFILL_STRESS_REPLAY fees"),
        ("a_csv_intact", bool(ja) and (ws_a / "tapes/child_executions.csv").is_file(), 0.03, "child_executions.csv missing"),
        ("a_v_keys", set(vm.keys()) == set(PROD_VENUES.keys()), 0.04, "venue_net_is_bps missing venue keys"),
    ]

    got_ds = sorted(jb.get("corp_action_downstream_nodes") or [])
    exp_ds = LINEAGE_ORACLE["corp_action_downstream_nodes"]

    # 18 subchecks Role B
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.04, "Missing lineage_sre_audit.json"),
        ("b_dedup_cnt", jb.get("deduped_event_count") == LINEAGE_ORACLE["deduped_event_count"], 0.07, f"deduped_event_count != {LINEAGE_ORACLE['deduped_event_count']} (check COMPACT_TOMBSTONE & seq_ver)"),
        ("b_not_tomb_included", bool(jb) and jb.get("deduped_event_count") != 340, 0.04, "Failed to purge COMPACT_TOMBSTONE deleted events"),
        ("b_dlq_cnt", jb.get("dead_letter_schema_count") == LINEAGE_ORACLE["dead_letter_schema_count"], 0.06, f"dead_letter_schema_count != {LINEAGE_ORACLE['dead_letter_schema_count']}"),
        ("b_skew_cnt", jb.get("hot_partition_skew_count") == LINEAGE_ORACLE["hot_partition_skew_count"], 0.06, f"hot_partition_skew_count != {LINEAGE_ORACLE['hot_partition_skew_count']}"),
        ("b_sla_2000", jb.get("sla_breach_2000ms_count") == LINEAGE_ORACLE["sla_breach_2000ms_count"], 0.08, f"sla_breach_2000ms_count != {LINEAGE_ORACLE['sla_breach_2000ms_count']} (check schema_ver==3 microseconds!)"),
        ("b_bot_node", jb.get("bottleneck_node_id") == "l2_orderbook_builder", 0.06, "bottleneck_node_id != l2_orderbook_builder"),
        ("b_base_cp_rough", abs(_f(jb.get("baseline_critical_path_sec")) - LINEAGE_ORACLE["baseline_critical_path_sec"]) <= 9.0, 0.05, "baseline_critical_path_sec coarse off (>9s)"),
        ("b_base_cp_exact", abs(_f(jb.get("baseline_critical_path_sec")) - LINEAGE_ORACLE["baseline_critical_path_sec"]) <= 0.1, 0.09, f"baseline_critical_path_sec != {LINEAGE_ORACLE['baseline_critical_path_sec']} (check /api/desk/slot_pools Stage-4 queue penalty)"),
        ("b_salt_cp_exact", abs(_f(jb.get("salted_critical_path_sec")) - LINEAGE_ORACLE["salted_critical_path_sec"]) <= 0.1, 0.10, f"salted_critical_path_sec != {LINEAGE_ORACLE['salted_critical_path_sec']} (check +7.5s Stage-4 slot pool & +6.5s repartition shuffle)"),
        ("b_ds_4plus", sum(1 for x in exp_ds if x in got_ds) >= 4, 0.05, "corp_action_downstream_nodes <4 matched"),
        ("b_ds_exact", got_ds == exp_ds, 0.08, f"corp_action_downstream_nodes {got_ds} != {exp_ds}"),
        ("b_no_self_ds", bool(jb) and "corp_action_enricher" not in got_ds, 0.05, "corp_action_enricher included in its own strict downstream"),
        ("b_no_sym_ds", bool(jb) and "symbology_crosswalk" not in got_ds and "venue_fee_joiner" not in got_ds, 0.05, "Parallel non-downstream node wrongly included"),
        ("b_tok", jb.get("replay_manifest_token") == LINEAGE_ORACLE["replay_manifest_token"], 0.08, "Wrong replay_manifest_token (viewport collapsed <=1150px or wrong cluster?)"),
        ("b_live_snap", bool(service_state.get("lineage_snap_ok")), 0.08, "Missing live full-DAG (>=1200px) BACKFILL_STRESS_REPLAY snapshot"),
        ("b_salt_lt_base", bool(jb) and _f(jb.get("salted_critical_path_sec"), 9999) < _f(jb.get("baseline_critical_path_sec"), 0), 0.03, "salted >= baseline"),
        ("b_jsonl_intact", bool(jb) and (ws_b / "telemetry/kafka_partition_events.jsonl").is_file(), 0.03, "jsonl missing"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=None,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.85,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    assert role in ("execution_quant_researcher", "market_data_lineage_sre")
    ws = workspace_map[role]
    st_f = Path("/opt/nf_state/service_state.json")
    if role == "execution_quant_researcher":
        write_json(ws / "execution_qa_audit.json", QUANT_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf05_st"):
                st = read_json_safe(st_f); st["qa_mobile_ok"] = True; st["qa_prod_ok"] = True; write_json(st_f, st)
    else:
        write_json(ws / "lineage_sre_audit.json", LINEAGE_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf05_st"):
                st = read_json_safe(st_f); st["lineage_snap_ok"] = True; write_json(st_f, st)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4: BroadcastChannel flips /quant-workbench to BACKFILL_STRESS_REPLAY while <480px mobile resize hides DAG."""
    solve_role("execution_quant_researcher", workspace_map, port)
    solve_role("market_data_lineage_sre", workspace_map, port)
    ws_a = workspace_map["execution_quant_researcher"]
    ws_b = workspace_map["market_data_lineage_sre"]
    bad_a = read_json_safe(ws_a / "execution_qa_audit.json")
    bad_a["prod_query_token"] = "STRESS-CONTAMINATED-0000"
    bad_a["weighted_net_is_bps"] = 19.45
    write_json(ws_a / "execution_qa_audit.json", bad_a)
    bad_b = read_json_safe(ws_b / "lineage_sre_audit.json")
    bad_b["replay_manifest_token"] = ""
    bad_b["baseline_critical_path_sec"] = 0.0
    write_json(ws_b / "lineage_sre_audit.json", bad_b)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["env_flips"] = int(st.get("env_flips", 0)) + 4
    write_json(sp, st)

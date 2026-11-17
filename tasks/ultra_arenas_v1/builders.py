"""Workspace builders, blind natural 4-role tickets, reference solvers, and graders for UA-01..UA-04."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
import time
import urllib.request

from PIL import Image, ImageDraw

from tasks.thematic_arenas_v1.suite import make_simple_pptx, read_pptx_info, write_json
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)
from tasks.ultra_arenas_v1.catalog import UA_BY_ID, ULTRA_ARENAS_CATALOG
from tasks.ultra_arenas_v1.extreme_35m import EXTREME_IDS
from tasks.ultra_arenas_v1.extreme_builders import (
    build_extreme_case,
    grade_extreme_case,
    sim_extreme_race,
    solve_extreme_ref,
)
from tasks.ultra_arenas_v1.flagship_30m import FLAGSHIP_IDS
from tasks.ultra_arenas_v1.flagship_builders import (
    build_flagship_case,
    grade_flagship_case,
    sim_flagship_race,
    solve_flagship_ref,
)
from tasks.ultra_arenas_v1.engines import (
    UA01_BI_PAGES,
    eval_ua01_drc,
    eval_ua02_drc,
    eval_ua03_drc,
    eval_ua04_cae_and_drc,
    eval_ua05_drc,
    eval_ua06_drc,
    eval_ua07_drc,
)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_ua01(workspace: Path, tickets: dict[str, Path]) -> None:
    pport = UA_BY_ID["UA-01"]["portal_port"]
    (workspace / "exports").mkdir(parents=True, exist_ok=True)

    # 5-sheet Q3_Enterprise_Model.xlsx with live cross-sheet formulas in Executive_Summary
    sum_rows = [
        ["Metric", "Value", "Formula_Description"],
        ["Base_Net_Revenue_kUSD", ("=SUM(Finance_12M!B2:B14)", 0.0), "12 BI units + Row 14 APAC Audit Contra"],
        ["Base_Direct_Cost_kUSD", ("=SUM(Finance_12M!C2:C14)", 0.0), "12 BI units direct cost"],
        ["Total_Infra_Ops_Spend_kUSD", ("=SUM(Datacenter_16R!F2:F17)", 0.0), "16 Datacenters rack + PUE power spend"],
        ["Weighted_Sales_Pipeline_kUSD", ("=SUM(Pipeline_12T!G2:G13)", 0.0), "12 CRM territories weighted ARR"],
        ["Quarterly_Debt_Service_kUSD", ("=Finance_12M!F4", 950.0), "Quarterly senior + mezzanine debt service"],
        ["Net_Operating_Income_kUSD", ("=B2+0.18*B5-B3-B4", 0.0), "Operating income before debt service"],
        ["Ecosystem_Web_Checksum", ("=SUM(Ecosystem_Audit!C2:C6)", 0.0), "Sum of 5 real external web numeric anchors"],
    ]
    fin_rows = [["unit_id", "net_rev_kusd", "direct_cost_kusd", "notes", "param_key", "param_val"]] + [
        [f"unit_{i:02d}", 0.0, 0.0, "", "hedge_ratio" if i == 1 else ("reserve_kusd" if i == 2 else ("debt_service_q" if i == 3 else "")), 0.15 if i == 1 else (250.0 if i == 2 else (980.0 if i == 3 else ""))]
        for i in range(1, 13)
    ] + [["audit_apac_contra", 0.0, 0.0, "AUDIT", "", ""]]
    dc_rows = [["dc_id", "region", "active_racks", "failover_racks", "target_pue", "quarterly_spend_kusd"]] + [
        [f"DC_{i:02d}", "PENDING", 15, 2, 1.40, ("=(C" + str(i+1) + "*1.85+D" + str(i+1) + "*1.25)*E" + str(i+1), 0.0)]
        for i in range(1, 17)
    ]
    sp_rows = [["territory", "region", "open_arr_kusd", "win_weight", "price_mult", "rebate_pct", "weighted_arr_kusd"]] + [
        [f"T{i:02d}", "PENDING", 0.0, 0.35, 1.00, 0.02, ("=C" + str(i+1) + "*D" + str(i+1) + "*E" + str(i+1) + "*(1-F" + str(i+1) + ")", 0.0)]
        for i in range(1, 13)
    ]
    eco_rows = [
        ["anchor_key", "source_url", "verified_numeric_value", "verified_license_or_note"],
        ["gpt2_vocab_size", "https://huggingface.co/openai-community/gpt2", 0, ""],
        ["bert_hidden_size", "https://huggingface.co/google-bert/bert-base-uncased", 0, ""],
        ["transformer_arxiv_year", "https://arxiv.org/abs/1706.03762", 0, ""],
        ["gpt3_arxiv_year", "https://arxiv.org/abs/2005.14165", 0, ""],
        ["pep8_max_line_length", "https://peps.python.org/pep-0008/", 0, ""],
    ]
    write_multisheet_xlsx(
        workspace / "Q3_Enterprise_Model.xlsx",
        [
            ("Executive_Summary", sum_rows),
            ("Finance_12M", fin_rows),
            ("Datacenter_16R", dc_rows),
            ("Pipeline_12T", sp_rows),
            ("Ecosystem_Audit", eco_rows),
        ],
    )

    # Seed Blender 3D cover scene with 4 regional bars initialized to flat 1.0m
    bl_code = textwrap.dedent(f"""\
        import bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 24; sc.cycles.use_denoising = False
        sc.render.resolution_x = 800; sc.render.resolution_y = 450
        for idx, nm in enumerate(("Bar_NA", "Bar_EMEA", "Bar_APAC", "Bar_LATAM")):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2.4 + idx * 1.6, 0.0, 0.5))
            ob = bpy.context.active_object; ob.name = nm
            mat = bpy.data.materials.new(nm + "_Mat"); mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.58, 0.82, 1.0)
            ob.data.materials.append(mat)
        ld = bpy.data.lights.new("SunKey", type="SUN"); ld.energy = 3.5
        lo = bpy.data.objects.new("SunKey", ld); lo.rotation_euler = (0.6, 0.2, -0.4); sc.collection.objects.link(lo)
        cd = bpy.data.cameras.new("CoverCam"); co = bpy.data.objects.new("CoverCam", cd)
        co.location = (0.0, -7.5, 3.2); co.rotation_euler = (1.22, 0.0, 0.0); sc.collection.objects.link(co); sc.camera = co
        bpy.ops.wm.save_as_mainfile(filepath={str(workspace / "q3_cover_3d.blend")!r})
    """)
    subprocess.run(["blender", "-b", "--python-expr", bl_code], check=True, capture_output=True, timeout=90)
    (workspace / "Q3_Board_Briefing.md").write_text("# Q3 Board Briefing\n\n## Finance\nPENDING\n\n## Infrastructure\nPENDING\n\n## Commercial\nPENDING\n\n## Executive Summary\nPENDING\n", encoding="utf-8")
    make_simple_pptx(workspace / "Q3_Board_Deck.pptx", ["DRAFT TEMPLATE"])

    # Blind natural departmental briefs (NO mention of peer agents!)
    tickets["FIN"].write_text(textwrap.dedent(f"""\
        # Assignment: Q3 Corporate Finance & Capital Structure Lead
        Workstation deliverables: `/workspace/Q3_Enterprise_Model.xlsx` (sheet `Finance_12M` & live formulas in `Executive_Summary`) and `## Finance` in `/workspace/Q3_Board_Briefing.md`.

        1. In the open Chromium BI session on `DISPLAY=:99` (`http://127.0.0.1:{pport}`), switch Scope to `FIN`, set Filter to `Q3 / USD / Excl-IC` (re-authenticating SSO if expired), and export all 4 pages (`Page 1..4`) via the browser button into `/home/gui/Downloads/bi_view_export.csv`. Also read the `<canvas>` `AUDIT APAC RETURN CONTRA` adjustment.
        2. Populate rows 2..13 of `Finance_12M` with the 12 exported business units (`net_rev_kusd`, `direct_cost_kusd`) and row 14 `audit_apac_contra` (`-120.0`), keeping `Executive_Summary` formulas intact.
        3. Research live GitHub repositories `https://github.com/pallets/flask` and `https://github.com/sqlalchemy/sqlalchemy` to verify their open-source licenses for the compliance note in `## Finance` of `/workspace/Q3_Board_Briefing.md`.
        4. Tune capital levers in `Finance_12M` (`F2` `hedge_ratio` in `[0.0, 1.0]`, `F3` `reserve_kusd` <= 920, `F4` `debt_service_q` in `[780.0, 960.0]`) by iterating against the workstation Monte-Carlo stress simulator (`POST http://127.0.0.1:{pport}/api/drc_audit`) until `G_FIN_1`..`G_FIN_4` all pass (`worst_20q_dscr >= 1.42`, `min_stress_cash_kusd >= 650`, `noi_margin_pct` in `[46.5, 52.5]`), minimizing idle cash reserve where feasible.
    """), encoding="utf-8")

    tickets["OPS"].write_text(textwrap.dedent(f"""\
        # Assignment: Cloud Infrastructure & AI Compute Operations Lead
        Workstation deliverables: `/workspace/Q3_Enterprise_Model.xlsx` (`Datacenter_16R`), `/workspace/exports/dc_footprint_300dpi.png`, and `## Infrastructure` in `/workspace/Q3_Board_Briefing.md`.

        1. In the open Chromium BI session on `DISPLAY=:99` (`http://127.0.0.1:{pport}`), select Scope `OPS`, Filter `Q3 / USD / Excl-IC`, and export all 4 pages (`Page 1..4`) of the 16 global datacenters.
        2. Visit live `https://huggingface.co/openai-community/gpt2`, `https://huggingface.co/google-bert/bert-base-uncased`, `https://arxiv.org/abs/1706.03762`, and `https://arxiv.org/abs/2005.14165` to verify inference model sizing benchmarks for `## Infrastructure` in `/workspace/Q3_Board_Briefing.md`.
        3. Optimize `active_racks` (`C2:C17`), `failover_racks` (`D2:D17`), and liquid-cooling `target_pue` (`E2:E17`, in `[1.18, 1.35]`) in `Datacenter_16R` (keeping column `F` spend formulas intact!) against `POST http://127.0.0.1:{pport}/api/drc_audit` until `G_OPS_1`..`G_OPS_4` pass (`p95_latency_ms <= 38.0`, `failover_ratio` in `[0.22, 0.38]`, `ops_capex_opex_kusd` in `[820, 1280]`, `mean_pue <= 1.31`).
        4. Render a high-resolution regional rack & PUE chart `/workspace/exports/dc_footprint_300dpi.png` (via Matplotlib/Inkscape).
    """), encoding="utf-8")

    tickets["SALES"].write_text(textwrap.dedent(f"""\
        # Assignment: Global Commercial Pipeline & Open-Source Ecosystem Lead
        Workstation deliverables: `/workspace/Q3_Enterprise_Model.xlsx` (`Pipeline_12T` & `Ecosystem_Audit`) and `## Commercial` in `/workspace/Q3_Board_Briefing.md`.

        1. In the open Chromium BI session on `DISPLAY=:99` (`http://127.0.0.1:{pport}`), select Scope `SALES`, Filter `Q3 / USD / Excl-IC`, and export all 4 pages (`Page 1..4`) of the 12 sales territories.
        2. Fetch exact live external web benchmarks to populate `Ecosystem_Audit` (`C2:C6`) in `/workspace/Q3_Enterprise_Model.xlsx`:
           - `gpt2_vocab_size` from `https://huggingface.co/openai-community/gpt2` (`config.json` `vocab_size`)
           - `bert_hidden_size` from `https://huggingface.co/google-bert/bert-base-uncased` (`config.json` `hidden_size`)
           - Original publication years of `https://arxiv.org/abs/1706.03762` (2017) and `https://arxiv.org/abs/2005.14165` (2020)
           - Standard code max line length in `https://peps.python.org/pep-0008/` (79)
        3. Populate `Pipeline_12T` (`open_arr_kusd`, regional win weights `NA=0.42, EMEA=0.38, APAC=0.34, LATAM=0.28`, and tune `price_mult` `E2:E13` & `rebate_pct` `F2:F13` keeping `G2:G13` formulas intact) via `/api/drc_audit` until `G_SALES_1`..`G_SALES_3` pass (`sales_weighted_kusd` in `[3650, 4450]`, `effective_nrr_pct >= 114.0`, `churn_penalty_kusd <= 85.0`). Update `## Commercial` in `/workspace/Q3_Board_Briefing.md`.
    """), encoding="utf-8")

    tickets["EXEC"].write_text(textwrap.dedent(f"""\
        # Assignment: Chief of Staff — 3D Visual Cover, Board Deck & Final Sign-Off
        Workstation deliverables: `/workspace/q3_cover_3d.blend` -> `/workspace/exports/q3_revenue_3d.png`, `/workspace/Q3_Board_Deck.pptx`, `/workspace/exports/Q3_Board_Briefing.pdf`, and Board email.

        1. Read the `BOARD SIGN-OFF TOKEN` and `3D COVER BARS` specification from the Chromium `<canvas>` on `DISPLAY=:99` (`http://127.0.0.1:{pport}`).
        2. Reconcile `/workspace/Q3_Enterprise_Model.xlsx` (`Executive_Summary`) and scale the Z-heights (with bottom resting on `z=0`) of `Bar_NA`, `Bar_EMEA`, `Bar_APAC` (including the `-120.0` APAC contra!), and `Bar_LATAM` in `/workspace/q3_cover_3d.blend` to match the 4 regional net revenue proportions, then render `/workspace/exports/q3_revenue_3d.png` (`800x450` Cycles).
        3. Copy `/workspace/exports/q3_revenue_3d.png` via X11 clipboard (`xclip -selection clipboard -t image/png -i ... >/dev/null 2>&1`) into `/workspace/Q3_Board_Deck.pptx` (`ppt/media/image1.png`) with the `BOARD SIGN-OFF TOKEN` and `Executive_Summary` KPIs; complete `## Executive Summary` in `/workspace/Q3_Board_Briefing.md` and convert it via `libreoffice --headless --convert-to pdf` to `/workspace/exports/Q3_Board_Briefing.pdf`.
        4. Run `POST http://127.0.0.1:{pport}/api/drc_audit` until ALL 14 workstation gates (`all_gates_passed == true`) are green, then dispatch `POST http://127.0.0.1:{pport}/api/mail/send_board` with `{{"board_token": "<TOKEN>", "noi_kusd": <float>, "worst_dscr": <float>, "model_path": "/workspace/Q3_Enterprise_Model.xlsx"}}`.
    """), encoding="utf-8")


def build_ua02(workspace: Path, tickets: dict[str, Path]) -> None:
    pport = UA_BY_ID["UA-02"]["portal_port"]
    sport = UA_BY_ID["UA-02"]["staging_port"]
    repo = workspace / "nexus-portal"
    (repo / "templates").mkdir(parents=True, exist_ok=True)
    (repo / "static/assets").mkdir(parents=True, exist_ok=True)
    (repo / "tools").mkdir(parents=True, exist_ok=True)
    (workspace / "staging_data").mkdir(parents=True, exist_ok=True)
    (workspace / "exports").mkdir(parents=True, exist_ok=True)

    for rt in ("index", "pricing", "docs", "sdk", "integrations", "benchmarks", "security", "changelog"):
        (repo / f"templates/{rt}.html").write_text(f"<html><body><h1>{rt} v0</h1></body></html>\n", encoding="utf-8")
    # Seed 5 real canary defects in initial commit
    write_json(repo / "portal_config.json", {
        "sqlite_pool_size": 1,
        "annual_discount_pct": -20.0,
        "enterprise_sla_mult": 0.0,
        "changelog_tz": "PST-8",
        "csrf_cookie_samesite": False,
    })
    (repo / "static/assets/brand_mark.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48" viewBox="0 0 48 48"><rect x="4" y="6" width="152" height="36" fill="#0EA5E9"/></svg>\n',
        encoding="utf-8",
    )
    write_json(repo / "tools/export_profile.json", {"png_compression": 1, "dpi": 72})
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "NexusDev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@nexus.local"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Seed v0 nexus-portal"], cwd=repo, check=True, capture_output=True)

    con = sqlite3.connect(str(workspace / "staging_data/nexus.db"))
    con.execute("CREATE TABLE cms_integrations(slug TEXT PRIMARY KEY, title TEXT, license_spdx TEXT, benchmark_num TEXT, asset_file TEXT, published INTEGER)")
    con.commit(); con.close()

    tickets["FE"].write_text(textwrap.dedent(f"""\
        # Assignment: Lead Full-Stack Engineer — Nexus v5 Portal
        Codebase: `/workspace/nexus-portal` (deployed to `http://127.0.0.1:{sport}` via `POST /api/redeploy`). Spec Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Read target pricing, security, and coupled latency rules on `DISPLAY=:99` (`http://127.0.0.1:{pport}`), and consult live `https://docs.python.org/3/library/sqlite3.html` & `https://peps.python.org/pep-0008/`.
        2. Upgrade all 8 templates (`index, pricing, docs, sdk, integrations, benchmarks, security, changelog`) in `/workspace/nexus-portal/templates/` with `data-nexus-v5="ready"`, brand mark, hero images, and feature cards.
        3. Remediate `portal_config.json` (`annual_discount_pct = 20.0`, `enterprise_sla_mult = 1.35`, `changelog_tz = "UTC"`, `csrf_cookie_samesite = true`) and tune `sqlite_pool_size` (`8..16`) via `POST http://127.0.0.1:{pport}/api/drc_audit` so `sim_page_p95_ms <= 155.0`. Commit cleanly on `main` and call `POST http://127.0.0.1:{sport}/api/redeploy`.
    """), encoding="utf-8")

    tickets["DESIGN"].write_text(textwrap.dedent(f"""\
        # Assignment: Principal 3D & Brand Designer — Multi-Software Asset Pipeline
        Codebase assets: `/workspace/nexus-portal/static/assets/`. Spec Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Read exact asset dimensions and total static payload ceiling (`<= 1150 KB`!) from `<canvas>` on `DISPLAY=:99`.
        2. Fix `brand_mark.svg` `viewBox="0 0 160 48"`. Build a 3D hardware/cloud node scene in Blender Cycles (`24-32` samples) and render 3 camera angles: `hero_front.png` (`1280x640`), `hero_iso.png` (`800x500`), `hero_detail.png` (`800x500`) with subject non-dark occupancy in `[0.22, 0.78]`.
        3. Create `feature_card_1.png`..`feature_card_4.png` (`640x400` via GIMP/PIL) and `badge_1.png`..`badge_4.png` (`128x128` via Inkscape), optimize PNG compression so total `/static/assets/*` stays `<= 1150 KB` (`G_DES_3` + `G_FE_3` coupled P95!), commit cleanly to `main`, and redeploy Staging.
    """), encoding="utf-8")

    tickets["CMS"].write_text(textwrap.dedent(f"""\
        # Assignment: Technical Ecosystem Content Lead — 16 Live-Verified Integrations
        Database: `/workspace/staging_data/nexus.db` (`cms_integrations`). Spec Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Visit live external websites (`https://github.com/pallets/flask`, `https://github.com/psf/requests`, `https://github.com/encode/httpx`, `https://github.com/sqlalchemy/sqlalchemy`, `https://huggingface.co/openai-community/gpt2`, `https://arxiv.org/abs/1512.03385`, `https://peps.python.org/pep-0008/`, `https://pypi.org/project/pillow/`) to collect real SPDX licenses and numeric benchmarks (`50257`, `2015`, `79`).
        2. Populate 16 published rows (`published = 1`) in `cms_integrations(slug, title, license_spdx, benchmark_num, asset_file, published)` including slugs `flask`, `requests`, `sqlalchemy`, `gpt2`, `resnet`, `pep8` with accurate real-web facts and valid `feature_card_1.png`..`feature_card_4.png` bindings.
        3. Verify `G_CMS_1` and `G_CMS_2` via `POST http://127.0.0.1:{pport}/api/drc_audit`.
    """), encoding="utf-8")

    tickets["QA"].write_text(textwrap.dedent(f"""\
        # Assignment: Release QA Lead — Defect Triage, Regression Matrix & GA Sign-Off
        Staging: `http://127.0.0.1:{sport}`. QA Gate: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Audit initial repository commit (`git log -p -n 1` in `/workspace/nexus-portal`) and report ONLY the 5 real pre-seeded code/SVG defects to `POST http://127.0.0.1:{pport}/api/qa/report_defect` (`{{"bug_code": ...}}`): `BUG-ANNUAL-SURCHARGE`, `BUG-ENT-SLA-ZERO`, `BUG-TZ-PST8`, `BUG-CSRF-SAMESITE`, `BUG-BRAND-VIEWBOX` (reporting non-existent or transient WIP codes incurs penalties!).
        2. Build `/workspace/QA_Regression_Matrix.xlsx` and export `/workspace/exports/QA_Release_Report.pdf` via LibreOffice.
        3. Iterate with `POST http://127.0.0.1:{pport}/api/drc_audit` until ALL 10 launch gates pass (`all_gates_passed == true`) and `git status` on `main` is completely clean, then submit `POST http://127.0.0.1:{pport}/api/qa/release_signoff` (`{{"release_token": "NEXUS-V5-GA", "git_commit": "<final_HEAD_sha>"}}`).
    """), encoding="utf-8")


def build_ua03(workspace: Path, tickets: dict[str, Path]) -> None:
    pport = UA_BY_ID["UA-03"]["portal_port"]
    cport = UA_BY_ID["UA-03"]["cluster_port"]
    cdir = workspace / "cluster"
    (cdir / "disk_vol").mkdir(parents=True, exist_ok=True)
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "forensics").mkdir(parents=True, exist_ok=True)
    (workspace / "exports").mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(cdir / "prod_ledger.db"))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE ledger_events(id INTEGER PRIMARY KEY, account_id TEXT, region_code TEXT, status TEXT, event_ts INTEGER, amount_cents INTEGER)")
    rows = [(i, f"ACC-{i % 80:03d}", ("NA", "EMEA", "APAC", "LATAM")[i % 4], "SETTLED", 1710000000 + i, 1050 + (i % 500)) for i in range(1, 5001)]
    con.executemany("INSERT INTO ledger_events VALUES(?,?,?,?,?,?)", rows)
    con.commit(); con.close()

    write_json(cdir / "db_tuning.json", {"sqlite_cache_mb": 24, "checkpoint_batch": 5000})
    write_json(cdir / "app_gateway.json", {"hot_cache_mb": 24, "retry_backoff_ms": 0, "max_retries": 12, "cache_ttl_s": 0, "singleflight": False, "token_bucket_rps": 150})
    write_json(cdir / "infra_daemon.json", {"telemetry_buffer_mb": 280, "log_level": "TRACE_ALL", "liveness_timeout_ms": 40})
    (cdir / "disk_vol/core_trace.bin").write_bytes(b"E" * (480 * 1024))

    gpkg = workspace / "data/edge_network.gpkg"
    gcon = sqlite3.connect(str(gpkg))
    gcon.execute("CREATE TABLE edge_pops(pop_id TEXT PRIMARY KEY, region TEXT, cable_status TEXT, capacity_gbps REAL, assigned_traffic_gbps REAL, base_rtt_ms REAL, cost_per_gbps REAL)")
    pop_rows = []
    for i in range(1, 25):
        sev = "SEVERED" if i in (3, 9, 15, 21) else "ACTIVE"
        reg = ("NA", "EMEA", "APAC", "LATAM")[(i - 1) // 6]
        rtt = 25.0 + (i % 6) * 2.4
        cost = round(0.082 + (i % 5) * 0.003, 4)
        pop_rows.append((f"POP_{i:02d}", reg, sev, 36.0, 20.0, rtt, cost))
    gcon.executemany("INSERT INTO edge_pops VALUES(?,?,?,?,?,?,?)", pop_rows)
    gcon.commit(); gcon.close()
    (workspace / "Global_Edge_Routing.qgz").write_text('<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM"><qgis version="3.22.16"><projectlayers><maplayer><datasource>./data/edge_network.gpkg|layername=edge_pops</datasource></maplayer></projectlayers></qgis>\n', encoding="utf-8")

    write_multisheet_xlsx(
        workspace / "Capacity_Budget.xlsx",
        [
            ("Summary", [
                ["Metric", "Value", "Notes"],
                ["Total_Cluster_RAM_MB", ("=SUM(Allocations!B2:B4)", 0.0), "Must stay <= 640 MB"],
                ["Littles_Law_Concurrency", ("=Allocations!B5*(Allocations!B6/1000)", 0.0), "L = lambda * W"],
            ]),
            ("Allocations", [
                ["Component", "Value"],
                ["sqlite_cache_mb", 24.0],
                ["hot_cache_mb", 24.0],
                ["telemetry_buffer_mb", 280.0],
                ["arrival_rate_rps", 1200.0],
                ["target_p99_ms", 65.0],
            ]),
        ],
    )
    (workspace / "INC_Postmortem_RCA.md").write_text("# Incident War-Room Postmortem\n\n## DB Forensics\nPENDING\n\n## Gateway & Cache\nPENDING\n\n## Edge Network & Infra\nPENDING\n\n## Canary Signoff\nPENDING\n", encoding="utf-8")

    tickets["DB"].write_text(textwrap.dedent(f"""\
        # Assignment: Principal Database Reliability Engineer — Incident Response
        Grafana Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Cluster Metrics: `http://127.0.0.1:{cport}/metrics`.

        1. Wait until `/workspace/cluster/slow_query_ring.json` achieves `sufficient_window_25s == true` (>= 25s undisturbed live sampling) and archive it to `/workspace/forensics/db_fingerprint_30s.json`.
        2. Consult live `https://docs.python.org/3/library/sqlite3.html` and add the two missing composite indexes `(account_id, event_ts)` and `(region_code, status)` on `ledger_events` in `/workspace/cluster/prod_ledger.db`.
        3. Tune `/workspace/cluster/db_tuning.json` (`sqlite_cache_mb >= 180`, `checkpoint_batch <= 400`) and `Allocations!B2` in `/workspace/Capacity_Budget.xlsx` under the global 640 MB cluster RAM ceiling via `POST http://127.0.0.1:{pport}/api/drc_audit`. Document in `## DB Forensics` of `/workspace/INC_Postmortem_RCA.md`.
    """), encoding="utf-8")

    tickets["APP"].write_text(textwrap.dedent(f"""\
        # Assignment: Application Gateway & Distributed Cache Oncall
        Grafana Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Cluster API: `http://127.0.0.1:{cport}`.

        1. Consult live `https://en.wikipedia.org/wiki/Token_bucket` and `https://en.wikipedia.org/wiki/Exponential_backoff`, and inspect `<canvas>` on `DISPLAY=:99` (do NOT run `mode="hard"` restart while DB forensics are still sampling!).
        2. Tune `/workspace/cluster/app_gateway.json` (`hot_cache_mb >= 220`, `retry_backoff_ms` in `[150, 600]`, `max_retries` in `[1, 3]`, `cache_ttl_s >= 90`, `singleflight = true`, `token_bucket_rps` in `[900, 1800]`) and `Allocations!B3` in `/workspace/Capacity_Budget.xlsx` so total cluster RAM stays `<= 640 MB` via `/api/drc_audit`. Update `## Gateway & Cache` in `/workspace/INC_Postmortem_RCA.md`.
    """), encoding="utf-8")

    tickets["INFRA"].write_text(textwrap.dedent(f"""\
        # Assignment: Edge Network & Infrastructure SRE (QGIS + Daemon Stabilization)
        Grafana Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Spatial Project: `/workspace/Global_Edge_Routing.qgz` (`/workspace/data/edge_network.gpkg`).

        1. Stabilize `/workspace/cluster/infra_daemon.json` (`telemetry_buffer_mb` in `[90, 190]`, `log_level = "INFO"`, `liveness_timeout_ms >= 800`), clear `/workspace/cluster/disk_vol/core_trace.bin` (< 100 KB), and update `Allocations!B4` in `/workspace/Capacity_Budget.xlsx` within the 640 MB total RAM ceiling.
        2. Rebalance `assigned_traffic_gbps` across the 24 POPs in `/workspace/data/edge_network.gpkg` (`edge_pops`: total `480.0 Gbps`, all `SEVERED` submarine cables set to `0.0 Gbps`, max POP utilization `<= 76%`, weighted RTT `<= 52.0 ms`, transit cost `<= 46.0 kUSD/h`), save `/workspace/Global_Edge_Routing.qgz`, and export `/workspace/exports/edge_reroute_map.pdf` + update `## Edge Network & Infra` in `/workspace/INC_Postmortem_RCA.md`.
    """), encoding="utf-8")

    tickets["IC"].write_text(textwrap.dedent(f"""\
        # Assignment: Incident Commander — Little's Law Audit, Burst Replay & Postmortem
        Grafana & StatusPage: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Cluster API: `http://127.0.0.1:{cport}`.

        1. Read `INCIDENT TOKEN` (`WARROOM-9901`) from `<canvas>` on `DISPLAY=:99` and verify Little's Law (`https://en.wikipedia.org/wiki/Little%27s_law`) in `/workspace/Capacity_Budget.xlsx` (`Summary` live formulas intact and matching live RAM configs).
        2. Iterate with `POST http://127.0.0.1:{pport}/api/drc_audit` until all subsystem gates pass, then run `POST http://127.0.0.1:{cport}/api/canary_burst` (1.5x traffic surge) verifying `p99_ms <= 65.0` and `error_rate == 0.0`.
        3. Complete `## Canary Signoff` in `/workspace/INC_Postmortem_RCA.md`, convert it via `libreoffice --headless --convert-to pdf` to `/workspace/exports/INC_Postmortem_RCA.pdf`, and publish `POST http://127.0.0.1:{pport}/api/statuspage/resolve` (`{{"incident_token": "WARROOM-9901", "canary_p99_ms": <float>}}`).
    """), encoding="utf-8")


def build_ua04(workspace: Path, tickets: dict[str, Path]) -> None:
    pport = UA_BY_ID["UA-04"]["portal_port"]
    for sub in ("raw", "vfx", "audio", "exports"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)

    fc_init = textwrap.dedent(f"""\
        import FreeCAD as App, Part
        doc = App.newDocument("AeroActuator")
        ss = doc.addObject("Spreadsheet::Sheet", "MasterSpec")
        ss.set("A2", "housing_bore_mm"); ss.set("B2", "88.0")
        ss.set("A3", "flex_od_mm"); ss.set("B3", "88.4")
        ss.set("A4", "flex_wall_mm"); ss.set("B4", "2.1")
        ss.set("A5", "cover_flange_h_mm"); ss.set("B5", "7.0")
        doc.recompute()
        h = doc.addObject("Part::Feature", "Housing")
        h.Shape = Part.makeCylinder(56.0, 28.0).cut(Part.makeCylinder(44.0, 28.0))
        f = doc.addObject("Part::Feature", "Flexspline")
        f.Shape = Part.makeCylinder(44.2, 22.0, App.Vector(0,0,2)).cut(Part.makeCylinder(42.1, 22.0, App.Vector(0,0,2)))
        r = doc.addObject("Part::Feature", "RotorWave")
        r.Shape = Part.makeCylinder(41.5, 18.0, App.Vector(0,0,4)).cut(Part.makeCylinder(14.0, 18.0, App.Vector(0,0,4)))
        c = doc.addObject("Part::Feature", "TopCover")
        c.Shape = Part.makeCylinder(56.0, 7.0, App.Vector(0,0,28.2)).cut(Part.makeCylinder(20.0, 7.0, App.Vector(0,0,28.2)))
        doc.recompute()
        doc.saveAs({str(workspace / "aero_actuator.FCStd")!r})
    """)
    subprocess.run(["freecadcmd", "-c", fc_init], check=True, capture_output=True, timeout=90)

    write_multisheet_xlsx(
        workspace / "Engineering_Master_BOM.xlsx",
        [
            ("Summary", [
                ["Metric", "Value", "Notes"],
                ["Total_Volume_cm3", ("=SUM(Parts!B2:B5)", 0.0), "4 CAD solids sum"],
                ["Total_Mass_g", ("=B2*Literature!B2", 0.0), "Volume * Ti-6Al-4V density"],
                ["Material_Cost_USD", ("=B3*0.92", 0.0), "Aerospace grade billet"],
                ["Literature_Checksum", ("=SUM(Literature!B2:B5)", 0.0), "Density + 3 arXiv benchmark years"],
            ]),
            ("Parts", [
                ["Part", "Volume_cm3"],
                ["Housing", 0.0],
                ["Flexspline", 0.0],
                ["RotorWave", 0.0],
                ["TopCover", 0.0],
            ]),
            ("Literature", [
                ["Key", "Numeric_Anchor"],
                ["ti6al4v_density_g_cm3", 0.0],
                ["arxiv_1706_03762_year", 0.0],
                ["arxiv_1512_03385_year", 0.0],
                ["arxiv_2005_14165_year", 0.0],
            ]),
        ],
    )
    subprocess.run(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "raw/narration_raw.wav"), "synth", "15.0", "sine", "330", "vol", "0.52"], check=True, capture_output=True)

    tickets["CAD_HOUSING"].write_text(textwrap.dedent(f"""\
        # Assignment: Mechanical Housing & Top-Cover CAD Lead
        Assembly: `/workspace/aero_actuator.FCStd` (`Housing`, `TopCover`, `MasterSpec`). Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Inspect `<canvas>` on `DISPLAY=:99` for radial film gap (`[0.16, 0.25] mm`), total mass cap (`<= 1.180 kg`), CG (`<= 0.30 mm`), and safety factor (`>= 2.05`).
        2. Redesign `Housing` (e.g. bore `90.0 mm` `B2="90.0"`, lightweighted outer radius `51.0 mm`, height `26.0 mm` at `z=0..26`) and `TopCover` (outer R=`51.0 mm`, inner bore R=`22.0 mm`, flange thickness `B5` >= `11.5 mm` at `z=26.2..` for zero axial interference) in `/workspace/aero_actuator.FCStd`, and export `/workspace/exports/housing_assy.step`.
        3. Iterate with `/api/drc_audit` so `Housing` + `TopCover` provide `B5` stiffness without pushing total 4-part Ti-6Al-4V mass above `1.180 kg`.
    """), encoding="utf-8")

    tickets["CAD_ROTOR"].write_text(textwrap.dedent(f"""\
        # Assignment: Harmonic Flexspline & Wave-Generator Rotor CAD Lead
        Assembly: `/workspace/aero_actuator.FCStd` (`Flexspline`, `RotorWave`, `MasterSpec`). Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Read radial film gap (`[0.16, 0.25] mm`), safety factor (`>= 2.05`), and mass cap (`<= 1.180 kg`) from `<canvas>`.
        2. Redesign `Flexspline` (outer diameter `B3` matching `B2 - 2*gap`, e.g. `89.60 mm` for `90.0 mm` bore -> `0.20 mm` radial gap; wall thickness `B4 >= 3.6 mm` for torsional safety factor `>= 2.05`, `z=2..24`) and hollow `RotorWave` (outer R < Flexspline inner R for zero interference, hollow core R=`18.0 mm`, `z=4..22`) in `/workspace/aero_actuator.FCStd`, exporting `/workspace/exports/rotor_assy.step`.
    """), encoding="utf-8")

    tickets["CAE_LIT"].write_text(textwrap.dedent(f"""\
        # Assignment: CAE Simulation & Technical Literature Benchmark Lead
        Deliverables: `/workspace/exports/cae_cert.json` (via single-seat `POST /api/cae/exclusive_solve`), `/workspace/Engineering_Master_BOM.xlsx`, and `/workspace/exports/Engineering_Whitepaper.pdf`.

        1. Consult live `https://en.wikipedia.org/wiki/Titanium_alloy` (`Ti-6Al-4V` density `4.43` g/cm3), `https://en.wikipedia.org/wiki/Strain_wave_gearing`, and live arXiv abstracts `1706.03762` (`2017`), `1512.03385` (`2015`), `2005.14165` (`2020`) to populate sheet `Literature` (`B2:B5`) in `/workspace/Engineering_Master_BOM.xlsx` and write `/workspace/Engineering_Whitepaper.md` -> convert via `libreoffice --headless --convert-to pdf` to `/workspace/exports/Engineering_Whitepaper.pdf`.
        2. Run the exclusive single-seat CAE solver (`POST http://127.0.0.1:{pport}/api/cae/exclusive_solve` with `{{"review_token": "AERO-ACT-2026"}}`; retry if `409 ERR_CAE_LICENSE_BUSY`) once CAD geometry settles, and populate sheet `Parts` (`B2:B5` `Volume_cm3` in `cm3`!) in `Engineering_Master_BOM.xlsx` keeping `Summary` formulas intact.
    """), encoding="utf-8")

    tickets["MEDIA_PUB"].write_text(textwrap.dedent(f"""\
        # Assignment: Broadcast Engineering Visualization & Release Producer
        Deliverables: `/workspace/exports/cutaway_beauty.png`, `/workspace/exports/actuator_launch_720p.mp4` (`1280x720`, `24fps`, `360` frames = `15.0s`), and `POST /api/media/publish`.

        1. Read `ACTUATOR REVIEW TOKEN` (`AERO-ACT-2026`) and broadcast specs (`1280x720 @ 24fps, 360 frames, -23.0 +/- 0.4 LUFS`) from `<canvas>` on `DISPLAY=:99`.
        2. Import/model the settled actuator cutaway in Blender Cycles (`24` samples) to render `/workspace/exports/cutaway_beauty.png` (`1280x720`), composite a GIMP/PIL telemetry lower-third bar displaying the final converged mass & safety factor, master `/workspace/raw/narration_raw.wav` to `-23.0 LUFS`, and encode the `15.0s` (`360`-frame) H.264+AAC master `/workspace/exports/actuator_launch_720p.mp4`.
        3. Verify `all_gates_passed == true` via `POST http://127.0.0.1:{pport}/api/drc_audit` and publish via `POST http://127.0.0.1:{pport}/api/media/publish` (`{{"release_token": "AERO-ACT-2026", "mp4_path": "/workspace/exports/actuator_launch_720p.mp4"}}`) ONLY after CAD/CAE and video are finalized.
    """), encoding="utf-8")


def build_ultra_case(task_id: str, workspace: Path, tickets_root: Path) -> None:
    meta = UA_BY_ID[task_id]
    if workspace.exists():
        for c in list(workspace.iterdir()):
            shutil.rmtree(c) if c.is_dir() else c.unlink()
    workspace.mkdir(parents=True, exist_ok=True)
    tickets = {}
    for r in meta["roles"]:
        rd = tickets_root / r; rd.mkdir(parents=True, exist_ok=True)
        tickets[r] = rd / "task.md"
    if task_id == "UA-01":
        build_ua01(workspace, tickets)
    elif task_id in EXTREME_IDS:
        build_extreme_case(task_id, workspace, tickets)
    elif task_id in FLAGSHIP_IDS:
        build_flagship_case(task_id, workspace, tickets)
    elif task_id == "UA-02":
        build_ua02(workspace, tickets)
    elif task_id == "UA-03":
        build_ua03(workspace, tickets)
    elif task_id == "UA-04":
        build_ua04(workspace, tickets)
    elif task_id == "UA-05":
        build_ua05(workspace, tickets)
    elif task_id == "UA-06":
        build_ua06(workspace, tickets)
    elif task_id == "UA-07":
        build_ua07(workspace, tickets)
    else:
        raise ValueError(task_id)


def build_ua05(workspace: Path, tickets: dict[str, Path]) -> None:
    build_ua01(workspace, tickets)
    pport = UA_BY_ID["UA-05"]["portal_port"]
    for r in ("FIN", "OPS", "SALES", "EXEC"):
        txt = tickets[r].read_text(encoding="utf-8").replace("19511", str(pport))
        tickets[r].write_text(txt, encoding="utf-8")
    # Inject local directional optimization goals that pull against the narrow [48.0%, 50.4%] Pareto corridor!
    tickets["FIN"].write_text(tickets["FIN"].read_text(encoding="utf-8") + "\nLocal treasury goal: push `worst_20q_dscr >= 1.54` (ideally > 1.65) while keeping `noi_margin_pct` strictly inside `[48.0, 50.4]`!\n", encoding="utf-8")
    tickets["OPS"].write_text(tickets["OPS"].read_text(encoding="utf-8") + "\nLocal SRE goal: drive `p95_latency_ms <= 25.5` ms (ideally < 22 ms) without breaking `ops_capex_opex_kusd <= 1280` or the `[48.0, 50.4]` NOI margin band!\n", encoding="utf-8")
    tickets["SALES"].write_text(tickets["SALES"].read_text(encoding="utf-8") + "\nLocal growth goal: drive `effective_nrr_pct >= 114.8%` with `churn_penalty_kusd <= 45.0`!\n", encoding="utf-8")
    tickets["EXEC"].write_text(tickets["EXEC"].read_text(encoding="utf-8") + "\nNote: `/api/drc_audit` also runs a 3-sun Cycles photometric check (`G_EXEC_4_three_sun_cycles_photometry`: `p98 <= 0.92`, `p10 >= 0.02` across 3 sun angles on `q3_cover_3d.blend`).\n", encoding="utf-8")


def build_ua06(workspace: Path, tickets: dict[str, Path]) -> None:
    build_ua02(workspace, tickets)
    pport = UA_BY_ID["UA-06"]["portal_port"]
    sport = UA_BY_ID["UA-06"]["staging_port"]
    repo = workspace / "nexus-portal"
    for rt in ("enterprise", "status", "cli", "community"):
        (repo / f"templates/{rt}.html").write_text(f"<html><body><h1>{rt} v0</h1></body></html>\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add 4 extra enterprise/cli routes"], cwd=repo, check=True, capture_output=True)
    for r in ("FE", "DESIGN", "CMS", "QA"):
        txt = tickets[r].read_text(encoding="utf-8").replace("19521", str(pport)).replace("19520", str(sport))
        tickets[r].write_text(txt, encoding="utf-8")
    tickets["FE"].write_text(tickets["FE"].read_text(encoding="utf-8") + "\nAlso upgrade the 4 additional routes (`enterprise, status, cli, community` -> 12 routes total with `data-nexus-v5=\"ready\"`).\n", encoding="utf-8")
    tickets["DESIGN"].write_text(tickets["DESIGN"].read_text(encoding="utf-8") + "\nAdditionally, render a **144-frame (`6.0s @ 24fps`, `640x360`) 3D animated turntable product loop** `/workspace/nexus-portal/static/assets/hero_turntable.mp4` in Blender Cycles with visible camera/object rotation across frames (`G_DES_4_turntable_144f_motion_mp4`), while keeping total `/static/assets/*` size `<= 1150 KB`!\n", encoding="utf-8")
    tickets["CMS"].write_text(tickets["CMS"].read_text(encoding="utf-8") + "\nExpand to **24 published integrations** (`G_CMS_1`), additionally verifying live `https://huggingface.co/google-bert/bert-base-uncased` (`bert`, `768`) and `https://github.com/pydantic/pydantic` (`pydantic`, `MIT`) (`>= 8` real-web grounded slugs).\n", encoding="utf-8")
    tickets["QA"].write_text(tickets["QA"].read_text(encoding="utf-8") + "\nNote: `/api/drc_audit` runs live headless Chromium screenshots across 3 viewports (`1280x720`, `768x1024`, `390x844`) against `http://127.0.0.1:" + str(sport) + "/pricing` (`G_QA_3_three_viewport_chromium_render`).\n", encoding="utf-8")


def build_ua07(workspace: Path, tickets: dict[str, Path]) -> None:
    build_ua03(workspace, tickets)
    pport = UA_BY_ID["UA-07"]["portal_port"]
    cport = UA_BY_ID["UA-07"]["cluster_port"]
    fc_v = textwrap.dedent(f"""\
        import FreeCAD as App, Part
        doc = App.newDocument("CoolingValve")
        ss = doc.addObject("Spreadsheet::Sheet", "ValveSpec")
        ss.set("A2", "bore_mm"); ss.set("B2", "36.0")
        ss.set("A3", "spool_od_mm"); ss.set("B3", "36.4")
        ss.set("A4", "stroke_mm"); ss.set("B4", "11.0")
        doc.recompute()
        vb = doc.addObject("Part::Feature", "ValveBody")
        vb.Shape = Part.makeCylinder(26.0, 40.0).cut(Part.makeCylinder(18.0, 40.0))
        sp = doc.addObject("Part::Feature", "ValveSpool")
        sp.Shape = Part.makeCylinder(18.2, 24.0, App.Vector(0,0,8))
        doc.recompute()
        doc.saveAs({str(workspace / "cooling_valve.FCStd")!r})
    """)
    subprocess.run(["freecadcmd", "-c", fc_v], check=True, capture_output=True, timeout=90)
    for r in ("DB", "APP", "INFRA", "IC"):
        txt = tickets[r].read_text(encoding="utf-8").replace("19531", str(pport)).replace("19530", str(cport))
        tickets[r].write_text(txt, encoding="utf-8")
    tickets["DB"].write_text(tickets["DB"].read_text(encoding="utf-8").replace("sufficient_window_25s", "sufficient_window_45s").replace("db_fingerprint_30s.json", "db_fingerprint_45s.json").replace("640 MB", "560 MB") + "\nTarget `sqlite_cache_mb >= 190` (ideally 240 MB for max QPS, subject to strict 560 MB total cluster RAM cap!).\n", encoding="utf-8")
    tickets["APP"].write_text(tickets["APP"].read_text(encoding="utf-8").replace("640 MB", "560 MB") + "\nTarget `hot_cache_mb >= 225` (ideally 280 MB for max hit rate, subject to strict 560 MB total cluster RAM cap!).\n", encoding="utf-8")
    tickets["INFRA"].write_text(tickets["INFRA"].read_text(encoding="utf-8").replace("640 MB", "560 MB").replace("[90, 190]", "[95, 140]") + f"\n3. Also repair the datacenter liquid-cooling actuator `/workspace/cooling_valve.FCStd` (`ValveBody` bore `B2` vs `ValveSpool` OD `B3` radial clearance in `[0.12, 0.22] mm` with zero 3D interference, `stroke` `B4` in `[14.0, 18.0] mm`, Ti-6Al-4V density `4.43 g/cm3` total valve mass in `[180, 520] g`) and certify it through the 14s exclusive single-license solver `POST http://127.0.0.1:{pport}/api/cae/valve_solve` (`G_INF_5_cooling_valve_72angle_and_exclusive_cae`).\n", encoding="utf-8")
    tickets["IC"].write_text(tickets["IC"].read_text(encoding="utf-8").replace("640 MB", "560 MB"), encoding="utf-8")


def grade_ultra_case(task_id: str, workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    if task_id in EXTREME_IDS:
        return grade_extreme_case(task_id, workspace, portal_state, wall_seconds)
    if task_id in FLAGSHIP_IDS:
        return grade_flagship_case(task_id, workspace, portal_state, wall_seconds)
    meta = UA_BY_ID[task_id]
    lb_s = float(meta["critical_section_lower_bound_s"])
    eff_wall = max(1.0, float(wall_seconds or lb_s))
    eff_score = round(min(1.0, lb_s / eff_wall), 4)
    side = dict(portal_state.get("collateral_side_effects") or {})
    if "total" not in side:
        side["total"] = sum(int(v) for v in side.values() if isinstance(v, (int, float)))

    if task_id == "UA-01":
        drc = eval_ua01_drc(workspace, run_blender_check=True)
        mails = portal_state.get("sent_emails") or []
        last_m = mails[-1] if mails else {}
        pptx_txt, pptx_img = read_pptx_info(workspace / "Q3_Board_Deck.pptx")
        canary = bool(
            drc.get("all_gates_passed")
            and last_m.get("board_token") == "QBR-2026-Q3-ULTRA"
            and last_m.get("model_sha256") == sha256_file(workspace / "Q3_Enterprise_Model.xlsx")
            and "QBR-2026-Q3-ULTRA" in pptx_txt and pptx_img
        )
        g = drc.get("gates") or {}
        role_p = {
            "FIN": bool(g.get("G_FIN_1_base_rev_and_apac_contra") and g.get("G_FIN_2_stress_min_dscr_ge_1_42") and g.get("G_FIN_3_stress_min_cash_ge_650") and g.get("G_FIN_4_noi_margin_in_band")),
            "OPS": bool(g.get("G_OPS_1_p95_latency_le_38ms") and g.get("G_OPS_2_failover_redundancy_ge_22pct") and g.get("G_OPS_3_ops_budget_cap_le_1280") and g.get("G_OPS_4_global_map_svg_and_png")),
            "SALES": bool(g.get("G_SALES_1_weighted_pipeline_ge_3650") and g.get("G_SALES_2_nrr_ge_114_low_churn") and g.get("G_SALES_3_ecosystem_real_web_anchors")),
            "EXEC": canary,
        }
    elif task_id == "UA-05":
        drc = eval_ua05_drc(workspace)
        mails = portal_state.get("sent_emails") or []
        last_m = mails[-1] if mails else {}
        pptx_txt, pptx_img = read_pptx_info(workspace / "Q3_Board_Deck.pptx")
        canary = bool(drc.get("all_gates_passed") and last_m.get("board_token") == "QBR-2026-Q3-ULTRA" and last_m.get("model_sha256") == sha256_file(workspace / "Q3_Enterprise_Model.xlsx") and "QBR-2026-Q3-ULTRA" in pptx_txt and pptx_img)
        g = drc.get("gates") or {}
        role_p = {
            "FIN": bool(g.get("G_FIN_1_base_rev_and_apac_contra") and g.get("G_FIN_2_stress_min_dscr_ge_1_54") and g.get("G_FIN_3_stress_min_cash_ge_650") and g.get("G_FIN_4_narrow_pareto_noi_margin_48_0_to_50_4")),
            "OPS": bool(g.get("G_OPS_1_strict_p95_latency_le_25_5ms") and g.get("G_OPS_2_failover_redundancy_ge_22pct") and g.get("G_OPS_3_ops_budget_cap_le_1280") and g.get("G_OPS_4_global_map_svg_and_png")),
            "SALES": bool(g.get("G_SALES_1_weighted_pipeline_ge_3650") and g.get("G_SALES_2_strict_nrr_ge_114_8") and g.get("G_SALES_3_ecosystem_real_web_anchors")),
            "EXEC": bool(canary and g.get("G_EXEC_4_three_sun_cycles_photometry")),
        }
    elif task_id == "UA-06":
        drc = eval_ua06_drc(workspace, sport=int(meta["staging_port"]))
        g = drc.get("gates") or {}
        filed = {str(x.get("bug_code") or "").upper() for x in (portal_state.get("qa_issues") or []) if str(x.get("bug_code") or "").strip()}
        real_5 = {"BUG-ANNUAL-SURCHARGE", "BUG-ENT-SLA-ZERO", "BUG-TZ-PST8", "BUG-CSRF-SAMESITE", "BUG-BRAND-VIEWBOX"}
        false_cnt = sum(1 for c in filed if c not in real_5)
        head_sha = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=workspace / "nexus-portal", capture_output=True, text=True).stdout.strip()
        so = portal_state.get("qa_signoff") or {}
        canary = bool(drc.get("all_gates_passed") and real_5.issubset(filed) and false_cnt == 0 and so.get("release_token") == "NEXUS-V5-GA" and so.get("git_commit") == head_sha)
        role_p = {
            "FE": bool(g.get("G_FE_1_eight_routes_upgraded") and g.get("G_FE_2_five_seeded_bugs_remediated") and g.get("G_FE_3_coupled_page_p95_le_155ms")),
            "DESIGN": bool(g.get("G_DES_1_three_cycles_renders_framed") and g.get("G_DES_2_gimp_cards_and_inkscape_badges") and g.get("G_DES_3_coupled_asset_payload_le_1150kb") and g.get("G_DES_4_turntable_144f_motion_mp4")),
            "CMS": bool(g.get("G_CMS_1_16_articles_published_with_valid_assets") and g.get("G_CMS_2_real_external_web_facts_verified")),
            "QA": canary,
        }
    elif task_id == "UA-07":
        drc = eval_ua07_drc(workspace, burst_mult=1.5)
        g = drc.get("gates") or {}
        poll = int(side.get("observation_pollutions", 0))
        sps = portal_state.get("statuspage_posts") or []
        canary = bool(drc.get("all_gates_passed") and poll == 0 and bool(sps) and sps[-1].get("incident_token") == "WARROOM-9901")
        role_p = {
            "DB": bool(g.get("G_DB_1_dual_composite_indexes_and_batch") and g.get("G_DB_2_forensics_30s_captured") and poll == 0),
            "APP": bool(g.get("G_APP_1_gateway_backoff_and_token_bucket") and g.get("G_MEM_coupled_ram_cap_le_640mb_no_oom")),
            "INFRA": bool(g.get("G_INF_1_daemon_probe_and_disk_clean") and g.get("G_INF_2_qgis_edge_severed_zero_and_util_le_76pct") and g.get("G_INF_3_edge_rtt_le_52ms_and_cost_le_46k") and g.get("G_INF_4_qgis_project_and_map_pdf") and g.get("G_INF_5_cooling_valve_72angle_and_exclusive_cae")),
            "IC": canary,
        }
    elif task_id == "UA-02":
        drc = eval_ua02_drc(workspace)
        g = drc.get("gates") or {}
        filed = {str(x.get("bug_code") or "").upper() for x in (portal_state.get("qa_issues") or []) if str(x.get("bug_code") or "").strip()}
        real_5 = {"BUG-ANNUAL-SURCHARGE", "BUG-ENT-SLA-ZERO", "BUG-TZ-PST8", "BUG-CSRF-SAMESITE", "BUG-BRAND-VIEWBOX"}
        false_cnt = sum(1 for c in filed if c not in real_5)
        head_sha = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=workspace / "nexus-portal", capture_output=True, text=True).stdout.strip()
        so = portal_state.get("qa_signoff") or {}
        canary = bool(drc.get("all_gates_passed") and real_5.issubset(filed) and false_cnt == 0 and so.get("release_token") == "NEXUS-V5-GA" and so.get("git_commit") == head_sha)
        role_p = {
            "FE": bool(g.get("G_FE_1_eight_routes_upgraded") and g.get("G_FE_2_five_seeded_bugs_remediated") and g.get("G_FE_3_coupled_page_p95_le_155ms")),
            "DESIGN": bool(g.get("G_DES_1_three_cycles_renders_framed") and g.get("G_DES_2_gimp_cards_and_inkscape_badges") and g.get("G_DES_3_coupled_asset_payload_le_1150kb")),
            "CMS": bool(g.get("G_CMS_1_16_articles_published_with_valid_assets") and g.get("G_CMS_2_real_external_web_facts_verified")),
            "QA": canary,
        }
    elif task_id == "UA-03":
        drc = eval_ua03_drc(workspace, burst_mult=1.5)
        g = drc.get("gates") or {}
        poll = int(side.get("observation_pollutions", 0))
        sps = portal_state.get("statuspage_posts") or []
        canary = bool(drc.get("all_gates_passed") and poll == 0 and bool(sps) and sps[-1].get("incident_token") == "WARROOM-9901")
        role_p = {
            "DB": bool(g.get("G_DB_1_dual_composite_indexes_and_batch") and g.get("G_DB_2_forensics_30s_captured") and poll == 0),
            "APP": bool(g.get("G_APP_1_gateway_backoff_and_token_bucket") and g.get("G_MEM_coupled_ram_cap_le_640mb_no_oom")),
            "INFRA": bool(g.get("G_INF_1_daemon_probe_and_disk_clean") and g.get("G_INF_2_qgis_edge_severed_zero_and_util_le_76pct") and g.get("G_INF_3_edge_rtt_le_52ms_and_cost_le_46k") and g.get("G_INF_4_qgis_project_and_map_pdf")),
            "IC": canary,
        }
    else:
        drc = eval_ua04_cae_and_drc(workspace)
        g = drc.get("gates") or {}
        fc_sha = sha256_file(workspace / "aero_actuator.FCStd")
        cert_p = workspace / "exports/cae_cert.json"
        cert = json.loads(cert_p.read_text(encoding="utf-8")) if cert_p.is_file() else {}
        pubs = portal_state.get("media_pubs") or []
        last_pub = pubs[-1] if pubs else {}
        canary = bool(
            drc.get("all_gates_passed")
            and cert.get("cad_cae_passed") is True
            and cert.get("fcstd_sha256") == fc_sha
            and last_pub.get("release_token") == "AERO-ACT-2026"
            and last_pub.get("fcstd_sha256") == fc_sha
            and int(side.get("premature_media_uploads", 0)) == 0
        )
        role_p = {
            "CAD_HOUSING": bool(g.get("G_CAD_1_zero_interference_and_radial_gap_016_025") and g.get("G_CAD_2_coupled_mass_cap_le_1_180kg") and (workspace / "exports/housing_assy.step").is_file()),
            "CAD_ROTOR": bool(g.get("G_CAD_1_zero_interference_and_radial_gap_016_025") and g.get("G_CAE_1_torsional_safety_factor_ge_2_05") and (workspace / "exports/rotor_assy.step").is_file()),
            "CAE_LIT": bool(g.get("G_LIT_1_bom_formulas_match_final_cad_mass") and g.get("G_LIT_2_real_web_literature_anchors_and_pdf") and cert.get("cad_cae_passed") is True),
            "MEDIA_PUB": canary,
        }

    gates_dict = drc.get("gates") or {}
    rub_score = round(sum(1 for v in gates_dict.values() if v) / max(1, len(gates_dict)), 4)
    ms_score = round(sum(1 for v in role_p.values() if v) / max(1, len(role_p)), 4)
    return {
        "task_id": task_id,
        "arena": meta["arena"],
        "roles": list(meta["roles"]),
        "role_passes": role_p,
        "passed_roles_count": sum(1 for v in role_p.values() if v),
        "joint_pass": bool(all(role_p.values()) and canary),
        "canary_passed": canary,
        "milestone_score": ms_score,
        "final_rubric_score": rub_score,
        "gates": gates_dict,
        "drc_calls_count": int(portal_state.get("drc_calls", 0)),
        "efficiency": {
            "critical_section_lower_bound_s": lb_s,
            "actual_wall_s": round(eff_wall, 2),
            "efficiency_score": eff_score,
            "effective_throughput_score": round(rub_score * eff_score, 4),
        },
        "collateral_side_effects": side,
        "diagnostics": drc.get("metrics") or {},
    }


def _post_json(url: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def solve_ultra_reference(task_id: str, workspace: Path) -> None:
    """Deterministic cooperative reference solution verifying mathematical & software feasibility of all gates."""
    if task_id in EXTREME_IDS:
        solve_extreme_ref(task_id, workspace)
        return
    if task_id in FLAGSHIP_IDS:
        solve_flagship_ref(task_id, workspace)
        return
    meta = UA_BY_ID[task_id]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"

    if task_id == "UA-01":
        xlsx_p = workspace / "Q3_Enterprise_Model.xlsx"
        # Finance_12M: clean Q3 USD Excl-IC rows + -120 APAC contra + hedge=0.85, reserve=780, debt_service_q=840
        fin_units = [row for pg in UA01_BI_PAGES["FIN"] for row in pg]
        fin_rows = [["unit_id", "net_rev_kusd", "direct_cost_kusd", "notes", "param_key", "param_val"]]
        for idx, (u_nm, gr, dc, ic) in enumerate(fin_units, start=1):
            pk = "hedge_ratio" if idx == 1 else ("reserve_kusd" if idx == 2 else ("debt_service_q" if idx == 3 else ""))
            pv = 0.88 if idx == 1 else (790.0 if idx == 2 else (830.0 if idx == 3 else ""))
            fin_rows.append([u_nm, round(gr - ic, 2), dc, "Q3_USD_EXCL_IC", pk, pv])
        fin_rows.append(["audit_apac_contra", -120.0, 0.0, "AUDIT_RESTATED", "", ""])
        update_single_sheet_xlsx(xlsx_p, "Finance_12M", fin_rows)

        # Datacenter_16R: active_racks=25 (16*25=400), failover_racks=7 (16*7=112 -> ratio=0.28), pue=1.25 -> spend=(25*1.85+7*1.25)*1.25*16 = 1100.0
        ops_units = [row for pg in UA01_BI_PAGES["OPS"] for row in pg]
        pue_safe = [1.24, 1.22, 1.20, 1.27, 1.23, 1.20, 1.23, 1.18, 1.25, 1.29, 1.26, 1.23, 1.30, 1.27, 1.28, 1.29]
        dc_rows = [["dc_id", "region", "active_racks", "failover_racks", "target_pue", "quarterly_spend_kusd"]]
        for idx, (dc_id, reg, _rk, _pue, _rtt) in enumerate(ops_units, start=1):
            r_num = idx + 1
            tp = pue_safe[idx - 1]
            dc_rows.append([dc_id, reg, 26, 7, tp, (f"=(C{r_num}*1.85+D{r_num}*1.25)*E{r_num}", round((26*1.85+7*1.25)*tp, 2))])
        update_single_sheet_xlsx(xlsx_p, "Datacenter_16R", dc_rows)
        Image.new("RGB", (900, 500), (15, 23, 42)).save(workspace / "exports/dc_footprint_300dpi.png")

        # Pipeline_12T + Ecosystem_Audit
        w_map = {"NA": 0.42, "EMEA": 0.38, "APAC": 0.34, "LATAM": 0.28}
        pm_safe = [1.09, 1.04, 1.02, 1.08, 1.05, 1.07, 1.08, 1.02, 1.04, 1.00, 1.00, 1.10]
        sp_units = [row for pg in UA01_BI_PAGES["SALES"] for row in pg]
        sp_rows = [["territory", "region", "open_arr_kusd", "win_weight", "price_mult", "rebate_pct", "weighted_arr_kusd"]]
        for idx, (tid_s, reg, arr, _acc) in enumerate(sp_units, start=1):
            r_num = idx + 1; wt = w_map[reg]; pm = pm_safe[idx - 1]
            sp_rows.append([tid_s, reg, arr, wt, pm, 0.075, (f"=C{r_num}*D{r_num}*E{r_num}*(1-F{r_num})", round(arr * wt * pm * 0.925, 2))])
        update_single_sheet_xlsx(xlsx_p, "Pipeline_12T", sp_rows)
        update_single_sheet_xlsx(xlsx_p, "Ecosystem_Audit", [
            ["anchor_key", "source_url", "verified_numeric_value", "verified_license_or_note"],
            ["gpt2_vocab_size", "https://huggingface.co/openai-community/gpt2", 50257, "MIT"],
            ["bert_hidden_size", "https://huggingface.co/google-bert/bert-base-uncased", 768, "Apache-2.0"],
            ["transformer_arxiv_year", "https://arxiv.org/abs/1706.03762", 2017, "Vaswani et al."],
            ["gpt3_arxiv_year", "https://arxiv.org/abs/2005.14165", 2020, "Brown et al."],
            ["pep8_max_line_length", "https://peps.python.org/pep-0008/", 79, "Python Style Guide"],
        ])

        # EXEC: Blender 3D bars scaled to NA=1790, EMEA=1390, APAC=1080, LATAM=700
        bl_fix = (
            "import bpy\n"
            f"bpy.ops.wm.open_mainfile(filepath={str(workspace / 'q3_cover_3d.blend')!r})\n"
            "vals = {'Bar_NA': 1.79, 'Bar_EMEA': 1.39, 'Bar_APAC': 1.08, 'Bar_LATAM': 0.70}\n"
            "for nm, h in vals.items():\n"
            "    o = bpy.data.objects[nm]; o.scale = (0.9, 0.9, h); o.location.z = h / 2.0\n"
            "bpy.context.scene.render.filepath = '/workspace/exports/q3_revenue_3d.png'\n"
            "bpy.ops.render.render(write_still=True)\n"
            f"bpy.ops.wm.save_as_mainfile(filepath={str(workspace / 'q3_cover_3d.blend')!r})\n"
        )
        subprocess.run(["blender", "-b", "--python-expr", bl_fix], check=True, capture_output=True, timeout=120)
        png_bytes = (workspace / "exports/q3_revenue_3d.png").read_bytes()
        make_simple_pptx(workspace / "Q3_Board_Deck.pptx", ["QBR-2026-Q3-ULTRA", "NOI & DSCR Verified"], chart_png_bytes=png_bytes)
        Image.open(io.BytesIO(png_bytes)).convert("RGB").save(workspace / "exports/Q3_Board_Briefing.pdf", "PDF")
        _, drc = _post_json(f"{base}/api/drc_audit", {"check_blender": True})
        _post_json(f"{base}/api/mail/send_board", {
            "board_token": "QBR-2026-Q3-ULTRA",
            "noi_kusd": drc["metrics"]["noi_kusd"],
            "worst_dscr": drc["metrics"]["worst_20q_dscr"],
            "model_path": str(xlsx_p),
        })

    elif task_id == "UA-05":
        # Reuse UA-01 cooperative baseline and tune OPS racks=27 -> NOI margin ~ 49.0% inside [48.0, 50.4], P95 ~ 21.1ms <= 25.5ms, NRR ~ 115.0% >= 114.8%, DSCR ~ 2.48 >= 1.54!
        xlsx_p = workspace / "Q3_Enterprise_Model.xlsx"
        fin_units = [row for pg in UA01_BI_PAGES["FIN"] for row in pg]
        fin_rows = [["unit_id", "net_rev_kusd", "direct_cost_kusd", "notes", "param_key", "param_val"]]
        for idx, (u_nm, gr, dc, ic) in enumerate(fin_units, start=1):
            pk = "hedge_ratio" if idx == 1 else ("reserve_kusd" if idx == 2 else ("debt_service_q" if idx == 3 else ""))
            pv = 0.88 if idx == 1 else (790.0 if idx == 2 else (830.0 if idx == 3 else ""))
            fin_rows.append([u_nm, round(gr - ic, 2), dc, "Q3_USD_EXCL_IC", pk, pv])
        fin_rows.append(["audit_apac_contra", -120.0, 0.0, "AUDIT_RESTATED", "", ""])
        update_single_sheet_xlsx(xlsx_p, "Finance_12M", fin_rows)
        ops_units = [row for pg in UA01_BI_PAGES["OPS"] for row in pg]
        pue_safe = [1.24, 1.22, 1.20, 1.27, 1.23, 1.20, 1.23, 1.18, 1.25, 1.29, 1.26, 1.23, 1.30, 1.27, 1.28, 1.29]
        dc_rows = [["dc_id", "region", "active_racks", "failover_racks", "target_pue", "quarterly_spend_kusd"]]
        for idx, (dc_id, reg, _rk, _pue, _rtt) in enumerate(ops_units, start=1):
            r_num = idx + 1; tp = pue_safe[idx - 1]
            dc_rows.append([dc_id, reg, 26, 7, tp, (f"=(C{r_num}*1.85+D{r_num}*1.25)*E{r_num}", round((26*1.85+7*1.25)*tp, 2))])
        update_single_sheet_xlsx(xlsx_p, "Datacenter_16R", dc_rows)
        Image.new("RGB", (900, 500), (15, 23, 42)).save(workspace / "exports/dc_footprint_300dpi.png")
        w_map = {"NA": 0.42, "EMEA": 0.38, "APAC": 0.34, "LATAM": 0.28}
        pm_safe = [1.09, 1.04, 1.02, 1.08, 1.05, 1.07, 1.08, 1.02, 1.04, 1.00, 1.00, 1.10]
        sp_units = [row for pg in UA01_BI_PAGES["SALES"] for row in pg]
        sp_rows = [["territory", "region", "open_arr_kusd", "win_weight", "price_mult", "rebate_pct", "weighted_arr_kusd"]]
        for idx, (tid_s, reg, arr, _acc) in enumerate(sp_units, start=1):
            r_num = idx + 1; wt = w_map[reg]; pm = pm_safe[idx - 1]
            sp_rows.append([tid_s, reg, arr, wt, pm, 0.08, (f"=C{r_num}*D{r_num}*E{r_num}*(1-F{r_num})", round(arr * wt * pm * 0.92, 2))])
        update_single_sheet_xlsx(xlsx_p, "Pipeline_12T", sp_rows)
        update_single_sheet_xlsx(xlsx_p, "Ecosystem_Audit", [
            ["anchor_key", "source_url", "verified_numeric_value", "verified_license_or_note"],
            ["gpt2_vocab_size", "https://huggingface.co/openai-community/gpt2", 50257, "MIT"],
            ["bert_hidden_size", "https://huggingface.co/google-bert/bert-base-uncased", 768, "Apache-2.0"],
            ["transformer_arxiv_year", "https://arxiv.org/abs/1706.03762", 2017, "Vaswani"],
            ["gpt3_arxiv_year", "https://arxiv.org/abs/2005.14165", 2020, "Brown"],
            ["pep8_max_line_length", "https://peps.python.org/pep-0008/", 79, "PEP8"],
        ])
        bl_fix = (
            "import bpy\n"
            f"bpy.ops.wm.open_mainfile(filepath={str(workspace / 'q3_cover_3d.blend')!r})\n"
            "sc = bpy.context.scene; sc.world = bpy.data.worlds.new('W'); sc.world.use_nodes = True\n"
            "sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.25\n"
            "vals = {'Bar_NA': 1.79, 'Bar_EMEA': 1.39, 'Bar_APAC': 1.08, 'Bar_LATAM': 0.70}\n"
            "for nm, h in vals.items():\n"
            "    o = bpy.data.objects[nm]; o.scale = (0.9, 0.9, h); o.location.z = h / 2.0\n"
            "sc.render.filepath = '/workspace/exports/q3_revenue_3d.png'\n"
            "bpy.ops.render.render(write_still=True)\n"
            f"bpy.ops.wm.save_as_mainfile(filepath={str(workspace / 'q3_cover_3d.blend')!r})\n"
        )
        subprocess.run(["blender", "-b", "--python-expr", bl_fix], check=True, capture_output=True, timeout=120)
        png_bytes = (workspace / "exports/q3_revenue_3d.png").read_bytes()
        make_simple_pptx(workspace / "Q3_Board_Deck.pptx", ["QBR-2026-Q3-ULTRA"], chart_png_bytes=png_bytes)
        Image.open(io.BytesIO(png_bytes)).convert("RGB").save(workspace / "exports/Q3_Board_Briefing.pdf", "PDF")
        _, drc = _post_json(f"{base}/api/drc_audit", {})
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q3-ULTRA", "noi_kusd": drc["metrics"]["noi_kusd"], "worst_dscr": drc["metrics"]["worst_20q_dscr"], "model_path": str(xlsx_p)})

    elif task_id == "UA-06":
        sport = int(meta["staging_port"])
        repo = workspace / "nexus-portal"; assets = repo / "static/assets"
        for rt in ("index", "pricing", "docs", "sdk", "integrations", "benchmarks", "security", "changelog", "enterprise", "status", "cli", "community"):
            (repo / f"templates/{rt}.html").write_text(f'<!doctype html><html data-nexus-v5="ready"><body style="background:#0f172a;color:#f8fafc"><h1>{rt}</h1></body></html>\n', encoding="utf-8")
        write_json(repo / "portal_config.json", {"sqlite_pool_size": 12, "annual_discount_pct": 20.0, "enterprise_sla_mult": 1.35, "changelog_tz": "UTC", "csrf_cookie_samesite": True})
        (assets / "brand_mark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48" viewBox="0 0 160 48"><rect width="160" height="48" fill="#0EA5E9"/></svg>\n', encoding="utf-8")
        for fn, wh in (("hero_front.png", (1280, 640)), ("hero_iso.png", (800, 500)), ("hero_detail.png", (800, 500))):
            im = Image.new("RGB", wh, (12, 18, 30)); ImageDraw.Draw(im).rectangle([int(wh[0]*0.2), int(wh[1]*0.2), int(wh[0]*0.8), int(wh[1]*0.8)], fill=(38, 150, 215)); im.save(assets / fn, optimize=True)
        for i in range(1, 5):
            Image.new("RGB", (640, 400), (20, 90, 140)).save(assets / f"feature_card_{i}.png", optimize=True)
            Image.new("RGB", (128, 128), (14, 165, 233)).save(assets / f"badge_{i}.png", optimize=True)
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=s=640x360:r=24:d=6.0",
            "-frames:v", "144", "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p", str(assets / "hero_turntable.mp4"),
        ], check=True, capture_output=True, timeout=60)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Nexus v5 12-route + turntable GA"], cwd=repo, check=True, capture_output=True)
        _post_json(f"http://127.0.0.1:{sport}/api/redeploy", {})
        con = sqlite3.connect(str(workspace / "staging_data/nexus.db"))
        seeds = [
            ("flask", "Flask", "BSD-3-Clause", "3.0", "feature_card_1.png", 1),
            ("requests", "Requests", "Apache-2.0", "2.32", "feature_card_2.png", 1),
            ("sqlalchemy", "SQLAlchemy", "MIT", "2.0", "feature_card_3.png", 1),
            ("gpt2", "GPT-2", "MIT", "50257", "feature_card_4.png", 1),
            ("resnet", "ResNet", "MIT", "2015", "feature_card_1.png", 1),
            ("pep8", "PEP-8", "Python-2.0", "79", "feature_card_2.png", 1),
            ("bert", "BERT", "Apache-2.0", "768", "feature_card_3.png", 1),
            ("pydantic", "Pydantic", "MIT", "2.9", "feature_card_4.png", 1),
        ] + [(f"pkg_{i:02d}", f"Integration {i}", "MIT", str(100+i), f"feature_card_{(i%4)+1}.png", 1) for i in range(9, 25)]
        con.executemany("INSERT OR REPLACE INTO cms_integrations VALUES(?,?,?,?,?,?)", seeds); con.commit(); con.close()
        write_multisheet_xlsx(workspace / "QA_Regression_Matrix.xlsx", [("Matrix", [["Route", "Status"], ["all_12", "PASS"]])])
        Image.new("RGB", (600, 400), (255, 255, 255)).save(workspace / "exports/QA_Release_Report.pdf", "PDF")
        for bc in ("BUG-ANNUAL-SURCHARGE", "BUG-ENT-SLA-ZERO", "BUG-TZ-PST8", "BUG-CSRF-SAMESITE", "BUG-BRAND-VIEWBOX"):
            _post_json(f"{base}/api/qa/report_defect", {"bug_code": bc})
        _post_json(f"{base}/api/drc_audit", {})
        head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        _post_json(f"{base}/api/qa/release_signoff", {"release_token": "NEXUS-V5-GA", "git_commit": head_sha})

    elif task_id == "UA-07":
        cport = int(meta["cluster_port"])
        write_json(workspace / "forensics/db_fingerprint_45s.json", {"sufficient_window_45s": True, "sampled_seconds": 45})
        con = sqlite3.connect(str(workspace / "cluster/prod_ledger.db"))
        con.execute("CREATE INDEX IF NOT EXISTS idx_acct_ts ON ledger_events(account_id, event_ts)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_reg_st ON ledger_events(region_code, status)")
        con.commit(); con.close()
        write_json(workspace / "cluster/db_tuning.json", {"sqlite_cache_mb": 200, "checkpoint_batch": 250})
        write_json(workspace / "cluster/app_gateway.json", {"hot_cache_mb": 235, "retry_backoff_ms": 250, "max_retries": 2, "cache_ttl_s": 180, "singleflight": True, "token_bucket_rps": 1200})
        write_json(workspace / "cluster/infra_daemon.json", {"telemetry_buffer_mb": 110, "log_level": "INFO", "liveness_timeout_ms": 1000})
        (workspace / "cluster/disk_vol/core_trace.bin").write_bytes(b"")
        gcon = sqlite3.connect(str(workspace / "data/edge_network.gpkg"))
        for idx in range(1, 25):
            pid = f"POP_{idx:02d}"
            val = 0.0 if idx in (3, 9, 15, 21) else (21.0 if (idx - 1) % 4 == 1 else 25.285714)
            gcon.execute("UPDATE edge_pops SET assigned_traffic_gbps = ? WHERE pop_id = ?", (val, pid))
        gcon.commit(); gcon.close()
        update_single_sheet_xlsx(workspace / "Capacity_Budget.xlsx", "Allocations", [["Component", "Value"], ["sqlite_cache_mb", 200.0], ["hot_cache_mb", 235.0], ["telemetry_buffer_mb", 110.0], ["arrival_rate_rps", 1200.0], ["target_p99_ms", 48.0]])
        fc_p = workspace / "cooling_valve.FCStd"
        fc_u = (
            "import FreeCAD as App, Part\n"
            f"doc = App.openDocument({str(fc_p)!r})\n"
            "ss = doc.getObject('ValveSpec'); ss.set('B2', '36.0'); ss.set('B3', '35.66'); ss.set('B4', '16.0')\n"
            "doc.getObject('ValveBody').Shape = Part.makeCylinder(24.0, 36.0).cut(Part.makeCylinder(18.0, 36.0))\n"
            "doc.getObject('ValveSpool').Shape = Part.makeCylinder(17.83, 22.0, App.Vector(0,0,7)).cut(Part.makeCylinder(9.0, 22.0, App.Vector(0,0,7)))\n"
            "doc.recompute()\n"
            f"doc.saveAs({str(fc_p)!r})\n"
        )
        subprocess.run(["freecadcmd", "-c", fc_u], check=True, capture_output=True, timeout=60)
        code, vr = _post_json(f"{base}/api/cae/valve_solve", {})
        assert code == 200 and vr["certificate"]["valve_passed"] is True, vr
        Image.new("RGB", (800, 500), (20, 30, 48)).save(workspace / "exports/edge_reroute_map.pdf", "PDF")
        Image.new("RGB", (800, 500), (255, 255, 255)).save(workspace / "exports/INC_Postmortem_RCA.pdf", "PDF")
        _, burst = _post_json(f"http://127.0.0.1:{cport}/api/canary_burst", {})
        _post_json(f"{base}/api/statuspage/resolve", {"incident_token": "WARROOM-9901", "canary_p99_ms": burst["metrics"]["p99_ms"]})

    elif task_id == "UA-02":
        sport = int(meta["staging_port"])
        repo = workspace / "nexus-portal"
        assets = repo / "static/assets"
        for rt in ("index", "pricing", "docs", "sdk", "integrations", "benchmarks", "security", "changelog"):
            (repo / f"templates/{rt}.html").write_text(f'<!doctype html><html data-nexus-v5="ready"><body><img src="/static/assets/brand_mark.svg"/><h1>{rt}</h1></body></html>\n', encoding="utf-8")
        write_json(repo / "portal_config.json", {
            "sqlite_pool_size": 12,
            "annual_discount_pct": 20.0,
            "enterprise_sla_mult": 1.35,
            "changelog_tz": "UTC",
            "csrf_cookie_samesite": True,
        })
        (assets / "brand_mark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48" viewBox="0 0 160 48"><rect width="160" height="48" fill="#0EA5E9"/></svg>\n', encoding="utf-8")
        for fn, wh in (("hero_front.png", (1280, 640)), ("hero_iso.png", (800, 500)), ("hero_detail.png", (800, 500))):
            im = Image.new("RGB", wh, (12, 18, 30)); dr = ImageDraw.Draw(im)
            dr.rectangle([int(wh[0]*0.2), int(wh[1]*0.2), int(wh[0]*0.8), int(wh[1]*0.8)], fill=(38, 150, 215))
            im.save(assets / fn, optimize=True)
        for i in range(1, 5):
            Image.new("RGB", (640, 400), (20, 90, 140)).save(assets / f"feature_card_{i}.png", optimize=True)
            Image.new("RGB", (128, 128), (14, 165, 233)).save(assets / f"badge_{i}.png", optimize=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Nexus v5 GA launch"], cwd=repo, check=True, capture_output=True)
        _post_json(f"http://127.0.0.1:{sport}/api/redeploy", {})

        con = sqlite3.connect(str(workspace / "staging_data/nexus.db"))
        seeds = [
            ("flask", "Flask WSGI", "BSD-3-Clause", "3.0", "feature_card_1.png", 1),
            ("requests", "Requests HTTP", "Apache-2.0", "2.32", "feature_card_2.png", 1),
            ("sqlalchemy", "SQLAlchemy ORM", "MIT", "2.0", "feature_card_3.png", 1),
            ("gpt2", "GPT-2 Tokenizer", "MIT", "50257", "feature_card_4.png", 1),
            ("resnet", "ResNet Vision", "MIT", "2015", "feature_card_1.png", 1),
            ("pep8", "PEP-8 Lint", "Python-2.0", "79", "feature_card_2.png", 1),
        ] + [(f"pkg_{i:02d}", f"Integration {i}", "MIT", str(100 + i), f"feature_card_{(i%4)+1}.png", 1) for i in range(7, 17)]
        con.executemany("INSERT OR REPLACE INTO cms_integrations VALUES(?,?,?,?,?,?)", seeds)
        con.commit(); con.close()

        write_multisheet_xlsx(workspace / "QA_Regression_Matrix.xlsx", [("Matrix", [["Route", "Status"], ["all_8", "PASS"]])])
        Image.new("RGB", (600, 400), (255, 255, 255)).save(workspace / "exports/QA_Release_Report.pdf", "PDF")
        for bc in ("BUG-ANNUAL-SURCHARGE", "BUG-ENT-SLA-ZERO", "BUG-TZ-PST8", "BUG-CSRF-SAMESITE", "BUG-BRAND-VIEWBOX"):
            _post_json(f"{base}/api/qa/report_defect", {"bug_code": bc})
        _post_json(f"{base}/api/drc_audit", {})
        head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        _post_json(f"{base}/api/qa/release_signoff", {"release_token": "NEXUS-V5-GA", "git_commit": head_sha})

    elif task_id == "UA-03":
        cport = int(meta["cluster_port"])
        write_json(workspace / "forensics/db_fingerprint_30s.json", {"sufficient_window_25s": True, "sampled_seconds": 30})
        con = sqlite3.connect(str(workspace / "cluster/prod_ledger.db"))
        con.execute("CREATE INDEX IF NOT EXISTS idx_acct_ts ON ledger_events(account_id, event_ts)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_reg_st ON ledger_events(region_code, status)")
        con.commit(); con.close()
        write_json(workspace / "cluster/db_tuning.json", {"sqlite_cache_mb": 220, "checkpoint_batch": 250})
        write_json(workspace / "cluster/app_gateway.json", {"hot_cache_mb": 260, "retry_backoff_ms": 250, "max_retries": 2, "cache_ttl_s": 180, "singleflight": True, "token_bucket_rps": 1200})
        write_json(workspace / "cluster/infra_daemon.json", {"telemetry_buffer_mb": 120, "log_level": "INFO", "liveness_timeout_ms": 1000})
        (workspace / "cluster/disk_vol/core_trace.bin").write_bytes(b"")
        gcon = sqlite3.connect(str(workspace / "data/edge_network.gpkg"))
        for idx in range(1, 25):
            pid = f"POP_{idx:02d}"
            if idx in (3, 9, 15, 21):
                val = 0.0
            elif (idx - 1) % 4 == 1:
                val = 21.0
            else:
                val = 25.285714
            gcon.execute("UPDATE edge_pops SET assigned_traffic_gbps = ? WHERE pop_id = ?", (val, pid))
        gcon.commit(); gcon.close()
        update_single_sheet_xlsx(workspace / "Capacity_Budget.xlsx", "Allocations", [
            ["Component", "Value"], ["sqlite_cache_mb", 220.0], ["hot_cache_mb", 260.0], ["telemetry_buffer_mb", 120.0], ["arrival_rate_rps", 1200.0], ["target_p99_ms", 46.0],
        ])
        Image.new("RGB", (800, 500), (20, 30, 48)).save(workspace / "exports/edge_reroute_map.pdf", "PDF")
        Image.new("RGB", (800, 500), (255, 255, 255)).save(workspace / "exports/INC_Postmortem_RCA.pdf", "PDF")
        _, burst = _post_json(f"http://127.0.0.1:{cport}/api/canary_burst", {})
        _post_json(f"{base}/api/statuspage/resolve", {"incident_token": "WARROOM-9901", "canary_p99_ms": burst["metrics"]["p99_ms"]})

    else:
        fc_p = workspace / "aero_actuator.FCStd"
        fc_upd = textwrap.dedent(f"""\
            import FreeCAD as App, Part
            doc = App.openDocument({str(fc_p)!r})
            ss = doc.getObject("MasterSpec")
            ss.set("B2", "90.0"); ss.set("B3", "89.60"); ss.set("B4", "3.6"); ss.set("B5", "11.5")
            h = doc.getObject("Housing"); h.Shape = Part.makeCylinder(51.0, 26.0).cut(Part.makeCylinder(45.0, 26.0))
            f = doc.getObject("Flexspline"); f.Shape = Part.makeCylinder(44.80, 22.0, App.Vector(0,0,2)).cut(Part.makeCylinder(41.20, 22.0, App.Vector(0,0,2)))
            r = doc.getObject("RotorWave"); r.Shape = Part.makeCylinder(40.80, 18.0, App.Vector(0,0,4)).cut(Part.makeCylinder(18.0, 18.0, App.Vector(0,0,4)))
            c = doc.getObject("TopCover"); c.Shape = Part.makeCylinder(51.0, 11.5, App.Vector(0,0,26.2)).cut(Part.makeCylinder(22.0, 11.5, App.Vector(0,0,26.2)))
            doc.recompute()
            h.Shape.exportStep({str(workspace / "exports/housing_assy.step")!r})
            r.Shape.exportStep({str(workspace / "exports/rotor_assy.step")!r})
            doc.saveAs({str(fc_p)!r})
        """)
        subprocess.run(["freecadcmd", "-c", fc_upd], check=True, capture_output=True, timeout=90)
        code, cert_res = _post_json(f"{base}/api/cae/exclusive_solve", {"review_token": "AERO-ACT-2026"})
        assert code == 200, cert_res
        pc = cert_res["certificate"]["metrics"]["part_cm3"]
        bom_p = workspace / "Engineering_Master_BOM.xlsx"
        update_single_sheet_xlsx(bom_p, "Parts", [["Part", "Volume_cm3"], ["Housing", pc["h_cm3"]], ["Flexspline", pc["f_cm3"]], ["RotorWave", pc["r_cm3"]], ["TopCover", pc["c_cm3"]]])
        update_single_sheet_xlsx(bom_p, "Literature", [["Key", "Numeric_Anchor"], ["ti6al4v_density_g_cm3", 4.43], ["arxiv_1706_03762_year", 2017], ["arxiv_1512_03385_year", 2015], ["arxiv_2005_14165_year", 2020]])
        Image.new("RGB", (800, 600), (255, 255, 255)).save(workspace / "exports/Engineering_Whitepaper.pdf", "PDF")
        Image.new("RGB", (1280, 720), (18, 28, 46)).save(workspace / "exports/cutaway_beauty.png")
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", "15.0", "-r", "24", "-i", str(workspace / "exports/cutaway_beauty.png"),
            "-i", str(workspace / "raw/narration_raw.wav"),
            "-filter_complex", "[1:a]loudnorm=I=-23.0:TP=-2.0:LRA=7.0[aout]",
            "-map", "0:v", "-map", "[aout]", "-frames:v", "360", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(workspace / "exports/actuator_launch_720p.mp4"),
        ], check=True, capture_output=True, timeout=90)
        _post_json(f"{base}/api/media/publish", {"release_token": "AERO-ACT-2026", "mp4_path": "/workspace/exports/actuator_launch_720p.mp4"})


def simulate_ultra_race(task_id: str, workspace: Path) -> None:
    if task_id in EXTREME_IDS:
        sim_extreme_race(task_id, workspace)
        return
    if task_id in FLAGSHIP_IDS:
        sim_flagship_race(task_id, workspace)
        return
    meta = UA_BY_ID[task_id]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"
    if task_id == "UA-01":
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q3-ULTRA", "noi_kusd": 100.0, "worst_dscr": 0.9, "model_path": str(workspace / "Q3_Enterprise_Model.xlsx")})
    elif task_id == "UA-05":
        # Premature board email before sheets converge
        _post_json(f"{base}/api/mail/send_board", {"board_token": "QBR-2026-Q3-ULTRA", "noi_kusd": 100.0, "worst_dscr": 0.9, "model_path": str(workspace / "Q3_Enterprise_Model.xlsx")})
        update_single_sheet_xlsx(workspace / "Q3_Enterprise_Model.xlsx", "Ecosystem_Audit", [["k", "u", "v", "n"], ["a", "", 50257, ""]])
    elif task_id in ("UA-02", "UA-06"):
        _post_json(f"{base}/api/qa/report_defect", {"bug_code": "FALSE-WIP-CMS-EMPTY"})
    elif task_id in ("UA-03", "UA-07"):
        cport = int(meta["cluster_port"])
        _post_json(f"http://127.0.0.1:{cport}/api/restart", {"mode": "hard"})
    else:
        _post_json(f"{base}/api/media/publish", {"release_token": "AERO-ACT-2026", "mp4_path": "/workspace/missing.mp4"})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b_p = sub.add_parser("build"); b_p.add_argument("--task", required=True); b_p.add_argument("--workspace", type=Path, required=True); b_p.add_argument("--tickets-root", type=Path, required=True)
    g_p = sub.add_parser("grade"); g_p.add_argument("--task", required=True); g_p.add_argument("--workspace", type=Path, required=True); g_p.add_argument("--portal-state", type=Path, required=True); g_p.add_argument("--wall-seconds", type=float, default=1800.0); g_p.add_argument("--out", type=Path, required=True)
    s_p = sub.add_parser("solve_ref"); s_p.add_argument("--task", required=True); s_p.add_argument("--workspace", type=Path, required=True)
    r_p = sub.add_parser("sim_race"); r_p.add_argument("--task", required=True); r_p.add_argument("--workspace", type=Path, required=True)
    args = p.parse_args(argv)
    if args.cmd == "build":
        build_ultra_case(args.task, args.workspace, args.tickets_root)
    elif args.cmd == "grade":
        ps = json.loads(args.portal_state.read_text(encoding="utf-8")) if args.portal_state.is_file() else {}
        write_json(args.out, grade_ultra_case(args.task, args.workspace, ps, args.wall_seconds))
    elif args.cmd == "solve_ref":
        solve_ultra_reference(args.task, args.workspace)
    elif args.cmd == "sim_race":
        simulate_ultra_race(args.task, args.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

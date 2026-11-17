"""Workspace builders, 4-dimensional graders, reference solvers, and self-validation for TA-A1..TA-E1."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
import time
import urllib.request
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from tasks.thematic_arenas_v1.catalog import TA_BY_ID, THEMATIC_ARENAS_CATALOG
from tasks.thematic_arenas_v1.services import QBR_CRM_TRUTH, QBR_FIN_TRUTH, QBR_OPS_TRUTH
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def make_simple_pptx(path: Path, slide_lines: list[str], chart_png_bytes: bytes | None = None) -> None:
    """Write a valid OOXML PowerPoint (.pptx) deck with slide text and optional embedded PNG image."""
    from xml.sax.saxutils import escape
    path.parent.mkdir(parents=True, exist_ok=True)
    ct_png = '<Default Extension="png" ContentType="image/png"/>' if chart_png_bytes else ''
    ct_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        f'<Default Extension="xml" ContentType="application/xml"/>{ct_png}'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        '</Types>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '</Relationships>'
    )
    pres_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>'
    )
    pres_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
        '</Relationships>'
    )
    paras = "".join(f"<a:p><a:r><a:t>{escape(ln)}</a:t></a:r></a:p>" for ln in slide_lines)
    slide_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        f'<p:cSld><p:spTree><p:sp><p:txBody><a:bodyPr/><a:lstStyle/>{paras}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("ppt/presentation.xml", pres_xml)
        zf.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
        zf.writestr("ppt/slides/slide1.xml", slide_xml)
        if chart_png_bytes:
            zf.writestr("ppt/media/image1.png", chart_png_bytes)


def read_pptx_info(path: Path) -> tuple[str, bool]:
    if not path.is_file():
        return "", False
    try:
        import xml.etree.ElementTree as ET
        with ZipFile(path, "r") as zf:
            has_img = any(nm.startswith("ppt/media/") and nm.endswith(".png") and len(zf.read(nm)) > 500 for nm in zf.namelist())
            slides = [nm for nm in zf.namelist() if nm.startswith("ppt/slides/slide") and nm.endswith(".xml")]
            txts = []
            for s in sorted(slides):
                root = ET.fromstring(zf.read(s))
                txts.extend(t.strip() for t in root.itertext() if t and t.strip())
        return "\n".join(txts), has_img
    except Exception:
        return "", False


def build_arena_a(task_id: str, workspace: Path, tickets: dict[str, Path]) -> None:
    meta = TA_BY_ID[task_id]
    port = meta["portal_port"]
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    summary_rows = [
        ["Metric", "Value_kUSD", "Notes"],
        ["Total_Net_Revenue_kUSD", ("=SUM(Revenue_Cost!B2:B14)", 0.0), "Cross-sheet formula (DO NOT OVERWRITE WITH LITERAL)"],
        ["Total_Direct_Cost_kUSD", ("=SUM(Revenue_Cost!C2:C14)", 0.0), "Cross-sheet formula"],
        ["Total_Ops_Fulfillment_kUSD", ("=SUM(Ops_KPI!D2:D11)", 0.0), "Cross-sheet formula"],
        ["Net_Operating_Income_kUSD", ("=B2-B3-B4", 0.0), "Canary operating income formula"],
        ["Weighted_Sales_Pipeline_kUSD", ("=SUM(Sales_Pipeline!E2:E9)", 0.0), "Cross-sheet formula"],
    ]
    rev_rows = [["table_id", "net_revenue_kusd", "direct_cost_kusd", "segment"]] + [[f"fin_m{i:02d}", 0.0, 0.0, "PENDING"] for i in range(1, 13)] + [["audit_apac_contra", 0.0, 0.0, "AUDIT_ADJUSTMENT"]]
    ops_rows = [["table_id", "warehouse_cost_kusd", "lastmile_cost_kusd", "total_fulfillment_kusd", "sla_pct"]] + [[f"ops_w{i:02d}", 0.0, 0.0, 0.0, 0.0] for i in range(1, 11)]
    crm_rows = [["table_id", "region", "raw_pipeline_usd", "win_rate_weight", "weighted_kusd"]] + [[f"crm_r{i:02d}", "PENDING", 0.0, 0.0, 0.0] for i in range(1, 9)]
    write_multisheet_xlsx(
        workspace / "Q3_Operating_Model.xlsx",
        [("Summary", summary_rows), ("Revenue_Cost", rev_rows), ("Ops_KPI", ops_rows), ("Sales_Pipeline", crm_rows)],
    )
    make_simple_pptx(workspace / "Q3_Executive_Deck.pptx", ["Q3 Executive Operating Review — TEMPLATE (UNPOPULATED)"])

    tickets["FIN"].write_text(textwrap.dedent(f"""\
        # Role FIN — Quarterly Finance Consolidation ({task_id})
        Shared desktop BI/CRM Portal: open in Chromium on `DISPLAY=:99` (`http://127.0.0.1:{port}`).
        Shared deliverable workbook: `/workspace/Q3_Operating_Model.xlsx` (`Summary`, `Revenue_Cost`, `Ops_KPI`, `Sales_Pipeline`).

        1. Inspect the Chromium `<canvas>` specification card on `DISPLAY=:99` to read:
           - Canonical BI filter (`quarter`, `currency`, `exclude_ic`), and
           - Any **AUDIT RESTATEMENT CANARY** for `APAC RETURN CONTRA` (`0.0` or negative kUSD adjustment).
        2. Set the BI filter via `POST http://127.0.0.1:{port}/api/bi/set_filter` (`{{"quarter":"Q3","currency":"USD","exclude_ic":true,"actor":"FIN"}}`) — note SSO may expire (`401`, refresh via `/api/sso/relogin` and re-set filter!) and other tasks share the same BI filter & `/home/gui/Downloads/bi_report_export.csv`!
        3. Export all 12 finance tables (`fin_m01` .. `fin_m12`) via `POST http://127.0.0.1:{port}/api/bi/export_table` (`{{"table_id": ...}}`), verifying each exported CSV indeed has `quarter=Q3` and `currency=USD`.
        4. Populate rows 2..13 of sheet `Revenue_Cost` (`[table_id, net_revenue_kusd, direct_cost_kusd, segment]`) and row 14 `["audit_apac_contra", <contra_kusd>, 0.0, "AUDIT_ADJUSTMENT"]` inside `/workspace/Q3_Operating_Model.xlsx` **without clobbering `Ops_KPI`, `Sales_Pipeline`, or the live formulas in `Summary`**!
        5. Write `/workspace/exports/fin_reconciliation.json` with `{{"total_net_revenue_kusd": <float>, "total_direct_cost_kusd": <float>}}`.
    """), encoding="utf-8")

    tickets["OPS"].write_text(textwrap.dedent(f"""\
        # Role OPS — Fulfillment & Warehouse Operations Review ({task_id})
        Shared BI Portal: `http://127.0.0.1:{port}` (open on `DISPLAY=:99`). Shared workbook: `/workspace/Q3_Operating_Model.xlsx`.

        1. Verify canonical BI filter (`quarter="Q3"`, `currency="USD"`, `exclude_ic=true`) from `<canvas>` / `/api/bi/set_filter` (`actor="OPS"`). Handle SSO TTL expiry if `401` occurs, and beware `/home/gui/Downloads/bi_report_export.csv` is shared across concurrent exports.
        2. Export all 10 operations reports (`ops_w01` .. `ops_w10`) via `POST http://127.0.0.1:{port}/api/bi/export_table`, verifying `quarter=Q3` and `currency=USD` on every row.
        3. Update ONLY sheet `Ops_KPI` rows 2..11 (`[table_id, warehouse_cost_kusd, lastmile_cost_kusd, total_fulfillment_kusd, sla_pct]`, where `total_fulfillment_kusd = warehouse_cost_kusd + lastmile_cost_kusd`) in `/workspace/Q3_Operating_Model.xlsx`, preserving all peer sheets and `Summary` live formulas!
        4. Render `/workspace/exports/ops_sla_chart.png` (>= 640x360 PNG bar/line chart of the 10 warehouse fulfillment costs & SLA).
    """), encoding="utf-8")

    tickets["SALES"].write_text(textwrap.dedent(f"""\
        # Role SALES — Regional Pipeline & Conversion Forecast ({task_id})
        Shared BI/CRM Portal: `http://127.0.0.1:{port}` (`DISPLAY=:99`). Shared workbook: `/workspace/Q3_Operating_Model.xlsx`.

        1. Take a GUI screenshot of Chromium on `DISPLAY=:99` to read from the `<canvas>` card:
           - Regional win-rate weights (`NA`, `EMEA`, `APAC`, `LATAM`), and
           - Whether `EMEA` open pipeline is denominated in `EUR` requiring an `EUR->USD` audit FX multiplier!
        2. Ensure BI filter has `quarter="Q3"` (`actor="SALES"`) and export all 8 CRM territories (`crm_r01` .. `crm_r08`) via `/api/bi/export_table`, checking `quarter=Q3` in each downloaded CSV.
        3. Convert raw pipeline to USD (`raw_usd = open_pipeline_raw * fx_if_eur`), multiply by the region win-rate weight (`weighted_kusd = round(raw_usd * weight, 2)`), and update ONLY sheet `Sales_Pipeline` rows 2..9 in `/workspace/Q3_Operating_Model.xlsx` without overwriting peer sheets or `Summary` formulas.
        4. Write regional analysis summary `/workspace/exports/regional_commentary.md` listing all 4 regional weighted subtotals and the grand total.
    """), encoding="utf-8")

    tickets["EXEC"].write_text(textwrap.dedent(f"""\
        # Role EXEC — Executive Board Deck, Clipboard Chart & Final Dispatch ({task_id})
        Shared Portal: `http://127.0.0.1:{port}` (`DISPLAY=:99`). Shared deliverables: `/workspace/Q3_Operating_Model.xlsx` and `/workspace/Q3_Executive_Deck.pptx`.

        1. Read the exact `BOARD SIGN-OFF CODE` from the Chromium `<canvas>` card on `DISPLAY=:99`.
        2. Wait and verify that `FIN` (`Revenue_Cost`), `OPS` (`Ops_KPI` + `/workspace/exports/ops_sla_chart.png`), and `SALES` (`Sales_Pipeline`) have all finished populating `/workspace/Q3_Operating_Model.xlsx` and stabilized (no zero/PENDING rows, and `Summary` formulas `B2..B6` intact!).
        3. Copy `/workspace/exports/ops_sla_chart.png` through the live X11 clipboard (`xclip -selection clipboard -t image/png -i /workspace/exports/ops_sla_chart.png >/dev/null 2>&1` and read back via `xclip -selection clipboard -t image/png -o`), embed that PNG image (`ppt/media/image1.png`) and exact `BOARD SIGN-OFF CODE` + `Summary` figures into `/workspace/Q3_Executive_Deck.pptx`, and export `/workspace/exports/Q3_Executive_Deck.pdf` (e.g. via Pillow/Matplotlib PDF export).
        4. Dispatch the final executive briefing via `POST http://127.0.0.1:{port}/api/mail/send_exec` with JSON `{{"board_code": "...", "subject": "Q3 Operating Review", "net_operating_income_kusd": <float>, "total_ops_cost_kusd": <float>, "weighted_pipeline_kusd": <float>, "model_path": "/workspace/Q3_Operating_Model.xlsx", "deck_path": "/workspace/Q3_Executive_Deck.pptx"}}` AFTER the workbook and deck are completely finalized.
    """), encoding="utf-8")


def build_arena_b(task_id: str, workspace: Path, tickets: dict[str, Path]) -> None:
    meta = TA_BY_ID[task_id]
    pport = meta["portal_port"]
    sport = meta["staging_port"]
    is_branch_race = bool(meta.get("branch_schema_race"))
    repo = workspace / "launch-repo"
    (repo / "templates").mkdir(parents=True, exist_ok=True)
    (repo / "static/assets").mkdir(parents=True, exist_ok=True)
    (repo / "tools").mkdir(parents=True, exist_ok=True)
    (workspace / "staging_data").mkdir(parents=True, exist_ok=True)

    for pg in ("index", "pricing", "features", "enterprise", "changelog"):
        (repo / f"templates/{pg}.html").write_text(
            f"<!doctype html><html><body><h1>{pg.upper()} DRAFT v0</h1><p>Placeholder pre-launch copy.</p></body></html>\n",
            encoding="utf-8",
        )
    write_json(repo / "app_logic.json", {
        "annual_multiplier": 1.20,
        "changelog_timezone": "-07:00",
        "checkout_tax_bps": 0,
    })
    (repo / "static/assets/nav_logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" viewBox="0 0 40 40">'
        '<rect x="2" y="4" width="116" height="32" fill="#0EA5E9"/></svg>\n',
        encoding="utf-8",
    )
    write_json(repo / "tools/asset_export_settings.json", {
        "dpi": 72,
        "hero_size": [800, 400],
        "card_size": [320, 200],
        "accent_rgb": [100, 116, 139],
    })
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "LaunchBot"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "launch@local"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial pre-launch v0 with seeded canary defects"], cwd=repo, check=True, capture_output=True)

    if is_branch_race:
        subprocess.run(["git", "checkout", "-b", "hotfix/checkout-tax"], cwd=repo, check=True, capture_output=True)
        write_json(repo / "app_logic.json", {
            "annual_multiplier": 1.20,
            "changelog_timezone": "-07:00",
            "checkout_tax_bps": 825,
        })
        subprocess.run(["git", "commit", "-am", "Hotfix: set checkout_tax_bps=825"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    cms_db = workspace / "staging_data/cms.db"
    con = sqlite3.connect(str(cms_db))
    if is_branch_race:
        con.execute("CREATE TABLE registered_assets(asset_file TEXT PRIMARY KEY, width INTEGER, height INTEGER)")
        con.execute("CREATE TABLE cms_articles(article_id TEXT PRIMARY KEY, title TEXT, asset_file TEXT, published INTEGER, FOREIGN KEY(asset_file) REFERENCES registered_assets(asset_file))")
    else:
        con.execute("CREATE TABLE cms_articles(article_id TEXT PRIMARY KEY, title TEXT, asset_file TEXT, published INTEGER)")
    con.commit()
    con.close()

    extra_fe = "First merge branch `hotfix/checkout-tax` into `main` so `checkout_tax_bps = 825` is preserved!" if is_branch_race else "Keep `main` branch clean."
    extra_des = "Also register `card_01.png`..`card_04.png` and `hero_banner.png` in SQLite table `registered_assets(asset_file, width, height)` inside `/workspace/staging_data/cms.db` so CMS foreign keys succeed!" if is_branch_race else ""

    tickets["FE"].write_text(textwrap.dedent(f"""\
        # Role FE — Frontend 5-Page Launch Upgrade & Pricing Logic ({task_id})
        Shared Git repo: `/workspace/launch-repo`. Live Staging server: `http://127.0.0.1:{sport}`. Spec Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Inspect the Chromium `<canvas>` spec card on `DISPLAY=:99` for exact pricing discount and timezone rules.
        2. {extra_fe}
        3. Upgrade all 5 HTML templates (`/workspace/launch-repo/templates/{{index,pricing,features,enterprise,changelog}}.html`) to include `data-launch-v4="ready"`, `<img src="/static/assets/nav_logo.svg">`, and `<img src="/static/assets/hero_banner.png">`.
        4. Fix `/workspace/launch-repo/app_logic.json` so `annual_multiplier = 0.80` (20% annual discount) and `changelog_timezone = "UTC"` (preserving `checkout_tax_bps` if set).
        5. Commit your changes cleanly on `main` (coordinate around `.git/index.lock` with DESIGN!) and deploy via `POST http://127.0.0.1:{sport}/api/staging/redeploy`.
    """), encoding="utf-8")

    tickets["DESIGN"].write_text(textwrap.dedent(f"""\
        # Role DESIGN — Multi-Size Brand Assets & SVG Viewport Fix ({task_id})
        Shared Git repo: `/workspace/launch-repo`. Spec Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Staging: `http://127.0.0.1:{sport}`.

        1. Read exact dimensions and brand accent RGB from the Chromium `<canvas>` spec card on `DISPLAY=:99` (`HERO = 1200x600`, `CARD = 600x400`, `ACCENT RGB = (14, 165, 233) #0EA5E9`, `NAV LOGO VIEWBOX = 0 0 120 40`).
        2. Update `/workspace/launch-repo/tools/asset_export_settings.json` (`dpi=150, hero_size=[1200,600], card_size=[600,400], accent_rgb=[14,165,233]`) and fix `/workspace/launch-repo/static/assets/nav_logo.svg` to `viewBox="0 0 120 40"`.
        3. Generate `/workspace/launch-repo/static/assets/hero_banner.png` (`1200x600`) and `card_01.png` .. `card_04.png` (`600x400`) containing brand accent `(14, 165, 233)` at center region.
        4. {extra_des}
        5. Commit assets cleanly to `main` in `/workspace/launch-repo` without discarding FE commits, and call `POST http://127.0.0.1:{sport}/api/staging/redeploy`.
    """), encoding="utf-8")

    tickets["CMS"].write_text(textwrap.dedent(f"""\
        # Role CMS — 20 Launch Articles Ingestion & Asset Binding ({task_id})
        Shared CMS Portal: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared DB: `/workspace/staging_data/cms.db`.

        1. Read required article count (`ART-01` .. `ART-20`) from the `<canvas>` spec card on `DISPLAY=:99`.
        2. Wait/verify DESIGN has exported (and registered, if foreign-key enabled) `card_01.png` .. `card_04.png` in `/workspace/launch-repo/static/assets/`.
        3. Publish all 20 launch articles (`ART-01` through `ART-20`, with `published = true` and `asset_file` cycling `card_01.png`..`card_04.png`) via `POST http://127.0.0.1:{pport}/api/cms/upsert`.
        4. Verify via `GET http://127.0.0.1:{sport}/api/staging/diagnostics` that `published_cms_count == 20`.
    """), encoding="utf-8")

    tickets["QA"].write_text(textwrap.dedent(f"""\
        # Role QA — Dynamic Staging Regression, Canary Defect Triage & Release Sign-Off ({task_id})
        Live Staging: `http://127.0.0.1:{sport}`. QA Tracker & `<canvas>` Spec: `http://127.0.0.1:{pport}` (`DISPLAY=:99`).

        1. Read `LAUNCH RELEASE GATE TOKEN` and target pricing/SVG/timezone specs from the `<canvas>` card on `DISPLAY=:99`.
        2. Audit initial Staging / Git baseline (`git log -p -n 1` or `/api/staging/diagnostics`) to identify and file ONLY the **3 real pre-seeded defects** via `POST http://127.0.0.1:{pport}/api/qa/file_issue` (`{{"bug_code": "<CODE>", "page": "<page>", "evidence": "..."}}`):
           - `BUG-ANNUAL-SIGN` (`pricing`: annual multiplier 1.20 surcharge instead of 0.80)
           - `BUG-SVG-VIEWBOX` (`index`: `nav_logo.svg` cropped `0 0 40 40` instead of `0 0 120 40`)
           - `BUG-CHANGELOG-TZ` (`changelog`: timezone `-07:00` instead of `UTC`)
           **CRITICAL**: Do NOT file issues for transient peer work-in-progress (e.g. missing CMS articles or unexported PNGs), as false transient bug reports penalize QA!
        3. Wait until FE, DESIGN, and CMS have all finished, committed to `main` (clean `git status`), and redeployed Staging so all 5 pages have `data-launch-v4="ready"`, `annual_total_usd == 960.0`, `nav_logo_viewbox == "0 0 120 40"`, `changelog_tz == "UTC"`, and `published_cms_count == 20`.
        4. Submit final release sign-off via `POST http://127.0.0.1:{pport}/api/qa/signoff` with `{{"release_gate": "LNCH-2026-V4", "git_commit": "<final_HEAD_sha40>", "verified_pages": ["index","pricing","features","enterprise","changelog"]}}`.
    """), encoding="utf-8")


def build_arena_c(task_id: str, workspace: Path, tickets: dict[str, Path]) -> None:
    meta = TA_BY_ID[task_id]
    pport = meta["portal_port"]
    cport = meta["cluster_port"]
    prof = str(meta.get("fault_profile", "triple_mask"))
    cdir = workspace / "cluster"
    (cdir / "disk_vol").mkdir(parents=True, exist_ok=True)
    (workspace / "forensics").mkdir(parents=True, exist_ok=True)

    db_p = cdir / "prod_orders.db"
    con = sqlite3.connect(str(db_p))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE orders_audit(id INTEGER PRIMARY KEY, tenant_id TEXT, status TEXT, created_ts INTEGER, payload TEXT)")
    rows = [(i, f"T-{i % 40:02d}", "OK", 1700000000 + i, f"order-payload-{i}-batch") for i in range(1, 4001)]
    con.executemany("INSERT INTO orders_audit VALUES(?,?,?,?,?)", rows)
    con.commit()
    con.close()

    if prof == "triple_mask":
        (cdir / "query_plan.sql").write_text(
            "SELECT id, tenant_id, status FROM orders_audit WHERE payload LIKE '%batch%' ORDER BY created_ts DESC LIMIT 50;\n",
            encoding="utf-8",
        )
        write_json(cdir / "gateway_config.json", {"retry_backoff_ms": 0, "max_retries": 10, "timeout_ms": 180})
        write_json(cdir / "logging_config.json", {"level": "TRACE_VERBOSE", "quota_kb": 512})
        (cdir / "disk_vol/trace.dump").write_bytes(b"T" * (520 * 1024))
    else:
        write_json(cdir / "worker_batch.json", {"batch_size": 5000, "isolation": "EXCLUSIVE_LOCK"})
        write_json(cdir / "gateway_config.json", {"hot_key_ttl_s": 0, "singleflight": False})
        write_json(cdir / "k8s_probe.json", {"liveness_timeout_ms": 50, "restart_on_fail": True})

    (workspace / "INC_Runbook_RCA.md").write_text(textwrap.dedent("""\
        # Collaborative Incident Runbook & Root Cause Analysis

        ## Forensics
        PENDING

        ## DB Mitigation
        PENDING

        ## App/Gateway Mitigation
        PENDING

        ## Infra/Storage Mitigation
        PENDING

        ## Canary Verification
        PENDING
    """), encoding="utf-8")

    if prof == "triple_mask":
        db_steps = "Create composite index `CREATE INDEX idx_orders_tenant_ts ON orders_audit(tenant_id, created_ts)` on `/workspace/cluster/prod_orders.db` and update `/workspace/cluster/query_plan.sql` to filter by `WHERE tenant_id = :tenant_id AND created_ts >= :min_ts ORDER BY created_ts DESC LIMIT 50;` (removing `LIKE '%batch%'`)."
        app_steps = "Update `/workspace/cluster/gateway_config.json` to safe thresholds from `<canvas>` (`retry_backoff_ms = 200`, `max_retries = 2`, `timeout_ms = 800`). Use ONLY `mode=\"graceful\", service=\"gateway\"` if calling `/api/cluster/restart`!"
        inf_steps = "Update `/workspace/cluster/logging_config.json` to `level = \"INFO\"` FIRST (so trace daemon stops refilling disk!) and truncate/remove `/workspace/cluster/disk_vol/trace.dump` (< 100 KB). Do NOT hard-restart `all`/`db`!"
        rc_list = '["db_missing_composite_index", "gateway_zero_backoff_retry_storm", "trace_log_disk_quota_full"]'
    else:
        db_steps = "Update `/workspace/cluster/worker_batch.json` to `batch_size = 200` (<= 250) and `isolation = \"WAL_READ_COMMITTED\"`."
        app_steps = "Update `/workspace/cluster/gateway_config.json` to `hot_key_ttl_s = 180` (>= 120) and `singleflight = true`. Do NOT hard-restart `all` before `/workspace/forensics/db_fingerprint.json` is saved!"
        inf_steps = "Update `/workspace/cluster/k8s_probe.json` to `liveness_timeout_ms = 1000` (>= 800) to stop the pod kill-loop without wiping DB forensics."
        rc_list = '["k8s_liveness_probe_kill_loop", "hot_cache_ttl_stampede", "db_exclusive_batch_lock"]'

    tickets["DB"].write_text(textwrap.dedent(f"""\
        # Role DB — Database Forensics & Query/Lock Remediation ({task_id})
        Grafana `<canvas>` Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Cluster API: `http://127.0.0.1:{cport}/metrics`. Shared RCA: `/workspace/INC_Runbook_RCA.md`.

        1. Wait until `/workspace/cluster/slow_query_ring.json` has `sufficient_window == true` (>= 12s live sample) and copy/archive it to `/workspace/forensics/db_fingerprint.json` BEFORE fixing or restarting.
        2. {db_steps}
        3. Replace `PENDING` under `## DB Mitigation` in `/workspace/INC_Runbook_RCA.md` with your exact SQL/config fix **without overwriting peer sections**!
    """), encoding="utf-8")

    tickets["APP"].write_text(textwrap.dedent(f"""\
        # Role APP — Application / Gateway Storm Mitigation ({task_id})
        Grafana `<canvas>` Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Cluster API: `http://127.0.0.1:{cport}`.

        1. Inspect the Chromium `<canvas>` dashboard on `DISPLAY=:99` for safe gateway/cache parameters and forensic preservation warning.
        2. **CRITICAL**: Do NOT call `POST /api/cluster/restart` with `mode="hard"` or `service="all"` while DB is still capturing `/workspace/forensics/db_fingerprint.json` (wiping the ring buffer causes an Observation Pollution penalty!).
        3. {app_steps}
        4. Update ONLY `## App/Gateway Mitigation` in `/workspace/INC_Runbook_RCA.md` preserving all other sections.
    """), encoding="utf-8")

    tickets["INFRA"].write_text(textwrap.dedent(f"""\
        # Role INFRA — Storage Quota / Liveness Probe Stabilization ({task_id})
        Grafana `<canvas>` Console: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Cluster API: `http://127.0.0.1:{cport}`.

        1. Read storage/probe policy from the `<canvas>` dashboard on `DISPLAY=:99`.
        2. Avoid uncoordinated `hard` restarts that wipe `/workspace/cluster/slow_query_ring.json` before `/workspace/forensics/db_fingerprint.json` exists.
        3. {inf_steps}
        4. Update ONLY `## Infra/Storage Mitigation` in `/workspace/INC_Runbook_RCA.md` preserving peer sections.
    """), encoding="utf-8")

    tickets["IC"].write_text(textwrap.dedent(f"""\
        # Role IC — Incident Commander, Canary Burst Replay & StatusPage ({task_id})
        Grafana `<canvas>` & StatusPage: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Cluster API: `http://127.0.0.1:{cport}`.

        1. Read `INCIDENT ID` and SLA target (`P99 <= 85 ms`, `5XX = 0.0%`) from the `<canvas>` dashboard on `DISPLAY=:99`.
        2. Wait until `/workspace/forensics/db_fingerprint.json` exists AND `GET http://127.0.0.1:{cport}/metrics` reports `healthy == true` (all 3 peer mitigations applied).
        3. Trigger the 1.35x burst verification via `POST http://127.0.0.1:{cport}/api/cluster/canary_replay` and confirm `p99_ms <= 85.0` and `error_rate == 0.0`.
        4. Publish StatusPage resolution via `POST http://127.0.0.1:{pport}/api/statuspage/publish` with `{{"incident_code": "<INCIDENT_ID>", "status": "RESOLVED", "root_causes": {rc_list}, "mitigated_p99_ms": <canary_p99>}}`, and fill `## Forensics` + `## Canary Verification` in `/workspace/INC_Runbook_RCA.md` without erasing `DB`, `App`, or `Infra` sections.
    """), encoding="utf-8")


def build_arena_d(task_id: str, workspace: Path, tickets: dict[str, Path]) -> None:
    meta = TA_BY_ID[task_id]
    pport = meta["portal_port"]
    for sub in ("raw", "vfx", "audio", "exports"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#1e293b:s=640x360:r=24:d=3.0", "-pix_fmt", "yuv420p", str(workspace / "raw/shot1.mp4")], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#334155:s=640x360:r=24:d=3.0", "-pix_fmt", "yuv420p", str(workspace / "raw/shot2.mp4")], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#0f172a:s=640x360:r=24:d=1.0", "-pix_fmt", "yuv420p", str(workspace / "raw/end_slate.mp4")], check=True, capture_output=True)
    subprocess.run(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "raw/vo_raw.wav"), "synth", "5.0", "sine", "440", "vol", "0.55"], check=True, capture_output=True)

    (workspace / "master_episode.mlt").write_text(textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <mlt profile="atsc_720p_24" version="7.12.0">
          <profile description="360p24" width="640" height="360" progressive="1" sample_aspect_num="1" sample_aspect_den="1" display_aspect_num="16" display_aspect_den="9" frame_rate_num="24" frame_rate_den="1" colorspace="709"/>
          <producer id="shot1"><property name="resource">/workspace/raw/shot1.mp4</property></producer>
          <producer id="shot2"><property name="resource">/workspace/raw/shot2.mp4</property></producer>
          <playlist id="video_main">
            <entry producer="shot1" in="0" out="71"/>
            <entry producer="shot2" in="0" out="71"/>
          </playlist>
          <tractor id="main_tractor" in="0" out="143">
            <track producer="video_main"/>
          </tractor>
        </mlt>
    """), encoding="utf-8")

    tickets["CUT"].write_text(textwrap.dedent(f"""\
        # Role CUT — Editorial Conform on Single-Seat MLT Timeline ({task_id})
        Media CMS `<canvas>` Spec: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared timeline: `/workspace/master_episode.mlt`.
        1. Read exact shot frame counts from `<canvas>` (`SHOT1=48f [0..47], SHOT2=48f [0..47], END_SLATE=24f [0..23] -> 120 frames = 5.00s @ 24fps`).
        2. Update `video_main` playlist and `<producer id="end_slate">` (`/workspace/raw/end_slate.mp4`) + `main_tractor out="119"` in `/workspace/master_episode.mlt` **preserving any VFX (`lower_third.png`) or Audio (`dialogue_ebu.wav`) tracks/transitions added by peers**!
    """), encoding="utf-8")

    tickets["VFX"].write_text(textwrap.dedent(f"""\
        # Role VFX — Lower-Third Graphic & MLT Overlay Track ({task_id})
        Media CMS `<canvas>` Spec: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared timeline: `/workspace/master_episode.mlt`.
        1. Read lower-third bar geometry & RGB from `<canvas>` (`640x360` RGBA PNG `/workspace/vfx/lower_third.png`: transparent top `y=0..279`, opaque teal bar `y=280..340` with exact `RGB=(20, 150, 168)`).
        2. Generate `/workspace/vfx/lower_third.png` (and save `/workspace/vfx/lower_third.xcf` via GIMP batch or valid XCF) and add producer/track + composite/qtblend transition for `/workspace/vfx/lower_third.png` (`in="0" out="119"`) into `/workspace/master_episode.mlt` **without overwriting CUT or AUDIO edits**!
    """), encoding="utf-8")

    tickets["AUDIO"].write_text(textwrap.dedent(f"""\
        # Role AUDIO — EBU R128 Dialogue Mastering & MLT Audio Track ({task_id})
        Media CMS `<canvas>` Spec: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared timeline: `/workspace/master_episode.mlt`.
        1. Read target integrated loudness from `<canvas>` (`-23.0 +/- 0.4 LUFS`, `5.00s` stereo 48kHz WAV).
        2. Master `/workspace/raw/vo_raw.wav` into `/workspace/audio/dialogue_ebu.wav` calibrated to `-23.0 +/- 0.4 LUFS` (verify with `ffmpeg -i /workspace/audio/dialogue_ebu.wav -af ebur128=framelog=verbose -f null -`), and wire `<producer id="vo_ebu">` (`/workspace/audio/dialogue_ebu.wav`) as a track in `main_tractor` inside `/workspace/master_episode.mlt` **without overwriting CUT or VFX edits**!
    """), encoding="utf-8")

    tickets["PUB"].write_text(textwrap.dedent(f"""\
        # Role PUB — Final Master Encode & Media CMS Release ({task_id})
        Media CMS `<canvas>` & Upload API: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared timeline: `/workspace/master_episode.mlt`.
        1. Read `MEDIA CMS RELEASE TAG` (`EP-2026-MASTER`) from `<canvas>`.
        2. Wait until ALL THREE upstream tracks (`end_slate.mp4` 120-frame conform, `lower_third.png` overlay, `dialogue_ebu.wav` audio) are present in `/workspace/master_episode.mlt` and files exist on disk.
        3. Render `/workspace/exports/final_episode.mp4` (`640x360`, 24fps, 120 frames = 5.00s, H.264 + AAC with `-23.0 +/- 0.4 LUFS` audio and visible `(20,150,168)` lower-third bar at `y=310`).
        4. Call `POST http://127.0.0.1:{pport}/api/media/upload_master` with `{{"release_tag": "EP-2026-MASTER", "mp4_path": "/workspace/exports/final_episode.mp4", "mlt_path": "/workspace/master_episode.mlt"}}` ONLY ONCE finalized (premature uploads incur side-effect penalties!).
    """), encoding="utf-8")


def build_arena_e(task_id: str, workspace: Path, tickets: dict[str, Path]) -> None:
    meta = TA_BY_ID[task_id]
    pport = meta["portal_port"]
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    fc_script = textwrap.dedent(f"""\
        import FreeCAD as App, Part
        doc = App.newDocument("TurbineReview")
        ss = doc.addObject("Spreadsheet::Sheet", "DesignSpec")
        ss.set("A2", "casing_bore_mm"); ss.set("B2", "80.0")
        ss.set("A3", "rotor_od_mm"); ss.set("B3", "81.0")
        ss.set("A4", "hub_thickness_mm"); ss.set("B4", "9.0")
        doc.recompute()
        c_out = Part.makeCylinder(52.0, 30.0)
        c_in = Part.makeCylinder(40.0, 30.0)
        c_obj = doc.addObject("Part::Feature", "Casing")
        c_obj.Shape = c_out.cut(c_in)
        r_obj = doc.addObject("Part::Feature", "Rotor")
        r_obj.Shape = Part.makeCylinder(40.5, 9.0, App.Vector(0,0,7.5))
        doc.recompute()
        doc.saveAs({str(workspace / "turbine_review.FCStd")!r})
    """)
    subprocess.run(["freecadcmd", "-c", fc_script], check=True, capture_output=True, timeout=90)

    write_multisheet_xlsx(
        workspace / "Engineering_Review_BOM.xlsx",
        [
            ("Summary", [
                ["Metric", "Value", "Formula_Spec"],
                ["Total_Volume_cm3", ("=SUM(Parts!B2:B3)", 0.0), "Cross-sheet volume sum"],
                ["Total_Mass_g", ("=B2*4.43", 0.0), "Ti-6Al-4V mass"],
                ["Total_Material_Cost_USD", ("=B3*0.85", 0.0), "Material cost"],
            ]),
            ("Parts", [
                ["Part_Name", "Volume_cm3", "Key_Dim_mm"],
                ["Casing", 0.0, 0.0],
                ["Rotor", 0.0, 0.0],
            ]),
        ],
    )

    tickets["HOUSING"].write_text(textwrap.dedent(f"""\
        # Role HOUSING — Casing Bore Tolerance Upgrade ({task_id})
        PLM `<canvas>` Spec: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared CAD: `/workspace/turbine_review.FCStd`.
        1. Read `CASING BORE` (`84.00 mm`, i.e. inner radius `42.00 mm`, outer radius `52.00 mm`, height `30.00 mm`) from `<canvas>`.
        2. Update `Casing` solid (`makeCylinder(52.0, 30.0).cut(makeCylinder(42.0, 30.0))`) and `DesignSpec.B2 = "84.0"` inside `/workspace/turbine_review.FCStd` **preserving `Rotor` and `DesignSpec.B3/B4`**, and export `/workspace/exports/casing.step`.
    """), encoding="utf-8")

    tickets["ROTOR"].write_text(textwrap.dedent(f"""\
        # Role ROTOR — Rotor Tip Clearance & Hub Stiffening ({task_id})
        PLM `<canvas>` Spec: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared CAD: `/workspace/turbine_review.FCStd`.
        1. Read `ROTOR TIP OD` (`83.10 mm`, radius `41.55 mm`) and minimum `ROTOR HUB THICKNESS` (`>= 14.0 mm`, set `15.0 mm` centered at `z=7.5`) from `<canvas>`.
        2. Update `Rotor` solid (`Part.makeCylinder(41.55, 15.0, App.Vector(0,0,7.5))`) and `DesignSpec.B3 = "83.10"`, `DesignSpec.B4 = "15.0"` inside `/workspace/turbine_review.FCStd` **preserving `Casing` and `DesignSpec.B2`**, and export `/workspace/exports/rotor.step`.
    """), encoding="utf-8")

    tickets["CAE"].write_text(textwrap.dedent(f"""\
        # Role CAE — Exclusive Single-License Structural/Clearance Verification ({task_id})
        PLM `<canvas>` & Exclusive CAE API: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared CAD: `/workspace/turbine_review.FCStd`.
        1. Read `ENGINEERING REVIEW CODE` (`ENG-REV-84`) and target safety factor (`>= 1.85`) + radial gap (`[0.35, 0.55] mm`) from `<canvas>`.
        2. Poll `/api/public_status` (`solver_busy == false`) and verify BOTH `HOUSING` (`B2=84.0`) and `ROTOR` (`B3=83.10, B4>=14.0`) have settled in `/workspace/turbine_review.FCStd` before calling `POST http://127.0.0.1:{pport}/api/cae/solve` (`{{"review_code": "ENG-REV-84", "fcstd_path": "/workspace/turbine_review.FCStd"}}`).
        3. Confirm `/workspace/exports/cae_cert.json` has `passed == true` and `fcstd_sha256` matching the final `/workspace/turbine_review.FCStd`!
    """), encoding="utf-8")

    tickets["BOM"].write_text(textwrap.dedent(f"""\
        # Role BOM — Alloy Mass/Cost Workbook & Final Engineering Sign-Off ({task_id})
        PLM `<canvas>` Spec: `http://127.0.0.1:{pport}` (`DISPLAY=:99`). Shared deliverables: `/workspace/turbine_review.FCStd` and `/workspace/Engineering_Review_BOM.xlsx`.
        1. Read `ENGINEERING REVIEW CODE`, `TI-6AL-4V DENSITY` (`4.43 g/cm3`), and `COST` (`0.85 USD/g`) from `<canvas>`.
        2. Wait until `HOUSING`, `ROTOR`, and `CAE` (`/workspace/exports/cae_cert.json` with `passed == true`) have settled.
        3. Populate sheet `Parts` (`Casing` `Volume_cm3` & `84.0`, `Rotor` `Volume_cm3` & `83.10`) in `/workspace/Engineering_Review_BOM.xlsx` **preserving the live formulas in `Summary` (`B2, B3, B4`)**, and write `/workspace/exports/review_signoff.json` (`{{"review_code": "ENG-REV-84", "fcstd_path": "/workspace/turbine_review.FCStd", "total_mass_g": <float>, "total_cost_usd": <float>, "safety_factor": <float>}}`).
    """), encoding="utf-8")


def build_case(task_id: str, workspace: Path, tickets_root: Path) -> None:
    meta = TA_BY_ID[task_id]
    if workspace.exists():
        for c in list(workspace.iterdir()):
            shutil.rmtree(c) if c.is_dir() else c.unlink()
    workspace.mkdir(parents=True, exist_ok=True)
    tickets: dict[str, Path] = {}
    for r in meta["roles"]:
        rdir = tickets_root / r
        rdir.mkdir(parents=True, exist_ok=True)
        tickets[r] = rdir / "task.md"
    arena = meta["arena"]
    if arena == "A_quarterly_business_review":
        build_arena_a(task_id, workspace, tickets)
    elif arena == "B_product_launch_day":
        build_arena_b(task_id, workspace, tickets)
    elif arena == "C_live_incident_war_room":
        build_arena_c(task_id, workspace, tickets)
    elif arena == "D_video_production_studio":
        build_arena_d(task_id, workspace, tickets)
    elif arena == "E_engineering_cad_cae_review":
        build_arena_e(task_id, workspace, tickets)
    else:
        raise ValueError(arena)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    b_p = sub.add_parser("build")
    b_p.add_argument("--task", required=True)
    b_p.add_argument("--workspace", type=Path, required=True)
    b_p.add_argument("--tickets-root", type=Path, required=True)

    g_p = sub.add_parser("grade")
    g_p.add_argument("--task", required=True)
    g_p.add_argument("--workspace", type=Path, required=True)
    g_p.add_argument("--portal-state", type=Path, required=True)
    g_p.add_argument("--wall-seconds", type=float, default=180.0)
    g_p.add_argument("--out", type=Path, required=True)

    s_p = sub.add_parser("solve_role")
    s_p.add_argument("--task", required=True)
    s_p.add_argument("--role", required=True)
    s_p.add_argument("--workspace", type=Path, required=True)

    r_p = sub.add_parser("simulate_race")
    r_p.add_argument("--task", required=True)
    r_p.add_argument("--workspace", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "build":
        build_case(args.task, args.workspace, args.tickets_root)
    elif args.cmd == "grade":
        from tasks.thematic_arenas_v1.graders import grade_case
        pstate = json.loads(args.portal_state.read_text(encoding="utf-8")) if args.portal_state.is_file() else {}
        res = grade_case(args.task, args.workspace, pstate, wall_seconds=args.wall_seconds)
        write_json(args.out, res)
    elif args.cmd == "solve_role":
        from tasks.thematic_arenas_v1.solvers import solve_role
        solve_role(args.task, args.role, args.workspace)
    elif args.cmd == "simulate_race":
        from tasks.thematic_arenas_v1.solvers import simulate_uncoordinated_race
        simulate_uncoordinated_race(args.task, args.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

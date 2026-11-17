"""Cooperative reference solvers and uncoordinated race simulators for TA-A1..TA-E1."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

from tasks.thematic_arenas_v1.catalog import TA_BY_ID
from tasks.thematic_arenas_v1.suite import make_simple_pptx, sha256_file, write_json
from tasks.thematic_arenas_v1.xlsx_utils import evaluate_xlsx_via_libreoffice, update_single_sheet_xlsx, write_multisheet_xlsx


def _http_post(url: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def _http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def solve_role(task_id: str, role: str, workspace: Path) -> None:
    meta = TA_BY_ID[task_id]
    arena = meta["arena"]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"

    if arena == "A_quarterly_business_review":
        is_fx = bool(meta.get("fx_restatement_canary"))
        xlsx_p = workspace / "Q3_Operating_Model.xlsx"
        if role == "FIN":
            _http_post(f"{base}/api/bi/set_filter", {"quarter": "Q3", "currency": "USD", "exclude_ic": True, "actor": "FIN"})
            rows = [["table_id", "net_revenue_kusd", "direct_cost_kusd", "segment"]]
            tot_rev = tot_cost = 0.0
            for i in range(1, 13):
                tid = f"fin_m{i:02d}"
                code, res = _http_post(f"{base}/api/bi/export_table", {"table_id": tid, "dest_filename": f"fin_{tid}.csv"})
                if code == 401:
                    _http_post(f"{base}/api/sso/relogin", {})
                    _http_post(f"{base}/api/bi/set_filter", {"quarter": "Q3", "currency": "USD", "exclude_ic": True, "actor": "FIN"})
                    _, res = _http_post(f"{base}/api/bi/export_table", {"table_id": tid, "dest_filename": f"fin_{tid}.csv"})
                r_csv = list(csv.DictReader((Path("/home/gui/Downloads") / f"fin_{tid}.csv").read_text().splitlines()))[0]
                Path("/home/gui/Downloads/bi_report_export.csv").unlink(missing_ok=True)
                rv = float(r_csv["net_revenue_kusd"]); cv = float(r_csv["direct_cost_kusd"])
                tot_rev += rv; tot_cost += cv
                rows.append([tid, rv, cv, r_csv["segment"]])
            contra = -180.0 if is_fx else 0.0
            tot_rev += contra
            rows.append(["audit_apac_contra", contra, 0.0, "AUDIT_ADJUSTMENT"])
            update_single_sheet_xlsx(xlsx_p, "Revenue_Cost", rows)
            write_json(workspace / "exports/fin_reconciliation.json", {"total_net_revenue_kusd": round(tot_rev, 2), "total_direct_cost_kusd": round(tot_cost, 2)})

        elif role == "OPS":
            _http_post(f"{base}/api/bi/set_filter", {"quarter": "Q3", "currency": "USD", "exclude_ic": True, "actor": "OPS"})
            rows = [["table_id", "warehouse_cost_kusd", "lastmile_cost_kusd", "total_fulfillment_kusd", "sla_pct"]]
            for i in range(1, 11):
                tid = f"ops_w{i:02d}"
                code, _ = _http_post(f"{base}/api/bi/export_table", {"table_id": tid, "dest_filename": f"ops_{tid}.csv"})
                if code == 401:
                    _http_post(f"{base}/api/sso/relogin", {})
                    _http_post(f"{base}/api/bi/set_filter", {"quarter": "Q3", "currency": "USD", "exclude_ic": True, "actor": "OPS"})
                    _http_post(f"{base}/api/bi/export_table", {"table_id": tid, "dest_filename": f"ops_{tid}.csv"})
                r_csv = list(csv.DictReader((Path("/home/gui/Downloads") / f"ops_{tid}.csv").read_text().splitlines()))[0]
                Path("/home/gui/Downloads/bi_report_export.csv").unlink(missing_ok=True)
                wc = float(r_csv["warehouse_cost_kusd"]); lc = float(r_csv["lastmile_cost_kusd"]); sla = float(r_csv["sla_pct"])
                rows.append([tid, wc, lc, round(wc + lc, 2), sla])
            update_single_sheet_xlsx(xlsx_p, "Ops_KPI", rows)
            im = Image.new("RGB", (680, 380), (15, 23, 42))
            dr = ImageDraw.Draw(im)
            for idx, r in enumerate(rows[1:]):
                h = int(float(r[3]) * 3.5)
                dr.rectangle([40 + idx * 60, 340 - h, 80 + idx * 60, 340], fill=(14, 165, 233))
            im.save(workspace / "exports/ops_sla_chart.png")

        elif role == "SALES":
            weights = {"NA": 0.40, "EMEA": 0.35, "APAC": 0.30, "LATAM": 0.25}
            _http_post(f"{base}/api/bi/set_filter", {"quarter": "Q3", "currency": "USD", "exclude_ic": True, "actor": "SALES"})
            rows = [["table_id", "region", "raw_pipeline_usd", "win_rate_weight", "weighted_kusd"]]
            reg_tot: dict[str, float] = {}
            for i in range(1, 9):
                tid = f"crm_r{i:02d}"
                _http_post(f"{base}/api/bi/export_table", {"table_id": tid, "dest_filename": f"crm_{tid}.csv"})
                r_csv = list(csv.DictReader((Path("/home/gui/Downloads") / f"crm_{tid}.csv").read_text().splitlines()))[0]
                Path("/home/gui/Downloads/bi_report_export.csv").unlink(missing_ok=True)
                reg = r_csv["region"]
                raw_v = float(r_csv["open_pipeline_raw"])
                fx = 1.10 if (is_fx and r_csv["source_currency"] == "EUR") else 1.00
                usd_v = round(raw_v * fx, 2)
                wt = weights[reg]
                w_v = round(usd_v * wt, 2)
                reg_tot[reg] = round(reg_tot.get(reg, 0.0) + w_v, 2)
                rows.append([tid, reg, usd_v, wt, w_v])
            update_single_sheet_xlsx(xlsx_p, "Sales_Pipeline", rows)
            (workspace / "exports/regional_commentary.md").write_text(
                f"# Q3 Regional Pipeline Commentary\n\nSubtotals: {json.dumps(reg_tot)} | Total Weighted = {sum(reg_tot.values()):.2f} kUSD\n",
                encoding="utf-8",
            )

        elif role == "EXEC":
            bcode = "QBR-2026-Q3-RESTATED" if is_fx else "QBR-2026-Q3-GOLD"
            ev = evaluate_xlsx_via_libreoffice(xlsx_p)["Summary"]
            noi = float(ev["B5"]["value"]); ops = float(ev["B4"]["value"]); pipe = float(ev["B6"]["value"])
            chart_p = workspace / "exports/ops_sla_chart.png"
            subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-i", str(chart_p)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            clip_png = subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"], check=True, capture_output=True, timeout=10).stdout
            pptx_p = workspace / "Q3_Executive_Deck.pptx"
            make_simple_pptx(pptx_p, [f"Board Sign-Off: {bcode}", f"Net Operating Income: {noi:.1f} kUSD", f"Ops Cost: {ops:.1f} kUSD | Pipeline: {pipe:.1f} kUSD"], chart_png_bytes=clip_png)
            Image.open(io.BytesIO(clip_png)).convert("RGB").save(workspace / "exports/Q3_Executive_Deck.pdf", "PDF", resolution=150.0)
            _http_post(f"{base}/api/mail/send_exec", {
                "board_code": bcode,
                "subject": f"{task_id} Final Board Pack",
                "net_operating_income_kusd": noi,
                "total_ops_cost_kusd": ops,
                "weighted_pipeline_kusd": pipe,
                "model_path": str(xlsx_p),
                "deck_path": str(pptx_p),
            })

    elif arena == "B_product_launch_day":
        sport = int(meta["staging_port"])
        repo = workspace / "launch-repo"
        is_branch = bool(meta.get("branch_schema_race"))
        if role == "FE":
            if is_branch:
                subprocess.run(["git", "merge", "--no-edit", "hotfix/checkout-tax"], cwd=repo, check=True, capture_output=True)
            for pg in ("index", "pricing", "features", "enterprise", "changelog"):
                (repo / f"templates/{pg}.html").write_text(
                    f'<!doctype html><html data-launch-v4="ready"><body><img src="/static/assets/nav_logo.svg"/><img src="/static/assets/hero_banner.png"/><h1>{pg.upper()} v4</h1></body></html>\n',
                    encoding="utf-8",
                )
            lg = json.loads((repo / "app_logic.json").read_text(encoding="utf-8"))
            lg["annual_multiplier"] = 0.80
            lg["changelog_timezone"] = "UTC"
            write_json(repo / "app_logic.json", lg)
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "FE: launch v4 pages and pricing/TZ fixes"], cwd=repo, check=True, capture_output=True)
            _http_post(f"http://127.0.0.1:{sport}/api/staging/redeploy", {})

        elif role == "DESIGN":
            write_json(repo / "tools/asset_export_settings.json", {"dpi": 150, "hero_size": [1200, 600], "card_size": [600, 400], "accent_rgb": [14, 165, 233]})
            (repo / "static/assets/nav_logo.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" viewBox="0 0 120 40"><rect x="2" y="4" width="116" height="32" fill="#0EA5E9"/></svg>\n',
                encoding="utf-8",
            )
            Image.new("RGB", (1200, 600), (14, 165, 233)).save(repo / "static/assets/hero_banner.png")
            for i in range(1, 5):
                Image.new("RGB", (600, 400), (14, 165, 233)).save(repo / f"static/assets/card_0{i}.png")
            if is_branch:
                con = sqlite3.connect(str(workspace / "staging_data/cms.db"))
                con.execute("INSERT OR REPLACE INTO registered_assets VALUES('hero_banner.png', 1200, 600)")
                for i in range(1, 5):
                    con.execute("INSERT OR REPLACE INTO registered_assets VALUES(?, 600, 400)", (f"card_0{i}.png",))
                con.commit(); con.close()
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "DESIGN: brand assets and nav_logo viewBox"], cwd=repo, check=True, capture_output=True)
            _http_post(f"http://127.0.0.1:{sport}/api/staging/redeploy", {})

        elif role == "CMS":
            for i in range(1, 21):
                _http_post(f"{base}/api/cms/upsert", {
                    "article_id": f"ART-{i:02d}",
                    "title": f"Launch Announcement #{i:02d}",
                    "asset_file": f"card_0{((i - 1) % 4) + 1}.png",
                    "published": True,
                })

        elif role == "QA":
            for bcode, pg in (("BUG-ANNUAL-SIGN", "pricing"), ("BUG-SVG-VIEWBOX", "index"), ("BUG-CHANGELOG-TZ", "changelog")):
                _http_post(f"{base}/api/qa/file_issue", {"bug_code": bcode, "page": pg, "evidence": "Verified in initial git commit"})
            head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
            _http_post(f"{base}/api/qa/signoff", {
                "release_gate": "LNCH-2026-V4",
                "git_commit": head_sha,
                "verified_pages": ["index", "pricing", "features", "enterprise", "changelog"],
            })

    elif arena == "C_live_incident_war_room":
        cport = int(meta["cluster_port"])
        prof = str(meta.get("fault_profile", "triple_mask"))
        rca_p = workspace / "INC_Runbook_RCA.md"

        def _patch_rca(section: str, content: str) -> None:
            txt = rca_p.read_text(encoding="utf-8")
            new_txt = re.sub(rf"(## {re.escape(section)}\n)(?:.+?)(?=\n## |\Z)", rf"\g<1>{content}\n", txt, flags=re.S)
            rca_p.write_text(new_txt, encoding="utf-8")

        if role == "DB":
            ring = workspace / "cluster/slow_query_ring.json"
            for _ in range(16):
                if ring.is_file():
                    d = json.loads(ring.read_text(encoding="utf-8"))
                    if d.get("sufficient_window"):
                        break
                time.sleep(1.0)
            (workspace / "forensics").mkdir(parents=True, exist_ok=True)
            (workspace / "forensics/db_fingerprint.json").write_text(ring.read_text(encoding="utf-8"), encoding="utf-8")
            if prof == "triple_mask":
                con = sqlite3.connect(str(workspace / "cluster/prod_orders.db"))
                con.execute("CREATE INDEX IF NOT EXISTS idx_orders_tenant_ts ON orders_audit(tenant_id, created_ts)")
                con.commit(); con.close()
                (workspace / "cluster/query_plan.sql").write_text(
                    "SELECT id, tenant_id, status FROM orders_audit WHERE tenant_id = :tenant_id AND created_ts >= :min_ts ORDER BY created_ts DESC LIMIT 50;\n",
                    encoding="utf-8",
                )
            else:
                write_json(workspace / "cluster/worker_batch.json", {"batch_size": 200, "isolation": "WAL_READ_COMMITTED"})
            _patch_rca("DB Mitigation", "Captured 12s live forensic ring buffer and applied composite index / WAL batch fix.")

        elif role == "APP":
            if prof == "triple_mask":
                write_json(workspace / "cluster/gateway_config.json", {"retry_backoff_ms": 200, "max_retries": 2, "timeout_ms": 800})
            else:
                write_json(workspace / "cluster/gateway_config.json", {"hot_key_ttl_s": 180, "singleflight": True})
            _http_post(f"http://127.0.0.1:{cport}/api/cluster/restart", {"mode": "graceful", "service": "gateway"})
            _patch_rca("App/Gateway Mitigation", "Applied bounded exponential retry backoff / singleflight cache policy via graceful gateway reload.")

        elif role == "INFRA":
            if prof == "triple_mask":
                write_json(workspace / "cluster/logging_config.json", {"level": "INFO", "quota_kb": 512})
                (workspace / "cluster/disk_vol/trace.dump").write_bytes(b"")
            else:
                write_json(workspace / "cluster/k8s_probe.json", {"liveness_timeout_ms": 1000, "restart_on_fail": True})
            _patch_rca("Infra/Storage Mitigation", "Switched logging level to INFO and cleared trace quota / raised liveness probe timeout to 1000ms.")

        elif role == "IC":
            time.sleep(1.5)
            _, rep = _http_post(f"http://127.0.0.1:{cport}/api/cluster/canary_replay", {})
            inc = "INC-4401" if prof == "triple_mask" else "INC-4402"
            rcs = ["db_missing_composite_index", "gateway_zero_backoff_retry_storm", "trace_log_disk_quota_full"] if prof == "triple_mask" else ["k8s_liveness_probe_kill_loop", "hot_cache_ttl_stampede", "db_exclusive_batch_lock"]
            _http_post(f"{base}/api/statuspage/publish", {"incident_code": inc, "status": "RESOLVED", "root_causes": rcs, "mitigated_p99_ms": rep["p99_ms"]})
            _patch_rca("Forensics", f"Incident {inc} correlated three mutually masking faults without observation pollution.")
            _patch_rca("Canary Verification", f"1.35x burst canary replay passed at P99={rep['p99_ms']}ms and 5xx=0.0%.")

    elif arena == "D_video_production_studio":
        mlt_p = workspace / "master_episode.mlt"
        if role == "CUT":
            root = ET.fromstring(mlt_p.read_text(encoding="utf-8"))
            if root.find(".//producer[@id='end_slate']") is None:
                pr = ET.Element("producer", {"id": "end_slate"})
                prop = ET.SubElement(pr, "property", {"name": "resource"})
                prop.text = "/workspace/raw/end_slate.mp4"
                root.insert(3, pr)
            pl = root.find(".//playlist[@id='video_main']")
            assert pl is not None
            pl.clear(); pl.attrib["id"] = "video_main"
            ET.SubElement(pl, "entry", {"producer": "shot1", "in": "0", "out": "47"})
            ET.SubElement(pl, "entry", {"producer": "shot2", "in": "0", "out": "47"})
            ET.SubElement(pl, "entry", {"producer": "end_slate", "in": "0", "out": "23"})
            tr = root.find(".//tractor[@id='main_tractor']")
            assert tr is not None
            tr.attrib["out"] = "119"
            mlt_p.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")

        elif role == "VFX":
            im = Image.new("RGBA", (640, 360), (0, 0, 0, 0))
            dr = ImageDraw.Draw(im)
            dr.rectangle([0, 280, 639, 340], fill=(20, 150, 168, 255))
            lt_p = workspace / "vfx/lower_third.png"
            im.save(lt_p)
            root = ET.fromstring(mlt_p.read_text(encoding="utf-8"))
            if root.find(".//producer[@id='vfx_lt']") is None:
                pr = ET.Element("producer", {"id": "vfx_lt", "in": "0", "out": "119"})
                prop = ET.SubElement(pr, "property", {"name": "resource"})
                prop.text = str(lt_p)
                root.insert(1, pr)
                tr = root.find(".//tractor[@id='main_tractor']")
                assert tr is not None
                ET.SubElement(tr, "track", {"producer": "vfx_lt"})
            mlt_p.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")

        elif role == "AUDIO":
            wav_out = workspace / "audio/dialogue_ebu.wav"
            subprocess.run([
                "ffmpeg", "-y", "-i", str(workspace / "raw/vo_raw.wav"),
                "-af", "loudnorm=I=-23.0:TP=-2.0:LRA=7.0", "-ar", "48000", "-ac", "2", str(wav_out),
            ], check=True, capture_output=True, timeout=45)
            root = ET.fromstring(mlt_p.read_text(encoding="utf-8"))
            if root.find(".//producer[@id='vo_ebu']") is None:
                pr = ET.Element("producer", {"id": "vo_ebu", "in": "0", "out": "119"})
                prop = ET.SubElement(pr, "property", {"name": "resource"})
                prop.text = str(wav_out)
                root.insert(1, pr)
                tr = root.find(".//tractor[@id='main_tractor']")
                assert tr is not None
                ET.SubElement(tr, "track", {"producer": "vo_ebu"})
            mlt_p.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")

        elif role == "PUB":
            mp4_out = workspace / "exports/final_episode.mp4"
            subprocess.run([
                "ffmpeg", "-y",
                "-t", "2.0", "-i", str(workspace / "raw/shot1.mp4"),
                "-t", "2.0", "-i", str(workspace / "raw/shot2.mp4"),
                "-t", "1.0", "-i", str(workspace / "raw/end_slate.mp4"),
                "-i", str(workspace / "vfx/lower_third.png"),
                "-i", str(workspace / "audio/dialogue_ebu.wav"),
                "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[base];[base][3:v]overlay=0:0[vout];[4:a]loudnorm=I=-23.0:TP=-2.0:LRA=7.0[aout]",
                "-map", "[vout]", "-map", "[aout]", "-r", "24", "-frames:v", "120",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(mp4_out),
            ], check=True, capture_output=True, timeout=90)
            _http_post(f"{base}/api/media/upload_master", {
                "release_tag": "EP-2026-MASTER",
                "mp4_path": str(mp4_out),
                "mlt_path": str(mlt_p),
            })

    elif arena == "E_engineering_cad_cae_review":
        fc_p = workspace / "turbine_review.FCStd"
        if role == "HOUSING":
            code = (
                "import FreeCAD as App, Part\n"
                f"doc = App.openDocument({str(fc_p)!r})\n"
                "doc.getObject('DesignSpec').set('B2', '84.0')\n"
                "c = doc.getObject('Casing')\n"
                "c.Shape = Part.makeCylinder(52.0, 30.0).cut(Part.makeCylinder(42.0, 30.0))\n"
                "doc.recompute()\n"
                f"c.Shape.exportStep({str(workspace / 'exports/casing.step')!r})\n"
                f"doc.saveAs({str(fc_p)!r})\n"
            )
            subprocess.run(["freecadcmd", "-c", code], check=True, capture_output=True, timeout=60)

        elif role == "ROTOR":
            code = (
                "import FreeCAD as App, Part\n"
                f"doc = App.openDocument({str(fc_p)!r})\n"
                "ss = doc.getObject('DesignSpec'); ss.set('B3', '83.10'); ss.set('B4', '15.0')\n"
                "r = doc.getObject('Rotor')\n"
                "r.Shape = Part.makeCylinder(41.55, 15.0, App.Vector(0,0,7.5))\n"
                "doc.recompute()\n"
                f"r.Shape.exportStep({str(workspace / 'exports/rotor.step')!r})\n"
                f"doc.saveAs({str(fc_p)!r})\n"
            )
            subprocess.run(["freecadcmd", "-c", code], check=True, capture_output=True, timeout=60)

        elif role == "CAE":
            code, res = _http_post(f"{base}/api/cae/solve", {"review_code": "ENG-REV-84", "fcstd_path": str(fc_p)})
            assert code == 200 and res["certificate"]["passed"] is True, res

        elif role == "BOM":
            cert = json.loads((workspace / "exports/cae_cert.json").read_text(encoding="utf-8"))
            c_cm3 = float(cert["casing_cm3"]); r_cm3 = float(cert["rotor_cm3"])
            bom_p = workspace / "Engineering_Review_BOM.xlsx"
            update_single_sheet_xlsx(bom_p, "Parts", [
                ["Part_Name", "Volume_cm3", "Key_Dim_mm"],
                ["Casing", c_cm3, 84.0],
                ["Rotor", r_cm3, 83.10],
            ])
            ev = evaluate_xlsx_via_libreoffice(bom_p)["Summary"]
            mass = float(ev["B3"]["value"]); cost = float(ev["B4"]["value"])
            write_json(workspace / "exports/review_signoff.json", {
                "review_code": "ENG-REV-84",
                "fcstd_sha256": sha256_file(fc_p),
                "total_mass_g": round(mass, 2),
                "total_cost_usd": round(cost, 2),
                "safety_factor": cert["safety_factor"],
            })


def simulate_uncoordinated_race(task_id: str, workspace: Path) -> None:
    """Inject authentic uncoordinated multi-agent race & verify delayed canary + side-effects fire."""
    meta = TA_BY_ID[task_id]
    arena = meta["arena"]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"

    if arena == "A_quarterly_business_review":
        # FIN sets filter, OPS clobbers filter + overwrites shared Downloads file, EXEC sends premature mail before SALES finishes
        _http_post(f"{base}/api/bi/set_filter", {"quarter": "Q3", "currency": "USD", "exclude_ic": True, "actor": "FIN"})
        _http_post(f"{base}/api/bi/set_filter", {"quarter": "Q2", "currency": "EUR", "exclude_ic": False, "actor": "OPS"})
        _http_post(f"{base}/api/bi/export_table", {"table_id": "fin_m01", "actor": "FIN"})
        _http_post(f"{base}/api/bi/export_table", {"table_id": "ops_w01", "actor": "OPS"})
        _http_post(f"{base}/api/mail/send_exec", {
            "board_code": "QBR-2026-Q3-GOLD",
            "subject": "Premature Pack",
            "net_operating_income_kusd": 912.0,
            "total_ops_cost_kusd": 370.0,
            "weighted_pipeline_kusd": 0.0,
            "model_path": str(workspace / "Q3_Operating_Model.xlsx"),
            "deck_path": str(workspace / "Q3_Executive_Deck.pptx"),
        })
        solve_role(task_id, "SALES", workspace)

    elif arena == "B_product_launch_day":
        sport = int(meta["staging_port"])
        _http_get(f"http://127.0.0.1:{sport}/api/staging/diagnostics")
        # QA files false transient issue while CMS/DESIGN are still in flight, and FE/DESIGN redeploy mid-probe
        _http_post(f"{base}/api/qa/file_issue", {"bug_code": "CMS-ARTICLES-MISSING-WIP", "page": "index", "evidence": "0 articles"})
        solve_role(task_id, "FE", workspace)
        solve_role(task_id, "DESIGN", workspace)
        solve_role(task_id, "CMS", workspace)

    elif arena == "C_live_incident_war_room":
        cport = int(meta["cluster_port"])
        # APP hard-restarts cluster BEFORE DB saves forensic fingerprint -> observation pollution!
        _http_post(f"http://127.0.0.1:{cport}/api/cluster/restart", {"mode": "hard", "service": "all"})
        solve_role(task_id, "APP", workspace)
        solve_role(task_id, "INFRA", workspace)

    elif arena == "D_video_production_studio":
        solve_role(task_id, "CUT", workspace)
        # PUB uploads premature cut before VFX and AUDIO tracks are merged!
        _http_post(f"{base}/api/media/upload_master", {
            "release_tag": "EP-2026-MASTER",
            "mp4_path": str(workspace / "raw/shot1.mp4"),
            "mlt_path": str(workspace / "master_episode.mlt"),
        })

    elif arena == "E_engineering_cad_cae_review":
        import threading
        solve_role(task_id, "HOUSING", workspace)
        # Two concurrent solver calls collide on single-seat CAE license, then ROTOR edits FCStd AFTER CAE cert!
        t1 = threading.Thread(target=lambda: _http_post(f"{base}/api/cae/solve", {"review_code": "ENG-REV-84", "fcstd_path": str(workspace / "turbine_review.FCStd")}))
        t1.start()
        time.sleep(0.4)
        _http_post(f"{base}/api/cae/solve", {"review_code": "ENG-REV-84", "fcstd_path": str(workspace / "turbine_review.FCStd")})
        t1.join()
        solve_role(task_id, "ROTOR", workspace)

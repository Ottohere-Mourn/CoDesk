"""NF2-03: W3C IndexedDB onversionchange Connection Blocking & Web Locks — Clinical Trial ADaM Kaplan-Meier vs. MedDRA Upgrade."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    file_atomic_lock,
    launch_chromium_natural,
    make_canary_code,
    read_json_safe,
    write_json,
    write_multipage_sop_pdf,
)

TASK_ID = "NF2-03"
PORTAL_PORT = 19603

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "W3C IndexedDB `versionchange` Blocking & Web Locks: Oncology ADaM Kaplan-Meier Survival vs. MedDRA v27 Schema Upgrade",
    "domain": "Biostatistics CDISC ADaM Survival Analysis & Clinical Data Management MedDRA Coding (Chromium IndexedDB + SQLite)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("biostat_kaplan_meier_lead", "meddra_coding_manager"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

KM_LOCK_TOKEN = make_canary_code("ADAM-KM", "pfs-180d-greenwood")
MEDDRA_V2_TOKEN = make_canary_code("MEDDRA-V2", "idb-schema-v27")


def _generate_adtte_rows() -> tuple[list[dict[str, Any]], set[str]]:
    rows: list[dict[str, Any]] = []
    deviations: set[str] = set()
    for i in range(1, 361):
        subj = f"SUBJ-{i:04d}"
        itt = "Y" if (i % 29 != 0) else "N"  # Screen failures ITTFL='N'
        arm = "ARM_EXP" if (i % 2 == 1) else "ARM_CTRL"
        aval_days = 25 + ((i * 17) % 240)
        # CDISC convention trap: CNSR == 0 means EVENT (progression/death), CNSR == 1 means CENSORED!
        cnsr = 0 if (i % 3 != 0 and aval_days <= 195) else 1
        if i % 31 == 0 and itt == "Y":
            deviations.add(subj)  # Major protocol crossover -> censor at crossover_day 90 in PP sensitivity or exclude!
        rows.append({"usubjid": subj, "ittfl": itt, "trt01p": arm, "aval_days": aval_days, "cnsr": cnsr})
    return rows, deviations


def _generate_adae_rows() -> list[dict[str, Any]]:
    socs = ["BLOOD_LYMPHATIC", "HEPATOBILIARY", "CARDIAC", "GASTROINTESTINAL"]
    rows: list[dict[str, Any]] = []
    for i in range(1, 411):
        soc = socs[(i * 3) % 4]
        trtemfl = "Y" if (i % 19 != 0) else "N"  # Pre-treatment AEs TRTEMFL='N' must be excluded from TEAE!
        grade_ctcae = 1 + (i % 4)
        # Legacy MedDRA v26 retired PT code remap on every 14th row
        pt_code = f"PT-OLD-{(i % 5) + 1}" if (i % 14 == 0) else f"PT-V27-{(i % 9) + 10}"
        rows.append({
            "ae_seq": i, "usubjid": f"SUBJ-{(i % 180) + 1:04d}", "trtemfl": trtemfl,
            "soc_group": soc, "pt_code": pt_code, "ctcae_grade": grade_ctcae,
        })
    return rows


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    adtte, devs = _generate_adtte_rows()
    # Per-protocol clean ITT cohort (exclude major crossover deviations in secondary table protocol_crossover_log)
    exp_arm = [r for r in adtte if r["ittfl"] == "Y" and r["trt01p"] == "ARM_EXP" and r["usubjid"] not in devs]
    # Product-limit Kaplan-Meier S(180) + Greenwood SE on ARM_EXP
    times = sorted({int(r["aval_days"]) for r in exp_arm if int(r["cnsr"]) == 0 and int(r["aval_days"]) <= 180})
    surv = 1.0
    gw_sum = 0.0
    for t in times:
        n_i = sum(1 for r in exp_arm if int(r["aval_days"]) >= t)
        d_i = sum(1 for r in exp_arm if int(r["aval_days"]) == t and int(r["cnsr"]) == 0)
        if n_i > 0 and d_i > 0:
            surv *= (1.0 - d_i / n_i)
            if n_i > d_i:
                gw_sum += d_i / (n_i * (n_i - d_i))
    gw_se = surv * math.sqrt(gw_sum)
    events_total = sum(1 for r in exp_arm if int(r["cnsr"]) == 0)
    or_a = {
        "evaluable_exp_arm_n": len(exp_arm),
        "exp_arm_event_count": events_total,
        "km_survival_180d": round(surv, 4),
        "greenwood_se_180d": round(gw_se, 4),
        "km_lock_token": KM_LOCK_TOKEN,
    }

    adae = _generate_adae_rows()
    teae = [r for r in adae if r["trtemfl"] == "Y"]
    # Distinct-subject incidence for Grade >= 3 TEAE (regulatory standard: count unique usubjid per SOC, NOT raw AE episodes!)
    g3_subjs_by_soc: dict[str, set[str]] = {s: set() for s in ("BLOOD_LYMPHATIC", "HEPATOBILIARY", "CARDIAC", "GASTROINTESTINAL")}
    remapped_cnt = 0
    for r in teae:
        if r["pt_code"].startswith("PT-OLD-"):
            remapped_cnt += 1
        if int(r["ctcae_grade"]) >= 3:
            g3_subjs_by_soc[r["soc_group"]].add(r["usubjid"])
    or_b = {
        "teae_episode_count": len(teae),
        "remapped_v27_pt_count": remapped_cnt,
        "grade3plus_unique_subjects_by_soc": {k: len(v) for k, v in g3_subjs_by_soc.items()},
        "total_grade3plus_unique_subjects": len(set().union(*g3_subjs_by_soc.values())),
        "meddra_v2_token": MEDDRA_V2_TOKEN,
    }
    return or_a, or_b


KM_ORACLE, MEDDRA_ORACLE = _compute_oracles()

ADAM_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>CDISC ADaM IndexedDB Cohort Explorer</title>
<style>body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace} button{padding:8px 14px;background:#2563eb;color:#fff;border:none;cursor:pointer;margin-right:8px} pre{background:#1e293b;padding:14px;border:1px solid #334155}</style></head><body>
<h2>ADaM Survival Explorer — Live IndexedDB (`ClinicalEDC`)</h2>
<p>Open IDB Connection Status: <strong id="st" style="color:#4ade80">OPEN_HOLDING_V1</strong>
  <label style="margin-left:14px"><input type="checkbox" id="auto-rel"/> Auto-close IDB on `versionchange`</label>
</p>
<button onclick="openV1()">Hold IndexedDB Read Snapshot</button>
<button style="background:#d97706" onclick="closeConn()">Release IndexedDB Connection</button>
<button style="background:#059669" onclick="mintKm()">Mint ADaM Survival Snapshot Token</button>
<a href="/meddra-upgrader" style="color:#38bdf8;margin-left:14px">MedDRA v27 Upgrader -></a>
<pre id="out">IndexedDB v1 connection open...</pre>
<script>
let dbConn = null;
function openV1() {
  const req = indexedDB.open('ClinicalEDC', 1);
  req.onupgradeneeded = e => { const db = e.target.result; if (!db.objectStoreNames.contains('cohorts')) db.createObjectStore('cohorts', {keyPath:'id'}); };
  req.onsuccess = e => {
    dbConn = e.target.result;
    document.getElementById('st').textContent = 'HOLDING_IDB_CONN (v' + dbConn.version + ')';
    fetch('/api/idb/hold?holding=1', {method:'POST', credentials:'include'});
    dbConn.onversionchange = () => {
      if (document.getElementById('auto-rel').checked) { closeConn(); }
      else { document.getElementById('out').textContent = 'WARNING: Peer requested IDB schema upgrade; holding v1 blocks upgrade!'; }
    };
  };
}
function closeConn() {
  if (dbConn) { dbConn.close(); dbConn = null; }
  document.getElementById('st').textContent = 'RELEASED';
  fetch('/api/idb/hold?holding=0', {method:'POST', credentials:'include'});
}
async function mintKm() {
  const r = await fetch('/api/idb/mint_km', {method:'POST', credentials:'include'});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
openV1();
</script></body></html>"""

MEDDRA_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>MedDRA v27 IndexedDB Schema Upgrader</title>
<style>body{margin:18px;background:#090d16;color:#f8fafc;font-family:monospace} button{padding:8px 14px;background:#059669;color:#fff;border:none;cursor:pointer;margin-right:8px} pre{background:#111827;padding:14px;border:1px solid #334155}</style></head><body>
<h2>MedDRA v27 Schema Upgrade (`indexedDB.open('ClinicalEDC', 2)`)</h2>
<button onclick="runUpgrade()">Run IndexedDB v1 -> v2 Schema Migration</button>
<a href="/adam-explorer" style="color:#38bdf8;margin-left:14px"><- ADaM Explorer</a>
<pre id="out">Click [Run IndexedDB v1 -> v2 Schema Migration] to upgrade dictionary store...</pre>
<script>
function runUpgrade() {
  document.getElementById('out').textContent = 'Requesting indexedDB.open(ClinicalEDC, 2)...';
  const req = indexedDB.open('ClinicalEDC', 2);
  req.onblocked = () => {
    fetch('/api/idb/blocked_event', {method:'POST', credentials:'include'});
    document.getElementById('out').textContent = 'BLOCKED (IDBOpenDBRequest.onblocked): Another open tab holds ClinicalEDC v1 without closing on versionchange!';
  };
  req.onupgradeneeded = e => {
    const db = e.target.result;
    if (!db.objectStoreNames.contains('meddra_v27')) db.createObjectStore('meddra_v27', {keyPath:'pt'});
  };
  req.onsuccess = async e => {
    e.target.result.close();
    const r = await fetch('/api/idb/upgrade_complete', {method:'POST', credentials:'include'});
    document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
  };
}
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — CDISC ADaM 180-Day Kaplan-Meier Survival Audit (`biostat_kaplan_meier_lead`)",
        "",
        "## Objective",
        f"Inspect the ADaM cohort console (`http://127.0.0.1:{PORTAL_PORT}/adam-explorer` in Chromium), analyze `{b}/workspace/clinical/adtte_oncology.sqlite{b}` per `{b}/workspace/docs/SOP_ADaM_KM.pdf{b}` (releasing idle IndexedDB connections cleanly when done), and write `{b}/workspace/adam_km_survival.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — MedDRA v27 IndexedDB Migration & Grade>=3 TEAE Incidence (`meddra_coding_manager`)",
        "",
        "## Objective",
        f"Complete the live `ClinicalEDC` v2 IndexedDB schema migration on `http://127.0.0.1:{PORTAL_PORT}/meddra-upgrader` in Chromium, reconcile `{b}/workspace/clinical/adae_coding.sqlite{b}` per `{b}/workspace/docs/SOP_MedDRA_Coding.pdf{b}`, and write `{b}/workspace/meddra_teae_audit.json{b}`.",
    ])
    return {"biostat_kaplan_meier_lead": ta, "meddra_coding_manager": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["biostat_kaplan_meier_lead"]
    ws_b = workspace_map["meddra_coding_manager"]
    (ws_a / "clinical").mkdir(parents=True, exist_ok=True)
    (ws_a / "docs").mkdir(parents=True, exist_ok=True)
    (ws_b / "clinical").mkdir(parents=True, exist_ok=True)
    (ws_b / "docs").mkdir(parents=True, exist_ok=True)

    adtte, devs = _generate_adtte_rows()
    with sqlite3.connect(str(ws_a / "clinical/adtte_oncology.sqlite")) as conn:
        conn.execute("CREATE TABLE adtte_pfs (usubjid TEXT PRIMARY KEY, ittfl TEXT, trt01p TEXT, aval_days INTEGER, cnsr INTEGER)")
        for r in adtte:
            conn.execute("INSERT INTO adtte_pfs VALUES (?,?,?,?,?)", (r["usubjid"], r["ittfl"], r["trt01p"], r["aval_days"], r["cnsr"]))
        conn.execute("CREATE TABLE protocol_crossover_exclusions (usubjid TEXT PRIMARY KEY, exclusion_reason TEXT)")
        for u_id in sorted(devs):
            conn.execute("INSERT INTO protocol_crossover_exclusions VALUES (?, 'UNBLINDED_CROSSOVER_EXCLUDE_FROM_EFFICACY')", (u_id,))
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_ADaM_KM.pdf", "SOP-BIO-303: CDISC ADaM Progression-Free Survival Analysis", [
        ("1. Kaplan-Meier Product-Limit & Greenwood Variance", [
            "1.1 Filter /workspace/clinical/adtte_oncology.sqlite to evaluable ARM_EXP subjects (respecting CDISC ADaM CNSR event/censoring conventions and any efficacy exclusions in the database).",
            "1.2 Compute product-limit Kaplan-Meier survival S(180) at day 180 (4 dec) and Greenwood standard error at day 180 (4 dec), and mint km_lock_token on /adam-explorer.",
        ]),
        ("2. JSON Schema (/workspace/adam_km_survival.json)", [
            "Keys: evaluable_exp_arm_n (int), exp_arm_event_count (int), km_survival_180d (float, 4 dec), greenwood_se_180d (float, 4 dec), km_lock_token (str).",
        ]),
    ])

    adae = _generate_adae_rows()
    with sqlite3.connect(str(ws_b / "clinical/adae_coding.sqlite")) as conn:
        conn.execute("CREATE TABLE adae_events (ae_seq INTEGER PRIMARY KEY, usubjid TEXT, trtemfl TEXT, soc_group TEXT, pt_code TEXT, ctcae_grade INTEGER)")
        for r in adae:
            conn.execute("INSERT INTO adae_events VALUES (?,?,?,?,?,?)", (r["ae_seq"], r["usubjid"], r["trtemfl"], r["soc_group"], r["pt_code"], r["ctcae_grade"]))
        conn.execute("CREATE TABLE meddra_v27_crosswalk (legacy_pt TEXT PRIMARY KEY, v27_pt TEXT)")
        for k in range(1, 6):
            conn.execute("INSERT INTO meddra_v27_crosswalk VALUES (?, ?)", (f"PT-OLD-{k}", f"PT-V27-9{k}"))
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_MedDRA_Coding.pdf", "SOP-CDM-303: MedDRA v27 Upgrade & Subject-Level TEAE Incidence", [
        ("1. TEAE Coding & Distinct-Subject CTCAE Grade >= 3 Incidence", [
            "1.1 Complete the live ClinicalEDC v2 IndexedDB upgrade on /meddra-upgrader to obtain meddra_v2_token.",
            "1.2 Filter /workspace/clinical/adae_coding.sqlite to treatment-emergent adverse events, count rows requiring legacy-to-v27 PT crosswalk remapping, and compute ICH-E3 distinct-subject (unique usubjid) Grade >= 3 incidence by SOC and overall.",
        ]),
        ("2. JSON Schema (/workspace/meddra_teae_audit.json)", [
            "Keys: teae_episode_count (int), remapped_v27_pt_count (int), grade3plus_unique_subjects_by_soc (dict), total_grade3plus_unique_subjects (int), meddra_v2_token (str).",
        ]),
    ])
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    st_p = state_dir / "service_state.json"
    mem = {"v1_holding": False, "idb_blocked_events": 0, "km_minted": False, "v2_upgraded": False}
    write_json(st_p, {"task_id": TASK_ID, **mem})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("idb_sso" in c) and (c["idb_sso"].value == tok)
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
                    self._json(403, {"error": "SSO sealed"}); return
                nxt = (qs.get("next") or ["/adam-explorer"])[0]
                raw = f"<html><body><script>location.href={json.dumps(nxt)};</script></body></html>".encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"idb_sso={tok}; HttpOnly; Path=/; SameSite=Lax"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            if u.path == "/adam-explorer":
                raw = ADAM_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/meddra-upgrader":
                raw = MEDDRA_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self._json(404, {"error": "not found"})
        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/idb/hold":
                mem["v1_holding"] = (qs.get("holding") == ["1"])
                write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True}); return
            if u.path == "/api/idb/blocked_event":
                mem["idb_blocked_events"] += 1
                write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"blocked_recorded": True}); return
            if u.path == "/api/idb/mint_km":
                mem["km_minted"] = True
                write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"km_lock_token": KM_LOCK_TOKEN}); return
            if u.path == "/api/idb/upgrade_complete":
                if mem["v1_holding"]:
                    self._json(200, {"upgraded": False, "error": "v1 connection still holding lock"}); return
                mem["v2_upgraded"] = True
                write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"upgraded": True, "meddra_v2_token": MEDDRA_V2_TOKEN}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del workspace_map
    roles = set(active_roles or META["roles"])
    urls = []
    if "biostat_kaplan_meier_lead" in roles:
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/adam-explorer")
    if "meddra_coding_manager" in roles:
        urls.append(f"http://127.0.0.1:{PORTAL_PORT}/boot_auth?next=/meddra-upgrader")
    launch_chromium_natural(urls)
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ja = read_json_safe(workspace_map["biostat_kaplan_meier_lead"] / "adam_km_survival.json")
    jb = read_json_safe(workspace_map["meddra_coding_manager"] / "meddra_teae_audit.json")

    def _f(v: Any, d: float = -999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing adam_km_survival.json"),
        ("a_km_coarse", abs(_f(ja.get("km_survival_180d")) - KM_ORACLE["km_survival_180d"]) <= 0.045, 0.14, "km_survival_180d coarse off (inverted CDISC CNSR==0 event vs CNSR==1?)"),
        ("a_gw_coarse", abs(_f(ja.get("greenwood_se_180d")) - KM_ORACLE["greenwood_se_180d"]) <= 0.008, 0.14, "greenwood_se_180d coarse off"),
        ("a_tok", ja.get("km_lock_token") == KM_LOCK_TOKEN and bool(service_state.get("km_minted")), 0.16, "Missing live km_lock_token"),
        ("a_idb_released", bool(ja) and not bool(service_state.get("v1_holding")), 0.12, "Tab left holding ClinicalEDC v1 IndexedDB connection blocking schema upgrades!"),
        ("a_fine_crossover_n", ja.get("evaluable_exp_arm_n") == KM_ORACLE["evaluable_exp_arm_n"] and ja.get("exp_arm_event_count") == KM_ORACLE["exp_arm_event_count"], 0.18, "Missed protocol_crossover_exclusions table in adtte_oncology.sqlite"),
        ("a_fine_km_exact", abs(_f(ja.get("km_survival_180d")) - KM_ORACLE["km_survival_180d"]) <= 0.0008 and abs(_f(ja.get("greenwood_se_180d")) - KM_ORACLE["greenwood_se_180d"]) <= 0.0005, 0.18, "Exact KM S(180d) & Greenwood SE missed"),
    ]

    soc_m = jb.get("grade3plus_unique_subjects_by_soc") if isinstance(jb.get("grade3plus_unique_subjects_by_soc"), dict) else {}
    exp_soc = MEDDRA_ORACLE["grade3plus_unique_subjects_by_soc"]
    soc_hits = sum(1 for k, v in exp_soc.items() if soc_m.get(k) == v)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing meddra_teae_audit.json"),
        ("b_teae_cnt", jb.get("teae_episode_count") == MEDDRA_ORACLE["teae_episode_count"], 0.12, "teae_episode_count mismatch (filter TRTEMFL=='Y')"),
        ("b_remap_cnt", jb.get("remapped_v27_pt_count") == MEDDRA_ORACLE["remapped_v27_pt_count"], 0.12, "remapped_v27_pt_count mismatch"),
        ("b_v2_upgraded", jb.get("meddra_v2_token") == MEDDRA_V2_TOKEN and bool(service_state.get("v2_upgraded")), 0.20, "IndexedDB ClinicalEDC v2 upgrade blocked or incomplete!"),
        ("b_soc_keys", set(soc_m.keys()) == set(exp_soc.keys()), 0.12, "grade3plus_unique_subjects_by_soc keys incomplete"),
        ("b_fine_unique_soc", soc_hits == 4, 0.18, "SOC Grade>=3 unique subject counts off (counted raw episodes instead of distinct usubjid?)"),
        ("b_fine_unique_tot", jb.get("total_grade3plus_unique_subjects") == MEDDRA_ORACLE["total_grade3plus_unique_subjects"], 0.18, "total_grade3plus_unique_subjects off (summed across SOCs instead of distinct union?)"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    st_f = Path("/opt/nf_state/service_state.json")
    if role == "biostat_kaplan_meier_lead":
        write_json(ws / "adam_km_survival.json", KM_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf203_st"):
                st = read_json_safe(st_f); st["km_minted"] = True; st["v1_holding"] = False; write_json(st_f, st)
    else:
        write_json(ws / "meddra_teae_audit.json", MEDDRA_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf203_st"):
                st = read_json_safe(st_f); st["v1_holding"] = False; st["v2_upgraded"] = True; write_json(st_f, st)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    solve_role("biostat_kaplan_meier_lead", workspace_map, port)
    solve_role("meddra_coding_manager", workspace_map, port)
    # Tab 1 keeps holding v1 IDB connection -> blocks Tab 2's v2 schema upgrade (`onblocked`)!
    st_p = state_dir / "service_state.json"
    st = read_json_safe(st_p)
    st["v1_holding"] = True; st["v2_upgraded"] = False; st["idb_blocked_events"] = 3
    write_json(st_p, st)
    jb = read_json_safe(workspace_map["meddra_coding_manager"] / "meddra_teae_audit.json")
    jb["meddra_v2_token"] = ""
    jb["teae_episode_count"] = 0
    write_json(workspace_map["meddra_coding_manager"] / "meddra_teae_audit.json", jb)

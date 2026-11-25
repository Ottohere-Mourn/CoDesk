"""NF2-14: Shared Bare Git Repository Non-Fast-Forward Push Race & YAML Merge + Open Writer — Basel III FRTB vs. SA-CCR RWA."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
import subprocess
import tempfile
from typing import Any
from urllib.parse import urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_odt_plain_text,
    sync_uno_writer_text,
    write_json,
    write_multipage_sop_pdf,
    write_simple_odt,
)

TASK_ID = "NF2-14"
PORTAL_PORT = 19614

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Shared Bare `Git` Non-Fast-Forward Push Race & Open Writer: Basel III FRTB Expected Shortfall vs. SA-CCR Credit RWA Cap",
    "domain": "Quantitative Regulatory Capital Engineering (`Git` Bare Repo + `YAML` + `LibreOffice Writer` + `SQLite`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("frtb_market_risk_dev", "saccr_credit_cva_dev"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

FRTB_SIGN_CODE = make_canary_code("BCBS-FRTB", "es-amber-zone-250d")
SACCR_SIGN_CODE = make_canary_code("BCBS-SACCR", "isda-csa-pfe-rwa")
DESK_RWA_CAP_M = 319.0  # Exact floors 144.57 + 169.50 = 314.07 (gap=4.93): pref 148.0 + 173.0 = 321.0 > 319.0 while solo 148.0+169.50=317.50 <= 319.0 & 144.57+173.0=317.57 <= 319.0!
FRTB_FLOOR_M = 144.57
SACCR_FLOOR_M = 169.50


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Basel III FRTB Expected-Shortfall Backtesting & Git Release (`frtb_market_risk_dev`)",
        "",
        "## Objective",
        f"Analyze `{b}/workspace/data/frtb_backtest_250d.sqlite{b}` per `{b}/workspace/docs/SOP_FRTB_Git.pdf{b}` and `http://127.0.0.1:{PORTAL_PORT}/git-gate` in Chromium, clone/pull `{b}/workspace/shared_docs/risk_monorepo.git{b}` (`main` branch), commit your `frtb_rwa_musd` allocation in `config/capital_allocation.yaml` and push cleanly to `origin main` without clobbering other keys, sign `{b}/workspace/shared_docs/Model_Validation_Memo.odt{b}` (open in Writer), and write `{b}/workspace/frtb_rwa_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — SA-CCR Netting-Set EAD/RWA & Git Release (`saccr_credit_cva_dev`)",
        "",
        "## Objective",
        f"Analyze `{b}/workspace/data/saccr_netting_sets.sqlite{b}` per `{b}/workspace/docs/SOP_SACCR_Git.pdf{b}` and `http://127.0.0.1:{PORTAL_PORT}/git-gate` in Chromium, clone/pull `{b}/workspace/shared_docs/risk_monorepo.git{b}` (`main` branch), commit your `saccr_rwa_musd` allocation in `config/capital_allocation.yaml` and push cleanly to `origin main` without clobbering other keys, sign `{b}/workspace/shared_docs/Model_Validation_Memo.odt{b}` (open in Writer), and write `{b}/workspace/saccr_rwa_audit.json{b}`.",
    ])
    return {"frtb_market_risk_dev": ta, "saccr_credit_cva_dev": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    import yaml
    ws_a = workspace_map["frtb_market_risk_dev"]
    ws_b = workspace_map["saccr_credit_cva_dev"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "data", ws_a / "docs", ws_b / "data", ws_b / "docs", hub):
        d.mkdir(parents=True, exist_ok=True)

    bare = hub / "risk_monorepo.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(bare)], check=True, capture_output=True, timeout=20)
    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "seed"
        subprocess.run(["git", "clone", str(bare), str(wt)], check=True, capture_output=True, timeout=20)
        (wt / "config").mkdir(parents=True, exist_ok=True)
        (wt / "config/capital_allocation.yaml").write_text(
            yaml.safe_dump({
                "desk_id": "GLOBAL-RATES-FX-04",
                "max_total_rwa_musd": DESK_RWA_CAP_M,
                "frtb_rwa_musd": 0.0,
                "frtb_status": "PENDING",
                "saccr_rwa_musd": 0.0,
                "saccr_status": "PENDING",
            }, sort_keys=False),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(wt), "config", "user.email", "init@risk.local"], check=True)
        subprocess.run(["git", "-C", str(wt), "config", "user.name", "RiskInit"], check=True)
        subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "Initial v0 pending capital allocation"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wt), "push", "origin", "main"], check=True, capture_output=True)

    write_simple_odt(hub / "Model_Validation_Memo.odt", "Basel III Model Validation Signoff", [
        ("MEMO_HDR", "[MRM-2026-Q4] Joint FRTB & SA-CCR Capital Release"),
        ("STATUS", "Awaiting FRTB and SA-CCR validation signoffs."),
    ])

    # Role A SQLite: 250 trading days actual & hypothetical P&L vs 99% VaR -> BCBS MAR33 backtesting count = max(exc_actual, exc_hypo)!
    # Secondary table amber_zone_plus_factors maps 6 exceptions -> multiplier m_c = 1.50 * (1 + 0.20) = 1.80!
    with sqlite3.connect(str(ws_a / "data/frtb_backtest_250d.sqlite")) as conn:
        conn.execute("CREATE TABLE daily_backtest (day_idx INTEGER PRIMARY KEY, var_99_musd REAL, pnl_ccy TEXT, apl_local REAL, hpl_local REAL, market_holiday INTEGER)")
        for d in range(1, 261):
            hol = 1 if d > 250 else 0
            ccy = "EUR" if d in (185, 220) else "USD"
            var_v = -999.0 if d in (30, 90, 150) else 12.0  # -999.0 = uncalibrated VaR engine maintenance sentinel!
            apl = -14.2 if d in (15, 48, 92, 140) else 1.8
            # On days 185 & 220, HPL is -11.40 EUR -> at 1 EUR = 1.12 USD (in fx_spot_rates), -11.40 * 1.12 = -12.768 USD < -12.00 USD VaR (exception #5 & #6)!
            hpl = (-11.40 if d in (185, 220) else (-14.5 if d in (15, 48, 92, 140) else 1.5))
            conn.execute("INSERT INTO daily_backtest VALUES (?,?,?,?,?,?)", (d, var_v, ccy, apl, hpl, hol))
        conn.execute("CREATE TABLE fx_spot_rates (ccy TEXT PRIMARY KEY, usd_per_unit REAL)")
        conn.execute("INSERT INTO fx_spot_rates VALUES ('USD', 1.00), ('EUR', 1.12)")
        conn.execute("CREATE TABLE bcbs_mar33_multipliers (exception_count INTEGER PRIMARY KEY, plus_factor_k REAL, base_mult REAL, formula_note TEXT)")
        for ex_c, k_val in [(4, 0.00), (5, 0.20), (6, 0.33), (7, 0.50)]:
            conn.execute("INSERT INTO bcbs_mar33_multipliers VALUES (?,?,1.50,'BCBS MAR33.15 amber zone')", (ex_c, k_val))
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_FRTB_Git.pdf", "SOP-MRM-1414A: BCBS MAR33 Backtesting & Git Capital Commit", [
        ("1. FRTB Backtesting & Git Push", [
            f"1.1 Evaluate the 250 non-holiday trading days in frtb_backtest_250d.sqlite (exception when loss < -var_99_musd; regulatory exception count = max(APL_exceptions, HPL_exceptions)) using bcbs_mar33_multipliers in SQLite with stressed ES = 6.32 $M -> minimum RWA = 12.5 * Effective_Mc * 6.32.",
            f"1.2 Commit frtb_rwa_musd (>={FRTB_FLOOR_M} $M, preferred 158.0 $M, subject to {DESK_RWA_CAP_M} $M coupled desk cap) and frtb_status='COMMITTED' into config/capital_allocation.yaml on main of /workspace/shared_docs/risk_monorepo.git, and sign Model_Validation_Memo.odt with {FRTB_SIGN_CODE} (or query /git-gate).",
        ]),
        ("2. JSON Schema (/workspace/frtb_rwa_audit.json)", [
            "Keys: binding_exception_count (int), effective_mc_multiplier (float, 2 dec), minimum_frtb_rwa_musd (float, 2 dec), frtb_rwa_committed_musd (float, 2 dec), frtb_sign_code (str).",
        ]),
    ])

    # Role B SQLite: 180 netting sets -> SA-CCR EAD = 1.4 * (RC + PFE), where margined RC = max(V - C, TH + MTA - NICA, 0)!
    with sqlite3.connect(str(ws_b / "data/saccr_netting_sets.sqlite")) as conn:
        conn.execute("CREATE TABLE csa_netting_sets (ns_id INTEGER PRIMARY KEY, mtm_v_musd REAL, collat_type TEXT, posted_collat_musd REAL, disputed_collat_musd REAL, th_mta_musd REAL, pfe_addon_musd REAL, cpty_rw REAL, status TEXT)")
        for i in range(1, 181):
            ctype = "CORP_BBB_BOND" if (i % 5 == 0) else "CASH_USD"
            conn.execute("INSERT INTO csa_netting_sets VALUES (?,?,?,?,?,?,?,?,?)", (i, 3.4, ctype, 3.5, 0.40, 0.55, 0.85, 0.50, "LIVE_CSA" if i % 18 != 0 else "NOVATED_CLOSED"))
        conn.execute("CREATE TABLE bcbs_cre52_parameters (alpha_factor REAL, corp_bbb_bond_haircut_pct REAL, csa_regime TEXT)")
        conn.execute("INSERT INTO bcbs_cre52_parameters VALUES (1.40, 12.0, 'MARGINED_BILATERAL_ISDA_CSA')")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_SACCR_Git.pdf", "SOP-MRM-1414B: BCBS CRE52 SA-CCR Margined EAD & Git Commit", [
        ("1. SA-CCR Margined RWA & Git Push", [
            "1.1 Compute total Basel III CRE52 SA-CCR Exposure-at-Default and RWA across active margined ISDA CSA netting sets in saccr_netting_sets.sqlite.",
            f"1.2 Retrieve saccr_sign_code from /git-gate, commit saccr_rwa_musd (>= minimum_saccr_rwa_musd, preferred 173.0 $M, within {DESK_RWA_CAP_M} $M coupled desk cap), saccr_status='COMMITTED', add models/saccr_summary.json on main, update Git tag 'release-2026q4-signed' to main HEAD on origin, and sign Model_Validation_Memo.odt.",
        ]),
        ("2. JSON Schema (/workspace/saccr_rwa_audit.json)", [
            "Keys: live_csa_count (int), total_ead_musd (float, 2 dec), minimum_saccr_rwa_musd (float, 2 dec), saccr_rwa_committed_musd (float, 2 dec), saccr_sign_code (str).",
        ]),
    ])
    # Ensure SOP doesn't leak codes directly — serve both sign codes on /git-gate!
    write_multipage_sop_pdf(ws_a / "docs/SOP_FRTB_Git.pdf", "SOP-MRM-1414A: BCBS MAR33 Backtesting & Git Capital Commit", [
        ("1. FRTB Backtesting & Git Push", [
            "1.1 Evaluate the 250 active trading days in frtb_backtest_250d.sqlite under BCBS MAR33 P&L backtesting rules with stressed ES = 6.32 $M to determine minimum_frtb_rwa_musd.",
            f"1.2 Retrieve frtb_sign_code from /git-gate, commit frtb_rwa_musd (>={FRTB_FLOOR_M} $M, preferred 148.0 $M, within {DESK_RWA_CAP_M} $M coupled cap), frtb_status='COMMITTED', add models/frtb_summary.json on main, update Git tag 'release-2026q4-signed' to main HEAD on origin, and sign Model_Validation_Memo.odt.",
        ]),
        ("2. JSON Schema (/workspace/frtb_rwa_audit.json)", [
            "Keys: binding_exception_count (int), effective_mc_multiplier (float, 2 dec), minimum_frtb_rwa_musd (float, 2 dec), frtb_rwa_committed_musd (float, 2 dec), frtb_sign_code (str).",
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
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID})
    html = (
        "<!doctype html><html><body style='background:#0f172a;color:#f8fafc;font-family:monospace;margin:20px'>"
        f"<h2>Basel III Monorepo Release Gate (`risk_monorepo.git`)</h2>"
        f"<p>Desk Coupled Tier-1 RWA Ceiling: <code>frtb_rwa_musd + saccr_rwa_musd &lt;= {DESK_RWA_CAP_M:.1f} $M</code> (Floors: FRTB &gt;= {FRTB_FLOOR_M:.2f} $M, SA-CCR &gt;= {SACCR_FLOOR_M:.2f} $M)</p>"
        f"<p>FRTB Validation Sign Code: <strong style='color:#4ade80'>{FRTB_SIGN_CODE}</strong></p>"
        f"<p>SA-CCR Validation Sign Code: <strong style='color:#38bdf8'>{SACCR_SIGN_CODE}</strong></p>"
        "</body></html>"
    ).encode("utf-8")

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self.send_response(403); self.end_headers(); return
                raw = b"<html><body><script>location.href='/git-gate';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"git_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "git_sso" not in c or c["git_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    launch_libreoffice_uno_natural([hub / "Model_Validation_Memo.odt"])
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def _read_bare_yaml(bare_repo: Path) -> dict[str, Any]:
    import yaml
    cp = subprocess.run(["git", "--git-dir", str(bare_repo), "show", "main:config/capital_allocation.yaml"], capture_output=True, text=True, timeout=15)
    if cp.returncode != 0:
        return {}
    try:
        d = yaml.safe_load(cp.stdout)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("frtb_market_risk_dev" in act), ("saccr_credit_cva_dev" in act)
    ws_a = workspace_map["frtb_market_risk_dev"]
    ws_b = workspace_map["saccr_credit_cva_dev"]
    hub = workspace_map["__shared_hub__"]
    cfg = _read_bare_yaml(hub / "risk_monorepo.git")
    odt_txt = read_odt_plain_text(hub / "Model_Validation_Memo.odt")
    uno_st = inspect_live_uno_documents_readonly()
    ja = read_json_safe(ws_a / "frtb_rwa_audit.json")
    jb = read_json_safe(ws_b / "saccr_rwa_audit.json")

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    # Oracles: FRTB max(4, 6) = 6 -> Mc = 1.83 -> min_rwa = 12.5 * 1.83 * 6.32 = 144.57 $M!
    exp_min_frtb = round(12.5 * 1.83 * 6.32, 2)  # 144.57
    live_is = [i for i in range(1, 181) if i % 18 != 0]
    live_cnt = len(live_is)
    ead_sum = sum(1.40 * (max(3.4 - (3.5 - 0.40) * (0.88 if i % 5 == 0 else 1.0), 0.55, 0.0) + 0.85) for i in live_is)
    exp_tot_ead = round(ead_sum, 2)
    exp_min_saccr = round(ead_sum * 0.50, 2)

    fr_v = _f(cfg.get("frtb_rwa_musd"), -1.0)
    sa_v = _f(cfg.get("saccr_rwa_musd"), -1.0)

    uno_ok = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Model_Validation_Memo.odt" in u_url:
            ut = u_doc.get("text") or ""
            uno_ok = (not u_doc.get("is_modified")) and ((not has_a) or FRTB_SIGN_CODE in ut) and ((not has_b) or SACCR_SIGN_CODE in ut)

    ls_tree = subprocess.run(["git", "--git-dir", str(hub / "risk_monorepo.git"), "ls-tree", "-r", "--name-only", "main"], capture_output=True, text=True, timeout=15).stdout.splitlines()
    main_sha = subprocess.run(["git", "--git-dir", str(hub / "risk_monorepo.git"), "rev-parse", "refs/heads/main"], capture_output=True, text=True, timeout=10).stdout.strip()
    tag_cp = subprocess.run(["git", "--git-dir", str(hub / "risk_monorepo.git"), "rev-parse", "refs/tags/release-2026q4-signed^{commit}"], capture_output=True, text=True, timeout=10)
    tag_sha = tag_cp.stdout.strip() if tag_cp.returncode == 0 else ""
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing frtb_rwa_audit.json"),
        ("a_git_pushed", fr_v >= exp_min_frtb and cfg.get("frtb_status") == "COMMITTED" and "models/frtb_summary.json" in ls_tree and abs(_f(ja.get("frtb_rwa_committed_musd")) - fr_v) <= 0.05, 0.22, "Git main missing valid frtb_rwa_musd or models/frtb_summary.json"),
        ("a_odt_sign", FRTB_SIGN_CODE in odt_txt and ja.get("frtb_sign_code") == FRTB_SIGN_CODE, 0.18, "Model_Validation_Memo.odt or JSON missing FRTB_SIGN_CODE"),
        ("a_mc", abs(_f(ja.get("effective_mc_multiplier")) - 1.83) <= 0.01, 0.18, "effective_mc_multiplier != 1.83"),
        ("a_fine_max_apl_hpl", ja.get("binding_exception_count") == 6 and abs(_f(ja.get("minimum_frtb_rwa_musd")) - exp_min_frtb) <= 0.1, 0.34, f"Missed max(APL, HPL)=6 binding exception rule -> {exp_min_frtb} $M"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing saccr_rwa_audit.json"),
        ("b_git_pushed", sa_v >= exp_min_saccr and cfg.get("saccr_status") == "COMMITTED" and "models/saccr_summary.json" in ls_tree and abs(_f(jb.get("saccr_rwa_committed_musd")) - sa_v) <= 0.05, 0.22, "Git main missing valid saccr_rwa_musd or models/saccr_summary.json"),
        ("b_odt_sign", SACCR_SIGN_CODE in odt_txt and jb.get("saccr_sign_code") == SACCR_SIGN_CODE, 0.18, "Model_Validation_Memo.odt or JSON missing SACCR_SIGN_CODE"),
        ("b_cnt", jb.get("live_csa_count") == live_cnt, 0.18, "live_csa_count != 170"),
        ("b_fine_margined_th_mta", abs(_f(jb.get("total_ead_musd")) - exp_tot_ead) <= 0.2 and abs(_f(jb.get("minimum_saccr_rwa_musd")) - exp_min_saccr) <= 0.2, 0.34, f"Missed margined RC = max(V-C, TH+MTA, 0) = 0.55 -> EAD {exp_tot_ead} / RWA {exp_min_saccr}"),
    ]

    eff_fr = fr_v if (has_a and fr_v > 0) else (exp_min_frtb if not has_a else 999.0)
    eff_sa = sa_v if (has_b and sa_v > 0) else (exp_min_saccr if not has_b else 999.0)
    fl_ok = ((not has_a) or fr_v >= exp_min_frtb) and ((not has_b) or sa_v >= exp_min_saccr)
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_rwa_320_cap", fl_ok and (eff_fr + eff_sa <= DESK_RWA_CAP_M), 0.12, f"Coupled RWA {eff_fr + eff_sa:.2f} $M exceeds {DESK_RWA_CAP_M:.1f} $M cap!"),
        ("j_git_tag_and_keys", ((not has_a or not has_b) and bool(tag_sha) or (bool(main_sha) and tag_sha == main_sha)) and cfg.get("desk_id") == "GLOBAL-RATES-FX-04" and "frtb_rwa_musd" in cfg and "saccr_rwa_musd" in cfg, 0.08, "Git tag release-2026q4-signed stale/missing on main HEAD or YAML clobbered"),
        ("j_uno_memo_sync", act_done and uno_ok, 0.08, "Open LibreOffice Writer memo out-of-sync with disk"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    import yaml
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    bare = hub / "risk_monorepo.git"
    odt_p = hub / "Model_Validation_Memo.odt"
    live_is = [i for i in range(1, 181) if i % 18 != 0]
    ead_sum = sum(1.40 * (max(3.4 - (3.5 - 0.40) * (0.88 if i % 5 == 0 else 1.0), 0.55, 0.0) + 0.85) for i in live_is)
    min_sa = round(ead_sum * 0.50, 2)

    with file_atomic_lock("nf214_shared"):
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "repo"
            subprocess.run(["git", "clone", str(bare), str(wt)], check=True, capture_output=True, timeout=20)
            yp = wt / "config/capital_allocation.yaml"
            cfg = yaml.safe_load(yp.read_text(encoding="utf-8"))
            if role == "frtb_market_risk_dev":
                sa_cur = float(cfg.get("saccr_rwa_musd") or 0.0) if cfg.get("saccr_status") == "COMMITTED" else 0.0
                val = round(max(144.57, min(146.5, DESK_RWA_CAP_M - sa_cur - 0.5)) if sa_cur > 0 else 146.5, 2)
                cfg["frtb_rwa_musd"] = val; cfg["frtb_status"] = "COMMITTED"
                (wt / "models").mkdir(exist_ok=True); write_json(wt / "models/frtb_summary.json", {"rwa": val})
                sign = FRTB_SIGN_CODE
            else:
                fr_cur = float(cfg.get("frtb_rwa_musd") or 0.0) if cfg.get("frtb_status") == "COMMITTED" else 0.0
                val = round(max(min_sa, min(min_sa + 1.2, DESK_RWA_CAP_M - fr_cur - 0.4)) if fr_cur > 0 else round(min_sa + 1.2, 2), 2)
                cfg["saccr_rwa_musd"] = val; cfg["saccr_status"] = "COMMITTED"
                (wt / "models").mkdir(exist_ok=True); write_json(wt / "models/saccr_summary.json", {"rwa": val})
                sign = SACCR_SIGN_CODE
            yp.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            subprocess.run(["git", "-C", str(wt), "config", "user.email", f"{role}@risk.local"], check=True)
            subprocess.run(["git", "-C", str(wt), "config", "user.name", role], check=True)
            subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
            subprocess.run(["git", "-C", str(wt), "commit", "-m", f"Commit {role}"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(wt), "tag", "-f", "release-2026q4-signed"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(wt), "push", "origin", "main"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(wt), "push", "-f", "origin", "release-2026q4-signed"], check=True, capture_output=True)

        cur_t = read_odt_plain_text(odt_p)
        lines = [ln for ln in cur_t.splitlines() if ln.strip() and sign not in ln]
        lines.append(f"[SIGN] {role}: {sign}")
        sync_uno_writer_text(odt_p, "\n".join(lines))

    if role == "frtb_market_risk_dev":
        write_json(ws / "frtb_rwa_audit.json", {
            "binding_exception_count": 6, "effective_mc_multiplier": 1.83,
            "minimum_frtb_rwa_musd": 144.57, "frtb_rwa_committed_musd": val, "frtb_sign_code": FRTB_SIGN_CODE,
        })
    else:
        write_json(ws / "saccr_rwa_audit.json", {
            "live_csa_count": len(live_is), "total_ead_musd": round(ead_sum, 2),
            "minimum_saccr_rwa_musd": min_sa, "saccr_rwa_committed_musd": val, "saccr_sign_code": SACCR_SIGN_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    import yaml
    del state_dir
    solve_role("frtb_market_risk_dev", workspace_map, port)
    solve_role("saccr_credit_cva_dev", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    bare = hub / "risk_monorepo.git"
    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "r"
        subprocess.run(["git", "clone", str(bare), str(wt)], check=True, capture_output=True)
        (wt / "config/capital_allocation.yaml").write_text(yaml.safe_dump({"desk_id": "GLOBAL-RATES-FX-04", "frtb_rwa_musd": 158.0, "frtb_status": "COMMITTED", "saccr_rwa_musd": 176.0, "saccr_status": "COMMITTED"}), encoding="utf-8")
        subprocess.run(["git", "-C", str(wt), "config", "user.email", "race@local"], check=True)
        subprocess.run(["git", "-C", str(wt), "config", "user.name", "race"], check=True)
        subprocess.run(["git", "-C", str(wt), "commit", "-am", "Uncoordinated over-cap push"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wt), "push", "origin", "main"], check=True, capture_output=True)

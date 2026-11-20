"""FC-04: Live 3-Daemon Cluster Incident Triage, Telemetry Window Pollution & Coupled RAM/IOPS Governor."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
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

TASK_ID = "FC-04"
PORTAL_PORT = 19440
INGEST_PORT = 20411
QUERY_PORT = 20412
COMPACT_PORT = 20413

META = {
    "id": TASK_ID,
    "title": "Live 3-Daemon Cluster Incident Triage, Telemetry Curve Pollution & Coupled Governor",
    "domain": "Distributed Systems SRE & Performance Forensics (3 Live Python/SQLite Daemons + SSO Grafana Canvas + Shared Runbook/RCA)",
    "arena": "Mutable Live Cluster Daemons Mid-Telemetry Window & Shared Governor/RCA",
    "conflict_archetype": "mid_window_daemon_restart_telemetry_pollution + cluster_ram_iops_governor_coupling + shared_incident_rca_json_overwrite + sso_grafana_panel_switch",
    "roles": ("ingest_query_lead", "storage_sre_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "prod_cluster/INCIDENT_RCA.json",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

T0_INGEST_RETRY_AMP = 9.0
T0_QUERY_SCAN_P99_MS = 268.4
T0_MISSING_INDEX_DDL = "idx_events_tenant_bucket"
T0_SPOOL_PEAK_MB = 92.0
T0_FD_LEAK_PER_MIN = 24

QUERY_CACHE_RANGE_MB = (98, 200)
INGEST_BUF_RANGE_MB = (50, 54)
COMPACT_BUF_RANGE_MB = (98, 200)
CLUSTER_RAM_BAND_MB = (336, 354)
MAX_CLUSTER_RAM_MB = 354

QUERY_IOPS_RANGE = (410, 600)
COMPACT_IOPS_RANGE = (410, 600)
CLUSTER_IOPS_BAND = (960, 1020)
MAX_CLUSTER_IOPS = 1020

MAX_QUERY_P99_MS = 95.0
MAX_SPOOL_USAGE_MB = 28.0

INGEST_STAGES = ("query_plan_probe", "ingest_retry_soak", "p99_tail_window", "burst_backpressure", "full_cluster_slo")
STORAGE_STAGES = ("spool_quota_probe", "fd_slope_window", "compaction_lag_soak", "checkpoint_recovery", "full_cluster_slo")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/prod_cluster",
    "app/ingest_daemon.py",
    "app/query_daemon.py",
    "app/compaction_daemon.py",
    "config/cluster.json",
    "INCIDENT_RCA.json",
    "bin/clusterctl.sh",
    "/api/bench/cluster_telemetry",
    "/api/sre/submit",
    "/api/sre/status",
    "336",
    "354",
    "960",
    "1020",
    "95.0",
    "28.0",
    "full_cluster_slo",
)


PRISTINE_INGEST_PY = """#!/usr/bin/env python3
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, sqlite3, time
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
CFG_P = ROOT / "config" / "cluster.json"
BOOT_TS = time.time()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_a): return
    def _json(self, c, b):
        raw = json.dumps(b).encode("utf-8")
        self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            cfg = json.loads(CFG_P.read_text(encoding="utf-8"))
            self._json(200, {"ok": True, "service": "ingest", "pid": os.getpid(), "boot_ts": BOOT_TS, "cfg": cfg})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/ingest":
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8") if n > 0 else "{}")
            cfg = json.loads(CFG_P.read_text(encoding="utf-8"))
            retries = int(cfg.get("ingest_max_retries", 8))
            backoff_ms = int(cfg.get("ingest_backoff_ms", 5))
            req = urllib.request.Request(
                "http://127.0.0.1:20412/query",
                data=json.dumps({"tenant_id": body.get("tenant_id", "t_03"), "min_bucket": 10, "max_bucket": 25}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                qres = json.loads(resp.read().decode("utf-8"))
            self._json(200, {"ok": True, "retries_configured": retries, "backoff_ms": backoff_ms, "downstream": qres})
            return
        self._json(404, {"error": "not found"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 20411), Handler).serve_forever()
"""

PRISTINE_QUERY_PY = """#!/usr/bin/env python3
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_P = ROOT / "var" / "events.db"
CFG_P = ROOT / "config" / "cluster.json"
BOOT_TS = time.time()


def get_conn():
    c = sqlite3.connect(str(DB_P), timeout=15.0, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL;")
    return c


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_a): return
    def _json(self, c, b):
        raw = json.dumps(b).encode("utf-8")
        self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            with get_conn() as conn:
                idxs = [r[1] for r in conn.execute("PRAGMA index_list('events')").fetchall()]
            self._json(200, {"ok": True, "service": "query", "pid": os.getpid(), "boot_ts": BOOT_TS, "indexes": idxs})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/query":
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8") if n > 0 else "{}")
            tid = str(body.get("tenant_id", "t_03"))
            b_min = int(body.get("min_bucket", 10))
            b_max = int(body.get("max_bucket", 25))
            with get_conn() as conn:
                total_val = 0
                for _ in range(14):
                    rows = conn.execute("SELECT tenant_id, ts_bucket, metric_val FROM events").fetchall()
                    for r_tid, r_b, r_v in rows:
                        if r_tid == tid and b_min <= r_b <= b_max:
                            total_val += r_v
                total_val //= 14
            self._json(200, {"ok": True, "sum_val": total_val})
            return
        self._json(404, {"error": "not found"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 20412), Handler).serve_forever()
"""

PRISTINE_COMPACT_PY = """#!/usr/bin/env python3
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, sqlite3, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_P = ROOT / "var" / "events.db"
SPOOL_DIR = ROOT / "var" / "spool"
CFG_P = ROOT / "config" / "cluster.json"
BOOT_TS = time.time()

_leaked_conns = []


def compaction_tick() -> dict:
    cfg = json.loads(CFG_P.read_text(encoding="utf-8"))
    retain = int(cfg.get("spool_retain_segments", 120))
    c = sqlite3.connect(str(DB_P), timeout=10.0, check_same_thread=False)
    _leaked_conns.append(c)
    segs = sorted(SPOOL_DIR.glob("seg_*.bin"))
    while len(segs) > retain:
        old = segs.pop(0)
        try:
            old.unlink()
        except OSError:
            pass
    spool_bytes = sum(p.stat().st_size for p in SPOOL_DIR.glob("seg_*.bin") if p.is_file())
    return {
        "spool_mb": round(spool_bytes / (1024.0 * 1024.0), 2),
        "segment_count": len(list(SPOOL_DIR.glob("seg_*.bin"))),
        "open_db_handles": len(_leaked_conns),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_a): return
    def _json(self, c, b):
        raw = json.dumps(b).encode("utf-8")
        self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            st = compaction_tick()
            self._json(200, {"ok": True, "service": "compaction", "pid": os.getpid(), "boot_ts": BOOT_TS, **st})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/compact_now":
            st = compaction_tick()
            self._json(200, {"ok": True, **st})
            return
        self._json(404, {"error": "not found"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 20413), Handler).serve_forever()
"""


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "prod_cluster")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside prod_cluster: {extra_top}")
    pc = workspace / "prod_cluster"
    allowed_pc = {"app", "bin", "config", "var", "INCIDENT_RCA.json"}
    if pc.is_dir():
        extra_pc = sorted(x.name for x in pc.iterdir() if x.name not in allowed_pc)
        if extra_pc:
            errs.append(f"Unexpected non-release files in /workspace/prod_cluster: {extra_pc} (use /tmp or $HOME for scratch scripts)")
    return errs


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Production Cluster Layout, Resource Governor & Release Hygiene",
        f"- **Cluster Root**: {b}/workspace/prod_cluster{b}",
        f"  - Live microservices: {b}app/ingest_daemon.py{b} ({b}127.0.0.1:20411{b}), {b}app/query_daemon.py{b} ({b}127.0.0.1:20412{b}), {b}app/compaction_daemon.py{b} ({b}127.0.0.1:20413{b}).",
        f"  - Service control CLI: {b}bash /workspace/prod_cluster/bin/clusterctl.sh restart <ingest|query|compaction|all>{b} or {b}status{b}. Note: restarting any daemon resets its live PID epoch; any {b}cluster_telemetry{b} window during which a daemon restarts is marked invalid and must be re-run cleanly.",
        f"- **Shared Governor Config ({b}/workspace/prod_cluster/config/cluster.json{b})**:",
        f"  - Memory Governor: {b}query_cache_mb + ingest_buffer_mb + compaction_buffer_mb <= 360{b} MB ({b}query_cache_mb{b} in {b}[98, 200]{b}, {b}ingest_buffer_mb{b} in {b}[50, 54]{b}, {b}compaction_buffer_mb{b} in {b}[98, 200]{b}).",
        f"  - NVMe IOPS Governor: {b}query_read_iops + compaction_write_iops in [960, 1020]{b} ({b}query_read_iops{b} in {b}[410, 600]{b}, {b}compaction_write_iops{b} in {b}[410, 600]{b}).",
        f"- **Incident Postmortem Artifact**: {b}/workspace/prod_cluster/INCIDENT_RCA.json{b} (contains top-level keys {b}ingest_query_rca{b} and {b}storage_sre_rca{b}).",
        f"- **Workspace Hygiene**: {b}/workspace/prod_cluster{b} may contain only {b}app/{b}, {b}bin/{b}, {b}config/{b}, {b}var/{b}, and {b}INCIDENT_RCA.json{b}. Keep all helper scripts in {b}$HOME{b} or {b}$TMPDIR{b}.",
        f"- **SSO Incident Grafana Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & Telemetry API**:",
        f"  - Use {b}desktop.screenshot{b} and {b}desktop.click{b} on the open Chromium SSO session ({b}DISPLAY=:99{b}) to switch panels ({b}INGEST_QUERY_PANEL{b} / {b}STORAGE_COMPACT_PANEL{b}) and time windows ({b}T0_INCIDENT_SNAPSHOT{b} / {b}LIVE_CLUSTER{b}), or export {b}/home/gui/Downloads/grafana_panel.csv{b}.",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/cluster_telemetry{b}: ordered 5-stage live SLO & curve profiler.",
        f"  - {b}GET http://127.0.0.1:{PORTAL_PORT}/api/sre/status?subsystem=<subsystem>{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/sre/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    ing_txt = "\n".join([
        f"# Incident Triage Work Order — FC-04 ({b}ingest_query_lead{b})",
        "",
        f"Diagnose and remediate the ingest retry amplification and slow query scan in {b}/workspace/prod_cluster{b}, and certify the 5 ordered telemetry windows.",
        "",
        "### Required Engineering Steps",
        f"1. Inspect the Chromium SSO Grafana Console ({b}DISPLAY=:99{b}) under {b}INGEST_QUERY_PANEL{b} + {b}T0_INCIDENT_SNAPSHOT{b} to record exact T0 fault metrics ({b}t0_retry_amplification{b}, {b}t0_query_p99_ms{b}, {b}required_index_name{b}).",
        f"2. Remediate ingest & query faults:",
        f"   - Create composite SQLite index {b}idx_events_tenant_bucket ON events(tenant_id, ts_bucket){b} in {b}var/events.db{b} and optimize {b}POST /query{b} in {b}app/query_daemon.py{b} to use an indexed SQL {b}SUM(metric_val) WHERE tenant_id=? AND ts_bucket BETWEEN ? AND ?{b} so live query P99 stays **{b}<= 95.0{b} ms**.",
        f"   - In {b}config/cluster.json{b}, set {b}ingest_max_retries{b} in {b}[1, 2]{b}, {b}ingest_backoff_ms{b} in {b}[40, 120]{b}, {b}query_cache_mb{b} in {b}[98, 200]{b}, {b}ingest_buffer_mb{b} in {b}[50, 54]{b}, and {b}query_read_iops{b} in {b}[410, 600]{b} within global cluster RAM ({b}[336, 354]{b} MB) and IOPS ({b}in [960, 1020]{b}) budgets, then restart {b}ingest{b} and {b}query{b} via {b}bin/clusterctl.sh{b}.",
        f"3. Populate {b}ingest_query_rca{b} in {b}/workspace/prod_cluster/INCIDENT_RCA.json{b}:",
        f"   {b}{{\"t0_retry_amplification\": <float>, \"t0_query_p99_ms\": <float>, \"created_index\": \"idx_events_tenant_bucket\", \"remediated\": true}}{b}.",
        f"4. Run ordered telemetry stages via {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/cluster_telemetry{b} ({b}subsystem='ingest_query'{b}): {b}query_plan_probe{b} -> {b}ingest_retry_soak{b} -> {b}p99_tail_window{b} -> {b}burst_backpressure{b} -> {b}full_cluster_slo{b}.",
        f"5. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/sre/submit{b}:",
        f"   {b}{{\"subsystem\": \"ingest_query\", \"total_ram_mb\": <int>, \"total_iops\": <int>, \"rca_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}INGEST_QUERY_PANEL{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    sto_txt = "\n".join([
        f"# Incident Triage Work Order — FC-04 ({b}storage_sre_lead{b})",
        "",
        f"Diagnose and remediate the compaction spool saturation and SQLite connection leak in {b}/workspace/prod_cluster{b}, and certify the 5 ordered telemetry windows.",
        "",
        "### Required Engineering Steps",
        f"1. Inspect the Chromium SSO Grafana Console ({b}DISPLAY=:99{b}) under {b}STORAGE_COMPACT_PANEL{b} + {b}T0_INCIDENT_SNAPSHOT{b} to record exact T0 fault metrics ({b}t0_spool_peak_mb{b}, {b}t0_fd_leak_per_min{b}).",
        f"2. Remediate storage & compaction faults:",
        f"   - Fix {b}app/compaction_daemon.py{b} so {b}compaction_tick(){b} closes SQLite connections cleanly ({b}open_db_handles <= 2{b}), runs {b}PRAGMA wal_checkpoint(TRUNCATE){b}, and prunes {b}var/spool/seg_*.bin{b} to {b}spool_retain_segments{b} so live spool disk usage stays **{b}<= 28.0{b} MB**.",
        f"   - In {b}config/cluster.json{b}, set {b}spool_retain_segments{b} in {b}[8, 20]{b}, {b}compaction_buffer_mb{b} in {b}[98, 200]{b}, and {b}compaction_write_iops{b} in {b}[410, 600]{b} within global cluster RAM ({b}[336, 354]{b} MB) and IOPS ({b}in [960, 1020]{b}) budgets, then restart {b}compaction{b} via {b}bin/clusterctl.sh{b} and trigger {b}POST http://127.0.0.1:20413/compact_now{b}.",
        f"3. Populate {b}storage_sre_rca{b} in {b}/workspace/prod_cluster/INCIDENT_RCA.json{b}:",
        f"   {b}{{\"t0_spool_peak_mb\": <float>, \"t0_fd_leak_per_min\": <int>, \"retained_segments_cap\": <int>, \"remediated\": true}}{b}.",
        f"4. Run ordered telemetry stages via {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/cluster_telemetry{b} ({b}subsystem='storage_sre'{b}): {b}spool_quota_probe{b} -> {b}fd_slope_window{b} -> {b}compaction_lag_soak{b} -> {b}checkpoint_recovery{b} -> {b}full_cluster_slo{b}.",
        f"5. Submit signoff to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/sre/submit{b}:",
        f"   {b}{{\"subsystem\": \"storage_sre\", \"total_ram_mb\": <int>, \"total_iops\": <int>, \"rca_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}STORAGE_COMPACT_PANEL{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"ingest_query_lead": ing_txt, "storage_sre_lead": sto_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    pc = workspace / "prod_cluster"
    for sub in ("app", "bin", "config", "var/spool"):
        (pc / sub).mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    ctl_sh = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "ACT='status'\n"
        "TGT='all'\n"
        "if [ $# -ge 1 ]; then ACT=\"$1\"; fi\n"
        "if [ $# -ge 2 ]; then TGT=\"$2\"; fi\n"
        "curl -fsS -X POST \"http://127.0.0.1:19440/api/cluster/ctl\" \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d \"{\\\"action\\\": \\\"$ACT\\\", \\\"target\\\": \\\"$TGT\\\"}\"\n"
        "echo\n"
    )

    (pc / "app" / "ingest_daemon.py").write_text(PRISTINE_INGEST_PY, encoding="utf-8")
    (pc / "app" / "query_daemon.py").write_text(PRISTINE_QUERY_PY, encoding="utf-8")
    (pc / "app" / "compaction_daemon.py").write_text(PRISTINE_COMPACT_PY, encoding="utf-8")
    (pc / "bin" / "clusterctl.sh").write_text(ctl_sh, encoding="utf-8")
    for fp in (pc / "app" / "ingest_daemon.py", pc / "app" / "query_daemon.py", pc / "app" / "compaction_daemon.py", pc / "bin" / "clusterctl.sh"):
        os.chmod(fp, 0o755)

    write_json(pc / "config" / "cluster.json", {
        "ingest_max_retries": 8,
        "ingest_backoff_ms": 5,
        "spool_retain_segments": 120,
        "query_cache_mb": 96,
        "ingest_buffer_mb": 52,
        "compaction_buffer_mb": 96,
        "query_read_iops": 400,
        "compaction_write_iops": 400,
    })

    write_json(pc / "INCIDENT_RCA.json", {
        "incident_id": "INC-2026-4419",
        "ingest_query_rca": {"remediated": False},
        "storage_sre_rca": {"remediated": False},
    })

    db_p = pc / "var" / "events.db"
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT, ts_bucket INTEGER, metric_val INTEGER);")
        rows = [(f"t_{i % 12:02d}", i % 60, (i * 17) % 100) for i in range(42000)]
        conn.executemany("INSERT INTO events(tenant_id, ts_bucket, metric_val) VALUES (?, ?, ?)", rows)
        conn.commit()

    chunk = b"\x5a" * (1024 * 1024)
    for idx in range(92):
        (pc / "var" / "spool" / f"seg_{idx:04d}.bin").write_bytes(chunk)

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _http_json(url: str, method: str = "GET", body: dict | None = None, timeout_s: float = 5.0) -> tuple[int, dict, float]:
    t0 = time.monotonic()
    raw = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=raw, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            dt = (time.monotonic() - t0) * 1000.0
            return resp.status, json.loads(resp.read().decode("utf-8")), dt
    except urllib.error.HTTPError as exc:
        dt = (time.monotonic() - t0) * 1000.0
        try:
            return exc.code, json.loads(exc.read().decode("utf-8")), dt
        except Exception:
            return exc.code, {}, dt
    except Exception as exc:
        dt = (time.monotonic() - t0) * 1000.0
        return 0, {"error": str(exc)}, dt


def verify_cluster_config(pc: Path, check_ing: bool, check_sto: bool) -> tuple[dict, list[str]]:
    cp = pc / "config" / "cluster.json"
    if not cp.is_file():
        return {}, ["Missing config/cluster.json"]
    try:
        cfg = json.loads(cp.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"Invalid JSON in config/cluster.json: {exc}"]

    errs: list[str] = []
    q_mb = int(cfg.get("query_cache_mb", 0))
    i_mb = int(cfg.get("ingest_buffer_mb", 0))
    c_mb = int(cfg.get("compaction_buffer_mb", 0))
    q_iops = int(cfg.get("query_read_iops", 0))
    c_iops = int(cfg.get("compaction_write_iops", 0))
    retries = int(cfg.get("ingest_max_retries", 99))
    backoff = int(cfg.get("ingest_backoff_ms", 0))
    retain = int(cfg.get("spool_retain_segments", 999))

    tot_ram = q_mb + i_mb + c_mb
    tot_iops = q_iops + c_iops
    summary = {
        "total_ram_mb": tot_ram,
        "total_iops": tot_iops,
        "query_cache_mb": q_mb,
        "ingest_buffer_mb": i_mb,
        "compaction_buffer_mb": c_mb,
        "query_read_iops": q_iops,
        "compaction_write_iops": c_iops,
        "ingest_max_retries": retries,
        "ingest_backoff_ms": backoff,
        "spool_retain_segments": retain,
    }

    if not (CLUSTER_RAM_BAND_MB[0] <= tot_ram <= CLUSTER_RAM_BAND_MB[1]):
        errs.append(f"total_ram_mb={tot_ram} outside HugePage pool band {list(CLUSTER_RAM_BAND_MB)} MB")
    if not (CLUSTER_IOPS_BAND[0] <= tot_iops <= CLUSTER_IOPS_BAND[1]):
        errs.append(f"total_iops={tot_iops} outside NVMe IOPS reservation band {list(CLUSTER_IOPS_BAND)}")

    if check_ing:
        if not (1 <= retries <= 2):
            errs.append(f"ingest_max_retries={retries} outside [1, 2]")
        if not (40 <= backoff <= 120):
            errs.append(f"ingest_backoff_ms={backoff} outside [40, 120]")
        if not (QUERY_CACHE_RANGE_MB[0] <= q_mb <= QUERY_CACHE_RANGE_MB[1]):
            errs.append(f"query_cache_mb={q_mb} outside {list(QUERY_CACHE_RANGE_MB)}")
        if not (INGEST_BUF_RANGE_MB[0] <= i_mb <= INGEST_BUF_RANGE_MB[1]):
            errs.append(f"ingest_buffer_mb={i_mb} outside {list(INGEST_BUF_RANGE_MB)}")
        if not (QUERY_IOPS_RANGE[0] <= q_iops <= QUERY_IOPS_RANGE[1]):
            errs.append(f"query_read_iops={q_iops} outside {list(QUERY_IOPS_RANGE)}")

    if check_sto:
        if not (8 <= retain <= 20):
            errs.append(f"spool_retain_segments={retain} outside [8, 20]")
        if not (COMPACT_BUF_RANGE_MB[0] <= c_mb <= COMPACT_BUF_RANGE_MB[1]):
            errs.append(f"compaction_buffer_mb={c_mb} outside {list(COMPACT_BUF_RANGE_MB)}")
        if not (COMPACT_IOPS_RANGE[0] <= c_iops <= COMPACT_IOPS_RANGE[1]):
            errs.append(f"compaction_write_iops={c_iops} outside {list(COMPACT_IOPS_RANGE)}")

    return summary, errs


def verify_rca_json(pc: Path, check_ing: bool, check_sto: bool) -> list[str]:
    rp = pc / "INCIDENT_RCA.json"
    if not rp.is_file():
        return ["Missing /workspace/prod_cluster/INCIDENT_RCA.json"]
    try:
        rca = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid INCIDENT_RCA.json: {exc}"]

    errs: list[str] = []
    if check_ing:
        iq = rca.get("ingest_query_rca") or {}
        if not iq.get("remediated"):
            errs.append("ingest_query_rca.remediated != true")
        if abs(float(iq.get("t0_retry_amplification", -1)) - T0_INGEST_RETRY_AMP) > 0.2:
            errs.append(f"ingest_query_rca.t0_retry_amplification != {T0_INGEST_RETRY_AMP}")
        if abs(float(iq.get("t0_query_p99_ms", -1)) - T0_QUERY_SCAN_P99_MS) > 2.0:
            errs.append(f"ingest_query_rca.t0_query_p99_ms != {T0_QUERY_SCAN_P99_MS}")
        if str(iq.get("created_index") or "") != T0_MISSING_INDEX_DDL:
            errs.append(f"ingest_query_rca.created_index != '{T0_MISSING_INDEX_DDL}'")

    if check_sto:
        sr = rca.get("storage_sre_rca") or {}
        if not sr.get("remediated"):
            errs.append("storage_sre_rca.remediated != true")
        if abs(float(sr.get("t0_spool_peak_mb", -1)) - T0_SPOOL_PEAK_MB) > 1.0:
            errs.append(f"storage_sre_rca.t0_spool_peak_mb != {T0_SPOOL_PEAK_MB}")
        if int(sr.get("t0_fd_leak_per_min", -1)) != T0_FD_LEAK_PER_MIN:
            errs.append(f"storage_sre_rca.t0_fd_leak_per_min != {T0_FD_LEAK_PER_MIN}")
        if not (8 <= int(sr.get("retained_segments_cap", -1)) <= 20):
            errs.append("storage_sre_rca.retained_segments_cap outside [8, 20]")

    return errs


def probe_live_cluster(pc: Path, duration_s: float, check_ing: bool, check_sto: bool, get_epochs_fn=None) -> tuple[dict, list[str], bool]:
    errs: list[str] = []
    ep_start = get_epochs_fn() if get_epochs_fn else {}

    c_ing, h_ing, _ = _http_json(f"http://127.0.0.1:{INGEST_PORT}/health")
    c_qry, h_qry, _ = _http_json(f"http://127.0.0.1:{QUERY_PORT}/health")
    c_cmp, h_cmp, _ = _http_json(f"http://127.0.0.1:{COMPACT_PORT}/health")
    if c_ing != 200 or c_qry != 200 or c_cmp != 200:
        return {}, [f"Cluster daemon unhealthy: ingest={c_ing}, query={c_qry}, compaction={c_cmp}"], False

    q_lats: list[float] = []
    http_fails = 0
    max_handles = int(h_cmp.get("open_db_handles", 0))
    max_spool = float(h_cmp.get("spool_mb", 999.0))
    contaminated = False

    t_end = time.monotonic() + duration_s
    step = 0
    while time.monotonic() < t_end:
        tid = f"t_{step % 12:02d}"
        c1, r1, dt_q = _http_json(
            f"http://127.0.0.1:{QUERY_PORT}/query",
            method="POST",
            body={"tenant_id": tid, "min_bucket": 5, "max_bucket": 35},
            timeout_s=4.0,
        )
        q_lats.append(dt_q)
        if c1 != 200:
            http_fails += 1
        if step % 3 == 0:
            c2, _, _ = _http_json(f"http://127.0.0.1:{INGEST_PORT}/ingest", method="POST", body={"tenant_id": tid}, timeout_s=4.0)
            if c2 != 200:
                http_fails += 1
        if step % 4 == 0:
            c3, r3, _ = _http_json(f"http://127.0.0.1:{COMPACT_PORT}/compact_now", method="POST", body={}, timeout_s=4.0)
            if c3 != 200:
                http_fails += 1
            else:
                max_handles = max(max_handles, int(r3.get("open_db_handles", 0)))
                max_spool = float(r3.get("spool_mb", max_spool))
        if get_epochs_fn and get_epochs_fn() != ep_start:
            contaminated = True
        step += 1
        time.sleep(0.12)

    if get_epochs_fn and get_epochs_fn() != ep_start:
        contaminated = True

    q_sorted = sorted(q_lats[1:] if len(q_lats) > 4 else q_lats)
    pct_f = 0.85 if len(q_sorted) < 30 else 0.95
    q_p99 = round(q_sorted[min(len(q_sorted) - 1, int(pct_f * len(q_sorted)))], 2) if q_sorted else 999.0

    if contaminated:
        errs.append("Telemetry sampling window invalidated: daemon restart / epoch reset detected mid-window (curves discontinuous); re-run clean window")
    if http_fails > 0:
        errs.append(f"Cluster returned {http_fails} failed HTTP probes during window")

    if check_ing:
        if T0_MISSING_INDEX_DDL not in (h_qry.get("indexes") or []):
            errs.append(f"Missing SQLite composite index {T0_MISSING_INDEX_DDL} on events")
        if q_p99 > MAX_QUERY_P99_MS:
            errs.append(f"query_p99_ms={q_p99} exceeds max {MAX_QUERY_P99_MS} ms")

    if check_sto:
        if max_spool > MAX_SPOOL_USAGE_MB:
            errs.append(f"spool_mb={max_spool} exceeds quota {MAX_SPOOL_USAGE_MB} MB")
        if max_handles > 2:
            errs.append(f"compaction open_db_handles={max_handles} > 2 (SQLite connection leak active)")

    metrics = {
        "query_p99_ms": q_p99,
        "spool_mb": max_spool,
        "open_db_handles": max_handles,
        "failed_probes": http_fails,
        "window_contaminated": contaminated,
    }
    return metrics, errs, contaminated


def render_grafana_plate_png(panel: str, window: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 520), (10, 14, 26))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 510)], outline=(56, 189, 248), width=2)
    dr.text(
        (26, 24),
        f"PROD CLUSTER INCIDENT GRAFANA  |  Panel: {panel}  |  Time Window: {window}",
        fill=(56, 189, 248),
    )
    dr.text(
        (26, 54),
        "Governor Caps: Total RAM (query_cache + ingest_buf + compact_buf) in [336, 354] MB  |  Total NVMe IOPS in [960, 1020]",
        fill=(226, 232, 240),
    )
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)

    y = 108
    if window != "T0_INCIDENT_SNAPSHOT":
        dr.text((28, y), "[LIVE_CLUSTER ROLLING VIEW — Switch to T0_INCIDENT_SNAPSHOT for Incident T0 Forensic Attribution]", fill=(251, 191, 36))
        y += 38
        dr.text((34, y), "Live endpoints: ingest=127.0.0.1:20411 | query=127.0.0.1:20412 | compaction=127.0.0.1:20413", fill=(241, 245, 249))
    elif panel == "INGEST_QUERY_PANEL":
        dr.text((28, y), "T0 FORENSIC TRACE — INGEST GATEWAY & QUERY ENGINE (INC-2026-4419)", fill=(251, 191, 36))
        y += 36
        rows = [
            f"t0_retry_amplification : {T0_INGEST_RETRY_AMP}   (8 retries + 1 initial at 5ms backoff storm)",
            f"t0_query_p99_ms        : {T0_QUERY_SCAN_P99_MS} ms  (4x unindexed full scan over 42,000 events rows)",
            f"required_index_name    : {T0_MISSING_INDEX_DDL}  ON events(tenant_id, ts_bucket)",
            "Target Post-Fix SLO    : query_p99_ms <= 95.0 ms | ingest_max_retries in [1,2] | backoff in [40,120] ms",
            "Governor Slice Ranges  : query_cache_mb in [98, 200] | ingest_buffer_mb in [50, 54] | query_read_iops in [410, 600]",
        ]
        for r in rows:
            dr.text((34, y), r, fill=(241, 245, 249))
            y += 32
    else:
        dr.text((28, y), "T0 FORENSIC TRACE — COMPACTION WORKER & SPOOL STORAGE (INC-2026-4419)", fill=(251, 191, 36))
        y += 36
        rows = [
            f"t0_spool_peak_mb       : {T0_SPOOL_PEAK_MB} MB  (92 unpruned 1MB segments exceeding 28.0 MB spool quota)",
            f"t0_fd_leak_per_min     : {T0_FD_LEAK_PER_MIN} handles/min  (unclosed sqlite3 connections in _leaked_conns)",
            "Target Post-Fix SLO    : spool_mb <= 28.0 MB | open_db_handles <= 2 | spool_retain_segments in [8, 20]",
            "Governor Slice Ranges  : compaction_buffer_mb in [98, 200] | compaction_write_iops in [410, 600]",
        ]
        for r in rows:
            dr.text((34, y), r, fill=(241, 245, 249))
            y += 32

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Prod Cluster Incident Grafana — FC-04</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 7px 12px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #0284c7; }
    #msg { color: #38bdf8; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>PANEL:</strong>
    <button onclick="setG({panel:'INGEST_QUERY_PANEL'})">INGEST_QUERY_PANEL</button>
    <button onclick="setG({panel:'STORAGE_COMPACT_PANEL'})">STORAGE_COMPACT_PANEL</button>
    <strong>WINDOW:</strong>
    <button onclick="setG({window:'T0_INCIDENT_SNAPSHOT'})">T0_INCIDENT_SNAPSHOT</button>
    <button onclick="setG({window:'LIVE_CLUSTER'})">LIVE_CLUSTER</button>
    <button onclick="expG()">Export Panel CSV (/home/gui/Downloads/grafana_panel.csv)</button>
    <span id="msg">Grafana SSO Active</span>
  </div>
  <canvas id="gf-canvas" width="1220" height="520"></canvas>
  <!-- Public protocol tokens:
       /workspace/prod_cluster app/ingest_daemon.py app/query_daemon.py app/compaction_daemon.py
       config/cluster.json INCIDENT_RCA.json bin/clusterctl.sh
       /api/bench/cluster_telemetry /api/sre/submit /api/sre/status 336 354 960 1020 95.0 28.0 full_cluster_slo -->
  <script>
    function drawG() {
      const cv = document.getElementById('gf-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/grafana_plate.png?t=' + Date.now();
    }
    async function setG(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.panel || '') + ' / ' + (d.window || '');
      drawG();
    }
    async function expG() {
      const r = await fetch('/api/ui/export_csv', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Exported ' + (d.path || '') + ' [' + (d.panel || '') + ']';
      drawG();
    }
    drawG();
    setInterval(drawG, 3500);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    pc = workspace / "prod_cluster"
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    state_lock = threading.Lock()
    ctl_lock = threading.Lock()
    sub_locks = {"ingest_query": threading.Lock(), "storage_sre": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    procs: dict[str, subprocess.Popen | None] = {"ingest": None, "query": None, "compaction": None}
    daemon_ports = {"ingest": INGEST_PORT, "query": QUERY_PORT, "compaction": COMPACT_PORT}
    daemon_scripts = {
        "ingest": pc / "app" / "ingest_daemon.py",
        "query": pc / "app" / "query_daemon.py",
        "compaction": pc / "app" / "compaction_daemon.py",
    }

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {
            "panel": "INGEST_QUERY_PANEL",
            "window": "T0_INCIDENT_SNAPSHOT",
        },
        "daemon_epochs": {"ingest": 0, "query": 0, "compaction": 0},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "contaminated_windows": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"ingest_query": {}, "storage_sre": {}},
        "qualified_stages": {"ingest_query": {}, "storage_sre": {}},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    def restart_service(name: str) -> bool:
        with ctl_lock:
            old = procs.get(name)
            if old is not None and old.poll() is None:
                old.terminate()
                try:
                    old.wait(timeout=3)
                except Exception:
                    old.kill()
            log_f = (pc / "var" / f"{name}.log").open("ab")
            cmd = ["python3", str(daemon_scripts[name])]
            if os.geteuid() == 0:
                cmd = ["su", "-s", "/bin/bash", "gui", "-c", f"python3 {daemon_scripts[name]}"]
            procs[name] = subprocess.Popen(cmd, cwd=pc, stdout=log_f, stderr=log_f)
            dport = daemon_ports[name]
            ok = False
            for _ in range(25):
                try:
                    with socket.create_connection(("127.0.0.1", dport), timeout=0.3):
                        ok = True
                        break
                except OSError:
                    time.sleep(0.15)
            with state_lock:
                pstate["daemon_epochs"][name] = int(pstate["daemon_epochs"].get(name, 0)) + 1
                persist()
            return ok

    for svc in ("query", "ingest", "compaction"):
        restart_service(svc)

    def get_epochs_snapshot() -> dict[str, int]:
        with state_lock:
            return dict(pstate["daemon_epochs"])

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args) -> None:
            return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc04_sso")
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
                    self.send_header("Set-Cookie", f"fc04_sso={sso_cookie_val}; Path=/; HttpOnly")
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

            if p == "/ui/grafana_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; use Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_grafana_plate_png(pstate["ui_session"]["panel"], pstate["ui_session"]["window"])
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return

            if p == "/api/sre/status":
                sub_q = (qs.get("subsystem") or [""])[0].strip().lower()
                if sub_q not in ("ingest_query", "storage_sre"):
                    self._json(400, {"error": "Pass ?subsystem=ingest_query or ?subsystem=storage_sre"})
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
                    self._json(401, {"error": "SSO browser session cookie required; click Grafana controls on DISPLAY=:99"})
                    return
                with state_lock:
                    changed = False
                    if body.get("panel") in ("INGEST_QUERY_PANEL", "STORAGE_COMPACT_PANEL"):
                        if pstate["ui_session"]["panel"] != body["panel"]:
                            changed = True
                        pstate["ui_session"]["panel"] = body["panel"]
                    if body.get("window") in ("T0_INCIDENT_SNAPSHOT", "LIVE_CLUSTER"):
                        if pstate["ui_session"]["window"] != body["window"]:
                            changed = True
                        pstate["ui_session"]["window"] = body["window"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/export_csv":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser session cookie required; click Export in Chromium on DISPLAY=:99"})
                    return
                dl_p = Path("/home/gui/Downloads/grafana_panel.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pnl = pstate["ui_session"]["panel"]
                    win = pstate["ui_session"]["window"]
                    lines = ["metric,value"]
                    if win != "T0_INCIDENT_SNAPSHOT":
                        lines.append("rolling_sample_count,120")
                    elif pnl == "INGEST_QUERY_PANEL":
                        lines.append(f"t0_retry_amplification,{T0_INGEST_RETRY_AMP}")
                        lines.append(f"t0_query_p99_ms,{T0_QUERY_SCAN_P99_MS}")
                        lines.append(f"required_index_name,{T0_MISSING_INDEX_DDL}")
                    else:
                        lines.append(f"t0_spool_peak_mb,{T0_SPOOL_PEAK_MB}")
                        lines.append(f"t0_fd_leak_per_min,{T0_FD_LEAK_PER_MIN}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o666)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_p), "panel": pnl, "window": win})
                return

            if p == "/api/cluster/ctl":
                act = str(body.get("action") or "status").strip().lower()
                tgt = str(body.get("target") or "all").strip().lower()
                if act == "status":
                    with state_lock:
                        eps = dict(pstate["daemon_epochs"])
                    self._json(200, {"ok": True, "epochs": eps})
                    return
                if act == "restart":
                    targets = ["query", "ingest", "compaction"] if tgt == "all" else ([tgt] if tgt in ("ingest", "query", "compaction") else [])
                    if not targets:
                        self._json(400, {"error": f"Unknown target {tgt}"})
                        return
                    res_map = {t: restart_service(t) for t in targets}
                    self._json(200, {"ok": all(res_map.values()), "restarted": res_map, "epochs": get_epochs_snapshot()})
                    return
                self._json(400, {"error": f"Unknown action {act}"})
                return

            if p == "/api/bench/cluster_telemetry":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("ingest_query", "storage_sre"):
                    self._json(400, {"error": "subsystem must be 'ingest_query' or 'storage_sre'"})
                    return
                seq_list = INGEST_STAGES if sub == "ingest_query" else STORAGE_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage} for {sub}; expected one of {list(seq_list)}"})
                    return
                st_idx = seq_list.index(stage)
                with state_lock:
                    prev_missing = [seq_list[i] for i in range(st_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_missing:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_missing}"})
                    return

                win_s = 1.0 if fast_selfval else float(os.environ.get("PARAGUI_FC04_WINDOW_S", "325.0"))
                exp_reg = "INGEST_QUERY_PANEL" if sub == "ingest_query" else "STORAGE_COMPACT_PANEL"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["panel"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    cfg_sum, cfg_errs = verify_cluster_config(
                        pc,
                        check_ing=(sub == "ingest_query"),
                        check_sto=(sub == "storage_sre"),
                    )
                    metrics, probe_errs, contam = probe_live_cluster(
                        pc,
                        duration_s=win_s,
                        check_ing=(sub == "ingest_query"),
                        check_sto=(sub == "storage_sre"),
                        get_epochs_fn=get_epochs_snapshot,
                    )
                    errs = list(cfg_errs) + list(probe_errs)
                    if stage == "full_cluster_slo":
                        errs.extend(verify_rca_json(pc, check_ing=(sub == "ingest_query"), check_sto=(sub == "storage_sre")))
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if contam:
                        pstate["contaminated_windows"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({
                        "timestamp": time.time(),
                        "subsystem": sub,
                        "stage": stage,
                        "passed": passed,
                        "contaminated": contam,
                        "elapsed_s": elapsed,
                    })
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "stage": stage,
                    "passed": passed,
                    "discrepancies": errs,
                    "governor_summary": cfg_sum,
                    "telemetry_metrics": metrics,
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/sre/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("ingest_query", "storage_sre"):
                    self._json(400, {"error": "subsystem must be 'ingest_query' or 'storage_sre'"})
                    return

                cfg_sum, cfg_errs = verify_cluster_config(
                    pc,
                    check_ing=(sub == "ingest_query"),
                    check_sto=(sub == "storage_sre"),
                )
                _, probe_errs, _ = probe_live_cluster(
                    pc,
                    duration_s=0.8,
                    check_ing=(sub == "ingest_query"),
                    check_sto=(sub == "storage_sre"),
                    get_epochs_fn=None,
                )
                rca_errs = verify_rca_json(
                    pc,
                    check_ing=(sub == "ingest_query"),
                    check_sto=(sub == "storage_sre"),
                )
                errs = list(cfg_errs) + list(probe_errs) + list(rca_errs) + verify_clean_workspace(workspace)

                seq_list = INGEST_STAGES if sub == "ingest_query" else STORAGE_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified cluster_telemetry stages for {sub}: {unqual}")

                live_rca_sha = sha256_file(pc / "INCIDENT_RCA.json")
                try:
                    if int(body.get("total_ram_mb", -1)) != cfg_sum.get("total_ram_mb", -2):
                        errs.append(f"Submitted total_ram_mb != live {cfg_sum.get('total_ram_mb')}")
                    if int(body.get("total_iops", -1)) != cfg_sum.get("total_iops", -2):
                        errs.append(f"Submitted total_iops != live {cfg_sum.get('total_iops')}")
                    if str(body.get("rca_sha256") or "") != live_rca_sha:
                        errs.append("Submitted rca_sha256 != sha256(/workspace/prod_cluster/INCIDENT_RCA.json)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {
                        "status": "REJECTED_SRE_SIGNOFF",
                        "subsystem": sub,
                        "errors": errs,
                        "governor_summary": cfg_sum,
                    })
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "total_ram_mb": cfg_sum["total_ram_mb"],
                    "total_iops": cfg_sum["total_iops"],
                    "rca_sha256": live_rca_sha,
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
    return audit_protocol_transparency(
        build_tickets_by_role(),
        PORTAL_HTML,
        REQUIRED_PUBLIC_TOKENS,
    )


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    pc = workspace / "prod_cluster"
    subs = portal_state.get("submissions") or {}
    ing_signed = (subs.get("ingest_query") or {}).get("status") == "APPROVED"
    sto_signed = (subs.get("storage_sre") or {}).get("status") == "APPROVED"
    closed_cnt = int(ing_signed) + int(sto_signed)

    cfg_sum, cfg_errs = verify_cluster_config(pc, check_ing=True, check_sto=True)
    rca_ing_errs = verify_rca_json(pc, check_ing=True, check_sto=False)
    rca_sto_errs = verify_rca_json(pc, check_ing=False, check_sto=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "ingest_query", INGEST_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "storage_sre", STORAGE_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs

    # Boot all 3 daemons locally inside isolated grade container to verify live end-to-end SLOs
    procs = []
    ing_probe_errs: list[str] = []
    sto_probe_errs: list[str] = []
    try:
        for script_rel, dport in (("app/query_daemon.py", QUERY_PORT), ("app/ingest_daemon.py", INGEST_PORT), ("app/compaction_daemon.py", COMPACT_PORT)):
            sp = pc / script_rel
            if sp.is_file():
                p = subprocess.Popen(["python3", str(sp)], cwd=pc, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                procs.append(p)
                for _ in range(25):
                    try:
                        with socket.create_connection(("127.0.0.1", dport), timeout=0.25):
                            break
                    except OSError:
                        time.sleep(0.15)
        _, ing_probe_errs, _ = probe_live_cluster(pc, duration_s=1.0, check_ing=True, check_sto=False)
        _, sto_probe_errs, _ = probe_live_cluster(pc, duration_s=1.0, check_ing=False, check_sto=True)
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=2)
            except Exception:
                p.kill()

    trans = audit_case_transparency()
    invariants = {
        "ingest_query_remediated_and_rca_accurate": bool(len(pur_a_errs) == 0 and ing_signed and len(ing_probe_errs) == 0 and len(rca_ing_errs) == 0),
        "storage_sre_remediated_and_rca_accurate": bool(len(pur_b_errs) == 0 and sto_signed and len(sto_probe_errs) == 0 and len(rca_sto_errs) == 0),
        "cluster_ram_and_iops_governor_valid": bool(len(cfg_errs) == 0),
        "workspace_clean_and_artifacts_intact": bool(len(clean_errs) == 0),
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
        "contaminated_windows": int(portal_state.get("contaminated_windows", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "governor_summary": cfg_sum,
        "diagnostics": {
            "governor_errors": cfg_errs,
            "ingest_query_errors": ing_probe_errs + rca_ing_errs,
            "storage_sre_errors": sto_probe_errs + rca_sto_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


FIXED_QUERY_PY = """#!/usr/bin/env python3
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_P = ROOT / "var" / "events.db"
BOOT_TS = time.time()


import threading
_tls = threading.local()
def get_conn():
    c = getattr(_tls, "conn", None)
    if c is None:
        c = sqlite3.connect(str(DB_P), timeout=15.0, check_same_thread=False)
        _tls.conn = c
    return c


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_a): return
    def _json(self, c, b):
        raw = json.dumps(b).encode("utf-8")
        self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            with get_conn() as conn:
                idxs = [r[1] for r in conn.execute("PRAGMA index_list('events')").fetchall()]
            self._json(200, {"ok": True, "service": "query", "pid": os.getpid(), "boot_ts": BOOT_TS, "indexes": idxs})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/query":
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8") if n > 0 else "{}")
            tid = str(body.get("tenant_id", "t_03"))
            b_min = int(body.get("min_bucket", 10))
            b_max = int(body.get("max_bucket", 25))
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(metric_val), 0) FROM events WHERE tenant_id = ? AND ts_bucket BETWEEN ? AND ?",
                    (tid, b_min, b_max),
                ).fetchone()
            self._json(200, {"ok": True, "sum_val": int(row[0])})
            return
        self._json(404, {"error": "not found"})


if __name__ == "__main__":
    with get_conn() as c:
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_bucket ON events(tenant_id, ts_bucket);")
        c.commit()
    ThreadingHTTPServer(("127.0.0.1", 20412), Handler).serve_forever()
"""

FIXED_COMPACT_PY = """#!/usr/bin/env python3
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_P = ROOT / "var" / "events.db"
SPOOL_DIR = ROOT / "var" / "spool"
CFG_P = ROOT / "config" / "cluster.json"
BOOT_TS = time.time()


def compaction_tick() -> dict:
    cfg = json.loads(CFG_P.read_text(encoding="utf-8"))
    retain = int(cfg.get("spool_retain_segments", 12))
    with sqlite3.connect(str(DB_P), timeout=10.0) as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    segs = sorted(SPOOL_DIR.glob("seg_*.bin"))
    while len(segs) > retain:
        old = segs.pop(0)
        try:
            old.unlink()
        except OSError:
            pass
    spool_bytes = sum(p.stat().st_size for p in SPOOL_DIR.glob("seg_*.bin") if p.is_file())
    return {
        "spool_mb": round(spool_bytes / (1024.0 * 1024.0), 2),
        "segment_count": len(list(SPOOL_DIR.glob("seg_*.bin"))),
        "open_db_handles": 1,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_a): return
    def _json(self, c, b):
        raw = json.dumps(b).encode("utf-8")
        self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            st = compaction_tick()
            self._json(200, {"ok": True, "service": "compaction", "pid": os.getpid(), "boot_ts": BOOT_TS, **st})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/compact_now":
            st = compaction_tick()
            self._json(200, {"ok": True, **st})
            return
        self._json(404, {"error": "not found"})


if __name__ == "__main__":
    compaction_tick()
    ThreadingHTTPServer(("127.0.0.1", 20413), Handler).serve_forever()
"""


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("ingest_query_lead", "storage_sre_lead")
    pc = workspace / "prod_cluster"
    base = f"http://127.0.0.1:{portal_port}"
    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}

    is_ing = (role == "ingest_query_lead")
    pnl = "INGEST_QUERY_PANEL" if is_ing else "STORAGE_COMPACT_PANEL"
    sub = "ingest_query" if is_ing else "storage_sre"

    req_v = urllib.request.Request(
        f"{base}/api/ui/view",
        data=json.dumps({"panel": pnl, "window": "T0_INCIDENT_SNAPSHOT"}).encode("utf-8"),
        headers={"Content-Type": "application/json", **adm_hdr},
        method="POST",
    )
    urllib.request.urlopen(req_v, timeout=10).read()
    req_e = urllib.request.Request(f"{base}/api/ui/export_csv", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(req_e, timeout=10).read()

    cfg_p = pc / "config" / "cluster.json"
    rca_p = pc / "INCIDENT_RCA.json"
    cur_cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    cur_rca = json.loads(rca_p.read_text(encoding="utf-8"))

    if is_ing:
        (pc / "app" / "query_daemon.py").write_text(FIXED_QUERY_PY, encoding="utf-8")
        os.chmod(pc / "app" / "query_daemon.py", 0o755)
        with sqlite3.connect(str(pc / "var" / "events.db")) as conn:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_bucket ON events(tenant_id, ts_bucket);")
            conn.commit()
        peer_c_mb = int(cur_cfg.get("compaction_buffer_mb", 64))
        peer_c_iops = int(cur_cfg.get("compaction_write_iops", 350))
        cur_cfg["ingest_max_retries"] = 2
        cur_cfg["ingest_backoff_ms"] = 60
        cur_cfg["ingest_buffer_mb"] = 52
        cur_cfg["query_cache_mb"] = max(98, min(200, 345 - 52 - peer_c_mb))
        cur_cfg["query_read_iops"] = max(410, min(600, 990 - peer_c_iops))
        write_json(cfg_p, cur_cfg)
        cur_rca["ingest_query_rca"] = {
            "t0_retry_amplification": T0_INGEST_RETRY_AMP,
            "t0_query_p99_ms": T0_QUERY_SCAN_P99_MS,
            "created_index": T0_MISSING_INDEX_DDL,
            "remediated": True,
        }
        write_json(rca_p, cur_rca)
        post_json(f"{base}/api/cluster/ctl", {"action": "restart", "target": "query"})
        post_json(f"{base}/api/cluster/ctl", {"action": "restart", "target": "ingest"})
    else:
        (pc / "app" / "compaction_daemon.py").write_text(FIXED_COMPACT_PY, encoding="utf-8")
        os.chmod(pc / "app" / "compaction_daemon.py", 0o755)
        peer_q_mb = int(cur_cfg.get("query_cache_mb", 64))
        peer_i_mb = int(cur_cfg.get("ingest_buffer_mb", 52))
        peer_q_iops = int(cur_cfg.get("query_read_iops", 400))
        cur_cfg["spool_retain_segments"] = 14
        cur_cfg["compaction_buffer_mb"] = max(98, min(200, 345 - peer_q_mb - peer_i_mb))
        cur_cfg["compaction_write_iops"] = max(410, min(600, 990 - peer_q_iops))
        write_json(cfg_p, cur_cfg)
        cur_rca["storage_sre_rca"] = {
            "t0_spool_peak_mb": T0_SPOOL_PEAK_MB,
            "t0_fd_leak_per_min": T0_FD_LEAK_PER_MIN,
            "retained_segments_cap": 14,
            "remediated": True,
        }
        write_json(rca_p, cur_rca)
        post_json(f"{base}/api/cluster/ctl", {"action": "restart", "target": "compaction"})
        _http_json(f"http://127.0.0.1:{COMPACT_PORT}/compact_now", method="POST", body={})

    subprocess.run(["chown", "-R", "1000:0", str(pc)], capture_output=True)
    stages = INGEST_STAGES if is_ing else STORAGE_STAGES
    for st in stages:
        code, resp = post_json(f"{base}/api/bench/cluster_telemetry", {"subsystem": sub, "stage": st}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {st} failed: {resp}"

    cfg_sum, _ = verify_cluster_config(pc, check_ing=False, check_sto=False)
    code, sresp = post_json(f"{base}/api/sre/submit", {
        "subsystem": sub,
        "total_ram_mb": cfg_sum["total_ram_mb"],
        "total_iops": cfg_sum["total_iops"],
        "rca_sha256": sha256_file(rca_p),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    pc = workspace / "prod_cluster"
    cfg_p = pc / "config" / "cluster.json"
    rca_p = pc / "INCIDENT_RCA.json"
    with tempfile.TemporaryDirectory() as tmp:
        snap_cfg = Path(tmp) / "cluster_v0.json"
        snap_rca = Path(tmp) / "rca_v0.json"
        shutil.copy2(cfg_p, snap_cfg)
        shutil.copy2(rca_p, snap_rca)

        solve_role("ingest_query_lead", workspace, portal_port, strict=False)

        # Second engineer writes from cached v0 cluster.json & INCIDENT_RCA.json snapshot
        shutil.copy2(snap_cfg, cfg_p)
        shutil.copy2(snap_rca, rca_p)
        solve_role("storage_sre_lead", workspace, portal_port, strict=False)

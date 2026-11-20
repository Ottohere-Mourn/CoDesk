"""FC-13: Zero-Trust Envoy mTLS Ingress & Upstream RPC Mesh Co-Tuning (OpenSSL X.509 RSA-2048 Certs + envoy_bootstrap.yaml + mesh_policy.json + TLS CPU vs RPC Queue Cross-Saturation + 6.5s FIPS-140-3 Sweep Canaries)."""
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

TASK_ID = "FC-13"
PORTAL_PORT = 19530

META = {
    "id": TASK_ID,
    "title": "Zero-Trust Envoy mTLS X.509 Certs, YAML Bootstrap & RPC Queue Cross-Saturation",
    "domain": "Cloud-Native Security & Service-Mesh Engineering (OpenSSL X.509 RSA-2048 + Envoy YAML + TLS/RPC Queue Simulator + SSO FIPS Console)",
    "arena": "Shared Envoy Bootstrap YAML, TLS Handshake CPU vs RPC Pipeline Saturation & 6.5s FIPS Sweeps",
    "conflict_archetype": "tls_cpu_vs_rpc_queue_asymmetric_saturation + async_6_5s_fips_audit_canary + openssl_x509_and_envoy_yaml_sync",
    "roles": ("mesh_mtls_sec_lead", "upstream_rpc_perf_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "service_mesh/envoy_bootstrap.yaml",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

CONTROLS = ("CTL_01", "CTL_02", "CTL_03", "CTL_04")

TRUE_FIPS_MTLS: dict[str, tuple[float, float]] = {
    "CTL_01": (14.2, 884.0),
    "CTL_02": (15.8, 942.0),
    "CTL_03": (13.5, 865.0),
    "CTL_04": (16.4, 976.0),
}
TRUE_FIPS_RPC: dict[str, tuple[float, float]] = {
    "CTL_01": (14.6, 920.0),
    "CTL_02": (16.2, 985.0),
    "CTL_03": (13.8, 890.0),
    "CTL_04": (15.4, 950.0),
}

TUNING_INDEX_RANGE = (58.0, 64.0)
CROSS_LOAD_BETA = 0.60
MAX_CORE_SATURATION_PCT = 98.9

MTLS_STAGES = ("x509_san_cert_gate", "envoy_sds_yaml_gate", "fips_control_matrix", "ingress_cpu_soak", "full_mesh_release")
RPC_STAGES = ("envoy_breaker_yaml_gate", "pipeline_window_gate", "fips_rpc_matrix", "upstream_queue_soak", "full_mesh_release")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/service_mesh/envoy_bootstrap.yaml",
    "/workspace/service_mesh/mesh_policy.json",
    "/workspace/service_mesh/certs/mesh_server.crt",
    "/workspace/service_mesh/certs/mesh_server.key",
    "DNS:mesh.internal",
    "tls_certificate_sds_config",
    "circuit_breakers_thresholds",
    "FIPS_140_3_STRICT",
    "/api/bench/mesh_tls_rpc_soak",
    "/api/mesh/submit",
    "/api/mesh/status",
    "58.0",
    "64.0",
    "0.60",
    "98.9",
    "full_mesh_release",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "service_mesh")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside service_mesh: {extra_top}")
    sm = workspace / "service_mesh"
    allowed_sm = {"envoy_bootstrap.yaml", "mesh_policy.json", "certs"}
    if sm.is_dir():
        extra_sm = sorted(x.name for x in sm.iterdir() if x.name not in allowed_sm)
        if extra_sm:
            errs.append(f"Unexpected non-release files in /workspace/service_mesh: {extra_sm}")
    cd = sm / "certs"
    if cd.is_dir():
        extra_c = sorted(x.name for x in cd.iterdir() if x.name not in {"mesh_server.crt", "mesh_server.key"})
        if extra_c:
            errs.append(f"Unexpected files in /workspace/service_mesh/certs: {extra_c}")
    return errs


def inspect_mesh_workspace(workspace: Path) -> dict:
    sm = workspace / "service_mesh"
    yp = sm / "envoy_bootstrap.yaml"
    pp = sm / "mesh_policy.json"
    crt_p = sm / "certs" / "mesh_server.crt"
    key_p = sm / "certs" / "mesh_server.key"
    if not yp.is_file() or not pp.is_file():
        return {"ok": False, "error": "Missing envoy_bootstrap.yaml or mesh_policy.json"}

    yaml_src = yp.read_text(encoding="utf-8", errors="replace")
    has_sds = ("tls_certificate_sds_config:" in yaml_src and "mesh_server.crt" in yaml_src)
    has_breaker = ("circuit_breakers_thresholds:" in yaml_src and "max_pending_requests:" in yaml_src)

    cert_ok = False
    if crt_p.is_file() and key_p.is_file():
        cp = subprocess.run(["openssl", "x509", "-in", str(crt_p), "-noout", "-text"], capture_output=True, text=True, timeout=10)
        if cp.returncode == 0 and "DNS:mesh.internal" in cp.stdout and ("2048 bit" in cp.stdout or "4096 bit" in cp.stdout):
            m1 = subprocess.run(["openssl", "x509", "-noout", "-modulus", "-in", str(crt_p)], capture_output=True, text=True, timeout=10)
            m2 = subprocess.run(["openssl", "rsa", "-noout", "-modulus", "-in", str(key_p)], capture_output=True, text=True, timeout=10)
            cert_ok = (m1.returncode == 0 and m2.returncode == 0 and m1.stdout.strip() == m2.stdout.strip())

    try:
        pol = json.loads(pp.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"Invalid mesh_policy.json: {exc}"}

    w_mtls = float((pol.get("mtls_security") or {}).get("cipher_work_index", 20.0))
    w_rpc = float((pol.get("rpc_upstream") or {}).get("pipeline_concurrency_index", 20.0))
    sat_mtls = round(w_mtls + CROSS_LOAD_BETA * w_rpc, 3)
    sat_rpc = round(w_rpc + CROSS_LOAD_BETA * w_mtls, 3)

    return {
        "ok": True,
        "pol": pol,
        "summary": {
            "cert_rsa_san_ok": cert_ok,
            "yaml_has_sds": has_sds,
            "yaml_has_breaker": has_breaker,
            "cipher_work_index": round(w_mtls, 3),
            "pipeline_concurrency_index": round(w_rpc, 3),
            "ingress_cpu_saturation_pct": sat_mtls,
            "upstream_queue_saturation_pct": sat_rpc,
        },
    }


def check_mesh_constraints(
    info: dict,
    check_mtls: bool,
    check_rpc: bool,
    stage: str = "full_mesh_release",
    check_oracle_canaries: bool = False,
) -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid mesh workspace")]
    errs: list[str] = []
    s = info["summary"]
    pol = info["pol"]

    if check_mtls:
        if not s["cert_rsa_san_ok"]:
            errs.append("certs/mesh_server.crt & .key missing valid matching >=2048-bit RSA cert with SAN DNS:mesh.internal")
        if stage in ("envoy_sds_yaml_gate", "fips_control_matrix", "ingress_cpu_soak", "full_mesh_release"):
            if not s["yaml_has_sds"]:
                errs.append("envoy_bootstrap.yaml missing tls_certificate_sds_config referencing mesh_server.crt")
        if stage in ("fips_control_matrix", "ingress_cpu_soak", "full_mesh_release"):
            cm = (pol.get("mtls_security") or {}).get("fips_controls") or {}
            for cid in CONTROLS:
                rec = cm.get(cid) or {}
                if float(rec.get("handshake_ms", -1)) <= 0 or float(rec.get("ecdh_ops", -1)) <= 0:
                    errs.append(f"mtls_security.fips_controls.{cid} missing positive swept metrics")
        if stage in ("ingress_cpu_soak", "full_mesh_release"):
            if not (TUNING_INDEX_RANGE[0] <= s["cipher_work_index"] <= TUNING_INDEX_RANGE[1]):
                errs.append(f"cipher_work_index={s['cipher_work_index']} outside {list(TUNING_INDEX_RANGE)}")
            if s["ingress_cpu_saturation_pct"] > MAX_CORE_SATURATION_PCT:
                errs.append(f"ingress_cpu_saturation_pct={s['ingress_cpu_saturation_pct']}% > {MAX_CORE_SATURATION_PCT}%")

    if check_rpc:
        if not s["yaml_has_breaker"]:
            errs.append("envoy_bootstrap.yaml missing circuit_breakers_thresholds with max_pending_requests")
        if stage in ("pipeline_window_gate", "fips_rpc_matrix", "upstream_queue_soak", "full_mesh_release"):
            if not (TUNING_INDEX_RANGE[0] <= s["pipeline_concurrency_index"] <= TUNING_INDEX_RANGE[1]):
                errs.append(f"pipeline_concurrency_index={s['pipeline_concurrency_index']} outside {list(TUNING_INDEX_RANGE)}")
        if stage in ("fips_rpc_matrix", "upstream_queue_soak", "full_mesh_release"):
            rm = (pol.get("rpc_upstream") or {}).get("fips_controls") or {}
            for cid in CONTROLS:
                rec = rm.get(cid) or {}
                if float(rec.get("frame_us", -1)) <= 0 or float(rec.get("qps_cap", -1)) <= 0:
                    errs.append(f"rpc_upstream.fips_controls.{cid} missing positive swept metrics")
        if stage in ("upstream_queue_soak", "full_mesh_release"):
            if s["upstream_queue_saturation_pct"] > MAX_CORE_SATURATION_PCT:
                errs.append(f"upstream_queue_saturation_pct={s['upstream_queue_saturation_pct']}% > {MAX_CORE_SATURATION_PCT}%")

    if check_oracle_canaries:
        cm = (pol.get("mtls_security") or {}).get("fips_controls") or {}
        for cid, (e1, e2) in TRUE_FIPS_MTLS.items():
            rec = cm.get(cid) or {}
            if abs(float(rec.get("handshake_ms", -999)) - e1) > 0.06 or abs(float(rec.get("ecdh_ops", -999)) - e2) > 4.0:
                errs.append(f"Canary mismatch mtls_security.fips_controls.{cid} != FIPS_140_3_STRICT {(e1, e2)}")
        rm = (pol.get("rpc_upstream") or {}).get("fips_controls") or {}
        for cid, (e1, e2) in TRUE_FIPS_RPC.items():
            rec = rm.get(cid) or {}
            if abs(float(rec.get("frame_us", -999)) - e1) > 0.3 or abs(float(rec.get("qps_cap", -999)) - e2) > 8.0:
                errs.append(f"Canary mismatch rpc_upstream.fips_controls.{cid} != FIPS_140_3_STRICT {(e1, e2)}")
    return errs


def run_mesh_queue_des_sim(summary: dict, fast_selfval: bool = False) -> dict:
    import numpy as np

    rng = np.random.default_rng(202613)
    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC13_SIM_S", "290.0"))
    t0 = time.monotonic()
    ticks = 0
    q_p99 = 0.0
    while True:
        arr = rng.exponential(scale=1.0, size=65536)
        srv = rng.gamma(shape=2.0, scale=0.35, size=65536)
        q_p99 = float(np.quantile(arr + srv, 0.99))
        ticks += 1
        if time.monotonic() - t0 >= target_s:
            break
    return {"des_batches": ticks, "sim_tail_ms": round(q_p99, 3), "elapsed_s": round(time.monotonic() - t0, 2)}


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Service-Mesh Artifacts, Worker Saturation Law & Hygiene",
        f"- **Mesh Root**: {b}/workspace/service_mesh{b}",
        f"  - Envoy Bootstrap: {b}envoy_bootstrap.yaml{b} (contains {b}tls_certificate_sds_config:{b} and {b}circuit_breakers_thresholds:{b} sections).",
        f"  - Policy JSON: {b}mesh_policy.json{b} ({b}mtls_security{b} and {b}rpc_upstream{b}).",
        f"  - X.509 Certs: {b}certs/mesh_server.crt{b} and {b}certs/mesh_server.key{b}.",
        f"- **Shared Worker-Core Saturation Law**:",
        f"  - Both {b}mtls_security.cipher_work_index{b} and {b}rpc_upstream.pipeline_concurrency_index{b} must lie in **{b}[58.0, 64.0]{b}**.",
        f"  - Ingress TLS Core Saturation: {b}ingress_cpu_saturation_pct = cipher_work_index + 0.60 * pipeline_concurrency_index <= 98.9%{b}.",
        f"  - Upstream RPC Queue Saturation: {b}upstream_queue_saturation_pct = pipeline_concurrency_index + 0.60 * cipher_work_index <= 98.9%{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/service_mesh{b} may contain ONLY {b}envoy_bootstrap.yaml{b}, {b}mesh_policy.json{b}, and {b}certs/{{mesh_server.crt,mesh_server.key}}{b}.",
        f"- **SSO FIPS Compliance Profiler ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & Mesh API**:",
        f"  - Select your assigned profile ({b}FIPS_140_3_STRICT{b} or {b}CHA20_POLY1305_MESH{b}), plane ({b}MTLS_INGRESS{b} or {b}RPC_UPSTREAM{b}), and control ({b}CTL_01..CTL_04{b}), then click {b}Run 6.5s FIPS Profiler{b} to export {b}/home/gui/Downloads/fips_profile.csv{b}.",
        f"  - Each {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/mesh_tls_rpc_soak{b} run takes ~110s (use {b}curl --max-time 300{b}); pass {b}X-Role-Token{b} from {b}/session/ticket/role_token.txt{b} on {b}GET /api/mesh/status{b}.",
    ]
    common_txt = "\n".join(common_lines)

    mtls_txt = "\n".join([
        f"# Security Mesh Work Order — FC-13 ({b}mesh_mtls_sec_lead{b})",
        "",
        f"Provision X.509 SAN certificates, configure {b}tls_certificate_sds_config{b} in {b}envoy_bootstrap.yaml{b}, sweep {b}CTL_01..CTL_04{b} under {b}FIPS_140_3_STRICT{b} + {b}MTLS_INGRESS{b}, and tune {b}cipher_work_index{b}.",
        "",
        "### mTLS Security Steps",
        f"1. Generate matching >=2048-bit RSA {b}certs/mesh_server.key{b} and {b}certs/mesh_server.crt{b} with SubjectAltName {b}DNS:mesh.internal{b}, and add {b}tls_certificate_sds_config:{b} referencing {b}mesh_server.crt{b} to {b}envoy_bootstrap.yaml{b}.",
        f"2. Sweep {b}CTL_01..CTL_04{b} under **{b}FIPS_140_3_STRICT{b}** + **{b}MTLS_INGRESS{b}** on {b}DISPLAY=:99{b} into {b}mtls_security.fips_controls.<CTL_ID> = {{\"handshake_ms\": <float>, \"ecdh_ops\": <float>}}{b} in {b}mesh_policy.json{b}.",
        f"3. Set {b}mtls_security.cipher_work_index{b} in **{b}[58.0, 64.0]{b}** respecting both saturation caps ({b}<= 98.9%{b}), certify ordered stages ({b}x509_san_cert_gate -> envoy_sds_yaml_gate -> fips_control_matrix -> ingress_cpu_soak -> full_mesh_release{b}) on {b}POST /api/bench/mesh_tls_rpc_soak{b} ({b}subsystem='mesh_mtls_sec'{b}), and submit to {b}POST /api/mesh/submit{b}:",
        f"   {b}{{\"subsystem\": \"mesh_mtls_sec\", \"tuning_index\": <float>, \"saturation_pct\": <float>, \"yaml_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}FIPS_140_3_STRICT{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    rpc_txt = "\n".join([
        f"# Upstream RPC Performance Work Order — FC-13 ({b}upstream_rpc_perf_lead{b})",
        "",
        f"Configure {b}circuit_breakers_thresholds{b} in {b}envoy_bootstrap.yaml{b}, sweep {b}CTL_01..CTL_04{b} under {b}CHA20_POLY1305_MESH{b} + {b}RPC_UPSTREAM{b}, and tune {b}pipeline_concurrency_index{b}.",
        "",
        "### Upstream RPC Steps",
        f"1. Add {b}circuit_breakers_thresholds:{b} with {b}max_pending_requests: 2048{b} to {b}envoy_bootstrap.yaml{b}.",
        f"2. Sweep {b}CTL_01..CTL_04{b} under **{b}CHA20_POLY1305_MESH{b}** + **{b}RPC_UPSTREAM{b}** on {b}DISPLAY=:99{b} into {b}rpc_upstream.fips_controls.<CTL_ID> = {{\"frame_us\": <float>, \"qps_cap\": <float>}}{b} in {b}mesh_policy.json{b}.",
        f"3. Set {b}rpc_upstream.pipeline_concurrency_index{b} in **{b}[58.0, 64.0]{b}** respecting both saturation caps ({b}<= 98.9%{b}), certify ordered stages ({b}envoy_breaker_yaml_gate -> pipeline_window_gate -> fips_rpc_matrix -> upstream_queue_soak -> full_mesh_release{b}) on {b}POST /api/bench/mesh_tls_rpc_soak{b} ({b}subsystem='upstream_rpc_perf'{b}), and submit to {b}POST /api/mesh/submit{b}:",
        f"   {b}{{\"subsystem\": \"upstream_rpc_perf\", \"tuning_index\": <float>, \"saturation_pct\": <float>, \"yaml_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}CHA20_POLY1305_MESH{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"mesh_mtls_sec_lead": mtls_txt, "upstream_rpc_perf_lead": rpc_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    sm = workspace / "service_mesh"
    (sm / "certs").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    (sm / "envoy_bootstrap.yaml").write_text(
        "node:\n  id: mesh-edge-01\n  cluster: prod-mesh\nstatic_resources:\n  listeners: []\n",
        encoding="utf-8",
    )
    write_json(sm / "mesh_policy.json", {
        "mesh_version": "v1.28",
        "mtls_security": {
            "cipher_work_index": 20.0,
            "fips_controls": {c: {"handshake_ms": 0.0, "ecdh_ops": 0.0} for c in CONTROLS},
        },
        "rpc_upstream": {
            "pipeline_concurrency_index": 20.0,
            "fips_controls": {c: {"frame_us": 0.0, "qps_cap": 0.0} for c in CONTROLS},
        },
    })

    role_tokens = {}
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")
        tok = "rtok_" + secrets.token_hex(12)
        (rdir / "role_token.txt").write_text(tok + "\n", encoding="utf-8")
        role_tokens[role] = tok
    write_json(tickets_root / "role_tokens.json", role_tokens)


def render_mesh_plate_png(prof: str, plane: str, ctl: str, busy: bool) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 480), (10, 14, 28))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 470)], outline=(56, 189, 248), width=2)
    dr.text((24, 24), f"ZERO-TRUST MESH FIPS PROFILER  |  Profile: {prof}  |  Plane: {plane}  |  Control: {ctl}", fill=(56, 189, 248))
    dr.text((24, 54), "Core Saturation Law: W_i + 0.60 * W_j <= 98.9%  |  W_mtls, W_rpc in [58.0, 64.0]", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)
    st = "FIPS CRYPTO/RPC BENCHMARK RUNNING (6.5s)..." if busy else "IDLE — Click [Run 6.5s FIPS Profiler]"
    dr.text((28, 118), f"Profiler State : {st}", fill=(251, 191, 36))
    dr.text((28, 156), f"Export Target  : {prof} / {plane} / {ctl} -> /home/gui/Downloads/fips_profile.csv", fill=(241, 245, 249))
    pts = [(60 + k * 14, int(390 - 160 * (1.0 - math.exp(-k / 20.0)))) for k in range(75)]
    dr.line(pts, fill=(167, 139, 250), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Zero-Trust Mesh FIPS Profiler — FC-13</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 6px 10px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #0284c7; }
    #msg { color: #38bdf8; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>PROFILE:</strong>
    <button onclick="setM({prof:'FIPS_140_3_STRICT'})">FIPS_140_3_STRICT</button>
    <button onclick="setM({prof:'CHA20_POLY1305_MESH'})">CHA20_POLY1305_MESH</button>
    <strong>PLANE:</strong>
    <button onclick="setM({plane:'MTLS_INGRESS'})">MTLS_INGRESS</button>
    <button onclick="setM({plane:'RPC_UPSTREAM'})">RPC_UPSTREAM</button>
    <strong>CONTROL:</strong>
    <button onclick="setM({ctl:'CTL_01'})">CTL_01</button>
    <button onclick="setM({ctl:'CTL_02'})">CTL_02</button>
    <button onclick="setM({ctl:'CTL_03'})">CTL_03</button>
    <button onclick="setM({ctl:'CTL_04'})">CTL_04</button>
  </div>
  <div class="bar">
    <button onclick="runFips()">Run 6.5s FIPS Profiler (/home/gui/Downloads/fips_profile.csv)</button>
    <span id="msg">Mesh FIPS SSO Active</span>
  </div>
  <canvas id="m-canvas" width="1220" height="480"></canvas>
  <!-- Public protocol tokens:
       /workspace/service_mesh/envoy_bootstrap.yaml /workspace/service_mesh/mesh_policy.json
       /workspace/service_mesh/certs/mesh_server.crt /workspace/service_mesh/certs/mesh_server.key
       DNS:mesh.internal tls_certificate_sds_config circuit_breakers_thresholds FIPS_140_3_STRICT
       /api/bench/mesh_tls_rpc_soak /api/mesh/submit /api/mesh/status 58.0 64.0 0.60 98.9 full_mesh_release -->
  <script>
    function drawM() {
      const cv = document.getElementById('m-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/mesh_plate.png?t=' + Date.now();
    }
    async function setM(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.prof || '') + ' | ' + (d.plane || '') + ' | ' + (d.ctl || '');
      drawM();
    }
    async function runFips() {
      document.getElementById('msg').textContent = 'Running 6.5s FIPS profiler...';
      drawM();
      const r = await fetch('/api/ui/run_fips', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Saved ' + (d.path || '');
      drawM();
    }
    drawM();
    setInterval(drawM, 3000);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    rtok_p = state_dir / "role_tokens.json"
    role_tokens = json.loads(rtok_p.read_text(encoding="utf-8")) if rtok_p.is_file() else {}
    tok_to_sub = {
        role_tokens.get("mesh_mtls_sec_lead", ""): "mesh_mtls_sec",
        role_tokens.get("upstream_rpc_perf_lead", ""): "upstream_rpc_perf",
    }

    state_lock = threading.Lock()
    sub_locks = {"mesh_mtls_sec": threading.Lock(), "upstream_rpc_perf": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"prof": "CHA20_POLY1305_MESH", "plane": "MTLS_INGRESS", "ctl": "CTL_01", "busy": False},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"mesh_mtls_sec": {}, "upstream_rpc_perf": {}},
        "qualified_stages": {"mesh_mtls_sec": {}, "upstream_rpc_perf": {}},
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
                m = c.get("fc13_sso")
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
                    self.send_header("Set-Cookie", f"fc13_sso={sso_cookie_val}; Path=/; HttpOnly")
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
            if p == "/ui/mesh_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    u = pstate["ui_session"]
                    png = render_mesh_plate_png(u["prof"], u["plane"], u["ctl"], bool(u["busy"]))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/mesh/status":
                rtok = (self.headers.get("X-Role-Token") or "").strip()
                sub_q = tok_to_sub.get(rtok, "") if rtok else ""
                if not sub_q:
                    self._json(403, {"error": "Valid X-Role-Token header required"})
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
                    if body.get("prof") in ("FIPS_140_3_STRICT", "CHA20_POLY1305_MESH"):
                        if pstate["ui_session"]["prof"] != body["prof"]:
                            changed = True
                        pstate["ui_session"]["prof"] = body["prof"]
                    if body.get("plane") in ("MTLS_INGRESS", "RPC_UPSTREAM"):
                        if pstate["ui_session"]["plane"] != body["plane"]:
                            changed = True
                        pstate["ui_session"]["plane"] = body["plane"]
                    if body.get("ctl") in CONTROLS:
                        pstate["ui_session"]["ctl"] = body["ctl"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/run_fips":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    pstate["ui_session"]["busy"] = True
                time.sleep(0.05 if fast_selfval else 6.5)
                dl_p = Path("/home/gui/Downloads/fips_profile.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pstate["ui_session"]["busy"] = False
                    pr = pstate["ui_session"]["prof"]
                    pl = pstate["ui_session"]["plane"]
                    ct = pstate["ui_session"]["ctl"]
                    src_tbl = TRUE_FIPS_MTLS if pl == "MTLS_INGRESS" else TRUE_FIPS_RPC
                    expected_pr = "FIPS_140_3_STRICT" if pl == "MTLS_INGRESS" else "CHA20_POLY1305_MESH"
                    mult = 1.0 if pr == expected_pr else 0.855
                    v1, v2 = src_tbl[ct]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(f"control_id,metric_primary,metric_secondary\n{ct},{round(v1*mult, 3)},{round(v2*mult, 2)}\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                self._json(200, {"ok": True, "path": str(dl_p)})
                return

            if p == "/api/bench/mesh_tls_rpc_soak":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("mesh_mtls_sec", "upstream_rpc_perf"):
                    self._json(400, {"error": "subsystem must be 'mesh_mtls_sec' or 'upstream_rpc_perf'"})
                    return
                seq_list = MTLS_STAGES if sub == "mesh_mtls_sec" else RPC_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                exp_reg = "FIPS_140_3_STRICT" if sub == "mesh_mtls_sec" else "CHA20_POLY1305_MESH"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["prof"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_mesh_workspace(workspace)
                    errs = check_mesh_constraints(
                        info,
                        check_mtls=(sub == "mesh_mtls_sec"),
                        check_rpc=(sub == "upstream_rpc_perf"),
                        stage=stage,
                        check_oracle_canaries=False,
                    )
                    des = run_mesh_queue_des_sim(info.get("summary") or {}, fast_selfval=fast_selfval) if info.get("ok") else {}
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({"timestamp": time.time(), "subsystem": sub, "stage": stage, "passed": passed, "elapsed_s": elapsed})
                    persist()

                s = info.get("summary") or {}
                own_m = {
                    "own_tuning_index": s.get("cipher_work_index") if sub == "mesh_mtls_sec" else s.get("pipeline_concurrency_index"),
                    "own_saturation_pct": s.get("ingress_cpu_saturation_pct") if sub == "mesh_mtls_sec" else s.get("upstream_queue_saturation_pct"),
                }
                self._json(200, {"ok": True, "subsystem": sub, "stage": stage, "passed": passed, "discrepancies": errs, "mesh_telemetry": own_m, "des": des, "elapsed_s": elapsed})
                return

            if p == "/api/mesh/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("mesh_mtls_sec", "upstream_rpc_perf"):
                    self._json(400, {"error": "subsystem must be 'mesh_mtls_sec' or 'upstream_rpc_perf'"})
                    return
                info = inspect_mesh_workspace(workspace)
                errs = check_mesh_constraints(
                    info,
                    check_mtls=(sub == "mesh_mtls_sec"),
                    check_rpc=(sub == "upstream_rpc_perf"),
                    stage="full_mesh_release",
                    check_oracle_canaries=False,
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = MTLS_STAGES if sub == "mesh_mtls_sec" else RPC_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified mesh_tls_rpc_soak stages for {sub}: {unqual}")

                s = info.get("summary") or {}
                yaml_sha = sha256_file(workspace / "service_mesh" / "envoy_bootstrap.yaml")
                exp_t = s.get("cipher_work_index", -1.0) if sub == "mesh_mtls_sec" else s.get("pipeline_concurrency_index", -1.0)
                exp_s = s.get("ingress_cpu_saturation_pct", -1.0) if sub == "mesh_mtls_sec" else s.get("upstream_queue_saturation_pct", -1.0)
                try:
                    if abs(float(body.get("tuning_index", -999)) - exp_t) > 0.25:
                        errs.append(f"Submitted tuning_index != live {exp_t}")
                    if abs(float(body.get("saturation_pct", -999)) - exp_s) > 0.35:
                        errs.append(f"Submitted saturation_pct != live {exp_s}")
                    if str(body.get("yaml_sha256") or "") != yaml_sha:
                        errs.append("Submitted yaml_sha256 != sha256(envoy_bootstrap.yaml)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_MESH_SIGNOFF", "subsystem": sub, "errors": errs})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "tuning_index": exp_t,
                    "saturation_pct": exp_s,
                    "yaml_sha256": yaml_sha,
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
    subs = portal_state.get("submissions") or {}
    m_signed = (subs.get("mesh_mtls_sec") or {}).get("status") == "APPROVED"
    r_signed = (subs.get("upstream_rpc_perf") or {}).get("status") == "APPROVED"
    closed_cnt = int(m_signed) + int(r_signed)

    info = inspect_mesh_workspace(workspace)
    all_errs = check_mesh_constraints(info, check_mtls=True, check_rpc=True, stage="full_mesh_release", check_oracle_canaries=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "mesh_mtls_sec", MTLS_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "upstream_rpc_perf", RPC_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()
    s = info.get("summary") or {}

    invariants = {
        "mtls_x509_yaml_and_fips_canaries_valid": bool(len(pur_a_errs) == 0 and m_signed and info.get("ok") and s.get("cert_rsa_san_ok") and s.get("yaml_has_sds") and not any("mtls_security" in e for e in all_errs)),
        "rpc_breaker_yaml_and_fips_canaries_valid": bool(len(pur_b_errs) == 0 and r_signed and info.get("ok") and s.get("yaml_has_breaker") and not any("rpc_upstream" in e for e in all_errs)),
        "both_core_saturation_caps_valid": bool(info.get("ok") and s.get("ingress_cpu_saturation_pct", 999) <= MAX_CORE_SATURATION_PCT and s.get("upstream_queue_saturation_pct", 999) <= MAX_CORE_SATURATION_PCT),
        "workspace_clean_and_valid": bool(len(all_errs) == 0 and len(clean_errs) == 0),
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
        "mesh_summary": s,
        "diagnostics": {
            "mesh_and_canary_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("mesh_mtls_sec_lead", "upstream_rpc_perf_lead")
    sm = workspace / "service_mesh"
    yp = sm / "envoy_bootstrap.yaml"
    pp = sm / "mesh_policy.json"
    crt_p = sm / "certs" / "mesh_server.crt"
    key_p = sm / "certs" / "mesh_server.key"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_m = (role == "mesh_mtls_sec_lead")
    pl = "MTLS_INGRESS" if is_m else "RPC_UPSTREAM"
    sub = "mesh_mtls_sec" if is_m else "upstream_rpc_perf"

    swept = {}
    for cid in CONTROLS:
        r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"prof": ("FIPS_140_3_STRICT" if is_m else "CHA20_POLY1305_MESH"), "plane": pl, "ctl": cid}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
        urllib.request.urlopen(r1, timeout=10).read()
        r2 = urllib.request.Request(f"{base}/api/ui/run_fips", data=b"{}", headers=adm_hdr, method="POST")
        urllib.request.urlopen(r2, timeout=20).read()
        row = Path("/home/gui/Downloads/fips_profile.csv").read_text(encoding="utf-8").strip().splitlines()[-1].split(",")
        swept[cid] = (float(row[1]), float(row[2]))

    ysrc = yp.read_text(encoding="utf-8")
    pol = json.loads(pp.read_text(encoding="utf-8"))
    if is_m:
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", str(key_p), "-out", str(crt_p), "-days", "365",
                "-subj", "/CN=mesh.internal", "-addext", "subjectAltName=DNS:mesh.internal",
            ],
            check=True,
            capture_output=True,
            timeout=20,
        )
        if "tls_certificate_sds_config:" not in ysrc:
            ysrc += "\ntls_certificate_sds_config:\n  certificate_chain: /workspace/service_mesh/certs/mesh_server.crt\n  private_key: /workspace/service_mesh/certs/mesh_server.key\n"
            yp.write_text(ysrc, encoding="utf-8")
        peer_w = float(pol["rpc_upstream"]["pipeline_concurrency_index"])
        my_w = round(max(58.2, min(63.5, (98.6 - peer_w) / CROSS_LOAD_BETA, 98.6 - CROSS_LOAD_BETA * peer_w)), 2) if peer_w >= 58.0 else 61.2
        pol["mtls_security"]["cipher_work_index"] = my_w
        pol["mtls_security"]["fips_controls"] = {c: {"handshake_ms": swept[c][0], "ecdh_ops": swept[c][1]} for c in CONTROLS}
    else:
        if "circuit_breakers_thresholds:" not in ysrc:
            ysrc += "\ncircuit_breakers_thresholds:\n  max_pending_requests: 2048\n  max_connections: 4096\n"
            yp.write_text(ysrc, encoding="utf-8")
        peer_w = float(pol["mtls_security"]["cipher_work_index"])
        my_w = round(max(58.2, min(63.5, (98.6 - peer_w) / CROSS_LOAD_BETA, 98.6 - CROSS_LOAD_BETA * peer_w)), 2) if peer_w >= 58.0 else 61.2
        pol["rpc_upstream"]["pipeline_concurrency_index"] = my_w
        pol["rpc_upstream"]["fips_controls"] = {c: {"frame_us": swept[c][0], "qps_cap": swept[c][1]} for c in CONTROLS}
    write_json(pp, pol)

    stages = MTLS_STAGES if is_m else RPC_STAGES
    for stg in stages:
        code, resp = post_json(f"{base}/api/bench/mesh_tls_rpc_soak", {"subsystem": sub, "stage": stg}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {stg} failed: {resp}"

    s1 = inspect_mesh_workspace(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/mesh/submit", {
        "subsystem": sub,
        "tuning_index": s1["cipher_work_index"] if is_m else s1["pipeline_concurrency_index"],
        "saturation_pct": s1["ingress_cpu_saturation_pct"] if is_m else s1["upstream_queue_saturation_pct"],
        "yaml_sha256": sha256_file(yp),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    sm = workspace / "service_mesh"
    yp = sm / "envoy_bootstrap.yaml"
    pp = sm / "mesh_policy.json"
    base = f"http://127.0.0.1:{portal_port}"
    solve_role("mesh_mtls_sec_lead", workspace, portal_port, strict=True)
    pol = json.loads(pp.read_text(encoding="utf-8"))
    pol["mtls_security"]["cipher_work_index"] = 63.0
    pol["rpc_upstream"]["pipeline_concurrency_index"] = 60.5
    pol["rpc_upstream"]["fips_controls"] = {c: {"frame_us": TRUE_FIPS_RPC[c][0]*0.845, "qps_cap": TRUE_FIPS_RPC[c][1]*0.845} for c in CONTROLS}
    write_json(pp, pol)
    ysrc = yp.read_text(encoding="utf-8") + "\ncircuit_breakers_thresholds:\n  max_pending_requests: 2048\n"
    yp.write_text(ysrc, encoding="utf-8")
    for stg in RPC_STAGES:
        post_json(f"{base}/api/bench/mesh_tls_rpc_soak", {"subsystem": "upstream_rpc_perf", "stage": stg}, timeout_s=240)
    s1 = inspect_mesh_workspace(workspace)["summary"]
    post_json(f"{base}/api/mesh/submit", {"subsystem": "upstream_rpc_perf", "tuning_index": s1["pipeline_concurrency_index"], "saturation_pct": s1["upstream_queue_saturation_pct"], "yaml_sha256": sha256_file(yp)}, timeout_s=60)

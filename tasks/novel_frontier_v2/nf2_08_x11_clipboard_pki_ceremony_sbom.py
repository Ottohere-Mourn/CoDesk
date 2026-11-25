"""NF2-08: X11 Asymmetric Selection Contention (`XA_PRIMARY` vs `CLIPBOARD`) — HSM X.509 CRL Audit vs. Firmware SBOM Signing."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import secrets
import shlex
import sqlite3
import subprocess
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

TASK_ID = "NF2-08"
PORTAL_PORT = 19608

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "X11 Asymmetric `XA_PRIMARY` vs `CLIPBOARD` Selection Contention: X.509 OCSP/CRL Ceremony vs. SPDX Firmware SBOM Release",
    "domain": "Enterprise PKI X.509 Revocation (`openssl` + `SQLite`) & Firmware Supply-Chain SBOM Security (`Chromium` HSM Vault)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("x509_crl_auditor", "firmware_sbom_signer"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

# Long 44-char masked HSM tokens (masked in DOM as `HSM-PKI-****` so agents copy/paste via X11 CLIPBOARD into the verification box!)
PKI_CEREMONY_SEAL = "HSM-X509-" + hashlib.sha256(b"nf208-pki-root-ceremony").hexdigest()[:28].upper()
SBOM_CEREMONY_SEAL = "HSM-SBOM-" + hashlib.sha256(b"nf208-sbom-cosign-digest").hexdigest()[:28].upper()


def _generate_ocsp_rows() -> list[dict[str, Any]]:
    reasons = ["KEY_COMPROMISE", "CA_COMPROMISE", "AFFILIATION_CHANGED", "SUPERSEDED", "CERTIFICATE_HOLD", "REMOVE_FROM_CRL"]
    rows = []
    for i in range(1, 381):
        serial = f"SN-{1000 + (i % 190):04d}"
        seq = 2 if i > 190 else 1
        rc = reasons[(i * 5) % 6] if (i % 4 == 0) else "GOOD"
        # RFC 5280 rule: REMOVE_FROM_CRL on seq=2 reinstates a prior CERTIFICATE_HOLD, and CERTIFICATE_HOLD is temporary suspension (not permanent revocation)!
        rows.append({
            "log_id": i, "cert_serial": serial, "update_seq": seq, "revocation_status": rc,
            "key_bits": 2048 if (i % 17 == 0) else 4096,
        })
    return rows


def _generate_sbom_rows() -> list[dict[str, Any]]:
    lics = ["Apache-2.0", "MIT", "BSD-3-Clause", "GPL-3.0-only", "LGPL-2.1-or-later"]
    rows = []
    for i in range(1, 351):
        lic = lics[(i * 3) % 5]
        scope = "DEV_TEST_ONLY" if (i % 13 == 0) else "RUNTIME_STATIC_LINK"
        cvss = round(3.5 + (i % 12) * 0.55, 1)
        rows.append({
            "pkg_idx": i, "pkg_purl": f"pkg:cargo/crate_{i:03d}@1.{i % 9}.0",
            "spdx_license": lic, "link_scope": scope, "max_cvss_v3": cvss,
        })
    return rows


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    # Role A: Latest update_seq per cert_serial; permanent revocations = KEY_COMPROMISE, CA_COMPROMISE, AFFILIATION_CHANGED, SUPERSEDED (exclude GOOD, REMOVE_FROM_CRL, and temporary CERTIFICATE_HOLD); plus count weak <3072-bit active (GOOD or REMOVE_FROM_CRL) certs per nist_sp800_57_policy in SQLite!
    latest: dict[str, dict[str, Any]] = {}
    for r in _generate_ocsp_rows():
        latest[r["cert_serial"]] = r
    perm_set = {"KEY_COMPROMISE", "CA_COMPROMISE", "AFFILIATION_CHANGED", "SUPERSEDED"}
    perm_rev = sum(1 for r in latest.values() if r["revocation_status"] in perm_set)
    hold_cnt = sum(1 for r in latest.values() if r["revocation_status"] == "CERTIFICATE_HOLD")
    weak_active = sum(1 for r in latest.values() if r["revocation_status"] in ("GOOD", "REMOVE_FROM_CRL") and int(r["key_bits"]) < 3072)
    or_a = {
        "unique_cert_count": len(latest),
        "permanently_revoked_count": perm_rev,
        "active_certificate_hold_count": hold_cnt,
        "weak_key_active_cert_count": weak_active,
        "pki_ceremony_seal": PKI_CEREMONY_SEAL,
    }

    # Role B: Runtime linked packages; exclude vex_not_affected_cves in SQLite when counting exploitable CVSS >= 7.0 runtime packages; copyleft conflict = GPL-3.0-only or LGPL-2.1-or-later under RUNTIME_STATIC_LINK!
    srows = _generate_sbom_rows()
    vex_exempt = {f"pkg:cargo/crate_{k:03d}@1.{k % 9}.0" for k in range(12, 351, 24)}
    rt = [r for r in srows if r["link_scope"] == "RUNTIME_STATIC_LINK"]
    copyleft = sum(1 for r in rt if r["spdx_license"] in ("GPL-3.0-only", "LGPL-2.1-or-later"))
    high_vuln = sum(1 for r in rt if r["max_cvss_v3"] >= 7.0 and r["pkg_purl"] not in vex_exempt)
    or_b = {
        "runtime_component_count": len(rt),
        "static_copyleft_violation_count": copyleft,
        "exploitable_high_cvss_count": high_vuln,
        "sbom_ceremony_seal": SBOM_CEREMONY_SEAL,
    }
    return or_a, or_b


PKI_ORACLE, SBOM_ORACLE = _compute_oracles()

VAULT_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>HSM Hardware Ceremony Clipboard Vault</title>
<style>body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace} button{padding:8px 14px;background:#2563eb;color:#fff;border:none;cursor:pointer;margin-right:8px} input{width:460px;padding:7px;background:#090d16;color:#f8fafc;border:1px solid #475569} pre{background:#1e293b;padding:14px;border:1px solid #334155}</style></head><body>
<h2>HSM Ceremony Vault — Hardware Clipboard Bridge</h2>
<p>Masked Hardware Token Slot: <code id="msk">HSM-****-MASKED</code> (tokens are copied directly into the X11 desktop clipboard by the HSM daemon)</p>
<button onclick="copySeal('pki')">Copy X.509 CRL Ceremony Seal -> X11 CLIPBOARD</button>
<button style="background:#7c3aed" onclick="copySeal('sbom')">Copy SPDX SBOM Signing Seal -> X11 CLIPBOARD</button><br><br>
<input id="paste-box" placeholder="Focus here & press Ctrl+V to verify/unmask your ceremony seal..."/>
<button style="background:#059669" onclick="verifyPaste()">Verify Unmasked Seal</button>
<pre id="out">Ready.</pre>
<script>
async function copySeal(domain) {
  const r = await fetch('/api/hsm/copy_x11?domain=' + domain, {method:'POST', credentials:'include'});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
async function verifyPaste() {
  const v = document.getElementById('paste-box').value.trim();
  const r = await fetch('/api/hsm/verify?seal=' + encodeURIComponent(v), {method:'POST', credentials:'include'});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — RFC 5280 X.509 CRL/OCSP Audit & Root Ceremony Seal (`x509_crl_auditor`)",
        "",
        "## Objective",
        f"Retrieve and verify your X.509 ceremony seal via the HSM Clipboard Vault (`http://127.0.0.1:{PORTAL_PORT}/vault` in Chromium), audit `{b}/workspace/pki/ocsp_staple_log.sqlite{b}` and `{b}/workspace/pki/ca_root.pem{b}` per `{b}/workspace/docs/SOP_PKI_5280.pdf{b}`, and write `{b}/workspace/x509_crl_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — SPDX Firmware SBOM Static-Link & VEX Vulnerability Triage (`firmware_sbom_signer`)",
        "",
        "## Objective",
        f"Retrieve and verify your SPDX SBOM ceremony seal via the HSM Clipboard Vault (`http://127.0.0.1:{PORTAL_PORT}/vault` in Chromium), audit `{b}/workspace/sbom/spdx_sbom.sqlite{b}` per `{b}/workspace/docs/SOP_SBOM_VEX.pdf{b}`, and write `{b}/workspace/sbom_release_audit.json{b}`.",
    ])
    return {"x509_crl_auditor": ta, "firmware_sbom_signer": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["x509_crl_auditor"]
    ws_b = workspace_map["firmware_sbom_signer"]
    for d in (ws_a / "pki", ws_a / "docs", ws_b / "sbom", ws_b / "docs"):
        d.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "/tmp/nf208_ca.key", "-out", str(ws_a / "pki/ca_root.pem"), "-days", "365", "-subj", "/CN=GenevaRootCA-2026"],
        check=True, capture_output=True, timeout=20,
    )
    Path("/tmp/nf208_ca.key").unlink(missing_ok=True)

    with sqlite3.connect(str(ws_a / "pki/ocsp_staple_log.sqlite")) as conn:
        conn.execute("CREATE TABLE ocsp_updates (log_id INTEGER PRIMARY KEY, cert_serial TEXT, update_seq INTEGER, revocation_status TEXT, key_bits INTEGER)")
        for r in _generate_ocsp_rows():
            conn.execute("INSERT INTO ocsp_updates VALUES (?,?,?,?,?)", (r["log_id"], r["cert_serial"], r["update_seq"], r["revocation_status"], r["key_bits"]))
        conn.execute("CREATE TABLE nist_sp800_57_policy (min_rsa_modulus_bits INTEGER, treat_certificate_hold_as_permanent INTEGER)")
        conn.execute("INSERT INTO nist_sp800_57_policy VALUES (3072, 0)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_PKI_5280.pdf", "SOP-PKI-808A: RFC 5280 CRL/OCSP State Machine & Key Policy", [
        ("1. Revocation State Resolution", [
            "1.1 Resolve the latest update_seq per cert_serial in /workspace/pki/ocsp_staple_log.sqlite following RFC 5280 REMOVE_FROM_CRL reinstatement and NIST SP 800-57 policy in SQLite.",
            "1.2 Obtain and verify pki_ceremony_seal via the HSM Vault on /vault.",
        ]),
        ("2. JSON Schema (/workspace/x509_crl_audit.json)", [
            "Keys: unique_cert_count (int), permanently_revoked_count (int), active_certificate_hold_count (int), weak_key_active_cert_count (int), pki_ceremony_seal (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "sbom/spdx_sbom.sqlite")) as conn:
        conn.execute("CREATE TABLE sbom_packages (pkg_idx INTEGER PRIMARY KEY, pkg_purl TEXT, spdx_license TEXT, link_scope TEXT, max_cvss_v3 REAL)")
        for r in _generate_sbom_rows():
            conn.execute("INSERT INTO sbom_packages VALUES (?,?,?,?,?)", (r["pkg_idx"], r["pkg_purl"], r["spdx_license"], r["link_scope"], r["max_cvss_v3"]))
        conn.execute("CREATE TABLE csaf_vex_not_affected (pkg_purl TEXT PRIMARY KEY, justification TEXT)")
        for k in range(12, 351, 24):
            conn.execute("INSERT INTO csaf_vex_not_affected VALUES (?, 'VULNERABLE_CODE_NOT_IN_EXECUTE_PATH')", (f"pkg:cargo/crate_{k:03d}@1.{k % 9}.0",))
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_SBOM_VEX.pdf", "SOP-SEC-808B: SPDX Static-Link Copyleft & CSAF VEX Triage", [
        ("1. Static-Link License & Exploitable CVSS >= 7.0 Audit", [
            "1.1 Filter /workspace/sbom/spdx_sbom.sqlite to RUNTIME_STATIC_LINK components, count GPL/LGPL static-linking copyleft violations, and count exploitable CVSS >= 7.0 components after applying CSAF VEX exemptions in SQLite.",
            "1.2 Obtain and verify sbom_ceremony_seal via the HSM Vault on /vault.",
        ]),
        ("2. JSON Schema (/workspace/sbom_release_audit.json)", [
            "Keys: runtime_component_count (int), static_copyleft_violation_count (int), exploitable_high_cvss_count (int), sbom_ceremony_seal (str).",
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
    mem = {"clip_writes": 0, "pki_verified": False, "sbom_verified": False}
    write_json(st_p, {"task_id": TASK_ID, **mem})

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("hsm_sso" in c) and (c["hsm_sso"].value == tok)
        def _json(self, code: int, obj: dict[str, Any]) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                self._json(200, {"ok": True}); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self._json(403, {"error": "SSO sealed"}); return
                raw = b"<html><body><script>location.href='/vault';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"hsm_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            raw = VAULT_HTML.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(raw)
        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly SSO required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/hsm/copy_x11":
                dom = (qs.get("domain") or ["pki"])[0]
                seal = PKI_CEREMONY_SEAL if dom == "pki" else SBOM_CEREMONY_SEAL
                subprocess.Popen(
                    ["su", "-s", "/bin/bash", "user", "-c", f"printf '%s' {shlex.quote(seal)} | DISPLAY=:99 XAUTHORITY=/run/user/1000/x99.auth xclip -selection clipboard >/dev/null 2>&1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                mem["clip_writes"] += 1
                write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"copied_to_x11_clipboard": True, "domain": dom, "hint": "Paste (Ctrl+V) into #paste-box to unmask & verify"}); return
            if u.path == "/api/hsm/verify":
                s = (qs.get("seal") or [""])[0].strip()
                if s == PKI_CEREMONY_SEAL:
                    mem["pki_verified"] = True; write_json(st_p, {"task_id": TASK_ID, **mem})
                    self._json(200, {"valid": True, "role_domain": "pki", "unmasked_seal": s}); return
                if s == SBOM_CEREMONY_SEAL:
                    mem["sbom_verified"] = True; write_json(st_p, {"task_id": TASK_ID, **mem})
                    self._json(200, {"valid": True, "role_domain": "sbom", "unmasked_seal": s}); return
                self._json(200, {"valid": False, "error": "Invalid or overwritten clipboard token"}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del workspace_map, active_roles
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ja = read_json_safe(workspace_map["x509_crl_auditor"] / "x509_crl_audit.json")
    jb = read_json_safe(workspace_map["firmware_sbom_signer"] / "sbom_release_audit.json")

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.10, "Missing x509_crl_audit.json"),
        ("a_uniq", ja.get("unique_cert_count") == PKI_ORACLE["unique_cert_count"], 0.14, "unique_cert_count != 190"),
        ("a_hold", ja.get("active_certificate_hold_count") == PKI_ORACLE["active_certificate_hold_count"], 0.16, "active_certificate_hold_count mismatch"),
        ("a_seal", ja.get("pki_ceremony_seal") == PKI_CEREMONY_SEAL and ja.get("pki_ceremony_seal") != SBOM_CEREMONY_SEAL and bool(service_state.get("pki_verified")), 0.22, "Wrong or unverified pki_ceremony_seal (overwritten X11 CLIPBOARD?)"),
        ("a_fine_perm_rev", ja.get("permanently_revoked_count") == PKI_ORACLE["permanently_revoked_count"], 0.19, "permanently_revoked_count included CERTIFICATE_HOLD or missed REMOVE_FROM_CRL"),
        ("a_fine_weak_key", ja.get("weak_key_active_cert_count") == PKI_ORACLE["weak_key_active_cert_count"], 0.19, "Missed nist_sp800_57_policy <3072-bit active cert check"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.10, "Missing sbom_release_audit.json"),
        ("b_rt_cnt", jb.get("runtime_component_count") == SBOM_ORACLE["runtime_component_count"], 0.16, "runtime_component_count mismatch"),
        ("b_copyleft", jb.get("static_copyleft_violation_count") == SBOM_ORACLE["static_copyleft_violation_count"], 0.18, "static_copyleft_violation_count mismatch (include LGPL-2.1 on static link!)"),
        ("b_seal", jb.get("sbom_ceremony_seal") == SBOM_CEREMONY_SEAL and jb.get("sbom_ceremony_seal") != PKI_CEREMONY_SEAL and bool(service_state.get("sbom_verified")), 0.24, "Wrong or unverified sbom_ceremony_seal (overwritten X11 CLIPBOARD?)"),
        ("b_fine_vex_vuln", jb.get("exploitable_high_cvss_count") == SBOM_ORACLE["exploitable_high_cvss_count"], 0.32, "Missed csaf_vex_not_affected exemptions in spdx_sbom.sqlite"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    st_f = Path("/opt/nf_state/service_state.json")
    if role == "x509_crl_auditor":
        write_json(ws / "x509_crl_audit.json", PKI_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf208_st"):
                st = read_json_safe(st_f); st["pki_verified"] = True; write_json(st_f, st)
    else:
        write_json(ws / "sbom_release_audit.json", SBOM_ORACLE)
        if st_f.is_file():
            with file_atomic_lock("nf208_st"):
                st = read_json_safe(st_f); st["sbom_verified"] = True; write_json(st_f, st)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    solve_role("x509_crl_auditor", workspace_map, port)
    solve_role("firmware_sbom_signer", workspace_map, port)
    # X11 CLIPBOARD clobber: Role A pastes Role B's SBOM seal
    ja = read_json_safe(workspace_map["x509_crl_auditor"] / "x509_crl_audit.json")
    ja["pki_ceremony_seal"] = SBOM_CEREMONY_SEAL
    ja["unique_cert_count"] = 0
    write_json(workspace_map["x509_crl_auditor"] / "x509_crl_audit.json", ja)
    st = read_json_safe(state_dir / "service_state.json")
    st["clip_writes"] = 6
    write_json(state_dir / "service_state.json", st)

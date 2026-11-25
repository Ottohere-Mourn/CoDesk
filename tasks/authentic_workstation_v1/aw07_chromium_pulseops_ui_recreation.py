"""AW-07: Multi-State Enterprise Incident & FinOps Console Recreation from Live Chromium."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    read_json_safe,
    resource_lock,
    write_json,
)

TASK_META: dict[str, Any] = {
    "id": "AW-07",
    "slug": "chromium_pulseops_ui_recreation",
    "title": "PulseOps Enterprise Console Recreation: Incident Triage Shell vs. FinOps Burn & Postmortem Drawer",
    "domain": "Multi-State Web UI Reverse-Engineering & Frontend Integration (Chromium + HTML5/CSS3/JS)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19607,
    "roles": ("incident_shell_frontend_eng", "finops_drawer_frontend_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

TICKET_A = (
    "# Work Order — Incident Triage Shell & KPI Frontend Engineer (`incident_shell_frontend_eng`)\n\n"
    "Recreate the **Incident Triage** workspace of the live **PulseOps Console** open in Chromium (`http://127.0.0.1:19607`) inside `/workspace/pulse_app` (`/workspace/pulse_app/index.html`, `styles.css`, `app.js`):\n\n"
    "1. Visually inspect the live reference app in Chromium across its top navigation bar, dark/slate sidebar, 4-card KPI strip, severity filter pills (`ALL`, `SEV-1`, `SEV-2`), and incident table rows (clicking each filter pill and inspecting colors, typography, badge colors, and exact incident IDs/MTTR/owner values).\n"
    "2. Implement the complete responsive layout and URL query-parameter routing (`?tab=incidents` default and `?tab=incidents&sev=SEV1` filtered state) in `/workspace/pulse_app/index.html`, `styles.css`, and `app.js` so opening `index.html` in Chromium matches the reference layout, colors, and interactive filter behavior.\n"
    "3. Also write `/workspace/pulse_app/incident_spec_audit.json` summarizing the exact values observed in the live app:\n"
    "   - `brand_header_hex`, `sidebar_bg_hex`, `sev1_badge_hex`\n"
    "   - `kpi_mttr_minutes` (float), `kpi_active_sev1_count` (int), `sev1_incident_ids` (sorted list of strings)\n"
)

TICKET_B = (
    "# Work Order — FinOps Burn View & Postmortem Drawer Frontend Engineer (`finops_drawer_frontend_eng`)\n\n"
    "Recreate the **FinOps Cloud Burn** view, **Postmortem Slide-Over Drawer**, and **Threshold Alert Modal** of the live **PulseOps Console** open in Chromium (`http://127.0.0.1:19607`) inside `/workspace/pulse_app` (`/workspace/pulse_app/index.html`, `styles.css`, `app.js`):\n\n"
    "1. Visually inspect the live reference app in Chromium by navigating to the `FinOps Burn` view, opening the `INC-402` postmortem right-hand drawer, and opening the `Configure Burn Alert` modal dialog (checking exact colors, regional spend bars, anomaly banner, root-cause timeline entries, and modal fields).\n"
    "2. Implement URL query-state routing and interactive toggles in `/workspace/pulse_app/index.html`, `styles.css`, and `app.js` supporting `?tab=finops`, `?drawer=INC-402` (right-aligned slide-over drawer), and `?modal=alert` (centered alert configuration modal).\n"
    "3. Also write `/workspace/pulse_app/finops_spec_audit.json` summarizing the exact values observed in the live app:\n"
    "   - `finops_accent_hex`, `drawer_header_hex`, `monthly_burn_musd` (float), `overrun_region` (string)\n"
    "   - `inc402_root_cause_code` (string), `default_alert_threshold_pct` (int)\n"
)


def render_reference_pulseops_html(tab: str = "incidents", sev: str = "ALL", drawer: str = "", modal: str = "") -> str:
    """Canonical multi-state PulseOps Enterprise Console HTML/CSS/JS."""
    inc_rows = [
        ("INC-402", "SEV-1", "#dc2626", "eu-central-1 Kafka Broker ISR Collapse", "18.4 min", "sre-frankfurt"),
        ("INC-405", "SEV-2", "#d97706", "us-east-1 Checkout Redis Latency Spike", "31.0 min", "payments-oncall"),
        ("INC-409", "SEV-1", "#dc2626", "ap-northeast-1 Cold-Chain MQTT TLS Expiry", "14.6 min", "iot-tokyo"),
        ("INC-412", "SEV-2", "#d97706", "eu-west-1 Invoice PDF Worker Queue Backlog", "42.5 min", "billing-dublin"),
    ]
    vis_rows = [r for r in inc_rows if (sev != "SEV1" or r[1] == "SEV-1")]
    rows_html = "".join(
        f"<tr style='border-bottom:1px solid #e2e8f0;'><td style='padding:14px;font-weight:700;'>"
        f"<a href='?tab=incidents&drawer={r[0]}' style='color:#1d4ed8;text-decoration:none;'>{r[0]}</a></td>"
        f"<td><span style='background:{r[2]};color:#ffffff;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;'>{r[1]}</span></td>"
        f"<td style='padding:14px;'>{r[3]}</td><td>{r[4]}</td><td><code>{r[5]}</code></td></tr>"
        for r in vis_rows
    )

    finops_html = """
    <div id="finops-panel" style="background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;padding:24px;">
      <div style="background:#7c3aed;color:#ffffff;padding:14px 20px;border-radius:8px;font-weight:700;margin-bottom:20px;">
        FINOPS ANOMALY BANNER | Monthly Cloud Burn: $2.84M (+19.4% Overrun in eu-central-1)
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-bottom:24px;">
        <div style="padding:18px;background:#f5f3ff;border-left:6px solid #7c3aed;border-radius:8px;"><div>Monthly Run-Rate</div><div style="font-size:30px;font-weight:800;">$2.84M</div></div>
        <div style="padding:18px;background:#fef2f2;border-left:6px solid #dc2626;border-radius:8px;"><div>Top Overrun Region</div><div style="font-size:30px;font-weight:800;">eu-central-1</div></div>
        <div style="padding:18px;background:#ecfdf5;border-left:6px solid #10b981;border-radius:8px;"><div>Reserved Coverage</div><div style="font-size:30px;font-weight:800;">76.5%</div></div>
      </div>
      <div style="height:180px;background:#0f172a;border-radius:10px;padding:20px;display:flex;align-items:flex-end;gap:28px;">
        <div style="width:90px;height:85px;background:#38bdf8;border-radius:6px 6px 0 0;"></div>
        <div style="width:90px;height:145px;background:#7c3aed;border-radius:6px 6px 0 0;"></div>
        <div style="width:90px;height:110px;background:#10b981;border-radius:6px 6px 0 0;"></div>
        <div style="width:90px;height:68px;background:#f59e0b;border-radius:6px 6px 0 0;"></div>
      </div>
    </div>"""

    inc_html = f"""
    <div id="incidents-panel">
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px;">
        <div style="background:#ffffff;padding:18px;border-radius:10px;border-top:5px solid #dc2626;"><div>Active SEV-1</div><div style="font-size:32px;font-weight:800;">2</div></div>
        <div style="background:#ffffff;padding:18px;border-radius:10px;border-top:5px solid #2563eb;"><div>Rolling MTTR</div><div style="font-size:32px;font-weight:800;">16.5 min</div></div>
        <div style="background:#ffffff;padding:18px;border-radius:10px;border-top:5px solid #10b981;"><div>Global SLO</div><div style="font-size:32px;font-weight:800;">99.94%</div></div>
        <div style="background:#ffffff;padding:18px;border-radius:10px;border-top:5px solid #d97706;"><div>Open Postmortems</div><div style="font-size:32px;font-weight:800;">4</div></div>
      </div>
      <div style="margin-bottom:14px;display:flex;gap:10px;">
        <a href="?tab=incidents&sev=ALL" style="padding:8px 16px;border-radius:999px;background:{'#1e293b' if sev!='SEV1' else '#cbd5e1'};color:{'#fff' if sev!='SEV1' else '#0f172a'};text-decoration:none;font-weight:700;">ALL (4)</a>
        <a href="?tab=incidents&sev=SEV1" style="padding:8px 16px;border-radius:999px;background:{'#dc2626' if sev=='SEV1' else '#fee2e2'};color:{'#fff' if sev=='SEV1' else '#991b1b'};text-decoration:none;font-weight:700;">SEV-1 ONLY (2)</a>
      </div>
      <div style="background:#ffffff;border-radius:10px;border:1px solid #cbd5e1;overflow:hidden;">
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead style="background:#f1f5f9;"><tr><th style="padding:14px;">Incident</th><th>Severity</th><th style="padding:14px;">Summary</th><th>MTTR</th><th>Owner</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </div>"""

    drawer_html = ""
    if drawer == "INC-402":
        drawer_html = """
        <div id="postmortem-drawer" style="position:fixed;top:0;right:0;width:440px;height:100vh;background:#ffffff;box-shadow:-8px 0 24px rgba(0,0,0,0.28);z-index:40;display:flex;flex-direction:column;">
          <div style="background:#0f766e;color:#ffffff;padding:20px;font-weight:800;font-size:18px;display:flex;justify-content:space-between;">
            <span>POSTMORTEM | INC-402</span><a href="?tab=incidents" style="color:#fff;">Close</a>
          </div>
          <div style="padding:22px;line-height:1.7;color:#0f172a;">
            <p><b>Root Cause Code:</b> <code>RC-KAFKA-ISR-QUORUM-77</code></p>
            <p><b>Blast Radius:</b> 14.2% EU order stream lag for 18.4 minutes.</p>
            <p><b>Corrective Action:</b> Enforced <code>min.insync.replicas=2</code> and rack-aware partition rebalance.</p>
          </div>
        </div>"""

    modal_html = ""
    if modal == "alert":
        modal_html = """
        <div id="alert-modal-backdrop" style="position:fixed;inset:0;background:rgba(15,23,42,0.65);z-index:50;display:flex;align-items:center;justify-content:center;">
          <div id="alert-modal" style="width:480px;background:#ffffff;border-radius:12px;overflow:hidden;">
            <div style="background:#7c3aed;color:#ffffff;padding:16px 22px;font-weight:800;">Configure Cloud Burn Alert</div>
            <div style="padding:22px;color:#0f172a;">
              <p style="margin-bottom:12px;">Default Overrun Alert Threshold (%): <b>115%</b></p>
              <input value="115" style="padding:8px;width:120px;border:1px solid #94a3b8;border-radius:6px;"/>
              <a href="?tab=finops" style="margin-left:14px;padding:9px 16px;background:#7c3aed;color:#fff;border-radius:6px;text-decoration:none;font-weight:700;">Save Rule</a>
            </div>
          </div>
        </div>"""

    main_content = finops_html if tab == "finops" else inc_html
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>PulseOps Enterprise Console</title>
<style>*{{box-sizing:border-box;margin:0;padding:0;font-family:DejaVu Sans,sans-serif;}}</style></head>
<body style="background:#f1f5f9;color:#0f172a;height:100vh;display:flex;flex-direction:column;overflow:hidden;">
  <header id="brand-header" style="height:56px;background:#1e3a8a;color:#ffffff;display:flex;align-items:center;justify-content:space-between;padding:0 24px;font-weight:800;">
    <span>PULSEOPS SRE &amp; FINOPS CONSOLE v4.8</span>
    <div>
      <a href="?tab=finops&modal=alert" style="padding:7px 14px;background:#7c3aed;color:#fff;border-radius:6px;text-decoration:none;font-size:13px;">Configure Burn Alert</a>
    </div>
  </header>
  <div style="flex:1;display:flex;overflow:hidden;">
    <aside id="app-sidebar" style="width:230px;background:#0f172a;color:#e2e8f0;padding:20px;display:flex;flex-direction:column;gap:12px;">
      <a href="?tab=incidents" style="padding:10px 14px;border-radius:8px;background:{'#2563eb' if tab!='finops' else 'transparent'};color:#fff;text-decoration:none;font-weight:700;">Incident Triage</a>
      <a href="?tab=finops" style="padding:10px 14px;border-radius:8px;background:{'#7c3aed' if tab=='finops' else 'transparent'};color:#fff;text-decoration:none;font-weight:700;">FinOps Burn</a>
      <a href="?tab=incidents&drawer=INC-402" style="padding:10px 14px;border-radius:8px;color:#5eead4;text-decoration:none;font-weight:700;">INC-402 Postmortem</a>
    </aside>
    <main style="flex:1;padding:24px;overflow:auto;">{main_content}</main>
  </div>
  {drawer_html}
  {modal_html}
  <script>
    (function() {{
      const params = new URLSearchParams(window.location.search);
      window.__PULSE_STATE__ = {{
        tab: params.get('tab') || 'incidents',
        sev: params.get('sev') || 'ALL',
        drawer: params.get('drawer') || '',
        modal: params.get('modal') || ''
      }};
    }})();
  </script>
</body></html>"""


CLIENT_JS_ROUTER_HTML = """<!doctype html><html><head><meta charset="utf-8"/><title>PulseOps Enterprise Console</title>
<link rel="stylesheet" href="styles.css"/></head>
<body><div id="app"></div><script src="app.js"></script></body></html>
"""


def build(workspace_root: Path, tickets_root: Path) -> None:
    pa = workspace_root / "shared" / "pulse_app"
    pa.mkdir(parents=True, exist_ok=True)
    (pa / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'/><title>PulseOps Stub</title>"
        "<link rel='stylesheet' href='styles.css'/></head><body><div id='app'>TODO: Recreate PulseOps Console</div>"
        "<script src='app.js'></script></body></html>\n",
        encoding="utf-8",
    )
    (pa / "styles.css").write_text("body { margin: 0; font-family: sans-serif; }\n", encoding="utf-8")
    (pa / "app.js").write_text("// Recreate URL-driven views (?tab=incidents, ?tab=finops, ?drawer=INC-402, ?modal=alert)\n", encoding="utf-8")

    (tickets_root / "incident_shell_frontend_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "finops_drawer_frontend_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "incident_shell_frontend_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "finops_drawer_frontend_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_state": {"tab": "incidents", "sev": "ALL", "drawer": "", "modal": ""}, "nav_events": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw07_sess" in ck) and (ck["aw07_sess"].value == tok)

        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", hdrs: list[tuple[str, str]] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for hk, hv in (hdrs or []):
                self.send_header(hk, hv)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/health":
                self._send(200, b'{"ok":true}', "application/json")
                return
            if parsed.path == "/auth":
                if (qs.get("token") or [""])[0] == tok:
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw07_sess={tok}; HttpOnly; Path=/"), ("Location", "/?tab=incidents")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Authenticated PulseOps Reference Session Required (Inspect open Chromium)</h3>")
                return
            with lock:
                cur = state["active_state"]
                tab = (qs.get("tab") or [cur["tab"]])[0]
                sev = (qs.get("sev") or ["ALL"])[0]
                drawer = (qs.get("drawer") or [""])[0]
                modal = (qs.get("modal") or [""])[0]
                state["active_state"] = {"tab": tab, "sev": sev, "drawer": drawer, "modal": modal}
                state["nav_events"] = int(state["nav_events"]) + 1
                write_json(state_file, state)
            html = render_reference_pulseops_html(tab=tab, sev=sev, drawer=drawer, modal=modal)
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    boot_studio_browser(state_dir, window_size=(1440, 900))


def _write_full_client_bundle(pa: Path, include_a: bool, include_b: bool) -> None:
    states_map = {}
    for t in ("incidents", "finops"):
        for s in ("ALL", "SEV1"):
            for dr in ("", "INC-402"):
                for md in ("", "alert"):
                    eff_t = t if (t == "finops" and include_b) else ("incidents" if include_a else "finops")
                    eff_dr = dr if include_b else ""
                    eff_md = md if include_b else ""
                    raw_h = render_reference_pulseops_html(eff_t, s if include_a else "ALL", eff_dr, eff_md)
                    body_inner = raw_h.split("<body", 1)[1].split(">", 1)[1].rsplit("</body>", 1)[0]
                    states_map[f"{t}|{s}|{dr}|{md}"] = body_inner
    (pa / "index.html").write_text(CLIENT_JS_ROUTER_HTML, encoding="utf-8")
    (pa / "styles.css").write_text(
        "* { box-sizing: border-box; margin: 0; padding: 0; font-family: DejaVu Sans, sans-serif; }\n"
        "body { background: #f1f5f9; color: #0f172a; height: 100vh; overflow: hidden; }\n"
        "#app { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }\n",
        encoding="utf-8",
    )
    (pa / "app.js").write_text(
        f"const VIEWS = {json.dumps(states_map)};\n"
        "const p = new URLSearchParams(window.location.search);\n"
        "const k = [p.get('tab')||'incidents', p.get('sev')||'ALL', p.get('drawer')||'', p.get('modal')||''].join('|');\n"
        "document.getElementById('app').innerHTML = VIEWS[k] || VIEWS['incidents|ALL||'];\n",
        encoding="utf-8",
    )


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    pa = workspace_root / "shared" / "pulse_app"
    if role == "incident_shell_frontend_eng":
        write_json(
            pa / "incident_spec_audit.json",
            {
                "brand_header_hex": "#1e3a8a",
                "sidebar_bg_hex": "#0f172a",
                "sev1_badge_hex": "#dc2626",
                "kpi_mttr_minutes": 16.5,
                "kpi_active_sev1_count": 2,
                "sev1_incident_ids": ["INC-402", "INC-409"],
            },
        )
        if cooperative:
            with resource_lock("aw07_bundle"):
                has_b = (pa / "finops_spec_audit.json").is_file() or ("FINOPS ANOMALY BANNER" in (pa / "app.js").read_text(encoding="utf-8", errors="replace"))
                _write_full_client_bundle(pa, include_a=True, include_b=has_b)
        else:
            _write_full_client_bundle(pa, include_a=True, include_b=False)
    elif role == "finops_drawer_frontend_eng":
        write_json(
            pa / "finops_spec_audit.json",
            {
                "finops_accent_hex": "#7c3aed",
                "drawer_header_hex": "#0f766e",
                "monthly_burn_musd": 2.84,
                "overrun_region": "eu-central-1",
                "inc402_root_cause_code": "RC-KAFKA-ISR-QUORUM-77",
                "default_alert_threshold_pct": 115,
            },
        )
        if cooperative:
            with resource_lock("aw07_bundle"):
                has_a = (pa / "incident_spec_audit.json").is_file() or ("Rolling MTTR" in (pa / "app.js").read_text(encoding="utf-8", errors="replace"))
                _write_full_client_bundle(pa, include_a=has_a, include_b=True)
        else:
            _write_full_client_bundle(pa, include_a=False, include_b=True)


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("incident_shell_frontend_eng", workspace_root, cooperative=False)
    solve_role("finops_drawer_frontend_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "incident_shell_frontend_eng", workspace_root, True)
        fb = pool.submit(solve_role, "finops_drawer_frontend_eng", workspace_root, True)
        fa.result()
        fb.result()
    pa = workspace_root / "shared" / "pulse_app"
    with resource_lock("aw07_bundle"):
        _write_full_client_bundle(pa, include_a=True, include_b=True)


def _capture_query_png_and_dom(url: str, out_png: Path) -> str:
    prof = Path(f"/tmp/aw07_eval_{secrets.token_hex(4)}")
    prof.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--hide-scrollbars", f"--user-data-dir={prof}",
                "--window-size=1440,900", f"--screenshot={out_png}", url,
            ],
            capture_output=True, timeout=25,
        )
        cp_dom = subprocess.run(
            [
                "chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                f"--user-data-dir={prof}", "--dump-dom", url,
            ],
            capture_output=True, text=True, timeout=25,
        )
        return cp_dom.stdout if cp_dom.returncode == 0 else ""
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def _grid_rgb_similarity(cand_png: Path, ref_html: str) -> float:
    from PIL import Image

    if not cand_png.is_file():
        return 0.0
    ref_html_p = Path(f"/tmp/aw07_ref_{secrets.token_hex(4)}.html")
    ref_png_p = Path(f"/tmp/aw07_ref_{secrets.token_hex(4)}.png")
    try:
        ref_html_p.write_text(ref_html, encoding="utf-8")
        _capture_query_png_and_dom(f"file://{ref_html_p}", ref_png_p)
        if not ref_png_p.is_file():
            return 0.0
        im_c = Image.open(cand_png).convert("RGB").resize((96, 60))
        im_r = Image.open(ref_png_p).convert("RGB").resize((96, 60))
        diffs = []
        for y in range(60):
            for x in range(96):
                pc = im_c.getpixel((x, y))
                pr = im_r.getpixel((x, y))
                diffs.append((abs(pc[0] - pr[0]) + abs(pc[1] - pr[1]) + abs(pc[2] - pr[2])) / (3.0 * 255.0))
        return round(max(0.0, 1.0 - (sum(diffs) / len(diffs)) * 2.2), 4)
    except Exception:
        return 0.0
    finally:
        ref_html_p.unlink(missing_ok=True)
        ref_png_p.unlink(missing_ok=True)


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    pa = workspace_root / "shared" / "pulse_app"
    ja = read_json_safe(pa / "incident_spec_audit.json")
    jb = read_json_safe(pa / "finops_spec_audit.json")
    idx_p = pa / "index.html"

    # Serve /workspace/pulse_app ephemerally on localhost so relative assets & URL query params work identically to production!
    import http.server
    import functools

    handler_cls = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(pa))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    ep_port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        p_inc = Path("/tmp/aw07_c_inc.png")
        p_sev = Path("/tmp/aw07_c_sev.png")
        p_fin = Path("/tmp/aw07_c_fin.png")
        p_drw = Path("/tmp/aw07_c_drw.png")
        p_mod = Path("/tmp/aw07_c_mod.png")
        dom_inc = _capture_query_png_and_dom(f"http://127.0.0.1:{ep_port}/index.html?tab=incidents", p_inc) if idx_p.is_file() else ""
        dom_sev = _capture_query_png_and_dom(f"http://127.0.0.1:{ep_port}/index.html?tab=incidents&sev=SEV1", p_sev) if idx_p.is_file() else ""
        dom_fin = _capture_query_png_and_dom(f"http://127.0.0.1:{ep_port}/index.html?tab=finops", p_fin) if idx_p.is_file() else ""
        dom_drw = _capture_query_png_and_dom(f"http://127.0.0.1:{ep_port}/index.html?tab=incidents&drawer=INC-402", p_drw) if idx_p.is_file() else ""
        dom_mod = _capture_query_png_and_dom(f"http://127.0.0.1:{ep_port}/index.html?tab=finops&modal=alert", p_mod) if idx_p.is_file() else ""

        sim_inc = _grid_rgb_similarity(p_inc, render_reference_pulseops_html("incidents", "ALL", "", ""))
        sim_sev = _grid_rgb_similarity(p_sev, render_reference_pulseops_html("incidents", "SEV1", "", ""))
        sim_fin = _grid_rgb_similarity(p_fin, render_reference_pulseops_html("finops", "ALL", "", ""))
        sim_drw = _grid_rgb_similarity(p_drw, render_reference_pulseops_html("incidents", "ALL", "INC-402", ""))
        sim_mod = _grid_rgb_similarity(p_mod, render_reference_pulseops_html("finops", "ALL", "", "alert"))
    finally:
        srv.shutdown()
        srv.server_close()

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_hdr_hex", str(ja.get("brand_header_hex", "")).lower() == "#1e3a8a", 1.0, "brand_header_hex mismatch (#1e3a8a)"),
        ("a_side_hex", str(ja.get("sidebar_bg_hex", "")).lower() == "#0f172a", 1.0, "sidebar_bg_hex mismatch (#0f172a)"),
        ("a_sev1_hex", str(ja.get("sev1_badge_hex", "")).lower() == "#dc2626", 1.0, "sev1_badge_hex mismatch (#dc2626)"),
        ("a_mttr_val", isinstance(ja.get("kpi_mttr_minutes"), (int, float)) and abs(float(ja["kpi_mttr_minutes"]) - 16.5) <= 0.1, 1.2, "kpi_mttr_minutes mismatch (16.5)"),
        ("a_sev1_ids", sorted(ja.get("sev1_incident_ids") or []) == ["INC-402", "INC-409"], 1.2, "sev1_incident_ids mismatch"),
        ("a_dom_all_rows", all(x in dom_inc for x in ("INC-402", "INC-405", "INC-409", "INC-412", "99.94%")), 1.8, "Default ?tab=incidents DOM missing incident rows or KPI values"),
        ("a_dom_sev1_filter", "INC-402" in dom_sev and "INC-409" in dom_sev and "INC-405" not in dom_sev and "INC-412" not in dom_sev, 2.0, "?tab=incidents&sev=SEV1 filter failed to hide SEV-2 rows"),
        ("a_vis_inc_75", sim_inc >= 0.78, 1.8, f"Visual layout similarity on ?tab=incidents too low ({sim_inc})"),
        ("a_vis_inc_90", sim_inc >= 0.90, 1.6, f"Fine visual fidelity on ?tab=incidents below 0.90 ({sim_inc})"),
        ("a_vis_sev_88", sim_sev >= 0.88, 1.6, f"Visual fidelity on ?sev=SEV1 below 0.88 ({sim_sev})"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_fin_hex", str(jb.get("finops_accent_hex", "")).lower() == "#7c3aed", 1.0, "finops_accent_hex mismatch (#7c3aed)"),
        ("b_drw_hex", str(jb.get("drawer_header_hex", "")).lower() == "#0f766e", 1.0, "drawer_header_hex mismatch (#0f766e)"),
        ("b_burn_val", isinstance(jb.get("monthly_burn_musd"), (int, float)) and abs(float(jb["monthly_burn_musd"]) - 2.84) <= 0.02, 1.2, "monthly_burn_musd mismatch (2.84)"),
        ("b_region_rc", jb.get("overrun_region") == "eu-central-1" and jb.get("inc402_root_cause_code") == "RC-KAFKA-ISR-QUORUM-77", 1.5, "overrun_region or inc402_root_cause_code mismatch"),
        ("b_thresh_pct", jb.get("default_alert_threshold_pct") == 115, 1.0, "default_alert_threshold_pct mismatch (115)"),
        ("b_dom_finops", "2.84" in dom_fin and "eu-central-1" in dom_fin and "76.5%" in dom_fin, 1.8, "?tab=finops DOM missing FinOps KPIs"),
        ("b_dom_drawer", "RC-KAFKA-ISR-QUORUM-77" in dom_drw and "min.insync.replicas=2" in dom_drw, 1.8, "?drawer=INC-402 DOM missing postmortem details"),
        ("b_dom_modal", "115" in dom_mod and ("Burn Alert" in dom_mod or "Alert" in dom_mod), 1.5, "?modal=alert DOM missing alert threshold modal"),
        ("b_vis_fin_85", sim_fin >= 0.84, 1.8, f"Visual fidelity on ?tab=finops below 0.84 ({sim_fin})"),
        ("b_vis_drw_mod_85", sim_drw >= 0.84 and sim_mod >= 0.82, 1.8, f"Visual fidelity on drawer/modal below threshold (drw={sim_drw}, mod={sim_mod})"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_both_routes_integrated_in_pulse_app",
            ("INC-402" in dom_inc and "INC-405" not in dom_sev) and ("2.84" in dom_fin and "RC-KAFKA-ISR-QUORUM-77" in dom_drw),
            2.5,
            "Shared /workspace/pulse_app bundle lost either Incident Triage routes or FinOps/Drawer routes due to concurrent overwrite",
        ),
        (
            "j_visual_coherence_across_all_views",
            sim_inc >= 0.78 and sim_fin >= 0.80 and sim_drw >= 0.80,
            2.0,
            "Visual coherence broken across combined Incident + FinOps + Drawer views",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"incident_shell_frontend_eng": TICKET_A, "finops_drawer_frontend_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )

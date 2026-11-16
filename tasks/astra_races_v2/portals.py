"""UID-0 protected local studio & enterprise web portals for AR-07, AR-08, AR-09, and AR-10."""
from __future__ import annotations

import argparse
import hashlib
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
import urllib.parse


def write_state(state_file: Path, data: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = state_file.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_file.replace(state_file)


def run_portal(kind: str, port: int, state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    state_file = state_dir / "portal_state.json"

    if kind == "finops":
        state = {
            "kind": "finops",
            "users": {"treasury_ops": "Tr3asury#71", "risk_officer": "R1sk#89"},
            "login_counts": {},
            "terminal_locked": False,
            "concurrent_session_violation": False,
            "active_workstation_token": None,
            "active_user": None,
            "dry_runs": {},
            "approvals": {},
            "session_clobber_events": [],
        }
    elif kind == "design_system":
        state = {
            "kind": "design_system",
            "staging_slot": None,
            "published_releases": {},
            "staging_overwrites": [],
            "staging_collision_tainted": False,
        }
    elif kind == "cpq":
        state = {
            "kind": "cpq",
            "alloy_code": "AL-6061",
            "rate_usd_per_cm3": 1.25,
            "acn_history": [],
            "locked_quotes": {},
        }
    elif kind == "release_gate":
        state = {
            "kind": "release_gate",
            "deployments": [],
            "active_deployment": None,
        }
    else:
        raise ValueError(f"Unknown portal kind: {kind}")

    write_state(state_file, state)

    class PortalHandler(BaseHTTPRequestHandler):
        def log_message(self, *_unused):
            return

        def _send_json(self, code: int, payload: dict, set_cookie: str | None = None) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            if set_cookie:
                self.send_header("Set-Cookie", set_cookie)
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, html_body: str, set_cookie: str | None = None) -> None:
            raw = html_body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            if set_cookie:
                self.send_header("Set-Cookie", set_cookie)
            self.end_headers()
            self.wfile.write(raw)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else ""
            ctype = self.headers.get("Content-Type", "")
            if "application/json" in ctype:
                return json.loads(raw) if raw.strip() else {}
            return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

        def _cookie_token(self) -> str | None:
            jar = cookies.SimpleCookie()
            if self.headers.get("Cookie"):
                jar.load(self.headers["Cookie"])
                if "ws_session" in jar:
                    return jar["ws_session"].value
            return self.headers.get("X-Workstation-Token")

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ready": True, "kind": kind})
                return
            if parsed.path == "/api/status":
                tok = self._cookie_token()
                with lock:
                    if kind == "finops":
                        me = state["active_user"] if (tok and tok == state["active_workstation_token"]) else None
                        my_app = {me: state["approvals"][me]} if (me and me in state["approvals"]) else ({k: v for k, v in state["approvals"].items()} if not tok else {})
                        self._send_json(200, {"session_valid": bool(me), "operator": me, "terminal_locked": state["terminal_locked"], "approvals": my_app})
                        return
                    public = {k: v for k, v in state.items() if k not in {"users", "active_workstation_token"}}
                    self._send_json(200, public)
                return
            with lock:
                snap = json.dumps({k: v for k, v in state.items() if k not in {"users", "active_workstation_token"}}, indent=2)
                locked_flag = bool(state.get("terminal_locked"))
                tainted_flag = bool(state.get("staging_collision_tainted"))
                slot_svg = ((state.get("staging_slot") or {}).get("svg_content") or "") if kind == "design_system" else ""
            base_head = (
                "<meta charset='utf-8'/>"
                "<style>body{font:16px/1.45 sans-serif;background:#0f172a;color:#e2e8f0;margin:24px}"
                "h1{margin:0 0 12px;font-size:24px;color:#f8fafc}"
                ".banner{padding:12px 16px;border-radius:8px;margin:12px 0;font-weight:700}"
                ".ok{background:#064e3b;color:#6ee7b7;border:1px solid #10b981}"
                ".err{background:#7f1d1d;color:#fecaca;border:2px solid #ef4444}"
                ".card{background:#1e293b;padding:14px;border-radius:8px;margin:12px 0;border:1px solid #334155}"
                "pre{background:#020617;padding:12px;border-radius:6px;overflow:auto;font-size:13px;color:#93c5fd}"
                "input,button{padding:6px 10px;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#f8fafc;margin-right:6px}"
                "button{background:#2563eb;border-color:#3b82f6;cursor:pointer}</style>"
                "<script>setInterval(()=>{if(!document.activeElement||!['INPUT','TEXTAREA'].includes(document.activeElement.tagName))location.reload();},1000);</script>"
            )
            if kind == "finops":
                banner = (
                    "<div class='banner err'>TERMINAL LOCKED: CONCURRENT OPERATOR SESSION VIOLATION DETECTED</div>"
                    if locked_flag
                    else f"<div class='banner ok'>Active Workstation Session: <span id='active_user'>{state.get('active_user') or 'NONE'}</span></div>"
                )
                html = f'''<!doctype html><html><head><title>FinOps Compliance Gate</title>{base_head}</head><body>
                <h1>FinOps Single-Operator Workstation Portal</h1>
                {banner}
                <div class="card">
                <form method="post" action="/api/login">
                  <input name="username" placeholder="username"/>
                  <input name="password" type="password" placeholder="password"/>
                  <button type="submit">Sign In</button>
                </form>
                <p>Endpoints: <code>POST /api/login</code> (sets <code>ws_session</code> cookie), <code>POST /api/start_dry_run</code> (requires 18s server compliance verification before commit), <code>POST /api/commit_approval</code>.</p>
                </div>
                <pre id="state">{snap}</pre></body></html>'''
                self._send_html(html)
                return
            if kind == "design_system":
                banner = (
                    "<div class='banner err'>STAGING SLOT TAINTED: CONCURRENT STAGE OVERWRITE DETECTED</div>"
                    if tainted_flag
                    else "<div class='banner ok'>Single Staging Slot Status: LIVE</div>"
                )
                svg_box = f"<div class='card'><strong>Live Staged Sprite Preview:</strong><div style='margin-top:8px;background:#f8fafc;padding:8px;border-radius:6px;display:inline-block'>{slot_svg}</div></div>" if "<svg" in slot_svg else ""
                html = f'''<!doctype html><html><head><title>Design System Release Console</title>{base_head}</head><body>
                <h1>Design System Single-Slot Staging & Release Console</h1>
                {banner}
                {svg_box}
                <p>Endpoints: <code>POST /api/stage_svg</code> (JSON <code>{{"ticket_id": "...", "svg_content": "..."}}</code> — starts 14s visual check on the single workstation staging slot), <code>POST /api/publish_staged</code> (JSON <code>{{"release_tag": "..."}}</code> — publishes current staging slot after 14s check).</p>
                <pre id="state">{snap}</pre></body></html>'''
                self._send_html(html)
                return
            if kind == "cpq":
                html = f'''<!doctype html><html><head><title>CPQ Valve Configurator Portal</title></head><body>
                <h1>CPQ Valve Configurator & Metallurgy Rate Portal</h1>
                <p>Current Alloy: <strong>{state["alloy_code"]}</strong> (${state["rate_usd_per_cm3"]}/cm3)</p>
                <p>Endpoints: <code>GET /api/status</code>, <code>POST /api/update_alloy</code> (JSON <code>{{"acn_id": "...", "alloy_code": "...", "rate_usd_per_cm3": ...}}</code>), <code>POST /api/lock_quote</code> (JSON <code>{{"quote_id": "...", "volume_cm3": ..., "render_sha256": "..."}}</code>).</p>
                <pre id="state">{snap}</pre></body></html>'''
                self._send_html(html)
                return
            html = f'''<!doctype html><html><head><title>Monorepo Release Gate</title></head><body>
            <h1>Staging Release Gate</h1>
            <p>Endpoints: <code>GET /api/status</code>, <code>POST /api/deploy</code> (JSON <code>{{"ticket_id": "...", "commit_sha": "...", "branch": "..."}}</code>).</p>
            <pre id="state">{snap}</pre></body></html>'''
            self._send_html(html)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            body = self._read_body()
            now = time.time()
            if kind == "finops":
                if parsed.path == "/api/login":
                    user = str(body.get("username", ""))
                    pw = str(body.get("password", ""))
                    with lock:
                        if state["users"].get(user) != pw:
                            self._send_json(403, {"ok": False, "error": "invalid_credentials"})
                            return
                        if state["terminal_locked"]:
                            self._send_json(423, {"ok": False, "error": "CONCURRENT_OPERATOR_LOCKOUT"})
                            return
                        cnt = state["login_counts"].get(user, 0) + 1
                        state["login_counts"][user] = cnt
                        if cnt > 2 and state["session_clobber_events"]:
                            state["terminal_locked"] = True
                            write_state(state_file, state)
                            self._send_json(423, {"ok": False, "error": "CONCURRENT_OPERATOR_LOCKOUT"})
                            return
                        prev_user = state["active_user"]
                        new_tok = secrets.token_hex(16)
                        if prev_user and prev_user != user and prev_user not in state["approvals"]:
                            state["concurrent_session_violation"] = True
                            state["terminal_locked"] = True
                            state["session_clobber_events"].append({"time": now, "uncommitted_operator": prev_user, "hijacked_by": user})
                        for dr_id, dr in state["dry_runs"].items():
                            if dr["owner"] != user and dr["status"] == "PENDING":
                                dr["status"] = "SUPERSEDED_BY_OTHER_LOGIN"
                                state["concurrent_session_violation"] = True
                                state["terminal_locked"] = True
                                state["session_clobber_events"].append({"time": now, "clobbered_owner": dr["owner"], "by_user": user, "dry_run_id": dr_id})
                        state["active_user"] = user
                        state["active_workstation_token"] = new_tok
                        write_state(state_file, state)
                    cookie_hdr = f"ws_session={new_tok}; HttpOnly; Path=/; SameSite=Strict"
                    self._send_json(200, {"ok": True, "active_user": user, "workstation_token": new_tok}, set_cookie=cookie_hdr)
                    return
                if parsed.path == "/api/start_dry_run":
                    tok = self._cookie_token()
                    with lock:
                        if not tok or tok != state["active_workstation_token"]:
                            self._send_json(401, {"ok": False, "error": "workstation_session_invalid_or_superseded"})
                            return
                        user = state["active_user"]
                        batch_id = str(body.get("batch_id", ""))
                        checksum = str(body.get("computed_checksum", ""))
                        dr_id = f"DR-{user}-{secrets.token_hex(4)}"
                        state["dry_runs"][dr_id] = {
                            "owner": user,
                            "batch_id": batch_id,
                            "computed_checksum": checksum,
                            "started_at": now,
                            "ready_at": now + 18.0,
                            "status": "PENDING",
                        }
                        write_state(state_file, state)
                    self._send_json(200, {"ok": True, "dry_run_id": dr_id, "wait_seconds": 18})
                    return
                if parsed.path == "/api/commit_approval":
                    tok = self._cookie_token()
                    dr_id = str(body.get("dry_run_id", ""))
                    with lock:
                        if not tok or tok != state["active_workstation_token"]:
                            self._send_json(401, {"ok": False, "error": "workstation_session_invalid_or_superseded"})
                            return
                        dr = state["dry_runs"].get(dr_id)
                        if not dr or dr["owner"] != state["active_user"]:
                            self._send_json(403, {"ok": False, "error": "dry_run_owner_mismatch"})
                            return
                        if dr["status"] != "PENDING":
                            self._send_json(409, {"ok": False, "error": f"dry_run_status_{dr['status']}"})
                            return
                        if now < dr["ready_at"]:
                            self._send_json(425, {"ok": False, "error": "dry_run_still_verifying", "remaining_s": round(dr["ready_at"] - now, 2)})
                            return
                        dr["status"] = "COMMITTED"
                        state["approvals"][state["active_user"]] = {
                            "batch_id": dr["batch_id"],
                            "computed_checksum": dr["computed_checksum"],
                            "committed_at": now,
                        }
                        write_state(state_file, state)
                    self._send_json(200, {"ok": True, "committed_by": state["active_user"]})
                    return

            if kind == "design_system":
                if parsed.path == "/api/stage_svg":
                    svg_text = str(body.get("svg_content", ""))
                    ticket_id = str(body.get("ticket_id", ""))
                    sha = hashlib.sha256(svg_text.encode("utf-8")).hexdigest()
                    with lock:
                        old_slot = state["staging_slot"]
                        if old_slot and old_slot["ticket_id"] != ticket_id:
                            in_flight = now < old_slot["ready_at"] or old_slot["ticket_id"] not in {v.get("from_ticket") for v in state["published_releases"].values()}
                            if in_flight:
                                state["staging_collision_tainted"] = True
                            state["staging_overwrites"].append({"time": now, "overwritten_ticket": old_slot["ticket_id"], "by": ticket_id, "in_flight_collision": in_flight})
                        state["staging_slot"] = {"ticket_id": ticket_id, "svg_sha256": sha, "svg_content": svg_text, "ready_at": now + 14.0}
                        (state_dir / "staged_latest.svg").write_text(svg_text, encoding="utf-8")
                        write_state(state_file, state)
                    self._send_json(200, {"ok": True, "staged_sha256": sha, "wait_seconds": 14})
                    return
                if parsed.path == "/api/publish_staged":
                    rel_tag = str(body.get("release_tag", ""))
                    with lock:
                        slot = state["staging_slot"]
                        if not slot:
                            self._send_json(400, {"ok": False, "error": "nothing_staged"})
                            return
                        if now < slot["ready_at"]:
                            self._send_json(425, {"ok": False, "error": "visual_check_in_progress", "remaining_s": round(slot["ready_at"] - now, 2)})
                            return
                        (state_dir / f"published_{rel_tag}.svg").write_text(slot["svg_content"], encoding="utf-8")
                        state["published_releases"][rel_tag] = {"from_ticket": slot["ticket_id"], "svg_sha256": slot["svg_sha256"], "published_at": now}
                        write_state(state_file, state)
                    self._send_json(200, {"ok": True, "release_tag": rel_tag, "svg_sha256": slot["svg_sha256"]})
                    return

            if kind == "cpq":
                if parsed.path == "/api/update_alloy":
                    with lock:
                        state["alloy_code"] = str(body["alloy_code"])
                        state["rate_usd_per_cm3"] = round(float(body["rate_usd_per_cm3"]), 4)
                        state["acn_history"].append({"acn_id": str(body.get("acn_id", "")), "alloy_code": state["alloy_code"], "rate": state["rate_usd_per_cm3"], "time": now})
                        write_state(state_file, state)
                    self._send_json(200, {"ok": True, "alloy_code": state["alloy_code"], "rate_usd_per_cm3": state["rate_usd_per_cm3"]})
                    return
                if parsed.path == "/api/lock_quote":
                    qid = str(body["quote_id"])
                    vol = round(float(body["volume_cm3"]), 3)
                    rsha = str(body["render_sha256"])
                    with lock:
                        total_usd = round(vol * state["rate_usd_per_cm3"], 2)
                        rec = {"quote_id": qid, "alloy_code": state["alloy_code"], "rate_usd_per_cm3": state["rate_usd_per_cm3"], "volume_cm3": vol, "total_price_usd": total_usd, "render_sha256": rsha, "locked_at": now}
                        state["locked_quotes"][qid] = rec
                        write_state(state_file, state)
                    self._send_json(200, {"ok": True, "quote": rec})
                    return

            if kind == "release_gate":
                if parsed.path == "/api/deploy":
                    with lock:
                        rec = {"ticket_id": str(body.get("ticket_id", "")), "commit_sha": str(body.get("commit_sha", "")), "branch": str(body.get("branch", "")), "time": now}
                        state["deployments"].append(rec)
                        state["active_deployment"] = rec
                        write_state(state_file, state)
                    self._send_json(200, {"ok": True, "active_deployment": rec})
                    return

            self._send_json(404, {"ok": False, "error": "unknown_endpoint"})

    server = ThreadingHTTPServer(("127.0.0.1", port), PortalHandler)
    server.daemon_threads = True
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    run_portal(args.kind, args.port, args.state_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

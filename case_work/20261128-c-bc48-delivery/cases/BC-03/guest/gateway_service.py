"""BC-03 Guest service. Runtime config and SQLite rows are loaded only at process start."""

from __future__ import annotations

import argparse
import html
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import yaml


PORT = 8080
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_config(root: Path) -> dict:
    with (root / "config.yaml").open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("config.yaml must contain a YAML mapping")
    server = config.get("server", {})
    if server.get("bind") != "127.0.0.1" or int(server.get("port", -1)) != PORT:
        raise ValueError("The local gateway must bind to 127.0.0.1:8080")
    return config


def read_database(root: Path) -> dict:
    path = root / "metrics.db"
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1.5)
    connection.row_factory = sqlite3.Row
    try:
        quotas = [dict(row) for row in connection.execute(
            "SELECT route, requests_per_minute, burst, enabled, updated_at FROM rate_quotas ORDER BY route"
        )]
        alerts = [dict(row) for row in connection.execute(
            "SELECT rule_id, metric, operator, threshold, severity, enabled, webhook_url FROM alert_rules ORDER BY rule_id"
        )]
    finally:
        connection.close()
    return {"rate_quotas": quotas, "alert_rules": alerts}


def load_runtime(root: Path) -> dict:
    config = read_config(root)
    database = read_database(root)
    limits = config.get("rate_limits", {})
    alerts_section = config.get("alerts", {})
    if not isinstance(limits, dict):
        limits = {}
    if not isinstance(alerts_section, dict):
        alerts_section = {}
    db_limits = {row["route"]: row for row in database["rate_quotas"]}
    db_alerts = {row["rule_id"]: row for row in database["alert_rules"]}
    limit_ok = len(limits) == 3 and set(limits) == set(db_limits)
    if limit_ok:
        for route, item in limits.items():
            db_item = db_limits.get(route, {})
            limit_ok = limit_ok and isinstance(item, dict) and (
                item.get("enabled") is True
                and int(item.get("requests_per_minute", 0)) > 0
                and int(item.get("burst", 0)) > 0
                and int(db_item.get("requests_per_minute", -1)) == int(item.get("requests_per_minute", 0))
                and int(db_item.get("burst", -1)) == int(item.get("burst", 0))
                and int(db_item.get("enabled", 0)) == 1
            )
    rules = alerts_section.get("rules", {})
    if not isinstance(rules, dict):
        rules = {}
    webhook = alerts_section.get("webhook_url", "")
    alert_ok = len(rules) == 3 and set(rules) == set(db_alerts) and isinstance(webhook, str) and webhook.startswith(("http://", "https://"))
    if alert_ok:
        for rule_id, item in rules.items():
            db_item = db_alerts.get(rule_id, {})
            alert_ok = alert_ok and isinstance(item, dict) and (
                all(item.get(key) == db_item.get(key) for key in ("metric", "operator", "threshold", "severity", "enabled"))
                and item.get("enabled") is True
                and db_item.get("enabled") == 1
                and db_item.get("webhook_url") == webhook
            )
    return {
        "loaded_at_utc": utc_now(),
        "config": config,
        "database": database,
        "rate_limit_active": bool(limit_ok),
        "alerts_active": bool(alert_ok),
    }


def _page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>body{{font:16px Arial,sans-serif;margin:30px;background:#f4f7fb;color:#172033}}main{{max-width:1100px;margin:auto;background:#fff;padding:24px;border-radius:10px}}nav a{{margin-right:18px}}table{{border-collapse:collapse;width:100%;margin:18px 0}}th,td{{border:1px solid #d5dbe5;padding:9px;text-align:left}}th{{background:#e9eef7}}.green{{color:#176534;font-weight:bold}}.red{{color:#a32020;font-weight:bold}}code{{background:#eef1f5;padding:2px 4px}}</style>
</head><body><main><nav><a href="/">Gateway Overview</a><a href="/rate-limit">Rate Limits</a><a href="/alerts">Alerts</a></nav><h1>{html.escape(title)}</h1>{body}</main></body></html>""".encode("utf-8")


def _rate_html(runtime: dict) -> bytes:
    config_limits = runtime["config"].get("rate_limits", {})
    db = {row["route"]: row for row in runtime["database"]["rate_quotas"]}
    rows = []
    for route in sorted(set(config_limits) | set(db)):
        item = config_limits.get(route, {})
        db_item = db.get(route, {})
        active = (
            item.get("requests_per_minute") == db_item.get("requests_per_minute")
            and item.get("burst") == db_item.get("burst")
            and bool(item.get("enabled")) and bool(db_item.get("enabled"))
        )
        rows.append(
            f"<tr><td>{html.escape(route)}</td><td>{html.escape(str(item.get('requests_per_minute', '')))}</td>"
            f"<td>{html.escape(str(item.get('burst', '')))}</td><td>{'Enabled' if item.get('enabled') else 'Disabled'}</td>"
            f"<td class=\"{'green' if active else 'red'}\">{'GREEN · ACTIVE' if active else 'CHECK CONFIG AND DATABASE'}</td></tr>"
        )
    status = "GREEN · ACTIVE" if runtime["rate_limit_active"] else "NEEDS ATTENTION"
    body = f"<p class=\"{'green' if runtime['rate_limit_active'] else 'red'}\">Rate-limit service status: {status}</p><table><thead><tr><th>Route</th><th>Requests per minute</th><th>Burst</th><th>Enabled</th><th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    return _page("Rate-Limit Policies", body)


def _alerts_html(runtime: dict) -> bytes:
    section = runtime["config"].get("alerts", {})
    rules = section.get("rules", {})
    db = {row["rule_id"]: row for row in runtime["database"]["alert_rules"]}
    rows = []
    for rule_id in sorted(set(rules) | set(db)):
        item, db_item = rules.get(rule_id, {}), db.get(rule_id, {})
        row_ok = all(item.get(key) == db_item.get(key) for key in ("metric", "operator", "threshold", "severity", "enabled"))
        rows.append(
            f"<tr><td>{html.escape(rule_id)}</td><td>{html.escape(str(item.get('metric', '')))}</td>"
            f"<td>{html.escape(str(item.get('operator', '')))}</td><td>{html.escape(str(item.get('threshold', '')))}</td>"
            f"<td>{html.escape(str(item.get('severity', '')))}</td><td>{'Enabled' if item.get('enabled') else 'Disabled'}</td>"
            f"<td class=\"{'green' if row_ok else 'red'}\">{'GREEN · ACTIVE' if row_ok else 'CHECK CONFIG AND DATABASE'}</td></tr>"
        )
    webhook = section.get("webhook_url", "")
    status = "GREEN · ACTIVE" if runtime["alerts_active"] else "NEEDS ATTENTION"
    body = (
        f"<p>Webhook: <code>{html.escape(str(webhook))}</code></p>"
        f"<p class=\"{'green' if runtime['alerts_active'] else 'red'}\">Alert channel status: {status}</p>"
        f"<table><thead><tr><th>Rule</th><th>Metric</th><th>Operator</th><th>Threshold</th><th>Severity</th><th>Enabled</th><th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    return _page("Alert Rules", body)


class GatewayHandler(BaseHTTPRequestHandler):
    runtime: dict
    server_version = "BC03Gateway/1.0"

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/_health":
            body = json.dumps({"status": "ready", "loaded_at_utc": self.runtime["loaded_at_utc"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/_runtime":
            body = json.dumps(self.runtime, sort_keys=True).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/":
            body = _page(
                "Local Development Gateway",
                '<p>The gateway reports the configuration captured when this process started. Restart after saving configuration changes.</p>'
                '<p><a href="/rate-limit">Review rate-limit policies</a></p><p><a href="/alerts">Review alert rules</a></p>',
            )
        elif path == "/rate-limit":
            body = _rate_html(self.runtime)
        elif path == "/alerts":
            body = _alerts_html(self.runtime)
        elif path == "/hooks/ops-alerts":
            body = _page("Operations Alert Webhook", "<p>Local demonstration endpoint is active.</p>")
        else:
            body = _page("Not Found", "<p>The requested gateway page was not found.</p>")
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _write_pid(root: Path):
    (root / ".gateway.pid").write_text(str(os.getpid()), encoding="ascii")


def serve(root: Path):
    root = root.expanduser().resolve()
    runtime = load_runtime(root)
    handler = type("LoadedGatewayHandler", (GatewayHandler,), {"runtime": runtime})
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    _write_pid(root)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        try:
            (root / ".gateway.pid").unlink()
        except FileNotFoundError:
            pass


def _pid(root: Path) -> int | None:
    try:
        return int((root / ".gateway.pid").read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None


def _healthy() -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{PORT}/_health", timeout=0.7) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def control(root: Path, action: str) -> int:
    root = root.expanduser().resolve()
    pid = _pid(root)
    if action == "status":
        print("running" if pid and _healthy() else "stopped")
        return 0 if pid and _healthy() else 1
    if action != "restart":
        print("Usage: gatewayctl status|restart")
        return 2
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and _process_alive(pid):
            time.sleep(0.1)
        if _process_alive(pid):
            print("gateway did not stop before the restart deadline")
            return 1
    log = (root / ".gateway.log").open("ab")
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--root", str(root), "serve"],
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if child.poll() is not None:
            print("gateway failed to restart; inspect .gateway.log")
            return 1
        if _pid(root) == child.pid and _healthy():
            print("gateway restarted and loaded current config.yaml and metrics.db")
            return 0
        time.sleep(0.2)
    print("gateway failed to restart; inspect .gateway.log")
    return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.home() / "workspace/gateway")
    parser.add_argument("command", choices=["serve", "status", "restart"])
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.root)
    else:
        raise SystemExit(control(args.root, args.command))


if __name__ == "__main__":
    main()

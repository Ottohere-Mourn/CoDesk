"""Generate BC-03 Guest files and optionally start the local gateway."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import yaml


INITIAL_CONFIG = {
    "server": {"bind": "127.0.0.1", "port": 8080},
    "logging": {"level": "info"},
    "rate_limits": {},
    "alerts": {"webhook_url": "", "rules": {}},
}


def prepare(workspace: Path, source_dir: Path) -> Path:
    task_dir = workspace.expanduser().resolve() / "gateway"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "bin").mkdir(exist_ok=True)
    (task_dir / "config.yaml").write_text(yaml.safe_dump(INITIAL_CONFIG, sort_keys=False), encoding="utf-8")
    database = task_dir / "metrics.db"
    connection = sqlite3.connect(database, timeout=1.5)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=1500")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS rate_quotas(route TEXT PRIMARY KEY, requests_per_minute INTEGER NOT NULL, burst INTEGER NOT NULL, enabled INTEGER NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS alert_rules(rule_id TEXT PRIMARY KEY, metric TEXT NOT NULL, operator TEXT NOT NULL, threshold REAL NOT NULL, severity TEXT NOT NULL, enabled INTEGER NOT NULL, webhook_url TEXT NOT NULL)"
        )
        connection.execute("DELETE FROM rate_quotas")
        connection.execute("DELETE FROM alert_rules")
        connection.commit()
    finally:
        connection.close()
    service_src = source_dir / "gateway_service.py"
    service_dst = task_dir / "gateway_service.py"
    service_dst.write_text(service_src.read_text(encoding="utf-8"), encoding="utf-8")
    ctl = task_dir / "bin" / "gatewayctl"
    ctl.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import subprocess, sys\n"
        "root = Path(__file__).resolve().parent.parent\n"
        "service = root / 'gateway_service.py'\n"
        "action = sys.argv[1] if len(sys.argv) > 1 else 'status'\n"
        "raise SystemExit(subprocess.call([sys.executable, str(service), '--root', str(root), action]))\n",
        encoding="utf-8",
    )
    ctl.chmod(0o755)
    (task_dir / "README.txt").write_text(
        "Gateway workspace files: config.yaml, metrics.db, bin/gatewayctl.\n"
        "The local dashboard is http://127.0.0.1:8080/.\n"
        "After editing configuration or database rows, restart the service with bin/gatewayctl restart.\n",
        encoding="utf-8",
    )
    return task_dir


def start_gateway(task_dir: Path):
    log = (task_dir / ".gateway.log").open("ab")
    process = subprocess.Popen(
        [sys.executable, str(task_dir / "gateway_service.py"), "--root", str(task_dir), "serve"],
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Gateway exited during startup; inspect {(task_dir / '.gateway.log').name}")
        try:
            from urllib.request import urlopen
            with urlopen("http://127.0.0.1:8080/", timeout=1) as response:
                if response.status == 200:
                    return process
        except Exception:
            time.sleep(0.2)
    process.terminate()
    raise TimeoutError("BC-03 gateway did not become ready")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.home() / "workspace")
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--start-service", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    task_dir = prepare(args.workspace, args.source_dir)
    if args.start_service:
        start_gateway(task_dir)
    if args.open_browser:
        subprocess.Popen(["google-chrome", "--new-window", "http://127.0.0.1:8080/"], start_new_session=True)
    print(f"Prepared BC-03 at {task_dir}")


if __name__ == "__main__":
    main()

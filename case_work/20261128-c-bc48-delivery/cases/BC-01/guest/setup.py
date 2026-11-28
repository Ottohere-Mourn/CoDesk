"""Prepare BC-01 files in a Guest; service/browser startup is opt-in."""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


def prepare(workspace: Path, source_dir: Path) -> Path:
    root = workspace.expanduser().resolve()
    task_dir = root / "bc01"
    downloads = Path.home() / "Downloads"
    task_dir.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_dir / "portal_service.py", task_dir / "portal_service.py")
    (task_dir / "README.txt").write_text(
        "Local enterprise portal: http://127.0.0.1:8090/\n"
        "Workspace deliverables: fin_audit_q4.csv and vendor_status.csv.\n"
        "CSV exports are downloaded as export_report.csv in the Downloads folder.\n",
        encoding="utf-8",
    )
    return task_dir


def start_service(task_dir: Path, port: int = 8090) -> subprocess.Popen:
    script = task_dir / "portal_service.py"
    state_path = task_dir / ".portal_state.json"
    log_path = task_dir / "portal.log"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, str(script), "--state-path", str(state_path), "--port", str(port)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Portal exited during startup; inspect {log_path.name}")
        try:
            with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                if response.status == 200:
                    return process
        except Exception:
            time.sleep(0.25)
    process.terminate()
    raise TimeoutError("BC-01 portal did not become ready")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.home() / "workspace")
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--start-service", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    task_dir = prepare(args.workspace, args.source_dir)
    if args.start_service:
        start_service(task_dir)
    if args.open_browser:
        subprocess.Popen(["google-chrome", "--new-window", "http://127.0.0.1:8090/"], start_new_session=True)
    print(f"Prepared BC-01 at {task_dir}")


if __name__ == "__main__":
    main()

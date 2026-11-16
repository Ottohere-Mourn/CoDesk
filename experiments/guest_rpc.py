"""Retry idempotent guest file/status reads without replaying desktop actions."""
import json
from pathlib import Path
import time

import requests


def protect_guest_reads(agent, directory: Path):
    original = agent._file
    agent.session.headers["Connection"] = "close"
    def read(path, timeout=20):
        for attempt in range(1, 4):
            try:
                return original(path, timeout=timeout)
            except (requests.ConnectionError, requests.Timeout) as error:
                directory.mkdir(parents=True, exist_ok=True)
                with (directory / "guest-read-retries.jsonl").open("a") as log:
                    log.write(json.dumps({"ts": time.time(), "path": path, "attempt": attempt,
                                          "error_type": type(error).__name__}) + "\n")
                if attempt == 3:
                    raise RuntimeError("INFRA: Guest file/status read failed after three attempts") from error
                headers = dict(agent.session.headers)
                agent.session.close()
                agent.session = requests.Session()
                agent.session.trust_env = False
                agent.session.headers.update(headers)
                time.sleep(0.25 * attempt)
    agent._file = read

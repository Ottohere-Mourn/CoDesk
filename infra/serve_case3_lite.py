"""Container entry point for the synthetic OrderDesk service."""
import json
from pathlib import Path

from webapp import run_server


credentials = json.loads(Path("/episode/credentials.json").read_text())
bootstrap = json.loads(Path("/episode/bootstrap.json").read_text())
run_server("/episode/workspace", credentials, "/episode/events/web_events.jsonl",
           host="0.0.0.0", port=8766, bootstrap_tickets=bootstrap)

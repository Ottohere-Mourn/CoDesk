"""Tiny real-model Codex session/resume probe; no Guest or benchmark scoring."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import time

from oscombo.collab.data_to_deck.live_pilot import _start_codex_compat_relay
from oscombo.harness.base import AgentContext
from oscombo.harness.external import CodexHarness


class NoGuest:
    url = "http://127.0.0.1:1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    provider_key_env = "CODESK_PROVIDER_KEY"
    relay_token_env = "CODESK_RUN_RELAY_TOKEN"
    os.environ[provider_key_env] = args.key_file.read_text().strip()
    relay_token = secrets.token_urlsafe(32)
    os.environ[relay_token_env] = relay_token
    relay, base_url = _start_codex_compat_relay(
        root, "https://api.haogpt.net/v1", provider_key_env, relay_token, relay_token_env)
    try:
        actor_spec = {"harness": "codex", "model": "gpt-6-astra", "effort": "medium",
                      "options": {"base_url": base_url, "api_key_env": relay_token_env,
                                  "redact_env_keys": [provider_key_env],
                                  "mcp_python": "/data3/whn/Project2/OSWorld-V2/.venv/bin/python",
                                  "timeout": 120, "request_retries": 2}}
        ctx = AgentContext(name="B", task_id="resume-compat-probe",
                           instruction="Answer READY and stop.", guest=NoGuest(),
                           out=root / "actor_runs", max_steps=2, spec=actor_spec, t0=time.time())
        harness = CodexHarness(actor_spec)
        harness.prepare(ctx)
        harness.prompt = lambda _ctx: "Reply with READY. Do not call any tool."
        first = harness.run(ctx)
        second = harness.resume_after_external_update(ctx, timeout=120) if first.status == "done" else None
        events = [json.loads(s) for s in (harness.dir / "stdout.log").read_text().splitlines()]
        turns = [x for x in events if x.get("type") == "turn.completed"]
        thread_ids = [x.get("thread_id") for x in events if x.get("type") == "thread.started"]
        result = {"first_status": first.status, "resume_status": second.status if second else None,
                  "turns_completed": len(turns), "thread_ids": thread_ids,
                  "same_private_thread": len(thread_ids) >= 2 and len(set(thread_ids)) == 1,
                  "desktop_calls": len((harness.dir / "actions.jsonl").read_text().splitlines())
                  if (harness.dir / "actions.jsonl").exists() else 0,
                  "scope": "Codex CLI resume compatibility only; no GUI Guest or task score"}
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    finally:
        relay.terminate()
        try:
            relay.wait(timeout=10)
        except Exception:
            relay.kill()
            relay.wait(timeout=10)
        os.environ.pop(provider_key_env, None)
        os.environ.pop(relay_token_env, None)


if __name__ == "__main__":
    main()

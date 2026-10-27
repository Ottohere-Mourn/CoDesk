"""Run one Lite model episode with a private coordinator/relay credential.

Caller must source env.local.sh. The key is never put on argv, in the repo,
in Actor env, or in logs. `live_pilot` creates a per-run loopback relay.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from oscombo.collab.data_to_deck.live_pilot import main as pilot_main


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--condition", required=True,
                        choices=("collaborative_shared", "collaborative_isolated"))
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--diagnostic-step-limit", type=int)
    args = parser.parse_args()
    os.environ["CODESK_PROVIDER_KEY"] = args.key_file.read_text().strip()
    argv = ["--case-lite-v1", "--condition", args.condition,
            "--run-root", str(args.run_root),
            "--provider", "/data3/whn/Project2/OSWorld-V2",
            "--image", os.environ["OSCOMBO_GUEST_IMAGE"],
            "--runtime", os.environ["OSCOMBO_RUNTIME_IMAGE"],
            "--model", "gpt-6-astra", "--base-url", "https://api.haogpt.net/v1",
            "--api-key-env", "CODESK_PROVIDER_KEY",
            "--mcp-python", "/data3/whn/Project2/OSWorld-V2/.venv/bin/python",
            "--effort", "medium", "--model-timeout", "1200",
            "--model-request-retries", "2"]
    if args.diagnostic_step_limit:
        argv.extend(["--diagnostic-step-limit", str(args.diagnostic_step_limit)])
    pilot_main(argv)


if __name__ == "__main__":
    main()

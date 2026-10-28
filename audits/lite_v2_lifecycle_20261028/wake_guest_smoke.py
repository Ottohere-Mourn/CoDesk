"""Diagnostic real-Guest wake test; deliberately yields B's first model turn.

This is never a Shared/Isolated benchmark score. The temporary B instruction
tests the coordinator's suspend/resume path without changing the case source.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from oscombo.collab.data_to_deck.live_pilot import main as pilot_main
from oscombo.collab.data_to_deck_lite_v2 import spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    os.environ["CODESK_PROVIDER_KEY"] = args.key_file.read_text().strip()
    spec.CASE_VERSION = "2.0.0-wake-smoke"
    spec.AGENT_B_INSTRUCTION += (
        "\nDiagnostic wake test: after your first screenshot, if A's saved revision "
        "and result message are not yet available, finish this first model turn "
        "with a short 'waiting for A' reply. Do not edit or publish the slide "
        "before A's handoff. The coordinator will resume this same conversation "
        "when the public handoff arrives; then complete the original task."
    )
    pilot_main([
        "--case-lite-v2", "--handoff-lifecycle",
        "--condition", "collaborative_isolated",
        "--run-root", str(args.run_root),
        "--provider", "/data3/whn/Project2/OSWorld-V2",
        "--image", os.environ["OSCOMBO_GUEST_IMAGE"],
        "--runtime", os.environ["OSCOMBO_RUNTIME_IMAGE"],
        "--model", "gpt-6-astra", "--base-url", "https://api.haogpt.net/v1",
        "--api-key-env", "CODESK_PROVIDER_KEY",
        "--mcp-python", "/data3/whn/Project2/OSWorld-V2/.venv/bin/python",
        "--effort", "medium", "--model-timeout", "1200",
        "--model-request-retries", "2",
    ])


if __name__ == "__main__":
    main()

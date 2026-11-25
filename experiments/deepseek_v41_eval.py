"""Standalone race-awareness telemetry analyzer for multi-agent desktop trajectories."""
from __future__ import annotations

import json
from pathlib import Path
import re

AWARENESS_CMD_PATTERNS = {
    "process_or_peer_probe": re.compile(r"\b(ps\s+aux|pgrep|lsof|fuser|who|xwininfo)\b"),
    "lock_or_handoff_ipc": re.compile(r"(flock|GUI_OWNER|ROLE_[ABCD]|_DONE|_READY|MESSAGE_FROM|\.lock|LOCK)", re.I),
    "polling_wait_loop": re.compile(r"(while\s+.*sleep|for\s+\w+\s+in\s+\$\(seq.*sleep|inotifywait)"),
    "hash_or_mtime_recheck": re.compile(r"(sha256sum|stat\s+-c)"),
}

AWARENESS_TEXT_PATTERNS = re.compile(
    r"(concurrent|another\s+agent|other\s+agent|co-?agent|race\s+condition|stole|clobber|overwrit|lock|mutex|竞争|并发|其他智能体|被改|抢占)",
    re.I,
)


def analyze_race_awareness(cond_dir: Path, roles: tuple[str, ...]) -> dict:
    per_role = {}
    any_ipc = False
    any_poll = False
    any_explicit = False
    for r in roles:
        adir = cond_dir / f"actor_{r}"
        if not adir.is_dir():
            adir = cond_dir / "actors" / r
        cmd_hits = {k: 0 for k in AWARENESS_CMD_PATTERNS}
        samples = []
        af = adir / "actions.jsonl"
        if af.is_file():
            for ln in af.read_text(encoding="utf-8", errors="replace").splitlines():
                if not ln.strip():
                    continue
                row = json.loads(ln)
                if row.get("tool", "").startswith("guest_bash"):
                    cmd = str((row.get("args") or {}).get("command", ""))
                    for pname, rx in AWARENESS_CMD_PATTERNS.items():
                        if rx.search(cmd):
                            cmd_hits[pname] += 1
                            if pname in ("lock_or_handoff_ipc", "polling_wait_loop") and len(samples) < 3:
                                samples.append(cmd[:140])
        explicit_mentions = 0
        for sfn in ("stdout.log", "codex-stdout.jsonl", "codex_events.jsonl"):
            sf = adir / sfn
            if sf.is_file():
                for ln in sf.read_text(encoding="utf-8", errors="replace").splitlines():
                    if '"agent_message"' in ln or '"reasoning"' in ln:
                        if AWARENESS_TEXT_PATTERNS.search(ln):
                            explicit_mentions += 1
                break
        if cmd_hits["lock_or_handoff_ipc"] > 0:
            any_ipc = True
        if cmd_hits["polling_wait_loop"] > 0:
            any_poll = True
        if explicit_mentions > 0:
            any_explicit = True
        per_role[r] = {
            "command_signals": cmd_hits,
            "explicit_race_mentions": explicit_mentions,
            "evidence_samples": samples,
        }
    return {
        "spontaneous_ipc_or_locking": any_ipc,
        "spontaneous_wait_polling": any_poll,
        "explicit_contention_verbalized": any_explicit,
        "autonomous_race_aware": bool(any_ipc or any_explicit or any_poll),
        "roles": per_role,
    }

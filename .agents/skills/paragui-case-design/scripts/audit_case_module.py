#!/usr/bin/env python3
"""Static & time-budget auditor for ParaGUI / CoDesk multi-agent benchmark cases.

Checks Python case modules or directories for known benchmark design anti-patterns:
  1. Prompt bans, peer spoilers, puppet undo commands, or continuous button-hold traps.
  2. Lying lab instruments / hidden runtime samplers (e.g. BackgroundRegimeSampler).
  3. First-write silent locks (official_wire_receipt, amendment_eco_seal).
  4. Wall-clock sleep/busy-wait padding (>45s) & FAST_SELFVAL timing distortion.
  5. Pigeonhole concurrent timeout infeasibility (8.2 * stage_s vs conc_role_timeout_s).
  6. Online-judge oracle leakage in /submit endpoints.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


PROMPT_BANS: tuple[tuple[str, str], ...] = (
    (r"do not modify [^\n]{0,60}/workspace[^\n]{0,40}until", "Explicit upstream write-ban delaying /workspace edits"),
    (r"\b(ctrl\+z|cmd\+z|command\+z)\b", "Puppet undo keystroke choreography in prompt/script"),
    (r"\b(other agent|another agent|peer agent|teammate|colleague)\b", "Peer-agent spoiler in single-role prompt"),
    (r"keep [^\n]{0,80} active on [^\n]{0,30}display=:99[^\n]{0,40}throughout", "Continuous GUI button-holding trap"),
)

HIDDEN_LOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"official_wire_receipt", "Hidden first-submission wire lock (SA/SD trap)"),
    (r"amendment_eco_seal", "Hidden ECO seal lock (SA/SD trap)"),
    (r"CLOSED_LOCAL_VERIFIED", "Deceptive local-verified close status hiding future invalidation"),
    (r"BackgroundRegimeSampler", "Hidden background UI regime sampler during blocking bench calls"),
    (r"verify_stage_regime_purity", "Post-hoc stage regime purity check"),
)


def audit_python_file(path: Path) -> dict:
    src = path.read_text(encoding="utf-8", errors="replace")
    # Strip FORBIDDEN_* deny-list blocks before scanning for banned tokens so self-audit lists do not false-positive
    scan_src = re.sub(r"FORBIDDEN_[A-Z0-9_]+[^=]*=\s*\([^)]*\)", "", src, flags=re.S)
    low = scan_src.lower()
    fails: list[str] = []
    warns: list[str] = []

    for pat, desc in PROMPT_BANS:
        m = re.search(pat, low)
        if m:
            fails.append(f"[PROMPT_TRAP] {desc}: matched '{m.group(0)}'")

    for pat, desc in HIDDEN_LOCK_PATTERNS:
        if re.search(pat, scan_src):
            fails.append(f"[HIDDEN_TRAP] {desc}: matched '{pat}'")

    post_idx = src.find("def do_POST")
    grade_idx = src.find("def grade(")
    if post_idx != -1 and grade_idx != -1 and grade_idx > post_idx:
        post_src = src[post_idx:grade_idx]
        if "stage_purity" in post_src and '"stage_purity"' not in post_src and '"regime_purity"' not in post_src:
            fails.append("[LYING_INSTRUMENT] 'stage_purity' recorded in do_POST without returning purity status to caller")
        if "/submit" in post_src and "422" in post_src and "REJECTED_" in post_src:
            warns.append(
                "[ONLINE_JUDGE_RISK] /submit returns HTTP 422 REJECTED_* diagnostics; verify it only checks basic schema "
                "and locks hand-in rather than leaking cross-role coupling/oracle answers across unlimited retries"
            )
        if "WORKSPACE_HYGIENE_VIOLATION" in post_src:
            warns.append("[ARTIFICIAL_HYGIENE_BAN] Endpoint rejects temporary files in /workspace with HTTP 422")
        if ("check_oracle_canaries=True" in post_src) or ("check_canaries=True" in post_src):
            fails.append("[ORACLE_LEAK] Runtime endpoint checks oracle canaries directly instead of reserving them for offline grade()")

    timers = re.findall(r'os\.environ\.get\(\s*"(PARAGUI_[A-Z0-9_]+)"\s*,\s*"([0-9.]+)"\s*\)', src)
    long_timers = [(k, float(v)) for k, v in timers if not k.endswith("SAMPLES") and float(v) >= 45.0]
    if long_timers and ("time.monotonic() - t0 >=" in src or "time.monotonic() - t0 <" in src):
        fails.append(f"[HORIZON_PADDING] Wall-clock busy-wait/sleep timer loop detected: {long_timers}")
    if long_timers and "fast_selfval" in low:
        fails.append(f"[SELFVAL_DISTORTION] fast_selfval bypasses multi-minute timers {long_timers} during self-validation")

    m_conc = re.search(r'"conc_role_timeout_s"\s*:\s*(\d+)', src)
    if m_conc and long_timers:
        conc_s = float(m_conc.group(1))
        max_stage_s = max(v for _, v in long_timers)
        if "verify_stage_regime_purity" in src:
            min_exclusivity_s = 8.2 * max_stage_s
            if min_exclusivity_s >= conc_s:
                fails.append(
                    f"[PIGEONHOLE_IMPOSSIBLE] 8.2 * {max_stage_s:.0f}s = {min_exclusivity_s:.0f}s ({min_exclusivity_s/60:.1f}m) "
                    f">= conc_role_timeout_s={conc_s:.0f}s ({conc_s/60:.1f}m): mathematically unsolvable in concurrent mode"
                )
            elif min_exclusivity_s > 0.55 * conc_s:
                warns.append(
                    f"[TIGHT_CONC_SLACK] Exclusive bench floor {min_exclusivity_s/60:.1f}m exceeds 55% of concurrent budget {conc_s/60:.1f}m"
                )

    if "PORTAL_HTML" in src and "<canvas" in src:
        real_gui_apps = ("libreoffice", "soffice", "gimp", "freecad", "qgis", "inkscape")
        if not any(app in low for app in real_gui_apps):
            warns.append("[CANVAS_FACADE] Uses custom PORTAL_HTML <canvas> with no detected native desktop GUI app reference")

    if "def self_validate" in src and "careful_conc" not in low and "coord_conc" not in low:
        warns.append("[MISSING_GATE_5] self_validate() found without Gate 5 concurrent feasibility check (careful_conc / coord_conc)")

    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    return {"file": str(path), "status": status, "fails": fails, "warns": warns}


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit ParaGUI/CoDesk benchmark case files for fairness and validity.")
    ap.add_argument("target", type=Path, help="Path to a Python case module or directory of case modules")
    ap.add_argument("--json", action="store_true", help="Emit JSON report")
    args = ap.parse_args()

    target: Path = args.target.resolve()
    if not target.exists():
        print(f"Error: target does not exist: {target}", file=sys.stderr)
        return 2

    py_files = [target] if target.is_file() else sorted(
        p for p in target.rglob("*.py") if p.name not in ("__init__.py", "registry.py")
    )
    results = [audit_python_file(p) for p in py_files]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        fail_files = 0
        warn_files = 0
        for r in results:
            if r["status"] == "FAIL":
                fail_files += 1
            elif r["status"] == "WARN":
                warn_files += 1
            print(f"[{r['status']}] {r['file']}")
            for f in r["fails"]:
                print(f"  ! {f}")
            for w in r["warns"]:
                print(f"  ? {w}")
        print(f"\nSummary: {len(results)} files audited | {fail_files} FAIL | {warn_files} WARN | {len(results) - fail_files - warn_files} PASS")

    return 1 if any(r["status"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

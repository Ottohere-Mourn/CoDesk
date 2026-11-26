#!/usr/bin/env python3
"""Static auditor for explicit peer-aware collaborative ParaGUI / CoDesk cases ($paragui-collab-case-design).

Checks:
  1. Explicit partner/collaboration brief IS present in role prompts (unlike blind co-tenancy).
  2. Zero scripted lock/sleep/poll choreography or puppet undo keystrokes in prompts.
  3. Zero inline synthetic PyQt/GTK/Tk toy GUI app mockups.
  4. Zero step/call caps (max_cua_calls banned), >= 7200s (2h+) anti-deadlock timeouts, default --effort 'high'.
  5. Zero hidden locks, lying samplers, busy-wait padding, post-exit Ctrl+S, asymmetric j_mult,
     Xvfb -ac bypasses, or brittle Qt Designer minimumWidth-only XML parsers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


COLLAB_SIGNAL_RE = re.compile(
    r"\b(partner|teammate|colleague|co-author|collaborat|jointly|working concurrently|working with)\b",
    flags=re.I,
)

SCRIPTED_SYNC_BANS: tuple[tuple[str, str], ...] = (
    (r"do not modify [^\n]{0,60}/workspace[^\n]{0,40}until", "Explicit write-ban delaying /workspace edits"),
    (r"\b(ctrl\+z|cmd\+z|command\+z)\b", "Puppet undo keystroke choreography in prompt"),
    (r"\bflock\b|/tmp/[a-z0-9_.-]*lock", "Scripted file-lock choreography leaked into prompt"),
    (r"poll every \d+\s*s|sleep \d+\s*s until", "Scripted polling/sleep choreography leaked into prompt"),
)

HIDDEN_LOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"official_wire_receipt", "Hidden first-submission wire lock (SA/SD trap)"),
    (r"amendment_eco_seal", "Hidden ECO seal lock (SA/SD trap)"),
    (r"CLOSED_LOCAL_VERIFIED", "Deceptive local-verified close status"),
    (r"BackgroundRegimeSampler", "Hidden background UI regime sampler"),
    (r"verify_stage_regime_purity", "Post-hoc stage regime purity check"),
)


def _extract_prompt_section(src: str) -> str:
    chunks: list[str] = []
    for m in re.finditer(r"(TICKET_[AB]\s*=\s*\([\s\S]*?\)\n|def build_tickets_by_role[\s\S]*?return\s*\{[^}]*\})", src):
        chunks.append(m.group(0))
    return "\n".join(chunks)


def audit_python_file(path: Path) -> dict:
    src = path.read_text(encoding="utf-8", errors="replace")
    scan_src = re.sub(r"FORBIDDEN_[A-Z0-9_]+[^=]*=\s*\([^)]*\)", "", src, flags=re.S)
    no_comment_src = "\n".join(ln for ln in scan_src.splitlines() if not ln.lstrip().startswith("#"))
    allow_synth_app = bool(re.search(r"ALLOW_SYNTHETIC_TARGET_APP\s*=\s*True", src))
    allow_custom_layout = bool(re.search(r"ALLOW_CUSTOM_WINDOW_LAYOUT\s*=\s*True", src))
    is_case_file = ("def build_tickets_by_role" in src) or ("TICKET_A" in src and "TICKET_B" in src)
    fails: list[str] = []
    warns: list[str] = []

    # 1. Explicit collaboration brief check + anti-choreography check on prompts
    prompt_sec = _extract_prompt_section(no_comment_src)
    if is_case_file:
        if not COLLAB_SIGNAL_RE.search(prompt_sec):
            fails.append(
                "[MISSING_COLLAB_BRIEF] Collaborative case prompts must explicitly inform each agent about its partner role and shared objective"
            )
        for pat, desc in SCRIPTED_SYNC_BANS:
            m = re.search(pat, prompt_sec, flags=re.I)
            if m:
                fails.append(f"[SCRIPTED_SYNC_LEAK] {desc}: matched '{m.group(0)}'")

    # 2. Hidden locks, busy-wait padding & asymmetric multipliers
    for pat, desc in HIDDEN_LOCK_PATTERNS:
        if re.search(pat, scan_src):
            fails.append(f"[HIDDEN_TRAP] {desc}: matched '{pat}'")

    timers = re.findall(r'os\.environ\.get\(\s*"(PARAGUI_[A-Z0-9_]+)"\s*,\s*"([0-9.]+)"\s*\)', src)
    long_timers = [(k, float(v)) for k, v in timers if not k.endswith("SAMPLES") and float(v) >= 45.0]
    if long_timers and ("time.monotonic() - t0 >=" in src or "time.monotonic() - t0 <" in src):
        fails.append(f"[HORIZON_PADDING] Wall-clock busy-wait/sleep timer loop detected: {long_timers}")

    if re.search(r"\bj_mult\s*=\s*\(\s*0\.75", src):
        fails.append("[ASYMMETRIC_SCORE_MULTIPLIER] Asymmetric shared-only j_mult=0.75 distorts dual_desktop vs shared_desktop comparison")

    for mp in re.finditer(r"pass_threshold\s*(?::\s*float\s*)?=\s*(0\.\d+)", no_comment_src):
        if float(mp.group(1)) < 0.999:
            fails.append(
                f"[LAX_PASS_THRESHOLD] pass_threshold={mp.group(1)} < 1.0 allows failed checkpoints to pass; "
                "unify binary pass_a/pass_b/joint_pass to strict pass_threshold=1.0 (zero failed checks)"
            )

    if 'pnm == "minimumWidth"' in src and "minimumSize" not in src and "loadUi" not in src:
        fails.append("[BRITTLE_UI_XML_PARSER] Parsing .ui 'minimumWidth' without 'minimumSize'/uic.loadUi breaks real Qt5 Designer saves")

    # 3. Real software vs inline synthetic PyQt/GTK mockups
    if not allow_synth_app:
        synth_var = re.findall(r"^([A-Z0-9_]+_(?:QT|GTK|TK|WX)_SOURCE)\s*=", src, flags=re.M)
        if synth_var or "stage_private_studio_script(" in src:
            fails.append(
                f"[SYNTHETIC_TOY_APP] Inline synthetic GUI mockup detected ({synth_var or ['stage_private_studio_script']}); launch real desktop software instead"
            )

    # 4. Runtime protocol: zero step caps, >= 7200s (2h+) timeouts, fixed --effort 'high'
    m_cua = re.search(r'"max_cua_calls"\s*:\s*([1-9]\d*)', src)
    if m_cua:
        fails.append(
            f"[STEP_LIMIT_BANNED] max_cua_calls={m_cua.group(1)} imposes an artificial step cap; set max_cua_calls to None (unlimited)"
        )
    if re.search(r"(loop-safety ceiling|safety ceiling)\s*:\s*\{", src, flags=re.I):
        fails.append("[PROMPT_STEP_LIMIT] Wrapper prompt injects a call/step ceiling notice; remove all step-limit text")

    for tkey in ("conc_role_timeout_s", "iso_role_timeout_s", "dual_role_timeout_s", "shared_role_timeout_s"):
        for mt in re.finditer(rf'"{tkey}"\s*:\s*(\d+)', src):
            if int(mt.group(1)) < 7200:
                fails.append(f"[LOW_TIMEOUT_BUDGET] {tkey}={mt.group(1)}s < 7200s (2h); set anti-deadlock timeout to >= 7200s")

    if re.search(r"time budget\s*:\s*\{", src, flags=re.I):
        warns.append("[PROMPT_TIME_PRESSURE] Wrapper prompt injects 'time budget: ...s' countdown text; keep >= 7200s timeout silent")

    m_eff = re.search(r'add_argument\(\s*"--effort"[^)]*default\s*=\s*"([^"]+)"', src)
    if m_eff and m_eff.group(1) != "high":
        fails.append(f"[NON_HIGH_DEFAULT_EFFORT] --effort defaults to '{m_eff.group(1)}'; standardize default reasoning effort to 'high'")

    # 5. Harness & window layout hygiene
    stop_idx = src.find("def stop_and_grade")
    if stop_idx != -1:
        stop_blk = src[stop_idx:stop_idx + 2500].lower()
        if "ctrl+s" in stop_blk and "xdotool" in stop_blk:
            fails.append("[POST_EXIT_CTRL_S] stop_and_grade() injects 'xdotool ... ctrl+s' after agents exit; grade read-only instead")

    if "Xvfb :99" in src and " -ac " in src and "container:" in src:
        warns.append("[XVFB_NO_AUTH_BYPASS] Xvfb launched with -ac while sharing container network; use 'Xvfb :99 -auth /tmp/x99.auth' + separate CLI UID")

    if ("def grade(" in src) and re.search(r"\b(qwen-cua-driver|cua-driver|agent-desktop)\b", src[src.find("def grade("):]):
        fails.append("[DRIVER_COUPLED_GRADER] grade() hardcodes a specific CUA driver binary")

    if "def self_validate" in src and "solo" not in no_comment_src.lower():
        warns.append("[MISSING_SOLO_INSUFFICIENCY_GATE] self_validate() should verify Gate 2 (solo_a and solo_b cannot pass joint_pass alone)")

    if not allow_custom_layout:
        solve_idx = src.find("def solve_role(")
        boot_src = src[:solve_idx] if solve_idx != -1 else src
        for spat, sdesc in (
            (r"--window-position=\d+,\d+", "Hardcoded --window-position at browser launch"),
            (r"\bself\.setGeometry\(\s*\d+\s*,\s*\d+\s*,", "Hardcoded main-window self.setGeometry(x, y, w, h)"),
            (r"wmctrl[^\n]*-e\s+0,9[4-9]\d,", "Rigid right-half split-screen wmctrl tiling"),
        ):
            sm = re.search(spat, boot_src)
            if sm:
                warns.append(f"[RIGID_SPLIT_SCREEN] {sdesc} ('{sm.group(0)}'); prefer natural WM placement")

    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    return {"file": str(path), "status": status, "fails": fails, "warns": warns}


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit explicit collaborative ParaGUI/CoDesk benchmark cases.")
    ap.add_argument("target", type=Path, help="Path to a Python case module, runner, or directory")
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
        fail_files = sum(1 for r in results if r["status"] == "FAIL")
        warn_files = sum(1 for r in results if r["status"] == "WARN")
        for r in results:
            print(f"[{r['status']}] {r['file']}")
            for f in r["fails"]:
                print(f"  ! {f}")
            for w in r["warns"]:
                print(f"  ? {w}")
        print(f"\nSummary: {len(results)} files audited | {fail_files} FAIL | {warn_files} WARN | {len(results) - fail_files - warn_files} PASS")

    return 1 if any(r["status"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

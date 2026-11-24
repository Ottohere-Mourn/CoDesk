#!/usr/bin/env python3
"""Static authenticity, harness & time-budget auditor for ParaGUI / CoDesk benchmark cases.

Audits Python case modules and runner scripts for known anti-patterns:
  1. Inline synthetic PyQt/GTK/Tk toy GUI app mockups impersonating real software.
  2. Prompt write-bans, peer spoilers, puppet undo commands, or continuous button-hold traps.
  3. Lying lab instruments / hidden runtime samplers (e.g. BackgroundRegimeSampler).
  4. First-write silent locks (official_wire_receipt, amendment_eco_seal).
  5. Wall-clock sleep/busy-wait padding (>45s) & FAST_SELFVAL timing distortion.
  6. Pigeonhole concurrent timeout infeasibility (8.2 * stage_s vs conc_role_timeout_s).
  7. Online-judge oracle leakage in /submit endpoints.
  8. Harness bugs: low max_cua_calls guillotines, guest_bash X11/AT-SPI driver bypass,
     cross-container daemon PID split without --pid, post-exit Ctrl+S injection,
     driver-hardcoded graders, and rigid boot-time split-screen tiling.
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
    (r"\b(other agent|another agent|peer agent|concurrent agent|teammate|colleague)\b", "Peer-agent spoiler in single-role prompt"),
    (r"keep [^\n]{0,80} active on [^\n]{0,30}display=:99[^\n]{0,40}throughout", "Continuous GUI button-holding trap"),
)

HIDDEN_LOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"official_wire_receipt", "Hidden first-submission wire lock (SA/SD trap)"),
    (r"amendment_eco_seal", "Hidden ECO seal lock (SA/SD trap)"),
    (r"CLOSED_LOCAL_VERIFIED", "Deceptive local-verified close status hiding future invalidation"),
    (r"BackgroundRegimeSampler", "Hidden background UI regime sampler during blocking bench calls"),
    (r"verify_stage_regime_purity", "Post-hoc stage regime purity check"),
)

REAL_DESKTOP_APPS: tuple[str, ...] = (
    "libreoffice", "soffice", "gimp", "freecad", "qgis", "inkscape", "blender",
    "chrome", "chromium", "firefox", "code", "wps", "shotcut", "kdenlive", "reaper",
    "kicad", "zotero", "thunderbird", "solvespace", "musescore", "sqlitebrowser",
)


def audit_python_file(path: Path) -> dict:
    src = path.read_text(encoding="utf-8", errors="replace")
    scan_src = re.sub(r"FORBIDDEN_[A-Z0-9_]+[^=]*=\s*\([^)]*\)", "", src, flags=re.S)
    no_comment_src = "\n".join(ln for ln in scan_src.splitlines() if not ln.lstrip().startswith("#"))
    allow_coord = bool(re.search(r"ALLOW_EXPLICIT_COORDINATION\s*=\s*True", src))
    allow_custom_layout = bool(re.search(r"ALLOW_CUSTOM_WINDOW_LAYOUT\s*=\s*True", src))
    allow_synth_app = bool(re.search(r"ALLOW_SYNTHETIC_TARGET_APP\s*=\s*True", src))
    allow_cli_x11 = bool(re.search(r"ALLOW_CLI_X11_BYPASS\s*=\s*True", src))
    low = no_comment_src.lower()
    fails: list[str] = []
    warns: list[str] = []

    # 1. Prompt & protocol anti-patterns
    for pat, desc in PROMPT_BANS:
        if allow_coord and "Peer-agent spoiler" in desc:
            continue
        m = re.search(pat, low)
        if m:
            fails.append(f"[PROMPT_TRAP] {desc}: matched '{m.group(0)}'")

    # 2. Hidden locks & lying samplers
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

    # 3. Busy-wait / sleep padding & FAST_SELFVAL distortion
    timers = re.findall(r'os\.environ\.get\(\s*"(PARAGUI_[A-Z0-9_]+)"\s*,\s*"([0-9.]+)"\s*\)', src)
    long_timers = [(k, float(v)) for k, v in timers if not k.endswith("SAMPLES") and float(v) >= 45.0]
    if long_timers and ("time.monotonic() - t0 >=" in src or "time.monotonic() - t0 <" in src):
        fails.append(f"[HORIZON_PADDING] Wall-clock busy-wait/sleep timer loop detected: {long_timers}")
    if long_timers and "fast_selfval" in low:
        fails.append(f"[SELFVAL_DISTORTION] fast_selfval bypasses multi-minute timers {long_timers} during self-validation")

    # 4. Pigeonhole concurrent timeout check
    m_conc = re.search(r'"conc_role_timeout_s"\s*:\s*(\d+)', src)
    if m_conc and long_timers and "verify_stage_regime_purity" in src:
        conc_s = float(m_conc.group(1))
        max_stage_s = max(v for _, v in long_timers)
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

    # 5. Inline synthetic PyQt/GTK/Tk toy GUI app mockups & static <canvas> facades
    if not allow_synth_app:
        synth_var = re.findall(r"^([A-Z0-9_]+_(?:QT|GTK|TK|WX)_SOURCE)\s*=", src, flags=re.M)
        if synth_var or "stage_private_studio_script(" in src:
            fails.append(
                f"[SYNTHETIC_TOY_APP] Inline synthetic GUI mockup detected ({synth_var or ['stage_private_studio_script']}); "
                "launch real open-source desktop software instead (or set ALLOW_SYNTHETIC_TARGET_APP = True only for explicit unknown-utility reverse-engineering)"
            )
    if "PORTAL_HTML" in src and "<canvas" in src:
        if not any(app in low for app in REAL_DESKTOP_APPS):
            warns.append("[CANVAS_FACADE] Uses custom PORTAL_HTML <canvas> with no detected real desktop/browser app reference")

    # 6. Artificial low max_cua_calls guillotine
    m_cua = re.search(r'"max_cua_calls"\s*:\s*(\d+)', src)
    if m_cua and int(m_cua.group(1)) < 90:
        fails.append(
            f"[LOW_CUA_CALL_CAP] max_cua_calls={m_cua.group(1)} < 90 artificially cuts off the GUI driver mid-task; "
            "remove low call caps or use a generous loop-safety ceiling (>= 120)"
        )

    # 7. Harness checks: post-exit Ctrl+S, guest_bash X11 leak, cross-container PID split, driver-coupled grader
    stop_idx = src.find("def stop_and_grade")
    if stop_idx != -1:
        stop_blk = src[stop_idx:stop_idx + 2500].lower()
        if "ctrl+s" in stop_blk and "xdotool" in stop_blk:
            fails.append("[POST_EXIT_CTRL_S] stop_and_grade() injects 'xdotool ... ctrl+s' after agents exit; grade read-only instead")

    if not allow_cli_x11 and "def exec_role" in src and ("gui_env_args" in src or "/tmp/.x11-unix" in low):
        warns.append(
            "[GUEST_BASH_GUI_BYPASS] Role CLI container mounts X11/AT-SPI sockets or DISPLAY=:99, allowing CLI xdotool/xclip "
            "to bypass the tested GUI driver during driver ablations"
        )

    if "--network" in src and "container:" in src and "role_containers" in src and not re.search(r'"--pid"\s*,|--pid[=\s]+container:', src):
        warns.append(
            "[CROSS_CONTAINER_PID_SPLIT] Role container shares --network container:<desk> without --pid; "
            "ensure tasks never ask CLI agents to restart daemons hidden in desk_container's PID namespace"
        )

    if ("def grade(" in src or "def evaluate_recreated_gui_app(" in src):
        g_start = src.find("def evaluate_recreated_gui_app(")
        if g_start == -1:
            g_start = src.find("def grade(")
        if g_start != -1 and re.search(r"\b(qwen-cua-driver|cua-driver|agent-desktop)\b", src[g_start:]):
            fails.append("[DRIVER_COUPLED_GRADER] Grading/evaluation function hardcodes a specific CUA driver binary")

    if "def self_validate" in src and "careful_conc" not in low and "coord_conc" not in low:
        warns.append("[MISSING_GATE_5] self_validate() found without Gate 5 concurrent feasibility check (careful_conc / coord_conc)")

    # 8. Rigid boot-time split-screen window pre-tiling
    if not allow_custom_layout:
        solve_idx = src.find("def solve_role(")
        boot_src = src[:solve_idx] if solve_idx != -1 else src
        split_pats = (
            (r"--window-position=\d+,\d+", "Hardcoded --window-position at browser launch"),
            (r"\bself\.setGeometry\(\s*\d+\s*,\s*\d+\s*,", "Hardcoded main-window self.setGeometry(x, y, w, h)"),
            (r"\bwindow_pos\s*=\s*\(\s*\d+", "Explicit window_pos=(x, y) passed at desktop boot"),
            (r"wmctrl[^\n]*-e\s+0,9[4-9]\d,", "Rigid right-half split-screen wmctrl -e 0,955..999 tiling"),
        )
        for spat, sdesc in split_pats:
            sm = re.search(spat, boot_src)
            if sm:
                warns.append(
                    f"[RIGID_SPLIT_SCREEN] {sdesc} ('{sm.group(0)}'); use natural WM placement (resize only) "
                    "or set ALLOW_CUSTOM_WINDOW_LAYOUT = True if required by a special case"
                )

    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    return {"file": str(path), "status": status, "fails": fails, "warns": warns}


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit ParaGUI/CoDesk benchmark case files for authenticity, fairness, and validity.")
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

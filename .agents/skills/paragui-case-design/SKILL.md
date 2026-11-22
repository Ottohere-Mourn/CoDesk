---
name: paragui-case-design
description: "Design, refactor, or audit multi-agent shared-desktop (GUI + CLI) benchmark cases in ParaGUI/CoDesk. Use when authoring new contention tasks, reviewing existing case suites, or fixing flawed conflict, timing, or grading mechanics. Skip for ordinary single-agent desktop automation unrelated to benchmark construction."
---

# ParaGUI / CoDesk Benchmark Case Design & Audit

Build and review multi-agent (or human-agent) shared-workstation benchmark cases where failures stem from **real OS/application state contention** rather than misleading prompts, lying tools, or unsolvable timeouts.

## Core Design Contract: The "Exam" Architecture

Every benchmark case must follow an **Exam-Style Self-Check + Blind Final Grading** architecture:

1. **Full Self-Checking Inside the Environment**: Give each agent real software, compilers, CLI utilities, and GUI tools so a careful agent can inspect files, verify UI state, re-read exports, and run its own sanity checks before finishing.
2. **Blind Offline Grading (`grade()`)**: Keep true target values (oracle canaries), cross-role physical/business coupling checks, and final consistency assertions strictly inside post-episode `grade()`. Never expose `grade()` as an interactive `HTTP 422` online judge that tells agents exact cross-role discrepancies across unlimited retries.
3. **One-Shot Hand-In (No Post-Grading Revisions)**: Grade the final `/workspace` and live service state after agents finish their turns. If the workflow includes an explicit `/submit` endpoint, restrict it to basic schema/existence validation plus **one-shot hand-in locking** (recording the role's final signoff without revealing oracle errors or allowing score-farming retries).
4. **Honest In-Environment Tools**: Any local tool, compiler, database, or lab service exposed to agents during the episode must behave truthfully. Never return `passed: true` or `qualified: true` from an in-environment test tool when environmental drift or lock contention invalidated the run.

## What Every Case MUST Do

### 1. Ground Contention in Genuine `GUI + CLI` Shared Primitives
Keep every case **GUI-driver agnostic** so the runner harness can swap different GUI drivers (`qwen-cua`, `cua-driver`, `agent-desktop`, `weavebench-cua`, `browser-use-cdp`, or raw `xdotool` MCP) for ablation studies:

- **Decouple Case Assets from Driver Tool Schemas**: Never hardcode MCP tool names (such as `desktop.click` or `click_and_type`) inside `task.md` or grading logic. Configure the desktop container with standard OS accessibility/automation surfaces (X11/WindowServer, `AT-SPI2` bus, and optional browser CDP when applicable) so both coordinate-based CUA drivers and semantic/accessibility drivers can operate the exact same case.
- **Support Both Driver-Sensitive and Driver-Invariant Contention**: Across a suite, you may include focus/pointer collisions that semantic background drivers (e.g., AT-SPI `set_value`) can mitigate during driver ablations, while ensuring long-horizon hybrid (`GUI + CLI`) cases also anchor in deeper OS/session/process conflicts that pure CLI or single-action atomicity cannot trivially bypass:
  - **In-Memory GUI Dirty Buffer vs. Disk CLI Split-Brain**: One role interacts with a live open desktop app (`LibreOffice`, `GIMP`, `FreeCAD`, `Inkscape`, `QGIS`) holding an in-memory document (e.g., to resolve embedded comments, visual layers, or live formatting) and saves, while the other role modifies the same file on disk via CLI (`openpyxl`, `python-docx`, Python scripts), causing a naive GUI `Ctrl+S` to overwrite disk changes.
  - **Cross-Step System Clipboard (`CLIPBOARD` / `NSPasteboard`)**: Single-slot session register shared across GUI `Ctrl+C/V`, CLI `xclip`/`pbcopy`, and browser copy buttons (`write -> switch context/verify -> paste`).
  - **Single-Instance Process, Profile & Port Locks**: Real desktop singletons such as Chrome `--user-data-dir` `SingletonLock`, LibreOffice `.~lock` / single `soffice.bin` instance blocking `--headless --convert-to`, `.git/index.lock`, or shared local daemon ports.
  - **Shared Authenticated Browser Session & `~/Downloads`**: Business data or actions gated behind an already-signed-in browser session (`HttpOnly` SSO cookies, stateful server-side filter/currency/role context, shared active tab/viewport, or default same-name export paths like `~/Downloads/report.csv`).
  - **Modal Grab, Continuous Drag & Workspace Focus Preemption**: Continuous drag trajectories, native modal dialogs/menus grabbing pointer/keyboard focus, or GUI window launches stealing active focus/Spaces.
  - **Bidirectional Shared Artifact & Coupled Envelope**: Monolithic packages (`.FCStd`, multi-sheet `.xlsx`, `.gpkg`, `.kicad_pcb`, Git repo + live daemon telemetry) where both roles edit subsystems coupled by a joint physical/financial budget, and **`v0` visibly requires work from both roles**.

### 2. Build Authentic Long-Horizon Depth (15-35 Minutes)
- **Make Base Tasks Genuinely Hard (Never Simplify for `100%` Sequential Model Pass)**: Do NOT spoon-feed formulas, exact CLI scripts, or step-by-step recipes in `task.md` just to make frontier LLMs pass `100%` sequentially. Agents must discover rules and edge cases from messy, realistic multi-file workspaces, multi-sheet workbooks, specs, databases, and live desktop/web UIs.
- **Target Non-Saturated Sequential Difficulty (`Pass_seq > Pass_conc`, NOT `100% vs 0%`)**: Even in single-agent or sequential mode (`seq_ab` / `seq_ba`), frontier models should face real domain, GUI, and self-verification difficulty (e.g., `30%-75%` sequential pass rate rather than `100%` saturation). If a frontier model effortlessly scores `100%` sequentially, the base task is too easy or over-prompted—increase intrinsic task complexity rather than adding artificial concurrency locks.
- **Derive Horizon from Multi-Stage Problem Solving**: Build 15-35 minute tasks from cross-referencing multiple real artifacts, cascading updates across code/CAD/spreadsheets/UI, and writing self-verification checks.
- Keep individual tool/solver calls at their **natural execution speed** (seconds, not padded 5-minute sleeps).
- Provide **at least `1.8x-2.0x` wall-clock slack** in `conc_role_timeout_s` relative to the time needed for two careful agents to complete and serialize around shared bottlenecks.

### 3. Write Natural, Self-Contained Role Prompts
- Write each `task.md` as a realistic single-role engineering work order describing only that role's deliverables, constraints, and acceptance criteria.
- Do not mention a peer agent (unless explicitly benchmarking explicit coordination), and never inject unnatural keystroke choreography.
- Keep high model scores meaningful: if careful agents detect anomalous UI/file changes, re-read live state, and recover cleanly (`30%-60%` pass), preserve that signal—discrimination between careless and careful agents is the goal.

### 4. Enforce Non-YOLO Isolation & Secret Hygiene
- Run all desktop and agent containers without `--yolo` or host-root bypasses (`--security-opt no-new-privileges`, scoped workspace mounts).
- Never print or copy raw API keys from private credential files into logs, containers, or reports.

## What Every Case MUST Avoid (Hard Bans)

Read [references/anti-patterns-and-case-archetypes.md](references/anti-patterns-and-case-archetypes.md) when reviewing existing suites or designing new conflict mechanics. Never introduce any of the following five failure patterns:

1. **Unannounced Upstream Waiting + Locked Downstream Exit (`SA` / `SD` Trap)**
   - **Ban**: Presenting a self-consistent fake `v0` baseline with zero pending/dirty indicators so Role A finishes and closes early, while Role B mutates `/workspace` to `v1` 10-15 minutes later.
   - **Ban**: Prompt write-bans (`Do NOT modify /workspace until all 16 stages...`), asymmetric dummy step counts (`6 vs 16` disconnected algebra stages), or silent first-write locks (`official_wire_receipt`, `amendment_eco_seal`, fake `CLOSED_LOCAL_VERIFIED`).
2. **Pigeonhole Timeout Deadlocks + Lying Samplers (`FC v_final` Trap)**
   - **Ban**: Requiring two roles to hold mutually exclusive states on a single global toggle across multi-minute windows whose combined minimum time exceeds or crowds `conc_role_timeout_s` (e.g., `8.2 * stage_s >= conc_role_timeout_s`).
   - **Ban**: Recording hidden `BackgroundRegimeSampler` / `stage_purity` scores in the background while `/api/bench` returns `passed: true` and `grade()` fails both roles post-hoc.
3. **Busy-Wait / `sleep` Horizon Inflation & `FAST_SELFVAL` Masking**
   - **Ban**: `while time.monotonic() - t0 < 290.0` dummy loops or `time.sleep(...)` padding inside endpoints to fake 30-minute runs, especially when `FAST_SELFVAL=1` shrinks those loops to `0.25s` during validation.
4. **Online-Judge Oracle Leakage**
   - **Ban**: Turning `/submit` or `/bench` into an infinite-retry oracle grader that returns `HTTP 422` with exact cross-role coupling answers or canary values.
5. **Puppet Prompts, Canvas Facades & Toy Micro-Probes (`MECH` / Facade Trap)**
   - **Ban**: Commanding unnatural destructive actions in prompts (e.g., "type X, press `Ctrl+Z` twice, then retype Y").
   - **Ban**: Replacing real desktop software (`LibreOffice`, `GIMP`, `FreeCAD`, real web apps) with a static custom `<canvas>` image and two HTML buttons while doing all real edits purely in CLI.
   - **Ban**: 4-row/4-line toy files solvable in 5 clicks when claiming a realistic long-horizon workflow.

## Mandatory 5-Gate Well-Posedness Check vs. Model Difficulty Calibration

Distinguish strictly between **deterministic problem-validity checks** (run with a privileged ground-truth reference script solely to prove the exam question has no broken math or hidden ordering trap) and **real LLM evaluation** (where models are expected to fail hard tasks even sequentially):

### A. Deterministic Ground-Truth Well-Posedness Gates (Author's Answer-Key Check, Zero LLM Calls)
Every case must include a deterministic ground-truth verification script proving the problem itself is mathematically well-posed across all 5 gates:

1. **`Gate 1 — pristine_fail`**: Grading the untouched `build_pristine()` workspace returns `joint_pass == False` (and `v0` visibly lacks required deliverables for both roles).
2. **`Gate 2 — gt_seq_ab_exists`**: A ground-truth solution exists when `Role A` completes before `Role B` (`joint_pass == True`).
3. **`Gate 3 — gt_seq_ba_exists`**: A ground-truth solution also exists when `Role B` completes before `Role A` (`joint_pass == True`), proving the task specification itself contains no unannounced upstream->downstream ordering trap.
4. **`Gate 4 — gt_naive_race_corrupts`**: Overlapping unguarded actions on the shared resource trigger a real state collision (`joint_pass == False`), proving the contention surface is active.
5. **`Gate 5 — gt_careful_conc_feasible`**: Under **real tool timing**, a valid concurrent execution schedule exists and achieves `joint_pass == True` within `<= 55%` of `conc_role_timeout_s`, proving the clock does not create a pigeonhole deadlock.

### B. Real LLM Evaluation Expectations (Do NOT Require `100%` Sequential LLM Pass!)
- **Never treat LLM `seq_ab` / `seq_ba == 100%` as a gate**: Real LLMs SHOULD struggle on hard single-agent GUI+CLI reasoning, multi-document reconciliation, and self-testing. Requiring LLMs to pass `100%` sequentially forces authors to dumb down tasks into spoon-fed checklists.
- **Evaluate Relative Contention Gap (`Pass_seq > Pass_conc`)**: A strong benchmark suite exhibits non-saturated sequential model accuracy (e.g., `35%-75%`) alongside a clear, diagnosable drop under concurrency (`Pass_conc < Pass_seq`) driven by genuine shared-resource collisions.

Before launching model runs, execute the bundled static & time-budget auditor on the task module or directory:

```bash
python3 .agents/skills/paragui-case-design/scripts/audit_case_module.py <path/to/task_file_or_dir>
```

Resolve every `FAIL` finding and review any `WARN` findings before spending GPU/CPU evaluation budget.

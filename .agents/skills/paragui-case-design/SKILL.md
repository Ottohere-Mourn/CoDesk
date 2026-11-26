---
name: paragui-case-design
description: "Design, refactor, or audit multi-agent shared-desktop (GUI + CLI) benchmark cases in ParaGUI/CoDesk. Use when authoring new contention tasks, reviewing existing case suites, or fixing flawed conflict, timing, harness, or grading mechanics. Skip for ordinary single-agent desktop automation unrelated to benchmark construction."
---

# ParaGUI / CoDesk Benchmark Case Design & Audit

Build and review multi-agent (or human-agent) shared-workstation benchmark cases where **single-case authenticity comes first** and contention arises naturally from **real desktop/web software and real OS/session state**, without misleading prompts, toy app mockups, broken harness isolation, lying tools, or unsolvable timeouts.

## Core Design Contract: Authenticity + The "Exam" Architecture

Every benchmark case must satisfy both **Single-Case Authenticity** and **Exam-Style Self-Check + Blind Final Grading**:

1. **Single-Case Authenticity First**: Viewed on its own, each role's task must be a realistic, complete professional workflow running on **real software**. Sharing a workstation between the two actors must also have a coherent real-world context.
2. **Full Self-Checking Inside the Environment**: Keep both the GUI driver and workstation CLI (`guest_bash`) enabled so a careful agent can inspect windows, write calculation/test scripts, re-read files, and verify its own work before finishing.
3. **Blind Offline Grading (`grade()`)**: Keep true target values (oracle canaries), reference test manifests, visual assertions, and cross-role coupling checks strictly inside post-episode `grade()`. Never expose `grade()` as an interactive `HTTP 422` online judge across unlimited retries, and support fine-grained **continuous partial-credit scoring (`[0.0, 1.0]`)** alongside **strict zero-error binary `joint_pass` (`pass_threshold = 1.0`)**:
   - **Strict `1.0` Binary Pass Standard**: `pass_a`, `pass_b`, and `joint_pass` MUST require **100% of subchecks to pass (`pass_threshold = 1.0`, `len(errors) == 0`)**. Never set `pass_threshold = 0.78 / 0.85 / 0.88 / 0.90` to mask failed functional checkpoints as `PASS`; put any numerical or pixel-similarity tolerance inside each individual subcheck, and reserve partial credit strictly for `score_a / score_b / mean_score`.
   - **Audited, Observable Oracles Only**: Every rule, sentinel exclusion, penalty term, or custom property tested in `grade()` MUST be either visibly rendered in the live GUI or documented in workspace specs/exhibits—never hide oracle terms in unrendered XHR JSON fields, unreferenced object metadata, single-file static string greps that penalize clean modularization (`app.js`), or private-JSON vs. shared-artifact catch-22s when a peer legitimately adjusts a shared parameter later.
4. **One-Shot Hand-In & Read-Only Post-Episode Grading**: Grade the final workspace(s) and live service state read-only after agents finish. Never mutate UI/files (such as injecting `Ctrl+S`) inside `stop_and_grade()`. If an explicit `/submit` endpoint is used, restrict it to basic schema checks plus one-shot hand-in locking.
5. **Honest In-Environment Tools**: Any local tool, compiler, database, or service exposed to agents during the episode must behave truthfully—never return `passed: true` when state drift or contention invalidated the run.

## What Every Case MUST Do

### 1. Use Authentic Real Software (No Inline Toy GUI Mockups)
- **Run Real Desktop & Web Applications**: Whenever a workflow involves spreadsheets/documents, raster/vector graphics, 3D/CAD, audio/video editing, music notation, GIS, EDA, databases, IDEs, mail/calendars, or web portals, launch **real open-source/production applications** (e.g., `LibreOffice`, `GIMP`, `Blender`, `FreeCAD`, `Inkscape`, `QGIS`, `MuseScore`, `Shotcut`/`Kdenlive`, `KiCad`, `DB Browser`, `Thunderbird`, `VS Code`, real multi-route web apps, or pre-compiled real open-source binaries).
- **Keep Contention Exploration Open-Ended**: Explore diverse OS, window-manager, browser-session, singleton-process, clipboard, input/focus, live-service, and shared-artifact contention organically within real software—do not force every case into a rigid formula template.

### 2. Ensure Single-Role Workflow Realism & Shared-Workstation Plausibility
- **Realistic Goal-Driven Prompts (No Spoon-Fed Checklists)**: Write each `task.md` like an authentic work order specifying business/engineering objectives, deliverable paths, and acceptance criteria. **Never spoon-feed** internal JSON key checklists to scrape from dialogs, hidden submenu paths, hotkey cheat-sheets, or ready-made formulas that the agent should discover from workspace specs, documents, databases, and live UIs.
- **Plausible Co-Tenancy on One Workstation**: Pairing two roles on one shared desktop must make real-world sense—either **collaborators on the same project/lab/engineering/financial workstation** (e.g., M&A QoE + Tax leads, mechanical + EMC engineers, same-ward clinical specialists) or **a foreground user workflow paired with a concurrent background assistant task** on one personal desktop. Never pair unrelated professions that would never share a login session.
- Do not mention a peer agent in `task.md` (unless explicitly benchmarking explicit coordination with `ALLOW_EXPLICIT_COORDINATION = True`).

### 3. Calibrate Non-Saturated Difficulty & Primary Contention Metrics
- **Target Non-Saturated Single-Agent Baselines (`0.40-0.85` score or `35%-75%` pass rate)**: Frontier models should face genuine multi-step domain, GUI, and self-verification difficulty even in `isolated` / `seq` mode (typically `>= 6-10+` minutes of real work). If frontier models finish in `1.5-3` minutes at `0.98-1.00`, the base task is too shallow or over-prompted—deepen the workflow rather than adding concurrency locks.
- **Accuracy Degradation Is Primary; Overhead Inflation Is Auxiliary**:
  - **Primary signal**: Measurable partial-credit or pass-rate drop under concurrency (`Score_shared < Score_isolated` or `Pass_conc < Pass_seq`). Never certify a `1.000 -> 1.000` ceiling-saturated task as a benchmark case merely because token usage rose.
  - **Auxiliary telemetry**: Always log input-token ratio, wall-clock ratio, window-focus flips, and misrouted keystrokes to quantify self-healing overhead alongside accuracy drops.
- Keep tool/solver execution at **natural speed** (seconds, never multi-minute sleeps). Keep `isolated` and `shared` per-role scoring denominators **100% identical**—never apply a `shared`-only global multiplier (`j_mult`) that double-penalizes single-role misses.

### 4. Standardized Evaluation Runtime Protocol & Clean GUI-Driver Isolation
- **Zero Step / Tool-Call Limits (严禁步数上限)**: **Never** impose `max_cua_calls`, `max_steps`, or per-role GUI/CLI tool-call caps in task metadata or MCP bridges, and **never** mention a call/step ceiling in the agent prompt. Let agents take as many GUI and CLI actions as needed to inspect, recover, and verify.
- **Anti-Deadlock Wall-Clock Guard Only (`>= 7200s` / `2h+`)**: Set outer role timeouts (`iso_role_timeout_s`, `conc_role_timeout_s`) to **at least `7200` seconds (`2 hours` or more)** solely to prevent infinite hangs. Never use tight 15-30 minute timeouts (`1080s`-`1800s`) that cut off long-horizon contention recovery, and **do not** inject countdown `time budget: ...s` pressure into the agent's prompt.
- **Fixed Reasoning Effort = `high`**: Standardize `model_reasoning_effort = "high"` (`--effort high`) across all evaluated models (`gpt-6.1-sol`, `gpt-6-astra`, etc.) unless the user explicitly asks for a reasoning-effort ablation. Ensure `models-catalog.json` includes all supported tiers.
- **Neutral Runtime Wrapper Prompt**: Keep the runner's wrapper around `task.md` minimal and neutral—only state factual workspace paths (e.g. `/workspace`) and available MCP servers, with **zero** step limits, countdown timers, artificial prohibitions, or peer-agent hints.
- **Decouple Tasks & Graders from Specific GUI Drivers**: Never hardcode MCP tool names (`desktop.click`, `qwen_cua_driver`, `click_and_type`) in `task.md`, and never hardcode a specific CUA driver binary inside `grade()`. Expose standard OS surfaces (X11/WindowServer, `AT-SPI2` bus, and browser CDP only when CDP itself is part of the tested workflow).
- **Prevent `guest_bash` from Bypassing the Tested GUI Driver**: Keep `guest_bash` scoped to filesystem, compilers, data tools, and service ports—**do not mount raw `:99` `/tmp/.X11-unix` or `AT-SPI` sockets or `DISPLAY=:99` into `guest_bash`**, enforce `Xvfb :99 -auth` (never `-ac` when sharing `--network container:<desk>` abstract sockets), and run `guest_bash` under a separate UID (e.g. `UID 2000`) when sharing `--pid` so `/proc/<pid>/root` cannot bypass GUI-only files.
- **Enforce Non-YOLO & Secret Hygiene**: Run all containers without `--yolo` or host-root bypasses (`--security-opt no-new-privileges`, verified `sandbox_mode = "workspace-write"` or `"read-only"`), and never expose private API keys in logs, containers, or reports.

## What Every Case & Harness MUST Avoid (Hard Bans)

Read [references/anti-patterns-and-case-archetypes.md](references/anti-patterns-and-case-archetypes.md) when auditing suites or building new cases. Reject all eight failure patterns below:

1. **Toy Synthetic GUI App Mockups (`*_QT_SOURCE` / `*_GTK_SOURCE` Trap)**
   - **Ban**: Embedding ~80-150 line inline `PyQt`/`GTK`/`Tk` scripts (`CutForge`, `ScoreCanvas`, `VectorForge`, `SignalDesk`) or static `<canvas>` facades to impersonate real creative/engineering/office software. Only set `ALLOW_SYNTHETIC_TARGET_APP = True` when a task explicitly tests black-box reverse engineering of an unknown proprietary utility (`<= 15%` of any suite).
2. **Frankenstein Role Pairings & Spoon-Fed Field Checklists**
   - **Ban**: Pairing unrelated jobs on one desktop (e.g., mortgage officer + digital-logic TA; font designer + CPU pipeline engineer) or listing exact target JSON keys/submenu paths/formulas in `task.md`.
3. **Harness Process-Namespace Traps, `isolated` Cross-Role Penalties & Post-Exit `Ctrl+S`**
   - **Ban**: Running a target daemon (e.g., `:18910` / `:19515`) in a container whose PID namespace is invisible to the agent's CLI when the task requires restarting that daemon (forcing LibreOffice UNO/macro container escapes).
   - **Ban**: Opening an absent peer role's dirty document during single-agent `isolated` baseline runs and penalizing the solo role for `split_brain` (`isolated < shared` inversion bug).
   - **Ban**: Sending `xdotool key ctrl+s` + `Return` inside `stop_and_grade()` after agents have exited, or leaving shared `~/Downloads` world-writable as an unmonitored plaintext chatroom.
4. **Unannounced Upstream Waiting + Locked Downstream Exit (`SA` / `SD` Trap)**
   - **Ban**: Fake self-consistent `v0` baselines with zero pending indicators, prompt write-bans (`Do NOT modify /workspace until...`), asymmetric dummy stages, or silent first-write locks (`official_wire_receipt`, `amendment_eco_seal`, `CLOSED_LOCAL_VERIFIED`).
5. **Pigeonhole Timeout Deadlocks + Lying Samplers (`FC v_final` Trap)**
   - **Ban**: Exclusive state-holding windows whose combined minimum time crowds `conc_role_timeout_s`, or hidden `BackgroundRegimeSampler` / `stage_purity` penalties behind `passed: true` responses.
6. **Busy-Wait / `sleep` Horizon Inflation & `FAST_SELFVAL` Masking**
   - **Ban**: `while time.monotonic() - t0 < 290.0` dummy loops, multi-minute endpoint sleeps, or `FAST_SELFVAL=1` timing shortcuts.
7. **Online-Judge Oracle Leakage**
   - **Ban**: Returning `HTTP 422` with exact cross-role coupling discrepancies or canary answers across unlimited `/submit` retries.
8. **Puppet Keystrokes & Rigid Boot-Time Split-Screen Tiling**
   - **Ban**: Puppet instructions (`"press Ctrl+Z twice"`), 4-row micro-probes, or hardcoding left/right split-screen window coordinates at boot (`--window-position=0,0` + `wmctrl -e 0,960,...`) unless `ALLOW_CUSTOM_WINDOW_LAYOUT = True` is justified by a specific case.

## Mandatory 5-Gate Well-Posedness Check vs. Model Calibration

Keep **deterministic problem-validity checks** (author's privileged ground-truth check, zero LLM calls) strictly separate from **real LLM difficulty calibration**:

### A. Deterministic 5-Gate Well-Posedness Check (Zero LLM Calls)
1. **`Gate 1 — pristine_fail`**: Untouched initial state fails (`joint_pass == False`, partial-credit baseline `<= 0.20`).
2. **`Gate 2 — gt_seq_ab_exists`**: Ground-truth solver achieves full credit (`1.0` / `joint_pass == True`) under `Role A -> Role B`.
3. **`Gate 3 — gt_seq_ba_exists`**: Ground-truth solver also achieves full credit under `Role B -> Role A` (zero hidden ordering trap).
4. **`Gate 4 — gt_naive_race_corrupts`**: Unguarded concurrent actions measurably corrupt target state or score (`joint_pass == False` or `Score_race < Score_isolated`).
5. **`Gate 5 — gt_careful_conc_feasible`**: Under **real tool timing** (using genuine multithreaded concurrency rather than a single global mutex shortcut), careful concurrent execution achieves full credit cleanly in real seconds (well below the `>= 7200s` anti-deadlock guard).

### B. Real LLM Screening Bar
- Require **non-saturated single-agent difficulty** (`isolated` / `seq` score in `0.40-0.85` or pass rate `35%-75%`) AND **measurable concurrent degradation** (`Score_shared < Score_isolated`), reporting token/latency/focus-flip overhead alongside accuracy.

Before running model evaluations, execute the static & harness auditor on both the task directory and its experiment runner:

```bash
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py <path/to/task_dir_or_runner.py>
```

Resolve every `FAIL` finding and review any `WARN` findings before spending evaluation budget.

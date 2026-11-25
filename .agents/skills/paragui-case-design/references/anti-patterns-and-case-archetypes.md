# Forensic Anti-Patterns & Empirical Lessons

Consult this reference when auditing benchmark suites or checking whether a proposed case avoids historical failure traps while staying realistic.

## 1. Six Historical Failure Families to Reject on Sight

### Family A: Unobservable Future Upstream Mutation (`stealth_arenas_v1` / `stealth_dual_v1`)
- **What happened**: `v0` in `/workspace` was engineered to look 100% self-consistent. Role A finished early, called `/api/ticket_close`, received `200 OK {"status": "CLOSED_LOCAL_VERIFIED"}`, and locked a hidden `official_wire_receipt`. Role B was forced by `Do NOT modify production files in /workspace until all 16 stages are calibrated` to wait ~32m before overwriting `/workspace` with `v1`, invalidating Role A's already-closed work.
- **Why it is invalid**: Role A had zero observable signal that an upstream change existed, and `official_wire_receipt` silently ignored re-submissions. Sequential solvability only worked `B -> A`, failing `A -> B`.
- **Fix**: Make `v0` visibly incomplete/unqualified for both roles, allow natural progressive writes, remove hidden first-submission locks, and require both `seq_ab` and `seq_ba` solvability.

### Family B: Pigeonhole Timeout + Lying Lab Sampler (`fair_contention_v1` `v_final`)
- **What happened**: Each role had to run 5 sequential `/api/bench/...` calls padded with `while time.monotonic() - t0 < 290.0` loops (~24.2m per role) while a hidden `BackgroundRegimeSampler` checked a mutually exclusive toggle. `/api/bench` lied (`passed: true`), offline `grade()` failed 29/30 runs, and `8.2 * 290s = 39.6m > conc_role_timeout_s = 38.0m` made concurrent completion mathematically impossible while `FAST_SELFVAL=1` hid it.
- **Why it is invalid**: In-environment lab instruments lied, 75% of wall time was dummy busy-waiting, and concurrent solvability was zero.
- **Fix**: Delete `BackgroundRegimeSampler` and wall-clock padding loops; keep tool execution times real; enforce `Gate 5` within `<= 55%` of `conc_role_timeout_s`.

### Family C: Online-Judge Oracle Leakage (`fair_contention_v1` `v1`)
- **What happened**: `/api/bench` and `/submit` ran full cross-role coupling verification and returned `HTTP 422` with exact error diagnostics across unlimited retries, letting models farm `/submit` as a free unit-test oracle.
- **Why it is invalid**: Hands the hidden exam key to the test-taker during the exam.
- **Fix**: Keep cross-role coupling, reference test manifests, and canary checks strictly inside offline `grade()`.

### Family D: Puppet Keystrokes & Toy Micro-Probes (`mechanism_expansion_v1` `MECH01..09`)
- **What happened**: 4-row spreadsheets / 4-line Writer files where prompts explicitly ordered *"Type sentence X, press `Ctrl+Z` twice to undo, then type sentence Y"*.
- **Why it is invalid**: Real users do not follow puppet undo scripts, and 4-row files do not represent authentic workflows.
- **Fix**: Keep prompts strictly goal-driven and embed contention in realistic multi-step workflows on real software.

### Family E: Harness PID Split, `isolated` Cross-Role Penalty & Post-Exit `Ctrl+S` (`EC-04`, `RBS-06`, `RBS3-04/05`)
- **What happened**:
  1. In `EC-04` and `RBS3-05`, a live Python daemon (`:18910` / `:19515`) was launched in `desk_container`, while role CLI containers only shared `--network container:<desk>` without `--pid`. Agents could not see or restart the daemon PID from CLI and spent 10+ minutes escaping the container via LibreOffice StarBasic/UNO shell execution; meanwhile world-writable `~/Downloads` became a plaintext coordination chatroom.
  2. In `RBS-06` and `RBS3-04`, two dirty LibreOffice docs (`Calc` for Role A, `Writer` for Role B) were opened at boot even in single-agent `isolated` mode; `stop_and_grade()` injected `Ctrl+S` on both windows and penalized solo Role A for not saving absent Role B's `.odt` (`isolated = 0.949 FAIL` vs `shared = 1.000 PASS`).
- **Why it is invalid**: Container topology bugs distort normal engineering tasks into sandbox-escape puzzles and corrupt the `isolated` control baseline.
- **Fix**: Share `--pid` (or provide a clean service supervisor) whenever agents must restart a daemon; scope `isolated` boot/grading strictly to the active role; never inject `Ctrl+S` after agent exit; keep shared `~/Downloads` non-chatroom or audited.

### Family F: Synthetic 100-Line PyQt/GTK Toy Mockups, Frankenstein Pairings & `1.0 -> 1.0` Saturation (`rb_osw2_synth_v1/v2`, `NF-20`)
- **What happened**: Instead of running real open-source desktop apps (`MuseScore`, `Shotcut`, `FreeCAD`, `Inkscape`, `GIMP`, `QGIS`), tasks embedded ~100-line inline `PyQt5`/`GTK` scripts (`CutForge_QT_SOURCE`, `ScoreCanvas_QT_SOURCE`, `VectorForge_QT_SOURCE`, `SignalDesk`), paired unrelated jobs on one screen (mortgage officer + digital-logic TA; font designer + CPU pipeline engineer), spoon-fed JSON field checklists in `task.md`, exposed `:99` X11 sockets inside `guest_bash` alongside artificial `max_cua_calls` caps (`42`–`180`) and 18-25m timeouts (`1080s`–`1500s`), and certified `1.000 -> 1.000` (93-180s) saturated tasks solely on token inflation.
- **Why it is invalid**: Violates single-case authenticity, saturates single-agent baselines (`0.96-0.99`), and contaminates GUI-driver ablations via CLI `xdotool`/`xclip` bypasses.
- **Fix**: Use real desktop/web software, plausible co-tenant roles, un-spoiled goal prompts, unlimited GUI/CLI steps with `>= 7200s` (`2h+`) anti-deadlock timeouts, `model_reasoning_effort = "high"`, non-saturated `0.40-0.85` single-agent difficulty with real `Score_shared < Score_isolated` degradation, and `Xvfb -auth` + separate-UID CLI isolation.

### Family G: Asymmetric `shared`-Only Score Multipliers & Brittle Non-GUI XML Parsers (`AW-19` `v1`, `NF2-15`)
- **What happened**:
  1. `build_aw_grade_payload` set `j_mult = 1.0` in `isolated` and `j_mult = 0.75` in `shared` while repeating single-role checks inside `checks_joint`, fabricating a `-23.6%` concurrent drop when `0` subchecks actually degraded.
  2. `NF2-15` parsed `.ui` files via raw `ElementTree` looking only for `<property name="minimumWidth">`, whereas saving in real `Qt5 Designer` serializes `<property name="minimumSize"><size><width>...`, turning GUI saves into `0 -> 9999+9999` failures.
- **Fix**: Keep per-role weights/denominators identical across `isolated` and `shared` (no `j_mult`), and load native app formats via real toolchains (`PyQt5.uic.loadUi`, headless `LibreOffice`, `FreeCAD`, `QGIS`, `Blender`) rather than brittle regex/tag assumptions.

---

## 2. Empirical Lessons from Real `OSWorld-V2` & `RecreationBench` Concurrency Runs

Keep these empirical system behaviors in mind as background knowledge (without turning them into rigid templates):

1. **Both Shared-Artifact Workflows AND Isolated-Workspace Shared-Display Workflows Are Valid**: On real `OSWorld-V2` (`OSW2-P5` Chrome responsive QA vs fullscreen capture: `0.939 -> 0.000`) and real `RecreationBench` (`DB Browser` modal file chooser vs `KSudoku`: `51.6% -> 23.1%`), severe contention occurs even when file workspaces are isolated—because the live running application or live display viewport is indispensable.
2. **Where Semantic Accessibility Drivers (`AT-SPI`) Still Collide**: Even when background element clicks avoid moving the cursor, display servers still share a single active keyboard focus (global shortcuts like `Ctrl+O`/`F10`/`Escape` and global XKB layouts hit the active window), modal dialogs (`Open File`, twin `Preferences`) and autohiding popovers preempt focus, and single-instance apps (`GIMP`, `WPS`, `LibreOffice`, `Chrome`) share internal active tabs/dialogs.
3. **Pure-GUI Terminal Self-Bootstrapping**: When external `guest_bash` is disabled on a real Linux desktop (`OSW2-P1/P4/P5`), coding-capable agents launch `gnome-terminal` via GUI shortcuts and end up typing concurrently into the **same foreground PTY** (sending `Ctrl+C` / `Ctrl+U` to each other's commands).
4. **Why Real Software Beats Toy Scripts**: Real open-source applications naturally yield non-saturated single-agent baselines (`32%-72%`) and realistic 10-30 minute trajectories without needing artificial sleep loops or arbitrary call caps.

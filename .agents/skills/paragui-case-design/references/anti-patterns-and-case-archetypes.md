# Forensic Anti-Patterns & Validated Case Archetypes

Consult this reference when auditing suspect benchmark suites or choosing concrete contention designs for new cases.

## 1. Four Historical Failure Families to Reject on Sight

### Family A: Unobservable Future Upstream Mutation (`stealth_arenas_v1` / `stealth_dual_v1`)
- **What happened**: `v0` in `/workspace` was engineered to look 100% self-consistent (all spreadsheets, CAD dimensions, and checksums matched `v0`). Role A (downstream) had only 6 dummy calibration steps, finished in ~18m, called `/api/ticket_close`, received `200 OK {"status": "CLOSED_LOCAL_VERIFIED"}`, and locked a hidden `official_wire_receipt`. Role B (upstream) was forced by `Do NOT modify production files in /workspace until all 16 stages are calibrated` to wait ~32m before overwriting `/workspace` with `v1` (e.g., expanding bore diameter or switching FX/routing), invalidating Role A's already-closed work.
- **Why it is invalid**: Role A had zero observable signal in `/workspace` or UI that an upstream change existed, and `official_wire_receipt` silently ignored re-submissions even when an agent tried to recover. Sequential solvability only worked `B -> A`, failing `A -> B`.
- **Fix**: Make `v0` visibly incomplete/unqualified for both roles, allow natural progressive writes, remove hidden first-submission locks, and require `seq_ab == True` AND `seq_ba == True`.

### Family B: Pigeonhole Timeout + Lying Lab Sampler (`fair_contention_v1` `v_final`)
- **What happened**: Across `FC-01..15`, each role had to run 5 sequential `/api/bench/...` calls padded with `while time.monotonic() - t0 < 290.0` loops (~24.2m per role). During Stages 2..5 (`4 * 290s`), a hidden `BackgroundRegimeSampler` checked whether a single shared `<canvas>` SSO toggle stayed on Role A's vs. Role B's mutually exclusive value for `>= 90%` of each stage. `/api/bench` always returned `passed: true` and `/submit` returned `200 APPROVED` without checking `stage_purity`; offline `grade()` then failed 29/30 runs on `regime_purity < 0.90`. Worse, `8.2 * 290s = 39.6m > conc_role_timeout_s = 38.0m` made 13/15 tasks mathematically impossible in concurrent mode even for cooperating oracles, while `FAST_SELFVAL=1` (`0.25s`) hid the impossibility during `self_validate`.
- **Why it is invalid**: In-environment lab instruments lied (`passed: true`), 75% of wall time was dummy busy-waiting, and concurrent solvability was mathematically zero.
- **Fix**: Delete `BackgroundRegimeSampler` and wall-clock padding loops; keep tool execution times real; enforce `Gate 5 (careful_conc_pass)` within `<= 55%` of `conc_role_timeout_s`.

### Family C: Online-Judge Oracle Leakage (`fair_contention_v1` `v1`)
- **What happened**: `/api/bench` and `/submit` ran full cross-role coupling verification and returned `HTTP 422` with exact error diagnostics across unlimited retries. Frontier models simply used `/submit` as a free unit-test oracle until `joint_pass == True` (>80% pass without genuine self-checking).
- **Why it is invalid**: Hands the hidden exam key to the test-taker during the exam.
- **Fix**: Keep cross-role coupling and canary checks strictly inside offline `grade()`. Let agents write and run their own verification scripts using real workstation tools before a one-shot hand-in.

### Family D: Puppet Keystrokes & Toy Micro-Probes (`mechanism_expansion_v1` `MECH01..09`)
- **What happened**: 4-row spreadsheets / 4-line Writer files where Role B's prompt explicitly ordered: *"Type sentence X, press `Ctrl+Z` twice to undo, then type sentence Y"* solely to trigger LibreOffice global undo against Role A.
- **Why it is invalid**: Real users do not follow puppet undo scripts, and 4-row toy files do not test realistic long-horizon workflows.
- **Fix**: Keep prompts strictly goal-driven and GUI-driver agnostic (so coordinate drivers like `qwen-cua`/`weavebench-cua` and semantic drivers like `cua-driver`/`agent-desktop` can be cleanly ablated on the same case), and embed conflicts in realistic multi-document/multi-step workflows.

---

## 2. Five Validated `GUI + CLI` Contention Archetypes (Positive Templates)

Use and combine these five proven patterns (validated in `macos_primitives_v1` `MP-01..05` and realistic engineering workflows) to create long-horizon, high-discrimination cases:

| Archetype | Shared OS / App Resource | Why Pure CLI Cannot Trivially Bypass It | How a Careful Agent Self-Checks & Succeeds |
|---|---|---|---|
| **1. GUI Dirty Buffer vs. Disk CLI Split-Brain** | Live open `.xlsx` / `.docx` / `.xcf` / `.FCStd` in desktop GUI + same file on disk | Role A must inspect/resolve GUI-only state (visual layers, tracked comments, live viewport, embedded scans) in the running desktop window; Role B updates structured tables/sheets via CLI. Saving the stale GUI buffer clobbers Role B's disk write. | Inspect file `mtime`/`sha256` and open window state (`wmctrl`/`xdotool`/lockfiles `.~lock.*`) before saving; reload or merge disk changes before final save. |
| **2. Cross-Step Clipboard Transaction** | X11 `CLIPBOARD` / macOS `NSPasteboard` single slot | Copying dynamic UI tokens/charts/signatures from a protected GUI app or browser canvas (`Ctrl+C` or UI Copy button), switching context to validate, and pasting into target dossier/form spans multiple steps. | Read back clipboard content (`xclip -o` / `pbpaste`) or verify pasted target content/hash immediately after pasting before final hand-in. |
| **3. Single-Instance App Lock & Shared Profile** | LibreOffice single `soffice.bin` + `.~lock`, Chrome `SingletonLock`, `.git/index.lock`, fixed local port | Launching CLI `soffice --headless --convert-to pdf` without isolated `-env:UserInstallation` silently blocks/fails when GUI LibreOffice holds the default profile; launching `chromium URL` injects a tab and steals focus in the live window. | Detect running instances/lockfiles, pass isolated `-env:UserInstallation=file:///tmp/...` for headless conversions, or coordinate clean git branch/merge state before hand-in. |
| **4. Shared Authenticated Browser Session & `~/Downloads`** | `HttpOnly` SSO session cookie + server-side session state (role/currency/filter) + `~/Downloads/<fixed_name>.csv` | Raw CLI `curl` lacks `HttpOnly` session cookies; clicking UI filters mutates shared server-side session state during multi-second exports and writes to the same default download filename. | Re-verify visible UI filter banner immediately after export completes, check CSV headers/timestamps/row invariants, and move verified exports to private scratch paths immediately. |
| **5. Modal Grab / Continuous Drag + Coupled Engineering Artifacts** | Display server pointer/focus during `drag` or modal save dialogs + shared coupled CAD/PCB/GIS/ledger files | Physical drag operations (timeline trim, canvas crop, slider) break if another GUI window pops up or clicks mid-drag; meanwhile both roles' subsystem edits share a tight two-sided physical/financial envelope (e.g., thermal budget, clearance, DSCR, LUFS). | Verify visual drag outcome via post-action screenshot + local CLI geometry/physics script; re-read shared artifact right before finishing to confirm joint envelope invariants still hold. |

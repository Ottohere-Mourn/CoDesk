# CoDesk Mechanism Validation Round 1

**Snapshot:** 2026-09-30, canonical A6000 repository.  
**Purpose:** exploratory mechanism screening, not a benchmark success-rate study.  
**Task/evaluator:** `CODESK-TA-OFFICE-001` v1.0.0 and its existing exact Flat ODF evaluator; no scoring rule or goal was changed.  
**Source checkpoint before this report:** `cc4bc7992032bfbde58594438f9783275530248c` (working tree then contained the listed setup/remote-client changes).

Evidence labels: **VERIFIED** = inspected from run artifacts/source/Git; **SCRIPTED ONLY** = real Guest/app with scripted actors; **OFFLINE ONLY** = source/schema/unit validation; **DESIGN ONLY** = no live task path; **INVALID_INFRA** = episode did not reach a valid actor-task trial; **NON-CAUSAL** = observed data do not isolate desktop sharing.

## 1. Executive Summary

| Mechanism | Round-1 decision | Evidence basis |
|---|---|---|
| Focus / input routing | **KEEP (anchor)** | **SCRIPTED ONLY:** historical real-Guest focus task recorded active-window transitions and keyboard misrouting under shared desktop; current Qwen evidence is one valid Writer Solo, with no valid two-model comparison. Historical MA-ID/MA-SD office results have a backend-topology mismatch and are **NON-CAUSAL**. |
| Clipboard ownership | **BLOCKED** | **OFFLINE ONLY:** sampler, task actor, evaluator, and attribution rules exist. No Guest observer-on/off episode; selection reads may perturb the owner and application paste target identity is unproven. |
| Window / modal competition | **BLOCKED** | **OFFLINE ONLY:** Save As instance/evaluator schema exists. No native dialog task runner, Guest dialog-owner trace, or scripted recovery episode. |
| Application internal context | **BLOCKED** | **OFFLINE ONLY:** two-tab fixture and evaluator schema exist. No live evidence joining constant X11 window ID to active-tab/page change. It cannot yet be distinguished from ordinary focus routing. |

**Capacity:** **STABLE for two-Guest startup, desktop readiness, accessibility/screenshot, and reset** on A6000. This is not a pass for the shared-backend Writer/Calc task: application save readiness failed before actors in the corrected shared-backend attempts.

**Round-1 funnel:** historical scripted focus evidence and one valid Qwen Writer Solo can be reused. No valid dual-model MA-SD or topology-matched MA-ID completed. Clipboard, Modal, and Application Context did not pass their real-Guest scripted gate. Continue mechanism validation; do not begin workflow expansion or generate large seed sets.

## 2. Infrastructure Status

### A6000 Guest capacity

- **VERIFIED:** OSWorld V2.1 real Guests launched through the existing Docker/QEMU runtime. Screenshots reached 1920×1080 and accessibility trees were returned; the r04 Writer and Calc setup identified the requested documents and initial ODF state.
- **VERIFIED, capacity-only:** `capacity-same-backend-maid-20260930-r04` ran two distinct Guests against one recorded backend ID. Both Guest sessions were simultaneously live for about 3m46s before the first reset; the complete run took about 540 seconds. Both reset checks passed, the ownership ledger recorded destruction for every created container, and no container remained active.
- During r04, host load was roughly 8–11; CPU PSI stayed at 0; available memory was about 218–223 GiB; swap-free was about 2.95 GiB; I/O PSI was near 0. Per-Guest `docker stats` showed roughly 3.4–3.7 GiB and peaks near 3.3 CPU cores. Later single-Guest setup runs also had CPU PSI 0 and over 220 GiB available memory.
- **Limitation:** readiness in r04 did not include a successful LibreOffice save through the shared 9p backend. Therefore the capacity result means the hardware can host the two Guests; it does not mean the MA-ID task is operationally ready.

### 4090 inference

- **VERIFIED historical route:** `a6000-writer-4090-solo-20260930-r01` used the native OSWorld V2.1 `Qwen3VLAgent` on an A6000 Guest and one Qwen3-VL-30B-A3B worker on 4090 through an SSH reverse port-forward. The agent produced five model responses/five GUI action steps; Writer exact-state evaluation and reset passed. Per-request inference times were 6.10–8.19 seconds (five requests; descriptive only). Provenance hashes were reconciled. This is one unversioned Writer Solo smoke, not dual-agent evidence.
- The worker and tunnel from that completed episode are stopped. No current 4090 model worker was found.
- **Current resource gate:** 4090 load was 126.55 / 82.84 / 68.97 and CPU PSI was `some avg10=26.50`, `avg60=40.58`, `avg300=23.42`; swap free was zero. GPUs 0–3 were idle at the observation, but given host CPU pressure and exhausted swap, no new model worker was started. This turn collected no new model latency or model trajectory.
- Earlier A6000-local Qwen episodes `a6000-qwen-writer-calc-solo-20260930-r01`, `r02`, and `r04-stage-timing` returned zero model steps and are **INVALID_INFRA / model-service failures**, not task failures.

### Current resources

All Round-1 run-created Guest containers were destroyed and `docker ps` returned zero active containers after the runs. Historical invalid artifacts and overlays were preserved. No other process, container, image, volume, or project was stopped or modified.

## 3. Per-Mechanism Evidence

### Focus / Input Routing — KEEP (anchor)

- **Workflow:** Writer + Calc independent edits (`CODESK-TA-OFFICE-001`), plus the prior real-Guest terminal focus-routing task `SWCUB-FOCUS-ROUTING-001` v2.0.0.
- **Scripted feasibility:** **SCRIPTED ONLY, historical.** `TRACK_A_RESULTS.md` records five real-Guest MA-SD trials with a scheduled, legitimate change of focus; each recorded a Document→Chat focus transition and two Document-actor keyboard actions received by Chat. The hidden evaluator detected contamination. This is a mechanism reproduction under its stated fixture; it is not a natural-model failure rate.
- **Historical office controls:** the old Writer/Calc report records Solo/MA-ID/MA-SD scripted repetitions and focus exposure. Its MA-ID used separate workspaces while MA-SD used one desktop; those paired values are **NON-CAUSAL** for desktop sharing. See `REAL_APP_TRACK_A_RESULTS.md` and `REAL_APP_TRACK_A_DESIGN.md`.
- **Qwen Solo:** one **VERIFIED** Qwen3VLAgent Writer Solo PASS on A6000/4090 (`a6000-writer-4090-solo-20260930-r01`, five steps). The older paired Writer/Calc five-step smoke from 2026-09-29 has post-hoc provenance and is smoke-only. No valid current Calc Solo pass was found; the earlier calibrated Calc baseline was 0/5.
- **Topology-matched trial attempts:**
  - `capacity-same-backend-maid-20260930-r04`: same-backend identity validator passed, but both files were root-owned `0644`; LibreOffice opened them read-only. Both scripted goals failed at final state. This is **INVALID_INFRA/task setup**, not focus interference.
  - `capacity-same-backend-maid-20260930-r05`: Guest `chmod` returned `EPERM` against the 9p file; aborted at application setup.
  - `capacity-same-backend-maid-20260930-r06`: coordinator-seeded `0666` files avoided the read-only title, but Writer Ctrl+S raised LibreOffice “insufficient user rights”; aborted at no-op-save validation.
  - `capacity-same-backend-maid-20260930-r07` and `capacity-same-backend-maid-20260930-r08`: one-Guest MA-SD setup reached Calc, but Ctrl+S raised the same application error before actors ran. r08 logged Guest UID/GID `1000:1000`, file UID/GID `1037:1037`, file mode `0666`, directory mode `0777`, `os.access(W_OK)=true`, and a passing create/rename/delete probe. The exact artifact and screenshot are retained.
- **Exposure / interference / outcome / recovery:** historical Track A scheduled exposure = yes; observed focus transition and keyboard misrouting = yes; joint goal outcome = fail by task design; autonomous recovery = not tested in that fixture. New same-backend Qwen exposure/interference/outcome/recovery = not observed because setup aborted before actor turns.
- **Judgment:** KEEP the Focus anchor because a distinct focus/input-routing signature is already observable on a real shared Guest. Do not claim Qwen susceptibility or a matched MA-ID-vs-MA-SD causal effect.

### Clipboard ownership — BLOCKED

- **Workflow:** `CODESK-TB-CLIPBOARD-001`, Writer/Calc copy→replace→paste with an optional explicit recopy recovery.
- **Scripted feasibility:** no real Guest task episode this round; there is no integrated Guest task runner for the prototype.
- **Observer:** **OFFLINE ONLY.** The probe records X11 CLIPBOARD owner XID, payload digest/generation, active/focused window evidence, and sampling duration. XID is not logical Actor ownership. Sampling text asks the current selection owner to convert the requested target and can perturb timing; no observer-on/off live comparison exists.
- **Solo / MA-SD / MA-ID / recovery:** not run. A same-backend MA-ID clipboard/session adapter is also unvalidated.
- **Attribution boundary:** without stable payload digest plus independently observed paste target, clipboard overwrite cannot be separated from focus/input misrouting. Keep target attribution `unknown` when accessibility does not identify the editable object.

### Window / Modal Competition — BLOCKED

- **Workflow:** Writer/Calc Save As or format/overwrite confirmation (`writer_calc_save_dialog_v1`).
- **Scripted feasibility:** **OFFLINE ONLY.** Manifest generation and final path/content/format oracle exist; there is no real task runner or stable dialog-owner instrumentation.
- **Solo / MA-SD / MA-ID / recovery:** not run. Native dialog XID, owning application/window, target path, and recoverable second-Actor behavior are unverified.
- **Judgment:** no evidence supports either a distinct modal family or merging it into Focus yet.

### Application Internal Context — BLOCKED

- **Workflow:** Chromium one top-level window, two Actor-specific tabs/pages (`chromium_two_tab_context_v1`).
- **Scripted feasibility:** **OFFLINE ONLY.** Server fixture and exact state evaluator exist; no Guest run joined browser tab/page identity with X11 active-window identity.
- **Solo / MA-SD / MA-ID / recovery:** not run.
- **Distinctness criterion:** only evidence of a constant top-level X11 window ID while active tab/page context changes can separate this candidate from OS-level Focus. Without it, evidence remains `unknown`; no MERGE or KEEP decision is justified.

## 4. Causal Validity

| Comparison | Status | Why |
|---|---|---|
| Historical office MA-ID vs MA-SD | **NON-CAUSAL** | Legacy MA-ID used separate workspaces/backends; MA-SD used one shared desktop. Backend topology changed with desktop topology. |
| Historical Track A MA-ID vs MA-SD | **Not a shared-backend causal comparison** | It is a valid focus fixture control for its own declared terminal/session setup, but its MA-ID does not represent the new same-authoritative-workspace contract. It supports existence of a focus mechanism, not the current matched topology contrast. |
| New same-backend Writer/Calc MA-ID vs MA-SD | **No valid pair** | Both conditions encountered LibreOffice save failures on the shared 9p path before actor actions. No valid outcomes exist to compare. |
| Qwen Solo vs shared | **No comparison** | One valid Writer Solo only; no valid current Calc Solo and no dual-model MA-SD/MA-ID episode. |

For any future comparison, keep Actor goals, task seed, backend identity/state, model/agent/prompt, per-Actor budget, fixed schedule, evaluator, app version, and reset rule unchanged; vary desktop session sharing alone. Record scheduled exposure, observed interference, final outcome, and recovery as separate fields.

## 5. Failure Analysis

### Infrastructure / setup failures

| Run ID | Exact failure point | Classification | Evidence / disposition |
|---|---|---|---|
| `capacity-same-backend-maid-20260930-r01` | OSWorld import could not resolve its relative proxy config; startup did not reach a valid task | **INVALID_INFRA** | Original artifact preserved; only the run-created container was cleaned after full ID/label/ledger verification. |
| `capacity-same-backend-maid-20260930-r02` | Guest screenshot/accessibility readiness passed; passwordless `sudo -n` could not mount 9p | **INVALID_INFRA** | Mount command updated to use the current Guest's configured password for the short-lived mount operation; evidence retained. |
| `capacity-same-backend-maid-20260930-r03` | Shared mount succeeded; Guest setup failed writing task file due permission error | **INVALID_INFRA** | Evidence retained; led to writable run-scoped backend/setup diagnostics. |
| `capacity-same-backend-maid-20260930-r04` | Both Guests reached app setup; Writer/Calc opened read-only and scripted outputs did not persist | **INVALID_INFRA / setup-gate false negative** | Final evaluator failed both; not model or focus failure. Same backend ID and two desktop IDs were recorded. |
| `capacity-same-backend-maid-20260930-r05` | Guest setup attempted chmod on a file it did not own; EPERM before app readiness | **INVALID_INFRA** | No actor turn; retained. |
| `capacity-same-backend-maid-20260930-r06` | Writer Ctrl+S no-op save showed “insufficient user rights” although initial ODF content still parsed exactly | **INVALID_INFRA / shared filesystem-app integration** | Saved screenshot and exact permission probe artifacts retained. |
| `capacity-same-backend-maid-20260930-r07` | Calc Ctrl+S no-op save showed same application error before actors | **INVALID_INFRA** | One real Guest; no actor trial. |
| `capacity-same-backend-maid-20260930-r08` | Same Calc save error; Guest mode/access and atomic filesystem probe all passed | **INVALID_INFRA / unresolved 9p-to-LibreOffice save behavior** | Diagnostic rules out simple lack of mode bits or directory write access; exact save failure still needs a minimal isolated reproduction. |

`PROXY_CONFIG_FILE` is now supplied as an absolute path in experiment commands. Existing task/evaluator/scoring rules were not changed. No container/image prune or unrelated cleanup was performed.

### Model capability failures

- No model task failure was produced in this round. The three A6000-local Qwen zero-step runs and two earlier shared-runner attempts were service-invalid. The one remote Writer Solo passed.
- No new model episode was started under current 4090 CPU pressure/swap exhaustion.

### Task design / instrumentation failures

- Shared-workspace Writer/Calc setup cannot currently pass the required LibreOffice no-op-save persistence gate through the same-backend QEMU 9p mount. Mode `0666`, directory mode `0777`, Guest `os.access`, and atomic create/rename/delete were insufficient to make LibreOffice save successfully. Do not count later Actor outcomes until this setup is fixed and revalidated.
- Clipboard, Modal, and Application Context currently lack runnable live Guest task paths and their required mechanism-specific evidence joins.

QEMU documents `security_model=none` as passthrough-like while suppressing ownership-setting failures; its documented `fmode`/`dmode` defaults apply only to `mapped-xattr` and `mapped-file`. That makes the observed Guest/host ownership boundary relevant, but does not by itself identify why LibreOffice's save operation is rejected. See [QEMU user documentation](https://www.qemu.org/docs/master/system/qemu-manpage.html). Linux documents `access=any` as a single-attach mode; this is already used by the current mount helper and did not resolve the observed app save error. See [Linux 9p filesystem documentation](https://www.kernel.org/doc/html/latest/filesystems/9p.html).

## 6. Mechanism Decision

| Mechanism | Feasibility | Solo | MA-SD | MA-ID | Distinct signature | Decision |
|---|---|---|---|---|---|---|
| Focus / input routing | Real Guest and scripted focus fixture historically pass; current shared-backend app setup fails | One Qwen Writer Solo pass; Calc gate absent | Historical scripted evidence only, topology caveat | Historical values not topology-matched; new same-backend setup invalid | Yes: X11/window focus transition plus keyboard misrouting in historical fixture | **KEEP (anchor)** |
| Clipboard | Offline code only | None | None | None | Unknown; observer perturbation and paste target unresolved | **BLOCKED** |
| Window / modal | Offline fixture/oracle only | None | None | None | Unknown; no native dialog owner trace | **BLOCKED** |
| Application Context | Offline two-tab fixture only | None | None | None | Unknown; no constant-window-ID/tab-change trace | **BLOCKED** |

## 7. Next Stage Recommendation

1. Keep Focus as the single validated anchor. Do not expand its workflow family or claim model interaction effects yet.
2. **Continue mechanism validation**, beginning with the shared backend save blocker. Use a minimal disposable Guest test that records mount options, Guest identity/mode, direct file create/write/rename, and LibreOffice save; only change the run-owned task directory. If the current 9p provider cannot support the app save protocol without changing topology, stop and design an equivalent same-backend MA-ID/MA-SD adapter before any causal comparison.
3. When the shared backend is operational, revalidate a scripted Solo write/read/save/reset on both Writer and Calc; then run Calc Qwen Solo only after 4090 pressure/swap recover and the remote worker health gate passes. The previous Writer Solo may be reused as one smoke datapoint, not as a rate.
4. Clipboard next: implement/run only its smallest Guest copy/paste probe with observer off/on controls. Stop if observer changes owner, payload, or timing or if the target widget cannot be identified.
5. Modal and Application Context remain queued until Clipboard's live gate is concluded; then require native dialog ownership or constant X11-window / changing tab identity respectively.
6. Do **not** start 10–15 workflow expansion yet. The present evidence supports one focus anchor and three blocked candidates, not a sufficiently validated mechanism portfolio. Do not create 200–300 same-workflow seed instances.

## 8. Artifacts and Reproduction

- A6000 report: `MECHANISM_VALIDATION_ROUND1.md`.
- Current run artifacts: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/mechanism-validation-round1/`.
- Notable reports: `capacity-same-backend-maid-20260930-r04/report.json`; `capacity-same-backend-maid-20260930-r05/capacity-same-backend-maid-20260930-r05/error.json`; `capacity-same-backend-maid-20260930-r06/error.json`; `capacity-same-backend-masd-20260930-r07/error.json`; `capacity-same-backend-masd-20260930-r08/error.json`.
- r08 setup screenshot: `capacity-same-backend-masd-20260930-r08/setup-validation/calc-after-noop-save.png`.
- Offline regression subset: `44 passed` (`test_writer_calc_readiness.py`, shared-workspace, clipboard observer, prototype tasks, and OSWorld adapter contract tests). This does not validate Guest tasks.
- No result artifact was overwritten. No model was loaded in this round. No remote push was performed.

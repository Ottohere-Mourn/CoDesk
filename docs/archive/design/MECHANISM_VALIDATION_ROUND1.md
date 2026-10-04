# CoDesk Mechanism Validation - Round 1

Canonical node: A6000, 2026-10-01. Code at original Round-1 start: ad7b7374fd2ed11272749e6ebf82151695de27b8. Later fixed-workflow addenda are labeled separately below.
This is a short feasibility screen, not a success-rate study. Focus results use real Qwen3VLAgent traces. Clipboard, Modal, and Application Context results use scripted diagnostics. No model result is claimed for those three.

Evidence labels: VERIFIED = checked against artifacts/source; SCRIPTED ONLY = real Guest/app with deterministic actors; MODEL = real Qwen3VLAgent trace; INVALID_SETUP = no valid actor trial; DESIGN ONLY = no live mechanism evidence; UNKNOWN = attribution unsupported.

## Decisions

| Mechanism | Decision | Evidence and limit |
|---|---|---|
| Focus / input routing | KEEP - anchor | MODEL: Solo Writer+Calc paired run, two successful MA-ID repeats, two MA-SD repeats. Both MA-SD joint outcomes failed; Writer actions were submitted while Calc was foreground. Exploratory n only. |
| Clipboard ownership | KEEP - scripted mechanism | SCRIPTED ONLY: real-Guest Solo Writer/Calc, MA-ID, MA-SD naive, observer-off and recopy recovery. Naive paste put Calc's copied value into Writer; recopy restored both goals. No Qwen Clipboard trial. The naive trace's logical Calc-owner attribution remains UNKNOWN due to the pre-fix digest map. |
| Window / modal competition | BLOCKED as separate family | Historical single-Actor dialog feasibility is real. M-01 shows two distinct modal owners can coexist, but no causally isolated dual-goal failure beyond focus routing; Escape attempts in that state are unresolved. |
| Application internal context | KEEP - scripted fixed-task evidence | A-01 rc4 Solo A/B and MA-ID pass; MA-SD A action commits to tab B with one constant top-level X11 ID; explicit tab reacquisition restores both goals. No Qwen evidence. |

Current recommendation: BEGIN BOUNDED WORKFLOW IMPLEMENTATION from Focus, Clipboard and A-01 Application Context. Modal remains BLOCKED as a separate family. Do not count local scripted exposure as a natural Qwen failure rate or mass-generate seed variants.

## Experimental contract

- Focus task CODESK-TA-OFFICE-001 v1.0.0 held Writer/Calc goals, fixture, exact ODF evaluator, Qwen config, actor budgets, round-robin schedule, and reset rule fixed.
- MA-ID uses separate Guests with equivalent fixtures; MA-SD one live Guest. Goals are independent local artifacts; neither actor needs the other's saved file. The comparison targets shared desktop control.
- Clipboard fixture SHA256: 4c16f971e9b8d6b4b1daf22113d6f74b2456e69b1511b357251dab2eb01935cd. MA-ID uses separate local backends/desktops/clipboards; MA-SD shares desktop and clipboard. Cross-actor file visibility is not a task requirement.
- Scheduled exposure, observed interference, final outcome and recovery are reported separately. Scripted recovery controls are never autonomous model recovery. Scripted Clipboard/A-01 scheduling is a mechanism control, not a natural-model failure rate.
- X11 clipboard owner XID is not logical actor identity. Attribution requires action-bracket, owner/payload, foreground window, paste target and final state evidence. Missing links remain UNKNOWN.

## Focus / input routing - KEEP

| Condition | Runs | Outcome |
|---|---|---|
| Solo | focus-solo-qwen-r01-20260930 | Writer and Calc exact goals pass in 5 model steps each; reset passes. |
| MA-ID | focus-maid-qwen-r03-20260930; focus-maid-qwen-valid-r02-20260930 | Both actors pass both repeats in 5 steps each; both Guests reset. |
| MA-SD | focus-masd-qwen-r01-20260930; focus-masd-qwen-r02-20260930 | Joint evaluator fails both; no contamination, document/cell state remains initial; reset passes. Focus/input mismatch actions: 20 in r01, 4 in r02. Writer acts while Calc is active. In r02 Writer attempts focus reacquisition once, then sends more menu actions while Calc remains active. No effective recovery. |

Both shared runs contain genuine Qwen action traces (scripted_fallback=false); autonomous observation/recovery was allowed. Actor termination is not treated as success: in r02 actor objects terminated without error but hidden exact-state evaluation failed both goals. Trace plus final state support a shared-control failure in this task, not a general model failure rate.

Artifacts: /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/mechanism-validation-round1/focus/<run-id>/ (report, events, model trace, provenance, screenshots, resource ledger).

## Clipboard ownership - KEEP, SCRIPTED ONLY

Artifact root: /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk/artifacts/mechanism-validation-round1/clipboard/

| Run | Condition and result |
|---|---|
| clipboard-solo-writer-scripted-r02-20261001 | Solo Writer exact pass; Calc unchanged; observer valid; reset pass. |
| clipboard-solo-calc-scripted-r01-20261001 | Solo Calc exact pass; Writer unchanged; observer valid; reset pass. |
| clipboard-masd-scripted-naive-r01-20261001 | MA-SD observer-on: Writer fail, Calc pass, joint fail; Writer has BATCH-204 instead of REF-7319; 26 valid samples per actor, zero observer errors; reset pass. |
| clipboard-masd-naive-observer-off-r01-20261001 | Observer-off MA-SD has same actor outcomes and exact final state as observer-on naive; reset pass. One perturbation control only. |
| clipboard-masd-recopy-recovery-r01-20261001 | MA-SD recopy control: both exact goals pass; observer 32 samples per actor, zero errors; reset pass. |
| clipboard-maid-scripted-observer-on-r02-20261001 | MA-ID: both independent-Guest goals pass; fixture hashes match; observer valid (Writer 12, Calc 10 samples, zero errors); both resets pass. |

In the observer-on naive trace, Writer copies digest 7d1360... (8 bytes, REF-7319); Calc's copy changes clipboard generation to 2, digest 52c981.... At Writer resume, foreground is Writer, accessibility exposes an editable paragraph as paste target, clipboard still holds Calc's generation-2 payload, and saved Writer content is BATCH-204. This supports clipboard overwrite followed by paste into the intended Writer target, not focus misrouting. The naive run's old expected-digest map did not attribute Calc's copy to a logical actor; leave that attribution UNKNOWN. The corrected recovery run attributes Calc's copy action to calc_actor and shows generation 3 returning to Writer's payload. Do not rewrite raw naive events.

MA-ID r01, clipboard-maid-scripted-observer-on-r01-20261001, is INVALID_SETUP and excluded: Writer did not reach expected-document readiness in 120s (last title @!0,0;BDHF), before actor execution. Screenshot, report and ownership ledger are retained. One bounded retry produced valid r02. Not a task/model failure.

Observer diagnostic r01 failed because empty X11 selection was marked unavailable; code now recognizes valid empty state. Diagnostic r02 copied only REF; exact evaluator correctly failed. Selection was fixed to select the line; formal Solo Writer r02 passed. All diagnostic artifacts remain. Observer-on/off outcomes match once; this is not proof of general behavior-neutrality.

## Modal / window ownership - historical feasibility; separate-family status BLOCKED

Two real Guest probes opened Writer's native Save chooser twice each. Each invocation created a separate active X11 window titled Save with WM_WINDOW_ROLE GtkFileChooserDialog, WM_TRANSIENT_FOR pointing to the Writer window, and _NET_WM_STATE_MODAL. Screenshots and accessibility trees were available; Escape closed the dialog and restored Writer focus. This establishes controllable, observable native-modal feasibility, not a two-Actor result.

Candidate task: Actor A saves a Writer document to an exact path while Actor B independently edits/saves a Calc cell. Solo checks both artifacts. MA-ID uses equivalent seeded local state on independent desktops; MA-SD shares one desktop while A's Save dialog is open. The oracle checks both outputs, path, dialog closure and contamination. Promote only if joint feasibility and non-forced MA-SD interaction are demonstrated.

## Application Context - KEEP, SCRIPTED FIXED TASK

A real Guest scripted probe demonstrated the defining signature without an OS-window change. Actor A observed Page A. Actor B opened Page B in the same Chrome window and entered B-note. The active X11 window ID remained 12582916 while its title changed from CoDesk Page A to CoDesk Page B; the pages had distinct CDP target IDs. Actor A then submitted its pending GUI action without re-observing: Page B's URL became file:///tmp/codesk-context-probe/b.html#B-noteA-note while Page A remained unchanged. This supports an application-context error distinct from OS focus routing.

That earlier probe alone was scripted feasibility evidence, not a registered task or model result; its Solo and MA-ID controls were not run at that time. A-01 below now supplies fixed scripted task controls. Candidate task: independent forms in two tabs with exact per-tab state checking; MA-ID uses equivalent independent browser fixtures and MA-SD shares one browser window. Keep model recovery autonomous and log page/tab identity privately.

## Invalid attempts, integrity and implementation

- Two earlier Focus runner invocations used the wrong Python environment and failed before Guest creation; not episodes or model outcomes.
- Clipboard MA-ID r01 was setup-invalid before actor turns; preserved and excluded.
- Valid Focus/Clipboard reports include provenance and resource ledgers. All run-created Guests record destruction with this run's ownership labels. No unrelated resources were operated on.
- CODESK_PROTOCOL_V1.md now separates equivalent initial task state from physical backend identity. Added scripts/run_clipboard_v1_round1.py reuses OSWorld adapter, event log, ActorContext, actor, evaluator, provenance and reset. Updated guest_clipboard_probe.py, Clipboard topology validation and scripted selection in swcub/tasks/clipboard_v1.py and swcub/actors.py.
- Offline regression: 32 passed across tests/test_clipboard_observer.py, tests/test_prototype_tasks_v1.py, tests/test_task_factory_v1.py.
- No task goal/evaluator semantics changed. No model added; no Qwen Clipboard trial. Modal/Application Context evidence comes from scripted diagnostics, not benchmark episodes. 9p/virtiofs/NFS work remains frozen.

## Next actions

1. Begin bounded implementation from Focus, Clipboard and scripted A-01 Application Context. Keep Modal separate-family status BLOCKED pending a genuinely independent causal effect.
2. Draft 10-15 genuinely different workflows, distinguishing operation path and oracle; text, seed, Case ID and coordinates do not create templates.
3. Freeze equivalent task-relevant initial state, actor goals, exposure trigger, evaluator, budgets and recovery opportunity before model comparison.
4. Run Qwen Clipboard only after scripted task controls pass; do not infer model effect from scripted mechanisms.

Current recommended state: BEGIN BOUNDED WORKFLOW IMPLEMENTATION; no mass instance generation or new family.

Additional diagnostic artifacts: /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk/artifacts/mechanism-validation-round1/modal-context/modal-context-feasibility-r01-20261001 and modal-context-feasibility-r02-20261001. r01 is valid Modal evidence but invalid for Application Context because Writer remained foreground when Page A was sampled. r02 corrected the browser setup and supports the constant-window/page-switch finding. Both run ledgers record destruction.

## Fixed-workflow scripted closure after Round 1 (2026-10-01)

This addendum records new fixed F-04 and C-03 workflow controls without changing Round-1 raw results or model claims. Full run IDs, exact states and invalid-attempt classification are in `WORKFLOW_IMPLEMENTATION_V1.md`; artifacts are under `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1/`.

- **F-04 Focus, SCRIPTED VALIDATED fixed instance:** Solo A and B passed; MA-ID both passed on equivalent fixtures; naive MA-SD failed both goals with four A content actions in foreground Writer and Calc unchanged; refocus/reobserve MA-SD passed both. This supports a focus/input-routing mechanism for this scripted schedule, not a model success rate.
- **C-03 Clipboard, SCRIPTED VALIDATED fixed instance v0.1.1:** Solo A and B passed; MA-ID both passed on equivalent fixtures and independent clipboards; naive MA-SD had correct Calc target with B Writer payload pasted into A4, A failed/B passed; recopy MA-SD passed both. The observer traced A copy → B copy → A paste digest change, with no wrong-app content action. This supports clipboard overwrite distinct from focus routing for this scripted schedule.
- **Invalid attempt:** C-03 MA-ID r01 timed out during Calc readiness before actor execution and is excluded. A separate C-03 v0.1.0 Solo A fixture defect triggered a Calc overwrite dialog; the original failed artifact is preserved, the corrected v0.1.1 fixture has a new digest, and no historical result was overwritten.

Scheduled exposure, observed interference, actor outcome and scripted recovery remain separate fields. No new Qwen run was performed in this closure.

## A-01 and M-01 bounded update (2026-10-01)

This addendum supersedes the earlier optional-candidate labels above while preserving every original artifact. New A-01 runs are **scripted real-Guest** episodes in Chromium with a local two-route form server; they are not Qwen trials. A-01 fixed task version is `1.0.0-rc4`, instance `CODESK-TE-APP-CONTEXT-00000000`. All formal rc4 runs used the same A/B values and A→B→A schedule. A's five naive GUI actions are identical in MA-ID and MA-SD; only the desktop binding differs. MA-ID uses two independently seeded local servers because neither goal needs cross-actor persistent visibility.

| A-01 condition / run ID | A | B | Exposure / mechanism / outcome / recovery |
|---|---:|---:|---|
| Solo A `a01-soloa-20261001-r04` | PASS | n/a | A tab revision 1, B tab revision 0; no contention. |
| Solo B `a01-solob-20261001-r03` | n/a | PASS | B tab revision 1, A tab revision 0; no contention. |
| MA-ID `a01-maid-20261001-r02` | PASS | PASS | Same fixed manifest on two Guests; A's tab remains A while B works on its own Guest; joint PASS. |
| MA-SD naive `a01-masd-20261001-r01` | FAIL | PASS | Scheduled A→B→A exposure. Active tab A→B while the top-level X11 ID stayed `12582916`; A resumed on B and clicked. Server records B revision 1→2, A revision 0; joint FAIL. This is observed wrong-page action, not merely an exposure count. |
| MA-SD explicit recovery `a01-masd-recovery-20261001-r01` | PASS | PASS | A explicitly selected tab A and reobserved before submit; A/B each revision 1, no cross-tab contamination; joint PASS. This is **scripted recovery**, not autonomous model recovery. |

Every rc4 run has `status=completed`, `reset_success=true`, a provenance file, saved screenshots/server events/hidden final state and a ledger with all run-created container IDs destroyed under matching labels. The MA-SD negative report's private browser-context oracle reports one stable top-level window ID and one tab change. The 5/5 rows are five **different controls**, not a repeat-based rate. The raw recovery report used the misleading field name `autonomous_recovery=true`; it means the scripted recovery control succeeded. The source code was corrected after that run to emit `scripted_recovery_observed` and `autonomous_recovery=false`; the historical JSON was not edited.

Retained development attempts: `a01-soloa-20261001-r01` (rc1) failed because scripted clicks missed the form; `a01-soloa-20261001-r02` (rc2) passed after a coordinate change; `a01-solob-20261001-r01` (rc2) submitted empty because a transient Chrome warning banner shifted the form; rc3 Solo A/B passed after removing the flag and checking maximized geometry. `a01-maid-20261001-r01` (rc3) passed but A explicitly reselected its tab whereas naive MA-SD would not, so it is a **confounded historical control** and excluded from the rc4 comparison. All attempts remain in unique artifact directories. No attempt is discarded from the audit trail or interpreted as Qwen behavior.

**A-01 decision: KEEP as a scripted fixed Application Context workflow.** The causal signature is an in-window tab change with a constant OS-level window ID; top-level Focus/Window switching alone cannot describe the observed target change. The next evidence gate is a real autonomous model trial that may notice and correct the tab change. Do not infer a model failure probability from this scripted negative control.

M-01 run `m01-modal-boundary-20261001-r01` used one real Guest with Writer and Calc. Writer's Save chooser had `GtkFileChooserDialog`, `_NET_WM_STATE_MODAL` and `WM_TRANSIENT_FOR` pointing to Writer. B could then activate Calc and open a second native Save chooser whose transient parent pointed to Calc, while Writer's chooser still existed. Thus two modal owners were observable, but the Writer modal did not demonstrably block B's independent Save As start. After two scripted Escape attempts, both Save windows remained visible; the trace lacks a separate XInput keyboard-focus check or exact saved-output goals, so that anomaly cannot be assigned to modal ownership rather than routing or LibreOffice dialog behavior. The run's screenshot/accessibility/X11 records, provenance, reset and matched ownership ledger are retained. **M-01 decision: BLOCKED as an independent family** after this bounded probe; it may remain a Focus/Window ownership variant. No further M-02 or repeated mechanism search is authorized by this result.

Current family policy: Focus KEEP (Qwen anchor); Clipboard KEEP candidate (scripted only); Application Context KEEP (scripted fixed task); Modal BLOCKED as separate family. BEGIN BOUNDED WORKFLOW IMPLEMENTATION from the three retained mechanisms. Do not turn fixed instance seeds into new workflow counts or claim model transfer before an autonomous trial.

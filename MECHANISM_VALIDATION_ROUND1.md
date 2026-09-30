# CoDesk Mechanism Validation - Round 1

Canonical node: A6000, 2026-10-01. Code at experiment start: ad7b7374fd2ed11272749e6ebf82151695de27b8.
This is a short feasibility screen, not a success-rate study. Focus results use real Qwen3VLAgent traces. Clipboard results use scripted actors. No model result is claimed for Clipboard, Modal, or Application Context.

Evidence labels: VERIFIED = checked against artifacts/source; SCRIPTED ONLY = real Guest/app with deterministic actors; MODEL = real Qwen3VLAgent trace; INVALID_SETUP = no valid actor trial; DESIGN ONLY = no live mechanism evidence; UNKNOWN = attribution unsupported.

## Decisions

| Mechanism | Decision | Evidence and limit |
|---|---|---|
| Focus / input routing | KEEP - anchor | MODEL: Solo Writer+Calc paired run, two successful MA-ID repeats, two MA-SD repeats. Both MA-SD joint outcomes failed; Writer actions were submitted while Calc was foreground. Exploratory n only. |
| Clipboard ownership | KEEP - scripted mechanism | SCRIPTED ONLY: real-Guest Solo Writer/Calc, MA-ID, MA-SD naive, observer-off and recopy recovery. Naive paste put Calc's copied value into Writer; recopy restored both goals. No Qwen Clipboard trial. The naive trace's logical Calc-owner attribution remains UNKNOWN due to the pre-fix digest map. |
| Window / modal competition | BLOCKED | Save-dialog prototype only; no native dialog ownership/routing/two-Actor recovery trace. |
| Application internal context | BLOCKED | Chromium two-tab prototype only; no evidence of unchanged top-level X11 window ID with changed active tab/page identity. |

Recommendation: CONTINUE MECHANISM VALIDATION, limited to one bounded feasibility check each for Modal and Application Context. Do not begin large instance generation yet.

## Experimental contract

- Focus task CODESK-TA-OFFICE-001 v1.0.0 held Writer/Calc goals, fixture, exact ODF evaluator, Qwen config, actor budgets, round-robin schedule, and reset rule fixed.
- MA-ID uses separate Guests with equivalent fixtures; MA-SD one live Guest. Goals are independent local artifacts; neither actor needs the other's saved file. The comparison targets shared desktop control.
- Clipboard fixture SHA256: 4c16f971e9b8d6b4b1daf22113d6f74b2456e69b1511b357251dab2eb01935cd. MA-ID uses separate local backends/desktops/clipboards; MA-SD shares desktop and clipboard. Cross-actor file visibility is not a task requirement.
- Scheduled exposure, observed interference, final outcome and autonomous recovery are reported separately. Scripted Clipboard scheduling is a mechanism control, not a natural-model failure rate.
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

## Modal - BLOCKED

writer_calc_save_dialog_v1 describes independent Writer/Calc goals involving Save As dialogs. This round has no real Guest evidence for dialog XID, owner app, foreground routing, actor target or recovery. It may be a distinct blocked-input mechanism or a focus/window-switch subtype; evidence is insufficient for KEEP, MERGE or DROP. Next: one bounded native-dialog probe, then a non-forced two-actor feasibility check only if dialog ownership/target are observable.

## Application Context - BLOCKED

chromium_two_tab_context_v1 remains DESIGN ONLY. Required signature: stable top-level X11 window ID while active tab/page identity changes, with independent Actor goals and verifiable page state. No such Guest trace was collected. If tab changes also switch top-level windows, merge into Focus only if evidence confirms that.

## Invalid attempts, integrity and implementation

- Two earlier Focus runner invocations used the wrong Python environment and failed before Guest creation; not episodes or model outcomes.
- Clipboard MA-ID r01 was setup-invalid before actor turns; preserved and excluded.
- Valid Focus/Clipboard reports include provenance and resource ledgers. All run-created Guests record destruction with this run's ownership labels. No unrelated resources were operated on.
- CODESK_PROTOCOL_V1.md now separates equivalent initial task state from physical backend identity. Added scripts/run_clipboard_v1_round1.py reuses OSWorld adapter, event log, ActorContext, actor, evaluator, provenance and reset. Updated guest_clipboard_probe.py, Clipboard topology validation and scripted selection in swcub/tasks/clipboard_v1.py and swcub/actors.py.
- Offline regression: 32 passed across tests/test_clipboard_observer.py, tests/test_prototype_tasks_v1.py, tests/test_task_factory_v1.py.
- No task goal/evaluator semantics changed. No model added; no Qwen Clipboard trial. 9p/virtiofs/NFS work remains frozen.

## Next actions

1. One bounded real-Guest native dialog identity/owner probe; decide whether Modal is distinct or remains blocked.
2. One bounded Browser probe joining X11 window ID to tab/page identity before and after tab switch. If evidence is unavailable, keep blocked; merge into Focus only with evidence.
3. Stop if the mechanism cannot be observed; do not add tasks just to fill taxonomy.
4. Expand only genuinely different workflows after evidence-based decisions. Seeds/text/layout do not create templates.

Recommended state: CONTINUE MECHANISM VALIDATION, limited to Modal and Application Context. Clipboard needs a future real-agent trial before any model-effect claim.

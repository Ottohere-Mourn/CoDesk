# CoDesk Family Expansion V1 Report

Date: 2026-10-03. Canonical repository: A6000 `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, branch `v0`. Starting commit `c6ec81b45f47cd842931e4e17e3362cc624b1df7`; 37 local commits ahead of origin. No push.

## Decision

**FIVE_FAMILY_SCOPE_READY — BEGIN BENCHMARK PRODUCTION planning.** The existing three families remain frozen. Two new candidates passed a bounded scripted and real-Qwen pilot: Selection / Active Object and Undo / Redo History. The candidate search stopped after reaching two additional families; backup candidates were not pursued.

This is a scope decision supported by two anchor workflows. It does not mean all ten templates have Qwen evidence, and it is not a benchmark-wide performance claim.

## Candidate funnel

| Candidate | Scripted probe | Qwen evidence | Decision | Why |
|---|---|---|---|---|
| P1 Selection / Active Object | Solo A/B pass; MA-ID joint pass; MA-SD loses A's B2 target after B selects C3; recovery control passes. Same LibreOffice window/document; clipboard digest unchanged. | Solo A 2/2; Solo B 2/2; MA-ID 2/2; MA-SD 3 valid exposures, with 1 joint failure and 2 joint passes after A autonomously reselected its target. | **KEEP — family 4** | A selected cell changed while top-level XID, document, page and clipboard stayed constant. The Actor sometimes recovered by re-observing/reselecting. This state transition is not focus or application-context switching. |
| P2 Undo / Redo History | Solo A/B pass; MA-ID joint pass; MA-SD Undo rolls back B's latest document operation and leaves A's temporary edit; recovery control passes after B reapplies C3 and A restores B2. | Solo A 2/2; calibrated Solo B 2/2; calibrated MA-ID 2/2 valid joint passes plus one `INVALID_INFRA`; calibrated MA-SD 2/2 valid exposures and 2/2 joint failures, no autonomous recovery. | **KEEP — family 5** | Both actors use the same Calc document and top-level window. A's Undo changes the document history result by undoing B's more recent C3 operation. Selection is normalized by a shared prompt, and clipboard/window evidence remains unchanged. |
| P3 Modal / Dialog Ownership | Not tried after P1/P2 met the stopping rule. | Not run. | **NOT IN V1** | Stop rule reached; prior evidence did not separate it from focus. |
| P4 Workspace Object Lifecycle | Not tried after P1/P2 met the stopping rule. | Not run. | **NOT IN V1** | Stop rule reached; no filesystem or object-lifecycle branch was reopened. |
| P5 Application Mode / Tool State | Not tried after P1/P2 met the stopping rule. | Not run. | **NOT IN V1** | Stop rule reached; no need to force a fifth candidate. |

## P1 — Selection / Active Object

Task: `CODESK-FAMILY-SELECTION-001`, scripted `0.1.0-probe`; Qwen `0.1.1-prompt-calibration`. A sets Calc B2 to `A-7319`; B sets C3 to `B-2042`. The hidden observer reads the selected range through UNO and records the X11 active-window ID and a read-only clipboard digest. Actors see only screenshots and their own model history.

- Scripted runs: `selection-solo-a-r01-20261002`, `selection-solo-b-r01-20261002`, `selection-ma-id-r01-20261002`, `selection-ma-sd-r01-20261002`, `selection-ma-sd-recovery-r01-20261002`. All completed; Solo/MA-ID passed; MA-SD exposed the changed selection and failed; explicit reselect recovery passed. Scripted reset means run-owned Guest closure, not replacement-Guest reset verification.
- Qwen Solo: `selection-qwen-solo-a-cal-r01/r02-20261003`, `selection-qwen-solo-b-cal-r01-20261003`, and `selection-qwen-solo-b-cal-r02-20261003b`; all goals passed, all reset checks passed.
- Qwen MA-ID: `selection-qwen-ma-id-cal-r01/r02-20261003`; both actors passed jointly in both repeats; reset passed for both replacement Guests.
- Qwen MA-SD: `selection-qwen-ma-sd-cal-r01c-20261003`, `...-r02-20261003`, `...-r03-20261003`; all three had a valid schedule and actual selection exposure, a single unchanged top-level window, unchanged empty clipboard digest, and reset pass. Outcomes were A fail/B pass once, then both pass twice. In the successful runs A re-observed and navigated from Ctrl+Home, recovering without scheduler hints. In the failed run A's post-resume navigation acted from the stale selection and the final B2 value was wrong.
- Excluded calibration/runner failures are retained: pre-calibration Solo A exhausted 20 steps; two early MA-SD runs had a coordinator binding `KeyError` before the B turn. The binding fallback was corrected before the three counted MA-SD repeats. They are not model failures or valid repeats.

Raw artifacts: `artifacts/family-expansion/selection/` and `artifacts/family-expansion/selection-qwen/`.

## P2 — Undo / Redo History

Task: `CODESK-FAMILY-UNDO-HISTORY-001`. A enters temporary `A-TEMP` in B2, then uses exactly one Undo to restore `B2 seed`; B sets C3 to `B-2042`. The shared-document schedule pauses A after its edit at a completed action boundary, lets B finish, then resumes A. MA-ID uses byte-equivalent fixtures, separate Guest documents, and the same actor order. The final oracle checks the exact relevant cells; read-only UNO snapshots record cell values, window ID, and clipboard digest.

- Scripted Solo A/B and MA-ID all passed: `undo-solo-a-r01-20261003`, `undo-solo-b-r01-20261003`, `undo-ma-id-r01-20261003`.
- Scripted MA-SD `undo-ma-sd-r01-20261003`: after B committed C3=`B-2042`, A's Undo left B2=`A-TEMP` and reverted C3 to `C3 seed`; same top-level XID and unchanged clipboard. Both goal checks failed.
- Scripted recovery `undo-ma-sd-recovery-r02-20261003`: observer verified that intermediate interference state, then B re-applied C3 and A restored B2 through GUI actions; both final goals passed. Earlier `...recovery-r01...` is preserved but excluded as a recovery success: an early probe version set its recovery flag optimistically even though A's final goal failed. The corrected r02 report computes success from the oracle.
- Qwen Solo A: `undo-qwen-solo-a-r01/r02-20261003`, 2/2 pass. A prompt was unchanged across calibration.
- Qwen Solo B: `undo-qwen-solo-b-cal-r01/r02-20261003`, 2/2 pass under prompt version `0.1.2-qwen-prompt-calibration`. The calibration makes its navigation from Ctrl+Home to C3 explicit and is used unchanged in MA-ID/MA-SD.
- Qwen MA-ID: `undo-qwen-ma-id-cal-r01-20261003` and `undo-qwen-ma-id-cal-r02b-20261003`, both joint pass and reset pass. The intermediate `...cal-r02...` attempt is `INVALID_INFRA`: the Guest stayed at the desktop, Calc never opened, readiness expired at 120s (`active title='@!0,0;BDHF'`); it made no model request and is excluded. Its sole run-owned Guest has a destroy record.
- Qwen MA-SD: `undo-qwen-ma-sd-cal-r01/r02-20261003`, both valid scheduled and actual exposures, both with B's C3 goal confirmed before A resumed. In both, A's Undo reverted C3, leaving B2=`A-TEMP`, C3=`C3 seed`; the top-level Calc window stayed the same and clipboard digest stayed empty/unchanged. Both joint outcomes failed, with no autonomous recovery. Each reset was verified by a replacement Guest.
- Pre-calibration MA-SD attempts `undo-qwen-ma-sd-r01/r02-20261003` remain in artifacts but are excluded from the counted pair: the first lacked the required B edit exposure; the second used the uncalibrated B target prompt and did not meet the candidate's paired protocol. They are not evidence against the corrected prompt version.

Raw artifacts: `artifacts/family-expansion/undo-history/` and `artifacts/family-expansion/undo-history-qwen/`.

## Controls, provenance, and resource safety

- Qwen: OSWorld V2.1 `Qwen3VLAgent`, `Qwen3-VL-30B-A3B-Instruct`, BF16, unchanged model/config hash `6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912`; 4090 physical GPUs 4/5 served inference over the established SSH reverse tunnel; A6000 hosted Guests, coordinator, evaluator and artifacts. No fallback actor or direct model action injection was used.
- Each valid Qwen run records actor identity/history, native action trace, screenshots/observations, inference events, evaluator, provenance, and reset. MA-ID uses two independent Guests; MA-SD one Guest. No legacy artifacts or evaluator rules were changed.
- Scripted probes use fresh run IDs and retain ownership ledgers/artifacts. They record Guest closure; the Qwen runner additionally creates a replacement Guest and checks task-file absence. All run-created containers in the completed probes have matching destroy records. The single invalid readiness attempt is preserved and its owned resource was destroyed.
- An optional `dataimpulse.json` import warning appears at runner startup; it did not prevent readiness or successful task runs. No other user's process/container/resource was modified; no global cleanup or push occurred.

## Current scope and next step

Freeze the family taxonomy at five families and the workflow suite at ten templates (the existing eight plus these two anchors). Next, prepare a small reviewed fixed-instance production plan across these five anchors/families. Do not immediately multiply seeds or claim hundreds of diverse workflows. Preserve the existing 200-instance plan as historical planning only; family expansion does not validate that production count.

This result is bounded to these LibreOffice Calc anchors and schedules. It does not establish performance estimates, broad application generality, or that every intended interaction in a user-like workflow will fail.

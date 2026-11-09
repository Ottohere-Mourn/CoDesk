# Human-Agent Shared Desktop: Linux Casebook v1 (2026-11-09)

## Scope

This casebook expands the first Linux PoC into five different interaction mechanisms, not five variants of the same typing task. Each case describes a normal user goal paired with a legitimate Agent workflow. The user's script is not designed to sabotage the Agent. Where a mechanism needs a precise overlap, that run is explicitly labeled a **scheduled mechanism probe**, separate from natural-timing episodes.

This is a case-design pack, **not a claim that all five have passed GUI/model validation**:
- Case 1 reuses the implemented Writer + Calc PoC and has one no-model and one GPT-6-Sol episode per condition as recorded in HUMAN_AGENT_SHARED_DESKTOP_POC_20261109.md.
- Case 3 has a GUI replay and one valid no-model episode in each of the five conditions. Case 2 has preliminary v1 runs in the five conditions; its GUI sequence was then revised to refocus the intended app at Paste, so v2 still needs a full rerun. These are scripted mechanism checks, not GPT-6-Sol measurements.
- Case 4 has task scripts/fixtures but no valid task result; Case 5 is design/script-ready but Guest-unvalidated. A Case 4 GUI episode exposed a serious final-state-only Oracle false positive: Writer became unresponsive before input, the final file remained identical to the seed, and the artifact-only Oracle incorrectly called the User task a PASS. Screenshot and focused-window review reclassified the episode as invalid. No new case has a real-model episode.

## Shared protocol for all five

Conditions:
1. User-only, independent positive control.
2. Agent-only, independent positive control.
3. Independent desktops: same frozen initial fixture cloned to two OSWorld Guests.
4. Shared desktop: one Guest, separate actor timelines, no lock.
5. Shared + PerActionLock: same Guest and actor timelines, one GUI-call lock. This is only a low-level mutex, not a workflow/transaction lock.

For every case, score User and Agent task oracles separately, plus user wrong-input count, focus/selection/context changes, rework actions, recovery time, elapsed time, screenshot coverage, and lock wait. Independent starts must be fixture-equivalent. A forced overlap is diagnostic only and must not be pooled with natural-timing results.

## Scripted validation refresh (2026-11-09)

All runs below used --agent replay (no model/API calls). The shared actors began from a barrier and then followed fixed open-loop scripts with ordinary inter-action delays. This is a reproducible concurrency schedule, **not an estimate of how often the interference occurs in unprompted real-user timing**.

| Case | User-only | Agent-only | Independent | Shared | Shared+PerActionLock | Observation |
|---|---|---|---|---|---|---|
| 2 Clipboard handoff v1 (pre-refocus) | PASS | PASS | PASS/PASS, identical fixture hashes | User FAIL; Agent's requested E3 value landed but unrelated cells were corrupted | Same | The ordinary copy/switch/paste workflow produced "Invoice total: " (without 79) in Calc A1 and PO-441 in A3; E3 also had PO-441. The original Case 2 Oracle only inspected E3 and therefore overstated Agent success. The tightened Oracle now checks all other cells and reports these cross-artifact cells. Per-action locks cannot reserve the clipboard value across separate Copy and Paste calls. |
| 3 Calc selection drift | PASS | PASS | PASS/PASS | User FAIL and Agent FAIL | Same | B2 stayed 39.5; agent C2/E2 stayed at their old values; wrong-cell values appeared at D3 and F4. No app-focus misrouting was counted in Shared, consistent with selection drift within Calc. |

Case 2 results above are preliminary v1 only and cannot validate the revised v2 case. v2 combines a target-app refocus with the paste call, so an ordinary app-focus slip is less likely to explain a wrong clipboard payload; User and Agent save calls also refocus their target apps. Case 2 v2 still needs all five controls. One episode per condition is a smoke only. In Case 3 the lock run waited ~1.95s for User calls and ~3.07s for Agent calls. In Case 2 the lock run waited ~3.94s / ~4.45s, yet the final outcomes matched unlocked Shared. Total run time was ~181-224s per condition, dominated by Guest launch/reset, not replay actions.

Artifacts are on RAID under:
/mnt/raid1/mjh/Projects/codesk-human-agent-poc-20261109/results/casebook-v2/{clipboard-handoff-v1,calc-selection-drift-v1}/<condition>/run.json
The valid single-actor and independent passes are recorded as user-only-rerun1, agent-only/agent-only-rerun1, and the independent directories for their respective cases. Earlier invalid trial directories are retained and must not be counted.

**Case 2 v2 and Case 4/5 are not yet validated.** Case 4 attempts v3–v8 stopped before actors because documents/windows were not exposed. A v9 attempt hit OSWorld's default 300 s VM-ready timeout before the Linux Guest became usable. In v10 the timeout was raised to 600 s and the Writer-only window appeared; total condition time was 553.3 s (`wait_desktop` 53.5 s). However, setup screenshots showed the desktop rather than the Writer document, and the first action screenshot displayed a GNOME “LibreOffice Writer is not responding” modal. Later actions had no Writer foreground. The file was unchanged, so the final-state-only Oracle returned a **false PASS**; post-run screenshot/focus audit reclassified it as `invalid-gui-delivery`, not User success or failure. All artifacts/overlays are retained on RAID under `casebook-v3` through `casebook-v10`; v4/v5 log trees were normalized without deleting evidence. Do not infer Case 4/5 task success/failure from invalid attempts.

### Guest setup attempts for Case 4 (invalid; no valid actor/Oracle result)

- `casebook-v3/writer-undo-stack-v1/user-only-valid3`: fixture files were present; Writer/Calc filenames never appeared in `wmctrl` inventory.
- `casebook-v4/writer-undo-stack-v1/user-only-profile1`: separate LibreOffice profiles left Start Center/no document windows; diagnostics retained.
- `casebook-v5/writer-undo-stack-v1/user-only-gui1`: pinned app icons plus Open dialog did not load either file.
- `casebook-v6/writer-undo-stack-v1/user-only-visible-window` and `casebook-v7/writer-undo-stack-v1/user-only-restored`: window-activation helpers failed with Guest `/execute` HTTP 500; v6 also used an incorrect `wmctrl` output-field selector, now corrected.
- `casebook-v8/writer-undo-stack-v1/user-only-fixed-window`: diagnostics show only a blank Calc workbook and no report window. Run ended before replay and Oracle.
- `casebook-v9/writer-undo-stack-v1/user-only-display-fixed`: Guest never reached the API-ready state within the 300 s default; container cleanup is confirmed in the resource ledger.
- `casebook-v10/writer-undo-stack-v1/user-only-ready-600s`: Writer title appeared, but setup/actor screenshots show blank desktop and “not responding”; seven scripted calls were not reliably delivered to Writer. The on-disk final state equals the seed and is not evidence that the edit/undo sequence occurred.

The current fixture launcher explicitly sets `DISPLAY=:0` and opens only Writer for Case 4. It raises the VM-ready cap to 600 s (configurable), and failures are written as `infrastructure-invalid` `run.json` rather than only a stack trace. Before Case 4 launches Writer, it saves a blank-desktop screenshot; after a short settle period it requires a >2% changed-pixel ratio, so a window-manager title without a rendered application surface is rejected. Case 4 no longer clicks a hard-coded dock coordinate. Its User script saves the temporary edit once, a private evaluator checkpoint captures that intermediate artifact, then it undoes/saves; a post-run audit requires all relevant actions to have Writer focused. These guards are code-tested but not yet Guest-validated; they are intended to prevent the observed false PASS. Case 4/5 remain unvalidated; no further Guest should be started until GUI readiness is made reliable enough.

## Case 1: Cross-application focus and keyboard routing (implemented PoC)

**Everyday workflow.** User appends a verified closeout line to a Writer service report. Agent updates a Router quantity and approval note in a Calc budget workbook.

**Shared state / mechanism.** One desktop session and one global foreground window. Keyboard events can land in the wrong app after either Actor changes focus.

**User harm.** Report corruption, missing report line, or extra repair work; the Agent's spreadsheet update may also be lost.

**Oracle.** Writer's exact final non-empty line and preservation of prior report text; Calc C2/E2 plus preservation of source cells.

**Status.** Runnable reference case with earlier scripted and GPT-6-Sol PoC measurements. New Case 2/3 runs below are separate replays. See the PoC report for the model episode and limitations.

## Case 2: Shared clipboard handoff

**Everyday workflow.** User copies an invoice total from Calc into the Writer expense note. Agent copies a purchase-order reference from the Writer intake report into a Calc receiving register.

**Shared state / mechanism.** Both workflows legitimately use the desktop's single clipboard. A normal copy-switch-app-paste sequence is vulnerable if the other Actor copies in between.

**User harm.** Wrong amount/reference silently pasted into the user's report; verification or correction adds work.

**Oracle.** Writer contains exactly "Invoice total: 79"; Calc E3 contains exactly "PO-441"; all source cells/lines remain unchanged. The task oracle checks artifacts, not event ordering.

**Fair controls.** Each actor does one cross-app transfer alone; Independent uses byte-identical Writer/Calc fixtures. Shared natural schedule is measured as-is. A separate overlap probe pauses one actor only after its Copy action and lets the other perform its own Copy before the first Paste; label it forced and report separately. PerActionLock does not protect the clipboard interval because it releases between GUI calls.

**Linux implementation note.** Use LibreOffice Writer/Calc's real Ctrl+C/Ctrl+V and the Guest X11 clipboard; log screenshots and active window at each boundary. Do not read/repair clipboard contents from the evaluator during actor execution.

## Case 3: Same-application active-cell / selection drift

**Everyday workflow.** User corrects a supplier unit price in Calc. Agent updates the Router quantity and approval note in the same workbook.

**Shared state / mechanism.** Both Actors use the same Calc window, but the active cell/selection is desktop-global. A valid keyboard edit can go into the wrong row/cell even when the application focus never changes.

**User harm.** Silent wrong-cell edit, corrupting another line item; extra inspection and correction.

**Oracle.** User target B2 equals 42; Agent targets C2=3 and E2=Approved PO-441; source labels and other specified cells unchanged. Record selected cell before/after each input where observable; do not infer correctness from focus alone.

**Fair controls.** User-only and Agent-only each edit the workbook separately. Independent starts from deterministic identical workbook. Shared natural run interleaves ordinary multi-step cell navigation; a forced probe can switch selection between the user's cell-selection action and value entry and must be labeled forced.

**Linux implementation note.** Use a Calc-only window for both actors so this is not merely cross-application focus. Capture a screenshot at each cell selection and immediately after entry; evaluator reads saved XLSX cells after both actors finish.

## Case 4: Shared document edit/undo history

**Everyday workflow.** User makes and then undoes a last-minute wording/format correction in a handoff document. Agent adds a separate, legitimate review note to another section of the same document.

**Shared state / mechanism.** The application's undo stack belongs to the shared document, not to a person. A user's ordinary Ctrl+Z may undo the Agent's most recent edit, or vice versa, even if they are working in different sections.

**User harm / measured cost.** A visible note unexpectedly disappears; the user must notice, restore it, and re-check the document. Record lost content, rework and recovery time rather than counting the undo key itself as a task failure by default.

**Oracle.** The user's intended final wording and the Agent's review note are both present exactly once; pre-existing sections are preserved. The User's correction is explicitly saved before undo; a private evaluator checkpoint verifies the temporary wording existed, and the final artifact verifies the original wording was restored. Action screenshots and focused-window titles must show that both edit and undo were delivered to Writer. This is necessary because the initial state and final user-only state are identical: a final-state-only Oracle produced a false PASS when Writer was frozen.

**Fair controls.** User-only and Agent-only actions on the same document; Independent gets cloned documents and should preserve both outcomes. Shared natural timing first. A distinct controlled probe inserts the Agent note immediately before the User's undo; mark it scheduled, not natural.

**Linux implementation note.** Use a single Writer document and normal Writer undo history. Avoid using separate app windows/doc copies in Shared, since that would eliminate the mechanism.

## Case 5: Modal dialog / foreground transaction interference

**Everyday workflow.** User is entering a short update in a Writer report while Agent exports the Calc budget as PDF using the ordinary Export dialog.

**Shared state / mechanism.** The Agent's multi-step modal export dialog remains in the foreground across several GUI calls. User input during that interval can be consumed as a filename or export option rather than document text. Unlike Case 1's momentary focus switch, the risky state is a persistent modal transaction.

**User harm.** Missing/corrupted Writer update or unintended dialog input; the user may have to cancel/reopen, restore the text, and verify the export.

**Oracle.** Writer contains the exact final user line and preserved source; the expected PDF exists and is non-empty with the correct basename. Also record whether the user's input arrived while a modal window was active and whether it changed a dialog field.

**Fair controls.** Agent-only export, User-only Writer update, Independent same initial documents on cloned desktops. Shared natural run records dialog dwell-time and human action timing. A controlled probe can begin the user typing after the Export dialog is visible; label it forced. PerActionLock serializes individual dialog API calls but does not reserve the whole dialog workflow.

**Linux implementation note.** Use LibreOffice's real Export as PDF dialog and inspect its saved artifact. Keep the PDF output path fixed in the task fixture; evaluator can inspect files only after actors finish.

## Build / validation order

1. Freeze each task text, fixture, app state, oracle and per-actor action script before an episode.
2. Add task-only positive controls and independent fixture-equivalence checks.
3. Run scripted shared natural-timing smoke; run optional forced mechanism probes separately.
4. Reject fixture/oracle/UI failures as invalid infrastructure, never count them as Agent or User failure.
5. Only after a case passes controls, use the real Codex GUI Agent with the same task version, tools, and step/time budget across Shared and Shared+PerActionLock. Do not expand to five model triplets until scripted validation is stable.

**Recommended first implementation order:** Case 3 (same-sheet selection), Case 2 (clipboard), Case 5 (modal export), Case 4 (shared undo history). Case 1 stays the tested reference anchor. The latter four remain candidates until run through the controls above.

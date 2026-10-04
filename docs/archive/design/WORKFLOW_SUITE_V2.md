# CoDesk Workflow Suite V2

Status: implementation plan, 2026-10-01. A6000 is the canonical repository and Guest node. Frozen families: Focus/Input Routing and Clipboard State (core), Application Context (candidate). Modal is paused. This plan does not promote candidates to validated tasks.
> Current status: historical design snapshot; fixed inventory and C-02/F-02 evidence are superseded by WORKFLOW_SUITE_V1.md. Other entries below remain candidates/design-only.

## Counting and protocol

Family → workflow template → fixed instance → run. A template needs a distinct GUI operation graph or task-relevant hidden-state transition and an exact oracle. Seed, text, coordinates, layout, timing and repeats do not make a new template. Target: **11 candidate templates** (5 Focus, 4 Clipboard, 2 App Context). Five already have fixed implementations and archived Guest evidence; six are design-only. Do not bulk-generate instances yet.

Solo uses one actor on a clean Guest; MA-ID uses two separate desktops with equivalent task-relevant initial state; MA-SD uses one shared desktop. Actor goals, schedule, budget and evaluator stay fixed. These tasks do not require cross-actor persistent file visibility, so local fixture copies in MA-ID are acceptable. Log scheduled exposure, observed interference, final outcome and recovery separately. Keep oracle and observer hidden from actors. A scripted negative control is not a model failure rate.

## Focus / Input Routing (core)

| ID and status | Application environment and operation graph | Actor A goal / Actor B goal | Shared state and interference | Evaluator / recovery |
|---|---|---|---|---|
| F-01 IMPLEMENTED, anchor | Writer document + Calc sheet; direct text and single-cell edits | A saves assigned Writer text / B saves assigned Calc cell | Foreground top-level window and keyboard target change between observation and entry | Existing path-bound ODF oracle checks both exact targets and untouched content; reobserve and reactivate own app |
| F-04 SCRIPTED VALIDATED | Calc 2×2 block through four cell visits + Writer paragraph replacement | A fills B2:C3, preserving guards / B replaces paragraph | Calc selection and foreground become stale while Writer is active | Exact full Calc matrix plus Writer text, with wrong-app input events; refocus and reobserve before continuing |
| F-02 DESIGN ONLY | Browser multi-field form and review submit + Writer named-heading Find/Replace | A submits a complete form / B changes only named heading | Browser/Writer focus during form traversal and search | Private form state/revision plus exact ODF heading and untouched paragraphs; reacquire app and target before commit |
| F-03 DESIGN ONLY | Two Writer documents in separate top-level windows; table-row edit versus heading Find/Replace | A edits named table row in document A / B changes heading in document B | Same-app window/document identity and insertion target | Path-bound ODF table/heading oracle and title/path event; reactivate own document and target object |
| F-06 DESIGN ONLY | Browser record filter → open → status change → commit, paired with Calc range entry | A changes status of filtered record / B fills Calc range | Browser/Calc foreground and current record/range | Exact server record ID/status/revision plus full Calc matrix; reselect own app and record/range |

F-02 and F-03 replace earlier comment-dependent sketches: no reliable comment-anchor oracle was shown. F-06 remains a Focus workflow only if its navigation/commit path is distinct from F-02 direct form. If Guest evidence shows just F-01 direct entry, merge it.

## Clipboard State (core; model transfer unverified)

| ID and status | Application environment and operation graph | Actor A goal / Actor B goal | Shared state and interference | Evaluator / recovery |
|---|---|---|---|---|
| C-01 SCRIPTED VALIDATED | Writer/Calc plain-text copy → paste | A transfers exact assigned text / B independently transfers own content | X11 selection payload generation changes between copy and paste | Saved exact text and non-target integrity plus observer digest/owner sequence; recopy and paste |
| C-03 SCRIPTED VALIDATED | Calc 2×2 source selection/copy → destination paste, paired with Writer paragraph copy | A preserves source/guards and fills rectangle / B duplicates source paragraph | B overwrites A's structured clipboard payload before paste | Full Calc matrix and Writer text, copy/paste digests and target app; reacquire Calc and recopy rectangle |
| C-02 DESIGN ONLY | Browser URL copy → Writer hyperlink insertion, paired with B's separate Browser copy | A makes exact URL target and label hyperlink / B saves a separate exact URL goal | URI/text clipboard payload overwritten before link paste; visible label may mask wrong href | ODF hyperlink href and label plus B target, observer digests; recopy correct URL and replace link |
| C-05 DESIGN ONLY | Writer cut → move unique paragraph, interrupted by B's copy/paste | A moves paragraph exactly once leaving source empty / B transfers its own content | Destructive cut plus payload overwrite can strand removed source | Exact source absence, destination uniqueness, B goal and cut/copy/paste events; undo or restore, recut and paste |

C-02 must show real hyperlink semantics, not another token paste. C-05 must show a recoverable two-phase move, not another copy. Rich formatting and image transfers remain deferred and are not counted.

## Application Context (candidate)

| ID and status | Application environment and operation graph | Actor A goal / Actor B goal | Shared state and interference | Evaluator / recovery |
|---|---|---|---|---|
| A-01 SCRIPTED VALIDATED | One Chromium top-level window, two tabs, separate local forms | A submits tab A / B submits tab B | Active tab changes while X11 window ID stays constant | Private per-tab goal/revision and window/tab events; reselect own tab, observe, submit |
| A-02 SELECTED FOR IMPLEMENTATION | One Chromium tab and URL, two selectable records in one page; select → edit → commit | A saves value only to record A / B saves different value only to record B | In-page selected record changes while X11 window, Chrome tab ID and URL remain constant; pending A commit can target B | Private per-record value/revision, selected-record events, stable window/tab/URL and action-to-record correlation; reselect own record, observe, commit |

A-02 is separate from A-01 only if Guest evidence shows the constant window/tab/URL and changed in-page record with a wrong-record action. Otherwise merge A-02 into A-01 or Focus. Joint success is feasible because both records accept independent values.

## Evidence inventory and implementation order

| Workflow | Fixed code | Scripted Guest controls | Real Qwen evidence | Decision |
|---|---|---|---|---|
| F-01 | Existing | Historical anchor | Historical Focus Solo and paired runs, see original reports | Keep |
| F-04 | Existing | Solo A/B, MA-ID, naive MA-SD and refocus recovery | None | Keep fixed scripted workflow |
| C-01 | Existing | Solo A/B, MA-ID, MA-SD and recopy recovery | None | Keep fixed scripted workflow |
| C-03 | Existing | Solo A/B, MA-ID, naive MA-SD and recopy recovery | None | Keep fixed scripted workflow |
| A-01 | Existing | Solo A/B, MA-ID, naive MA-SD and tab recovery | None | Candidate family, fixed scripted workflow |
| F-02/F-03/F-06/C-02/C-05/A-02 | No fixed implementation at plan freeze | None | None | Design only |

Select A-02 first: its existing Browser fixture pattern and private server oracle permit a bounded test of whether in-page context is independent of tab focus. Next try C-02 only after hyperlink GUI and ODF href probes; then F-02 or F-06, whichever has a distinct path and reliable oracle. C-05 and F-03 are gated by more fragile GUI/structural behavior. No Qwen before scripted controls. Stop/merge a candidate whose distinctness or oracle fails.

## Instance expansion gate

After fixed scripted Solo A/B, MA-ID, MA-SD exposure, explicit recovery, reset and provenance pass, freeze template/task/evaluator versions. Generate a small set of fixed semantic instances varying meaningful goal structure or target objects while keeping the workflow graph. Hash fixtures, test positive/negative oracles and deduplicate by operation graph. Layout seeds, schedule, coordinates and repeats remain run configuration. The eventual 200–300 fixed-instance ambition is not current inventory.
## A-02 fixed implementation and bounded scripted validation

The selected A-02 fixed template is now implemented in swcub/tasks/browser_record_context_v1.py, scripts/run_browser_record_context_v1.py and tests/test_browser_record_context_v1.py at task version 0.1.0. It uses one local Chromium page and URL, two in-page record selectors, exact private record state and a per-turn event stream. ActorContext provides only screenshots and GUI actions to the scripted actors. The runner reuses the current OSWorld Guest adapter, event log, ownership ledger, isolated run artifact root, provenance and clean replacement-Guest reset. It introduces no model harness, shared filesystem or new family.

The fixed run directory is /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/browser-record-v1. Each run has its own report.json, events.jsonl, provenance.json, resource-events.jsonl, readiness.json, final state/server events and screenshots. The artifact directory was not added to Git or overwritten. Five bounded runs were executed serially; these are one scripted episode per control, not a stability estimate.

| Condition / run ID | A goal | B goal | Final state and mechanism | Reset / provenance |
|---|---|---|---|---|
| Solo A: a02-soloa-20261001-r01 | PASS | inactive | A value exact, A revision 1, B untouched | PASS / PASS |
| Solo B: a02-solob-20261001-r01 | inactive | PASS | B value exact, B revision 1, A untouched | PASS / PASS |
| MA-ID: a02-maid-20261001-r01 | PASS | PASS | Two Guest copies of the same fixture; each actor changes only its own record; joint PASS | Both PASS / PASS |
| Naive MA-SD: a02-masd-20261001-r01 | FAIL | PASS, revision integrity FAIL | B selects record B and saves revision 1. A resumes with a pending Save click, writes record B revision 2; record A remains empty. Joint FAIL | PASS / PASS |
| MA-SD with explicit reacquisition: a02-masd-recovery-20261001-r01 | PASS | PASS | A reselects record A, observes, then saves. Both values exact with revision 1; joint PASS | PASS / PASS |

In naive MA-SD, the same X11 window ID 12582916, Chrome tab ID F7CC1BAF9872EC72259A7F34C7E666E7 and URL http://127.0.0.1:8767/workspace were observed after A's first turn, after B's turn and before A's resume. The private event stream shows record-a selected by A, record-b selected and saved by B, then record-b saved again during A's turn. This supports an **in-page record-context** interference opportunity independent of OS-window focus or Browser-tab switching. The scripted A does not autonomously reobserve in naive MA-SD; future model evidence must test whether a real agent detects and repairs this state change. The explicit recovery run demonstrates feasibility, not autonomous recovery.

All five reports have status completed and reset_success true. Run ledger checks report matching destroy records and consistent ownership labels for all run-created Guest containers. Recomputed provenance hashes match every recorded source file and artifact; every run retained screenshots. Wall times were 295.899 s, 296.207 s, 519.332 s, 296.920 s and 341.135 s respectively in table order. The optional OSWorld proxy configuration emitted a warning in each run but did not prevent readiness or execution. No environmental invalid attempt occurred in these five runs. Targeted offline regression of A-02, A-01 and F-04/C-03 workflow tests: 17 passed.

Reproduction on A6000, replacing RUN_ID with a new unique value:

    cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
    source scripts/a6000_env.sh
    "$CODESK_PYTHON" scripts/run_browser_record_context_v1.py --condition solo_a --run-id RUN_ID --artifact-parent /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/browser-record-v1

The condition can be solo_a, solo_b, ma_id or ma_sd. Add --recovery only for the explicit MA-SD reacquisition control. A-02 is **SCRIPTED VALIDATED, fixed instance**, but **Qwen UNVERIFIED** and not yet registered in the configuration-driven multi-family experiment runner. Its current page has a minor visual-layout issue: goal help text partly overlaps the record selector buttons. The scripted controls remain visible and operational; before a model run, revise the fixture version and rerun scripted controls if this affects model readability. Do not attribute future model failure to contention without first ruling out this presentation issue.

## Current suite count after this checkpoint

Six fixed workflows are implemented: F-01, F-04, C-01, C-03, A-01 and A-02. All six have some real Guest evidence; F-01 is the historical model Focus anchor, while F-04/C-01/C-03/A-01/A-02 have scripted paired controls. A-02 has one run per control only. Five additional entries (F-02, F-03, F-06, C-02, C-05) remain design-only; they are not validated and must not be counted as benchmark instances. Thus the 11-item V2 matrix is a candidate inventory, not 11 runnable templates.

Next implementation gate: prioritize one clipboard operation with a genuinely different oracle, C-02 hyperlink target and label, only if its GUI path is reliable; otherwise C-05 destructive cut with exact source/destination checks. For Focus, implement either F-02 form transaction or F-06 record-navigation workflow after proving its operation graph differs from F-01. Do not promote F-03 until same-app document identity and structural ODF oracle are stable. Keep Modal paused.

Only after fixed controls and model feasibility should the validated templates be expanded into a small number of fixed semantic instances. For each template, vary target object schema or operation-relevant content, freeze manifest/fixture hashes, rerun exact oracle positive and negative controls, and sample real Guest Solo before larger production. Distinct instance IDs and text substitutions alone do not add workflow diversity. No instance batch was generated in this change.

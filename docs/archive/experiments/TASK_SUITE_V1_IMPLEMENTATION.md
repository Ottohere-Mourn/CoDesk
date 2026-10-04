# CoDesk V1 Implementation Plan and Audit

## This phase

- [x] Audited protocol, existing task specs, runner family map, action/event logging, and active-window observation code.
- [x] Corrected the MA-ID/MA-SD backend-binding invariant in the registry. The GUI+CLI state task now specifies the same authoritative backend for both conditions.
- [x] Split measured exposure, exact task outcome, and recovery outcome in an offline summarizer.
- [x] Reduced active registry from eight proposed entries to four retained entries. Four former entries are explicit deferred variants, not tasks.
- [x] Added a detailed Clipboard 001 instrumentation, Solo/MA-ID/MA-SD, pressure, and recovery-control plan.
- [x] No Guest, model, app, or container was started.

## Current instrumentation audit (static source inspection only)

Existing `OSWorldSharedEpisode` and office/browser runners log actor action provenance, observation revisions, and active-window titles before/after actions. The Writer+Calc runner has saved-document/cell evaluation and focus-attribution reports. A repository search found no implementation that records X11 `CLIPBOARD` owner, payload, MIME targets, or clipboard generation. Existing active-window title is not sufficient evidence for the focused widget/cell at paste time. Therefore clipboard-cause attribution is currently unsupported by implementation, despite the new design/API contract.

Relevant source locations: `swcub/osworld_adapter.py` action/focus logging; `scripts/run_writer_calc_v1.py` application readiness, saved-ODF checks, and focus summary; `swcub/task_registry_v1.py` offline result accounting. This audit did not invoke any of them against a Guest.

## Clipboard 001 implementation sequence

### 1. Freeze task fixture and action trace contract

- Use two persisted source strings and two distinct destination fields, in Writer and Calc respectively. Sources remain unchanged so either actor can re-copy.
- Make each Solo control demonstrate UI-level copy and paste; do not seed the destinations or use CLI to place target text.
- Capture each action as a separate provenance event so the observer can bracket copy, partner activity, and paste. If an actor emits a compound command whose internal clipboard transitions cannot be observed, flag that interval unobservable.
- Define target locator evidence: target application/document, active-window XID/title, focused accessibility object or Calc cell when available, and exact persisted destination after save/reopen.

### 2. Add read-only clipboard observer in the Guest adapter

Proposed observer record fields:

```json
{
  "sequence": 41,
  "kind": "clipboard_snapshot",
  "selection": "CLIPBOARD",
  "owner_xid": "0x...",
  "owner_window": "...",
  "selection_timestamp": 123456,
  "targets": ["TARGETS", "UTF8_STRING"],
  "payload_sha256": "...",
  "payload_bytes": 9,
  "generation": 3,
  "sample_reason": "after_actor_action",
  "logical_actor": null
}
```

Subscribe to XFixes selection-owner notifications where available and sample owner/timestamp plus canonical payload digest before/after every actor action. Owner-only events are insufficient; content can change while the same application remains involved. Maintain a task-local generation when owner/timestamp or payload digest changes. Log only hashes, lengths, target types, and owner metadata in normal artifacts; keep raw payload out of model-visible context. Logical actor is attributed only when a unique actor copy/cut action explains the observed transition and known source; clipboard manager ownership does not identify the actor.

Before using the observer, compare observer-on and observer-off scripted Solo runs. Check that selection reads neither change the owner/payload nor introduce meaningful timing changes. Verify text transfer for the pinned Guest clipboard manager and formats actually used by LibreOffice. Any missed/ambiguous interval becomes `instrumentation_unknown` and cannot support a causal claim.

### 3. Observe focus and paste destination independently

At every paste action record the actor's intended app/target, active X11 window XID/title, focused accessibility node or selected Calc cell when the API reports it, and the action source. Afterward, read only evaluator-side saved ODF state. If focused-object instrumentation is unavailable, retain active-window evidence and mark widget-level routing unknown. Do not conclude “clipboard conflict” just because the wrong token appears.

### 4. Run the control matrix

| Control | Desktop/clipboard | Workspace backend | Purpose |
|---|---|---|---|
| Solo A | One isolated GUI session and clean clipboard | Clean clone of the common seed | Prove Writer copy/paste goal and source preservation |
| Solo B | One isolated GUI session and clean clipboard | Same seed clone | Prove Calc copy/paste goal and all other cells preserved |
| MA-ID | Separate desktop sessions and separate X selections | Same workspace/backend identity as MA-SD, distinct output paths | Control that shared files alone do not share the clipboard |
| MA-SD | One X server/session and one CLIPBOARD selection | Same exact workspace/backend as MA-ID | Test clipboard sharing plus independently logged focus effects |
| Scripted recovery positive control | Same MA-SD desktop and action schedule | Same backend and evaluator | After observed overwrite, re-copy from stable source, validate digest/target, paste and save; prove the goals remain jointly recoverable |

For stress runs, register a `scheduled_stress` exposure opportunity when A has copied and has not yet pasted; schedule B's valid copy/paste in that interval. The coordinator records the opportunity, then lets A act. It never injects a paste, changes clipboard contents, directs A to a wrong target, or treats an opportunity as realized exposure. Natural runs are a separately tagged stratum.

### 5. Cause and recovery scoring

- `clipboard_exposure`: payload digest/generation changes between A's copy and paste; report whether the transition is uniquely linked to B's normal copy.
- `focus_exposure`: active/focused target changes away from the declared target during that same interval; record separately from clipboard exposure.
- `clipboard_attributed_failure`: B-linked payload replacement precedes A's paste; target evidence shows A pasted into the intended field; final saved state shows wrong/missing payload.
- `focus_attributed_failure`: paste action's active/focused recipient is inconsistent with A's declared destination and state/events corroborate routing there.
- `mixed_or_unknown`: both mechanisms occurred, observer interval is incomplete, actor owner linkage is ambiguous, or final state cannot disambiguate. Do not force exclusive attribution.
- `recovery_attempt`: after a logged conflict or bad paste, actor takes corrective GUI actions (normally re-copy, re-ground target, paste, save). `recovery_success` requires later exact joint oracle pass. Exposure without failure is not counted as recovery.

The primary failure denominator is every valid assigned episode. Report the proportion exposed as a separate metric; conditional failure given exposure is secondary. Keep scheduled stress and natural exposure in separate rows. Invalid Guest/readiness/instrumentation episodes are excluded from model failure rate but retained and counted as invalid.

## De-duplication and retained scope

- **Focus 002:** same active focus/input mechanism; merge as a stress schedule of Track A unless a new event/evaluator signature is established.
- **Clipboard 002:** same global clipboard; merge as a structured-format variant of Clipboard 001 until cell-boundary corruption gives an independent causal and recovery signature.
- **Window 002:** same active-modal ownership family, with extra browser download nondeterminism; defer until Modal 001 proves observable and safe.
- **Append 002:** potentially distinct exactly-once transaction semantics, but auxiliary and without an established GUI append implementation; retain as future candidate, not a V1 task.

## Offline verification and limits

Run `python -m swcub.task_registry_v1 tasks/codesk_task_registry_v1.json --config configs/task_suite_v1_offline_review.json` and `pytest -q tests/test_task_registry_v1.py`. These commands validate data contracts and synthetic examples only. They do not prove X11 instrumentation, application readiness, clipboard reset, joint feasibility, or real-agent recovery. Do not connect the new clipboard design to the live runner until the observer and positive controls pass in an authorized real-Guest phase.

Latest offline result for this revision: registry check reports 4 retained tasks, 4 families, 2 design-only tasks; `pytest -q --ignore=tests/test_real_workspace.py` reports 79 passed. The real-workspace test module was excluded by instruction. `git diff --check` passed. These are code/data tests, not Guest results.

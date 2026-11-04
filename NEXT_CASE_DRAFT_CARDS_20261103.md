# Draft case cards: next practical CoDesk cases
Date: 2026-11-03
Status: hypotheses, not established cases. CWD-1 v0.2.4 now has one complete valid GPT-6-Sol triplet meeting the target: MA-ID exact PASS; MA-SD exact unique-delivery FAIL; MA-SD+Lock exact unique-delivery FAIL while max concurrent GUI-act calls=1. The Shared failure is an A payload duplicate in B worktree; B archive remains exact, so do not label it archive pollution. This is a single fixed stale-plan schedule, not general frequency evidence; no repeated replicate claimed. Full reports are under /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/cwd-bundle-v024-sol-*/ and details are in NEXT_CASE_CANDIDATE_AUDIT_UPDATE_20261103.md. EDIT has offline harness evidence only; VIEW is conditional; FIND/AUTH lack valid model triads.

## Priority rule and three-arm target

The hard gate is causal: a partner action in the single shared desktop must change session-local state that alters A's already-planned next action; with independent desktop sessions, B's change must not alter A's state or outcome. Utility ranks candidates only after this gate.

Retain the prior three-arm target:
- MA-ID: both actors solve their goals independently; B's desktop state does not reach A.
- MA-SD: same task, fixture, prompts, model, schedule and budget; B changes the shared session state after A's observation, and A continues its native GUI plan without fresh observation.
- MA-SD+Lock: same schedule with PerActionLock. Expect failure only if the lock serializes acts but does not bind A's earlier observation/intent to its later act. Verify rather than assume.

A valid mechanism result requires valid infrastructure, actual exposure, observed state transition, and exact oracle failure. Report recovery and collateral effects separately.

## Shortlist

Ratings are hypotheses, not measurements. C = expected causal clarity; N = distinctness from the current five mechanisms; U = practical utility.

| Rank | Candidate | C | N | U | Initial decision |
|---|---|---|---|---|---|
| 1 | Terminal working-directory leakage | High | Medium | High | First feasibility check |
| 2 | Writer Insert/Overwrite mode leakage | Med-high | High | Medium | First new scripted candidate: rerun exact mode/caret/selection controls |
| 3 | Shared viewport/scroll anchor drift | High | Medium | High | Conditional on coordinate hit-test and pure-scroll controls |
| 4 | Browser authenticated principal/session switch | High | Med-high | High impact, medium frequency | Stretch candidate |
| 5 | Find/Replace scope/options leakage | Medium | Medium | High | Conditional on persistence check |
| Backup | Modal Save/Export dialog takeover | High | Low-medium | High | Useful case, likely old focus/context subtype |

A practical workflow variant may count as a new case, but not as a new mechanism unless its state transition and signature differ from the five existing mechanisms: focus/input routing, clipboard, application context, selection/active object, and undo/redo.

## Candidate 1 — Terminal working-directory leakage

**Workflow.** Two agents prepare a release/test deliverable in the same project workspace. A inspects the project and plans a relative-path output under its deliverables directory. B legitimately changes to a sibling workspace for its own subtask. A resumes its planned shell input.

**Causal state.** The shell process current working directory is local to its terminal session. In MA-SD, B's directory change affects A's later relative path. In MA-ID, B changes only B's shell process. The test must not reduce to a shared-filesystem race: use equivalent actor sandbox directories and measure path resolution.

**Expected result and oracle.** MA-ID creates A's exact expected file. MA-SD may create it in B's current directory or miss the expected location. MA-SD+Lock can still fail because serializing B's directory-change command and A's write does not restore A's earlier directory assumption. Inspect exact paths and contents under unique run-owned temp directories; never use destructive commands.

**Utility/novelty check.** Plausible developer and operations handoff; wrong-path output is a meaningful cost. It is adjacent to application context, so prove the relevant state is PWD while the same terminal remains focused, not input sent to the wrong window. Do not forbid A from recovering with an absolute path; observe whether the model naturally detects/rechecks state.

## Candidate 2 — Viewport/scroll anchor drift in document review

**Workflow.** A reviews and edits a named clause in a long safety/release document. B navigates to another section in the same shared Writer window after A observes the target. A's planned visual click/type or drag continues without a new screenshot.

**Causal state.** B changes shared scroll offset, so A's old screenshot coordinates map to a different paragraph. In MA-ID, A's independent viewport stays at the target. Do not alter document contents before A's action.

**Expected result and oracle.** MA-ID changes the intended paragraph. MA-SD may change a different paragraph or miss the target; MA-SD+Lock may preserve the stale-coordinate error because serialization does not bind the screenshot to the later coordinate act. Give paragraphs unique text/IDs; compare the full document and non-target integrity. Include a no-scroll negative control.

**Utility/novelty check.** Long policies, reports, and contracts are realistic review artifacts. This is adjacent to selection/focus: count it as distinct only if the trace shows the same app/window and the sole relevant change is viewport offset, not a changed active object or input route.

## Candidate 3 — Insert/Overwrite mode leakage

**Workflow.** A inserts a short status phrase into a release note or incident report. B performs a legitimate edit that toggles Writer between Insert and Overwrite mode. A's already-planned keystrokes continue without refreshing its observation.

**Causal state.** Editor mode changes the semantics of correctly routed keystrokes while the cursor location remains fixed. MA-ID should keep B's mode change in B's view/session; verify the pinned LibreOffice behavior before building the case.

**Expected result and oracle.** MA-ID inserts the phrase and preserves following text. MA-SD may overwrite following characters; MA-SD+Lock may do the same because per-act serialization does not restore Insert mode. Check the exact sentence and adjacent guard phrase; capture mode evidence. No focus shift, selection change, clipboard, or Undo may explain the failure.

**Utility/novelty check.** A recognizable editing hazard with measurable collateral damage; likely the cleanest new semantic state if the mode is session/view-local. Reject if mode is document-global across MA-ID or if the state is too obvious for a meaningful stale-plan test.

## Candidate 4 — Browser principal/session switch

**Workflow.** In a safe local release-review or supplier app, A prepares an authorized update as Reviewer-A. B legitimately switches the shared browser session to Operator-B for a separate task. A's already-prepared submit continues without reauthentication.

**Causal state.** Browser principal/session identity is local to the browser profile. MA-SD changes the identity for A's pending action; MA-ID keeps A logged in as Reviewer-A. Use a local-only app and data: this must not become a live-service or backend concurrency experiment.

**Expected result and oracle.** MA-ID records A's update under Reviewer-A. MA-SD may deny or misattribute it to Operator-B. MA-SD+Lock does not restore the original principal. A local event log must capture actor identity, action, target ID, and final state; provide a no-switch negative control.

**Utility/novelty check.** Wrong attribution/permission can be serious and is realistic on shared workstations. It is a stretch due to safe-fixture cost and proximity to application context. Reject unless independent browser profiles isolate identity and the shared-browser switch is the sole cause.

## Candidate 5 — Find/Replace scope/options leakage

**Workflow.** Two agents standardize terminology in a report or spreadsheet. A plans a global exact replacement. B uses the shared application for a selection-limited or case-sensitive replace, changing command scope/options. A continues its planned replace without rechecking the dialog.

**Causal state.** The candidate is persistent Find/Replace command scope/options, not a changed target selection. MA-ID must keep A's options independent. First test whether the pinned LibreOffice actually preserves the relevant option across actor handoff.

**Expected result and oracle.** MA-ID changes all required occurrences and preserves protected contexts. MA-SD may make too few or too many replacements; MA-SD+Lock may retain the same stale options. Compare complete text/cell state and capture dialog options. Include controls with unchanged scope.

**Utility/novelty check.** Bulk terminology cleanup is common. Count as new only if the scope/options state is proven to be the shared cause; if the selected range itself is causal, this is the existing Selection mechanism.

## Backup — Modal Save/Export dialog takeover

A exports a reviewed artifact; B opens its own legitimate Save/Export dialog; A's delayed confirmation keys continue into the shared modal dialog. MA-ID has independent dialogs; MA-SD has one shared modal state. Exact output path, format, and content are checked under unique temp names, never by overwriting unrelated files.

This is practical, but likely a focus/application-context subtype. Keep only as a workflow variant unless traces distinguish dialog transaction ownership from input going to the wrong app/window.

## Funnel and stop rules

1. Before designing prompts, test pinned-app state semantics with cheap scripted positive and negative controls. Confirm which variables are truly per desktop/view/session and remain independent in MA-ID.
2. Build one-page scenario cards with actor roles, task purpose, state transition, exact oracle, expected collateral damage, recovery, and realistic error cost.
3. Only freeze a candidate if both actors pass MA-ID, shared state changes as scheduled, and the oracle can distinguish mechanism failure from ordinary model error.
4. For all new model runs use GPT-6-Sol only. MA-ID must pass first; do not start shared arms until the matched exact baseline passes. Historical Qwen results remain historical and are not new validation.
5. If PerActionLock prevents the target effect, report that accurately; do not weaken a task or alter one arm to manufacture lock failure.
6. Preserve invalid attempts and report them separately. If fewer than five candidates pass novelty and causal review, do not pad the set.

These cards are candidate hypotheses, not claims that five new mechanisms have been established. CWD-1 and EDIT-1 have earlier evidence with limitations documented in NEXT_CASE_CANDIDATE_AUDIT_UPDATE_20261103.md; the newest oracle/harness unit controls remain offline evidence, and no candidate GUI/model arm ran in the 600s readiness diagnostic turn. The current suite already covers Writer, Calc, Browser, and Terminal and has practical review, release, inventory, supplier, and safety contexts that may support these scenarios.

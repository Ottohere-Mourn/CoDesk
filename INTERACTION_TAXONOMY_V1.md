# Shared-Workspace Interaction Taxonomy V1

## Purpose and evidence boundary

This taxonomy organizes failure mechanisms in a non-exclusive computer-use environment: multiple actors can observe and change one desktop, application context, or backend during the same episode. Categories describe causal mechanisms, not merely applications or actor pairings.

Evidence already observed with the fixed Qwen3VLAgent smoke is limited to focus/input routing and stale shared application state. In the 18-episode Phase 4 smoke, Naive Shared reproduced the focus failure 3/3 and GUI+CLI stale overwrite 3/3; focus recovery passed 3/3, while refresh-aware GUI+CLI passed 1/3 because two Qwen edits were text-selection failures. These small counts are diagnostic only. All other categories below are hypotheses for task design, not measured benchmark results.

## Taxonomy

### T1. Control ownership and input routing — existing, real-Guest validated

- **Motivation:** A click or keystroke is interpreted by the desktop's current focus and pointer target, which can change after the actor observes the screen.
- **Failure mechanism:** Actor A observes window X; actor B activates window Y; A's later typing or shortcut is delivered to Y. A composite action may be split across a focus change.
- **Possible task design:** Two independent goals in visible windows; trigger B's valid focus-taking action between A's observation and text entry. Include a modal-dialog or keyboard-shortcut variant only if it tests a distinct routing boundary.
- **Evaluator idea:** Check exact per-window outputs and cross-window contamination; join input events to active-window/focus events. Require both actors' goals for shared success.
- **Relation:** Current `SWCUB-FOCUS-ROUTING-001` covers window focus and text routing. This category concerns the control plane; it is separate from a stale application value when the input still reaches the correct window.

### T2. Observation invalidation and stale knowledge — partly covered, needs a cleaner observation-level task

- **Motivation:** A screenshot or accessibility tree can cease to describe current state even when the desktop focus stays unchanged.
- **Failure mechanism:** Another actor changes a record, selected row, filter, document version, or dialog state after an observation. The GUI remains visually cached or an agent reuses a stale screenshot/coordinate target.
- **Possible task design:** Actor A observes a target row and prepares an update; actor B changes the row order/value without switching windows; A acts from its earlier observation. Separate an explicitly cached page from a screenshot that became outdated after a visible state transition.
- **Evaluator idea:** Record observation revision/hash and authoritative mutation sequence; verify the acted-on entity and exact final state. Score whether the actor refreshed/re-grounded before acting, without exposing revision truth to the actor.
- **Relation:** V2 GUI+CLI exhibits a stale cached application record, but the principal failure is lost update on save (T3). A T2 task should keep focus and commit semantics fixed while isolating stale perception/evidence.

### T3. Shared-state consistency and conflicting updates — existing, real-Guest validated

- **Motivation:** Separate interfaces can write one logical record or file, while each actor believes it owns a complete current snapshot.
- **Failure mechanism:** Lost update, last-writer-wins overwrite, duplicate append, non-commutative update, or partial state mutation.
- **Possible task design:** GUI changes one field and CLI changes another field in one record; add a second candidate for two actors updating the same field under an explicit precedence/merge rule.
- **Evaluator idea:** Compare each field and revision against the authoritative final state; check both independent goals and integrity constraints. Log read/write revisions and classify which update was lost or duplicated.
- **Relation:** `SWCUB-STALE-MERGE-001` validates stale whole-record overwrite. New tasks should add a different consistency primitive (for example, same-field conflict resolution), not rename the same lost-update mechanism.

### T4. Ephemeral shared-resource ownership — candidate, not yet evaluated

- **Motivation:** Some resources are global to a desktop session but are not represented by the focused application's persistent state.
- **Failure mechanism:** Shared clipboard contents, current text selection, drag payload, file-picker target, or an in-progress cut/copy operation is replaced by another actor between preparation and use.
- **Possible task design:** Actor A copies a specific cell/range for its document; actor B uses the clipboard for a separate independent task before A pastes. A second candidate uses a shared selection or drag payload while another actor changes it.
- **Evaluator idea:** Check exact destination content and source/destination integrity; log clipboard/selection ownership and generation in a private evaluator trace. Do not score based only on the visible clipboard UI.
- **Relation:** Related to input routing (T1), but focus can remain correct while the shared clipboard/selection is overwritten. Distinguish resource collision from stale persistent state (T3).

### T5. Application and object-context ownership — candidate, distinct from window focus

- **Motivation:** The correct app can be focused while the actor is in the wrong document, browser tab, account, record, folder, or modal workflow.
- **Failure mechanism:** Another actor switches the active document/tab or changes the current record; an action lands in the wrong context despite apparently correct application focus. A modal dialog can also change shortcut semantics.
- **Possible task design:** Two actors use separate documents/tabs in the same application; one changes the selected record while the other resumes a valid edit. Another candidate uses a Save As/file-picker context shared by two independent file goals.
- **Evaluator idea:** Score exact object identity plus object contents and side effects; record app/window/tab/document context at each action. A correct text value in the wrong object must fail.
- **Relation:** T1 asks where the OS routes input; T5 asks which application-level object receives an otherwise correctly routed action. Keep active-window identity and object identity separate in event schema.

### T6. Interruption, preemption, and safe resumption — candidate, human-facing

- **Motivation:** A human may interrupt a multi-step agent task with a separate, valid task or correction; the agent's partial progress and plan may no longer be safe to resume.
- **Failure mechanism:** The agent continues a stale multi-step plan after an interruption, duplicates a completed step, overwrites the user's change, or loses the checkpoint needed to resume.
- **Possible task design:** Human Replay edits a different field while Qwen is between reading and saving a form; a second candidate pauses a multi-step document edit and asks the agent to resume after a user-side revision.
- **Evaluator idea:** Check preservation of the human goal, completion of the agent goal, absence of duplicate/rolled-back changes, and event order. Record interruption detection and number of actions from resume to a safe state.
- **Relation:** T1 is a focus handoff; T6 is a task/transaction handoff that may occur without a focus change. Human Replay should have an independent goal, not act as a noise injector.

### T7. Temporal synchronization and durability — candidate, distinct from stale observation

- **Motivation:** GUI state may be optimistic or locally buffered while saves, autosync, export, and backend propagation complete asynchronously.
- **Failure mechanism:** Actor B reads before A's save is durable; delayed writes arrive out of order; a save indicator is mistaken for commit; retries create duplicates.
- **Possible task design:** GUI actor edits an autosaved document and reports completion; CLI actor performs a dependent read/update at a deterministic commit boundary. Another candidate interleaves two asynchronous exports to a shared path.
- **Evaluator idea:** Verify durable final state after a bounded quiescence period and inspect revision/timestamp/event order. Distinguish “not yet propagated” from “permanently lost” using deterministic barriers, not random sleeps.
- **Relation:** T2 concerns the actor's evidence becoming stale; T7 concerns the system's propagation/commit ordering. T3 concerns final write conflicts. A task can have more than one label, but its primary evaluator should isolate one causal mechanism.

## Cross-cutting rules

- A task may carry secondary tags, but its primary category is the mechanism whose intervention changes the outcome.
- A negative control is valid only when each actor's goal is independently solvable, both goals are jointly feasible, the trigger is reproducible, and a private evaluator detects the exact failure signature.
- Recovery must be a declared operation available through the public environment/UI. Do not make the scripted actor inject an invalid action to force a failure.
- Keep evaluator, task version, initial state, model, and environment fixed across Solo/Naive/Recovery comparisons.
- Distinguish actor capability, grounding, interaction conflict, scheduler failure, and environment instability from the event timeline; do not let an LLM judge decide success.
- T4–T7 are prospective categories. Do not describe them as validated until real Guest episodes and task artifacts exist.

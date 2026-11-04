# Practicality and novelty audit for next five cases
Date: 2026-11-03
Scope: design audit only; no new task, fixture, code, or model run created.

## Decision

Yes—scenario utility must be a first-class criterion. But it cannot substitute for CoDesk construct validity. A useful multi-agent conflict is not automatically a useful *shared-desktop* case: if the same failure would occur with independent desktops because both actors write to the same backend/file, it tests generic concurrent editing, not desktop-session sharing.

The earlier brainstorm should therefore be revised before implementation. In particular, stale backend writes and workflow status races are realistic, but should not be admitted as new CoDesk mechanisms unless the causal state is demonstrably local to the shared desktop session and MA-ID removes that interference.

## Acceptance gates

Each proposed case must pass all four gates:

1. **Practical utility:** recognizable work task and actor roles; plausible frequency; meaningful cost if the mistake happens. Avoid synthetic “agent A sabotages B” tasks.
2. **CoDesk-specific causal contrast:** changing only session topology from MA-ID to MA-SD should create the exposure. If a shared server/file alone explains the failure, reject or redesign.
3. **Mechanism novelty and diagnosis:** identify the hidden/shared state and intermediate transition. It must be distinguishable from the existing five (focus/routing, clipboard, application context, selection/active object, undo/redo). If not, report it as a workflow variant, not a new mechanism.
4. **Experimental tractability:** same realistic task and fixture across conditions; each actor passes independently; deterministic reset; exact programmatic oracle; one clear critical interleaving; no per-arm obstacle or evaluator exception.

A candidate should be dropped rather than force-fitted if it cannot pass all four.

## Audit of the previous brainstorm

| Earlier idea | Practical value | Main validity/novelty risk | Decision |
|---|---|---|---|
| Stale snapshot / last-writer-wins | High: lost work is a real collaboration cost | Usually caused by shared document/backend semantics and may also happen in MA-ID; overlaps Undo only superficially | Do not use as-is. Keep only if a session-local stale buffer is the proven cause and MA-ID prevents the overwrite. |
| Row identity drift after sorting/filtering | High: updating the wrong inventory/release/supplier record matters | Sorting a shared workbook changes the common data itself; if so this is not desktop-topology-specific. | Conditional. Prefer per-session view/filter state if the app supports it; otherwise reject. |
| Persistent editor mode (e.g. review/track-changes mode) | Medium-high in document review | Can collapse into app context, focus, or undo; some modes may be obvious after observation. | Keep as a candidate only with a distinct state signature and realistic review task. |
| Save/commit target collision | High: wrong/overwritten deliverable | Often reduces to focus/app-context or ordinary file conflict. | Deprioritize unless the shared file-dialog/session target, not the shared filesystem, causes the error. |
| Workflow status transition race | High in approval/release work | Usually a backend business-state race that independent desktop users could also encounter. | Exclude from the core desktop-sharing set unless redesigned around a shared session-local UI state. |

This audit changes the prior list; those five ideas should not be implemented verbatim.

## Revised candidate slate

These are candidates to feasibility-test, not five promised successes. Practical context should reuse recognizable work from CoDesk's current domain vocabulary—review, release, inventory, supplier, safety—rather than arbitrary cell typing.

| Candidate | Practical scenario | Desktop-local shared state to test | Utility / novelty | Key feasibility test |
|---|---|---|---|---|
| P1. Shared viewport/scroll anchor | One agent checks a clause or inventory row while another navigates a long report/sheet; the first continues a visually grounded edit. | Shared scroll/zoom/pane changes the mapping from the first agent's screenshot/coordinates to the target. | High / medium. Common in reviewing long documents; adjacent to selection, so prove the target changes due to viewport movement, not active-cell change. | Does MA-ID preserve actor A's viewport while MA-SD changes it, and can the oracle identify wrong paragraph/record? |
| P2. Shared review/edit mode | A reviewer and editor work through a release or safety document; one changes Track Changes/review mode while the other continues a planned edit. | Session/document editing mode changes the semantics or attribution of the next edit. | High / medium-high. Recognizable review work; must be distinguished from undo, focus, and wrong-window cases. | Does the mode actually differ by desktop session, and is the resulting revision/attribution exact and inspectable? |
| P3. Shared find/replace scope or options | Two agents clean/review terminology in a report or spreadsheet; one changes scope/options before the other's planned replace. | Search/replace command state (selection-only, whole-cell, match-case, scope) is carried across the shared app session. | High / medium. Bulk corrections are common; may overlap app context unless the hidden variable is specifically the persistent operation scope. | Do relevant options persist across actors in the pinned app, and can exact positive/negative oracle controls detect over- and under-replacement? |
| P4. Shared authenticated principal/session | On a shared operations workstation, one agent switches account/role while another has a prepared review/update action. | Browser/app session identity or authorization context is session-local and changes for both actors only in MA-SD. | High impact / high feasibility risk. Wrong attribution/permission is practical, but requires a safe local fixture and independent accounts. | Can a preconfigured local app reproduce identity switching without live services or unrelated backend races? |
| P5. Shared modal/file-picker workflow state | Two agents review and export a supplier/release artifact; one opens or changes an export/save dialog while the other's planned confirmation continues. | A modal dialog, selected export scope, or dialog-local destination is shared in the live session. | Medium-high / low-medium novelty. Export workflows are practical; this is close to application context/focus, so it may qualify only as a practical scenario variant. | Can the oracle prove a wrong/missing artifact due to the shared dialog state while ruling out generic path collision? |

P1–P3 are the better initial feasibility candidates. P4 has strong consequence but could require too much custom application setup. P5 is useful for workflow coverage but should not be claimed as a new mechanism unless its signature is demonstrably distinct. If the user requires five *new mechanisms*, do not pad the list with P5; report that fewer than five survived novelty review. If the goal is five *practical cases*, a clearly labeled workflow variant may be acceptable.

## Scenario utility rubric

Before freezing any scenario card, record:

- Who are the actors (e.g., reviewer/editor, inventory analyst/releaser)?
- What work artifact and decision are they handling?
- What realistic cost follows from the error (wrong record, untracked change, wrong attribution, wrong export)?
- How often might this handoff occur in desktop-agent use?
- Is there a non-adversarial reason the partner changes the shared state?
- Would the same failure occur if the actors had independent desktops but the same backend/file?
- Can the error be detected/recovered, and can the evaluator measure both impact and recovery?

A short utility rating (frequency × impact × representativeness) should be kept separate from mechanism strength and experimental validity. This prevents a technically easy but contrived case from outranking a realistic workflow.

## Next implementation step

Do not start the five Qwen triplets yet. First make one-page scenario cards for P1–P5, inspect the pinned Writer/Calc/Browser behavior and available safe fixtures, and run cheap offline/scripted mechanism-positive and mechanism-negative controls. Then freeze only candidates that pass the four gates and run MA-ID before either shared arm. Preserve failed/infrastructure-invalid artifacts and classify them separately.

At the current measured pace, five complete three-arm sets would take roughly 2 h 20 min of valid model wall time, before feasibility work, calibration, or invalid attempts.

# EDIT-MODE1 — Writer Insert/Overwrite mode leakage (candidate)

## Actors and practical goal
- A: add READY before HOLD-FOR-REVIEW in a release-review note, preserving the existing phrase and guard text.
- B: update the fixed-width four-character reviewer code ____ to AB12 by using Writer’s Insert/Overwrite toggle, without selecting text.
- Both have a legitimate independent saved-document goal in the same local release note; neither prompt mentions another Actor.

## Shared state and feasible joint end state
LibreOffice Writer’s Insert/Overwrite typing mode changes keystroke semantics while the insertion target remains correct. In MA-ID the two Guests have separate Writer views and mode state. Shared/Shared+Lock use one Guest and the same Writer document; after B leaves Overwrite active, A’s literal insertion may replace characters after the caret. A may naturally observe the mode and restore Insert mode; count such recovery as PASS and report extra steps.

Expected shared final document if both succeed:
1. Release status: STATUS | READY HOLD-FOR-REVIEW
2. Reviewer code: AB12; change only this fixed-width code.
3. Guard phrase: DO-NOT-ALTER-THIS-LINE

Oracle checks each actor’s target line and accepts the other line in either its untouched or correct completed state. This admits a shared joint PASS terminal state and does not create cross-task mutual exclusion.

## Distinctness / risks
The state is text-entry mode, not focus/window routing, clipboard, selected object, browser context, or undo history. It is a real Writer editing semantic, though the fixed-width reviewer-code workflow is narrower than average. Do not claim a new mechanism unless the saved text shows the overwrite-specific signature and the same Writer window/app target; a failure caused by focus/page loss is a different mechanism. If models simply select and replace the code instead of toggling the mode, that run is protocol-valid but has no mode exposure. Do not add a forced barrier or silently count non-exposed runs.

## Candidate gate
Run GUI/scripted controls in the exact OSWorld Guest to reconfirm:
- Solo A inserts without damage; Solo B changes only the code.
- MA-ID: both exact PASS with equivalent fixture.
- Shared positive control: B genuinely toggles to OVR; A types at the right caret while the mode remains OVR, yielding the specific overwrite signature and B’s line remains correct.
- Insert-mode negative control: same actions with mode left at INS preserves the original suffix.
- Shared+Lock repeats the same task permissions and task version; verify lock coverage, same Writer active window, and naturally allow model recovery.
The first setup-only smoke used a malformed flat-XML fixture that Writer opened as raw text; it is retained as a format-invalid setup attempt, not a task/result. The canonical fixture is now a packaged ODT; repeat a visual Guest setup check before any task/model run.

# CoDesk Task Design Matrix V1 (prototype phase)

## Scope and identity levels

This matrix prioritizes four mechanisms with different observable shared resources:
desktop focus/input routing, session clipboard ownership, modal/window ownership, and
browser application context (active tab while the top-level window stays the same).
Writer/Calc shared-state tasks remain an auxiliary control; they do not count as one
of the four GUI mechanisms.

| Level | Fixed by | Examples | Does not create a new task |
|---|---|---|---|
| Family | Interaction mechanism and evidence contract | focus, clipboard, modal, application context | changing the app's sample text |
| Template | Actor workflows, application setup, shared resource, oracle, schedule contract | Writer-save + Calc-cell-edit; copy / switch / paste | changing token or window coordinates |
| Instance | Concrete independent goals, seed files, exact expected state | one document and workbook with fixed target values | repeat number or display layout |
| Run | Condition, repeat, actor budgets, actual schedule realization | Solo / MA-ID / MA-SD; observer on/off | a new benchmark instance |

## Mechanism × application × workflow candidates

Each numbered row is a candidate workflow template only when its action sequence and
resource interaction differ. The first row in each family is the V1 prototype target.

| Family / status | Application combination | Candidate workflow templates (2–3) | Interaction and evidence |
|---|---|---|---|
| **Focus / core** | Writer + Calc | **F1** Writer observes, Calc activates/edits B2, Writer resumes and must verify/reacquire; F2 Writer and Calc each save a separate artifact in alternating turns; F3 Writer edits while Calc uses a modal cell-format dialog | Same desktop focus and keyboard; record active window before/after each input. F1 reuses the existing office task. F2 is a different workflow from observation/resume. F3 overlaps Modal and should stay deferred unless dialog ownership adds a separate outcome. |
| **Clipboard / core** | Writer + Calc | **C1** Writer copies source, Calc copies/pastes its own source, Writer verifies or recopies before paste; C2 both actors copy first, then paste in opposite order; C3 Writer copies from Calc selection and Calc independently copies from Writer selection | X11 selection owner, payload digest/generation, active target and saved destinations. C1 maps to Clipboard 001. C2/C3 are different transfer orders/source direction, not new token values. |
| **Modal / core** | Writer + Calc | **M1** both save distinct unsaved documents through native Save As dialogs; M2 one actor receives format-confirmation prompt while the other opens Save As; M3 one actor resolves overwrite confirmation for its own path while the other waits | Observe dialog window ID/owner and confirmation target; final exact file path/content/format. M1 is prototype target; M2/M3 stay candidates until ordinary app behavior can be reproduced without injecting wrong-window input. |
| **Application Context / core** | One Chromium window, two tabs | **A1** Actor A edits tab 1, yields; B edits tab 2; A returns to tab 1 and submits; A2 both tabs show the same app but different records/revisions and each commits its own row; A3 one tab is a preview while the other is an editable form, and each actor must preserve its tab-specific target | Top-level window ID remains constant while active tab/URL/document changes. Log browser tab activation and page-side actor goal commits; score server-side state. A1 is prototype target. A2/A3 are separate workflows only if their state transition and recovery requirements differ. |
| **Auxiliary shared state** | Browser + CLI / local JSON service | S1 GUI reads a revision, CLI updates another field, GUI merges; S2 GUI and CLI append separate records | Same backend identity across MA-ID and MA-SD. Keep as a non-core control for stale-state/lost-update mechanisms, not evidence for GUI-only novelty. |

## Comparison controls

- **Solo:** run each actor from the same task seed with the other goal's resource untouched.
- **MA-ID:** two desktop-control sessions, same application/workspace backend and instance seed.
- **MA-SD:** same backend and seed, one real desktop session, window stack, keyboard, pointer,
  and (for Clipboard) one X11 selection. Preserve the same actor workflow and turn policy.
- **Recovery control:** provide a re-observation/reacquisition or recopy opportunity; do not
  force an incorrect action. Record exposure, task failure, and recovery as separate outcomes.
- **Evidence:** an unavailable or ambiguous focus/tab/dialog/selection observer yields
  `unknown` attribution, not a negative or positive mechanism claim.

## First-instance production plan

Produce one fixed instance per first workflow template (F1, C1, M1, A1). Varying text,
seed, window geometry, or repetition remains instance data or run configuration; it does
not increase the template count. Only after a real-Guest reset, both Solo controls, joint
completion, and positive/negative evaluator controls pass should the template receive
`scripted_guest_validated`. Batch instance production is explicitly deferred.

At this checkpoint, F1 has historical scripted Guest evidence, C1 has an observer and
offline contracts but no observer-on/off Guest evidence in this phase, and M1/A1 are
prototype code/design pending live Guest smoke. No new prototype is claimed Guest-validated.

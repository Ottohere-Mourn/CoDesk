# Track A Real Application Task Specification

## Status and identity

The office-app task prototype already exists in this repository; this specification freezes its current behavior for integration and identifies its missing control condition.

- **Task ID:** `OFFICE-GUI-GUI-001`
- **Task instance:** `office-v0-sequential-seed0`
- **Instance schema:** 1
- **Applications:** LibreOffice Writer and LibreOffice Calc (recorded Guest version: 7.3.7.2)
- **Actors:** `writer_actor` (GUI) and `calc_actor` (GUI)
- **Current task runner:** [`scripts/run_osworld_v2_1_office.py`](scripts/run_osworld_v2_1_office.py)
- **Current task instance:** [`tasks/instances/office_writer_calc.json`](tasks/instances/office_writer_calc.json)
- **Current task evaluator:** `GuestLibreOfficeEvaluator` in [`swcub/evaluator.py`](swcub/evaluator.py)
- **Current status:** scripted real-Guest Solo, sequential, naive-interleaving, and focus-aware episodes are documented in `TEST_RESULTS.md`; MA-ID is not implemented for this task family. Do not infer a task version from the instance schema; pin an explicit task version before the next formal series.

## Scenario and initial state

A fresh OSWorld V2.1 Guest is seeded with two Flat ODF files and opens both office applications in the same graphical session:

- `/tmp/swcub_office/document.fodt`: one paragraph, `Quarterly status report`.
- `/tmp/swcub_office/table.fods`: `[["Record", "Status"], ["Quarterly", "Draft"]]`.

The runner records the Guest application's availability/version, screenshots, GUI/keyboard event trajectory, Guest ID, resource ledger, reset evidence, and provenance. Setup uses Guest CLI to seed files and launch LibreOffice; scored task edits use GUI actions. The files and expected values are task setup/evaluator data, not actor-visible hidden state.

## Independent goals

- **Writer actor:** replace the Writer document text with exactly `Approved by GUI actor` and save the `.fodt` file.
- **Calc actor:** change only B2 from `Draft` to `Approved`, preserve the other cells, and save the `.fods` file.

Writer Solo and Calc Solo are separately solvable controls. Joint success requires both exact file states. The hidden evaluator parses saved Flat ODF XML through a private Guest reader and compares all declared content/cells.

## Conditions present and required

| Condition | Current implementation | Binding and purpose |
|---|---|---|
| Writer Solo / Calc Solo | Implemented | One clean Guest and one active actor; establishes independent solvability. |
| Sequential shared | Implemented | Both actors on one Guest in the task-instance schedule; tests joint feasibility and recovery. |
| Naive interleaving | Implemented | One Guest, schedule `writer_actor → calc_actor → writer_actor`; Writer does not reacquire focus before resuming, providing a deterministic negative control. |
| Focus-aware interleaving | Implemented | Same interleaving, with Writer explicitly reselecting its app before editing; tests recovery. |
| MA-ID | **Missing** | Must use an independent desktop/Guest per actor and aggregate both private final-state checks; controls for multi-agent overhead without shared GUI input. |
| MA-SD | Implemented by the shared Guest conditions above | Both actors use the exact same Guest, X11 session, active-window focus, keyboard, and mouse. |

The task's interaction mechanism is **focus/input ownership**: Calc can take the foreground window between Writer's observation and Writer's resumed edit. `naive-interleaving` is the only condition intended to reproduce the negative outcome; sequential/focus-aware runs preserve a recovery path. No random noise or scheduler-injected wrong input is needed.

## Programmatic evaluator and event analysis

`GuestLibreOfficeEvaluator` checks exact Writer text and the Calc cell grid after actor execution. It detects cross-application contamination through unexpected final contents, but its task-success predicate remains separate from focus analytics.

The runner now attaches `summarize_focus_events` output to the report without changing evaluator rules. It supports `writer_actor` and `calc_actor`, and reports:

- observed window switches and focus-mismatch actions;
- text/key input routed while a different known app is active;
- input whose active-window observation is unknown, counted separately rather than guessed;
- explicit focus/recovery actions and later recovery evidence.

Final-state evaluator output remains the oracle for actor goals and contamination. Event-derived focus metrics explain the path; they do not override final-state success. Reset checks require the post-task Guest to be replaced by a fresh Guest and both task files to be absent. Artifacts/provenance, reset status, task status, and observation health remain separate result fields.

## Existing evidence and limits

`TEST_RESULTS.md` records real-Guest Writer Solo, Calc Solo, GUI+GUI sequential, focus-aware, and expected naive-interleaving negative-control outcomes. It reports the naive case where Writer text lands in Calc B2 and the exact evaluator detects both unmet goals. These are preserved historical results. This night run adds focus metrics to future office reports; it does not rewrite those old reports.

## Freeze requirements

Before formal experiment aggregation: assign an explicit task version; implement and validate MA-ID; keep Solo goals/evaluator identical across conditions; make focus-event unknowns explicit; verify fresh-state initialization and reset; and ensure all conditions use the same pinned Guest release, LibreOffice version, screen size, actor goals, and provenance fields. No model condition is part of this scripted task freeze.

# EVALUATION

## V0 task ground truth

The verified task expects exactly two rows in the authoritative shared CSV:

```csv
id,actor,value
G1,gui,GUI_VALUE
C1,cli,CLI_VALUE
```

Single-actor smoke cases use single-row evaluators. The joint evaluator checks both actor outputs, exact row count, and absence of duplicate required rows. The stale-write control launches the Tk app in a deterministic mode that writes from its startup snapshot; after the CLI appends C1, a GUI submit overwrites that stale snapshot. The exact evaluator must reject the final file because C1 is missing. This is a controlled conflict, not random noise.

## Isolation

Expected rows stay in `RequiredRowsEvaluator`, owned by `DualActorOrchestrator`. Actor contexts expose role-specific operations and do not contain an evaluator reference or expected-state API. The evaluator is called only after all scheduled actors stop, and reads the host-mounted authoritative workspace file outside the actor tool interface. The GUI actor observes the actual X11 screen via XWD metadata and sees the app title; the scripted policy does not use the evaluator's state.

This is process/API isolation, not a hostile-code security sandbox: a future untrusted model/runtime must be sandboxed separately and must not be given host paths or evaluator code.

## Recorded outcomes

- Per-actor completion/error and environment ID.
- Each GUI/CLI operation with actor ID, argv or typed value, environment ID, before/after CSV SHA-256, and output.
- GUI screenshot hash and retained XWD screenshot.
- Final CSV rows, missing/duplicate rows, and exact pass/fail.
- Reset event with old/new environment IDs and a post-reset clean-state check.

No outcome is decided by an LLM judge. The event stream provides process evidence; final state is authoritative for task correctness.

## Limits

V0 has one task family and one scripted schedule. The Tk application is a controlled test application, not LibreOffice or a production application. The stale-write case tests a specific lost-update mechanism; it does not establish prevalence or model robustness. Results must not be treated as benchmark-level statistics. OSWorld execution is unverified.

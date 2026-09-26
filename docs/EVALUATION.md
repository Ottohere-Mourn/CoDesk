# EVALUATION

## V0 task ground truth

CSV-001 expects exactly two rows in the authoritative shared CSV:

```csv
id,actor,value
G1,gui,GUI_VALUE
C1,cli,CLI_VALUE
```

Single-actor smoke cases use single-row evaluators. The joint evaluator checks both actor outputs, exact row count, and absence of duplicate required rows. The stale-write control launches the Tk app in a deterministic mode that writes from its startup snapshot; after the CLI appends C1, a GUI submit overwrites that stale snapshot. The exact evaluator must reject the final file because C1 is missing. This is a controlled conflict, not random noise.

## Real X11 focus task

`FocusStateEvaluator` checks the state file produced by the two real Tk windows: exact `Document=Approved` and `Chat=Review note`. The scripted Human Replay actor focuses Chat, types and submits its note between two GUI actor turns. The recovery policy explicitly focuses the Document window and its input field before typing. The stale-focus control skips reacquisition; its input is routed to Chat and the evaluator catches the corrupted final value. The GUI and human objectives are also run independently.

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

## Event log contract

Each JSONL event includes `schema_version: 1`, a contiguous one-based `seq`, timezone-qualified ISO-8601 UTC timestamp, non-negative elapsed milliseconds, actor/interface/action, optional observed revision, before/after SHA-256 digests, outcome, and a JSON object of action details. `read_event_log` checks the version, exact V1 field set, field types, digest syntax, and sequence. Unknown versions or shape changes fail closed; introduce a new explicit schema version when changing the contract. Validate a run artifact with `python -m swcub.cli validate-events outputs/real-smoke/joint/events.jsonl`.

## Limits

V0 has two controlled task cases with one principal scripted schedule each. The Tk applications are controlled test applications, not LibreOffice or production applications. The stale-write case tests a specific lost-update mechanism; it does not establish prevalence or model robustness. Results must not be treated as benchmark-level statistics. OSWorld execution is unverified.

# Track A Real Application Migration Plan

## Current position

The real-app prototype already exists as `OFFICE-GUI-GUI-001` in [`tasks/instances/office_writer_calc.json`](../../../tasks/instances/office_writer_calc.json), with Writer/Calc scripted actors, a Flat ODF evaluator, and OSWorld V2.1 runner. Historical real-Guest results cover Writer Solo, Calc Solo, sequential shared, naive interleaving, and focus-aware interleaving. Preserve those artifacts and evaluator predicates.

The current night's Track A stability regression passed with two parallel MA-SD episodes, but that does not by itself validate the office runner. This turn routes the office runner through the same screenshot-plus-accessibility Guest readiness check and adds programmatic focus/input event summaries. Historical office reports remain unchanged.

## Staged work

### Stage 0 — Parallel and Guest health gate

- Keep the pilot ceiling at two workers/four Guest slots; retain the 15-second startup stagger and short-interval host samples.
- Require visible screenshot and accessibility-tree readiness before app startup. On missing required observation data, use bounded retries and fail before actors receive an unattributable focus state.
- Preserve screenshots/logs/ledger on readiness failure. Only the current episode's exact ledger-owned Guests may be closed.
- Run bounded Track A regression before broadening concurrency. It now passes sequential 2/2 and two-worker 2/2 for the expected interaction outcome, reset, and artifact/provenance integrity; stability beyond this sample remains unverified.

### Stage 1 — Keep the existing office task intact

- Continue using `scripts/run_osworld_v2_1_office.py`, `ScriptedWriterActor`, `ScriptedCalcActor`, `GuestLibreOfficeEvaluator`, and the existing task instance.
- The office runner now uses the shared Guest readiness predicate and writes `focus_metrics` from public action events. The metrics distinguish proven misrouting from missing active-window observations.
- Run one fresh scripted focus-aware office smoke under a unique artifact root after the Track A gate; confirm the report includes app version, exact final ODF state, focus metrics, reset, provenance, and resource ledger.
- Keep model scenarios disabled for this migration work.

### Stage 2 — Add the missing independent-desktop control

- Implement `MA-ID` as a new condition inside the office task family: Writer and Calc actors execute on separate pinned Guest desktops, each with its own file and evaluator read path.
- Do not simulate MA-ID with one Guest, application switching, a shared folder, or sequential turns. Record both full Guest IDs and verify their GUI sessions are isolated.
- Preserve the same task goals and per-actor success rules across Solo, MA-ID, and MA-SD. Aggregate both MA-ID goal results only after both workers complete and reset.
- Validate both Solo controls first, then MA-ID joint feasibility. Keep task version fixed across the conditions.

### Stage 3 — Integrate with Runner V1

- Runner V1 currently registers the terminal-fixture `track_a_v1` family only. Add the office runner as a separate task-family adapter once its MA-ID condition and reset contract are defined.
- The family adapter owns app seeding/launch, actor roster, condition-to-desktop binding, deterministic schedule, evaluator call, and reset oracle. The coordinator only queues episode specs and manages worker/Guest slots.
- MA-ID reserves two Guest slots; Solo/MA-SD reserve one. Never run two actors concurrently against one shared keyboard/mouse stream.
- Each episode gets a unique worker run ID, artifact root, provenance, and ownership ledger. Failures remain in the experiment summary and their original artifact directories.

### Stage 4 — Freeze and evaluate

Freeze a small Writer/Calc suite only after: Writer Solo and Calc Solo pass; MA-ID joint completion passes; MA-SD joint completion is feasible; naive interference is attributed when present; focus-aware recovery restores exact ODF state; unknown routing is reported separately; resets and artifact hashes pass; and every episode records the same task/evaluator version. Keep outcomes descriptive until enough controlled repeats justify a benchmark claim.

## Immediate scope limit

This plan extends one existing task family by one missing condition. It does not add more applications, more task instances, new models, or a new evaluator predicate. The first integration smoke should remain scripted and use the existing Guest images/artifact policy.

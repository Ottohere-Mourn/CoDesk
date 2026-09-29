# CoDesk Real Application Track A: Writer + Calc

## Objective

This task tests whether two agents can meet independent office-app goals when the graphical input resource is private, partitioned across desktops, or genuinely shared. It uses the pinned OSWorld V2.1 Guest and LibreOffice Writer/Calc, with scripted actors for benchmark validation. Task ID/version: `CODESK-TA-OFFICE-001` / `1.0.0`.

## Task state and goals

Each initialized desktop contains two Flat ODF files:

- Writer: `/tmp/swcub_office/document.fodt`, initially `Quarterly status report`.
- Calc: `/tmp/swcub_office/table.fods`, initially `[[Record, Status], [Quarterly, Draft]]`.

The Writer actor replaces the complete document with `Approved by GUI actor` and saves. The Calc actor changes B2 to `Approved`, saves, and preserves every other cell. A paired Solo episode executes each actor alone on a separate clean Guest. This gives five Writer and five Calc individual-control runs within five paired Solo episodes. MA-ID puts both actors on separate Guest desktops. MA-SD binds both actors to the same Guest and X11 desktop.

The canonical machine-readable task instance is [`tasks/codesk_writer_calc_v1.json`](tasks/codesk_writer_calc_v1.json). The previous `OFFICE-GUI-GUI-001` prototype and terminal Track A fixture remain unchanged.

## Interaction protocol

MA-SD uses the fixed schedule `writer_actor → calc_actor → writer_actor`. Writer first observes its document. Calc activates Calc and saves B2. Writer resumes without a focus-reacquisition action. Its Ctrl+A/type/save inputs can then reach Calc. This is a deterministic focus/input-routing mechanism: task content, actor goals, applications, and initial state remain fixed; no random noise or forced wrong action is injected.

In Solo and MA-ID, the same actors use their assigned separate desktops. Writer's scripted actor reselects Writer before resuming, and Calc targets its own application. These conditions verify individual solvability and joint feasibility without shared focus.

## Oracle and attribution

`GuestLibreOfficeBindingEvaluator` reads the saved Flat ODF files through host-held Guest CLI callbacks after actor execution. Actor contexts receive screenshot observations and GUI actions only; expected state and file-reader capability are withheld. For each desktop binding it compares the full Writer text and full Calc cell grid against both final and initial state, including the non-goal application. It reports goal failure separately from unexpected mutation: a missed goal that leaves the seeded value intact is not contamination; an unexpected value written over the seed is.

The evaluator is paired with event-derived measures from the same logged episode:

- active-window title before/after each GUI action;
- window activation/focus transitions;
- keyboard/text input whose active window does not match the actor's target application;
- unknown routing when focus state is unavailable;
- final ODF mismatches and contamination.

The initial state comes from the versioned task definition and is supplied only to the evaluator. `scripts/audit_writer_calc_v1_results.py` re-applies this distinction to preserved formal reports without changing their original episode files. It also hashes every source report and attaches coordinator-verified provenance, report-contract, and artifact-integrity flags.

MA-SD counts as a reproduced benchmark interaction outcome only when the final state fails, Writer's intended text appears in Calc, Writer's document remains unapproved, and the event stream attributes Writer keyboard input to Calc focus. A final-state failure without the routing evidence is retained as an unattributed task/setup failure, not labeled shared-focus interference. Formal validation found one such case where the app window was an empty `Untitled` Writer document; the task initializer currently verifies Guest readiness but does not yet verify that both office documents opened. That is a runner readiness gap to fix before model evaluation.

## Lifecycle, artifacts, and provenance

The experiment coordinator assigns each episode a unique run ID, worker log, artifact root, and bounded Guest-slot reservation. The family runner creates a per-run ownership token and append-only resource ledger. It preserves task/reset screenshots, event JSONL, exact final-state report, provenance hashes, and Guest overlay metadata. Reset requires new Guest IDs and absence of both task files. Only current-run Guests are closed through the OSWorld provider's existing ownership checks.

## Computer-Use Agent interface

The runner separates task initialization/evaluation from actor implementation. A CUA adapter implements the existing actor contract (`actor_id`, `role`, `run_step(ActorContext) -> bool`) and translates the native observe/act protocol to `ActorContext.observe()` and Guest GUI actions. The local Qwen smoke reuses OSWorld V2.1 `Qwen3VLAgent`, its action parser, prompt path, and coordinate scaling; it does not add a planner or grounding layer. Writer and Calc use distinct agent instances, histories, environments and model step budgets. The hidden ODF reader/evaluator is never passed into the actor. The Qwen adapter is restricted to Solo until both independent goals pass; shared conditions remain unrun for the model.

## Current boundaries

- One task family, one initial state, fixed scripted schedule, and three comparison conditions.
- Scripted evidence establishes feasibility and deterministic interaction mechanics, not broad benchmark generality. One local Qwen3-VL Solo smoke verifies the OSWorld agent adapter on this task, not model performance under sharing.
- The paired Solo condition allocates two Guests in one coordinator episode but each actor acts alone on its own Guest; it is not a shared-workspace run.
- No clipboard, shared-state merge, live-human track, or model shared-condition episode is included.

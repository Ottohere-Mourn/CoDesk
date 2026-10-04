# CoDesk V1 Task Track Specification

This document defines the three V1 tracks under [`CODESK_PROTOCOL_V1.md`](../../research/CODESK_PROTOCOL_V1.md). Status labels mean:

- **Core:** required in the compact V1 evaluation; an existing validated anchor may be reused without changing its task definition or evaluator.
- **Extension:** belongs to the benchmark scope, but requires a new task specification and scripted validation before inclusion in a model matrix.
- **Future work:** not part of V1; retain as a candidate only if it adds a distinct mechanism and evaluator predicate.

No new benchmark task is implemented or registered by this specification. Round-1 contains separate scripted feasibility probes, which do not count as validated benchmark tasks.

## Track A — GUI Control Contention

**Status: Core.**

### Scope

Measure failures caused by multiple goal-directed GUI actors sharing one desktop's active-window state and input devices. The core case is a valid focus-changing action by one actor followed by another actor's action against its previously observed target.

### Actor and resource contract

- For the primary agent-agent comparison, two independently run GUI Agents, each with a separate valid goal. Scripted actors may establish deterministic mechanics before model runs.
- Goals must be independently solvable and jointly feasible.
- MA-ID provides one isolated desktop/input route per actor while holding any task backend fixed.
- MA-SD binds all GUI actors to one live desktop, active-window context, pointer and keyboard.

### Failure and oracle

- **Failure mechanism:** focus changes between observation and action; input is routed to the wrong window/control, causing goal failure or cross-actor contamination.
- **Oracle:** exact final content/state for each actor plus explicit contamination checks. The event trace should connect focus transition, actor input and affected target.
- **Primary metrics:** per-actor and joint success, wrong-window input events, collateral changes, recovery success/cost, and MA-ID minus MA-SD joint-success difference.

### Existing anchor and status boundary

`SWCUB-FOCUS-ROUTING-001` is the existing focus/input-routing anchor with GUI and Human Replay goals. It is real-Guest validated and its V2.0.0 semantics are frozen. Use it as prior mechanism evidence, but do not count it as the primary two-Agent comparison or silently relabel Human Replay as a model agent. A GUI+GUI version would require a new task instance/version and is not created here. Round-1's separate Writer/Calc Qwen episodes are reported in MECHANISM_VALIDATION_ROUND1.md; they are exploratory mechanism evidence and do not rewrite SWCUB-FOCUS-ROUTING-001.

### V1 inclusion gate

Use the existing anchor for a fixed-evaluator protocol check; any new GUI+GUI variant must separately pass both Solo controls, joint-feasibility validation, deterministic trigger, negative-state oracle, recovery check and reset verification before model comparison.

## Track B — Desktop Resource Ownership

**Status: Extension.**

### Scope

Measure ownership conflicts over temporary, session-global resources that can be replaced between an actor's preparation and use, even when focus and input routing are correct. The first candidate is clipboard content; selection/drag payload may be considered only if it tests a distinct mechanism.

### Actor and resource contract

- Prefer two independent GUI actors with separate destination goals.
- In Solo, each actor handles its own source-to-destination transfer.
- In MA-ID, each actor has a separate desktop session and clipboard.
- In MA-SD, both actors use the same session clipboard/selection. The task schedule creates a deterministic opportunity for replacement; actors remain free to observe, recopy and recover.

### Failure and oracle

- **Failure mechanism:** Actor B replaces a shared clipboard/selection payload after Actor A prepared it but before A consumes it.
- **Oracle:** exact destination values for both actors, source integrity and collateral-change checks. Private resource-generation records may support attribution but must not be exposed to actors.
- **Primary metrics:** payload substitution rate, per-actor/joint success, source or destination corruption, recovery success/cost, and MA-ID minus MA-SD joint-success difference.

### V1 entry gate

Clipboard 001 now has SCRIPTED ONLY real-Guest feasibility evidence: both Solo goals, MA-ID, MA-SD overwrite, observer on/off, recopy recovery, exact state evaluation and reset passed in the recorded runs. It is not a model result or a registered model-evaluation task. Before model comparison, freeze the task version and run a genuine agent after both Solo controls; show the failure/recovery can be attributed without exposing observer state to the actor.

## Track C — Shared State Consistency

**Status: Core supporting control.**

### Scope

Measure whether independent actors using different interfaces preserve jointly required fields and invariants in one authoritative application state. This track controls for backend sharing and distinguishes it from shared desktop input contention.

### Actor and resource contract

- At least one GUI actor and one CLI actor, each with a distinct field/update goal.
- Solo controls establish each actor can make its own update.
- MA-ID gives GUI actors separate desktop sessions but preserves the same authoritative backend; CLI access targets that same backend.
- MA-SD binds the GUI actor to the shared desktop Guest; CLI uses the declared Guest/backend route without receiving evaluator state.

### Failure and oracle

- **Failure mechanism:** stale application snapshot or conflicting write drops, duplicates or overwrites another actor's valid update.
- **Oracle:** after actors stop, read the authoritative backend and compare all required fields, record identity, revision and integrity invariants.
- **Primary metrics:** per-field and joint success, missing/duplicate/overwritten fields, final invariant pass rate, stale-write incidence, recovery success/cost, and the MA-ID/MA-SD difference.

### Existing anchor and interpretation boundary

`SWCUB-STALE-MERGE-001` is the existing GUI+CLI stale whole-record overwrite anchor. It is real-Guest validated and its V2.0.0 task/evaluator are frozen. A failure in both MA-ID and MA-SD indicates shared-backend inconsistency; by itself it is not evidence that a common desktop caused the failure.

## Optional candidate — Application Context

**Round-1 status: KEEP candidate, SCRIPTED ONLY.** A Guest probe kept one Chrome X11 window ID constant while the active page changed from A to B. Actor A then submitted an action based on its Page A observation; the saved URL state showed that action entered Page B. This is a distinct signature from OS focus routing, but no registered task or Solo/MA-ID/MA-SD controls exist yet.

A task should give each Actor an independent page/form goal, keep the top-level browser window constant in MA-SD, and evaluate exact per-tab state plus contamination. MA-ID should use equivalent independent browser fixtures. Do not call it validated until task goals, controls, reset, and oracle pass.

## Optional candidate — Window / Modal Ownership

**Round-1 status: KEEP candidate, SCRIPTED ONLY.** The pinned LibreOffice Guest repeatedly opened a native Save chooser with a separate X11 window, GtkFileChooserDialog role, transient parent identifying Writer, and _NET_WM_STATE_MODAL. Screenshot/accessibility observation and Escape dismissal worked. No two-Actor outcome has been measured.

A candidate pairs Writer Save As with an independent Calc edit. Solo checks each goal; MA-ID uses equivalent separate desktops; MA-SD opens the Writer modal while Calc's actor continues with its own valid goal. Evaluate both files, exact destination, dialog state and contamination. Promote only after joint feasibility and non-forced MA-SD interaction are demonstrated.

## Future work outside current tracks

- Observation invalidation isolated from lost-write consistency.
- Human interruption and safe resumption with a genuine independent human goal.
- Asynchronous commit, autosave and durability ordering.

Promote a future mechanism only when it has a distinct causal trigger and evaluator predicate, not merely a new application or actor pairing.

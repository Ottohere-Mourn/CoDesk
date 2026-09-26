# Positioning revision after novelty audit

**Status:** replaces the provisional novelty language in `docs/POSITIONING.md` for research-planning purposes. It does not change benchmark code or assert a priority claim.

## Decision

Keep the project only as a **narrow shared-GUI interaction benchmark hypothesis**, centered on independent actors contending for one live desktop’s global input/focus state. Withdraw broader claims about first multi-agent shared-workspace evaluation, shared-file interference, stale reads/writes, human-in-the-loop desktop work, or GUI+CLI workflows. Those areas have direct prior work: CoAgent, AgentRoom, CooperBench, STALE, ParaGUIBench, DeskCraft, SWE-Touch, and WeaveBench cover substantial portions (details in [NOVELTY_AUDIT.md](NOVELTY_AUDIT.md) and [OVERLAP_MATRIX.md](OVERLAP_MATRIX.md)).

The audited papers support a **candidate intersection**, not a verified first: distinct goal-bearing actors + one actual display/window focus/pointer/keyboard route + separately solvable objectives + programmatic joint-state and collateral-effect evaluation + explicit recovery measurement. The reviewed GUI work has multiple workers on separate desktops (ParaGUIBench), one GUI actor with a conversational simulator (DeskCraft), or one actor switching between GUI and CLI (WeaveBench). The live shared-state and composition benchmarks are CLI/code focused (CoAgent, AgentRoom, CooperBench, STALE). No reviewed work combines all of those properties. Expand search before publication claims.

## Proposed paper question

> When independent principals act on one live graphical desktop, which shared-input and shared-state interleavings prevent otherwise solvable tasks from both completing, and which coordination or recovery policies restore the joint task invariants at what cost?

This is narrower than “multi-agent computer use” and tests an interaction mechanism that separate VMs, common folders, conversational interruptions, and within-agent tool switching do not isolate.

## Contributions that remain plausible

1. **A precise runtime topology and protocol.** Two separately goal-directed actors issue attributed actions against one live desktop instance, not separate VMs. The event log records actor identity, observation version, foreground window/focus, action target, timestamps/causal order, and resulting application/workspace state.
2. **Causal interference measurement.** For each principal and the joint task, compare isolated runs, serialized joint runs, and controlled concurrent interleavings. Record whether another actor’s action caused a goal regression or made an observation stale. Report actor success, joint invariant success, collateral regressions, recovery success, and action/time overhead.
3. **A GUI-specific contention axis.** Test focus/foreground-window competition and input routing as an explicit, observable shared resource, alongside file/application state. Include separate-desktop and single-actor perturbation controls so the mechanism is distinguishable from ParaGUIBench and OSWorld-Noisy.
4. **An executable task/evaluator protocol.** Each task contains two independent goals, per-actor acceptance predicates, compatible joint-state predicates, reset state, deterministic interaction schedule(s), and hidden state-derived checks. Evaluators inspect final application state and event provenance without using an LLM judge as the success oracle.

These are candidate contributions only. A small number of deterministic examples can validate harness feasibility but cannot substantiate broad empirical conclusions. Do not count model breadth, task count, GPU use, or an orchestrator alone as the principal research contribution.

## What to do with current V0 cases

### Keep and strengthen: GUI + Human Replay focus competition

Use a single real desktop/display and one global input path. Human Replay must represent a second actor with an explicit, independently satisfiable intention and logged actions. It must change focus or window state through the same mechanism a person uses, not merely inject a scripted interruption message. The agent and replayed person should each have an individual success predicate; a joint predicate should expose when one actor accidentally acts in the other’s window or overwrites the other’s work. Add a no-contention/serialized control and at least one deterministic harmful interleaving plus a recoverable interleaving.

This is the strongest route to a distinct benchmark contribution relative to ParaGUIBench and DeskCraft. It remains unproven until one true end-to-end task demonstrates shared OS focus/input and the evaluator establishes independent success, causal interference, and recovery.

### De-emphasize or redesign: GUI + CLI CSV stale read/write

A generic shared CSV stale-read example substantially overlaps CoAgent’s live Kubernetes read/write anomalies, AgentRoom’s shared mutable filesystem, and CooperBench/STALE’s independent-vs-composed correctness logic. Keep it as a harness smoke or a contrast condition unless the app makes the GUI’s visible/cache state a necessary second consistency surface. If retained as a research task, require evidence such as: CLI changes backend data; GUI still displays an old state; a GUI actor acts on that stale observation; the joint application invariant fails; refreshing/reconciling repairs it. Compare with CLI-only and GUI-only controls. A plain CSV overwrite is insufficient.

## Task inclusion gates

Do not add a benchmark task unless it passes all gates:

- **Independent solvability:** each actor can complete its own goal alone from the same reset state, confirmed by scripted reference actors and, later, tested model/human actors.
- **Joint satisfiability:** a valid serial or coordinated schedule reaches a state satisfying both actor goals and all global invariants.
- **Interaction relevance:** at least one reproducible interleaving changes what an actor observes or where its input lands, causing a measurable collateral failure. Pure time jitter/noise does not qualify.
- **Recoverability:** the task defines how recovery success is distinguished from accidental final-state success and logs the cost/action history.
- **Evaluator isolation:** hidden state predicates are unavailable to actors and inspect final state independently of their narrative reports.
- **Causal control:** isolated, serialized, and concurrent conditions use the same task state and checks; interference is computed only among runs in which both independent goals succeed in isolation (following the methodological lesson from STALE).
- **Reproducibility:** reset, schedule, actor event source, application version, and expected final predicates are pinned. Non-deterministic external services are disabled or replaced by bounded recorded fixtures.

## Scope recommendation

**Continue conditionally** with one production-quality focus contention case and one secondary GUI/backend state-visibility case. Keep the existing CSV behavior only if the GUI state is truly observable and materially affects the correct action. Do not expand to a large taxonomy before the first case survives a direct comparison against ParaGUIBench, DeskCraft, OSWorld-Noisy, and CoAgent.

**Adjust or stop** if the shared focus case can be represented as one actor plus an exogenous interruption, if Human Replay lacks an independent goal, or if the measured failure is only a filesystem conflict. In those outcomes, the defensible product is a small OSWorld interaction extension/protocol study, not a new broad shared-workspace benchmark novelty claim.

Before a paper claim, expand the search to multi-user remote desktop/VDI benchmarks, collaborative GUI agents, concurrent UI automation, and online workflow systems; locate or contact authors only through approved channels; inspect releases at a pinned revision; and compare exact task/evaluator implementations. State the audited date and write “we found no prior work combining…” rather than “first-ever” unless that broader audit supports more.

## Suggested replacement positioning paragraph

> Existing work studies parallel GUI workers that exchange files across isolated desktops (ParaGUIBench), user-interactive desktop tasks with one acting GUI agent (DeskCraft), hybrid GUI/CLI workflows within one actor (WeaveBench), and concurrent agents sharing mutable software or application state (AgentRoom, CoAgent, CooperBench, STALE). We investigate a narrower setting: independently goal-directed principals issuing actions through the same live desktop input/focus state, and measure per-principal completion, joint invariants, cross-actor regressions, and recovery with executable state checks. Our novelty claim is limited to this combination and remains subject to a broader artifact-level comparison.

## Evidence checklist before submission

- Confirm the focus target is literally shared: record one desktop/display instance and global input/focus identifiers.
- Publish the two actors’ prompts/instructions, action traces, task reset fixtures, and evaluator source.
- Show individual-only, serialized-both, concurrent-both, and recovery outcomes with matched reset state.
- Show at least one interleaving in which both solo baselines pass but the uncoordinated joint run violates a hidden invariant; quantify incidence only after sufficient repeated runs.
- Report whether the actor was a model, deterministic script, or real human replay. Keep actor/source labels in every event.
- Conduct a final citation and repository audit after checking the full paper version current at submission time.

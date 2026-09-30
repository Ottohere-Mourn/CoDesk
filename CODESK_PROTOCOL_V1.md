# CoDesk Benchmark Protocol V1

## 1. Protocol status

This document freezes the V1 experimental design for CoDesk, the Collaborative Desktop Use Benchmark. It defines the research question, condition topology, task tracks, score definitions, failure attribution and initial experiment matrix. It does not add tasks or change the existing task version `2.0.0` evaluators. Existing benchmark results remain historical evidence and are not re-scored under this protocol.

V1 is a compact mechanism benchmark. Its primary claim is limited to whether sharing one live desktop session causes additional interaction failures beyond multi-agent execution on independent desktops. It is not a broad leaderboard or a claim about all computer-use agents.

## 2. Research question

**When independently goal-directed Computer-Use Agents use the same live desktop session, how does shared control of GUI resources affect each actor's goal completion, joint state integrity and recovery, compared with the same actors using independent desktop sessions?**

The primary unit is a matched task episode block: same task instance, actor goals, model/runtime, task-relevant initial workspace and application state, schedule and evaluator, with desktop topology changed between MA-ID and MA-SD. Workspace equivalence is semantic and task-scoped; it does not require physical filesystem identity when actors do not need to observe each other’s persistent file changes.

## 3. Scope

CoDesk V1 evaluates two or more actors with independent, individually solvable goals. At least one actor must interact through a GUI. V1 separates:

- **Desktop-session interaction:** focus, keyboard, pointer, clipboard and active application context.
- **Shared application-state interaction:** cached observations, concurrent updates, revisions and durable final state.

GUI+GUI is the primary modality for desktop-session mechanisms. GUI+CLI is a supporting cross-interface track for shared-state consistency. A primary GUI+GUI claim requires two independently run GUI Agents with separate goals. Scripted actors may validate mechanics; GUI+Human Replay evidence remains a separately labeled actor composition and does not substitute for the two-Agent comparison.

## 4. Experimental conditions

### Solo baseline

Run each actor separately from the same task version and initial fixture, with no partner actions. Each actor must pass its own goal before the task is eligible for shared-condition analysis. Solo completion establishes independent solvability; it is not included as an extra actor in a shared episode.

### MA-ID: Multi-Agent Independent Desktop

- Each GUI actor controls its own independent desktop session, with independent window focus, keyboard, pointer and session clipboard.
- Actors execute the same declared schedule and goals as in MA-SD.
- Both sessions start from equivalent task fixtures and preserve the same task-relevant workspace state. Separate per-Guest local filesystems are allowed when cross-Actor file visibility is not part of either goal.
- If a task requires one Actor to observe another Actor’s persistent update, use the same authoritative backend in MA-ID and MA-SD; never vary backend topology with desktop topology.
- This condition removes a common GUI control surface while preserving the task’s declared workspace semantics.

### MA-SD: Multi-Agent Shared Desktop

- All GUI actors act through the same live desktop session, Guest, active-window state, keyboard and pointer. Session-global resources such as clipboard are shared.
- Each actor retains its own task instruction and actor identity but receives observations from the current shared session on its scheduled turn.
- Actors and evaluator use the same task fixture and task-relevant state. In one Guest they naturally share its local filesystem and application processes; record this topology explicitly. A direct MA-ID comparison is eligible only when the relevant initial workspace and goal semantics match.

### Matched controls

MA-ID and MA-SD use the same task instance, actor-to-goal mapping, model checkpoint and settings, application versions, semantically equivalent task-relevant workspace/state, action budget, schedule, trigger and evaluator. The desktop-session topology changes. For tasks requiring cross-Actor persistence, the authoritative backend must also be identical; for independent per-Actor artifacts, equivalent seeded local filesystems are permitted and claims are limited to the shared GUI control effect. No condition forces an actor to make an invalid action. Scheduler or recovery actions are attributed separately from actor actions.

## 5. Task tracks

| Track | Status in V1 | Purpose |
|---|---|---|
| A. GUI Control Contention | **Core** | Test whether actors' valid focus/window actions misroute another actor's GUI input on one shared desktop. Existing focus-routing task is the validated anchor. |
| B. Desktop Resource Ownership | **Extension** | Test session-global transient resources such as clipboard or selection while focus remains correct. Design candidate only; not yet a validated task. |
| C. Shared State Consistency | **Core supporting control** | Test GUI/CLI access to one authoritative backend and distinguish backend lost-update failures from desktop-session contention. Existing stale-merge task is the validated anchor. |

The detailed scope and lifecycle gates are in [`TASK_TRACK_SPEC.md`](TASK_TRACK_SPEC.md). Application/object context, observation invalidation isolated from lost writes, human interruption/resumption, and asynchronous durability are **future work**, not V1 core results.

The existing `SWCUB-FOCUS-ROUTING-001` GUI+Human Replay case is prior mechanism evidence only. V1's primary Track A claim remains untested until a two-GUI-Agent comparison is specified and passes its inclusion gates.

## 6. Evaluation metrics

Use the same deterministic, post-episode programmatic evaluator in Solo, MA-ID and MA-SD. The evaluator reads authoritative state after actors stop; it does not expose expected values or private state to actors. Do not use an LLM judge as the success oracle.

### Primary outcomes

- **Actor goal success:** exact pass/fail for each actor's own goal.
- **Joint success:** all actor goals and task integrity invariants pass together.
- **Shared-desktop penalty:** `MA-ID joint success rate − MA-SD joint success rate`, reported by task with matched uncertainty. Positive values indicate lower success under a shared desktop.

### Interaction outcomes

- **Interference incidence:** episodes with a trace-supported partner-caused goal deviation, unintended side effect, misrouted input, overwritten transient resource or invalidated state assumption, divided by eligible shared-condition episodes. Mere temporal succession does not prove causation.
- **State consistency:** final invariant pass rate and counts of missing, duplicated, overwritten or wrong-version fields/objects. Apply to Track C and any task with persistent shared state.
- **Recovery success:** among episodes with a detected disturbance or deviation, proportion that return to a state satisfying all actor goals and integrity invariants within the task budget.
- **Recovery cost:** actor actions and wall-clock time from the first observable deviation/detection to restored valid state. Report separately from total post-interference decisions; those decisions alone are not recovery.
- **Efficiency/context metrics:** total actor actions, scheduler actions, elapsed time, focus-conflict events, wrong-target inputs, and task-specific resource conflicts. Preserve the underlying event IDs for audit.

Report actor-level outcomes as well as joint success. Do not collapse all errors into one score or label a resource conflict as a coordination failure without evidence of a failed coordination policy.

## 7. Failure taxonomy

Every failed episode receives one or more evidence-backed labels:

1. **Actor capability/task failure:** the actor cannot complete its own goal in Solo or fails without a preceding partner-caused state change.
2. **Grounding/input-routing failure:** the intended target is misidentified or input reaches the wrong window/control; identify whether this occurred in Solo or after a shared-session transition.
3. **Shared-control conflict:** focus, keyboard, pointer or active-window ownership changed between observation and action and caused a wrong-target effect.
4. **Transient-resource conflict:** clipboard, selection or another session-global temporary resource was replaced or consumed by another actor.
5. **Observation/stale-state failure:** the actor acted on an outdated observation or application snapshot. Separate stale perception from a persistent lost update when evidence permits.
6. **Shared-state consistency failure:** lost update, duplicate, overwrite, invalid merge or violation of a declared revision/integrity invariant.
7. **Recovery failure:** a disturbance was observed or detectable but joint goals/invariants were not restored within the declared budget. Record the triggering mechanism separately.
8. **Scheduler/protocol failure:** actual actor order, trigger, budget, desktop binding or declared scheduler intervention differs from the frozen protocol.
9. **Environment/reset failure:** Guest, application, backend or reset did not satisfy the task's declared initial/final-state contract.

Classify a failure as an interaction effect only when the partner action precedes a relevant state transition and the trajectory/evaluator support the causal link. Keep unresolved cases as `unattributed`; do not force them into an interaction category.

## 8. Experiment matrix

| Track | Solo controls | MA-ID | MA-SD | Primary contrast |
|---|---|---|---|---|
| A. GUI Control Contention (Core) | GUI Agent A solo; GUI Agent B solo | Both pursue independent goals on separate desktops | Same goals/schedule on one desktop | Joint-success penalty, wrong-window input, cross-window contamination and recovery |
| B. Desktop Resource Ownership (Extension) | Each GUI actor solo with its own clipboard/selection | Independent session resources; shared task backend only if needed | One session clipboard/selection | Resource substitution, goal/integrity violations and recovery; run only after a task is specified and scripted controls validate |
| C. Shared State Consistency (Core supporting control) | GUI actor solo; CLI actor solo | Separate desktops/processes, same authoritative backend | GUI and CLI share the same Guest/session backend | Field-level consistency and whether backend conflict changes with desktop topology |

### Execution order and repetition

1. For each task, validate initial state, each actor's Solo goal, joint feasibility, evaluator negative-state detection and reset using scripted actors.
2. Run matched MA-ID/MA-SD episodes with counterbalanced actor order and actor-to-goal assignment. Use paired task seeds/schedules; freeze all non-topology variables.
3. The initial model comparison uses the existing fixed OSWorld V2.1 `Qwen3VLAgent` pipeline only after both actors pass Solo. Begin with five matched repeats per task-condition as a diagnostic pilot. These counts do not support a benchmark-wide or statistical-performance claim; preserve outcomes and uncertainty and determine any larger confirmatory sample before interpreting results.
4. Keep recovery behavior autonomous in the primary three-condition matrix. A separately defined recovery-aware scheduler condition is a later ablation and must not be merged into MA-ID or MA-SD.

### Evidence required per episode

Record task/version/seed, actor IDs/roles/goals, condition and desktop/backend identities; initial and final state; actor and scheduler actions; observation/screenshot digests; focus and resource events available for that task; evaluator output; recovery trace; reset proof; and full provenance. Preserve failures. Never overwrite prior artifacts.

## 9. Interpretation and claim boundary

The primary evidence for an independent shared-desktop dimension is a task-specific MA-ID versus MA-SD difference that is accompanied by the predicted interaction trace. Strong construct evidence is a mechanism-by-topology pattern: focus and session-resource tasks degrade specifically in MA-SD, while the shared-backend consistency task may fail in both multi-agent topologies.

If every task degrades similarly, investigate generic scheduling or execution differences. If no MA-ID/MA-SD difference is observed, report that result; do not infer a shared-desktop effect from scripted negative controls alone. V1 is a compact mechanism demonstration, not a broad claim about all agents, applications or human behavior.

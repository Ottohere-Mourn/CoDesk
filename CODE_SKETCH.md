# CoDesk Code Sketch

This sketch describes the current framework boundary and intended extension path. It is architectural documentation only; it does not change runtime code, tasks or evaluators.

## Episode flow

```text
Versioned Task Instance
        │ declares goals, shared resources, trigger and schedule
        ▼
Environment Adapter ─── reset / observe / act / snapshot / close
        │ one environment_id and one live Guest per episode
        ├───────────────┐
        ▼               ▼
 Actor A             Actor B       independent ActorContext objects
        └──────┬────────┘           same underlying adapter/session
               ▼
      Turn Scheduler / Orchestrator
      deterministic triggers; optional declared recovery hook
               │
        actor-attributed Event Logger
        actions, observations, focus/context and state transitions
               │ actors stop; reset proof collected
               ▼
      Hidden Programmatic Evaluator
      per-actor goals + joint integrity + scenario/reset result
```

## Existing module map

| Component | Current location | Responsibility |
|---|---|---|
| Environment contract and adapters | `swcub/environment.py`, `swcub/osworld_adapter.py` | Bind all actors to one shared real environment; expose controlled observation and action methods. |
| Actor interface and role context | `swcub/actors.py` | Provide actor identity, capabilities and access to the public environment interface without evaluator state. |
| Orchestration / scheduling | `swcub/orchestrator.py`, `swcub/turn_scheduler.py` | Execute reproducible actor turns, triggers, budgets and declared recovery interventions. |
| Event and provenance records | `swcub/core.py`, `swcub/provenance.py` | Attribute actions to actors and preserve task, environment, source and resource provenance. |
| Evaluator | `swcub/evaluator.py` plus Guest-specific evaluator bindings | Inspect authoritative final state after actor execution and score goals and integrity constraints. Existing evaluator rules are frozen for current task versions. |
| Task declarations | `swcub/instances.py`, `tasks/` | Define versioned goals, initial state, roles, shared resources, schedules and evaluator binding. |
| Runtime and episode scripts | `infra/`, `env/`, `scripts/` | Provision the pinned guest/runtime and produce isolated episode evidence. |

## Extension boundary

1. Add a versioned task specification and isolated fixture for a distinct interaction mechanism.
2. Reuse the existing actor interface and native OSWorld agent pipeline where applicable; task work must not silently introduce a second planner or grounding stack.
3. Bind all actors to the same adapter instance and record the shared environment identity in episode metadata.
4. Express timing as deterministic event triggers or explicit barriers. Record actor and scheduler actions separately.
5. Keep hidden expected state and evaluator callbacks outside actor contexts. Evaluate final state and reset after actors stop.
6. Preserve all prior task instances, results and artifact paths. A changed goal, trigger, recovery rule or evaluator predicate requires a new version.

## Future event fields to consider

New observability fields should be introduced through an explicit schema version and reviewed for actor leakage. Candidate fields include active-window ID, application-object ID, clipboard generation, observation digest/revision, read/write revision and persistence/commit status. These are design candidates; current logs do not necessarily capture all of them.

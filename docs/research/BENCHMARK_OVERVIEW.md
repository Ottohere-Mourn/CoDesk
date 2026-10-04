# CoDesk Benchmark Overview

## Research question

Is sharing a live desktop session an independent evaluation dimension for computer-use agents? Traditional GUI benchmarks usually give one agent exclusive control of a desktop. That setup measures task completion but cannot reveal failures caused by another independent actor changing the state on which the first actor relies.

CoDesk studies independent actors with separate goals in a non-exclusive desktop workspace. The central comparison is **MA-ID vs MA-SD**: independent desktop/input sessions versus one shared live desktop session. Solo runs establish that each goal is independently solvable. The comparison holds task-relevant state, actor goals, schedule, budgets, applications, backend, evaluator, and reset protocol equivalent; only desktop-session topology should differ. A shared filesystem is not the definition of MA-SD.

## Interaction mechanisms

The current offline suite groups workflows into five families:

1. Focus and input routing
2. Clipboard state
3. Application context
4. Selection and active object
5. Undo/redo history

These families describe distinct hidden state that can redirect or invalidate a valid next action. Whether a workflow has passed a real Guest or model gate must be checked in the [current handoff](../handoff/HANDOFF.md), not inferred from its presence in the manifest.

## Measurements

Report four concepts separately:

- **Exposure:** a natural or scheduled opportunity for shared state to change.
- **Observed interference:** trace and state evidence that a partner action changed the resource/context relevant to another actor.
- **Outcome:** per-actor goal success, joint success, and non-target integrity from the programmatic oracle.
- **Recovery:** actor actions after the event and whether the exact goals were restored.

A scheduled opportunity alone is not observed interference. Failure without an evidence chain remains model/task failure or unattributed. The evaluator reads hidden state after actors finish and does not rely on an LLM judge.

## V1 inventory and evidence boundary

The final offline manifest contains 5 families, 30 workflow templates, and 600 fixed instances: 20 per workflow. Its task domains cover Writer, Calc, Browser, and Terminal. This is an offline suite count, not a count of real Guest or model runs. `benchmarks/codesk_v1_final/` is canonical V1; `benchmarks/codesk_v1/` is a legacy prototype.

The current project status is **OFFLINE_FINAL_SUITE_READY**, not **FULL_HANDOFF_READY**. The 5-family real Guest smoke and formal model evaluation remain outstanding. Historical model/Guest results apply only to the exact task versions and protocols recorded in their reports.

## Planned paper tables

These are planned analyses; no formal results are asserted here.

1. **Benchmark statistics:** families, workflows, fixed instances, domains, operation types, and evidence level.
2. **Representative agent comparison:** Solo / MA-ID / MA-SD outcomes, broken down by family; exposure, interference, recovery, and outcome shown separately.
3. **Multi-agent/model leaderboard:** matched protocols and per-model/per-family results, with invalid infrastructure episodes reported separately.
4. **Actor-count scaling:** a small subset comparing increasing actor counts after the core two-condition protocol is validated.

For causal interpretation, task version, backend, actor goals, schedule, budgets, application state, evaluator, and reset must remain fixed between MA-ID and MA-SD. See [CODESK_PROTOCOL_V1.md](../../CODESK_PROTOCOL_V1.md) and [EVALUATION.md](../../docs/EVALUATION.md).

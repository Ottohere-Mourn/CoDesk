# CoDesk Handoff

**Status:** `OFFLINE_FINAL_SUITE_READY`; **not** `FULL_HANDOFF_READY`. The canonical V1 suite is `benchmarks/codesk_v1_final/`. No claim is made that 30 workflows have completed live Guest or model validation.

## What is ready

- Five family definitions, 30 workflow templates, and 600 fixed task instances (20 per workflow) in the final offline suite.
- Four task domains: Writer, Calc, Browser, and Terminal.
- Final suite manifest, fixtures, evaluator specifications, metadata, and runtime plans.
- Shared actor/environment/orchestrator contracts, runtime binding layer, provenance, runner CLI, and result aggregator.
- Historical evidence and failures retained in reports/artifacts; each result must be read with its task version, topology, and evidence level.

The older `benchmarks/codesk_v1/` tree is a legacy 15-workflow prototype. Do not use it as the current V1 task catalog.

## Experiment sequence for the next owner

### A. Five-family quick smoke

Start with a resource/ownership check and one bounded, scripted Guest episode per selected family. Confirm fixture identity, app readiness, screenshot/observation, a real UI action, exact evaluator, provenance, artifact capture, and reset. The currently documented A6000 launcher is a legacy Writer/Calc smoke; it is not yet the required five-family gate. Record unsupported workflow bindings as blocked rather than substituting a fake backend.

### B. Thirty-workflow smoke

After A passes, run one scripted Solo A/B and the minimum joint-control cases for every workflow. Aggregate readiness failures separately from task outcomes. Do not count runtime-plan compilation as Guest validation.

### C. Qwen baseline

Once the Guest/runtime gate is stable, run the fixed Qwen baseline first under Solo, then matched MA-ID and MA-SD. Hold task version, actor goals, backend, schedule, budgets, prompts, model configuration, evaluator, and reset fixed. Preserve all attempts; classify `INVALID_INFRA` separately. Report exposure, observed interference, recovery, and final outcome separately.

### D. Other agent/model leaderboard

Only after Qwen protocol stability, add community agents through the existing adapter seam. Keep model-specific configuration fixed and report per-family and per-topology results. This is future work; no new adapter is implemented here.

### E. Small actor-count scaling subset

Run N=3/4 only on a small, already validated subset after the two-actor causal comparison is reproducible. Keep task, backend, scheduling policy, budget accounting, and evaluator comparable; label scaling as a separate experiment.

## Allowed fixes and frozen benchmark semantics

The next owner may fix runtime, readiness, adapter, resource, artifact, and reset bugs. Preserve the failure evidence and rerun the affected control.

Do not silently change task semantics, oracle/evaluator criteria, family definitions, or treatment semantics. A semantic change requires a new task/suite version and fresh validation. Do not equate reset success with task success, scripted results with model results, or scheduled exposure with observed interference.

## Immediate gates

1. Read `docs/getting-started/QUICK_START.md` and check host/resource ownership before launching anything.
2. Run final-manifest offline audit from a clean checkout.
3. Verify the exact A6000 Guest image/runtime and run the bounded environment smoke.
4. Select one representative workflow per family and close its scripted Guest path.
5. Complete the 5-family gate before the 30-workflow gate; stop and preserve evidence at the first infrastructure blocker.
6. Begin Qwen only after valid Solo and reset/provenance gates; then use matched MA-ID/MA-SD.

Until these gates complete, describe the handoff as partial and keep `FULL_HANDOFF_READY` false.

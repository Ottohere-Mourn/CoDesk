# CoDesk Batch Runner V1

## Status

The deterministic planner, 15-entry workflow runtime registry, manifest filter, bounded infrastructure retry policy, resume scan, result schema, and aggregator are implemented offline. `run_benchmark.py --execute` now dispatches per-run through the registry; a missing adapter becomes a task-scoped `ADAPTER_MISSING`, never a global abort. Current Guest runners still use static task fixtures, and there is no registered concrete A6000 Guest backend/scheduler. Without `SWCUB_RUNTIME_EXECUTOR_FACTORY=module:factory`, each selected run is recorded as `BLOCKED_RUNTIME_BACKEND` and no Guest starts. The plan layer is ready; Guest integration and validation remain before real execution/model runs.

## Plan/resume

```bash
python scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1/manifest.jsonl \
  --workflow F-01 --topology solo --topology ma_id --topology ma_sd \
  --model qwen3vl --repeats 1 --offset 0 --limit 3 --dry-run \
  --plan /tmp/f01-plan.jsonl
```

For instance selection add `--instance INSTANCE_ID` (repeatable), `--family`, `--workflow`, or `--offset/--limit`. For resume, add `--resume --results PATH --max-infra-retries 2`. A completed PASS/TASK_FAILURE/MODEL_FAILURE base run is skipped. Only a result explicitly marked `INVALID_INFRA` is eligible for retry, with an attempt-specific run directory and a fixed maximum. Infrastructure-invalid attempts are excluded from task success denominators. Task/model failures are never retried as infrastructure. The plan records runtime adapter and plan hashes, schedule policy, actor set, topology, family/workflow, artifact path, owner UID, and attempt.

`solo` expands to separate Actor A and Actor B runs. `ma_id` and `ma_sd` each use the same two-Actor schedule/config, differing only in the desktop-session topology contract. Actor list storage is N-extensible; V1 plan generation remains the two-Actor benchmark protocol.

## Runtime adapter gate

`--execute` no longer fails globally on a missing workflow adapter. All 15 workflow plan adapters are registered. To start a Guest, configure an explicit executor plugin implementing the adapter/backend lifecycle: consume the exact manifest instance, materialize the matching fixture, bind its private evaluator, implement clean reset and ownership-ledger recording, and preserve observation/action/events/artifacts. The adapter contract is in `swcub/runtime_v1.py`. Registration is explicit by workflow/version; no fallback to a static task is permitted. Plan adapters are not evidence of Guest runtime validation.

## Result aggregation

```bash
python scripts/aggregate_benchmark_results.py RUNS_ROOT --output-dir REPORT_DIR
python scripts/compile_runtime_suite.py
python scripts/run_smoke_suite.py --model qwen3vl --plan /tmp/codesk-smoke-plan.jsonl
```

Reads `*/result.json`, excludes `INVALID_INFRA` from outcome groups, and writes CSV/JSON/Markdown. Metrics retain scheduled exposure, actual exposure, observed interference, autonomous recovery, recovery success, Actor A/B and joint outcomes, action count, wall time and inference latency. No-exposure failure is not counted as observed interference. Missing metrics remain null/unknown.

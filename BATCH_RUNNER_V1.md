# CoDesk Batch Runner V1

## Status

The deterministic planner, manifest filter, bounded infrastructure retry policy, resume scan, result schema, and aggregator are implemented offline. **Live execution is fail-closed and not yet enabled.** Current Guest runners use static task fixtures and do not accept the generated per-instance manifest/oracle contract. The runner refuses `--execute` instead of silently running the wrong task. Therefore model/Guest burning is not the only remaining work: 15 manifest-to-runtime adapters and their reset/provenance checks are still required.

## Plan/resume

```bash
python scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1/manifest.jsonl \
  --workflow F-01 --topology solo --topology ma_id --topology ma_sd \
  --model qwen3vl --repeats 1 --offset 0 --limit 3 --dry-run \
  --plan /tmp/f01-plan.jsonl
```

For resume, add `--resume --results PATH --max-infra-retries 2`. A completed PASS/TASK_FAILURE/MODEL_FAILURE base run is skipped. Only a result explicitly marked `INVALID_INFRA` is eligible for retry, with an attempt-specific run directory and a fixed maximum. Infrastructure-invalid attempts are excluded from task success denominators. Task/model failures are never retried as infrastructure. The plan records run config hash, actor set, topology, family/workflow, artifact path, owner UID, and attempt.

`solo` expands to separate Actor A and Actor B runs. `ma_id` and `ma_sd` each use the same two-Actor schedule/config, differing only in the desktop-session topology contract. Actor list storage is N-extensible; V1 plan generation remains the two-Actor benchmark protocol.

## Runtime adapter gate

`--execute` currently exits with `LIVE_EXECUTION_BLOCKED` before creating a Guest. To enable a workflow, an adapter must consume the exact manifest instance, materialize the matching fixture, bind its private evaluator, implement clean reset and ownership-ledger recording, and preserve observation/action/events/artifacts. Registration must be explicit by workflow/version and validated offline plus Guest before enablement. No fallback to a static task is permitted.

## Result aggregation

```bash
python scripts/aggregate_benchmark_results.py RUNS_ROOT --output-dir REPORT_DIR
```

Reads `*/result.json`, excludes `INVALID_INFRA` from outcome groups, and writes CSV/JSON/Markdown. Metrics retain scheduled exposure, actual exposure, observed interference, autonomous recovery, recovery success, Actor A/B and joint outcomes, action count, wall time and inference latency. No-exposure failure is not counted as observed interference. Missing metrics remain null/unknown.

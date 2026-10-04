# CoDesk Quick Start

This guide distinguishes offline checks from Guest execution. Commands below use the current CLI arguments. No Guest or model was launched while preparing this guide.

## 1. Offline final-suite validation

Requires the project Python dependencies to be installed. This validates manifest records, fixture/evaluator hashes, and positive/negative oracle controls; it does not launch a Guest or model.

```bash
python scripts/audit_instance_suite.py \
  benchmarks/codesk_v1_final/manifest.jsonl \
  --suite-root benchmarks/codesk_v1_final \
  --output /tmp/codesk-v1-audit.json
```

The existing `scripts/offline_self_test.py` is an older production-v1 test bundle that targets `benchmarks/codesk_v1/`; it is not a substitute for auditing `benchmarks/codesk_v1_final/`.

## 2. Plan one workflow without a Guest

The planner accepts `--manifest`, `--suite-root`, `--workflow`, `--topology`, `--model`, `--plan`, and `--dry-run`. This writes a run plan under `/tmp` and does not launch a Guest:

```bash
python scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1_final/manifest.jsonl \
  --suite-root benchmarks/codesk_v1_final \
  --workflow F-01 --topology solo --model qwen3vl \
  --plan /tmp/codesk-f01-solo-plan.jsonl --dry-run
```

`--dry-run` confirms plan/adapter compilation only. It does not prove Guest readiness or live task execution.

## 3. Real Guest smoke

**PENDING REAL-GUEST VALIDATION.** The repository has a bounded legacy Writer/Calc launcher:

```bash
bash scripts/run_a6000_single_worker_smoke.sh
```

It runs `configs/a6000_writer_calc_solo_smoke.json` through the existing coordinator after checking Docker/KVM/assets and refusing to proceed when project-labeled containers are present. This is an environment/Writer-Calc smoke, not a completed 5-family smoke and not model evidence. Confirm resource availability and ownership immediately before running it.

## 4. Execute one final-suite workflow

**PENDING REAL-GUEST VALIDATION.** The generic CLI accepts the following one-workflow execution shape; execution requires the registered A6000 runtime executor, Guest assets/permissions, and a validated workflow binding:

```bash
python scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1_final/manifest.jsonl \
  --suite-root benchmarks/codesk_v1_final \
  --workflow F-01 --topology solo --model qwen3vl --repeats 1 \
  --results runs/f01-solo --plan runs/f01-solo/plan.jsonl \
  --execute --backend a6000
```

The `a6000` backend is a real execution selection, not a dry-run. Start with the bounded Guest launcher above; do not treat a compiled runtime plan as proof that every final workflow is executable.

## 5. Full run and resume

**PENDING REAL-GUEST VALIDATION and workflow coverage review.** The CLI supports repeated topologies and `--repeats`; a small pilot-shaped command is shown below. Remove `--limit 1` only after the workflow subset has passed live smoke and the experiment plan is approved.

```bash
python scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1_final/manifest.jsonl \
  --suite-root benchmarks/codesk_v1_final \
  --topology solo --topology ma_id --topology ma_sd \
  --model qwen3vl --repeats 1 --limit 1 \
  --results runs/pilot --plan runs/pilot/plan.jsonl \
  --execute --backend a6000
```

To resume the same result root using the implemented `--resume` flag, rerun the command with `--resume` added before `--execute`. The runner skips terminal statuses and tracks bounded `INVALID_INFRA` retries according to `--max-infra-retries`. Confirm the plan and result root before any live run.

### Full V1 suite invocation

**PENDING REAL-GUEST VALIDATION. Do not launch until the 5-family/30-workflow smoke, runtime binding review, and resource plan pass.** The current CLI accepts this full-suite shape; it expands the 600 fixed instances across all three topologies at one repeat each and can create a large run tree:

```bash
python scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1_final/manifest.jsonl \
  --suite-root benchmarks/codesk_v1_final \
  --topology solo --topology ma_id --topology ma_sd \
  --model qwen3vl --repeats 1 \
  --results runs/v1-qwen --plan runs/v1-qwen/plan.jsonl \
  --execute --backend a6000
```

This command is documented from the parser and is not a claim that every workflow has a validated live executor. Stage the suite through the bounded gates above before considering this run.

## 6. Aggregate results

The aggregator consumes per-run `result.json` files and excludes `INVALID_INFRA` from success denominators:

```bash
python scripts/aggregate_benchmark_results.py \
  runs/pilot --output-dir runs/pilot/aggregate
```

Aggregation is only meaningful for complete, provenance-backed run artifacts. Keep scripted, model, and invalid-infrastructure episodes distinguishable.

## Runtime prerequisites and boundaries

Guest execution requires the supported OSWorld V2.1 Guest environment, Docker/KVM permissions, pinned runtime assets, and verified resource ownership. See [ENV_SETUP.md](../archive/design/ENV_SETUP.md) and [A6000 environment check](../../scripts/a6000_environment_check.sh). Model execution additionally requires a healthy configured inference endpoint. Do not infer readiness from this document; the live Guest smoke and Qwen baseline remain pending.

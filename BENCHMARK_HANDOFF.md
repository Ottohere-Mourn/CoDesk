# CoDesk Benchmark V1 Handoff

Read this file first. Canonical checkout is A6000: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, branch `v0`. The repository contains a frozen five-family / 15-workflow scope and a generated 600-row fixed candidate suite. This is a data-production milestone, not a claim that all rows have passed Guest execution.

## Evidence boundary

- Workflow history and Qwen evidence are summarized in root `WORKFLOW_SUITE_V1.md`, `QWEN_FAMILY_PILOT_REPORT.md`, `FAMILY_EXPANSION_V1_REPORT.md`, and `MATRIX_WORKFLOW_IMPLEMENTATION_V1.md`.
- Five added workflows are included with truthful levels: F-N1 `guest_solo` (Solo A/B only, one each); C-N1/A-N1/S-N1/U-N1 `offline`. Their full Solo/MA-ID/MA-SD/recovery runtime gate is incomplete.
- 45 validation samples passed offline generation/hash/positive-negative oracle checks. This does not verify application readiness or GUI action feasibility.
- The fixed suite has 600 rows (15 × 40); it is 15 workflow templates with fixed semantic instances, not 600 workflows or 600 independently Guest-validated tasks.
- The registry now compiles all fixed instances into runtime plans. Existing Guest runners still use static fixtures; a concrete manifest-driven OSWorld Guest backend/scheduler is not yet registered. Without an executor plugin, `--execute` records per-run `BLOCKED_RUNTIME_BACKEND` and does not launch a Guest. The current remaining work is **Guest backend integration and real smoke, then model runs**, not model runs alone.

## Handoff gates

- **OFFLINE_HANDOFF_READY:** all 15 workflow plan adapters are registered, all 600 instances compile, and runtime/runner/aggregator/offline tests pass. This authorizes offline preparation and review only.
- **FULL_HANDOFF_READY:** additionally requires the five-family `smoke_suite.jsonl` to pass as real Guest runs through a concrete backend, with reset, ownership ledger, provenance and artifacts verified.

**Current gate state:** OFFLINE_HANDOFF_READY is met: 15 registered plan adapters, 600/600 compiled plans, 45 positive and 45 negative offline oracle controls, runner resume/retry and aggregator self-tests pass. FULL_HANDOFF_READY is not met: the A6000 OSWorld Guest backend/scheduler is not registered and no Guest smoke ran in this phase.

## Environment check

On A6000, inspect (do not assume): `git status --short --branch`, `scripts/a6000_env.sh`, pinned OSWorld V2.1 paths, Docker/KVM access, Guest image and provider image. Run `python scripts/offline_self_test.py` before editing. Never use Docker prune; follow `RESOURCE_SAFETY.md`.

On 4090, the previously verified inference arrangement was Qwen3-VL-30B-A3B-Instruct BF16 on two 4090s, private worker bound to loopback port 15485 and reached by A6000 through SSH reverse forwarding. Reference `REMOTE_INFERENCE_4090_A6000.md`; re-check GPU ownership, worker config, local model path and SSH connectivity each session. GPU indices are not assumed. Do not launch a worker on a card with another user's compute PID.

## Immediate execution order

1. Verify clean repository state and offline self-test; preserve artifacts and old results.
2. Review `benchmarks/codesk_v1/manifest.jsonl`, `metadata/diversity-audit.json`, and `validation_45/`. Verify hashes.
3. Review `benchmarks/codesk_v1/runtime_plans.jsonl` and `RUNTIME_ADAPTER_AUDIT.md`; compilation is not Guest validation.
4. Implement/register the concrete A6000 OSWorld `GuestBackend` and turn scheduler. Verify exact fixture materialization, GUI readiness, private evaluator, reset, resource ownership and artifacts.
5. Run `scripts/run_smoke_suite.py --execute` only after backend readiness, with one representative per family. Verify reset/provenance before marking FULL_HANDOFF_READY.
6. After smoke readiness, connect the existing remote Qwen inference path. Start with one Solo run per actor; then run topology comparisons using fixed goals, schedule, budgets and evaluator.
7. Resume from run artifacts, not by overwriting old results. Retry only `INVALID_INFRA`, within the configured cap.
8. Aggregate with `scripts/aggregate_benchmark_results.py`; review exposure, interference, outcome and recovery as separate measurements.

## Existing command entrypoints

Offline generation:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
source scripts/a6000_env.sh
"$CODESK_PYTHON" scripts/offline_self_test.py
"$CODESK_PYTHON" scripts/compile_runtime_suite.py
"$CODESK_PYTHON" scripts/generate_suite.py --quota-per-workflow 40 --seed 2026 --output /tmp/codesk-v1-check
```

Planner-only dry run:

```bash
"$CODESK_PYTHON" scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1/manifest.jsonl \
  --workflow F-01 --topology solo --topology ma_id --topology ma_sd \
  --model qwen3vl --repeats 1 --dry-run --plan /tmp/f01-plan.jsonl
```

Without an explicit `SWCUB_RUNTIME_EXECUTOR_FACTORY=module:factory`, `--execute` marks each selected run `BLOCKED_RUNTIME_BACKEND` and does not start a Guest. Do not describe the handoff as “models only remain.”

## Result interpretation

Keep these independent: scheduled exposure, actual exposure, observed interference, actor goal outcomes, and autonomous recovery. Do not label a failure as shared-state interference without exposure/observation evidence. `INVALID_INFRA` is excluded from task/model success. MA-ID and MA-SD must keep task-relevant fixture, schedule, goals, budget, model, prompt and evaluator equivalent; only desktop-session sharing changes.

## Ownership / no-go actions

Read `RESOURCE_SAFETY.md`. Never stop another user's process, remove unknown resources, prune Docker, push without explicit authorization, change historical scores, or overwrite artifacts. If access/readiness fails, preserve exact logs and classify infrastructure invalid; continue independent offline work.

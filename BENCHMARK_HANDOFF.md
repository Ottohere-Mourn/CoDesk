# CoDesk Benchmark V1 Handoff

Read this file first. Canonical checkout is A6000: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, branch `v0`. The repository contains a frozen five-family / 15-workflow scope and a generated 600-row fixed candidate suite. This is a data-production milestone, not a claim that all rows have passed Guest execution.

## Evidence boundary

- Workflow history and Qwen evidence are summarized in root `WORKFLOW_SUITE_V1.md`, `QWEN_FAMILY_PILOT_REPORT.md`, `FAMILY_EXPANSION_V1_REPORT.md`, and `MATRIX_WORKFLOW_IMPLEMENTATION_V1.md`.
- Five added workflows are included with truthful levels: F-N1 `guest_solo` (Solo A/B only, one each); C-N1/A-N1/S-N1/U-N1 `offline`. Their full Solo/MA-ID/MA-SD/recovery runtime gate is incomplete.
- 45 validation samples passed offline generation/hash/positive-negative oracle checks. This does not verify application readiness or GUI action feasibility.
- The fixed suite has 600 rows (15 × 40); it is 15 workflow templates with fixed semantic instances, not 600 workflows or 600 independently Guest-validated tasks.
- Live batch `--execute` is intentionally blocked until parameterized per-workflow runtime adapters are implemented. Thus the current remaining work is **runtime adapters and their validation, then model runs**, not model runs alone.

## Environment check

On A6000, inspect (do not assume): `git status --short --branch`, `scripts/a6000_env.sh`, pinned OSWorld V2.1 paths, Docker/KVM access, Guest image and provider image. Run `python scripts/offline_self_test.py` before editing. Never use Docker prune; follow `RESOURCE_SAFETY.md`.

On 4090, the previously verified inference arrangement was Qwen3-VL-30B-A3B-Instruct BF16 on two 4090s, private worker bound to loopback port 15485 and reached by A6000 through SSH reverse forwarding. Reference `REMOTE_INFERENCE_4090_A6000.md`; re-check GPU ownership, worker config, local model path and SSH connectivity each session. GPU indices are not assumed. Do not launch a worker on a card with another user's compute PID.

## Immediate execution order

1. Verify clean repository state and offline self-test; preserve artifacts and old results.
2. Review `benchmarks/codesk_v1/manifest.jsonl`, `metadata/diversity-audit.json`, and `validation_45/`. Verify hashes.
3. Choose one representative smoke row per family from `benchmarks/codesk_v1/smoke_suite.jsonl`.
4. Implement one manifest-driven adapter at a time, starting with an already evidenced workflow. Adapter must materialize exact fixture, set up the application, expose only GUI observations to actors, use its instance-bound private oracle, reset and prove reset, and log run ownership/provenance.
5. Only after the first adapter passes scripted Solo A/B, MA-ID and MA-SD controls plus reset, enable it in a registry; never route generated IDs through a static fixture runner.
6. Run the five-row `SMOKE_SUITE` across all enabled adapters. `run_benchmark.py --execute` remains blocked until adapters are explicitly registered.
7. After smoke readiness, connect the existing remote Qwen inference path. Start with one Solo run per actor; then run topology comparisons using fixed goals, schedule, budgets and evaluator.
8. Resume from run artifacts, not by overwriting old results. Retry only `INVALID_INFRA`, within the configured cap.
9. Aggregate with `scripts/aggregate_benchmark_results.py`; review exposure, interference, outcome and recovery as separate measurements.

## Existing command entrypoints

Offline generation:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
source scripts/a6000_env.sh
"$CODESK_PYTHON" scripts/offline_self_test.py
"$CODESK_PYTHON" scripts/generate_suite.py --quota-per-workflow 40 --seed 2026 --output /tmp/codesk-v1-check
```

Planner-only dry run:

```bash
"$CODESK_PYTHON" scripts/run_benchmark.py \
  --manifest benchmarks/codesk_v1/manifest.jsonl \
  --workflow F-01 --topology solo --topology ma_id --topology ma_sd \
  --model qwen3vl --repeats 1 --dry-run --plan /tmp/f01-plan.jsonl
```

Live execution is currently unavailable and must fail closed. Do not describe the handoff as “models only remain.”

## Result interpretation

Keep these independent: scheduled exposure, actual exposure, observed interference, actor goal outcomes, and autonomous recovery. Do not label a failure as shared-state interference without exposure/observation evidence. `INVALID_INFRA` is excluded from task/model success. MA-ID and MA-SD must keep task-relevant fixture, schedule, goals, budget, model, prompt and evaluator equivalent; only desktop-session sharing changes.

## Ownership / no-go actions

Read `RESOURCE_SAFETY.md`. Never stop another user's process, remove unknown resources, prune Docker, push without explicit authorization, change historical scores, or overwrite artifacts. If access/readiness fails, preserve exact logs and classify infrastructure invalid; continue independent offline work.

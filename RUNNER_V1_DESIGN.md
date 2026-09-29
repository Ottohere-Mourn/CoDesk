# CoDesk Runner V1 Design and Prototype

## Objective and boundaries

Runner V1 expands a frozen experiment config into an ordered episode queue, runs each independent episode in its own worker process and artifact directory, and aggregates results only after reports/provenance are saved. It does not change the benchmark protocol, task payloads, actor schedule, or evaluator predicates. It parallelizes episodes only; actors sharing one desktop continue in their declared serial order.

The current prototype has two entry points:

- [`scripts/run_codesk_experiment.py`](scripts/run_codesk_experiment.py): JSON-configured coordinator, queue, Guest-slot allocation, worker launch, result/hash verification, and aggregation.
- [`scripts/run_track_a_v1.py`](scripts/run_track_a_v1.py): Track A V1 episode-family implementation: Guest lifecycle, actor bindings/order, evaluator, reset, event log, and provenance.

The coordinator currently registers `track_a_v1` only. Its family dispatch is intentionally a small condition-to-existing-runner mapping, not yet a general plugin API. The existing fixed pilot wrapper remains useful for paired sequential/two-worker throughput measurements.

## Execution flow

```text
experiment.json
    │ validate schema, family/version, queue, worker and Guest budgets
    ▼
coordinator ── deterministic episode queue
    │             run-id, condition, repeat, Guest-slot reservation
    ├── worker process 1 ── existing family runner ── isolated Guest(s), ledger, artifacts
    └── worker process 2 ── existing family runner ── isolated Guest(s), ledger, artifacts
    │
    ▼
aggregator ── ordered episode table, outcomes, reset, integrity, health
```

## Configuration contract

The checked-in minimal example is [`configs/track_a_smoke_v1.json`](configs/track_a_smoke_v1.json). Current config keys:

```json
{
  "schema_version": 1,
  "experiment_id": "track-a-v1-smoke",
  "task_family": "track_a_v1",
  "task_version": "1.0.0",
  "episodes": [{"condition": "ma_sd", "repeat": 1}],
  "max_workers": 1,
  "max_concurrent_guests": 2,
  "startup_stagger_seconds": 15,
  "artifact_root": "/mnt/raid1/mjh/CoDesk-V1-artifacts/experiments"
}
```

Currently registered condition names are `solo_document`, `solo_chat`, `ma_id`, and `ma_sd`; Solo distinguishes which actor is active. Repeat IDs are 1–5 to match the fixed Track A instances. Duplicate condition/repeat pairs, unpinned task versions, unsafe experiment IDs, unsupported families, and insufficient Guest slots are rejected before resource creation.

Run the plan without creating files or Guests:

```bash
python scripts/run_codesk_experiment.py configs/track_a_smoke_v1.json --validate-only
```

Run an experiment by omitting `--validate-only`. The artifact root is created with `exist_ok=False`; a collision stops before episodes launch. Each episode gets an isolated worker log and artifact parent; the existing family runner then creates its own run-owner marker, full resource ledger, overlay, report, reset evidence, and provenance.

## Coordinator responsibilities

- Validate the immutable config and expand its declared episodes in queue order.
- Assign stable per-job run IDs and separate artifact roots.
- Allocate up to two worker processes and enforce a weighted Guest-slot budget. Solo/MA-SD consume one slot; MA-ID consumes two.
- Stagger worker submissions when configured and collect five-second host load/memory samples during parallel execution.
- Collect worker exit status and preserve failures; aggregate rows in planned order regardless of completion order.
- Keep actor order, task version, evaluator version, and evaluator predicate owned by the task-family runner.

## Worker responsibilities

- Execute one episode in a separate process, with its own run ID, artifact root, environment, and runner-created ownership token/ledger.
- Invoke the existing family runner rather than copying its setup/evaluator/reset implementation into the coordinator.
- Require screenshot and accessibility readiness before actors start; retry transient missing observations within a bound and fail closed if focus state remains unavailable.
- Preserve partial screenshots, logs, report/error, reset result, and resource ledger on failure. The worker never prunes artifacts.
- Close only the episode's exact ledger-owned Guests through provider ownership checks.

The current implementation uses a `ProcessPoolExecutor` worker that starts the task-family shell runner as a subprocess. The coordinator does not yet implement graceful process-group cancellation on forced termination; this is a limitation to address before long-running batch execution. In normal completion, each family runner owns Guest cleanup and resource-ledger reconciliation.

## Episode result and aggregation

The summary separates:

- `scenario_success`: task-specific expected outcome or goal predicate. For MA-SD Track A, the scripted negative-control trigger reproducing and attributing the focus conflict is the expected scenario outcome.
- `reset_success`: fresh Guest identity and clean reset oracle.
- `artifact_integrity`: report contract, provenance, required files, matching SHA-256, and resource lifecycle validity.
- `environment_health`: readiness/accessibility retries, missing observations, Guest IDs, and worker host snapshots.
- `worker_status`: process exit code or error.

No artifact pass can count as task success. The coordinator retains missing/failed queue jobs and reports them rather than dropping their denominator. Current summary includes episode latency and median, reset/scenario/artifact counts, host samples, and per-episode environment health. Add p95 and family-stratified throughput when there are enough episodes to make those summaries useful.

## Stability evidence and limits

The latest bounded Track A regression (`tracka-p10-stab-2357`) passed sequential 2/2 and two-worker 2/2 expected scenario outcomes, reset 2/2 in each mode, and artifact/provenance integrity 2/2 in each mode. Parallel batch wall time was 352.348 s versus 709.798 s sequential (50.36% lower for this n=2 sample). No accessibility/readiness failure occurred after adding the service gate; 15 s startup staggering was used. This supports a controlled two-worker prototype, not a general reliability or capacity claim. Keep the ceiling at two workers/four Guest slots and repeat stability checks before formal parallel data collection.

## Task-family migration

1. Keep `track_a_v1` implementation unchanged except shared readiness/health infrastructure.
2. Add a registry adapter for the existing Writer/Calc family after its missing MA-ID condition and reset contract are defined. The current office task has real Guest Solo and shared conditions, ODF final-state evaluation, and focus event summaries; it is not yet wired into the generic coordinator.
3. Make each family define its own condition set, Guest slots, command/episode plan, final-state evaluator, event analysis, and reset oracle.
4. Add other families only after independent Solo controls pass. The coordinator should not acquire app-specific selectors or evaluator code.

## Current verified scope

The Track A config parser and allocation plan are validated with `--validate-only`. One complete config-driven coordinator episode then ran against the real OSWorld V2.1 Guest: experiment `track-a-v1-smoke-retry-01`, condition MA-SD, one repeat. Runtime was 351.915 seconds; the expected shared-focus conflict was attributed, reset passed, artifact/provenance hashes passed, and the worker exited 0. The episode created and destroyed both its task Guest and reset Guest under matching ownership labels. Artifacts are retained at `/mnt/raid1/mjh/CoDesk-V1-artifacts/experiments/track-a-v1-smoke-retry-01/`.

The first coordinator integration attempt (`track-a-v1-smoke`) failed during reset because `scripts/run_track_a_v1.py` used `requests` without importing it. Its partial error report and ledger remain preserved in their own artifact root. The missing import was fixed; the second attempt used a new experiment ID and passed. The integration smoke is one episode and does not establish family-general behavior. Unit tests cover pinned versions, duplicate episodes, MA-ID resource slots, event focus analysis, adapter contracts, and ownership safety. Worker process-group cancellation and office-family registration remain future work.

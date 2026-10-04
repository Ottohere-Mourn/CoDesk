# CoDesk Track A Runner Parallelization Audit

## Scope

Read-only review of `scripts/run_track_a_v1.py`, `swcub/resource_safety.py`, the OSWorld adapter, and the pinned OSWorld V2.1 Docker provider. This document designs a two-worker prototype; it does not change runner code, task definitions, evaluators, or protocol.

## Findings

### 1. Guest lifecycle

Each logical episode calls `run_episode` serially in the current top-level plan. It starts one task Guest for Solo/MA-SD and two separate task Guests for MA-ID. After task evaluation, each desktop binding is reset to a newly created clean Guest, checked for a new container ID and absent task files, then closed. The current sequence can therefore record two containers for Solo/MA-SD and four for MA-ID. At most one Guest is active for a Solo/MA-SD episode; MA-ID temporarily has two active Guests.

Within an episode, the actors and resets are intentionally scheduled serially. In MA-SD they must use the same live desktop in sequence; parallel actor actions would alter the focus/input interaction being measured. Episode-level workers are independent and do not require changing this schedule.

### 2. Artifact isolation

- A runner invocation creates `<artifact-parent>/<run-id>` with `exist_ok=False`; an existing run root fails closed.
- Each episode has a unique condition/repeat directory, a separate `overlays/` directory, screenshots, event log, report, provenance, and `resource-events.jsonl` ledger.
- Two independent runner invocations are safe from path collisions when each receives a unique `--run-id`. Reusing one run ID for parallel child invocations is unsafe because both attempt to create the same run root.
- `matrix_progress.jsonl` is append-only within one runner invocation. Independent workers should not append to a shared progress file; one coordinator should persist queue status and merge result summaries.

### 3. Resource ownership and concurrency

The current resource model supports concurrency **between processes**:

- `configure_episode_identity` generates a unique run ID and owner token and points each episode at its own append-only ledger.
- Docker Guests receive project, run, and owner labels. Cleanup verifies the full immutable container ID against both labels and that episode's creation ledger before removal.
- Each episode receives its own overlay directory. The current OSWorld provider has a host-wide file lock around Docker port selection/container creation, protecting port allocation; VM boot can proceed after that section releases the lock.

The current model is **not safe for episode threads in one interpreter**. `configure_episode_identity` changes `SWCUB_RUN_ID`, `SWCUB_OWNER_TOKEN`, `SWCUB_RESOURCE_LEDGER`, and the initialized-identity marker through process-wide `os.environ`. Concurrent threads could make a provider attach the wrong identity or ledger to a Guest. `ensure_resource_identity` also uses that environment as the caller's identity source. Use isolated worker processes unless the ownership API is redesigned and separately validated.

The existing file ledger uses append-only writes and `fsync`; separate per-episode ledgers avoid inter-worker write races. Keep it that way in the prototype. The coordinator should never clean up resources by names or image tags; failed-worker cleanup remains the runner's exact-ID/label/ledger path. Preserve partial artifact roots and ledgers for failed jobs.

## Two-worker prototype design

### Coordinator and worker queue

Use one coordinator process and a durable queue of **single logical episodes**. A queue key is `(task_version, condition, solo_actor, repeat)`, for example:

```text
1.0.0 | solo | document_actor | 03
1.0.0 | ma_id | both            | 02
1.0.0 | ma_sd | both            | 04
```

Each item transitions `queued → leased → succeeded | failed`; a lease contains `worker_id`, `attempt_id`, start time, and heartbeat. The coordinator assigns at most two leases at once. Workers execute one episode in a child process and return its run ID, episode path, status, reset result, and error summary. The coordinator is the only writer of queue state and the final aggregate manifest.

Launch each child with the existing pinned OSWorld V2.1 checkout and a unique, safe run ID, using the existing CLI selectors:

| Episode job | Existing selection |
|---|---|
| Document Solo repeat `r` | `--only solo --start-repeat r --limit-episodes 1` |
| Chat Solo repeat `r` | `--only solo_chat --start-repeat r --limit-episodes 1` |
| MA-ID repeat `r` | `--only ma_id --start-repeat r --limit-episodes 1` |
| MA-SD repeat `r` | `--only ma_sd --start-repeat r --limit-episodes 1` |

Use a different `--run-id` for every child attempt. A failed or interrupted attempt keeps its original directory and ownership ledger; a retry gets a new run ID and references the earlier attempt in coordinator metadata. Never overwrite or delete partial artifacts to make a retry fit the original path.

### Episode isolation invariants

Before counting a worker result, the coordinator verifies:

1. The worker's task ID/version, condition, actor assignment, and repeat match its queue lease.
2. Its unique run root and episode directory do not overlap any other lease.
3. All task/reset containers in that episode's ledger have full IDs, consistent project/run/owner labels, and destroy records.
4. The episode report says reset passed; provenance, event logs, and expected screenshots exist.
5. A retry is a new attempt ID; the failed attempt remains preserved and excluded from the success count.

Within a task, keep the current actor ordering, focus setup, action calls, pause values, hidden evaluator timing, and reset oracle. In particular, do not run the two MA-SD actors concurrently or put them on different Guests.

### Initial two-worker trial

1. First run a non-counted infrastructure pilot with one Solo job and one MA-SD job concurrently. Check that both QEMU Guests boot, receive distinct port mappings and ownership labels, save to disjoint directories, and pass reset verification.
2. Then test one MA-ID job beside one Solo/MA-SD job. Confirm the MA-ID pair remains isolated from the other job and from each other.
3. Only after both checks pass, run the formal repeat queue with two episode workers. Preserve repeat IDs and report the serial and parallel conditions together.
4. Stop the pilot on any mismatched ownership labels, path collision, missing artifact, reset failure, or queue lease ambiguity. Keep logs and partial resources for exact-ledger reconciliation.

## Maximum safe concurrency estimate

**Prototype ceiling: two episode worker processes, with a four-Guest global semaphore.** A Solo or MA-SD episode consumes one active Guest slot; an MA-ID episode reserves two slots for its two isolated desktops. This bounds the pilot to at most four concurrent 4-vCPU / 4-GiB QEMU Guests and prevents two MA-ID jobs from silently oversubscribing the initial budget.

This is a conservative trial ceiling, not a proven host capacity. A sampled host snapshot during the Track A runs showed 80 logical CPUs but load averages around 135/177/140; available memory was ample, while swap was fully used. Under that sampled load, keep the effective concurrency at one until the host is quieter. There are no controlled throughput measurements for concurrency 2 or higher, and CPU load, swap activity, storage latency, KVM scheduling, and the provider's port lock may cap useful parallelism before nominal RAM/CPU limits.

Collect p50/p95 episode wall time, Guest-ready time, reset timeout rate, reset pass rate, active Guest count, host load, and episodes/hour at worker counts 1 and 2. Do not raise the ceiling unless concurrency 2 improves throughput without worsening readiness tails, reset reliability, or provenance completeness. Four is only a later test point after two-worker evidence; it is not the recommended default.

## Recommendation

Implement the smallest next step as a coordinator that launches the existing runner once per queued episode in a separate process, with unique run IDs and per-attempt artifact roots. Start with a two-worker limit and four Guest slots, but use one worker when host load resembles the sampled overloaded state. Keep all actors within each episode serial and preserve the current task/evaluator/reset contract.

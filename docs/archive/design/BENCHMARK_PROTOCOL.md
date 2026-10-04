# CoDesk Protocol V2 (Historical Shared-Workspace Suite)

## Protocol version and scope

- Benchmark suite: `SWCUB-V2-SCRIPTED-REAL-GUEST`
- Current project name: CoDesk (Collaborative Desktop Use Benchmark)
- Historical prototype name: Shared-Workspace Benchmark
- Task version: `2.0.0`
- Task-spec schema: `TaskInstanceSpec` schema `1`
- Episode metadata schema: `1`
- Event log schema: `1`
- Environment: pinned OSWorld V2.1 Ubuntu QEMU Guest, one Guest per episode
- Current task set: `SWCUB-FOCUS-ROUTING-001` and `SWCUB-STALE-MERGE-001`

The two tasks, independent actor goals, conditions, and output locations are in [`tasks/task_suite_v2.json`](../../../tasks/task_suite_v2.json). Existing evaluators and task semantics are frozen for the initial model smoke. The V2 scripted validation artifacts are on RAID1 under `/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/`; the three re-run focus cases use `task-suite-v2-protocol/`.

## Episode protocol

1. **Resolve a fixed task instance.** Validate `task_id`, `task_version`, seed, environment release, actor IDs and roles, actor goals, schedule, initial state, evaluator class, and task instance ID before starting a Guest.
2. **Preflight each actor independently.** The model's GUI goal and the second actor's goal must each pass in solo episodes under the same task version and initial fixture. A shared episode does not start if either solo control fails.
3. **Reset and initialize one Guest.** Start from the pinned OSWorld V2.1 Guest image; install the local fixture and applications; wait for the desktop and task app readiness; record initial app state and screenshot digest. Every actor in that episode uses the same `OSWorldSharedEpisode`, Guest container, desktop, keyboard, pointer, and backend.
4. **Run a deterministic schedule.** Keep actor turn order and trigger points fixed. A GUI turn is one existing OSWorld `predict`/action batch. Do not insert incorrect model actions. Naive Shared lets the model see each new desktop observation and choose whether to recover. Recovery/Focus-aware may apply only the declared scheduler intervention and must log its source and exact operation.
5. **Score after actors stop.** The existing evaluator reads authoritative Guest state through a host-held callback after the schedule. Never pass the evaluator, expected state, or raw backend file path into an ActorContext.
6. **Verify reset.** Close the current Guest through the pinned ownership-safe provider, start a new Guest, assert the task files/backend state are absent or at the declared initial state, and record both full Guest IDs. A task episode counts as operationally complete only when its reset check passes.
7. **Freeze evidence.** Save `report.json`, `events.jsonl`, screenshots, actor trace/model trace, `resource-events.jsonl`, `provenance.json`, and the reset screenshot in the episode directory. Preserve failures and preflight failures; never overwrite an existing run directory.

## Conditions

| Condition | Fixed intervention | Interpretation |
|---|---|---|
| Solo | One actor active; same task fixture and evaluator. For the second actor, use a separate solo episode. | Verifies independent solvability and model baseline. |
| Naive Shared | Deterministic trigger allows the other actor to perform its own task on the shared Guest. The model receives a fresh desktop screenshot on its next turn and may recover autonomously. | Measures observed joint result under ordinary interleaving; do not force an error. |
| Recovery / Focus-aware | Apply only the task's declared recovery policy: focus task reactivates the GUI actor's target window; stale-state task refreshes the public cached state before the GUI actor resumes. | Measures the declared coordination intervention, not generic autonomy. Log scheduler-generated actions separately from actor actions. |

For the GUI+Human focus task, the Human Replay action is a valid independent goal and the naive trigger changes the shared desktop focus. For GUI+CLI consistency, the CLI update changes the authoritative backend while the Browser retains a cached record; the refresh recovery condition operates the visible Refresh affordance. The evaluator is unchanged across conditions.

## Success and failure accounting

Every report distinguishes:

- `goal_success[actor]`: that actor's own authoritative final-state predicate.
- `joint_success`: all active actor goals and state-integrity predicates pass.
- `scenario_success`: the condition behaved as declared; this is true for a negative control only if the evaluator rejects the contaminated/lost-update state and the expected failure signature is present.
- `evaluation.success`: the unmodified evaluator's result. It must be false for a correctly reproduced negative control.
- `reset_check.success`: clean reinitialization completed and the new Guest ID differs from the task Guest ID.

Failure labels are assigned from traces and evaluator state: `focus_conflict`, `stale_observation_or_app_state`, `input_routing_error`, `scheduling_issue`, `actor_task_failure`, `joint_goal_failure`, and `reset_failure`. Multiple labels may apply. A task failure does not become an interaction failure unless the timeline and public state show that the other actor or declared scheduling intervention preceded and explains the divergence. Small smoke samples are descriptive, not statistical.

## Resource and execution provenance

Each new episode has an isolated RAID1 output directory and unique run ID/owner token. Any Guest container that the provider stops or removes must have its complete immutable ID, project/run/owner labels, and creation row in that run's append-only ledger. Keep the V2.1 base image and shared dependencies intact. Do not use global prune or delete artifacts by name/prefix.

`episode_metadata` in `report.json` and `provenance.json` freezes:

- benchmark/task/schema versions, task instance, condition, seed, schedule, actor IDs/classes/roles, evaluator class and post-episode-only state access;
- repository commit/dirty paths and SHA-256 hashes of task, actor, evaluator, orchestrator, adapter, runner, and provenance source files;
- OSWorld checkout commit/dirty status, V2.1 release manifest hash, declared source archive digest, Guest image path/size, runtime image immutable ID, environment and Guest container IDs;
- run ID, exact ownership labels, ledger path/digest, and create/destroy confirmation;
- Python/host information, model metadata (null for scripted episodes), and SHA-256 hashes of reports, logs, screenshots, traces, and reset evidence.

The Guest archive digest in the release manifest identifies the downloaded archive; it is not claimed to be the SHA-256 of the extracted QCOW2 file.

## Current validation and entry gate

The V2 scripted suite currently has eight validated episodes across the two tasks. The older three focus artifacts lacked resource ledgers and were rerun under the current ownership mechanism; the suite validator now requires ledgered Guest create/destroy, unified task version, content hashes, exact actor rosters, and reset verification.

Before the first shared model smoke, require one successful Qwen solo episode for that exact task/version plus a passing solo control for the second actor. If either fails, retain the evidence and stop shared conditions for that task. Do not alter model, task goal, evaluator, or task difficulty to clear the gate. The run plan is fixed in [`MODEL_SMOKE_PLAN.md`](../experiments/MODEL_SMOKE_PLAN.md).

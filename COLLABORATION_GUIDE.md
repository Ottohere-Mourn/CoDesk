# CoDesk Collaboration Guide

CoDesk is the current project name; Shared-Workspace Benchmark is the historical prototype name used by earlier artifacts and identifiers.

## Repository status

- Current branch: `v0`.
- Working tree at preparation: clean, based on checkpoint `3f469f9`.
- Git remotes: none configured. The checkout contains no canonical remote URL. Set `origin` only after the repository owner supplies the authoritative URL; do not add a placeholder or infer a personal fork. Then verify with `git remote -v` and `git fetch --dry-run origin` before pushing.
- Local Git identity is `mjh <mjh@localhost>`; this is a machine-local default, not a team identity policy.

## Directory map

| Path | Responsibility | Collaboration guidance |
|---|---|---|
| `swcub/` | Shared environment/actor interfaces, orchestration, event log, task schemas, provenance, OSWorld adapter and evaluator | Core framework. Extend through stable interfaces and versioned schemas. Do not alter existing evaluator predicates or actor-visible boundaries to make a task pass. |
| `swcub/tasks/` | Task-specific setup and fixtures | New behavior belongs in a new task module or an explicitly versioned implementation. Existing V2 task behavior is frozen. |
| `tasks/` | Machine-readable suite catalog and deterministic task instances | Add new task IDs/instances. Do not edit `task_suite_v2.json` or its existing instances in place; retain them as the V2.0.0 record. |
| `env/` | Original Docker/X11 workspace and local GUI/CLI fixture | Environment implementation. Keep its dependency and fixture behavior separate from OSWorld Guest tasks. |
| `infra/osworld-v2.1-qemu-runtime/` | Project-owned OSWorld V2.1 QEMU runtime Dockerfile and entrypoint | Pinned runtime integration. Changes require a new validated runtime/image provenance record; do not replace the shared base Guest image. |
| `scripts/` | Environment setup, episode runners, validators, summarizers, ownership-safe cleanup | Reuse existing runners and validators. New runners must write to a fresh output path, carry provenance and ownership ledgers, and must not clean resources by name or prefix. |
| `tests/` | Unit, interface-contract, scheduler, provenance and resource-safety tests | Add tests for new contracts or schema behavior. Keep mock/interface tests labeled separately from real-Guest evidence. |
| `docs/` and root `*.md` | Protocols, API, analysis, runbooks and planning | Add versioned design/protocol documentation. Clearly separate measured results from proposals. |
| `outputs/` | Existing repository-local run outputs and validation artifacts | Preserve. Never delete, rewrite, or reuse an existing episode directory. |
| `/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/` | Large real-Guest and Phase 4 model artifacts, screenshots, logs and resource ledgers | External to this Git checkout. Treat as immutable evidence; write new runs to new paths. |
| `../_deps/OSWorld-V2-osworld-v2.1/` and its Guest/runtime images | Pinned upstream checkout and environment assets | External dependency. Do not patch or clean it as part of ordinary task contribution. Record release/commit/image provenance. |

## Protected benchmark components

The following changes need an explicit new version and review; do not make them as incidental task fixes:

- `swcub/evaluator.py`, evaluator predicates, and hidden-state access boundaries.
- Existing entries in `tasks/task_suite_v2.json`, `tasks/instances/*.json`, and task-version `2.0.0` semantics.
- Existing result reports, `outputs/**`, RAID1 episode artifacts, screenshots, event logs, and provenance sidecars.
- `swcub/resource_safety.py`, `scripts/cleanup_owned_resources.py`, ownership labels/ledgers, and cleanup policy.
- Pinned OSWorld checkout, Guest image, runtime image, package lock files, and task application fixture versions.

Do not run Docker prune commands, delete unknown containers/images/volumes, or clean directories by glob. The project cleaner may stop only an exact full container ID whose project/run/owner labels and creation record all match its run ledger. Any other resource must be reported with its exact identity, purpose, and impact; obtain owner approval before modifying it. Never modify another user's resources.

## Adding a task

1. **Choose a mechanism, not a theme.** Explain the shared resource and the causal interaction that makes the task fail. Show that it is distinct from focus-routing or stale whole-record overwrite already covered in V2.
2. **Declare independent goals.** Every actor must pass its own solo control using the same task version and initial fixture. A shared episode must be jointly feasible without one actor's goal invalidating the other's.
3. **Make the interaction reproducible.** Define initial state, actor roles, exact event trigger, schedule, target resource, expected failure signature, and a recovery path. Do not rely on random noise or require a model to take an obviously wrong action.
4. **Add a new task ID and instance.** Use `TaskInstanceSpec` from `swcub/instances.py`; add a new file under `tasks/instances/` and register it as a new entry in a new/versioned suite manifest. Keep V2.0.0 specs unchanged. Declare actor goals, schedule, environment release, shared resources, and evaluator type.
5. **Write a deterministic evaluator.** Evaluate authoritative final state after actors stop. Keep expected values and hidden state outside `ActorContext`; score all active goals, contamination/integrity constraints, and reset. Do not use an LLM judge as the success oracle.
6. **Start with scripted actors.** Demonstrate solo success, joint feasibility, the declared naive failure trigger, and recovery before testing a model. Preserve negative controls as expected evaluator failures with a separate scenario outcome.
7. **Use fresh evidence paths.** Write each attempt under a new RAID1 episode directory. Save model/scripted traces, screenshots, event log, evaluator report, reset proof, provenance, and ownership ledger. Never overwrite an existing result.
8. **Validate and submit a focused change.** Run the relevant schema/task/resource-safety checks, record exact commands and results, update the new protocol/task documentation, and submit a branch/PR without unrelated environment or evaluator changes.

## Contributor workflow

```bash
git status --short --branch
git switch -c task/<short-mechanism-name>
# implement a new task ID/instance and its isolated tests/evidence
python scripts/validate_task_instances.py
python scripts/validate_task_manifest.py
python scripts/validate_task_suite_v2.py --help
git diff --check
```

Use the repository's current task validator CLI as documented by `python scripts/validate_task_suite_v2.py --help`; do not write new outputs into existing episode directories. Before a model comparison, satisfy the solo gate in `BENCHMARK_PROTOCOL.md` for every actor. Keep the model, OSWorld release, task version, and evaluator fixed within each comparison.

## Remote setup handoff

No remote is configured in this checkout. Once the owner provides the canonical URL, configure and verify it explicitly:

```bash
git remote add origin <owner-provided-canonical-url>
git remote -v
git fetch --dry-run origin
```

Do not push the existing local `v0` branch or publish artifacts until the remote target and branch policy are confirmed.

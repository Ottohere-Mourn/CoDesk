# Shared-Workspace Benchmark Agent Rules

## Resource safety

- Never use global Docker cleanup (`docker system prune`, `docker container prune`, `docker image prune`, `docker volume prune`) or wildcard/bulk stop/remove commands.
- Automatic cleanup is limited to temporary resources created by this project during the current run. Before stopping or deleting a Docker container, verify its **full immutable container ID**, project label `org.swcub.project=shared-workspace-benchmark-v0`, current-run label `org.swcub.run-id`, and unique `org.swcub.owner-token`; also verify the exact ID and labels are in that run's append-only `resource-events.jsonl` ledger.
- The only automatic container cleaner is `scripts/cleanup_owned_resources.py`, which takes one full container ID and one run ledger. It must refuse short IDs, names, missing ledger entries, or any label mismatch. Never select resources by image name, tag, prefix, or account ownership.
- Images, volumes, host directories, overlays, and resources belonging to another project or user are never automatically removed. If cleanup would touch any of them, report the exact target, purpose, and impact and wait for explicit approval. Other users' resources are never modified or deleted autonomously.
- Keep `docker run --rm` out of project scripts because it removes a container without a separate ID-and-label verification step. Log creation and destruction with full IDs and ownership labels. If verification or logging fails, leave the resource in place and report it.
- Temporary host directories must carry a project/run/token ownership marker and a matching ledger entry before automatic deletion. Never recursively clean a shared or pre-existing directory.

## Benchmark integrity

- Keep the pinned OSWorld V2.1 Qwen3VLAgent, model weights, task instances, and evaluators fixed during a comparison run.
- Save per-episode trajectories, screenshots, programmatic results, and resource ledger entries under the episode artifact directory.
- Do not begin shared conditions if the solo control for either actor fails. Preserve failed episodes and classify failures before interpreting interaction effects.

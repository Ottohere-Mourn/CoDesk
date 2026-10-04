# CoDesk Resource Safety

Applies to all benchmark production and later execution.

1. Do not use a GPU that reports another user's compute PID. Do not kill, pause, renice, inspect private project files of, or otherwise modify another user's process.
2. Never run `docker system prune`, `docker container prune`, broad image deletion, or cleanup by image name.
3. A run may remove only resources it created and whose complete IDs, owner labels, run ID and ownership ledger match that run. If ownership is ambiguous, fail closed and preserve the resource.
4. Keep a per-run resource ledger with resource type, full identifier, creator/run ID, ownership labels, creation time, cleanup result and artifact path.
5. Keep all run artifacts and failed attempts. Reset success only means the next task starts clean; it does not turn an earlier task failure into success.
6. Model workers and SSH tunnels are run-owned only when PID/command or SSH control socket matches the run ledger. Stop only those exact resources.
7. Runner defaults to dry-run. It must not create a Guest until a workflow adapter has passed its readiness and ownership checks. Infrastructure failures are `INVALID_INFRA`, not model failures.
8. Do not use global or other-project directories for benchmark outputs. Use explicit CoDesk artifact roots with restrictive permissions for private evaluators and model logs.

**Recovery rule:** if a container, file, process, volume, model worker, or lock has uncertain ownership, leave it unchanged, capture read-only evidence, and report the exact identifier and impact.

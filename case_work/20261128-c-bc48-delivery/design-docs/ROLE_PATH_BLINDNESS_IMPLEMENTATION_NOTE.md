# Role-path blindness implementation note

**Effective 2026-11-27:** this note supersedes any earlier BC design/implementation wording that requires a per-Actor Docker container, separate Guest UID, Docker bind mount, or technically inaccessible private folder.

## Runtime arrangement

- Preserve the formal `oscombo` Shared arrangement: two host-side persistent Codex subprocesses operate one shared OSWorld Guest.
- Create the directories `~/workspace/private/actor_a` and `~/workspace/private/actor_b` in that Guest. They are normal Guest workspace directories, not protected mounts or ACL boundaries.
- Keep each Actor's prompt focused on its own role and source-path convention. Do not tell either Actor that another Actor exists.
- Do not expose host Oracle, hidden truth, runner control, provider credentials, or host archive directories through the Guest CLI.

## Post-run audit

The pipeline scans each Actor's archived `actions.jsonl` for explicit references to `private/actor_a` and `private/actor_b`. A cross-role path reference is recorded as an audit failure in `blind-path-audit.json` and the episode report. It does not rewrite the task score and must not be presented as an ACL.

This audit cannot prove that cross-role information was never accessed. In particular it cannot detect generic listing of the parent directory, symlinks or aliases, access via an application/service that does not log paths, or unrecorded/implicit Guest activity. Case prompts, shared services, and Guest setup must therefore avoid relying on a security claim that the other role's files are unreachable.

## Evidence and teardown

The formal runner's `env.close()` wrapper captures only declared `host_snapshots` and `host_http_snapshots` after official evaluation and before Guest teardown. Required service/state/DB receipts fail closed when absent. Missing deliverables are explicitly recorded as missing so the offline Oracle can assign partial/zero credit rather than convert an ordinary Agent omission into a capture failure. Guest teardown is considered verified only when official close completes and Docker inspection returns the specific “No such object” result for that captured Guest ID.

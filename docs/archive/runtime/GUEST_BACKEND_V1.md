# CoDesk Guest Backend V1

`swcub/osworld_guest_backend_v1.py` implements the A6000/OSWorld V2.1 backend interface. Import and construction are lazy and do not start a Guest. `create_owned_guest` is the first operation that can instantiate `DesktopEnv`.

## Implemented operations

- Resolve pinned OSWorld source, qcow2 image, task cache, runtime image, and artifact root from `scripts/a6000_env.sh` settings.
- Require the patched Docker provider ownership marker before Guest creation.
- Create a per-run owner token and append-only resource ledger; validate full container ID, labels, and ledger entry.
- Start the pinned DesktopEnv, perform screenshot/accessibility readiness, copy hash-checked fixture bytes through the Guest execute endpoint, and launch Writer, Calc, Chromium, or Terminal.
- Record readiness, screenshots, run-owned resources, fixture hashes, and reset/cleanup results.
- Delegate cleanup to the patched provider only after rechecking exact run ownership. If ownership cannot be proved, preserve the resource and fail.

## Fail-closed boundaries

The backend does not claim initial task readiness from a visible screenshot alone. It requires a per-workflow `verify_initial` observer. It also requires a per-workflow exact hidden-state observer for evaluation. No 15-workflow observer registry is currently registered. Therefore the backend refuses to begin actor turns for an unbound workflow and cannot yet score generated task instances on a real Guest.

`static_preflight()` checks local paths and source patch markers only. It does not call Docker, start a Guest, access the model endpoint, or prove Guest readiness. Actual use still requires a live A6000 resource preflight and a real smoke.

The backend currently launches applications from fixture extensions. Workflow-specific browser local servers, UNO state probes, clipboard observers, native dialog protocols, and reset-specific semantic checks must be bound before this backend can support the corresponding workflow.

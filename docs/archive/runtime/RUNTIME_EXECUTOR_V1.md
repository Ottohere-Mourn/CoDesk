# CoDesk Runtime Executor V1

`swcub/runtime_execution_v1.py` supplies the unified episode state machine and deterministic scheduler. It reuses actor objects through `run_step`, so model planning, grounding, prompt history, action parsing, and GUI action construction remain in the selected existing actor framework.

## Topology and scheduling

- Solo: one active actor and one Guest.
- MA-ID: one Guest per active actor; each Actor receives its own Guest context.
- MA-SD: one Guest/context shared by the active Actors; actor objects and histories remain separate.
- A native action completes before `action_boundary` is called. The scheduler can pause at that boundary and resume later.
- Fixed-order, round-robin, and observer-fed `EventGate` APIs exist. A task-specific gate must be supplied; the scheduler does not invent evidence or tell an Actor what changed.
- Per-actor turn budgets, episode timeout, action counts, Actor termination, and oracle result are distinct fields.

## Outcomes

The runtime taxonomy includes `SUCCESS`, `TASK_FAILURE`, `MODEL_FAILURE`, `INVALID_INFRA`, `BLOCKED_RESOURCE`, `BLOCKED_RUNTIME_BACKEND`, `RESET_FAILURE`, `EVALUATOR_FAILURE`, and `TIMEOUT`. Oracle success is recorded independently of Actor termination. Infrastructure and reset failures do not become task failures.

## Fake execution

`swcub/fake_runtime_backend_v1.py` and `swcub/runtime_plugin_v1.py` support orchestration tests only. Outputs carry `FAKE_ORCHESTRATION_ONLY` and `fake_backend_only=true`; they are not benchmark results and must not be reported as Guest/model evidence.

The built-in `a6000` plugin currently fails closed when workflow setup/evaluator bindings are incomplete. The `fake` plugin is selectable only explicitly and uses an isolated output root when invoked from the smoke wrapper.

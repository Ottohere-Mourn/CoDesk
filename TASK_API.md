# CoDesk Task API V2 (Historical Shared-Workspace Prototype)

## Version boundaries

- Task version: `2.0.0`
- `TaskInstanceSpec` schema: `1`
- `EnvironmentAdapter` contract: Python protocol in `swcub/environment.py`
- `Actor` contract: Python protocol in `swcub/actors.py`
- `Evaluator` contract: Python protocol in `swcub/evaluator.py`
- Event log schema: `1` (`swcub/core.py`)
- Episode metadata schema: `1` (`swcub/provenance.py`)

Task version changes when actor goals, initial-state semantics, trigger behavior, evaluator predicates, or recovery intervention changes. Metadata fields may be extended additively by increasing the metadata schema version; that does not silently change a task version. The task version applies to both V2 tasks in [`tasks/task_suite_v2.json`](tasks/task_suite_v2.json).

## Task specification

The versioned task catalog declares the stable task-level mechanism and actor roles. A concrete `TaskInstanceSpec` supplies a deterministic fixture and schedule:

```json
{
  "schema_version": 1,
  "task_id": "SWCUB-STALE-MERGE-001",
  "instance_id": "stale-merge-seed-0",
  "seed": 0,
  "environment": {
    "adapter": "OSWorldSharedEpisode",
    "release": "osworld-v2.1",
    "shared_resources": ["one desktop", "one Browser cache", "one Guest backend"]
  },
  "initial_state": {"gui_status": "Draft", "cli_note": "Draft", "revision": 0},
  "actors": {"gui_actor": "gui", "cli_actor": "cli"},
  "actor_goals": {
    "gui_actor": {"gui_status": "Approved"},
    "cli_actor": {"cli_note": "Reviewed by CLI"}
  },
  "schedule": [
    {"actor_id": "gui_actor", "trigger": "episode_started"},
    {"actor_id": "cli_actor", "trigger": {"after_actor_turn": {"actor_id": "gui_actor", "count": 1}}},
    {"actor_id": "gui_actor", "trigger": {"after_actor_turn": {"actor_id": "cli_actor", "count": 1}}}
  ],
  "evaluator": {"type": "GuestWebStateEvaluator"},
  "expected_state": {"gui_status": "Approved", "cli_note": "Reviewed by CLI"}
}
```

`TaskInstanceSpec.from_dict` validates and copies the data. `materialize_schedule()` resolves declared actor-turn prerequisites deterministically. `expected_state` is evaluator-only; task setup code may hold it, but ActorContext never exposes it. The actual in-use instance is [`tasks/instances/browser_gui_cli.json`](tasks/instances/browser_gui_cli.json); focus task declarations are in [`tasks/task_suite_v2.json`](tasks/task_suite_v2.json).

## Actor interface

An Actor has a stable `actor_id`, a capability `role`, and either `run(context)` or incremental `run_step(context) -> done`. Incremental actors preserve their own model/history state between scheduled turns. Shared task execution passes every actor a context bound to the same environment object.

Public `ActorContext` operations:

| Method | Capability | Meaning |
|---|---|---|
| `observe()` | GUI / Human Replay | Return the current GUI observation; update the actor's observed revision. |
| `refresh_observation()` | GUI / Human Replay | Request a fresh screenshot when the adapter supports it. |
| `click(x, y)` | GUI / Human Replay | Click in the shared desktop coordinate space. |
| `type_text(text)` | GUI / Human Replay | Type into the currently focused shared control. |
| `press_key(key)` | GUI / Human Replay | Send a keyboard action to the shared desktop. |
| `focus_window(title)` | GUI / Human Replay | Request the adapter's declared window focus action, when supported. |
| `execute_gui_action(native)` | GUI / Human Replay | Forward the native action string from a reused GUI framework. |
| `run_cli(argv)` | CLI | Run an allowed command in the same Guest/workspace. |

The context has no evaluator property, expected-state object, raw host path, or unrestricted cross-role tool. A framework adapter such as `OSWorldAgentActor` forwards OSWorld's existing predict/actions; it does not add planning or grounding.

## Environment and orchestration interfaces

`EnvironmentAdapter` provides:

```python
reset(**kwargs) -> initial_observation
observe(actor_id, interface) -> observation
act(actor_id, interface, action, observed_revision=None) -> result
snapshot() -> public event state
close() -> None
```

`OSWorldSharedEpisode` binds one `DesktopEnv` and an injected CLI executor for that same Guest. The Orchestrator receives one adapter, a unique actor roster, a deterministic list of actor IDs, one evaluator capability, and an output path. Optional `before_actor_turn(actor, index)` hooks are coordination interventions; they must use a distinct scheduler actor ID in the event log.

Each event records sequence, UTC timestamp, actor, kind, action, observed revision, before/after digests, outcome, and structured details. Raw screenshots are stored as files; JSONL events store their hashes and metadata.

## Evaluator interface

```python
class Evaluator(Protocol):
    def evaluate(self, environment) -> dict[str, object]: ...
```

The Orchestrator invokes the evaluator once after all scheduled actors finish (including error/step-budget termination). Evaluators read authoritative state through private host-held callbacks, not actor-visible context. The evaluator returns at least `success`, exact `expected`/`final_state` for the scored fields, and `missing` details. The same class and predicate set must be used for every condition of a task. `GuestFocusEvaluator` and `GuestWebStateEvaluator` remain unchanged in V2.

## Episode report and metadata schema

`report.json` retains task result fields and includes these V2 additions:

```json
{
  "task_id": "SWCUB-FOCUS-ROUTING-001",
  "task_version": "2.0.0",
  "task_instance_id": "swcub-focus-routing-001-focus-recovery-seed0",
  "condition": "coordination_recovery",
  "environment_id": "osworld-...",
  "shared_guest_container_id": "<full 64-character container ID>",
  "schedule": ["gui_actor", "human_replay", "gui_actor"],
  "actors": {},
  "evaluation": {},
  "reset_check": {},
  "episode_metadata": {
    "metadata_schema_version": 1,
    "benchmark": {}, "task": {}, "actors": [], "evaluator": {},
    "environment": {}, "resources": {}, "source": {}, "host": {}, "model": null
  },
  "provenance_file": "provenance.json"
}
```

`provenance.json` repeats the metadata and adds `artifact_sha256`, keyed by episode-relative path. Hashes cover the final report, events, screenshots, action/model traces, reset evidence, and ownership ledger; the sidecar does not hash itself. Every new Guest run records its full ID and project/run/owner labels in `resource-events.jsonl`.

## Task-specific API bindings

| Task ID | Actors | Evaluator | Solo predicates | Joint predicate |
|---|---|---|---|---|
| `SWCUB-FOCUS-ROUTING-001` | `gui_actor: gui`; `human_replay: human_replay` | `GuestFocusEvaluator` | exact Document or Chat file value | both exact values in their own files; no cross-window input |
| `SWCUB-STALE-MERGE-001` | `gui_actor: gui`; `cli_actor: cli` | `GuestWebStateEvaluator` | own field equals target value | both fields equal their targets after both actors run |

The first Qwen smoke changes the GUI Actor implementation for the selected episode only; actor ID, role, task instance, evaluator, and metadata schema remain fixed. Scripted actor controls remain the independent-solvability gate.

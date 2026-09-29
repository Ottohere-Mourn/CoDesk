# CoDesk Task Registry V1

## Canonical files

- `tasks/codesk_task_registry_v1.json` is the declarative catalog. It freezes task IDs, actor goals, seed state, shared resources, natural interaction path, joint-feasibility rationale, Solo/MA-ID/MA-SD topology, oracle, evidence-based attribution rule, recovery opportunity, reset check, and evidence references.
- `configs/task_suite_v1_offline_review.json` selects the initial eight tasks and all three conditions for contract review. It explicitly sets `guest_launch_allowed` and `model_launch_allowed` to `false`.
- `swcub/task_registry_v1.py` validates the registry/config and supplies reusable pure helpers for copying a seed fixture, exact reset comparison, exact per-actor/joint oracle checks, and event-based interaction metrics. It never starts an environment.
- `tests/test_task_registry_v1.py` exercises those offline contracts with registry data and synthetic event/state dictionaries.

Run the offline validation from the repository root:

```bash
python -m swcub.task_registry_v1 tasks/codesk_task_registry_v1.json \
  --config configs/task_suite_v1_offline_review.json
pytest -q tests/test_task_registry_v1.py
```

This command is a data-contract check only. The config is not accepted by the live runner; `scripts/run_codesk_experiment.py` currently maps only `track_a_v1` and `writer_calc_v1` to Guest scripts. V1 live integration must be implemented behind an explicit execution mode after task setup/evaluator pilots are ready.

## Evidence statuses

| Status | Meaning | Entries |
|---|---|---|
| `scripted_anchor` | Existing real-app task with prior scripted Solo/MA-ID/MA-SD validation recorded in project history; current phase did not rerun it | `CODESK-TA-OFFICE-001` |
| `registered_anchor` | Existing V2 task definition/evaluator referenced by the project; this phase did not rerun or upgrade its evidence | `CODESK-TD-STALE-MERGE-001` |
| `design_only` | Contract proposal; no task-specific setup code, Guest episode, or real-app evaluator validation yet | the other six IDs |

`status` is not a score. Do not add an aggregate pass rate across these statuses.

## Registry contract

Every task contains exactly two independent actor goals, a nonempty seed state, named shared resources, an organic MA-SD path, an explicit jointly feasible end state, and all three conditions. Evaluator fields refer to exact state checks and invariants; attribution fields specify which event chain is sufficient and state what not to infer. Reset checks compare the authoritative state with the seed and should include a new environment identity when the real adapter supplies one.

The registry's `oracle_checks` are evaluator data. They must remain in the evaluator capability, never be included in an `ActorContext`, prompt, screenshot annotation, or actor-visible filesystem. `evaluate_exact_state` consumes state delivered by a private callback; the helper itself does not enforce process isolation. That isolation remains the responsibility of the existing OSWorld/environment adapter.

The event-metric helper assumes ordered events with `sequence`, `actor_id`, `kind`, and mechanism-specific `resource`; stale attribution additionally requires observation/action revisions and an intervening partner state-change event. Missing fields result in no supported attribution. A label in the task config alone never proves interference.

## Relationship to existing task API and evaluator

This is an additive catalog. It does not modify `TASK_API.md`, TaskInstanceSpec schema, existing V2 task definitions, Writer/Calc evaluator rules, prior reports, or the model harness. The anchors link to their current files rather than copying or re-scoring results. A future Adapter should map a registry entry into current `EnvironmentAdapter`, `Actor`, scheduler, and private `Evaluator` contracts. Existing evaluator semantics remain fixed for existing tasks.

## Extension checklist

1. Pick a resource mechanism that has an observable signature distinct from existing focus-routing and stale whole-record overwrite.
2. Specify two actor-local goals, a simultaneous exact final state, the common resource, and a benign interaction schedule.
3. Add exact Solo controls for both actors and an MA-ID topology that removes the intended shared resource.
4. Define objective state checks and the event chain required for causal attribution; define an unattributed bucket.
5. Document recovery that is available to actors without scheduler-forced errors.
6. Add clean-reset and negative-control tests. Unit tests validate the contract only; real-Guest validation is a separate evidence gate.
7. Promote status only after preserving every episode artifact and reviewing setup readiness, evaluator behavior, provenance, and reset.

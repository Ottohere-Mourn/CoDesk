# CoDesk Instance Schema V1

Status: production data contract; main benchmark uses two Actors. The `actors` collection is a list so a later N=3/N=4 subset can be expressed without changing the family or workflow identifiers.

## Identity levels

`family → workflow → semantic instance → run` are separate. `instance_id` is a hash of the workflow operation graph, semantic domain, target-object/schema profile, and task-relevant layout. It excludes generation seed, repeat, topology, model, schedule, and window coordinates. Those execution choices belong to `run_config`.

## Required fields

| Field | Meaning |
|---|---|
| `benchmark_version`, `schema_version` | Frozen data-contract version. |
| `family`, `workflow_id`, `instance_id` | Taxonomy, operation graph, and immutable task content identity. |
| `actor_goals[]` | `actor_id`, application domain, natural-language goal, operation, target objects, initial and expected values. Each actor has a distinct target. |
| `task_domains` | App/domain assigned to each Actor. |
| `schedule_policy_id` | Frozen interleaving policy for this workflow, held identical across MA-ID/MA-SD. Event gates observe completed actions and never inject actor actions or hints. |
| `initial_fixture_spec` | Public fixture references and byte hashes; fixture files contain starting state only. |
| `semantic_parameters` | Domain, object profile, schema, and task-relevant guard/target layout. |
| `target_objects` | Exact object references for each Actor. |
| `expected_final_state` | Private expected state; not included in public manifest rows. |
| `treatment_relevant_state` | Shared state whose exposure/interference is measured for that family. |
| `evaluator` | Versioned exact state oracle and invariants, stored separately under `evaluators/`. |
| `reset_metadata` | Fixture identity/hash and clean-state verification contract. |
| `topology_compatibility` | Solo, MA-ID, MA-SD fixture/session requirements. MA-ID/MA-SD task-relevant starting state is equivalent; filesystem sharing is not required. |
| `provenance` | Generator source hash/commit, semantic hash, fixture hash, seed role. |
| `signatures` | Structural, semantic, goal-pair and fixture SHA-256 used in audit. |
| `validation_level` | Existing evidence level; generated instances do not inherit runtime validation that was never performed. |

The canonical typed definition is `swcub/production_v1.py::InstanceSpecV1`; the serialized format is JSON-compatible. Each JSONL manifest row carries a self-hash. Expected-state details stay in the separate evaluator file. Fixture bytes are addressed by relative paths and checked before materialization.

## Run configuration

`RunConfigV1` contains instance, topology, model, repeat and active actors. Run ID is a deterministic hash of this record. Conditions, repeats, model settings, schedule, budgets, desktop geometry and actor count do not create new instances.

## Validation rules

Reject unknown workflow/family/version, missing actor goals, overlapping actor targets, no-op goals, missing fixture/provenance, absent topology contracts, manifest/hash mismatch, evaluator positive-control failure, or evaluator negative-control pass.

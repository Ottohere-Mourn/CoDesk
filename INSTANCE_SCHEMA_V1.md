# Instance Schema V1

## Four levels

1. **Family** — shared hidden-state mechanism.
2. **Workflow template** — fixed application-operation graph, actor roles, evaluator and schedule.
3. **Fixed semantic instance** — domain record, target-object profile, initial/goal content, exact fixture and oracle hashes.
4. **Run** — topology, model, repeat, budget, schedule and artifact identity.

## Identity

Task identity includes workflow, domain schema, object profile, operation schema, and semantic fixture/oracle content. Seed, run repeat, condition/model choice, screen geometry, and window placement do not create new instances. The V1 final suite uses 20 fixed semantic instances per workflow: 4 domain schemas × 5 distinct object/operation profiles, with one canonical guard layout.

Each manifest row binds two independent actor goals, target objects, initial/goal values, operation graph, task domains, fixture file hashes, private evaluator path/hash, reset metadata, provenance, and topology compatibility. Runtime plans bind Solo A/B, MA-ID, and MA-SD without changing the task definition.

## Oracle contract

Scoring is programmatic. It checks each actor's exact target value, non-target integrity/guards, and workflow-specific operation/history evidence. For Undo workflows, final state alone is insufficient; action chronology and recovery are required. Guest-side observers must provide the evidence represented by each contract before those workflows are called runtime-validated.

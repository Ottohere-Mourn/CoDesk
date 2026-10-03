# CoDesk Benchmark Manifest V1

## Layout

```text
benchmarks/codesk_v1/
  manifest.jsonl                 # one immutable row per fixed semantic instance
  smoke_suite.jsonl              # 5 representative rows, one per family
  families/*.json                # family identity and scope
  workflows/*.json               # operation graph and evidence level
  instances/<instance_id>/manifest.json
  fixtures/<instance_id>/*       # deterministic initial state only
  evaluators/<instance_id>.json   # private oracle parameters
  validation_45/<workflow_id>/*  # three hand-check instances per workflow
  metadata/generation.json
  metadata/workflow-registry.json
  metadata/diversity-audit.json
```

## Manifest row contract

Each row identifies family/workflow/instance, two independent Actor goals, domains, task-relevant parameters, object targets, fixture references and SHA-256 hashes, evaluator path/hash, reset verification, Solo/MA-ID/MA-SD topology contract, provenance, evidence level and self-hash. Expected final values are held in evaluator JSON rather than public fixture files. Filter by `family`, `workflow_id`, and `instance_id`; topology/model/repeat are run selectors and do not mutate the manifest.

`validation_45` is separate from the fixed suite. It contains 3 offline samples per workflow (45 total), each checked for deterministic re-generation and positive/negative oracle behavior. The five new prototypes remain runtime-incomplete.

## Integrity verification

```bash
python scripts/offline_self_test.py
python scripts/audit_instance_suite.py benchmarks/codesk_v1/manifest.jsonl --output /tmp/codesk-audit.json
```

Every path is relative to the suite root; reject path traversal, hash mismatch, missing fixture/evaluator, duplicate ID, and a manifest row whose canonical JSON hash is invalid. Suite directories are immutable: generate to a new path and compare before replacing anything.

# Instance Generation V1

The reproducible generator is `scripts/generate_final_suite_v1.py`. It refuses to overwrite an existing destination and writes the final suite to `benchmarks/codesk_v1_final/` using a temporary staging directory owned by that invocation.

```bash
python3 scripts/generate_final_suite_v1.py --seed 2026
```

The current 15-workflow, 600-row suite at `benchmarks/codesk_v1/` is retained as a prototype/previous-production snapshot with manifest provenance recorded in the new suite metadata. The final V1 quota is 30 workflows × 20 semantic instances = 600 fixed tasks. Each workflow draws across all four domain schemas and five distinct object/operation profiles; layout-only variants are not counted.

The generator validates manifest hashes, fixture hashes, deterministic task IDs, exact positive/negative oracle cases, duplicate/near-duplicate signatures, and runtime-plan compilation. This is offline validation only; real Guest readiness, GUI behavior, observer fidelity, and reset remain a later validation phase.

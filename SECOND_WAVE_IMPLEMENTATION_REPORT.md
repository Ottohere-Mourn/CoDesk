# Second-Wave Implementation Report

Date: 2026-10-03  
Canonical repo: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, branch `v0`  
Status: **OFFLINE_FINAL_SUITE_READY**; not `FULL_HANDOFF_READY`.

## Scope and preserved snapshot

The original 15 workflow suite at `benchmarks/codesk_v1/` was not rewritten. Its 600-row manifest SHA-256 is recorded in `benchmarks/codesk_v1_final/metadata/prototype_snapshot.json` and independently matches the source snapshot. New suite files are under `benchmarks/codesk_v1_final/`.

The task-operation axis is described in `TASK_OPERATION_TAXONOMY_V1.md`; first-wave operation coverage is mapped in the same document and `TASK_DOMAIN_MATRIX_V1.md`. Candidate selection, reserve/rejected designs, goals, shared state, recovery, oracle and difficulty are in `SECOND_WAVE_WORKFLOW_PLAN.md`.

## Selected second wave

All 15 second-wave templates have a production `InstanceSpec → fixture → independent actor goals → exact oracle → runtime observer/setup → reset/cleanup binding → Solo/MA-ID/MA-SD plan` path. Their status is `OFFLINE-CODE-READY`, not real Guest-validated.

| Family | Added workflows | Offline status |
|---|---|---|
| Focus / Input Routing | F-05, F-06, F-07 | 3/3 CODE_READY |
| Clipboard State | C-04, C-05, C-06 | 3/3 CODE_READY |
| Application Context | A-03, A-04, A-05 | 3/3 CODE_READY |
| Selection / Active Object | S-02, S-03, S-04 | 3/3 CODE_READY |
| Undo / Redo History | U-02, U-03, U-04 | 3/3 CODE_READY |
| **Total** | **15** | **15/15 CODE_READY** |

This produces 30 workflow templates in total with family counts 7 / 7 / 5 / 6 / 5. The chosen operation graphs add formula/Find-Replace, Browser+Terminal command execution, character formatting/range fill, URL-to-hyperlink and structured table transfer, sheet/filter/section context, range/phrase/row-set selection, and cross-actor undo/recovery. No template is counted solely from text, seed, coordinate, or repeat changes.

## Final fixed suite

- 30 workflows × 20 semantic instances = **600 fixed tasks**.
- Per-workflow quota: average 20, minimum 20, maximum 20.
- Domain/profile combinations: four domain schemas × five object/operation profiles; the layout-only axis is excluded.
- 600 unique task IDs and 600 unique semantic signatures.
- Exact duplicate audit: 0; near-duplicate audit: 0.
- Positive oracle checks: 600/600; negative oracle checks: 600/600.
- Fixture hashes checked: 1,540/1,540.
- Browser server source syntax checks: 180/180.
- Runtime-plan compile: **600/600** across Solo, MA-ID, MA-SD; `MISSING_IMPLEMENTATION=0`.
- Exact manifest regeneration with the same seed and pinned generator provenance produced the same SHA-256: `ac20e381f2dff99f03af99a7afb218553db838a00a3f41602ee3cdfbd613d583`.
- Final suite size: about 31 MiB. Prior suite remains intact.

Generator command:

```bash
.venv/bin/python scripts/generate_final_suite_v1.py --seed 2026
```

The generator refuses to overwrite an existing suite. It validates the schema, private oracle, fixture hashes, duplicate signatures, concrete runtime bindings, and runtime-plan compilation before publishing the staged directory.

## Offline test results

The focused non-Guest regression selection passed **62 tests**:

```bash
.venv/bin/python -m pytest -q \
  tests/test_production_v1.py tests/test_runtime_execution_v1.py \
  tests/test_runtime_v1.py tests/test_second_wave_v1.py \
  tests/test_runtime_binding_browser_selection_v1.py \
  tests/test_runtime_binding_f_n1.py tests/test_runtime_binding_odf_v1.py \
  tests/test_runner_v1_config.py tests/test_task_factory_v1.py \
  tests/test_task_instances.py
```

Second-wave tests cover deterministic regeneration for every profile/domain pair, positive/negative oracle behavior, concrete setup/observer/evaluator/reset/cleanup callables, Solo A/B and MA-ID/MA-SD FakeBackend lifecycles, and a negative control that detects non-target Writer guard corruption. FakeBackend output is test-only and does not count as experiment evidence.

## Evidence boundary and remaining work

No Guest, Docker, Qwen, model endpoint, or real application was launched in this phase. Thus no second-wave workflow is yet Guest-validated, no model solvability is claimed, and no natural MA-SD interference or recovery is claimed. Modal remains outside the frozen five-family suite. The operation-state observers and Browser local service need one real Guest setup/readiness/reset smoke per template before any model pilot.

The first 15 historical workflow evidence is retained as-is. No first-wave task goal, evaluator rule, or historical experiment artifact was overwritten. Shared-filesystem work remains frozen.

## Checkpoints

- Runtime/template checkpoint: `2fc3a8e1e6bfbaf84868acdc839f6254e0d3652e`
- Generator oracle gate fix: `1036de483efe0040e9fb6ba0452c0cd968c1984b`
- Runtime plan path metadata: `95ae92237347b76ce56004e04f03abca35ccf8cd`
- Pinned deterministic provenance: `ff2c2511b6159834351fdd95bf7f15f48d206b3a`
- Final suite artifact commit: `95c905caa5d9de4473f27e743873676f48ef1fdf`

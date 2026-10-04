# Real Backend Preflight

Date: 2026-10-03. This is an offline code/config preflight; no Docker command, Guest, model, or endpoint request was made.

## Classification

| Area | Status | Evidence / remaining check |
|---|---|---|
| RuntimeExecutor lifecycle | CODE_READY | `RuntimeExecutor` records Actor termination separately from oracle outcome and handles reset/cleanup errors. Fake lifecycle tests pass. |
| Deterministic scheduler API | CODE_READY | Solo / MA-ID / MA-SD mappings, per-actor budget, action-boundary switching, timeout, and observer-fed event gate are implemented. Event source must be bound per workflow. |
| A6000 OSWorld backend shell | CODE_READY, unvalidated | `A6000OSWorldBackend` is lazy; requires pinned source, qcow2, patched provider, and run ownership ledger. It has not been instantiated against Docker. |
| Fixture byte injection | CODE_READY, unvalidated | Host and Guest hashes are checked by the backend implementation; no Guest transfer was attempted. |
| Application launch | CODE_READY, unvalidated | Writer/Calc/Chromium/Terminal launch commands and process/readable-target checks exist. This does not set up Browser workflow state servers or prove task-specific readiness. |
| Exact initial-state checks | MISSING_IMPLEMENTATION | Requires per-workflow semantic observer; screenshot and fixture byte identity are insufficient. |
| Exact hidden-state evaluators | MISSING_IMPLEMENTATION | No generated-instance observer registry for the 15 workflows is registered. Existing evaluators remain inside legacy static runners/probes. |
| Legacy anchor parameterization | MISSING_IMPLEMENTATION | 0/10 legacy Guest scripts have been converted to accept arbitrary `InstanceSpec` inputs and passed equivalence tests. |
| New five workflow execution bindings | MISSING_IMPLEMENTATION | Five setup references compile, but no exact Guest observer/evaluator binding is registered. Validation levels remain unchanged. |
| Ownership-safe cleanup | CODE_READY, unvalidated | Uses pinned provider safety patch; static source marker is checked. Live container ownership/cleanup was not tested. |
| Qwen endpoint interface | RESOURCE_REQUIRED | Existing remote endpoint path is documented in `REMOTE_INFERENCE_4090_A6000.md`; no endpoint check was performed. |
| A6000 Docker/KVM/qcow2 readiness | RESOURCE_REQUIRED | Must be checked before real smoke. No Docker/KVM/resource query was made in this phase. |

## 600-instance backend preflight compile

Run `scripts/compile_backend_preflight.py`. It compiles one backend configuration for every fixed manifest row and emits `benchmarks/codesk_v1/backend_preflight.jsonl` plus a summary. Compile success means the plan has a workflow reference, app launch specification, topology, evaluator/reset bindings, and ownership metadata. It does not imply those workflow bindings are executable; missing setup/evaluator components remain explicit in every record.

## Current result

- Backend configurations compiled: 600/600.
- Fake lifecycle self-tests: 15/15 workflow IDs pass.
- `MISSING_IMPLEMENTATION = 0`: **No.** Task-specific initial-state/evaluator observers, browser state setup, and legacy-anchor parameterization remain missing. This preflight intentionally does not re-label them as resource requirements.
- No Guest or model was started.

## Offline test execution

- `test_production_v1.py`: 3/3 passed.
- `test_runtime_v1.py`: 7/7 passed.
- `test_runtime_execution_v1.py`: 9/9 passed, including 15/15 FakeBackend lifecycle paths, Solo A/B, MA-ID, MA-SD, event gate, task failure, model timeout, invalid readiness, reset failure, and ownership rejection.
- `scripts/offline_self_test.py`: PASS (15 workflows; 45 positive and 45 negative oracle controls; 600 runtime plan compile).
- Five-family FakeBackend smoke: 20/20 synthetic runs returned `SUCCESS`, all marked `FAKE_ORCHESTRATION_ONLY`; no Guest started.
- Five-family A6000 plugin preflight: 20/20 returned `BLOCKED_RUNTIME_BACKEND`; no Guest started.
- Full pytest excluding the Docker-backed `tests/test_real_workspace.py`: 176 passed, 1 failed. The failure is `tests/test_task_factory_v1.py::test_clipboard_template_uses_common_manifest_contract_but_stays_unvalidated`, where the test expects a Writer seed document to contain only the source token but the unchanged `writer_seed_odf()` fixture also contains `INSERT COPIED VALUE`. This task-factory/test pair was not changed in this phase.

No Guest/Docker tests were run. The unrelated failing offline test is retained as a failure; no historical test or evaluator was modified to make it pass.

## Runtime code gate decision

The 600 rows compile into backend configuration records, but all 600 are status `MISSING_IMPLEMENTATION` because their workflow setup and exact observer hooks are not registered; 400 rows (the ten historical anchor workflows × 40 instances) additionally lack the required anchor-equivalence adapter. Thus `600/600 backend preflight compile` is a structural compile pass, **not** a runtime-ready pass. `RUNTIME_CODE_READY` is not reached.

## Future smoke command shape

Once all workflow hooks are registered and the A6000/4090 resources are independently checked, the entrypoint is:

```bash
source scripts/a6000_env.sh
SWCUB_RUNTIME_BINDING_FACTORY=package.module:factory \
  "$CODESK_PYTHON" scripts/run_smoke_suite.py \
  --backend a6000 --execute --model qwen3vl \
  --model-endpoint http://127.0.0.1:15485 \
  --topology solo --topology ma_id --topology ma_sd
```

At this checkpoint that command is **not** a real smoke: the plugin will record `BLOCKED_RUNTIME_BACKEND` for unresolved workflow hooks and start no Guest. The binding factory value above is a required future component, not an existing configuration.

# Workflow Runtime Migration Status

**Scope:** Offline workflow-to-runtime migration only. No Guest, Qwen, Docker, or benchmark episode was started for this migration pass.

## Status summary

- Legacy workflows parameterized with a canonical manifest InstanceSpec and offline historical-equivalence coverage: **10/10**.
- New workflows bound to generated InstanceSpec rows with a concrete runtime binding and self-test: **5/5**.
- Concrete setup + initial-state verifier + observer/evaluator + event gate registry entries: **15/15**.
- Concrete observer/evaluator/reset/cleanup references: **15/15**.
- Manifest rows compiled by the backend preflight: **600/600 CODE_READY**, **0 MISSING_IMPLEMENTATION**, **0 compile failures**.
- Runtime plan compilation: **600/600 compiled** for Solo, MA-ID, and MA-SD.
- **RUNTIME_CODE_READY: YES (offline code/preflight meaning only).**
- **GUEST_VALIDATED: NO for this migration pass.** CODE_READY is not evidence that a Guest launched, an application was ready, or a task passed.

## Workflow bindings

All evaluators flow through `swcub.production_v1.evaluate_oracle`; workflow-specific observer classes provide the measured state. Reset and cleanup use the ownership-checked A6000 Guest backend entry points.

| Workflow | Setup | Observer / task evidence | Evaluator | Reset | Cleanup | Offline binding |
|---|---|---|---|---|---|---|
| F-01 | `_setup_f01` | `F01RuntimeObserver` (foreground document + Writer/Calc state) | `evaluate_oracle` | `A6000OSWorldBackend.reset_guest` | `cleanup_owned_guest` | CODE_READY + legacy equivalence |
| F-04 | `_setup_f04` | `F04RuntimeObserver` (Calc range + Writer target) | same | same | same | CODE_READY + legacy equivalence |
| F-02 | `_setup_f02` | `F02RuntimeObserver` (Browser form + Writer comment/focus) | same | same | same | CODE_READY + legacy equivalence |
| C-01 | `_setup_c01` | `C01RuntimeObserver` (clipboard + Writer/Calc targets) | same | same | same | CODE_READY + legacy equivalence |
| C-02 | `_setup_c02` | `C02RuntimeObserver` (hyperlink target + Browser submission) | same | same | same | CODE_READY + legacy equivalence |
| C-03 | `_setup_c03` | `C03RuntimeObserver` (Calc range + Writer paragraph) | same | same | same | CODE_READY + restored historical graph |
| A-01 | `_setup_a01` | `A01RuntimeObserver` (top-level window + active tab) | same | same | same | CODE_READY + legacy equivalence |
| A-02 | `_setup_a02` | `A02RuntimeObserver` (same-page record/revision) | same | same | same | CODE_READY + legacy equivalence |
| S-01 | `_setup_s01` | `S01RuntimeObserver` (UNO active cell + exact grid) | same | same | same | CODE_READY + legacy equivalence |
| U-01 | `_setup_u01` | `U01RuntimeObserver` (Calc state + coordinator action history) | same | same | same | CODE_READY + legacy equivalence |
| F-N1 | `_setup_f_n1` | `F_N1RuntimeObserver` (two Writer documents/windows) | same | same | same | CODE_READY + generated-instance self-test |
| C-N1 | `_setup_cn1` | `CN1RuntimeObserver` (HTML table structure, URL submit, clipboard snapshots) | same | same | same | CODE_READY + generated-instance self-test |
| A-N1 | `_setup_an1` | `AN1RuntimeObserver` (single-window route/revision) | same | same | same | CODE_READY + generated-instance self-test |
| S-N1 | `_setup_sn1` | `SN1RuntimeObserver` (Writer range/ODF style) | same | same | same | CODE_READY + generated-instance self-test |
| U-N1 | `_setup_un1` | `UN1RuntimeObserver` (Writer final ODF + ordered actor action events) | same | same | same | CODE_READY + generated-instance self-test |

The registry audit checked every manifest workflow ID against the concrete binding registry and the setup/observer/evaluator/reset/cleanup reference map: **15 IDs, no missing or non-callable entries**.

## C-03 conflict resolution

The canonical historical workflow in `swcub/tasks/workflows_v1.py::C03` is preserved:

- Actor A copies Calc `A1:B2` to `A4:B5`, preserving the source and guards.
- Actor B copies Writer paragraph 1 into blank paragraph 2.
- The exact final Calc matrix and Writer paragraphs are checked by the oracle.

The generated C-03 schema and its 40 active manifest rows were corrected to encode that operation graph, source/destination ranges, blank Writer destination, goals, and fixture. Only C-03 active rows/assets were regenerated for the correction; the previous generated C-03 state was retained under `benchmarks/codesk_v1/metadata/archive-c03-runtime-schema-v3/`. An offline equivalence test checks initial state, both goals, final state, evaluator, and reset.

## Evidence limits

- The test suite exercises generated specs, fake Guests, observer logic, positive/negative evaluator cases, and reset/readiness binding. It is not a real application run.
- **C-N1:** the generated Browser server source is syntax-compiled in the test. Rich table structure is checked in ODF and clipboard MIME targets are represented by the observer interface, but this pass did not verify real Guest HTML clipboard transfer or MIME preservation.
- **U-N1:** temporal Undo evidence is derived from coordinator-recorded actor action order plus final ODF state. It does not inspect LibreOffice internal UndoManager.
- Historical Guest/scripted/Qwen evidence remains historical evidence; this pass neither reran nor replaced it.
- No historical result or `artifacts/` directory was modified by the migration validation commands. Workflow-specific pre-regeneration records remain archived.

## Reproduction

From the A6000 CoDesk checkout:

```bash
.venv/bin/pytest -q tests/test_runtime_binding_odf_v1.py tests/test_runtime_binding_f_n1.py tests/test_runtime_binding_browser_selection_v1.py tests/test_runtime_execution_v1.py tests/test_production_v1.py
.venv/bin/python scripts/compile_backend_preflight.py
.venv/bin/python scripts/compile_runtime_suite.py
```

Latest results:

- Focused tests: **31 passed**.
- Backend preflight: **600 compiled, 0 failures, 600 CODE_READY, 0 MISSING_IMPLEMENTATION**.
- Runtime suite: **600 compiled, 0 failed**; Solo / MA-ID / MA-SD plans compiled.
- Both compilers report that no Guest or model was started.

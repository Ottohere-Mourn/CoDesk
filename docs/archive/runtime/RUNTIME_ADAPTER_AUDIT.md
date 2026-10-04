# CoDesk V1 Runtime Adapter Audit

Date: 2026-10-03. Scope: static runner/source reuse and offline compilation. No Guest or model was started for this audit.

## Adapter status meaning

**Plan adapter COMPLETE** means a workflow has a registry entry that compiles the committed InstanceSpec into fixture/app/Actor/evaluator/reset/topology/provenance/ownership execution-plan fields, with fixture and evaluator hashes checked. It does not mean a parameterized OSWorld backend has passed a Guest run. Legacy runners remain preserved and are not silently called with generated instance IDs.

| Workflow | Existing runtime / evidence to reuse | Hard-coded anchor fields found | Instance-driven replacement fields | Adapter status |
|---|---|---|---|---|
| F-01 | `scripts/run_writer_calc_v1.py`, `swcub/actors.py` | Writer final text; Calc Sheet1/B2 and Draft/Approved; file names; initial foreground order | Writer/Calc fixture paths, cell target, headers, initial/expected values, schedule policy | Plan adapter complete; legacy Guest runner remains static |
| F-04 | `scripts/run_workflows_v1.py`, `swcub/tasks/workflows_v1.py` | Calc B2:C3; fixed matrix values; fixed Writer paragraph and guards | range bounds/shape, target paragraph, matrix values, guard placement | Plan adapter complete; generated plan not yet connected to Guest runner |
| F-02 | `scripts/run_browser_writer_workflows_v1.py`, `swcub/tasks/browser_writer_workflows_v1.py` | Browser case/decision, Writer anchor/comment text, paths/port/profile | anchor kind, form fields, task values, fixture paths, revision oracle | Plan adapter complete; existing scripted workflow remains a static anchor |
| C-01 | `scripts/run_clipboard_v1_round1.py`, `swcub/tasks/clipboard_v1.py` | REF-7319/BATCH-204, paragraph/cell positions, clipboard checkpoints | payload type/value, source/destination, target object, clipboard schedule | Plan adapter complete; new spec plan not executed in Guest |
| C-03 | `scripts/run_workflows_v1.py`, `swcub/tasks/workflows_v1.py` | 2×2 range and fixed Writer paragraph/table slot | range bounds/shape, destination slot, payload cells, guard | Plan adapter complete; legacy task stays static |
| C-02 | `scripts/run_browser_writer_workflows_v1.py`, `swcub/tasks/browser_writer_workflows_v1.py` | Reference label/href and Browser destination form | link label semantics, URL target, Browser field, ODF href oracle | Plan adapter complete; generated instances not Guest-validated |
| A-01 | `scripts/run_browser_context_v1.py`, `swcub/tasks/browser_context_v1.py` | Two fixed pages/tabs, tokens, page identities and local server state | page/tab identity, form fields/tokens, initial context and per-tab oracle | Plan adapter complete; generated instance not executed |
| A-02 | `scripts/run_browser_record_context_v1.py`, `swcub/tasks/browser_record_context_v1.py` | Record IDs/labels, field values, selected-record state | record pair/schema, selected object and per-record values/revisions | Plan adapter complete; generated instance not executed |
| S-01 | `scripts/probe_selection_active_object_v1.py`, `scripts/run_selection_qwen_pilot.py` | Calc selected cells, cell values, sheet layout and read-only selection probe | target cell pair, initial state, action and untouched-grid oracle | Plan adapter complete; parameterized runtime not Guest-tested |
| U-01 | `scripts/probe_undo_history_v1.py`, `scripts/run_undo_history_qwen_pilot.py` | Calc edit values, undo order/history observer fields | operation class, object pair, undo depth/order, expected full-grid state | Plan adapter complete; parameterized runtime not Guest-tested |
| F-N1 | `scripts/run_matrix_workflow_v1.py`, `swcub/tasks/matrix_workflows_v1.py` | A-FINAL-731/B-FINAL-204, doc paths, paragraphs/window identities | domain, document/paragraph target, guard and window launch targets | Plan adapter complete; historical evidence remains Guest Solo A/B only |
| C-N1 | same matrix runner/module | Fixed 2×2 HTML table, fixed URL/label, table slot and paths | HTML dimensions/MIME target, destination slot, URL and table-cell oracle | Plan adapter complete; validation level remains offline |
| A-N1 | same matrix runner/module | route-a/route-b labels, tokens, local server state | route pair, field, tokens, initial route and revisions | Plan adapter complete; validation level remains offline |
| S-N1 | same matrix runner/module | ALPHA/BETA text ranges and fixed Writer paragraph | range classes/targets, action, ODF span oracle and guards | Plan adapter complete; validation level remains offline |
| U-N1 | same matrix runner/module | fixed first/second lines, temporary value and undo order | paragraph pair, edit class, undo depth/order and exact document oracle | Plan adapter complete; validation level remains offline |

## Shared runtime contract

`swcub/runtime_v1.py` defines `WorkflowRuntimeAdapter`, `WorkflowRuntimeRegistry`, `RuntimeActorSpec`, `GuestBackend`, and `TurnScheduler`. Each registered adapter exposes `prepare`, `launch`, `get_actor_specs`, `run` (scheduler handoff), `evaluate`, `collect_artifacts`, `reset`, and `cleanup`. Workflow-specific identity/targets come from registry metadata and InstanceSpec; `run_benchmark.py` contains no workflow setup constants. Plans include generator and runtime-adapter source hashes/commits.

The backend protocol is injected. No concrete A6000 OSWorld `GuestBackend` or scheduler implementation is registered yet. This deliberately keeps compilation and readiness checks offline, and keeps existing static runners as preserved evidence. A full parameterized Guest execution adapter has not been empirically validated; do not interpret the 15 registry entries as 15 Guest-capable runtime implementations.

## Offline compile gate

`scripts/compile_runtime_suite.py` compiles one master plan per fixed instance. Each plan contains Solo A/B, MA-ID and MA-SD variants. Compile checks registry lookup, fixture and evaluator existence/hashes, actor goals, target disjointness, schedule, topology counts, reset/evaluator binding, provenance and run-owned artifact/cleanup contracts. It does not create a Guest.

Verified result on A6000: **15/15 plan adapters; 600/600 plan rows compile**. The five new workflows retain their existing `validation_level`. Offline handoff is ready after the recorded tests and compile pass. Full handoff still requires the real five-row Guest smoke through a concrete backend.

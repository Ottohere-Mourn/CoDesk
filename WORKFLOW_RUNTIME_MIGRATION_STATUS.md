# Workflow Runtime Migration Status

当前仓库：`v0`。此表描述 runtime 代码迁移，不代表 Guest 或模型验证。仅当 InstanceSpec 已贯通 setup/readiness/observer/evaluator/reset/cleanup 且有等价测试时，状态才可为 `IMPLEMENTED`。

| Workflow | Historical runner/probe | Fixture/setup | App readiness | Required observer | Actor goals | Evaluator | Reset / cleanup | InstanceSpec parameterized | Runtime binding | Anchor equivalence test | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F-01 | `scripts/run_writer_calc_v1.py` | Static Writer/Calc fixture | Existing static Writer/Calc gates | Focus + saved ODF/Calc state | Static prompts/constants | Static `GuestLibreOfficeBindingEvaluator` | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| F-04 | `scripts/run_workflows_v1.py` | `tasks/workflows_v1.py` fixed F04 fixture | Existing static LO readiness | Foreground + Calc range + ODF | Fixed range/text | `Workflow.evaluate` | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| F-02 | `scripts/run_browser_writer_workflows_v1.py` | Static Browser/Writer setup | Static app checks | Focus + form + Writer comment | Static actor prompts | Static workflow evaluator | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| C-01 | `scripts/run_clipboard_v1_round1.py` | Static Writer/Calc clipboard fixture | Static app checks | X11 clipboard + foreground target | Static source/destination | Static ODF + event evaluator | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| C-03 | `scripts/run_workflows_v1.py` | Fixed Calc-to-Calc / Writer fixture | Existing static LO readiness | Clipboard formats + target state | Historical actor graph differs from generated C-03 range-to-Writer graph | Historical `Workflow.evaluate` | Existing runner lifecycle | No | No | No | BLOCKED_SPEC |
| C-02 | `scripts/run_browser_writer_workflows_v1.py` | Static hyperlink/Browser fixture | Static app checks | Clipboard + href + Browser submit state | Static goals | Static evaluator | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| A-01 | `scripts/run_browser_context_v1.py` | Static two-tab web app | Runner-local server/readiness | Top-level window + active tab + server state | Static tab forms | `BrowserContextTask.evaluate` | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| A-02 | `scripts/run_browser_record_context_v1.py` | Static record app | Runner-local server/readiness | Window + record + revision | Static record goals | Static record evaluator | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| S-01 | `scripts/probe_selection_active_object_v1.py` | Fixed Calc grid/targets | Calc + UNO readiness | UNO selected range + active window | Fixed B2/C3 goals | Fixed exact-grid evaluator | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| U-01 | `scripts/probe_undo_history_v1.py` | Fixed Calc undo fixture | Calc + UNO readiness | Undo timeline + exact grid | Fixed edit/undo sequence | Fixed grid/history evaluator | Existing runner lifecycle | No | No | No | IN_PROGRESS |
| F-N1 | `scripts/run_matrix_workflow_v1.py` | `tasks/matrix_workflows_v1.py` fixed doc pair | Static Writer readiness | Foreground + document identity | Fixed document text | `matrix_workflows_v1.evaluate` | Existing runner lifecycle | No | No | N/A | IN_PROGRESS |
| C-N1 | `scripts/run_matrix_workflow_v1.py` | Fixed Browser HTML + Writer table | Static Browser/Writer readiness | Clipboard owner/generation/MIME + ODF table | Fixed HTML table/URL goals | Matrix evaluator | Existing runner lifecycle | No | No | N/A | IN_PROGRESS |
| A-N1 | `scripts/run_matrix_workflow_v1.py` | Fixed SPA route server | Static route readiness | Same-tab route/revision endpoint | Fixed route values | Matrix evaluator | Existing runner lifecycle | No | No | N/A | IN_PROGRESS |
| S-N1 | `scripts/run_matrix_workflow_v1.py` | Fixed Writer text ranges | Static Writer readiness | UNO selection + ODF spans/styles | Fixed ALPHA/BETA spans | Matrix evaluator | Existing runner lifecycle | No | No | N/A | IN_PROGRESS |
| U-N1 | `scripts/run_matrix_workflow_v1.py` | Fixed Writer edit/undo sequence | Static Writer readiness | Undo events + paragraph state | Fixed paragraph values | Matrix evaluator | Existing runner lifecycle | No | No | N/A | IN_PROGRESS |

## Findings

- The 10 legacy runners/probes contain their own task constants and are not parameterized by `InstanceSpecV1`.
- The new five have concrete prototype setup/evaluator code in `tasks/matrix_workflows_v1.py` and `scripts/run_matrix_workflow_v1.py`, but those constants are not yet consumed from the 600-row manifest.
- C-03 is `BLOCKED_SPEC`: `production_v1` describes Calc rectangular content transferred into a Writer target, while the historical C-03 runner describes Calc range relocation plus a separate Writer paragraph copy. Reusing the historical evaluator would silently score a different action graph. Resolve the frozen task/evaluator contract before wiring it.
- The A6000 checkout used in this pass has no OSWorld source checkout at its configured external path. Offline tests that import static helper code should not require that checkout; Guest execution still must.

## Current counts

- Legacy anchors parameterized: **0/10**.
- New workflows with manifest-driven runtime binding: **0/5**.
- Workflow-specific observer/evaluator/reset bindings in `A6000OSWorldBackend`: **0/15**.
- 600-instance backend compile: **600 compiled, 600 `MISSING_IMPLEMENTATION`**; missing components are setup (600), exact observer (600), and legacy anchor equivalence adapter (400).
- This checkpoint is **not** `RUNTIME_CODE_READY`.

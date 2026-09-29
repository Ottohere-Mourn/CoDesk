# CoDesk Task Suite V1 Implementation Checklist

## Work completed offline

- [x] Audited the frozen protocol, Task API, current Writer/Calc task, legacy focus/CSV tasks, GUI+CLI Browser instance, task manifest, and current runner family map.
- [x] Added an eight-entry V1 declarative registry, grouped into four mechanism families.
- [x] Added a review-only config that refuses to enable Guest/model launch.
- [x] Added schema validation, detached initial-state fixture helper, exact reset comparison, hidden-state exact oracle helper, and event-evidence interaction/recovery metrics.
- [x] Added offline unit tests for registry shape, config guard, state-oracle behavior, reset integrity, evidence-supported attribution, and recovery counting.
- [x] Added task-suite, registry, and implementation-boundary documentation.

## Offline verification performed

- Registry/config CLI validation: passed; 8 task entries, 4 families, 6 design-only entries, 3 conditions.
- Targeted task/evaluator/runner regression: 28 passed (`test_task_registry_v1.py`, `test_task_manifest.py`, `test_task_instances.py`, `test_runner_v1_config.py`, `test_writer_calc_evaluator.py`).
- Offline suite excluding the real-workspace test module: 76 passed. `tests/test_real_workspace.py` was intentionally not run because this phase forbids starting or using a real Guest.
- `git diff --check`: passed before checkpoint.
- No Guest, model, Docker/container, or application was started by this phase.

## Not implemented or not validated

- [ ] No Guest, GUI application, CLI workspace episode, or model was launched in this phase.
- [ ] Six design-only tasks have no app-specific setup, actor actions, screenshots, task evaluator implementation, or reset validation.
- [ ] The GUI+CLI stale-merge registered anchor was not rerun here.
- [ ] The Writer/Calc scripted evidence and two prior Qwen Solo successes were not repeated or independently re-scored here.
- [ ] `run_codesk_experiment.py` does not consume the new catalog or offline config; live registry-to-runner integration is deliberately deferred.
- [ ] The generic helper is not a secure hidden-state boundary by itself. Production integration must keep the oracle in the environment/evaluator process and out of actor context and artifacts visible during acting.
- [ ] Clipboard instrumentation, dialog ownership instrumentation, and browser download event attribution are not present in the existing adapter and need a capability audit before task pilots.

## Task-specific real-environment gates

| Task | Offline contract | Required before promotion |
|---|---|---|
| Writer+Calc anchor | Registered, exact goal/path contract; previous scripted evidence retained | Preserve current readiness and saved-ODF evaluator; rerun only when host scheduling permits |
| Multi-step focus handoff | Goal and causal rule specified | Ensure the normal action sequence has a deterministic scheduling barrier without forcing a misrouted action; inspect input/focus event fidelity |
| Clipboard token transfer | Shared payload replacement and exact destinations specified | Verify Guest clipboard persistence/format API; instrument generation and owner without exposing hidden score; run both Solo goals and safe recovery |
| Clipboard multi-cell transfer | Cell-boundary oracle specified | Prove the clipboard format actually carries TSV/range structure in pinned LibreOffice; drop if evaluator signature duplicates token overwrite |
| Native save-modal ownership | Paths, content, owner evidence specified | Confirm Writer/Calc save dialogs are reproducible at the pinned version; derive active-modal owner from desktop events/accessibility evidence |
| Browser prompt + Writer save | File hash/path oracle specified | Pin the download source and prompt behavior; ensure no real network, unsafe overwrite, or nondeterministic browser policy |
| GUI+CLI stale merge anchor | Existing task spec/evaluator linked | Revalidate reset and provenance under current owner ledger before model comparison |
| Append-only activity log | Exactly-once multiset oracle specified | Implement GUI/CLI paths that naturally append; prove that a complete log is jointly reachable and retries are idempotent |

## Recommended next implementation order

1. Run only offline tests and inspect the resulting local diff/checkpoint.
2. Once host resources are available, revalidate the two anchors (Writer/Calc and stale merge) from clean state; preserve every attempt.
3. Check what OSWorld V2.1 exposes for clipboard contents, active window, active modal, and input target. Add adapter instrumentation only where evidence is unavailable; do not infer from screenshots alone.
4. Implement one clipboard token task as the first new pilot. It is the cleanest separation from focus routing if focus is recorded and held as an independent dimension. Keep exact source/destination state and allow a recopy recovery path.
5. Implement one modal-dialog task only if active modal ownership is observable and both actor goals have non-colliding outputs.
6. Run each pilot's Solo A, Solo B, MA-ID, MA-SD, and recovery controls before considering a second instance in that family. Drop or merge any instance whose evaluator signature duplicates an existing task.
7. Only after a candidate passes these gates, adapt the existing config-driven runner to load a registry ID. Preserve current runner's resource ownership ledger, provenance, artifact isolation, reset verification, and max-worker safety gates.

## Safe offline commands

```bash
python -m swcub.task_registry_v1 tasks/codesk_task_registry_v1.json \
  --config configs/task_suite_v1_offline_review.json
pytest -q tests/test_task_registry_v1.py
```

Do not use the current review config to launch an experiment: it intentionally has no live execution mode and explicitly disables Guest/model launch.

# CoDesk Legacy Runtime Map

Date: 2026-10-03. Read-only source audit plus offline adapter work. No Guest, Docker, or model was started.

## Shared real-Guest path

- Pinned environment: `scripts/a6000_env.sh`, `scripts/run_writer_calc_v1.sh`, and the OSWorld V2.1 checkout configured by `OSWORLD_V2_DIR`.
- Guest construction/readiness reference: `scripts/run_writer_calc_v1.py` (`make_desktop`, `guest_command`, `wait_for_guest_desktop`, `read_seeded_state`) and `swcub/osworld_readiness.py` (`wait_for_guest_desktop`). Browser runner references are in `scripts/run_osworld_v2_1_browser.py` and `scripts/run_browser_context_v1.py`.
- GUI action/observation reference: `swcub/osworld_adapter.py` (`OSWorldSharedEpisode`) wraps the pinned OSWorld `DesktopEnv`; `swcub/osworld_agent_actor.py` wraps the existing agent `predict/reset` protocol.
- Resource ownership: `swcub/resource_safety.py`, `scripts/patch_osworld_docker_runtime.py`. The external Docker provider must contain the project ownership patch; cleanup requires a full container ID, matching project/run/owner labels, and this run's creation ledger.
- Reset, artifacts and event logs are implemented separately in the historical runners; the new executor does not silently substitute generated instances into those static runners.

## Workflow references and remaining parameterization

| Workflow | Closest real Guest runner/probe | Setup / actors / evaluator reference | Instance-driven runtime status |
|---|---|---|---|
| F-01 | `scripts/run_writer_calc_v1.py` | Writer+Calc fixture, scripted and OSWorld actor paths, LibreOffice evaluator | Plan bound; legacy setup/evaluator still static |
| F-04 | `scripts/run_workflows_v1.py` | Calc range and Writer destination workflow | Plan bound; legacy workflow still static |
| F-02 | `scripts/run_browser_writer_workflows_v1.py` | Browser review form + Writer anchor/comment | Plan bound; Browser/Writer state server and evaluator remain runner-specific |
| C-01 | `scripts/run_clipboard_v1_round1.py` | Clipboard observer and Writer/Calc task protocol | Plan bound; event gate/clipboard oracle not attached to generated plan execution |
| C-03 | `scripts/run_workflows_v1.py` | Calc range → Writer structured paste | Plan bound; legacy runner still static |
| C-02 | `scripts/run_browser_writer_workflows_v1.py` | Hyperlink source/destination | Plan bound; exact href evaluator remains runner-specific |
| A-01 | `scripts/run_browser_context_v1.py` | Chrome tab/page state | Plan bound; local page server and exact context observer remain runner-specific |
| A-02 | `scripts/run_browser_record_context_v1.py` | Browser record selection/context | Plan bound; record state endpoint/evaluator remain runner-specific |
| S-01 | `scripts/probe_selection_active_object_v1.py` | Calc selection observer and cell oracle | Plan bound; UNO observer is not registered with the runtime backend |
| U-01 | `scripts/probe_undo_history_v1.py` | Calc history probe and grid oracle | Plan bound; UNO history observer is not registered |
| F-N1 | `scripts/run_matrix_workflow_v1.py` | Two Writer documents/windows | Plan bound; evidence remains `guest_solo`; generated instance setup is not wired |
| C-N1 | `scripts/run_matrix_workflow_v1.py` | Rich table payload workflow | Plan bound; MIME-preserving observer/evaluator is not registered |
| A-N1 | `scripts/run_matrix_workflow_v1.py` | Same-window route state | Plan bound; route/revision service is not registered |
| S-N1 | `scripts/run_matrix_workflow_v1.py` | Writer selection/range | Plan bound; UNO selection observer is not registered |
| U-N1 | `scripts/run_matrix_workflow_v1.py` | Writer edit/undo | Plan bound; UNO history observer is not registered |

## Interpretation

All 15 IDs resolve to an `InstanceSpec`-driven offline execution binding. This does **not** mean the original 10 anchor runners were converted to arbitrary-instance drivers: **0/10 legacy scripts have been parameterized in place**. The five newer workflows have **5/5 compiled setup references**, while **0/5 have a registered exact Guest observer/evaluator binding**. This distinction preserves historical Guest evidence without overstating new runtime coverage.

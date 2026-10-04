# TEST_RESULTS

## OSWorld V2.1 Guest verification update (2026-09-26)

The pinned V2.1 Guest was booted from the official QCOW and exercised through the Docker provider using the documented local QEMU runtime fallback.

| Check | Result | Evidence |
|---|---|---|
| Official OSWorld quickstart reset and GUI action | **PASS, real Guest** | `outputs/osworld-v2.1/quickstart/run.log`: environment reset, PyAutoGUI right-click succeeded, environment closed. |
| Shared GUI+CLI CSV episode | **PASS, real Guest** | `outputs/osworld-v2.1/shared-csv/report.json`: both actors completed in one environment; exact two rows present, no missing/duplicates. |
| Screenshot-driven GUI operation | **PASS, real Guest** | Saved observations show GNOME Activities search and a real Terminal window with the GUI actor's append command. |
| Hidden evaluator separation | **PASS, code path** | Expected rows and host reader callback are not provided in ActorContext; evaluator reads exact Guest file after the actor schedule. |
| Guest reset | **PASS, real Guest** | Report records a new container ID and confirms task file absent after reset. |
| Independent success replay | **PASS, real Guest** | `outputs/osworld-v2.1/shared-csv-repeat-02/report.json`: different Guest/container, same exact final CSV SHA-256, stale GUI actions logged and joint evaluation passes. |
| Stale whole-file overwrite conflict control | **PASS as a negative control, real Guest** | `outputs/osworld-v2.1/stale-overwrite/report.json`: evaluator rejects final state with missing CLI row; conflict detection and clean reset both pass. The task outcome itself is intentionally unsuccessful. |
| GUI focus competition / GUI+Human Replay on OSWorld Guest | **UNVERIFIED** | Not yet ported to a reliable real Guest protocol. Existing separate Docker/Xvfb focus case remains passing. |
| Official scored OSWorld task | **UNVERIFIED** | Gated task/assets were unavailable; shared CSV is a project probe, not an official task. |
| Official pinned runtime image | **NOT USED** | Pull was unavailable; used a local QEMU runtime built from pinned Ubuntu base. |

Early failed Guest attempts are retained in `outputs/osworld-v2.1/shared-csv-attempt-01` to `-04` and are not counted as successful runs. The successful repeat uses its own complete artifact directory; the shared CSV suite launcher now exports the selected output path to the Python runner.

After the final runner, artifact-path, and documentation updates, `python -m pytest -q --junitxml=outputs/test-results/osworld-v2.1-junit.xml` passed **30 passed, 0 failed, 0 skipped in 26.84s**. This includes the new Guest adapter contract tests; those seven contract tests are stub-only. The task manifest validator, shell syntax checks, Python compilation checks, event-log review, and `git diff --check` also passed.

## Real Guest GUI+Human Replay focus update (2026-09-27)

| Check | Result | Evidence |
|---|---|---|
| GUI actor independent Document goal | **PASS, real Guest** | `outputs/osworld-v2.1/focus-gui-solo/report.json`: exact `Approved` file, Chat remains empty. |
| Human Replay independent Chat goal | **PASS, real Guest** | `outputs/osworld-v2.1/focus-human-solo/report.json`: exact `Review note` file, Document remains empty. |
| Joint focus recovery | **PASS, real Guest** | `outputs/osworld-v2.1/focus-recovery-attempt-01/report.json`: both files exact; saved Guest screen shows both GNOME Terminal windows. |
| Stale-focus contamination control | **PASS as a negative control, real Guest** | `outputs/osworld-v2.1/focus-stale-attempt-01/report.json`: evaluator rejects final state because `Approved` is in Chat and Document is empty. |
| Focus scenario reset | **PASS, real Guest** | All four reports show a different new Guest container and absence of both task files. |

All four focus scenario event logs validate as schema V1. Full final test command `python -m pytest -q --junitxml=outputs/test-results/osworld-v2.1-junit-final.xml` passed **32 passed, 0 failed, 0 skipped in 28.40s**. Tests cover the Guest focus evaluator's exact-state logic and actor-to-GUI-operation dispatch; actual Guest claims above come from the separate real runs and screenshots, not from test doubles.

Final verification date: 2026-09-26. The real-environment tests use Docker Ubuntu containers, Xvfb, Tk windows, xdotool desktop actions, guest CLI processes, and mounted files. Separate unit tests validate event/task formats and OSWorld adapter wiring with an explicitly labeled stub; those unit checks are not reported as environment outcomes.

## Automated suite

Command:

```bash
pytest -q --junitxml=outputs/test-results/junit.xml
```

Result: **28 passed, 0 failed, 0 skipped in 27.19s**. Machine-readable report: [`outputs/test-results/junit.xml`](../../../outputs/test-results/junit.xml).

| Test | Result | Evidence checked |
|---|---|---|
| GUI single actor | PASS | Actor receives actual 1024×768 XWD bytes; retained artifact matches its observed screenshot hash; row graded from CSV. |
| CLI single actor | PASS | Guest Python CLI writes row; row graded from CSV. |
| Joint GUI+CLI | PASS | Same environment ID, both exact rows survive, actor-attributed trace; GUI keeps observation revision 0 across its scheduled turns while CLI advances workspace 0→1 and GUI commit advances it 1→2. |
| Stale CSV write conflict | PASS | GUI stale snapshot loses CLI row; evaluator rejects final state and identifies missing C1. |
| Role/evaluator isolation | PASS | GUI context cannot call CLI; CLI cannot observe GUI; neither exposes evaluator. |
| Environment reset | PASS | Dirty state removed by a fresh container/workspace, new GUI window visible, prior container gone. |
| GUI+Human Replay focus recovery | PASS | One real display, three interleaved actor turns, both final window states exact. |
| Stale focus contention | PASS | GUI text goes to Chat after replay steals focus; evaluator rejects both incorrect window state and cross-window contamination. |
| Focus goals independently solvable | PASS | GUI-only and Human Replay-only episodes each satisfy their private goal. |
| Event schema round trip | PASS | V1 version field and contiguous sequence survive JSONL serialization and parsing. |
| Event schema rejection cases | PASS | Unsupported version, missing/extra fields, invalid digest, sequence, malformed JSON, and non-standard constants are rejected. |
| OSWorld adapter contract stubs | PASS | Reset/step, text/key/submit translation, focus translator, evaluator logger, CLI injection and close are covered; tests use an explicit stub and are not real OSWorld results. |
| Task manifest structure and references | PASS | Both tasks have unique roles, independent goals, joint goal, deterministic pass/fail interactions, turn descriptions aligned to schedules, explicit final states, and existing actor/test/smoke references. |

## End-to-end smoke

`python scripts/smoke_real_workspace.py` result: **7/7 checks true**. Machine-readable summary: [`outputs/real-smoke/summary.json`](../../../outputs/real-smoke/summary.json). Scenario reports/logs are in the adjacent per-scenario directories; real XWD screenshots are retained.

Final artifact audit confirmed non-empty event logs, valid XWD screenshot files (`1024x768x24`), no running V0 containers, and no leftover runner temporary workspace directories.

`read_event_log` validated all **32 archived event logs / 409 events** across real Docker runs, repeated runs, clean-build runs, and the separately labeled simulator outputs. CLI checks for joint CSV, focus, conflict, and simulator logs reported schema version 1.

## Cold rebuild verification

Built a no-cache image from the pinned Ubuntu digest and ran `python scripts/smoke_real_workspace.py --image swcub-v0:clean-check --skip-build`: **7/7 smoke checks passed**. The cold-built image ID exactly matched the existing `swcub-v0:local` image ID. All seven directly pinned package versions matched `env/requirements.lock`. Build and episode evidence is in [`outputs/clean-build-validation/manifest.json`](../../../outputs/clean-build-validation/manifest.json).

## Repeated deterministic replay

Command: `python scripts/repeatability_study.py 5`.

Result: **20 fresh-container episodes, all expected outcomes observed, and one final-state hash per policy across five repetitions**. Both CSV actor orders passed 5/5 and produced the same final-state hash; focus recovery passed 5/5; stale-focus control failed evaluation as intended in 5/5. CSV schedules now include GUI observe → CLI append → GUI submit. Median actor/evaluation/report time was 0.999s, 0.992s, 2.038s, and 1.610s respectively (reset/build excluded). See [`outputs/repeatability/REPORT.md`](../../../outputs/repeatability/REPORT.md) and [`study.json`](../../../outputs/repeatability/study.json).

These results establish deterministic scripted replay on this local Docker/Xvfb setup. They do not establish cross-host reproducibility, model/human performance, or benchmark validity.

## Resolved attempts and unverified areas

- Initial `pytest -q` collection missed the repository import path. Added pytest path configuration; `pytest -q` and `python -m pytest -q` subsequently passed.
- Early smoke issues (missing isolated `DISPLAY` on one xdotool query and Tk child Entry focus after top-level focus) were fixed and the full smoke rerun.
- **UNVERIFIED:** actual OSWorld VM/provider execution, model actors, alternative real applications/backends, truly simultaneous key events, and statistical benchmark validity.
- **NOT RUN:** training, batch data generation, large downloads, GPU workloads.

## Clean checkout replay

A detached temporary worktree of commit `a53ebb0` passed `python -m pytest -q --junitxml=outputs/test-results/junit.xml` (**28 passed in 27.08s**) and `python scripts/smoke_real_workspace.py --skip-build` (**7/7 checks true**). The smoke used the existing locally built pinned image. The temporary worktree was removed after verification.

## OSWorld V2.1 real application episodes (2026-09-27)

All rows below are real OSWorld V2.1 Guest runs using the pinned local QEMU runtime and shared desktop/file state. Each completed run has `events.jsonl`, screenshots, a hidden-state evaluator result, and a reset check under the linked output path. Scripted actor/interface tests are reported separately at the end.

| Task / condition | Result | Evidence |
|---|---|---|
| Writer solo and Calc solo | **PASS, real Guest** | [`writer-solo/report.json`](../../../outputs/osworld-v2.1/office/writer-solo/report.json), [`calc-solo-attempt-05/report.json`](../../../outputs/osworld-v2.1/office/calc-solo-attempt-05/report.json). ODF evaluator checks exact Writer text and Calc cells; earlier failed Calc coordinates remain in `calc-solo-attempt-01..04`. |
| GUI+GUI sequential | **PASS, real Guest** | [`sequential-attempt-02/report.json`](../../../outputs/osworld-v2.1/office/sequential-attempt-02/report.json): both actor goals pass with no cross-application corruption. The first sequential run is retained as a startup/focus failure. |
| GUI+GUI focus-aware | **PASS, real Guest** | [`focus-aware/report.json`](../../../outputs/osworld-v2.1/office/focus-aware/report.json): Calc takes focus; Writer reselects its window and both saved documents satisfy exact goals. |
| GUI+GUI naive interleaving | **PASS as an expected negative control, real Guest** | [`naive-interleaving-attempt-02/report.json`](../../../outputs/osworld-v2.1/office/naive-interleaving-attempt-02/report.json): Writer text lands in Calc B2, Writer remains draft, both goals fail, and the failure is correctly classified. The first invalid negative-control attempt is retained separately. |
| Browser GUI solo and CLI solo | **PASS, real Guest** | [`gui-cli-gui-solo-attempt-02/report.json`](../../../outputs/osworld-v2.1/browser/gui-cli-gui-solo-attempt-02/report.json), [`gui-cli-cli-solo-attempt-03/report.json`](../../../outputs/osworld-v2.1/browser/gui-cli-cli-solo-attempt-03/report.json). |
| Browser GUI+CLI refresh | **PASS, real Guest** | [`gui-cli-refresh/report.json`](../../../outputs/osworld-v2.1/browser/gui-cli-refresh/report.json): GUI writes `Approved` and preserves the CLI's `Reviewed by CLI` update. |
| Browser GUI+CLI stale save | **PASS as an expected negative control, real Guest** | [`gui-cli-stale/report.json`](../../../outputs/osworld-v2.1/browser/gui-cli-stale/report.json): GUI target succeeds while saving a cached page drops the intervening CLI update; evaluator identifies the exact missing field. |
| Human Replay solo and GUI Agent solo | **PASS, real Guest** | [`human-solo-attempt-02/report.json`](../../../outputs/osworld-v2.1/browser/human-solo-attempt-02/report.json), [`agent-solo/report.json`](../../../outputs/osworld-v2.1/browser/agent-solo/report.json). The first Human solo report is retained; attempt 02 fixes its non-participant actor summary. |
| Browser GUI+Human focus-aware | **PASS, real Guest** | [`human-agent-focus-aware-attempt-02/report.json`](../../../outputs/osworld-v2.1/browser/human-agent-focus-aware-attempt-02/report.json): independent Human Replay review and GUI Agent approval both persist. |
| Browser GUI+Human naive | **PASS as an expected negative control, real Guest** | [`human-agent-naive/report.json`](../../../outputs/osworld-v2.1/browser/human-agent-naive/report.json): Human review persists while the GUI actor's input is lost when it does not reacquire the field. |
| Guest reset after GUI and CLI mutations | **PASS, real Guest** | Completed reports above record a new Guest container ID and task state absent after reset. A CLI-only reset bug was found and fixed by marking `DesktopEnv.is_environment_used`; pre-fix failures are retained in earlier CLI solo artifacts. |
| Task instance definitions and triggered schedules | **PASS** | `python scripts/validate_task_instances.py` validates the three JSON instances; the office and browser runners resolve their actor-turn triggers from those records. |
| Event logs and summary | **PASS** | [`summary.json`](../../../outputs/osworld-v2.1/summary.json) includes complete/reset-success episodes only. Its counts mix solo, recovery, and intentional negative-control conditions and are descriptive, not performance estimates. |

Final automated command: `python -m pytest -q --junitxml=outputs/test-results/osworld-v2.1-real-apps-junit.xml` — **40 passed, 0 failed, 0 skipped in 27.45s**. `validate_task_manifest.py`, `validate_task_instances.py`, Python compilation, shell syntax checks, and `git diff --check` passed. Unit and interface contract tests that use stubs remain explicitly separate from the real-Guest rows above.

**Not tested:** model actors, model/human performance, official OSWorld scored tasks, statistical comparisons, and truly simultaneous OS-level input. The new Human Replay target is a deterministic replayed browser form action, not a live user study.

## Bounded repeat runs (2026-09-27)

Repeated each positive two-actor schedule once on a fresh Guest. All six paired participant goals and all three post-run resets passed. Existing first runs are linked above; repeat reports are:

| Pair / schedule | Repeats | Second Guest evidence |
|---|---:|---|
| GUI+GUI Writer/Calc focus-aware | 2 successful runs total | [`focus-aware-repeat-02/report.json`](../../../outputs/osworld-v2.1/office/focus-aware-repeat-02/report.json) |
| GUI+CLI browser refresh/merge | 2 successful runs total | [`gui-cli-refresh-repeat-02/report.json`](../../../outputs/osworld-v2.1/browser/gui-cli-refresh-repeat-02/report.json) |
| GUI+Human Replay browser focus-aware | 2 successful runs total | [`human-agent-focus-aware-repeat-02/report.json`](../../../outputs/osworld-v2.1/browser/human-agent-focus-aware-repeat-02/report.json) |

These repeats establish that the three scripted positive schedules replayed successfully twice on this host. Negative controls still have one successful reproduction each; this is a smoke-level sample, not a comparison or reliability estimate. The `outputs/osworld-v2.1/summary.json` report is regenerated from all complete episodes with successful reset and explicitly labels its mixed-condition counts descriptive.

## Local VLM smoke (2026-09-27)

| Check | Result | Evidence |
|---|---|---|
| Repeat focus-interference negative control | **PASS, scripted real Guest** | `outputs/osworld-v2.1/office/naive-interleaving-repeat-02/report.json`; expected cross-application input detected, reset passed. |
| Repeat GUI+CLI stale-state negative control | **PASS, scripted real Guest** | `outputs/osworld-v2.1/browser/gui-cli-stale-repeat-02/report.json`; missing CLI update detected, reset passed. |
| Repeat GUI+Human focus-loss negative control | **PASS, scripted real Guest** | `outputs/osworld-v2.1/browser/human-agent-naive-repeat-02/report.json`; lost GUI goal detected, reset passed. |
| Negative-control event schemas | **PASS** | V1 logs validate: 25, 19, 19 events. |
| Qwen2.5-VL-3B Writer solo | **FAIL as a model task; evaluator/reset PASS** | Five real inference records. Model failed to select all text before typing; final artifact unchanged. `model_failure_class=model_or_action_execution_failure`. |
| Qwen2.5-VL-3B Calc solo | **FAIL as a model task; evaluator/reset PASS** | Eight real inference records. Model wrote `Approved` into A2 instead of B2; exact evaluator detected cell contamination. |
| Qwen3-VL-4B Calc solo | **FAIL as a model task; evaluator/reset PASS** | Four valid model actions (click/type/save/done). The click landed in A2 instead of B2; the exact evaluator detected the wrong cell and task corruption. Reset passed. |
| Full repository tests | **PASS** | `python -m pytest -q`: **51 passed, 0 failed**. |
| Local VLM action parser tests | **PASS** | `tests/test_local_vlm.py`: 11 passed. |
| Compile and shell checks | **PASS** | `python -m compileall -q swcub scripts/run_osworld_v2_1_office.py scripts/local_qwen_worker.py`; `bash -n scripts/run_osworld_v2_1_office.sh`. |

These model episodes are live local inference on the real OSWorld Guest; they are not scripted actor results. All three failed solo due to model task execution/grounding. They provide no performance estimate and do not justify shared-condition comparisons.

Final post-edit validation: `python -m pytest -q` — **51 passed**; task manifest and all three task instances validated; compileall, shell syntax, and `git diff --check` passed. All six repeated negative-control/model `events.jsonl` files validated (25, 19, 19, 20, 29, and 27 events).

## OSWorld-native agent integration (2026-09-27)

The previous JSON-action local actor is retired. These rows use OSWorld V2.1's own `Qwen3VLAgent` with local Qwen3-VL-30B-A3B-Instruct weights, the pinned Guest, native OSWorld screenshot preprocessing/history/action parser/coordinate scaling, and the real PyAutoGUI executor. They are separate from the original OSWorld GPT-4o paper baseline and do not represent a leaderboard result.

| Episode | Result | Evidence / interpretation |
|---|---|---|
| Writer solo, first attempt | **FAIL, real model + real Guest** | [`writer-osworld-agent-solo-attempt-01/report.json`](../../../outputs/osworld-v2.1/office/writer-osworld-agent-solo-attempt-01/report.json). The model sent select/delete/type/save without first clicking the document body; the saved Writer text remained unchanged, Calc was unchanged, and reset passed. Five native agent predictions and screenshots are retained. |
| Writer solo, explicit focus instruction | **PASS, real model + real Guest** | [`writer-osworld-agent-solo-explicit-click/report.json`](../../../outputs/osworld-v2.1/office/writer-osworld-agent-solo-explicit-click/report.json). Five model predictions: click paragraph → Ctrl+A → type exact target → Ctrl+S → DONE. The independent evaluator found exact Writer text `Approved by GUI actor`, untouched Calc cells, and reset passed with a new Guest container. Actual Guest screenshots (including [`guest-screen.png`](../../../outputs/osworld-v2.1/office/writer-osworld-agent-solo-explicit-click/guest-screen.png)), native actions, per-step hashes, model responses, worker log and event log are saved beside the report. |
| Writer agent + scripted Calc sequential attempt | **FAIL, real shared Guest attempt** | [`writer-agent-calc-scripted-sequential/report.json`](../../../outputs/osworld-v2.1/office/writer-agent-calc-scripted-sequential/report.json). On this episode the model repeatedly alternated Ctrl+A/Ctrl+V and hit the 20-step bound; the Orchestrator stopped before the scripted Calc actor received a turn. The evaluator identified the missing Writer and Calc goals. This is a model task failure and an incomplete shared pair, not a valid two-actor success or a shared-interference result. Reset passed. The full Guest screenshots and [`agent-messages`](../../../outputs/osworld-v2.1/office/writer-agent-calc-scripted-sequential/agent-messages) are retained. |
| Repository regression suite after scenario addition | **PASS** | `python -m pytest -q --junitxml=outputs/test-results/framework-integration-junit.xml` — **40 passed, 0 failed in 31.02s**. |
| Integration syntax/import/event checks | **PASS** | Python compilation, `bash -n`, `git diff --check`, and the pinned OSWorld V2.1 runner's `--help` command pass with the OSWorld UV environment. `read_event_log` validated all three model episode logs (25, 25 and 71 events). |

The solo pass demonstrates that the reusable agent/environment bridge can complete one real office task. The single successful episode is not a reliability estimate. Do not begin model-based interleaving comparisons until the agent can complete its solo target consistently and the paired actor receives a scheduled turn.

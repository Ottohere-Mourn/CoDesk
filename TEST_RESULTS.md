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

Final verification date: 2026-09-26. The real-environment tests use Docker Ubuntu containers, Xvfb, Tk windows, xdotool desktop actions, guest CLI processes, and mounted files. Separate unit tests validate event/task formats and OSWorld adapter wiring with an explicitly labeled stub; those unit checks are not reported as environment outcomes.

## Automated suite

Command:

```bash
pytest -q --junitxml=outputs/test-results/junit.xml
```

Result: **28 passed, 0 failed, 0 skipped in 27.19s**. Machine-readable report: [`outputs/test-results/junit.xml`](outputs/test-results/junit.xml).

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

`python scripts/smoke_real_workspace.py` result: **7/7 checks true**. Machine-readable summary: [`outputs/real-smoke/summary.json`](outputs/real-smoke/summary.json). Scenario reports/logs are in the adjacent per-scenario directories; real XWD screenshots are retained.

Final artifact audit confirmed non-empty event logs, valid XWD screenshot files (`1024x768x24`), no running V0 containers, and no leftover runner temporary workspace directories.

`read_event_log` validated all **32 archived event logs / 409 events** across real Docker runs, repeated runs, clean-build runs, and the separately labeled simulator outputs. CLI checks for joint CSV, focus, conflict, and simulator logs reported schema version 1.

## Cold rebuild verification

Built a no-cache image from the pinned Ubuntu digest and ran `python scripts/smoke_real_workspace.py --image swcub-v0:clean-check --skip-build`: **7/7 smoke checks passed**. The cold-built image ID exactly matched the existing `swcub-v0:local` image ID. All seven directly pinned package versions matched `env/requirements.lock`. Build and episode evidence is in [`outputs/clean-build-validation/manifest.json`](outputs/clean-build-validation/manifest.json).

## Repeated deterministic replay

Command: `python scripts/repeatability_study.py 5`.

Result: **20 fresh-container episodes, all expected outcomes observed, and one final-state hash per policy across five repetitions**. Both CSV actor orders passed 5/5 and produced the same final-state hash; focus recovery passed 5/5; stale-focus control failed evaluation as intended in 5/5. CSV schedules now include GUI observe → CLI append → GUI submit. Median actor/evaluation/report time was 0.999s, 0.992s, 2.038s, and 1.610s respectively (reset/build excluded). See [`outputs/repeatability/REPORT.md`](outputs/repeatability/REPORT.md) and [`study.json`](outputs/repeatability/study.json).

These results establish deterministic scripted replay on this local Docker/Xvfb setup. They do not establish cross-host reproducibility, model/human performance, or benchmark validity.

## Resolved attempts and unverified areas

- Initial `pytest -q` collection missed the repository import path. Added pytest path configuration; `pytest -q` and `python -m pytest -q` subsequently passed.
- Early smoke issues (missing isolated `DISPLAY` on one xdotool query and Tk child Entry focus after top-level focus) were fixed and the full smoke rerun.
- **UNVERIFIED:** actual OSWorld VM/provider execution, model actors, alternative real applications/backends, truly simultaneous key events, and statistical benchmark validity.
- **NOT RUN:** training, batch data generation, large downloads, GPU workloads.

## Clean checkout replay

A detached temporary worktree of commit `a53ebb0` passed `python -m pytest -q --junitxml=outputs/test-results/junit.xml` (**28 passed in 27.08s**) and `python scripts/smoke_real_workspace.py --skip-build` (**7/7 checks true**). The smoke used the existing locally built pinned image. The temporary worktree was removed after verification.

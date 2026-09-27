# RUN_LOG

## OSWorld V2.1 real Guest deployment and shared CSV run (2026-09-26)

- **Pinned real Guest provisioned on RAID1:** OSWorld V2.1 code tag resolves to `3d778a3c9a34a079316f70df023b166700445792`; release manifest is preserved at `outputs/osworld-v2.1/environment/release_manifest.json`. Downloaded official Ubuntu Guest archive is 14,891,811,084 bytes and SHA-256 `14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3`. Archive and extracted QCOW live at `/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/`; VM overlays and task cache also point to `/mnt/raid1/mjh`.
- **Runtime limitation and workaround:** the release-pinned official runtime image pull was denied/unreachable. Built `swcub/osworld-v2.1-qemu-runtime:local` from a digest-pinned Ubuntu base and recorded QEMU/OVMF package versions. The pinned OSWorld Docker provider has a narrow local patch for runtime-image selection and RAID1 copy-on-write overlays. This executes the real official Guest QCOW but does not claim the official runtime image was used.
- **Official quickstart real Guest PASS:** `scripts/run_osworld_v2_1_quickstart.sh` completed `Environment reset complete`, dispatched actual `pyautogui.rightClick()`, reported `Action executed successfully`, and closed. Log: `outputs/osworld-v2.1/quickstart/run.log`.
- **Shared GUI+CLI real Guest PASS:** `scripts/run_osworld_v2_1_shared_csv.sh` launched two independent scripted actor objects against one `OSWorldSharedEpisode` and one Docker Guest container. GUI actor observed screenshots, clicked GNOME Activities, typed the Terminal search, launched the real desktop terminal and typed its append command. CLI actor ran a separate Guest CLI append. The hidden host-side exact CSV evaluator found both expected rows, zero duplicates, and the final SHA-256 `18b91afe6ac5fc0f743bdce0f4bdd4be85caea0c50d77ab93752084a326ced5c`. Shared Guest container ID: `9c6e9c28b973c66ca2b2d2709027069ab49f0941918a7972ef020a6bdcbcaec8`. Report, full event trace and five real screenshots are in `outputs/osworld-v2.1/shared-csv/`.
- **Real Guest reset PASS:** reset created Guest container `5e1f9b609554bdf029f399f54b4ca0f574d2a66cb8a239bbc93155187a0d5f12`; readiness screenshot was visible and `/tmp/swcub_shared.csv` was absent.
- **Independent success replay PASS:** a second clean Guest produced the same CSV SHA-256, `18b91afe6ac5fc0f743bdce0f4bdd4be85caea0c50d77ab93752084a326ced5c`. It recorded two stale GUI actions (GUI observed revision 1, current revision 2) while still preserving both rows. The separate artifacts are in `outputs/osworld-v2.1/shared-csv-repeat-02/`.
- **Real Guest stale-overwrite control PASS (expected task failure):** ran `scripts/run_osworld_v2_1_shared_csv.sh --scenario stale-overwrite`. After CLI appended its independent row, GUI committed a stale whole-file snapshot through the visible Guest terminal. Exact hidden evaluation rejected joint completion: only GUI row remained and CLI row was missing. The control marked `stale_overwrite_detected`; reset then created a new Guest and confirmed the task file absent. Evidence: `outputs/osworld-v2.1/stale-overwrite/report.json`, `events.jsonl`, screenshots.
- **Failures preserved:** early real Guest attempts failed because Ctrl+Alt+T did not launch GNOME Terminal and because reset returned before a visible desktop; one upstream task readiness probe could hang without an HTTP timeout. Attempt evidence is saved under `shared-csv-attempt-01` through `shared-csv-attempt-04`. Runner now uses bounded screenshot readiness and desktop Activities search. These failures remain part of the artifact trail.
- **Current full test suite:** after the OSWorld adapter, actors and evaluator additions, `python -m pytest -q` passed **30/30 in 27.64s**. The suite includes real Docker/Xvfb cases and separately labeled OSWorld adapter contract stubs. Stub tests do not count as Guest validation.
- **Not verified:** OSWorld's gated task/assets download and official task scoring; successful run on the upstream official Docker runtime; OSWorld Guest multi-window GUI focus contention or GUI+Human Replay; model actors; true simultaneous keyboard injection.

## OSWorld Guest focus contention follow-up (2026-09-27)

- Added four repeatable Guest scenarios to the same runner: `focus-gui-solo`, `focus-human-solo`, `focus-recovery`, and `focus-stale`. Setup launches two visible GNOME Terminal windows, `Document` and `Chat`, with each terminal accepting input into a different file. GUI and Human Replay use real Guest mouse clicks and keyboard input; the evaluator reads exact contents through a host-held Guest CLI callback.
- **GUI solo PASS:** `outputs/osworld-v2.1/focus-gui-solo/report.json` has `Document="Approved\n"`, empty Chat. Reset produced a new Guest container and removed both files.
- **Human Replay solo PASS:** `outputs/osworld-v2.1/focus-human-solo/report.json` has empty Document, `Chat="Review note\n"`. Reset produced a new Guest container and removed both files.
- **GUI+Human Replay recovery PASS:** `outputs/osworld-v2.1/focus-recovery-attempt-01/report.json` has both exact independent goals and no cross-window contamination. Screenshots show both real windows and the final text. Reset passed.
- **Stale-focus control PASS as negative control:** `outputs/osworld-v2.1/focus-stale-attempt-01/report.json` shows Document empty and Chat containing both `Review note` and the misdirected `Approved`. The task evaluator correctly returns failure; the control records `stale_focus_misdirected`, and reset passes.
- Four focus event logs validate as event schema V1 (13, 11, 17 and 16 records respectively). The outcomes are serial interleavings, not simultaneous keyboard races.
- Added adapter-level tests for exact hidden focus evaluation and actor click/type dispatch. Final full suite: `python -m pytest -q --junitxml=outputs/test-results/osworld-v2.1-junit-final.xml` passed **32/32 in 28.40s**. An initial assertion inspected the event's display label rather than its source action; the test was corrected to validate `details.source_action` and rerun successfully.
- **Still not verified:** official OSWorld task/asset scoring, upstream official runtime image, model actors, GUI+GUI coordination, simultaneous input races, or another host.

## Local visual model validation (2026-09-27)

- **Local resources found:** eight RTX 4090 GPUs; used free `cuda:0` (GPU 1 was already occupied by an unrelated process). Reused the existing `/mnt/raid1/mjh/models/Qwen/Qwen2.5-VL-3B-Instruct` checkpoint and `/opt/miniconda3` Transformers runtime. Also found `/mnt/raid1/mjh/models/Qwen3-VL-4B-Instruct`; no weights were downloaded and no API was called.
- **P0 negative-control replay PASS:** repeated Writer/Calc focus interference, browser GUI+CLI stale save, and browser GUI+Human Replay focus loss on clean real Guests. Each expected negative outcome was detected, task state was removed on reset, and the reset Guest had a different container ID. The three event logs validate as V1 with 25, 19, and 19 events respectively.
- **Retired custom model loop (historical):** `LocalQwenGUIActor` sent real screenshots to a local worker and parsed a project-defined JSON click/type/key/done format. It was used only for the failed exploratory trials below. The class, schema and custom parser have been removed; this is not the current model baseline.
- **Qwen2.5-VL-3B Writer solo FAIL, evaluator and reset PASS:** five model responses were recorded. The model first emitted an out-of-bounds coordinate, then clicked Writer, but repeatedly tried to type without `Ctrl+A`; the action precondition stopped the edit. The final document remained `Quarterly status report`, and the independent evaluator rejected the goal. Reset removed the task state and launched a different Guest. Evidence: `outputs/osworld-v2.1/office/writer-model-solo-qwen2_5vl-3b-attempt-05/`.
- **Qwen2.5-VL-3B Calc solo FAIL, evaluator and reset PASS:** eight responses were recorded. The model clicked A2 (the Record cell) and wrote `Approved` there instead of changing B2 (Status); the exact final-state evaluator caught both the missing B2 update and cross-cell contamination. Reset passed. Evidence: `outputs/osworld-v2.1/office/calc-model-solo-qwen2_5vl-3b-attempt-01/`.
- **Qwen3-VL-4B Calc solo FAIL, evaluator and reset PASS:** four real model actions were recorded. The model correctly returned click/type/save/done actions, but clicked A2 at `(116,230)` instead of adjacent B2; the exact evaluator rejected the result. This is a model grounding/task failure, not a shared-desktop failure. Evidence: `outputs/osworld-v2.1/office/calc-model-solo-qwen3vl-4b-attempt-01/`.
- These failed episodes used the retired custom actor and are not evidence about the OSWorld-native agent. The exact evaluator caught task failures, reset worked, and no shared comparison was run with those custom-harness trials.

Date: 2026-09-26 (Asia/Shanghai). Working directory: `/home/mjh/Projects/Shared-Workspace-Benchmark-V0`, standalone Git repository on branch `v0`. The original `Multi-GUI-Agent-Bench` directory was copied as the starting point and left untouched during V0 implementation.

## Environment and access audit

- Host: Python 3.13.2, pytest available, Docker Engine 29.1.3; user `mjh` is in the `docker` group.
- Docker image `ubuntu:22.04` was present locally. Its repo digest is pinned in `Dockerfile` as `sha256:3ba65aa20f86a0fad9df2b2c259c613df006b2e6d0bfcc8a146afb8c525a9751`.
- Installed only the listed, version-pinned guest packages for the isolated image: Python 3.10.6, Tk 3.10.8, Xvfb 21.1.4, xdotool 3.20160805.1, x11-utils 7.7+5, x11-apps 7.7+8, and ca-certificates 20260601. Package inventory is saved in `env/requirements.lock`.
- `desktop_env`/OSWorld and pyautogui were not installed. `/dev/kvm` exists. Host `DISPLAY` is unset; `:0` belongs to user `supermicr`, and authorization failed. No attempt was made to access or alter that session. V0 uses isolated Xvfb inside disposable containers.
- No GPU used; scripted desktop and CSV workloads are CPU-bound.

## Implementation and execution

- Added a common reset/observe/act/snapshot/close `EnvironmentAdapter`, actor protocol, role-scoped actor tools, `DualActorOrchestrator`, shared event log, final-state evaluators, Docker/X11 environment, and OSWorld adapter seam.
- Each episode uses one Ubuntu container, one Xvfb display and one temporary workspace. The GUI and CLI channels share `/workspace/shared.csv`; the GUI and Human Replay channels interact with two windows on one X11 display.
- Final `python scripts/smoke_real_workspace.py` run passed all seven checks: GUI-only CSV, CLI-only CSV, joint GUI+CLI, stale CSV write rejected, recovered GUI+Human focus task, stale-focus failure detected, and environment reset.
- Final `pytest -q --junitxml=outputs/test-results/junit.xml` passed all nine real environment tests. Reports, JSONL logs, XWD screen captures and final application state are under `outputs/real-smoke/`.
- Fixed two implementation issues during development: a window-title query initially lacked `DISPLAY=:99`; and the pytest console entrypoint initially omitted repository import configuration. Both were fixed and rerun. The first focus recovery attempt also showed that X11 top-level focus alone did not set the Tk Entry focus in Xvfb; adding a real pointer click to the selected entry fixed it. The stale-focus control then reproduced the intended misdirected text.
- Removed only containers and temporary workspace directories created by this runner. Final audit found no running V0 containers or leftover `/tmp/swcub-episode-*` directories. No unrelated containers, images, project files, or host configuration were changed.

## Research boundary

The real CSV and two-window focus cases are controlled infrastructure probes, not benchmark-scale task coverage. The OSWorld adapter follows the discovered `DesktopEnv` call shape but was not exercised because the package/task assets are absent. No model was connected and no paper claim or statistical hypothesis was tested.

## Continued replay validation

- Added `scripts/repeatability_study.py` and an orchestrator option to skip copying XWD/application artifacts while retaining reports and event logs. This keeps repeated execution bounded without changing the default artifact behavior used by the main smokes and tests.
- Ran 20 fresh-container episodes: five each for GUI→CLI CSV, CLI→GUI CSV, GUI+Human focus recovery, and stale-focus failure. All four policies produced one unique final-state SHA-256 across their five trials. Expected outcome was 5/5 for each policy (20/20 total).
- Median actor/evaluation/report time (container reset and image build excluded): GUI→CLI 0.999 s; CLI→GUI 0.991 s; focus recovery 2.052 s; stale-focus failure 1.625 s. These are local scripted replay timings, not benchmark performance claims.
- After generalizing the evaluator event action name to `evaluate`, reran the 20 episode replay study and all final checks. `python scripts/smoke_real_workspace.py`: 7/7 true. `python -m pytest -q --junitxml=outputs/test-results/junit.xml`: 9 passed, 0 failed, 0 skipped in 26.97 s.
- Detailed replay rows and per-trial reports/event traces: `outputs/repeatability/study.json`, `outputs/repeatability/REPORT.md`, and the policy subdirectories. The script is bounded to 1–20 episodes per policy and deletes/recreates only its own `outputs/repeatability/` directory.
- These repeats validate deterministic scripted outcomes only. They do not test model/human behavior, truly simultaneous events, external OSWorld execution, or statistical benchmark validity.

## Event log schema and artifact validation

- Added event schema V1 to every JSONL record with contiguous sequence, UTC timestamp, elapsed time, actor/interface/action, optional observed revision, before/after digests, outcome and details.
- Added strict `read_event_log` validation and `python -m swcub.cli validate-events PATH`; unsupported versions, field changes, malformed timestamps/digests and sequence errors fail with a line-specific diagnostic. Evaluator documentation now treats schema changes as explicit versioned changes.
- Added seven contract tests and made the real joint GUI+CLI integration assertion parse its emitted trace through the validator. Full suite: `python -m pytest -q --junitxml=outputs/test-results/junit.xml` passed 16/16 in 27.22s.
- Reran all Docker smokes (7/7), all 20 repeatability episodes, and regenerated only `outputs/smoke/` using the separate deterministic simulator command to refresh its old-format logs. This directory remains simulator evidence, not real-environment evidence. After adding strict non-standard JSON constant rejection, reran the 16-test suite and the Docker smokes again.
- Parsed all 32 archived event logs (409 total events) successfully as schema V1 after adding clean-build and stale-observation schedule traces. Representative CLI checks on joint CSV, focus, conflict, and simulator logs each reported valid version 1.

## Cold image rebuild

- Ran `docker build --no-cache --pull=false --tag swcub-v0:clean-check --file Dockerfile .` from the pinned local Ubuntu base digest. Apt fetched package indexes and installed only the package set pinned in `env/requirements.lock` plus required transitive dependencies.
- Queried the resulting image with `dpkg-query`: all seven direct package versions exactly matched the lock file. The new image ID was byte-identical to the existing `swcub-v0:local` image (`sha256:75437cf018982d37c3093b710041dc1e7c33dab785b006cc738e1809d2aec1a6`).
- Ran the full real smoke suite with `python scripts/smoke_real_workspace.py --image swcub-v0:clean-check --skip-build`: 7/7 checks passed. Separately ran fresh-image CSV joint success, focus recovery success, and stale-write rejection; all three logs validated as schema V1.
- The 16-test suite passed again in 27.24 s. Build details, container IDs, package versions and checks are saved in `outputs/clean-build-validation/manifest.json`.
- Removed only the temporary `swcub-v0:clean-check` tag after verification; the pre-existing `swcub-v0:local` tag remains available.

## OSWorld adapter API audit

- Checked the adapter against the official OSWorld `DesktopEnv` source. Its `reset(task_config, seed, options)` result shape, four-value `step(action, pause)` result, `close()`, and `evaluate(eval_logger)` call were reviewed against upstream. The adapter previously omitted the required evaluator logger; it now passes one and supports zero-argument evaluator wrappers by inspecting the callable signature. GUI action pause now matches OSWorld's two-second default.
- `ActorContext` emits generic `type` / `key` / `submit` operation records; the OSWorld adapter now translates those to PyAutoGUI command strings and records both source and dispatched actions. Window focus requires an injected application-specific translator because there is no generic window locator in the adapter.
- Added five explicitly stub-only adapter tests for reset/step, text/key/submit translation, focus translator injection, evaluator logger forwarding, CLI callback injection, no-argument wrappers and close. These are interface checks and are not OSWorld VM/provider evidence.
- Latest full suite: 21 passed, 0 failed, 0 skipped in 27.56 s. Actual `desktop_env` installation, VM startup, guest CLI reachability and task evaluation remain unverified; the provider setup requires OSWorld-specific VM assets not present on this host.

## Machine-readable task catalog

- Added `tasks/v0_manifest.json` with CSV-001 and FOCUS-001 environment starts, actor-role/ID mappings, independent goals, joint final-state predicates, deterministic success/failure schedules, and test/smoke evidence names.
- Added structural validation in `swcub.task_manifest` and `scripts/validate_task_manifest.py`. The validator rejects missing independent goals, invalid actor mappings, incomplete joint schedules, absent final states, and tasks without both passing and failing interactions.
- Six manifest tests and the CLI validator passed. The validator also checks that every referenced actor class, test function, and smoke script exists in the repository. Latest full suite: 27 passed, 0 failed, 0 skipped in 27.29 s, including the real Docker tests; simulator and stub-only results remain separately identified.

## GUI actor visual observations

- The Docker adapter previously returned only screenshot metadata to actors despite capturing a real XWD artifact. It now returns the actual XWD bytes, format, 1024×768 dimensions, byte count and SHA-256 to `ActorContext.observe()`; event JSONL retains only metadata/hash, and the artifact remains separately stored.
- Updated the real GUI-only test to assert the actor received the same bytes as the retained screenshot artifact and that its event includes the matching hash without embedding image bytes.
- Latest full suite: 27 passed, 0 failed, 0 skipped in 27.37 s. This enables visual-capable actors to consume desktop observations; it does not mean a model actor has been connected.

## CSV stale-observation schedule

- Converted `ScriptedGUIActor` into two scheduled steps so it observes the real XWD screen and retains that observation, yields to the CLI append, then submits on a later turn. Both success and stale-write conflict cases now use GUI observe → CLI append → GUI submit; the repeatability permutation also checks CLI append → GUI observe → GUI submit.
- The normal Tk mode rereads the shared CSV on submit, preserving CLI and GUI rows after the intervening update. The negative control uses the reset-time snapshot and loses C1; the evaluator rejects it. The real joint integration test checks the observation event precedes the CLI write, which precedes the GUI type action.
- Reran smoke: 7/7. Reran 20 fresh-container episodes: both CSV orders passed 5/5 with the same final-state hash; focus recovery passed 5/5; stale-focus failure was detected 5/5. Latest medians: 1.013 s, 1.008 s, 2.039 s, and 1.598 s respectively (reset/build excluded). After adding schedule-description consistency checks to the manifest validator, the latest full suite passed 28/28 in 27.51 s.


## Observation revision tracking

- The orchestrator now keeps one actor context across its scheduled turns. An observation records the workspace revision, and later actions by that actor retain the revision they actually observed. Docker revision advances on committed shared CSV/application-state changes; event details include current revision before/after actions.
- The joint GUI+CLI integration trace proves GUI observation at revision 0, intervening CLI write 0→1, GUI typing from the stale observation at revision 0, and GUI Return commit 1→2. This is an explicit stale-observation trace while the normal shared-file reread policy preserves both required rows.
- OSWorld adapter calls also carry the actor's observed revision into GUI/CLI event records. Adapter wiring remains stub-tested; real OSWorld VM execution remains unverified.
- Revalidated from the updated tree: `python -m pytest -q --junitxml=outputs/test-results/junit.xml` passed 28/28 in 27.19 s; `python scripts/smoke_real_workspace.py` passed 7/7; `python scripts/repeatability_study.py 5` passed all 20 expected outcomes with one final-state hash per policy. Median times (reset/build excluded): CSV GUI→CLI 0.999 s, CSV CLI→GUI 0.992 s, focus recovery 2.038 s, stale-focus control 1.610 s.
- All 32 archived JSONL logs (409 events) parse under schema V1. Manifest validation and `git diff --check` passed.
- Clean-commit checkout verification: created a detached temporary worktree at `a53ebb0`, ran the full suite (28/28 in 27.08 s) and `python scripts/smoke_real_workspace.py --skip-build` (7/7). The smoke used the already-built pinned local image. Removed the temporary worktree; no episode containers or `/tmp/swcub-episode-*` directories remained.

## OSWorld V2.1 real application episodes (2026-09-27)

- Confirmed LibreOffice 7.3.7.2, Firefox, and Chrome are available in the pinned Guest. Added repeatable Writer/Calc and Guest-local browser runners; each episode uses one Guest desktop and shared Guest application state.
- Writer and Calc actors independently saved an ODT document and ODS spreadsheet. Solo goals passed, as did sequential and focus-aware schedules. Naive interleaving reproducibly typed Writer's approval into Calc B2, left Writer unsaved, and was rejected by the exact ODF evaluator. Coordinate/focus failures are retained beside the successful artifacts.
- Browser GUI and CLI actors have independent fields backed by a Guest-local JSON app. The refresh schedule preserved both updates. The stale-cache control lost the CLI update and was rejected by the exact backend-state evaluator. GUI and CLI solo goals passed in separate Guest runs.
- Human Replay has an independent browser review goal. Its solo goal and the GUI+Human focus-aware schedule passed. Naive interleaving lost the GUI Agent field and was rejected. This is deterministic scripted replay, not a live user study.
- Added TaskInstanceSpec schema v1 with independent actor goals, initial state, triggered turns, reset/initializer contract, and result aggregation. Browser setup is initialized through the spec. The summary includes only completed episodes with a successful reset and labels mixed policies as descriptive.
- Fixed two real-run issues: GUI actors now receive a fresh post-launch screenshot instead of the cached reset image; CLI-only mutations mark `DesktopEnv.is_environment_used`, allowing snapshot reset. The successful CLI solo run confirmed a new Guest ID and absent task state after reset.
- Latest automated suite: 40 passed, 0 failed, 0 skipped. Full per-condition outcomes and artifact paths are recorded in `TEST_RESULTS.md`; commands are in `README.md`.
- No model actor, training, bulk data generation, GPU job, or official scored OSWorld task was run. The local pinned QEMU runtime fallback remains in use. Results show scripted real-app feasibility on this Guest only.
- Ran one additional fresh-Guest repeat for each positive paired schedule: Writer/Calc focus-aware, browser GUI+CLI refresh/merge, and browser GUI+Human focus-aware. Each repeat independently passed both actor goals and its clean-reset check. Individual artifacts are in the corresponding `*-repeat-02/` directories. Negative controls remain one reproduced run each; sample sizes support smoke-level repeatability only.
- Moved the Office and browser run artifacts (screenshots, event traces, and episode reports) to `/mnt/raid1/mjh/Projects/Shared-Workspace-Benchmark-V0/outputs/osworld-v2.1/` per the workspace storage preference. The repository's `outputs/osworld-v2.1/{office,browser}` paths are local symlinks to those RAID1 directories; both paths were re-read and the report aggregation was rerun after transfer.

## OSWorld agent framework integration (2026-09-27)

- Reviewed OSWorld's canonical pipeline and local V2.1 implementations plus CogAgent, UFO/UFO², SeeAct, Anthropic Computer Use, and OpenAI Computer Use/Operator. Details, source links, interface boundaries, and adapter sequence are in `AGENT_FRAMEWORK_REVIEW.md`.
- **Baseline distinction:** the original OSWorld repository documents its paper baseline as GPT-4o with pure screenshots. Because hosted paid inference remains out of scope, this experiment uses the pinned V2.1 first-party `Qwen3VLAgent` with an existing local Qwen3-VL-30B-A3B checkpoint. This is an OSWorld-native local variant, not the original GPT-4o baseline or a leaderboard submission.
- Removed the custom `LocalQwenGUIActor` and its project-defined JSON action schema. The only new agent-side interfaces are a role-checked native PyAutoGUI action forwarder in `ActorContext`, a thin `OSWorldAgentActor` that calls OSWorld's `reset/predict` API, and a loopback local inference transport. Prompt construction, image history, computer-use schema, parser, relative-coordinate mapping, and action strings come from the pinned OSWorld source.
- First real Writer solo attempt **failed**: the model omitted a body click, and the independent evaluator found the original text unchanged; Calc stayed unchanged and reset passed. A second attempt with an explicit click/focus task instruction **passed**: five model predictions clicked the paragraph, selected/replaced its text, saved, and terminated. The Guest evaluator found exact Writer text `Approved by GUI actor`, intact Calc cells, and a clean reset/new Guest. The success artifact directory is `outputs/osworld-v2.1/office/writer-osworld-agent-solo-explicit-click/`.
- Entered the first same-Guest Writer-agent + scripted-Calc sequential condition after the solo pass. This **failed as a paired episode**: the model repeated Ctrl+A/Ctrl+V to the 20-step bound; Orchestrator stopped before Calc received a scheduled turn. Exact evaluation found both goals missing, while reset passed. It is a model-task failure; no shared-interference conclusion follows. Full trace is under `outputs/osworld-v2.1/office/writer-agent-calc-scripted-sequential/`.
- All three episode event logs validate under schema V1 (25, 25, 71 events). Corrected report attribution labels the bounded Ctrl+A/Ctrl+V loop as a model task failure rather than an action-execution failure. Existing regression suite after the sequential scenario addition: 40 passed in 31.02s. Python compilation, runner help under the pinned OSWorld UV project, shell syntax, and `git diff --check` pass.
- The local 30B checkpoint was already present on RAID1; the model worker used local-only Transformers with Hub/offline flags and bound only to `127.0.0.1`. No paid API, model download, or training was used. First weight load took 7m25s; a subsequent cached load took 28s. The model trace and actual Guest screenshots are preserved per episode.

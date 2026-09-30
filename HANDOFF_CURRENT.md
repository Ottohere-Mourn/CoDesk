# CoDesk Current Handoff

**State snapshot:** 2026-09-30, A6000. Evidence labels used below: **VERIFIED** = checked against a run artifact, source, or Git state; **SCRIPTED ONLY** = real app/Guest with scripted actors; **OFFLINE ONLY** = unit/schema/artifact checks without a live Guest; **DESIGN ONLY** = specification without a validated executable run; **INVALID / SUPERSEDED** = retained history that cannot support the stated inference.

## 1. Project Goal

CoDesk (Collaborative Desktop Use Benchmark) asks: **what additional task failures and recovery costs arise when independently goal-directed Computer-Use Agents share a live, non-exclusive desktop session?** (**VERIFIED protocol:** [`CODESK_PROTOCOL_V1.md`](CODESK_PROTOCOL_V1.md), [`PROJECT_POSITIONING.md`](PROJECT_POSITIONING.md)).

- An Actor is an independent action-producing entity with its own goal, identity, observation/action history, budget, and execution state. Human Replay is a distinct actor composition; scripted actors validate task mechanics but are not model-agent evidence.
- **Solo:** each actor's goal is run from the same clean task fixture without partner actions. Every actor must pass its own Solo goal before interpreting a shared-condition failure.
- **MA-ID:** multiple actors use separate live desktop/input sessions. Any files or application backend relevant to the task are held the same as MA-SD.
- **MA-SD:** actors share one live Guest desktop session, including focus, keyboard, pointer, windows, and session clipboard.
- Shared desktop and shared backend are different axes. A MA-ID private-backend vs MA-SD shared-backend contrast changes two variables and cannot establish a desktop-sharing effect.

## 2. Experimental Causal Contract

For matched MA-ID/MA-SD comparisons, hold task instance and initial state, Actor-goal mapping, model/Agent and prompt, action budget, schedule, trigger, app version, authoritative backend, evaluator, and reset rule fixed. The intended treatment is desktop-session topology alone. If the same backend cannot be kept under both conditions, report a factorial design or stop the causal comparison; never use the diagonal private-vs-shared backend comparison as the desktop effect. (**VERIFIED:** [`CODESK_PROTOCOL_V1.md`](CODESK_PROTOCOL_V1.md), [`TASK_REGISTRY_V1.md`](TASK_REGISTRY_V1.md)).

Report these separately:

1. **Exposure:** a measured opportunity/resource change, identified as natural or scheduled-stress.
2. **Observed interference:** trace plus state evidence that a partner action altered the other Actor's input/resource/state.
3. **Task outcome:** per-Actor success, joint success, and integrity from the programmatic evaluator.
4. **Recovery:** observable post-conflict recovery actions and whether exact joint success was restored.

A scheduled opportunity is not automatically exposure; exposure is not task failure; temporal order alone is not causation. Actors retain autonomous observation and recovery. Evaluator reads hidden authoritative state only after actors stop; never use an LLM judge as the success oracle.

## 3. Mechanism Taxonomy

1. **Focus / input routing — Core, prior mechanism validated with scripted/Human Replay composition; model GUI+GUI comparison not yet established.** Shared window focus, keyboard, and pointer can route a valid action to the wrong application.
2. **Clipboard / session resource ownership — Extension, design and offline implementation only.** Selection owner/payload changes may affect paste while focus remains correct. Observer-on/off perturbation and real target evidence are still required.
3. **Window / modal competition — Extension/design only.** Competing windows or Save/format dialogs can redirect or block otherwise valid actions. No real dialog-owner evidence yet.
4. **Application internal context — Candidate/design prototype only.** Example is two tabs in one Browser window: X11 window focus unchanged while active page/tab changes. No joined live X11/page-context trace yet.

GUI+CLI stale backend/revision consistency is an **auxiliary shared-state control**, not the core shared-desktop mechanism.

## 4. Current Task / Benchmark Status

| Evidence state | What exists | Boundary |
|---|---|---|
| **VERIFIED, real Guest, scripted** | Writer+Calc task `CODESK-TA-OFFICE-001` v1.0.0 on OSWorld V2.1; the A6000 paired Solo migration smoke passed both exact goals once. Historical 15-episode set has separate scripted Solo/MA-ID/MA-SD records. | Historical MA-ID used separate workspaces/backends; do not claim it isolates desktop topology. A6000 run is a scripted environment acceptance, not a model result. |
| **VERIFIED, real Guest, GUI+Human Replay** | Focus routing anchor `SWCUB-FOCUS-ROUTING-001` v2.0.0. | Actor composition is GUI+Human Replay; not two GUI Agents. |
| **VERIFIED, real Guest, GUI+CLI** | Stale merge anchor `SWCUB-STALE-MERGE-001` v2.0.0. | Auxiliary shared-backend mechanism. It is not a desktop-sharing-only contrast. |
| **SCRIPTED ONLY / previous topology caveat** | Writer+Calc scripted repeat reports include paired Solo 5/5, MA-ID 5/5, and expected MA-SD focus interference in a separate 5-run repeat set. | These runs used legacy topology with distinct MA-ID workspaces; do not use as matched shared-backend causal evidence. See [`REAL_APP_TRACK_A_RESULTS.md`](REAL_APP_TRACK_A_RESULTS.md). |
| **OFFLINE ONLY / unvalidated live** | Clipboard observer/tracker, task registry, Modal Save-dialog fixture, Browser two-tab fixture, Task Factory manifests/oracles. | No Guest proof for clipboard non-perturbation, Modal ownership, or Application Context attribution. See [`PROTOTYPE_STATUS_V1.md`](PROTOTYPE_STATUS_V1.md). |
| **OFFLINE ONLY** | Same-workspace backend topology helpers/configs and offline tests. MA-ID intends two Guests/sessions with one backend; MA-SD one Guest/session with that backend. | QEMU 9p visibility, persistence, and reset under this topology have not been Guest-validated. |
| **VERIFIED model failures, service-invalid** | A6000 Qwen attempts `...-r01` and `...-r02` below. | Real Guest and model load were reached, but 0 model actions; both are `model_service_failure`, excluded from Agent task-success scoring. Not a Qwen task failure and not PASS. |

Task hierarchy is **family → workflow template → fixed task instance → run config**. The historical factory registered 2 templates across 2 families, saved 8 Writer+Calc candidate instances, and dry-ran 250 IDs/fingerprints. The 8 office instances are content/target variations of **one actual Writer+Calc workflow template**, not 8 workflows; 250 IDs are not 250 workflow designs. New office candidates have zero Guest validations. (**VERIFIED:** [`TASK_FACTORY_V1_REPORT.md`](TASK_FACTORY_V1_REPORT.md)).

## 5. Important Historical Results

- **Scripted Writer+Calc:** the fixed office task and exact saved ODF evaluator work on real Guest. The frozen 15-run report has paired Solo actor goals 5/5; MA-ID 4/5 in its formal table and 5/5 in a separate readiness-stable repeat set; MA-SD focus trigger 4/5 formal and 5/5 in a separate repeat set. All these are engineering/scripted results on a single task, not statistics. Legacy MA-ID backend topology is confounded, and MA-SD fixture results do not establish natural-model failure. Raw artifacts are under `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/` on the prior environment; see [`REAL_APP_TRACK_A_RESULTS.md`](REAL_APP_TRACK_A_RESULTS.md).
- **Qwen solo history:** [`BASELINE_CALIBRATION.md`](BASELINE_CALIBRATION.md) records 15 real Guest runs across Browser/Writer/Calc: Browser 5/5, Writer 2/5, Calc 0/5; the stability gate failed. A separate 2026-09-29 paired Writer+Calc Solo smoke completed each goal in 5 actions with real screenshot-conditioned Qwen3VLAgent output; its original provenance was post-hoc reconciled, so it is one-time smoke evidence, not a clean formal baseline. See [`MODEL_SOLO_SMOKE_RESULTS.md`](MODEL_SOLO_SMOKE_RESULTS.md).
- **Prior dual-model report:** [`REAL_DUAL_AGENT_EVAL_REPORT.md`](REAL_DUAL_AGENT_EVAL_REPORT.md) lists two Solo attempts, both service/runner-invalid, and zero MA-ID/MA-SD attempts. No valid model shared comparison exists.
- **Parallel runner:** two-worker pilot showed throughput improvement but accessibility-tree HTTP 500 affected attribution; bounded follow-up and retry changes are documented in [`PARALLEL_PILOT_REPORT.md`](PARALLEL_PILOT_REPORT.md), [`PARALLEL_STABILITY_REPORT.md`](PARALLEL_STABILITY_REPORT.md). Keep episode parallelism separate from within-episode actor scheduling.
- **Clipboard:** the observer requests X11 selection conversion, which may perturb timing. Code tracks sample duration but does not prove non-perturbation. No observer-on/off Guest validation. See [`CLIPBOARD_001_STATUS.md`](CLIPBOARD_001_STATUS.md).
- **A6000 scripted acceptance:** run `a6000-wc-solo-smoke-retry-01` passed Writer+Calc exact goals, readiness, persistence, reset, provenance, and artifact integrity 1/1 in 615.487 seconds. It used the already present `:local` runtime. This confirms the migrated Guest/app path only.
- **Current A6000 model smoke:** `r01` and `r02` both load Qwen3-VL locally and pass Guest readiness but time out before the first Agent decision (240 s and 600 s). Details and evidence are in [`A6000_QWEN_SMOKE_RESULTS.md`](A6000_QWEN_SMOKE_RESULTS.md). Current state is **BLOCKED**, not PASS.

## 6. Repository / Infrastructure State

- A6000 host: `admin123-Super-Server`, account `mjh`; project clone: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`; branch `v0`. The migration checkpoint before this handoff work was `f38b2e9` (9 commits ahead of `origin/v0`); handoff/model-timeout changes are part of the checkpoint being created now. Do not push.
- Key project areas: `swcub/` task/actor/environment/evaluator/registry; `tasks/` task definitions and manifests; `configs/` runner configs; `scripts/` OSWorld runners, setup, checks, factory and local model worker; `tests/` offline and Guest tests; `outputs/` pinned manifests; `external/` and model/assets are outside Git.
- OSWorld V2.1 external checkout: `/home1/mjh/Projects/CoDesk-V0-A6000/external/OSWorld-V2-osworld-v2.1`, commit `3d778a3c9a34a079316f70df023b166700445792`, with modified Docker provider patch separately preserved at `/home1/mjh/Projects/CoDesk-V0-A6000/snapshots/OSWorld-V2-osworld-v2.1-provider.patch`. This external patch is required for run labels, QEMU overlay bind, and optional shared workspace bind; it is not a clean Git checkout.
- Guest QCOW: `/home1/mjh/Projects/CoDesk-V0-A6000/assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2`; runtime: `swcub/osworld-v2.1-qemu-runtime:a6000`, image ID in the A6000 smoke report. Docker/KVM checks now pass for `mjh` (groups `docker,kvm`); `scripts/a6000_environment_check.sh` is the read-only preflight. Normal ephemeral run-owned containers are closed by runner and checked against `resource-events.jsonl`.
- OSWorld Python: `/home1/mjh/Projects/CoDesk-V0-A6000/envs/osworld-v2.1/bin/python` (Python 3.12.3). Model Python: `/home1/mjh/Projects/CoDesk-V0-A6000/envs/qwen/bin/python` (PyTorch 2.7.0+cu128, Transformers 5.5.0.dev0, Accelerate 1.11.0 as observed). Model weights: `/home1/mjh/Projects/CoDesk-V0-A6000/models/Qwen/Qwen3-VL-30B-A3B-Instruct`, 13 shards; target checksum verification previously passed.
- Model runtime: prior successful 4090 smoke used the local checkpoint on 4090 with per-call latency reported 6.1–35.3 s. The two current A6000 attempts ran inference on A6000 itself, loopback on port 54485 / 43721, with `CUDA_VISIBLE_DEVICES=0,2`; physical GPU 1 had an unrelated 39.8 GiB allocation and was not used or inspected further. Do not assume the 4090 service endpoint is configured here; discover only an explicitly owned/authorized endpoint before using it.
- A6000 current Qwen artifacts: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/{a6000-qwen-writer-calc-solo-20260930-r01,a6000-qwen-writer-calc-solo-20260930-r02}/`; console/preflight logs: `/home1/mjh/Projects/CoDesk-V0-A6000/snapshots/a6000-validation/`. The Writer/Calc scripted smoke is under `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/writer-calc-v1/a6000-wc-solo-smoke-retry-01/`.
- The run wrapper now uses `CODESK_PYTHON` to avoid `uv` network build isolation and prioritizes `SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE`. Qwen HTTP deadline was changed from 240 to 600 seconds in `scripts/run_writer_calc_v1.py`; this is an infra-only working-tree change, not yet part of the preceding `f38b2e9` commit. Offline tests after this edit passed 117/117; both Qwen reports have 46/46 artifact hashes matching.
- No Qwen inference process or CoDesk Guest should remain after the run; check `docker ps` by the exact project label and GPU snapshot before another run. Do not assume no other workload just because CoDesk is idle.

## 7. Resource / Safety Rules

- Never run Docker global prune or wildcard/bulk stop/remove. Never delete unknown containers, images, volumes, directories, overlays, checkpoints, or artifacts.
- Cleanup is allowed only for resources created by the current CoDesk run, after checking the full immutable ID, project/run/owner labels, and exact matching `resource-events.jsonl` ledger entry. Never clean by image name/tag or prefix.
- Do not inspect, stop, modify, or delete other users' processes/resources or other projects' resources. Do not modify host-wide permissions, system Python, CUDA driver, SSH configuration, or global Docker setup.
- Preserve every attempt and artifact; new runs need new unique run IDs/directories. Reset success does not turn a task miss or timeout into a success.
- A prior unrelated-container deletion incident is why these checks are permanent; verify ownership every time even if a container looks familiar.

## 8. Research Priorities

- **P0:** complete one valid real Qwen3VLAgent loop on A6000 Guest. The present block is first-response latency, not setup. Compare the known-successful 4090 inference path before further modifying A6000 serving. Require at least one returned model response, native Agent action, Guest action submission, exact evaluator, provenance, and reset.
- **P1:** validate Focus / Clipboard / Modal / Application Context task paths on live Guest; Clipboard requires observer-on/off non-perturbation. Keep these at one mechanism each and mark unsupported instrumentation unknown.
- **P2:** only after each Actor passes Solo, run genuine two-Actor Solo/MA-ID/MA-SD matched minimal pilots with identical backend topology, schedule, budget, goals, and evaluator.
- **P3:** retain, merge, or reject mechanisms based on evidence, separating exposure, interference, task outcome, and recovery.
- **P4:** expand only genuinely different workflow templates.
- **P5:** only after templates validate, create roughly 200–300 fixed instances and perform batch multi-model evaluation. Seed count/unique IDs alone are not diversity.

## 9. Immediate Next Actions

1. **Inspect the two failed Qwen artifacts, not the task answer.** Confirm `model_worker.log`, saved screenshot, `messages_step_0.json`, report error, `model_turn_elapsed_ms` (240.353 s / 600.256 s), empty `model_trace.jsonl`, and preserved ownership/reset. Success: facts match [`A6000_QWEN_SMOKE_RESULTS.md`](A6000_QWEN_SMOKE_RESULTS.md); otherwise correct this handoff from the artifacts.
2. **Compare with the preserved 2026-09-29 successful paired Solo run.** Read its model metadata, prompt hashes, inference host/framework and response traces. Success: identify a concrete working inference endpoint/runtime. If no reachable/authorized service exists, record that fact; do not guess ports or inspect other users' project files.
3. **Check resource permission immediately before any model attempt.** Confirm no CoDesk run/Guest remains, check GPU free memory and host pressure; use only explicitly free devices. If capacity changed, stop without reclaiming another user's GPU.
4. **Choose one inference route:** use the verified 4090 service via an approved reachable endpoint if its historical harness is still up; otherwise diagnose why the A6000 local worker takes >600 s per first screenshot. Do not just keep increasing timeout. Keep the same Qwen checkpoint, Qwen3VLAgent, prompt, parser, task, 512-token limit and evaluator.
5. **Run exactly one fresh paired-Solo smoke under a new run ID.** Do not reuse r01/r02. Success: at least one actor has saved screenshot → raw Qwen response → native action → GUI action, while task setup, exact evaluator, provenance, reset and resource lifecycle are complete. Both actors must pass Solo before shared experiments.
6. **Classify and write the result.** Model service timeout is infra-invalid; a returned action that is wrong is Agent/task failure; a Guest readiness/transport error is environment-invalid. Preserve all attempts and do not pool invalid runs.
7. **Only on P0 pass, proceed to one live Clipboard/Focus feasibility task or paired model comparison.** Maintain same backend between MA-ID and MA-SD and keep exposure/interference/outcome/recovery separate.

## 10. Things NOT To Do

- Do not redesign CoDesk from scratch or rewrite OSWorld's planner/grounding/action parser.
- Do not call the scripted A6000 smoke a model PASS; do not call timeout attempts model task failures.
- Do not compare legacy different-backend MA-ID against MA-SD as a desktop causal effect.
- Do not use small-model failures, scripted negative controls, timing adjacency, or unique task IDs alone to claim interference or diversity.
- Do not change task goal, prompt, model, token budget, evaluator, or inject a correct/forced action to get a success.
- Do not promote Clipboard/Modal/App Context without the specified real instrumentation and reset evidence.
- Do not expand seed counts, start multi-worker runs, or launch shared conditions before P0 and both Solo gates pass.
- Do not perform unowned cleanup, touch other users' resources, or push to a remote.

# A6000 Qwen3VLAgent Solo Smoke — 2026-09-30

## Decision

**BLOCKED:** the A6000 Guest and local Qwen model worker both started, but the first Qwen3VLAgent request did not return before the bounded HTTP deadline. The Agent submitted **zero GUI actions**. This is a model-service latency/response failure, not a valid task-capability failure and not a shared-desktop result.

## Fixed path and task

- Guest and inference host: `admin123-Super-Server` (A6000).
- OSWorld: V2.1 checkout `3d778a3c9a34a079316f70df023b166700445792`, Docker runtime `swcub/osworld-v2.1-qemu-runtime:a6000`, image `sha256:8e4d74c1fbec619992e1c4b8c80d9fa613d5d2af4d0e443d2e43da3bcba03dc7`.
- Model: local, offline `Qwen3-VL-30B-A3B-Instruct`; config SHA-256 `6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912`.
- Agent: pinned OSWorld `mm_agents/qwen3vl_agent.py::Qwen3VLAgent`; model transport is loopback `scripts/local_qwen_worker.py`. No planner, prompt, action parser, task, or evaluator change.
- Existing task: `CODESK-TA-OFFICE-001` v1.0.0, paired Solo control (Writer and Calc each on a separate Guest), 20 Agent steps per actor, deterministic generation, 512-token limit.
- CUDA visibility: physical GPUs 0 and 2 only. GPU 1 had an unrelated active allocation and was not used or inspected further.

## Attempts (append-only)

| Run ID | HTTP deadline | Actor result | Guest/evaluator/reset/provenance | Episode wall time |
|---|---:|---|---|---:|
| `a6000-qwen-writer-calc-solo-20260930-r01` | 240 s | Writer request timed out at 240.353 s; 0 Agent steps, 0 GUI actions; Calc did not run | Both app setups ready; unchanged initial ODF state; reset 2/2; provenance complete; 46/46 provenance artifact hashes match; all 4 run-owned containers destroyed | 948.878 s |
| `a6000-qwen-writer-calc-solo-20260930-r02` | 600 s | Writer request timed out at 600.256 s; 0 Agent steps, 0 GUI actions; Calc did not run | Both app setups ready; unchanged initial ODF state; reset 2/2; provenance complete; 46/46 provenance artifact hashes match; all 4 run-owned containers destroyed | 1091.045 s |

For both runs the evaluator correctly found Writer and Calc goals unmet with no contamination. Reports mark `episode_validity.valid_for_agent_success_rate=false` and `model_failure_class=model_service_failure`; neither attempt belongs in the Agent task-success denominator. `model_trace.jsonl` is empty because `Qwen3VLAgent.predict()` did not return. Each screenshot and full prompt message cache is preserved.

## Exact evidence paths

- R01: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/a6000-qwen-writer-calc-solo-20260930-r01/`
- R02: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/a6000-qwen-writer-calc-solo-20260930-r02/`
- Console logs and preflight: `/home1/mjh/Projects/CoDesk-V0-A6000/snapshots/a6000-validation/`
- R02 starts with `setup-validation/{writer,calc}-window-ready.png`, accessibility trees, input probes and no-op-save persistence screenshots. `model-actors/writer_actor/observations/step-001.png` and `draft/message_cache/messages_step_0.json` prove a real Guest screenshot and the unmodified Agent prompt reached the model path.
- `model_worker.log` records local model load and `/health` ready on loopback. Transformers warned that temperature/top-p/top-k generation flags may be ignored; the existing worker uses deterministic `do_sample=False`. No response/action was received before timeout.

## Classification and next diagnostic

Environment checks, both Guest app readiness checks, local model loading, model health, hidden-state evaluation, reset, provenance, ownership lifecycle, and artifacts all worked. The single demonstrated blocker is first-request latency: the A6000 Transformers service failed to return one response within even 600 seconds. No task, prompt, evaluator, step budget, token limit, or action parser was relaxed. Do not extend the deadline repeatedly without new evidence. Compare this path with the preserved 2026-09-29 successful 4090 paired-Solo smoke (reported per-call inference 6.1–35.3 s) and prefer its already working inference host/service if it is still available. Any new attempt needs a new run ID.


## 2026-09-30 GPU allocation and instrumented retry

A third A6000 card (`nvidia-smi` index 2) was free, but one 48 GiB card cannot hold the 58 GiB BF16 checkpoint. The instrumented Qwen retry therefore used the two free cards, physical indices 0 and 2 (CUDA-visible logical devices 0 and 1); the occupied physical index 1 was excluded.

- `a6000-qwen-writer-calc-solo-20260930-r03-stage-timing` was **environment-invalid**. The direct invocation omitted `scripts/a6000_env.sh`, so OSWorld mounted `_deps/OSWorld-V2-osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2`, which on this host is a directory. The actual 14.9 GB Guest image is `assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2`. QEMU failed before model startup; the run-owned container was destroyed by the runner. No model/task outcome is inferred.
- `a6000-qwen-writer-calc-solo-20260930-r04-stage-timing` sourced `scripts/a6000_env.sh`; both real Guests passed Writer/Calc readiness. Qwen3VLAgent sent a real screenshot request (200,443-byte payload, one image, 2,254 input tokens). Image decoding, chat-template/render preparation, and tensor preparation took 0.032 s, 0.055 s, and 0.089 s. `model.generate()` did not return within the unchanged 600 s client deadline; Agent steps/actions were 0, model trace is empty, and the exact evaluator reports both goals unmet. Classify this as `model_service_failure`, not task capability or shared-desktop interference.
- R04 elapsed 1,155.524 s including Guest setup and reset. Reset verified both desktops (2/2); provenance artifact hashes checked 46/46; run-owned containers were stopped/destroyed by the runner.
- New timing-only logging in `scripts/local_qwen_worker.py` records request phases, durations, token counts, and mapped device IDs. It does not log prompt text, screenshots, or model response. Prompt, model weights/config, Qwen3VLAgent, task, and evaluator were unchanged.

Evidence: R03 artifacts at `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/a6000-qwen-writer-calc-solo-20260930-r03-stage-timing/`; R04 at `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/a6000-qwen-writer-calc-solo-20260930-r04-stage-timing/`; startup logs under `snapshots/a6000-validation/`. Always source `scripts/a6000_env.sh` before starting the A6000 runner and set `CODESK_CUDA_VISIBLE_DEVICES=0,2` only after confirming those GPUs are free.


## vLLM alternate-serving feasibility probe

- Upstream vLLM currently lists `Qwen3VLMoeForConditionalGeneration` / `Qwen3-VL-30B-A3B-Instruct` as supported, but explicitly notes Qwen-VL image preprocessing differs from the Hugging Face path. Treat a vLLM trial as a separately recorded serving variant, not as an identical inference-runtime comparison.
- A6000 driver reports CUDA 13.0; Python 3.12 and glibc 2.39 satisfy the current documented platform bounds. An isolated empty environment was created at `/home1/mjh/Projects/CoDesk-V0-A6000/envs/vllm-qwen-0.30.0`; no vLLM package was installed.
- Official vLLM 0.30.0 cu129 GitHub wheel request returned HTTP 403. A bounded 180-second PyPI dependency dry-run reached the PyTorch cu129 index but timed out reading it. Logs: `snapshots/a6000-validation/vllm-qwen-0.30.0-install.log` and `snapshots/a6000-validation/vllm-pypi-dry-run.log`. No GPU was used and the existing Qwen environment was not modified.
- Next serving investigation must use an accessible, pinned official wheel source or improve the existing Transformers generation path; do not switch the benchmark’s model/agent/prompt/evaluator or mislabel a vLLM result as fixed-backend baseline.

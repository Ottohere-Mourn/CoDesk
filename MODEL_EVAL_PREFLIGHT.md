# CoDesk Writer + Calc model evaluation preflight

## Current audit disposition (2026-09-29)

The artifact described below under run ID `codesk-real-v1-qwen-solo-r01-20260929` is present and internally consistent, but it came from a separately launched run while this checkout and shared OSWorld host were being used concurrently. Its report records a complete provenance manifest, 10 Qwen decisions, exact Writer/Calc goal states, and a successful reset. Because the run's source revision at process start cannot be established and it was not isolated under this evaluation's ownership ledger, it is **not counted** toward P1's three new controlled Solo repeats or as controlled P0 verification.

This turn's attempt `dualqwen-solo-r01b-20260929` did not reach model startup: the localhost:5000 screenshot service timed out during Writer readiness while other run IDs had QEMU Guests forwarding the same host ports. It is retained as an environment-invalid attempt with screenshots and a complete resource ledger; it is not a model failure. An earlier explicit management abort is retained separately. Thus this evaluation has **0/3 accepted new P1 Solo repeats** and has not entered MA-ID or MA-SD. The independent-run artifact below is descriptive evidence only pending a clean, exclusive reproduction.

## Status

P0 preflight passed on a new real OSWorld V2.1 episode. Task ID/version remain `CODESK-TA-OFFICE-001` / `1.0.0`; model and `GuestLibreOfficeBindingEvaluator` scoring rules were not changed. The episode also counts as Solo stability repeat 1 for each actor.

## Separately launched artifact (not accepted as a controlled repeat)

The artifact reports completion through the normal runner path and includes `provenance.json`. Its report has `provenance_status=complete`, both actor goals passed, reset passed, and the ownership ledger has matching create/destroy entries for all four task/reset Guests. Provenance covers 84 saved artifacts; all 84 SHA-256 values were recomputed and matched. This validates the artifact's internal consistency, but the run is excluded from controlled success denominators for the reason above.

Episode root:

`/mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/real-dual-agent-eval-v1/codesk-real-v1-qwen-solo-r01-20260929/`

The prior Qwen smoke at `qwen-solo-retry-20260929` remains unchanged. Its exact final states and 10 observed Qwen tool calls support that it was model-driven, but its run process returned nonzero during provenance finalization; its provenance is therefore post-hoc and is not used as a formal trial.

## Action trace and fallback audit

The new trace is `model_trace.jsonl` (10 model decisions, five per actor) and is ordered by event sequence. It records the screenshot hash/path, the raw OSWorld response, parsed native GUI actions, model latency, and observed Guest revision. `final-odf/` contains both saved documents from each Solo Guest; the hidden evaluator passed Writer text and Calc B2 exactly, with no non-goal mutation.

The only Qwen branch constructs one `Qwen3VLAgent` object per actor and dispatches both through `OSWorldAgentActor.run_step`. It does not construct either scripted actor. `report.json` records `scripted_fallback=false`; `model_worker.log` and provenance identify the local checkpoint and the single inference process. Thus the task changes came from the official Qwen image-conditioned `predict()` path and its parsed PyAutoGUI calls, not from prefilled file state or evaluator writes.

The older official agent writes debug messages to a working-directory-relative `draft/message_cache/messages_step_N.json`. The earlier Solo smoke ran both agent objects from the shared repository working directory, so these debug messages could collide by step number; that old cache is not treated as canonical evidence. The current adapter runs each official `predict()` call with a per-actor working directory under the unique episode root and saves each input screenshot separately. This preserves the standard planner/parser while isolating diagnostic artifacts.

## Setup, model and resource isolation

- Writer and Calc readiness checks opened the named `document.fodt` and `table.fods`, verified seeded values, GUI interactivity, Sheet1/B2 navigation, and no-op save persistence.
- The run used two distinct Guest IDs (`writer_desktop`, `calc_desktop`), a unique `run_id`, and a previously nonexistent artifact directory. Both Guests reset to fresh IDs after grading.
- One local Qwen worker served the two separate actor objects over loopback. Each actor has a distinct actor ID, actor instance ID, prompt, Qwen conversation state, screenshot history, action budget and artifact subdirectory. No second model copy was loaded.
- The model worker was shut down before hidden-state evaluation/reset. Actor contexts have no evaluator or file-reader capability.
- Host load was high at launch, so the run used one experiment at a time. It did not start a second worker. MA-ID episodes will allocate exactly two concurrent task Guests; reset replaces each task Guest before starting its reset Guest.

## Frozen model protocol for this phase

- Model: local `Qwen3-VL-30B-A3B-Instruct`, OSWorld V2.1 `Qwen3VLAgent`.
- Agent config: Ubuntu, screenshot observation, PyAutoGUI action space, relative coordinates, `max_tokens=512`, `top_p=0.9`, `temperature=0.0`, history window 4.
- Local generation: one-token cap 512 and deterministic greedy decode (`do_sample=false`); same worker/config for both actors and every episode.
- Actor budget: 20 `predict()` decisions per actor. Each turn observes independently, asks the model once, then submits the returned action list serially. The frozen multi-agent schedule alternates Writer then Calc; completed actors are skipped. Solo also alternates the independent controls.
- The schedule is predeclared and recorded. In r1 each actor completed in five decisions; the trace shows the order Writer-1, Calc-1, Writer-2, Calc-2, …, Writer-5, Calc-5.

## P1–P3 execution gates

P1 requires three valid new paired Solo episodes (each episode contains one Writer-only Guest and one Calc-only Guest). Current controlled count: **0/3 valid**. Startup/readiness/provenance failures are retained and excluded from agent success denominators.

After P1, P2 requires three valid two-Guest MA-ID episodes with both model actors. P3 requires three valid one-Guest MA-SD episodes using the same round-robin schedule, prompts and budgets. The first valid episode in each condition also serves as its integration check. Model shared conditions have not yet run.

## Resource boundary

The experiment is being run serially with one inference worker. The only reset/destruction so far was by the OSWorld provider for containers whose full IDs, run ID, project label and owner token appear in this run's ledger. No other project's or user's resources were modified; no prune command was used.

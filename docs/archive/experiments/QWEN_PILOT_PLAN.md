# CoDesk Qwen Pilot Plan

Status: **design only; no Qwen episode was run in this phase.** Use the already installed OSWorld Qwen3VLAgent and the existing Qwen3-VL-30B-A3B inference service. The plan does not introduce a model adapter or alter prompts, evaluator, tasks, action budget or decoding.

## Research question

Do the scripted exposure signatures in one representative workflow per family also occur when an autonomous computer-use agent can observe, replan, switch target and recover?

The pilot checks transfer of a mechanism signature. It is not a performance benchmark or a model comparison.

## Fixed representatives

| Family | Template / fixed task | Representative mechanism | Required private evidence |
|---|---|---|---|
| Focus / Input Routing | F-01, CODESK-TA-OFFICE-001 v1.0.0, existing Writer+Calc instance | An actor's pending content action after the other app becomes foreground | active window before/after each action, intended object, actual saved ODF, contamination and refocus |
| Clipboard State | C-01, CODESK-TB-CLIPBOARD-001, pin the task version and fixture hash in preflight | Clipboard payload changes between copy and paste while both GUI goals remain reachable | selection owner, payload digest/generation, copy/paste brackets, target app, exact saved files |
| Application Context | A-01, CODESK-TE-APP-CONTEXT-00000000 v1.0.0-rc4 | Active Browser tab/page changes under one top-level Chrome window | X11 window ID, Chrome target/tab ID and URL, tab events, per-tab goals/revisions |

Use these exact existing task instances. Do not generate new content. If the C-01 task version or fixture hash does not match its archived scripted artifact, stop and resolve the version mapping before the model run.

## Conditions and bounded repeats

For each representative, run:

1. Solo A and Solo B once each on clean Guest resets. Both independent goals must be individually feasible before shared conditions.
2. MA-ID twice with two independent Guests initialized from the exact same task fixture. Keep the actor sequence, model settings and coordinator schedule equal to MA-SD.
3. MA-SD twice with both actors on one shared desktop. Each turn receives a fresh screenshot, while each actor keeps its own goal, prompt, model conversation, action history and budget.
4. Do not add a forced-error or recovery-aware scripted condition. Let Qwen notice, switch, recopy, reselect or recover on its own; annotate those actions from the trace. If the two MA-SD runs disagree, add at most two diagnostic repeats for that representative and report the discrepancy.

Initial maximum: 18 valid episodes (3 tasks × [2 Solo + 2 MA-ID + 2 MA-SD]). Setup, inference or reset failures are retained but excluded from model task denominators and listed as invalid infrastructure episodes. Do not replace failures silently.

## Causal controls

Keep these equal across MA-ID and MA-SD:

- task/template version, fixed instance and byte-level initial fixture;
- Qwen3VLAgent source and commit, model weight/config, inference host, prompt, decoding and action parser;
- actor A/B goals, actor identities, independent conversation/history, per-Actor action budget and coordinator turn sequence;
- evaluator, reset procedure and observation refresh policy.

The intended contrast is desktop control/context sharing. Do not change backend topology or task data at the same time. For A-01 the local Browser server can be independently initialized in MA-ID because its goals do not require cross-Actor persistence; the pages and initial state must match the MA-SD fixture hash.

Do not run two model servers or duplicate model weights. Actor calls may share the existing inference service, but use separate requests and actor histories. Record inference host and Guest host on every run.

## Logging and scoring

Save each observation screenshot, model response, parsed action, execution result, actor identity, timestamp, current turn and active window/tab context. Keep oracle files private to the evaluator.

Per run report:

- actor A goal, actor B goal and joint success;
- scheduled exposure (whether the task schedule creates an opportunity);
- observed mechanism evidence (window/target mismatch, payload overwrite, tab change);
- actual wrong-target or contaminated action, if supported by both action and state evidence;
- recovery attempt and recovery success, distinguishing autonomous from scripted;
- actions and elapsed time per actor, invalid actions, focus transitions, clipboard generations or tab transitions;
- environment/readiness/inference failures, reset, provenance and artifact integrity.

A mechanism exposure is not an observed interference event. An observed event is not automatically task failure. A failed goal without event-chain evidence is unclassified or a task-capability failure, not shared-state interference.

## Decision rules

- **Solo gate:** do not run MA-ID/MA-SD for a representative unless both Solo actor goals pass. Diagnose setup/evaluator/model-operation failures separately.
- **Interference claim:** require a temporally ordered action trace, private state transition and saved-state consequence that identify the shared mechanism.
- **Recovery claim:** report only if an agent action restores its own goal and the final oracle passes. Mention unsuccessful repair attempts separately.
- **Sample interpretation:** report raw per-condition counts and individual run evidence. With n=2 per shared condition, do not claim stable rates, significance, or generalization.
- **Stopping:** if the selected agent cannot perform a task in Solo, repair only a documented infrastructure defect or stop that task. Do not change task goal, evaluator or model prompt to obtain a pass.

## Readiness checklist

Before the first model run, freeze and record:

- A6000 repository commit and clean/dirty source state;
- external OSWorld checkout and provider source hashes;
- Qwen agent class path, prompt/config files, model identifier and weight checksum/reference;
- 4090 inference endpoint health and network route;
- A6000 Guest image, app versions and task fixture hashes;
- action budget, decoding, scheduler order, artifact root and reset contract.

Pilot gate follows the frozen Workflow Suite V1 and scripted validation. This file authorizes a plan only; all model runs remain pending.

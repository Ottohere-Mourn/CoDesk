# Focus / Clipboard two-family pilot protocol (2026-11-02)

## Scope and status

This pilot covers only these mechanisms:

1. **F-04 Focus / Input Routing**: one Writer actor changes foreground; the Calc actor resumes without focus reacquisition, testing stale foreground routing.
2. **C-03 Clipboard ownership**: Calc actor copies a range; Writer actor copies text; Calc actor resumes and pastes the current shared clipboard into Calc.

This document freezes the remaining **scripted, real-Guest mechanism-control** arms. These are not LLM outcomes and must not be described as model pass rates or final case qualification.

## Frozen comparison

- Isolated arm: `ma_id`, both actors receive independent fresh Guests, each initialized with the same fixture digest.
- Shared arm: `ma_sd`, one Guest and one foreground/clipboard state shared by both actors.
- Shared+Lock arm: `ma_sd_lock`, identical shared task/fixture/schedule with one `threading.Lock` around each individual actor GUI `act` call.
- Actor schedule is fixed `actor_a` first turn â†’ `actor_b` â†’ `actor_a` resume. No prompts, fixture, actor code, evaluator, or schedule change across shared vs locked shared.
- The lock does **not** cover screenshot observation, planning/turn gaps, clipboard state, or window ownership. It is intentionally a per-input-call lock comparable to Case 2's Action Lock. Actor turns are deterministic/serial; lock wait can legitimately be zero. Do not reinterpret this as a contention stress test.
- No dedicated obstacle is injected into Shared. Task outcome is scored only from exact saved ODF state. Mechanism attribution additionally requires screenshot/window evidence for Focus or clipboard payload hashes and correct Calc paste target for Clipboard.
- Infrastructure/setup/API/scorer/reset failures stay invalid and are never counted as business FAIL. Raw logs, screenshots, overlays, and invalid runs remain preserved.
- No second repetition is required for this first mechanism-design screen.

## Run conditions and target

Target directional combination for each mechanism is:

`Isolated PASS` + `Shared FAIL` + `Shared+Lock FAIL`.

Scripted controls prove that task/fixture/evaluator and mechanism schedule can produce the intended path; they do not establish that a model will reproduce it. Any later model run needs its own frozen model/version, prompt, call budget, timeout, and evaluator parity across all three arms.

## F-04 current evidence

Run `f04-focus-scripted-isolated-20261102d` completed with `status=completed`, joint/condition success `true`, reset success `true`, wall 1,591.193 s. Both applications reached active-window/document readiness on matching fixture digest `cc3c6eeb9ef85ab2f9d3d7eb17ae11fb2378f6d2c6a9fbc9dee8233644791164`. Evaluator passed both actor goals; `known_wrong_app_content_action_count=0`, as expected in isolated mode. The run uses scripted GUI actors (`model_used=false`).

Invalid retained attempts (not denominators):

- `f04-focus-scripted-isolated-20261102a`: host Python lacked `gymnasium`; failed before Guest construction.
- `f04-focus-scripted-isolated-20261102b`: runner selected absent default OSWorld Docker image; no image was pulled.
- `f04-focus-scripted-isolated-20261102c`: used a non-reference guest-image path; Calc never reached document readiness. Guest screenshots and diagnostics were retained.

Run environment for valid arms: existing `/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2`, existing `swcub/osworld-v2.1-qemu-runtime:local`, overlays/artifacts under `/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs`. No GPU or Docker pull.

## Expected mechanism evidence

- F-04 Shared: the second actor's Writer turn should leave Writer foreground; resumed Calc actor should type without reacquiring focus, creating wrong-app content entry and failing exact joint state. Locked Shared serializes each GUI call but must still fail if the cross-turn focus gap remains exposed.
- C-03 Shared: clipboard sampler must show A's Calc payload, B's intervening Writer payload, then the paste payload equal to B's payload, with active paste target Calc. Locked Shared should retain the same global clipboard semantics and fail exact Calc state.

A failed or unexpectedly passing Shared control triggers design audit before model calls; do not tune only one arm after seeing results.


## F-04 shared-arm results (completed 2026-11-02)

Both shared arms completed as valid scripted real-Guest episodes (`status=completed`, `reset_success=true`, `model_used=false`) on fixture `cc3c6eeb9ef85ab2f9d3d7eb17ae11fb2378f6d2c6a9fbc9dee8233644791164`:

- `f04-focus-scripted-shared-20261102a` (`ma_sd`): condition/joint PASS=false; both actor goals false. The Writer actor changed foreground Calc->Writer; all four resumed Calc writes were routed to the still-foreground Writer (`known_wrong_app_content_action_count=4`, `unknown_route_count=0`). The saved Writer text contains the four Calc values while Calc remains unchanged; `observed_interference=focus_misroute_supported`. Wall 831.536 s.
- `f04-focus-scripted-locked-20261102a` (`ma_sd_lock`): condition/joint PASS=false; both actor goals false; same four-of-four wrong-app writes, exact-state failure, and `focus_misroute_supported`. Wall 769.414 s. The per-action lock wrapped 20 GUI calls (`max_concurrent_gui_act_calls=1`); no meaningful wait occurred because the fixed actor schedule is serial. Cross-turn focus staleness remains outside the lock scope, as designed.

Together with isolated `f04-focus-scripted-isolated-20261102d` (PASS, 1591.193 s), F-04 meets the **scripted mechanism-control** target `Isolated PASS + Shared FAIL + Shared+Lock FAIL`. This does not establish an LLM result or model qualification. Artifacts are under `/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/`.


## C-03 isolated-arm result (completed 2026-11-02)

`c03-clipboard-scripted-isolated-20261102a` (`ma_id`) completed with condition/joint success=true, both actor goals true, reset success=true, and wall 940.593 s. Fixture: `e34fb942fee7d2a63dd6783ce68f97d3289d13bf621d03e3afe181c4ddcb366c`. Both clipboard observers were valid (Calc 26 samples/0 failures; Writer 18/0). A's paste payload matched A's original Calc-copy payload and targeted Calc; the Writer Guest's independent copy did not overwrite Calc's clipboard (`no_overwrite_at_paste`). This is the expected isolated PASS control, not an LLM result. Artifacts are under `/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/c03-clipboard-scripted-isolated-20261102a/`.


## C-03 shared-arm result (completed 2026-11-02)

`c03-clipboard-scripted-shared-20261102a` (`ma_sd`) completed with status=completed and reset_success=true (wall 548.938 s). The condition/joint result was FAIL: actor A failed while actor B passed. The shared clipboard observer was valid (46 samples, 0 failures); A's Calc copy digest `576bb73d...bdd1fa7` (12 bytes) was replaced after B's Writer copy by digest `be4d3900...d47bb8b` (8 bytes). A's later paste targeted Calc, its payload matched B's Writer digest, and Calc A4 contains `NOTE-571` instead of the expected `Q1`; `observed_interference=clipboard_overwrite_supported`. This is valid scripted mechanism evidence, not an LLM result. Artifacts are under `/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/c03-clipboard-scripted-shared-20261102a/`.


## C-03 Shared+Lock result (completed 2026-11-02)

`c03-clipboard-scripted-locked-20261102a` (`ma_sd_lock`) completed with status=completed, condition/joint success=false, reset_success=true, wall 663.221 s. Actor A failed and actor B passed. Clipboard observer valid=true (46 samples, 0 failures); the same A-to-B payload replacement was observed as in Shared: Calc digest `576bb73d...bdd1fa7` (12 bytes), then Writer digest `be4d3900...d47bb8b` (8 bytes), then A's Calc-targeted paste carried the Writer digest. `clipboard_overwrite_supported`; Calc A4 contains `NOTE-571` rather than expected `Q1`. The per-action lock covered 18 GUI calls, max concurrency=1, with only 0.04 ms total lock wait under the fixed serial actor schedule; it does not protect clipboard state between turns. No infrastructure/scorer/reset failure.

## Pilot screen summary

All six planned scripted real-Guest arms completed validly with reset success. F-04 Focus/Input Routing: `ma_id` PASS (1591.193 s), `ma_sd` FAIL (831.536 s), `ma_sd_lock` FAIL (769.414 s). C-03 Clipboard ownership: `ma_id` PASS (940.593 s), `ma_sd` FAIL (548.938 s), `ma_sd_lock` FAIL (663.221 s). Total measured arm wall time: 5344.895 s (~89.1 min), run serially. Therefore both mechanisms meet the requested single-screen scripted target `Isolated PASS + Shared FAIL + Shared+Lock FAIL`. This is not model-based evidence; no LLM runs or repeat trials were requested or performed. The lock arm is a per-individual-GUI-action serialization control, not a stress/contention test.


## LLM pilot screen addendum (2026-11-02; supersedes the earlier "no LLM runs" sentence)

The LLM screen has now been run on the **Isolated (ma_id) gate only** using the existing local Qwen2.5-VL-7B-Instruct worker (BF16/SDPA, temperature 0, top-p 0.9, max_new_tokens 128, 20 decisions per actor). No model-specific obstacle or per-condition prompt change was introduced.

- **F-04 Focus/Input Routing** - run `focus-F04-ma_id-qwen25vl-20261102-04`: completed, `valid_model_run=true`, `model_task_outcome=FAIL`, both actor goals false, reset successful, wall 899.914 s (~15.0 min). The Calc target cells remained empty and the Writer paragraph remained "Review summary: Draft". This is an isolated task failure, not evidence of a focus misroute.
- **C-03 Clipboard** - run `c03-clipboard-ma_id-qwen25vl7b-20261102-03`: completed, `valid_model_run=true`, `model_task_outcome=FAIL`, both actor goals false, reset successful, wall 926.417 s (~15.4 min). Calc's destination range remained blank; Writer stayed at its original single paragraph. The copy observer recorded no confirmed copy events (`sequence_valid=false`), so this is failure to carry out the task, not evidence of shared-clipboard overwrite.
- Both model runs preserved full traces, inference events, screenshots, and resource records under `/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/<run_id>/`; all four run-owned containers per run have destroyed records.
- Therefore **no Shared or Shared+Lock LLM arms were launched**: neither Isolated baseline passed, so downstream FAILs could not establish a collaboration/lock mechanism effect. The six scripted Guest controls above still meet their scripted directional target, but **neither mechanism currently meets the LLM target**.
- Two earlier C-03 launch attempts are retained as invalid infrastructure attempts, not task outcomes: `...-01` failed the expected-model health check before Guest startup; `...-02` failed because the runtime Docker image was not explicitly set. The successful `...-03` run used the already-local runtime and guest image; nothing was pulled or installed.

Next model work should first change the candidate/agent-task fit (e.g. use the previously model-validated F-01 anchor for Focus and audit a model-executable Clipboard anchor), then pass the same Isolated gate before spending time on Shared arms. Do not relabel these two valid isolated FAILs as mechanism failures.


## Focus follow-up candidate freeze (before F-01 model run, 2026-11-02)

The next Focus isolated gate uses the historical F-01 Writer+Calc scalar-entry anchor because the F-04 isolated Qwen gate failed and F-01 has prior Qwen3-VL-30B success evidence (historical evidence is not counted as this run's result). The migrated local workflow version is 0.1.0, with actor A=Writer and actor B=Calc: Writer starts with Quarterly status report and must replace the document with Approved by GUI actor; Calc starts with B2=Draft and must change it to Approved, preserving other cells. Both exact ODF states and non-target integrity are scored.

The model prompts, action budget (20 decisions per actor), generation settings, fixture and schedule are frozen in source and run provenance before the new model call. The schedule is actor A's first native GUI action -> actor B's task -> actor A resume; Shared setup opens Calc then Writer so actor A initially starts in Writer. Use the already-running local Qwen2.5-VL-7B worker. Run only ma_id first. Launch the Shared and Shared+Lock arms only if both isolated actor goals pass; otherwise stop the comparison and report the model baseline gate as failed.


## F-01 second isolated gate freeze: historical Qwen3-VL class (2026-11-02)

The F-01 migration passed offline oracle checks, but its first current-model ma_id run with Qwen2.5-VL-7B-Instruct was a valid isolated FAIL. To match the model class used by the historical F-01 anchor, a separate F-01 candidate run is frozen with local Qwen3-VL-30B-A3B-Instruct, BF16/SDPA, no quantization/offload, visible physical GPUs 4 and 6 only (logical 0 and 1), max_new_tokens=128, temperature=0, top_p=0.9, 20 decisions per actor, the same frozen F-01 prompts/fixture/evaluator/action-boundary schedule. This is a separate model condition, not a continuation or pooling of the 7B result. Run ma_id first; run Shared and Shared+Lock only if both isolated actor goals pass. Do not touch any other GPU allocation; no downloads or installs.


## F-01 Qwen3-VL-30B isolated result (2026-11-02)

Run f01-focus-ma_id-qwen3vl30b-20261102-01 completed in 1003.788 s (16.7 min): valid_model_run=true, model_task_outcome=FAIL, both actor goals false, reset_success=true, with all four owned runtime containers destroyed. The exact evaluator found Writer unchanged (Quarterly status report instead of Approved by GUI actor). Calc was damaged at A1 (Record became empty), while target B2 remained Draft; the trace shows Backspace opened Delete Contents and the confirmation click cleared A1, followed by a false success termination. There was no wrong-app content routing in this isolated run (known_wrong_app_content_action_count=0) and the interference classification was unknown_or_absent. This is a valid task-execution failure, not Focus mechanism evidence. Per the frozen gate, no Shared or Shared+Lock LLM arms were launched.

### F-01 prompt-only retry freeze

A new isolated-only candidate keyboard-explicit-v2 is frozen for run f01-focus-ma_id-qwen3vl30b-prompt2-20261102-01. It keeps the same F-01 workflow version 0.1.0, Writer/Calc fixture, evaluator, Qwen3-VL-30B-A3B-Instruct service, generation settings, 20-decision actor budget, and action-boundary schedule. Only the prompts change, based on the observed failure modes: Writer explicitly uses Ctrl+A + text-entry (not Ctrl+V); Calc uses Ctrl+Home / Down / Right + text-entry and forbids Backspace/Delete. Run ma_id only; shared arms remain gated on both isolated actor goals passing. The prior failed run and artifacts remain unchanged.


## F-01 keyboard-explicit-v2 isolated gate PASS and shared-arm freeze (2026-11-02)

Run f01-focus-ma_id-qwen3vl30b-prompt2-20261102-01 completed in 725.240 s (12.1 min), valid_model_run=true, both actor goals true, joint/condition success=true, reset_success=true. The per-run exact ODF oracle passed: Writer is exactly Approved by GUI actor; Calc B2 is Approved and all other cells are unchanged. The first-action gate was valid (actor A Ctrl+A, then actor B completes, then actor A resumes). This is the first current-model-qualified F-01 isolated PASS; it does not by itself establish a focus failure.

Freeze and run the remaining F-01 arms sequentially:
- Shared ma_sd run ID: f01-focus-ma_sd-qwen3vl30b-prompt2-20261102-01
- Shared+Lock ma_sd_lock run ID: f01-focus-ma_sd_lock-qwen3vl30b-prompt2-20261102-01
- Keep identical prompts (actor A SHA256 08dc1cdaf38335882110cbfc4fba8a63e4ac9f560cc169c8666605cb4a44abd9; actor B SHA256 51ea9ed557eedf7122422e7ec5c72b76a06905ddd3d7e10574fa300908e0dda0), fixture digest ae42eb8fdd49accb800fd8c997fcf605038dd18102ea08d59418d17add77b3c8, workflow/oracle, Qwen3-VL-30B-A3B-Instruct BF16/SDPA service on GPUs 4+6, generation parameters, 20-decision budget, and actor/action-boundary schedule.
- The only intentional arm differences are one-Guest shared desktop (ma_sd) and one-Guest shared desktop plus per-GUI-act-call lock (ma_sd_lock), as frozen in the common protocol above. Do not run concurrently; report all valid/invalid outcomes without selection.


### F-01 keyboard-explicit-v2 Shared arm result and interpretation

Run f01-focus-ma_sd-qwen3vl30b-prompt2-20261102-01 completed in 416.099 s (6.9 min), valid_model_run=true, model_task_outcome=FAIL, both actor goals false, reset_success=true, with both owned containers destroyed. The report confirms the same prompts as ma_id (same two prompt hashes), same fixture and valid first-action handoff. The exact shared evaluator found no change: Writer remained Quarterly status report and Calc B2 remained Draft. The focus log shows actor B changed the active window from Writer to Calc. On its resume, actor A's screenshot/trace was the Calc desktop although its instruction remained Writer; it issued Ctrl+V then Ctrl+S, not the requested text-entry sequence. That is direct trace-level evidence of a focus/context mismatch, but the action caused no observed state mutation: known_wrong_app_content_action_count=0, keyboard_routes=[], and automated observed_interference=unknown_or_absent. Therefore record this as a valid Shared task FAIL with plausible but not yet action-effect-attributed focus misrouting; do not count it as a fully qualified mechanism result.

The pre-frozen Shared+Lock arm remains to run unchanged except for its per-individual-GUI-act-call lock. Preserve the same caution in its interpretation.


### F-01 keyboard-explicit-v2 Shared+Lock result and audit (2026-11-02)

Run f01-focus-ma_sd_lock-qwen3vl30b-prompt2-20261102-01 completed in 458.345 s (7.6 min), valid_model_run=true, model_task_outcome=FAIL, actor A PASS / actor B FAIL, reset_success=true; both owned containers have destroy records. Prompt hashes match the isolated and Shared runs. The exact final state has Writer correctly updated to Approved by GUI actor, but Calc B2 remains Draft. The trace shows actor B's keyboard navigation went one row too far in the shared desktop (two Down actions before Right), so its Calc goal failed. Actor A noticed the focus shift and clicked the Writer launcher before typing; no wrong-app content action was recorded. Thus this is a valid Shared+Lock task FAIL, but not a focus-routing failure. It demonstrates that the current model candidate still has a Shared task-navigation confound; do not qualify F-01 from the directional PASS/FAIL/FAIL tuple alone.


### F-01 keyboard-explicit-v2 triplet closeout

The frozen v2 triplet completed with three valid model runs and successful resets (total wall time 1,599.684 s / 26.7 min):
- ma_id PASS: both goals true.
- ma_sd FAIL: both goals false and exact saved state unchanged. Trace-level focus/context mismatch is visible, but no wrong-app content effect was recorded.
- ma_sd_lock FAIL: actor A PASS, actor B FAIL because it navigated to the wrong Calc row; no wrong-app content action was recorded.

Thus the *outcome tuple* is directionally PASS/FAIL/FAIL, but the mechanism attribution criterion is not met; do not count F-01 v2 as an LLM-validated Focus case. The shared arms reveal two design gaps: actor A can recover/refocus under lock, and actor B's keyboard navigation can independently fail. The next design candidate should make the delayed input a genuine already-planned keyboard/type action, while leaving the shared-vs-independent Guest as the only condition difference, and preselect both valid target widgets identically during setup. First validate the new handoff with cheap local/scripted controls and oracle before another LLM triplet.


## F-01 v0.2.0 Qwen3 stale-planned-input candidate freeze (2026-11-02)

This is a new, preregistered Focus/Input Routing candidate after the v2 triplet failed mechanism attribution. It is not a relabeling of the v2 results. The task remains exact Writer replacement by actor A and Calc B2 update by actor B; F-01 is version 0.2.0, fixture digest ae42eb8fdd49accb800fd8c997fcf605038dd18102ea08d59418d17add77b3c8. Actor A is Writer / actor B is Calc. Setup selects the existing Writer paragraph and Calc B2 through keyboard-only GUI setup in every arm and verifies the underlying ODF files remain at initial state. Shared setup opens Calc first and Writer last, so Writer is foreground with both target selections retained. Isolated actors receive separate Guests and the same per-actor fixture digest.

The Qwen3-VL-30B-A3B-Instruct endpoint remains the already-loaded offline local worker on physical GPUs 4+6, BF16/SDPA, no quantization or CPU offload. Generation is temperature 0, top-p 0.9, max_new_tokens 128; each actor has a separate Qwen3VLAgent/history and 20-decision budget. Actor A's prompt is: "In the open LibreOffice Writer document, the existing paragraph is already selected. Type exactly "Approved by GUI actor" to replace that selection, then press Ctrl+S. Do not use Ctrl+A, menus, or Ctrl+V. Do not edit Calc." Actor B's prompt is: "In LibreOffice Calc, cell B2 is already selected. Make sure Calc is the active window (switch to its open window if needed), type exactly "Approved", press Enter, and save with Ctrl+S. Do not navigate to another cell or edit Writer." Prompt SHA256: actor A 5b3f0a32963cda1c1a40672c49dbdadd73803bf0eb9101ac2415c8c09dea055b; actor B 25856ebb45fd38d59017701e78874d8a555a1050ad167b1e3fc97123decfb990.

Frozen schedule, identical in all arms: (1) Actor A observes the prepared Writer screen and asks the model for its first native action batch; (2) a coordinator callback pauses A after inference but before any GUI act, preserving that batch verbatim; (3) Actor B completes its task; (4) A resumes by dispatching its already-predicted actions without a refreshed observation or another inference. In ma_id, B acts on its separate Calc Guest and cannot change A's Writer focus. In ma_sd and ma_sd_lock, B uses the same desktop, changes foreground to Calc, and A's stale content-entry is dispatched against that foreground. The lock arm uses the same threading.Lock around each individual GUI act call only; it deliberately does not cover A's observe/think-to-act gap, so it cannot repair stale focus. This is a deterministic observation-to-action handoff schedule, not a claim that the model naturally creates concurrent overlap; the same schedule is imposed in all three arms. No condition-specific prompts, fixtures, setup selections, or recovery behavior are used.

Run only the isolated gate first: f01-focus-ma_id-qwen3vl30b-stale-v3-20261102-01. Launch ma_sd (f01-focus-ma_sd-qwen3vl30b-stale-v3-20261102-01) and then ma_sd_lock (f01-focus-ma_sd_lock-qwen3vl30b-stale-v3-20261102-01) sequentially only if the isolated run is valid/reset-clean, both actor goals pass, and Actor A's first planned native action is direct text entry (pyautogui.typewrite or pyautogui.write). Otherwise preserve the isolated evidence and stop; do not tune a shared-only prompt. No second repeat is planned.

Interpretation rule: task PASS/FAIL is the exact saved ODF oracle. Focus mechanism support additionally requires a valid planned text-entry action from A, a successful B Calc action, Actor A's stale action dispatched with active-window title identifying Calc rather than Writer, and exact non-target Calc mutation attributable to that action (e.g. B2 overwritten with A's Writer phrase) plus wrong-route metrics. Shared FAIL without this chain is only task failure. Any setup/API/model-service/reset invalidity is excluded from PASS/FAIL and retained. All run artifacts, overlays and logs remain under the RAID1 pilot run directory; do not clean prior runs or overlays. Pre-run host status: root filesystem ~58 GB free (97% used), RAID1 ~1.6 TB free; no active QEMU Guest was detected; the already loaded 30B service returned ready. No images were pulled and no packages installed for this freeze.


## F-01 v0.2.0 stale-planned-input isolated gate result

Run f01-focus-ma_id-qwen3vl30b-stale-v3-20261102-01 completed as a valid Qwen3-VL-30B real-Guest episode: PASS, actor A=true / actor B=true, reset_success=true, wall 680.050 s (11.3 min). Actor A's first predicted native action was exactly pyautogui.typewrite('Approved by GUI actor'), recorded before Actor B's turn and then dispatched from the held plan on A's separate Writer Guest. Actor B entered Approved in Calc. The exact oracle passed Writer text, Calc B2, and all non-target state. Reset passed; no Guest remains. The frozen gate therefore permits both shared arms; the run itself is not Focus mechanism evidence (expected_app was active at both content actions).


## F-01 v0.2.0 stale-planned-input Shared result

Run f01-focus-ma_sd-qwen3vl30b-stale-v3-20261102-01 completed validly: Shared task FAIL, reset_success=true, wall 381.826 s (6.4 min). Actor A's exact held first action was the same direct Writer text entry as in Isolated. Actor B first changed foreground from Writer to Calc, entered Approved at the preselected B2 and saved. After B completed, A dispatched its stale typewrite without a new observation; xdotool reported Calc as the active window before and after, while A's intended target was Writer. The final saved Calc state is B2=Approved and B3=Approved by GUI actor; Writer remains Quarterly status report. Thus the exact joint oracle fails because A's content was routed into Calc B3, and actor B's full-grid preservation goal is marked false after this post-task collateral mutation even though the target B2 edit itself is correct. Route metrics record one wrong-app content action; protocol gate classification is focus_misroute_supported. Both Guests reset cleanly. This is valid LLM Focus mechanism evidence for Shared, not an infrastructure failure. Continue to the already frozen Shared+Lock arm unchanged.


## F-01 v0.2.0 stale-planned-input Shared+Lock result and adjudication

Run f01-focus-ma_sd_lock-qwen3vl30b-stale-v3-20261102-01 completed validly as a task FAIL with reset_success=true and wall 377.368 s (6.3 min). The planned Actor A typewrite was dispatched after B's turn; Calc was the active top-level window and known_wrong_app_content_action_count=1. The per-action lock wrapped 6 GUI calls (max concurrency 1; total wait 0.016 ms; total held 18.392 s), so it did not cover the observation-to-action gap. However, the exact final Writer/Calc files equal their initial states: Actor B's B2 remained Draft and Actor A's Writer goal remained unchanged; no Calc non-target mutation or actual content effect was recorded. Therefore this is a valid Shared+Lock task FAIL and a logged wrong-app input dispatch, but it does not meet the frozen effect-level Focus attribution criterion. The machine-generated field mechanism_evidence=focus_misroute_supported is too permissive here because it keys only on the Calc window title; adjudicate this run conservatively as wrong_app_input_observed_no_state_effect, not a mechanism-supported case. This is an arm failure with a model/UI execution confound, not an infrastructure-invalid run.

The v0.2.0 LLM triplet thus yields Isolated PASS, Shared mechanism-supported FAIL, and Shared+Lock valid task FAIL without attributable state effect. It does not fully qualify the strict Isolated PASS + Shared FAIL + Shared+Lock FAIL-with-effect target. Do not count the triplet as a fully qualified Focus case. The shared-arm effect is clean; the lock arm remains the blocker.


## C-03 v0.2.0 Qwen3-VL-30B isolated gate result (2026-11-03)

Run `c03-clipboard-ma_id-qwen3vl30b-preselect-v2-20261102-01` completed as a valid model episode: `valid_model_run=true`, exact task FAIL, reset successful, wall 752.583 s (12.5 min). Both actor goals failed. The clipboard observer itself was healthy on both isolated Guests (24/0 and 26/0 samples/failures), and it confirmed the actors' copy actions; this is **not** an observer/infrastructure failure and **not** evidence of shared overwrite because it is the isolated arm.

The retained setup screenshots expose a setup-control defect in v0.2.0: Calc only had A1 active, not range A1:B2. Actor A copied a 3-byte single-cell payload and final Calc contains only Q1 in A4 rather than Q1:Q2 / 17:29 in A4:B5. Actor B correctly copied NOTE-571 but pressed Enter before paste, leaving an extra blank paragraph (`NOTE-571\n\nNOTE-571`) instead of the exact expected second paragraph. No Shared or Shared+Lock model arms were run. This candidate does not qualify Clipboard and is closed as a valid isolated task FAIL with setup/interaction difficulty, not a mechanism FAIL. Full trace and evidence are under `runs/c03-clipboard-ma_id-qwen3vl30b-preselect-v2-20261102-01/`.

## C-03 v0.2.1 Qwen3-VL-30B isolated-gate freeze (2026-11-03)

This is a new candidate after the valid v0.2.0 isolated FAIL; it is not a reclassification or overwrite. Task fixture and oracle remain unchanged (fixture SHA-256 `e34fb942fee7d2a63dd6783ce68f97d3289d13bf621d03e3afe181c4ddcb366c`). Task version is now `0.2.1`.

Setup correction, applied identically to all conditions: the Guest must show visible seeded document content before any setup clicks or model turns (Calc top-left grid pixel signal >=0.025; Writer NOTE-571 text-region signal >=0.003), in addition to expected active document title. Calc A1:B2 is selected by focusing A1, then holding Shift across Right and Down; Writer NOTE-571 is selected by clicking inside the text and using Ctrl+Home/Shift+End. Setup must leave seeded ODF state unchanged. Setup-only smoke `c03-clipboard-selection-smoke-20261103-02` validated both visible selections: Calc status bar showed+§uçâç\Selected: 2 rows, 2 columnsºw^~)Þu and Writer"éÝyø§yÜSelected: 1 word, 8 characters.ºw^~)Þu The preceding smoke `...-01` is retained as invalid setup (the former generic screenshot-difference readiness heuristic did not distinguish a Calc loading window and triggered a Writer readiness timeout); its owned Guest was destroyed.

New frozen prompts (same in ma_id, ma_sd, ma_sd_lock):
- Actor A SHA-256 `98b4519518d82594b59cb9f8f148e0ec2cd8450eab371863d3caee3ddb36027b`: copy selected Calc A1:B2 and paste beginning A4, preserve all other cells, save; do not edit Writer.
- Actor B SHA-256 `ed25d4e176f298cf1a37d3a1e327f0400d1991f2281cb1e8add68382a5065763`: copy selected Writer NOTE-571; paste into the already-existing blank second paragraph; explicitly do not press Enter/create paragraphs; save, then leave Calc foreground; do not edit Calc.

Model/limits: already-loaded local Qwen3-VL-30B-A3B-Instruct (same worker endpoint and generation as F-01), separate actor instances and histories, temperature 0, top-p 0.9, max_new_tokens 128, 20 decisions/actor. Clipboard schedule unchanged: confirm Actor A copy from observer, let B copy and finish its Writer task / foreground Calc, then resume A to paste the already-copied payload; identical coordinator schedule across all three conditions. Isolated Guests open Calc then Writer in both actor environments; Shared has the same app order. No condition-specific setup or prompt.

Run only the isolated gate first: `c03-clipboard-ma_id-qwen3vl30b-preselect-v3-20261103-01`. Continue to Shared and then Shared+Lock only if isolated is a valid/reset-clean exact PASS for both goals, both copies are observer-confirmed, and A's paste observer reports the expected Calc target. Otherwise retain the attempt and stop without counting downstream model FAILs. Infrastructure/setup invalidity is never task FAIL.


## C-03 v0.2.1 Qwen3-VL-30B isolated gate result (2026-11-03)

Run `c03-clipboard-ma_id-qwen3vl30b-preselect-v3-20261103-01` completed validly: `valid_model_run=true`, exact task PASS, actor A=true / actor B=true, reset_success=true, wall 846.478 s (14.1 min). Both clipboard observers were healthy (24 and 26 samples, zero failures). Actor A's observer-confirmed Calc copy payload digest was `576bb73db619d55dc924c7f7c8d328a5e0df71b5f1c7e98f166c22378bdd1fa7`; Actor B's Writer copy digest was `be4d3900bf45518e586d422a31670f9399dfe23a7cfd26e017e9b0c45d47bb8b`. Each actor's paste routed to its intended app; exact Calc A4:B5 and Writer second paragraph states passed with all guards/non-target state preserved. The prepared UI screenshots for both actor Guests showed Calc A1:B2 selected and Writer NOTE-571 selected before model turns. The runner's generic cross-Guest clipboard-interference summary is `unknown` for ma_id by design; the copy gates and exact isolated oracle are valid. This is the required isolated PASS gate for the frozen candidate. Shared may now run; preserve its identical prompts/setup/schedule.


## C-03 v0.2.1 Shared attempt `-01`: setup-invalid (2026-11-03)

Run `c03-clipboard-ma_sd-qwen3vl30b-preselect-v3-20261103-01` did not reach a model turn. During Calc setup, a LibreOffice"éÝyø§yÜnot respondinféÝyø§yÝ dialog was captured; the earlier visible-content heuristic mistakenly treated the gray dialog as rendered grid, then the target-preselection check failed. Status is `invalid_infrastructure_or_setup`, `valid_model_run=false`; the run-owned Guest has a `destroyed` ledger event and no model inference/artifacts. This is not a task FAIL and is excluded. Artifact screenshots/events are retained under that run directory.

Readiness erratum for the same v0.2.1 candidate: Calc visibility now requires a strong repeated grid/text edge signal (>=0.05 in the upper-left grid crop); this rejects both a blank loading canvas and the observed uniform gray nonresponsive dialog, while loaded Calc screenshots signal ~0.188. Target preselection now clicks a safely visible mid-sheet cell at (100,400), uses Ctrl+Home, and extends to B2, avoiding toolbar/banner coordinate variation. This is a setup/readiness-only correction; fixture, exact oracle, prompts, actors and schedules are unchanged. The isolated PASS remains valid and remains the gate. Retry Shared once using the frozen candidate; preserve all attempts.


## C-03 v0.2.1 Shared Qwen3-VL-30B result (2026-11-03): valid task FAIL, no clipboard effect

Run `c03-clipboard-ma_sd-qwen3vl30b-preselect-v3-20261103-02` completed as a valid model episode with reset_success=true, wall 658.751 s (11.0 min), and a valid clipboard observer (66 samples / 0 failures). Actor A's Calc source copy was confirmed with the expected 12-byte source digest `576bb73dºw^~)Þvbdd1fa7`, but Actor B never produced an observer-confirmed Writer copy; the Qwen actor repeatedly clicked the wrong dock location while trying to reach Writer and exhausted its 20-decision budget. The gate therefore has `actor_b_copy_confirmed=false`, `sequence_valid=false`; there was no measured Aºw^~)ÞvB clipboard replacement. The final Calc content also landed one row above target (A3 rather than A4), and Writer remained unchanged, so both actor goals failed. This is a valid Shared task FAIL caused by app-switch/target-navigation failures, **not** Clipboard mechanism evidence. Do not count it as Shared mechanism FAIL; no Shared+Lock v0.2.1 model run was launched. Artifacts are retained under the run directory.

## C-03 v0.3.0 controlled-target-context candidate freeze (2026-11-03)

The v0.2.1 model screen identified two non-clipboard confounds: in Shared the LLM could not reliably switch Calcºw^~)ÞvWriter (B never copied), and A's post-handoff paste target click landed at A3. v0.3.0 keeps the same ODF fixture, exact actor goals, local model class/limits, and model copy/paste actions, but gives each actor the same role-appropriate foreground/selection at turn entry using coordinator-controlled UI-only context normalization. This is intended to isolate the global clipboard ownership variable; the coordinator never reads, changes, clears, or copies the clipboard.

Frozen cross-condition schedule:
1. Setup opens Calc then Writer; selects Calc A1:B2 and Writer NOTE-571; exact seeded files remain unchanged.
2. Actor A copies A1:B2; observer confirms copy and gate yields before its paste.
3. Before Actor B's turn, the coordinator verifies Writer is foreground on Actor B's bound desktop (activates the existing Writer window only if necessary). In `ma_id`, this is Actor B's private Guest; in Shared/Shared+Lock it is the same Shared Guest. Thus B begins with Writer active in every arm.
4. Actor B copies the selected NOTE-571, pastes it into the existing blank second paragraph (no extra paragraphs), saves and terminates.
5. Coordinator activates Calc on Actor A's bound desktop and keyboard-selects A4 using a GUI click in the visible mid-sheet, Ctrl+Home, then three Down key presses. This occurs in every arm; the same state (Calc/A4 selected) is shown to A on resume. It performs no edit/save and no clipboard operation.
6. Actor A resumes, presses Ctrl+V into preselected A4 and saves. In `ma_id`, A's private clipboard still contains its Calc range; in Shared and Shared+Lock the single clipboard should contain B's NOTE-571. The per-action lock remains around model GUI-act calls only and cannot isolate/lock the OS clipboard.

Updated common prompts: Actor A is told that after the coordination pause A4 will already be selected and to paste/save without clicking or navigating. Actor B is told Writer is role-active at turn start; to copy/paste/save and not switch applications (the coordinator normalizes A's foreground after B terminates). Prompt hashes and exact text are recorded in report/provenance and below before the isolated gate. No condition-specific actor prompt or clipboard manipulation is allowed.

This is a new schedule/prompt candidate and requires its own isolated gate before any Shared arms. Run only `ma_id` first; Shared then Shared+Lock may proceed sequentially only if isolated is a valid, reset-clean exact PASS, both observer-confirmed copy gates succeed and both paste targets are valid. A Shared task FAIL without A's paste observing B's digest and a Calc A4 paste target is not Clipboard mechanism support. Preserve all attempts; no repeat trial is planned.


## C-03 v0.3.0 exact prompt freeze and isolated run authorization (2026-11-03)

Fixture SHA-256 remains `e34fb942fee7d2a63dd6783ce68f97d3289d13bf621d03e3afe181c4ddcb366c`. Exact prompts (UTF-8 SHA-256):
- Actor A: `82a3077c4072c9707d6614f23b7f0393622f9c42d5ff5a4ac8ad654ba4cb6558`  In LibreOffice Calc, the complete source range A1:B2 is selected. Copy it. After the coordination pause, Calc cell A4 will already be selected for you. Do not click or navigate; press Ctrl+V to paste, then save with Ctrl+S. Preserve the source, guard cells, and every other cell. Do not edit Writer.
- Actor B: `4302d4c03491d6c41220c922f5aff75be812daee8d2afaa40ba5833e220e20c9`  LibreOffice Writer is active and the first paragraph "NOTE-571" is selected. Copy it. The document already has a blank second paragraph immediately below it. Click inside that existing blank paragraph and paste exactly one copy there. Do NOT press Enter or create any paragraphs. Keep the first paragraph unchanged and save with Ctrl+S. Do not switch applications; the coordinator handles the next actor window. Do not edit Calc.

Use Qwen3-VL-30B-A3B-Instruct from the already-running offline loopback worker at 127.0.0.1:15488; CUDA_VISIBLE_DEVICES=4,6; BF16/SDPA, no quantization/offload; temperature=0, top_p=0.9, max_new_tokens=128; separate actor instances/histories; 20 decisions per actor. Run only `c03-clipboard-ma_id-qwen3vl30b-rolectx-v1-20261103-01` first. Artifact parent is `/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs`. Preflight on 2026-11-03: source compiles, workflow tests 9/9 pass, git diff --check clean, endpoint ready on expected model, no active QEMU/model episode detected; /mnt/raid1 had 1.6 TB free. Root remained 97% used with 58 GB free; swap full but host reported 161 GB available RAM. No cleanup, package install, image pull, or Docker pull.

Proceed to Shared only if this isolated run is a valid model run, exact PASS for both actors, reset-clean, both observer-confirmed copies, and Actor A's paste samples the expected Calc payload at a Calc target after the handoff. Proceed to Shared+Lock only if Shared independently has the same valid observer-confirmed overwrite chain and exact target condition; otherwise stop after preserving the evidence. No repeats are planned. Any model task FAIL, invalid episode, bad sequence, or inconclusive clipboard digest stops downstream arms; do not reinterpret as Clipboard support.


## C-03 v0.3.0 isolated-gate result and metrics audit (2026-11-03)

Run `c03-clipboard-ma_id-qwen3vl30b-rolectx-v1-20261103-01` completed validly: model_task_outcome=PASS, both exact actor goals=true, reset_success=true, valid_model_run=true, wall 800.067 s (13.3 min). Fixture digest matched the freeze. Clipboard observers: actor A 24 samples/0 failures; actor B 30/0. Role-context handoffs confirmed Writer/Calc foreground as scheduled, unchanged ODF state, and no coordinator clipboard operation. Both actor copy gates fired. Actor A copied SHA-256 `576bb73db619d55dc924c7f7c8d328a5e0df71b5f1c7e98f166c22378bdd1fa7`; Actor B copied `be4d3900bf45518e586d422a31670f9399dfe23a7cfd26e017e9b0c45d47bb8b`. Actor A's raw observer sample before Ctrl+V (event 139) was the original A digest at `calc.fods - LibreOffice Calc`; the isolated exact oracle confirms A4:B5 and B's second Writer paragraph, with guards/non-target state intact. Recomputed from retained raw events after the reporting correction, evidence is copy A event 77 -> copy B event 89 -> A paste event 139, paste digest equals A's original digest, target Calc, overwrite=false, classification `no_overwrite_at_paste`. Therefore the v0.3.0 isolated gate passes all preregistered continuation checks; Shared is authorized.

Metrics audit: the initial report's derived `clipboard_evidence` had unknown/null fields because it searched for literal `ctrl+v`, while this runner's native action serialization is `pyautogui.hotkey('ctrl', 'v')`. The raw event log contains the full observer evidence above. Corrected the derived metric to normalize native Ctrl+V syntax and added unit tests covering both private original-digest and shared intervening-overwrite classifications; workflow tests now pass 11/11. This is an analysis/reporting-only change after the isolated episode; no fixture, prompt, actor, generation, GUI setup, schedule, model, budget or condition contract changed. Source hashes before/after are retained in the isolated provenance and current worktree; raw evidence remains authoritative.



## C-03 v0.3.0 Shared Qwen3-VL-30B result and Shared+Lock gate (2026-11-03)

Run `c03-clipboard-ma_sd-qwen3vl30b-rolectx-v1-20261103-01` completed validly: exact joint task FAIL, Actor A=false / Actor B=true, reset_success=true, valid_model_run=true, wall 449.162 s (7.5 min). Shared observer was healthy (42 samples / 0 failures); sequence_valid=true and both actor copy gates fired. Actor A copied expected Calc range digest `576bb73db619d55dc924c7f7c8d328a5e0df71b5f1c7e98f166c22378bdd1fa7` (event 45); Actor B copied Writer NOTE-571 digest `be4d3900bf45518e586d422a31670f9399dfe23a7cfd26e017e9b0c45d47bb8b` (event 57). Before Actor A's paste, the observer read B's digest; the paste targeted active Calc (event 113), not a focus misroute. Exact final Calc A4 is NOTE-571 rather than Q1, and Actor B's Writer goal is exact PASS with no extra paragraph. Derived classification after the reporting-only metric fix is `clipboard_overwrite_supported`; this is valid LLM Shared Clipboard mechanism evidence. Proceed to the already frozen Shared+Lock arm unchanged. This is not causal evidence that a lock blocks nothing generally; it is this lock-scope arm's result.



## C-03 v0.3.0 Shared+Lock Qwen3-VL-30B result and triplet closeout (2026-11-03)

Run `c03-clipboard-ma_sd_lock-qwen3vl30b-rolectx-v1-20261103-01` completed validly: exact joint task FAIL, Actor A=false / Actor B=true, reset_success=true, valid_model_run=true, wall 437.533 s (7.3 min). Shared+Lock observer was healthy (40 samples / 0 failures); sequence_valid=true; both copy confirmations succeeded. Copy A event 43 digest was `576bb73db619d55dc924c7f7c8d328a5e0df71b5f1c7e98f166c22378bdd1fa7`; copy B event 55 digest was `be4d3900bf45518e586d422a31670f9399dfe23a7cfd26e017e9b0c45d47bb8b`; A paste event 105 read B's digest with Calc foreground. Exact final Calc A4 is NOTE-571, not Q1; Writer second paragraph is correct and no wrong-app focus route occurred. Derived classification is `clipboard_overwrite_supported`.

The per-action lock was enabled for 10 native GUI act calls, max concurrent act calls=1, total wait=0.035 ms; it does not cover the observe/think/yield gap, coordinator GUI setup, or the OS clipboard state. This staged schedule is intentionally serialized. Therefore do not claim a lock-versus-no-lock effect on overlapping clipboard API calls: the result demonstrates that this specified per-act lock does not preserve an earlier payload across an actor's later copy in a shared clipboard. Both Shared arms produced the same valid Clipboard mechanism-supported task failure.

C-03 v0.3.0 Qwen triplet closeout: Isolated exact PASS (800.067 s), Shared mechanism-supported exact FAIL (449.162 s), Shared+Lock mechanism-supported exact FAIL (437.533 s); combined model runtime 1,686.762 s = 28.1 min. All three runs were valid and reset-clean; no repeats planned. Thus this C-03 candidate satisfies the requested single-run Isolated PASS / Shared FAIL / Shared+Lock FAIL pattern. It is one candidate only; no separate clipboard repeat is required.



## F-01 v0.3.0 role-context-normalized stale-input candidate freeze (2026-11-03)

This is a new F-01 candidate after F-01 v0.2.0 reached Isolated PASS + Shared mechanism-supported FAIL but its Shared+Lock run lacked an attributable state effect and Actor B did not pass. Prior v0.2.0 artifacts remain untouched. Fixture digest remains `ae42eb8fdd49accb800fd8c997fcf605038dd18102ea08d59418d17add77b3c8`; exact task oracle and initial/final states are unchanged. Only F-01 task version is advanced to 0.3.0. Setup uses the existing UI preselection (complete Writer paragraph; Calc B2).

Exact prompts and SHA-256:
- Actor A `bb6970b4b394e4c602b81688dbad5b62d4045834a4a59a50649edeade22d0529`: LibreOffice Writer is active and the complete existing paragraph is selected. Replace it by typing exactly "Approved by GUI actor", then save with Ctrl+S. Do not use Ctrl+A, menus, or Ctrl+V. Do not edit Calc.
- Actor B `13e7c1681ab28f9eacb9de99d0d95c82e1692b1ed23837f10017a41987d84859`: LibreOffice Calc is active and cell B2 is already selected. Replace Draft by typing exactly "Approved", press Enter to commit, then save with Ctrl+S. Do not navigate to another cell or switch applications. Do not edit Writer.

Controlled schedule, identical across ma_id / ma_sd / ma_sd_lock:
1. Verify both exact fixtures and visible document content; require active-window title plus the screenshot content signal. A title over an LO blank/loading window is setup-invalid, not a model result.
2. Normalize Actor A to active Writer with its paragraph selected. Actor A observes and predicts its first action; pause before any GUI action and preserve the plan.
3. Normalize Actor B to active Calc / B2; run B to completion. Before resuming A, read the exact ODF oracle to record whether B's B2 goal actually passed, then coordinator-select B2 again without editing or touching clipboard.
4. Resume A by dispatching the held plan verbatim without another model observation. In ma_id, B's Calc work is in a distinct Guest, so A's Writer remains active. In ma_sd / ma_sd_lock, B's task and restored B2 selection are on the same Guest, so A's stale typewrite is dispatched into Calc B2. The lock remains only around each GUI act call, excluding the decision/handoff gap and coordinator actions.

Effect-level Focus support requires: valid direct content-entry plan; B's pre-resume exact Calc goal passed; A's held action dispatched with Calc foreground; exact Calc B2 changed to A's Writer phrase; and exact final ODF oracle/reset checks. Shared task FAIL absent this chain is not mechanism evidence. Only run Shared after isolated is a valid/reset-clean exact PASS for both actor goals, A's first planned action is direct typewrite/write, and the preserved action schedule is valid. Run Shared+Lock only if Shared independently yields the actor-B pre-resume pass and the effect-level chain. No repeat planned.

Model remains the already-loaded local offline Qwen3-VL-30B-A3B-Instruct endpoint 127.0.0.1:15488; CUDA_VISIBLE_DEVICES=4,6, BF16/SDPA, no quant/offload; temperature 0, top_p .9, max_new_tokens 128; two separate actor instances/history; 20 decisions per actor. Artifact parent is `/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs`. Isolated first: `f01-focus-ma_id-qwen3vl30b-rolectx-v1-20261103-01`. Continue only on gate pass, then `f01-focus-ma_sd-qwen3vl30b-rolectx-v1-20261103-01`, then `f01-focus-ma_sd_lock-qwen3vl30b-rolectx-v1-20261103-01`.

Setup/readiness risk to retain: older v0.2.0 screenshots show the Writer title while the screenshot was still a blank/loading canvas in at least the isolated and lock attempts; the new strict visible-content gate is intentionally retained, so such an episode must stop as setup-invalid rather than count PASS/FAIL. Shared v0.2.0 Writer screenshot did show content. This new candidate must independently pass its own visible UI setup; do not weaken the gate to reach an LLM turn.


## F-01 v0.3.0 isolated attempt -01: invalid Qwen transport (2026-11-03)

Run `f01-focus-ma_id-qwen3vl30b-rolectx-v1-20261103-01` completed after 671.153 s. Both private Guests passed visible UI setup and the resets passed, but both actors' first inference requests immediately returned `RemoteDisconnected: Remote end closed connection without response` (19.83 ms and 7.87 ms). The report has `valid_model_run=false`, `model_task_outcome=environment_invalid`, model_failure_class=`model_service_failure`; there is no task PASS/FAIL and no model output/action. This attempt is preserved and excluded.

Read-only service diagnosis: 127.0.0.1:15488 /health still returned ready for the expected Qwen3-VL-30B model, but the serving PID 1782775 had stdout/stderr redirected to anonymous pipes whose only open endpoints were the worker's own descriptors (pipe inode scan found no consumer). The worker logs every /infer request to stdout before inference; writing to a disconnected pipe causes the handler to close the connection, consistent with both immediate RemoteDisconnected errors. The old worker's exact command/model/GPU mapping were verified (model Qwen3-VL-30B-A3B-Instruct, CUDA_VISIBLE_DEVICES=4,6; no current benchmark/QEMU episode remained). A controlled service restart is needed with stdout/stderr redirected to a durable RAID log before retrying the same isolated gate. Do not count -01 as a model attempt/result.

## F-01 v0.3.0 isolated retry -02 (2026-11-03)

Run `f01-focus-ma_id-qwen3vl30b-rolectx-v1-20261103-02` completed as a valid Qwen3-VL-30B-A3B-Instruct real-Guest episode: `valid_model_run=true`, exact `model_task_outcome=PASS`, both actor goals true, `joint_success=true`, and `reset_success=true`; wall time was 714.187 s (11.9 min). Strict Writer and Calc visible-content setup checks passed. The exact ODF evaluator confirms Writer text exactly "Approved by GUI actor", Calc B2 exactly "Approved", and all non-target state unchanged.

The planned-input schedule was valid: Actor A's first action was `pyautogui.typewrite('Approved by GUI actor')`; Actor B completed first and its pre-resume exact Calc goal passed; Actor A then dispatched the held action. As expected in ma_id, Writer remained foreground and no wrong-app dispatch/effect was observed. This is an isolated PASS, not mechanism evidence by itself.

Before this retry, the local model worker on 127.0.0.1:15488 was restarted with stdout/stderr redirected to a durable RAID log because the previous worker had broken anonymous output pipes and returned immediate RemoteDisconnected errors. The same offline BF16/SDPA/no-offload Qwen model on physical GPUs 4+6 passed an `/infer` smoke request (`OK`), and the pilot suite passed 11 tests. The earlier -01 transport-invalid run remains preserved and excluded.

The isolated gate now permits the frozen Shared arm `f01-focus-ma_sd-qwen3vl30b-rolectx-v1-20261103-01`. Run it sequentially and preserve its outcome; launch Shared+Lock only if the pre-resume and effect-level Shared gates pass as specified above.

## F-01 v0.3.0 Shared arm result (2026-11-03)

Run `f01-focus-ma_sd-qwen3vl30b-rolectx-v1-20261103-01` completed as a valid model run with `model_task_outcome=FAIL`, `reset_success=true`, and wall time 400.701 s (6.7 min). Actor B's exact Calc goal passed immediately before Actor A resumed. Actor A had planned direct text entry against Writer while the active window was Writer; after B completed on the shared desktop, the frozen held action was dispatched without a new observation, with Calc active before and after.

This meets the strict effect-level focus gate: `wrong_app=true`, `wrong_app_content_mutation_observed=true`, and `wrong_app_effect_attributed_after_actor_b_success=true`. The exact final oracle found Writer unchanged and Calc B2 changed from the correct intermediate "Approved" to "Approved by GUI actor". Thus this is a mechanism-supported Shared FAIL, not an infrastructure-invalid or unrelated task failure. The run reset successfully.

The frozen protocol now permits the Shared+Lock arm `f01-focus-ma_sd_lock-qwen3vl30b-rolectx-v1-20261103-01`; keep all prompts, fixture, schedule, and gates unchanged.

## F-01 v0.3.0 Shared+Lock result and triplet conclusion (2026-11-03)

Run `f01-focus-ma_sd_lock-qwen3vl30b-rolectx-v1-20261103-01` completed as a valid model run with `model_task_outcome=FAIL`, `reset_success=true`, and wall time 382.698 s (6.4 min). The Shared+Lock run reproduced the effect-level chain: Actor B passed its exact pre-resume Calc goal; the same held Actor A text-entry plan was then dispatched with Calc active and `wrong_app=true`; the exact final state has Writer unchanged and Calc B2 overwritten by "Approved by GUI actor". The report classifies `focus_misroute_supported` and `wrong_app_effect_attributed_after_actor_b_success=true`.

The lock was enabled and covered one GUI act call at a time, excluding the observation/think gap. Therefore this result shows that this per-act lock does not repair the frozen stale-focus handoff; it is not a claim that a broader lock covering observation through dispatch would fail. The one-pass F-01 v0.3.0 candidate now meets the requested directional tuple: Isolated PASS (714.187 s), Shared mechanism-supported FAIL (400.701 s), Shared+Lock mechanism-supported FAIL (382.698 s), all three valid with successful reset checks. No second repeat was run.

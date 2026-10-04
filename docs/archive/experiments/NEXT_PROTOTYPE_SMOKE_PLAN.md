# Next CoDesk Prototype Smoke Plan

## Entry gate

Do not launch until host CPU pressure is compatible with the existing Guest protocol,
swap is no longer exhausted, and no unrelated experiment is using the Guest capacity.
Use one worker and one Guest first. Do not stop, reset, or remove any resource without
the current-run ownership ID and ledger evidence required by `AGENTS.md`.

## Scripted order

1. **F1 Focus / Writer+Calc:** run Writer Solo, Calc Solo, then MA-SD and the recovery
   control from the existing fixed task. Capture active-window/focus evidence before each
   keyboard action. For generated office instances, first parameterize the actors with the
   instance's exact target strings; current fixed-string actors are not a valid seed runner.
2. **C1 Clipboard 001:** run Writer Solo and Calc Solo, then paired MA-SD with observer
   off and observer on from identical clean reset states. Compare clipboard digest/owner,
   action timing, saved files, and screenshots. Require stable observer reads and target
   attribution before interpreting paste failures. Validate same-backend MA-ID separately;
   the legacy separate-workspace runner is not a valid substitute.
3. **A1 Browser Context:** install the generated local server in the Guest, launch both URLs
   as tabs in one Chromium window, and verify two actor-specific exact submissions. Join
   page `visibilitychange` events with X11 active-window ID samples. Require a constant
   top-level window ID and observed tab changes; otherwise context evidence is `unknown`.
4. **M1 Modal:** verify Writer and Calc readiness and one-actor Save As controls first.
   Then interleave a normal first-actor Save As dialog with the second Actor's independent
   app observation. Do not send a blind confirmation. Only confirm a dialog after its
   owner, target path, and native format are visible and recorded. If LibreOffice blocks
   the second window, preserve that as the observed mechanism and provide a recoverable wait.

For each mechanism, require each Actor Solo, both goals jointly reachable, a negative
control, a reset check, exact saved-state scoring, and a complete raw event/screenshot
bundle before calling the scripted smoke passed. Exposure, terminal task failure, and
recovery remain separate fields.

## Model entry gate

Only after the corresponding scripted Guest gates pass, run the pinned Qwen3VLAgent as
two separate actor instances with separate histories, observations, budgets, and run IDs.
First run Solo A/B, then MA-ID, then MA-SD, one valid episode each. Hold task seed, backend,
instructions, model settings, and actor schedule fixed. Do not substitute a scripted second
Actor. Preserve all invalid-environment runs and failures. Add repeats only for mechanisms
whose first runs show distinct failure or recovery signatures.

## Artifact contract

Every run should carry: task/template/instance/version, condition, both actor IDs and target
goals, Guest/window/tab/dialog/clipboard identities available to observers, raw action and
observation trajectory, screenshots at state transitions, exact initial/final artifacts,
reset check, provenance, evaluator output, and environment-validity status. Missing mechanism
instrumentation must be reported as `unknown`.

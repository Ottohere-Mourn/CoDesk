# Case 3 Lite follow-up: editor readiness and topology variability

The v1.4.2 real-Guest pilot did not establish a stable independent-pass/shared-fail contrast. The independent run `runs/case3-lite-pair-isolated-v142-20261030c` passed. Ordinary shared passed once (`...shared-v142-20261030a`) and failed once (`...shared-v142-20261030b`); action-locked shared failed (`...shared-v142-lock-20261030a`). The failed runs' action traces show input crossing between Chrome and VS Code. The successful shared run is valid and remains in the record.

An additional setup inconsistency was visible in `browser_setup.jsonl`: after the initial `filtering.py` window check, VS Code sometimes showed `Welcome - Visual Studio Code` when browser setup completed. The old setup did not recheck the editor at model release. Version 1.4.3 reopens and confirms `filtering.py` after all browser windows exist, closes any Welcome window, and restores the appropriate active window: A's editor for independent desktops, B's browser for the shared desktop. The task, fixture, Oracle, model, and 12-call-per-actor budget are unchanged. The API default now uses the user-provided `https://docode.cc/v1` fallback because the primary endpoint was unreliable during Case 4 testing.

The same-version additional locked run, `runs/case3-lite-pair-shared-v142-lock-20261030b`, failed only `browser_retest_pass`. A and B each used all 12 calls; the repaired source passed Python acceptance, but B did not submit the final browser test. All 24 desktop actions recorded `window_samples_atomic: true`. The run reset was verified, the app container was removed, and no cleanup errors were recorded. This is a second v1.4.2 action-locked shared failure, still not a pass-rate estimate.

The v1.4.3 shared setup-only run `runs/case3-lite-v143-setup-shared-20261030a` returned `SETUP_PASS`. Its final screenshot, `guest_A_stabilized.png`, shows the prepared OrderDesk browser in front and `filtering.py` open behind it; the Welcome page is absent. No model calls were made. Paired model trials follow below.

| v1.4.3 condition | Run directory | A / B desktop calls | Result | Failed Oracle checks |
| --- | --- | ---: | --- | --- |
| Independent desktops | `runs/case3-lite-pair-isolated-v143-20261030a` | 6 / 7 | PASS | None |
| Shared desktop | `runs/case3-lite-pair-shared-v143-20261030a` | 12 / 10 | FAIL | `python_filter_acceptance_pass`, `browser_retest_pass` |
| Shared, action lock | `runs/case3-lite-pair-shared-v143-lock-20261030a` | 12 / 11 | FAIL | `python_filter_acceptance_pass`, `browser_retest_pass` |
| Shared repeat | `runs/case3-lite-pair-shared-v143-20261030b` | — | INFRA_FAIL | No model episode; A Chrome bootstrap page stayed blank |
| Shared retry | `runs/case3-lite-pair-shared-v143-20261030c` | 9 / 12 | Raw `MODEL_COMPLETED`; post-hoc FAIL | `python_filter_acceptance_pass`, `browser_retest_pass` |

The independent run recorded the broken three-row Dana + Processing result with Enter before A's edit, then an empty NW-2402 + Processing result with Apply under the saved source hash. All seven Oracle checks passed. `RESET_VERIFIED`, app removal, and no cleanup errors were recorded. No late B resume was needed. The combined 13 desktop calls meet the intended 10–15-call scale.

The locked shared run recorded the initial browser defect, but the final source hash remained the initial hash and there was no final browser retest. All 23 recorded desktop actions used the same per-Guest lock (`window_samples_atomic: true`). B's text input and key actions landed in VS Code while A was editing, and A's later actions began in Chrome. Both actors tried to recover focus, then A exhausted 12 calls. The run reset and app cleanup passed. This is a valid shared failure despite successful editor stabilization; it does not imply every shared run will fail.

The ordinary shared run also recorded the initial browser defect, but its final source hash remained the initial hash and its final browser retest was absent. A used all 12 calls; B used 10. Action traces show A's save keystroke starting in Chrome and B's text input landing in VS Code. The run reset and app cleanup passed. Its unmodified source and missing retest make it a business failure, not a setup or timeout invalidation.

The first ordinary-shared repeat never reached model start: after 20 browser-readiness checks, A's Chrome still showed a blank bootstrap page and the app had no login event. The runner marked this `INFRA_FAIL` and cleaned up the app and Guest. It is excluded from business-result counts. A fresh-run retry used the unchanged v1.4.3 code and a new overlay.

The fresh retry began from the same initial `filtering.py` SHA-256 `dbcbd9fe1f847e802f3b88e18311954f2811513c60a6aa6aa828ec9b2843e216` as the other valid v1.4.3 runs. A saved a syntactically valid but wrong-signature `filter_orders` implementation; B sent a message claiming a final submission, but the application recorded no final Apply event. The old Oracle called the candidate with three arguments and raised `TypeError`, so the raw runner stopped at `MODEL_COMPLETED` with `evaluation_error` and did not reset. It must not be counted as a valid runner-scored FAIL or PASS. The original `pair_pilot_result.json` is unchanged.

## v1.4.4 evaluator repair

Version 1.4.4 keeps the task, fixture, GUI setup, model, and budget unchanged. The Oracle now catches candidate-call exceptions (including wrong function signatures and runtime errors), reports a failed `python_filter_acceptance_pass`, and handles a missing candidate file without aborting evaluation. The pair runner separately attempts owned reset even if evaluation itself raises, and labels such a crash `EVALUATION_ERROR` rather than leaving the ambiguous `MODEL_COMPLETED` status.

Eleven Case 3 tests pass, including new wrong-signature, runtime-error, and deleted-file controls. Evaluating the preserved v1.4.3 retry workspace with v1.4.4 code produced `posthoc_oracle_result_v144.json`: `joint_business_success=false`, with `python_filter_acceptance_pass` and `browser_retest_pass` false and candidate `TypeError` recorded. The run then completed `RESET_VERIFIED`; its raw result remains untouched. This post-hoc score is explicitly a corrected evaluation of a v1.4.3 episode, not a new v1.4.4 model trial.

Across the valid v1.4.3 pilot episodes, independent passed once, ordinary shared failed once, and action-locked shared failed once. The post-hoc retry is also a business failure but is reported separately because the original scorer crashed. Earlier v1.4.2 ordinary shared passed once. This is evidence of focus contention and a one-run topology contrast under stabilized setup, not proof of a stable failure probability or guaranteed shared-desktop failure.
